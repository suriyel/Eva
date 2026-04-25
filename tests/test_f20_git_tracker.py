"""F20 · GitTracker non-repo failure mode unit test (T28).

[unit] — uses real git binary on tmp_path empty dir to exercise exit=128 path.
T27 / T29 (real repo + commits) live in tests/integration/test_f20_real_git.py.

Feature ref: feature_20

Traces To:
  T28 → FR-042 + IFR-005 GitError(code='not_a_repo') failure mode
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


# ---- T28 -------------------------------------------------------------------
async def test_t28_git_tracker_begin_in_non_git_repo_raises_git_error(tmp_path: Path) -> None:
    """T28 FUNC/error: begin(workdir without .git/) → GitError(code='not_a_repo'); exit=128 captured."""
    from harness.subprocess.git.tracker import GitError, GitTracker

    tracker = GitTracker()
    # tmp_path is empty (no .git/)
    assert not (tmp_path / ".git").exists()

    with pytest.raises(GitError) as excinfo:
        await tracker.begin(ticket_id="t-x", workdir=tmp_path)

    assert (
        excinfo.value.code == "not_a_repo"
    ), f"IFR-005 failure mode: expected code='not_a_repo'; got {excinfo.value.code!r}"
    # exit=128 from `git rev-parse HEAD` outside a repo
    assert excinfo.value.exit_code == 128
