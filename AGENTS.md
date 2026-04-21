# Harness


<!-- long-task-agent -->
## Long-Task Agent

**语言规则（Language Rule）**：
- 所有对用户的回复和生成的文档必须使用**简体中文**。
- 以下内容保留英文原样，不翻译：代码标识符、函数/变量/字段名（如 `srs_trace`、`feature_id`）、命令行示例、工具名（`Skill` / `Agent` / `Grep` / `mvn test` 等）、YAML frontmatter 的 `name` / `description` 字段、commit message、文件路径。
- 已成标识符的缩写保留英文：`SRS` / `FR` / `NFR` / `ATS` / `UCD` / `ST` / `TDD` / `UT` / `E2E`（首次出现可在括号内注中文）。
- 术语统一参考 `docs/templates/glossary.md`（若存在），避免漂移。

Multi-session workflow. `using-long-task` skill routes by project state:

**Pre-init** (no `feature-list.json`):
  requirements → ucd (if UI) → design → ats → init

**Post-init** (has `feature-list.json`): route by root `current` lock:
  - `current = {feature_id: N, phase: "design"}` → `long-task-work-design`
  - `current = {feature_id: N, phase: "tdd"}`    → `long-task-work-tdd`
  - `current = {feature_id: N, phase: "st"}`     → `long-task-work-st`
  - `current = null` AND any feature `status=failing` → router picks next dep-ready feature
  - `current = null` AND all features `status=passing` → `long-task-st` (system-wide)

Override signals: `bugfix-request.json` or `increment-request.json` at project root
→ `long-task-hotfix` / `long-task-increment` runs first (highest priority).

One feature × one phase per session. Sessions terminate explicitly (no auto-loop).

Quick status: `python scripts/count_pending.py feature-list.json`
State source of truth: `feature-list.json`.
<!-- /long-task-agent -->
