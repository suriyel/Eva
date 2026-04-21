"""SQLite schema bootstrap (F02 · Design §5.3).

``Schema.ensure`` is idempotent: re-running against an already-initialised
connection is a no-op (``CREATE TABLE IF NOT EXISTS`` + ``CREATE INDEX IF
NOT EXISTS``). PRAGMAs are re-asserted on every call so reconnecting to a
file DB still gets WAL / foreign_keys / busy_timeout.
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from harness.domain.ticket import TicketState
from harness.persistence.errors import DaoError


def resolve_db_path(workdir: Path) -> Path:
    """Return ``<workdir>/.harness/tickets.sqlite3`` (Design §5.5)."""

    return workdir / ".harness" / "tickets.sqlite3"


# ``runs.state`` enum (Design §5.3).
_RUNS_STATE_VALUES: tuple[str, ...] = (
    "idle",
    "starting",
    "running",
    "paused",
    "cancelled",
    "completed",
    "failed",
)


def _ticket_state_values() -> tuple[str, ...]:
    return tuple(s.value for s in TicketState)


def _quote_csv(values: tuple[str, ...]) -> str:
    return ",".join(f"'{v}'" for v in values)


class Schema:
    """Namespace for schema bootstrap."""

    @staticmethod
    async def ensure(conn: aiosqlite.Connection) -> None:
        """Apply PRAGMAs + CREATE TABLE/INDEX idempotently (Design §5.3)."""

        try:
            # PRAGMAs — re-assert on every connection.
            await conn.execute("PRAGMA journal_mode = WAL")
            await conn.execute("PRAGMA synchronous = NORMAL")
            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.execute("PRAGMA busy_timeout = 5000")

            runs_states_csv = _quote_csv(_RUNS_STATE_VALUES)
            ticket_states_csv = _quote_csv(_ticket_state_values())

            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS runs (
                    id               TEXT PRIMARY KEY,
                    workdir          TEXT NOT NULL,
                    state            TEXT NOT NULL CHECK(state IN ({runs_states_csv})),
                    current_phase    TEXT,
                    current_feature  TEXT,
                    cost_usd         REAL NOT NULL DEFAULT 0,
                    num_turns        INTEGER NOT NULL DEFAULT 0,
                    head_start       TEXT,
                    head_latest      TEXT,
                    started_at       TEXT NOT NULL,
                    ended_at         TEXT,
                    payload          TEXT NOT NULL DEFAULT '{{}}',
                    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_state ON runs(state)")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC)"
            )

            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS tickets (
                    id               TEXT PRIMARY KEY,
                    run_id           TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    parent_ticket    TEXT REFERENCES tickets(id),
                    depth            INTEGER NOT NULL DEFAULT 0 CHECK(depth BETWEEN 0 AND 2),
                    tool             TEXT NOT NULL CHECK(tool IN ('claude','opencode')),
                    skill_hint       TEXT,
                    state            TEXT NOT NULL CHECK(state IN ({ticket_states_csv})),
                    started_at       TEXT,
                    ended_at         TEXT,
                    exit_code        INTEGER,
                    cost_usd         REAL NOT NULL DEFAULT 0,
                    payload          TEXT NOT NULL,
                    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_run ON tickets(run_id)")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_run_state " "ON tickets(run_id, state)"
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_state ON tickets(state)")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_parent ON tickets(parent_ticket)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_tool_skill " "ON tickets(tool, skill_hint)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_started " "ON tickets(started_at DESC)"
            )
            await conn.commit()
        except Exception as exc:  # pragma: no cover — re-wrapped for callers.
            raise DaoError(f"schema bootstrap failed: {exc!r}") from exc


__all__ = ["Schema", "resolve_db_path"]
