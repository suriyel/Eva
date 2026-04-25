"""F20 · RunOrchestrator unit tests (Test Inventory T01/T02/T09/T10/T35/T39/T40/T46/T48/T49).

[unit] — uses in-memory stores; tmp_path for git repo fixtures; ToolAdapter / phase_route
mocked at module boundary. Real subprocess / DB / WS exercised by tests/integration/*.

Feature ref: feature_20

Traces To:
  T01 → §Interface Contract `start_run` postcondition + §Design Alignment seq msg#1-7
  T02 → §State Diagram Idle→Failed
  T09 → §State Diagram Running→PausePending→Paused
  T10 → §Interface Contract `cancel_run` postcondition
  T35 → NFR-016 already_running 409
  T39 → §State Diagram Running→Cancelling
  T40 → §Interface Contract `submit_command` Raises InvalidCommand
  T46 → §State Diagram Running→Completed (ST Go)
  T48 → §Implementation flow branch#3 (CheckPause)
  T49 → §Implementation flow branch#5 (PrOk no)
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Module under test (does not exist yet → ImportError is the expected RED).
# ---------------------------------------------------------------------------
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
            "init",
        ],
        cwd=workdir,
        check=True,
    )


# ---- T01 -------------------------------------------------------------------
async def test_t01_start_run_happy_path_enters_running(tmp_path: Path) -> None:
    """T01 FUNC/happy: legal git workdir → start_run returns starting/running ≤5s + lock + run row."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.errors import RunStartError  # noqa: F401
    from harness.orchestrator.schemas import RunStartRequest, RunStatus

    _git_init(tmp_path)

    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    started_at = asyncio.get_event_loop().time()
    status: RunStatus = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    elapsed = asyncio.get_event_loop().time() - started_at

    assert elapsed <= 5.0, f"start_run took {elapsed}s, FR-001 AC-1 soft target ≤5s"
    assert status.state in {"starting", "running"}, f"state={status.state} not in starting/running"
    assert status.workdir == str(tmp_path)
    assert (
        tmp_path / ".harness" / "run.lock"
    ).exists(), "RunLock file must be created in workdir/.harness/"
    # runs row inserted
    rows = await orch.run_repo.list_active()
    assert len(rows) == 1 and rows[0].state in {"starting", "running"}


# ---- T02 -------------------------------------------------------------------
async def test_t02_start_run_rejects_non_git_repo(tmp_path: Path) -> None:
    """T02 FUNC/error: non-git workdir → RunStartError(reason='not_a_git_repo'); no row, no lock."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.errors import RunStartError
    from harness.orchestrator.schemas import RunStartRequest

    # tmp_path is empty (not a git repo)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)

    with pytest.raises(RunStartError) as excinfo:
        await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    assert (
        excinfo.value.reason == "not_a_git_repo"
    ), f"expected reason='not_a_git_repo', got {excinfo.value.reason!r}"
    assert not (
        tmp_path / ".harness" / "run.lock"
    ).exists(), "lock must NOT be created on rejection"
    rows = await orch.run_repo.list_active()
    assert rows == [], "no run row on non-git rejection"


# ---- T09 -------------------------------------------------------------------
async def test_t09_pause_run_transitions_via_pause_pending(tmp_path: Path) -> None:
    """T09 FUNC/happy: pause_run sets pause_pending; current ticket completes → state=paused; phase_route NOT invoked."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    status = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    run_id = status.run_id

    # Track phase_route invocations after pause
    invocations_before = orch.phase_route_invoker.invocation_count
    paused_status = await orch.pause_run(run_id)
    # Allow current ticket to drain
    await orch.wait_for_state(run_id, "paused", timeout=2.0)
    invocations_after = orch.phase_route_invoker.invocation_count

    assert paused_status.state in {"paused", "pause_pending"}
    final = await orch.run_repo.get(run_id)
    assert final.state == "paused"
    # No additional phase_route after pause request
    assert invocations_after <= invocations_before + 1, (
        f"phase_route invoked {invocations_after - invocations_before}x after pause "
        "— FR-004 AC-1 forbids dispatching new tickets after pause"
    )


