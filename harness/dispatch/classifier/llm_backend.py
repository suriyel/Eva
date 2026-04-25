"""F19 · LlmBackend — httpx AsyncClient + OpenAI-compat chat completions.

Feature design §IC LlmBackend.invoke (+ Wave 3 §6.1.4 / §3a):
    * HTTP POST <base_url>/v1/chat/completions with 10 s timeout
      (IFR-004 PERF).
    * Dual-path request body by ``effective_strict`` (§3a):
        - ``effective_strict=True`` → body includes
          ``response_format = json_schema + strict=true`` (defense against T18).
        - ``effective_strict=False`` → body OMITS ``response_format``; system
          message = ``prompt + _JSON_ONLY_SUFFIX`` to nudge JSON-only output
          (FR-023 AC-3, IFR-004 AC-mod). URL / method / Authorization /
          temperature unchanged across both paths.
    * Authorization: Bearer <key> from KeyringGateway (IAPI-014).
    * Tolerant JSON extraction (``_extract_json``) applied to every response:
      strip ``<think>...</think>`` blocks → scan for first balanced top-level
      JSON object via bracket counting. Always used (strict-on & strict-off).
    * Raises ``ClassifierHttpError`` on timeout / connection / 4xx/5xx.
    * Raises ``ClassifierProtocolError`` on JSON invalid / schema / out-of-enum
      (Wave 3: tolerant extractor failure surfaces as
      ``cause='json_parse_error'`` → FallbackDecorator audit → rule fallback).
"""

from __future__ import annotations

import json as _json
import re
from typing import Any

import httpx

from ...auth import KeyringGateway
from .errors import ClassifierHttpError, ClassifierProtocolError
from .models import ClassifyRequest, ProviderPreset, Verdict


_TIMEOUT_SECONDS = 10.0
_KEYRING_SERVICE = "harness-classifier"

_VERDICT_ENUM = ("HIL_REQUIRED", "CONTINUE", "RETRY", "ABORT", "COMPLETED")
_ANOMALY_ENUM = (
    "context_overflow",
    "rate_limit",
    "network",
    "timeout",
    "skill_error",
)

_VERDICT_SCHEMA = {
    "name": "verdict_schema",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict", "reason", "anomaly", "hil_source"],
        "properties": {
            "verdict": {
                "type": "string",
                "enum": list(_VERDICT_ENUM),
            },
            "reason": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1024,
            },
            "anomaly": {
                "type": ["string", "null"],
                "enum": [*_ANOMALY_ENUM, None],
            },
            "hil_source": {"type": ["string", "null"]},
        },
    },
}


# ---------------------------------------------------------------------------
# Wave 3 (§3a) — fixed JSON-only suffix appended to system prompt when
# ``effective_strict=False`` (prompt-only substitute for json_schema).
# ---------------------------------------------------------------------------
_JSON_ONLY_SUFFIX = (
    "\n\n[STRICT OUTPUT CONTRACT] 只输出一个严格 JSON 对象："
    '{"verdict": "...", "reason": "...", "anomaly": null|"...", "hil_source": null|"..."}'
    "。不要包裹 markdown 代码块，不要输出 <think> 推理链，不要输出额外文本。"
)


# ---------------------------------------------------------------------------
# Wave 3 (§3a) — tolerant JSON extractor
# ---------------------------------------------------------------------------
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _extract_json(content: str) -> dict[str, Any]:
    """Strip ``<think>...</think>`` blocks, scan for first balanced JSON object.

    Pure function (idempotent). Used by **both** strict-on and strict-off
    paths — strict-on simply benefits from ``<think>`` stripping as a no-op.

    Raises ``ClassifierProtocolError(cause='json_parse_error')`` when:
        * no balanced top-level ``{...}`` object is present, or
        * every candidate object fails ``json.loads``.
    """
    stripped = _THINK_BLOCK_RE.sub("", content)

    # Bracket-count scanner: find each '{' and scan forward for the matching
    # balanced '}', respecting string literals + escape chars. Yield the first
    # candidate that parses as a JSON dict.
    text = stripped
    idx = 0
    n = len(text)
    while idx < n:
        # Locate next '{'.
        start = text.find("{", idx)
        if start == -1:
            break

        depth = 0
        in_string = False
        escape = False
        end = -1
        for i in range(start, n):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end == -1:
            # No balanced match starting at ``start`` — abandon; extractor fails.
            break

        candidate = text[start : end + 1]
        try:
            parsed = _json.loads(candidate)
        except (ValueError, _json.JSONDecodeError):
            # Skip this candidate; advance past the opening brace and retry.
            idx = start + 1
            continue

        if isinstance(parsed, dict):
            return parsed

        # Non-dict top-level JSON (array / number / str) → skip + continue.
        idx = end + 1

    raise ClassifierProtocolError(
        "tolerant extractor found no balanced JSON object", cause="json_parse_error"
    )


