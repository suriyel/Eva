"""F18 · Bk-Adapter — HilWriteback / HilEventBus tests.

Covers Test Inventory: T21, T22, T23, T32.
SRS: FR-011 (AC-1, AC-2), IAPI-009 (audit append).

Layer marker:
  # [unit] — PtyWorker boundary mocked; HIL writeback semantics validated.

UML traces:
  - seq msg#10 / msg#12 (write_answer → write)
  - state diagram: hil_waiting → classifying (T21) / hil_waiting → failed (T22)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

# F18 imports deferred per-test (TDD Red — modules absent).


def _answer(text="x", question_id="q1"):
    # Local import keeps top-of-module deferral consistent.
    from harness.domain.ticket import HilAnswer

    return HilAnswer(
        question_id=question_id,
        selected_labels=[text],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )


class _FakeWorker:
    def __init__(self):
        self.writes = []
        self._fail = None

    def write(self, data: bytes) -> None:
        if self._fail is not None:
            raise self._fail
        self.writes.append(data)


class _FakeAudit:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)


class _FakeTicketRepo:
    def __init__(self, ticket):
        self.ticket = ticket
        self.transitions = []

    def transition(self, ticket_id, to_state):
        self.transitions.append((ticket_id, to_state))


# ---------------------------------------------------------------------------
# T21 — FUNC/happy — Traces To: FR-011 AC-1 · seq msg#10 · state hil_waiting→classifying
# ---------------------------------------------------------------------------
def test_t21_write_answer_pipes_to_pty_and_emits_audit():
    from harness.hil.writeback import HilWriteback

    worker = _FakeWorker()
    audit = _FakeAudit()
    repo = _FakeTicketRepo(ticket=None)
    wb = HilWriteback(worker=worker, audit=audit, ticket_repo=repo, ticket_id="t1")

    ans = _answer(text="yes")
    wb.write_answer(ans)

    # PtyWorker.write was invoked exactly once (kills "no-op" wrong impl)
    assert len(worker.writes) == 1
    assert b"yes" in worker.writes[0], "answer payload must reach PTY stdin"
    # Audit appended hil_answered (kills "missing audit" wrong impl)
    assert len(audit.events) == 1
    assert audit.events[0].event_type == "hil_answered"
    # State transitions to classifying
    assert ("t1", "classifying") in [(tid, st) for tid, st in repo.transitions]


# ---------------------------------------------------------------------------
# T22 — FUNC/error — Traces To: FR-011 AC-2 · §Interface Contract PtyClosedError
#       state hil_waiting→failed; answer preserved
# ---------------------------------------------------------------------------
def test_t22_write_answer_preserves_answer_when_pty_closed():
    from harness.hil.writeback import HilWriteback
    from harness.pty.errors import PtyClosedError

    worker = _FakeWorker()
    worker._fail = PtyClosedError("EOF")
    audit = _FakeAudit()
    repo = _FakeTicketRepo(ticket=None)
    wb = HilWriteback(worker=worker, audit=audit, ticket_repo=repo, ticket_id="t1")

    ans = _answer(text="late")
    # The contract says: ticket → failed; answer kept (FR-011 AC-2)
    # write_answer either raises and the supervisor handles it, OR returns gracefully
    # but EITHER WAY: the answer must be preserved on the writeback's `pending_answers`
    # collection AND the ticket must be marked failed.
    with pytest.raises(PtyClosedError):
        wb.write_answer(ans)

    assert ans in wb.pending_answers, "FR-011 AC-2: answer must be preserved"
    assert ("t1", "failed") in [(tid, st) for tid, st in repo.transitions]


# ---------------------------------------------------------------------------
# T23 — FUNC/error — Traces To: §Interface Contract EscapeError · ATS FR-011 SEC
# ---------------------------------------------------------------------------
def test_t23_write_answer_rejects_control_chars():
    """freeform_text 含 SIGINT (\\x03) → EscapeError；PtyWorker.write 未被调用。"""
    from harness.adapter.errors import EscapeError
    from harness.domain.ticket import HilAnswer
    from harness.hil.writeback import HilWriteback

    worker = _FakeWorker()
    audit = _FakeAudit()
    repo = _FakeTicketRepo(ticket=None)
    wb = HilWriteback(worker=worker, audit=audit, ticket_repo=repo, ticket_id="t1")

    bad = HilAnswer(
        question_id="q1",
        selected_labels=[],
        freeform_text="hello\x03world",  # 0x03 = SIGINT control char
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    with pytest.raises(EscapeError):
        wb.write_answer(bad)
    assert worker.writes == [], "PtyWorker.write must NOT be invoked on escape failure"


# ---------------------------------------------------------------------------
# T32 — INTG/audit — Traces To: IAPI-009 · FR-009 · seq msg#8 / msg#9 (publish_opened)
# ---------------------------------------------------------------------------
def test_t32_event_bus_publish_opened_appends_audit_and_broadcasts():
    """publish_opened → AuditWriter.append called once with hil_captured event."""
    from harness.hil.event_bus import HilEventBus

    audit = _FakeAudit()
    broadcasts = []

    def ws_broadcast(payload):
        broadcasts.append(payload)

    bus = HilEventBus(ws_broadcast=ws_broadcast, audit=audit)

    from harness.domain.ticket import HilOption, HilQuestion

    q = HilQuestion(
        id="q1",
        kind="single_select",
        header="h",
        question="q",
        options=[HilOption(label="x")],
        multi_select=False,
        allow_freeform=False,
    )
    bus.publish_opened(ticket_id="t1", run_id="r1", question=q)

    # Audit invoked exactly once with hil_captured (kills missing-audit wrong impl)
    assert len(audit.events) == 1
    ae = audit.events[0]
    assert ae.event_type == "hil_captured"
    assert ae.ticket_id == "t1"
    assert ae.run_id == "r1"
    # Payload must carry the question (not just empty {})
    assert ae.payload is not None
    assert "questions" in ae.payload or "question" in ae.payload

    # WebSocket broadcast also triggered with the same question id
    assert len(broadcasts) == 1
    assert "q1" in str(broadcasts[0])
