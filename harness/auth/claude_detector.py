"""ClaudeAuthDetector — IFR-001 read-only detector for ``claude auth login``.

Design §6.1.1 + §Implementation Summary item 5:
    * Only invokes ``claude --version`` and ``claude auth status`` via
      ``subprocess.run`` (no shell=True). Never writes ``~/.claude/``.
    * When ``shutil.which('claude')`` returns ``None`` → returns
      ``ClaudeAuthStatus(cli_present=False, ..., hint="未检测到 Claude Code CLI")``.
    * When ``auth status`` exits non-zero → hint is simplified-Chinese
      and includes the canonical remedy ``claude auth login`` (NFR-010).
    * ``OSError`` from subprocess is absorbed → cli_present=False.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ClaudeAuthStatus(BaseModel):
    """Result schema for ``ClaudeAuthDetector.detect()``.

    Contract: see Design §Interface Contract row ``ClaudeAuthDetector.detect``.
    """

    model_config = ConfigDict(extra="forbid")

    cli_present: bool
    authenticated: bool
    hint: str | None = None
    source: Literal["claude-cli", "skipped"] = "skipped"


_HINT_CLI_MISSING_ZH = "未检测到 Claude Code CLI"
_HINT_NOT_AUTHENTICATED_ZH = "请运行: claude auth login"


class ClaudeAuthDetector:
    """Read-only detector. Never writes to ``~/.claude/`` (NFR-009 / CON-007)."""

    def detect(self) -> ClaudeAuthStatus:
        path = shutil.which("claude")
        if path is None:
            return ClaudeAuthStatus(
                cli_present=False,
                authenticated=False,
                hint=_HINT_CLI_MISSING_ZH,
                source="skipped",
            )

        # ``claude --version`` — probes CLI presence & returns quickly.
        try:
            ver = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except OSError:
            return ClaudeAuthStatus(
                cli_present=False,
                authenticated=False,
                hint=_HINT_CLI_MISSING_ZH,
                source="skipped",
            )

        if ver.returncode != 0:
            return ClaudeAuthStatus(
                cli_present=False,
                authenticated=False,
                hint=_HINT_CLI_MISSING_ZH,
                source="skipped",
            )

        # ``claude auth status`` — zero exit → authenticated.
        try:
            st = subprocess.run(
                ["claude", "auth", "status"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except OSError:
            return ClaudeAuthStatus(
                cli_present=True,
                authenticated=False,
                hint=_HINT_NOT_AUTHENTICATED_ZH,
                source="claude-cli",
            )

        if st.returncode == 0:
            return ClaudeAuthStatus(
                cli_present=True,
                authenticated=True,
                hint=None,
                source="claude-cli",
            )
        return ClaudeAuthStatus(
            cli_present=True,
            authenticated=False,
            hint=_HINT_NOT_AUTHENTICATED_ZH,
            source="claude-cli",
        )
