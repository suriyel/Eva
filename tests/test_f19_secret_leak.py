"""F19 · Bk-Dispatch — Secret-leak defense on the NEW /api/settings/classifier PUT path.

Covers Test Inventory: T26.
SRS: FR-021 AC-1 · NFR-008 · §IS §4 integration (new REST path must not
accept plaintext api_key; it must funnel through ApiKeyRef indirection).

Layer marker:
  # [unit] — FastAPI TestClient against the in-process app; the assertion is
  # that the NEW F19 code refuses plaintext `api_key` fields in the
  # ClassifierConfig PUT body. This kills a real bypass: a naive
  # implementation that accepts `{"api_key":"sk-…"}` and writes it into
  # config.json circumvents the keyring entirely (NFR-008 violation).
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest


# ---------------------------------------------------------------------------
# T26 — SEC/secret-leak — Traces To: FR-021 AC-1 · NFR-008 · IAPI-002
# Kills: PUT /api/settings/classifier accepting a plaintext api_key payload.
# Drives NEW F19 code: the classifier settings route + pydantic
# ``ClassifierConfig`` schema which must only carry ``api_key_ref`` (indirect),
# never ``api_key`` (direct).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t26_put_classifier_settings_refuses_plaintext_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.api import app

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    # Attacker-style payload: try to slip an ``api_key`` field straight into
    # the persisted config. The NEW F19 code must reject this — either via
    # pydantic ``extra="forbid"`` (422 / 400) or via a dedicated 400 with a
    # ``secret_leak``-style error code. What it MUST NOT do is return 200 and
    # persist the plaintext key.
    bad_payload = {
        "enabled": True,
        "provider": "glm",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model_name": "glm-4-plus",
        "api_key": "sk-ABCDEF0123456789abcdef0123456789ZZZZZZZ",
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        # Step 1 — prove the route EXISTS (NOT 404/405). A 404/405 here means
        # the F19 classifier settings endpoint has not been wired at all, which
        # is a distinct defect from "wired but accepts plaintext".
        resp = await c.put("/api/settings/classifier", json=bad_payload)
        assert resp.status_code not in {404, 405}, (
            f"PUT /api/settings/classifier must be a registered route; "
            f"got {resp.status_code} — F19 router not mounted."
        )

    # Step 2 — the route must REJECT the plaintext `api_key` field, precisely
    # because ClassifierConfig pydantic schema should forbid it
    # (model_config extra='forbid' + no api_key field declared). Expected
    # 400 / 422 with a validation-style body. A 200 here means the route
    # accepted plaintext creds, which is the NFR-008 violation this kills.
    assert resp.status_code in {400, 422}, (
        f"PUT with plaintext `api_key` must be rejected by pydantic "
        f"validation (400/422); got {resp.status_code}. A 200 here means "
        "the NEW F19 route accepted plaintext credentials (NFR-008 violation)."
    )

    # Step 3 — defense-in-depth: even if the route returned a non-200 status,
    # config.json must NOT carry the plaintext token (nothing should have been
    # persisted).
    config_json = tmp_path / ".harness" / "config.json"
    if config_json.exists():
        body = config_json.read_text(encoding="utf-8")
        assert "sk-ABCDEF" not in body, (
            "plaintext api_key leaked into config.json — F19 route bypassed "
            "the keyring indirection"
        )
