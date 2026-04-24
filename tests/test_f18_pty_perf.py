"""F18 · Bk-Adapter — Performance latency tests (NFR-002).

Covers Test Inventory: T31.

Layer marker:
  # [unit] — uses fake PTY worker; measures pure parser+queue throughput.

Why unit-layer for PERF: the parser and queue dispatch are deterministic in pure
Python; the NFR-002 p95 < 2s claim is dominated by parser latency for 100 events,
not by syscall jitter. End-to-end PTY perf is gated separately in T29/T30.
"""

from __future__ import annotations

import json
import time

# F18 imports deferred per-test (TDD Red — modules absent).


# ---------------------------------------------------------------------------
# T31 — PERF/latency — Traces To: NFR-002 · ATS line 276
# ---------------------------------------------------------------------------
def test_t31_parser_p95_latency_for_100_events_burst():
    """100 event burst → end-to-end (feed → consumer) p95 < 2.0s.

    Wrong-impl killers:
      - quadratic O(N^2) buffer copy → blows past 2s
      - per-event sleep / blocking I/O → blows past 2s
      - skipping events (returning empty) → assertion on event count fails
    """
    from harness.stream.events import StreamEvent
    from harness.stream.parser import JsonLinesParser

    parser = JsonLinesParser()
    events_payload = b"".join(
        json.dumps({"type": "text", "seq": i, "text": f"e{i}"}).encode("utf-8") + b"\n"
        for i in range(100)
    )

    durations = []
    for _ in range(20):  # 20 trials to compute p95
        start = time.perf_counter()
        out = parser.feed(events_payload)
        durations.append(time.perf_counter() - start)
        # reset buffer state for next trial
        parser._reset_for_test() if hasattr(parser, "_reset_for_test") else None
    durations.sort()
    p95 = durations[int(len(durations) * 0.95) - 1]
    assert p95 < 2.0, f"NFR-002 fail: p95 latency {p95:.3f}s for 100 events"
    # Sanity: parser must actually return events (kills "skip everything" wrong impl)
    assert len(out) == 100
    # And events must be StreamEvent instances with valid kind
    assert all(isinstance(e, StreamEvent) for e in out)
