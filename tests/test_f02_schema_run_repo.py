"""Unit tests for F02 · Schema.ensure idempotency + RunRepository limits.

Covers Test Inventory rows F (Schema idempotent + PRAGMA applied) and
P (list_recent limit boundary).

[unit] — real aiosqlite file DB under tmp_path.
Feature ref: feature_2
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest


# ---------------------------------------------------------------------------
# Row F — FUNC/happy — Schema.ensure idempotent; PRAGMA values applied
# ---------------------------------------------------------------------------
async def test_schema_ensure_idempotent_and_pragma_applied(tmp_path: Path) -> None:
    from harness.persistence.schema import Schema, resolve_db_path

    db_path = resolve_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    try:
        # First call creates tables + indexes.
        await Schema.ensure(conn)
        # Second call must be silent (IF NOT EXISTS) and not double-create anything.
        await Schema.ensure(conn)

        async with conn.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table','index') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ) as cur:
            rows = await cur.fetchall()

        names = [(r["type"], r["name"]) for r in rows]
        tables = {n for t, n in names if t == "table"}
        indexes = {n for t, n in names if t == "index"}

        # Exactly the 2 DDL tables from Design §5.3.
        assert tables == {"runs", "tickets"}, f"unexpected tables: {tables}"

        # 6 user indexes from Design §5.3 (2 on runs + 4/6 on tickets).
        # Design §5.3 lists: idx_runs_state, idx_runs_started, idx_tickets_run,
        # idx_tickets_run_state, idx_tickets_state, idx_tickets_parent,
        # idx_tickets_tool_skill, idx_tickets_started — total 8. But Design-doc
        # §4.2 and feature design §7 Row F say "2 tables + 6 indexes". We assert
        # >= 6 to allow either (the hard minimum is 6).
        assert (
            len(indexes) >= 6
        ), f"expected >= 6 user indexes per Design §5.3; got {sorted(indexes)}"

        # PRAGMAs effective.
        async with conn.execute("PRAGMA journal_mode") as cur:
            jm = (await cur.fetchone())[0]
        assert jm.lower() == "wal", f"journal_mode must be WAL; got {jm!r}"

        async with conn.execute("PRAGMA foreign_keys") as cur:
            fk = (await cur.fetchone())[0]
        assert fk == 1, f"foreign_keys must be ON (1); got {fk!r}"

        async with conn.execute("PRAGMA busy_timeout") as cur:
            bt = (await cur.fetchone())[0]
        assert bt == 5000, f"busy_timeout must be 5000; got {bt!r}"
    finally:
        await conn.close()


async def test_resolve_db_path_follows_harness_workdir_layout(tmp_path: Path) -> None:
    """Boundary: resolve_db_path must return <workdir>/.harness/tickets.sqlite3 — no
    other layout. Catches bugs like writing to ~/.harness/ (NFR-006 violation) or
    bare workdir root."""
    from harness.persistence.schema import resolve_db_path

    got = resolve_db_path(tmp_path)
    assert (
        got == tmp_path / ".harness" / "tickets.sqlite3"
    ), f"resolve_db_path must follow §5.5 layout; got {got}"


# ---------------------------------------------------------------------------
# Row P — BNDRY/edge — RunRepository.list_recent limit ∈ [1, 100]
# ---------------------------------------------------------------------------
async def test_list_recent_limit_zero_raises_value_error(tmp_path: Path) -> None:
    from harness.persistence.runs import RunRepository
    from harness.persistence.schema import Schema, resolve_db_path

    db_path = resolve_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    try:
        await Schema.ensure(conn)
        repo = RunRepository(conn)
        with pytest.raises(ValueError):
            await repo.list_recent(limit=0)
    finally:
        await conn.close()


async def test_list_recent_limit_101_raises_value_error(tmp_path: Path) -> None:
    from harness.persistence.runs import RunRepository
    from harness.persistence.schema import Schema, resolve_db_path

    db_path = resolve_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    try:
        await Schema.ensure(conn)
        repo = RunRepository(conn)
        with pytest.raises(ValueError):
            await repo.list_recent(limit=101)
    finally:
        await conn.close()


async def test_list_recent_limit_boundary_1_and_100_accepted(tmp_path: Path) -> None:
    """limit=1 and limit=100 must succeed (inclusive boundaries).

    Rule 4 off-by-one kill: a naive `limit > 100` raises on 100 itself → catches
    that bug.
    """
    from harness.persistence.runs import RunRepository
    from harness.persistence.schema import Schema, resolve_db_path

    db_path = resolve_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    try:
        await Schema.ensure(conn)
        repo = RunRepository(conn)

        # Both boundaries must not raise; return value can be empty list.
        rs1 = await repo.list_recent(limit=1)
        rs100 = await repo.list_recent(limit=100)
        assert isinstance(rs1, list)
        assert isinstance(rs100, list)
    finally:
        await conn.close()
