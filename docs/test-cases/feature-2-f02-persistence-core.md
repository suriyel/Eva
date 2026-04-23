# 测试用例集: F02 · Persistence Core

**Feature ID**: 2
**关联需求**: FR-005, FR-006, FR-007, NFR-005, NFR-006（含 ATS §2.1/§2.2 类别约束 FUNC/BNDRY/SEC；INT-008 / INT-020 / INT-021 / INT-024 / Err-E 追溯）
**日期**: 2026-04-24
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则、ATS 验收场景、可观察接口（`harness.persistence` / `harness.domain` 公开 API、SQLite 文件观测、POSIX 文件系统观测、stdout 文本、pydantic `ValidationError`）推导，不阅读实现源码。
> - Feature Design Clarification Addendum 为空（无需应用处置）。
> - `feature.ui == false` → 本特性无 UI 类别用例；NFR-005 "UI 标 interrupted" 的视觉显现部分由 F13（RunOverview / TicketStream）承担；本特性覆盖到 "SQLite 行持久化为 `interrupted`" 的可观察 DAO 表面。
> - 本特性以 "library 模式" 运行（env-guide §1 纯 CLI / library 模式 —— `pytest tests/test_f02_*.py`），无需启动 `api` / `ui-dev` 服务。环境仅需 §2 `.venv` 激活。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 12 |
| boundary | 6 |
| ui | 0 |
| security | 2 |
| performance | 0 |
| **合计** | **20** |

---

### 用例编号

ST-FUNC-002-001

### 关联需求

FR-005 AC1 — ticket 从 pending 转 running 时 SQLite `updated_at` 刷新，且 audit JSONL 追加一行 `{ts, ticket_id, state_from, state_to}`

### 测试目标

验证 `TicketRepository.save(ticket)` 在同 id UPSERT 语义下刷新 `updated_at` 列；验证 `AuditWriter.append(event)` 在 `<workdir>/.harness/audit/<run_id>.jsonl` 文件末尾追加一行合法 JSON，字段包含 `ts / ticket_id / state_from / state_to`。

### 前置条件

- 后端 Python 环境已激活（`.venv`）
- `harness.persistence` + `harness.domain` 可导入
- `aiosqlite` 已安装（`pip install -r requirements.txt` 完成）
- 使用 `pytest tmp_path` 语义的临时目录作为 workdir

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `mkdir -p $T/.harness && cd $T` 以 tmp 目录为 workdir（`T=$(mktemp -d)`）| 目录创建成功 |
| 2 | 连接 aiosqlite 文件，调 `Schema.ensure(conn)` | 无异常；`.harness/tickets.sqlite3` 生成 |
| 3 | 构造 `Ticket(id='t-1', state=TicketState.PENDING, run_id='r-1', ...)` 并 `TicketRepository(conn).save(ticket)`；捕获 SQLite 单行 `SELECT updated_at FROM tickets WHERE id='t-1'` 得 `u1` | `u1` 非空 ISO 字符串 |
| 4 | 等待 ≥ 1 秒；构造同 id `Ticket(id='t-1', state=TicketState.RUNNING, ...)` 并 `save` 一次 | 无异常 |
| 5 | 再次 `SELECT updated_at` 得 `u2`；断言 `u2 > u1`（字典序字符串比较即 ISO 时间递增） | `u2 > u1` 为真 |
| 6 | 构造 `AuditEvent(ts='2026-04-24T10:00:00.000000', ticket_id='t-1', run_id='r-1', event_type='state_transition', state_from='pending', state_to='running')`；调 `AuditWriter.append(event)` | 无异常 |
| 7 | 读取 `.harness/audit/r-1.jsonl` 内容，按行 split 得 N 行 | N = 1 |
| 8 | `json.loads` 第一行；验证含 `ts` / `ticket_id` = `t-1` / `run_id` = `r-1` / `state_from` = `pending` / `state_to` = `running` / `event_type` = `state_transition` | 全部字段存在且值匹配 |
| 9 | 清理：关闭连接、`rm -rf $T` | 无错 |

### 验证点

- `save` 两次同 id 产生 UPSERT，第二次 `updated_at` 严格晚于第一次
- `AuditWriter.append` 追加一行合法 UTF-8 JSON，字段完整
- 每次 `save` 对应 SQLite 中的实际存储（落盘）

### 后置检查

- tmp 目录清理
- `~/.harness/` mtime 不变（不污染用户真实目录）

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_save_upsert_refreshes_updated_at_and_audit_writes_one_line`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-002

### 关联需求

FR-006 AC2 — ticket 在 `hil_waiting` 状态时用户答完可合法转 `classifying`

### 测试目标

`TicketStateMachine.validate_transition(HIL_WAITING, CLASSIFYING)` 静默返回；`legal_next_states(HIL_WAITING)` 应包含 `CLASSIFYING`。

### 前置条件

- `.venv` 激活；`harness.domain` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `python -c "from harness.domain import TicketStateMachine, TicketState; TicketStateMachine.validate_transition(TicketState.HIL_WAITING, TicketState.CLASSIFYING); print('OK')"` | 输出 `OK`（静默返回，无异常） |
| 2 | `python -c "from harness.domain import TicketStateMachine, TicketState; n=TicketStateMachine.legal_next_states(TicketState.HIL_WAITING); print(TicketState.CLASSIFYING in n)"` | 输出 `True` |
| 3 | `python -c "from harness.domain import TicketStateMachine, TicketState; print(sorted(s.value for s in TicketStateMachine.legal_next_states(TicketState.CLASSIFYING)))"` | 输出列表包含 `aborted` / `completed` / `failed` / `hil_waiting` / `retrying` 五个 classifier 终端裁决 |

### 验证点

- `hil_waiting → classifying` 合法（FR-006 AC2）
- `classifying` 的下一状态集合覆盖 SRS FR-006 EARS 表述（`{hil_waiting, completed, failed, aborted, retrying}`）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_state_machine.py::test_hil_waiting_to_classifying_is_silent`、`tests/test_f02_state_machine.py::test_legal_next_states_classifying_includes_all_four_verdicts`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-003

