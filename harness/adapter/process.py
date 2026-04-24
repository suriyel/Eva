"""F18 · Bk-Adapter — TicketProcess return value of ToolAdapter.spawn (Design §4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TicketProcess(BaseModel):
    """Spawn result. Includes pty handle so callers can drive read/write/close.

    `worker` and `byte_queue` are excluded from pydantic serialization since
    they hold runtime objects (PtyWorker / asyncio.Queue) — they are passed
    around in-process only.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    ticket_id: str
    pid: int
    pty_handle_id: str
    started_at: str
    # Runtime references (not part of the wire schema):
    worker: Any = Field(default=None, exclude=True, repr=False)
    byte_queue: Any = Field(default=None, exclude=True, repr=False)


__all__ = ["TicketProcess"]
