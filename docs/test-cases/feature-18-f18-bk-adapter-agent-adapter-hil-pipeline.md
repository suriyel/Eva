# 测试用例集: F18 · Bk-Adapter — Agent Adapter & HIL Pipeline

**Feature ID**: 18
**关联需求**: FR-008, FR-009, FR-011, FR-012, FR-013, FR-015, FR-016, FR-017, FR-018, FR-051, FR-052, FR-053, NFR-014, IFR-001, IFR-002（FR-014 [DEPRECATED Wave 4]，由 SessionEnd hook + tool_use_id queue 自然替代；ATS §2.1 C/D 必须类别 FUNC/BNDRY/SEC/PERF；INT-001 [Wave 4 REWRITE / Wave 4.1 unified Esc-text 默认]；Test Inventory T01–T39 + T-HOOK-SCHEMA-CANARY + Wave 4.1 NEW × 9）
**日期**: 2026-04-27
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明 / Specification Resolution**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则、ATS §3.1 / §5.1 INT-001 / §4 NFR Matrix、Feature Design §Test Inventory（49 行：T01–T39 + T-HOOK-SCHEMA-CANARY + Wave 4.1 NEW × 9）+ §Boundary Conditions + §Interface Contract Postcondition、可观察接口（`harness.adapter.claude.ClaudeCodeAdapter` / `harness.adapter.opencode` / `harness.hil.tui_keys.TuiKeyEncoder` / `harness.hil.hook_mapper.HookEventMapper` / `harness.hil.event_bus.HilEventBus` / `harness.hil.writeback.HilWriteback` / `harness.api.hook` / `harness.api.pty_writer` / `harness.adapter.workdir_artifacts` / `harness.stream.hook_to_stream.HookEventToStreamMapper` 公开 API、HTTP TestClient、POSIX 文件系统观测含 `os.stat().st_mode` 权限位、`hashlib.sha256` 字节守恒、pytest caplog structlog warning 观测、`@pytest.mark.real_cli` 真 `claude` CLI ≥ 2.1.119 行为观测、mypy `--strict` 退出码、subprocess 退出码 + stderr）推导，不阅读实现源码。
> - **Specification resolutions applied from Feature Design §Clarification Addendum (Resolved, user-approved 2026-04-27)**：FR-016 argv 模板冲突已由用户裁决 B（Revise — 重写 §6.1.1 同步 SRS）消化（commit `92538da`）。SRS / 系统设计 §6.1.1 + §4.3.2 / Feature Design §Interface Contract `build_argv` Postcondition 四处文字等值：`["claude", "--dangerously-skip-permissions", "--plugin-dir", <bundle>, "--settings", <isolated.settings.json>, "--setting-sources", "project"]`（含可选 `--model <alias>` 时插在 `--settings <path>` 之后、`--setting-sources project` 之前；len(argv) 严格 8 / 10）。本文档 ST-FUNC-018-001 / ST-FUNC-018-002 / ST-FUNC-018-003 / ST-FUNC-018-004 的 argv 断言以本权威白名单为准。
> - `feature.ui == false` → 本特性无 UI 类别用例；FR-009 捕获的 HIL 事件最终由 F21 `Fe-RunViews` 渲染（独立 ST 承担），本特性覆盖的是**后端事件管道** + argv / hooks 构造契约表面 + TUI 键序协议 + workdir 三件套预置 + audit 闭环。
> - 本特性以 **"No server processes — environment activation only"** 模式运行（env-guide §1 纯 CLI / library 模式 —— `pytest tests/test_f18_w4_*.py tests/integration/test_f18_*.py -m "not real_cli"`），无需启动 `api` / `ui-dev` 服务（FastAPI 的 hook bridge / pty writer 路由由 `fastapi.testclient.TestClient` in-process 驱动）。环境仅需 §2 `.venv` 激活。
> - **FR-013 HIL PoC 与 T29 真 CLI round-trip / T30 PoC 20-round / T-MULTI-ROUND 跨 user_turn 3 轮**：需在用户真实 `claude` CLI ≥ v2.1.119 下以交互 prompt 驱动 AskUserQuestion 触发；headless 模式下 `claude` CLI 在无用户 prompt 时不会自发产生 AskUserQuestion，因此这三条用例（ST-FUNC-018-029、ST-PERF-018-001、ST-PERF-018-002）标注 `已自动化: No`、`手动测试原因: external-action`，由下游 dispatcher 以 `[MANUAL_TEST_REQUIRED]` 人工 review 闭环；其余 FR-013 验证由 T-USER-PROMPT-SUBMIT-AUDIT / T-MULTI-ROUND 单元逻辑 + 单元 ↔ 集成 mock 路径覆盖关键属性（`hil_answered` × N、merged_text、跨轮 channel 标识守恒）。
> - **结果列起始为 PENDING**；下文 Step 7 执行后由 SubAgent 更新；手动用例为 `PENDING-MANUAL`。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 38 |
| boundary | 5 |
| ui | 0 |
| security | 5 |
| performance | 2 |
| **合计** | **50** |

> 50 = 49 Test Inventory 行（T01–T39 + T-HOOK-SCHEMA-CANARY + Wave 4.1 NEW × 9）一一映射 + 1 个 INT-001 [Wave 4 REWRITE / Wave 4.1 unified Esc-text 默认] 系统集成 ST 用例（ST-FUNC-018-038，跨 F18+F21+F20+F02 四特性 HIL round-trip）。

---

### 用例编号

ST-FUNC-018-001

### 关联需求

FR-016 AC-1 · IFR-001 · §Interface Contract `ClaudeCodeAdapter.build_argv` Postcondition · Feature Design §Test Inventory T01 · ATS §3.1 FR-016 · §Clarification Addendum Resolved #1（user-approved 2026-04-27）

### 测试目标

验证 `ClaudeCodeAdapter.build_argv(spec)` 在 `spec.model is None` 时输出与 SRS FR-016 严格白名单字面等值的 8 项 argv：`["claude", "--dangerously-skip-permissions", "--plugin-dir", spec.plugin_dir, "--settings", spec.settings_path, "--setting-sources", "project"]`，逐项 `==` 比对，禁用任何多 / 漏 / 顺序错。

### 前置条件

- `.venv` 激活；`harness.adapter.claude.ClaudeCodeAdapter`、`harness.domain.ticket.DispatchSpec` 可导入
- `pytest tmp_path` 提供干净目录；`plugin_dir` / `settings_path` 均位于 `<tmp>/.harness-workdir/<run-id>/.claude/` 隔离子树

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 在 `tmp_path` 下构造 `.harness-workdir/r1/.claude/` 子树并预置 `settings.json` 占位 | 路径可由 `Path.resolve()` 解析 |
| 2 | 构造 `DispatchSpec(argv=["claude"], env={...}, cwd=<wd>, model=None, mcp_config=None, plugin_dir=<bundle>, settings_path=<settings.json>)` | pydantic 构造成功 |
| 3 | `argv = ClaudeCodeAdapter().build_argv(spec)` | 返回 `list[str]` 无异常 |
| 4 | 断言 `len(argv) == 8` | True |
| 5 | 断言 `argv == ["claude", "--dangerously-skip-permissions", "--plugin-dir", str(spec.plugin_dir), "--settings", str(spec.settings_path), "--setting-sources", "project"]` | True |

### 验证点

- argv 长度严格 8
- argv 与 SRS FR-016 严格 8 项白名单逐项 `==`
- `--model` 不出现（`spec.model is None`）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_build_argv.py::test_t01_claude_build_argv_strict_8_item_template_no_model`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-002

### 关联需求

FR-016 AC-1 含可选 `--model` · §Interface Contract `build_argv` Postcondition · Feature Design §Test Inventory T02 · 系统设计 §6.1.1（commit `92538da`）

### 测试目标

验证 `spec.model = "opus"` 时 argv 长度严格 10、`--model opus` 严格插入在 `--settings <path>` 与 `--setting-sources project` 之间，逐项 `==` 比对模板。

### 前置条件

- 同 ST-FUNC-018-001
- `spec.model = "opus"`；其余路径与 ST-FUNC-018-001 一致

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `DispatchSpec(...model="opus", mcp_config=None, plugin_dir=..., settings_path=...)` | pydantic 构造成功 |
| 2 | `argv = ClaudeCodeAdapter().build_argv(spec)` | 返回 `list[str]` 无异常 |
| 3 | 断言 `len(argv) == 10` | True |
| 4 | 断言 `argv == ["claude", "--dangerously-skip-permissions", "--plugin-dir", str(spec.plugin_dir), "--settings", str(spec.settings_path), "--model", "opus", "--setting-sources", "project"]` | True |

### 验证点

- `--model opus` 插入位置严格在 `--settings <path>` 之后、`--setting-sources project` 之前
- argv 长度严格 10

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_build_argv.py::test_t02_claude_build_argv_strict_10_item_template_with_model`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-003

### 关联需求

FR-008 AC-1 negative · FR-016 永禁 flag · Feature Design §Test Inventory T03 · ATS §3.1 FR-008 SEC

### 测试目标

验证 `ClaudeCodeAdapter.build_argv(spec)` 任意构造路径下 argv 永禁包含 `-p` / `--print` / `--output-format` / `--include-partial-messages` 中的任一 flag（旧 stream-json 协议遗留）。

### 前置条件

- 同 ST-FUNC-018-001 / ST-FUNC-018-002

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `DispatchSpec` 多种典型组合（model None / "opus"；mcp_config None / 任意；env 多变量） | pydantic 构造成功 |
| 2 | 对每个 spec 调 `ClaudeCodeAdapter().build_argv(spec)` 收集 argv | 返回 `list[str]` |
| 3 | 断言每个 argv 中均：`"-p" not in argv and "--print" not in argv and "--output-format" not in argv and "--include-partial-messages" not in argv` | True |

