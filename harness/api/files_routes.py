"""F23 · /api/files REST routes (wraps FilesService)."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request

from harness.api.files import FileNotFound, PathTraversalError


router = APIRouter()


@router.get("/api/files/tree")
async def get_tree(request: Request, root: str = Query(default="docs")) -> dict[str, Any]:
    svc = request.app.state.files_service
    try:
        return cast(dict[str, Any], await svc.read_file_tree(root))
    except PathTraversalError as exc:
        raise HTTPException(
            status_code=400, detail={"error_code": "path_traversal", "message": str(exc)}
        )


@router.get("/api/files/read")
async def get_read(request: Request, path: str = Query(default="")) -> dict[str, Any]:
    svc = request.app.state.files_service
    try:
        return cast(dict[str, Any], await svc.read_file_content(path))
    except PathTraversalError as exc:
        raise HTTPException(
            status_code=400, detail={"error_code": "path_traversal", "message": str(exc)}
        )
    except FileNotFound as exc:
        raise HTTPException(
            status_code=404, detail={"error_code": "file_not_found", "message": str(exc)}
        )


__all__ = ["router"]
