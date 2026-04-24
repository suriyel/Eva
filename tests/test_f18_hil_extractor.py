"""F18 · Bk-Adapter — HilExtractor / HilControlDeriver / parse_hook_line tests.

Covers Test Inventory: T09, T10, T11, T12, T13, T14.
SRS: FR-009, FR-010, IFR-002 SEC BNDRY.

Layer marker:
  # [unit] — pure parsing logic; no I/O.
"""

from __future__ import annotations

import json
import logging

# F18 imports deferred per-test (TDD Red — modules absent).


# ---------------------------------------------------------------------------
# T09 — FUNC/happy — Traces To: FR-009 AC-1 · §Interface Contract extract_hil
# ---------------------------------------------------------------------------
def test_t09_extract_hil_returns_single_select_with_options():
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    event = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "AskUserQuestion",
            "input": {
                "questions": [
                    {
                        "header": "Choose env",
                        "question": "Which environment?",
                        "options": [{"label": "x"}],
                        "multiSelect": False,
                        "allowFreeformInput": False,
                    }
                ]
            },
        },
    )
    qs = HilExtractor().extract(event)
    assert len(qs) == 1
    q = qs[0]
    assert q.kind == "single_select", "single option + no freeform → single_select"
    assert q.header == "Choose env"
    assert q.question == "Which environment?"
    assert len(q.options) == 1
    assert q.options[0].label == "x"
    assert q.id  # auto-generated, not empty


# ---------------------------------------------------------------------------
# T10 — FUNC/error — Traces To: FR-009 AC-2 · §Interface Contract extract_hil
# ---------------------------------------------------------------------------
def test_t10_extract_hil_missing_options_warns_and_fills_defaults(caplog):
    """缺 options 字段：返回 1 个 HilQuestion(options=[], kind=free_text) + warning."""
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    event = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "AskUserQuestion",
            "input": {
                "questions": [
                    {
                        "header": "h",
                        "question": "q",
                        # NO options key
                        "multiSelect": False,
                        "allowFreeformInput": False,
                    }
                ]
            },
        },
    )
    with caplog.at_level(logging.WARNING):
        qs = HilExtractor().extract(event)
    assert len(qs) == 1
    assert qs[0].options == []
    assert qs[0].kind == "free_text", "empty options falls back to free_text"
    # structlog warning is emitted (caplog catches via std logging adapter)
    assert any("option" in rec.getMessage().lower() for rec in caplog.records)


# ---------------------------------------------------------------------------
# T11 — BNDRY/edge — Traces To: §Boundary Conditions · IFR-002 SEC BNDRY
# ---------------------------------------------------------------------------
def test_t11_parse_hook_line_truncates_question_name_over_256_bytes():
    """Question.name 500B → 截断至 256B 字节边界，不崩，附 '…' 后缀。"""
    from harness.adapter.opencode import OpenCodeAdapter

    long_name = "A" * 500
    raw = json.dumps(
        {
            "kind": "hook",
            "channel": "harness-hil",
            "payload": {"name": long_name, "question": "q?"},
        }
    ).encode("utf-8")
    parser = OpenCodeAdapter()
    evt = parser.parse_hook_line(raw)
    assert evt is not None
    assert evt.channel == "harness-hil"
    truncated = evt.payload["name"]
    # Must be truncated; final character is the ellipsis indicator.
    assert truncated.endswith("…")
    assert len(truncated.encode("utf-8")) <= 256 + len("…".encode("utf-8"))
    assert truncated != long_name


# ---------------------------------------------------------------------------
# T12 — BNDRY/edge — Traces To: §Boundary Conditions · FR-010 · HilControlDeriver
# ---------------------------------------------------------------------------
def test_t12_control_deriver_multi_select_when_flag_true():
    from harness.hil.control import HilControlDeriver

    kind = HilControlDeriver().derive(
        {
            "multi_select": True,
            "options": [{"label": "a"}, {"label": "b"}],
            "allow_freeform": False,
        }
    )
    assert kind == "multi_select"


# ---------------------------------------------------------------------------
# T13 — BNDRY/edge — Traces To: §Boundary Conditions · HilControlDeriver
# ---------------------------------------------------------------------------
def test_t13_control_deriver_free_text_when_no_options_and_freeform():
    from harness.hil.control import HilControlDeriver

    kind = HilControlDeriver().derive(
        {"multi_select": False, "options": [], "allow_freeform": True}
    )
    assert kind == "free_text"


# ---------------------------------------------------------------------------
# T14 — BNDRY/edge — Traces To: §Boundary Conditions · HilControlDeriver
# ---------------------------------------------------------------------------
def test_t14_control_deriver_single_select_with_freeform_one_option():
    """1 option + allow_freeform=True → single_select (含 "其他…" 标记)."""
    from harness.hil.control import HilControlDeriver

    kind = HilControlDeriver().derive(
        {"multi_select": False, "options": [{"label": "x"}], "allow_freeform": True}
    )
    assert kind == "single_select"
