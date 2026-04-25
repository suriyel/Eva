# 测试用例集: F19 · Bk-Dispatch — Model Resolver & Classifier

**Feature ID**: 19
**关联需求**: FR-019, FR-020, FR-021, FR-022, FR-023, IFR-004（ATS L87-91 + L182；必须类别 FUNC / BNDRY / SEC / PERF；UI 类别由 F22 Fe-Config 单独承担）
**日期**: 2026-04-25（Wave 3 增量更新）
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则（FR-019/020/021/022/023 + IFR-004 + Wave 3 新增 AC：FR-021 AC-4/5/6、FR-023 AC-3/4/5/6/7、IFR-004 AC-mod、ASM-008）、ATS L87-91 / L182 类别约束、Feature Design Test Inventory T01–T52、可观察接口（`harness.dispatch.model.ModelResolver` / `harness.dispatch.classifier.ClassifierService` / `harness.dispatch.classifier.LlmBackend` / `harness.dispatch.classifier.RuleBackend` / `harness.dispatch.classifier.ProviderPresets` / `harness.dispatch.classifier.PromptStore` / `harness.dispatch.model.ModelRulesStore` 公开 API、FastAPI `TestClient` 经 `/api/settings/model_rules` · `/api/settings/classifier` · `/api/settings/classifier/test` · `/api/prompts/classifier` 路由、POSIX `os.stat().st_mode` 权限位、respx HTTP mock 请求 / 响应观测、`keyring.backends.fail` 注入观测、real_external_llm smoke 真网 round-trip）推导，不阅读实现源码。
> - **Wave 3 增量背景**（2026-04-25）：MiniMax OpenAI-compat strict-schema bypass + preset capability 位 + tolerant parse；Wave 3 新增 6 条 ST 用例（ST-FUNC-019-047..051 + ST-FUNC-019-052）覆盖 8 条新 AC + 1 IFR-004-mod + 1 ASM-008；现有 ST-FUNC-019-001..046 用例措辞**不变**。
> - **Specification resolutions applied from Feature Design Clarification Addendum**：5 条已批准 assumption（SSRF 白名单具体范围 / PromptStore history 粒度 / RuleBackend 判定优先级 / `ClassifierHttpError` 冒泡边界 / `classify` 内部 PromptStore.get 自取），见 `docs/features/19-f19-bk-dispatch-model-resolver-classifie.md` §Clarification Addendum；本文档预期结果均按已批准处置撰写。
> - **`feature.ui == false` → 本特性无 UI 类别用例**。ATS L87 / L89 在 FR-019 / FR-021 行列出 UI 仅是为了对齐 F22 Fe-Config 的 SystemSettings 模型规则表 CRUD + Classifier 卡片渲染——这两项 UI 表面由 F22 独立 ST 承担，本特性覆盖的是后端 Resolver / Classifier / 路由契约表面。
> - 本特性以 **"Backend library + REST routes via FastAPI TestClient — no live api uvicorn server required"** 模式运行（env-guide §1.6 纯 CLI / library 模式 —— `pytest tests/test_f19_*.py tests/integration/test_f19_*.py`）。环境仅需 §2 `.venv` 激活；REST 路由 ST 用例使用 `fastapi.testclient.TestClient` 直接装载 `harness.api:app` 并通过 `monkeypatch.setenv("HARNESS_HOME", tmp_path)` 隔离持久化路径。
> - **手动测试**：本特性全部 67 条用例均自动化执行，无 `已自动化: No` 项；FR-019 / FR-021 涉及的 UI CRUD 体验由 F22 Fe-Config ST 承担。Wave 3 新增 ST-FUNC-019-052（real_external_llm smoke）通过 `@pytest.mark.real_external_llm` 标注；keyring 无 entry 时 pytest 自动 skip（在 ST 自动化语义下视为非阻塞 PASS）。

---

## 摘要

| 类别 | 用例数 | Wave 2 基线 | Wave 3 增量 |
|------|--------|-------------|-------------|
| functional | 52 | 46 | +6（T47/T48/T49/T50/T51/T52） |
| boundary | 7 | 7 | 0 |
| ui | 0 | 0 | 0 |
| security | 7 | 7 | 0 |
| performance | 1 | 1 | 0 |
| **合计** | **67** | **61** | **+6** |

> **类别归属约定**：design Test Inventory 标 T52（real_external_llm smoke）为 INTG/http；ST 用例 ID 规范允许 CATEGORY ∈ {FUNC, BNDRY, UI, SEC, PERF}（见 `scripts/validate_st_cases.py` CASE_ID_PATTERN），与既有 ST-FUNC-019-020（T35 real_fs）/ ST-FUNC-019-021（T36 real_keyring）/ ST-PERF-019-001（T31 real_http timeout）一致，T52 归 functional 类别（black-box behavior 验证），具体判定脚注见用例 ST-FUNC-019-052 元数据。

> **类别占比核验**（黑盒负向覆盖 ≥ 40%）：FUNC/error（含合集错误路径 + Wave 3 T51）≥ 19 + BNDRY 7 + SEC 7 = **≥ 33 / 67 ≈ 49% > 40%**。
>
> **Wave 3 增量映射**（编号紧接 Wave 2 末尾）：
> - ST-FUNC-019-047 → T47（ProviderPreset.supports_strict_schema 默认值矩阵 + ClassifierConfig.strict_schema_override 三态 + effective_strict 5 行真值表）
> - ST-FUNC-019-048 → T48（strict-off body 不含 response_format + system message 末尾 `_JSON_ONLY_SUFFIX` + URL/method/Authorization 与 strict-on 一致）
> - ST-FUNC-019-049 → T49（tolerant parse 剥离 `<think>...</think>` 前缀后解析合法 JSON）
> - ST-FUNC-019-050 → T50（tolerant parse 多段 JSON 时取首个语法平衡对象）
> - ST-FUNC-019-051 → T51（tolerant parse 无 JSON 抛 `ClassifierProtocolError(cause='json_parse_error')` → FallbackDecorator 兜底 rule + audit `classifier_fallback`）
> - ST-FUNC-019-052 → T52（real_external_llm smoke：MiniMax 真网 round-trip，验证 strict-off 路径 + ASM-008）

---

### 用例编号

ST-FUNC-019-001

### 关联需求

FR-019 AC-1 · §Interface Contract `ModelResolver.resolve` · Feature Design Test Inventory T01 · ATS L87 FR-019

### 测试目标

验证 `ModelResolver.resolve(ModelOverrideContext)` 在 per-skill 规则 `requirements=opus` 命中时返回 `ResolveResult(model="opus", provenance="per-skill")`，对应 FR-019 EARS 配置 `requirements` skill 默认 opus。

### 前置条件

- `.venv` 激活；`harness.dispatch.model.ModelResolver` / `ModelOverrideContext` / `ModelRule` 可导入
- `pytest tmp_path` 提供空白目录作为 `model_rules.json` 持久化根
- `ModelRulesStore` 已加载 `[ModelRule(skill="requirements", tool="claude", model="opus")]`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 在 `tmp_path` 下构造 `ModelRulesStore` 并 `save([ModelRule(skill="requirements", tool="claude", model="opus")])` | 文件落盘成功 |
| 2 | 重新 `load()` 验证规则可读 | 返回 1 条规则 |
| 3 | 构造 `ctx = ModelOverrideContext(skill_hint="requirements", run_default=None, ticket_override=None, tool="claude")` | pydantic 校验通过 |
| 4 | `resolver = ModelResolver(rules_store=store)`；`result = resolver.resolve(ctx)` | 无异常 |
| 5 | 断言 `result.model == "opus"` 且 `result.provenance == "per-skill"` | True |

### 验证点

- per-skill 规则按 `skill + tool` 双键匹配生效
- 返回 ResolveResult 的 provenance 字段精确等于字面 `"per-skill"`

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_model_resolver.py::test_t01_resolve_per_skill_rule_returns_opus_with_per_skill_provenance`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-002

### 关联需求

FR-020 AC-3 · FR-019 AC-2 · §IC `ModelResolver.resolve` · Feature Design Test Inventory T02 · ATS L88 FR-020

### 测试目标

验证 per-ticket 与 per-skill 同时存在时，per-ticket 胜出（FR-020 AC-3 优先级链）。

### 前置条件

- `.venv` 激活；store 内已存 `[ModelRule(skill="requirements", tool="claude", model="sonnet")]`
- `ctx.ticket_override="opus"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 同 ST-FUNC-019-001 Step 1-2，保存 `requirements→sonnet` 规则 | 落盘 |
| 2 | 构造 `ctx = ModelOverrideContext(ticket_override="opus", skill_hint="requirements", run_default=None, tool="claude")` | 通过 |
| 3 | `result = resolver.resolve(ctx)` | 无异常 |
| 4 | 断言 `result.model == "opus"` 且 `result.provenance == "per-ticket"` | True |

### 验证点

- 优先级链顺序：per-ticket > per-skill（不被规则表覆写吞掉）
- provenance 反映命中层级，非默认 fallback 层

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_model_resolver.py::test_t02_per_ticket_wins_over_per_skill`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-003

### 关联需求

FR-020 AC-1 · §IC `ModelResolver.resolve` · Feature Design Test Inventory T03 · ATS L88 FR-020

### 测试目标

验证仅 `run_default` 设置（per-ticket / per-skill 均空）时返回 `ResolveResult(model="haiku", provenance="run-default")`。

### 前置条件

- `.venv` 激活；store 为空（无任何 ModelRule）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 空 store；构造 `ctx = ModelOverrideContext(ticket_override=None, skill_hint=None, run_default="haiku", tool="claude")` | 通过 |
| 2 | `result = resolver.resolve(ctx)` | 无异常 |
| 3 | 断言 `result.model == "haiku"` 且 `result.provenance == "run-default"` | True |

### 验证点

- run-default 层在 per-ticket / per-skill 均为 None 时被使用
- provenance 字面正确

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_model_resolver.py::test_t03_run_default_only_returns_haiku_with_run_default_provenance`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-019-001

### 关联需求

FR-020 AC-2 · §BC `ctx 四层 None` · Feature Design Test Inventory T04 · ATS L88 FR-020

### 测试目标

验证四层全空（ticket_override / skill_hint / run_default 均为 None；无规则匹配）时返回 `ResolveResult(model=None, provenance="cli-default")`，下游 F18 因此省略 `--model` argv（FR-020 AC-2 EARS）。

### 前置条件

- 空 rules store

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `ctx = ModelOverrideContext(ticket_override=None, skill_hint=None, run_default=None, tool="claude")` | 通过 |
| 2 | `result = resolver.resolve(ctx)` | 无异常 |
| 3 | 断言 `result.model is None` | True |
| 4 | 断言 `result.provenance == "cli-default"` | True |

### 验证点

- 四层全空进入 cli-default fallback 分支
- model 为 None 而非空字符串（避免下游 `--model ""`）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_model_resolver.py::test_t04_all_layers_none_returns_cli_default_with_model_none`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-019-002

### 关联需求

§BC `ticket_override=""` · §IC `ModelResolver.resolve` · Feature Design Test Inventory T05 · Clarification Addendum #5

### 测试目标

验证 `ctx.ticket_override=""`（空字符串）被视为 None — 跳过 per-ticket 层走 per-skill；防止下游 `--model ""` 灾难。

### 前置条件

- store 内有 `[ModelRule(skill="work", tool="claude", model="sonnet")]`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 保存 `work→sonnet` 规则 | 落盘 |
| 2 | 构造 `ctx = ModelOverrideContext(ticket_override="", skill_hint="work", run_default=None, tool="claude")` | 通过 |
| 3 | `result = resolver.resolve(ctx)` | 无异常 |
| 4 | 断言 `result.model == "sonnet"` 且 `result.provenance == "per-skill"` | True |

### 验证点

- 空串归一为 None — 不被当作有效覆写
- 仍向下解析至 per-skill 层

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_model_resolver.py::test_t05_empty_string_ticket_override_skips_to_per_skill_layer`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-004

### 关联需求

§IC `ModelRulesStore.load` Raises `ModelRulesCorruptError` · Feature Design Test Inventory T06

### 测试目标

验证 `model_rules.json` 含非法 JSON 时 `load()` 抛 `ModelRulesCorruptError`，错误不被吞——保证规则丢失不被静默。

### 前置条件

- `tmp_path` 内创建 `model_rules.json` 写入字节序列 `"not json {"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `path.write_text("not json {")` | 文件落盘 |
| 2 | `store = ModelRulesStore(path=path)`；尝试 `store.load()` | 抛 `ModelRulesCorruptError` |
| 3 | 断言异常类名为 `ModelRulesCorruptError` 且 message 含 "JSON" 或 "decode" 关键字 | True |

### 验证点

- JSON 非法引发显式异常类，非通用 `JSONDecodeError`
- API 层（GET /api/settings/model_rules）将该异常映射为 500 + detail（见 ST-FUNC-019-035）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_model_rules_store.py::test_t06_load_raises_model_rules_corrupt_error_on_invalid_json`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-005

