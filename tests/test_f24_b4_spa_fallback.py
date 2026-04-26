"""Feature #24 B4 — SPA fallback for unknown sub-paths.

Traces To
=========
  B4-P1  §IC `harness.api.app.spa_fallback` postcondition / FR-049 / NFR-013   (INTG/http)
  B4-P2  §IC `spa_fallback` 6-path coverage                                    (INTG/http)
  B4-N1  §IC `spa_fallback` Raises — must NOT swallow /api/* 404               (FUNC/error)
  B4-N2  §IC `spa_fallback` Raises — must NOT swallow /ws/* GET                (FUNC/error)
  B4-N3  §IC `spa_fallback` SEC — path traversal (`/../etc/passwd`) / FR-035   (SEC/path-traversal)
         FR-035 (path traversal 拒绝) 与 NFR-007 (loopback bind) 共轨：fallback 命中时
         必须既不泄漏 dist 外文件（FR-035），也不被外部地址访问（NFR-007 仅 127.0.0.1）。
  B4-P3  §IC `spa_fallback` static asset still served                          (INTG/http)
  §Design Alignment flowchart TD branch#1..#6 (B4 SPA fallback resolver)
  §Implementation Summary B4 (catch-all `@app.get("/{full_path:path}")`)

Rule 4 wrong-impl challenge:
  - 「忘记顺序：fallback 注册在 router 之前」 → /api/health 命中 fallback 返 200 text/html → B4-N1 FAIL
  - 「fallback 不分 api/ ws/ 前缀」 → 同上 FAIL
  - 「fallback 仅 html=True 不显式 catch-all」 → /hil 仍 404 → B4-P1 FAIL
  - 「path traversal 被解码后命中 dist/index.html」 → B4-N3 仍 200 但内容错 → assert 内容包含 root mount → 假阳性
  - 「StaticFiles mount 顺序错」 → /assets/x.js 返回 index.html → B4-P3 FAIL

Rule 5 layer:
  [unit] uses TestClient (in-process ASGI) — no socket; harness.api:app real
  import (not mocked).
  Real test for end-to-end SPA fallback against running uvicorn lives in
  tests/integration/test_f24_real_health_ttl.py (real_http marker).

Feature ref: feature 24

[unit] — uses real harness.api:app via Starlette TestClient.
"""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient


def _ui_dist_index_exists() -> bool:
    return (
        pathlib.Path(__file__).resolve().parents[1] / "apps" / "ui" / "dist" / "index.html"
    ).is_file()


@pytest.fixture()
def client() -> TestClient:
    """Build a TestClient against the production harness.api:app.

    The catch-all `spa_fallback` route is expected to be registered at module
    import time (post-router, post-StaticFiles mount). In Red phase this
    expectation fails because no such route exists.
    """
    from harness.api import app

    return TestClient(app)


# ------------------------------------------------------------------ B4-P1 ----
def test_b4_p1_spa_fallback_serves_index_for_hil_path(client: TestClient) -> None:
    """GET /hil → 200 text/html with `<div id="root">` body."""
    if not _ui_dist_index_exists():
        # Build apps/ui/dist or skip — Red still fails because feature unimplemented.
        # Use assert (not pytest.skip) per Rule 5a real-test silent-skip ban.
        pytest.fail(
            "[ENV-PRECONDITION] apps/ui/dist/index.html missing — run "
            "`( cd apps/ui && npm run build )`. Test is INVALID without it."
        )

    resp = client.get("/hil")
    # Hard assertion (B4 direct hit): currently this returns 404 + JSON.
    assert (
        resp.status_code == 200
    ), f"expected 200 for SPA route /hil, got {resp.status_code} body={resp.text[:200]}"
    ctype = resp.headers.get("content-type", "")
    assert ctype.startswith("text/html"), f"expected text/html, got content-type={ctype!r}"
    body = resp.text
    # Vite SPA shell must contain `<div id="root">` — assert content correctness,
    # not just length, to defeat "return empty 200".
    assert (
        '<div id="root">' in body or 'id="root"' in body
    ), f"SPA index.html must contain id=root mount node; body[:300]={body[:300]!r}"


