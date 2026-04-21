"""Unit tests for F01 · 简体中文 user-facing strings (feature #1, NFR-010).

Covers T20 from design §7 Test Inventory.

[unit] — pure string assertions over public API.
"""

from __future__ import annotations

import re

import pytest


CJK_RE = re.compile(r"[一-鿿]")

# Blocklist of plain-English business phrases that must NOT leak into user-facing
# strings under NFR-010.
ENGLISH_BLACKLIST = [
    "please log in",
    "not authenticated",
    "not found",
    "error occurred",
    "success",
]


def _assert_zh_cn(text: str, *, context: str) -> None:
    assert text, f"{context}: string must be non-empty"
    assert CJK_RE.search(text), f"{context}: expected CJK characters in {text!r}"
    lowered = text.lower()
    for bad in ENGLISH_BLACKLIST:
        assert bad not in lowered, f"{context}: forbidden English phrase {bad!r} found in {text!r}"


def test_first_run_welcome_message_is_zh_cn(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.app import FirstRunWizard
    from harness.config import ConfigStore

    home = tmp_path / ".harness"
    monkeypatch.setenv("HARNESS_HOME", str(home))

    wizard = FirstRunWizard(ConfigStore(home / "config.json"))
    result = wizard.bootstrap()
    _assert_zh_cn(result.welcome_message, context="FirstRunResult.welcome_message")


def test_keyring_degraded_warning_is_zh_cn(monkeypatch: pytest.MonkeyPatch) -> None:
    import keyring
    import keyrings.alt.file  # type: ignore[import-not-found]

    from harness.auth import KeyringGateway

    monkeypatch.setattr(keyring, "get_keyring", lambda: keyrings.alt.file.PlaintextKeyring())

    info = KeyringGateway().detect_backend()
    assert info.degraded is True
    assert info.warning is not None
    _assert_zh_cn(info.warning, context="BackendInfo.warning")


def test_claude_auth_not_authenticated_hint_is_zh_cn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil as _shutil
    import subprocess
    import harness.auth.claude_detector as mod
    from harness.auth import ClaudeAuthDetector

    monkeypatch.setattr(
        _shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None
    )

    def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        returncode = 0 if args[:2] == ["claude", "--version"] else 1
        return subprocess.CompletedProcess(
            args=args, returncode=returncode, stdout="", stderr="not authenticated"
        )

    monkeypatch.setattr(mod.subprocess, "run", _run)

    status = ClaudeAuthDetector().detect()
    assert status.hint is not None
    _assert_zh_cn(status.hint, context="ClaudeAuthStatus.hint (not authenticated)")


def test_claude_auth_cli_missing_hint_is_zh_cn(monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil as _shutil
    from harness.auth import ClaudeAuthDetector

    monkeypatch.setattr(_shutil, "which", lambda name: None)

    status = ClaudeAuthDetector().detect()
    assert status.hint is not None
    _assert_zh_cn(status.hint, context="ClaudeAuthStatus.hint (cli missing)")
