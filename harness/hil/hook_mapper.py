"""F18 Wave 4 · HookEventMapper — hook stdin JSON → HilQuestion[].

Per Design §Interface Contract HookEventMapper.parse + FR-009 + ASM-009 +
IFR-001 hook stdin schema.

Behaviour:
  - Only ``hook_event_name == "PreToolUse"`` AND
    ``tool_name in {"AskUserQuestion", "Question"}`` derive a HilQuestion list;
    other events → empty list (no raise).
  - Each question's ``id`` is derived from ``tool_use_id`` + index.
  - Each string field is truncated at 256 UTF-8 bytes (FR-009 BNDRY).
  - Missing fields fall back to defaults with a warning log (FR-009 AC-3).
  - kind derivation delegates to HilControlDeriver (FR-010 reuse).
"""

from __future__ import annotations

import logging
from typing import Any

from harness.domain.ticket import HilOption, HilQuestion
from harness.hil.control import HilControlDeriver

_log = logging.getLogger(__name__)

_HIL_TOOL_NAMES: frozenset[str] = frozenset({"AskUserQuestion", "Question"})
_MAX_BYTES = 256
_ELLIPSIS = "…"


def _truncate_utf8(s: str, limit: int = _MAX_BYTES) -> str:
    """Truncate so UTF-8 byte length <= limit; append ellipsis if truncated.

    Implementation detail: when truncating, we reserve room for the ellipsis
    inside the limit so the final byte length stays <= limit (FR-009 BNDRY).
    """
    if not isinstance(s, str):
        s = str(s)
    encoded = s.encode("utf-8")
    if len(encoded) <= limit:
        return s
    # Ellipsis (…) is 3 bytes in UTF-8; reserve room.
    ellipsis_bytes = _ELLIPSIS.encode("utf-8")
    head_budget = max(0, limit - len(ellipsis_bytes))
    return encoded[:head_budget].decode("utf-8", errors="ignore") + _ELLIPSIS


class HookEventMapper:
    """Parse hook stdin JSON payload (or HookEventPayload) → HilQuestion[]."""

    def __init__(self, deriver: HilControlDeriver | None = None) -> None:
        self._deriver = deriver or HilControlDeriver()

    # ------------------------------------------------------------------
    def parse(self, payload: Any) -> list[HilQuestion]:
        """Map a hook stdin JSON dict (or HookEventPayload) to HilQuestion[].

        Never raises (FR-009 healthiness): unknown / non-HIL hooks → ``[]``.
        """
        # Accept both pydantic HookEventPayload and raw dict.
        data: dict[str, Any]
        if hasattr(payload, "model_dump"):
            data = payload.model_dump()
        elif isinstance(payload, dict):
            data = payload
        else:
            return []

        hook_event_name = data.get("hook_event_name")
        tool_name = data.get("tool_name")
        if hook_event_name != "PreToolUse":
            return []
        if tool_name not in _HIL_TOOL_NAMES:
            return []

        tool_input = data.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return []
        questions_raw = tool_input.get("questions")
        if not isinstance(questions_raw, list):
            return []

        tool_use_id = data.get("tool_use_id") or "toolu_unknown"
        out: list[HilQuestion] = []
        for idx, raw in enumerate(questions_raw):
            if not isinstance(raw, dict):
                _log.warning(
                    "HookEventMapper: skipping non-dict question entry index=%d", idx
                )
                continue
            out.append(self._normalise(raw, str(tool_use_id), idx))
        return out

    # ------------------------------------------------------------------
    def record_pending(self, bus: Any, payload: Any, questions: list[HilQuestion]) -> None:
        """Append the payload's tool_use_id to bus.tool_use_id_queue.

        Used by the HookRouter and SessionEnd handler (FR-014 replacement
        logic per Design rationale (e)).
        """
        if not questions:
            return
        # Accept raw dict or pydantic HookEventPayload.
        tool_use_id: Any
        if hasattr(payload, "tool_use_id"):
            tool_use_id = payload.tool_use_id
        elif isinstance(payload, dict):
            tool_use_id = payload.get("tool_use_id")
        else:
            tool_use_id = None
        if tool_use_id is None:
            return
        if not hasattr(bus, "tool_use_id_queue"):
            return
        bus.tool_use_id_queue.append(str(tool_use_id))

    # ------------------------------------------------------------------
    def _normalise(self, raw: dict[str, Any], tool_use_id: str, idx: int) -> HilQuestion:
        header = raw.get("header") or raw.get("title") or ""
        question = raw.get("question") or raw.get("prompt") or ""
        multi_select = bool(raw.get("multiSelect", raw.get("multi_select", False)))
        allow_freeform = bool(
            raw.get("allowFreeformInput", raw.get("allow_freeform", False))
        )

        if "options" not in raw:
            _log.warning(
                "HookEventMapper: question missing 'options' field — defaulting to []"
            )
            options_raw: list[Any] = []
        else:
            options_raw = raw.get("options") or []
            if not isinstance(options_raw, list):
                _log.warning("HookEventMapper: options not a list — coercing to []")
                options_raw = []

        options: list[HilOption] = []
        for o in options_raw:
            if isinstance(o, dict):
                label = _truncate_utf8(str(o.get("label", "")))
                desc = o.get("description")
                description = _truncate_utf8(str(desc)) if desc is not None else None
            else:
                label = _truncate_utf8(str(o))
                description = None
            options.append(HilOption(label=label, description=description))

        kind = self._deriver.derive(
            {
                "multi_select": multi_select,
                "options": options_raw,
                "allow_freeform": allow_freeform,
            }
        )

        qid = f"{tool_use_id}-{idx}"
        return HilQuestion(
            id=qid,
            kind=kind,
            header=_truncate_utf8(str(header)),
            question=_truncate_utf8(str(question)),
            options=options,
            multi_select=multi_select,
            allow_freeform=allow_freeform,
        )


__all__ = ["HookEventMapper"]
