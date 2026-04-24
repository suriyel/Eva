"""Branch-coverage supplement for F02 · Persistence Core.

These tests exist exclusively to raise line/branch coverage on the F02 impl
files (harness/domain/*, harness/persistence/*) above the quality gate
thresholds (line ≥ 90%, branch ≥ 80%). They target error paths, optional
parameter combinations, and defensive early returns that the primary Red
tests (rows A..T) did not exercise.

Feature ref: feature_2
SRS trace: FR-005, FR-006, FR-007, NFR-005, NFR-006
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite
import pytest


# ---------------------------------------------------------------------------
# Shared fixtures (mirrors tests/test_f02_ticket_repository.py helpers)
# ---------------------------------------------------------------------------
async def _connect_and_ensure(workdir: Path) -> aiosqlite.Connection:
    from harness.persistence.schema import Schema, resolve_db_path

    db_path = resolve_db_path(workdir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await Schema.ensure(conn)
    return conn


def _make_ticket(
    *,
    ticket_id: str,
    run_id: str,
    state: str = "pending",
    depth: int = 0,
    tool: str = "claude",
    parent: str | None = None,
    started_at: str | None = None,
) -> Any:
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
        skill_hint=None,
        state=TicketState(state),
        dispatch=DispatchSpec(
            argv=[tool],
            env={},
            cwd="/tmp",
            plugin_dir="/tmp/p",
            settings_path="/tmp/s.json",
        ),
        execution=ExecutionInfo(started_at=started_at),
        output=OutputInfo(),
        hil=HilInfo(),
        anomaly=None,
        classification=None,
        git=GitContext(),
    )


async def _insert_run(conn: aiosqlite.Connection, run_id: str, workdir: Path) -> None:
    from harness.domain.ticket import Run
    from harness.persistence.runs import RunRepository

    await RunRepository(conn).create(
        Run(
            id=run_id,
            workdir=str(workdir),
            state="starting",
            started_at="2026-04-21T10:00:00.000000+00:00",
        )
    )


# ---------------------------------------------------------------------------
# harness/domain/state_machine.py — RunNotFoundError instantiation (FR-005)
# ---------------------------------------------------------------------------
def test_fr_005_run_not_found_error_carries_run_id_and_message() -> None:
    """RunNotFoundError.__init__ must store run_id and format message.

    Covers state_machine.py lines 56-57 (constructor body).
    """
    from harness.domain.state_machine import RunNotFoundError

    err = RunNotFoundError("run-missing-001")
    assert err.run_id == "run-missing-001"
    assert "run-missing-001" in str(err)
    assert "not found" in str(err).lower()


# ---------------------------------------------------------------------------
# harness/persistence/runs.py — RunRepository exhaustive coverage (FR-005)
# ---------------------------------------------------------------------------
async def test_fr_005_run_update_all_optional_fields_together(tmp_path: Path) -> None:
    """Exercise every optional branch inside RunRepository.update.

    Covers runs.py lines 72-110 (every `if ... is not None:` branch).
    """
    from harness.domain.ticket import Run
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = RunRepository(conn)
        await repo.create(
            Run(
                id="run-U-001",
                workdir=str(tmp_path),
                state="starting",
                started_at="2026-04-21T10:00:00.000000+00:00",
            )
        )

        await repo.update(
            "run-U-001",
            state="running",
            current_phase="tdd",
            current_feature="feature_2",
            cost_usd_delta=0.5,
            num_turns_delta=3,
            head_latest="abcdef1",
            ended_at="2026-04-21T11:00:00.000000+00:00",
        )

        got = await repo.get("run-U-001")
        assert got is not None
        assert got.state == "running"
        assert got.current_phase == "tdd"
        assert got.current_feature == "feature_2"
        assert got.cost_usd == pytest.approx(0.5)
        assert got.num_turns == 3
        assert got.head_latest == "abcdef1"
        assert got.ended_at == "2026-04-21T11:00:00.000000+00:00"
    finally:
        await conn.close()


async def test_fr_005_run_update_empty_run_id_raises_value_error(tmp_path: Path) -> None:
    """update("") — guard fires before DB touch (runs.py line 73)."""
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = RunRepository(conn)
        with pytest.raises(ValueError):
            await repo.update("", state="running")
    finally:
        await conn.close()


async def test_fr_005_run_update_missing_id_raises_run_not_found(tmp_path: Path) -> None:
    """update on unknown id → RunNotFoundError (runs.py line 77)."""
    from harness.domain.state_machine import RunNotFoundError
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = RunRepository(conn)
        with pytest.raises(RunNotFoundError):
            await repo.update("run-does-not-exist", state="running")
    finally:
        await conn.close()


async def test_fr_005_run_get_missing_returns_none(tmp_path: Path) -> None:
    """get() on unknown id → None, not error (runs.py lines 116-118)."""
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = RunRepository(conn)
        assert await repo.get("run-missing") is None
    finally:
        await conn.close()


async def test_fr_005_run_list_recent_offset_negative_raises(tmp_path: Path) -> None:
    """offset<0 must raise ValueError (runs.py line 126)."""
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = RunRepository(conn)
        with pytest.raises(ValueError):
            await repo.list_recent(limit=10, offset=-1)
    finally:
        await conn.close()


async def test_fr_005_run_list_recent_returns_in_started_at_desc(tmp_path: Path) -> None:
    """Seed 3 runs; list_recent must order by started_at DESC."""
    from harness.domain.ticket import Run
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = RunRepository(conn)
        for i, ts in enumerate(
            [
                "2026-04-21T10:00:01.000000+00:00",
                "2026-04-21T10:00:03.000000+00:00",
                "2026-04-21T10:00:02.000000+00:00",
            ],
            start=1,
        ):
            await repo.create(
                Run(
                    id=f"run-L-{i}",
                    workdir=str(tmp_path),
                    state="starting",
                    started_at=ts,
                )
            )

        recent = await repo.list_recent(limit=5, offset=0)
        ids = [r.id for r in recent]
        # DESC order by started_at → run-L-2 (10:00:03), run-L-3 (10:00:02), run-L-1.
        assert ids == ["run-L-2", "run-L-3", "run-L-1"]
    finally:
        await conn.close()


async def test_fr_005_run_create_dao_error_on_closed_connection(tmp_path: Path) -> None:
    """A closed connection → create() wraps OperationalError as DaoError.

    Covers runs.py lines 57-58 (except Exception branch).
    """
    from harness.domain.ticket import Run
    from harness.persistence.errors import DaoError
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    repo = RunRepository(conn)
    await conn.close()

    with pytest.raises(DaoError):
        await repo.create(
            Run(
                id="run-broken",
                workdir=str(tmp_path),
                state="starting",
                started_at="2026-04-21T10:00:00.000000+00:00",
            )
        )


async def test_fr_005_run_update_dao_error_on_closed_connection(tmp_path: Path) -> None:
    """update() after the connection has been poisoned → DaoError.

    Covers runs.py lines 109-110 (except branch in update).
    Uses monkey-patched execute to raise a non-Exception-safe error AFTER the
    get() call so we reach the outer try/except.
    """
    from harness.domain.ticket import Run
    from harness.persistence.errors import DaoError
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = RunRepository(conn)
        await repo.create(
            Run(
                id="run-brk",
                workdir=str(tmp_path),
                state="starting",
                started_at="2026-04-21T10:00:00.000000+00:00",
            )
        )

        original_execute = conn.execute

        def flaky_execute(sql: str, *args: Any, **kwargs: Any) -> Any:
            # Allow SELECT path of `get(run_id)` first; fail the UPDATE.
            if sql.lstrip().upper().startswith("UPDATE"):

                async def _boom() -> Any:
                    raise RuntimeError("simulated driver UPDATE failure")

                return _boom()
            return original_execute(sql, *args, **kwargs)

        conn.execute = flaky_execute  # type: ignore[assignment]
        with pytest.raises(DaoError):
            await repo.update("run-brk", state="running")
    finally:
        await conn.close()


async def test_fr_005_run_get_dao_error_on_closed_connection(tmp_path: Path) -> None:
    """get() after connection close → DaoError (runs.py lines 119-120)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    repo = RunRepository(conn)
    await conn.close()
    with pytest.raises(DaoError):
        await repo.get("any-id")


