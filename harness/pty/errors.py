"""F18 · Bk-Adapter — pty subpackage exceptions."""

from __future__ import annotations


class PtyError(Exception):
    """Base PTY error (fork / execvp failure)."""


class PtyClosedError(PtyError):
    """Raised when PTY stdin write is attempted after EOF / unexpected child exit.

    FR-011 AC-2: HilWriteback must preserve the answer when this is raised.
    """


__all__ = ["PtyError", "PtyClosedError"]
