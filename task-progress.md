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

