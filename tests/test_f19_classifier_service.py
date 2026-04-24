"""F19 · Bk-Dispatch — ClassifierService facade tests.

Covers Test Inventory: T27, T37, T44.
SRS: FR-022 · §IC ClassifierService.classify · §DA seq msg#1/#2/#3 ·
     §IS flow EnabledCheck / FallbackDecorator audit.

Layer marker:
  # [unit] — LLM endpoint mocked via respx; keyring via monkeypatch; audit
  # writer captured via a spy. Real-http and real-keyring integration live
  # in tests/integration/test_f19_real_http.py (T31) and
  # tests/integration/test_f19_real_keyring.py (T36).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import respx


GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


class _AuditSpy:
    """Captures audit events passed to ClassifierService.

    The actual ClassifierService API is expected to accept a callback with the
    shape ``audit_sink(event: dict[str, Any]) -> None``. We record every call
    and expose ``events`` for assertions.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


def _valid_envelope(verdict: dict[str, Any]) -> dict[str, Any]:
    import json as _json

    return {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": _json.dumps(verdict)},
                "finish_reason": "stop",
            }
        ]
    }


# ---------------------------------------------------------------------------
# T27 — FUNC/happy — Traces To: FR-022 · §IS flow EnabledCheck=false
# Kills: enabled=False still hitting LLM (wastes quota + breaks offline mode).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t27_classifier_service_enabled_false_uses_rule_only_no_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.models import ClassifierConfig, ClassifyRequest
    from harness.dispatch.classifier.service import ClassifierService

    cfg = ClassifierConfig(
        enabled=False,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    service = ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "classifier_prompt.json",
    )
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    # Set up respx; we will assert ZERO requests made (off-switch must skip LLM).
    # [TEST-FIX] respx.mock() defaults to assert_all_called=True which breaks
    # tests that deliberately assert a route was NOT called. Flip the flag off.
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(GLM_URL)
        verdict = await service.classify(req)

    assert verdict.verdict == "COMPLETED"
    assert verdict.backend == "rule"
    assert not route.called, "enabled=False must not fire any HTTP request to the LLM"


# ---------------------------------------------------------------------------
# T37 — FUNC/error — Traces To: §IC classify 永不抛 contract
# Kills: any exception bubbling to F20 (state-machine deadlock).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t37_classifier_service_never_raises_even_on_all_backends_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import ClassifierConfig, ClassifyRequest
    from harness.dispatch.classifier.service import ClassifierService

    def _boom_keyring(self: KeyringGateway, service: str, user: str):  # noqa: ARG001
        raise RuntimeError("keyring totally broken")

    monkeypatch.setattr(KeyringGateway, "get_secret", _boom_keyring, raising=True)

    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    service = ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "classifier_prompt.json",
    )
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    # [TEST-FIX] T37 keyring is broken, so LlmBackend raises BEFORE hitting
    # respx — the route is intentionally unreached; disable assert_all_called.
    with respx.mock(assert_all_called=False) as mock:
        mock.post(GLM_URL).mock(side_effect=httpx.ConnectError("network gone"))
        # Contract: classify MUST return a Verdict, never raise.
        verdict = await service.classify(req)

    assert verdict.verdict in {"COMPLETED", "CONTINUE", "RETRY", "ABORT", "HIL_REQUIRED"}
    assert verdict.backend == "rule"


# ---------------------------------------------------------------------------
# T44 — BNDRY/edge — Traces To: §IC FallbackDecorator.invoke audit log
# Kills: silent fallback (no audit trail → ops cannot diagnose regressions).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t44_classifier_service_emits_audit_fallback_on_http_5xx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import ClassifierConfig, ClassifyRequest
    from harness.dispatch.classifier.service import ClassifierService

    monkeypatch.setattr(
        KeyringGateway,
        "get_secret",
        lambda self, service, user: "sk-t",  # noqa: ARG005
        raising=True,
    )

    spy = _AuditSpy()
    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    service = ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "classifier_prompt.json",
        audit_sink=spy,
    )
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock() as mock:
        mock.post(GLM_URL).respond(502, text="Bad Gateway")
        verdict = await service.classify(req)

    # Fallback happened (backend=rule) AND audit captured it.
    assert verdict.backend == "rule"
    fallback_events = [e for e in spy.events if e.get("event") == "classifier_fallback"]
    assert len(fallback_events) >= 1, f"no classifier_fallback audit event; got {spy.events!r}"
    cause = fallback_events[0].get("cause", "")
    # Cause must mention the http failure mode (5xx / http_error / status code).
    assert any(
        token in str(cause).lower() for token in ("http", "5xx", "502")
    ), f"audit cause must identify http failure; got {cause!r}"
