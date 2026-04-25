"""F23 · /api/git REST routes (wraps CommitListService / DiffLoader)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request

from harness.api.git import DiffNotFound, GitCommit


router = APIRouter()


@router.get("/api/git/commits")
async def get_commits(
    request: Request,
    run_id: str | None = Query(default=None),
    feature_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    svc = request.app.state.commit_list_service
    rows: list[GitCommit] = await svc.list_commits(run_id=run_id, feature_id=feature_id)
    return [asdict(row) for row in rows]


@router.get("/api/git/diff/{sha}")
async def get_diff(sha: str, request: Request) -> dict[str, Any]:
    svc = request.app.state.diff_loader
    try:
        return cast(dict[str, Any], await svc.load_diff(sha))
    except DiffNotFound:
        raise HTTPException(status_code=404, detail={"error_code": "diff_not_found", "sha": sha})


__all__ = ["router"]
