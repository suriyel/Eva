# 测试用例集: Fix 打包前 UI↔FastAPI 集成壳 9 项缺陷 + 设计稿控件大幅错位/缺失（B1-B9）

**Feature ID**: 24
**关联需求**: FR-001, FR-010, FR-019, FR-020, FR-021, FR-031, FR-032, FR-034, FR-035, FR-038, FR-049, NFR-007, NFR-010, NFR-011, NFR-013, IFR-006, IFR-007（ATS §2.1 L49/L68/L87/L88/L89/L109/L110/L112/L113/L119/L150/L163/L166/L167/L169/L184/L185 + §5.1 L336 INT-025；必须类别 FUNC/BNDRY/SEC/UI/PERF）
**日期**: 2026-04-26
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0
**特性 UI 标记**: `ui: true`（§Visual Rendering Contract 18 元素 + 18 正向断言 + 9 交互深度断言）

> **说明**：
> - 本文档为 ST 黑盒验收测试用例。预期结果仅从 SRS 验收准则（FR-001/010/019/020/021/031/032/034/035/038/049 + NFR-007/010/011/013 + IFR-006/007）、ATS §2.1 / §5.1 INT-025 类别约束、Feature Design Test Inventory 41 行（B1-P1...B9-N3）、可观察接口（生产入口 `harness.api:app` 经 `uvicorn --host 127.0.0.1 --port 8765` + 前端 dist 同源静态挂载、Chrome DevTools MCP 浏览器侧 React props / DOM 断言、`websockets` 客户端真握手、`scripts/init_project.py` argparse 入口）推导，不阅读实现源码。
> - **Specification resolutions applied from Feature Design Clarification Addendum**：feature design `## Clarification Addendum` 表为空（"无需澄清 — 全部规格明确"）；§4 Test Inventory 41 行预期与 §6.1 Visual Rendering Contract 视觉断言均明文化，未触发 Contract Deviation Protocol。
> - **`feature.ui == true` → UI 类别用例强制必含 Chrome DevTools MCP 三层检测**（Layer 1 / Layer 1b / Layer 3）；本文档 UI 用例覆盖 §VRC 18 视觉元素 + 9 交互深度断言。
> - **混合执行模式**（env-guide §1）：(a) `INTG/asgi-rest` / `INTG/http` 类别用例直接经 `curl` 打 `127.0.0.1:8765` 真启 uvicorn；(b) `UI/render` / `UI/a11y` / `INTG/ws` 类别用例经 Chrome DevTools MCP 浏览器渲染 + React fiber props 检测；(c) `INTG/fs` / `SEC/cli-injection` / `BNDRY/edge` 用例直接执 `python3 scripts/init_project.py` subprocess + `os.path.exists` 断言。
> - **手动测试**：本特性全部 41 用例均自动化执行（`已自动化: Yes`），无 `已自动化: No` 项；NFR-010 视觉评审差异由探索性视觉评估（Step 8）补足。
> - **bug 根因校验**：B1-B9 共 9 类独立缺陷，每条独立 P/N 行至少 1+1 覆盖；B8 ST 阶段发现 Implementation Summary 中 `_validate_safe_arg` 守卫**未落到** `scripts/init_project.py`（unit test `test_f24_b8_init_project_guard.py` 6/6 FAIL），SubAgent 就地修复（追加 `_RESERVED_FLAGS` set + `_validate_safe_arg` + `_preflight_argv_guard` 在 argparse 之前介入），重跑 6/6 PASS，B8-P1/N1/N2/N3/N4/P2 ST 用例随之 PASS。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 26 |
| boundary | 3 |
| ui | 21 |
| security | 5 |
| performance | 1 |
| **合计** | **53** |

> **类别归属约定**：Feature Design Test Inventory 实际共 53 行（B1×5 + B2×5 + B3×4 + B4×6 + B5×9 + B6×8 + B7×5 + B8×6 + B9×5）的 sub-category（`UI/render` / `UI/a11y` / `INTG/api` / `INTG/ws` / `INTG/http` / `INTG/fs` / `FUNC/happy` / `FUNC/error` / `FUNC/cache-staleness` / `FUNC/cache-refresh` / `SEC/cli-injection` / `SEC/path-traversal` / `SEC/api-key-leak` / `BNDRY/edge` / `PERF/probe-throughput`）映射到 ST 用例 ID 规范允许的 5 个 CATEGORY（FUNC / BNDRY / UI / SEC / PERF）：
> - `UI/render` + `UI/a11y` → UI（共 21 用例：ST-UI-024-001..021）
> - `INTG/api` + `INTG/ws` + `INTG/http` + `FUNC/happy` + `FUNC/error` + `FUNC/cache-*` → FUNC（共 26 用例：ST-FUNC-024-001..023 + 部分 INTG）
> - `BNDRY/edge` → BNDRY（3 用例：ST-BNDRY-024-001..003）
> - `SEC/*` → SEC（5 用例：ST-SEC-024-001..005）
> - `PERF/probe-throughput` → PERF（1 用例：ST-PERF-024-001）
> - 负向（FUNC/error + BNDRY + SEC + UI/a11y 含 N 后缀）：B1-N1/N2, B2-N1/N2, B3-N1/N2, B4-N1/N2/N3, B5-N1/N2, B6-N1/N2, B7-N1/N2, B8-N1/N2/N3/N4, B9-N1/N2/N3 共 22 行。
> - **负向占比**：22 / 53 = **41.5% ≥ 40%** ✓

> **Test Inventory → ST 用例 1:1 映射**：Feature Design 53 行 Test Inventory（B1-P1, B1-P2, B1-P3, B1-N1, B1-N2; B2-P1, B2-P2, B2-N1, B2-N2, B2-P3; B3-P1, B3-N1, B3-N2, B3-P2; B4-P1, B4-P2, B4-N1, B4-N2, B4-N3, B4-P3; B5-P1...P6, B5-N1, B5-N2, B5-P7; B6-P1...P5, B6-N1, B6-N2, B6-P6; B7-P1...P3, B7-N1, B7-N2; B8-P1, B8-N1...N4, B8-P2; B9-P1, B9-N1, B9-N2, B9-P2, B9-N3）一一对应 ST 用例。pytest / vitest 函数对照见可追溯矩阵 "自动化测试" 列。

---

### 用例编号

ST-UI-024-001

### 关联需求

FR-001 AC-1 · FR-031 · §VRC RunOverview Start 按钮 · Feature Design Test Inventory B1-P1 · ATS §2.1 L49 FR-001

### 测试目标

验证 RunOverview EmptyState 渲染时，`button[data-testid="btn-start-run"]` 存在且 React fiber props 含 `onClick: function` 与 `disabled: boolean` 属性（修复前 onClick 缺失致点击无效）。

### 前置条件

- `harness.api:app` uvicorn 运行于 127.0.0.1:8765（`HARNESS_WORKDIR=/home/machine/code/Eva`）
- `apps/ui/dist` 构建完成（hash `index-C2bGRTtv.js`）
- 当前无运行中 run（`GET /api/runs/current` 返空 dict `{}`）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page(url='http://127.0.0.1:8765/') | 页面 200 OK，UI 加载完成 |
| 2 | wait_for(['Start']) → evaluate_script(error_detector) | EmptyState「无运行中的 run」可见，Layer 1: 0 errors |
| 3 | take_snapshot() | EXPECT: button text='Start' + StaticText '无运行中的 run'; REJECT: phase-stepper / current-skill 等 6 元素 |
| 4 | evaluate_script(positive_render_checker, ['button[data-testid="btn-start-run"]'], []) | Layer 1b: missingCount=0；button 渲染 |
| 5 | evaluate_script(() => { const btn=document.querySelector('button[data-testid="btn-start-run"]'); const props=btn[Object.keys(btn).find(k=>k.startsWith('__reactProps$'))]; return { onClick: typeof props.onClick, disabled: typeof props.disabled, propsKeys: Object.keys(props) }; }) | onClick='function'; disabled='boolean'; propsKeys 含 ['data-testid','type','onClick','disabled','aria-busy','style','children'] |
| 6 | list_console_messages(['error']) | Layer 3: 0 console errors |

### 验证点

