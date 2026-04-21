"""Unit tests for F02 · TicketStateMachine + TransitionError + Ticket pydantic model.

Covers Test Inventory rows B, G, H, I (FR-006 state transitions + FR-007 depth boundary).

[unit] — pure synchronous tests; no I/O, no DB, no filesystem. The module under
test (`harness.domain.state_machine`, `harness.domain.ticket`) is intentionally
not yet implemented — every test must fail during TDD Red with
ImportError / AttributeError / pydantic ValidationError / AssertionError on
the expected behaviour.
Feature ref: feature_2
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Row B — FUNC/happy — FR-006 AC-2: HIL_WAITING → CLASSIFYING legal transition
# ---------------------------------------------------------------------------
def test_hil_waiting_to_classifying_is_silent() -> None:
    """validate_transition(HIL_WAITING, CLASSIFYING) must return silently (no exception).

    FR-006 AC-2 authority: HIL 答完回流到 classifying。A buggy matrix that
    omits this edge would raise TransitionError and fail this test.
    """
    from harness.domain.state_machine import TicketStateMachine
    from harness.domain.ticket import TicketState

    # Must not raise.
    result = TicketStateMachine.validate_transition(
        TicketState.HIL_WAITING, TicketState.CLASSIFYING
    )
    # validate_transition returns None on success; assert explicitly.
    assert result is None

    # Cross-check via legal_next_states: CLASSIFYING must be in the allowed set.
    legal = TicketStateMachine.legal_next_states(TicketState.HIL_WAITING)
    assert (
        TicketState.CLASSIFYING in legal
    ), f"HIL_WAITING must allow CLASSIFYING; got {sorted(s.value for s in legal)}"


# ---------------------------------------------------------------------------
# Row G — FUNC/error — FR-006 AC-1: pending → completed must raise TransitionError
# ---------------------------------------------------------------------------
def test_pending_to_completed_raises_transition_error_with_both_labels() -> None:
    """validate_transition(PENDING, COMPLETED) must raise with both state labels in message."""
    from harness.domain.state_machine import TicketStateMachine, TransitionError
    from harness.domain.ticket import TicketState

    with pytest.raises(TransitionError) as exc_info:
        TicketStateMachine.validate_transition(TicketState.PENDING, TicketState.COMPLETED)

    # Message must contain both source and destination labels (per §IC Raises column).
    msg = str(exc_info.value)
    assert "pending" in msg.lower(), f"message missing 'pending': {msg!r}"
    assert "completed" in msg.lower(), f"message missing 'completed': {msg!r}"

    # Attribute access (§IC Raises: "携带 from_state / to_state 属性")
    assert exc_info.value.from_state == TicketState.PENDING
    assert exc_info.value.to_state == TicketState.COMPLETED


# ---------------------------------------------------------------------------
# Row H — FUNC/error — FR-006: 9 typical illegal pairs all raise TransitionError
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "from_name,to_name",
    [
        ("PENDING", "CLASSIFYING"),
        ("PENDING", "HIL_WAITING"),
        ("RUNNING", "HIL_WAITING"),
        ("COMPLETED", "RUNNING"),
        ("FAILED", "COMPLETED"),
        ("ABORTED", "PENDING"),
        ("RETRYING", "COMPLETED"),
        ("INTERRUPTED", "RUNNING"),
        ("HIL_WAITING", "COMPLETED"),
    ],
)
def test_illegal_transitions_all_raise(from_name: str, to_name: str) -> None:
    """Each of the 9 listed illegal pairs must raise TransitionError (Rule 4 kill switch).

    A buggy implementation that only guards pending→completed passes row G but fails
    multiple rows here — that's the point.
    """
    from harness.domain.state_machine import TicketStateMachine, TransitionError
    from harness.domain.ticket import TicketState

    from_state = TicketState[from_name]
    to_state = TicketState[to_name]
    with pytest.raises(TransitionError):
        TicketStateMachine.validate_transition(from_state, to_state)


# ---------------------------------------------------------------------------
# Row B helper — legal_next_states explicit contract check (Rule 3: high-value)
# ---------------------------------------------------------------------------
def test_legal_next_states_classifying_includes_all_four_verdicts() -> None:
    """CLASSIFYING must legally transition to HIL_WAITING/COMPLETED/FAILED/ABORTED/RETRYING.

    Per §Design rationale "state 转移矩阵（FR-006 权威）":
    classifying → {hil_waiting, completed, failed, aborted, retrying}
    """
    from harness.domain.state_machine import TicketStateMachine
    from harness.domain.ticket import TicketState

    nxt = TicketStateMachine.legal_next_states(TicketState.CLASSIFYING)
    expected = {
        TicketState.HIL_WAITING,
        TicketState.COMPLETED,
        TicketState.FAILED,
        TicketState.ABORTED,
        TicketState.RETRYING,
    }
    assert expected.issubset(nxt), f"classifying next states missing: {expected - set(nxt)}"


def test_terminal_states_have_no_outgoing_user_transitions() -> None:
    """completed / failed / aborted / retrying / interrupted: no outgoing transitions.

    Per §Design rationale: "terminal 状态：completed / failed / aborted / retrying / interrupted
    (不允许再转出)". A buggy matrix that allows e.g. completed→running fails here.
    """
    from harness.domain.state_machine import TicketStateMachine
    from harness.domain.ticket import TicketState

    for term_name in ("COMPLETED", "FAILED", "ABORTED", "RETRYING", "INTERRUPTED"):
        term = TicketState[term_name]
        nxt = TicketStateMachine.legal_next_states(term)
        # Terminal = empty outgoing set (or at most a reflexive no-op, but design says empty).
        assert len(nxt) == 0, (
            f"terminal state {term.value} must have no legal next states; got "
            f"{sorted(s.value for s in nxt)}"
        )


# ---------------------------------------------------------------------------
# Row I — FUNC/error — FR-007 AC-2: depth=3 raises pydantic ValidationError
# ---------------------------------------------------------------------------
def test_ticket_depth_3_raises_validation_error_on_depth_field() -> None:
    """pydantic Field(ge=0, le=2) must reject depth=3 with error localised on 'depth'."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        _build_minimal_ticket(depth=3)

    errors = exc_info.value.errors()
    # At least one error must target the `depth` field specifically (Rule 4: off-by-one detector).
    assert any(
        ("depth",) == tuple(e["loc"]) or "depth" in e["loc"] for e in errors
    ), f"expected ValidationError on depth; got {errors}"


