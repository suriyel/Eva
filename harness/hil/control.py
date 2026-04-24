"""F18 · Bk-Adapter — HilControlDeriver (Design §4 row + FR-010 rule matrix).

Rule matrix (Design §4 row HilControlDeriver.derive):
  - multi_select == True                                          → multi_select
  - allow_freeform == True AND len(options) == 0                  → free_text
  - len(options) >= 2                                             → single_select
  - len(options) == 1 + freeform                                  → single_select (含 "其他…")
  - len(options) == 1 (no freeform)                               → single_select
  - len(options) == 0 (no freeform)                               → free_text (fallback per §Boundary)
"""

from __future__ import annotations

from typing import Any, Literal

ControlKind = Literal["single_select", "multi_select", "free_text"]


class HilControlDeriver:
    """Pure rule-matrix mapping (raw question dict) → control kind."""

    def derive(self, raw: dict[str, Any]) -> ControlKind:
        multi = bool(raw.get("multi_select", False))
        options = raw.get("options") or []
        freeform = bool(raw.get("allow_freeform", False))

        if multi:
            return "multi_select"
        if not options and freeform:
            return "free_text"
        if not options and not freeform:
            # Edge per §Boundary: empty options + no freeform → still falls back
            # to free_text (T10 covers this). The HilExtractor warns separately.
            return "free_text"
        # options non-empty → single_select (covers len 1 with freeform "其他",
        # len 1 without freeform, len ≥2)
        return "single_select"


__all__ = ["HilControlDeriver", "ControlKind"]
