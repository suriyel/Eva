"""F20 Wave 4 (2026-04-27) hard-flush — Test Inventory T01..T60 from feature design §7.

Authoritative tests for F20 Bk-Loop after the Wave 4 protocol-layer rewrite
(IAPI-005 prepare_workdir 前置 + IAPI-006/008 REMOVED + supervisor 主循环
``stream_parser.events(proc)`` → ``ticket_stream.events(ticket_id)`` 迁移).

Every test maps 1:1 to a row in
``docs/features/20-f20-bk-loop-run-orchestrator-recovery-su.md`` §Test Inventory.
The Wave 4 cases (T41/T42/T43/T44 + supervisor renames) are the RED signals
that drive the Green phase. Other rows codify Wave 3 contract behavior that
the rename must preserve.

[unit] coverage scope:
  - Orchestrator (T01..T18, T54..T60): in-memory store + filelock.
  - PhaseRouteInvoker (T06..T13, T38): asyncio.create_subprocess_exec mocked
    at the boundary; ``set_responses`` exercises the test-mode loop.
  - Recovery (T19..T35): pure functions / RetryPolicy / Watchdog with
    spy on ``os.kill``.
  - Supervisor (T41..T44): Wave 4 — assert ``TicketStream.subscribe`` in
    call_trace, prepare_workdir-before-spawn ordering, ``WorkdirPrepareError``
    propagation, ``_FakeTicketStream.events(ticket_id)`` rename.
  - SignalFileWatcher (T39..T40): real ``watchdog.Observer`` on tmp_path.
  - Subprocess (T48..T52, T58): GitTracker + ValidatorRunner non-fork unit
    paths; T52 = allow-list rejection.

[integration] markers (T45..T53): real ``python scripts/phase_route.py``,
real git CLI, real validate scripts, real watchdog Observer.

Real test policy: this feature does NOT trigger IFR-004 (OpenAI-compat
HTTP). LLM provider stays mocked via ``_FakeClassifier`` per the user
constraint recorded in design §Test Inventory header. Provider tally:
mock=51, claude-cli=0, minimax-http=0.
"""

# real_test  --  marker keyword for check_real_tests.py discovery (feature_20)

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.asyncio


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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


def _mock_proc(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0) -> Any:
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.pid = 4242
    proc.wait = AsyncMock(return_value=returncode)
    proc.kill = MagicMock()
    proc.terminate = MagicMock()
    return proc


# ===========================================================================
# Orchestrator — start_run / pause_run / cancel_run / control bus (T01..T18)
# ===========================================================================
# ---- T01 -----------------------------------------------------------------
async def test_t01_start_run_happy_path_lock_and_run_row(tmp_path: Path) -> None:
    """T01 FUNC/happy: legal git workdir → state ∈ {starting,running}; RunLock + run row inserted.

    Traces To: §Interface Contract `start_run` postconditions + §Design Alignment seq msg#1.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)

    status = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    assert status.state in {"starting", "running"}, f"got {status.state!r}"
    assert (
        tmp_path / ".harness" / "run.lock"
    ).exists(), "RunLock file must exist under .harness/"
    rows = await orch.run_repo.list_active()
    assert len(rows) == 1
    assert rows[0].state in {"starting", "running"}
    assert status.run_id == rows[0].id


# ---- T02 -----------------------------------------------------------------
async def test_t02_start_run_rejects_non_git_directory(tmp_path: Path) -> None:
    """T02 FUNC/error: empty (non-git) tmp_path → RunStartError(reason='not_a_git_repo', http=400)."""
    from harness.orchestrator.errors import RunStartError
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    orch = RunOrchestrator.build_test_default(workdir=tmp_path)

    with pytest.raises(RunStartError) as excinfo:
        await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    assert excinfo.value.reason == "not_a_git_repo"
    assert excinfo.value.http_status == 400
    assert not (
        tmp_path / ".harness" / "run.lock"
    ).exists(), "lock must NOT be created on rejection"


# ---- T03 -----------------------------------------------------------------
async def test_t03_start_run_rejects_shell_metacharacters(tmp_path: Path) -> None:
    """T03 FUNC/error (SEC): workdir containing shell metachar → RunStartError(invalid_workdir, 400)."""
    from harness.orchestrator.errors import RunStartError
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    orch = RunOrchestrator.build_test_default(workdir=tmp_path)

    with pytest.raises(RunStartError) as excinfo:
        await orch.start_run(RunStartRequest(workdir=str(tmp_path) + "; rm -rf /"))
    assert excinfo.value.reason in {"invalid_workdir", "not_a_git_repo"}
    assert excinfo.value.http_status == 400


# ---- T04 -----------------------------------------------------------------
async def test_t04_start_run_rejects_empty_workdir(tmp_path: Path) -> None:
    """T04 FUNC/error: empty string workdir → RunStartError(invalid_workdir, 400)."""
    from harness.orchestrator.errors import RunStartError
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    orch = RunOrchestrator.build_test_default(workdir=tmp_path)

    with pytest.raises(RunStartError) as excinfo:
        await orch.start_run(RunStartRequest(workdir=""))
    assert excinfo.value.reason == "invalid_workdir"
    assert excinfo.value.http_status == 400


# ---- T05 -----------------------------------------------------------------
async def test_t05_start_run_already_running_raises_409(tmp_path: Path) -> None:
    """T05 BNDRY/edge: same workdir twice → second raises RunStartError(already_running, 409, ALREADY_RUNNING).

    Traces To: NFR-016 + §Interface Contract `start_run` Raises.
    """
    from harness.orchestrator.errors import RunStartError
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch1 = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch2 = RunOrchestrator.build_test_default(workdir=tmp_path)

    await orch1.start_run(RunStartRequest(workdir=str(tmp_path)))
    with pytest.raises(RunStartError) as excinfo:
        await orch2.start_run(RunStartRequest(workdir=str(tmp_path)))
    assert excinfo.value.reason == "already_running"
    assert excinfo.value.http_status == 409
    assert excinfo.value.error_code == "ALREADY_RUNNING"


# ===========================================================================
# PhaseRouteInvoker (T06..T13, T38)
# ===========================================================================
# ---- T06 -----------------------------------------------------------------
async def test_t06_phase_route_invoke_returns_phase_route_result(tmp_path: Path) -> None:
    """T06 FUNC/happy: stdout JSON {ok:true,next_skill:long-task-design} → PhaseRouteResult preserves fields; invocation_count=1."""
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    invoker.set_responses([{"ok": True, "next_skill": "long-task-design"}])

    result = await invoker.invoke(workdir=tmp_path)

    assert result.ok is True
    assert result.next_skill == "long-task-design"
    assert invoker.invocation_count == 1


# ---- T07 -----------------------------------------------------------------
async def test_t07_phase_route_invoke_exit_nonzero_raises(tmp_path: Path) -> None:
    """T07 FUNC/error: invoker.set_failure(1, 'boom') → PhaseRouteError with exit_code=1 and stderr in message."""
    from harness.orchestrator.errors import PhaseRouteError
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    invoker.set_failure(exit_code=1, stderr="boom")

    with pytest.raises(PhaseRouteError) as excinfo:
        await invoker.invoke(workdir=tmp_path)
    assert excinfo.value.exit_code == 1
    assert "boom" in str(excinfo.value)


# ---- T08 -----------------------------------------------------------------
async def test_t08_phase_route_stdout_not_json_raises_parse_error(tmp_path: Path) -> None:
    """T08 FUNC/error: real-subprocess fixture stdout='not json' exit=0 → PhaseRouteParseError; audit phase_route_parse_error written when audit_writer injected."""
    from harness.orchestrator.errors import PhaseRouteParseError
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    audit_calls: list[tuple[str, dict[str, Any]]] = []

    class _FakeAudit:
        async def append_raw(
            self, run_id: str, kind: str, payload: dict[str, Any], ts: str
        ) -> None:
            audit_calls.append((kind, payload))

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path, audit_writer=_FakeAudit(), run_id="r-1")
    proc = _mock_proc(stdout=b"not a json", returncode=0)

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(PhaseRouteParseError):
            await invoker.invoke(workdir=tmp_path)

    kinds = [c[0] for c in audit_calls]
    assert "phase_route_parse_error" in kinds, f"expected audit kind; got {kinds!r}"


# ---- T09 -----------------------------------------------------------------
async def test_t09_phase_route_relaxed_parsing_default_fields(tmp_path: Path) -> None:
    """T09 BNDRY/relaxed: stdout {'ok':true} (only) → defaults filled; no ValidationError.

    Traces To: NFR-015 + §Interface Contract `PhaseRouteResult` defaults.
    """
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    invoker.set_responses([{"ok": True}])

    result = await invoker.invoke(workdir=tmp_path)

    assert result.ok is True
    assert result.feature_id is None
    assert result.next_skill is None
    assert result.starting_new is False
    assert result.needs_migration is False
    assert result.errors == []


# ---- T10 -----------------------------------------------------------------
async def test_t10_phase_route_extra_fields_are_ignored(tmp_path: Path) -> None:
    """T10 BNDRY/relaxed: extras + future_field present → silently ignored (extra='ignore')."""
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    invoker.set_responses(
        [{"ok": True, "extras": {"x": 1}, "future_field": "v", "next_skill": "x"}]
    )

    result = await invoker.invoke(workdir=tmp_path)

    assert result.ok is True
    assert result.next_skill == "x"
    assert getattr(result, "future_field", None) is None
    extras = getattr(result, "extras", None)
    assert extras in (None, {}), f"extras must be ignored; got {extras!r}"


# ---- T11 -----------------------------------------------------------------
async def test_t11_hotfix_skill_hint_passes_through_unmodified(tmp_path: Path) -> None:
    """T11 FUNC/happy: phase_route returns next_skill='long-task-hotfix' → tool_adapter.spawn_log[0].skill_hint == 'long-task-hotfix'."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.phase_route_invoker.set_responses(
        [
            {"ok": True, "next_skill": "long-task-hotfix", "feature_id": "hotfix-001"},
            {"ok": True, "next_skill": None},  # ST Go terminator
        ]
    )

    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    await orch.wait_for_state(s.run_id, "completed", timeout=4.0)

    spawned = orch.tool_adapter.dispatched_skill_hints()
    assert "long-task-hotfix" in spawned, f"expected 'long-task-hotfix' in spawn log; got {spawned}"