# ---- T10 -------------------------------------------------------------------
async def test_t10_cancel_run_no_resume_endpoint(tmp_path: Path) -> None:
    """T10 FUNC/happy: cancel → state=cancelled; subsequent start_run creates a NEW run (no resume)."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    s1 = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    run_id_1 = s1.run_id
    await orch.cancel_run(run_id_1)

    final_old = await orch.run_repo.get(run_id_1)
    assert final_old.state == "cancelled"

    # Resume must NOT exist as method
    assert not hasattr(
        orch, "resume_run"
    ), "FR-004 AC-3: resume endpoint must NOT exist for cancelled runs"

    # New start_run creates new run row, distinct id
    s2 = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    assert s2.run_id != run_id_1, "second start_run must spawn a fresh run, not resume"


# ---- T35 -------------------------------------------------------------------
async def test_t35_start_run_already_running_409(tmp_path: Path) -> None:
    """T35 FUNC/error: filelock held → RunStartError(reason='already_running') + http=409 hint."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.errors import RunStartError
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch1 = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch2 = RunOrchestrator.build_test_default(workdir=tmp_path)

    await orch1.start_run(RunStartRequest(workdir=str(tmp_path)))
    with pytest.raises(RunStartError) as excinfo:
        await orch2.start_run(RunStartRequest(workdir=str(tmp_path)))

    assert excinfo.value.reason == "already_running"
    assert excinfo.value.http_status == 409, "NFR-016: must surface 409"
    assert excinfo.value.error_code == "ALREADY_RUNNING"


# ---- T39 -------------------------------------------------------------------
async def test_t39_run_control_bus_cancel_command(tmp_path: Path) -> None:
    """T39 FUNC/happy: RunControlCommand(kind='cancel') → cancel_run dispatched + ack(accepted=True)."""
    from harness.orchestrator.bus import RunControlBus, RunControlCommand
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    bus: RunControlBus = orch.control_bus
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    ack = await bus.submit(RunControlCommand(kind="cancel", run_id=s.run_id))
    assert ack.accepted is True
    assert ack.current_state in {"cancelling", "cancelled"}, ack.current_state
    # Subsequent run state must be cancelled
    final = await orch.wait_for_state(s.run_id, "cancelled", timeout=2.0)
    assert final.state == "cancelled"


# ---- T40 -------------------------------------------------------------------
async def test_t40_run_control_bus_invalid_command_400(tmp_path: Path) -> None:
    """T40 FUNC/error: RunControlCommand(kind='skip_ticket', target_ticket_id=None) → InvalidCommand 400."""
    from harness.orchestrator.bus import RunControlBus, RunControlCommand
    from harness.orchestrator.errors import InvalidCommand
    from harness.orchestrator.run import RunOrchestrator

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    bus: RunControlBus = orch.control_bus

    with pytest.raises(InvalidCommand) as excinfo:
        await bus.submit(RunControlCommand(kind="skip_ticket", target_ticket_id=None))
    assert excinfo.value.http_status == 400


# ---- T46 -------------------------------------------------------------------
async def test_t46_phase_route_no_next_skill_completes_run(tmp_path: Path) -> None:
    """T46 FUNC/happy: phase_route returns next_skill=None (all features passing) → state=completed."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    # Configure injectable phase_route mock to return ok=True next_skill=None
    orch.phase_route_invoker.set_responses(
        [
            {"ok": True, "next_skill": None, "feature_id": None},
        ]
    )
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    final = await orch.wait_for_state(s.run_id, "completed", timeout=3.0)
    assert final.state == "completed", f"expected completed, got {final.state}"


# ---- T48 -------------------------------------------------------------------
async def test_t48_run_loop_pause_pending_skips_phase_route(tmp_path: Path) -> None:
    """T48 FUNC/happy: pause_pending=True after current ticket → MarkPaused; PhaseRouteInvoker.invoke NOT called next iter."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)

    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    invocations_before = orch.phase_route_invoker.invocation_count
    orch.set_pause_pending(s.run_id, True)

    # Wait for current ticket to settle
    final = await orch.wait_for_state(s.run_id, "paused", timeout=3.0)
    assert final.state == "paused"

    invocations_after = orch.phase_route_invoker.invocation_count
    # At most one final invocation after the marker; subsequent loop iter must not call again
    assert invocations_after - invocations_before <= 1


# ---- T49 -------------------------------------------------------------------
async def test_t49_phase_route_exit_nonzero_pauses_and_escalates(tmp_path: Path) -> None:
    """T49 FUNC/error: phase_route exit=1 → state=paused + Escalated(reason='phase_route_error') broadcast."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.phase_route_invoker.set_failure(exit_code=1, stderr="feature-list.json missing")

    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    final = await orch.wait_for_state(s.run_id, "paused", timeout=3.0)
    assert final.state == "paused"

    events = orch.control_bus.captured_anomaly_events()
    escalated = [e for e in events if e.kind == "Escalated"]
    assert escalated, f"Escalated event missing; got {[e.kind for e in events]}"
    assert escalated[-1].reason == "phase_route_error"