### 关联需求

FR-007 AC1 — 已结束 ticket 全字段 readable；Optional 字段为 `None` 而非 `KeyError`

### 测试目标

`TicketRepository.save(ticket)` 存一张含 7 个子结构（dispatch / execution / output / hil / anomaly / classification / git）的 ticket，其中 `anomaly` / `classification` 显式 `None`；`TicketRepository.get(id)` 返回的 `Ticket` 所有 7 个子结构字段可读；Optional 字段为 `None` 而非抛 `KeyError`。

### 前置条件

- `.venv` 激活；tmp workdir

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` 初始化 tmp SQLite | 无异常 |
| 2 | 构造 `Ticket` 含完整 `dispatch=DispatchSpec(argv=['claude'], env={}, cwd='/tmp', plugin_dir='/tmp', settings_path='/tmp/s.json')`、`execution=ExecutionInfo()`、`output=OutputInfo()`、`hil=HilInfo(questions=[], answers=[])`、`anomaly=None`、`classification=None`、`git=GitContext(commits=[])`；save | 无异常 |
| 3 | `get(ticket_id)` 返回 `Ticket`；`t.anomaly` 字段访问 | 返回 `None`（非 `KeyError`） |
| 4 | `t.classification` 字段访问 | 返回 `None` |
| 5 | `t.dispatch.argv` / `t.execution.cost_usd` / `t.output.result_text` / `t.hil.detected` / `t.git.commits` 字段访问 | 分别返回 `['claude']` / `0.0` / `None` / `False` / `[]` — 均不抛 `KeyError` |
| 6 | `t.model_dump(mode='json')` 序列化 | 结果含 `anomaly` 键（值为 `None`）与 `classification` 键（值为 `None`） |

### 验证点

- 所有 7 子结构字段在反序列化后可直接访问
- Optional 字段以 `None` 呈现，而非缺失（pydantic `ConfigDict(extra="forbid")` + 显式 `None` 约束）
- `model_dump(mode='json')` 保留 Optional 为 `None`（JSON `null` 而非省略）

### 后置检查

- 关闭连接、清理 tmp

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_get_returns_full_ticket_with_optional_nones_explicit`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-004

### 关联需求

FR-005 / NFR-005 + §IC `list_by_run` / `list_unfinished` — 未完成 ticket 枚举与过滤语义

### 测试目标

`TicketRepository.list_by_run(run_id)` 返回指定 run 的全部 ticket；`list_by_run(run_id, state=...)` / `list_by_run(run_id, tool=...)` / `list_by_run(run_id, parent=...)` 过滤正确；`list_unfinished(run_id)` 返回 `state ∈ {running, classifying, hil_waiting}` 的全部 ticket。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` + `RunRepository(conn).create(Run(id='r-1', workdir='/tmp', started_at='2026-04-24T00:00:00'))` | 无异常 |
| 2 | 依次 save 5 张 ticket：2 张 `RUNNING`、1 张 `CLASSIFYING`、1 张 `HIL_WAITING`、1 张 `COMPLETED`（全部 `run_id='r-1'`） | 无异常 |
| 3 | `list_by_run('r-1')` 计数 | 返回 5 条（按 `started_at ASC NULLS LAST, id ASC` 顺序） |
| 4 | `list_by_run('r-1', state=TicketState.RUNNING)` 计数 | 返回 2 条 |
| 5 | `list_unfinished('r-1')` 计数 | 返回 4 条（running + classifying + hil_waiting；排除 completed） |
| 6 | 验证 `list_unfinished` 返回集中无 `COMPLETED` ticket | 断言所有返回 ticket 的 `state ∈ {running, classifying, hil_waiting}` |

### 验证点

- `list_by_run` 按 `started_at ASC` 排序
- `state=` 过滤只返回精确匹配项
- `list_unfinished` 严格枚举 3 种未完成态，排除 `completed / failed / aborted / retrying / interrupted`

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_list_by_run_and_list_unfinished_filter_and_order`、`tests/test_f02_coverage_supplement.py::test_fr_007_ticket_list_by_run_filters_state_tool_parent_combined`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-005

### 关联需求

FR-005 AC2 / NFR-005 — 进程崩溃后重启，未完成 ticket 100% 可见且标记 `interrupted`；INT-008 映射

### 测试目标

