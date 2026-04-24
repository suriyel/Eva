# 验收测试策略: Harness

**SRS 参考**: docs/plans/2026-04-21-harness-srs.md
**设计文档参考**: docs/plans/2026-04-21-harness-design.md
**UCD 参考**: docs/plans/2026-04-21-harness-ucd.md
**日期**: 2026-04-21（Wave 2 feature 重包装 feature id 重映射：2026-04-24）
**状态**: Approved（Reviewer Round 1 CONDITIONAL_PASS → 7 项修复 → Round 2 PASS；Wave 2 refactor-only remap 免重跑）
**模板版本**: 1.0
**Scale**: 中型（48 active FR + 17 NFR + 7 IFR；10 features：F01/F02/F10/F12/F17 保留 + F18–F22 新）→ 完整 ATS 五节

---

## 1. 测试范围与策略概览

### 1.1 测试目标

本 ATS 保证 Harness v1 的所有 active SRS 需求（48 FR + 17 NFR + 7 IFR）在 Worker 的 feature-st 阶段与 System ST 阶段都有充分、可审计的验收测试覆盖。**延至 v1.1 的 FR-033b / FR-035b / FR-036 / FR-037 四条不在本策略范围**，它们由 `long-task-increment` skill 在后续批次纳入。

### 1.2 质量目标

- 每个 active FR 至少覆盖 FUNC + BNDRY 两类
- 处理用户输入 / 认证 / 外部数据的 FR 必须覆盖 SEC
- `ui:true` 的特性（F12, F21, F22）必须覆盖 UI
- 每条 NFR 带可度量阈值 + 指定工具 + 量化 pass 标准
- 跨特性集成路径必须在 System ST 阶段验证（含 happy / error / 一致性）
- Feature-ST 测试用例类别由本 ATS §2 的 `必须类别` 列决定，不可临时增删

### 1.3 测试级别定义

| 级别 | 描述 | 执行阶段 |
|---|---|---|
| 单元测试 | TDD Red-Green-Refactor | Worker (long-task-tdd) |
| 特性验收测试 | 黑盒 ST 测试用例（ISO/IEC/IEEE 29119）| Worker (long-task-feature-st) |
| 系统测试 | 跨特性集成 + NFR 端到端验证 | ST (long-task-st) |
| 分发冒烟 | 三平台干净 VM 启动 | ST 末期 |

---

## 2. 需求→验收场景映射

> 覆盖 48 active FR + 17 NFR + 7 IFR = 72 行。类别 = FUNC / BNDRY / SEC / PERF / UI；优先级 = Critical(Must) / High(Should) / Medium(Could)。自动化可行性默认 `Auto`；`Manual` 才显式标注。

### 2.1 功能需求（FR）

#### A. 自动编排（Orchestration）

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-001 | Start + 自主循环 14-skill | 合法 workdir 启动 5s 内进 running / ST Go 后 COMPLETED 自停 / 非 git repo 被拒并提示 | FUNC, BNDRY, SEC | Critical | Auto | SEC：workdir 路径必须拒 `..` 穿越与符号链逃逸 |
| FR-002 | 每 ticket 结束调 phase_route.py | 终态后必须调 phase_route 而非缓存 / next_skill 透传为 skill_hint / ok=false 暂停并呈 error | FUNC, BNDRY | Critical | Auto | 松弛 JSON 解析—字段增减不破适配器 |
| FR-003 | 信号文件自动进 hotfix/increment | bugfix 存在 → hotfix 分支 / increment 存在 → increment / 两者共存 → 按 phase_route 优先级忠实执行 | FUNC, BNDRY, SEC | Critical | Auto | SEC：信号 JSON 解析需防注入（pydantic strict） |
| FR-004 | Pause / Cancel | running 点 Pause 当前 ticket 结束后暂停 / Cancel 后只读快照可见 / Cancelled run Resume 按钮禁用 | FUNC, BNDRY, UI | Critical | Auto | UI：Pause 二次确认 3s 超时 |

#### B. 票据系统（Ticket）

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-005 | SQLite 单表 + JSONL audit | 状态转换写库 updated_at 刷新 + JSONL append 一行 / 崩溃后重启 interrupted 可见 / WAL pragma 生效 | FUNC, BNDRY | Critical | Auto | 关联 NFR-005 |
| FR-006 | 票据状态机 | pending→running 合法 / pending→completed 拒绝并抛 TransitionError / hil_waiting→classifying 合法 | FUNC, BNDRY | Critical | Auto | 9 态转移矩阵完整单测 |
| FR-007 | 票据字段覆盖核心元数据 | 已结束 ticket 全字段 readable / 缺字段为 null 非不存在 / depth > 2 拒绝 spawn | FUNC, BNDRY | Critical | Auto | depth 边界 0/1/2/3 四值 |

#### C. HIL（Human-in-the-Loop）

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-008 | pty 包装交互模式运行 Claude | 观察进程 argv 不含 `-p` / pty 通道建立后 tool_use 可捕获 / CLI 缺失 → skill_error | FUNC, BNDRY, SEC | Critical | Auto | SEC：env 白名单（不透传 HOME 默认值） |
| FR-009 | 监听 stream-json 捕获 AskUserQuestion | tool_use=AskUserQuestion → hil.detected=true / 缺字段默认补齐 + warning / 半行 JSON 缓冲正确续解析 | FUNC, BNDRY, SEC | Critical | Auto | SEC：防 stream-json 恶意大对象 DoS（>10MB 截断） |
| FR-010 | UI 渲染 3 种 HIL 控件 | multiSelect=false + options≥2 → Radio / multiSelect=true → Checkbox / allowFreeform=true + options=0 → Textarea / allowFreeform + options>0 → Radio+其他 | FUNC, BNDRY, SEC, UI | Critical | Auto | SEC：XSS（用户提交 freeform 到 UI 渲染）。UI：Chrome DevTools 三层检测 |
| FR-011 | pty stdin 回写原会话 | 答案写入后同 pid 续跑 / pty 关闭尝试写入 → failed + 答案保留 / 答案含特殊字符正确 escape | FUNC, BNDRY, SEC | Critical | Auto | SEC：命令注入防护（answer bytes 禁 `\x03` 等信号） |
| FR-012 | OpenCode HIL hooks 捕获 | hooks 注册成功 skill 调 Question → HIL 控件生成 / 版本不兼容注册失败 → ticket failed 并提示升级 | FUNC, BNDRY | Critical | Auto | — |
| FR-013 | HIL pty 穿透 PoC | PoC 脚本 20 次 HIL 循环成功率 ≥ 95% / 失败率 > 5% → 冻结 HIL FR 并上报 | FUNC, BNDRY, PERF | Critical | Auto | PERF：20 次 round-trip + 统计 |
| FR-014 | 终止横幅 + 未答 HIL 冲突优先 HIL | 末尾同时有 banner + AskUserQuestion → state=hil_waiting / 答完后调 phase_route 而非 completed | FUNC, BNDRY | Critical | Auto | BannerConflictArbiter ≥10 fixture |

#### D. Tool Adapter

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-015 | ToolAdapter Protocol 定义 | **Happy**：mypy 严格检查 Claude+OpenCode Adapter 通过 / Mock Provider 实现 Protocol 可被 orchestrator dispatch / **Error**：Mock Provider 缺实现某方法 → mypy --strict 报错 + orchestrator 运行时 TypeError 拒绝注册 | FUNC, BNDRY | Critical | Auto | 静态 + 运行时；6 方法残缺场景覆盖 |
| FR-016 | ClaudeCodeAdapter argv | argv 必含全部 FR-016 列表 flag / 未指定 model → 无 `--model` | FUNC, BNDRY | Critical | Auto | argv 等值断言 |
| FR-017 | OpenCodeAdapter argv + hooks | argv 首 `opencode` + 可选 model/agent / v1 指定 mcp_config 降级 + UI 提示 | FUNC, BNDRY | Critical | Auto | — |
| FR-018 | 适配器接口稳定性 | **Happy**：Mock Provider 实现 6 方法可注册并 dispatch / **Error**：ToolAdapter 新增可选方法（未来）不破坏现有 Claude/OpenCode Adapter（向后兼容断言）| FUNC, BNDRY | High | Auto | 向后兼容 regression |

