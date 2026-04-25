# 测试用例集: F20 · Bk-Loop — Run Orchestrator · Recovery · Subprocess

**Feature ID**: 20
**关联需求**: FR-001, FR-002, FR-003, FR-004, FR-024, FR-025, FR-026, FR-027, FR-028, FR-029, FR-039, FR-040, FR-042, FR-047, FR-048, NFR-003, NFR-004, NFR-015, NFR-016, IFR-003（ATS L49-52, L97-101, L120-121, L128, L143-144, L159-160, L171-172, L181；必须类别 FUNC / BNDRY / SEC / PERF / INTG；UI 类别由 F21/F22 单独承担——本特性 `ui:false`）
**日期**: 2026-04-25
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则（FR-001/002/003/004/024/025/026/027/028/029/039/040/042/047/048 + NFR-003/004/015/016 + IFR-003）、ATS L49-52 / L97-101 / L120-121 / L128 / L143-144 / L159-160 / L171-172 / L181 类别约束、Feature Design Test Inventory T01–T50、可观察接口（`harness.orchestrator.run.RunOrchestrator` / `harness.orchestrator.supervisor.TicketSupervisor` + `DepthGuard` / `harness.orchestrator.phase_route.PhaseRouteInvoker` + `PhaseRouteResult` / `harness.orchestrator.signal_watcher.SignalFileWatcher` / `harness.orchestrator.bus.RunControlBus` / `harness.orchestrator.run_lock.RunLock` / `harness.recovery.anomaly.AnomalyClassifier` / `harness.recovery.retry.RetryPolicy` + `RetryCounter` / `harness.recovery.watchdog.Watchdog` / `harness.subprocess.git.GitTracker` / `harness.subprocess.validator.ValidatorRunner` 公开 API、FastAPI `TestClient` 经 `/api/runs/start|pause|cancel`、`/api/anomaly/:ticket/skip|force-abort`、`/api/git/commits`、`/api/git/diff/:sha`、`/api/files/tree`、`/api/files/read`、`/api/validate/:file` 路由、WebSocket `/ws/run/:id` · `/ws/anomaly` · `/ws/signal` envelope、`os.kill` SIGTERM/SIGKILL 调用观测、`subprocess` argv 与 `cwd` 观测、`git rev-parse HEAD` / `git log --oneline` 真实子进程、`watchdog` Observer 真实 inotify 事件、`filelock` 真实文件互斥）推导，不阅读实现源码。
> - **Specification resolutions applied from Feature Design Clarification Addendum**：9 条已批准 assumption（FR-001 5s 软目标 / NFR-003-004 retry_count 起 0 / GitCommit 字段集 / FR-048 200ms 防抖 / FR-027 v1 写死 1800s / `validate_*.py --json` 协议 / EscalationEmitter 双 channel 推送 / FR-003 bugfix>increment 优先级 / NFR-016 filelock acquire timeout=0.5s），见 `docs/features/20-f20-bk-loop-run-orchestrator-recovery-su.md` §Clarification Addendum；本文档预期结果均按已批准处置撰写。
> - **`feature.ui == false` → 本特性无 UI 类别用例**。ATS L52 / L102 / L121 / L144 在 FR-004 / FR-029 / FR-040 / FR-048 行列出 UI 仅是为了对齐 F21（RunOverview / HILInbox / TicketStream）/ F22（CommitHistory / ProcessFiles）的视觉表面——这些 UI 表面由 F21/F22 独立 ST 承担，本特性覆盖的是后端 Run lifecycle / Recovery / Subprocess 契约表面。Feature Design Visual Rendering Contract = N/A（backend-only feature），对应豁免不构成缺口。
> - 本特性以 **"Backend library + REST routes via FastAPI TestClient — no live api uvicorn server required"** 模式运行（env-guide §1.6 纯 CLI / library 模式 —— `pytest tests/test_f20_*.py tests/integration/test_f20_*.py`）。环境仅需 §2 `.venv` 激活；REST 路由 ST 用例使用 `fastapi.testclient.TestClient` 直接装载 `harness.api:app` 并通过 `monkeypatch.setenv("HARNESS_HOME", tmp_path)` 隔离持久化路径。INTG 类用例（T05/T14/T24/T27/T29/T33/T36/T47/T50）使用真实 subprocess / 真实 git / 真实 watchdog / 真实 sqlite / 真实 FastAPI TestClient + WebSocket，不 mock。
> - **手动测试**：本特性全部 50 条用例均自动化执行，无 `已自动化: No` 项；FR-004 / FR-029 / FR-040 / FR-048 涉及的 UI 体验（Pause 二次确认、异常 Skip/Force-Abort 按钮、自检按钮、信号文件徽章）由 F21/F22 ST 单独承担。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 40 |
| boundary | 8 |
| ui | 0 |
| security | 2 |
| performance | 1 |
| **合计** | **51** |

> **类别归属约定**：design Test Inventory 标 T05/T14/T24/T29/T33/T36/T47/T50 为 INTG/subprocess|timing|git|fs|concurrency|db|api+ws；ST 用例 ID 规范允许 CATEGORY ∈ {FUNC, BNDRY, UI, SEC, PERF}（见 `scripts/validate_st_cases.py` CASE_ID_PATTERN），与既有 F19 ST-FUNC-019-020（T35 real_fs）/ ST-FUNC-019-021（T36 real_keyring）惯例一致——本特性 INTG 用例归 functional 类别（black-box behavior 验证），具体判定脚注见相应用例元数据。负向占比：FUNC/error + BNDRY + SEC = 11（FUNC error：T02/T04/T07/T18/T19/T22/T25/T28/T31 等）+ 8 + 2 ≥ **21 / 51 ≈ 41% > 40%**。

> **Test Inventory → ST 用例 1:1 映射**：Feature Design 50 行 Test Inventory（T01-T50）一一对应 ST 用例；pytest 函数为 51 个（含 1 条额外 RetryPolicy 负边界 → ST-BNDRY-020-004 `test_retry_policy_negative_retry_count_raises`）。9 个 INTG pytest 函数（T05/T14/T24/T27/T29/T33/T36/T47/T50）作为独立 ST 用例。

---

### 用例编号

ST-FUNC-020-001

### 关联需求

FR-001 AC-1 · §Interface Contract `start_run` postcondition · §Design Alignment seq msg#1-7 · Feature Design Test Inventory T01 · ATS L49 FR-001

### 测试目标

验证 `RunOrchestrator.start_run(RunStartRequest(workdir=<legal git repo>))` 在 ≤5s 内返回 `RunStatus(state ∈ {starting, running}, workdir, started_at)`，并完成 `RunLock` 持有 + `runs` 表插入新行 + 后台 `_run_loop` 启动。覆盖 FR-001 EARS 主路径。

### 前置条件

- `.venv` 激活；`harness.orchestrator.run.RunOrchestrator` / `harness.orchestrator.schemas.RunStartRequest` / `harness.persistence.runs.RunRepository` 可导入
- `pytest tmp_path` 提供空白目录；`subprocess.run(["git", "init", str(tmp_path)])` 已成功（exit=0）
- `aiosqlite` schema 已 `Schema.ensure(conn)` 完成（F02 依赖）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `subprocess.run(["git","init",str(tmp_path)],check=True)` 初始化 git repo | exit=0；`tmp_path/.git/` 存在 |
| 2 | 构造 `req = RunStartRequest(workdir=str(tmp_path))` | pydantic 校验通过 |
| 3 | `orchestrator = RunOrchestrator(...)` 注入 mock 依赖（`PhaseRouteInvoker` 返 `PhaseRouteResult(ok=True, next_skill=None)`、`ToolAdapter` 不 spawn）| 构造成功 |
| 4 | `start_time = time.monotonic(); status = await orchestrator.start_run(req)` | 不抛异常 |
| 5 | 断言 `status.state in {"starting","running"}` 且 `status.workdir == str(tmp_path)` | True |
| 6 | 断言 `(tmp_path/".harness"/"run.lock").exists()` | True |
| 7 | 断言 `time.monotonic() - start_time <= 5.0`（FR-001 AC-1 软目标，Clarification #1）| True |

### 验证点

- start_run 在 5s 内返回（软目标，UI 立即看到 `state="starting"` 即满足"用户体感"，Clarification Addendum #1）
- `<workdir>/.harness/run.lock` 文件实际创建（filelock 已被持有）
- `runs` 表新行 state 为 `starting` 或 `running`（受 `_run_loop` 调度时机影响，两者均合法）
- 不 spawn ticket 仍能由 phase_route `next_skill=None` 路径自然完成

### 后置检查

- `tmp_path` 自动清理；`run.lock` 随 `cancel_run` / 进程结束释放

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t01_start_run_happy_path_enters_running`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-002

### 关联需求

FR-001 AC-3 · §Interface Contract `start_run` Raises `not_a_git_repo` · §State Diagram Idle→Failed · Test Inventory T02 · ATS L49 FR-001 SEC

### 测试目标

验证非 git 仓库 workdir 触发 `RunStartError(reason="not_a_git_repo")` 并回滚（不创建 run row、不持有 lock）；HTTP 层映射为 400。

### 前置条件

- `.venv` 激活
- `tmp_path` 存在但**未** `git init`（无 `.git/` 子目录）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 确保 `tmp_path/".git"` 不存在 | `False` |
| 2 | `req = RunStartRequest(workdir=str(tmp_path))` | pydantic 通过 |
| 3 | `with pytest.raises(RunStartError) as exc: await orchestrator.start_run(req)` | 抛 RunStartError |
| 4 | 断言 `exc.value.reason == "not_a_git_repo"` | True |
| 5 | 断言 `not (tmp_path/".harness"/"run.lock").exists()` | True（lock 未创建）|
| 6 | 断言 `runs` 表无新行（或 state=`failed`）| True |

### 验证点

- 非 git repo 拒绝启动是 SEC + FUNC 复合断言（ATS L49 SEC 注："workdir 路径必须拒 `..` 穿越与符号链逃逸"——此处验证最基础"必须是 git repo"路径）
- `RunStartError.reason` 字面与 §IC Raises 列对齐
- 失败路径无副作用（lock + run row 均回滚）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t02_start_run_rejects_non_git_repo`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-003

### 关联需求

FR-002 AC-2 · §Interface Contract `PhaseRouteInvoker.invoke` postcondition · Test Inventory T03 · ATS L50 FR-002

### 测试目标

验证 `PhaseRouteInvoker.invoke(workdir)` 在 mock subprocess stdout=`{"ok":true,"next_skill":"long-task-design","feature_id":null,"counts":{"work":3}}` 时返回正确填充的 `PhaseRouteResult`，并下次 `TicketCommand.skill_hint` 透传。

