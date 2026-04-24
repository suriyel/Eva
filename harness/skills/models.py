"""F10 · Skills data models (pydantic v2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    commit_sha: str | None = None


class PluginSyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dst_plugin_dir: str
    manifest_sha256: str
    copied_file_count: int


class SkillsInstallRequest(BaseModel):
    """IAPI-018 request body."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["clone", "pull", "local"]
    source: str
    target_dir: str = ""


class SkillsInstallResult(BaseModel):
    """IAPI-018 response body."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    commit_sha: str | None = None
    message: str = ""


__all__ = [
    "PluginManifest",
    "PluginSyncResult",
    "SkillsInstallRequest",
    "SkillsInstallResult",
]
