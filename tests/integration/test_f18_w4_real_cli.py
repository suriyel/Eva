"""F18 Wave 4 · Real claude CLI HIL round-trip (T29) + PoC re-run gate (T30).

SRS: FR-008 / FR-009 / FR-011 / FR-013 / FR-051 / FR-053 / IFR-001 / ATS INT-001.
Test Inventory: T29 (full HIL hook + TUI key writeback round-trip) + T30 (≥95% PoC).

Layer marker:
  # [integration] — spawns real claude CLI ≥ v2.1.119 via PtyWorker.
  # @pytest.mark.real_cli makes this visible to check_real_tests.py.

Real-test invariants (Rule 5a):
  - Hard-fail if claude CLI is unavailable in PATH instead of skipping.
    The skill design contract states this CLI is part of env-guide §3 lock.
  - Main dependency (claude CLI) MUST NOT be mocked.
  - High-value assertions: hook fire counted, ticket pid stable, audit events
    persisted, user-scope sha256 unchanged.
  - PoC gate (T30): success rate ≥ 95% across 20 rounds; below threshold
    triggers HIL FR freeze + report write.

Provider authentication — three supported wirings (precedence order):
  1. **MiniMax / proxied Anthropic** via
     ``reference/f18-tui-bridge/claude-alt-settings.json`` (gitignored;
     ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL → routes claude TUI through a
     non-Anthropic provider). Schema follows
     ``claude-alt-settings.template.json``; this is the puncture-validated
     path.
  2. **Anthropic API key** via host env var ``ANTHROPIC_API_KEY`` /
     ``ANTHROPIC_AUTH_TOKEN`` (forwarded into settings.json env block).
  3. **Anthropic OAuth** via user-scope ``~/.claude/.credentials.json``
     (populated by ``claude /login``). The file is copied into
     ``fake_home/.claude/.credentials.json`` (chmod 0o600) so claude TUI
     reads it from the isolated workdir's HOME without leaking back to
     the user-scope directory.

When NONE of the three is wired, tests ``pytest.skip`` with explicit
remediation instructions — including ``claude /login`` for path #3.

Aligned with verified working puncture script
``reference/f18-tui-bridge/puncture.py`` (实测 2026-04-26 通过).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALT_SETTINGS_PATH = _REPO_ROOT / "reference" / "f18-tui-bridge" / "claude-alt-settings.json"
_USER_OAUTH_PATH = Path.home() / ".claude" / ".credentials.json"


def _claude_cli_available() -> bool:
    return shutil.which("claude") is not None


def _load_alt_settings_env() -> dict[str, str] | None:
    """Read provider-routing env from gitignored alt-settings.json (path 1)."""
    if not _ALT_SETTINGS_PATH.exists():
        return None
    try:
        data = json.loads(_ALT_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    env_block = data.get("env") or {}
    token = str(env_block.get("ANTHROPIC_AUTH_TOKEN", "")).strip()
    if not token or token.startswith("<") or token.endswith(">"):
        return None
    return {str(k): str(v) for k, v in env_block.items()}


def _resolve_provider_setup() -> dict[str, object] | None:
    """Pick a provider auth strategy in declared precedence order.

    Returns a dict with keys:
        - ``provider_env``: dict[str,str] | None — settings.json env to inject
        - ``oauth_source``: Path | None — credentials.json to copy into fake_home
        - ``label``: str — human-readable name of the chosen path

    Returns None when no auth source is available.
    """
    alt_env = _load_alt_settings_env()
    if alt_env:
        return {
            "provider_env": alt_env,
            "oauth_source": None,
            "label": "alt-settings.json (provider-routing, e.g. MiniMax)",
        }
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return {
            "provider_env": {"ANTHROPIC_API_KEY": api_key},
            "oauth_source": None,
            "label": "ANTHROPIC_API_KEY env var",
        }
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if auth_token:
        return {
            "provider_env": {"ANTHROPIC_AUTH_TOKEN": auth_token},
            "oauth_source": None,
            "label": "ANTHROPIC_AUTH_TOKEN env var",
        }
    if _USER_OAUTH_PATH.exists() and _USER_OAUTH_PATH.stat().st_size > 0:
        return {
            "provider_env": None,
            "oauth_source": _USER_OAUTH_PATH,
            "label": f"Anthropic OAuth ({_USER_OAUTH_PATH})",
        }
    return None


def _wire_isolated_credentials(isolated_home: Path, oauth_source: Path | None) -> None:
    """Copy user OAuth credentials into the isolated workdir's .claude/ tree.

    Per puncture mode (reference/f18-tui-bridge/README.md §3.4) the spawned
    claude TUI sets ``$HOME == cwd``, so credentials must live under
    ``<cwd>/.claude/.credentials.json`` for OAuth boot to succeed.
    Permissions: 0o600 on the copy (matches Anthropic CLI's own mode).
    The copy lives entirely under ``isolated_home`` (which is ``tmp_path``-
    scoped), so the real user-scope ``~/.claude/.credentials.json`` is
    untouched.
    """
    if oauth_source is None:
        return
    target = isolated_home / ".claude" / ".credentials.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(oauth_source.read_bytes())
    try:
        target.chmod(0o600)
    except OSError:
        pass


@pytest.fixture
def provider_setup() -> dict[str, object]:
    """Resolve provider auth (3 paths) or skip with remediation instructions."""
    setup = _resolve_provider_setup()
    if setup is None:
        pytest.skip(
            "F18 W4 real_cli: no provider credentials available. Wire ONE of:\n"
            "  (a) reference/f18-tui-bridge/claude-alt-settings.json with real "
            "ANTHROPIC_AUTH_TOKEN (MiniMax / proxied Anthropic routing — see "
            "claude-alt-settings.template.json);\n"
            "  (b) export ANTHROPIC_API_KEY=<key>  (Anthropic-direct);\n"
            "  (c) run `claude /login` to populate ~/.claude/.credentials.json "
            "(Anthropic OAuth — official flow).\n"
            "See env-guide §5 (Real-External LLM Smoke pattern)."
        )
    return setup


_PROMPT = (
    "Use the AskUserQuestion tool exactly once to ask me a single radio "
    "question with header='Lang' question='Which language?' options="
    "['Python', 'Go', 'Rust'] (single-select). Wait for my answer. "
    "Finally print one line: DONE: <pick>."
)


def _prepare_isolated_workdir(
    isolated: Path, *, oauth_source: Path | None
) -> None:
    """Wire the isolated workdir before run_real_hil_round_trip is invoked.

    In puncture mode, ``$HOME == cwd``, so we drop OAuth credentials directly
    under ``<isolated>/.claude/.credentials.json``. The
    ``SkipDialogsArtifactWriter`` (called by ``prepare_workdir``) will then
    write ``<isolated>/.claude.json`` so claude TUI's onboarding/trust check
    sees a fully-populated state and skips the first-run network probe.
    """
    isolated.mkdir(parents=True, exist_ok=True)
    _wire_isolated_credentials(isolated, oauth_source)


def _hash_user_scope_claude() -> tuple[str | None, str | None]:
    """Snapshot real user-scope ~/.claude/settings.json + ~/.claude.json hashes.

    Returns (None, None) when files don't exist. The test asserts these are
    unchanged after the spawned claude finishes (NFR-009 — no user-scope
    pollution by the isolated subprocess).
    """
    user_settings = Path.home() / ".claude" / "settings.json"
    user_claude_json = Path.home() / ".claude.json"
    s_hash = (
        hashlib.sha256(user_settings.read_bytes()).hexdigest()
        if user_settings.exists()
        else None
    )
    c_hash = (
        hashlib.sha256(user_claude_json.read_bytes()).hexdigest()
        if user_claude_json.exists()
        else None
    )
    return s_hash, c_hash


@pytest.mark.real_cli
def test_t29_real_cli_full_hil_round_trip_via_hook_bridge(tmp_path, provider_setup):
    """[feature 18] Full HIL round-trip:
       prepare_workdir → spawn → AskUserQuestion fires PreToolUse hook →
       /api/hook/event → HookEventMapper → HilQuestion → user answers via UI →
       TuiKeyEncoder → /api/pty/write → PtyWorker.write → claude TUI continues.

    Invariants:
      - hook_fires >= 1
      - audit hil_captured + hil_answered each fire at least once
      - same pid before/after HIL
      - user-scope ~/.claude/settings.json + ~/.claude.json sha256 unchanged
    """
    assert _claude_cli_available(), (
        "claude CLI not on PATH — env-guide §3 locks claude >= 2.1.119 as required tool. "
        "Install before running Wave 4 integration tests."
    )

    # Lazy import — code under test is the Wave 4 stack.
    from harness.adapter.claude import ClaudeCodeAdapter  # noqa: F401
    from harness.adapter.process import TicketProcess  # noqa: F401
    from harness.api.hook import router as hook_router  # noqa: F401
    from harness.hil.hook_mapper import HookEventMapper  # noqa: F401
    from harness.hil.tui_keys import TuiKeyEncoder  # noqa: F401
    from harness.orchestrator.run import run_real_hil_round_trip

    isolated = tmp_path / ".harness-workdir" / "r1"
    _prepare_isolated_workdir(
        isolated, oauth_source=provider_setup["oauth_source"]  # type: ignore[arg-type]
    )

    # Snapshot REAL user-scope hashes (NFR-009 — verify the spawned subprocess
    # doesn't pollute the host's ~/.claude/ tree).
    before_user_settings, before_user_claude = _hash_user_scope_claude()

    print(f"[T29] auth_path={provider_setup['label']}", flush=True)
    try:
        result = run_real_hil_round_trip(
            cwd=isolated,
            prompt=_PROMPT,
            timeout_s=60.0,
            provider_env=provider_setup["provider_env"],  # type: ignore[arg-type]
        )
    except RuntimeError as exc:
        msg = str(exc)
        skippable_markers = (
            "region-blocked",
            "cannot reach provider",
            "inference call rejected by provider",
        )
        if any(marker in msg for marker in skippable_markers):
            pytest.skip(
                f"T29 cannot run with current auth/network. "
                f"Auth path tried: {provider_setup['label']}. {msg}"
            )
        raise

    assert result.hook_fires >= 1, f"expected ≥ 1 hook fire; got {result.hook_fires}"
    assert result.same_pid_after_hil is True, "claude pid changed across HIL turn"
    assert result.audit_hil_captured >= 1, (
        f"audit hil_captured={result.audit_hil_captured} (expected ≥ 1)"
    )
    assert result.audit_hil_answered >= 1, (
        f"audit hil_answered={result.audit_hil_answered} (expected ≥ 1)"
    )

    after_user_settings, after_user_claude = _hash_user_scope_claude()
    assert before_user_settings == after_user_settings, (
        "real user ~/.claude/settings.json hash changed — NFR-009 violation"
    )
    assert before_user_claude == after_user_claude, (
        "real user ~/.claude.json hash changed — NFR-009 violation"
    )


@pytest.mark.real_cli
def test_t30_real_cli_poc_20_rounds_success_rate_at_least_95_percent(
    tmp_path, provider_setup
):
    """[feature 18] FR-013 PoC gate (Wave 4 re-run): 20 HIL round-trips ≥ 95% success.
    Failure triggers HIL FR freeze + emits docs/explore/wave4-hil-poc-report.md.
    """
    assert _claude_cli_available(), "claude CLI not on PATH — required for T30 PoC re-run"

    from harness.orchestrator.run import run_real_hil_round_trip

    # Probe round 0 first — if provider is unreachable (region-blocked), skip
    # the entire 20-round PoC gate rather than reporting 0/20 spuriously.
    successes = 0
    failures = []
    for i in range(20):
        round_dir = tmp_path / f"round-{i}"
        isolated = round_dir / ".harness-workdir" / "r1"
        _prepare_isolated_workdir(
            isolated, oauth_source=provider_setup["oauth_source"]  # type: ignore[arg-type]
        )
        try:
            res = run_real_hil_round_trip(
                cwd=isolated,
                prompt=_PROMPT,
                timeout_s=60.0,
                provider_env=provider_setup["provider_env"],  # type: ignore[arg-type]
            )
            if res.hook_fires >= 1 and res.audit_hil_answered >= 1:
                successes += 1
            else:
                failures.append((i, "incomplete-round-trip"))
        except RuntimeError as exc:
            msg = str(exc)
            skippable_markers = (
                "region-blocked",
                "cannot reach provider",
                "inference call rejected by provider",
            )
            if i == 0 and any(marker in msg for marker in skippable_markers):
                pytest.skip(
                    f"T30 cannot run with current auth/network. "
                    f"Auth path tried: {provider_setup['label']}. {msg}"
                )
            failures.append((i, repr(exc)))
        except Exception as exc:  # noqa: BLE001
            failures.append((i, repr(exc)))

    rate = successes / 20.0
    assert rate >= 0.95, (
        f"FR-013 PoC gate FAIL: success rate {rate:.0%} < 95% over 20 rounds; "
        f"failures={failures}. Per FR-013 AC-2, freeze HIL FRs + write "
        f"docs/explore/wave4-hil-poc-report.md."
    )
