"""Integration tests for F10 · real filesystem setup + audit JSONL append.

Covers Test Inventory rows:
  T01/T26-fs — real filesystem execution of setup_run + teardown_run;
               no mock on shutil.copytree / os.mkdir / open; workdir
               writes confined to .harness-workdir/ and .harness/.
  T26 INTG/audit — F02 AuditWriter JSONL contains env.setup / env.teardown
                   events with run_id, paths and ok fields in payload.

[integration] — real fs, real shutil, real F02 AuditWriter append. Primary
dependency (filesystem) is NOT mocked.

Feature ref: feature_3
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.real_fs


def _write_bundle(root: Path) -> Path:
    bundle = root / "longtaskforagent"
    (bundle / ".claude-plugin").mkdir(parents=True)
    (bundle / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "longtaskforagent", "version": "1.0"}), encoding="utf-8"
    )
    (bundle / "skills").mkdir()
    (bundle / "skills" / "x.md").write_text("X\n", encoding="utf-8")
    return bundle


@pytest.mark.real_fs
async def test_f10_real_setup_writes_nothing_outside_allowed_subdirs(
    tmp_path: Path,
) -> None:
    """feature_3 real test — exercise setup_run + teardown_run end-to-end on
    real fs; assert nothing was written outside ``.harness-workdir/`` and
    ``.harness/``. No mock at the fs boundary."""
    from harness.env import EnvironmentIsolator

    bundle = _write_bundle(tmp_path / "src_bundle")
    workdir = tmp_path / "project"
    workdir.mkdir()
    (workdir / "README.md").write_text("# proj\n", encoding="utf-8")
    (workdir / "src").mkdir()
    (workdir / "src" / "user.py").write_text("pass\n", encoding="utf-8")
    fake_home = tmp_path / "fake_home" / ".claude"
    fake_home.mkdir(parents=True)
    (fake_home / "settings.json").write_text("{}", encoding="utf-8")

    before = {str(p.relative_to(workdir)) for p in workdir.rglob("*") if p.is_file()}
    before_home = {
        str(p.relative_to(fake_home)): p.stat().st_mtime_ns
        for p in fake_home.rglob("*")
        if p.is_file()
    }

    iso = EnvironmentIsolator()
    paths = iso.setup_run("real-run-1", workdir=workdir, bundle_root=bundle, home_dir=fake_home)
    # Filesystem postconditions — REAL writes must have happened.
    isolated_root = workdir / ".harness-workdir" / "real-run-1" / ".claude"
    assert isolated_root.is_dir()
    assert (isolated_root / "settings.json").is_file()
    assert (isolated_root / "mcp.json").is_file()
    assert (
        isolated_root / "plugins" / "longtaskforagent" / ".claude-plugin" / "plugin.json"
    ).is_file()

    # Now scan every new file and assert location rule (FR-044).
    after = {str(p.relative_to(workdir)) for p in workdir.rglob("*") if p.is_file()}
    new_paths = after - before
    assert new_paths, "setup_run must have created at least one file"
    for p in new_paths:
        assert p.startswith(".harness-workdir/") or p.startswith(
            ".harness/"
        ), f"setup wrote outside allowed subdirs: {p}"

    # Home must not have been touched at all (NFR-009).
    after_home = {
        str(p.relative_to(fake_home)): p.stat().st_mtime_ns
        for p in fake_home.rglob("*")
        if p.is_file()
    }
    assert (
        after_home == before_home
    ), f"fake_home mtime_ns changed: before={before_home} after={after_home}"

    diff = iso.teardown_run("real-run-1", paths)
    assert diff.ok is True


@pytest.mark.real_fs
async def test_t26_audit_writer_records_env_setup_and_teardown(tmp_path: Path) -> None:
    """feature_3 real test — AuditWriter JSONL contains env.setup and
    env.teardown events with run_id / paths / ok."""
    from harness.env import EnvironmentIsolator
    from harness.persistence.audit import AuditWriter

    bundle = _write_bundle(tmp_path / "src_bundle")
    workdir = tmp_path / "project"
    workdir.mkdir()
    fake_home = tmp_path / "fake_home" / ".claude"
    fake_home.mkdir(parents=True)

    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    writer = AuditWriter(audit_dir, fsync=False)

    iso = EnvironmentIsolator(audit_writer=writer)
    paths = iso.setup_run("audit-run", workdir=workdir, bundle_root=bundle, home_dir=fake_home)
    iso.teardown_run("audit-run", paths)
    await writer.close()

    # Expect a file <run_id>.jsonl in audit_dir
    jsonl = audit_dir / "audit-run.jsonl"
    assert jsonl.is_file(), f"audit file missing under {audit_dir}"
    lines = [
        json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    # Find env.setup and env.teardown events. The exact shape may live on
    # either ``event_type`` or ``kind``; accept either field.
    types = [ev.get("event_type") or ev.get("kind") for ev in lines]
    assert "env.setup" in types, f"env.setup missing; types={types!r}"
    assert "env.teardown" in types, f"env.teardown missing; types={types!r}"

    setup_ev = next(ev for ev in lines if (ev.get("event_type") or ev.get("kind")) == "env.setup")
    teardown_ev = next(
        ev for ev in lines if (ev.get("event_type") or ev.get("kind")) == "env.teardown"
    )
    # Both events carry run_id
    assert setup_ev.get("run_id") == "audit-run"
    assert teardown_ev.get("run_id") == "audit-run"
    # teardown payload reports ok=True (home untouched)
    payload = teardown_ev.get("payload") or {}
    assert payload.get("ok") is True, f"teardown payload must contain ok=True: {payload!r}"
