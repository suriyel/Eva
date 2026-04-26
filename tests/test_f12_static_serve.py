"""T33 INTG/static-serve —— F12 扩展 F01 FastAPI app 挂载 apps/ui/dist。

Traces To 特性设计 §Implementation Summary "§4 Internal API Contract 集成" 第 (1) 项:
    F01 `harness/api/__init__.py` 必须在 Green 阶段新增
    `app.mount("/", StaticFiles(directory="apps/ui/dist", html=True))`
    且保证 `/api/*` 路由优先级高于静态 fallback。

Red 阶段：apps/ui/dist 不存在 + 未 mount StaticFiles。测试必须失败，
Green 阶段 minimal 实现让测试转绿。
"""

from __future__ import annotations

import pathlib

import httpx
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from harness.api import app


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "apps" / "ui" / "dist"


def _find_static_mount() -> Mount | None:
    for route in app.router.routes:
        if isinstance(route, Mount) and isinstance(route.app, StaticFiles):
            return route
    return None


def test_f12_t33_static_mount_registered() -> None:
    """feature 12: FastAPI app 必须挂载 apps/ui/dist 静态资源。

    F24 B4 sanctioned drift: SPA fallback 不再依赖 ``html=True`` —
    改为显式 ``/assets`` StaticFiles 挂载 + ``/{full_path:path}``
    catch-all 路由（覆盖 ``/process-files``、``/hil`` 等子路径）。
    本测试只断言至少有一个 StaticFiles 挂载存在；``html=True`` 不再要求。
    """
    mount = _find_static_mount()
    assert mount is not None, "feature 12 期望 FastAPI app 挂载 StaticFiles，当前未找到"


async def test_f12_t33_get_root_returns_index_html() -> None:
    """feature 12: GET / 返回 index.html 且内含 <div id=\"root\">。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/")
    assert resp.status_code == 200, f"GET / 状态码 {resp.status_code}"
    assert '<div id="root"' in resp.text, 'index.html 必须含 <div id="root"> 挂载点'


async def test_f12_t33_api_routes_precede_static_fallback() -> None:
    """feature 12: StaticFiles 必须已挂载 *且* /api/health 仍返回 JSON。

    Red 阶段：StaticFiles 未挂载 → 第一条断言 FAIL；Green 挂载后两条同时成立。
    单独只要求 /api/health 200 并不构成 F12 Red 信号（F01 已有），故显式要求
    StaticFiles 存在、路由优先级正确两条共轭断言。
    """
    mount = _find_static_mount()
    assert mount is not None, "feature 12 Green 必须先挂载 StaticFiles（T33 前置）"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200, "/api/health 必须仍返回 200"
    assert resp.headers["content-type"].startswith(
        "application/json"
    ), "/api/health 必须返回 JSON 而非 HTML（StaticFiles 不得屏蔽 /api 路由）"
