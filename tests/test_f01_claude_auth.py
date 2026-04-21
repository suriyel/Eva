"""Unit tests for F01 · ClaudeAuthDetector (feature #1, FR-046 + IFR-001 协同).

Covers T04, T05, T06 from design §7 Test Inventory and the
``ClaudeAuthDetector.detect`` boundary rows in §8.

[unit] — ``subprocess.run`` + ``shutil.which`` mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _make_completed_process(
    args: list[str], returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=args, returncode=returncode, stdout=stdout, stderr=stderr
    )


# ---------------------------------------------------------------------------
# T04 — FUNC/happy — FR-046 AC1 — logged in
# ---------------------------------------------------------------------------
def test_detect_returns_authenticated_when_claude_auth_status_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil as _shutil
    import harness.auth.claude_detector as mod
    from harness.auth import ClaudeAuthDetector

    monkeypatch.setattr(
        _shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None
    )

    calls: list[list[str]] = []

    def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        if args[:2] == ["claude", "--version"]:
            return _make_completed_process(args, 0, stdout="claude 1.2.3\n")
        if args[:3] == ["claude", "auth", "status"]:
            return _make_completed_process(args, 0, stdout="Logged in as user@example.com\n")
        raise AssertionError(f"unexpected subprocess call: {args!r}")

    monkeypatch.setattr(mod.subprocess, "run", _run)

    status = ClaudeAuthDetector().detect()

    assert status.cli_present is True
    assert status.authenticated is True
    assert status.hint is None
    assert status.source == "claude-cli"
    # Both probe commands must have been called.
    assert ["claude", "--version"] in calls
    assert ["claude", "auth", "status"] in calls


# ---------------------------------------------------------------------------
# T05 — FUNC/error — FR-046 AC2 — cli present but not authenticated
# ---------------------------------------------------------------------------
def test_detect_returns_not_authenticated_when_status_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil as _shutil
    import re
    import harness.auth.claude_detector as mod
    from harness.auth import ClaudeAuthDetector

    monkeypatch.setattr(
        _shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None
    )

    def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["claude", "--version"]:
            return _make_completed_process(args, 0, stdout="claude 1.2.3\n")
        if args[:3] == ["claude", "auth", "status"]:
            return _make_completed_process(args, 1, stderr="not authenticated\n")
        raise AssertionError(f"unexpected: {args!r}")

    monkeypatch.setattr(mod.subprocess, "run", _run)

    status = ClaudeAuthDetector().detect()

    assert status.cli_present is True
    assert status.authenticated is False
    assert status.source == "claude-cli"
    # NFR-010 — hint must be 简体中文 and contain the canonical remedy.
    assert status.hint is not None
    assert "claude auth login" in status.hint
    assert re.search(
        r"[一-鿿]", status.hint
    ), f"hint should contain CJK characters: {status.hint!r}"


# ---------------------------------------------------------------------------
# T06 — FUNC/error — CLI missing from PATH
# ---------------------------------------------------------------------------
def test_detect_returns_cli_absent_when_claude_not_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil as _shutil
    from harness.auth import ClaudeAuthDetector

    monkeypatch.setattr(_shutil, "which", lambda name: None)

    status = ClaudeAuthDetector().detect()

    assert status.cli_present is False
    assert status.authenticated is False
    assert status.source == "skipped"
    assert status.hint == "未检测到 Claude Code CLI"


# ---------------------------------------------------------------------------
# Detect must not write ~/.claude/ (NFR-009 / CON-007) — mtime must not change.
# ---------------------------------------------------------------------------
def test_detect_never_writes_to_claude_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Detect is READ-only per §Implementation Summary item 5."""
    import shutil as _shutil
    import harness.auth.claude_detector as mod
    from harness.auth import ClaudeAuthDetector

    fake_claude_home = tmp_path / "dot_claude"
    fake_claude_home.mkdir()
    sentinel = fake_claude_home / "sentinel"
    sentinel.write_text("x", encoding="utf-8")
    before_mtime = sentinel.stat().st_mtime_ns

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        _shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None
    )

    def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _make_completed_process(args, 0, stdout="claude 1.0.0\n")

    monkeypatch.setattr(mod.subprocess, "run", _run)

    ClaudeAuthDetector().detect()
    after_mtime = sentinel.stat().st_mtime_ns

    # READ-only contract — sentinel in a fake ~/.claude/ must remain untouched.
    assert after_mtime == before_mtime, "detect() must not touch ~/.claude/"


# ---------------------------------------------------------------------------
# T-subprocess-oserror — OSError from subprocess.run must be absorbed.
# ---------------------------------------------------------------------------
def test_detect_returns_cli_absent_on_subprocess_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil as _shutil
    import harness.auth.claude_detector as mod
    from harness.auth import ClaudeAuthDetector

    monkeypatch.setattr(
        _shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None
    )

    def _raise(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("cannot spawn")

    monkeypatch.setattr(mod.subprocess, "run", _raise)

    status = ClaudeAuthDetector().detect()
    # Must degrade to cli_present=False, never raise.
    assert status.cli_present is False
    assert status.authenticated is False