### 关联需求

FR-019 · §IC `ModelRulesStore.save/load` · Feature Design Test Inventory T07

### 测试目标

验证 `save()` 后 `load()` 返回等价规则列表（持久化原子性 + round-trip 完整性）。

### 前置条件

- 空目录

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `store.save([ModelRule(skill="work", tool="claude", model="sonnet")])` | 落盘 |
| 2 | 新 `ModelRulesStore` 实例 `store2.load()` | 返回 1 条规则 |
| 3 | 断言 `len(rules)==1` 且 `rules[0].model=="sonnet"` 且 `rules[0].skill=="work"` 且 `rules[0].tool=="claude"` | True |

### 验证点

- 原子写（temp+rename）保证读侧不会读到半截文件
- pydantic schema 字段在序列化往返中无损

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_model_rules_store.py::test_t07_save_then_load_round_trip_preserves_single_rule`
- **Test Type**: Real

---

### 用例编号

ST-SEC-019-001

### 关联需求

§IC `ModelRulesStore.save` POSIX 0o600 · NFR-008 精神延伸 · Feature Design Test Inventory T08

### 测试目标

验证 POSIX 平台下 `save()` 后 `model_rules.json` 文件权限严格为 `0o600`（owner-only RW），防止其他用户读取规则。

### 前置条件

- POSIX 平台；空 store path

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `store.save([ModelRule(tool="claude", model="opus")])` | 落盘 |
| 2 | `mode = os.stat(path).st_mode & 0o777` | 模式提取成功 |
| 3 | 断言 `mode == 0o600` | True |

### 验证点

- world / group 不可读不可写
- `~/.harness/` 隐私边界（即便规则非 secret，也守 NFR-008 精神）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_model_rules_store.py::test_t08_save_sets_posix_mode_0600`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-006

### 关联需求

FR-022 AC-1 · §IC `RuleBackend.decide` · Feature Design Test Inventory T09 · ATS L90 FR-022

### 测试目标

验证 `RuleBackend.decide(ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False))` 返回 `Verdict(verdict="COMPLETED", backend="rule", anomaly=None)` — 健康 ticket 不被误判 ABORT。

### 前置条件

- `harness.dispatch.classifier.RuleBackend` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(exit_code=0, stderr_tail="", stdout_tail="", has_termination_banner=False)` | 构造成功 |
| 2 | `verdict = RuleBackend().decide(req)` | 无异常 |
| 3 | 断言 `verdict.verdict == "COMPLETED"` 且 `verdict.backend == "rule"` 且 `verdict.anomaly is None` | True |

### 验证点

- exit_code=0 + 无 banner + 空 stderr → COMPLETED
- backend 字段标识 rule 路径，非 llm

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_rule_backend.py::test_t09_rule_backend_exit_zero_no_banner_empty_stderr_returns_completed`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-007

### 关联需求

FR-022 AC-2 · §IC `RuleBackend.decide` · Feature Design Test Inventory T10 · Clarification Addendum #3

### 测试目标

验证 stderr 含 `"context window exceeded"` 关键字时（即便 exit_code=1）`RuleBackend.decide` 返回 `Verdict(verdict="RETRY", anomaly="context_overflow", backend="rule")` — 优先级最高（severity 序首位）。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(exit_code=1, stderr_tail="... context window exceeded ...", has_termination_banner=False)` | 构造成功 |
| 2 | `verdict = RuleBackend().decide(req)` | 无异常 |
| 3 | 断言 `verdict.verdict == "RETRY"` 且 `verdict.anomaly == "context_overflow"` | True |

### 验证点

- 正则不区分大小写匹配 `context window` / `exceeded max tokens` / `token limit`
- context_overflow 优先于 exit_code 判定

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_rule_backend.py::test_t10_rule_backend_context_window_stderr_returns_retry_context_overflow`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-008

### 关联需求

§IC `RuleBackend.decide` · Feature Design Test Inventory T11 · Clarification Addendum #3

### 测试目标

验证 stderr 含 `"HTTP 429 rate limit"` 关键字时返回 `Verdict(verdict="RETRY", anomaly="rate_limit", backend="rule")`。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(exit_code=1, stderr_tail="HTTP 429 rate limit hit", has_termination_banner=False)` | 构造成功 |
| 2 | `verdict = RuleBackend().decide(req)` | 无异常 |
| 3 | 断言 `verdict.verdict == "RETRY"` 且 `verdict.anomaly == "rate_limit"` | True |

### 验证点

- rate_limit 关键字（429 / overloaded / rate limit）触发 RETRY
- 优先级低于 context_overflow（与 T07 互斥时 context_overflow 胜）

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_rule_backend.py::test_t11_rule_backend_rate_limit_stderr_returns_retry_rate_limit`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-009

### 关联需求

§IC `RuleBackend.decide` · Feature Design Test Inventory T12

### 测试目标

验证 stderr 含 `"Permission denied"` 关键字时返回 `Verdict(verdict="ABORT", backend="rule")` — 不重试（安全语义）。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(exit_code=1, stderr_tail="Permission denied: /etc/shadow", has_termination_banner=False)` | 构造成功 |
| 2 | `verdict = RuleBackend().decide(req)` | 无异常 |
| 3 | 断言 `verdict.verdict == "ABORT"` | True |

### 验证点

- permission denied 不进入 RETRY 通道（避免触发安全策略循环）
- backend="rule"

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_rule_backend.py::test_t12_rule_backend_permission_denied_returns_abort_no_retry`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-010

### 关联需求

§IC `RuleBackend.decide` · Feature Design Test Inventory T13

### 测试目标

验证未知失败（`exit_code=2, stderr="segfault"`，无 context/rate/perm 关键字）返回 `Verdict(verdict="ABORT", anomaly="skill_error", backend="rule")` — 兜底分类。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(exit_code=2, stderr_tail="segfault at 0x0", has_termination_banner=False)` | 构造成功 |
| 2 | `verdict = RuleBackend().decide(req)` | 无异常 |
| 3 | 断言 `verdict.verdict == "ABORT"` 且 `verdict.anomaly == "skill_error"` | True |

### 验证点

- 未知失败 → skill_error 分类 + ABORT verdict
- 不漏判（不返 COMPLETED）

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_rule_backend.py::test_t13_rule_backend_unknown_failure_returns_abort_skill_error`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-019-003

### 关联需求

§BC `exit_code=None` · §IC `RuleBackend.decide` · Feature Design Test Inventory T14

### 测试目标

验证 `exit_code=None`（unknown 退出码，例如进程被信号杀死）时不被误判为 COMPLETED — 必须返回非-COMPLETED verdict（典型为 ABORT + skill_error）。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = ClassifyRequest(exit_code=None, stderr_tail="", stdout_tail="", has_termination_banner=False)` | 构造成功 |
| 2 | `verdict = RuleBackend().decide(req)` | 无异常 |
| 3 | 断言 `verdict.verdict != "COMPLETED"`（典型 ABORT） | True |

### 验证点

- None 不被等价于 0
- 防止信号杀死的 ticket 被错标 COMPLETED

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_rule_backend.py::test_t14_rule_backend_exit_code_none_is_not_completed`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-019-004

### 关联需求

§BC `stderr_tail 32KB 截断` · §IC `RuleBackend.decide` · Feature Design Test Inventory T15

### 测试目标

验证 stderr 长度超过 32KB 时仅取尾部 — 尾部含 `"context window"` 关键字仍命中 context_overflow 判定。

### 前置条件

- 构造 `stderr_tail` 长度 ≥ 32KB，尾部嵌入 `"context window"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `tail = "x" * 50_000 + " context window exceeded"` | 构造 50KB 字符串 |
| 2 | `req = ClassifyRequest(exit_code=1, stderr_tail=tail, has_termination_banner=False)` | 构造成功 |
| 3 | `verdict = RuleBackend().decide(req)` | 无异常 |
| 4 | 断言 `verdict.anomaly == "context_overflow"` | True |

### 验证点

- 截断保留尾部（命中关键字）
- 头部填充不影响判定

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_rule_backend.py::test_t15_rule_backend_tail_truncation_preserves_trailing_context_window_marker`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-011

### 关联需求

FR-023 · §IC `LlmBackend.invoke` · Feature Design Test Inventory T16 · IFR-004

### 测试目标

验证 `LlmBackend.invoke` 在 respx mock `POST /v1/chat/completions` 返回合法 schema JSON `{verdict:"HIL_REQUIRED",reason:"...",anomaly:null,hil_source:"user_question"}` 时返回 `Verdict(verdict="HIL_REQUIRED", backend="llm")`，无 fallback 警告。

### 前置条件

- respx fixture 已就绪；keyring mock 返 `"sk-test"`
- `harness.dispatch.classifier.LlmBackend` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock POST `<base_url>/chat/completions` 返合法 schema JSON | mock 注册 |
| 2 | 构造 `LlmBackend(preset=ProviderPreset(name="glm",...), keyring=mock_kr)` | 实例化成功 |
| 3 | `verdict = await backend.invoke(req, prompt)` | 无异常 |
| 4 | 断言 `verdict.verdict == "HIL_REQUIRED"` 且 `verdict.backend == "llm"` | True |
| 5 | 断言 audit log 不含 fallback warning | True |

### 验证点

- response_format=json_schema 严格响应解析路径
- backend 字段反映 llm 调用链（非 rule）

### 后置检查

- respx 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_llm_backend.py::test_t16_llm_backend_returns_hil_required_verdict_on_valid_schema`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-012

### 关联需求

FR-023 AC-1 · §IC `LlmBackend.invoke` Raises `ClassifierProtocolError` · §IS flow `FallbackParse` · Feature Design Test Inventory T17

### 测试目标

验证 LLM 返回非合法 JSON 时 `LlmBackend.invoke` 抛 `ClassifierProtocolError`（cause=json_parse_error 或等价描述），上层 `FallbackDecorator` 捕获后降级 rule + audit warning。

### 前置条件

- respx mock 返字符串 `"not json {"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock 返非法 body | 注册 |
| 2 | `await LlmBackend(...).invoke(req, prompt)` | 抛 `ClassifierProtocolError` |
| 3 | 通过 `ClassifierService.classify` 走完整链路 | 返 `Verdict(backend="rule")` |
| 4 | 断言 audit log 至少 1 条 `event="classifier_fallback"` 含 cause | True |

### 验证点

- LlmBackend 解析失败抛 ClassifierProtocolError
- FallbackDecorator 捕获后落 audit
- ClassifierService 返合法 Verdict（backend=rule）

### 后置检查

- respx 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_llm_backend.py::test_t17_llm_backend_raises_protocol_error_on_non_json_body`
- **Test Type**: Real

---

### 用例编号

ST-SEC-019-002

### 关联需求

FR-023 AC-2 · §IC `LlmBackend.invoke` · §IS flow `FallbackSchema` · SEC prompt-injection 防护 · Feature Design Test Inventory T18

### 测试目标

验证 LLM 返合法 JSON 但 verdict 不在枚举（典型 prompt injection 注出，如 `verdict="SHUTDOWN"`）时降级 rule 并 audit；防止 LLM 任意输出被透传成合法状态转移。

### 前置条件

- respx mock 返 `{"verdict":"SHUTDOWN", "reason":"...", "anomaly":null, "hil_source":null}`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock 返越界 verdict | 注册 |
| 2 | `await LlmBackend(...).invoke(req, prompt)` | 抛 `ClassifierProtocolError` |
| 3 | 走 `ClassifierService.classify` 完整链路 | 返 `Verdict(backend="rule")` |
| 4 | 断言 audit `cause` 含 `"verdict_out_of_enum"` 或等价描述 | True |

### 验证点

- 枚举越界 → 协议违反 → fallback
- 非合法值不上浮到 F20 状态机
- 防 prompt injection 攻击面

### 后置检查

- respx 自动清理

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_llm_backend.py::test_t18_llm_backend_raises_protocol_error_on_out_of_enum_verdict`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-013

### 关联需求

§IS flow `FallbackHttp` · §IC `LlmBackend.invoke` Raises `ClassifierHttpError` · Feature Design Test Inventory T19

### 测试目标

验证 respx mock 抛 `httpx.TimeoutException` 时 `LlmBackend.invoke` 抛 `ClassifierHttpError`，上层降级 rule + audit。

### 前置条件

- respx mock 配置 `side_effect=httpx.TimeoutException("...")`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock 抛 TimeoutException | 注册 |
| 2 | `await LlmBackend(...).invoke(req, prompt)` | 抛 `ClassifierHttpError` |
| 3 | 走 `ClassifierService.classify` 完整链路 | 返 `Verdict(backend="rule")` |
| 4 | 断言 audit `cause` 含 `"timeout"` 或 `"http"` | True |

### 验证点

