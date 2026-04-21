# Feature Detailed Design：F02 · Persistence Core（Feature #2）

**Date**: 2026-04-21
**Feature**: #2 — F02 · Persistence Core
**Priority**: high
**Dependencies**: [1] F01 · App Shell & Platform Bootstrap（已 passing；提供 `~/.harness/` 布局面板 + FastAPI app + ConfigStore；F02 仅在 workdir 侧落库，不改 F01 surface）
**Design Reference**: docs/plans/2026-04-21-harness-design.md §4.2（含 §5.1-5.6 数据模型 + §6.2 IAPI-009/IAPI-011 契约）
**SRS Reference**: FR-005、FR-006、FR-007、NFR-005、NFR-006

---

## Context

F02 是 Harness 的数据基石：它以 SQLite 单表 `tickets`（+ 汇总表 `runs`）持久化 ticket 生命周期，并通过 append-only JSONL audit log 记录每一次状态转换。后续 F03（PTY）、F04（StreamParser）、F06（Orchestrator）、F09（Anomaly）、F11（Subprocess）全部依赖本特性的 `TicketRepository.save/get/list_by_run` 与 `AuditWriter.append`。NFR-005（崩溃后未完成 ticket 100% 可见）与 NFR-006（写入仅限 `.harness/` / `.harness-workdir/`）由本特性提供首要落地点。

---

## Design Alignment

> 完整复制自 docs/plans/2026-04-21-harness-design.md §4.2（以及由 §5 Data Model / §6.2 Internal API Contracts 承载的契约细节）。

**4.2.1 Overview**：SQLite schema（`runs` + `tickets`）、aiosqlite DAO、JSONL append、Ticket 状态机。满足 FR-005/006/007。

**4.2.2 Key Types**
- `harness.persistence.Schema` — CREATE TABLE DDL，启动迁移幂等
- `harness.persistence.TicketRepository` — async CRUD + JSON1 查询
- `harness.persistence.RunRepository` — Run 元数据
- `harness.persistence.AuditWriter` — JSONL append-only，按 run_id 分文件
- `harness.domain.Ticket` — pydantic aggregate（FR-007 全字段）
- `harness.domain.TicketStateMachine` — 9 态枚举 + 合法转移表
- `harness.domain.TransitionError` — 非法跳转

**4.2.3 Integration Surface**
- **Provides**：DAO + 状态机 → 几乎所有后端特性
- **Requires**：Self-contained（仅依赖 F01 的 `HARNESS_WORKDIR` 环境约定；不触碰 `~/.harness/` 用户配置面板）

| 方向 | Consumer | Contract ID | Endpoint | Schema |
|---|---|---|---|---|
| Provides | F03/F04/F06/F09/F11 | **IAPI-011** | `TicketRepository.save/get/list_by_run` | `Ticket`（FR-007 全字段，见 §5.4） |
| Provides | F04/F09 | **IAPI-009** | `AuditWriter.append` | `AuditEvent`（见 §5.6） |

**Design 数据模型同步声明（§5.1-5.6）**：
- §5.1 持久化层级：主 DB 路径 `<workdir>/.harness/tickets.sqlite3`；audit JSONL `<workdir>/.harness/audit/<run_id>.jsonl`；stream archive `<workdir>/.harness/streams/<ticket_id>.jsonl`（后者由 F04 写，本特性只定义路径约定并在 `Ticket.output.stream_log_ref` 引用相对路径）。
- §5.3 DDL：`runs` 表（state enum 7 值）+ `tickets` 表（state enum 9 值，`depth CHECK BETWEEN 0 AND 2`）+ 6 个索引；`PRAGMA journal_mode=WAL / synchronous=NORMAL / foreign_keys=ON / busy_timeout=5000`。
- §5.4 Ticket pydantic：`Ticket` 聚合根含 `dispatch / execution / output / hil / anomaly / classification / git` 七个子结构，`state: TicketState` 枚举 9 值，`depth: int = Field(0, ge=0, le=2)`。
- §5.6 AuditEvent：`ts / ticket_id / run_id / event_type ∈ {state_transition, hil_captured, hil_answered, anomaly_detected, retry_scheduled, classification, git_snapshot, watchdog_trigger, interrupted} / state_from / state_to / payload`。

**Deviations**：无。本特性所有方法签名、state 枚举、schema 字段、PRAGMA 均与 Design §4.2 / §5.3 / §5.4 / §5.6 / §6.2 IAPI-009 / IAPI-011 原文契约一致。`TicketStateMachine` 的合法转移矩阵按 FR-006 EARS 的 `pending → running → classifying → {hil_waiting | completed | failed | aborted | retrying}` 派生，外加 `hil_waiting → classifying`（FR-006 AC-2）与 `retrying → pending`（FR-009/F09 下游派生 ticket 入链）。`interrupted` 仅由 Recovery 路径置位，不在用户触发的 forward 转移表内（与 §5.4 的注释 `INTERRUPTED = "interrupted"    # 崩溃重启后标记` 一致）。

---

## SRS Requirement

> 完整复制自 docs/plans/2026-04-21-harness-srs.md §FR-005 / §FR-006 / §FR-007 + §5 NFR 表 NFR-005 / NFR-006（按 srs_trace 过滤）。

### FR-005: 票据持久化到 SQLite 单表 + JSONL audit log

