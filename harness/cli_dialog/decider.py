"""DialogDecider — DialogScreen → DialogAction."""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from harness.cli_dialog.catalog import DEFAULT_POLICIES
from harness.cli_dialog.models import DialogAction, DialogScreen


@runtime_checkable
class DialogDecider(Protocol):
    """Strategy interface for picking an action given a recognised dialog."""

    def decide(self, screen: DialogScreen) -> DialogAction: ...


class CatalogDecider:
    """Look up the action for a known dialog name in a policy table.

    Default policy table: ``DEFAULT_POLICIES``. Override the table to plug
    in different behaviour for production vs. UT (e.g. production wires
    ``DelegatingDecider`` so user sees + confirms the dialog).
    """

    def __init__(
        self, policies: Mapping[str, DialogAction] = DEFAULT_POLICIES
    ) -> None:
        self._policies = dict(policies)

    def decide(self, screen: DialogScreen) -> DialogAction:
        if screen.name is None:
            raise UnknownDialogError(
                "CatalogDecider cannot decide on an un-named DialogScreen "
                "(catalog miss). Wire LLMDecider via a chain to handle this."
            )
        action = self._policies.get(screen.name)
        if action is None:
            raise UnknownDialogError(
                f"No catalog policy for dialog name={screen.name!r}; "
                "extend DEFAULT_POLICIES or chain into LLMDecider."
            )
        return action


class LLMDecider:
    """LLM-backed decider for un-known or un-policied dialogs (stub).

    Reserved for the boot-dialog-handler increment. Expected protocol:

      1. Build a tool_use schema mirroring DialogAction.
      2. Send the DialogScreen + UT/production context to a small model.
      3. Strict-parse the tool_use payload back into a DialogAction.
      4. If the LLM picks an index out-of-range or violates schema → raise
         (don't guess on behalf of the user).

    Until the increment lands, calling ``decide`` raises NotImplementedError.
    """

    def __init__(self, *, llm_client: object | None = None) -> None:
        self._llm_client = llm_client

    def decide(self, screen: DialogScreen) -> DialogAction:
        raise NotImplementedError(
            "LLMDecider is reserved for the boot-dialog-handler increment; "
            "use CatalogDecider until the increment wires a real LLM client."
        )


class DelegatingDecider:
    """Production decider stub — dialog should be shown to the end user.

    Reserved for the boot-dialog-handler increment. Production spawn paths
    (F22 / F23 ticket dispatch) wire this so unknown / sensitive dialogs
    are surfaced through the same HilQuestion UI surface that
    PreToolUse(AskUserQuestion) hooks use.

    Until the increment lands, this raises NotImplementedError so any
    accidental injection in the test pipeline is caught early.
    """

    def __init__(self, *, hil_event_bus: object | None = None) -> None:
        self._hil_event_bus = hil_event_bus

    def decide(self, screen: DialogScreen) -> DialogAction:
        raise NotImplementedError(
            "DelegatingDecider is reserved for the boot-dialog-handler "
            "increment; wire HilEventBus + a UI round-trip when the "
            "increment lands."
        )


class UnknownDialogError(LookupError):
    """Raised when a decider has no policy for the screen's name."""


__all__ = [
    "DialogDecider",
    "CatalogDecider",
    "LLMDecider",
    "DelegatingDecider",
    "UnknownDialogError",
]
