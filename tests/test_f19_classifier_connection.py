"""F19 · Bk-Dispatch — ClassifierService.test_connection unit tests (respx).

Covers Test Inventory: T32, T33, T34, T45.
SRS: ATS INT-025 · §IC ClassifierService.test_connection · FR-021 AC-3 (SSRF).

Layer marker:
  # [unit] — httpx mocked via respx. Real HTTP is exercised by T31 in
  # tests/integration/test_f19_real_http.py.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx


GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def _make_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import ClassifierConfig
    from harness.dispatch.classifier.service import ClassifierService

    monkeypatch.setattr(
        KeyringGateway,
        "get_secret",
        lambda self, service, user: "sk-t",  # noqa: ARG005
        raising=True,
    )

    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    return ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "prompt.json",
    )


# ---------------------------------------------------------------------------
# T32 — INTG/http — Traces To: ATS INT-025 · §IC test_connection
# Kills: 401 being raised to UI instead of funneled into TestConnectionResult.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t32_test_connection_401_returns_ok_false_with_error_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.models import TestConnectionRequest

    service = _make_service(tmp_path, monkeypatch)
    req = TestConnectionRequest(
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    with respx.mock() as mock:
        mock.post(GLM_URL).respond(401, json={"error": "unauthorized"})
        # Must NOT raise.
        result = await service.test_connection(req)

    assert result.ok is False
    assert result.error_code == "401"
    assert result.message  # human-readable message populated


# ---------------------------------------------------------------------------
# T33 — INTG/http — Traces To: ATS INT-025
# Kills: ConnectError mis-classified as generic 500.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t33_test_connection_connect_refused_returns_connection_refused_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.models import TestConnectionRequest

    service = _make_service(tmp_path, monkeypatch)
    req = TestConnectionRequest(
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    with respx.mock() as mock:
        mock.post(GLM_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        result = await service.test_connection(req)

    assert result.ok is False
    assert result.error_code == "connection_refused"


# ---------------------------------------------------------------------------
# T34 — INTG/http — Traces To: ATS INT-025
# Kills: DNS failure bucketed into "500" generic bag.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t34_test_connection_dns_failure_returns_dns_failure_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.models import TestConnectionRequest

    service = _make_service(tmp_path, monkeypatch)
    req = TestConnectionRequest(
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    with respx.mock() as mock:
        # The service must be able to distinguish DNS from generic connect —
        # the design (§IC) uses the "getaddrinfo failed" substring.
        mock.post(GLM_URL).mock(side_effect=httpx.ConnectError("getaddrinfo failed"))
        result = await service.test_connection(req)

    assert result.ok is False
    assert (
        result.error_code == "dns_failure"
    ), f"DNS failure must be its own code, got {result.error_code!r}"


# ---------------------------------------------------------------------------
# T45 — FUNC/error / SEC/ssrf — Traces To: §IC test_connection SSRF
# Kills: test-connection code path bypassing SSRF validation (re-introducing
#        the metadata-service attack vector via "just testing" button).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t45_test_connection_rejects_loopback_custom_base_url_with_ssrf_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.models import TestConnectionRequest

    service = _make_service(tmp_path, monkeypatch)
    req = TestConnectionRequest(
        provider="custom",
        base_url="http://127.0.0.1:8080/v1",  # loopback via HTTP for a custom provider
        model_name="local-llm",
    )

    # Must NOT actually hit the URL — should short-circuit to ssrf_blocked.
    # [TEST-FIX] respx default assert_all_called=True would flag the unused
    # route. Explicitly disable to honor the intent: "NOT called".
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post("http://127.0.0.1:8080/v1/chat/completions")
        result = await service.test_connection(req)

    assert result.ok is False
    assert (
        result.error_code == "ssrf_blocked"
    ), f"loopback + custom provider must be blocked; got {result.error_code!r}"
    assert not route.called, "SSRF-blocked path must short-circuit before hitting the network"
