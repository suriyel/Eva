# 测试用例集: F18 · Bk-Adapter — Agent Adapter & HIL Pipeline

**Feature ID**: 18
**关联需求**: FR-008, FR-009, FR-011, FR-012, FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, NFR-014, IFR-001, IFR-002（ATS §2.1 C HIL + D Tool Adapter；必须类别：FUNC/BNDRY/SEC/PERF/INTG；Test Inventory T01–T32 追溯）
**日期**: 2026-04-24
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则（FR-008/009/011/012/013/014/015/016/017/018 + NFR-014 + IFR-001/002）、ATS §2.1 C/D 必须类别约束、Feature Design Test Inventory T01–T32、可观察接口（`harness.adapter` / `harness.pty` / `harness.stream` / `harness.hil` 公开 API、`subprocess.run argv` 观测、POSIX 文件系统观测含 `os.stat().st_mode` 权限位、`pathlib.Path.is_symlink`、pytest caplog structlog warning 观测、`@pytest.mark.real_cli` 真 `claude` CLI 行为观测、mypy `--strict` 退出码）推导，不阅读实现源码。
> - **Specification resolutions applied from Feature Design Clarification Addendum**：
>   - **A1 DEP-AMBIGUOUS（assumed, low-impact）**：IAPI-015 `ModelResolver.resolve`（F19 Provider）在 Wave 2 未实现 — F18 TDD Green 期以 `ModelResolverStub.resolve(ctx) → ResolveResult(model, provenance)` 填洞；接口签名与 Design §6.2.4 `ResolveResult` 完全一致。本特性 ST 用例 T01/T02/T04 的 argv 断言以 Stub 行为为准（`--model <alias>` 仅在 `spec.model` 非 None 时出现），F19 落地后 orchestrator 换实现 0 改动 F18 代码。
> - `feature.ui == false` → 本特性无 UI 类别用例；FR-009 捕获的 HIL 事件最终由 F21 `Fe-RunViews` 渲染（独立 ST 承担），本特性覆盖的是**后端事件管道** + argv/hooks 构造契约表面。
> - 本特性以 **"No server processes — environment activation only"** 模式运行（env-guide §1 纯 CLI / library 模式 —— `pytest tests/test_f18_*.py tests/integration/test_f18_*.py -m "not real_cli"`），无需启动 `api` / `ui-dev` 服务。环境仅需 §2 `.venv` 激活。
> - **FR-013 HIL PoC 与 T29 真 CLI round-trip**：需在用户真实 `claude` CLI 下以交互 prompt 驱动 AskUserQuestion 触发；本 SubAgent 无法在无 prompt 的 headless 模式下自动完成 20 轮 round-trip（`claude` CLI 在 headless pty + `HOME=<isolated>` 但无用户 prompt 的情况下不会自发产生 AskUserQuestion）。ST-FUNC-018-018（T29）与 ST-PERF-018-001（T30）标注为 `已自动化: No`，`手动测试原因: external-action`（需用户提交真实 prompt 驱动 HIL round-trip）并在下游由 dispatcher 以 `[MANUAL_TEST_REQUIRED]` 人工 review 闭环；其余 FR-013 的自动化覆盖由 T21/T22/T23 + 单元级 event burst 覆盖 PoC 关键路径。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 26 |
| boundary | 7 |
| ui | 0 |
| security | 4 |
| performance | 2 |
| **合计** | **39** |

---

### 用例编号

ST-FUNC-018-001

### 关联需求

FR-016 AC-1 · IFR-001 · §Interface Contract ClaudeCodeAdapter.build_argv · Feature Design Test Inventory T01 · ATS §2.1 D FR-016

### 测试目标

验证 `ClaudeCodeAdapter.build_argv(DispatchSpec)` 在典型隔离输入下输出与 FR-016 精确匹配的 argv 顺序：`claude`、`--dangerously-skip-permissions`、`--output-format stream-json`、`--include-partial-messages`、`--plugin-dir <p>`、`--mcp-config <p>`、`--strict-mcp-config`、`--settings <p>`、`--setting-sources user,project`；不含 `-p` 与 `--model`（`spec.model is None`）。

### 前置条件

- `.venv` 激活；`harness.adapter.claude.ClaudeCodeAdapter`、`harness.domain.ticket.DispatchSpec` 可导入
- `pytest tmp_path` 提供空白目录；构造 `plugin_dir` / `settings_path` / `mcp_config` 均位于 `<tmp>/.harness-workdir/r1/.claude/` 隔离子树
- `spec.argv=["claude"]`、`spec.env={...}`、`spec.model=None`、`spec.mcp_config=<path>`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 在 `tmp_path` 下构造 `.harness-workdir/r1/.claude/` 并写入合法 `settings.json` / `mcp.json` | 路径可被 `Path.resolve()` 解析 |
| 2 | 构造 `DispatchSpec(argv=["claude"], env={...}, cwd=<wd>, model=None, mcp_config=<mcp.json>, plugin_dir=<plugins>, settings_path=<settings.json>)` | pydantic 构造成功 |
| 3 | `adapter = ClaudeCodeAdapter()`；`argv = adapter.build_argv(spec)` | 返回 `list[str]` 无异常 |
| 4 | 断言 `argv[0] == "claude"` | True |
| 5 | 断言 `"--dangerously-skip-permissions" in argv` 且 `"-p" not in argv` | True |
| 6 | 断言 `"--output-format" in argv` 且 `argv[argv.index("--output-format")+1] == "stream-json"` | True |
| 7 | 断言 `"--include-partial-messages" in argv` | True |
| 8 | 断言 `"--plugin-dir" in argv` 且其后跟的路径等于 `spec.plugin_dir` | True |
| 9 | 断言 `"--mcp-config" in argv` 且其后跟 `spec.mcp_config`；`"--strict-mcp-config" in argv` | True |
| 10 | 断言 `"--settings" in argv` 且其后跟 `spec.settings_path` | True |
| 11 | 断言 `"--setting-sources" in argv` 且其后参数 `== "user,project"`（不含 `local`） | True |
| 12 | 断言 `"--model" not in argv`（`spec.model is None`） | True |

### 验证点

- argv 顺序与 FR-016 精确匹配（equality list assertion）
- `-p` 绝不出现（违反 FR-008 基本前提）
- `--setting-sources` 不含 `local`（NFR-009 环境清洁）
- `--model` 仅在 `spec.model` 显式给定时出现（FR-016 AC-2）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_protocol.py::test_t01_claude_build_argv_full_required_flag_set`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-002

### 关联需求

FR-016 AC-2 · §Interface Contract build_argv · Feature Design Test Inventory T02

### 测试目标

验证 `ClaudeCodeAdapter.build_argv` 在 `spec.model="sonnet-4"` 时额外输出 `--model sonnet-4`，且位置位于 flag 段尾部（不破坏 FR-016 必选 flag 顺序）。

### 前置条件

- 同 ST-FUNC-018-001；`spec.model="sonnet-4"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 同 ST-FUNC-018-001 Step 1-2，但 `spec.model="sonnet-4"` | spec 构造成功 |
| 2 | `argv = adapter.build_argv(spec)` | 返回 `list[str]` |
| 3 | 断言 `"--model" in argv` | True |
| 4 | 断言 `argv[argv.index("--model")+1] == "sonnet-4"` | True |
| 5 | 同时断言 FR-016 全部必选 flag 仍按 ST-FUNC-018-001 规则存在 | True |

### 验证点

- `spec.model` 非 None 时透传为 `--model <alias>`
- 模型 alias 原样传递，不被改写

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_protocol.py::test_t02_claude_build_argv_includes_model_when_set`、`tests/test_f18_coverage_supplement.py::test_claude_build_argv_with_model_and_mcp`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-001

### 关联需求

FR-016 · IFR-001 SEC · NFR-009 · §Interface Contract `InvalidIsolationError` Raises · Feature Design Test Inventory T03 · ATS §2.1 D 备注"env 白名单"

### 测试目标

验证 `ClaudeCodeAdapter.build_argv` 当 `spec.plugin_dir` 指向用户真实 `~/.claude/plugins` 或其它 `.harness-workdir/` 子树之外的路径时抛 `InvalidIsolationError`；不构造任何 argv、不泄漏隔离外路径到子进程 argv。

### 前置条件

- `.venv` 激活；`harness.adapter.errors.InvalidIsolationError` 可导入
- 构造 `plugin_dir="/home/user/.claude/plugins"`（绝对路径、隔离外）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `DispatchSpec(argv=["claude"], ..., plugin_dir="/home/user/.claude/plugins", settings_path=<合法隔离路径>)` | spec 构造成功（字段 pydantic 级校验不拦） |
| 2 | `adapter.build_argv(spec)` | 抛 `InvalidIsolationError` |
| 3 | 断言异常 message 含"plugin_dir" 或等效路径描述词 | True |
| 4 | 断言过程中未产生任何 argv 返回值 | True |

### 验证点

- 隔离路径守卫在 build 阶段拦截（早期失败）
- 违反 CON-007 / NFR-009 的输入不被放行
- 异常消息可辨认漏洞点

### 后置检查

- 无服务副作用；无需清理

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_protocol.py::test_t03_claude_build_argv_rejects_non_isolated_plugin_dir`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-003

