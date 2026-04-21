"""Ticket state machine (FR-006) + domain-level exceptions.

Design §Interface Contract (feature #2) specifies:
  - pending      → running
  - running      → classifying
  - classifying  → {hil_waiting, completed, failed, aborted, retrying}
  - hil_waiting  → classifying        (FR-006 AC-2)
  - retrying     → pending            (F09 派生新 ticket；old stays terminal)
  - terminal     = {completed, failed, aborted, retrying, interrupted}
  - interrupted  is only written through ``mark_interrupted`` /
    ``scan_and_mark_interrupted`` — never through ``validate_transition``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from harness.domain.ticket import TicketState


# ---------------------------------------------------------------------------
# Domain exceptions (re-exported from harness.domain package root).
# ---------------------------------------------------------------------------
class TransitionError(Exception):
    """Raised when an illegal ticket state transition is attempted."""

    def __init__(
        self,
        from_state: "TicketState",
        to_state: "TicketState",
        message: str | None = None,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        msg = (
            message
            if message is not None
            else f"illegal transition: {from_state.value} → {to_state.value}"
        )
        super().__init__(msg)


class TicketNotFoundError(Exception):
    """Raised when a DAO lookup by ticket id misses."""

    def __init__(self, ticket_id: str) -> None:
        self.ticket_id = ticket_id
        super().__init__(f"ticket not found: {ticket_id!r}")


class RunNotFoundError(Exception):
    """Raised when a DAO lookup / update by run id misses."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"run not found: {run_id!r}")


# ---------------------------------------------------------------------------
# State machine matrix.
# ---------------------------------------------------------------------------
def _build_matrix() -> dict["TicketState", frozenset["TicketState"]]:
    """Return the authoritative FR-006 transition table.

    Terminal states map to empty frozensets — no user-driven transition may
    leave them (``interrupted`` is produced by the recovery path only).
    """
    from harness.domain.ticket import TicketState as _TS

    return {
        _TS.PENDING: frozenset({_TS.RUNNING}),
        _TS.RUNNING: frozenset({_TS.CLASSIFYING}),
        _TS.CLASSIFYING: frozenset(
            {
                _TS.HIL_WAITING,
                _TS.COMPLETED,
                _TS.FAILED,
                _TS.ABORTED,
                _TS.RETRYING,
            }
        ),
        _TS.HIL_WAITING: frozenset({_TS.CLASSIFYING}),
        # Terminals — no outgoing edge through user path.
        _TS.COMPLETED: frozenset(),
        _TS.FAILED: frozenset(),
        _TS.ABORTED: frozenset(),
        _TS.RETRYING: frozenset(),
        _TS.INTERRUPTED: frozenset(),
    }


class TicketStateMachine:
    """Pure synchronous guard for FR-006 ticket state transitions."""

    @classmethod
    def _matrix(cls) -> dict["TicketState", frozenset["TicketState"]]:
        # Built lazily so the TicketState enum import is resolved.
        cached = getattr(cls, "_MATRIX_CACHE", None)
        if cached is None:
            cached = _build_matrix()
            cls._MATRIX_CACHE = cached  # type: ignore[attr-defined]
        return cached

    @classmethod
    def legal_next_states(cls, state: "TicketState") -> frozenset["TicketState"]:
        """Return the set of states that ``state`` may legally transition to."""
        return cls._matrix().get(state, frozenset())

    @classmethod
    def validate_transition(cls, from_state: "TicketState", to_state: "TicketState") -> None:
        """Raise :class:`TransitionError` if ``from_state → to_state`` is illegal.

        Returns ``None`` on success (silent).
        """
        allowed = cls.legal_next_states(from_state)
        if to_state in allowed:
            return None
        raise TransitionError(from_state, to_state)


# Used by ``TicketRepository.mark_interrupted``: only these source states can
# be rewritten to ``interrupted`` via the recovery path.
INTERRUPTIBLE_SOURCE_STATES: frozenset[str] = frozenset({"running", "classifying", "hil_waiting"})


__all__ = [
    "INTERRUPTIBLE_SOURCE_STATES",
    "RunNotFoundError",
    "TicketNotFoundError",
    "TicketStateMachine",
    "TransitionError",
]
