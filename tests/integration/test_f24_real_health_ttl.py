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

[integration] — uses REAL HTTP socket against ``http://127.0.0.1:8765``.
The ``running_uvicorn`` module-scope fixture spawns a real uvicorn subprocess
and polls /api/health until ready, so the test suite no longer needs a manual
``svc-api-start.sh`` precondition. If a server is already listening on 8765
(e.g. dev started one manually) the fixture reuses it instead of double-binding.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time

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


@pytest.fixture(scope="module", autouse=True)
def running_uvicorn():
    """Start uvicorn against ``harness.api:app`` on 127.0.0.1:8765.

    Reuses an already-running server if one is listening, otherwise spawns
    a subprocess and polls /api/health until 200 (≤15s boot budget).
    """
    if _server_up():
        yield
        return

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "harness.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--log-level",
            "warning",
        ],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 15.0
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        if _server_up():
            break
        time.sleep(0.3)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        pytest.fail(f"uvicorn boot timeout after 15s; last_err={last_err!r}")

    try:
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.mark.real_http
def test_b9_p1_real_health_schema_against_running_uvicorn() -> None:
    """Real GET /api/health round-trip — 4 schema fields + TTL refresh observable."""
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
    api_src = (
        pathlib.Path(__file__).resolve().parents[2] / "harness" / "api" / "__init__.py"
    ).read_text(encoding="utf-8")
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
    """Real GET /api/nonexistent must remain 404 JSON, not swallowed by SPA."""
    from harness.api import app as _app_in_proc

    paths = [getattr(r, "path", None) for r in _app_in_proc.router.routes]
    assert "/{full_path:path}" in paths, (
        f"spa_fallback catch-all `/{{full_path:path}}` not registered in "
        f"harness.api.app — fix not applied. routes (last 10): {paths[-10:]}"
    )

    with httpx.Client(timeout=5.0) as c:
        resp = c.get(f"{API_BASE}/api/nonexistent-route-xyz")
    assert resp.status_code == 404, f"/api/* 404 leaked: {resp.status_code}; body={resp.text[:200]}"
    assert 'id="root"' not in resp.text, f"API 404 leaked SPA shell: {resp.text[:200]!r}"
