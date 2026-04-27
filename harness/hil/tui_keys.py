"""F18 Wave 4 · TuiKeyEncoder — HilAnswer → Claude TUI key sequence bytes.

Per Design §Interface Contract TuiKeyEncoder rows + FR-053 + FR-011 SEC.

Encoding contract:
  - encode_radio(N) → b"<N>\\r"  (1-based; N >= 1)  [baseline fallback]
  - encode_checkbox([N1, N2, ...]) → multi-step keystrokes  [baseline fallback]
  - encode_freeform(text) → b"\\x1b[200~<text>\\x1b[201~\\r"  (bracketed paste + CR)
  - encode_interrupt() → b"\\x03"
  - encode_exit() → b"\\x03\\x03"
  - encode_unified_answer(text)  [Wave 4.1 default · 2026-04-27]
        → b"\\x1b" + b"\\x1b[200~" + text.encode("utf-8") + b"\\x1b[201~" + b"\\r"
        Single-shot Esc-text protocol that handles single-select, multi-select,
        multi-question, and freeform answers via one merged text payload.
        Audit closes via PreToolUse + UserPromptSubmit + Stop instead of the
        baseline PostToolUse path.

Security (FR-053 SEC + FR-011 SEC):
  encode_freeform / encode_unified_answer reject bare \\x03 / \\x04 / \\x1b
  inside the user-supplied text (the protocol-prefix Esc + bracketed-paste
  wrapper bytes are emitted by the encoder itself; user text MUST NOT
  contain them).
"""

from __future__ import annotations

from harness.adapter.errors import EscapeError


# Forbidden control bytes inside freeform text (the bracketed-paste wrapper
# is added by encode_freeform itself; user text MUST NOT contain them).
_FORBIDDEN_FREEFORM: frozenset[str] = frozenset({"\x03", "\x04", "\x1b"})


def _validate_freeform_text(text: str) -> None:
    """Reject bare \\x03 / \\x04 / \\x1b control bytes inside freeform text."""
    for ch in text:
        if ch in _FORBIDDEN_FREEFORM:
            raise EscapeError(
                f"freeform text contains forbidden control byte 0x{ord(ch):02x}"
            )


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
        _validate_freeform_text(text)
        return b"\x1b[200~" + text.encode("utf-8") + b"\x1b[201~\r"

    # ------------------------------------------------------------------
    def encode_unified_answer(self, text: str) -> bytes:
        """Wave 4.1 unified Esc-text protocol — single answer channel for HIL.

        Returns
            ``b"\\x1b" + b"\\x1b[200~" + text.encode("utf-8") + b"\\x1b[201~" + b"\\r"``

        The leading bare ESC discards any partial composition the TUI might
        be holding (e.g. if claude landed in compose mode after option-1
        highlighting); the bracketed-paste body delivers the merged answer
        text in one shot; the trailing CR submits it. This matches the puncture
        evidence A in §2.1: PreToolUse(AskUserQuestion) + 2nd UserPromptSubmit
        + Stop close the audit loop (PostToolUse does NOT fire under this
        path — by design).

        Use cases — ``text`` is the merged answer string for any of:
          - single-select (label of chosen option)
          - multi-select (e.g. "Python, Go")
          - multi-question form (concatenated per-question answers)
          - freeform/free-text answer

        Raises EscapeError if ``text`` contains the forbidden control bytes
        \\x03 / \\x04 / \\x1b (the protocol-prefix Esc + paste-start/end
        sequences are added by this method, not the caller).
        """
        _validate_freeform_text(text)
        return (
            b"\x1b"  # bare ESC: clear partial composition before paste
            + b"\x1b[200~"
            + text.encode("utf-8")
            + b"\x1b[201~"
            + b"\r"
        )

    # ------------------------------------------------------------------
    def encode_interrupt(self) -> bytes:
        """Encode an interrupt key (ETX, b'\\x03') per FR-053 (c)."""
        return b"\x03"

    # ------------------------------------------------------------------
    def encode_exit(self) -> bytes:
        """Encode an exit key (double ETX, b'\\x03\\x03') per FR-053 (c)."""
        return b"\x03\x03"


__all__ = ["TuiKeyEncoder"]
