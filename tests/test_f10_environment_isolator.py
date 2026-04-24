"""Unit tests for F10 · EnvironmentIsolator + HomeMtimeGuard + WorkdirScopeGuard.

Covers Test Inventory (docs/features/3-f10-environment-isolation-skills-install.md §7):
  T01 FUNC/happy    — setup_run returns IsolatedPaths + copies bundle physically
  T03 FUNC/happy    — workdir scope guard confirms no stray writes
  T06 FUNC/happy    — teardown_run produces empty HomeMtimeDiff (NFR-009)
  T07 FUNC/error    — run_id traversal rejected (RunIdInvalidError)
  T08 FUNC/error    — missing workdir (WorkdirNotFoundError)
  T09 FUNC/error    — missing bundle manifest (BundleNotFoundError)
  T10 FUNC/error    — read-only workdir → IsolationSetupError
  T14 SEC/path-traversal — scope guard detects __injected__.tmp
  T16 BNDRY/run_id-max — 64 char accepted, 65 rejected, empty rejected
  T17 BNDRY/mtime-precision — nanosecond mtime diff detected (NFR-009)

All tests here are UT — system boundaries (fs) use ``tmp_path`` real fs; no
mock on the subject under test. Every test MUST FAIL in Red phase because
``harness.env`` does not yet exist.

Feature ref: feature_3
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers (fixtures)
# ---------------------------------------------------------------------------


def _make_bundle(root: Path, name: str = "longtaskforagent") -> Path:
    """Create a minimal valid bundle with .claude-plugin/plugin.json and
    a few sibling files."""
    bundle = root / name
    (bundle / ".claude-plugin").mkdir(parents=True)
    manifest = {
        "name": name,
        "version": "0.0.1-test",
        "description": "F10 red-phase fixture bundle",
    }
    (bundle / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # a secondary file to prove recursive copy
    (bundle / "skills").mkdir()
    (bundle / "skills" / "hello.md").write_text("# hello\n", encoding="utf-8")
    return bundle


def _make_workdir(tmp_path: Path) -> Path:
    wd = tmp_path / "project"
    wd.mkdir()
    # one file inside "user code" simulating a normal project layout
    (wd / "README.md").write_text("# project\n", encoding="utf-8")
    (wd / "src").mkdir()
    (wd / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    return wd


def _make_fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "fake_home" / ".claude"
    home.mkdir(parents=True)
    (home / "settings.json").write_text('{"ok": true}\n', encoding="utf-8")
    (home / "mcp.json").write_text("{}\n", encoding="utf-8")
    (home / "plugins").mkdir()
    (home / "plugins" / "marker").write_text("marker\n", encoding="utf-8")
    return home


# ---------------------------------------------------------------------------
# T01 · FUNC/happy — setup_run returns IsolatedPaths + physical copy
# Traces To: FR-043 AC-1 · §Interface Contract setup_run postcond
#            §Design Alignment seq msg#1-6
# ---------------------------------------------------------------------------


def test_t01_setup_run_produces_isolated_paths_and_physical_copy(tmp_path: Path) -> None:
    """[unit] setup_run returns IsolatedPaths with correct schema and performs
    physical copy (not symlink) of bundle."""
    # Import inside the test — module does not exist in Red phase.
    from harness.env import EnvironmentIsolator, IsolatedPaths

    bundle = _make_bundle(tmp_path / "bundle_src")
    workdir = _make_workdir(tmp_path)
    fake_home = _make_fake_home(tmp_path)

    isolator = EnvironmentIsolator()
    paths = isolator.setup_run(
        "run-001",
        workdir=workdir,
        bundle_root=bundle,
        home_dir=fake_home,
    )

    # Schema checks — each field must equal a concrete deterministic path.
    assert isinstance(paths, IsolatedPaths)
    isolated_root = workdir / ".harness-workdir" / "run-001"
    assert Path(paths.cwd) == workdir
    assert Path(paths.plugin_dir) == isolated_root / ".claude" / "plugins"
    assert Path(paths.settings_path) == isolated_root / ".claude" / "settings.json"
    assert Path(paths.mcp_config_path) == isolated_root / ".claude" / "mcp.json"

    # Filesystem postconditions.
    assert (isolated_root / ".claude").is_dir()
    # settings.json parses as JSON with a "permissions" top-level key.
    settings = json.loads(Path(paths.settings_path).read_text(encoding="utf-8"))
    assert "permissions" in settings
    # mcp.json exists and is valid JSON
    mcp = json.loads(Path(paths.mcp_config_path).read_text(encoding="utf-8"))
    assert isinstance(mcp, dict)

    # Plugin bundle under plugins/longtaskforagent — MUST be a physical copy,
    # not a symlink or junction.
    dst_bundle = Path(paths.plugin_dir) / "longtaskforagent"
    assert dst_bundle.is_dir()
    assert not dst_bundle.is_symlink(), "plugin dir must be physical copy, not symlink"
    dst_manifest = dst_bundle / ".claude-plugin" / "plugin.json"
    assert dst_manifest.is_file()
    assert not dst_manifest.is_symlink()
    # the recursive sub-file must be copied too
    assert (dst_bundle / "skills" / "hello.md").read_text(encoding="utf-8") == "# hello\n"


# ---------------------------------------------------------------------------
# T02 · FUNC/happy — manifest sha256 == source (see test_f10_plugin_registry)
# T02 here: sanity post-setup_run sha equality
# ---------------------------------------------------------------------------


def test_t02_setup_run_manifest_sha256_matches_source(tmp_path: Path) -> None:
    """After setup_run, the copy's plugin.json sha256 equals the source's."""
    import hashlib

    from harness.env import EnvironmentIsolator

    bundle = _make_bundle(tmp_path / "bundle_src")
    workdir = _make_workdir(tmp_path)
    fake_home = _make_fake_home(tmp_path)

    src_bytes = (bundle / ".claude-plugin" / "plugin.json").read_bytes()
    src_sha = hashlib.sha256(src_bytes).hexdigest()

    isolator = EnvironmentIsolator()
    paths = isolator.setup_run("run-sha", workdir=workdir, bundle_root=bundle, home_dir=fake_home)
    dst_bytes = (
        Path(paths.plugin_dir) / "longtaskforagent" / ".claude-plugin" / "plugin.json"
    ).read_bytes()
    dst_sha = hashlib.sha256(dst_bytes).hexdigest()

    assert dst_sha == src_sha, "physical copy must preserve manifest bytes exactly"


# ---------------------------------------------------------------------------
# T03 · FUNC/happy — WorkdirScopeGuard.assert_scope, ok=True when only .harness*
# Traces To: FR-044 AC-1 · §Interface Contract assert_scope postcond
# ---------------------------------------------------------------------------


def test_t03_workdir_scope_guard_ok_when_only_harness_subdirs_changed(tmp_path: Path) -> None:
    """[unit] simulate a clean run: only .harness-workdir/ appears → ok=True."""
    from harness.env import WorkdirScopeGuard

    wd = _make_workdir(tmp_path)
    # snapshot the pre-state file set (relative paths, recursive).
    before = {str(p.relative_to(wd)) for p in wd.rglob("*") if p.is_file()}

    # simulate an isolated setup: only a .harness-workdir/<id>/... tree is added.
    (wd / ".harness-workdir" / "r1" / ".claude").mkdir(parents=True)
    (wd / ".harness-workdir" / "r1" / ".claude" / "settings.json").write_text(
        "{}", encoding="utf-8"
    )
    # user skill wrote inside src/ — that's their legitimate write
    (wd / "src" / "user_wrote.py").write_text("x=1\n", encoding="utf-8")

    report = WorkdirScopeGuard().assert_scope(
        wd,
        before=before,
        after=None,  # guard re-scans
    )
    # guard considers .harness-workdir/** within allowed_subdirs; user_wrote.py
    # is foreign to before-set but NOT produced by Harness: guard reports it
    # verbatim and the caller (Orchestrator) differentiates harness-owned vs
    # tool-produced. The contract here: anything outside allowed_subdirs that
    # did not exist in `before` appears in `unexpected_new`.
    assert report.ok is False
    assert "src/user_wrote.py" in report.unexpected_new
    # critically, .harness-workdir/r1/... must NEVER leak into unexpected_new.
    for p in report.unexpected_new:
        assert not p.startswith(".harness-workdir"), f"allowed path leaked: {p}"
        assert not p.startswith(".harness/"), f"allowed path leaked: {p}"


def test_t03b_workdir_scope_guard_ok_true_when_nothing_new_outside_allowed(
    tmp_path: Path,
) -> None:
    """ok=True path: only .harness subtree appears, nothing else new."""
    from harness.env import WorkdirScopeGuard

    wd = _make_workdir(tmp_path)
    before = {str(p.relative_to(wd)) for p in wd.rglob("*") if p.is_file()}
    (wd / ".harness").mkdir()
    (wd / ".harness" / "log.jsonl").write_text("{}\n", encoding="utf-8")

    report = WorkdirScopeGuard().assert_scope(wd, before=before)
    assert report.ok is True
    assert report.unexpected_new == []


# ---------------------------------------------------------------------------
# T06 · FUNC/happy — NFR-009 mtime diff empty across setup+teardown
# Traces To: NFR-009 · §Interface Contract teardown_run postcond
# ---------------------------------------------------------------------------


def test_t06_teardown_run_returns_empty_home_mtime_diff(tmp_path: Path) -> None:
    """[unit] simulate a full setup→teardown. ~/.claude (fake_home) is never
    touched by Harness → diff is empty and ok=True."""
    from harness.env import EnvironmentIsolator, HomeMtimeDiff

    bundle = _make_bundle(tmp_path / "bundle_src")
    workdir = _make_workdir(tmp_path)
    fake_home = _make_fake_home(tmp_path)

    isolator = EnvironmentIsolator()
    paths = isolator.setup_run(
        "run-teardown", workdir=workdir, bundle_root=bundle, home_dir=fake_home
    )
    diff = isolator.teardown_run("run-teardown", paths)

    assert isinstance(diff, HomeMtimeDiff)
    assert diff.ok is True
    assert list(diff.changed_files) == []
    assert list(diff.added_files) == []
    assert list(diff.removed_files) == []


# ---------------------------------------------------------------------------
# T07 · FUNC/error — run_id traversal rejected
# Traces To: §Interface Contract Raises: RunIdInvalidError
# ---------------------------------------------------------------------------


def test_t07_setup_run_rejects_traversal_run_id(tmp_path: Path) -> None:
    """run_id containing path traversal → RunIdInvalidError, no dirs created."""
    from harness.env import EnvironmentIsolator, RunIdInvalidError

    bundle = _make_bundle(tmp_path / "bundle_src")
    workdir = _make_workdir(tmp_path)
    fake_home = _make_fake_home(tmp_path)

    isolator = EnvironmentIsolator()
    with pytest.raises(RunIdInvalidError) as excinfo:
        isolator.setup_run(
            "../../evil",
            workdir=workdir,
            bundle_root=bundle,
            home_dir=fake_home,
        )
    # error message must signal the invalidity
    assert "run_id" in str(excinfo.value).lower()
    # no .harness-workdir/ must have been created (no partial state)
    assert not (workdir / ".harness-workdir").exists()


@pytest.mark.parametrize(
    "bad",
    [
        "a/b",  # slash
        "a\\b",  # backslash
        "has space",  # whitespace
        "weird#tag",  # invalid char
        "unicodé-id",  # non-ASCII
    ],
)
def test_t07b_setup_run_rejects_various_illegal_run_ids(tmp_path: Path, bad: str) -> None:
    from harness.env import EnvironmentIsolator, RunIdInvalidError

    bundle = _make_bundle(tmp_path / "bundle_src")
    workdir = _make_workdir(tmp_path)
    fake_home = _make_fake_home(tmp_path)

    isolator = EnvironmentIsolator()
    with pytest.raises(RunIdInvalidError):
        isolator.setup_run(bad, workdir=workdir, bundle_root=bundle, home_dir=fake_home)


# ---------------------------------------------------------------------------
# T08 · FUNC/error — workdir missing → WorkdirNotFoundError
# ---------------------------------------------------------------------------


def test_t08_setup_run_raises_workdir_not_found(tmp_path: Path) -> None:
    from harness.env import EnvironmentIsolator, WorkdirNotFoundError

    bundle = _make_bundle(tmp_path / "bundle_src")
    fake_home = _make_fake_home(tmp_path)
    missing = tmp_path / "nope" / "does" / "not" / "exist"
    assert not missing.exists()

    isolator = EnvironmentIsolator()
    with pytest.raises(WorkdirNotFoundError):
        isolator.setup_run("r1", workdir=missing, bundle_root=bundle, home_dir=fake_home)


# ---------------------------------------------------------------------------
# T09 · FUNC/error — bundle missing manifest → BundleNotFoundError
# ---------------------------------------------------------------------------


def test_t09_setup_run_raises_bundle_not_found(tmp_path: Path) -> None:
    from harness.env import BundleNotFoundError, EnvironmentIsolator

    workdir = _make_workdir(tmp_path)
    fake_home = _make_fake_home(tmp_path)
    empty_bundle = tmp_path / "empty_bundle"
    empty_bundle.mkdir()  # no .claude-plugin/plugin.json

    isolator = EnvironmentIsolator()
    with pytest.raises(BundleNotFoundError):
        isolator.setup_run("r1", workdir=workdir, bundle_root=empty_bundle, home_dir=fake_home)


# ---------------------------------------------------------------------------
# T10 · FUNC/error — read-only workdir → IsolationSetupError
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX chmod semantics only")
def test_t10_setup_run_raises_isolation_setup_error_on_readonly_workdir(
    tmp_path: Path,
) -> None:
    from harness.env import EnvironmentIsolator, IsolationSetupError

    bundle = _make_bundle(tmp_path / "bundle_src")
    fake_home = _make_fake_home(tmp_path)
    ro_workdir = tmp_path / "ro_project"
    ro_workdir.mkdir()
    (ro_workdir / "README.md").write_text("hi\n", encoding="utf-8")
    # strip write bits from owner and group — mkdir inside must fail
    os.chmod(ro_workdir, 0o500)
    try:
        isolator = EnvironmentIsolator()
        with pytest.raises(IsolationSetupError) as excinfo:
            isolator.setup_run(
                "r1",
                workdir=ro_workdir,
                bundle_root=bundle,
                home_dir=fake_home,
            )
        # error message must contain the failing subpath to aid debugging
        msg = str(excinfo.value)
        assert ".harness-workdir" in msg or "mkdir" in msg.lower()
    finally:
        os.chmod(ro_workdir, 0o700)  # restore for cleanup


# ---------------------------------------------------------------------------
# T14 · SEC/path-traversal — WorkdirScopeGuard detects injected tmp
# Traces To: FR-044 · §Interface Contract assert_scope
# ---------------------------------------------------------------------------


def test_t14_workdir_scope_guard_flags_injected_tmp_outside_allowed(tmp_path: Path) -> None:
    """Simulate a Harness bug writing outside .harness/ — guard must catch it."""
    from harness.env import WorkdirScopeGuard

    wd = _make_workdir(tmp_path)
    before = {str(p.relative_to(wd)) for p in wd.rglob("*") if p.is_file()}

    # Harness "accidentally" writes a stray tmp at the workdir root.
    (wd / "__injected__.tmp").write_text("oops\n", encoding="utf-8")

    report = WorkdirScopeGuard().assert_scope(wd, before=before)
    assert report.ok is False
    assert "__injected__.tmp" in report.unexpected_new


# ---------------------------------------------------------------------------
# T16 · BNDRY — run_id length bounds
# Traces To: §Boundary run_id 长度
# ---------------------------------------------------------------------------


def test_t16_run_id_length_bounds(tmp_path: Path) -> None:
    from harness.env import EnvironmentIsolator, RunIdInvalidError

    bundle = _make_bundle(tmp_path / "bundle_src")
    workdir = _make_workdir(tmp_path)
    fake_home = _make_fake_home(tmp_path)

    # 64 chars — accepted
    ok_id = "a" * 64
    iso = EnvironmentIsolator()
    paths = iso.setup_run(ok_id, workdir=workdir, bundle_root=bundle, home_dir=fake_home)
    assert (workdir / ".harness-workdir" / ok_id).is_dir()
    # do not leave residue for the next parametric — teardown
    iso.teardown_run(ok_id, paths)

    # 65 chars — rejected
    with pytest.raises(RunIdInvalidError):
        iso.setup_run("a" * 65, workdir=workdir, bundle_root=bundle, home_dir=fake_home)

    # empty — rejected
    with pytest.raises(RunIdInvalidError):
        iso.setup_run("", workdir=workdir, bundle_root=bundle, home_dir=fake_home)


# ---------------------------------------------------------------------------
# T17 · BNDRY — HomeMtimeGuard nanosecond precision
# Traces To: NFR-009 · §Interface Contract snapshot uses st_mtime_ns
# ---------------------------------------------------------------------------


def test_t17_home_mtime_guard_detects_nanosecond_change(tmp_path: Path) -> None:
    """[unit] snapshot → bump mtime by 1 ns → diff.ok == False and file listed.

    This is the wrong-impl probe: a buggy implementation using ``st_mtime``
    (seconds float) would lose a 1 ns difference and report ok=True.
    """
    from harness.env import HomeMtimeGuard

    home = tmp_path / "fake_home"
    home.mkdir()
    target = home / "a.txt"
    target.write_text("x\n", encoding="utf-8")

    guard = HomeMtimeGuard()
    before = guard.snapshot(home)
    # Bump mtime by exactly 1 nanosecond — forces the implementation to
    # compare st_mtime_ns rather than st_mtime (which rounds to 1s on EXT4).
    st = target.stat()
    new_ns = st.st_mtime_ns + 1
    os.utime(target, ns=(new_ns, new_ns))

    diff = guard.diff_against(before)
    assert diff.ok is False, "nanosecond mtime change must be detected"
    # the changed file must be reported
    changed_paths = {
        getattr(c, "path", c) if not isinstance(c, str) else c for c in diff.changed_files
    }
    assert "a.txt" in changed_paths


def test_t17b_home_mtime_guard_empty_snapshot_on_missing_home(tmp_path: Path) -> None:
    """snapshot on non-existent home → empty snapshot, not an error."""
    from harness.env import HomeMtimeGuard

    missing = tmp_path / "no_home_here"
    guard = HomeMtimeGuard()
    snap = guard.snapshot(missing)
    # entries dict must exist and be empty
    assert dict(snap.entries) == {}


__all__: list[str] = []