### 验证点

- 4 个永禁 flag 均不出现，无论 spec 字段如何组合
- 与 SRS FR-008 EARS 完全等值

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_build_argv.py::test_t03_claude_argv_never_contains_banned_flags`、`tests/test_f18_w4_build_argv.py::test_t03b_claude_argv_never_contains_mcp_flags_even_when_spec_has_mcp`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-004

### 关联需求

FR-016 AC-2 · FR-017 · Feature Design §Test Inventory T04 · §flowchart#3 OpenCodeBranch

### 测试目标

验证 OpenCode `spec.mcp_config` 非空时，`OpenCodeAdapter.build_argv(spec)` 的 argv 不写入 `--mcp-config` / `--strict-mcp-config`，且 `mcp_degrader.toast_pushed` 列表中含 `"OpenCode MCP 延后 v1.1"` 提示文案；argv 首项必为 `"opencode"`。

### 前置条件

- 同 ST-FUNC-018-001
- `harness.adapter.opencode.OpenCodeAdapter` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 OpenCode `DispatchSpec(argv=["opencode"], mcp_config="/path/x", model=None, plugin_dir=..., settings_path=...)` | pydantic 构造成功 |
| 2 | `adapter = OpenCodeAdapter(); argv = adapter.build_argv(spec)` | 返回 `list[str]` |
| 3 | 断言 `argv[0] == "opencode"` 且 `"--mcp-config" not in argv` 且 `"--strict-mcp-config" not in argv` | True |
| 4 | 断言 `adapter.mcp_degrader.toast_pushed` 是 `list[str]` 且至少 1 条 `"OpenCode MCP 延后 v1.1"` 子串命中 | True |

### 验证点

- OpenCode MCP 不写入 argv（v1 降级）
- toast 列表含 `"OpenCode MCP 延后 v1.1"`
- argv 首项 `"opencode"`

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_build_argv.py::test_t04_opencode_mcp_config_triggers_v1_degrade_with_user_toast`、`tests/test_f18_w4_build_argv.py::test_t04b_opencode_argv_starts_with_opencode_and_mcp_degrader_toast_is_list`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-001

### 关联需求

FR-053 边界 `option_index` 1-based · FR-011 边界 · §Boundary Conditions option_index · Feature Design §Test Inventory T05

### 测试目标

验证 `TuiKeyEncoder().encode_radio(0)` 与负数索引抛 `ValueError`（1-based 协议；0 / 负数错认为合法属典型 off-by-one bug）。

### 前置条件

- `.venv` 激活；`harness.hil.tui_keys.TuiKeyEncoder` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | 调 `enc.encode_radio(0)` | 抛 `ValueError` |
| 3 | 调 `enc.encode_radio(-1)` | 抛 `ValueError` |

### 验证点

- 0 / 负索引一律 `ValueError`
- encoder 不接受非 1-based 输入

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_t05_encode_radio_rejects_zero_index_one_based`、`tests/test_f18_w4_tui_keys.py::test_t05b_encode_radio_rejects_negative_index`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-005

### 关联需求

FR-053 AC-baseline · Feature Design §Test Inventory T06

### 测试目标

验证 `TuiKeyEncoder().encode_radio(1)` 与 `encode_radio(9)` 字节级输出严格等于 `b"1\r"` 与 `b"9\r"`（baseline 协议保留为 fallback）。

### 前置条件

- `.venv` 激活；`harness.hil.tui_keys.TuiKeyEncoder` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | 断言 `enc.encode_radio(1) == b"1\r"`（byte-equal） | True |
| 3 | 断言 `enc.encode_radio(9) == b"9\r"`（byte-equal） | True |

### 验证点

- 字节序列与 SRS FR-053 baseline AC 完全等值
- `\r` 不被替换为 `\n`；不含多余空格

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_t06_encode_radio_one_returns_b_one_cr`、`tests/test_f18_w4_tui_keys.py::test_t06b_encode_radio_nine_returns_b_nine_cr`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-006

### 关联需求

FR-053 AC-baseline freeform · ATS INT-001 SEC byte-equal · Feature Design §Test Inventory T07

### 测试目标

验证 baseline `encode_freeform("hello")` 字节级输出 `b"\x1b[200~hello\x1b[201~\r"`（bracketed paste 包裹 + CR）。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | 断言 `enc.encode_freeform("hello") == b"\x1b[200~hello\x1b[201~\r"` | True |

### 验证点

- bracketed paste 序列字节级正确
- 末尾 CR 不漏

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_t07_encode_freeform_hello_exact_bytes`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-001

### 关联需求

FR-053 SEC · FR-011 SEC · ATS §3.1 FR-011 SEC · Feature Design §Test Inventory T08 · §Boundary Conditions 控制字符攻击面

### 测试目标

验证 baseline `encode_freeform` 拒绝 `\x03` (ETX) / `\x04` (EOT) / 协议外 `\x1b` (ESC，超出 bracketed paste 包裹) — 抛 `EscapeError`，防止控制字符注入。

### 前置条件

- 同 ST-FUNC-018-005；`harness.hil.errors.EscapeError` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | 调 `enc.encode_freeform("a\x03b")` | 抛 `EscapeError` |
| 3 | 调 `enc.encode_freeform("a\x04b")` | 抛 `EscapeError` |
| 4 | 调 `enc.encode_freeform("color\x1b[31mred")` | 抛 `EscapeError` |

### 验证点

- 三类禁用控制字符全部抛 `EscapeError`
- 攻击面（bracketed paste 包裹外的 ESC 序列）被拦截

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_t08_encode_freeform_rejects_etx_x03`、`tests/test_f18_w4_tui_keys.py::test_t08b_encode_freeform_rejects_eot_x04`、`tests/test_f18_w4_tui_keys.py::test_t08c_encode_freeform_rejects_bare_esc_x1b_outside_paste`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-002

### 关联需求

FR-053 UTF-8 守恒 · §Boundary Conditions text UTF-8 · Feature Design §Test Inventory T09

### 测试目标

验证 baseline `encode_freeform("中文😀")` UTF-8 多字节 byte-equal 守恒：bytes `== b"\x1b[200~" + "中文😀".encode("utf-8") + b"\x1b[201~\r"`。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | `out = enc.encode_freeform("中文😀")` | 返回 `bytes` |
| 3 | 断言 `out == b"\x1b[200~" + "中文😀".encode("utf-8") + b"\x1b[201~\r"` | True |

### 验证点

- UTF-8 多字节字符（含 emoji）byte-equal 守恒
- 不存在编码丢失或截断

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_t09_encode_freeform_utf8_multibyte_byte_equal`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-007

### 关联需求

FR-053 AC-3 baseline 多 question 串行 · FR-011 多 question · Feature Design §Test Inventory T10

### 测试目标

验证 baseline 多 question 表单 `[encode_radio(2), encode_radio(1)]` 串行字节序列：每条 byte-equal 单条编码（`b"2\r"`, `b"1\r"`），且不串扰；同时验证 `encode_interrupt() == b"\x03"`。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | 断言 `enc.encode_radio(2) == b"2\r"` 且 `enc.encode_radio(1) == b"1\r"` | True |
| 3 | 断言 `enc.encode_interrupt() == b"\x03"` | True |

### 验证点

- 多 question 串行编码无串扰
- 中断字节为 ETX `\x03`

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_t10_multi_question_serial_encoding_each_byte_equal_single`、`tests/test_f18_w4_tui_keys.py::test_t10b_encode_interrupt_returns_etx`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-008

### 关联需求

FR-009 AC-1 · IFR-001 hook stdin schema · ASM-009 · Feature Design §Test Inventory T11 + §sequenceDiagram msg#7

### 测试目标

验证 `HookEventMapper().parse(payload)` 在真 `PreToolUse(AskUserQuestion)` payload 下输出 `HilQuestion[0].header / question / options / multi_select / kind` 字段齐全且与 reference puncture v8 实测样本字段一致。

### 前置条件

- 同 ST-FUNC-018-005；`harness.hil.hook_mapper.HookEventMapper`、`harness.domain.ticket.HilQuestion / HilOption` 可导入；`tests/fixtures/hook_event_askuserquestion_v2_1_119.json` 存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 加载真 fixture payload（载有 `questions[0]={header:"Lang",question:"Which language?",options:[{label:"Python",description:"Python language"},...],multiSelect:false}`） | dict 加载 |
| 2 | `qs = HookEventMapper().parse(payload)` | 返回 `list[HilQuestion]` 非空 |
| 3 | 断言 `qs[0].header == "Lang"` 且 `qs[0].question == "Which language?"` | True |
| 4 | 断言 `qs[0].options == [HilOption(label="Python", description="Python language"), ...]`（按 puncture 实测） | True |
| 5 | 断言 `qs[0].multi_select is False` 且 `qs[0].kind == "single_select"` | True |

### 验证点

- 字段提取无错位 / UTF-8 截断
- `kind` 派生与 `HilControlDeriver` 规则一致

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_hook_mapper.py::test_t11_hook_event_mapper_parses_real_askuserquestion_payload`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-009

### 关联需求

FR-009 AC-3 缺字段补默认 · §Interface Contract `HookEventMapper.parse` Postcondition · Feature Design §Test Inventory T12

### 测试目标

验证 payload `tool_input.questions[0]` 缺 `options` 字段时 mapper 用空列表补齐 + 发 warning 日志（不抛）。

### 前置条件

- 同 ST-FUNC-018-008；pytest `caplog` fixture

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 payload 中 `tool_input.questions[0]` 删除 `options` 键 | dict 合法 |
| 2 | 调 `HookEventMapper().parse(payload)`（caplog 捕获 WARNING） | 不抛异常 |
| 3 | 断言 `qs[0].options == []` | True |
| 4 | 断言 caplog WARNING 命中 `"missing 'options'"` 子串 | True |

### 验证点

- mapper 不抛
- options 默认空 list
- warning 日志显式提示

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_hook_mapper.py::test_t12_missing_options_field_defaults_empty_with_warning`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-003

