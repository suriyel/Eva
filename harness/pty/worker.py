"""F18 · Bk-Adapter — PtyWorker (Design §4 + state diagram).

Bridges blocking PTY I/O (in a worker thread) to an asyncio.Queue[bytes].
Per Implementation Summary §6 (2): PTY I/O can NOT use loop.add_reader(fd)
because pywinpty's ConPTY handle is not a POSIX fd — so we always use a
thread, regardless of platform, for cross-platform consistency.

State diagram (Design §4):
   Initialized → Running → Closing → Closed
                  ↘ Crashed → Closed
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from harness.pty.errors import PtyClosedError, PtyError

_log = logging.getLogger(__name__)


class PtyWorker:
    """Thread + asyncio.Queue bridge over a PtyProcessAdapter."""

    def __init__(
        self,
        pty: Any,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        chunk_size: int = 4096,
    ) -> None:
        self._pty = pty
        self._loop = loop
        self._chunk_size = chunk_size
        self._thread: threading.Thread | None = None
        self._closed = False
        self._state = "initialized"
        # asyncio.Queue requires a running loop at creation time — defer until
        # start() so we don't burst on import.
        self.byte_queue: asyncio.Queue[bytes | None] | None = None

    # ------------------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def pid(self) -> int | None:
        return getattr(self._pty, "pid", None)

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._state != "initialized":
            return  # idempotent guard
        # Lazily wire up the queue so we can run unit tests without a loop.
        try:
            if self.byte_queue is None:
                self.byte_queue = asyncio.Queue()
        except RuntimeError:
            # No running loop (synchronous unit test context). Defer queue.
            self.byte_queue = None

        # Start the underlying pty (FakePty in tests records this call).
        starter = getattr(self._pty, "start", None)
        if callable(starter):
            try:
                starter()
            except Exception as exc:  # pragma: no cover - defensive
                raise PtyError(f"pty start failed: {exc}") from exc

        self._state = "running"
        # Reader thread is only useful when there's a real read() method.
        if hasattr(self._pty, "read"):
            t = threading.Thread(target=self._reader_loop, name="PtyWorker", daemon=True)
            self._thread = t
            t.start()

    # ------------------------------------------------------------------
    def write(self, data: bytes) -> None:
        if self._closed or self._state in ("closed", "closing"):
            raise PtyClosedError("PTY already closed")
        try:
            self._pty.write(data)
        except PtyClosedError:
            raise
        except Exception as exc:  # pragma: no cover - underlying pty error → closed
            self._state = "crashed"
            raise PtyClosedError(f"pty write failed: {exc}") from exc

    # ------------------------------------------------------------------
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._state = "closing"
        try:
            close_fn = getattr(self._pty, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception:  # pragma: no cover - best effort cleanup
            pass
        if self._thread is not None and self._thread.is_alive():
            # Reader loop will see closed flag and exit; join briefly.
            self._thread.join(timeout=0.5)
        # Sentinel to wake any consumer awaiting the queue.
        if self.byte_queue is not None and self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self.byte_queue.put_nowait, None)
            except RuntimeError:
                pass
        self._state = "closed"

    # ------------------------------------------------------------------
    def _reader_loop(self) -> None:
        try:
            while not self._closed:
                try:
                    chunk = self._pty.read(self._chunk_size)
                except (EOFError, OSError):
                    break
                if not chunk:
                    break
                if self.byte_queue is not None and self._loop is not None:
                    try:
                        self._loop.call_soon_threadsafe(self.byte_queue.put_nowait, chunk)
                    except RuntimeError:
                        break
        finally:
            if self.byte_queue is not None and self._loop is not None:
                try:
                    self._loop.call_soon_threadsafe(self.byte_queue.put_nowait, None)
                except RuntimeError:
                    pass
            self._state = "closed" if not self._closed else "closed"


__all__ = ["PtyWorker"]