### 关联需求

FR-017 AC-1 · IFR-002 · §Interface Contract OpenCodeAdapter.build_argv · Feature Design Test Inventory T04

### 测试目标

验证 `OpenCodeAdapter.build_argv(DispatchSpec)` 在 `model=None`、`mcp_config=None` 时返回 `["opencode"]` 或等效最简 argv（不含 `--model`、`--agent`、`--mcp-config`、`--strict-mcp-config` 等 Claude 专属 flag）。

### 前置条件

- `.venv` 激活；`harness.adapter.opencode.OpenCodeAdapter` 可导入
- 构造 DispatchSpec `argv=["opencode"]`、`model=None`、`mcp_config=None`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 同 ST-FUNC-018-001 Step 1 构造隔离目录 | 就绪 |
| 2 | 构造 `DispatchSpec(argv=["opencode"], ..., model=None, mcp_config=None)` | spec 构造成功 |
| 3 | `adapter = OpenCodeAdapter()`；`argv = adapter.build_argv(spec)` | 返回 list |
| 4 | 断言 `argv[0] == "opencode"` | True |
| 5 | 断言 `"--model" not in argv`、`"--agent" not in argv` | True |
| 6 | 断言 `"--mcp-config" not in argv` 且 `"--strict-mcp-config" not in argv` | True |
| 7 | 断言 `"--dangerously-skip-permissions" not in argv`（Claude 专属 flag 不串入 OpenCode） | True |

### 验证点

- OpenCode argv 首元素正确
- 无 Claude 专属 flag 污染
- 可选 flag 在对应字段为 None 时严格省略

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_protocol.py::test_t04_opencode_build_argv_minimal_no_model_no_mcp`、`tests/test_f18_coverage_supplement.py::test_opencode_build_argv_minimal_only_binary_name`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-004

### 关联需求

FR-017 AC-2 · INT-013 · §Interface Contract OpenCodeAdapter.build_argv McpDegradation · Feature Design Test Inventory T05

### 测试目标

验证当 `DispatchSpec.mcp_config` 非 None 时，`OpenCodeAdapter.build_argv` 触发 v1 降级：argv 不含任何 mcp 相关 flag；`McpDegradation.toast_pushed == True`；UI 可经 toast 读取 "OpenCode MCP 延后 v1.1" 一类降级提示。

### 前置条件

- `.venv` 激活；`harness.adapter.opencode.hooks.McpDegradation` 可观测 `toast_pushed` 状态
- 构造 DispatchSpec `mcp_config="/tmp/mcp.json"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `adapter = OpenCodeAdapter()`；注入 fresh `McpDegradation` 实例 | 就绪 |
| 2 | 构造 `DispatchSpec(argv=["opencode"], ..., mcp_config="/tmp/mcp.json")` | spec 成功 |
| 3 | `argv = adapter.build_argv(spec)` | 返回 list |
| 4 | 断言 `"--mcp-config" not in argv`、`"--strict-mcp-config" not in argv`（FR-017 AC-2 降级） | True |
| 5 | 断言 `adapter.mcp_degrader.toast_pushed == True` 或等效 messages 非空 | True |
| 6 | 断言 toast message 含 "MCP" 或等效降级语义关键词 | True |

### 验证点

- mcp_config 非 None 仅作"触发信号"，flag 不被透传
- 降级 toast 被累积、可供 UI 经 IAPI-001 `/ws/anomaly` 拉取
- 与 CON-009 v1 scope 对齐

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_protocol.py::test_t05_opencode_build_argv_drops_mcp_and_pushes_toast`、`tests/test_f18_coverage_supplement.py::test_opencode_build_argv_mcp_drops_flag_and_toasts`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-005

### 关联需求

FR-008 AC-1 · IFR-001 · §Interface Contract spawn · Feature Design Test Inventory T06

### 测试目标

验证 `ClaudeCodeAdapter.spawn(DispatchSpec)` 在 CLI 二进制可寻（mock `shutil.which="/usr/bin/claude"`）的情况下返回 `TicketProcess { ticket_id, pid, pty_handle_id, started_at }`，argv 不含 `-p`，PtyWorker 线程已启动并向 byte_queue 推字节。

### 前置条件

- `.venv` 激活
- monkeypatch `shutil.which` 返回 `/usr/bin/claude`；注入 `FakePty` / `FakePtyWorker` 替身观测 argv

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | monkeypatch `shutil.which` | 覆盖成功 |
| 2 | `adapter.spawn(spec)` | 返回 `TicketProcess` |
| 3 | 断言 `ticket.pid > 0`（或替身返回的标识符非 None） | True |
| 4 | 断言 `ticket.ticket_id` 非空字符串 | True |
| 5 | 断言替身 PTY 接收的 argv 首元素 `== "claude"` 且 `"-p" not in argv` | True |
| 6 | 断言 byte_queue（`proc.byte_queue`）对象存在且可消费 | True |

### 验证点

- 接口契约 postcondition 完整：4 字段齐全
- 交互模式（argv 不含 `-p`）贯穿到 spawn 层
- PtyWorker 激活链路被触发（byte_queue 已挂）

### 后置检查

- 替身 PTY 关闭；无残留子进程

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_spawn.py::test_t06_spawn_returns_ticket_process_without_dash_p`、`tests/integration/test_f18_pty_real_subprocess.py::test_claude_adapter_spawn_posix_factory_with_real_cat`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-006

### 关联需求

FR-008 error-path · ATS Err-B · §Interface Contract spawn `SpawnError("Claude CLI not found")` · Feature Design Test Inventory T07

### 测试目标

验证 `ClaudeCodeAdapter.spawn` 在 `shutil.which("claude")` 返 None 时抛 `SpawnError`，message 含 "Claude CLI not found"；不 fork pty、不创建 worker。

### 前置条件

- monkeypatch `shutil.which("claude")` 返回 None

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | monkeypatch `shutil.which` → None | 覆盖成功 |
| 2 | 调 `adapter.spawn(spec)` | 抛 `SpawnError` |
| 3 | 断言 exception message 含 "Claude CLI not found" 或等效语义 | True |
| 4 | 断言未创建任何 PtyWorker / 子进程（替身观测 spawn_count == 0） | True |

### 验证点

- CLI 缺失 → 显式错误（非挂死）
- 错误消息可被 UI 以 `skill_error` 渲染
- 防早期资源泄漏

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_spawn.py::test_t07_spawn_raises_when_cli_missing`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-007

### 关联需求

ATS Err-J · FR-046 skill_error 分类 · §Interface Contract detect_anomaly · Feature Design Test Inventory T08

### 测试目标

验证 `ClaudeCodeAdapter.detect_anomaly(events)` 能在 stderr 或 system 事件含 `"not authenticated"` 时返回 `AnomalyInfo(cls="skill_error", ...)`，不误判为 `context_overflow` 或 `network`。

### 前置条件

- 构造 `StreamEvent(kind="system", payload={"text":"not authenticated..."})` 或 stderr 等效事件

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造含"not authenticated"子串的事件列表 | 就绪 |
| 2 | `info = adapter.detect_anomaly(events)` | 返回 `AnomalyInfo` |
| 3 | 断言 `info.cls == "skill_error"` | True |
| 4 | 断言 `info.cls not in ("context_overflow","rate_limit","network","timeout")` | True |

### 验证点

- auth 错误被正确分类
- 与其他异常分类不重叠

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_spawn.py::test_t08_detect_anomaly_classifies_not_authenticated_as_skill_error`、`tests/test_f18_coverage_supplement.py::test_claude_detect_anomaly_all_classifications`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-008

