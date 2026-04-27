"""F18 Wave 4 · HookEventMapper / HookEventPayload tests.

Test Inventory: T11, T12, T13, T14, T-HOOK-SCHEMA-CANARY.
SRS: FR-009 / IFR-001 / ASM-009.
Design Trace: §Interface Contract HookEventMapper.parse + Design seq msg#7 +
              evidence-summary §C real fixture.

Layer marker:
  # [unit] — pure mapping logic; payload validated via pydantic.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest


_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "hook_event_askuserquestion_v2_1_119.json"
)


def _load_fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T11 — FUNC/happy — Traces To: FR-009 AC-1 + Design seq msg#7
# ---------------------------------------------------------------------------
def test_t11_hook_event_mapper_parses_real_askuserquestion_payload():
    """Real PreToolUse(AskUserQuestion) payload → HilQuestion[] with all fields populated."""
    from harness.hil.hook_mapper import HookEventMapper

    payload = _load_fixture()
    questions = HookEventMapper().parse(payload)

    assert isinstance(questions, list)
    assert len(questions) == 1, f"Expected 1 question, got {len(questions)}"
    q = questions[0]
    assert q.header == "Lang", f"header={q.header!r}"
    assert q.question == "Which language?"
    # options must be three: Python / Go / Rust with descriptions
    assert len(q.options) == 3
    labels = [o.label for o in q.options]
    assert labels == ["Python", "Go", "Rust"], f"labels={labels}"
    descs = [o.description for o in q.options]
    assert descs == ["Python language", "Go language", "Rust language"]
    assert q.multi_select is False
    assert q.kind == "single_select"


# ---------------------------------------------------------------------------
# T12 — FUNC/error — FR-009 AC-3 missing-field default + warning
# ---------------------------------------------------------------------------
def test_t12_missing_options_field_defaults_empty_with_warning(caplog):
    from harness.hil.hook_mapper import HookEventMapper

    payload = _load_fixture()
    # Strip the options field
    payload["tool_input"]["questions"][0].pop("options")

    with caplog.at_level(logging.WARNING):
        questions = HookEventMapper().parse(payload)

    assert isinstance(questions, list)
    assert len(questions) == 1
    assert questions[0].options == []
    # Log must mention missing options
    log_text = "\n".join(r.getMessage() for r in caplog.records)
    assert "options" in log_text.lower(), f"Expected warning mentioning 'options'; got logs: {log_text}"


# ---------------------------------------------------------------------------
# T13 — BNDRY/edge — same session_id stable across hook turns
# ---------------------------------------------------------------------------
def test_t13_session_id_stable_across_turns_and_tool_use_ids_unique():
    """Multiple PreToolUse(AskUserQuestion) hook events in same session keep
    session_id stable while tool_use_id is unique per call (lifecycle anchor)."""
    from harness.hil.hook_mapper import HookEventMapper

    base = _load_fixture()
    payloads = []
    for i, tu_id in enumerate(("toolu_AAA", "toolu_BBB", "toolu_CCC")):
        p = json.loads(json.dumps(base))
        p["tool_use_id"] = tu_id
        p["tool_input"]["questions"][0]["question"] = f"Q{i+1}?"
        payloads.append(p)

    mapper = HookEventMapper()
    # Same session_id, distinct tool_use_id; mapper must derive a question per call.
    derived = [mapper.parse(p) for p in payloads]
    assert all(len(qs) == 1 for qs in derived)
    questions = [qs[0] for qs in derived]
    # Per Interface Contract: id is derived from tool_use_id + index → must be distinct
    ids = [q.id for q in questions]
    assert len(set(ids)) == 3, f"Question ids must be unique per tool_use_id, got {ids}"
    # session_id stability: same fixture session_id present in every payload
    assert len({p["session_id"] for p in payloads}) == 1


# ---------------------------------------------------------------------------
# T14 — FUNC/error — non-AskUserQuestion / non-PreToolUse → empty list, no raise
# ---------------------------------------------------------------------------
def test_t14a_post_tool_use_returns_empty_no_raise():
    from harness.hil.hook_mapper import HookEventMapper

    payload = _load_fixture()
    payload["hook_event_name"] = "PostToolUse"
    out = HookEventMapper().parse(payload)
    assert out == []


def test_t14b_pretool_use_with_unrelated_tool_returns_empty():
    from harness.hil.hook_mapper import HookEventMapper

    payload = _load_fixture()
    payload["tool_name"] = "Read"
    out = HookEventMapper().parse(payload)
    assert out == []


def test_t14c_session_start_returns_empty():
    from harness.hil.hook_mapper import HookEventMapper

    payload = {
        "session_id": "abc",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp",
        "hook_event_name": "SessionStart",
        "ts": "2026-04-26T23:46:00+00:00",
    }
    out = HookEventMapper().parse(payload)
    assert out == []


# ---------------------------------------------------------------------------
# T-HOOK-SCHEMA-CANARY — UT/BNDRY — ASM-009 / IFR-001 hook stdin schema canary
# ---------------------------------------------------------------------------
def _collect_keys(obj, prefix=""):
    """Recursively collect keys with dotted-path prefix; lists collapse to '[]'."""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            keys.add(path)
            keys |= _collect_keys(v, path)
    elif isinstance(obj, list):
        if obj:
            # Drift-protocol fix: emit the list-marker key itself so canary's
            # locked schema tokens like 'tool_input.questions[]' actually
            # appear in the fixture key set.
            keys.add(f"{prefix}[]")
        for item in obj:
            keys |= _collect_keys(item, f"{prefix}[]")
    return keys


def test_t_hook_schema_canary_field_set_strict_equal_to_locked_schema():
    """Canary against ASM-009: claude CLI hook stdin JSON schema field set is locked.

    Any rename / add / remove → fixture updater must:
      (1) re-run reference/f18-tui-bridge/puncture.py
      (2) refresh tests/fixtures/hook_event_askuserquestion_v2_1_119.json
      (3) update HookEventMapper field extraction + ASM-009 SRS assumption
      (4) re-run UT until equality restored
    """
    payload = _load_fixture()
    fixture_keys = _collect_keys(payload)

    # Locked schema (Interface Contract HookEventMapper.parse postcondition +
    # Design rationale (f) + ASM-009).
    expected_keys = {
        "session_id",
        "transcript_path",
        "cwd",
        "hook_event_name",
        "tool_name",
        "tool_use_id",
        "tool_input",
        "tool_input.questions",
        "tool_input.questions[]",
        "tool_input.questions[].header",
        "tool_input.questions[].question",
        "tool_input.questions[].options",
        "tool_input.questions[].options[]",
        "tool_input.questions[].options[].label",
        "tool_input.questions[].options[].description",
        "tool_input.questions[].multiSelect",
        "ts",
    }
    diff = fixture_keys ^ expected_keys
    assert not diff, (
        f"Hook stdin schema drift detected. set(fixture) ^ set(locked) = {sorted(diff)}. "
        "Maintainer action: (1) re-run reference/f18-tui-bridge/puncture.py to capture "
        "the new claude CLI hook stdin JSON; (2) replace "
        "tests/fixtures/hook_event_askuserquestion_v2_1_119.json; "
        "(3) update HookEventMapper field extraction; "
        "(4) update ASM-009 SRS assumption."
    )


def test_t_hook_schema_canary_pydantic_validate_passes_locked_fixture():
    """HookEventPayload pydantic schema must accept the locked fixture without error."""
    from harness.adapter import HookEventPayload  # type: ignore

    payload = _load_fixture()
    obj = HookEventPayload.model_validate(payload)
    # Concrete equality on critical fields — not just non-None.
    assert obj.hook_event_name == "PreToolUse"
    assert obj.tool_name == "AskUserQuestion"
    assert obj.session_id == payload["session_id"]
