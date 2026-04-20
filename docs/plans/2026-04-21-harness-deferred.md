# Harness — 延期需求待办清单（Deferred Requirements Backlog）

**日期（Date）**: 2026-04-21
**来源 SRS（Source SRS）**: docs/plans/2026-04-21-harness-srs.md
**状态（Status）**: Active
**轨道（Track）**: Lite
**目标批次（Target Wave）**: v1.1

## 目的（Purpose）

本文档跟踪在 Harness SRS 阐释过程中识别、但为控制 v1 范围而延期到 v1.1 的需求。每条记录完整保留其 EARS 语句与验收准则（Acceptance Criteria），以便通过 `long-task-increment` skill 在 v1 冻结后无缝接入。

v1 审阅方（reviewer）与用户对以下 4 条 FR 达成一致：v1 不实现，保留占位 ID 不让后续号段错位；对应 EXC-013 已登记于 SRS §8。下游 ROI 分析链（FR-036/037）在 v1 阶段作为"知道缺失但可接受"的裁剪，不阻塞 v1 Go verdict。

## 延期需求清单（Deferred Requirements）

### DFR-001: Classifier Prompt 版本历史与 Diff 视图 (from FR-033b)

**原始 ID（Original ID）**: FR-033b
**优先级（Priority）**: Should（v1.1）
**EARS**: When the Harness User edits `classifier/system_prompt.md` in the PromptsAndSkills UI, the system shall preserve full version history and present a side-by-side diff viewer to compare any two historical revisions with inline change highlighting.
**验收准则（Acceptance Criteria）**:
- Given 用户对 classifier prompt 做了 ≥ 2 次编辑保存, when 打开 "History" 面板, then 列出所有历史版本（时间戳 + 摘要）
- Given 用户选择两个历史版本, when 点击 "Compare", then 展示 side-by-side diff（增删行高亮）
- Given 用户点击某历史版本的 "Revert", when 确认, then 将当前 prompt 回滚为该版本并记一条新版本

**延期原因（Deferral Reason）**: v1 MVP 只提供 classifier prompt 基础编辑（FR-033 内已含"带版本历史（diff 列表）"的初版），完整的 diff viewer + revert 工作流属于锦上添花，不进入 v1 关键路径。
**对本轮的依赖（Dependencies on Current Round）**: FR-033（PromptsAndSkills 界面）— 需先有基础编辑能力。
**建议批次（Suggested Wave）**: v1.1（第一波增量）
**再入口提示（Re-entry Hint）**: 当用户报告"无法对比 prompt 修改历史"或"误改 prompt 无法回退"成为高频痛点，重新纳入。
**v1 影响（v1 Impact）**: 用户仍可编辑 classifier prompt；历史记录在 FR-033 v1 实现中保留为追加列表，但无对比 / 回滚交互。
**状态（Status）**: Pending

---

### DFR-002: ROI 面板入口 (from FR-035b)

**原始 ID（Original ID）**: FR-035b
**优先级（Priority）**: Should（v1.1）
**EARS**: When the Harness User selects a document section in the DocsAndROI UI, the system shall expose a "Run ROI Analysis" button that dispatches a dedicated side-ticket and renders the resulting ROI panel (consumer list + verdict).
**验收准则（Acceptance Criteria）**:
- Given 用户在 DocsAndROI 中选中 SRS §4.1 的某条 FR, when 点击 "Run ROI Analysis", then Harness 启动 side-ticket（执行 FR-036 的分析逻辑）
- Given side-ticket 完成, when UI 收到结果, then ROI 面板展示 consumer skill 列表 + `roi_verdict`
- Given 用户对同一节再次点击 "Run ROI Analysis", when 缓存命中（FR-037）, then 即时展示不再 dispatch 新 ticket

**延期原因（Deferral Reason）**: v1 的 DocsAndROI（FR-035）仅实现"文件树 + Markdown 预览"，ROI 按钮在 UI 层面可见但不可点击（grayed out）。完整交互依赖 FR-036 与 FR-037 两条后端 FR，三者一并延后保持一致性。
**对本轮的依赖（Dependencies on Current Round）**: FR-035（DocsAndROI 界面 v1 的文件树 + Markdown 预览）。
**建议批次（Suggested Wave）**: v1.1（与 DFR-003、DFR-004 同批次发布，否则按钮点不到后端）
**再入口提示（Re-entry Hint）**: DFR-003（FR-036 后端分析链）设计评审通过后立即启动。
**v1 影响（v1 Impact）**: DocsAndROI 可浏览文档但无 ROI 分析入口；SRS §4.1 FR-035 AC 中已声明 ROI 按钮点击效果延后 v1.1。
**状态（Status）**: Pending

---

### DFR-003: ROI 下游 skill 消费链分析 (from FR-036)

**原始 ID（Original ID）**: FR-036
**优先级（Priority）**: Should（v1.1）
**EARS**: When the Harness User triggers ROI analysis on a selected document section via the DocsAndROI UI, the system shall identify every downstream `longtaskforagent` skill step that reads/consumes that section (e.g., `long-task-design Step 3`, `long-task-ats Step 2`, `long-task-feature-design Step 4`, `long-task-tdd Red Step`, `long-task-feature-st Case 1-3`) and surface the consumer list with referenced line ranges.
**验收准则（Acceptance Criteria）**:
- Given SRS §4.1 FR-001, when 分析完成, then 列出 ≥ 1 consumer skill+step（否则标记为 orphan）
- Given 文档某节未被任何 skill 消费, when 分析, then `roi_verdict: orphan` 并给出 candidate_for_trim 建议
- Given consumer skill 引用了该节具体行号, when 分析, then ROI 面板列出 `skill + step + 引用行号范围`

