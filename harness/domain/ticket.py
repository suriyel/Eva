"""Pydantic v2 models for F02 · Persistence Core (Design §5.4 / §5.6).

Every model uses ``extra="forbid"`` so accidental drift from the contract
is caught at construction time. Optional fields are declared explicitly
with ``None`` defaults — FR-007 AC-1 requires "缺失字段为 null 而非不存在".
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Ticket state enum (Design §5.4) — values MUST match DDL CHECK constants.
# ---------------------------------------------------------------------------
class TicketState(str, Enum):
    """Nine canonical ticket states (Design §5.3 / §5.4)."""

    PENDING = "pending"
    RUNNING = "running"
    CLASSIFYING = "classifying"
    HIL_WAITING = "hil_waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    RETRYING = "retrying"
    INTERRUPTED = "interrupted"


# ---------------------------------------------------------------------------
# Run aggregate (Design §5.3 runs table mirror for DAO round-trip).
# ---------------------------------------------------------------------------
RunStateLiteral = Literal[
    "idle",
    "starting",
    "running",
    "paused",
    "cancelled",
    "completed",
    "failed",
]


class Run(BaseModel):
    """Mirror of the ``runs`` DB row (Design §5.3)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    workdir: str
    state: RunStateLiteral = "starting"
    current_phase: str | None = None
    current_feature: str | None = None
    cost_usd: float = 0.0
    num_turns: int = 0
    head_start: str | None = None
    head_latest: str | None = None
    started_at: str
    ended_at: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ticket sub-structures (Design §5.4).
# ---------------------------------------------------------------------------
class DispatchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str | None = None
    argv: list[str]
    env: dict[str, str]
    cwd: str
    model: str | None = None
    model_provenance: Literal["per-ticket", "per-skill", "run-default", "cli-default"] = (
        "cli-default"
    )
    mcp_config: str | None = None
    plugin_dir: str
    settings_path: str


class ExecutionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pid: int | None = None
    started_at: str | None = None
    ended_at: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    cost_usd: float = 0.0


class OutputInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_text: str | None = None
    stream_log_ref: str | None = None
    session_id: str | None = None


class HilOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    description: str | None = None


class HilQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["single_select", "multi_select", "free_text"]
    header: str
    question: str
    options: list[HilOption] = Field(default_factory=list)
    multi_select: bool = False
    allow_freeform: bool = False


class HilAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    selected_labels: list[str] = Field(default_factory=list)
    freeform_text: str | None = None
    answered_at: str


class HilInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected: bool = False
    source: Literal["AskUserQuestion", "Question"] | None = None
    questions: list[HilQuestion] = Field(default_factory=list)
    answers: list[HilAnswer] = Field(default_factory=list)


class AnomalyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cls: Literal["context_overflow", "rate_limit", "network", "timeout", "skill_error"]
    detail: str
    retry_count: int = 0
    next_attempt_at: str | None = None


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["HIL_REQUIRED", "CONTINUE", "RETRY", "ABORT", "COMPLETED"]
    reason: str
    anomaly: str | None = None
    hil_source: str | None = None
    backend: Literal["llm", "rule"]


class GitCommit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha: str
    message: str
    author: str
    time: str
    files_changed: list[str] = Field(default_factory=list)


class GitContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    head_before: str | None = None
    head_after: str | None = None
    commits: list[GitCommit] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Ticket aggregate root (Design §5.4).
# ---------------------------------------------------------------------------
class Ticket(BaseModel):
    """Ticket aggregate root (Design §5.4, FR-007)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    parent_ticket: str | None = None
    depth: int = Field(0, ge=0, le=2)
    tool: Literal["claude", "opencode"]
    skill_hint: str | None = None
    state: TicketState
    dispatch: DispatchSpec
    execution: ExecutionInfo
    output: OutputInfo
    hil: HilInfo
    anomaly: AnomalyInfo | None = None
    classification: Classification | None = None
    git: GitContext


# ---------------------------------------------------------------------------
# AuditEvent (Design §5.6).
# ---------------------------------------------------------------------------
AuditEventType = Literal[
    "state_transition",
    "hil_captured",
    "hil_answered",
    "anomaly_detected",
    "retry_scheduled",
    "classification",
    "git_snapshot",
    "watchdog_trigger",
    "interrupted",
]


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ts: str = Field(min_length=1)
    ticket_id: str
    run_id: str
    event_type: AuditEventType
    state_from: TicketState | None = None
    state_to: TicketState | None = None
    payload: dict[str, Any] | None = None


# Re-export domain exceptions so ``from harness.domain.ticket import
# TicketNotFoundError`` works for the integration tests. The late import
# keeps the module side-effect free at the top of the file (state_machine
# imports TicketState from here via TYPE_CHECKING).
from harness.domain.state_machine import (  # noqa: E402  circular-safe late import
    RunNotFoundError,
    TicketNotFoundError,
    TransitionError,
)

__all__ = [
    "AnomalyInfo",
    "AuditEvent",
    "AuditEventType",
    "Classification",
    "DispatchSpec",
    "ExecutionInfo",
    "GitCommit",
    "GitContext",
    "HilAnswer",
    "HilInfo",
    "HilOption",
    "HilQuestion",
    "OutputInfo",
    "Run",
    "RunNotFoundError",
    "RunStateLiteral",
    "Ticket",
    "TicketNotFoundError",
    "TicketState",
    "TransitionError",
]
