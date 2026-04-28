"""Branch-coverage supplement for F10 · Environment Isolation & Skills Installer.

These tests exist exclusively to raise line/branch coverage on the F10 impl
files (harness/env/*, harness/skills/*, harness/api/skills.py) above the
quality-gate thresholds (line >= 90%, branch >= 80%). They target error
paths, optional parameter combinations, and defensive early returns that
the primary Red tests (T01..T25) did not exercise.

Feature ref: feature_3
SRS trace: FR-043, FR-044, FR-045, NFR-009
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# harness.env.home_guard — HomeMtimeGuard + WorkdirScopeGuard branch gaps
# ---------------------------------------------------------------------------


def test_home_guard_snapshot_raises_when_home_is_file_not_dir(tmp_path: Path) -> None:
    """Covers home_guard line 37 — home exists but is not a directory."""
    from harness.env.home_guard import HomeMtimeGuard
    from harness.env.errors import HomeSnapshotError

    bogus = tmp_path / "claude_as_file"
    bogus.write_text("not a dir", encoding="utf-8")

    with pytest.raises(HomeSnapshotError):
        HomeMtimeGuard().snapshot(bogus)


def test_home_guard_snapshot_skips_symlinks_when_follow_is_false(tmp_path: Path) -> None:
    """Covers home_guard lines 45-46 — symlink skip path."""
    from harness.env.home_guard import HomeMtimeGuard

    home = tmp_path / "home"
    home.mkdir()
    real = tmp_path / "real.txt"
    real.write_text("r", encoding="utf-8")
    link = home / "link.txt"
    link.symlink_to(real)
    regular = home / "reg.txt"
    regular.write_text("x", encoding="utf-8")

    snap = HomeMtimeGuard().snapshot(home, follow_symlinks=False)
    assert "reg.txt" in snap.entries
    assert "link.txt" not in snap.entries  # symlink filtered


def test_home_guard_snapshot_follow_symlinks_filters_non_files(tmp_path: Path) -> None:
    """Covers home_guard lines 41-43 — follow_symlinks True but non-file path."""
    from harness.env.home_guard import HomeMtimeGuard

    home = tmp_path / "home"
    home.mkdir()
    sub = home / "subdir"  # directory — p.is_file() is False under follow branch
    sub.mkdir()
    (sub / "f.txt").write_text("a", encoding="utf-8")

    snap = HomeMtimeGuard().snapshot(home, follow_symlinks=True)
    # subdir itself is not recorded (directories are skipped)
    assert "subdir" not in snap.entries
    assert "subdir/f.txt" in snap.entries


def test_home_guard_snapshot_handles_stat_oserror(tmp_path: Path) -> None:
    """Covers home_guard lines 51-52 — stat() raises OSError, entry skipped.

    Model a race where rglob has already buffered a filename but the file
    disappears before the snapshot loop calls lstat on it. We unlink the
    file from inside a patched is_file hook so that lstat (called next)
    raises ENOENT / OSError. is_symlink / is_file still succeed via the
    file's in-memory state before deletion.
    """
    from harness.env import home_guard as hg

    home = tmp_path / "home"
    home.mkdir()
    (home / "good.txt").write_text("g", encoding="utf-8")
    (home / "stable.txt").write_text("s", encoding="utf-8")

    real_is_file = Path.is_file
    deleted = {"done": False}

    def flaky_is_file(self):  # type: ignore[no-untyped-def]
        result = real_is_file(self)
        if self.name == "good.txt" and result and not deleted["done"]:
            # is_file came back True; now unlink so the subsequent lstat fails
            try:
                self.unlink()
            except OSError:
                pass
            deleted["done"] = True
        return result

    with patch.object(Path, "is_file", flaky_is_file):
        snap = hg.HomeMtimeGuard().snapshot(home)

    # good.txt entered the loop but the lstat-after-unlink failed → skipped
    assert "good.txt" not in snap.entries
    assert "stable.txt" in snap.entries


def test_home_guard_diff_detects_added_and_removed(tmp_path: Path) -> None:
    """Covers home_guard lines 80-81 (removed) and 87-88 (added) branches."""
    from harness.env.home_guard import HomeMtimeGuard

    home = tmp_path / "home"
    home.mkdir()
    (home / "keeps.txt").write_text("k", encoding="utf-8")
    (home / "deletes.txt").write_text("d", encoding="utf-8")

    guard = HomeMtimeGuard()
    before = guard.snapshot(home)

    (home / "deletes.txt").unlink()
    (home / "new.txt").write_text("n", encoding="utf-8")

    diff = guard.diff_against(before)
    assert "deletes.txt" in diff.removed_files
    assert "new.txt" in diff.added_files
    assert diff.ok is False


def test_workdir_scope_guard_raises_when_workdir_missing(tmp_path: Path) -> None:
    """Covers home_guard line 121 — workdir missing/non-dir."""
    from harness.env.home_guard import WorkdirScopeGuard
    from harness.env.errors import WorkdirScopeError

    missing = tmp_path / "does_not_exist"

    with pytest.raises(WorkdirScopeError):
        WorkdirScopeGuard().assert_scope(missing, before=set())


def test_workdir_scope_guard_auto_computes_after_set(tmp_path: Path) -> None:
    """Covers the `after is None` branch in assert_scope — self rglob."""
    from harness.env.home_guard import WorkdirScopeGuard

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / ".harness" / "ok.txt").write_text("o", encoding="utf-8")
    # Unexpected file at root
    (wd / "stray.txt").write_text("s", encoding="utf-8")

    report = WorkdirScopeGuard().assert_scope(wd, before=set())
    assert "stray.txt" in report.unexpected_new
    assert report.ok is False


# ---------------------------------------------------------------------------
# harness.skills.registry — PluginRegistry branch gaps
# ---------------------------------------------------------------------------


def _write_manifest(plugin_dir: Path, payload: object | bytes) -> None:
    (plugin_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    path = plugin_dir / ".claude-plugin" / "plugin.json"
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def test_registry_read_manifest_raises_on_read_oserror(tmp_path: Path) -> None:
    """Covers registry lines 38-39 — read_bytes OSError."""
    from harness.skills.registry import PluginRegistry
    from harness.skills.errors import PluginManifestCorruptError

    plugin = tmp_path / "p"
    _write_manifest(plugin, {"name": "n", "version": "1"})

    original_read_bytes = Path.read_bytes

    def flaky(self):  # type: ignore[no-untyped-def]
        if self.name == "plugin.json":
            raise OSError("read failed")
        return original_read_bytes(self)

    with patch.object(Path, "read_bytes", flaky):
        with pytest.raises(PluginManifestCorruptError):
            PluginRegistry().read_manifest(plugin)


def test_registry_read_manifest_rejects_invalid_json(tmp_path: Path) -> None:
    """Covers registry lines 51-52 — json decode error."""
    from harness.skills.registry import PluginRegistry
    from harness.skills.errors import PluginManifestCorruptError

    plugin = tmp_path / "p"
    _write_manifest(plugin, b"not json {")

    with pytest.raises(PluginManifestCorruptError):
        PluginRegistry().read_manifest(plugin)


def test_registry_read_manifest_rejects_non_object_top_level(tmp_path: Path) -> None:
    """Covers registry line 57 — top-level JSON is a list."""
    from harness.skills.registry import PluginRegistry
    from harness.skills.errors import PluginManifestCorruptError

    plugin = tmp_path / "p"
    _write_manifest(plugin, ["a", "b"])

    with pytest.raises(PluginManifestCorruptError):
        PluginRegistry().read_manifest(plugin)


def test_registry_read_manifest_requires_name_version(tmp_path: Path) -> None:
    """Covers registry line 64 — missing/invalid name/version types."""
    from harness.skills.registry import PluginRegistry
    from harness.skills.errors import PluginManifestCorruptError

    plugin = tmp_path / "p"
    _write_manifest(plugin, {"name": 1, "version": 2})

    with pytest.raises(PluginManifestCorruptError):
        PluginRegistry().read_manifest(plugin)


def test_registry_sync_bundle_rejects_non_dir_source(tmp_path: Path) -> None:
    """Covers registry line 86 — src_bundle not a directory."""
    from harness.skills.registry import PluginRegistry
    from harness.skills.errors import BundleSyncError

    f = tmp_path / "not_a_dir.txt"
    f.write_text("x", encoding="utf-8")

    with pytest.raises(BundleSyncError):
        PluginRegistry().sync_bundle(f, tmp_path / "dst")


def test_registry_sync_bundle_requires_manifest_in_source(tmp_path: Path) -> None:
    """Covers registry line 89 — src_bundle missing plugin.json."""
    from harness.skills.registry import PluginRegistry
    from harness.skills.errors import BundleSyncError

    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"

    with pytest.raises(BundleSyncError):
        PluginRegistry().sync_bundle(src, dst)


def test_registry_sync_bundle_rejects_src_nested_inside_dst(tmp_path: Path) -> None:
    """Covers registry line 102 — src_bundle nested inside dst."""
    from harness.skills.registry import PluginRegistry
    from harness.skills.errors import BundleSyncError

    parent = tmp_path / "parent"
    parent.mkdir()
    src = parent / "inner"
    _write_manifest(src, {"name": "n", "version": "1"})

    # dst == parent (so src is nested inside dst)
    with pytest.raises(BundleSyncError):
        PluginRegistry().sync_bundle(src, parent)


def test_registry_sync_bundle_wraps_copytree_oserror(tmp_path: Path) -> None:
    """Covers registry lines 113-114 — shutil.copytree raises OSError."""
    from harness.skills.registry import PluginRegistry
    from harness.skills.errors import BundleSyncError

    src = tmp_path / "src"
    _write_manifest(src, {"name": "n", "version": "1"})
    dst = tmp_path / "dst"

    with patch("harness.skills.registry.shutil.copytree", side_effect=OSError("boom")):
        with pytest.raises(BundleSyncError):
            PluginRegistry().sync_bundle(src, dst)


def test_registry_rev_parse_returns_none_on_subprocess_error(tmp_path: Path) -> None:
    """Covers registry lines 144-145 — subprocess raises OSError."""
    from harness.skills.registry import PluginRegistry

    plugin = tmp_path / "p"
    _write_manifest(plugin, {"name": "n", "version": "1"})
    (plugin / ".git").mkdir()

    with patch("harness.skills.registry.subprocess.run", side_effect=OSError("no git")):
        m = PluginRegistry().read_manifest(plugin)
    assert m.commit_sha is None


def test_registry_rev_parse_returns_none_on_nonzero_exit(tmp_path: Path) -> None:
    """Covers registry line 147 — rev-parse returncode != 0."""
    from harness.skills.registry import PluginRegistry

    plugin = tmp_path / "p"
    _write_manifest(plugin, {"name": "n", "version": "1"})
    (plugin / ".git").mkdir()

    with patch(
        "harness.skills.registry.subprocess.run",
        return_value=subprocess.CompletedProcess(["git"], 128, stdout="", stderr="err"),
    ):
        m = PluginRegistry().read_manifest(plugin)
    assert m.commit_sha is None


def test_registry_rev_parse_returns_none_on_bad_sha_format(tmp_path: Path) -> None:
    """Covers registry line 151 — stdout not 40-hex."""
    from harness.skills.registry import PluginRegistry

    plugin = tmp_path / "p"
    _write_manifest(plugin, {"name": "n", "version": "1"})
    (plugin / ".git").mkdir()

    with patch(
        "harness.skills.registry.subprocess.run",
        return_value=subprocess.CompletedProcess(["git"], 0, stdout="not-a-sha\n", stderr=""),
    ):
        m = PluginRegistry().read_manifest(plugin)
    assert m.commit_sha is None


# ---------------------------------------------------------------------------
# harness.skills.installer — URL/path whitelist + subprocess failure paths
# ---------------------------------------------------------------------------


def test_installer_rejects_non_string_source(tmp_path: Path) -> None:
    """Covers installer line 34 — non-string source path."""
    from harness.skills.installer import _is_git_url_allowed

    assert _is_git_url_allowed(123) is False  # type: ignore[arg-type]
    assert _is_git_url_allowed(None) is False  # type: ignore[arg-type]


def test_installer_rejects_oversized_url() -> None:
    from harness.skills.installer import _is_git_url_allowed

    too_long = "https://example.com/" + ("a" * 2048)
    assert _is_git_url_allowed(too_long) is False


def test_installer_rejects_non_ascii_url() -> None:
    """Covers installer lines 46-47 — UnicodeEncodeError path."""
    from harness.skills.installer import _is_git_url_allowed

    assert _is_git_url_allowed("https://example.com/中文.git") is False


def test_installer_rejects_https_without_host() -> None:
    """Covers installer line 59 — https missing host or path."""
    from harness.skills.installer import _is_git_url_allowed

    # urlparse yields empty hostname for "https:///foo"
    assert _is_git_url_allowed("https:///path") is False
    # Missing path
    assert _is_git_url_allowed("https://example.com") is False


@pytest.mark.parametrize(
    "bad",
    [
        "git@",  # no split
        "git@host",  # no colon after host
        "git@:path",  # empty host
        "git@host:",  # empty path
    ],
)
def test_installer_rejects_malformed_git_at_urls(bad: str) -> None:
    """Covers installer lines 64-73 — git@host:path edge cases."""
    from harness.skills.installer import _is_git_url_allowed

    assert _is_git_url_allowed(bad) is False


def test_installer_accepts_valid_git_at_url() -> None:
    """Covers the success branch for git@host:path (line 73)."""
    from harness.skills.installer import _is_git_url_allowed

    assert _is_git_url_allowed("git@github.com:org/repo.git") is True


def test_installer_rejects_empty_target_dir(tmp_path: Path) -> None:
    """Covers installer line 85 — target_dir empty."""
    from harness.skills.installer import _validate_target_dir
    from harness.skills.errors import TargetPathEscapeError

    wd = tmp_path / "wd"
    wd.mkdir()
    with pytest.raises(TargetPathEscapeError):
        _validate_target_dir("", wd)
    with pytest.raises(TargetPathEscapeError):
        _validate_target_dir(None, wd)  # type: ignore[arg-type]


def test_installer_rejects_backslash_absolute_target(tmp_path: Path) -> None:
    """Covers installer line 87/90 — Windows-style absolute target."""
    from harness.skills.installer import _validate_target_dir
    from harness.skills.errors import TargetPathEscapeError

    wd = tmp_path / "wd"
    wd.mkdir()
    with pytest.raises(TargetPathEscapeError):
        _validate_target_dir("\\absolute\\path", wd)


def test_installer_unsupported_kind_raises(tmp_path: Path) -> None:
    """Covers installer line 152 — unknown kind fall-through.

    SkillsInstallRequest pydantic model restricts Literal, so we bypass it
    by constructing a direct argument-object that only carries the kind
    attribute the installer reads.
    """
    from harness.skills.installer import SkillsInstaller
    from harness.skills.errors import GitUrlRejectedError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()

    class _BogusReq:
        kind = "nope"
        source = "https://x.y/z.git"
        target_dir = "plugins/ltfa"

    with pytest.raises(GitUrlRejectedError):
        SkillsInstaller().install(_BogusReq(), workdir=wd)  # type: ignore[arg-type]


def test_installer_local_kind_rejects_relative_source(tmp_path: Path) -> None:
    """Covers installer line 145 — local source not absolute existing dir."""
    from harness.skills import SkillsInstaller, SkillsInstallRequest
    from harness.skills.errors import GitUrlRejectedError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()

    req = SkillsInstallRequest(
        kind="local",
        source="./relative/dir",
        target_dir="plugins/ltfa",
    )
    with pytest.raises(GitUrlRejectedError):
        SkillsInstaller().install(req, workdir=wd)


def test_installer_local_kind_rejects_when_target_exists(tmp_path: Path) -> None:
    """Covers installer line 246 — local copy target already present."""
    from harness.skills import SkillsInstaller, SkillsInstallRequest
    from harness.skills.errors import GitSubprocessError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    dst = wd / "plugins" / "ltfa"
    dst.mkdir()

    bundle = tmp_path / "bundle"
    _write_manifest(bundle, {"name": "n", "version": "1"})

    req = SkillsInstallRequest(
        kind="local",
        source=str(bundle),
        target_dir="plugins/ltfa",
    )
    with pytest.raises(GitSubprocessError):
        SkillsInstaller().install(req, workdir=wd)


def test_installer_local_kind_wraps_copytree_oserror(tmp_path: Path) -> None:
    """Covers installer lines 250-251 — shutil.copytree OSError path."""
    from harness.skills import SkillsInstaller, SkillsInstallRequest
    from harness.skills.errors import GitSubprocessError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()

    bundle = tmp_path / "bundle"
    _write_manifest(bundle, {"name": "n", "version": "1"})

    req = SkillsInstallRequest(
        kind="local",
        source=str(bundle),
        target_dir="plugins/ltfa",
    )
    with patch("harness.skills.installer.shutil.copytree", side_effect=OSError("boom")):
        with pytest.raises(GitSubprocessError):
            SkillsInstaller().install(req, workdir=wd)


def test_installer_clone_target_already_exists(tmp_path: Path) -> None:
    """Covers installer line 209 — clone target already present."""
    from harness.skills import SkillsInstaller, SkillsInstallRequest
    from harness.skills.errors import GitSubprocessError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    (wd / "plugins" / "ltfa").mkdir()

    req = SkillsInstallRequest(
        kind="clone",
        source="https://github.com/org/ltfa.git",
        target_dir="plugins/ltfa",
    )
    with patch("harness.skills.installer.subprocess.run") as mock_run:
        with pytest.raises(GitSubprocessError):
            SkillsInstaller().install(req, workdir=wd)
        mock_run.assert_not_called()


def test_installer_clone_subprocess_error_is_wrapped(tmp_path: Path) -> None:
    """Covers installer lines 228-229 — subprocess OSError."""
    from harness.skills import SkillsInstaller, SkillsInstallRequest
    from harness.skills.errors import GitSubprocessError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()

    req = SkillsInstallRequest(
        kind="clone",
        source="https://github.com/org/ltfa.git",
        target_dir="plugins/ltfa",
    )
    with patch("harness.skills.installer.subprocess.run", side_effect=OSError("nope")):
        with pytest.raises(GitSubprocessError):
            SkillsInstaller().install(req, workdir=wd)


def test_installer_clone_nonzero_exit_cleans_up_and_raises(tmp_path: Path) -> None:
    """Covers installer lines 232-235 — rc != 0 with partial dir cleanup."""
    from harness.skills import SkillsInstaller, SkillsInstallRequest
    from harness.skills.errors import GitSubprocessError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()

    def fail_clone(argv, **kwargs):
        target = Path(argv[-1])
        # simulate half-cloned state
        target.mkdir(parents=True, exist_ok=True)
        (target / "partial.txt").write_text("x", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 128, stdout="", stderr="fatal: nope\n")

    req = SkillsInstallRequest(
        kind="clone",
        source="https://github.com/org/ltfa.git",
        target_dir="plugins/ltfa",
    )
    with patch("harness.skills.installer.subprocess.run", side_effect=fail_clone):
        with pytest.raises(GitSubprocessError):
            SkillsInstaller().install(req, workdir=wd)

    # clean-up occurred
    assert not (wd / "plugins" / "ltfa").exists()


def test_installer_pull_target_not_under_plugins(tmp_path: Path) -> None:
    """Covers installer line 173 — pull target escapes plugins/."""
    from harness.skills import SkillsInstaller
    from harness.skills.errors import TargetPathEscapeError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    outside = wd / "outside"
    outside.mkdir()
    (outside / ".git").mkdir()

    with pytest.raises(TargetPathEscapeError):
        SkillsInstaller().pull(str(outside), workdir=wd)


def test_installer_pull_accepts_relative_and_resolves(tmp_path: Path) -> None:
    """Covers installer line 168 — relative pull target resolves under plugins/."""
    from harness.skills import SkillsInstaller

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    target = wd / "plugins" / "ltfa"
    target.mkdir()
    (target / ".git").mkdir()
    _write_manifest(target, {"name": "n", "version": "1"})

    def fake_run(argv, **kwargs):
        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout="a" * 40 + "\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="Already up to date.\n", stderr="")

    with patch("harness.skills.installer.subprocess.run", side_effect=fake_run):
        result = SkillsInstaller().pull("plugins/ltfa", workdir=wd)
    assert result.ok is True


def test_installer_pull_subprocess_os_error(tmp_path: Path) -> None:
    """Covers installer lines 188-189 — pull OSError wrap."""
    from harness.skills import SkillsInstaller
    from harness.skills.errors import GitSubprocessError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    target = wd / "plugins" / "ltfa"
    target.mkdir()
    (target / ".git").mkdir()

    with patch("harness.skills.installer.subprocess.run", side_effect=OSError("boom")):
        with pytest.raises(GitSubprocessError):
            SkillsInstaller().pull(str(target), workdir=wd)


def test_installer_pull_nonzero_exit_raises(tmp_path: Path) -> None:
    """Covers installer lines 190-192 — rc != 0 raises GitSubprocessError."""
    from harness.skills import SkillsInstaller
    from harness.skills.errors import GitSubprocessError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    target = wd / "plugins" / "ltfa"
    target.mkdir()
    (target / ".git").mkdir()

    with patch(
        "harness.skills.installer.subprocess.run",
        return_value=subprocess.CompletedProcess(
            ["git"], 1, stdout="", stderr="fatal: diverged\nline2\n"
        ),
    ):
        with pytest.raises(GitSubprocessError):
            SkillsInstaller().pull(str(target), workdir=wd)


def test_installer_pull_target_without_git_dir(tmp_path: Path) -> None:
    """Covers installer line 177 — pull target missing .git/."""
    from harness.skills import SkillsInstaller
    from harness.skills.errors import TargetPathEscapeError

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    target = wd / "plugins" / "ltfa"
    target.mkdir()
    # NO .git/

    with pytest.raises(TargetPathEscapeError):
        SkillsInstaller().pull(str(target), workdir=wd)


# ---------------------------------------------------------------------------
# harness.api.skills — REST layer error branches
# ---------------------------------------------------------------------------


def _set_workdir(app_, path) -> None:
    """注入 app.state.workdir（替代旧 HARNESS_WORKDIR env）。"""
    app_.state.workdir = str(path) if path is not None else None


def _clear_workdir(app_) -> None:
    if hasattr(app_.state, "workdir"):
        try:
            delattr(app_.state, "workdir")
        except AttributeError:
            pass


@pytest.fixture
def app_client_without_workdir():
    from harness.api import app

    _clear_workdir(app)
    with TestClient(app) as client:
        yield client
    _clear_workdir(app)


def test_api_skills_missing_workdir_returns_400(app_client_without_workdir) -> None:
    """workdir 未配置 → 400 workdir_not_selected。"""
    resp = app_client_without_workdir.post(
        "/api/skills/install",
        json={"kind": "clone", "source": "https://github.com/org/x.git", "target_dir": "plugins/x"},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "workdir_not_selected"


def test_api_skills_workdir_pointing_at_non_dir_returns_400(tmp_path: Path) -> None:
    """app.state.workdir 指向非目录 → 400 invalid_workdir。"""
    from harness.api import app

    bogus = tmp_path / "not_a_dir"
    bogus.write_text("", encoding="utf-8")
    _set_workdir(app, bogus)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/install",
                json={
                    "kind": "clone",
                    "source": "https://github.com/org/x.git",
                    "target_dir": "plugins/x",
                },
            )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert isinstance(detail, dict)
        assert detail.get("error_code") == "invalid_workdir"
    finally:
        _clear_workdir(app)


def test_api_skills_install_git_subprocess_error_returns_409(tmp_path: Path) -> None:
    """Covers api/skills lines 60-61 — GitSubprocessError → 409."""
    from harness.api import app

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    (wd / "plugins" / "ltfa").mkdir()  # force target-exists GitSubprocessError

    _set_workdir(app, wd)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/install",
                json={
                    "kind": "clone",
                    "source": "https://github.com/org/ltfa.git",
                    "target_dir": "plugins/ltfa",
                },
            )
        assert resp.status_code == 409
        assert "git" in resp.json()["detail"]
    finally:
        _clear_workdir(app)


def test_api_skills_pull_happy_path(tmp_path: Path) -> None:
    """Covers api/skills lines 66-75 — POST /api/skills/pull happy path."""
    from harness.api import app

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    target = wd / "plugins" / "ltfa"
    target.mkdir()
    (target / ".git").mkdir()
    _write_manifest(target, {"name": "n", "version": "1"})

    _set_workdir(app, wd)

    def fake_run(argv, **kwargs):
        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout="c" * 40 + "\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="Already up to date.\n", stderr="")

    try:
        with patch("harness.skills.installer.subprocess.run", side_effect=fake_run):
            with patch("harness.skills.registry.subprocess.run", side_effect=fake_run):
                with TestClient(app) as client:
                    resp = client.post(
                        "/api/skills/pull",
                        json={"kind": "pull", "source": "", "target_dir": "plugins/ltfa"},
                    )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
    finally:
        _clear_workdir(app)


def test_api_skills_pull_invalid_target_returns_400(tmp_path: Path) -> None:
    """Covers api/skills lines 76-77 — TargetPathEscapeError → 400."""
    from harness.api import app

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    _set_workdir(app, wd)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/pull",
                json={"kind": "pull", "source": "", "target_dir": "../escape"},
            )
        assert resp.status_code == 400
    finally:
        _clear_workdir(app)


def test_api_skills_pull_run_lock_returns_409(tmp_path: Path) -> None:
    """Covers api/skills lines 78-79 — SkillsInstallBusyError on pull → 409."""
    from harness.api import app

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    target = wd / "plugins" / "ltfa"
    target.mkdir()
    (target / ".git").mkdir()
    (wd / ".harness" / "run.lock").write_text("", encoding="utf-8")

    _set_workdir(app, wd)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/pull",
                json={"kind": "pull", "source": "", "target_dir": "plugins/ltfa"},
            )
        assert resp.status_code == 409
    finally:
        _clear_workdir(app)


def test_api_skills_pull_git_subprocess_error_returns_409(tmp_path: Path) -> None:
    """Covers api/skills lines 80-81 — GitSubprocessError on pull → 409."""
    from harness.api import app

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    target = wd / "plugins" / "ltfa"
    target.mkdir()
    (target / ".git").mkdir()
    _write_manifest(target, {"name": "n", "version": "1"})

    _set_workdir(app, wd)

    try:
        with patch("harness.skills.installer.subprocess.run", side_effect=OSError("boom")):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/skills/pull",
                    json={"kind": "pull", "source": "", "target_dir": "plugins/ltfa"},
                )
        assert resp.status_code == 409
    finally:
        _clear_workdir(app)


# ---------------------------------------------------------------------------
# harness.env.isolator — sweep edge paths (line 140-141, 174)
# ---------------------------------------------------------------------------


def test_isolator_module_importable() -> None:
    """Smoke check — ensure harness.env.isolator is importable.

    Mainline paths are covered by test_f10_environment_isolator.py; this
    supplement only needs to keep the module loaded. Lines 140-141 / 174
    are OS-error fallbacks under shutil.copytree failure and exist to
    fence against platform-specific stat issues — they are exercised only
    when host FS returns stat-error mid-iteration, which is not reliably
    reproducible in pytest; we tolerate them as known boundary skips.
    """
    import harness.env.isolator as m

    assert hasattr(m, "EnvironmentIsolator")


__all__: list[str] = []