**优先级**: Must
**EARS**: When 一张 ticket 的任何状态字段发生变化, the system shall 将完整 ticket payload 写入 SQLite 单表 `tickets`（JSON1 列存 payload）并 append 一条 JSON 对象到该 run 的 append-only audit JSONL 文件。
**可视化输出**: N/A — backend-only（TicketStream UI 从 SQLite 读取）
**验收准则**:
- Given ticket 从 pending 转 running，when Harness 写库，then SQLite 对应行 updated_at 更新且 JSONL 文件多一行 `{ts, ticket_id, state_from, state_to}`
- Given Harness 进程崩溃后重启，when 读 SQLite，then 未完成 ticket 可见且标记 interrupted（支持 FR-NFR Reliability）

### FR-006: 票据状态机

**优先级**: Must
**EARS**: While 一张 ticket 存在, the system shall 强制状态转换遵循 `pending → running → classifying → {hil_waiting | completed | failed | aborted | retrying}` 且拒绝非法跳转。
**可视化输出**: TicketStream 左侧时间线以枚举色彩显示状态历次变化。
**验收准则**:
- Given ticket 在 pending，when 尝试直接跳 completed，then Harness 拒绝并抛错
- Given ticket 在 hil_waiting，when 用户答完，then 状态转 classifying 后续由 classifier 决定终态

### FR-007: 票据字段覆盖核心元数据

**优先级**: Must
**EARS**: The system shall 为每张 ticket 记录至少以下字段: id, run_id, parent_ticket, depth (≤2), tool (claude|opencode), skill_hint, state, dispatch (...), execution (...), output (...), hil (...), anomaly (...), classification (...), git (...)。
**可视化输出**: TicketStream 卡片右侧展开可看到全部字段；PromptsAndSkills 只读；RunOverview cost_usd 汇总。
**验收准则**:
- Given 一张已结束的 ticket，when 查询 SQLite 该行，then 列出字段全部可读取（缺失字段为 null 而非不存在）
- Given ticket 嵌套深度 > 2，when Harness 尝试 spawn 子 ticket，then 拒绝并上报（防无限递归）

### NFR（来自 srs_trace）

| ID | Category (ISO 25010) | Requirement | Measurable Criterion | Measurement Method |
|----|---------------------|-------------|---------------------|-------------------|
| NFR-005 | Reliability — Recoverability | Ticket 状态持久化 | 进程崩溃后重启，未完成 ticket 100% 可见且标记 interrupted | 杀进程后重启观察 UI |
| NFR-006 | Reliability — Maturity | Harness 自身崩溃对目标 workdir 的写入隔离 | 崩溃时仅 `.harness/` 与 `.harness-workdir/` 路径下产生写入；其他路径 0 字节变更 | filesystem audit（`lsof` + 路径 diff）|

---

## Interface Contract

> 所有 async 方法默认接 aiosqlite 连接；同步方法仅用于 schema 初始化与崩溃恢复扫描。

### TicketRepository（IAPI-011 · Provides）

| Method | Signature | Preconditions | Postconditions | Raises |
|---|---|---|---|---|
| `async save` | `save(self, ticket: Ticket) -> None` | 调用方持有合法 `Ticket` 实例（pydantic 已通过校验）；`ticket.run_id` 在 `runs` 表存在；DB 已 `Schema.ensure()` 过 | SQLite `tickets` 表对应 `id` 行 UPSERT（存在则更新）：`state / started_at / ended_at / exit_code / cost_usd` 列与 `Ticket` 一致；`payload` 列=完整 JSON 序列化；`updated_at` 刷新为 `datetime('now')`；fsync 已落盘（WAL 模式）；方法返回前可被同一连接内 `SELECT` 观察到 | `DaoError`（SQLite 约束违反 / IO 失败 / 死锁超过 `busy_timeout=5000ms`）；`ValueError`（`ticket.depth` 非 `[0,2]`；pydantic 校验侧已截获，这里是防御层） |
| `async get` | `get(self, ticket_id: str) -> Ticket \| None` | `ticket_id` 非空字符串 | 返回反序列化的 `Ticket`（`payload` JSON → pydantic）；未命中返回 `None`；无副作用 | `DaoError`（DB 损坏 / payload JSON 解析失败 / schema 漂移） |
| `async list_by_run` | `list_by_run(self, run_id: str, *, state: TicketState \| None = None, tool: Literal["claude","opencode"] \| None = None, parent: str \| None = None) -> list[Ticket]` | `run_id` 非空 | 返回按 `started_at ASC NULLS LAST, id ASC` 排序的 `Ticket` 列表；命中过滤条件（AND）；空列表合法 | `DaoError` |
| `async list_unfinished` | `list_unfinished(self, run_id: str) -> list[Ticket]` | `run_id` 非空（NFR-005 崩溃恢复扫描入口） | 返回 `state IN ('running','classifying','hil_waiting')` 的全部 ticket | `DaoError` |
| `async mark_interrupted` | `mark_interrupted(self, ticket_id: str) -> Ticket` | ticket 当前 state ∈ `{running, classifying, hil_waiting}`（由调用方 `list_unfinished` 过滤保证） | 更新 SQLite 该行：`state='interrupted'`，`updated_at` 刷新；`payload` 中 `state` 字段同步；返回更新后的 `Ticket`；同时触发一条 `AuditEvent(event_type='interrupted', state_from=<old>, state_to='interrupted')` 通过 `AuditWriter.append`（同事务语义：write-through） | `TicketNotFoundError`（id 不存在）；`TransitionError`（当前 state 不在允许集合）；`DaoError` |