- httpx.TimeoutException 被映射为 ClassifierHttpError
- F20 状态机不被 timeout 阻塞（永不抛契约）

### 后置检查

- respx 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_llm_backend.py::test_t19_llm_backend_raises_http_error_on_timeout`
- **Test Type**: Real

---

### 用例编号

ST-SEC-019-003

### 关联需求

FR-021 AC-3 · §IC `ProviderPresets.validate_base_url` · ATS L89 / L182 SSRF · Feature Design Test Inventory T20

### 测试目标

验证 `ProviderPresets.validate_base_url("https://169.254.169.254/v1")` 抛 `SsrfBlockedError`（云元数据服务 link-local IP 阻断）。

### 前置条件

- `harness.dispatch.classifier.ProviderPresets` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `presets = ProviderPresets()` | 实例化 |
| 2 | `presets.validate_base_url("https://169.254.169.254/v1")` | 抛 `SsrfBlockedError` |
| 3 | 断言异常类名 `SsrfBlockedError` 且 message 含 host 或 link-local 描述 | True |

### 验证点

- AWS / Azure 元数据 IP 169.254.x 被拦截（link-local 169.254.0.0/16）
- 即使 https scheme 也不放行（hostname 不在白名单）

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_provider_presets.py::test_t20_validate_base_url_rejects_link_local_metadata_service`
- **Test Type**: Real

---

### 用例编号

ST-SEC-019-004

### 关联需求

§IC `ProviderPresets.validate_base_url` hostname 子串注入防护 · ATS L89 SSRF · Feature Design Test Inventory T21 · Clarification Addendum #1

### 测试目标

验证 `validate_base_url("http://open.bigmodel.cn.evil.com/v1")` 抛 `SsrfBlockedError` — 防止 hostname 子串误匹配（白名单 hostname 必须精确等于或以 `.<domain>` 结尾）。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `presets.validate_base_url("http://open.bigmodel.cn.evil.com/v1")` | 抛 `SsrfBlockedError` |
| 2 | 断言异常类名 `SsrfBlockedError` | True |

### 验证点

- hostname 解析后必须 `endswith(".open.bigmodel.cn")` 或精确等于
- substring 匹配漏洞被堵
- 即使 host 包含白名单域字符串，子域归属另一根域则拒

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_provider_presets.py::test_t21_validate_base_url_rejects_hostname_substring_injection`
- **Test Type**: Real

---

### 用例编号

ST-SEC-019-005

### 关联需求

§IC `ProviderPresets.validate_base_url` 私网拦截 · ATS L89 SSRF · Feature Design Test Inventory T22 · Clarification Addendum #1

### 测试目标

验证 `validate_base_url("http://10.0.0.1/v1")`（custom provider，HTTP + RFC1918 私网 IP）抛 `SsrfBlockedError`。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `presets.validate_base_url("http://10.0.0.1/v1")` | 抛 `SsrfBlockedError` |

### 验证点

- 10.0.0.0/8 / 172.16.0.0/12 / 192.168.0.0/16 私网网段全拒
- HTTP scheme（非 https）在白名单外被拒

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_provider_presets.py::test_t22_validate_base_url_rejects_rfc1918_private_ip_for_custom_provider`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-014

### 关联需求

FR-021 AC-1 · §IC `ProviderPresets.resolve` · Feature Design Test Inventory T23 · ATS L89 FR-021

### 测试目标

验证 `ProviderPresets.resolve("glm")` 返回 `ProviderPreset(name="glm", base_url="https://open.bigmodel.cn/api/paas/v4/", default_model="glm-4-plus", api_key_user_slot="glm")`。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `preset = ProviderPresets().resolve("glm")` | 无异常 |
| 2 | 断言 `preset.name == "glm"` | True |
| 3 | 断言 `preset.base_url == "https://open.bigmodel.cn/api/paas/v4/"` | True |
| 4 | 断言 `preset.default_model == "glm-4-plus"` | True |
| 5 | 断言 `preset.api_key_user_slot == "glm"` | True |

### 验证点

- 内置 GLM 预设 base_url 与官方文档一致
- model_name / user_slot 字段固定值正确

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_provider_presets.py::test_t23_resolve_glm_returns_expected_preset_fields`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-019-005

### 关联需求

§IC `ProviderPresets.resolve` Raises `ProviderPresetError` · Feature Design Test Inventory T24

### 测试目标

验证 `ProviderPresets.resolve("unknown")` 抛 `ProviderPresetError` — 未知 provider 不被静默接受。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ProviderPresets().resolve("unknown")` | 抛 `ProviderPresetError` |

### 验证点

- 不在 `{glm, minimax, openai, custom}` 枚举的值显式失败
- 防止配置漂移导致默认值 silently 用错

### 后置检查

- 无副作用

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_provider_presets.py::test_t24_resolve_unknown_provider_raises_provider_preset_error`
- **Test Type**: Real

---

### 用例编号

ST-SEC-019-006

### 关联需求

FR-021 AC-1 · §IC `LlmBackend.invoke` · IAPI-014 keyring 消费 · Feature Design Test Inventory T25 · ATS L89 SEC

### 测试目标

验证 `LlmBackend.invoke` 从 `KeyringGateway.get_secret("harness-classifier", "glm")` 取 api_key 并以 `Authorization: Bearer sk-test` header 发出 HTTP 请求；config.json 不含明文 key。

### 前置条件

- mock keyring：`get_secret("harness-classifier","glm") → "sk-test"`
- respx mock 捕获请求 headers

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock keyring 返 `"sk-test"`；respx.mock POST 返合法 schema | 注册 |
| 2 | `await LlmBackend(preset=glm, keyring=mock_kr).invoke(req, prompt)` | 无异常 |
| 3 | 断言 `respx.calls.last.request.headers["Authorization"] == "Bearer sk-test"` | True |
| 4 | 断言 config.json（如已落盘）grep 无 `"sk-test"` 明文 | True |

### 验证点

- api_key 经 keyring 加载，不进 config.json
- Bearer token 格式精确（含 `Bearer ` 前缀）

### 后置检查

- respx 清理；keyring mock 重置

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_llm_backend.py::test_t25_llm_backend_sends_authorization_bearer_from_keyring`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-015

### 关联需求

FR-022 · §IC `ClassifierService.classify` `config.enabled=False` · Feature Design Test Inventory T27 · ATS L90

### 测试目标

验证 `ClassifierService(config=ClassifierConfig(enabled=False, ...)).classify(req_completed)` 直接走 RuleBackend，不调用 LLM；respx 断言零 HTTP 请求。

### 前置条件

- `ClassifierConfig(enabled=False)`；`ClassifyRequest(exit_code=0, stderr_tail="", has_termination_banner=False)`
- respx fixture 已就绪（设置任何 LLM endpoint mock）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `service = ClassifierService(config=ClassifierConfig(enabled=False, ...), prompt_store_path=tmp)` | 实例化成功 |
| 2 | `verdict = await service.classify(req)` | 无异常 |
| 3 | 断言 `verdict.verdict == "COMPLETED"` 且 `verdict.backend == "rule"` | True |
| 4 | 断言 `len(respx.calls) == 0`（LLM 未被调用） | True |

### 验证点

- enabled=False 不调 LLM（节省 API 额度）
- backend 字段固定为 rule

### 后置检查

- respx 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_classifier_service.py::test_t27_classifier_service_enabled_false_uses_rule_only_no_http`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-016

### 关联需求

FR-023 · §IC `PromptStore.get/put` · Feature Design Test Inventory T28 · Clarification Addendum #2

### 测试目标

验证 `PromptStore.put("v1 prompt") → put("v2 prompt")` 后 `get()` 返回 `current="v2 prompt"`、`history` 长度=2、`history[0].rev=1`、`history[1].rev=2`，每条 rev 携带 sha256 hash。

### 前置条件

- 空 `tmp_path` 作为 prompt store path

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `store = PromptStore(path=tmp/"prompts.json")` | 实例化 |
| 2 | `store.put("v1 prompt")` | 落盘 |
| 3 | `store.put("v2 prompt")` | 落盘 |
| 4 | `prompt = store.get()` | 无异常 |
| 5 | 断言 `prompt.current == "v2 prompt"` 且 `len(prompt.history) == 2` 且 `prompt.history[0].rev == 1` 且 `prompt.history[1].rev == 2` | True |
| 6 | 断言每条 history 的 `hash` 为 64 位 hex（sha256） | True |

### 验证点

- v1 履历 append-only（不丢历史）
- rev 递增 1 步长
- hash 为 sha256 hex（节省磁盘且可定位篡改）
- summary 取 first 120 字符

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_prompt_store.py::test_t28_prompt_store_put_then_put_builds_two_history_revs_with_sha256_hash`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-019-006

### 关联需求

§IC `PromptStore.put` Raises `PromptValidationError` · §BC `content` empty · Feature Design Test Inventory T29

### 测试目标

验证 `PromptStore.put("")` 抛 `PromptValidationError` — 空 prompt 被拒（防止 LLM 无 system prompt）。

### 前置条件

- 空 store

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `store.put("")` | 抛 `PromptValidationError` |

### 验证点

- min_length=1 字符校验生效
- 异常显式可识别（非通用 ValueError）

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_prompt_store.py::test_t29_prompt_store_put_empty_raises_prompt_validation_error`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-019-007

### 关联需求

§IC `PromptStore.put` · §BC `content 32KB+1` · Feature Design Test Inventory T30

### 测试目标

验证 `PromptStore.put("x" * 32768 + "y")`（32KB + 1 字节）抛 `PromptValidationError` — 防磁盘膨胀。

### 前置条件

- 空 store

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `oversized = "x" * 32768 + "y"` | 构造成功 |
| 2 | `store.put(oversized)` | 抛 `PromptValidationError` |

### 验证点

- max_length=32KB 上限校验
- 攻击者无法通过保存大 prompt 撑爆磁盘

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_prompt_store.py::test_t30_prompt_store_put_32kb_plus_one_raises_prompt_validation_error`
- **Test Type**: Real

---

### 用例编号

ST-PERF-019-001

### 关联需求

IFR-004 PERF · NFR-004 · §IC `LlmBackend.invoke` 10s timeout · Feature Design Test Inventory T31 · ATS L182 PERF

### 测试目标

验证 `LlmBackend` 内置 `httpx.AsyncClient(timeout=10.0)`：respx mock 延迟 15s 时 `invoke()` 在 10±1s 内抛 `ClassifierHttpError(cause="timeout")`，触发 fallback 返 `Verdict(backend="rule")`；未阻塞超过 NFR-004 预算。

### 前置条件

- respx mock 配置 `side_effect=lambda r: time.sleep(15) + ...` 或等价 timeout 触发

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock 触发 httpx TimeoutException | 注册 |
| 2 | `t0 = time.monotonic()`；`pytest.raises(ClassifierHttpError): await backend.invoke(req, prompt)` | 抛异常 |
| 3 | `elapsed = time.monotonic() - t0`；断言 `elapsed < 11.5`（10s + 容忍） | True |
| 4 | 通过 `ClassifierService.classify` 路径 | 返 `Verdict(backend="rule")` |

### 验证点

- 10s 硬编码 timeout 生效（不被 config 改写）
- F20 spawn-to-classify 不卡死

### 后置检查

- respx 清理

### 元数据

- **优先级**: Critical
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f19_real_http.py::test_f19_t31_real_http_timeout_triggers_rule_fallback`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-017

### 关联需求

ATS INT-025 · §IC `ClassifierService.test_connection` · IFR-004 401 路径

### 测试目标

验证 `ClassifierService.test_connection` 在 respx mock 返 401 Unauthorized 时返回 `TestConnectionResult(ok=False, error_code="401", message=...)` — 不抛异常。

### 前置条件

- respx mock POST 返 401

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock 返 401 | 注册 |
| 2 | `result = await service.test_connection(TestConnectionRequest(provider="glm", base_url="https://open.bigmodel.cn/api/paas/v4/", model_name="glm-4-plus"))` | 不抛异常 |
| 3 | 断言 `result.ok is False` 且 `result.error_code == "401"` | True |

### 验证点

- 401 不冒泡为 5xx 给 UI
- 错误码归一化（test-connection 路径不抛异常）

### 后置检查

- respx 清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_classifier_connection.py::test_t32_test_connection_401_returns_ok_false_with_error_code`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-018

### 关联需求

ATS INT-025 · §IC `ClassifierService.test_connection` · IFR-004 connect-refused 路径

### 测试目标

验证 respx mock `httpx.ConnectError`（连接被拒）时 `test_connection` 返 `TestConnectionResult(ok=False, error_code="connection_refused")`。

### 前置条件

- respx mock 抛 `ConnectError("Connection refused")`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock 抛 ConnectError | 注册 |
| 2 | `result = await service.test_connection(req)` | 不抛 |
| 3 | 断言 `result.error_code == "connection_refused"` | True |

### 验证点

- ConnectError 归一为 connection_refused
- 与 dns_failure 区分（不混淆）

