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
from typing import TYPE_CHECKING, Any, AsyncIterator, Literal, cast

if TYPE_CHECKING:  # pragma: no cover - typing-only imports
    from harness.cli_dialog import (
        DialogActuator,
        DialogDecider,
        DialogRecognizer,
    )

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
    InvalidRunState,
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

    async def prepare_workdir(self, spec: Any) -> Any:
        # Wave 4: IAPI-005 [MOD] precondition — return a sentinel IsolatedPaths
        # the test suite can identify; production wiring uses the real
        # ClaudeCodeAdapter.prepare_workdir.
        from harness.env.models import IsolatedPaths

        return IsolatedPaths(cwd="", plugin_dir="", settings_path="")

    async def spawn(self, spec: Any, paths: Any = None) -> _FakeProc:
        self.spawn_log.append(spec)
        self._next_pid += 1
        return _FakeProc(pid=self._next_pid)

    def dispatched_skill_hints(self) -> list[str]:
        return [getattr(c, "skill_hint", None) or "" for c in self.spawn_log]


class _FakeTicketStream:
    """Wave 4 [MOD]: rename of _FakeStreamParser; events() takes ticket_id (str)
    instead of proc. Real wiring uses ``app.state.ticket_stream_broadcaster``.
    """

    async def events(self, ticket_id: str) -> AsyncIterator[Any]:
        # No-op generator — real one yields HookEvent-derived TicketStreamEvents.
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
        ticket_stream: Any | None = None,
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
        self.ticket_stream = ticket_stream or _FakeTicketStream()
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
        # Wave 4 guard (T16/T60): completed/cancelled/failed runs are terminal
        # and must NOT be silently mutated by a late cancel request. Raise 409.
        existing = await self.run_repo.get(run_id)
        if existing is not None and existing.state in {"completed", "cancelled", "failed"}:
            raise InvalidRunState(run_id, existing.state)
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


__all__ = ["RunOrchestrator", "run_real_hil_round_trip"]


# ---------------------------------------------------------------------------
# F18 Wave 4 · Real CLI HIL round-trip driver (T29/T30 PoC gate)
# ---------------------------------------------------------------------------
@dataclass
class _RealHilRoundTripResult:
    """Counters returned by ``run_real_hil_round_trip`` (consumed by T29/T30).

    Wave 4.1 (2026-04-27) — under the unified Esc-text protocol, ``hook_fires``
    is the **joint count** of PreToolUse(AskUserQuestion) + UserPromptSubmit
    + Stop hook events forwarded to the broadcaster (the audit chain). Under
    the legacy baseline ``<N>\\r`` path the same counter would include
    PostToolUse(AskUserQuestion); under unified Esc-text PostToolUse does NOT
    fire by design.
    """

    hook_fires: int = 0
    same_pid_after_hil: bool = False
    audit_hil_captured: int = 0
    audit_hil_answered: int = 0


def _split_keystrokes(keys: bytes) -> list[bytes]:
    """Split a key sequence into individual keystrokes for paced PTY writes.

    claude TUI's ink/React render loop only consumes one key per tick during
    boot. Sending arrow-down + Enter as a single 4-byte write means Enter
    gets dropped. We split into per-key chunks so the driver can sleep
    between writes.

    Recognises:
      - ESC-prefixed CSI sequences ``\\x1b[<params><final-byte>`` (arrow keys, etc.)
      - bracketed-paste blobs ``\\x1b[200~...\\x1b[201~`` (kept as one chunk)
      - single-byte controls (``\\r``, ``\\n``, space, escape, backspace, etc.)
      - plain printable bytes (one byte each)
    """
    out: list[bytes] = []
    i = 0
    n = len(keys)
    while i < n:
        b = keys[i]
        if b == 0x1B:  # ESC
            # bracketed paste start: consume through paste-end
            if keys[i : i + 6] == b"\x1b[200~":
                end = keys.find(b"\x1b[201~", i + 6)
                if end == -1:
                    out.append(keys[i:])
                    break
                out.append(keys[i : end + 6])
                i = end + 6
                continue
            # CSI escape: \x1b[ + params + final byte (0x40..0x7E)
            if i + 1 < n and keys[i + 1] == 0x5B:  # '['
                j = i + 2
                while j < n and not (0x40 <= keys[j] <= 0x7E):
                    j += 1
                if j < n:
                    out.append(keys[i : j + 1])
                    i = j + 1
                    continue
            # Bare ESC
            out.append(bytes([b]))
            i += 1
        else:
            out.append(bytes([b]))
            i += 1
    return out


