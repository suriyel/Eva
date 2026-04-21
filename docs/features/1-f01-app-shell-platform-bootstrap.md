# Feature Detailed Design：F01 · App Shell & Platform Bootstrap（Feature #1）

**Date**: 2026-04-21
**Feature**: #1 — F01 · App Shell & Platform Bootstrap
**Priority**: high
**Dependencies**: 无（本特性是所有后端特性的起点）
**Design Reference**: docs/plans/2026-04-21-harness-design.md § 4.1
**SRS Reference**: FR-046, FR-050, NFR-007, NFR-010, NFR-012, NFR-013（含 CON-006 / CON-007 / IFR-006 / IFR-001 协同约束）

---

## Context

F01 是 Harness 桌面应用的进程入口与平台基线：拉起 PyWebView 壳、绑定 FastAPI（`127.0.0.1`）、首次启动时建 `~/.harness/`、为后续特性提供 `KeyringGateway` 与 `ClaudeAuthDetector` 门面。本特性承载 NFR-007（仅绑 127.0.0.1）/ NFR-008（API key 仅 keyring）/ NFR-009 协同基线（不写 `~/.claude/`，由 F10 实施环境隔离，本特性提供探测面）/ NFR-010 / NFR-012 / NFR-013。

---

## Design Alignment

> 完整复制自 docs/plans/2026-04-21-harness-design.md §4.1。

**4.1.1 Overview**：Python 入口、FastAPI 实例、PyWebView 窗口、首次启动向导、`~/.harness/` 初始化、keyring 门面；强制 FastAPI 绑 `127.0.0.1`。满足 FR-046、FR-050 + NFR-007/008 基线。

**4.1.2 Key Types**
- `harness.app.AppBootstrap` — 选 ephemeral 端口、启 uvicorn、拉 PyWebView 窗口
- `harness.app.FirstRunWizard` — 检测 `~/.harness/config.json` 缺失 → 引导设置
- `harness.config.ConfigStore` — 读/写 `~/.harness/config.json`
- `harness.auth.KeyringGateway` — 封装 `keyring.get/set/delete_password`
- `harness.auth.ClaudeAuthDetector` — 探测 `claude auth` 状态
- `harness.net.BindGuard` — 启动自检 `127.0.0.1` bind

**4.1.3 Integration Surface**
- **Provides**：ConfigStore + Keyring 门面 → F07 / F08 / F10 / F15
- **Requires**：Self-contained

| 方向 | Consumer | Contract ID | Endpoint | Schema |
|---|---|---|---|---|
| Provides | F07 / F08 / F15 | IAPI-014 | Settings Manager ↔ keyring | `get_secret(service, user) → str \| None` |

**Key types 摘要**：本特性引入 6 个新类（AppBootstrap / FirstRunWizard / ConfigStore / KeyringGateway / ClaudeAuthDetector / BindGuard），全部位于 `harness.app` / `harness.config` / `harness.auth` / `harness.net` 命名空间下。

**Provides / Requires 摘要**：
- **Provides**：
  - **IAPI-014**（Settings+KeyringGateway → app-wide）— `get_secret(service, user) → str | None` / `set_secret(service, user, value) → None` / `delete_secret(service, user) → None`，由 F07 / F08 / F15 消费
  - **IFR-006**（Platform keyring）— Provider façade（macOS Keychain / freedesktop Secret Service / Windows Credential Manager；Linux 无 daemon 时自动降级 `keyrings.alt.file.PlaintextKeyring` 并标记 `degraded=True`）
  - **IFR-001 协同**（Claude Code CLI 凭证继承面）— `ClaudeAuthDetector` 暴露 `detect() → ClaudeAuthStatus`，供 F03 / F11 在 spawn 前校验，并供 `/api/health` 写入 `claude_auth` 字段
  - **ConfigStore**（in-process 门面）— F07 / F08 / F15 通过它读写 `~/.harness/config.json`（`api_key_ref` 引用 keyring service+user，从不写明文）
- **Requires**：Self-contained（不依赖项目内其他 feature；外部依赖：`keyring`、`fastapi`、`uvicorn`、`pywebview`、`pydantic v2`）

**Deviations**：无。本特性所有方法签名均与 Design §6.1.6（IFR-006）/ §6.2.1（IAPI-014）/ §6.1.1（IFR-001 凭证继承）原文契约一致。

---

## SRS Requirement

> 完整复制自 docs/plans/2026-04-21-harness-srs.md §FR-046 / §FR-050 / §5 NFR 表 / §7 约束（按 srs_trace 过滤）。

### FR-046: 继承 claude auth login 凭证

**优先级**: Must
**EARS**: The system shall 继承用户机器 `claude auth login` 凭证运行 Claude Code，不单独管理 Anthropic API key。
**可视化输出**: SystemSettings 中 Claude 账号区域显示 "使用系统 claude auth login（只读）"。
**验收准则**:
- Given 用户已 `claude auth login`，when Harness 启动 claude ticket，then 不额外提示 API key
- Given 用户未 auth，when ticket 启动，then CLI 自身报错并被 Harness 捕获为 `skill_error` 上报
**来源**: raw_requirements K.46

### FR-050: 首次启动自动建 ~/.harness/ 与 keyring secrets

**优先级**: Must
**EARS**: When 首次启动 Harness, the system shall 自动创建 `~/.harness/` 目录存配置，且通过平台 keyring（macOS Keychain / freedesktop Secret Service / Windows Credential Manager）存取 LLM provider API key。
**可视化输出**: 首次启动弹窗 "Welcome, 已初始化 ~/.harness/"。
**验收准则**:
- Given 首次启动，when 结束，then `~/.harness/config.json` 存在
- Given 用户保存 API key，when 查配置文件，then 配置文件不含明文 key（仅 keyring 引用）
**来源**: raw_requirements M.50

### NFR（来自 srs_trace）

