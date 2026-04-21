"""Harness net package — loopback bind guard + listening-socket parser.

Exports:
    BindGuard             — assert_loopback_only + parse_listening_sockets
    ListeningSocket       — dataclass (host, port, pid)
    BindRejectedError     — bind host is not 127.0.0.1 / ::1
    BindUnavailableError  — requested port is busy
"""

from __future__ import annotations

from .bind_guard import (
    BindGuard,
    BindRejectedError,
    BindUnavailableError,
    ListeningSocket,
)

__all__ = [
    "BindGuard",
    "BindRejectedError",
    "BindUnavailableError",
    "ListeningSocket",
]
