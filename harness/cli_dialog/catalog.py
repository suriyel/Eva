"""Catalogue of known claude TUI dialogs + default policies.

Each entry maps a stable dialog ``name`` to:
  - a token-based ``Detector`` (collapsed-whitespace text matcher used by
    ``CatalogRecognizer``)
  - a default ``DialogAction`` consumed by ``CatalogDecider``

When claude CLI updates its TUI text, only this file changes.

Detection runs on **whitespace-collapsed** screen text — claude TUI uses
cursor-position escapes to lay out tokens, so consecutive words appear
without spaces (e.g. ``"BypassPermissionsmode"``). Detectors must match
the same form. See the ``_collapse`` helper in ``recognizer.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.cli_dialog.models import ChoiceItem, DialogAction, DialogScreen


@dataclass(frozen=True)
class Detector:
    """A simple set-of-tokens matcher.

    A screen matches when *all* required tokens are present in the
    collapsed-whitespace screen text. Lightweight on purpose — anything
    more elaborate belongs in the LLM recognizer.
    """

    name: str
    required_tokens: tuple[str, ...]
    parse: callable  # type: ignore[type-arg] # callable(collapsed_text) → DialogScreen


# ---------------------------------------------------------------------------
# Parsers — each returns a fully populated DialogScreen for its dialog.
# ---------------------------------------------------------------------------

def _parse_bypass_permissions(_collapsed: str) -> DialogScreen:
    return DialogScreen(
        name="bypass-permissions-consent",
        title="Claude Code running in Bypass Permissions mode",
        body=(
            "In Bypass Permissions mode, Claude Code will not ask for your "
            "approval before running potentially dangerous commands."
        ),
        choices=(
            ChoiceItem(index=1, label="No, exit"),
            ChoiceItem(index=2, label="Yes, I accept"),
        ),
        multi_select=False,
        allow_freeform=False,
        cursor_index=1,  # ❯ defaults to "No, exit"
    )


def _parse_trust_folder(_collapsed: str) -> DialogScreen:
    return DialogScreen(
        name="trust-folder",
        title="Quick safety check",
        body="Is this a project you created or one you trust?",
        choices=(
            ChoiceItem(index=1, label="Yes, I trust this folder"),
            ChoiceItem(index=2, label="No, exit"),
        ),
        multi_select=False,
        allow_freeform=False,
        cursor_index=1,
    )


def _parse_settings_error(_collapsed: str) -> DialogScreen:
    return DialogScreen(
        name="settings-error",
        title="Settings Error",
        body=(
            "Files with errors are skipped entirely, not just the invalid "
            "settings."
        ),
        choices=(
            ChoiceItem(index=1, label="Exit and fix manually"),
            ChoiceItem(index=2, label="Continue without these settings"),
        ),
        multi_select=False,
        allow_freeform=False,
        cursor_index=1,
    )


def _parse_wizard(_collapsed: str) -> DialogScreen:
    return DialogScreen(
        name="onboarding-wizard",
        title="Choose the text style",
        body=None,
        choices=(),
        multi_select=False,
        allow_freeform=False,
        cursor_index=1,
    )


# ---------------------------------------------------------------------------
# Detector table — order matters (more specific dialogs first). Tokens are
# matched against the WHITESPACE-COLLAPSED screen text — see
# ``recognizer.normalise``. claude TUI's "Files with errors are skipped
# entirely..." collapses to ``"Fileswitherrorsareskippedentirely"``.
# ---------------------------------------------------------------------------

KNOWN_DIALOGS: tuple[Detector, ...] = (
    Detector(
        name="settings-error",
        required_tokens=("SettingsError", "Fileswitherrorsareskippedentirely"),
        parse=_parse_settings_error,
    ),
    Detector(
        name="bypass-permissions-consent",
        required_tokens=("BypassPermissionsmode", "Iaccept"),
        parse=_parse_bypass_permissions,
    ),
    Detector(
        name="trust-folder",
        required_tokens=("Quicksafetycheck", "Yes,Itrustthisfolder"),
        parse=_parse_trust_folder,
    ),
    Detector(
        name="onboarding-wizard",
        required_tokens=("Choosethetextstyle",),
        parse=_parse_wizard,
    ),
)


# ---------------------------------------------------------------------------
# Default policies — what action to take for each known dialog.
# ---------------------------------------------------------------------------

DEFAULT_POLICIES: dict[str, DialogAction] = {
    "bypass-permissions-consent": DialogAction(
        kind="select",
        indices=(2,),
        rationale=(
            "UT/PoC scope: bypass-mode acceptance is required for hooks to "
            "register; production spawn paths should override this with "
            "DelegatingDecider so end-users see + confirm the dialog."
        ),
    ),
    "trust-folder": DialogAction(
        kind="select",
        indices=(1,),
        rationale=(
            "UT/PoC scope: cwd is .harness-workdir/<run-id>/ owned entirely "
            "by the test fixture (NFR-009 isolation); trust is safe."
        ),
    ),
    "settings-error": DialogAction(
        kind="cancel",
        rationale=(
            "Settings-error must fail loudly — silently continuing would let "
            "hooks be silently dropped and break the Wave-4 protocol contract."
        ),
    ),
    "onboarding-wizard": DialogAction(
        kind="ignore",
        rationale=(
            "If the wizard is reached the .claude.json onboarding fields "
            "weren't honored — main agent should detect this and re-raise "
            "WorkdirPrepareError rather than play through the wizard."
        ),
    ),
}


__all__ = ["Detector", "KNOWN_DIALOGS", "DEFAULT_POLICIES"]
