"""F18 · Bk-Adapter — OpenCode adapter (FR-012/017, IFR-002).

Submodule layout (per Design §6 散文):
  - this file (__init__.py): OpenCodeAdapter class, owning HookConfigWriter /
    HookQuestionParser / McpDegradation / VersionCheck instances from .hooks
  - hooks.py: the four helper classes
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.adapter.errors import (
    HookRegistrationError,
    InvalidIsolationError,
    SpawnError,
)
from harness.adapter.opencode.hooks import (
    HookConfigWriter,
    HookEvent,
    HookQuestionParser,
    McpDegradation,
    VersionCheck,
)
from harness.adapter.process import TicketProcess
from harness.adapter.protocol import CapabilityFlags
from harness.domain.ticket import (
    AnomalyInfo,
    DispatchSpec,
    HilQuestion,
    OutputInfo,
)
from harness.env.models import IsolatedPaths
from harness.hil.extractor import HilExtractor
from harness.pty.worker import PtyWorker
from harness.stream.events import StreamEvent

_log = logging.getLogger(__name__)

_MIN_HOOKS_VERSION = (0, 3, 0)
_ENV_WHITELIST: tuple[str, ...] = (
    "PATH",
    "PYTHONPATH",
    "SHELL",
    "LANG",
    "USER",
    "LOGNAME",
    "TERM",
    "HOME",
)


def _parse_version(s: str) -> tuple[int, int, int]:
    parts = s.strip().lstrip("v").split(".")
    nums = []
    for p in parts[:3]:
        try:
            nums.append(int("".join(c for c in p if c.isdigit()) or "0"))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


class OpenCodeAdapter:
    """ToolAdapter implementation for the OpenCode CLI."""

    def __init__(
        self,
        *,
        pty_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._pty_factory = pty_factory
        self._extractor = HilExtractor()
        # Public attribute (T05 reads adapter.mcp_degrader.toast_pushed)
        self.mcp_degrader = McpDegradation()
        self.hook_writer = HookConfigWriter()
        self.hook_parser = HookQuestionParser()

    # ------------------------------------------------------------------
    def build_argv(self, spec: DispatchSpec) -> list[str]:
        argv: list[str] = ["opencode"]
        # Decision branch 1 (flowchart in Design §6): mcp_config present?
        if spec.mcp_config is not None:
            self.mcp_degrader.push_toast("OpenCode MCP 延后 v1.1 — 已忽略 --mcp-config flag")
            # NB: argv intentionally drops both --mcp-config and --strict-mcp-config
        # Decision branch 2: model present?
        if spec.model is not None:
            argv += ["--model", spec.model]
        # Decision branch 3: agent present (skill_hint maps to --agent)?
        agent = getattr(spec, "agent", None)
        if agent is not None:
            argv += ["--agent", agent]
        return argv

    # ------------------------------------------------------------------
    def spawn(self, spec: DispatchSpec) -> TicketProcess:
        argv = self.build_argv(spec)
        if shutil.which(argv[0]) is None:
            raise SpawnError("OpenCode CLI not found")

        # Hook version gate — FR-012 AC-2: too-old OpenCode → upgrade prompt.
        version = VersionCheck.current_version()
        if _parse_version(version) < _MIN_HOOKS_VERSION:
            raise HookRegistrationError(
                f"OpenCode version {version} too old — please upgrade to "
                f">= {'.'.join(str(n) for n in _MIN_HOOKS_VERSION)}"
            )

        env = {k: v for k, v in spec.env.items() if k in _ENV_WHITELIST}
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
        return TicketProcess(
            ticket_id=ticket_id,
            pid=int(getattr(pty, "pid", -1)),
            pty_handle_id=f"pty-{ticket_id}",
            started_at=datetime.now(timezone.utc).isoformat(),
            worker=worker,
            byte_queue=worker.byte_queue,
        )

    # ------------------------------------------------------------------
    def ensure_hooks(self, paths: IsolatedPaths) -> str:
        """Write hooks.json under <paths.cwd>/.opencode/ (mode 0o600).

        Path traversal guard: resolve() and assert is_relative_to(cwd).
        """
        if not paths.cwd:
            raise InvalidIsolationError("paths.cwd must not be empty")
        cwd = Path(paths.cwd).resolve()
        opencode_dir = Path(paths.cwd) / ".opencode"

        # Path traversal guard — symlink_to(/etc) elsewhere triggers this.
        try:
            resolved_dir = opencode_dir.resolve()
        except (OSError, RuntimeError) as exc:
            raise InvalidIsolationError(f"failed to resolve hooks dir: {exc}") from exc
        if not _path_is_under(resolved_dir, cwd):
            raise InvalidIsolationError(f".opencode dir {resolved_dir} escapes isolated cwd {cwd}")

        hooks_path = opencode_dir / "hooks.json"
        try:
            self.hook_writer.write(hooks_path)
        except (OSError, ValueError) as exc:
            raise HookRegistrationError(f"hooks.json write failed: {exc}") from exc
        # POSIX: tighten perms to 0o600.
        if os.name == "posix":
            os.chmod(hooks_path, 0o600)
        return str(hooks_path)

    # ------------------------------------------------------------------
    def parse_hook_line(self, raw: bytes) -> HookEvent | None:
        return self.hook_parser.parse(raw)

    # ------------------------------------------------------------------
    def extract_hil(self, event: StreamEvent) -> list[HilQuestion]:
        return self._extractor.extract(event)

    def parse_result(self, events: list[StreamEvent]) -> OutputInfo:
        texts = []
        for e in events:
            if e.kind == "text":
                t = e.payload.get("text")
                if isinstance(t, str):
                    texts.append(t)
        return OutputInfo(result_text="".join(texts) or None)

    def detect_anomaly(self, events: list[StreamEvent]) -> AnomalyInfo | None:
        for evt in events:
            if evt.kind != "error":
                continue
            msg = str(evt.payload.get("message") or "")
            lower = msg.lower()
            if "not authenticated" in lower:
                return AnomalyInfo(cls="skill_error", detail=msg)
            if "context" in lower and "exceeded" in lower:
                return AnomalyInfo(cls="context_overflow", detail=msg)
            if "rate" in lower:
                return AnomalyInfo(cls="rate_limit", detail=msg)
        return None

    def supports(self, flag: CapabilityFlags) -> bool:
        return flag is CapabilityFlags.HOOKS

    # ------------------------------------------------------------------
    @staticmethod
    def _default_factory() -> Callable[..., Any]:
        if os.name == "posix":
            from harness.pty.posix import PosixPty

            return PosixPty
        else:  # pragma: no cover
            from harness.pty.windows import WindowsPty

            return WindowsPty


def _path_is_under(child: Path, parent: Path) -> bool:
    """is_relative_to backport that also tolerates non-existent ``parent``."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


__all__ = [
    "HookEvent",
    "OpenCodeAdapter",
]