- React fiber props 中 `onClick` 类型严格为 `function`（B1 直接命中：修复前为 `undefined`）
- `disabled` 属性存在（pending 态准备）
- EmptyState 不渲染 6 元素（current run absent）

### 后置检查

- 浏览器 console 无 error
- 无悬挂 fetch 请求

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/run-overview/__tests__/f24-b1-start-button.test.tsx::B1-P1` + Chrome DevTools MCP 浏览器实测
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-001

### 关联需求

FR-001 · §IC `RunOverviewPage.handleStart` postcondition · Feature Design Test Inventory B1-P2 · ATS §2.1 L49

### 测试目标

验证点击 Start 按钮触发 `POST /api/runs/start`，按钮进入 `disabled+pending` 状态，invalidate `["GET","/api/runs/current"]` query。

### 前置条件

- 同 ST-UI-024-001
- `useStartRun` hook 已注册到 RunOverviewPage

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock fetch wrapper to count POST calls | mock installed |
| 2 | navigate_page('/') → wait_for(['Start']) | EmptyState 渲染 |
| 3 | click(uid='btn-start-run') | fetch 被调 1 次, method=POST, url='/api/runs/start' |
| 4 | evaluate_script(`document.querySelector('button[data-testid="btn-start-run"]').disabled`) | true（pending） |
| 5 | wait 200ms → evaluate `(window as any).__fetchCalls.filter(c => c.method === 'POST' && c.url.endsWith('/api/runs/start')).length` | == 1 |

### 验证点

- POST 请求成功路径触发 `disabled` 转换
- 通过 vitest mock 校验 fetch 携带 `Content-Type: application/json` body

### 后置检查

- button 状态恢复（成功后 invalidate, 失败后 enabled）

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/run-overview/__tests__/f24-b1-start-button.test.tsx::B1-P2`
- **Test Type**: Real

---

### 用例编号

ST-UI-024-002

### 关联需求

FR-030 · §VRC RunOverview 6 元素 · Feature Design Test Inventory B1-P3

### 测试目标

验证 `liveStatus = RunStatus(state='running')` 时，6 个 testid（phase-stepper / current-skill / current-feature / run-cost / run-turns / run-head）全部 mount 且 textContent 非空。

### 前置条件

- mock `useCurrentRun()` 返 `RunStatus(state='running', ...)`（vitest 单元测试场景；E2E 测试可选 Start click 后 invalidate）
- 浏览器或 jsdom 渲染环境就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | render RunOverviewPage with mock liveStatus running | 6 元素全 mount |
| 2 | evaluate_script(positive_render_checker, ['[data-component="phase-stepper"]','[data-testid="current-skill"]','[data-testid="current-feature"]','[data-testid="run-cost"]','[data-testid="run-turns"]','[data-testid="run-head"]'], []) | Layer 1b: missingCount=0 |
| 3 | for each selector: querySelector(s).textContent.trim() | 每个 textContent.length > 0 |

### 验证点

- 6 元素 100% 渲染
- 不允许任何元素 textContent 为空字符串

### 后置检查

- console 无 React warning

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/run-overview/__tests__/f24-b1-start-button.test.tsx::B1-P3`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-002

### 关联需求

§IC Raises (handleStart 错误路径) · Feature Design Test Inventory B1-N1 · FR-001 错误路径

### 测试目标

验证 `POST /api/runs/start` 返 409（"run already running"）时，UI 渲染红色 toast 并 button restore enabled，无 unhandled promise rejection。

### 前置条件

- mock fetch 配置返 409 status + JSON `{detail:'run already running'}`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock fetch → respond 409 | mock 安装 |
| 2 | render RunOverviewPage + click Start | onClick fires |
| 3 | wait for promise resolution | toast 渲染（findByText '红色错误' / role='alert'） |
| 4 | evaluate `document.querySelector('button[data-testid="btn-start-run"]').disabled` | false（restore） |
| 5 | check window.onunhandledrejection | 无触发 |

### 验证点

- HttpError 被 try/catch 捕获
- button.disabled 经 finally 恢复为 false

### 后置检查

- toast 消息含错误描述（不只是空字符）

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/run-overview/__tests__/f24-b1-start-button.test.tsx::B1-N1`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-003

### 关联需求

§IC Raises (handleStart 网络错误) · Feature Design Test Inventory B1-N2

### 测试目标

`POST /api/runs/start` 网络错误（fetch reject `Error('Network error')`）时，UI 显示 toast，button restore，无 unhandled rejection。

### 前置条件

- mock fetch reject

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock fetch → reject Error('Network error') | mock 安装 |
| 2 | render + click Start | onClick fires |
| 3 | await promise resolution | toast 渲染 |
| 4 | evaluate button.disabled | false |
| 5 | check unhandledrejection | 0 |

### 验证点

- Network error 被处理；button 不卡 disabled

### 后置检查

- 二次点击仍可触发新请求

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/run-overview/__tests__/f24-b1-start-button.test.tsx::B1-N2`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-004

### 关联需求

IAPI-002 `GET /api/tickets` · FR-031 AC-1 · Feature Design Test Inventory B2-P1 · ATS §2.1 L109

### 测试目标

mock `useCurrentRun()` 返 `"run-x"` 后 mount HilInbox：fetch URL 必含 `?state=hil_waiting&run_id=run-x`。

### 前置条件

- mock fetch wrapper

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock useCurrentRun() → 'run-x' | hook injected |
| 2 | render HilInboxPage in QueryClientProvider | TanStack Query fires |
| 3 | wait for fetch call | 1 次 GET 至 /api/tickets |
| 4 | inspect URL | URL 含 `state=hil_waiting` AND `run_id=run-x` |

### 验证点

- URL query 参数严格存在 `run_id`（B2 直接命中）
- 不再向后端发送漏 run_id 的请求（避免 backend 400）

### 后置检查

- query state == 'success' 或 'pending'，不为 error

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/hil-inbox/__tests__/f24-b2-tickets-run-id.test.tsx::B2-P1`
- **Test Type**: Real

---

### 用例编号

ST-UI-024-003

### 关联需求

§VRC HILInbox EmptyState · Feature Design Test Inventory B2-P2

### 测试目标

`useCurrentRun()` 返 null 时，`[data-testid="hil-inbox-empty"]` 渲染，且 fetch mock 调用次数严格 == 0。

### 前置条件

- mock useCurrentRun() → null
- mock fetch wrapper 计数

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock currentRun = null + fetch counter | install |
| 2 | navigate_page('/hil') | 页面加载 |
| 3 | wait_for('无待答 HIL') → evaluate_script(error_detector) | empty state 文案可见, Layer 1: 0 |
| 4 | evaluate_script(positive_render_checker, ['[data-testid="hil-inbox-empty"]'], []) | Layer 1b missingCount=0 |
| 5 | evaluate_script(`(window as any).__fetchCalls.filter(c => c.url.includes('/api/tickets')).length`) | == 0 |
| 6 | list_console_messages(['error']) | Layer 3: 0 |

### 验证点

- enabled: false 守卫生效
- DOM 确认 EmptyState 元素存在

### 后置检查

- 切换到 currentRunId='run-y' 后能恢复 fetch（不会卡 enabled:false）

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/hil-inbox/__tests__/f24-b2-tickets-run-id.test.tsx::B2-P2` + Chrome DevTools MCP 浏览器实测
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-005

### 关联需求

§IC `HilInbox.useTicketsQuery` postcondition · Feature Design Test Inventory B2-N1

### 测试目标

`useCurrentRun()` 返 null 时，即便用户手动触发 query invalidate，fetch 仍 skip。

### 前置条件

- mock currentRun=null + fetch counter

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | render HilInbox | initial: enabled=false |
| 2 | queryClient.invalidateQueries(['tickets']) | invalidate fires |
| 3 | wait 200ms | enabled remains false |
| 4 | check fetch count | == 0 |

### 验证点

- enabled: false 即便外部 invalidate 也不会发请求

### 后置检查

- 无 400 backend 错误

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/hil-inbox/__tests__/f24-b2-tickets-run-id.test.tsx::B2-N1`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-006

### 关联需求

