"""F20 · Orchestrator errors.

Each error carries a ``http_status`` hint so REST handlers can transparently
project the failure into a status code (no separate mapping table).
"""

from __future__ import annotations


class RunStartError(Exception):
    """Raised by :meth:`RunOrchestrator.start_run` for refusable inputs."""

    def __init__(
        self,
        *,
        reason: str,
        message: str | None = None,
        http_status: int = 400,
        error_code: str | None = None,
    ) -> None:
        self.reason = reason
        self.http_status = http_status
        self.error_code = error_code or reason.upper()
        super().__init__(message or f"start_run rejected: reason={reason}")


class RunNotFound(Exception):
    http_status = 404

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"run not found: {run_id!r}")


class InvalidRunState(Exception):
    http_status = 409

    def __init__(self, run_id: str, state: str) -> None:
        self.run_id = run_id
        self.state = state
        super().__init__(f"invalid run state: run={run_id!r} state={state!r}")


class TicketNotFound(Exception):
    http_status = 404

    def __init__(self, ticket_id: str) -> None:
        self.ticket_id = ticket_id
        super().__init__(f"ticket not found: {ticket_id!r}")


class InvalidTicketState(Exception):
    http_status = 409

    def __init__(self, ticket_id: str, state: str) -> None:
        self.ticket_id = ticket_id
        self.state = state
        super().__init__(f"invalid ticket state: ticket={ticket_id!r} state={state!r}")


class InvalidCommand(Exception):
    http_status = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)


class PhaseRouteError(Exception):
    """Raised when phase_route subprocess exits non-zero or times out."""

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        self.exit_code = exit_code
        super().__init__(message)


class PhaseRouteParseError(Exception):
    """Raised when phase_route stdout cannot be parsed as JSON."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class TicketError(Exception):
    """Internal error raised by TicketSupervisor (e.g. depth_exceeded)."""

    def __init__(self, *, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or f"ticket error: {code}")


__all__ = [
    "InvalidCommand",
    "InvalidRunState",
    "InvalidTicketState",
    "PhaseRouteError",
    "PhaseRouteParseError",
    "RunNotFound",
    "RunStartError",
    "TicketError",
    "TicketNotFound",
]
