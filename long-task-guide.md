# Harness · long-task-guide

> Worker 会话的**导航**文件。本文件**只讲工作流顺序与纪律**；**所有命令**（构建 / 测试 / 覆盖率 / 静态分析 / 服务启停）一律引用 `env-guide.md` §1 与 §3，避免双源漂移。
>
> 变更本文件前请先阅读 `feature-list.json.quality_gates`（line ≥ 90% / branch ≥ 80%）与 `docs/plans/2026-04-21-harness-*.md` 四件套。

---

## 0. Orient —— 启动第一动作

1. 读 `feature-list.json`：
   - 根字段 `current`：若 `current == null`，由 `long-task-work-design` Step 1 原子 pick 下一可做 feature；若非 null，直接继续该 feature 当前 `phase`
   - `features[]`：找到 `current.feature_id` 的 entry，定位其 `srs_trace[]`、`dependencies[]`、`wave`、`ui`
2. 读 `task-progress.md` 看上次会话收尾位置与未决事项
3. 判定当前 phase：`design` → `tdd` → `st`；由 `phase` 字段驱动，不要越级
4. 扫 `docs/plans/2026-04-21-harness-{srs,design,ucd,ats}.md` 与当前 feature 对应章节；必要时反查到 FR-xxx 原文

## 1. Bootstrap —— 恢复环境

**不要手敲命令**。按序执行：

1. 首次或装新依赖：运行 `init.sh`（Unix/macOS）或 `init.ps1`（Windows），脚本幂等，自动建 venv、装 pip/npm 依赖。
2. 激活 Python venv / 前端 Node：**See `env-guide.md` §2 Environment Activation**。
3. 若需后端 / 前端 dev server：**See `env-guide.md` §1 Service Lifecycle**（`svc-api-start.sh` / `svc-ui-dev-start.sh`；重启遵循 §1 的 4 步 Restart Protocol）。
4. 纯 CLI / 单元测试子任务：**"No server processes — environment activation only"**。

## 2. Config Gate —— 每张 feature 开工前必经

Worker 进入 TDD 前，**必须**跑一次配置检查；失败即立刻停，不进入 Red：

```bash
python scripts/check_configs.py feature-list.json --feature <current.feature_id>
```

- 退出码 0 方可继续；非 0 时输出里的 `hint` 指示用户如何补齐
- 本项目的 config 由三处源头组合：
  - **`.env` 文件**（repo 根；`.env.example` 是模板，`.env` 不入库，见 `.gitignore`）— 提供 `HARNESS_HOME` / `HARNESS_WORKDIR` 等非秘密 env 变量
  - **平台 keyring**（NFR-008 / IFR-006）— 承载一切 API key / token；`.env` 不允许写明文秘密
  - **`~/.harness/*.json`**（config.json / model_rules.json / ui-state.json）— 运行期持久化，不入库
- 新增 / 改动 `required_configs[]`：同步更新 `.env.example`；平台 keyring 键也要在 `.env.example` 占位注释里列出（不写值）

## 3. TDD Red —— 失败测试先行（Rule 1–7）

目标：先在 `tests/` 与 `apps/ui/src/__tests__/` 里写出**会失败**的测试，绝不先写实现。

1. 入口：由 router 调用 `long-task-tdd-red` 子 skill；它读当前 feature 的 `docs/features/<id>/design.md §7 Test Inventory` 清单
2. 按 Test Category 分配：FUNC / BNDRY / SEC / PERF / UI —— 见 `docs/plans/2026-04-21-harness-ats.md §3`
3. **真实测试（Real Tests）约定** —— 见本文 §8
4. **测试先失败**：先跑全量单测确认新增测试 RED；绿则说明测试写错或已有实现抢跑，要中止 Red 阶段调查
5. 运行命令：**See `env-guide.md` §3 Unit Test Commands**（后端 pytest；前端 vitest）

## 4. TDD Green —— 最小实现让测试转绿

- 严格锚到 `docs/features/<id>/design.md` 的 §4（接口契约）/ §6（算法伪码）/ §8（错误路径）。不允许"设计外即兴"。
- 实现顺序：按依赖**由底向上**，每绿一个测试就跑一次对应测试文件（by name），避免整轮重跑 —— **See `env-guide.md` §3 Re-check Protocol**。
- 后端新增模块 `harness/...` 必须能被 `python -c "import harness"` 导入（构建命令已含该 smoke，**See `env-guide.md` §3 Build Commands**）。
- UI 实现走 `apps/ui/src/`，色板 / 组件规约严格遵 `docs/plans/2026-04-21-harness-ucd.md` §2-§3。