| ID | Category (ISO 25010) | Requirement | Measurable Criterion | Measurement Method |
|----|---------------------|-------------|---------------------|-------------------|
| NFR-007 | Security — Access Control | FastAPI 绑定地址 | 仅绑 `127.0.0.1`，不监听 `0.0.0.0` / LAN | `ss -tnlp` 验证 socket bind |
| NFR-010 | Usability — Appropriateness Recognizability | UI 语言 | 仅简体中文（v1 不做 i18n）| 视觉评审 + 源代码 grep 无其他语言 strings |
| NFR-012 | Portability — Installability | 支持平台 | Linux x86_64 / macOS x86_64+arm64 / Windows x86_64；PyInstaller 各平台打包 | 三平台 smoke 测试 |
| NFR-013 | Portability — Adaptability | 不依赖用户预装 Python | 二进制在无 Python 环境中能启动 | 干净 VM 测试 |

> NFR-008（API key 仅 keyring）虽未列入本特性 srs_trace，但 IAPI-014 与 KeyringGateway 实现是 NFR-008 的关键载体，本设计在 Implementation Summary 显式记录其对齐方式。
> NFR-009（不写 `~/.claude/`）由 F10 实施环境隔离，本特性仅提供 `ClaudeAuthDetector`（**只读**）协助；写入隔离不在本特性范围。

### 约束（来自 srs_trace 协同）

| ID | Constraint | Rationale |
|----|-----------|-----------|
| CON-006 | FastAPI 绑 `127.0.0.1` only | 安全（NFR-007） |
| CON-007 | Harness 不写入 `~/.claude/` | 环境清洁（NFR-009） |

### IFR（来自 srs_trace 协同）

| ID | External System | Direction | Protocol | Data Format |
|----|----------------|-----------|----------|-------------|
| IFR-006 | 平台 keyring | Bidirectional | python `keyring` 库（macOS Keychain / freedesktop Secret Service / Windows Credential Manager）| Key-Value string pair |
| IFR-001（协同） | Claude Code CLI | Outbound + Bidirectional via pty | pty + argv + stream-json stdout | F01 仅提供 `claude auth login` **凭证存在性**探测面（不 spawn ticket），spawn 由 F03 实现 |

---

## Interface Contract

> 公开方法清单（本特性暴露给同进程其他模块或 REST/WebSocket 客户端）。所有方法签名与 Design §6.1.6 / §6.2.1 / §6.1.1 契约对齐；`Raises` 列是 TDD Rule 4 负向测试的权威来源。

| Method | Signature | Preconditions | Postconditions | Raises |
|--------|-----------|---------------|----------------|--------|
| `AppBootstrap.__init__` | `__init__(self, *, harness_home: Path \| None = None, host: str = "127.0.0.1", port: int = 0) -> None` | `host` 必须为 `"127.0.0.1"`（CON-006 / NFR-007）；`port == 0` 表示 ephemeral；`harness_home` 为 `None` 时由 `ConfigStore.default_path()` 推导（默认 `~/.harness`） | 内部状态初始化完成；尚未 bind socket 也未启 webview | `BindRejectedError`（host ≠ `"127.0.0.1"`）|
| `AppBootstrap.start` | `start(self) -> AppRuntime` | 进程持有创建 `~/.harness/` 的写权限；`pywebview` GUI 后端可用（macOS Cocoa / Linux GTK + WebKit2GTK / Windows EdgeChromium） | uvicorn 监听 `127.0.0.1:<chosen_port>`；`AppRuntime.port > 0`；`BindGuard.assert_loopback_only()` 通过；首启场景下 `~/.harness/config.json` 已存在；PyWebView 主窗口 ≤ 10s 内进入可见态（NFR-012/013 + verification_steps[3]）；`/api/health` 返回 `bind="127.0.0.1"` | `BindRejectedError` / `BindUnavailableError`（端口被占且 `port != 0`）/ `WebviewBackendUnavailableError`（GUI backend 缺失）/ `HarnessHomeWriteError`（无写权限） |
| `AppBootstrap.stop` | `stop(self) -> None` | `start()` 已调用且 `AppRuntime` 在线 | uvicorn server graceful shutdown；PyWebView 窗口关闭；端口释放 | `RuntimeError`（未 start 调 stop） |
| `BindGuard.assert_loopback_only` | `assert_loopback_only(self, sock: socket.socket) -> None` | `sock` 已 bind 完成（`getsockname()` 可调用） | 若 `sock.getsockname()[0]` ∈ {`"127.0.0.1"`, `"::1"`}：返回 None；否则抛 | `BindRejectedError(actual_host: str)` |
| `BindGuard.parse_listening_sockets` | `parse_listening_sockets(self) -> list[ListeningSocket]` | 平台命令可用：Linux `ss -tnlp`、macOS `lsof -nP -iTCP -sTCP:LISTEN`、Windows `netstat -ano -p TCP` | 返回当前进程 PID 拥有的所有 LISTEN socket（host + port + pid）；用于 NFR-007 自检与 `/api/health` 上报 | `OSError`（命令缺失或无权限） |
| `ConfigStore.default_path` | `@classmethod default_path(cls) -> Path` | 进程 `os.environ` 可读 | 返回 `Path(os.environ.get("HARNESS_HOME", str(Path.home() / ".harness"))) / "config.json"`；不创建文件 | — |
| `ConfigStore.load` | `load(self) -> HarnessConfig` | 调用方持有 `config.json` 路径的读权限 | 若文件存在且合法：返回 pydantic 验证过的 `HarnessConfig`；若不存在：返回 `HarnessConfig.default()`（不写盘） | `ConfigCorruptError`（JSON 非法或 pydantic 校验失败，含错误详情） |
| `ConfigStore.save` | `save(self, config: HarnessConfig) -> None` | `config` 已通过 pydantic 校验；调用方持有 `~/.harness/` 写权限 | 写入临时文件后原子 rename；`config.json` 不含明文 API key（仅 `api_key_ref={service,user}`），`~/.harness/` 已存在并 `chmod 0700`（POSIX） | `SecretLeakError`（payload 含疑似明文 key — 见 §3 Implementation Summary 的 leak detector）/ `OSError`（写失败） |
| `FirstRunWizard.is_first_run` | `is_first_run(self) -> bool` | — | 若 `ConfigStore.default_path()` 不存在 OR `~/.harness/` 目录不存在 → `True`；否则 `False` | — |
| `FirstRunWizard.bootstrap` | `bootstrap(self) -> FirstRunResult` | 进程持有 `~/.harness/` 写权限；首启场景（`is_first_run() == True`） | `~/.harness/` 创建（POSIX `chmod 0700`）；`config.json` 写入空配置（`HarnessConfig.default()`，不含明文 key）；返回 `FirstRunResult { home_path, created_files: list[Path], welcome_message: "Welcome, 已初始化 ~/.harness/" }`（NFR-010 简体中文）；`config.json` 写入字节序列经 leak detector 验证 0 条 base64/hex 明文 key 命中（FR-050 AC2） | `HarnessHomeWriteError` / `SecretLeakError` |
| `KeyringGateway.get_secret` | `get_secret(self, service: str, user: str) -> str \| None` | `service` 与 `user` 非空字符串，长度 ≤ 256；`service` 必须以 `"harness-"` 前缀（命名约定 IFR-006）| 返回 `keyring.get_password(service, user)`；若 backend 已降级，附带在 `degraded` 标志（通过 `KeyringGateway.degraded` property）；不抛对调用方 | `KeyringServiceError`（仅当 backend 完全不可用且无 fallback；返 None 优先） |
| `KeyringGateway.set_secret` | `set_secret(self, service: str, user: str, value: str) -> None` | 同上；`value` 非空 | `keyring.set_password(service, user, value)` 已成功；若 backend 是降级文件后端，先写一次性 UI 警告记录到 `degradation_log` | `KeyringServiceError`（写失败）/ `ValidationError`（前缀不符） |
| `KeyringGateway.delete_secret` | `delete_secret(self, service: str, user: str) -> None` | 同 `get_secret` | `keyring.delete_password(service, user)` 已成功；若 entry 不存在，幂等返回 None（不抛） | `KeyringServiceError`（删除失败且 entry 存在） |
| `KeyringGateway.detect_backend` | `detect_backend(self) -> BackendInfo` | — | 返回 `BackendInfo { name: str, degraded: bool, warning: str \| None }`；Linux 无 `SecretService` 时 `degraded=True` 且 `warning="未检测到 Secret Service，凭证以明文存储，建议安装 gnome-keyring"`（IFR-006 + ATS Err-H） | — |
| `ClaudeAuthDetector.detect` | `detect(self) -> ClaudeAuthStatus` | `which claude` 可执行（若不可执行返 `cli_present=False`）| 返回 `ClaudeAuthStatus { cli_present: bool, authenticated: bool, hint: str \| None, source: Literal["claude-cli","skipped"] }`；只读、不修改任何文件、不写 `~/.claude/`（NFR-009 / CON-007）；FR-046 happy 路径 `cli_present=True` & `authenticated=True`；FR-046 错误路径 `cli_present=True` & `authenticated=False` 给出 `hint="请运行: claude auth login"` | `OSError`（subprocess 启动失败时返回 `cli_present=False`，不冒泡） |

