"""F18 Wave 4 · HookEventToStreamMapper.map kind-derivation matrix.

Test Inventory: T34.
SRS: IAPI-002 / IAPI-001 (TicketStreamEvent envelope) + Design Interface Contract.

Layer marker:
  # [unit] — pure mapping logic.
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


def _payload(hook_event_name: str, tool_name: str | None = None) -> dict:
    p = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    p["hook_event_name"] = hook_event_name
    if tool_name is None:
        p.pop("tool_name", None)
        p.pop("tool_use_id", None)
        p.pop("tool_input", None)
    else:
        p["tool_name"] = tool_name
    return p


# ---------------------------------------------------------------------------
# T34 — FUNC/happy — kind derivation matrix
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "hook_event,tool_name,expected_kind",
    [
        ("SessionStart", None, "system"),
        ("SessionEnd", None, "system"),
        ("PreToolUse", "AskUserQuestion", "tool_use"),
        ("PreToolUse", "Question", "tool_use"),
        ("PreToolUse", "Read", "tool_use"),
        ("PostToolUse", "Read", "tool_result"),
    ],
)
def test_t34_hook_to_stream_kind_matrix(hook_event, tool_name, expected_kind):
    from harness.adapter import HookEventPayload  # type: ignore
    from harness.orchestrator.hook_to_stream import HookEventToStreamMapper

    raw = _payload(hook_event, tool_name)
    payload = HookEventPayload.model_validate(raw)

    mapper = HookEventToStreamMapper()
    event = mapper.map(payload, ticket_id="t-1", seq=42)

    # ticket_id / seq passthrough
    assert getattr(event, "ticket_id", None) == "t-1"
    assert getattr(event, "seq", None) == 42
    assert getattr(event, "kind", None) == expected_kind, (
        f"hook_event={hook_event!r}, tool={tool_name!r} → kind={getattr(event, 'kind', None)!r}, "
        f"expected {expected_kind!r}"
    )
    # payload dict must include original hook_event_name and not be empty
    payload_dict = getattr(event, "payload", None)
    assert isinstance(payload_dict, dict) and payload_dict, "payload dict must be non-empty"
    assert payload_dict.get("hook_event_name") == hook_event
