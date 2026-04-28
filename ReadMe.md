# Harness

> 桌面外部包裹层（external wrapper），用于在单机单用户场景下自动编排
> [longtaskforagent](https://github.com/) 的 14-skill long-task 管线，
> 驱动 Claude Code 与 OpenCode 交互会话，实现从 Requirements 到 ST Go verdict 的闭环自动执行。

**Status**: Pre-release · 12 features，11 passing / 1 failing（详见 `feature-list.json`）
**Track**: Lite（greenfield · desktop single-user · 仅简体中文 UI）
**License**: 暂未发布

---

## 1. 这是什么

开发者使用 `longtaskforagent` 跑 long-task 项目时，需要：

- 手动起多次 `claude` / `opencode` 会话
- 手动判断阶段路由（requirements → ucd → design → ats → init → work → quality → ...）
- 手动处理 `AskUserQuestion` 这类 HIL（Human-in-the-Loop）阻塞问题
- 手动记录 cost / commits / 异常恢复

Harness 把这些都自动化：单 PyWebView 桌面应用，内嵌 FastAPI + React UI；
`asyncio` 主循环驱动 14 skill；pty 穿透保留交互式 HIL 能力；崩溃可恢复；
ticket 持久化到 SQLite + append-only JSONL audit log。

**核心价值**：让开发者只回答设计/需求层问题，不再管会话生命周期 / 路由切换 / 模型切换 / 票据记录。

---

## 2. 关键特性

| 维度 | 内容 |
|---|---|
| Tool Adapters | Claude Code（TUI + Hook Bridge，CLI ≥ **v2.1.119**）+ OpenCode |
| Skill 驱动 | 14 skills 自动编排 + `AskUserQuestion` HIL 捕获回写 |
| 异常恢复 | `context_overflow` / `rate_limit` / `network` / `timeout` / `skill_error` 五类 + 指数退避 |
| 模型覆写 | 三层 per-ticket / per-skill / run-default + `ModelResolver` 优先级链 |
| Classifier | 自带 OpenAI-compatible 后端（GLM / MiniMax / OpenAI / 自定义），rule-based 降级 |
| 8 大 UI | RunOverview / HILInbox / SystemSettings / PromptsAndSkills / TicketStream / DocsAndROI / ProcessFiles / CommitHistory |
| 环境隔离 | Per-run `.harness-workdir/<run-id>/.claude/` + sha256 守恒（NFR-009：`~/.claude/` 零写入） |
| 持久化 | SQLite `tickets` 单表 + append-only JSONL audit log + WAL |
| 凭证存储 | API key 仅入平台 keyring（NFR-008，`.env` 严禁明文） |
| 分发 | PyInstaller 单文件二进制（Linux / macOS / Windows） |
| 网络边界 | FastAPI 仅绑 `127.0.0.1`（NFR-007） |

---

## 3. 技术栈

**后端 · Python ≥ 3.11**
- FastAPI 0.136 · uvicorn[standard] 0.44 · websockets 16 · httpx 0.28
- pydantic 2.13 · aiosqlite 0.20 · structlog 24.4
- pywebview 6.2 · keyring 25.7 · filelock 3.29 · watchdog 6.0
- POSIX pty 用 `ptyprocess` 0.7；Windows 走 `pywinpty`
- pytest 8.4 · pytest-asyncio 0.26 · pytest-cov 5.0 · ruff 0.15 · black 24.10 · mypy 1.20
- pyinstaller 6.19

**前端 · Node ≥ 20**
- React 18.3 · Vite 5.4 · TypeScript 5.5 · TailwindCSS 3.4
- TanStack Query 5.59 · Zustand 5 · React Router 7
- Vitest 2.1 · Playwright 1.48 · Testing Library

依赖清单：
- 后端：`requirements.txt` / `pyproject.toml`
- 前端：`apps/ui/package.json`

---

## 4. 目录结构

```
.
├── apps/ui/                     # React SPA（Vite + Tailwind + shadcn/ui）
├── harness/                     # Python 后端
│   ├── adapter/                 # ToolAdapter（Claude / OpenCode）
│   ├── api/                     # FastAPI routers（runs / hil / hook / git ...）
│   ├── app/                     # 进程入口 · PyWebView shell · first-run wizard
│   ├── auth/                    # KeyringGateway · ClaudeAuthDetector
│   ├── cli_dialog/              # TUI 识别 / 决策 / 执行
│   ├── config/                  # ConfigStore · ModelRulesStore
│   ├── dispatch/                # ModelResolver · ClassifierService
│   ├── domain/                  # Ticket · TicketStateMachine（9-state）
│   ├── env/                     # EnvironmentIsolator · WorkdirScopeGuard
│   ├── hil/                     # HookEventMapper · TuiKeyEncoder
│   ├── orchestrator/            # RunOrchestrator · TicketSupervisor · phase_route_local
│   ├── persistence/             # SQLite schema · TicketRepository · AuditWriter
│   ├── pty/                     # POSIX / Windows pty backend
│   ├── recovery/                # AnomalyClassifier · RetryPolicy · Watchdog
│   ├── stream/                  # TicketStream broadcaster
│   └── subprocess/              # GitTracker · ValidatorRunner
├── tests/                       # pytest（unit / integration / e2e）
├── scripts/                     # 校验、路由、服务启停、bootstrap
├── docs/
│   ├── plans/                   # SRS / Design / UCD / ATS / Deferred
│   ├── design-bundle/eava2/     # 视觉真相源（JSX prototype）
│   ├── features/<id>/           # Per-feature design.md
│   └── test-cases/feature-<id>/ # IEEE 29119 ST cases
├── examples/                    # 用法示例
├── feature-list.json            # 状态唯一事实源
├── env-guide.md                 # 环境契约（命令唯一事实源）
├── long-task-guide.md           # Worker 工作流导航
├── init.sh / init.ps1           # 幂等环境引导脚本
└── pyproject.toml / requirements.txt
```

---

## 5. 快速开始

### 5.1 前置条件
- Python ≥ 3.11
- Node ≥ 20，npm ≥ 10
- Git ≥ 2.30
- `claude` CLI ≥ **2.1.119** 且已完成 `claude auth login`（凭证由 Harness 继承）
- Linux 桌面环境若无 GNOME Keyring / KDE KWallet：自动降级到 `keyrings.alt`，UI 顶部会出现告警 banner

### 5.2 一键引导

```bash
# Unix / macOS
bash init.sh

# Windows（PowerShell）
.\init.ps1
```

脚本幂等：建 `.venv`、装 pip 依赖、装 `apps/ui/node_modules`、生成
`scripts/svc-*-start.{sh,ps1}` 占位启动器。

### 5.3 配置

```bash
cp .env.example .env
# 按文件内注释填 HARNESS_HOME / HARNESS_WORKDIR
# API key **不写在 .env**，启动后在 UI SystemSettings → Classifier 录入，自动入 keyring
```

### 5.4 开发期启动两条服务

参见 `env-guide.md` §1（命令的唯一事实源）。摘要：

```bash
# Unix / macOS
bash scripts/svc-api-start.sh    > /tmp/svc-api-start.log    2>&1 &
bash scripts/svc-ui-dev-start.sh > /tmp/svc-ui-dev-start.log 2>&1 &

curl -f http://127.0.0.1:8765/api/health   # → {"ok": true}
open  http://127.0.0.1:5173/               # Vite dev server
```

停止：

```bash
kill "$(cat /tmp/svc-api.pid)" "$(cat /tmp/svc-ui-dev.pid)"
# 端口 fallback: lsof -ti :8765 :5173 | xargs -r kill -9
```

> 发布形态是 PyInstaller 单文件桌面应用，**生产无服务进程**；上述两条仅开发期使用。

---

## 6. 测试与质量门槛

完整命令见 `env-guide.md` §3。

```bash
# 后端单测（默认 mock，禁网络）
pytest -q

# 后端覆盖率（line ≥ 90% / branch ≥ 80%，硬性闸门）
pytest --cov=harness --cov-branch --cov-report=term-missing

# 真实测试（需 claude auth login / 真 LLM 凭证）
pytest -q -m "real_cli or real_fs"
pytest -q -m "real_external_llm"     # F19 Classifier smoke

# 静态分析
ruff check . && black --check . && mypy harness

# 前端
( cd apps/ui && npm run test && npm run typecheck && npm run build )
```

**Real-test 分布约定**：80% mock · 15% integration · 5% e2e（ATS §3.1）。
`@pytest.mark.real_cli / real_fs / real_http / real_external_llm` marker 区分。

---

## 7. 文档索引

| 文档 | 用途 |
|---|---|
| `docs/plans/2026-04-21-harness-srs.md` | 软件需求规约（FR / NFR / IFR / CON / ASM / ESI） |
| `docs/plans/2026-04-21-harness-design.md` | 架构与各 feature 集成设计 |
| `docs/plans/2026-04-21-harness-ucd.md` | UI Component Design（Cockpit Dark） |
| `docs/plans/2026-04-21-harness-ats.md` | Acceptance Test Strategy |
| `docs/plans/2026-04-21-harness-deferred.md` | 延期需求 backlog |
| `env-guide.md` | 环境契约 · 命令唯一事实源 |
| `long-task-guide.md` | Worker 会话工作流导航 |
| `task-progress.md` | 历次会话进度日志 |
| `RELEASE_NOTES.md` | 版本变更记录（Keep a Changelog） |
| `CLAUDE.md` / `AGENTS.md` | Long-Task Agent 路由与语言规则 |

---

## 8. 长任务工作流（开发者视角）

Harness 仓库本身就是一个 long-task 项目，路由规则见 `CLAUDE.md`：

**Pre-init**（无 `feature-list.json`）：
`requirements → ucd（含 UI 时） → design → ats → init`

**Post-init**（已有 `feature-list.json`），按根字段 `current` 锁路由：

| `current` 值 | 下一 skill |
|---|---|
| `{feature_id: N, phase: "design"}` | `long-task-work-design` |
| `{feature_id: N, phase: "tdd"}`    | `long-task-work-tdd` |
| `{feature_id: N, phase: "st"}`     | `long-task-work-st` |
| `null` 且任一 feature `failing`     | router pick 下一 dep-ready feature |
| `null` 且全 `passing`               | `long-task-st`（系统级 ST） |

特殊信号：根目录 `bugfix-request.json` / `increment-request.json` 触发
`long-task-hotfix` / `long-task-increment`（最高优先级）。

**纪律**：

- 每张 feature 开工前 `python scripts/check_configs.py feature-list.json --feature <id>` 必过
- TDD 严格 Red → Green → Refactor，不得"先实现后补测"
- Coverage Gate 不过 → 不得进 ST
- `failing → passing` 翻转只能 `long-task-work-st` Persist 步原子完成
- 静态分析失败不得推进；commit 严禁 `--no-verify`
- 写路径仅允许 `.harness/` ∪ `.harness-workdir/`，**禁止**写 `~/.claude/`

完整 13 条铁律见 `long-task-guide.md` §13。

快速看进度：

```bash
python scripts/count_pending.py feature-list.json
# → current=none passing=11 failing=1 (total=12, deprecated=12)
```

---

## 9. 重要约束（NFR 摘要）

| 编号 | 阈值 | 实现保障 |
|---|---|---|
| NFR-001 | UI 响应 p95 < 500ms | WebSocket 直推，不轮询 |
| NFR-002 | Stream 事件 p95 < 2s | 增量解析 + 即推 |
| NFR-003 | `context_overflow` 自动恢复 ≤ 3 次 | `RetryPolicy` 序列 `[0,0,0,None]` |
| NFR-004 | `rate_limit` 指数退避 ≤ 3 次 | `[30s, 120s, 300s, None]` |
| NFR-005 | 进程崩溃后 ticket 100% 可见 + interrupted | 状态转换同步 WAL 写入 |
| NFR-006 | 崩溃仅 `.harness/` ∪ `.harness-workdir/` 有写 | pty 子进程 cwd/env 白名单 |
| NFR-007 | FastAPI 仅绑 `127.0.0.1` | uvicorn host 锁定 + 启动自检 BindGuard |
| NFR-008 | API key 仅存 keyring | config.json 仅存服务引用 |
| NFR-009 | `~/.claude/` 零写入 | Adapter env 隔离 + sha256 mtime snapshot |
| NFR-016 | 单 workdir 单 run 互斥 | filelock `<workdir>/.harness/run.lock` |

---

## 10. 范围外（v1）

`SaaS / 多用户 / CI 触发 / 移动 UI / i18n / Skill 市场 / 全文搜索 /
已取消 run 恢复 / 同 workdir 并发 / Gemini 等其他 CLI` 均明确不做（EXC-001..011）。
延期项见 [deferred backlog](docs/plans/2026-04-21-harness-deferred.md)。

---

## 11. 贡献

本仓库由 Long-Task Agent 流水线驱动（详见 `CLAUDE.md`）。手工提交规范：

- Commit 信息：`feat(F<id>): <title>` / `fix: ...` / `tdd: ...` / `chore: ...`
- 禁用 `--no-verify`、`--no-gpg-sign`
- 推送前过 `validate_features.py` + `check_ats_coverage.py` + `check_st_readiness.py`
- 仅修改 `env-guide.md` §3 / §4 时需要本人在文件头 frontmatter 续签 `approved_by` / `approved_date`

**语言规则**：所有用户面向文档与回复用简体中文；代码标识符、CLI 命令、commit message、
`SRS/FR/NFR/ATS/UCD/ST/TDD/UT/E2E` 等约定缩写保留英文。

---

_Generated 2026-04-28 · 维护：Long-Task Agent Worker pipeline_
