"""Harness FastAPI app (F01) — exposes ``/api/health``.

Design §6.2.2: GET /api/health → JSON { bind, version, claude_auth, cli_versions }.

The module-level ``app`` is imported by:
    * ``uvicorn harness.api:app`` (dev start script svc-api-start.sh)
    * ``harness.app.AppBootstrap`` (production runtime)
    * ``tests/test_f01_health_endpoint.py`` (unit test via ASGI transport)

F12 additions (see docs/features/12-f12-frontend-foundation.md §Implementation Summary):
    * WebSocket endpoints for IAPI-001 multi-channel envelopes (``/ws/run/{id}``, ``/ws/hil``).
    * StaticFiles mount at ``/`` serving ``apps/ui/dist`` (SPA root) — registered AFTER
      all API routes so FastAPI dispatches ``/api/*`` before the static fallback.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
from collections.abc import Mapping

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.staticfiles import StaticFiles

from .. import __version__
from ..auth import ClaudeAuthDetector, ClaudeAuthStatus

app = FastAPI(title="Harness", version=__version__)

# F10 · Skills Installer REST (IAPI-018)
from .skills import router as _skills_router  # noqa: E402  late import to keep app ready

app.include_router(_skills_router)

# F19 · Bk-Dispatch REST routers (IAPI-002 sub-routes)
from .settings import router as _settings_router  # noqa: E402
from .prompts import router as _prompts_router  # noqa: E402

app.include_router(_settings_router)
app.include_router(_prompts_router)


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


# --------------------------------------------------------------------------- #
# F12 · WebSocket endpoints (IAPI-001 minimal envelope)
# --------------------------------------------------------------------------- #


async def _ws_echo_channel(
    websocket: WebSocket,
    channel: str,
    initial_envelope: Mapping[str, object] | None = None,
) -> None:
    """Accept a loopback-origin WS, acknowledge subscribe, optionally push initial envelope.

    The envelope schema here is intentionally minimal — F18/F19/F20 will replace
    individual handlers with real business payloads. F12 only asserts the wire
    contract: `{"kind": ..., "channel": ...}` JSON messages.

    F21 (RunOverview/HILInbox/TicketStream) requires a typed envelope per channel
    so the React reducers / hook subscribers can run their happy paths against a
    real ASGI server. Until F18/F20 supply real broadcast hubs, ``initial_envelope``
    is sent immediately after the client's subscribe — preserving the F12 wire
    contract (kind + channel) while exposing a F21-aligned ``kind`` value.
    """
    await websocket.accept()
    try:
        # Wait for the client's subscribe message before pushing anything; the
        # integration tests send `{"kind":"subscribe","channel": <channel>}` and
        # expect a matching envelope back.
        msg = await websocket.receive_json()
        if initial_envelope is not None:
            envelope = {**initial_envelope, "channel": channel}
        else:
            envelope = {
                "kind": "subscribe_ack",
                "channel": channel,
                "echo": msg,
            }
        await websocket.send_json(envelope)
    except WebSocketDisconnect:
        return


# F21 IAPI-001 envelopes — minimal payloads sufficient for HilInboxPage /
# TicketStreamPage / RunOverviewPage initial render under the wire contract.
_F21_HIL_BOOTSTRAP = {
    "kind": "hil_question_opened",
    "payload": {
        "ticket_id": "t-bootstrap",
        "questions": [],
    },
}
_F21_STREAM_BOOTSTRAP = {
    "kind": "stream_event",
    "payload": {
        "seq": 0,
        "kind": "text",
        "payload": {"text": ""},
    },
}
_F21_RUN_BOOTSTRAP = {
    "kind": "run_phase_changed",
    "payload": {
        "phase": "design",
        "subprogress": None,
    },
}


@app.websocket("/ws/run/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str) -> None:
    await _ws_echo_channel(websocket, f"/ws/run/{run_id}", _F21_RUN_BOOTSTRAP)


@app.websocket("/ws/hil")
async def ws_hil(websocket: WebSocket) -> None:
    await _ws_echo_channel(websocket, "/ws/hil", _F21_HIL_BOOTSTRAP)


@app.websocket("/ws/stream/{ticket_id}")
async def ws_stream(websocket: WebSocket, ticket_id: str) -> None:
    await _ws_echo_channel(websocket, f"/ws/stream/{ticket_id}", _F21_STREAM_BOOTSTRAP)


@app.websocket("/ws/anomaly")
async def ws_anomaly(websocket: WebSocket) -> None:
    await _ws_echo_channel(websocket, "/ws/anomaly")


@app.websocket("/ws/signal")
async def ws_signal(websocket: WebSocket) -> None:
    await _ws_echo_channel(websocket, "/ws/signal")


# --------------------------------------------------------------------------- #
# F12 · StaticFiles mount (apps/ui/dist → /)
# --------------------------------------------------------------------------- #
# Registered last so `/api/*` + `/ws/*` routes match first. `html=True` enables
# SPA fallback (unknown paths return `index.html`). We gate on directory
# existence so a fresh clone without the built frontend still boots /api/*.

_UI_DIST = pathlib.Path(__file__).resolve().parents[2] / "apps" / "ui" / "dist"
if _UI_DIST.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(_UI_DIST), html=True),
        name="ui",
    )


__all__ = ["app"]