### 关联需求

FR-009 AC-1 · §Design Alignment seq msg#6 · §Interface Contract extract_hil · Feature Design Test Inventory T09

### 测试目标

验证 `HilExtractor.extract(event)` 在 `event.kind="tool_use"` 且 `payload.name="AskUserQuestion"` 的典型结构下返回 1 个 `HilQuestion(kind="single_select")`，options 由 payload 的 `options[*].label` 正确映射。

### 前置条件

- 构造合法 tool_use StreamEvent：
  `{name:"AskUserQuestion", input:{questions:[{header:"A", question:"B", options:[{label:"x"}], multiSelect:false, allowFreeformInput:false}]}}`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 StreamEvent | 就绪 |
| 2 | `qs = extractor.extract(event)` | 返回 `list[HilQuestion]` 长度 1 |
| 3 | 断言 `qs[0].kind == "single_select"` | True |
| 4 | 断言 `qs[0].options[0].label == "x"` | True |
| 5 | 断言 `qs[0].header == "A"`、`qs[0].question == "B"` | True |

### 验证点

- tool_use=AskUserQuestion → HIL 事件被捕获
- kind 推导按 FR-010 规则矩阵执行
- 字段规范化完整（header/question/options）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_extractor.py::test_t09_extract_hil_returns_single_select_with_options`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-009

### 关联需求

FR-009 AC-2 · §Interface Contract extract_hil 默认值补齐 · Feature Design Test Inventory T10

### 测试目标

验证缺字段（payload 无 `options`）时 `HilExtractor.extract` 仍返回 1 个 `HilQuestion(options=[], kind="free_text")` 并记 structlog warning（由 `caplog` 捕获）。

### 前置条件

- tool_use payload 无 `options` 字段；`pytest caplog`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造缺 options 的 tool_use StreamEvent | 就绪 |
| 2 | `with caplog.at_level("WARNING"): qs = extractor.extract(event)` | 返回 list 长度 1 |
| 3 | 断言 `qs[0].options == []` | True |
| 4 | 断言 warning 已被记录（`caplog.records` 非空，且消息含 options 关键词） | True |
| 5 | 断言无异常抛出（非 `KeyError`） | True |

### 验证点

- 缺字段补默认、不崩
- warning 路径可观测
- 不破坏下游消费

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_extractor.py::test_t10_extract_hil_missing_options_warns_and_fills_defaults`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-001

### 关联需求

FR-009 SEC BNDRY · IFR-002 SEC BNDRY · §Boundary Conditions · Feature Design Test Inventory T11

### 测试目标

验证 `HookQuestionParser.parse_hook_line` 对 Question `name` 字段 500B 长度的输入截断至 256B（UTF-8 字节边界安全）并附 `…`、不崩、不产生 UTF-8 乱码。

### 前置条件

- 构造 JSON hook line，`payload.name` 为 500 字节的 CJK / ASCII 混合字符串

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `raw = (b'{"channel":"harness-hil","payload":{"name":"<500B>"}}\n')` | 就绪 |
| 2 | `evt = parser.parse_hook_line(raw)` | 返回 `HookEvent` 非 None |
| 3 | 断言 `len(evt.payload["name"].encode("utf-8")) <= 256 + len("…".encode("utf-8"))` | True |
| 4 | 断言 truncated 值可 UTF-8 decode（无 `UnicodeDecodeError`） | True |
| 5 | 断言非 JSON / 非 dict / 缺 channel 路径（另一组输入）返回 None | True |

### 验证点

- 长度边界按 UTF-8 bytes 而非字符数切
- CJK 多字节不被切断生成乱码
- `…` 后缀保留供 UI 识别

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_extractor.py::test_t11_parse_hook_line_truncates_question_name_over_256_bytes`、`tests/test_f18_coverage_supplement.py::test_hook_parser_truncates_long_name_utf8_safe`、`tests/test_f18_coverage_supplement.py::test_hook_parser_truncate_cjk_boundary`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-002

### 关联需求

FR-009 · FR-010 规则矩阵 · §Boundary Conditions HilControlDeriver · Feature Design Test Inventory T12

### 测试目标

验证 `HilControlDeriver.derive` 在 `multi_select=True`、`options=[{label:"a"},{label:"b"}]` 时返回 `"multi_select"`（FR-010 多选分支）。

### 前置条件

- 构造 raw question dict：`{multi_select:True, options:[{"label":"a"},{"label":"b"}], allow_freeform:False}`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `kind = HilControlDeriver().derive(raw)` | 返回字符串 |
| 2 | 断言 `kind == "multi_select"` | True |

### 验证点

- `multi_select=True` 分支优先级正确

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_extractor.py::test_t12_control_deriver_multi_select_when_flag_true`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-003

### 关联需求

FR-009 · FR-010 · §Boundary Conditions HilControlDeriver · Feature Design Test Inventory T13

### 测试目标

验证 `HilControlDeriver.derive` 在 `multi_select=False`、`options=[]`、`allow_freeform=True` 时返回 `"free_text"`（自由文本分支）。

### 前置条件

- 构造 `{multi_select:False, options:[], allow_freeform:True}`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `kind = HilControlDeriver().derive(raw)` | 返回 |
| 2 | 断言 `kind == "free_text"` | True |

### 验证点

- 空 options + freeform=True 正确映射到 free_text

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_extractor.py::test_t13_control_deriver_free_text_when_no_options_and_freeform`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-004

### 关联需求

FR-009 · FR-010 · §Boundary Conditions HilControlDeriver · Feature Design Test Inventory T14

### 测试目标

验证 `HilControlDeriver.derive` 在 `multi_select=False`、`options=[{label:"x"}]`、`allow_freeform=True` 时返回 `"single_select"`（附 "其他…" 分支属于 UI 渲染，由 F21 负责；本层仅断言 kind 不退化）。

### 前置条件

- 构造 `{multi_select:False, options:[{"label":"x"}], allow_freeform:True}`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `kind = HilControlDeriver().derive(raw)` | 返回 |
| 2 | 断言 `kind == "single_select"` | True |

### 验证点

- 单 option + freeform 正确映射
- freeform 标记不丢失（交由 UI 渲染 "其他…"）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_extractor.py::test_t14_control_deriver_single_select_with_freeform_one_option`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-010

### 关联需求

FR-009 · §Design Alignment seq msg#5 · §Interface Contract JsonLinesParser.feed · Feature Design Test Inventory T15

### 测试目标

验证 `JsonLinesParser.feed(chunk)` 能在 chunk 含两条完整 JSON-Lines（以 `\n` 分隔）时返回两个 `StreamEvent`，顺序与行序一致。

### 前置条件

- 构造 `chunk = b'{"type":"tool_use","name":"AskUserQuestion","input":{"questions":[]}}\n{"type":"text","text":"hi"}\n'`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `events = parser.feed(chunk)` | 返回 list 长度 2 |
| 2 | 断言 `events[0].kind == "tool_use"` | True |
| 3 | 断言 `events[1].kind == "text"` | True |
| 4 | 断言 parser 内部 buffer 为空（无半行残留） | True |

### 验证点

- 多行 chunk 一次解析出全部事件
- 半行 buffer 正确 reset

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_stream_parser.py::test_t15_feed_two_complete_lines_returns_two_events`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-005

### 关联需求

FR-009 · §Boundary Conditions JsonLinesParser.feed · Feature Design Test Inventory T16

### 测试目标

验证 `JsonLinesParser.feed` 在 chunk 跨调用拆分一条 JSON-Lines 时，第一次返空 list、半行入 buffer，第二次返回完整事件。

### 前置条件

- `chunk1 = b'{"type":"text",'`、`chunk2 = b'"text":"hi"}\n'`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `r1 = parser.feed(chunk1)` | `r1 == []` |
| 2 | `r2 = parser.feed(chunk2)` | `len(r2) == 1` 且 `r2[0].kind == "text"` |

### 验证点

- 半行 buffer 持续累积
- 完成行触发解析

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_stream_parser.py::test_t16_feed_handles_split_chunk_across_calls`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-011

### 关联需求

ATS Err-D · §Implementation Summary 决策 (3) 非法 JSON warning · Feature Design Test Inventory T17

### 测试目标

验证 `JsonLinesParser.feed` 在遇到非法 JSON 行时跳过并记 warning（caplog 捕获），同 chunk 中合法行正常返回；不抛 `JSONDecodeError`。