# ------------------------------------------------------------------ B4-P2 ----
@pytest.mark.parametrize(
    "path",
    ["/settings", "/docs", "/skills", "/process-files", "/commits", "/ticket-stream"],
)
def test_b4_p2_spa_fallback_serves_index_for_six_subpaths(client: TestClient, path: str) -> None:
    """6 SPA sub-paths each return 200 text/html with root mount."""
    if not _ui_dist_index_exists():
        pytest.fail("[ENV-PRECONDITION] apps/ui/dist/index.html missing")

    resp = client.get(path)
    assert resp.status_code == 200, (
        f"expected 200 for SPA route {path}, got {resp.status_code} " f"body={resp.text[:200]}"
    )
    assert resp.headers.get("content-type", "").startswith(
        "text/html"
    ), f"path={path} content-type={resp.headers.get('content-type')!r}"
    body = resp.text
    assert 'id="root"' in body, f"path={path} body missing root mount: {body[:300]!r}"


# ------------------------------------------------------------------ B4-N1 ----
def test_b4_n1_api_unknown_returns_json_404_not_swallowed(client: TestClient) -> None:
    """/api/nonexistent must remain 404 JSON (router precedence after fallback registered).

    This is a regression guard: the fix MUST register `spa_fallback` AFTER the
    9 routers but the route precedence semantics must keep /api/* under their
    routers' 404 path. We assert (a) the fallback route exists in the app's
    route table — the fix introduces it; in Red phase it does not — AND (b)
    /api/* 404 is JSON.
    """
    from harness.api import app

    # The fix introduces a catch-all route `/{full_path:path}` registered last.
    # Red phase: this route does NOT exist → assertion fails.
    paths = [getattr(r, "path", None) for r in app.router.routes]
    assert "/{full_path:path}" in paths, (
        f"spa_fallback catch-all `/{{full_path:path}}` not registered; "
        f"current routes (last 10): {paths[-10:]}"
    )

    resp = client.get("/api/nonexistent-route-xyz")
    assert resp.status_code == 404, (
        f"/api/nonexistent must be 404, got {resp.status_code}; "
        f"fallback MUST NOT swallow API 404"
    )
    ctype = resp.headers.get("content-type", "")
    assert (
        "application/json" in ctype or "text/plain" in ctype
    ), f"/api/* 404 must not be SPA HTML; got content-type={ctype!r}"
    assert 'id="root"' not in resp.text, f"API 404 leaked SPA shell body: {resp.text[:200]!r}"


# ------------------------------------------------------------------ B4-N2 ----
def test_b4_n2_ws_path_via_http_get_not_swallowed(client: TestClient) -> None:
    """GET /ws/nonexistent (non-upgrade) must NOT return SPA index.

    Regression guard with fix-presence check: assert the fallback function
    `spa_fallback` exists as an attribute of `harness.api`; this is part of
    the fix per §IC. In Red phase, the function does not exist.
    """
    import harness.api as api_mod

    assert hasattr(
        api_mod, "spa_fallback"
    ), "harness.api.spa_fallback function not defined — fix not yet applied"

    resp = client.get("/ws/nonexistent-channel")
    assert resp.status_code in (404, 405, 426, 400), (
        f"/ws/* HTTP GET must not return 200 SPA, got {resp.status_code}; "
        f"body={resp.text[:200]}"
    )
    assert 'id="root"' not in resp.text, f"WS path leaked SPA shell: {resp.text[:200]!r}"


