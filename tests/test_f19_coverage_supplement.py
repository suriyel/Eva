"""F19 · Bk-Dispatch — coverage supplement tests (Quality Gates Round 2).

Supplements the T01-T46 test inventory with **error-path** tests that lift
line + branch coverage above the 90/80% threshold. Every test here targets
miss-line / miss-branch clusters flagged by ``pytest-cov --cov-branch
--cov-report=term-missing`` in Round 1 of the F19 Quality Gates.

SRS trace: FR-019 · FR-020 · FR-021 · FR-022 · FR-023 · IFR-004 (via
``tests/integration/test_f19_real_http.py`` T31 wall-clock assertion).

Layer marker:
  # [unit] — all tests are hermetic: tmp_path for filesystem, ``respx`` for
  # HTTP, ``monkeypatch`` for KeyringGateway. No real network / real
  # HARNESS_HOME touched.

Category breakdown (Rule 1):
  * FUNC/error   — REST error-path (400/422/500) + service fallback audit
  * BNDRY/edge   — empty-file / non-list-root / out-of-enum schema probes
  * SEC          — path traversal / plaintext api_key smuggle defense
  * INTG/http    — ClassifierService.test_connection edge codes

Assertion quality (Rule 2):
  * No ``assert True`` or bare ``is not None`` on primitives.
  * Status-code checks compare to concrete int sets; error-code checks compare
    to the exact string the service contract promises.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx


GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
async def _app_client(home: Path) -> httpx.AsyncClient:
    """Build an AsyncClient bound to the in-process FastAPI app."""
    from harness.api import app

    home.mkdir(parents=True, exist_ok=True)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _valid_envelope(verdict: dict[str, Any]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps(verdict)},
                "finish_reason": "stop",
            }
        ]
    }


# ===========================================================================
# SECTION A — harness.api.prompts (miss lines 45-46, 54-55, 59-60, 68-71)
# ===========================================================================


# ---------------------------------------------------------------------------
# T47 — FUNC/error — Traces To: FR-023 · IAPI-002 PUT /api/prompts/classifier
# Kills: missing 400 branch on malformed JSON body (silent 500 trace leak).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t47_put_prompt_rejects_malformed_json_body_with_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.put(
            "/api/prompts/classifier",
            content=b"{not-json,,,",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 400, f"malformed JSON must surface 400, got {resp.status_code}"
    assert "invalid JSON" in str(
        resp.json().get("detail", "")
    ), f"detail must identify invalid JSON, got {resp.json()!r}"


# ---------------------------------------------------------------------------
# T48 — FUNC/error — Traces To: IAPI-002 PUT /api/prompts/classifier schema
# Kills: extra fields accepted (extra="forbid" regression).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t48_put_prompt_rejects_extra_fields_with_422(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.put(
            "/api/prompts/classifier",
            json={"content": "hi", "unknown_field": 42},
        )

    assert resp.status_code == 422, f"extra field must trigger 422, got {resp.status_code}"
    body = resp.json()
    assert (
        body.get("detail", {}).get("error_code") == "validation"
    ), f"detail.error_code must be 'validation', got {body!r}"


# ---------------------------------------------------------------------------
# T49 — BNDRY/edge — Traces To: §BC content 32 KB cap via REST
# Kills: PUT path bypassing PromptValidationError → 500 leak.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t49_put_prompt_oversized_content_returns_422(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    oversized = "x" * (32 * 1024 + 1)
    async with client as c:
        resp = await c.put("/api/prompts/classifier", json={"content": oversized})

    assert resp.status_code == 422, f"oversized prompt must map to 422, got {resp.status_code}"


# ---------------------------------------------------------------------------
# T50 — FUNC/error — Traces To: IAPI-002 GET /api/prompts/classifier corrupt
# Kills: corrupted on-disk JSON leaking as 500 trace instead of 500 + detail.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t50_get_prompt_corrupt_file_returns_500_with_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = tmp_path / ".harness"
    home.mkdir(parents=True)
    # Prepopulate a corrupt prompt file.
    (home / "classifier_prompt.json").write_text("{ not JSON ---", encoding="utf-8")
    monkeypatch.setenv("HARNESS_HOME", str(home))

    client = await _app_client(home)
    async with client as c:
        resp = await c.get("/api/prompts/classifier")

    assert resp.status_code == 500, f"corrupt JSON must map to 500, got {resp.status_code}"
    detail = str(resp.json().get("detail", ""))
    assert (
        "corrupt" in detail.lower() or "JSON" in detail
    ), f"detail must identify corruption, got {detail!r}"


# ---------------------------------------------------------------------------
# T51 — FUNC/error — Traces To: IAPI-002 PUT /api/prompts/classifier I/O
# Kills: PromptStoreError surfacing as 500 (covers prompts.py line 70-71).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t51_put_prompt_store_io_failure_returns_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.errors import PromptStoreError
    from harness.dispatch.classifier.prompt_store import PromptStore

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    def _boom(self: PromptStore, content: str) -> Any:  # noqa: ARG001
        raise PromptStoreError("simulated disk failure")

    monkeypatch.setattr(PromptStore, "put", _boom, raising=True)

    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.put("/api/prompts/classifier", json={"content": "hello"})

    assert resp.status_code == 500, f"PromptStoreError must map to 500, got {resp.status_code}"
    assert "simulated disk failure" in str(resp.json().get("detail", ""))


# ===========================================================================
# SECTION B — harness.api.settings (miss 47,51,62-63,72-73,76,100-107,112-121,
#             133-134,145-149,155-176)
# ===========================================================================


# ---------------------------------------------------------------------------
# T52 — FUNC/error — Traces To: FR-019 · GET /api/settings/model_rules corrupt
# Kills: ModelRulesCorruptError leaking as 500 trace (covers settings.py 62-63).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t52_get_model_rules_corrupt_file_returns_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = tmp_path / ".harness"
    home.mkdir()
    (home / "model_rules.json").write_text("{ not json -- [broken", encoding="utf-8")
    monkeypatch.setenv("HARNESS_HOME", str(home))

    client = await _app_client(home)
    async with client as c:
        resp = await c.get("/api/settings/model_rules")

    assert resp.status_code == 500, f"corrupt rules must surface 500, got {resp.status_code}"
    detail = str(resp.json().get("detail", ""))
    assert "JSON" in detail or "corrupt" in detail.lower()


# ---------------------------------------------------------------------------
# T53 — FUNC/error — Traces To: PUT /api/settings/model_rules JSON parse
# Kills: malformed JSON body surfacing as 500 (covers settings.py 72-73).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t53_put_model_rules_malformed_body_returns_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.put(
            "/api/settings/model_rules",
            content=b"[[[broken",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 400, f"malformed JSON must map to 400, got {resp.status_code}"
    assert "invalid JSON" in str(resp.json().get("detail", ""))


# ---------------------------------------------------------------------------
# T54 — BNDRY/edge — Traces To: PUT /api/settings/model_rules non-list
# Kills: non-list root silently accepted (covers settings.py 76-79 branch).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t54_put_model_rules_non_list_payload_returns_422(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.put(
            "/api/settings/model_rules",
            json={"skill": "requirements", "tool": "claude", "model": "opus"},
        )

    assert resp.status_code == 422, f"non-list payload must map to 422, got {resp.status_code}"
    body = resp.json()
    detail = body.get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error_code") == "validation", f"missing validation error_code: {body!r}"


# ---------------------------------------------------------------------------
# T55 — FUNC/happy — Traces To: GET /api/settings/classifier default
# Kills: missing built-in GLM default when file absent (covers 112-121).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t55_get_classifier_config_returns_glm_default_when_file_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.get("/api/settings/classifier")

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("enabled") is False, "default must be disabled (opt-in)"
    assert body.get("provider") == "glm", f"default provider must be glm, got {body!r}"
    assert body.get("base_url") == "https://open.bigmodel.cn/api/paas/v4/"
    assert body.get("model_name") == "glm-4-plus"


# ---------------------------------------------------------------------------
# T56 — FUNC/happy — Traces To: GET /api/settings/classifier from disk
# Kills: disk payload ignored in favor of default (covers 100-106 positive).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t56_get_classifier_config_reads_persisted_value_from_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = tmp_path / ".harness"
    home.mkdir()
    (home / "classifier_config.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "provider": "openai",
                "base_url": "https://api.openai.com/v1/",
                "model_name": "gpt-4o-mini",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HARNESS_HOME", str(home))

    client = await _app_client(home)
    async with client as c:
        resp = await c.get("/api/settings/classifier")

    body = resp.json()
    assert body["enabled"] is True
    assert body["provider"] == "openai"
    assert body["model_name"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# T57 — BNDRY/edge — Traces To: GET /api/settings/classifier corrupt
# Kills: corruption bubbling up as 500 instead of graceful default.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t57_get_classifier_config_returns_default_on_corrupt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = tmp_path / ".harness"
    home.mkdir()
    (home / "classifier_config.json").write_text("{{{not json", encoding="utf-8")
    monkeypatch.setenv("HARNESS_HOME", str(home))

    client = await _app_client(home)
    async with client as c:
        resp = await c.get("/api/settings/classifier")

    assert resp.status_code == 200, "corrupt file must not surface as 500 for GET"
    body = resp.json()
    assert body.get("provider") == "glm", f"default fall-back expected, got {body!r}"


# ---------------------------------------------------------------------------
# T58 — FUNC/error — Traces To: PUT /api/settings/classifier JSON parse
# Kills: malformed body surfacing as 500 (covers 133-134).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t58_put_classifier_config_malformed_body_returns_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.put(
            "/api/settings/classifier",
            content=b"{broken",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 400, f"malformed JSON must map to 400, got {resp.status_code}"


# ---------------------------------------------------------------------------
# T59 — FUNC/error — Traces To: PUT /api/settings/classifier schema
# Kills: schema mismatch accepted silently (covers 138-143).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t59_put_classifier_config_schema_mismatch_returns_422(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    # Missing required "base_url" + "model_name" field.
    async with client as c:
        resp = await c.put(
            "/api/settings/classifier",
            json={"enabled": True, "provider": "glm"},
        )

    assert resp.status_code == 422, f"schema mismatch must map to 422, got {resp.status_code}"
    body = resp.json()
    assert body.get("detail", {}).get("error_code") == "validation"


# ---------------------------------------------------------------------------
# T60 — FUNC/happy — Traces To: PUT /api/settings/classifier persist
# Kills: file not written (round-trip failure) — covers 145-149.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t60_put_classifier_config_persists_to_disk_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = tmp_path / ".harness"
    monkeypatch.setenv("HARNESS_HOME", str(home))

    payload = {
        "enabled": True,
        "provider": "minimax",
        "base_url": "https://api.minimax.chat/v1/",
        "model_name": "MiniMax-M2.7-highspeed",
    }
    client = await _app_client(home)
    async with client as c:
        put_resp = await c.put("/api/settings/classifier", json=payload)
        get_resp = await c.get("/api/settings/classifier")

    assert put_resp.status_code == 200
    # File must physically exist on disk (atomic write).
    persisted = home / "classifier_config.json"
    assert persisted.exists(), "PUT must persist classifier_config.json"
    # Round-trip fidelity.
    assert get_resp.json()["provider"] == "minimax"
    assert get_resp.json()["enabled"] is True


# ---------------------------------------------------------------------------
# T61 — FUNC/error — Traces To: POST /api/settings/classifier/test malformed
# Kills: malformed JSON on test endpoint surfacing as 500 (covers 155-158).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t61_post_test_connection_malformed_body_returns_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.post(
            "/api/settings/classifier/test",
            content=b"bad{",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 400, f"malformed JSON must map to 400, got {resp.status_code}"


# ---------------------------------------------------------------------------
# T62 — FUNC/error — Traces To: POST /api/settings/classifier/test schema
# Kills: schema mismatch surfacing as 500 (covers 160-166).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t62_post_test_connection_missing_fields_returns_422(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.post(
            "/api/settings/classifier/test",
            json={"provider": "glm"},  # missing base_url & model_name
        )

    assert resp.status_code == 422, f"schema mismatch must map to 422, got {resp.status_code}"
    assert resp.json().get("detail", {}).get("error_code") == "validation"


# ---------------------------------------------------------------------------
# T63 — SEC/ssrf — Traces To: POST /api/settings/classifier/test SSRF
# Kills: /test endpoint bypassing SSRF guard (covers 168-176 happy-path probe).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t63_post_test_connection_ssrf_blocked_for_internal_ip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    monkeypatch.setattr(
        KeyringGateway,
        "get_secret",
        lambda self, service, user: "sk-t",  # noqa: ARG005
        raising=True,
    )

    client = await _app_client(tmp_path / ".harness")
    async with client as c:
        resp = await c.post(
            "/api/settings/classifier/test",
            json={
                "provider": "custom",
                "base_url": "http://169.254.169.254/v1",
                "model_name": "metadata-attack",
            },
        )

    assert resp.status_code == 200, "endpoint funnels SSRF into the result body"
    body = resp.json()
    assert body["ok"] is False
    assert body["error_code"] == "ssrf_blocked", f"SSRF guard missing; got {body!r}"


# ===========================================================================
# SECTION C — harness.dispatch.classifier.service (miss 79-81,95-96,105-114,
#             125-134,153-154,172,190-191,206-214)
# ===========================================================================


# ---------------------------------------------------------------------------
# T64 — FUNC/error — Traces To: §IC classify · preset resolve error
# Kills: preset KeyError escaping as crash (covers service.py 105-114).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t64_classify_preset_resolve_error_audits_and_falls_back_to_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.models import ClassifierConfig, ClassifyRequest
    from harness.dispatch.classifier.service import ClassifierService

    events: list[dict[str, Any]] = []
    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    service = ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "p.json",
        audit_sink=events.append,
    )

    # Force _resolve_preset to raise.
    def _boom(self, provider, base_url, model_name):  # noqa: ARG001
        raise RuntimeError("synthetic preset failure")

    monkeypatch.setattr(ClassifierService, "_resolve_preset", _boom, raising=True)

    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)
    verdict = await service.classify(req)

    assert verdict.backend == "rule", "preset error must fall back to rule backend"
    fallback_events = [e for e in events if e.get("event") == "classifier_fallback"]
    assert fallback_events, "preset failure must emit classifier_fallback audit"
    assert (
        fallback_events[0].get("cause") == "preset_resolve_error"
    ), f"cause must be preset_resolve_error, got {fallback_events[0]!r}"


# ---------------------------------------------------------------------------
# T65 — FUNC/error — Traces To: §IC classify never-raise contract
# Kills: unexpected exception in decorator.invoke leaking (covers 125-134).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t65_classify_catches_unexpected_decorator_exception_and_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.fallback import FallbackDecorator
    from harness.dispatch.classifier.models import ClassifierConfig, ClassifyRequest
    from harness.dispatch.classifier.service import ClassifierService

    monkeypatch.setattr(
        KeyringGateway,
        "get_secret",
        lambda self, service, user: "sk-t",  # noqa: ARG005
        raising=True,
    )

    async def _boom_invoke(self, req, prompt):  # noqa: ARG001
        raise MemoryError("OOM during classification")

    monkeypatch.setattr(FallbackDecorator, "invoke", _boom_invoke, raising=True)

    events: list[dict[str, Any]] = []
    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    service = ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "p.json",
        audit_sink=events.append,
    )
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    verdict = await service.classify(req)

    assert verdict.backend == "rule"
    causes = [e.get("cause") for e in events if e.get("event") == "classifier_fallback"]
    assert "unexpected_error" in causes, f"unexpected_error must be audited, got {causes!r}"


# ---------------------------------------------------------------------------
# T66 — BNDRY/edge — Traces To: §IC classify prompt corruption tolerance
# Kills: prompt store corruption crashing classify (covers 95-96).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t66_classify_tolerates_prompt_store_corruption_and_uses_default(
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

    # Write a corrupted prompt file at the store location.
    corrupt = tmp_path / "p.json"
    corrupt.write_text("{not-json", encoding="utf-8")

    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    service = ClassifierService(
        config=cfg,
        prompt_store_path=corrupt,
    )
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock(assert_all_called=True) as mock:
        mock.post(GLM_URL).respond(
            200,
            json=_valid_envelope(
                {
                    "verdict": "COMPLETED",
                    "reason": "ok",
                    "anomaly": None,
                    "hil_source": None,
                }
            ),
        )
        verdict = await service.classify(req)

    # Corrupt prompt file must NOT crash — LlmBackend still invoked.
    assert verdict.verdict == "COMPLETED"
    assert verdict.backend == "llm"


# ---------------------------------------------------------------------------
# T67 — INTG/http — Traces To: §IC test_connection timeout branch
# Kills: timeout mis-classified (covers service.py 171-176).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t67_test_connection_timeout_returns_timeout_error_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import (
        ClassifierConfig,
        TestConnectionRequest,
    )
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
    service = ClassifierService(config=cfg, prompt_store_path=tmp_path / "p.json")
    req = TestConnectionRequest(
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    with respx.mock() as mock:
        mock.post(GLM_URL).mock(side_effect=httpx.TimeoutException("simulated timeout"))
        result = await service.test_connection(req)

    assert result.ok is False
    assert result.error_code == "timeout", f"must map to 'timeout', got {result.error_code!r}"


# ---------------------------------------------------------------------------
# T68 — INTG/http — Traces To: §IC test_connection generic HTTPError
# Kills: HTTPError mis-classified (covers service.py 190-195).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t68_test_connection_generic_httperror_returns_connection_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import (
        ClassifierConfig,
        TestConnectionRequest,
    )
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
    service = ClassifierService(config=cfg, prompt_store_path=tmp_path / "p.json")
    req = TestConnectionRequest(
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    # ProtocolError is an httpx.HTTPError subclass but neither Timeout nor Connect.
    with respx.mock() as mock:
        mock.post(GLM_URL).mock(side_effect=httpx.ProtocolError("bad protocol"))
        result = await service.test_connection(req)

    assert result.ok is False
    assert (
        result.error_code == "connection_refused"
    ), f"generic HTTPError must map to connection_refused, got {result.error_code!r}"


# ---------------------------------------------------------------------------
# T69 — INTG/http — Traces To: §IC test_connection >=400 branch
# Kills: non-401 4xx mis-classified (covers service.py 206-212).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t69_test_connection_5xx_returns_connection_refused_with_latency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import (
        ClassifierConfig,
        TestConnectionRequest,
    )
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
    service = ClassifierService(config=cfg, prompt_store_path=tmp_path / "p.json")
    req = TestConnectionRequest(
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    with respx.mock() as mock:
        mock.post(GLM_URL).respond(503, text="Service Unavailable")
        result = await service.test_connection(req)

    assert result.ok is False
    assert result.error_code == "connection_refused"
    assert (
        result.latency_ms is not None and result.latency_ms >= 0
    ), "latency_ms must be populated for non-exception responses"
    assert "HTTP 503" in result.message


# ---------------------------------------------------------------------------
# T70 — FUNC/happy — Traces To: §IC test_connection OK branch
# Kills: happy 200 ignored (covers service.py 214-218).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t70_test_connection_200_returns_ok_true_with_latency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import (
        ClassifierConfig,
        TestConnectionRequest,
    )
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
    service = ClassifierService(config=cfg, prompt_store_path=tmp_path / "p.json")
    req = TestConnectionRequest(
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    with respx.mock() as mock:
        mock.post(GLM_URL).respond(200, json={"choices": []})
        result = await service.test_connection(req)

    assert result.ok is True
    assert result.error_code is None
    assert result.latency_ms is not None and result.latency_ms >= 0
    assert result.message == "OK"


# ---------------------------------------------------------------------------
# T71 — BNDRY/edge — Traces To: §IC test_connection keyring failure tolerance
# Kills: keyring exception crashing (covers service.py 153-154).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t71_test_connection_continues_when_keyring_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import (
        ClassifierConfig,
        TestConnectionRequest,
    )
    from harness.dispatch.classifier.service import ClassifierService

    def _boom(self, service, user):  # noqa: ARG001
        raise RuntimeError("keyring down")

    monkeypatch.setattr(KeyringGateway, "get_secret", _boom, raising=True)

    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    service = ClassifierService(config=cfg, prompt_store_path=tmp_path / "p.json")
    req = TestConnectionRequest(
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )

    with respx.mock() as mock:
        route = mock.post(GLM_URL).respond(200, json={"choices": []})
        result = await service.test_connection(req)

    # Keyring exception must NOT crash; request proceeds without Authorization.
    assert result.ok is True
    assert route.called
    sent = route.calls.last.request
    assert "authorization" not in {
        k.lower() for k in sent.headers.keys()
    }, "no Authorization header expected when keyring raised"


# ===========================================================================
# SECTION D — harness.dispatch.classifier.fallback (miss 56-67)
# ===========================================================================


# ---------------------------------------------------------------------------
# T72 — FUNC/error — Traces To: §IC FallbackDecorator ClassifierProtocolError
# Kills: protocol error bucket missing (covers fallback.py 56-65).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t72_fallback_decorator_audits_protocol_error_with_cause(tmp_path: Path):
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.fallback import FallbackDecorator
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    class _StubLlm:
        async def invoke(self, req, prompt):  # noqa: ARG002
            raise ClassifierProtocolError("bad schema", cause="schema_mismatch")

    events: list[dict[str, Any]] = []
    decorator = FallbackDecorator(
        primary=_StubLlm(),  # type: ignore[arg-type]
        fallback=RuleBackend(),
        audit_sink=events.append,
    )
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    verdict = await decorator.invoke(req, prompt="p")

    assert verdict.backend == "rule"
    assert len(events) == 1
    assert events[0]["cause"] == "schema_mismatch", f"cause propagation broken: {events[0]!r}"
    assert events[0]["exc_class"] == "ClassifierProtocolError"


# ---------------------------------------------------------------------------
# T73 — FUNC/error — Traces To: §IC FallbackDecorator catch-all
# Kills: unexpected error leaking (covers fallback.py 66-74).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t73_fallback_decorator_catches_unexpected_exception_as_fallback(
    tmp_path: Path,
):
    from harness.dispatch.classifier.fallback import FallbackDecorator
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    class _StubLlm:
        async def invoke(self, req, prompt):  # noqa: ARG002
            raise ZeroDivisionError("unexpected")

    events: list[dict[str, Any]] = []
    decorator = FallbackDecorator(
        primary=_StubLlm(),  # type: ignore[arg-type]
        fallback=RuleBackend(),
        audit_sink=events.append,
    )
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    verdict = await decorator.invoke(req, prompt="p")

    assert verdict.backend == "rule"
    assert events[0]["cause"] == "unexpected_error"
    assert events[0]["exc_class"] == "ZeroDivisionError"


# ---------------------------------------------------------------------------
# T74 — FUNC/happy — Traces To: §IC FallbackDecorator pass-through
# Kills: decorator eating a valid LLM verdict (covers fallback.py 44-45).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t74_fallback_decorator_passes_through_successful_llm_verdict():
    from harness.dispatch.classifier.fallback import FallbackDecorator
    from harness.dispatch.classifier.models import ClassifyRequest, Verdict
    from harness.dispatch.classifier.rule_backend import RuleBackend

    class _StubLlm:
        async def invoke(self, req, prompt):  # noqa: ARG002
            return Verdict(
                verdict="CONTINUE",
                reason="ongoing",
                anomaly=None,
                hil_source=None,
                backend="llm",
            )

    events: list[dict[str, Any]] = []
    decorator = FallbackDecorator(
        primary=_StubLlm(),  # type: ignore[arg-type]
        fallback=RuleBackend(),
        audit_sink=events.append,
    )
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    verdict = await decorator.invoke(req, prompt="p")

    assert verdict.backend == "llm"
    assert verdict.verdict == "CONTINUE"
    assert events == [], "no audit events expected on happy path"


# ===========================================================================
# SECTION E — harness.dispatch.classifier.llm_backend (miss 131-134,142-143,
#             149-150,162,172,178)
# ===========================================================================


def _build_backend(monkeypatch: pytest.MonkeyPatch):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.llm_backend import LlmBackend
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    monkeypatch.setattr(
        KeyringGateway,
        "get_secret",
        lambda self, service, user: "sk-x",  # noqa: ARG005
        raising=True,
    )
    return LlmBackend(preset=ProviderPresets().resolve("glm"), keyring=KeyringGateway())


# ---------------------------------------------------------------------------
# T75 — FUNC/error — Traces To: §IC LlmBackend.invoke ConnectError
# Kills: ConnectError not mapped to ClassifierHttpError (llm_backend.py 131-132).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t75_llm_backend_raises_http_error_on_connect_error(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierHttpError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock() as mock:
        mock.post(GLM_URL).mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(ClassifierHttpError) as exc_info:
            await backend.invoke(req, prompt="p")

    assert exc_info.value.cause == "connection_error"


# ---------------------------------------------------------------------------
# T76 — FUNC/error — Traces To: §IC LlmBackend.invoke generic HTTPError
# Kills: other HTTPErrors leaking untyped (llm_backend.py 133-134).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t76_llm_backend_raises_http_error_on_generic_http_error(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierHttpError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock() as mock:
        mock.post(GLM_URL).mock(side_effect=httpx.ProtocolError("bad wire"))
        with pytest.raises(ClassifierHttpError) as exc_info:
            await backend.invoke(req, prompt="p")

    assert exc_info.value.cause == "http_error"


# ---------------------------------------------------------------------------
# T77 — FUNC/error — Traces To: §IC LlmBackend.invoke non-JSON envelope
# Kills: envelope JSON parse error swallowed (llm_backend.py 142-143).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t77_llm_backend_raises_protocol_error_on_non_json_envelope(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock() as mock:
        mock.post(GLM_URL).respond(200, text="not-json at all")
        with pytest.raises(ClassifierProtocolError) as exc_info:
            await backend.invoke(req, prompt="p")

    assert exc_info.value.cause == "json_parse_error"


# ---------------------------------------------------------------------------
# T78 — FUNC/error — Traces To: §IC LlmBackend.invoke missing choices
# Kills: KeyError on choices[0] bubbling up (llm_backend.py 149-150).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t78_llm_backend_raises_protocol_error_on_missing_choices(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock() as mock:
        # Valid JSON but no choices array.
        mock.post(GLM_URL).respond(200, json={"id": "x", "object": "chat.completion"})
        with pytest.raises(ClassifierProtocolError) as exc_info:
            await backend.invoke(req, prompt="p")

    assert exc_info.value.cause == "schema_mismatch"


# ---------------------------------------------------------------------------
# T79 — FUNC/error — Traces To: §IC LlmBackend.invoke non-dict assistant JSON
# Kills: array-as-verdict slipping past (llm_backend.py 161-162).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t79_llm_backend_raises_protocol_error_when_assistant_is_array(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock() as mock:
        mock.post(GLM_URL).respond(
            200,
            json=_valid_envelope({"bogus": "shape"}) | {},  # type: ignore[operator]
        )
        # Re-shape the envelope so the assistant payload is an array.
        mock.reset()
        mock.post(GLM_URL).respond(
            200,
            json={
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "[1,2,3]"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )
        with pytest.raises(ClassifierProtocolError) as exc_info:
            await backend.invoke(req, prompt="p")

    # Wave 3 (§3a): tolerant extractor scans for a balanced JSON OBJECT.
    # A top-level array has no balanced ``{...}`` match → cause is
    # ``json_parse_error`` (extractor miss), not ``schema_mismatch``.
    assert exc_info.value.cause == "json_parse_error"


# ---------------------------------------------------------------------------
# T80 — FUNC/error — Traces To: §IC LlmBackend.invoke anomaly out-of-enum
# Kills: anomaly drift slipping past (llm_backend.py 171-173).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t80_llm_backend_raises_protocol_error_on_anomaly_out_of_enum(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock() as mock:
        mock.post(GLM_URL).respond(
            200,
            json=_valid_envelope(
                {
                    "verdict": "CONTINUE",
                    "reason": "x",
                    "anomaly": "ALIEN_ANOMALY",  # not in AnomalyLiteral
                    "hil_source": None,
                }
            ),
        )
        with pytest.raises(ClassifierProtocolError) as exc_info:
            await backend.invoke(req, prompt="p")

    assert exc_info.value.cause == "schema_mismatch"


# ---------------------------------------------------------------------------
# T81 — FUNC/error — Traces To: §IC LlmBackend.invoke reason validation
# Kills: empty/non-string reason accepted (llm_backend.py 176-180).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t81_llm_backend_raises_protocol_error_on_empty_reason(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.dispatch.classifier.errors import ClassifierProtocolError
    from harness.dispatch.classifier.models import ClassifyRequest

    backend = _build_backend(monkeypatch)
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with respx.mock() as mock:
        mock.post(GLM_URL).respond(
            200,
            json=_valid_envelope(
                {
                    "verdict": "CONTINUE",
                    "reason": "",  # empty string
                    "anomaly": None,
                    "hil_source": None,
                }
            ),
        )
        with pytest.raises(ClassifierProtocolError) as exc_info:
            await backend.invoke(req, prompt="p")

    assert exc_info.value.cause == "schema_mismatch"


# ---------------------------------------------------------------------------
# T82 — FUNC/error — Traces To: §IC LlmBackend.invoke keyring outage
# Kills: keyring exception leaking as arbitrary error (llm_backend.py 115-116).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t82_llm_backend_maps_keyring_failure_to_http_error_keyring_cause(
    monkeypatch: pytest.MonkeyPatch,
):
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.errors import ClassifierHttpError
    from harness.dispatch.classifier.llm_backend import LlmBackend
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    def _boom(self, service, user):  # noqa: ARG001
        raise RuntimeError("keyring daemon dead")

    monkeypatch.setattr(KeyringGateway, "get_secret", _boom, raising=True)
    backend = LlmBackend(preset=ProviderPresets().resolve("glm"), keyring=KeyringGateway())
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)

    with pytest.raises(ClassifierHttpError) as exc_info:
        await backend.invoke(req, prompt="p")

    assert exc_info.value.cause == "keyring_error"


# ===========================================================================
# SECTION F — harness.dispatch.classifier.provider_presets (miss 58, 79, 85,
#             94->108, 108->exit)
# ===========================================================================


# ---------------------------------------------------------------------------
# T83 — SEC/ssrf — Traces To: FR-021 AC-3 validate_base_url missing scheme
# Kills: empty scheme/host accepted (provider_presets.py 78-79).
# ---------------------------------------------------------------------------
def test_t83_validate_base_url_rejects_scheme_missing():
    from harness.dispatch.classifier.errors import SsrfBlockedError
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    with pytest.raises(SsrfBlockedError) as exc_info:
        ProviderPresets().validate_base_url("//open.bigmodel.cn/v1")
    assert "scheme" in str(exc_info.value).lower() or "host" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# T84 — SEC/ssrf — Traces To: FR-021 AC-3 whitelist + http rejected
# Kills: HTTP scheme on whitelist domain accepted (provider_presets.py 84-86).
# ---------------------------------------------------------------------------
def test_t84_validate_base_url_rejects_http_scheme_for_whitelist_domain():
    from harness.dispatch.classifier.errors import SsrfBlockedError
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    with pytest.raises(SsrfBlockedError):
        ProviderPresets().validate_base_url("http://api.openai.com/v1/")


# ---------------------------------------------------------------------------
# T85 — SEC/ssrf — Traces To: FR-021 AC-3 subdomain allowed
# Kills: subdomain pattern broken (provider_presets.py 82-83 positive branch).
# ---------------------------------------------------------------------------
def test_t85_validate_base_url_accepts_whitelist_subdomain_over_https():
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    # Must not raise.
    ProviderPresets().validate_base_url("https://edge.open.bigmodel.cn/api/paas/v4/")


# ---------------------------------------------------------------------------
# T86 — SEC/ssrf — Traces To: FR-021 AC-3 custom host https enforcement
# Kills: HTTP accepted for custom DNS names (provider_presets.py 108-111).
# ---------------------------------------------------------------------------
def test_t86_validate_base_url_rejects_http_scheme_for_custom_dns_host():
    from harness.dispatch.classifier.errors import SsrfBlockedError
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    with pytest.raises(SsrfBlockedError) as exc_info:
        ProviderPresets().validate_base_url("http://llm.corp.example.com/v1/")
    assert "https" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# T87 — FUNC/happy — Traces To: §IC ProviderPresets.list
# Kills: preset list missing provider (provider_presets.py 57-58).
# ---------------------------------------------------------------------------
def test_t87_list_returns_all_four_providers_including_custom():
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    presets = ProviderPresets().list()
    names = {p.name for p in presets}
    assert names == {"glm", "minimax", "openai", "custom"}, f"missing provider: {names!r}"


# ===========================================================================
# SECTION G — harness.dispatch.model.rules_store (miss 38, 50, 58, 64-65,
#             108-109, 113-114)
# ===========================================================================


# ---------------------------------------------------------------------------
# T88 — BNDRY/edge — Traces To: §IC ModelRulesStore.load absent file
# Kills: missing file raising instead of returning [] (rules_store.py 41-43).
# ---------------------------------------------------------------------------
def test_t88_rules_store_load_missing_file_returns_empty_list(tmp_path: Path):
    from harness.dispatch.model.rules_store import ModelRulesStore

    store = ModelRulesStore(path=tmp_path / "does-not-exist.json")
    rules = store.load()
    assert rules == [], f"missing file must return [], got {rules!r}"


# ---------------------------------------------------------------------------
# T89 — BNDRY/edge — Traces To: §IC ModelRulesStore.load empty file
# Kills: whitespace-only file raising corrupt error (rules_store.py 49-50).
# ---------------------------------------------------------------------------
def test_t89_rules_store_load_whitespace_file_returns_empty_list(tmp_path: Path):
    from harness.dispatch.model.rules_store import ModelRulesStore

    path = tmp_path / "model_rules.json"
    path.write_text("   \n\t\n", encoding="utf-8")
    store = ModelRulesStore(path=path)

    rules = store.load()
    assert rules == [], f"whitespace-only file must return [], got {rules!r}"


# ---------------------------------------------------------------------------
# T90 — FUNC/error — Traces To: §IC ModelRulesStore.load non-list root
# Kills: dict root silently accepted (rules_store.py 57-60).
# ---------------------------------------------------------------------------
def test_t90_rules_store_load_dict_root_raises_corrupt_error(tmp_path: Path):
    from harness.dispatch.model.rules_store import ModelRulesCorruptError, ModelRulesStore

    path = tmp_path / "model_rules.json"
    path.write_text('{"skill": "x"}', encoding="utf-8")
    store = ModelRulesStore(path=path)

    with pytest.raises(ModelRulesCorruptError) as exc_info:
        store.load()
    assert "list" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# T91 — FUNC/error — Traces To: §IC ModelRulesStore.load schema mismatch
# Kills: schema-invalid rule silently loaded (rules_store.py 62-67).
# ---------------------------------------------------------------------------
def test_t91_rules_store_load_schema_mismatch_raises_corrupt_error(tmp_path: Path):
    from harness.dispatch.model.rules_store import ModelRulesCorruptError, ModelRulesStore

    path = tmp_path / "model_rules.json"
    # Invalid tool value ("gpt" not in enum).
    path.write_text(
        json.dumps([{"skill": "requirements", "tool": "gpt", "model": "opus"}]),
        encoding="utf-8",
    )
    store = ModelRulesStore(path=path)

    with pytest.raises(ModelRulesCorruptError):
        store.load()


# ---------------------------------------------------------------------------
# T92 — FUNC/happy — Traces To: §IC ModelRulesStore.save list
# Kills: multi-rule save dropping entries (rules_store.py 70-102 happy).
# ---------------------------------------------------------------------------
def test_t92_rules_store_save_preserves_all_rules_in_order(tmp_path: Path):
    from harness.dispatch.model.models import ModelRule
    from harness.dispatch.model.rules_store import ModelRulesStore

    rules_file = tmp_path / "model_rules.json"
    store = ModelRulesStore(path=rules_file)
    rules = [
        ModelRule(skill="requirements", tool="claude", model="opus"),
        ModelRule(skill=None, tool="claude", model="sonnet"),
        ModelRule(skill="work", tool="opencode", model="haiku"),
    ]
    store.save(rules)

    on_disk = json.loads(rules_file.read_text(encoding="utf-8"))
    assert len(on_disk) == 3
    assert on_disk[0]["skill"] == "requirements"
    assert on_disk[2]["tool"] == "opencode"


# ---------------------------------------------------------------------------
# T93 — FUNC/happy — Traces To: §IC ModelRulesStore.path accessor
# Kills: .path property breakage (rules_store.py 37-38).
# ---------------------------------------------------------------------------
def test_t93_rules_store_path_property_returns_constructor_path(tmp_path: Path):
    from harness.dispatch.model.rules_store import ModelRulesStore

    target = tmp_path / "sub" / "model_rules.json"
    store = ModelRulesStore(path=target)
    assert store.path == target, f"path property must return constructor input, got {store.path!r}"


# ===========================================================================
# SECTION H — harness.dispatch.classifier.prompt_store (miss 48, 76, 80-81,
#             97-98, 131-132, 152-153)
# ===========================================================================


# ---------------------------------------------------------------------------
# T94 — BNDRY/edge — Traces To: §IC PromptStore.get empty file
# Kills: whitespace-only file crashing (prompt_store.py 75-76).
# ---------------------------------------------------------------------------
def test_t94_prompt_store_get_whitespace_file_returns_default_prompt(tmp_path: Path):
    from harness.dispatch.classifier.prompt_store import PromptStore

    path = tmp_path / "prompt.json"
    path.write_text("\n\n  ", encoding="utf-8")
    store = PromptStore(path=path)

    prompt = store.get()
    assert (
        isinstance(prompt.current, str) and prompt.current.strip()
    ), "whitespace file must fall back to built-in default"
    assert prompt.history == []


# ---------------------------------------------------------------------------
# T95 — FUNC/error — Traces To: §IC PromptStore.get corrupt JSON
# Kills: corrupt JSON swallowed (prompt_store.py 80-81).
# ---------------------------------------------------------------------------
def test_t95_prompt_store_get_corrupt_json_raises_prompt_store_corrupt_error(
    tmp_path: Path,
):
    from harness.dispatch.classifier.errors import PromptStoreCorruptError
    from harness.dispatch.classifier.prompt_store import PromptStore

    path = tmp_path / "prompt.json"
    path.write_text("{ not json ---", encoding="utf-8")
    store = PromptStore(path=path)

    with pytest.raises(PromptStoreCorruptError):
        store.get()


# ---------------------------------------------------------------------------
# T96 — BNDRY/edge — Traces To: §IC PromptStore.put corruption recovery
# Kills: corruption on existing file preventing put() overwrite (97-98).
# ---------------------------------------------------------------------------
def test_t96_prompt_store_put_overwrites_corrupt_existing_file(tmp_path: Path):
    from harness.dispatch.classifier.prompt_store import PromptStore

    path = tmp_path / "prompt.json"
    path.write_text("{ broken", encoding="utf-8")
    store = PromptStore(path=path)

    prompt = store.put("fresh prompt v1")
    assert prompt.current == "fresh prompt v1"
    # History starts from rev=1 (corruption treated as empty-history baseline).
    assert len(prompt.history) == 1
    assert prompt.history[0].rev == 1


# ---------------------------------------------------------------------------
# T97 — FUNC/error — Traces To: §IC PromptStore.put parent dir failure
# Kills: mkdir failure leaking as OSError (prompt_store.py 129-132).
# ---------------------------------------------------------------------------
def test_t97_prompt_store_put_parent_mkdir_failure_raises_prompt_store_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.errors import PromptStoreError
    from harness.dispatch.classifier.prompt_store import PromptStore

    path = tmp_path / "new-dir" / "prompt.json"
    store = PromptStore(path=path)

    # Patch Path.mkdir to raise OSError.
    original_mkdir = Path.mkdir

    def _boom(self, *args, **kwargs):  # noqa: ARG001
        if self == path.parent:
            raise OSError("simulated mkdir denial")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _boom, raising=True)

    with pytest.raises(PromptStoreError) as exc_info:
        store.put("content")
    assert "simulated mkdir denial" in str(exc_info.value)


# ---------------------------------------------------------------------------
# T98 — FUNC/happy — Traces To: §IC PromptStore.path property
# Kills: .path accessor regression (prompt_store.py 47-48).
# ---------------------------------------------------------------------------
def test_t98_prompt_store_path_property_matches_constructor(tmp_path: Path):
    from harness.dispatch.classifier.prompt_store import PromptStore

    target = tmp_path / "a" / "b" / "prompt.json"
    store = PromptStore(path=target)
    assert store.path == target
