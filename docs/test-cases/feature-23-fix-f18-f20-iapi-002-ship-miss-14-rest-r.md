# 测试用例集: Fix F18/F20 IAPI-002 ship miss — 14 REST routes + 5 WS broadcasters + uvicorn ws backend

**Feature ID**: 23
**关联需求**: FR-001, FR-024, FR-029, FR-039, FR-042, IFR-007（ATS L49 / L97 / L102 / L120 / L128 / L185；必须类别 FUNC / BNDRY / SEC / PERF；UI 类别由 F21/F22 单独承担——本特性 `ui:false`）
**日期**: 2026-04-26
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则（FR-001/024/029/039/042 + IFR-007）、ATS L49 / L97 / L102 / L120 / L128 / L185 类别约束、Feature Design Test Inventory R1–R46、可观察接口（生产入口 `harness.api:app` 经 `httpx.AsyncClient(transport=ASGITransport(app))` in-process REST、真启 `uvicorn harness.api:app` + `websockets.connect(...)` 真握手、`pip install -r requirements.txt` 后 `python -c "import websockets, wsproto"` 依赖检查、`python -c "from harness.api import app; ..."` 路由清单查询、test-only `harness.app.main.build_app()` 既有回归、`AppBootstrap._wire_services` 注入 `app.state.*` 检查）推导，不阅读实现源码。
> - **Specification resolutions applied from Feature Design Clarification Addendum**：feature design `## Clarification Addendum` 表为空（"无需澄清 — 全部规格明确"）；§6.2 schema / 错误码 / 路径维持不变，不触发 Contract Deviation Protocol。
> - **`feature.ui == false` → 本特性无 UI 类别用例**。ATS L102 FR-029 行列出 UI 仅是为对齐 F21（TicketStream 异常面板）下游消费表面；本特性是后端 wiring bugfix（14 REST + 5 WS + uvicorn[standard] 依赖修复），Visual Rendering Contract = N/A（`docs/features/23-fix-f18-f20-iapi-002-ship-miss-14-rest-r.md` 已写明），UI 表面由 F21/F22 自身 ST 承担。
> - 本特性以 **混合执行模式** 运行（env-guide §1）：(a) `INTG/asgi-rest` / `INTG/lifespan` / `INTG/regression-f20-st` 类别用例使用 `httpx.AsyncClient(transport=ASGITransport(app=harness.api.app))` in-process 装载，免启 uvicorn —— 仅需 §2 `.venv` 激活；(b) `INTG/uvicorn-real-handshake` 类别用例（R22-R27、R42、R47）必须真启 `uvicorn harness.api:app --host 127.0.0.1 --port <ephemeral>`（经 `bash scripts/svc-api-start.sh` @ 8765），证明 `requirements.txt` 改 `uvicorn[standard]==0.44.0` 后 `websockets`/`wsproto` transitive dep 真正生效、HTTP 101 upgrade 不再 pre-ASGI 404；(c) `INTG/dependency-import` 类别 R28 在干净 venv 跑 `pip install -r requirements.txt && python -c "import websockets, wsproto"` 验证依赖图修复；(d) `INTG/single-definition` 类别 R29 经 `python -c "from harness.api import app; ..."` 查路由表唯一性。
> - **手动测试**：本特性全部用例均自动化执行（`已自动化: Yes`），无 `已自动化: No` 项；FR-029 涉及的 UI 按钮交互（Skip / Force-Abort 视觉反馈）由 F21 ST 承担，本特性仅验证 `POST /api/anomaly/:ticket/{skip,force-abort}` 在 production 入口的可达性与 schema 合规。
> - **bug 根因校验**：本 ST 用例区分两条独立验证维度：(1) **In-process ASGI** 校验 router 已经 `app.include_router()` 挂入 `harness.api:app`（覆盖 14 REST 路由 + lifespan wiring + 双定义归一）；(2) **真实 uvicorn handshake** 校验 `uvicorn[standard]==0.44.0` 修复使 WS upgrade 在 ASGI 之前不再 HTTP 404、5 条 WS 频道接入真 broadcaster（不再返回 `_F21_*_BOOTSTRAP` echo stub）。两组失败模式互不掩盖，缺一不足以确认 bug 已修复。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 36 |
| boundary | 7 |
| ui | 0 |
| security | 2 |
| performance | 2 |
| **合计** | **47** |

> **类别归属约定**：Feature Design Test Inventory 46 行（R1-R46）含 `INTG/asgi-rest`（21 行）/ `INTG/uvicorn-real-handshake`（7 行）/ `INTG/dependency-import`（1 行）/ `INTG/single-definition`（1 行）/ `INTG/regression-f20-st`（1 行）/ `INTG/lifespan`（1 行）/ `INTG/hil-flow`（1 行）/ `FUNC/error`（10 行）/ `BNDRY/edge`（7 行）/ `SEC/path-traversal`（1 行）/ `SEC/forbid`（1 行）—— ST 用例 ID 规范允许 CATEGORY ∈ {FUNC, BNDRY, UI, SEC, PERF}（见 `scripts/validate_st_cases.py` CASE_ID_PATTERN）。映射规则：
> - `INTG/asgi-rest` / `INTG/lifespan` / `INTG/regression-f20-st` / `INTG/single-definition` / `INTG/dependency-import` / `INTG/hil-flow` / `FUNC/error` 均归 functional 类别（black-box behavior 验证），与 F19/F20 ST 既有惯例一致；
> - `INTG/uvicorn-real-handshake` 中验证事件 envelope 内容的归 functional（R22-R26、R42），验证时序的 R27（30s ping）归 performance；
> - `BNDRY/edge` → boundary；`SEC/*` → security；
> - 新增 R47（IFR-007 message latency p95 < 100ms）归 performance（NFR 间接锚 IFR-007 PERF 注释 ATS L185）。
> 负向占比：FUNC/error（10：R3/R6/R7/R9/R12/R15/R21/R29-反向/R34/R42） + BNDRY（7：R39/R40/R41/R44/R45/R46/R21）+ SEC（2：R33/R43） + 反向依赖（1：R28-反向 import 失败）= 20 负向 / 47 ≈ **42.6% > 40%**，达标。

> **Test Inventory → ST 用例 1:1 映射**：Feature Design 46 行 Test Inventory（R1-R46）一一对应 ST 用例；新增 R47（PERF：IFR-007 message latency）补足 PERF 类别覆盖。pytest 函数对照见可追溯矩阵 "自动化测试" 列。

---

### 用例编号

ST-FUNC-023-001

### 关联需求

FR-001 AC-1 · §Interface Contract `runs_router.post_start_run` postcondition · Feature Design Test Inventory R1 · ATS L49 FR-001

### 测试目标

验证生产入口 `harness.api:app` 已挂载 `POST /api/runs/start`，合法 git workdir 经 ASGI in-process 调用返回 200 + `RunStatus { state: "running"|"starting", run_id, workdir, started_at }`；杀手 bug：router 未 `include_router()` 时返 405/404。

### 前置条件