def _build_url(base_url: str) -> str:
    """Ensure trailing slash + append ``chat/completions``."""
    base = base_url.rstrip("/") + "/"
    return base + "chat/completions"


def _build_request_body(
    req: ClassifyRequest,
    prompt: str,
    *,
    model: str,
    effective_strict: bool,
) -> dict[str, Any]:
    """Build the chat-completions POST body.

    Wave 3 (§3a) dual-path:
        * ``effective_strict=True`` → include ``response_format.json_schema``.
        * ``effective_strict=False`` → OMIT ``response_format`` key entirely;
          append ``_JSON_ONLY_SUFFIX`` to the system prompt to compensate.

    URL / method / Authorization / ``temperature=0`` unchanged between paths
    (IFR-004 AC-mod).
    """
    user_payload = {
        "exit_code": req.exit_code,
        "stderr_tail": req.stderr_tail,
        "stdout_tail": req.stdout_tail,
        "has_termination_banner": req.has_termination_banner,
    }
    system_content = prompt if effective_strict else prompt + _JSON_ONLY_SUFFIX
    body: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": _json.dumps(user_payload)},
        ],
    }
    if effective_strict:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": _VERDICT_SCHEMA,
        }
    return body


class LlmBackend:
    """httpx-based OpenAI-compat chat-completions backend."""

    def __init__(
        self,
        preset: ProviderPreset,
        keyring: KeyringGateway,
        *,
        model_name: str | None = None,
        timeout: float = _TIMEOUT_SECONDS,
        effective_strict: bool | None = None,
    ) -> None:
        """Build an LlmBackend.

        Wave 3 (§3a): ``effective_strict`` is fixed at construction time. When
        not supplied, it defaults to ``preset.supports_strict_schema`` so that
        legacy callers preserve pre-Wave-3 semantics.
        """
        self._preset = preset
        self._keyring = keyring
        self._model_name = model_name or preset.default_model
        self._timeout = timeout
        self._effective_strict = (
            effective_strict if effective_strict is not None else preset.supports_strict_schema
        )

    async def invoke(self, req: ClassifyRequest, prompt: str) -> Verdict:
        """POST to <base_url>/v1/chat/completions; return strict Verdict(backend='llm')."""
        # ---- api_key lookup (keyring) ----
        try:
            api_key = self._keyring.get_secret(_KEYRING_SERVICE, self._preset.api_key_user_slot)
        except Exception as exc:  # keyring totally broken → map to http_error
            raise ClassifierHttpError(f"keyring unavailable: {exc}", cause="keyring_error") from exc

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = _build_url(self._preset.base_url)
        body = _build_request_body(
            req,
            prompt,
            model=self._model_name,
            effective_strict=self._effective_strict,
        )

        # ---- HTTP POST with timeout ----
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ClassifierHttpError(str(exc), cause="http_timeout") from exc
        except httpx.ConnectError as exc:
            raise ClassifierHttpError(str(exc), cause="connection_error") from exc
        except httpx.HTTPError as exc:
            raise ClassifierHttpError(str(exc), cause="http_error") from exc

        if resp.status_code >= 400:
            raise ClassifierHttpError(f"HTTP {resp.status_code}", cause=f"http_{resp.status_code}")

        # ---- Response parsing ----
        try:
            envelope = resp.json()
        except (ValueError, _json.JSONDecodeError) as exc:
            raise ClassifierProtocolError(
                "non-json response body", cause="json_parse_error"
            ) from exc

        try:
            assistant = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ClassifierProtocolError(
                "missing choices[0].message.content", cause="schema_mismatch"
            ) from exc

        # Wave 3 (§3a): tolerant extractor — strip <think> blocks + scan for
        # first balanced JSON object; used for both strict-on and strict-off
        # paths. Raises ClassifierProtocolError(cause='json_parse_error').
        parsed = _extract_json(assistant)

        verdict_value = parsed.get("verdict")
        if verdict_value not in _VERDICT_ENUM:
            raise ClassifierProtocolError(
                f"verdict {verdict_value!r} not in enum", cause="verdict_out_of_enum"
            )

        anomaly_value = parsed.get("anomaly")
        if anomaly_value is not None and anomaly_value not in _ANOMALY_ENUM:
            raise ClassifierProtocolError(
                f"anomaly {anomaly_value!r} not in enum", cause="schema_mismatch"
            )

        reason_value = parsed.get("reason")
        if not isinstance(reason_value, str) or not reason_value:
            raise ClassifierProtocolError(
                "reason must be a non-empty string", cause="schema_mismatch"
            )

        return Verdict(
            verdict=verdict_value,
            reason=reason_value,
            anomaly=anomaly_value,
            hil_source=parsed.get("hil_source"),
            backend="llm",
        )


__all__ = ["LlmBackend", "_JSON_ONLY_SUFFIX", "_extract_json"]
