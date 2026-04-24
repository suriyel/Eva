"""F18 · Bk-Adapter — Windows PTY back-end (pywinpty).

Only imported on Windows. Implementation skeleton; real-CLI tests run on
POSIX in CI per env-guide §3, so this module only needs to load on
Windows hosts and remain importable elsewhere as a no-op stub.
"""

from __future__ import annotations

from typing import Any


class WindowsPty:
    """Wraps pywinpty's ``PtyProcess`` to satisfy PtyProcessAdapter (skeleton)."""

    def __init__(self, argv: list[str], env: dict[str, str], cwd: str) -> None:
        self._argv = list(argv)
        self._env = dict(env)
        self._cwd = cwd
        self._proc: Any = None
        self.pid: int = -1

    def start(self) -> None:  # pragma: no cover - exercised on Windows hosts only
        try:
            from winpty import PtyProcess  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "pywinpty not installed — required for real PTY spawn on Windows"
            ) from exc
        self._proc = PtyProcess.spawn(self._argv, env=self._env, cwd=self._cwd)
        self.pid = int(getattr(self._proc, "pid", -1))

    def read(self, n: int = 4096) -> bytes:  # pragma: no cover - Windows-only
        if self._proc is None:
            return b""
        data = self._proc.read(n)
        if isinstance(data, str):
            return data.encode("utf-8", errors="replace")
        return bytes(data or b"")

    def write(self, data: bytes) -> int:  # pragma: no cover - Windows-only
        if self._proc is None:
            return 0
        return int(self._proc.write(data))

    def close(self) -> None:  # pragma: no cover - Windows-only
        if self._proc is None:
            return
        try:
            self._proc.close()
        except Exception:
            pass


__all__ = ["WindowsPty"]
