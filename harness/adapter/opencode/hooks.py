"""F18 · Bk-Adapter — OpenCode hooks helpers (Design §4.3.2 / §6).

Four helpers:
  - HookConfigWriter      : write hooks.json under <isolated>/.opencode/
  - HookQuestionParser    : parse a single OpenCode hook NDJSON line
  - McpDegradation        : tracks toast push for FR-017 v1 MCP degradation
  - VersionCheck          : queries `opencode --version` (mockable in tests)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_MAX_NAME_BYTES = 256
_ELLIPSIS = "…"


def _truncate_utf8(s: str, limit: int = _MAX_NAME_BYTES) -> str:
    encoded = s.encode("utf-8")
    if len(encoded) <= limit:
        return s
    return encoded[:limit].decode("utf-8", errors="ignore") + _ELLIPSIS


@dataclass
class HookEvent:
    """One parsed OpenCode hook line (Design §4 row parse_hook_line)."""

    channel: str
    payload: dict[str, Any] = field(default_factory=dict)


class HookConfigWriter:
    """Writes hooks.json registering the Question tool → harness-hil channel."""

    HOOKS_BODY = {
        "version": 1,
        "onToolCall": [
            {
                "match": {"name": "Question"},
                "action": "emit",
                "channel": "harness-hil",
            }
        ],
    }

    def write(self, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Open with mode 0o600 (POSIX). chmod re-applied by OpenCodeAdapter.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        try:
            fd = os.open(str(dest), flags, 0o600)
        except OSError:
            # Windows / restricted FS — fall back to the standard open path.
            dest.write_text(json.dumps(self.HOOKS_BODY, indent=2))
            return
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                json.dump(self.HOOKS_BODY, fp, indent=2)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise


class HookQuestionParser:
    """Parses a single hook NDJSON line emitted by OpenCode."""

    def parse(self, raw: bytes) -> HookEvent | None:
        try:
            obj = json.loads(raw.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _log.warning("HookQuestionParser: invalid JSON line skipped (%s)", exc)
            return None
        if not isinstance(obj, dict):
            _log.warning("HookQuestionParser: non-object hook skipped")
            return None
        channel = obj.get("channel")
        if not isinstance(channel, str):
            _log.warning("HookQuestionParser: missing channel — skipping")
            return None
        payload = obj.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        # IFR-002 SEC BNDRY: truncate `name` field to 256 UTF-8 bytes.
        name = payload.get("name")
        if isinstance(name, str):
            payload = dict(payload)
            payload["name"] = _truncate_utf8(name)
        return HookEvent(channel=channel, payload=payload)


class McpDegradation:
    """Records that a UI degradation toast has been pushed (FR-017)."""

    def __init__(self) -> None:
        self.toast_pushed: bool = False
        self._toasts: list[str] = []

    def push_toast(self, msg: str) -> None:
        self.toast_pushed = True
        self._toasts.append(msg)

    @property
    def messages(self) -> list[str]:
        return list(self._toasts)


class VersionCheck:
    """Queries OpenCode CLI for its version (mocked in unit tests)."""

    @staticmethod
    def current_version() -> str:
        try:
            res = subprocess.run(
                ["opencode", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            out = (res.stdout or res.stderr or "").strip()
            return out or "0.0.0"
        except (OSError, subprocess.SubprocessError):  # pragma: no cover
            return "0.0.0"


__all__ = [
    "HookConfigWriter",
    "HookEvent",
    "HookQuestionParser",
    "McpDegradation",
    "VersionCheck",
]