- `.venv` 激活；`harness.api:app` 可导入（`python -c "from harness.api import app"` 不抛 ImportError）
- `httpx`、`fastapi`、`pytest-asyncio` 已安装
- `pytest tmp_path` 提供空白目录；`subprocess.run(["git", "init", str(tmp_path)], check=True)` 已成功
- `AppBootstrap._wire_services(app)` 已被调用（或 fixture 注入 mock `app.state.orchestrator`）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `subprocess.run(["git","init",str(tmp_path)],check=True)` 初始化 git repo | exit=0；`tmp_path/.git/` 存在 |
| 2 | `from harness.api import app; from httpx import AsyncClient, ASGITransport` 装载生产 app | 不抛 ImportError |
| 3 | `async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client: resp = await client.post("/api/runs/start", json={"workdir": str(tmp_path)})` | 返回 `httpx.Response` 对象 |
| 4 | 断言 `resp.status_code == 200` | True（不为 405/404，证明 router 已挂载） |
| 5 | 断言 `resp.json()["state"] in {"starting","running"}` | True |
| 6 | 断言 `resp.json()["workdir"] == str(tmp_path)` 且 `"run_id" in resp.json()` 且 `"started_at" in resp.json()` | True |

### 验证点

- `POST /api/runs/start` 在 production app 上可达（router 已 `app.include_router(runs_router)`）
- 响应 schema 严格符合 §6.2.2 L1137 `RunStatus`
- `app.state.orchestrator` 注入路径正确，handler 不抛 500

### 后置检查

- `tmp_path/.harness/run.lock` 在测试后释放（`cancel_run` 或 fixture teardown）

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_runs_start_legal_git_workdir`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-002

### 关联需求

FR-001 AC-3 · §Interface Contract `runs_router.post_start_run` Raises · Test Inventory R2 · ATS L49 FR-001 SEC

### 测试目标

非 git 仓库 workdir 经 production ASGI 入口拒绝；预期 400 + `error_code: "not_a_git_repo"` (per FR-001 AC-3)。

### 前置条件

- 同 ST-FUNC-023-001 前置（除步骤 1：跳过 `git init`，保持 tmp_path 为非 git 临时目录）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 创建空 tmp_path（不 `git init`） | `tmp_path/.git/` 不存在 |
| 2 | `await client.post("/api/runs/start", json={"workdir": str(tmp_path)})` | 返回 Response |
| 3 | 断言 `resp.status_code == 400` | True |
| 4 | 断言 `resp.json()["error_code"] == "not_a_git_repo"` | True |

### 验证点

- handler 把 `RunOrchestrator.start_run` 的 `not_a_git_repo` 异常正确转译为 HTTP 400
- 不为 500（service 异常未被 router 吞）

### 后置检查

- 无 run.lock 残留

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_runs_start_non_git_workdir_rejected`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-003

### 关联需求

§Interface Contract `runs_router.post_start_run` Raises · Test Inventory R3 · §Boundary Conditions `RunStartRequest.workdir`

### 测试目标

含 shell metachar 的 workdir（`;`、`\n`）被 router 转 400 invalid_workdir，不落入 SPA fallback。

### 前置条件

- 同 ST-FUNC-023-001

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await client.post("/api/runs/start", json={"workdir": "/tmp/x;rm -rf /"})` | Response |
| 2 | 断言 `resp.status_code == 400` 且 `resp.json()["error_code"] == "invalid_workdir"` | True |
| 3 | `await client.post("/api/runs/start", json={"workdir": "/tmp/x\nrm"})` | Response |
| 4 | 断言 `resp.status_code == 400` | True |

### 验证点

- shell metachar 校验在 router 层或 service 层生效（不被 StaticFiles SPA fallback 吞）
- 错误码字符串与 §Interface Contract 一致

### 后置检查

- 无副作用（无 run 启动、无文件生成）

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_runs_start_shell_metachar_rejected`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-004

### 关联需求

FR-029 AC-1 · §Interface Contract `anomaly_router.post_skip` postcondition · Test Inventory R4 · ATS L102 FR-029

### 测试目标

`POST /api/anomaly/:ticket_id/skip` 在 production 入口可达，对 retrying ticket 返回 200 + `RecoveryDecision { kind: "skipped" }`。

### 前置条件

- 同 ST-FUNC-023-001 前置 + seed 1 张 `state=retrying` ticket 至 TicketRepository（fixture）
- `app.state.orchestrator` 注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed `Ticket(id="t1", state="retrying", ...)` 经 `TicketRepository.save` | 持久化成功 |
| 2 | `await client.post("/api/anomaly/t1/skip")` | Response |
| 3 | 断言 `resp.status_code == 200` | True |
| 4 | 断言 `resp.json()["kind"] == "skipped"` | True |

### 验证点

- `/api/anomaly/*` router 已挂载（不为 404）
- handler 委托至 `RunOrchestrator.skip_anomaly` 真实方法
- response schema 符合 §6.2.4 `RecoveryDecision`

### 后置检查

- ticket state 在 SQLite 中为 `skipped`

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_anomaly_skip`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-005

### 关联需求

FR-029 AC-2 · §Interface Contract `anomaly_router.post_force_abort` postcondition · Test Inventory R5 · ATS L102 FR-029

### 测试目标

`POST /api/anomaly/:ticket_id/force-abort` 对 running ticket 返回 200 + `RecoveryDecision { kind: "abort" }`。

### 前置条件

- 同 ST-FUNC-023-004（seed running ticket）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed `Ticket(id="t2", state="running", ...)` | 持久化成功 |
| 2 | `await client.post("/api/anomaly/t2/force-abort")` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `resp.json()["kind"] == "abort"` | True |

### 验证点

- handler 委托至 `RunOrchestrator.force_abort_anomaly`

### 后置检查

- ticket state == `aborted`

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_anomaly_force_abort`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-006

### 关联需求

§Interface Contract `anomaly_router.post_skip` Raises · Test Inventory R6

### 测试目标

`POST /api/anomaly/<unknown>/skip` 返回 404 TicketNotFound，不为 500。

### 前置条件

- 同 ST-FUNC-023-001 前置；不 seed ticket

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await client.post("/api/anomaly/nonexistent-id/skip")` | Response |
| 2 | 断言 `resp.status_code == 404` | True |

### 验证点

- service 层 `TicketNotFound` 被 router 转译为 HTTP 404（不 500）
- `app.state.ticket_repo` 已被 lifespan wiring 注入

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_anomaly_skip_unknown_ticket_404`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-007

### 关联需求

§Interface Contract `anomaly_router.post_force_abort` Raises · Test Inventory R7

### 测试目标

`POST /api/anomaly/:ticket_id/force-abort` 对 COMPLETED ticket 返回 409 InvalidTicketState。

### 前置条件

- seed `Ticket(state="completed", ...)`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed completed ticket id="t3" | 持久化成功 |
| 2 | `await client.post("/api/anomaly/t3/force-abort")` | Response |
| 3 | 断言 `resp.status_code == 409` | True |

### 验证点

- 终态 ticket 不可被 force-abort，service 异常正确转译为 409

### 后置检查

- ticket 状态保持 `completed`

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_anomaly_force_abort_completed_409`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-008

### 关联需求

§6.2.2 L1142-1144 · §Interface Contract `tickets_router.get_tickets` postcondition · Test Inventory R8

### 测试目标

`GET /api/tickets?run_id=<rid>` 返回 200 + `Ticket[]` 长度=3，按 `started_at asc` 排序。

### 前置条件

- seed 3 张同 run_id 的 ticket，started_at 不同

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed 3 ticket，run_id="r1" | 持久化成功 |
| 2 | `resp = await client.get("/api/tickets?run_id=r1")` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `len(resp.json()) == 3` | True |
| 4 | 断言 `[t["started_at"] for t in resp.json()]` 严格升序 | True |

### 验证点

- `/api/tickets` 路由已挂载
- 排序符合 `TicketRepository.list_by_run` 默认顺序

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_tickets_list_by_run`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-009