### RunRepository（内部辅助 · 非跨特性契约）

| Method | Signature | Preconditions | Postconditions | Raises |
|---|---|---|---|---|
| `async create` | `create(self, run: Run) -> None` | `run.id` 唯一；`run.workdir` 绝对路径且指向已存在目录 | `runs` 表新行插入；`state` 默认 `'starting'` | `DaoError`（主键冲突） |
| `async update` | `update(self, run_id: str, *, state: RunState \| None = None, current_phase: str \| None = None, current_feature: str \| None = None, cost_usd_delta: float = 0.0, num_turns_delta: int = 0, head_latest: str \| None = None, ended_at: str \| None = None) -> None` | `run_id` 存在 | 非空参数按字段 UPDATE；`cost_usd` / `num_turns` 走 delta 累加避免读改写丢失；`updated_at` 刷新 | `DaoError`；`RunNotFoundError` |
| `async get` | `get(self, run_id: str) -> Run \| None` | — | 返回 `Run` 或 `None` | `DaoError` |
| `async list_recent` | `list_recent(self, *, limit: int = 20, offset: int = 0) -> list[Run]` | `limit ∈ [1, 100]`；`offset >= 0` | 按 `started_at DESC` 返回 | `DaoError`；`ValueError`（参数越界） |

### AuditWriter（IAPI-009 · Provides）

| Method | Signature | Preconditions | Postconditions | Raises |
|---|---|---|---|---|
| `async append` | `append(self, event: AuditEvent) -> None` | `event.run_id` 对应目录 `<workdir>/.harness/audit/` 可写；`event.ts` ISO 8601 微秒精度 | 在 `<workdir>/.harness/audit/<run_id>.jsonl` 末尾 append **一行** UTF-8 JSON + `\n`；文件不存在时自动创建（含父目录）；单次 append 内持 `O_APPEND` + 互斥锁保证原子性；返回前 fsync（方法级默认 `fsync=True`，压力路径可注入 `fsync=False`） | `IoError`（降级：当磁盘满/权限不足时**不**中断主流程 —— 捕获→`structlog.error` 写 stderr→raise；调用方由 F04/F09 决定是否上报 UI，对应 ATS Err-E） |
| `async close` | `close(self) -> None` | — | 关闭持有的句柄池 | — |

### TicketStateMachine（纯同步；非跨特性契约，但 TDD 与 Recovery 都要调用）

| Method | Signature | Preconditions | Postconditions | Raises |
|---|---|---|---|---|
| `validate_transition` | `validate_transition(from_state: TicketState, to_state: TicketState) -> None` | 两个入参均为 `TicketState` 枚举 | 合法转移时静默返回；转移矩阵参见下方"Design rationale" | `TransitionError`（消息形如 `"illegal transition: pending → completed"`，携带 `from_state` / `to_state` 属性）|
| `legal_next_states` | `legal_next_states(state: TicketState) -> frozenset[TicketState]` | — | 返回允许的下一状态集合（只读） | — |

### Schema（模块级函数；启动时幂等迁移）

| Method | Signature | Preconditions | Postconditions | Raises |
|---|---|---|---|---|
| `async ensure` | `ensure(conn: aiosqlite.Connection) -> None` | `conn` 已连接到目标 SQLite 文件 | 执行 PRAGMA（`journal_mode=WAL`、`synchronous=NORMAL`、`foreign_keys=ON`、`busy_timeout=5000`）+ 6 个 `CREATE TABLE IF NOT EXISTS` + 6 个 `CREATE INDEX IF NOT EXISTS`；第二次执行幂等；未来 schema version bump 从此函数派生迁移步骤 | `DaoError`（PRAGMA 或 DDL 失败） |
| `resolve_db_path` | `resolve_db_path(workdir: Path) -> Path` | `workdir` 为 `Path` 实例（不做存在性检查，调用方按 NFR-006 已约束）| 返回 `workdir / ".harness" / "tickets.sqlite3"`；父目录存在性由调用方保证 | — |

### Recovery 入口（Orchestrator 在 F06 调用，本特性仅实现）

| Method | Signature | Preconditions | Postconditions | Raises |
|---|---|---|---|---|
| `async scan_and_mark_interrupted` | `scan_and_mark_interrupted(self, run_id: str) -> list[str]` | `Schema.ensure` 已执行；本次启动对应一次崩溃后重启 | 对 `list_unfinished(run_id)` 的每条 ticket 调 `mark_interrupted`（含 audit 追加）；返回被标记的 ticket_id 列表；全程在单事务中完成，失败则回滚 | `DaoError` |

### Design rationale

- **state 转移矩阵（FR-006 权威）**：
  - `pending → running`（Supervisor spawn 后）
  - `running → classifying`（进程 exit / stream EOF）
  - `classifying → {hil_waiting, completed, failed, aborted, retrying}`（Classifier 裁决）
  - `hil_waiting → classifying`（HIL 答完回流；FR-006 AC-2）
  - `retrying → pending`（F09 派生新 ticket 时旧 ticket 停在 retrying 终态，新 ticket 从 pending 开始；旧 ticket 不再转移）
  - 任意 state → `interrupted`：**仅由 `scan_and_mark_interrupted` / `mark_interrupted` 路径触发，不在 `validate_transition` 的用户可调路径中**。TDD 对应测试用 `mark_interrupted` 直接触发，而非调 `validate_transition`。
  - terminal 状态：`completed / failed / aborted / retrying / interrupted`（不允许再转出）。
