# Harness — UCD Style Guide

**Date**: 2026-04-21 · **Revised**: 2026-04-24
**Status**: Approved（**v2 · 视觉源改为 design-bundle 原型**）
**SRS Reference**: docs/plans/2026-04-21-harness-srs.md
**Chosen Style**: Cockpit Dark · v2 精调
**Scale**: 8 个页面 + 1 个封面 artboard

---

## 1. 单一源声明（SOT）

**本文档不再承载视觉规格**。Harness UI 的视觉真相源是 `docs/design-bundle/eava2/`（由 Claude Design 导出的可运行原型），本文档仅承载 prototype 无法声明的内容(a11y / 中文排印 / 动效 / 响应式 / 状态语义)与指向 prototype 的指针。

**真相分工**：

| 关注点 | 真相源 | 形态 |
|---|---|---|
| 色板 token / 尺寸 token / radii / shadow | `design-bundle/eava2/project/styles/tokens.css` | CSS 变量(可执行) |
| 字体级阶 / 间距尺度 | 同上 | CSS 变量 |
| 页面布局 / 组件结构 / props / 交互细节 | `design-bundle/eava2/project/pages/*.jsx`、`components/*.jsx` | React 源码(可执行) |
| 图标集与用法 | prototype 内联 SVG(`components/Icons.jsx`) | React 源码 |
| 封面 / phase 色带 / 品牌元素 | `design-bundle/eava2/project/app.jsx`(`Cover`) | React 源码 |
| **WCAG AA 基线 / 键盘导航 / 动效约束 / 中文排印 / 响应式断点** | **本文档 §2** | markdown 规则 |
| **状态色语义映射**(锚定 SRS FR-006 状态机) | **本文档 §2.6** | markdown 规则 |
| **变更流程**(如何改 UI) | **本文档 §3** | markdown 流程 |
| 8 页 / 15 组件的索引指针 | **本文档 §4 / §5** | markdown 指针表 |

**实施者必读**：阅读 prototype **源码**(不看截图、不看本文档复述),逐文件打开 `design-bundle/eava2/project/`。本文档 §2-§5 只是"规则约束 + 找东西的地图",不是"视觉规格"。

---

## 2. 规则性约束(prototype 无法声明,此处为权威源)

### 2.1 Accessibility · WCAG AA 基线

- **对比度**：所有前景/背景组合须 ≥ 4.5:1(正文)或 ≥ 3:1(≥18px 大文本、UI 图形)。prototype 的 `tokens.css` 色板已按此设计;任何新增色必须回到 WebAIM Contrast Checker 验证再合入。
- **控件尺寸**：所有可点击控件 hit area ≥ 32×32px(含内部 padding)。icon-only button 最小 32×32(prototype `.btn.icon` 已合规)。
- **Focus ring**：所有可聚焦元素必须有可见 focus ring —— 2px outline · `--accent` · offset 2px · 不依赖平台默认样式。prototype `.input:focus` 的 `--ring` 已是此规格;自定义交互元素须沿用。
- **颜色不是唯一信号**：状态信息必须同时用 icon + 文字 + 色彩至少两种表达。红色错误必带 `alert-triangle` 图标 + 文字;绿色 running 必带 pulse 动画 + 文字。
- **键盘导航**：Tab 顺序 = 视觉阅读顺序;Esc 关 modal / drawer / popover;Enter 触发 primary action;Space 切换 toggle;方向键在 radio group / menu / list 内导航。
- **Screen reader**:
  - icon-only button 必须有 `aria-label`
  - chip / badge 若文字不可见须 `aria-label`
  - live region 用 `aria-live="polite"`(HIL 通知、toast)或 `"assertive"`(错误中断)
  - stream-json tree 须 `role="tree"` + `aria-level` / `aria-expanded`

### 2.2 Animation & Motion