**延期原因（Deferral Reason）**: 需要一个稳定的 "skill 内容静态分析器"（遍历 `plugins/longtaskforagent/skills/**/SKILL.md` 抽取对文档章节的引用），v1 没有余力构建。属于优化类功能：有它更好，没它 v1 也能跑完 full run。
**对本轮的依赖（Dependencies on Current Round）**: 无硬依赖（但需访问 v1 已 bundle 的 `plugins/longtaskforagent/` 目录；FR-045 保证了 plugin 路径稳定）。
**建议批次（Suggested Wave）**: v1.1（DFR-004 依赖本项，应一同规划）
**再入口提示（Re-entry Hint）**: 当文档体量增长到 3-5 份 SRS（含多轮 increment）后，"哪些章节仍被 skill 消费、哪些可裁剪" 成为刚需时重新启动。
**v1 影响（v1 Impact）**: 文档可能存在未被任何 skill 消费的"孤儿"章节，v1 无自动识别机制；由用户人工 review。属于可接受的裁剪。
**状态（Status）**: Pending

---

### DFR-004: ROI 缓存（混合失效策略）(from FR-037)

**原始 ID（Original ID）**: FR-037
**优先级（Priority）**: Should（v1.1）
**EARS**: The system shall execute ROI analysis as a dedicated side-ticket (独立 Claude 会话 + 专用 system prompt 用于识别 skill 消费者 + 引用章节 + 给出 `roi_verdict: kept | candidate_for_trim | orphan`) and cache results in `docs/roi/<doc>-roi.json`. Cache invalidation shall follow a hybrid policy: (a) a file watcher marks cache entries as `outdated` when source documents (SRS / design / ATS / UCD / feature-list.json) change; (b) actual recomputation only triggers when the user clicks "Refresh" in the ROI panel.
**验收准则（Acceptance Criteria）**:
- Given 首次对 SRS 触发 ROI 分析, when side-ticket 完成, then 生成 `docs/roi/srs-roi.json` 文件
- Given 二次打开同一节, when 缓存存在且未标记 outdated, then 即时展示不 spawn 新 ticket
- Given 用户修改了 SRS 源文件, when file watcher 检测到变更, then 对应缓存条目标记为 `outdated`（UI 展示黄色徽章）
- Given 缓存标记为 outdated, when 用户点击 "Refresh", then 才重新 dispatch side-ticket 重算；否则继续展示旧结果

**延期原因（Deferral Reason）**: FR-036 是前置依赖（没有分析链就谈不上缓存）。且缓存失效策略（混合模式）在 v1 MVP 阶段没有高频编辑文档的场景去验证是否合理，不如延到 v1.1 配合 FR-036 一起实测调整。
**对本轮的依赖（Dependencies on Current Round）**: **DFR-003（FR-036）**— 硬依赖：无分析链则无可缓存的结果。
**建议批次（Suggested Wave）**: v1.1（必须与 DFR-003 同批次或之后，顺序：FR-036 → FR-037）
**再入口提示（Re-entry Hint）**: DFR-003 设计落地 + 用户报告"每次重复计算 ROI 成本高"时启动。
**v1 影响（v1 Impact）**: 无（因 FR-036 本身在 v1 未实现，缓存层面无意义）。
**状态（Status）**: Pending

---

## 依赖关系图（Dependency Graph）

```
DFR-001 (FR-033b) ── 独立，依赖 v1 的 FR-033 基础编辑
DFR-002 (FR-035b) ── 依赖 DFR-003（ROI 按钮点击需后端支撑）
DFR-003 (FR-036)  ── 独立后端分析链
DFR-004 (FR-037)  ── 硬依赖 DFR-003（缓存的是 DFR-003 的产出）
```

v1.1 推荐发布顺序：**DFR-003 → DFR-004 → DFR-002 → DFR-001**。其中 DFR-003/004/002 为一组（ROI 完整链路），DFR-001 可独立发布。

## 裁剪范围已接受（Accepted Trim Scope for v1）

以下 v1 能力裁剪已通过 user + reviewer 双方确认：
1. **v1 无 classifier prompt 历史对比/回滚交互** — 仅保留追加式历史列表（FR-033 v1 AC 范围）。
2. **v1 无 ROI 分析入口与后端链路** — DocsAndROI 仅作文件树 + Markdown 预览（FR-035 v1 AC 已明示）。
3. **v1 文档无孤儿章节自动检测** — 由用户人工 review；不阻塞 v1 Go verdict。
4. **v1 无 ROI 缓存层** — 因无 ROI 计算，无需缓存；v1.1 一次性引入分析 + 缓存。

## 纳入日志（Incorporation Log）

| 日期 | 批次 | 纳入项 | 剔除项 | 剩余 |
|------|------|--------|--------|------|
| 2026-04-21 | v1 冻结 | — | — | DFR-001, DFR-002, DFR-003, DFR-004 (4 items pending) |

## 备注（Notes）

- DFR-002/003/004 形成一条完整的 "文档 ROI 分析链"；v1.1 规划时应作为一个 epic 处理，避免拆分导致用户体验断裂。
- DFR-001 与 ROI 链无耦合，可作为 v1.1 的独立小增量单独发布。
- 若 v1 完成后 6 个月内无用户反馈 ROI 链需求，考虑将 DFR-002/003/004 降级为 Could 或 Dropped。
- 再入口通道：当 `increment-request.json` 出现时，`long-task-increment` skill 会读取本文档作为延期来源之一。