#### E. Models & Classifier

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-019 | per-ticket / per-skill 覆写 | skill=requirements, model=opus 映射生效 argv 含 `--model opus` / 重叠规则按优先级选 | FUNC, BNDRY, UI | Critical | Auto | UI：规则表 CRUD |
| FR-020 | 四层优先级 | 仅 run-default → argv 含该 model / 四层空 → 不含 `--model` / per-ticket 胜 per-skill | FUNC, BNDRY | Critical | Auto | 优先级表全 2^4=16 组合抽样 |
| FR-021 | Classifier OpenAI-compat | GLM 预设保存 base_url 自动填 + keyring 读 api_key / 空 base_url 前端阻止 | FUNC, BNDRY, SEC, UI | Critical | Auto | SEC：api_key 不落 config 明文；SSRF 防（base_url 白名单校验域名） |
| FR-022 | Classifier on/off + rule 降级 | Off + exit_code=0 + 无 banner → rule 判 COMPLETED / Off + stderr 含 "context window" → context_overflow | FUNC, BNDRY | Critical | Auto | rule 规则全覆盖 |
| FR-023 | JSON schema 严格输出 | LLM 非合法 JSON → 降级 rule + audit warning / verdict 非枚举 → 同降级 | FUNC, BNDRY, SEC | Critical | Auto | SEC：防 LLM prompt injection 导致越权 verdict |

#### F. Anomaly Handling

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-024 | context_overflow 识别与恢复 | stderr 匹配 → 自动 spawn 新 ticket + retry_count+1 / 第 3 次同 skill 命中 → 暂停 + UI 提示 | FUNC, BNDRY | Critical | Auto | 关联 NFR-003 |
| FR-025 | rate_limit 指数退避 | 首次 rate_limit → 30s 后 spawn / 第 4 次 → 暂停 | FUNC, BNDRY, PERF | Critical | Auto | PERF：实测退避时延窗口 30/120/300s ±5s |
| FR-026 | network 异常恢复 | 首次 network → 立即 spawn / 第二次 → 60s 后 spawn / 第三次 → 上报 | FUNC, BNDRY | Critical | Auto | 关联 NFR-004 |
| FR-027 | 单 ticket watchdog timeout | 30 分钟未结束 → SIGTERM / SIGTERM 后 5s 未终止 → SIGKILL | FUNC, BNDRY, PERF | Critical | Auto | PERF：计时精度 ±1s |
| FR-028 | skill_error 直通 ABORT | result_text 首行 `[CONTRACT-DEVIATION]` → aborted + anomaly=skill_error 不重试 / 暂停等用户决 | FUNC, BNDRY | Critical | Auto | — |
| FR-029 | 异常可视化 + 手动控制 | Skip 点击 → 跳过 ticket 并调 phase_route / Force-Abort → ticket 立即 aborted | FUNC, BNDRY, UI | Critical | Auto | UI：Chrome DevTools 按钮交互 |