### 前置条件

- `.venv` 激活；`harness.orchestrator.phase_route.PhaseRouteInvoker` / `PhaseRouteResult` 可导入
- mock `asyncio.create_subprocess_exec` 返回 stdout 与 exit 可控

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock `asyncio.create_subprocess_exec` returns stdout=`b'{"ok":true,"next_skill":"long-task-design","feature_id":null,"counts":{"work":3}}\n'` exit=0 | mock 注入成功 |
| 2 | `invoker = PhaseRouteInvoker(plugin_dir=tmp_plugin)` | 构造成功 |
| 3 | `result = await invoker.invoke(tmp_path)` | 不抛异常 |
| 4 | 断言 `result.ok is True and result.next_skill == "long-task-design"` | True |
| 5 | 断言 `result.feature_id is None and result.counts == {"work":3}` | True |
| 6 | 断言 mock 被调用时 argv 含 `"phase_route.py"` 与 `"--json"` | True |

### 验证点

- next_skill 字面透传（FR-002 AC-2）
- `counts` 子字段被 pydantic 正确反序列化（dict[str,int]）
- argv 至少包含 `--json` 参数（IFR-003 协议）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_phase_route_invoker.py::test_t03_invoke_happy_path_returns_phase_route_result`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-004

### 关联需求

FR-002 AC-3 · §Interface Contract `PhaseRouteInvoker.invoke` Raises `PhaseRouteError` · Test Inventory T04 · ATS L181 IFR-003

### 测试目标

验证 mock subprocess exit=2 + stderr=`"feature-list.json missing"` 时 `invoke` 抛 `PhaseRouteError`；orchestrator 主循环捕获后 `runs.state` 转 `paused` 并 broadcast `Escalated{reason="phase_route_error"}`。

### 前置条件

- `.venv` 激活；`PhaseRouteInvoker` / `PhaseRouteError` / `RunControlBus` 可导入
- mock subprocess 可控 exit + stderr

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock subprocess exit=2 stderr=`b"feature-list.json missing\n"` stdout=`b""` | 注入 |
| 2 | `with pytest.raises(PhaseRouteError) as exc: await invoker.invoke(tmp_path)` | 抛 PhaseRouteError |
| 3 | 断言 `exc.value.errors` 含 `"feature-list.json missing"` 子串（stderr_tail） | True |
| 4 | 在 orchestrator 集成路径下断言 `runs.state == "paused"` | True |
| 5 | 断言 RunControlBus broadcast 收到 `Escalated(reason="phase_route_error")` | True |

### 验证点

- exit≠0 即时暂停（FR-002 AC-3 显式语义）
- stderr_tail 不被吞（被附到 errors 列表）
- WebSocket 推送 `Escalated{reason}` envelope（IAPI-001）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_phase_route_invoker.py::test_t04_invoke_exit_nonzero_raises_phase_route_error`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-005

### 关联需求

FR-002 · IFR-003 · §Interface Contract `PhaseRouteInvoker.invoke` · Test Inventory T05 · ATS L181 IFR-003 INTG

### 测试目标

真实 subprocess `python scripts/phase_route.py --json` 在受控 fixture（含 stub `feature-list.json`）下执行，验证 stdout 是合法 JSON 且 `PhaseRouteResult` 字段对齐 `ok/next_skill/feature_id/...`，timeout 30s 内完成。

### 前置条件

- `.venv` 激活
- 真实 `scripts/phase_route.py` 可执行；`tmp_path` 含 `feature-list.json` stub（最小合法版本）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 创建 tmp `feature-list.json`（最小 schema：含 `project`、`features:[]` 与 `current:null`）| 落盘 |
| 2 | `invoker = PhaseRouteInvoker(plugin_dir=<plugin_root>)` | 构造成功 |
| 3 | `result = await invoker.invoke(tmp_path, timeout_s=30.0)` | 不抛 |
| 4 | 断言 `result.ok is True`（或 ok=False 但 errors 字段非空）| True |
| 5 | 断言 `isinstance(result, PhaseRouteResult)` 且字段集 ⊇ `{ok, next_skill, feature_id, starting_new, needs_migration, counts, errors}` | True |
| 6 | 断言整体耗时 < 30s | True |

### 验证点

- 真实 subprocess argv 由 `PhaseRouteInvoker` 内部组装（cwd=workdir、`python scripts/phase_route.py --json`）；不依赖 mock
- stdout 解析为合法 JSON（如非 JSON 应触发 `PhaseRouteParseError`，由 ST-FUNC-020-007 覆盖）
- 没有 PYTHONPATH 错误、cwd 错误、二进制路径错误

### 后置检查

- `tmp_path` 自动清理；subprocess 自然退出

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_subprocess.py::test_t05_real_phase_route_subprocess_returns_valid_phase_route_result`
- **Test Type**: Real
- **类别归属说明**：design 标 T05 为 INTG/subprocess；ST 规范无 INTG 类，归 functional（黑盒契约 = "phase_route subprocess 在真实环境产出合法 PhaseRouteResult"）。

---

### 用例编号

ST-BNDRY-020-001

### 关联需求

NFR-015 · §Interface Contract `PhaseRouteResult` `extra="ignore"` · Test Inventory T06 · ATS L171 NFR-015

### 测试目标

验证 `PhaseRouteResult` 容忍 phase_route.py 输出字段增减（缺 `next_skill` / 缺 `feature_id` / 新增 `extras` 字段）—— 缺失字段补默认值，新增字段被忽略，不抛 ValidationError。

### 前置条件

- `.venv` 激活；`PhaseRouteResult` 可导入
- mock subprocess 可注入两种 stdout fixture

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock stdout=`b'{"ok":true}\n'` | 注入 fixture A |
| 2 | `result_a = await invoker.invoke(tmp_path)` | 不抛 ValidationError |
| 3 | 断言 `result_a.next_skill is None and result_a.feature_id is None` | True |
| 4 | 断言 `result_a.errors == [] and result_a.starting_new is False` | True |
| 5 | mock stdout=`b'{"ok":true,"next_skill":"x","extras":{"new_field":1}}\n'` | 注入 fixture B |
| 6 | `result_b = await invoker.invoke(tmp_path)` | 不抛 ValidationError |
| 7 | 断言 `result_b.next_skill == "x"` | True |
| 8 | 断言 `not hasattr(result_b, "extras") or result_b.model_dump().get("extras") is None` | True（新增字段被忽略） |

### 验证点

- pydantic v2 `ConfigDict(extra="ignore")` + 全字段默认值生效
- 适配器对 phase_route.py 字段演化的容忍度（NFR-015 单一断言）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_phase_route_invoker.py::test_t06_relaxed_parsing_default_fields`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-002

### 关联需求

FR-002 AC-3 · IFR-003 故障模式 · §Interface Contract `PhaseRouteInvoker.invoke` Raises `PhaseRouteParseError` · Test Inventory T07 · ATS L181 IFR-003

### 测试目标

验证 mock subprocess stdout=`"not a json"` exit=0 时抛 `PhaseRouteParseError`；audit 写入 `phase_route_parse_error` 事件；run 暂停。

### 前置条件

- `.venv` 激活；`PhaseRouteParseError` / `AuditWriter` 可导入
- mock subprocess + audit spy

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock stdout=`b"not a json\n"` exit=0 | 注入 |
| 2 | `with pytest.raises(PhaseRouteParseError): await invoker.invoke(tmp_path)` | 抛 PhaseRouteParseError |
| 3 | 断言 audit 写入条目 `event_type == "phase_route_parse_error"` | True |
| 4 | 断言整体 orchestrator 路径 `runs.state == "paused"`（如做集成测试）| True |

### 验证点

- 非 JSON 不被默默忽略（IFR-003 故障模式硬关卡）
- audit 事件名字面 `phase_route_parse_error`（Implementation Summary 决策 d）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_phase_route_invoker.py::test_t07_stdout_not_json_raises_parse_error_and_audits`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-006

### 关联需求

FR-003 · §Interface Contract `PhaseRouteInvoker.invoke` · Clarification Addendum #8（bugfix>increment 优先级） · Test Inventory T08 · ATS L51 FR-003

### 测试目标

验证 workdir 含 `bugfix-request.json` 时 phase_route.py 返回 `next_skill="long-task-hotfix"`；下次 `TicketCommand.skill_hint == "long-task-hotfix"` 透传，不在 orchestrator 重新实现路由判定（FR-003 + CON-008 单一事实源）。

### 前置条件

- `.venv` 激活
- mock workdir 含 `bugfix-request.json` 占位文件
- mock phase_route 返 `next_skill="long-task-hotfix"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `(tmp_path/"bugfix-request.json").write_text("{}")` | 落盘 |
| 2 | mock phase_route stdout=`b'{"ok":true,"next_skill":"long-task-hotfix"}\n'` | 注入 |
| 3 | `result = await invoker.invoke(tmp_path)` | 不抛 |
| 4 | 断言 `result.next_skill == "long-task-hotfix"` | True |
| 5 | 经 orchestrator 集成路径 spawn ticket，验证 `TicketCommand.skill_hint == "long-task-hotfix"` 透传 | True |

### 验证点

- bugfix 信号被 phase_route 自身判定（FR-003 AC-1）；orchestrator 不重写路由（CON-008）
- bugfix > increment 优先级由 phase_route.py 自身保证（Clarification Addendum #8 处置）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_phase_route_invoker.py::test_t08_hotfix_signal_passed_through_via_skill_hint`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-007

### 关联需求

FR-004 AC-1 · §State Diagram Running→PausePending→Paused · Test Inventory T09 · ATS L52 FR-004

### 测试目标

验证 `pause_run(run_id)` 在当前 ticket 进行中时立即返回 `RunStatus(state ∈ {pause_pending, paused})`；当前 ticket 完成后 `runs.state` 转 `paused`；`_run_loop` 不再调 `phase_route.invoke`。

### 前置条件

- `.venv` 激活
- run 已通过 `start_run` 进入 running，且当前 ticket 仍在 spawn / 流式阶段
- mock `TicketSupervisor.run_ticket` 可控完成时机

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await orchestrator.start_run(...)` 首张 ticket 进入 running | state=running |
| 2 | `status = await orchestrator.pause_run(run_id)` | 立即返回 |
| 3 | 断言 `status.state in {"pause_pending", "paused"}` 且 `pause_pending=True` | True |
| 4 | mock 当前 ticket 完成（emit completed verdict）| 触发 |
| 5 | 等候 orchestrator loop 结束当前 cycle，断言 `runs.state == "paused"` | True |
| 6 | 断言 `PhaseRouteInvoker.invoke` 在 step 4 后**未**被调用 | True |

### 验证点

- pause 不立即终止 ticket（违反 AC-1 表现为 ticket 被强杀）
- pause_pending 被尊重，`_run_loop` 跳出循环 `MarkPaused`
- broadcast `RunPhaseChanged(state="paused")`

### 后置检查

- `tmp_path` 自动清理；run.lock 释放

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t09_pause_run_transitions_via_pause_pending`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-008