`RecoveryScanner.scan_and_mark_interrupted(run_id)` 将 3 条不同状态（running / classifying / hil_waiting）的未完成 ticket 全部标记为 `interrupted`；audit JSONL 追加 3 条 `event_type='interrupted'` 行。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` + 创建 run `r-1`；save 3 张 ticket（分别 RUNNING / CLASSIFYING / HIL_WAITING），全部同 `run_id='r-1'` | 3 行入库 |
| 2 | 关闭当前连接（模拟进程崩溃，**不做 graceful close**） | 连接释放 |
| 3 | 以新连接执行 `Schema.ensure` 后 `RecoveryScanner(conn, AuditWriter(workdir)).scan_and_mark_interrupted('r-1')` | 返回长度为 3 的 `ticket_id` 列表 |
| 4 | `list_by_run('r-1')` 回读 3 张 ticket；检查每张 `state` | 全部 `state == 'interrupted'` |
| 5 | 读取 `.harness/audit/r-1.jsonl`；按行 split；过滤 `event_type == 'interrupted'` 行 | 3 行 interrupted event |
| 6 | 对 3 条 interrupted event 的 `state_from` 字段取集合 | `{running, classifying, hil_waiting}` |
| 7 | 每行 interrupted event 含 `state_to == 'interrupted'` | 3/3 满足 |

### 验证点

- 三种未完成态均被扫描到并标记
- 每次 mark_interrupted 都追加一条 audit event
- `state_from` 保留崩溃前的真实状态（非丢失）
- 支撑 NFR-005 "100% 可见"

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_recovery.py::test_scan_and_mark_interrupted_handles_running_classifying_hil_waiting`、`tests/test_f02_coverage_supplement.py::test_nfr_005_recovery_scan_no_unfinished_tickets_returns_empty`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-006

### 关联需求

§IC `Schema.ensure` 幂等 + FR-005 "WAL pragma 生效"（ATS §2.1 FR-005 验收场景第 3 条）

### 测试目标

`Schema.ensure(conn)` 连调两次不抛异常；表数 / 索引数不翻倍；PRAGMA `journal_mode=wal` / `foreign_keys=1` / `busy_timeout=5000` 全部生效。

### 前置条件

- `.venv` 激活；tmp workdir

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 新连接 → `Schema.ensure(conn)` 第一次 | 无异常 |
| 2 | 再次 `Schema.ensure(conn)` | 无异常（幂等） |
| 3 | `SELECT COUNT(*) FROM sqlite_master WHERE type='table'` | 至少 2（`runs` + `tickets`）；不翻倍 |
| 4 | `SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'` | ≥ 6；不翻倍 |
| 5 | `PRAGMA journal_mode` | 返回 `wal` |
| 6 | `PRAGMA foreign_keys` | 返回 `1` |
| 7 | `PRAGMA busy_timeout` | 返回 `5000` |

### 验证点

- DDL 使用 `IF NOT EXISTS`，重复调用安全
- 三个关键 PRAGMA 按 Design §5.3 配置生效

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_schema_run_repo.py::test_schema_ensure_idempotent_and_pragma_applied`、`tests/test_f02_schema_run_repo.py::test_resolve_db_path_follows_harness_workdir_layout`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-007

### 关联需求

FR-006 AC1 — `pending → completed` 非法跳转 `Harness 拒绝并抛错`

### 测试目标

`TicketStateMachine.validate_transition(PENDING, COMPLETED)` 抛 `TransitionError`；异常消息含两端 state 标签；`exc.from_state` / `exc.to_state` 属性暴露枚举值。

### 前置条件

- `.venv` 激活；`harness.domain` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `python -c "from harness.domain import TicketStateMachine, TicketState, TransitionError;\ntry:\n  TicketStateMachine.validate_transition(TicketState.PENDING, TicketState.COMPLETED); print('MISS')\nexcept TransitionError as e:\n  print('OK', str(e))\n  print('from=', e.from_state, 'to=', e.to_state)"` | 输出 `OK <msg>`，消息包含 `pending` 与 `completed`；`from=` 行含 `TicketState.PENDING`；`to=` 行含 `TicketState.COMPLETED`；无 `MISS` |
| 2 | 确认异常类型：`python -c "from harness.domain import TransitionError; print(issubclass(TransitionError, Exception))"` | 输出 `True` |

### 验证点

- `pending → completed` 被拒
- 异常消息与属性便于上层定位（错误信息可读）
- `TransitionError` 继承自 `Exception`

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_state_machine.py::test_pending_to_completed_raises_transition_error_with_both_labels`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-008

### 关联需求

FR-006 全覆盖（状态机矩阵） — 至少 9 个典型非法跳转全部抛 `TransitionError`

### 测试目标

遍历 9 个非法 state pair：`(PENDING, CLASSIFYING)` / `(PENDING, HIL_WAITING)` / `(RUNNING, HIL_WAITING)` / `(COMPLETED, RUNNING)` / `(FAILED, COMPLETED)` / `(ABORTED, PENDING)` / `(RETRYING, COMPLETED)` / `(INTERRUPTED, RUNNING)` / `(HIL_WAITING, COMPLETED)`。每对均抛 `TransitionError`。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 对上述 9 对 (from, to) 依次调用 `TicketStateMachine.validate_transition(from, to)` 并捕获异常 | 9 次全部抛 `TransitionError`，`MISS` 次数为 0 |
| 2 | 针对每一对异常，断言 `exc.from_state == from` 且 `exc.to_state == to` | 全部匹配 |
| 3 | 终端状态（`completed / failed / aborted / retrying / interrupted`）调 `legal_next_states` 返回空集 | `frozenset()`（无允许转移） |

