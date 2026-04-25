"""F23 · POST /api/validate/{file} REST route (wraps ValidatorRunner)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness.subprocess.validator.runner import ValidatorScriptUnknown, ValidatorTimeout
from harness.subprocess.validator.schemas import ValidateRequest, ValidatorScript, ValidationReport


router = APIRouter()


class _ValidateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script: ValidatorScript | None = None
    timeout_s: float = Field(default=60.0)


def _resolve_safe_file(file: str, workdir: Path) -> Path:
    """Reject obvious path-traversal; resolve under workdir."""
    if not file or ".." in Path(file).parts or file.startswith("/"):
        raise HTTPException(
            status_code=400,
            detail={"error_code": "path_traversal", "path": file},
        )
    candidate = (workdir / file).resolve()
    try:
        candidate.relative_to(workdir.resolve())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "path_traversal", "path": file},
        )
    return candidate


@router.post("/api/validate/{file:path}")
async def post_validate(file: str, request: Request) -> dict[str, Any]:
    raw = await request.json()
    try:
        body = _ValidateBody.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail={"error_code": "validation", "errors": exc.errors()}
        )

    workdir = Path(getattr(request.app.state, "workdir", os.getcwd())).resolve()
    target = _resolve_safe_file(file, workdir)

    runner = request.app.state.validator_runner
    req = ValidateRequest(
        path=str(target),
        script=body.script,
        workdir=str(workdir),
        timeout_s=body.timeout_s,
    )
    try:
        report: ValidationReport = await runner.run(req)
    except ValidatorScriptUnknown as exc:
        raise HTTPException(
            status_code=400, detail={"error_code": "unknown_script", "message": str(exc)}
        )
    except ValidatorTimeout as exc:
        raise HTTPException(status_code=500, detail={"error_code": "timeout", "message": str(exc)})
    return report.model_dump(mode="json")


__all__ = ["router"]
