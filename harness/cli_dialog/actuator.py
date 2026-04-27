"""Encodes a DialogAction into claude TUI keystroke bytes.

This is the only layer that knows about terminal escape sequences. Upstream
deciders (catalog / LLM / user-delegation) emit high-level DialogAction;
the actuator translates per the current claude TUI keymap (2.1.119, see
reference/f18-tui-bridge/README.md §5).
"""

from __future__ import annotations

from harness.cli_dialog.models import DialogAction, DialogScreen


# Keystroke constants — single source of truth for claude 2.1.119 TUI.
# Ref: reference/f18-tui-bridge/README.md §5 + puncture.py:248-252.
ARROW_UP = b"\x1b[A"
ARROW_DOWN = b"\x1b[B"
SPACE = b" "
ENTER = b"\r"
ESCAPE = b"\x1b"
PASTE_START = b"\x1b[200~"
PASTE_END = b"\x1b[201~"


class DialogActuator:
    """Translate (DialogAction, DialogScreen) → bytes for PTY stdin."""

    def encode(self, action: DialogAction, screen: DialogScreen) -> bytes:
        """Encode the action into the byte sequence claude TUI expects.

        Algorithms per action kind:

        - ``ignore`` → empty bytes (caller decides what to do).
        - ``cancel`` → ``ESC`` (matches "Esc to cancel" footer).
        - ``submit`` → ``Enter`` only (use the cursor's current highlight).
        - ``select`` (single, ``multi_select=False``):
            arrow-down/up to move cursor from ``screen.cursor_index`` →
            ``action.indices[0]``, then Enter.
        - ``select`` (multi, ``multi_select=True``):
            for each target index, walk cursor to it and emit Space (toggle),
            then Enter to submit.
        - ``freeform`` → bracketed paste of ``action.text`` + Enter.
        """
        if action.kind == "ignore":
            return b""

        if action.kind == "cancel":
            return ESCAPE

        if action.kind == "submit":
            return ENTER

        if action.kind == "freeform":
            assert action.text is not None  # validated in DialogAction.__post_init__
            return PASTE_START + action.text.encode("utf-8") + PASTE_END + ENTER

        if action.kind == "select":
            return self._encode_select(action, screen)

        raise ValueError(f"unknown DialogAction.kind={action.kind!r}")

    # ------------------------------------------------------------------
    @staticmethod
    def _encode_select(action: DialogAction, screen: DialogScreen) -> bytes:
        if not action.indices:
            raise ValueError("select action requires non-empty indices")

        # Cursor walk helper: (from, to) → arrow-down × |delta| or arrow-up × |delta|
        def _walk(from_idx: int, to_idx: int) -> bytes:
            if to_idx == from_idx:
                return b""
            step = ARROW_DOWN if to_idx > from_idx else ARROW_UP
            return step * abs(to_idx - from_idx)

        if not screen.multi_select:
            if len(action.indices) != 1:
                raise ValueError(
                    "single-select dialog accepts exactly 1 index; "
                    f"got {len(action.indices)}"
                )
            target = action.indices[0]
            return _walk(screen.cursor_index, target) + ENTER

        # Multi-select: walk to each target in order, toggle with Space, finally Enter.
        out = bytearray()
        cur = screen.cursor_index
        for target in action.indices:
            out += _walk(cur, target)
            out += SPACE
            cur = target
        out += ENTER
        return bytes(out)


__all__ = ["DialogActuator"]
