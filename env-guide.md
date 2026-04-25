---
version: 1.1
approved_by: godsuriyel@gmail.com
approved_date: 2026-04-21T09:21:02+08:00
approved_sections: ["§3", "§4"]
---

# env-guide.md —— 环境契约（单一事实源）

> **用户可编辑。** Claude 在以下场景读取本文件：服务启停、构建/测试命令、存量代码库约束。
> 本文件是下游流水线（Worker / TDD / Quality / Feature-ST）的**单一事实源**。任何对 §3 或 §4 的修改必须经人工审批（更新本文件头的 `approved_by` / `approved_date` / `approved_sections`）。
>
> **项目性质**：Harness 是 Greenfield · Desktop Single-User · Python + React（PyWebView 壳）应用；最终产物为 **PyInstaller 单文件二进制**，发布后运行时没有常驻 server process。本文件记录的 **§1 服务** 面向 *开发/测试* 阶段，用于本地调试。

## 目录
- §1 服务生命周期
- §2 环境配置
- §3 构建与执行命令
- §4 存量代码库约束
- §5 测试环境依赖
- §6 人工审批记录

---

## §1 服务生命周期

> Harness 发布形态为 PyInstaller 单文件桌面应用，**无服务端部署**；本节记录的是**开发时**需要的进程。E2E / UI 调试通常同时需要 `api`（FastAPI + uvicorn）与 `ui-dev`（Vite dev server）两条进程。纯后端单元测试不需要启动任何服务，仅需 §2 的环境激活。

### Services 清单

| Service Name | Port | Start Command | Stop Command | Verify URL |
|---|---|---|---|---|
| `api` | `8765`（开发期固定，生产走 ephemeral） | `bash scripts/svc-api-start.sh` | `kill $(cat /tmp/svc-api.pid)` 或 `lsof -ti :8765 \| xargs kill -9` | `http://127.0.0.1:8765/api/health` |
| `ui-dev` | `5173`（Vite 默认） | `bash scripts/svc-ui-dev-start.sh` | `kill $(cat /tmp/svc-ui-dev.pid)` 或 `lsof -ti :5173 \| xargs kill -9` | `http://127.0.0.1:5173/` |

> 两条启动命令 >2 shell 步，已抽成 `scripts/svc-api-start.sh` 与 `scripts/svc-ui-dev-start.sh`（由 `init.sh` / `init.ps1` 生成；首次构建前占位）。

### 启动全部服务（输出捕获）

```bash
# ───── Unix / macOS ─────
# api（FastAPI + uvicorn，仅绑 127.0.0.1 — NFR-007）
bash scripts/svc-api-start.sh > /tmp/svc-api-start.log 2>&1 &
echo $! > /tmp/svc-api.pid
sleep 3
head -30 /tmp/svc-api-start.log
# → 日志里 `Uvicorn running on http://127.0.0.1:8765` 一行确认 PID + port

# ui-dev（Vite）
bash scripts/svc-ui-dev-start.sh > /tmp/svc-ui-dev-start.log 2>&1 &
echo $! > /tmp/svc-ui-dev.pid
sleep 3
head -30 /tmp/svc-ui-dev-start.log
```

```powershell
# ───── Windows ─────
# api
cmd /c "start /b powershell -File scripts\svc-api-start.ps1 > %TEMP%\svc-api-start.log 2>&1"
timeout /t 3 /nobreak >nul
powershell "Get-Content $env:TEMP\svc-api-start.log -TotalCount 30"

# ui-dev
cmd /c "start /b powershell -File scripts\svc-ui-dev-start.ps1 > %TEMP%\svc-ui-dev-start.log 2>&1"
timeout /t 3 /nobreak >nul
powershell "Get-Content $env:TEMP\svc-ui-dev-start.log -TotalCount 30"
```

### 验证服务在运行

```bash
# Unix / macOS
curl -f http://127.0.0.1:8765/api/health
curl -f http://127.0.0.1:5173/
```

```powershell
# Windows
powershell "Invoke-WebRequest -Uri http://127.0.0.1:8765/api/health -UseBasicParsing | Select-Object -ExpandProperty StatusCode"
powershell "Invoke-WebRequest -Uri http://127.0.0.1:5173/           -UseBasicParsing | Select-Object -ExpandProperty StatusCode"
```

### 停止全部服务（PID 优先，端口 fallback）

```bash
# ───── Unix / macOS ─────
kill "$(cat /tmp/svc-api.pid)"    2>/dev/null || true
kill "$(cat /tmp/svc-ui-dev.pid)" 2>/dev/null || true

# 端口 fallback
lsof -ti :8765 | xargs -r kill -9
lsof -ti :5173 | xargs -r kill -9
```

```powershell
# ───── Windows ─────
taskkill /F /PID (Get-Content $env:TEMP\svc-api.pid)
taskkill /F /PID (Get-Content $env:TEMP\svc-ui-dev.pid)

