"""Unit tests for harness.cli_dialog.actuator — keystroke encoding."""

from __future__ import annotations

import pytest

from harness.cli_dialog.actuator import (
    ARROW_DOWN,
    ARROW_UP,
    DialogActuator,
    ENTER,
    ESCAPE,
    PASTE_END,
    PASTE_START,
    SPACE,
)
from harness.cli_dialog.models import ChoiceItem, DialogAction, DialogScreen


def _screen(
    *,
    multi_select: bool = False,
    cursor_index: int = 1,
    n_choices: int = 2,
) -> DialogScreen:
    return DialogScreen(
        name="test",
        title="Test",
        body=None,
        choices=tuple(
            ChoiceItem(index=i, label=f"opt{i}") for i in range(1, n_choices + 1)
        ),
        multi_select=multi_select,
        allow_freeform=False,
        cursor_index=cursor_index,
    )


# ---------------------------------------------------------------------------
# ignore / cancel / submit / freeform
# ---------------------------------------------------------------------------

def test_ignore_returns_empty_bytes():
    keys = DialogActuator().encode(DialogAction(kind="ignore"), _screen())
    assert keys == b""


def test_cancel_returns_escape():
    keys = DialogActuator().encode(DialogAction(kind="cancel"), _screen())
    assert keys == ESCAPE


def test_submit_returns_enter_only():
    keys = DialogActuator().encode(DialogAction(kind="submit"), _screen())
    assert keys == ENTER


def test_freeform_wraps_in_bracketed_paste_plus_enter():
    action = DialogAction(kind="freeform", text="hello")
    keys = DialogActuator().encode(action, _screen())
    assert keys == PASTE_START + b"hello" + PASTE_END + ENTER


def test_freeform_utf8_encoded():
    action = DialogAction(kind="freeform", text="你好")
    keys = DialogActuator().encode(action, _screen())
    assert keys == PASTE_START + "你好".encode("utf-8") + PASTE_END + ENTER


# ---------------------------------------------------------------------------
# select (single)
# ---------------------------------------------------------------------------

def test_select_target_below_cursor_walks_down():
    """cursor=1, target=2 → arrow-down × 1 + Enter."""
    screen = _screen(cursor_index=1, n_choices=2)
    action = DialogAction(kind="select", indices=(2,))
    keys = DialogActuator().encode(action, screen)
    assert keys == ARROW_DOWN + ENTER


def test_select_target_above_cursor_walks_up():
    """cursor=3, target=1 → arrow-up × 2 + Enter."""
    screen = _screen(cursor_index=3, n_choices=3)
    action = DialogAction(kind="select", indices=(1,))
    keys = DialogActuator().encode(action, screen)
    assert keys == ARROW_UP * 2 + ENTER


def test_select_target_equals_cursor_emits_enter_only():
    screen = _screen(cursor_index=2, n_choices=3)
    action = DialogAction(kind="select", indices=(2,))
    keys = DialogActuator().encode(action, screen)
    assert keys == ENTER


def test_select_far_below_walks_n_times():
    """cursor=1, target=4 → arrow-down × 3 + Enter."""
    screen = _screen(cursor_index=1, n_choices=4)
    action = DialogAction(kind="select", indices=(4,))
    keys = DialogActuator().encode(action, screen)
    assert keys == ARROW_DOWN * 3 + ENTER


def test_single_select_rejects_multiple_indices():
    screen = _screen(multi_select=False, n_choices=3)
    action = DialogAction(kind="select", indices=(1, 2))
    with pytest.raises(ValueError, match="exactly 1 index"):
        DialogActuator().encode(action, screen)


# ---------------------------------------------------------------------------
# select (multi)
# ---------------------------------------------------------------------------

def test_multi_select_walks_and_toggles_each_target_then_submits():
    """cursor=1 multi-select, indices=(2, 3) → down + space + down + space + Enter."""
    screen = _screen(multi_select=True, cursor_index=1, n_choices=4)
    action = DialogAction(kind="select", indices=(2, 3))
    keys = DialogActuator().encode(action, screen)
    assert keys == ARROW_DOWN + SPACE + ARROW_DOWN + SPACE + ENTER


