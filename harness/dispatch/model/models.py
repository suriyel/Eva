"""F19 · Model resolver pydantic models.

Feature design §IC + §BC:
    * ModelOverrideContext — resolve input (4 layers).
    * ModelRule — persisted rule (skill? / tool / model).
    * ResolveResult — output (model | None + provenance).
    * ProvenanceTag — literal.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ToolLiteral = Literal["claude", "opencode"]
ProvenanceTag = Literal["per-ticket", "per-skill", "run-default", "cli-default"]


class ModelRule(BaseModel):
    """A single model-override rule (per-skill or global run-default)."""

    model_config = ConfigDict(extra="forbid")

    skill: str | None = None
    tool: ToolLiteral
    model: str = Field(min_length=1, max_length=64)


class ModelOverrideContext(BaseModel):
    """Input context for ModelResolver.resolve — the 4-layer decision input."""

    model_config = ConfigDict(extra="forbid")

    ticket_override: str | None = None
    skill_hint: str | None = None
    run_default: str | None = None
    tool: ToolLiteral


class ResolveResult(BaseModel):
    """Output of ModelResolver.resolve: chosen model + provenance."""

    model_config = ConfigDict(extra="forbid")

    model: str | None
    provenance: ProvenanceTag


__all__ = [
    "ModelRule",
    "ModelOverrideContext",
    "ResolveResult",
    "ProvenanceTag",
    "ToolLiteral",
]
