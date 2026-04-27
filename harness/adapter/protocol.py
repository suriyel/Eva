"""F18 Wave 4 · ToolAdapter Protocol (7 methods) + CapabilityFlags enum.

Wave 4 protocol-layer rewrite (Design §4.3 + commit 92538da):

  Methods (in canonical order):
    build_argv / prepare_workdir / spawn / map_hook_event /
    parse_result / detect_anomaly / supports

  ``extract_hil`` (Wave 3) is physically removed; replaced by ``map_hook_event``
  which consumes a ``HookEventPayload`` (the workdir-scoped hook stdin schema)
  rather than parsed StreamEvent.

NFR-014: ``typing.Protocol + @runtime_checkable`` so future GeminiAdapter does
not need to inherit a concrete base.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from harness.adapter.hook_payload import HookEventPayload
from harness.adapter.process import TicketProcess
from harness.domain.ticket import (
    AnomalyInfo,
    DispatchSpec,
    HilQuestion,
    OutputInfo,
)
from harness.env.models import IsolatedPaths
from harness.stream.events import StreamEvent


class CapabilityFlags(Enum):
    """Static capability flags reported by ToolAdapter.supports."""

    MCP_STRICT = "mcp_strict"
    HOOKS = "hooks"


@runtime_checkable
class ToolAdapter(Protocol):
    """Wave-4 7-method contract every backend Agent CLI adapter must satisfy."""

    def build_argv(self, spec: DispatchSpec) -> list[str]: ...

    def prepare_workdir(
        self, spec: DispatchSpec, paths: IsolatedPaths
    ) -> IsolatedPaths: ...

    def spawn(
        self, spec: DispatchSpec, paths: IsolatedPaths | None = None
    ) -> TicketProcess: ...

    def map_hook_event(self, payload: HookEventPayload) -> list[HilQuestion]: ...

    def parse_result(self, events: list[StreamEvent]) -> OutputInfo: ...

    def detect_anomaly(self, events: list[StreamEvent]) -> AnomalyInfo | None: ...

    def supports(self, flag: CapabilityFlags) -> bool: ...


__all__ = ["CapabilityFlags", "ToolAdapter"]
