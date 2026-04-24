"""F18 · Bk-Adapter — HilExtractor (Design §4 / §6).

Normalises a tool_use StreamEvent into HilQuestion[]:
  - 256B truncation on header / question / option labels (UTF-8 boundary safe)
  - Missing options → defaults to [] (warning logged) and kind=free_text
  - Auto-generates question.id when payload lacks one
  - Routes per-question raw dict through HilControlDeriver to compute `kind`

Reuse note (Design §Existing Code Reuse): HilQuestion / HilOption come from
``harness.domain.ticket`` — no schema redefinition.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from harness.domain.ticket import HilOption, HilQuestion
from harness.hil.control import HilControlDeriver
from harness.stream.events import StreamEvent

_log = logging.getLogger(__name__)

_MAX_BYTES = 256
_ELLIPSIS = "…"


def _truncate_utf8(s: str, limit: int = _MAX_BYTES) -> str:
    """Truncate a string so its UTF-8 byte length is ≤ limit, append ellipsis."""
    encoded = s.encode("utf-8")
    if len(encoded) <= limit:
        return s
    truncated = encoded[:limit].decode("utf-8", errors="ignore")
    return truncated + _ELLIPSIS


class HilExtractor:
    """Adapter-neutral HIL question extraction (FR-009 / FR-010)."""

    def __init__(self, deriver: HilControlDeriver | None = None) -> None:
        self._deriver = deriver or HilControlDeriver()

    def extract(self, event: StreamEvent) -> list[HilQuestion]:
        if event.kind != "tool_use":
            return []
        payload = event.payload or {}
        name = payload.get("name")
        if name not in ("AskUserQuestion", "Question"):
            return []
        questions_raw = (payload.get("input") or {}).get("questions") or []
        if not isinstance(questions_raw, list):
            _log.warning(
                "HilExtractor: questions payload is not a list (got %r)",
                type(questions_raw).__name__,
            )
            return []

        out: list[HilQuestion] = []
        for raw in questions_raw:
            if not isinstance(raw, dict):
                _log.warning("HilExtractor: skipping non-dict question entry %r", raw)
                continue
            out.append(self._normalise(raw))
        return out

    # ------------------------------------------------------------------
    def _normalise(self, raw: dict[str, Any]) -> HilQuestion:
        # Field harvesting tolerates both Claude (camelCase) and OpenCode (snake_case)
        header = raw.get("header") or raw.get("title") or ""
        question = raw.get("question") or raw.get("prompt") or ""
        multi_select = bool(raw.get("multiSelect", raw.get("multi_select", False)))
        allow_freeform = bool(raw.get("allowFreeformInput", raw.get("allow_freeform", False)))

        if "options" not in raw:
            _log.warning("HilExtractor: question missing 'options' field — defaulting to []")
            options_raw: list[dict[str, Any]] = []
        else:
            options_raw = raw.get("options") or []
            if not isinstance(options_raw, list):
                _log.warning("HilExtractor: options not a list, coercing to []")
                options_raw = []

        options = [
            HilOption(
                label=_truncate_utf8(str(o.get("label", "") if isinstance(o, dict) else o)),
                description=(
                    _truncate_utf8(str(o["description"]))
                    if isinstance(o, dict) and o.get("description") is not None
                    else None
                ),
            )
            for o in options_raw
        ]

        # Run control kind derivation using the normalised dict shape (snake_case).
        kind = self._deriver.derive(
            {
                "multi_select": multi_select,
                "options": options_raw,
                "allow_freeform": allow_freeform,
            }
        )

        qid = str(raw.get("id") or uuid.uuid4().hex)

        return HilQuestion(
            id=qid,
            kind=kind,
            header=_truncate_utf8(str(header)),
            question=_truncate_utf8(str(question)),
            options=options,
            multi_select=multi_select,
            allow_freeform=allow_freeform,
        )


__all__ = ["HilExtractor"]
