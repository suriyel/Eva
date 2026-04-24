"""F18 · Bk-Adapter — adapter subpackage.

Re-exports the runtime_checkable ToolAdapter Protocol + CapabilityFlags enum
so callers can ``from harness.adapter import ToolAdapter``.
"""

from __future__ import annotations

from harness.adapter.protocol import CapabilityFlags, ToolAdapter

__all__ = ["CapabilityFlags", "ToolAdapter"]
