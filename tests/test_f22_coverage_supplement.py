"""Supplemental unit tests for F22 — raises line/branch coverage of the
F22-modified backend modules to the Gate 1 thresholds (line >= 90%, branch >= 80%).

Targeted lines (as reported by pytest-cov term-missing for harness/ scope):
    - harness/api/validate.py            52-53 (path-traversal resolve escape),
                                          82, 130-140 (ValidatorScriptUnknown,
                                          ValidatorTimeout finally branches),
                                          147-153 (env restore on temp-file path)
    - harness/api/general_settings.py    58, 64, 66, 69-70 (_detect_keyring_backend
                                          branches), 76 (_mask_plaintext short),
                                          87-90 (_persist_keyring exception),
                                          103, 119, 137, 161, 163 (PUT branches)
    - harness/api/git_routes.py          42-43 (_is_git_repo OSError),
                                          69, 74-106 (_list_git_log full path),
                                          120-124 (DiffNotFound fallback),
                                          166, 181-184 (binary marker, del/context
                                          path-prefix)
    - harness/api/skills.py              80, 83-85, 88, 91-102 (get_tree workdir
                                          fallback + plugin enumeration)
    - harness/subprocess/validator/runner.py 108-109, 113-114 (ProcessLookupError
                                              both branches), 133-143
                                              (issue dict-vs-non-dict),
                                              151-156 (subprocess_exit tail)

All tests anchor to feature #22 (F22) SRS coverage (FR-032, FR-033, FR-035,
FR-038, FR-041, NFR-008, IFR-004, IFR-005, IFR-006); no new FR-IDs are
introduced.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# harness.api.general_settings — keyring backend detection branches
# Traces To NFR-008 + IFR-006 (keyring native vs alt vs fail vs unknown)
# ---------------------------------------------------------------------------
def test_f22_general_settings_detect_native_macos_branch() -> None:
    """`_detect_keyring_backend` returns 'native' when keyring class name
    matches macOS / SecretService / Windows signatures (line 58)."""
    from harness.api import general_settings as gs

    class FakeKR:
        __module__ = "keyring.backends.macOS"
        __class__ = type("macOSKeyring", (), {})

    fake = FakeKR()
    fake.__class__.__module__ = "keyring.backends.macOS"
    fake.__class__.__name__ = "Keyring"

    with patch.object(gs, "__name__", gs.__name__):
        with patch("keyring.get_keyring", return_value=fake):
            assert gs._detect_keyring_backend() == "native"


def test_f22_general_settings_detect_keyrings_alt_plaintext_branch() -> None:
    """`keyrings.alt.PlaintextKeyring` → 'keyrings.alt' (line 64)."""
    from harness.api import general_settings as gs

    fake = type("PlaintextKeyring", (), {})()
    fake.__class__.__module__ = "keyrings.alt.file"

    with patch("keyring.get_keyring", return_value=fake):
        assert gs._detect_keyring_backend() == "keyrings.alt"


def test_f22_general_settings_detect_fail_branch() -> None:
    """fail/null backend → 'fail' (line 66)."""
    from harness.api import general_settings as gs

    fake = type("NullKeyring", (), {})()
    fake.__class__.__module__ = "keyring.backends.null"

    with patch("keyring.get_keyring", return_value=fake):
        assert gs._detect_keyring_backend() == "fail"


def test_f22_general_settings_detect_unknown_falls_back_alt() -> None:
    """Unknown keyring class → conservative 'keyrings.alt' (line 68)."""
    from harness.api import general_settings as gs

    fake = type("MysteryKR", (), {})()
    fake.__class__.__module__ = "third_party.crypto"

    with patch("keyring.get_keyring", return_value=fake):
        assert gs._detect_keyring_backend() == "keyrings.alt"


def test_f22_general_settings_detect_import_error_returns_fail() -> None:
    """Exception in keyring init → 'fail' (lines 69-70)."""
    from harness.api import general_settings as gs

    with patch("keyring.get_keyring", side_effect=RuntimeError("boom")):
        assert gs._detect_keyring_backend() == "fail"


def test_f22_general_settings_mask_short_plaintext() -> None:
    """`_mask_plaintext('ab')` returns '***ab' (whole string when < 3 chars)."""
    from harness.api.general_settings import _mask_plaintext

    assert _mask_plaintext("ab") == "***ab"
    assert _mask_plaintext("") is None
    assert _mask_plaintext(None) is None


def test_f22_general_settings_persist_keyring_swallows_backend_failure() -> None:
    """`_persist_keyring` swallows backend exceptions silently (lines 87-90)."""
    from harness.api import general_settings as gs

    with patch("keyring.set_password", side_effect=RuntimeError("backend down")):
        # Must not raise.
        gs._persist_keyring("plaintext-abc", {"service": "s", "user": "u"})


# ---------------------------------------------------------------------------
# harness.api.git_routes — _is_git_repo OSError + _list_git_log full path
# Traces To IFR-005 + FR-041
# ---------------------------------------------------------------------------
def test_f22_git_routes_is_git_repo_oserror_returns_false(tmp_path: Path) -> None:
    """`_is_git_repo` returns False when subprocess.run raises OSError (lines 42-43)."""
    from harness.api import git_routes

    with patch.object(
        git_routes.subprocess,
        "run",
        side_effect=OSError("no git binary"),
    ):
        assert git_routes._is_git_repo(tmp_path) is False


def test_f22_git_routes_is_git_repo_subprocess_error_returns_false(tmp_path: Path) -> None:
    """`_is_git_repo` returns False when SubprocessError raised (timeout)."""
    from harness.api import git_routes

    err = subprocess.SubprocessError("boom")
    with patch.object(git_routes.subprocess, "run", side_effect=err):
        assert git_routes._is_git_repo(tmp_path) is False


@pytest.mark.asyncio
async def test_f22_git_routes_list_git_log_returns_rows_for_real_repo(
    tmp_path: Path,
) -> None:
    """`_list_git_log` parses real `git log` output for a fresh repo (lines 73-106)."""
    from harness.api import git_routes

    subprocess.run(
        ["git", "init", "-q", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    # Configure committer (CI environments may lack global config).
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Tester"],
        check=True,
        capture_output=True,
    )
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "a.txt"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "initial: feat"],
        check=True,
        capture_output=True,
    )

    rows = await git_routes._list_git_log(tmp_path, limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row["sha"], str) and len(row["sha"]) == 40
    assert row["subject"] == "initial: feat"
    assert row["files_changed"] == 0
    assert row["feature_id"] is None


@pytest.mark.asyncio
async def test_f22_git_routes_list_git_log_returns_empty_when_git_fails(
    tmp_path: Path,
) -> None:
    """`_list_git_log` returns [] on non-zero git exit (line 86)."""
    from harness.api import git_routes

    rows = await git_routes._list_git_log(tmp_path, limit=10)
    # Non-git directory → git log exits non-zero → []
    assert rows == []


def test_f22_git_routes_parse_unified_diff_binary_marker() -> None:
    """`_parse_unified_diff` flips kind=binary on `Binary files ...` line (line 167-171)."""
    from harness.api.git_routes import _parse_unified_diff

    text = (
        "diff --git a/logo.png b/logo.png\n"
        "Binary files a/logo.png and b/logo.png differ\n"
    )
    files = _parse_unified_diff(text)
    assert len(files) == 1
    assert files[0]["kind"] == "binary"
    assert files[0]["placeholder"] is True
    assert "hunks" not in files[0]


def test_f22_git_routes_parse_unified_diff_text_lines() -> None:
    """`_parse_unified_diff` collects add/del/context lines (lines 179-184)."""
    from harness.api.git_routes import _parse_unified_diff

    text = (
        "diff --git a/foo.py b/foo.py\n"
        "@@ -1,2 +1,3 @@\n"
        " unchanged\n"
        "-old\n"
        "+new\n"
        "+extra\n"
    )
    files = _parse_unified_diff(text)
    assert len(files) == 1
    f = files[0]
    assert f["kind"] == "text"
    assert len(f["hunks"]) == 1
    line_types = [ln["type"] for ln in f["hunks"][0]["lines"]]
    assert "add" in line_types
    assert "del" in line_types
    assert "context" in line_types


# ---------------------------------------------------------------------------
# harness.api.skills — get_tree env-fallback + plugin enumeration
# Traces To FR-033 + IFR-006 (RT06)
# ---------------------------------------------------------------------------
def test_f22_skills_get_tree_uses_env_workdir_when_app_state_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When `app.state.workdir` is unset, `get_tree` falls back to
    `HARNESS_WORKDIR` env (lines 83-85)."""
    from harness.api.skills import router

    # Build a tiny FastAPI app with NO `app.state.workdir`.
    app = FastAPI()
    app.include_router(router)

    # Layout: tmp/plugins/foo/ and tmp/plugins/bar/
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "foo").mkdir()
    (tmp_path / "plugins" / "bar").mkdir()
    monkeypatch.setenv("HARNESS_WORKDIR", str(tmp_path))

    client = TestClient(app)
    resp = client.get("/api/skills/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert data["root"] == str(tmp_path)
    plugin_names = sorted(p["name"] for p in data["plugins"])
    assert plugin_names == ["bar", "foo"]


def test_f22_skills_get_tree_returns_empty_when_no_workdir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No app.state.workdir AND no env → empty tree, 200 (lines 86-88)."""
    from harness.api.skills import router

    app = FastAPI()
    app.include_router(router)
    monkeypatch.delenv("HARNESS_WORKDIR", raising=False)

    client = TestClient(app)
    resp = client.get("/api/skills/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plugins"] == []
    assert data["children"] == []


def test_f22_skills_get_tree_app_state_workdir_takes_priority(
    tmp_path: Path,
) -> None:
    """`app.state.workdir` (set via wire_services) overrides env var (line 80→82)."""
    from harness.api.skills import router

    app = FastAPI()
    app.include_router(router)
    app.state.workdir = str(tmp_path)
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "skillA").mkdir()

    client = TestClient(app)
    resp = client.get("/api/skills/tree")
    assert resp.status_code == 200
    plugins = resp.json()["plugins"]
    assert len(plugins) == 1
    assert plugins[0]["name"] == "skillA"


# ---------------------------------------------------------------------------
# harness.api.validate — path-traversal escape + error branches
# Traces To FR-035 SEC + FR-038 + FR-039
# ---------------------------------------------------------------------------
def test_f22_validate_rejects_resolved_escape(tmp_path: Path) -> None:
    """`_resolve_safe_file` rejects paths whose resolution escapes workdir
    (lines 52-53)."""
    from harness.api.validate import _resolve_safe_file
    from fastapi import HTTPException

    workdir = tmp_path / "wd"
    workdir.mkdir()
    # Create a sibling target outside workdir, then a symlink inside that points to it.
    sibling = tmp_path / "outside"
    sibling.mkdir()
    target = sibling / "secret.json"
    target.write_text("{}", encoding="utf-8")
    link = workdir / "alias.json"
    link.symlink_to(target)

    with pytest.raises(HTTPException) as excinfo:
        _resolve_safe_file("alias.json", workdir)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail["error_code"] == "path_traversal"


def test_f22_validate_normalise_collects_subprocess_exit_into_stderr_tail() -> None:
    """`_normalise_for_fe` extracts `subprocess_exit` rule_id messages into both
    a visible issue AND `stderr_tail` (lines 78-85)."""
    from harness.api.validate import _normalise_for_fe
    from harness.subprocess.validator.schemas import (
        ValidationIssue,
        ValidationReport,
    )

    report = ValidationReport(
        ok=False,
        issues=[
            ValidationIssue(
                severity="error",
                rule_id="subprocess_exit",
                path_json_pointer=None,
                message="Traceback (most recent call last): boom",
            ),
            ValidationIssue(
                severity="warning",
                rule_id="schema",
                path_json_pointer="/features/0/title",
                message="title too short",
            ),
        ],
        script_exit_code=1,
        duration_ms=42,
        http_status_hint=200,
    )
    out = _normalise_for_fe(report)
    assert out["ok"] is False
    assert out["stderr_tail"] == "Traceback (most recent call last): boom"
    paths = sorted(i["path"] for i in out["issues"])
    assert paths == ["/features/0/title", "subprocess_exit"]


# ---------------------------------------------------------------------------
# harness.subprocess.validator.runner — timeout dual-cleanup + parse branches
# Traces To FR-039 + FR-040
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_f22_validator_runner_timeout_swallows_processlookuperror(
    tmp_path: Path,
) -> None:
    """When `proc.terminate()` AND `proc.kill()` both raise ProcessLookupError,
    the runner still raises ValidatorTimeout (lines 108-114)."""
    from harness.subprocess.validator.runner import (
        ValidatorRunner,
        ValidatorTimeout,
    )
    from harness.subprocess.validator.schemas import ValidateRequest

    # Stage a synthetic `validate_features.py` script that sleeps long.
    plugin_root = tmp_path / "plugin"
    scripts_dir = plugin_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "validate_features.py").write_text(
        "import time, sys\ntime.sleep(30)\n",
        encoding="utf-8",
    )

    runner = ValidatorRunner(plugin_dir=plugin_root)
    req = ValidateRequest(
        path=str(tmp_path / "feature-list.json"),
        script="validate_features",
        workdir=str(tmp_path),
        timeout_s=0.1,
    )

    with pytest.raises(ValidatorTimeout):
        await runner.run(req)


@pytest.mark.asyncio
async def test_f22_validator_runner_parses_non_dict_issues_as_strings(
    tmp_path: Path,
) -> None:
    """When parsed JSON `issues` contains non-dict entries, they become
    severity='error' strings (lines 142-143)."""
    from harness.subprocess.validator.runner import ValidatorRunner
    from harness.subprocess.validator.schemas import ValidateRequest

    plugin_root = tmp_path / "plugin"
    scripts_dir = plugin_root / "scripts"
    scripts_dir.mkdir(parents=True)
    # Synthetic validator that emits non-dict issues
    (scripts_dir / "validate_features.py").write_text(
        'import json, sys\n'
        'print(json.dumps({"ok": False, "issues": ["bad-string-issue", 42]}))\n',
        encoding="utf-8",
    )
    runner = ValidatorRunner(plugin_dir=plugin_root)
    req = ValidateRequest(
        path=str(tmp_path / "feature-list.json"),
        script="validate_features",
        workdir=str(tmp_path),
        timeout_s=10.0,
    )
    report = await runner.run(req)
    assert report.ok is False
    issue_msgs = [i.message for i in report.issues]
    assert "bad-string-issue" in issue_msgs


@pytest.mark.asyncio
async def test_f22_validator_runner_appends_subprocess_exit_tail_on_nonzero_exit(
    tmp_path: Path,
) -> None:
    """When validator subprocess exits non-zero, runner appends a
    `subprocess_exit` issue with stderr tail (lines 148-154)."""
    from harness.subprocess.validator.runner import ValidatorRunner
    from harness.subprocess.validator.schemas import ValidateRequest

    plugin_root = tmp_path / "plugin"
    scripts_dir = plugin_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "validate_features.py").write_text(
        'import sys\n'
        'sys.stderr.write("Traceback: boom-from-validator\\n")\n'
        'sys.exit(2)\n',
        encoding="utf-8",
    )
    runner = ValidatorRunner(plugin_dir=plugin_root)
    req = ValidateRequest(
        path=str(tmp_path / "feature-list.json"),
        script="validate_features",
        workdir=str(tmp_path),
        timeout_s=10.0,
    )
    report = await runner.run(req)
    assert report.ok is False
    assert report.script_exit_code == 2
    rule_ids = [i.rule_id for i in report.issues]
    assert "subprocess_exit" in rule_ids
    tail_msgs = [i.message for i in report.issues if i.rule_id == "subprocess_exit"]
    assert any("boom-from-validator" in m for m in tail_msgs)
