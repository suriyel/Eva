"""F18 W4 · Claude TUI dialog auto-handler (refactor extracted from
``run_real_hil_round_trip``).

Layered abstraction:

  bytes (PTY stdout) → DialogScreen → DialogAction → bytes (PTY stdin keys)
                       └─ recognize ─┘└─ decide ───┘└─ actuate ─┘

Each layer has a Protocol + a default ``Catalog*`` implementation backed by a
hardcoded table, plus ``LLM*`` stubs reserved for the next increment
(see docs/explore notes — wired but raise NotImplementedError until the
follow-up FR lands).

Usage:

    recognizer = ChainRecognizer([CatalogRecognizer(), LLMRecognizer()])
    decider    = CatalogDecider(DEFAULT_POLICIES)
    actuator   = DialogActuator()

    screen = recognizer.recognize(screen_text)
    if screen and screen.name not in (None, "main-prompt"):
        action = decider.decide(screen)
        keys = actuator.encode(action, screen)
        pty.write(keys)
"""

from __future__ import annotations

from harness.cli_dialog.actuator import DialogActuator
from harness.cli_dialog.catalog import DEFAULT_POLICIES, KNOWN_DIALOGS
from harness.cli_dialog.decider import (
    CatalogDecider,
    DelegatingDecider,
    DialogDecider,
    LLMDecider,
    UnknownDialogError,
)
from harness.cli_dialog.models import (
    ChoiceItem,
    DialogAction,
    DialogScreen,
)
from harness.cli_dialog.recognizer import (
    CatalogRecognizer,
    ChainRecognizer,
    DialogRecognizer,
    LLMRecognizer,
)

__all__ = [
    "ChoiceItem",
    "DialogAction",
    "DialogScreen",
    "DialogRecognizer",
    "CatalogRecognizer",
    "LLMRecognizer",
    "ChainRecognizer",
    "DialogDecider",
    "CatalogDecider",
    "LLMDecider",
    "DelegatingDecider",
    "UnknownDialogError",
    "DialogActuator",
    "DEFAULT_POLICIES",
    "KNOWN_DIALOGS",
]
