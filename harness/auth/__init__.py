"""Harness auth package — keyring facade + Claude CLI detector.

Exports:
    KeyringGateway      — IAPI-014 Provider (get/set/delete_secret + detect_backend)
    BackendInfo         — BackendInfo { name, degraded, warning }
    KeyringServiceError — raised when keyring backend fails irrecoverably
    ClaudeAuthDetector  — IFR-001 detector (read-only ``claude auth status``)
    ClaudeAuthStatus    — { cli_present, authenticated, hint, source }
"""

from __future__ import annotations

from .claude_detector import ClaudeAuthDetector, ClaudeAuthStatus
from .keyring_gateway import BackendInfo, KeyringGateway, KeyringServiceError

__all__ = [
    "BackendInfo",
    "ClaudeAuthDetector",
    "ClaudeAuthStatus",
    "KeyringGateway",
    "KeyringServiceError",
]
