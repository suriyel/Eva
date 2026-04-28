"""Harness FastAPI app — exposes ``/api/health`` + IAPI-002 / IAPI-001 routes.

Design §6.2.2: GET /api/health → JSON { bind, version, claude_auth, cli_versions }.

The module-level ``app`` is imported by:
    * ``uvicorn harness.api:app`` (dev start script svc-api-start.sh)
    * ``harness.app.AppBootstrap`` (production runtime)
    * ``tests/test_f01_health_endpoint.py`` (unit test via ASGI transport)

F23 wiring: 14 REST routes + 5 WebSocket broadcasters are mounted via
:mod:`harness.api.runs` / :mod:`harness.api.tickets` / :mod:`harness.api.hil`
/ :mod:`harness.api.anomaly` / :mod:`harness.api.signal_ws` /
:mod:`harness.api.files_routes` / :mod:`harness.api.git_routes` /
:mod:`harness.api.general_settings` / :mod:`harness.api.validate`. Service
singletons are populated on ``app.state`` via :func:`wire_services` (called
by ``AppBootstrap`` or by integration tests).
"""

from __future__ import annotations

import contextlib
import pathlib
import shutil
import subprocess
import sys
import time
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from .. import __version__
from ..auth import ClaudeAuthDetector, ClaudeAuthStatus
from ..config.schema import ConfigCorruptError, HarnessConfig
from ..config.store import ConfigStore
from .wiring import wire_services


# Health cache TTL (B9 — §IS B9). Use time.monotonic() so wall-clock skew
# doesn't bypass the refresh.
TTL_SEC = 30.0


@contextlib.asynccontextmanager
async def _lifespan(app_: FastAPI) -> AsyncIterator[None]:
    """Auto-wire services based on ``config.current_workdir``.

    UI 端通过 ``/api/workdirs/select`` 显式选/切换 workdir；lifespan 仅在
    重启时把上次 current 自动 wire 起来。无 current 或路径失效时**不报错**，
    所有依赖 orchestrator 的路由会优雅返回空态。
    """
    store = ConfigStore(ConfigStore.default_path())
    try:
        cfg = store.load()
    except ConfigCorruptError:
        cfg = HarnessConfig.default()
    target = cfg.current_workdir
    if target and pathlib.Path(target).is_dir():
        try:
            wire_services(app_, workdir=pathlib.Path(target))
        except Exception as exc:
            sys.stderr.write(
                f"[harness] wire_services failed for {target}: {exc}\n"
            )
    # B9 — initialise the lazy-probe cache; do NOT freeze cli_versions /
    # claude_auth here. The cache is refreshed by ``health()`` on demand
    # (TTL=30s via time.monotonic()).
    app_.state._health_cache = {"_value": None, "_ts": 0.0}
    yield


app = FastAPI(
    title="Harness",
    version=__version__,
    lifespan=_lifespan,
    # B4 — `/docs` is reserved for the SPA route (renders `id="root"` shell);
    # FastAPI's default Swagger UI would shadow it. We disable the default
    # docs/redoc/openapi.json endpoints since this is an internal loopback API
    # consumed by the Vite-built UI (the OpenAPI surface is documented via
    # design docs, not Swagger).
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# F10 · Skills Installer REST (IAPI-018) + F23 · /api/skills/tree
from .skills import router as _skills_router  # noqa: E402

app.include_router(_skills_router)

# F19 · Bk-Dispatch REST routers (IAPI-002 sub-routes)
from .settings import router as _settings_router  # noqa: E402
from .prompts import router as _prompts_router  # noqa: E402

app.include_router(_settings_router)
app.include_router(_prompts_router)

# F23 · IAPI-002 / IAPI-001 routers
from .runs import router as _runs_router  # noqa: E402
from .tickets import router as _tickets_router  # noqa: E402
from .hil import router as _hil_router  # noqa: E402
from .anomaly import router as _anomaly_router  # noqa: E402
from .signal_ws import router as _signal_router  # noqa: E402
from .files_routes import router as _files_router  # noqa: E402
from .git_routes import router as _git_router  # noqa: E402
from .general_settings import router as _general_settings_router  # noqa: E402
from .validate import router as _validate_router  # noqa: E402
from .hook import router as _hook_router  # noqa: E402  (F18 Wave 4 IAPI-020)
from .pty_writer import router as _pty_writer_router  # noqa: E402  (F18 Wave 4 IAPI-021)
from .workdir import router as _workdir_router  # noqa: E402

app.include_router(_runs_router)
app.include_router(_tickets_router)
app.include_router(_hil_router)
app.include_router(_anomaly_router)
app.include_router(_signal_router)
app.include_router(_files_router)
app.include_router(_git_router)
app.include_router(_general_settings_router)
app.include_router(_validate_router)
app.include_router(_hook_router)
app.include_router(_pty_writer_router)
app.include_router(_workdir_router)


def _probe_cli_version(name: str) -> str | None:
    """Run ``<name> --version`` and return stdout trimmed; None when missing."""
    path = shutil.which(name)
    if path is None:
        return None
    try:
        proc = subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or proc.stderr or "").strip() or None


