"""F18 · Bk-Adapter — adapter-level exceptions (Design §4 Interface Contract Raises column)."""

from __future__ import annotations


class AdapterError(Exception):
    """Base for all adapter-layer failures (PTY init, etc.)."""


class SpawnError(AdapterError):
    """Raised when CLI binary not found on PATH or pty_factory invocation fails."""


class InvalidIsolationError(AdapterError):
    """Raised when plugin_dir / settings_path / hooks path is not under the
    isolated workdir (.harness-workdir/<run>/)."""


class HilPayloadError(AdapterError):
    """Raised when AskUserQuestion / Question payload schema is malformed."""


class HookRegistrationError(AdapterError):
    """Raised when OpenCode version is too old to support hooks (FR-012 AC-2)."""


class EscapeError(AdapterError):
    """Raised by HilWriteback when freeform answer contains forbidden control chars."""


class WorkdirPrepareError(AdapterError):
    """Raised when ToolAdapter.prepare_workdir mkdir/write/copy fails (FR-051)."""


__all__ = [
    "AdapterError",
    "SpawnError",
    "InvalidIsolationError",
    "HilPayloadError",
    "HookRegistrationError",
    "EscapeError",
    "WorkdirPrepareError",
]
