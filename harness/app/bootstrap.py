"""AppBootstrap — process lifecycle for Harness desktop app (F01).

Design §6 · Implementation Summary item 1-3:
    * Constructor validates ``host`` (must be ``127.0.0.1``; fail-fast) and
      ``port`` (0..65535). Raises ``BindRejectedError`` / ``ValueError``.
    * ``start()`` executes:
        1. ``ConfigStore.default_path()`` → Path (already resolved; used only if
           the caller didn't override ``harness_home``).
        2. ``FirstRunWizard.is_first_run()`` → optional ``bootstrap()`` call.
        3. Dry-run ``socket.bind(("127.0.0.1", port))`` → ``BindGuard.assert_loopback_only``.
        4. Boot ``uvicorn.Server`` in a background thread bound to the chosen port.
        5. Cache a ``ClaudeAuthDetector.detect()`` result on the FastAPI app.
        6. Call ``webview.create_window`` + ``webview.start`` (daemon thread).
    * ``stop()`` flips ``uvicorn.Server.should_exit`` and joins.
    * Failure modes map 1:1 to §IC Raises column.
"""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn

from ..auth import ClaudeAuthDetector
from ..config import ConfigStore
from ..net import BindGuard, BindRejectedError, BindUnavailableError
from .first_run import FirstRunWizard


class WebviewBackendUnavailableError(Exception):
    """Raised when pywebview GUI backend cannot be instantiated (NFR-012)."""


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})


@dataclass
class AppRuntime:
    """Live handle returned by ``AppBootstrap.start()``."""

    port: int
    uvicorn_server: Any = None  # uvicorn.Server — typed Any to avoid leak
    webview_window: Any = None
    server_thread: threading.Thread | None = None
    webview_thread: threading.Thread | None = None
    claude_auth_status: Any = None


class AppBootstrap:
    """Lifecycle orchestrator for Harness."""

    def __init__(
        self,
        *,
        harness_home: Path | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        # --- port validation -------------------------------------------------
        if not isinstance(port, int) or isinstance(port, bool):
            raise ValueError(f"port must be int; got {type(port).__name__}")
        if port < 0 or port > 65535:
            raise ValueError(f"port out of range [0..65535]: {port}")

        # --- host validation (fail-fast on non-loopback) --------------------
        if host not in _LOOPBACK_HOSTS:
            raise BindRejectedError(host, f"AppBootstrap host must be loopback; got {host!r}")

        self._host = host
        self._port = port
        self._harness_home = harness_home
        self._runtime: AppRuntime | None = None

    # ---------------------------------------------------------------- props
    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    # ---------------------------------------------------------------- start
    def start(self) -> AppRuntime:
        if self._runtime is not None:
            raise RuntimeError("AppBootstrap already started")

        # 1) Determine config path.
        if self._harness_home is not None:
            cfg_path = Path(self._harness_home) / "config.json"
        else:
            cfg_path = ConfigStore.default_path()
        store = ConfigStore(cfg_path)

        # 2) First-run provisioning.
        wizard = FirstRunWizard(store)
        if wizard.is_first_run():
            wizard.bootstrap()

        # 3) Dry-run bind to surface non-loopback / port-in-use early.
        chosen_port = self._dry_run_bind(self._host, self._port)

        # 4) Boot uvicorn in a background thread on chosen_port.
        #    We defer import of harness.api until here to avoid circular deps.
        from ..api import app as fastapi_app

        server_config = uvicorn.Config(
            app=fastapi_app,
            host=self._host,
            port=chosen_port,
            log_level="warning",
            access_log=False,
            loop="asyncio",
            lifespan="on",
        )
        server = uvicorn.Server(server_config)

        # Attach singletons to app.state for /api/health consumption.
        fastapi_app.state.bind_host = self._host
        fastapi_app.state.bind_port = chosen_port

        thread = threading.Thread(
            target=server.run,
            name="harness-uvicorn",
            daemon=True,
        )
        thread.start()

        # Wait up to ~5s for the server to become ready.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if getattr(server, "started", False):
                break
            time.sleep(0.05)
        else:
            # Timed out → try to shut down and raise.
            server.should_exit = True
            thread.join(timeout=2.0)
            raise BindUnavailableError(
                f"uvicorn did not start listening on 127.0.0.1:{chosen_port} in time"
            )

        # 5) Cache claude auth status for /api/health.
        try:
            claude_auth_status = ClaudeAuthDetector().detect()
        except Exception:  # pragma: no cover — defensive
            claude_auth_status = None
        fastapi_app.state.claude_auth_status = claude_auth_status

        # 6) Webview — run in a daemon thread; failure raises WebviewBackendUnavailableError.
        webview_window = None
        webview_thread: threading.Thread | None = None
        try:
            import webview

            try:
                webview_window = webview.create_window(
                    "Harness",
                    f"http://{self._host}:{chosen_port}",
                )
            except Exception as exc:
                # Tear down uvicorn before bubbling the error up.
                server.should_exit = True
                thread.join(timeout=3.0)
                raise WebviewBackendUnavailableError(
                    f"pywebview create_window failed: {exc}"
                ) from exc

            def _webview_runner() -> None:
                try:
                    webview.start()
                except Exception:  # pragma: no cover — backend-specific
                    pass

            webview_thread = threading.Thread(
                target=_webview_runner,
                name="harness-webview",
                daemon=True,
            )
            webview_thread.start()
        except WebviewBackendUnavailableError:
            raise
        except Exception as exc:
            server.should_exit = True
            thread.join(timeout=3.0)
            raise WebviewBackendUnavailableError(f"pywebview unavailable: {exc}") from exc

        self._runtime = AppRuntime(
            port=chosen_port,
            uvicorn_server=server,
            webview_window=webview_window,
            server_thread=thread,
            webview_thread=webview_thread,
            claude_auth_status=claude_auth_status,
        )
        return self._runtime

    # ---------------------------------------------------------------- stop
    def stop(self) -> None:
        if self._runtime is None:
            raise RuntimeError("AppBootstrap.stop() called before start()")
        rt = self._runtime
        if rt.uvicorn_server is not None:
            rt.uvicorn_server.should_exit = True
        if rt.server_thread is not None:
            rt.server_thread.join(timeout=5.0)
        # webview: best-effort — destroy the window if pywebview exposes it.
        try:
            import webview

            if rt.webview_window is not None:
                try:
                    rt.webview_window.destroy()
                except Exception:  # pragma: no cover — backend-specific
                    pass
            try:
                webview.windows.clear()
            except Exception:  # pragma: no cover
                pass
        except Exception:  # pragma: no cover
            pass
        self._runtime = None

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _dry_run_bind(host: str, port: int) -> int:
        """Return the bindable port (OS-chosen when port==0).

        Raises ``BindRejectedError`` / ``BindUnavailableError`` per §IC.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError as exc:
                raise BindUnavailableError(f"cannot bind {host}:{port} ({exc})") from exc
            BindGuard().assert_loopback_only(sock)
            _, chosen = sock.getsockname()[:2]
            return int(chosen)
        finally:
            sock.close()
