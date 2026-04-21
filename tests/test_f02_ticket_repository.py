"""Unit tests for F02 · TicketRepository (IAPI-011 Provider).

Covers Test Inventory rows A, C, D, J, K, M, N, O, R, T.

[unit] — uses aiosqlite in-memory / tmp_path file DB. No external service.
The module under test (`harness.persistence.tickets`, `harness.persistence.schema`)
is intentionally not yet implemented — each test must fail in TDD Red with
ImportError / AttributeError / AssertionError.
Feature ref: feature_2
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiosqlite
import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
async def _connect_and_ensure(workdir: Path) -> aiosqlite.Connection:
    """Open an aiosqlite connection against a real file DB under the given workdir
    and run Schema.ensure() so all tables + PRAGMAs are live."""
    from harness.persistence.schema import Schema, resolve_db_path

    db_path = resolve_db_path(workdir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await Schema.ensure(conn)
    return conn


async def _insert_run(conn: aiosqlite.Connection, run_id: str, workdir: Path) -> None:
    """Insert a minimal runs row so foreign keys on tickets can succeed."""
    from harness.domain.ticket import Run

    from harness.persistence.runs import RunRepository

    repo = RunRepository(conn)
    await repo.create(
        Run(
            id=run_id,
            workdir=str(workdir),
            state="starting",
            started_at="2026-04-21T10:00:00.000000+00:00",
        )
    )


def _make_ticket(
    *,
    ticket_id: str,
    run_id: str,
    state: str = "pending",
    depth: int = 0,
    tool: str = "claude",
    started_at: str | None = None,
    parent: str | None = None,
) -> Any:
    """Build a full-shaped Ticket for save/get round-trip tests.

    All 7 sub-structures are set (dispatch/execution/output/hil/anomaly=None/
    classification=None/git) so row C can verify FR-007 AC-1 'missing = null not
    absent'.
    """
    from harness.domain.ticket import (
        DispatchSpec,
        ExecutionInfo,
        GitContext,
        HilInfo,
        OutputInfo,
        Ticket,
        TicketState,
    )

    return Ticket(
        id=ticket_id,
        run_id=run_id,
        parent_ticket=parent,
        depth=depth,
        tool=tool,
        skill_hint="requirements",
        state=TicketState(state),
        dispatch=DispatchSpec(
            prompt="hi",
            argv=[tool, "--dangerously-skip-permissions"],
            env={"CLAUDE_CONFIG_DIR": "/tmp/iso/.claude"},
            cwd="/tmp/workdir",
            model=None,
            plugin_dir="/tmp/iso/plugins",
            settings_path="/tmp/iso/settings.json",
        ),
        execution=ExecutionInfo(pid=None, started_at=started_at, ended_at=None),
        output=OutputInfo(result_text=None, stream_log_ref=f"streams/{ticket_id}.jsonl"),
        hil=HilInfo(),
        anomaly=None,
        classification=None,
        git=GitContext(),
    )


# ---------------------------------------------------------------------------
# Row A — FUNC/happy — FR-005 AC-1 — save + audit append; updated_at advances
# ---------------------------------------------------------------------------
async def test_save_upsert_refreshes_updated_at_and_audit_writes_one_line(
    tmp_path: Path,
) -> None:
    """Two saves of the same ticket_id: second save must update state,
    refresh updated_at (string ISO strictly greater than first), and audit
    append must write exactly one JSON line per state_transition call.
    """
    from harness.domain.ticket import AuditEvent, TicketState
    from harness.persistence.audit import AuditWriter
    from harness.persistence.tickets import TicketRepository

    run_id = "run-A-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)
        audit = AuditWriter(tmp_path / ".harness" / "audit")

        # First save: pending.
        t_pending = _make_ticket(ticket_id="t-A-1", run_id=run_id, state="pending")
        await repo.save(t_pending)

        async with conn.execute(
            "SELECT state, updated_at FROM tickets WHERE id=?", ("t-A-1",)
        ) as cur:
            row1 = await cur.fetchone()
        assert row1 is not None
        assert row1["state"] == "pending"
        ua1 = row1["updated_at"]

        # Small delay so datetime('now') ticks forward by at least 1 microsecond/second.
        await asyncio.sleep(1.1)

        # Second save: running (same id; UPSERT).
        t_running = _make_ticket(ticket_id="t-A-1", run_id=run_id, state="running")
        await repo.save(t_running)

        async with conn.execute(
            "SELECT state, updated_at FROM tickets WHERE id=?", ("t-A-1",)
        ) as cur:
            row2 = await cur.fetchone()
        assert row2 is not None
        assert row2["state"] == "running", "UPSERT must advance state column"
        ua2 = row2["updated_at"]

        # updated_at is ISO text; string-wise strictly greater (same TZ / format).
        assert ua2 > ua1, f"updated_at must advance; got {ua1!r} → {ua2!r}"

        # Audit append: state_transition pending→running.
        await audit.append(
            AuditEvent(
                ts="2026-04-21T10:00:02.000000+00:00",
                ticket_id="t-A-1",
                run_id=run_id,
                event_type="state_transition",
                state_from=TicketState.PENDING,
                state_to=TicketState.RUNNING,
            )
        )
        await audit.close()

        jsonl_path = tmp_path / ".harness" / "audit" / f"{run_id}.jsonl"
        assert (
            jsonl_path.is_file()
        ), "audit JSONL must be created at <workdir>/.harness/audit/<run_id>.jsonl"
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1, f"expected exactly 1 audit line, got {len(lines)}"
        record = json.loads(lines[0])
        assert record["ticket_id"] == "t-A-1"
        assert record["event_type"] == "state_transition"
        assert record["state_from"] == "pending"
        assert record["state_to"] == "running"
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row C — FUNC/happy — FR-007 AC-1 — get() returns all 7 sub-structures, None present
# ---------------------------------------------------------------------------
async def test_get_returns_full_ticket_with_optional_nones_explicit(tmp_path: Path) -> None:
    """After save+get, anomaly / classification must be literally None on the
    reconstituted Ticket (not KeyError / missing attr)."""
    from harness.persistence.tickets import TicketRepository

    run_id = "run-C-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)

        saved = _make_ticket(ticket_id="t-C-1", run_id=run_id, state="pending")
        await repo.save(saved)

        loaded = await repo.get("t-C-1")
        assert loaded is not None, "get() must find the ticket we just saved"
        # All 7 sub-structures reachable as attributes.
        assert loaded.dispatch is not None
        assert loaded.execution is not None
        assert loaded.output is not None
        assert loaded.hil is not None
        assert loaded.git is not None
        # Optional sub-structures must be literal None (not AttributeError, not KeyError).
        assert loaded.anomaly is None, "missing anomaly must surface as None (FR-007 AC-1)"
        assert loaded.classification is None, "missing classification must surface as None"

        # FR-005 drift guard: `state` column and payload.state agree.
        async with conn.execute("SELECT state, payload FROM tickets WHERE id=?", ("t-C-1",)) as cur:
            row = await cur.fetchone()
        payload = json.loads(row["payload"])
        assert (
            payload["state"] == row["state"]
        ), "Design §Impl Summary decision 1: state column must equal payload.state"
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row D — FUNC/happy — list_by_run + list_unfinished filter & ordering
# ---------------------------------------------------------------------------
async def test_list_by_run_and_list_unfinished_filter_and_order(tmp_path: Path) -> None:
    """5 tickets in one run (2 running, 1 classifying, 1 hil_waiting, 1 completed):
    list_unfinished → 4; list_by_run(state=RUNNING) → 2; list_by_run (no filter)
    → 5 ordered by started_at ASC."""
    from harness.domain.ticket import TicketState
    from harness.persistence.tickets import TicketRepository

    run_id = "run-D-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)

        specs = [
            ("t-D-01", "running", "2026-04-21T10:00:01.000000+00:00"),
            ("t-D-02", "running", "2026-04-21T10:00:02.000000+00:00"),
            ("t-D-03", "classifying", "2026-04-21T10:00:03.000000+00:00"),
            ("t-D-04", "hil_waiting", "2026-04-21T10:00:04.000000+00:00"),
            ("t-D-05", "completed", "2026-04-21T10:00:05.000000+00:00"),
        ]
        for tid, state, sa in specs:
            await repo.save(_make_ticket(ticket_id=tid, run_id=run_id, state=state, started_at=sa))

        unfinished = await repo.list_unfinished(run_id)
        assert len(unfinished) == 4, (
            f"list_unfinished must return running/classifying/hil_waiting only; "
            f"got {[t.id for t in unfinished]}"
        )
        unfinished_states = {t.state for t in unfinished}
        assert (
            TicketState.COMPLETED not in unfinished_states
        ), "completed ticket must NOT appear in list_unfinished (Rule 4 guard)"

        only_running = await repo.list_by_run(run_id, state=TicketState.RUNNING)
        assert len(only_running) == 2
        assert all(t.state == TicketState.RUNNING for t in only_running)

        all_in_run = await repo.list_by_run(run_id)
        assert len(all_in_run) == 5
        ids_in_order = [t.id for t in all_in_run]
        assert ids_in_order == [
            "t-D-01",
            "t-D-02",
            "t-D-03",
            "t-D-04",
            "t-D-05",
        ], "list_by_run must sort by started_at ASC, id ASC"
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row J — FUNC/error — mark_interrupted on COMPLETED raises TransitionError
# ---------------------------------------------------------------------------
async def test_mark_interrupted_on_completed_ticket_raises_and_does_not_mutate(
    tmp_path: Path,
) -> None:
    """Per §IC Raises: mark_interrupted must reject completed state.

    Rule 4: a naive UPDATE that doesn't check current state would silently change
    completed→interrupted — this test detects that exact bug.
    """
    from harness.domain.state_machine import TransitionError
    from harness.persistence.tickets import TicketRepository

    run_id = "run-J-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)

        completed = _make_ticket(ticket_id="t-J-1", run_id=run_id, state="completed")
        await repo.save(completed)

        with pytest.raises(TransitionError):
            await repo.mark_interrupted("t-J-1")

        async with conn.execute("SELECT state FROM tickets WHERE id=?", ("t-J-1",)) as cur:
            row = await cur.fetchone()
        assert (
            row["state"] == "completed"
        ), "mark_interrupted on completed must leave state untouched"
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row K — FUNC/error — get(missing_id) returns None; mark_interrupted raises NotFound
# ---------------------------------------------------------------------------
async def test_get_missing_id_returns_none_and_mark_interrupted_raises_not_found(
    tmp_path: Path,
) -> None:
    from harness.domain.ticket import TicketNotFoundError
    from harness.persistence.tickets import TicketRepository

    run_id = "run-K-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)

        loaded = await repo.get("t-K-does-not-exist")
        assert loaded is None, "get() on unknown id must return None, not raise"

        with pytest.raises(TicketNotFoundError):
            await repo.mark_interrupted("t-K-does-not-exist")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row M — BNDRY/edge — depth ∈ {0, 1, 2} round-trips exactly
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("depth", [0, 1, 2])
async def test_depth_boundary_values_round_trip(tmp_path: Path, depth: int) -> None:
    from harness.persistence.tickets import TicketRepository

    run_id = "run-M-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)

        tid = f"t-M-depth-{depth}"
        await repo.save(_make_ticket(ticket_id=tid, run_id=run_id, state="pending", depth=depth))

        loaded = await repo.get(tid)
        assert loaded is not None
        assert loaded.depth == depth, f"depth must round-trip exactly; got {loaded.depth}"
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row N — BNDRY/edge — raw SQL INSERT with depth=3 must violate DDL CHECK
# ---------------------------------------------------------------------------
async def test_raw_insert_depth_3_violates_ddl_check(tmp_path: Path) -> None:
    """§Design rationale 'depth 约束层叠三层': pydantic + DDL CHECK + F03.
    If someone bypasses pydantic by raw SQL, DDL CHECK must still catch depth=3.
    """
    conn = await _connect_and_ensure(tmp_path)
    try:
        run_id = "run-N-001"
        await _insert_run(conn, run_id, tmp_path)

        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO tickets (id, run_id, depth, tool, state, payload, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
                ("t-N-1", run_id, 3, "claude", "pending", "{}"),
            )
            await conn.commit()
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row O — BNDRY/edge — list_by_run("") raises ValueError (no SQL executed)
# ---------------------------------------------------------------------------
async def test_list_by_run_empty_string_raises_value_error(tmp_path: Path) -> None:
    """Empty run_id must NOT run `WHERE run_id=''` against SQLite; must ValueError early.

    Rule 4 trap: a naive impl that forwards the raw string would return tickets
    whose run_id column is literally '' (none exist, but the SELECT still runs
    on the table — worse if a bug inserts with empty run_id). Reject upfront.
    """
    from harness.persistence.tickets import TicketRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = TicketRepository(conn)
        with pytest.raises(ValueError):
            await repo.list_by_run("")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row R — BNDRY/edge — concurrent save on same ticket merges state + anomaly
# ---------------------------------------------------------------------------
async def test_concurrent_save_same_ticket_preserves_both_updates(tmp_path: Path) -> None:
    """StreamParser sets state=running; Anomaly sets anomaly.retry_count=1.
    After both saves complete, both fields must be present — neither should
    wipe the other via whole-record overwrite.

    This test fails if save() is not UPSERT-style or serialized behind a lock.
    """
    from harness.domain.ticket import AnomalyInfo, TicketState
    from harness.persistence.tickets import TicketRepository

    run_id = "run-R-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)

        # Seed a pending ticket.
        base = _make_ticket(ticket_id="t-R-1", run_id=run_id, state="pending")
        await repo.save(base)

        running_only = _make_ticket(ticket_id="t-R-1", run_id=run_id, state="running")
        with_anomaly = _make_ticket(ticket_id="t-R-1", run_id=run_id, state="running")
        with_anomaly.anomaly = AnomalyInfo(cls="network", detail="ECONNRESET", retry_count=1)

        # Sequential order: state first, then anomaly — final must reflect both.
        await repo.save(running_only)
        await repo.save(with_anomaly)

        loaded = await repo.get("t-R-1")
        assert loaded is not None
        assert loaded.state == TicketState.RUNNING, "state field must survive the merge"
        assert loaded.anomaly is not None, "anomaly must survive the merge (Rule 4: overwrite bug)"
        assert loaded.anomaly.retry_count == 1
        assert loaded.anomaly.cls == "network"
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Row T — SEC/injection — parameterized binding; DROP TABLE attempt is inert
# ---------------------------------------------------------------------------
async def test_list_by_run_sql_injection_is_neutralised(tmp_path: Path) -> None:
    """run_id containing `'; DROP TABLE tickets; --` must return [] and tickets table survives."""
    from harness.persistence.tickets import TicketRepository

    run_id = "run-T-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)

        # Seed 1 ticket so the table is non-empty (makes the DROP check meaningful).
        await repo.save(_make_ticket(ticket_id="t-T-1", run_id=run_id, state="pending"))

        malicious = "'; DROP TABLE tickets; --"
        rows = await repo.list_by_run(malicious)
        assert rows == [], f"injection string must return empty list; got {rows}"

        # tickets table still exists with original row.
        async with conn.execute("SELECT COUNT(*) AS n FROM tickets") as cur:
            row = await cur.fetchone()
        assert row["n"] == 1, "tickets table must still contain the seeded row (no DROP)"
    finally:
        await conn.close()
