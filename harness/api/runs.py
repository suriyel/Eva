"""F23 · /api/runs REST routes + /ws/run WebSocket broadcaster.

Routes:
    GET  /api/runs/current
    GET  /api/runs?limit=&offset=
    POST /api/runs/start
    POST /api/runs/{run_id}/pause
    POST /api/runs/{run_id}/cancel

    WebSocket /ws/run/{run_id}
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from harness.orchestrator.errors import (
    RunNotFound,
    RunStartError,
)
from harness.orchestrator.schemas import RunStartRequest, RunStatus


router = APIRouter()


@router.get("/api/runs/current")
async def get_runs_current(request: Request) -> Any:
    orch = request.app.state.orchestrator
    rows = await orch.run_repo.list_active()
    if not rows:
        return None
    run = rows[0]
    return {
        "run_id": run.id,
        "state": run.state,
        "workdir": run.workdir,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
    }


@router.get("/api/runs")
async def get_runs(
    request: Request,
    limit: int = Query(50),
    offset: int = Query(0),
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=400, detail={"error_code": "invalid_param", "field": "limit"}
        )
    if offset < 0:
        raise HTTPException(
            status_code=400, detail={"error_code": "invalid_param", "field": "offset"}
        )
    orch = request.app.state.orchestrator
    repo = orch.run_repo
    list_recent = getattr(repo, "list_recent", None)
    if list_recent is None:
        rows = await repo.list_active()
    else:
        rows = await list_recent(limit=limit, offset=offset)
    return [
        {
            "run_id": r.id,
            "state": r.state,
            "workdir": r.workdir,
            "started_at": r.started_at,
            "ended_at": r.ended_at,
        }
        for r in rows
    ]


@router.post("/api/runs/start")
async def post_start_run(request: Request) -> dict[str, Any]:
    raw = await request.json()
    try:
        body = RunStartRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_workdir", "errors": exc.errors()},
        )
    orch = request.app.state.orchestrator
    try:
        status: RunStatus = await orch.start_run(body)
    except RunStartError as exc:
        raise HTTPException(
            status_code=getattr(exc, "http_status", 400),
            detail={
                "error_code": exc.reason,
                "message": str(exc),
            },
        )
    return status.model_dump()


@router.post("/api/runs/{run_id}/pause")
async def post_pause(run_id: str, request: Request) -> dict[str, Any]:
    orch = request.app.state.orchestrator
    try:
        status: RunStatus = await orch.pause_run(run_id)
    except RunNotFound as exc:
        raise HTTPException(
            status_code=404, detail={"error_code": "run_not_found", "run_id": exc.run_id}
        )
    return status.model_dump()


@router.post("/api/runs/{run_id}/cancel")
async def post_cancel(run_id: str, request: Request) -> dict[str, Any]:
    orch = request.app.state.orchestrator
    try:
        status: RunStatus = await orch.cancel_run(run_id)
    except RunNotFound as exc:
        raise HTTPException(
            status_code=404, detail={"error_code": "run_not_found", "run_id": exc.run_id}
        )
    return status.model_dump()


# ---------------------------------------------------------------------------
# /ws/run/{run_id}
# ---------------------------------------------------------------------------
@router.websocket("/ws/run/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str) -> None:
    """Subscribe to RunControlBus run events filtered by run_id.

    Replays previously captured events whose payload.run_id matches, then
    streams future events; emits ``{"kind": "ping"}`` heartbeats every
    ``HARNESS_WS_PING_INTERVAL_SEC`` (default 30s) for IFR-007 reconnect.
    """
    await websocket.accept()
    bus = getattr(websocket.app.state, "run_control_bus", None)
    if bus is None:
        await websocket.close(code=1011)
        return
    q = bus.subscribe_run()
    # Replay
    for evt in bus.captured_run_events():
        payload = evt.payload if isinstance(evt.payload, dict) else {}
        if payload.get("run_id") == run_id:
            try:
                q.put_nowait({"kind": evt.kind, "payload": payload})
            except asyncio.QueueFull:
                pass
    try:
        while True:
            sender = asyncio.create_task(_send_loop(websocket, q, run_id))
            pinger = asyncio.create_task(_ping_loop(websocket))
            done, pending = await asyncio.wait(
                {sender, pinger}, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            for t in done:
                exc = t.exception()
                if exc is not None:
                    raise exc
            return
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        bus.unsubscribe_run(q)


async def _send_loop(websocket: WebSocket, q: asyncio.Queue[dict[str, Any]], run_id: str) -> None:
    while True:
        envelope = await q.get()
        payload = envelope.get("payload")
        if isinstance(payload, dict) and payload.get("run_id") not in (None, run_id):
            # Skip events that target a different run.
            continue
        await websocket.send_json(envelope)


async def _ping_loop(websocket: WebSocket) -> None:
    interval = float(os.environ.get("HARNESS_WS_PING_INTERVAL_SEC", "30"))
    while True:
        await asyncio.sleep(interval)
        try:
            await websocket.send_json({"kind": "ping", "payload": {}})
        except Exception:
            return


__all__ = ["router"]
