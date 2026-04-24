"""F18 · Bk-Adapter — ClaudeCodeAdapter (FR-008/015/016, IFR-001).

Implements ToolAdapter for the Claude Code CLI. Strict argv equality (not
subset) per FR-016 design rationale: any future careless edit that adds
``-p`` is caught by T01.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any, Callable

from harness.adapter.errors import (
    InvalidIsolationError,
    SpawnError,
)
from harness.adapter.process import TicketProcess
from harness.adapter.protocol import CapabilityFlags
from harness.domain.ticket import (
    AnomalyInfo,
    DispatchSpec,
    HilQuestion,
    OutputInfo,
)
from harness.hil.extractor import HilExtractor
from harness.pty.worker import PtyWorker
from harness.stream.events import StreamEvent

_log = logging.getLogger(__name__)

# Anomaly classification keywords (Design §4 row detect_anomaly + ATS Err-J).
_ANOMALY_RULES: tuple[tuple[str, str], ...] = (
    ("not authenticated", "skill_error"),
    ("context length exceeded", "context_overflow"),
    ("rate limited", "rate_limit"),
    ("ehostunreach", "network"),
    ("timeout", "timeout"),
    ("sigsegv", "skill_error"),
    ("eof", "skill_error"),
)

# Env whitelist (IFR-001):
_ENV_WHITELIST: tuple[str, ...] = (
    "PATH",
    "PYTHONPATH",
    "SHELL",
    "LANG",
    "USER",
    "LOGNAME",
    "TERM",
    "HOME",
    "CLAUDE_CONFIG_DIR",
)


def _is_under(path: str, root: str) -> bool:
    """True iff *path* lives inside *root* (after pure-path normalisation).

    We avoid resolve() / realpath here so that **non-existent** isolated paths
    in unit tests still pass; the symlink-escape test for OpenCode hooks does
    use real resolve() — see opencode/__init__.py.
    """
    try:
        p = os.path.normpath(os.path.abspath(path))
        r = os.path.normpath(os.path.abspath(root))
    except Exception:
        return False
    if r in p:
        return True
    return PurePath(p).as_posix().startswith(PurePath(r).as_posix() + "/")


def _validate_isolation(spec: DispatchSpec) -> None:
    """Reject argv whose plugin_dir / settings_path escape the isolated workdir.

    Rule (Design §4 row build_argv preconditions + IFR-001 SEC):
      A path is considered isolated if it lives inside ``.harness-workdir/``
      (the convention emitted by ``EnvironmentIsolator.setup_run``). Anything
      under a user home ``.claude/`` is the canonical NFR-009 violation.
    """
    for label, p in (
        ("plugin_dir", spec.plugin_dir),
        ("settings_path", spec.settings_path),
    ):
        norm = os.path.normpath(os.path.abspath(p))
        # Must be under .harness-workdir/ somewhere along the path.
        if ".harness-workdir" + os.sep not in (norm + os.sep):
            raise InvalidIsolationError(
                f"{label}={p!r} not under .harness-workdir/ — "
                "F10 EnvironmentIsolator.setup_run must produce the path (NFR-009)"
            )


class ClaudeCodeAdapter:
    """ToolAdapter implementation for the Claude Code CLI."""

    def __init__(
        self,
        *,
        pty_factory: Callable[..., Any] | None = None,
        resolver: Any = None,
    ) -> None:
        # `pty_factory` is injected in unit tests (FakePty); production code
        # selects PosixPty / WindowsPty by os.name.
        self._pty_factory = pty_factory
        self._resolver = resolver
        self._extractor = HilExtractor()

    # ------------------------------------------------------------------
    def build_argv(self, spec: DispatchSpec) -> list[str]:
        _validate_isolation(spec)
        # FR-016 strict order:
        #   claude --dangerously-skip-permissions
        #          --output-format stream-json --include-partial-messages
        #          --plugin-dir <dir>
        #          --mcp-config <json> --strict-mcp-config        (only if mcp_config)
        #          --settings <json>
        #          --setting-sources user,project
        #          [--model <alias>]
        argv: list[str] = [
            "claude",
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--include-partial-messages",
            "--plugin-dir",
            spec.plugin_dir,
        ]
        if spec.mcp_config is not None:
            argv += ["--mcp-config", spec.mcp_config, "--strict-mcp-config"]
        argv += [
            "--settings",
            spec.settings_path,
            "--setting-sources",
            "user,project",
        ]
        if spec.model is not None:
            argv += ["--model", spec.model]
        # FR-008: -p MUST never appear.
        assert "-p" not in argv
        return argv

    # ------------------------------------------------------------------
    def spawn(self, spec: DispatchSpec) -> TicketProcess:
        argv = self.build_argv(spec)
        if shutil.which(argv[0]) is None:
            raise SpawnError("Claude CLI not found")
        env = self._sanitise_env(spec.env)
        factory = self._pty_factory or self._default_factory()
        try:
            pty = factory(argv, env, spec.cwd)
        except Exception as exc:
            raise SpawnError(f"PTY init failed: {exc}") from exc

        worker = PtyWorker(pty)
        try:
            worker.start()
        except Exception as exc:
            raise SpawnError(f"PtyWorker.start failed: {exc}") from exc

        ticket_id = uuid.uuid4().hex
        pid = int(getattr(pty, "pid", -1))
        return TicketProcess(
            ticket_id=ticket_id,
            pid=pid,
            pty_handle_id=f"pty-{ticket_id}",
            started_at=datetime.now(timezone.utc).isoformat(),
            worker=worker,
            byte_queue=worker.byte_queue,
        )

    # ------------------------------------------------------------------
    def extract_hil(self, event: StreamEvent) -> list[HilQuestion]:
        return self._extractor.extract(event)

    # ------------------------------------------------------------------
    def parse_result(self, events: list[StreamEvent]) -> OutputInfo:
        text_parts: list[str] = []
        session_id: str | None = None
        for evt in events:
            if evt.kind == "text":
                t = evt.payload.get("text")
                if isinstance(t, str):
                    text_parts.append(t)
            elif evt.kind == "system":
                sid = evt.payload.get("session_id") or evt.payload.get("sessionId")
                if isinstance(sid, str):
                    session_id = sid
        return OutputInfo(
            result_text="".join(text_parts) or None,
            stream_log_ref=None,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    def detect_anomaly(self, events: list[StreamEvent]) -> AnomalyInfo | None:
        for evt in events:
            if evt.kind not in ("error", "system"):
                continue
            msg = str(evt.payload.get("message") or evt.payload.get("text") or "")
            lower = msg.lower()
            for needle, cls in _ANOMALY_RULES:
                if needle in lower:
                    return AnomalyInfo(cls=cls, detail=msg, retry_count=0)  # type: ignore[arg-type]
        return None

    # ------------------------------------------------------------------
    def supports(self, flag: CapabilityFlags) -> bool:
        return flag is CapabilityFlags.MCP_STRICT

    # ------------------------------------------------------------------
    @staticmethod
    def _sanitise_env(raw: dict[str, str]) -> dict[str, str]:
        return {k: v for k, v in raw.items() if k in _ENV_WHITELIST}

    @staticmethod
    def _default_factory() -> Callable[..., Any]:
        if os.name == "posix":
            from harness.pty.posix import PosixPty

            return PosixPty
        else:  # pragma: no cover - exercised only on Windows hosts
            from harness.pty.windows import WindowsPty

            return WindowsPty


__all__ = ["ClaudeCodeAdapter"]
