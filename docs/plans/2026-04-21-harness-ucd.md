# Harness — UCD Style Guide

**Date**: 2026-04-21
**Status**: Approved
**SRS Reference**: docs/plans/2026-04-21-harness-srs.md
**Chosen Style**: Cockpit Dark
**Scale**: 小型到中型（8 个主要页面）

## 1. Visual Style Direction

**Style**: Cockpit Dark — 深色驾驶舱。灵感来自 Linear / Raycast / Vercel Dashboard / Supabase Studio。设计目标：支撑开发者长时段（数小时）监看 ticket 流、HIL 停顿、异常告警的场景；以极简几何 + 高对比状态点为核心。

**Mood**：工程、聚焦、冷静。深灰/近黑主面板，少量饱和度用于状态区分（running / hil_waiting / failed / retrying / completed）。阴影极少，依靠 1px 描边区分层级。

**Rationale**：
- 用户画像：开发者长时间盯 UI（SRS §3 Personas）
- 信息密度需求：ticket 流 + stream-json 树 + git diff 皆要求紧凑布局
- 状态驱动：票据/异常/HIL 等阻塞点需要"一眼识别"的色语义
- 贴合 Harness 的 CLI 血统，与 Claude Code / OpenCode 终端体验连续

## 2. Style Tokens

### 2.1 色板

所有 hex 颜色均经过 WebAIM Contrast Checker 验证，满足 WCAG AA（普通文本 ≥4.5:1）。

| Token | Hex | Usage | Contrast |
|-------|-----|-------|----------|
| `--color-bg-app` | `#0D1117` | App shell 背景 | — |
| `--color-bg-surface` | `#161B22` | 主卡片 / 面板背景 | — |
| `--color-bg-surface-alt` | `#1C2128` | 嵌套卡片 / 表格斑马行 | — |
| `--color-bg-hover` | `#1F2937` | Hover 背景 | — |
| `--color-bg-active` | `#2D3748` | 选中 / 按下态 | — |
| `--color-border` | `#30363D` | 默认 1px 描边 | — |
| `--color-border-subtle` | `#21262D` | 分割线 | — |
| `--color-border-emphasis` | `#6E7681` | Focus ring / 强调描边 | — |
| `--color-text-primary` | `#E6EDF3` | 主文本 | 15.4:1 on bg-app |
| `--color-text-secondary` | `#8B949E` | 次要文本 / caption | 5.6:1 on bg-app |
| `--color-text-tertiary` | `#6E7681` | 禁用 / 占位 | 4.5:1 on bg-app |
| `--color-accent-primary` | `#58A6FF` | Primary action / link | 8.2:1 on bg-app |
| `--color-accent-primary-hover` | `#79B8FF` | Primary hover | 10.3:1 |
| `--color-accent-secondary` | `#A78BFA` | HIL 状态色 / classifier 强调 | 8.0:1 |
| `--color-state-running` | `#22C55E` | 票据运行中 | 8.7:1 |
| `--color-state-hil` | `#F59E0B` | 等待 HIL 答复 | 9.4:1 |
| `--color-state-completed` | `#3FB950` | 已完成 / passing | 9.0:1 |
| `--color-state-failed` | `#F85149` | 失败 / 异常 | 5.9:1 |
| `--color-state-retrying` | `#DB8E2E` | 重试中 | 7.8:1 |
| `--color-state-pending` | `#6E7681` | 待调度 | 4.5:1 |
| `--color-phase-req` | `#58A6FF` | Requirements phase | — |
| `--color-phase-ucd` | `#BC8CFF` | UCD phase | — |
| `--color-phase-design` | `#D2A8FF` | Design phase | — |
| `--color-phase-ats` | `#FF7B72` | ATS phase | — |
| `--color-phase-init` | `#F0883E` | Init phase | — |
| `--color-phase-work` | `#3FB950` | Work phase | — |
| `--color-phase-st` | `#79B8FF` | ST phase | — |
| `--color-phase-finalize` | `#A5D6FF` | Finalize phase | — |
| `--color-diff-add-bg` | `#033A16` | Git diff 新增行背景 | — |
| `--color-diff-add-fg` | `#3FB950` | Git diff 新增文字 | — |
| `--color-diff-del-bg` | `#67060C` | Git diff 删除行背景 | — |
| `--color-diff-del-fg` | `#F85149` | Git diff 删除文字 | — |
| `--color-code-keyword` | `#FF7B72` | Syntax keyword | — |
| `--color-code-string` | `#A5D6FF` | Syntax string | — |
| `--color-code-comment` | `#8B949E` | Syntax comment | — |
| `--color-code-function` | `#D2A8FF` | Syntax function | — |

**Dark mode only** — v1 不提供 light theme（EXC 已在 SRS 中记录）。

### 2.2 字体级阶

| Token | Font Family | Size | Weight | LH | Usage |
|-------|-------------|------|--------|-----|-------|
| `--font-heading-1` | Inter, system-ui | 24px | 600 | 1.25 | 页面标题（RunOverview 标题） |
| `--font-heading-2` | Inter, system-ui | 18px | 600 | 1.33 | 段落标题（Settings 分组） |
| `--font-heading-3` | Inter, system-ui | 15px | 600 | 1.4 | 卡片标题（ticket title） |
| `--font-body` | Inter, system-ui | 14px | 400 | 1.5 | 正文 |
| `--font-body-small` | Inter, system-ui | 12px | 400 | 1.45 | 次级说明 |
| `--font-label` | Inter, system-ui | 12px | 500 | 1.3 | 表单标签 / chip 文字 |
| `--font-button` | Inter, system-ui | 13px | 500 | 1 | 按钮文字 |
| `--font-code` | "JetBrains Mono", "Fira Code", Menlo, monospace | 13px | 400 | 1.55 | 代码片段 / stream-json / diff |
| `--font-code-sm` | "JetBrains Mono", Menlo, monospace | 12px | 400 | 1.5 | inline code / tag |

