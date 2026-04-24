"""F18 · Bk-Adapter — re-export of domain HilQuestion (Design §6 散文).

The detailed design says this module is a "薄包装或直接 re-export
``harness.domain.ticket.HilQuestion``". We pick re-export to enforce
"0 重实现" (Existing Code Reuse table line 2).
"""

from __future__ import annotations

from harness.domain.ticket import HilAnswer, HilOption, HilQuestion

__all__ = ["HilAnswer", "HilOption", "HilQuestion"]
