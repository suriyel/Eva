"""Unit tests for F01 · ConfigStore + HarnessConfig (feature #1).

Covers T02, T03, T15, T16 from design §7 Test Inventory and the
ConfigStore Boundary Conditions table in §8.

[unit] — uses in-memory config values + tmp_path for file ops
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# T02 — FUNC/happy — FR-050 AC2 — config.json never contains plaintext secrets
# ---------------------------------------------------------------------------
def test_config_store_save_never_writes_plaintext_api_key(tmp_path: Path) -> None:
    """ConfigStore.save must write api_key_ref={service,user} — never a raw key."""
    from harness.config import ConfigStore, HarnessConfig
    from harness.config.schema import ApiKeyRef

    cfg_path = tmp_path / "config.json"
    store = ConfigStore(cfg_path)
    cfg = HarnessConfig(
        provider_refs={"glm": ApiKeyRef(service="harness-classifier-glm", user="default")}
    )

    store.save(cfg)

    payload = cfg_path.read_bytes()
    data = json.loads(payload)
    # Positive: the reference structure is present.
    assert data["provider_refs"]["glm"] == {
        "service": "harness-classifier-glm",
        "user": "default",
    }
    # Negative: no plaintext-looking key markers anywhere in the payload.
    text = payload.decode("utf-8")
    assert "sk-" not in text
    assert "sk-ant-" not in text
    for forbidden in ("value", "secret", "api_key", "apiKey"):
        assert (
            forbidden not in data["provider_refs"]["glm"]
        ), f"provider_refs.glm unexpectedly contains {forbidden!r}"


# ---------------------------------------------------------------------------
# T03 — FUNC/error — ConfigStore.save raises SecretLeakError on plaintext
# ---------------------------------------------------------------------------
def test_config_store_save_raises_on_plaintext_api_key_in_payload(tmp_path: Path) -> None:
    """A payload containing an ``sk-ant-...`` blob must abort with SecretLeakError."""
    from harness.config import ConfigStore, SecretLeakError
    from harness.config.schema import HarnessConfig

    cfg_path = tmp_path / "config.json"
    store = ConfigStore(cfg_path)

    # Build a config and monkey-insert a plaintext string through model_dump mutation
    # to simulate a caller bypassing the pydantic schema.
    class Leaky(HarnessConfig):
        model_config = {"extra": "allow"}

    leaky = Leaky()
    # Inject a realistic-looking secret via extra field.
    object.__setattr__(
        leaky,
        "__pydantic_extra__",
        {
            "leaked": "sk-ant-1234567890abcdef1234567890abcdef",
        },
    )

    with pytest.raises(SecretLeakError):
        store.save(leaky)

    # Atomic-rename contract: no partial file may be visible.
    assert not cfg_path.exists(), "config.json must not be written on SecretLeakError"


# ---------------------------------------------------------------------------
# T15 — SEC/config-extra-fields — pydantic extra="forbid"
# ---------------------------------------------------------------------------
def test_config_store_load_rejects_unknown_api_key_field(tmp_path: Path) -> None:
    """Legacy ``api_key`` field must be rejected by pydantic (NFR-008 defence-in-depth)."""
    from harness.config import ConfigStore, ConfigCorruptError

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"api_key": "sk-ant-xyz", "schema_version": 1}),
        encoding="utf-8",
    )
    store = ConfigStore(cfg_path)

    with pytest.raises(ConfigCorruptError):
        store.load()


# ---------------------------------------------------------------------------
# T16 — BNDRY/config-corrupt — zero-byte config.json
# ---------------------------------------------------------------------------
def test_config_store_load_raises_on_zero_byte_file(tmp_path: Path) -> None:
    from harness.config import ConfigStore, ConfigCorruptError

    cfg_path = tmp_path / "config.json"
    cfg_path.write_bytes(b"")
    store = ConfigStore(cfg_path)

    with pytest.raises(ConfigCorruptError) as excinfo:
        store.load()
    # Error must include diagnostic detail (not just empty).
    assert str(excinfo.value), "ConfigCorruptError must carry a diagnostic message"


# ---------------------------------------------------------------------------
# Additional ConfigStore.default_path boundary coverage from §8
# ---------------------------------------------------------------------------
def test_default_path_uses_harness_home_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from harness.config import ConfigStore

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / "custom"))
    p = ConfigStore.default_path()
    assert p == tmp_path / "custom" / "config.json"


def test_default_path_falls_back_to_home_harness_when_env_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harness.config import ConfigStore

    monkeypatch.setenv("HARNESS_HOME", "")
    monkeypatch.setenv("HOME", "/fake/home-dir-xyz")
    p = ConfigStore.default_path()
    assert p == Path("/fake/home-dir-xyz") / ".harness" / "config.json"


def test_load_returns_default_when_file_missing(tmp_path: Path) -> None:
    from harness.config import ConfigStore
    from harness.config.schema import HarnessConfig

    store = ConfigStore(tmp_path / "does_not_exist.json")
    cfg = store.load()
    # Exact equality with a fresh default — not merely isinstance.
    assert cfg == HarnessConfig.default()


def test_save_rejects_host_ip_smuggled_via_string_field(tmp_path: Path) -> None:
    """Even a base64-ish blob (≥32 chars) must trip the leak detector."""
    from harness.config import ConfigStore, SecretLeakError
    from harness.config.schema import HarnessConfig

    cfg_path = tmp_path / "config.json"
    store = ConfigStore(cfg_path)

    class Leaky(HarnessConfig):
        model_config = {"extra": "allow"}

    leaky = Leaky()
    object.__setattr__(
        leaky,
        "__pydantic_extra__",
        {
            # 40 chars, valid base64 alphabet — should fire leak detector.
            "blob": "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU=",
        },
    )
    with pytest.raises(SecretLeakError):
        store.save(leaky)


# SEC: injection coverage lives in test_f01_first_run.py (path-traversal) and
# test_f01_keyring_gateway.py (prefix validation). No additional SEC cases here.