**Design rationale**：
- **`host` 默认 `"127.0.0.1"` 且 `__init__` 拒绝其他值**：CON-006 / NFR-007 是硬约束，构造期失败比启动期失败更早暴露配置错误（fail-fast）。
- **`port=0` 默认 ephemeral**：生产模式由 OS 选空闲端口避免冲突；开发模式（`env-guide.md §1`）固定 `8765`，由调用方显式传入。
- **`ConfigStore.save` 原子 rename + leak detector**：避免半写文件被下次启动读到；leak detector 静态扫描 payload 是否含 base64 ≥ 32 字符序列或 `sk-`/`sk-ant-` 前缀，命中即 `SecretLeakError` 防御 NFR-008。
- **`KeyringGateway.set_secret` 校验 service 前缀**：所有 Harness 凭证 service 必须以 `"harness-"` 开头（Design §6.1.6 命名约定），防止误污染其他应用的 keyring 命名空间。
- **`KeyringGateway.detect_backend` Linux 降级文案为简体中文**：NFR-010 + ATS Err-H 共同要求；UI 横幅文本必须中文。
- **`ClaudeAuthDetector.detect` 只读**：CON-007 / NFR-009 禁止本特性写 `~/.claude/`；探测仅 `subprocess.run(["claude", "--version"])` + `subprocess.run(["claude", "auth", "status"])`（或等效轻命令），不触发任何配置写入。
- **`BindGuard.parse_listening_sockets` 跨平台命令选择**：Linux 优先 `ss`（`net-tools` 已废弃）；macOS 用 `lsof`；Windows 用 `netstat`。所有命令以 `argv: list[str]` 调用 `subprocess.run`，禁 `shell=True`（Design §3.3 SEC + ATS §3.3）。
- **跨特性契约对齐**：
  - `KeyringGateway.get_secret/set_secret/delete_secret` ↔ **IAPI-014**（Provider，对 F07 / F08 / F15）— 三方法签名 `(service: str, user: str) → str | None / None / None` 与 §6.2.1 schema `get_secret(service, user) → str | None` 完全一致。
  - `KeyringGateway.detect_backend` ↔ **IFR-006**（Provider façade）— 暴露 `BackendInfo` 让 F15 SystemSettings 显示降级横幅。
  - `ClaudeAuthDetector.detect` ↔ **IFR-001**（凭证继承面，Provider）— `ClaudeAuthStatus` 让 F03 / F11 / `/api/health` 上游消费；本特性不实现 spawn，spawn 是 F03 的责任。

---

## Visual Rendering Contract