### 关联需求

FR-009 AC-2 跨 turn session_id 稳定 · Feature Design §Test Inventory T13 · §sequenceDiagram msg#7 cross-turn

### 测试目标

验证同一 `session_id` 多 turn HIL hook event 下 `tool_use_id` 唯一且 `session_id` 跨 turn 稳定，可作 lifecycle 锚。

### 前置条件

- 同 ST-FUNC-018-008

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 2 个 payload 同 `session_id` 不同 `tool_use_id` | dict 合法 |
| 2 | 分别调 `HookEventMapper().parse(payload)` | 各自返 `HilQuestion[]` |
| 3 | 断言两 `tool_use_id` 不相等 | True |
| 4 | 断言两 `session_id` 相等 | True |

### 验证点

- session_id 跨 turn 守恒
- tool_use_id 唯一性

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_hook_mapper.py::test_t13_session_id_stable_across_turns_and_tool_use_ids_unique`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-010

### 关联需求

FR-009 §Interface Contract `map_hook_event` Raises · Feature Design §Test Inventory T14

### 测试目标

验证非 PreToolUse(AskUserQuestion) 类型（`hook_event_name == "PostToolUse"` / `tool_name == "Read"` / `SessionStart`）的 payload 经 mapper 处理返 `[]`（不抛），保证 hook 事件流不会被误派为 HIL。

### 前置条件

- 同 ST-FUNC-018-008

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `hook_event_name="PostToolUse"` payload 并调 `HookEventMapper().parse` | 返 `[]` 不抛 |
| 2 | 构造 `hook_event_name="PreToolUse"` 但 `tool_name="Read"` 的 payload | 返 `[]` 不抛 |
| 3 | 构造 `hook_event_name="SessionStart"` 的 payload | 返 `[]` 不抛 |

### 验证点

- 三种非 HIL hook event 类型一律返 `[]`
- 无误抛 / 误派

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_hook_mapper.py::test_t14a_post_tool_use_returns_empty_no_raise`、`tests/test_f18_w4_hook_mapper.py::test_t14b_pretool_use_with_unrelated_tool_returns_empty`、`tests/test_f18_w4_hook_mapper.py::test_t14c_session_start_returns_empty`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-004

### 关联需求

FR-009 + ASM-009 hook stdin JSON 字段稳定（schema canary）· IFR-001 hook stdin JSON 字段集合 · Feature Design §Test Inventory T-HOOK-SCHEMA-CANARY

### 测试目标

验证 `tests/fixtures/hook_event_askuserquestion_v2_1_119.json` (golden 实测 fixture) 经 `HookEventPayload.model_validate` + `HookEventMapper().parse` 处理时，递归字段集合（top-level + `tool_input.questions[*]` + `tool_input.questions[*].options[*]`）严格等值锁定 schema；任何 schema 漂移立即 FAIL（claude CLI 升级后 hook stdin schema 字段重命名 / 嵌套结构变 / 新增字段 / 缺失字段 → mapper 静默失配的硬关卡）。

### 前置条件

- 同 ST-FUNC-018-008；fixture 文件存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 加载 fixture → `HookEventPayload.model_validate(payload)` | pydantic 校验通过无 ValidationError |
| 2 | 递归提取所有键名为 `set` | top-level 含 `{session_id, transcript_path, cwd, hook_event_name, tool_name, tool_use_id, tool_input, ts}` |
| 3 | 断言 `tool_input.questions[0]` 键集严格 `{header, question, options, multiSelect}` | True |
| 4 | 断言 `tool_input.questions[0].options[0]` 键集严格 `{label, description}` | True |

### 验证点

- 字段集合 set 等值断言（任何漂移立即定位）
- 失败时输出 `set(fixture_keys) ^ set(schema_keys)` diff（提示维护者重跑 puncture）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_hook_mapper.py::test_t_hook_schema_canary_field_set_strict_equal_to_locked_schema`、`tests/test_f18_w4_hook_mapper.py::test_t_hook_schema_canary_pydantic_validate_passes_locked_fixture`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-011

### 关联需求

IAPI-020 happy · FR-009 hook bridge POST happy · Feature Design §Test Inventory T15 · §sequenceDiagram msg#8

### 测试目标

验证 `POST /api/hook/event` 在合法 hook stdin envelope 下：返 200 `{accepted: True}`，并 fan-out 到 `HilEventBus._ws_broadcast`（含 `kind="hil_event"` payload）+ `TicketStream broadcaster`（`TicketStreamEvent.kind == "tool_use"`）。

### 前置条件

- 同 ST-FUNC-018-008；`fastapi.testclient.TestClient` + 路由装配

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 FastAPI app + 注册 `_hook_router`；以 TestClient 包装 | TestClient 可用 |
| 2 | TestClient.post `/api/hook/event` body=fixture payload, content-type=application/json | 200 `{"accepted": true}` |
| 3 | 断言 `HilEventBus._ws_broadcast` 收到 `{"kind":"hil_event", "payload":{...}}` | True |
| 4 | 断言 `TicketStream broadcaster` 收到 `TicketStreamEvent(kind="tool_use", ...)` | True |

### 验证点

- HTTP 200 + `accepted: true`
- 双 fan-out 无漏分支（HilEventBus + TicketStream）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_api_hook.py::test_t15_post_hook_event_happy_fan_out_returns_200_and_dispatches`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-012

### 关联需求

IAPI-020 415 · IFR-001 AC-w4-2 · Feature Design §Test Inventory T16

### 测试目标

验证 `POST /api/hook/event` content-type ≠ `application/json` 时返 415，audit warning，且 ticket 不卡死。

### 前置条件

- 同 ST-FUNC-018-011

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | TestClient.post `/api/hook/event` body=任意, content-type=`text/plain` | 415 |
| 2 | 断言响应 status_code == 415 | True |

### 验证点

- 415 拒绝路径触发
- ticket 不卡死（audit warning 路径已覆盖）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_api_hook.py::test_t16_post_hook_event_non_json_content_type_returns_415`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-013

### 关联需求

IAPI-020 422 · IFR-001 AC-w4-2 schema 校验 · Feature Design §Test Inventory T17

### 测试目标

验证 `POST /api/hook/event` body 缺必填字段（仅 `{"foo":"bar"}`）时返 422，pydantic errors 列出缺失字段。

### 前置条件

- 同 ST-FUNC-018-011

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | TestClient.post `/api/hook/event` body=`{"foo":"bar"}` | 422 |
| 2 | 断言响应 detail 含 pydantic errors 列表，`hook_event_name` / `session_id` 等必填字段名出现 | True |

### 验证点

- 422 schema 拒绝
- pydantic ValidationError 透出字段名

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_api_hook.py::test_t17_post_hook_event_missing_required_fields_returns_422`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-014

### 关联需求

IAPI-021 happy · FR-011 PTY 回写 · Feature Design §Test Inventory T18 · §sequenceDiagram msg#15

### 测试目标

验证 `POST /api/pty/write` body `{"ticket_id":"<t>","payload":"<base64('1\r')>"}`，ticket state == hil_waiting 时：返 200 `{written_bytes: 2}`，且 `PtyWorker.write` 收到 `b"1\r"` 字节。

### 前置条件

- 同 ST-FUNC-018-011；`harness.api.pty_writer` 路由可装配；FakePty / FakeTicketRepo 可注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 注册 `_pty_writer_router`，注入 FakePty + ticket state=hil_waiting | TestClient 可用 |
| 2 | TestClient.post `/api/pty/write` body=`{"ticket_id":"<t>","payload":"<base64('1\\r')>"}` | 200 `{"written_bytes": 2}` |
| 3 | 断言 FakePty.received_bytes == `b"1\r"` | True |

### 验证点

- HTTP 200 + 字节计数
- base64 解码 + 透传到 pty.write 正确

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_api_pty_writer.py::test_t18_post_pty_write_happy_writes_decoded_bytes`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-015

### 关联需求

IAPI-021 400 ticket-not-running · Feature Design §Test Inventory T19

### 测试目标

验证 ticket state == completed 时 `POST /api/pty/write` 返 400，error_code 为 `ticket-not-running`。

### 前置条件

- 同 ST-FUNC-018-014

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 注入 ticket state=completed | TestClient 可用 |
| 2 | TestClient.post `/api/pty/write` body=合法 payload | 400 |
| 3 | 断言 detail.error_code == `"ticket-not-running"` | True |

### 验证点

- 400 拒绝死 ticket 写入
- error_code 字符串严格匹配

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_api_pty_writer.py::test_t19_post_pty_write_completed_ticket_returns_400_ticket_not_running`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-016

### 关联需求

IAPI-021 404 + 400 b64 · Feature Design §Test Inventory T20

### 测试目标

验证 `POST /api/pty/write` 对未知 ticket_id 返 404；payload 非合法 base64 返 400 + error_code `b64-decode-error`。

### 前置条件

- 同 ST-FUNC-018-014

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | TestClient.post `/api/pty/write` body=`{"ticket_id":"unknown","payload":"<合法 base64>"}` | 404 |
| 2 | TestClient.post `/api/pty/write` body=`{"ticket_id":"<t>","payload":"@@@invalid"}` | 400 |
| 3 | 断言 400 detail.error_code == `"b64-decode-error"` | True |

