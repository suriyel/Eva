"""F18 Wave 4 · TuiKeyEncoder tests.

Test Inventory: T05, T06, T07, T08, T09, T10.
SRS: FR-053 / FR-011 / FR-053 SEC.
Design Trace: §Interface Contract TuiKeyEncoder rows + §Boundary Conditions.

Layer marker:
  # [unit] — pure encoding logic; no I/O / no PTY.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# T05 — BNDRY/edge — option_index 0 → ValueError (1-based)
# ---------------------------------------------------------------------------
def test_t05_encode_radio_rejects_zero_index_one_based():
    from harness.hil.tui_keys import TuiKeyEncoder

    with pytest.raises(ValueError):
        TuiKeyEncoder().encode_radio(0)


def test_t05b_encode_radio_rejects_negative_index():
    from harness.hil.tui_keys import TuiKeyEncoder

    with pytest.raises(ValueError):
        TuiKeyEncoder().encode_radio(-1)


# ---------------------------------------------------------------------------
# T06 — FUNC/happy — encode_radio byte equality
# ---------------------------------------------------------------------------
def test_t06_encode_radio_one_returns_b_one_cr():
    from harness.hil.tui_keys import TuiKeyEncoder

    out = TuiKeyEncoder().encode_radio(1)
    assert out == b"1\r", f"Expected b'1\\r', got {out!r}"
    # Hard-fail any \n usage
    assert b"\n" not in out


def test_t06b_encode_radio_nine_returns_b_nine_cr():
    """Boundary: 9 (claude TUI single-question max) → b'9\\r'."""
    from harness.hil.tui_keys import TuiKeyEncoder

    out = TuiKeyEncoder().encode_radio(9)
    assert out == b"9\r"


# ---------------------------------------------------------------------------
# T07 — FUNC/happy — encode_freeform bracketed-paste byte equality
# ---------------------------------------------------------------------------
def test_t07_encode_freeform_hello_exact_bytes():
    from harness.hil.tui_keys import TuiKeyEncoder

    out = TuiKeyEncoder().encode_freeform("hello")
    assert out == b"\x1b[200~hello\x1b[201~\r", f"Got {out!r}"
    # Sanity: bracketed-paste prefix and suffix and trailing CR all present
    assert out.startswith(b"\x1b[200~")
    assert out.endswith(b"\x1b[201~\r")


# ---------------------------------------------------------------------------
# T08 — SEC/inject — control char rejection in freeform
# ---------------------------------------------------------------------------
def test_t08_encode_freeform_rejects_etx_x03():
    from harness.adapter.errors import EscapeError
    from harness.hil.tui_keys import TuiKeyEncoder

    with pytest.raises(EscapeError):
        TuiKeyEncoder().encode_freeform("a\x03b")


def test_t08b_encode_freeform_rejects_eot_x04():
    from harness.adapter.errors import EscapeError
    from harness.hil.tui_keys import TuiKeyEncoder

    with pytest.raises(EscapeError):
        TuiKeyEncoder().encode_freeform("a\x04b")


def test_t08c_encode_freeform_rejects_bare_esc_x1b_outside_paste():
    """Embedded ESC outside the bracketed-paste wrapper added by encode_freeform itself."""
    from harness.adapter.errors import EscapeError
    from harness.hil.tui_keys import TuiKeyEncoder

    with pytest.raises(EscapeError):
        TuiKeyEncoder().encode_freeform("a\x1b[31mred\x1b[0m")


# ---------------------------------------------------------------------------
# T09 — BNDRY/edge — UTF-8 multibyte byte-equal preservation
# ---------------------------------------------------------------------------
def test_t09_encode_freeform_utf8_multibyte_byte_equal():
    from harness.hil.tui_keys import TuiKeyEncoder

    text = "中文😀"
    out = TuiKeyEncoder().encode_freeform(text)
    expected = b"\x1b[200~" + text.encode("utf-8") + b"\x1b[201~\r"
    assert out == expected, f"Got {out!r}, expected {expected!r}"


# ---------------------------------------------------------------------------
# T10 — FUNC/error — multi-question serial encoding
# ---------------------------------------------------------------------------
def test_t10_multi_question_serial_encoding_each_byte_equal_single():
    """Q1=opt2, Q2=opt1: each encode_radio bytes must equal single-shot encode."""
    from harness.hil.tui_keys import TuiKeyEncoder

    enc = TuiKeyEncoder()
    seq = [enc.encode_radio(2), enc.encode_radio(1)]
    assert seq[0] == b"2\r"
    assert seq[1] == b"1\r"
    # Must remain two distinct writes — never concatenated into a single write
    assert len(seq) == 2
    # No accidental mixing of newline encodings between rounds
    for chunk in seq:
        assert b"\n" not in chunk


def test_t10b_encode_interrupt_returns_etx():
    """FR-053 (c): interrupt is b'\\x03'."""
    from harness.hil.tui_keys import TuiKeyEncoder

    out = TuiKeyEncoder().encode_interrupt()
    assert out == b"\x03"


# ---------------------------------------------------------------------------
# Wave 4.1 (2026-04-27) — unified Esc-text protocol encoder tests.
#
# Layout:  ESC + ESC[200~ + text(utf-8) + ESC[201~ + CR
#   - The leading bare ESC clears any partial composition the TUI is holding
#   - The bracketed-paste body delivers the merged answer in one shot
#   - The trailing CR submits
# ---------------------------------------------------------------------------
def _expected_unified(merged_text: str) -> bytes:
    return (
        b"\x1b"
        + b"\x1b[200~"
        + merged_text.encode("utf-8")
        + b"\x1b[201~"
        + b"\r"
    )


def test_unified_radio_single_select_encoding() -> None:
    """T-UNIFIED-RADIO: single-select label → unified bytes."""
    from harness.hil.tui_keys import TuiKeyEncoder

    out = TuiKeyEncoder().encode_unified_answer("Python")
    assert out == _expected_unified("Python"), f"got {out!r}"


def test_unified_multi_select_merged_encoding() -> None:
    """T-UNIFIED-MULTI-SELECT: ", ".join(labels) → unified bytes."""
    from harness.hil.tui_keys import TuiKeyEncoder

    merged = "Python, Go"
    out = TuiKeyEncoder().encode_unified_answer(merged)
    assert out == _expected_unified(merged)


def test_unified_multi_question_concatenated_encoding() -> None:
    """T-UNIFIED-MULTI-QUESTION: 3 questions joined into one merged answer."""
    from harness.hil.tui_keys import TuiKeyEncoder

    # e.g. Lang/Test/CI all answered in one round
    merged = "Lang: Python; Test: pytest; CI: github-actions"
    out = TuiKeyEncoder().encode_unified_answer(merged)
    assert out == _expected_unified(merged)
    # Spot-check: prefix is bare ESC then bracketed-paste-start
    assert out.startswith(b"\x1b\x1b[200~")
    assert out.endswith(b"\x1b[201~\r")


def test_unified_freeform_encoding() -> None:
    """T-UNIFIED-FREEFORM: freeform body → unified bytes (UTF-8 preserved)."""
    from harness.hil.tui_keys import TuiKeyEncoder

    text = "我想要 Rust 语言 — 因为速度"
    out = TuiKeyEncoder().encode_unified_answer(text)
    assert out == _expected_unified(text)


def test_unified_empty_text_is_legal() -> None:
    """Empty merged text is permitted — paste of zero bytes + CR submits."""
    from harness.hil.tui_keys import TuiKeyEncoder

    out = TuiKeyEncoder().encode_unified_answer("")
    assert out == b"\x1b\x1b[200~\x1b[201~\r"


def test_unified_rejects_etx_x03() -> None:
    """SEC: \\x03 inside merged_text → EscapeError (no control-byte injection)."""
    from harness.adapter.errors import EscapeError
    from harness.hil.tui_keys import TuiKeyEncoder

    with pytest.raises(EscapeError):
        TuiKeyEncoder().encode_unified_answer("safe\x03injected")


def test_unified_rejects_bare_esc_outside_protocol_prefix() -> None:
    """SEC: \\x1b inside merged_text → EscapeError (the protocol prefix is
    the only ESC the encoder is allowed to emit)."""
    from harness.adapter.errors import EscapeError
    from harness.hil.tui_keys import TuiKeyEncoder

    with pytest.raises(EscapeError):
        TuiKeyEncoder().encode_unified_answer("color\x1b[31mred")
