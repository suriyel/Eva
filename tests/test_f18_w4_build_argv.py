"""F18 Wave 4 · ClaudeCodeAdapter / OpenCodeAdapter build_argv tests.

Test Inventory: T01, T02, T03, T04.
SRS: FR-008 / FR-016 / FR-017.
Design Trace: §Interface Contract build_argv + Design seq msg#3 +
              系统设计 §6.1.1 commit 92538da.

Layer marker:
  # [unit] — pure logic; no PTY / no real CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.domain.ticket import DispatchSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _claude_spec(tmp_path: Path, *, model: str | None = None, mcp_config: str | None = None) -> DispatchSpec:
    base = tmp_path / ".harness-workdir" / "r1"
    (base / ".claude").mkdir(parents=True, exist_ok=True)
    plugin_dir = base / ".claude" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path = base / ".claude" / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    return DispatchSpec(
        argv=[],
        env={"HOME": str(base)},
        cwd=str(base),
        model=model,
        mcp_config=mcp_config,
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )


def _opencode_spec(tmp_path: Path, *, model: str | None = None, mcp_config: str | None = None) -> DispatchSpec:
    base = tmp_path / ".harness-workdir" / "r1"
    base.mkdir(parents=True, exist_ok=True)
    plugin_dir = base / ".opencode" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path = base / ".opencode" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{}", encoding="utf-8")
    return DispatchSpec(
        argv=[],
        env={"HOME": str(base)},
        cwd=str(base),
        model=model,
        mcp_config=mcp_config,
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )


# ---------------------------------------------------------------------------
# T01 — FUNC/happy — Traces To: FR-016 AC-1 + Design seq msg#3 + §6.1.1
# ---------------------------------------------------------------------------
def test_t01_claude_build_argv_strict_8_item_template_no_model(tmp_path):
    """argv must equal SRS FR-016 strict 8-item whitelist when no model."""
    from harness.adapter.claude import ClaudeCodeAdapter

    spec = _claude_spec(tmp_path, model=None)
    argv = ClaudeCodeAdapter().build_argv(spec)
    expected = [
        "claude",
        "--dangerously-skip-permissions",
        "--plugin-dir",
        spec.plugin_dir,
        "--settings",
        spec.settings_path,
        "--setting-sources",
        "project",
    ]
    assert argv == expected, f"argv mismatch: got {argv}, expected {expected}"
    assert len(argv) == 8


# ---------------------------------------------------------------------------
# T02 — FUNC/happy — Traces To: FR-016 AC-1 with --model
# ---------------------------------------------------------------------------
def test_t02_claude_build_argv_strict_10_item_template_with_model(tmp_path):
    """argv must equal SRS FR-016 strict 10-item template with --model inserted between settings and setting-sources."""
    from harness.adapter.claude import ClaudeCodeAdapter

    spec = _claude_spec(tmp_path, model="opus")
    argv = ClaudeCodeAdapter().build_argv(spec)
    expected = [
        "claude",
        "--dangerously-skip-permissions",
        "--plugin-dir",
        spec.plugin_dir,
        "--settings",
        spec.settings_path,
        "--model",
        "opus",
        "--setting-sources",
        "project",
    ]
    assert argv == expected, f"argv mismatch: got {argv}, expected {expected}"
    assert len(argv) == 10
    # --model must appear AFTER --settings and BEFORE --setting-sources
    assert argv.index("--model") > argv.index("--settings")
    assert argv.index("--model") < argv.index("--setting-sources")


# ---------------------------------------------------------------------------
# T03 — FUNC/error — Traces To: FR-008 AC-1 negative (banned flags)
# ---------------------------------------------------------------------------
def test_t03_claude_argv_never_contains_banned_flags(tmp_path):
    """argv must never contain -p / --print / --output-format / --include-partial-messages."""
    from harness.adapter.claude import ClaudeCodeAdapter

    for model in (None, "opus", "sonnet"):
        spec = _claude_spec(tmp_path, model=model)
        argv = ClaudeCodeAdapter().build_argv(spec)
        for banned in ("-p", "--print", "--output-format", "--include-partial-messages"):
            assert banned not in argv, f"banned flag {banned!r} appeared in argv: {argv}"


def test_t03b_claude_argv_never_contains_mcp_flags_even_when_spec_has_mcp(tmp_path):
    """FR-016 forbids --mcp-config / --strict-mcp-config; spec.mcp_config must trigger v1 degrade not argv injection."""
    from harness.adapter.claude import ClaudeCodeAdapter

    spec = _claude_spec(tmp_path, mcp_config="/tmp/some-mcp.json")
    argv = ClaudeCodeAdapter().build_argv(spec)
    assert "--mcp-config" not in argv
    assert "--strict-mcp-config" not in argv


# ---------------------------------------------------------------------------
# T04 — FUNC/error — Traces To: FR-016 AC-2 + flowchart#3 OpenCodeBranch
# ---------------------------------------------------------------------------
def test_t04_opencode_mcp_config_triggers_v1_degrade_with_user_toast(tmp_path):
    """OpenCode adapter with mcp_config: argv must NOT contain mcp flags; degrader records UI toast."""
    from harness.adapter.opencode import OpenCodeAdapter

    spec = _opencode_spec(tmp_path, mcp_config="/path/x")
    adapter = OpenCodeAdapter()
    argv = adapter.build_argv(spec)
    assert "--mcp-config" not in argv
    assert "--strict-mcp-config" not in argv
    # mcp_degrader must have pushed an explanatory toast to UI:
    toasts = getattr(adapter, "mcp_degrader", None)
    assert toasts is not None, "OpenCodeAdapter must expose mcp_degrader for UI toasts"
    pushed = list(getattr(toasts, "toast_pushed", []))
    assert len(pushed) >= 1, "Expected a v1 MCP degrade toast"
    assert any("OpenCode MCP" in t and "v1.1" in t for t in pushed), (
        f"Expected toast to mention 'OpenCode MCP' and 'v1.1'; got {pushed}"
    )


def test_t04b_opencode_argv_starts_with_opencode_and_mcp_degrader_toast_is_list(tmp_path):
    """FR-017: OpenCode argv first element must be 'opencode'.

    Wave 4 strengthens FR-016 AC-2 by requiring `mcp_degrader.toast_pushed`
    to be a LIST of pushed messages (Wave 3 used a bool flag). T04 reads
    `toast_pushed[0]` so this attribute must support indexing.
    """
    from harness.adapter.opencode import OpenCodeAdapter

    spec = _opencode_spec(tmp_path, model="claude-3-7-sonnet", mcp_config="/path/x")
    adapter = OpenCodeAdapter()
    argv = adapter.build_argv(spec)
    assert argv[0] == "opencode"
    # Optional model should appear when supplied
    assert "--model" in argv
    assert "claude-3-7-sonnet" in argv
    # Wave-4 contract: toast_pushed is a list of message strings (T04 expectation).
    pushed = adapter.mcp_degrader.toast_pushed
    assert isinstance(pushed, list), (
        f"Wave 4 expects mcp_degrader.toast_pushed to be a list of pushed messages "
        f"(supports [0] indexing); got type={type(pushed).__name__}"
    )
    assert len(pushed) == 1, f"expected 1 toast message; got {len(pushed)}"
