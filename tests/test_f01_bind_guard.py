"""Unit tests for F01 · BindGuard (feature #1, NFR-007 + CON-006).

Covers T08 from design §7 Test Inventory and ``BindGuard.assert_loopback_only`` /
``BindGuard.parse_listening_sockets`` rows in §Interface Contract.

[unit] — real ``socket.socket`` against loopback; no external infra required.
"""

from __future__ import annotations

import socket

import pytest


# ---------------------------------------------------------------------------
# T08 — SEC/bind-runtime — a bound 0.0.0.0 socket must be rejected
# ---------------------------------------------------------------------------
def test_assert_loopback_only_rejects_wildcard_bind() -> None:
    from harness.net import BindGuard, BindRejectedError

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 0))
        guard = BindGuard()
        with pytest.raises(BindRejectedError) as excinfo:
            guard.assert_loopback_only(sock)
        # The error must carry the actual host for post-mortem.
        assert "0.0.0.0" in str(excinfo.value)
    finally:
        sock.close()


def test_assert_loopback_only_accepts_ipv4_loopback() -> None:
    from harness.net import BindGuard

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        BindGuard().assert_loopback_only(sock)  # must not raise
    finally:
        sock.close()


def test_assert_loopback_only_accepts_ipv6_loopback() -> None:
    from harness.net import BindGuard

    if not socket.has_ipv6:
        pytest.skip("IPv6 unavailable on this host")  # pragma: no cover
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        sock.bind(("::1", 0))
        BindGuard().assert_loopback_only(sock)  # must not raise
    finally:
        sock.close()


def test_assert_loopback_only_rejects_lan_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even when getsockname() returns a LAN IP, guard must reject."""
    from harness.net import BindGuard, BindRejectedError

    class _FakeSock:
        def getsockname(self) -> tuple[str, int]:
            return ("192.168.1.42", 8765)

    with pytest.raises(BindRejectedError) as excinfo:
        BindGuard().assert_loopback_only(_FakeSock())  # type: ignore[arg-type]
    assert "192.168.1.42" in str(excinfo.value)


# ---------------------------------------------------------------------------
# parse_listening_sockets must return a list and filter to own PID
# ---------------------------------------------------------------------------
def test_parse_listening_sockets_returns_list_structure() -> None:
    """Sanity — result is iterable of ListeningSocket objects with (host, port, pid)."""
    from harness.net import BindGuard, ListeningSocket

    guard = BindGuard()
    # Bind a socket to guarantee at least one loopback LISTEN for the current PID.
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    try:
        result = guard.parse_listening_sockets()
        assert isinstance(result, list), "parse_listening_sockets must return list"
        for entry in result:
            assert isinstance(entry, ListeningSocket)
            # Filter contract: only own PID.
            import os as _os

            assert (
                entry.pid == _os.getpid()
            ), f"parse_listening_sockets should filter to own PID, got {entry.pid}"
    finally:
        srv.close()
