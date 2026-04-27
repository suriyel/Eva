"""F18 Wave 4 · HilWriteback (TUI keys + IAPI-021 path) tests.

Test Inventory: T27, T28.
SRS: FR-052 AC-1 / FR-011 AC-4 / Design seq HilWriteback row.

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


# ---------------------------------------------------------------------------
# T27 — FUNC/happy — FR-052 AC-1 — UI answer submit drives TUI key writeback
# ---------------------------------------------------------------------------
def test_t27_write_answer_drives_pty_write_via_tui_key_encoder():
    from harness.hil.writeback import HilWriteback

    posted: list[dict] = []

    class FakePtyWriteClient:
        def post(self, ticket_id: str, payload_b64: str) -> int:
            posted.append({"ticket_id": ticket_id, "payload_b64": payload_b64})
            return len(base64.b64decode(payload_b64))

    answered: list[dict] = []
    state_changes: list[str] = []

    class FakeBus:
        def publish_answered(self, ticket_id, answer):
            answered.append({"ticket_id": ticket_id, "answer": answer})

    class FakeTicketRepo:
        def __init__(self):
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
    # selected option index 1 (Python) → b'1\r'
    assert decoded == b"1\r", f"got {decoded!r}"

    # State transition hil_waiting → classifying
    assert state_changes == ["classifying"], f"transitions: {state_changes!r}"
    # Bus publish_answered fired
    assert len(answered) == 1


# ---------------------------------------------------------------------------
# T28 — FUNC/error — FR-011 AC-4 — pty closed: answer preserved + ticket failed
# ---------------------------------------------------------------------------
def test_t28_pty_closed_preserves_answer_and_marks_ticket_failed():
    from harness.adapter.errors import EscapeError  # noqa: F401  (sanity import)
    from harness.hil.writeback import HilWriteback
    from harness.pty.errors import PtyClosedError

    state_changes: list[str] = []

    class FakePtyWriteClient:
        def post(self, ticket_id, payload_b64):
            raise PtyClosedError("pty closed")

    class FakeBus:
        def publish_answered(self, *a, **kw):
            raise AssertionError("publish_answered must NOT fire on PtyClosedError")

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
        assert answer in (pending["t-1"] if isinstance(pending["t-1"], list) else [pending["t-1"]])
    else:
        assert any(getattr(p, "question_id", None) == "q-1" for p in pending)
