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

