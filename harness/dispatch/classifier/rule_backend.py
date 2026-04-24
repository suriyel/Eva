"""F19 · RuleBackend — hard-coded fallback classifier (pure function).

Feature design §IC RuleBackend.decide + §IS flowchart TD:
    1. has_termination_banner or stderr matches ``context window / exceeded max tokens
       / token limit`` → RETRY + anomaly=context_overflow.
    2. stderr matches ``rate limit / overloaded / HTTP 429`` → RETRY + rate_limit.
    3. stderr matches ``permission denied`` → ABORT (anomaly=None).
    4. exit_code == 0 AND no banner AND no stderr match → COMPLETED.
    5. Otherwise → ABORT + skill_error.

Boundary: stderr_tail / stdout_tail over 32 KB → keep tail (§BC row).
"""

from __future__ import annotations

import re

from .models import ClassifyRequest, Verdict


_MAX_TAIL_BYTES = 32 * 1024

_CONTEXT_RE = re.compile(r"context window|exceeded max tokens|token limit", re.IGNORECASE)
_RATE_RE = re.compile(r"rate limit|overloaded|http 429|\b429\b", re.IGNORECASE)
_PERM_RE = re.compile(r"permission denied", re.IGNORECASE)


def _tail(s: str, limit: int = _MAX_TAIL_BYTES) -> str:
    """Return the final ``limit`` bytes of ``s`` (decode-safe for utf-8)."""
    if not s:
        return ""
    encoded = s.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return s
    clipped = encoded[-limit:]
    # Decode may drop partial utf-8 at the head — that's fine for regex matching.
    return clipped.decode("utf-8", errors="replace")


class RuleBackend:
    """Hard-coded fallback classifier — never raises, returns Verdict(backend='rule')."""

    def decide(self, req: ClassifyRequest) -> Verdict:
        stderr = _tail(req.stderr_tail or "")
        banner = bool(req.has_termination_banner)

        # 1 — context_overflow (Banner / RateLimit branch order, per §IS flow).
        if banner or _CONTEXT_RE.search(stderr):
            return Verdict(
                verdict="RETRY",
                reason="context window exhausted / termination banner",
                anomaly="context_overflow",
                hil_source=None,
                backend="rule",
            )

        # 2 — rate_limit.
        if _RATE_RE.search(stderr):
            return Verdict(
                verdict="RETRY",
                reason="upstream rate-limited or overloaded",
                anomaly="rate_limit",
                hil_source=None,
                backend="rule",
            )

        # 3 — permission_denied.
        if _PERM_RE.search(stderr):
            return Verdict(
                verdict="ABORT",
                reason="permission denied (fatal)",
                anomaly=None,
                hil_source=None,
                backend="rule",
            )

        # 4 — clean exit.
        if req.exit_code == 0 and not stderr.strip():
            return Verdict(
                verdict="COMPLETED",
                reason="clean exit (code=0, empty stderr, no banner)",
                anomaly=None,
                hil_source=None,
                backend="rule",
            )

        # 5 — catch-all skill error.
        return Verdict(
            verdict="ABORT",
            reason="unclassified non-zero exit",
            anomaly="skill_error",
            hil_source=None,
            backend="rule",
        )


__all__ = ["RuleBackend"]
