"""F23 · POST /api/validate/{file} REST route (wraps ValidatorRunner).

F22 IAPI-016 contract — accepts both legacy F23 body shape ({script,timeout_s})
and the F22-FE body shape ({path, content[, script, timeout_s]}). When ``content``
is supplied, the route writes it to a temp file under ``workdir`` so the
ValidatorRunner subprocess can validate the user's *unsaved* edit (FR-039:
前端 Zod 通过 → 后端 cross-field 校验).

Response shape: ``ValidationReport`` from the runner is normalised to the
FE-consumed surface ``{ ok, issues:[{path, level, message}], stderr_tail? }``
so ``apps/ui/src/lib/zod-schemas.ts`` parses without drift.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness.subprocess.validator.runner import ValidatorScriptUnknown, ValidatorTimeout
from harness.subprocess.validator.schemas import ValidateRequest, ValidatorScript, ValidationReport


router = APIRouter()


class _ValidateBody(BaseModel):
    """Permissive body schema accepting both F23 (legacy) and F22 (FE) shapes."""

    model_config = ConfigDict(extra="ignore")

    script: ValidatorScript | None = None
    timeout_s: float = Field(default=60.0)
    path: str | None = None
    content: str | None = None


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


def _normalise_for_fe(report: ValidationReport) -> dict[str, Any]:
    """Project ValidatorReport → FE-consumed shape `{ok, issues:[{path,level,message}], stderr_tail?}`.

    F22 FR-039 + IAPI-016: subprocess crash output is preserved both as a
    visible issue (so CrossFieldErrorList renders it) AND in ``stderr_tail``
    (so a dedicated `<[data-testid="process-file-stderr-tail"]>` panel can
    render the raw traceback for the SEC/INTG case).
    """
    raw = report.model_dump(mode="json")
    issues_out: list[dict[str, Any]] = []
    stderr_tail: str | None = None
    for issue in raw.get("issues") or []:
        path = issue.get("path_json_pointer") or issue.get("rule_id") or ""
        # F22 §IC level ∈ {error, warning}; the runner emits {error, warning, info}.
        sev = issue.get("severity", "error")
        level = "warning" if sev == "warning" else "error"
        message = str(issue.get("message", ""))
        if issue.get("rule_id") == "subprocess_exit":
            stderr_tail = message
            # Also emit a single visible issue so the FE list isn't empty.
            issues_out.append({"path": "subprocess_exit", "level": "error", "message": message})
            continue
        issues_out.append({"path": path, "level": level, "message": message})
    out: dict[str, Any] = {"ok": bool(raw.get("ok", False)), "issues": issues_out}
    if stderr_tail:
        out["stderr_tail"] = stderr_tail
    return out


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

    # F22: when caller supplied content (unsaved edit), persist to a temp file
    # under workdir so subprocess validator can read it. Use the original
    # basename to keep the script's heuristic file-routing intact.
    temp_path: Path | None = None
    runner_path = str(target)
    if body.content is not None:
        # Place under workdir so the validator's relative paths match.
        # Suffix carries the original filename so the runner's heuristic
        # script-routing (filename-based) stays intact.
        fd, name = tempfile.mkstemp(
            suffix=f"_{Path(target).name}", prefix="f22_validate_", dir=str(workdir)
        )
        os.close(fd)
        temp_path = Path(name)
        temp_path.write_text(body.content, encoding="utf-8")
        runner_path = str(temp_path)

    runner = request.app.state.validator_runner
    req = ValidateRequest(
        path=runner_path,
        script=body.script,
        workdir=str(workdir),
        timeout_s=body.timeout_s,
    )
    # F22 FR-039: route-layer flag that flips validate_features.py's empty-
    # features[] from soft warning to hard error. phase_route subprocess
    # bypasses this layer and keeps the lenient default.
    prev_strict = os.environ.get("HARNESS_STRICT_FEATURES")
    if Path(target).name == "feature-list.json":
        os.environ["HARNESS_STRICT_FEATURES"] = "1"
    try:
        try:
            report: ValidationReport = await runner.run(req)
        except ValidatorScriptUnknown as exc:
            raise HTTPException(
                status_code=400, detail={"error_code": "unknown_script", "message": str(exc)}
            )
        except ValidatorTimeout as exc:
            raise HTTPException(
                status_code=500, detail={"error_code": "timeout", "message": str(exc)}
            )
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
        if Path(target).name == "feature-list.json":
            if prev_strict is None:
                os.environ.pop("HARNESS_STRICT_FEATURES", None)
            else:
                os.environ["HARNESS_STRICT_FEATURES"] = prev_strict

    return _normalise_for_fe(report)


__all__ = ["router"]
