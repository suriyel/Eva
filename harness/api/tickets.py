"""F23 · /api/tickets REST routes + /ws/stream WebSocket broadcaster."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect


router = APIRouter()


@router.get("/api/tickets")
async def get_tickets(
    request: Request,
    run_id: str | None = Query(default=None),
    state: str | None = Query(default=None),
    tool: str | None = Query(default=None),
    parent: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    repo = request.app.state.ticket_repo
    if not run_id:
        raise HTTPException(
            status_code=400, detail={"error_code": "invalid_param", "field": "run_id"}
        )
    rows = await repo.list_by_run(run_id, state=None, tool=tool, parent=parent)
    if state:
        rows = [t for t in rows if t.state.value == state]
    return [t.model_dump(mode="json") for t in rows]


@router.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, request: Request) -> dict[str, Any]:
    repo = request.app.state.ticket_repo
    row = await repo.get(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error_code": "ticket_not_found"})
    return cast(dict[str, Any], row.model_dump(mode="json"))


@router.get("/api/tickets/{ticket_id}/stream")
async def get_ticket_stream(
    ticket_id: str,
    request: Request,
    offset: int = Query(default=0),
) -> list[dict[str, Any]]:
    if offset < 0:
        raise HTTPException(
            status_code=400, detail={"error_code": "invalid_param", "field": "offset"}
        )
    repo = request.app.state.ticket_repo
    row = await repo.get(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error_code": "ticket_not_found"})
    orch = request.app.state.orchestrator
    events = orch.stream_events_for(ticket_id) if hasattr(orch, "stream_events_for") else []
    events = [e for e in events if e.get("seq", 0) >= offset]
    events.sort(key=lambda e: e.get("seq", 0))
    return events


# ---------------------------------------------------------------------------
# /ws/stream/{ticket_id}
# ---------------------------------------------------------------------------
@router.websocket("/ws/stream/{ticket_id}")
async def ws_stream(websocket: WebSocket, ticket_id: str) -> None:
    """Subscribe to broadcast_stream_event for this ticket_id."""
    await websocket.accept()
    bus = getattr(websocket.app.state, "run_control_bus", None)
    if bus is None:
        await websocket.close(code=1011)
        return
    q = bus.subscribe_stream(ticket_id)
    # Replay captured stream events for this ticket.
    for evt in bus.captured_stream_events():
        if evt.get("ticket_id") == ticket_id:
            try:
                q.put_nowait({"kind": "StreamEvent", "payload": evt})
            except asyncio.QueueFull:
                pass
    try:
        while True:
            envelope = await q.get()
            await websocket.send_json(envelope)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        bus.unsubscribe_stream(ticket_id, q)


__all__ = ["router"]
