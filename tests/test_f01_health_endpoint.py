"""Unit tests for F01 · /api/health endpoint (feature #1, NFR-007 + IAPI-014 协同).

Covers T19 from design §7 Test Inventory.

[unit] — FastAPI app imported directly, tested via ``httpx.AsyncClient``
with ASGI transport (no socket needed).
"""

from __future__ import annotations


async def test_health_endpoint_returns_loopback_bind_field() -> None:
    import httpx

    from harness.api import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/health")

    assert resp.status_code == 200
    payload = resp.json()
    # Schema per §6.2.2 + §Implementation Summary item 5.
    assert payload["bind"] == "127.0.0.1"
    assert "version" in payload
    # claude_auth structure (ClaudeAuthStatus).
    assert "claude_auth" in payload
    auth = payload["claude_auth"]
    assert set(auth.keys()) >= {"cli_present", "authenticated", "source"}
    # cli_versions has claude + opencode keys (per-§IC, possibly null).
    assert "cli_versions" in payload
    assert set(payload["cli_versions"].keys()) >= {"claude", "opencode"}


async def test_health_endpoint_bind_field_never_reports_wildcard() -> None:
    """Negative guardrail: even under a manipulated env, 'bind' must not leak 0.0.0.0."""
    import httpx

    from harness.api import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/health")

    payload = resp.json()
    assert payload["bind"] != "0.0.0.0"
    # Must not report any LAN-ish prefix either.
    assert not payload["bind"].startswith("192.168.")
    assert not payload["bind"].startswith("10.")