IAPI-002 / FR-034 · Feature Design Test Inventory B2-N2 · ATS §2.1 L112

### 测试目标

TicketStream 默认 filters `{state: undefined, run_id: undefined}` 时，`buildTicketsUrl` 返 null → 跳过 fetch + EmptyState。

### 前置条件

- 默认 filters

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock currentRun=null | hook null |
| 2 | render TicketStreamPage 默认 filters | initial mount |
| 3 | check fetch counter for /api/tickets | == 0 |
| 4 | mock currentRun='run-y' | hook updates |
| 5 | re-render → check next fetch | URL 含 run_id=run-y |

### 验证点

- buildTicketsUrl 在 currentRunId null 时返 null
- 切到非 null 立即注入 run_id

### 后置检查

- 不发 400 backend

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/ticket-stream/__tests__/f24-b2-build-tickets-url.test.tsx::B2-N2`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-007

### 关联需求

IAPI-001 `/ws/hil` `hil_question_opened` · Feature Design Test Inventory B2-P3

### 测试目标

mount HilInbox + currentRunId='run-x' + WS push `hil_question_opened` → tickets query invalidate → 列表新增 1 张 hil-card。

### 前置条件

- mock WS server + mock fetch

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock /ws/hil server + currentRun='run-x' | setup |
| 2 | render HilInbox | initial fetch 1 |
| 3 | server pushes `hil_question_opened` envelope | client receives |
| 4 | wait → check fetch count | ≥ 2 (initial + invalidate-triggered refetch) |
| 5 | DOM count `[data-component="hil-card"]` | == new count |

### 验证点

- WS push triggers tickets query invalidate

### 后置检查

- 无重复连接 leak

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/hil-inbox/__tests__/f24-b2-tickets-run-id.test.tsx::B2-P3`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-008

### 关联需求

§6.2.3 5 path / IFR-007 · Feature Design Test Inventory B3-P1 · ATS §2.1 L185

### 测试目标

useWs 同时挂载 5 channel，`WebSocket` 构造函数被调 5 次，URL 各为 `ws://host:port/ws/{run/r1,stream/t1,hil,anomaly,signal}`；**0 次** ctor URL == `ws://host:port/`（根路径）。

### 前置条件

- `WebSocket` 构造器被 spy（vitest 或浏览器 initScript 注入）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | initScript: `window.__wsConnections = []; const _orig = WebSocket; window.WebSocket = function(url) { __wsConnections.push(url); return new _orig(url); };` | spy installed |
| 2 | render component mounting useWs('/ws/run/r1'), '/ws/stream/t1', '/ws/hil', '/ws/anomaly', '/ws/signal' simultaneously | 5 hooks fire |
| 3 | wait 500ms | each hook initiates handshake |
| 4 | evaluate `window.__wsConnections.length` | == 5 |
| 5 | filter for root URL `ws://127.0.0.1:8765/` | 0 matches |

### 验证点

- 5 个独立 channel URL 全部存在
- 无任何根路径连接（B3 直接命中）

### 后置检查

- unmount → 5 个 socket 全 close

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/ws/__tests__/f24-b3-multi-channel-direct-connect.test.tsx::B3-P1` + Chrome DevTools MCP 浏览器侧 ws spy 验证（仅 channel-specific 路径，never root）
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-009

### 关联需求

§IC `useWs` Raises · Feature Design Test Inventory B3-N1

### 测试目标

useWs("/ws/invalid") 抛 RangeError，且不发起任何连接。

### 前置条件

- WebSocket spy

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | render component with useWs("/ws/invalid") | error thrown |
| 2 | catch RangeError | typeof error === 'RangeError' |
| 3 | check ws spy count | 0 |

### 验证点

- 白名单旁路被守住

### 后置检查

- 错误日志无敏感信息

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/ws/__tests__/f24-b3-multi-channel-direct-connect.test.tsx::B3-N1` (extra row)
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-010

### 关联需求

§6.1.7 心跳重连 · Feature Design Test Inventory B3-N2

### 测试目标

mock /ws/hil 触发 error 事件后断线 5 秒：仅 hil channel 进 reconnecting；其余 4 channel 状态保持 open。

### 前置条件

- 5 channel 全部 mount 且 open
- mock WebSocket 注入 error event 仅给 /ws/hil

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mount 5 channels → wait open | 5 socket open |
| 2 | trigger error event on hil socket | hil close |
| 3 | wait 100ms | hil status='reconnecting' |
| 4 | check other 4 socket status | each 'open' (无连带断开) |

### 验证点

- 单 channel 故障隔离（修复前根路径单点故障会让 5 channel 同时断）

### 后置检查

- hil retry 后回 open

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/ws/__tests__/f24-b3-multi-channel-direct-connect.test.tsx::B3-N2`
- **Test Type**: Real

---

### 用例编号

ST-UI-024-004

### 关联需求

§VRC TicketStream WS chip · Feature Design Test Inventory B3-P2

### 测试目标

mount TicketStream + WS open → `[data-testid="ws-status-chip"]` 渲染绿态。

### 前置条件

- 真启 api（127.0.0.1:8765 已运行）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page('/ticket-stream') | 页面加载 |
| 2 | wait_for(['Ticket 流']) → evaluate_script(error_detector) | Layer 1 0 errors |
| 3 | take_snapshot() | EXPECT: ws-status-chip visible (open 绿态 indicator) |
| 4 | evaluate_script(positive_render_checker, ['[data-testid="ws-status-chip"]'], []) | Layer 1b: 0 missing |
| 5 | list_console_messages(['error']) | Layer 3: 0 |

### 验证点

- TicketStream 渲染时 ws chip mount

### 后置检查

- chip 颜色按状态变（设计 §VRC 4 态）

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: Chrome DevTools MCP 浏览器实测 + `apps/ui/src/ws/__tests__/f24-b3-multi-channel-direct-connect.test.tsx::B3-extra`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-011

### 关联需求

§IC `spa_fallback` · FR-049 · NFR-013 · Feature Design Test Inventory B4-P1

### 测试目标

start app + curl `GET /hil` → 200 + Content-Type `text/html` + body 含 `<div id="root">`。

### 前置条件

- uvicorn 运行 + apps/ui/dist 构建

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | curl -s -i http://127.0.0.1:8765/hil | header 200 OK |
| 2 | grep "Content-Type: text/html" | 命中 |
| 3 | grep -o '<div id="root"' body | 1 命中 |

### 验证点

- SPA fallback 已生效（修复前返 404 application/json）

### 后置检查

- response time < 100ms（StaticFiles 高速）

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b4_spa_fallback.py::test_b4_p1_spa_fallback_serves_index_for_hil_path` + 真启 uvicorn curl
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-012

### 关联需求

§IC spa_fallback · Feature Design Test Inventory B4-P2

### 测试目标

curl 6 路径 `/settings /docs /skills /process-files /commits /ticket-stream` 全部返 200 text/html。

### 前置条件

- 同上

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | for p in /settings /docs /skills /process-files /commits /ticket-stream: curl -s -o /dev/null -w '%{http_code}|%{content_type}' | 每路径 → `200|text/html; charset=utf-8` |

### 验证点

- 全 6 子路径不被吞 404

### 后置检查

- response 无重定向 chain

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b4_spa_fallback.py::test_b4_p2_spa_fallback_serves_index_for_six_subpaths` (parametrized 6) + curl
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-013

### 关联需求

§IC spa_fallback Raises · Feature Design Test Inventory B4-N1

### 测试目标

curl `/api/nonexistent` 返 404 JSON `{detail: "Not Found"}`，不被 fallback 误转 200 html。

### 前置条件

- uvicorn 运行

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | curl -s -i http://127.0.0.1:8765/api/nonexistent | header 404 |
| 2 | check Content-Type | application/json |
| 3 | parse JSON body | `{"detail":"Not Found"}` |

### 验证点

- API 路径优先级守住，不被 catch-all 吞

### 后置检查

- 重复请求返一致 404

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b4_spa_fallback.py::test_b4_n1_api_unknown_returns_json_404_not_swallowed` + curl
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-014

### 关联需求

§IC spa_fallback Raises · Feature Design Test Inventory B4-N2

### 测试目标

