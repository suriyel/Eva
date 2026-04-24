"""Integration tests for F10 · real git CLI subprocess (IFR-005).

Covers Test Inventory rows:
  T21 INTG/git-subprocess — real git pull --ff-only against a real local remote
  T22 INTG/git-non-repo    — target_dir without .git/ → GitSubprocessError

[integration] — uses REAL git binary + REAL filesystem. Subprocess is NOT
mocked. The primary external dependency (git CLI) is exercised end-to-end.

Feature ref: feature_3
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.real_cli


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    # ensure minimal identity so git commit works without global config
    env.setdefault("GIT_AUTHOR_NAME", "Harness Test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "Harness Test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )


@pytest.mark.real_cli
def test_t21_real_git_pull_ff_only_against_local_remote(tmp_path: Path) -> None:
    """feature_3 real test — exercise SkillsInstaller.pull against a real
    local bare repo + local clone. No subprocess mock."""
    assert shutil.which("git"), "git CLI must be available for this real test"

    # 1. create a bare "remote" with one commit
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(["init", "--bare", "--initial-branch=main"], cwd=remote)

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(["init", "--initial-branch=main"], cwd=seed)
    (seed / ".claude-plugin").mkdir()
    (seed / ".claude-plugin" / "plugin.json").write_text(
        '{"name":"longtaskforagent","version":"1.0"}', encoding="utf-8"
    )
    _git(["add", "-A"], cwd=seed)
    _git(["commit", "-m", "seed"], cwd=seed)
    _git(["remote", "add", "origin", str(remote)], cwd=seed)
    _git(["push", "origin", "main"], cwd=seed)

    # 2. clone the remote into a workdir/plugins subdir
    workdir = tmp_path / "project"
    (workdir / "plugins").mkdir(parents=True)
    (workdir / ".harness").mkdir()
    target = workdir / "plugins" / "longtaskforagent"
    _git(["clone", str(remote), str(target)])

    # 3. call SkillsInstaller.pull for real — must actually invoke git
    from harness.skills import SkillsInstaller

    result = SkillsInstaller().pull(str(target), workdir=workdir)

    assert result.ok is True
    # HEAD sha is returned in commit_sha — match against real rev-parse
    expected = _git(["rev-parse", "HEAD"], cwd=target).stdout.strip()
    assert (
        result.commit_sha == expected
    ), f"commit_sha mismatch: got {result.commit_sha!r}, expected {expected!r}"
    # HIGH-VALUE assertion: the message must not be a hollow placeholder
    assert result.message, "real pull must carry a message (stderr tail or zh summary)"


@pytest.mark.real_cli
def test_t22_real_pull_on_non_git_dir_raises_subprocess_error(tmp_path: Path) -> None:
    """feature_3 real test — target_dir exists but lacks .git/; pull must fail
    with GitSubprocessError OR TargetPathEscapeError (contract permits either).
    No subprocess.run mock — we rely on the real ``git`` binary returning
    non-zero in a non-repo directory."""
    assert shutil.which("git"), "git CLI must be available"

    from harness.skills import (
        GitSubprocessError,
        SkillsInstaller,
        TargetPathEscapeError,
    )

    workdir = tmp_path / "project"
    (workdir / "plugins").mkdir(parents=True)
    (workdir / ".harness").mkdir()
    target = workdir / "plugins" / "not-a-repo"
    target.mkdir()  # no .git/ inside

    with pytest.raises((GitSubprocessError, TargetPathEscapeError)):
        SkillsInstaller().pull(str(target), workdir=workdir)
