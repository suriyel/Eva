"""Unit tests for F02 · RecoveryScanner.scan_and_mark_interrupted (NFR-005).

Covers Test Inventory row E.

[unit] — simulate a crash by closing the first aiosqlite connection without
a graceful shutdown, then reopen and scan. Uses real SQLite file DB + real
audit JSONL under tmp_path (no mocks on either).
Feature ref: feature_2
"""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite


async def test_scan_and_mark_interrupted_handles_running_classifying_hil_waiting(
    tmp_path: Path,
) -> None:
    """3 unfinished tickets (running / classifying / hil_waiting) in one run →
    simulate crash → new connection + scan_and_mark_interrupted → all 3 marked
    interrupted + 3 audit JSONL lines appended with correct state_from values.
    """
    from harness.domain.ticket import Run, TicketState
    from harness.persistence.audit import AuditWriter
    from harness.persistence.recovery import RecoveryScanner
    from harness.persistence.runs import RunRepository
    from harness.persistence.schema import Schema, resolve_db_path
    from harness.persistence.tickets import TicketRepository

    # Keep make_ticket helper local so tests remain self-contained.
    from harness.domain.ticket import (
        DispatchSpec,
        ExecutionInfo,
        GitContext,
        HilInfo,
        OutputInfo,
        Ticket,
    )

    def mkt(tid: str, run_id: str, state: str) -> Ticket:
        return Ticket(
            id=tid,
            run_id=run_id,
            depth=0,
            tool="claude",
            state=TicketState(state),
            dispatch=DispatchSpec(
                argv=["claude"],
                env={},
                cwd=str(tmp_path),
                plugin_dir=str(tmp_path / "plugins"),
                settings_path=str(tmp_path / "settings.json"),
            ),
            execution=ExecutionInfo(),
            output=OutputInfo(),
            hil=HilInfo(),
            anomaly=None,
            classification=None,
            git=GitContext(),
        )

    run_id = "run-E-001"
    db_path = resolve_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------- Connection #1: write 3 unfinished tickets, then "crash" ----------
    conn1 = await aiosqlite.connect(str(db_path))
    conn1.row_factory = aiosqlite.Row
    await Schema.ensure(conn1)
    run_repo1 = RunRepository(conn1)
    await run_repo1.create(
        Run(
            id=run_id,
            workdir=str(tmp_path),
            state="running",
            started_at="2026-04-21T10:00:00.000000+00:00",
        )
    )
    tix_repo1 = TicketRepository(conn1)
    # Use three distinct unfinished states.
    await tix_repo1.save(mkt("t-E-run", run_id, "running"))
    await tix_repo1.save(mkt("t-E-cls", run_id, "classifying"))
    await tix_repo1.save(mkt("t-E-hil", run_id, "hil_waiting"))
    # Simulate crash: close without calling mark_interrupted.
    await conn1.close()

    # ---------- Connection #2: new process → recovery scan ----------
    conn2 = await aiosqlite.connect(str(db_path))
    conn2.row_factory = aiosqlite.Row
    await Schema.ensure(conn2)
    audit = AuditWriter(tmp_path / ".harness" / "audit")
    tix_repo2 = TicketRepository(conn2)
    scanner = RecoveryScanner(conn2, audit)

    marked_ids = await scanner.scan_and_mark_interrupted(run_id)
    await audit.close()

    # Return value: 3 ids, set equality to avoid ordering sensitivity.
    assert set(marked_ids) == {
        "t-E-run",
        "t-E-cls",
        "t-E-hil",
    }, f"expected all 3 unfinished ticket ids to be marked; got {marked_ids}"

    # Re-read the tickets: state must be 'interrupted'.
    for tid in ("t-E-run", "t-E-cls", "t-E-hil"):
        t = await tix_repo2.get(tid)
        assert t is not None
        assert t.state == TicketState.INTERRUPTED, f"{tid} must now be INTERRUPTED; got {t.state}"

    # Audit JSONL: 3 lines, event_type='interrupted', state_from preserved.
    jsonl_path = tmp_path / ".harness" / "audit" / f"{run_id}.jsonl"
    assert jsonl_path.is_file(), f"audit file must exist at {jsonl_path}"
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3, f"expected 3 interrupted audit lines; got {len(lines)}"

    state_from_by_ticket: dict[str, str] = {}
    for ln in lines:
        rec = json.loads(ln)
        assert rec["event_type"] == "interrupted", rec
        assert rec["state_to"] == "interrupted"
        state_from_by_ticket[rec["ticket_id"]] = rec["state_from"]

    assert state_from_by_ticket["t-E-run"] == "running"
    assert state_from_by_ticket["t-E-cls"] == "classifying"
    assert state_from_by_ticket["t-E-hil"] == "hil_waiting"

    await conn2.close()