> N/A — 后端/平台 feature，无 UI 渲染表面。F15 SystemSettings 页面（`ui: true`，feature #15）会消费本特性的 `KeyringGateway.detect_backend()` 结果与 `ClaudeAuthDetector.detect()` 结果，但具体 DOM 渲染由 F15 的 Visual Rendering Contract 定义，不属于本特性范围。本特性 `feature.ui == false`。

---

## Implementation Summary

**1. 主要类 / 函数与文件布局**

新建 6 个 Python 模块，全部位于 `harness/` 包下：

- `harness/app/__init__.py` — 暴露 `AppBootstrap`、`AppRuntime`、`FirstRunWizard`、`FirstRunResult` 给调用方
- `harness/app/bootstrap.py` — `AppBootstrap`（生命周期：`__init__` → `start()` → `stop()`）、`AppRuntime` dataclass（含 `port: int`、`uvicorn_server`、`webview_window`）
- `harness/app/first_run.py` — `FirstRunWizard.is_first_run()` / `bootstrap()`、`FirstRunResult` pydantic 模型
- `harness/config/__init__.py` — 导出 `ConfigStore`、`HarnessConfig`、`SecretLeakError`、`ConfigCorruptError`
- `harness/config/store.py` — `ConfigStore.default_path()` / `load()` / `save()`、私有 `_detect_secret_leak(payload: bytes) -> None`
- `harness/config/schema.py` — pydantic v2 模型 `HarnessConfig`（字段：`schema_version: int = 1`、`provider_refs: dict[str, ApiKeyRef]`、`retention_run_count: int = 20`、`ui_density: Literal["compact","comfortable"]`），其中 `ApiKeyRef = { service: str, user: str }`（**禁止**含 `value` / `secret` 字段）
- `harness/auth/__init__.py` — 导出 `KeyringGateway`、`BackendInfo`、`KeyringServiceError`、`ClaudeAuthDetector`、`ClaudeAuthStatus`
- `harness/auth/keyring_gateway.py` — `KeyringGateway` 全部方法 + 内部 `_validate_service_prefix(service: str) -> None`
- `harness/auth/claude_detector.py` — `ClaudeAuthDetector.detect()`、`ClaudeAuthStatus` pydantic 模型
- `harness/net/__init__.py` — 导出 `BindGuard`、`ListeningSocket`、`BindRejectedError`、`BindUnavailableError`
- `harness/net/bind_guard.py` — `BindGuard.assert_loopback_only()` / `parse_listening_sockets()`，含 `_parse_ss_output` / `_parse_lsof_output` / `_parse_netstat_output` 三个私有平台 helper
- `harness/api/__init__.py` — 暴露 FastAPI `app`，定义 `/api/health` 路由（`AppBootstrap.start()` 启动后由 uvicorn 加载）

**2. 调用链（运行时谁调谁）**

```
__main__.py → AppBootstrap(host="127.0.0.1", port=0)
            → AppBootstrap.start():
                1. ConfigStore.default_path() → Path
                2. FirstRunWizard.is_first_run() → bool
                3. if first run: FirstRunWizard.bootstrap() → 创建 ~/.harness/ + config.json
                4. socket.socket().bind(("127.0.0.1", port)) → BindGuard.assert_loopback_only(sock)
                5. uvicorn.Server(app, host="127.0.0.1", port=chosen_port).serve() (在后台 asyncio 任务)
                6. BindGuard.parse_listening_sockets() 自检（仅 127.0.0.1 LISTEN）
                7. webview.create_window("Harness", f"http://127.0.0.1:{chosen_port}") + webview.start()
                8. ClaudeAuthDetector.detect() 一次（结果缓存到 AppRuntime，写入 /api/health）
            → AppRuntime
```

后续 F07/F08/F15 通过依赖注入或 FastAPI `Depends` 持有 `KeyringGateway` 与 `ConfigStore` 单例（在 `harness.api` 的 lifespan 中初始化）。

**3. 关键设计决策与非显见约束**

- **`socket.bind` 在 uvicorn 启动**前**先做一次 dry-run**：`AppBootstrap.start` 显式 `socket.socket().bind(("127.0.0.1", port))`，立即 `assert_loopback_only(sock)`，再 close 让 uvicorn 用同一 host:port 重 bind。这避免 uvicorn 内部如果接收到 `host="0.0.0.0"`（无论来源）也能在 BindGuard 处即刻拒绝（fail-fast）。NFR-007 因此双重保险（构造期 + 启动期）。
- **`~/.harness/` POSIX 权限 `0700`**：FirstRunWizard 用 `Path.mkdir(mode=0o700, parents=True, exist_ok=True)`；`config.json` 用 `os.umask(0o077)` + 原子 rename。Windows 平台不强制 ACL（pywin32 加固列入 v1.1 backlog）。
- **`HarnessConfig` 用 pydantic v2 `model_config = ConfigDict(extra="forbid")`**：禁止额外字段，防止意外把 `api_key` 字面量字段写入 config.json。
- **`_detect_secret_leak`**：扫描 payload 是否含连续 base64 字符 ≥ 32 字符且非空白；或匹配 `sk-`、`sk-ant-`、`xai-` 等已知 LLM key 前缀；或匹配 PEM 块。任一命中抛 `SecretLeakError(field_path)`。该检查是 NFR-008 的**纵深防御**层（pydantic schema 已禁字段，但仍存在用户手编 JSON 引入风险）。
- **`KeyringGateway` 单例 vs 多实例**：单例（在 `AppBootstrap.start` lifespan 创建一次）以共享 `degradation_log` 与 backend 探测缓存；FastAPI 用 `Annotated[KeyringGateway, Depends(get_keyring)]` 注入。
- **`ClaudeAuthDetector` 不写 `~/.claude/`**：仅运行 `claude --version` 与 `claude auth status`（若可用）；通过 `subprocess.run(..., env={**os.environ, "CLAUDE_CONFIG_DIR": "/dev/null"})` **不指定**写路径来确保读路径走默认 `~/.claude/`、并读完即返。CON-007 / NFR-009 实施细节由 F10（spawn ticket 时的环境隔离）兜底；本特性的探测调用对 mtime 影响为零（READ-only 操作），ATS NFR-009 验证仍由 F10 整链 mtime diff 断言。
- **`/api/health` 路由**：返回 `{ "bind": "127.0.0.1", "version": "0.0.0", "claude_auth": ClaudeAuthStatus, "cli_versions": { "claude": "<x.y.z>" | null, "opencode": "<x.y.z>" | null } }`（与 Design §6.2.2 行 `GET /api/health` schema 一致）。
- **PyWebView 启动时序**：`webview.start()` 是阻塞调用；`AppBootstrap.start` 在前置完成后 spawn 一个 daemon thread 跑 `webview.start()`，主线程 await uvicorn server。NFR-012/013 + verification_steps[3] 要求 ≤ 10s 可见 — 通过预先打开 webview 的 splash window（pywebview 5.x 支持）+ 异步 init 实现。
- **三平台兼容**（NFR-012）：Linux 需 `libwebkit2gtk-4.1`；macOS 用系统 WKWebView；Windows 用 EdgeChromium WebView2 runtime（PyInstaller spec 检测并在缺失时给出友好提示）。
- **NFR-010 简体中文**：本特性产生的所有面向用户字符串（`FirstRunResult.welcome_message`、`KeyringGateway.detect_backend().warning`、`ClaudeAuthStatus.hint`）必须为简体中文；TDD 测试用 `re.search(r"[一-鿿]", text)` + 黑名单关键英文断言。