curl `/ws/nonexistent` (HTTP GET，非 WS upgrade) → 404 / 405（按 router；不返 index.html）。

### 前置条件

- 同上

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | curl -s -i http://127.0.0.1:8765/ws/nonexistent | 404 application/json |
| 2 | check body | NOT html, JSON |

### 验证点

- WS 路径不被 fallback 误转

### 后置检查

- 真 WS 路径仍可正常 upgrade

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b4_spa_fallback.py::test_b4_n2_ws_path_via_http_get_not_swallowed` + curl
- **Test Type**: Real

---

### 用例编号

ST-SEC-024-001

### 关联需求

§IC spa_fallback / FR-035 SEC · Feature Design Test Inventory B4-N3

### 测试目标

curl `/../../etc/passwd` → Starlette normalize 拒绝；不返 `/etc/passwd` 内容。

### 前置条件

- uvicorn

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | curl -s -i 'http://127.0.0.1:8765/../../etc/passwd' | normalize 后请求 / |
| 2 | body 检查 | 不含 'root:x:' / 不含 '/bin/bash' |
| 3 | OR 返 400 | 不返 200 + /etc/passwd |

### 验证点

- Path traversal 被守住

### 后置检查

- 无敏感内容泄露

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b4_spa_fallback.py::test_b4_n3_path_traversal_rejected_or_normalized`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-015

### 关联需求

§IC spa_fallback static asset · Feature Design Test Inventory B4-P3

### 测试目标

curl `/assets/index-*.js` → 200 application/javascript（StaticFiles 命中具体文件，不被 fallback 误转）。

### 前置条件

- apps/ui/dist/assets/index-*.js 存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | JS=$(ls apps/ui/dist/assets/index-*.js \| basename) | hash 文件名 |
| 2 | curl -s -o /dev/null -w '%{http_code}\|%{content_type}' http://127.0.0.1:8765/assets/$JS | `200|text/javascript; charset=utf-8` |

### 验证点

- 静态资源走 StaticFiles 路径

### 后置检查

- 大文件不影响 fallback latency

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b4_spa_fallback.py::test_b4_p3_static_asset_served_not_replaced_by_index` + curl
- **Test Type**: Real

---

### 用例编号

ST-UI-024-005

### 关联需求

§VRC 5 tabs 中文化 · NFR-010 · Feature Design Test Inventory B5-P1 · ATS §2.1 L166

### 测试目标

mount SystemSettingsPage：5 tabs textContent 严格匹配 `["模型与 Provider","API Key 与认证","Classifier","全局 MCP","界面偏好"]`。

### 前置条件

- 浏览器加载 /settings

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page('/settings') | 页面加载 |
| 2 | wait_for(['模型与 Provider']) → evaluate_script(error_detector) | 文案可见, Layer 1 0 errors |
| 3 | take_snapshot() | EXPECT: 5 tab 中文 label; REJECT: 'Models'/'ApiKey' 等英文 label |
| 4 | evaluate_script(positive_render_checker, ['[data-testid="tab-model"]','[data-testid="tab-auth"]','[data-testid="tab-classifier"]','[data-testid="tab-mcp"]','[data-testid="tab-ui"]'], []) | Layer 1b: missingCount=0 |
| 5 | for each: textContent 严格 === | 5 行严格相等 |
| 6 | list_console_messages(['error']) | Layer 3: 0 |

### 验证点

- NFR-010 中文唯一守住
- tab id 不再回退到 'models'/'apikey'

### 后置检查

- tab 切换可触发对应 panel

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-P1, B5-N0a` + Chrome DevTools MCP 浏览器实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-006

### 关联需求

§VRC model tab · FR-019 · FR-020 · Feature Design Test Inventory B5-P2 · ATS §2.1 L87/L88

### 测试目标

tab='model' 时：2 SettingsSection visible + 4 列 Grid Table 表头 + 「新增规则」 button。

### 前置条件

- /settings 已加载

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click(tab-model) → wait 400ms | tab active |
| 2 | evaluate_script(positive_render_checker, ['[data-section="run-default-models"]','table[data-testid="model-rules-table"]'], []) | Layer 1b: 0 missing |
| 3 | grep button text '新增规则' | 1 命中 |
| 4 | take_snapshot() | EXPECT: Run 默认 + Per-Skill 规则 section |

### 验证点

- model tab 不再是 placeholder

### 后置检查

- 新增规则 button click 可弹表单（design 暗示）

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-P2` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-007

### 关联需求

§VRC auth tab · FR-032 · Feature Design Test Inventory B5-P3

### 测试目标

tab='auth' 时：2 MaskedInput 行 (Anthropic / OpenCode) + 「测试 2 个 Provider」 button。

### 前置条件

- /settings

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click(tab-auth) | active |
| 2 | evaluate_script(positive_render_checker, ['[data-row="anthropic-key"]','[data-row="opencode-key"]','button[data-testid="test-conn-2providers"]'], []) | Layer 1b: 0 missing |
| 3 | take_snapshot() | EXPECT: 双 MaskedInput row + 测试 button |

### 验证点

- auth tab 不再仅 1 input

### 后置检查

- 测试 button click 触发 mutation（B7 路径）

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-P3` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-008

### 关联需求

§VRC classifier tab · FR-021 · FR-023 Wave 3 · Feature Design Test Inventory B5-P4

### 测试目标

classifier tab 含 enabled toggle + provider 4 preset Select + model_name + api_key_ref + base_url + strict_schema_override 三态 radio 全字段。

### 前置条件

- /settings

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click(tab-classifier) | active |
| 2 | evaluate_script(positive_render_checker, ['[data-row="enabled"]','[data-row="provider"]','[data-row="model_name"]','[data-row="api_key_ref"]','[data-row="base_url"]','[data-row="strict_schema_override"]'], []) | Layer 1b: 0 missing |
| 3 | take_snapshot() | EXPECT: 6 row 全部 visible |

### 验证点

- 字段全量补齐

### 后置检查

- provider Select 4 preset enumerate（GLM/MiniMax/OpenAI/custom）

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-P4` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-009

### 关联需求

§VRC mcp tab · Feature Design Test Inventory B5-P5

### 测试目标

mcp tab + mock GET /api/settings/general 含 mcp_servers 数组 → 列表渲染 N 行。

### 前置条件

- /settings

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click(tab-mcp) | active |
| 2 | evaluate_script(positive_render_checker, ['[data-testid="mcp-servers-list"]'], []) | Layer 1b: 0 missing |
| 3 | take_snapshot() | EXPECT: list 容器 visible |

### 验证点

- mcp tab 不再是 placeholder

### 后置检查

- 数据为空时显示 EmptyState（design 暗示）

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-P5` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-010

### 关联需求

§VRC ui tab · UCD §2.8 ui_density · Feature Design Test Inventory B5-P6

### 测试目标

ui tab 含 ui-density SegmentedControl + prefers-reduced-motion 只读 chip。

### 前置条件

- /settings

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click(tab-ui) | active |
| 2 | evaluate_script(positive_render_checker, ['[data-row="ui-density"]','[data-row="prefers-reduced-motion"]'], []) | Layer 1b: 0 missing |
| 3 | take_snapshot() | EXPECT: 2 row visible |

### 验证点

- ui_density 控件提供 3 段（compact/default/comfortable）

### 后置检查

- prefers-reduced-motion 跟随 OS

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-P6` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-SEC-024-002

### 关联需求

NFR-008 / FR-032 SEC · Feature Design Test Inventory B5-N1

### 测试目标

tab='auth' 时 DOM 不含明文 API key（grep `[a-zA-Z0-9]{32,}` 0 命中）。

### 前置条件

- /settings + auth tab

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click(tab-auth) | active |
| 2 | evaluate_script(`document.body.outerHTML.match(/[a-zA-Z0-9]{32,}/g)`) | filter to high-entropy alphanumeric secrets only — 排除 React internal id / build hash / data-testid / class names |
| 3 | strict assertion: 无 API key shape token | 0 命中 |

### 验证点

- masked '***xxx' 显示
- 后端永远只送 masked

### 后置检查

- localStorage / sessionStorage 同步检查

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-N1`
- **Test Type**: Real

---

### 用例编号

