"""F19 · Classifier errors (feature design §IC Raises column)."""

from __future__ import annotations


class ClassifierHttpError(Exception):
    """Raised by LlmBackend on httpx timeout / connection / 4xx/5xx."""

    def __init__(self, message: str = "", *, cause: str | None = None) -> None:
        super().__init__(message or (cause or ""))
        self.cause = cause or ""


class ClassifierProtocolError(Exception):
    """Raised by LlmBackend when JSON invalid / schema mismatch / verdict out-of-enum."""

    def __init__(self, message: str = "", *, cause: str | None = None) -> None:
        super().__init__(message or (cause or ""))
        self.cause = cause or ""


class SsrfBlockedError(Exception):
    """Raised by ProviderPresets.validate_base_url on whitelist / private-range violation."""


class ProviderPresetError(Exception):
    """Raised by ProviderPresets.resolve when provider is unknown."""


class PromptStoreError(Exception):
    """Raised by PromptStore on I/O failure or path-traversal attempts."""


class PromptValidationError(Exception):
    """Raised by PromptStore.put when content is empty or > 32 KB."""


class PromptStoreCorruptError(Exception):
    """Raised by PromptStore.get when on-disk JSON is invalid."""


__all__ = [
    "ClassifierHttpError",
    "ClassifierProtocolError",
    "SsrfBlockedError",
    "ProviderPresetError",
    "PromptStoreError",
    "PromptValidationError",
    "PromptStoreCorruptError",
]
