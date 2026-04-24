"""F18 · Bk-Adapter — pty subpackage.

Cross-platform PtyProcessAdapter Protocol + PtyWorker (threading + asyncio
bridge). Concrete platform back-ends in posix.py / windows.py.
"""

from __future__ import annotations

from harness.pty.errors import PtyClosedError, PtyError
from harness.pty.protocol import PtyProcessAdapter
from harness.pty.worker import PtyWorker

__all__ = [
    "PtyClosedError",
    "PtyError",
    "PtyProcessAdapter",
    "PtyWorker",
]