async def test_fr_005_run_list_recent_dao_error_on_closed_connection(tmp_path: Path) -> None:
    """list_recent after close → DaoError (runs.py lines 135-136)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    repo = RunRepository(conn)
    await conn.close()
    with pytest.raises(DaoError):
        await repo.list_recent(limit=5)


async def test_fr_005_run_row_payload_invalid_json_raises_dao_error(tmp_path: Path) -> None:
    """Corrupt payload column → _row_to_run raises DaoError (runs.py line 144)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        # Write raw bad payload (bypass pydantic entirely).
        await conn.execute(
            "INSERT INTO runs (id, workdir, state, started_at, payload) VALUES (?,?,?,?,?)",
            (
                "run-bad-json",
                str(tmp_path),
                "starting",
                "2026-04-21T10:00:00.000000+00:00",
                "{this-is-not-json",
            ),
        )
        await conn.commit()

        repo = RunRepository(conn)
        with pytest.raises(DaoError):
            await repo.get("run-bad-json")
    finally:
        await conn.close()


async def test_fr_005_run_row_payload_null_defaults_to_empty_dict(tmp_path: Path) -> None:
    """payload='' falls through the `if payload_raw else {}` branch → {}.

    Covers runs.py lines 140-142 + 158 (payload_dict={}).
    """
    from harness.persistence.runs import RunRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        await conn.execute(
            "INSERT INTO runs (id, workdir, state, started_at, payload) VALUES (?,?,?,?,?)",
            (
                "run-empty-payload",
                str(tmp_path),
                "starting",
                "2026-04-21T10:00:00.000000+00:00",
                "",
            ),
        )
        await conn.commit()

        got = await RunRepository(conn).get("run-empty-payload")
        assert got is not None
        assert got.payload == {}
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# harness/persistence/tickets.py — branch-coverage supplement (FR-005/006/007)
# ---------------------------------------------------------------------------
async def test_fr_007_ticket_get_rejects_empty_and_non_str_ids(tmp_path: Path) -> None:
    """Defensive early-miss for bad ids (tickets.py lines 108-110)."""
    from harness.persistence.tickets import TicketRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = TicketRepository(conn)
        assert await repo.get("") is None
        assert await repo.get(None) is None  # type: ignore[arg-type]
    finally:
        await conn.close()


