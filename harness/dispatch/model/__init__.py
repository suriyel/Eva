"""F19 · Model-resolver sub-package.

Public facade:
    ModelResolver           — 4-layer priority resolver.
    ModelRulesStore         — JSON persistence for rules.
    ModelRule / ModelOverrideContext / ResolveResult — schema.
"""

from __future__ import annotations

from .models import ModelOverrideContext, ModelRule, ResolveResult
from .resolver import ModelResolver
from .rules_store import ModelRulesCorruptError, ModelRulesStore, ModelRulesStoreError

__all__ = [
    "ModelResolver",
    "ModelRulesStore",
    "ModelRulesCorruptError",
    "ModelRulesStoreError",
    "ModelRule",
    "ModelOverrideContext",
    "ResolveResult",
]
