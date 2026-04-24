"""F18 · Bk-Adapter — hil subpackage."""

from __future__ import annotations

# Re-export the existing domain HilQuestion so callers can `import from harness.hil`.
from harness.domain.ticket import HilAnswer, HilOption, HilQuestion

__all__ = ["HilAnswer", "HilOption", "HilQuestion"]