**4. 遗留 / 存量代码交互点**

- `harness/` 包当前仅含 `.gitkeep`（task-progress.md Session 0 记录）；`tests/` 同。本特性是 Harness 后端的真正起点。
- `scripts/svc-api-start.sh` / `.ps1` 已经预期 `import harness.api` 并以 `uvicorn harness.api:app --host 127.0.0.1 --port 8765` 启动（开发期固定端口）；本特性必须确保 `harness.api:app` 模块顶层暴露 `app: FastAPI`，并在 uvicorn 直接拉起场景下 `BindGuard` 仍生效（通过 FastAPI `lifespan` startup 钩子调用）。
- `scripts/check_configs.py` 已读取 `~/.harness/config.json` 与 `HARNESS_HOME` env（feature-list.json `required_configs` 列出 `HARNESS_HOME` / `HARNESS_WORKDIR` / `HarnessConfigFile`）；本特性需保证 `FirstRunWizard.bootstrap()` 写出的 `config.json` 通过 `check_configs.py` 校验。
- **env-guide.md §4**：当前为空（greenfield 占位，已经过 §6 审批 v1.1 — 内容仍为空但已 acknowledged）；故没有强制内部库或禁用 API。本设计采用 PEP 8 + mypy strict（`pyproject.toml` 已配 `[tool.mypy] strict = true, files = ["harness"]`）+ ruff + black 作为 de-facto 基线，符合 env-guide §3 工具链记录。日后若 `docs/rules/coding-constraints.md` 出现强制项，需通过 §6 审批后回填本文件并重新评审。

**5. §4 / §6 Internal API Contract 集成**

- **IAPI-014**（Provider）：`KeyringGateway.get_secret/set_secret/delete_secret` 直接实现 §6.2.1 表行 `IAPI-014 | Settings+KeyringGateway | app-wide | method | (service, user) | str | None | KeyringError`。F07 ModelOverride、F08 Classifier、F15 SystemSettings 通过 FastAPI `Depends(get_keyring)` 消费。
- **IFR-006**（Provider façade）：`KeyringGateway.detect_backend()` + Linux 降级路径 + UI 中文告警，对齐 §6.1.6 故障模式。
- **IFR-001**（凭证继承面，Provider）：`ClaudeAuthDetector.detect()` 暴露 `ClaudeAuthStatus`，被 `/api/health` 与未来 F03 spawn 前置消费；本特性**不**触发 ticket spawn（spawn 是 F03 的责任，IAPI-005）。
- 没有 Consumer 角色 — F01 是依赖图的根。

### Boundary Conditions

| Parameter | Min | Max | Empty/Null | At boundary |
|-----------|-----|-----|------------|-------------|
| `AppBootstrap.host` | — | — | `""` → `BindRejectedError` | 仅 `"127.0.0.1"` 与 `"::1"` 通过；`"0.0.0.0"` / `"localhost"`（解析后非 loopback）/ LAN IP 全部抛 `BindRejectedError` |
| `AppBootstrap.port` | `0`（ephemeral） | `65535` | `None` → 用 `0`；`< 0` 或 `> 65535` 抛 `ValueError` | `0` → OS 选；非 0 且被占 → `BindUnavailableError` |
| `ConfigStore.default_path()` 解析 | — | — | `HARNESS_HOME=""` → 用默认 `~/.harness`；`HARNESS_HOME="~"` 不展开（按字面）| `HARNESS_HOME=/不存在/path` → `load()` 走 `default()` 不抛；`save()` 抛 `OSError`（无写权限） |
| `KeyringGateway.service` 长度 | 1 | 256 | `""` → `ValidationError` | 长度 > 256 → `ValidationError`；前缀必须 `harness-` 否则 `ValidationError` |
| `KeyringGateway.user` 长度 | 1 | 256 | `""` → `ValidationError` | 长度 > 256 → `ValidationError` |
| `KeyringGateway.set_secret(value)` 长度 | 1 | 32768（任意 LLM API key 远小于此） | `""` → `ValidationError` | 极大 value 截断警告但仍写入（按 keyring backend 容量） |
| `FirstRunWizard.bootstrap` `~/.harness/` 已存在但 `config.json` 缺 | — | — | `~/.harness/` 存在但 `config.json` 不存在 → 视作 first run（ATS Err-H 共轨）；`~/.harness/` 存在 + 文件存在 + 0 字节 → `ConfigCorruptError` | 目录存在但权限不允许写 → `HarnessHomeWriteError` |
| `ClaudeAuthDetector.detect()` `which claude` | — | — | `claude` 不在 PATH → `cli_present=False, authenticated=False, hint="未检测到 Claude Code CLI"` | `claude` 存在但 `auth status` exit ≠ 0 → `cli_present=True, authenticated=False, hint="请运行: claude auth login"`（FR-046 错误路径） |
| `BindGuard.parse_listening_sockets()` PID 集合 | 0 个 socket | 任意 | 进程无 LISTEN 端口 → 返 `[]` | 含非本进程 PID 的 socket 必须被过滤掉 |