### 关联需求

FR-004 AC-3 · §Interface Contract `cancel_run` postcondition · Test Inventory T10 · ATS L52 FR-004

### 测试目标

验证 `cancel_run(run_id)` 后 run 转 `cancelled`；后续 `start_run(same_workdir)` 创建**新** run（不 resume 旧 run）；后端不暴露 resume 端点。

### 前置条件

- `.venv` 激活；FastAPI TestClient 已装载 `harness.api:app`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await orchestrator.start_run(req)` | run id=R1 创建 |
| 2 | `await orchestrator.cancel_run("R1")` | 返回 RunStatus(state="cancelled") |
| 3 | TestClient `POST /api/runs/R1/resume` | 404 / 405（无 resume 端点）|
| 4 | `await orchestrator.start_run(req)` 同 workdir | 创建**新** run id=R2（≠R1）|
| 5 | 断言 `R2 != R1` 且 `runs[R1].state == "cancelled"` | True |

### 验证点

- cancel 后状态不可被恢复（无 resume 路由）
- 新 start_run 视为新 run（不复用旧 run_id）
- run.lock 在 R1 cancel 后释放，否则 R2 acquire 会 409

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t10_cancel_run_no_resume_endpoint`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-009

### 关联需求

FR-024 AC-1 · §Interface Contract `RetryPolicy.next_delay`（context_overflow） · §State Diagram ContextOverflow→Retrying · Test Inventory T11 · ATS L97 FR-024

### 测试目标

验证 `RetryPolicy.next_delay("context_overflow", retry_count=0)` 返回 `0.0`（即时新会话）；`RetryCounter.inc(skill_hint, "context_overflow")` 返回 `1`；`reenqueue_ticket` 被调用且新 ticket `parent_ticket==旧 ticket_id`。

### 前置条件

- `.venv` 激活；`harness.recovery.retry.RetryPolicy` / `RetryCounter` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy(); counter = RetryCounter()` | 构造成功 |
| 2 | `delay = policy.next_delay("context_overflow", retry_count=0)` | 不抛 |
| 3 | 断言 `delay == 0.0` | True |
| 4 | `new_count = counter.inc("long-task-tdd-red", "context_overflow")` | 不抛 |
| 5 | 断言 `new_count == 1` | True |

### 验证点

- context_overflow 即时新会话（首次 retry_count=0 → 0.0s 延迟，与 rate_limit 30s 起对比的关键差异）
- RetryCounter 起始为 0，inc 后返 1（Clarification #2 一致）

### 后置检查

- 无（纯函数）

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_t11_context_overflow_retry_zero_delay_and_increment`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-003

### 关联需求

NFR-003 · FR-024 AC-2 · §State Diagram ContextOverflow→Escalated · Test Inventory T12 · ATS L159 NFR-003

### 测试目标

验证连续 4 次 context_overflow 注入：第 1-3 次 spawn 新 ticket（retry_count 1→3）；第 4 次 `RetryPolicy.next_delay("context_overflow", retry_count=3) == None`，触发 `EscalationEmitter.emit`；`runs.state="paused"`；UI 收 `Escalated{cls="context_overflow", retry_count=3}`。

### 前置条件

- `.venv` 激活；`RetryPolicy` / `RetryCounter` / `EscalationEmitter` / `RunControlBus` 可导入
- mock claude stderr `"context window exceeded"` 4 次同 skill

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy(); counter = RetryCounter()` | 构造 |
| 2 | 循环 4 次：`rc = counter.inc(skill, "context_overflow"); delays.append(policy.next_delay("context_overflow", rc-1))` | 收集 4 个 delay |
| 3 | 断言 `delays[0:3] == [0.0, 0.0, 0.0]`（前 3 次即时 retry）| True |
| 4 | 断言 `delays[3] is None`（第 4 次 escalate）| True |
| 5 | 集成路径下断言 `EscalationEmitter.emit` 被调用且 `cls="context_overflow"` `retry_count=3` | True |

### 验证点

- retry_count 从 0 起递增（Clarification Addendum #2）
- 第 4 次必 escalate（NFR-003 硬关卡）
- audit + RunControlBus broadcast 双通道（Clarification #7）

### 后置检查

- 纯内存计数器无副作用

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_t12_context_overflow_4th_attempt_escalates`
- **Test Type**: Real

---

### 用例编号

ST-PERF-020-001

### 关联需求

NFR-004 · FR-025 AC-1 · §Boundary `RetryPolicy(rate_limit)` · Test Inventory T13 · ATS L98 FR-025 PERF · ATS L160 NFR-004

### 测试目标

验证 `RetryPolicy.next_delay("rate_limit", retry_count=0..3)` 严格返回序列 `[30.0, 120.0, 300.0, None]`，覆盖 NFR-004 + FR-025 退避序列锚定（30/120/300s + 第 4 次 escalate）。

### 前置条件

- `.venv` 激活；`RetryPolicy` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy()` | 构造 |
| 2 | `delays = [policy.next_delay("rate_limit", rc) for rc in range(4)]` | 4 元素列表 |
| 3 | 断言 `delays == [30.0, 120.0, 300.0, None]`（精确）| True |

### 验证点

- 精确序列锚定（不允许 30/60/120 等错位）
- 第 4 次必 None（escalate）—— 覆盖 NFR-004 上限

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_t13_rate_limit_backoff_sequence_30_120_300_none`
- **Test Type**: Real
- **类别归属说明**：design 标 T13 为 PERF/timing；ST 用例验证退避序列纯函数正确性归 PERF（与 ATS L98 FR-025 PERF + L160 NFR-004 一致）。

---

### 用例编号

ST-FUNC-020-010

### 关联需求

NFR-004 · FR-025 AC-1 · Test Inventory T14 · ATS L160 NFR-004 INTG

### 测试目标

真实 `asyncio.sleep` 注入 + monotonic clock 测量首次 rate_limit 重试间隔；实测延迟 30s ±10% 容忍（27-33s）。覆盖 NFR-004 实测窗口。

### 前置条件

- `.venv` 激活
- 该用例可能耗时 ≥ 30s；CI 标 `@pytest.mark.slow` 但仍执行

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 mock retry 注入：第 1 次 rate_limit anomaly | 触发 |
| 2 | `t0 = time.monotonic(); await orchestrator.handle_anomaly(rate_limit, retry_count=0)` | 启动 sleep |
| 3 | 等候 retry 实际触发 | 真实 asyncio.sleep |
| 4 | `elapsed = time.monotonic() - t0`，断言 `27.0 <= elapsed <= 33.0`（±10% 容忍）| True |

### 验证点

- 真实 `asyncio.sleep` 调用时长（NFR-004 ATS L278 测量方法）
- 时钟精度满足 ±10%（不允许偏差 > 3s）

### 后置检查

- 测试自动清理 mock

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_subprocess.py::test_t14_real_asyncio_sleep_first_retry_interval_30s_within_tolerance`
- **Test Type**: Real
- **类别归属说明**：design 标 T14 为 INTG/timing；与 F19 ST-PERF-019-001 / ST-FUNC-019-020 等惯例一致，归 functional。

---

### 用例编号

ST-FUNC-020-011

### 关联需求

FR-026 AC-1/2/3 · §Boundary `RetryPolicy(network)` · Test Inventory T15 · ATS L99 FR-026

### 测试目标

验证 `RetryPolicy.next_delay("network", retry_count=0..2)` 返回 `[0.0, 60.0, None]`，第 3 次 escalate（network 序列与 rate_limit 不同：首次即时、第 2 次 60s、第 3 次 escalate，覆盖上限 ≤ 2）。

### 前置条件

- `.venv` 激活；`RetryPolicy` 可导入；mock stderr `"ECONNREFUSED"` × 3

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy()` | 构造 |
| 2 | `delays = [policy.next_delay("network", rc) for rc in range(3)]` | 3 元素列表 |
| 3 | 断言 `delays == [0.0, 60.0, None]` | True |

### 验证点

- network 序列与 rate_limit 完全独立（不退化为 30/120）
- 第 3 次必 None（覆盖 FR-026 AC-3 上报）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_t15_network_backoff_sequence_0_60_none`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-004

### 关联需求

§Boundary `RetryPolicy.retry_count`（empty/null）· §Implementation Summary 决策 b（纯函数枚举）

### 测试目标

验证 `RetryPolicy.next_delay(cls, retry_count=-1)` 抛 `ValueError`（覆盖 §Boundary "0 / 负数 → ValueError"）。

### 前置条件

- `.venv` 激活；`RetryPolicy` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy()` | 构造 |
| 2 | `with pytest.raises(ValueError): policy.next_delay("rate_limit", retry_count=-1)` | 抛 ValueError |

### 验证点

- 边界值校验（不允许负数 retry_count，与 §Boundary `RetryPolicy.retry_count` 表 "Empty/Null → ValueError" 对齐）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_retry_policy_negative_retry_count_raises`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-012

### 关联需求

FR-027 AC-1 · §Interface Contract `Watchdog.arm` · §State Diagram Timeout→Retrying · Test Inventory T16 · ATS L100 FR-027

### 测试目标

验证 `Watchdog.arm(ticket_id, pid, timeout_s=1.0)`（测试压缩到 1s）在 1s 后调用 `os.kill(pid, SIGTERM)`。覆盖 FR-027 AC-1 SIGTERM 触发。

### 前置条件

- `.venv` 激活；`harness.recovery.watchdog.Watchdog` 可导入；`os.kill` mock 可拦截调用

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `wd = Watchdog()` | 构造 |
| 2 | mock `os.kill` 拦截 | 注入 spy |
| 3 | mock pid alive 2s（process polling 仍在） | 注入 |
| 4 | `await wd.arm(ticket_id="T1", pid=12345, timeout_s=1.0)` | 不抛 |
| 5 | 等待 ≥ 1.2s | 触发 |
| 6 | 断言 `os.kill` 至少被调用一次且参数 == `(12345, signal.SIGTERM)` | True |

### 验证点

- timeout_s 参数生效（v1 实际默认 1800.0 写死，测试压缩到 1.0；Clarification #5）
- SIGTERM 信号调用语义正确

### 后置检查

- 测试自动 disarm

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_t16_watchdog_arm_fires_sigterm_after_timeout`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-013

### 关联需求

