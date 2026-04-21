"""TicketRepository (F02 · IAPI-011 · Design §4.2 / §5.3 / §5.4).

Implements the five methods in the feature-design contract:
``save`` (UPSERT), ``get``, ``list_by_run``, ``list_unfinished``,
``mark_interrupted``.

Key invariants:

- Columns ``state / started_at / ended_at / exit_code / cost_usd`` are a
  reflective projection of :class:`Ticket`; ``payload`` stores the full
  pydantic-serialised JSON for FR-007 AC-1 ``None-vs-absent`` fidelity.
- ``save`` uses ``INSERT ... ON CONFLICT(id) DO UPDATE SET ...`` so
  concurrent saves on the same id merge rather than overwrite wholesale
  (Row R: state then anomaly both survive).
- ``mark_interrupted`` validates the current DB state against
  :const:`INTERRUPTIBLE_SOURCE_STATES` and raises :class:`TransitionError`
  for terminal sources (Row J).
- ``list_by_run("")`` raises :class:`ValueError` up-front (Row O).
"""

from __future__ import annotations

import json
from typing import Any, Literal

import aiosqlite

from harness.domain.state_machine import (
    INTERRUPTIBLE_SOURCE_STATES,
    TicketNotFoundError,
    TransitionError,
)
from harness.domain.ticket import Ticket, TicketState
from harness.persistence.errors import DaoError


_UNFINISHED_STATES: tuple[str, ...] = ("running", "classifying", "hil_waiting")


