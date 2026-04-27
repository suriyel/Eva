"""Structured data for claude TUI dialog handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# Action kinds — kept narrow + Literal-typed so deciders can't invent verbs
# the actuator doesn't know how to encode.
ActionKind = Literal["select", "submit", "cancel", "freeform", "ignore"]


@dataclass(frozen=True)
class ChoiceItem:
    """One option in a dialog menu."""

    index: int  # 1-based display index
    label: str
    selected: bool = False  # for multi-select (already-toggled state)


@dataclass(frozen=True)
class DialogScreen:
    """A recognised claude TUI dialog (post-render parse)."""

    name: str | None
    """
    Stable identifier of a known dialog
    (e.g. ``"bypass-permissions-consent"`` / ``"trust-folder"`` /
    ``"settings-error"``). ``None`` means the recognizer has not seen this
    layout before — the caller should either fall back to LLM recognition
    or escalate.
    """
    title: str
    body: str | None
    choices: tuple[ChoiceItem, ...]
    multi_select: bool
    allow_freeform: bool
    cursor_index: int  # 1-based; current ❯ highlight position


@dataclass(frozen=True)
class DialogAction:
    """High-level operation chosen for a DialogScreen.

    Decoupled from key bytes so policy code never needs to know which terminal
    escape sequence claude TUI accepts in 2.1.119 vs future versions.
    """

    kind: ActionKind
    indices: tuple[int, ...] = ()  # 1-based; for select / multi-select
    text: str | None = None  # for freeform
    rationale: str = ""  # used in audit logs + LLM tool_use input

    def __post_init__(self) -> None:
        if self.kind == "select" and not self.indices:
            raise ValueError("DialogAction(kind='select') requires non-empty indices")
        if self.kind == "freeform" and not self.text:
            raise ValueError("DialogAction(kind='freeform') requires text")
        for idx in self.indices:
            if idx < 1:
                raise ValueError(f"DialogAction.indices must be 1-based; got {idx}")


__all__ = [
    "ActionKind",
    "ChoiceItem",
    "DialogAction",
    "DialogScreen",
]
