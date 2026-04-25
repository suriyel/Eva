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
import os
import pathlib
import shutil
import subprocess
from collections.abc import AsyncIterator

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from .. import __version__
from ..auth import ClaudeAuthDetector, ClaudeAuthStatus
from .wiring import wire_services


@contextlib.asynccontextmanager
async def _lifespan(app_: FastAPI) -> AsyncIterator[None]:
    """Auto-wire services from HARNESS_WORKDIR when launched via uvicorn.

    Tests that drive the app via TestClient/ASGITransport call
    :func:`wire_services` themselves; the lifespan path is only exercised by
    the real uvicorn subprocess (F23 R22-R27).
    """
    workdir_env = os.environ.get("HARNESS_WORKDIR", "").strip()
    if workdir_env and not getattr(app_.state, "orchestrator", None):
        try:
            wire_services(app_, workdir=pathlib.Path(workdir_env))
        except Exception:
            pass
    # Cache /api/health probe results so the first request doesn't block on
    # subprocess CLI invocations (claude --version / opencode --version).
    if not hasattr(app_.state, "_health_cache"):
        try:
            cli_versions = {
                "claude": _probe_cli_version("claude"),
                "opencode": _probe_cli_version("opencode"),
            }
        except Exception:
            cli_versions = {"claude": None, "opencode": None}
        try:
            claude_auth = ClaudeAuthDetector().detect()
        except Exception:
            claude_auth = None
        app_.state._health_cache = {
            "cli_versions": cli_versions,
            "claude_auth": claude_auth,
        }
    yield


app = FastAPI(title="Harness", version=__version__, lifespan=_lifespan)

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

app.include_router(_runs_router)
app.include_router(_tickets_router)
app.include_router(_hil_router)
app.include_router(_anomaly_router)
app.include_router(_signal_router)
app.include_router(_files_router)
app.include_router(_git_router)
app.include_router(_general_settings_router)
app.include_router(_validate_router)


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
    """
    bind_host = getattr(app.state, "bind_host", "127.0.0.1")
    if bind_host not in {"127.0.0.1", "::1"}:
        bind_host = "127.0.0.1"

    cached: ClaudeAuthStatus | None = getattr(app.state, "claude_auth_status", None)
    health_cache = getattr(app.state, "_health_cache", None)
    if cached is None and isinstance(health_cache, dict):
        cached = health_cache.get("claude_auth")
    if cached is None:
        cached = ClaudeAuthDetector().detect()

    if isinstance(health_cache, dict) and "cli_versions" in health_cache:
        cli_versions = health_cache["cli_versions"]
    else:
        cli_versions = {
            "claude": _probe_cli_version("claude"),
            "opencode": _probe_cli_version("opencode"),
        }

    return {
        "bind": bind_host,
        "version": __version__,
        "claude_auth": cached.model_dump(mode="json"),
        "cli_versions": cli_versions,
    }


# --------------------------------------------------------------------------- #
# StaticFiles mount (apps/ui/dist → /)
# Registered last so `/api/*` + `/ws/*` routes match first. `html=True` enables
# SPA fallback (unknown paths return `index.html`).
# --------------------------------------------------------------------------- #
_UI_DIST = pathlib.Path(__file__).resolve().parents[2] / "apps" / "ui" / "dist"
if _UI_DIST.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(_UI_DIST), html=True),
        name="ui",
    )


__all__ = ["app", "wire_services"]