class TicketRepository:
    """CRUD + state-machine UPSERT over the ``tickets`` table."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # save (UPSERT)
    # ------------------------------------------------------------------
    async def save(self, ticket: Ticket) -> None:
        """INSERT or UPDATE a ticket row; refresh ``updated_at``.

        See Design §Interface Contract row ``save`` and Impl Summary decision
        1 (column + payload must agree).
        """

        payload_json = json.dumps(
            ticket.model_dump(mode="json"),
            ensure_ascii=False,
        )
        params = (
            ticket.id,
            ticket.run_id,
            ticket.parent_ticket,
            ticket.depth,
            ticket.tool,
            ticket.skill_hint,
            ticket.state.value,
            ticket.execution.started_at,
            ticket.execution.ended_at,
            ticket.execution.exit_code,
            ticket.execution.cost_usd,
            payload_json,
        )
        try:
            await self._conn.execute(
                """
                INSERT INTO tickets (
                    id, run_id, parent_ticket, depth, tool, skill_hint,
                    state, started_at, ended_at, exit_code, cost_usd, payload
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    run_id        = excluded.run_id,
                    parent_ticket = excluded.parent_ticket,
                    depth         = excluded.depth,
                    tool          = excluded.tool,
                    skill_hint    = excluded.skill_hint,
                    state         = excluded.state,
                    started_at    = excluded.started_at,
                    ended_at      = excluded.ended_at,
                    exit_code     = excluded.exit_code,
                    cost_usd      = excluded.cost_usd,
                    payload       = excluded.payload,
                    updated_at    = datetime('now')
                """,
                params,
            )
            await self._conn.commit()
        except ValueError:
            # Propagate pydantic-style defensive ValueError untouched.
            raise
        except Exception as exc:
            raise DaoError(f"ticket save failed: {exc!r}") from exc

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------
    async def get(self, ticket_id: str) -> Ticket | None:
        if not isinstance(ticket_id, str) or not ticket_id:
            # Defensive: treat as miss rather than SQL noop with '' predicate.
            return None
        try:
            async with self._conn.execute(
                "SELECT payload FROM tickets WHERE id = ?", (ticket_id,)
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                return None
            return _row_to_ticket(row)
        except Exception as exc:
            raise DaoError(f"ticket get failed: {exc!r}") from exc

    # ------------------------------------------------------------------
    # list_by_run
    # ------------------------------------------------------------------
    async def list_by_run(
        self,
        run_id: str,
        *,
        state: TicketState | None = None,
        tool: Literal["claude", "opencode"] | None = None,
        parent: str | None = None,
    ) -> list[Ticket]:
        if not isinstance(run_id, str) or run_id == "":
            raise ValueError("run_id must be a non-empty string")

        sql_parts = ["SELECT payload FROM tickets WHERE run_id = ?"]
        params: list[Any] = [run_id]
        if state is not None:
            sql_parts.append("AND state = ?")
            params.append(state.value)
        if tool is not None:
            sql_parts.append("AND tool = ?")
            params.append(tool)
        if parent is not None:
            sql_parts.append("AND parent_ticket = ?")
            params.append(parent)
        sql_parts.append(
            "ORDER BY CASE WHEN started_at IS NULL THEN 1 ELSE 0 END, " "started_at ASC, id ASC"
        )
        sql = " ".join(sql_parts)
        try:
            async with self._conn.execute(sql, params) as cur:
                rows = await cur.fetchall()
            return [_row_to_ticket(r) for r in rows]
        except Exception as exc:
            raise DaoError(f"ticket list_by_run failed: {exc!r}") from exc

    # ------------------------------------------------------------------
    # list_unfinished
    # ------------------------------------------------------------------
    async def list_unfinished(self, run_id: str) -> list[Ticket]:
        if not isinstance(run_id, str) or run_id == "":
            raise ValueError("run_id must be a non-empty string")
        placeholders = ",".join("?" for _ in _UNFINISHED_STATES)
        sql = (
            f"SELECT payload FROM tickets "
            f"WHERE run_id = ? AND state IN ({placeholders}) "
            f"ORDER BY CASE WHEN started_at IS NULL THEN 1 ELSE 0 END, "
            f"started_at ASC, id ASC"
        )
        params: list[Any] = [run_id, *_UNFINISHED_STATES]
        try:
            async with self._conn.execute(sql, params) as cur:
                rows = await cur.fetchall()
            return [_row_to_ticket(r) for r in rows]
        except Exception as exc:
            raise DaoError(f"ticket list_unfinished failed: {exc!r}") from exc

    # ------------------------------------------------------------------
    # mark_interrupted
    # ------------------------------------------------------------------
    async def mark_interrupted(self, ticket_id: str) -> Ticket:
        try:
            async with self._conn.execute(
                "SELECT payload, state FROM tickets WHERE id = ?", (ticket_id,)
            ) as cur:
                row = await cur.fetchone()
        except Exception as exc:
            raise DaoError(f"ticket lookup failed: {exc!r}") from exc

        if row is None:
            raise TicketNotFoundError(ticket_id)

        current_state = row["state"]
        if current_state not in INTERRUPTIBLE_SOURCE_STATES:
            from_state = TicketState(current_state)
            raise TransitionError(from_state, TicketState.INTERRUPTED)

        ticket = _row_to_ticket(row)
        ticket_dict = ticket.model_dump(mode="json")
        ticket_dict["state"] = TicketState.INTERRUPTED.value
        updated = Ticket.model_validate(ticket_dict)
        try:
            new_payload_json = json.dumps(updated.model_dump(mode="json"), ensure_ascii=False)
            await self._conn.execute(
                """
                UPDATE tickets
                   SET state      = ?,
                       payload    = ?,
                       updated_at = datetime('now')
                 WHERE id = ?
                """,
                (TicketState.INTERRUPTED.value, new_payload_json, ticket_id),
            )
            await self._conn.commit()
        except Exception as exc:
            raise DaoError(f"ticket mark_interrupted failed: {exc!r}") from exc

        return updated


def _row_to_ticket(row: Any) -> Ticket:
    """Reconstruct a :class:`Ticket` from a ``payload`` column."""

    payload_raw = row["payload"]
    try:
        data = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        raise DaoError(f"ticket payload json invalid: {exc!r}") from exc
    try:
        return Ticket.model_validate(data)
    except Exception as exc:
        raise DaoError(f"ticket payload schema drift: {exc!r}") from exc


__all__ = ["TicketRepository"]
