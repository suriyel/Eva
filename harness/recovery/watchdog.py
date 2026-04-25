"""F20 · Watchdog — SIGTERM / SIGKILL escalation per ticket.

Design §IC + Boundary table:
    * arm(ticket_id, pid, timeout_s, is_alive=lambda) — schedules an asyncio
      task that fires SIGTERM after ``timeout_s`` then SIGKILL after
      ``sigkill_grace_s`` if the process is still alive
    * disarm(ticket_id) — cancels the pending task

``is_alive`` is injected by the supervisor so unit tests can simulate hung
processes without spawning real children. The signal calls go through
``os.kill`` so test code can ``patch('harness.recovery.watchdog.os.kill')``.
"""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Callable


class Watchdog:
    """Per-ticket SIGTERM/SIGKILL escalator."""

    def __init__(self, *, sigkill_grace_s: float = 5.0) -> None:
        self._grace = sigkill_grace_s
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def arm(
        self,
        *,
        ticket_id: str,
        pid: int,
        timeout_s: float,
        is_alive: Callable[[int], bool] | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError(f"timeout_s must be > 0; got {timeout_s!r}")

        async def _runner() -> None:
            try:
                await asyncio.sleep(timeout_s)
            except asyncio.CancelledError:
                return

            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

            # Grace period for SIGTERM
            try:
                await asyncio.sleep(self._grace)
            except asyncio.CancelledError:
                return

            alive = True if is_alive is None else bool(is_alive(pid))
            if alive:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        task = loop.create_task(_runner())
        self._tasks[ticket_id] = task

    def disarm(self, *, ticket_id: str) -> None:
        task = self._tasks.pop(ticket_id, None)
        if task is not None and not task.done():
            task.cancel()


__all__ = ["Watchdog"]
