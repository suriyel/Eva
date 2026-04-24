"""F18 · Bk-Adapter — ToolAdapter Protocol + CapabilityFlags enum.

Per Design §4 row ToolAdapter and rationale (Design §6):
  - ``typing.Protocol + @runtime_checkable`` (NOT ``abc.ABC``) so future
    GeminiAdapter classes don't need to inherit a concrete base.
  - Six methods: build_argv / spawn / extract_hil / parse_result /
    detect_anomaly / supports.
  - mypy ``--strict`` is enforced separately in env-guide §3.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from harness.adapter.process import TicketProcess
from harness.domain.ticket import (
    AnomalyInfo,
    DispatchSpec,
    HilQuestion,
    OutputInfo,
)
from harness.stream.events import StreamEvent


class CapabilityFlags(Enum):
    """Static capability flags reported by ToolAdapter.supports (Design §4)."""

    MCP_STRICT = "mcp_strict"
    HOOKS = "hooks"


@runtime_checkable
class ToolAdapter(Protocol):
    """Six-method contract every backend Agent CLI adapter must satisfy."""

    def build_argv(self, spec: DispatchSpec) -> list[str]: ...

    def spawn(self, spec: DispatchSpec) -> TicketProcess: ...

    def extract_hil(self, event: StreamEvent) -> list[HilQuestion]: ...

    def parse_result(self, events: list[StreamEvent]) -> OutputInfo: ...

    def detect_anomaly(self, events: list[StreamEvent]) -> AnomalyInfo | None: ...

    def supports(self, flag: CapabilityFlags) -> bool: ...


__all__ = ["CapabilityFlags", "ToolAdapter"]