# ------------------------------------------------------------------ B4-N3 ----
def test_b4_n3_path_traversal_rejected_or_normalized(client: TestClient) -> None:
    """Path traversal `/../../etc/passwd` must NOT serve /etc/passwd contents.

    Combined with fix-presence: the fallback route `/{full_path:path}` must be
    registered AND the fix must reject traversal. In Red the route doesn't
    exist; in Green the fallback resolves traversal cleanly.
    """
    from harness.api import app

    paths = [getattr(r, "path", None) for r in app.router.routes]
    assert "/{full_path:path}" in paths, (
        f"spa_fallback catch-all not registered; cannot enforce "
        f"path-traversal semantics. routes (last 10): {paths[-10:]}"
    )

    resp = client.get("/../../etc/passwd")
    assert (
        "root:x:0" not in resp.text
    ), f"path traversal exposed /etc/passwd content: {resp.text[:200]!r}"
    assert resp.status_code in (
        200,
        400,
        403,
        404,
    ), f"unexpected status {resp.status_code} for traversal probe"


# ------------------------------------------------------------------ B4-P3 ----
def test_b4_p3_static_asset_served_not_replaced_by_index(client: TestClient) -> None:
    """A real /assets/* JS file must serve as application/javascript, not SPA.

    Combined with fix-presence: the fallback must be registered AFTER static
    files mount. Pre-fix the fallback doesn't exist; post-fix it must be
    after StaticFiles mount (so static assets win).
    """
    from harness.api import app

    paths = [getattr(r, "path", None) for r in app.router.routes]
    # In Green, the LAST route MUST be the fallback (per Implementation Summary B4
    # "在所有 router/static 之后注册").
    assert (
        "/{full_path:path}" in paths
    ), f"spa_fallback catch-all not registered; routes (last 10): {paths[-10:]}"
    # Fallback must be the very last route registered.
    assert getattr(app.router.routes[-1], "path", None) == "/{full_path:path}", (
        f"spa_fallback must be registered last (after StaticFiles + 9 routers); "
        f"current last route: {getattr(app.router.routes[-1], 'path', None)!r}"
    )

    if not _ui_dist_index_exists():
        pytest.fail("[ENV-PRECONDITION] apps/ui/dist/index.html missing")

    dist = pathlib.Path(__file__).resolve().parents[1] / "apps" / "ui" / "dist"
    assets_dir = dist / "assets"
    if not assets_dir.is_dir():
        pytest.fail("[ENV-PRECONDITION] apps/ui/dist/assets missing — vite build incomplete")
    js_files = list(assets_dir.glob("*.js"))
    assert js_files, "[ENV-PRECONDITION] no .js asset emitted by vite build"

    asset_name = js_files[0].name
    resp = client.get(f"/assets/{asset_name}")
    assert resp.status_code == 200, f"static asset /assets/{asset_name} returned {resp.status_code}"
    ctype = resp.headers.get("content-type", "")
    assert "javascript" in ctype or "ecmascript" in ctype, (
        f"static asset content-type wrong: {ctype!r} — fallback may have " f"swallowed /assets/*"
    )
    assert (
        'id="root"' not in resp.text
    ), "asset body leaked SPA shell — fallback misordered before StaticFiles"


# --------------------------------------------------------------- B4-N4 (extra)
def test_b4_n4_dotfile_traversal_does_not_leak_repo_files(
    client: TestClient,
) -> None:
    """SEC: GET `/.git/config` and `/.env` must NOT serve repo dotfiles.

    Defends against a wrong fallback that resolves `full_path` via
    `UI_DIST/full_path` without rejecting paths outside the dist tree, OR
    a mistake of mounting StaticFiles at repo root by accident.
    """
    from harness.api import app

    paths = [getattr(r, "path", None) for r in app.router.routes]
    assert "/{full_path:path}" in paths, "spa_fallback catch-all not registered — fix not applied"

    for probe in ("/.git/config", "/.env", "/CLAUDE.md", "/feature-list.json"):
        resp = client.get(probe)
        # Either SPA fallback (200 + index) OR 404 — never the actual file
        # content. Body must NOT contain repo-internal markers.
        body = resp.text
        forbidden = ("[core]", "HARNESS_HOME=", "SECRET", '"features":')
        for marker in forbidden:
            assert (
                marker not in body
            ), f"{probe} leaked repo content (marker={marker!r}): {body[:200]!r}"
