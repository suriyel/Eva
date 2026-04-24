"""F18 · Bk-Adapter — BannerConflictArbiter (Design §4 / §6 flowchart 2).

FR-014: When a ticket simultaneously emits a terminate banner AND has an
unanswered HIL question, HIL wins. Pure stateless function over an event
list, fixture-friendly per ATS requirement (≥10 fixtures).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from harness.stream.events import StreamEvent

Verdict = Literal["hil_waiting", "completed", "running"]

# Terminate banner markers (Design §4 row + 散文):
#   - Chinese "# 终止"
#   - English "terminated"
_BANNER_MARKERS: tuple[str, ...] = ("# 终止", "terminated")
# HIL tool names (FR-009, IFR-002):
_HIL_NAMES: frozenset[str] = frozenset({"AskUserQuestion", "Question"})


@dataclass(frozen=True)
class ArbitrationVerdict:
    """Result of BannerConflictArbiter.arbitrate (Design §4)."""

    verdict: Verdict
    has_hil: bool = False
    has_banner: bool = False


class BannerConflictArbiter:
    """Pure deterministic verdict from an event timeline."""

    def arbitrate(self, events: list[StreamEvent]) -> ArbitrationVerdict:
        has_hil = any(self._is_unanswered_hil(e) for e in events)
        has_banner = any(self._is_terminate_banner(e) for e in events)
        # Decision matrix per flowchart in Design §6:
        #   HIL=YES + Banner=YES → hil_waiting (FR-014: HIL wins)
        #   HIL=YES + Banner=NO  → hil_waiting
        #   HIL=NO  + Banner=YES → completed
        #   HIL=NO  + Banner=NO  → running
        if has_hil:
            verdict: Verdict = "hil_waiting"
        elif has_banner:
            verdict = "completed"
        else:
            verdict = "running"
        return ArbitrationVerdict(verdict=verdict, has_hil=has_hil, has_banner=has_banner)

    # ------------------------------------------------------------------
    @staticmethod
    def _is_unanswered_hil(event: StreamEvent) -> bool:
        if event.kind != "tool_use":
            return False
        name = event.payload.get("name")
        return name in _HIL_NAMES

    @staticmethod
    def _is_terminate_banner(event: StreamEvent) -> bool:
        if event.kind != "text":
            return False
        text = event.payload.get("text", "")
        if not isinstance(text, str):
            return False
        return any(marker in text for marker in _BANNER_MARKERS)


__all__ = ["BannerConflictArbiter", "ArbitrationVerdict", "Verdict"]
