"""F19 · Classifier sub-package.

Public facade: ClassifierService + all key types.
"""

from __future__ import annotations

from .errors import (
    ClassifierHttpError,
    ClassifierProtocolError,
    ProviderPresetError,
    PromptStoreCorruptError,
    PromptStoreError,
    PromptValidationError,
    SsrfBlockedError,
)
from .fallback import FallbackDecorator
from .llm_backend import LlmBackend
from .models import (
    AnomalyLiteral,
    ClassifierConfig,
    ClassifierPrompt,
    ClassifierPromptRev,
    ClassifyRequest,
    ProviderLiteral,
    ProviderPreset,
    TestConnectionRequest,
    TestConnectionResult,
    Verdict,
    VerdictLiteral,
)
from .prompt_store import PromptStore
from .provider_presets import ProviderPresets
from .rule_backend import RuleBackend
from .service import ClassifierService

__all__ = [
    "ClassifierService",
    "LlmBackend",
    "RuleBackend",
    "FallbackDecorator",
    "PromptStore",
    "ProviderPresets",
    "ClassifyRequest",
    "Verdict",
    "ClassifierConfig",
    "ClassifierPrompt",
    "ClassifierPromptRev",
    "ProviderPreset",
    "TestConnectionRequest",
    "TestConnectionResult",
    "ProviderLiteral",
    "VerdictLiteral",
    "AnomalyLiteral",
    "ClassifierHttpError",
    "ClassifierProtocolError",
    "SsrfBlockedError",
    "ProviderPresetError",
    "PromptStoreError",
    "PromptStoreCorruptError",
    "PromptValidationError",
]