#### G. UI 主页面（6 条 active，FR-033b / FR-035b 延后 v1.1）

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-030 | RunOverview 界面 | phase 进度条 6 元素可见 + cost 总和等于 Σ ticket.cost_usd / work 3/8 feature 正确渲染 | FUNC, BNDRY, PERF, UI | Critical | Auto | PERF：p95<500ms（NFR-001）；UI：phase stepper 状态色语义映射 |
| FR-031 | HILInbox 界面 | 3 张 hil_waiting → 3 卡片 / 提交答案 → 卡片转 answered + ticket 推进 / 空列表 → Empty State | FUNC, BNDRY, SEC, UI | Critical | Auto | SEC：answer 回填防 XSS |
| FR-032 | SystemSettings 界面 | 保存 API key → keyring 存原文 + UI masked `***abc` / test 连接按钮成功 ping / **test 连接 401 → UI 错误横幅** / **test 连接 connection-refused → UI 错误横幅 + 降级 rule** | FUNC, BNDRY, SEC, UI | Critical | Auto | SEC：masked 显示不泄漏到 DOM 明文；CSRF 不适用（localhost）；test 错误路径对接 IFR-004 HTTP 401/502 |
| FR-033 | PromptsAndSkills 界面（v1 基础） | skill tree 列 SKILL.md 可读 / 编辑 classifier prompt 保存后历史追加一条 / 只读 skill 不允许编辑 | FUNC, BNDRY, SEC, UI | High | Auto | SEC：Path traversal 防 skill_tree 逃逸 plugins/ |
| FR-034 | TicketStream 界面 | 筛选 tool=claude → 仅 claude ticket / 100 事件三类分组折叠 / 10k+ 事件虚拟滚动不卡 | FUNC, BNDRY, PERF, UI | Critical | Auto | PERF：10k 事件帧率 ≥30fps；UI：虚拟滚动视口边界 |
| FR-035 | DocsAndROI 界面（v1 subset） | 文件树列出 docs/plans/* / Markdown 预览渲染 / ROI 按钮 disabled + tooltip `v1.1 规划中` | FUNC, BNDRY, SEC, UI | High | Auto | SEC：文件读取限 `<workdir>/docs/` 前缀 |

#### I. 过程文件编辑 + 自检

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-038 | ProcessFiles 结构化表单 | feature-list.json schema 分组渲染 / +添加特性 按钮扩展数组 / 字段按类型渲染 | FUNC, BNDRY, SEC, UI | Critical | Auto | SEC：输入 sanitize（防 JSON 注入） |
| FR-039 | 前端 + 后端双层校验 | 必填空 onChange → 字段红 + Save 禁用 / 前端通过后端报错 → inline 错误列表 / 跨字段校验 | FUNC, BNDRY, SEC, UI | Critical | Auto | SEC：后端 subprocess 命令注入防护 |
| FR-040 | 过程文件自检按钮 | 合法 feature-list.json 点自检 → PASS / 脚本 exit≠0 stderr 非空 → 错误不被吞 | FUNC, BNDRY, UI | Critical | Auto | — |

#### J. Git + Diff

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-041 | CommitHistory 界面 | 5 feature 8 commits 列表完整 / 选中 commit → 右侧文件级 diff / 二进制文件占位 | FUNC, BNDRY, UI | Critical | Auto | — |
| FR-042 | Ticket 级 git 记录 | 2 commit ticket 结束 → git.commits 长度=2 且 head_after≠head_before / feature 完成 ticket → feature_id 非空 git_sha 匹配 | FUNC, BNDRY | Critical | Auto | — |

#### K. 环境隔离 + Skills 管理

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-043 | 不写入 ~/.claude | 一次 run 后 `~/.claude/` 文件 mtime 全无变化 / symlink 指向 bundle 正常加载 | FUNC, BNDRY, SEC | Critical | Auto | SEC：filesystem audit（lsof + mtime diff）；NFR-009 共轨 |
| FR-044 | workdir 只读写 .harness/ | run 结束 workdir 非 .harness 下无 Harness 临时文件出现 | FUNC, BNDRY, SEC | Critical | Auto | SEC：WorkdirScopeGuard 拦截 |
| FR-045 | Skills 安装 / 更新 | git URL clone → 目录生成 + UI 显示 sha / 本地目录 pull → 执行 git -C pull 显示结果 / 无效 URL → 报错 / **CON-005 反面**：run 期间 `plugins/longtaskforagent/` mtime 不变（无自动 pull） | FUNC, BNDRY, SEC, UI | Critical | Auto | SEC：git URL 白名单；CON-005：仅手动触发，运行期不自动更新 |
| FR-046 | 继承 claude auth | **Happy**：已 auth → 不提示 API key，ticket 正常启动 / **Err-J（区分 Err-B）**：CLI 存在但未 auth → spawn 成功但子进程 stderr 含 `not authenticated` 类字符串 → classifier 判 `skill_error` → 区别于 Err-B（CLI 二进制不存在）| FUNC, BNDRY, SEC | Critical | Happy: Manual: external-action / Err-J: Auto | 真实 `claude auth login` OAuth 人工；未 auth 分支用 mock CLI stderr 注入（与 "CLI 缺失" 为两类 error）|

#### L. Skill 覆盖

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-047 | 驱动全部 14 skill | 完整 run dispatch 过 skill 集 ⊇ 14 必要子集 / phase_route 返回未硬编码 skill 仍能 dispatch | FUNC, BNDRY | Critical | Auto | 端到端 full run |
| FR-048 | 信号文件感知 | 外部新增 bugfix-request.json watcher 触发 → 2s 内 UI 可见 / docs/plans/* 变更 UI 文件树 "NEW" 徽章 | FUNC, BNDRY, UI | Critical | Auto | UI：watcher + WebSocket 推送 |

#### M. 分发

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| FR-049 | PyInstaller 三平台打包 | 无 Python Linux 运行二进制启动 UI / macOS Apple Silicon 启动 UI / Windows 启动 UI | FUNC, BNDRY, PERF | Critical | Auto | PERF：冷启动 < 10s；CI matrix 3 job |
| FR-050 | 首启自动建 ~/.harness + keyring | 首启 → `~/.harness/config.json` 存在 / 保存 API key → config.json 不含明文 key | FUNC, BNDRY, SEC | Critical | Auto | SEC：NFR-008 共轨 |

### 2.2 非功能需求（NFR）

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| NFR-001 | UI 响应 p95 < 500ms | Playwright 100 次票据提交 p95 < 500ms / 页面切换 p95 < 500ms / 表单提交 p95 < 500ms | PERF, UI | Critical | Auto | 工具：Playwright + Chrome DevTools 抽样 |
| NFR-002 | Stream-json 事件 p95 < 2s | 100 个事件时间戳到达差 p95 < 2s | PERF | High | Auto | 工具：TicketStream 事件时间戳 |
| NFR-003 | context_overflow 上限 ≤ 3 | 注入 mock stderr 4 次 → 第 4 次不再 spawn 而 escalate | FUNC, PERF | Critical | Auto | — |
| NFR-004 | rate_limit 上限 ≤ 3 次（30/120/300s） | 注入 HTTP 429 mock 4 次 → 第 4 次 escalate；第 1-3 次延迟测量 | FUNC, PERF | Critical | Auto | — |
| NFR-005 | 崩溃重启后 interrupted 100% 可见 | 杀进程后重启 UI → 未完成 ticket 全标 interrupted | FUNC, BNDRY | Critical | Auto | — |
| NFR-006 | 崩溃时写入隔离 | 杀 Harness 进程 → filesystem audit 仅 `.harness/` + `.harness-workdir/` 有写 | SEC | Critical | Auto | 工具：lsof + 路径 diff |
| NFR-007 | FastAPI 绑 127.0.0.1 | 启动后 `ss -tnlp` socket bind 验证 / 不监听 0.0.0.0 | SEC | Critical | Auto | — |
| NFR-008 | API key 仅 keyring | 递归 grep 配置目录无 api_key 明文 / keyring list 含对应 service | SEC | Critical | Auto | — |
| NFR-009 | 不写 ~/.claude | `stat` run 前后 `~/.claude` 所有 mtime 不变 | SEC | Critical | Auto | FR-043 共轨 |
| NFR-010 | UI 仅简体中文 | 源代码 grep 无其他语言字符串 / 视觉评审通过 | FUNC, UI | High | Manual: visual-judgment | 视觉评审部分需人工；源码 grep 部分 Auto |
| NFR-011 | HIL 控件标注 | 控件顶部显示 "单选/多选/自由文本" / 自由文本 placeholder 含 skill hint | FUNC, UI | High | Auto | — |
| NFR-012 | 三平台支持 | Linux x86_64 / macOS x86_64+arm64 / Windows x86_64 smoke 测试通过 | FUNC | Critical | Auto | — |
| NFR-013 | 不依赖用户预装 Python | 干净 VM 二进制启动 UI | FUNC | Critical | Auto | — |
| NFR-014 | 适配器 Protocol mypy 严格 | mypy 静态检查 Adapter 全通过 / 新增 Mock 无需改 orchestrator | FUNC | High | Auto | — |
| NFR-015 | phase_route 字段增删容忍 | 缺 `feature_id` / 新增 `extras` 字段不崩 | FUNC, BNDRY | High | Auto | — |
| NFR-016 | 单 workdir 单 run 互斥 | 并发启动 2 run → 第二个被 filelock 拒 | FUNC, BNDRY | Critical | Auto | — |
| NFR-017 | 历史保留 20 run | 21 个 run 后主列表 20 条（最新）+ 归档入口含第 1 条（最老溢出） | FUNC, BNDRY | High | Auto | 主列表保留最新 N=20，溢出的最老条目进归档 |

### 2.3 接口需求（IFR）

| Req ID | 需求摘要 | 验收场景 | 必须类别 | 优先级 | 自动化可行性 | 备注 |
|---|---|---|---|---|---|---|
| IFR-001 | Claude Code CLI pty+argv+stream-json | 完整 argv 包含 FR-016 flag / stream-json 事件 kind 5 种全解 / CLI 缺失 → skill_error | FUNC, BNDRY, SEC | Critical | Auto | 关联 FR-008/016 |
| IFR-002 | OpenCode CLI pty+hooks | argv `opencode ...` 正确构造 / hooks.json 注入成功 Question 工具被捕获 / **hooks.json 写入路径限 `<isolated>/.opencode/` 防目录逃逸** / **Question name 超长（>256B）截断不崩** | FUNC, BNDRY, SEC | Critical | Auto | 关联 FR-012/017；SEC：hooks.json 作第三方 JSON 需防注入边界 |
| IFR-003 | phase_route.py subprocess --json | 松弛 JSON 解析增减字段均可 / exit≠0 → 暂停 + 呈 error / stdout 非 JSON → parse_error + 暂停 | FUNC, BNDRY, SEC | Critical | Auto | SEC：subprocess argv 不拼接用户输入 |
| IFR-004 | OpenAI-compat HTTP | GLM/MiniMax/OpenAI/custom 4 preset 均能发起成功 POST / 401 → 降级 rule + audit / response_format strict schema 外返回值拒收 | FUNC, BNDRY, SEC, PERF | Critical | Auto | SEC：SSRF 防（base_url domain 白名单校验）；PERF：10s timeout |
| IFR-005 | git CLI subprocess | status/rev-parse/log/show/pull 6 命令正确调用 / 非 git 目录 exit=128 被捕获 | FUNC, BNDRY, SEC | Critical | Auto | SEC：git URL 仅 https/git+ssh 白名单 |
| IFR-006 | 平台 keyring | macOS Keychain / Secret Service / Credential Manager 各自 get/set/delete 通过 / Linux 无 daemon → 降级 keyrings.alt + UI 告警 | FUNC, BNDRY, SEC | Critical | Auto | SEC：降级到明文文件时必提示 |
| IFR-007 | WebSocket FastAPI → React | 5 channel 事件推送 / 30s ping 心跳 / 60s 未收客户端重连 | FUNC, BNDRY, PERF | Critical | Auto | PERF：消息延迟 p95 < 100ms |

### 2.4 覆盖统计

| 类别 | 出现次数 | 占比 |
|---|---:|---:|
| FUNC | 72 / 72 | 100% |
| BNDRY | 71 / 72 | 99%（NFR-006/007/008/009 仅 SEC 无 BNDRY）|
| SEC | 34 / 72 | 47%（含 IFR-002 hooks.json 注入防护） |
| PERF | 13 / 72 | 18% |
| UI | 20 / 72 | 28% |
| Manual 标记 | 2 / 72 | 3%（FR-046 Happy / NFR-010 视觉评审） |

---

## 3. 测试类别策略

### 3.1 功能测试 (FUNC)

- 每个 FR 至少一个 happy-path + 一个 error-path 场景
- SRS 每条 AC（Given/When/Then）必须有对应 pytest / Chrome DevTools MCP / Playwright 用例
- **Mock 策略**：
  - **80%** 后端单测使用 **mock Claude/OpenCode CLI**（fixture 提供预录 stream-json 序列）
  - **15%** 集成测试使用**真实 Claude CLI**（`claude auth login` 已在 CI secret 注入）
  - **5%** 端到端用 Claude CLI + 真实 phase_route.py + 真实 git 仓库
- **状态机矩阵**：`Ticket.state` 9 态全转移矩阵覆盖（合法转移各一例 + 典型非法跳转 ≥3 例 → `TransitionError`）
- **Classifier rule backend**：硬编码规则每条独立单测（正则匹配、exit_code 判定、banner 识别、permission_denials 计数）

### 3.2 边界测试 (BNDRY)

- **数值边界**：
  - `ticket.depth` 取 0 / 1 / 2 / 3（3 应拒）
  - `retry_count` 取 0 / 1 / 2 / 3 / 4（context_overflow 阈值 3；rate_limit 阈值 3；network 阈值 2）
  - 历史 run 数 N=0 / 1 / 20 / 21（NFR-017）
  - stream 事件数 0 / 1 / 1k / 10k（NFR-002 + FR-034 虚拟滚动）
  - payload 大小 0 / 10KB / 1MB / 10MB（FR-009 大对象截断策略）
- **时间边界**：
  - watchdog timeout ±5s 容忍（30 分钟整点触发）
  - rate_limit 退避 30s/120s/300s ±10% 容忍
- **字符串/路径边界**：
  - 空 prompt / 单字 prompt / 超长 prompt（> 1MB）
  - workdir 路径：空 / 单层 / 含空格 / 含 Unicode
- **JSONL 解析边界**：半行（缺 `\n`）/ 多行合并（`\n\n`）/ 非法 JSON / 空 bytes

### 3.3 安全测试 (SEC)

- **输入验证**：
  - `workdir` 路径拒 `..` 穿越与符号链逃逸（resolve 后断言在白名单）
  - git URL 协议白名单（仅 `https://` 和 `git+ssh://`；拒 `file://` 和 `http://`）
  - HIL answer bytes 过滤（拒 `\x03` SIGINT、`\x04` EOF、`\x7f` DEL；允许 UTF-8 可打印 + `\n`）
  - 过程文件编辑 payload 经 Pydantic strict mode 校验，JSON 注入 `"\x00"` 被拒
- **命令注入防护**：
  - subprocess 一律 `argv: list[str]`，禁止 `shell=True`
  - `phase_route.py` / `validate_*.py` / `git` 调用均为数组形式；lint 规则 `ruff S602/S605` 配置
- **认证 / 授权**：
  - API key 仅 keyring（NFR-008）；config.json 递归 grep 断言 0 明文 match
  - FastAPI 启动断言仅 127.0.0.1（NFR-007）；`Origin` header 白名单拒 non-localhost
  - masked API key UI 断言 DOM 无明文 value（仅 `value="••••••••1234"`）
- **SSRF 防护**（classifier base_url）：
  - 拒私有网段（`127.0.0.1` / `10.x` / `172.16-31.x` / `192.168.x` / `169.254.x` / `fc00::/7`）
  - 仅 https 协议；自签证书用户显式确认（设置里 `allow_insecure_tls` 默认 false）
- **数据泄漏**：audit log / stream archive / error trace / stack trace 全部断言不含 `api_key` 明文子串

### 3.4 性能测试 (PERF)

- **工具**：
  - Python 计时：`time.perf_counter_ns` + pytest-benchmark
  - Web 计时：Playwright `page.evaluate` + Chrome DevTools MCP `performance_start_trace`
  - 启动时延：`hyperfine` CLI
- **基线采样**：每次 CI run 在 matrix 三平台各跑 3 轮取 p50 / p95 / p99；跨版本允许 10% 波动
- **负载参数**：每 NFR 条目在 §4 矩阵明确标出并发数 + 持续时长 + 渐进策略
- **pass/fail 判定**：p95 超阈 → fail；p50 超阈但 p95 在阈值内 → warning 不 block（记 trend）

### 3.5 UI 测试 (UI)

- **工具**：Chrome DevTools MCP（本地用 pywebview 嵌入 Chromium；CI 用独立 `playwright install chromium` 指 `http://127.0.0.1:<port>`）
- **交互链**：`navigate_page` → `click/fill_form/press_key` → `wait_for` → `take_snapshot` → 断言
- **三层检测**：
  - **Layer 1（DOM）**：`evaluate_script` 确认关键 selector 存在 + 文本内容正确（空白画布 = Major defect）
  - **Layer 2（EXPECT/REJECT 交互）**：点击 / 输入 / 拖拽后状态变化符合预期；负例（点击 disabled 按钮不应产生副作用）
  - **Layer 3（Console）**：`list_console_messages` 无 `error` / `warning`
- **Visual Rendering Contract**（每个 UCD §3 组件一份）：渲染完整性 / 交互深度 / 视觉一致性 / 功能准确性
- **动效与 a11y**：Tab 顺序 + Esc 关闭 modal + `prefers-reduced-motion` 降级 + 状态色 1:1 映射 `ticket.state`

---

## 4. NFR 测试方法矩阵

| NFR ID | 测试方法 | 工具 | 通过标准 | 负载参数 | 关联 Feature |
|---|---|---|---|---|---|
| NFR-001 | UI 操作响应抽样 | Playwright + DevTools MCP `performance_start_trace` | p95 < 500ms（ticket 提交 / 页面切换 / 表单提交）| 100 次交互 / 持续 60s / 10 Hz 采样 | F12, F21, F22 |
| NFR-002 | Stream-json 事件到达延迟 | asyncio `time.perf_counter_ns` + event timestamp diff | p95 < 2s（从 pty 读到字节到 UI WebSocket 收到）| 100 events burst + 10k events 长跑 | F18, F21 |
| NFR-003 | context_overflow 重试上限 | mock claude stderr 注入 | 第 4 次必 escalate 且不 spawn 新 ticket；retry_count 标 3 | 连续 4 次同 skill 的 context_overflow | F20 |
| NFR-004 | rate_limit 退避时延 | mock HTTP 429 + 计时 | 第 1 次延迟 30s±3s；第 2 次 120s±6s；第 3 次 300s±15s；第 4 次 escalate | 4 次 429 响应 | F20 |
| NFR-005 | 崩溃后 interrupted 可见 | `os.kill(SIGKILL)` + 重启 | 重启后 `state in ('running','classifying','hil_waiting')` 的 ticket 全标 `interrupted` | 杀进程中断 5 条 ticket（混合态）| F02, F20 |
| NFR-006 | workdir 写入隔离 | `lsof` + 路径 diff + filesystem audit | 仅 `.harness/` 与 `.harness-workdir/` 子树有写；其他路径 byte-level 0 变更 | 10 ticket full run 期间 + 崩溃注入 | F10 |
| NFR-007 | bind 127.0.0.1 | `ss -tnlp` 解析 + 外网 socket 连接尝试 | 启动后端口仅 127.0.0.1 bind；从 LAN 连接拒绝（connection refused）| 启动后 5s 内扫描 + 跨网段 telnet | F01 |
| NFR-008 | API key 仅 keyring | 递归 `grep -rE "<api_key_bytes>"` + `keyring list` | 0 match 明文；keyring 对应 service/user entry 存在 | 保存 3 个 API key（GLM / OpenAI / custom）| F01, F19 |
| NFR-009 | 不写 `~/.claude` | run 前后 `stat -c '%Y' ~/.claude/**/*` 全量比对 | 所有文件 mtime 完全相等（零变更）| 完整 run ≥ 10 ticket + 含 HIL round-trip | F10 |
| NFR-010 | UI 仅简体中文 | 源代码 grep + 视觉评审 | 源码除变量名/import/技术术语外无英文业务字符串；视觉评审 8 页面无英文 | 全源码扫描 + 8 页面各 1 次 | F12, F21, F22（Manual: visual-judgment 视觉评审）|
| NFR-011 | HIL 控件标注 | DOM 断言 `[data-test-hil-kind]` attr + 文本标签 | single → "单选" / multi → "多选" / free → "自由文本" 三种 attr 全出现 | 3 类控件各一例 HIL ticket | F21 |
| NFR-012 | 三平台支持 | CI matrix smoke + `playwright test --project=chromium` | 三平台二进制启动 UI 并响应 `/api/health` 200 | 每平台 1 次 CI job | F17 |
| NFR-013 | 不依赖预装 Python | 干净 VM Docker 镜像（无 python3）+ Windows 无 VS C++ runtime | 二进制 `./harness` 启动成功 | 每平台 1 次干净 VM | F17 |
| NFR-014 | Adapter Protocol mypy 严格 | `mypy --strict harness/adapter/` | 退出码 0；无 `error` 级 diagnostic | 全 adapter 包源码 | F18 |
| NFR-015 | phase_route 松弛解析 | pytest fixture 注入缺字段 / 新增字段 JSON | 无 exception 抛出；默认值补齐后 `PhaseRouteResult` 可读 | 10 种 fixture | F20 |
| NFR-016 | 单 workdir 单 run 互斥 | 并发启 2 run 同 workdir | 第二个 filelock `Timeout` + 显式错误 "已有 run 在运行" | 2 run 并发 | F20 |
| NFR-017 | 历史 20 run 保留 | 21 次 run 后查主列表 + 归档 | 主列表 20 条（最新）；归档入口含第 1 条 + 原样保留 | 21 个小 run | F02, F20 |

---

## 5. 跨 Feature 集成场景

基于 Design §6.2 IAPI-001..019 派生。每个 IAPI 至少 1 条 happy-path，关键错误边补 error-path；共享状态加一致性场景。

### 5.1 核心端到端与错误路径场景

| 场景 ID | 场景描述 | 涉及 Features | 数据流路径（Contract IDs） | 验证要点 | ST 阶段 |
|---|---|---|---|---|---|
| **INT-001** | **HIL full round-trip**：Claude skill 触发 AskUserQuestion → UI 渲染控件 → 用户提交答案 → pty 续跑 | F18, F21, F20, F02 | CLI stream → IAPI-006 byte_queue → StreamParser → IAPI-008 StreamEvent → HilEventBus → IAPI-001 `/ws/hil` push → UI → `POST /api/hil/:ticket_id/answer` (IAPI-002) → HilWriteback → IAPI-007 pty stdin → CLI 续跑 → IAPI-009 AuditWriter | 整链 p95 < 3s；同 pid 续跑；ticket.hil.answers 持久化；FR-013 PoC 门（≥95% 成功率 / 20 轮）| System ST |
| **INT-002** | **Run Start 流**：用户点 Start → workdir 校验 → phase_route → 第一张 ticket spawn | F01, F20, F10, F18 | `POST /api/runs/start` (IAPI-002) → BindGuard 通过 → RunLock acquire → IAPI-017 EnvironmentIsolator.setup_run → IAPI-003 phase_route JSON → IAPI-004 TicketCommand → IAPI-005 ToolAdapter.spawn → IAPI-006 DispatchSpec → PTY spawn | 5s 内 UI 进 running；隔离目录生成；argv 含全部 FR-016 flag；head_start 记录 git sha | System ST |
| **INT-003** | **非 git repo Start 错误**：用户指定非 git 目录 → 拒启动并提示 | F01, F20 | `POST /api/runs/start` → `git status --porcelain` exit=128 → Gateway 返 400 → UI Modal 展示错误 | error_code 正确；filelock 未被占用；UI error Modal 可读 | Feature ST |
| **INT-004** | **Anomaly context_overflow 自愈链**：stderr 匹配 → Classifier RETRY → 新 ticket 继承 skill_hint → 3 次后 escalate | F19, F20, F18 | StreamParser → Classifier (IAPI-010) Verdict=RETRY → IAPI-004 Supervisor.reenqueue_ticket → 新 DispatchSpec 含 skill_hint → spawn → 第 4 次同 skill stderr 匹配 → EscalationEmitter → IAPI-001 `/ws/anomaly` escalated 事件 | retry_count 累加 1/2/3；第 4 次 `RecoveryDecision.kind="escalate"`；run 状态 paused；UI 显示上报 | System ST |
| **INT-005** | **Classifier LLM 失败降级**：LLM 返回非法 JSON → 降级 rule → audit warning → ticket 仍继续 | F19, F20 | Classifier.classify → HTTP 200 but JSON 不合 schema → FallbackDecorator 捕获 → RuleBackend.classify → Verdict(backend="rule") → audit warning event → Orchestrator 按 verdict 继续 | ticket.classification.backend == "rule"；audit JSONL 含 `classifier_fallback`；UI 无异常提示（降级透明）| Feature ST |
| **INT-006** | **Signal file → hotfix 分支**：外部写入 bugfix-request.json → watcher 触发 → 下一次 phase_route 选 long-task-hotfix | F10（FileWatcher）, F20, F02 | watchdog observer → IAPI-012 SignalEvent → Orchestrator queue → 当前 ticket 终态后 → IAPI-003 phase_route → next_skill=long-task-hotfix → IAPI-004 spawn ticket | 2s 内 UI 可见 `SignalFileChanged` 推送；hotfix ticket 被 dispatch；signal file 由 skill 自行删除 | System ST |
| **INT-007** | **并发 run 互斥**（NFR-016）：两个 UI 窗口同时启同 workdir → 第二个被 filelock 拒 | F20, F01 | UI#1 `POST /api/runs/start` → RunLock acquire 成功；UI#2 → RunLock 被占 → Gateway 返 409 + `reason="已有 run 在运行"` | error_code=ALREADY_RUNNING；UI#2 Modal 正确展示；UI#1 不受影响 | Feature ST |
| **INT-008** | **崩溃 + 重启恢复**（NFR-005）：`kill -9` Harness 主进程 → 重启 → 未完成 ticket 全标 interrupted | F02, F20, F01 | `kill -9 <pid>` → 进程死 → `harness.app.AppBootstrap` 重启 → `TicketRepository.list_by_run` WHERE `state IN (running, classifying, hil_waiting)` → 全部 UPDATE state=interrupted + AuditEvent `interrupted` | SQLite WAL journal 恢复；所有未完成 ticket 可见；run 状态=failed；UI 显示 `⚠ 因异常中断而保留 N 张 ticket` | System ST |
| **INT-009** | **Skills install via git URL**：用户 UI 填 git URL + 点 Clone → `git clone` → plugin 目录就绪 | F10, F22, F01 | `POST /api/skills/install` (IAPI-018) → SkillsInstaller.clone → git subprocess (IFR-005) → PluginRegistry 读 plugin.json 版本 → 返回 SkillsInstallResult → UI 显示 sha | URL 白名单拒 `file://`；target_dir 防逃逸；pull 后 `plugins/longtaskforagent/.claude-plugin/plugin.json` 存在；UI commit sha 显示 | Feature ST |
| **INT-010** | **ProcessFiles 编辑 + 后端校验**：UI 改 feature-list.json → onChange 前端 schema 校验 → 点"后端校验" → subprocess → issues 面板 | F20, F22 | UI `PUT /api/files/...` → FrontendValidator（Zod）实时 → 用户点 "后端校验" → `POST /api/validate/feature-list.json` (IAPI-016) → ValidatorRunner subprocess `validate_features.py` → ValidationReport → UI issues 列表 | onChange 必填空红 + Save 禁用；跨字段校验（例如 deprecated=true 但缺 reason）报错；subprocess exit≠0 不被吞 | Feature ST |
| **INT-011** | **CommitHistory + Diff 查看**：ticket 完成 3 commit → UI 刷新列表 → 选 commit → 右侧显示 diff | F20, F22, F02 | ticket 结束 → GitTracker.end (IAPI-013) → TicketRepository.save (IAPI-011) → UI `GET /api/git/commits?run_id=X` → 列表 → 选 commit → `GET /api/git/diff/:sha` → DiffPayload → react-diff-view 渲染 | commits 长度正确；feature_id ↔ git_sha 关联；diff 含 +/- 行号；>500 行分页 | Feature ST |
| **INT-012** | **API key keyring 往返 + masked UI**（NFR-008）：保存 classifier API key → 关机重启 → 读 keyring → UI 显示 masked | F01, F19, F22 | `PUT /api/settings/classifier` (IAPI-002) 含 api_key → KeyringGateway.set_password (IAPI-014) → 重启 → GET → UI masked `••••••••1234` | config.json 递归 grep 0 明文 match；keyring list 含 `harness-classifier-glm`；masked UI DOM 断言无明文；test 连接按钮工作 | System ST |
| **INT-013** | **OpenCode MCP 降级**：用户 DispatchSpec 带 mcp_config → OpenCode ticket 降级运行 + UI 提示 | F18, F21 | Orchestrator → OpenCodeAdapter.build_argv → 检测 mcp_config → McpDegradation 路径 → ticket 继续 spawn（不带 mcp）+ 推 UI `/ws/anomaly` 或 toast `"OpenCode MCP 延后 v1.1"` | ticket 仍 completed；UI toast 展示；argv 不含 mcp 相关 flag | Feature ST |
| **INT-014** | **Stream event fan-out + WebSocket 断线续连**：100 个 stream event 连续到达 → DB persist + WS push；UI 中途断 WS → 重连后 state 对齐 | F18, F02, F12 | PTY byte_queue (IAPI-006) → StreamParser.events() (IAPI-008) → 并行 fan-out: AuditWriter (IAPI-009) + TicketRepository.save (IAPI-011) + WebSocket broadcast (IAPI-001) → UI 断 WS 60s → 重连 → TanStack Query refetch `GET /api/tickets/:id/stream?offset=` 补齐 | 100 event DB 全中；UI 断连期间 DB 持续写；重连后 offset 补齐无丢事件；无重复 | System ST |
| **INT-015** | **Path traversal 攻击拒绝**（SEC）：恶意 workdir 含 `../../etc` → 启动拒；signal file 指向外部路径 → watcher 忽略 | F01, F20, F10 | `POST /api/runs/start { workdir: "/home/user/../../etc" }` → 路径 resolve 后断言 → 400 Bad Request；FileWatcher 订阅路径限 `<workdir>/**` 前缀 | error_code=PATH_REJECTED；审计记录访问企图；无任何文件被读 | Feature ST |
| **INT-016** | **SSRF classifier base_url 防护**（SEC）：用户填 `http://169.254.169.254/...` → 保存被拒 | F19, F22 | UI `PUT /api/settings/classifier` → 后端 `ClassifierConfig` validator 检测 base_url → 解析到私有网段 IP → 400 + `detail="base_url resolves to private network"` | 私有 IP 网段全拒；允许明确 whitelist（本地 llama.cpp）时有显式 toggle；响应不泄漏解析过程 | Feature ST |
| **INT-017** | **14-skill 完整 run**（FR-047）：新建空项目 → 端到端跑完 Requirements → UCD → Design → ATS → Init → Work（N 个 feature）→ ST → Finalize | F01, F02, F10, F12, F17, F18, F19, F20, F21, F22 全栈 | Start → phase_route loop × N → 全 skill dispatch 轨迹记录 | dispatch 过的 skill 集合 ⊇ 14 必要子集；整 run 能达 ST Go verdict；cost 汇总正确 | System ST（关键冒烟）|
| **INT-018** | **三平台 PyInstaller 冷启动**（NFR-012/013）：Linux/macOS/Windows 干净 VM 各启一次 | F17 | CI matrix 3 job → `./harness` 启动 → `curl http://127.0.0.1:<port>/api/health` → 200 + bind=127.0.0.1 | 每平台启动 < 10s；UI 正常渲染；`/api/health` 报告正确版本与 claude_auth 状态 | System ST |
| **INT-019** | **Classifier prompt 版本追加**（FR-033 v1）：编辑 classifier prompt 保存 → 历史追加一条 | F19, F22 | UI `PUT /api/prompts/classifier { content: "new" }` → PromptStore 追加 → history[N+1] 包含 hash + summary | 保存前 N 条；保存后 N+1 条；summary 首 80 字截断；v1.1 的 diff/revert 交互 disabled | Feature ST |
| **INT-020** | **Ticket 历史保留 20 run**（NFR-017）：连续跑 21 个 run → 主列表 20 / 归档含第 1 条 | F02, F20 | run ×21 完成 → RunRepository.list 主列表返回 20 条最新 → archived list 接口返回第 1 条 | 主列表精确 20；归档第 1 条原样（无压缩 / 脱敏）；sqlite 存储未膨胀 | Feature ST |
| **INT-021** | **并发写一致性**（IAPI-011）：StreamParser 写 state + Anomaly 写 retry_count 同瞬间触发 | F02, F18, F20 | TicketRepository.save 并发 2 次 → SQLite WAL + busy_timeout 5000ms 串行化 | 最终 ticket.payload 完整无字段覆盖丢失；全字段读回正确 | Feature ST |
| **INT-022** | **Model 4 层优先级全矩阵**：per-ticket / per-skill / run-default 任意组合 | F19, F18 | IAPI-015 ModelResolver.resolve → DispatchSpec.model + provenance | 8 种典型组合（2^3 - 1 非空 + 全空）argv `--model` 行为均符预期；provenance 追溯正确 | Feature ST |
| **INT-023** | **Pause / Cancel 指令**（IAPI-019）：running 时 Pause → 当前 ticket 结束后不再 spawn；Cancel → 立即 abort | F20, F21 | UI `POST /api/runs/:id/pause` → RunControlBus → Orchestrator 主循环下一迭代检测标志 → 不调 phase_route；`/cancel` → 向当前 Supervisor 发 TicketCommand(cancel) → pty SIGTERM | Pause 当前 ticket 仍 completes；Cancel 后 state=cancelled；UI 对应横幅；Resume 按钮 disabled | Feature ST |
| **INT-024** | **ticket 级 git 记录 + feature_id 关联**（IAPI-013）：feature completion ticket 结束时自动绑 feature_id + git_sha | F20, F02 | TicketSupervisor 结束前 → GitTracker.end → head_after + commits + feature_id 合入 ticket.git | TicketRepository 读出 feature_id 非空且 git_sha == head_after；`GET /api/git/commits?feature_id=X` 过滤正确 | Feature ST |
| **Err-A** | phase_route.py stdout 非 JSON | F20 | IAPI-003 subprocess exit=0 但 stdout="traceback..." → PhaseRouteInvoker parse 失败 → 暂停 run + audit event `phase_route_parse_error` | run 状态 paused；UI 显示 stderr tail；不崩溃 | Feature ST |
| **Err-B** | ToolAdapter.spawn 失败（CLI 缺失）| F18, F20 | `which claude` → None → ClaudeCodeAdapter.spawn 抛 `SpawnError("Claude CLI not found")` → Supervisor 捕获 → ticket failed + anomaly=skill_error | 提示清晰；run 暂停不循环 | Feature ST |
| **Err-C** | pty 子进程异常 exit | F18 | pty child SIGSEGV → ptyprocess read 返回 EOF → PtyWorker 关 queue → StreamParser 产 ErrorEvent → ticket failed | stream archive 含到 EOF 为止的字节；audit 记 `pty_unexpected_exit` | Feature ST |
| **Err-D** | 非法 JSONL 混入 stream | F18 | stream 含 `"{invalid json"` → JsonLinesParser 捕 `json.JSONDecodeError` → audit warning + 跳过该行 + 继续 | 后续合法 JSONL 继续解析；ticket 不因此 failed；audit 记 parser warning | Feature ST |
| **Err-E** | JSONL audit 磁盘满 | F02, F18 | AuditWriter.append → OSError(ENOSPC) → 降级 `structlog.error` 写 stderr + UI toast；SQLite 仍写 | ticket 不因此 failed；UI 告警磁盘；主流程继续 | Feature ST |
| **Err-F** | 信号文件连续高频变更 | F10 | watchdog 连续 50 次 modified within 1s → debounce 500ms → 仅 2-3 次 SignalEvent 入队 | UI 不卡；Orchestrator 不被刷爆 | Feature ST |
| **Err-H** | Linux 无 Secret Service 降级 | F01 | keyring backend = `keyrings.alt.file.PlaintextKeyring` → 保存 API key → UI 顶部黄色警告条 `"未检测到 Secret Service，凭证以明文存储，建议安装 gnome-keyring"` | UI 警告可见；明文文件路径可查；功能仍可用 | Feature ST |
| **Err-I** | Validator subprocess 崩溃 | F20, F22 | `POST /api/validate/feature-list.json` → subprocess exit=1 stderr="traceback..." → ValidationReport ok=false + issues 含 stderr tail | UI 显示脚本崩溃；不吞错 | Feature ST |
| **Err-J** | Claude CLI 存在但未 auth（区别 Err-B）| F18, F20 | `which claude` → 二进制路径存在 → ClaudeCodeAdapter.spawn 成功 → pty 子进程运行短暂 → stderr 含 `not authenticated` / `please run claude auth login` 类字符串 → exit 非零 → classifier 判 `skill_error` → ticket aborted | 与 Err-B 区分：Err-B spawn 失败；Err-J spawn 成功但认证失败；UI 提示清晰区分 | Feature ST |
| **INT-025** | Classifier test-connection 错误路径（FR-032 补齐）| F19, F22 | UI `POST /api/settings/classifier/test` → httpx 请求 → 401 Unauthorized → Gateway 返 400 + 错误 detail / connection-refused → Gateway 返 502 Bad Gateway + detail / DNS 失败 → 500 | 三种错误码 UI 横幅正确展示；保存动作因 test 失败不阻塞（仅警告）；IFR-004 protocol 错误分支覆盖 | Feature ST |

