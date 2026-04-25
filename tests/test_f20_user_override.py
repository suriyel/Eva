"""F20 · UserOverride / skip / force-abort unit tests (T20/T21/T22).

[unit] — exercises Skip/ForceAbort REST handlers via direct method invocation.

Feature ref: feature_20

Traces To:
  T20 → FR-029 AC-1 + Interface Contract `skip_anomaly` postcondition
  T21 → FR-029 AC-2 + Interface Contract `force_abort_anomaly`
  T22 → FR-029 + Interface Contract `skip_anomaly` Raises InvalidTicketState
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness.domain.ticket import TicketState


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


# ---- T20 -------------------------------------------------------------------
async def test_t20_skip_anomaly_resets_counter_and_invokes_phase_route(tmp_path: Path) -> None:
    """T20 FUNC/happy: skip_anomaly(ticket retrying) → RecoveryDecision(kind='skipped'); RetryCounter reset; phase_route invoked next."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    # Force a ticket into retrying state (test helper)
    ticket_id = await orch.spawn_test_ticket(
        state=TicketState.RETRYING, skill_hint="long-task-tdd-red"
    )
    orch.retry_counter.inc("long-task-tdd-red", "rate_limit")
    orch.retry_counter.inc("long-task-tdd-red", "rate_limit")
    assert orch.retry_counter.value("long-task-tdd-red") == 2

    invocations_before = orch.phase_route_invoker.invocation_count
    decision = await orch.skip_anomaly(ticket_id)

    assert decision.kind == "skipped"
    assert orch.retry_counter.value("long-task-tdd-red") == 0, "RetryCounter must reset after skip"
    invocations_after = orch.phase_route_invoker.invocation_count
    assert (
        invocations_after > invocations_before
    ), "FR-029 AC-1: phase_route must be invoked immediately after skip"


# ---- T21 -------------------------------------------------------------------
async def test_t21_force_abort_transitions_running_to_aborted(tmp_path: Path) -> None:
    """T21 FUNC/happy: force_abort(ticket running) → ticket immediately aborted; audit force_abort event."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    ticket_id = await orch.spawn_test_ticket(
        state=TicketState.RUNNING, skill_hint="long-task-design"
    )

    decision = await orch.force_abort_anomaly(ticket_id)
    assert decision.kind == "abort"

    ticket = await orch.ticket_repo.get(ticket_id)
    assert (
        ticket.state == TicketState.ABORTED.value or ticket.state == "aborted"
    ), f"force_abort must set state=aborted; got {ticket.state}"
    audit_kinds = [e.event_type for e in orch.audit_writer.captured_events()]
    assert "force_abort" in audit_kinds, f"force_abort audit event missing; got {audit_kinds}"


# ---- T22 -------------------------------------------------------------------
async def test_t22_skip_anomaly_invalid_state_409(tmp_path: Path) -> None:
    """T22 FUNC/error: skip_anomaly on completed ticket → InvalidTicketState 409."""
    from harness.orchestrator.errors import InvalidTicketState
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    ticket_id = await orch.spawn_test_ticket(
        state=TicketState.COMPLETED, skill_hint="long-task-design"
    )

    with pytest.raises(InvalidTicketState) as excinfo:
        await orch.skip_anomaly(ticket_id)
    assert excinfo.value.http_status == 409