### Existing Code Reuse

> 以下关键字在 `/home/machine/code/Eva/harness/` 与 `/home/machine/code/Eva/tests/` 全量 grep 命中 0 处（两目录目前仅含 `.gitkeep` 占位）。`scripts/svc-api-start.sh` 引用 `harness.api:app` 但属于 launcher 脚本（非 Python 可复用符号）。

| Existing Symbol | Location (file:line) | Reused Because |
|-----------------|---------------------|----------------|

> N/A — searched keywords: [`AppBootstrap`, `FirstRunWizard`, `ConfigStore`, `KeyringGateway`, `ClaudeAuthDetector`, `BindGuard`, `import keyring`, `from keyring`, `from fastapi`, `import pywebview`, `import uvicorn`, `harness_home`, `HARNESS_HOME`, `claude_auth`, `bind_127`, `first_run`, `wizard`], no reusable match — Harness 是 greenfield 项目（`harness/` 与 `tests/` 仅含 `.gitkeep`，task-progress.md Session 0 已记录）。`scripts/check_configs.py` 与 `scripts/svc-api-start.sh` 已建立**外部接口约定**（`HARNESS_HOME` env、`harness.api:app` 模块路径、`~/.harness/config.json` 文件结构）但未提供可导入的 Python 符号。

---

## Test Inventory

> 综合 Interface Contract / Boundary Conditions / SRS srs_trace 派生。**ATS 类别覆盖检查**：FR-046 要求 FUNC + BNDRY + SEC；FR-050 要求 FUNC + BNDRY + SEC；NFR-007 要求 SEC；NFR-010 要求 FUNC + UI（本特性后端无 UI 表面，UI 部分追溯到 F15）；NFR-012 / NFR-013 要求 FUNC + PERF（冷启动 < 10s）；IFR-006 要求 FUNC + BNDRY + SEC；IFR-001（凭证继承面）要求 FUNC + BNDRY + SEC。本特性外部依赖：filesystem（`~/.harness/`）+ keyring + 网络 socket bind + claude CLI 进程 → 至少 4 行 INTG。