# ---- T12 -----------------------------------------------------------------
async def test_t12_skill_hint_unknown_name_passes_through(tmp_path: Path) -> None:
    """T12 FUNC/happy: build_ticket_command must NOT enum-map skill names; future-skill-x dispatched verbatim."""
    from harness.orchestrator.phase_route import PhaseRouteResult
    from harness.orchestrator.supervisor import build_ticket_command

    res = PhaseRouteResult(ok=True, next_skill="future-skill-x")
    cmd = build_ticket_command(res, parent=None)
    assert cmd.skill_hint == "future-skill-x"

    res2 = PhaseRouteResult(ok=True, next_skill="long-task-finalize")
    cmd2 = build_ticket_command(res2, parent=None)
    assert cmd2.skill_hint == "long-task-finalize"


# ---- T13 -----------------------------------------------------------------
async def test_t13_build_ticket_command_rejects_ok_false() -> None:
    """T13 FUNC/error: PhaseRouteResult(ok=False) → build_ticket_command raises ValueError."""
    from harness.orchestrator.phase_route import PhaseRouteResult
    from harness.orchestrator.supervisor import build_ticket_command

    res = PhaseRouteResult(ok=False, errors=["boom"])
    with pytest.raises(ValueError) as excinfo:
        build_ticket_command(res, parent=None)
    assert "ok=False" in str(excinfo.value) or "ok = False" in str(excinfo.value).replace(" ", "")


# ---- T14 -----------------------------------------------------------------
async def test_t14_pause_run_settles_at_paused(tmp_path: Path) -> None:
    """T14 FUNC/happy: pause_run after start → eventually state=paused; phase_route ≤1 extra invocation.

    Traces To: FR-004 AC-1 / §State Diagram running→paused.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    invocations_before = orch.phase_route_invoker.invocation_count
    await orch.pause_run(s.run_id)
    final = await orch.wait_for_state(s.run_id, "paused", timeout=3.0)

    assert final.state == "paused"
    invocations_after = orch.phase_route_invoker.invocation_count
    assert invocations_after - invocations_before <= 1, (
        f"only the in-flight phase_route may complete; got "
        f"{invocations_after - invocations_before}"
    )


# ---- T15 -----------------------------------------------------------------
async def test_t15_cancel_run_transitions_to_cancelled(tmp_path: Path) -> None:
    """T15 FUNC/happy: cancel_run → state=cancelled; resume endpoint must NOT exist."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    await orch.cancel_run(s.run_id)

    final = await orch.run_repo.get(s.run_id)
    assert final is not None
    assert final.state == "cancelled"
    assert not hasattr(orch, "resume_run"), "FR-004 AC-3: resume must NOT exist"


