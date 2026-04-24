"""F18 · Bk-Adapter — OpenCode hooks.json + version check tests.

Covers Test Inventory: T24, T25, T26.
SRS: FR-012 (AC-1, AC-2), IFR-002 SEC (path traversal).

Layer marker:
  # [unit + fs] — uses real tmp_path filesystem; subprocess version check mocked.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from harness.env.models import IsolatedPaths

# F18 imports deferred per-test (TDD Red — modules absent).


def _paths(cwd: Path) -> IsolatedPaths:
    pd = cwd / ".claude" / "plugins"
    sp = cwd / ".claude" / "settings.json"
    pd.mkdir(parents=True, exist_ok=True)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("{}")
    return IsolatedPaths(
        cwd=str(cwd),
        plugin_dir=str(pd),
        settings_path=str(sp),
        mcp_config_path=None,
    )


# ---------------------------------------------------------------------------
# T24 — FUNC/happy — Traces To: FR-012 AC-1 · OpenCodeAdapter.ensure_hooks
# ---------------------------------------------------------------------------
def test_t24_ensure_hooks_writes_secure_file(tmp_path):
    """hooks.json 写入 0o600，含 name='Question' + channel='harness-hil'."""
    from harness.adapter.opencode import OpenCodeAdapter

    cwd = tmp_path / ".harness-workdir" / "r1"
    cwd.mkdir(parents=True, exist_ok=True)
    paths = _paths(cwd)

    adapter = OpenCodeAdapter()
    hooks_path = adapter.ensure_hooks(paths)

    p = Path(hooks_path)
    assert p.exists(), "hooks.json must be created"
    assert p.parent.name == ".opencode"
    assert p.parent.parent == cwd, "hooks must reside under <cwd>/.opencode/"

    # File mode must be 0o600 (POSIX). Skip strict mode assertion on Windows.
    if os.name == "posix":
        mode = stat.S_IMODE(p.stat().st_mode)
        assert mode == 0o600, f"expected 0o600, got 0o{mode:o}"

    body = json.loads(p.read_text())
    body_str = json.dumps(body)
    assert "Question" in body_str, "must register Question tool match"
    assert "harness-hil" in body_str, "must wire channel=harness-hil"


# ---------------------------------------------------------------------------
# T25 — SEC/bndry — Traces To: FR-012 AC-2 · IFR-002 SEC · path traversal
# ---------------------------------------------------------------------------
def test_t25_ensure_hooks_rejects_symlink_escape(tmp_path):
    """构造 symlink <cwd>/.opencode -> /etc → 抛 InvalidIsolationError；/etc 未被写。"""
    from harness.adapter.errors import InvalidIsolationError
    from harness.adapter.opencode import OpenCodeAdapter

    if os.name != "posix":
        pytest.skip("symlink escape test requires POSIX symlink semantics")

    cwd = tmp_path / ".harness-workdir" / "r1"
    cwd.mkdir(parents=True, exist_ok=True)
    # Create symlink that escapes outside <cwd>
    target = tmp_path / "outside"
    target.mkdir(parents=True, exist_ok=True)
    (cwd / ".opencode").symlink_to(target, target_is_directory=True)

    paths = _paths(cwd)
    with pytest.raises(InvalidIsolationError):
        OpenCodeAdapter().ensure_hooks(paths)

    # Outside dir must NOT have been written.
    assert not (target / "hooks.json").exists(), "must NOT write outside <cwd>"


# ---------------------------------------------------------------------------
# T26 — FUNC/error — Traces To: FR-012 AC-2 (version check)
# ---------------------------------------------------------------------------
def test_t26_spawn_raises_when_opencode_version_too_old(tmp_path, monkeypatch):
    """OpenCode <0.3.0 不支持 hooks → spawn 抛 HookRegistrationError 提示升级。"""
    from harness.adapter.errors import HookRegistrationError
    from harness.adapter.opencode import OpenCodeAdapter

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    from harness.adapter.opencode.hooks import VersionCheck

    # Force version check to report old version.
    monkeypatch.setattr(VersionCheck, "current_version", staticmethod(lambda: "0.2.9"))

    cwd = tmp_path / ".harness-workdir" / "r1"
    cwd.mkdir(parents=True, exist_ok=True)
    paths = _paths(cwd)

    from harness.domain.ticket import DispatchSpec

    spec = DispatchSpec(
        argv=["opencode"],
        env={"PATH": "/usr/bin"},
        cwd=str(cwd),
        model=None,
        mcp_config=None,
        plugin_dir=paths.plugin_dir,
        settings_path=paths.settings_path,
    )

    with pytest.raises(HookRegistrationError) as exc:
        OpenCodeAdapter().spawn(spec)
    msg = str(exc.value).lower()
    assert "upgrade" in msg or "version" in msg or "opencode" in msg
