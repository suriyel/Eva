"""F10 · Environment isolation data models (pydantic v2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IsolatedPaths(BaseModel):
    """IAPI-017 Provider schema — returned by EnvironmentIsolator.setup_run.

    Matches Design §6.2.4 IsolatedPaths { cwd, plugin_dir, settings_path,
    mcp_config_path }.
    """

    model_config = ConfigDict(extra="forbid")

    cwd: str
    plugin_dir: str
    settings_path: str
    mcp_config_path: str | None = None


class HomeMtimeSnapshot(BaseModel):
    """Before/after ~/.claude mtime_ns snapshot."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    root: Any  # Path; arbitrary_types_allowed so we accept pathlib.Path directly
    entries: dict[str, int] = Field(default_factory=dict)


class HomeMtimeChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    before_ns: int
    after_ns: int


class HomeMtimeDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changed_files: list[HomeMtimeChange] = Field(default_factory=list)
    added_files: list[str] = Field(default_factory=list)
    removed_files: list[str] = Field(default_factory=list)
    ok: bool = True
    # Optional convenience: count of untouched files
    untouched_files_count: int = 0


class WorkdirScopeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unexpected_new: list[str] = Field(default_factory=list)
    ok: bool = True


__all__ = [
    "IsolatedPaths",
    "HomeMtimeSnapshot",
    "HomeMtimeChange",
    "HomeMtimeDiff",
    "WorkdirScopeReport",
]
