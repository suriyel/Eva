"""F18 · Bk-Adapter — POSIX PTY back-end (ptyprocess).

Only imported on POSIX platforms; ptyprocess is Unix-only. Real-CLI
integration tests (T29/T30) exercise this; unit tests substitute FakePty.
"""

from __future__ import annotations

import os
from typing import Any


class PosixPty:
    """Wraps ``ptyprocess.PtyProcess`` to satisfy PtyProcessAdapter."""

    def __init__(self, argv: list[str], env: dict[str, str], cwd: str) -> None:
        self._argv = list(argv)
        self._env = dict(env)
        self._cwd = cwd
        self._proc: Any = None
        self.pid: int = -1

    def start(self) -> None:
        # Defer the import so non-POSIX platforms / unit tests without
        # ptyprocess installed do not blow up at module collection time.
        try:
            from ptyprocess import PtyProcess  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - integration-only path
            raise RuntimeError("ptyprocess not installed — required for real PTY spawn") from exc
        self._proc = PtyProcess.spawn(self._argv, env=self._env, cwd=self._cwd)
        self.pid = int(self._proc.pid)

    def read(self, n: int = 4096) -> bytes:
        if self._proc is None:
            return b""
        try:
            data = self._proc.read(n)
        except EOFError:
            return b""
        if isinstance(data, str):
            return data.encode("utf-8", errors="replace")
        return bytes(data)

    def write(self, data: bytes) -> int:
        if self._proc is None:
            return 0
        return int(self._proc.write(data))

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate(force=True)
        except Exception:  # pragma: no cover - best effort
            try:
                os.kill(int(self._proc.pid), 9)
            except Exception:
                pass


__all__ = ["PosixPty"]
