"""Unit tests for _split_keystrokes helper in run_real_hil_round_trip."""

from __future__ import annotations

import pytest

from harness.orchestrator.run import _split_keystrokes


@pytest.mark.parametrize(
    ("inp", "expected"),
    [
        (b"\x1b[B\r", [b"\x1b[B", b"\r"]),
        (b"\x1b[A\x1b[A\r", [b"\x1b[A", b"\x1b[A", b"\r"]),
        (
            b"\x1b[B \x1b[B \r",
            [b"\x1b[B", b" ", b"\x1b[B", b" ", b"\r"],
        ),
        (b"\r", [b"\r"]),
        (b"\x1b", [b"\x1b"]),
        (b"", []),
        (
            b"\x1b[200~hello\x1b[201~\r",
            [b"\x1b[200~hello\x1b[201~", b"\r"],
        ),
        # Multi-byte CSI with semicolon parameters
        (b"\x1b[5;3H\r", [b"\x1b[5;3H", b"\r"]),
    ],
)
def test_split_keystrokes(inp: bytes, expected: list[bytes]) -> None:
    assert _split_keystrokes(inp) == expected


def test_split_keystrokes_each_chunk_is_self_contained_keystroke():
    """Each chunk should be playable as a single PTY write that ink processes
    as one keypress. We assert no chunk contains ENTER co-mixed with other keys."""
    keys = b"\x1b[B\r\x1b[A "
    chunks = _split_keystrokes(keys)
    for chunk in chunks:
        # No single chunk should mix arrows with Enter / Space etc.
        if chunk == b"\r":
            continue
        if chunk.startswith(b"\x1b["):
            # Should end with a single CSI final byte
            assert chunk[-1:].isascii() and 0x40 <= chunk[-1] <= 0x7E
            # No trailing CR or extra bytes after CSI final
            continue
        assert len(chunk) == 1, (
            f"non-CSI chunk should be single byte; got {chunk!r}"
        )
