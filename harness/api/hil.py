"""F23 · /api/hil REST + /ws/hil WebSocket broadcaster."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from harness.domain.ticket import HilAnswer, TicketState


router = APIRouter()


class _AnswerBody(BaseModel):
    question_id: str
    selected_labels: list[str] = []
    freeform_text: str | None = None
    answered_at: str


@router.post("/api/hil/{ticket_id}/answer")
async def post_answer(ticket_id: str, request: Request) -> dict[str, Any]:
    raw = await request.json()
    try:
        body = _AnswerBody.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail={"error_code": "invalid_payload", "errors": exc.errors()}
        )

    repo = request.app.state.ticket_repo
    ticket = await repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail={"error_code": "ticket_not_found"})
    if ticket.state != TicketState.HIL_WAITING:
        raise HTTPException(status_code=409, detail={"error_code": "invalid_ticket_state"})

    bus = request.app.state.hil_event_bus
    answer = HilAnswer(
        question_id=body.question_id,
        selected_labels=body.selected_labels,
        freeform_text=body.freeform_text,
        answered_at=body.answered_at,
    )
    bus.publish_answered(ticket_id=ticket_id, run_id=ticket.run_id, answer=answer)
    return {"accepted": True, "ticket_state": "running"}


# ---------------------------------------------------------------------------
# /ws/hil
# ---------------------------------------------------------------------------
@router.websocket("/ws/hil")
async def ws_hil(websocket: WebSocket) -> None:
    await websocket.accept()
    state = websocket.app.state
    if not hasattr(state, "_hil_subs"):
        state._hil_subs = []
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
    state._hil_subs.append(q)
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
        try:
            state._hil_subs.remove(q)
        except ValueError:
            pass


__all__ = ["router"]