### 验证点

- 404 / 400 错误码无混淆
- b64 解码失败明确归类

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_api_pty_writer.py::test_t20a_post_pty_write_unknown_ticket_returns_404`、`tests/test_f18_w4_api_pty_writer.py::test_t20b_post_pty_write_invalid_base64_returns_400_b64_decode_error`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-017

### 关联需求

FR-015 AC-1 · NFR-014 · ATS §3.1 FR-015 · ATS §4 NFR-014 · Feature Design §Test Inventory T21

### 测试目标

验证 `mypy --strict` 对 `harness/adapter/claude.py` + `harness/adapter/opencode/__init__.py` 通过；`ToolAdapter` Protocol 暴露 `build_argv / prepare_workdir / spawn / map_hook_event / parse_result / detect_anomaly / supports` 共 7 方法且 `ClaudeCodeAdapter` / `OpenCodeAdapter` 实现完整；`isinstance(adapter, ToolAdapter)` 在 runtime 通过。

### 前置条件

- 同 ST-FUNC-018-005；mypy 装在 `.venv`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | shell 执行 `mypy --strict harness/adapter/claude.py harness/adapter/opencode/__init__.py` | exit 0 |
| 2 | python 断言 `set(ToolAdapter.__protocol_attrs__) == {"build_argv","prepare_workdir","spawn","map_hook_event","parse_result","detect_anomaly","supports"}` | True |
| 3 | 断言 `ClaudeCodeAdapter`、`OpenCodeAdapter` 各实现全部 7 方法 | True |
| 4 | 断言 `isinstance(ClaudeCodeAdapter(), ToolAdapter)` 与 `isinstance(OpenCodeAdapter(), ToolAdapter)` 同 True | True |

### 验证点

- mypy 0 error
- runtime Protocol 等值
- 双 adapter 同时通过

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_protocol.py::test_t21_tool_adapter_protocol_exposes_seven_methods`、`tests/test_f18_w4_protocol.py::test_t21b_claude_adapter_implements_seven_methods`、`tests/test_f18_w4_protocol.py::test_t21c_opencode_adapter_implements_seven_methods`、`tests/test_f18_w4_protocol.py::test_t21d_runtime_isinstance_protocol_check_passes_for_concrete_adapters`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-018

### 关联需求

FR-015 AC-2 · FR-018 · Feature Design §Test Inventory T22

### 测试目标

验证 Mock Provider 缺 `prepare_workdir` 时 `isinstance(mock, ToolAdapter)` 返 False（runtime Protocol 拒注册），且 mypy --strict 报错；orchestrator 拒注册抛 `TypeError`（FR-018 向后兼容不破坏）。

### 前置条件

- 同 ST-FUNC-018-017

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 定义残缺 mock 类（缺 `prepare_workdir`） | python 类构造 |
| 2 | 断言 `isinstance(mock(), ToolAdapter) is False` | True |

### 验证点

- 静态 mypy 拒收 + runtime isinstance 拒收
- Protocol 强制 7 方法

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_protocol.py::test_t22_mock_adapter_missing_prepare_workdir_fails_isinstance_check`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-019

### 关联需求

FR-051 AC-1 · §flowchart prepare_workdir · Feature Design §Test Inventory T23

### 测试目标

验证 `prepare_workdir(spec, paths)` 完成后三件套：`<workdir>/.claude.json`、`<workdir>/.claude/settings.json`、`<workdir>/.claude/hooks/claude-hook-bridge.py` 全部存在；hooks/bridge 模式 `0o755`；settings.json 含 `env / hooks / enabledPlugins / skipDangerousModePermissionPrompt` 全字段。

### 前置条件

- 同 ST-FUNC-018-005；`harness.adapter.workdir_artifacts` 可导入；`tmp_path` 隔离根

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 在 `tmp_path/.harness-workdir/r1/` 下设置 `paths.cwd` | 路径合法 |
| 2 | 调 `ClaudeCodeAdapter().prepare_workdir(spec, paths)` | 无异常 |
| 3 | 断言 `os.path.exists(paths.cwd + "/.claude.json")` | True |
| 4 | 断言 `os.path.exists(paths.cwd + "/.claude/settings.json")` | True |
| 5 | 断言 `os.path.exists(paths.cwd + "/.claude/hooks/claude-hook-bridge.py")` | True |
| 6 | 断言 `os.stat(<bridge>).st_mode & 0o777 == 0o755` | True |
| 7 | 加载 settings.json，断言含 `env / hooks / enabledPlugins / skipDangerousModePermissionPrompt` 全字段 | True |

### 验证点

- 三件套全存在
- bridge 可执行位 `0o755`
- settings.json 4 字段无漏

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_prepare_workdir.py::test_t23_prepare_workdir_writes_three_artifacts_with_correct_modes`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-018-005

### 关联需求

FR-051 §Interface Contract `prepare_workdir` postcondition idempotent · Feature Design §Test Inventory T24

### 测试目标

验证连续两次同 `run_id` 调用 `prepare_workdir` 时三件套**字节级一致**（mtime 可不同），保证幂等性。

### 前置条件

- 同 ST-FUNC-018-019

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 第一次调 `prepare_workdir(spec, paths)` 收集三件套字节内容 | 文件落盘 |
| 2 | 第二次调 `prepare_workdir(spec, paths)` 收集三件套字节内容 | 不抛 |
| 3 | 断言两次三件套字节内容逐字节相等（hashlib.sha256） | True |

### 验证点

- 幂等：第二次调用不破坏 / 不丢字段
- 字节级守恒（mtime 可变化）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_prepare_workdir.py::test_t24_prepare_workdir_is_idempotent_byte_equal_on_re_call`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-002

### 关联需求

FR-051 AC-2 · IFR-001 AC-w4-1 · NFR-009 强化 · ATS INT-001 SEC · Feature Design §Test Inventory T25

### 测试目标

验证 mock 用户家目录（HOME）下 run 前后 `~/.claude/settings.json` + `~/.claude.json` sha256 字节级守恒（before == after），完整 prepare_workdir + 三件套写入路径不污染 user-scope。

### 前置条件

- 同 ST-FUNC-018-019；`tmp_path` 充当 mock HOME；预先在 `<HOME>/.claude/` 下放置占位 settings.json + .claude.json

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | monkeypatch HOME → `tmp_path`；预置 `<HOME>/.claude/settings.json` + `<HOME>/.claude.json` 占位文件 | 文件存在 |
| 2 | 计算 before sha256(file1) + sha256(file2) | hex digests |
| 3 | 调 `prepare_workdir(spec, paths)` 在 `<HOME>/.harness-workdir/r1/` 下写三件套 | 完成 |
| 4 | 计算 after sha256(file1) + sha256(file2) | hex digests |
| 5 | 断言 before == after（两文件均字节守恒） | True |

### 验证点

- user-scope 不被写
- 隔离写路径白名单严格

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f18_w4_real_isolation.py::test_t25_real_fs_prepare_workdir_does_not_touch_user_scope_settings`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-003

### 关联需求

§Boundary Conditions write path escape · §flowchart#5 RaiseIsolation · Feature Design §Test Inventory T26

### 测试目标

验证 `paths.cwd = "/tmp/foo"`（不在 `.harness-workdir/` 下）时 `prepare_workdir` 抛 `InvalidIsolationError`，越界写被拦截。

### 前置条件

- 同 ST-FUNC-018-019；`harness.adapter.errors.InvalidIsolationError` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `paths.cwd = "/tmp/foo"`（不在 `.harness-workdir/` 下） | 路径合法但越界 |
| 2 | 调 `ClaudeCodeAdapter().prepare_workdir(spec, paths)` | 抛 `InvalidIsolationError` |

### 验证点

- 越界路径被拦
- 异常类型严格 `InvalidIsolationError`

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_prepare_workdir.py::test_t26_prepare_workdir_rejects_paths_outside_harness_workdir`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-020

### 关联需求

FR-052 AC-1 · IAPI-007 [Wave 4 MOD / Wave 4.1 MOD] · Feature Design §Test Inventory T27

### 测试目标

验证 `hil_waiting` ticket 用户经 harness UI 提交答案：`HilWriteback.write_answer` 调 `TuiKeyEncoder` + POST `/api/pty/write`；ticket 状态 → `classifying`；`HilEventBus.publish_answered` 触发 audit `hil_answered`（unified Esc-text 默认）。

### 前置条件

- 同 ST-FUNC-018-005；`harness.hil.writeback.HilWriteback` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `hil_waiting` ticket + FakePty + FakeTicketRepo + FakeAuditWriter | 测试装置就绪 |
| 2 | `wb = HilWriteback(...); wb.write_answer(answer={"value":"Python", "channel":"unified_esc_text"})` | 不抛 |
| 3 | 断言 FakePty.posted 含 `b"\x1b\x1b[200~Python\x1b[201~\r"` | True |
| 4 | 断言 ticket.state 转移到 `classifying` | True |
| 5 | 断言 audit `hil_answered` 事件 emit 1 次 | True |

### 验证点

- unified Esc-text 写入路径
- 状态机转移
- audit 闭环

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_writeback.py::test_t27_write_answer_drives_pty_write_via_unified_esc_text`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-021

### 关联需求

FR-011 AC-4 · §Interface Contract Raises `PtyClosedError` · Feature Design §Test Inventory T28

### 测试目标

验证 pty 已关闭（`PtyClosedError`）尝试写键序时：`HilWriteback.pending_answers` 保留 answer 不丢；ticket 状态 → `failed`。

### 前置条件

