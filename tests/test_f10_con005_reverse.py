"""F10 · T19 BNDRY/con-005-reverse — source bundle mtime unchanged.

Covers Test Inventory row:
  T19 BNDRY/con-005-reverse — source plugins/longtaskforagent/ (SkillsInstaller
       write-target) mtime_ns must NOT change across a full setup→teardown
       cycle. This is the reverse assertion of CON-005 constrained to the
       SOURCE bundle (copy under .harness-workdir/<run>/ is explicitly
       allowed to change — it is a per-run ephemeral copy).

Feature ref: feature_3
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _write_source_bundle(root: Path) -> Path:
    bundle = root / "longtaskforagent"
    (bundle / ".claude-plugin").mkdir(parents=True)
    (bundle / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "longtaskforagent", "version": "1"}), encoding="utf-8"
    )
    (bundle / "skills").mkdir()
    (bundle / "skills" / "a.md").write_text("A\n", encoding="utf-8")
    (bundle / "skills" / "b.md").write_text("B\n", encoding="utf-8")
    return bundle


def _snapshot_mtime_ns(root: Path) -> dict[str, int]:
    return {str(p.relative_to(root)): p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}


def test_t19_source_bundle_mtime_ns_unchanged_through_setup_teardown(tmp_path: Path) -> None:
    """[unit] run a full setup→teardown cycle; source bundle mtime_ns unchanged.

    Wrong-impl probes this catches:
      - impl accidentally writes into src instead of dst (reverse copytree)
      - impl updates manifest sha on source during read (opens in write mode)
      - impl triggers an auto-pull into the source as part of run lifecycle
    """
    from harness.env import EnvironmentIsolator

    src = _write_source_bundle(tmp_path / "bundle_src")
    workdir = tmp_path / "project"
    workdir.mkdir()
    fake_home = tmp_path / "fake_home" / ".claude"
    fake_home.mkdir(parents=True)

    before = _snapshot_mtime_ns(src)
    assert before, "pre-snapshot must be non-empty"

    iso = EnvironmentIsolator()
    paths = iso.setup_run("run-con005", workdir=workdir, bundle_root=src, home_dir=fake_home)
    # touch the COPY to prove that copy-side mutation does not propagate
    dst_manifest = Path(paths.plugin_dir) / "longtaskforagent" / ".claude-plugin" / "plugin.json"
    # bump dst mtime deliberately to prove isolation
    st = dst_manifest.stat()
    os.utime(dst_manifest, ns=(st.st_mtime_ns + 1000, st.st_mtime_ns + 1000))

    iso.teardown_run("run-con005", paths)

    after = _snapshot_mtime_ns(src)
    assert after.keys() == before.keys(), "no file may appear/disappear on source"
    for rel, before_ns in before.items():
        assert after[rel] == before_ns, (
            f"source file {rel} mtime_ns changed from {before_ns} to {after[rel]} — "
            "CON-005 reverse assertion failed"
        )
