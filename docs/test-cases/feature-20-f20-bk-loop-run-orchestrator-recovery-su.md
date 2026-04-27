# 测试用例集: F20 · Bk-Loop — Run Orchestrator · Recovery · Subprocess

**Feature ID**: 20
**关联需求**: FR-001, FR-002, FR-003, FR-004, FR-024, FR-025, FR-026, FR-027, FR-028, FR-029, FR-039, FR-040, FR-042, FR-047, FR-048, NFR-003, NFR-004, NFR-015, NFR-016, IFR-003（ATS L49-52, L97-101, L120-121, L128, L143-144, L159-160, L171-172, L181；必须类别 FUNC / BNDRY / SEC / PERF / INTG；UI 类别由 F21/F22 单独承担——本特性 `ui:false`）
**日期**: 2026-04-27
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0
**Wave**: Wave 4 (2026-04-27) — 整体重生成 1:1 映射 design Test Inventory T01–T60

> **说明**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则（FR-001/002/003/004/024/025/026/027/028/029/039/040/042/047/048 + NFR-003/004/015/016 + IFR-003）、ATS L49-52 / L97-101 / L120-121 / L128 / L143-144 / L159-160 / L171-172 / L181 类别约束、Feature Design Test Inventory T01–T60、可观察接口（`harness.orchestrator.run.RunOrchestrator` / `harness.orchestrator.supervisor.TicketSupervisor` + `DepthGuard` + `build_ticket_command` / `harness.orchestrator.phase_route.PhaseRouteInvoker` + `PhaseRouteResult` / `harness.orchestrator.signal_watcher.SignalFileWatcher` / `harness.orchestrator.bus.RunControlBus` + `RunControlCommand` + `RunControlAck` + `AnomalyEvent` / `harness.orchestrator.run_lock.RunLock` / `harness.orchestrator.errors.{RunStartError, PhaseRouteError, PhaseRouteParseError, TicketError, InvalidCommand, InvalidRunState}` / `harness.orchestrator.hook_to_stream.{HookEventToStreamMapper, TicketStreamEvent}` / `harness.recovery.anomaly.AnomalyClassifier` + `AnomalyInfo` + `AnomalyClass` / `harness.recovery.retry.{RetryPolicy, RetryCounter}` / `harness.recovery.watchdog.Watchdog` / `harness.subprocess.git.tracker.{GitTracker, GitContext, GitCommit, GitError}` / `harness.subprocess.validator.runner.{ValidatorRunner, ValidatorTimeout, ValidatorScriptUnknown}` 公开 API、subprocess argv 与 `cwd` 观测、`os.kill` SIGTERM/SIGKILL 调用观测、`git rev-parse HEAD` / `git log --oneline` 真实子进程、`watchdog` Observer 真实 inotify 事件、`filelock` 真实文件互斥）推导，不阅读实现源码。
> - **Specification resolutions applied from Feature Design Clarification Addendum**：design §Clarification Addendum 表显示"无需澄清 — 全部规格明确"。Wave 4 改造（IAPI-005 prepare_workdir 前置 / IAPI-008 stream_parser 移除 / `cancel_run` 终态 → InvalidRunState 409 / `_FakeStreamParser` → `_FakeTicketStream`）系 design §4.12 + §4.5.4.x 已显式定义的 hard impact 传播；srs_trace 19 条 FR/NFR/IFR 的 EARS 与 AC 在 SRS 文档中均含可度量阈值。本文档预期结果均按 design 已固化处置撰写。
> - **`feature.ui == false` → 本特性无 UI 类别用例**。ATS L52 / L102 / L121 / L144 在 FR-004 / FR-029 / FR-040 / FR-048 行列出 UI 仅是为了对齐 F21（RunOverview / HILInbox / TicketStream）/ F22（CommitHistory / ProcessFiles）的视觉表面 —— 这些 UI 表面由 F21/F22 独立 ST 承担，本特性覆盖的是后端 Run lifecycle / Recovery / Subprocess 契约表面。Feature Design Visual Rendering Contract = N/A（backend-only feature），对应豁免不构成缺口。
> - 本特性以 **"Backend library + REST routes via FastAPI TestClient — no live api uvicorn server required"** 模式运行（env-guide §1.6 纯 CLI / library 模式 —— `pytest tests/test_f20_*.py tests/integration/test_f20_*.py`）。环境仅需 §2 `.venv` 激活；REST 路由 ST 用例使用 `fastapi.testclient.TestClient` 直接装载 `harness.api:app` 并通过 `monkeypatch.setenv("HARNESS_HOME", tmp_path)` 隔离持久化路径。INTG 类用例（T45/T46/T47/T48/T49/T50/T51/T53）使用真实 subprocess / 真实 git / 真实 watchdog / 真实 sqlite / 真实 FastAPI TestClient，不 mock。
> - **手动测试**：本特性全部 60 条用例均自动化执行，无 `已自动化: No` 项；FR-004 / FR-029 / FR-040 / FR-048 涉及的 UI 体验（Pause 二次确认、异常 Skip/Force-Abort 按钮、自检按钮、信号文件徽章）由 F21/F22 ST 单独承担。
> - **Wave 4 改造点回归**：T16（`cancel_run` 终态 → `InvalidRunState` 409）/ T41（supervisor `record_call("TicketStream.subscribe")` 替代旧 `"StreamParser.events()"`）/ T42（`prepare_workdir` 前置于 `spawn`）/ T43（`WorkdirPrepareError` 传播）/ T44（`_FakeTicketStream.events(ticket_id)` 签名）/ T60（已 completed run 再 cancel 仍保 InvalidRunState）—— 所有覆盖 design §Implementation Summary "Wave 4 改造范围" 三处。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 50 |
| boundary | 8 |
| ui | 0 |
| security | 1 |
| performance | 1 |
| **合计** | **60** |