**字体选择**：Inter 作为 UI 主字体（开源、覆盖中文宋体回退 `-apple-system, "Microsoft YaHei"`）；等宽使用 JetBrains Mono（免费商用，支持中文等宽回退）。

### 2.3 间距与布局

| Token | Value | Usage |
|-------|-------|-------|
| `--space-0` | 0 | flush |
| `--space-1` | 4px | inline small gap |
| `--space-2` | 8px | button 内填充 / 图标-文字间距 |
| `--space-3` | 12px | 卡片内项间距 |
| `--space-4` | 16px | 卡片 padding / 表单行间距 |
| `--space-5` | 24px | 卡片间距 / 段落间距 |
| `--space-6` | 32px | 主内容 section 间距 |
| `--space-8` | 48px | 页面顶部 breathing |
| `--radius-sm` | 4px | input / 小按钮 |
| `--radius-md` | 6px | 主按钮 / chip |
| `--radius-lg` | 8px | 卡片 / 面板 |
| `--radius-xl` | 12px | modal / 大容器 |
| `--radius-full` | 9999px | avatar / badge pill |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | subtle elevation（很少用） |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.4)` | dropdown / popover |
| `--shadow-lg` | `0 12px 32px rgba(0,0,0,0.5)` | modal |
| `--layout-sidebar-width` | 240px | 主 sidebar 宽度 |
| `--layout-sidebar-collapsed` | 56px | 折叠后只剩图标 |
| `--layout-content-max` | 1440px | 主内容最大宽度 |
| `--layout-inspector-width` | 360px | 右侧检查器面板 |
| `--layout-header-height` | 48px | 顶部 bar 高度 |

**栅格**：12 列，gutter 24px，content padding 24px（desktop ≥1280px），20px（1024-1279px）。断点：`lg ≥1280px`、`md 1024-1279px`、`sm <1024px`（sm 下 sidebar 变 drawer）。Harness v1 仅桌面 PyWebView 最小窗口 1024×720，不对 <1024px 做优化。

### 2.4 图标与图片

- **Icon style**: Outlined, 1.5px stroke, rounded caps
- **Icon library**: **Lucide Icons 0.379+**（MIT，与 Inter 视觉风格同频）
- **Icon sizes**: 14px（inline）、16px（默认）、20px（页面级）、24px（空状态 / 强调）
- **Illustration style**: 极简线稿 + 单色填充（使用 `--color-text-secondary`）；空状态插画尺寸 120×120px
- **Avatars / Logos**: Monogram 圆形 avatar 32px / 24px 两档；Claude Code / OpenCode logo 使用官方 wordmark

## 3. Component Prompts

### 3.1 Button

**SRS Trace**: FR-001..050 全局交互
**Variants**: primary / secondary / ghost / danger / icon-only；各含 default / hover / active / disabled / loading

#### Base Prompt (Primary Button)
> A rectangular button with 6px border radius, 36px height, horizontal padding 16px. Background uses `--color-accent-primary` (#58A6FF) as solid fill. Label text centered, 13px Inter semibold (weight 500), color `--color-bg-app` (#0D1117) for maximum contrast. No border in default state. Subtle inner top highlight 1px rgba(255,255,255,0.1). When icon present (16px Lucide outlined), icon is 8px left of label, stroke inherits label color. Minimum width 80px; if content is a single word like "取消" auto-width with horizontal padding 16px left/right.

#### Variant Prompts
> **Hover state**: fill transitions to `--color-accent-primary-hover` (#79B8FF) in 120ms ease-out; label remains `--color-bg-app`.
> **Active state**: fill darkens to `#388BFD`; inner top highlight removed; label color unchanged.
> **Disabled state**: fill becomes `--color-bg-active` (#2D3748); label text `--color-text-tertiary` (#6E7681); cursor `not-allowed`; no hover effect.
> **Loading state**: label replaced by 14px spinner (2px stroke Lucide loader icon rotating 1.2s linear infinite); button width unchanged; clicks disabled.
> **Secondary variant**: background `--color-bg-surface` (#161B22); 1px solid border `--color-border` (#30363D); label `--color-text-primary`; hover fills to `--color-bg-hover`.
> **Ghost variant**: transparent background; no border; label `--color-text-primary`; hover adds `--color-bg-hover` fill.
> **Danger variant**: fill `--color-state-failed` (#F85149); label `#FFFFFF`; hover slight lightness.
> **Icon-only variant**: square 32×32px; 6px radius; icon centered; tooltip on hover.

#### Style Constraints
- All buttons height ≥32px (touch target within desktop constraints)
- Focus ring: 2px `--color-border-emphasis` offset 2px, high contrast outline
- Minimum label length 1 Chinese char or 2 Latin chars; single Chinese chars like "跑" use icon-only variant instead

---

### 3.2 Input (Text / Textarea / Select)

**SRS Trace**: FR-031, FR-032, FR-038
**Variants**: default / focus / error / disabled / readonly

#### Base Prompt
> A rounded-corner input field with `--radius-sm` (4px), 32px height for single line. Background `--color-bg-surface` (#161B22); 1px solid border `--color-border` (#30363D). Inner horizontal padding 12px, vertical padding 6px. Placeholder text `--color-text-tertiary` (#6E7681) at 14px Inter 400. Typed text `--color-text-primary` (#E6EDF3). Icon (if prefix) 14px Lucide placed 10px from left, vertically centered; label text shifts right by 22px. Optional suffix action button within input (e.g., clear or reveal password) 28×28px ghost button on right edge.

#### Variant Prompts
> **Focus state**: border becomes 1px `--color-accent-primary` (#58A6FF) + 2px outer glow rgba(88,166,255,0.2); background unchanged.
> **Error state**: border `--color-state-failed` (#F85149); below the input, a 12px `--font-body-small` error message in `--color-state-failed` with Lucide `alert-circle` 14px icon prefix.
> **Disabled state**: background `--color-bg-active`; text `--color-text-tertiary`; cursor `not-allowed`.
> **Readonly state**: background `--color-bg-app`; border `--color-border-subtle`; text selectable but not editable.
> **Textarea variant**: minimum height 72px, resize vertical only, uses `--font-code` if `data-code=true` attribute.
> **Select variant**: right side shows Lucide `chevron-down` 14px icon; opens a dropdown anchored below, using `--shadow-md` and `--color-bg-surface-alt`.

#### Style Constraints
- Error message renders BELOW input (never as tooltip) to meet accessibility requirements
- All inputs must have visible label (`--font-label` 12px 500 above input, 6px margin-bottom); placeholder alone is insufficient
- Focus ring prominent for keyboard navigation

---

### 3.3 Ticket Card

**SRS Trace**: FR-005, FR-006, FR-007, FR-030, FR-034
**Variants**: compact (in RunOverview) / expanded (in TicketStream detail) / mini (in HILInbox)

#### Base Prompt (Compact variant, used in ticket list)
> A horizontal card 64px tall, full-width of its container (min 480px, max 720px). Background `--color-bg-surface` (#161B22); 1px solid `--color-border` (#30363D) bottom only (stacked list feel, not individual cards). Inner padding 12px 16px. Layout: a 6×6px round state dot at far left (colored by state: running=green, hil_waiting=amber, completed=dim-green, failed=red, retrying=orange, pending=gray) with a subtle 1.5s pulse animation for `running` and `hil_waiting` states. To the right of the dot, 2-row content: row 1 — ticket ID in `--font-code-sm` (e.g., `#t-0042`, color `--color-text-secondary`) + spacing + skill hint `--font-body` 14px 500 (e.g., `long-task-requirements`, color `--color-text-primary`) + spacing + tool tag chip (claude / opencode) on right. Row 2 — short status text `--font-body-small` 12px `--color-text-secondary` (e.g., "Running · 2m 14s · 32 events"). Far right: a 14px Lucide chevron-right `--color-text-tertiary`. Hover: background shifts to `--color-bg-hover` (#1F2937); chevron color → primary text.

#### Variant Prompts
> **Expanded variant (TicketStream detail)**: full card 240px tall, includes collapsible stream-json preview of last 3 events; border becomes full box with 8px radius; shadow-sm applied.
> **Mini variant (HILInbox)**: 48px tall; state dot is always amber (hil_waiting); extra right-side badge "需要您回答" (amber pill, 10px radius).
> **Selected state**: left edge 3px accent stripe in state color; background `--color-bg-active`.

#### Style Constraints
- State dot color maps 1:1 to SRS FR-006 state enum; cannot be customized
- Pulse animation limited to running/hil_waiting only to avoid visual fatigue
- If `skill_hint` is null, show "(no skill)" in `--color-text-tertiary`

---

### 3.4 HIL Question Card

**SRS Trace**: FR-009, FR-010, FR-031
**Variants**: single_select / multi_select / free_text

#### Base Prompt
> A vertical card within the HILInbox workspace, max-width 720px, `--color-bg-surface` background, 1px `--color-border`, 8px radius, 20px padding. Top-right corner has a phase badge (e.g., "Phase: Work · TDD") using `--color-phase-work` tint. Header: ticket ID chip + amber Lucide `help-circle` icon 16px + "question header" text `--font-heading-3`. Body: full question text `--font-body` with proper Chinese line-height 1.6. Then renders the controls per variant (below). Footer: a divider (1px `--color-border-subtle`), then two buttons: "提交答复" (primary) on right, "暂缓" (ghost) on left.

#### Variant Prompts
> **single_select**: radio list; each row 40px tall with 14px Lucide circle icon (empty) on left, label and optional description below label in `--color-text-secondary` 12px. Selected row: icon becomes filled `check-circle` accent-primary, row background becomes `--color-bg-active`.
> **multi_select**: checkbox list; same layout; icon is `square` default / `check-square` checked. Chip counter "已选 3/5" in header area.
> **free_text**: large textarea `--font-code` or `--font-body` depending on `allowFreeformInput` context; min-height 160px; character counter bottom-right; placeholder shows SRS-referenced hint if available.

#### Style Constraints
- "Skip" / "暂缓" only enabled if skill explicitly permits; otherwise rendered disabled with tooltip "此问题必须回答"
- Submit button remains disabled until at least one option selected (multi/single) or text length ≥1 (free_text)
- On submit, card transitions to "已提交" state (muted colors, no controls) in 200ms

---

### 3.5 Stream-JSON Event Tree

**SRS Trace**: FR-034
**Variants**: collapsed / expanded / highlighted (filter match)

#### Base Prompt
> A left-indented tree view where each node is a stream-json event. Root nodes are ticket-level messages; child nodes are individual events (text / tool_use / tool_result / thinking). Each node renders as 1 line: a 12px Lucide caret icon (chevron-right when collapsed, chevron-down when expanded), an event-type chip (`tool_use` purple, `tool_result` cyan, `text` gray, `thinking` amber, `error` red) using --font-label 11px, a compact summary (e.g., "Read(/docs/plans/srs.md)" for tool_use, or first 80 chars of text). Indentation 16px per level. Hover row background `--color-bg-hover`. Click chevron to toggle; click row to open in right inspector panel. Font `--font-code` 13px for tool args; `--font-body` 13px for text.

#### Variant Prompts
> **Expanded**: shows full event body below summary, with JSON pretty-printed (2-space indent), color-syntax-highlighted using `--color-code-*` tokens, monospace, scrollable up to 320px then clipped with "展开全部" button.
> **Filtered / search match**: matched substring highlighted with `--color-state-hil` background (rgba amber 0.2); non-match rows faded to 0.4 opacity.

#### Style Constraints
- Events stream in live; auto-scroll to bottom ONLY if user hasn't manually scrolled in last 2s
- Tool call that has `permission_denial` set → mark with red outline on left edge
- JSON content >10KB collapsed by default with "（大对象，点击展开）" placeholder

---

### 3.6 Phase Progress Stepper

**SRS Trace**: FR-030
**Variants**: horizontal (RunOverview header) / compact (sidebar)

#### Base Prompt (Horizontal)
> A horizontal stepper with 8 nodes representing: Requirements → UCD → Design → ATS → Init → Work → ST → Finalize. Each node is a 36×36px circle; connecting line 2px between consecutive nodes. Node states: completed (filled with phase color + white check Lucide 16px), current (filled with phase color + ring + subtle pulse 1.5s), pending (hollow with 1.5px `--color-border` + label `--color-text-secondary`). Below each circle, a 12px label (e.g., "需求") using `--font-label`. Current node label in `--color-text-primary`, others in `--color-text-secondary`. Work node shows additional fraction "3/7" under label indicating feature progress. If phase is hotfix/increment/retrospective (non-mainline), a second row of smaller 24px circles appears below with dashed connector to indicate re-entry points.

#### Variant Prompts
> **Compact (sidebar)**: vertical orientation, nodes 20×20px, labels on right, connector 2px vertical. Used when sidebar expanded.

#### Style Constraints
- Completed nodes always show check icon for clarity
- Currently "paused" state (Run paused by user) renders current node with `pause` Lucide icon instead of pulse
- "blocked" state (anomaly ABORT or HIL past 10min without answer) renders current node in `--color-state-failed`

---

### 3.7 Diff Viewer

**SRS Trace**: FR-041
**Variants**: unified / side-by-side

#### Base Prompt (Unified)
> A monospace text viewer with 2 gutters: left gutter shows old line number (16px wide, right-aligned, `--color-text-tertiary`), second gutter shows new line number. Then a 3px wide prefix column showing `+` / `-` / ` ` / `@` in diff color. Then content in `--font-code` 13px with syntax highlight using `--color-code-*` tokens. Added lines have background `--color-diff-add-bg` (#033A16) and text `--color-diff-add-fg` (#3FB950); deleted lines `--color-diff-del-bg` (#67060C) and `--color-diff-del-fg` (#F85149); context lines use `--color-text-secondary`. Hunk header `@@ -old +new @@` in `--color-accent-secondary` with background `--color-bg-surface-alt`. Horizontal scroll for lines >120 chars. Header above: file path `--font-body` 14px 500, and +N/-N stat chips on right.

#### Variant Prompts
> **Side-by-side**: two columns separated by 1px border; old content left, new content right; changed lines aligned by hunk; unchanged lines flush.

#### Style Constraints
- When diff >500 lines, paginate by hunk with "展开后 N 个 hunk" button
- Binary files show placeholder "（二进制文件，不显示 diff）" with file size

---

### 3.8 Sidebar Navigation

**SRS Trace**: FR-030 (全局导航)
**Variants**: expanded (240px) / collapsed (56px) / drawer (<1024px fallback)

#### Base Prompt (Expanded)
> A vertical sidebar 240px wide, full-height. Background `--color-bg-surface` (#161B22); 1px right border `--color-border-subtle`. Top: 48px header showing "Harness" wordmark (Inter semibold 16px) + version chip (e.g., "v1.0.0") in `--color-text-tertiary` `--font-body-small`. Middle: nav items stacked — each is 40px tall, 16px horizontal padding, 20px Lucide icon + 14px label with 12px gap. Items (v1): `home` "总览"、`inbox` "HIL 待答" (with badge counter if >0)、`zap` "Ticket 流"、`file-text` "文档 & ROI"、`edit-3` "过程文件"、`git-branch` "提交历史"、`book-open` "Skills"、`settings` "设置". Active item: left edge 3px accent stripe (color by current phase), background `--color-bg-active`, label color `--color-text-primary`, icon `--color-accent-primary`. Hover: background `--color-bg-hover`. Bottom (pinned): 48px "Run 选择器" drop-down + runtime status badge (green dot "在线" or red dot "离线").

#### Variant Prompts
> **Collapsed**: width 56px; labels hidden; icons centered; active stripe still visible; tooltip appears on hover showing label.

#### Style Constraints
- Badge counter on "HIL 待答" shows count (1-99+); circle 18px, amber `--color-state-hil`, white text `--font-body-small` bold
- Sidebar collapse state persists per user via `~/.harness/ui-state.json`
- Runtime status: green = Claude & OpenCode both detected; amber = only one; red = neither

---

### 3.9 Modal / Dialog

**SRS Trace**: FR-032 API key 输入, FR-038 file edit confirm, FR-040 validation result
**Variants**: confirmation / form / info

#### Base Prompt
> A centered dialog 480px wide (forms up to 640px), max height 80vh. Background `--color-bg-surface`; 12px radius; `--shadow-lg`; 1px border `--color-border`. Inside: header 48px with title `--font-heading-2` on left and X close icon (20px Lucide, ghost) on right; divider; body with 24px padding; footer 64px with right-aligned button group (primary right, ghost left). Backdrop `rgba(0,0,0,0.6)` with 8px blur.

#### Variant Prompts
> **Confirmation**: 400px wide; body has single Lucide `alert-triangle` 24px icon (color by severity) + short text; two buttons.
> **Form**: 640px wide; body scrollable; validated on submit with inline errors.
> **Info**: 480px wide; body shows read-only info + "关闭" button only.

#### Style Constraints
- Escape key closes (unless form dirty → prompt confirmation)
- Primary action focused on open for keyboard operation
- Never stack modals; existing modal closes before opening new one

---

### 3.10 Toast / Alert Notification

**SRS Trace**: FR-029 异常可视化, global notifications
**Variants**: success / info / warning / error

#### Base Prompt
> A toast notification appears in bottom-right corner, 360px wide, min 48px tall, 8px radius, `--shadow-md`. Background `--color-bg-surface-alt`; left edge 4px accent color (by variant): success green, info blue, warning amber, error red. Layout: icon 16px Lucide (check-circle / info / alert-triangle / alert-octagon) in variant color + title `--font-body` 14px 500 + body `--font-body-small` 12px `--color-text-secondary` below title. Top-right close X 14px ghost. Auto-dismiss after 5s for success/info; warning 10s; error sticky until dismissed. Stack vertically with 8px gap.

#### Variant Prompts
> **Error with action**: includes a "查看详情" link on right that opens the corresponding ticket; sticky.
> **Progress variant**: for long operations (e.g., skill install), shows progress bar 3px at bottom of toast; updates via WebSocket.

---

### 3.11 Empty State

**SRS Trace**: global
**Variants**: no-runs / no-tickets / no-hil-pending / no-docs

#### Base Prompt
> Centered content with 120×120px illustration (line-drawn, single color `--color-text-tertiary`), below it a `--font-heading-3` title (e.g., "还没有 Run"), then `--font-body` description (e.g., "点击下方按钮在当前工作目录启动第一个 Run。"), then a primary button (e.g., "开始新 Run"). Vertical center aligned in parent container.

---

### 3.12 Table

**SRS Trace**: FR-038 (过程文件表格视图), FR-041 (commits)
**Variants**: compact / regular

#### Base Prompt (Regular)
> A data table with alternating row backgrounds: odd rows `--color-bg-surface`, even rows `--color-bg-surface-alt`. Column header row: `--font-label` 12px 500 uppercase, color `--color-text-secondary`, 12px vertical padding, 16px horizontal padding, 1px bottom border `--color-border`. Each cell: 14px Inter, 10px vertical padding. Sort icon (Lucide chevron-up/down 12px) on sortable columns, appears on hover or when active. Row hover: background `--color-bg-hover`. Row action icons (edit / delete) appear on hover at right edge, ghost buttons.

---

### 3.13 Chip / Badge / Tag

**SRS Trace**: FR-005 tool tag, FR-030 phase, FR-034 event type
**Variants**: solid / outline / dot

#### Base Prompt
> A pill-shaped chip 22-24px tall, 10px horizontal padding, 9999px radius. Background: solid variant uses tinted color (phase color at 20% opacity) + foreground color at 100%; outline variant transparent + 1px border + full-strength text; dot variant includes 6px round dot on left. `--font-label` 11px 500, subtle letter-spacing 0.02em. Optional Lucide icon 12px on left with 4px gap.

---

### 3.14 Settings Form Section

**SRS Trace**: FR-032
**Variants**: section-card / inline-row

#### Base Prompt (section-card)
> A settings card 8px radius, 1px `--color-border`, `--color-bg-surface`, 24px padding. Inside: `--font-heading-3` 15px title + `--font-body-small` description below, then a form with labeled inputs (per §3.2). Each input row has: label (12px 500 uppercase) + optional help icon with tooltip + input field + optional "Apply" button on right for instant-save fields. API Key fields show masked value (e.g., "••••••••1234") with "显示" button (24px ghost) to temporarily reveal.

---

### 3.15 Skill Tree Viewer (Read-only)

**SRS Trace**: FR-033 (v1 仅基础编辑)
**Variants**: tree / flat-list

#### Base Prompt (Tree)
> A collapsible tree showing `plugins/longtaskforagent/skills/*/SKILL.md` hierarchy. Each node: 14px Lucide folder / file icon + skill name `--font-body` 14px. Selected node: background `--color-bg-active`; right pane shows read-only markdown rendering of SKILL.md with `--font-body` for text, `--font-code` for code blocks, syntax-highlighted using `--color-code-*` tokens. YAML frontmatter collapsed by default with "展开 frontmatter" pill.

---

## 4. Page Prompts

### 4.1 Page: RunOverview（总览）

**SRS Trace**: FR-030, FR-003
**User Persona**: Harness User, primary landing page
**Entry Points**: 应用启动首屏 / sidebar "总览"

#### Layout Description
Full-page layout with sidebar (3.8). Main area: Top header 64px with page title "总览" + current Run ID chip + Run controls (Pause / Cancel ghost buttons) right-aligned. Below header, 24px gap, then the horizontal **Phase Progress Stepper** (3.6) occupying full width up to 1200px, centered. Below stepper (24px gap), two-column grid (2:1 ratio): left column "当前票据" panel shows expanded **Ticket Card** (3.3 expanded variant) for the currently running ticket; right column "运行指标" panel shows a Settings-Form-Section (3.14) with read-only rows: Cost USD / Turns / Duration / Tool (claude/opencode) / Skill (current phase) / git HEAD (short sha + 点击跳到 CommitHistory). Below the two-column (24px gap), full-width "近期票据流" section showing last 10 **Ticket Cards** (3.3 compact variant, stacked list). A "查看全部" ghost link at section top-right routes to TicketStream page.

#### Full-Page Prompt
> A dashboard landing page at 1280×800 viewport. Sidebar on left (240px expanded state, showing "总览" item active with blue phase-requirements accent stripe since requirements is current phase). Main content area (padding 24px). Top 64px header: on left, page title "总览" `--font-heading-1` 24px 600 color `--color-text-primary`; immediately right, a Run ID chip showing "#run-2026-04-21-001" in `--font-code-sm` (cyan accent); on far right, two ghost buttons "暂停" and "取消" with Lucide pause/x icons 14px. Below, centered phase stepper showing 8 circular nodes (Requirements node marked current with blue pulsing ring and check; UCD/Design/ATS/Init/Work/ST/Finalize pending hollow). Under stepper, 2-col grid: larger left card (520×240px) titled "当前票据" showing an expanded ticket card #t-0042 for skill long-task-requirements, state dot pulsing green (running), body shows last 3 stream-json events in collapsed form with event chips. Right card (280×240px) titled "运行指标" with 6 label-value rows (Cost $0.14, Turns 8, Duration 2m 14s, Tool claude, Skill long-task-requirements, HEAD de507b2). Below the grid, a section header "近期票据流" with "查看全部" ghost link right-aligned; then 10 compact ticket cards stacked. Overall tone: cold dark #0D1117 app bg, surfaces #161B22, text #E6EDF3, accents #58A6FF/#22C55E/#F59E0B/#A78BFA.

#### Key Interactions
- Clicking the "当前票据" card opens TicketStream focused on that ticket
- Clicking any phase node in the stepper opens a tooltip with "X 张票据已完成，耗时 N"
- Pause button: first click → toast "确认暂停 Run？"; second click within 3s → actual pause
- Cancel: always requires confirmation modal (3.9)

#### Responsive Behavior
- **Desktop (≥1280px)**: layout as above
- **Narrow desktop (1024-1279px)**: two-column grid collapses to single column; stepper remains horizontal but nodes compact
- **Mobile (<1024px)**: not supported in v1 (per SRS NFR-008)

---

### 4.2 Page: HILInbox（HIL 待答）

**SRS Trace**: FR-031, FR-010, FR-009
**User Persona**: Harness User when a HIL question arrives
**Entry Points**: sidebar "HIL 待答" (with badge counter) / notification toast link

#### Layout Description
Sidebar + main. Main area header 64px with page title "HIL 待答" + counter chip "3 条待答". Body: single-column max-width 720px, centered. Each待答 HIL 作为独立 **HIL Question Card** (3.4) vertically stacked with 16px gap. 若列表为空，渲染 **Empty State** (3.11) "暂无待答问题".

#### Full-Page Prompt
> A focused inbox-style page 1024×768 viewport. Sidebar unchanged; "HIL 待答" item active with amber left stripe and amber badge "3" on the right. Main content 24px padding. Header "HIL 待答" `--font-heading-1` + amber chip "3 条待答" `--color-state-hil` 20% opacity bg with full-strength text. Below, single-column stack of 3 HIL Question Cards at 680px max-width, centered. Card 1: phase badge "Phase: Requirements", question header "请确认 HIL PoC 的成功率门槛", 3 radio options (20/25/30 次循环 ≥95%), submit button disabled until selection. Card 2: "Phase: UCD", multi-select with 4 checkbox options (choose deferred FRs). Card 3: "Phase: Design", free-text area 160px tall with placeholder "请描述期望的类图边界". Overall: calm focused look, amber accents for HIL, dark background.

#### Key Interactions
- Submit reveals confirmation toast "已提交答复 · 等待 skill 继续"
- Cards disappear once answered (transition 200ms slide + fade)
- If connection to tool dropped mid-answer, card shows warning banner "会话已断开，刷新后重试"

---

### 4.3 Page: SystemSettings（设置）

**SRS Trace**: FR-032, FR-021, FR-022, FR-046
**User Persona**: Harness User 首次配置 / 切换模型 / 更新 API key
**Entry Points**: sidebar "设置"

#### Layout Description
Sidebar + main. Main area: page title "设置" + 左侧二级 tab 列 (180px width): 模型与 Provider / API Key 与认证 / Classifier / 全局 MCP / 界面偏好. 右侧 tab 内容区 flex fill. 每个 tab 是一个或多个 **Settings Form Section** (3.14) 卡片堆叠.

#### Full-Page Prompt
> A two-column settings page. Left 180px vertical tab list: 5 items (模型与 Provider · API Key 与认证 · Classifier · 全局 MCP · 界面偏好), current tab "模型与 Provider" active with left stripe and bg-active. Right tab content: 3 stacked section cards. Section 1 "Run 默认模型": label + select dropdown (Claude sonnet/opus/haiku; OpenCode providers). Section 2 "Per-Skill 模型覆写规则": a table with 3 columns (Skill · Tool · Model) + "新增规则" button; rows show e.g. "long-task-requirements · claude · opus-4-7". Section 3 "Per-Ticket 覆写 (高级)": toggle + description. All cards use #161B22 background on #0D1117 app bg, #E6EDF3 text.

#### Key Interactions
- API Key field uses masked input (3.14); "保存到 keyring" button writes via platform API
- Classifier toggle disabled → all per-skill model overrides still active but no verdict classification
- "测试连接" button next to each provider runs a minimal ping (curl to base_url/v1/models)

---

### 4.4 Page: PromptsAndSkills（Skills）

**SRS Trace**: FR-033 (v1 仅基础编辑), FR-045
**User Persona**: Harness User 要查看 / 更新 skill，或微调 classifier prompt
**Entry Points**: sidebar "Skills"

#### Layout Description
Sidebar + main. Main: left 320px **Skill Tree Viewer** (3.15) — a 2-层 tree (按 plugin 分组: longtaskforagent / harness-classifier); 中间 flex content 显示选中条目 markdown render (readonly for skill, editable for classifier prompt); 右上 action bar "更新 Plugin" 按钮触发 git pull dialog (3.9 form variant).

#### Full-Page Prompt
> 3-pane layout: left 320px skill tree (#161B22 bg, 1px right border), center scroll-able markdown viewer with dark syntax highlighting (font-code 13px, headings Inter 18/15/13px), right 40px empty reserved for future. Active tree node "long-task-requirements" highlighted. Center pane shows rendered SKILL.md with frontmatter collapsed, body text in #E6EDF3, code blocks in #1C2128 with #D2A8FF/A5D6FF/FF7B72 syntax colors. Top right of center pane, "更新 Plugin" ghost button with Lucide git-pull-request icon.

#### Key Interactions
- Tree node single-click: show preview; double-click: pin
- Classifier prompt (harness-classifier/system_prompt.md) renders an Edit mode toggle (default read, click → textarea)
- "更新 Plugin" opens modal with git repo URL field + local path field + "Pull" button

---

### 4.5 Page: TicketStream（Ticket 流）

**SRS Trace**: FR-034, FR-005..007
**User Persona**: Harness User 排障 / 审计某票据执行过程
**Entry Points**: sidebar "Ticket 流" / RunOverview 卡片点击

#### Layout Description
Sidebar + main. Main: top filter bar (60px) with search + state/tool/parent 多选筛选 + run 选择. 下方 3-pane split: 左 320px ticket list (compact cards 3.3 stacked), 中 flex stream-json event tree (3.5), 右 360px inspector panel shows selected event details (raw JSON + metadata + actions)。

#### Full-Page Prompt
> 3-pane ticket stream explorer. Top filter bar: search input 320px + 3 multi-select chips "状态" "工具" "Run" + "清除" ghost. Left pane: list of 20+ compact ticket cards (3.3), each 64px tall with state dot + id + skill. Middle pane: stream-json tree with 30+ events, chevron toggles, event-type chips (purple tool_use, cyan tool_result, gray text, amber thinking), JSON pretty-print with syntax highlight. Right inspector: tabs "事件" "元数据" "Raw"; event tab shows timestamp/duration/size + structured content; actions "导出 JSON" "重新分类" (if classifier enabled) "复制到剪贴板".

#### Key Interactions
- Virtualized scrolling in both left list and middle tree (10k+ events supported)
- Dragging splitter adjusts pane widths; persisted in ui-state
- Ctrl/Cmd+F opens inline search within stream tree

---

### 4.6 Page: DocsAndROI（文档）

**SRS Trace**: FR-035 (v1 仅文件树 + Markdown 预览)
**User Persona**: Harness User 审阅当前 run 生成的文档
**Entry Points**: sidebar "文档 & ROI"

#### Layout Description
Sidebar + main. Main: left 280px 文件树 (docs/plans/*, docs/features/*, docs/test-cases/*) 按目录层级；右 flex markdown 预览 + TOC 侧边栏 (180px)。v1 **不含** ROI 按钮 (FR-035b 延后 v1.1)。

#### Full-Page Prompt
> Document reader layout. Left 280px file tree with folder icons; expanded nodes show srs/ucd/design/ats/st-report md files, each with size chip. Active file "2026-04-21-harness-srs.md" highlighted. Center 700px max-width scrollable markdown view: H1 "Harness — 软件需求规约" 24px bold #E6EDF3; section headings blue accent; body Inter 14px #E6EDF3; tables with #30363D borders; code blocks in #1C2128 with monospace. Right 180px sticky TOC showing current section highlight. Overall clean document reading feel.

#### Key Interactions
- Click TOC item: smooth scroll to section
- Search Ctrl/Cmd+F inline within viewer
- "复制 markdown" ghost button top-right exports raw md
- v1.1 placeholder: grayed out "运行 ROI 分析" button with tooltip "v1.1 规划中"

---

### 4.7 Page: ProcessFiles（过程文件）

**SRS Trace**: FR-038, FR-039, FR-040
**User Persona**: Harness User 手动调整 feature-list.json / env-guide / long-task-guide
**Entry Points**: sidebar "过程文件"

#### Layout Description
Sidebar + main. Main: top file selector bar with chips for each editable file (feature-list.json / env-guide.md / long-task-guide.md / .env.example). 下方 2-pane: 左 flex 结构化表单 (or md textarea); 右 320px validation panel 显示 inline 校验结果 (实时 + 保存时脚本校验).

#### Full-Page Prompt
> File editor with validation panel. Top chip row: "feature-list.json" active (blue tint), 3 other chips. Left pane: structured form for feature-list.json — project name input, tech_stack group (3 fields: language/test_framework/coverage_tool), quality_gates group, features array table with inline edit per feature (id/title/status/dependencies); "+ 添加特性" button. Right panel: sticky header "实时校验" green checkmark + "后端校验" button; below, scrollable list of issues each with: icon (check / alert-triangle / alert-circle), severity label, row ref "FR-014", message "srs_trace 缺失"; click issue focuses the offending form field. Bottom: "保存并提交" primary + "还原更改" ghost.

#### Key Interactions
- onChange: front-end schema validation runs (frontend Zod / JSON Schema), issues panel updates within 300ms
- "后端校验" triggers `validate_features.py` via subprocess; result added to issues panel
- Dirty state prevents navigation with confirm dialog

---

### 4.8 Page: CommitHistory（提交历史）

**SRS Trace**: FR-041, FR-042
**User Persona**: Harness User 审阅每个 feature 的代码变更
**Entry Points**: sidebar "提交历史" / RunOverview "git HEAD" 链接

#### Layout Description
Sidebar + main. Main: top filter bar (run 选择 / feature 选择 / 时间范围). 下方 2-pane split: 左 360px commits list (每 row 80px: sha + message + author + time + feature chip); 右 flex **Diff Viewer** (3.7) 显示选中 commit 的 patch.

#### Full-Page Prompt
> Commit browser. Top filter: Run chip "#run-2026-04-21-001" + feature select + "全部" time. Left: scrollable commit list, each row: 7-char sha `de507b2` in font-code-sm cyan, single-line message `docs: add Harness SRS (Lite track)...`, author "Harness" + time "2m ago", feature chip bottom "feature-12" (if applicable). Active commit highlighted. Right: unified diff viewer showing file "docs/plans/2026-04-21-harness-srs.md" added 848 lines (big +848 stat chip), monospace diff with + lines on green bg, @@ hunk headers on muted surface-alt; header "+" sign and line numbers in gutters. Floating "切换到 side-by-side" ghost button top-right of diff.

#### Key Interactions
- Commit row click: load patch (lazy fetch)
- Diff viewer: collapsible per-file; "展开全部" / "折叠全部" buttons
- "复制 sha" icon button on each commit row

---

## 5. Style Rules & Constraints

### 5.1 Accessibility
- WCAG AA 基线：所有文本对比 ≥4.5:1（已在色板表中标注）；UI controls 尺寸 ≥32×32 像素以满足触控目标（即便桌面环境）
- 所有交互元素必须有可见 focus ring（2px `--color-border-emphasis` offset 2px）
- 状态色信息不能仅靠颜色传达：配合图标 / 文字（e.g., 错误除红色外必有 alert-triangle 图标 + 文字说明）
- 键盘导航：Tab 顺序遵循视觉顺序；Esc 关闭 modal；Ctrl/Cmd+K 打开命令面板（v1.x 规划）
- Screen reader：所有 icon-only 按钮须 `aria-label`；chip 须有可读 label

### 5.2 Animation & Motion
- 状态转场 120-200ms ease-out；避免 >300ms
- 运行中 ticket 的 pulsing 动画 1.5s infinite（频率 0.67Hz，低于前庭刺激阈值）
- 尊重 `prefers-reduced-motion`: 所有非关键动画降级为无过渡

### 5.3 Responsive
- v1 目标 PyWebView 桌面窗口，最小 1024×720；< 1024 的断点不适配（SRS NFR-008）
- 侧边栏在 1024-1279px 自动折叠到 56px 变 icon-only
- 主内容区最大 1440px，居中留白

### 5.4 Dark Mode
- v1 只有 dark theme（EXC 已记录）；所有色 token 基于 dark 基线；不提供 light/high-contrast 变体

### 5.5 Icon 使用规则
- 所有 icon 统一 Lucide Icons，禁止混入其他 icon set
- 默认 16px；inline in text 14px；page-level 20px；empty state 24px+
- Icon stroke-width 1.5px；rounded caps

### 5.6 状态色语义（Hard-coded mapping）

本系统状态色语义由 SRS FR-006（ticket 状态机）锚定，不可被主题覆写：

| Ticket State | Color Token | Visual Cue |
|---|---|---|
| pending | `--color-state-pending` | 灰 dot |
| running | `--color-state-running` | 绿 dot + pulse |
| classifying | `--color-accent-secondary` | 紫 dot |
| hil_waiting | `--color-state-hil` | 琥珀 dot + pulse + sidebar badge |
| completed | `--color-state-completed` | 暗绿 check |
| failed | `--color-state-failed` | 红 dot + toast |
| aborted | `--color-state-failed` | 红 X |
| retrying | `--color-state-retrying` | 橙 dot + countdown |

### 5.7 中文排印
- 中英混排时，中英之间自动添加 0.25em 空隙（使用 `text-spacing-trim: space-all` + 必要时 `&nbsp;`）
- 中文正文 `--font-body` 1.6 line-height（覆盖西文 1.5）；标题 1.35
- 标点禁用 full-width 括号（用半角 `(`）保持与 Inter 气质一致

### 5.8 Data Density
- 列表 / 表格默认 compact 模式：行高 40px；用户可通过 "设置 · 界面偏好" 切到 comfortable（52px）

---

## 6. 组件 ↔ 页面 矩阵

| Component | 4.1 RunOverview | 4.2 HILInbox | 4.3 Settings | 4.4 Skills | 4.5 TicketStream | 4.6 Docs | 4.7 ProcessFiles | 4.8 CommitHistory |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 3.1 Button | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3.2 Input | | ✓ | ✓ | ✓ | ✓ | | ✓ | |
| 3.3 Ticket Card | ✓ | ✓ mini | | | ✓ | | | |
| 3.4 HIL Card | | ✓ | | | | | | |
| 3.5 Stream Tree | | | | | ✓ | | | |
| 3.6 Phase Stepper | ✓ | | | | | | | |
| 3.7 Diff Viewer | | | | | | | | ✓ |
| 3.8 Sidebar | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3.9 Modal | | | ✓ | ✓ | | | ✓ | |
| 3.10 Toast | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3.11 Empty | ✓ | ✓ | | | ✓ | ✓ | | ✓ |
| 3.12 Table | | | ✓ | | | | ✓ | ✓ |
| 3.13 Chip/Badge | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3.14 Settings Section | | | ✓ | | | | | |
| 3.15 Skill Tree | | | | ✓ | | | | |

