"""Feature #24 B8-P2 — repo-root residual directory regression (REAL FS).

Traces To
=========
  B8-P2  init_project guard residual cleanup / FR-001 SEC共轨   (INTG/fs)
  §6 风险与回滚策略 B8 — 「`--version/` 和 `status/` 两 untracked
       目录在 TDD 阶段由实施者 rm -rf 删除」

This test is a **real_fs** integration test: it inspects the REAL repository
working tree, not a sandboxed tmp_path. It MUST FAIL today because the two
untracked directories are present.

Why a real test (not unit):
  - The bug surface is the literal repo-root directory listing as observed by
    PyInstaller `--add-data .` and by `git status -u`. A unit test against
    tmp_path would not exercise this surface.
  - Per `feature-list.json#real_test.marker_pattern`, a real test must be
    discoverable via `@pytest.mark.real_fs` AND must not mock the primary
    dependency (filesystem).

Feature ref: feature 24
"""

from __future__ import annotations

import pathlib

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.mark.real_fs
def test_b8_p2_no_dash_version_dir_at_repo_root() -> None:
    """`--version/` directory must not exist at repo root."""
    bad = REPO_ROOT / "--version"
    assert not bad.exists(), (
        f"Repo-root residual directory {bad} must be removed (B8 cleanup). "
        f"Currently exists; would be packaged by PyInstaller."
    )


@pytest.mark.real_fs
def test_b8_p2_no_status_dir_at_repo_root() -> None:
    """`status/` directory must not exist at repo root."""
    bad = REPO_ROOT / "status"
    assert not bad.exists(), (
        f"Repo-root residual directory {bad} must be removed (B8 cleanup). "
        f"Currently exists; would be packaged by PyInstaller."
    )
