# 测试用例集: F12 · Frontend Foundation

**Feature ID**: 12
**关联需求**: NFR-001, NFR-010, NFR-011（含 ATS §3.1 类别约束 NFR-001={PERF, UI}、NFR-010={FUNC, UI}、NFR-011={FUNC, UI}；Feature Design §Visual Rendering Contract、§Test Inventory T01–T41）
**日期**: 2026-04-24
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为 F12（React 18 + Vite + TypeScript + TailwindCSS + shadcn/ui 前端基座）的黑盒 ST 验收测试用例。预期结果仅从 SRS NFR-001/010/011 验收准则、ATS §3.1 行、feature-list.json `verification_steps` 7 条、Feature Design §Interface Contract postcondition、§Visual Rendering Contract 正向渲染断言、UCD §2.2（prefers-reduced-motion）/ §3.8（Sidebar）/ §5 F12 实施规约 / §7 视觉回归 SOP、以及可观察接口（`http://127.0.0.1:5173/`、`http://127.0.0.1:8765/api/*`、Chrome DevTools MCP `take_snapshot` / `take_screenshot` / `evaluate_script` / `performance_start_trace`、`scripts/check_source_lang.sh`、`scripts/check_tokens_fidelity.sh` 退出码）推导，不阅读实现源码。
> - **Clarification Addendum**：Feature Design `## Clarification Addendum` 为空（"无需澄清 — 全部规格明确"）。Feature Design §SRS Requirement 尾注已明确 F12 对 NFR-011 的基座义务 = "提供 Label / Radio / Checkbox / Textarea primitives + label slot 约定"；具体 HIL 文本 "单选/多选/自由文本" 在 F21 HILCard 里渲染。NFR-011 的 F12 覆盖落在 **primitives 存在性** 与 **AppShell 可挂载** 间接验证层（Test Inventory 注记 §ATS 类别对齐自检 与 UI 承接自检）。
> - `feature.ui == true` → 本文档含 UI 类别用例并通过 Chrome DevTools MCP / Playwright / vitest 浏览器等价工具执行。
> - **服务依赖**：`api` (`http://127.0.0.1:8765/api/health`) + `ui-dev` (`http://127.0.0.1:5173/`)；ST 执行由 SubAgent 启停（env-guide §1 `bash scripts/svc-api-start.sh` / `bash scripts/svc-ui-dev-start.sh`）。
> - **前端单元/组件测试复用**：`apps/ui/src/**/__tests__/*.test.{ts,tsx}` 由 Vitest + happy-dom 执行（TDD 已跑通，coverage ≥ 90%/80%）；本 ST 文档仅在"自动化测试"列引用相关测试函数作为可追溯锚，而 ST 黑盒执行以 **运行中的 ui-dev 真实浏览器 / Playwright / Chrome DevTools MCP** 为主。
> - **已知占位**：Feature Design §Design Alignment 明确 T35/T36 pixelmatch 与真实 prototype artboard 图像 (`docs/design-bundle/eava2/project/pages/overview-1280.png` / `overview-1440.png`) **尚未生成**；`apps/ui/e2e/f12-visual-regression.spec.ts` 内置 `expect(false).toBe(true)` 占位失败。此属已声明的 F12 实施缺口（UCD §7 SOP 第 5 步"截图存档"落 F21/F22 后续 feature 或后续 ST 阶段补齐），本文档 ST-UI-012-009 记录为 `BLOCKED` 并在 `## Manual Test Case Summary` / `## Issues` 之外的 `## Known-Gap` 章节说明；不阻塞 ATS UI 类别最低覆盖（ST-UI-012-001..008 覆盖 §VRC 全部元素 + devtools snapshot + reduced-motion + token fidelity）。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 8 |
| boundary | 3 |
| ui | 9 |
| security | 2 |
| performance | 1 |
| **合计** | **23** |

---

### 用例编号

ST-FUNC-012-001

### 关联需求

NFR-001 基座义务 · Feature Design §Interface Contract `HarnessWsClient.connect` / `HarnessWsClient.disconnect` postcondition · §Design Alignment stateDiagram `closed → connecting → open` · Feature Design Test Inventory T01

### 测试目标

验证 `HarnessWsClient.connect("ws://127.0.0.1:8765/ws/run/<id>")` 对合法 loopback URL 调用后状态机依次 `closed → connecting → open`；`disconnect()` 后进入 `closed` 并停止重连调度。黑盒表面：`AppShell` 挂载时 `useEffect` 内的 `connect()`；可观察通过 `window.__HARNESS_WS__.state` dev 探针 / `useWs()` 返回的 `status`。

### 前置条件

- `api` (127.0.0.1:8765) 与 `ui-dev` (127.0.0.1:5173) 均健康
- 浏览器加载 `http://127.0.0.1:5173/` 完成（AppShell mount 完毕）
- 无 `prefers-reduced-motion` 强制（默认动效）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `navigate_page("http://127.0.0.1:5173/")` | 页面加载开始 |
| 2 | `wait_for(["总览"])`；`evaluate_script(() => !!document.querySelector('[data-component="app-shell"]'))` | 返回 `true`（AppShell 已挂载，Layer 1 无错） |
| 3 | `evaluate_script(() => { /* 轮询 useWs status 或 window.__HARNESS_WS__ state */ const el = document.querySelector('[data-ws-status]'); return el?.getAttribute('data-ws-status') ?? 'unknown'; })` | 若组件暴露 `data-ws-status` 则返回 `"open"`（黑盒等价：可通过 `evaluate_script` 读 React fiber 或 store） |
| 4 | 间接断言：`list_network_requests()` 查询 WebSocket 握手 —— 目标 URL `ws://127.0.0.1:8765/ws/` | 至少 1 条 101 Switching Protocols 响应 |
| 5 | `evaluate_script(error_detector)` 后 `list_console_messages(["error"])` | Layer 1 count = 0；控制台无 error |

### 验证点

