"""Unit tests for harness.cli_dialog.models — DialogAction validation."""

from __future__ import annotations

import pytest

from harness.cli_dialog.models import ChoiceItem, DialogAction, DialogScreen


def test_dialog_action_select_requires_indices():
    with pytest.raises(ValueError, match="requires non-empty indices"):
        DialogAction(kind="select", indices=())


def test_dialog_action_freeform_requires_text():
    with pytest.raises(ValueError, match="requires text"):
        DialogAction(kind="freeform", text=None)


def test_dialog_action_indices_must_be_one_based():
    with pytest.raises(ValueError, match="1-based"):
        DialogAction(kind="select", indices=(0,))


def test_dialog_action_negative_index_rejected():
    with pytest.raises(ValueError, match="1-based"):
        DialogAction(kind="select", indices=(2, -1))


def test_dialog_action_submit_no_indices_ok():
    action = DialogAction(kind="submit")
    assert action.indices == ()
    assert action.text is None


def test_dialog_action_cancel_no_indices_ok():
    action = DialogAction(kind="cancel", rationale="user clicked No")
    assert action.kind == "cancel"
    assert action.rationale == "user clicked No"


def test_dialog_action_ignore_no_indices_ok():
    action = DialogAction(kind="ignore")
    assert action.kind == "ignore"


def test_dialog_action_select_multi_indices_ok():
    action = DialogAction(kind="select", indices=(2, 3))
    assert action.indices == (2, 3)


def test_dialog_action_freeform_with_text_ok():
    action = DialogAction(kind="freeform", text="hello world")
    assert action.text == "hello world"


def test_dialog_screen_frozen():
    screen = DialogScreen(
        name="x",
        title="t",
        body=None,
        choices=(ChoiceItem(index=1, label="a"),),
        multi_select=False,
        allow_freeform=False,
        cursor_index=1,
    )
    with pytest.raises(Exception):  # frozen → FrozenInstanceError
        screen.title = "y"  # type: ignore[misc]


def test_choice_item_default_unselected():
    c = ChoiceItem(index=1, label="opt")
    assert c.selected is False