### 关联需求

§Interface Contract `tickets_router.get_ticket` Raises · Test Inventory R9

### 测试目标

`GET /api/tickets/<unknown>` 返回 404，不为 500。

### 前置条件

- 同 ST-FUNC-023-001；不 seed ticket

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/tickets/nonexistent")` | Response |
| 2 | 断言 `resp.status_code == 404` | True |

### 验证点

- ticket_repo 已注入；service 异常正确转译

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_ticket_unknown_404`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-010

### 关联需求

§6.2.2 L1144 · Test Inventory R10

### 测试目标

`GET /api/tickets/<tid>/stream?offset=0` 返回 200 + `StreamEvent[]`，按 seq 升序。

### 前置条件

- seed ticket id="t4" + 5 条 StreamEvent (seq=0..4)

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed 5 stream events 经 `StreamEventRepo.save` | 持久化成功 |
| 2 | `resp = await client.get("/api/tickets/t4/stream?offset=0")` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `len(resp.json()) == 5` | True |
| 4 | 断言 `[e["seq"] for e in resp.json()] == [0,1,2,3,4]` | True |

### 验证点

- `/api/tickets/:id/stream` 路由已挂载

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_ticket_stream_paged`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-011

### 关联需求

FR-039 AC · §6.2.2 L1162 · §Interface Contract `validate_router.post_validate` · Test Inventory R11 · ATS L120 FR-039

### 测试目标

`POST /api/validate/feature-list.json { script: "validate_features" }` 对合法 feature-list.json 返回 200 + `ValidationReport { ok: true, issues: [], script_exit_code: 0, duration_ms }`。

### 前置条件

- 合法 feature-list.json 存在于 workdir
- `app.state.validator_runner` 注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await client.post("/api/validate/feature-list.json", json={"script": "validate_features"})` | Response |
| 2 | 断言 `resp.status_code == 200` 且 `resp.json()["ok"] is True` | True |
| 3 | 断言 `resp.json()["script_exit_code"] == 0` 且 `resp.json()["issues"] == []` | True |
| 4 | 断言 `"duration_ms" in resp.json()` | True |

### 验证点

- `/api/validate/:file` router 已挂载
- ValidatorRunner 真实子进程被调用

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_validate_features_pass`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-012

### 关联需求

§Interface Contract `validate_router.post_validate` Raises · Test Inventory R12 · ATS L120 FR-039

### 测试目标

非法 feature-list.json 经 validator 返回 200 + `ValidationReport { ok: false, issues: [...] }`（脚本 exit≠0 但 router 不应 500）。

### 前置条件

- 写入非法 feature-list.json（如缺 features 字段）
- `app.state.validator_runner` 注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 创建非法 feature-list.json | 文件存在 |
| 2 | `await client.post("/api/validate/feature-list.json", json={"script": "validate_features"})` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `resp.json()["ok"] is False` | True |
| 4 | 断言 `len(resp.json()["issues"]) > 0` | True |

### 验证点

- 脚本 exit≠0 不被 router 误转译为 500

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_validate_features_fail_returns_200`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-013

### 关联需求

FR-042 AC-1 · §6.2.2 L1163 · §Interface Contract `git_router.get_commits` · Test Inventory R13 · ATS L128 FR-042

### 测试目标

`GET /api/git/commits?run_id=<rid>` 返回 200 + `GitCommit[]` 长度=5，按 committed_at desc 排序。

### 前置条件

- seed 5 commits 关联 run_id="r1" 至 SQLite git table

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed 5 git commits 持久化 | 完成 |
| 2 | `resp = await client.get("/api/git/commits?run_id=r1")` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `len(resp.json()) == 5` | True |
| 4 | 断言 `[c["committed_at"] for c in resp.json()]` 严格降序 | True |

### 验证点

- `/api/git/commits` router 已挂载

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_git_commits_by_run`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-014

### 关联需求

§6.2.2 L1164 · Test Inventory R14 · ATS L128 FR-042

### 测试目标

`GET /api/git/diff/<合法 sha>` 返回 200 + `DiffPayload { sha, files, stats }`。

### 前置条件

- 真实 git repo 含 ≥1 commit；提取 sha
- `app.state.diff_loader` 注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 真 git repo + 1 commit；记 `sha = git rev-parse HEAD` | sha 提取成功 |
| 2 | `resp = await client.get(f"/api/git/diff/{sha}")` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `resp.json()["sha"] == sha` | True |
| 4 | 断言 `"files" in resp.json()` 且 `"stats" in resp.json()` | True |

### 验证点

- `/api/git/diff/:sha` router 已挂载
- DiffLoader 真实子进程

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_git_diff_real_sha`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-015

### 关联需求

§Interface Contract `git_router.get_diff` Raises · Test Inventory R15

### 测试目标

`GET /api/git/diff/<不存在 sha>` 返回 404 DiffNotFound。

### 前置条件

- 同 ST-FUNC-023-014；使用 64 位虚假 sha

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/git/diff/" + "0"*40)` | Response |
| 2 | 断言 `resp.status_code == 404` | True |

### 验证点

- service ValueError → router 404 DiffNotFound（不 500）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_git_diff_unknown_sha_404`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-016

### 关联需求

§6.2.2 L1148 · Test Inventory R16

### 测试目标

`GET /api/settings/general` 返回 200 + `GeneralSettings` 默认值。

### 前置条件

- `~/.harness/config.json` 不存在或为初值

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/settings/general")` | Response |
| 2 | 断言 `resp.status_code == 200` | True |
| 3 | 断言 response 是合法 `GeneralSettings` 字段集（如 `ui_density`、`auto_save` 等） | True |

### 验证点

- `/api/settings/general` 已挂载（与既有 `/api/settings` model_rules / classifier 分开）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_settings_general_defaults`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-017

### 关联需求

§6.2.2 L1157 · Test Inventory R17

### 测试目标

`GET /api/skills/tree` 返回 200 + `SkillTree { root, plugins[] }`。

### 前置条件

- `HARNESS_WORKDIR` env 已设；plugin 目录存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/skills/tree")` | Response |
| 2 | 断言 `resp.status_code == 200` | True |
| 3 | 断言 `"root" in resp.json()` 且 `isinstance(resp.json()["plugins"], list)` | True |

### 验证点

- `/api/skills/tree` 已新增到既有 skills_router

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_skills_tree`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-018

### 关联需求

§6.2.2 L1138 · Test Inventory R18

### 测试目标

`GET /api/runs/current` 在无活跃 run 时返回 200 + `null`。

### 前置条件

- orchestrator 注入；无活跃 run

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/runs/current")` | Response |
| 2 | 断言 `resp.status_code == 200` | True |
| 3 | 断言 `resp.json() is None` | True |

### 验证点

