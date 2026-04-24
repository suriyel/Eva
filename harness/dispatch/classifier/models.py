"""F19 · Classifier pydantic models.

Feature design §IC, §BC, §6.2.4:
    * ClassifyRequest / Verdict — IAPI-010 contract.
    * ClassifierConfig / TestConnectionRequest / TestConnectionResult — IAPI-002.
    * ClassifierPrompt / ClassifierPromptRev — IAPI-002 /api/prompts/classifier.
    * ProviderPreset — resolved preset tuple.

Schemas use ``ConfigDict(extra="forbid")`` to reject unknown fields (NFR-008
defense: forbid plaintext ``api_key`` on ClassifierConfig PUT path — T26).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProviderLiteral = Literal["glm", "minimax", "openai", "custom"]
VerdictLiteral = Literal["HIL_REQUIRED", "CONTINUE", "RETRY", "ABORT", "COMPLETED"]
AnomalyLiteral = Literal["context_overflow", "rate_limit", "network", "timeout", "skill_error"]


# ---------------------------------------------------------------------------
# ClassifyRequest / Verdict (IAPI-010)
# ---------------------------------------------------------------------------
class ClassifyRequest(BaseModel):
    """Input payload for ClassifierService.classify."""

    model_config = ConfigDict(extra="forbid")

    exit_code: int | None
    stderr_tail: str = ""
    stdout_tail: str = ""
    has_termination_banner: bool = False


class Verdict(BaseModel):
    """Classifier verdict payload (pydantic, IAPI-010)."""

    model_config = ConfigDict(extra="forbid")

    verdict: VerdictLiteral
    reason: str = ""
    anomaly: AnomalyLiteral | None = None
    hil_source: str | None = None
    backend: Literal["llm", "rule"]


# ---------------------------------------------------------------------------
# ClassifierConfig + TestConnection* (IAPI-002)
# ---------------------------------------------------------------------------
class ClassifierConfig(BaseModel):
    """Classifier configuration persisted in ``HarnessConfig`` extras.

    NFR-008: ``extra="forbid"`` prevents plaintext ``api_key`` from being
    smuggled in via PUT (T26).
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    provider: ProviderLiteral = "glm"
    base_url: str
    model_name: str
    api_key_ref: dict[str, str] | None = None


class TestConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderLiteral
    base_url: str
    model_name: str


class TestConnectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    latency_ms: int | None = None
    model_list: list[str] | None = None
    error_code: (
        Literal["401", "connection_refused", "dns_failure", "timeout", "ssrf_blocked"] | None
    ) = None
    message: str = ""


# ---------------------------------------------------------------------------
# ClassifierPrompt + history rev
# ---------------------------------------------------------------------------
class ClassifierPromptRev(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rev: int
    saved_at: str
    hash: str
    summary: str


class ClassifierPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current: str
    history: list[ClassifierPromptRev] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ProviderPreset
# ---------------------------------------------------------------------------
class ProviderPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProviderLiteral
    base_url: str
    default_model: str
    api_key_user_slot: str


__all__ = [
    "ClassifyRequest",
    "Verdict",
    "ClassifierConfig",
    "TestConnectionRequest",
    "TestConnectionResult",
    "ClassifierPrompt",
    "ClassifierPromptRev",
    "ProviderPreset",
    "ProviderLiteral",
    "VerdictLiteral",
    "AnomalyLiteral",
]