# ---- T16 -----------------------------------------------------------------
async def test_t16_cancel_after_completed_raises_invalid_state(tmp_path: Path) -> None:
    """T16 FUNC/error: cancel_run on already-completed run → 409-style error (RunNotFound or InvalidRunState).

    Wave 4 design contract: completed runs are terminal; cancel_run must NOT
    silently reset state. Implementation may raise either RunNotFound (if the
    runtime entry was reaped) or an InvalidRunState exception (409 hint).
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.phase_route_invoker.set_responses([{"ok": True, "next_skill": None}])

    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    await orch.wait_for_state(s.run_id, "completed", timeout=4.0)

    # Now request cancel — must raise (cannot bring completed back)
    with pytest.raises(Exception) as excinfo:
        await orch.cancel_run(s.run_id)
    http_status = getattr(excinfo.value, "http_status", None)
    # Either RunNotFound (404) — runtime was cleaned — or 409 InvalidRunState.
    assert http_status in {404, 409}, f"unexpected status {http_status!r}; exc={excinfo.value!r}"

    # And the run row must remain completed (not reset)
    rerun = await orch.run_repo.get(s.run_id)
    assert rerun is not None and rerun.state == "completed"


# ---- T17 -----------------------------------------------------------------
async def test_t17_skip_anomaly_resets_counter_and_invokes_phase_route(tmp_path: Path) -> None:
    """T17 FUNC/happy: skip_anomaly on retrying ticket → RecoveryDecision.kind='skipped'; counter reset; next phase_route invoked."""
    from harness.domain.ticket import TicketState
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    ticket_id = await orch.spawn_test_ticket(
        state=TicketState.RETRYING, skill_hint="long-task-tdd-red"
    )
    orch.retry_counter.inc("long-task-tdd-red", "rate_limit")
    orch.retry_counter.inc("long-task-tdd-red", "rate_limit")
    assert orch.retry_counter.value("long-task-tdd-red") == 2

    invocations_before = orch.phase_route_invoker.invocation_count
    decision = await orch.skip_anomaly(ticket_id)

    assert decision.kind == "skipped"
    assert orch.retry_counter.value("long-task-tdd-red") == 0
    assert orch.phase_route_invoker.invocation_count > invocations_before


# ---- T18 -----------------------------------------------------------------
async def test_t18_force_abort_immediately_aborts_running_ticket(tmp_path: Path) -> None:
    """T18 FUNC/happy: force_abort on running ticket → ticket state=aborted; force_abort audit event captured."""
    from harness.domain.ticket import TicketState
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
    assert ticket is not None
    state_str = ticket.state.value if hasattr(ticket.state, "value") else str(ticket.state)
    assert state_str == "aborted"

    audit_kinds = [e.event_type for e in orch.audit_writer.captured_events()]
    assert "force_abort" in audit_kinds, f"expected force_abort audit; got {audit_kinds!r}"


# ===========================================================================
# AnomalyClassifier (T19..T21)
# ===========================================================================
# ---- T19 -----------------------------------------------------------------
def test_t19_anomaly_classifier_context_overflow_from_stderr() -> None:
    """T19 FUNC/happy: stderr 'context window exceeded' + Verdict(verdict=RETRY, anomaly=None) → cls=CONTEXT_OVERFLOW + retry."""
    from harness.dispatch.classifier.models import ClassifyRequest, Verdict
    from harness.recovery.anomaly import AnomalyClass, AnomalyClassifier

    classifier = AnomalyClassifier()
    req = ClassifyRequest(
        exit_code=1, stderr_tail="context window exceeded", stdout_tail=""
    )
    verdict = Verdict(verdict="RETRY", anomaly=None, backend="rule")

    info = classifier.classify(req, verdict)
    assert info.cls == AnomalyClass.CONTEXT_OVERFLOW
    assert info.next_action == "retry"


# ---- T20 -----------------------------------------------------------------
def test_t20_anomaly_classifier_contract_deviation_aborts_no_retry() -> None:
    """T20 FUNC/error: stdout starts with [CONTRACT-DEVIATION] → cls=SKILL_ERROR + next_action='abort'.

    Traces To: FR-028 AC-1.
    """
    from harness.dispatch.classifier.models import ClassifyRequest, Verdict
    from harness.recovery.anomaly import AnomalyClass, AnomalyClassifier

    classifier = AnomalyClassifier()
    req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="[CONTRACT-DEVIATION] ABC")
    verdict = Verdict(verdict="COMPLETED", anomaly=None, backend="rule")

    info = classifier.classify(req, verdict)
    assert info.cls == AnomalyClass.SKILL_ERROR
    assert info.next_action == "abort"
    assert "[CONTRACT-DEVIATION]" in info.detail


# ---- T21 -----------------------------------------------------------------
def test_t21_anomaly_classifier_contract_deviation_with_leading_whitespace() -> None:
    """T21 BNDRY/edge: stdout '   \\n[CONTRACT-DEVIATION] X' (leading whitespace) → still SKILL_ERROR + abort.

    Validates ``stdout.lstrip().startswith(...)`` semantics — splitlines()[0]
    would miss this case.
    """
    from harness.dispatch.classifier.models import ClassifyRequest, Verdict
    from harness.recovery.anomaly import AnomalyClass, AnomalyClassifier

    classifier = AnomalyClassifier()
    req = ClassifyRequest(
        exit_code=0,
        stderr_tail="",
        stdout_tail="   \n[CONTRACT-DEVIATION] X",
    )
    verdict = Verdict(verdict="COMPLETED", anomaly=None, backend="rule")

    info = classifier.classify(req, verdict)
    assert info.cls == AnomalyClass.SKILL_ERROR
    assert info.next_action == "abort"


# ===========================================================================
# RetryPolicy (T22..T29)
# ===========================================================================
# ---- T22 -----------------------------------------------------------------
def test_t22_retry_policy_context_overflow_sequence() -> None:
    """T22 FUNC/happy: context_overflow at retry_count 0/1/2 → 0.0; retry_count=3 → None.

    Traces To: FR-024 / NFR-003.
    """
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    seq = [policy.next_delay("context_overflow", retry_count=i) for i in range(4)]
    assert seq[0] == 0.0
    assert seq[1] == 0.0
    assert seq[2] == 0.0
    assert seq[3] is None, f"NFR-003: 4th must escalate; got {seq}"


# ---- T23 -----------------------------------------------------------------
def test_t23_retry_policy_rate_limit_sequence_30_120_300_none() -> None:
    """T23 FUNC/happy: rate_limit at retry_count 0..3 → [30, 120, 300, None].

    Traces To: FR-025 / NFR-004.
    """
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    seq = [policy.next_delay("rate_limit", retry_count=i) for i in range(4)]
    assert seq == [30.0, 120.0, 300.0, None], f"got {seq}"


# ---- T24 -----------------------------------------------------------------
def test_t24_retry_policy_scale_factor_compresses_rate_limit() -> None:
    """T24 PERF/timing: RetryPolicy(scale_factor=0.001) compresses 30s → 0.030 ±10%.

    Traces To: NFR-004 ±10% tolerance + Boundary scale_factor.
    """
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy(scale_factor=0.001)
    delay = policy.next_delay("rate_limit", retry_count=0)
    assert delay is not None
    assert 0.027 <= delay <= 0.033, f"expected 0.030 ±10%; got {delay}"


# ---- T25 -----------------------------------------------------------------
def test_t25_retry_policy_network_sequence_0_60_none() -> None:
    """T25 FUNC/happy: network at retry_count 0/1 → [0.0, 60.0]; retry_count=2 → None.

    Traces To: FR-026.
    """
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    assert policy.next_delay("network", retry_count=0) == 0.0
    assert policy.next_delay("network", retry_count=1) == 60.0
    assert policy.next_delay("network", retry_count=2) is None


# ---- T26 -----------------------------------------------------------------
def test_t26_retry_policy_negative_retry_count_raises_value_error() -> None:
    """T26 FUNC/error: retry_count=-1 → ValueError."""
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    with pytest.raises(ValueError):
        policy.next_delay("rate_limit", retry_count=-1)


# ---- T27 -----------------------------------------------------------------
def test_t27_retry_policy_non_int_retry_count_raises_type_error() -> None:
    """T27 FUNC/error: retry_count='0' (string) → TypeError, not silent coercion."""
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    with pytest.raises(TypeError):
        policy.next_delay("rate_limit", retry_count="0")  # type: ignore[arg-type]


# ---- T28 -----------------------------------------------------------------
def test_t28_retry_policy_unknown_class_returns_none() -> None:
    """T28 BNDRY/unknown: cls='future_class' → None (conservative; no infinite retry)."""
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    assert policy.next_delay("future_class", retry_count=0) is None
    assert policy.next_delay("not_a_real_class", retry_count=2) is None


# ---- T29 -----------------------------------------------------------------
def test_t29_retry_policy_skill_error_never_retries() -> None:
    """T29 FUNC/error: skill_error at any retry_count → None (no retry; FR-028)."""
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    assert policy.next_delay("skill_error", retry_count=0) is None
    assert policy.next_delay("skill_error", retry_count=2) is None


# ===========================================================================
# Watchdog (T30..T32)
# ===========================================================================
# ---- T30 -----------------------------------------------------------------
async def test_t30_watchdog_arm_sigterm_then_sigkill() -> None:
    """T30 PERF/timing: Watchdog(sigkill_grace_s=0.05).arm(timeout_s=0.05, is_alive=True) → SIGTERM then SIGKILL recorded.

    Traces To: FR-027 AC-1 + AC-2.
    """
    from harness.recovery.watchdog import Watchdog

    wd = Watchdog(sigkill_grace_s=0.05)
    pid = 99001
    kills: list[tuple[int, int]] = []

    def _spy(p: int, sig: int) -> None:
        kills.append((p, sig))

    with patch("harness.recovery.watchdog.os.kill", side_effect=_spy):
        wd.arm(ticket_id="t-w1", pid=pid, timeout_s=0.05, is_alive=lambda _p: True)
        await asyncio.sleep(0.30)
        wd.disarm(ticket_id="t-w1")

    sigs = [s for (_p, s) in kills]
    assert signal.SIGTERM in sigs, f"expected SIGTERM; got {sigs}"
    assert signal.SIGKILL in sigs, f"expected SIGKILL; got {sigs}"
    assert sigs.index(signal.SIGTERM) < sigs.index(signal.SIGKILL)


# ---- T31 -----------------------------------------------------------------
async def test_t31_watchdog_disarm_cancels_pending_kill() -> None:
    """T31 FUNC/happy: arm then disarm before timeout → no kill calls; task removed."""
    from harness.recovery.watchdog import Watchdog

    wd = Watchdog()
    kills: list[tuple[int, int]] = []

    def _spy(p: int, s: int) -> None:
        kills.append((p, s))

    with patch("harness.recovery.watchdog.os.kill", side_effect=_spy):
        wd.arm(ticket_id="t-w2", pid=99002, timeout_s=1.0, is_alive=lambda _p: True)
        await asyncio.sleep(0.05)
        wd.disarm(ticket_id="t-w2")
        # give cancellation a moment
        await asyncio.sleep(0.05)

    assert kills == [], f"disarm before timeout must produce zero kill calls; got {kills}"


# ---- T32 -----------------------------------------------------------------
def test_t32_watchdog_arm_zero_timeout_raises() -> None:
    """T32 FUNC/error: timeout_s=0 → ValueError (no immediate-kill mode)."""
    from harness.recovery.watchdog import Watchdog

    wd = Watchdog()
    with pytest.raises(ValueError):
        wd.arm(ticket_id="t-w3", pid=1, timeout_s=0, is_alive=lambda _p: False)


# ===========================================================================
# DepthGuard (T33..T35)
# ===========================================================================
# ---- T33 -----------------------------------------------------------------
def test_t33_depth_guard_parent_depth_one_returns_two() -> None:
    """T33 FUNC/happy: ensure_within(1) → 2 (off-by-one canary)."""
    from harness.orchestrator.supervisor import DepthGuard

    assert DepthGuard.ensure_within(1) == 2


# ---- T34 -----------------------------------------------------------------
def test_t34_depth_guard_at_max_depth_raises_ticket_error() -> None:
    """T34 FUNC/error: ensure_within(2) → TicketError(code='depth_exceeded')."""
    from harness.orchestrator.errors import TicketError
    from harness.orchestrator.supervisor import DepthGuard

    with pytest.raises(TicketError) as excinfo:
        DepthGuard.ensure_within(2)
    assert excinfo.value.code == "depth_exceeded"


# ---- T35 -----------------------------------------------------------------
def test_t35_depth_guard_none_parent_returns_zero() -> None:
    """T35 BNDRY/edge: ensure_within(None) → 0."""
    from harness.orchestrator.supervisor import DepthGuard

    assert DepthGuard.ensure_within(None) == 0


# ===========================================================================
# RunLock (T36..T37)
# ===========================================================================
# ---- T36 -----------------------------------------------------------------
async def test_t36_run_lock_acquire_release_reacquire(tmp_path: Path) -> None:
    """T36 FUNC/happy: acquire → release → acquire again succeeds (release isn't permanent)."""
    from harness.orchestrator.run_lock import RunLock

    h1 = await RunLock.acquire(tmp_path, timeout=0.5)
    assert h1 is not None
    RunLock.release(h1)
    # Releasing twice must be safe (idempotent).
    RunLock.release(h1)

    h2 = await RunLock.acquire(tmp_path, timeout=0.5)
    assert h2 is not None
    RunLock.release(h2)


# ---- T37 -----------------------------------------------------------------
async def test_t37_run_lock_timeout_raises_when_held(tmp_path: Path) -> None:
    """T37 FUNC/error: lock already held → second acquire(timeout=0.0) raises RunLockTimeout."""
    from harness.orchestrator.run_lock import RunLock, RunLockTimeout

    h1 = await RunLock.acquire(tmp_path, timeout=0.5)
    try:
        with pytest.raises(RunLockTimeout):
            await RunLock.acquire(tmp_path, timeout=0.0)
    finally:
        RunLock.release(h1)


# ===========================================================================
# PhaseRouteInvoker SEC: argv (T38)
# ===========================================================================
# ---- T38 -----------------------------------------------------------------
def test_t38_phase_route_uses_argv_list_not_shell(tmp_path: Path) -> None:
    """T38 SEC/argv: PhaseRouteInvoker.uses_shell is False; build_argv returns list[str] starting with python.

    Traces To: IFR-003 SEC mapping.
    """
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    assert invoker.uses_shell is False, "shell=True permits command injection"

    argv = invoker.build_argv(workdir=tmp_path)
    assert isinstance(argv, list)
    assert all(isinstance(a, str) for a in argv)
    assert "python" in argv[0]
    assert "--json" in argv, f"--json flag must be present; got {argv}"


# ===========================================================================
# SignalFileWatcher (T39..T40)
# ===========================================================================
# ---- T39 -----------------------------------------------------------------
async def test_t39_signal_watcher_yields_bugfix_request_within_2s(tmp_path: Path) -> None:
    """T39 FUNC/happy: external write of bugfix-request.json → events() yields kind='bugfix_request' within 2s; bus.broadcast_signal also called."""
    from harness.orchestrator.signal_watcher import SignalEvent, SignalFileWatcher

    broadcasted: list[SignalEvent] = []

    class _FakeBus:
        def broadcast_signal(self, event: SignalEvent) -> None:
            broadcasted.append(event)

    watcher = SignalFileWatcher(workdir=tmp_path, control_bus=_FakeBus())
    watcher.start(workdir=tmp_path)
    try:
        target = tmp_path / "bugfix-request.json"

        async def _writer() -> None:
            await asyncio.sleep(0.1)
            target.write_text("{}")

        wt = asyncio.create_task(_writer())
        evt: SignalEvent | None = None
        async with asyncio.timeout(2.0):
            async for e in watcher.events():
                if e.kind == "bugfix_request":
                    evt = e
                    break
        await wt

        assert evt is not None, "FR-048: bugfix_request not yielded within 2s"
        assert Path(evt.path).name == "bugfix-request.json"
        assert any(b.kind == "bugfix_request" for b in broadcasted)
    finally:
        await watcher.stop()


# ---- T40 -----------------------------------------------------------------
async def test_t40_signal_watcher_debounces_rapid_writes(tmp_path: Path) -> None:
    """T40 BNDRY/debounce: 3 rapid writes within 200ms window → exactly 1 event yielded."""
    from harness.orchestrator.signal_watcher import SignalFileWatcher

    class _NullBus:
        def broadcast_signal(self, _e: object) -> None:
            return None

    watcher = SignalFileWatcher(workdir=tmp_path, control_bus=_NullBus(), debounce_ms=200)
    watcher.start(workdir=tmp_path)
    target = tmp_path / "bugfix-request.json"
    received_kinds: list[str] = []

    async def _consume() -> None:
        try:
            async with asyncio.timeout(1.0):
                async for e in watcher.events():
                    received_kinds.append(e.kind)
                    if len(received_kinds) >= 3:
                        return
        except asyncio.TimeoutError:
            return

    async def _flood() -> None:
        await asyncio.sleep(0.05)
        for _ in range(3):
            target.write_text("{}")
            await asyncio.sleep(0.03)

    try:
        flooder = asyncio.create_task(_flood())
        await _consume()
        await flooder
    finally:
        await watcher.stop()

    bugfixes = [k for k in received_kinds if k == "bugfix_request"]
    assert len(bugfixes) == 1, f"expected exactly 1 debounced event; got {len(bugfixes)}"


# ===========================================================================
# Wave 4 supervisor (T41..T44) — RED signals for the protocol-layer rewrite
# ===========================================================================
# ---- T41 -----------------------------------------------------------------
async def test_t41_supervisor_call_trace_subscribes_ticket_stream_not_stream_parser(
    tmp_path: Path,
) -> None:
    """T41 [Wave 4 MOD] FUNC/happy: run_ticket call_trace contains 'TicketStream.subscribe' AND must NOT contain 'StreamParser.events()'.

    Traces To: §Interface Contract `TicketSupervisor.run_ticket` Wave 4 [MOD]
    + §Implementation Summary supervisor.py L95–L100.

    This is the RED that drives the Wave 4 supervisor rewrite (IAPI-008
    REMOVED): subscription source must be ``orch.ticket_stream`` keyed by
    ``ticket_id``, not the legacy ``orch.stream_parser`` keyed by ``proc``.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest, TicketCommand

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    cmd = TicketCommand(
        kind="spawn",
        skill_hint="long-task-design",
        tool="claude",
        run_id=s.run_id,
        parent_ticket=None,
    )
    await orch.ticket_supervisor.run_ticket(cmd)

    trace = orch.call_trace()
    expected_order = [
        "GitTracker.begin",
        "ToolAdapter.prepare_workdir",
        "ToolAdapter.spawn",
        "Watchdog.arm",
        "TicketStream.subscribe",
        "Watchdog.disarm",
        "ClassifierService.classify",
        "GitTracker.end",
        "TicketRepository.save",
    ]
    indices = [
        next((i for i, c in enumerate(trace) if exp in c), -1) for exp in expected_order
    ]
    assert all(i >= 0 for i in indices), (
        f"missing call(s) in trace; expected order {expected_order}; got trace={trace}"
    )
    assert indices == sorted(indices), (
        f"call order violated; got indices={indices} for {expected_order}; trace={trace}"
    )

    # Wave 4 invariant — old marker must be GONE
    assert not any(
        "StreamParser.events" in c for c in trace
    ), f"Wave 4: 'StreamParser.events' must NOT appear in supervisor call_trace; got {trace}"


# ---- T42 -----------------------------------------------------------------
async def test_t42_supervisor_calls_prepare_workdir_then_spawn_with_paths(
    tmp_path: Path,
) -> None:
    """T42 [Wave 4 MOD] FUNC/happy: supervisor invokes ``prepare_workdir`` BEFORE ``spawn``, and the second arg of ``spawn`` is the IsolatedPaths returned from prepare_workdir.

    Traces To: IAPI-005 [Wave 4 MOD] precondition + flowchart prepare_workdir.

    A tracking ToolAdapter records calls; the test asserts ordering and that
    the paths sentinel passed to ``spawn`` is the EXACT object returned by
    ``prepare_workdir``.
    """
    from harness.env.models import IsolatedPaths
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest, TicketCommand

    sentinel_paths = IsolatedPaths(
        cwd=str(tmp_path),
        plugin_dir=str(tmp_path),
        settings_path=str(tmp_path / ".claude" / "settings.json"),
    )

    class _TrackingAdapter:
        def __init__(self) -> None:
            self.calls: list[tuple[str, Any]] = []
            self.spawn_log: list[Any] = []
            self._next_pid = 1000

        async def prepare_workdir(self, spec: Any) -> IsolatedPaths:
            self.calls.append(("prepare_workdir", spec))
            return sentinel_paths

        async def spawn(self, spec: Any, paths: Any) -> Any:
            self.calls.append(("spawn", (spec, paths)))
            self.spawn_log.append(spec)
            self._next_pid += 1

            class _Proc:
                pid = self._next_pid
                exit_code = 0
                result_text = "ok"
                stderr_tail = ""
                stdout_tail = ""

            return _Proc()

        def dispatched_skill_hints(self) -> list[str]:
            return [getattr(c, "skill_hint", None) or "" for c in self.spawn_log]

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.tool_adapter = _TrackingAdapter()
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    await orch.ticket_supervisor.run_ticket(
        TicketCommand(
            kind="spawn",
            skill_hint="long-task-design",
            tool="claude",
            run_id=s.run_id,
            parent_ticket=None,
        )
    )

    names = [n for (n, _) in orch.tool_adapter.calls]
    assert names == ["prepare_workdir", "spawn"], (
        f"prepare_workdir must come before spawn; got {names}"
    )
    spawn_args = orch.tool_adapter.calls[1][1]
    assert spawn_args[1] is sentinel_paths, (
        "spawn must receive the IsolatedPaths returned by prepare_workdir"
    )


# ---- T43 -----------------------------------------------------------------
async def test_t43_supervisor_propagates_workdir_prepare_error(tmp_path: Path) -> None:
    """T43 [Wave 4 MOD] FUNC/error: when ToolAdapter.prepare_workdir raises WorkdirPrepareError, the supervisor must NOT call spawn; the exception propagates."""
    from harness.adapter.errors import WorkdirPrepareError
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest, TicketCommand

    spawn_called: list[Any] = []

    class _FailingAdapter:
        def __init__(self) -> None:
            self.spawn_log: list[Any] = []

        async def prepare_workdir(self, spec: Any) -> Any:
            raise WorkdirPrepareError("triplet write failed")

        async def spawn(self, spec: Any, paths: Any = None) -> Any:
            spawn_called.append(spec)
            raise AssertionError("spawn must NOT be called when prepare_workdir raises")

        def dispatched_skill_hints(self) -> list[str]:
            return []

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.tool_adapter = _FailingAdapter()
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    with pytest.raises(WorkdirPrepareError):
        await orch.ticket_supervisor.run_ticket(
            TicketCommand(
                kind="spawn",
                skill_hint="long-task-design",
                tool="claude",
                run_id=s.run_id,
                parent_ticket=None,
            )
        )

    assert spawn_called == [], "spawn invoked despite prepare_workdir failure"


# ---- T44 -----------------------------------------------------------------
async def test_t44_fake_ticket_stream_signature_takes_ticket_id(tmp_path: Path) -> None:
    """T44 [Wave 4 MOD] FUNC/happy: the orchestrator default ticket_stream test double exposes ``events(ticket_id: str)`` (NOT the old ``events(proc)``); call_trace records 'TicketStream.subscribe' before 'Watchdog.disarm'.

    Traces To: §Implementation Summary `_FakeTicketStream` rename + flowchart
    SubscribeStream node.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest, TicketCommand

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)

    # The Wave 4 default ticket_stream attribute must exist and accept
    # ticket_id (not a process). Calling ``events("t-x")`` is what the
    # supervisor will do; an empty AsyncIterator is acceptable.
    assert hasattr(orch, "ticket_stream"), (
        "Wave 4: RunOrchestrator must expose `ticket_stream` (renamed from stream_parser)"
    )
    iterator = orch.ticket_stream.events("t-x")  # type: ignore[union-attr]
    assert hasattr(iterator, "__aiter__"), "events() must return an async iterator"

    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    await orch.ticket_supervisor.run_ticket(
        TicketCommand(
            kind="spawn",
            skill_hint="long-task-design",
            tool="claude",
            run_id=s.run_id,
            parent_ticket=None,
        )
    )

    trace = orch.call_trace()
    sub_idx = next((i for i, c in enumerate(trace) if "TicketStream.subscribe" in c), -1)
    disarm_idx = next((i for i, c in enumerate(trace) if "Watchdog.disarm" in c), -1)
    assert sub_idx >= 0, f"trace must include TicketStream.subscribe; got {trace}"
    assert disarm_idx >= 0, f"trace must include Watchdog.disarm; got {trace}"
    assert sub_idx < disarm_idx, (
        f"subscribe must precede disarm; got sub_idx={sub_idx}, disarm_idx={disarm_idx}"
    )