- **时长预算**：状态转场 120-200ms;**禁止** > 300ms 的 UI 过渡。
- **缓动**：统一 `cubic-bezier(0.4, 0, 0.2, 1)`(prototype 已用)。
- **pulse 动画**：`running` / `hil_waiting` / `retrying` 三态带 pulse 光环,周期 1.6s(prototype `@keyframes hns-pulse`);不得加快至 < 1.5s(前庭刺激)或减慢至 > 3s(失去"活着"的语义)。
- **prefers-reduced-motion**:所有 pulse / slide / fade 动画必须在该媒体查询下降级为 `transition: none` + 静态视觉替代(state-dot 保留颜色,去掉光环)。实施 F12 时必须落 `@media (prefers-reduced-motion: reduce)` 分支。
- **禁用区**:视差滚动、自动旋转 carousel、自动 alert 弹窗(HIL 例外,因为 HIL 是业务语义)。

### 2.3 Responsive

- **目标环境**:PyWebView 桌面窗口,**最小尺寸 1024×720**(SRS NFR-008);< 1024 不适配。
- **1024-1279px**:侧栏自动折叠到 icon-only(prototype `Sidebar` 的 collapsed 态)。
- **≥ 1280px**:侧栏展开 240px。
- **主内容区 max-width**:1440px,居中留白。超宽显示器不拉伸内容。
- **不提供**:mobile drawer / 触控手势 / 旋转适配。

### 2.4 Dark Mode Only

- v1 仅深色主题,**无 light / high-contrast 变体**(EXC 已在 SRS 记录)。
- 实施者不得预留 `data-theme="light"` 分支 —— 避免死代码。
- 未来若开 light 主题,按 `long-task-increment` 流程走,不属 v1 范围。

### 2.5 中文排印

- 中英混排空隙:用 CSS `text-spacing-trim: space-all`(Chromium ≥ 118 支持;PyWebView 基于 Chromium,可用);不足处人工插 `&thinsp;`。
- 中文正文 `line-height`:1.6(覆盖 prototype 的 1.5 西文默认);标题 1.35。实施时 `.hns-cn-body` / `.hns-cn-heading` 两个 utility class 落到 tokens.css 扩展(本条为对 prototype 的**增补**,非覆盖)。
- 标点:半角括号 `(` `)` + 半角逗号句号。**不用** full-width `（` `，` `。`(与 Inter 气质冲突)。
- 字体回退链:`Inter, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`(prototype `tokens.css` `--font-sans` 已定义,勿改)。
- 等宽中文场景用 JetBrains Mono + `"Sarasa Mono SC"` 回退(若需 CJK 等宽对齐 stream-json 缩进)。

### 2.6 状态色语义映射(硬约束 · 锚定 SRS FR-006)

本表不可覆写,也不允许主题切换改变:

| Ticket State | tokens.css 变量 | 视觉表现 |
|---|---|---|
| `pending` | `--state-pending` | 灰 dot,无动画 |
| `running` | `--state-running` | 绿 dot + pulse |
| `classifying` | `--state-classify` | 紫 dot |
| `hil_waiting` | `--state-hil` | 琥珀 dot + pulse + sidebar 徽标 |
| `completed` | `--state-done` | 暗绿 check icon |
| `failed` | `--state-fail` | 红 dot + toast + alert icon |
| `aborted` | `--state-fail` | 红 X icon |
| `retrying` | `--state-retry` | 橙 dot + countdown text |

若 prototype 与此表冲突,以本表为准(实施时修 prototype);若本表与 SRS FR-006 冲突,以 SRS 为准(走 increment 流程同步此表)。

### 2.7 Icon 规则

- **统一图标源**:Lucide 视觉家族(线稿 · stroke 1.5-1.75px · rounded caps)。prototype 的 `components/Icons.jsx` 是内联 SVG 复刻,**实施 F12 时允许替换为 `lucide-react` npm 包**(视觉等价)。
- **尺寸**:14px(inline in text)· 16px(default)· 20px(page-level)· 24px+(empty state)。
- 禁止混入其它 icon set(Feather / Heroicons / FontAwesome)。

### 2.8 Data Density

- 列表 / 表格默认 **compact** 模式,行高 40px(prototype 已是此规格)。
- 用户偏好 `UI · Data Density = comfortable` 时行高 52px;仅影响列表/表格,不影响卡片/表单。
- 实施点:F15 SystemSettings `UiTab` 暴露此开关,F12 foundation 负责全局 CSS 变量 `--row-height` 的切换。

