"""Harness domain models (F02 · feature #2).

Exposes `Ticket`, `TicketState`, `Run`, `AuditEvent`, the sub-structures
required by `TicketRepository` / `AuditWriter`, and the domain-level
exceptions (`TransitionError`, `TicketNotFoundError`, `RunNotFoundError`).

All types are pydantic v2 models with ``extra="forbid"`` — drift from the
contract at Design §5.4/§5.6 raises immediately.
"""

from __future__ import annotations

from harness.domain.state_machine import (
    TicketNotFoundError,
    TicketStateMachine,
    TransitionError,
    RunNotFoundError,
)
from harness.domain.ticket import (
    AnomalyInfo,
    AuditEvent,
    Classification,
    DispatchSpec,
    ExecutionInfo,
    GitCommit,
    GitContext,
    HilAnswer,
    HilInfo,
    HilOption,
    HilQuestion,
    OutputInfo,
    Run,
    Ticket,
    TicketState,
)

__all__ = [
    "AnomalyInfo",
    "AuditEvent",
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
    "Ticket",
    "TicketNotFoundError",
    "TicketState",
    "TicketStateMachine",
    "TransitionError",
]
