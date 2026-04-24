"""Unit tests for F10 · SkillsInstaller.install / pull.

Covers Test Inventory rows:
  T04 FUNC/happy        — install(kind="clone") argv + commit_sha
  T05 FUNC/happy        — pull(target_dir) argv = ["git","-C",..,"pull","--ff-only"]
  T11 SEC/url-whitelist — file:// rejected without spawning subprocess
  T12 SEC/url-meta      — shell-meta URL rejected without spawning subprocess
  T13 SEC/path-traversal— target_dir "plugins/../../etc/evil" rejected
  T15 SEC/run-lock      — .harness/run.lock present → SkillsInstallBusyError
  T-LOCAL FUNC/happy    — install(kind="local") copies absolute dir inside workdir
                          (design note: "TDD Red 期追加 local 分支")

All tests expect ``harness.skills`` to exist — FAIL in Red.

Feature ref: feature_3
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


def _make_workdir(tmp_path: Path) -> Path:
    wd = tmp_path / "project"
    wd.mkdir()
    (wd / ".harness").mkdir()  # for audit/lock files if needed
    (wd / "plugins").mkdir()
    return wd


def _make_local_bundle(root: Path) -> Path:
    bundle = root / "local_ltfa"
    (bundle / ".claude-plugin").mkdir(parents=True)
    (bundle / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "longtaskforagent", "version": "9.9"}), encoding="utf-8"
    )
    (bundle / "skills").mkdir()
    (bundle / "skills" / "x.md").write_text("X", encoding="utf-8")
    return bundle


# ---------------------------------------------------------------------------
# T04 · FUNC/happy — clone: argv list + commit_sha + no shell=True
# Traces To: FR-045 AC-1 · §Implementation Summary flow branch#Clone-ok
# ---------------------------------------------------------------------------


def test_t04_install_clone_uses_argv_list_no_shell_and_returns_commit_sha(
    tmp_path: Path,
) -> None:
    """Mock subprocess.run to fake a successful clone and populate target."""
    from harness.skills import SkillsInstaller, SkillsInstallRequest, SkillsInstallResult

    wd = _make_workdir(tmp_path)

    # Fake git clone implementation: create the target dir w/ manifest + .git
    captured_argv: list[list[str]] = []
    captured_kwargs: list[dict[str, Any]] = []

    def fake_run(argv, **kwargs):
        captured_argv.append(list(argv))
        captured_kwargs.append(dict(kwargs))
        # argv[0:4] = ["git","clone","--depth","1"]; argv[-2:] = [source, target]
        # Create target layout at argv[-1]
        target = Path(argv[-1])
        (target / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (target / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "longtaskforagent", "version": "1.2.3"}),
            encoding="utf-8",
        )
        (target / ".git").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    # Fake rev-parse to yield a stable commit_sha
    def fake_read_manifest_result(plugin_dir):
        # When read_manifest is called, it should invoke git rev-parse.
        return None

    with patch("subprocess.run", side_effect=fake_run) as mock_run:
        installer = SkillsInstaller()
        req = SkillsInstallRequest(
            kind="clone",
            source="https://github.com/org/longtaskforagent.git",
            target_dir="plugins/longtaskforagent",
        )

        # We also expect that when read_manifest is called and .git/ is present,
        # the installer fills commit_sha. Patch the registry's rev-parse call
        # via subprocess.run too (fake_run above already returns 0). For the
        # rev-parse we want a 40-hex stdout. Switch to a richer side effect:
        def fake_run_v2(argv, **kwargs):
            if "rev-parse" in argv:
                return subprocess.CompletedProcess(argv, 0, stdout="a" * 40 + "\n", stderr="")
            return fake_run(argv, **kwargs)

        mock_run.side_effect = fake_run_v2

        result = installer.install(req, workdir=wd)

    assert isinstance(result, SkillsInstallResult)
    assert result.ok is True
    # commit_sha is 40 hex chars (from fake rev-parse)
    assert isinstance(result.commit_sha, str)
    assert len(result.commit_sha) == 40
    assert all(c in "0123456789abcdef" for c in result.commit_sha)
    # message is non-empty and contains some user-facing string
    assert result.message and isinstance(result.message, str)

    # Verify argv list. The CLONE call is the one that writes .claude-plugin —
    # find it in captured_argv (rev-parse call also captured).
    clone_argvs = [a for a in captured_argv if "clone" in a]
    assert clone_argvs, "expected at least one git clone invocation"
    clone_argv = clone_argvs[0]
    assert clone_argv[0] == "git"
    assert clone_argv[1] == "clone"
    assert "--depth" in clone_argv and "1" in clone_argv
    assert "--" in clone_argv, "argv must terminate options with --"
    # source URL appears intact
    assert "https://github.com/org/longtaskforagent.git" in clone_argv

    # No subprocess.run call used shell=True
    for kw in captured_kwargs:
        assert kw.get("shell") is not True, "shell=True must NEVER be used"


# ---------------------------------------------------------------------------
# T05 · FUNC/happy — pull argv with -C and --ff-only
# Traces To: FR-045 AC-2 · §Implementation Summary flow branch#pull
# ---------------------------------------------------------------------------


def test_t05_pull_uses_dash_C_and_ff_only_and_returns_head_sha(tmp_path: Path) -> None:
    from harness.skills import SkillsInstaller

    wd = _make_workdir(tmp_path)
    target = wd / "plugins" / "longtaskforagent"
    target.mkdir(parents=True)
    (target / ".git").mkdir()
    (target / ".claude-plugin").mkdir()
    (target / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "longtaskforagent", "version": "1.0"}), encoding="utf-8"
    )

    captured: list[list[str]] = []

    def fake_run(argv, **kwargs):
        captured.append(list(argv))
        assert kwargs.get("shell") is not True
        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout="b" * 40 + "\n", stderr="")
        # pull
        return subprocess.CompletedProcess(argv, 0, stdout="Already up to date.\n", stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        result = SkillsInstaller().pull(str(target), workdir=wd)

    assert result.ok is True
    assert result.commit_sha == "b" * 40
    # locate the pull invocation
    pulls = [a for a in captured if "pull" in a]
    assert pulls, "expected at least one git pull invocation"
    pull_argv = pulls[0]
    assert pull_argv[0] == "git"
    assert "-C" in pull_argv
    dash_c_idx = pull_argv.index("-C")
    assert Path(pull_argv[dash_c_idx + 1]) == target
    assert "pull" in pull_argv
    assert "--ff-only" in pull_argv


# ---------------------------------------------------------------------------
# T11 · SEC/url-whitelist — file:// rejected, subprocess NOT invoked
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "file:///etc/passwd",
        "ftp://example.com/repo.git",
        "javascript:alert(1)",
        "",
    ],
)
def test_t11_install_rejects_non_whitelisted_url(tmp_path: Path, bad_url: str) -> None:
    from harness.skills import GitUrlRejectedError, SkillsInstaller, SkillsInstallRequest

    wd = _make_workdir(tmp_path)
    req = SkillsInstallRequest(kind="clone", source=bad_url, target_dir="plugins/ltfa")
    with patch("subprocess.run") as mock_run:
        with pytest.raises(GitUrlRejectedError):
            SkillsInstaller().install(req, workdir=wd)
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# T12 · SEC/url-meta — shell meta injection rejected, subprocess NOT invoked
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://legit.com/repo.git; rm -rf ~",
        "https://legit.com/repo.git\nrm -rf ~",
        "https://legit.com/repo.git\r\nls",
        "https://legit.com/../../etc/repo.git",  # path traversal in URL
    ],
)
def test_t12_install_rejects_shell_meta_in_url(tmp_path: Path, bad_url: str) -> None:
    from harness.skills import GitUrlRejectedError, SkillsInstaller, SkillsInstallRequest

    wd = _make_workdir(tmp_path)
    req = SkillsInstallRequest(kind="clone", source=bad_url, target_dir="plugins/ltfa")
    with patch("subprocess.run") as mock_run:
        with pytest.raises(GitUrlRejectedError):
            SkillsInstaller().install(req, workdir=wd)
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# T13 · SEC/path-traversal — target_dir escaping plugins/ rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_target",
    [
        "plugins/../../etc/evil",
        "../outside",
        "/absolute/path",
        "plugins",  # must have a sub-name under plugins/
    ],
)
def test_t13_install_rejects_target_path_escape(tmp_path: Path, bad_target: str) -> None:
    from harness.skills import (
        SkillsInstaller,
        SkillsInstallRequest,
        TargetPathEscapeError,
    )

    wd = _make_workdir(tmp_path)
    req = SkillsInstallRequest(
        kind="clone",
        source="https://github.com/org/ltfa.git",
        target_dir=bad_target,
    )
    with patch("subprocess.run") as mock_run:
        with pytest.raises(TargetPathEscapeError):
            SkillsInstaller().install(req, workdir=wd)
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# T15 · SEC/run-lock — .harness/run.lock present → Busy
# ---------------------------------------------------------------------------


def test_t15_install_rejects_when_run_lock_present(tmp_path: Path) -> None:
    from harness.skills import (
        SkillsInstallBusyError,
        SkillsInstaller,
        SkillsInstallRequest,
    )

    wd = _make_workdir(tmp_path)
    (wd / ".harness" / "run.lock").write_text("", encoding="utf-8")

    req = SkillsInstallRequest(
        kind="clone",
        source="https://github.com/org/ltfa.git",
        target_dir="plugins/longtaskforagent",
    )
    with patch("subprocess.run") as mock_run:
        with pytest.raises(SkillsInstallBusyError):
            SkillsInstaller().install(req, workdir=wd)
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# T-LOCAL · FUNC/happy — kind="local" copies an absolute dir
# Design note: "`kind="local"` 分支的单测补于 TDD 阶段"
# Traces To: §Implementation Summary flow branch#Local (CopyLocal)
# ---------------------------------------------------------------------------


def test_t_local_install_copies_absolute_local_dir_into_plugins(tmp_path: Path) -> None:
    from harness.skills import SkillsInstaller, SkillsInstallRequest

    wd = _make_workdir(tmp_path)
    # a valid local bundle OUTSIDE of wd/plugins (but "absolute + somewhere")
    local_bundle = _make_local_bundle(tmp_path)

    req = SkillsInstallRequest(
        kind="local",
        source=str(local_bundle),
        target_dir="plugins/longtaskforagent",
    )
    # local copy must not spawn any subprocess (no git needed for bare copy)
    with patch("subprocess.run") as mock_run:
        result = SkillsInstaller().install(req, workdir=wd)

    # destination contains the bundle's manifest
    dst = wd / "plugins" / "longtaskforagent"
    assert (dst / ".claude-plugin" / "plugin.json").is_file()
    assert (dst / "skills" / "x.md").read_text(encoding="utf-8") == "X"
    assert result.ok is True
    # local copy must NOT invoke git for the copy step itself
    # (it may still call git rev-parse if .git is present; our bundle has none)
    for call in mock_run.call_args_list:
        argv = call.args[0] if call.args else call.kwargs.get("args")
        assert "clone" not in argv, "local kind must not call git clone"


__all__: list[str] = []
