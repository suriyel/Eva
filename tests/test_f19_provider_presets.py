"""F19 · Bk-Dispatch — ProviderPresets + SSRF validation tests.

Covers Test Inventory: T20, T21, T22, T23, T24.
SRS: FR-021 AC-1/AC-3 · ATS L89/L182 · §IC ProviderPresets.resolve / validate_base_url.

Layer marker:
  # [unit] — pure function; no I/O.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# T20 — SEC/ssrf — Traces To: FR-021 AC-3 · ATS L182
# Kills: metadata-service SSRF (link-local 169.254.169.254).
# ---------------------------------------------------------------------------
def test_t20_validate_base_url_rejects_link_local_metadata_service():
    from harness.dispatch.classifier.errors import SsrfBlockedError
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    with pytest.raises(SsrfBlockedError):
        ProviderPresets().validate_base_url("https://169.254.169.254/v1")


# ---------------------------------------------------------------------------
# T21 — SEC/ssrf — Traces To: FR-021 AC-3
# Kills: substring hostname match (e.g. endswith "openai.com" naive).
# ---------------------------------------------------------------------------
def test_t21_validate_base_url_rejects_hostname_substring_injection():
    from harness.dispatch.classifier.errors import SsrfBlockedError
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    with pytest.raises(SsrfBlockedError):
        # Legal-looking suffix, but actual hostname is *evil.com*.
        ProviderPresets().validate_base_url("http://open.bigmodel.cn.evil.com/v1")


# ---------------------------------------------------------------------------
# T22 — SEC/ssrf — Traces To: FR-021 AC-3 · ATS L182
# Kills: internal private-range IPs accepted for custom provider.
# ---------------------------------------------------------------------------
def test_t22_validate_base_url_rejects_rfc1918_private_ip_for_custom_provider():
    from harness.dispatch.classifier.errors import SsrfBlockedError
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    with pytest.raises(SsrfBlockedError):
        ProviderPresets().validate_base_url("http://10.0.0.1/v1")


# ---------------------------------------------------------------------------
# T23 — FUNC/happy — Traces To: FR-021 AC-1 · §IC resolve
# Kills: GLM preset base_url typos; missing default_model field.
# ---------------------------------------------------------------------------
def test_t23_resolve_glm_returns_expected_preset_fields():
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    preset = ProviderPresets().resolve("glm")

    assert preset.name == "glm"
    # Must be exactly the GLM base_url (catches typos like .com instead of .cn).
    assert preset.base_url == "https://open.bigmodel.cn/api/paas/v4/"
    assert preset.default_model == "glm-4-plus"
    assert preset.api_key_user_slot == "glm"


# ---------------------------------------------------------------------------
# T24 — BNDRY/edge — Traces To: §IC resolve
# Kills: unknown provider silently accepted.
# ---------------------------------------------------------------------------
def test_t24_resolve_unknown_provider_raises_provider_preset_error():
    from harness.dispatch.classifier.errors import ProviderPresetError
    from harness.dispatch.classifier.provider_presets import ProviderPresets

    with pytest.raises(ProviderPresetError):
        ProviderPresets().resolve("anthropic-secret")  # not in enum
