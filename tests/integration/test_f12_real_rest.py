"""T32 INTG/rest —— feature 12 × IAPI-002 真实 REST client 同源挂载。

Traces To 特性设计 §Interface Contract apiClient.fetch · §Test Inventory T32 · §IS §4 契约集成 (1)。

apiClient 的 base URL 约定为 `http://127.0.0.1:<port>/`（`window.__HARNESS_API_BASE__`
或 `VITE_API_BASE`）—— 与 apps/ui/dist 同源。因此 F12 期望后端在同一端口**同时**提供
`/api/*` 与 `/` 静态资源。本测试同时断言：
    (1) /api/health 契约稳定（apiClient 的 Zod schema 预期）；
    (2) 同源挂载：/ 返回 HTML（StaticFiles 已挂载），即 apiClient 推导 base URL 不会跨端口。

Red 阶段：StaticFiles 未挂载 → 第 (2) 条断言 FAIL。Green 后两条同时绿。
"""

from __future__ import annotations

import re

import httpx
import pytest

from harness.api import app


@pytest.mark.real_http
async def test_f12_t32_real_api_health_contract_and_same_origin_mount() -> None:
    """feature 12: /api/health schema OK 且 / 返回 HTML（同源）。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/health")
        root_resp = await client.get("/")
    # (1) IAPI-002 契约字段
    assert resp.status_code == 200, f"/api/health 状态码 {resp.status_code}"
    body = resp.json()
    for key in ("bind", "version", "claude_auth", "cli_versions"):
        assert key in body, f"/api/health 响应缺失字段 {key!r}；前端 Zod schema 会失败"
    assert body["bind"] in {"127.0.0.1", "::1"}, "bind 必须为回环（NFR-007）"
    assert re.match(
        r"^\d+\.\d+\.\d+", body["version"]
    ), "version 字段必须 semver-like（前端 Zod 期望）"
    assert set(body["cli_versions"].keys()) == {"claude", "opencode"}
    # (2) 同源挂载：/ 返回 HTML，apiClient base URL 同端口（Red 阶段 StaticFiles 未挂载 → fail）
    assert (
        root_resp.status_code == 200
    ), f"GET / 必须返回 200（StaticFiles 挂载后），实际 {root_resp.status_code}"
    ctype = root_resp.headers.get("content-type", "")
    assert (
        "html" in ctype.lower()
    ), f"GET / 必须返回 text/html 表明 apps/ui/dist 已同源挂载，实际 content-type={ctype}"