FR-027 AC-2 · §Interface Contract `Watchdog` SIGKILL escalation · Test Inventory T17 · ATS L100 FR-027

### 测试目标

验证 SIGTERM 后 5s pid 仍 alive 时 `os.kill(pid, SIGKILL)` 被调用；ticket 转 `aborted` 或 `retrying`（取决于 anomaly cls=timeout）。

### 前置条件

- `.venv` 激活
- mock pid 仍 alive 6s+

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `wd = Watchdog()` mock os.kill spy | 构造 |
| 2 | mock pid 在 SIGTERM 后仍存活 5s+ | 注入 |
| 3 | `await wd.arm("T1", 12345, timeout_s=1.0)` | 不抛 |
| 4 | 等候 ≥ 6.5s | 触发 SIGTERM 然后 SIGKILL |
| 5 | 断言 `os.kill` 调用序列为 `[(12345, SIGTERM), (12345, SIGKILL)]`（顺序约束） | True |
| 6 | 断言 SIGKILL 调用时点 ≈ SIGTERM + 5s（±0.5s 容忍）| True |

### 验证点

- SIGTERM → SIGKILL 升级在 5s 后（FR-027 AC-2 硬关卡）
- 信号顺序不可乱（SIGKILL 不能先于 SIGTERM）

### 后置检查

- 测试自动 disarm

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_t17_watchdog_escalates_to_sigkill_after_sigterm_5s`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-014

### 关联需求

FR-028 AC-1 · §State Diagram SkillError→Aborted · Test Inventory T18 · ATS L101 FR-028

### 测试目标

验证 `Verdict(anomaly="skill_error")` + `result_text` 首行 `[CONTRACT-DEVIATION] ...` 时 `AnomalyClassifier.classify` 返回 `cls="skill_error"`；ticket 转 `aborted`；`reenqueue_ticket` 不被调用；`runs.state="paused"`。

### 前置条件

- `.venv` 激活；`AnomalyClassifier` / `ClassifyRequest` / `Verdict` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `Verdict(anomaly="skill_error", reason="..."); req = ClassifyRequest(stdout_tail="[CONTRACT-DEVIATION] feature design missing srs_trace\n...", ...)` | 通过 |
| 2 | `classifier = AnomalyClassifier()` | 构造 |
| 3 | `info = classifier.classify(req, verdict)` | 不抛 |
| 4 | 断言 `info.cls == "skill_error"` | True |
| 5 | 在集成路径中验证 ticket 转 `aborted` 且 `TicketSupervisor.reenqueue_ticket` **未**被调用 | True |
| 6 | 断言 orchestrator `runs.state == "paused"` | True |

### 验证点

- skill_error 直通 aborted 不重试（FR-028 AC-1）
- 不进入 retry 路径（reenqueue_ticket 零调用）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_t18_skill_error_passthrough_to_aborted_no_retry`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-015

### 关联需求

FR-028 AC-2 · §State Diagram SkillError→Aborted (orchestrator pause) · Test Inventory T19 · ATS L101 FR-028

### 测试目标

验证 skill_error 后 orchestrator 主循环立即 `state="paused"`；UI 收到 `Escalated{cls="skill_error"}`。

### 前置条件

- `.venv` 激活；`RunControlBus` / `EscalationEmitter` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 注入 mock ticket outcome `final_state="aborted"` `anomaly.cls="skill_error"` | 触发 |
| 2 | orchestrator `_run_loop` 在 1 个 cycle 内处理 | 进入 PauseSkillError |
| 3 | 断言 `runs.state == "paused"` | True |
| 4 | 断言 RunControlBus broadcast 收到 envelope `Escalated{cls="skill_error"}` | True |

### 验证点

- skill_error 不被默默继续（必须暂停等用户决策）
- broadcast envelope 字段对齐 §6.2.3

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_anomaly_recovery.py::test_t19_skill_error_pauses_run_in_orchestrator`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-016

### 关联需求

FR-029 AC-1 · §Interface Contract `skip_anomaly` postcondition · Test Inventory T20 · ATS L102 FR-029

### 测试目标

验证 ticket 处 `retrying` 时调 `skip_anomaly(ticket_id)` 返回 `RecoveryDecision(kind="skipped")`；`RetryCounter[skill]` 重置为 0；下次 ticket 由 `phase_route.invoke` 决定。

### 前置条件

- `.venv` 激活；`UserOverride` / `RecoveryDecision` 可导入；ticket 状态可控

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 ticket state=`retrying`；counter inc 后值=2 | 状态准备 |
| 2 | `decision = await orchestrator.skip_anomaly(ticket_id)` | 不抛 |
| 3 | 断言 `decision.kind == "skipped"` | True |
| 4 | 断言 `counter.get(skill_hint) == 0`（reset） | True |
| 5 | 断言 `PhaseRouteInvoker.invoke` 在 skip 后立即被调用 | True |

### 验证点

- skip 必须重置 RetryCounter（避免污染同 skill 后续 ticket）
- skip 立即调 phase_route 拿下一张（不再走 retry 路径）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_user_override.py::test_t20_skip_anomaly_resets_counter_and_invokes_phase_route`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-017

### 关联需求

FR-029 AC-2 · §Interface Contract `force_abort_anomaly` · Test Inventory T21 · ATS L102 FR-029

### 测试目标

验证 ticket 处 `running` 时调 `force_abort_anomaly(ticket_id)` 立即转 `aborted`；audit 写入 `force_abort` event。

### 前置条件

- `.venv` 激活；ticket repo + AuditWriter 可观测

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 ticket state=`running` | 状态准备 |
| 2 | `decision = await orchestrator.force_abort_anomaly(ticket_id)` | 不抛 |
| 3 | 断言 `decision.kind == "abort"` | True |
| 4 | 断言 `tickets[ticket_id].state == "aborted"` | True |
| 5 | 断言 audit 含 `event_type == "force_abort"` 条目 | True |

### 验证点

- 强制中止 transition 合法（`running → aborted` 由 TicketStateMachine 允许）
- audit 事件名字面 `force_abort`

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_user_override.py::test_t21_force_abort_transitions_running_to_aborted`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-018

### 关联需求

FR-029 · §Interface Contract `skip_anomaly` Raises `InvalidTicketState` · Test Inventory T22

### 测试目标

验证 ticket 处 `completed` 时调 `skip_anomaly(ticket_id)` 抛 `InvalidTicketState`，HTTP 映射 409。

### 前置条件

- `.venv` 激活；FastAPI TestClient

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 ticket state=`completed` | 状态准备 |
| 2 | TestClient `POST /api/anomaly/{ticket_id}/skip` | 响应 |
| 3 | 断言 HTTP status_code == 409 | True |
| 4 | 断言响应 body 含 `error_code` 或 detail 字段提示 InvalidTicketState | True |

### 验证点

- 已结束 ticket 不能 skip（state guard）
- HTTP 错误码映射对齐 §6.2.5（409 InvalidState）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_user_override.py::test_t22_skip_anomaly_invalid_state_409`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-019

### 关联需求

FR-039 · §Interface Contract `validate_file` postcondition · Test Inventory T23 · ATS L120 FR-039

### 测试目标

验证 mock subprocess `validate_features.py` exit=0 stdout=`{"ok":true,"issues":[]}` 时 `ValidationReport(ok=True, issues=[], script_exit_code=0, duration_ms>0)`；HTTP 200。

### 前置条件

- `.venv` 激活；`ValidatorRunner` / `ValidationReport` 可导入；mock subprocess

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock subprocess exit=0 stdout=`b'{"ok":true,"issues":[]}\n'` | 注入 |
| 2 | `report = await runner.run(ValidateRequest(path=str(tmp_path/"feature-list.json"), script="validate_features"))` | 不抛 |
| 3 | 断言 `report.ok is True and report.issues == []` | True |
| 4 | 断言 `report.script_exit_code == 0 and report.duration_ms > 0` | True |

### 验证点

- 正常路径 ok=True 透传
- duration_ms 真实计时（非 0）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_validator_runner.py::test_t23_validator_happy_path_returns_ok_report`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-020

### 关联需求

FR-040 · IAPI-016 · Test Inventory T24 · ATS L121 FR-040 INTG

### 测试目标

真实 subprocess `python scripts/validate_features.py --json <path>` 在合法 fixture 下：exit=0 + 合法 JSON + 真实 issues 数。覆盖 IAPI-016 真实 subprocess 协议。

### 前置条件

- `.venv` 激活
- 真实 `scripts/validate_features.py` 可执行
- tmp `feature-list.json` 含合法 schema

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 创建合法 `feature-list.json` fixture | 落盘 |
| 2 | `report = await runner.run(ValidateRequest(path=<fixture>, script="validate_features"))` | 不抛 |
| 3 | 断言 `report.script_exit_code == 0` | True |
| 4 | 断言 `isinstance(report.issues, list)` | True |
| 5 | 断言 `report.duration_ms > 0` | True |

### 验证点

- argv 与 cwd 正确（不依赖 mock）
- stdout JSON 解析正确（`scripts/validate_*.py --json` 协议，Clarification #6）

### 后置检查

- `tmp_path` 自动清理；subprocess 自然退出

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_subprocess.py::test_t24_real_validate_features_subprocess`
- **Test Type**: Real
- **类别归属说明**：design 标 T24 为 INTG/subprocess；归 functional（黑盒契约 = "真实 validator 子进程产出合法 ValidationReport"）。

---

### 用例编号

ST-FUNC-020-021

### 关联需求

FR-040 AC-2 · §Interface Contract `validate_file` 错误不被吞 · Test Inventory T25 · ATS L121 FR-040

### 测试目标

验证 mock subprocess exit=2 stderr=`"FileNotFoundError: feature-list.json"` 时 `ValidationReport(ok=False, issues=[ValidationIssue(severity="error", message=stderr_tail)], script_exit_code=2)`；HTTP 200（错误数据不被吞 + 不视为 server error）。

### 前置条件

- `.venv` 激活；`ValidatorRunner` / `ValidationIssue` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock subprocess exit=2 stdout=`b""` stderr=`b"FileNotFoundError: feature-list.json\n"` | 注入 |
| 2 | `report = await runner.run(ValidateRequest(path="missing.json", script="validate_features"))` | 不抛（HTTP 200 语义）|
| 3 | 断言 `report.ok is False` | True |
| 4 | 断言 `report.script_exit_code == 2` | True |
| 5 | 断言 `len(report.issues) >= 1 and report.issues[0].severity == "error"` | True |
| 6 | 断言 `"FileNotFoundError" in report.issues[0].message` | True |

### 验证点