### 5.2 IAPI 覆盖自检

| IAPI | happy-path 场景 | error-path 场景 | 一致性场景 |
|---|---|---|---|
| IAPI-001（WS）| INT-001, INT-006, INT-014 | INT-014（断线） | — |
| IAPI-002（REST）| INT-002, INT-009, INT-010, INT-011, INT-012, INT-019 | INT-003, INT-007, INT-015, INT-016 | — |
| IAPI-003（phase_route）| INT-002, INT-017 | INT-003, Err-A | — |
| IAPI-004（TicketCommand）| INT-002, INT-004 | — | — |
| IAPI-005（ToolAdapter）| INT-002, INT-013 | Err-B（CLI 缺失）, Err-J（未 auth） | — |
| IAPI-006（PTY handle）| INT-001, INT-014 | Err-C | — |
| IAPI-007（pty write）| INT-001 | INT-001 分支（pty 关闭时写入失败） | — |
| IAPI-008（StreamEvent）| INT-001, INT-014 | Err-D | — |
| IAPI-009（AuditWriter）| INT-001, INT-004 | Err-E | — |
| IAPI-010（Classifier）| INT-001, INT-004, INT-012 | INT-005, INT-025（test 401/502/DNS 错误） | — |
| IAPI-011（TicketRepo）| INT-008, INT-011, INT-014 | INT-008 | INT-021 |
| IAPI-012（SignalEvent）| INT-006 | Err-F | — |
| IAPI-013（GitTracker）| INT-011, INT-002, INT-024 | INT-003 | — |
| IAPI-014（keyring）| INT-012 | Err-H | — |
| IAPI-015（ModelResolver）| INT-022 | — | — |
| IAPI-016（ValidatorRunner）| INT-010 | Err-I | — |
| IAPI-017（EnvironmentIsolator）| INT-002 | — | — |
| IAPI-018（SkillsInstaller）| INT-009 | INT-009 | — |
| IAPI-019（RunControlBus）| INT-023 | INT-007 | — |

