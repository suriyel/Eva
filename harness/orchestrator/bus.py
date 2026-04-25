"""F20 · RunControlBus (IAPI-019 Provider) + WS broadcast helpers.

Two roles:
    * **Command sink** — :meth:`submit` validates :class:`RunControlCommand`
      and dispatches to the bound :class:`RunOrchestrator`. Exposed to F21
      for HTTP → orchestrator glue.
    * **Event bus** — :meth:`broadcast_run_event` /
      :meth:`broadcast_anomaly` / :meth:`broadcast_signal` /
      :meth:`broadcast_stream_event` push WebSocket envelopes
      (``WsEvent{kind, payload}``) to the registered subscribers.

Test instances expose :meth:`captured_anomaly_events` so unit tests can
inspect what was broadcast without needing real WebSocket clients.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from harness.orchestrator.errors import InvalidCommand
from harness.orchestrator.schemas import SignalEvent


# ---------------------------------------------------------------------------
# Command + ack pydantic models
# ---------------------------------------------------------------------------
class RunControlCommand(BaseModel):
    """User intent: start / pause / cancel / skip / abort."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["start", "pause", "cancel", "skip_ticket", "force_abort"]
    run_id: str | None = None
    target_ticket_id: str | None = None
    workdir: str | None = None


class RunControlAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    current_state: str
    reason: str | None = None


# ---------------------------------------------------------------------------
# Anomaly / Run event envelopes (lightweight dataclasses; not pydantic)
# ---------------------------------------------------------------------------
@dataclass
class AnomalyEvent:
    kind: Literal["AnomalyDetected", "RetryScheduled", "Escalated"]
    cls: str | None = None
    reason: str | None = None
    ticket_id: str | None = None
    retry_count: int = 0


@dataclass
class RunEvent:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class _SignalSubscription:
    received: list[dict[str, Any]] = field(default_factory=list)

    def received_messages(self) -> list[dict[str, Any]]:
        return list(self.received)


