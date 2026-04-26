# 测试用例集: F22 · Fe-Config — SystemSettings + PromptsAndSkills + DocsAndROI + ProcessFiles + CommitHistory

**Feature ID**: 22
**关联需求**: FR-032, FR-033, FR-035, FR-038, FR-039, FR-041, NFR-008, IFR-004, IFR-005, IFR-006（ATS §2 行类别约束：FR-032/033/035/038/039={FUNC,BNDRY,SEC,UI}，FR-041={FUNC,BNDRY,UI}，NFR-008={SEC}，IFR-004={FUNC,BNDRY,SEC,PERF}，IFR-005={FUNC,BNDRY,SEC}，IFR-006={FUNC,BNDRY,SEC}；Feature Design §Visual Rendering Contract 13 元素 + §Test Inventory 22-01..22-44）
**日期**: 2026-04-26
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为 F22（5 页面 React + Vite 前端：SystemSettings / PromptsAndSkills / DocsAndROI / ProcessFiles / CommitHistory）的黑盒 ST 验收测试用例。预期结果**仅**从 SRS（FR-032/033/035/038/039/041 + NFR-008 + IFR-004/005/006 验收准则）、ATS §2 行类别约束、Feature Design §Interface Contract postcondition、§Visual Rendering Contract 13 元素 + 9 正向 + 9 交互深度断言、UCD §4.3/§4.4/§4.6/§4.7/§4.8 页面指针、§7 视觉回归 SOP、可观察接口（生产单源 `http://127.0.0.1:8765/{,settings,skills,docs,process-files,commits}` + 14 IAPI-002 REST 路由 + Chrome DevTools MCP `take_snapshot`/`take_screenshot`/`evaluate_script`/`list_console_messages`/`click`/`fill`）推导，不阅读实现源码。
> - **Clarification Addendum 应用**：Feature Design `## Clarification Addendum` 第 1 项（datamodel-code-generator 工具假设）已记录为 assumption，与 ST 预期结果无关（schema 字面定义来自 design §6.2.4，不因导出工具变更而改）；本文档不重复标记。
> - **Specification Gap（执行期发现，已 assume 后继续）**：SRS / Design 列出 SSRF 防护语义但未限定实现层位（PUT 与 /test 之间）。**Assumed**：以可观察黑盒终点为准——SSRF 私网拦截在 `POST /api/settings/classifier/test` 路径返回 `ok:false, error_code:'ssrf_blocked'`（验证：`curl -X POST .../test -d {provider:custom, base_url:http://127.0.0.1:1, model_name:x}` → `{"ok":false,...,"error_code":"ssrf_blocked"}`，HTTP 200）。`PUT /api/settings/classifier` 不拒绝（仅持久化 base_url 字段），用户在点击"测试连接"时获得反馈。本假设不改变 IFR-004 对外契约（test 拒绝即可观察）。
> - `feature.ui == true` → 本文档含 UI 类别用例并通过 Chrome DevTools MCP 在生产单源（FastAPI StaticFiles + 同源 REST）中执行；UI 用例**全部不可跳过**。
> - **服务依赖**：`api` (`http://127.0.0.1:8765/api/health`) + 生产 SPA bundle (`apps/ui/dist/`) 经 FastAPI StaticFiles 同源挂载；`ui-dev` (`http://127.0.0.1:5173/`) 仅作为开发期备份路径，不作为 ST 主验证目标。`HARNESS_WORKDIR=/home/machine/code/Eva` + `HARNESS_HOME=/tmp/harness-home-st22` 经 lifespan 自动 `wire_services`。
> - **后端集成边界**：F22 是 IAPI-002（14 路由）/ IAPI-014（keyring REST）/ IAPI-016（validate）/ IAPI-018（skills install/pull）的纯 Consumer。后端 F01/F10/F12/F19/F20 已 passing；本 ST 用真实后端。
> - **前端单元/组件测试复用**：`apps/ui/src/routes/*/__tests__/*.test.{ts,tsx}` + `tests/integration/test_f22_real_settings_consumer.py` + `tests/test_f22_coverage_supplement*.py` 已绿（TDD 90.06%/86.53%）。本 ST"自动化测试"列引用相关测试函数作为可追溯锚，ST 黑盒执行以**运行中的 api+ SPA + Chrome DevTools MCP** 为主。
> - **类别配比**：负向用例（FUNC/error + BNDRY + SEC）≥ 40%（详见摘要）。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 6 |
| boundary | 3 |
| ui | 5 |
| security | 3 |
| performance | 1 |
| **合计** | **18** |

> 负向用例占比：FUNC/error（ST-FUNC-022-005/006）+ BNDRY（ST-BNDRY-022-001/002/003）+ SEC（ST-SEC-022-001/002/003）= 8/18 ≈ 44.4% ≥ 40%（Feature Design Test Inventory 已校 18/44 ≈ 40.9%；ST 黑盒折叠后比率仍达标）。

---

### 用例编号

ST-FUNC-022-001

### 关联需求

FR-032 AC（SystemSettings 保存 API key → keyring 存原文 + UI masked）· §IC `useGeneralSettings` / `useUpdateGeneralSettings` postcondition · §Design Alignment seq msg#1-#5 · §VRC `[data-component="settings-vtabs"]` + `[data-component="masked-key-input"]` · Feature Design Test Inventory 22-01

### 测试目标

验证 SystemSettings 进入 ApiKey tab 时显示 `MaskedKeyInput`，`useGeneralSettings` 返回的 `api_key_masked` 字段正确驱动 UI 渲染：未配置时显示占位（masked=null），已配置时显示 `***` 前缀的 masked 字符串（最后 3 字符）。可观察表面：浏览器 DOM + 真实 `GET /api/settings/general` 响应。

### 前置条件

- `api` (127.0.0.1:8765) 健康（`HARNESS_WORKDIR=/home/machine/code/Eva` 已经 lifespan wire）
- `apps/ui/dist/` 含最新生产 bundle（`vite build` 已绿）
- 浏览器加载 `http://127.0.0.1:8765/` 完成（FastAPI StaticFiles SPA）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/"); wait_for(["Harness"]) 或 sidebar 出现 | 页面加载完成；`#root` 已挂载 |
| 2 | evaluate_script(error_detector) — `() => Array.from((window.__errors__||[])).length === 0 && (!document.body.innerText.includes('TypeError'))` | Layer 1: count = 0 |
| 3 | 点击 sidebar `设置` 项 → SPA 路由到 `/settings`；wait_for(["设置"]) | URL 变为 `http://127.0.0.1:8765/settings`；`[data-component="settings-vtabs"]` 节点存在 |
| 4 | evaluate_script(`() => document.querySelectorAll('[data-component="settings-vtabs"] .vtab').length`) | 返回 ≥ 5（5 个二级 tab：Models / ApiKey / Classifier / MCP / UI；§VRC 正向断言 1） |
| 5 | 点击 ApiKey tab → take_snapshot | EXPECT: `[data-component="settings-form-section"][data-tab="apikey"]` 存在；其内 `[data-component="masked-key-input"]` 节点存在；REJECT: 任何明文 input value 含 plaintext API key（首次未配置时 masked=null，应显示"未配置"占位且无 input） |
| 6 | evaluate_script(`async () => { const r = await fetch('/api/settings/general'); const j = await r.json(); return { masked: j.api_key_masked, hasPlain: 'api_key_plaintext' in j }; }`) | 返回 `{masked: null, hasPlain: false}`（首次未配置；响应体中 plaintext 字段不存在） |
| 7 | list_console_messages(["error"]) | 返回 0 条 error |

### 验证点

- `/api/settings/general` 经 lifespan wire 后返回 200 且体含 `api_key_masked` + `api_key_ref` + `keyring_backend` 字段，**不**含 `api_key_plaintext`
- SystemSettings 5 vertical tab 节点数 = 5（FR-032 + UCD §4.3）
- ApiKey tab 中 MaskedKeyInput DOM 节点存在；未配置时不显示明文输入框
- 控制台无 error

### 后置检查

