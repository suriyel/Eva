"""Unit tests for harness.cli_dialog.decider."""

from __future__ import annotations

import pytest

from harness.cli_dialog.catalog import DEFAULT_POLICIES
from harness.cli_dialog.decider import (
    CatalogDecider,
    DelegatingDecider,
    LLMDecider,
    UnknownDialogError,
)
from harness.cli_dialog.models import ChoiceItem, DialogAction, DialogScreen


def _screen(name: str | None) -> DialogScreen:
    return DialogScreen(
        name=name,
        title=name or "x",
        body=None,
        choices=(ChoiceItem(index=1, label="a"), ChoiceItem(index=2, label="b")),
        multi_select=False,
        allow_freeform=False,
        cursor_index=1,
    )


# ---------------------------------------------------------------------------
# CatalogDecider
# ---------------------------------------------------------------------------

def test_catalog_decider_picks_bypass_action_from_default_policies():
    decider = CatalogDecider()
    action = decider.decide(_screen("bypass-permissions-consent"))
    assert action.kind == "select"
    assert action.indices == (2,)


def test_catalog_decider_picks_trust_folder_action():
    action = CatalogDecider().decide(_screen("trust-folder"))
    assert action.kind == "select"
    assert action.indices == (1,)  # "Yes, I trust"


def test_catalog_decider_picks_settings_error_cancel():
    action = CatalogDecider().decide(_screen("settings-error"))
    assert action.kind == "cancel"


def test_catalog_decider_wizard_returns_ignore():
    """Wizard handler is intentionally non-resolving; main agent must escalate."""
    action = CatalogDecider().decide(_screen("onboarding-wizard"))
    assert action.kind == "ignore"


def test_catalog_decider_unknown_name_raises():
    with pytest.raises(UnknownDialogError):
        CatalogDecider().decide(_screen("never-seen-dialog"))


def test_catalog_decider_none_name_raises():
    with pytest.raises(UnknownDialogError, match="un-named"):
        CatalogDecider().decide(_screen(None))


def test_catalog_decider_custom_policies_override_default():
    custom = {"bypass-permissions-consent": DialogAction(kind="cancel")}
    decider = CatalogDecider(custom)
    action = decider.decide(_screen("bypass-permissions-consent"))
    assert action.kind == "cancel"


def test_default_policies_cover_all_known_dialogs():
    """Every detector in KNOWN_DIALOGS must have a default policy."""
    from harness.cli_dialog.catalog import KNOWN_DIALOGS

    catalog_names = {d.name for d in KNOWN_DIALOGS}
    policy_names = set(DEFAULT_POLICIES.keys())
    missing = catalog_names - policy_names
    assert not missing, f"detectors lack default policy: {missing}"


# ---------------------------------------------------------------------------
# LLMDecider stub
# ---------------------------------------------------------------------------

def test_llm_decider_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="reserved for the boot-dialog"):
        LLMDecider().decide(_screen("any"))


# ---------------------------------------------------------------------------
# DelegatingDecider stub
# ---------------------------------------------------------------------------

def test_delegating_decider_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="reserved for the boot-dialog"):
        DelegatingDecider().decide(_screen("any"))