- 同 ST-FUNC-018-020；可注入 PtyClosedError 抛出方式

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 FakePty 在 write 时抛 `PtyClosedError` | 测试装置就绪 |
| 2 | `wb.write_answer(answer)` | 抛 `PtyClosedError` 或 wrapped exception |
| 3 | 断言 `wb.pending_answers` 保留原 answer | True |
| 4 | 断言 ticket.state == `"failed"` | True |

### 验证点

- 答案不丢失
- 状态显式 failed

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_writeback.py::test_t28_pty_closed_preserves_answer_and_marks_ticket_failed`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-022

### 关联需求

FR-014 [DEPRECATED Wave 4] new AC · ATS FR-014 静态分析 · Feature Design §Test Inventory T31 · Design rationale (e)

### 测试目标

验证 `grep -r "BannerConflictArbiter\|JsonLinesParser\|HilExtractor" harness/ scripts/ tests/` 0 命中（旧 Wave 3 死代码已物理删除）。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 在 repo 根下分别针对 `BannerConflictArbiter` / `JsonLinesParser` / `HilExtractor` 调 `subprocess.run(["grep","-rn",needle,"harness/","scripts/","tests/"])` | 退出码 1（grep 无命中） |
| 2 | 断言每条 needle 命中数 == 0 | True |

### 验证点

- 死代码 0 残留
- Wave 3 → Wave 4 协议层重构已彻底切换

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_protocol.py::test_t31_dead_code_grep_returns_zero_hits_in_production_paths`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-023

### 关联需求

FR-014 替代逻辑 · Design rationale (e) SessionEnd hook 协调 · Feature Design §Test Inventory T32

### 测试目标

验证 session 中 PreToolUse(AskUserQuestion) fire 但用户未答、随后 SessionEnd hook 触发时：`HilEventBus.tool_use_id_queue` 含 unanswered tool_use_id；SessionEnd handler 判 queue 非空 → ticket state `hil_waiting`（不是 completed）。

### 前置条件

- 同 ST-FUNC-018-008

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 PreToolUse(AskUserQuestion) hook payload，先经 mapper 入 `tool_use_id_queue` | queue 含一项 |
| 2 | 构造 SessionEnd hook payload；触发 SessionEnd handler | handler 检查 queue |
| 3 | 断言 ticket.state == `"hil_waiting"`（非 `"completed"`） | True |

### 验证点

- SessionEnd hook 不误判 completed
- tool_use_id queue 是 lifecycle 锚

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_session_end.py::test_t32_session_end_with_unanswered_hil_keeps_ticket_in_hil_waiting`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-024

### 关联需求

IAPI-006 [Wave 4 MOD] byte_queue 字段语义降级 · Feature Design §Test Inventory T33

### 测试目标

验证 spawn ticket 后 `worker.byte_queue` 字段保留作为 backward compat 占位但不被任何 supervisor / parser 订阅；`harness/orchestrator/` 下 0 个 `byte_queue.get` 调用（grep audit）。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | shell 执行 `grep -rn "byte_queue.get" harness/orchestrator/` | 退出码 1（0 命中） |
| 2 | 断言 0 命中 | True |

### 验证点

- byte_queue 不被消费
- 下游 TicketStreamEvent 仅经 HookEventToStreamMapper 派生

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_protocol.py::test_t33_byte_queue_not_subscribed_by_orchestrator_or_supervisor`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-025

### 关联需求

`HookEventToStreamMapper.map` kind 派生矩阵 · Feature Design §Test Inventory T34

### 测试目标

验证 `HookEventToStreamMapper.map` 的 kind 派生矩阵：`SessionStart/End → "system"`；`PreToolUse + AskUserQuestion → "tool_use"`；`PreToolUse + Read → "tool_use"`；`PostToolUse → "tool_result"`。

### 前置条件

- 同 ST-FUNC-018-008；`harness.stream.hook_to_stream.HookEventToStreamMapper` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 参数化构造 4+ 个 (hook_event_name, tool_name, expected_kind) 组合 | 测试矩阵 |
| 2 | 对每组调 `HookEventToStreamMapper().map(payload)` | 返 `TicketStreamEvent` |
| 3 | 断言每组 `event.kind == expected_kind` | True |

### 验证点

- kind 派生矩阵完整 4 类 + AskUserQuestion / Read 双 PreToolUse 分支
- 无误派

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_hook_to_stream.py::test_t34_hook_to_stream_kind_matrix`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-026

### 关联需求

`claude-hook-bridge.py` stdin → POST · Feature Design §Test Inventory T35

### 测试目标

验证 `scripts/claude-hook-bridge.py` 在 mock claude TUI 喂 stdin JSON envelope 时 spawn → POST harness `/api/hook/event`；脚本 exit 0 + harness 收到 POST。

### 前置条件

- 同 ST-FUNC-018-005；脚本路径已部署；TestClient/local HTTP server 可拉起捕获

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 拉起本地 HTTP capture server 监听 `/api/hook/event` | 服务器就绪 |
| 2 | `subprocess.run([sys.executable, "<bridge_path>"], input=<json_envelope>, env={"HARNESS_HOOK_URL": <capture_url>})` | exit 0 |
| 3 | 断言 capture server 收到 1 个 POST，body 与 envelope 一致 | True |

### 验证点

- bridge 子进程 exit 0
- harness 端收到 POST

### 后置检查

- HTTP server 关闭

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_bridge_script.py::test_t35_bridge_script_posts_stdin_json_to_harness`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-027

### 关联需求

`claude-hook-bridge.py` POST 失败 · Feature Design §Test Inventory T36

### 测试目标

验证 bridge 在 harness 不可达时：stderr 命中 `[harness-hook-bridge] POST failed:`；exit 非 0；不阻塞 claude TUI（脚本不挂死）但 hook 副作用丢失（应在外层 audit warning + UI 横幅）。

### 前置条件

- 同 ST-FUNC-018-026

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `subprocess.run([sys.executable, "<bridge_path>"], input=<json>, env={"HARNESS_HOOK_URL": "http://127.0.0.1:1/unreachable"}, capture_output=True)` | 子进程返回 |
| 2 | 断言 exit 非 0 | True |
| 3 | 断言 stderr 含 `[harness-hook-bridge] POST failed:` | True |

### 验证点

- bridge 不静默吞错
- 失败可观察

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_bridge_script.py::test_t36_bridge_script_unreachable_harness_exits_nonzero_with_stderr`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-028

### 关联需求

FR-012 · IFR-002 · ATS FR-012 · Feature Design §Test Inventory T37

### 测试目标

验证 OpenCode hooks.json 注册成功 → skill 调 Question 工具 → POST `/api/hook/event` (OpenCode 侧 hooks 输出到 stdout 桥接) → `OpenCodeAdapter.map_hook_event` 派 HilQuestion，schema 与 Claude 同。

### 前置条件

- 同 ST-FUNC-018-008；`harness.adapter.opencode` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 OpenCode hook envelope（与 Claude AskUserQuestion 同 schema） | dict |
| 2 | 调 `OpenCodeAdapter().map_hook_event(envelope)` | 返 `HilQuestion[]` |
| 3 | 断言字段 schema 与 Claude HilQuestion 等值（header/question/options/multi_select/kind） | True |

### 验证点

- HIL 控件可生成
- 双 provider schema 等值

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_opencode.py::test_t37_opencode_map_hook_event_returns_hil_question_same_schema`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-029

### 关联需求

FR-013 PoC gate · FR-008/009/011/051/053 · ATS INT-001 [Wave 4 REWRITE / Wave 4.1 unified Esc-text] · Feature Design §Test Inventory T29 · §sequenceDiagram full

### 测试目标

验证真 `claude` CLI ≥ v2.1.119 完整 HIL round-trip：spawn → 1× AskUserQuestion → POST `/api/hook/event` → `HookEventMapper` → `HilQuestion` → `/ws/hil` 推前端 → 用户答 → `TuiKeyEncoder.encode_unified_answer` → POST `/api/pty/write` → PtyWorker stdin → claude TUI 续跑。`hook_fires == 1`；ticket 同 pid 续跑；audit `hil_captured` + `hil_answered` 各 1；user-scope sha256 守恒；TUI 渲染 "● User answered Claude's questions: ⎿ · ... → option_label"。

### 前置条件

- 同 ST-FUNC-018-005；用户机器装有 `claude` CLI ≥ v2.1.119 且已完成 auth；env-guide §3 工具锁定满足
- **手动驱动**：用户需以真实 prompt 触发 claude 调 AskUserQuestion（headless 自动化无法替代）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 在 isolated `.harness-workdir/<run-id>/` 下 prepare_workdir 写三件套 | 三件套就绪 |
| 2 | spawn 真 `claude` CLI；用户在其交互 prompt 中提交一段会触发 AskUserQuestion 的指令 | claude TUI 渲染问题 |
| 3 | 观察 `/api/hook/event` 收到 1 次 PreToolUse(AskUserQuestion) POST | hook_fires == 1 |
| 4 | 在 harness UI 提交答案；观察 `TuiKeyEncoder.encode_unified_answer` + POST `/api/pty/write` | 同 pid 续跑 |
| 5 | 观察 audit `hil_captured` + `hil_answered` 各 1 条 | True |
| 6 | run 前后 sha256 user-scope `~/.claude/settings.json` + `~/.claude.json` | 字节守恒 |
| 7 | 观察 claude TUI 渲染 `"● User answered Claude's questions: ⎿ · ... → option_label"` | True |

### 验证点

- 全链路 round-trip 成功
- 隔离守恒（user-scope sha256）
- TUI 渲染 confirmation 行

### 后置检查