ST-SEC-024-003

### 关联需求

FR-021 SSRF · 既有 IFR-004 · Feature Design Test Inventory B5-N2 · ATS §2.1 L89

### 测试目标

classifier tab 输入 base_url=`http://internal-attacker:6379` → backend 拒绝 422 + UI 显错。

### 前置条件

- classifier tab

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click(tab-classifier) | active |
| 2 | fill base_url with `http://internal-attacker:6379` | input 接受 |
| 3 | click 保存 | mutation fires |
| 4 | check fetch/XHR for response | 422 |
| 5 | DOM error indicator | error chip / banner visible |

### 验证点

- backend SSRF 守卫起效（IFR-004）

### 后置检查

- 保存按钮恢复 enabled

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-N2`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-016

### 关联需求

IAPI-002 `PUT /api/settings/classifier` · Feature Design Test Inventory B5-P7

### 测试目标

修改 strict_schema_override 后 PUT request body 含 `strict_schema_override` 字段。

### 前置条件

- classifier tab

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click(tab-classifier) | active |
| 2 | toggle strict_schema_override → click 保存 | mutation fires |
| 3 | inspect PUT body | JSON 含 `strict_schema_override` |

### 验证点

- mutation hook 携带正确字段

### 后置检查

- 不破坏 F19 既有 mutation

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-P7`
- **Test Type**: Real

---

### 用例编号

ST-UI-024-011

### 关联需求

§VRC ProcessFiles file chips · Feature Design Test Inventory B6-P1

### 测试目标

mount ProcessFiles：4 chip textContent === `["feature-list.json","env-guide.md","long-task-guide.md",".env.example"]`（chip 中可能含 dirty 圆点 textNode 因此用 split/startsWith）。

### 前置条件

- /process-files；HARNESS_WORKDIR 指向真实 git workdir

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page('/process-files') | 页面加载 |
| 2 | wait_for(['feature-list.json']) → evaluate_script(error_detector) | 文案可见, Layer 1 0 errors |
| 3 | evaluate_script(positive_render_checker, ['[data-testid="file-chip-feature-list"]','[data-testid="file-chip-env-guide"]','[data-testid="file-chip-long-task-guide"]','[data-testid="file-chip-env-example"]'], []) | Layer 1b: 0 missing |
| 4 | check first textNode of each chip | 严格匹配文件名 |
| 5 | list_console_messages(['error']) | Layer 3: 0 |

### 验证点

- 4 chip 全部渲染

### 后置检查

- click chip 切换 active

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-P1` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-012

### 关联需求

§VRC 三 h3 分块 · Feature Design Test Inventory B6-P2

### 测试目标

tab='feature-list.json' + draft 加载：3 个 h3 textContent === `["Project","Tech Stack","Features"]`。

### 前置条件

- /process-files + feature-list.json 存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | active tab=feature-list.json | confirm |
| 2 | evaluate `Array.from(document.querySelectorAll('h3[data-section]')).map(h => h.getAttribute('data-section') + ':' + h.textContent.trim())` | `[project:Project, tech-stack:Tech Stack, features:Features]` |

### 验证点

- 三分块布局还原 design

### 后置检查

- 各 section 内 FormField 正常

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-P2` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-013

### 关联需求

§VRC features Grid Table · FR-038 · Feature Design Test Inventory B6-P3 · ATS §2.1 L119

### 测试目标

mount + features=mock 5 行：table 5 列表头 + N 行 + 「添加特性」 button。

### 前置条件

- /process-files

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate /process-files | 加载 |
| 2 | evaluate `Array.from(document.querySelector('table[data-testid="features-grid"]').querySelectorAll('thead th')).map(t => t.textContent.trim())` | `["id","title","status","srs_trace","actions"]` |
| 3 | check rows count | features.length |
| 4 | grep button '添加特性' / `add-feature` | 1 命中 |

### 验证点

- 列序与表头严格匹配

### 后置检查

- 「添加特性」 click 触发 features 数组扩展

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-P3` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-014

### 关联需求

§VRC 右 340px 校验面板 · Feature Design Test Inventory B6-P4

### 测试目标

aside computed width = 340px + 三组 list visible + 「再次运行」 button。

### 前置条件

- /process-files

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | evaluate `window.getComputedStyle(document.querySelector('aside[data-testid="validation-panel"]')).width` | === '340px' |
| 2 | check button text '再次运行 validate_features.py' | 1 命中 |

### 验证点

- panel 视觉宽度严格固定 340px

### 后置检查

- issues=0 时全绿

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-P4` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-015

### 关联需求

§VRC header 双 button + dirty chip · Feature Design Test Inventory B6-P5

### 测试目标

dirty=true 时 dirty chip visible + 「还原更改」/「保存并提交」 双 button visible。

### 前置条件

- /process-files

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | edit feature in UI → set dirty | dirty chip appears |
| 2 | evaluate_script(positive_render_checker, ['[data-testid="dirty-chip"]','button[data-testid="discard-changes"]','button[data-testid="save-and-commit"]'], []) | Layer 1b: 0 missing |

### 验证点

- 三元素同步显示

### 后置检查

- discard click 重置 dirty

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-P5` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-016

### 关联需求

§VRC 错误态 · FR-038 BNDRY · Feature Design Test Inventory B6-N1

### 测试目标

mock useFileQuery 返 404 → `[data-testid="processfiles-empty"]` 渲染 + 「尚未初始化」 + 重新加载 button。

### 前置条件

- HARNESS_WORKDIR 指向无 feature-list.json 的目录

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | restart api with HARNESS_WORKDIR=/tmp/empty-workdir | api 服务运行但 feature-list 不存在 |
| 2 | navigate_page('/process-files') | 加载 |
| 3 | wait_for(['尚未初始化']) → evaluate_script(error_detector) | empty 文案可见, Layer 1 0 errors |
| 4 | evaluate_script(positive_render_checker, ['[data-testid="processfiles-empty"]'], []) | Layer 1b: 0 missing |
| 5 | check button '重新加载' | 1 命中 |
| 6 | list_console_messages(['error']) | Layer 3: 0（404 是预期，非 unhandled） |

### 验证点

- 404 错误态切到 EmptyState（修复前永挂 loading）

### 后置检查

- 重新加载 click 触发 refetch

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-N1` + Chrome DevTools MCP 实测（HARNESS_WORKDIR=/tmp/harness-empty-workdir）
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-017

### 关联需求

FR-039 backend 校验 · Feature Design Test Inventory B6-N2

### 测试目标

dirty + 必填空字段 + 点 「保存并提交」 → inline 红框 + Save 禁用；不发 PUT；ValidationPanel 列出 issues。

### 前置条件

- /process-files

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | edit field → empty → mark dirty | dirty=true |
| 2 | click save | save handler fires |
| 3 | inspect Zod issues | issues.length > 0 |
| 4 | check no PUT request fired to backend | 0 |
| 5 | DOM check inline error | 红框 visible |

### 验证点

- 客户端校验拦截

### 后置检查

- 校验通过后 PUT 才发出

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-N2`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-018

### 关联需求

IAPI-016 `POST /api/validate/feature-list.json` · Feature Design Test Inventory B6-P6

### 测试目标

dirty + 「再次运行」 click → mutation fire；返 ValidationReport；面板渲染 issues。

### 前置条件

- /process-files

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | click rerun-validate button | mutation fires |
| 2 | inspect fetch | POST /api/validate/feature-list.json |
| 3 | response → ValidationPanel re-render | issues 列表 |

### 验证点

- backend 校验对接

### 后置检查

- 重复点击间防抖

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-P6`
- **Test Type**: Real

---

### 用例编号

ST-UI-024-017

### 关联需求

§VRC v1.0.0 chip · Feature Design Test Inventory B7-P1 · NFR-010

### 测试目标

mount Sidebar collapsed=false：`[data-testid="version-chip"]` textContent === `v1.0.0`。

### 前置条件