### 5.3 场景总数与类别分布

- **INT-001 .. INT-025**：25 个常规集成场景（含新增 INT-025 test-connection 错误路径）
- **Err-A, B, C, D, E, F, H, I, J**：9 个错误路径场景（Err-G 已并入 INT-003；新增 Err-J "CLI 存在但未 auth"）
- **合计：34 个集成场景**（System ST：9 + Feature ST：25）

类别覆盖：
- FUNC: 34 / 34
- BNDRY: 16 / 34（并发、重试次数、路径边界）
- SEC: 7 / 34（INT-015, INT-016, INT-009, INT-012, INT-025, Err-H, Err-J）
- PERF: 4 / 34（INT-001 时延、INT-014 fan-out、INT-017 整 run 时长、INT-018 冷启动）
- UI: 8 / 34

### 5.4 Wave 2 Feature 重组对 ATS 覆盖的影响（2026-04-24）

Wave 2 重包装将 12 个旧 feature（F03/F04/F05/F06/F07/F08/F09/F11/F13/F14/F15/F16）合并为 5 个新 feature（F18 Bk-Adapter / F19 Bk-Dispatch / F20 Bk-Loop / F21 Fe-RunViews / F22 Fe-Config），保留 5 个 feature（F01/F02/F10/F12/F17）。对 ATS 覆盖的影响：

