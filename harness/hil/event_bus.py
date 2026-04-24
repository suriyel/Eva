"""F18 · Bk-Adapter — HilEventBus (Design §4 rows publish_opened / publish_answered).

Bridges captured HIL events to:
  - WebSocket /ws/hil broadcast (callable injected by F21 hub owner)
  - AuditWriter.append (IAPI-009 Provider; F02 already passing)

The bus does NOT own a FastAPI WebSocket — Implementation Summary explicitly
keeps the layering clean by accepting a broadcast callable.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from harness.domain.ticket import AuditEvent, HilAnswer, HilQuestion


class _AuditAppender(Protocol):
    """Structural protocol covering both AuditWriter (async) and test fakes (sync)."""

    def append(self, event: AuditEvent) -> Any: ...


class HilEventBus:
    """Emit hil_captured / hil_answered to UI broadcast + audit log."""

    def __init__(
        self,
        ws_broadcast: Callable[[dict[str, Any]], None] | None = None,
        audit: _AuditAppender | None = None,
    ) -> None:
        self._ws_broadcast = ws_broadcast
        self._audit = audit

    # ------------------------------------------------------------------
    def publish_opened(self, *, ticket_id: str, run_id: str, question: HilQuestion) -> None:
        """Fire HilQuestionOpened: append AuditEvent + broadcast to /ws/hil."""
        payload = {
            "ticket_id": ticket_id,
            "run_id": run_id,
            "question": question.model_dump(mode="json"),
            # Keep both keys so loose consumers ('questions' / 'question') match.
            "questions": [question.model_dump(mode="json")],
        }
        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    ts=_now_iso(),
                    ticket_id=ticket_id,
                    run_id=run_id,
                    event_type="hil_captured",
                    payload=payload,
                )
            )
        if self._ws_broadcast is not None:
            self._ws_broadcast(payload)

    # ------------------------------------------------------------------
    def publish_answered(self, *, ticket_id: str, run_id: str, answer: HilAnswer) -> None:
        payload = {
            "ticket_id": ticket_id,
            "run_id": run_id,
            "answer": answer.model_dump(mode="json"),
        }
        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    ts=_now_iso(),
                    ticket_id=ticket_id,
                    run_id=run_id,
                    event_type="hil_answered",
                    payload=payload,
                )
            )
        if self._ws_broadcast is not None:
            self._ws_broadcast(payload)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["HilEventBus"]