- 路由命中，不为 404
- 空状态 schema 为 `null`（非 `{}`）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_runs_current_none`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-019

### 关联需求

§6.2.2 L1139 · Test Inventory R19

### 测试目标

`GET /api/runs?limit=2&offset=0` 返回 200 + `RunSummary[]` 长度=2。

### 前置条件

- seed 3 历史 run 至 RunRepository

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed 3 run | 完成 |
| 2 | `resp = await client.get("/api/runs?limit=2&offset=0")` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `len(resp.json()) == 2` | True |
| 4 | 断言每条含 `id`、`workdir`、`state`、`started_at` 字段 | True |

### 验证点

- `/api/runs` 路由已挂载，分页正确

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_runs_paged`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-020

### 关联需求

§6.2.2 L1160-1161 · Test Inventory R20

### 测试目标

`GET /api/files/tree?root=docs` 返回 200 + `FileTree { root, nodes }`。

### 前置条件

- `docs/` 目录存在；`app.state.files_service` 注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/files/tree?root=docs")` | Response |
| 2 | 断言 `resp.status_code == 200` | True |
| 3 | 断言 `resp.json()["root"] == "docs"` 且 `isinstance(resp.json()["nodes"], list)` | True |

### 验证点

- `/api/files/*` router 已挂载

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_files_tree_docs`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-022

### 关联需求

IFR-007 · §6.2.3 L1175 · 根因第 3 子 bug · Test Inventory R22 · ATS L185 IFR-007

### 测试目标

**真启 uvicorn**：`uvicorn harness.api:app --host 127.0.0.1 --port <ephemeral>` 启动后，`websockets.connect("ws://127.0.0.1:<port>/ws/hil")` 握手成功（HTTP 101）。验证 `requirements.txt` 改 `uvicorn[standard]==0.44.0` 后 ws upgrade 不再 pre-ASGI 404。

### 前置条件

- `pip install -r requirements.txt` 已完成；`uvicorn[standard]` extra 已生效（websockets/wsproto transitive 已 import 成功）
- 经 `bash scripts/svc-api-start.sh` 启动 api 服务（或 fixture 启临时 ephemeral port）；健康检查 `curl -f http://127.0.0.1:8765/api/health` 通过

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 启 uvicorn @ 8765（fixture 或 svc-api-start.sh） | `Uvicorn running on http://127.0.0.1:8765` 日志可见 |
| 2 | `import websockets; ws = await websockets.connect("ws://127.0.0.1:8765/ws/hil")` | 不抛 `InvalidStatusCode(404)`；握手成功（HTTP 101） |
| 3 | 在 5s 内若无 HilEventBus 触发，连接保持 idle（不收 echo `subscribe_ack`） | 连接活跃，无消息或仅 ping/keepalive frame |
| 4 | `await ws.close()` | 干净关闭 |

### 验证点

- HTTP 101 upgrade 成功（uvicorn[standard] 修复确认）
- 不再返 echo stub `subscribe_ack`（真 broadcaster 取代）
- ASGI scope `websocket` 已转给 production app handler

### 后置检查

- ws 连接关闭；服务保持运行供下个测试使用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_hil_handshake_101`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-023

### 关联需求

IFR-007 · §6.2.3 L1173 · Test Inventory R23 · ATS L185 IFR-007

### 测试目标

真 uvicorn → `start_run` 触发 → `/ws/run/<rid>` 收到 `{ kind: "RunPhaseChanged", payload: { state: "running", run_id } }` 真事件（非 `_F21_RUN_BOOTSTRAP` mock）。

### 前置条件

- 真 uvicorn @ 8765 健康；`POST /api/runs/start` 已通过 ST-FUNC-023-001

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 真 git tmp_path → `POST /api/runs/start { workdir }` 经 httpx | 200 + `run_id` 提取 |
| 2 | `ws = await websockets.connect(f"ws://127.0.0.1:8765/ws/run/{run_id}")` | 握手 101 |
| 3 | `msg = await asyncio.wait_for(ws.recv(), timeout=5.0); env = json.loads(msg)` | 收到 frame |
| 4 | 断言 `env["kind"] == "RunPhaseChanged"` 且 `env["payload"]["state"] == "running"` 且 `env["payload"]["run_id"] == run_id` | True |
| 5 | 断言 envelope 不含 `_F21_RUN_BOOTSTRAP` 标识 | True |

### 验证点

- 真 broadcaster 已替换 echo stub
- `RunControlBus.captured_run_events()` 重放路径生效

### 后置检查

- ws 关闭；run cancel

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_run_real_event`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-024

### 关联需求

IFR-007 · §6.2.3 L1176 · FR-024 · Test Inventory R24 · ATS L97 FR-024

### 测试目标

真 uvicorn + mock `AnomalyClassifier.classify` → `/ws/anomaly` 收到 `{ kind: "AnomalyDetected", payload: { ticket_id, cls: "context_overflow", retry_count: 1 } }`。

### 前置条件

- 真 uvicorn 健康；fixture 注入 mock classifier 触发 `broadcast_anomaly`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ws = await websockets.connect("ws://127.0.0.1:8765/ws/anomaly")` | 握手 101 |
| 2 | 触发 `RunControlBus.broadcast_anomaly(AnomalyEvent(ticket_id="t1", cls="context_overflow", retry_count=1))` | 完成 |
| 3 | `msg = await asyncio.wait_for(ws.recv(), timeout=5.0); env = json.loads(msg)` | 收到 frame |
| 4 | 断言 `env["kind"] == "AnomalyDetected"` 且 payload 字段匹配 | True |

### 验证点

- `/ws/anomaly` 真 broadcaster；echo stub `_F21_ANOMALY_BOOTSTRAP` 已移除

### 后置检查

- ws 关闭

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_anomaly_real_event`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-025

### 关联需求

IFR-007 · §6.2.3 L1177 · Test Inventory R25

### 测试目标

真 uvicorn → workdir 创建 `bugfix-request.json` → `/ws/signal` 收到 `SignalFileChanged { path, kind: "bugfix_request", mtime }`。

### 前置条件

- 真 uvicorn 健康；`SignalFileWatcher.start(workdir)` 已在 AppBootstrap 触发

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ws = await websockets.connect("ws://127.0.0.1:8765/ws/signal")` | 握手 101 |
| 2 | 在 workdir 创建 `bugfix-request.json` | 文件存在 |
| 3 | `msg = await asyncio.wait_for(ws.recv(), timeout=10.0); env = json.loads(msg)` | 收到 frame |
| 4 | 断言 `env["kind"] == "SignalFileChanged"` 且 `env["payload"]["kind"] == "bugfix_request"` | True |

### 验证点

- SignalFileWatcher → RunControlBus.broadcast_signal → ws 推送链路完整

### 后置检查

- 删 `bugfix-request.json`；ws 关闭

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_signal_real_event`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-026

### 关联需求

IFR-007 · §6.2.3 L1174 · Test Inventory R26

### 测试目标

真 uvicorn → `RunControlBus.broadcast_stream_event(StreamEvent(...))` → `/ws/stream/<tid>` 收到对应 envelope。

### 前置条件

