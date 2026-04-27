"""F18 Wave 4 · TuiKeyEncoder — HilAnswer → Claude TUI key sequence bytes.

Per Design §Interface Contract TuiKeyEncoder rows + FR-053 + FR-011 SEC.

Encoding contract:
  - encode_radio(N) → b"<N>\\r"  (1-based; N >= 1)
  - encode_checkbox([N1, N2, ...]) → multi-step keystrokes
  - encode_freeform(text) → b"\\x1b[200~<text>\\x1b[201~\\r"  (bracketed paste + CR)
  - encode_interrupt() → b"\\x03"
  - encode_exit() → b"\\x03\\x03"

Security (FR-053 SEC + FR-011 SEC):
  encode_freeform rejects bare \\x03 / \\x04 / \\x1b inside the user-supplied
  text (i.e. outside the bracketed-paste wrapper added by this method).
"""

from __future__ import annotations

from harness.adapter.errors import EscapeError


# Forbidden control bytes inside freeform text (the bracketed-paste wrapper
# is added by encode_freeform itself; user text MUST NOT contain them).
_FORBIDDEN_FREEFORM: frozenset[str] = frozenset({"\x03", "\x04", "\x1b"})


class TuiKeyEncoder:
    """Encode HilAnswer payloads into Claude TUI key-sequence bytes."""

    # ------------------------------------------------------------------
    def encode_radio(self, option_index: int) -> bytes:
        """Encode a single-select option choice (1-based) → ``b"<N>\\r"``."""
        if option_index < 1:
            raise ValueError(
                f"option_index must be >= 1 (1-based per FR-053); got {option_index}"
            )
        return f"{option_index}\r".encode("ascii")

    # ------------------------------------------------------------------
    def encode_checkbox(self, option_indices: list[int]) -> bytes:
        """Encode a multi-select checkbox sequence.

        Wave 4 implements a simple deterministic sequence: for each toggled
        option index N (1-based) emit a down-arrow advance to it from the top
        plus a space toggle, then a final CR to confirm. Empty list → bare CR
        (confirm empty selection per §Boundary Conditions).
        """
        for idx in option_indices:
            if idx < 1:
                raise ValueError(
                    f"option_indices must all be >= 1 (1-based); got {option_indices!r}"
                )
        if not option_indices:
            return b"\r"
        # Walk the option menu from index 1 → max; toggle space at each
        # index in option_indices. Down arrow = ESC [ B.
        ordered = sorted(set(option_indices))
        out = bytearray()
        cursor = 1
        for idx in ordered:
            while cursor < idx:
                out.extend(b"\x1b[B")
                cursor += 1
            out.extend(b" ")  # space toggles
        out.extend(b"\r")
        return bytes(out)

    # ------------------------------------------------------------------
    def encode_freeform(self, text: str) -> bytes:
        """Encode a freeform-text answer using bracketed paste + CR.

        Returns ``b"\\x1b[200~" + text.encode("utf-8") + b"\\x1b[201~\\r"``.
        Raises EscapeError if text contains forbidden control bytes.
        """
        for ch in text:
            if ch in _FORBIDDEN_FREEFORM:
                raise EscapeError(
                    f"freeform text contains forbidden control byte 0x{ord(ch):02x}"
                )
        return b"\x1b[200~" + text.encode("utf-8") + b"\x1b[201~\r"

    # ------------------------------------------------------------------
    def encode_interrupt(self) -> bytes:
        """Encode an interrupt key (ETX, b'\\x03') per FR-053 (c)."""
        return b"\x03"

    # ------------------------------------------------------------------
    def encode_exit(self) -> bytes:
        """Encode an exit key (double ETX, b'\\x03\\x03') per FR-053 (c)."""
        return b"\x03\x03"


__all__ = ["TuiKeyEncoder"]
