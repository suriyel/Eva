"""Integration test for F01 · real keyring backend round-trip (feature #1).

Covers T10 (INTG/keyring) from design §7 Test Inventory.

[integration] — uses ``keyrings.alt.file.EncryptedKeyring``-style file-backed
storage with an explicit filesystem path, bypassing platform Keychain / Secret
Service while still exercising the REAL keyring library end-to-end (no monkey-
patch on keyring.set/get/delete_password).

Feature ref: feature_1
"""

from __future__ import annotations

from pathlib import Path

import keyring
import pytest

pytestmark = pytest.mark.real_fs


@pytest.mark.real_fs
def test_real_keyring_round_trip_via_file_backend(tmp_path: Path) -> None:
    """feature_1 real test: set/get/delete via a real file-backed keyring.

    We configure a PlaintextKeyring (keyrings.alt.file) backed by a tmp file
    and do NOT patch keyring.set_password / keyring.get_password. The
    KeyringGateway must truly persist to disk and read back.
    """
    import keyrings.alt.file  # type: ignore[import-not-found]

    from harness.auth import KeyringGateway

    backend = keyrings.alt.file.PlaintextKeyring()
    # Redirect the backend's file path into tmp_path (real fs, not platform path).
    backend.file_path = str(tmp_path / "keyring.cfg")  # type: ignore[attr-defined]
    keyring.set_keyring(backend)

    gw = KeyringGateway()
    gw.set_secret("harness-classifier-glm", "default", "real-token-xyz")

    # Value must round-trip through the real backend.
    assert gw.get_secret("harness-classifier-glm", "default") == "real-token-xyz"

    # File must exist on disk — proves no mock was intercepting.
    kr_file = Path(backend.file_path)  # type: ignore[attr-defined]
    assert kr_file.exists(), "keyring file backend must have persisted a real file"
    assert kr_file.stat().st_size > 0, "keyring file must contain data"

    gw.delete_secret("harness-classifier-glm", "default")
    assert gw.get_secret("harness-classifier-glm", "default") is None

    # detect_backend reports a non-empty backend name (IFR-006 contract).
    info = gw.detect_backend()
    assert info.name, "BackendInfo.name must be non-empty"
    # PlaintextKeyring → degraded True with Chinese warning (ATS Err-H).
    assert info.degraded is True
    assert info.warning and "Secret Service" in info.warning
