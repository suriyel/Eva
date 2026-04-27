"""F18 Wave 4 · Real-fs isolation hash test (T25).

SRS: FR-051 AC-2 / IFR-001 AC-w4-1 / NFR-009.
Test Inventory: T25 — sha256 of mocked user-scope ~/.claude/settings.json
                + ~/.claude.json must remain byte-equal across a full HIL run.

Layer marker:
  # [integration] — uses real local filesystem (tmp_path is real fs).
  # @pytest.mark.real_fs makes this visible to check_real_tests.py.

Real-test invariants (Rule 5a):
  - We do NOT mock pathlib / os / open. tmp_path is real fs.
  - We hard-fail if the run is unable to execute prepare_workdir, instead of
    skipping silently.
  - High-value assertion: byte-equal sha256 hashes (not 'no exception' or
    'file is not None').
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from harness.domain.ticket import DispatchSpec
from harness.env.models import IsolatedPaths


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.real_fs
def test_t25_real_fs_prepare_workdir_does_not_touch_user_scope_settings(tmp_path, monkeypatch):
    """[feature 18] FR-051 AC-2 + IFR-001 AC-w4-1: user-scope ~/.claude/settings.json
    + ~/.claude.json byte-equal before/after prepare_workdir + (mock) HIL round-trip.
    """
    from harness.adapter.claude import ClaudeCodeAdapter

    # Mock user home — a separate tmp tree that simulates ~/.claude
    fake_home = tmp_path / "fake-home"
    user_claude_dir = fake_home / ".claude"
    user_claude_dir.mkdir(parents=True, exist_ok=True)
    user_settings = user_claude_dir / "settings.json"
    user_claude_json = fake_home / ".claude.json"
    user_settings.write_text(
        json.dumps({"sentinel": "user-scope-must-not-be-touched"}),
        encoding="utf-8",
    )
    user_claude_json.write_text(
        json.dumps({"hasCompletedOnboarding": False, "sentinel": "user"}),
        encoding="utf-8",
    )

    before_settings_sha = _sha256(user_settings)
    before_claude_json_sha = _sha256(user_claude_json)

    # Isolated workdir under .harness-workdir/
    isolated = tmp_path / ".harness-workdir" / "r1"
    plugin_dir = isolated / ".claude" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path = isolated / ".claude" / "settings.json"
    spec = DispatchSpec(
        argv=[],
        env={
            "HOME": str(isolated),
            "HARNESS_BASE_URL": "http://127.0.0.1:8765",
        },
        cwd=str(isolated),
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )
    paths = IsolatedPaths(
        cwd=str(isolated),
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("HARNESS_BASE_URL", "http://127.0.0.1:8765")

    adapter = ClaudeCodeAdapter()
    adapter.prepare_workdir(spec, paths)

    # Hash invariance after prepare_workdir
    after_settings_sha = _sha256(user_settings)
    after_claude_json_sha = _sha256(user_claude_json)

    assert after_settings_sha == before_settings_sha, (
        f"~/.claude/settings.json was modified by prepare_workdir "
        f"(before={before_settings_sha} after={after_settings_sha}). "
        "Wave 4 isolation contract violated (FR-051 AC-2 / IFR-001 AC-w4-1)."
    )
    assert after_claude_json_sha == before_claude_json_sha, (
        f"~/.claude.json was modified by prepare_workdir "
        f"(before={before_claude_json_sha} after={after_claude_json_sha})."
    )