### 前置条件

- `chunk = b'{invalid json\n{"type":"text","text":"ok"}\n'`；`pytest caplog`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `with caplog.at_level("WARNING"): events = parser.feed(chunk)` | 返回长度 1 |
| 2 | 断言 `events[0].kind == "text"` 且 `events[0].payload["text"] == "ok"` | True |
| 3 | 断言 caplog 含 JSON 解析 warning（关键词 "json" 或 "decode"） | True |
| 4 | 断言无异常抛出 | True |

### 验证点

- 错误流容错：不因一行非法崩全流
- warning 可观测

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_stream_parser.py::test_t17_feed_skips_invalid_json_and_continues`、`tests/test_f18_coverage_supplement.py::test_parser_non_dict_json_is_skipped`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-012

### 关联需求

FR-014 AC-1 · §Design Alignment seq msg#7 · §Interface Contract BannerConflictArbiter · Feature Design Test Inventory T18

### 测试目标

验证 `BannerConflictArbiter.arbitrate(events)` 在同时存在终止横幅（`text` 含 "# 终止"）和未答 AskUserQuestion 时返回 `verdict="hil_waiting"`（HIL 优先）。

### 前置条件

- 构造 `events = [text_event("# 终止"), tool_use_event(AskUserQuestion unanswered)]`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `verdict = BannerConflictArbiter().arbitrate(events)` | 返回 |
| 2 | 断言 `verdict == "hil_waiting"` | True |

### 验证点

- HIL 优先于 terminate banner（FR-014 核心约束）
- verdict 字符串 API 稳定

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_stream_parser.py::test_t18_arbiter_hil_wins_over_terminate_banner`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-006

### 关联需求

FR-014 · §Implementation Summary 10 fixture · Feature Design Test Inventory T19

### 测试目标

验证 `BannerConflictArbiter.arbitrate` 仅有终止横幅、无 HIL 时返回 `"completed"`（非 `hil_waiting`）。

### 前置条件

- `events = [text_event("# 终止")]`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `verdict = BannerConflictArbiter().arbitrate(events)` | 返回 |
| 2 | 断言 `verdict == "completed"` | True |

### 验证点

- 纯 banner 分支正确落 completed
- 未误判 hil_waiting

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_stream_parser.py::test_t19_arbiter_only_banner_yields_completed`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-007

### 关联需求

FR-014 · §Interface Contract BannerConflictArbiter · Feature Design Test Inventory T20

### 测试目标

验证 `BannerConflictArbiter.arbitrate` 仅有未答 HIL、无终止横幅时返回 `"hil_waiting"`。

### 前置条件

- `events = [tool_use_event(AskUserQuestion unanswered)]`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `verdict = BannerConflictArbiter().arbitrate(events)` | 返回 |
| 2 | 断言 `verdict == "hil_waiting"` | True |

### 验证点

- 纯 HIL 分支落 hil_waiting
- 不误判 running / completed

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_stream_parser.py::test_t20_arbiter_only_hil_yields_hil_waiting`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-013

### 关联需求

FR-011 AC-1 · §Design Alignment seq msg#10 · §Interface Contract HilWriteback.write_answer · Feature Design Test Inventory T21

### 测试目标

验证 `HilWriteback.write_answer(HilAnswer)` 在正常路径下调用 `PtyWorker.write` 一次、向 `AuditWriter.append` 写入 `hil_answered` 事件、触发 ticket `classifying` transition。

### 前置条件

- mock `PtyWorker.write` 成功；mock `AuditWriter.append` 可观测
- 构造 `HilAnswer(question_id="q1", selected_labels=["x"], freeform_text=None, answered_at="...")`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `HilWriteback(worker, audit, ticket_repo, ticket_id)` | 就绪 |
| 2 | `wb.write_answer(ans)` | 无异常 |
| 3 | 断言 `worker.write` 被调用一次，bytes 参数非空 | True |
| 4 | 断言 `audit.append` 被调用一次，`event_type=="hil_answered"` | True |
| 5 | 断言 ticket 状态转至 `classifying`（或 ticket_repo.save 参数反映该转换） | True |

### 验证点

- 答案写 pty stdin（同 pid 续跑前提）
- audit 与 state machine 正确联动
- 不重复写、不漏写

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_writeback.py::test_t21_write_answer_pipes_to_pty_and_emits_audit`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-014

### 关联需求

FR-011 AC-2 · §Interface Contract PtyClosedError · Feature Design Test Inventory T22

### 测试目标

验证 `HilWriteback.write_answer` 在 `PtyWorker.write` 抛 `PtyClosedError` 时，ticket 被标记 `failed` 且 `HilAnswer` 被保留（便于重放）。

### 前置条件

- mock `PtyWorker.write` → 抛 `PtyClosedError`
- mock ticket_repo 可观测 `ticket.hil.answers` 字段

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `HilWriteback` 并调 `write_answer(ans)` | 抛 `PtyClosedError` 或内部捕获转状态 |
| 2 | 断言最终 ticket.status 为 `failed`（或保存调用参数反映） | True |
| 3 | 断言 `ticket.hil.answers` 含提交的 `HilAnswer`（保留未丢失） | True |

### 验证点

- 崩溃路径答案不丢失
- 错误状态转换正确

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_writeback.py::test_t22_write_answer_preserves_answer_when_pty_closed`、`tests/test_f18_coverage_supplement.py::test_writeback_pty_closed_with_repo_none_still_raises`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-002

### 关联需求

FR-011 SEC · ATS §2.1 C FR-011 备注"命令注入防护" · §Interface Contract EscapeError · Feature Design Test Inventory T23

### 测试目标

验证 `HilWriteback.write_answer` 在 `HilAnswer.freeform_text` 含非法 ASCII 控制字符（如 `\x03` SIGINT）时抛 `EscapeError`，`PtyWorker.write` **未被调用**（命令注入防线）。

### 前置条件

- 构造 `HilAnswer(freeform_text="hello\x03world", ...)`
- mock `PtyWorker.write` 可观测调用计数

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `wb.write_answer(ans)` | 抛 `EscapeError` |
| 2 | 断言 `worker.write.call_count == 0` | True |
| 3 | 断言异常 message 含 "control" 或等效违规关键词 | True |
| 4 | 对照：`freeform_text="hello\tworld"`（白名单 `\n\r\t`）不抛异常 | True |

### 验证点

- 黑名单外的控制字符被早期拒绝
- 白名单 `\n\r\t` 允许（不 false positive）
- 攻击面不触达 pty stdin

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_writeback.py::test_t23_write_answer_rejects_control_chars`、`tests/test_f18_coverage_supplement.py::test_writeback_freeform_with_whitespace_tabs_allowed`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-015

### 关联需求

FR-012 AC-1 · IFR-002 · §Interface Contract OpenCodeAdapter.ensure_hooks · Feature Design Test Inventory T24

### 测试目标

验证 `OpenCodeAdapter.ensure_hooks(IsolatedPaths)` 在合法隔离 `paths.cwd` 下：写入 `<paths.cwd>/.opencode/hooks.json`，文件权限为 `0o600`，内容含 `"name":"Question"` 与 `"channel":"harness-hil"`。

### 前置条件

- `tmp_path` 提供 `wd = tmp/.harness-workdir/r1`
- `IsolatedPaths(cwd=str(wd), ...)`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 adapter 与 IsolatedPaths | 就绪 |
| 2 | `hooks_path = adapter.ensure_hooks(paths)` | 返回 `Path` |
| 3 | 断言 `hooks_path.exists()` 且 `hooks_path.is_file()` | True |
| 4 | 断言 `oct(hooks_path.stat().st_mode)[-3:] == "600"` | True |
| 5 | `data = json.loads(hooks_path.read_text())`；断言含 `onToolCall`/`match`/`name="Question"` 层级 | True |
| 6 | 断言 JSON 某层含 `"channel":"harness-hil"` | True |

### 验证点

- 文件 0o600 权限（防其他用户读取）
- hooks schema 与 IFR-002 约定一致
- 路径严格落在 `<cwd>/.opencode/`

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_opencode_hooks.py::test_t24_ensure_hooks_writes_secure_file`、`tests/integration/test_f18_real_fs_hooks.py::test_real_fs_ensure_hooks_writes_complete_hooks_json`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-003

### 关联需求

FR-012 AC-2 · IFR-002 SEC · §Interface Contract ensure_hooks Raises InvalidIsolationError · Feature Design Test Inventory T25

