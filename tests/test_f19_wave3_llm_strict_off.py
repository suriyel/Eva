"""F19 Wave 3 · LlmBackend strict-off body shape + tolerant JSON extraction.

Covers Test Inventory rows **T48 / T49 / T50 / T51** (Wave 3 —
FR-023 AC-3/4/5/6/7 · IFR-004 AC-mod).

Layer marker:
    # [unit] — respx mocks the HTTP endpoint; keyring via monkeypatch.

Rule 5 note:
    Real-HTTP integration for Wave 3 is delivered by the existing
    ``tests/integration/test_f19_real_minimax.py`` smoke (T52,
    marker=real_external_llm). This unit file only asserts local request
    shaping + tolerant parse behaviour.

SRS trace:
    FR-023 AC-3 — strict-off body omits response_format + JSON-only suffix
    FR-023 AC-4 — strict-off returns Verdict(backend='llm') on clean JSON
    FR-023 AC-5 — `<think>...</think>` prefix is stripped
    FR-023 AC-6 — multi-JSON → first balanced object wins
    FR-023 AC-7 — no JSON → ClassifierProtocolError(cause='json_parse_error')
                  → FallbackDecorator audit + RuleBackend fallback
    IFR-004 AC-mod — URL/method/Authorization identical to strict-on path
"""

from __future__ import annotations

import json as _json
from typing import Any

import httpx
import pytest
import respx


GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MINIMAX_URL = "https://api.minimax.chat/v1/chat/completions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _chat_envelope(content: str) -> dict[str, Any]:
    """Wrap any assistant ``content`` into an OpenAI-compat chat-completions envelope."""
    return {
        "id": "cmpl-w3",
        "object": "chat.completion",
        "model": "glm-4-plus",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _valid_verdict_json(verdict: str = "COMPLETED", reason: str = "ok") -> str:
    return _json.dumps(
        {
            "verdict": verdict,
            "reason": reason,
            "anomaly": None,
            "hil_source": None,
        }
    )


def _new_backend(
    *,
    preset_name: str = "glm",
    strict: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    """Build an LlmBackend with the given effective_strict flag.

    The Wave 3 contract requires ``LlmBackend`` to accept an
    ``effective_strict`` keyword at construction time (design §3a). If the
    parameter is missing, ``TypeError`` is raised → the test correctly FAILs
    red until the Wave 3 Green lands.
    """
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.llm_backend import LlmBackend
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    preset = ProviderPresets().resolve(preset_name)

    class _FakeKeyring(KeyringGateway):
        def get_secret(self, service, user):  # type: ignore[override]
            return "sk-fake-wave3"

    return LlmBackend(
        preset=preset,
        keyring=_FakeKeyring(),
        model_name=preset.default_model,
        effective_strict=strict,
    )


# ===========================================================================
# T48 — FUNC/happy — strict-off body shape (FR-023 AC-3 · IFR-004 AC-mod)
# ===========================================================================
@pytest.mark.asyncio
async def test_t48a_strict_off_body_omits_response_format_key(
    monkeypatch: pytest.MonkeyPatch,
):
    """Kills: MiniMax provider rejects body with ``response_format`` key."""
    from harness.dispatch.classifier.models import ClassifyRequest

    captured: dict[str, Any] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["body"] = _json.loads(request.content.decode("utf-8"))
        captured["headers"] = dict(request.headers)
        captured["url"] = str(request.url)
        captured["method"] = request.method
        return httpx.Response(
            200,
            json=_chat_envelope(_valid_verdict_json("COMPLETED")),
        )

    backend = _new_backend(preset_name="glm", strict=False, monkeypatch=monkeypatch)
    req = ClassifyRequest(
        exit_code=0, stderr_tail="", stdout_tail="done", has_termination_banner=False
    )

    with respx.mock(base_url="https://open.bigmodel.cn", assert_all_called=True) as mock:
        mock.post("/api/paas/v4/chat/completions").mock(side_effect=_capture)
        await backend.invoke(req, prompt="SYSTEM PROMPT BODY")

    body = captured["body"]
    assert (
        "response_format" not in body
    ), f"strict-off body MUST omit response_format; got keys={sorted(body)!r}"


@pytest.mark.asyncio
async def test_t48b_strict_off_system_message_ends_with_json_only_suffix(
    monkeypatch: pytest.MonkeyPatch,
):
    """Kills: tolerant-parse provider missing JSON-only nudge → returns markdown."""
    from harness.dispatch.classifier.llm_backend import _JSON_ONLY_SUFFIX
    from harness.dispatch.classifier.models import ClassifyRequest

    captured: dict[str, Any] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["body"] = _json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=_chat_envelope(_valid_verdict_json()))

    backend = _new_backend(preset_name="glm", strict=False, monkeypatch=monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(base_url="https://open.bigmodel.cn", assert_all_called=True) as mock:
        mock.post("/api/paas/v4/chat/completions").mock(side_effect=_capture)
        await backend.invoke(req, prompt="CUSTOM PROMPT BODY")

    messages = captured["body"]["messages"]
    system_msgs = [m for m in messages if m.get("role") == "system"]
    assert system_msgs, "system message missing entirely"
    content = system_msgs[-1]["content"]
    assert content.endswith(_JSON_ONLY_SUFFIX), (
        "strict-off system message MUST end with the fixed JSON-only suffix; "
        f"tail={content[-80:]!r}"
    )
    assert content.startswith(
        "CUSTOM PROMPT BODY"
    ), "PromptStore.current must prefix the system message (before the suffix)"


@pytest.mark.asyncio
async def test_t48c_strict_off_url_method_auth_identical_to_strict_on(
    monkeypatch: pytest.MonkeyPatch,
):
    """AC-mod: URL / HTTP method / Authorization header do NOT change between paths.

    Kills: strict-off branch accidentally downgrades to GET / strips bearer /
    routes to a different URL.
    """
    from harness.dispatch.classifier.models import ClassifyRequest

    captured_off: dict[str, Any] = {}
    captured_on: dict[str, Any] = {}

    def _capture_into(bucket: dict[str, Any]):
        def _impl(request: httpx.Request) -> httpx.Response:
            bucket["url"] = str(request.url)
            bucket["method"] = request.method
            bucket["authorization"] = request.headers.get("Authorization")
            return httpx.Response(200, json=_chat_envelope(_valid_verdict_json()))

        return _impl

    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    for strict_flag, bucket in ((False, captured_off), (True, captured_on)):
        backend = _new_backend(preset_name="glm", strict=strict_flag, monkeypatch=monkeypatch)
        with respx.mock(base_url="https://open.bigmodel.cn", assert_all_called=True) as mock:
            mock.post("/api/paas/v4/chat/completions").mock(side_effect=_capture_into(bucket))
            await backend.invoke(req, prompt="P")

    assert (
        captured_off["url"] == captured_on["url"]
    ), f"URL diverged: off={captured_off['url']!r} vs on={captured_on['url']!r}"
    assert captured_off["method"] == captured_on["method"] == "POST"
    assert captured_off["authorization"] == captured_on["authorization"] == "Bearer sk-fake-wave3"


# ===========================================================================
# T49 — FUNC/happy — `<think>...</think>` prefix stripped (FR-023 AC-5)
# ===========================================================================
@pytest.mark.asyncio
async def test_t49a_tolerant_extract_strips_think_prefix_and_parses_json(
    monkeypatch: pytest.MonkeyPatch,
):
    """Kills: reasoning-model ``<think>`` tag leaks into JSON parser → failure."""
    from harness.dispatch.classifier.models import ClassifyRequest

    content = "<think>step 1: analyse; step 2: decide COMPLETED</think>\n" + _valid_verdict_json(
        "COMPLETED", reason="looks clean"
    )

    backend = _new_backend(preset_name="glm", strict=False, monkeypatch=monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(base_url="https://open.bigmodel.cn", assert_all_called=True) as mock:
        mock.post("/api/paas/v4/chat/completions").mock(
            return_value=httpx.Response(200, json=_chat_envelope(content))
        )
        verdict = await backend.invoke(req, prompt="P")

    assert verdict.verdict == "COMPLETED", f"expected COMPLETED, got {verdict.verdict!r}"
    assert verdict.reason == "looks clean"
    assert verdict.backend == "llm", "strict-off parse success must preserve backend=llm"


# ===========================================================================
# T50 — FUNC/happy — first balanced JSON object wins (FR-023 AC-6)
# ===========================================================================
@pytest.mark.asyncio
async def test_t50a_tolerant_extract_picks_first_balanced_json_object(
    monkeypatch: pytest.MonkeyPatch,
):
    """Kills: greedy scan concatenates all JSON → parse explodes / picks last."""
    from harness.dispatch.classifier.models import ClassifyRequest

    first_json = _json.dumps(
        {"verdict": "CONTINUE", "reason": "a", "anomaly": None, "hil_source": None}
    )
    second_json = _json.dumps({"other": "junk"})
    content = "前言文本" + first_json + "后续 " + second_json

    backend = _new_backend(preset_name="glm", strict=False, monkeypatch=monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(base_url="https://open.bigmodel.cn", assert_all_called=True) as mock:
        mock.post("/api/paas/v4/chat/completions").mock(
            return_value=httpx.Response(200, json=_chat_envelope(content))
        )
        verdict = await backend.invoke(req, prompt="P")

    assert (
        verdict.verdict == "CONTINUE"
    ), f"tolerant extractor must pick the first balanced JSON, got verdict={verdict.verdict!r}"
    assert verdict.backend == "llm"


# ===========================================================================
# T51 — FUNC/error — no JSON → ClassifierProtocolError(json_parse_error)
#                 → FallbackDecorator audit + RuleBackend fallback (AC-7)
# ===========================================================================
@pytest.mark.asyncio
async def test_t51a_tolerant_extract_no_json_raises_protocol_error_with_json_parse_error_cause(
    monkeypatch: pytest.MonkeyPatch,
):
    """LlmBackend.invoke raises ClassifierProtocolError(cause='json_parse_error').

    Kills: tolerant extractor silently returns None → upstream assumes success.
    """
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _new_backend(preset_name="glm", strict=False, monkeypatch=monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(base_url="https://open.bigmodel.cn", assert_all_called=True) as mock:
        mock.post("/api/paas/v4/chat/completions").mock(
            return_value=httpx.Response(200, json=_chat_envelope("对不起我无法分类"))
        )
        with pytest.raises(ClassifierProtocolError) as excinfo:
            await backend.invoke(req, prompt="P")

    assert (
        getattr(excinfo.value, "cause", None) == "json_parse_error"
    ), f"expected cause='json_parse_error', got cause={getattr(excinfo.value, 'cause', None)!r}"


@pytest.mark.asyncio
async def test_t51b_classifier_service_no_json_content_falls_back_to_rule_with_audit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    """End-to-end AC-7: ClassifierService stays 永不抛 and audits json_parse_error.

    Kills: FallbackDecorator misses the new ProtocolError cause → upstream
    receives a bogus Verdict(backend='llm') or an un-audited fallback.
    """
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import (
        ClassifierConfig,
        ClassifyRequest,
    )
    from harness.dispatch.classifier.service import ClassifierService

    class _FakeKeyring(KeyringGateway):
        def get_secret(self, service, user):  # type: ignore[override]
            return "sk-fake"

    audit: list[dict[str, Any]] = []

    cfg = ClassifierConfig(
        enabled=True,
        provider="minimax",
        base_url="https://api.minimax.chat/v1/",
        model_name="MiniMax-M2.7-highspeed",
        # Wave 3: None → preset (MiniMax=False) → effective_strict=False.
        strict_schema_override=None,
    )
    service = ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "prompt.json",
        keyring=_FakeKeyring(),
        audit_sink=audit.append,
    )
    req = ClassifyRequest(
        exit_code=0, stderr_tail="", stdout_tail="all good", has_termination_banner=False
    )

    with respx.mock(base_url="https://api.minimax.chat", assert_all_called=True) as mock:
        mock.post("/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json=_chat_envelope("对不起我无法分类 — no JSON emitted at all"),
            )
        )
        verdict = await service.classify(req)

    # 永不抛: returned a Verdict, rule backend took over.
    assert (
        verdict.backend == "rule"
    ), f"no-JSON path MUST fall back to rule backend; got backend={verdict.backend!r}"
    assert (
        verdict.verdict == "COMPLETED"
    ), f"RuleBackend should decide COMPLETED for exit_code=0 + no banner; got {verdict.verdict!r}"

    # AC-7: audit one line with event=classifier_fallback, cause=json_parse_error.
    fallback_events = [e for e in audit if e.get("event") == "classifier_fallback"]
    assert fallback_events, f"no classifier_fallback audit event recorded; audit={audit!r}"
    causes = [e.get("cause") for e in fallback_events]
    assert (
        "json_parse_error" in causes
    ), f"expected cause='json_parse_error' in audit; got causes={causes!r}"