def test_multi_select_target_above_cursor_walks_up():
    """cursor=3 multi-select, indices=(1, 4) → up*2 + space + down*3 + space + Enter."""
    screen = _screen(multi_select=True, cursor_index=3, n_choices=4)
    action = DialogAction(kind="select", indices=(1, 4))
    keys = DialogActuator().encode(action, screen)
    assert keys == ARROW_UP * 2 + SPACE + ARROW_DOWN * 3 + SPACE + ENTER


def test_multi_select_single_target_still_toggles_then_submits():
    screen = _screen(multi_select=True, cursor_index=1, n_choices=3)
    action = DialogAction(kind="select", indices=(2,))
    keys = DialogActuator().encode(action, screen)
    assert keys == ARROW_DOWN + SPACE + ENTER


def test_multi_select_no_indices_raises():
    screen = _screen(multi_select=True, n_choices=3)
    with pytest.raises(ValueError, match="non-empty indices"):
        DialogAction(kind="select", indices=())


# ---------------------------------------------------------------------------
# unknown action kind
# ---------------------------------------------------------------------------

class _Bypass(DialogAction):  # type: ignore[misc]
    pass


def test_unknown_action_kind_raises():
    screen = _screen()
    # Force an invalid kind by bypassing __post_init__ — uses object.__new__
    # to produce a frozen instance with an out-of-Literal kind.
    action = DialogAction.__new__(DialogAction)
    object.__setattr__(action, "kind", "frobnicate")
    object.__setattr__(action, "indices", ())
    object.__setattr__(action, "text", None)
    object.__setattr__(action, "rationale", "")
    with pytest.raises(ValueError, match="unknown DialogAction.kind"):
        DialogActuator().encode(action, screen)


# ---------------------------------------------------------------------------
# unified_answer (Wave 4.1, 2026-04-27) — default HIL answer encoding.
#
# Layout:  ESC + ESC[200~ + text(utf-8) + ESC[201~ + CR
# ---------------------------------------------------------------------------
def _expected_unified(text: str) -> bytes:
    return ESCAPE + PASTE_START + text.encode("utf-8") + PASTE_END + ENTER


def test_unified_answer_basic_radio_label() -> None:
    """T-UNIFIED-RADIO equivalent — single-select label text."""
    action = DialogAction(kind="unified_answer", text="Python")
    keys = DialogActuator().encode(action, _screen())
    assert keys == _expected_unified("Python")


def test_unified_answer_utf8_freeform_body() -> None:
    """T-UNIFIED-FREEFORM equivalent — UTF-8 multibyte preserved."""
    text = "我想要 Rust 因为速度"
    action = DialogAction(kind="unified_answer", text=text)
    keys = DialogActuator().encode(action, _screen())
    assert keys == _expected_unified(text)


def test_unified_answer_multi_question_concatenated() -> None:
    """T-UNIFIED-MULTI-QUESTION equivalent — 3 answers joined into one merged text."""
    merged = "Lang: Python; Test: pytest; CI: github-actions"
    action = DialogAction(kind="unified_answer", text=merged)
    keys = DialogActuator().encode(action, _screen())
    assert keys == _expected_unified(merged)
    # Spot-check the protocol prefix + suffix.
    assert keys.startswith(ESCAPE + PASTE_START)
    assert keys.endswith(PASTE_END + ENTER)


def test_unified_answer_multi_select_comma_join() -> None:
    """T-UNIFIED-MULTI-SELECT equivalent — labels joined with ", "."""
    merged = "Python, Go"
    action = DialogAction(kind="unified_answer", text=merged)
    keys = DialogActuator().encode(action, _screen())
    assert keys == _expected_unified(merged)


def test_unified_answer_empty_text_legal() -> None:
    """Empty merged text — paste of zero bytes + CR submits TUI default."""
    action = DialogAction(kind="unified_answer", text="")
    keys = DialogActuator().encode(action, _screen())
    assert keys == ESCAPE + PASTE_START + PASTE_END + ENTER


def test_unified_answer_requires_text_not_none() -> None:
    """``unified_answer`` requires text (may be empty string but not None)."""
    with pytest.raises(ValueError, match="unified_answer.*requires text"):
        DialogAction(kind="unified_answer", text=None)