### 测试目标

验证 `OpenCodeAdapter.ensure_hooks` 当 `<cwd>/.opencode` 是指向 `/etc` 的 symlink 时抛 `InvalidIsolationError`，不向 `/etc` 写入 `hooks.json`；`Path.resolve()` 后仍需位于 `<cwd>` 子树（目录逃逸防护）。

### 前置条件

- 构造 `<wd>/.opencode` symlink → `/etc`（或其他 `<wd>` 之外目录）；`pytest tmp_path`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `wd/.opencode -> /etc` symlink | 成功 |
| 2 | 调 `adapter.ensure_hooks(IsolatedPaths(cwd=str(wd), ...))` | 抛 `InvalidIsolationError` |
| 3 | 断言 `/etc/hooks.json` **未被写入** | True |
| 4 | 断言异常 message 含路径 / 逃逸关键词 | True |

### 验证点

- symlink resolve 后路径守卫生效
- 第三方路径不被污染
- 异常消息可辨认攻击意图

### 后置检查

- 清理 tmp_path；`/etc` 未被触碰

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_opencode_hooks.py::test_t25_ensure_hooks_rejects_symlink_escape`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-016

### 关联需求

FR-012 AC-2 · IFR-002 · §Interface Contract spawn HookRegistrationError · Feature Design Test Inventory T26

### 测试目标

验证 `OpenCodeAdapter.spawn` 当 mock 的 OpenCode 版本检测返回 `< 0.3.0`（hooks 不支持）时抛 `HookRegistrationError`，message 含"升级 OpenCode"或等效提示。

### 前置条件

- monkeypatch `VersionCheck.parse_opencode_version` 返回 `"0.2.0"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | monkeypatch 版本检测 → `0.2.0` | 就绪 |
| 2 | `adapter.spawn(spec)` | 抛 `HookRegistrationError` |
| 3 | 断言 message 含 "OpenCode" + "升级/upgrade" 或等效语义 | True |
| 4 | 断言未 fork pty（替身观测 0 spawn） | True |

### 验证点

- 版本不兼容 → 显式错误
- 提示可被 UI 渲染为升级引导
- 不静默降级（避免 skill 运行期 hooks 失效）

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_opencode_hooks.py::test_t26_spawn_raises_when_opencode_version_too_old`、`tests/test_f18_coverage_supplement.py::test_opencode_spawn_raises_when_too_old`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-017

### 关联需求

FR-015 · FR-018 · NFR-014 · §Interface Contract ToolAdapter Protocol · Feature Design Test Inventory T27

### 测试目标

验证当 `class MockProvider` 实现 `ToolAdapter` 全部 6 方法（`build_argv / spawn / extract_hil / parse_result / detect_anomaly / supports`）时，`isinstance(MockProvider(), ToolAdapter)` 在 `@runtime_checkable` 下返回 `True`；同时 `mypy --strict harness/adapter/` 退出码 0。

### 前置条件

- `mypy>=1.11`；`harness.adapter.protocol.ToolAdapter` 带 `@runtime_checkable`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 定义 `class MockProvider` 实现 6 方法（签名与 Protocol 一致） | 类定义成功 |
| 2 | 断言 `isinstance(MockProvider(), ToolAdapter) is True` | True |
| 3 | 运行 `mypy --strict harness/adapter/` | 退出码 0，无 error |
| 4 | 断言 `ClaudeCodeAdapter` / `OpenCodeAdapter` 也 `isinstance(..., ToolAdapter) is True` | True |

### 验证点

- Protocol 运行时可检测
- 新 provider 实现 Protocol 即可被 orchestrator 注册（FR-018 扩展性）
- mypy `--strict` 静态检查通过（NFR-014 度量）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_protocol.py::test_t27_runtime_checkable_protocol_accepts_full_provider`（isinstance 断言）；`mypy --strict harness/adapter/`（env-guide §3 静态分析命令）
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-019

### 关联需求

FR-015 error-path · FR-018 error-path · NFR-014 · §Interface Contract Protocol 运行时检查 · Feature Design Test Inventory T28

### 测试目标

验证当 `class Broken` 仅实现 Protocol 的 1 个方法（如仅 `build_argv`）时，`isinstance(Broken(), ToolAdapter) is False`；`mypy --strict` 在对等 fixture 上报 error（方法缺失）。

### 前置条件

- `class Broken: def build_argv(self, spec): ...`（缺其余 5 方法）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 定义 `Broken` | 类定义成功 |
| 2 | 断言 `isinstance(Broken(), ToolAdapter) is False` | True |
| 3 | 在对应 mypy fixture 上跑 `mypy --strict` | 命中 missing-method error |

### 验证点

- runtime_checkable 不误放行
- 静态 + 运行时双层防护

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_protocol.py::test_t28_runtime_checkable_protocol_rejects_partial_provider`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-020

### 关联需求

FR-015 · §Interface Contract CapabilityFlags · Feature Design §4.3.2

### 测试目标

验证 `CapabilityFlags` enum 含 `MCP_STRICT` 与 `HOOKS` 成员；`ClaudeCodeAdapter.supports(MCP_STRICT) is True` / `supports(HOOKS) is False`；`OpenCodeAdapter.supports(MCP_STRICT) is False` / `supports(HOOKS) is True`（FR-015 `supports` 方法返回稳定布尔）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `from harness.adapter.protocol import CapabilityFlags` | import 成功 |
| 2 | 断言 `CapabilityFlags.MCP_STRICT` 与 `CapabilityFlags.HOOKS` 存在 | True |
| 3 | `ClaudeCodeAdapter().supports(CapabilityFlags.MCP_STRICT)` | True |
| 4 | `ClaudeCodeAdapter().supports(CapabilityFlags.HOOKS)` | False |
| 5 | `OpenCodeAdapter().supports(CapabilityFlags.MCP_STRICT)` | False |
| 6 | `OpenCodeAdapter().supports(CapabilityFlags.HOOKS)` | True |

### 验证点

- enum 成员稳定
- 两实现的 capability 声明互补
- 为未来 provider 注册提供分派依据

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_adapter_protocol.py::test_capability_flags_enum_has_required_members`、`tests/test_f18_coverage_supplement.py::test_claude_supports_flags`、`tests/test_f18_coverage_supplement.py::test_opencode_supports_flags`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-021

### 关联需求

IFR-001 · FR-008 · §Interface Contract PtyWorker.start/close · ATS INT-001

### 测试目标

在真实 POSIX pty 上用 `cat` 子进程进行 round-trip：`PosixPty` + `PtyWorker` 能启动、经 pty stdin 写入 bytes、从 byte_queue 回读相同 bytes、`close()` 幂等；无需 `claude` CLI 即完成 pty 基础能力验证。

### 前置条件

- 平台为 POSIX（Linux/macOS）；`/bin/cat` 可寻
- `asyncio` event loop

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `pty = PosixPty(argv=["cat"], env={...}, cwd=str(tmp))`；启动 PtyWorker | 子进程启动 |
| 2 | `worker.write(b"hello\n")` | 无异常 |
| 3 | 从 `proc.byte_queue.get()` 读取；断言含 `b"hello"` | True |
| 4 | `worker.close()`；断言 `byte_queue` 收到 sentinel `None` | True |
| 5 | 再次 `worker.close()`（幂等） | 无异常 |

### 验证点

- pty 双向管道可用
- Worker threading + asyncio bridge 正确
- close 幂等

### 后置检查

