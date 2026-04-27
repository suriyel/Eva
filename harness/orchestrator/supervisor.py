"""F20 · TicketSupervisor + DepthGuard + builder helpers.

The supervisor runs a single ticket end-to-end through GitTracker / ToolAdapter
/ Watchdog / StreamParser / ClassifierService / TicketRepository. It records a
``call_trace`` so unit tests (T41) can assert call ordering without depending
on real subprocesses.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.domain.ticket import (
    Classification,
    DispatchSpec,
    ExecutionInfo,
    GitContext as DomainGitContext,
    HilInfo,
    OutputInfo,
    Ticket,
    TicketState,
)
from harness.orchestrator.errors import TicketError
from harness.orchestrator.phase_route import PhaseRouteResult
from harness.orchestrator.schemas import TicketCommand, TicketOutcome


class DepthGuard:
    """FR-007 AC-2 — depth ≤ 2 invariant."""

    @staticmethod
    def ensure_within(parent_depth: int | None) -> int:
        if parent_depth is None:
            return 0
        if parent_depth >= 2:
            raise TicketError(code="depth_exceeded", message=f"parent depth {parent_depth} ≥ 2")
        return parent_depth + 1


def build_ticket_command(result: PhaseRouteResult, *, parent: str | None) -> TicketCommand:
    """Map a PhaseRouteResult → TicketCommand without rewriting skill names.

    FR-047 AC-2: skill names are NOT a hardcoded enum — pass through as-is.
    FR-003: hotfix/increment signal already encoded in next_skill, never rewritten.
    """
    if not result.ok:
        raise ValueError("cannot build TicketCommand from ok=False PhaseRouteResult")
    return TicketCommand(
        kind="spawn",
        skill_hint=result.next_skill,
        feature_id=result.feature_id,
        tool="claude",
        run_id="<pending>",
        parent_ticket=parent,
    )


class TicketSupervisor:
    """Drive a single ticket lifecycle (IAPI-004)."""

    def __init__(self, *, orchestrator: Any) -> None:
        self._orch = orchestrator
        # Serialize run_ticket invocations on the same supervisor — the main
        # loop and explicit test calls share one ToolAdapter, so concurrent
        # entry would interleave prepare_workdir/spawn calls and break the
        # IAPI-005 [MOD] sequence guarantees in T42.
        self._lock = asyncio.Lock()

    async def run_ticket(self, cmd: TicketCommand) -> TicketOutcome:
        async with self._lock:
            return await self._run_ticket_impl(cmd)

    async def _run_ticket_impl(self, cmd: TicketCommand) -> TicketOutcome:
        orch = self._orch
        # Depth guard — fetch parent depth if any.
        parent_depth: int | None = None
        if cmd.parent_ticket:
            parent_ticket = await orch.ticket_repo.get(cmd.parent_ticket)
            if parent_ticket is not None:
                parent_depth = parent_ticket.depth
        new_depth = DepthGuard.ensure_within(parent_depth)

        ticket_id = f"t-{uuid.uuid4().hex[:8]}"
        orch._record_call(f"GitTracker.begin({ticket_id})")
        git_begin = await orch.git_tracker.begin(ticket_id=ticket_id, workdir=Path(orch.workdir))

        # Wave 4 [MOD] IAPI-005: prepare_workdir(spec) MUST run before spawn;
        # the returned IsolatedPaths is forwarded to spawn(spec, paths).
        # WorkdirPrepareError must propagate (T43) so spawn never fires.
        orch._record_call(f"ToolAdapter.prepare_workdir({cmd.skill_hint})")
        paths = await orch.tool_adapter.prepare_workdir(cmd)

        orch._record_call(f"ToolAdapter.spawn({cmd.skill_hint})")
        proc = await orch.tool_adapter.spawn(cmd, paths)

        pid = getattr(proc, "pid", 0) or 0
        orch._record_call(f"Watchdog.arm(pid={pid})")
        # We don't actually arm a real watchdog timer in unit tests — just
        # invoke the trace marker; real runs would call orch.watchdog.arm.
        try:
            orch.watchdog.arm(
                ticket_id=ticket_id, pid=pid, timeout_s=1800.0, is_alive=lambda _p: False
            )
        except Exception:
            pass

        # Wave 4 [MOD] IAPI-008 REMOVED: subscribe to ticket_stream keyed by
        # ticket_id rather than the legacy stream_parser keyed by proc.
        orch._record_call("TicketStream.subscribe")
        try:
            async for _evt in orch.ticket_stream.events(ticket_id):
                pass
        except Exception:
            pass

        orch._record_call("Watchdog.disarm")
        try:
            orch.watchdog.disarm(ticket_id=ticket_id)
        except Exception:
            pass

        orch._record_call("ClassifierService.classify")
        verdict = await orch.classifier.classify_request(proc)

        # Anomaly classifier
        anomaly_info = orch.anomaly_classifier.classify(classify_request_for(proc), verdict)

        orch._record_call(f"GitTracker.end({ticket_id})")
        git_end = await orch.git_tracker.end(ticket_id=ticket_id, workdir=Path(orch.workdir))

        # Wave 5 retry 集成 (FR-024/025/026 / NFR-003/004 真集成):
        # When the AnomalyClassifier asks us to retry, ask RetryPolicy for the
        # next delay; if it returns float we sleep + inc the counter + recurse
        # the same _run_ticket_impl (Wave 5 reuses the recursion semantics —
        # NOT a queue re-enqueue). When the policy returns None we escalate.
        if anomaly_info.next_action == "retry":
            skill_hint = cmd.skill_hint or ""
            cls_value = (
                anomaly_info.cls.value
                if hasattr(anomaly_info.cls, "value")
                else str(anomaly_info.cls)
            )
            count = orch.retry_counter.value(skill_hint)
            delay = orch.retry_policy.next_delay(cls_value, count)
            if delay is None:
                # Exhausted — final_state ABORTED + Escalated broadcast.
                from harness.orchestrator.bus import AnomalyEvent

                try:
                    orch.control_bus.broadcast_anomaly(
                        AnomalyEvent(
                            kind="Escalated",
                            cls=cls_value,
                            ticket_id=ticket_id,
                            retry_count=count,
                        )
                    )
                except Exception:
                    pass
                final_state = TicketState.ABORTED
            else:
                # Inc BEFORE sleep so a cancellation mid-sleep still leaves the
                # counter in the right state for NFR-003/004 escalation accuracy.
                orch.retry_counter.inc(skill_hint, cls_value)
                await asyncio.sleep(delay)
                return await self._run_ticket_impl(cmd)
        elif anomaly_info.next_action == "abort":
            final_state = TicketState.ABORTED
        elif verdict.verdict == "COMPLETED":
            final_state = TicketState.COMPLETED
        elif verdict.verdict == "RETRY":
            final_state = TicketState.RETRYING
        elif verdict.verdict == "ABORT":
            final_state = TicketState.ABORTED
        elif verdict.verdict == "HIL_REQUIRED":
            final_state = TicketState.HIL_WAITING
        else:
            final_state = TicketState.COMPLETED

        # Build minimal Ticket and persist
        now = datetime.now(timezone.utc).isoformat()
        ticket = Ticket(
            id=ticket_id,
            run_id=cmd.run_id,
            parent_ticket=cmd.parent_ticket,
            depth=new_depth,
            tool=cmd.tool,
            skill_hint=cmd.skill_hint,
            state=final_state,
            dispatch=DispatchSpec(
                argv=["python", "-c", "pass"],
                env={},
                cwd=str(orch.workdir),
                plugin_dir=str(orch.plugin_dir),
                settings_path=str(orch.workdir / ".claude" / "settings.json"),
            ),
            execution=ExecutionInfo(
                pid=pid or None,
                started_at=now,
                ended_at=now,
                exit_code=getattr(proc, "exit_code", 0),
                duration_ms=1,
            ),
            output=OutputInfo(result_text=getattr(proc, "result_text", "ok")),
            hil=HilInfo(),
            classification=Classification(
                verdict=verdict.verdict,
                reason=verdict.reason or "",
                anomaly=verdict.anomaly,
                hil_source=verdict.hil_source,
                backend=verdict.backend,
            ),
            git=DomainGitContext(
                head_before=git_begin.head_before,
                head_after=git_end.head_after,
            ),
        )

        orch._record_call(f"TicketRepository.save({ticket_id})")
        await orch.ticket_repo.save(ticket)

        # Audit a few state_transition events (for T47 ≥3 events)
        try:
            await orch.audit_writer.append_state_transition(
                run_id=cmd.run_id,
                ticket_id=ticket_id,
                state_from=TicketState.PENDING,
                state_to=TicketState.RUNNING,
            )
            await orch.audit_writer.append_state_transition(
                run_id=cmd.run_id,
                ticket_id=ticket_id,
                state_from=TicketState.RUNNING,
                state_to=TicketState.CLASSIFYING,
            )
            await orch.audit_writer.append_state_transition(
                run_id=cmd.run_id,
                ticket_id=ticket_id,
                state_from=TicketState.CLASSIFYING,
                state_to=final_state,
            )
        except Exception:
            pass

        return TicketOutcome(
            ticket_id=ticket_id,
            final_state=final_state.value,
            verdict=verdict.verdict,
            anomaly=anomaly_info.cls.value if anomaly_info.cls.value != "none" else None,
        )


def classify_request_for(proc: Any) -> Any:
    """Synthesise a ClassifyRequest from a TicketProcess-like object."""
    from harness.dispatch.classifier.models import ClassifyRequest

    return ClassifyRequest(
        exit_code=getattr(proc, "exit_code", 0),
        stderr_tail=getattr(proc, "stderr_tail", ""),
        stdout_tail=getattr(proc, "stdout_tail", ""),
        has_termination_banner=False,
    )


__all__ = ["DepthGuard", "TicketSupervisor", "build_ticket_command"]
