"""F23 · /api/anomaly REST + /ws/anomaly WebSocket broadcaster."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from harness.orchestrator.bus import AnomalyEvent
from harness.orchestrator.errors import InvalidTicketState, TicketNotFound
from harness.orchestrator.schemas import RecoveryDecision


router = APIRouter()


@router.post("/api/anomaly/{ticket_id}/skip")
async def post_skip(ticket_id: str, request: Request) -> dict[str, Any]:
    if not ticket_id.strip():
        raise HTTPException(
            status_code=400, detail={"error_code": "invalid_param", "field": "ticket_id"}
        )
    orch = request.app.state.orchestrator
    try:
        decision: RecoveryDecision = await orch.skip_anomaly(ticket_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail={"error_code": "ticket_not_found"})
    except InvalidTicketState:
        raise HTTPException(status_code=409, detail={"error_code": "invalid_ticket_state"})
    return decision.model_dump()


@router.post("/api/anomaly/{ticket_id}/force-abort")
async def post_force_abort(ticket_id: str, request: Request) -> dict[str, Any]:
    if not ticket_id.strip():
        raise HTTPException(
            status_code=400, detail={"error_code": "invalid_param", "field": "ticket_id"}
        )
    orch = request.app.state.orchestrator
    try:
        decision: RecoveryDecision = await orch.force_abort_anomaly(ticket_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail={"error_code": "ticket_not_found"})
    except InvalidTicketState:
        raise HTTPException(status_code=409, detail={"error_code": "invalid_ticket_state"})
    return decision.model_dump()


@router.post("/api/anomaly/_test/inject")
async def post_test_inject_anomaly(request: Request) -> dict[str, Any]:
    """Test-only hook used by the F23 real-uvicorn handshake suite (R24)."""
    raw = await request.json()
    bus = request.app.state.run_control_bus
    bus.broadcast_anomaly(
        AnomalyEvent(
            kind="AnomalyDetected",
            cls=raw.get("cls"),
            ticket_id=raw.get("ticket_id"),
            retry_count=int(raw.get("retry_count") or 0),
        )
    )
    return {"ok": True}


@router.post("/api/_test/stream-inject")
async def post_test_inject_stream(request: Request) -> dict[str, Any]:
    """Test-only hook for /ws/stream/{tid} broadcaster (R26)."""
    raw = await request.json()
    bus = request.app.state.run_control_bus
    bus.broadcast_stream_event(
        {
            "ticket_id": raw.get("ticket_id"),
            "seq": int(raw.get("seq") or 0),
            "ts": raw.get("ts", ""),
            "kind": raw.get("kind", "text"),
            "payload": raw.get("payload", {}),
        }
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# /ws/anomaly
# ---------------------------------------------------------------------------
@router.websocket("/ws/anomaly")
async def ws_anomaly(websocket: WebSocket) -> None:
    await websocket.accept()
    bus = getattr(websocket.app.state, "run_control_bus", None)
    if bus is None:
        await websocket.close(code=1011)
        return
    q = bus.subscribe_anomaly()
    # Replay captured anomaly events.
    for evt in bus.captured_anomaly_events():
        try:
            q.put_nowait(
                {
                    "kind": evt.kind,
                    "payload": {
                        "ticket_id": evt.ticket_id,
                        "cls": evt.cls,
                        "reason": evt.reason,
                        "retry_count": evt.retry_count,
                    },
                }
            )
        except Exception:
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
        bus.unsubscribe_anomaly(q)


__all__ = ["router"]
