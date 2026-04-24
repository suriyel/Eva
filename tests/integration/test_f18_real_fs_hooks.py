"""F18 · Bk-Adapter — Real filesystem hooks.json integration test.

Covers Test Inventory: T24-companion (real fs round-trip for OpenCode hooks).
feature_18 real_fs marker per feature-list.json real_test.marker_pattern.
feature: 18 (Bk-Adapter — Agent Adapter & HIL Pipeline).

Layer marker:
  # [integration] — uses real local filesystem (tmp_path is real fs from pytest).
  # `@pytest.mark.real_fs` makes this visible to check_real_tests.py.

Real-test invariants (Rule 5a):
  - Filesystem operations performed against real OS calls (no mocking of pathlib /
    os / open). tmp_path IS the real filesystem.
  - High-value assertions: file content parses as JSON, mode is 0o600, file is
    placed under <cwd>/.opencode/.
  - Hard-fail (no skip) on POSIX where mode bits are meaningful.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from harness.env.models import IsolatedPaths

# F18 imports deferred per-test (TDD Red — modules absent).


@pytest.mark.real_fs
def test_real_fs_ensure_hooks_writes_complete_hooks_json(tmp_path):
    """[feature 18] Real filesystem: hooks.json round-trips via real os.write + chmod (POSIX)."""
    from harness.adapter.opencode import OpenCodeAdapter

    cwd = tmp_path / ".harness-workdir" / "r1"
    pd = cwd / ".claude" / "plugins"
    sp = cwd / ".claude" / "settings.json"
    pd.mkdir(parents=True, exist_ok=True)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("{}")

    paths = IsolatedPaths(
        cwd=str(cwd),
        plugin_dir=str(pd),
        settings_path=str(sp),
        mcp_config_path=None,
    )

    adapter = OpenCodeAdapter()
    hooks_path = adapter.ensure_hooks(paths)

    # File exists on real fs and is JSON-parseable
    p = Path(hooks_path)
    assert p.exists()
    body = json.loads(p.read_text())
    # High-value structural assertions (kills "wrote {}" stub impl)
    body_str = json.dumps(body)
    assert "Question" in body_str
    assert "harness-hil" in body_str
    # Path is under <cwd>/.opencode/
    assert p.resolve().is_relative_to(cwd.resolve())
    # Mode is 0o600 (POSIX)
    if os.name == "posix":
        mode = stat.S_IMODE(p.stat().st_mode)
        assert mode == 0o600, f"expected 0o600, got 0o{mode:o}"
