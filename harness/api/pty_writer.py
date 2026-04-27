"""F18 Wave 4 · POST /api/pty/write router (IAPI-021).

Per Design §Interface Contract PtyWriterRouter.post_pty_write.

Behaviour:
  1. body validated against ``PtyWriteRequest`` pydantic schema
  2. base64 decode payload → bytes
  3. ticket lookup via ``request.app.state.ticket_repo.get(ticket_id)``
  4. ticket.state ∈ {running, hil_waiting} else 400 ticket-not-running
  5. ticket.worker.write(decoded) — PtyClosedError → 400 ticket-not-running
  6. returns ``{"written_bytes": int}``

Errors:
  - 400 ticket-not-running   (state ∉ {running, hil_waiting})
  - 400 b64-decode-error     (invalid base64 payload)
  - 404 ticket-not-found     (repo.get → None)
"""

from __future__ import annotations

import base64
import binascii
import inspect
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from harness.pty.errors import PtyClosedError

_log = logging.getLogger(__name__)

router = APIRouter()

_RUNNABLE_STATES: frozenset[str] = frozenset({"running", "hil_waiting"})


class PtyWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    payload: str  # base64-encoded bytes


@router.post("/api/pty/write")
async def post_pty_write(request: Request) -> dict[str, int]:
    body = await request.json()
    req = PtyWriteRequest.model_validate(body)

    repo = getattr(request.app.state, "ticket_repo", None)
    if repo is None:
        raise HTTPException(status_code=500, detail={"error_code": "ticket-repo-missing"})

    ticket = repo.get(req.ticket_id)
    if inspect.isawaitable(ticket):
        ticket = await ticket
    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "ticket-not-found", "ticket_id": req.ticket_id},
        )

    state = _ticket_state_str(ticket)
    if state not in _RUNNABLE_STATES:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "ticket-not-running",
                "ticket_id": req.ticket_id,
                "state": state,
            },
        )

    try:
        decoded = base64.b64decode(req.payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "b64-decode-error", "message": str(exc)},
        )

    worker = getattr(ticket, "worker", None)
    if worker is None or not hasattr(worker, "write"):
        raise HTTPException(
            status_code=400,
            detail={"error_code": "ticket-not-running", "reason": "no-pty-worker"},
        )

    try:
        worker.write(decoded)
    except PtyClosedError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "ticket-not-running", "reason": "pty-closed", "message": str(exc)},
        )

    return {"written_bytes": len(decoded)}


def _ticket_state_str(ticket: object) -> str:
    state = getattr(ticket, "state", None)
    if state is None:
        return ""
    if hasattr(state, "value"):  # TicketState enum
        return str(state.value)
    return str(state)


__all__ = ["router", "PtyWriteRequest"]
