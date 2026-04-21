"""Unit tests for F01 · KeyringGateway (feature #1, IFR-006 + IAPI-014).

Covers T11, T12, T13, T14 from design §7 Test Inventory and the
``KeyringGateway.service/user/value`` boundary rows in §8.

[unit] — uses ``keyring.backends.null.Keyring`` via conftest + monkeypatch.
"""

from __future__ import annotations

import keyring
import pytest


# ---------------------------------------------------------------------------
# T12 — SEC/keyring-prefix — service must start with "harness-"
# ---------------------------------------------------------------------------
def test_set_secret_rejects_service_without_harness_prefix() -> None:
    from harness.auth import KeyringGateway
    from pydantic import ValidationError

    gw = KeyringGateway()
    with pytest.raises(ValidationError):
        gw.set_secret("not-harness-prefix", "user", "value")


def test_get_secret_rejects_service_without_harness_prefix() -> None:
    from harness.auth import KeyringGateway
    from pydantic import ValidationError

    gw = KeyringGateway()
    with pytest.raises(ValidationError):
        gw.get_secret("openai", "default")


def test_delete_secret_rejects_service_without_harness_prefix() -> None:
    from harness.auth import KeyringGateway
    from pydantic import ValidationError

    gw = KeyringGateway()
    with pytest.raises(ValidationError):
        gw.delete_secret("bad-prefix", "user")


# ---------------------------------------------------------------------------
# T13 — BNDRY/keyring-empty — empty strings rejected, backend NOT called
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "service,user,value",
    [
        ("", "user", "v"),
        ("harness-x", "", "v"),
        ("harness-x", "user", ""),
    ],
    ids=["service-empty", "user-empty", "value-empty"],
)
def test_set_secret_rejects_empty_string(
    service: str, user: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.auth import KeyringGateway
    from pydantic import ValidationError

    calls: list[tuple[str, str, str]] = []

    def _track(s: str, u: str, v: str) -> None:
        calls.append((s, u, v))

    monkeypatch.setattr(keyring, "set_password", _track)

    gw = KeyringGateway()
    with pytest.raises(ValidationError):
        gw.set_secret(service, user, value)
    # Critical: backend must NOT be invoked with empty string.
    assert calls == [], f"keyring.set_password should not be called; got {calls!r}"


# ---------------------------------------------------------------------------
# T14 — BNDRY/keyring-length — 256 passes, 257 fails (off-by-one guard)
# ---------------------------------------------------------------------------
def test_service_length_exactly_256_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.auth import KeyringGateway

    captured: dict[str, str] = {}

    def _set(s: str, u: str, v: str) -> None:
        captured["service"] = s
        captured["user"] = u
        captured["value"] = v

    monkeypatch.setattr(keyring, "set_password", _set)

    gw = KeyringGateway()
    service = "harness-" + "a" * (256 - len("harness-"))
    assert len(service) == 256
    gw.set_secret(service, "u", "v")
    assert captured["service"] == service


def test_service_length_257_rejected() -> None:
    from harness.auth import KeyringGateway
    from pydantic import ValidationError

    gw = KeyringGateway()
    service = "harness-" + "a" * (257 - len("harness-"))
    assert len(service) == 257
    with pytest.raises(ValidationError):
        gw.set_secret(service, "u", "v")


def test_user_length_257_rejected() -> None:
    from harness.auth import KeyringGateway
    from pydantic import ValidationError

    gw = KeyringGateway()
    with pytest.raises(ValidationError):
        gw.set_secret("harness-x", "a" * 257, "v")


# ---------------------------------------------------------------------------
# T11 — INTG/keyring-degradation — Linux PlaintextKeyring → degraded=True
# ---------------------------------------------------------------------------
def test_detect_backend_reports_degraded_for_plaintext_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When keyrings.alt.file.PlaintextKeyring is active, detect_backend must warn."""
    import keyrings.alt.file  # type: ignore[import-not-found]

    from harness.auth import KeyringGateway

    plain = keyrings.alt.file.PlaintextKeyring()
    monkeypatch.setattr(keyring, "get_keyring", lambda: plain)

    gw = KeyringGateway()
    info = gw.detect_backend()

    assert info.degraded is True
    assert info.warning is not None
    # NFR-010: warning must be in 简体中文
    import re

    assert re.search(
        r"[一-鿿]", info.warning
    ), f"degraded warning should contain CJK: {info.warning!r}"
    # And specifically call out Secret Service (IFR-006 contract).
    assert "Secret Service" in info.warning


def test_detect_backend_healthy_when_secret_service_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harness.auth import KeyringGateway

    # Simulate a healthy, non-degraded backend: use null keyring as surrogate for
    # "a real platform backend" — detect_backend must treat it as non-degraded
    # because it is NOT PlaintextKeyring.
    null_backend = keyring.backends.null.Keyring()
    monkeypatch.setattr(keyring, "get_keyring", lambda: null_backend)

    gw = KeyringGateway()
    info = gw.detect_backend()

    assert info.degraded is False


# ---------------------------------------------------------------------------
# Happy-path round-trip via the null backend (sanity — IAPI-014 contract)
# ---------------------------------------------------------------------------
def test_set_then_get_round_trip_via_inmemory_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harness.auth import KeyringGateway

    # Provide an in-memory dict-backed backend (not a real one), to exercise
    # that KeyringGateway truly round-trips via keyring.get/set_password rather
    # than caching internally.
    store: dict[tuple[str, str], str] = {}

    def _set(s: str, u: str, v: str) -> None:
        store[(s, u)] = v

    def _get(s: str, u: str) -> str | None:
        return store.get((s, u))

    def _delete(s: str, u: str) -> None:
        store.pop((s, u), None)

    monkeypatch.setattr(keyring, "set_password", _set)
    monkeypatch.setattr(keyring, "get_password", _get)
    monkeypatch.setattr(keyring, "delete_password", _delete)

    gw = KeyringGateway()
    gw.set_secret("harness-classifier-glm", "default", "token-abc")
    assert gw.get_secret("harness-classifier-glm", "default") == "token-abc"

    gw.delete_secret("harness-classifier-glm", "default")
    assert gw.get_secret("harness-classifier-glm", "default") is None