---

## 3. 变更流程(强约束)

**Harness UI 视觉改动的唯一合法路径**:

1. **改 prototype**:在 `docs/design-bundle/eava2/project/` 内修改 `.jsx` / `.css` / `tokens.css`,在浏览器里跑 `Harness UCD.html` 确认视觉。
2. **跑 `long-task-increment-ucd` skill**:产出 increment-request.json 或直接在 UCD.md §4 / §5 更新指针(新增页面 / 新增组件时)。
3. **同步 design.md §4.12-§4.16**(如页面/组件 API 变了,更新 Integration Surface 表)。
4. **同步 feature-list.json**(如验收准则变了,更新 `verification_steps`)。

**禁止**:

- 直接改本 UCD.md 的色号、尺寸、布局描述(本文档不承载此内容)
- 只改 tokens.css 不走 increment 流程(会导致 feature-list / design 失同步)
- 在 design.md 里复述 prototype 的视觉细节(见 §6 引用禁令)

---

## 4. 页面指针(8 + 1)

下列 anchor(§4.1-§4.8)保留以兼容 feature-list.json / design.md 对 UCD 页面锚点的引用。每页的视觉/交互真相在 `design-bundle/eava2/project/pages/<File>.jsx`。

| Anchor | Page | Prototype 文件 | 路由 | 归属 Feature | SRS 覆盖 |
|---|---|---|---|---|---|
| §4.1 | RunOverview(总览) | `pages/RunOverview.jsx` | `/` | F13 | FR-010 / FR-030 |
| §4.2 | HILInbox(HIL 待答) | `pages/HILInbox.jsx` | `/hil` | F13 | FR-010 / FR-031 |
| §4.3 | SystemSettings(设置) | `pages/SystemSettings.jsx` | `/settings` | F15 | FR-032 / IFR-004 / IFR-006 |
| §4.4 | PromptsAndSkills(Skills) | `pages/PromptsAndSkills.jsx` | `/skills` | F15 | FR-033 |
| §4.5 | TicketStream(Ticket 流) | `pages/TicketStream.jsx` | `/ticket-stream` | F14 | FR-034 / NFR-002 |
| §4.6 | DocsAndROI(文档) | `pages/DocsAndROI.jsx` | `/docs` | F16 | FR-035 |
| §4.7 | ProcessFiles(过程文件) | `pages/ProcessFiles.jsx` | `/process-files` | F16 | FR-038 / FR-039 |
| §4.8 | CommitHistory(提交历史) | `pages/CommitHistory.jsx` | `/commits` | F16 | FR-041 / IFR-005 |
| §4.0 | Cover(品牌封面 · 非应用内页面) | `app.jsx` `Cover` 组件 | — | — | — |

**SRS FR 覆盖声明**:prototype `app.jsx` 宣称 "8 页覆盖 FR-001..050 全部交互路径"。实际映射见上表:UI 可见的 FR 由 F13-F16 承接;FR-001 ~ FR-029(后台) / FR-036 / FR-037 / FR-040 / FR-042 ~ FR-050 属非 UI 直接承接(由后端 feature F01-F11 实现、UI 作副作用消费)。

---

## 5. 组件指针(15)

组件按命名来源分两类:**shared primitives**(prototype `components/`)与**页面内局部组件**(页面文件内定义)。

