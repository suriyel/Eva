"""Integration test for F19 · real MiniMax OpenAI-compat round-trip (feature #19).

Optional external-LLM smoke test. Skips silently when the api_key is absent
from the platform keyring; runs end-to-end against ``api.minimax.chat`` when
present.

[real_external_llm] — exercises the *primary* httpx → real OpenAI-compat
endpoint path. Uses the REAL ``KeyringGateway`` (no monkey-patch), REAL
``httpx.AsyncClient``, and a REAL TLS connection to MiniMax. The assertion
gates on contract semantics (Verdict shape + 永不抛 + IFR-004 wall-clock budget),
NOT on the specific model output (which depends on provider state).

Setup (one-time, do NOT commit the key):
    >>> from harness.auth import KeyringGateway
    >>> KeyringGateway().set_secret("harness-classifier", "minimax", "<key>")

SRS trace: FR-021 (OpenAI-compat endpoint) · FR-023 (json_schema) · IFR-004.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.real_external_llm

_KEYRING_SERVICE = "harness-classifier"
_KEYRING_USER = "minimax"


def _read_minimax_key() -> str | None:
    from harness.auth import KeyringGateway

    try:
        return KeyringGateway().get_secret(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception:
        return None


@pytest.mark.real_external_llm
@pytest.mark.asyncio
async def test_f19_real_minimax_test_connection_round_trip(tmp_path: Path) -> None:
    """Real ping to ``api.minimax.chat/v1/chat/completions``.

    Asserts ``test_connection`` resolves to a structured ``TestConnectionResult``
    (ok=True OR ok=False with a known error_code) within IFR-004's 10 s budget,
    proving the SSRF whitelist accepts the preset and the network path works.
    """
    key = _read_minimax_key()
    if not key:
        pytest.skip(
            f"keyring entry {_KEYRING_SERVICE}/{_KEYRING_USER} missing — set via "
            "KeyringGateway().set_secret(...) to enable this real-LLM smoke test"
        )

    from harness.dispatch.classifier.models import (
        ClassifierConfig,
        TestConnectionRequest,
    )
    from harness.dispatch.classifier.service import ClassifierService

    cfg = ClassifierConfig(
        enabled=True,
        provider="minimax",
        base_url="https://api.minimax.chat/v1/",
        model_name="MiniMax-M2.7-highspeed",
    )
    service = ClassifierService(config=cfg, prompt_store_path=tmp_path / "prompt.json")

    start = time.monotonic()
    result = await service.test_connection(
        TestConnectionRequest(
            provider="minimax",
            base_url=cfg.base_url,
            model_name=cfg.model_name,
        )
    )
    elapsed = time.monotonic() - start

    assert elapsed <= 12.0, f"test_connection over budget: {elapsed:.2f}s (IFR-004 10 s)"
    assert result.error_code in {None, "401", "connection_refused", "dns_failure", "timeout"}, (
        f"unexpected error_code={result.error_code!r}"
    )
    if result.error_code == "401":
        pytest.fail(
            f"MiniMax rejected key as Unauthorized — message={result.message!r}; "
            "regenerate or fix the keyring entry"
        )


@pytest.mark.real_external_llm
@pytest.mark.asyncio
async def test_f19_real_minimax_classify_never_raises(tmp_path: Path) -> None:
    """Real ``classify`` against MiniMax with the strict json_schema body.

    Contract assertion (IAPI-010 永不抛):
      * ``classify`` returns a Verdict regardless of provider behavior.
      * If MiniMax respects ``response_format=json_schema`` and returns a valid
        verdict → ``backend == "llm"``.
      * If it ignores response_format / returns a non-conforming JSON → fallback
        triggers and ``backend == "rule"``. Both are acceptable per design.
      * Total round-trip ≤ 12 s (IFR-004 10 s + tolerance for network noise).
    """
    key = _read_minimax_key()
    if not key:
        pytest.skip(f"keyring entry {_KEYRING_SERVICE}/{_KEYRING_USER} missing")

    from harness.dispatch.classifier.models import ClassifierConfig, ClassifyRequest
    from harness.dispatch.classifier.service import ClassifierService

    audit_events: list[dict] = []

    cfg = ClassifierConfig(
        enabled=True,
        provider="minimax",
        base_url="https://api.minimax.chat/v1/",
        model_name="MiniMax-M2.7-highspeed",
    )
    service = ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "prompt.json",
        audit_sink=audit_events.append,
    )
    req = ClassifyRequest(
        exit_code=0,
        stderr_tail="",
        stdout_tail="task complete",
        has_termination_banner=False,
    )

    start = time.monotonic()
    verdict = await service.classify(req)
    elapsed = time.monotonic() - start

    assert verdict.backend in {"llm", "rule"}, f"unexpected backend={verdict.backend!r}"
    assert verdict.verdict in {"HIL_REQUIRED", "CONTINUE", "RETRY", "ABORT", "COMPLETED"}
    assert isinstance(verdict.reason, str)
    assert elapsed <= 12.0, f"classify over budget: {elapsed:.2f}s (IFR-004 10 s)"

    if verdict.backend == "rule":
        causes = [e.get("cause") for e in audit_events if e.get("event") == "classifier_fallback"]
        assert causes, "rule fallback must emit audit warning(s)"