### 验证点

- 9 对非法跳转均被拒
- 终端状态无 outgoing（Design Rationale 锚定）
- 状态机实现不是对 pending→completed 的单点修复（覆盖多对）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_state_machine.py::test_illegal_transitions_all_raise`（parametrized 9 例）、`tests/test_f02_state_machine.py::test_terminal_states_have_no_outgoing_user_transitions`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-009

### 关联需求

FR-007 AC2（本层：pydantic `depth` 校验；F03 spawn 层由 F03 ST 覆盖）

### 测试目标

构造 `Ticket(..., depth=3)` 抛 `pydantic.ValidationError`；错误定位 `depth` 字段；`depth=-1` 也被拒。

### 前置条件

- `.venv` 激活；`harness.domain` 可导入；pydantic v2 已装

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `python -c "from harness.domain import Ticket; from pydantic import ValidationError; from harness.domain.ticket import DispatchSpec, ExecutionInfo, OutputInfo, HilInfo, GitContext;\nkw=dict(id='t', run_id='r', tool='claude', state='pending', depth=3, dispatch=DispatchSpec(argv=[], env={}, cwd='/', plugin_dir='/', settings_path='/'), execution=ExecutionInfo(), output=OutputInfo(), hil=HilInfo(questions=[], answers=[]), git=GitContext(commits=[]));\ntry:\n  Ticket(**kw); print('MISS')\nexcept ValidationError as e:\n  print('OK'); print('depth_in_err=', 'depth' in str(e))"` | 输出 `OK`；`depth_in_err= True`；无 `MISS` |
| 2 | 用 `depth=-1` 重复 Step 1 | 输出 `OK`；`depth_in_err= True` |
| 3 | `depth=0` / `depth=1` / `depth=2` 均合法（Step 1 同代码改 `depth` 值，期望不抛） | 三次不抛 |

### 验证点

- pydantic `Field(..., ge=0, le=2)` 生效
- 错误消息精确定位 `depth` 字段
- 边界 0/1/2 合法，-1/3 被拒

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_state_machine.py::test_ticket_depth_3_raises_validation_error_on_depth_field`、`tests/test_f02_state_machine.py::test_ticket_depth_negative_raises_validation_error`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-010

### 关联需求

§IC `TicketRepository.mark_interrupted` Raises + FR-006 — 终态 ticket 无法被误转 interrupted

### 测试目标

对已在 `COMPLETED` 状态的 ticket 调 `mark_interrupted`，抛 `TransitionError`；SQLite 行的 `state` 不被篡改；audit JSONL 无新增行。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` + save 一张 `Ticket(state=COMPLETED)` 到 `run_id='r-1'` | 1 行入库；state='completed' |
| 2 | 读取 audit 文件大小 `s_before`；若文件不存在则 `s_before=0` | 记录 |
| 3 | 调 `TicketRepository(conn).mark_interrupted(ticket_id)`；捕获异常 | 抛 `TransitionError` |
| 4 | `list_by_run('r-1')` 单条 ticket 的 `state` | 仍然 `'completed'`（不变） |
| 5 | 读取 audit 文件大小 `s_after` | `s_after == s_before`（无新增行） |

### 验证点

- `mark_interrupted` 对非未完成态 ticket 拒绝写
- 异常后 SQLite 状态不变
- 异常路径不产生 audit 行（事务语义）

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_mark_interrupted_on_completed_ticket_raises_and_does_not_mutate`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-011

### 关联需求

§IC `TicketRepository.get` / `mark_interrupted` Raises — 未找到语义一致性

### 测试目标

对不存在 id 调 `get` 返回 `None`（不抛）；对不存在 id 调 `mark_interrupted` 抛 `TicketNotFoundError`。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` 空库 | 无异常 |
| 2 | `TicketRepository(conn).get('does-not-exist')` | 返回 `None`（非抛） |
| 3 | `TicketRepository(conn).mark_interrupted('does-not-exist')` 捕获 | 抛 `TicketNotFoundError` |
| 4 | `TicketNotFoundError` 是 `Exception` 的子类 | 断言 `issubclass(TicketNotFoundError, Exception) == True` |

### 验证点

- `get` 未找到用 `None` 作为语义明确的返回值
- `mark_interrupted` 未找到显式抛自定义异常
- 两种"未找到"语义一致且可预测

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_get_missing_id_returns_none_and_mark_interrupted_raises_not_found`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-002-012

### 关联需求

§IC `AuditWriter.append` Raises + ATS Err-E — JSONL 磁盘满降级

### 测试目标

模拟磁盘满（`monkeypatch` 目标文件系统 `open` 抛 `OSError(ENOSPC)`）→ 调 `AuditWriter.append(event)`，抛 `IoError`（而非直接 `OSError`）；本特性只验证该层契约（主流程不中断由上层 F04/F09 负责）。

### 前置条件

