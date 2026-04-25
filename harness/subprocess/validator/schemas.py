"""Pydantic schemas for ValidatorRunner / IAPI-016 (Design §6.2.4)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ValidatorScript = Literal[
    "validate_features",
    "validate_guide",
    "check_configs",
    "check_st_readiness",
]


class ValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    path: str
    script: ValidatorScript | None = None
    workdir: Any = None  # Path-like; arbitrary_types_allowed=True keeps this loose
    timeout_s: float = 60.0


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["error", "warning", "info"] = "error"
    rule_id: str | None = None
    path_json_pointer: str | None = None
    message: str = ""


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = False
    issues: list[ValidationIssue] = Field(default_factory=list)
    script_exit_code: int = 0
    duration_ms: int = 0
    http_status_hint: int = 200


__all__ = [
    "ValidateRequest",
    "ValidationIssue",
    "ValidationReport",
    "ValidatorScript",
]