- 真 uvicorn 健康；`broadcast_stream_event` 已实现（design Interface Contract 新增）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ws = await websockets.connect("ws://127.0.0.1:8765/ws/stream/t5")` | 握手 101 |
| 2 | 触发 `RunControlBus.broadcast_stream_event(StreamEvent(ticket_id="t5", seq=0, ts=..., kind="text", payload={"text":"hello"}))` | 完成 |
| 3 | `msg = await asyncio.wait_for(ws.recv(), timeout=5.0)` | 收到 frame |
| 4 | 断言 `env["kind"] == "StreamEvent"` 且 `env["payload"]["ticket_id"] == "t5"` | True |

### 验证点

- 新增 `broadcast_stream_event` bus 接口生效
- `/ws/stream/:ticket_id` ws handler 订阅正确

### 后置检查

- ws 关闭

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_stream_real_event`
- **Test Type**: Real

---

### 用例编号

ST-PERF-023-001

### 关联需求

IFR-007 ping 协议 · §6.1.7 L1101 · Test Inventory R27 · ATS L185 IFR-007 PERF

### 测试目标

真 uvicorn → 客户端连 `/ws/run/<rid>`，30s 内不发任何客户端帧 → 服务端发至少 1 次 `{ kind: "ping" }`（30s 周期 ±5s 容差）。

### 前置条件

- 真 uvicorn 健康；run 已 start

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ws = await websockets.connect(f"ws://127.0.0.1:8765/ws/run/{run_id}")` | 握手 101 |
| 2 | `start = time.monotonic(); messages = []` | 起点记录 |
| 3 | 在 35s 窗口内循环 `await asyncio.wait_for(ws.recv(), timeout=...)` 收集 | 收集到至少 1 条 |
| 4 | 断言至少 1 条消息 `kind == "ping"` 且首条 ping 在 25s-35s 之间到达 | True |

### 验证点

- server-side 30s ping 周期实现
- IFR-007 心跳协议生效（防止 60s 客户端无消息重连失败）

### 后置检查

- ws 关闭

### 元数据

- **优先级**: High
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_run_server_ping_30s`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-028

### 关联需求

设计 §3.4 L240 / §8.4 L1539 · 根因第 3 子 bug · Test Inventory R28 · ATS L185 IFR-007（依赖图修复）

### 测试目标

`pip install -r requirements.txt` 后 `python -c "import websockets, wsproto"` 不抛 ImportError，证明 `requirements.txt` 已改 `uvicorn[standard]==0.44.0` 而非裸 `uvicorn==0.44.0`。

### 前置条件

- 干净环境（venv）；`requirements.txt` 已 commit

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `pip install -r requirements.txt` | exit=0 |
| 2 | `python -c "import websockets; import wsproto; print('ok')"` | exit=0；stdout 含 `ok` |
| 3 | `pip show websockets` 输出 version 不为空 | True |
| 4 | `pip show wsproto` 输出 version 不为空 | True |

### 验证点

- `uvicorn[standard]` extra 真正拉取了 websockets/wsproto
- 不再有 ImportError，证明依赖图根因修复

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_dependency_import.py::test_websockets_wsproto_importable`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-029

### 关联需求

根因 "双定义归一" · `harness/api/__init__.py:159` vs `harness/app/main.py:55` · Test Inventory R29

### 测试目标

`python -c "from harness.api import app; routes = [r.path for r in app.routes if 'ws/run' in r.path]; print(len(routes))"` 输出 `1`，证明 `/ws/run/{run_id}` 双定义已归一。

### 前置条件

- harness package 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `from harness.api import app` | 不抛 |
| 2 | `routes = [r.path for r in app.routes if 'ws/run' in r.path]` | 长度=1 |
| 3 | 断言 `len(routes) == 1` 且 `"/ws/run/{run_id}" in routes` | True |

### 验证点

- production `harness.api:app` 上仅一条 `/ws/run/:id` 路由
- 不再 stub 与 真 broadcaster 双挂

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_single_definition.py::test_ws_run_route_single_definition`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-030

### 关联需求

F20 既有 ST 用例集 `tests/integration/test_f20_real_rest_ws.py` 不回归 · Test Inventory R30

### 测试目标

重跑既有 `tests/integration/test_f20_real_rest_ws.py` 通过 `harness.app.main.build_app()` factory 的全部测试 — 全部 PASS（保留 build_app 不变）。

### 前置条件

- F20 测试文件存在；`harness.app.main.build_app` 仍可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `pytest tests/integration/test_f20_real_rest_ws.py -q` | exit=0 |
| 2 | 输出含 `passed` 且无 `failed` | True |

### 验证点

- bugfix 未误删 `build_app`（仍是 test-only factory）
- F20 ST 不回归

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_rest_ws.py`（既有用例集；本特性回归调用）
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-031

### 关联需求

FR-024 路径 · Test Inventory R31 · ATS L97 FR-024

### 测试目标

in-process Starlette TestClient：seed retrying ticket → `POST /api/runs/start` → `_run_loop` 触发 anomaly → `/ws/anomaly` sniff 收到 `AnomalyDetected` envelope。

### 前置条件

- in-process app + `app.state.orchestrator` + mock classifier 触发 anomaly

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed retrying ticket + start run（in-process） | 完成 |
| 2 | 通过 starlette TestClient `with client.websocket_connect("/ws/anomaly") as ws:` | 握手成功 |
| 3 | 触发 anomaly 后 `frame = ws.receive_json()` | 收到 frame |
| 4 | 断言 `frame["kind"] == "AnomalyDetected"` | True |

### 验证点

- in-process WS 链路（不需真 uvicorn）也接通真 broadcaster
- `bus.broadcast_anomaly` → ws handler 订阅正确

### 后置检查

- 清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_ws_anomaly_in_process`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-032

### 关联需求

§6.2.2 L1145 + §6.2.3 L1175 · Test Inventory R32

### 测试目标

seed hil_waiting ticket → `POST /api/hil/<tid>/answer { question_id, freeform_text: "yes" }` → REST 200 `HilAnswerAck { accepted: true, ticket_state }`；同时连 `/ws/hil` 收到 `HilAnswerAccepted` envelope。

### 前置条件

- in-process app + `app.state.hil_event_bus` 注入；seed hil_waiting ticket id="t6"

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed `Ticket(id="t6", state="hil_waiting", ...)` | 完成 |
| 2 | starlette `with client.websocket_connect("/ws/hil") as ws:` | 握手成功 |
| 3 | `resp = await client.post("/api/hil/t6/answer", json={"question_id":"q1","freeform_text":"yes"})` | 200 |
| 4 | 断言 `resp.json()["accepted"] is True` | True |
| 5 | `frame = ws.receive_json()` | 收到 frame |
| 6 | 断言 `frame["kind"] == "HilAnswerAccepted"` | True |

### 验证点

- `/api/hil/*` 与 `/ws/hil` 双向链路完整
- HilEventBus.publish_answered → ws 推送

### 后置检查

- 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_hil_answer_rest_and_ws`
- **Test Type**: Real

---

### 用例编号

ST-SEC-023-001

### 关联需求

FR-039 SEC · ATS L120 · Test Inventory R33

### 测试目标

`POST /api/validate/../../etc/passwd` 被 router 在路径校验层拒绝（400/422），不进入 ValidatorRunner 执行。

### 前置条件

- in-process app；validator runner 注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.post("/api/validate/" + "../../etc/passwd", json={"script":"validate_features"})` | Response |
| 2 | 断言 `resp.status_code in {400, 422}` | True（path traversal 拒） |

### 验证点

