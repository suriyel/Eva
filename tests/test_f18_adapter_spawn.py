"""F18 · Bk-Adapter — spawn / detect_anomaly tests (FR-008, ATS Err-B/J).

Covers Test Inventory: T06, T07, T08.

Layer marker:
  # [unit] — pty boundary mocked; pure spawn-flow validation.
"""

from __future__ import annotations

import pytest

from harness.domain.ticket import DispatchSpec

# F18 imports are deferred into test bodies (TDD Red — modules not yet created).


def _spec(tmp_path):
    base = tmp_path / ".harness-workdir" / "r1"
    base.mkdir(parents=True, exist_ok=True)
    plugin_dir = base / ".claude" / "plugins"
    settings_path = base / ".claude" / "settings.json"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{}")
    return DispatchSpec(
        argv=["claude"],
        env={"PATH": "/usr/bin"},
        cwd=str(base),
        model=None,
        mcp_config=None,
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )


# ---------------------------------------------------------------------------
# T06 — FUNC/happy — Traces To: FR-008 · §Interface Contract ClaudeCodeAdapter.spawn
#       seq msg#1 / msg#2 / msg#3 (Supervisor→spawn→start→exec)
# ---------------------------------------------------------------------------
def test_t06_spawn_returns_ticket_process_without_dash_p(tmp_path, monkeypatch):
    """spawn 返回 TicketProcess；argv 不含 -p；pty 子进程命令为 claude。

    Wrong-impl killers:
      - if spawn passes -p (non-interactive), assertion fails
      - if spawn returns None / dict instead of TicketProcess, attribute access fails
      - if pty_argv[0] != "claude", assertion fails
    """
    from harness.adapter.claude import ClaudeCodeAdapter

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    captured = {}

    class FakePty:
        def __init__(self, argv, env, cwd):
            captured["argv"] = list(argv)
            captured["env"] = dict(env)
            captured["cwd"] = cwd
            self.pid = 12345

        def start(self):
            captured["started"] = True

        def write(self, data):  # noqa: D401
            return len(data)

        def close(self):
            captured["closed"] = True

    adapter = ClaudeCodeAdapter(pty_factory=FakePty)
    proc = adapter.spawn(_spec(tmp_path))

    assert proc.pid == 12345
    assert proc.ticket_id  # non-empty
    assert "-p" not in captured["argv"], "FR-008: -p forbidden"
    assert captured["argv"][0] == "claude"
    assert captured.get("started") is True


# ---------------------------------------------------------------------------
# T07 — FUNC/error — Traces To: §Interface Contract spawn Raises · ATS Err-B
# ---------------------------------------------------------------------------
def test_t07_spawn_raises_when_cli_missing(tmp_path, monkeypatch):
    """shutil.which 返回 None → SpawnError("Claude CLI not found")。"""
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.errors import SpawnError

    monkeypatch.setattr("shutil.which", lambda name: None)

    with pytest.raises(SpawnError) as exc:
        ClaudeCodeAdapter().spawn(_spec(tmp_path))
    assert "Claude CLI not found" in str(exc.value)


# ---------------------------------------------------------------------------
# T08 — FUNC/error — Traces To: ATS Err-J · FR-046 (anomaly classification)
# ---------------------------------------------------------------------------
def test_t08_detect_anomaly_classifies_not_authenticated_as_skill_error():
    """stderr 含 "not authenticated" 应被分类为 skill_error，而非 context_overflow。"""
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.stream.events import StreamEvent

    events = [
        StreamEvent(
            kind="error",
            seq=1,
            payload={"message": "Error: not authenticated. Please re-login."},
        )
    ]
    info = ClaudeCodeAdapter().detect_anomaly(events)
    assert info is not None
    assert info.cls == "skill_error"
    assert "not authenticated" in info.detail.lower()
