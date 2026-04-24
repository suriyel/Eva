"""F18 · Bk-Adapter — stream subpackage exceptions."""

from __future__ import annotations


class StreamError(Exception):
    """Base stream-layer error."""


__all__ = ["StreamError"]
