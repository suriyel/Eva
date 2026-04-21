"""KeyringGateway — IAPI-014 Provider facade over the ``keyring`` library.

Design §6.1.6 + §6.2.1 · Implementation:
    * ``set/get/delete_secret`` validate ``service`` / ``user`` / ``value`` via
      pydantic ``TypeAdapter`` (raises ``ValidationError`` for empty strings,
      length > 256, missing ``harness-`` prefix).
    * ``detect_backend()`` inspects ``keyring.get_keyring()`` — Linux's
      ``PlaintextKeyring`` triggers ``degraded=True`` + Chinese warning.
    * Errors from the underlying backend bubble up as ``KeyringServiceError``
      (set/delete only — get returns ``None`` on missing entries, per §IC).
"""

from __future__ import annotations

import datetime
from typing import Annotated

import keyring
from pydantic import BaseModel, ConfigDict, StringConstraints, TypeAdapter


class KeyringServiceError(Exception):
    """Raised when the backend fails irrecoverably (set/delete)."""


class BackendInfo(BaseModel):
    """Result of ``KeyringGateway.detect_backend()``."""

    model_config = ConfigDict(extra="forbid")

    name: str
    degraded: bool
    warning: str | None = None


# ---------------------------------------------------------------------------
# Validated string types (service/user/value).
# ---------------------------------------------------------------------------
_HarnessServiceStr = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256, pattern=r"^harness-.*$"),
]
_UserStr = Annotated[str, StringConstraints(min_length=1, max_length=256)]
_ValueStr = Annotated[str, StringConstraints(min_length=1, max_length=32768)]

_service_adapter: TypeAdapter[str] = TypeAdapter(_HarnessServiceStr)
_user_adapter: TypeAdapter[str] = TypeAdapter(_UserStr)
_value_adapter: TypeAdapter[str] = TypeAdapter(_ValueStr)


_PLAINTEXT_KEYRING_NAMES = {
    # Both full name and class name variants (different keyrings.alt versions).
    "keyrings.alt.file.PlaintextKeyring",
    "PlaintextKeyring",
}

_DEGRADED_WARNING_ZH = "未检测到 Secret Service，凭证以明文存储，建议安装 gnome-keyring"


class KeyringGateway:
    """Provider facade around the ``keyring`` library."""

    def __init__(self) -> None:
        # degradation_log: list of (timestamp ISO, backend name) — written once
        # per set_secret when the backend is a Plaintext fallback.
        self.degradation_log: list[tuple[str, str]] = []

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _validate_service_prefix(service: str) -> str:
        return _service_adapter.validate_python(service)

    @staticmethod
    def _validate_user(user: str) -> str:
        return _user_adapter.validate_python(user)

    @staticmethod
    def _validate_value(value: str) -> str:
        return _value_adapter.validate_python(value)

    # ------------------------------------------------------------ degraded?
    @staticmethod
    def _is_plaintext_backend(backend: object) -> bool:
        cls = backend.__class__
        full = f"{cls.__module__}.{cls.__qualname__}"
        if full in _PLAINTEXT_KEYRING_NAMES:
            return True
        if cls.__name__ in _PLAINTEXT_KEYRING_NAMES:
            return True
        # Also match by MRO name — handles subclasses.
        for base in cls.__mro__:
            if base.__name__ == "PlaintextKeyring":
                return True
        return False

    @property
    def degraded(self) -> bool:
        """Current backend is a plaintext fallback (Linux no Secret Service)."""
        return self._is_plaintext_backend(keyring.get_keyring())

    # ------------------------------------------------------------ get/set/del
    def get_secret(self, service: str, user: str) -> str | None:
        self._validate_service_prefix(service)
        self._validate_user(user)
        try:
            return keyring.get_password(service, user)
        except Exception as exc:  # pragma: no cover — backend-specific
            raise KeyringServiceError(f"keyring.get_password failed: {exc}") from exc

    def set_secret(self, service: str, user: str, value: str) -> None:
        self._validate_service_prefix(service)
        self._validate_user(user)
        self._validate_value(value)
        try:
            keyring.set_password(service, user, value)
        except Exception as exc:
            raise KeyringServiceError(f"keyring.set_password failed: {exc}") from exc
        # Record a single degradation entry when backend is plaintext fallback.
        backend = keyring.get_keyring()
        if self._is_plaintext_backend(backend):
            self.degradation_log.append(
                (
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    f"{backend.__class__.__module__}.{backend.__class__.__qualname__}",
                )
            )

    def delete_secret(self, service: str, user: str) -> None:
        self._validate_service_prefix(service)
        self._validate_user(user)
        try:
            keyring.delete_password(service, user)
        except keyring.errors.PasswordDeleteError:
            # Entry does not exist → idempotent no-op per §IC postcondition.
            return
        except Exception as exc:
            raise KeyringServiceError(f"keyring.delete_password failed: {exc}") from exc

    # ------------------------------------------------------------ detect_backend
    def detect_backend(self) -> BackendInfo:
        backend = keyring.get_keyring()
        cls = backend.__class__
        name = f"{cls.__module__}.{cls.__qualname__}"
        if self._is_plaintext_backend(backend):
            return BackendInfo(
                name=name,
                degraded=True,
                warning=_DEGRADED_WARNING_ZH,
            )
        return BackendInfo(name=name, degraded=False, warning=None)
