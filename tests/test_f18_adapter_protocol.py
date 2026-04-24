"""F18 · Bk-Adapter — ToolAdapter Protocol & build_argv tests (FR-008/015/016/017/018, NFR-014).

Covers Test Inventory: T01, T02, T03, T04, T05, T27, T28.

Layer marker:
  # [unit] — pure logic; no PTY / no real CLI; integration counterparts in tests/integration/
"""

from __future__ import annotations

import pytest

# Top-level dependency on existing F02 schema is OK (F02 is passing).
from harness.domain.ticket import DispatchSpec

# F18 imports are deferred into each test body — during TDD Red they will raise
# ImportError per-test (each test FAILs individually) instead of breaking pytest
# collection for the whole file.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _isolated_paths(tmp_path):
    """Return (cwd, plugin_dir, settings_path, mcp_config) all under .harness-workdir/r1/."""
    base = tmp_path / ".harness-workdir" / "r1"
    base.mkdir(parents=True, exist_ok=True)
    plugin_dir = base / ".claude" / "plugins"
    settings_path = base / ".claude" / "settings.json"
    mcp_config = base / "mcp.json"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{}")
    mcp_config.write_text("{}")
    return str(base), str(plugin_dir), str(settings_path), str(mcp_config)


def _spec(
    *,
    argv,
    cwd,
    plugin_dir,
    settings_path,
    mcp_config=None,
    model=None,
):
    return DispatchSpec(
        argv=argv,
        env={"PATH": "/usr/bin", "HOME": cwd},
        cwd=cwd,
        model=model,
        mcp_config=mcp_config,
        plugin_dir=plugin_dir,
        settings_path=settings_path,
    )


# ---------------------------------------------------------------------------
# T01 — FUNC/happy — Traces To: FR-016 AC-1 · §Interface Contract ClaudeCodeAdapter.build_argv
# ---------------------------------------------------------------------------
def test_t01_claude_build_argv_full_required_flag_set(tmp_path):
    """argv 必含 FR-016 全部必选 flag，按确定顺序；不含 -p 与 --model；setting-sources 不含 local。

    Wrong-impl killers:
      - any missing flag → assertion fails
      - extra `-p`       → set membership assertion fails
      - setting-sources containing `local` → equality on `user,project` fails
    """
    from harness.adapter.claude import ClaudeCodeAdapter

    cwd, plugin_dir, settings_path, mcp_config = _isolated_paths(tmp_path)
    spec = _spec(
        argv=["claude"],
        cwd=cwd,
        plugin_dir=plugin_dir,
        settings_path=settings_path,
        mcp_config=mcp_config,
    )
    adapter = ClaudeCodeAdapter()
    argv = adapter.build_argv(spec)

    assert argv[0] == "claude"
    assert "-p" not in argv, "FR-008: interactive mode must NEVER pass -p"
    assert "--dangerously-skip-permissions" in argv
    assert "--include-partial-messages" in argv
    assert "--strict-mcp-config" in argv
    # Output format pair must be adjacent and ordered
    out_idx = argv.index("--output-format")
    assert argv[out_idx + 1] == "stream-json"
    # Flag-with-value pairs
    pd_idx = argv.index("--plugin-dir")
    assert argv[pd_idx + 1] == plugin_dir
    mc_idx = argv.index("--mcp-config")
    assert argv[mc_idx + 1] == mcp_config
    st_idx = argv.index("--settings")
    assert argv[st_idx + 1] == settings_path
    ss_idx = argv.index("--setting-sources")
    assert argv[ss_idx + 1] == "user,project", "must exclude `local`"
    assert "local" not in argv[ss_idx + 1].split(",")
    # No --model when spec.model is None
    assert "--model" not in argv


# ---------------------------------------------------------------------------
# T02 — FUNC/happy — Traces To: FR-016 AC-2
# ---------------------------------------------------------------------------
def test_t02_claude_build_argv_includes_model_when_set(tmp_path):
    from harness.adapter.claude import ClaudeCodeAdapter

    cwd, plugin_dir, settings_path, mcp_config = _isolated_paths(tmp_path)
    spec = _spec(
        argv=["claude"],
        cwd=cwd,
        plugin_dir=plugin_dir,
        settings_path=settings_path,
        mcp_config=mcp_config,
        model="sonnet-4",
    )
    argv = ClaudeCodeAdapter().build_argv(spec)
    assert "--model" in argv
    m_idx = argv.index("--model")
    assert argv[m_idx + 1] == "sonnet-4"


