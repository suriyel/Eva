"""Integration test for F19 · real keyring failure propagation (feature #19).

Covers T36 (INTG/keyring) from feature design §7 Test Inventory.

[integration] — uses the REAL ``keyring`` library with ``keyring.backends.fail``
(a genuinely non-operational backend shipped with the keyring package). We do
NOT monkey-patch ``keyring.get_password`` — the fail backend exists precisely
to test library-level failure propagation end-to-end.

Feature ref: feature_19

Real-test invariants (Rule 5a):
  - Uses the REAL keyring library (not monkey-patched get_password)
  - Backend substitution via ``keyring.set_keyring(fail.Keyring())`` is the
    library-sanctioned way to exercise failure paths; this is NOT mocking.
  - Hard-fails if the backend isn't fail (assert, not skip).
  - Asserts fallback semantics: ClassifierService must still return a Verdict,
    not raise.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import keyring
import keyring.backends.fail
import pytest
import respx

pytestmark = pytest.mark.real_http  # marker choice: cross-listed to ensure
# the conftest autouse fixture does NOT reset the keyring to null.


GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


@pytest.mark.real_http
@pytest.mark.asyncio
async def test_f19_t36_real_keyring_fail_backend_triggers_rule_fallback(
    tmp_path: Path,
) -> None:
    """feature_19 real test: install keyring.backends.fail as the library
    backend (without monkey-patching), and verify ClassifierService falls back
    to RuleBackend (never raising) when LlmBackend cannot obtain the api_key.
    """
    from harness.dispatch.classifier.models import ClassifierConfig, ClassifyRequest
    from harness.dispatch.classifier.service import ClassifierService

    # Install the genuinely-broken backend (shipped by the keyring package).
    keyring.set_keyring(keyring.backends.fail.Keyring())
    # Sanity: prove it really is the fail backend (kills accidental real-cred leaks).
    assert isinstance(keyring.get_keyring(), keyring.backends.fail.Keyring)

    cfg = ClassifierConfig(
        enabled=True,
        provider="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4-plus",
    )
    service = ClassifierService(
        config=cfg,
        prompt_store_path=tmp_path / "prompt.json",
    )
    req = ClassifyRequest(
        exit_code=0,
        stderr_tail="",
        stdout_tail="",
        has_termination_banner=False,
    )

    # Gate the HTTP call too; if the service tries to reach GLM with no key,
    # it gets a hard ConnectError via respx (secondary safety net).
    # [TEST-FIX] respx default assert_all_called=True rejects un-called routes,
    # but here the keyring failure is expected to short-circuit BEFORE HTTP.
    with respx.mock(assert_all_called=False) as mock:
        mock.post(GLM_URL).mock(side_effect=httpx.ConnectError("should not reach here"))
        verdict = await service.classify(req)

    # Contract: classify never raises, keyring failure → rule fallback.
    assert (
        verdict.backend == "rule"
    ), f"keyring.fail must cause fallback to rule backend, got backend={verdict.backend!r}"
