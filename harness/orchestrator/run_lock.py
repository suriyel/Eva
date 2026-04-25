"""F20 · RunLock — single-run-per-workdir mutual exclusion.

Backed by the :mod:`filelock` PyPI package as prescribed by Design §6 (cross-
platform consistent advisory locking on POSIX/Windows). The lock file lives at
``<workdir>/.harness/run.lock``; ``acquire`` opens the file with a 0.5 s
acquisition budget by default and surfaces :class:`RunLockTimeout` when another
process already holds the lock (NFR-016 → HTTP 409).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout


class RunLockTimeout(Exception):
    """Raised when :meth:`RunLock.acquire` exhausts its budget."""


@dataclass
class RunLockHandle:
    """Opaque handle returned by :meth:`RunLock.acquire`."""

    path: Path
    lock: FileLock


class RunLock:
    """File-based mutex on ``<workdir>/.harness/run.lock``."""

    @staticmethod
    async def acquire(workdir: Path, *, timeout: float = 0.5) -> RunLockHandle:
        lock_dir = workdir / ".harness"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / "run.lock"

        # filelock's blocking `.acquire(timeout=...)` is synchronous; offload to
        # the default executor so the orchestrator's event loop is not stalled
        # while another process holds the lock. ``thread_local=False`` is
        # required because acquire runs on a worker thread while release is
        # invoked from the asyncio main thread — the default thread-local
        # bookkeeping would refuse to release a lock acquired in another thread.
        lock = FileLock(str(lock_path), thread_local=False)
        try:
            await asyncio.to_thread(lock.acquire, timeout=max(0.0, timeout))
        except Timeout as exc:
            raise RunLockTimeout(str(lock_path)) from exc
        return RunLockHandle(path=lock_path, lock=lock)

    @staticmethod
    def release(handle: RunLockHandle) -> None:
        try:
            handle.lock.release()
        except Exception:
            # Releasing a non-held lock is benign; never raise out of release().
            pass


__all__ = ["RunLock", "RunLockHandle", "RunLockTimeout"]