# 端口 fallback
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8765') do taskkill /F /PID %a
for /f "tokens=5" %a in ('netstat -ano ^| findstr :5173') do taskkill /F /PID %a
```

### 验证服务已停止

```bash
# Unix / macOS —— 预期无输出
lsof -i :8765
lsof -i :5173
```

```powershell
# Windows —— 预期无输出
netstat -ano | findstr :8765
netstat -ano | findstr :5173
```

### 重启协议（Restart Protocol，4 步）

1. **Kill** —— 按"停止全部服务"逐条执行
2. **Verify dead** —— 执行"验证服务已停止"；最多轮询 5 秒
3. **Start + capture** —— 执行"启动全部服务（输出捕获）" → `head -30` → 提取 PID/port → 更新 `task-progress.md`
4. **Verify alive** —— 执行"验证服务在运行"；最多轮询 10 秒

### 纯 CLI / library 模式

部分子任务（纯后端单元测试、静态分析、classifier 规则测试等）**不需要任何服务**，仅做 §2 环境激活即可。遇到这类任务请写 "No server processes — environment activation only"。

---

## §2 环境配置

> 环境变量清单、`.env.example` 关联、必需 configs。

### 环境激活命令

```bash
# ───── Unix / macOS （Python venv） ─────
source .venv/bin/activate

# ───── Windows （PowerShell） ─────
.\.venv\Scripts\Activate.ps1

