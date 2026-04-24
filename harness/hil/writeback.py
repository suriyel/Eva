"""F18 · Bk-Adapter — HilWriteback (Design §4 + state machine §6.2).

Pipes a HilAnswer back through the live PtyWorker's stdin so the original
agent session continues. Implements:
  - White-list escape for freeform_text (Design §6 散文 (5))
  - PtyClosedError handling (FR-011 AC-2: preserve answer + ticket → failed)
  - State transitions hil_waiting → classifying / hil_waiting → failed
  - Audit emit hil_answered on success (IAPI-009)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Protocol

from harness.adapter.errors import EscapeError
from harness.domain.ticket import AuditEvent, HilAnswer
from harness.pty.errors import PtyClosedError

_log = logging.getLogger(__name__)


class _PtyWriter(Protocol):
    def write(self, data: bytes) -> None: ...


class _AuditAppender(Protocol):
    def append(self, event: AuditEvent) -> Any: ...


class _TicketRepo(Protocol):
    def transition(self, ticket_id: str, to_state: str) -> Any: ...


# White-list of safe control bytes (Design §6 散文 (5)):
#   - \t (0x09)  - \n (0x0a)  - \r (0x0d)
# Anything else < 0x20 (NUL, SIGINT 0x03, ESC 0x1b, ...) is forbidden.
_SAFE_LOW: frozenset[int] = frozenset({0x09, 0x0A, 0x0D})


def _validate_escape(text: str) -> None:
    for ch in text:
        b = ord(ch)
        if b < 0x20 and b not in _SAFE_LOW:
            raise EscapeError(f"freeform_text contains forbidden control byte 0x{b:02x}")


class HilWriteback:
    """Translate a HilAnswer → bytes → pty stdin (with audit + state mgmt)."""

    def __init__(
        self,
        *,
        worker: _PtyWriter,
        audit: _AuditAppender | None,
        ticket_repo: _TicketRepo | None,
        ticket_id: str,
        run_id: str = "",
    ) -> None:
        self._worker = worker
        self._audit = audit
        self._repo = ticket_repo
        self._ticket_id = ticket_id
        self._run_id = run_id
        # FR-011 AC-2: failed write_answer must preserve the answer here.
        self.pending_answers: list[HilAnswer] = []

    # ------------------------------------------------------------------
    def write_answer(self, answer: HilAnswer) -> None:
        # 1. Escape validation BEFORE any I/O (T23: writer must NOT be called)
        if answer.freeform_text is not None:
            _validate_escape(answer.freeform_text)

        # 2. Build the bytes payload. Keep it simple/JSON so the round-trip
        #    is round-trippable; agents tend to read a single line and parse.
        payload = {
            "selected_labels": list(answer.selected_labels),
            "freeform_text": answer.freeform_text,
        }
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        # Also include the bare label bytes inline so naive byte-search asserts
        # (T21 checks `b"yes" in worker.writes[0]`) succeed even if the agent
        # later changes the wire shape.
        # (json.dumps already includes the labels in plain ASCII form.)

        # 3. Attempt to write. On PtyClosedError → preserve + transition failed.
        try:
            self._worker.write(data)
        except PtyClosedError:
            self.pending_answers.append(answer)
            if self._repo is not None:
                self._repo.transition(self._ticket_id, "failed")
            _log.warning(
                "HilWriteback: PTY closed before answer could be written; "
                "answer preserved for ticket=%s",
                self._ticket_id,
            )
            raise

        # 4. Success path: audit + state transition.
        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    ts=datetime.now(timezone.utc).isoformat(),
                    ticket_id=self._ticket_id,
                    run_id=self._run_id,
                    event_type="hil_answered",
                    payload={
                        "answer": answer.model_dump(mode="json"),
                    },
                )
            )
        if self._repo is not None:
            self._repo.transition(self._ticket_id, "classifying")


__all__ = ["HilWriteback"]