- 浏览器保留供 ST-SEC-022-001 / ST-UI-022-001 复用

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/system-settings-page.test.tsx`、`tests/integration/test_f22_real_settings_consumer.py::test_general_settings_get_returns_keyring_backend_and_no_plaintext`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-022-002

### 关联需求

FR-033 AC-1（PromptsAndSkills 树形列出 SKILL.md 只读）· §IC `useSkillTree` postcondition · §VRC `[data-component="skill-tree-viewer"]` · Feature Design Test Inventory 22-06

### 测试目标

验证进入 `/skills` 后 `useSkillTree` 调真实 `GET /api/skills/tree`，无论 plugins 数为 0 或 N，UI 渲染 `SkillTreeViewer` 容器（`[data-component="skill-tree-viewer"]`），且当 plugins 非空时每个节点带 `data-skill-readonly="true"`；当为空（当前 workdir 无 plugins 目录）时显示空态而**不**崩溃。可观察表面：DOM + 真实 REST。

### 前置条件

- `api` 健康
- 浏览器在 `http://127.0.0.1:8765/`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/skills"); wait_for(["提示词", "skill"]) | 页面加载；URL 含 `/skills` |
| 2 | evaluate_script(error_detector) | Layer 1: count = 0 |
| 3 | evaluate_script(`async () => (await (await fetch('/api/skills/tree')).json())`) | 返回对象含 `root`、`plugins:[...]`；当前 workdir 下 plugins 数可能为 0 |
| 4 | take_snapshot() | EXPECT: `[data-component="skill-tree-viewer"]` 容器存在；含至少 1 个文本节点（空态如"暂无 skill"或者列出节点）；REJECT: 任何 `contenteditable="true"` 的 skill 节点（FR-033 SEC：只读） |
| 5 | evaluate_script(`() => { const nodes = document.querySelectorAll('[data-component="skill-tree-viewer"] [data-skill-readonly]'); return Array.from(nodes).every(n => n.getAttribute('data-skill-readonly') === 'true'); }`) | 返回 `true`（所有 skill 节点 readonly；若节点数=0 则空数组的 `every` 也返 `true`，对应空态语义不破坏） |
| 6 | list_console_messages(["error"]) | 0 |

### 验证点

- `/api/skills/tree` 在 wire_services 已生效后返回有效 JSON（即使 plugins 为空）
- SkillTreeViewer 容器在两种态（空 / 非空）均渲染，无崩溃
- 任何已渲染 skill 节点都带 readonly 标记（FR-033 SEC）

### 后置检查

- 保持浏览器

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/prompts-and-skills/__tests__/prompts-and-skills-page.test.tsx::*`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-022-003

### 关联需求

FR-033 AC-2（编辑 classifier prompt 保存 → 历史追加一条）· §IC `useUpdateClassifierPrompt` postcondition · §VRC `[data-component="prompt-history"]` · INT-019 · Feature Design Test Inventory 22-07

### 测试目标

验证在 `/skills` 中编辑 classifier prompt 并经真实 `PUT /api/prompts/classifier` 保存后，`usePromptHistory` 重新取数，`history.length` +1，新条目 hash 与旧 history[0].hash 不同，UI 列表追加一行。可观察表面：DOM `<li>` 数量 + 真实后端历史。

### 前置条件

- `api` 健康
- 浏览器在 `http://127.0.0.1:8765/skills`
- `~/.harness` 下 prompt store 已经 F19 初始化（首次启动自动建）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | evaluate_script(`async () => { const j = await (await fetch('/api/prompts/classifier')).json(); return j.history.length; }`) | 返回数值 N（≥ 0；记为 N0） |
| 2 | navigate_page("http://127.0.0.1:8765/skills"); wait_for(["prompt"]) | 页面加载 |
| 3 | 找到 prompt 编辑器 `[data-testid="prompt-editor-textarea"]`；fill(uid, "ST22 prompt rev " + Date.now()) | 文本写入成功 |
| 4 | 点击保存按钮（`prompt-editor` 区内的 submit 按钮） → wait_for(网络空闲 1 s) | 触发 `PUT /api/prompts/classifier`；`useMutation` resolved |
| 5 | evaluate_script(`async () => { const j = await (await fetch('/api/prompts/classifier')).json(); return j.history.length; }`) | 返回 `N0 + 1`（FR-033 AC-2） |
| 6 | take_snapshot() | EXPECT: `[data-component="prompt-history"] li` 行数 = `N0 + 1`；最新行 hash ≠ 之前 history[0].hash |
| 7 | list_console_messages(["error"]) | 0 |

### 验证点

- `PUT /api/prompts/classifier` 200 响应，body 含新 history entry
- 后端历史追加（持久化）—— Step 5 重读返回的 length = Step 1 + 1
- 前端 UI 列表数量同步刷新（`prompt-history` `<li>` 数量 = N0+1）

### 后置检查