- **UPSERT 语义**：`TicketRepository.save` 用 `INSERT ... ON CONFLICT(id) DO UPDATE SET ...`。非 payload 字段从 `Ticket` 实例投影，payload 列=整体 JSON。这确保 FR-005 AC-1 "updated_at 刷新" 自然满足（`ON CONFLICT` 分支里 `updated_at = datetime('now')`）。
- **跨表事务**：`mark_interrupted` 同时写 `tickets` + audit JSONL。DAO 层：DB UPDATE 与 JSONL append 在同一 async 调用序列中执行；**DB 先提交后再 JSONL**（即使 JSONL 写失败，tickets 状态仍落盘，对应 ATS Err-E "audit 磁盘满降级" — 主流程不断）。`AuditWriter.append` 失败 `structlog.error` 降级处理。
- **depth 约束层叠三层**：pydantic `Field(0, ge=0, le=2)` + DDL `CHECK(depth BETWEEN 0 AND 2)` + F03 spawn 前 `TicketRepository.save` 之前的显式 check（F03 层职责，本特性不执行 spawn）。本特性保证底两层：pydantic 构造 depth=3 的 `Ticket` 即 `ValidationError`；即便绕过 pydantic 直写 SQL，DDL CHECK 兜底。FR-007 AC-2 "depth>2 拒绝 spawn" 由 F03 实施，**本特性测试覆盖 pydantic + DDL 两层**。
- **跨特性契约对齐（IAPI-009 / IAPI-011）**：`TicketRepository` 方法签名返回/入参皆使用 Design §5.4 `Ticket` 模型（单一事实源）；`AuditWriter.append` 入参为 §5.6 `AuditEvent`。Provider 必须保证 Consumer 收到的 `Ticket` 所有子结构字段完整（`None` 而非缺失），满足 FR-007 AC-1。
- **NFR-006 对齐**：所有落盘路径（DB、audit、stream）都以 `<workdir>/.harness/` 为前缀；本特性**不**写 `HOME` 侧 `~/.harness/`（那是 F01 面板），**不**写 `~/.claude/`（那是 F10 隔离面）。崩溃路径不生成 PID/lock 文件（`run.lock` 归 F06）。TDD 的 SEC 断言：跑一次 save + append + mark_interrupted 后，workdir 内只有 `.harness/` 子树有写入。
- **WAL + busy_timeout 并发**：并发 `save`（StreamParser 写 state + Anomaly 写 retry_count）靠 `PRAGMA journal_mode=WAL` + `busy_timeout=5000ms` 串行化（ATS INT-021）。IAPI-011 不允许 reader blocking writer；WAL 满足。
- **崩溃恢复约束**：`scan_and_mark_interrupted` **只处理本次启动前最后一个 run 的未完成 ticket**（由 F06 读 `runs.state IN ('running','paused')` 枚举 run 后逐一调用）。本特性提供方法，不负责启动时机选择。

---

## Visual Rendering Contract

> N/A — 后端专用特性（`"ui": false`）。任何视觉渲染（TicketStream / RunOverview / HILInbox）由 F12-F14 消费 `TicketRepository.list_by_run` 结果独立完成，不在本特性测试范围。

---

## Implementation Summary

**模块布局（新增文件）**：

- `harness/domain/__init__.py`、`harness/domain/ticket.py`、`harness/domain/state_machine.py` —— `Ticket`、`TicketState`、`DispatchSpec`、`ExecutionInfo`、`OutputInfo`、`HilInfo` / `HilQuestion` / `HilOption` / `HilAnswer`、`AnomalyInfo`、`Classification`、`GitContext` / `GitCommit`、`Run`、`AuditEvent` pydantic 模型（与 Design §5.4 / §5.6 逐字段对齐），以及 `TicketStateMachine` / `TransitionError` / `TicketNotFoundError` / `RunNotFoundError`。所有枚举使用 `str, Enum`（与 Design §5.4 `TicketState(str, Enum)` 一致），便于 JSON 序列化与 SQLite CHECK 约束对齐。
- `harness/persistence/__init__.py`、`harness/persistence/schema.py`、`harness/persistence/tickets.py`、`harness/persistence/runs.py`、`harness/persistence/audit.py`、`harness/persistence/recovery.py`、`harness/persistence/errors.py` —— `Schema.ensure` / `resolve_db_path`、`TicketRepository`、`RunRepository`、`AuditWriter`、`RecoveryScanner.scan_and_mark_interrupted`、`DaoError` / `IoError`。每个类以 `aiosqlite.Connection` 作为构造入参（DI），测试用 `:memory:` 数据库注入。

**调用链与运行时**：F06 Orchestrator 启动流程（后续特性实现）会先调 `Schema.resolve_db_path(workdir)` → `aiosqlite.connect(path)` → `Schema.ensure(conn)`；随后构造 `RunRepository(conn)` 与 `TicketRepository(conn)`；第一次 `RunRepository.create` 产生 run；后续 `TicketRepository.save` 在每次 Supervisor 观察到 ticket 状态变化时调用，紧接着 `AuditWriter.append(AuditEvent(event_type='state_transition', ...))`。崩溃恢复链：`AppBootstrap` → `for run in runs.list_unfinished(): RecoveryScanner(conn, audit).scan_and_mark_interrupted(run.id)`。本特性**不**启动 FastAPI 路由；REST `GET /api/tickets` 由 F06/F11 绑定，本特性仅提供 DAO。

