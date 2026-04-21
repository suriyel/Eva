"""Recovery scanner (F02 · NFR-005 · Design §Interface Contract Recovery).

Invoked by F06 orchestrator on startup after a crash: for every ticket in
``run_id`` whose current state is in ``{running, classifying, hil_waiting}``
mark it as ``interrupted`` (DB + audit JSONL) and return the list of
``ticket_id`` values.
"""

from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite

from harness.domain.ticket import AuditEvent, TicketState
from harness.persistence.audit import AuditWriter
from harness.persistence.errors import DaoError
from harness.persistence.tickets import TicketRepository


def _utc_iso_micro() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


class RecoveryScanner:
    """Crash-restart scanner — one pass per ``run_id``."""

    def __init__(self, conn: aiosqlite.Connection, audit: AuditWriter) -> None:
        self._conn = conn
        self._audit = audit
        self._tickets = TicketRepository(conn)

    async def scan_and_mark_interrupted(self, run_id: str) -> list[str]:
        """Mark every unfinished ticket of ``run_id`` as ``interrupted``.

        Emits one audit event per ticket with the original ``state_from``
        preserved. Ticket-table update happens before the audit append, so a
        failed JSONL write does not roll back the DB state (Design §Design
        rationale: "DB 先提交后再 JSONL").
        """

        if not run_id:
            raise ValueError("run_id must be non-empty")

        unfinished = await self._tickets.list_unfinished(run_id)
        marked: list[str] = []

        try:
            for ticket in unfinished:
                from_state = ticket.state
                updated = await self._tickets.mark_interrupted(ticket.id)
                marked.append(updated.id)
                # Audit append happens after the DB commit — if it fails, the
                # ticket row is still authoritative, per Design rationale.
                await self._audit.append(
                    AuditEvent(
                        ts=_utc_iso_micro(),
                        ticket_id=updated.id,
                        run_id=run_id,
                        event_type="interrupted",
                        state_from=from_state,
                        state_to=TicketState.INTERRUPTED,
                    )
                )
        except Exception as exc:
            # Re-raise DAO/Io errors as DaoError to keep the scanner surface
            # tight for orchestrator callers (they already catch DaoError).
            if isinstance(exc, (DaoError,)):
                raise
            raise DaoError(f"recovery scan failed: {exc!r}") from exc

        return marked


__all__ = ["RecoveryScanner"]
