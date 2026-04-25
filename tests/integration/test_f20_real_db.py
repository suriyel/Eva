"""Integration test for F20 · real aiosqlite ticket persistence (T47).

[integration] — uses REAL aiosqlite database against tmp_path.

Feature ref: feature_20

Traces To:
  T47 → §Interface Contract `run_ticket` end-to-end + IAPI-011/009 real sqlite
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.real_fs, pytest.mark.asyncio]


def _git_init(workdir: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=a@b",
            "-c",
            "user.name=A",
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            "i",
        ],
        cwd=workdir,
        check=True,
    )


@pytest.mark.real_fs
async def test_t47_run_ticket_persists_to_real_sqlite(tmp_path: Path) -> None:
    """T47 INTG/db (feature_20): end-to-end ticket → real aiosqlite tickets table row + audit jsonl ≥3 state_transition rows."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)

    # Use real aiosqlite (no in-memory mock)
    orch = RunOrchestrator.build_real_persistence(workdir=tmp_path)
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    await orch.wait_for_state(s.run_id, "completed", timeout=10.0)

    # Verify ticket row in real sqlite
    db_path = tmp_path / ".harness" / "tickets.sqlite3"
    assert db_path.exists(), f"real sqlite DB missing at {db_path}"

    import aiosqlite

    async with aiosqlite.connect(str(db_path)) as conn:
        cur = await conn.execute(
            "SELECT id, state, payload FROM tickets WHERE run_id = ?", (s.run_id,)
        )
        rows = await cur.fetchall()

    assert len(rows) >= 1, "at least one ticket row required"
    # FR-007 fields present in payload
    payload = json.loads(rows[0][2])
    for required in ("state", "skill_hint", "tool", "dispatch", "execution"):
        assert (
            required in payload
        ), f"ticket payload missing FR-007 field {required!r}; got keys={list(payload.keys())}"

    # audit jsonl
    audit_dir = tmp_path / ".harness" / "audit"
    audit_files = list(audit_dir.glob("*.jsonl")) if audit_dir.exists() else []
    assert audit_files, f"audit/<run_id>.jsonl missing under {audit_dir}"
    audit_lines = audit_files[0].read_text().splitlines()
    state_events = [ln for ln in audit_lines if "state_transition" in ln]
    assert (
        len(state_events) >= 3
    ), f"expected ≥3 state_transition audit events; got {len(state_events)}: {audit_lines}"
