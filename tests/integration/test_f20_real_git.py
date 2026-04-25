"""Integration tests for F20 · real git CLI subprocess (T27/T29) + filelock concurrency (T36).

[integration] — uses REAL git binary + REAL filesystem; spawns 2 OS processes for T36.

Feature ref: feature_20

Traces To:
  T27 → FR-042 AC-1 + Interface Contract `GitTracker.begin/end` + seq msg#9 + msg#16
  T29 → FR-042 + IAPI-013 real git rev-parse / git log subprocess
  T36 → NFR-016 + ATS INT-007 real filelock concurrency
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.real_cli, pytest.mark.asyncio]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "Harness Test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "Harness Test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


# ---- T27 -------------------------------------------------------------------
@pytest.mark.real_cli
async def test_t27_git_tracker_begin_end_records_2_commits(tmp_path: Path) -> None:
    """T27 FUNC/happy (feature_20): real git repo → begin → 2 commits → end → GitContext.commits length=2; head_after != head_before."""
    from harness.subprocess.git.tracker import GitTracker

    _git(["init", "-q"], tmp_path)
    _git(["commit", "--allow-empty", "-q", "-m", "root"], tmp_path)

    tracker = GitTracker()
    ctx_begin = await tracker.begin(ticket_id="t-1", workdir=tmp_path)
    assert ctx_begin.head_before is not None
    head_before = ctx_begin.head_before

    # 2 commits
    (tmp_path / "a.txt").write_text("a")
    _git(["add", "."], tmp_path)
    _git(["commit", "-q", "-m", "first"], tmp_path)
    (tmp_path / "b.txt").write_text("b")
    _git(["add", "."], tmp_path)
    _git(["commit", "-q", "-m", "second"], tmp_path)

    ctx_end = await tracker.end(ticket_id="t-1", workdir=tmp_path)
    assert ctx_end.head_after is not None
    assert ctx_end.head_after != head_before, "head must advance after 2 commits"
    assert (
        len(ctx_end.commits) == 2
    ), f"expected 2 commits; got {len(ctx_end.commits)}: {ctx_end.commits}"

    # Reverse-chrono — first element is most recent
    subjects = [c.subject for c in ctx_end.commits]
    assert subjects[0] == "second", f"DESC ordering broken; got {subjects}"
    assert subjects[1] == "first"


# ---- T29 -------------------------------------------------------------------
@pytest.mark.real_cli
async def test_t29_git_rev_parse_and_log_real_subprocess(tmp_path: Path) -> None:
    """T29 INTG/git (feature_20): real git rev-parse HEAD → 40-hex sha; git log --oneline → list[GitCommit]."""
    from harness.subprocess.git.tracker import GitTracker

    _git(["init", "-q"], tmp_path)
    _git(["commit", "--allow-empty", "-q", "-m", "root"], tmp_path)
    (tmp_path / "f.txt").write_text("x")
    _git(["add", "."], tmp_path)
    _git(["commit", "-q", "-m", "feat-x"], tmp_path)

    tracker = GitTracker()
    sha = await tracker.head_sha(workdir=tmp_path)
    assert isinstance(sha, str)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)

    log = await tracker.log_oneline(workdir=tmp_path, since=None)
    assert len(log) >= 2, f"expected ≥2 commits; got {len(log)}"
    assert all(len(c.sha) == 40 and c.subject for c in log)


# ---- T36 -------------------------------------------------------------------
@pytest.mark.real_cli
async def test_t36_concurrent_orchestrators_filelock_only_one_acquires(tmp_path: Path) -> None:
    """T36 INTG/concurrency (feature_20): 2 RunOrchestrator instances start_run on same workdir → exactly 1 succeeds, the other 409."""
    from harness.orchestrator.errors import RunStartError
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    _git(["init", "-q"], tmp_path)
    _git(["commit", "--allow-empty", "-q", "-m", "root"], tmp_path)

    orch1 = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch2 = RunOrchestrator.build_test_default(workdir=tmp_path)

    req = RunStartRequest(workdir=str(tmp_path))

    results = await asyncio.gather(
        orch1.start_run(req),
        orch2.start_run(req),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, BaseException)]
    failures = [r for r in results if isinstance(r, BaseException)]
    assert (
        len(successes) == 1
    ), f"exactly 1 must acquire; got {len(successes)} successes; results={results}"
    assert len(failures) == 1
    err = failures[0]
    assert isinstance(err, RunStartError)
    assert err.reason == "already_running"
    assert err.http_status == 409
