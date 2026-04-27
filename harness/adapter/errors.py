"""F18 · Bk-Adapter — adapter-level exceptions (Design §4 Interface Contract Raises column)."""

from __future__ import annotations


class AdapterError(Exception):
    """Base for all adapter-layer failures (PTY init, etc.)."""


class SpawnError(AdapterError):
    """Raised when CLI binary not found on PATH or pty_factory invocation fails."""


class SkillDispatchError(SpawnError):
    """Wave 5 NEW · raised when ``ClaudeCodeAdapter.spawn`` cannot inject the
    leading ``/<next_skill>`` slash command after PTY boot.

    Subclass of :class:`SpawnError` so existing
    ``try: spawn except SpawnError`` paths in the supervisor still catch it
    (FR-055 backward-compat invariant — see Design §Implementation Summary).

    Attributes:
        reason: One of ``"BOOT_TIMEOUT"`` / ``"WRITE_FAILED"`` / ``"MARKER_TIMEOUT"``.
        skill_hint: The slash-skill name we tried to dispatch (audit trail / UI hint).
        elapsed_ms: Time spent in the failing phase (boot wait or marker wait).
    """

    def __init__(
        self,
        reason: str,
        *,
        skill_hint: str = "",
        elapsed_ms: float = 0.0,
    ) -> None:
        super().__init__(
            f"SkillDispatchError reason={reason} skill={skill_hint!r} "
            f"elapsed={elapsed_ms:.0f}ms"
        )
        self.reason = reason
        self.skill_hint = skill_hint
        self.elapsed_ms = elapsed_ms


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
    "SkillDispatchError",
    "InvalidIsolationError",
    "HilPayloadError",
    "HookRegistrationError",
    "EscapeError",
    "WorkdirPrepareError",
]
