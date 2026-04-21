"""Pytest-wide fixtures for Harness F01 test suite.

Keyring backend is forced to ``keyring.backends.null.Keyring`` for unit
tests that import ``keyring``; integration tests override via marker.
"""

from __future__ import annotations

import os
from pathlib import Path

import keyring
import keyring.backends.null
import pytest


# --- Env isolation: strip any proxy env the dev shell may inject -----------
# Loopback HTTP calls made by the tests (``httpx.Client(base_url=127.0.0.1:...)``)
# must not route through a developer-local SOCKS/HTTP proxy. Some dev machines
# export ``ALL_PROXY=socks://...`` which httpx rejects at Client construction
# time. Scrubbing here keeps the tests deterministic across environments.
for _var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "FTP_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "ftp_proxy",
    "all_proxy",
):
    os.environ.pop(_var, None)


@pytest.fixture(autouse=True)
def _null_keyring_for_unit_tests(request: pytest.FixtureRequest) -> None:
    """Force keyring null backend unless the test opts into real fs/cli/http."""
    markers = {m.name for m in request.node.iter_markers()}
    if markers & {"real_cli", "real_fs", "real_http"}:
        # Real-test: leave the real configured backend in place.
        return
    keyring.set_keyring(keyring.backends.null.Keyring())


@pytest.fixture
def tmp_harness_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated HARNESS_HOME under tmp_path."""
    home = tmp_path / ".harness"
    monkeypatch.setenv("HARNESS_HOME", str(home))
    # Ensure parent dir writable; do NOT pre-create .harness — let FirstRunWizard do it.
    return home


def pytest_configure(config: pytest.Config) -> None:
    # Register custom markers used by integration tests.
    for mark in ("real_cli", "real_fs", "real_http"):
        config.addinivalue_line("markers", f"{mark}: real integration test ({mark})")