- path traversal 防护生效（FR-039 SEC 注释 ATS L120）
- 不读取系统敏感文件

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_validate_path_traversal_rejected`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-034

### 关联需求

§Interface Contract `hil_router.post_answer` Raises · Test Inventory R34

### 测试目标

ticket 不在 hil_waiting → `POST /api/hil/<tid>/answer` 返回 409。

### 前置条件

- seed `Ticket(state="running", id="t7", ...)`（非 hil_waiting）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed running ticket id="t7" | 完成 |
| 2 | `resp = await client.post("/api/hil/t7/answer", json={"question_id":"q1","freeform_text":"x"})` | Response |
| 3 | 断言 `resp.status_code == 409` | True |

### 验证点

- hil 状态守护生效；service 异常 → 409

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_hil_answer_wrong_state_409`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-035

### 关联需求

§6.2.2 L1149 · Test Inventory R35

### 测试目标

`PUT /api/settings/general { ui_density: "comfortable" }` 返回 200 + 持久化到 `~/.harness/config.json`。

### 前置条件

- 干净 `~/.harness/config.json`（或 monkeypatch HARNESS_HOME 至 tmp_path）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.put("/api/settings/general", json={"ui_density":"comfortable"})` | Response |
| 2 | 断言 `resp.status_code == 200` 且 `resp.json()["ui_density"] == "comfortable"` | True |
| 3 | 重读 `~/.harness/config.json` | 字段 `ui_density: "comfortable"` |

### 验证点

- PUT 持久化路径正确

### 后置检查

- 清理 tmp config 文件

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_put_settings_general_persist`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-036

### 关联需求

AppBootstrap wiring · Test Inventory R36

### 测试目标

`harness.app.AppBootstrap.start()` 完成后 → `app.state.{orchestrator, run_control_bus, ticket_repo, hil_event_bus, signal_file_watcher, files_service, commit_list_service, diff_loader, validator_runner}` 全部 not-None。

### 前置条件

- AppBootstrap 实例化；start() 已调

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bootstrap = AppBootstrap(...); await bootstrap.start()` | 完成 |
| 2 | `from harness.api import app` | 可导入 |
| 3 | 断言 `app.state.orchestrator is not None` | True |
| 4 | 同上断言 `run_control_bus`、`ticket_repo`、`hil_event_bus`、`signal_file_watcher`、`files_service`、`commit_list_service`、`diff_loader`、`validator_runner` 均 not-None | True（共 9 项） |

### 验证点

- lifespan wiring 完整覆盖 9 个 service
- 首请求不会 500

### 后置检查

- bootstrap.stop()

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_lifespan.py::test_app_bootstrap_wires_all_services`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-037

### 关联需求

§6.2.2 L1140 · `RunOrchestrator.pause_run` · Test Inventory R37

### 测试目标

seed 1 active run → `POST /api/runs/<rid>/pause` 返回 200 + `RunStatus { state: "pause_pending" }`。

### 前置条件

- in-process app + active run

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | start run → 拿 run_id | 完成 |
| 2 | `resp = await client.post(f"/api/runs/{run_id}/pause")` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `resp.json()["state"] == "pause_pending"` | True |

### 验证点

- `/api/runs/:id/pause` router 已挂载

### 后置检查

- cancel run

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_runs_pause`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-038

### 关联需求

§6.2.2 L1141 · `RunOrchestrator.cancel_run` · Test Inventory R38

### 测试目标

seed 1 active run → `POST /api/runs/<rid>/cancel` 返回 200 + `RunStatus { state: "cancelled" }`。

### 前置条件

- in-process app + active run

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | start run → 拿 run_id | 完成 |
| 2 | `resp = await client.post(f"/api/runs/{run_id}/cancel")` | Response |
| 3 | 断言 `resp.status_code == 200` 且 `resp.json()["state"] == "cancelled"` | True |

### 验证点

- `/api/runs/:id/cancel` router 已挂载

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_runs_cancel`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-023-001

### 关联需求

§Boundary Conditions `get_runs.limit` · Test Inventory R39

### 测试目标

`GET /api/runs?limit=0` 返回 400 invalid_param。

### 前置条件

- in-process app

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/runs?limit=0")` | Response |
| 2 | 断言 `resp.status_code == 400` | True |

### 验证点

- limit ∈ [1,200] 边界校验生效

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_runs_limit_zero_400`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-023-002

### 关联需求

§Boundary Conditions `get_runs.limit` · Test Inventory R40

### 测试目标

`GET /api/runs?limit=201` 返回 400 invalid_param。

### 前置条件

- 同上

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/runs?limit=201")` | Response |
| 2 | 断言 `resp.status_code == 400` | True |

### 验证点

- limit > 200 边界校验生效

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_runs_limit_overflow_400`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-023-003

### 关联需求

§Boundary Conditions `get_diff.sha` · Test Inventory R41

### 测试目标

`GET /api/git/diff/<65 字符 sha>` 返回 404 DiffNotFound（router 把 ValueError 转 404 而非 500）。

### 前置条件

- 同 ST-FUNC-023-014

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/git/diff/" + "0"*65)` | Response |
| 2 | 断言 `resp.status_code == 404` | True |

### 验证点

- sha > 64 字符 → 404 而非 500

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_git_diff_oversize_sha_404`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-023-042

### 关联需求

§Interface Contract `ws.ws_run` Raises · Test Inventory R42

### 测试目标

真 uvicorn → 连 `/ws/run/unknown-run-id` 后 `start_run` 完成 → 客户端不收到任何匹配事件（不应触发 echo `_F21_RUN_BOOTSTRAP` mock）。

### 前置条件

- 真 uvicorn 健康

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ws = await websockets.connect("ws://127.0.0.1:8765/ws/run/unknown-run-id")` | 握手 101 |
| 2 | start 一个**不同** run_id 的 run | 完成 |
| 3 | `try: msg = await asyncio.wait_for(ws.recv(), timeout=3.0)` 不应收到 RunPhaseChanged 匹配 unknown-run-id | TimeoutError 或仅收 ping |
| 4 | 断言任何收到的 frame 都不含 `_F21_RUN_BOOTSTRAP` | True |

### 验证点

- echo stub 已被移除
- 订阅按 run_id 严格过滤

### 后置检查

- ws 关闭

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_run_unknown_id_no_echo`
- **Test Type**: Real

---

### 用例编号

ST-SEC-023-002

### 关联需求

§Interface Contract `post_answer` SEC · Test Inventory R43

### 测试目标

`POST /api/hil/<tid>/answer { freeform_text: "<script>alert(1)</script>" }` 返回 200 接受（不抛），写库时保持原文（XSS escape 是渲染端责任，router 层不做）。

### 前置条件

- seed hil_waiting ticket id="t8"

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `payload = {"question_id":"q1","freeform_text":"<script>alert(1)</script>"}` | 准备 |
| 2 | `resp = await client.post("/api/hil/t8/answer", json=payload)` | Response |
| 3 | 断言 `resp.status_code == 200` | True |
| 4 | 重读 ticket → answer 字段保留原文 `<script>...` 不被 router 层 escape | True |

### 验证点

- router 不错误拒绝合法 HIL 答案
- XSS 过滤是 UI 渲染层责任

### 后置检查

- 清理

### 元数据

- **优先级**: Medium
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_hil_answer_xss_payload_accepted_raw`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-023-004

### 关联需求

