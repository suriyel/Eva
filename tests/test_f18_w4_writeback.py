"""F18 Wave 4 · HilWriteback (TUI keys + IAPI-021 path) tests.

Test Inventory: T27, T28 + Wave 4.1 unified Esc-text protocol additions
(T-UNIFIED-RADIO / T-UNIFIED-MULTI-SELECT / T-UNIFIED-MULTI-QUESTION /
T-UNIFIED-FREEFORM / T-BASELINE-COMPAT).
SRS: FR-052 AC-1 / FR-011 AC-4 / FR-053 (unified Esc-text protocol) /
Design seq HilWriteback row.

Layer marker:
  # [unit] — fakes IAPI-021 client + PtyWorker close behavior; no real PTY.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from harness.domain.ticket import HilAnswer, HilOption, HilQuestion


def _make_question(kind: str = "single_select") -> HilQuestion:
    return HilQuestion(
        id="q-1",
        kind=kind,
        header="Lang",
        question="Which language?",
        options=[HilOption(label="Python"), HilOption(label="Go")],
        multi_select=(kind == "multi_select"),
        allow_freeform=False,
    )


def _expected_unified(merged_text: str) -> bytes:
    """Wave 4.1 — unified Esc-text protocol byte sequence."""
    return b"\x1b" + b"\x1b[200~" + merged_text.encode("utf-8") + b"\x1b[201~" + b"\r"


# ---------------------------------------------------------------------------
# T27 — FUNC/happy — FR-052 AC-1 — UI answer submit drives TUI key writeback
#   (Wave 4.1 default = unified Esc-text protocol)
# ---------------------------------------------------------------------------
def test_t27_write_answer_drives_pty_write_via_unified_esc_text() -> None:
    from harness.hil.writeback import HilWriteback

    posted: list[dict] = []

    class FakePtyWriteClient:
        def post(self, ticket_id: str, payload_b64: str) -> int:
            posted.append({"ticket_id": ticket_id, "payload_b64": payload_b64})
            return len(base64.b64decode(payload_b64))

    answered_via_prompt: list[dict] = []
    state_changes: list[str] = []

    class FakeBus:
        def publish_answered_via_prompt(self, *, ticket_id, run_id, merged_text):
            answered_via_prompt.append(
                {"ticket_id": ticket_id, "run_id": run_id, "merged_text": merged_text}
            )

    class FakeTicketRepo:
        def __init__(self) -> None:
            self.state = "hil_waiting"

        def transition(self, ticket_id, new_state):
            self.state = new_state
            state_changes.append(new_state)

    repo = FakeTicketRepo()
    wb = HilWriteback(
        pty_write_client=FakePtyWriteClient(),
        event_bus=FakeBus(),
        ticket_repo=repo,
    )

    answer = HilAnswer(
        question_id="q-1",
        selected_labels=["Python"],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    wb.write_answer(ticket_id="t-1", question=_make_question(), answer=answer)

    # Must have POSTed exactly one IAPI-021 payload
    assert len(posted) == 1, f"posted={posted!r}"
    decoded = base64.b64decode(posted[0]["payload_b64"])
    # Default = unified Esc-text protocol with merged label "Python"
    assert decoded == _expected_unified("Python"), f"got {decoded!r}"

    # State transition hil_waiting → classifying
    assert state_changes == ["classifying"], f"transitions: {state_changes!r}"
    # Bus publish_answered_via_prompt fired with merged_text == label
    assert len(answered_via_prompt) == 1
    assert answered_via_prompt[0]["merged_text"] == "Python"


# ---------------------------------------------------------------------------
# T28 — FUNC/error — FR-011 AC-4 — pty closed: answer preserved + ticket failed
# ---------------------------------------------------------------------------
def test_t28_pty_closed_preserves_answer_and_marks_ticket_failed() -> None:
    from harness.adapter.errors import EscapeError  # noqa: F401  (sanity import)
    from harness.hil.writeback import HilWriteback
    from harness.pty.errors import PtyClosedError

    state_changes: list[str] = []

    class FakePtyWriteClient:
        def post(self, ticket_id, payload_b64):
            raise PtyClosedError("pty closed")

    class FakeBus:
        def publish_answered_via_prompt(self, *a, **kw):
            raise AssertionError(
                "publish_answered_via_prompt must NOT fire on PtyClosedError"
            )

        def publish_answered(self, *a, **kw):
            raise AssertionError(
                "publish_answered must NOT fire on PtyClosedError"
            )

    class FakeTicketRepo:
        def transition(self, ticket_id, new_state):
            state_changes.append(new_state)

    wb = HilWriteback(
        pty_write_client=FakePtyWriteClient(),
        event_bus=FakeBus(),
        ticket_repo=FakeTicketRepo(),
    )

    answer = HilAnswer(
        question_id="q-1",
        selected_labels=["Python"],
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    with pytest.raises(PtyClosedError):
        wb.write_answer(ticket_id="t-1", question=_make_question(), answer=answer)

    # ticket must have transitioned to failed
    assert "failed" in state_changes, f"state_changes={state_changes!r}"
    # answer must be preserved in pending_answers for later retry / forensic
    pending = getattr(wb, "pending_answers", None)
    assert pending is not None, "HilWriteback must expose pending_answers attribute"
    # entry keyed by ticket_id (or a list keyed by ticket_id)
    if isinstance(pending, dict):
        assert "t-1" in pending, f"pending_answers={pending!r}"
        assert answer in (
            pending["t-1"] if isinstance(pending["t-1"], list) else [pending["t-1"]]
        )
    else:
        assert any(getattr(p, "question_id", None) == "q-1" for p in pending)


# ---------------------------------------------------------------------------
# T-UNIFIED-MULTI-SELECT — multi-select label list joined → unified merged_text
# ---------------------------------------------------------------------------
def test_unified_multi_select_merges_labels_with_comma_space() -> None:
    from harness.hil.writeback import HilWriteback

    posted: list[bytes] = []

    class FakePtyWriteClient:
        def post(self, ticket_id, payload_b64):
            posted.append(base64.b64decode(payload_b64))
            return len(posted[-1])

    class FakeBus:
        def __init__(self) -> None:
            self.last_merged: str | None = None

        def publish_answered_via_prompt(self, *, ticket_id, run_id, merged_text):
            self.last_merged = merged_text

    bus = FakeBus()
    question = _make_question(kind="multi_select")
    answer = HilAnswer(
        question_id="q-1",
        selected_labels=["Python", "Go"],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )

    wb = HilWriteback(pty_write_client=FakePtyWriteClient(), event_bus=bus)
    wb.write_answer(ticket_id="t-1", question=question, answer=answer)

    assert posted == [_expected_unified("Python, Go")]
    assert bus.last_merged == "Python, Go"


# ---------------------------------------------------------------------------
# T-UNIFIED-FREEFORM — freeform_text wins over selected_labels
# ---------------------------------------------------------------------------
def test_unified_freeform_text_wins_over_labels() -> None:
    from harness.hil.writeback import HilWriteback

    posted: list[bytes] = []

    class FakePtyWriteClient:
        def post(self, ticket_id, payload_b64):
            posted.append(base64.b64decode(payload_b64))
            return len(posted[-1])

    class FakeBus:
        def publish_answered_via_prompt(self, *, ticket_id, run_id, merged_text):
            pass

    question = _make_question(kind="single_select")
    answer = HilAnswer(
        question_id="q-1",
        selected_labels=["Python"],  # should be IGNORED — freeform wins
        freeform_text="actually I want Rust",
        answered_at=datetime.now(timezone.utc).isoformat(),
    )

    wb = HilWriteback(pty_write_client=FakePtyWriteClient(), event_bus=FakeBus())
    wb.write_answer(ticket_id="t-1", question=question, answer=answer)

    assert posted == [_expected_unified("actually I want Rust")]


# ---------------------------------------------------------------------------
# T-BASELINE-COMPAT — prefer_baseline=True drops back to legacy `<N>\r`
# ---------------------------------------------------------------------------
def test_baseline_compat_radio_path_preserved() -> None:
    from harness.hil.writeback import HilWriteback

    posted: list[bytes] = []

    class FakePtyWriteClient:
        def post(self, ticket_id, payload_b64):
            posted.append(base64.b64decode(payload_b64))
            return len(posted[-1])

    answered: list[HilAnswer] = []

    class FakeBus:
        def publish_answered(self, *, ticket_id, answer):
            answered.append(answer)

    state_changes: list[str] = []

    class FakeRepo:
        def transition(self, ticket_id, new_state):
            state_changes.append(new_state)

    answer = HilAnswer(
        question_id="q-1",
        selected_labels=["Python"],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    wb = HilWriteback(
        pty_write_client=FakePtyWriteClient(),
        event_bus=FakeBus(),
        ticket_repo=FakeRepo(),
        prefer_baseline=True,
    )
    wb.write_answer(ticket_id="t-1", question=_make_question(), answer=answer)

    # Baseline path: <1>\r for the first option (Python).
    assert posted == [b"1\r"], f"got {posted!r}"
    assert state_changes == ["classifying"]
    # Baseline still uses the legacy publish_answered path.
    assert len(answered) == 1
