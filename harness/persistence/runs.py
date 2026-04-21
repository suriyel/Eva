"""RunRepository (F02 · Design §4.2/§5.3).

Internal helper consumed by F06 orchestrator and by
:class:`TicketRepository` tests for FK setup. Not a cross-feature contract.
"""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from harness.domain.state_machine import RunNotFoundError
from harness.domain.ticket import Run, RunStateLiteral
from harness.persistence.errors import DaoError


_LIMIT_MIN = 1
_LIMIT_MAX = 100


class RunRepository:
    """CRUD helpers for the ``runs`` table."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, run: Run) -> None:
        """Insert a fresh run row (Design §4.2 RunRepository.create)."""

        try:
            await self._conn.execute(
                """
                INSERT INTO runs (
                    id, workdir, state, current_phase, current_feature,
                    cost_usd, num_turns, head_start, head_latest,
                    started_at, ended_at, payload
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run.id,
                    run.workdir,
                    run.state,
                    run.current_phase,
                    run.current_feature,
                    run.cost_usd,
                    run.num_turns,
                    run.head_start,
                    run.head_latest,
                    run.started_at,
                    run.ended_at,
                    json.dumps(run.payload, ensure_ascii=False),
                ),
            )
            await self._conn.commit()
        except Exception as exc:
            raise DaoError(f"run create failed: {exc!r}") from exc

    async def update(
        self,
        run_id: str,
        *,
        state: RunStateLiteral | None = None,
        current_phase: str | None = None,
        current_feature: str | None = None,
        cost_usd_delta: float = 0.0,
        num_turns_delta: int = 0,
        head_latest: str | None = None,
        ended_at: str | None = None,
    ) -> None:
        if not run_id:
            raise ValueError("run_id must be non-empty")

        existing = await self.get(run_id)
        if existing is None:
            raise RunNotFoundError(run_id)

        sets: list[str] = []
        params: list[Any] = []
        if state is not None:
            sets.append("state = ?")
            params.append(state)
        if current_phase is not None:
            sets.append("current_phase = ?")
            params.append(current_phase)
        if current_feature is not None:
            sets.append("current_feature = ?")
            params.append(current_feature)
        if cost_usd_delta:
            sets.append("cost_usd = cost_usd + ?")
            params.append(cost_usd_delta)
        if num_turns_delta:
            sets.append("num_turns = num_turns + ?")
            params.append(num_turns_delta)
        if head_latest is not None:
            sets.append("head_latest = ?")
            params.append(head_latest)
        if ended_at is not None:
            sets.append("ended_at = ?")
            params.append(ended_at)

        sets.append("updated_at = datetime('now')")
        params.append(run_id)
        sql = f"UPDATE runs SET {', '.join(sets)} WHERE id = ?"
        try:
            await self._conn.execute(sql, params)
            await self._conn.commit()
        except Exception as exc:
            raise DaoError(f"run update failed: {exc!r}") from exc

    async def get(self, run_id: str) -> Run | None:
        try:
            async with self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)) as cur:
                row = await cur.fetchone()
            if row is None:
                return None
            return _row_to_run(row)
        except Exception as exc:
            raise DaoError(f"run get failed: {exc!r}") from exc

    async def list_recent(self, *, limit: int = 20, offset: int = 0) -> list[Run]:
        if not isinstance(limit, int) or limit < _LIMIT_MIN or limit > _LIMIT_MAX:
            raise ValueError(f"limit must be in [{_LIMIT_MIN}, {_LIMIT_MAX}]; got {limit!r}")
        if offset < 0:
            raise ValueError(f"offset must be >= 0; got {offset!r}")

        try:
            async with self._conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ) as cur:
                rows = await cur.fetchall()
            return [_row_to_run(r) for r in rows]
        except Exception as exc:
            raise DaoError(f"run list_recent failed: {exc!r}") from exc


def _row_to_run(row: Any) -> Run:
    payload_raw = row["payload"] if _has_key(row, "payload") else "{}"
    try:
        payload_dict = json.loads(payload_raw) if payload_raw else {}
    except json.JSONDecodeError as exc:
        raise DaoError(f"run payload json invalid: {exc!r}") from exc

    return Run(
        id=row["id"],
        workdir=row["workdir"],
        state=row["state"],
        current_phase=row["current_phase"],
        current_feature=row["current_feature"],
        cost_usd=row["cost_usd"],
        num_turns=row["num_turns"],
        head_start=row["head_start"],
        head_latest=row["head_latest"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        payload=payload_dict,
    )


def _has_key(row: Any, key: str) -> bool:
    try:
        _ = row[key]
        return True
    except (IndexError, KeyError):
        return False


__all__ = ["RunRepository"]