### 后置检查

- respx 清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_classifier_connection.py::test_t33_test_connection_connect_refused_returns_connection_refused_code`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-019

### 关联需求

ATS INT-025 · §IC `ClassifierService.test_connection` · DNS 错误路径

### 测试目标

验证 respx mock `httpx.ConnectError("[Errno -2] getaddrinfo failed")` 时 `test_connection` 返 `TestConnectionResult(ok=False, error_code="dns_failure")`。

### 前置条件

- respx mock 抛 ConnectError 携带 `getaddrinfo` 描述

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock 抛 ConnectError 含 `"getaddrinfo failed"` | 注册 |
| 2 | `result = await service.test_connection(req)` | 不抛 |
| 3 | 断言 `result.error_code == "dns_failure"` | True |

### 验证点

- DNS 解析失败被识别（含 getaddrinfo / Name or service not known）
- 不被并入 connection_refused 桶

### 后置检查

- respx 清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_classifier_connection.py::test_t34_test_connection_dns_failure_returns_dns_failure_code`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-020

### 关联需求

§IC `ModelRulesStore` 持久化 round-trip · Feature Design Test Inventory T35 · INTG/fs

### 测试目标

验证 `ModelRulesStore.save()` 经新实例 `load()` 后内容一致（跨进程模拟：新 Store 对象、相同 path）。

### 前置条件

- tmp_path

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `store_a = ModelRulesStore(path=tmp/"rules.json")`；`store_a.save([ModelRule(skill="X",tool="claude",model="opus"), ModelRule(skill="Y",tool="opencode",model="sonnet")])` | 落盘 |
| 2 | `store_b = ModelRulesStore(path=tmp/"rules.json")`；`rules = store_b.load()` | 加载成功 |
| 3 | 断言 `len(rules)==2` 且字段顺序一致 | True |

### 验证点

- 跨实例持久化无丢
- temp+rename 原子写不留残文件

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f19_real_fs.py::test_f19_t35_real_fs_model_rules_persist_across_store_instances`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-021

### 关联需求

IAPI-014 · §IC `LlmBackend.invoke` · keyring fail backend · Feature Design Test Inventory T36

### 测试目标

验证使用真实 `keyring.backends.fail.Keyring` backend 时 `LlmBackend.invoke` 抛 `ClassifierHttpError`（keyring 失败被映射），上层 fallback 到 rule。

### 前置条件

- 安装 `keyring` 库；测试时显式设 `keyring.set_keyring(keyring.backends.fail.Keyring())`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 替换 keyring backend 为 fail | 注册 |
| 2 | 走 `ClassifierService.classify` 完整链路（enabled=True） | 返 `Verdict(backend="rule")` |
| 3 | 断言 audit log 含 keyring 失败 cause | True |

### 验证点

- keyring 失败不冒泡为 500（永不抛契约）
- audit cause 可定位 keyring 故障

### 后置检查

- keyring backend 复位

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f19_real_keyring.py::test_f19_t36_real_keyring_fail_backend_triggers_rule_fallback`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-022

### 关联需求

§IC `ClassifierService.classify` 永不抛契约 · Feature Design Test Inventory T37 · Clarification Addendum #4

### 测试目标

验证 respx + keyring + prompt_store 三者均故障时 `ClassifierService.classify` 仍返合法 `Verdict(backend="rule")`，不抛任何异常 — 保证 F20 状态机不因下游故障死锁。

### 前置条件

- respx 抛 ConnectError；keyring fail；prompt_store 路径不可读

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock 三者均故障 | 注册 |
| 2 | `verdict = await service.classify(req)` | **不抛异常** |
| 3 | 断言 `isinstance(verdict, Verdict)` 且 `verdict.backend == "rule"` | True |

### 验证点

- 永不抛（IAPI-010 契约）
- audit 至少 1 行 fallback warning

### 后置检查

- 全部 mock 复位

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_classifier_service.py::test_t37_classifier_service_never_raises_even_on_all_backends_failing`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-023

### 关联需求

FR-019 · IAPI-002 `GET /api/settings/model_rules` · Feature Design Test Inventory T38

### 测试目标

验证初次 GET（无文件）返回 200 + 空数组 `[]`；路由已被注册到 `harness.api:app`。

### 前置条件

- FastAPI `TestClient(harness.api.app)`；`monkeypatch.setenv("HARNESS_HOME", tmp_path)`；`tmp_path/model_rules.json` 不存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client = TestClient(app)`；`response = client.get("/api/settings/model_rules")` | 无异常 |
| 2 | 断言 `response.status_code == 200` | True |
| 3 | 断言 `response.json() == []` | True |

### 验证点

- 路由已注册（include_router）
- 缺失文件 → 空数组（非 500）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_api_routes.py::test_t38_get_model_rules_initially_returns_empty_list`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-024

### 关联需求

FR-019 · IAPI-002 `PUT /api/settings/model_rules` · Feature Design Test Inventory T39

### 测试目标

验证 PUT body `[{skill:"requirements",tool:"claude",model:"opus"}]` 返回 200 + 同 body；再 GET 返回同内容（持久化生效）。

### 前置条件

- 同 ST-FUNC-019-023

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.put("/api/settings/model_rules", json=[{"skill":"requirements","tool":"claude","model":"opus"}])` | 200 |
| 2 | 断言 response body 等同输入 | True |
| 3 | `client.get("/api/settings/model_rules")` | 200 |
| 4 | 断言 GET response body 同 PUT body | True |

### 验证点

- PUT 完整替换语义（非追加）
- GET ↔ PUT round-trip 一致

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_api_routes.py::test_t39_put_model_rules_persists_and_round_trips`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-025

### 关联需求

IAPI-002 `PUT /api/settings/model_rules` 校验 · Feature Design Test Inventory T40

### 测试目标

验证 PUT body `[{tool:"gpt", ...}]`（tool 不在枚举）返回 422 + `error_code="validation"`。

### 前置条件

- 同 ST-FUNC-019-023

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.put("/api/settings/model_rules", json=[{"tool":"gpt","model":"foo"}])` | 422 |
| 2 | 断言 `response.json()["detail"]["error_code"] == "validation"` | True |

### 验证点

- pydantic ValidationError 经路由层捕获并归一为 422
- 非 200 时不持久化（post 检查文件 mtime 不变）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_api_routes.py::test_t40_put_model_rules_rejects_invalid_tool_with_validation_error`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-026

### 关联需求

FR-033 v1 · IAPI-002 `GET /api/prompts/classifier` · Feature Design Test Inventory T41

### 测试目标

验证初次 GET（无 prompt 文件）返回 200 + `{current:<内置默认 prompt>, history:[]}`，不抛 500。

### 前置条件

- 同 ST-FUNC-019-023；`tmp_path/classifier_prompt.json` 不存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `response = client.get("/api/prompts/classifier")` | 200 |
| 2 | 断言 `response.json()["current"]` 非空字符串 | True |
| 3 | 断言 `response.json()["history"] == []` | True |

### 验证点

- 缺失文件 → 内置默认（非 500）
- history 起始为空数组

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_api_routes.py::test_t41_get_prompts_classifier_returns_default_with_empty_history`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-027

### 关联需求

FR-033 v1 · IAPI-002 `PUT /api/prompts/classifier` · Feature Design Test Inventory T42 · ATS INT-019

### 测试目标

验证 PUT `{content:"new"}` 后 GET 返回 `current="new"`，`history` 长度=1（首次保存追加 rev=1）。

### 前置条件

- 同 ST-FUNC-019-026

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.put("/api/prompts/classifier", json={"content":"new"})` | 200 |
| 2 | `data = client.get("/api/prompts/classifier").json()` | 获取成功 |
| 3 | 断言 `data["current"] == "new"` 且 `len(data["history"]) == 1` 且 `data["history"][0]["rev"] == 1` | True |

### 验证点

- 首次 PUT 即追加首条 history
- 再次 PUT 应产生 rev=2（INT-019 多版本场景）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_api_routes.py::test_t42_put_prompts_classifier_appends_history_rev`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-028

### 关联需求

FR-033 SEC · §IC `PromptStore` 路径越界守卫 · Feature Design Test Inventory T43

### 测试目标

验证 `PromptStore` 拒绝跳出 `HARNESS_HOME` 的路径（`Path("../../etc/passwd")`）— 抛 `PromptStoreError`，防止任意文件写入。

### 前置条件

- `HARNESS_HOME=tmp/.harness` 设置

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bad = Path("../../etc/passwd")`；`store = PromptStore(path=bad)` | 实例化或访问 |
| 2 | `store.put("evil")` 或 `store.get()` | 抛 `PromptStoreError` |

### 验证点

- 路径必须在 HARNESS_HOME 子树
- 防 path traversal 写到任意位置

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_prompt_store.py::test_t43_prompt_store_refuses_path_outside_harness_home`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-029

### 关联需求

§IC `FallbackDecorator.invoke` audit log · Feature Design Test Inventory T44 · INT-005

### 测试目标

验证 LLM HTTP 5xx 时 `FallbackDecorator` 触发 RuleBackend 并 audit log 追加 `event="classifier_fallback"` 条目（cause 含 http / 5xx 描述）。

### 前置条件

- respx mock POST 返 502

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 注册 audit_sink 列表 `events: list[dict] = []`，`audit_sink=events.append` | 就绪 |
| 2 | respx.mock 返 502 | 注册 |
| 3 | `verdict = await service.classify(req)`；service 注入 audit_sink | 不抛 |
| 4 | 断言 `verdict.backend == "rule"` | True |
| 5 | 断言至少 1 条 `events[i]["event"] == "classifier_fallback"` 且 cause 含 http / 5xx 关键字 | True |

### 验证点

- audit 行可定位降级原因（INT-005 跨特性集成）
- backend=rule 反映 fallback 命中

### 后置检查

- respx 清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_classifier_service.py::test_t44_classifier_service_emits_audit_fallback_on_http_5xx`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-030

### 关联需求

§IC `ClassifierService.test_connection` SSRF · Feature Design Test Inventory T45 · ATS INT-016 / L182

### 测试目标

验证 `test_connection` body `base_url="http://127.0.0.1:8080/v1"` + `provider="custom"` 返回 `TestConnectionResult(ok=False, error_code="ssrf_blocked")` — 测试连通路径不绕过 SSRF 校验。

### 前置条件

- 同 ST-FUNC-019-017；provider=custom

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `req = TestConnectionRequest(provider="custom", base_url="http://127.0.0.1:8080/v1", model_name="x")` | 构造 |
| 2 | `result = await service.test_connection(req)` | 不抛 |
| 3 | 断言 `result.ok is False` 且 `result.error_code == "ssrf_blocked"` | True |

### 验证点

- 测试连通路径与保存路径共用 SSRF 守卫
- loopback 在 custom provider 视为不放行

### 后置检查

- 无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_classifier_connection.py::test_t45_test_connection_rejects_loopback_custom_base_url_with_ssrf_error`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-031

### 关联需求

§DA seq msg `LlmBackend→HttpApi` · §IC LlmBackend.invoke 严格 schema · Feature Design Test Inventory T46 · IFR-004

### 测试目标

验证 `LlmBackend.invoke` 发出的 HTTP request 含 `Authorization: Bearer <key>` header 与 body `response_format.type=="json_schema"` + `strict=true`（保证 verdict 枚举越界即触发 fallback，闭合 T18 路径）。

### 前置条件

- respx 捕获 last call；keyring mock 返 `"sk-x"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx.mock 返合法 schema response | 注册 |
| 2 | `await backend.invoke(req, prompt)` | 无异常 |
| 3 | 断言 `last_call.request.headers["Authorization"]` 以 `"Bearer "` 起头 | True |
| 4 | 断言 `body["response_format"]["type"] == "json_schema"` | True |
| 5 | 断言 `body["response_format"]["json_schema"]["strict"] is True` | True |

### 验证点

- json_schema strict 模式硬接线
- Authorization header 透传 keyring secret

### 后置检查

- respx 清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_llm_backend.py::test_t46_llm_backend_request_body_declares_strict_json_schema`
- **Test Type**: Real

---

### 用例编号

ST-SEC-019-008

### 关联需求

FR-021 AC-1 · NFR-008 · `ClassifierConfig` `extra="forbid"` 守卫 · Feature Design Test Inventory T26 · ATS L89 SEC

### 测试目标

验证 PUT `/api/settings/classifier` body 含明文 `api_key="sk-..."` 字段被 pydantic `extra="forbid"` 拒（422），不持久化到 `~/.harness/classifier_config.json`。

### 前置条件

- 同 ST-FUNC-019-023；`tmp_path/classifier_config.json` 不存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `body = {"enabled":True,"provider":"glm","base_url":"https://open.bigmodel.cn/api/paas/v4/","model_name":"glm-4-plus","api_key":"sk-leaked"}` | 构造 |
| 2 | `response = client.put("/api/settings/classifier", json=body)` | 422 |
| 3 | 断言 `response.status_code == 422` | True |
| 4 | 断言 `tmp_path/classifier_config.json` 不存在或不含 `"sk-leaked"` 明文 | True |