- stderr 不被吞（FR-040 AC-2 硬关卡）
- HTTP 200 + ok=False 语义（错误数据，非服务故障）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_validator_runner.py::test_t25_validator_exit_nonzero_does_not_swallow_stderr`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-005

### 关联需求

FR-040 · §Boundary `ValidatorRunner.timeout_s` · Test Inventory T26

### 测试目标

验证 mock subprocess 长时间 sleep（>60s 默认 timeout）时抛 `ValidatorTimeout`；HTTP 500；stderr_tail 含 `"validator timeout"`。

### 前置条件

- `.venv` 激活；`ValidatorTimeout` 可导入；可压缩 timeout 至 ≤2s

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock subprocess sleep（不响应）；runner 内部 timeout 压缩到 1s | 注入 |
| 2 | `with pytest.raises(ValidatorTimeout) as exc: await runner.run(ValidateRequest(...), timeout_s=1.0)` | 抛 ValidatorTimeout |
| 3 | 断言 `"validator timeout" in str(exc.value).lower()` 或 `exc.value.detail` 含相同字串 | True |
| 4 | TestClient `POST /api/validate/feature-list.json` 经超时路径 → HTTP 500 | True |

### 验证点

- timeout 触发 + 进程被 kill（不允许永挂）
- HTTP 错误码 500（区别于 exit≠0 的 200）

### 后置检查

- subprocess 被 kill 干净

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_validator_runner.py::test_t26_validator_timeout_raises_validator_timeout`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-022

### 关联需求

FR-042 AC-1 · §Interface Contract `GitTracker.begin/end` · §Design Alignment seq msg#9 + msg#16 · Test Inventory T27 · ATS L128 FR-042 INTG

### 测试目标

真实 git repo fixture：`begin` → 写 2 个文件 → `git commit` × 2 → `end`；验证 `GitContext.head_after != head_before`、`commits` 长度=2、按 reverse-chrono 排序、audit 写 `ticket_git_recorded`。

### 前置条件

- `.venv` 激活；真实 git CLI 可用；`GitTracker` / `GitContext` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `subprocess.run(["git","init",str(tmp_path)])` 初始 repo + 配置 user.email / user.name | exit=0 |
| 2 | `git commit --allow-empty -m "initial"` | 创建 head_before commit |
| 3 | `tracker = GitTracker(); ctx = await tracker.begin("T1", tmp_path)` | head_before 捕获 |
| 4 | 写 `a.txt` + `git add . && git commit -m "c1"` | commit 1 |
| 5 | 写 `b.txt` + `git add . && git commit -m "c2"` | commit 2 |
| 6 | `ctx2 = await tracker.end("T1", tmp_path)` | head_after 捕获 |
| 7 | 断言 `ctx2.head_after != ctx.head_before` | True |
| 8 | 断言 `len(ctx2.commits) == 2` | True |
| 9 | 断言 `ctx2.commits[0].subject == "c2" and ctx2.commits[1].subject == "c1"`（reverse-chrono）| True |

### 验证点

- 真实 git rev-parse + git log --oneline 子进程（IFR-005）
- commits 数量 + 顺序（FR-042 AC-1）
- audit `ticket_git_recorded` 事件

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_git.py::test_t27_git_tracker_begin_end_records_2_commits`
- **Test Type**: Real
- **类别归属说明**：design 标 T27 为 FUNC/happy（含 INTG/git 性质——真实 git）；ST 归 functional。

---

### 用例编号

ST-FUNC-020-023

### 关联需求

FR-042 · IFR-005 故障模式 · §Interface Contract `GitTracker.begin` Raises `GitError` · Test Inventory T28

### 测试目标

验证非 git repo 调 `GitTracker.begin` 抛 `GitError(code="not_a_repo")`（exit=128）；orchestrator 记 audit warning 但 ticket 流不中断。

### 前置条件

- `.venv` 激活；`GitTracker` / `GitError` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `tmp_path` 是已存在目录但**未** `git init` | True（无 .git） |
| 2 | `tracker = GitTracker()` | 构造 |
| 3 | `with pytest.raises(GitError) as exc: await tracker.begin("T1", tmp_path)` | 抛 GitError |
| 4 | 断言 `exc.value.code == "not_a_repo"` 或字面消息含 `"not_a_repo"` 或 exit=128 | True |

### 验证点

- 非 git repo 错误码与 §IC Raises 列对齐
- 此处由 GitTracker 自身验证；orchestrator 集成路径处理由 ST-FUNC-020-001 主路径覆盖

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_git_tracker.py::test_t28_git_tracker_begin_in_non_git_repo_raises_git_error`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-024

### 关联需求

FR-042 · IAPI-013 · Test Inventory T29 · ATS L128 FR-042 INTG

### 测试目标

真实 `git rev-parse HEAD` + `git log --oneline` subprocess：输出 sha 是 40-hex；`commits[]` 是 list of `GitCommit{sha, subject}`。

### 前置条件

- `.venv` 激活；真实 git；fixture 含 ≥1 commit

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 真实 git repo fixture（至少 1 commit）| 准备 |
| 2 | `ctx = await tracker.begin("T1", tmp_path)` | 不抛 |
| 3 | 断言 `re.match(r"^[0-9a-f]{40}$", ctx.head_before)` | True |
| 4 | 写文件 + `git commit -m "test"` | 创建 commit |
| 5 | `ctx2 = await tracker.end("T1", tmp_path)` | 不抛 |
| 6 | 断言每个 `GitCommit` 实例含 `sha`（40-hex）+ `subject`（str）字段 | True |

### 验证点

- mock 漏掉的 git 二进制路径与 argv 转义在真实 subprocess 下被验证
- GitCommit schema 字段集（Clarification #3）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_git.py::test_t29_git_rev_parse_and_log_real_subprocess`
- **Test Type**: Real
- **类别归属说明**：design 标 T29 为 INTG/git；归 functional。

---

### 用例编号

ST-FUNC-020-025

### 关联需求

FR-047 AC-1 · 端到端 dry-run · Test Inventory T30 · ATS L143 FR-047

### 测试目标

注入 14 个 mock phase_route 输出（覆盖 14 个核心 skill）；mock ToolAdapter spawn 立即 completed；验证 14 个 ticket 全部 dispatch；`set(skill_hints) ⊇ 14-skill 必要子集`。

### 前置条件

- `.venv` 激活；`TicketSupervisor` / `RunOrchestrator` 可注入 mock dependencies

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 14 个 mock phase_route stdout：依次返回 `using-long-task` / `requirements` / `ucd` / `design` / `ats` / `init` / `work-design` / `work-tdd` / `work-st` / `quality` / `feature-st` / `st` / `finalize` / `hotfix`（前缀 `long-task-` 略） | 准备序列 |
| 2 | mock ToolAdapter spawn → 立即 verdict completed | 注入 |
| 3 | `await orchestrator.start_run(req); await orchestrator._wait_until_completed()` | 14 ticket 跑完 |
| 4 | 收集 dispatched skill_hints | list of 14 items |
| 5 | 断言 `set(skill_hints) ⊇ {"long-task-using-long-task","long-task-requirements",...}`（14 必要子集）| True |

### 验证点

- 端到端 dispatch 链路通畅（FR-047 AC-1）
- skill 集合完备（不缺失任何 14 个核心 skill）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_ticket_supervisor.py::test_t30_run_dispatches_14_skill_subset`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-006

### 关联需求

FR-047 AC-2 · 不硬编码白名单 · Test Inventory T31 · ATS L143 FR-047

### 测试目标

验证 mock phase_route 返回 `next_skill="long-task-future-skill-xyz"`（不在 14 集内）仍能 dispatch；`TicketCommand.skill_hint == "long-task-future-skill-xyz"` 透传；不抛 `UnknownSkill`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock phase_route stdout=`b'{"ok":true,"next_skill":"long-task-future-skill-xyz"}\n'` | 注入 |
| 2 | `result = await invoker.invoke(tmp_path)` | 不抛 |
| 3 | 经 orchestrator 集成路径，断言 spawn 时 `TicketCommand.skill_hint == "long-task-future-skill-xyz"` | True |
| 4 | 不抛任何 `UnknownSkill` / `ValueError` 异常 | True |

### 验证点

- 不硬编码 enum（FR-047 AC-2 硬关卡 + Implementation Summary 决策 e）
- skill_hint 字面透传，由 longtaskforagent 自身路由

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_phase_route_invoker.py::test_t31_unknown_skill_name_dispatchable`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-026

### 关联需求

FR-048 · §Interface Contract `SignalFileWatcher.events` · Test Inventory T32 · ATS L144 FR-048

### 测试目标

验证 `SignalFileWatcher.start(workdir)` 后外部写入 `bugfix-request.json` → 2s 内 `events()` yield `SignalEvent(kind="bugfix_request", path=...)`；`broadcast_signal` 被调用。

### 前置条件

- `.venv` 激活；`SignalFileWatcher` / `SignalEvent` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `watcher = SignalFileWatcher(); watcher.start(tmp_path)` | 不抛 |
| 2 | 异步：等候 events stream → `event = await asyncio.wait_for(watcher._queue.get(), timeout=2.0)` | 触发后 yield |
| 3 | 同步：`(tmp_path/"bugfix-request.json").write_text("{}")` | 落盘 |
| 4 | 断言 `event.kind == "bugfix_request"` | True |
| 5 | 断言 event 时点距文件写入 ≤ 2s | True |
| 6 | 断言 `RunControlBus.broadcast_signal` 被调用 | True |

### 验证点

- 文件变化到 yield 延迟 ≤ 2s（FR-048 AC）
- kind 字面对齐 § IC（"bugfix_request" / "increment_request" / "feature_list_changed" / etc.）

### 后置检查

- `await watcher.stop()` + `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_signal_watcher.py::test_t32_watcher_yields_bugfix_request_within_2s`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-027

### 关联需求

FR-048 · IAPI-012 · Test Inventory T33 · ATS L144 FR-048 INTG

### 测试目标

真实 watchdog observer + tmp dir：创建 5 个不同 signal file（`bugfix-request.json` / `increment-request.json` / `feature-list.json` / `docs/plans/srs.md` / `docs/rules/coding.md`）→ yield 5 个 SignalEvent；kind 分别匹配。

### 前置条件

- `.venv` 激活；`watchdog` 库可用

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `watcher = SignalFileWatcher(); watcher.start(tmp_path)` | 不抛 |
| 2 | 创建 5 个文件分布于 `bugfix-request.json` / `increment-request.json` / `feature-list.json` / `docs/plans/2026-04-21-harness-srs.md` / `docs/rules/coding.md` | 落盘 |
| 3 | 异步 收集 event 队列直至 5 个或 5s timeout | 收集成功 |
| 4 | 断言 5 个 event kind 分别为 `bugfix_request` / `increment_request` / `feature_list_changed` / `srs_changed` / `rules_changed` | True |