# ===========================================================================
# Integration tests (T45..T53) — real subprocess / git / fs / validator
# ===========================================================================
# ---- T45 ---  real_test  --  marker keyword for check_real_tests.py -----
@pytest.mark.real_cli
async def test_t45_real_phase_route_subprocess_returns_phase_route_result(tmp_path: Path) -> None:
    """T45 INTG/subprocess: real ``python scripts/phase_route.py --json`` → PhaseRouteResult with ok in {True,False} and well-typed fields."""
    from harness.orchestrator.phase_route import PhaseRouteInvoker, PhaseRouteResult

    phase_route_script = REPO_ROOT / "scripts" / "phase_route.py"
    assert phase_route_script.is_file(), f"phase_route.py missing at {phase_route_script}"

    _git_init(tmp_path)
    (tmp_path / "feature-list.json").write_text(
        json.dumps(
            {
                "version": 1,
                "real_test": {"marker_pattern": "real_test", "test_dir": "tests"},
                "features": [],
                "current": None,
            }
        )
    )

    invoker = PhaseRouteInvoker(plugin_dir=REPO_ROOT)
    result: PhaseRouteResult = await invoker.invoke(workdir=tmp_path, timeout_s=30.0)

    assert isinstance(result.ok, bool)
    assert hasattr(result, "next_skill")
    assert hasattr(result, "feature_id")
    assert isinstance(result.errors, list)


