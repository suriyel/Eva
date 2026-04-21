"""Pydantic v2 schema for ``~/.harness/config.json`` (F01 · Design §6).

Field contract:
    schema_version: int = 1
    provider_refs:  dict[str, ApiKeyRef]
    retention_run_count: int = 20
    ui_density: Literal["compact","comfortable"] = "comfortable"

``ApiKeyRef`` intentionally contains **only** ``service`` + ``user`` — any
plaintext key field is rejected by pydantic ``extra="forbid"`` and also
caught by the ``ConfigStore`` leak detector as defense-in-depth.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigCorruptError(Exception):
    """Raised when ``ConfigStore.load()`` cannot parse/validate config.json."""


class SecretLeakError(Exception):
    """Raised when ``ConfigStore.save()`` detects plaintext API key payload."""

    def __init__(self, field_path: str, message: str | None = None) -> None:
        self.field_path = field_path
        super().__init__(message or f"secret-like payload detected at {field_path!r}")


class ApiKeyRef(BaseModel):
    """Reference tuple (service, user) used to look up a secret in keyring.

    NEVER contains the secret value itself (NFR-008 + Design §6.1.6).
    """

    model_config = ConfigDict(extra="forbid")

    service: str
    user: str


class HarnessConfig(BaseModel):
    """Top-level schema for ``~/.harness/config.json`` (pydantic v2)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    provider_refs: dict[str, ApiKeyRef] = Field(default_factory=dict)
    retention_run_count: int = 20
    ui_density: Literal["compact", "comfortable"] = "comfortable"

    @classmethod
    def default(cls) -> "HarnessConfig":
        """Return a brand-new empty config (equivalent to first-run default)."""
        return cls()
