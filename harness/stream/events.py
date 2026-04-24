"""F18 · Bk-Adapter — StreamEvent pydantic model (Design §4.3.2 + §6.2.4).

Single permissive model rather than a discriminated union — keeps the parser
straightforward and matches the Test Inventory which inspects ``kind`` /
``seq`` / ``payload`` directly.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StreamEventKind = Literal[
    "text",
    "tool_use",
    "tool_result",
    "thinking",
    "error",
    "system",
]


class StreamEvent(BaseModel):
    """One JSON-Lines event from the agent CLI stdout.

    `kind` mirrors `payload["type"]` for ergonomic access in arbiters /
    extractors. `payload` keeps the full original dict (minus 'type') so
    downstream layers can read `name`, `text`, `input`, `message`, ...
    """

    model_config = ConfigDict(extra="forbid")

    kind: StreamEventKind
    seq: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


__all__ = ["StreamEvent", "StreamEventKind"]
