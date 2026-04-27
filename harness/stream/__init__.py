"""F18 Wave 4 · stream subpackage (StreamEvent envelope only).

Wave 4 physically removed the stdout-byte parser (legacy NDJSON event parser)
and banner-arbiter; stream events are now produced by
``harness.orchestrator.hook_to_stream.HookEventToStreamMapper`` from hook
stdin payloads (IAPI-020 → /api/hook/event).
"""

from __future__ import annotations

from harness.stream.events import StreamEvent, StreamEventKind

__all__ = ["StreamEvent", "StreamEventKind"]