| ID | Category | Traces To | Input / Setup | Expected | Kills Which Bug? |
|----|----------|-----------|---------------|----------|-----------------|
| T01 | FUNC/happy | FR-050 AC1, §IC `FirstRunWizard.bootstrap` | tmp `HARNESS_HOME=<tmpdir>/.harness`（不存在）→ `FirstRunWizard(ConfigStore(...)).bootstrap()` | `<tmpdir>/.harness/config.json` 存在；`HarnessConfig.load()` 返回 `default()`；目录权限 `0o700`（POSIX）；返回 `FirstRunResult.welcome_message == "Welcome, 已初始化 ~/.harness/"` | 首启目录未建 / 权限错 / 默认 config 字段缺 |
| T02 | FUNC/happy | FR-050 AC2, §IC `ConfigStore.save` | `HarnessConfig(provider_refs={"glm": ApiKeyRef(service="harness-classifier-glm", user="default")})` → `ConfigStore.save(cfg)` | 写出的 `config.json` bytes 不含 `sk-`、`sk-ant-`、≥32 连续 base64 字符；JSON 含 `api_key_ref` 但无 `value`/`secret` 字段 | 误把明文 API key 序列化进 config.json |
| T03 | FUNC/error | FR-050 AC2, §IC `ConfigStore.save` Raises `SecretLeakError` | 构造非法 payload（如手动 `model_dump` 后 inject 字符串 `"sk-ant-1234567890abcdef..."` 到自由字段） | 抛 `SecretLeakError(field_path)`；`config.json` **未**被覆写（原子 rename 前抛错） | leak detector 未生效或绕过；半写文件污染 |
| T04 | FUNC/happy | FR-046 AC1, §IC `ClaudeAuthDetector.detect` | mock `subprocess.run(["claude", "--version"])` exit=0 + `subprocess.run(["claude", "auth", "status"])` exit=0 stdout `"Logged in as user@example.com"` | `ClaudeAuthStatus { cli_present=True, authenticated=True, hint=None, source="claude-cli" }`；调用过程**不**写任何文件（mtime diff = 0） | 误以为已登录而上报未登录 / 误写 `~/.claude/` |
| T05 | FUNC/error | FR-046 AC2, §IC `ClaudeAuthDetector.detect` | mock `subprocess.run(["claude", "auth", "status"])` exit=1 stderr `"not authenticated"` | `ClaudeAuthStatus { cli_present=True, authenticated=False, hint="请运行: claude auth login", source="claude-cli" }` | 未 auth 状态被吞 / hint 缺失或非中文（NFR-010） |
| T06 | FUNC/error | §Boundary `claude` 不在 PATH | mock `shutil.which("claude") → None` | `ClaudeAuthStatus { cli_present=False, authenticated=False, hint="未检测到 Claude Code CLI", source="skipped" }`；不抛异常 | CLI 缺失冒泡为未捕获异常导致 Harness 崩溃 |
| T07 | SEC/bind-host | NFR-007, §IC `AppBootstrap.__init__` Raises | `AppBootstrap(host="0.0.0.0")` | 抛 `BindRejectedError(actual_host="0.0.0.0")`；进程未启 socket | host 默认值被覆写为 LAN，导致暴露 |
| T08 | SEC/bind-runtime | NFR-007, §IC `BindGuard.assert_loopback_only` | 构造一个 bind 到 `0.0.0.0:0` 的真实 socket（不经过 `AppBootstrap`，模拟绕过场景）→ `BindGuard().assert_loopback_only(sock)` | 抛 `BindRejectedError(actual_host="0.0.0.0")` | 启动期 guard 失效；只信任构造期检查 |
| T09 | INTG/network | NFR-007, §IC `AppBootstrap.start` + `BindGuard.parse_listening_sockets` | 真实启动 `AppBootstrap(port=0).start()` → 本机执行 `ss -tnlp`（Linux）/ `lsof`（macOS）/ `netstat`（Windows）解析 | 仅一条 LISTEN socket，`host == "127.0.0.1"`，PID == os.getpid()；无 `0.0.0.0` 监听；`stop()` 后端口释放 | uvicorn 默认 host 漂移；端口泄漏 |
| T10 | INTG/keyring | IFR-006 + IAPI-014 happy, §IC `KeyringGateway.set_secret/get_secret/delete_secret` | pytest fixture 用 `keyring.backends.fail.Keyring` 与 `keyring.backends.null.Keyring` 切换；happy 用真实平台 backend（CI 跳 — Linux 用 keyrings.alt 文件后端 fixture） | `set_secret("harness-classifier-glm", "default", "v")` 后 `get_secret(...)` 返 `"v"`；`delete_secret(...)` 后 `get_secret(...)` 返 `None`；`detect_backend().name` 非空 | API 漂移 / backend 实际未写 |
| T11 | INTG/keyring-degradation | IFR-006 Linux fallback, ATS Err-H | mock `keyring.get_keyring()` 返 `keyrings.alt.file.PlaintextKeyring` | `KeyringGateway.detect_backend()` 返 `BackendInfo { degraded=True, warning="未检测到 Secret Service，凭证以明文存储，建议安装 gnome-keyring" }`；`set_secret` 仍成功；`degradation_log` 含一条记录 | Linux 降级未触发 UI 警告 → 用户误以为安全 |
| T12 | SEC/keyring-prefix | §Boundary `KeyringGateway.service` 前缀 | `KeyringGateway().set_secret("not-harness-prefix", "u", "v")` | 抛 `ValidationError`（service 必须 `harness-` 前缀） | 命名空间污染其他应用的 keyring 项 |
| T13 | BNDRY/keyring-empty | §Boundary `service`/`user`/`value` 空串 | `KeyringGateway().set_secret("", "u", "v")` / `(s, "", "v")` / `(s, "u", "")` | 三种均抛 `ValidationError`；keyring 未被调用 | 空字符串 silently 写入 backend 产生不可读条目 |
| T14 | BNDRY/keyring-length | §Boundary 长度 256/257 | `set_secret("harness-" + "a"*249, ...)` 通过；`set_secret("harness-" + "a"*250, ...)` 抛 | 256 通过 / 257 抛 `ValidationError` | off-by-one 边界 |
| T15 | SEC/config-extra-fields | NFR-008 共轨, §IC `ConfigStore.load` Raises | 手写 `config.json = {"api_key": "sk-ant-xyz", "schema_version": 1}` → `ConfigStore(path).load()` | 抛 `ConfigCorruptError`（pydantic `extra="forbid"`） | 历史遗留字段被静默接受 → 明文 key 流入运行时 |
| T16 | BNDRY/config-corrupt | §Boundary config 0 字节 | 写 `config.json` 为 0 字节 → `ConfigStore.load()` | 抛 `ConfigCorruptError`（含错误详情） | 半写状态被当作 default 静默继续 |
| T17 | BNDRY/first-run-rerun | §Boundary `is_first_run` | 已经存在的 `~/.harness/config.json`（合法）→ `FirstRunWizard.is_first_run()` | 返 `False`；`bootstrap()` 不被调用；不覆盖现有 config | 重启误触首启向导 → 覆盖用户配置 |
| T18 | INTG/filesystem-permissions | §IC `FirstRunWizard.bootstrap` Raises `HarnessHomeWriteError` | tmp dir `chmod 0500`（不可写）→ `FirstRunWizard(ConfigStore(<tmp>/.harness/config.json)).bootstrap()` | 抛 `HarnessHomeWriteError`；不部分写文件 | 无写权限被吞 → 后续 load 失败 cascade |
| T19 | FUNC/health-endpoint | NFR-007 + IAPI-014 协同 + §3 §6.2.2 `/api/health` | 启动 `AppBootstrap(port=0)` → `httpx.AsyncClient(...).get("/api/health")` | 200；JSON 含 `{ "bind": "127.0.0.1", "version": ..., "claude_auth": {...}, "cli_versions": {...} }`；`bind` 字段 == `"127.0.0.1"` | health 错误地报 `0.0.0.0` / 字段缺失 |
| T20 | FUNC/zh-CN-text | NFR-010, §IC `FirstRunResult.welcome_message` + `KeyringGateway.detect_backend.warning` + `ClaudeAuthStatus.hint` | 收集本特性所有面向用户字符串列表 → 对每条断言 | 含至少一个 CJK 字符（`re.search(r"[一-鿿]", text)`）且不含黑名单英文短语（`Welcome, please log in` / `not authenticated` 等业务字符串）| 文案漏译为英文 |
| T21 | INTG/cli-presence-real | IFR-001 凭证继承面，验收 verification_steps[3] 协同 | 在 CI 中真实安装 `claude` CLI（mock 化路径）→ `ClaudeAuthDetector().detect()` | `cli_present=True`；耗时 < 1s；不写 `~/.claude/`（`stat -c '%Y' ~/.claude/**/*` 前后一致） | subprocess 漂移导致 mtime 变化（破坏 NFR-009 前置） |
| T22 | PERF/cold-start | NFR-012 / NFR-013 + verification_steps[3] | 从 `AppBootstrap()` 构造到 `/api/health` 返回 200 计时（不含 webview render） | `< 10_000 ms`（CI 三平台 smoke 各跑 1 次） | 启动慢 → UI 冷启动超 10s（违反 verification_steps[3]） |
| T23 | BNDRY/port-out-of-range | §Boundary `AppBootstrap.port` 越界 | `AppBootstrap(port=-1)` / `AppBootstrap(port=65536)` | 两者均抛 `ValueError` | 越界 port 被传到 `socket.bind` 触发 `OverflowError`（不友好） |
| T24 | FUNC/error | §IC `AppBootstrap.start` Raises `BindUnavailableError` | 提前用另一 socket 占用 `127.0.0.1:8765` → `AppBootstrap(port=8765).start()` | 抛 `BindUnavailableError`；不启 webview；不污染 `~/.harness/` | 端口冲突被吞 → silent 双启动 |
| T25 | FUNC/error | §IC `AppBootstrap.start` Raises `WebviewBackendUnavailableError` | mock `webview.create_window` 抛 `RuntimeError("no GUI backend")` | 抛 `WebviewBackendUnavailableError`；uvicorn server graceful shutdown；端口已释放 | webview 失败导致 uvicorn 端口悬挂 |
| T26 | FUNC/error | §IC `AppBootstrap.stop` Raises `RuntimeError` | 未 `start()` 直接 `stop()` | 抛 `RuntimeError("not started")` | 静默成功导致后续状态混乱 |
| T27 | SEC/path-traversal | §Boundary `HARNESS_HOME` 解析 | 设 `HARNESS_HOME="/etc/passwd"` → `FirstRunWizard.bootstrap()` | 不写入 `/etc/passwd`；按字面路径尝试 `mkdir` → `HarnessHomeWriteError`（无权限或非目录） | env 注入导致越权写敏感路径 |