### 验证点

- 真实 watchdog observer 不丢事件
- kind enum 完备（IAPI-012 § IC `kind ∈ {...}` 列表）

### 后置检查

- `await watcher.stop()`

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_signal_fs.py::test_t33_real_watcher_yields_5_distinct_signal_kinds`
- **Test Type**: Real
- **类别归属说明**：design 标 T33 为 INTG/fs；归 functional。

---

### 用例编号

ST-BNDRY-020-007

### 关联需求

FR-048 防抖 · §Boundary `SignalFileWatcher.debounce_ms` · Test Inventory T34 · Clarification Addendum #4

### 测试目标

验证 100ms 内连续写 `bugfix-request.json` 3 次仅 yield 1 个 SignalEvent（去重，debounce_ms=200 默认）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `watcher = SignalFileWatcher(debounce_ms=200); watcher.start(tmp_path)` | 不抛 |
| 2 | 异步收集 event 队列，timeout 1s | 准备 |
| 3 | 100ms 内连续 `(tmp_path/"bugfix-request.json").write_text(str(i))` for i in 0..2 | 3 次写入 |
| 4 | 收集 events，断言 `len(events) == 1` | True |
| 5 | 断言 `events[0].kind == "bugfix_request"` | True |

### 验证点

- 防抖窗口 200ms 内重复写仅触发 1 次 broadcast（避免重复 dispatch）
- 防抖不影响 kind 标记

### 后置检查

- `await watcher.stop()`

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_signal_watcher.py::test_t34_watcher_debounces_rapid_writes`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-028

### 关联需求

NFR-016 · §Interface Contract `start_run` Raises `already_running` · Test Inventory T35 · ATS L172 NFR-016

### 测试目标

验证进程持有 `<workdir>/.harness/run.lock` 时再次 `start_run(same workdir)` 抛 `RunStartError(reason="already_running")`；HTTP 409 + `error_code="ALREADY_RUNNING"`。

### 前置条件

- `.venv` 激活；filelock 持有可控

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await orchestrator.start_run(req)` 首次启动 | run.lock 持有 |
| 2 | `with pytest.raises(RunStartError) as exc: await orchestrator.start_run(req)` 同 workdir | 抛 RunStartError |
| 3 | 断言 `exc.value.reason == "already_running"` | True |
| 4 | TestClient `POST /api/runs/start` 经 same workdir → 断言 HTTP 409 + `error_code="ALREADY_RUNNING"` | True |

### 验证点

- filelock 互斥（NFR-016 硬关卡）
- HTTP 409 + error_code 字面对齐 ATS INT-007

### 后置检查

- `await orchestrator.cancel_run(...)` 释放 lock

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t35_start_run_already_running_409`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-029

### 关联需求

NFR-016 ATS INT-007 · Test Inventory T36 · ATS L172 NFR-016 INTG

### 测试目标

两个 `RunOrchestrator` 实例并发 `start_run(same workdir)`：仅 1 个 acquire 成功；另 1 个抛 RunStartError + HTTP 409。覆盖 INT-007 真实并发场景。

### 前置条件

- `.venv` 激活；真实 filelock + asyncio gather

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `orch_a = RunOrchestrator(...); orch_b = RunOrchestrator(...)` 各自独立实例 | 构造 |
| 2 | 真实 git repo tmp_path | 准备 |
| 3 | `results = await asyncio.gather(orch_a.start_run(req), orch_b.start_run(req), return_exceptions=True)` | 并发 |
| 4 | 断言 results 中恰好 1 个 `RunStatus`（成功）+ 1 个 `RunStartError(reason="already_running")` | True |

### 验证点

- 真实 filelock 互斥（不依赖 mock；不允许两者都 acquire）
- timeout=0.5s（Clarification #9）足以让正常 acquire 完成

### 后置检查

- 成功的 orchestrator `cancel_run` 释放 lock

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_git.py::test_t36_concurrent_orchestrators_filelock_only_one_acquires`
- **Test Type**: Real
- **类别归属说明**：design 标 T36 为 INTG/concurrency；归 functional。

---

### 用例编号

ST-SEC-020-001

### 关联需求

§Interface Contract `read_file_tree` / `read_file_content` Raises `PathTraversalError` · Test Inventory T37 · ATS L49 FR-001 SEC

### 测试目标

验证 `read_file_content("../etc/passwd")` 或 `read_file_tree("../")` 抛 `PathTraversalError`；HTTP 映射 400。覆盖路径穿越防护。

### 前置条件

- `.venv` 激活；FastAPI TestClient

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | TestClient `GET /api/files/read?path=../etc/passwd` | 响应 |
| 2 | 断言 HTTP 400 | True |
| 3 | 断言 response detail 含 `"PathTraversal"` 或 `"path_traversal"` 字面 | True |
| 4 | TestClient `GET /api/files/tree?root=../` 同样 400 | True |

### 验证点

- `..` 穿越被拒（SEC 硬关卡）
- 符号链接 / 绝对路径同样应被拒（IsPath.resolve().is_relative_to(workdir) 校验）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_security.py::test_t37_path_traversal_blocked`
- **Test Type**: Real

---

### 用例编号

ST-SEC-020-002

### 关联需求

IFR-003 · IFR-005 · ATS Hint "subprocess argv 不拼接用户输入" · Test Inventory T38 · ATS L181 IFR-003 SEC

### 测试目标

验证 mock 用户输入 `"; rm -rf /"` 作 workdir → `start_run` 路径校验拒绝（非合法目录）；即使被拼到 phase_route argv 也是 `cwd` 参数（不进 shell；`asyncio.create_subprocess_exec` 不走 shell）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = RunStartRequest(workdir="/tmp/legit_dir; rm -rf /")` | pydantic 通过（仅字符串校验）|
| 2 | `with pytest.raises(RunStartError): await orchestrator.start_run(req)` | 抛 RunStartError（路径不存在 / 非目录 / 非 git repo）|
| 3 | 验证 spy `asyncio.create_subprocess_exec` 调用时 argv 不含 shell 元字符相关解释；`cwd` 参数为 Path 对象 | True |
| 4 | 即便 path 通过（如恶意创建了同名目录），shell 元字符不会被解释（`subprocess_exec` 不走 shell）| True |

### 验证点

- argv 注入防护（IFR-003 + IFR-005 SEC 硬关卡）
- 路径校验先于 subprocess（双重防护）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_security.py::test_t38_subprocess_argv_no_shell_injection`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-030

### 关联需求

§Interface Contract `submit_command` happy · §State Diagram Running→Cancelling · Test Inventory T39

### 测试目标

验证 `RunControlCommand(kind="cancel")` 经 `submit_command` 调 `cancel_run`；返回 `RunControlAck(accepted=True, current_state="cancelling")`；广播 `RunPhaseChanged(state="cancelled")`。

### 前置条件

- `.venv` 激活；`RunControlBus` / `RunControlCommand` / `RunControlAck` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await orchestrator.start_run(req)` | run id=R1 |
| 2 | `cmd = RunControlCommand(kind="cancel", run_id="R1")` | 通过 |
| 3 | `ack = await bus.submit_command(cmd)` | 不抛 |
| 4 | 断言 `ack.accepted is True and ack.current_state in {"cancelling","cancelled"}` | True |
| 5 | 断言 broadcast 收到 `RunPhaseChanged(state="cancelled")` envelope | True |

### 验证点

- command kind 路由正确（"cancel" → cancel_run）
- 返回 ack 字段对齐 §IC

### 后置检查

- run.lock 释放

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t39_run_control_bus_cancel_command`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-031

### 关联需求

§Interface Contract `submit_command` Raises `InvalidCommand` · Test Inventory T40

### 测试目标

验证 `RunControlCommand(kind="skip_ticket", target_ticket_id=None)` 抛 `InvalidCommand`；HTTP 400。

### 前置条件

- `.venv` 激活；FastAPI TestClient

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `cmd = RunControlCommand(kind="skip_ticket", target_ticket_id=None)` | pydantic 通过（None 作为 optional） |
| 2 | `with pytest.raises(InvalidCommand): await bus.submit_command(cmd)` | 抛 InvalidCommand |
| 3 | TestClient `POST /api/run-control` body `{"kind":"skip_ticket","target_ticket_id":null}` → HTTP 400 | True |

### 验证点

- 缺 target_ticket_id 不能 skip（`kind ∈ {skip_ticket, force_abort}` 强制 target_ticket_id 非空）
- HTTP 400 字面对齐

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t40_run_control_bus_invalid_command_400`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-032

### 关联需求

§Interface Contract `run_ticket` postcondition · IAPI-005/008 · §Design Alignment seq msg#8-12 · Test Inventory T41

### 测试目标

验证 `TicketSupervisor.run_ticket` 调用顺序 = `begin → spawn → arm → events → disarm → classify → end → save`；`TicketOutcome.final_state` 在 `{completed, failed, aborted, retrying}`。

### 前置条件

- `.venv` 激活；mock `ToolAdapter.spawn` 返 `TicketProcess(pid=1234)`；mock `StreamParser.events()` yield 3 文本事件 + 1 system exit

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock 全部依赖（GitTracker.begin/end、ToolAdapter.spawn、Watchdog.arm/disarm、StreamParser.events、ClassifierService.classify、TicketRepository.save）| 注入 spy |
| 2 | `outcome = await supervisor.run_ticket(cmd)` | 不抛 |
| 3 | 断言调用顺序：`begin` → `spawn` → `arm` → `events` consumed → `disarm` → `classify` → `end` → `save` | True |
| 4 | 断言 `outcome.final_state in {"completed","failed","aborted","retrying"}` | True |

### 验证点

- 调用顺序硬关卡（缺一不可，乱序导致 watchdog 漏 disarm 或 git head 错位）
- save 必有调用（不允许 ticket 不入库）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_ticket_supervisor.py::test_t41_run_ticket_call_order_begin_spawn_arm_events_disarm_classify_end_save`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-008

### 关联需求

§Interface Contract `DepthGuard.ensure_within` · §Boundary `DepthGuard.parent.depth` · Test Inventory T42

### 测试目标

验证 `parent.depth=2` 时 spawn child 抛 `TicketError(code="depth_exceeded")`；`ToolAdapter.spawn` 不被调用。

### 前置条件

- `.venv` 激活；`DepthGuard` / `TicketError` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 parent ticket `depth=2` | 准备 |
| 2 | `with pytest.raises(TicketError) as exc: DepthGuard().ensure_within(parent=parent_ticket)` | 抛 TicketError |
| 3 | 断言 `exc.value.code == "depth_exceeded"` 或 `"depth" in str(exc.value)` | True |
| 4 | 在 supervisor 集成路径中验证 `ToolAdapter.spawn` 调用次数为 0 | True |

