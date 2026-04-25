"""F20 · RetryPolicy + RetryCounter.

Pure functions / in-memory dictionaries — no external dependencies.

Design §Boundary table:
    * context_overflow → 0/0/0 immediate, then escalate at retry_count==3
    * rate_limit       → 30 / 120 / 300 / None
    * network          → 0 / 60 / None
    * timeout          → uses context_overflow ramp (0 / 0 / 0 / None) per
                          state diagram; not directly exercised by Red tests
"""

from __future__ import annotations


_RATE_LIMIT_SEQUENCE: tuple[float, ...] = (30.0, 120.0, 300.0)
_NETWORK_SEQUENCE: tuple[float, ...] = (0.0, 60.0)
_CONTEXT_OVERFLOW_LIMIT = 3
_TIMEOUT_LIMIT = 3


class RetryPolicy:
    """Pure function: ``(cls, retry_count) → delay_seconds | None``.

    ``scale_factor`` < 1 compresses the sequence for CI integration tests
    (T14) without altering the policy logic.
    """

    def __init__(self, *, scale_factor: float = 1.0) -> None:
        if scale_factor <= 0:
            raise ValueError(f"scale_factor must be > 0; got {scale_factor!r}")
        self._scale = float(scale_factor)

    def next_delay(self, cls: str, retry_count: int) -> float | None:
        if retry_count is None:
            raise TypeError("retry_count must not be None")
        if not isinstance(retry_count, int):
            raise TypeError(f"retry_count must be int; got {type(retry_count).__name__}")
        if retry_count < 0:
            raise ValueError(f"retry_count must be >= 0; got {retry_count}")

        if cls == "rate_limit":
            if retry_count >= len(_RATE_LIMIT_SEQUENCE):
                return None
            return _RATE_LIMIT_SEQUENCE[retry_count] * self._scale
        if cls == "network":
            if retry_count >= len(_NETWORK_SEQUENCE):
                return None
            return _NETWORK_SEQUENCE[retry_count] * self._scale
        if cls == "context_overflow":
            if retry_count >= _CONTEXT_OVERFLOW_LIMIT:
                return None
            return 0.0
        if cls == "timeout":
            if retry_count >= _TIMEOUT_LIMIT:
                return None
            return 0.0
        if cls == "skill_error":
            return None  # never retry skill_error
        # Unknown class — treat as no-retry to be safe.
        return None


class RetryCounter:
    """Per-skill anomaly counter (in-memory)."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def inc(self, skill_hint: str, cls: str) -> int:  # noqa: ARG002 - cls reserved
        new = self._counts.get(skill_hint, 0) + 1
        self._counts[skill_hint] = new
        return new

    def value(self, skill_hint: str) -> int:
        return self._counts.get(skill_hint, 0)

    def reset(self, skill_hint: str) -> None:
        self._counts.pop(skill_hint, None)


__all__ = ["RetryCounter", "RetryPolicy"]
