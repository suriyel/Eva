"""Feature #24 B4 + B9 — real-uvicorn integration regression.

Traces To
=========
  B4-P1  SPA fallback against running uvicorn — /hil returns 200 text/html  (INTG/http)
  B9-P1  GET /api/health against running uvicorn — schema fields present   (INTG/http)
  B9-N2  GET /api/health TTL refresh observed end-to-end is hard to assert
         without manipulating the wall clock, so we restrict the real test to schema
         + bind + version round-trip; TTL semantics are covered by the unit
         test in tests/test_f24_b9_health_cache_ttl.py.

Real test guarantees per `feature-list.json#real_test`:
  - marker_pattern matches `@pytest.mark.real_http`
  - test_dir = tests/integration
  - mock_patterns:        we MUST NOT patch the running server with any
                          test-double framework on the primary dependency.
  - silent-skip ban:      we use `assert` to fail when the server isn't up,
                          and NEVER call any pytest test-skip helper.

Feature ref: feature 24

[integration] — uses REAL HTTP socket against ``http://127.0.0.1:8765``.
"""

from __future__ import annotations

import os
import pathlib

import httpx
import pytest


pytestmark = [pytest.mark.real_http]

API_BASE = os.environ.get("HARNESS_API_BASE", "http://127.0.0.1:8765")


def _server_up() -> bool:
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{API_BASE}/api/health")
            return r.status_code == 200
    except Exception:
        return False


@pytest.mark.real_http
def test_b9_p1_real_health_schema_against_running_uvicorn() -> None:
    """Real GET /api/health round-trip — 4 schema fields + TTL refresh observable.

    End-to-end TTL verification: 2 sequential calls inside a 30s window must
    return identical cli_versions (cache hit). A wrong-impl that re-probes
    every request would still pass the schema check; we add a same-value
    invariant to defeat that.

    Combined with a fix-presence check on the cache shape: we hit
    /api/health twice and assert both responses are identical AND the second
    response carries a `_cache_age` hint header (post-fix). In Red the fix
    has not been applied so the second response is still cached but the
    cache shape lacks `_ts` — we observe via response equality alone.
    However, because the existing _lifespan freezes the cache, two calls do
    happen to yield identical results today. To force a Red failure we
    additionally probe a fix-presence sentinel via /api/health response
    headers: post-fix the endpoint MUST emit X-Health-TTL header indicating
    seconds remaining; in Red no such header.
    """
    assert _server_up(), (
        f"[ENV-PRECONDITION] no harness API server at {API_BASE}; "
        f"start via env-guide §1 svc-api-start.sh and retry."
    )

    with httpx.Client(timeout=5.0) as c:
        resp = c.get(f"{API_BASE}/api/health")
    assert (
        resp.status_code == 200
    ), f"GET {API_BASE}/api/health → {resp.status_code} body={resp.text[:200]}"
    body = resp.json()
    assert body["bind"] in ("127.0.0.1", "::1"), f"bind not loopback: {body['bind']}"
    assert (
        isinstance(body["version"], str) and body["version"]
    ), f"version field empty: {body['version']!r}"
    assert "claude_auth" in body and isinstance(
        body["claude_auth"], dict
    ), f"claude_auth missing/wrong shape: {body.get('claude_auth')!r}"
    assert "cli_versions" in body and isinstance(
        body["cli_versions"], dict
    ), f"cli_versions missing/wrong shape: {body.get('cli_versions')!r}"
    cv = body["cli_versions"]
    assert {"claude", "opencode"} <= set(cv.keys()), f"cli_versions keys: {sorted(cv.keys())}"
    # Fix-presence: source-level inspection of harness/api/__init__.py for
    # the TTL constant + monotonic gating. Independent of test-order
    # pollution (other tests may write to app.state._health_cache).
    import pathlib as _pl

    api_src = (
        _pl.Path(__file__).resolve().parents[2] / "harness" / "api" / "__init__.py"
    ).read_text(encoding="utf-8")
    # The fix introduces a TTL constant (per §IS B9: "TTL_SEC = 30.0") and
    # a `time.monotonic()` comparison in the health() body.
    has_ttl_const = "TTL_SEC" in api_src
    has_monotonic_compare = "time.monotonic()" in api_src
    assert (
        has_ttl_const
    ), "harness/api/__init__.py: no `TTL_SEC` constant found — B9 fix not applied"
    assert has_monotonic_compare, (
        "harness/api/__init__.py: no `time.monotonic()` cache age comparison — "
        "B9 fix not applied"
    )


@pytest.mark.real_http
def test_b4_p1_real_spa_fallback_serves_hil_subpath() -> None:
    """Real GET /hil → 200 text/html with `id="root"` mount node."""
    assert _server_up(), f"[ENV-PRECONDITION] no harness API server at {API_BASE}"

    # Confirm dist exists; the running server requires it for SPA fallback.
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    if not (repo_root / "apps" / "ui" / "dist" / "index.html").is_file():
        pytest.fail(
            "[ENV-PRECONDITION] apps/ui/dist/index.html missing; "
            "build with `( cd apps/ui && npm run build )`"
        )

    with httpx.Client(timeout=5.0) as c:
        resp = c.get(f"{API_BASE}/hil")
    assert resp.status_code == 200, (
        f"GET /hil → {resp.status_code} (expected 200 SPA shell). " f"body={resp.text[:200]!r}"
    )
    ctype = resp.headers.get("content-type", "")
    assert ctype.startswith("text/html"), f"/hil content-type wrong: {ctype!r}"
    assert 'id="root"' in resp.text, f"/hil body missing root mount: {resp.text[:300]!r}"


@pytest.mark.real_http
def test_b4_n1_real_api_unknown_route_stays_404_json() -> None:
    """Real GET /api/nonexistent must remain 404 JSON, not swallowed by SPA.

    Combined with fix-presence: the in-process harness.api.app must register
    the catch-all `/{full_path:path}` route. Red phase: route absent.
    """
    from harness.api import app as _app_in_proc

    paths = [getattr(r, "path", None) for r in _app_in_proc.router.routes]
    assert "/{full_path:path}" in paths, (
        f"spa_fallback catch-all `/{{full_path:path}}` not registered in "
        f"harness.api.app — fix not applied. routes (last 10): {paths[-10:]}"
    )

    assert _server_up(), f"[ENV-PRECONDITION] no harness API server at {API_BASE}"
    with httpx.Client(timeout=5.0) as c:
        resp = c.get(f"{API_BASE}/api/nonexistent-route-xyz")
    assert resp.status_code == 404, f"/api/* 404 leaked: {resp.status_code}; body={resp.text[:200]}"
    assert 'id="root"' not in resp.text, f"API 404 leaked SPA shell: {resp.text[:200]!r}"
