"""F18 Wave 4 · FR-014 replacement logic — SessionEnd queue + tool_use_id tracking.

Test Inventory: T32.
SRS: FR-014 [DEPRECATED] new AC + Design rationale (e).

Layer marker:
  # [unit] — pure logic; no PTY / no real CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "hook_event_askuserquestion_v2_1_119.json"
)


# ---------------------------------------------------------------------------
# T32 — FUNC/happy — SessionEnd handler reads tool_use_id_queue to detect
#                    unanswered HIL → ticket state hil_waiting (not completed)
# ---------------------------------------------------------------------------
def test_t32_session_end_with_unanswered_hil_keeps_ticket_in_hil_waiting():
    from harness.adapter import HookEventPayload  # type: ignore
    from harness.hil.event_bus import HilEventBus
    from harness.hil.hook_mapper import HookEventMapper

    base = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))

    # Step 1: PreToolUse(AskUserQuestion) fires — HookEventMapper enqueues tool_use_id
    mapper = HookEventMapper()
    bus = HilEventBus()
    # tool_use_id_queue is a Wave 4 [NEW] instance attribute on HilEventBus
    assert hasattr(bus, "tool_use_id_queue"), "HilEventBus must expose tool_use_id_queue"

    pretool = HookEventPayload.model_validate(base)
    questions = mapper.parse(pretool.model_dump())
    # Mapper must record tool_use_id into bus queue (per Interface Contract HookEventMapper.parse postcondition)
    mapper.record_pending(bus, pretool, questions)
    assert base["tool_use_id"] in list(bus.tool_use_id_queue), (
        f"tool_use_id should be enqueued; queue={list(bus.tool_use_id_queue)!r}"
    )

    # Step 2: SessionEnd fires WITHOUT user answering → unanswered tool_use_id remains
    end_payload = {
        "session_id": base["session_id"],
        "transcript_path": base["transcript_path"],
        "cwd": base["cwd"],
        "hook_event_name": "SessionEnd",
        "ts": "2026-04-26T23:50:00+00:00",
    }
    end_obj = HookEventPayload.model_validate(end_payload)

    # The orchestrator-level handler must check whether tool_use_id_queue is
    # non-empty and keep ticket state hil_waiting (not completed).
    from harness.orchestrator.hook_to_stream import resolve_session_end_state  # type: ignore

    new_state = resolve_session_end_state(end_obj, bus, current_state="running")
    assert new_state == "hil_waiting", (
        f"SessionEnd with unanswered HIL must yield hil_waiting; got {new_state!r}"
    )

    # Negative control: when queue is drained → SessionEnd transitions to completed
    bus.tool_use_id_queue.clear()
    new_state2 = resolve_session_end_state(end_obj, bus, current_state="running")
    assert new_state2 == "completed", (
        f"SessionEnd with empty queue must yield completed; got {new_state2!r}"
    )