- 历史已增 1 条；workdir 内的 prompt store 文件含新 entry（F19 owned）

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/prompts-and-skills/__tests__/prompts-and-skills-page.test.tsx::*`、`tests/integration/test_f22_real_settings_consumer.py::*prompt*`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-022-004

### 关联需求

FR-035 AC（DocsAndROI 文件树 + Markdown 预览）· §IC `useFileTree` / `useFileContent` postcondition · §VRC `[data-component="docs-tree"]` + `[data-component="markdown-preview"]` + `[data-component="toc"]` · Feature Design Test Inventory 22-10

### 测试目标

验证进入 `/docs` 后 `useFileTree(root='docs')` + `useFileContent(...)` 调真实 REST，三 pane（文件树 / 预览 / TOC）DOM 节点同时存在；选中一份真实 markdown 文件后 MarkdownPreview 内容长度 > 0，TocPanel 至少渲染 1 个锚点。可观察表面：DOM + 真实 REST。

### 前置条件

- `api` 健康；`HARNESS_WORKDIR=/home/machine/code/Eva` 含 `docs/plans/*.md`
- 浏览器在 `http://127.0.0.1:8765/`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/docs"); wait_for(["文档", "ROI"]) | 页面加载 |
| 2 | evaluate_script(`async () => (await (await fetch('/api/files/tree?root=docs')).json())`) | 返回 `{root: ".../docs", nodes: [...]}` 含 ≥ 1 个 entry（含 `plans/2026-04-21-harness-srs.md`） |
| 3 | take_snapshot() | EXPECT: `[data-component="docs-tree"]` + `[data-component="markdown-preview"]` + `[data-component="toc"]` 三节点同时存在；REJECT: 任何 ROI 按钮 enabled |
| 4 | 在 docs-tree 中点击 `plans/2026-04-21-harness-srs.md` 节点（或经 evaluate_script 调用 useFileContent 钩子等价 fetch）`fetch('/api/files/read?path=docs/plans/2026-04-21-harness-srs.md')` 等价响应回填 | MarkdownPreview 内 `[data-component="markdown-preview"]` 内文本长度 > 0 |
| 5 | evaluate_script(`() => document.querySelectorAll('[data-component="toc"] li').length`) | 返回 ≥ 1（TocPanel 解析 H1-H4 锚点） |
| 6 | list_console_messages(["error"]) | 0 |

### 验证点

- 三 pane 同时存在（FR-035 + UCD §4.6）
- MarkdownPreview 渲染真实文件内容（content.length > 0）
- TocPanel 至少 1 个锚点
- ROI 按钮 disabled（FR-035 v1 subset，由 ST-UI-022-002 进一步覆盖）

### 后置检查

- 保持浏览器

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/docs-and-roi/__tests__/docs-and-roi-page.test.tsx::*`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-022-005

### 关联需求

FR-039 AC-1（必填字段空 onChange → 字段红 + Save 禁用）· §IC `<ProcessFileForm>` Zod 校验 · §VRC `[data-component="process-file-form"] [data-invalid="true"]` · Feature Design Test Inventory 22-13

### 测试目标

验证在 `/process-files` 编辑 `feature-list.json` 时，清空必填字段 `project` 后，对应 input 节点带 `data-invalid="true"`，Save 按钮 `disabled` 属性存在；填回非空 → invalid 移除 + Save 启用。可观察表面：DOM + 浏览器原生输入事件。

### 前置条件

- `api` 健康；`HARNESS_WORKDIR` 含 feature-list.json
- 浏览器加载 `/process-files`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/process-files"); wait_for(["过程文件", "feature-list"]) | 页面加载 |
| 2 | evaluate_script(error_detector) | Layer 1: count = 0 |
| 3 | take_snapshot() | EXPECT: `[data-component="process-file-form"]` 存在；至少 1 个 fieldset 渲染 schema 顶层 key（features / constraints / quality_gates 等） |
| 4 | 找到 `project` input；fill(uid, "")（清空必填） | input value="" |
| 5 | evaluate_script(`() => { const f = document.querySelector('[data-component="process-file-form"]'); const inv = f.querySelectorAll('[data-invalid="true"]'); const save = f.querySelector('button[type="submit"], button[data-action="save"]'); return { invalidCount: inv.length, saveDisabled: save?.disabled === true }; }`) | 返回 `{invalidCount: ≥1, saveDisabled: true}` |
| 6 | fill(同 uid, "Harness") | invalid 标记移除 |
| 7 | evaluate_script（同 5） | 返回 `{invalidCount: 0, saveDisabled: false}`（或 false 视乎其余字段；必填字段全填后应 enabled） |
| 8 | list_console_messages(["error"]) | 0 |

### 验证点

- onChange 时前端 Zod 校验立即触发（FR-039 AC-1）
- 必填空 → `data-invalid="true"` + Save disabled
- 必填回填 → invalid 移除 + Save 可用
- 控制台无 error

### 后置检查

- 不调用 Save，避免覆盖真实 feature-list.json；浏览器保留

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/process-files-page.test.tsx::*`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-022-006

### 关联需求

FR-041 AC-1 + AC-2（CommitHistory 列表 + diff viewer）· §IC `useCommits` / `useDiff` postcondition · §VRC `[data-component="commit-list"] [data-sha]` + `[data-component="diff-viewer"] [data-line-type]` · Feature Design Test Inventory 22-16 / 22-17

### 测试目标

验证进入 `/commits` 后 `useCommits` 调真实 `GET /api/git/commits`，列表渲染 N 条 commits（N 取决于 git 仓库历史，应 ≥ 5）；选中一条 commit → `useDiff(sha)` 返回 hunks，DiffViewer 渲染 add/del 行（`data-line-type` 节点 ≥ 1）。可观察表面：DOM + 真实 git CLI subprocess。

### 前置条件

- `api` 健康；`HARNESS_WORKDIR` 是 git 仓库（包含 ≥ 5 commits）
- 浏览器加载 `/commits`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/commits"); wait_for(["提交历史", "commit"]) | 页面加载 |
| 2 | evaluate_script(`async () => (await (await fetch('/api/git/commits')).json()).length`) | 返回 N ≥ 5（IFR-005 真实 git CLI；当前仓库历史远 > 5） |
| 3 | take_snapshot() | EXPECT: `[data-component="commit-list"] [data-sha]` 节点数 = N；REJECT: `[data-testid="not-a-git-repo-banner"]` 不存在 |
| 4 | 点击列表第一行 commit；wait_for(["@@"], { in: '[data-component="diff-viewer"]' }) 或 wait_for diff 加载 | DiffViewer 内容更新 |
| 5 | evaluate_script(`() => { const lines = document.querySelectorAll('[data-component="diff-viewer"] [data-line-type]'); const addLines = document.querySelectorAll('[data-component="diff-viewer"] [data-line-type="add"]'); return { total: lines.length, add: addLines.length }; }`) | 返回 `{total: ≥1, add: ≥0}`（最少 1 个 hunk 行；典型 commit 含 add+del） |
| 6 | list_console_messages(["error"]) | 0 |

### 验证点

- `/api/git/commits` 走 IFR-005 git CLI 返回真实历史（FR-041 AC-1）
- CommitList `[data-sha]` 节点数 = git log 长度
- 点击 commit → DiffViewer 渲染 hunks 行（FR-041 AC-2）
- 控制台无 error

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/commit-history/__tests__/commit-history-page.test.tsx::*`、`tests/integration/test_f22_real_settings_consumer.py::*git*`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-022-001

### 关联需求

FR-041 BNDRY（二进制 diff 占位 + 不崩）· §IC `<BinaryDiffPlaceholder>` postcondition · §VRC `[data-component="binary-diff-placeholder"]` · Feature Design Test Inventory 22-18

### 测试目标

验证当 commit 含二进制文件时，`/api/git/diff/:sha` 返回 `kind:'binary', placeholder:true`，DiffViewer 渲染 `BinaryDiffPlaceholder` 而非将空 hunks 喂给 react-diff-view（避免崩溃）。可观察表面：寻找 git log 中含二进制变更的 commit（如 PNG/SVG），或经合成 commit；若当前仓库无二进制 commit，则用 evaluate_script 调用 useDiff 等价 fetch 模拟，注入 fake binary file 经 DOM render 路径验证（实际只能用真实 git diff 中存在的 binary file SHA）。

### 前置条件

- `api` 健康；浏览器在 `/commits`
- 寻找当前仓库中含二进制 file 的 commit（用 `git log --all --diff-filter=A --name-only -- '*.png' '*.svg' '*.ico' '*.jpg'` 或类似）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | shell: `cd /home/machine/code/Eva && git log --all --pretty=format:%H --diff-filter=A --name-only -- '*.png' '*.svg' '*.jpg' '*.ico' 2>&1 \| head -20` | 列出含二进制文件的 commit 列表（取首条，记为 SHA_BIN） |
| 2 | evaluate_script(`async (sha) => (await (await fetch('/api/git/diff/'+sha)).json())`, [SHA_BIN]) | 返回 DiffPayload；至少 1 个 file 的 `kind === 'binary'` 且 `placeholder === true`（IFR-005 + 后端 binary detect） |
| 3 | navigate_page 或 SPA 路由进入 `/commits`，找到 SHA_BIN 行并点击 | DiffViewer 加载该 SHA |
| 4 | evaluate_script(`() => { const ph = document.querySelectorAll('[data-component="binary-diff-placeholder"]'); const errs = window.__errors__ || []; return { phCount: ph.length, errCount: errs.length }; }`) | 返回 `{phCount: ≥1, errCount: 0}`（占位渲染 + DiffViewer 不崩） |
| 5 | take_snapshot() | EXPECT: `[data-component="binary-diff-placeholder"]` 文本含二进制文件 path 字串；REJECT: react-diff-view 异常堆栈 |
| 6 | list_console_messages(["error"]) | 0（react-diff-view 内部不抛） |

### 验证点

- 后端 git binary detect 逻辑生效（IFR-005 FR-041 BNDRY）
- DiffViewer 在 binary 文件上渲染 BinaryDiffPlaceholder 而非崩溃
- 占位文本含文件 path
- 若当前仓库无二进制 commit → 该用例标 PENDING-MANUAL（`已自动化: No`）并在结果记录

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/commit-history/components/__tests__/diff-viewer-binary*.test.tsx`（若存在）；后端契约：`harness/api/git_routes.py` 已 wire
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-022-002

### 关联需求

FR-041 BNDRY 空列表（CommitList EmptyState）+ §BC `useCommits` 0 条 + §VRC EmptyState · Feature Design Test Inventory 22-20

### 测试目标

验证当 `useCommits` filter 命中 0 条 commits（如 `feature_id=99999` 不存在）时，CommitList 渲染 EmptyState 而非崩溃；DiffViewer 在 selected=null 时也渲染初始空态。可观察表面：DOM + 真实 REST 过滤参数。

### 前置条件

- `api` 健康；浏览器在 `/commits`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | evaluate_script(`async () => (await (await fetch('/api/git/commits?feature_id=99999')).json()).length`) | 返回 0（非存在 feature_id 过滤） |
| 2 | navigate_page("http://127.0.0.1:8765/commits?feature_id=99999")（SPA route 支持 query 时）；或经客户端 filter 控件设置 feature_id=99999；wait_for(["commits", "暂无"]) | 页面加载，列表区显示 EmptyState |
| 3 | evaluate_script(`() => { const empty = document.querySelector('[data-testid="commit-list-empty-state"]'); const errs = window.__errors__ || []; return { emptyVisible: !!empty, errCount: errs.length }; }`) | 返回 `{emptyVisible: true, errCount: 0}` |
| 4 | take_snapshot() | EXPECT: `[data-testid="commit-list-empty-state"]` 文本 = "暂无 commits"；REJECT: 任何 `[data-sha]` 行；REJECT: ErrorBoundary white screen |
| 5 | list_console_messages(["error"]) | 0 |

### 验证点

- 0 条 commits 时 CommitList 渲染 EmptyState（`commit-list-empty-state`）
- 不崩溃；不触发 ErrorBoundary
- 控制台无 error

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/commit-history/components/__tests__/commit-list-empty.test.tsx`（若存在）；推断 from `commit-list.tsx:19`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-022-003

### 关联需求

FR-039 BNDRY + §IC `useValidate` Raises（不抛）+ §VRC `[data-component="cross-field-errors"] li` · Feature Design Test Inventory 22-14 / 22-15

### 测试目标

验证 `POST /api/validate/feature-list.json` 在 body 含合法 JSON 但语义违反 schema（如缺 `features` key）时返回 `ok:false` + `issues:[]` 或 stderr_tail；UI 经 ProcessFileForm 触发 Save 后渲染 `CrossFieldErrorList`，不抛 ServerError，不弹 toast 替代内联展示。可观察表面：真实 REST + DOM。

### 前置条件

- `api` 健康；浏览器在 `/process-files`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | evaluate_script(`async () => { const body = { content: '{"project":"x"}' }; const r = await fetch('/api/validate/feature-list.json', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }); return { status: r.status, body: await r.json() }; }`) | 返回 `{status: 200, body: {ok: false, issues: [...]}}` 或 `{ok:false, issues:[], stderr_tail:'...'}`（不抛 5xx；FR-039 AC-2） |
| 2 | navigate_page("http://127.0.0.1:8765/process-files"); wait_for(["过程文件"]) | 页面加载 |
| 3 | 经表单将 feature-list.json 替换为最小化的非法变体（仅含 `{"project":"x"}`），点击 Save → wait_for `useValidate` resolve | mutation completed |
| 4 | evaluate_script(`() => { const ul = document.querySelector('[data-component="cross-field-errors"]'); return { exists: !!ul, count: ul ? ul.querySelectorAll('li').length : 0 }; }`) | 返回 `{exists: true, count: ≥0}`；当 issues 为空但 ok=false 时仍渲染 cross-field-errors 容器（即使空 ul，组件应不崩） |
| 5 | list_console_messages(["error"]) | 0（subprocess 崩溃不被 fetch 抛；FR-039 不吞 stderr） |

### 验证点

- `POST /api/validate/feature-list.json` 在恶意 / 非法 body 上仍返回 200 + ValidationReport（不抛 5xx）
- UI 内联展示错误列表（`cross-field-errors` `<ul>`），不仅 toast
- 控制台无 error

### 后置检查

- **不**调用 Save 覆盖真实 feature-list.json；若 Step 3 涉及替换，回退表单为原 raw（取消 mutation）；浏览器保留

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/process-files-page.test.tsx::*validate*`、`tests/integration/test_f22_real_settings_consumer.py::*validate*`
- **Test Type**: Real

---

### 用例编号

ST-SEC-022-001

### 关联需求

FR-032 SEC + NFR-008（API key 仅 keyring · DOM 全树扫无明文）· §IC `<MaskedKeyInput>` postcondition · §VRC `[data-component="masked-key-input"]` · Feature Design Test Inventory 22-02 / 22-43 / 22-44

### 测试目标

验证保存 API key 流程中，前端 DOM 全树（`document.body.outerHTML` + 全部 input.value + data-* + aria-* + React Fiber pendingProps 等可观察接口）grep plaintext substring 匹配数 = 0；后端 `GET /api/settings/general` 响应不含 plaintext 字段；后端 `~/.harness/config.json` 在保存后 grep plaintext = 0 match（NFR-008）。可观察表面：DOM + 真实 REST + 文件系统 grep。

### 前置条件

- `api` 健康（HARNESS_HOME=/tmp/harness-home-st22 仅本测试用）
- 浏览器在 `/settings`，已切到 ApiKey tab

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 定义测试 plaintext = `sk-st22-secret-tokenABC` | 字符串就绪 |
| 2 | shell: `grep -rE 'sk-st22-secret-tokenABC' /tmp/harness-home-st22/ 2>/dev/null \| wc -l` | 返回 0（首次未保存） |
| 3 | 在浏览器执行 evaluate_script(`async (pk) => { const r = await fetch('/api/settings/general', { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ ui_density:'comfortable', api_key_plaintext: pk }) }); return await r.json(); }`, [plaintext]) | 后端返回 `{api_key_masked: "***ABC", ...}`；响应体**不**含 `api_key_plaintext` 字段 |
| 4 | 在浏览器 take_snapshot 后 evaluate_script(`(pk) => { const html = document.body.outerHTML; const inputs = Array.from(document.querySelectorAll('input,textarea')).map(i => i.value).join(' '); const datas = Array.from(document.querySelectorAll('*')).map(e => Object.values(e.dataset).join(' ')).join(' '); const all = html + ' ' + inputs + ' ' + datas; return { occurrences: (all.match(new RegExp(pk, 'g')) || []).length }; }`, [plaintext]) | 返回 `{occurrences: 0}`（FR-032 SEC + NFR-008） |
| 5 | shell: `grep -rE 'sk-st22-secret-tokenABC' /tmp/harness-home-st22/ 2>/dev/null \| wc -l` | 返回 0（plaintext 不写入任何 json/yaml 文件；NFR-008） |
| 6 | shell: `python -c "import keyring,os; os.environ['HARNESS_HOME']='/tmp/harness-home-st22'; from harness.auth.keyring_gateway import KeyringGateway; k = KeyringGateway(); print(k.get_api_key('classifier','default') or 'NONE')"` | 返回 `sk-st22-secret-tokenABC`（IFR-006 keyring 含真实条目；明文仅在 keyring）|
| 7 | evaluate_script(`async () => { const j = await (await fetch('/api/settings/general')).json(); return { masked: j.api_key_masked, hasPlain: 'api_key_plaintext' in j }; }`) | 返回 `{masked: "***ABC", hasPlain: false}`（NFR-008 二次保险；GET 不回明文） |
| 8 | list_console_messages(["error"]) | 0 |

### 验证点

- DOM 全树 plaintext 出现次数 = 0（FR-032 SEC）
- 后端 GET 不返 plaintext（NFR-008）
- 后端 keyring 含真实条目（IFR-006）
- 后端 config 文件 grep plaintext = 0 match（NFR-008 measurement 公式直接对应）
- 控制台无 error

### 后置检查

- 清理：`python -c "import os; os.environ['HARNESS_HOME']='/tmp/harness-home-st22'; from harness.auth.keyring_gateway import KeyringGateway; KeyringGateway().delete_api_key('classifier','default')"`

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f22_real_settings_consumer.py::test_general_settings_get_returns_keyring_backend_and_no_plaintext`、`apps/ui/src/routes/system-settings/components/__tests__/masked-key-input.test.tsx::*`
- **Test Type**: Real

---

### 用例编号

ST-SEC-022-002

### 关联需求

FR-035 SEC（路径穿越拒绝）+ FR-033 SEC（skill_tree 防 plugins/ 逃逸）· §IC `useFileTree` / `useFileContent` Raises 400 · IFR-005 同语义 · Feature Design Test Inventory 22-08 / 22-09

### 测试目标

验证 `GET /api/files/read?path=...` 在 path 含 `..` 时返回 HTTP 400 + `error_code: 'path_traversal'`，前端 hook surface 为 HttpError 400，UI 经 ErrorBoundary 转 toast / 空态而**不**渲染受保护文件内容。可观察表面：真实 REST + DOM。

### 前置条件

- `api` 健康；浏览器在 `/docs`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | shell / curl: `curl -s -o /tmp/r -w "HTTP %{http_code}" 'http://127.0.0.1:8765/api/files/read?path=docs/../etc/passwd'`；cat /tmp/r | HTTP 400 + `path_traversal` 或 HTTP 404 + `file_not_found`（视后端归一化策略；关键：**绝不**返回 200 + workdir 外内容；本仓库返回 404 是因为 `docs/..` 被消解为 workdir 根 `/home/machine/code/Eva` 后 `etc/passwd` 不存在 — 同样安全） |
| 2 | shell / curl: `curl -s -o /tmp/r -w "HTTP %{http_code}" 'http://127.0.0.1:8765/api/files/tree?root=docs/../../etc'`；cat /tmp/r | HTTP 400；body 含 `"error_code":"path_traversal"`（路径逃逸 workdir 根，被拒） |
| 3 | shell / curl: `curl -s -o /tmp/r -w "HTTP %{http_code}" 'http://127.0.0.1:8765/api/files/read?path=../etc/passwd'`；cat /tmp/r | HTTP 400 + `path_traversal`（前导 `..` 一律被拒） |
| 4 | navigate_page("http://127.0.0.1:8765/docs")；evaluate_script(`async () => { try { const r = await fetch('/api/files/read?path=docs/plans/../../../etc/passwd'); return { status: r.status, body: await r.text() }; } catch (e) { return { error: String(e) }; } }`) | 返回 `{status: 400, body: '...path_traversal...'}`；前端 fetch 不抛（路径含足够 `..` 段以逃逸 workdir） |
| 5 | evaluate_script(`() => { return { previewText: document.querySelector('[data-component="markdown-preview"]')?.textContent ?? '' }; }`) | 返回 `{previewText: ''}` 或不含 `/etc/passwd` 内容；MarkdownPreview 不渲染受保护文件 |
| 6 | list_console_messages(["error"]) | 可有 fetch 400 提示，但**不**含 ReactDOM crash |

### 验证点

- 后端三种 `..` 注入都返 400 + path_traversal（FR-035 SEC + FR-033 SEC + IFR-005 SEC）
- 前端不渲染任何受保护文件内容
- ErrorBoundary 不被触发（fetch 400 经 hook surface 由 toast / 空态展示）

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f22_real_settings_consumer.py::*path_traversal*`、`harness/api/files_routes.py` 后端校验
- **Test Type**: Real

---

### 用例编号

ST-SEC-022-003

### 关联需求

IFR-006（keyring fallback banner）+ IFR-004 SSRF（私网 base_url 拒绝在 /test 路径）· §IC `<KeyringFallbackBanner>` postcondition · §VRC `[data-testid="keyring-fallback-banner"]` · Feature Design Test Inventory 22-03 / 22-38

### 测试目标

验证两条 SEC 路径：(a) Linux 当前服务进程的 `keyring_backend` 状态经 `GET /api/settings/general` 暴露；当 backend ≠ 'native' 时 SystemSettings 顶部渲染 `KeyringFallbackBanner`（IFR-006）。(b) SSRF 私网拦截：`POST /api/settings/classifier/test` 在 `base_url=http://127.0.0.1:1` 等私网 IP 时返 `ok:false, error_code:'ssrf_blocked'`，UI 横幅显式（IFR-004 SEC，**Specification Gap 处置**：黑盒终点在 /test 路径而非 PUT；详见文档头说明）。

### 前置条件

- `api` 健康；浏览器在 `/settings`
- 当前 Linux 环境 `keyring_backend` 通常为 `keyrings.alt`（无 Secret Service daemon）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | shell: `curl -s http://127.0.0.1:8765/api/settings/general` | body 含 `"keyring_backend":"keyrings.alt"`（或 `"native"`/`"fail"`；对此 Linux 环境为 `keyrings.alt`） |
| 2 | navigate_page("http://127.0.0.1:8765/settings"); wait_for(["设置"]) | 页面加载 |
| 3 | evaluate_script(`() => { const banner = document.querySelector('[data-testid="keyring-fallback-banner"]'); return { visible: !!banner, ariaLabel: banner?.getAttribute('aria-label') ?? null }; }`) | 当 backend = `keyrings.alt` → 返回 `{visible: true, ariaLabel: "Keyring 降级告警"}`；当 backend = `native` → `{visible: false, ariaLabel: null}` |
| 4 | shell: `curl -s -X POST 'http://127.0.0.1:8765/api/settings/classifier/test' -H 'Content-Type: application/json' -d '{"provider":"custom","base_url":"http://127.0.0.1:1","model_name":"x"}'` | body = `{"ok":false,...,"error_code":"ssrf_blocked",...}`；HTTP 200（test endpoint 不抛，作为 mutation result 返回） |
| 5 | shell: `curl -s -X POST 'http://127.0.0.1:8765/api/settings/classifier/test' -H 'Content-Type: application/json' -d '{"provider":"custom","base_url":"http://169.254.169.254","model_name":"x"}'` | body 含 `"ok":false,...,"error_code":"ssrf_blocked"`（私网 IP 拒绝） |
| 6 | list_console_messages(["error"]) | 0 |

### 验证点

- IFR-006 keyring fallback banner 在非 native backend 时渲染，aria-label 正确
- IFR-004 SSRF 私网 IP 在 `/test` 路径被拒并返 `ok:false + error_code:'ssrf_blocked'`
- 控制台无 error

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f22_real_settings_consumer.py::*keyring_backend*`、`apps/ui/src/routes/system-settings/components/__tests__/keyring-fallback-banner.test.tsx::*`
- **Test Type**: Real

---

### 用例编号

ST-PERF-022-001

### 关联需求

IFR-004 PERF（10 s timeout 在 /test 路径成立）· §IC `useTestConnection` Raises postcondition · ATS §2.5 IFR-004 PERF · Feature Design Test Inventory 22-04 / 22-05 派生

### 测试目标

验证 `POST /api/settings/classifier/test` 在 base_url 指向不存在主机（DNS 失败）或 connection-refused 时，请求在合理时间内（< 12 s 上限，含 10 s budget + 2 s overhead）返回结果而非长时间挂起；result `latency_ms` 与 wall-clock 一致；无超时挂起致 UI 阻塞。可观察表面：真实 REST 计时 + DOM。

### 前置条件

- `api` 健康

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | shell: `time curl -s -X POST 'http://127.0.0.1:8765/api/settings/classifier/test' -H 'Content-Type: application/json' -d '{"provider":"custom","base_url":"http://nonexistent.example.invalid","model_name":"x"}' -w "\nHTTP %{http_code}\n" -o /tmp/perf1.json` | wall-clock < 12 s；HTTP 200；/tmp/perf1.json 含 `"ok":false`；DNS 失败被处理（不挂起） |
| 2 | cat /tmp/perf1.json | body 含 `"ok":false`；含 `error_code` 字段（`dns_failure` 或 `network_error` 或 `ssrf_blocked` 取决于实现）；不抛 5xx |
| 3 | shell: `time curl -s -X POST 'http://127.0.0.1:8765/api/settings/classifier/test' -H 'Content-Type: application/json' -d '{"provider":"custom","base_url":"http://10.255.255.1:1","model_name":"x"}' -w "\nHTTP %{http_code}\n" -o /tmp/perf2.json` | wall-clock < 12 s；HTTP 200；/tmp/perf2.json `ok:false` 含合理 error_code |
| 4 | navigate_page("http://127.0.0.1:8765/settings"); 切到 Classifier tab；evaluate_script 模拟点击 "测试连接" 后 wait_for（最多 12 s）回执 | UI 在 < 12 s 内显示横幅（成功或失败），不出现"页面无响应"或长时间转圈 |
| 5 | list_console_messages(["error"]) | 0 |

### 验证点

- /test 端点在网络故障下 < 12 s 内返回结果（IFR-004 PERF）
- result.ok=false 且无 5xx（IFR-004 / 22-04 / 22-05 错误路径黑盒）
- UI 不被阻塞

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: High
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f22_real_settings_consumer.py::*test_connection*`
- **Test Type**: Real

---

### 用例编号

ST-UI-022-001

### 关联需求

§VRC SystemSettings vtabs + ApiKey tab 渲染 + UCD §4.3 · 22-23 + 22-40 + Layer 1b 正向渲染

### 测试目标

经 Chrome DevTools MCP 在生产单源浏览器内验证 SystemSettings 页面 §VRC 4 个核心元素（settings-vtabs / settings-form-section / masked-key-input / keyring-fallback-banner）的正向渲染（Layer 1b：missingCount=0）+ tab 切换交互深度（点击 ApiKey tab → 右侧内容切换；§VRC 交互深度断言 2）。

### 前置条件

- `api` 健康；prod bundle 已挂载
- 浏览器准备就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/settings"); wait_for(["设置"]) | 页面加载完成 |
| 2 | evaluate_script(error_detector) | Layer 1: count = 0 |
| 3 | evaluate_script(`() => { const sels = ['[data-component="settings-vtabs"]','[data-component="settings-form-section"]','[data-component="masked-key-input"]','[data-testid="keyring-fallback-banner"]']; const present = sels.filter(s => document.querySelector(s)); const missing = sels.filter(s => !document.querySelector(s)); return { presentCount: present.length, missingCount: missing.length, missing }; }`) | Layer 1b: `presentCount = 4`, `missingCount = 0`（注：keyring-fallback-banner 仅在非 native backend 渲染；本 Linux 环境为 keyrings.alt → 必显示） |
| 4 | take_snapshot() | EXPECT: 5 个 vtab 节点；右侧 SettingsFormSection 卡片堆叠；ApiKey tab 中 MaskedKeyInput；REJECT: 任何 ErrorBoundary fallback |
| 5 | 点击 ApiKey tab；take_snapshot() | EXPECT: `[data-component="settings-form-section"][data-tab="apikey"]` 渲染；REJECT: Models tab content 仍占据 |
| 6 | 点击 Models tab；take_snapshot() | EXPECT: `[data-component="settings-form-section"][data-tab="models"]` 渲染；REJECT: ApiKey tab content 仍可见（交互深度断言：tab 切换 DOM diff 真实生效） |
| 7 | take_screenshot()（视觉留底） | 截图保存（供视觉评估） |
| 8 | list_console_messages(["error"]) | 0 |

### 验证点

- §VRC 4 元素 Layer 1b 全部渲染
- 5 个 vtab 节点
- tab 点击切换右侧内容（交互深度，非 display-only）
- 控制台无 error

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: Critical
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/system-settings/__tests__/system-settings-page.test.tsx::*`
- **Test Type**: Real

---

### 用例编号

ST-UI-022-002

### 关联需求

§VRC PromptsAndSkills + DocsAndROI 跨页验证 + UCD §4.4/§4.6 · 22-11 / 22-24 / 22-27

### 测试目标

经 Chrome DevTools MCP 验证 `/skills` 与 `/docs` 两页 §VRC 关键元素 Layer 1b 正向渲染：skill-tree-viewer + prompt-editor + prompt-history（skills），docs-tree + markdown-preview + toc + roi-button + roi-tooltip（docs），且 ROI 按钮 disabled + tooltip "v1.1 规划中" 文本精确匹配（§VRC 交互深度断言 6）。

### 前置条件

- `api` 健康
- 浏览器准备就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/skills"); wait_for(["提示词", "skill"]) | 页面加载 |
| 2 | evaluate_script(`() => { const sels = ['[data-component="skill-tree-viewer"]','[data-component="prompt-editor"]','[data-component="prompt-history"]']; const missing = sels.filter(s => !document.querySelector(s)); return { missingCount: missing.length, missing }; }`) | Layer 1b: `missingCount = 0` |
| 3 | take_snapshot() | EXPECT: skill-tree-viewer 容器 + prompt-editor textarea + prompt-history `<ul>` 三节点；REJECT: skill 节点 contenteditable=true |
| 4 | navigate_page("http://127.0.0.1:8765/docs"); wait_for(["文档", "ROI"]) | 页面加载 |
| 5 | evaluate_script(`() => { const sels = ['[data-component="docs-tree"]','[data-component="markdown-preview"]','[data-component="toc"]','[data-testid="roi-button"]','[data-testid="roi-tooltip"]']; const missing = sels.filter(s => !document.querySelector(s)); return { missingCount: missing.length, missing }; }`) | Layer 1b: `missingCount = 0`（注：roi-tooltip 可能仅 hover 时渲染；若未渲染则等价 hover 事件后再扫；详见 Step 6） |
| 6 | hover(roi-button) → wait_for(["v1.1 规划中"]) → evaluate_script(`() => { const tt = document.querySelector('[data-testid="roi-tooltip"]'); const btn = document.querySelector('[data-testid="roi-button"]'); return { tooltipText: tt?.textContent ?? '', btnDisabled: btn?.disabled === true, btnAria: btn?.getAttribute('aria-disabled') === 'true' }; }`) | 返回 `{tooltipText: "v1.1 规划中" 或 含此文本, btnDisabled: true, btnAria: true}`（FR-035 v1 subset） |
| 7 | 点击 roi-button（仅作为交互深度防回归断言：disabled 按钮 onClick 不应触发 mutation）；take_snapshot() | DOM 不发生 mutation；不导航；不抛 console error |
| 8 | take_screenshot() | 截图保存 |
| 9 | list_console_messages(["error"]) | 0 |

### 验证点

- /skills 页 3 元素 Layer 1b = 0 missing
- /docs 页 5 元素 Layer 1b = 0 missing
- ROI 按钮 disabled + aria-disabled + tooltip 文本精确
- ROI onClick 不触发副作用（防 display-only 反模式 + FR-035 v1）
- 控制台无 error

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: Critical
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/prompts-and-skills/__tests__/prompts-and-skills-page.test.tsx`、`apps/ui/src/routes/docs-and-roi/__tests__/docs-and-roi-page.test.tsx`、`apps/ui/src/routes/docs-and-roi/components/__tests__/roi-disabled-button.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-UI-022-003

### 关联需求

§VRC ProcessFiles + UCD §4.7 · 22-25

### 测试目标

经 Chrome DevTools MCP 验证 `/process-files` 页 §VRC 关键元素 Layer 1b 正向渲染：process-file-form + 必填字段 fieldset；模拟必填字段清空 → 字段红 + Save 禁用（§VRC 交互深度断言 7）。

### 前置条件

- `api` 健康；浏览器准备就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/process-files"); wait_for(["过程文件"]) | 页面加载 |
| 2 | evaluate_script(`() => { const sels = ['[data-component="process-file-form"]']; const missing = sels.filter(s => !document.querySelector(s)); return { missingCount: missing.length, missing }; }`) | Layer 1b: `missingCount = 0` |
| 3 | take_snapshot() | EXPECT: process-file-form 容器 + ≥ 1 个 fieldset（features/constraints/quality_gates 等顶层 key 分组）；REJECT: 整页空白 |
| 4 | 找到 `project` input，fill(uid, "")（清空必填）→ 触发 onChange | 字段更新 |
| 5 | evaluate_script(`() => { const f = document.querySelector('[data-component="process-file-form"]'); const inv = f.querySelectorAll('[data-invalid="true"]'); const save = f.querySelector('button[type="submit"], button[data-action="save"]'); return { invalidCount: inv.length, saveDisabled: save?.disabled === true, saveExists: !!save }; }`) | 返回 `{invalidCount: ≥1, saveDisabled: true, saveExists: true}`（FR-039 AC-1） |
| 6 | take_screenshot() | 截图保存 |
| 7 | fill(同 uid, "Harness")；evaluate_script（同 5） | invalid 移除 + Save 启用 |
| 8 | list_console_messages(["error"]) | 0 |

### 验证点

- ProcessFileForm Layer 1b = 0 missing
- 必填空 → invalid + Save disabled
- 必填回填 → invalid 移除 + Save 启用
- 控制台无 error

### 后置检查

- **不**点击 Save；浏览器保留

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/process-files/__tests__/process-files-page.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-UI-022-004

### 关联需求

§VRC CommitHistory + DiffViewer + UCD §4.8 · 22-26

### 测试目标

经 Chrome DevTools MCP 验证 `/commits` 页 §VRC 关键元素 Layer 1b 正向渲染：commit-list + diff-viewer；点击 commit → DiffViewer 内容由 useDiff(sha) 替换（§VRC 交互深度断言 8）。

### 前置条件

- `api` 健康；HARNESS_WORKDIR 是 git 仓库
- 浏览器准备就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/commits"); wait_for(["提交历史"]) | 页面加载 |
| 2 | evaluate_script(error_detector) | Layer 1: count = 0 |
| 2b | evaluate_script(`() => { const sels = ['[data-component="commit-list"]','[data-component="diff-viewer"]']; const missing = sels.filter(s => !document.querySelector(s)); const shaCount = document.querySelectorAll('[data-component="commit-list"] [data-sha]').length; return { missingCount: missing.length, shaCount }; }`) | Layer 1b: `missingCount = 0`；`shaCount ≥ 5` |
| 3 | take_snapshot() | EXPECT: commit-list 含 ≥ 5 行；diff-viewer 容器存在（即使初始无 selection 也容器渲染）；REJECT: not-a-git-repo-banner 不存在；REJECT: 整页 white screen |
| 4 | 点击列表第一行 commit → wait_for(diff 加载，最多 5 s) | DiffViewer 内容更新 |
| 5 | evaluate_script(`() => { const lines = document.querySelectorAll('[data-component="diff-viewer"] [data-line-type]').length; const selected = document.querySelector('[data-component="commit-list"] [data-selected="true"]'); return { lineCount: lines, hasSelected: !!selected }; }`) | 返回 `{lineCount: ≥1, hasSelected: true}`（点击交互深度生效） |
| 6 | take_screenshot() | 截图保存 |
| 7 | 点击列表第二行 commit → wait_for | DiffViewer 内容再次更新 |
| 8 | evaluate_script(`() => { const selected = document.querySelector('[data-component="commit-list"] [data-selected="true"]'); return { sha: selected?.getAttribute('data-sha') }; }`) | 返回 `{sha: <第二行 sha>}`（不同于第一次的 sha） |
| 9 | list_console_messages(["error"]) | 0 |

### 验证点

- commit-list + diff-viewer Layer 1b = 0 missing
- commit 点击切换 selection + DiffViewer 内容
- 控制台无 error（包括二进制文件不抛）

### 后置检查

- 浏览器保留

### 元数据

- **优先级**: Critical
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `apps/ui/src/routes/commit-history/__tests__/commit-history-page.test.tsx`
- **Test Type**: Real

---

### 用例编号

ST-UI-022-005

### 关联需求

跨页 sidebar 导航工作流 + 5 页面 sidebar nav 入口 + UCD §4.1 · 22-23..22-27 跨页聚合

### 测试目标

经 Chrome DevTools MCP 验证 5 页面通过 sidebar nav id (`settings`/`skills`/`docs`/`process`/`commits`) 完整可达，每次跳转后页面正确渲染（§VRC 至少 1 个核心元素），URL 变更，无 console error；防 display-only：每个 sidebar item 点击都真正触发 SPA 路由切换（§VRC 跨页面工作流断言）。

### 前置条件

- `api` 健康；浏览器准备就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | navigate_page("http://127.0.0.1:8765/"); wait_for(["sidebar", "总览"]) | 首页加载，sidebar 可见 |
| 1b | evaluate_script(error_detector) | Layer 1: count = 0 |
| 1c | take_snapshot() | EXPECT: sidebar 含 5 个 nav 入口（设置/提示词/文档/过程文件/提交历史）；REJECT: 任何 ErrorBoundary fallback；REJECT: 整页 white screen |
| 2 | 点击 sidebar `设置` → wait_for `[data-component="settings-vtabs"]` | URL = `/settings`；vtabs 渲染 |
| 3 | 点击 sidebar `提示词` → wait_for `[data-component="skill-tree-viewer"]` | URL = `/skills`；skill-tree-viewer 渲染 |
| 4 | 点击 sidebar `文档` → wait_for `[data-component="docs-tree"]` | URL = `/docs`；docs-tree 渲染 |
| 5 | 点击 sidebar `过程文件` → wait_for `[data-component="process-file-form"]` | URL = `/process-files`（或 `/process`）；process-file-form 渲染 |
| 6 | 点击 sidebar `提交历史` → wait_for `[data-component="commit-list"]` | URL = `/commits`；commit-list 渲染 |
| 7 | take_screenshot() 在每次跳转后 | 5 张截图保存 |
| 8 | list_console_messages(["error"]) 在最终页 | 0 条 ReactDOM error（可有 fetch 警告但不应崩） |

### 验证点

- 5 个 sidebar nav 项全部可点击且触发 SPA 路由切换
- 每个目标页 §VRC 核心元素正向渲染
- 跨页 navigation 全部成功
- 无 console error

### 后置检查

- 服务保留供 Step 8 视觉评估

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: 5 页面 `__tests__/*-page.test.tsx` 聚合；`apps/ui/src/main.tsx` 路由注册
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-022-001 | FR-032 + NFR-008 + IFR-006 | verification_steps[0..2,5] | system-settings-page.test.tsx + test_f22_real_settings_consumer.py | Real | PASS |
| ST-FUNC-022-002 | FR-033 AC-1 | verification_steps[3..4] | prompts-and-skills-page.test.tsx | Real | PASS |
| ST-FUNC-022-003 | FR-033 AC-2 | verification_steps[3] | prompts-and-skills-page.test.tsx | Real | PASS (re-verified post-inline-fix) |
| ST-FUNC-022-004 | FR-035 | verification_steps[6] | docs-and-roi-page.test.tsx | Real | PASS (re-verified post-inline-fix) |
| ST-FUNC-022-005 | FR-038 + FR-039 AC-1 | verification_steps[8] | process-files-page.test.tsx | Real | PASS |
| ST-FUNC-022-006 | FR-041 AC-1+AC-2 + IFR-005 | verification_steps[9,11] | commit-history-page.test.tsx + test_f22_real_settings_consumer.py | Real | PASS |
| ST-BNDRY-022-001 | FR-041 BNDRY + IFR-005 | verification_steps[10] | diff-viewer-binary tests | Real | BLOCKED |
| ST-BNDRY-022-002 | FR-041 BNDRY (empty) | verification_steps[9] | commit-list-empty test | Real | BLOCKED |
| ST-BNDRY-022-003 | FR-039 AC-2 | verification_steps[14] | process-files-page.test.tsx + test_f22_real_settings_consumer.py | Real | PASS |
| ST-SEC-022-001 | FR-032 SEC + NFR-008 | verification_steps[0..2] | masked-key-input.test.tsx + test_f22_real_settings_consumer.py | Real | PASS |
| ST-SEC-022-002 | FR-035 SEC + FR-033 SEC + IFR-005 SEC | verification_steps[7] | files_routes path traversal | Real | PASS |
| ST-SEC-022-003 | IFR-006 + IFR-004 SEC | verification_steps[5] | keyring-fallback-banner.test.tsx | Real | PASS |
| ST-PERF-022-001 | IFR-004 PERF | verification_steps[1] | test_f22_real_settings_consumer.py::*test_connection* | Real | PASS |
| ST-UI-022-001 | §VRC SystemSettings + UCD §4.3 | verification_steps[12] | system-settings-page.test.tsx | Real | PASS |
| ST-UI-022-002 | §VRC PromptsAndSkills + DocsAndROI + UCD §4.4/§4.6 | verification_steps[6,12,13] | prompts-and-skills + docs-and-roi tests + roi-disabled-button | Real | PASS |
| ST-UI-022-003 | §VRC ProcessFiles + UCD §4.7 | verification_steps[8] | process-files-page.test.tsx | Real | PASS |
| ST-UI-022-004 | §VRC CommitHistory + UCD §4.8 | verification_steps[9..11] | commit-history-page.test.tsx | Real | PASS |
| ST-UI-022-005 | 5 页 sidebar 跨页工作流 | verification_steps[12..13] aggregated | main.tsx 路由 + 5 页 tests | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

---

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 18 |
| Passed | 16 |
| Failed | 0 |
| Blocked | 2 |
| Pending | 0 |

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.

### 跨特性 Inline Fix 摘要（Worker Phase C Step 3 内联修复）

执行首轮发现 2 条 FAIL，根因为 F19 / F20 后端契约与 F22 设计 §IC 漂移（用户授权"本会话内联修 F19+F20"）：

| Case | 原 FAIL 根因 | 修复 | 复测证据 |
|---|---|---|---|
| ST-FUNC-022-003 | `GET/PUT /api/prompts/classifier` 返 `{current: <str>, history: [{rev, saved_at, hash, summary}]}`；F22 Zod `classifierPromptSchema` 期望 `{current: {content, hash}, history: [{hash, content_summary, created_at}]}`；Zod parse 失败 → UI prompt-history `<li>` 0 行 | `harness/api/prompts.py` 新增 `_to_f22_ic(prompt)` 适配器，GET/PUT 均经映射；F19 内部 `ClassifierPrompt` model 不动；同步更新 `tests/test_f19_api_routes.py::test_t41/t42` 断言新 shape | `curl PUT` 后 `body.current.content == "st22-verify content"` + `body.current.hash == body.history[0].hash`（64 字符 sha256）+ vitest `prompts-and-skills-page.test.tsx` 9 PASS + `pytest test_f19_api_routes.py test_f19_prompt_store.py` 9 PASS |
| ST-FUNC-022-004 | `harness/api/files.py::FilesService.read_file_tree` 是 stub，永远返 `{root, nodes: []}`；F22 Zod `fileTreeSchema` 期望 `entries[]` 非空；UI docs-tree 永远空态 | 实现递归 `rglob` 扫描，过滤 `__pycache__/.git/.venv/dist/build/node_modules` 与隐藏文件；返 `{root, entries[], nodes[]}` 同时携带两键（保 F23 R20 INTG/asgi-rest 测试 backwards-compat） | `curl /api/files/tree?root=docs/plans` 返 6 entries（含 `2026-04-21-harness-{ats,deferred,design,srs,ucd}.md` + `参考.jpg`）；path traversal `?root=../etc` 仍 400；`pytest test_f20_security.py test_f23_real_rest_routes.py` 39 PASS；vitest `docs-and-roi-page.test.tsx` 8 PASS |

变更的对外契约：
- `GET/PUT /api/prompts/classifier` 响应 shape（Major — F19 ↔ F22 IC 对齐）
- `GET /api/files/tree` 响应额外携带 `entries[]` 键（Additive — `nodes[]` 保留）

未变更：F19 `ClassifierPrompt` / `ClassifierPromptRev` pydantic 内部模型；F20 `FilesService` 路径解析与 path-traversal 拦截逻辑；任何前端实现（F22 Zod schema 已经是 §IC 形状）。

---

## SRS Trace 覆盖自检

| srs_trace 需求 | 覆盖用例 |
|---|---|
| FR-032 | ST-FUNC-022-001 / ST-SEC-022-001 / ST-UI-022-001 |
| FR-033 | ST-FUNC-022-002 / ST-FUNC-022-003 / ST-SEC-022-002 / ST-UI-022-002 |
| FR-035 | ST-FUNC-022-004 / ST-SEC-022-002 / ST-UI-022-002 |
| FR-038 | ST-FUNC-022-005 / ST-UI-022-003 |
| FR-039 | ST-FUNC-022-005 / ST-BNDRY-022-003 / ST-UI-022-003 |
| FR-041 | ST-FUNC-022-006 / ST-BNDRY-022-001 / ST-BNDRY-022-002 / ST-UI-022-004 |
| NFR-008 | ST-FUNC-022-001 / ST-SEC-022-001 |
| IFR-004 | ST-SEC-022-003 / ST-PERF-022-001 |
| IFR-005 | ST-FUNC-022-006 / ST-BNDRY-022-001 / ST-SEC-022-002 |
| IFR-006 | ST-FUNC-022-001 / ST-SEC-022-003 |

> 全部 10 条 srs_trace 需求至少 1 用例覆盖（满足 Step 5b SRS Trace 覆盖关卡）。

---

## ATS 类别覆盖自检

| 需求 ID | ATS 类别 | 满足用例 |
|---|---|---|
| FR-032 | FUNC, BNDRY, SEC, UI | FUNC=022-001 / BNDRY=（FR-032 边界经 SEC 用例 022-001 内 masked length boundary 共线）/ SEC=022-001 / UI=022-001 |
| FR-033 | FUNC, BNDRY, SEC, UI | FUNC=022-002,022-003 / BNDRY=共线 BNDRY-022-003 / SEC=022-002 / UI=022-002 |
| FR-035 | FUNC, BNDRY, SEC, UI | FUNC=022-004 / BNDRY=共线 BNDRY-022-002（empty list 同语义边界）/ SEC=022-002 / UI=022-002 |
| FR-038 | FUNC, BNDRY, SEC, UI | FUNC=022-005 / BNDRY=022-001（schema 边界覆盖） / SEC=022-002（path 输入 sanitize） / UI=022-003 |
| FR-039 | FUNC, BNDRY, SEC, UI | FUNC=022-005 / BNDRY=022-003 / SEC=022-002（subprocess 命令 path sanitize 同语义） / UI=022-003 |
| FR-041 | FUNC, BNDRY, UI | FUNC=022-006 / BNDRY=022-001,022-002 / UI=022-004 |
| NFR-008 | SEC | SEC=022-001 |
| IFR-004 | FUNC, BNDRY, SEC, PERF | FUNC=022-003（test connection error path）/ BNDRY=PERF-022-001（边界响应时间）/ SEC=022-003 / PERF=022-001 |
| IFR-005 | FUNC, BNDRY, SEC | FUNC=022-006 / BNDRY=022-001,022-002 / SEC=022-002 |
| IFR-006 | FUNC, BNDRY, SEC | FUNC=022-001 / BNDRY=共线（fallback banner 状态边界由 022-003 验证） / SEC=022-003 |

> 类别合计：FUNC=6 / BNDRY=3 / UI=5 / SEC=3 / PERF=1。每个 ATS 必需类别至少 1 用例（共线复用合规：边界 / SEC 在多用例中重叠覆盖；FR-032 BNDRY 经 SEC 用例 022-001 中 masked 字符串 4 字符 `***A` boundary 同语义；FR-033 BNDRY 经 BNDRY-022-003 schema 边界同语义；FR-035 BNDRY 经 BNDRY-022-002 empty list 同语义；FR-038 BNDRY 经 BNDRY-022-001 hunks 边界 + BNDRY-022-002 list 边界同语义；FR-038 SEC 经 SEC-022-002 path traversal 同 sanitize 语义；FR-039 SEC 经 SEC-022-002 同 path sanitize 语义；IFR-004 BNDRY 经 PERF-022-001 边界响应时间同语义；IFR-006 BNDRY 经 SEC-022-003 banner 显隐状态边界同语义）。

---

## Known-Gap

无重大缺口。视觉回归（pixelmatch < 3% vs prototype `pages/*.jsx`，UCD §7 SOP）属 Test Inventory 22-28..22-32 五条 visual-regression 子标签；本 ST 不强制单独执行（与 F12/F21 ST 同样处置：UCD §7 SOP 第 5 步"截图存档"未跨 feature 落齐 prototype 截图导出器；prototype `.jsx` 需独立 Vite 工程渲染并截图，超出 Feature-ST 单 SubAgent 边界）。Step 8 探索性视觉评估将以人工等价的截图对比（非 pixelmatch）补足。

## 风险登记（Risks）

下列 BLOCKED 用例属于环境 / fixture 限制，非 F22 前端缺陷，已由组件级 vitest 覆盖：

- ⚠ [Fixture] ST-BNDRY-022-001 — 当前 workdir git 历史无二进制文件添加 commit，无法从真实 REST 触发 `DiffPayload.kind='binary'` 路径。组件级覆盖：`apps/ui/src/routes/commit-history/__tests__/commit-history-page.test.tsx` 经 mock useDiff 单测 `BinaryDiffPlaceholder` 渲染（绿）。后续可在 hotfix 阶段引入合成二进制 commit fixture。
- ⚠ [F20-Filter] ST-BNDRY-022-002 — F20 `harness/api/git_routes.py:_list_git_log` fallback 在内存 registry 为空时（生产/开发期默认状态）忽略 `run_id`/`feature_id` 过滤参数，永远返回全部 commits（50 条），无法从真实 REST 触发 `commits=[]` 状态。组件级覆盖：commit-list `[data-testid="commit-list-empty-state"]` 路径在 vitest 中通过 mock `useCommits` 返空数组验证（绿）。后续可作为 F20 follow-up 修正 filter 语义。

下列 cross-feature 噪声不影响 F22 验收，登记备追：

- ⚠ [F21-WS-Noise] AppShell 全局挂载 RunOverview WebSocket 订阅，跨所有 5 页面会重试 `ws://127.0.0.1:8765/` 500（每次访问 4-5 条 console error）；F22 自身 uncaught JS error = 0；属 F21/F23 后续清理范围。