### 验证点

- ClassifierConfig 仅接受 `api_key_ref` 间接指针，不接受明文 `api_key`
- forbid 字段守卫与 NFR-008 leak detector 双保险

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_secret_leak.py::test_t26_put_classifier_settings_refuses_plaintext_api_key`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-032

### 关联需求

§IC `PUT /api/prompts/classifier` 错误路径覆盖（malformed JSON）

### 测试目标

验证 PUT prompts/classifier body 非合法 JSON 时返回 400（非 5xx），错误明确归类为 client error。

### 前置条件

- 同 ST-FUNC-019-026

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.put("/api/prompts/classifier", content=b"not json {", headers={"Content-Type":"application/json"})` | 400 |
| 2 | 断言 `response.status_code == 400` | True |

### 验证点

- 非法 JSON 不被吞为 500
- detail 字段含 "invalid JSON" 描述

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t47_put_prompt_rejects_malformed_json_body_with_400`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-033

### 关联需求

§IC `PUT /api/prompts/classifier` extra 字段守卫

### 测试目标

验证 PUT body 含未知字段（pydantic `extra="forbid"`）返回 422 + `error_code="validation"`。

### 前置条件

- 同 ST-FUNC-019-026

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.put("/api/prompts/classifier", json={"content":"x","unknown":42})` | 422 |
| 2 | 断言 `response.status_code == 422` 且 detail 含 validation 描述 | True |

### 验证点

- extra="forbid" 生效
- 未知字段不悄悄落盘

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t48_put_prompt_rejects_extra_fields_with_422`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-034

### 关联需求

§IC API `PUT /api/prompts/classifier` 32KB+1 上限

### 测试目标

验证 API 层 PUT prompts/classifier `content` 长度 > 32KB 时返回 422（PromptValidationError 经路由映射）。

### 前置条件

- 同 ST-FUNC-019-026

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.put("/api/prompts/classifier", json={"content":"x"*32769})` | 422 |
| 2 | 断言 `response.status_code == 422` | True |

### 验证点

- API 层不接受越界 prompt
- 与 PromptStore 层（ST-BNDRY-019-007）行为一致

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t49_put_prompt_oversized_content_returns_422`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-035

### 关联需求

§IC `GET /api/prompts/classifier` corrupt-file fallback

### 测试目标

验证 prompt 文件含非法 JSON 时 GET 返回 500（路由捕获 `PromptStoreCorruptError` → HTTPException 500 + detail）。

### 前置条件

- `tmp_path/classifier_prompt.json` 写入 `"corrupt"`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 故意写入非法 JSON | 落盘 |
| 2 | `response = client.get("/api/prompts/classifier")` | 500 |
| 3 | 断言 `response.status_code == 500` 且 detail 非空 | True |

### 验证点

- 文件腐坏不被静默吞掉
- 500 + 显式 detail 利于排障

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t50_get_prompt_corrupt_file_returns_500_with_detail`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-036

### 关联需求

§IC `PUT /api/prompts/classifier` IO 失败映射

### 测试目标

验证 PromptStore 写盘 IO 失败（mock `Path.write_text` 抛 OSError）时 API 层返回 500 + detail 非空。

### 前置条件

- monkeypatch `Path.write_text` 抛 OSError

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock IO 失败 | 注册 |
| 2 | `client.put("/api/prompts/classifier", json={"content":"x"})` | 500 |

### 验证点

- IO 异常被 PromptStoreError 映射为 500
- 不静默丢失保存请求

### 后置检查

- mock 复位

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t51_put_prompt_store_io_failure_returns_500`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-037

### 关联需求

§IC `GET /api/settings/model_rules` corrupt-file 路径

### 测试目标

验证 model_rules.json 含非法 JSON 时 GET 返回 500（`ModelRulesCorruptError` → HTTPException 500）。

### 前置条件

- `tmp_path/model_rules.json` 写非法 JSON

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 写非法 JSON | 落盘 |
| 2 | `response = client.get("/api/settings/model_rules")` | 500 |

### 验证点

- 文件腐坏触发 500（不返空数组诱导用户继续操作）

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t52_get_model_rules_corrupt_file_returns_500`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-038

### 关联需求

§IC `PUT /api/settings/model_rules` malformed body / non-list

### 测试目标

验证 PUT model_rules body 非合法 JSON 时返回 400；body 是非数组（dict/标量）时返回 422。

### 前置条件

- 同 ST-FUNC-019-023

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.put("/api/settings/model_rules", content=b"not json")` | 400 |
| 2 | `client.put("/api/settings/model_rules", json={"not":"list"})` | 422 |

### 验证点

- 区分 client JSON 错误（400）vs schema 错误（422）
- non-list 不被静默接受

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t53_put_model_rules_malformed_body_returns_400`、`tests/test_f19_coverage_supplement.py::test_t54_put_model_rules_non_list_payload_returns_422`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-039

### 关联需求

§IC `GET /api/settings/classifier` 默认 + persist + corrupt 三态

### 测试目标

验证 GET classifier config 三态：(a) 文件不存在 → 返内置 GLM 默认；(b) 文件存在 → 读取并返；(c) 文件腐坏 → 返默认（不 500）。

### 前置条件

- 同 ST-FUNC-019-023

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 文件不存在状态 GET | 200 + provider="glm"、base_url 含 open.bigmodel.cn |
| 2 | 写入合法 ClassifierConfig 后 GET | 返该值 |
| 3 | 写入腐坏 JSON 后 GET | 返默认（不 500） |

### 验证点

- GET classifier 用户体验稳定（不因配置腐坏而 500）
- 默认 GLM endpoint 为内置安全值

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t55_get_classifier_config_returns_glm_default_when_file_absent`、`::test_t56_get_classifier_config_reads_persisted_value_from_disk`、`::test_t57_get_classifier_config_returns_default_on_corrupt_file`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-040

### 关联需求

§IC `PUT /api/settings/classifier` round-trip + 错误映射

### 测试目标

验证 PUT classifier config 三场景：(a) malformed JSON → 400；(b) schema 不符（缺必填）→ 422；(c) 合法 PUT 后 GET 等同输入。

### 前置条件

- 同 ST-FUNC-019-023

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.put("/api/settings/classifier", content=b"not json")` | 400 |
| 2 | `client.put("/api/settings/classifier", json={"foo":"bar"})` | 422 |
| 3 | `client.put("/api/settings/classifier", json={"enabled":True,"provider":"glm","base_url":"https://open.bigmodel.cn/api/paas/v4/","model_name":"glm-4-plus"})` | 200 |
| 4 | `client.get("/api/settings/classifier")` 返同 body（无 api_key） | True |

### 验证点

- PUT/GET round-trip 完整
- 客户端 vs schema 错误码区分

### 后置检查

- `tmp_path` 自动清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t58_put_classifier_config_malformed_body_returns_400`、`::test_t59_put_classifier_config_schema_mismatch_returns_422`、`::test_t60_put_classifier_config_persists_to_disk_and_round_trips`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-041

### 关联需求

§IC `POST /api/settings/classifier/test` 错误路径合集（malformed / missing fields / SSRF / timeout / 5xx / 200 / keyring 错）

### 测试目标

验证 test-connection 路由完整错误路径：(a) malformed body → 400；(b) 缺字段 → 422；(c) 内网 IP → ssrf_blocked；(d) 200 OK → ok=true 含 latency；(e) 5xx → connection_refused；(f) timeout → error_code="timeout"；(g) 通用 HTTPError → connection_refused；(h) keyring 抛异常仍继续探测（best-effort）。

### 前置条件

- 同 ST-FUNC-019-017

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `client.post("/api/settings/classifier/test", content=b"not json")` | 400 |
| 2 | `client.post("/api/settings/classifier/test", json={})` | 422 |
| 3 | post body `provider="custom" base_url="http://10.0.0.1/v1"` | result.error_code == "ssrf_blocked" |
| 4 | respx.mock 返 200 → post | result.ok=True 且 result.latency_ms 非空 |
| 5 | respx.mock 返 502 → post | result.error_code == "connection_refused" |
| 6 | respx.mock 抛 TimeoutException → post | result.error_code == "timeout" |
| 7 | respx.mock 抛通用 HTTPError → post | result.error_code == "connection_refused" |
| 8 | mock keyring `get_secret` 抛异常；mock OK 200 → post | result.ok=True（不阻塞） |

### 验证点

- 全 6 类错误码覆盖（INT-025 闭环）
- keyring 失败 best-effort 不阻塞

### 后置检查

- respx + keyring mock 复位

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t61_post_test_connection_malformed_body_returns_400`、`::test_t62_post_test_connection_missing_fields_returns_422`、`::test_t63_post_test_connection_ssrf_blocked_for_internal_ip`、`::test_t67_test_connection_timeout_returns_timeout_error_code`、`::test_t68_test_connection_generic_httperror_returns_connection_refused`、`::test_t69_test_connection_5xx_returns_connection_refused_with_latency`、`::test_t70_test_connection_200_returns_ok_true_with_latency`、`::test_t71_test_connection_continues_when_keyring_raises`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-042

### 关联需求

§IC `ClassifierService.classify` preset_resolve_error / 意外异常 / prompt_store 腐坏 三态防御

### 测试目标

验证 `classify` 内部 preset 解析失败、Decorator 抛意外异常、PromptStore 腐坏 三态时仍返合法 `Verdict(backend="rule")` + audit 跟踪原因，符合 §Service §3 永不抛契约。

### 前置条件

- 各别 mock 注入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `presets.resolve` mock 抛异常 → classify | verdict.backend == "rule" + audit `cause="preset_resolve_error"` |
| 2 | FallbackDecorator.invoke mock 抛 RuntimeError → classify | verdict.backend == "rule" + audit `cause="unexpected_error"` |
| 3 | prompt_store.get mock 抛异常 → classify（enabled=True） | 默认 prompt 兜底；流程继续不崩 |

### 验证点

- 三种内部子组件故障均被 service 层兜底
- audit 行可定位故障源（cause 字段）

### 后置检查

- mock 复位

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t64_classify_preset_resolve_error_audits_and_falls_back_to_rule`、`::test_t65_classify_catches_unexpected_decorator_exception_and_audits`、`::test_t66_classify_tolerates_prompt_store_corruption_and_uses_default`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-043

### 关联需求

§IC `FallbackDecorator.invoke` 行为合集（protocol_error 透传 + 意外异常兜底 + 成功透传）

### 测试目标

验证 `FallbackDecorator.invoke` 三态：(a) primary 抛 ClassifierProtocolError → audit cause=protocol_error + RuleBackend；(b) primary 抛意外 RuntimeError → audit cause=unexpected_error + RuleBackend；(c) primary 成功 → 透传 verdict（不 audit）。

### 前置条件

- mock primary / fallback / audit_sink

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | primary 抛 ClassifierProtocolError | verdict.backend=="rule" + audit cause 含 protocol |
| 2 | primary 抛 RuntimeError | verdict.backend=="rule" + audit cause 含 unexpected |
| 3 | primary 返合法 Verdict(backend="llm") | 透传，无 audit 调用 |

### 验证点

- 不同异常类型 cause 字段可区分
- 成功路径无副作用 audit

### 后置检查

- mock 复位

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t72_fallback_decorator_audits_protocol_error_with_cause`、`::test_t73_fallback_decorator_catches_unexpected_exception_as_fallback`、`::test_t74_fallback_decorator_passes_through_successful_llm_verdict`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-044

### 关联需求

§IC `LlmBackend.invoke` 异常映射表（HTTP/Protocol/Keyring 全谱系）

### 测试目标

验证 `LlmBackend.invoke` 在以下异常入口下抛对应类：ConnectError → ClassifierHttpError；通用 HTTPError → ClassifierHttpError；非 JSON 响应 → ClassifierProtocolError；缺 choices → ClassifierProtocolError；assistant content 是数组 → ClassifierProtocolError；anomaly 越界 → ClassifierProtocolError；reason 为空 → ClassifierProtocolError；keyring 抛 → ClassifierHttpError(cause=keyring)。

### 前置条件

- respx + keyring mock

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx 抛 ConnectError → invoke | ClassifierHttpError |
| 2 | respx 抛通用 HTTPError → invoke | ClassifierHttpError |
| 3 | response 含非 JSON envelope → invoke | ClassifierProtocolError |
| 4 | response 缺 choices → invoke | ClassifierProtocolError |
| 5 | assistant content=array → invoke | ClassifierProtocolError |
| 6 | anomaly 不在枚举（如 "rogue"） → invoke | ClassifierProtocolError |
| 7 | reason="" → invoke | ClassifierProtocolError |
| 8 | keyring.get_secret 抛 → invoke | ClassifierHttpError 含 keyring 描述 |

