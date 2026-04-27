"""F20 · TicketSupervisor + IAPI-002 (commits/diff/files) unit tests.

[unit] — ToolAdapter / TicketStream / ClassifierService injected as fakes.
T47 (real sqlite end-to-end) lives in tests/integration/test_f20_real_db.py.
T50 (real REST+WS) lives in tests/integration/test_f20_real_rest_ws.py.

Feature ref: feature_20

Traces To:
  T30 → FR-047 AC-1 14-skill end-to-end dry-run
  T42 → §Interface Contract `DepthGuard.ensure_within` + Boundary depth=2
  T43 → §Interface Contract `list_commits` (IAPI-002 → F22)
  T44 → §Interface Contract `load_diff` Raises DiffNotFound
  T45 → §Interface Contract `broadcast_signal` (IAPI-001) WS envelope

[Wave 4 deletion 2026-04-27] — old test_t41 (asserted ``StreamParser.events``
in supervisor call_trace) is deprecated by F20 design Wave 4 (IAPI-008 REMOVED;
supervisor must subscribe ``ticket_stream.events(ticket_id)`` instead). The
canonical Wave 4 T41 lives in ``tests/test_f20_w4_design.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


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


# ---- T30 -------------------------------------------------------------------
async def test_t30_run_dispatches_14_skill_subset(tmp_path: Path) -> None:
    """T30 FUNC/happy: 14 phase_route outputs → 14 tickets dispatched; skill_hints superset of 14-skill canonical set."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)

    fourteen = [
        "using-long-task",
        "long-task-requirements",
        "long-task-ucd",
        "long-task-design",
        "long-task-ats",
        "long-task-init",
        "long-task-work-design",
        "long-task-work-tdd",
        "long-task-work-st",
        "long-task-quality",
        "long-task-feature-st",
        "long-task-st",
        "long-task-finalize",
        "long-task-hotfix",
    ]

    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.phase_route_invoker.set_responses(
        [{"ok": True, "next_skill": s, "feature_id": None} for s in fourteen]
        + [{"ok": True, "next_skill": None}]  # ST Go terminator
    )

    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    await orch.wait_for_state(s.run_id, "completed", timeout=5.0)

    dispatched = orch.tool_adapter.dispatched_skill_hints()
    assert set(dispatched) >= set(
        fourteen
    ), f"FR-047 AC-1: expected ⊇ 14-skill set; missing={set(fourteen) - set(dispatched)}"


# ---- T41 (deprecated 2026-04-27 Wave 4 hard-flush) -------------------------
# Old supervisor call-trace assertion expected ``StreamParser.events`` — Wave 4
# (IAPI-008 REMOVED; IAPI-006 byte_queue downgraded) requires the supervisor to
# subscribe ``ticket_stream.events(ticket_id)`` from the broadcaster instead.
# The replacement lives in tests/test_f20_w4_design.py::test_t41_*.


# ---- T42 -------------------------------------------------------------------
async def test_t42_depth_guard_rejects_depth_3(tmp_path: Path) -> None:
    """T42 BNDRY/edge: parent.depth=2 → child spawn raises TicketError(code='depth_exceeded'); ToolAdapter.spawn NOT called."""
    from harness.orchestrator.errors import TicketError
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest, TicketCommand

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    parent_id = await orch.spawn_test_ticket(skill_hint="long-task-design", depth=2)
    spawns_before = len(orch.tool_adapter.dispatched_skill_hints())

    with pytest.raises(TicketError) as excinfo:
        await orch.ticket_supervisor.run_ticket(
            TicketCommand(
                kind="spawn",
                skill_hint="long-task-tdd-red",
                tool="claude",
                run_id=s.run_id,
                parent_ticket=parent_id,
            )
        )

    assert excinfo.value.code == "depth_exceeded"
    spawns_after = len(orch.tool_adapter.dispatched_skill_hints())
    assert spawns_after == spawns_before, "spawn must NOT be invoked when depth_exceeded"


# ---- T43 -------------------------------------------------------------------
async def test_t43_list_commits_filters_and_orders_desc(tmp_path: Path) -> None:
    """T43 FUNC/happy: 3 tickets with 1 commit each in run-1 → list_commits(run_id='run-1') returns 3 GitCommit DESC by committed_at."""
    from harness.api.git import CommitListService

    svc = CommitListService.build_test_default()
    await svc.seed_test_commits(
        [
            {
                "sha": "a" * 40,
                "subject": "ticket1",
                "committed_at": "2026-04-21T10:00:00Z",
                "run_id": "run-1",
            },
            {
                "sha": "b" * 40,
                "subject": "ticket2",
                "committed_at": "2026-04-21T11:00:00Z",
                "run_id": "run-1",
            },
            {
                "sha": "c" * 40,
                "subject": "ticket3",
                "committed_at": "2026-04-21T12:00:00Z",
                "run_id": "run-1",
            },
            {
                "sha": "d" * 40,
                "subject": "other-run",
                "committed_at": "2026-04-21T13:00:00Z",
                "run_id": "run-2",
            },
        ]
    )

    commits = await svc.list_commits(run_id="run-1")
    assert len(commits) == 3, f"expected 3 commits filtered to run-1; got {len(commits)}"
    times = [c.committed_at for c in commits]
    assert times == sorted(times, reverse=True), f"DESC ordering violated; got {times}"
    subjects = [c.subject for c in commits]
    assert subjects == ["ticket3", "ticket2", "ticket1"]


# ---- T44 -------------------------------------------------------------------
async def test_t44_load_diff_unknown_sha_raises_diff_not_found(tmp_path: Path) -> None:
    """T44 FUNC/error: sha not in repo → DiffNotFound 404."""
    from harness.api.git import DiffLoader, DiffNotFound

    _git_init(tmp_path)
    loader = DiffLoader(workdir=tmp_path)
    bogus_sha = "deadbeef" * 5  # 40-hex but not in repo

    with pytest.raises(DiffNotFound) as excinfo:
        await loader.load_diff(bogus_sha)
    assert excinfo.value.http_status == 404


# ---- T45 -------------------------------------------------------------------
async def test_t45_broadcast_signal_ws_envelope_shape(tmp_path: Path) -> None:
    """T45 FUNC/happy: broadcast_signal(SignalFileChanged) → WS clients receive {kind:'signal_file_changed', payload:{path, kind:'bugfix_request'}}."""
    from harness.orchestrator.bus import RunControlBus
    from harness.orchestrator.signal_watcher import SignalEvent

    bus = RunControlBus.build_test_default()
    sub = bus.subscribe_signal_test_client()

    bus.broadcast_signal(
        SignalEvent(kind="bugfix_request", path="/tmp/workdir/bugfix-request.json", mtime=0.0)
    )
    msgs = sub.received_messages()
    assert len(msgs) == 1, f"expected 1 WS envelope; got {len(msgs)}"
    env = msgs[0]
    assert env["kind"] == "signal_file_changed"
    assert env["payload"]["kind"] == "bugfix_request"
    assert env["payload"]["path"].endswith("bugfix-request.json")