### 验证点

- depth ≤ 2 硬关卡（FR-007 由 F02 落 DDL，本特性 spawn 前显式 check）
- spawn 不被调用（无副作用拒绝）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_ticket_supervisor.py::test_t42_depth_guard_rejects_depth_3`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-033

### 关联需求

§Interface Contract `list_commits` (IAPI-002 → F22) · Test Inventory T43

### 测试目标

验证 `list_commits(run_id="run-1")` 在 3 个 ticket 各产 1 commit 时返回 3 个 `GitCommit`，按 `committed_at DESC` 排序。

### 前置条件

- `.venv` 激活；FastAPI TestClient + mock git repo

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed 3 ticket each with 1 commit `committed_at` 间隔 1s | 准备 |
| 2 | TestClient `GET /api/git/commits?run_id=run-1` | HTTP 200 |
| 3 | 解析 response → list of 3 commits | True |
| 4 | 断言 commits[0].committed_at > commits[1].committed_at > commits[2].committed_at（reverse-chrono）| True |
| 5 | 断言 filter `?feature_id=X` 仅返回该 feature 关联 commit（如有）| True |

### 验证点

- filter 正确（run_id / feature_id 至少一项有效）
- 排序方向 DESC

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_ticket_supervisor.py::test_t43_list_commits_filters_and_orders_desc`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-034

### 关联需求

§Interface Contract `load_diff` Raises `DiffNotFound` · Test Inventory T44

### 测试目标

验证 `load_diff(sha="deadbeef" * 5)`（不存在）抛 `DiffNotFound`；HTTP 404。

### 前置条件

- `.venv` 激活；FastAPI TestClient

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | TestClient `GET /api/git/diff/deadbeefdeadbeefdeadbeefdeadbeefdeadbeef` | 响应 |
| 2 | 断言 HTTP 404 | True |
| 3 | 断言 response detail 含 `"DiffNotFound"` 或 `"not found"` | True |

### 验证点

- sha 不存在被拒（不允许默默返回空 diff）
- HTTP 404 字面对齐

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_ticket_supervisor.py::test_t44_load_diff_unknown_sha_raises_diff_not_found`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-035

### 关联需求

§Interface Contract `broadcast_signal` (IAPI-001) · Test Inventory T45

### 测试目标

验证注入 `SignalEvent(kind="bugfix_request")` 时订阅 `/ws/signal` 的 mock client 收到 envelope `WsEvent{kind="signal_file_changed", payload:{path, kind:"bugfix_request"}}`。

### 前置条件

- `.venv` 激活；FastAPI TestClient + WebSocket mock client

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | TestClient WebSocket 订阅 `/ws/signal` | 连接成功 |
| 2 | `bus.broadcast_signal(SignalEvent(kind="bugfix_request", path="/tmp/bugfix-request.json", mtime=...))` | 触发 |
| 3 | mock client 收到 envelope；解析 JSON | 解码成功 |
| 4 | 断言 envelope `kind == "signal_file_changed"`（或 `signal`，取决于 §6.2.3）| True |
| 5 | 断言 envelope `payload.kind == "bugfix_request"` and `"path" in payload` | True |

### 验证点

- WS envelope schema 对齐 §6.2.3（不允许字段漂移）
- payload 透传 SignalEvent 字段

### 后置检查

- WebSocket 关闭

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_ticket_supervisor.py::test_t45_broadcast_signal_ws_envelope_shape`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-036

### 关联需求

FR-001 AC-2（ST Go → COMPLETED） · §State Diagram Running→Completed · Test Inventory T46 · ATS L49 FR-001

### 测试目标

验证 mock phase_route 返回 `{"ok":true, "next_skill":null}`（all features passing）时 `runs.state="completed"`；orchestrator 退出 `_run_loop`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock phase_route stdout=`b'{"ok":true,"next_skill":null}\n'` | 注入 |
| 2 | `await orchestrator.start_run(req)` 等候 _run_loop 自然退出 | 触发 |
| 3 | 断言 `runs.state == "completed"` | True |
| 4 | 断言 `_run_loop` 已 exited | True |

### 验证点

- ST Go → COMPLETED 自停（FR-001 AC-2）
- 完成态不被错判为 paused

### 后置检查

- run.lock 释放

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t46_phase_route_no_next_skill_completes_run`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-037

### 关联需求

§Interface Contract `run_ticket` 末段 · IAPI-011/009 真实 sqlite · Test Inventory T47 · ATS INTG

### 测试目标

真实 aiosqlite + tmp_path：end-to-end ticket 执行后 `tickets` 表新行 payload 含全 FR-007 字段；`audit/<run_id>.jsonl` 含 ≥3 行（state_transition）。

### 前置条件

- `.venv` 激活；真实 aiosqlite；F02 schema 已 ensure

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 真实 sqlite tmp file；`Schema.ensure(conn)` | 表创建 |
| 2 | 经 `supervisor.run_ticket(cmd)` 完成一个 ticket | 持久化 |
| 3 | 查询 `SELECT payload FROM tickets WHERE id=?` | 返回 1 行 |
| 4 | 断言 payload JSON 含 FR-007 全字段（state, dispatch, execution, output, hil, anomaly, classification, git）| True |
| 5 | 检查 `audit/<run_id>.jsonl` 文件存在且行数 ≥ 3（含 state_transition events）| True |

### 验证点

- 真实 sqlite UPSERT（mock 漏的字段在此被发现）
- audit 三层 event（spawn / verdict / state_transition）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_db.py::test_t47_run_ticket_persists_to_real_sqlite`
- **Test Type**: Real
- **类别归属说明**：design 标 T47 为 INTG/db；归 functional。

---

### 用例编号

ST-FUNC-020-038

### 关联需求

§Implementation flow branch#3 (CheckPause) · FR-004 · Test Inventory T48

### 测试目标

验证 `pause_pending=True` 且当前 ticket 完成时 `_run_loop` 进 `MarkPaused`；不调 `PhaseRouteInvoker.invoke`；广播 `RunPhaseChanged(state="paused")`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await orchestrator.start_run(req)` 进入 running | True |
| 2 | 设 `pause_pending = True`（经 `pause_run` 调用）| True |
| 3 | mock 当前 ticket 立即 completed | 触发 |
| 4 | 断言 _run_loop 经 CheckPause 分支进入 MarkPaused | True |
| 5 | 断言 `PhaseRouteInvoker.invoke` 在 step 3 后未被调用 | True |
| 6 | 断言 `runs.state == "paused"` 且 broadcast `RunPhaseChanged(state="paused")` | True |

### 验证点

- pause_pending 被尊重（_run_loop flowchart branch#3 → MarkPaused）
- phase_route.invoke 调用次数为 0（不浪费一次 phase_route）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t48_run_loop_pause_pending_skips_phase_route`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-039

### 关联需求

§Implementation flow branch#5 (PrOk no) · FR-002 AC-3 · Test Inventory T49

### 测试目标

验证 mock phase_route exit=1 时 `_run_loop` 进 `PauseAndEscalate`；广播 `Escalated{reason="phase_route_error"}`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock phase_route exit=1 stderr=`b"feature-list missing\n"` | 注入 |
| 2 | `await orchestrator.start_run(req)` | 触发 _run_loop |
| 3 | 断言 _run_loop 进 PauseAndEscalate（broadcast `Escalated{reason="phase_route_error"}`）| True |
| 4 | 断言 `runs.state == "paused"` | True |

### 验证点

- exit≠0 即时暂停 + Escalated 广播（FR-002 AC-3 + flowchart branch#5）
- reason 字面对齐 ATS

### 后置检查

