"""Harness app package — process entry, first-run wizard, bootstrap orchestrator.

Exports:
    AppBootstrap    — lifecycle: __init__ → start() → stop()
    AppRuntime      — dataclass (port, uvicorn_server, webview_window)
    FirstRunWizard  — is_first_run() / bootstrap() → FirstRunResult
    FirstRunResult  — pydantic model (home_path, created_files, welcome_message)
"""

from __future__ import annotations

from .bootstrap import (
    AppBootstrap,
    AppRuntime,
    WebviewBackendUnavailableError,
)
from .first_run import (
    FirstRunResult,
    FirstRunWizard,
    HarnessHomeWriteError,
)

__all__ = [
    "AppBootstrap",
    "AppRuntime",
    "FirstRunResult",
    "FirstRunWizard",
    "HarnessHomeWriteError",
    "WebviewBackendUnavailableError",
]