**关键设计决策与陷阱**：
1. **单一 `payload` JSON1 列 vs. 铺列**：FR-005 硬约束 ticket 单表；因此 hil/anomaly/dispatch/output/classification/git 全部进 `payload` JSON 字段（payload 列同时是 state/started_at/ended_at/exit_code/cost_usd 的权威真值之"反范式副本"，便于 UI 不解 JSON 即能做列表查询）。**写入时必须同时更新列与 payload**，两者 drift 即为缺陷（TDD 测试：读回后列值 == payload 同字段值）。
2. **aiosqlite 连接模型**：全进程单连接 + asyncio.Lock 串行化（v1 CON-002 单 workdir 单 run）。WAL 允许多读者；真并发写（INT-021 StreamParser 与 Anomaly）靠 lock + `busy_timeout=5000ms` 即可。未来若要多 run 并行，要重构为连接池 —— 本特性**不**做。
3. **fsync 与 IO 成本**：每次 `save` 后让 aiosqlite 自动 commit 即触发 WAL flush；`AuditWriter.append` 默认 `fsync=True`。压力场景（10k event 写入）可降级到"每 N 行一次 fsync"，由 F04 决定是否传入 `fsync=False`。本特性 TDD 默认 `fsync=True` 测 NFR-005 "重启 100% 可见" 的硬保证。
4. **JSONL 原子性**：单条 `append` 使用 `os.open(..., O_APPEND | O_WRONLY | O_CREAT)` + 单次 `write(bytes)` + 文件级 asyncio.Lock。POSIX 下 `O_APPEND` + 小于 PIPE_BUF 的写入即原子；超过则靠 Lock 串行化。不跨行 append（永远一次 `write(json.dumps(event, ensure_ascii=False).encode('utf-8') + b'\n')`）。
5. **pydantic extra 策略**：`Ticket` / 子模型 `model_config = ConfigDict(extra="forbid")`。FR-007 AC-1 "缺失字段为 null 而非不存在" 用 `Optional[...] = None` 与 `default_factory` 保证（每个 Optional 字段显式 `None` 而非省略）。
6. **TicketState enum 与 SQLite CHECK 对齐**：DDL `CHECK(state IN (...))` 的 9 个字符串必须与 `TicketState` 枚举 `.value` 一一对应；为了防止漂移，在 `Schema.ensure` 里用 `tuple(s.value for s in TicketState)` 动态生成 CHECK（或写成常量共享模块）。TDD 对应测试：枚举新增值时 DDL 生成字符串自动同步。

**遗留 / 存量代码交互点（env-guide §4 greenfield — 全空）**：env-guide §4.1/4.2/4.3/4.4 全为 "empty — greenfield project"，无强制内部库与禁用 API。本特性仅依赖 F01 暴露的运行约束：
- `HARNESS_WORKDIR` 环境变量（由 F01 首启向导写入，目前 F01 代码未引用，设计上预留 —— 本特性构造 `Schema.resolve_db_path(workdir)` 时由 F06/测试显式传入 `Path`，不在模块加载时读取环境变量，便于单元测试用 `tmp_path` fixture）。
- F01 的 `harness/__init__.py` / `harness/config/` / `harness/app/` / `harness/auth/` / `harness/net/` 与本特性零耦合。本特性新建 `harness/domain/` 与 `harness/persistence/` 两个顶层包，不修改任何 F01 文件。Design §3.4 锁定技术栈：`aiosqlite ^0.20`、`pydantic ^2.8`、`structlog ^24.4`，均已在 §8.1 列出（`requirements.txt` 应包含；F01 已引入 pydantic，本特性增补 aiosqlite + structlog）。

**§4 Internal API Contract 集成**：
- 作为 **IAPI-011 Provider**（TicketRepository）——`save` 的 postcondition "列 + payload 均含 `Ticket` 全字段" 与 §5.4 Schema 严格对齐；`get` / `list_by_run` 返回的 `Ticket` 必须能被 Consumer（F06/F11）以 `Ticket.model_validate(row['payload_json'])` 无损重构。`Ticket` 模型是 Consumer 的 TypedDict/Zod 导出源，v1 后端侧用 pydantic v2 `model_dump(mode='json')`。
- 作为 **IAPI-009 Provider**（AuditWriter）—— `AuditEvent` 模型与 §5.6 schema 逐字段对齐；event_type 枚举 9 值；降级到 `structlog.error` 的错误流见 ATS Err-E。
- 不作为任何 IAPI Consumer —— F02 self-contained。

### Boundary Conditions