# ---- T46 -----------------------------------------------------------------
@pytest.mark.real_cli
async def test_t46_real_phase_route_subprocess_exit_nonzero_raises(tmp_path: Path) -> None:
    """T46 INTG/subprocess: phase_route fixture script ``sys.exit(2)`` stderr non-empty → PhaseRouteError(exit_code=2)."""
    from harness.orchestrator.errors import PhaseRouteError
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    plugin_dir = tmp_path / "plugin"
    scripts_dir = plugin_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    fixture = scripts_dir / "phase_route.py"
    fixture.write_text(
        "import sys\nsys.stderr.write('phase route boom\\n')\nsys.exit(2)\n"
    )

    invoker = PhaseRouteInvoker(plugin_dir=plugin_dir)
    with pytest.raises(PhaseRouteError) as excinfo:
        await invoker.invoke(workdir=tmp_path, timeout_s=10.0)
    assert excinfo.value.exit_code == 2
    assert "phase route boom" in str(excinfo.value)


# ---- T47 -----------------------------------------------------------------
@pytest.mark.real_cli
async def test_t47_real_phase_route_subprocess_timeout_kills_process(tmp_path: Path) -> None:
    """T47 INTG/subprocess timeout: fixture sleeps 5s; invoke(timeout_s=0.2) → PhaseRouteError; child process eventually disappears."""
    from harness.orchestrator.errors import PhaseRouteError
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    plugin_dir = tmp_path / "plugin"
    scripts_dir = plugin_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    fixture = scripts_dir / "phase_route.py"
    fixture.write_text("import time\ntime.sleep(5)\n")

    invoker = PhaseRouteInvoker(plugin_dir=plugin_dir)
    t0 = time.monotonic()
    with pytest.raises(PhaseRouteError) as excinfo:
        await invoker.invoke(workdir=tmp_path, timeout_s=0.2)
    elapsed = time.monotonic() - t0

    assert "timeout" in str(excinfo.value).lower()
    assert elapsed < 4.0, (
        f"timeout must kill subprocess well below 5s; got {elapsed:.2f}s"
    )


