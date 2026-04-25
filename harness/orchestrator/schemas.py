"""F20 · Orchestrator pydantic schemas (Design §6.2.4 alignment).

Public payloads consumed by the orchestrator REST/WS layer + by the internal
supervisor / phase-route / control-bus components. ``extra="forbid"`` everywhere
except :class:`PhaseRouteResult`, which uses ``extra="ignore"`` to honour
NFR-015 (relaxed parsing — new fields are silently dropped).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# REST payloads — Run lifecycle
# ---------------------------------------------------------------------------
class RunStartRequest(BaseModel):
    """Payload for ``POST /api/runs/start`` (IAPI-002)."""

    model_config = ConfigDict(extra="forbid")

    workdir: str


class RunStatus(BaseModel):
    """Return shape of ``start_run`` / ``pause_run`` / ``cancel_run``."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    state: Literal[
        "starting",
        "running",
        "pause_pending",
        "paused",
        "cancelling",
        "cancelled",
        "completed",
        "failed",
    ]
    workdir: str
    started_at: str
    ended_at: str | None = None
    current_phase: str | None = None
    current_feature: str | None = None


# ---------------------------------------------------------------------------
# Ticket internal command/outcome objects
# ---------------------------------------------------------------------------
class TicketCommand(BaseModel):
    """Internal payload for :meth:`TicketSupervisor.run_ticket`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["spawn", "retry"] = "spawn"
    skill_hint: str | None = None
    feature_id: str | None = None
    tool: Literal["claude", "opencode"] = "claude"
    run_id: str
    parent_ticket: str | None = None
    retry_count: int = 0


class TicketOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    final_state: str
    verdict: str | None = None
    anomaly: str | None = None


# ---------------------------------------------------------------------------
# Recovery decisions / signals
# ---------------------------------------------------------------------------
class RecoveryDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["retry", "skipped", "abort", "escalate"]
    delay_seconds: float | None = None
    reason: str | None = None


class SignalEvent(BaseModel):
    """Filesystem signal yielded by :class:`SignalFileWatcher`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "bugfix_request",
        "increment_request",
        "feature_list_changed",
        "srs_changed",
        "design_changed",
        "ats_changed",
        "ucd_changed",
        "rules_changed",
    ]
    path: str
    mtime: float = 0.0


__all__ = [
    "RecoveryDecision",
    "RunStartRequest",
    "RunStatus",
    "SignalEvent",
    "TicketCommand",
    "TicketOutcome",
]
