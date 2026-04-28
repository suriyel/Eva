"""F10 · Skills REST routes (IAPI-018).

POST /api/skills/install   → SkillsInstallResult (200) | 400 | 409
POST /api/skills/pull      → SkillsInstallResult (200) | 400 | 409

workdir 来源于 ``app.state.workdir``（由 ``wire_services`` 注入）；UI 通过
``/api/workdirs/select`` 显式选择 + 持久化。Subprocess 调用走
``SkillsInstaller``，使用 argv list 而非 ``shell=True``（NFR-008）。
"""

from __future__ import annotations

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


def _resolve_workdir(request: Request) -> Path:
    wd = getattr(request.app.state, "workdir", None)
    if not wd:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "workdir_not_selected", "message": "请先选择工作目录"},
        )
    p = Path(wd)
    if not p.is_dir():
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "invalid_workdir",
                "message": f"工作目录已失效: {p}",
            },
        )
    return p


@router.post("/install", response_model=SkillsInstallResult)
def post_install(req: SkillsInstallRequest, request: Request) -> SkillsInstallResult:
    workdir = _resolve_workdir(request)
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

    F22 RT06 SEC：任何 ``..`` 路径穿越仍在 workdir 解析前被 400 拦截。
    workdir 未配置时返回空 tree（FE 渲染 EmptyState），不报 500。
    """
    if path is not None and (".." in path or path.startswith("/")):
        raise HTTPException(
            status_code=400,
            detail={"error_code": "path_traversal", "path": path},
        )
    wd = getattr(request.app.state, "workdir", None)
    workdir = Path(wd) if wd else None
    if workdir is None or not workdir.is_dir():
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
def post_pull(req: SkillsInstallRequest, request: Request) -> SkillsInstallResult:
    workdir = _resolve_workdir(request)
    installer = SkillsInstaller()
    target_dir = req.target_dir or "plugins/longtaskforagent"
    try:
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