# ---- T48 -----------------------------------------------------------------
@pytest.mark.real_cli
async def test_t48_real_git_tracker_records_commits_between_begin_and_end(
    tmp_path: Path,
) -> None:
    """T48 INTG/git: real git → begin (head_before) → 1 commit → end → ctx.commits len=1; head_after differs from head_before."""
    from harness.subprocess.git.tracker import GitTracker

    _git_init(tmp_path)
    tracker = GitTracker()
    ctx_begin = await tracker.begin(ticket_id="t-1", workdir=tmp_path)
    head_before = ctx_begin.head_before
    assert head_before is not None and len(head_before) == 40

    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=a@b",
            "-c",
            "user.name=A",
            "commit",
            "-q",
            "-m",
            "feat-x",
        ],
        cwd=tmp_path,
        check=True,
    )

    ctx_end = await tracker.end(ticket_id="t-1", workdir=tmp_path)
    assert ctx_end.head_after is not None
    assert ctx_end.head_after != head_before, "head must advance"
    assert len(ctx_end.commits) == 1, f"expected 1 commit; got {len(ctx_end.commits)}"
    assert ctx_end.commits[0].subject == "feat-x"


# ---- T49 -----------------------------------------------------------------
async def test_t49_git_tracker_head_sha_in_non_repo_raises(tmp_path: Path) -> None:
    """T49 INTG/git/error: tmp_path with no .git → GitError(code='not_a_repo', exit_code=128)."""
    from harness.subprocess.git.tracker import GitError, GitTracker

    tracker = GitTracker()
    with pytest.raises(GitError) as excinfo:
        await tracker.head_sha(workdir=tmp_path)
    assert excinfo.value.code == "not_a_repo"
    assert excinfo.value.exit_code == 128