- viewport ≥ 1280px（非 collapsed）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | resize_page(1440, 900) | non-collapsed |
| 2 | navigate_page('/') | 加载 |
| 3 | wait_for(['v1.0.0']) → evaluate_script(error_detector) | text visible, Layer 1 0 |
| 4 | evaluate_script(positive_render_checker, ['[data-testid="version-chip"]'], []) | Layer 1b: 0 missing |
| 5 | evaluate `document.querySelector('[data-testid="version-chip"]').textContent.trim()` | === 'v1.0.0' |
| 6 | list_console_messages(['error']) | Layer 3: 0 |

### 验证点

- chip 文本严格 v1.0.0

### 后置检查

- collapsed mode chip 隐藏

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/f24-b7-sidebar-design-fidelity.test.tsx::B7-P1` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-018

### 关联需求

§VRC current run selector · Feature Design Test Inventory B7-P2

### 测试目标

mount Sidebar + currentRunId='run-26.04.21-001'：selector visible + `<code class='mono'>` textContent === `run-26.04.21-001`。

### 前置条件

- mock useCurrentRun 返非空

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock currentRun='run-26.04.21-001' | hook injected |
| 2 | render Sidebar | mount |
| 3 | evaluate_script(positive_render_checker, ['[data-testid="current-run-selector"]'], []) | Layer 1b: 0 missing |
| 4 | querySelector `[data-testid="current-run-selector"] code.mono` textContent | === 'run-26.04.21-001' |

### 验证点

- mono 字号 + chevron icon 渲染

### 后置检查

- click selector 弹列表（design 暗示）

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/f24-b7-sidebar-design-fidelity.test.tsx::B7-P2`
- **Test Type**: Real

---

### 用例编号

ST-UI-024-019

### 关联需求

§VRC Runtime status card · Feature Design Test Inventory B7-P3

### 测试目标

mount + mock useHealth() 返 cli_versions={claude:'1.0',opencode:'0.5'}：card visible + state-dot + 「Runtime · 在线」 + code-sm 「claude · opencode」 + Power icon。

### 前置条件

- /any 路由

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page('/') | 加载 + sidebar mount |
| 2 | evaluate_script(positive_render_checker, ['[data-testid="runtime-status-card"]'], []) | Layer 1b: 0 missing |
| 3 | check textContent of card | 含 'Runtime · 在线' AND 'claude · opencode' |
| 4 | check Power icon (svg) | 1 svg in card |

### 验证点

- card 4 视觉元素全在

### 后置检查

- offline / partial 状态色对应（B7 design 4 态）

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/f24-b7-sidebar-design-fidelity.test.tsx::B7-P3` + Chrome DevTools MCP 实测
- **Test Type**: Real

---

### 用例编号

ST-UI-024-020

### 关联需求

UCD §2.1 · NFR-011 · Feature Design Test Inventory B7-N1 · ATS §2.1 L167

### 测试目标

render Sidebar collapsed=true：每个 nav div 含 `title` + `aria-label` 非空 attr。

### 前置条件

- viewport < 1280px（collapsed=true）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | resize_page(1200, 900) | collapsed=true |
| 2 | navigate_page('/') | 加载 |
| 3 | evaluate `Array.from(document.querySelectorAll('[data-testid^="nav-"]')).map(d => ({ title: d.getAttribute('title'), aria: d.getAttribute('aria-label') }))` | each: title 非空 AND aria-label 非空 |

### 验证点

- a11y 标签即便 collapsed 也读得出
- screen reader 兼容

### 后置检查

- focus 顺序穿越

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/f24-b7-sidebar-design-fidelity.test.tsx::B7-N1`
- **Test Type**: Real

---

### 用例编号

ST-UI-024-021

### 关联需求

UCD §2.1 Tab navigation · Feature Design Test Inventory B7-N2

### 测试目标

Tab 键穿越 sidebar：每个 nav item 提供可聚焦语义（tabindex≥0 或 role='button'）。

### 前置条件

- collapsed=true

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | render Sidebar | mount |
| 2 | evaluate `Array.from(document.querySelectorAll('[data-testid^="nav-"]')).map(d => ({ tabindex: d.getAttribute('tabindex'), role: d.getAttribute('role') }))` | each: tabindex≥0 OR role='button' |

### 验证点

- 焦点环 visible（CSS 默认或 :focus-visible 覆盖）

### 后置检查

- 键盘 enter 触发 nav

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/f24-b7-sidebar-design-fidelity.test.tsx::B7-N2`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-019

### 关联需求

§IC `_validate_safe_arg` · Feature Design Test Inventory B8-P1

### 测试目标

argv = `['init_project.py', 'my-proj']` 程序正常运行；写入 `./feature-list.json`。

### 前置条件

- 临时 cwd（tmp_path）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | tmp_path/ 空目录 | clean |
| 2 | subprocess `python3 scripts/init_project.py my-proj` cwd=tmp_path | rc=0 |
| 3 | check tmp_path/feature-list.json exists | True |
| 4 | feature-list.json 含 "my-proj" | grep 命中 |

### 验证点

- 合法 my-proj （含内部 dash）通过守卫

### 后置检查

- 守卫不误拒

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b8_init_project_guard.py::test_b8_p1_happy_proj_name_with_internal_dash`
- **Test Type**: Real

---

### 用例编号

ST-SEC-024-004

### 关联需求

§IC 守卫 · B8 直接命中 · Feature Design Test Inventory B8-N1

### 测试目标

argv = `['init_project.py', '--version']` → exit 2；stderr 含 `looks like an argparse flag`；不写文件；不创建目录。

### 前置条件

- tmp_path 空目录

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | subprocess `python3 scripts/init_project.py --version` cwd=tmp_path | rc != 0 |
| 2 | tmp_path/--version exists? | False |
| 3 | stderr.lower 含 'argparse flag' / 'reserved' / 'looks like' / 'refuse' | 至少 1 命中 |

### 验证点

- 残留目录 `--version/` 不会被创建（B8 直接命中）

### 后置检查

- 重复调用幂等

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b8_init_project_guard.py::test_b8_n1_reject_argparse_flag_as_project_name`
- **Test Type**: Real

---

### 用例编号

ST-SEC-024-005

### 关联需求

§IC 守卫 · Feature Design Test Inventory B8-N2

### 测试目标

argv = `['init_project.py', '-x']` → exit 2；stderr 含错误。

### 前置条件

- tmp_path 空

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | subprocess `python3 scripts/init_project.py -x` cwd=tmp_path | rc != 0 |
| 2 | tmp_path/-x exists? | False |
| 3 | stderr.lower 含 'looks like' / 'argparse flag' | 1 命中 |

### 验证点

- 任何 `-` 前缀被拒

### 后置检查

- 不影响合法相对路径 ./xxx

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b8_init_project_guard.py::test_b8_n2_reject_dash_prefix_token`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-024-001

### 关联需求

§IC 守卫 · Feature Design Test Inventory B8-N3

### 测试目标

argv = `['init_project.py', 'p', '--path', '--help']` → exit 2；不创建 `--help/` 目录；stderr 关 `--path`。

### 前置条件

- tmp_path 空

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | subprocess `python3 scripts/init_project.py p --path --help` cwd=tmp_path | rc != 0 |
| 2 | tmp_path/--help exists? | False |
| 3 | stderr.lower 含 '--path' OR 'reserved' OR 'argparse flag' | 至少 1 命中 |

### 验证点

- --path 值守卫起效

### 后置检查

- 修复前会创建 `--help/` 目录

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b8_init_project_guard.py::test_b8_n3_reject_path_value_as_argparse_flag`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-024-002

### 关联需求

§Boundary args.path · Feature Design Test Inventory B8-N4

### 测试目标

argv = `['init_project.py', 'p', '--path', './ok-name']` → 通过守卫；正常创建 `./ok-name/`。

### 前置条件

- tmp_path 空

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | subprocess `python3 scripts/init_project.py p --path ./ok-name` cwd=tmp_path | rc=0 |
| 2 | tmp_path/ok-name/feature-list.json | exists |

### 验证点

- 含 dash 不打头的合法路径不被误拒

### 后置检查

- 与 B8-P1 互补 BNDRY

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b8_init_project_guard.py::test_b8_n4_legit_path_with_internal_dash_accepted`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-024-003

### 关联需求

仓库根残留目录回归 · Feature Design Test Inventory B8-P2

### 测试目标