## 5. Coverage Gate —— 不过不推进

- **门槛**（硬性）：line ≥ 90% / branch ≥ 80%（`feature-list.json.quality_gates`）
- 运行：**See `env-guide.md` §3 Coverage Commands**（后端 pytest --cov；前端 vitest --coverage）
- 未过：优先补测用例，**不得靠 `# pragma: no cover` 绕开**；无法覆盖的代码路径→设计缺陷→回到 `long-task-work-design` 修订
- 由 `long-task-quality` skill 自动执行：未过会阻断 `st` 阶段进入

## 6. TDD Refactor —— 保持绿再清理

- 改命名、抽公共函数、合并重复 fixture；每一步 refactor 后跑测试包**对应子集**（by name），不整轮重跑
- 静态分析：**See `env-guide.md` §3 Static Analysis Commands**（ruff / black --check / mypy / eslint）
- 与 `docs/features/<id>/design.md` §4-§6-§8 对齐复查：若 refactor 偏离契约，要在 design.md 写 Decision Log 并升级设计文档

## 7. Verification Enforcement —— 永不"臆断通过"

- 在进入 `st` 阶段前，必须有**本会话产生**的新鲜证据：最新一次 pytest 与 vitest 的 log 或 junit，以及 coverage 命令的 exit=0
- 不得仅凭"上次跑过"就推进；`long-task-quality` 会拒绝陈旧 evidence
- feature 从 `failing` → `passing` 的 flip 只能在 `long-task-work-st` Persist 步骤原子完成，不由 Worker 手动编辑 JSON

## 8. Real Test Convention —— 真实 I/O vs Mock

Harness 遵循"**80% mock / 15% integration / 5% e2e**"的分布（ATS §3.1）。

- **Marker 约定**（后端 pytest）：
  - `@pytest.mark.real_cli` — 跑真 Claude / OpenCode CLI（需 `claude auth login` 已完成）
  - `@pytest.mark.real_fs` — 直接写临时目录（git init + subprocess）
  - `@pytest.mark.real_http` — 调真实 LLM provider 端点（慎用，默认 skip）
  - 无 marker = 默认单元测试（mock 完备，禁网络）
- **目录约定**：
  - `tests/unit/` — 全 mock；`pytest tests/unit -q` 一键跑
  - `tests/integration/` — 带 real_cli / real_fs marker
  - `tests/e2e/` — 极少数端到端，含 Playwright 套件
  - 前端：`apps/ui/src/__tests__/` 单元 vitest；`tests/e2e/ui/` 走 Playwright
- **命名**：`test_<module>_<behavior>.py`；UI 侧 `<Component>.test.tsx`
- **仅跑真实测试**：**See `env-guide.md` §3 Unit Test Commands**（后端追加 `-m real_cli or real_fs`；前端按文件路径过滤）
- 本技术栈下真实测试示例：
  - `tests/integration/test_pty_round_trip.py::test_hil_20x` — 真起 claude CLI pty，20 次 round-trip（FR-013）
  - `tests/integration/test_git_adapter.py::test_log_show` — `tmp_path` 里 `git init` + commit + 断言 `log --oneline`
  - `tests/unit/test_classifier_rules.py::test_context_overflow_stderr` — 纯规则匹配，无网络

## 9. UI Functional Testing —— Chrome DevTools MCP

UI 特性（`ui: true`；本项目共 5 条：F12/F13/F14/F15/F16）在 ST 阶段必须用 Chrome DevTools MCP 做**正面视觉存在**断言：

- 工具链：`mcp__chrome-devtools__new_page` → `navigate_page` → `take_snapshot` → 针对 `ui_entry` 路径做可见性断言；必要时 `take_screenshot` 附在 evidence 里
- 正面断言至少一条：页面加载 ≤ 3s，DOM 中能找到该页面的标志性组件（phase stepper / HIL card / skill tree 等，见 UCD §4.X）
- 异常路径断言：配合后端 mock 制造 context_overflow / rate_limit / HIL empty state 等，观察 toast / banner / empty-state（3.11）正确渲染
- 静态分析包含 a11y 基线：色对比 ≥ 4.5:1（UCD §5.1）；键盘可聚焦

## 10. ST Test Cases —— IEEE 29119 映射