- `cat` 子进程被 SIGTERM 回收；`tmp` 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f18_pty_real_subprocess.py::test_posix_pty_roundtrip_via_cat_echo`、`::test_worker_reader_thread_pushes_real_cat_bytes_to_queue`、`::test_worker_close_sends_sentinel_on_queue`、`tests/test_f18_coverage_supplement.py::test_worker_close_is_idempotent`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-022

### 关联需求

IAPI-009 · FR-009 · FR-011 · §Design Alignment seq msg#8/13 · Feature Design Test Inventory T32

### 测试目标

验证 `HilEventBus.publish_opened(HilQuestionOpened)` 触发 `AuditWriter.append` 一次（`event_type="hil_captured"`）并经注入 callable broadcast 到 WebSocket 层；`publish_answered(HilAnswerAck)` 同理对 `event_type="hil_answered"`。

### 前置条件

- mock `AuditWriter`（可观测 append 调用）；mock broadcast callable

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `HilEventBus(ws_broadcast=mock_bcast, audit=mock_audit)` | 就绪 |
| 2 | `bus.publish_opened(q)` | 无异常 |
| 3 | 断言 `mock_audit.append.call_count == 1` 且 `event_type="hil_captured"` | True |
| 4 | 断言 `mock_bcast` 被调用一次，payload 含 question 信息 | True |
| 5 | `bus.publish_answered(a)`；断言 `event_type="hil_answered"` append | True |
| 6 | `mock_audit=None` 分支：仅 broadcast；`mock_bcast=None` 分支：仅 audit（fallback 行为） | True |

### 验证点

- IAPI-009 契约（AuditWriter.append 被正确调用）
- IAPI-001 WebSocket 广播解耦（不直接持 FastAPI 对象）
- 空依赖分支容忍

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_hil_writeback.py::test_t32_event_bus_publish_opened_appends_audit_and_broadcasts`、`tests/test_f18_coverage_supplement.py::test_event_bus_publish_answered_appends_audit_and_broadcasts`、`::test_event_bus_publish_without_audit_still_broadcasts`、`::test_event_bus_audit_only_path_no_broadcast`
- **Test Type**: Real

---

### 用例编号

ST-PERF-018-001

### 关联需求

NFR-002 · FR-013 PoC 性能代理 · §Implementation Summary 决策 (2)/(3) · Feature Design Test Inventory T31

### 测试目标

验证 `JsonLinesParser.feed` 对 100 条事件 burst（合法 JSON-Lines stream），整体解析 p95 延迟 < 2s；作为 FR-013 HIL PoC 性能代理指标（不依赖真 CLI）。

### 前置条件

- 生成 100 条合法 stream-json 行的合成 fixture

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 生成 `chunks = [json.dumps({...}).encode()+b"\n" for _ in range(100)]`；合并为一条 chunk | 就绪 |
| 2 | 计时 `t0 = perf_counter(); events = parser.feed(big_chunk); t1 = perf_counter()` | events 长度 ≥ 100 |
| 3 | 断言 `(t1 - t0) < 2.0` | True |
| 4 | 运行多次（≥10 次）取 p95，断言 p95 < 2s | True |

### 验证点

- NFR-002 p95 < 2s 端到端 proxy 指标
- 增量解析不阻塞

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_pty_perf.py::test_t31_parser_p95_latency_for_100_events_burst`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-004

### 关联需求

FR-009 SEC · §Interface Contract parser events · Feature Design §Implementation Summary (3)

### 测试目标

验证 `JsonLinesParser` 在空行 / 非 dict JSON / 未知 kind / 非法 seq 等若干恶意或异常输入下不崩，按规范（空行跳过 / 非 dict 警告并跳过 / 未知 kind 降级 system / seq 非 int 回退 0）处理，避免 DoS。

### 前置条件

- 构造混合输入：`b"\n\n{\"type\":\"text\",\"text\":\"ok\"}\n[1,2,3]\n{\"type\":\"strange\"}\n{\"type\":\"text\",\"seq\":\"abc\"}\n"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `with caplog.at_level("WARNING"): events = parser.feed(payload)` | 无异常 |
| 2 | 断言至少 2 条合法 events 被返回（"ok"、未知 kind 降级后的事件） | True |
| 3 | 断言 warning 被记录（`[1,2,3]` / 非 dict） | True |
| 4 | 断言 seq 非 int 的事件 `seq == 0`（回退） | True |

### 验证点

- 多种异常输入的鲁棒性
- warning 可观测
- 无 unhandled exception

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_coverage_supplement.py::test_parser_empty_chunk_returns_empty_list`、`::test_parser_non_dict_json_is_skipped`、`::test_parser_unknown_kind_coerced_to_system`、`::test_parser_seq_non_int_falls_back_to_zero`、`::test_parser_blank_lines_skipped`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-023

### 关联需求

FR-015 · FR-016 · FR-017 · §Interface Contract extract_hil/parse_result/detect_anomaly 跨 provider 一致性

### 测试目标

验证 `OpenCodeAdapter` 在 `extract_hil` / `parse_result` / `detect_anomaly` / `build_argv(model=...)` 场景下行为与 Protocol 一致（代理 shared extractor、拼接 text 事件、若干异常分类、`--model` 透传），与 Claude 实现互换性对齐 FR-018 扩展契约。

### 前置条件

- `.venv` 激活；构造 tool_use / text / system 混合事件

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `OpenCodeAdapter().extract_hil(event)` 与 `ClaudeCodeAdapter().extract_hil(event)` 对同一 tool_use 返回结构一致 list | True |
| 2 | `OpenCodeAdapter().parse_result(events)` 拼接 text 字段为 `result_text`；空 events 返回空对象 | True |
| 3 | `OpenCodeAdapter().detect_anomaly(events)` 对 "rate limited"/"context length"/"EHOSTUNREACH" 等模式分类正确；无匹配返 None | True |
| 4 | `OpenCodeAdapter().build_argv(spec with model="codex-small")` 含 `--model codex-small` | True |

### 验证点

- 跨 provider 行为一致性（FR-018 互换性）
- `supports` 差异不影响基础协议方法

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_coverage_supplement.py::test_opencode_extract_hil_delegates_to_shared_extractor`、`::test_opencode_parse_result_concatenates_text_events`、`::test_opencode_parse_result_empty`、`::test_opencode_detect_anomaly_classifications`、`::test_opencode_build_argv_with_model`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-024

### 关联需求

IFR-001 · §Interface Contract sanitise env 白名单 · ATS §2.1 C FR-008 备注"env 白名单"

### 测试目标

验证 `ClaudeCodeAdapter` 环境 sanitise 仅保留白名单变量（`PATH` / `PYTHONPATH` / `SHELL` / `LANG` / `USER` / `LOGNAME` / `TERM`），其他变量（如恶意注入的 `EVIL_VAR`）在 spawn 前被丢弃。

### 前置条件

- 构造 `spec.env={"PATH":"/x","EVIL_VAR":"bad","HOME_IGNORED":"y",...}`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 调 `sanitise` 等效 API（observable via spawn argv+env replay 或直接测工具函数） | 返回 dict |
| 2 | 断言返回 dict 含 `PATH` | True |
| 3 | 断言返回 dict **不含** `EVIL_VAR` / 任意非白名单 key | True |

### 验证点

- env 白名单严格
- NFR-009 / CON-007 环境清洁前提

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_coverage_supplement.py::test_claude_sanitise_env_only_whitelisted_vars_survive`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-025

### 关联需求

FR-018 AC · §Interface Contract 向后兼容

### 测试目标

验证 `OpenCodeAdapter.parse_hook_line` 委托逻辑 + `HookConfigWriter` 结构写入的向后兼容性：在 raw bytes 合法 JSON 但 name 字段超长时自动截断、缺 channel 时返回 None + warning、非 JSON 时返回 None + warning；既有 `ClaudeCodeAdapter` 不受 OpenCode 专属方法新增影响。

### 前置条件

- 构造多种 raw hook line 输入（合法 / 非 JSON / 缺 channel / 超长 name）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 合法 hook line `parse_hook_line` 返 `HookEvent` | True |
| 2 | 非 JSON 返 None + warning | True |
| 3 | 非 dict JSON 返 None + warning | True |
| 4 | 缺 channel 返 None + warning | True |
| 5 | payload 非 dict 默认空 dict、不崩 | True |
| 6 | 导入 `ClaudeCodeAdapter` 不需要 `HookConfigWriter`（OpenCode 专属方法增删不影响 Claude 实现） | True |

### 验证点

- FR-018 向后兼容（新 provider 方法新增不破坏既有）
- 错误分支完整覆盖

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_coverage_supplement.py::test_hook_parser_returns_none_on_invalid_json`、`::test_hook_parser_returns_none_on_non_dict_json`、`::test_hook_parser_returns_none_when_channel_missing`、`::test_hook_parser_payload_non_dict_defaults_to_empty`、`::test_hook_config_writer_writes_expected_structure`、`::test_opencode_parse_hook_line_delegates`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-026

### 关联需求

NFR-014 · §Interface Contract ToolAdapter Protocol mypy --strict

### 测试目标

验证执行 `mypy --strict harness/adapter/`（env-guide §3 静态分析命令）退出码为 0，无 error 级 diagnostic；即 ToolAdapter / ClaudeCodeAdapter / OpenCodeAdapter 全包静态类型严格通过。