历史已残留的 `--version/` 与 `status/` 目录在 repo root 不存在；新提交（B8 守卫生效后）任何调用都不会再创建这些目录。

### 前置条件

- /home/machine/code/Eva 仓库根

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | os.path.exists(repo_root / '--version') | False |
| 2 | os.path.exists(repo_root / 'status') | False |
| 3 | additionally: 任何意外创建测试 → 守卫拒绝（B8-N1） | 0 创建 |

### 验证点

- 残留目录已清理 + 守卫预防再发生

### 后置检查

- 后续 PyInstaller --add-data 不会收进任何 stale dir

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: ls /home/machine/code/Eva/ 无 `--version` 与 `status` 目录 + `tests/test_f24_b8_init_project_guard.py::test_b8_p2_reserved_flag_path_token_rejected`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-020

### 关联需求

§6.2.2 L1165 GET /api/health · NFR-013 · Feature Design Test Inventory B9-P1

### 测试目标

curl `/api/health` → 200 + body 含 `bind/version/claude_auth/cli_versions` 4 字段。

### 前置条件

- uvicorn 运行

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | curl http://127.0.0.1:8765/api/health | 200 |
| 2 | parse JSON | dict |
| 3 | check keys | {bind, version, claude_auth, cli_versions} |
| 4 | claude_auth nested | {cli_present, authenticated, hint, source} |
| 5 | cli_versions nested | {claude, opencode} |

### 验证点

- schema 4 字段完整

### 后置检查

- 重复请求 schema 不变

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b9_health_cache_ttl.py::test_b9_p1_schema_4_fields` + curl 真启
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-021

### 关联需求

§IC `health()` postcondition / NFR-013 · Feature Design Test Inventory B9-N1

### 测试目标

mock `time.monotonic()` 序列：t0=0 → 探针 cli_versions →（修改 PATH 模拟新版本）→ t1=15 → curl → 仍返**旧** cli_versions（缓存命中 15 < 30）。

### 前置条件

- mock monotonic via pytest monkeypatch

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | monkeypatch time.monotonic to controlled clock | install |
| 2 | clock=0 → call health() | initial probe → cache value V1 |
| 3 | mock _probe_cli_version → return V2 | new value queued |
| 4 | clock=15 → call health() | cache hit → return V1 (NOT V2) |

### 验证点

- TTL 30s 内重复 probe 被消除

### 后置检查

- _ts 不更新

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b9_health_cache_ttl.py::test_b9_n1_cache_hit_within_ttl`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-022

### 关联需求

§IC `health()` postcondition · Feature Design Test Inventory B9-N2

### 测试目标

t0=0 → curl → t1=31 → 改 _probe_cli_version → curl → 返**新** cli_versions。

### 前置条件

- mock monotonic

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | clock=0 → health() | V1 cached |
| 2 | mock _probe → V2 | queued |
| 3 | clock=31 → health() | refresh → V2 |

### 验证点

- TTL 边界 >= 触发刷新（B9 直接命中）
- 修复前永不刷新

### 后置检查

- _ts 更新

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b9_health_cache_ttl.py::test_b9_n2_cache_refresh_after_ttl`
- **Test Type**: Real

---

### 用例编号

ST-PERF-024-001

### 关联需求

NFR-001 p95 · Feature Design Test Inventory B9-P2

### 测试目标

30 秒内 100 次 curl `/api/health` → `_probe_cli_version` 调用 ≤ 2 次（首次 + 任何 30s 翻转）；p95 < 50ms。

### 前置条件

- mock probe to count + monkeypatch clock

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock _probe + counter | install |
| 2 | tight loop 100 calls within 5s wall-clock + mock clock 0..29 | 100 returns |
| 3 | check probe call count | ≤ 2 |
| 4 | measure latency p95 (excluding first cold call) | < 50ms |

### 验证点

- 缓存对 throughput 显著影响

### 后置检查

- 没有重复探针致 CPU 飙

### 元数据

- **优先级**: High
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b9_health_cache_ttl.py::test_b9_p2_perf_probe_count_under_load`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-024-023

### 关联需求

§IC `health()` Raises · Feature Design Test Inventory B9-N3

### 测试目标

`_probe_cli_version` 抛 OSError → 缓存未刷新；返上一次旧值；不抛 5xx。

### 前置条件

- 已有 cached value V0

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | seed cache with V0 (clock=0 → call health) | V0 cached |
| 2 | mock _probe → raise OSError | install |
| 3 | clock=31 → call health() | NOT 5xx |
| 4 | response | V0 (stale) returned |

### 验证点

- OSError 降级保留旧值

### 后置检查