# ---- T50 -----------------------------------------------------------------
@pytest.mark.real_cli
async def test_t50_real_validator_runner_happy_path(tmp_path: Path) -> None:
    """T50 INTG/validator/subprocess: real ``python scripts/validate_features.py --json`` → ValidationReport with script_exit_code in {0,1,2} and duration_ms > 0."""
    from harness.subprocess.validator.runner import ValidatorRunner
    from harness.subprocess.validator.schemas import ValidateRequest

    assert (REPO_ROOT / "scripts" / "validate_features.py").is_file()

    fl = tmp_path / "feature-list.json"
    fl.write_text(
        json.dumps(
            {
                "version": 1,
                "real_test": {"marker_pattern": "real_test", "test_dir": "tests"},
                "features": [],
                "current": None,
            }
        )
    )

    runner = ValidatorRunner(plugin_dir=REPO_ROOT)
    report = await runner.run(
        ValidateRequest(
            path=str(fl),
            script="validate_features",
            workdir=tmp_path,
            timeout_s=30.0,
        )
    )
    assert report.script_exit_code in (0, 1, 2)
    assert report.duration_ms > 0


# ---- T51 -----------------------------------------------------------------
@pytest.mark.real_cli
async def test_t51_real_validator_subprocess_exit_nonzero_captures_stderr(
    tmp_path: Path,
) -> None:
    """T51 INTG/validator/error: fixture script writes to stderr and exits 1 → ValidationReport(ok=False, exit=1, issues contain 'traceback')."""
    from harness.subprocess.validator.runner import ValidatorRunner
    from harness.subprocess.validator.schemas import ValidateRequest

    plugin_dir = tmp_path / "plugin"
    scripts_dir = plugin_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    fixture = scripts_dir / "validate_features.py"
    fixture.write_text(
        "import sys\nsys.stderr.write('traceback... validate boom\\n')\nsys.exit(1)\n"
    )

    fl = tmp_path / "feature-list.json"
    fl.write_text("{}")

    runner = ValidatorRunner(plugin_dir=plugin_dir)
    report = await runner.run(
        ValidateRequest(
            path=str(fl),
            script="validate_features",
            workdir=tmp_path,
            timeout_s=10.0,
        )
    )
    assert report.ok is False
    assert report.script_exit_code == 1
    msgs = " ".join(i.message for i in report.issues)
    assert "traceback" in msgs.lower(), f"stderr must surface in issues; got {report.issues}"


# ---- T52 -----------------------------------------------------------------
@pytest.mark.asyncio(loop_scope="function")
async def test_t52_validator_request_unknown_script_rejected_at_schema(tmp_path: Path) -> None:
    """T52 FUNC/error (SEC): ValidateRequest(script='malicious_script') → schema rejects (allow-list enforced).

    The Literal allow-list on ``ValidateRequest.script`` blocks command
    injection at the pydantic boundary; runner code never sees the bad value.
    """
    from pydantic import ValidationError

    from harness.subprocess.validator.schemas import ValidateRequest

    with pytest.raises(ValidationError):
        ValidateRequest(path=str(tmp_path / "x.json"), script="malicious_script")  # type: ignore[arg-type]


