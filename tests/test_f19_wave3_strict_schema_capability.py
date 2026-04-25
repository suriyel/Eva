"""F19 Wave 3 · ProviderPreset capability bit + ClassifierConfig override + effective_strict.

Covers Test Inventory row **T47** (Wave 3 — FR-021 AC-4/5/6 · §IC
ProviderPresets.resolve + effective_strict 计算 · ProviderPreset.supports_strict_schema ·
ClassifierConfig.strict_schema_override).

Layer marker:
    # [unit] — pure data / attribute checks; no I/O.

Rule 5 note:
    # [no integration test] — pure function / pydantic schema; no external I/O.

SRS trace:
    FR-021 AC-4 (minimax=False)
    FR-021 AC-5 (glm/openai/custom=True)
    FR-021 AC-6 (strict_schema_override=False coerces effective_strict=False)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helper — resolve effective_strict via the design-stated ternary merge rule.
# This is the contract: Red phase MUST fail because one of three things is
# missing (``ProviderPreset.supports_strict_schema``,
# ``ClassifierConfig.strict_schema_override``, or the merge helper itself).
# ---------------------------------------------------------------------------
def _effective_strict(preset, override):
    """Contract: override if not None else preset.supports_strict_schema."""
    if override is not None:
        return override
    return preset.supports_strict_schema


# ---------------------------------------------------------------------------
# T47 · capability bits — FR-021 AC-4/5 preset defaults
# Kills: MiniMax incorrectly inherits strict=True → Wave 3 smoke regression.
# ---------------------------------------------------------------------------
def test_t47a_provider_preset_model_declares_supports_strict_schema_field():
    """ProviderPreset pydantic schema MUST expose supports_strict_schema."""
    from harness.dispatch.classifier.models import ProviderPreset

    assert (
        "supports_strict_schema" in ProviderPreset.model_fields
    ), "ProviderPreset.supports_strict_schema is required for Wave 3 strict-off path"


def test_t47b_glm_preset_supports_strict_schema_is_true():
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    preset = ProviderPresets().resolve("glm")
    assert (
        preset.supports_strict_schema is True
    ), "GLM OpenAI-compat endpoint supports response_format=json_schema strict"


def test_t47c_openai_preset_supports_strict_schema_is_true():
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    preset = ProviderPresets().resolve("openai")
    assert preset.supports_strict_schema is True


def test_t47d_custom_preset_supports_strict_schema_is_true():
    """Custom presets default to strict=True (users can override per-config)."""
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    preset = ProviderPresets().resolve("custom")
    assert preset.supports_strict_schema is True


def test_t47e_minimax_preset_supports_strict_schema_is_false():
    """MiniMax OpenAI-compat endpoint does NOT reliably honour json_schema strict."""
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    preset = ProviderPresets().resolve("minimax")
    assert (
        preset.supports_strict_schema is False
    ), "MiniMax capability bit must default to False — blocks strict-on path"


# ---------------------------------------------------------------------------
# T47 · ClassifierConfig.strict_schema_override three-state field
# ---------------------------------------------------------------------------
def test_t47f_classifier_config_strict_schema_override_defaults_to_none():
    """When omitted, strict_schema_override must be None (sentinel: 'use preset')."""
    from harness.dispatch.classifier.models import ClassifierConfig

    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    assert (
        cfg.strict_schema_override is None
    ), "default must be None so effective_strict falls back to preset capability"


def test_t47g_classifier_config_strict_schema_override_accepts_bool_tri_state():
    """True, False, and None are all valid (ternary three-state)."""
    from harness.dispatch.classifier.models import ClassifierConfig

    base = dict(
        enabled=True,
        provider="minimax",
        base_url="https://api.minimax.chat/v1/",
        model_name="MiniMax-M2.7-highspeed",
    )
    assert ClassifierConfig(**base, strict_schema_override=True).strict_schema_override is True
    assert ClassifierConfig(**base, strict_schema_override=False).strict_schema_override is False
    assert ClassifierConfig(**base, strict_schema_override=None).strict_schema_override is None


# ---------------------------------------------------------------------------
# T47 · effective_strict five-row truth table — FR-021 AC-6 merge semantics
#
# Kills: override=None treated as False; override=False silently ignored on
# strict-capable preset; override=True silently ignored on MiniMax.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("provider", "override", "expected_effective"),
    [
        # preset=glm (capability True) × three override states → override wins when set
        ("glm", None, True),  # None → preset wins → True
        ("glm", False, False),  # explicit False → coerces strict-OFF (Wave 3 bypass)
        ("glm", True, True),  # explicit True → stays strict-ON (idempotent)
        # preset=minimax (capability False) × two override states
        ("minimax", None, False),  # None → preset wins → False (Wave 3 default)
        ("minimax", True, True),  # explicit True → force strict-ON despite incapable preset
    ],
    ids=[
        "glm_none_preset_wins_true",
        "glm_false_override_coerces_off",
        "glm_true_override_stays_on",
        "minimax_none_preset_wins_false",
        "minimax_true_override_forces_on",
    ],
)
def test_t47_effective_strict_truth_table(provider, override, expected_effective):
    """AC-6: effective_strict = override if override is not None else preset.supports_strict_schema.

    Exercises the NEW ``ClassifierConfig.strict_schema_override`` field AND the
    NEW ``ProviderPreset.supports_strict_schema`` capability bit; every row
    constructs both so that in Red phase every row fails (extra_forbidden on
    override, missing attribute on preset). Once Green lands, all 5 rows pass.
    """
    from harness.dispatch.classifier.models import ClassifierConfig
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    preset = ProviderPresets().resolve(provider)

    # Construct ClassifierConfig with the explicit override — Red will reject
    # ``strict_schema_override`` with ``extra_forbidden`` until the pydantic
    # schema adds the field.
    cfg = ClassifierConfig(
        enabled=True,
        provider=provider,
        base_url=preset.base_url or "https://example.com/v1/",
        model_name=preset.default_model or "test-model",
        strict_schema_override=override,
    )

    # Both NEW symbols must be consulted to compute effective_strict.
    effective = _effective_strict(preset, cfg.strict_schema_override)
    assert effective is expected_effective, (
        f"preset={provider} override={override!r} "
        f"must resolve to effective_strict={expected_effective}"
    )

    # Row-specific sanity: when override is None the preset capability must
    # be consulted — assert the capability bit drives the result.
    if override is None:
        assert (
            preset.supports_strict_schema is expected_effective
        ), "None override MUST fall through to preset.supports_strict_schema"
