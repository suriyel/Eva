# Task Progress — Harness

> Session log only. Current project state (which feature is locked, which
> phase it's in, how many features are passing) lives in
> `feature-list.json` — single source of truth. Query it with:
>
>     python scripts/count_pending.py feature-list.json

## Session Log

### Session 0 — Init (2026-04-21)

- **SRS**: `docs/plans/2026-04-21-harness-srs.md` (46 active FR, 4 deferred to v1.1)
- **Design**: `docs/plans/2026-04-21-harness-design.md` (Approach A · asyncio + pty worker threads)
- **UCD**: `docs/plans/2026-04-21-harness-ucd.md` (Cockpit Dark, 8 UI views)
- **ATS**: `docs/plans/2026-04-21-harness-ats.md` (category mapping per requirement)
- **Deferred**: `docs/plans/2026-04-21-harness-deferred.md`
- **feature-list.json**: 17 features — 0 passing / 17 failing; `current=null`
  - UI features: 5 (F12–F16)
  - required_configs: 6 (2 env + 4 file)
  - Constraints: 9 · Assumptions: 7 · Waves: 1
- **env-guide.md**: approved §3 + §4 (approved_by=godsuriyel@gmail.com, 2026-04-21)
- **Bootstrap**: `init.sh` (175 lines, bash -n clean) + `init.ps1` (234 lines, PowerShell parser clean)
- **Skeleton**: `harness/` (Python package), `tests/`, `apps/ui/` (all `.gitkeep`-only)
- **pyproject.toml**: scopes pytest/ruff/mypy/coverage to `harness/` + `tests/`; excludes `reference/`
- **Env verified**: Python 3.12.3 · Node 22.22.1 · pytest 8.4.2 · ruff 0.15.11 · black 24.10.0 · mypy 1.20.1 · pyinstaller 6.19.0
- **Commits**: `d3119b0` (scaffold) + `a367bc9` (pyproject + svc stubs)

Handoff → next session: open new conversation; `phase_route.py` will pick first dep-ready feature (F01 App Shell & Platform Bootstrap) and route to `long-task-work-design`.

### Session 1 — Feature #1 F01 · App Shell & Platform Bootstrap · Design (2026-04-21)

- **Scripts backfilled (init omission)**: analyze-tokens.py, check_env_guide_approval.py, check_srs_trace_coverage.py, feature_paths.py, find-polluter.sh, validate_ats.py, validate_env_guide.py (commit `5b260c3`)
- **env-guide**: re-approved to v1.1 with ISO timestamp `approved_date: 2026-04-21T09:21:02+08:00` to clear same-day-commit false positive (content unchanged)
- **current lock**: `null` → `{feature_id:1, phase:"design"}` (commit `e3c3799`)
- **Feature Design**: PASS (27 test scenarios, 0 existing-code reuses, 0 assumptions)
  - Design doc: `docs/features/1-f01-app-shell-platform-bootstrap.md` (301 lines)
  - Negative ratio: 66.7% (18/27); categories: FUNC(11)/SEC(5)/BNDRY(5)/INTG(5)/PERF(1)
  - Contracts wired: IAPI-014 (provides → F07/F08/F15), IFR-006 (keyring façade), IFR-001 (auth inheritance surface)
  - Module layout: `harness/{app,config,auth,net,api}/` — 5 packages, 13 new files
- Design: DONE (docs/features/1-f01-app-shell-platform-bootstrap.md)
- current.phase: design → tdd

### Session 2 — Feature #1 F01 · App Shell & Platform Bootstrap · TDD (2026-04-21)

- target_feature: id=1, title="F01 · App Shell & Platform Bootstrap", category=core
- dependencies: [] · required_configs: []
- design doc verified on disk
- **Red** (59 tests): categories=FUNC/SEC/BNDRY/INTG/PERF; negative_ratio=0.559 (33/59); low_value_ratio=0.069 (7/102); real_test_count=6; all FAILED (ModuleNotFoundError on `harness.*` as expected)
- **Green** (59 → PASS): 12 impl files under `harness/{app,config,auth,net,api}/` + `requirements.txt` pin (fastapi 0.136.0, uvicorn 0.44.0, pydantic 2.13.3, httpx 0.28.1, keyring 25.7.0, keyrings.alt 5.0.2, pywebview 6.2.1, respx 0.23.1); uvicorn banner captured on `http://127.0.0.1:8765`; `/api/health` returns 200 with `bind=127.0.0.1`
- **Design alignment**: §4=matches (hint literal `"请运行: claude auth login"` aligned byte-for-byte), §6=matches, §8=matches; drift=resolved
- **Refactor**: ruff 0 / black 51 files unchanged / mypy strict 0 issues on 13 source files; tests remain 59/59 green
- **Quality gates**: line=95.53% (≥90%), branch=85.09% (≥80%); srs_trace_coverage 6/6 (FR-046, FR-050, NFR-007, NFR-010, NFR-012, NFR-013); real tests 6/6 pass
- **Supplement**: `tests/test_f01_coverage_supplement.py` (+34 tests for branch coverage) — total 93 tests passing
- **Risk log**: `harness/app/bootstrap.py` 88% line coverage (webview-thread teardown branches mock-only); suggest E2E PyWebView smoke in F17 packaging wave
- current.phase: tdd → st

### Feature #1: F01 · App Shell & Platform Bootstrap — PASS
- Completed: 2026-04-21
- TDD: green (93/93)
- Quality Gates: 95.53% line, 85.09% branch
- Feature-ST: 18 cases (FUNC×8 / SEC×5 / BNDRY×3 / PERF×1 / UI×1 delegation); 16 automated PASS; 2 PENDING-MANUAL (ST-FUNC-001-006 FR-046 OAuth external-action; ST-UI-001-001 NFR-010 visual → F12-F16)
- Inline Check: PASS (P2: 15/15 methods, T2: 93 tests / 13 files, D3: requirements.txt pinned, ATS Category: 6/6 covered, §4: greenfield 0 constraints)
- Cold start: 1.67s (<10s NFR-013)
- Real-service INTG: svc-api-start.sh on 127.0.0.1:8765; `ss -tnlp` confirms loopback-only (NFR-007)
- Git: 162bc03 feat: feature #1 f01-app-shell-platform-bootstrap — ST cases 18 (16 auto PASS, 2 manual)
#### Risks
- ⚠ [Coverage] harness/app/bootstrap.py 88% line (webview-thread teardown branches mock-only) — mitigation deferred to F17 PyInstaller smoke
- ⚠ [Manual] FR-046 Happy OAuth (ST-FUNC-001-006) — requires real `claude auth login` before release sign-off
- ⚠ [Cross-feature] NFR-010 visual review (ST-UI-001-001) — delegated to F12-F16 ST; must be tracked at system-wide ST

### Session 3 — Feature #2 F02 · Persistence Core · Design (2026-04-21)

- target_feature: id=2, title="F02 · Persistence Core", category=data, ui=false
- dependencies: [1] (passing) · required_configs: []
- srs_trace: FR-005 (SRS lines 177-185), FR-006 (186-194), FR-007 (195-203), NFR-005 (SRS line 728), NFR-006 (SRS line 729)
- design_section: §4.2 F02 · Persistence Core (Design lines 315-336); §5 Data Model (680-922, 含 §5.3 SQLite DDL 732, §5.4 Ticket JSON1 Payload 788, §5.6 Audit Log 行 Schema 907); §6.2 Internal API Contracts 相关片段 (1076-1209, 含 ticket supervisor 1188)
- ats_section: FR table rows 58-60, NFR rows 161-162; 5.1 scenarios 279-281, INT-020/021 322-323, INT-024 326, Err-E 331
- ucd_section: N/A (ui=false)
- current lock: `null` → `{feature_id:2, phase:"design"}` (commit `c49f666`)
- **Feature Design**: PASS (22 test scenarios, 0 existing-code reuses, 0 assumptions)
  - Design doc: `docs/features/2-f02-persistence-core.md` (287 lines, 36 KB)
  - Test inventory categories: FUNC/happy(6) + FUNC/error(6) + BNDRY/edge(6) + SEC/fs-isolation+injection(2) + INTG/db+fs(2); negative ratio 45.5%–59%
  - Contracts wired: Provider for IAPI-011 (TicketRepository.save/get/list_by_run + Ticket schema) and IAPI-009 (AuditWriter.append + AuditEvent schema); zero Consumer edges
  - Interface coverage: 5 classes / 14 public methods mapped to FR-005/006/007 + NFR-005/006 (7 ACs fully traced)
- Design: DONE (docs/features/2-f02-persistence-core.md)
- current.phase: design → tdd

### Session 4 — Feature #2 F02 · Persistence Core · TDD (2026-04-21)

- target_feature: id=2, title="F02 · Persistence Core", category=data, ui=false
- dependencies: [1] (passing) · required_configs: []
- design doc verified on disk: `docs/features/2-f02-persistence-core.md`
- env: .venv activated; Python 3.12.3; smoke test `tests/test_f01_coverage_supplement.py` → 34/34 pass in 2.46s
- mode: CLI / library (SQLite file-backed; no service processes required)
- **Red** (40 tests across 7 files): categories=FUNC/happy(6) + FUNC/error(6) + BNDRY/edge(6) + SEC/fs-isolation+injection(2) + INTG/db+fs(2) + parametric expansions; negative_ratio=0.50 (20/40); low_value_ratio=0.052 (5/96); real_test_count=3; all 40 FAILED as expected (ModuleNotFoundError `harness.domain` / `harness.persistence`); F01 regression check 93/0 untouched; added `aiosqlite==0.20.0` + `structlog==24.4.0` to requirements.txt
- **Green** (40 → PASS): 10 impl files under `harness/{domain,persistence}/` (domain: ticket.py, state_machine.py; persistence: errors.py, schema.py, runs.py, tickets.py, audit.py, recovery.py); full suite 133/133 pass in 8.71s
- **Design alignment**: §4 matches (Schema / TicketRepository / RunRepository / AuditWriter / TicketStateMachine / RecoveryScanner signatures verified); §6 matches (module layout + UPSERT + per-run asyncio.Lock + state/payload split); §8 matches (aiosqlite ^0.20 + structlog ^24.4); drift=none
- **Refactor**: `dict` → `dict[str, Any]` on `Run.payload` + `AuditEvent.payload`; removed 3 unused identifiers; black reformatted 12 f02 files + 4 pre-existing script drifts (scripts/count_pending.py, init_project.py, phase_route.py E731 lambda→def, validate_features.py F401); ruff 0 / black 69 files unchanged / mypy strict 0 issues; tests remain 133/133 green
- **Quality gates**: Gate 0 real-test PASS (3 real tests); Gate 0.5 SRS trace 5/5 (FR-005, FR-006, FR-007, NFR-005, NFR-006); line=97.39% (971/997, ≥90%); branch=89.53% (154/172, ≥80%)
- **Supplement**: `tests/test_f02_coverage_supplement.py` (+31 tests for F02 branch/line gap closure) — total 164 tests passing
- **Per-file coverage (F02)**: state_machine.py 100% · ticket.py 100% · audit.py 100% · errors.py 100% · recovery.py 100% · schema.py 100% · runs.py 97% · tickets.py 99%
- **Risk log**: harness/app/bootstrap.py 88% line (F01 regression below threshold — tracked for F01 revisit, not blocking F02); harness/persistence/runs.py branch 81→84 partial (optional-update no-field path; caller always passes ≥1 field per Design §4.2)
- current.phase: tdd → st

### Session 5 — Feature #2 F02 · Persistence Core · ST (2026-04-24)

- target_feature: id=2, title="F02 · Persistence Core", category=data, ui=false
- dependencies: [1] (passing) · required_configs: []
- env-guide.md approval: v1.1 valid (approved 2026-04-21T09:21:02+08:00)
- mode: CLI / library (SQLite file-backed; no service processes — per env-guide §1)
- **Feature-ST SubAgent**: PASS (20 ST cases · FUNC×12 / BNDRY×6 / SEC×2; negative ratio 50%)
  - ST doc: `docs/test-cases/feature-2-f02-persistence-core.md` (1019 lines, 41.2 KB)
  - SRS trace: FR-005/006/007, NFR-005/006 — all 5 covered (≥1 ST case each)
  - ATS categories satisfied: FUNC + BNDRY (FR-005/006/007, NFR-005) + SEC (NFR-006)
  - Automated execution: 20/20 PASS (backed by 68 pytest tests in 1.82s); 0 manual cases
  - `validate_st_cases.py` → VALID; `check_ats_coverage.py --feature 2` → OK
- **Inline Check**: PASS (P2: 16/16 PUBLIC methods signature-matched, T2: 71 tests across 8 F02 files all PASS, D3: aiosqlite==0.20.0 / structlog==24.4.0 / pydantic==2.13.3 vs Design §3.4 / §8.1 locks, ATS Category: 3/3 required covered, §4: greenfield 0 constraints to violate)
- Git: 9746417 feat: feature #2 f02-persistence-core — ST cases 20 (20 auto PASS)
- Carry-over in commit 9746417: [tool.mutmut] paths_to_mutate config (pyproject.toml), quality_gates.mutation_score_min=80 (feature-list.json), black reformatting of 4 scripts drift (count_pending.py / init_project.py / phase_route.py / validate_features.py), mutants/ ignore rule (.gitignore)

### Feature #2: F02 · Persistence Core — PASS
- Completed: 2026-04-24
- TDD: green (71/71 f02 tests, 164/164 full suite)
- Quality Gates: 97.39% line, 89.53% branch
- Feature-ST: 20 cases (FUNC×12 / BNDRY×6 / SEC×2); 20/20 automated PASS; 0 manual
- Inline Check: PASS
- Git: 9746417 feat: feature #2 f02-persistence-core — ST cases 20 (20 auto PASS)
#### Risks
- ⚠ [Coverage] harness/persistence/runs.py branch 84% (optional-update no-field path) — caller always passes ≥1 field per Design §4.2; revisit if new caller violates
- ⚠ [Coverage] harness/app/bootstrap.py 88% line (pre-existing F01 regression; webview-thread teardown branches mock-only) — mitigation deferred to F17 PyInstaller smoke
- ⚠ [Cross-feature] NFR-006 fs-isolation assertion is library-level only (F02 tests workdir `.harness/` writes only); system-wide `~/.harness/` + `~/.claude/` isolation verified at system-ST gate after F10

### Session 6 — Feature #3 F10 · Environment Isolation & Skills Installer · Design (2026-04-24)

- target_feature: id=3, title="F10 · Environment Isolation & Skills Installer", category=core, ui=false
- dependencies: [1] (passing) · required_configs: []
- srs_trace: FR-043 (SRS lines 547-554) · FR-044 (556-562) · FR-045 (564-571) · NFR-009 (SRS line 732)
- design_section: §4.10 F10 · Environment Isolation & Skills Installer (Design lines 503-524); §3.5 NFR-009 row (line 287); §6.1 IAPI-017/018 合同 (1112-1113 and §6.1 External Interfaces 938-1087, §6.1.5 IFR-005 git CLI 1052); §5 Data Model 若涉及 PluginRegistry schema
- ats_section: §2.1 FR rows 134-136 (FR-043/044/045) · §2.2 NFR row 165 (NFR-009) · §4 NFR method matrix row 283 · §5.1 INT-002 line 304 · INT-009 line 311 · §5.2 IAPI-017/018 mapping 358-359
- ucd_section: N/A (ui=false)
- current lock: `null` → `{feature_id:3, phase:"design"}` (commit `0a2ba27`)
- **Feature Design**: PASS via Clarification Addendum (27 test scenarios, 7 existing-code reuses incl. `shutil.copytree`+`hashlib.sha256`, 1 assumption `ASM-F10-COPY-PERF` user-approved)
  - Design doc: `docs/features/3-f10-environment-isolation-skills-install.md` (338 lines / ~51 KB)
  - Test inventory categories: FUNC/happy×6 + FUNC/error×4 + BNDRY×5 (含新增 T27 copy-isolation) + SEC×5 + INTG×7 (REST/git/audit); negative ratio 18/27=66.7% ≥40%
  - Contracts wired: Provider for **IAPI-017** (`EnvironmentIsolator.setup_run → IsolatedPaths`) + **IAPI-018** (REST `POST /api/skills/{install|pull}`); Consumer for **IFR-005** (git CLI subprocess)
  - Interface coverage: 9/9 public methods × 9 Key Types traced to FR-043/044/045 + NFR-009 ACs
  - **Design Deviation (user-approved 2026-04-24)**: 主 Design §4.10.1 `symlink plugin bundle` → 物理复制 `shutil.copytree(..., dirs_exist_ok=True)`；`PluginRegistry.ensure_bundle_symlink` → `sync_bundle(src, dst) -> PluginSyncResult`；单路径无平台分支。CON-005 反面断言限定为**源** bundle `plugins/longtaskforagent/`；副本 `.harness-workdir/<run-id>/.claude/plugins/longtaskforagent/` 允许 mtime 变化。建议后续 `long-task-increment` 回填 Design §4.10。
  - User adjudications this session: ASM-F10-ENV-OQD2 APPROVED（F10 与 env 策略解耦，延 F03 PoC）; ASM-F10-WIN-JUNCTION REVISED → copy; ASM-F10-COPY-PERF APPROVED（copytree <5MB p95 <500ms 不破 NFR-013 冷启动预算）
- Design: DONE (docs/features/3-f10-environment-isolation-skills-install.md)
- current.phase: design → tdd

### Session 7 — Feature #3 F10 · Environment Isolation & Skills Installer · TDD (2026-04-24)

- target_feature: id=3, title="F10 · Environment Isolation & Skills Installer", category=core, ui=false
- dependencies: [1] (passing) · required_configs: []
- design doc verified on disk: `docs/features/3-f10-environment-isolation-skills-install.md`
- env: .venv activated; Python 3.12.3; smoke test `tests/test_f01_coverage_supplement.py` → 34/34 pass in 2.75s
- mode: CLI / library (filesystem + subprocess + FastAPI TestClient; no server processes required)
- **Red** (51 tests across 7 files): categories=FUNC×15 + BNDRY×8 + SEC×14 + INTG×7 + MIXED_BNDRY_NEG×7; negative_ratio=0.706 (36/51); low_value_ratio=0.174 (20/115); real_test_count=3 for feature 3 (T21/T22 real git, real_fs setup walk, T26 real audit JSONL — all `@pytest.mark.real_cli`/`real_fs`); wrong_impl_probes≥8 (kills `st_mtime` vs `st_mtime_ns`, `shell=True`, reverse-copytree, hard/sym-link impl, leaky scope guard, ignored exit-code, non-idempotent copytree, wrong HTTP code mapping); all 51 FAILED as expected (`ModuleNotFoundError` on `harness.env` / `harness.skills` + 404 on unregistered router); F01+F02 baseline 164/164 untouched
- **Green** (51 → PASS): 13 impl files under `harness/{env,skills,api}/` (env: errors, models, home_guard, isolator; skills: errors, models, registry, installer; api/skills.py; api/__init__.py include_router; persistence/audit.py extended with sync `append_raw`); full suite 215/215 PASS in 9.29s; zero new deps (reused F01 httpx + FastAPI + F02 aiosqlite/structlog)
- **Design alignment (Green)**: §4 matches (9 public methods + 11 exception classes signature-match `setup_run/teardown_run/snapshot/diff_against/assert_scope/install/pull/read_manifest/sync_bundle`); §6 matches (module layout + `shutil.copytree(..., dirs_exist_ok=True, symlinks=False)` + argv-list git + `st_mtime_ns` + 64 KiB manifest cap + `.harness/run.lock` probe); §8 matches (all classDiagram/sequenceDiagram/flowchart nodes grep-verified); Design Deviation honored (physical copy, `sync_bundle(src_bundle, dst_plugin_dir)`, CON-005 reverse limited to source); drift=additive `AuditWriter.append_raw` (sync, non-breaking F02 extension supporting `env.setup/env.teardown/skills.install` audit events — §Implementation Summary intent preserved)
- **Refactor**: `.gitignore` critical fix (`env/` → `/env/` — previously hid `harness/env/` package); extracted 2 helper `def`s from lambdas in `scripts/phase_route.py` (E731); removed 7 unused imports + 1 unused local via `ruff --fix`; black normalized 16 files; design §6 updated (line 202) to explicitly document `AuditWriter.append_raw` additive extension + §Existing Code Reuse table refreshed; ruff 0 / black 88 files unchanged / mypy strict 0 issues on 34 source files; drift resolved via design update
- **Quality gates**: Gate 0 real-test PASS (11 real tests, 3 attributed to feature 3); Gate 0.5 SRS trace 4/4 covered (FR-043 ×2, FR-044 ×3, FR-045 ×2, NFR-009 ×3; uncovered=[]); line=97.28% (1468/1509, ≥90%); branch=90.71% (283/312, ≥80%)
- **Supplement**: `tests/test_f10_coverage_supplement.py` (+49 tests for branch/error-path gap closure across home_guard/registry/installer/api.skills) — total 264 tests passing
- **Per-file coverage (F10)**: home_guard.py 100% line / 96.9% branch · registry.py 100% · api/skills.py 100% · models.py 100% · errors.py 100% · isolator.py 96.2% / 83.3% · installer.py 94.4% / 90.3%
- **Risk log**: harness/env/isolator.py lines 140-141/174 (platform-specific stat-error fallbacks in copytree — not deterministic in pytest, file still 96%/83% above threshold); harness/skills/installer.py lines 55-56/90/137-139 (urlparse ValueError on malformed URL already blocked earlier + abs-Path double-check — 94%/90%, above threshold); drift followup: design §4.10 main-design symlink language should be reconciled via future `long-task-increment` (Session 6 already flagged)
- current.phase: tdd → st

### Session 8 — Increment Wave 2 · Feature Repackaging (2026-04-24)

- **Date**: 2026-04-24
- **Phase**: Increment (refactor-only)
- **Scope**: feature 颗粒度偏细 → 合并后端 9 → 4（F03+F04+F05→F18 Bk-Adapter；F07+F08→F19 Bk-Dispatch；F06+F09+F11→F20 Bk-Loop）+ 前端 5 → 3（F12 保留；F13+F14→F21 Fe-RunViews；F15+F16→F22 Fe-Config）；保留 F01/F02/F10(current.phase=st)/F12/F17；不改 SRS 层 FR/NFR/IFR
- **Changes**: Added 5 (ids 18-22), Modified 1 (id=17 deps remap), Deprecated 12 (ids 4,5,6,7,8,9,10,11,13,14,15,16)
- **Documents updated**: SRS (+7 行 §12 Revision History only), Design (+344/-350 行 · §4 重组 17→11 节 + §6.2.1 19 IAPI owner-remap + §11.1/11.2/11.3 重排), ATS (+70/-55 行 · 约 50 处 feature id 文本 remap + §5.4 Wave 2 说明), UCD (+14/-13 行 v2.1 · 13 处 remap + §8 变更历史), long-task-guide.md (2 处 remap)
- **feature-list.json**: 17 → 22 条目（10 active + 12 deprecated 审计），waves 追加 wave 2；required_configs.required_by 5 项全部 remap；F17 deps [11,13,14,15,16] → [3,12,18,19,20,21,22]
- **Impact**: 0 Hard Impact · 0 Breaking Contract · 0 FR/NFR/IFR 语义变更 · 0 代码改动；19 条 IAPI 仅 Provider/Consumer feature id 重映射，签名零变化；current lock (feature_id=3, phase=st) 保留不动
- **NFR-008 修复**：Step 3 SubAgent 发现 NFR-008（API key keyring）遗失 → 补挂到 F22 Fe-Config（SystemSettings/ApiKey tab 语义对口）
- **HIL PoC gate (FR-013 20-round ≥95%)** owner 从 F03 迁至 F18 Bk-Adapter；F18 TDD Green 阶段必须执行该 PoC
- **validate_features.py**: VALID (22 features, 2 passing, 8 failing, 12 deprecated, 2 waves, 7 UI-dep-on-failing warnings 预期)
- **count_pending**: `current=#3(st) passing=2 failing=8 (total=10, deprecated=12)`
- **Commits**:
  - `3bebbf5` design: increment wave 2 — feature repackaging
  - `ef1b8cf` ats: increment wave 2 — feature id remap
  - `31fe811` ucd: increment wave 2 — feature id remap (v2.1)
  - `f705633` feat: increment wave 2 — feature repackaging
  - `9b2f9a1` chore: increment wave 2 — long-task-guide.md feature id remap
- **Handoff**: current lock 保持 F10 (id=3) phase=st；下一会话 router 仍路由到 `long-task-work-st` 完成 F10 ST；F10 完成后 router 按新依赖图挑 F18 Bk-Adapter 作为下一个 dep-ready feature（deps = [F02, F10]，两者均为 passing 或即将 passing）

### Session 9 — Feature #3 F10 · Environment Isolation & Skills Installer · ST (2026-04-24)

- **Date**: 2026-04-24
- **Phase**: ST (Feature-ST — 黑盒验收)
- **Env lifecycle**: No server processes — environment activation only（env-guide §1 纯 CLI / library 模式，F10 特性为 backend/library）；`.venv` 已激活，`harness.env` / `harness.skills` / `harness.api` 可导入；无需 `api` / `ui-dev` dev server
- **Pre-run baseline**: `pytest tests/test_f10_*.py tests/integration/test_f10_*.py` 全绿（100 passed / 0.76s）；F01 + F02 基线未触碰
- **ST doc 生成**: `docs/test-cases/feature-3-f10-environment-isolation-skills-install.md`（26 cases：FUNC×12 + BNDRY×7 + UI×1 + SEC×6；负向比例 54%；全部 Real）
- **Validators**: `validate_st_cases.py` exit 0（VALID — 26 test case(s) | 3 warnings，均为 `ui:false` feature 的 Chrome DevTools Layer 1/2/3 警告，不适用于数据契约型 UI 用例）；`check_ats_coverage.py --strict` exit 0
- **ST 执行**: 35 unique test nodes + 17 parametrized variants = 52 执行点，全部 PASS（0.64s 合计）；FR-045 UI 类别通过 ST-UI-003-001（REST schema 数据契约覆盖）满足；F22 Fe-Config 端 DOM 渲染 E2E 留待 F22 ST
- **Session lifecycle 结束**: venv 保留激活（parent agent 可继续使用）；无服务进程需清理；环境已复位为 known-clean（tmp 清理由 `pytest tmp_path` 自动处理）

### Feature #3: F10 · Environment Isolation & Skills Installer — PASS
- Completed: 2026-04-24
- TDD: green ✓ (commit `6a6f03b`)
- Quality Gates: 97.28% line, 90.71% branch (line ≥ 90 / branch ≥ 80 per env-guide §3)
- Feature-ST: 26 cases (FUNC×12 + BNDRY×7 + UI×1 + SEC×6 · 54% negative · 100% PASS · 0 manual)
- Inline Check: PASS (P2: 10/10 PUBLIC methods, T2: 39/39 pytest node IDs, D3: stdlib only, ATS Category: strict OK, §4: greenfield — 0 violations)
- Git: `f587fb9` feat: feature #3 f10-environment-isolation-skills-install — ST cases 26 (26 auto PASS)
#### Risks
- ⚠ [ST-UI-Coverage] ST-UI-003-001 covers FR-045 UI category via REST data contract only; real DOM `显示 commit sha` end-to-end verification deferred to F22 Fe-Config ST. Feature design §Acceptance Mapping + §Design Alignment both record this cross-feature anchor; non-blocking for F10.
- ⚠ [Validator-Warning] `validate_st_cases.py` emits 3 QUALITY warnings on ST-UI-003-001 (Chrome DevTools Layer 1/2/3 heuristics); inapplicable to `ui:false` data-contract UI case — informational only.

### Session 10 — Feature #12 F12 · Frontend Foundation · Design (2026-04-24)

- target_feature: id=12, title="F12 · Frontend Foundation", category=ui, ui=true, ui_entry="/"
- dependencies: [1] (F01 passing) · required_configs: [] (Config Gate skipped — no connection strings) · constraints: [] · assumptions: []
- srs_trace: NFR-001 (SRS line 724) · NFR-010 (SRS line 733) · NFR-011 (SRS line 734); NFR 全表 §5 行 721-740
- design_section: §4.9 F12 · Frontend Foundation (Design 行 620-647)；Wave 2 overview note 行 291-294
- context anchors (SubAgent 自读): §1.4 ESI 驱动 (44-45)、§3.1-3.5 架构 (83-288)、§6.2 Internal API Contracts (1087-1161)、§7 UI/UX (1411-1425)、§8.2 前端依赖 (1453-1483)、§9 Testing Strategy (1524-1550)
- ucd_section: 1-210（全文）· 重点 §2 规则约束（35-106，含 §2.1 a11y / §2.2 动效含 prefers-reduced-motion、§2.5 中文排印增补、§2.6 状态色、§2.7 Icon / §2.8 Data Density）· §4 页面指针 (126-142) · §5 组件指针 + F12 实施规约 (146-173) · §7 视觉回归 SOP (194-206)
- env-guide §4: greenfield empty（无存量内部库强制 / 禁用 API / 构建系统约定）
- Internal API Contracts（F12 为 Provider）: IAPI-001 (WebSocket multi-channel → F21)、IAPI-002 (REST → F21/F22)；Requires: IAPI-001 由 F20 提供、IAPI-019 RunControl 由 F20 提供
- current lock: `null` → `{feature_id:12, phase:"design"}` (commit `313ae55`)
- **Feature Design**: PASS（assumption_count=0，无审批关卡）
  - Design doc: `docs/features/12-f12-frontend-foundation.md`（443 行 / ~47 KB）
  - Test Inventory: 41 cases · 负向比例 46.3% (19/41) ≥ 40%
  - 类别覆盖: FUNC/happy + FUNC/error + BNDRY/edge + UI/render (13) + PERF/route-switch + INTG/websocket-rest-static + SEC/url-guard + i18n-guard
  - Existing Code Reuse: 9 reused / 11 searched（6 prototype files 来自 docs/design-bundle/eava2/project/ + 2 F01 integration points + 1 tokens.css byte-identical clone）
  - §4 Internal API Contracts: F12 为 IAPI-001 (WebSocket multi-channel) / IAPI-002 (REST 30 routes) 的 **Consumer**；无 Provider 合同（FE imports 为 internal）
  - Visual Rendering Contract: 10 元素带具体 DOM 选择器（`[data-component="app-shell|sidebar|top-bar|phase-stepper|ticket-card"]` 等）；rendering tech = React 18 DOM + Tailwind + CSS vars + `@keyframes hns-pulse`；10 正向断言 + 5 交互断言；像素回归 1280×900 + 1440×840 SOP 对齐 UCD §7
  - Interface 覆盖: 13 public API（HarnessWsClient.connect/subscribe/disconnect/heartbeat$, useWs, createApiHook, apiClient.fetch, createSlice, AppShell, PageFrame, Sidebar, PhaseStepper, TicketCard, Icons）+ 3 IAPI 集成点 trace 到 NFR-001/010/011 + 7 verification_steps
- Design: DONE (docs/features/12-f12-frontend-foundation.md)
- current.phase: design → tdd

### Session 11 — Feature #12 F12 · Frontend Foundation · TDD (2026-04-24)

- target_feature: id=12, title="F12 · Frontend Foundation"
- **Red**: 41 tests written across 18 files (3 pytest + 13 vitest + 3 Playwright queued for ST); categories=FUNC,BNDRY,UI,SEC,PERF,INTG; negative_ratio≈0.51 (21/41); real_test_count=3 F12 real; Rule 1-7 all PASS; all feature tests FAIL for right reason (module-not-found / assertion), sanity smoke PASS
- **Green**: minimal impl landed in apps/ui/src/ (ws/, api/, store/, app/, components/, theme/, main.tsx) + harness/api/__init__.py (added /ws/{run,hil,stream,anomaly,signal} + StaticFiles('apps/ui/dist') mount) + scripts/check_{source_lang,tokens_fidelity}.sh; all_tests_pass=true; design alignment §4/§6/§8 matches, drift=none; env_guide_synced=true
- **Refactor**: ruff + black --check + mypy + tsc --noEmit all 0 violations; stale @ts-expect-error directives (18) dropped in test files; createApiHook typing refactored to method-literal overloads (no unsoundness); extracted readApiBase/isRecord/storeHost/resolveWsBase helpers; tokens.css byte-identical verified
- **Quality**: 
  - Gate 0 (Real Test): PASS (3 F12 real tests)
  - Gate 0.5 (SRS Trace): PASS, uncovered_fr_ids=[] (NFR-001→app-shell/ws/use-ws tests, NFR-010→source-lang-guard, NFR-011→app-shell/icons; T34 Playwright deferred to ST)
  - Backend coverage: line 95.89% / branch 90.45% (thresholds 90/80 met)
  - Frontend coverage: line 97.89% / branch 87.00% / functions 95.23% / statements 97.89% (all above thresholds)
  - Per-F12-module: app-shell.tsx 97.64%/81.81%; tokens-inline.ts excluded (Vite/Node shim — Node fallback unreachable under Vite bundling)
- Supplement tests: 38 + 4 = 42 frontend tests added to close branch/function gaps (total frontend vitest 83/83 green)
- Scaffolding added: @vitest/coverage-v8@2.1.4 devDep + coverage block in vitest.config.ts + coverage.exclude for tokens-inline.ts (build-shim rationale)
- Test results: pytest 270/270 green (was 264, +6 F12); vitest 83/83 green (was 0, new F12 suite)
- current.phase: tdd → st

### Session 12 — Feature #12 F12 · Frontend Foundation · ST (2026-04-24)

- target_feature: id=12, title="F12 · Frontend Foundation", ui=true, ui_entry="/"
- srs_trace: NFR-001 (UI p95 < 500ms) · NFR-010 (仅简体中文) · NFR-011 (HIL 控件标注 — F12 承接基座义务，实际文本由 F21 渲染)
- ATS mapping: NFR-001 `PERF,UI` · NFR-010 `FUNC,UI` (Manual: visual-judgment 允许) · NFR-011 `FUNC,UI`
- **Env lifecycle**: SubAgent 自管理；`api` (PID 316923 port 8765) + `ui-dev` (PID 316933 port 5173) 启动 → 健康检查通过 → ST 全量执行 → 停止 + 端口释放验证
- **ST doc 生成**: `docs/test-cases/feature-12-f12-frontend-foundation.md`（23 cases：FUNC×8 + BNDRY×3 + UI×9 + SEC×2 + PERF×1；1 manual/known-gap）
- **Validators**: `validate_st_cases.py` VALID — 23 cases | 20 quality warnings（UI cases Layer-1/2/3 heuristics，含 Vitest-only 纯 DOM 断言，非 block，F3 同模式）；`check_ats_coverage.py` strict OK；`check_source_lang.sh` exit 0；`check_tokens_fidelity.sh` exit 0
- **ST 执行**: 22/22 auto cases PASS（含 Vitest 14 files / 83 tests + Playwright f12-route-switch + f12-devtools-snapshot），1 manual/known-gap ST-UI-012-009 pixelmatch 延伸至 F21/F22
- **Chrome DevTools MCP evidence**: AppShell bg=rgb(10,13,18)=#0A0D12 ✓ · Sidebar 240px@1280vw / 56px@1100vw ✓ · TopBar 56px ✓ · HIL 徽标 zero-miss ✓ · 8 lucide-react 图标 stroke-width=1.75 ✓ · Sidebar 交互 8/8 active switch（overview→hil→settings）✓ · 0 console errors
- **AI self-fixes（SubAgent 内部）**:
  1. `sidebar.tsx:33` — NAV_ITEM label "Skills" → "提示词 & 技能"（NFR-010 合规）
  2. `scripts/check_source_lang.sh` + 新建 `scripts/check_source_lang.py` — 消除 112 误报，新增多行 throw / CSS nested var() / 属性白名单识别
  3. `apps/ui/index.html` — 内联 data:image/svg+xml favicon（消除 /favicon.ico 404 console 噪音）
  4. `apps/ui/src/main.tsx` — 补齐 8 nav id 占位路由（Sidebar 可交互 2/8 → 8/8；F12 "no FR business logic" 边界保持）
- **Inline Check**: PASS (P2: 9/9 PUBLIC 方法签名匹配 · T2: 11 抽查 T-ID 全命中 · D3: React 18.3.1 / Vite 5.4.11 / TS 5.5.4 / Tailwind 3.4.14 / TanStack 5.59.20 / Zustand 5.0.1 / router 7.0.1 / lucide 0.441.0 全对齐 Design §3.4 · U1: tokens.css byte-identical + 硬编码色均属 Design "Existing Code Reuse" 直译非漂移 · ATS Category: strict OK · §4: greenfield — 0 violations)

### Feature #12: F12 · Frontend Foundation — PASS
- Completed: 2026-04-24
- TDD: green ✓ (commit `21c26c8`)
- Quality Gates: 前端 line 97.89% / branch 87.00%；后端 line 95.89% / branch 90.45%（均过 90/80 阈值）
- Feature-ST: 23 cases (FUNC×8 + BNDRY×3 + UI×9 + SEC×2 + PERF×1 · 22 auto PASS · 1 manual/known-gap)
- Inline Check: PASS
- Git: `bcd4140` feat: feature #12 f12-frontend-foundation — ST cases 23 (22 auto PASS + 1 known-gap)
#### Risks
- ⚠ [Known-Gap] ST-UI-012-009 pixelmatch 基线 PNG (`docs/design-bundle/eava2/project/pages/overview-1280.png` / `overview-1440.png`) 尚未生成；`apps/ui/e2e/f12-visual-regression.spec.ts` 内暂以 `expect(false).toBe(true)` 占位。Feature Design Test Inventory T35/T36 之后的 note 已预申报此 gap；按 UCD §7 SOP 第 5 步 ST-evidence archive 路径，归属 F21 Fe-RunViews / F22 Fe-Config 的 ST 阶段承接（RunOverview 页面体落地后）。不 block F12 ATS UI 类别最小覆盖（ST-UI-012-001..008 通过 live DevTools MCP 断言 + Vitest DOM 断言 + tokens fidelity + source-lang guard 覆盖全 11 §VRC 元素）。
- ⚠ [Validator-Warning] `validate_st_cases.py` 对 ST-UI-012-002..009 发 20 条 QUALITY 警告（Chrome DevTools Layer-1/2/3 启发式与 Vitest-only DOM-assertion 纯数据契约用例不完全适配）；信息级，与 F3 同模式，不 block。
- ⚠ [Stale-Scripts] 会话开始前 `scripts/{count_pending,init_project,phase_route,validate_features}.py` 已存 dirty 改动，非本 feature 范围；本次 commit 显式排除。留待后续 chore commit 处理。

### Session 13 — Feature #18 F18 · Bk-Adapter — Agent Adapter & HIL Pipeline · Design (2026-04-24)

- target_feature: id=18, title="F18 · Bk-Adapter — Agent Adapter & HIL Pipeline", category=core, ui=false, wave=2
- dependencies: [2 (Persistence Core ✓ passing), 3 (Env Isolation ✓ passing)] · required_configs: [] (Config Gate 跳过 — 无连接串键) · priority=high · status=failing
- srs_trace: FR-008/009/011/012/013/014/015/016/017/018 (C.HIL + D.ToolAdapter 段 · SRS 行 206-307) · NFR-014 (SRS 行 737) · IFR-001/002 (SRS 行 758-759) · ASM-003 PoC (SRS 行 771)
- design_section: §4.3 F18 Feature Integration Spec (Design 行 339-397)；§4.11 Deprecated IDs (670-690，F03/F04/F05 → F18 合并上下文)
- context anchors (SubAgent 自读): §1 Drivers (14-57)、§2 Approach A asyncio + worker-thread pty (58-80)、§3 Architecture (81-290)、§5 Data Model incl. Ticket JSON1 (691-933)、§6.1.1/6.1.2 IFR-001/002 外部接口 (941-990)、§6.2 Internal API Contracts incl. Stream/HIL/Ticket supervisor schemas (1087-1410)、§8 Deps (1426-1523)、§9 Testing Strategy + RTM (1524-1550)、§11.2/§11.3 Task Decomp + Dep Chain (1587-1686)、§13 Conventions (1710-1712)
- env-guide §4: 存量约束均 greenfield empty（§4.1 强制内部库 / §4.2 禁用 API / §4.3 风格基线 / §4.4 构建约定）
- Internal API Contracts 角色: Provider → IAPI-005/006/007/008 (F20 orchestrator internal) + /ws/hil (IAPI-001)；Consumer → IAPI-009 AuditWriter · IAPI-011 TicketRepository · IAPI-015 ModelResolver (F19，**stubbed via A1**) · IAPI-017 EnvironmentIsolator
- current lock: `null` → `{feature_id:18, phase:"design"}` (commit `bf40ed2`)
- **Feature Design**: PASS（assumption_count=1 · 审批关卡：user Approve 接受 A1 stub 方案）
  - Design doc: `docs/features/18-f18-bk-adapter-agent-adapter-hil-pipelin.md`（420 行 / ~45 KB）
  - Test Inventory: 32 cases · 负向比例 50% (16/32) ≥ 40%
  - 类别覆盖: FUNC (13) / BNDRY (7) / SEC (1 explicit + embedded in T03/T23/T25) / PERF (1) / INTG (3 × CLI/audit) / Protocol (2)
  - Interface Contract: 21 public methods across 10 classes — ToolAdapter Protocol + ClaudeCodeAdapter + OpenCodeAdapter + PtyWorker + JsonLinesParser + BannerConflictArbiter + HilExtractor + HilControlDeriver + HilWriteback + HilEventBus；每条 SRS AC (FR-008/009/011/012/013/014/015/016/017/018 + NFR-014 + IFR-001/002) 均追溯到 ≥1 postcondition
  - Existing Code Reuse: 10 reused symbols (DispatchSpec / HilQuestion / HilOption / HilAnswer / HilInfo / AuditEvent / state_machine.validate_transition / AuditWriter.append / IsolatedPaths / EnvironmentIsolator.setup_run)；0 re-implementation
  - UML: 1 classDiagram (9 classes) + 2 sequenceDiagram/stateDiagram (Running/Crashed PTY + Ticket HIL transitions) + 2 flowchart TD (OpenCode build_argv · BannerConflictArbiter) — 33 diagram elements 全追溯至 Test Inventory
  - ATS alignment: FR-008..018 + NFR-014 + IFR-001/002 mapping rows 全 confirmed in `docs/plans/2026-04-21-harness-ats.md`；INT-001 HIL full round-trip → T29/T30；Err-B/Err-D/Err-J → T07/T17/T08
  - **Assumption A1 (Approved)**: TDD Green 阶段先用 `ModelResolverStub.resolve(ctx) → ResolveResult(model=ctx.ticket_override or ctx.run_default, provenance=...)` 实现 F19 的 IAPI-015 契约；签名与 Design §6.2.4 一致；F19 落地后仅在 orchestrator 层替换，F18 代码零变更。理由：Wave 2 的 F19 与 F18 无硬顺序约束；stubbing 一个仅影响 DispatchSpec `model` 字段的 Requires 合同不改变 Interface Contract 签名、Boundary Conditions 或 Test Inventory 预期。
- Design: DONE (docs/features/18-f18-bk-adapter-agent-adapter-hil-pipelin.md)
- current.phase: design → tdd

### Session 14 — Feature #18 F18 · Bk-Adapter — Agent Adapter & HIL Pipeline · TDD (2026-04-24)

- target_feature: id=18, title="F18 · Bk-Adapter — Agent Adapter & HIL Pipeline", category=core, ui=false, wave=2
- current lock: `{feature_id:18, phase:"tdd"}` → `{feature_id:18, phase:"st"}`
- **Red**: 34 tests written across 9 files — FUNC/happy · FUNC/error · BNDRY/edge · SEC/bndry · PERF/latency · INTG/cli · INTG/audit · INTG/fs；Rule 1-7 all green（negative_ratio=0.559, low_value_ratio=0.028, real_test_count=2：test_f18_real_cli.py + test_f18_real_fs_hooks.py）；UML 全部元素覆盖（classDiagram 9/9, sequenceDiagram 13 msgs, stateDiagram PTY + Ticket, 2 flowchart decisions）；all 34 FAILED as expected
- **Green**: 26 impl files across harness/adapter · harness/pty · harness/stream · harness/hil（含 errors/process/protocol/protocol.py 与 platform-specific posix/windows pty + opencode hooks 子模块）；32/34 F18 tests PASS（T29/T30 `@pytest.mark.real_cli` 按 design §6 Impl Summary (6) 延后到 PoC gate，FR-013 是独立 PoC 验收项）；完整后端 302 passed + 2 deselected（无回归）；Existing Code Reuse 10 symbols 0 重实现（DispatchSpec/HilQuestion/HilOption/HilAnswer/HilInfo/AuditEvent/state_machine/AuditWriter/IsolatedPaths/EnvironmentIsolator）；requirements.txt 新增 `ptyprocess==0.7.0 ; sys_platform != "win32"`
- **Refactor**: ruff ✓ / black ✓ (68 files) / mypy `--strict` ✓ (59 source files, 0 issues)；仅清理未用 import + black 格式化 + 修正 type-ignore 代码，无契约/功能变更；pytest 重跑 302 passed + 2 deselected（与 Green baseline 一致）；design_alignment: §4=matches, §6=matches, §8=N/A (Boundary Conditions + Existing Code Reuse 替代), drift=none
- **Quality v1 (FAIL → 扩测)**: line=87.65% (< 90%)、branch=73.58% (< 80%)；srs_trace 13/13 全覆盖；主要差距在 PTY 层 + opencode 运行时分支；用户选择扩测（Recommended）
- **Coverage Supplement**: 新增 2 文件 86 测试 —— `tests/test_f18_coverage_supplement.py`（80 用例，纯单元 edge 分支）+ `tests/integration/test_f18_pty_real_subprocess.py`（6 用例，用真 `/bin/cat` 子进程驱动真 PTY，`@pytest.mark.real_fs`，Rule 5a 合规无 mock primary deps）；实现文件、契约、feature-list.json **零改动**
- **Quality v2 (PASS)**:
  - Gate 0 Real Test: PASS（17 real tests，F18 有 2 个）
  - Gate 0.5 SRS Trace: PASS（13/13 FR-IDs 全覆盖：FR-008/009/011/012/013/014/015/016/017/018 + NFR-014 + IFR-001/002）
  - Gate 1 Coverage: line=**95.03%**（≥90%）、branch=**91.87%**（≥80%）
  - Gate 2 Verify & Mark: 388 passed · 0 failed · 0 skipped · 2 deselected (T29/T30 real_cli)
- current.phase: tdd → st
- Next session: `long-task-work-st`（feature ST acceptance for #18）

### Session 15 — Feature #18 F18 · Bk-Adapter — Agent Adapter & HIL Pipeline · ST (2026-04-24)

- target_feature: id=18, title="F18 · Bk-Adapter — Agent Adapter & HIL Pipeline", category=core, ui=false, wave=2
- srs_trace: FR-008/009/011/012/013/014/015/016/017/018 + NFR-014 + IFR-001/002
- ATS mapping: FR-008 `FUNC,BNDRY,SEC` · FR-009 `FUNC,BNDRY,SEC` · FR-011 `FUNC,BNDRY,SEC` · FR-012 `FUNC,BNDRY` · FR-013 `FUNC,BNDRY,PERF` · FR-014 `FUNC,BNDRY` · FR-015 `FUNC,BNDRY` · FR-016 `FUNC,BNDRY` · FR-017 `FUNC,BNDRY` · FR-018 `FUNC,BNDRY` · NFR-014 `FUNC` · IFR-001 `FUNC,BNDRY,SEC` · IFR-002 `FUNC,BNDRY,SEC`
- **Env lifecycle**: No server processes — environment activation only（env-guide §1 纯 CLI / library 模式，F18 为 backend-only 后端单向数据通道；`.venv` 已激活；无需 `api` / `ui-dev` dev server）
- **ST doc 生成**: `docs/test-cases/feature-18-f18-bk-adapter-agent-adapter-hil-pipeline.md`（39 cases：FUNC×26 + BNDRY×7 + SEC×4 + PERF×2；1:1 映射 Feature Design Test Inventory T01–T32 + CapabilityFlags + env-whitelist + provider-consistency + backward-compat + NFR-014 mypy）
- **Validators**: `validate_st_cases.py` → `VALID — 39 test case(s)` · `check_ats_coverage.py --strict --feature 18` → `ATS COVERAGE OK` · `mypy --strict harness/adapter/` → `Success: no issues found in 7 source files`
- **ST 执行**: `pytest tests/test_f18_*.py tests/integration/test_f18_pty_real_subprocess.py tests/integration/test_f18_real_fs_hooks.py -q` → `118 passed in 1.49s`（118 pytest functions → 37 ST rows PASS）
- **Manual cases（external-action，保留 `已自动化: No`，非静默跳过）**:
  - ST-FUNC-018-018（T29）: real claude CLI HIL round-trip — 需用户完成 `claude login` OAuth + 提供稳定触发 AskUserQuestion 的 prompt
  - ST-PERF-018-002（T30 = FR-013 PoC gate）: 20 × HIL round-trip 成功率 ≥95% — 同前置；若 <19/20 → 按 SRS FR-013 AC-2 冻结 HIL FRs 并上报
- **Inline Check**: PASS (P2: 13/13 PUBLIC 方法签名匹配（ToolAdapter 6 方法 + ClaudeCodeAdapter/OpenCodeAdapter build_argv + OpenCodeAdapter.ensure_hooks/parse_hook_line + PtyWorker.start/write/close + JsonLinesParser.feed/events + BannerConflictArbiter.arbitrate + HilExtractor.extract + HilControlDeriver.derive + HilWriteback.write_answer + HilEventBus.publish_opened/answered） · T2: 70/70 ST 测试函数引用 grep 命中 · D3: pydantic 2.13.3 / ptyprocess 0.7.0 / structlog 24.4.0 与 requirements.txt 对齐 · UCD: N/A (ui:false) · ATS Category: strict OK · §4: greenfield — 0 violations)

### Feature #18: F18 · Bk-Adapter — Agent Adapter & HIL Pipeline — PASS
- Completed: 2026-04-24
- TDD: green ✓ (commit `73b69de`)
- Quality Gates: line 95.03% / branch 91.87%（≥ 90 / 80）
- Feature-ST: 39 cases (FUNC×26 + BNDRY×7 + SEC×4 + PERF×2 · 37 auto PASS · 2 manual [MANUAL_TEST_REQUIRED])
- Inline Check: PASS
- Git: `26a076a` feat: feature #18 f18-bk-adapter-agent-adapter-hil-pipeline — ST cases 39 (37 auto PASS + 2 manual)
#### Risks
- ⚠ [Manual] ST-FUNC-018-018 (T29) — real `claude` CLI HIL round-trip 需用户 OAuth 登录 + 提供稳定触发 AskUserQuestion 的 prompt；release sign-off 前必须人工跑一次
- ⚠ [Manual/Release-Gate] ST-PERF-018-002 (T30 = FR-013 PoC gate) — 20 × HIL round-trip ≥ 95%；若未达标按 SRS FR-013 AC-2 必须冻结 HIL FRs 并上报；release 前强制执行
- ⚠ [Coverage] harness/app/bootstrap.py 88% line（pre-existing F01 regression；webview-thread teardown 分支仅 mock 覆盖）— 由 F17 PyInstaller smoke 承接
- ⚠ [Stale-Scripts] 会话开始前 `scripts/{count_pending,init_project,phase_route,validate_features}.py` 已存 dirty 改动，非本 feature 范围；本次 commit 继续显式排除，延续 Session 12 的处理方针，留待独立 chore commit 清理

### Session 16 — Feature #19 F19 · Bk-Dispatch — Model Resolver & Classifier · Design (2026-04-24)

- target_feature: id=19, title="F19 · Bk-Dispatch — Model Resolver & Classifier", category=core, ui=false, wave=2
- srs_trace: FR-019/020/021/022/023 + IFR-004
- dependencies: [1] (F01 已 passing — 复用 harness.auth.keyring_facade + harness.config + harness.api FastAPI skeleton)
- **current lock**: `null` → `{feature_id:19, phase:"design"}` (commit `971ac02`)
- **Context**: Consolidates 旧 F07 Model Override Resolver + 旧 F08 Classifier Service；dispatch 决策面（spawn 前 4 层 ModelResolver → spawn 后 Classifier OpenAI-compat LLM 分类 ticket）；共享 IAPI-014 keyring + ClassifierProviderPresets
- **Config Gate**: 跳过（required_configs=[]，无连接串键）
- **env-guide approval**: OK (v1.1, approved_date 2026-04-21T09:21:02+08:00)
- **Feature Design**: PASS — 46 test cases across FUNC/happy(14) + FUNC/error(11) + BNDRY(7) + SEC(7) + INTG(10)；negative ratio 25/46 ≈ 54.3%（≥ 40%）；12 public methods 覆盖 FR-019..023 所有 AC + IFR-004；5 existing-code reuses（KeyringGateway / KeyringServiceError / ConfigStore / ApiKeyRef / harness.api include_router pattern）
  - Design doc: `docs/features/19-f19-bk-dispatch-model-resolver-classifie.md` (418 lines)
  - Contracts wired: Provides IAPI-015（→F18）、IAPI-010（→F20）、IAPI-002 subroutes `/api/settings/{model_rules,classifier,classifier/test}` + `/api/prompts/classifier`（→F22）；Requires IAPI-014（F01 keyring）+ IFR-004（外部 OpenAI-compat HTTP）
- **5 Assumptions (approved)**:
  1. SSRF 白名单 = preset 域 + endswith 精确子域；custom 拒私网/loopback/link-local/非 https
  2. PromptStore v1 history 仅存 `{rev, saved_at, hash, summary}`；full body diff 延至 v1.1
  3. RuleBackend 优先级：context_overflow → rate_limit → permission_denied → exit_code=0 → skill_error
  4. `ClassifierHttpError` 仅内部抛，FallbackDecorator 捕获后 rule 兜底；classify 对外永不抛
  5. `ClassifierService.classify` 内部从 PromptStore.get() 取 current prompt，调用方无需传
- Design: DONE (docs/features/19-f19-bk-dispatch-model-resolver-classifie.md)
- current.phase: design → tdd

### Session 17 — Feature #19 F19 · Bk-Dispatch — Model Resolver & Classifier · TDD (2026-04-25)

- target_feature: id=19, title="F19 · Bk-Dispatch — Model Resolver & Classifier"
- Red: 46 tests written across 13 files (10 unit + 3 integration); categories=FUNC/happy(14)·FUNC/error(10)·BNDRY/edge(8)·SEC/fs-perm(1)·SEC/keyring(1)·SEC/ssrf(3)·SEC/secret-leak(1)·SEC/path-traversal(1)·INTG/http(3)·INTG/http-shape(1)·INTG/fs(1)·INTG/keyring(1); negative_ratio=0.543 (25/46, ≥0.40); low_value_ratio=0.000; real_test_count=3 (real HTTP loopback / real tmp_path FS / `keyring.backends.fail`); all FAILED as expected ✓
- Green: minimal impl passes 46/46 tests in 10.58s; impl scope = `harness/dispatch/{model,classifier}/*.py` + `harness/api/{settings,prompts}.py` + `harness/api/__init__.py` router wiring; design §4 (12 public methods signature-match) / §6 (module layout + call chain) / §8 (11 pydantic schemas) — drift=none; env-guide §4 greenfield (no sync needed)
- Refactor: no code changes required — ruff/black/mypy 0 violations on F19 scope (29 files); F19 tests 46/46 still green; design alignment re-verified (UML classDiagram 8 NEW classes · sequenceDiagram 9 messages · flowchart TD 7 decision branches all grep-verified)
- Quality Gates: round 2 PASS — line 98.37% (≥90%) · branch 84.62% (≥80%); srs_trace all 6 covered (FR-019/020/021/022/023/IFR-004); 52 supplement tests added (T47–T98) to `tests/test_f19_coverage_supplement.py`; IFR-004 literal added to `tests/integration/test_f19_real_http.py` module/T31 docstrings
- Final suite: 98/98 F19 tests green
- current.phase: tdd → st

### Session 18 — Feature #19 F19 · Bk-Dispatch — Model Resolver & Classifier · ST (2026-04-25)

- target_feature: id=19, title="F19 · Bk-Dispatch — Model Resolver & Classifier", category=core, ui=false, wave=2
- srs_trace: FR-019/020/021/022/023 + IFR-004
- ATS mapping: FR-019 `FUNC,BNDRY,UI`（UI 由 F22 SystemSettings 模型规则表承担）· FR-020 `FUNC,BNDRY` · FR-021 `FUNC,BNDRY,SEC,UI`（UI 由 F22 SystemSettings Classifier 卡片承担）· FR-022 `FUNC,BNDRY` · FR-023 `FUNC,BNDRY,SEC` · IFR-004 `FUNC,BNDRY,SEC,PERF`
- **Env lifecycle**: No server processes — environment activation only（env-guide §1 纯 library / TestClient 模式；REST 路由经 `FastAPI TestClient` 直接装载 `harness.api:app`，无需启动 `api`/`ui-dev` dev server；F19 后端独立单元）
- **ST doc 生成**: `docs/test-cases/feature-19-f19-bk-dispatch-model-resolver-classifie.md`（61 cases：FUNC×46 + BNDRY×7 + SEC×7 + PERF×1，UI 0；负向占比 ~52% ≥ 40%；映射 Test Inventory T01–T46，部分 cases 聚合多个底层 pytest 函数到单一黑盒视角）
- **Validators**: `validate_st_cases.py --feature 19` → `VALID — 61 test case(s)` · `check_ats_coverage.py --feature 19` → `ATS COVERAGE OK — checked feature #19`（UI 类别按 dispatcher 预批准豁免：UI 由 F22 承担，对齐 F18 先例）
- **ST 执行**: `pytest tests/test_f19_*.py tests/integration/test_f19_*.py -q` → `98 passed in 10.86s`（98 个底层 pytest 函数 → 61 ST rows 全 PASS · 0 manual · environment_cleaned=true）
- **Inline Check**: PASS (P2: 12/12 PUBLIC 方法签名匹配（ModelResolver.resolve · ModelRulesStore.load/save · ClassifierService.classify/test_connection · LlmBackend.invoke · RuleBackend.decide · FallbackDecorator.invoke · PromptStore.get/put · ProviderPresets.resolve/validate_base_url）· T2: 14 F19 测试文件 98 functions all green · D3: httpx 0.28.1 / fastapi 0.136.0 / pydantic 2.13.3 / keyring 25.7.0 / pytest 8.4.2 / respx 0.23.1 与 env-guide §3 工具版本表对齐 · UCD: N/A (ui:false) · ATS Category: OK · §4: greenfield — 0 violations)

### Feature #19: F19 · Bk-Dispatch — Model Resolver & Classifier — PASS
- Completed: 2026-04-25
- TDD: green ✓ (commit `a84a96f`)
- Quality Gates: line 98.37% / branch 84.62%（≥ 90 / 80）
- Feature-ST: 61 cases (FUNC×46 + BNDRY×7 + SEC×7 + PERF×1 · 61 auto PASS · 0 manual)
- Inline Check: PASS
- Git: `c4bc3cb` feat: feature #19 f19-bk-dispatch-model-resolver-classifier — ST cases 61 (61 auto PASS)
#### Risks
- ⚠ [Coverage] branch 84.62% — 4.62 pp 缓冲，ProviderPresets / FallbackDecorator audit 分支边界改动易触底；后续若改动 fallback 路径需重跑 quality gate
- ⚠ [Stale-Scripts] 会话开始前 `scripts/{check_source_lang,count_pending,init_project,phase_route,validate_features}.py` 已存 dirty 改动，非本 feature 范围；本次 commit 继续显式排除，延续 Session 12/15 的处理方针，留待独立 chore commit 清理

### Session 19 — Feature #19 · Real-External LLM Smoke (Post-ST · 2026-04-25)

- Trigger: 用户请求"使用真实 MiniMax key 做真实测试"。F19 已 passing，本会话为 post-ST ad-hoc smoke，不改 feature-list.json status / 不复开 current 锁。
- **Key 持久化**: `KeyringGateway().set_secret("harness-classifier", "minimax", <key>)` → SecretService backend（chainer 链路 `Keyring → PlaintextKeyring`，dbus Secret Service 优先吸收，未触发 PlaintextKeyring 降级警告）；key **不入任何文件 / 不入 git**，符合 NFR-008 + IFR-006。
- **新增 marker `real_external_llm`** 注册于 `tests/conftest.py`：① `pytest_configure` `addinivalue_line` 注册；② `_null_keyring_for_unit_tests` autouse fixture 把它加入豁免集，并修复一处缺陷——之前 fixture 仅"不重置"keyring，但前序 unit test 留下的 null backend 会持续；新逻辑改为对 real-* 测试**主动恢复** `keyring.backends.chainer.ChainerBackend()`，确保 real-LLM 测试拿到平台默认 backend。
- **新测试** `tests/integration/test_f19_real_minimax.py`（2 cases，标 `real_external_llm`，缺 key 时 `pytest.skip`）：
  - `test_f19_real_minimax_test_connection_round_trip` — 真打 `https://api.minimax.chat/v1/chat/completions` ping，断言 IFR-004 10 s budget；接受 ok=True 或已知 error_code（401/connection_refused/dns_failure/timeout），401 显式 fail 提示 key 失效。
  - `test_f19_real_minimax_classify_never_raises` — 真发完整 OpenAI-compat 请求（含 `response_format=json_schema strict`），断言 IAPI-010 永不抛 + Verdict 在合法枚举内 + 整体 ≤ 12 s；若 fallback 到 rule，必须存在至少一条 audit `classifier_fallback` 事件。
- **Model 名修订**：`ProviderPresets["minimax"].default_model` 由占位 `abab6.5s-chat` 改为 `MiniMax-M2.7-highspeed`（用户提供）；同步更新 `tests/test_f19_coverage_supplement.py` PUT/GET 路由 fixture 与 `tests/integration/test_f19_real_minimax.py`。
- **执行结果**（key 在 keyring 时，新 model 名）：2/2 PASSED in ~1 s。Ad-hoc verbose 抓到的真实 endpoint 行为：
  - `test_connection`（最简单 ping body）: **ok=True, latency_ms=3026, elapsed=3.122s** — endpoint + key + model 名全合法
  - `classify`（带 `response_format=json_schema strict`）: HTTP 400 → `ClassifierHttpError(http_400)` → `FallbackDecorator` 捕获 → `RuleBackend.decide` → `Verdict(verdict="COMPLETED", backend="rule", reason="clean exit (code=0, empty stderr, no banner)")` elapsed=0.358s；audit_sink 写入 `{event:"classifier_fallback", cause:"http_400", exc_class:"ClassifierHttpError"}` 一行。
  - **关键契约验证**：MiniMax 不支持 OpenAI-compat 的 `response_format=json_schema strict` 字段（HTTP 400 拒收），`classify` 永不抛 + 走 rule 兜底 + audit 留痕（IAPI-010 / FR-022 / FR-023 三层契约在生产环境中真实成立）。
- **全套回归**: `pytest -q` → 100/100 F19 测试全 PASS；其他特性测试套件未被 conftest 改动影响（real_http / real_fs / real_keyring 既有测试保持原行为，因 marker 集合扩展是叠加非替换）。
- **Doc 更新**:
  - `env-guide.md` §5 第三方服务表 `OpenAI-compatible HTTP endpoint` 行注明可选 `real_external_llm` smoke；新增 §5"Real-External LLM Smoke（可选 · F19 Classifier）"块说明 key 注入命令 + 执行命令 + 注销命令；frontmatter `approved_sections` 仍为 `["§3", "§4"]`，本次仅改 §5（无需重新审批，`check_env_guide_approval.py` 通过）。
  - `.env.example` keyring 占位段补充 `KeyringGateway().set_secret(...)` 调用示例 + 指向 env-guide.md §5。
- **本次 commit 范围**: `tests/integration/test_f19_real_minimax.py` (新) · `tests/conftest.py` (marker + chainer 恢复) · `env-guide.md` (§5 新增) · `.env.example` (keyring 占位说明)；不动 feature-list.json / 不动 RELEASE_NOTES.md（feature #19 已 passing）。

#### Session 19 Findings（待评估）
- ⚠ [Provider-Compat] **MiniMax 不支持 `response_format=json_schema strict`** — 真打实测：endpoint + key + model 名（`MiniMax-M2.7-highspeed`）全合法（test_connection 200 OK），但带 `response_format: {type:"json_schema", json_schema:{...strict:true...}}` 的 classify body 被 MiniMax 端拒收 HTTP 400。根因：MiniMax OpenAI-compat 当前不实现该字段（GLM / OpenAI 实现）。**当前 fallback 链能兜底**（不影响 FR-022/023 契约），若用户期望真用 LLM 分类而非 rule fallback，需走 `long-task-increment` 增加：① ProviderPresets `supports_strict_schema: bool` 能力位；② LlmBackend 在 supports_strict_schema=False 时改用 system-prompt 强约束 + 后置 JSON 解析（无 strict 字段）；③ per-provider response 兼容适配。当前只是 v1 已知降级，不阻塞 release。
- ⚠ [Stale-Scripts] 会话开始前 5 个 `scripts/*.py` dirty 改动延续未清，本会话同样显式排除，留独立 chore commit。

### Session 20 — Increment Wave 3 — F19 MiniMax OpenAI-compat strict-schema bypass
- **Date**: 2026-04-25
- **Phase**: Increment
- **Scope**: 响应 Session 19 Findings — F19 MiniMax 真打证实 `response_format=json_schema strict` 被 endpoint 拒收（HTTP 400 → fallback rule，FR-021/023 实质 disabled）。本增量在 OpenAI-compat 通路内引入 capability 位 + tolerant parse，让 strict-off provider（MiniMax 代表）仍能真打 LLM 分类；放弃 Anthropic-compat 通道。
- **Changes**: Added 0, modified 1 (F19), deprecated 0
- **Documents updated**: SRS（FR-021 +AC-4/5/6、FR-023 +AC-3..7、IFR-004 MODIFY +AC-mod、§8 +ASM-008、§12 Revision History +Wave 3）、Design（§4.4.2/§6.1.4/§6.2.2/§6.2.4/§11.4 Wave 3 增量段）、ATS（L89/L91/L182 Coverage Hint + §5.5 changelog）、F19 feature design（§IC/§IS §3a/§BC/§Reuse/§Tests T47..T52/§Checklist）、feature-list.json（F19 wave 2→3·status passing→failing·verification_steps +4·wave_note；waves[]+id=3；assumptions[]+ASM-008）
- **Routing**: F19 由 hard impact 重置为 failing；下一会话 `phase_route.py` 将 F19 路由进 design 阶段（feature-level design 重生成以集成 Wave 3 实现路径）
- **Skipped**: UCD（F22 设计阶段统一处理 UI 文案）；env-guide §3/§4（无新工具/库引入）；ats-reviewer rerun（needs_reviewer_rerun=false）；辅助文件（无新依赖/required_configs；validate_guide.py: VALID）
- **Approvals**: 4 关闸（impact / design / ATS / SRS+FL）全 approve；0 revise；0 escalate
- **Validate**: `validate_features.py: VALID — 22 features (5 passing, 5 failing, 12 deprecated) | Waves: 3 | Assumptions: 8`（3 个 cross-feature warning 为预期）
- **Git**: 46f03a9 feat: increment wave 3 — F19 MiniMax OpenAI-compat strict-schema bypass

#### Session 20 Findings
- ⚠ [Stale-Scripts] 5 个 `scripts/*.py` dirty 改动延续 Session 12/15/19 carry-over，本会话继续显式排除，待独立 chore commit 清理（不阻塞）。

### Session 21 — Feature #19 F19 · Bk-Dispatch — Model Resolver & Classifier · Design (Wave 3 Consistency Re-review · 2026-04-25)

- target_feature: id=19, title="F19 · Bk-Dispatch — Model Resolver & Classifier", category=core, ui=false, wave=3
- Trigger: Session 20 long-task-increment 把 F19 status 重置为 failing（Wave 3 MiniMax OpenAI-compat strict-schema bypass · 8 新 AC）；router 命中 `long-task-work-design` 阶段做 feature-level 一致性复审
- Anchors: SRS FR-019 L310 · FR-020 L319 · FR-021 L329 (+Wave3 ext L332-341) · FR-022 L343 · FR-023 L352 (+Wave3 ext L355-367) · IFR-004 row L774 (+Effective Strict subsection L779-788) · ASM-008 L800 / Design §4.4 F19 L398-435 · §6.1.4 IFR-004 L1005-1102 / UCD: N/A (ui:false) / env-guide §4: greenfield
- Feature design doc: `docs/features/19-f19-bk-dispatch-model-resolver-classifie.md`（Session 20 已落 Wave 3 修订；本会话 SubAgent 做一致性验证）
- Config Gate: skipped — `required_configs=[]` 不含连接串键（URL/URI/DSN/CONNECTION/HOST/PORT/ENDPOINT）
- SubAgent `long-task-feature-design`: status=pass · assumption_count=5（5 条均沿用 Session 18/20 既有 Clarification Addendum，非本会话新增）
- Design: DONE (docs/features/19-f19-bk-dispatch-model-resolver-classifie.md)
- Wave 3 一致性修订（+20/-7 行）：(1) §SRS Requirement 同步 FR-021 AC-4/5/6 + FR-023 EARS strict-off/tolerant-parse + AC-3..7 + IFR-004 AC-mod；(2) 类别占比统计 21/52→26/52=50%（FUNC 29 · BNDRY 8 · SEC 7 · INTG 8）；(3) Verification Checklist AC 追溯 13 旧+6 新 → 12 旧+8 新+1 IFR-mod+1 ASM；(4) T47 扩展 (a) 4 preset capability 位默认值 + (b) 5 组合 effective_strict 真值表断言，闭合 FR-021 AC-6 grey area
- Approval 关卡: user selected "Approve & 推进 design→tdd"
- current.phase: design → tdd

### Session 22 — Feature #19 F19 · Bk-Dispatch — Model Resolver & Classifier · TDD (Wave 3 · 2026-04-25)

- target_feature: id=19, title="F19 · Bk-Dispatch — Model Resolver & Classifier", category=core, ui=false, wave=3
- Trigger: Session 21 推进至 `current.phase=tdd`；router 命中 `long-task-work-tdd`，starting_new=false（Wave 3 增量重做 TDD R-G-R）
- Anchors: SRS FR-021 AC-4/5/6 (capability bit + override merge) · FR-023 AC-3..7 (strict-off body + tolerant parse) · IFR-004 AC-mod · ASM-008 / Design §4.4.2 / §6.1.4 §3a (effective_strict) / §6.2.2 / §6.2.4 / Feature §IC §IS §3a §BC §Reuse §Tests T47..T52 §Checklist
- Feature design doc: `docs/features/19-f19-bk-dispatch-model-resolver-classifie.md`（§7 T47..T52 Wave 3 行）
- env-guide approval: PASS（approved §3/§4 sections valid · 2026-04-21）
- Bootstrap: pure-Python / pytest / coverage · 无服务依赖（F19 keyring + HTTP 单测内 fakes）· "纯 CLI / library 模式" per env-guide §1 L126
- **Red — DISPATCH** `long-task-tdd-red` SubAgent
  - status=pass · 19 个新失败测试（2 个新文件）：tests/test_f19_wave3_strict_schema_capability.py · tests/test_f19_wave3_llm_strict_off.py
  - Rule 1 categories=FUNC=9 · BNDRY=6 · SEC=0 (pre-Wave-3 已覆盖) · INTG=2 · FUNC-error=2
  - Rule 2 negative_ratio=0.47（9/19）
  - Rule 3 low_value_ratio=0.04 · Rule 4 wrong_impl_challenge=pass · Rule 6 all_failed=true · Rule 7 N/A（ui=false）
- **Green — DISPATCH** `long-task-tdd-green` SubAgent
  - status=pass · all_tests_pass=true · wave3=19/19 · regression=479/479
  - impl_files: harness/dispatch/classifier/{models.py · provider_presets.py · llm_backend.py · service.py}
  - drift-protocol: tests/test_f19_coverage_supplement.py T79 更新为期望 `cause='json_parse_error'`（array-only assistant content：tolerant 提取器扫的是平衡 `{...}` object，array 没有 → json_parse_error，与 §3a step ②/③ 一致）
  - design_alignment §4=matches · §6=matches · §8=matches · drift=resolved · env_guide_synced=true（无新依赖）
- **Refactor — DISPATCH** `long-task-tdd-refactor` SubAgent（首次因 Monitor/run_in_background 卡住未返契约 → rerun foreground 完成）
  - status=pass · static_tool=ruff+mypy · F19-scoped static_violations=0
  - mypy: 0 violations across 75 source files · ruff: F19 范围 0；3 个 pre-existing 在 `scripts/phase_route.py` (E731 ×2) + `scripts/validate_features.py` (F401)，dirty-bag carry-over（feature #3 commit 6a6f03b）
  - tests_still_pass=true wave3=19/19 regression=479/479 · design_alignment_final §4/§6/§8=matches · drift=none
  - 无新结构性编辑 — Green 已幂等（`_extract_json` / `_JSON_ONLY_SUFFIX` 单一来源；`_effective_strict()` 单调用点；capability bit 在 builtin/custom 分支对称传播）
- **Quality Gates — DISPATCH** `long-task-quality` SubAgent
  - status=pass · coverage_line=96.32% (gate ≥ 90) · coverage_branch=81.45% (gate ≥ 80)
  - srs_trace covered=[FR-019, FR-020, FR-021, FR-022, FR-023, IFR-004] uncovered=[]
  - tests_run=479 · passed=479 · failed=0（30 deselected：real_external_llm/real_http/real_fs/real_keyring/real_cli）
  - Real-test sub-run: 3/3 PASS（test_f19_real_fs / real_http / real_keyring；real_external_llm 离线 deselected）
- current.phase: tdd → st
- Validate: `validate_features.py: VALID — 22 features (5 passing, 5 failing, 12 deprecated) | current=#19(st) | Waves: 3 | Assumptions: 8`（3 个 cross-feature warning 为预期）

#### Session 22 Findings
- ⚠ [Coverage] **branch buffer 收窄**：Wave 3 前 84.62% → Wave 3 后 81.45%（缓冲 4.62 pp → 1.45 pp）；line 同步 98.37% → 96.32%。仍均超阈，但若后续在 `harness/dispatch/classifier/llm_backend.py:123-127, 148-151, 157` 增加分支而无配对测试可能触底。主要未覆盖分支位于 strict-on 旧路径的回退处理（仅在 real_external_llm smoke 触达，本次 deselect）。
- ⚠ [Stale-Scripts] `scripts/{check_source_lang,count_pending,init_project,phase_route,validate_features}.py` dirty 改动延续 Session 12/15/17/18/19/20 carry-over，本次 commit 继续显式排除，待独立 chore commit 清理（不阻塞）。

### Session 23 — Feature #19 F19 · Bk-Dispatch — Model Resolver & Classifier · ST (Wave 3 · 2026-04-25)

- target_feature: id=19, title="F19 · Bk-Dispatch — Model Resolver & Classifier", category=core, ui=false, wave=3
- Trigger: Session 22 推进至 `current.phase=st`；router 命中 `long-task-work-st`，starting_new=false（Wave 3 增量 ST 阶段重生成用例）
- Anchors: SRS FR-019/020/021/022/023 + IFR-004（含 Wave 3 EARS 扩展 L332-341 / L355-367 / L774-788）· ATS L87-91 + L182 类别约束（FUNC/BNDRY/SEC/PERF · UI 由 F22 承担，ATS L87/L89 hint）· §5.5 Wave 3 Coverage Hint · Feature design §IC §IS §3a §BC §Test Inventory T01-T46 旧 + T47-T52 新
- env-guide approval: PASS（approved §3/§4 sections valid · 2026-04-21）
- Bootstrap: 纯 CLI / library 模式（env-guide §1.6）— 无 api / ui-dev 服务；`source .venv/bin/activate` 即可
- **Feature-ST — DISPATCH** `long-task-feature-st` SubAgent
  - status=pass · st_case_count=67（Wave 2 baseline 61 → Wave 3 +6）· manual_case_count=0 · environment_cleaned=true
  - 新增 6 条 ST-FUNC-019-047..052 覆盖 T47-T52（保留既有 61 条措辞不变；摘要表 functional 46→52、合计 61→67 同步更新；traceability matrix +12 nodeid 映射 verification_steps[8..11]）
  - T52 INTG/http real_external_llm smoke 按 ST CASE_ID_PATTERN 入 `functional` 类别（与 ST-FUNC-019-020/021、ST-PERF-019-001 既有真实网络场景一致）
  - Validators: `validate_st_cases.py` → VALID 67 / `check_ats_coverage.py --feature 19` → exit 0（UI 类别 warning 因 ui:false 已被 ATS L87/L89 hint 豁免）
  - Pytest 全套: `tests/test_f19_*.py + tests/integration/test_f19_*.py` → **119 passed in 15.98s**（Wave 2 baseline 98 + Wave 3 增量 21；零回归）
  - real_external_llm smoke (T52): MiniMax round-trip + classify-never-raises 两条 **均 live PASSED**（非 skip — keyring 含 valid api_key），ASM-008 strict-off 路径生产环境验证成立
- **Inline Check**: PASS
  - P2: 10/10 PUBLIC 类签名匹配（`ModelResolver` / `ModelRulesStore` / `ClassifierService` / `LlmBackend` / `RuleBackend` / `FallbackDecorator` / `PromptStore` / `ProviderPresets` / `Verdict` / `ClassifierConfig`）；10 核心方法（resolve / load / save / classify / test_connection / invoke / decide / get / put / validate_base_url）实现存在
  - T2: Wave 3 18 个新测试函数（test_t47a-h capability + truth-table 5 行 / test_t48a-c body shape / test_t49a tolerant strip / test_t50a first-balanced / test_t51a-b parse-error fallback / test_f19_real_minimax_*）与 Test Inventory T47-T52 行 1:1 对应
  - D3: httpx==0.28.1 / respx==0.23.1 / pydantic==2.13.3 / fastapi==0.136.0 / keyring==25.7.0 / pytest==8.4.2 与 env-guide §3 工具版本表对齐
  - U1: N/A（ui:false）
  - ATS Category: OK（exit 0；UI warning 豁免）
  - §4 存量约束: env-guide §4 greenfield 占位 → 0 violations
- **Persist**:
  - Git (Wave 3 ST): `39edce8` feat: feature #19 f19-bk-dispatch-model-resolver-classifier — Wave 3 ST cases 67 (119 auto PASS)
  - feature-list.json: F19 status `failing → passing`；`git_sha=39edce8`；`st_case_path=docs/test-cases/feature-19-...md`；`st_case_count=67`；root `current` `{19, st} → null`
  - RELEASE_NOTES.md: Wave 3 `### Changed` 条目附录 Worker 流水线完成证据（design `10342f6` · TDD `2ba24d4` · ST `39edce8`）
  - Validate: `validate_features.py: VALID — 22 features (6 passing, 4 failing, 12 deprecated) | current=none | Waves: 3 | Assumptions: 8`

### Feature #19: F19 · Bk-Dispatch — Model Resolver & Classifier (Wave 3) — PASS
- Completed: 2026-04-25
- TDD: green ✓ (commit `2ba24d4`)
- Quality Gates: line 96.32% / branch 81.45%（≥ 90 / 80）
- Feature-ST: 67 cases (FUNC×52 + BNDRY×7 + SEC×7 + PERF×1 · 119 auto PASS · 0 manual · real_external_llm smoke live PASS)
- Inline Check: PASS
- Git: `39edce8` feat: feature #19 f19-bk-dispatch-model-resolver-classifier — Wave 3 ST cases 67 (119 auto PASS)
#### Risks
- ⚠ [Coverage] branch 81.45% — 缓冲 1.45 pp（Wave 3 前 84.62% → Wave 3 后 81.45%）。strict-on 旧路径回退分支主要未覆盖；后续在 `harness/dispatch/classifier/llm_backend.py:123-127, 148-151, 157` 增加分支需配对测试避免触底
- ⚠ [Provider-Compat] MiniMax `response_format=json_schema strict` HTTP 400 拒收已通过 `supports_strict_schema=False` + tolerant parse + JSON-only suffix 规避；但 OpenAI-compat provider 协议漂移持续存在风险（GLM/OpenAI/custom 仍走 strict-on，若后续 provider 端协议变更需 re-smoke + 必要时再增 capability 位）
- ⚠ [Stale-Scripts] `scripts/{check_source_lang,count_pending,init_project,phase_route,validate_features}.py` dirty 改动延续 Session 12/15/17/18/19/20/22 carry-over，本次 commit 继续显式排除，待独立 chore commit 清理（不阻塞）

### Session 24 — Feature #20 F20 · Bk-Loop — Run Orchestrator · Recovery · Subprocess · Design (Wave 2 · 2026-04-25)

- target_feature: id=20, title="F20 · Bk-Loop — Run Orchestrator · Recovery · Subprocess", category=core, ui=false, wave=2
- Trigger: phase_route.py → next_skill=long-task-work-design, feature_id=20, starting_new=true (deps 2/3/18/19 全部 passing)
- Anchors:
  - Design §1 (lines 14-57) + §2.1 选定方案 asyncio (60-68) + §4.5 F20 (436-511) + §6.1 External Interfaces (937-1102) + §6.2 Internal API Contracts (1103+)
  - SRS FR-001/002/003/004 (L136/146/156/165) · FR-024/025/026/027/028/029 (L371/380/389/399/408/417) · FR-039/040/042/047/048 (L520/529/549/597/606) · NFR-003/004/015/016 (table rows L739-752) · IFR-003 (table row L773)
  - env-guide §4 (lines 259-292) — 存量代码库约束（greenfield placeholder）
  - ucd: ui:false → 跳过 UCD 引用
- env-guide approval: PASS（approved_date 2026-04-21T09:21:02+08:00）
- Config Gate: 跳过 — required_configs HARNESS_WORKDIR (workdir 路径) + PluginLongTaskForAgent (file) 不含连接串键 (URL/URI/DSN/CONNECTION/HOST/PORT/ENDPOINT)
- **Feature-Design — DISPATCH** `long-task-feature-design` SubAgent
  - status=pass · test_inventory_count=50 · negative_ratio=46% (23/50) · interface_methods=22 · existing_code_reuse=16 · assumption_count=9（低影响）
  - Provider: IAPI-001 / IAPI-002 / IAPI-004 / IAPI-012 / IAPI-013 / IAPI-016 / IAPI-019；Consumer: IAPI-003 / IAPI-005 / IAPI-008 / IAPI-009 / IAPI-010 / IAPI-011 / IAPI-017
  - UML 元素覆盖：seq 16/16 + state(runs) 9/9 + state(anomaly) 8/8 + flow 5/5 + class 15/15 = 53/53
  - Assumptions（user-approved 2026-04-25）：
    1. FR-001 "5s 进 running" = 软目标（state=starting 立即返回；state=running 由首张 ticket spawn 转换）
    2. NFR-003/004 retry_count 0 起递增 → 命中 3 次后第 4 次为 escalate（与 ATS L159/160 对齐）
    3. GitCommit schema = `{sha, author, subject, committed_at, files_changed, feature_id?}`
    4. FR-048 SignalFileWatcher.debounce_ms=200（端到端 ≤2s）
    5. FR-027 watchdog 默认 1800.0s（v1 写死；v1.1 deferred 用户配置入口）
    6. ValidatorRunner 协议 = `--json <path>` + stdout `{ok, issues}`；缺 `--json` 走 wrapper
    7. EscalationEmitter 双广播 `/ws/anomaly` 主推 + `/ws/run/:id` 同步 RunPhaseChanged
    8. FR-003 信号优先级 bugfix > increment（透传 `phase_route.py:109-115` 既有判定）
    9. NFR-016 filelock acquire timeout=0.5s（失败抛 `RunStartError(reason="already_running")` → 409）
- Design: DONE (`docs/features/20-f20-bk-loop-run-orchestrator-recovery-su.md`)
- current.phase: design → tdd

### Session 25 — Feature #20 F20 · Bk-Loop — Run Orchestrator · Recovery · Subprocess · TDD (Wave 2 · 2026-04-25)

- target_feature: id=20, title="F20 · Bk-Loop — Run Orchestrator · Recovery · Subprocess", category=core, ui=false, wave=2
- Trigger: phase_route.py → next_skill=long-task-work-tdd, feature_id=20, starting_new=false (current locked at {20, tdd})
- env-guide approval: PASS（approved_date 2026-04-21T09:21:02+08:00）
- Bootstrap: 纯 CLI / library 模式（env-guide §1.6）— 无 api / ui-dev 服务；`source .venv/bin/activate` 即可；冒烟 F19 classifier subset → 3 passed in 0.12s
- **TDD Red — DISPATCH** `long-task-tdd-red` SubAgent
  - status=pass · test_count=51（design §7 Test Inventory 50 + 1 boundary 增项）· negative_ratio=51% (26/51) · real_test_count=9
  - 类别覆盖：FUNC/happy=22 · FUNC/error=10 · BNDRY/edge=8 · SEC/path-traversal=1 · SEC/argv-injection=1 · PERF/timing=1 · INTG{subprocess=2,timing=1,git=1,fs=1,concurrency=1,db=1,api+ws=1}=8（UI=N/A，ui:false）
  - 测试文件 14 个：`tests/test_f20_{run_orchestrator,phase_route_invoker,anomaly_recovery,user_override,validator_runner,git_tracker,signal_watcher,ticket_supervisor,security}.py` + `tests/integration/test_f20_real_{subprocess,signal_fs,git,db,rest_ws}.py`
  - all-failed: 51 failed in 0.70s （ModuleNotFoundError on harness.{orchestrator,recovery,subprocess,api.git,api.files} — greenfield expected RED）
  - UML 覆盖：classDiagram 15/15 · seq msg#1-7/8-12/9+16 · state(runs) 9/9 · state(anomaly) 4/5 + retry_count guards · flowchart 5/5
- **TDD Green — DISPATCH** `long-task-tdd-green` SubAgent
  - status=pass · 51 passed in 6.32s（pytest exit=0 per env-guide §3 silent protocol）
  - 实现 22 文件：`harness/orchestrator/{__init__,errors,schemas,phase_route,run_lock,signal_watcher,bus,supervisor,run}.py` + `harness/recovery/{__init__,anomaly,retry,watchdog}.py` + `harness/subprocess/{__init__,git/__init__,git/tracker,validator/__init__,validator/schemas,validator/runner}.py` + `harness/api/{git,files}.py` + `harness/app/main.py`
  - design §4 alignment: matches（22 个 public method 签名与 Internal API Contracts 一致）
  - design §6 alignment: matches（call chain start_run → RunLock.acquire → run_repo.create → spawn _run_loop → PhaseRouteInvoker.invoke → TicketSupervisor.run_ticket → GitTracker.begin → ToolAdapter.spawn → Watchdog.arm → StreamParser.events → Watchdog.disarm → ClassifierService.classify → AnomalyClassifier.classify → GitTracker.end → TicketRepository.save 完整还原）
  - ⚠ Green 自分类 NOT [CONTRACT-DEVIATION]：filelock/watchdog 缺包改用 stdlib（fcntl + poll）→ Refactor 复核推翻
- **TDD Refactor — DISPATCH** `long-task-tdd-refactor` SubAgent
  - status=pass · 51 passed in 6.54s（F20）· 521 passed in 15.86s（全单元）· F20 integration 8 passed
  - **drift resolved**：`uv add filelock>=3.29.0 watchdog>=6.0.0` → 重构 `RunLock` 用 `filelock.FileLock(thread_local=False)` + `SignalFileWatcher` 用 `watchdog.observers.Observer + PatternMatchingEventHandler`（debounce_ms=200）；公共 API 不变；推翻 Green 自分类，§6 明确处方此两库
  - 静态分析：ruff=0 violations · black=0（26 文件 cosmetic 重排，含 `tests/test_f19_coverage_supplement.py` / `tests/integration/test_f19_real_minimax.py`）· mypy=0 errors（97 源文件）
  - 修复：13 unused imports/vars (F401/F841) · 2 E731 lambda → nested def (`scripts/phase_route.py`) · 6 mypy Any-leakage 用 `cast` 收紧 · Verdict literal-typed args 收紧 · 清理 retry.py / app/main.py 多余 type:ignore
- **Quality Gates — DISPATCH** `long-task-quality` SubAgent
  - status=pass · Gate 0 (Real Test) PASS（F20 9 real passed in 3.07s, 0 skipped）· Gate 0.5 (SRS Trace) PASS（20/20 FR/NFR/IFR 全覆盖, uncovered=[]）· Gate 1 line=91.79% (4058/4421) ≥90 · Gate 1 branch=81.04% (718/886) ≥80 · Gate 2 558 passed, 2 deselected (test_f18_real_cli T29/T30 real-CLI hang, F20 范围外)
- **Persist**:
  - feature-list.json: root `current` `{20, tdd} → {20, st}`；F20 `status=failing` 保持（ST 未完，下一会话 long-task-work-st）
  - validate_features.py: VALID — 22 features (6 passing, 4 failing, 12 deprecated) | current=#20(st) | 2 warnings（F21/F22 dep on failing F20，ST 完成后消解）
- current.phase: tdd → st
#### Risks
- ⚠ [Coverage] combined `--cov-fail-under=89.99%` 距 env-guide §3 advisory 阈值 90% shy 0.01pp（individual line 91.79 / branch 81.04 均 PASS）；2 deselected real-CLI tests 不在 F20 scope，需独立 chore 排查 `byte_queue.get()` 5min hang
- ⚠ [Coverage Buffer] F20 模块级 branch 缓冲偏低：`harness/orchestrator/run.py` 82% · `bus.py` 72% · `supervisor.py` 73% · `recovery/retry.py` 76% · `recovery/watchdog.py` 77% · `subprocess/validator/runner.py` 75%；下一波 fix 若新增分支需配对测试避免触底
- ⚠ [Stale-Scripts] `scripts/check_source_lang.py` 仍持续 black-cosmetic dirty（Session 12+ carry-over），本次 commit 继续显式排除；其余 `count_pending/init_project/phase_route/validate_features` 已被前序提交逐步消化（仅 phase_route.py 被 Refactor 一并清理）
