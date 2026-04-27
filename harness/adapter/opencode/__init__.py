"""F18 Wave 4 · OpenCodeAdapter (FR-012/017, IFR-002).

Submodule layout:
  - this file (__init__.py): OpenCodeAdapter class with Wave-4 7-method Protocol
  - hooks.py: HookConfigWriter / HookQuestionParser / McpDegradation / VersionCheck

Wave 4 changes:
  - prepare_workdir(spec, paths) writes ``<paths.cwd>/.opencode/hooks.json`` (mode 0o600)
  - map_hook_event(payload) accepts HookEventPayload-shaped dict and returns HilQuestion[]
  - extract_hil removed (Wave 3 contract)
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
    WorkdirPrepareError,
)
from harness.adapter.hook_payload import HookEventPayload
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
from harness.hil.hook_mapper import HookEventMapper
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
    "HARNESS_BASE_URL",
)


def _parse_version(s: str) -> tuple[int, int, int]:
    parts = s.strip().lstrip("v").split(".")
    nums: list[int] = []
    for p in parts[:3]:
        try:
            nums.append(int("".join(c for c in p if c.isdigit()) or "0"))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def _probe_opencode_version() -> str:
    """Module-level seam so tests can monkeypatch this rather than VersionCheck."""
    return VersionCheck.current_version()


class OpenCodeAdapter:
    """ToolAdapter implementation for the OpenCode CLI (Wave 4)."""

    def __init__(
        self,
        *,
        pty_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._pty_factory = pty_factory
        self._mapper = HookEventMapper()
        # Public attribute (Wave 4 T04 reads adapter.mcp_degrader.toast_pushed[0])
        self.mcp_degrader = McpDegradation()
        self.hook_writer = HookConfigWriter()
        self.hook_parser = HookQuestionParser()

    # ------------------------------------------------------------------
    def build_argv(self, spec: DispatchSpec) -> list[str]:
        argv: list[str] = ["opencode"]
        # Decision branch 1: mcp_config present → v1 degrade + UI toast
        if spec.mcp_config is not None:
            self.mcp_degrader.push_toast(
                "OpenCode MCP 延后 v1.1 — 已忽略 --mcp-config flag"
            )
        # Decision branch 2: model present
        if spec.model is not None:
            argv += ["--model", spec.model]
        # Decision branch 3: agent present (skill_hint maps to --agent)
        agent = getattr(spec, "agent", None)
        if agent is not None:
            argv += ["--agent", agent]
        return argv

    # ------------------------------------------------------------------
    def prepare_workdir(
        self, spec: DispatchSpec, paths: IsolatedPaths
    ) -> IsolatedPaths:
        """Write ``<paths.cwd>/.opencode/hooks.json`` (mode 0o600).

        FR-012 AC-2: opencode version < 0.3.0 → HookRegistrationError.
        """
        if not paths.cwd:
            raise InvalidIsolationError("paths.cwd must not be empty")

        version = _probe_opencode_version()
        if _parse_version(version) < _MIN_HOOKS_VERSION:
            raise HookRegistrationError(
                f"OpenCode version {version} too old — please upgrade to "
                f">= {'.'.join(str(n) for n in _MIN_HOOKS_VERSION)}"
            )

        cwd = Path(paths.cwd).resolve()
        opencode_dir = Path(paths.cwd) / ".opencode"

        # Path traversal guard — symlink attack containment.
        try:
            resolved_dir = opencode_dir.resolve()
        except (OSError, RuntimeError) as exc:
            raise InvalidIsolationError(f"failed to resolve hooks dir: {exc}") from exc
        if not _path_is_under(resolved_dir, cwd):
            raise InvalidIsolationError(
                f".opencode dir {resolved_dir} escapes isolated cwd {cwd}"
            )

        hooks_path = opencode_dir / "hooks.json"
        try:
            self.hook_writer.write(hooks_path)
        except (OSError, ValueError) as exc:
            raise WorkdirPrepareError(f"hooks.json write failed: {exc}") from exc
        if os.name == "posix":
            try:
                os.chmod(hooks_path, 0o600)
            except OSError as exc:
                raise WorkdirPrepareError(
                    f"chmod 0o600 on hooks.json failed: {exc}"
                ) from exc
        return paths

    # ------------------------------------------------------------------
    def spawn(
        self, spec: DispatchSpec, paths: IsolatedPaths | None = None
    ) -> TicketProcess:
        argv = self.build_argv(spec)
        if shutil.which(argv[0]) is None:
            raise SpawnError("OpenCode CLI not found")

        version = _probe_opencode_version()
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
        """Backwards-compat shim around ``prepare_workdir`` for callers that
        only need the hooks.json side-effect (used by F18 fs integration test).

        Returns the absolute path to the written ``hooks.json``.
        """
        # Build a minimal DispatchSpec carrying just enough fields for the
        # OpenCode prepare_workdir branch (cwd + plugin_dir + settings_path).
        spec = DispatchSpec(
            argv=[],
            env={},
            cwd=paths.cwd,
            plugin_dir=paths.plugin_dir,
            settings_path=paths.settings_path,
        )
        self.prepare_workdir(spec, paths)
        return str(Path(paths.cwd) / ".opencode" / "hooks.json")

    # ------------------------------------------------------------------
    def map_hook_event(self, payload: Any) -> list[HilQuestion]:
        """Map a hook stdin payload (HookEventPayload OR raw dict) → HilQuestion[]."""
        # Accept dicts directly (test T37 passes a raw dict) or pydantic obj.
        return self._mapper.parse(payload)

    # ------------------------------------------------------------------
    def parse_hook_line(self, raw: bytes) -> HookEvent | None:
        """Backwards-compatible NDJSON line parser (kept for in-tree callers)."""
        return self.hook_parser.parse(raw)

    # ------------------------------------------------------------------
    def parse_result(self, events: list[StreamEvent]) -> OutputInfo:
        texts: list[str] = []
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
        if flag is CapabilityFlags.HOOKS:
            return True
        if flag is CapabilityFlags.MCP_STRICT:
            return False
        return False

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