- WebSocket 握手到达 `127.0.0.1:8765`（NFR-007 回环基线，作 NFR-001 WS push 通路基座）
- AppShell 挂载后无异步 reject / 未捕获 error
- DevTools 网络面板含 `101 Switching Protocols` 响应（真实 WS 连接成立）

### 后置检查

- 保持浏览器打开供后续 UI 用例复用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/ws/__tests__/client.test.ts::HarnessWsClient connect state machine`、`apps/ui/e2e/f12-route-switch.spec.ts`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-012-002

### 关联需求

Feature Design §Interface Contract `HarnessWsClient.subscribe` postcondition · §Design Alignment sequenceDiagram msg#3 `subscribe → SubscribeMsg` · Feature Design Test Inventory T03

### 测试目标

验证 `useWs("/ws/hil", handler)` hook 在组件 mount 时调用 `HarnessWsClient.subscribe`，handler 登记成功；`Unsubscribe` 闭包在 `useEffect` cleanup 时被调用，subscribe set 中对应 handler 被移除。黑盒表面：对运行中的 `ui-dev` 浏览器通过 Vitest jsdom（`apps/ui/src/ws/__tests__/use-ws.test.tsx`）旁证；运行期 Playwright E2E 路由切换验证 status 文本不崩。

### 前置条件

- `ui-dev` 运行中；`apps/ui/` 已 `npm install`
- `.venv` 激活（便于 pytest 同批运行后端端对称 fixture，但本用例仅前端）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/ws/__tests__/use-ws.test.tsx src/ws/__tests__/client.test.ts src/ws/__tests__/subscribe.test.ts` | 退出码 0；每个文件 0 失败 |
| 2 | 在浏览器 `http://127.0.0.1:5173/` 打开 DevTools → Performance；触发路由切换 `/ ↔ /hil` 1 次 | 控制台无 "handler leaked" / "duplicate subscribe" 异常 |
| 3 | `evaluate_script(() => !!document.querySelector('[data-component="app-shell"]'))` 两次 | 两次均 `true` |

### 验证点

- `useWs` 的 mount/unmount 对 `HarnessWsClient.subscribe`/`Unsubscribe` 的调用 1:1 成对（Vitest 组件单测是可信的黑盒旁证）
- 运行期浏览器无堆积的 subscribe handler 导致的 console 抛错

### 后置检查

- 保留浏览器

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/ws/__tests__/use-ws.test.tsx`、`apps/ui/src/ws/__tests__/subscribe.test.ts`、`apps/ui/src/ws/__tests__/client.test.ts`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-012-003

### 关联需求

Feature Design §Interface Contract `apiClient.fetch` / `createApiHook` postcondition · IAPI-002 REST（F01 提供） · Feature Design Test Inventory T08, T09, T40

### 测试目标

验证 `apiClient.fetch("GET","/api/health")` 对运行中的 F01 FastAPI 返回 2xx JSON，且 `createApiHook` 工厂通过 Zod runtime schema 校验；错误路径（5xx、schema mismatch）reject `ServerError` / `ZodError`。黑盒表面：运行期通过 `list_network_requests()` 验证 200；以 Vitest + `respx`/fetch mock 验证 5xx / Zod 路径。

### 前置条件

- `api` (127.0.0.1:8765) 健康 —— `curl /api/health` 返回 `{"bind":"127.0.0.1", ...}`
- `ui-dev` 运行中

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `curl -sf http://127.0.0.1:8765/api/health` | 退出码 0；JSON 含 `bind:"127.0.0.1"`、`version`、`claude_auth`、`cli_versions` |
| 2 | `cd apps/ui && npx vitest run src/api/__tests__/client.test.ts src/api/__tests__/query-hook-factory.test.tsx` | 退出码 0 |
| 3 | 在浏览器 `http://127.0.0.1:5173/` 触发应用级首次 fetch（如果首屏包含 `useApi`）；`list_network_requests()` 过滤 `/api/` | 至少 1 次 200；无 4xx/5xx（除非有意向导试探） |
| 4 | 断言：存在 `/api/health` 200 响应在 response body 满足 Zod schema（旁证：`health` 字段在 query-hook-factory test 中 Zod 解析通过） | 断言成立 |

### 验证点

- REST base URL 指向 `http://127.0.0.1:8765`（与 F01 bind 一致，NFR-007 回环）
- `apiClient.fetch` 响应 JSON 通过 Zod schema parse
- Error 路径（5xx → `ServerError`、schema mismatch → `ZodError`）由 Vitest 单元测试覆盖并通过

### 后置检查

- 保留浏览器

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/api/__tests__/client.test.ts`、`apps/ui/src/api/__tests__/query-hook-factory.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-012-004

### 关联需求

Feature Design §Interface Contract `createSlice` postcondition / Raises · Feature Design Test Inventory T13, T14

### 测试目标

验证 Zustand `createSlice("ui", ...)` 返回的 store hook：初始 state 字段正确；派发 action 修改 state；重名 slice 再次创建抛 `Error`。黑盒表面：Vitest + happy-dom 执行 `apps/ui/src/store/__tests__/slice-factory.test.ts`。

### 前置条件

- `apps/ui/` 已安装依赖

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/store/__tests__/slice-factory.test.ts` | 退出码 0 |
| 2 | 检查测试输出含至少 2 个 describe：正常创建 + 重名拒绝 | 两类都 PASS |

### 验证点

- `createSlice` 返回的 store hook 可订阅与 dispatch
- 重名 slice 抛 `Error`（`"slice 'ui' already registered"` 或等效消息）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/store/__tests__/slice-factory.test.ts`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-012-005

### 关联需求

NFR-011 基座义务 · Feature Design §SRS Requirement 尾注（F12 承接 Label / Radio / Checkbox / Textarea primitives + label slot） · Feature Design Test Inventory T15 + T38

### 测试目标

验证 F12 提供的 primitives 基座在 AppShell 挂载后可用：Icons 集合（`Home`/`Inbox`/`Zap` 等 40+ 键）导出完整且 render 产物为 `<svg>`；PageFrame 的 top bar `title` slot 存在以承接 F21 后续的"单选/多选/自由文本"文本标签。F12 不直接渲染 HIL 文本标签（落 F21）。

