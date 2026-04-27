"""F18 Wave 4 · HookEventPayload pydantic model (IAPI-020 request body).

Schema sourced from Design Implementation Summary §5 + system design §6.2.4
+ ASM-009 locked field set:

  Required: session_id, transcript_path, cwd, hook_event_name
  Optional: tool_name, tool_use_id, tool_input, ts

Permissive on extra (extra="allow"); the canonical key set is asserted by
the hook stdin schema canary test (T-HOOK-SCHEMA-CANARY).

Note on ``ts``: SRS IFR-001 line 867 originally listed ``ts`` as required,
but ASM-009 line 913 (the canonical schema lock) lists 7 fields without
``ts``. The puncture evidence (reference/f18-tui-bridge/evidence-summary.md
§C) confirms claude CLI 2.1.119 does NOT emit a ``ts`` key. Treating ``ts``
as optional aligns the pydantic validator with the ASM-009 + real-CLI
ground truth; the SRS IFR-001 wording will be reconciled in the next
increment.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


HookEventName = Literal[
    "PreToolUse",
    "PostToolUse",
    "SessionStart",
    "SessionEnd",
]


class HookEventPayload(BaseModel):
    """Hook stdin JSON payload (claude / opencode hook bridge POST body)."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    transcript_path: str
    cwd: str
    hook_event_name: HookEventName
    tool_name: str | None = None
    tool_use_id: str | None = None
    tool_input: dict[str, Any] | None = None
    ts: str | None = None


__all__ = ["HookEventName", "HookEventPayload"]