- **需求 → 测试场景映射**：48 active FR + 17 NFR + 7 IFR = 72 行，保持 1:1，**0 新增 / 0 修改语义 / 0 弃用**。
- **类别占比（FUNC/BNDRY/SEC/PERF/UI）**：全表数字不变（FUNC 100%、BNDRY 99%、SEC 47%、PERF 18%、UI 28%、Manual 3%）。
- **Feature ID 文本引用**：§1.2 / §2.4（无 feature 列，无影响）/ §4 NFR Matrix / §5.1 集成场景 / §5.2 IAPI 覆盖自检 / §6.1 风险矩阵 / 附录评审摘要的 feature id 按 Wave 2 映射重写；合计约 40 处文本替换。
- **§4 NFR Matrix 关联 Feature 列**：17 条 NFR 的关联 feature id 重映射（F03/F05 → F18；F04 → F18；F06/F09 → F20；F08 → F19；F13/F14 → F21；F15/F16 → F22），测试方法 / 通过标准 / 负载参数 **0 变更**。
- **§5.1 跨 Feature 集成场景**：25 个 INT + 9 个 Err = 34 个场景，场景逻辑 / 数据流路径 (Contract IDs) / 验证要点全部保留；仅涉及 feature id 标记（F0x/F1x → F18–F22）的文本替换。
- **§5.2 IAPI 覆盖自检**：19 条 IAPI 签名与语义 **0 变更**（Design §6.2.1 Wave 2 OWNER-REMAP）；对应测试场景清单不变。