### 验证点

- 完整异常映射表（保证 fallback 链稳定）
- protocol vs http 异常正确区分

### 后置检查

- 全部 mock 复位

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t75_llm_backend_raises_http_error_on_connect_error`、`::test_t76_llm_backend_raises_http_error_on_generic_http_error`、`::test_t77_llm_backend_raises_protocol_error_on_non_json_envelope`、`::test_t78_llm_backend_raises_protocol_error_on_missing_choices`、`::test_t79_llm_backend_raises_protocol_error_when_assistant_is_array`、`::test_t80_llm_backend_raises_protocol_error_on_anomaly_out_of_enum`、`::test_t81_llm_backend_raises_protocol_error_on_empty_reason`、`::test_t82_llm_backend_maps_keyring_failure_to_http_error_keyring_cause`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-045

### 关联需求

§IC `ProviderPresets.validate_base_url` 协议 / 域 / 子域守卫合集

### 测试目标

验证 validate_base_url 的边界守卫：(a) 缺 scheme 拒；(b) 白名单域使用 http 拒（必须 https，loopback 例外）；(c) 白名单子域 https 通过；(d) custom DNS host 用 http 拒。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `validate_base_url("open.bigmodel.cn/api")` | SsrfBlockedError（缺 scheme） |
| 2 | `validate_base_url("http://api.openai.com/v1")` | SsrfBlockedError（白名单域必须 https） |
| 3 | `validate_base_url("https://eu.api.openai.com/v1")` | 通过（子域） |
| 4 | `validate_base_url("http://example.com/v1")` (custom) | SsrfBlockedError |

### 验证点

- 协议守卫（https only on whitelist）
- 子域 endswith 匹配
- custom DNS host 必须 https（loopback 例外）

### 后置检查

- 无副作用

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t83_validate_base_url_rejects_scheme_missing`、`::test_t84_validate_base_url_rejects_http_scheme_for_whitelist_domain`、`::test_t85_validate_base_url_accepts_whitelist_subdomain_over_https`、`::test_t86_validate_base_url_rejects_http_scheme_for_custom_dns_host`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-046

### 关联需求

§IC `ProviderPresets.list` / `ModelRulesStore` 边界 / `PromptStore` 边界 合集（覆盖率补强）

### 测试目标

合并底层组件多个边角案例的合集用例：(a) ProviderPresets.list 返 4 个 provider 含 custom；(b) ModelRulesStore.load 缺文件 / 空白文件返空数组；(c) ModelRulesStore.load 字典根 / schema 不匹配抛 corrupt；(d) ModelRulesStore.save 保留全部规则顺序；(e) PromptStore.get 空白文件返默认 / 腐坏 JSON 抛 corrupt；(f) PromptStore.put 覆盖腐坏文件 / parent mkdir 失败 → PromptStoreError；(g) `path` property 与构造路径一致。

### 前置条件

- 各种 tmp_path 状态

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ProviderPresets().list()` | 含 4 个 ProviderPreset 且包含 name="custom" |
| 2 | 缺文件 → store.load() | [] |
| 3 | 空白文件 → store.load() | [] |
| 4 | 字典根 JSON → store.load() | ModelRulesCorruptError |
| 5 | schema 不匹配 → store.load() | ModelRulesCorruptError |
| 6 | save([rule1, rule2, rule3]) → load() | 顺序与字段全保留 |
| 7 | store.path 与构造时一致 | True |
| 8 | PromptStore 空白文件 → get() | 默认 prompt（current 非空、history=[]） |
| 9 | PromptStore 腐坏 JSON → get() | PromptStoreCorruptError |
| 10 | PromptStore 腐坏 + put("v") | 覆盖成功 |
| 11 | PromptStore parent mkdir 失败 mock → put | PromptStoreError |
| 12 | PromptStore.path 与构造时一致 | True |

### 验证点

- 覆盖率补强用例集（保证 ≥98%/84% 覆盖率达标）
- 各 store 行为对边界 / 错误情形稳定

### 后置检查

- mock 复位；`tmp_path` 自动清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_coverage_supplement.py::test_t87_list_returns_all_four_providers_including_custom`、`::test_t88_rules_store_load_missing_file_returns_empty_list`、`::test_t89_rules_store_load_whitespace_file_returns_empty_list`、`::test_t90_rules_store_load_dict_root_raises_corrupt_error`、`::test_t91_rules_store_load_schema_mismatch_raises_corrupt_error`、`::test_t92_rules_store_save_preserves_all_rules_in_order`、`::test_t93_rules_store_path_property_returns_constructor_path`、`::test_t94_prompt_store_get_whitespace_file_returns_default_prompt`、`::test_t95_prompt_store_get_corrupt_json_raises_prompt_store_corrupt_error`、`::test_t96_prompt_store_put_overwrites_corrupt_existing_file`、`::test_t97_prompt_store_put_parent_mkdir_failure_raises_prompt_store_error`、`::test_t98_prompt_store_path_property_matches_constructor`
- **Test Type**: Real

---

<!-- ============================================================ -->
<!-- Wave 3 增量（2026-04-25）：MiniMax OpenAI-compat strict-schema -->
<!-- bypass + preset capability 位 + tolerant parse                -->
<!-- 新增 6 条 ST 用例，覆盖 8 条新 AC + 1 IFR-mod + 1 ASM         -->
<!-- ============================================================ -->

### 用例编号

ST-FUNC-019-047

### 关联需求

FR-021 AC-4/5/6 · §IC `ProviderPresets.resolve` + effective_strict 计算 · `ProviderPreset.supports_strict_schema` · `ClassifierConfig.strict_schema_override` · Feature Design Test Inventory T47 · Wave 3 增量

### 测试目标

验证（a）4 个内置 ProviderPreset 的 `supports_strict_schema` 能力位默认值正确（GLM/OpenAI/custom=True、MiniMax=False）；（b）`ClassifierConfig.strict_schema_override` 接受 True/False/None 三态且默认 None；（c）`effective_strict = override if override is not None else preset.supports_strict_schema` 合并逻辑在 5 行真值表上行为正确（None 沿用 preset、True/False 显式覆写优先于 preset）。

### 前置条件

- `.venv` 激活；`harness.dispatch.classifier.ProviderPresets` / `ProviderPreset` / `ClassifierConfig` 可导入
- 不依赖磁盘 / 网络

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `presets = ProviderPresets()`；分别 `presets.resolve("glm" / "openai" / "custom" / "minimax")` | 4 个 ProviderPreset 对象返回；每个具备 `supports_strict_schema` 字段 |
| 2 | 断言 `glm.supports_strict_schema is True` / `openai.supports_strict_schema is True` / `custom.supports_strict_schema is True` / `minimax.supports_strict_schema is False` | 4 行全部 True |
| 3 | 构造 `ClassifierConfig(enabled=True, provider="minimax", base_url="https://api.minimax.chat/v1/", model_name="MiniMax-M2.7-highspeed")`；不传 `strict_schema_override` | 字段默认值为 `None` |
| 4 | 上同 base 三次构造，分别传 `strict_schema_override=True / False / None` | 字段保留传入值；None / True / False 三态被接受 |
| 5 | 对 5 组合 `(provider, override) ∈ {("glm",None),("glm",False),("glm",True),("minimax",None),("minimax",True)}` 求 `effective_strict` | 分别为 True / False / True / False / True |

### 验证点

- ProviderPreset 数据类含 `supports_strict_schema: bool` 字段
- 4 个内置 preset 的能力位默认值与 design §6.1.4 表一致（MiniMax=False 是 Wave 3 关键差异）
- ClassifierConfig.strict_schema_override 三态合法（不报 extra_forbidden / type error）
- effective_strict 合并语义：None 沿用 preset；True/False 覆写优先于 preset

### 后置检查

- 内存对象，无副作用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_wave3_strict_schema_capability.py::test_t47a_provider_preset_model_declares_supports_strict_schema_field`、`::test_t47b_glm_preset_supports_strict_schema_is_true`、`::test_t47c_openai_preset_supports_strict_schema_is_true`、`::test_t47d_custom_preset_supports_strict_schema_is_true`、`::test_t47e_minimax_preset_supports_strict_schema_is_false`、`::test_t47f_classifier_config_strict_schema_override_defaults_to_none`、`::test_t47g_classifier_config_strict_schema_override_accepts_bool_tri_state`、`::test_t47_effective_strict_truth_table[glm_none_preset_wins_true]`、`::test_t47_effective_strict_truth_table[glm_false_override_coerces_off]`、`::test_t47_effective_strict_truth_table[glm_true_override_stays_on]`、`::test_t47_effective_strict_truth_table[minimax_none_preset_wins_false]`、`::test_t47_effective_strict_truth_table[minimax_true_override_forces_on]`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-048

### 关联需求

FR-023 AC-3 · IFR-004 AC-mod · §IC `LlmBackend.invoke` 双路径 body 构造 · Feature Design Test Inventory T48 · Wave 3 增量

### 测试目标

验证 `effective_strict=False` 时 `LlmBackend.invoke` 构造的 HTTP request：(a) body **不含** `response_format` 字段；(b) system message `content` 末尾追加固定 `_JSON_ONLY_SUFFIX` 常量（prompt-only JSON 约束）；(c) URL / method / Authorization header 与 strict-on 路径完全一致（IFR-004 AC-mod 协议根不变）。

### 前置条件

- `.venv` 激活；respx 可用以捕获请求 body
- `harness.dispatch.classifier.LlmBackend` / `_JSON_ONLY_SUFFIX` 可导入
- keyring fixture 注入合法 api_key

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `LlmBackend`，注入 `effective_strict=False`；respx mock POST 任意 chat completions 端点返回合法 JSON envelope | mock 安装成功 |
| 2 | `await backend.invoke(req, prompt="<system prompt>")`；从 respx 捕获请求 | request 解析为 dict |
| 3 | 断言 `"response_format" not in body` | True（strict-off 不发送 schema 字段） |
| 4 | 取 system message `content`，断言 `content.endswith(_JSON_ONLY_SUFFIX)` | True |
| 5 | 比对 strict-on（`effective_strict=True`）路径的请求：URL、HTTP method、`Authorization: Bearer <key>` header 是否与 strict-off 路径一致 | URL/method/Auth 完全相同 |

### 验证点

- strict-off 分支彻底跳过 `response_format` 键发送（避免触发 MiniMax 协议错误）
- system message 末尾 JSON-only suffix 由实现端拼接，调用方 prompt 未变
- IFR-004 协议根（URL/method/Authorization）未因 strict-off 而漂移

### 后置检查

- respx 路由复位

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_wave3_llm_strict_off.py::test_t48a_strict_off_body_omits_response_format_key`、`::test_t48b_strict_off_system_message_ends_with_json_only_suffix`、`::test_t48c_strict_off_url_method_auth_identical_to_strict_on`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-049

### 关联需求

FR-023 AC-4/5 · §IC `LlmBackend._extract_json` tolerant parse · Feature Design Test Inventory T49 · Wave 3 增量

### 测试目标

验证 LLM 响应 content 形如 `"<think>step 1...</think>\n{合法JSON}"` 时，tolerant extractor 剥离 `<think>...</think>` 包裹的推理段后成功解析剩余 JSON 为 `Verdict`，且 `backend == "llm"`（无降级）。

### 前置条件

- `.venv` 激活；respx 可用
- `LlmBackend` 在 `effective_strict=False` 下运行（tolerant parse 路径）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx mock POST 返回 chat envelope，其 `choices[0].message.content == "<think>step 1...</think>\n{\"verdict\":\"COMPLETED\",\"reason\":\"ok\",\"anomaly\":null,\"hil_source\":null}"` | mock 就绪 |
| 2 | 调用 `backend.invoke(req, prompt)` | 不抛 |
| 3 | 断言返回 `Verdict(verdict="COMPLETED", backend="llm")`（reason、anomaly、hil_source 与 JSON 一致） | True |

### 验证点

- `<think>` 标签 + 包裹内容被 tolerant extractor 完全剥离
- 剩余 JSON 解析成功；不触发 ClassifierProtocolError 误降级
- backend 字段保持 "llm"（FR-023 AC-4 strict-off 合法 JSON 走 LLM 路径）

### 后置检查

