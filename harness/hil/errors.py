"""F18 · Bk-Adapter — hil subpackage exceptions."""

from __future__ import annotations


class HilError(Exception):
    """Base HIL-layer error."""


__all__ = ["HilError"]
