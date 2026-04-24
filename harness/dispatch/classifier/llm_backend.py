"""F19 · LlmBackend — httpx AsyncClient + OpenAI-compat chat completions.

Feature design §IC LlmBackend.invoke:
    * HTTP POST <base_url>/v1/chat/completions with 10 s timeout
      (IFR-004 PERF).
    * response_format = json_schema + ``strict=true`` (defense against T18).
    * Authorization: Bearer <key> from KeyringGateway (IAPI-014).
    * Raises ``ClassifierHttpError`` on timeout / connection / 4xx/5xx.
    * Raises ``ClassifierProtocolError`` on JSON invalid / schema / out-of-enum.
"""

from __future__ import annotations

import json as _json
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


def _build_url(base_url: str) -> str:
    """Ensure trailing slash + append ``chat/completions``."""
    base = base_url.rstrip("/") + "/"
    return base + "chat/completions"


def _build_request_body(
    req: ClassifyRequest,
    prompt: str,
    *,
    model: str,
) -> dict[str, Any]:
    user_payload = {
        "exit_code": req.exit_code,
        "stderr_tail": req.stderr_tail,
        "stdout_tail": req.stdout_tail,
        "has_termination_banner": req.has_termination_banner,
    }
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": _json.dumps(user_payload)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": _VERDICT_SCHEMA,
        },
    }


class LlmBackend:
    """httpx-based OpenAI-compat chat-completions backend."""

    def __init__(
        self,
        preset: ProviderPreset,
        keyring: KeyringGateway,
        *,
        model_name: str | None = None,
        timeout: float = _TIMEOUT_SECONDS,
    ) -> None:
        self._preset = preset
        self._keyring = keyring
        self._model_name = model_name or preset.default_model
        self._timeout = timeout

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
        body = _build_request_body(req, prompt, model=self._model_name)

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

        try:
            parsed = _json.loads(assistant)
        except (ValueError, _json.JSONDecodeError) as exc:
            raise ClassifierProtocolError(
                "assistant content is not valid JSON", cause="json_parse_error"
            ) from exc

        if not isinstance(parsed, dict):
            raise ClassifierProtocolError("assistant JSON must be object", cause="schema_mismatch")

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


__all__ = ["LlmBackend"]