@app.get("/api/health")
def health() -> dict[str, object]:
    """Return loopback-bind status + claude auth + CLI versions.

    ``bind`` is sourced from ``app.state.bind_host`` when ``AppBootstrap.start``
    populated it; otherwise we default to the hard-coded constant ``127.0.0.1``
    (CON-006 — this endpoint must NEVER advertise a non-loopback bind).

    B9 — health probe results (cli_versions + claude_auth) are cached with a
    30-second monotonic TTL. ``_probe_cli_version`` raising ``OSError`` does
    NOT propagate as 5xx; the cache simply isn't refreshed and we degrade to
    a ``{"claude": None, "opencode": None}`` shape on the first miss.
    """
    bind_host = getattr(app.state, "bind_host", "127.0.0.1")
    if bind_host not in {"127.0.0.1", "::1"}:
        bind_host = "127.0.0.1"

    cache = getattr(app.state, "_health_cache", None)
    if not isinstance(cache, dict) or "_ts" not in cache:
        cache = {"_value": None, "_ts": 0.0}
        app.state._health_cache = cache

    now = time.monotonic()
    needs_refresh = cache.get("_value") is None or (now - cache.get("_ts", 0.0)) > TTL_SEC
    if needs_refresh:
        try:
            cli_versions = {
                "claude": _probe_cli_version("claude"),
                "opencode": _probe_cli_version("opencode"),
            }
        except OSError:
            # Probe failure: degrade to None values; do NOT raise 5xx.
            cli_versions = {"claude": None, "opencode": None}
        try:
            claude_auth = ClaudeAuthDetector().detect()
        except Exception:
            claude_auth = None
        cache["_value"] = {"cli_versions": cli_versions, "claude_auth": claude_auth}
        cache["_ts"] = now

    cached_value = cache.get("_value") or {}
    cli_versions_out = cached_value.get("cli_versions") or {"claude": None, "opencode": None}
    claude_auth_obj: ClaudeAuthStatus | None = cached_value.get("claude_auth")
    # Late-bind fallback to AppBootstrap-populated detector result so first-request
    # round-trip still returns the rich shape.
    if claude_auth_obj is None:
        claude_auth_obj = getattr(app.state, "claude_auth_status", None)
    if claude_auth_obj is None:
        claude_auth_obj = ClaudeAuthDetector().detect()

    return {
        "bind": bind_host,
        "version": __version__,
        "claude_auth": claude_auth_obj.model_dump(mode="json"),
        "cli_versions": cli_versions_out,
    }


# --------------------------------------------------------------------------- #
# StaticFiles mount (apps/ui/dist/assets → /assets)
# B4 — Don't rely on `html=True` (StaticFiles only auto-resolves index.html for
# precise dir hits like `/`). Instead serve assets explicitly + register a
# catch-all SPA fallback last so unknown sub-paths (`/hil`, `/settings`, etc.)
# return `index.html`.
# --------------------------------------------------------------------------- #
_UI_DIST = pathlib.Path(__file__).resolve().parents[2] / "apps" / "ui" / "dist"
if _UI_DIST.exists():
    _ASSETS_DIR = _UI_DIST / "assets"
    if _ASSETS_DIR.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_ASSETS_DIR)),
            name="ui-assets",
        )


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request) -> FileResponse:
    """B4 — SPA fallback for unknown sub-paths.

    Decision tree (see §Design Alignment flowchart TD branch#1..#6):
      1. ``api/`` prefix → defensive 404 (router precedence has already
         handled valid ``/api/*`` paths; this is a not-found that the
         catch-all MUST NOT swallow as SPA shell).
      2. ``ws/`` prefix → defensive 404 (same rationale).
      3. ``UI_DIST/<full_path>`` resolves to a real file (e.g. ``favicon.ico``)
         → serve it as static.
      4. else → return ``UI_DIST/index.html`` so react-router can take over.

    Path traversal is rejected by Starlette's URL normalisation BEFORE this
    handler is invoked; we additionally guard against ``..`` segments resolving
    outside ``UI_DIST`` for defensive depth.
    """
    if full_path.startswith(("api/", "ws/")):
        raise HTTPException(status_code=404)

    if not _UI_DIST.exists():
        raise HTTPException(status_code=404)

    # Defensive: candidate must resolve under UI_DIST.
    if full_path:
        try:
            candidate = (_UI_DIST / full_path).resolve()
            ui_dist_resolved = _UI_DIST.resolve()
            if (
                candidate != ui_dist_resolved
                and ui_dist_resolved in candidate.parents
                and candidate.is_file()
            ):
                return FileResponse(str(candidate))
        except (OSError, ValueError):
            pass

    index = _UI_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(str(index), media_type="text/html", status_code=200)


__all__ = ["app", "wire_services", "spa_fallback"]
