"""Harness config package — ``~/.harness/config.json`` facade.

Exports:
    ConfigStore        — load/save facade with atomic rename + secret-leak detector
    HarnessConfig      — pydantic v2 model (schema_version, provider_refs, ...)
    SecretLeakError    — raised when ``save()`` detects plaintext key in payload
    ConfigCorruptError — raised when ``load()`` fails JSON/pydantic validation
"""

from __future__ import annotations

from .schema import (
    ApiKeyRef,
    ConfigCorruptError,
    HarnessConfig,
    SecretLeakError,
)
from .store import ConfigStore

__all__ = [
    "ApiKeyRef",
    "ConfigCorruptError",
    "ConfigStore",
    "HarnessConfig",
    "SecretLeakError",
]