结论：ATS 仍是 feature-list.json Wave 2 版本的权威测试源；无需 ats-reviewer 重跑（测试场景与验收标准未动）。

---

## 6. 风险驱动测试优先级

### 6.1 风险评估矩阵

| 风险区域 | 风险级别 | 影响范围 | 测试深度 | 依据 |
|---|---|---|---|---|
| HIL pty 穿透（Claude `AskUserQuestion` round-trip） | Critical | F18, F21（关键路径节点） | 深度 | SRS ASM-003 需 PoC 验证；F18 HIL PoC gate（≥95%）不过则冻结 v1 |
| stream-json schema 跨 Claude 版本漂移 | High | F18 所有消费者 | 深度 | Design Risk；宽松 Pydantic 容忍未知字段；CLI 版本在 `/api/health` 暴露 |
| Cross-platform pty（Windows ConPTY） | High | F18 | 深度 | pywinpty 基于 ConPTY 需 Win10 1809+；CI matrix 验证 |
| PyInstaller + pywebview 三平台打包 | High | F17 | 深度 | NFR-012/013；干净 VM smoke；libwebkit2gtk 版本约束 |
| Classifier LLM 供应商协议漂移 | Medium | F19 | 标准 | response_format=json_schema 支持度差异；rule 降级兜底 |
| SQLite 并发写 + WAL 恢复 | Medium | F02 | 标准 | busy_timeout=5000ms；NFR-005 崩溃恢复关键 |
| pywebview WebKit2GTK Linux 版本敏感 | Medium | F01, F17 | 标准 | 打包要求 libwebkit2gtk-4.1（Ubuntu 22.04+） |
| FR-014 终止横幅 + HIL 冲突仲裁 | Medium | F18 | 标准 | BannerConflictArbiter ≥10 fixture 单测 |
| 14-skill 完整 run 端到端 | High | F01, F02, F10, F12, F17, F18, F19, F20, F21, F22 全栈 | 标准 | System ST 冒烟 |
| Path traversal / SSRF（安全输入） | High | F01, F19, F10 | 标准 | 6 个 SEC 场景 + §3.3 策略 |
| Deferred FR（ROI / classifier diff）| Low | — | 轻量 | v1.1；v1 仅 UI placeholder + 文字提示 |