- 由 `long-task-feature-st` 生成 `docs/test-cases/feature-<id>/*.md`，每个 feature 一目录
- 每条 case 挂到一个 `srs_trace` FR-xxx 与一个 ATS 类别（FUNC/BNDRY/SEC/PERF/UI）
- 命名：`TC-<FR-id>-<seq>.md`，metadata 含 preconditions / steps / expected / postcondition / actual / verdict

## 11. Inline Compliance Check —— 兑现设计

`long-task-work-st` 过 design-compliance 关卡：

- 对照 `docs/features/<id>/design.md` §4 接口契约逐条验收：函数签名 / 返回类型 / 错误码集合
- 检查 §6 伪码的关键分支在实现里都有对应代码路径（diff grep）
- 不满足一条 → 退回 TDD Refactor 或 `long-task-work-design` 修订

## 12. Persist —— 原子落盘

- 仅 `long-task-work-st` 可翻 `features[i].status` 为 `passing` 并清 `current` 锁；**Worker 不得手工 `git commit` 改 feature-list.json 的 status 字段**
- 每完成一 feature：写入 `task-progress.md` 一行（skill / 时间 / feature id / 下一步 hint）
- git commit：`feat(F<id>): <title>`；commit 目标包含实现、测试、design.md、test-cases/。**禁用 `--no-verify`**
- 提交后执行 `python scripts/validate_features.py feature-list.json` 确保 JSON 合规

## 13. Critical Rules —— 铁律

| # | 规则 | 违反后果 |
|---|---|---|
| 1 | `current` 锁只能 by `long-task-work-design` 原子写、by `long-task-work-st` 原子清；其他 skill 绝不触碰 | `feature-list.json` 失控，整 run 卡死 |
| 2 | feature `failing → passing` 翻转只能在 Persist 原子完成 | 假绿灯；Coverage Gate 被绕过 |
| 3 | 任何命令参数（构建 / 测试 / 覆盖率）**必须**引用 `env-guide.md` §3；**不得**在本文件或其他 skill 里硬编码重复 | 双源漂移；用户改命令后流水线不跟随 |
| 4 | `.env` 与 `~/.harness/` 里严禁出现 API key 明文；API key 仅入 keyring（NFR-008） | 凭证泄露 |
| 5 | 新代码写入路径必须 ∈ `.harness/` ∪ `.harness-workdir/`；不得写 `~/.claude/`（NFR-009） | 环境污染；FR-043 验收失败 |
| 6 | 未跑 `check_configs.py`、未跑最新 coverage、未跑 `validate_features.py` **不得**进入 ST | 推进前提被绕过，后续 ST Go verdict 不可信 |
| 7 | UI 特性 E2E 前必须启动 `api` + `ui-dev` 两条服务（§1 Restart Protocol）；只靠"我以为在跑"等于作弊 | Playwright / devtools 连不上目标，证据不成立 |
| 8 | 依赖未 `passing` 的 feature 不得开工；违反时 router 会 refuse，强跑会破坏依赖链（见 Design §11.3） | 循环阻塞；HIL PoC 未过就跑 F04 会浪费会话 |
| 9 | 静态分析失败不得推进（ruff / black / mypy / eslint）；先修再跑测试 | Refactor 阶段留垃圾债 |
| 10 | 提交 commit 前检查 `.gitignore` 生效：`dist/` `.venv/` `.harness/` 不得进入 diff | 大文件污染仓库 |

## 14. 常见陷阱（Harness 专属）

- `CLAUDE_CONFIG_DIR` 对某些 Claude Code 版本不生效（OQ-D2）— 看 Design §6.1 的兜底；遇测试失败先核 env injection
- pty 在 macOS / Linux 使用 `ptyprocess`，Windows 走 `pywinpty` —— 跨平台测试分别加 marker `@pytest.mark.skipif(sys.platform != ...)`
- Vite dev server 默认 5173；若与本机其他前端冲突，在 `apps/ui/vite.config.ts` 改后**必须同步更新 `env-guide.md` §1** 并走 §6 审批
- FastAPI 绑定地址：NFR-007 硬编码 127.0.0.1；任何 `0.0.0.0` 补丁 CI 直接挂
- filelock 互斥单 workdir 单 run（NFR-016）—— 集成测试里要手工清 `.harness/lock` 避免前个用例残留

---

_本文件引用但不复制 `env-guide.md` 的命令部分；命令的唯一事实源是 `env-guide.md` §1 与 §3。任何命令修改走该文件的 §6 审批流程。_


*by long task skill*
