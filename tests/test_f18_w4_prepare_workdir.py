"""F18 Wave 4 · ClaudeCodeAdapter.prepare_workdir tests.

Test Inventory: T23, T24, T26.
SRS: FR-051 / NFR-009 / IFR-001 AC-w4-1.
Design Trace: §Implementation Summary flowchart prepare_workdir + §Interface Contract.

Layer marker:
  # [unit] — uses real local fs (tmp_path); does not invoke claude CLI.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from harness.domain.ticket import DispatchSpec
from harness.env.models import IsolatedPaths


def _spec_and_paths(tmp_path: Path, *, model: str | None = None, tool: str = "claude"):
    """Return (spec, paths) with cwd properly under .harness-workdir/."""
    cwd = tmp_path / ".harness-workdir" / "r1"
    cwd.mkdir(parents=True, exist_ok=True)
    plugin_dir = cwd / ".claude" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path = cwd / ".claude" / "settings.json"
    spec = DispatchSpec(
        argv=[],
        env={
            "HOME": str(cwd),
            "HARNESS_BASE_URL": "http://127.0.0.1:8765",
        },
        cwd=str(cwd),
        model=model,
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )
    # tool dispatch hint stored as attribute on spec extension dict if needed by adapter.
    paths = IsolatedPaths(cwd=str(cwd), plugin_dir=str(plugin_dir), settings_path=str(settings_path))
    return spec, paths


# ---------------------------------------------------------------------------
# T23 — FUNC/happy — FR-051 AC-1 — three artifacts produced + 0o755 on bridge
# ---------------------------------------------------------------------------
def test_t23_prepare_workdir_writes_three_artifacts_with_correct_modes(tmp_path, monkeypatch):
    from harness.adapter.claude import ClaudeCodeAdapter

    spec, paths = _spec_and_paths(tmp_path)
    monkeypatch.setenv("HARNESS_BASE_URL", "http://127.0.0.1:8765")

    adapter = ClaudeCodeAdapter()
    out = adapter.prepare_workdir(spec, paths)

    cwd = Path(paths.cwd)
    skip_dialogs = cwd / ".claude.json"
    settings = cwd / ".claude" / "settings.json"
    bridge = cwd / ".claude" / "hooks" / "claude-hook-bridge.py"

    assert skip_dialogs.exists(), f"missing {skip_dialogs}"
    assert settings.exists(), f"missing {settings}"
    assert bridge.exists(), f"missing {bridge}"

    # bridge must be 0o755
    mode = stat.S_IMODE(bridge.stat().st_mode)
    assert mode == 0o755, f"bridge mode {oct(mode)} != 0o755"

    # settings.json must contain required fields
    sd = json.loads(settings.read_text(encoding="utf-8"))
    assert "env" in sd and isinstance(sd["env"], dict)
    assert "hooks" in sd and isinstance(sd["hooks"], dict)
    for hook_event in ("PreToolUse", "PostToolUse", "SessionStart", "SessionEnd"):
        assert hook_event in sd["hooks"], f"settings.hooks missing {hook_event}"
    # claude CLI 2.1.119 expects enabledPlugins as a record (Expected record,
    # but received array). Empty dict ≡ "no plugins enabled" + passes validator.
    assert sd.get("enabledPlugins") == {}, f"enabledPlugins must be {{}}; got {sd.get('enabledPlugins')!r}"
    assert sd.get("skipDangerousModePermissionPrompt") is True

    # .claude.json field check
    cd = json.loads(skip_dialogs.read_text(encoding="utf-8"))
    assert cd.get("hasCompletedOnboarding") is True
    assert cd.get("projects", {}).get(str(cwd), {}).get("hasTrustDialogAccepted") is True
    assert isinstance(cd.get("lastOnboardingVersion"), str) and cd["lastOnboardingVersion"]
    assert int(cd.get("projectOnboardingSeenCount", 0)) >= 1

    # postcondition: returns paths transparently
    assert out.cwd == paths.cwd


# ---------------------------------------------------------------------------
# T24 — BNDRY/idempotent — second call produces byte-equal content
# ---------------------------------------------------------------------------
def test_t24_prepare_workdir_is_idempotent_byte_equal_on_re_call(tmp_path, monkeypatch):
    from harness.adapter.claude import ClaudeCodeAdapter

    spec, paths = _spec_and_paths(tmp_path)
    monkeypatch.setenv("HARNESS_BASE_URL", "http://127.0.0.1:8765")

    adapter = ClaudeCodeAdapter()
    adapter.prepare_workdir(spec, paths)

    cwd = Path(paths.cwd)
    files = [
        cwd / ".claude.json",
        cwd / ".claude" / "settings.json",
        cwd / ".claude" / "hooks" / "claude-hook-bridge.py",
    ]
    first = {f: f.read_bytes() for f in files}

    # Second call
    adapter.prepare_workdir(spec, paths)
    second = {f: f.read_bytes() for f in files}

    for f in files:
        assert first[f] == second[f], (
            f"prepare_workdir not idempotent — content of {f.name} changed on re-call"
        )


# ---------------------------------------------------------------------------
# T26 — SEC/escape — write-path escape detection (cwd not under .harness-workdir/)
# ---------------------------------------------------------------------------
def test_t26_prepare_workdir_rejects_paths_outside_harness_workdir(tmp_path, monkeypatch):
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.errors import InvalidIsolationError

    # Force cwd OUTSIDE .harness-workdir/
    bad_cwd = tmp_path / "user-home"
    bad_cwd.mkdir(parents=True, exist_ok=True)
    plugin_dir = bad_cwd / ".claude" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path = bad_cwd / ".claude" / "settings.json"

    spec = DispatchSpec(
        argv=[],
        env={"HOME": str(bad_cwd)},
        cwd=str(bad_cwd),
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )
    paths = IsolatedPaths(
        cwd=str(bad_cwd),
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )
    monkeypatch.setenv("HARNESS_BASE_URL", "http://127.0.0.1:8765")

    with pytest.raises(InvalidIsolationError):
        ClaudeCodeAdapter().prepare_workdir(spec, paths)
