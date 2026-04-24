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
