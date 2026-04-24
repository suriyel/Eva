"""F19 · Bk-Dispatch — LlmBackend HTTP + schema tests (respx mock).

Covers Test Inventory: T16, T17, T18, T19, T25, T46.
SRS: FR-023 AC-1/AC-2 · §IC LlmBackend.invoke · §DA seq msg#4/#5 · §IS flow HttpResult/ParseJson/SchemaCheck.

Layer marker:
  # [unit] — httpx endpoint is mocked via respx; keyring via monkeypatch.
  # Real OpenAI-compat HTTP timeout lives in tests/integration/test_f19_real_http.py (T31).

Rule 5a note: Real-HTTP integration (T31) + Real-keyring (T36) live in the
integration folder. These unit tests mock both deliberately to isolate
LlmBackend's request shaping & schema handling.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx


GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def _valid_schema_envelope(verdict_payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap a verdict dict into an OpenAI-compat chat-completions response."""
    import json as _json

    return {
        "id": "cmpl-xyz",
        "object": "chat.completion",
        "model": "glm-4-plus",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": _json.dumps(verdict_payload)},
                "finish_reason": "stop",
            }
        ],
    }


def _build_llm_backend(monkeypatch: pytest.MonkeyPatch):
    """Construct an LlmBackend wired against the GLM preset with a mocked keyring."""
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.llm_backend import LlmBackend
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    preset = ProviderPresets().resolve("glm")

    # Stub keyring.get_secret to always return a fixed token.
    def _fake_get_secret(
        self: KeyringGateway, service: str, user: str
    ) -> str | None:  # noqa: ARG001
        return "sk-test-key-LOOKUP"

    monkeypatch.setattr(KeyringGateway, "get_secret", _fake_get_secret, raising=True)

    return LlmBackend(preset=preset, keyring=KeyringGateway())


# ---------------------------------------------------------------------------
# T16 — FUNC/happy — Traces To: FR-023 · §IC invoke · §DA seq msg#5/#6 (schema_ok)
# Kills: schema_ok path returning backend="rule" (layer mis-tag).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t16_llm_backend_returns_hil_required_verdict_on_valid_schema(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_llm_backend(monkeypatch)
    req = ClassifyRequest(
        exit_code=0,
        stderr_tail="",
        stdout_tail="Would you like to proceed?",
        has_termination_banner=False,
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.post(GLM_URL).respond(
            200,
            json=_valid_schema_envelope(
                {
                    "verdict": "HIL_REQUIRED",
                    "reason": "assistant paused for a question",
                    "anomaly": None,
                    "hil_source": "user_question",
                }
            ),
        )
        verdict = await backend.invoke(req, prompt="CLASSIFIER SYSTEM PROMPT")

    assert verdict.verdict == "HIL_REQUIRED"
    assert verdict.backend == "llm"
    assert verdict.reason  # non-empty reason string
    assert verdict.hil_source == "user_question"


# ---------------------------------------------------------------------------
# T17 — FUNC/error — Traces To: FR-023 AC-1 · §IS flow FallbackParse
# Kills: malformed JSON treated as opaque success (backend=llm).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t17_llm_backend_raises_protocol_error_on_non_json_body(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_llm_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    # Return a 200 whose assistant content is NOT valid JSON.
    with respx.mock(assert_all_called=True) as mock:
        mock.post(GLM_URL).respond(
            200,
            json={
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "not json {"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )
        with pytest.raises(ClassifierProtocolError):
            await backend.invoke(req, prompt="prompt")


# ---------------------------------------------------------------------------
# T18 — FUNC/error / SEC/prompt-injection — Traces To: FR-023 AC-2 · §IS flow FallbackSchema
# Kills: LLM output ingested regardless of verdict enum (state-machine poisoning).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t18_llm_backend_raises_protocol_error_on_out_of_enum_verdict(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_llm_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(assert_all_called=True) as mock:
        mock.post(GLM_URL).respond(
            200,
            json=_valid_schema_envelope(
                {
                    "verdict": "SHUTDOWN",  # out-of-enum injection attempt
                    "reason": "malicious",
                    "anomaly": None,
                    "hil_source": None,
                }
            ),
        )
        with pytest.raises(ClassifierProtocolError):
            await backend.invoke(req, prompt="prompt")


# ---------------------------------------------------------------------------
# T19 — FUNC/error — Traces To: §IS flow FallbackHttp
# Kills: timeout bubbling up to F20 (state-machine deadlock).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t19_llm_backend_raises_http_error_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierHttpError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_llm_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(assert_all_called=True) as mock:
        mock.post(GLM_URL).mock(side_effect=httpx.TimeoutException("simulated"))
        with pytest.raises(ClassifierHttpError):
            await backend.invoke(req, prompt="prompt")


# ---------------------------------------------------------------------------
# T25 — SEC/keyring — Traces To: FR-021 AC-1 · §IC invoke · IAPI-014
# Kills: api_key leaking into config.json instead of keyring; missing Bearer header.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t25_llm_backend_sends_authorization_bearer_from_keyring(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_llm_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(GLM_URL).respond(
            200,
            json=_valid_schema_envelope(
                {
                    "verdict": "COMPLETED",
                    "reason": "done",
                    "anomaly": None,
                    "hil_source": None,
                }
            ),
        )
        await backend.invoke(req, prompt="prompt")

    assert route.called, "LlmBackend must actually POST to /v1/chat/completions"
    sent_request = route.calls.last.request
    auth = sent_request.headers.get("authorization", "")
    # Header must carry the keyring-sourced token (note Bearer prefix, case-insensitive).
    assert auth.lower().startswith("bearer "), f"missing Bearer prefix: {auth!r}"
    assert "sk-test-key-LOOKUP" in auth, "api_key from keyring must be sent as Bearer"


# ---------------------------------------------------------------------------
# T46 — INTG/http-shape — Traces To: §DA seq msg#5 · request body contract
# Kills: response_format.type missing or strict!=True (letting T18 slip by).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t46_llm_backend_request_body_declares_strict_json_schema(
    monkeypatch: pytest.MonkeyPatch,
):
    import json as _json

    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_llm_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(GLM_URL).respond(
            200,
            json=_valid_schema_envelope(
                {
                    "verdict": "CONTINUE",
                    "reason": "ongoing",
                    "anomaly": None,
                    "hil_source": None,
                }
            ),
        )
        await backend.invoke(req, prompt="SYSTEM PROMPT")

    sent = route.calls.last.request
    body = _json.loads(sent.content.decode("utf-8"))
    # Assert strict schema envelope present.
    rf = body.get("response_format", {})
    assert (
        rf.get("type") == "json_schema"
    ), f"response_format.type must be 'json_schema', got {rf!r}"
    schema_obj = rf.get("json_schema", {})
    assert schema_obj.get("strict") is True, "json_schema.strict must be true"
    # The verdict enum must be declared in the schema (defense against T18).
    schema = schema_obj.get("schema", {})
    verdict_enum = schema.get("properties", {}).get("verdict", {}).get("enum", [])
    assert "HIL_REQUIRED" in verdict_enum and "SHUTDOWN" not in verdict_enum