### 前置条件

- `mypy>=1.11`；`.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 运行 `mypy --strict harness/adapter/` | 退出码 0 |
| 2 | 断言 stdout / stderr 无 `error:` 级 diagnostic | True |

### 验证点

- NFR-014 mypy 静态严格关卡
- Protocol + 实现两侧都无类型漂移

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `mypy --strict harness/adapter/`（env-guide §3）
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-018

### 关联需求

IFR-001 · FR-008 · FR-011 · ATS INT-001 · Feature Design Test Inventory T29

### 测试目标

【MANUAL_TEST_REQUIRED — external-action】在真实 `claude` CLI 下触发一次 HIL round-trip：用户启动 `claude` 会话并以能触发 `AskUserQuestion` 的 prompt 驱动；Harness 观测 `TicketProcess.pid` 在 round-trip 前后不变、timeline 至少含 2 条 tool_use 事件；CLI 缺失 / 未登录时硬失败（不静默 skip）。

### 前置条件

- 用户已执行 `claude login` 并完成 OAuth 凭证绑定；`which claude` 非空
- 用户以真实 prompt（e.g., `"Please ask a multiple-choice AskUserQuestion then proceed"`）驱动 round-trip

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `source .venv/bin/activate` | 环境就绪 |
| 2 | 用户以真实 prompt 启动交互 claude；同时跑 `pytest tests/integration/test_f18_real_cli.py::test_t29_real_claude_hil_round_trip -q -m real_cli --timeout=60` | pytest 执行 |
| 3 | Pytest 断言 `proc.pid == initial_pid`（同 pid 续跑） | True |
| 4 | Pytest 断言 `len(tool_use_events) >= 2`（初始 + 答后） | True |
| 5 | 测试 PASS 则视为 MANUAL-PASS | PASS |

### 验证点

- 真 CLI round-trip 同 pid（pty stdin 写回）
- AskUserQuestion 可被 stream-json 捕获

### 后置检查

- PTY 子进程被 worker.close() 回收
- 清理 tmp_path

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: No
- **手动测试原因**: external-action（需用户提交真实 prompt 驱动 HIL；headless pytest 在无 prompt 下 claude CLI 不会自发产生 AskUserQuestion；此外真 CLI 需用户账号凭证）
- **测试引用**: `tests/integration/test_f18_real_cli.py::test_t29_real_claude_hil_round_trip`（`@pytest.mark.real_cli`）
- **Test Type**: Real

---

### 用例编号

ST-PERF-018-002

### 关联需求

FR-013 HIL PoC gate · ATS INT-001 · Feature Design Test Inventory T30

### 测试目标

【MANUAL_TEST_REQUIRED — external-action】FR-013 20-round HIL PoC gate：在真实 `claude` CLI 下跑 20 轮 HIL round-trip；成功率 ≥ 95%（≥ 19/20）；结果归档至 `docs/poc/<date>-hil-poc.md`；成功率 < 95% 则冻结 HIL 相关 FR 并上报用户。

### 前置条件

- 用户已执行 `claude login`；`which claude` 非空
- 用户以稳定 prompt 触发每轮 AskUserQuestion

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 用户准备 prompt，使每轮启动都能稳定触发 AskUserQuestion | 就绪 |
| 2 | 跑 `pytest tests/integration/test_f18_real_cli.py::test_t30_hil_poc_20_round_success_rate_at_least_95_percent -q -m real_cli --timeout=600` | 20 轮执行 |
| 3 | 断言 `successes >= 19`（成功率 ≥ 95%） | True |
| 4 | 断言 `docs/poc/<date>-hil-poc.md` 被写入并含 successes / rate / 失败摘要 | True |
| 5 | 若 `successes < 19`：状态转 BLOCKED 并冻结 HIL FR | 上报 |

### 验证点

- 20 轮 PoC 成功率 ≥ 95%
- PoC 报告归档
- 冻结条件可触发（设计第二路径）

### 后置检查

- 每轮 PTY 子进程清理（worker.close）
- 报告文件提交至 `docs/poc/`

### 元数据

- **优先级**: Critical
- **类别**: performance
- **已自动化**: No
- **手动测试原因**: external-action（同 T29：需用户驱动 prompt + 有效 claude 账号；headless 无 prompt 不触发 HIL）
- **测试引用**: `tests/integration/test_f18_real_cli.py::test_t30_hil_poc_20_round_success_rate_at_least_95_percent`（`@pytest.mark.real_cli`）
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-018-001 | FR-016 AC-1 / IFR-001 / T01 | verification_steps[0] | `tests/test_f18_adapter_protocol.py::test_t01_claude_build_argv_full_required_flag_set` | Real | PASS |
| ST-FUNC-018-002 | FR-016 AC-2 / T02 | verification_steps[0] | `tests/test_f18_adapter_protocol.py::test_t02_claude_build_argv_includes_model_when_set`、`tests/test_f18_coverage_supplement.py::test_claude_build_argv_with_model_and_mcp` | Real | PASS |
| ST-SEC-018-001 | FR-016 / IFR-001 SEC / NFR-009 / T03 | verification_steps[0] | `tests/test_f18_adapter_protocol.py::test_t03_claude_build_argv_rejects_non_isolated_plugin_dir` | Real | PASS |
| ST-FUNC-018-003 | FR-017 AC-1 / IFR-002 / T04 | verification_steps[5] | `tests/test_f18_adapter_protocol.py::test_t04_opencode_build_argv_minimal_no_model_no_mcp`、`tests/test_f18_coverage_supplement.py::test_opencode_build_argv_minimal_only_binary_name` | Real | PASS |
| ST-FUNC-018-004 | FR-017 AC-2 / INT-013 / T05 | verification_steps[5] | `tests/test_f18_adapter_protocol.py::test_t05_opencode_build_argv_drops_mcp_and_pushes_toast`、`tests/test_f18_coverage_supplement.py::test_opencode_build_argv_mcp_drops_flag_and_toasts` | Real | PASS |
| ST-FUNC-018-005 | FR-008 / IFR-001 / T06 | verification_steps[0] | `tests/test_f18_adapter_spawn.py::test_t06_spawn_returns_ticket_process_without_dash_p`、`tests/integration/test_f18_pty_real_subprocess.py::test_claude_adapter_spawn_posix_factory_with_real_cat` | Real | PASS |
| ST-FUNC-018-006 | FR-008 error / Err-B / T07 | verification_steps[0] | `tests/test_f18_adapter_spawn.py::test_t07_spawn_raises_when_cli_missing` | Real | PASS |
| ST-FUNC-018-007 | ATS Err-J / FR-046 / T08 | verification_steps[0] | `tests/test_f18_adapter_spawn.py::test_t08_detect_anomaly_classifies_not_authenticated_as_skill_error`、`tests/test_f18_coverage_supplement.py::test_claude_detect_anomaly_all_classifications` | Real | PASS |
| ST-FUNC-018-008 | FR-009 AC-1 / T09 | verification_steps[1] | `tests/test_f18_hil_extractor.py::test_t09_extract_hil_returns_single_select_with_options` | Real | PASS |
| ST-FUNC-018-009 | FR-009 AC-2 / T10 | verification_steps[1] | `tests/test_f18_hil_extractor.py::test_t10_extract_hil_missing_options_warns_and_fills_defaults` | Real | PASS |
| ST-BNDRY-018-001 | IFR-002 SEC BNDRY / T11 | verification_steps[9] | `tests/test_f18_hil_extractor.py::test_t11_parse_hook_line_truncates_question_name_over_256_bytes`、`tests/test_f18_coverage_supplement.py::test_hook_parser_truncates_long_name_utf8_safe`、`::test_hook_parser_truncate_cjk_boundary` | Real | PASS |
| ST-BNDRY-018-002 | FR-010 / T12 | verification_steps[1] | `tests/test_f18_hil_extractor.py::test_t12_control_deriver_multi_select_when_flag_true` | Real | PASS |
| ST-BNDRY-018-003 | FR-010 / T13 | verification_steps[1] | `tests/test_f18_hil_extractor.py::test_t13_control_deriver_free_text_when_no_options_and_freeform` | Real | PASS |
| ST-BNDRY-018-004 | FR-010 / T14 | verification_steps[1] | `tests/test_f18_hil_extractor.py::test_t14_control_deriver_single_select_with_freeform_one_option` | Real | PASS |
| ST-FUNC-018-010 | FR-009 / T15 | verification_steps[1] | `tests/test_f18_stream_parser.py::test_t15_feed_two_complete_lines_returns_two_events` | Real | PASS |
| ST-BNDRY-018-005 | FR-009 / T16 | verification_steps[1] | `tests/test_f18_stream_parser.py::test_t16_feed_handles_split_chunk_across_calls` | Real | PASS |
| ST-FUNC-018-011 | ATS Err-D / T17 | verification_steps[1] | `tests/test_f18_stream_parser.py::test_t17_feed_skips_invalid_json_and_continues` | Real | PASS |
| ST-FUNC-018-012 | FR-014 AC-1 / T18 | verification_steps[3] | `tests/test_f18_stream_parser.py::test_t18_arbiter_hil_wins_over_terminate_banner` | Real | PASS |
| ST-BNDRY-018-006 | FR-014 / T19 | verification_steps[3] | `tests/test_f18_stream_parser.py::test_t19_arbiter_only_banner_yields_completed` | Real | PASS |
| ST-BNDRY-018-007 | FR-014 / T20 | verification_steps[3] | `tests/test_f18_stream_parser.py::test_t20_arbiter_only_hil_yields_hil_waiting` | Real | PASS |
| ST-FUNC-018-013 | FR-011 AC-1 / T21 | verification_steps[2] | `tests/test_f18_hil_writeback.py::test_t21_write_answer_pipes_to_pty_and_emits_audit` | Real | PASS |
| ST-FUNC-018-014 | FR-011 AC-2 / T22 | verification_steps[2] | `tests/test_f18_hil_writeback.py::test_t22_write_answer_preserves_answer_when_pty_closed`、`tests/test_f18_coverage_supplement.py::test_writeback_pty_closed_with_repo_none_still_raises` | Real | PASS |
| ST-SEC-018-002 | FR-011 SEC / T23 | verification_steps[2] | `tests/test_f18_hil_writeback.py::test_t23_write_answer_rejects_control_chars`、`tests/test_f18_coverage_supplement.py::test_writeback_freeform_with_whitespace_tabs_allowed` | Real | PASS |
| ST-FUNC-018-015 | FR-012 AC-1 / IFR-002 / T24 | verification_steps[4] | `tests/test_f18_opencode_hooks.py::test_t24_ensure_hooks_writes_secure_file`、`tests/integration/test_f18_real_fs_hooks.py::test_real_fs_ensure_hooks_writes_complete_hooks_json` | Real | PASS |
| ST-SEC-018-003 | FR-012 AC-2 / IFR-002 SEC / T25 | verification_steps[4] | `tests/test_f18_opencode_hooks.py::test_t25_ensure_hooks_rejects_symlink_escape` | Real | PASS |
| ST-FUNC-018-016 | FR-012 AC-2 / T26 | verification_steps[4] | `tests/test_f18_opencode_hooks.py::test_t26_spawn_raises_when_opencode_version_too_old`、`tests/test_f18_coverage_supplement.py::test_opencode_spawn_raises_when_too_old` | Real | PASS |
| ST-FUNC-018-017 | FR-015 / FR-018 / NFR-014 / T27 | verification_steps[8] | `tests/test_f18_adapter_protocol.py::test_t27_runtime_checkable_protocol_accepts_full_provider` · `mypy --strict harness/adapter/` | Real | PASS |
| ST-FUNC-018-019 | FR-015 error / FR-018 error / NFR-014 / T28 | verification_steps[8] | `tests/test_f18_adapter_protocol.py::test_t28_runtime_checkable_protocol_rejects_partial_provider` | Real | PASS |
| ST-FUNC-018-020 | FR-015 / CapabilityFlags | verification_steps[8] | `tests/test_f18_adapter_protocol.py::test_capability_flags_enum_has_required_members`、`tests/test_f18_coverage_supplement.py::test_claude_supports_flags`、`::test_opencode_supports_flags` | Real | PASS |
| ST-FUNC-018-021 | IFR-001 / FR-008 / PTY basics | verification_steps[2] | `tests/integration/test_f18_pty_real_subprocess.py::test_posix_pty_roundtrip_via_cat_echo`、`::test_worker_reader_thread_pushes_real_cat_bytes_to_queue`、`::test_worker_close_sends_sentinel_on_queue`、`tests/test_f18_coverage_supplement.py::test_worker_close_is_idempotent` | Real | PASS |
| ST-FUNC-018-022 | IAPI-009 / FR-009 / FR-011 / T32 | verification_steps[1] | `tests/test_f18_hil_writeback.py::test_t32_event_bus_publish_opened_appends_audit_and_broadcasts`、`tests/test_f18_coverage_supplement.py::test_event_bus_publish_answered_appends_audit_and_broadcasts`、`::test_event_bus_publish_without_audit_still_broadcasts`、`::test_event_bus_audit_only_path_no_broadcast` | Real | PASS |
| ST-PERF-018-001 | NFR-002 / FR-013 PoC 代理 / T31 | verification_steps[7] | `tests/test_f18_pty_perf.py::test_t31_parser_p95_latency_for_100_events_burst` | Real | PASS |
| ST-SEC-018-004 | FR-009 SEC / parser robustness | verification_steps[1] | `tests/test_f18_coverage_supplement.py::test_parser_empty_chunk_returns_empty_list`、`::test_parser_non_dict_json_is_skipped`、`::test_parser_unknown_kind_coerced_to_system`、`::test_parser_seq_non_int_falls_back_to_zero`、`::test_parser_blank_lines_skipped` | Real | PASS |
| ST-FUNC-018-023 | FR-015 / FR-017 / FR-018 / provider consistency | verification_steps[6] | `tests/test_f18_coverage_supplement.py::test_opencode_extract_hil_delegates_to_shared_extractor`、`::test_opencode_parse_result_concatenates_text_events`、`::test_opencode_parse_result_empty`、`::test_opencode_detect_anomaly_classifications`、`::test_opencode_build_argv_with_model` | Real | PASS |
| ST-FUNC-018-024 | IFR-001 / env 白名单 | verification_steps[0] | `tests/test_f18_coverage_supplement.py::test_claude_sanitise_env_only_whitelisted_vars_survive` | Real | PASS |
| ST-FUNC-018-025 | FR-018 / 向后兼容 | verification_steps[6] | `tests/test_f18_coverage_supplement.py::test_hook_parser_returns_none_on_invalid_json`、`::test_hook_parser_returns_none_on_non_dict_json`、`::test_hook_parser_returns_none_when_channel_missing`、`::test_hook_parser_payload_non_dict_defaults_to_empty`、`::test_hook_config_writer_writes_expected_structure`、`::test_opencode_parse_hook_line_delegates` | Real | PASS |
| ST-FUNC-018-026 | NFR-014 / mypy --strict | verification_steps[8] | `mypy --strict harness/adapter/`（env-guide §3） | Real | PASS |
| ST-FUNC-018-018 | IFR-001 / FR-008 / FR-011 / T29 | verification_steps[7] | `tests/integration/test_f18_real_cli.py::test_t29_real_claude_hil_round_trip`（`@pytest.mark.real_cli`） | Real | PENDING-MANUAL |
| ST-PERF-018-002 | FR-013 HIL PoC gate / T30 | verification_steps[7] | `tests/integration/test_f18_real_cli.py::test_t30_hil_poc_20_round_success_rate_at_least_95_percent`（`@pytest.mark.real_cli`） | Real | PENDING-MANUAL |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

---

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 39 |
| Passed | 37 |
| Failed | 0 |
| Pending | 2 |

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.
> 2 Pending cases are手动（`已自动化: No`）：ST-FUNC-018-018 (T29) 与 ST-PERF-018-002 (T30) —— 需用户驱动真实 claude CLI prompt 触发 HIL round-trip；由 dispatcher 以 `[MANUAL_TEST_REQUIRED]` 交付人工 review 闭环。

---

## Manual Test Case Summary

| Metric | Count |
|--------|-------|
| Total Manual Test Cases | 2 |
| Manual Passed (MANUAL-PASS) | 0 |
| Manual Failed (MANUAL-FAIL) | 0 |
| Blocked | 0 |
| Pending (PENDING-MANUAL) | 2 |

> Manual test cases = test cases with `已自动化: No`. Results collected via human review gate after automated execution.
> Any MANUAL-FAIL blocks the feature from being marked `"passing"` — same as automated FAIL.
