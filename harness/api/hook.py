"""F18 Wave 4 · POST /api/hook/event router (IAPI-020).

Per Design §Interface Contract HookRouter.post_hook_event + Implementation
Summary §3 hook bridge.

Behaviour:
  1. content-type must be ``application/json`` → else 415
  2. Body validated against ``HookEventPayload`` pydantic schema → else 422
  3. Adapter chosen from ``request.app.state.adapter_registry`` ("claude" by
     default) → ``map_hook_event(payload)`` → HilQuestion[]
  4. For HIL events: ``HilEventBus.publish_opened`` (or queue tool_use_id)
  5. Always: ``HookEventToStreamMapper.map`` → ``ticket_stream_broadcaster.publish``
  6. Returns ``{"accepted": True}`` on success.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from harness.adapter import HookEventPayload
from harness.orchestrator.hook_to_stream import HookEventToStreamMapper

_log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/hook/event")
async def post_hook_event(request: Request) -> dict[str, Any]:
    """Receive hook stdin JSON from claude TUI bridge → fan-out HIL + stream."""
    # 1. content-type check (IFR-001 AC-w4-2: 415 on wrong content-type)
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if content_type != "application/json":
        raise HTTPException(
            status_code=415,
            detail={"error_code": "unsupported-media-type", "got": content_type},
        )

    # 2. parse + pydantic validate (IFR-001 AC-w4-2: 422 on schema mismatch)
    try:
        raw = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "invalid-json", "message": str(exc)},
        )
    try:
        payload = HookEventPayload.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    state = request.app.state

    # 3. adapter dispatch
    registry = getattr(state, "adapter_registry", {}) or {}
    adapter = registry.get("claude")
    questions = []
    if adapter is not None and hasattr(adapter, "map_hook_event"):
        try:
            questions = adapter.map_hook_event(payload)
        except Exception:  # noqa: BLE001 — adapter must not propagate (FR-009)
            _log.exception("adapter.map_hook_event raised; treating as no-questions")
            questions = []

    # 4. HIL fan-out
    bus = getattr(state, "hil_event_bus", None)
    ticket_id = _resolve_ticket_id(state, payload)
    run_id = _resolve_run_id(state, payload)
    if bus is not None:
        if questions:
            for q in questions:
                try:
                    bus.publish_opened(ticket_id=ticket_id, run_id=run_id, question=q)
                except Exception:  # noqa: BLE001
                    _log.exception("HilEventBus.publish_opened raised")
            # Track tool_use_id for FR-014 replacement logic.
            if hasattr(bus, "tool_use_id_queue") and payload.tool_use_id:
                bus.tool_use_id_queue.append(payload.tool_use_id)
        else:
            # Non-HIL tools still touch the queue so SessionEnd reasoning
            # has the lifecycle anchor when needed.
            if (
                payload.hook_event_name == "PreToolUse"
                and hasattr(bus, "tool_use_id_queue")
                and payload.tool_use_id
            ):
                bus.tool_use_id_queue.append(payload.tool_use_id)

    # 5. Stream broadcast
    bcast = getattr(state, "ticket_stream_broadcaster", None)
    if bcast is not None:
        seq = _next_seq(state, ticket_id)
        try:
            event = HookEventToStreamMapper().map(payload, ticket_id=ticket_id, seq=seq)
            bcast.publish(event)
        except Exception:  # noqa: BLE001
            _log.exception("ticket_stream_broadcaster.publish raised")

    return {"accepted": True}


def _resolve_ticket_id(state: Any, payload: HookEventPayload) -> str:
    mapping = getattr(state, "ticket_id_for_session", None)
    if isinstance(mapping, dict):
        tid = mapping.get(payload.session_id)
        if isinstance(tid, str):
            return tid
    return payload.session_id


def _resolve_run_id(state: Any, payload: HookEventPayload) -> str:
    mapping = getattr(state, "run_id_for_session", None)
    if isinstance(mapping, dict):
        rid = mapping.get(payload.session_id)
        if isinstance(rid, str):
            return rid
    return payload.session_id


def _next_seq(state: Any, ticket_id: str) -> int:
    counters = getattr(state, "_hook_event_seq", None)
    if not isinstance(counters, dict):
        counters = {}
        state._hook_event_seq = counters
    counters[ticket_id] = counters.get(ticket_id, 0) + 1
    return counters[ticket_id]


__all__ = ["router"]