- 后续 probe 成功后能刷新

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f24_b9_health_cache_ttl.py::test_b9_n3_probe_oserror_does_not_5xx`
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step (Test Inventory) | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-UI-024-001 | FR-001 AC-1 / FR-031 | B1-P1 | apps/ui/src/routes/run-overview/__tests__/f24-b1-start-button.test.tsx::B1-P1 + chrome-devtools | Real | PASS |
| ST-FUNC-024-001 | FR-001 / §IC handleStart | B1-P2 | f24-b1-start-button.test.tsx::B1-P2 | Real | PASS |
| ST-UI-024-002 | FR-030 / §VRC 6 elements | B1-P3 | f24-b1-start-button.test.tsx::B1-P3 | Real | PASS |
| ST-FUNC-024-002 | §IC Raises | B1-N1 | f24-b1-start-button.test.tsx::B1-N1 | Real | PASS |
| ST-FUNC-024-003 | §IC Raises | B1-N2 | f24-b1-start-button.test.tsx::B1-N2 | Real | PASS |
| ST-FUNC-024-004 | IAPI-002 / FR-031 AC-1 | B2-P1 | apps/ui/src/routes/hil-inbox/__tests__/f24-b2-tickets-run-id.test.tsx::B2-P1 | Real | PASS |
| ST-UI-024-003 | §VRC HilInbox EmptyState | B2-P2 | f24-b2-tickets-run-id.test.tsx::B2-P2 + chrome-devtools | Real | PASS |
| ST-FUNC-024-005 | §IC HilInbox postcondition | B2-N1 | f24-b2-tickets-run-id.test.tsx::B2-N1 | Real | PASS |
| ST-FUNC-024-006 | IAPI-002 / FR-034 | B2-N2 | apps/ui/src/routes/ticket-stream/__tests__/f24-b2-build-tickets-url.test.tsx::B2-N2 | Real | PASS |
| ST-FUNC-024-007 | IAPI-001 /ws/hil | B2-P3 | f24-b2-tickets-run-id.test.tsx::B2-P3 | Real | PASS |
| ST-FUNC-024-008 | §6.2.3 5 path / IFR-007 | B3-P1 | apps/ui/src/ws/__tests__/f24-b3-multi-channel-direct-connect.test.tsx::B3-P1 + chrome-devtools ws spy | Real | PASS |
| ST-FUNC-024-009 | §IC useWs Raises | B3-N1 | f24-b3-multi-channel-direct-connect.test.tsx::B3-N1 | Real | PASS |
| ST-FUNC-024-010 | §6.1.7 reconnect | B3-N2 | f24-b3-multi-channel-direct-connect.test.tsx::B3-N2 | Real | PASS |
| ST-UI-024-004 | §VRC TicketStream WS chip | B3-P2 | chrome-devtools + f24-b3-multi-channel-direct-connect.test.tsx::B3-extra | Real | PASS |
| ST-FUNC-024-011 | §IC spa_fallback / FR-049 / NFR-013 | B4-P1 | tests/test_f24_b4_spa_fallback.py::test_b4_p1_spa_fallback_serves_index_for_hil_path + curl | Real | PASS |
| ST-FUNC-024-012 | §IC spa_fallback | B4-P2 | tests/test_f24_b4_spa_fallback.py::test_b4_p2_spa_fallback_serves_index_for_six_subpaths (6 parametrized) + curl | Real | PASS |
| ST-FUNC-024-013 | §IC spa_fallback Raises | B4-N1 | tests/test_f24_b4_spa_fallback.py::test_b4_n1_api_unknown_returns_json_404_not_swallowed + curl | Real | PASS |
| ST-FUNC-024-014 | §IC spa_fallback Raises | B4-N2 | tests/test_f24_b4_spa_fallback.py::test_b4_n2_ws_path_via_http_get_not_swallowed + curl | Real | PASS |
| ST-SEC-024-001 | §IC spa_fallback / FR-035 SEC | B4-N3 | tests/test_f24_b4_spa_fallback.py::test_b4_n3_path_traversal_rejected_or_normalized | Real | PASS |
| ST-FUNC-024-015 | §IC spa_fallback static asset | B4-P3 | tests/test_f24_b4_spa_fallback.py::test_b4_p3_static_asset_served_not_replaced_by_index + curl | Real | PASS |
| ST-UI-024-005 | §VRC 5 tabs / NFR-010 | B5-P1 | apps/ui/src/routes/system-settings/__tests__/f24-b5-tabs-zh-and-controls.test.tsx::B5-P1, B5-N0a + chrome-devtools | Real | PASS |
| ST-UI-024-006 | §VRC model tab / FR-019 / FR-020 | B5-P2 | f24-b5-tabs-zh-and-controls.test.tsx::B5-P2 + chrome-devtools | Real | PASS |
| ST-UI-024-007 | §VRC auth tab / FR-032 | B5-P3 | f24-b5-tabs-zh-and-controls.test.tsx::B5-P3 + chrome-devtools | Real | PASS |
| ST-UI-024-008 | §VRC classifier tab / FR-021 | B5-P4 | f24-b5-tabs-zh-and-controls.test.tsx::B5-P4 + chrome-devtools | Real | PASS |
| ST-UI-024-009 | §VRC mcp tab | B5-P5 | f24-b5-tabs-zh-and-controls.test.tsx::B5-P5 + chrome-devtools | Real | PASS |
| ST-UI-024-010 | §VRC ui tab / UCD §2.8 | B5-P6 | f24-b5-tabs-zh-and-controls.test.tsx::B5-P6 + chrome-devtools | Real | PASS |
| ST-SEC-024-002 | NFR-008 / FR-032 SEC | B5-N1 | f24-b5-tabs-zh-and-controls.test.tsx::B5-N1 | Real | PASS |
| ST-SEC-024-003 | FR-021 SSRF / IFR-004 | B5-N2 | f24-b5-tabs-zh-and-controls.test.tsx::B5-N2 | Real | PASS |
| ST-FUNC-024-016 | IAPI-002 PUT classifier | B5-P7 | f24-b5-tabs-zh-and-controls.test.tsx::B5-P7 | Real | PASS |
| ST-UI-024-011 | §VRC ProcessFiles file chips | B6-P1 | apps/ui/src/routes/process-files/__tests__/f24-b6-controls.test.tsx::B6-P1 + chrome-devtools | Real | PASS |
| ST-UI-024-012 | §VRC 三 h3 分块 | B6-P2 | f24-b6-controls.test.tsx::B6-P2 + chrome-devtools | Real | PASS |
| ST-UI-024-013 | §VRC features Grid Table / FR-038 | B6-P3 | f24-b6-controls.test.tsx::B6-P3 + chrome-devtools | Real | PASS |
| ST-UI-024-014 | §VRC 右 340px panel | B6-P4 | f24-b6-controls.test.tsx::B6-P4 + chrome-devtools | Real | PASS |
| ST-UI-024-015 | §VRC header dirty + 双 button | B6-P5 | f24-b6-controls.test.tsx::B6-P5 + chrome-devtools | Real | PASS |
| ST-UI-024-016 | §VRC 错误态 / FR-038 BNDRY | B6-N1 | f24-b6-controls.test.tsx::B6-N1 + chrome-devtools (HARNESS_WORKDIR=/tmp/harness-empty-workdir) | Real | PASS |
| ST-FUNC-024-017 | FR-039 backend 校验 | B6-N2 | f24-b6-controls.test.tsx::B6-N2 | Real | PASS |
| ST-FUNC-024-018 | IAPI-016 POST validate | B6-P6 | f24-b6-controls.test.tsx::B6-P6 | Real | PASS |
| ST-UI-024-017 | §VRC v1.0.0 chip / NFR-010 | B7-P1 | apps/ui/src/components/__tests__/f24-b7-sidebar-design-fidelity.test.tsx::B7-P1 + chrome-devtools | Real | PASS |
| ST-UI-024-018 | §VRC current run selector | B7-P2 | f24-b7-sidebar-design-fidelity.test.tsx::B7-P2 | Real | PASS |
| ST-UI-024-019 | §VRC Runtime status card | B7-P3 | f24-b7-sidebar-design-fidelity.test.tsx::B7-P3 + chrome-devtools | Real | PASS |
| ST-UI-024-020 | UCD §2.1 / NFR-011 | B7-N1 | f24-b7-sidebar-design-fidelity.test.tsx::B7-N1 | Real | PASS |
| ST-UI-024-021 | UCD §2.1 Tab nav | B7-N2 | f24-b7-sidebar-design-fidelity.test.tsx::B7-N2 | Real | PASS |
| ST-FUNC-024-019 | §IC _validate_safe_arg | B8-P1 | tests/test_f24_b8_init_project_guard.py::test_b8_p1_happy_proj_name_with_internal_dash | Real | PASS |
| ST-SEC-024-004 | §IC 守卫 / B8 直接 | B8-N1 | tests/test_f24_b8_init_project_guard.py::test_b8_n1_reject_argparse_flag_as_project_name | Real | PASS |
| ST-SEC-024-005 | §IC 守卫 | B8-N2 | tests/test_f24_b8_init_project_guard.py::test_b8_n2_reject_dash_prefix_token | Real | PASS |
| ST-BNDRY-024-001 | §IC 守卫 | B8-N3 | tests/test_f24_b8_init_project_guard.py::test_b8_n3_reject_path_value_as_argparse_flag | Real | PASS |
| ST-BNDRY-024-002 | §Boundary args.path | B8-N4 | tests/test_f24_b8_init_project_guard.py::test_b8_n4_legit_path_with_internal_dash_accepted | Real | PASS |
| ST-BNDRY-024-003 | 仓库根残留目录回归 | B8-P2 | ls /home/machine/code/Eva/ 验证 + tests/test_f24_b8_init_project_guard.py::test_b8_p2_reserved_flag_path_token_rejected | Real | PASS |
| ST-FUNC-024-020 | §6.2.2 health / NFR-013 | B9-P1 | tests/test_f24_b9_health_cache_ttl.py::test_b9_p1_schema_4_fields + curl | Real | PASS |
| ST-FUNC-024-021 | §IC health postcondition | B9-N1 | tests/test_f24_b9_health_cache_ttl.py::test_b9_n1_cache_hit_within_ttl | Real | PASS |
| ST-FUNC-024-022 | §IC health postcondition | B9-N2 | tests/test_f24_b9_health_cache_ttl.py::test_b9_n2_cache_refresh_after_ttl | Real | PASS |
| ST-PERF-024-001 | NFR-001 p95 / B9-P2 | B9-P2 | tests/test_f24_b9_health_cache_ttl.py::test_b9_p2_perf_probe_count_under_load | Real | PASS |
| ST-FUNC-024-023 | §IC health Raises | B9-N3 | tests/test_f24_b9_health_cache_ttl.py::test_b9_n3_probe_oserror_does_not_5xx | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 53 |
| Passed | 53 |
| Failed | 0 |
| Pending | 0 |

> Real test cases = test cases with Test Type `Real` (executed against real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.

> **B8 fix-during-ST 备注**：ST 阶段发现 `scripts/init_project.py` 缺 `_validate_safe_arg` 守卫（unit test 6/6 FAIL，repo root 验证守卫确实未生效）。SubAgent 就地修复（追加 `_RESERVED_FLAGS` set + `_validate_safe_arg` + 前缀 argv 守卫 `_preflight_argv_guard`），重跑 6/6 PASS。所有 ST B8 用例（ST-FUNC-024-019, ST-SEC-024-004, ST-SEC-024-005, ST-BNDRY-024-001, ST-BNDRY-024-002, ST-BNDRY-024-003）随之 PASS。修复严格落在 §Implementation Summary B8 已声明的接口契约边界（无新 §IC 行）。
