"""F10 · EnvironmentIsolator — setup_run / teardown_run orchestration.

Design ref: docs/features/3-f10-environment-isolation-skills-install.md §4 / §6.

Flow (setup_run):
    Orchestrator → setup_run(run_id, workdir, bundle_root, home_dir?)
    → HomeMtimeGuard.snapshot(~/.claude) stored on instance
    → mkdir .harness-workdir/<run_id>/.claude/ (mode 0o700, parents=True)
    → write settings.json + mcp.json (UTF-8, \n terminated)
    → PluginRegistry.sync_bundle(src=bundle_root, dst=plugins/longtaskforagent)
    → return IsolatedPaths

Flow (teardown_run):
    Orchestrator → teardown_run(run_id, paths)
    → HomeMtimeGuard.diff_against(before_snapshot)
    → AuditWriter.append_raw(env.setup/env.teardown) [optional]
    → return HomeMtimeDiff
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .errors import (
    BundleNotFoundError,
    IsolationSetupError,
    RunIdInvalidError,
    TeardownError,
    WorkdirNotFoundError,
)
from .home_guard import HomeMtimeGuard
from .models import HomeMtimeDiff, IsolatedPaths, HomeMtimeSnapshot

if TYPE_CHECKING:  # pragma: no cover
    from harness.persistence.audit import AuditWriter


# Strict run_id regex per §Interface Contract: ^[A-Za-z0-9_-]{1,64}$
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        raise RunIdInvalidError(f"invalid run_id: {run_id!r} (must match ^[A-Za-z0-9_-]{{1,64}}$)")


@dataclass
class _RunState:
    """Per-run state the isolator retains between setup and teardown."""

    run_id: str
    workdir: Path
    home_dir: Path
    paths: IsolatedPaths
    home_snapshot: HomeMtimeSnapshot


class EnvironmentIsolator:
    """Creates per-run ``.harness-workdir/<run_id>/.claude/`` tree + copies
    bundle; snapshots + diffs ~/.claude for NFR-009 compliance."""

    def __init__(
        self,
        *,
        home_guard: HomeMtimeGuard | None = None,
        audit_writer: "AuditWriter | None" = None,
    ) -> None:
        self._home_guard = home_guard or HomeMtimeGuard()
        self._audit_writer = audit_writer
        self._runs: dict[str, _RunState] = {}

    # ------------------------------------------------------------------ setup
    def setup_run(
        self,
        run_id: str,
        *,
        workdir: Path,
        bundle_root: Path,
        home_dir: Path | None = None,
    ) -> IsolatedPaths:
        _validate_run_id(run_id)

        workdir = Path(workdir)
        if not workdir.exists() or not workdir.is_dir():
            raise WorkdirNotFoundError(f"workdir not found or not a directory: {workdir}")

        bundle_root = Path(bundle_root)
        manifest = bundle_root / ".claude-plugin" / "plugin.json"
        if not bundle_root.is_dir() or not manifest.is_file():
            raise BundleNotFoundError(f"bundle missing .claude-plugin/plugin.json: {bundle_root}")

        effective_home = Path(home_dir) if home_dir is not None else Path.home() / ".claude"

        # snapshot BEFORE creating anything — NFR-009 baseline.
        home_snapshot = self._home_guard.snapshot(effective_home)

        isolated_root = workdir / ".harness-workdir" / run_id
        claude_dir = isolated_root / ".claude"
        plugin_dir = claude_dir / "plugins"
        settings_path = claude_dir / "settings.json"
        mcp_config_path = claude_dir / "mcp.json"

        try:
            # mode 0o700 only takes effect on POSIX; NT ignores it.
            plugin_dir.mkdir(parents=True, exist_ok=True)
            if os.name == "posix":
                try:
                    os.chmod(claude_dir, 0o700)
                    os.chmod(isolated_root, 0o700)
                except OSError:  # pragma: no cover
                    pass

            settings_payload = {
                "permissions": {"allow": [], "deny": []},
                "paths": {"plugins": "./plugins"},
            }
            settings_path.write_text(
                json.dumps(settings_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            mcp_config_path.write_text(
                json.dumps({"servers": {}}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise IsolationSetupError(f"mkdir/write failed under {isolated_root}: {exc!r}") from exc

        # Physical copy of the plugin bundle (lazy import to avoid cycle).
        from harness.skills.registry import PluginRegistry
        from harness.skills.errors import BundleSyncError

        dst_plugin_dir = plugin_dir / "longtaskforagent"
        try:
            PluginRegistry().sync_bundle(bundle_root, dst_plugin_dir)
        except BundleSyncError as exc:
            raise IsolationSetupError(f"copytree failed for {dst_plugin_dir}: {exc!r}") from exc

        paths = IsolatedPaths(
            cwd=str(workdir),
            plugin_dir=str(plugin_dir),
            settings_path=str(settings_path),
            mcp_config_path=str(mcp_config_path),
        )

        self._runs[run_id] = _RunState(
            run_id=run_id,
            workdir=workdir,
            home_dir=effective_home,
            paths=paths,
            home_snapshot=home_snapshot,
        )

        self._maybe_audit(
            "env.setup",
            run_id,
            {
                "paths": paths.model_dump(mode="json"),
                "workdir": str(workdir),
                "home_dir": str(effective_home),
            },
        )

        return paths

    # ------------------------------------------------------------------ teardown
    def teardown_run(self, run_id: str, paths: IsolatedPaths) -> HomeMtimeDiff:
        state = self._runs.get(run_id)
        if state is None:
            raise TeardownError(f"teardown_run called without matching setup: {run_id!r}")

        diff = self._home_guard.diff_against(state.home_snapshot)

        # remove the run state AFTER computing diff so a re-teardown is rejected.
        self._runs.pop(run_id, None)

        self._maybe_audit(
            "env.teardown",
            run_id,
            {
                "ok": diff.ok,
                "changed_files": [c.model_dump(mode="json") for c in diff.changed_files],
                "added_files": list(diff.added_files),
                "removed_files": list(diff.removed_files),
            },
        )

        return diff

    # ---------------------------------------------------------------- audit
    def _maybe_audit(self, kind: str, run_id: str, payload: dict[str, Any]) -> None:
        writer = self._audit_writer
        if writer is None:
            return
        # Sync raw append — avoids asyncio plumbing in sync setup/teardown.
        writer.append_raw(run_id=run_id, kind=kind, payload=payload)


__all__ = ["EnvironmentIsolator"]