def test_ticket_depth_negative_raises_validation_error() -> None:
    """Boundary: depth=-1 is also rejected (ge=0 check)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _build_minimal_ticket(depth=-1)


# ---------------------------------------------------------------------------
# Cross-reference: TicketState enum values (prevents typos that would break DDL CHECK)
# ---------------------------------------------------------------------------
def test_ticket_state_enum_values_match_design_contract() -> None:
    """All 9 state enum values must equal the DDL CHECK strings from Design §5.3.

    A typo in one enum value would make DDL CHECK fail on save — this test
    locks the canonical strings before any SQL touches them.
    """
    from harness.domain.ticket import TicketState

    expected = {
        "pending",
        "running",
        "classifying",
        "hil_waiting",
        "completed",
        "failed",
        "aborted",
        "retrying",
        "interrupted",
    }
    actual = {s.value for s in TicketState}
    assert (
        actual == expected
    ), f"TicketState mismatch: missing={expected - actual} extra={actual - expected}"


# ---------------------------------------------------------------------------
# Minimal-ticket helper (shared across depth tests).
# ---------------------------------------------------------------------------
def _build_minimal_ticket(*, depth: int):
    """Build a minimally-valid Ticket with the given depth. Depth validation happens
    in pydantic before any other check."""
    from harness.domain.ticket import (
        DispatchSpec,
        ExecutionInfo,
        GitContext,
        HilInfo,
        OutputInfo,
        Ticket,
        TicketState,
    )

    return Ticket(
        id="t-run-001-0001",
        run_id="run-001",
        parent_ticket=None,
        depth=depth,
        tool="claude",
        skill_hint=None,
        state=TicketState.PENDING,
        dispatch=DispatchSpec(
            argv=["claude"],
            env={},
            cwd="/tmp",
            plugin_dir="/tmp/plugins",
            settings_path="/tmp/settings.json",
        ),
        execution=ExecutionInfo(),
        output=OutputInfo(),
        hil=HilInfo(),
        anomaly=None,
        classification=None,
        git=GitContext(),
    )
