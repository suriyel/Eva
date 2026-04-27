"""F18 · Bk-Adapter — adapter subpackage.

Wave 4 exports:
  - ``ToolAdapter`` Protocol + ``CapabilityFlags`` enum
  - ``HookEventPayload`` pydantic model (IAPI-020 request body)
"""

from __future__ import annotations

from harness.adapter.hook_payload import HookEventPayload
from harness.adapter.protocol import CapabilityFlags, ToolAdapter

__all__ = ["CapabilityFlags", "HookEventPayload", "ToolAdapter"]