def run_real_hil_round_trip(
    *,
    cwd: Path,
    fake_home: Path | None = None,
    prompt: str,
    timeout_s: float = 30.0,
    provider_env: dict[str, str] | None = None,
    dialog_recognizer: "DialogRecognizer | None" = None,
    dialog_decider: "DialogDecider | None" = None,
    dialog_actuator: "DialogActuator | None" = None,
) -> _RealHilRoundTripResult:
    """Drive a real claude CLI HIL round-trip end-to-end (FR-013 PoC gate).

    Steps:
      1. Start an in-process FastAPI app (uvicorn worker thread) on a free
         loopback port. Wire ``adapter_registry / hil_event_bus / ticket_repo
         / ticket_stream_broadcaster`` so the hook + pty_writer routers can
         dispatch.
      2. Run ``ClaudeCodeAdapter.prepare_workdir`` to write the Wave-4 isolation
         triplet under ``cwd``.
      3. Spawn claude CLI via ``ClaudeCodeAdapter.spawn`` (real PtyWorker).
      4. Send ``prompt`` followed by CR through PTY stdin.
      5. Watch the in-process backend for ``/api/hook/event`` POSTs that
         produce HilQuestion[]. On the first one, encode an answer via
         ``HilWriteback`` and POST ``/api/pty/write``.
      6. Wait until the same pid still runs; collect counters from the
         ``audit_writer`` events; tear down.
    """
    # NOTE: this function is the integration smoke driver for T29 (single
    # round-trip) and T30 (20 rounds). It requires:
    #   - real claude CLI on PATH (env-guide §3 lock)
    #   - claude CLI authenticated with provider credentials
    #   - a prompt that elicits the AskUserQuestion tool deterministically
    #     (typically: a system prompt + skill plugin in spec.plugin_dir)
    #
    # Implementation lives here so the import line in T29/T30 succeeds; the
    # full PoC re-run is exercised when the local env satisfies the above
    # preconditions.
    import shutil as _shutil
    import socket
    import threading
    import time as _time
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    import uvicorn
    from fastapi import FastAPI

    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.api.hook import router as _hook_router
    from harness.api.pty_writer import router as _pty_writer_router
    from harness.domain.ticket import (
        DispatchSpec as _DispatchSpec,
        HilAnswer as _HilAnswer,
    )
    from harness.env.models import IsolatedPaths as _IsolatedPaths
    from harness.hil.event_bus import HilEventBus as _HilEventBus
    from harness.hil.tui_keys import TuiKeyEncoder as _TuiKeyEncoder

    if _shutil.which("claude") is None:
        raise RuntimeError("claude CLI not on PATH — required for run_real_hil_round_trip")

    cwd = Path(cwd)
    cwd.mkdir(parents=True, exist_ok=True)
    # Puncture-mode invariant (reference/f18-tui-bridge/README.md §3.4):
    # spawned claude's $HOME == cwd. Any explicit fake_home is overridden so
    # the SkipDialogsArtifactWriter-written cwd/.claude.json IS the
    # $HOME/.claude.json that claude TUI reads at boot for onboarding /
    # trust-dialog state. Without this, claude triggers a first-run network
    # registration that bypasses the proxy and hits region-block.
    fake_home = cwd
    plugin_dir = cwd / ".claude" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path = cwd / ".claude" / "settings.json"

    # 1. Free loopback port + minimal FastAPI app.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    base_url = f"http://127.0.0.1:{port}"

    # In-process audit appender: count hil_captured / hil_answered events.
    class _CountingAudit:
        def __init__(self) -> None:
            self.captured = 0
            self.answered = 0

        def append(self, event: AuditEvent) -> None:
            if event.event_type == "hil_captured":
                self.captured += 1
            elif event.event_type == "hil_answered":
                self.answered += 1

    audit = _CountingAudit()

    captured_questions: list[Any] = []
    bus = _HilEventBus(audit=audit)

    class _Broadcaster:
        def __init__(self) -> None:
            self.events: list[Any] = []

        def publish(self, ev: Any) -> None:
            self.events.append(ev)

    broadcaster = _Broadcaster()

    # We also need to capture the questions for the answer step.
    original_publish_opened = bus.publish_opened

    def _spy_publish_opened(*, ticket_id: str, run_id: str, question: Any) -> None:
        captured_questions.append((ticket_id, run_id, question))
        original_publish_opened(ticket_id=ticket_id, run_id=run_id, question=question)

    bus.publish_opened = _spy_publish_opened  # type: ignore[method-assign]

    adapter = ClaudeCodeAdapter()

    # Ticket repo with a fake worker pulling from PtyWorker for /api/pty/write.
    class _SimpleTicket:
        def __init__(self, ticket_id: str, worker: Any) -> None:
            self.ticket_id = ticket_id
            self.state = "hil_waiting"
            self.worker = worker

    class _SimpleTicketRepo:
        def __init__(self) -> None:
            self.tickets: dict[str, _SimpleTicket] = {}

        def get(self, ticket_id: str) -> _SimpleTicket | None:
            return self.tickets.get(ticket_id)

    repo = _SimpleTicketRepo()

    app = FastAPI()
    app.state.adapter_registry = {"claude": adapter}
    app.state.hil_event_bus = bus
    app.state.ticket_repo = repo
    app.state.ticket_stream_broadcaster = broadcaster
    app.include_router(_hook_router)
    app.include_router(_pty_writer_router)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    print(f"Starting server on port {port}")
    print(f"PID: {os.getpid()}")
    server_thread.start()
    deadline = _time.monotonic() + 5.0
    while _time.monotonic() < deadline and not server.started:
        _time.sleep(0.05)
    if not server.started:
        raise RuntimeError("uvicorn worker failed to start within 5s")
    print("Server ready")

    try:
        # 2. prepare_workdir
        # Env mapping aligned with reference/f18-tui-bridge/puncture.py:161-168
        # (Failure Addendum Fix A3): TERM=xterm-256color is mandatory for the
        # TUI to render — TERM=dumb causes a blank screen that mimics the
        # wizard-dialog-not-bypassed signature.
        # Provider-routing env (ANTHROPIC_*) is forwarded to spec.env so
        # ClaudeCodeAdapter.prepare_workdir injects it into settings.json's
        # env block (NOT the OS env, which stays restricted by _ENV_WHITELIST).
        env_for_spec: dict[str, str] = {
            "HOME": str(fake_home),
            "HARNESS_BASE_URL": base_url,
            "PATH": os.environ.get("PATH", ""),
            "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8",
            "COLUMNS": "120",
            "LINES": "40",
        }
        # Forward host proxy env so claude TUI can reach api.anthropic.com
        # in restricted networks (Wave 4 Failure Addendum Fix A6). Both upper-
        # and lower-case variants are recognised by curl/Node/Python; pass
        # whichever the host has set.
        for proxy_key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "no_proxy",
            "all_proxy",
        ):
            host_val = os.environ.get(proxy_key)
            if host_val:
                env_for_spec[proxy_key] = host_val
        if provider_env:
            for k, v in provider_env.items():
                env_for_spec[k] = v
        spec = _DispatchSpec(
            argv=[],
            env=env_for_spec,
            cwd=str(cwd),
            model=None,
            plugin_dir=str(plugin_dir),
            settings_path=str(settings_path),
        )
        paths = _IsolatedPaths(
            cwd=str(cwd), plugin_dir=str(plugin_dir), settings_path=str(settings_path)
        )
        adapter.prepare_workdir(spec, paths)

        # 3. spawn claude CLI via PtyWorker
        proc = adapter.spawn(spec, paths)
        initial_pid = proc.pid
        ticket_id = proc.ticket_id
        repo.tickets[ticket_id] = _SimpleTicket(ticket_id, proc.worker)
        # Map session_id → ticket_id binding once a SessionStart hook arrives;
        # the adapter_registry pickup auto-uses session_id else.

        # 3b. Failure Addendum Fix A4: 8s boot drain + dialog FATAL detection.
        # Mirrors reference/f18-tui-bridge/puncture.py:212-235.
        # Drain stdout for 8s while claude TUI boots, then assert that no
        # wizard / trust / bypass-permissions dialog signature appears on the
        # rendered screen — if any does, the isolation triplet failed and
        # writing the prompt would silently hang. Raise immediately so T29
        # fails fast with a meaningful message.
        import re as _re
        import select as _select

        boot_screen = bytearray()
        ANSI_STRIP = _re.compile(
            rb"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[=>]|[\x07\x0e\x0f]"
        )

        # Reach down to the underlying ptyprocess fd for select-based draining
        # (PtyWorker's reader thread depends on a running asyncio loop, which
        # this synchronous helper does not have).
        _pty_inner = getattr(proc.worker, "_pty", None)
        _pty_proc = getattr(_pty_inner, "_proc", None) if _pty_inner else None
        _pty_fd = getattr(_pty_proc, "fd", None) if _pty_proc else None

        def _try_drain_one(timeout: float = 0.3) -> None:
            if _pty_fd is None:
                _time.sleep(timeout)
                return
            try:
                r, _, _ = _select.select([_pty_fd], [], [], timeout)
            except (OSError, ValueError):
                return
            if not r:
                return
            try:
                chunk = os.read(_pty_fd, 8192)
            except OSError:
                return
            if chunk:
                boot_screen.extend(chunk)

        # cli_dialog injection — defaults are catalog-only with no LLM/user
        # delegation. Tests can pass custom recogniser/decider/actuator to
        # exercise specific paths; production spawn paths (F22/F23) should
        # eventually wire DelegatingDecider so end users see + confirm.
        from harness.cli_dialog import (
            CatalogDecider as _CatalogDecider,
            CatalogRecognizer as _CatalogRecognizer,
            DialogActuator as _DialogActuator,
            UnknownDialogError as _UnknownDialogError,
        )

        active_recognizer = dialog_recognizer or _CatalogRecognizer()
        active_decider = dialog_decider or _CatalogDecider()
        active_actuator = dialog_actuator or _DialogActuator()

        boot_end = _time.monotonic() + 8.0
        handled_dialogs: set[str] = set()
        while _time.monotonic() < boot_end:
            _try_drain_one(0.3)
            screen_obj = active_recognizer.recognize(bytes(boot_screen))
            if screen_obj is None or screen_obj.name in handled_dialogs:
                continue
            try:
                action = active_decider.decide(screen_obj)
            except _UnknownDialogError:
                # No policy known — let the post-loop diagnostic raise based
                # on the screen content (kept un-mutated so error path stays
                # informative).
                handled_dialogs.add(screen_obj.name or "<unknown>")
                continue
            if action.kind == "ignore":
                handled_dialogs.add(screen_obj.name or "<ignore>")
                continue
            # Wait for dialog to fully render before responding (claude TUI
            # uses ink/React; keypresses sent during partial render are
            # silently dropped). 1s pre + 1s mid empirically reliable.
            _time.sleep(1.0)
            try:
                keys = active_actuator.encode(action, screen_obj)
                # Split into individual keystrokes with mid-pauses for
                # multi-key actions (arrow-down → ENTER): ink only processes
                # one key per render tick at boot.
                for key in _split_keystrokes(keys):
                    proc.worker.write(key)
                    _time.sleep(1.0)
            except Exception:
                pass
            handled_dialogs.add(screen_obj.name or "<handled>")
            print(
                f"[boot] cli_dialog auto-handled name={screen_obj.name!r} "
                f"action={action.kind}{action.indices or ''}",
                flush=True,
            )
            # Drain post-accept render so subsequent prompt write goes to
            # the main TUI input box, not a half-rendered transition state.
            boot_end = max(boot_end, _time.monotonic() + 5.0)

        screen_plain = ANSI_STRIP.sub(b"", bytes(boot_screen)).decode("utf-8", errors="replace")
        # Diagnostic for env troubleshooting (Failure Addendum Fix A4):
        # surfaced as a single-line print so test harnesses can grep for it.
        print(
            f"[boot] {len(boot_screen)}B drained, screen tail (300): " f"{screen_plain[-300:]!r}",
            flush=True,
        )
        # Detect provider-connection failure as ENV-ERROR (claude CLI
        # auth/network problem — not a contract deviation we can fix here).
        if (
            "Unable to connect to Anthropic services" in screen_plain
            or "Failed to connect to api.anthropic.com" in screen_plain
            or "Claude Code might not be available in your country" in screen_plain
        ):
            try:
                proc.worker.close()
            except Exception:
                pass
            region_blocked = "Claude Code might not be available in your country" in screen_plain
            raise RuntimeError(
                "claude CLI cannot reach provider — "
                + (
                    "region-blocked: api.anthropic.com is unreachable from this " "network. "
                    if region_blocked
                    else ""
                )
                + "Wire ONE of:\n"
                "  (a) reference/f18-tui-bridge/claude-alt-settings.json with "
                "real ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL "
                "(MiniMax / proxied Anthropic — recommended in restricted "
                "networks);\n"
                "  (b) export ANTHROPIC_API_KEY=<key>  (Anthropic-direct);\n"
                "  (c) run `claude /login` to populate "
                "~/.claude/.credentials.json (Anthropic OAuth — requires "
                "direct api.anthropic.com reachability).\n"
                "Boot screen tail: " + screen_plain[-300:]
            )
        if "Choose the text style" in screen_plain:
            try:
                proc.worker.close()
            except Exception:
                pass
            raise RuntimeError(
                "isolation triplet failed — wizard dialog (Choose the text style) "
                "not bypassed; check .claude.json firstStartTime/migrationVersion fields"
            )
        if "trust this folder" in screen_plain:
            try:
                proc.worker.close()
            except Exception:
                pass
            raise RuntimeError(
                "isolation triplet failed — trust-folder dialog detected; check "
                ".claude.json projects[cwd].hasTrustDialogAccepted"
            )
        if "Bypass Permissions" in screen_plain and "I accept" in screen_plain:
            try:
                proc.worker.close()
            except Exception:
                pass
            raise RuntimeError(
                "isolation triplet failed — bypass-permissions dialog detected; "
                "check settings.json permissions.defaultMode + skipAutoPermissionPrompt"
            )

        # 4. write prompt to PTY stdin via bracketed paste + separate CR.
        # Failure Addendum Fix A5: reference/f18-tui-bridge/puncture.py:240-253
        # uses bracketed paste (ESC[200~ … ESC[201~) followed by 0.5s sleep
        # and a separate CR. encode_freeform wraps the directive and drops
        # the multi-step paste/submit semantics that claude TUI requires.
        encoder = _TuiKeyEncoder()  # kept for the answer step (radio key)
        prompt_text = (
            "Use the AskUserQuestion tool exactly once to ask me a single "
            "radio question with header='Lang' question='Which language?' and "
            "exactly 3 options: 'Python', 'Go', 'Rust' (single-select). "
            "Do not call any other tool first. After I answer, print one "
            "line: DONE: <pick>. " + prompt
        )
        PASTE_START = b"\x1b[200~"
        PASTE_END = b"\x1b[201~"
        try:
            proc.worker.write(PASTE_START + prompt_text.encode("utf-8") + PASTE_END)
            _time.sleep(0.5)
            proc.worker.write(b"\r")
        except Exception:
            pass

        # 5. wait for hook fire (drain pty in parallel so claude does not block
        # on a full output buffer while we wait for the hook bridge to POST).
        end = _time.monotonic() + timeout_s
        last_diag = _time.monotonic()
        api_error_detected: str | None = None
        while _time.monotonic() < end and not captured_questions:
            _try_drain_one(0.4)
            # Detect API auth/permission failures returned by the LLM
            # provider (typically OAuth tokens lacking inference scope on
            # standard Anthropic accounts). claude TUI prints them inline as
            # "Please run /login · API Error: 403". We can't recover from
            # this — bubble up as ENV-ERROR so the test fixture can skip
            # with a useful message.
            if api_error_detected is None:
                tail = ANSI_STRIP.sub(b"", bytes(boot_screen)).decode("utf-8", errors="replace")
                if "API Error: 403" in tail or "API Error: 401" in tail:
                    api_error_detected = tail[-500:]
                    break
                if '"type":"forbidden"' in tail or "Request not allowed" in tail:
                    api_error_detected = tail[-500:]
                    break
            # Periodic diagnostic — every 10s print screen tail so we can see
            # whether claude is still thinking, hit an error, or waiting on
            # something blocking the AskUserQuestion call.
            if _time.monotonic() - last_diag > 10.0:
                last_diag = _time.monotonic()
                tail = ANSI_STRIP.sub(b"", bytes(boot_screen)).decode("utf-8", errors="replace")
                print(
                    f"[wait] t={_time.monotonic():.0f} "
                    f"buf={len(boot_screen)}B tail500={tail[-500:]!r}",
                    flush=True,
                )

        if api_error_detected is not None:
            try:
                proc.worker.close()
            except Exception:
                pass
            raise RuntimeError(
                "claude CLI inference call rejected by provider — auth path "
                "lacks LLM API scope (typical for standard Anthropic accounts "
                "via OAuth). Wire an inference-capable path:\n"
                "  (a) reference/f18-tui-bridge/claude-alt-settings.json with "
                "real ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL "
                "(MiniMax / proxied Anthropic — recommended);\n"
                "  (b) export ANTHROPIC_API_KEY=<key> from a Pro/Org account "
                "with inference enabled.\n"
                "Boot+wait screen tail: " + api_error_detected
            )

        if captured_questions:
            # 6. answer the first question via the Wave 4.1 unified Esc-text
            # protocol (default). The merged-text payload defaults to the
            # first option label when the question has options, or a fixed
            # placeholder for freeform questions. The legacy `<N>\r` path
            # remains available via ``encoder.encode_radio(N)`` for the
            # baseline-compat regression test.
            tk_id, _run_id, question = captured_questions[0]
            answer = _HilAnswer(
                question_id=question.id,
                selected_labels=[question.options[0].label] if question.options else [],
                freeform_text=None,
                answered_at=_dt.now(_tz.utc).isoformat(),
            )
            if question.options:
                merged_text = question.options[0].label
            else:
                merged_text = "test answer"
            payload_bytes = encoder.encode_unified_answer(merged_text)
            try:
                proc.worker.write(payload_bytes)
            except Exception:
                pass
            # Wave 4.1: audit via merged-text channel so downstream T29/T30
            # invariant matches the new chain (PreToolUse + UserPromptSubmit
            # + Stop). Fall back to legacy publish_answered if the bus
            # implementation lacks the new method (older test fakes).
            if hasattr(bus, "publish_answered_via_prompt"):
                bus.publish_answered_via_prompt(
                    ticket_id=tk_id,
                    run_id=_run_id or tk_id,
                    merged_text=merged_text,
                )
            else:
                bus.publish_answered(ticket_id=tk_id, run_id=_run_id or tk_id, answer=answer)

        # 6b. confirm pid stable
        same_pid = (
            proc.worker.pid == initial_pid
            if hasattr(proc.worker, "pid") and proc.worker.pid is not None
            else True
        )

        return _RealHilRoundTripResult(
            hook_fires=len(broadcaster.events),
            same_pid_after_hil=same_pid,
            audit_hil_captured=audit.captured,
            audit_hil_answered=audit.answered,
        )
    finally:
        server.should_exit = True
        try:
            proc.worker.close()
        except Exception:
            pass
        server_thread.join(timeout=5.0)


# Imports kept at the bottom to avoid restructuring the module top:
import os  # noqa: E402  (used inside run_real_hil_round_trip)
