"""Unit tests for harness.cli_dialog.recognizer / catalog."""

from __future__ import annotations

import pytest

from harness.cli_dialog.recognizer import (
    CatalogRecognizer,
    ChainRecognizer,
    LLMRecognizer,
    normalise,
)


# Real frame samples captured from claude TUI 2.1.119 (with ANSI escapes
# already stripped by tests for brevity; recognise() handles raw bytes too).
BYPASS_DIALOG_SAMPLE = """
WARNING: Claude Code running in Bypass Permissions mode

In Bypass Permissions mode, Claude Code will not ask for your approval
before running potentially dangerous commands.

❯ 1. No, exit
  2. Yes, I accept
Enter to confirm · Esc to cancel
"""

TRUST_DIALOG_SAMPLE = """
Quick safety check: Is this a project you created or one you trust?

❯ 1. Yes, I trust this folder
  2. No, exit
Enter to confirm · Esc to cancel
"""

SETTINGS_ERROR_SAMPLE = """
Settings Error: /tmp/x/.claude/settings.json
└ enabledPlugins: Expected record, but received array
Files with errors are skipped entirely, not just the invalid settings.
❯ 1. Exit and fix manually
  2. Continue without these settings
"""

WIZARD_SAMPLE = """
Choose the text style:
❯ 1. Light
  2. Dark
"""

MAIN_PROMPT_SAMPLE = """
❯
⏵⏵ bypass permissions on (shift+tab to cycle) · esc to interrupt
"""


# ---------------------------------------------------------------------------
# normalise
# ---------------------------------------------------------------------------

def test_normalise_strips_ansi_and_collapses_whitespace():
    raw = b"\x1b[31mHello\x1b[0m  World\n\tFoo"
    out = normalise(raw)
    assert out == "HelloWorldFoo"


def test_normalise_handles_str_input():
    out = normalise("Hello   World")
    assert out == "HelloWorld"


def test_normalise_handles_cursor_position_escapes():
    # \x1b[5;3H is a cursor-position sequence; should be stripped.
    raw = b"\x1b[5;3HText"
    out = normalise(raw)
    assert out == "Text"


# ---------------------------------------------------------------------------
# CatalogRecognizer
# ---------------------------------------------------------------------------

def test_catalog_recognises_bypass_permissions_dialog():
    screen = CatalogRecognizer().recognize(BYPASS_DIALOG_SAMPLE)
    assert screen is not None
    assert screen.name == "bypass-permissions-consent"
    assert screen.multi_select is False
    assert len(screen.choices) == 2
    assert screen.choices[1].label == "Yes, I accept"


def test_catalog_recognises_trust_folder_dialog():
    screen = CatalogRecognizer().recognize(TRUST_DIALOG_SAMPLE)
    assert screen is not None
    assert screen.name == "trust-folder"
    assert screen.choices[0].label == "Yes, I trust this folder"


def test_catalog_recognises_settings_error_dialog():
    screen = CatalogRecognizer().recognize(SETTINGS_ERROR_SAMPLE)
    assert screen is not None
    assert screen.name == "settings-error"
    assert "skipped entirely" in (screen.body or "").lower()


def test_catalog_recognises_onboarding_wizard():
    screen = CatalogRecognizer().recognize(WIZARD_SAMPLE)
    assert screen is not None
    assert screen.name == "onboarding-wizard"


def test_catalog_returns_none_for_main_prompt():
    screen = CatalogRecognizer().recognize(MAIN_PROMPT_SAMPLE)
    assert screen is None


def test_catalog_returns_none_for_unknown_layout():
    screen = CatalogRecognizer().recognize("some random TUI screen text")
    assert screen is None


def test_catalog_settings_error_priority_over_bypass():
    """Settings-error must match before bypass-permissions when both tokens
    appear — settings-error fail-loud takes precedence."""
    combined = SETTINGS_ERROR_SAMPLE + BYPASS_DIALOG_SAMPLE
    screen = CatalogRecognizer().recognize(combined)
    assert screen is not None
    # detector order in KNOWN_DIALOGS puts settings-error first.
    assert screen.name == "settings-error"


# ---------------------------------------------------------------------------
# LLMRecognizer (stub) + ChainRecognizer
# ---------------------------------------------------------------------------

def test_llm_recognizer_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="reserved for the boot-dialog"):
        LLMRecognizer().recognize("anything")


def test_chain_recognizer_returns_first_non_none():
    chain = ChainRecognizer([CatalogRecognizer()])
    screen = chain.recognize(BYPASS_DIALOG_SAMPLE)
    assert screen is not None
    assert screen.name == "bypass-permissions-consent"


def test_chain_recognizer_skips_unimplemented_llm_recognizer():
    """LLMRecognizer raises NotImplementedError; chain should skip and
    continue, returning None when no recogniser matches."""
    chain = ChainRecognizer([LLMRecognizer(), CatalogRecognizer()])
    screen = chain.recognize("totally unknown screen content")
    assert screen is None


def test_chain_recognizer_catalog_then_llm_returns_catalog_match():
    """When catalog matches, LLM should not be consulted (no NotImplementedError)."""
    chain = ChainRecognizer([CatalogRecognizer(), LLMRecognizer()])
    screen = chain.recognize(BYPASS_DIALOG_SAMPLE)
    assert screen is not None
    assert screen.name == "bypass-permissions-consent"