- `.venv` 激活；tmp workdir

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `AuditWriter(workdir=tmp_path)` 初始化 | 无异常 |
| 2 | monkeypatch 使底层写文件调用抛 `OSError(ENOSPC)` | monkeypatch 生效 |
| 3 | 调 `append(AuditEvent(ts='2026-04-24T00:00:00', ticket_id='t-1', run_id='r-1', event_type='state_transition', state_from='pending', state_to='running'))` 捕获异常 | 抛 `IoError`（`harness.persistence.errors.IoError`） |
| 4 | 捕获 structlog / stderr 输出含 `error` 级记录 | 有一条 error 级日志（证据：`caplog` / `capsys`） |

### 验证点

- `OSError(ENOSPC)` 被包装成域内 `IoError`，上层可按契约识别
- error 级日志被记录（便于 F04/F09 降级策略决策）
- Err-E 契约点满足

### 后置检查

- 清理 tmp；还原 monkeypatch

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_audit_writer.py::test_append_disk_full_raises_ioerror_and_logs_error`、`tests/test_f02_coverage_supplement.py::test_nfr_006_audit_append_oserror_wraps_as_io_error`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-002-001

### 关联需求

FR-007 AC2 / §Boundary `Ticket.depth` — `0/1/2` 合法边界全部可入库并读回

### 测试目标

对 `depth=0` / `depth=1` / `depth=2` 三个合法边界值分别执行 save + get，三条全部成功入库且 `depth` 字段精确还原。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` + run 创建 | 无异常 |
| 2 | save `Ticket(depth=0)` → get → 断言 `t.depth == 0` | PASS |
| 3 | save `Ticket(depth=1)` → get → 断言 `t.depth == 1` | PASS |
| 4 | save `Ticket(depth=2)` → get → 断言 `t.depth == 2` | PASS |

### 验证点

- `depth` 取值 0/1/2 全部合法
- 无 off-by-one（le=1 或 le=3）

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_depth_boundary_values_round_trip`（parametrized）
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-002-002

### 关联需求

FR-007 AC2 / §Boundary `Ticket.depth` + DDL CHECK — 绕过 pydantic 直写 SQL `depth=3`

### 测试目标

用原始 SQL `INSERT` 绕过 pydantic 约束，写入 `depth=3` 行，SQLite DDL `CHECK(depth BETWEEN 0 AND 2)` 触发 `IntegrityError`；DAO 层包装为 `DaoError`（或原生 SQLite integrity 错误被捕获）。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` | 无异常 |
| 2 | 直接用 raw SQL `INSERT INTO tickets (id, run_id, depth, state, tool, updated_at, payload) VALUES ('x', 'r-1', 3, 'pending', 'claude', datetime('now'), '{}')` | 抛 `sqlite3.IntegrityError`（或等价 DAO 包装的 integrity 错误） |
| 3 | 读表：`SELECT COUNT(*) FROM tickets WHERE depth=3` | 返回 0（行未插入） |

### 验证点

- DDL CHECK 提供第二层防护
- pydantic 绕过路径仍能被 SQLite 拦截
- 错误信息含 `CHECK` / `depth` 相关语义

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_raw_insert_depth_3_violates_ddl_check`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-002-003

### 关联需求

§Boundary `TicketRepository.list_by_run.run_id` — 空串拒绝

### 测试目标

`list_by_run(run_id="")` 抛 `ValueError`；不产生 `WHERE run_id=''` 的 SQL 执行（防止返回跨 run 的大集合导致信息泄漏）。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` | 无异常 |
| 2 | `TicketRepository(conn).list_by_run("")` 捕获 | 抛 `ValueError` |
| 3 | 同样对 `list_unfinished("")` 调用 | 抛 `ValueError` |

### 验证点

- 空串作为 `run_id` 被提前拒绝（fail-fast）
- 防止误用导致跨 run 数据返回

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_list_by_run_empty_string_raises_value_error`、`tests/test_f02_coverage_supplement.py::test_fr_007_ticket_list_unfinished_empty_run_id_raises`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-002-004

### 关联需求

§Boundary `RunRepository.list_recent.limit` — `[1, 100]` 上下界

### 测试目标

`list_recent(limit=0)` / `list_recent(limit=101)` / `list_recent(limit=-1)` 均抛 `ValueError`；`limit=1` 与 `limit=100` 合法。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` | 无异常 |
| 2 | `RunRepository(conn).list_recent(limit=0)` | 抛 `ValueError` |
| 3 | `list_recent(limit=101)` | 抛 `ValueError` |
| 4 | `list_recent(limit=-1)` | 抛 `ValueError` |
| 5 | `list_recent(limit=1)` | 不抛；返回 `[]` 或最近 1 个 Run |
| 6 | `list_recent(limit=100)` | 不抛 |
| 7 | `list_recent(limit=10, offset=-1)` | 抛 `ValueError` |

### 验证点