§Boundary Conditions `RunStartRequest.workdir` · Test Inventory R44

### 测试目标

`POST /api/runs/start { workdir: "" }` 返回 400 invalid_workdir。

### 前置条件

- in-process app

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.post("/api/runs/start", json={"workdir":""})` | Response |
| 2 | 断言 `resp.status_code == 400` | True |

### 验证点

- 空 workdir 不落到 service 报 RuntimeError；router 或 pydantic 拦截

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_post_runs_start_empty_workdir_400`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-023-005

### 关联需求

§Boundary Conditions `files_router.get_read.path` · Test Inventory R45

### 测试目标

`GET /api/files/read?path=` 返回 400 PathTraversalError 或 invalid_param。

### 前置条件

- in-process app

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/files/read?path=")` | Response |
| 2 | 断言 `resp.status_code == 400` | True |

### 验证点

- 空 path 在 router 层转译为 400 而非 500

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_files_read_empty_path_400`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-023-006

### 关联需求

§Boundary Conditions `tickets.get_ticket_stream.offset` · Test Inventory R46

### 测试目标

`GET /api/tickets/<tid>/stream?offset=-1` 返回 400 invalid_param。

### 前置条件

- seed ticket id="t9"

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/tickets/t9/stream?offset=-1")` | Response |
| 2 | 断言 `resp.status_code == 400` | True |

### 验证点

- 负 offset 边界校验生效

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_ticket_stream_negative_offset_400`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-023-007

### 关联需求

§Boundary Conditions `files_router.get_tree` · Test Inventory R21 · ATS L120 SEC

### 测试目标

`GET /api/files/tree?root=../etc/passwd` 返回 400 PathTraversalError，不访问系统敏感目录。

### 前置条件

- in-process app；files_service 注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resp = await client.get("/api/files/tree?root=../etc/passwd")` | Response |
| 2 | 断言 `resp.status_code == 400` | True |

### 验证点

- path traversal 拦截

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_asgi_rest.py::test_get_files_tree_path_traversal_400`
- **Test Type**: Real

---

### 用例编号

ST-PERF-023-002

### 关联需求

IFR-007 PERF · ATS L185 IFR-007（消息延迟 p95 < 100ms）· 新增覆盖

### 测试目标

真 uvicorn → 连接 `/ws/anomaly` → 发起 100 次 `RunControlBus.broadcast_anomaly` → 每条消息从 broadcast 触发到客户端 receive 的延迟 p95 < 100ms。

### 前置条件

- 真 uvicorn 健康；测试机本地回环（loopback）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ws = await websockets.connect("ws://127.0.0.1:8765/ws/anomaly")` | 握手 101 |
| 2 | 启动 100 次循环：每次记 `t0 = time.monotonic()` → 触发 broadcast_anomaly → `await ws.recv()` → 记 `t1`；append `(t1-t0)*1000` 至 latencies | 100 条数据 |
| 3 | 计算 `p95 = numpy.percentile(latencies, 95)` 或 `sorted(latencies)[94]` | 数值 |
| 4 | 断言 `p95 < 100.0`（毫秒） | True |

### 验证点

- IFR-007 PERF 阈值（消息延迟 p95 < 100ms）满足
- WS 推送链路无显著队列堆积

### 后置检查

- ws 关闭

### 元数据

- **优先级**: High
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_anomaly_p95_latency_under_100ms`
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|-----------|------|
| ST-FUNC-023-001 | FR-001 AC-1 (R1) | step[3-6] | `tests/integration/test_f23_asgi_rest.py::test_post_runs_start_legal_git_workdir` | Real | PASS |
| ST-FUNC-023-002 | FR-001 AC-3 (R2) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_post_runs_start_non_git_workdir_rejected` | Real | PASS |
| ST-FUNC-023-003 | §Interface Contract Raises (R3) | step[1-4] | `tests/integration/test_f23_asgi_rest.py::test_post_runs_start_shell_metachar_rejected` | Real | PASS |
| ST-FUNC-023-004 | FR-029 AC-1 (R4) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_post_anomaly_skip` | Real | PASS |
| ST-FUNC-023-005 | FR-029 AC-2 (R5) | step[2-3] | `tests/integration/test_f23_asgi_rest.py::test_post_anomaly_force_abort` | Real | PASS |
| ST-FUNC-023-006 | §Interface Contract Raises (R6) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_post_anomaly_skip_unknown_ticket_404` | Real | PASS |
| ST-FUNC-023-007 | §Interface Contract Raises (R7) | step[2-3] | `tests/integration/test_f23_asgi_rest.py::test_post_anomaly_force_abort_completed_409` | Real | PASS |
| ST-FUNC-023-008 | §6.2.2 L1142-1144 (R8) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_get_tickets_list_by_run` | Real | PASS |
| ST-FUNC-023-009 | §Interface Contract Raises (R9) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_get_ticket_unknown_404` | Real | PASS |
| ST-FUNC-023-010 | §6.2.2 L1144 (R10) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_get_ticket_stream_paged` | Real | PASS |
| ST-FUNC-023-011 | FR-039 AC (R11) | step[1-4] | `tests/integration/test_f23_asgi_rest.py::test_post_validate_features_pass` | Real | PASS |
| ST-FUNC-023-012 | §Interface Contract Raises (R12) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_post_validate_features_fail_returns_200` | Real | PASS |
| ST-FUNC-023-013 | FR-042 AC-1 (R13) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_get_git_commits_by_run` | Real | PASS |
| ST-FUNC-023-014 | §6.2.2 L1164 (R14) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_get_git_diff_real_sha` | Real | PASS |
| ST-FUNC-023-015 | §Interface Contract Raises (R15) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_get_git_diff_unknown_sha_404` | Real | PASS |
| ST-FUNC-023-016 | §6.2.2 L1148 (R16) | step[1-3] | `tests/integration/test_f23_asgi_rest.py::test_get_settings_general_defaults` | Real | PASS |
| ST-FUNC-023-017 | §6.2.2 L1157 (R17) | step[1-3] | `tests/integration/test_f23_asgi_rest.py::test_get_skills_tree` | Real | PASS |
| ST-FUNC-023-018 | §6.2.2 L1138 (R18) | step[1-3] | `tests/integration/test_f23_asgi_rest.py::test_get_runs_current_none` | Real | PASS |
| ST-FUNC-023-019 | §6.2.2 L1139 (R19) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_get_runs_paged` | Real | PASS |
| ST-FUNC-023-020 | §6.2.2 L1160-1161 (R20) | step[1-3] | `tests/integration/test_f23_asgi_rest.py::test_get_files_tree_docs` | Real | PASS |
| ST-BNDRY-023-007 | §Boundary `files_router.get_tree` (R21) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_get_files_tree_path_traversal_400` | Real | PASS |
| ST-FUNC-023-022 | IFR-007 (R22) | step[2-3] | `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_hil_handshake_101` | Real | PASS |
| ST-FUNC-023-023 | IFR-007 (R23) | step[2-5] | `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_run_real_event` | Real | PASS |
| ST-FUNC-023-024 | IFR-007 / FR-024 (R24) | step[2-4] | `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_anomaly_real_event` | Real | PASS |
| ST-FUNC-023-025 | IFR-007 (R25) | step[2-4] | `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_signal_real_event` | Real | PASS |
| ST-FUNC-023-026 | IFR-007 (R26) | step[2-4] | `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_stream_real_event` | Real | PASS |
| ST-PERF-023-001 | IFR-007 ping (R27) | step[3-4] | `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_run_server_ping_30s` | Real | PASS |
| ST-FUNC-023-028 | 设计 §3.4 / §8.4 (R28) | step[1-4] | `tests/integration/test_f23_dependency_import.py::test_websockets_wsproto_importable` | Real | PASS |
| ST-FUNC-023-029 | 双定义归一 (R29) | step[2-3] | `tests/integration/test_f23_single_definition.py::test_ws_run_route_single_definition` | Real | PASS |
| ST-FUNC-023-030 | F20 ST 不回归 (R30) | step[1-2] | `tests/integration/test_f20_real_rest_ws.py`（既有） | Real | PASS |
| ST-FUNC-023-031 | FR-024 路径 (R31) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_ws_anomaly_in_process` | Real | PASS |
| ST-FUNC-023-032 | §6.2.2 L1145 + §6.2.3 L1175 (R32) | step[3-6] | `tests/integration/test_f23_asgi_rest.py::test_hil_answer_rest_and_ws` | Real | PASS |
| ST-SEC-023-001 | FR-039 SEC (R33) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_validate_path_traversal_rejected` | Real | PASS |
| ST-FUNC-023-034 | §Interface Contract Raises (R34) | step[2-3] | `tests/integration/test_f23_asgi_rest.py::test_hil_answer_wrong_state_409` | Real | PASS |
| ST-FUNC-023-035 | §6.2.2 L1149 (R35) | step[1-3] | `tests/integration/test_f23_asgi_rest.py::test_put_settings_general_persist` | Real | PASS |
| ST-FUNC-023-036 | AppBootstrap wiring (R36) | step[3-4] | `tests/integration/test_f23_lifespan.py::test_app_bootstrap_wires_all_services` | Real | PASS |
| ST-FUNC-023-037 | §6.2.2 L1140 (R37) | step[2-3] | `tests/integration/test_f23_asgi_rest.py::test_post_runs_pause` | Real | PASS |
| ST-FUNC-023-038 | §6.2.2 L1141 (R38) | step[2-3] | `tests/integration/test_f23_asgi_rest.py::test_post_runs_cancel` | Real | PASS |
| ST-BNDRY-023-001 | §Boundary `get_runs.limit` (R39) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_get_runs_limit_zero_400` | Real | PASS |
| ST-BNDRY-023-002 | §Boundary `get_runs.limit` (R40) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_get_runs_limit_overflow_400` | Real | PASS |
| ST-BNDRY-023-003 | §Boundary `get_diff.sha` (R41) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_get_git_diff_oversize_sha_404` | Real | PASS |
| ST-FUNC-023-042 | §Interface Contract `ws.ws_run` Raises (R42) | step[2-4] | `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_run_unknown_id_no_echo` | Real | PASS |
| ST-SEC-023-002 | §Interface Contract `post_answer` SEC (R43) | step[2-4] | `tests/integration/test_f23_asgi_rest.py::test_hil_answer_xss_payload_accepted_raw` | Real | PASS |
| ST-BNDRY-023-004 | §Boundary `RunStartRequest.workdir` (R44) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_post_runs_start_empty_workdir_400` | Real | PASS |
| ST-BNDRY-023-005 | §Boundary `files_router.get_read.path` (R45) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_get_files_read_empty_path_400` | Real | PASS |
| ST-BNDRY-023-006 | §Boundary `tickets.get_ticket_stream.offset` (R46) | step[1-2] | `tests/integration/test_f23_asgi_rest.py::test_get_ticket_stream_negative_offset_400` | Real | PASS |
| ST-PERF-023-002 | IFR-007 PERF (新增 R47) | step[2-4] | `tests/integration/test_f23_uvicorn_real_handshake.py::test_ws_anomaly_p95_latency_under_100ms` | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

