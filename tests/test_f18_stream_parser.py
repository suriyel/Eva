"""F18 · Bk-Adapter — JsonLinesParser & BannerConflictArbiter tests.

Covers Test Inventory: T15, T16, T17, T18, T19, T20.
SRS: FR-009, FR-014. UML: seq msg#5; flow branches in BannerConflictArbiter (3 cases).

Layer marker:
  # [unit] — pure parser logic; no I/O.
"""

from __future__ import annotations

import logging

# F18 imports deferred per-test (TDD Red — modules absent).


# ---------------------------------------------------------------------------
# T15 — FUNC/happy — Traces To: FR-009 · §Design Alignment seq msg#5 · JsonLinesParser.feed
# ---------------------------------------------------------------------------
def test_t15_feed_two_complete_lines_returns_two_events():
    from harness.stream.parser import JsonLinesParser

    chunk = (
        b'{"type":"tool_use","name":"AskUserQuestion","seq":1,"input":{"questions":[]}}\n'
        b'{"type":"text","seq":2,"text":"hi"}\n'
    )
    events = JsonLinesParser().feed(chunk)
    assert len(events) == 2
    # Validate first event is the tool_use kind, not just any object
    kinds = [e.kind for e in events]
    assert "tool_use" in kinds
    assert "text" in kinds
    # Validate text body present (kills "returned a stub event" wrong impl)
    text_evt = next(e for e in events if e.kind == "text")
    assert text_evt.payload.get("text") == "hi"


# ---------------------------------------------------------------------------
# T16 — BNDRY/edge — Traces To: §Boundary Conditions · JsonLinesParser
# ---------------------------------------------------------------------------
def test_t16_feed_handles_split_chunk_across_calls():
    """半行 chunk 必须保留 buffer 直至下一片完整。"""
    from harness.stream.parser import JsonLinesParser

    parser = JsonLinesParser()
    chunk1 = b'{"type":"text","seq":1,'
    chunk2 = b'"text":"hi"}\n'
    out1 = parser.feed(chunk1)
    out2 = parser.feed(chunk2)
    assert out1 == [], "incomplete line must NOT yield events"
    assert len(out2) == 1
    assert out2[0].kind == "text"
    assert out2[0].payload.get("text") == "hi"


# ---------------------------------------------------------------------------
# T17 — FUNC/error — Traces To: ATS Err-D · JsonLinesParser
# ---------------------------------------------------------------------------
def test_t17_feed_skips_invalid_json_and_continues(caplog):
    from harness.stream.parser import JsonLinesParser

    chunk = b'{invalid json\n{"type":"text","seq":3,"text":"ok"}\n'
    parser = JsonLinesParser()
    with caplog.at_level(logging.WARNING):
        events = parser.feed(chunk)
    assert len(events) == 1
    assert events[0].kind == "text"
    assert events[0].payload.get("text") == "ok"
    # Warning emitted for the invalid line (keyword: invalid / json / parse)
    msgs = " ".join(rec.getMessage().lower() for rec in caplog.records)
    assert "invalid" in msgs or "json" in msgs or "parse" in msgs


# ---------------------------------------------------------------------------
# T18 — FUNC/happy — Traces To: FR-014 · §Design Alignment seq msg#7 · BannerConflictArbiter
#       UML flow branch: HIL=YES + Banner=YES → hil_waiting (FR-014 wins)
# ---------------------------------------------------------------------------
def test_t18_arbiter_hil_wins_over_terminate_banner():
    from harness.stream.banner_arbiter import BannerConflictArbiter
    from harness.stream.events import StreamEvent

    events = [
        StreamEvent(kind="text", seq=1, payload={"text": "# 终止"}),
        StreamEvent(
            kind="tool_use",
            seq=2,
            payload={"name": "AskUserQuestion", "input": {"questions": [{"id": "q1"}]}},
        ),
    ]
    verdict = BannerConflictArbiter().arbitrate(events)
    assert verdict.verdict == "hil_waiting", "FR-014: HIL must win even if banner present"


# ---------------------------------------------------------------------------
# T19 — BNDRY/edge — Traces To: FR-014 · BannerConflictArbiter
#       UML flow branch: HIL=NO + Banner=YES → completed
# ---------------------------------------------------------------------------
def test_t19_arbiter_only_banner_yields_completed():
    from harness.stream.banner_arbiter import BannerConflictArbiter
    from harness.stream.events import StreamEvent

    events = [StreamEvent(kind="text", seq=1, payload={"text": "terminated"})]
    verdict = BannerConflictArbiter().arbitrate(events)
    assert verdict.verdict == "completed"


# ---------------------------------------------------------------------------
# T20 — BNDRY/edge — Traces To: FR-014 · BannerConflictArbiter
#       UML flow branch: HIL=YES + Banner=NO → hil_waiting (NOT running)
# ---------------------------------------------------------------------------
def test_t20_arbiter_only_hil_yields_hil_waiting():
    from harness.stream.banner_arbiter import BannerConflictArbiter
    from harness.stream.events import StreamEvent

    events = [
        StreamEvent(
            kind="tool_use",
            seq=1,
            payload={"name": "AskUserQuestion", "input": {"questions": [{"id": "q1"}]}},
        )
    ]
    verdict = BannerConflictArbiter().arbitrate(events)
    assert verdict.verdict == "hil_waiting"