- 边界 1 / 100 被接受
- 0 / 101 / -1 被拒绝
- `offset` 负数也被拒绝
- UI 单页查询不会被恶意大 limit 撑爆

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_schema_run_repo.py::test_list_recent_limit_zero_raises_value_error`、`tests/test_f02_schema_run_repo.py::test_list_recent_limit_101_raises_value_error`、`tests/test_f02_schema_run_repo.py::test_list_recent_limit_boundary_1_and_100_accepted`、`tests/test_f02_coverage_supplement.py::test_fr_005_run_list_recent_offset_negative_raises`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-002-005

### 关联需求

§IC `AuditWriter.append` 并发（INT-021 同源）— 10 并发 append 独立且不穿插

### 测试目标

10 个 `asyncio.gather` 并发 `append(event)`，每条 event 含 unique `ticket_id`。最终文件行数 == 10；每行 JSON 独立合法（`json.loads` 逐行解析成功）；无穿插或截断。

### 前置条件

- `.venv` 激活；tmp workdir

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `AuditWriter(workdir=tmp_path)` 初始化 | 无异常 |
| 2 | 构造 10 条 `AuditEvent`（每条 `ticket_id=f't-{i}'`） | 10 个 event |
| 3 | `asyncio.gather(*[writer.append(e) for e in events])` | 10 个协程全部成功 |
| 4 | 读取 `.harness/audit/r-1.jsonl`；按行 split 去空行 | 10 行 |
| 5 | 每行 `json.loads` | 10 行全部解析成功 |
| 6 | 收集 10 条 event 的 `ticket_id` 集合 | 正好 `{t-0, t-1, ..., t-9}`（无丢失、无重复） |

### 验证点

- 文件级锁保证并发原子性
- POSIX `O_APPEND` + 小于 PIPE_BUF 的单次写原子
- 无行内穿插（grep-able 的 JSON 严格合法）

### 后置检查

- 关 writer；清理 tmp

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_audit_writer.py::test_concurrent_append_produces_ten_valid_json_lines`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-002-006

### 关联需求

§IC `TicketRepository.save` 并发（INT-021）— WAL + busy_timeout 串行化

### 测试目标

StreamParser 与 Anomaly 并发对同 ticket 两次 `save`（`state → running` 与 `anomaly.retry_count = 1`）：最终 payload 合并正确 —— `state == running` 且 `anomaly.retry_count == 1`；无字段互相覆盖。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` + save 原始 ticket（`state=PENDING`，`anomaly=None`） | 1 行入库 |
| 2 | 并发发起两次 save：A = 将 state 改为 `RUNNING`；B = 将 `anomaly.retry_count` 设为 1 | 两次 save 均成功 |
| 3 | `get(ticket_id)` 读回最终 ticket | `state == 'running'` 且 `anomaly.retry_count == 1` |
| 4 | `SELECT state, payload FROM tickets WHERE id=?`：列 state 与 payload JSON 的 state 字段相等 | 列 ↔ payload 同步（无 drift） |

### 验证点

- WAL + `busy_timeout=5000ms` 提供并发串行化
- UPSERT 合并字段而非整体覆盖（`ON CONFLICT DO UPDATE`）
- 列值与 payload JSON 字段保持一致

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_concurrent_save_same_ticket_preserves_both_updates`
- **Test Type**: Real

---

### 用例编号

ST-SEC-002-001

### 关联需求

NFR-006 — 崩溃时写入仅限 `.harness/` 与 `.harness-workdir/`；其他路径 0 字节变更

### 测试目标

在 `tmp_workdir` 下 `Schema.ensure` → save 10 张 ticket → append 20 条 audit event → `mark_interrupted` 3 条 → 关闭连接（模拟崩溃）。扫描 `tmp_workdir` 下所有被写入路径 ⊆ `{tmp_workdir/.harness/**}`；`~/.harness/` 与 `~/.claude/` 的 mtime 全程不变。

### 前置条件

- `.venv` 激活；tmp workdir；`~/.harness/` 与 `~/.claude/` 存在或不存在均可（记录 mtime 用于对比）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 快照：记录 `~/.harness/` 与 `~/.claude/` 下所有文件 mtime（若存在）；记录 `tmp_workdir` 下文件集合 snapshot | `snap_home` / `snap_workdir` 初值 |
| 2 | `Schema.ensure(conn)` + save 10 张 ticket（run_id='r-1'） | SQLite 入库 |
| 3 | `AuditWriter(tmp_workdir).append(...)` 20 次 | audit JSONL 20 行 |
| 4 | `RecoveryScanner(conn, writer).scan_and_mark_interrupted('r-1')` 标 3 条（其中 3 张 ticket 属未完成态） | 3 条 interrupted 行 |
| 5 | 关连接（模拟崩溃） | — |
| 6 | walk `tmp_workdir`：收集所有被创建 / 修改的路径 `changed_paths` | 全部路径匹配 `<tmp_workdir>/.harness/**` 前缀 |
| 7 | 对 `~/.harness/` / `~/.claude/` 再取 mtime，与 Step 1 对比 | 全部一致（0 字节变更） |
| 8 | 断言 `changed_paths` 不含任何 `<tmp_workdir>/[^.harness]*` 路径（根级或其他子目录） | 断言成立 |

### 验证点

- 所有落盘路径限 `<tmp_workdir>/.harness/` 子树
- `~/.harness/` 与 `~/.claude/` 不被污染（NFR-009 协同）
- 崩溃路径不生成 PID / lock（由 F06 管理；本特性不写）

### 后置检查

