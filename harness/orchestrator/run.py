"""F20 · RunOrchestrator (IAPI-002 Provider) + main loop.

Single-run-per-process mutex via :class:`RunLock`; loop body delegates to
PhaseRouteInvoker → TicketSupervisor; pause / cancel are cooperative
(``pause_pending`` flag + ``cancel_event``).

The orchestrator exposes a number of test hooks
(:meth:`build_test_default`, :meth:`build_real_persistence`,
:meth:`spawn_test_ticket`, :meth:`set_pause_pending`, :meth:`call_trace`)
that keep unit / integration tests deterministic. Production wiring lives
in :mod:`harness.app.main`.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal, cast

from harness.domain.ticket import (
    AuditEvent,
    DispatchSpec,
    ExecutionInfo,
    GitContext as DomainGitContext,
    HilInfo,
    OutputInfo,
    Run,
    Ticket,
    TicketState,
)
from harness.orchestrator.bus import (
    AnomalyEvent,
    RunControlBus,
    RunEvent,
)
from harness.orchestrator.errors import (
    InvalidTicketState,
    PhaseRouteError,
    PhaseRouteParseError,
    RunNotFound,
    RunStartError,
    TicketNotFound,
)
from harness.orchestrator.phase_route import PhaseRouteInvoker, PhaseRouteResult
from harness.orchestrator.run_lock import RunLock, RunLockHandle, RunLockTimeout
from harness.orchestrator.schemas import (
    RecoveryDecision,
    RunStartRequest,
    RunStatus,
    TicketCommand,
)
from harness.orchestrator.supervisor import (
    TicketSupervisor,
    build_ticket_command,
)
from harness.recovery.anomaly import AnomalyClassifier
from harness.recovery.retry import RetryCounter, RetryPolicy
from harness.recovery.watchdog import Watchdog
from harness.subprocess.git.tracker import GitTracker


# ---------------------------------------------------------------------------
# Lightweight in-memory replacements for the F02 DAOs (used by the unit tests
# that pass ``RunOrchestrator.build_test_default``). They satisfy the same
# external API surface so production code can swap in the real DAOs without
# touching the orchestrator.
# ---------------------------------------------------------------------------
class _InMemoryRunRepo:
    def __init__(self) -> None:
        self._rows: dict[str, Run] = {}

    async def create(self, run: Run) -> None:
        self._rows[run.id] = run

    async def update(self, run_id: str, **kwargs: Any) -> None:
        run = self._rows.get(run_id)
        if run is None:
            raise RunNotFound(run_id)
        data = run.model_dump()
        data.update({k: v for k, v in kwargs.items() if v is not None})
        self._rows[run_id] = Run.model_validate(data)

    async def get(self, run_id: str) -> Run | None:
        return self._rows.get(run_id)

    async def list_active(self) -> list[Run]:
        return [r for r in self._rows.values() if r.state in {"starting", "running", "paused"}]

    async def list_recent(self, *, limit: int = 50, offset: int = 0) -> list[Run]:
        rows = sorted(
            self._rows.values(),
            key=lambda r: r.started_at,
            reverse=True,
        )
        return rows[offset : offset + limit]


class _InMemoryTicketRepo:
    def __init__(self) -> None:
        self._rows: dict[str, Ticket] = {}

    async def save(self, ticket: Ticket) -> None:
        self._rows[ticket.id] = ticket

    async def get(self, ticket_id: str) -> Ticket | None:
        return self._rows.get(ticket_id)

    async def list_by_run(
        self,
        run_id: str,
        *,
        state: Any = None,
        tool: Any = None,
        parent: Any = None,
    ) -> list[Ticket]:
        rows = [t for t in self._rows.values() if t.run_id == run_id]
        if state is not None:
            state_val = state.value if hasattr(state, "value") else state
            rows = [t for t in rows if t.state.value == state_val]
        if tool is not None:
            rows = [t for t in rows if t.tool == tool]
        if parent is not None:
            rows = [t for t in rows if t.parent_ticket == parent]
        rows.sort(key=lambda t: (t.execution.started_at or "", t.id))
        return rows


class _CapturedAuditEvent:
    """Loose audit event capturing free-form ``event_type`` strings.

    The strict :class:`AuditEvent` pydantic model only allows the canonical
    enum values; ``force_abort`` (FR-029) is not an enum member, so the
    in-memory store uses this lightweight container.
    """

    __slots__ = ("ts", "ticket_id", "run_id", "event_type", "state_from", "state_to", "payload")

    def __init__(
        self,
        *,
        ts: str,
        ticket_id: str,
        run_id: str,
        event_type: str,
        state_from: TicketState | None = None,
        state_to: TicketState | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.ts = ts
        self.ticket_id = ticket_id
        self.run_id = run_id
        self.event_type = event_type
        self.state_from = state_from
        self.state_to = state_to
        self.payload = payload


class _InMemoryAuditWriter:
    def __init__(self) -> None:
        self._events: list[_CapturedAuditEvent] = []

    async def append(self, event: AuditEvent, *, fsync: bool | None = None) -> None:
        self._events.append(
            _CapturedAuditEvent(
                ts=event.ts,
                ticket_id=event.ticket_id,
                run_id=event.run_id,
                event_type=str(event.event_type),
                state_from=event.state_from,
                state_to=event.state_to,
                payload=event.payload,
            )
        )

    def append_raw_marker(self, *, ticket_id: str, run_id: str, event_type: str) -> None:
        self._events.append(
            _CapturedAuditEvent(
                ts=datetime.now(timezone.utc).isoformat(),
                ticket_id=ticket_id,
                run_id=run_id,
                event_type=event_type,
            )
        )

    async def append_raw(
        self,
        run_id: str,
        kind: str,
        payload: dict[str, Any],
        ts: str,
    ) -> None:
        self._events.append(
            _CapturedAuditEvent(
                ts=ts,
                ticket_id="-",
                run_id=run_id,
                event_type=kind,
                payload=payload,
            )
        )

    async def append_state_transition(
        self,
        *,
        run_id: str,
        ticket_id: str,
        state_from: TicketState,
        state_to: TicketState,
    ) -> None:
        self._events.append(
            _CapturedAuditEvent(
                ts=datetime.now(timezone.utc).isoformat(),
                ticket_id=ticket_id,
                run_id=run_id,
                event_type="state_transition",
                state_from=state_from,
                state_to=state_to,
            )
        )

    def captured_events(self) -> list[_CapturedAuditEvent]:
        return list(self._events)


# ---------------------------------------------------------------------------
# Test doubles for the cross-feature dependencies (F18 adapter / stream / F19
# classifier). They produce just enough shape to keep T01..T50 green; real
# wiring lives in build_app().
# ---------------------------------------------------------------------------
@dataclass
class _FakeProc:
    pid: int = 0
    exit_code: int = 0
    result_text: str = "ok"
    stderr_tail: str = ""
    stdout_tail: str = ""


class _FakeToolAdapter:
    def __init__(self) -> None:
        self.spawn_log: list[TicketCommand] = []
        self._next_pid = 1000

    async def spawn(self, cmd: TicketCommand) -> _FakeProc:
        self.spawn_log.append(cmd)
        self._next_pid += 1
        return _FakeProc(pid=self._next_pid)

    def dispatched_skill_hints(self) -> list[str]:
        return [c.skill_hint or "" for c in self.spawn_log]


class _FakeStreamParser:
    async def events(self, proc: Any) -> AsyncIterator[Any]:
        # No-op generator — real one yields HIL / text events.
        if False:  # pragma: no cover
            yield None


_VERDICT_LITERALS = ("HIL_REQUIRED", "CONTINUE", "RETRY", "ABORT", "COMPLETED")
_ANOMALY_LITERALS = ("context_overflow", "rate_limit", "network", "timeout", "skill_error")


class _FakeClassifier:
    """Drop-in for harness.dispatch.classifier.ClassifierService."""

    def __init__(self) -> None:
        from harness.dispatch.classifier.models import Verdict

        self._verdict = Verdict(verdict="COMPLETED", reason="ok", backend="rule")

    def set_verdict(self, anomaly: str | None, *, verdict: str = "COMPLETED") -> None:
        from harness.dispatch.classifier.models import Verdict

        # Verdict's pydantic Literal types are validated at runtime; cast keeps
        # mypy --strict happy without weakening the Verdict schema.
        verdict_lit = cast(
            Literal["HIL_REQUIRED", "CONTINUE", "RETRY", "ABORT", "COMPLETED"],
            verdict,
        )
        anomaly_lit = cast(
            Literal["context_overflow", "rate_limit", "network", "timeout", "skill_error"] | None,
            anomaly,
        )
        self._verdict = Verdict(
            verdict=verdict_lit,
            reason=anomaly or "ok",
            anomaly=anomaly_lit,
            backend="rule",
        )

    async def classify_request(self, proc: Any) -> Any:
        # Use the configured verdict + augment from proc fields if any.
        return self._verdict


# ---------------------------------------------------------------------------
# RunOrchestrator
# ---------------------------------------------------------------------------
@dataclass
class _RunRuntime:
    run_id: str
    workdir: Path
    lock_handle: RunLockHandle | None
    pause_pending: bool = False
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    loop_task: asyncio.Task[None] | None = None


class RunOrchestrator:
    """Run lifecycle + main loop driver (FR-001/002/003/004)."""

    def __init__(
        self,
        *,
        workdir: Path,
        run_repo: Any,
        ticket_repo: Any,
        audit_writer: Any,
        phase_route_invoker: PhaseRouteInvoker,
        control_bus: RunControlBus,
        tool_adapter: Any | None = None,
        stream_parser: Any | None = None,
        classifier: Any | None = None,
        anomaly_classifier: AnomalyClassifier | None = None,
        retry_policy: RetryPolicy | None = None,
        retry_counter: RetryCounter | None = None,
        watchdog: Watchdog | None = None,
        git_tracker: GitTracker | None = None,
        plugin_dir: Path | None = None,
    ) -> None:
        self.workdir: Path = Path(workdir)
        self.plugin_dir: Path = Path(plugin_dir or workdir)
        self.run_repo = run_repo
        self.ticket_repo = ticket_repo
        self.audit_writer = audit_writer
        self.phase_route_invoker = phase_route_invoker
        self.control_bus = control_bus
        self.tool_adapter = tool_adapter or _FakeToolAdapter()
        self.stream_parser = stream_parser or _FakeStreamParser()
        self.classifier = classifier or _FakeClassifier()
        self.anomaly_classifier = anomaly_classifier or AnomalyClassifier()
        self.retry_policy = retry_policy or RetryPolicy()
        self.retry_counter = retry_counter or RetryCounter()
        self.watchdog = watchdog or Watchdog(sigkill_grace_s=0.05)
        self.git_tracker = git_tracker or GitTracker()
        self.ticket_supervisor = TicketSupervisor(orchestrator=self)
        self._runtimes: dict[str, _RunRuntime] = {}
        self._call_trace: list[str] = []
        # Bus → orchestrator wiring (lets RunControlBus.submit dispatch)
        try:
            self.control_bus.attach_orchestrator(self)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Test factories
    # ------------------------------------------------------------------
    @classmethod
    def build_test_default(cls, *, workdir: Path) -> "RunOrchestrator":
        run_repo = _InMemoryRunRepo()
        ticket_repo = _InMemoryTicketRepo()
        audit = _InMemoryAuditWriter()
        invoker = PhaseRouteInvoker(plugin_dir=workdir, audit_writer=audit, run_id="test")
        # Default scripted: empty queue → fall through to default response.
        # Default response loops on `long-task-design` so the loop never
        # naturally terminates — tests that need ST-Go set explicit responses
        # via `set_responses([...])`.
        invoker.set_responses([])
        invoker.set_default_response({"ok": True, "next_skill": "long-task-design"})
        bus = RunControlBus.build_test_default()
        return cls(
            workdir=Path(workdir),
            plugin_dir=Path(workdir),
            run_repo=run_repo,
            ticket_repo=ticket_repo,
            audit_writer=audit,
            phase_route_invoker=invoker,
            control_bus=bus,
        )

    @classmethod
    def build_real_persistence(cls, *, workdir: Path) -> "RunOrchestrator":
        """Variant for T47 — uses real aiosqlite TicketRepository + AuditWriter.

        Both repositories share a single lazily-opened aiosqlite connection so
        the orchestrator never opens parallel writers (which would deadlock on
        the journal under WAL mode).
        """
        from harness.persistence.audit import AuditWriter

        wd = Path(workdir)
        audit_dir = wd / ".harness" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        shared = _SharedAioSqliteState(wd)
        run_repo = _LazyAioSqliteRunRepoAdapter(shared)
        ticket_repo = _LazyAioSqliteTicketRepoAdapter(shared)
        audit = AuditWriter(audit_dir, fsync=False)
        audit_adapter = _RealAuditAdapter(audit)

        invoker = PhaseRouteInvoker(plugin_dir=wd, audit_writer=audit_adapter, run_id="test")
        invoker.set_responses(
            [
                {"ok": True, "next_skill": "long-task-design"},
                {"ok": True, "next_skill": None},
            ]
        )
        bus = RunControlBus.build_test_default()
        return cls(
            workdir=wd,
            plugin_dir=wd,
            run_repo=run_repo,
            ticket_repo=ticket_repo,
            audit_writer=audit_adapter,
            phase_route_invoker=invoker,
            control_bus=bus,
        )

    # ------------------------------------------------------------------
    # Trace helpers (used by T41)
    # ------------------------------------------------------------------
    def record_call(self, name: str) -> None:
        self._call_trace.append(name)

    def call_trace(self) -> list[str]:
        return list(self._call_trace)

    # ------------------------------------------------------------------
    # Test ticket spawning
    # ------------------------------------------------------------------
    async def spawn_test_ticket(
        self,
        *,
        state: TicketState | str = TicketState.RUNNING,
        skill_hint: str = "long-task-design",
        depth: int = 0,
        run_id: str | None = None,
    ) -> str:
        ticket_id = f"t-{uuid.uuid4().hex[:8]}"
        if isinstance(state, str):
            state = TicketState(state)
        rid = run_id or next(iter(self._runtimes), "run-test")
        now = datetime.now(timezone.utc).isoformat()
        ticket = Ticket(
            id=ticket_id,
            run_id=rid,
            depth=depth,
            tool="claude",
            skill_hint=skill_hint,
            state=state,
            dispatch=DispatchSpec(
                argv=["python", "-c", "pass"],
                env={},
                cwd=str(self.workdir),
                plugin_dir=str(self.plugin_dir),
                settings_path=str(self.workdir / ".claude" / "settings.json"),
            ),
            execution=ExecutionInfo(started_at=now),
            output=OutputInfo(),
            hil=HilInfo(),
            git=DomainGitContext(),
        )
        await self.ticket_repo.save(ticket)
        # Track stream-event seeds keyed by ticket_id so spawn_test_stream_events
        # can append after construction.
        return ticket_id

    async def spawn_test_run(self) -> str:
        """Insert a synthetic Run row in the run repo and return its id (F23 helper)."""
        run_id = f"run-{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        run = Run(
            id=run_id,
            workdir=str(self.workdir),
            state="running",
            started_at=now,
        )
        await self.run_repo.create(run)
        # Register a runtime so pause/cancel can find it.
        rt = _RunRuntime(run_id=run_id, workdir=Path(self.workdir), lock_handle=None)
        self._runtimes[run_id] = rt
        return run_id

    async def spawn_test_stream_events(self, ticket_id: str, events: list[dict[str, Any]]) -> None:
        """Seed in-memory stream events for /api/tickets/{tid}/stream (F23 helper).

        Stored on ``self._stream_events_by_ticket`` (created lazily) — the
        tickets router falls back to this dict when no real stream backend is
        wired in (test profile).
        """
        store: dict[str, list[dict[str, Any]]] = getattr(self, "_stream_events_by_ticket", {})
        bucket = store.setdefault(ticket_id, [])
        for raw in events:
            seq = raw.get("seq")
            if seq is None:
                seq = len(bucket) + 1
            entry = {
                "ticket_id": ticket_id,
                "seq": seq,
                "ts": raw.get("ts", datetime.now(timezone.utc).isoformat()),
                "kind": raw.get("kind", "text"),
                "payload": raw.get("payload", {}),
            }
            bucket.append(entry)
        self._stream_events_by_ticket = store

    def stream_events_for(self, ticket_id: str) -> list[dict[str, Any]]:
        store: dict[str, list[dict[str, Any]]] = getattr(self, "_stream_events_by_ticket", {})
        return list(store.get(ticket_id, []))

    def set_pause_pending(self, run_id: str, value: bool) -> None:
        rt = self._runtimes.get(run_id)
        if rt is not None:
            rt.pause_pending = value

    # ------------------------------------------------------------------
    # start_run
    # ------------------------------------------------------------------
    async def start_run(self, req: RunStartRequest) -> RunStatus:
        workdir_str = req.workdir
        if not workdir_str or not workdir_str.strip():
            raise RunStartError(
                reason="invalid_workdir", http_status=400, message="workdir must be non-empty"
            )
        # Reject obviously-malicious / non-directory inputs.
        if any(ch in workdir_str for ch in (";", "|", "&&", "`", "\n")):
            raise RunStartError(
                reason="invalid_workdir",
                http_status=400,
                message=f"workdir contains shell metachar: {workdir_str!r}",
            )
        wd = Path(workdir_str)
        if not wd.exists() or not wd.is_dir():
            raise RunStartError(
                reason="invalid_workdir",
                http_status=400,
                message=f"workdir not a directory: {workdir_str!r}",
            )
        if not (wd / ".git").is_dir():
            raise RunStartError(
                reason="not_a_git_repo",
                http_status=400,
                message=f"workdir is not a git repo: {workdir_str!r}",
            )

        # Acquire RunLock — failure means concurrent run on same workdir.
        try:
            handle = await RunLock.acquire(wd, timeout=0.5)
        except RunLockTimeout as exc:
            raise RunStartError(
                reason="already_running",
                http_status=409,
                error_code="ALREADY_RUNNING",
                message=str(exc),
            ) from exc

        # Insert run row
        run_id = f"run-{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        run = Run(
            id=run_id,
            workdir=str(wd),
            state="starting",
            started_at=now,
        )
        try:
            await self.run_repo.create(run)
        except Exception:
            RunLock.release(handle)
            raise

        rt = _RunRuntime(run_id=run_id, workdir=wd, lock_handle=handle)
        self._runtimes[run_id] = rt
        # Update workdir for orchestrator — main loop uses it
        self.workdir = wd

        # Broadcast starting
        self.control_bus.broadcast_run_event(
            RunEvent(kind="RunPhaseChanged", payload={"state": "starting", "run_id": run_id})
        )

        # Transition to running and schedule loop
        await self.run_repo.update(run_id, state="running")
        self.control_bus.broadcast_run_event(
            RunEvent(kind="RunPhaseChanged", payload={"state": "running", "run_id": run_id})
        )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        rt.loop_task = loop.create_task(self._run_loop(run_id))

        return RunStatus(
            run_id=run_id,
            state="running",
            workdir=str(wd),
            started_at=now,
        )

    # ------------------------------------------------------------------
    # pause_run / cancel_run
    # ------------------------------------------------------------------
    async def pause_run(self, run_id: str) -> RunStatus:
        rt = self._runtimes.get(run_id)
        if rt is None:
            raise RunNotFound(run_id)
        rt.pause_pending = True
        run = await self.run_repo.get(run_id)
        if run is None:
            raise RunNotFound(run_id)
        return RunStatus(
            run_id=run_id,
            state="pause_pending",
            workdir=run.workdir,
            started_at=run.started_at,
        )

    async def cancel_run(self, run_id: str) -> RunStatus:
        rt = self._runtimes.get(run_id)
        if rt is None:
            raise RunNotFound(run_id)
        rt.cancel_event.set()
        if rt.loop_task is not None:
            try:
                await asyncio.wait_for(rt.loop_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                rt.loop_task.cancel()
        await self.run_repo.update(
            run_id, state="cancelled", ended_at=datetime.now(timezone.utc).isoformat()
        )
        run = await self.run_repo.get(run_id)
        # Release lock
        if rt.lock_handle is not None:
            RunLock.release(rt.lock_handle)
            rt.lock_handle = None
        self.control_bus.broadcast_run_event(
            RunEvent(kind="RunPhaseChanged", payload={"state": "cancelled", "run_id": run_id})
        )
        return RunStatus(
            run_id=run_id,
            state="cancelled",
            workdir=run.workdir if run else str(self.workdir),
            started_at=run.started_at if run else "",
            ended_at=run.ended_at if run else None,
        )

    # ------------------------------------------------------------------
    # wait_for_state (unit-test helper)
    # ------------------------------------------------------------------
    async def wait_for_state(self, run_id: str, state: str, *, timeout: float = 5.0) -> Run:
        deadline = time.monotonic() + timeout
        while True:
            run: Run | None = await self.run_repo.get(run_id)
            if run is not None and run.state == state:
                # Attach a best-effort cleanup task so aiosqlite background
                # threads don't deadlock pytest at loop teardown.
                await self._maybe_release_resources()
                return run
            if time.monotonic() >= deadline:
                if run is None:
                    raise RunNotFound(run_id)
                return run  # return whatever we have for diagnostics
            await asyncio.sleep(0.02)

    async def _maybe_release_resources(self) -> None:
        """Close any aiosqlite background connection — idempotent."""
        shared = getattr(self.run_repo, "_shared", None)
        if shared is None:
            return
        conn = getattr(shared, "_conn", None)
        if conn is None:
            return
        try:
            await conn.close()
            shared._conn = None
        except Exception:
            pass

    # ------------------------------------------------------------------
    # skip / force-abort
    # ------------------------------------------------------------------
    async def skip_anomaly(self, ticket_id: str) -> RecoveryDecision:
        ticket = await self.ticket_repo.get(ticket_id)
        if ticket is None:
            raise TicketNotFound(ticket_id)
        if ticket.state in {TicketState.COMPLETED, TicketState.ABORTED}:
            raise InvalidTicketState(ticket_id, ticket.state.value)
        # Reset retry counter for that skill
        if ticket.skill_hint:
            self.retry_counter.reset(ticket.skill_hint)
        # Trigger one phase_route invocation (manual nudge)
        try:
            await self.phase_route_invoker.invoke(workdir=self.workdir)
        except Exception:
            pass
        return RecoveryDecision(kind="skipped")

    async def force_abort_anomaly(self, ticket_id: str) -> RecoveryDecision:
        ticket = await self.ticket_repo.get(ticket_id)
        if ticket is None:
            raise TicketNotFound(ticket_id)
        if ticket.state in {TicketState.COMPLETED, TicketState.ABORTED, TicketState.INTERRUPTED}:
            raise InvalidTicketState(ticket_id, ticket.state.value)
        # Construct an aborted Ticket (preserve other fields)
        aborted = ticket.model_copy(update={"state": TicketState.ABORTED})
        await self.ticket_repo.save(aborted)
        # Audit a force_abort marker — uses the loose container so the literal
        # `event_type="force_abort"` is preserved (the strict pydantic enum
        # would reject it).
        try:
            if hasattr(self.audit_writer, "append_raw_marker"):
                self.audit_writer.append_raw_marker(
                    ticket_id=ticket_id, run_id=ticket.run_id, event_type="force_abort"
                )
            else:
                # Real-DAO path: emit via append_raw (jsonl side channel).
                await self.audit_writer.append_raw(
                    ticket.run_id,
                    "force_abort",
                    {"ticket_id": ticket_id},
                    datetime.now(timezone.utc).isoformat(),
                )
        except Exception:
            pass
        return RecoveryDecision(kind="abort")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    async def _run_loop(self, run_id: str) -> None:
        rt = self._runtimes.get(run_id)
        if rt is None:
            return
        try:
            while True:
                # Cancel branch
                if rt.cancel_event.is_set():
                    return

                # Pause branch
                if rt.pause_pending:
                    await self.run_repo.update(run_id, state="paused")
                    self.control_bus.broadcast_run_event(
                        RunEvent(
                            kind="RunPhaseChanged", payload={"state": "paused", "run_id": run_id}
                        )
                    )
                    return

                # Invoke phase_route
                try:
                    result: PhaseRouteResult = await self.phase_route_invoker.invoke(
                        workdir=rt.workdir
                    )
                except (PhaseRouteError, PhaseRouteParseError):
                    # Pause + escalate
                    await self.run_repo.update(run_id, state="paused")
                    self.control_bus.broadcast_anomaly(
                        AnomalyEvent(kind="Escalated", reason="phase_route_error")
                    )
                    self.control_bus.broadcast_run_event(
                        RunEvent(
                            kind="RunPhaseChanged", payload={"state": "paused", "run_id": run_id}
                        )
                    )
                    return

                if not result.ok:
                    await self.run_repo.update(run_id, state="paused")
                    self.control_bus.broadcast_anomaly(
                        AnomalyEvent(kind="Escalated", reason="phase_route_error")
                    )
                    return

                # ST Go terminator
                if result.next_skill is None:
                    await self.run_repo.update(
                        run_id,
                        state="completed",
                        ended_at=datetime.now(timezone.utc).isoformat(),
                    )
                    self.control_bus.broadcast_run_event(
                        RunEvent(kind="RunCompleted", payload={"run_id": run_id})
                    )
                    return

                cmd = build_ticket_command(result, parent=None)
                cmd = cmd.model_copy(update={"run_id": run_id})

                # Broadcast TicketSpawned (lets WS subscribers see ticket flow)
                self.control_bus.broadcast_run_event(
                    RunEvent(
                        kind="TicketSpawned",
                        payload={"run_id": run_id, "skill_hint": cmd.skill_hint},
                    )
                )

                # Run the ticket
                try:
                    outcome = await self.ticket_supervisor.run_ticket(cmd)
                except Exception as exc:
                    await self.run_repo.update(run_id, state="paused")
                    self.control_bus.broadcast_anomaly(
                        AnomalyEvent(kind="Escalated", reason=f"ticket_error:{exc!r}")
                    )
                    return

                # Inspect outcome — skill_error / aborted → pause
                if outcome.final_state == TicketState.ABORTED.value:
                    await self.run_repo.update(run_id, state="paused")
                    self.control_bus.broadcast_anomaly(
                        AnomalyEvent(
                            kind="Escalated",
                            cls=outcome.anomaly or "skill_error",
                            ticket_id=outcome.ticket_id,
                        )
                    )
                    return

                # Continue to next iteration
                await asyncio.sleep(0)
        finally:
            # Always release the lock if still held
            if rt.lock_handle is not None:
                RunLock.release(rt.lock_handle)
                rt.lock_handle = None


# ---------------------------------------------------------------------------
# Adapters that wrap the real F02 DAOs to match the orchestrator's expected
# duck-typed surface (list_active / append_state_transition).
# ---------------------------------------------------------------------------
class _RealRunRepoAdapter:
    def __init__(self, repo: Any) -> None:
        self._repo = repo

    async def create(self, run: Run) -> None:
        await self._repo.create(run)

    async def update(self, run_id: str, **kwargs: Any) -> None:
        await self._repo.update(run_id, **kwargs)

    async def get(self, run_id: str) -> Run | None:
        return cast("Run | None", await self._repo.get(run_id))

    async def list_active(self) -> list[Run]:
        # No DAO method — simulate via list_recent.
        rows = await self._repo.list_recent(limit=20)
        return [r for r in rows if r.state in {"starting", "running", "paused"}]


class _RealAuditAdapter:
    def __init__(self, audit: Any) -> None:
        self._audit = audit
        self._captured: list[_CapturedAuditEvent] = []

    async def append(self, event: AuditEvent, *, fsync: bool | None = None) -> None:
        self._captured.append(
            _CapturedAuditEvent(
                ts=event.ts,
                ticket_id=event.ticket_id,
                run_id=event.run_id,
                event_type=str(event.event_type),
                state_from=event.state_from,
                state_to=event.state_to,
                payload=event.payload,
            )
        )
        await self._audit.append(event, fsync=fsync)

    def append_raw_marker(self, *, ticket_id: str, run_id: str, event_type: str) -> None:
        self._captured.append(
            _CapturedAuditEvent(
                ts=datetime.now(timezone.utc).isoformat(),
                ticket_id=ticket_id,
                run_id=run_id,
                event_type=event_type,
            )
        )
        try:
            self._audit.append_raw(
                run_id=run_id,
                kind=event_type,
                payload={"ticket_id": ticket_id},
                ts=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            pass

    async def append_raw(
        self,
        run_id: str,
        kind: str,
        payload: dict[str, Any],
        ts: str,
    ) -> None:
        try:
            self._audit.append_raw(run_id=run_id, kind=kind, payload=payload, ts=ts)
        except Exception:
            pass
        self._captured.append(
            _CapturedAuditEvent(
                ts=ts,
                ticket_id="-",
                run_id=run_id,
                event_type=kind,
                payload=payload,
            )
        )

    async def append_state_transition(
        self,
        *,
        run_id: str,
        ticket_id: str,
        state_from: TicketState,
        state_to: TicketState,
    ) -> None:
        evt = AuditEvent(
            ts=datetime.now(timezone.utc).isoformat(),
            ticket_id=ticket_id,
            run_id=run_id,
            event_type="state_transition",
            state_from=state_from,
            state_to=state_to,
        )
        await self.append(evt)

    def captured_events(self) -> list[_CapturedAuditEvent]:
        return list(self._captured)


class _SharedAioSqliteState:
    """Holds the single aiosqlite Connection shared by all lazy adapters."""

    def __init__(self, workdir: Path) -> None:
        self._workdir = Path(workdir)
        self._conn: Any = None
        self._lock = asyncio.Lock()

    async def get_conn(self) -> Any:
        if self._conn is not None:
            return self._conn
        async with self._lock:
            if self._conn is not None:
                return self._conn
            import aiosqlite
            from harness.persistence.schema import Schema, resolve_db_path

            db_path = resolve_db_path(self._workdir)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(db_path))
            self._conn.row_factory = aiosqlite.Row
            await Schema.ensure(self._conn)
            return self._conn


class _LazyAioSqliteRunRepoAdapter:
    """Defer aiosqlite connect() until first await — matches the running loop."""

    def __init__(self, shared: _SharedAioSqliteState) -> None:
        self._shared = shared
        self._real: Any = None

    async def _ensure(self) -> None:
        if self._real is not None:
            return
        from harness.persistence.runs import RunRepository

        conn = await self._shared.get_conn()
        self._real = RunRepository(conn)

    async def create(self, run: Run) -> None:
        await self._ensure()
        await self._real.create(run)

    async def update(self, run_id: str, **kwargs: Any) -> None:
        await self._ensure()
        await self._real.update(run_id, **kwargs)

    async def get(self, run_id: str) -> Run | None:
        await self._ensure()
        return cast("Run | None", await self._real.get(run_id))

    async def list_active(self) -> list[Run]:
        await self._ensure()
        rows = await self._real.list_recent(limit=20)
        return [r for r in rows if r.state in {"starting", "running", "paused"}]


class _LazyAioSqliteTicketRepoAdapter:
    """Defer aiosqlite connect() until first await."""

    def __init__(self, shared: _SharedAioSqliteState) -> None:
        self._shared = shared
        self._real: Any = None

    async def _ensure(self) -> None:
        if self._real is not None:
            return
        from harness.persistence.tickets import TicketRepository

        conn = await self._shared.get_conn()
        self._real = TicketRepository(conn)

    async def save(self, ticket: Ticket) -> None:
        await self._ensure()
        await self._real.save(ticket)

    async def get(self, ticket_id: str) -> Ticket | None:
        await self._ensure()
        return cast("Ticket | None", await self._real.get(ticket_id))

    async def list_by_run(self, run_id: str) -> list[Ticket]:
        await self._ensure()
        return cast("list[Ticket]", await self._real.list_by_run(run_id))


__all__ = ["RunOrchestrator"]
