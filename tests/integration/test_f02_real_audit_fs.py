"""Integration test for F02 · real filesystem audit JSONL + NFR-006 isolation.

Covers Test Inventory rows V (INTG/fs) and S (SEC/fs-isolation).

[integration] — real aiosqlite + real JSONL writes + recursive workdir walk
to validate NFR-006 "writes limited to .harness/". No mocks. Neither
~/.harness/ nor ~/.claude/ may be touched — the test asserts their mtimes
remain unchanged.
Feature ref: feature_2
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import aiosqlite
import pytest

pytestmark = [pytest.mark.real_fs]


@pytest.mark.real_fs
async def test_real_jsonl_round_trip_5_events(tmp_path: Path) -> None:
    """feature_2 real test: append 5 AuditEvents through a real AuditWriter,
    close, reopen the file with `json.loads` per line, and reconstruct each
    event via AuditEvent.model_validate — all 5 must round-trip exactly.
    """
    from harness.domain.ticket import AuditEvent, TicketState
    from harness.persistence.audit import AuditWriter

    run_id = "run-V-001"
    audit_dir = tmp_path / ".harness" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    writer = AuditWriter(audit_dir)
    originals = [
        AuditEvent(
            ts=f"2026-04-21T10:00:{i:02d}.000000+00:00",
            ticket_id=f"t-V-{i:02d}",
            run_id=run_id,
            event_type="state_transition",
            state_from=TicketState.PENDING,
            state_to=TicketState.RUNNING,
            payload={"sequence": i, "note": "来自中文 payload"},
        )
        for i in range(5)
    ]
    for ev in originals:
        await writer.append(ev)
    await writer.close()

    jsonl_path = audit_dir / f"{run_id}.jsonl"
    assert jsonl_path.is_file(), f"real audit file must be created at {jsonl_path}"
    raw = jsonl_path.read_bytes()
    # utf-8 encoding, no BOM.
    assert not raw.startswith(b"\xef\xbb\xbf"), "audit JSONL must not have UTF-8 BOM"

    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 5, f"expected 5 audit lines; got {len(lines)}"

    round_tripped = [AuditEvent.model_validate(json.loads(ln)) for ln in lines]
    for orig, reloaded in zip(originals, round_tripped):
        assert orig.ticket_id == reloaded.ticket_id
        assert orig.event_type == reloaded.event_type
        assert orig.state_from == reloaded.state_from
        assert orig.state_to == reloaded.state_to
        assert orig.payload == reloaded.payload


@pytest.mark.real_fs
async def test_real_fs_isolation_nfr_006_all_writes_under_dot_harness(
    tmp_path: Path,
) -> None:
    """feature_2 real test: NFR-006 enforcement.

    After a full Schema.ensure + 10 ticket saves + 20 audit appends +
    3 mark_interrupted operations, every file written inside `tmp_path` must
    live under `tmp_path/.harness/**`. Nothing should spill into sibling
    directories or the tmp_path root. ~/.harness/ and ~/.claude/ mtimes
    must remain unchanged across the whole operation.
    """
    from harness.domain.ticket import (
        AuditEvent,
        DispatchSpec,
        ExecutionInfo,
        GitContext,
        HilInfo,
        OutputInfo,
        Run,
        Ticket,
        TicketState,
    )
    from harness.persistence.audit import AuditWriter
    from harness.persistence.runs import RunRepository
    from harness.persistence.schema import Schema, resolve_db_path
    from harness.persistence.tickets import TicketRepository

    # --- Pre-snapshot of HOME-side paths (NFR-006 nothing-touched assertion) ---
    home = Path.home()
    home_harness = home / ".harness"
    home_claude = home / ".claude"
    home_harness_pre = home_harness.stat().st_mtime if home_harness.exists() else None
    home_claude_pre = home_claude.stat().st_mtime if home_claude.exists() else None

    # --- Seed a sibling file outside .harness/ so the walk can prove it wasn't
    # disturbed by Harness logic.
    sibling = tmp_path / "unrelated.txt"
    sibling.write_text("pre-existing", encoding="utf-8")
    sibling_mtime_before = sibling.stat().st_mtime

    run_id = "run-S-001"
    db_path = resolve_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await Schema.ensure(conn)
    run_repo = RunRepository(conn)
    await run_repo.create(
        Run(
            id=run_id,
            workdir=str(tmp_path),
            state="running",
            started_at="2026-04-21T10:00:00.000000+00:00",
        )
    )
    tix_repo = TicketRepository(conn)
    audit = AuditWriter(tmp_path / ".harness" / "audit")

    def _mkt(tid: str, state: str) -> Ticket:
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

    # 10 ticket saves (mix states; 3 stay unfinished for later mark_interrupted).
    states = [
        "pending",
        "running",
        "running",
        "completed",
        "completed",
        "failed",
        "classifying",
        "hil_waiting",
        "aborted",
        "retrying",
    ]
    for i, st in enumerate(states, start=1):
        await tix_repo.save(_mkt(f"t-S-{i:02d}", st))

    # 20 audit appends.
    for i in range(20):
        await audit.append(
            AuditEvent(
                ts=f"2026-04-21T10:00:{i:02d}.000000+00:00",
                ticket_id=f"t-S-{(i % 10) + 1:02d}",
                run_id=run_id,
                event_type="state_transition",
                state_from=TicketState.PENDING,
                state_to=TicketState.RUNNING,
            )
        )

    # 3 mark_interrupted (on the classifying / hil_waiting / second running).
    await tix_repo.mark_interrupted("t-S-07")  # classifying → interrupted
    await tix_repo.mark_interrupted("t-S-08")  # hil_waiting → interrupted
    await tix_repo.mark_interrupted("t-S-02")  # running → interrupted

    await audit.close()
    await conn.close()

    # --- NFR-006 assertion: every file under tmp_path is either `unrelated.txt`
    # (pre-existing) or under `tmp_path/.harness/`.
    allowed_prefix = (tmp_path / ".harness").resolve()
    offending: list[str] = []
    for dirpath, _dirs, files in os.walk(tmp_path):
        for fn in files:
            fp = (Path(dirpath) / fn).resolve()
            # Skip the pre-seeded sibling.
            if fp == sibling.resolve():
                continue
            try:
                fp.relative_to(allowed_prefix)
            except ValueError:
                offending.append(str(fp))

    assert not offending, f"NFR-006 violation: files written outside .harness/: {offending}"

    # Sibling untouched.
    assert (
        sibling.stat().st_mtime == sibling_mtime_before
    ), "unrelated file in workdir root must not be touched"

    # HOME-side untouched.
    if home_harness_pre is not None:
        assert (
            home_harness.stat().st_mtime == home_harness_pre
        ), "~/.harness/ must not be touched by F02 (that's F01's panel — NFR-006)"
    if home_claude_pre is not None:
        assert (
            home_claude.stat().st_mtime == home_claude_pre
        ), "~/.claude/ must not be touched by F02 (that's F10's isolation surface)"