- run.lock 释放

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_run_orchestrator.py::test_t49_phase_route_exit_nonzero_pauses_and_escalates`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-040

### 关联需求

§Interface Contract `start_run` 端到端 · IAPI-001/002 · Test Inventory T50 · ATS INTG

### 测试目标

FastAPI TestClient + WebSocket client：`POST /api/runs/start` + 监听 `/ws/run/:id`；HTTP 200 RunStatus；WS 收到 `RunPhaseChanged(state="starting")` 然后 `(state="running")`。

### 前置条件

- `.venv` 激活；FastAPI TestClient + websockets

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | TestClient `POST /api/runs/start` body `{"workdir": <legal git repo>}` | 响应 |
| 2 | 断言 HTTP 200 + 响应 body 含 `state` 字段值 ∈ `{"starting","running"}` | True |
| 3 | TestClient WebSocket 订阅 `/ws/run/{run_id}` | 连接 |
| 4 | 收集 envelopes 直至 2 个或 5s timeout | 收集成功 |
| 5 | 断言 envelopes 至少含 `RunPhaseChanged(state="starting")` 且后续 `RunPhaseChanged(state="running")` | True |

### 验证点

- REST/WS 集成不断链（IAPI-001/002 端到端）
- 状态转换序列：starting → running

### 后置检查

- `await orchestrator.cancel_run(...)` 释放 lock

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f20_real_rest_ws.py::test_t50_post_runs_start_emits_ws_run_phase_changed`
- **Test Type**: Real
- **类别归属说明**：design 标 T50 为 INTG/api+ws；归 functional。

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-020-001 | FR-001 AC-1 / T01 | verification_steps[0] | `tests/test_f20_run_orchestrator.py::test_t01_start_run_happy_path_enters_running` | Real | PASS |
| ST-FUNC-020-002 | FR-001 AC-3 / T02 | verification_steps[1] | `tests/test_f20_run_orchestrator.py::test_t02_start_run_rejects_non_git_repo` | Real | PASS |
| ST-FUNC-020-003 | FR-002 AC-2 / T03 | verification_steps[2] | `tests/test_f20_phase_route_invoker.py::test_t03_invoke_happy_path_returns_phase_route_result` | Real | PASS |
| ST-FUNC-020-004 | FR-002 AC-3 / T04 | verification_steps[14]-[15] | `tests/test_f20_phase_route_invoker.py::test_t04_invoke_exit_nonzero_raises_phase_route_error` | Real | PASS |
| ST-FUNC-020-005 | FR-002 / IFR-003 / T05 | verification_steps[2] | `tests/integration/test_f20_real_subprocess.py::test_t05_real_phase_route_subprocess_returns_valid_phase_route_result` | Real | PASS |
| ST-BNDRY-020-001 | NFR-015 / T06 | verification_steps[15] | `tests/test_f20_phase_route_invoker.py::test_t06_relaxed_parsing_default_fields` | Real | PASS |
| ST-BNDRY-020-002 | FR-002 AC-3 / IFR-003 / T07 | verification_steps[15] | `tests/test_f20_phase_route_invoker.py::test_t07_stdout_not_json_raises_parse_error_and_audits` | Real | PASS |
| ST-FUNC-020-006 | FR-003 / T08 | verification_steps[3] | `tests/test_f20_phase_route_invoker.py::test_t08_hotfix_signal_passed_through_via_skill_hint` | Real | PASS |
| ST-FUNC-020-007 | FR-004 AC-1 / T09 | verification_steps[15]（pause）| `tests/test_f20_run_orchestrator.py::test_t09_pause_run_transitions_via_pause_pending` | Real | PASS |
| ST-FUNC-020-008 | FR-004 AC-3 / T10 | verification_steps[15]（cancel）| `tests/test_f20_run_orchestrator.py::test_t10_cancel_run_no_resume_endpoint` | Real | PASS |
| ST-FUNC-020-009 | FR-024 AC-1 / T11 | verification_steps[7] | `tests/test_f20_anomaly_recovery.py::test_t11_context_overflow_retry_zero_delay_and_increment` | Real | PASS |
| ST-BNDRY-020-003 | NFR-003 / FR-024 AC-2 / T12 | verification_steps[7] | `tests/test_f20_anomaly_recovery.py::test_t12_context_overflow_4th_attempt_escalates` | Real | PASS |
| ST-PERF-020-001 | NFR-004 / FR-025 AC-1 / T13 | verification_steps[8] | `tests/test_f20_anomaly_recovery.py::test_t13_rate_limit_backoff_sequence_30_120_300_none` | Real | PASS |
| ST-FUNC-020-010 | NFR-004 / FR-025 / T14 | verification_steps[8] | `tests/integration/test_f20_real_subprocess.py::test_t14_real_asyncio_sleep_first_retry_interval_30s_within_tolerance` | Real | PASS |
| ST-FUNC-020-011 | FR-026 AC-1/2/3 / T15 | verification_steps[15]（network）| `tests/test_f20_anomaly_recovery.py::test_t15_network_backoff_sequence_0_60_none` | Real | PASS |
| ST-BNDRY-020-004 | RetryPolicy.retry_count Empty/Null Boundary | verification_steps[15] | `tests/test_f20_anomaly_recovery.py::test_retry_policy_negative_retry_count_raises` | Real | PASS |
| ST-FUNC-020-012 | FR-027 AC-1 / T16 | verification_steps[9] | `tests/test_f20_anomaly_recovery.py::test_t16_watchdog_arm_fires_sigterm_after_timeout` | Real | PASS |
| ST-FUNC-020-013 | FR-027 AC-2 / T17 | verification_steps[9] | `tests/test_f20_anomaly_recovery.py::test_t17_watchdog_escalates_to_sigkill_after_sigterm_5s` | Real | PASS |
| ST-FUNC-020-014 | FR-028 AC-1 / T18 | verification_steps[10] | `tests/test_f20_anomaly_recovery.py::test_t18_skill_error_passthrough_to_aborted_no_retry` | Real | PASS |
| ST-FUNC-020-015 | FR-028 AC-2 / T19 | verification_steps[10] | `tests/test_f20_anomaly_recovery.py::test_t19_skill_error_pauses_run_in_orchestrator` | Real | PASS |
| ST-FUNC-020-016 | FR-029 AC-1 / T20 | verification_steps[11] | `tests/test_f20_user_override.py::test_t20_skip_anomaly_resets_counter_and_invokes_phase_route` | Real | PASS |
| ST-FUNC-020-017 | FR-029 AC-2 / T21 | verification_steps[11] | `tests/test_f20_user_override.py::test_t21_force_abort_transitions_running_to_aborted` | Real | PASS |
| ST-FUNC-020-018 | FR-029 / T22 | verification_steps[11] | `tests/test_f20_user_override.py::test_t22_skip_anomaly_invalid_state_409` | Real | PASS |
| ST-FUNC-020-019 | FR-039 / T23 | verification_steps[14] | `tests/test_f20_validator_runner.py::test_t23_validator_happy_path_returns_ok_report` | Real | PASS |
| ST-FUNC-020-020 | FR-040 / IAPI-016 / T24 | verification_steps[13]-[14] | `tests/integration/test_f20_real_subprocess.py::test_t24_real_validate_features_subprocess` | Real | PASS |
| ST-FUNC-020-021 | FR-040 AC-2 / T25 | verification_steps[14] | `tests/test_f20_validator_runner.py::test_t25_validator_exit_nonzero_does_not_swallow_stderr` | Real | PASS |
| ST-BNDRY-020-005 | FR-040 / Boundary timeout_s / T26 | verification_steps[14] | `tests/test_f20_validator_runner.py::test_t26_validator_timeout_raises_validator_timeout` | Real | PASS |
| ST-FUNC-020-022 | FR-042 AC-1 / T27 | verification_steps[12] | `tests/integration/test_f20_real_git.py::test_t27_git_tracker_begin_end_records_2_commits` | Real | PASS |
| ST-FUNC-020-023 | FR-042 / IFR-005 / T28 | verification_steps[12] | `tests/test_f20_git_tracker.py::test_t28_git_tracker_begin_in_non_git_repo_raises_git_error` | Real | PASS |
| ST-FUNC-020-024 | FR-042 / IAPI-013 / T29 | verification_steps[12] | `tests/integration/test_f20_real_git.py::test_t29_git_rev_parse_and_log_real_subprocess` | Real | PASS |
| ST-FUNC-020-025 | FR-047 AC-1 / T30 | verification_steps[5] | `tests/test_f20_ticket_supervisor.py::test_t30_run_dispatches_14_skill_subset` | Real | PASS |
| ST-BNDRY-020-006 | FR-047 AC-2 / T31 | verification_steps[5] | `tests/test_f20_phase_route_invoker.py::test_t31_unknown_skill_name_dispatchable` | Real | PASS |
| ST-FUNC-020-026 | FR-048 / T32 | verification_steps[4] | `tests/test_f20_signal_watcher.py::test_t32_watcher_yields_bugfix_request_within_2s` | Real | PASS |
| ST-FUNC-020-027 | FR-048 / IAPI-012 / T33 | verification_steps[4] | `tests/integration/test_f20_real_signal_fs.py::test_t33_real_watcher_yields_5_distinct_signal_kinds` | Real | PASS |
| ST-BNDRY-020-007 | FR-048 / debounce / T34 | verification_steps[4] | `tests/test_f20_signal_watcher.py::test_t34_watcher_debounces_rapid_writes` | Real | PASS |
| ST-FUNC-020-028 | NFR-016 / T35 | verification_steps[6] | `tests/test_f20_run_orchestrator.py::test_t35_start_run_already_running_409` | Real | PASS |
| ST-FUNC-020-029 | NFR-016 / INT-007 / T36 | verification_steps[6] | `tests/integration/test_f20_real_git.py::test_t36_concurrent_orchestrators_filelock_only_one_acquires` | Real | PASS |
| ST-SEC-020-001 | PathTraversalError / T37 | verification_steps[15] | `tests/test_f20_security.py::test_t37_path_traversal_blocked` | Real | PASS |
| ST-SEC-020-002 | IFR-003 / IFR-005 / T38 SEC | verification_steps[15] | `tests/test_f20_security.py::test_t38_subprocess_argv_no_shell_injection` | Real | PASS |
| ST-FUNC-020-030 | submit_command / T39 | verification_steps[15]（cancel via bus）| `tests/test_f20_run_orchestrator.py::test_t39_run_control_bus_cancel_command` | Real | PASS |
| ST-FUNC-020-031 | submit_command Raises / T40 | verification_steps[15] | `tests/test_f20_run_orchestrator.py::test_t40_run_control_bus_invalid_command_400` | Real | PASS |
| ST-FUNC-020-032 | run_ticket call order / T41 | verification_steps[15] | `tests/test_f20_ticket_supervisor.py::test_t41_run_ticket_call_order_begin_spawn_arm_events_disarm_classify_end_save` | Real | PASS |
| ST-BNDRY-020-008 | DepthGuard / T42 | verification_steps[15] | `tests/test_f20_ticket_supervisor.py::test_t42_depth_guard_rejects_depth_3` | Real | PASS |
| ST-FUNC-020-033 | list_commits IAPI-002 / T43 | verification_steps[12] | `tests/test_f20_ticket_supervisor.py::test_t43_list_commits_filters_and_orders_desc` | Real | PASS |
| ST-FUNC-020-034 | load_diff DiffNotFound / T44 | verification_steps[15] | `tests/test_f20_ticket_supervisor.py::test_t44_load_diff_unknown_sha_raises_diff_not_found` | Real | PASS |
| ST-FUNC-020-035 | broadcast_signal IAPI-001 / T45 | verification_steps[4] | `tests/test_f20_ticket_supervisor.py::test_t45_broadcast_signal_ws_envelope_shape` | Real | PASS |
| ST-FUNC-020-036 | FR-001 AC-2 / T46 | verification_steps[15] | `tests/test_f20_run_orchestrator.py::test_t46_phase_route_no_next_skill_completes_run` | Real | PASS |
| ST-FUNC-020-037 | run_ticket persistence / T47 / IAPI-011/009 | verification_steps[15] | `tests/integration/test_f20_real_db.py::test_t47_run_ticket_persists_to_real_sqlite` | Real | PASS |
| ST-FUNC-020-038 | FR-004 / flow CheckPause / T48 | verification_steps[15] | `tests/test_f20_run_orchestrator.py::test_t48_run_loop_pause_pending_skips_phase_route` | Real | PASS |
| ST-FUNC-020-039 | FR-002 AC-3 / flow PrOk no / T49 | verification_steps[14]-[15] | `tests/test_f20_run_orchestrator.py::test_t49_phase_route_exit_nonzero_pauses_and_escalates` | Real | PASS |
| ST-FUNC-020-040 | start_run end-to-end / T50 / IAPI-001/002 | verification_steps[0] | `tests/integration/test_f20_real_rest_ws.py::test_t50_post_runs_start_emits_ws_run_phase_changed` | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

---

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 47 |
| Passed | 47 |
| Failed | 0 |
| Pending | 0 |

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.
> 全部 47 用例自动化执行（无 `已自动化: No` 项）；映射到 51 个底层 pytest 函数（含 9 个 INTG 真实环境用例：T05/T14/T24/T27/T29/T33/T36/T47/T50）。
>
> **执行证据**（2026-04-25）：
> - `pytest tests/test_f20_*.py tests/integration/test_f20_*.py -q --no-header` → 51 passed, 8 warnings in 6.52s
> - 覆盖率门槛已在 long-task-quality 阶段验证（line 91.79% / branch 81.04% ≥ 90/80 — 见 commit 13c0957）