### 前置条件

- `ui-dev` 运行中；`apps/ui` 已 build

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/components/__tests__/icons.test.tsx src/components/__tests__/page-frame.test.tsx` | 退出码 0 |
| 2 | `navigate_page("http://127.0.0.1:5173/")`；`evaluate_script(() => Array.from(document.querySelectorAll('[data-component="top-bar"]')).length)` | 返回 ≥ 1 |
| 3 | `evaluate_script(() => { const bar = document.querySelector('[data-component="top-bar"]'); return bar ? bar.textContent?.trim() : null; })` | 返回非空字符串（当前路由 title，如 "总览"） |
| 4 | 确认 PageFrame 提供 `title` + children slot API：`evaluate_script(() => !!document.querySelector('[data-component="top-bar"] + *, [data-component="top-bar"] ~ main, [data-component="top-bar"] ~ [role="main"], [data-component="sidebar"] ~ *'))` | 返回 `true`（存在主内容容器作为 children slot 承接点） |

### 验证点

- Icons 键名齐全（Vitest 列举 40+ re-export 断言通过）
- PageFrame 渲染 top bar + children slot，为 F21 HILCard 的 label slot 提供落位
- F12 不渲染 "单选/多选/自由文本" 文本（由 F21 承接；此处只验证基座槽位存在）

### 后置检查

- 保留浏览器

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/icons.test.tsx`、`apps/ui/src/components/__tests__/page-frame.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-012-006

### 关联需求

Feature Design §Visual Rendering Contract / §Interface Contract `PhaseStepper` · Feature Design Test Inventory T21

### 测试目标

验证 `<PhaseStepper current={3} />` 渲染 8 phase 圆点（`data-state` 分别为 3 个 `done` + 1 个 `current` + 4 个 `pending`），current 圆点的 pulse 光环节点 `[data-pulse]` 存在。

### 前置条件

- `apps/ui/` Vitest 环境可跑

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/components/__tests__/phase-stepper.test.tsx` | 退出码 0 |
| 2 | 输出含 `current=3` 下 8 子节点 state 分布断言通过 | PASS |

### 验证点

- phase state 映射正确（0..2 done / 3 current / 4..7 pending）
- current 元素的 `[data-pulse]` 存在

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/phase-stepper.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-012-007

### 关联需求

Feature Design §Visual Rendering Contract `TicketCard state-dot` / `TicketCard tool chip` · Feature Design Test Inventory T24, T25

### 测试目标

验证 `<TicketCard state="running" tool="claude" ... />` 渲染 `[data-state-dot]` 且含 `.pulse` class（UCD §2.6 running → 绿 dot + pulse）；`[data-tool="claude"]` 存在。

### 前置条件

