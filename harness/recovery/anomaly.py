"""F20 · AnomalyClassifier — maps Verdict + ClassifyRequest to AnomalyClass.

Heuristics align with Design §State-Diagram:
    * stdout_tail starts with ``[CONTRACT-DEVIATION]``  → SKILL_ERROR (passthrough)
    * verdict.anomaly == ``context_overflow`` / ``rate_limit`` / ``network`` /
      ``timeout`` / ``skill_error``                     → mapped 1:1
    * stderr_tail matches ``context window`` / ``token limit``  → CONTEXT_OVERFLOW
    * stderr_tail contains ``ECONNREFUSED`` / ``DNS``           → NETWORK_ERROR
    * stderr_tail contains ``429`` / ``rate limit``             → RATE_LIMIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from harness.dispatch.classifier.models import ClassifyRequest, Verdict


class AnomalyClass(str, Enum):
    CONTEXT_OVERFLOW = "context_overflow"
    RATE_LIMIT = "rate_limit"
    NETWORK_ERROR = "network"
    TIMEOUT = "timeout"
    SKILL_ERROR = "skill_error"
    NONE = "none"


@dataclass
class AnomalyInfo:
    cls: AnomalyClass
    detail: str = ""
    next_action: Literal["retry", "abort", "escalate", "continue"] = "continue"


_CONTEXT_OVERFLOW_RE = re.compile(r"context window|exceeded max tokens|token limit", re.IGNORECASE)
_RATE_LIMIT_RE = re.compile(r"429|rate.?limit", re.IGNORECASE)
_NETWORK_RE = re.compile(r"econnrefused|dns|getaddrinfo|connection reset", re.IGNORECASE)


class AnomalyClassifier:
    """Map Verdict / classifier output → AnomalyClass + recovery action."""

    def classify(self, req: ClassifyRequest, verdict: Verdict) -> AnomalyInfo:
        # CONTRACT-DEVIATION passthrough (FR-028)
        stdout = req.stdout_tail or ""
        if stdout.lstrip().startswith("[CONTRACT-DEVIATION]"):
            return AnomalyInfo(
                cls=AnomalyClass.SKILL_ERROR,
                detail=stdout.splitlines()[0] if stdout else "",
                next_action="abort",
            )

        # Honour Verdict's anomaly hint when present.
        if verdict.anomaly is not None:
            mapped = AnomalyClass(verdict.anomaly)
            if mapped is AnomalyClass.SKILL_ERROR:
                return AnomalyInfo(cls=mapped, detail=verdict.reason, next_action="abort")
            return AnomalyInfo(cls=mapped, detail=verdict.reason, next_action="retry")

        # Fallback to stderr heuristics
        stderr = req.stderr_tail or ""
        if _CONTEXT_OVERFLOW_RE.search(stderr):
            return AnomalyInfo(
                cls=AnomalyClass.CONTEXT_OVERFLOW, detail=stderr[-200:], next_action="retry"
            )
        if _RATE_LIMIT_RE.search(stderr):
            return AnomalyInfo(
                cls=AnomalyClass.RATE_LIMIT, detail=stderr[-200:], next_action="retry"
            )
        if _NETWORK_RE.search(stderr):
            return AnomalyInfo(
                cls=AnomalyClass.NETWORK_ERROR, detail=stderr[-200:], next_action="retry"
            )

        if verdict.verdict == "ABORT":
            return AnomalyInfo(
                cls=AnomalyClass.SKILL_ERROR, detail=verdict.reason, next_action="abort"
            )
        return AnomalyInfo(cls=AnomalyClass.NONE, detail="", next_action="continue")


__all__ = ["AnomalyClass", "AnomalyClassifier", "AnomalyInfo"]