async def test_fr_007_ticket_get_dao_error_on_closed_connection(tmp_path: Path) -> None:
    """get() after close → DaoError (tickets.py lines 119-120)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.tickets import TicketRepository

    conn = await _connect_and_ensure(tmp_path)
    repo = TicketRepository(conn)
    await conn.close()
    with pytest.raises(DaoError):
        await repo.get("t-missing")


async def test_fr_007_ticket_save_dao_error_on_generic_driver_failure(tmp_path: Path) -> None:
    """save() — generic driver Exception wrapped as DaoError (tickets.py lines 101-102).

    ``ValueError`` is re-raised untouched (line 98-100); to exercise the
    DaoError branch we inject a RuntimeError via a patched conn.execute.
    """
    from harness.persistence.errors import DaoError
    from harness.persistence.tickets import TicketRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, "run-close", tmp_path)
        repo = TicketRepository(conn)

        async def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("simulated driver INSERT failure")

        conn.execute = boom  # type: ignore[assignment]
        with pytest.raises(DaoError):
            await repo.save(_make_ticket(ticket_id="t-x", run_id="run-close"))
    finally:
        # Restore so close() doesn't explode on patched method.
        await conn.close()


async def test_fr_007_ticket_list_by_run_filters_state_tool_parent_combined(
    tmp_path: Path,
) -> None:
    """Exercise every optional-filter branch (tickets.py lines 138-146)."""
    from harness.domain.ticket import TicketState
    from harness.persistence.tickets import TicketRepository

    run_id = "run-F-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)

        # Parent ticket at depth=0.
        parent = _make_ticket(
            ticket_id="t-parent",
            run_id=run_id,
            state="running",
            tool="claude",
            started_at="2026-04-21T10:00:01.000000+00:00",
        )
        await repo.save(parent)

        # Child tickets at depth=1, tool=opencode.
        for i in range(2):
            await repo.save(
                _make_ticket(
                    ticket_id=f"t-child-{i}",
                    run_id=run_id,
                    state="classifying",
                    tool="opencode",
                    depth=1,
                    parent="t-parent",
                    started_at=f"2026-04-21T10:00:0{i+2}.000000+00:00",
                )
            )

        # Filter state only.
        only_running = await repo.list_by_run(run_id, state=TicketState.RUNNING)
        assert {t.id for t in only_running} == {"t-parent"}

        # Filter tool only.
        only_opencode = await repo.list_by_run(run_id, tool="opencode")
        assert {t.id for t in only_opencode} == {"t-child-0", "t-child-1"}

        # Filter parent only.
        only_children = await repo.list_by_run(run_id, parent="t-parent")
        assert {t.id for t in only_children} == {"t-child-0", "t-child-1"}

        # Combined: parent + state + tool.
        all_combo = await repo.list_by_run(
            run_id,
            state=TicketState.CLASSIFYING,
            tool="opencode",
            parent="t-parent",
        )
        assert {t.id for t in all_combo} == {"t-child-0", "t-child-1"}
    finally:
        await conn.close()


async def test_fr_007_ticket_list_by_run_dao_error_on_closed_connection(
    tmp_path: Path,
) -> None:
    """list_by_run after close → DaoError (tickets.py lines 155-156)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.tickets import TicketRepository

    conn = await _connect_and_ensure(tmp_path)
    repo = TicketRepository(conn)
    await conn.close()
    with pytest.raises(DaoError):
        await repo.list_by_run("run-any")


