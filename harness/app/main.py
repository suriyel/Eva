"""F20 · build_app — FastAPI factory wiring orchestrator REST/WS endpoints.

Used by T50 (real REST + WS integration). Production wiring keeps the
orchestrator in ``app.state.orchestrator`` so REST handlers can dispatch.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from harness.orchestrator.run import RunOrchestrator
from harness.orchestrator.schemas import RunStartRequest


class _StartReqBody(BaseModel):
    workdir: str


def build_app(*, workdir: Path) -> FastAPI:
    app = FastAPI(title="Harness Orchestrator")
    orch = RunOrchestrator.build_test_default(workdir=Path(workdir))
    app.state.orchestrator = orch

    # In-memory subscriber list for /ws/run/{id}
    subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    # Hook the bus's broadcast_run_event into our queue dispatch.
    original_broadcast = orch.control_bus.broadcast_run_event

    def _broadcast(event):  # type: ignore[no-untyped-def]
        original_broadcast(event)
        run_id = event.payload.get("run_id") if isinstance(event.payload, dict) else None
        if run_id is None:
            return
        envelope = {"kind": event.kind, "payload": event.payload}
        for q in subscribers.get(run_id, []):
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                pass

    orch.control_bus.broadcast_run_event = _broadcast  # type: ignore[method-assign]

    @app.post("/api/runs/start")
    async def start_run_endpoint(body: _StartReqBody) -> dict[str, Any]:
        status = await orch.start_run(RunStartRequest(workdir=body.workdir))
        return status.model_dump()

    @app.websocket("/ws/run/{run_id}")
    async def ws_run(ws: WebSocket, run_id: str) -> None:
        await ws.accept()
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        subscribers.setdefault(run_id, []).append(q)
        # Replay recent events for the new subscriber
        for evt in orch.control_bus.captured_run_events():
            if evt.payload.get("run_id") == run_id:
                try:
                    q.put_nowait({"kind": evt.kind, "payload": evt.payload})
                except asyncio.QueueFull:
                    pass
        try:
            while True:
                envelope = await q.get()
                await ws.send_text(json.dumps(envelope, ensure_ascii=False))
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            try:
                subscribers[run_id].remove(q)
            except (KeyError, ValueError):
                pass

    return app


__all__ = ["build_app"]
