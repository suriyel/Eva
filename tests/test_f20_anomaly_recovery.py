"""F20 · Recovery (AnomalyClassifier / RetryPolicy / Watchdog) unit tests.

[unit] — pure functions / in-memory counters; signals (SIGTERM/SIGKILL) traced via
os.kill spy. T14 (real asyncio.sleep timing) is in tests/integration/test_f20_real_subprocess.py.

Feature ref: feature_20

Traces To:
  T11 → FR-024 AC-1 + RetryPolicy.next_delay(context_overflow) + State Diagram ContextOverflow→Retrying
  T12 → NFR-003 + FR-024 AC-2 (4-shot escalate; context_overflow→Escalated)
  T13 → NFR-004 + FR-025 AC-1 + Boundary RetryPolicy(rate_limit) → [30,120,300,None]
  T15 → FR-026 AC-1/2/3 RetryPolicy(network) → [0,60,None]
  T16 → FR-027 AC-1 Watchdog SIGTERM
  T17 → FR-027 AC-2 Watchdog SIGKILL after SIGTERM+5s
  T18 → FR-028 AC-1 skill_error → aborted, no retry
  T19 → FR-028 AC-2 skill_error → run paused
"""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.asyncio


# ---- T11 -------------------------------------------------------------------
async def test_t11_context_overflow_retry_zero_delay_and_increment() -> None:
    """T11 FUNC/happy: context_overflow at retry_count=0 → next_delay=0.0 (immediate spawn); retry_count→1."""
    from harness.recovery.retry import RetryCounter, RetryPolicy

    policy = RetryPolicy()
    counter = RetryCounter()

    delay = policy.next_delay("context_overflow", retry_count=0)
    assert (
        delay == 0.0
    ), f"context_overflow first retry must be 0.0s (immediate new session); got {delay}"

    new_count = counter.inc("long-task-tdd-red", "context_overflow")
    assert new_count == 1, "RetryCounter.inc must return 1 after first inc"


# ---- T12 -------------------------------------------------------------------
async def test_t12_context_overflow_4th_attempt_escalates() -> None:
    """T12 BNDRY/edge: 4 mock injections — first 3 retry; 4th → next_delay=None (escalate)."""
    from harness.recovery.retry import RetryCounter, RetryPolicy

    policy = RetryPolicy()
    counter = RetryCounter()

    delays: list[float | None] = []
    for _ in range(4):
        rc = counter.inc("long-task-tdd-red", "context_overflow")
        delays.append(policy.next_delay("context_overflow", retry_count=rc - 1))

    # First three retries → not None; fourth → None (escalate)
    assert delays[0] is not None and delays[0] == 0.0
    assert delays[1] is not None
    assert delays[2] is not None
    assert (
        delays[3] is None
    ), f"NFR-003: 4th context_overflow must escalate (None); got delays={delays}"
    # retry_count expectation per NFR-003: 3 (zero-indexed last retry)
    assert counter.value("long-task-tdd-red") == 4


# ---- T13 -------------------------------------------------------------------
async def test_t13_rate_limit_backoff_sequence_30_120_300_none() -> None:
    """T13 PERF/timing: RetryPolicy.next_delay('rate_limit', 0..3) == [30.0, 120.0, 300.0, None]."""
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    seq = [policy.next_delay("rate_limit", retry_count=i) for i in range(4)]
    assert seq == [30.0, 120.0, 300.0, None], f"FR-025: rate_limit sequence wrong; got {seq}"


# ---- T15 -------------------------------------------------------------------
async def test_t15_network_backoff_sequence_0_60_none() -> None:
    """T15 FUNC/happy: RetryPolicy.next_delay('network', 0..2) == [0.0, 60.0, None]."""
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    seq = [policy.next_delay("network", retry_count=i) for i in range(3)]
    assert seq == [0.0, 60.0, None], f"FR-026: network sequence wrong; got {seq}"


# ---- Boundary helper: invalid retry_count rejected --------------------------
async def test_retry_policy_negative_retry_count_raises() -> None:
    """BNDRY: retry_count=None / negative → ValueError per Boundary table row."""
    from harness.recovery.retry import RetryPolicy

    policy = RetryPolicy()
    with pytest.raises(ValueError):
        policy.next_delay("rate_limit", retry_count=-1)  # type: ignore[arg-type]
    with pytest.raises((ValueError, TypeError)):
        policy.next_delay("rate_limit", retry_count=None)  # type: ignore[arg-type]


