"""F18 Wave 4 · HookEventToStreamMapper + SessionEnd handler.

Per Design §Interface Contract HookEventToStreamMapper.map + Test T34 +
Design rationale (e) (FR-014 replacement logic).

kind derivation matrix (Interface Contract row):
  - SessionStart / SessionEnd → "system"
  - PreToolUse + tool_name in {AskUserQuestion, Question} → "tool_use"
  - PreToolUse + other tools → "tool_use"
  - PostToolUse → "tool_result"
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from harness.adapter import HookEventPayload


TicketStreamKind = Literal["text", "tool_use", "tool_result", "thinking", "error", "system"]


class TicketStreamEvent(BaseModel):
    """Wire-layer envelope (alias of legacy StreamEvent)."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    seq: int
    ts: str
    kind: TicketStreamKind
    payload: dict[str, Any] = Field(default_factory=dict)


class HookEventToStreamMapper:
    """Map a HookEventPayload to a TicketStreamEvent."""

    def map(
        self, payload: HookEventPayload, ticket_id: str, seq: int
    ) -> TicketStreamEvent:
        hook_event = payload.hook_event_name
        if hook_event in ("SessionStart", "SessionEnd"):
            kind: TicketStreamKind = "system"
        elif hook_event == "PreToolUse":
            kind = "tool_use"
        elif hook_event == "PostToolUse":
            kind = "tool_result"
        else:  # pragma: no cover — pydantic Literal protects us
            kind = "system"

        # Strip nothing: payload dict carries the original hook event fields.
        data = payload.model_dump()
        return TicketStreamEvent(
            ticket_id=ticket_id,
            seq=seq,
            ts=str(payload.ts),
            kind=kind,
            payload=data,
        )


def resolve_session_end_state(
    payload: HookEventPayload,
    bus: Any,
    *,
    current_state: str,
) -> str:
    """Decide ticket state on SessionEnd.

    FR-014 replacement logic (Design rationale (e)):
      - If bus.tool_use_id_queue still has unanswered tool_use_ids → keep
        ticket in ``hil_waiting`` (terminate-coordination postponed).
      - Otherwise → ``completed``.
    """
    if payload.hook_event_name != "SessionEnd":
        return current_state
    queue = getattr(bus, "tool_use_id_queue", None)
    if queue is not None:
        try:
            pending = list(queue)
        except TypeError:
            pending = []
        if pending:
            return "hil_waiting"
    return "completed"


__all__ = [
    "HookEventToStreamMapper",
    "TicketStreamEvent",
    "TicketStreamKind",
    "resolve_session_end_state",
]