async def test_fr_007_ticket_list_unfinished_empty_run_id_raises(tmp_path: Path) -> None:
    """list_unfinished("") → ValueError (tickets.py lines 162-163)."""
    from harness.persistence.tickets import TicketRepository

    conn = await _connect_and_ensure(tmp_path)
    try:
        repo = TicketRepository(conn)
        with pytest.raises(ValueError):
            await repo.list_unfinished("")
    finally:
        await conn.close()


async def test_fr_007_ticket_list_unfinished_dao_error_on_closed_connection(
    tmp_path: Path,
) -> None:
    """list_unfinished after close → DaoError (tickets.py lines 176-177)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.tickets import TicketRepository

    conn = await _connect_and_ensure(tmp_path)
    repo = TicketRepository(conn)
    await conn.close()
    with pytest.raises(DaoError):
        await repo.list_unfinished("run-any")


async def test_fr_006_ticket_mark_interrupted_lookup_dao_error(tmp_path: Path) -> None:
    """mark_interrupted() after conn close → DaoError on SELECT (lines 188-189)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.tickets import TicketRepository

    conn = await _connect_and_ensure(tmp_path)
    repo = TicketRepository(conn)
    await conn.close()
    with pytest.raises(DaoError):
        await repo.mark_interrupted("t-any")


async def test_fr_006_ticket_mark_interrupted_update_dao_error(tmp_path: Path) -> None:
    """mark_interrupted UPDATE failure → DaoError (tickets.py lines 216-217).

    Achieved by patching conn.execute so the SELECT succeeds but the UPDATE
    raises — mirrors a real aiosqlite driver hiccup mid-transaction.
    """
    from harness.persistence.errors import DaoError
    from harness.persistence.tickets import TicketRepository

    run_id = "run-MU-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        repo = TicketRepository(conn)
        await repo.save(_make_ticket(ticket_id="t-MU-1", run_id=run_id, state="running"))

        original_execute = conn.execute

        def flaky_execute(sql: str, *args: Any, **kwargs: Any) -> Any:
            if sql.lstrip().upper().startswith("UPDATE"):

                async def _boom() -> Any:
                    raise RuntimeError("simulated aiosqlite UPDATE failure")

                return _boom()
            return original_execute(sql, *args, **kwargs)

        conn.execute = flaky_execute  # type: ignore[assignment]

        with pytest.raises(DaoError):
            await repo.mark_interrupted("t-MU-1")
    finally:
        await conn.close()