# ---- T53 -----------------------------------------------------------------
@pytest.mark.real_fs
async def test_t53_real_signal_watcher_yields_increment_request(tmp_path: Path) -> None:
    """T53 INTG/filesystem/signal: real watchdog Observer + write of increment-request.json → events() yields kind='increment_request' within 2s."""
    from harness.orchestrator.signal_watcher import SignalEvent, SignalFileWatcher

    class _NullBus:
        def broadcast_signal(self, _e: SignalEvent) -> None:
            return None

    watcher = SignalFileWatcher(workdir=tmp_path, control_bus=_NullBus())
    watcher.start(workdir=tmp_path)
    try:
        target = tmp_path / "increment-request.json"

        async def _writer() -> None:
            await asyncio.sleep(0.1)
            target.write_text("{}")

        wt = asyncio.create_task(_writer())
        evt: SignalEvent | None = None
        async with asyncio.timeout(2.0):
            async for e in watcher.events():
                if e.kind == "increment_request":
                    evt = e
                    break
        await wt

        assert evt is not None, "FR-048: increment_request not yielded within 2s"
        assert Path(evt.path).name == "increment-request.json"
    finally:
        await watcher.stop()


# ===========================================================================
# RunControlBus (T54..T57)
# ===========================================================================
# ---- T54 -----------------------------------------------------------------
async def test_t54_run_control_bus_skip_without_target_raises_invalid(tmp_path: Path) -> None:
    """T54 FUNC/error: RunControlCommand(kind='skip_ticket', target_ticket_id=None) → InvalidCommand 400."""
    from harness.orchestrator.bus import RunControlBus, RunControlCommand
    from harness.orchestrator.errors import InvalidCommand

    bus = RunControlBus.build_test_default()
    with pytest.raises(InvalidCommand) as excinfo:
        await bus.submit(RunControlCommand(kind="skip_ticket", target_ticket_id=None))
    assert excinfo.value.http_status == 400


# ---- T55 -----------------------------------------------------------------
async def test_t55_run_control_bus_unbound_orchestrator_rejects(tmp_path: Path) -> None:
    """T55 FUNC/error: RunControlBus without attach_orchestrator → submit raises InvalidCommand."""
    from harness.orchestrator.bus import RunControlBus, RunControlCommand
    from harness.orchestrator.errors import InvalidCommand

    bus = RunControlBus()
    with pytest.raises(InvalidCommand):
        await bus.submit(
            RunControlCommand(kind="start", workdir=str(tmp_path))
        )


# ---- T56 -----------------------------------------------------------------
async def test_t56_run_control_bus_start_dispatches_to_orchestrator(tmp_path: Path) -> None:
    """T56 FUNC/happy: bus attached → submit(start) → ack.accepted=True; current_state ∈ {starting,running}."""
    from harness.orchestrator.bus import RunControlCommand
    from harness.orchestrator.run import RunOrchestrator

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    bus = orch.control_bus
    bus.attach_orchestrator(orch)

    ack = await bus.submit(RunControlCommand(kind="start", workdir=str(tmp_path)))
    assert ack.accepted is True
    assert ack.current_state in {"starting", "running"}, ack.current_state


# ---- T57 -----------------------------------------------------------------
async def test_t57_broadcast_anomaly_reaches_subscribers(tmp_path: Path) -> None:
    """T57 FUNC/happy: bus.broadcast_anomaly(Escalated, cls=rate_limit, retry_count=3) → subscribe_anomaly queue receives envelope with kind='Escalated' and payload.cls='rate_limit'."""
    from harness.orchestrator.bus import AnomalyEvent, RunControlBus

    bus = RunControlBus.build_test_default()
    queue = bus.subscribe_anomaly()
    bus.broadcast_anomaly(
        AnomalyEvent(kind="Escalated", cls="rate_limit", retry_count=3, ticket_id="t-1")
    )

    # Allow event loop to deliver
    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert msg["kind"] == "Escalated"
    payload = msg.get("payload", {})
    assert payload.get("cls") == "rate_limit"
    assert payload.get("retry_count") == 3


# ===========================================================================
# T58 — supervisor persists git fields
# ===========================================================================
# ---- T58 -----------------------------------------------------------------
async def test_t58_run_ticket_persists_git_head_before_and_after(tmp_path: Path) -> None:
    """T58 FUNC/happy: after run_ticket completes, ticket_repo.get(ticket_id).git carries head_before and head_after (real git CLI on tmp_path)."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest, TicketCommand

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    cmd = TicketCommand(
        kind="spawn",
        skill_hint="long-task-design",
        tool="claude",
        run_id=s.run_id,
        parent_ticket=None,
    )
    outcome = await orch.ticket_supervisor.run_ticket(cmd)

    ticket = await orch.ticket_repo.get(outcome.ticket_id)
    assert ticket is not None
    assert ticket.git is not None
    assert ticket.git.head_before is not None and len(ticket.git.head_before) == 40
    assert ticket.git.head_after is not None and len(ticket.git.head_after) == 40


# ===========================================================================
# T59 — 14 skill superset
# ===========================================================================
# ---- T59 -----------------------------------------------------------------
async def test_t59_run_dispatches_14_skill_superset(tmp_path: Path) -> None:
    """T59 FUNC/happy: orchestrator dispatches the canonical 14-skill set verbatim — no enum mapping; superset assertion (FR-047 AC-1/2)."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    fourteen = [
        "long-task-using",
        "long-task-requirements",
        "long-task-ucd",
        "long-task-design",
        "long-task-ats",
        "long-task-init",
        "long-task-feature-design",
        "long-task-work-tdd",
        "long-task-feature-st",
        "long-task-quality",
        "long-task-st",
        "long-task-finalize",
        "long-task-hotfix",
        "long-task-increment",
    ]
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.phase_route_invoker.set_responses(
        [{"ok": True, "next_skill": s, "feature_id": None} for s in fourteen]
        + [{"ok": True, "next_skill": None}]
    )
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    await orch.wait_for_state(s.run_id, "completed", timeout=10.0)

    dispatched = orch.tool_adapter.dispatched_skill_hints()
    missing = set(fourteen) - set(dispatched)
    assert not missing, f"FR-047 AC-1: dispatched set must ⊇ 14 skills; missing={missing}"


# ===========================================================================
# T60 — cancel_run after completed already covered by T16; this row checks
# that a duplicate cancel request cannot be issued through the public API
# without a 4xx response (no silent reset).
# ===========================================================================
# ---- T60 -----------------------------------------------------------------
async def test_t60_cancel_after_completed_keeps_state(tmp_path: Path) -> None:
    """T60 FUNC/error (state machine): cancel_run on completed run does NOT mutate run row to 'cancelled'."""
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.phase_route_invoker.set_responses([{"ok": True, "next_skill": None}])

    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    await orch.wait_for_state(s.run_id, "completed", timeout=4.0)

    # Cancel after completed — must error (RunNotFound / InvalidRunState).
    raised = False
    try:
        await orch.cancel_run(s.run_id)
    except Exception as exc:
        raised = True
        # Either 404 or 409 hint
        assert getattr(exc, "http_status", None) in {404, 409}, exc

    final = await orch.run_repo.get(s.run_id)
    assert final is not None
    assert final.state == "completed", (
        "completed state must not be reset to 'cancelled' "
        f"(raised={raised}; got state={final.state})"
    )