- claude 进程清理
- isolated workdir 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: No
- **手动测试原因**: external-action（headless 模式下 claude CLI 在无用户 prompt 时不会自发产生 AskUserQuestion，需用户提交真实 prompt 驱动）
- **测试引用**: `tests/integration/test_f18_w4_real_cli.py::test_t29_real_cli_full_hil_round_trip_via_hook_bridge`（@pytest.mark.real_cli，需手动设置）
- **Test Type**: Real

---

### 用例编号

ST-PERF-018-001

### 关联需求

FR-013 PoC gate 重跑 · ATS INT-001 PoC · Feature Design §Test Inventory T30

### 测试目标

验证在新 hook bridge + TuiKeyEncoder 实现下重跑 PoC：T29 路径跑 20 轮跨 user_turn HIL × hook + 键序回写，成功率 ≥ 95%（19/20）；< 5% → 冻结 HIL FR；输出 `docs/explore/wave4-hil-poc-report.md`（每轮耗时 + hook event timestamps）。

### 前置条件

- 同 ST-FUNC-018-029
- **手动驱动**：用户需准备 20 轮触发 prompt 序列；本 SubAgent 不能 headless 自动化

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 准备 20 轮 prompt 序列；逐轮 spawn isolated workdir + claude CLI | claude TUI 各轮渲染问题 |
| 2 | 每轮记录开始 / hook fire / 答复 / TUI 续跑 timestamp | 时间序列 |
| 3 | 统计成功轮次 | success_count |
| 4 | 断言 success_count / 20 ≥ 0.95 | True |
| 5 | 输出 `docs/explore/wave4-hil-poc-report.md`（每轮耗时 + hook event timestamps） | 文件落盘 |

### 验证点

- ≥ 95% 成功率
- 每轮耗时可观察
- 失败 ≥ 5% → 冻结决策可执行

### 后置检查

- 报告归档
- claude 进程清理

### 元数据

- **优先级**: Critical
- **类别**: performance
- **已自动化**: No
- **手动测试原因**: external-action（20 轮真 CLI HIL round-trip，每轮需用户提交触发 prompt，且需手动观察 TUI 续跑成功）
- **测试引用**: `tests/integration/test_f18_w4_real_cli.py::test_t30_real_cli_poc_20_rounds_success_rate_at_least_95_percent`（@pytest.mark.real_cli，需手动驱动）
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-030

### 关联需求

FR-012 AC-2 · IFR-002 OpenCode 版本兼容 · Feature Design §Test Inventory T38

### 测试目标

验证 OpenCode 版本 < 0.3.0 时 `OpenCodeAdapter` 抛 `HookRegistrationError`；ticket failed + UI 升级提示。

### 前置条件

- 同 ST-FUNC-018-028；`harness.adapter.errors.HookRegistrationError` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | monkeypatch OpenCode 版本检查返 `"0.2.99"` | 测试装置就绪 |
| 2 | 调 `OpenCodeAdapter().prepare_workdir(spec, paths)` 或对应入口 | 抛 `HookRegistrationError` |

### 验证点

- 异常类型严格 `HookRegistrationError`
- 错误信息可读，便于 UI 提示升级

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_opencode.py::test_t38_opencode_version_too_old_raises_hook_registration_error`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-004

### 关联需求

IFR-002 SEC · ATS IFR-002 BNDRY · Feature Design §Test Inventory T39

### 测试目标

验证 Question name > 256B 时 `OpenCodeAdapter` hook 注入路径正确截断到 256B + ellipsis，不崩溃。

### 前置条件

- 同 ST-FUNC-018-028

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 question name 为 > 256 字节字符串（含 CJK 跨字节边界） | dict |
| 2 | 调 OpenCode hook 注入路径 | 不抛异常 |
| 3 | 断言写入 hooks.json 的 name 长度 ≤ 256 字节 + 含截断标记 | True |

### 验证点

- 长 name 不崩
- 截断与 UTF-8 字节边界安全

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_opencode.py::test_t39_long_question_name_truncated_to_256_bytes_no_crash`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-031

### 关联需求

FR-053 Wave 4.1 AC-default · `TuiKeyEncoder.encode_unified_answer` 单选合并 · Feature Design §Test Inventory T-UNIFIED-RADIO

### 测试目标

验证 `TuiKeyEncoder().encode_unified_answer("Python")` 字节级输出严格 `b"\x1b\x1b[200~Python\x1b[201~\r"`（unified Esc-text 协议前缀 = `ESC + bracketed-paste(merged_text) + CR`）。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | `out = enc.encode_unified_answer("Python")` | 返 `bytes` |
| 3 | 断言 `out == b"\x1b\x1b[200~Python\x1b[201~\r"`（byte-equal） | True |

### 验证点

- unified Esc-text 协议前缀字节正确
- 与 SRS FR-053 Wave 4.1 AC-default 等值

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_unified_radio_single_select_encoding`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-032

### 关联需求

FR-053 Wave 4.1 AC-default-multi · multi-select 合并语义 · Feature Design §Test Inventory T-UNIFIED-MULTI-SELECT

### 测试目标

验证 multi-select 合并文本（如 "Python, Go" 经 `_merge_text` 用 `", ".join` 合并）经 `encode_unified_answer` 后字节级输出 `b"\x1b\x1b[200~Python, Go\x1b[201~\r"`。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | 断言 `enc.encode_unified_answer("Python, Go") == b"\x1b\x1b[200~Python, Go\x1b[201~\r"` | True |

### 验证点

- 多选合并字节级守恒（顺序 / 分隔符严格）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_unified_multi_select_merged_encoding`、`tests/test_f18_w4_writeback.py::test_unified_multi_select_merges_labels_with_comma_space`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-033

### 关联需求

FR-053 Wave 4.1 AC-default 多 question 合并 · Feature Design §Test Inventory T-UNIFIED-MULTI-QUESTION

### 测试目标

验证多 question 合并文本（如 `"Lang: Python; Test: pytest; CI: github-actions"`）经 `encode_unified_answer` 后字节级守恒（协议前缀 + 合并文本 + 后缀 + CR），UTF-8 不破坏。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | `merged = "Lang: Python; Test: pytest; CI: github-actions"` | str |
| 3 | 断言 `enc.encode_unified_answer(merged) == b"\x1b" + b"\x1b[200~" + merged.encode("utf-8") + b"\x1b[201~" + b"\r"` | True |

### 验证点

- 多 question 一次注入语义
- UTF-8 守恒

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_unified_multi_question_concatenated_encoding`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-034

### 关联需求

FR-053 Wave 4.1 AC-default-utf8 freeform 合并 · Feature Design §Test Inventory T-UNIFIED-FREEFORM

### 测试目标

验证 freeform 文本（含 UTF-8 多字节字符 — 中文 + emoji + ASCII 混合）经 `encode_unified_answer` 后字节级守恒。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | `text = "我想要 Rust 语言 — 因为速度"` | str |
| 3 | 断言 `enc.encode_unified_answer(text) == b"\x1b" + b"\x1b[200~" + text.encode("utf-8") + b"\x1b[201~" + b"\r"` | True |
| 4 | 断言 `enc.encode_unified_answer("") == b"\x1b\x1b[200~\x1b[201~\r"`（空文本合法） | True |

### 验证点

- UTF-8 多字节守恒
- 空文本合法路径

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_unified_freeform_encoding`、`tests/test_f18_w4_tui_keys.py::test_unified_empty_text_is_legal`、`tests/test_f18_w4_writeback.py::test_unified_freeform_text_wins_over_labels`
- **Test Type**: Real

---

### 用例编号

ST-SEC-018-005

### 关联需求

FR-053 Wave 4.1 AC-default-sec · 协议外 ESC 注入防护 · Feature Design §Test Inventory T-UNIFIED-SEC

### 测试目标

验证 unified Esc-text 路径下 `encode_unified_answer` 拒绝 `\x03` (ETX) / `\x04` (EOT) / 协议外 `\x1b` (ESC) — 抛 `EscapeError`，防止协议外 ESC 注入（如 `"color\x1b[31mred"`）。

### 前置条件

- 同 ST-FUNC-018-005

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `enc = TuiKeyEncoder()` | 实例化成功 |
| 2 | 调 `enc.encode_unified_answer("safe\x03injected")` | 抛 `EscapeError` |
| 3 | 调 `enc.encode_unified_answer("color\x1b[31mred")` | 抛 `EscapeError` |

### 验证点

- 控制字符全拒
- 协议外 ESC 注入被拦

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_tui_keys.py::test_unified_rejects_etx_x03`、`tests/test_f18_w4_tui_keys.py::test_unified_rejects_bare_esc_outside_protocol_prefix`
- **Test Type**: Real

---

### 用例编号

ST-PERF-018-002

### 关联需求

FR-013 PoC + FR-053 Wave 4.1 unified path 跨轮 · Feature Design §Test Inventory T-MULTI-ROUND

### 测试目标

验证跨 user_turn 3 轮 HIL × unified Esc-text：每轮 `merged_text` 不同；每轮 FakePty.posted 列表新增一段 unified bytes；audit `hil_answered` × 3，每条 `payload.answer.value == merged_text`；ticket 状态每轮 `hil_waiting → classifying`。

### 前置条件

- 同 ST-FUNC-018-020；mock 跨 turn 状态机

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 准备 3 个不同 merged_text 序列 | str list |
| 2 | 对每轮：构造 `hil_waiting` ticket → `wb.write_answer(answer)` → 状态转 `classifying` | 3 轮独立 |
| 3 | 断言 FakePty.posted 累计含 3 段 unified bytes，每段对应 merged_text | True |
| 4 | 断言 audit `hil_answered` × 3，每条 `payload.answer.value == merged_text` | True |
| 5 | 断言 channel 标识 `"unified_esc_text"` 跨轮一致 | True |

### 验证点

- 跨轮无串扰
- audit 与 PTY 字节计数一致

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_unified_audit.py::test_multi_round_three_unified_answers_all_succeed`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-035

