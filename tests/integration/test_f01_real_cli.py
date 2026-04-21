"""Integration test for F01 · real claude-CLI presence detection (feature #1).

Covers T21 (INTG/cli-presence-real) from design §7 Test Inventory.

[integration] — uses a real subprocess invocation against a shim script on disk,
proving that ``ClaudeAuthDetector.detect()`` runs real subprocess.run (no mock
on subprocess.run inside this test).

Feature ref: feature_1
"""

from __future__ import annotations

import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

pytestmark = pytest.mark.real_cli


@contextmanager
def _path_prepended(new_prefix: str) -> Iterator[None]:
    """Prepend ``new_prefix`` to PATH for the duration of the block (no monkeypatch)."""
    prev = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{new_prefix}{os.pathsep}{prev}" if prev else new_prefix
    try:
        yield
    finally:
        os.environ["PATH"] = prev


@contextmanager
def _path_replaced(new_value: str) -> Iterator[None]:
    prev = os.environ.get("PATH", "")
    os.environ["PATH"] = new_value
    try:
        yield
    finally:
        os.environ["PATH"] = prev


@pytest.mark.real_cli
def test_real_claude_detector_invokes_real_subprocess(tmp_path: Path) -> None:
    """feature_1 real test: fabricate a shim ``claude`` on PATH, detect must call it.

    No mock on subprocess.run — we rely on PATH manipulation so the real detector
    spawns a real shim binary.
    """
    from harness.auth import ClaudeAuthDetector

    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "claude"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "--version" ]]; then\n'
        '  echo "claude 9.9.9-shim"\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "auth" && "$2" == "status" ]]; then\n'
        '  echo "Logged in as real-shim@example.com"\n'
        "  exit 0\n"
        "fi\n"
        "exit 99\n",
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    assert os.environ.get("PATH"), "PATH env var is required for real CLI test"

    with _path_prepended(str(shim_dir)):
        t0 = time.monotonic()
        status = ClaudeAuthDetector().detect()
        elapsed = time.monotonic() - t0

    assert status.cli_present is True, "shim on PATH should be discovered by shutil.which"
    assert status.authenticated is True
    assert status.source == "claude-cli"
    assert elapsed < 2.0, f"detect() took {elapsed:.2f}s, expected < 2s (NFR-005-adjacent)"


@pytest.mark.real_cli
def test_real_claude_detector_handles_real_missing_cli(tmp_path: Path) -> None:
    """feature_1 real test: empty PATH → cli_present=False without raising."""
    from harness.auth import ClaudeAuthDetector

    # Scrub PATH so no claude binary can be located.
    with _path_replaced(str(tmp_path / "nonexistent_bin")):
        status = ClaudeAuthDetector().detect()

    assert status.cli_present is False
    assert status.authenticated is False
    assert status.hint == "未检测到 Claude Code CLI"
