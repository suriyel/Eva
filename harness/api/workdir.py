"""Workspace 管理 — `/api/workdirs`.

支持持久化全量 workdirs 列表 + 当前选中（current_workdir），桌面壳走原生
``pywebview.create_file_dialog`` 选目录，Web/dev 浏览器 fallback 到文本输入。

路由：
    GET  /api/workdirs          → {workdirs: [...], current: "..."}
    POST /api/workdirs/select   {path}  → 校验 + add + 设 current + wire_services
    POST /api/workdirs/remove   {path}  → 移除；若是 current 同时 unwire
    POST /api/workdirs/pick-native      → 桌面壳调原生 FOLDER_DIALOG；Web 返回 501
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError

from ..config.schema import HarnessConfig
from ..config.store import ConfigStore
from .wiring import wire_services


router = APIRouter()


_WIRED_STATE_KEYS = (
    "orchestrator",
    "run_control_bus",
    "ticket_repo",
    "hil_event_bus",
    "signal_file_watcher",
    "files_service",
    "commit_list_service",
    "diff_loader",
    "validator_runner",
    "workdir",
)


def validate_workdir(path: str) -> Path:
    """校验候选 workdir：非空 / 无 shell metachar / 是已存在目录。

    与 ``RunOrchestrator.start_run`` 校验逻辑对齐，但**不强制** ``.git``——
    用户可以在 git init 之前先把目录加进列表。``start_run`` 自身仍会拦
    非 git repo 的运行请求。
    """
    if not path or not path.strip():
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_workdir", "message": "workdir must be non-empty"},
        )
    if any(ch in path for ch in (";", "|", "&&", "`", "\n")):
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "invalid_workdir",
                "message": f"workdir contains shell metachar: {path!r}",
            },
        )
    p = Path(path)
    if not p.exists() or not p.is_dir():
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "invalid_workdir",
                "message": f"workdir not a directory: {path!r}",
            },
        )
    return p


def _unwire_services(app: Any) -> None:
    """清除 wire_services 注入的全部 app.state.* 槽位（含 SignalFileWatcher stop）。

    ``SignalFileWatcher.stop`` 在某些实现里是 ``async``——这里只能尽力 stop，
    无法 await（同步路径），让 watcher 自身的事件循环处理收尾。常驻线程会随
    进程退出释放，不影响内存正确性。
    """
    watcher = getattr(app.state, "signal_file_watcher", None)
    if watcher is not None:
        sync_stop = getattr(watcher, "stop_sync", None)
        if callable(sync_stop):
            try:
                sync_stop()
            except Exception:
                pass
    for key in _WIRED_STATE_KEYS:
        if hasattr(app.state, key):
            try:
                delattr(app.state, key)
            except AttributeError:
                pass


def _config_store() -> ConfigStore:
    return ConfigStore(ConfigStore.default_path())


def _state_payload(cfg: HarnessConfig) -> dict[str, Any]:
    return {"workdirs": list(cfg.workdirs), "current": cfg.current_workdir}


# ---------------------------------------------------------------------------
# Body schemas
# ---------------------------------------------------------------------------
class _WorkdirBody(BaseModel):
    path: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/api/workdirs")
async def get_workdirs() -> dict[str, Any]:
    cfg = _config_store().load()
    return _state_payload(cfg)


@router.post("/api/workdirs/select")
async def post_select(request: Request) -> dict[str, Any]:
    raw = await request.json()
    try:
        body = _WorkdirBody.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_body", "errors": exc.errors()},
        )
    p = validate_workdir(body.path)
    store = _config_store()
    store.add_workdir(str(p))
    cfg = store.set_current_workdir(str(p))

    # 切换前先卸载旧 services（防 SignalFileWatcher 线程泄漏）
    _unwire_services(request.app)
    wire_services(request.app, workdir=p)
    return _state_payload(cfg)


@router.post("/api/workdirs/remove")
async def post_remove(request: Request) -> dict[str, Any]:
    raw = await request.json()
    try:
        body = _WorkdirBody.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_body", "errors": exc.errors()},
        )
    store = _config_store()
    cfg_before = store.load()
    was_current = cfg_before.current_workdir == body.path
    cfg = store.remove_workdir(body.path)
    if was_current:
        _unwire_services(request.app)
    return _state_payload(cfg)


@router.post("/api/workdirs/pick-native")
async def post_pick_native(request: Request) -> dict[str, Any]:
    """同进程调 pywebview FOLDER_DIALOG。无 webview window 返回 501。"""
    window = getattr(request.app.state, "webview_window", None)
    if window is None:
        raise HTTPException(
            status_code=501,
            detail={
                "error_code": "not_supported_in_web_mode",
                "message": "原生文件夹对话框仅在桌面壳模式可用",
            },
        )
    try:
        import webview  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover — defensive
        raise HTTPException(
            status_code=501,
            detail={
                "error_code": "pywebview_unavailable",
                "message": f"pywebview import failed: {exc}",
            },
        )

    try:
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "dialog_failed",
                "message": f"create_file_dialog raised: {exc}",
            },
        )

    # pywebview 返回 None（取消）或 list[str]（选了一个或多个目录）
    if result is None:
        return {"path": None}
    if isinstance(result, (list, tuple)) and result:
        return {"path": str(result[0])}
    if isinstance(result, str) and result:
        return {"path": result}
    return {"path": None}


__all__ = ["router", "validate_workdir"]