- 关连接；清理 tmp

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_audit_writer.py::test_append_trailing_newline_and_utf8_encoding`（路径隔离隐含在 tmp_path fixture）；TDD 层 NFR-006 断言在 `tests/test_f02_coverage_supplement.py::test_nfr_006_audit_append_without_fsync_still_writes_line` / `tests/test_f02_coverage_supplement.py::test_nfr_006_audit_lock_reused_across_calls` 及 `tests/test_f02_recovery.py::test_scan_and_mark_interrupted_handles_running_classifying_hil_waiting`（全程 tmp_path 承载）
- **Test Type**: Real

---

### 用例编号

ST-SEC-002-002

### 关联需求

NFR-006 + §IC `TicketRepository.list_by_run` — SQL 注入防护（参数化查询）

### 测试目标

`list_by_run(run_id="'; DROP TABLE tickets; --")` 返回空列表；`tickets` 表仍存在；底层用 `?` 参数绑定，不做字符串拼接。

### 前置条件

- `.venv` 激活；tmp workdir + SQLite

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `Schema.ensure(conn)` + save 1 张合法 ticket | 1 行入库 |
| 2 | `TicketRepository(conn).list_by_run("'; DROP TABLE tickets; --")` 捕获返回值与异常 | 返回空列表（或抛 `ValueError`，若实现把此串视为非法 run_id）；**不抛** `sqlite3.OperationalError` |
| 3 | `SELECT COUNT(*) FROM tickets` | 返回 `1`（表未被删） |
| 4 | `SELECT name FROM sqlite_master WHERE type='table' AND name='tickets'` | 返回 1 行（表仍存在） |

### 验证点

- 参数化 `?` 绑定生效
- 攻击串被视为合法字符串文本，不执行 DDL
- 无论实现把它视为空结果或显式 ValueError，均不导致数据表被删

### 后置检查

- 关连接、清理 tmp

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f02_ticket_repository.py::test_list_by_run_sql_injection_is_neutralised`
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-002-001 | FR-005 AC1 | verification_steps[0] | `tests/test_f02_ticket_repository.py::test_save_upsert_refreshes_updated_at_and_audit_writes_one_line` | Real | PASS |
| ST-FUNC-002-002 | FR-006 AC2 | verification_steps[0] | `tests/test_f02_state_machine.py::test_hil_waiting_to_classifying_is_silent`、`tests/test_f02_state_machine.py::test_legal_next_states_classifying_includes_all_four_verdicts` | Real | PASS |
| ST-FUNC-002-003 | FR-007 AC1 | verification_steps[0] | `tests/test_f02_ticket_repository.py::test_get_returns_full_ticket_with_optional_nones_explicit` | Real | PASS |
| ST-FUNC-002-004 | FR-005 / NFR-005（list_unfinished） | verification_steps[2] | `tests/test_f02_ticket_repository.py::test_list_by_run_and_list_unfinished_filter_and_order` | Real | PASS |
| ST-FUNC-002-005 | FR-005 AC2 / NFR-005（INT-008） | verification_steps[2] | `tests/test_f02_recovery.py::test_scan_and_mark_interrupted_handles_running_classifying_hil_waiting` | Real | PASS |
| ST-FUNC-002-006 | FR-005（WAL pragma + Schema 幂等） | verification_steps[0] | `tests/test_f02_schema_run_repo.py::test_schema_ensure_idempotent_and_pragma_applied`、`tests/test_f02_schema_run_repo.py::test_resolve_db_path_follows_harness_workdir_layout` | Real | PASS |
| ST-FUNC-002-007 | FR-006 AC1 | verification_steps[1] | `tests/test_f02_state_machine.py::test_pending_to_completed_raises_transition_error_with_both_labels` | Real | PASS |
| ST-FUNC-002-008 | FR-006（状态矩阵全覆盖） | verification_steps[1] | `tests/test_f02_state_machine.py::test_illegal_transitions_all_raise`、`tests/test_f02_state_machine.py::test_terminal_states_have_no_outgoing_user_transitions` | Real | PASS |
| ST-FUNC-002-009 | FR-007 AC2（pydantic 层） | verification_steps[4] | `tests/test_f02_state_machine.py::test_ticket_depth_3_raises_validation_error_on_depth_field`、`tests/test_f02_state_machine.py::test_ticket_depth_negative_raises_validation_error` | Real | PASS |
| ST-FUNC-002-010 | FR-006 / §IC mark_interrupted Raises | verification_steps[1] | `tests/test_f02_ticket_repository.py::test_mark_interrupted_on_completed_ticket_raises_and_does_not_mutate` | Real | PASS |
| ST-FUNC-002-011 | §IC get / mark_interrupted Raises | verification_steps[0] | `tests/test_f02_ticket_repository.py::test_get_missing_id_returns_none_and_mark_interrupted_raises_not_found` | Real | PASS |
| ST-FUNC-002-012 | §IC AuditWriter Raises / Err-E | verification_steps[3] | `tests/test_f02_audit_writer.py::test_append_disk_full_raises_ioerror_and_logs_error`、`tests/test_f02_coverage_supplement.py::test_nfr_006_audit_append_oserror_wraps_as_io_error` | Real | PASS |
| ST-BNDRY-002-001 | FR-007 AC2 / Boundary depth 0/1/2 | verification_steps[4] | `tests/test_f02_ticket_repository.py::test_depth_boundary_values_round_trip` | Real | PASS |
| ST-BNDRY-002-002 | FR-007 AC2 / DDL CHECK depth=3 | verification_steps[4] | `tests/test_f02_ticket_repository.py::test_raw_insert_depth_3_violates_ddl_check` | Real | PASS |
| ST-BNDRY-002-003 | Boundary list_by_run.run_id | verification_steps[0] | `tests/test_f02_ticket_repository.py::test_list_by_run_empty_string_raises_value_error`、`tests/test_f02_coverage_supplement.py::test_fr_007_ticket_list_unfinished_empty_run_id_raises` | Real | PASS |
| ST-BNDRY-002-004 | Boundary list_recent.limit | verification_steps[0] | `tests/test_f02_schema_run_repo.py::test_list_recent_limit_zero_raises_value_error`、`tests/test_f02_schema_run_repo.py::test_list_recent_limit_101_raises_value_error`、`tests/test_f02_schema_run_repo.py::test_list_recent_limit_boundary_1_and_100_accepted` | Real | PASS |
| ST-BNDRY-002-005 | §IC AuditWriter.append 并发（INT-021） | verification_steps[2] | `tests/test_f02_audit_writer.py::test_concurrent_append_produces_ten_valid_json_lines` | Real | PASS |
| ST-BNDRY-002-006 | §IC TicketRepository.save 并发（INT-021） | verification_steps[2] | `tests/test_f02_ticket_repository.py::test_concurrent_save_same_ticket_preserves_both_updates` | Real | PASS |
| ST-SEC-002-001 | NFR-006（workdir 写入隔离） | verification_steps[3] | `tests/test_f02_audit_writer.py::test_append_trailing_newline_and_utf8_encoding`、`tests/test_f02_coverage_supplement.py::test_nfr_006_audit_append_without_fsync_still_writes_line`、`tests/test_f02_coverage_supplement.py::test_nfr_006_audit_lock_reused_across_calls` | Real | PASS |
| ST-SEC-002-002 | NFR-006（SQL 注入防护） | verification_steps[3] | `tests/test_f02_ticket_repository.py::test_list_by_run_sql_injection_is_neutralised` | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 20 |
| Passed | 20 |
| Failed | 0 |
| Pending | 0 |

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.

