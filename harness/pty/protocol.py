"""F18 · Bk-Adapter — PtyProcessAdapter Protocol (Design §4.3.2).

Cross-platform contract over pty subprocess handle. Concrete impls in
posix.py (ptyprocess) / windows.py (pywinpty). PtyWorker depends only on
this protocol → unit tests can substitute a FakePty class trivially.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PtyProcessAdapter(Protocol):
    """Minimal duck-typed contract used by PtyWorker / ClaudeCodeAdapter.spawn."""

    pid: int

    def __init__(self, argv: list[str], env: dict[str, str], cwd: str) -> None: ...

    def start(self) -> None: ...

    def write(self, data: bytes) -> int: ...

    def close(self) -> None: ...


__all__ = ["PtyProcessAdapter"]
