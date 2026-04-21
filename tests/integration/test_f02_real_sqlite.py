"""Integration test for F02 · real aiosqlite file persistence (feature #2).

Covers Test Inventory row U (INTG/db).

[integration] — a real file-backed SQLite DB under tmp_path; reopens after
close to verify WAL durability. No mocks on aiosqlite, no in-memory DB.
Feature ref: feature_2

The real_fs marker makes the test discoverable via check_real_tests.py and
pytest -m real_fs. The module does NOT silently skip — if aiosqlite is
unavailable the import fails fast (ModuleNotFoundError propagates).
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

pytestmark = [pytest.mark.real_fs]


@pytest.mark.real_fs
async def test_real_sqlite_file_round_trip_with_wal_sidecar(tmp_path: Path) -> None:
    """feature_2 real test: save a ticket through connection #1, close, then
    get() through a brand-new connection against the same file. Verify
    `.harness/tickets.sqlite3` exists and the WAL sidecar indicates that WAL
    journal mode actually took effect.
    """
    from harness.domain.ticket import (
        DispatchSpec,
        ExecutionInfo,
        GitContext,
        HilInfo,
        OutputInfo,
        Run,
        Ticket,
        TicketState,
    )
    from harness.persistence.runs import RunRepository
    from harness.persistence.schema import Schema, resolve_db_path
    from harness.persistence.tickets import TicketRepository

    run_id = "run-U-001"
    db_path = resolve_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connection 1: schema + run + ticket save.
    conn1 = await aiosqlite.connect(str(db_path))
    conn1.row_factory = aiosqlite.Row
    await Schema.ensure(conn1)
    run_repo = RunRepository(conn1)
    await run_repo.create(
        Run(
            id=run_id,
            workdir=str(tmp_path),
            state="starting",
            started_at="2026-04-21T10:00:00.000000+00:00",
        )
    )
    tix_repo = TicketRepository(conn1)

    original = Ticket(
        id="t-U-1",
        run_id=run_id,
        depth=1,
        tool="claude",
        skill_hint="design",
        state=TicketState.RUNNING,
        dispatch=DispatchSpec(
            prompt="run design",
            argv=["claude", "--dangerously-skip-permissions"],
            env={"CLAUDE_CONFIG_DIR": "/iso/.claude"},
            cwd=str(tmp_path),
            plugin_dir="/iso/plugins",
            settings_path="/iso/settings.json",
        ),
        execution=ExecutionInfo(pid=12345, started_at="2026-04-21T10:00:01.000000+00:00"),
        output=OutputInfo(stream_log_ref="streams/t-U-1.jsonl"),
        hil=HilInfo(),
        anomaly=None,
        classification=None,
        git=GitContext(head_before="abc123"),
    )
    await tix_repo.save(original)

    # Sanity: DB file exists on disk (not an in-memory DB).
    assert (
        db_path.is_file()
    ), f"real SQLite file must exist at {db_path}; received no file after save()"

    # Force a WAL checkpoint-sensitive state: leaving the connection open should
    # have created a `-wal` sidecar because journal_mode=WAL is live.
    wal_sidecar = Path(str(db_path) + "-wal")
    # Run one more write to ensure WAL is engaged, then close.
    await conn1.execute("UPDATE runs SET num_turns = num_turns + 1 WHERE id = ?", (run_id,))
    await conn1.commit()
    assert (
        wal_sidecar.is_file()
    ), f"expected WAL sidecar at {wal_sidecar} — PRAGMA journal_mode=WAL not applied"
    await conn1.close()

    # Connection 2: brand-new process-level handle reopens the same file.
    conn2 = await aiosqlite.connect(str(db_path))
    conn2.row_factory = aiosqlite.Row
    await Schema.ensure(conn2)
    tix_repo2 = TicketRepository(conn2)
    loaded = await tix_repo2.get("t-U-1")
    await conn2.close()

    assert loaded is not None, "second connection must see the ticket persisted by the first"
    assert loaded.id == "t-U-1"
    assert loaded.run_id == run_id
    assert loaded.state == TicketState.RUNNING
    assert loaded.depth == 1
    assert loaded.dispatch.cwd == str(tmp_path)
    assert loaded.execution.pid == 12345
    assert loaded.output.stream_log_ref == "streams/t-U-1.jsonl"
    assert loaded.git.head_before == "abc123"