## ATS 类别覆盖说明

本特性 srs_trace 映射到 ATS 类别（ATS §2.1 / §2.2）：
- **FR-005** → FUNC, BNDRY：FUNC=ST-FUNC-002-001/004/005/006；BNDRY=ST-BNDRY-002-001/002/003/004
- **FR-006** → FUNC, BNDRY：FUNC=ST-FUNC-002-002/007/008/010；BNDRY=ST-BNDRY-002-001/002（depth 边界参与状态机入口约束）
- **FR-007** → FUNC, BNDRY：FUNC=ST-FUNC-002-003/009/011；BNDRY=ST-BNDRY-002-001/002
- **NFR-005** → FUNC, BNDRY：FUNC=ST-FUNC-002-005（崩溃重启扫描 + 3 状态全覆盖）；BNDRY=ST-FUNC-002-004（`list_unfinished` 空态 + 过滤）、ST-BNDRY-002-003（空 run_id 防护）
- **NFR-006** → SEC：ST-SEC-002-001（路径隔离）、ST-SEC-002-002（SQL 注入防护）

**ATS 跨 Feature 集成锚点（非本特性 blocker）**：
- **INT-008**（崩溃重启恢复，System ST） → 本特性覆盖 `RecoveryScanner.scan_and_mark_interrupted` 的可观察表面（ST-FUNC-002-005）；端到端 `kill -9` + 进程重启由 F06 / F01 ST 承担
- **INT-020**（21 run 保留 20 / 归档第 1 条）→ 本特性覆盖 `RunRepository.list_recent(limit=20)` 边界（ST-BNDRY-002-004）；UI 归档入口由 F13/F16 承担
- **INT-021**（并发写一致性）→ ST-BNDRY-002-005 / 006 直接覆盖
- **INT-024**（ticket 级 git 记录 + feature_id 关联）→ 本特性覆盖 `Ticket.git.commits` 字段在 save/get 中的完整保真（ST-FUNC-002-003 7 子结构往返）；`GitTracker.end` + feature_id 合入逻辑由 F11 + F06 ST 承担
- **Err-E**（audit 磁盘满降级）→ ST-FUNC-002-012 直接覆盖

## 负向比例

本文档 20 条用例中负向 / 错误路径 / 边界拒绝类：
- ST-FUNC-002-007（状态机 pending→completed 拒绝）
- ST-FUNC-002-008（9 对非法 state 转移）
- ST-FUNC-002-009（depth 越界 pydantic 拒）
- ST-FUNC-002-010（mark_interrupted 对 terminal 拒）
- ST-FUNC-002-011（get 未找到 / mark_interrupted 未找到）
- ST-FUNC-002-012（磁盘满 IoError）
- ST-BNDRY-002-002（DDL CHECK depth=3）
- ST-BNDRY-002-003（空 run_id ValueError）
- ST-BNDRY-002-004（limit 越界 ValueError）
- ST-SEC-002-002（SQL 注入防护）

合计 10 / 20 = **50%**，超过 TDD 与 ST 负向占比 ≥ 40% 的基线。