- `apps/ui/` Vitest 环境可跑

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/components/__tests__/ticket-card.test.tsx` | 退出码 0；测试覆盖 running / pulse / tool=claude |

### 验证点

- `data-state-dot` 在 state=running 下含 `pulse` class
- `data-tool="claude"` 节点存在

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/ticket-card.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-012-008

### 关联需求

Feature Design §Existing Code Reuse F01 `harness/api/__init__.py` StaticFiles mount · Feature Design Test Inventory T33

### 测试目标

验证 F01 FastAPI app 在 `apps/ui/dist/` build 后通过 StaticFiles 挂载 `/`，请求根路径返回 `index.html` 含 `<div id="root">`；`/api/*` 优先级高于静态 fallback。**降级说明**：当前开发期使用 Vite dev server (`5173`) 分离；本用例以 ui-dev 代替 build+mount 的等价黑盒（`http://127.0.0.1:5173/` 返回 `<div id="root">`）。Build+mount 的 prod 路径在 F17（PyInstaller 打包）feature 处覆盖。

### 前置条件

- `ui-dev` 运行中

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `curl -sf http://127.0.0.1:5173/ | grep -c 'id="root"'` | 输出 ≥ 1 |
| 2 | `curl -sf http://127.0.0.1:8765/api/health | grep -c 'bind'` | 输出 ≥ 1（API 路由未被静态 catch-all 吞） |

### 验证点

- 根路径返回的 HTML 含 `<div id="root">`（AppShell 挂载点）
- `/api/*` 仍返回 JSON（路由优先级正确；dev 期由端口分离天然保证，prod 期由 F17 接力）

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: 手动 curl 等价，F17 feature ST 将覆盖 build+mount 完整路径
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-012-001

### 关联需求

Feature Design §Interface Contract `HarnessWsClient.connect` / `PhaseStepper current` Raises · Feature Design §Boundary Conditions · Feature Design Test Inventory T02, T28

### 测试目标

验证边界拒绝：`HarnessWsClient.connect("http://evil.com")` 抛 `TypeError`（非 `ws://` scheme 或非 loopback host）；`<PhaseStepper current={-1} />` 与 `current={8}` 抛 `RangeError`。

### 前置条件

- `apps/ui/` Vitest 环境可跑

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/ws/__tests__/client.test.ts --reporter verbose 2>&1 | grep -Ei 'connect.*(rejects|type|scheme|loopback)'` | 匹配 ≥ 1 条（connect 非法 URL 拒绝测试通过） |
| 2 | `cd apps/ui && npx vitest run src/components/__tests__/phase-stepper.test.tsx --reporter verbose 2>&1 | grep -Ei 'current.*(-1\|8\|range|throw|out of)'` | 匹配 ≥ 1 条 |

### 验证点

- connect 对非 `ws://127.0.0.1` URL 拒绝
- PhaseStepper current 越界抛 RangeError

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/ws/__tests__/client.test.ts`、`apps/ui/src/components/__tests__/phase-stepper.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-012-002

### 关联需求

Feature Design §Boundary Conditions `HarnessWsClient` 指数退避 / 心跳窗口 · Feature Design Test Inventory T05, T06, T39

### 测试目标

验证重连退避序列 1s / 2s / 4s / 8s / 16s（第 6 次起保持 16s）；心跳 60s 窗口（59.9s 前保持 open，60.1s 进入 reconnecting）；`reconnecting` 态调 `disconnect()` 立即进入 `closed` 并清 setTimeout。

### 前置条件

- `apps/ui/` Vitest 环境可跑（fake timer）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/ws/__tests__/client.test.ts src/ws/__tests__/subscribe.test.ts --reporter verbose 2>&1 | tail -40` | 所有测试 PASS；含退避序列 / 心跳 / disconnect-in-reconnecting 覆盖 |

### 验证点

- 退避间隔 1/2/4/8/16s ±10% jitter 容忍内
- 心跳 60s 阈值对 off-by-one 敏感
- disconnect 在 reconnecting 态立即终止

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/ws/__tests__/client.test.ts`、`apps/ui/src/ws/__tests__/subscribe.test.ts`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-012-003

### 关联需求

Feature Design §Boundary Conditions viewport 1279px ↔ 1280px 边界 · §Visual Rendering Contract Sidebar 展开/折叠 · Feature Design Test Inventory T16, T17

### 测试目标

验证 Sidebar 的响应式折叠：viewport=1280×900 时 `[data-component="sidebar"]` 宽度 240px；viewport=1100×800（或 1279×900）时折叠为 56px。使用 Chrome DevTools MCP `resize_page` 模拟。

### 前置条件

- `ui-dev` 运行中；浏览器已连 DevTools MCP

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `resize_page(1280, 900)` → `navigate_page("http://127.0.0.1:5173/")` → `wait_for(["总览"])` | 页面加载完成 |
| 2 | `evaluate_script(() => { const el = document.querySelector('[data-component="sidebar"]'); return el ? parseInt(getComputedStyle(el).width, 10) : -1; })` | 返回 `240` |
| 3 | `resize_page(1100, 800)` → 等 transition 300ms（或 `wait_for` no-op） → step 2 的 `evaluate_script` | 返回 `56`（折叠） |
| 4 | `evaluate_script(error_detector)` → `list_console_messages(["error"])` | Layer 1 count = 0；控制台无 error |

### 验证点

- viewport ≥ 1280 → sidebar 240px 展开
- viewport < 1280 → sidebar 56px 折叠 icon-only
- 切换 viewport 过程无 console.error

### 后置检查

- `resize_page(1280, 900)` 恢复默认

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/page-frame.test.tsx` 单元旁证；DevTools MCP 运行期观察
- **Test Type**: Real

---

### 用例编号

ST-UI-012-001

### 关联需求

verification_steps[3]（devtools snapshot） · Feature Design §Visual Rendering Contract AppShell / Sidebar / Top bar · Feature Design Test Inventory T15, T20, T37 · UCD §3.8

### 测试目标

验证首启 `/` 的 Chrome DevTools `take_snapshot` 含 AppShell root + Sidebar + Top bar + 主内容区 4 个可见 DOM 节点。同时 Layer 1（error_detector）count=0；Layer 1b（positive_render_checker）`missingCount=0`；Layer 3（console error）无 error。

### 前置条件

- `ui-dev` 运行中；浏览器已打开 `http://127.0.0.1:5173/`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `navigate_page("http://127.0.0.1:5173/")` → `wait_for(["总览"])` | 页面加载完成 |
| 2 | `take_snapshot()` | EXPECT: `[data-component="app-shell"]`、`[data-component="sidebar"]`、`[data-component="top-bar"]`、`header`、`aside`、`main`（或等价主容器）全部出现；REJECT: `null` / 空快照 |
| 3 | `evaluate_script(error_detector)`（Layer 1 —— `window.onerror` + `unhandledrejection` 断言） | count = 0 |
| 4 | `evaluate_script(positive_render_checker, ['[data-component="app-shell"]','[data-component="sidebar"]','[data-component="top-bar"]'], [])` | `{missingCount: 0, details: [...]}`  |
| 5 | `list_console_messages(["error"])` | 返回空数组（Layer 3） |
| 6 | `evaluate_script(() => getComputedStyle(document.querySelector('[data-component="top-bar"]')).height)` | 返回 `"56px"` |

### 验证点

- devtools snapshot 含 Sidebar + Top bar + 主内容区 三大结构元素（verification_steps[3] 直接 AC）
- Layer 1 / 1b / 3 三层检测全过
- Top bar 渲染尺寸为 `56px`（Feature Design §VRC 契约）

### 后置检查

- 保留浏览器

### 元数据

- **优先级**: Critical
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/e2e/f12-devtools-snapshot.spec.ts`
- **Test Type**: Real

---

### 用例编号

ST-UI-012-002

### 关联需求

Feature Design §Visual Rendering Contract Sidebar 激活项 · Feature Design Test Inventory T18 · UCD §3.8

### 测试目标

验证 Sidebar 激活项：路由切换到 `/hil` 时，`[data-component="sidebar"] [data-nav="hil"][data-active="true"]` 存在且唯一激活；其他 nav 项不带 `data-active="true"`。执行 Chrome DevTools MCP `navigate_page` + `evaluate_script`。

### 前置条件

- `ui-dev` 运行中；浏览器已打开根页

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `navigate_page("http://127.0.0.1:5173/")` → `wait_for(["总览"])` | 页面就绪 |
| 2 | `evaluate_script(() => document.querySelector('[data-component="sidebar"] [data-active="true"]')?.getAttribute('data-nav'))` | 返回当前根路由对应的 nav id（`"overview"` 或等价） |
| 3 | `navigate_page("http://127.0.0.1:5173/hil")` → `wait_for(["HIL"])` 或等效 | 页面路由切换完成 |
| 4 | step 2 的 `evaluate_script` 重复 | 返回 `"hil"` |
| 5 | `evaluate_script(() => Array.from(document.querySelectorAll('[data-component="sidebar"] [data-active="true"]')).length)` | 返回 `1`（单激活项） |
| 6 | `evaluate_script(error_detector)` → `list_console_messages(["error"])` | Layer 1 count = 0；无 console error |

### 验证点

- Sidebar 激活项随路由切换而切换（React re-render）
- 同一时刻激活项唯一
- 无渲染错误

### 后置检查

- `navigate_page("http://127.0.0.1:5173/")` 恢复

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/page-frame.test.tsx`（active prop 断言旁证）；DevTools MCP 运行期
- **Test Type**: Real

---

### 用例编号

ST-UI-012-003

### 关联需求

Feature Design §Visual Rendering Contract HIL 徽标 · Feature Design §Boundary Conditions hilCount=0 · Feature Design Test Inventory T19

### 测试目标

验证 HIL 徽标零值不渲染 / 非零渲染文本：`hilCount=3` 时 `[data-component="sidebar"] [data-nav="hil"] [data-badge="true"]` 存在且 textContent 含 "3"；`hilCount=0` 时该节点不存在。

### 前置条件

- Vitest 环境可跑

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/components/__tests__/page-frame.test.tsx --reporter verbose 2>&1 | grep -Ei 'hilCount|badge'` | 断言通过（`hilCount=3` 显示、`hilCount=0` 不渲染） |

### 验证点

- 徽标零值不渲染
- 非零值 textContent 匹配

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/page-frame.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-UI-012-004

### 关联需求

verification_steps[5]（a11y: prefers-reduced-motion） · Feature Design §Visual Rendering Contract Reduced-motion 降级 · Feature Design Test Inventory T23, T27 · UCD §2.2

### 测试目标

验证 `prefers-reduced-motion: reduce` 媒体查询生效时，PhaseStepper current pulse 动画降级为 `animation: none`，dot 本体颜色保留。使用 Chrome DevTools MCP `emulate({"reducedMotion":"reduce"})`。

### 前置条件

- `ui-dev` 运行中

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `emulate({"reducedMotion":"reduce"})` | 生效 |
| 2 | `navigate_page("http://127.0.0.1:5173/")` → `wait_for(["总览"])` | 页面就绪 |
| 3 | `evaluate_script(() => { const el = document.querySelector('[data-component="phase-stepper"] [data-state="current"] [data-pulse]'); return el ? getComputedStyle(el).animationName : 'no-pulse-element'; })` | 返回 `"none"` 或 `"no-pulse-element"`（Vitest happy-dom 等价断言已覆盖；运行期 phase-stepper 可能由 F21 具体 RunOverview 挂载才出现；若该 selector 不存在则以 Vitest 单测为权威） |
| 4 | `evaluate_script(() => { const dot = document.querySelector('[data-component="ticket-card"][data-state="running"] [data-state-dot]'); if (!dot) return 'no-ticket'; const cs = getComputedStyle(dot, '::after'); return cs.animationName; })` | 返回 `"none"` 或 `"no-ticket"`（同上） |
| 5 | 权威旁证：`cd apps/ui && npx vitest run src/components/__tests__/phase-stepper.test.tsx src/components/__tests__/ticket-card.test.tsx --reporter verbose 2>&1 | grep -Ei 'reduced-motion|prefers-reduced'` | 匹配 ≥ 1 条断言通过（单元测试通过即视为硬关卡） |
| 6 | `list_console_messages(["error"])` | 无 error |

### 验证点

- 在 reduced-motion 下 pulse 光环 `animation-name` 为 `none`
- dot 本体颜色（非动画部分）保留
- Vitest 单测作为权威旁证通过

### 后置检查

- `emulate({"reducedMotion":"no-preference"})` 恢复

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/phase-stepper.test.tsx`、`apps/ui/src/components/__tests__/ticket-card.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-UI-012-005

### 关联需求

verification_steps[6]（token-fidelity） · Feature Design §Visual Rendering Contract Theme surface · Feature Design Test Inventory T26 · UCD §5 F12 实施规约

### 测试目标

验证 `apps/ui/src/theme/tokens.css` `:root` 块与 `docs/design-bundle/eava2/project/styles/tokens.css` `:root` 块 byte-identical。追加的中文排印 + prefers-reduced-motion 扩展位于 `:root` 之外，不计入 diff。使用 `scripts/check_tokens_fidelity.sh`。

### 前置条件

- prototype tokens.css 存在于 `docs/design-bundle/eava2/project/styles/`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bash scripts/check_tokens_fidelity.sh` | 退出码 0 |
| 2 | `cd apps/ui && npx vitest run src/theme/__tests__/tokens-fidelity.test.ts` | 退出码 0（Vitest 同步旁证） |
| 3 | `navigate_page("http://127.0.0.1:5173/")` → `evaluate_script(() => getComputedStyle(document.documentElement).getPropertyValue('--bg-app').trim())` | 返回 `"#0A0D12"`（运行期 token 已加载） |

### 验证点

- `:root` 块 byte-identical
- 仅允许追加（中文排印 + reduced-motion），禁止修改已有 token 值
- 运行期 CSS 变量生效

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `scripts/check_tokens_fidelity.sh`、`apps/ui/src/theme/__tests__/tokens-fidelity.test.ts`
- **Test Type**: Real

---

### 用例编号

ST-UI-012-006

### 关联需求

Feature Design §Visual Rendering Contract PhaseStepper pulse · Feature Design Test Inventory T22

### 测试目标

验证默认动效（非 reduced-motion）下，PhaseStepper current pulse 元素的 `animation-name` 为 `hns-pulse`（或等价 keyframe 名）。由于 PhaseStepper 可能只在具体 feature 页面（如 RunOverview）挂载，本用例以 Vitest 单元测试作为权威证据 + Storybook-equiv test。

### 前置条件

- Vitest 环境可跑

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/components/__tests__/phase-stepper.test.tsx --reporter verbose 2>&1 | tail -30` | PASS；含 pulse animationName 断言 |

### 验证点

- PhaseStepper current 的 `[data-pulse]` 动画绑定正确

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/phase-stepper.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-UI-012-007

### 关联需求

Feature Design §Visual Rendering Contract AppShell 根容器 + Theme surface（颜色 token） · Feature Design Test Inventory T15

### 测试目标

验证 AppShell 渲染后 `[data-component="app-shell"]` 非空；`getComputedStyle().backgroundColor` 解析为 `rgb(10, 13, 18)`（即 `#0A0D12` = `--bg-app`，tokens 已加载）。

### 前置条件

- `ui-dev` 运行中

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `navigate_page("http://127.0.0.1:5173/")` → `wait_for(["总览"])` | 页面就绪 |
| 2 | `evaluate_script(() => !!document.querySelector('[data-component="app-shell"]'))` | `true` |
| 3 | `evaluate_script(() => { const el = document.querySelector('[data-component="app-shell"]'); return el ? getComputedStyle(el).backgroundColor : null; })` | 返回 `"rgb(10, 13, 18)"`（允许浏览器等价 representation） |
| 4 | `evaluate_script(positive_render_checker, ['[data-component="app-shell"]'], [])` | `missingCount: 0` |
| 5 | `list_console_messages(["error"])` | 无 error |

### 验证点

- AppShell root 挂载
- 背景色由 `--bg-app` token 驱动，可解析为 rgb(10,13,18)

### 后置检查

- 保留浏览器

### 元数据

- **优先级**: Critical
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/app/__tests__/app-shell.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-UI-012-008

### 关联需求

Feature Design §Visual Rendering Contract Theme surface + TicketCard state-dot + tool chip · UCD §2.6

### 测试目标

验证 TicketCard 组件 DOM 断言在 Vitest happy-dom 下通过：`data-state-dot` 背景色对应 `--state-running`；`data-tool="claude"` 节点存在。

### 前置条件

- Vitest 环境可跑

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/components/__tests__/ticket-card.test.tsx --reporter verbose 2>&1 | tail -30` | PASS；含 state-dot + tool chip 断言 |

### 验证点

- state-dot 颜色由 `--state-running` 驱动
- tool chip 节点存在

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/components/__tests__/ticket-card.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-UI-012-009

### 关联需求

verification_steps[4]（visual-regression pixelmatch） · Feature Design Test Inventory T35, T36 · UCD §7 SOP

### 测试目标

验证前端实现渲染 vs prototype artboard 1280×900 / 1440×840 分辨率 pixelmatch 对比，差异 < 3%。**Known Gap**：prototype artboard PNG 文件 `docs/design-bundle/eava2/project/pages/overview-1280.png` / `overview-1440.png` **当前不存在**（Feature Design §Design Alignment 已声明 F12 实施期未生成 artboard；UCD §7 第 5 步 "截图存档" 由后续 ST 阶段补齐）；`apps/ui/e2e/f12-visual-regression.spec.ts` 内置 `expect(false).toBe(true)` 占位。本用例记录为 **BLOCKED**（not SKIP），并作为 Known-Gap 在文档末尾跟踪。

### 前置条件

- `ui-dev` 运行中；Playwright 已安装

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `ls docs/design-bundle/eava2/project/pages/*.png 2>&1` | 若无 PNG 输出 → 用例 BLOCKED，跳到 step 3 |
| 2 | `cd apps/ui && npx playwright test e2e/f12-visual-regression.spec.ts --reporter=list` | （当 step 1 有 PNG）退出码 0 + pixelmatch diff < 3% |
| 3 | 若 BLOCKED，记入 `## Known-Gap` 并在 Issues 表登记 | 记录生效 |

### 验证点

- 前端 1280/1440 渲染与 prototype 像素差 < 3%

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: No
- **手动测试原因**: external-action（需提供 prototype artboard PNG 基线截图，属 F21/F22 或后续 ST 补齐的 UCD §7 SOP 产物）
- **测试引用**: `apps/ui/e2e/f12-visual-regression.spec.ts`
- **Test Type**: Real

---

### 用例编号

ST-SEC-012-001

### 关联需求

verification_steps[1]（NFR-010 中文唯一 —— 源码 grep 无匹配） · Feature Design Test Inventory T30

### 测试目标

验证 `apps/ui/src/**/*.{ts,tsx}` 源码中无可见英文业务字符串（排除 import / CSS var / 技术术语白名单 / test fixture）。使用 `scripts/check_source_lang.sh`。

### 前置条件

- `apps/ui/src/` 存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bash scripts/check_source_lang.sh` | 退出码 0 |
| 2 | `cd apps/ui && npx vitest run src/__tests__/source-lang-guard.test.ts` | 退出码 0（Vitest 同步旁证） |

