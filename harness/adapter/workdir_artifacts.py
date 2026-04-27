"""F18 Wave 4 · Claude TUI isolation triplet writers (FR-051).

Per Design §Implementation Summary §1 + flowchart `prepare_workdir` + env-guide
§4.5 Wave 4 isolation triplet.

Three classes:
  - ``SkipDialogsArtifactWriter``  → writes ``<cwd>/.claude.json``
  - ``SettingsArtifactWriter``     → writes ``<cwd>/.claude/settings.json``
  - ``HookBridgeScriptDeployer``   → copies repo-root scripts/claude-hook-bridge.py
                                     into ``<cwd>/.claude/hooks/`` (chmod 0o755)

All writers are **idempotent**: re-invoking with the same inputs produces
byte-equal file contents (T24).

Schema reference: aligned byte-equivalent semantically with the verified
working puncture script ``reference/f18-tui-bridge/puncture.py`` (2026-04-26).
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from harness.adapter.errors import WorkdirPrepareError


# Wave 4 lock: matches env-guide §4.5 + Test T23 expected fields.
# Bumped occasionally when claude CLI bumps its onboarding revision.
_LAST_ONBOARDING_VERSION = "2.1.119"

# Constant first-start timestamp (idempotency: must NOT use datetime.now()).
# Rationale: T24 asserts byte-equal re-write; reference puncture.py uses a
# constant string here.
_FIRST_START_TIME = "2026-04-26T00:00:00.000Z"


class SkipDialogsArtifactWriter:
    """Writes ``<cwd>/.claude.json`` with onboarding/trust dialog suppression."""

    def write(self, cwd: Path) -> Path:
        """Idempotent write of the .claude.json onboarding-skip artifact.

        Mirrors reference/f18-tui-bridge/puncture.py field set so the
        Claude CLI bypasses every onboarding/migration dialog at boot.

        Idempotency: ``userID`` is derived deterministically from ``cwd``
        via ``uuid.uuid5(NAMESPACE_OID, str(cwd))`` so re-writes are
        byte-equal (FR-051 / T24).
        """
        target = cwd / ".claude.json"
        deterministic_user_id = uuid.uuid5(uuid.NAMESPACE_OID, str(cwd)).hex
        body = {
            "firstStartTime": _FIRST_START_TIME,
            "migrationVersion": 12,
            "hasCompletedOnboarding": True,
            "opusProMigrationComplete": True,
            "sonnet1m45MigrationComplete": True,
            "userID": deterministic_user_id,
            "numStartups": 5,
            "hasSeenTasksHint": True,
            "hasVisitedPasses": True,
            "lastOnboardingVersion": _LAST_ONBOARDING_VERSION,
            "projectOnboardingSeenCount": 5,
            "projects": {
                str(cwd): {
                    "hasTrustDialogAccepted": True,
                    "allowedTools": [],
                    "hasClaudeMdExternalIncludesApproved": True,
                    "hasClaudeMdExternalIncludesWarningShown": True,
                    "projectOnboardingSeenCount": 5,
                }
            },
        }
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise WorkdirPrepareError(f".claude.json write failed: {exc}") from exc
        return target


class SettingsArtifactWriter:
    """Writes ``<cwd>/.claude/settings.json`` (env + nested hooks + flags).

    Schema mirrors reference/f18-tui-bridge/puncture.py (verified working
    2026-04-26 against claude CLI 2.1.119): hooks use the nested
    ``[{"matcher": ..., "hooks": [{"type": "command", "command": ..., "timeout": 30}]}]``
    shape so Claude actually invokes the bridge for AskUserQuestion events.
    """

    def write(
        self,
        cwd: Path,
        *,
        harness_base_url: str,
        model: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> Path:
        target = cwd / ".claude" / "settings.json"
        # Absolute path so the hook subprocess can locate the bridge regardless
        # of the cwd claude TUI happens to spawn it under (puncture-validated:
        # reference/f18-tui-bridge/puncture.py:104 uses str(hook_sh) absolute).
        # Relative path silently fails when claude's hook executor runs the
        # command from a different cwd than the workdir root.
        bridge_abs_path = (cwd / ".claude" / "hooks" / "claude-hook-bridge.py").resolve()
        bridge_cmd = f"python3 {bridge_abs_path}"

        # Nested hooks schema (puncture.py:118-141).
        # Wave 4.1 (2026-04-27): unified Esc-text protocol registers 8 hook
        # event types so the audit chain (PreToolUse + UserPromptSubmit + Stop)
        # closes for the unified-paste answer path. The 4 catch-all events
        # (Stop / SubagentStop / UserPromptSubmit / Notification) are NEW.
        # Matcher rule:
        #   - PreToolUse + PostToolUse: matcher="AskUserQuestion" (HIL only)
        #   - SessionStart / SessionEnd / Stop / SubagentStop /
        #     UserPromptSubmit / Notification: no matcher key (catch-all)
        matched_entry = [
            {
                "matcher": "AskUserQuestion",
                "hooks": [
                    {"type": "command", "command": bridge_cmd, "timeout": 30}
                ],
            }
        ]
        unmatched_entry = [
            {
                "hooks": [
                    {"type": "command", "command": bridge_cmd, "timeout": 30}
                ]
            }
        ]

        # Provider routing env (e.g., ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL)
        # is injected via settings.json, NOT via the OS env whitelist — claude
        # TUI reads settings.json `env` itself (see reference/f18-tui-bridge/
        # puncture.py:108-122 + claude-alt-settings.template.json). This keeps
        # the Wave-4 _ENV_WHITELIST tight while still letting integration tests
        # route to non-Anthropic providers.
        body_env: dict[str, str] = {"HARNESS_BASE_URL": harness_base_url}
        if extra_env:
            for key, value in extra_env.items():
                if key == "HARNESS_BASE_URL":
                    continue
                body_env[key] = value

        body: dict[str, object] = {
            "env": body_env,
            "permissions": {"defaultMode": "bypassPermissions"},
            "skipAutoPermissionPrompt": True,
            "skipDangerousModePermissionPrompt": True,
            "hooks": {
                "PreToolUse": matched_entry,
                "PostToolUse": matched_entry,
                "SessionStart": unmatched_entry,
                "SessionEnd": unmatched_entry,
                # Wave 4.1 NEW (2026-04-27): unified Esc-text protocol audit chain.
                "Stop": unmatched_entry,
                "SubagentStop": unmatched_entry,
                "UserPromptSubmit": unmatched_entry,
                "Notification": unmatched_entry,
            },
            # claude CLI 2.1.119 schema: enabledPlugins is a record
            # (plugin-name → enabled-bool), NOT an array. Empty record means
            # "no plugins enabled" — equivalent to puncture's effect, but
            # passes claude's settings validator (Expected record).
            "enabledPlugins": {},
        }
        if model is not None:
            body["model"] = model
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise WorkdirPrepareError(f".claude/settings.json write failed: {exc}") from exc
        return target


class HookBridgeScriptDeployer:
    """Copies repo-root scripts/claude-hook-bridge.py into the isolated workdir."""

    def deploy(self, cwd: Path, *, source: Path) -> Path:
        target = cwd / ".claude" / "hooks" / "claude-hook-bridge.py"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Idempotent copy: copy bytes directly so re-invocation is byte-equal.
            shutil.copyfile(str(source), str(target))
            os.chmod(str(target), 0o755)
        except OSError as exc:
            raise WorkdirPrepareError(f"claude-hook-bridge.py deploy failed: {exc}") from exc
        return target


__all__ = [
    "HookBridgeScriptDeployer",
    "SettingsArtifactWriter",
    "SkipDialogsArtifactWriter",
    "WorkdirPrepareError",
]