### 关联需求

Wave 4.1 audit chain · `HookEventToStreamMapper.map(Stop)` · Feature Design §Test Inventory T-STOP-AUDIT

### 测试目标

验证 `HookEventToStreamMapper.map` 处理 `hook_event_name="Stop"` payload 时派 `TicketStreamEvent.kind == "turn_complete"`，且 `payload.hook_event_name == "Stop"` 透传到事件 payload。

### 前置条件

- 同 ST-FUNC-018-025

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `hook_event_name="Stop"` payload | dict |
| 2 | 调 `HookEventToStreamMapper().map(payload)` | 返 `TicketStreamEvent` |
| 3 | 断言 `event.kind == "turn_complete"` | True |
| 4 | 断言 `event.payload.hook_event_name == "Stop"` | True |

### 验证点

- Stop hook 派 turn_complete 不误派 system
- enum case 完整

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_unified_audit.py::test_stop_hook_event_maps_to_turn_complete_kind`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-036

### 关联需求

Wave 4.1 audit chain · UserPromptSubmit hook + `publish_answered_via_prompt` · Feature Design §Test Inventory T-USER-PROMPT-SUBMIT-AUDIT

### 测试目标

验证：(a) `mapper.map(UserPromptSubmit payload)` → `TicketStreamEvent.kind == "user_prompt_submit"`；(b) `bus.publish_answered_via_prompt(merged_text="Python, Go")` → audit `hil_answered` 事件 `payload.answer == {"value":"Python, Go", "channel":"unified_esc_text"}` 且 WS broadcast 同 payload。

### 前置条件

- 同 ST-FUNC-018-025

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `hook_event_name="UserPromptSubmit"` payload | dict |
| 2 | 调 `HookEventToStreamMapper().map(payload)` | 返 `TicketStreamEvent` |
| 3 | 断言 `event.kind == "user_prompt_submit"` | True |
| 4 | 调 `HilEventBus.publish_answered_via_prompt(merged_text="Python, Go")` | 不抛 |
| 5 | 断言 audit `hil_answered` payload `answer.value == "Python, Go"` 且 `answer.channel == "unified_esc_text"` | True |
| 6 | 断言 `_ws_broadcast` 同 payload | True |

### 验证点

- UserPromptSubmit 派对类
- merged_text 与 channel 标识跨 audit + WS 一致

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_unified_audit.py::test_user_prompt_submit_hook_maps_to_user_prompt_submit_kind`、`tests/test_f18_w4_unified_audit.py::test_publish_answered_via_prompt_writes_hil_answered_with_merged_text`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-037

### 关联需求

Wave 4 兼容回归 · `prefer_baseline=True` · Feature Design §Test Inventory T-BASELINE-COMPAT

### 测试目标

验证 `HilWriteback(..., prefer_baseline=True).write_answer(...)` 走 baseline 路径：FakePty.posted 含 `b"1\r"`（旧 `<N>\r` 编码）；audit 走 `publish_answered`（不是 `publish_answered_via_prompt`）。两路径互不污染。

### 前置条件

- 同 ST-FUNC-018-020

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `hil_waiting` ticket + FakePty + FakeAuditWriter | 装置就绪 |
| 2 | `wb = HilWriteback(..., prefer_baseline=True); wb.write_answer(answer="option-1 → index 1")` | 不抛 |
| 3 | 断言 FakePty.posted == `[b"1\r"]` | True |
| 4 | 断言 audit chain 走 `publish_answered`（不是 `publish_answered_via_prompt`） | True |

### 验证点