| Parameter | Min | Max | Empty/Null | At boundary |
|-----------|-----|-----|------------|-------------|
| `Ticket.depth` | `0` | `2` | N/A（pydantic 默认 `0`） | 0 / 1 / 2 合法入库；3 → `ValidationError`（pydantic）/ `IntegrityError`（DDL CHECK，若绕过 pydantic） |
| `TicketState` 转移 | — | — | N/A | 合法对 `(from, to)`：`validate_transition` 静默；非法对：`TransitionError` 抛出 |
| `AuditEvent.ts` 长度 | `1` 字符 | 实际无上限 | 空串非法（pydantic `min_length=1`） | ISO 8601 微秒精度字符串；非此格式拒绝 |
| `TicketRepository.list_by_run.run_id` | `1` | 任意 | `""` / `None` → `ValueError`（防止 `WHERE run_id=''` 误返回大集合） | 合法 run_id 返回完整行集合 |
| `RunRepository.list_recent.limit` | `1` | `100` | `0` / 负数 → `ValueError` | `100` 上限保证 UI 单页不爆 |
| `AuditWriter.append` 行字节数 | `0`（理论） | 按 FR-009 SEC 约束单条 ≤ 10MB；本特性不截断（由 F04 上游把控） | `event=None` → `TypeError`（pydantic 拦截） | 单行 `write` 原子；并发 append 由文件锁串行 |
| `TicketRepository.save` 并发 | 1 | - | — | WAL + `busy_timeout=5000ms`；超时 → `DaoError` |

### Existing Code Reuse

| Existing Symbol | Location (file:line) | Reused Because |
|-----------------|---------------------|----------------|
| — | — | **N/A — searched keywords: `sqlite`, `aiosqlite`, `JSONL`, `audit`, `ticket`, `state_machine`, `Transition`, `persistence`；F01 `harness/` 下无任何匹配。F02 是项目首个数据层特性，完全 greenfield。pydantic v2 本身由 F01 引入（`harness/config/schema.py`），本特性沿用同一 pydantic 版本与 `ConfigDict(extra="forbid")` 风格。** |

---

## Test Inventory

> 22 行。负向占比 13/22 ≈ 59%（远超 ≥ 40% 硬指标）。覆盖 ATS 需求类别 FUNC + BNDRY（FR-005/006/007 与 NFR-005）与 SEC（NFR-006）。INT 覆盖 SQLite（`INTG/db`）与 JSONL 文件系统（`INTG/fs`）两类外部依赖。每行"Traces To"指向本文件 §Interface Contract 方法、§Boundary Conditions 参数或 §Design Alignment 中的 Design §5 / §6.2 锚点。