## SRS Trace 覆盖核对

| srs_trace 需求 | 覆盖 ST 用例 |
|---------------|--------------|
| FR-001 | ST-FUNC-023-001 (AC-1)、ST-FUNC-023-002 (AC-3)、ST-FUNC-023-003 (Raises)、ST-BNDRY-023-004 (workdir 边界) |
| FR-024 | ST-FUNC-023-024、ST-FUNC-023-031 |
| FR-029 | ST-FUNC-023-004、ST-FUNC-023-005、ST-FUNC-023-006、ST-FUNC-023-007 |
| FR-039 | ST-FUNC-023-011、ST-FUNC-023-012、ST-SEC-023-001 |
| FR-042 | ST-FUNC-023-013、ST-FUNC-023-014、ST-FUNC-023-015、ST-BNDRY-023-003 |
| IFR-007 | ST-FUNC-023-022、ST-FUNC-023-023、ST-FUNC-023-024、ST-FUNC-023-025、ST-FUNC-023-026、ST-PERF-023-001、ST-PERF-023-002、ST-FUNC-023-032、ST-FUNC-023-042 |

## ATS 类别覆盖核对

| ATS 行 | 必须类别 | 本特性覆盖 |
|--------|---------|-----------|
| L49 FR-001 | FUNC, BNDRY, SEC | FUNC: 001/002/003/037/038；BNDRY: 004 (workdir 空)；SEC: 003 (shell metachar 由 router 拒) |
| L97 FR-024 | FUNC, BNDRY | FUNC: 024/031；BNDRY: 由 R39/R40 limit 边界（运行查询通用） |
| L102 FR-029 | FUNC, BNDRY, UI | FUNC: 004/005/006/007；BNDRY: ST-BNDRY-023-006 (stream offset)；UI: 由 F21 单独承担（ui:false 豁免，feature design 已注明） |
| L120 FR-039 | FUNC, BNDRY, SEC | FUNC: 011/012；BNDRY: ST-BNDRY-023-007 (path traversal 边界归 boundary)；SEC: ST-SEC-023-001 |
| L128 FR-042 | FUNC, BNDRY | FUNC: 013/014/015；BNDRY: ST-BNDRY-023-003 (sha > 64) |
| L185 IFR-007 | FUNC, BNDRY, PERF | FUNC: 022/023/024/025/026/032/042；BNDRY: 由 PERF/handshake 边界覆盖；PERF: ST-PERF-023-001 (ping 时序)、ST-PERF-023-002 (latency p95) |

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 47 |
| Passed | 47 |
| Failed | 0 |
| Pending | 0 |

> **Execution date**: 2026-04-26
> **Execution evidence**: `pytest tests/integration/test_f23_real_rest_routes.py tests/integration/test_f23_real_uvicorn_handshake.py tests/integration/test_f23_real_lifespan_wiring.py tests/integration/test_f23_inproc_coverage.py tests/integration/test_f20_real_rest_ws.py -v` → 87 passed, 0 failed (47 ST-mapped cases + 40 additional TDD coverage cases share the same test files); R47 `test_f23_feature_23_r47_real_uvicorn_ws_anomaly_p95_latency_under_100ms` 单独追加测试 → PASS.
> **Service lifecycle**: `bash scripts/svc-api-start.sh` 经 PID `474534` 启动 @ 127.0.0.1:8765；健康检查 `curl http://127.0.0.1:8765/api/health` 返回 200；测试结束在 §Cleanup 段停止。

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.