# ---------------------------------------------------------------------------
# T03 — FUNC/error — Traces To: §Interface Contract build_argv Raises · IFR-001 SEC
# ---------------------------------------------------------------------------
def test_t03_claude_build_argv_rejects_non_isolated_plugin_dir(tmp_path):
    """plugin_dir 指向 ~/.claude/plugins → InvalidIsolationError (NFR-009 zero-write)."""
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.errors import InvalidIsolationError

    cwd, _, settings_path, mcp_config = _isolated_paths(tmp_path)
    bad_plugin_dir = "/home/user/.claude/plugins"
    spec = _spec(
        argv=["claude"],
        cwd=cwd,
        plugin_dir=bad_plugin_dir,
        settings_path=settings_path,
        mcp_config=mcp_config,
    )
    with pytest.raises(InvalidIsolationError):
        ClaudeCodeAdapter().build_argv(spec)


# ---------------------------------------------------------------------------
# T04 — FUNC/happy — Traces To: FR-017 AC-1 · OpenCodeAdapter.build_argv
#       UML flow branch: McpDegrade=NO, Model=NO, Agent=NO
# ---------------------------------------------------------------------------
def test_t04_opencode_build_argv_minimal_no_model_no_mcp(tmp_path):
    from harness.adapter.opencode import OpenCodeAdapter

    cwd, plugin_dir, settings_path, _ = _isolated_paths(tmp_path)
    spec = _spec(
        argv=["opencode"],
        cwd=cwd,
        plugin_dir=plugin_dir,
        settings_path=settings_path,
        mcp_config=None,
        model=None,
    )
    argv = OpenCodeAdapter().build_argv(spec)
    assert argv[0] == "opencode"
    assert "--model" not in argv
    assert "--agent" not in argv
    assert "--mcp-config" not in argv
    assert "--strict-mcp-config" not in argv
    assert "-p" not in argv


# ---------------------------------------------------------------------------
# T05 — FUNC/error — Traces To: FR-017 AC-2 · INT-013
#       UML flow branch: McpDegrade=YES (FR-014 — mcp dropped + toast)
# ---------------------------------------------------------------------------
def test_t05_opencode_build_argv_drops_mcp_and_pushes_toast(tmp_path):
    from harness.adapter.opencode import OpenCodeAdapter

    cwd, plugin_dir, settings_path, mcp_config = _isolated_paths(tmp_path)
    spec = _spec(
        argv=["opencode"],
        cwd=cwd,
        plugin_dir=plugin_dir,
        settings_path=settings_path,
        mcp_config=mcp_config,
    )
    adapter = OpenCodeAdapter()
    argv = adapter.build_argv(spec)
    # Degradation: mcp flags dropped
    assert "--mcp-config" not in argv
    assert "--strict-mcp-config" not in argv
    assert mcp_config not in argv
    # Degradation toast must have been pushed (anomaly bus / WebSocket)
    assert adapter.mcp_degrader.toast_pushed is True


# ---------------------------------------------------------------------------
# T27 — FUNC/happy — Traces To: FR-015 · FR-018 · NFR-014
# ---------------------------------------------------------------------------
def test_t27_runtime_checkable_protocol_accepts_full_provider():
    """A class implementing all 6 ToolAdapter methods passes isinstance(_, ToolAdapter)."""
    from harness.adapter import ToolAdapter

    class MockProvider:
        def build_argv(self, spec):
            return ["mock"]

        def spawn(self, spec):
            raise NotImplementedError

        def extract_hil(self, event):
            return []

        def parse_result(self, events):
            raise NotImplementedError

        def detect_anomaly(self, events):
            return None

        def supports(self, flag):
            return False

    assert isinstance(MockProvider(), ToolAdapter) is True


# ---------------------------------------------------------------------------
# T28 — FUNC/error — Traces To: FR-015 AC · FR-018 error path · NFR-014
# ---------------------------------------------------------------------------
def test_t28_runtime_checkable_protocol_rejects_partial_provider():
    """A class missing 5 of the 6 methods must NOT pass isinstance(_, ToolAdapter)."""
    from harness.adapter import ToolAdapter

    class Broken:
        def build_argv(self, spec):
            return ["broken"]

    assert isinstance(Broken(), ToolAdapter) is False


# ---------------------------------------------------------------------------
# Capability flags sanity (covers ToolAdapter.supports method T27 traceability)
# ---------------------------------------------------------------------------
def test_capability_flags_enum_has_required_members():
    """CapabilityFlags must expose MCP_STRICT and HOOKS (used by Adapter.supports)."""
    from harness.adapter import CapabilityFlags

    assert hasattr(CapabilityFlags, "MCP_STRICT")
    assert hasattr(CapabilityFlags, "HOOKS")