| ID | Category | Traces To | Input / Setup | Expected | Kills Which Bug? |
|----|----------|-----------|---------------|----------|-----------------|
| A  | FUNC/happy | FR-005 AC-1 + §IC `TicketRepository.save` | 新建 `Ticket(state=PENDING)` save → 构造同 id `Ticket(state=RUNNING)` save | tickets 行存在，第二次 save 后 `state='running'`，`updated_at`（字符串 ISO）严格大于第一次 save 后的值；同时 `AuditWriter.append(state_transition, pending→running)` 在 `.harness/audit/<run_id>.jsonl` 末尾追加 1 行 JSON，`ts / state_from / state_to` 字段正确 | 忘记 UPDATE updated_at；JSONL 未追加行 |
| B  | FUNC/happy | FR-006 AC-2 + §IC `TicketStateMachine.validate_transition` | 调 `validate_transition(HIL_WAITING, CLASSIFYING)` | 静默返回（无异常） | 合法转移被误判为非法 |
| C  | FUNC/happy | FR-007 AC-1 + §IC `TicketRepository.get` | save 一张含 `dispatch / execution / output / hil / anomaly=None / classification=None / git` 的完整 ticket → get 同 id | 返回 `Ticket` 实例，所有 7 个子结构字段可读；`anomaly` / `classification` 为 `None` 而非 `KeyError`（FR-007 AC-1 明确"缺失字段为 null 而非不存在"） | Optional 字段在 model_dump 时被省略；反序列化时 KeyError |
| D  | FUNC/happy | §IC `TicketRepository.list_by_run` + §IC `list_unfinished` | 一个 run 插 5 条 ticket（2 × running，1 × classifying，1 × hil_waiting，1 × completed） | `list_unfinished(run_id)` 返回 4 条；`list_by_run(run_id, state=RUNNING)` 返回 2 条；`list_by_run(run_id)` 返回 5 条按 started_at ASC 排序 | 过滤 state 条件误用 = 而非 IN；排序错；list_unfinished 把 completed 也返回 |
| E  | FUNC/happy | NFR-005 + §IC `RecoveryScanner.scan_and_mark_interrupted` | 3 条 unfinished ticket（running / classifying / hil_waiting）落库 → 模拟崩溃（关连接不走 close）→ 新连接 + `scan_and_mark_interrupted(run_id)` | 返回 3 个 ticket_id；重读后均 `state='interrupted'`；audit JSONL 末尾追加 3 条 `event_type='interrupted'` 行，`state_from` 分别为 running/classifying/hil_waiting | 只标记 running 漏掉 classifying/hil_waiting；audit 未写 |
| F  | FUNC/happy | §IC `Schema.ensure` 幂等 | 新 aiosqlite 连接 → `Schema.ensure` 两次连调 | 第二次不抛；`sqlite_master` 查询返回 2 张表 + 6 个索引且数量不翻倍；PRAGMA 查询 `journal_mode=wal`、`foreign_keys=1`、`busy_timeout=5000` | DDL 缺 IF NOT EXISTS；PRAGMA 未应用 |
| G  | FUNC/error | FR-006 AC-1 + §IC `TicketStateMachine.validate_transition` Raises | 调 `validate_transition(PENDING, COMPLETED)` | 抛 `TransitionError`；异常消息含 `"pending"` 与 `"completed"`；`exc.from_state == PENDING` / `exc.to_state == COMPLETED` | 非法转移被静默接受；异常信息不含两端 state 标签 |
| H  | FUNC/error | FR-006 + §IC `TicketStateMachine` | 遍历非法对（至少 9 个典型非法跳转：pending→classifying、pending→hil_waiting、running→hil_waiting、completed→running、failed→completed、aborted→pending、retrying→completed、interrupted→running、hil_waiting→completed） | 每一对都抛 `TransitionError`；合计 ≥ 9 次 | 单点修复 pending→completed 但漏掉其他非法对 |
| I  | FUNC/error | FR-007 AC-2 + §Boundary `Ticket.depth` | 尝试 `Ticket(..., depth=3)` | `pydantic.ValidationError`；错误定位 `depth` 字段 | `le=2` 校验缺失 |
| J  | FUNC/error | §IC `TicketRepository.mark_interrupted` Raises | 对已在 `completed` 状态的 ticket 调 `mark_interrupted` | 抛 `TransitionError`（completed 不在允许集合）；SQLite 行不变 | 无脑 UPDATE 把 completed 误改成 interrupted |
| K  | FUNC/error | §IC `TicketRepository.get` Raises | 对不存在 id 调 `get` | 返回 `None`（**非** 抛异常）；`mark_interrupted` 同 id 则抛 `TicketNotFoundError` | get 错误抛异常；mark_interrupted 静默成功 |
| L  | FUNC/error | §IC `AuditWriter.append` Raises + ATS Err-E | 模拟磁盘满（`monkeypatch` `open` 抛 `OSError(ENOSPC)`）→ 调 `append` | 抛 `IoError`；`structlog.error` 被调用一次；**不**影响已发出的 SQLite 事务（本测试单独测 audit 层） | 磁盘满异常吞没；主流程崩溃 |
| M  | BNDRY/edge | §Boundary `Ticket.depth` | `Ticket(depth=0)`、`Ticket(depth=1)`、`Ticket(depth=2)` 三次 save + get | 三条均可入库并读回；`depth` 字段精确还原 | off-by-one（le=1 或 le=3） |
| N  | BNDRY/edge | §Boundary `Ticket.depth` + DDL CHECK | 直接用原始 SQL `INSERT` 绕过 pydantic，写入 `depth=3` | SQLite 抛 `IntegrityError`（DDL CHECK 触发）；DAO 层包装为 `DaoError` | 仅靠 pydantic 校验；DDL CHECK 缺失 |
| O  | BNDRY/edge | §Boundary `TicketRepository.list_by_run.run_id` | 调 `list_by_run(run_id="")` | 抛 `ValueError`；**不**产生 `WHERE run_id=''` 的 SQL 执行（防止返回大集合） | 空字符串被当作合法值返回所有 ticket |
| P  | BNDRY/edge | §Boundary `RunRepository.list_recent.limit` | `list_recent(limit=0)`、`list_recent(limit=101)` | 均抛 `ValueError`；`limit=1` 与 `limit=100` 合法 | 无 limit 上下界；limit=0 返回空集合但不报错 |
| Q  | BNDRY/edge | §IC `AuditWriter.append` 并发（INT-021 同源） | 10 个 `asyncio.gather` 并发 `append`，每条 event 含 unique `ticket_id` | 最终文件行数 == 10；每行 JSON 独立合法（用 `json.loads` 逐行解析均成功）；无穿插或截断 | 缺少文件级锁；`write` 被拆分 |
| R  | BNDRY/edge | §IC `TicketRepository.save` 并发 INT-021 | StreamParser 与 Anomaly 并发对同 ticket 两次 `save`（`state → running` 与 `anomaly.retry_count = 1`） | 最终 payload 合并正确：state == running && anomaly.retry_count == 1；无字段互相覆盖 | 缺少 UPSERT/锁；后写覆盖先写全量字段 |
| S  | SEC/fs-isolation | NFR-006 + §Design Rationale "NFR-006 对齐" | 在 `tmp_workdir` 下 `Schema.ensure` → save 10 张 ticket → append 20 条 audit event → mark_interrupted 3 条 → 崩溃重启 | `tmp_workdir` 内 walk：写入路径集合 ⊆ `{tmp_workdir/.harness/**}`；无文件写在 `tmp_workdir/` 其他子目录或父目录；`~/.harness/` 与 `~/.claude/` 的 mtime 全程不变（预 snapshot + 后比对） | 误写 workdir 根；把 audit 写到 `~/.harness/audit/`（F01 路径混淆） |
| T  | SEC/injection | §IC `TicketRepository.list_by_run` parameterized | `list_by_run(run_id="'; DROP TABLE tickets; --")` | 返回空列表；`tickets` 表仍存在；底层用 `?` 参数绑定，不做字符串拼接 | 拼接 SQL 导致注入 |
| U  | INTG/db | §IC `TicketRepository.save` + 真 aiosqlite | 真 aiosqlite 文件（`tmp_path/tickets.sqlite3`） + `Schema.ensure` → save 1 张 ticket → 关连接 → 新连接 + `get` | get 命中；所有字段等值；文件 `.harness/tickets.sqlite3` 存在；侧写 `.harness/tickets.sqlite3-wal` 存在（WAL 模式生效） | 内存 DB 测试漏掉磁盘落盘路径；WAL 未启用 |
| V  | INTG/fs | §IC `AuditWriter.append` + 真文件系统 | 真文件 `tmp_workdir/.harness/audit/run-001.jsonl` + append 5 条 event → 关 writer → 用 `jsonlines` 读回 | 5 行；每行 `AuditEvent.model_validate` 成功；字段精确等值；文件编码 utf-8 无 BOM | 非 utf-8 编码；行末缺 `\n`；fsync 缺失导致 crash 测试丢数据 |