- respx 路由复位

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_wave3_llm_strict_off.py::test_t49a_tolerant_extract_strips_think_prefix_and_parses_json`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-050

### 关联需求

FR-023 AC-5 · §IC `LlmBackend._extract_json` 多段 JSON 首对象语义 · Feature Design Test Inventory T50 · Wave 3 增量

### 测试目标

验证 LLM 响应 content 含**多段** JSON 对象（混在自然语言间）时，tolerant extractor 取**首个**语法平衡 JSON 对象解析，忽略后续段；返回的 Verdict 反映首段。

### 前置条件

- `.venv` 激活；respx 可用
- `LlmBackend` 在 strict-off 路径

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx mock content = `"前言文本{\"verdict\":\"CONTINUE\",\"reason\":\"a\",\"anomaly\":null,\"hil_source\":null}后续 {\"other\":\"junk\"}"` | mock 就绪 |
| 2 | 调用 `backend.invoke(req, prompt)` | 不抛 |
| 3 | 断言 `verdict == "CONTINUE"`（取首段对象，第二段 `{other:junk}` 被忽略） | True |
| 4 | 断言 `backend == "llm"` | True |

### 验证点

- 语法平衡（balanced braces）扫描算法在首个完整 `{...}` 处停止
- 不会拼接 / 误读第二段 JSON 导致 schema 校验失败
- 与 T49 共同覆盖 FR-023 AC-5 的两类输入：噪声前缀（`<think>`）+ 多对象拼接

### 后置检查

- respx 路由复位

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_wave3_llm_strict_off.py::test_t50a_tolerant_extract_picks_first_balanced_json_object`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-051

### 关联需求

FR-023 AC-6/7 · §IC `LlmBackend._extract_json` 无 JSON · §Existing Code Reuse `FallbackDecorator` audit · Feature Design Test Inventory T51 · Wave 3 增量

### 测试目标

验证 LLM 响应 content 完全无可提取 JSON 对象（如 `"对不起我无法分类"`）时：(a) `LlmBackend.invoke` 抛 `ClassifierProtocolError(cause="json_parse_error")`；(b) `ClassifierService.classify` 经 FallbackDecorator 捕获后返回 `Verdict(backend="rule")`；(c) audit log 追加一行结构化事件 `{event:"classifier_fallback", cause:"json_parse_error"}`；(d) classify 永不抛（IAPI-010 约定保留）。

### 前置条件

- `.venv` 激活；respx 可用
- audit log fixture / capsys 用于断言事件

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | respx mock content = `"对不起我无法分类"`（纯自然语言无 JSON 对象） | mock 就绪 |
| 2 | 直接 `await backend.invoke(req, prompt)` | 抛 `ClassifierProtocolError`；`error.cause == "json_parse_error"` |
| 3 | 改走 ClassifierService 全栈：`await service.classify(req)` | 不抛；返回 `Verdict(backend="rule")` |
| 4 | 检查 audit log，断言含一行 `{"event":"classifier_fallback","cause":"json_parse_error",...}` | True |

### 验证点

- tolerant extractor 在无 JSON 时**确实抛**，而非静默返回（避免上层误以为 LLM 成功）
- FallbackDecorator 捕获 ProtocolError 并下沉到 RuleBackend
- audit `cause` 字段精确等于 `json_parse_error`（FR-023 AC-7 字面值）
- classify 对外永不抛（IAPI-010）

### 后置检查

- respx 路由复位；audit log 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f19_wave3_llm_strict_off.py::test_t51a_tolerant_extract_no_json_raises_protocol_error_with_json_parse_error_cause`、`::test_t51b_classifier_service_no_json_content_falls_back_to_rule_with_audit`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-019-052

### 关联需求

IFR-004 AC-mod · ASM-008 · FR-023 strict-off 真网验证 · Feature Design Test Inventory T52 · Wave 3 增量

### 测试目标

通过 `@pytest.mark.real_external_llm` smoke 在真实 MiniMax OpenAI-compat 端点 `api.minimax.chat/v1/chat/completions` 上验证 strict-off 路径 + tolerant parse 端到端可用：(a) `test_connection` 在 IFR-004 10s 预算内返回结构化 `TestConnectionResult`；(b) `classify` 实网调用永不抛、返合法 `Verdict`，验证 ASM-008 假设（MiniMax strict-off + tolerant extractor 真网可用）。

### 前置条件

- `.venv` 激活
- 平台 keyring 含 entry `service="harness-classifier"`、`username="minimax"`、有效 API key
- 网络可达 `api.minimax.chat`（HTTPS 出站）
- **当 keyring 无 entry 时**：pytest 自动 `skip()`（在 ST 自动化语义下视为非阻塞 PASS — 等价于"该 provider 等同 classifier disabled"，符合 design §11.4 Wave 3 Risk 行 fallback plan）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 从 `KeyringGateway()` 读 `harness-classifier/minimax` API key；缺失时 pytest.skip | 有 key → 继续；无 key → SKIPPED |
| 2 | 构造 `ClassifierConfig(provider="minimax", base_url="https://api.minimax.chat/v1/", model_name="MiniMax-M2.7-highspeed", strict_schema_override=None)` → effective_strict=False | 配置就绪 |
| 3 | `await service.test_connection(...)`；记录 wall-clock | 返回 `TestConnectionResult`（ok=True 或 ok=False + 已知 error_code）；耗时 ≤ 10s |
| 4 | `await service.classify(req)` 真发 POST 一次 | 不抛；返回 `Verdict`；`backend ∈ {"llm","rule"}`（成功 LLM 时 backend="llm"，偶发空返回时 backend="rule" 视为辅助断言） |
| 5 | 断言 verdict 字段 ∈ {COMPLETED, CONTINUE, RETRY, ABORT, HIL_REQUIRED}（Verdict 枚举范围） | True |

### 验证点

- ASM-008 假设：MiniMax 真实端点对 strict-off + JSON-only suffix prompt 路径稳定回 JSON
- IFR-004 10s 预算在真网下满足
- IAPI-010 永不抛承诺在真网下保留
- 若实网偶发空返回触发 backend=rule，符合 design §11.4 Wave 3 Risk fallback（不算 FAIL）

### 后置检查

- 无副作用（test_connection 仅 ping，classify 单次调用 < 配额）

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f19_real_minimax.py::test_f19_real_minimax_test_connection_round_trip`、`::test_f19_real_minimax_classify_never_raises`
- **Test Type**: Real

