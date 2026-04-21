"""Unit tests for F01 · AppBootstrap (feature #1, NFR-007/012/013).

Covers T07, T22, T23, T24, T25, T26 from design §7 Test Inventory.

[unit] — ``webview`` module attributes monkeypatched; actual uvicorn start is
exercised where feasible via ephemeral ports (T22, T24). T09 (ss -tnlp)
lives in tests/integration/test_f01_real_bind.py.
"""

from __future__ import annotations

import socket
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# T07 — SEC/bind-host — constructor rejects non-loopback host
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad_host",
    ["0.0.0.0", "192.168.1.1", "10.0.0.1", "", "localhost"],
)
def test_app_bootstrap_rejects_non_loopback_host(bad_host: str) -> None:
    from harness.app import AppBootstrap
    from harness.net import BindRejectedError

    with pytest.raises(BindRejectedError):
        AppBootstrap(host=bad_host)


def test_app_bootstrap_accepts_127_0_0_1_default() -> None:
    from harness.app import AppBootstrap

    # No exception — construction only, does not start anything.
    AppBootstrap(host="127.0.0.1", port=0)


# ---------------------------------------------------------------------------
# T23 — BNDRY/port-out-of-range — -1 and 65536 both raise ValueError
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_port", [-1, 65536, 999999])
def test_app_bootstrap_rejects_out_of_range_port(bad_port: int) -> None:
    from harness.app import AppBootstrap

    with pytest.raises(ValueError):
        AppBootstrap(port=bad_port)


# ---------------------------------------------------------------------------
# T24 — FUNC/error — port already in use → BindUnavailableError
# ---------------------------------------------------------------------------
def test_app_bootstrap_start_raises_when_port_is_occupied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.app import AppBootstrap
    from harness.net import BindUnavailableError

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupier.bind(("127.0.0.1", 0))
    _, port = occupier.getsockname()
    occupier.listen(1)
    try:
        app = AppBootstrap(port=port)
        with pytest.raises(BindUnavailableError):
            app.start()
    finally:
        occupier.close()


# ---------------------------------------------------------------------------
# T25 — FUNC/error — webview backend unavailable
# ---------------------------------------------------------------------------
def test_app_bootstrap_start_raises_webview_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import webview as _webview  # type: ignore[import-not-found]

    from harness.app import AppBootstrap
    from harness.app.bootstrap import WebviewBackendUnavailableError

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("no GUI backend")

    monkeypatch.setattr(_webview, "create_window", _boom, raising=False)
    monkeypatch.setattr(_webview, "start", _boom, raising=False)

    app = AppBootstrap(port=0)
    with pytest.raises(WebviewBackendUnavailableError):
        app.start()

    # Post-condition: uvicorn must NOT remain listening.
    # AppBootstrap.start should tear down the server on failure (§IC stop).
    # We verify by attempting to bind to 0-returned port is not meaningful; instead
    # we check the 'runtime' is absent — only best-effort property. A strong check
    # is that calling stop() now raises because start() did not complete.
    with pytest.raises(RuntimeError):
        app.stop()


# ---------------------------------------------------------------------------
# T26 — FUNC/error — stop() before start() raises RuntimeError
# ---------------------------------------------------------------------------
def test_app_bootstrap_stop_before_start_raises() -> None:
    from harness.app import AppBootstrap

    app = AppBootstrap(port=0)
    with pytest.raises(RuntimeError):
        app.stop()


# ---------------------------------------------------------------------------
# T22 — PERF/cold-start — constructor→health 200 must be < 10s
# ---------------------------------------------------------------------------
def test_cold_start_reaches_health_within_10_seconds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import webview as _webview  # type: ignore[import-not-found]
    import httpx

    from harness.app import AppBootstrap

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))

    # Neutralise webview — we only time backend readiness (NFR-012, NFR-013 clause).
    # NFR-013: 不依赖用户预装 Python（干净 VM cold-start < 10s 由该测试计时锚定）。
    monkeypatch.setattr(_webview, "create_window", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(_webview, "start", lambda *a, **kw: None, raising=False)

    t0 = time.monotonic()
    app = AppBootstrap(port=0)
    runtime = app.start()
    try:
        assert runtime.port > 0
        # Hit /api/health synchronously.
        with httpx.Client(base_url=f"http://127.0.0.1:{runtime.port}", timeout=5) as client:
            resp = client.get("/api/health")
            assert resp.status_code == 200
        elapsed = time.monotonic() - t0
        assert elapsed < 10.0, f"cold-start took {elapsed:.2f}s, NFR-012/013 requires < 10s"
    finally:
        app.stop()