# ---- T16 -------------------------------------------------------------------
async def test_t16_watchdog_arm_fires_sigterm_after_timeout() -> None:
    """T16 FUNC/happy: Watchdog.arm(pid, timeout_s=0.05) → os.kill(pid, SIGTERM) called within ~50ms."""
    from harness.recovery.watchdog import Watchdog

    wd = Watchdog()
    pid = 99999  # synthetic
    kills: list[tuple[int, int]] = []

    def _spy_kill(p: int, s: int) -> None:
        kills.append((p, s))

    with patch("harness.recovery.watchdog.os.kill", side_effect=_spy_kill):
        # alive predicate: True until SIGKILL would be sent
        wd.arm(ticket_id="t-1", pid=pid, timeout_s=0.05, is_alive=lambda p: True)
        # Wait for SIGTERM but not SIGKILL window
        await asyncio.sleep(0.25)
        wd.disarm(ticket_id="t-1")

    sig_signals = [s for (_p, s) in kills]
    assert (
        signal.SIGTERM in sig_signals
    ), f"Watchdog must call SIGTERM after timeout; got {sig_signals}"


# ---- T17 -------------------------------------------------------------------
async def test_t17_watchdog_escalates_to_sigkill_after_sigterm_5s() -> None:
    """T17 FUNC/happy: SIGTERM then pid alive 5s → SIGKILL called."""
    from harness.recovery.watchdog import Watchdog

    # Compress timing window: timeout_s=0.05 first, then sigkill_grace_s=0.1
    wd = Watchdog(sigkill_grace_s=0.1)
    pid = 99998
    kills: list[tuple[int, int]] = []

    def _spy_kill(p: int, s: int) -> None:
        kills.append((p, s))

    with patch("harness.recovery.watchdog.os.kill", side_effect=_spy_kill):
        wd.arm(ticket_id="t-2", pid=pid, timeout_s=0.05, is_alive=lambda p: True)
        await asyncio.sleep(0.30)  # > 0.05 + 0.1 = 0.15s
        wd.disarm(ticket_id="t-2")

    sig_signals = [s for (_p, s) in kills]
    assert signal.SIGTERM in sig_signals
    assert (
        signal.SIGKILL in sig_signals
    ), f"FR-027 AC-2: SIGKILL must follow SIGTERM grace; got signals={sig_signals}"
    # Order: SIGTERM before SIGKILL
    idx_term = sig_signals.index(signal.SIGTERM)
    idx_kill = sig_signals.index(signal.SIGKILL)
    assert idx_term < idx_kill


# ---- T18 -------------------------------------------------------------------
async def test_t18_skill_error_passthrough_to_aborted_no_retry() -> None:
    """T18 FUNC/happy: AnomalyClassifier given Verdict(anomaly='skill_error') + result_text '[CONTRACT-DEVIATION]' → cls=skill_error; ticket aborted; no reenqueue."""
    from harness.dispatch.classifier.models import ClassifyRequest, Verdict
    from harness.recovery.anomaly import AnomalyClassifier, AnomalyClass

    classifier = AnomalyClassifier()
    req = ClassifyRequest(
        exit_code=0, stderr_tail="", stdout_tail="[CONTRACT-DEVIATION] bad output"
    )
    verdict = Verdict(verdict="ABORT", anomaly="skill_error", backend="rule")

    info = classifier.classify(req, verdict)
    assert info.cls == AnomalyClass.SKILL_ERROR, f"expected skill_error; got {info.cls}"
    assert info.next_action == "abort", "skill_error must abort, not retry"


# ---- T19 -------------------------------------------------------------------
async def test_t19_skill_error_pauses_run_in_orchestrator(tmp_path: Path) -> None:
    """T19 FUNC/error: skill_error verdict in main loop → run.state=paused + Escalated(cls='skill_error')."""
    import subprocess
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
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
        cwd=tmp_path,
        check=True,
    )

    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.classifier.set_verdict("skill_error", verdict="ABORT")

    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))
    final = await orch.wait_for_state(s.run_id, "paused", timeout=3.0)
    assert final.state == "paused"

    events = orch.control_bus.captured_anomaly_events()
    escalated = [e for e in events if e.kind == "Escalated"]
    assert escalated, f"Escalated event expected after skill_error; got {[e.kind for e in events]}"
    assert escalated[-1].cls == "skill_error"