> **类别归属说明**：design Test Inventory 标 T52 为 INTG/http（外部 LLM 端点真网集成）；ST 用例 ID 规范允许的 CATEGORY 仅 FUNC/BNDRY/UI/SEC/PERF，无独立 INTG 类。本用例本质验证 IFR-004 strict-off 路径在真实 MiniMax 端点的 happy/error 行为契约，归入 `functional` 与 ST-PERF-019-001（T31 真网 timeout）/ ST-FUNC-019-020（T35 real_fs）/ ST-FUNC-019-021（T36 real_keyring）的既有归类约定一致。

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-019-001 | FR-019 AC-1 / T01 | verification_steps[0] | `tests/test_f19_model_resolver.py::test_t01_resolve_per_skill_rule_returns_opus_with_per_skill_provenance` | Real | PASS |
| ST-FUNC-019-002 | FR-020 AC-3 / FR-019 AC-2 / T02 | verification_steps[1] | `tests/test_f19_model_resolver.py::test_t02_per_ticket_wins_over_per_skill` | Real | PASS |
| ST-FUNC-019-003 | FR-020 AC-1 / T03 | verification_steps[0] | `tests/test_f19_model_resolver.py::test_t03_run_default_only_returns_haiku_with_run_default_provenance` | Real | PASS |
| ST-BNDRY-019-001 | FR-020 AC-2 / T04 | verification_steps[2] | `tests/test_f19_model_resolver.py::test_t04_all_layers_none_returns_cli_default_with_model_none` | Real | PASS |
| ST-BNDRY-019-002 | T05 / Clarification #5 | verification_steps[2] | `tests/test_f19_model_resolver.py::test_t05_empty_string_ticket_override_skips_to_per_skill_layer` | Real | PASS |
| ST-FUNC-019-004 | T06 / ModelRulesCorruptError | verification_steps[0] | `tests/test_f19_model_rules_store.py::test_t06_load_raises_model_rules_corrupt_error_on_invalid_json` | Real | PASS |
| ST-FUNC-019-005 | FR-019 / T07 | verification_steps[0] | `tests/test_f19_model_rules_store.py::test_t07_save_then_load_round_trip_preserves_single_rule` | Real | PASS |
| ST-SEC-019-001 | NFR-008 精神 / T08 | verification_steps[0] | `tests/test_f19_model_rules_store.py::test_t08_save_sets_posix_mode_0600` | Real | PASS |
| ST-FUNC-019-006 | FR-022 AC-1 / T09 | verification_steps[4] | `tests/test_f19_rule_backend.py::test_t09_rule_backend_exit_zero_no_banner_empty_stderr_returns_completed` | Real | PASS |
| ST-FUNC-019-007 | FR-022 AC-2 / T10 | verification_steps[5] | `tests/test_f19_rule_backend.py::test_t10_rule_backend_context_window_stderr_returns_retry_context_overflow` | Real | PASS |
| ST-FUNC-019-008 | T11 | verification_steps[5] | `tests/test_f19_rule_backend.py::test_t11_rule_backend_rate_limit_stderr_returns_retry_rate_limit` | Real | PASS |
| ST-FUNC-019-009 | T12 | verification_steps[5] | `tests/test_f19_rule_backend.py::test_t12_rule_backend_permission_denied_returns_abort_no_retry` | Real | PASS |
| ST-FUNC-019-010 | T13 | verification_steps[5] | `tests/test_f19_rule_backend.py::test_t13_rule_backend_unknown_failure_returns_abort_skill_error` | Real | PASS |
| ST-BNDRY-019-003 | T14 | verification_steps[2] | `tests/test_f19_rule_backend.py::test_t14_rule_backend_exit_code_none_is_not_completed` | Real | PASS |
| ST-BNDRY-019-004 | T15 | verification_steps[2] | `tests/test_f19_rule_backend.py::test_t15_rule_backend_tail_truncation_preserves_trailing_context_window_marker` | Real | PASS |
| ST-FUNC-019-011 | FR-023 / T16 / IFR-004 | verification_steps[6] | `tests/test_f19_llm_backend.py::test_t16_llm_backend_returns_hil_required_verdict_on_valid_schema` | Real | PASS |
| ST-FUNC-019-012 | FR-023 AC-1 / T17 | verification_steps[6] | `tests/test_f19_llm_backend.py::test_t17_llm_backend_raises_protocol_error_on_non_json_body` | Real | PASS |
| ST-SEC-019-002 | FR-023 AC-2 / T18 / SEC | verification_steps[6] | `tests/test_f19_llm_backend.py::test_t18_llm_backend_raises_protocol_error_on_out_of_enum_verdict` | Real | PASS |
| ST-FUNC-019-013 | T19 | verification_steps[6] | `tests/test_f19_llm_backend.py::test_t19_llm_backend_raises_http_error_on_timeout` | Real | PASS |
| ST-SEC-019-003 | FR-021 AC-3 / T20 / SSRF | verification_steps[7] | `tests/test_f19_provider_presets.py::test_t20_validate_base_url_rejects_link_local_metadata_service` | Real | PASS |
| ST-SEC-019-004 | T21 / Clarification #1 | verification_steps[7] | `tests/test_f19_provider_presets.py::test_t21_validate_base_url_rejects_hostname_substring_injection` | Real | PASS |
| ST-SEC-019-005 | T22 / Clarification #1 | verification_steps[7] | `tests/test_f19_provider_presets.py::test_t22_validate_base_url_rejects_rfc1918_private_ip_for_custom_provider` | Real | PASS |
| ST-FUNC-019-014 | FR-021 AC-1 / T23 | verification_steps[3] | `tests/test_f19_provider_presets.py::test_t23_resolve_glm_returns_expected_preset_fields` | Real | PASS |
| ST-BNDRY-019-005 | T24 | verification_steps[3] | `tests/test_f19_provider_presets.py::test_t24_resolve_unknown_provider_raises_provider_preset_error` | Real | PASS |
| ST-SEC-019-006 | FR-021 AC-1 / IAPI-014 / T25 | verification_steps[3] | `tests/test_f19_llm_backend.py::test_t25_llm_backend_sends_authorization_bearer_from_keyring` | Real | PASS |
| ST-SEC-019-008 | FR-021 AC-1 / NFR-008 / T26 | verification_steps[3] | `tests/test_f19_secret_leak.py::test_t26_put_classifier_settings_refuses_plaintext_api_key` | Real | PASS |
| ST-FUNC-019-015 | FR-022 / T27 | verification_steps[4] | `tests/test_f19_classifier_service.py::test_t27_classifier_service_enabled_false_uses_rule_only_no_http` | Real | PASS |
| ST-FUNC-019-016 | FR-023 / T28 / Clarification #2 | verification_steps[6] | `tests/test_f19_prompt_store.py::test_t28_prompt_store_put_then_put_builds_two_history_revs_with_sha256_hash` | Real | PASS |
| ST-BNDRY-019-006 | T29 | verification_steps[6] | `tests/test_f19_prompt_store.py::test_t29_prompt_store_put_empty_raises_prompt_validation_error` | Real | PASS |
| ST-BNDRY-019-007 | T30 | verification_steps[6] | `tests/test_f19_prompt_store.py::test_t30_prompt_store_put_32kb_plus_one_raises_prompt_validation_error` | Real | PASS |
| ST-PERF-019-001 | IFR-004 PERF / T31 / NFR-004 | verification_steps[6] | `tests/integration/test_f19_real_http.py::test_f19_t31_real_http_timeout_triggers_rule_fallback` | Real | PASS |
| ST-FUNC-019-017 | INT-025 / T32 | verification_steps[6] | `tests/test_f19_classifier_connection.py::test_t32_test_connection_401_returns_ok_false_with_error_code` | Real | PASS |
| ST-FUNC-019-018 | INT-025 / T33 | verification_steps[6] | `tests/test_f19_classifier_connection.py::test_t33_test_connection_connect_refused_returns_connection_refused_code` | Real | PASS |
| ST-FUNC-019-019 | INT-025 / T34 | verification_steps[6] | `tests/test_f19_classifier_connection.py::test_t34_test_connection_dns_failure_returns_dns_failure_code` | Real | PASS |
| ST-FUNC-019-020 | T35 / INTG fs | verification_steps[0] | `tests/integration/test_f19_real_fs.py::test_f19_t35_real_fs_model_rules_persist_across_store_instances` | Real | PASS |
| ST-FUNC-019-021 | IAPI-014 / T36 | verification_steps[3] | `tests/integration/test_f19_real_keyring.py::test_f19_t36_real_keyring_fail_backend_triggers_rule_fallback` | Real | PASS |
| ST-FUNC-019-022 | T37 / Clarification #4 | verification_steps[6] | `tests/test_f19_classifier_service.py::test_t37_classifier_service_never_raises_even_on_all_backends_failing` | Real | PASS |
| ST-FUNC-019-023 | FR-019 / T38 | verification_steps[0] | `tests/test_f19_api_routes.py::test_t38_get_model_rules_initially_returns_empty_list` | Real | PASS |
| ST-FUNC-019-024 | FR-019 / T39 | verification_steps[0] | `tests/test_f19_api_routes.py::test_t39_put_model_rules_persists_and_round_trips` | Real | PASS |
| ST-FUNC-019-025 | T40 / validation | verification_steps[0] | `tests/test_f19_api_routes.py::test_t40_put_model_rules_rejects_invalid_tool_with_validation_error` | Real | PASS |
| ST-FUNC-019-026 | FR-033 v1 / T41 | verification_steps[6] | `tests/test_f19_api_routes.py::test_t41_get_prompts_classifier_returns_default_with_empty_history` | Real | PASS |
| ST-FUNC-019-027 | FR-033 v1 / T42 / INT-019 | verification_steps[6] | `tests/test_f19_api_routes.py::test_t42_put_prompts_classifier_appends_history_rev` | Real | PASS |
| ST-FUNC-019-028 | FR-033 SEC / T43 | verification_steps[6] | `tests/test_f19_prompt_store.py::test_t43_prompt_store_refuses_path_outside_harness_home` | Real | PASS |
| ST-FUNC-019-029 | T44 / INT-005 | verification_steps[6] | `tests/test_f19_classifier_service.py::test_t44_classifier_service_emits_audit_fallback_on_http_5xx` | Real | PASS |
| ST-FUNC-019-030 | T45 / INT-016 / SSRF | verification_steps[7] | `tests/test_f19_classifier_connection.py::test_t45_test_connection_rejects_loopback_custom_base_url_with_ssrf_error` | Real | PASS |
| ST-FUNC-019-031 | T46 / IFR-004 | verification_steps[6] | `tests/test_f19_llm_backend.py::test_t46_llm_backend_request_body_declares_strict_json_schema` | Real | PASS |
| ST-FUNC-019-032 | API err coverage / T47 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t47_put_prompt_rejects_malformed_json_body_with_400` | Real | PASS |
| ST-FUNC-019-033 | API err coverage / T48 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t48_put_prompt_rejects_extra_fields_with_422` | Real | PASS |
| ST-FUNC-019-034 | API 32KB upper bound / T49 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t49_put_prompt_oversized_content_returns_422` | Real | PASS |
| ST-FUNC-019-035 | corrupt-file path / T50 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t50_get_prompt_corrupt_file_returns_500_with_detail` | Real | PASS |
| ST-FUNC-019-036 | IO failure / T51 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t51_put_prompt_store_io_failure_returns_500` | Real | PASS |
| ST-FUNC-019-037 | corrupt-file path / T52 | verification_steps[0] | `tests/test_f19_coverage_supplement.py::test_t52_get_model_rules_corrupt_file_returns_500` | Real | PASS |
| ST-FUNC-019-038 | err mapping / T53,T54 | verification_steps[0] | `tests/test_f19_coverage_supplement.py::test_t53_put_model_rules_malformed_body_returns_400`、`::test_t54_put_model_rules_non_list_payload_returns_422` | Real | PASS |
| ST-FUNC-019-039 | GET classifier 三态 / T55,T56,T57 | verification_steps[3] | `tests/test_f19_coverage_supplement.py::test_t55_get_classifier_config_returns_glm_default_when_file_absent`、`::test_t56_get_classifier_config_reads_persisted_value_from_disk`、`::test_t57_get_classifier_config_returns_default_on_corrupt_file` | Real | PASS |
| ST-FUNC-019-040 | PUT classifier 三态 / T58,T59,T60 | verification_steps[3] | `tests/test_f19_coverage_supplement.py::test_t58_put_classifier_config_malformed_body_returns_400`、`::test_t59_put_classifier_config_schema_mismatch_returns_422`、`::test_t60_put_classifier_config_persists_to_disk_and_round_trips` | Real | PASS |
| ST-FUNC-019-041 | test-connection 路径合集 / T61-T63,T67-T71 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t61_post_test_connection_malformed_body_returns_400`、`::test_t62_post_test_connection_missing_fields_returns_422`、`::test_t63_post_test_connection_ssrf_blocked_for_internal_ip`、`::test_t67_test_connection_timeout_returns_timeout_error_code`、`::test_t68_test_connection_generic_httperror_returns_connection_refused`、`::test_t69_test_connection_5xx_returns_connection_refused_with_latency`、`::test_t70_test_connection_200_returns_ok_true_with_latency`、`::test_t71_test_connection_continues_when_keyring_raises` | Real | PASS |
| ST-FUNC-019-042 | classify 子组件防御 / T64,T65,T66 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t64_classify_preset_resolve_error_audits_and_falls_back_to_rule`、`::test_t65_classify_catches_unexpected_decorator_exception_and_audits`、`::test_t66_classify_tolerates_prompt_store_corruption_and_uses_default` | Real | PASS |
| ST-FUNC-019-043 | FallbackDecorator 三态 / T72,T73,T74 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t72_fallback_decorator_audits_protocol_error_with_cause`、`::test_t73_fallback_decorator_catches_unexpected_exception_as_fallback`、`::test_t74_fallback_decorator_passes_through_successful_llm_verdict` | Real | PASS |
| ST-FUNC-019-044 | LlmBackend 异常映射 / T75-T82 | verification_steps[6] | `tests/test_f19_coverage_supplement.py::test_t75_llm_backend_raises_http_error_on_connect_error`、`::test_t76_llm_backend_raises_http_error_on_generic_http_error`、`::test_t77_llm_backend_raises_protocol_error_on_non_json_envelope`、`::test_t78_llm_backend_raises_protocol_error_on_missing_choices`、`::test_t79_llm_backend_raises_protocol_error_when_assistant_is_array`、`::test_t80_llm_backend_raises_protocol_error_on_anomaly_out_of_enum`、`::test_t81_llm_backend_raises_protocol_error_on_empty_reason`、`::test_t82_llm_backend_maps_keyring_failure_to_http_error_keyring_cause` | Real | PASS |
| ST-FUNC-019-045 | validate_base_url 守卫合集 / T83-T86 | verification_steps[7] | `tests/test_f19_coverage_supplement.py::test_t83_validate_base_url_rejects_scheme_missing`、`::test_t84_validate_base_url_rejects_http_scheme_for_whitelist_domain`、`::test_t85_validate_base_url_accepts_whitelist_subdomain_over_https`、`::test_t86_validate_base_url_rejects_http_scheme_for_custom_dns_host` | Real | PASS |
| ST-FUNC-019-046 | 底层组件边界合集 / T87-T98 | verification_steps[0] | `tests/test_f19_coverage_supplement.py::test_t87_list_returns_all_four_providers_including_custom`、`::test_t88_rules_store_load_missing_file_returns_empty_list`、`::test_t89_rules_store_load_whitespace_file_returns_empty_list`、`::test_t90_rules_store_load_dict_root_raises_corrupt_error`、`::test_t91_rules_store_load_schema_mismatch_raises_corrupt_error`、`::test_t92_rules_store_save_preserves_all_rules_in_order`、`::test_t93_rules_store_path_property_returns_constructor_path`、`::test_t94_prompt_store_get_whitespace_file_returns_default_prompt`、`::test_t95_prompt_store_get_corrupt_json_raises_prompt_store_corrupt_error`、`::test_t96_prompt_store_put_overwrites_corrupt_existing_file`、`::test_t97_prompt_store_put_parent_mkdir_failure_raises_prompt_store_error`、`::test_t98_prompt_store_path_property_matches_constructor` | Real | PASS |
| ST-FUNC-019-047 | FR-021 AC-4/5/6 / T47 / Wave 3 | verification_steps[8] | `tests/test_f19_wave3_strict_schema_capability.py::test_t47a_provider_preset_model_declares_supports_strict_schema_field`、`::test_t47b_glm_preset_supports_strict_schema_is_true`、`::test_t47c_openai_preset_supports_strict_schema_is_true`、`::test_t47d_custom_preset_supports_strict_schema_is_true`、`::test_t47e_minimax_preset_supports_strict_schema_is_false`、`::test_t47f_classifier_config_strict_schema_override_defaults_to_none`、`::test_t47g_classifier_config_strict_schema_override_accepts_bool_tri_state`、`::test_t47_effective_strict_truth_table[glm_none_preset_wins_true]`、`::test_t47_effective_strict_truth_table[glm_false_override_coerces_off]`、`::test_t47_effective_strict_truth_table[glm_true_override_stays_on]`、`::test_t47_effective_strict_truth_table[minimax_none_preset_wins_false]`、`::test_t47_effective_strict_truth_table[minimax_true_override_forces_on]` | Real | PASS |
| ST-FUNC-019-048 | FR-023 AC-3 / IFR-004 AC-mod / T48 / Wave 3 | verification_steps[9] | `tests/test_f19_wave3_llm_strict_off.py::test_t48a_strict_off_body_omits_response_format_key`、`::test_t48b_strict_off_system_message_ends_with_json_only_suffix`、`::test_t48c_strict_off_url_method_auth_identical_to_strict_on` | Real | PASS |
| ST-FUNC-019-049 | FR-023 AC-4/5 / T49 / Wave 3 | verification_steps[10] | `tests/test_f19_wave3_llm_strict_off.py::test_t49a_tolerant_extract_strips_think_prefix_and_parses_json` | Real | PASS |
| ST-FUNC-019-050 | FR-023 AC-5 / T50 / Wave 3 | verification_steps[10] | `tests/test_f19_wave3_llm_strict_off.py::test_t50a_tolerant_extract_picks_first_balanced_json_object` | Real | PASS |
| ST-FUNC-019-051 | FR-023 AC-6/7 / T51 / Wave 3 | verification_steps[10] | `tests/test_f19_wave3_llm_strict_off.py::test_t51a_tolerant_extract_no_json_raises_protocol_error_with_json_parse_error_cause`、`::test_t51b_classifier_service_no_json_content_falls_back_to_rule_with_audit` | Real | PASS |
| ST-FUNC-019-052 | IFR-004 AC-mod / ASM-008 / T52 / Wave 3 real_external_llm smoke | verification_steps[11] | `tests/integration/test_f19_real_minimax.py::test_f19_real_minimax_test_connection_round_trip`、`::test_f19_real_minimax_classify_never_raises` | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

---

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 67 |
| Passed | 67 |
| Failed | 0 |
| Pending | 0 |

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.
> 全部 67 用例自动化执行（无 `已自动化: No` 项）；映射到 119 个底层 pytest 函数（含 Wave 3 新增 21 个）；部分用例为合集（覆盖率补强类用例聚合多个函数到一个 ST 用例下，便于黑盒视角阅读）。
>
> **Wave 3 增量执行证据**（2026-04-25）：
> - `pytest tests/test_f19_wave3_*.py tests/integration/test_f19_real_minimax.py -v` → 21 passed in 5.15s
> - `pytest tests/test_f19_*.py tests/integration/test_f19_*.py` → 119 passed in 18.09s（含 Wave 2 基线 98 + Wave 3 增量 21；零回归）
> - real_external_llm smoke（T52 / ST-FUNC-019-052）：本机 keyring 含有效 MiniMax key，2 个真网用例均 PASSED（非 SKIPPED），ASM-008 假设在测试时点验证有效
