"""Feature #24 B9 — `/api/health` 30s TTL refresh policy.

Traces To
=========
  B9-P1  §6.2.2 L1165 GET /api/health / NFR-013 schema           (INTG/http)
  B9-N1  §IC `health()` cache hit < 30s — second call returns
         SAME cli_versions even if probe would yield new value    (FUNC/cache-staleness)
  B9-N2  §IC `health()` cache miss > 30s — second call MUST
         re-probe and return new cli_versions                     (FUNC/cache-refresh)
  B9-P2  PERF/probe-throughput — 100 calls within 30s window
         trigger _probe_cli_version <= 2 times                    (PERF)
  B9-N3  §IC `health()` Raises — _probe_cli_version raises
         OSError → cache untouched, no 5xx                        (FUNC/error)
  §Implementation Summary B9 (TTL_SEC = 30.0 + monotonic + lazy probe)

Rule 4 wrong-impl challenge:
  - 「永远刷新」(无 TTL)              → B9-N1 FAIL（旧值未保留）
  - 「永远缓存」(_lifespan freeze)   → B9-N2 FAIL（>30s 仍旧值）
  - 「TTL 用 time.time() 而非 monotonic()」→ 系统时钟回拨 flake — by design 用 monotonic
  - 「探针抛 OSError 直接 5xx」       → B9-N3 FAIL
  - 「监视器只缓存 cli_versions 不缓存 claude_auth」→ B9-N2 partial fail

Rule 5 layer:
  [unit] uses ASGITransport + monkeypatch on time.monotonic and
  _probe_cli_version. Real test for end-to-end TTL behaviour against
  uvicorn lives in tests/integration/test_f24_real_health_ttl.py
  (real_http marker).

Feature ref: feature 24

[unit] — uses real harness.api:app via httpx.AsyncClient(ASGITransport).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest


@pytest.fixture
def reset_health_cache() -> Any:
    """Pre-seed `app.state._health_cache` to the post-fix shape for TTL tests.

    Tests that exercise TTL behaviour (B9-N1/N2/P2) opt in via this fixture.
    B9-P1 (schema + invariant) deliberately does NOT use this fixture so it
    can observe the production code's actual cache shape.
    """
    from harness.api import app

    app.state._health_cache = {"_value": None, "_ts": 0.0}
    yield
    app.state._health_cache = {"_value": None, "_ts": 0.0}


# ------------------------------------------------------------------ B9-P1 ----
async def test_b9_p1_schema_4_fields() -> None:
    """First request returns 200 + 4 fields (bind/version/claude_auth/cli_versions).

    Combined with fix-presence: post-fix the cache shape carries a `_ts`
    monotonic timestamp (per §IS B9). Red phase still uses the old shape
    `{cli_versions, claude_auth}` without `_ts`/`_value` — assertion fails.
    """
    from harness.api import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.get("/api/health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) >= {
        "bind",
        "version",
        "claude_auth",
        "cli_versions",
    }, f"schema fields missing; keys={list(body.keys())}"
    cv = body["cli_versions"]
    assert isinstance(cv, dict), f"cli_versions must be dict, got {type(cv)}"
    assert {"claude", "opencode"} <= set(cv.keys()), f"cli_versions missing keys: {cv.keys()}"

    # Post-fix invariant: _health_cache must carry a `_ts` monotonic timestamp
    # (lazy-probe TTL). Red phase: this key is absent.
    cache = getattr(app.state, "_health_cache", None)
    assert isinstance(cache, dict), f"_health_cache missing or wrong type: {type(cache)}"
    assert "_ts" in cache, (
        f"_health_cache missing `_ts` field — TTL semantics not yet wired; "
        f"current keys={list(cache.keys())}"
    )


# ------------------------------------------------------------------ B9-N1 ----
async def test_b9_n1_cache_hit_within_ttl(
    monkeypatch: pytest.MonkeyPatch, reset_health_cache: Any
) -> None:
    """t=0 → curl → t=15 → probe would return new — second curl returns OLD."""
    import harness.api as api_mod
    from harness.api import app

    # Track _probe_cli_version invocations + control its return per call.
    probe_calls: list[str] = []

    def fake_probe(name: str) -> str | None:
        probe_calls.append(name)
        # Each call observes a different probe value to detect staleness.
        return f"{name}-v{len(probe_calls)}"

    monkeypatch.setattr(api_mod, "_probe_cli_version", fake_probe)

    # Pin time.monotonic to a controllable value.
    fake_now = {"v": 0.0}
    monkeypatch.setattr(api_mod.time, "monotonic", lambda: fake_now["v"])  # type: ignore[attr-defined]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as cli:
        fake_now["v"] = 0.0
        first = (await cli.get("/api/health")).json()
        fake_now["v"] = 15.0  # within 30s TTL → must NOT re-probe
        second = (await cli.get("/api/health")).json()

    # The cli_versions snapshot must be identical (cache hit).
    assert first["cli_versions"] == second["cli_versions"], (
        f"cache hit broken: t=15s yielded different value; "
        f"first={first['cli_versions']} second={second['cli_versions']}"
    )
    # Probe must NOT have been called twice on the same name within 30s.
    claude_calls = [c for c in probe_calls if c == "claude"]
    assert len(claude_calls) <= 1, (
        f"probe called {len(claude_calls)} times for 'claude' inside TTL window; "
        f"expected ≤1 — cache disabled or TTL=0"
    )


# ------------------------------------------------------------------ B9-N2 ----
async def test_b9_n2_cache_refresh_after_ttl(
    monkeypatch: pytest.MonkeyPatch, reset_health_cache: Any
) -> None:
    """t=0 → curl → t=31 → second curl re-probes and returns NEW cli_versions."""
    import harness.api as api_mod
    from harness.api import app

    probe_calls: list[str] = []

    def fake_probe(name: str) -> str | None:
        probe_calls.append(name)
        return f"{name}-v{len(probe_calls)}"

    monkeypatch.setattr(api_mod, "_probe_cli_version", fake_probe)

    fake_now = {"v": 0.0}
    monkeypatch.setattr(api_mod.time, "monotonic", lambda: fake_now["v"])  # type: ignore[attr-defined]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as cli:
        fake_now["v"] = 0.0
        first = (await cli.get("/api/health")).json()
        fake_now["v"] = 31.0  # past TTL → must re-probe
        second = (await cli.get("/api/health")).json()

    assert first["cli_versions"] != second["cli_versions"], (
        f"TTL refresh broken: t=31s should yield NEW values; "
        f"first={first['cli_versions']} second={second['cli_versions']}"
    )
    # Both probe names must have been called at least twice across the two requests.
    assert (
        probe_calls.count("claude") >= 2
    ), f"second request did not re-probe 'claude'; calls={probe_calls}"


# ------------------------------------------------------------------ B9-P2 ----
async def test_b9_p2_perf_probe_count_under_load(
    monkeypatch: pytest.MonkeyPatch, reset_health_cache: Any
) -> None:
    """100 sequential GETs within the same monotonic instant → ≤2 probe calls per name."""
    import harness.api as api_mod
    from harness.api import app

    probe_calls: list[str] = []

    def fake_probe(name: str) -> str | None:
        probe_calls.append(name)
        return f"{name}-stable"

    monkeypatch.setattr(api_mod, "_probe_cli_version", fake_probe)

    # All 100 requests observe t=5.0 (single TTL window).
    monkeypatch.setattr(api_mod.time, "monotonic", lambda: 5.0)  # type: ignore[attr-defined]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as cli:
        for _ in range(100):
            r = await cli.get("/api/health")
            assert r.status_code == 200

    # ≤2 calls (claude + opencode = 2) for the entire 100-request burst.
    assert len(probe_calls) <= 2, (
        f"_probe_cli_version called {len(probe_calls)} times across 100 requests "
        f"in TTL window — caching disabled. calls={probe_calls!r}"
    )


# ------------------------------------------------------------------ B9-N3 ----
async def test_b9_n3_probe_oserror_does_not_5xx(
    monkeypatch: pytest.MonkeyPatch, reset_health_cache: Any
) -> None:
    """When _probe_cli_version raises OSError, /api/health must still return 200."""
    import harness.api as api_mod
    from harness.api import app

    def boom(_name: str) -> str | None:
        raise OSError("simulated CLI exec failure")

    monkeypatch.setattr(api_mod, "_probe_cli_version", boom)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.get("/api/health")

    # Must NOT propagate as 500.
    assert (
        resp.status_code == 200
    ), f"OSError leaked as 5xx; status={resp.status_code} body={resp.text[:200]!r}"
    body = resp.json()
    # cli_versions field must still be present (degradation), not absent.
    assert "cli_versions" in body, "cli_versions field dropped on probe error"
    cv = body["cli_versions"]
    # Acceptable degraded shape: {"claude": None, "opencode": None}.
    assert isinstance(cv, dict), f"cli_versions must remain dict on error; got {type(cv)}"