# ---------------------------------------------------------------------------
# Bus
# ---------------------------------------------------------------------------
class RunControlBus:
    """Command sink + WS broadcaster (Provider for IAPI-019/001)."""

    def __init__(self) -> None:
        self._orchestrator: Any | None = None
        self._anomaly_events: list[AnomalyEvent] = []
        self._run_events: list[RunEvent] = []
        self._stream_events: list[dict[str, Any]] = []
        self._signal_subs: list[_SignalSubscription] = []
        # F23 · queue subscribers for WS broadcasters.
        self._run_subs: list[asyncio.Queue[dict[str, Any]]] = []
        self._anomaly_subs: list[asyncio.Queue[dict[str, Any]]] = []
        self._signal_queue_subs: list[asyncio.Queue[dict[str, Any]]] = []
        self._stream_subs: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    # ------------------------------------------------------------------
    @classmethod
    def build_test_default(cls) -> "RunControlBus":
        return cls()

    def attach_orchestrator(self, orch: Any) -> None:
        self._orchestrator = orch

    # ------------------------------------------------------------------
    def subscribe_signal_test_client(self) -> _SignalSubscription:
        sub = _SignalSubscription()
        self._signal_subs.append(sub)
        return sub

    # ------------------------------------------------------------------
    # submit_command (alias: submit) — IAPI-019 entry point
    # ------------------------------------------------------------------
    async def submit(self, cmd: RunControlCommand) -> RunControlAck:
        return await self.submit_command(cmd)

    async def submit_command(self, cmd: RunControlCommand) -> RunControlAck:
        # Validation per Boundary table T40.
        if cmd.kind in {"skip_ticket", "force_abort"} and not cmd.target_ticket_id:
            raise InvalidCommand(f"command kind={cmd.kind!r} requires target_ticket_id")

        orch = self._orchestrator
        if orch is None:
            raise InvalidCommand("RunControlBus not attached to an orchestrator")

        if cmd.kind == "start":
            if not cmd.workdir:
                raise InvalidCommand("start command requires workdir")
            from harness.orchestrator.schemas import RunStartRequest

            status = await orch.start_run(RunStartRequest(workdir=cmd.workdir))
            return RunControlAck(accepted=True, current_state=status.state)
        if cmd.kind == "pause":
            if not cmd.run_id:
                raise InvalidCommand("pause command requires run_id")
            status = await orch.pause_run(cmd.run_id)
            return RunControlAck(accepted=True, current_state=status.state)
        if cmd.kind == "cancel":
            if not cmd.run_id:
                raise InvalidCommand("cancel command requires run_id")
            status = await orch.cancel_run(cmd.run_id)
            return RunControlAck(accepted=True, current_state=status.state)
        if cmd.kind == "skip_ticket":
            assert cmd.target_ticket_id is not None
            await orch.skip_anomaly(cmd.target_ticket_id)
            return RunControlAck(accepted=True, current_state="retrying")
        if cmd.kind == "force_abort":
            assert cmd.target_ticket_id is not None
            await orch.force_abort_anomaly(cmd.target_ticket_id)
            return RunControlAck(accepted=True, current_state="aborted")
        raise InvalidCommand(f"unknown command kind: {cmd.kind!r}")

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------
    def broadcast_run_event(self, event: RunEvent) -> None:
        self._run_events.append(event)
        envelope = {"kind": event.kind, "payload": dict(event.payload)}
        for q in list(self._run_subs):
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                pass

    def broadcast_anomaly(self, event: AnomalyEvent) -> None:
        self._anomaly_events.append(event)
        envelope = {
            "kind": event.kind,
            "payload": {
                "ticket_id": event.ticket_id,
                "cls": event.cls,
                "reason": event.reason,
                "retry_count": event.retry_count,
            },
        }
        for q in list(self._anomaly_subs):
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                pass

    def broadcast_signal(self, event: SignalEvent) -> None:
        envelope = {
            "kind": "signal_file_changed",
            "payload": {"kind": event.kind, "path": event.path, "mtime": event.mtime},
        }
        for sub in self._signal_subs:
            sub.received.append(envelope)
        for q in list(self._signal_queue_subs):
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                pass

    def broadcast_stream_event(self, event: dict[str, Any]) -> None:
        """Push a stream event to /ws/stream/{ticket_id} subscribers.

        Captures into ``_stream_events`` for replay-on-subscribe and pushes
        the envelope to per-ticket queues. ``event`` is a flat dict with at
        least ``ticket_id``; the WS envelope is wrapped as
        ``{"kind": "StreamEvent", "payload": event}``.
        """
        captured = dict(event)
        self._stream_events.append(captured)
        ticket_id = str(event.get("ticket_id") or "")
        envelope = {"kind": "StreamEvent", "payload": captured}
        if ticket_id:
            for q in list(self._stream_subs.get(ticket_id, [])):
                try:
                    q.put_nowait(envelope)
                except asyncio.QueueFull:
                    pass

    # ------------------------------------------------------------------
    # WS subscribe / unsubscribe (F23)
    # ------------------------------------------------------------------
    def subscribe_run(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._run_subs.append(q)
        return q

    def unsubscribe_run(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        try:
            self._run_subs.remove(q)
        except ValueError:
            pass

    def subscribe_anomaly(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._anomaly_subs.append(q)
        return q

    def unsubscribe_anomaly(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        try:
            self._anomaly_subs.remove(q)
        except ValueError:
            pass

    def subscribe_signal(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._signal_queue_subs.append(q)
        return q

    def unsubscribe_signal(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        try:
            self._signal_queue_subs.remove(q)
        except ValueError:
            pass

    def subscribe_stream(self, ticket_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._stream_subs.setdefault(ticket_id, []).append(q)
        return q

    def unsubscribe_stream(self, ticket_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._stream_subs.get(ticket_id)
        if not subs:
            return
        try:
            subs.remove(q)
        except ValueError:
            pass
        if not subs:
            self._stream_subs.pop(ticket_id, None)

    # ------------------------------------------------------------------
    # Test introspection
    # ------------------------------------------------------------------
    def captured_anomaly_events(self) -> list[AnomalyEvent]:
        return list(self._anomaly_events)

    def captured_run_events(self) -> list[RunEvent]:
        return list(self._run_events)

    def captured_stream_events(self) -> list[dict[str, Any]]:
        return list(self._stream_events)


__all__ = [
    "AnomalyEvent",
    "RunControlAck",
    "RunControlBus",
    "RunControlCommand",
    "RunEvent",
]