async def test_fr_007_row_to_ticket_invalid_json_payload_raises_dao_error(
    tmp_path: Path,
) -> None:
    """Corrupt payload text → DaoError (tickets.py lines 228-229)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.tickets import TicketRepository

    run_id = "run-JSON-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        # Force-insert a ticket with invalid payload JSON.
        await conn.execute(
            "INSERT INTO tickets (id, run_id, depth, tool, state, payload, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))",
            ("t-bad-json", run_id, 0, "claude", "pending", "{broken"),
        )
        await conn.commit()

        repo = TicketRepository(conn)
        with pytest.raises(DaoError):
            await repo.get("t-bad-json")
    finally:
        await conn.close()


async def test_fr_007_row_to_ticket_schema_drift_raises_dao_error(tmp_path: Path) -> None:
    """Payload JSON-valid but schema-wrong → DaoError (tickets.py lines 232-233)."""
    from harness.persistence.errors import DaoError
    from harness.persistence.tickets import TicketRepository

    run_id = "run-DRIFT-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        # Valid JSON but missing required fields for Ticket model.
        bad_payload = json.dumps({"id": "x", "not_a_ticket_field": True})
        await conn.execute(
            "INSERT INTO tickets (id, run_id, depth, tool, state, payload, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))",
            ("t-drift", run_id, 0, "claude", "pending", bad_payload),
        )
        await conn.commit()

        repo = TicketRepository(conn)
        with pytest.raises(DaoError):
            await repo.get("t-drift")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# harness/persistence/audit.py — fsync=False branch (NFR-006)
# ---------------------------------------------------------------------------
async def test_nfr_006_audit_append_without_fsync_still_writes_line(tmp_path: Path) -> None:
    """fsync=False path (audit.py line 84->87 branch skip)."""
    from harness.domain.ticket import AuditEvent, TicketState
    from harness.persistence.audit import AuditWriter

    audit_dir = tmp_path / ".harness" / "audit"
    writer = AuditWriter(audit_dir, fsync=False)
    await writer.append(
        AuditEvent(
            ts="2026-04-21T10:00:00.000000+00:00",
            ticket_id="t-nf-1",
            run_id="run-nf-1",
            event_type="state_transition",
            state_from=TicketState.PENDING,
            state_to=TicketState.RUNNING,
        )
    )
    # Override per-call: fsync=True even though default=False.
    await writer.append(
        AuditEvent(
            ts="2026-04-21T10:00:01.000000+00:00",
            ticket_id="t-nf-1",
            run_id="run-nf-1",
            event_type="state_transition",
            state_from=TicketState.RUNNING,
            state_to=TicketState.CLASSIFYING,
        ),
        fsync=True,
    )
    await writer.close()

    jsonl_path = audit_dir / "run-nf-1.jsonl"
    assert jsonl_path.is_file()
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


async def test_nfr_006_audit_append_oserror_wraps_as_io_error(tmp_path: Path) -> None:
    """Permission failure inside append → IoError (audit.py lines 88-95)."""
    from harness.domain.ticket import AuditEvent, TicketState
    from harness.persistence.audit import AuditWriter
    from harness.persistence.errors import IoError

    # Point audit at a path where mkdir will fail: a FILE named like a dir.
    conflict = tmp_path / "not-a-dir"
    conflict.write_text("sentinel")

    writer = AuditWriter(conflict / "audit")
    with pytest.raises(IoError):
        await writer.append(
            AuditEvent(
                ts="2026-04-21T10:00:00.000000+00:00",
                ticket_id="t-er-1",
                run_id="run-er-1",
                event_type="state_transition",
                state_from=TicketState.PENDING,
                state_to=TicketState.RUNNING,
            )
        )


async def test_nfr_006_audit_lock_reused_across_calls(tmp_path: Path) -> None:
    """Second append reuses existing lock (audit.py lines 40-44 lock-hit branch)."""
    from harness.domain.ticket import AuditEvent, TicketState
    from harness.persistence.audit import AuditWriter

    writer = AuditWriter(tmp_path / ".harness" / "audit")
    lock_first = writer._get_lock("run-reuse")
    lock_second = writer._get_lock("run-reuse")
    assert lock_first is lock_second

    await writer.append(
        AuditEvent(
            ts="2026-04-21T10:00:00.000000+00:00",
            ticket_id="t-re-1",
            run_id="run-reuse",
            event_type="state_transition",
            state_from=TicketState.PENDING,
            state_to=TicketState.RUNNING,
        )
    )
    await writer.close()
    # After close, the lock map is empty — next call must create a new lock.
    assert writer._locks == {}


# ---------------------------------------------------------------------------
# harness/persistence/recovery.py — NFR-005 defensive branches
# ---------------------------------------------------------------------------
async def test_nfr_005_recovery_scan_empty_run_id_raises(tmp_path: Path) -> None:
    """scan_and_mark_interrupted('') → ValueError (recovery.py line 43)."""
    from harness.persistence.audit import AuditWriter
    from harness.persistence.recovery import RecoveryScanner

    conn = await _connect_and_ensure(tmp_path)
    try:
        audit = AuditWriter(tmp_path / ".harness" / "audit")
        scanner = RecoveryScanner(conn, audit)
        with pytest.raises(ValueError):
            await scanner.scan_and_mark_interrupted("")
    finally:
        await conn.close()


async def test_nfr_005_recovery_scan_wraps_unexpected_errors_as_dao_error(
    tmp_path: Path,
) -> None:
    """audit.append raises RuntimeError → scanner re-raises as DaoError.

    Covers recovery.py lines 65-70 (except Exception → DaoError wrap).
    """
    from harness.domain.ticket import AuditEvent
    from harness.persistence.audit import AuditWriter
    from harness.persistence.errors import DaoError
    from harness.persistence.recovery import RecoveryScanner

    run_id = "run-RC-001"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        from harness.persistence.tickets import TicketRepository

        await TicketRepository(conn).save(
            _make_ticket(ticket_id="t-rc-1", run_id=run_id, state="running")
        )

        audit = AuditWriter(tmp_path / ".harness" / "audit")

        async def boom(event: AuditEvent, *, fsync: bool | None = None) -> None:
            raise RuntimeError("boom: audit subsystem explode")

        audit.append = boom  # type: ignore[assignment]

        scanner = RecoveryScanner(conn, audit)
        with pytest.raises(DaoError):
            await scanner.scan_and_mark_interrupted(run_id)
    finally:
        await conn.close()


async def test_nfr_005_recovery_scan_re_raises_dao_error_untouched(
    tmp_path: Path,
) -> None:
    """A DaoError raised during iteration must propagate untouched.

    Covers recovery.py line 68-69 (isinstance(exc, DaoError) re-raise branch).
    """
    from harness.persistence.audit import AuditWriter
    from harness.persistence.errors import DaoError
    from harness.persistence.recovery import RecoveryScanner

    run_id = "run-RC-002"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        from harness.persistence.tickets import TicketRepository

        repo = TicketRepository(conn)
        await repo.save(_make_ticket(ticket_id="t-rc-2", run_id=run_id, state="running"))

        audit = AuditWriter(tmp_path / ".harness" / "audit")
        scanner = RecoveryScanner(conn, audit)

        # Patch TicketRepository.mark_interrupted to raise DaoError mid-loop.
        async def boom_dao(ticket_id: str) -> Any:
            raise DaoError("simulated DAO failure")

        scanner._tickets.mark_interrupted = boom_dao  # type: ignore[assignment]

        with pytest.raises(DaoError) as exc_info:
            await scanner.scan_and_mark_interrupted(run_id)

        # Must be the ORIGINAL DaoError, not a newly-wrapped one.
        assert "simulated DAO failure" in str(exc_info.value)
    finally:
        await conn.close()


async def test_nfr_005_recovery_scan_no_unfinished_tickets_returns_empty(
    tmp_path: Path,
) -> None:
    """A clean run with zero unfinished tickets → scanner returns []."""
    from harness.persistence.audit import AuditWriter
    from harness.persistence.recovery import RecoveryScanner

    run_id = "run-RC-clean"
    conn = await _connect_and_ensure(tmp_path)
    try:
        await _insert_run(conn, run_id, tmp_path)
        # No unfinished tickets seeded.
        audit = AuditWriter(tmp_path / ".harness" / "audit")
        scanner = RecoveryScanner(conn, audit)
        marked = await scanner.scan_and_mark_interrupted(run_id)
        assert marked == []
        await audit.close()
    finally:
        await conn.close()