- baseline 路径完整保留
- 两路径互不污染

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f18_w4_writeback.py::test_baseline_compat_radio_path_preserved`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-018-038

### 关联需求

INT-001 [Wave 4 REWRITE / Wave 4.1 unified Esc-text 默认] · ATS §5.1 INT-001 · 跨 feature F18 + F21 + F20 + F02 系统集成

### 测试目标

验证 ATS §5.1 INT-001 描述的 HIL 全链路系统集成（hooks + TUI 键序）：spawn claude → 1× PreToolUse(AskUserQuestion) hook fire → harness HookEventMapper → HilQuestion → harness UI 渲染控件 → 用户合并答案为 merged_text → TuiKeyEncoder.encode_unified_answer → POST /api/pty/write → claude TUI 续跑 → 第 2 个 UserPromptSubmit + Stop hook 关闭 audit 闭环（PreToolUse + UserPromptSubmit + Stop 三 hook 联合判定）。整链 p95 < 3s；同 pid 续跑；ticket.hil.answers 持久化；user-scope sha256 守恒；bracketed paste 合并文本 byte-equal 守恒。

### 前置条件

- 同 ST-FUNC-018-029；F18 + F21 + F20 + F02 全部 passing；服务 api + ui-dev 可启动；用户具备真 claude CLI

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 启动 api（8765）+ ui-dev（5173）；浏览器进入 UI | 服务健康 |
| 2 | 用户在 UI 启动 run；spawn claude 进入 isolated workdir | claude TUI 启动 |
| 3 | 用户 prompt 触发 AskUserQuestion；观察 hook bridge POST 1 次 | 后端收到 hook |
| 4 | UI HilControl 渲染问题；用户合并答复并提交 | merged_text 经 encoder + POST /api/pty/write |
| 5 | 观察 TUI 续跑 + Stop hook + UserPromptSubmit hook 各 1 | audit 闭环 |
| 6 | 断言整链 p95 < 3s | True |
| 7 | 断言 user-scope `~/.claude/settings.json` + `~/.claude.json` sha256 守恒 | True |
| 8 | 断言 audit `hil_answered` payload 含 `value=merged_text` + `channel="unified_esc_text"` | True |

### 验证点

- 三 hook 联合判定 audit 闭环
- 同 pid 续跑
- 整链 SLA p95 < 3s
- user-scope 字节守恒
- bracketed paste 字节守恒

### 后置检查

- 服务停止；isolated workdir 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: No
- **手动测试原因**: external-action（系统集成 INT-001 跨 4 feature 系统级 HIL round-trip，需启动完整 UI / api 服务 + 用户在浏览器 UI + 真 claude CLI 中端到端操作；headless 模式下 claude CLI 不会自发产生 AskUserQuestion）
- **测试引用**: 集成在 `tests/integration/test_f18_w4_real_cli.py::test_t29_real_cli_full_hil_round_trip_via_hook_bridge` 单元 + UI 端 F21 ST 用例联合执行（@pytest.mark.real_cli）
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|-----------|------|
| ST-FUNC-018-001 | FR-008/FR-016 (T01) | verification_steps[0] | tests/test_f18_w4_build_argv.py::test_t01_claude_build_argv_strict_8_item_template_no_model | Real | PASS |
| ST-FUNC-018-002 | FR-016 (T02) | verification_steps[0] | tests/test_f18_w4_build_argv.py::test_t02_claude_build_argv_strict_10_item_template_with_model | Real | PASS |
| ST-FUNC-018-003 | FR-008 (T03) | verification_steps[0] | tests/test_f18_w4_build_argv.py::test_t03_claude_argv_never_contains_banned_flags | Real | PASS |
| ST-FUNC-018-004 | FR-016/FR-017 (T04) | verification_steps[18] | tests/test_f18_w4_build_argv.py::test_t04_opencode_mcp_config_triggers_v1_degrade_with_user_toast | Real | PASS |
| ST-BNDRY-018-001 | FR-053/FR-011 (T05) | verification_steps[9] | tests/test_f18_w4_tui_keys.py::test_t05_encode_radio_rejects_zero_index_one_based | Real | PASS |
| ST-FUNC-018-005 | FR-053 (T06) | verification_steps[9] | tests/test_f18_w4_tui_keys.py::test_t06_encode_radio_one_returns_b_one_cr | Real | PASS |
| ST-FUNC-018-006 | FR-053 (T07) | verification_steps[10] | tests/test_f18_w4_tui_keys.py::test_t07_encode_freeform_hello_exact_bytes | Real | PASS |
| ST-SEC-018-001 | FR-053/FR-011 SEC (T08) | verification_steps[7] | tests/test_f18_w4_tui_keys.py::test_t08_encode_freeform_rejects_etx_x03 | Real | PASS |
| ST-BNDRY-018-002 | FR-053 UTF-8 (T09) | verification_steps[7] | tests/test_f18_w4_tui_keys.py::test_t09_encode_freeform_utf8_multibyte_byte_equal | Real | PASS |
| ST-FUNC-018-007 | FR-053/FR-011 multi (T10) | verification_steps[11] | tests/test_f18_w4_tui_keys.py::test_t10_multi_question_serial_encoding_each_byte_equal_single | Real | PASS |
| ST-FUNC-018-008 | FR-009 (T11) | verification_steps[2] | tests/test_f18_w4_hook_mapper.py::test_t11_hook_event_mapper_parses_real_askuserquestion_payload | Real | PASS |
| ST-FUNC-018-009 | FR-009 (T12) | verification_steps[4] | tests/test_f18_w4_hook_mapper.py::test_t12_missing_options_field_defaults_empty_with_warning | Real | PASS |
| ST-BNDRY-018-003 | FR-009 cross-turn (T13) | verification_steps[3] | tests/test_f18_w4_hook_mapper.py::test_t13_session_id_stable_across_turns_and_tool_use_ids_unique | Real | PASS |
| ST-FUNC-018-010 | FR-009 (T14) | verification_steps[2] | tests/test_f18_w4_hook_mapper.py::test_t14a_post_tool_use_returns_empty_no_raise | Real | PASS |
| ST-BNDRY-018-004 | FR-009/IFR-001 (T-HOOK-SCHEMA-CANARY) | verification_steps[2] | tests/test_f18_w4_hook_mapper.py::test_t_hook_schema_canary_field_set_strict_equal_to_locked_schema | Real | PASS |
| ST-FUNC-018-011 | FR-009/IAPI-020 (T15) | verification_steps[1] | tests/test_f18_w4_api_hook.py::test_t15_post_hook_event_happy_fan_out_returns_200_and_dispatches | Real | PASS |
| ST-FUNC-018-012 | IFR-001 AC-w4-2 (T16) | verification_steps[15] | tests/test_f18_w4_api_hook.py::test_t16_post_hook_event_non_json_content_type_returns_415 | Real | PASS |
| ST-FUNC-018-013 | IFR-001 AC-w4-2 (T17) | verification_steps[15] | tests/test_f18_w4_api_hook.py::test_t17_post_hook_event_missing_required_fields_returns_422 | Real | PASS |
| ST-FUNC-018-014 | FR-011/IAPI-021 (T18) | verification_steps[5] | tests/test_f18_w4_api_pty_writer.py::test_t18_post_pty_write_happy_writes_decoded_bytes | Real | PASS |
| ST-FUNC-018-015 | FR-011 (T19) | verification_steps[5] | tests/test_f18_w4_api_pty_writer.py::test_t19_post_pty_write_completed_ticket_returns_400_ticket_not_running | Real | PASS |
| ST-FUNC-018-016 | FR-011 (T20) | verification_steps[8] | tests/test_f18_w4_api_pty_writer.py::test_t20a_post_pty_write_unknown_ticket_returns_404 | Real | PASS |
| ST-FUNC-018-017 | FR-015/NFR-014 (T21) | verification_steps[16] | tests/test_f18_w4_protocol.py::test_t21_tool_adapter_protocol_exposes_seven_methods | Real | PASS |
| ST-FUNC-018-018 | FR-015/FR-018 (T22) | verification_steps[17] | tests/test_f18_w4_protocol.py::test_t22_mock_adapter_missing_prepare_workdir_fails_isinstance_check | Real | PASS |
| ST-FUNC-018-019 | FR-051 (T23) | verification_steps[12] | tests/test_f18_w4_prepare_workdir.py::test_t23_prepare_workdir_writes_three_artifacts_with_correct_modes | Real | PASS |
| ST-BNDRY-018-005 | FR-051 idempotent (T24) | verification_steps[12] | tests/test_f18_w4_prepare_workdir.py::test_t24_prepare_workdir_is_idempotent_byte_equal_on_re_call | Real | PASS |
| ST-SEC-018-002 | FR-051/IFR-001 AC-w4-1 (T25) | verification_steps[13] | tests/integration/test_f18_w4_real_isolation.py::test_t25_real_fs_prepare_workdir_does_not_touch_user_scope_settings | Real | PASS |
| ST-SEC-018-003 | FR-051 isolation escape (T26) | verification_steps[12] | tests/test_f18_w4_prepare_workdir.py::test_t26_prepare_workdir_rejects_paths_outside_harness_workdir | Real | PASS |
| ST-FUNC-018-020 | FR-052 (T27) | verification_steps[14] | tests/test_f18_w4_writeback.py::test_t27_write_answer_drives_pty_write_via_unified_esc_text | Real | PASS |
| ST-FUNC-018-021 | FR-011 PtyClosed (T28) | verification_steps[8] | tests/test_f18_w4_writeback.py::test_t28_pty_closed_preserves_answer_and_marks_ticket_failed | Real | PASS |
| ST-FUNC-018-022 | FR-014 [DEP] (T31) | verification_steps[0] | tests/test_f18_w4_protocol.py::test_t31_dead_code_grep_returns_zero_hits_in_production_paths | Real | PASS |
| ST-FUNC-018-023 | FR-014 替代 SessionEnd (T32) | verification_steps[0] | tests/test_f18_w4_session_end.py::test_t32_session_end_with_unanswered_hil_keeps_ticket_in_hil_waiting | Real | PASS |
| ST-FUNC-018-024 | IAPI-006 byte_queue (T33) | verification_steps[0] | tests/test_f18_w4_protocol.py::test_t33_byte_queue_not_subscribed_by_orchestrator_or_supervisor | Real | PASS |
| ST-FUNC-018-025 | IFR-001/HookEventToStreamMapper (T34) | verification_steps[1] | tests/test_f18_w4_hook_to_stream.py::test_t34_hook_to_stream_kind_matrix | Real | PASS |
| ST-FUNC-018-026 | FR-009/bridge happy (T35) | verification_steps[1] | tests/test_f18_w4_bridge_script.py::test_t35_bridge_script_posts_stdin_json_to_harness | Real | PASS |
| ST-FUNC-018-027 | FR-009/bridge fail (T36) | verification_steps[1] | tests/test_f18_w4_bridge_script.py::test_t36_bridge_script_unreachable_harness_exits_nonzero_with_stderr | Real | PASS |
| ST-FUNC-018-028 | FR-012/IFR-002 (T37) | verification_steps[20] | tests/test_f18_w4_opencode.py::test_t37_opencode_map_hook_event_returns_hil_question_same_schema | Real | PASS |
| ST-FUNC-018-029 | FR-013/INT-001 (T29) | verification_steps[22] | tests/integration/test_f18_w4_real_cli.py::test_t29_real_cli_full_hil_round_trip_via_hook_bridge | Real | PENDING-MANUAL |
| ST-PERF-018-001 | FR-013 PoC (T30) | verification_steps[22] | tests/integration/test_f18_w4_real_cli.py::test_t30_real_cli_poc_20_rounds_success_rate_at_least_95_percent | Real | PENDING-MANUAL |
| ST-FUNC-018-030 | FR-012 (T38) | verification_steps[20] | tests/test_f18_w4_opencode.py::test_t38_opencode_version_too_old_raises_hook_registration_error | Real | PASS |
| ST-SEC-018-004 | IFR-002 SEC (T39) | verification_steps[23] | tests/test_f18_w4_opencode.py::test_t39_long_question_name_truncated_to_256_bytes_no_crash | Real | PASS |
| ST-FUNC-018-031 | FR-053 Wave 4.1 (T-UNIFIED-RADIO) | verification_steps[9] | tests/test_f18_w4_tui_keys.py::test_unified_radio_single_select_encoding | Real | PASS |
| ST-FUNC-018-032 | FR-053 Wave 4.1 (T-UNIFIED-MULTI-SELECT) | verification_steps[10] | tests/test_f18_w4_tui_keys.py::test_unified_multi_select_merged_encoding | Real | PASS |
| ST-FUNC-018-033 | FR-053 Wave 4.1 (T-UNIFIED-MULTI-QUESTION) | verification_steps[11] | tests/test_f18_w4_tui_keys.py::test_unified_multi_question_concatenated_encoding | Real | PASS |
| ST-FUNC-018-034 | FR-053 Wave 4.1 (T-UNIFIED-FREEFORM) | verification_steps[10] | tests/test_f18_w4_tui_keys.py::test_unified_freeform_encoding | Real | PASS |
| ST-SEC-018-005 | FR-053 Wave 4.1 SEC (T-UNIFIED-SEC) | verification_steps[7] | tests/test_f18_w4_tui_keys.py::test_unified_rejects_etx_x03 | Real | PASS |
| ST-PERF-018-002 | FR-013/FR-053 (T-MULTI-ROUND) | verification_steps[22] | tests/test_f18_w4_unified_audit.py::test_multi_round_three_unified_answers_all_succeed | Real | PASS |
| ST-FUNC-018-035 | IFR-001/Stop audit (T-STOP-AUDIT) | verification_steps[1] | tests/test_f18_w4_unified_audit.py::test_stop_hook_event_maps_to_turn_complete_kind | Real | PASS |
| ST-FUNC-018-036 | IFR-001/UserPromptSubmit (T-USER-PROMPT-SUBMIT-AUDIT) | verification_steps[1] | tests/test_f18_w4_unified_audit.py::test_user_prompt_submit_hook_maps_to_user_prompt_submit_kind | Real | PASS |
| ST-FUNC-018-037 | FR-053 baseline compat (T-BASELINE-COMPAT) | verification_steps[9] | tests/test_f18_w4_writeback.py::test_baseline_compat_radio_path_preserved | Real | PASS |
| ST-FUNC-018-038 | INT-001 系统集成 (Wave 4.1) | INT-001 | (manual; cross-feature) | Real | PENDING-MANUAL |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 49 |
| Passed | 46 |
| Failed | 0 |
| Pending | 3 |

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Pending 3 = ST-FUNC-018-029 (T29) + ST-PERF-018-001 (T30) + ST-FUNC-018-038 (INT-001 系统集成) — all `已自动化: No`，`PENDING-MANUAL`，下游 dispatcher 以 `[MANUAL_TEST_REQUIRED]` 收集人工 review 闭环。
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.

## Manual Test Case Summary

| Metric | Count |
|--------|-------|
| Total Manual Test Cases | 3 |
| Manual Passed (MANUAL-PASS) | 0 |
| Manual Failed (MANUAL-FAIL) | 0 |
| Blocked | 0 |
| Pending (PENDING-MANUAL) | 3 |

> Manual test cases = test cases with `已自动化: No`. Results collected via human review gate after automated execution.
> Any MANUAL-FAIL blocks the feature from being marked `"passing"` — same as automated FAIL.
