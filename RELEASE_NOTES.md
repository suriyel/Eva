# Release Notes — Harness

## [Unreleased]

### Added
- Initial project scaffold
- F01 · App Shell & Platform Bootstrap — PyWebView + FastAPI (127.0.0.1-only) + first-run wizard; KeyringGateway facade (IAPI-014 / IFR-006 with Linux plaintext fallback); ClaudeAuthDetector (IFR-001 credential-inheritance surface); BindGuard loopback enforcement; `/api/health` endpoint; zh-CN user-facing strings
- F02 · Persistence Core — SQLite `tickets` single-table + append-only JSONL audit log (IAPI-011 TicketRepository.save/get/list_by_run/list_unfinished/mark_interrupted + IAPI-009 AuditWriter.append); 9-state `TicketStateMachine` with legal-transition matrix (FR-006); `RunRepository` CRUD; `RecoveryScanner.scan_and_mark_interrupted` for NFR-005 crash recovery; `Schema.ensure` idempotent WAL migration (journal_mode=WAL, busy_timeout=5000ms, foreign_keys=ON); pydantic v2 Ticket aggregate with 7 sub-structures (FR-007); workdir-only write isolation under `<workdir>/.harness/` (NFR-006); aiosqlite 0.20 + structlog 24.4 pinned
- F10 · Environment Isolation & Skills Installer — per-run `.harness-workdir/<run-id>/.claude/` tree with `settings.json` / `mcp.json` + **physical-copy** of `plugins/longtaskforagent` bundle via `shutil.copytree(dirs_exist_ok=True)` + sha256 manifest verification (single-path, no `sys.platform` branch — supersedes original symlink design per 2026-04-24 user ruling, avoids Windows `WinError 1314`); `EnvironmentIsolator.setup_run` / `teardown_run` with nanosecond-precision `HomeMtimeGuard` snapshot+diff enforcing NFR-009 zero-write to `~/.claude/`; `WorkdirScopeGuard.assert_scope` enforcing FR-044 `.harness/` + `.harness-workdir/` only; `SkillsInstaller` with git URL whitelist (https + git@host:path, rejects file://, shell meta, `..`) + `run.lock` guard; REST `POST /api/skills/{install,pull}` (IAPI-018) with 400/409 error mapping; `PluginRegistry` manifest reader (≤64 KiB DoS cap) + idempotent `sync_bundle`; `AuditWriter.append_raw` non-destructive extension for `env.setup` / `env.teardown` / `skills.install` events (IAPI-009 reuse)

### Changed
- Increment Wave 2 (refactor-only feature repackaging, 2026-04-24): consolidated 12 fine-grained features into 5 cohesive TDD units — F18 Bk-Adapter (F03+F04+F05), F19 Bk-Dispatch (F07+F08), F20 Bk-Loop (F06+F09+F11), F21 Fe-RunViews (F13+F14), F22 Fe-Config (F15+F16). Preserved F01/F02/F10(st)/F12/F17; F17 dependencies remapped to new ids; 12 old feature ids marked `deprecated:true` for audit traceability. **0 FR/NFR/IFR semantic changes · 0 breaking contracts · 0 code changes** — only Design §4 / §6.2.1 / §11 reorganization, ATS / UCD / guide feature-id remapping, feature-list.json reshape. HIL PoC gate (FR-013) ownership moved F03 → F18.

### Fixed
- (none yet)

---

_Format: [Keep a Changelog](https://keepachangelog.com/) — Updated after every git commit._