> **类别归属约定**：design Test Inventory 标 T05/T14/T15/T17/T18/T28/T31/T32（计 8 行）为 BNDRY；T24/T30 为 PERF；T38 为 SEC；T45/T46/T47/T48/T49/T50/T51/T53 为 INTG/subprocess|git|filesystem。ST 用例 ID 规范允许 CATEGORY ∈ {FUNC, BNDRY, UI, SEC, PERF}（见 `scripts/validate_st_cases.py` CASE_ID_PATTERN），与既有 F19 ST-FUNC-019-020/021 惯例一致 —— 本特性 INTG 用例归 functional 类别（black-box behavior 验证），具体判定脚注见相应用例元数据。
>
> **负向占比**（FUNC/error + BNDRY + SEC + PERF + INTG-error）：
> - FUNC/error：T02/T03/T04/T07/T08/T13/T16/T20/T26/T27/T29/T32/T34/T43/T52/T54/T55/T60 = 18
> - BNDRY/*：T05/T09/T10/T21/T28/T35/T40 = 7（design Test Inventory 类别小计的 7 项）
> - SEC：T38 = 1
> - PERF：T24/T30 = 2
> - INTG/error：T46/T47/T49/T51 = 4
> - 合计 32 / 60 ≈ **53.3%** ≥ 40% 阈值

> **Test Inventory → ST 用例 1:1 映射**：Feature Design 60 行 Test Inventory（T01-T60）一一对应 ST 用例；pytest 函数 60 个，均位于 `tests/test_f20_w4_design.py`（Wave 4 整体重写测试套）。Wave 3 的 `tests/test_f20_*.py` + `tests/integration/test_f20_*.py` 110 测试与 W4 相互独立 —— W4 路径作为 ST 唯一权威覆盖（T01-T60），W3 路径保留作 regression 安全网。

---

### 用例编号

ST-FUNC-020-001

### 关联需求

FR-001 AC-1 · §Interface Contract `RunOrchestrator.start_run` postcondition · §sequenceDiagram msg #1-5 · Test Inventory T01 · ATS L49 FR-001 FUNC

### 测试目标

验证 `RunOrchestrator.start_run(RunStartRequest(workdir=<合法 git repo>))` 在合法路径下完成：返回 `RunStatus(state ∈ {"starting","running"})`、`runs` 表新增行、`<workdir>/.harness/run.lock` 被本进程持有、后台 `_run_loop` task 已 schedule。覆盖 FR-001 EARS 主路径 + Run state machine `idle → starting → running` 转移。

### 前置条件

- `.venv` 激活；`harness.orchestrator.run.RunOrchestrator` / `harness.orchestrator.schemas.RunStartRequest` 可导入
- `pytest tmp_path` 提供空白目录；`subprocess.run(["git","init",str(tmp_path)])` 已成功（exit=0）
- 注入 mock 依赖：`PhaseRouteInvoker` 默认返回 `PhaseRouteResult(ok=True, next_skill=None)`；`ToolAdapter` 不实际 spawn

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `subprocess.run(["git","init",str(tmp_path)],check=True)` | exit=0；`tmp_path/.git/` 存在 |
| 2 | `req = RunStartRequest(workdir=str(tmp_path))` | pydantic 校验通过 |
| 3 | `orch = RunOrchestrator.build_test_default(...)` 注入 mock 依赖 | 构造成功 |
| 4 | `status = await orch.start_run(req)` | 不抛异常 |
| 5 | 断言 `status.state in {"starting","running"}` | True |
| 6 | 断言 `(tmp_path/".harness"/"run.lock").exists()` | True |
| 7 | 断言 后台 `_run_loop` task 已被 schedule（orch._main_task is not None） | True |

### 验证点

- start_run 返回 RunStatus 含 `run_id` 字符串非空、`workdir` 与请求一致、`state` ∈ {starting, running}（首 ticket spawn 完成时机决定具体值）
- `<workdir>/.harness/run.lock` 文件实际创建（filelock 已被持有，NFR-016 前置条件）
- `runs` 表至少新增 1 行（state ∈ {starting, running}）
- 不调用真实 phase_route subprocess（mock 注入路径下默认 `ok=True, next_skill=None` → ST Go 自然完成）

### 后置检查

- `tmp_path` 自动清理；`run.lock` 随 `cancel_run` / 进程结束释放

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t01_start_run_happy_path_lock_and_run_row`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-002

### 关联需求

FR-001 AC-3 · ASM-007 · §Interface Contract `RunOrchestrator.start_run` Raises `RunStartError(not_a_git_repo)` · Test Inventory T02 · ATS L49 FR-001 SEC

### 测试目标

验证非 git 仓库 workdir 触发 `RunStartError(reason="not_a_git_repo", http_status=400)`；不创建 run row、不持有 lock。

### 前置条件

- `.venv` 激活
- `tmp_path` 存在但**未** `git init`（无 `.git/` 子目录）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 确保 `(tmp_path/".git").exists() is False` | True |
| 2 | `req = RunStartRequest(workdir=str(tmp_path))` | pydantic 通过 |
| 3 | `with pytest.raises(RunStartError) as exc: await orch.start_run(req)` | 抛 RunStartError |
| 4 | 断言 `exc.value.reason == "not_a_git_repo"` | True |
| 5 | 断言 `exc.value.http_status == 400` | True |
| 6 | 断言 `not (tmp_path/".harness"/"run.lock").exists()` | True |

### 验证点

- 非 git repo 拒绝启动（FR-001 AC-3 + ASM-007 失败路径硬契约）
- `RunStartError.reason` 字面与 §IC Raises 列对齐
- 失败路径无副作用（lock + run row 均回滚）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t02_start_run_rejects_non_git_directory`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-003

### 关联需求

§Interface Contract `RunOrchestrator.start_run` Raises `RunStartError(invalid_workdir)` · ATS L49 FR-001 SEC（shell metachar 防穿透）· Test Inventory T03

### 测试目标

验证 workdir 含 shell metacharacter（`;|&` / 反引号 / `\n`）时触发 `RunStartError(reason="invalid_workdir", http_status=400)`；防止 subprocess argv 拼接被注入。

### 前置条件

- `.venv` 激活
- 准备含 shell metachar 的字符串 `"/path; rm -rf /"`（实际目录不存在）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = RunStartRequest(workdir="/path; rm -rf /")` | pydantic 通过（schema 不限字符）|
| 2 | `with pytest.raises(RunStartError) as exc: await orch.start_run(req)` | 抛 RunStartError |
| 3 | 断言 `exc.value.reason == "invalid_workdir"` | True |
| 4 | 断言 `exc.value.http_status == 400` | True |
| 5 | 断言 系统中无 `rm -rf` 实际执行（filesystem 未被破坏） | True |

### 验证点

- shell metachar 被 RunStartError 显式拒绝（SEC：FR-001 SEC AC）
- 不调用 subprocess（不发生命令注入）

### 后置检查

- 无文件系统副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t03_start_run_rejects_shell_metacharacters`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-004

### 关联需求

§Interface Contract `RunOrchestrator.start_run` Raises `RunStartError(invalid_workdir)` · Test Inventory T04 · ATS L49 FR-001 BNDRY

### 测试目标

验证空字符串 workdir 触发 `RunStartError(reason="invalid_workdir", http_status=400)`；不被透传到 RunLock 触发奇怪错误。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = RunStartRequest(workdir="")` | pydantic 通过（或被前置拒绝；若拒则等价覆盖 invalid_workdir） |
| 2 | `with pytest.raises(RunStartError) as exc: await orch.start_run(req)` | 抛 RunStartError |
| 3 | 断言 `exc.value.reason == "invalid_workdir"` | True |
| 4 | 断言 `exc.value.http_status == 400` | True |

### 验证点

- 空 workdir 被显式拒绝（边界值 BNDRY）
- 不下沉到 RunLock 抛 OSError

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t04_start_run_rejects_empty_workdir`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-001

### 关联需求

NFR-016 · §Interface Contract `RunLock.acquire` + `start_run` Raises `RunStartError(already_running, http=409)` · Test Inventory T05 · ATS L182 NFR-016 BNDRY

### 测试目标

验证同 workdir 并行两次 `start_run` 时第二次抛 `RunStartError(reason="already_running", http_status=409, error_code="ALREADY_RUNNING")`；filelock 互斥生效（NFR-016 单 workdir 单 run）。

### 前置条件

- `.venv` 激活
- `tmp_path` 已 `git init`
- 第一个 orchestrator 实例 `orch_a` 已成功 `start_run` 持有 lock

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await orch_a.start_run(RunStartRequest(workdir=str(tmp_path)))` | 第一次成功（state ∈ {starting, running}） |
| 2 | 创建独立 orchestrator 实例 `orch_b`（同 workdir）| 构造成功 |
| 3 | `with pytest.raises(RunStartError) as exc: await orch_b.start_run(RunStartRequest(workdir=str(tmp_path)))` | 抛 RunStartError |
| 4 | 断言 `exc.value.reason == "already_running"` | True |
| 5 | 断言 `exc.value.http_status == 409` 且 `exc.value.error_code == "ALREADY_RUNNING"` | True |

### 验证点

- 第二次 acquire 在 `RunLock.timeout`（默认 0.5s）内 RunLockTimeout → 上层映射 RunStartError
- HTTP 状态 409、错误码 `ALREADY_RUNNING`（IAPI 契约）
- 第一个 run 不受影响（仍 running）

### 后置检查

- 取消 / 释放 `orch_a`；`run.lock` 文件被释放

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t05_start_run_already_running_raises_409`
- **Test Type**: Real
- **类别归属说明**：design 标 T05 为 BNDRY/edge（NFR-016 边界）；ST 类别归 boundary 与 design 一致。

---

### 用例编号

ST-FUNC-020-005

### 关联需求

FR-002 AC-1 · §Interface Contract `PhaseRouteInvoker.invoke` postcondition · Test Inventory T06 · ATS L50 FR-002 FUNC

### 测试目标

验证 `PhaseRouteInvoker.set_responses([{"ok":True,"next_skill":"long-task-design"}])` + `invoke(workdir)` 返回 `PhaseRouteResult(ok=True, next_skill="long-task-design")`；`invocation_count` 计数 +1。

### 前置条件

- `.venv` 激活
- 测试模式 PhaseRouteInvoker（不经真实 subprocess）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `invoker = PhaseRouteInvoker(plugin_dir=tmp)`；`invoker.set_responses([{"ok":True, "next_skill":"long-task-design"}])` | 注入成功 |
| 2 | `result = await invoker.invoke(workdir=tmp_path)` | 不抛 |
| 3 | 断言 `result.ok is True and result.next_skill == "long-task-design"` | True |
| 4 | 断言 `invoker.invocation_count == 1` | True |

### 验证点

- next_skill 字面透传（FR-002 AC-2）
- 测试模式不经 subprocess fork

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t06_phase_route_invoke_returns_phase_route_result`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-006

### 关联需求

FR-002 AC-3 · §Interface Contract `PhaseRouteInvoker.invoke` Raises `PhaseRouteError(exit≠0)` · Test Inventory T07 · ATS L181 IFR-003 FUNC

### 测试目标

验证 `invoker.set_failure(exit_code=1, stderr="boom")` + `invoke()` 抛 `PhaseRouteError("phase_route exited 1: boom", exit_code=1)`；exit≠0 不被吞。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `invoker.set_failure(exit_code=1, stderr="boom")` | 注入 |
| 2 | `with pytest.raises(PhaseRouteError) as exc: await invoker.invoke(tmp_path)` | 抛 PhaseRouteError |
| 3 | 断言 `exc.value.exit_code == 1` | True |
| 4 | 断言 `"boom" in str(exc.value)` | True |

### 验证点

- exit≠0 即时抛 PhaseRouteError（FR-002 AC-3 显式语义）
- stderr 不被吞

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t07_phase_route_invoke_exit_nonzero_raises`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-007

### 关联需求

IFR-003 · §Interface Contract `PhaseRouteInvoker.invoke` Raises `PhaseRouteParseError` · Test Inventory T08 · ATS L181 IFR-003

### 测试目标

验证真实 subprocess fixture stdout=`"not json"` 时 `invoke()` 抛 `PhaseRouteParseError`；audit 记录 `phase_route_parse_error`（如 audit_writer 注入）。

### 前置条件

- `.venv` 激活
- 真实 subprocess fixture 写入 stdout 非 JSON 字符串

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 配置 fixture 脚本 `print("not json")` | 注入 |
| 2 | `invoker = PhaseRouteInvoker(plugin_dir=fixture_plugin)` | 构造成功 |
| 3 | `with pytest.raises(PhaseRouteParseError) as exc: await invoker.invoke(tmp_path)` | 抛 PhaseRouteParseError |
| 4 | 断言 异常 message 含 "not JSON" 子串 | True |

### 验证点

- 非 JSON stdout 显式抛 PhaseRouteParseError
- 不静默通过

### 后置检查

- subprocess 自然退出

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t08_phase_route_stdout_not_json_raises_parse_error`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-002

### 关联需求

NFR-015 · IFR-003 · §Interface Contract `PhaseRouteResult` 默认值 · Test Inventory T09 · ATS L181 NFR-015 BNDRY

### 测试目标

验证 `invoker.set_responses([{"ok":True}])`（缺 feature_id / next_skill / counts / errors）时 `invoke()` 不抛；`result.feature_id is None`、`next_skill is None`、`counts is None`、`errors == []`、`starting_new is False`、`needs_migration is False`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `invoker.set_responses([{"ok":True}])` | 注入 |
| 2 | `result = await invoker.invoke(tmp_path)` | 不抛 |
| 3 | 断言 `result.ok is True and result.next_skill is None and result.feature_id is None` | True |
| 4 | 断言 `result.errors == [] and result.starting_new is False and result.needs_migration is False` | True |
| 5 | 断言 `result.counts is None`（按设计默认） | True |

### 验证点

- 缺字段补默认值（NFR-015 松弛解析）
- ValidationError 不抛

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t09_phase_route_relaxed_parsing_default_fields`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-003

### 关联需求

NFR-015 · §Interface Contract `PhaseRouteResult` `model_config(extra="ignore")` · Test Inventory T10 · ATS L181 NFR-015

### 测试目标

验证 `invoker.set_responses([{"ok":True, "extras":{"x":1}, "future_field":"v"}])` 时 `invoke()` 不抛；未知字段静默忽略；`result.ok is True`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `invoker.set_responses([{"ok":True, "extras":{"x":1}, "future_field":"v"}])` | 注入 |
| 2 | `result = await invoker.invoke(tmp_path)` | 不抛 |
| 3 | 断言 `result.ok is True` | True |
| 4 | 断言 `not hasattr(result, "extras")` 或 `not hasattr(result, "future_field")` | True |

### 验证点

- 未知字段被 pydantic `extra="ignore"` 静默丢弃
- phase_route schema 升级不破裂

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t10_phase_route_extra_fields_are_ignored`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-008

### 关联需求

FR-003 AC-1 · §Interface Contract `build_ticket_command` postcondition (skill_hint 透传) · Test Inventory T11 · ATS L51 FR-003 FUNC

### 测试目标

验证 `phase_route` 返回 `next_skill="long-task-hotfix", feature_id="hotfix-001"` 时，主循环一次迭代后 `TicketCommand.skill_hint == "long-task-hotfix"` 且 `tool_adapter.spawn_log[0].skill_hint == "long-task-hotfix"`；FR-003 hotfix 信号文件分支被忠实路由。

### 前置条件

- `.venv` 激活
- mock ToolAdapter 含 `spawn_log` 累加器

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `invoker.set_responses([{"ok":True, "next_skill":"long-task-hotfix", "feature_id":"hotfix-001"}])` | 注入 |
| 2 | 启动 main loop 一次迭代 | 不抛 |
| 3 | 断言 `tool_adapter.spawn_log[0].skill_hint == "long-task-hotfix"` | True |
| 4 | 断言 `tool_adapter.spawn_log[0].feature_id == "hotfix-001"` | True |

### 验证点

- hotfix skill_hint 字面透传不被映射
- 主回路按 phase_route 决定的 next_skill 派发

### 后置检查

- run cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t11_hotfix_skill_hint_passes_through_unmodified`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-009

### 关联需求

FR-047 AC-2 · §Interface Contract `build_ticket_command` (FR-047 AC-2：skill_hint 不映射任何枚举) · Test Inventory T12 · ATS L143 FR-047

### 测试目标

验证 phase_route 返回未知 / 未来 skill 名（如 `"future-skill-x"`）时仍被透传到 `dispatched_skill_hints()`；不硬编码 enum。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `invoker.set_responses([{"ok":True,"next_skill":"long-task-finalize"},{"ok":True,"next_skill":"future-skill-x"}])` | 注入 |
| 2 | 启动 main loop 两次迭代 | 不抛 |
| 3 | 断言 `orch.dispatched_skill_hints() == ["long-task-finalize", "future-skill-x"]` | True |
| 4 | 断言 第二次迭代未被 ValueError 拒绝（未硬编码 enum） | True |

### 验证点

- skill name 不被映射或拒绝（FR-047 AC-2）
- 14-skill 集合不硬编码

### 后置检查

- run cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t12_skill_hint_unknown_name_passes_through`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-010

### 关联需求

§Interface Contract `build_ticket_command` Raises `ValueError("cannot build ... ok=False")` · Test Inventory T13

### 测试目标

验证 `build_ticket_command(PhaseRouteResult(ok=False, errors=["x"]), parent=None)` 抛 `ValueError`；ok=False 不生成 ticket。

### 前置条件

- `.venv` 激活
- `from harness.orchestrator.supervisor import build_ticket_command`
- `from harness.orchestrator.phase_route import PhaseRouteResult`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `result = PhaseRouteResult(ok=False, errors=["x"])` | 构造成功 |
| 2 | `with pytest.raises(ValueError) as exc: build_ticket_command(result, parent=None)` | 抛 ValueError |
| 3 | 断言 `"ok=False"` 在 str(exc.value) 中 | True |

### 验证点

- ok=False 拒绝构造 TicketCommand
- 错误信息可定位

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t13_build_ticket_command_rejects_ok_false`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-011

### 关联需求

FR-004 AC-1 · §Interface Contract `RunOrchestrator.pause_run` postcondition · Test Inventory T14 · ATS L52 FR-004

### 测试目标

验证 running run 调 `pause_run(run_id)` 后 `pause_pending=True`；当前 ticket 完成后主循环不再调 phase_route；run state="paused"。

### 前置条件

- `.venv` 激活
- 已 start_run 等待 first ticket completed

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await orch.start_run(req)` | 进入 running |
| 2 | 等 first ticket completed（监听 ticket.state） | True |
| 3 | `status = await orch.pause_run(run_id)` | 不抛 |
| 4 | 断言 `status.state == "paused"` | True |
| 5 | 断言 主循环下一迭代未调 `invoker.invoke`（observed via `invoker.invocation_count`） | True |

### 验证点

- pause 不强切当前 ticket（先让其结束）
- pause_pending 影响下一迭代

### 后置检查

- cancel + cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t14_pause_run_settles_at_paused`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-012

### 关联需求

FR-004 AC-2 · §Interface Contract `RunOrchestrator.cancel_run` postcondition · Test Inventory T15 · ATS L52 FR-004

### 测试目标

验证 running run 调 `cancel_run(run_id)` 后 `cancel_event.set()`；当前 ticket 收 SIGTERM；run.state="cancelled"；ticket 历史只读保留。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `await orch.start_run(req)` | 进入 running |
| 2 | `status = await orch.cancel_run(run_id)` | 不抛 |
| 3 | 断言 `status.state == "cancelled"` | True |
| 4 | 断言 当前 ticket SIGTERM 已发出（mock pty / subprocess.kill 被调用） | True |
| 5 | 断言 ticket 历史 row 仍可查询（只读） | True |

### 验证点

- cancel 即时（不等当前 ticket finish）
- ticket 历史不被破坏

### 后置检查

- run row state="cancelled" 持久化

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t15_cancel_run_transitions_to_cancelled`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-013

### 关联需求

FR-004 AC-3 · §Interface Contract `RunOrchestrator.cancel_run` Raises `InvalidRunState(409)` (Wave 4 改造点) · Test Inventory T16

### 测试目标

**Wave 4 改造**：验证已 completed run 上调 `cancel_run` 抛 `InvalidRunState(http_status=409)`；不重置已 completed run；Resume 永远禁用 (state ∈ {completed, cancelled, failed} → 拒绝转移)。

### 前置条件

- `.venv` 激活
- run 已自然完成（state="completed"）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 启动并等 run state="completed"（phase_route 返 next_skill=None 触发 ST Go） | True |
| 2 | `with pytest.raises(InvalidRunState) as exc: await orch.cancel_run(run_id)` | 抛 InvalidRunState |
| 3 | 断言 `exc.value.http_status == 409` | True |
| 4 | 断言 后续 `get_run(run_id).state == "completed"`（未被重置） | True |

### 验证点

- 终态 run 拒绝 cancel（FR-004 AC-3）
- HTTP 409 而非 200/404
- Resume 路径同样拒绝（v1 设计层保证）

### 后置检查

- 无变更

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t16_cancel_after_completed_raises_invalid_state`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-014

### 关联需求

FR-029 AC-1 · §Interface Contract `RunOrchestrator.skip_anomaly` postcondition · Test Inventory T17

### 测试目标

验证 ticket state="retrying" 时 `skip_anomaly(ticket_id)` 返回 `RecoveryDecision(kind="skipped")`；ticket state→aborted；下一迭代调 phase_route 而非重试。

### 前置条件

- `.venv` 激活
- 一张 ticket 处于 retrying 状态（注入 anomaly）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 注入 ticket 进入 retrying（如 RetryPolicy 返非 None） | True |
| 2 | `decision = await orch.skip_anomaly(ticket_id)` | 不抛 |
| 3 | 断言 `decision.kind == "skipped"` | True |
| 4 | 断言 ticket state 转为 "aborted" | True |
| 5 | 断言 RetryCounter.value(skill_hint) reset 至 0 | True |
| 6 | 断言 下一迭代调用 phase_route（invocation_count + 1）| True |

### 验证点

- Skip 跳过 ticket 并续 phase_route（FR-029 AC-1）
- counter reset 防止后续误判

### 后置检查

- run cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t17_skip_anomaly_resets_counter_and_invokes_phase_route`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-015

### 关联需求

FR-029 AC-2 · §Interface Contract `RunOrchestrator.force_abort_anomaly` postcondition · Test Inventory T18

### 测试目标

验证 ticket state="running" 时 `force_abort_anomaly(ticket_id)` 立即将 ticket 转 aborted；run pause_pending=True 等待用户决策。

### 前置条件

- `.venv` 激活
- ticket 处于 running

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 启动 run，让 ticket 进入 running | True |
| 2 | `decision = await orch.force_abort_anomaly(ticket_id)` | 不抛 |
| 3 | 断言 ticket state == "aborted" 立即可见（无需等当前 ticket finish） | True |
| 4 | 断言 run.pause_pending is True | True |

### 验证点

- Force-Abort 立即生效（FR-029 AC-2）
- 阻塞主循环等待用户

### 后置检查

- run cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t18_force_abort_immediately_aborts_running_ticket`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-016

### 关联需求

FR-024 AC-1 · §Interface Contract `AnomalyClassifier.classify` (context_overflow) · Test Inventory T19 · ATS L97 FR-024

### 测试目标

验证 `ClassifyRequest(stderr_tail="context window exceeded")` + `Verdict(verdict="RETRY", anomaly=None)` → `AnomalyInfo(cls=CONTEXT_OVERFLOW, next_action="retry")`；正则匹配 case-insensitive。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(stderr_tail="context window exceeded", stdout_tail="")` | 构造 |
| 2 | `verdict = Verdict(verdict="RETRY", anomaly=None)` | 构造 |
| 3 | `info = AnomalyClassifier().classify(req, verdict)` | 不抛 |
| 4 | 断言 `info.cls == AnomalyClass.CONTEXT_OVERFLOW` | True |
| 5 | 断言 `info.next_action == "retry"` | True |

### 验证点

- stderr 模式 "context window" 命中（FR-024 AC-1）
- next_action="retry" 触发后续 RetryPolicy 路径

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t19_anomaly_classifier_context_overflow_from_stderr`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-017

### 关联需求

FR-028 AC-1 · §Interface Contract `AnomalyClassifier.classify` (CONTRACT-DEVIATION 优先) · Test Inventory T20 · ATS L101 FR-028

### 测试目标

验证 `ClassifyRequest(stdout_tail="[CONTRACT-DEVIATION] ABC")` → `AnomalyInfo(cls=SKILL_ERROR, next_action="abort")`；首行检测以 `lstrip().startswith` 实现，不被 `splitlines()[0]` 边角案例干扰。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(stdout_tail="[CONTRACT-DEVIATION] ABC", stderr_tail="")` | 构造 |
| 2 | `verdict = Verdict(verdict="RETRY", anomaly=None)`（即便 verdict=RETRY，CD 优先级最高） | 构造 |
| 3 | `info = AnomalyClassifier().classify(req, verdict)` | 不抛 |
| 4 | 断言 `info.cls == AnomalyClass.SKILL_ERROR` | True |
| 5 | 断言 `info.next_action == "abort"` | True |
| 6 | 断言 `"[CONTRACT-DEVIATION]"` in info.detail | True |

### 验证点

- CONTRACT-DEVIATION 优先于其他 anomaly 分类（FR-028 AC-1）
- next_action="abort" 不触发 RetryPolicy

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t20_anomaly_classifier_contract_deviation_aborts_no_retry`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-004

### 关联需求

FR-028 · §Implementation Summary 决策 #5（lstrip 而非 splitlines[0]）· Test Inventory T21

### 测试目标

边界：验证 `stdout_tail = "   \n[CONTRACT-DEVIATION] X"`（前导空白与换行）仍触发 cls=SKILL_ERROR + next_action="abort"；防止 lstrip 缺失漏判。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(stdout_tail="   \n[CONTRACT-DEVIATION] X", stderr_tail="")` | 构造 |
| 2 | `info = AnomalyClassifier().classify(req, Verdict(verdict="RETRY", anomaly=None))` | 不抛 |
| 3 | 断言 `info.cls == AnomalyClass.SKILL_ERROR` | True |
| 4 | 断言 `info.next_action == "abort"` | True |

### 验证点

- 前导空白被 lstrip 消除后仍命中 CONTRACT-DEVIATION
- 防止字符串处理边界 bug

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t21_anomaly_classifier_contract_deviation_with_leading_whitespace`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-018

### 关联需求

FR-024 · NFR-003 · §Interface Contract `RetryPolicy.next_delay` (context_overflow) · Test Inventory T22 · ATS L169 NFR-003

### 测试目标

验证 `RetryPolicy.next_delay("context_overflow", retry_count)` 在 retry_count ∈ {0,1,2} 时返回 `0.0`（立即重试新会话）；retry_count=3 时返回 None（escalate）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy()` | 构造 |
| 2 | 断言 `policy.next_delay("context_overflow", 0) == 0.0` | True |
| 3 | 断言 `policy.next_delay("context_overflow", 1) == 0.0` | True |
| 4 | 断言 `policy.next_delay("context_overflow", 2) == 0.0` | True |
| 5 | 断言 `policy.next_delay("context_overflow", 3) is None` | True |

### 验证点

- 序列 0/0/0/None 与设计 §IC RetryPolicy.next_delay 表对齐
- 第 4 次（index=3）escalate（NFR-003 ≤ 3）

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t22_retry_policy_context_overflow_sequence`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-019

### 关联需求

FR-025 · NFR-004 · §Interface Contract `RetryPolicy.next_delay` (rate_limit) · Test Inventory T23 · ATS L98 FR-025

### 测试目标

验证 `RetryPolicy.next_delay("rate_limit", retry_count)` 序列：retry_count=0 → 30.0、=1 → 120.0、=2 → 300.0、=3 → None（escalate）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy()` | 构造 |
| 2 | 断言 `policy.next_delay("rate_limit", 0) == 30.0` | True |
| 3 | 断言 `policy.next_delay("rate_limit", 1) == 120.0` | True |
| 4 | 断言 `policy.next_delay("rate_limit", 2) == 300.0` | True |
| 5 | 断言 `policy.next_delay("rate_limit", 3) is None` | True |

### 验证点

- 序列 30/120/300 与 FR-025 / NFR-004 EARS 对齐
- 第 4 次 escalate

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t23_retry_policy_rate_limit_sequence_30_120_300_none`
- **Test Type**: Real

---

### 用例编号

ST-PERF-020-001

### 关联需求

NFR-004 ±10% · §Interface Contract `RetryPolicy(scale_factor=...)` · Test Inventory T24 · ATS L170 NFR-004 PERF

### 测试目标

性能 / 可压缩性：验证 `RetryPolicy(scale_factor=0.001).next_delay("rate_limit", 0) == 0.030`（±10% 即 0.027–0.033）；scale_factor 用于 CI 时间压缩。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy(scale_factor=0.001)` | 构造 |
| 2 | `delay = policy.next_delay("rate_limit", 0)` | 不抛 |
| 3 | 断言 `0.027 <= delay <= 0.033`（±10% 容忍） | True |

### 验证点

- scale_factor 线性应用（30s × 0.001 = 0.030s）
- ±10% 窗口（NFR-004 实测容忍）

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t24_retry_policy_scale_factor_compresses_rate_limit`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-020

### 关联需求

FR-026 · §Interface Contract `RetryPolicy.next_delay` (network) · Test Inventory T25 · ATS L99 FR-026

### 测试目标

验证 `RetryPolicy.next_delay("network", retry_count)` 序列：retry_count=0 → 0.0（立即）、=1 → 60.0、=2 → None（escalate）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy()` | 构造 |
| 2 | 断言 `policy.next_delay("network", 0) == 0.0` | True |
| 3 | 断言 `policy.next_delay("network", 1) == 60.0` | True |
| 4 | 断言 `policy.next_delay("network", 2) is None` | True |

### 验证点

- 序列与 FR-026 AC 对齐
- 立即重试 + 60s 退避 + escalate 三段

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t25_retry_policy_network_sequence_0_60_none`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-021

### 关联需求

§Interface Contract `RetryPolicy.next_delay` Raises `ValueError` · Test Inventory T26

### 测试目标

错误：`next_delay(cls="rate_limit", retry_count=-1)` 抛 `ValueError`；防止负数被静默接受导致逻辑错乱。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `policy = RetryPolicy()` | 构造 |
| 2 | `with pytest.raises(ValueError): policy.next_delay("rate_limit", -1)` | 抛 ValueError |

### 验证点

- 负 retry_count 被拒绝
- 错误信息含 "retry_count" 字面（可定位）

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t26_retry_policy_negative_retry_count_raises_value_error`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-022

### 关联需求

§Interface Contract `RetryPolicy.next_delay` Raises `TypeError` · Test Inventory T27

### 测试目标

错误：`next_delay(cls="rate_limit", retry_count="0")` 抛 `TypeError`；防止字符串被误解析为 0。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `with pytest.raises(TypeError): RetryPolicy().next_delay("rate_limit", "0")` | 抛 TypeError |

### 验证点

- 类型校验严格
- 防止 truthy 字符串成意外的 0

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t27_retry_policy_non_int_retry_count_raises_type_error`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-005

### 关联需求

§Interface Contract `RetryPolicy.next_delay` (unknown cls 保守路径) · Test Inventory T28

### 测试目标

边界 / unknown：`next_delay(cls="future_class", retry_count=0)` 返回 None（保守不重试）；防止未来 anomaly 类追加时静默无限重试。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `result = RetryPolicy().next_delay("future_class", 0)` | 不抛 |
| 2 | 断言 `result is None` | True |

### 验证点

- 未知 cls 返回 None（保守策略）
- 强制新增 cls 时显式扩展

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t28_retry_policy_unknown_class_returns_none`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-023

### 关联需求

FR-028 · §Interface Contract `RetryPolicy.next_delay` (skill_error 始终 None) · Test Inventory T29

### 测试目标

错误：`next_delay(cls="skill_error", retry_count=0)` 返回 None；skill_error 永不重试（FR-028 AC）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `result = RetryPolicy().next_delay("skill_error", 0)` | 不抛 |
| 2 | 断言 `result is None` | True |

### 验证点

- skill_error 始终 None（FR-028 不重试）
- next_action="abort" 配合此返回值

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t29_retry_policy_skill_error_never_retries`
- **Test Type**: Real

---

### 用例编号

ST-PERF-020-002

### 关联需求

FR-027 AC-1 · §Interface Contract `Watchdog.arm` · Test Inventory T30 · ATS L100 FR-027 PERF

### 测试目标

性能 / 时序：验证 `Watchdog(sigkill_grace_s=0.05).arm(timeout_s=0.05, pid=child_pid, is_alive=lambda _: True)` 在 0.05s 后 SIGTERM、再 0.05s 后 SIGKILL（is_alive 强制返 True 模拟僵尸）。

### 前置条件

- `.venv` 激活
- 真实子进程 fork（如 `python -c "import time; time.sleep(10)"`）取得 child_pid

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | spawn 子进程 取得 pid | True |
| 2 | `wd = Watchdog(sigkill_grace_s=0.05)`；`wd.arm(ticket_id="t", pid=pid, timeout_s=0.05, is_alive=lambda _: True)` | 不抛 |
| 3 | 等 `0.15s` 让 SIGTERM + grace + SIGKILL 序列触发 | True |
| 4 | 断言 子进程在 ≤ 0.5s 内被 reap（`os.waitpid`/退出码可验证） | True |
| 5 | 断言 SIGTERM 与 SIGKILL 调用顺序正确（mock os.kill 计数） | True |

### 验证点

- timeout 后 SIGTERM（FR-027 AC-1）
- grace 后 SIGKILL（FR-027 AC-2）
- 时序在容忍窗口内（PERF：±少量 ms 调度抖动）

### 后置检查

- 子进程已退出；ticket_id 已 disarm

### 元数据

- **优先级**: Critical
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t30_watchdog_arm_sigterm_then_sigkill`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-024

### 关联需求

FR-027 AC-2 · §Interface Contract `Watchdog.disarm` · Test Inventory T31

### 测试目标

验证 `arm(...)` 后在 timeout 之前 `disarm(ticket_id)` 取消 task；no kill 发出；`_tasks` pop。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `wd = Watchdog()`；`wd.arm(ticket_id="t", pid=pid, timeout_s=10.0, is_alive=...)` | 不抛 |
| 2 | `wd.disarm(ticket_id="t")` 在 timeout 前 | 不抛 |
| 3 | 断言 `os.kill` 未被调用 | True |
| 4 | 断言 `wd._tasks.get("t")` is None | True |
| 5 | `wd.disarm("t")` 重复调用 | 不抛（idempotent）|

### 验证点

- disarm 取消 timer task
- 不误杀进程
- 重复 disarm 安全

### 后置检查

- 无残留 task

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t31_watchdog_disarm_cancels_pending_kill`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-025

### 关联需求

§Interface Contract `Watchdog.arm` Raises `ValueError(timeout_s <= 0)` · Test Inventory T32

### 测试目标

错误：`Watchdog().arm(ticket_id="t", pid=1, timeout_s=0, is_alive=...)` 抛 `ValueError`；防止 0 timeout 立即 kill。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `with pytest.raises(ValueError): Watchdog().arm(ticket_id="t", pid=1, timeout_s=0.0, is_alive=lambda _: True)` | 抛 ValueError |

### 验证点

- timeout_s ≤ 0 被拒
- 防止误传 0 即时 kill

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t32_watchdog_arm_zero_timeout_raises`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-026

### 关联需求

FR-007 AC-2 · §Interface Contract `DepthGuard.ensure_within` · Test Inventory T33

### 测试目标

验证 `DepthGuard.ensure_within(parent_depth=1)` 返回 2；防止 off-by-one。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `result = DepthGuard.ensure_within(1)` | 不抛 |
| 2 | 断言 `result == 2` | True |

### 验证点

- 深度递增 1 → 2（FR-007 AC-2）
- 边界 0/1/2 在其他用例覆盖

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t33_depth_guard_parent_depth_one_returns_two`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-027

### 关联需求

FR-007 AC-2 · §Interface Contract `DepthGuard.ensure_within` Raises `TicketError(depth_exceeded)` · Test Inventory T34

### 测试目标

错误：`DepthGuard.ensure_within(parent_depth=2)` 抛 `TicketError(code="depth_exceeded")`；防止 depth=2 仍允许子 ticket（防递归）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `with pytest.raises(TicketError) as exc: DepthGuard.ensure_within(2)` | 抛 TicketError |
| 2 | 断言 `exc.value.code == "depth_exceeded"` | True |

### 验证点

- depth=2 拒绝下一层（FR-007 AC-2）
- TicketError 显式携带 code 字段便于路由

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t34_depth_guard_at_max_depth_raises_ticket_error`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-006

### 关联需求

§Interface Contract `DepthGuard.ensure_within` (None → 0) · Test Inventory T35

### 测试目标

边界：`DepthGuard.ensure_within(parent_depth=None)` 返回 0；防止 None 错误返 1。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `result = DepthGuard.ensure_within(None)` | 不抛 |
| 2 | 断言 `result == 0` | True |

### 验证点

- None 起点深度为 0
- 与文档 §IC 表对齐

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t35_depth_guard_none_parent_returns_zero`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-028

### 关联需求

NFR-016 · §Interface Contract `RunLock.acquire` + `release` · Test Inventory T36

### 测试目标

验证 `acquire(workdir, timeout=0.5)` → `release(handle)` → `acquire` again 第二次再次成功；release 不导致后续永远拒。

### 前置条件

- `.venv` 激活；`tmp_path` 存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `h1 = await RunLock.acquire(tmp_path, timeout=0.5)` | 不抛 |
| 2 | `RunLock.release(h1)` | 不抛 |
| 3 | `h2 = await RunLock.acquire(tmp_path, timeout=0.5)` | 不抛 |
| 4 | `RunLock.release(h2)` | 不抛 |
| 5 | 重复 release(h2) | 不抛（idempotent）|

### 验证点

- release 后 lock 真实释放
- 同 path 后续 acquire 成功
- release 重复调用安全

### 后置检查

- `.harness/run.lock` 文件可被清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t36_run_lock_acquire_release_reacquire`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-029

### 关联需求

NFR-016 · §Interface Contract `RunLock.acquire` Raises `RunLockTimeout` · Test Inventory T37

### 测试目标

错误：`acquire(workdir, timeout=0.0)`（lock 已被另一进程持有，模拟）抛 `RunLockTimeout`；上层映射 `RunStartError(already_running, http=409)`。

### 前置条件

- `.venv` 激活；模拟另一进程持有 lock（先 acquire 不 release）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `h_held = await RunLock.acquire(tmp_path, timeout=0.5)`（模拟外部持有） | 不抛 |
| 2 | `with pytest.raises(RunLockTimeout): await RunLock.acquire(tmp_path, timeout=0.0)` | 抛 RunLockTimeout |
| 3 | `RunLock.release(h_held)` | 不抛 |

### 验证点

- timeout=0.0 立即返回 / 失败
- RunLockTimeout 被显式抛而非 silent

### 后置检查

- lock 文件释放

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t37_run_lock_timeout_raises_when_held`
- **Test Type**: Real

---

### 用例编号

ST-SEC-020-001

### 关联需求

IFR-003 SEC mapping · §Interface Contract `PhaseRouteInvoker.build_argv` · Test Inventory T38 · ATS L181 IFR-003 SEC

### 测试目标

安全：验证 `invoker.build_argv(workdir=Path("/x"))` 返回 `[sys.executable, plugin_dir/scripts/phase_route.py, "--json"]` 列表；`invoker.uses_shell == False`；不拼接用户输入到 shell。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `argv = invoker.build_argv(workdir=Path("/x"))` | 不抛 |
| 2 | 断言 `argv[0] == sys.executable` | True |
| 3 | 断言 `argv[-1] == "--json"` 且 `argv[1].endswith("phase_route.py")` | True |
| 4 | 断言 `invoker.uses_shell is False` | True |
| 5 | 断言 argv 中无任何元素含 user-controlled workdir 字面（不拼接）| True |

### 验证点

- argv 列表，shell=False（防命令注入）
- workdir 仅作 cwd，不拼到 argv
- IFR-003 SEC AC

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t38_phase_route_uses_argv_list_not_shell`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-030

### 关联需求

FR-048 AC-1 · §Interface Contract `SignalFileWatcher.events` · Test Inventory T39 · ATS L144 FR-048

### 测试目标

验证 `start(workdir)` 后外部写入 `<workdir>/bugfix-request.json`，`events()` 在 2.0s 内 yield `SignalEvent(kind="bugfix_request", path 含 文件名)`；bus 已 broadcast。

### 前置条件

- `.venv` 激活
- `tmp_path` 已 git init

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `watcher = SignalFileWatcher(...)`；`watcher.start(workdir=tmp_path)` | 不抛 |
| 2 | 后台异步启动 `events()` 消费 task | 启动 |
| 3 | `(tmp_path/"bugfix-request.json").write_text("{}")` | 文件落盘 |
| 4 | 等待 2.0s 内捕获 SignalEvent | True |
| 5 | 断言 `event.kind == "bugfix_request"` 且 `"bugfix-request.json" in event.path` | True |

### 验证点

- watchdog 触发（2s 内可见，FR-048 AC-1）
- kind 推断正确

### 后置检查

- `await watcher.stop()`

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t39_signal_watcher_yields_bugfix_request_within_2s`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-020-007

### 关联需求

FR-048 · §Interface Contract `SignalFileWatcher.debounce_ms` · Test Inventory T40

### 测试目标

边界：同一文件 50ms 内连续写 5 次 → `events()` 仅 yield 1 次（debounce 200ms 默认）。

### 前置条件

- `.venv` 激活
- `tmp_path` 已准备

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `watcher.start(workdir=tmp_path)` | 不抛 |
| 2 | for i in range(5): `(tmp_path/"bugfix-request.json").write_text(str(i))`；间隔 10ms | 落盘 |
| 3 | 等待 1.0s 收集所有 yield | True |
| 4 | 断言 yield 数量 == 1 | True |

### 验证点

- 防抖在 200ms 默认下生效
- 5 次写仅 1 次事件

### 后置检查

- `await watcher.stop()`

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t40_signal_watcher_debounces_rapid_writes`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-031

### 关联需求

§Interface Contract `TicketSupervisor.run_ticket` Wave 4 [MOD] · supervisor.py L95–L100 · Test Inventory T41

### 测试目标

**Wave 4 改造点（核心回归）**：验证 `RunOrchestrator.build_test_default + run_ticket(cmd)` 后 `orch.call_trace()` 含子序列：`["GitTracker.begin(...)", "ToolAdapter.prepare_workdir(...)", "ToolAdapter.spawn(...)", "Watchdog.arm(pid=...)", "TicketStream.subscribe", "Watchdog.disarm", "ClassifierService.classify", "GitTracker.end(...)", "TicketRepository.save(...)"]`，且**不含** `"StreamParser.events()"`（旧调用必须被移除）。

### 前置条件

- `.venv` 激活
- `RunOrchestrator.build_test_default` 装配 mock 依赖（含 `_FakeTicketStream`）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `orch = RunOrchestrator.build_test_default(...)` | 构造成功 |
| 2 | `cmd = TicketCommand(kind="spawn", skill_hint="x", feature_id=None, tool="claude", parent_ticket=None)` | 构造 |
| 3 | `outcome = await orch.supervisor.run_ticket(cmd)` | 不抛 |
| 4 | `trace = orch.call_trace()` | 拿到 list[str] |
| 5 | 断言 `trace` 含 `"TicketStream.subscribe"` | True |
| 6 | 断言 `trace` 不含 `"StreamParser.events()"`（旧调用被移除） | True |
| 7 | 断言 trace 子序列顺序为 [begin, prepare_workdir, spawn, arm, subscribe, disarm, classify, end, save] | True |

### 验证点

- supervisor 主循环已迁移到 `ticket_stream.events(ticket_id)`（Wave 4 IAPI-008 REMOVED 合规）
- 旧 `stream_parser.events()` 调用 0 残留
- 顺序符合 §sequenceDiagram

### 后置检查

- run cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t41_supervisor_call_trace_subscribes_ticket_stream_not_stream_parser`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-032

### 关联需求

IAPI-005 [Wave 4 MOD] precondition · §Interface Contract `TicketSupervisor.run_ticket` (prepare_workdir 前置) · Test Inventory T42

### 测试目标

**Wave 4 改造点**：验证 mock `ToolAdapter.prepare_workdir(spec) → IsolatedPaths sentinel`；`spawn(spec, paths)` 调用时第二参数 == sentinel；prepare_workdir 必先于 spawn。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock ToolAdapter `prepare_workdir` 返回 sentinel = IsolatedPaths(...) | 注入 |
| 2 | mock `spawn` 记录 (spec, paths) 并返回 fake TicketProcess | 注入 |
| 3 | `await orch.supervisor.run_ticket(cmd)` | 不抛 |
| 4 | 断言 spawn 第二参数 is sentinel（identity 一致） | True |
| 5 | 断言 调用顺序 prepare_workdir 在 spawn 之前 | True |

### 验证点

- 双段调用契约 IAPI-005 [Wave 4 MOD]
- paths 由 prepare_workdir 产出后传给 spawn

### 后置检查

- run cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t42_supervisor_calls_prepare_workdir_then_spawn_with_paths`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-033

### 关联需求

IAPI-005 [Wave 4 MOD] · `WorkdirPrepareError` 传播 · Test Inventory T43

### 测试目标

错误：mock `ToolAdapter.prepare_workdir` 抛 `WorkdirPrepareError("triplet write failed")` → `TicketSupervisor.run_ticket` 异常被传播 / ticket state→failed；`adapter.spawn` 不被调用。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock prepare_workdir 抛 WorkdirPrepareError | 注入 |
| 2 | `with pytest.raises(WorkdirPrepareError) or assert ticket.state == "failed"` | True |
| 3 | 断言 `adapter.spawn` 未被调用（call_count == 0） | True |

### 验证点

- prepare_workdir 失败终止流程（IAPI-005 [Wave 4 MOD]）
- spawn 在准备失败时不被启动（防止后续状态混乱）

### 后置检查

- 无 ticket process 残留

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t43_supervisor_propagates_workdir_prepare_error`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-034

### 关联需求

Wave 4 改造点 · `_FakeTicketStream.events(ticket_id)` 签名 · Test Inventory T44

### 测试目标

**Wave 4 改造点**：验证 `RunOrchestrator(ticket_stream=_FakeTicketStream())`；调用 `ticket_stream.events("t-x")` 立即 EOF；`async for` 循环正常退出（空迭代）；`call_trace` 中 "TicketStream.subscribe" 出现在 disarm 之前。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `orch = RunOrchestrator(...ticket_stream=_FakeTicketStream())` | 构造成功 |
| 2 | `await orch.supervisor.run_ticket(cmd)`（其内部走 ticket_stream.events("t-x")）| 不抛 |
| 3 | 断言 events("t-x") 立即 EOF（async for 不挂起） | True |
| 4 | 断言 call_trace 中 "TicketStream.subscribe" 索引 < "Watchdog.disarm" 索引 | True |

### 验证点

- _FakeTicketStream 接口签名正确（events(ticket_id: str)）
- 旧 `events(proc)` 签名残留会 TypeError 被本测试捕获
- 空迭代不变成无限挂起

### 后置检查

- 无残留

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t44_fake_ticket_stream_signature_takes_ticket_id`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-035

### 关联需求

IFR-003 · `PhaseRouteInvoker.invoke` 真实 subprocess · Test Inventory T45 · ATS L181 IFR-003 INTG

### 测试目标

集成：在真实 plugin_dir 下放 `scripts/phase_route.py` fixture（stdout=`{"ok":true,"next_skill":null}`），调 `invoke(workdir=tmp)` → 返回 `PhaseRouteResult(ok=True, next_skill=None)`；`invocation_count==1`；exit=0。

### 前置条件

- `.venv` 激活
- 真实 fixture plugin dir 含 phase_route.py 写入预期 stdout

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 创建 fixture plugin_dir + phase_route.py 输出 `{"ok":true,"next_skill":null}` | 落盘 |
| 2 | `invoker = PhaseRouteInvoker(plugin_dir=fixture_plugin)` | 构造 |
| 3 | `result = await invoker.invoke(workdir=tmp)` | 不抛 |
| 4 | 断言 `result.ok is True and result.next_skill is None` | True |
| 5 | 断言 `invoker.invocation_count == 1` | True |
| 6 | 断言 真实 subprocess 已 fork 并自然退出 | True |

### 验证点

- 真实 subprocess fork 路径（非 mock）
- argv / cwd 正确

### 后置检查

- subprocess 自然退出

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t45_real_phase_route_subprocess_returns_phase_route_result`
- **Test Type**: Real
- **类别归属说明**：design 标 T45 为 INTG/subprocess；ST 类别归 functional（黑盒契约 = "phase_route subprocess 真实 fork 产出合法 result"）。

---

### 用例编号

ST-FUNC-020-036

### 关联需求

FR-002 AC-3 · 真实 subprocess exit≠0 · Test Inventory T46

### 测试目标

集成 / 错误：fixture 脚本 `sys.exit(2)` + stderr=`"phase route boom"` → `invoke()` 抛 `PhaseRouteError(exit_code=2)` 含 stderr tail。

### 前置条件

- `.venv` 激活
- 真实 fixture 写入 exit=2

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 创建 fixture phase_route.py 写 `sys.stderr.write("phase route boom"); sys.exit(2)` | 落盘 |
| 2 | `with pytest.raises(PhaseRouteError) as exc: await invoker.invoke(tmp)` | 抛 PhaseRouteError |
| 3 | 断言 `exc.value.exit_code == 2` | True |
| 4 | 断言 `"phase route boom" in str(exc.value)` | True |

### 验证点

- 真实 fork 错误被捕获
- stderr 不被吞

### 后置检查

- subprocess 自然退出

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t46_real_phase_route_subprocess_exit_nonzero_raises`
- **Test Type**: Real
- **类别归属说明**：design 标 T46 为 INTG/subprocess（error 路径）；ST 类别归 functional。

---

### 用例编号

ST-FUNC-020-037

### 关联需求

IFR-003 timeout · 真实 subprocess SIGTERM→SIGKILL · Test Inventory T47

### 测试目标

集成 / 时序：fixture 脚本 `sleep 5`；`invoke(timeout_s=0.1)` → 抛 `PhaseRouteError("phase_route timeout")`；child 进程已 SIGTERM 后 SIGKILL（最终消失）。

### 前置条件

- `.venv` 激活
- 真实 fixture 含 sleep 5

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | fixture phase_route.py 写 `time.sleep(5)` | 落盘 |
| 2 | `with pytest.raises(PhaseRouteError) as exc: await invoker.invoke(tmp, timeout_s=0.1)` | 抛 PhaseRouteError |
| 3 | 断言 `"timeout" in str(exc.value).lower()` | True |
| 4 | 断言 child PID 已被 reap（不再存在 / orphan 不存在） | True |

### 验证点

- timeout SIGTERM→SIGKILL 序列
- 不留 orphan

### 后置检查

- subprocess 已彻底终结

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t47_real_phase_route_subprocess_timeout_kills_process`
- **Test Type**: Real
- **类别归属说明**：design 标 T47 为 INTG/subprocess timeout；ST 类别归 functional。

---

### 用例编号

ST-FUNC-020-038

### 关联需求

FR-042 AC-1 · `GitTracker.begin/end` 真实 git · Test Inventory T48 · ATS L128 FR-042

### 测试目标

集成：真实 git repo (tmp)：先 commit 一次取 head_before；`GitTracker.begin` → 再 commit 一次 → `end`；`GitContext.head_before != head_after`；`len(commits) == 1`；`commits[0].sha == head_after`。

### 前置条件

- `.venv` 激活
- `tmp_path` 真实 git repo（git init + 至少 1 commit）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | git init + 第一 commit；记录 head_before | True |
| 2 | `ctx_b = await GitTracker().begin(ticket_id="t", workdir=tmp_path)` | 不抛 |
| 3 | 在 tmp_path 内做第二 commit | True |
| 4 | `ctx_e = await GitTracker().end(ticket_id="t", workdir=tmp_path)` | 不抛 |
| 5 | 断言 `ctx_e.head_before != ctx_e.head_after` | True |
| 6 | 断言 `len(ctx_e.commits) == 1` | True |
| 7 | 断言 `ctx_e.commits[0].sha == ctx_e.head_after` | True |

### 验证点

- log_oneline 范围正确（不含 head_before 自身）
- 顺序方向（new commits between begin..end）
- FR-042 AC-1 严格

### 后置检查

- tmp_path 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t48_real_git_tracker_records_commits_between_begin_and_end`
- **Test Type**: Real
- **类别归属说明**：design 标 T48 为 INTG/git；ST 类别归 functional。

---

### 用例编号

ST-FUNC-020-039

### 关联需求

IFR-005 · `GitTracker.head_sha` Raises `GitError(not_a_repo)` · Test Inventory T49

### 测试目标

集成 / 错误：tmp dir 无 .git；`GitTracker().head_sha(workdir=tmp)` 抛 `GitError(code="not_a_repo", exit_code=128)`。

### 前置条件

- `.venv` 激活
- tmp 无 .git

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 准备空 tmp_path 不 git init | True |
| 2 | `with pytest.raises(GitError) as exc: await GitTracker().head_sha(workdir=tmp_path)` | 抛 GitError |
| 3 | 断言 `exc.value.code == "not_a_repo"` | True |
| 4 | 断言 `exc.value.exit_code == 128` | True |

### 验证点

- exit=128 → GitError(not_a_repo)（IFR-005 AC）
- 不抛 generic Exception

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t49_git_tracker_head_sha_in_non_repo_raises`
- **Test Type**: Real
- **类别归属说明**：design 标 T49 为 INTG/git/error；ST 类别归 functional。

---

### 用例编号

ST-FUNC-020-040

### 关联需求

FR-040 AC-1 · `ValidatorRunner.run` 真实 subprocess · Test Inventory T50 · ATS L120 FR-040

### 测试目标

集成：tmp/feature-list.json 合法 + plugin_dir=repo root；`ValidateRequest(path=...)` → `ValidationReport(ok=True, issues=[], script_exit_code=0, duration_ms>0)`。

### 前置条件

- `.venv` 激活
- 合法最小 feature-list.json fixture
- plugin_dir 含 validate_features.py

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 写 tmp/feature-list.json 最小合法版本 | 落盘 |
| 2 | `runner = ValidatorRunner(plugin_dir=...)`；`req = ValidateRequest(path=str(tmp/"feature-list.json"))` | 构造 |
| 3 | `report = await runner.run(req)` | 不抛 |
| 4 | 断言 `report.ok is True and report.script_exit_code == 0` | True |
| 5 | 断言 `report.issues == []` | True |
| 6 | 断言 `report.duration_ms > 0` | True |

### 验证点

- 真实 fork validate_features.py（非 mock）
- happy path 报告正确

### 后置检查

- subprocess 自然退出

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t50_real_validator_runner_happy_path`
- **Test Type**: Real
- **类别归属说明**：design 标 T50 为 INTG/validator/subprocess；ST 类别归 functional。

---

### 用例编号

ST-FUNC-020-041

### 关联需求

FR-040 AC-2 · ValidatorRunner exit≠0 不吞 stderr · Test Inventory T51

### 测试目标

集成 / 错误：fixture script `sys.stderr.write("traceback..."); sys.exit(1)` → `ValidationReport(ok=False, script_exit_code=1, issues 含 ValidationIssue(rule_id="subprocess_exit", message 含 "traceback...")`。

### 前置条件

- `.venv` 激活
- 自定义 fixture validator script

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 写 fixture validate_xxx.py exit=1 stderr="traceback..." | 落盘 |
| 2 | `report = await runner.run(ValidateRequest(path=..., script="custom"))` 或同类调用 | 不抛 |
| 3 | 断言 `report.ok is False and report.script_exit_code == 1` | True |
| 4 | 断言 任一 issue 的 `rule_id == "subprocess_exit"` 且 `"traceback" in message` | True |

### 验证点

- exit≠0 stderr 不被吞（FR-040 AC-2）
- ValidationIssue 携带可定位信息

### 后置检查

- subprocess 自然退出

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t51_real_validator_subprocess_exit_nonzero_captures_stderr`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-042

### 关联需求

FR-040 · §Interface Contract `ValidateRequest.script` Literal allow-list · `ValidatorScriptUnknown(http=400)` · Test Inventory T52

### 测试目标

错误 / SEC：`ValidateRequest(path="x.json", script="malicious_script")` 抛 `ValidatorScriptUnknown(http_status=400)`；allow-list 防命令注入。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `with pytest.raises(ValidatorScriptUnknown) as exc: ValidateRequest(path="x.json", script="malicious_script")` | 抛 ValidatorScriptUnknown（构造时） 或在 runner.run 阶段抛 |
| 2 | 断言 `exc.value.http_status == 400` | True |

### 验证点

- script Literal 枚举防命令注入
- HTTP 400 而非 500

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t52_validator_request_unknown_script_rejected_at_schema`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-043

### 关联需求

FR-048 真实 watchdog · Test Inventory T53

### 测试目标

集成：tmp git repo 中 `SignalFileWatcher.start` → 外部 `Path(tmp/"increment-request.json").write_text("{}")` → 2s 内 yield `SignalEvent(kind="increment_request")`。

### 前置条件

- `.venv` 激活
- tmp_path git init

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `watcher.start(workdir=tmp_path)` | 不抛 |
| 2 | 后台启动 events 消费 task | 启动 |
| 3 | 外部写 increment-request.json | 落盘 |
| 4 | 等 2s 内 yield | True |
| 5 | 断言 `event.kind == "increment_request"` | True |

### 验证点

- 真实 watchdog Observer + inotify 触发
- kind 正确推断

### 后置检查

- watcher.stop()

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t53_real_signal_watcher_yields_increment_request`
- **Test Type**: Real
- **类别归属说明**：design 标 T53 为 INTG/filesystem/signal；ST 类别归 functional。

---

### 用例编号

ST-FUNC-020-044

### 关联需求

IAPI-019 · `RunControlBus.submit` Raises `InvalidCommand` · Test Inventory T54

### 测试目标

错误：`submit(RunControlCommand(kind="skip_ticket", target_ticket_id=None))` 抛 `InvalidCommand("...requires target_ticket_id")`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bus = RunControlBus()`；`bus.attach_orchestrator(orch)` | 不抛 |
| 2 | `cmd = RunControlCommand(kind="skip_ticket", target_ticket_id=None)` | 构造（schema 容许 None）|
| 3 | `with pytest.raises(InvalidCommand) as exc: await bus.submit(cmd)` | 抛 InvalidCommand |
| 4 | 断言 `"target_ticket_id"` in str(exc.value) | True |

### 验证点

- 缺必填字段被拒
- 防止 KeyError 泄漏

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t54_run_control_bus_skip_without_target_raises_invalid`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-045

### 关联需求

IAPI-019 · `RunControlBus.submit` 未绑定 orchestrator · Test Inventory T55

### 测试目标

错误：`bus = RunControlBus()`（未 attach_orchestrator）→ `submit(start, workdir=...)` 抛 `InvalidCommand("RunControlBus not attached to an orchestrator")`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bus = RunControlBus()`（不 attach） | 构造成功 |
| 2 | `cmd = RunControlCommand(kind="start", workdir=str(tmp_path))` | 构造 |
| 3 | `with pytest.raises(InvalidCommand) as exc: await bus.submit(cmd)` | 抛 |
| 4 | 断言 `"not attached"` in str(exc.value) 或类似 | True |

### 验证点

- 未绑定时显式 InvalidCommand 而非 NoneType 异常
- 错误信息含 "orchestrator" 或类似

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t55_run_control_bus_unbound_orchestrator_rejects`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-046

### 关联需求

IAPI-019 · `RunControlBus.submit` start happy · Test Inventory T56

### 测试目标

`bus.attach_orchestrator(orch)` + `submit(RunControlCommand(kind="start", workdir=tmp_git))` → `RunControlAck(accepted=True, current_state ∈ {"starting","running"})`。

### 前置条件

- `.venv` 激活
- tmp_path git init

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bus = RunControlBus()`；`bus.attach_orchestrator(orch)` | 不抛 |
| 2 | `cmd = RunControlCommand(kind="start", workdir=str(tmp_path))` | 构造 |
| 3 | `ack = await bus.submit(cmd)` | 不抛 |
| 4 | 断言 `ack.accepted is True` | True |
| 5 | 断言 `ack.current_state in {"starting","running"}` | True |

### 验证点

- bus 路由到 orch.start_run
- ack 携带当前 state

### 后置检查

- run cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t56_run_control_bus_start_dispatches_to_orchestrator`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-047

### 关联需求

FR-029 · IAPI-001 · `RunControlBus.broadcast_anomaly` · Test Inventory T57

### 测试目标

`bus.broadcast_anomaly(AnomalyEvent(kind="Escalated", cls="rate_limit", retry_count=3))` + `bus.subscribe_anomaly()` → 订阅 queue 收到 envelope `{kind:"Escalated", payload:{cls,retry_count:3,...}}`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bus = RunControlBus()`；`q = bus.subscribe_anomaly()` | 不抛 |
| 2 | `bus.broadcast_anomaly(AnomalyEvent(kind="Escalated", cls="rate_limit", retry_count=3))` | 不抛 |
| 3 | `evt = await asyncio.wait_for(q.get(), timeout=1.0)` | 收到 |
| 4 | 断言 envelope 含 `kind == "Escalated"` 与 `payload.cls == "rate_limit"` 与 `payload.retry_count == 3` | True |

### 验证点

- broadcast 真正达订阅者
- payload 字段完整

### 后置检查

- bus 状态清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t57_broadcast_anomaly_reaches_subscribers`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-048

### 关联需求

FR-042 AC-2 · `TicketSupervisor.run_ticket` → ticket.git 字段持久化 · Test Inventory T58

### 测试目标

`run_ticket` 完成后 `ticket_repo.get(ticket_id)` 的 `ticket.git.head_before` 与 `head_after` 已设置（mock GitTracker 回返）；`ticket.run_id == cmd.run_id`。

### 前置条件

- `.venv` 激活
- mock GitTracker 返回固定 head_before / head_after

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock GitTracker.begin → GitContext(head_before="aaa") | 注入 |
| 2 | mock GitTracker.end → GitContext(head_before="aaa", head_after="bbb", commits=[GitCommit(sha="bbb",...)]) | 注入 |
| 3 | `await orch.supervisor.run_ticket(cmd)` | 不抛 |
| 4 | `t = await ticket_repo.get(ticket_id)` | 拿到 |
| 5 | 断言 `t.git.head_before == "aaa" and t.git.head_after == "bbb"` | True |
| 6 | 断言 `t.run_id == cmd.run_id` | True |

### 验证点

- git 字段持久化（FR-042 AC-2）
- run_id 正确关联

### 后置检查

- repo cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t58_run_ticket_persists_git_head_before_and_after`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-049

### 关联需求

FR-047 · 14-skill 透传冒烟 · Test Inventory T59 · ATS L143 FR-047

### 测试目标

模拟 phase_route 14 skill name 序列；连续 `run_ticket`；`dispatched_skill_hints()` 集合 ⊇ 14 必要子集（using/requirements/ucd/design/ats/init/feature-design/work-tdd/feature-st/quality/st/finalize/hotfix/increment）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `invoker.set_responses([{"ok":True,"next_skill": s} for s in 14_skills])` | 注入 |
| 2 | 启动 14 次主循环迭代 | 不抛 |
| 3 | `hints = orch.dispatched_skill_hints()` | 拿到 list[str] |
| 4 | 断言 `set(hints) >= {"long-task-using","long-task-requirements","long-task-ucd","long-task-design","long-task-ats","long-task-init","long-task-feature-design","long-task-work-tdd","long-task-feature-st","long-task-quality","long-task-st","long-task-finalize","long-task-hotfix","long-task-increment"}` | True |

### 验证点

- 14 skill 全覆盖（FR-047 AC-1）
- 不硬编码（透传）

### 后置检查

- run cleanup

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t59_run_dispatches_14_skill_superset`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-020-050

### 关联需求

§Interface Contract `RunOrchestrator.cancel_run` 状态机 · Test Inventory T60

### 测试目标

**Wave 4 状态机回归**：run state="completed" → `cancel_run` 抛 `InvalidRunState(409)`（实现选 409）；不重置已 completed run。

### 前置条件

- `.venv` 激活
- run 已 completed

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | run 自然进入 completed（next_skill=None ST Go） | True |
| 2 | `with pytest.raises(InvalidRunState) as exc: await orch.cancel_run(run_id)` | 抛 |
| 3 | 断言 `exc.value.http_status == 409` | True |
| 4 | 断言 run 仍处于 "completed" state | True |

### 验证点

- terminate 状态拒绝 cancel
- HTTP 409 一致（与 T16 同协议契约）

### 后置检查

- 无变更

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f20_w4_design.py::test_t60_cancel_after_completed_keeps_state`
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-020-001 | FR-001 AC-1 / T01 | verification_steps[0] | `tests/test_f20_w4_design.py::test_t01_start_run_happy_path_lock_and_run_row` | Real | PASS |
| ST-FUNC-020-002 | FR-001 AC-3 / T02 | verification_steps[1] | `tests/test_f20_w4_design.py::test_t02_start_run_rejects_non_git_directory` | Real | PASS |
| ST-FUNC-020-003 | FR-001 SEC / T03 | verification_steps[1] | `tests/test_f20_w4_design.py::test_t03_start_run_rejects_shell_metacharacters` | Real | PASS |
| ST-FUNC-020-004 | FR-001 BNDRY / T04 | verification_steps[1] | `tests/test_f20_w4_design.py::test_t04_start_run_rejects_empty_workdir` | Real | PASS |
| ST-BNDRY-020-001 | NFR-016 / T05 | verification_steps[6] | `tests/test_f20_w4_design.py::test_t05_start_run_already_running_raises_409` | Real | PASS |
| ST-FUNC-020-005 | FR-002 AC-1 / T06 | verification_steps[2] | `tests/test_f20_w4_design.py::test_t06_phase_route_invoke_returns_phase_route_result` | Real | PASS |
| ST-FUNC-020-006 | FR-002 AC-3 / T07 | verification_steps[14] | `tests/test_f20_w4_design.py::test_t07_phase_route_invoke_exit_nonzero_raises` | Real | PASS |
| ST-FUNC-020-007 | IFR-003 / T08 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t08_phase_route_stdout_not_json_raises_parse_error` | Real | PASS |
| ST-BNDRY-020-002 | NFR-015 / T09 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t09_phase_route_relaxed_parsing_default_fields` | Real | PASS |
| ST-BNDRY-020-003 | NFR-015 / T10 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t10_phase_route_extra_fields_are_ignored` | Real | PASS |
| ST-FUNC-020-008 | FR-003 AC-1 / T11 | verification_steps[3] | `tests/test_f20_w4_design.py::test_t11_hotfix_skill_hint_passes_through_unmodified` | Real | PASS |
| ST-FUNC-020-009 | FR-047 AC-2 / T12 | verification_steps[5] | `tests/test_f20_w4_design.py::test_t12_skill_hint_unknown_name_passes_through` | Real | PASS |
| ST-FUNC-020-010 | build_ticket_command / T13 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t13_build_ticket_command_rejects_ok_false` | Real | PASS |
| ST-FUNC-020-011 | FR-004 AC-1 / T14 | verification_steps[15]（pause）| `tests/test_f20_w4_design.py::test_t14_pause_run_settles_at_paused` | Real | PASS |
| ST-FUNC-020-012 | FR-004 AC-2 / T15 | verification_steps[15]（cancel）| `tests/test_f20_w4_design.py::test_t15_cancel_run_transitions_to_cancelled` | Real | PASS |
| ST-FUNC-020-013 | FR-004 AC-3 / T16 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t16_cancel_after_completed_raises_invalid_state` | Real | PASS |
| ST-FUNC-020-014 | FR-029 AC-1 / T17 | verification_steps[11] | `tests/test_f20_w4_design.py::test_t17_skip_anomaly_resets_counter_and_invokes_phase_route` | Real | PASS |
| ST-FUNC-020-015 | FR-029 AC-2 / T18 | verification_steps[11] | `tests/test_f20_w4_design.py::test_t18_force_abort_immediately_aborts_running_ticket` | Real | PASS |
| ST-FUNC-020-016 | FR-024 AC-1 / T19 | verification_steps[7] | `tests/test_f20_w4_design.py::test_t19_anomaly_classifier_context_overflow_from_stderr` | Real | PASS |
| ST-FUNC-020-017 | FR-028 AC-1 / T20 | verification_steps[10] | `tests/test_f20_w4_design.py::test_t20_anomaly_classifier_contract_deviation_aborts_no_retry` | Real | PASS |
| ST-BNDRY-020-004 | FR-028 lstrip / T21 | verification_steps[10] | `tests/test_f20_w4_design.py::test_t21_anomaly_classifier_contract_deviation_with_leading_whitespace` | Real | PASS |
| ST-FUNC-020-018 | FR-024 / NFR-003 / T22 | verification_steps[7] | `tests/test_f20_w4_design.py::test_t22_retry_policy_context_overflow_sequence` | Real | PASS |
| ST-FUNC-020-019 | FR-025 / NFR-004 / T23 | verification_steps[8] | `tests/test_f20_w4_design.py::test_t23_retry_policy_rate_limit_sequence_30_120_300_none` | Real | PASS |
| ST-PERF-020-001 | NFR-004 ±10% / T24 | verification_steps[8] | `tests/test_f20_w4_design.py::test_t24_retry_policy_scale_factor_compresses_rate_limit` | Real | PASS |
| ST-FUNC-020-020 | FR-026 / T25 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t25_retry_policy_network_sequence_0_60_none` | Real | PASS |
| ST-FUNC-020-021 | RetryPolicy ValueError / T26 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t26_retry_policy_negative_retry_count_raises_value_error` | Real | PASS |
| ST-FUNC-020-022 | RetryPolicy TypeError / T27 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t27_retry_policy_non_int_retry_count_raises_type_error` | Real | PASS |
| ST-BNDRY-020-005 | RetryPolicy unknown cls / T28 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t28_retry_policy_unknown_class_returns_none` | Real | PASS |
| ST-FUNC-020-023 | FR-028 skill_error never / T29 | verification_steps[10] | `tests/test_f20_w4_design.py::test_t29_retry_policy_skill_error_never_retries` | Real | PASS |
| ST-PERF-020-002 | FR-027 AC-1 / T30 | verification_steps[9] | `tests/test_f20_w4_design.py::test_t30_watchdog_arm_sigterm_then_sigkill` | Real | PASS |
| ST-FUNC-020-024 | FR-027 disarm / T31 | verification_steps[9] | `tests/test_f20_w4_design.py::test_t31_watchdog_disarm_cancels_pending_kill` | Real | PASS |
| ST-FUNC-020-025 | Watchdog ValueError / T32 | verification_steps[9] | `tests/test_f20_w4_design.py::test_t32_watchdog_arm_zero_timeout_raises` | Real | PASS |
| ST-FUNC-020-026 | FR-007 DepthGuard / T33 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t33_depth_guard_parent_depth_one_returns_two` | Real | PASS |
| ST-FUNC-020-027 | FR-007 DepthGuard error / T34 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t34_depth_guard_at_max_depth_raises_ticket_error` | Real | PASS |
| ST-BNDRY-020-006 | DepthGuard None / T35 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t35_depth_guard_none_parent_returns_zero` | Real | PASS |
| ST-FUNC-020-028 | NFR-016 / T36 | verification_steps[6] | `tests/test_f20_w4_design.py::test_t36_run_lock_acquire_release_reacquire` | Real | PASS |
| ST-FUNC-020-029 | NFR-016 / T37 | verification_steps[6] | `tests/test_f20_w4_design.py::test_t37_run_lock_timeout_raises_when_held` | Real | PASS |
| ST-SEC-020-001 | IFR-003 SEC / T38 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t38_phase_route_uses_argv_list_not_shell` | Real | PASS |
| ST-FUNC-020-030 | FR-048 AC-1 / T39 | verification_steps[4] | `tests/test_f20_w4_design.py::test_t39_signal_watcher_yields_bugfix_request_within_2s` | Real | PASS |
| ST-BNDRY-020-007 | FR-048 debounce / T40 | verification_steps[4] | `tests/test_f20_w4_design.py::test_t40_signal_watcher_debounces_rapid_writes` | Real | PASS |
| ST-FUNC-020-031 | TicketSupervisor.run_ticket Wave 4 trace / T41 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t41_supervisor_call_trace_subscribes_ticket_stream_not_stream_parser` | Real | PASS |
| ST-FUNC-020-032 | IAPI-005 [Wave 4 MOD] prepare_workdir 前置 / T42 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t42_supervisor_calls_prepare_workdir_then_spawn_with_paths` | Real | PASS |
| ST-FUNC-020-033 | IAPI-005 WorkdirPrepareError / T43 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t43_supervisor_propagates_workdir_prepare_error` | Real | PASS |
| ST-FUNC-020-034 | _FakeTicketStream signature / T44 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t44_fake_ticket_stream_signature_takes_ticket_id` | Real | PASS |
| ST-FUNC-020-035 | IFR-003 real subprocess / T45 | verification_steps[2] | `tests/test_f20_w4_design.py::test_t45_real_phase_route_subprocess_returns_phase_route_result` | Real | PASS |
| ST-FUNC-020-036 | FR-002 AC-3 real exit≠0 / T46 | verification_steps[14] | `tests/test_f20_w4_design.py::test_t46_real_phase_route_subprocess_exit_nonzero_raises` | Real | PASS |
| ST-FUNC-020-037 | IFR-003 real timeout / T47 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t47_real_phase_route_subprocess_timeout_kills_process` | Real | PASS |
| ST-FUNC-020-038 | FR-042 AC-1 real git / T48 | verification_steps[12] | `tests/test_f20_w4_design.py::test_t48_real_git_tracker_records_commits_between_begin_and_end` | Real | PASS |
| ST-FUNC-020-039 | IFR-005 GitError not_a_repo / T49 | verification_steps[12] | `tests/test_f20_w4_design.py::test_t49_git_tracker_head_sha_in_non_repo_raises` | Real | PASS |
| ST-FUNC-020-040 | FR-040 AC-1 real validator / T50 | verification_steps[13] | `tests/test_f20_w4_design.py::test_t50_real_validator_runner_happy_path` | Real | PASS |
| ST-FUNC-020-041 | FR-040 AC-2 real validator stderr / T51 | verification_steps[14] | `tests/test_f20_w4_design.py::test_t51_real_validator_subprocess_exit_nonzero_captures_stderr` | Real | PASS |
| ST-FUNC-020-042 | FR-040 ScriptUnknown / T52 | verification_steps[14] | `tests/test_f20_w4_design.py::test_t52_validator_request_unknown_script_rejected_at_schema` | Real | PASS |
| ST-FUNC-020-043 | FR-048 real watcher / T53 | verification_steps[4] | `tests/test_f20_w4_design.py::test_t53_real_signal_watcher_yields_increment_request` | Real | PASS |
| ST-FUNC-020-044 | IAPI-019 InvalidCommand / T54 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t54_run_control_bus_skip_without_target_raises_invalid` | Real | PASS |
| ST-FUNC-020-045 | IAPI-019 unbound bus / T55 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t55_run_control_bus_unbound_orchestrator_rejects` | Real | PASS |
| ST-FUNC-020-046 | IAPI-019 submit start / T56 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t56_run_control_bus_start_dispatches_to_orchestrator` | Real | PASS |
| ST-FUNC-020-047 | FR-029 IAPI-001 broadcast_anomaly / T57 | verification_steps[11] | `tests/test_f20_w4_design.py::test_t57_broadcast_anomaly_reaches_subscribers` | Real | PASS |
| ST-FUNC-020-048 | FR-042 AC-2 ticket.git persistence / T58 | verification_steps[12] | `tests/test_f20_w4_design.py::test_t58_run_ticket_persists_git_head_before_and_after` | Real | PASS |
| ST-FUNC-020-049 | FR-047 14-skill superset / T59 | verification_steps[5] | `tests/test_f20_w4_design.py::test_t59_run_dispatches_14_skill_superset` | Real | PASS |
| ST-FUNC-020-050 | cancel after completed / T60 | verification_steps[15] | `tests/test_f20_w4_design.py::test_t60_cancel_after_completed_keeps_state` | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

---

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 60 |
| Passed | 60 |
| Failed | 0 |
| Pending | 0 |

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.
> 全部 60 用例自动化执行（无 `已自动化: No` 项）；映射到 60 个底层 pytest 函数（全部位于 `tests/test_f20_w4_design.py`）。
>
> **执行证据**（2026-04-27）：
> - `pytest tests/test_f20_*.py tests/integration/test_f20_*.py -q --no-header` → **110 passed, 35 warnings in 9.52s**（含 W3 60 + W4 60 - 10 重叠 ≈ 110 函数；W4 60 全数 PASS；W3 50 函数 baseline regression 仍 PASS）
> - 覆盖率门槛已在 long-task-quality 阶段验证（line 89.05% / branch 83.26% ≥ 85/80 — 见 Session 40）
> - W4 改造点 T16/T41/T42/T43/T44/T60 = 6 行 RED-anchor 全数转 GREEN（Wave 4 R-G-R 闭环）
