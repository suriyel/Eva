"""F23 · /api/git REST routes (wraps CommitListService / DiffLoader).

F22 RT03 / RT04 / IFR-005: when ``app.state.workdir`` is not a git repo
(``.git`` directory missing or ``git rev-parse`` exits non-zero), commits
endpoint returns 502 with ``{code: 'not_a_git_repo'}`` so the FE can render
``NotAGitRepoBanner``. The diff endpoint uses real ``git show`` output to
flag binary files via ``kind='binary' placeholder=true`` (FR-041 BNDRY).
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request

from harness.api.git import DiffNotFound, GitCommit


router = APIRouter()


def _resolve_workdir(request: Request) -> Path | None:
    raw = getattr(request.app.state, "workdir", None)
    return Path(raw) if raw else None


def _is_git_repo(workdir: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


@router.get("/api/git/commits")
async def get_commits(
    request: Request,
    run_id: str | None = Query(default=None),
    feature_id: str | None = Query(default=None),
    limit: int | None = Query(default=None),
) -> Any:
    workdir = _resolve_workdir(request)
    if workdir is None:
        return []
    if not _is_git_repo(workdir):
        raise HTTPException(
            status_code=502,
            detail={
                "code": "not_a_git_repo",
                "message": f"workdir is not a git repository: {workdir}",
            },
        )
    svc = getattr(request.app.state, "commit_list_service", None)
    rows: list[GitCommit] = (
        await svc.list_commits(run_id=run_id, feature_id=feature_id) if svc else []
    )
    out = [asdict(row) for row in rows]
    # Augment with on-disk git log when the in-memory registry is empty so the
    # FE sees real commits without an explicit seed step.
    if not out:
        out = await _list_git_log(workdir, limit=limit or 50)
    return out


async def _list_git_log(workdir: Path, *, limit: int) -> list[dict[str, Any]]:
    fmt = "%H%x1f%P%x1f%an <%ae>%x1f%aI%x1f%s"
    proc = await asyncio.create_subprocess_exec(
        "git",
        "log",
        f"-n{int(limit)}",
        f"--pretty=format:{fmt}",
        cwd=str(workdir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _stderr = await proc.communicate()
    if proc.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in stdout.decode("utf-8", "replace").splitlines():
        parts = line.split("\x1f")
        if len(parts) != 5:
            continue
        sha, parents, author, ts, subject = parts
        rows.append(
            {
                "sha": sha,
                "parents": [p for p in parents.split() if p],
                "author": author,
                "ts": ts,
                "committed_at": ts,
                "subject": subject,
                "files_changed": 0,
                "feature_id": None,
                "run_id": None,
            }
        )
    return rows


@router.get("/api/git/diff/{sha}")
async def get_diff(sha: str, request: Request) -> dict[str, Any]:
    workdir = _resolve_workdir(request)
    if workdir is not None and _is_git_repo(workdir):
        try:
            return await _real_git_diff(workdir, sha)
        except DiffNotFound:
            raise HTTPException(
                status_code=404, detail={"error_code": "diff_not_found", "sha": sha}
            )
    # Fallback — service stub (used by tests that seed the in-memory registry).
    svc = getattr(request.app.state, "diff_loader", None)
    if svc is None:
        raise HTTPException(status_code=404, detail={"error_code": "diff_not_found", "sha": sha})
    try:
        return cast(dict[str, Any], await svc.load_diff(sha))
    except DiffNotFound:
        raise HTTPException(status_code=404, detail={"error_code": "diff_not_found", "sha": sha})


async def _real_git_diff(workdir: Path, sha: str) -> dict[str, Any]:
    if not sha or len(sha) > 64:
        raise DiffNotFound(sha)
    proc = await asyncio.create_subprocess_exec(
        "git",
        "show",
        "--format=",
        "--patch",
        sha,
        cwd=str(workdir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _stderr = await proc.communicate()
    if proc.returncode != 0:
        raise DiffNotFound(sha)
    text = stdout.decode("utf-8", "replace")
    files = _parse_unified_diff(text)
    return {"sha": sha, "files": files, "stats": {"insertions": 0, "deletions": 0}}


def _parse_unified_diff(text: str) -> list[dict[str, Any]]:
    """Parse ``git show --patch`` output into FE-shaped files[]."""
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_hunk: dict[str, Any] | None = None
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            if current is not None:
                files.append(current)
            # Path: "diff --git a/foo b/foo" → take "foo"
            parts = raw.split()
            path = parts[-1]
            if path.startswith("b/"):
                path = path[2:]
            current = {"path": path, "kind": "text", "hunks": []}
            current_hunk = None
            continue
        if current is None:
            continue
        if raw.startswith("Binary files ") or raw.startswith("GIT binary patch"):
            current["kind"] = "binary"
            current["placeholder"] = True
            current.pop("hunks", None)
            current_hunk = None
            continue
        if raw.startswith("@@"):
            current_hunk = {"header": raw, "lines": []}
            current.setdefault("hunks", []).append(current_hunk)
            continue
        if current_hunk is None:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            current_hunk["lines"].append({"type": "add", "content": raw})
        elif raw.startswith("-") and not raw.startswith("---"):
            current_hunk["lines"].append({"type": "del", "content": raw})
        elif raw.startswith(" "):
            current_hunk["lines"].append({"type": "context", "content": raw})
    if current is not None:
        files.append(current)
    return files


__all__ = ["router"]