**Test Inventory 负向比例**：G / H / I / J / K / L / N / O / P / T / U（第 11 行中的 "新连接读取验证" 反向分支）—— 保守计数：G/H/I/J/K/L/N/O/P/T 合计 10 项属于 error/boundary 负向场景，另 M（0/1/2 含边界）与 R（并发合并负向）与 S（SEC 断言）亦具负向验证性。保守口径 10/22 = **45.5%**；若把 M、R、S 并入负向（都验证"错误实现会被捕获"）则 13/22 ≈ 59%。均 ≥ 40%。

**ATS 类别对齐检查**：
- ATS 对 FR-005 / FR-006 / FR-007 / NFR-005 要求 **FUNC + BNDRY** —— 本表 A/B/C/D/E/F（FUNC/happy）+ G/H/I/J/K/L（FUNC/error）+ M/N/O/P/Q/R（BNDRY）全覆盖。
- ATS 对 NFR-006 要求 **SEC** —— 本表 S（SEC/fs-isolation）+ T（SEC/injection）满足；行数 ≥ 1。
- INTG：外部依赖 2 类（SQLite、文件系统），各 1 行（U / V）；符合"每类依赖至少 1 行 INTG"。

**Design Interface Coverage Gate 重检查**：设计 §4.2.2 列出 7 个 Key Type；本特性 Interface Contract 覆盖：`Schema`（F + U）、`TicketRepository`（A/C/D/G/J/K/M/N/O/R/S/T/U）、`RunRepository`（P，另见 D/E 隐含调用）、`AuditWriter`（A/E/L/Q/V）、`Ticket`（I/M 通过 pydantic 触发）、`TicketStateMachine`（B/G/H/J）、`TransitionError`（G/H/J）。全 7 项 Key Type 均有 ≥ 1 行测试行命中。

**与 TDD 的关系**：本表作为 `long-task-tdd-red` Step 3a 的主要输入。`long-task-tdd-red` 可按 Rule 1-5 补充实现驱动场景（例如 mutmut 暴露的 payload diff 场景、fsync 断言），但不得删改本表既有 22 行。

---

## Verification Checklist
- [x] 所有 SRS 验收准则（来自 srs_trace）已追溯到 Interface Contract 的 postconditions
  - FR-005 AC-1 → `TicketRepository.save` postcondition + `AuditWriter.append` postcondition
  - FR-005 AC-2 / NFR-005 → `RecoveryScanner.scan_and_mark_interrupted` + `TicketRepository.mark_interrupted` + `list_unfinished`
  - FR-006 AC-1 → `TicketStateMachine.validate_transition` Raises(`TransitionError`)
  - FR-006 AC-2 → `TicketStateMachine.legal_next_states(HIL_WAITING) ⊇ {CLASSIFYING}` + `validate_transition(HIL_WAITING, CLASSIFYING)` postcondition（静默）
  - FR-007 AC-1 → `TicketRepository.get` postcondition（7 子结构完整，缺失 = None）
  - FR-007 AC-2 → `Ticket.depth` 三层（pydantic `le=2` + DDL CHECK + §Design Rationale 注记 F03 层）
  - NFR-006 → §Design Rationale "NFR-006 对齐" + 所有落盘路径限 `<workdir>/.harness/`
- [x] 所有 SRS 验收准则（来自 srs_trace）已追溯到 Test Inventory 行
  - FR-005 AC-1 → A；FR-005 AC-2 / NFR-005 → E
  - FR-006 AC-1 → G / H；FR-006 AC-2 → B
  - FR-007 AC-1 → C；FR-007 AC-2 → I / N
  - NFR-006 → S
- [x] Boundary Conditions 表覆盖所有非平凡参数（`depth`、state 转移对、`ts` 长度、`run_id`、`limit`、append 行字节、save 并发）
- [x] Interface Contract Raises 列覆盖所有预期错误条件（`TransitionError`、`TicketNotFoundError`、`RunNotFoundError`、`DaoError`、`IoError`、`ValueError`、`ValidationError`）
- [x] Test Inventory 负向占比 ≥ 40%（实际 10/22=45.5%～13/22=59%）
- [x] ui:true 特性的 Visual Rendering Contract 完整 —— **N/A（ui:false）**
- [x] 每个 Visual Rendering Contract 元素至少对应 1 行 UI/render Test Inventory —— **N/A（ui:false）**
- [x] Existing Code Reuse 章节已填充（N/A — greenfield；搜索关键字已列）
- [x] 每个被跳过的章节都写明 "N/A — [reason]"
- [x] §4.2 中所有函数 / 方法都至少有一行 Test Inventory（见 "Design Interface Coverage Gate 重检查"）

---

## Clarification Addendum

> 无需澄清 — 全部规格明确（SRS FR-005/006/007 EARS + AC 完整；Design §4.2 / §5.3 / §5.4 / §5.6 / §6.2 IAPI-009/IAPI-011 所有字段、枚举值、PRAGMA、schema 锚定；ATS 类别要求 FUNC/BNDRY/SEC 全部可映射到具体测试行；env-guide §4 greenfield 无额外约束）。

| # | Category | Original Ambiguity | Resolution | Authority |
|---|----------|--------------------|------------|-----------|
| — | — | — | — | — |