# ───── 前端（apps/ui/） ─────
cd apps/ui && nvm use   # 若使用 nvm；否则确保 Node >= 20
```

### 必需环境变量

参见 `.env.example`（由 `long-task-init-features` 维护）。每个 `env`-type 配置对应 `feature-list.json` 的 `required_configs[]` 一项。

Harness 运行时期望存在的关键变量：

- `HARNESS_HOME` — 默认 `~/.harness`，可覆写
- `HARNESS_WORKDIR` — 目标 repo 绝对路径（F01 首启向导写入）
- `CLAUDE_CONFIG_DIR` — 由 F10 动态设为 `.harness-workdir/<run-id>/.claude/`（NFR-009 零写 `~/.claude/`）
- **不在 .env**：LLM provider API key 必须进 platform keyring（NFR-008 / IFR-006），`.env` 只允许占位注释

### Config 加载

参见 `scripts/check_configs.py`（由 `long-task-init-features` 生成）—— 按项目原生格式加载：

- `.env`（Harness 运行时环境）
- `~/.harness/config.json` / `~/.harness/model_rules.json` / `~/.harness/ui-state.json`
- Platform keyring 条目（通过 `harness.auth.KeyringGateway`）

---

## §3 构建与执行命令

> **下游流水线消费区**。TDD Red/Green、Quality Gate、Feature-ST 通过读取本段获取命令。
> 所有命令使用 **quiet execution 协议**：输出重定向到 `/tmp/*.log`，成功时无需读日志；失败时提取最后 100 行 + 抓 FAIL/ERROR 行。

### 构建命令

```bash
# 后端（Python）—— 安装依赖 + 校验导入
pip install -r requirements.txt > /tmp/build-py-$$.log 2>&1; echo $? > /tmp/build-py-$$.exit
python -c "import harness" >> /tmp/build-py-$$.log 2>&1; echo $? >> /tmp/build-py-$$.exit

# 前端（apps/ui/）—— 安装依赖 + 生产构建（输出 apps/ui/dist/，供 PyInstaller 嵌入）
( cd apps/ui && npm ci && npm run build ) > /tmp/build-ui-$$.log 2>&1; echo $? > /tmp/build-ui-$$.exit

# 单文件打包（仅 M4 / F17；日常开发可跳过）
python -m PyInstaller packaging/harness.spec > /tmp/build-dist-$$.log 2>&1; echo $? > /tmp/build-dist-$$.exit
```

### 单元测试命令

```bash
# 后端（pytest）
pytest -q > /tmp/ut-py-$$.log 2>&1; echo $? > /tmp/ut-py-$$.exit

# 前端（Vitest）
( cd apps/ui && npx vitest run ) > /tmp/ut-ui-$$.log 2>&1; echo $? > /tmp/ut-ui-$$.exit
```

### 覆盖率命令

```bash
# 后端 —— line ≥ 90% / branch ≥ 80%（quality_gates）
pytest --cov=harness --cov-branch --cov-report=term-missing \
       --cov-fail-under=90 > /tmp/cov-py-$$.log 2>&1; echo $? > /tmp/cov-py-$$.exit

# 前端
( cd apps/ui && npx vitest run --coverage ) > /tmp/cov-ui-$$.log 2>&1; echo $? > /tmp/cov-ui-$$.exit
```

### 静态分析命令

> Greenfield：`docs/rules/coding-constraints.md` 不存在，无强制静态分析表。以下命令作为**项目默认工具链**建议（来源：Design §3.4 表 + §8 依赖），未来补齐 `docs/rules/` 时此段升级为强制项并触发 §6 审批。

```bash
# Python lint
ruff check . > /tmp/static-ruff-$$.log 2>&1; echo $? > /tmp/static-ruff-$$.exit
black --check . > /tmp/static-black-$$.log 2>&1; echo $? > /tmp/static-black-$$.exit

# Python 静态类型
mypy harness > /tmp/static-mypy-$$.log 2>&1; echo $? > /tmp/static-mypy-$$.exit

# TS lint
( cd apps/ui && npx eslint src ) > /tmp/static-eslint-$$.log 2>&1; echo $? > /tmp/static-eslint-$$.exit
```

### Re-check 协议

- 任何命令失败 → 修复后**仅重跑失败的测试/步骤**（by name，例如 `pytest tests/test_parser.py::test_hil_extraction -q`），绝不整轮重跑
- 临时文件清理：`trap 'rm -f /tmp/*-$$.log /tmp/*-$$.exit' EXIT`，或统一使用 `mktemp`

### 工具版本锁定

| 工具 | 最低版本 | 来源 |
|---|---|---|
| Python | `>= 3.11`（含 3.12；3.13 暂不稳） | Design CON-001 / §3.4 |
| Node.js | `>= 20` | Vite 5 / shadcn 要求 |
| npm | `>= 10` | 随 Node 20 |
| pytest | `>= 8.3` | Design §8.1 |
| pytest-asyncio | `>= 0.24` | Design §8.1 |
| pytest-cov | `>= 5.0` | Design §8.1 |
| ruff | `>= 0.6` | Design §8.1 |
| black | `>= 24.8` | Design §8.1 |
| mypy | `>= 1.11` | Design §8.1 |
| vite | `>= 5.4` | Design §8.2 |
| vitest | `>= 2.1` | Design §8.2 |
| playwright | `>= 1.48`（仅 E2E） | Design §8.2 |
| pyinstaller | `>= 6.10`（仅 F17） | Design §8.1 |

### 工具/环境故障 Fallback

命令本身异常退出（如 `ModuleNotFoundError` / `npm: command not found` / 端口已占用 / keyring backend 不可用）：

1. **诊断根因** —— 读最后 100 行日志 + 抓 ERROR 行；判断是测试栈未装 / env 未激活 / 服务未启动 / 工具未安装
2. **修复一次** —— 视情况跑 `bash init.sh` / `powershell init.ps1`，或按 §1 启动依赖服务（`svc-api-start.sh` / `svc-ui-dev-start.sh`），或重装依赖（`pip install -r requirements.txt` / `npm ci`）
3. **仍失败** —— SubAgent 返回 `status: blocked`，`evidence` 前缀 `[ENV-ERROR]` 附故障摘要（日志 path + 关键错误行）；**绝不跳过测试继续推进**

---

## §4 存量代码库约束

> **下游流水线消费区**（单一事实源）。Feature Design、TDD、Worker 的新代码必须遵守以下约束。
> **数据源**：`docs/rules/*.md`（由 `codebase-scanner` 扫描填充）。init 阶段直接从 `docs/rules/` 提取关键约束投影到此处；设计文档**不再**镜像这些约束。
> 本段变更必须经人工审批（见 §6）。
>
> **当前状态**：Harness 为 Greenfield 项目（Design §13 明确 "Not applicable — greenfield project"），`docs/rules/` 为空；以下各小节均写占位。首次引入存量代码约束（合并既有仓库、采纳第三方样式规约等）时，应由人工填充并触发 §6 审批。

### §4.1 强制内部库

| 场景 | 必须使用 | 禁止重新实现 |
|---|---|---|
| _(empty — greenfield project)_ | | |

### §4.2 禁用 API

| API / 模式 | 禁用理由 | 替代方案 |
|---|---|---|
| _(empty — greenfield project)_ | | |

### §4.3 代码风格基线

- 命名约定：_(empty — greenfield project)_
- 文件布局：_(empty — greenfield project)_
- 错误处理模式：_(empty — greenfield project)_

### §4.4 构建系统约定

- 构建产物目录：_(empty — greenfield project)_
- 忽略清单参考：`.gitignore`
- 依赖锁文件：_(empty — greenfield project)_

---

## §5 测试环境依赖

> 数据库、消息队列、第三方服务的本地替身配置。

### 数据库

Harness 使用 **文件型 SQLite（aiosqlite）**，每 run 自建 `<workdir>/.harness/tickets.sqlite3`；无外部 DB 服务。测试阶段使用临时目录 fixture 保证隔离：

```bash
# pytest 自动创建 tmp SQLite；无需外部启停
pytest tests/ -q
```

### 消息队列

无。Harness 内部使用 **asyncio.Queue + WebSocket 广播**（IAPI-008/IAPI-012），不依赖外部 MQ。

### 第三方服务

Harness 通过 subprocess / HTTP 调用以下外部依赖（见 Design §6.1 IFR-001..007）：

| 依赖 | 集成方式 | 测试模式 |
|---|---|---|
| Claude Code CLI | subprocess + pty (IFR-001) | Integration 用真 CLI；Unit mock `ptyprocess` |
| OpenCode CLI | subprocess + pty (IFR-002) | 同上 |
| `scripts/phase_route.py` | `asyncio.create_subprocess_exec` (IFR-003) | Integration 调真 py 脚本 |
| OpenAI-compatible HTTP endpoint | `httpx.AsyncClient` (IFR-004) | 默认 `respx` mock；可选 `real_external_llm` smoke（key 经 keyring 注入，本地不入库——见 §5 替身配置） |
| git CLI | subprocess (IFR-005) | 临时 repo fixture + 真 git |
| Platform keyring | `keyring` 库 (IFR-006) | 测试用 `keyring.backends.fail.Keyring` 注入 |
| 内部 WebSocket | FastAPI TestClient (IFR-007) | `httpx.AsyncClient` + `websockets` |

### Chrome DevTools MCP（UI 特性必需）

Harness **UI 特性启用**（feature-list.json 后续标 `ui: true`，如 F12–F16）。Worker 阶段执行 Visual Rendering Contract：

```bash
# 启动 Chrome DevTools MCP server（由 hooks/chrome-mcp-setup 触发；详见 long-task 插件文档）
# Harness 自身不直接启动 MCP；由外层 Claude Code agent 负责拉起
```

### 替身配置

- **OpenAI-compatible HTTP mock**：使用 `respx` pytest fixture；测试夹具 path `tests/fixtures/classifier_responses/`
- **keyring mock**：`pytest` conftest 安装 `keyring.backends.null.Keyring` 避开真实 keychain
- **git repo fixture**：`tmp_path` + `subprocess.run(["git", "init"])`

### Real-External LLM Smoke（可选 · F19 Classifier）

Marker `real_external_llm` 用于真打 OpenAI-compat provider endpoint，验证 IAPI-010 永不抛 + IFR-004 timeout budget 在生产环境成立。**默认 skip**（当 keyring 中无对应 entry 时）；不依赖任何 mock。

API key 路径（NFR-008，**不写入任何文件**，不入 git）：

```bash
source .venv/bin/activate
python -c "
from harness.auth import KeyringGateway
KeyringGateway().set_secret('harness-classifier', '<provider>', '<key>')
"
# <provider> ∈ {minimax, glm, openai, custom}；service prefix 固定 'harness-classifier'
```

执行：

```bash
pytest tests/integration/test_f19_real_minimax.py -v   # 单 provider
pytest -m real_external_llm -v                          # 全部 real-LLM 测试
```

不入 keyring 时测试自动 `pytest.skip(...)`，CI 默认无副作用。注销可调 `KeyringGateway().delete_secret('harness-classifier', '<provider>')`。

---

## §6 人工审批记录

> **任何对 §3 或 §4 的修改必须经过人工审批**。Worker Step 0 读取本段 frontmatter 决定是否阻断启动。

### 审批流程

1. 开发/AI 修改 §3 或 §4
2. 用户审阅 diff
3. 用户更新本文件头 YAML frontmatter：
   ```yaml
   ---
   version: <bump>
   approved_by: <user-handle>
   approved_date: <YYYY-MM-DD>
   approved_sections: ["§3", "§4"]  # 或全部
   ---
   ```
4. 运行 `python scripts/validate_env_guide.py env-guide.md --strict`，退出码 0 → Worker 可启动

### 首次生成豁免

由 `long-task-init` 首次生成时，`approved_by: null` 表示豁免状态；**下次修改 §3/§4 时必须审批**。

### 历史记录

| 日期 | 版本 | 审批人 | 变更摘要 |
|---|---|---|---|
| 2026-04-21 | 1.0 | null | 由 `long-task-init-env` 首次生成：§1 双服务（api/ui-dev）、§2 venv + npm、§3 pytest/pytest-cov/ruff/mypy/eslint、§4 greenfield 占位、§5 SQLite + subprocess 替身说明 |
| 2026-04-21 | 1.1 | godsuriyel@gmail.com | 重新审批 §3 + §4：将 `approved_date` 提升为精确 ISO 时间戳（2026-04-21T09:21:02+08:00），解除 `check_env_guide_approval.py` 同日 commit 误判；内容无变更 |
