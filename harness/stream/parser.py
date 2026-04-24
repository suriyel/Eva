"""F18 · Bk-Adapter — JsonLinesParser (Design §4 / §6).

Incremental NDJSON parser:
  - feed(chunk: bytes) -> list[StreamEvent]: parse complete lines, retain
    half-line in internal buffer; skip invalid JSON with a structlog warning.
  - events() -> AsyncIterator[StreamEvent]: consume a PtyWorker.byte_queue,
    yield each StreamEvent; on EOF (sentinel None) yield ErrorEvent and stop.

Contract derived from §4 row JsonLinesParser.feed and §6 散文：
  "用 bytearray buffer + split(b'\\n') 增量模式；chunk 末若不以 '\\n' 结尾则
   最后一片进 buffer；空行过滤掉；非法 JSON 行记 structlog warning 并继续 (Err-D)"
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from harness.stream.events import StreamEvent

_log = logging.getLogger(__name__)

# Permissible event kinds (Design §4.3.2 / IFR-001):
#   text / tool_use / tool_result / thinking / error / system
_KNOWN_KINDS: frozenset[str] = frozenset(
    {"text", "tool_use", "tool_result", "thinking", "error", "system"}
)


class JsonLinesParser:
    """Incremental JSON-Lines parser feeding StreamEvent instances."""

    def __init__(self) -> None:
        self._buffer: bytearray = bytearray()

    # ------------------------------------------------------------------
    # Test helper — the perf test calls this between trials to reset state
    # without constructing a fresh parser instance.
    # ------------------------------------------------------------------
    def _reset_for_test(self) -> None:
        self._buffer.clear()

    # ------------------------------------------------------------------
    def feed(self, chunk: bytes) -> list[StreamEvent]:
        """Parse a (possibly partial) chunk of bytes into StreamEvents.

        Behaviour (Design §4 row + §6 散文):
          - Empty chunk → return []
          - Lines split on b"\\n"; trailing partial line goes back into buffer
          - Invalid JSON → warning + skip; do not break stream
          - Empty JSON lines (whitespace only) → ignored
        """
        if not chunk:
            return []
        self._buffer.extend(chunk)
        events: list[StreamEvent] = []
        # Split into complete lines + remainder. If buffer ends with b"\n",
        # the last element is b""; we must preserve buffer state correctly.
        lines = self._buffer.split(b"\n")
        # Last element is what remains after the final \n (or the entire
        # buffer if no \n at all). Always replace buffer with that remainder.
        self._buffer = bytearray(lines[-1])
        for raw in lines[:-1]:
            if not raw.strip():
                continue
            evt = self._parse_line(raw)
            if evt is not None:
                events.append(evt)
        return events

    # ------------------------------------------------------------------
    def _parse_line(self, raw: bytes | bytearray) -> StreamEvent | None:
        try:
            obj: Any = json.loads(bytes(raw).decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _log.warning(
                "JsonLinesParser: invalid JSON line skipped (%s): %r",
                exc,
                bytes(raw[:80]),
            )
            return None
        if not isinstance(obj, dict):
            _log.warning("JsonLinesParser: non-object JSON skipped: %r", obj)
            return None
        kind = obj.pop("type", None)
        if kind not in _KNOWN_KINDS:
            _log.warning("JsonLinesParser: unknown event kind %r — coerced to 'system'", kind)
            kind = "system"
        seq = int(obj.pop("seq", 0)) if isinstance(obj.get("seq", 0), int) else 0
        # `obj` minus type/seq is the payload. Keep type-erased dict.
        return StreamEvent(kind=kind, seq=seq, payload=obj)

    # ------------------------------------------------------------------
    async def events(self, byte_queue: Any) -> AsyncIterator[StreamEvent]:
        """Async-iterate a byte queue, parsing each chunk into events.

        Contract row §4: pty EOF (sentinel None) → yield ErrorEvent then stop.
        """
        while True:
            chunk = await byte_queue.get()
            if chunk is None:
                yield StreamEvent(kind="error", seq=0, payload={"message": "pty_eof"})
                return
            for evt in self.feed(chunk):
                yield evt


__all__ = ["JsonLinesParser"]