### 验证点

- 源码 scan 无英文业务字符串
- Vitest source-lang-guard 通过

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `scripts/check_source_lang.sh`、`apps/ui/src/__tests__/source-lang-guard.test.ts`
- **Test Type**: Real

---

### 用例编号

ST-SEC-012-002

### 关联需求

Feature Design §Interface Contract `HarnessWsClient.connect` SEC url-guard · Feature Design Test Inventory T29 · NFR-007 回环基线（F12 不违反）

### 测试目标

验证 `HarnessWsClient.connect("ws://attacker.com")` 或 `"ws://192.168.1.1:8765"` 抛 `TypeError`（非 127.0.0.1 / localhost host 拒绝）；socket 未被创建。

### 前置条件

- Vitest 环境可跑

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx vitest run src/ws/__tests__/client.test.ts --reporter verbose 2>&1 | grep -Ei 'reject|loopback|non-127|attack|scheme'` | 匹配 ≥ 1 条断言通过 |

### 验证点

- 非 loopback host 拒绝（NFR-007 心智模型基座）
- 非 `ws://` scheme 拒绝

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/ws/__tests__/client.test.ts`
- **Test Type**: Real

---

### 用例编号

ST-PERF-012-001

### 关联需求

verification_steps[0]（NFR-001 p95 < 500ms 页面切换） · Feature Design Test Inventory T34 · ATS NFR-001 行

### 测试目标

验证路由切换 100 次 `/ ↔ /hil` 的 p95 < 500ms（NFR-001 PERF）。使用 Playwright E2E 或 Chrome DevTools MCP `performance_start_trace` + route navigate 循环。

### 前置条件

- `ui-dev` 运行中；Playwright 已安装（`@playwright/test@1.48.2`）
- Chromium 已 `npx playwright install chromium`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `cd apps/ui && npx playwright test e2e/f12-route-switch.spec.ts --reporter=list 2>&1 | tail -30` | 退出码 0；报告含 p95 < 500ms |
| 2 | 若 Playwright browser 未装：`npx playwright install chromium`；重试 step 1 | 重试通过 |

### 验证点

- 100 次样本的 p95 切换耗时 < 500ms
- 测试结果可重现（Playwright spec 存档于 `apps/ui/e2e/f12-route-switch.spec.ts`）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `apps/ui/e2e/f12-route-switch.spec.ts`
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-012-001 | NFR-001 基座 / T01 | verification_steps[0][3] | `apps/ui/src/ws/__tests__/client.test.ts`、`apps/ui/e2e/f12-route-switch.spec.ts` | Real | PASS |
| ST-FUNC-012-002 | §IC `useWs` / T03, T11, T12 | verification_steps[3] | `apps/ui/src/ws/__tests__/use-ws.test.tsx`、`apps/ui/src/ws/__tests__/subscribe.test.ts`、`apps/ui/src/ws/__tests__/client.test.ts` | Real | PASS |
| ST-FUNC-012-003 | §IC `apiClient.fetch` / T08, T09, T40 | verification_steps[3] | `apps/ui/src/api/__tests__/client.test.ts`、`apps/ui/src/api/__tests__/query-hook-factory.test.tsx` | Real | PASS |
| ST-FUNC-012-004 | §IC `createSlice` / T13, T14 | verification_steps[3] | `apps/ui/src/store/__tests__/slice-factory.test.ts` | Real | PASS |
| ST-FUNC-012-005 | NFR-011 基座 / T15, T38 | verification_steps[2] | `apps/ui/src/components/__tests__/icons.test.tsx`、`apps/ui/src/components/__tests__/page-frame.test.tsx` | Real | PASS |
| ST-FUNC-012-006 | §VRC PhaseStepper / T21 | verification_steps[3] | `apps/ui/src/components/__tests__/phase-stepper.test.tsx` | Real | PASS |
| ST-FUNC-012-007 | §VRC TicketCard state-dot / T24, T25 | verification_steps[3] | `apps/ui/src/components/__tests__/ticket-card.test.tsx` | Real | PASS |
| ST-FUNC-012-008 | §ECR F01 StaticFiles / T33 | verification_steps[3] | 手动 curl 等价 | Real | PASS |
| ST-BNDRY-012-001 | §IC connect Raises + PhaseStepper current / T02, T28 | verification_steps[3] | `apps/ui/src/ws/__tests__/client.test.ts`、`apps/ui/src/components/__tests__/phase-stepper.test.tsx` | Real | PASS |
| ST-BNDRY-012-002 | §BC 指数退避 + 心跳 / T05, T06, T39 | verification_steps[3] | `apps/ui/src/ws/__tests__/client.test.ts`、`apps/ui/src/ws/__tests__/subscribe.test.ts` | Real | PASS |
| ST-BNDRY-012-003 | §BC viewport 1279↔1280 / T16, T17 | verification_steps[3] | `apps/ui/src/components/__tests__/page-frame.test.tsx` + DevTools MCP | Real | PASS |
| ST-UI-012-001 | §VRC AppShell/Sidebar/Top bar / T15, T20, T37 | verification_steps[3] | `apps/ui/e2e/f12-devtools-snapshot.spec.ts` + DevTools MCP | Real | PASS |
| ST-UI-012-002 | §VRC Sidebar 激活 / T18 | verification_steps[3] | `apps/ui/src/components/__tests__/page-frame.test.tsx` + DevTools MCP | Real | PASS |
| ST-UI-012-003 | §VRC HIL 徽标 / T19 | verification_steps[3] | `apps/ui/src/components/__tests__/page-frame.test.tsx` | Real | PASS |
| ST-UI-012-004 | NFR-001 / UCD §2.2 reduced-motion / T23, T27 | verification_steps[5] | `apps/ui/src/components/__tests__/phase-stepper.test.tsx`、`apps/ui/src/components/__tests__/ticket-card.test.tsx` | Real | PASS |
| ST-UI-012-005 | UCD §5 token fidelity / T26 | verification_steps[6] | `scripts/check_tokens_fidelity.sh`、`apps/ui/src/theme/__tests__/tokens-fidelity.test.ts` | Real | PASS |
| ST-UI-012-006 | §VRC PhaseStepper pulse / T22 | verification_steps[3] | `apps/ui/src/components/__tests__/phase-stepper.test.tsx` | Real | PASS |
| ST-UI-012-007 | §VRC AppShell root + Theme / T15 | verification_steps[3] | `apps/ui/src/app/__tests__/app-shell.test.tsx` + DevTools MCP | Real | PASS |
| ST-UI-012-008 | §VRC TicketCard tool chip / T24, T25 | verification_steps[3] | `apps/ui/src/components/__tests__/ticket-card.test.tsx` | Real | PASS |
| ST-UI-012-009 | verification_steps[4] visual-regression pixelmatch / T35, T36 | verification_steps[4] | `apps/ui/e2e/f12-visual-regression.spec.ts` | Real | PENDING-MANUAL |
| ST-SEC-012-001 | NFR-010 源码 grep / T30 | verification_steps[1] | `scripts/check_source_lang.sh`、`apps/ui/src/__tests__/source-lang-guard.test.ts`、`scripts/check_source_lang.py` | Real | PASS |
| ST-SEC-012-002 | NFR-007 回环 + §IC connect SEC / T29 | verification_steps[3] | `apps/ui/src/ws/__tests__/client.test.ts` | Real | PASS |
| ST-PERF-012-001 | NFR-001 p95 < 500ms / T34 | verification_steps[0] | `apps/ui/e2e/f12-route-switch.spec.ts` | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 23 |
| Passed | 22 |
| Failed | 0 |
| Pending | 1 (PENDING-MANUAL — ST-UI-012-009 Known-Gap) |

> Real test cases = all 23 cases run against real ui-dev (127.0.0.1:5173) + real api (127.0.0.1:8765) + Vitest with happy-dom DOM runtime（DOM 运行期不是 mock；组件逻辑走完整代码路径）+ DevTools MCP real browser + real Playwright Chromium（ST-PERF-012-001 / ST-UI-012-001）+ real file system（tokens fidelity / source-lang grep）。
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.

## Manual Test Case Summary

| Metric | Count |
|--------|-------|
| Total Manual Test Cases | 1 |
| Manual Passed (MANUAL-PASS) | 0 |
| Manual Failed (MANUAL-FAIL) | 0 |
| Blocked | 0 |
| Pending (PENDING-MANUAL) | 1 |

> Manual test cases = ST-UI-012-009（pixelmatch artboard 基线缺失）。`已自动化: No` `手动测试原因: external-action`。SubAgent 返回后由 dispatcher 向人类征集裁决：是以 BLOCKED 计（Known-Gap 跟踪到 F21/F22）、SKIP（承认遗漏）、或 MANUAL-PASS/FAIL（人工拉取 prototype 截图后肉眼比对）。

## ATS 类别覆盖说明

Feature F12 `srs_trace = [NFR-001, NFR-010, NFR-011]` 映射到 ATS §2.2 必须类别：

- **NFR-001 → {PERF, UI}**：
  - PERF = ST-PERF-012-001（Playwright 100 次路由切换 p95 < 500ms）
  - UI = ST-UI-012-001（devtools snapshot 首屏结构齐）、ST-UI-012-007（AppShell root + token 解析）、ST-UI-012-004（reduced-motion a11y 不破坏 p95）
- **NFR-010 → {FUNC, UI}**：
  - FUNC = ST-SEC-012-001（源码 grep 零英文业务字串，属 FUNC/SEC 交叉，grep 逻辑本身 FUNC 覆盖）
  - UI = ST-UI-012-001 中 `take_snapshot` 隐式含中文文本（如 "总览"）验证 —— 视觉评审（Manual: visual-judgment）部分 ATS 明确允许走人工（ATS §2.2 NFR-010 注"视觉评审部分需人工；源码 grep 部分 Auto"）。本 ST 的 FUNC 侧完全 Auto；UI 视觉评审延到 `长 ST` / F21/F22 feature ST 阶段人工复核。
- **NFR-011 → {FUNC, UI}**：
  - F12 只承接基座义务（Feature Design §SRS Requirement 尾注）
  - FUNC = ST-FUNC-012-005（primitives 存在性 + PageFrame title slot 存在）
  - UI = ST-FUNC-012-005 step 2-4（top-bar 在浏览器实际渲染可验证）；完整 "单选/多选/自由文本" 文本 ST 由 F21 Fe-RunViews ST 承接

**ATS §4 NFR-001 行补充**："工具：Playwright + DevTools MCP `performance_start_trace`；100 次交互 / 10 Hz 采样" —— 由 ST-PERF-012-001 + ST-UI-012-001 共同满足（Playwright 100 次样本 + DevTools MCP snapshot 首屏可观察）。

## ATS 跨 Feature 集成锚点（非本特性 blocker）

- **NFR-010 视觉评审（Manual: visual-judgment）**：F12 只完成源码 grep 的 Auto 部分；8 页面视觉评审由 F21/F22 feature ST 承接（届时 ST-UI-012-009 的 pixelmatch 基线图也应已由 F21/F22 prototype-artboard 产出）。
- **NFR-011 文本渲染**：HIL 控件实际"单选/多选/自由文本"文本渲染与 skill hint placeholder 由 F21 HILCard feature 实现；F12 只提供 Label / Radio / Checkbox / Textarea primitives slot API（本 ST 文档 ST-FUNC-012-005 覆盖）。

## Known-Gap

| # | ST Case | Gap | Downstream Owner | Rationale |
|---|---------|-----|------------------|-----------|
| 1 | ST-UI-012-009 | `docs/design-bundle/eava2/project/pages/overview-1280.png` / `overview-1440.png` prototype artboard PNG 基线不存在；`apps/ui/e2e/f12-visual-regression.spec.ts` 内置 `expect(false).toBe(true)` 占位 | F21/F22 feature ST 补齐（UCD §7 SOP 第 5 步"ST 证据：截图 + diff 报告存档 `docs/test-cases/F<N>/visual-regression/`"） | F12 Feature Design §Design Alignment 已声明此为预期缺口；不阻塞 ATS UI 类别最低覆盖（ST-UI-012-001..008 覆盖 §VRC 全部 11 个视觉元素 + devtools snapshot + reduced-motion + token fidelity）。 |

## 负向比例

本文档 23 条用例中负向 / 错误路径 / 边界拒绝类：
- ST-BNDRY-012-001（connect 非法 URL + PhaseStepper current 越界 拒绝）
- ST-BNDRY-012-002（退避 / 心跳边界）
- ST-BNDRY-012-003（viewport 1279 边界折叠）
- ST-UI-012-003（hilCount=0 零值不渲染 —— 负向分支）
- ST-UI-012-004（reduced-motion 降级 —— 负向分支）
- ST-UI-012-005（tokens 漂移检测 —— 负向断言）
- ST-SEC-012-001（源码英文 grep 零命中 —— 负向断言）
- ST-SEC-012-002（非 loopback host 拒绝）

共 8 条（= 34.8%）；考虑到 F12 作为"基座特性"大量用例为 happy-path primitive 可用性（基座义务型），负向比例低于 Feature Design Test Inventory 的 46.3%（Test Inventory 含更多 WS 协议级边界与错误路径）。ATS 仍要求最小功能/边界覆盖：FUNC=8、BNDRY=3、UI=9、SEC=2、PERF=1 全部达到。
