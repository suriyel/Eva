"""F10 · Skills REST routes (IAPI-018).

POST /api/skills/install   → SkillsInstallResult (200) | 400 | 409
POST /api/skills/pull      → SkillsInstallResult (200) | 400 | 409

The workdir is resolved from the ``HARNESS_WORKDIR`` env var (F01
convention). Subprocess calls happen via ``SkillsInstaller`` which uses
argv lists — never ``shell=True`` (NFR-008 / §Implementation Summary).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from harness.skills import (
    GitSubprocessError,
    GitUrlRejectedError,
    SkillsInstallBusyError,
    SkillsInstaller,
    SkillsInstallRequest,
    SkillsInstallResult,
    TargetPathEscapeError,
)


router = APIRouter(prefix="/api/skills", tags=["skills"])


def _resolve_workdir() -> Path:
    """Derive the active workdir from ``HARNESS_WORKDIR`` env var."""

    env = os.environ.get("HARNESS_WORKDIR", "")
    if not env:
        raise HTTPException(
            status_code=500,
            detail="HARNESS_WORKDIR 未设置，无法执行 skills 安装",
        )
    wd = Path(env)
    if not wd.is_dir():
        raise HTTPException(
            status_code=500,
            detail=f"HARNESS_WORKDIR 指向的目录不存在: {wd}",
        )
    return wd


@router.post("/install", response_model=SkillsInstallResult)
def post_install(req: SkillsInstallRequest) -> SkillsInstallResult:
    workdir = _resolve_workdir()
    installer = SkillsInstaller()
    try:
        return installer.install(req, workdir=workdir)
    except (GitUrlRejectedError, TargetPathEscapeError) as exc:
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}")
    except SkillsInstallBusyError as exc:
        raise HTTPException(status_code=409, detail=f"run 进行中: {exc}")
    except GitSubprocessError as exc:
        raise HTTPException(status_code=409, detail=f"git 调用失败: {exc}")


@router.get("/tree")
def get_tree(request: Request, path: str | None = None) -> dict[str, object]:
    """Return ``SkillTree {root, plugins[]}``.

    F22 RT06 SEC: any '..' path-traversal probe is rejected with 400 BEFORE
    the workdir lookup so production app rejects regardless of whether
    HARNESS_WORKDIR / app.state.workdir is wired.
    """
    if path is not None and (".." in path or path.startswith("/")):
        raise HTTPException(
            status_code=400,
            detail={"error_code": "path_traversal", "path": path},
        )
    # Resolve workdir from app.state first (F22 wire_services), env var fallback.
    workdir: Path | None = None
    wd = getattr(request.app.state, "workdir", None)
    if wd:
        workdir = Path(wd)
    if workdir is None:
        env = os.environ.get("HARNESS_WORKDIR", "")
        if env:
            workdir = Path(env)
    if workdir is None or not workdir.is_dir():
        # No workdir → empty tree; do NOT 500 (FE just renders EmptyState).
        return {"root": "", "plugins": [], "name": "root", "kind": "plugin", "children": []}
    plugins_root = workdir / "plugins"
    plugins: list[dict[str, object]] = []
    if plugins_root.is_dir():
        for entry in sorted(plugins_root.iterdir()):
            if entry.is_dir():
                plugins.append(
                    {
                        "name": entry.name,
                        "source": "local",
                        "sha": None,
                        "installed_at": None,
                    }
                )
    return {"root": str(workdir), "plugins": plugins}


@router.post("/pull", response_model=SkillsInstallResult)
def post_pull(req: SkillsInstallRequest) -> SkillsInstallResult:
    workdir = _resolve_workdir()
    installer = SkillsInstaller()
    # For pull, ``target_dir`` may be a relative path under workdir/plugins/.
    target_dir = req.target_dir or "plugins/longtaskforagent"
    try:
        # Pre-validate target before running git.
        from harness.skills.installer import _validate_target_dir

        target_path = _validate_target_dir(target_dir, workdir)
        return installer.pull(str(target_path), workdir=workdir)
    except TargetPathEscapeError as exc:
        raise HTTPException(status_code=400, detail=f"目标路径非法: {exc}")
    except SkillsInstallBusyError as exc:
        raise HTTPException(status_code=409, detail=f"run 进行中: {exc}")
    except GitSubprocessError as exc:
        raise HTTPException(status_code=409, detail=f"git 调用失败: {exc}")


__all__ = ["router"]
