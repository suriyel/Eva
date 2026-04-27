"""F18 Wave 4.1 · unified Esc-text protocol audit chain — bus + multi-round tests.

Test Inventory:
  - T-STOP-AUDIT             : Stop hook → mapper produces TicketStreamEvent
                                kind="turn_complete" (verifies the new event type
                                survives the full router → mapper path).
  - T-USER-PROMPT-SUBMIT-AUDIT: UserPromptSubmit hook → kind="user_prompt_submit"
                                AND HilEventBus.publish_answered_via_prompt
                                appends a hil_answered audit with the merged text.
  - T-MULTI-ROUND            : 3 sequential HIL rounds via HilWriteback all
                                land merged_text → unified Esc-text bytes; each
                                round produces a new audit hil_answered marker.

SRS: FR-009 / FR-011 / FR-053 (Wave 4.1 default = unified Esc-text).

Layer markers:
  # [unit] — uses fakes for audit + ws broadcast + pty client.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone


def _make_question():
    from harness.domain.ticket import HilOption, HilQuestion

    return HilQuestion(
        id="q-1",
        kind="single_select",
        header="Lang",
        question="Which language?",
        options=[HilOption(label="Python"), HilOption(label="Go")],
        multi_select=False,
        allow_freeform=False,
    )


def _expected_unified(text: str) -> bytes:
    return b"\x1b" + b"\x1b[200~" + text.encode("utf-8") + b"\x1b[201~" + b"\r"


# ---------------------------------------------------------------------------
# T-STOP-AUDIT
# ---------------------------------------------------------------------------
def test_stop_hook_event_maps_to_turn_complete_kind() -> None:
    """Stop hook → TicketStreamEvent.kind == "turn_complete".

    The new audit chain (unified Esc-text protocol) terminates each user turn
    with a Stop hook. The mapper emits a stream event so consumers can detect
    turn boundaries without parsing stdout.
    """
    from harness.adapter import HookEventPayload
    from harness.orchestrator.hook_to_stream import HookEventToStreamMapper

    payload = HookEventPayload.model_validate(
        {
            "session_id": "sess-1",
            "transcript_path": "/tmp/x.jsonl",
            "cwd": "/tmp",
            "hook_event_name": "Stop",
            "ts": "2026-04-27T00:00:00+00:00",
        }
    )
    mapper = HookEventToStreamMapper()
    event = mapper.map(payload, ticket_id="t-1", seq=10)

    assert event.kind == "turn_complete"
    assert event.ticket_id == "t-1"
    assert event.seq == 10
    assert event.payload["hook_event_name"] == "Stop"


# ---------------------------------------------------------------------------
# T-USER-PROMPT-SUBMIT-AUDIT (mapper side)
# ---------------------------------------------------------------------------
def test_user_prompt_submit_hook_maps_to_user_prompt_submit_kind() -> None:
    """UserPromptSubmit hook → TicketStreamEvent.kind == "user_prompt_submit"."""
    from harness.adapter import HookEventPayload
    from harness.orchestrator.hook_to_stream import HookEventToStreamMapper

    payload = HookEventPayload.model_validate(
        {
            "session_id": "sess-1",
            "transcript_path": "/tmp/x.jsonl",
            "cwd": "/tmp",
            "hook_event_name": "UserPromptSubmit",
            "ts": "2026-04-27T00:00:01+00:00",
        }
    )
    mapper = HookEventToStreamMapper()
    event = mapper.map(payload, ticket_id="t-1", seq=11)

    assert event.kind == "user_prompt_submit"


# ---------------------------------------------------------------------------
# T-USER-PROMPT-SUBMIT-AUDIT (event_bus side)
# ---------------------------------------------------------------------------
def test_publish_answered_via_prompt_writes_hil_answered_with_merged_text() -> None:
    """HilEventBus.publish_answered_via_prompt should append a ``hil_answered``
    AuditEvent carrying the merged_text in payload.answer.value.

    This is the audit-side counterpart of the unified Esc-text protocol —
    it replaces the legacy ``publish_answered(answer=HilAnswer(...))`` call
    chain that fired on PostToolUse(AskUserQuestion).
    """
    from harness.hil.event_bus import HilEventBus

    captured = []

    class FakeAudit:
        def append(self, event):
            captured.append(event)

    ws_events = []

    def ws_publish(payload):
        ws_events.append(payload)

    bus = HilEventBus(ws_broadcast=ws_publish, audit=FakeAudit())
    bus.publish_answered_via_prompt(
        ticket_id="t-1",
        run_id="run-1",
        merged_text="Python, Go",
    )

    assert len(captured) == 1
    evt = captured[0]
    assert evt.event_type == "hil_answered"
    assert evt.ticket_id == "t-1"
    assert evt.run_id == "run-1"
    assert evt.payload["answer"]["value"] == "Python, Go"
    assert evt.payload["answer"]["channel"] == "unified_esc_text"

    assert len(ws_events) == 1
    assert ws_events[0]["answer"]["value"] == "Python, Go"


# ---------------------------------------------------------------------------
# T-MULTI-ROUND — 3 sequential HIL rounds via HilWriteback
# ---------------------------------------------------------------------------
def test_multi_round_three_unified_answers_all_succeed() -> None:
    """Drive HilWriteback through 3 sequential answers — each becomes a
    separate Esc-text payload and a separate hil_answered audit event.

    This stresses the cross-turn behaviour of the unified Esc-text channel.
    """
    from harness.domain.ticket import HilAnswer
    from harness.hil.event_bus import HilEventBus
    from harness.hil.writeback import HilWriteback

    posted: list[bytes] = []

    class FakePtyWriteClient:
        def post(self, ticket_id, payload_b64):
            posted.append(base64.b64decode(payload_b64))
            return len(posted[-1])

    captured = []

    class FakeAudit:
        def append(self, event):
            captured.append(event)

    state_changes = []

    class FakeRepo:
        def transition(self, ticket_id, new_state):
            state_changes.append(new_state)

    bus = HilEventBus(audit=FakeAudit())
    wb = HilWriteback(
        pty_write_client=FakePtyWriteClient(),
        event_bus=bus,
        ticket_repo=FakeRepo(),
    )

    rounds = [
        ("Python",),
        ("Python", "Go"),
        ("Rust",),
    ]
    expected_merged = ["Python", "Python, Go", "Rust"]

    for i, labels in enumerate(rounds):
        answer = HilAnswer(
            question_id=f"q-{i}",
            selected_labels=list(labels),
            freeform_text=None,
            answered_at=datetime.now(timezone.utc).isoformat(),
        )
        wb.write_answer(
            ticket_id="t-1", question=_make_question(), answer=answer
        )

    # Each round produced a distinct unified Esc-text payload.
    assert posted == [_expected_unified(t) for t in expected_merged]
    # Each round transitioned ticket → classifying.
    assert state_changes == ["classifying"] * 3
    # Each round wrote a hil_answered audit with the matching merged_text.
    answered_events = [e for e in captured if e.event_type == "hil_answered"]
    assert len(answered_events) == 3
    for evt, exp_text in zip(answered_events, expected_merged):
        assert evt.payload["answer"]["value"] == exp_text
        assert evt.payload["answer"]["channel"] == "unified_esc_text"