**统计**：27 行，其中负向（FUNC/error + BNDRY/* + SEC/*）= T03 / T05 / T06 / T07 / T08 / T11 / T12 / T13 / T14 / T15 / T16 / T17 / T18 / T23 / T24 / T25 / T26 / T27 共 **18 行**。负向占比 = 18/27 = **66.7%**（≥ 40% 阈值）。

**类别覆盖**：FUNC（T01/T02/T03/T04/T05/T06/T19/T20/T24/T25/T26）/ SEC（T07/T08/T12/T15/T27）/ BNDRY（T13/T14/T16/T17/T23）/ INTG（T09/T10/T11/T18/T21）/ PERF（T22）— 覆盖 ATS 对本特性 srs_trace 的全部要求类别（FUNC / BNDRY / SEC / PERF）。UI 类别本特性 `ui:false` → 由 F15 SystemSettings 覆盖 NFR-010 视觉评审部分（ATS §2.2 NFR-010 备注：F12-F16）。

**INTG 行**：T09（network/socket bind）/ T10（keyring 真实 backend）/ T11（keyring 降级）/ T18（filesystem 权限）/ T21（CLI 真实存在性）= **5 行**，覆盖本特性 4 类外部依赖（socket bind、keyring、filesystem、subprocess CLI）。

**Design Interface Coverage Gate**：§4.1.2 列出 6 个 Key Type — `AppBootstrap`（T07/T09/T19/T22/T23/T24/T25/T26）/ `FirstRunWizard`（T01/T17/T18/T27）/ `ConfigStore`（T02/T03/T15/T16）/ `KeyringGateway`（T10/T11/T12/T13/T14）/ `ClaudeAuthDetector`（T04/T05/T06/T21）/ `BindGuard`（T08/T09）— 全部至少 1 行覆盖。`/api/health` 路由由 T19 覆盖。

---

## Verification Checklist
- [x] 所有 SRS 验收准则（来自 srs_trace）已追溯到 Interface Contract 的 postconditions（FR-046 → `ClaudeAuthDetector.detect`；FR-050 → `FirstRunWizard.bootstrap` + `ConfigStore.save`；NFR-007 → `BindGuard` 双方法 + `AppBootstrap.start`；NFR-010 → 文案 postcondition；NFR-012/013 → `AppBootstrap.start` 启动时序与 `BindGuard.parse_listening_sockets`）
- [x] 所有 SRS 验收准则（来自 srs_trace）已追溯到 Test Inventory 行（FR-046 → T04/T05/T06/T21；FR-050 → T01/T02/T03/T15/T16/T17；NFR-007 → T07/T08/T09/T19；NFR-010 → T20；NFR-012/013 → T22）
- [x] Boundary Conditions 表覆盖所有非平凡参数（host / port / service 长度 / user 长度 / value 长度 / config 字节 / `~/.harness/` 状态 / `HARNESS_HOME` env）
- [x] Interface Contract Raises 列覆盖所有预期错误条件（`BindRejectedError` / `BindUnavailableError` / `WebviewBackendUnavailableError` / `HarnessHomeWriteError` / `ConfigCorruptError` / `SecretLeakError` / `KeyringServiceError` / `ValidationError`）
- [x] Test Inventory 负向占比 ≥ 40%（实际 66.7% = 18/27）
- [x] Visual Rendering Contract — N/A（`feature.ui == false` 已说明）
- [x] 每个 Visual Rendering Contract 元素至少 1 行 UI/render — N/A（同上）
- [x] Existing Code Reuse 章节已填充（greenfield，附 17 个搜索关键字 + 0 命中说明）
- [x] 每个被跳过的章节都写明 "N/A — [reason]"（仅 Visual Rendering Contract 段；其他段全部完整）

---

## Clarification Addendum

> 无需澄清 — 全部规格明确。Step 1b 歧义扫描未发现 `SRS-VAGUE` / `SRS-DESIGN-CONFLICT` / `SRS-MISSING` / `ATS-MISMATCH` / `DEP-AMBIGUOUS` / `NFR-GAP`。本特性 `ui: false` → 跳过 `UCD-VAGUE`。`category: "core"` → 跳过 `ATS-BUGFIX-REGRESSION-MISSING`。

| # | Category | Original Ambiguity | Resolution | Authority |
|---|----------|--------------------|------------|-----------|
| — | — | — | — | — |
