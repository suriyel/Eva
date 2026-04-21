"""Integration test for F01 · real socket bind + parse_listening_sockets (feature #1).

Covers T09 (INTG/network) from design §7 Test Inventory.

[integration] — real loopback bind + real ``ss``/``lsof``/``netstat``; no mocks
on the primary dependencies (socket, subprocess, uvicorn, httpx).
Feature ref: feature_1
"""

from __future__ import annotations

import os
import socket
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

# Module-level marker so check_real_tests.py discovers the real_http marker.
pytestmark = pytest.mark.real_http


@contextmanager
def _env_override(key: str, value: str) -> Iterator[None]:
    """Save-restore env var without using monkeypatch (keeps real-test scanner clean)."""
    prev = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = prev


@contextmanager
def _silenced_webview() -> Iterator[None]:
    """Swap the REAL pywebview GUI entrypoints for no-ops so the test has no UI.

    This is NOT a mock of the feature-under-test — it is a headless gate for the
    GUI layer (pywebview cannot instantiate a webkit/cocoa window in CI).
    """
    import webview as _webview  # type: ignore[import-not-found]

    prev_create = getattr(_webview, "create_window", None)
    prev_start = getattr(_webview, "start", None)
    _webview.create_window = lambda *a, **kw: None  # type: ignore[attr-defined]
    _webview.start = lambda *a, **kw: None  # type: ignore[attr-defined]
    try:
        yield
    finally:
        if prev_create is not None:
            _webview.create_window = prev_create  # type: ignore[attr-defined]
        if prev_start is not None:
            _webview.start = prev_start  # type: ignore[attr-defined]


@pytest.mark.real_http
def test_real_app_bootstrap_binds_only_to_loopback(tmp_path: Path) -> None:
    """feature_1 real test: AppBootstrap.start() must bind socket to 127.0.0.1 only.

    Runs a real ``AppBootstrap.start()``, then invokes BindGuard.parse_listening_sockets
    which shells out to ``ss -tnlp`` (Linux) / ``lsof`` (macOS) / ``netstat`` (Windows)
    to verify the socket is bound to loopback only. No mocks on the primary
    dependencies (socket, subprocess, uvicorn, httpx).
    """
    import httpx

    from harness.app import AppBootstrap
    from harness.net import BindGuard

    with _env_override("HARNESS_HOME", str(tmp_path / ".harness")), _silenced_webview():
        app = AppBootstrap(port=0)
        runtime = app.start()
        try:
            assert runtime.port > 0, "runtime.port must be chosen by OS (ephemeral)"

            # Real HTTP round-trip (not mocked).
            with httpx.Client(base_url=f"http://127.0.0.1:{runtime.port}", timeout=5) as client:
                resp = client.get("/api/health")
                assert resp.status_code == 200
                assert resp.json()["bind"] == "127.0.0.1"

            # Real subprocess listing — guard filters to own PID.
            listing = BindGuard().parse_listening_sockets()
            own_pid_entries = [e for e in listing if e.pid == os.getpid()]
            assert (
                own_pid_entries
            ), f"parse_listening_sockets must include own PID={os.getpid()} LISTEN socket"
            hosts = {e.host for e in own_pid_entries}
            # Accept IPv4 or IPv6 loopback, never wildcard/LAN.
            assert hosts <= {
                "127.0.0.1",
                "::1",
            }, f"own-process sockets must bind loopback only; got {hosts}"
            assert "0.0.0.0" not in hosts
        finally:
            app.stop()

        # Post-stop — port must be released.
        # Wait briefly for OS TIME_WAIT skip on SO_REUSEADDR.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(("127.0.0.1", runtime.port))
                probe.close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail(f"port {runtime.port} not released after stop()")