### 6.2 测试深度定义

| 深度 | 含义 |
|---|---|
| 深度 | 所有必须类别（FUNC + BNDRY + 适用的 SEC/PERF/UI）+ 额外探索性测试 + 多 fixture 变体 |
| 标准 | 所有必须类别各覆盖 1-2 条场景 |
| 轻量 | FUNC + BNDRY 各一例（用于 Low 风险或 deferred 占位）|

---

## 附录: ATS 审核报告

**评审者**: long-task:ats-reviewer SubAgent（独立）
**评审日期**: 2026-04-21
**评审模式**: 两轮审阅（Round 1 初审 + Round 2 修复验证）

> **Wave 2 Remap (2026-04-24)**: 本审核报告引用的 feature id（F03–F16）属于 Wave 1 命名；Wave 2 重包装已将旧 feature 合并/重命名为 F18–F22（参见 Design §6.2.1 Wave 2 OWNER-REMAP）。由于本轮 increment 仅为 refactor-only 重包装（0 FR/NFR/IFR 语义变更、0 mapping 新增/删除），Round 1/Round 2 评审的所有结论（缺陷修复、最终裁决 PASS）继续有效；下文保留原 Wave 1 feature 号便于追溯评审当时的上下文。

### 最终裁决: PASS

- Major 缺陷: 0（Round 1 发现 1，已修复）
- Minor 缺陷: 0（Round 1 发现 6，全部修复）
- CROSS-REF 冲突: 0（Round 1 发现 1，已裁决修复）

---

### Round 1 评审摘要

#### R1 需求覆盖完备性: PASS
48 active FR + 17 NFR + 7 IFR = 72 行，全部入映射表；v1.1 延后的 FR-033b / 035b / 036 / 037 明确排除；无孤立行；§2.4 统计与 §2.1-2.3 实际行数一致。

#### R2 类别多样性: PASS（Round 1 有 2 Minor，已修复）
- FR 全部覆盖 FUNC + BNDRY
- 处理外部输入/认证的 FR 均含 SEC
- `ui:true` 特性全覆盖 UI
- NFR 带量化阈值的均含 PERF
- **Minor #4**：IFR-002 初稿缺 SEC → 修复后追加路径逃逸 + Question name 长度边界两场景
- **Minor #6**：FR-015 / FR-018 初稿仅 Happy → 修复后均有 Happy + Error 双路径

#### R3 场景充分性: PASS（Round 1 有 3 Minor，已修复）
- 路径覆盖：FR 全部 happy + error
- 边界：数值/时间/字符串/JSONL 四类在 §3.2 明确
- 状态：Ticket 9 态机合法+非法转移矩阵覆盖
- 错误处理：外部依赖（IFR）均含超时/不可用/401
- 隐式需求：
  - **Minor #2**：FR-046 未 auth 场景缺失 → 新增 Err-J，与 Err-B（CLI 缺失）明确区分
  - **Minor #3**：FR-032 test-connection 错误路径缺失 → 新增 INT-025 覆盖 401/502/DNS
  - **Minor #5**：CON-005 反面场景缺失 → FR-045 追加「run 期间 plugins mtime 不变」

#### R4 可验证性: PASS
所有 NFR 通过标准可测量；FR 场景含具体输入/输出；UI 场景映射 Chrome DevTools MCP（§3.5 三层检测）；无含糊词。

#### R5 NFR 可测试性: PASS
§4 矩阵 17 条 NFR 均具工具 + 量化阈值 + 负载参数；Manual 标注 2/72=3%，远低于 20% 上限。

#### R6 跨特性集成: PASS
§5.1 列出 34 个集成场景，引用 F01-F22（preserved: F01/F02/F10/F12/F17；new: F18-F22）+ IAPI-001..019；§5.2 IAPI 覆盖自检确认每个 IAPI 至少 1 happy + 关键 error。

#### R8 交叉校验: PASS（Round 1 有 1 Major CROSS-REF CONFLICT，已裁决修复）
- **Major**：NFR-017 归档语义 ATS §2.2 与 ATS §4 / INT-020 / SRS 三方矛盾 → 用户裁决 A → 统一为"主列表 20 条最新 + 归档入口含第 1 条最老溢出"
- R8.1 SRS AC 覆盖：每条 FR Given/When/Then 至少 1 场景
- R8.2 通过标准一致性：NFR 阈值 ATS §4 与 SRS §5 完全一致
- R8.3 工具栈可行性：Playwright + pytest + mypy + hyperfine 与 Design §1.4 兼容；IAPI-001..019 全存在于 Design §6.2.1

---

### Round 2 修复验证摘要

| 缺陷 ID | Round 1 级别 | Round 2 状态 | 证据 |
|---|---|---|---|
| NFR-017 CROSS-REF | Major | RESOLVED | §2.2 / §4 / INT-020 三处对齐 |
| §5.3 统计 | Minor | RESOLVED | 34 场景（25 INT + 9 Err） |
| FR-046 未 auth | Minor | RESOLVED | §2.1 FR-046 行 + §5.1 Err-J |
| FR-032 test-connection | Minor | RESOLVED | §2.1 FR-032 行 + §5.1 INT-025 |
| IFR-002 SEC | Minor | RESOLVED | §2.3 IFR-002 行 + §2.4 SEC 34/72 |
| CON-005 反面 | Minor | RESOLVED | §2.1 FR-045 行 |
| FR-015/018 error-path | Minor | RESOLVED | §2.1 FR-015 + FR-018 行 |

Round 2 未发现新缺陷；7 项修复全部 RESOLVED；ATS 获批进入 Init 阶段。

---

### 评审结论

ATS 具备完整的 48 FR + 17 NFR + 7 IFR 映射、5 类别多样性、17 NFR 量化工具链、34 跨特性集成场景、19 IAPI 契约覆盖。**可作为 feature-list.json 生成与 Feature-ST 测试用例派生的权威源。**
