"""F19 · Bk-Dispatch — REST routes for model rules & classifier prompt.

Covers Test Inventory: T38, T39, T40, T41, T42.
SRS: FR-019 · FR-033 (v1) · IAPI-002 sub-routes.

Layer marker:
  # [unit] — FastAPI TestClient against the in-process ``harness.api:app`` via
  # httpx.ASGITransport; no external HTTP, no real keyring. Data is written to
  # tmp_path via HARNESS_HOME override so tests are hermetic.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest


async def _client(tmp_harness_home: Path):
    """Build an AsyncClient bound to the ASGI app with HARNESS_HOME pinned."""
    from harness.api import app

    tmp_harness_home.mkdir(parents=True, exist_ok=True)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# T38 — FUNC/happy — Traces To: FR-019 · IAPI-002 GET /api/settings/model_rules
# Kills: router not registered (404).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t38_get_model_rules_initially_returns_empty_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    client = await _client(tmp_path / ".harness")
    async with client as c:
        resp = await c.get("/api/settings/model_rules")

    assert resp.status_code == 200, f"route must exist, got {resp.status_code}"
    assert resp.json() == [], "with no rules file, response must be []"


# ---------------------------------------------------------------------------
# T39 — FUNC/happy — Traces To: FR-019 · PUT /api/settings/model_rules
# Kills: PUT not persisting (next GET returns stale []).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t39_put_model_rules_persists_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    payload = [{"skill": "requirements", "tool": "claude", "model": "opus"}]
    client = await _client(tmp_path / ".harness")
    async with client as c:
        put_resp = await c.put("/api/settings/model_rules", json=payload)
        get_resp = await c.get("/api/settings/model_rules")

    assert put_resp.status_code == 200, f"PUT must succeed, got {put_resp.status_code}"
    assert put_resp.json() == payload
    assert get_resp.status_code == 200
    assert get_resp.json() == payload, "GET after PUT must round-trip identical body"


# ---------------------------------------------------------------------------
# T40 — FUNC/error — Traces To: IAPI-002 PUT /api/settings/model_rules validation
# Kills: pydantic validation not wired (bad tool enum accepted).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t40_put_model_rules_rejects_invalid_tool_with_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    bad_payload = [{"skill": "requirements", "tool": "gpt", "model": "opus"}]
    client = await _client(tmp_path / ".harness")
    async with client as c:
        resp = await c.put("/api/settings/model_rules", json=bad_payload)

    # FastAPI surfaces pydantic errors as 422; design maps these to "validation".
    assert resp.status_code in {400, 422}, f"expected validation failure, got {resp.status_code}"
    body = resp.json()
    # Body must carry an identifiable error code — not just a generic 500 trace.
    as_text = str(body).lower()
    assert (
        "tool" in as_text or "validation" in as_text
    ), f"response body must surface the 'tool' validation failure, got {body!r}"


# ---------------------------------------------------------------------------
# T41 — FUNC/happy — Traces To: FR-033 v1 · GET /api/prompts/classifier
# Kills: first GET crashing because prompt file absent.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t41_get_prompts_classifier_returns_default_with_empty_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    client = await _client(tmp_path / ".harness")
    async with client as c:
        resp = await c.get("/api/prompts/classifier")

    assert resp.status_code == 200, f"prompt GET must succeed on first-run, got {resp.status_code}"
    body = resp.json()
    assert (
        isinstance(body.get("current"), str) and body["current"].strip()
    ), "current must be the built-in default prompt (non-empty)"
    assert body.get("history") == [], "history must start empty"


# ---------------------------------------------------------------------------
# T42 — FUNC/happy — Traces To: FR-033 v1 · PUT /api/prompts/classifier
# Kills: append logic missing (history stays empty after PUT).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t42_put_prompts_classifier_appends_history_rev(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    client = await _client(tmp_path / ".harness")
    async with client as c:
        put_resp = await c.put("/api/prompts/classifier", json={"content": "new prompt"})
        get_resp = await c.get("/api/prompts/classifier")

    assert put_resp.status_code == 200
    body = get_resp.json()
    assert body["current"] == "new prompt"
    assert len(body["history"]) == 1, f"history length must be 1, got {body['history']!r}"
    assert body["history"][0]["rev"] == 1
