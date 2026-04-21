"""Harness FastAPI app (F01) — exposes ``/api/health``.

Design §6.2.2: GET /api/health → JSON { bind, version, claude_auth, cli_versions }.

The module-level ``app`` is imported by:
    * ``uvicorn harness.api:app`` (dev start script svc-api-start.sh)
    * ``harness.app.AppBootstrap`` (production runtime)
    * ``tests/test_f01_health_endpoint.py`` (unit test via ASGI transport)
"""

from __future__ import annotations

import shutil
import subprocess

from fastapi import FastAPI

from .. import __version__
from ..auth import ClaudeAuthDetector, ClaudeAuthStatus

app = FastAPI(title="Harness", version=__version__)


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
    # NFR-007 defense: never advertise a non-loopback host.
    if bind_host not in {"127.0.0.1", "::1"}:
        bind_host = "127.0.0.1"

    cached: ClaudeAuthStatus | None = getattr(app.state, "claude_auth_status", None)
    if cached is None:
        cached = ClaudeAuthDetector().detect()

    return {
        "bind": bind_host,
        "version": __version__,
        "claude_auth": cached.model_dump(mode="json"),
        "cli_versions": {
            "claude": _probe_cli_version("claude"),
            "opencode": _probe_cli_version("opencode"),
        },
    }


__all__ = ["app"]
