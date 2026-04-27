"""F18 Wave 4 · ClaudeCodeAdapter (FR-008/015/016/051, IFR-001).

Implements ``ToolAdapter`` for the Claude Code CLI. Wave-4 contract:

  argv: strict 8-item whitelist (or 10-item with optional --model).
        Banned flags: -p / --print / --output-format /
                      --include-partial-messages /
                      --mcp-config / --strict-mcp-config.

  prepare_workdir: writes the Wave-4 isolation triplet into <paths.cwd>:
        .claude.json (skip dialogs) +
        .claude/settings.json (env + 4 hook entries + flags) +
        .claude/hooks/claude-hook-bridge.py (chmod 0o755)

  map_hook_event: hook stdin payload → HilQuestion[] (delegates to HookEventMapper).
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Any, Callable

from harness.adapter.errors import (
    InvalidIsolationError,
    SpawnError,
    WorkdirPrepareError,
)
from harness.adapter.hook_payload import HookEventPayload
from harness.adapter.process import TicketProcess
from harness.adapter.protocol import CapabilityFlags
from harness.adapter.workdir_artifacts import (
    HookBridgeScriptDeployer,
    SettingsArtifactWriter,
    SkipDialogsArtifactWriter,
)
from harness.domain.ticket import (
    AnomalyInfo,
    DispatchSpec,
    HilQuestion,
    OutputInfo,
)
from harness.env.models import IsolatedPaths
from harness.hil.hook_mapper import HookEventMapper
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

# Env whitelist (IFR-001 SEC):
# COLUMNS / LINES added 2026-04-27 per Wave 4 Failure Addendum Fix A3 — required
# by reference/f18-tui-bridge/puncture.py so the TUI sizes its viewport
# correctly (otherwise claude renders blank screens that look like the wizard
# dialog never bypassed).
# *_PROXY added 2026-04-27 per Wave 4 Failure Addendum Fix A6 — claude TUI
# spawned in restricted networks needs the host's HTTP/HTTPS proxy settings
# to reach api.anthropic.com. Proxy URL is not a secret (NFR-008 only covers
# LLM API keys, which still live in keyring / settings.json env block).
_ENV_WHITELIST: tuple[str, ...] = (
    "PATH",
    "PYTHONPATH",
    "SHELL",
    "LANG",
    "USER",
    "LOGNAME",
    "TERM",
    "HOME",
    "COLUMNS",
    "LINES",
    "HARNESS_BASE_URL",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "all_proxy",
)


def _is_under_workdir(path: str) -> bool:
    """True iff *path* is under a ``.harness-workdir/`` segment."""
    try:
        norm = os.path.normpath(os.path.abspath(path))
    except Exception:
        return False
    sep = os.sep
    return f"{sep}.harness-workdir{sep}" in (norm + sep)


def _validate_isolation(spec: DispatchSpec) -> None:
    """Reject argv whose plugin_dir / settings_path escape the isolated workdir.

    The convention: each path must live under ``.harness-workdir/`` somewhere
    along the absolute path. This is the canonical NFR-009 violation guard.
    """
    for label, p in (
        ("plugin_dir", spec.plugin_dir),
        ("settings_path", spec.settings_path),
    ):
        if not _is_under_workdir(p):
            raise InvalidIsolationError(
                f"{label}={p!r} not under .harness-workdir/ — "
                "F10 EnvironmentIsolator.setup_run must produce the path (NFR-009)"
            )


class ClaudeCodeAdapter:
    """ToolAdapter implementation for the Claude Code CLI (Wave 4)."""

    def __init__(
        self,
        *,
        pty_factory: Callable[..., Any] | None = None,
        resolver: Any = None,
        bridge_source: Path | None = None,
    ) -> None:
        # `pty_factory` is injected in unit tests (FakePty); production code
        # selects PosixPty / WindowsPty by os.name.
        self._pty_factory = pty_factory
        self._resolver = resolver
        self._mapper = HookEventMapper()
        self._skip_dialogs_writer = SkipDialogsArtifactWriter()
        self._settings_writer = SettingsArtifactWriter()
        self._bridge_deployer = HookBridgeScriptDeployer()
        self._bridge_source = bridge_source or _default_bridge_source()

    # ------------------------------------------------------------------
    def build_argv(self, spec: DispatchSpec) -> list[str]:
        """Build the SRS FR-016 strict argv whitelist (8 or 10 items)."""
        _validate_isolation(spec)
        argv: list[str] = [
            "claude",
            "--dangerously-skip-permissions",
            "--plugin-dir",
            spec.plugin_dir,
            "--settings",
            spec.settings_path,
        ]
        if spec.model is not None:
            argv += ["--model", spec.model]
        argv += ["--setting-sources", "project"]
        # FR-008/016: banned flags must never appear.
        assert "-p" not in argv
        assert "--print" not in argv
        assert "--output-format" not in argv
        assert "--include-partial-messages" not in argv
        assert "--mcp-config" not in argv
        assert "--strict-mcp-config" not in argv
        return argv

    # ------------------------------------------------------------------
    def prepare_workdir(
        self, spec: DispatchSpec, paths: IsolatedPaths
    ) -> IsolatedPaths:
        """Idempotently write the Wave-4 isolation triplet under ``paths.cwd``.

        See env-guide §4.5 + FR-051 + Design Implementation Summary §3.
        """
        cwd = Path(paths.cwd)
        # CheckEscape — paths.cwd must live under .harness-workdir/.
        if not _is_under_workdir(str(cwd)):
            raise InvalidIsolationError(
                f"paths.cwd={paths.cwd!r} escapes user-scope; "
                "must be under .harness-workdir/ (NFR-009)"
            )

        # DeployBridge precondition — HARNESS_BASE_URL must be available.
        harness_base_url = (
            spec.env.get("HARNESS_BASE_URL")
            or os.environ.get("HARNESS_BASE_URL", "")
        ).strip()
        if not harness_base_url:
            raise WorkdirPrepareError(
                "HARNESS_BASE_URL must be set in spec.env or os.environ for "
                "Wave-4 workdir-scoped hook bridge"
            )

        # Provider-routing env (ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL etc.)
        # is injected via settings.json `env` block — claude TUI reads it
        # directly without going through the OS env whitelist (puncture.py
        # validated 2026-04-26). Convention: any spec.env key with prefix
        # ``ANTHROPIC_`` or ``API_`` is forwarded into settings.json.
        provider_env: dict[str, str] = {}
        for key, value in spec.env.items():
            if key in _ENV_WHITELIST:
                continue
            if key.startswith("ANTHROPIC_") or key.startswith("API_") or key in (
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
            ):
                provider_env[key] = value

        try:
            self._skip_dialogs_writer.write(cwd)
            self._settings_writer.write(
                cwd,
                harness_base_url=harness_base_url,
                model=spec.model,
                extra_env=provider_env or None,
            )
            self._bridge_deployer.deploy(cwd, source=self._bridge_source)
        except WorkdirPrepareError:
            raise
        except OSError as exc:
            raise WorkdirPrepareError(f"prepare_workdir failed: {exc}") from exc
        return paths

    # ------------------------------------------------------------------
    def spawn(
        self, spec: DispatchSpec, paths: IsolatedPaths | None = None
    ) -> TicketProcess:
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
    def map_hook_event(self, payload: HookEventPayload) -> list[HilQuestion]:
        """Map a hook stdin payload (or raw dict) to HilQuestion[]."""
        return self._mapper.parse(payload)

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
        # Wave 4: HOOKS=True; mcp_config is degraded so MCP_STRICT=False.
        if flag is CapabilityFlags.HOOKS:
            return True
        if flag is CapabilityFlags.MCP_STRICT:
            return False
        return False

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


def _default_bridge_source() -> Path:
    """Locate the repo-root scripts/claude-hook-bridge.py."""
    here = Path(__file__).resolve()
    # harness/adapter/claude.py → repo root is parents[2]
    return here.parents[2] / "scripts" / "claude-hook-bridge.py"


__all__ = ["ClaudeCodeAdapter"]