| Anchor | 组件 | Prototype 文件 | 类型 |
|---|---|---|---|
| §3.1 | Button(primary/secondary/ghost/danger/icon + sm) | `tokens.css` `.btn.*` | CSS utility |
| §3.2 | Input | `tokens.css` `.input` | CSS utility |
| §3.3 | Ticket Card | `components/TicketCard.jsx` | React |
| §3.4 | HIL Card + RadioRow | `pages/HILInbox.jsx` `HILCard` / `RadioRow` | React(local) |
| §3.5 | Stream-JSON Event Tree | `pages/TicketStream.jsx` `EventTree`(或同义名) | React(local) |
| §3.6 | Phase Progress Stepper | `components/PhaseStepper.jsx` | React |
| §3.7 | Diff Viewer | `pages/CommitHistory.jsx` `DiffViewer` | React(local) |
| §3.8 | Sidebar Navigation | `components/Sidebar.jsx` | React |
| §3.9 | Modal / Dialog | `pages/SystemSettings.jsx` or `pages/PromptsAndSkills.jsx` 内 | React(local) |
| §3.10 | Toast / Alert | `components/PageFrame.jsx`(toast slot) | React |
| §3.11 | Empty State | 各页面内 `EmptyState` 局部 | React(local) |
| §3.12 | Table | 各页面内(SystemSettings / ProcessFiles) | React(local) |
| §3.13 | Chip / Badge / Tag | `tokens.css` `.chip.*` | CSS utility |
| §3.14 | Settings Form Section | `pages/SystemSettings.jsx` 内 | React(local) |
| §3.15 | Skill Tree Viewer | `pages/PromptsAndSkills.jsx` 内 | React(local) |

**实施规约(F12)**:
- `tokens.css` **原样**进入 `apps/ui/src/theme/tokens.css`(不改 token 值;允许追加 §2.5 的中文排印扩展 class)
- `components/Sidebar.jsx` / `PhaseStepper.jsx` / `TicketCard.jsx` / `PageFrame.jsx` / `Icons.jsx` **移植**到 `apps/ui/src/components/`,CDN React + 内联 style **重构**为 TypeScript + Tailwind + shadcn/ui,但视觉产物必须**像素等价**
- 页面内的 local 组件(HILCard / EventTree / DiffViewer 等)在对应 feature(F13/F14/F16)里移植
- 移植正确性验证:见 §7 视觉回归 SOP

---

## 6. 文档引用禁令

**design.md / 各 feature 详设 / ATS / ST 文档禁止复述 prototype 内的视觉细节**,包括:

- 色号(hex / oklch 值)
- 具体尺寸(padding / margin / width / height 数值)
- 组件内部 DOM 结构与层级
- 具体字号 / 字重 / 字距

**允许的引用形式**:
- "见 `design-bundle/eava2/project/pages/RunOverview.jsx` 的 `PhaseStepper` 段"
- "token `--accent` 见 tokens.css"
- "组件行为规约见 UCD §2.6 状态色语义"

**理由**:任何复述都是重复源 → 必漂移 → 设计衰减。这是"单一视觉源"的核心执行力。

---

## 7. 视觉回归 SOP(F12-F16 验收必跑)

实施一个页面 / 组件后,必须执行:

1. **本地跑 prototype**:`python -m http.server` 从 `docs/design-bundle/eava2/project/` 目录起 → 浏览器打开 `Harness UCD.html` → focus 到目标 artboard → 1:1 截图(1280×900 or 1440×840 按 artboard 实际尺寸)。
2. **跑实现**:`pnpm --filter apps/ui dev` → 浏览器打开对应路由 → 同分辨率截图。
3. **像素对比**:用 `pixelmatch` 或等价工具对两张截图求差异率:
   - **阈值**:差异像素占比 < 3%(允许 sub-pixel AA、字体 hinting、日期/时间 mock 数据差异)
   - 超阈 → 记录失败点(布局偏移? token 漂移? icon 错位?)→ 修实现直到过阈
4. **手测 a11y**:Tab 遍历可达性、Esc 关 modal、screen reader 念 aria-label、`prefers-reduced-motion` 禁用动画。
5. **ST 证据**:截图 + diff 报告存 `docs/test-cases/F<N>/visual-regression/`。

本 SOP 由 F12 的 devtools 验收步骤实施(prototype 浏览器加载 + `mcp__chrome-devtools__take_snapshot`)。

---

## 8. 变更历史

| Date | Rev | 变更 | Author |
|---|---|---|---|
| 2026-04-21 | v1 | 初始 UCD — 自洽 markdown 视觉规格(598 行) | long-task-ucd skill |
| 2026-04-24 | v2 | **单一源改为 design-bundle prototype**;本文档瘦身为规则+指针;v1 的 §2 tokens / §3 组件描述 / §4 页面描述已被 `docs/design-bundle/eava2/` 取代 | 用户 + 本次会话 |
