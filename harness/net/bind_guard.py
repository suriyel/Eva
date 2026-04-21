"""BindGuard — NFR-007 / CON-006 loopback enforcement.

Provides:
    * ``assert_loopback_only(sock)`` — raises ``BindRejectedError`` unless
      ``sock.getsockname()`` reports ``127.0.0.1`` or ``::1``.
    * ``parse_listening_sockets()`` — shells out to platform-appropriate
      command (ss / lsof / netstat) and returns sockets owned by the current
      process. Used by ``/api/health`` + NFR-007 self-check.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass


class BindRejectedError(Exception):
    """Raised when the bind host is not loopback (NFR-007 + CON-006)."""

    def __init__(self, actual_host: str, message: str | None = None) -> None:
        self.actual_host = actual_host
        super().__init__(
            message or f"refusing non-loopback bind (host={actual_host!r}); NFR-007/CON-006"
        )


class BindUnavailableError(Exception):
    """Raised when the requested port is already in use (port != 0)."""


@dataclass(frozen=True)
class ListeningSocket:
    host: str
    port: int
    pid: int


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})


class BindGuard:
    """Loopback-only guard + cross-platform LISTEN socket introspection."""

    # ------------------------------------------------------------ assert
    def assert_loopback_only(self, sock: "socket.socket | _HasGetsockname") -> None:
        """Raise ``BindRejectedError`` if socket is not bound to loopback."""
        name = sock.getsockname()
        # IPv4 getsockname returns (host, port); IPv6 returns 4-tuple.
        host = name[0]
        if host not in _LOOPBACK_HOSTS:
            raise BindRejectedError(host)

    # ------------------------------------------------------------ parse
    def parse_listening_sockets(self) -> list[ListeningSocket]:
        """Return LISTEN sockets owned by the current process.

        Linux  : ``ss -tnlp``
        macOS  : ``lsof -nP -iTCP -sTCP:LISTEN``
        Windows: ``netstat -ano -p TCP``
        """
        own_pid = os.getpid()
        try:
            if sys.platform.startswith("linux"):
                out = _run(["ss", "-tnlpH"])
                return [s for s in _parse_ss_output(out) if s.pid == own_pid]
            if sys.platform == "darwin":
                out = _run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"])
                return [s for s in _parse_lsof_output(out) if s.pid == own_pid]
            if sys.platform == "win32":  # pragma: no cover — non-Linux CI
                out = _run(["netstat", "-ano", "-p", "TCP"])
                return [s for s in _parse_netstat_output(out) if s.pid == own_pid]
        except FileNotFoundError as exc:
            raise OSError(f"listing command not available: {exc}") from exc
        return []


class _HasGetsockname:  # pragma: no cover — structural protocol stub for typing
    def getsockname(self) -> tuple[str, int]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Platform parsers.
# ---------------------------------------------------------------------------
def _run(argv: list[str]) -> str:
    """Run command with no shell; return stdout text (stderr merged empty)."""
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    return proc.stdout or ""


# Example ss -tnlpH line:
# LISTEN 0 128 127.0.0.1:46473 0.0.0.0:* users:(("python",pid=12345,fd=8))
_SS_PID_RE = re.compile(r"pid=(\d+)")


def _parse_ss_output(text: str) -> list[ListeningSocket]:
    out: list[ListeningSocket] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not line.startswith("LISTEN"):
            # ``-H`` suppresses the header; but defensively skip "State" rows too.
            if not line.lower().startswith("state"):
                pass
        cols = line.split()
        if len(cols) < 5:
            continue
        # With -H, the first col is state; without, first is state too. Pick
        # the column that contains ':' and is NOT '*:*' / '0.0.0.0:*'.
        local = None
        for c in cols[:6]:
            if ":" in c and not c.endswith(":*"):
                local = c
                break
        if local is None:
            continue
        host, _, port_s = local.rpartition(":")
        # IPv6 brackets: "[::1]:8080" → strip brackets.
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        try:
            port = int(port_s)
        except ValueError:
            continue
        pid_match = _SS_PID_RE.search(line)
        if not pid_match:
            continue
        pid = int(pid_match.group(1))
        out.append(ListeningSocket(host=host, port=port, pid=pid))
    return out


# Example lsof output line:
# python  12345 user    8u  IPv4 0xff   0t0  TCP 127.0.0.1:46473 (LISTEN)
def _parse_lsof_output(text: str) -> list[ListeningSocket]:
    out: list[ListeningSocket] = []
    for line in text.splitlines()[1:]:  # skip header
        cols = line.split()
        if len(cols) < 9:
            continue
        try:
            pid = int(cols[1])
        except ValueError:
            continue
        addr = cols[8]
        if "(LISTEN)" not in line:
            continue
        host, _, port_s = addr.rpartition(":")
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        try:
            port = int(port_s)
        except ValueError:
            continue
        out.append(ListeningSocket(host=host, port=port, pid=pid))
    return out


# Example netstat -ano -p TCP line:
#   TCP    127.0.0.1:46473   0.0.0.0:0   LISTENING   12345
def _parse_netstat_output(text: str) -> list[ListeningSocket]:  # pragma: no cover
    out: list[ListeningSocket] = []
    for line in text.splitlines():
        cols = line.split()
        if len(cols) < 5 or cols[0].upper() != "TCP":
            continue
        state = cols[3].upper()
        if state != "LISTENING":
            continue
        local = cols[1]
        host, _, port_s = local.rpartition(":")
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        try:
            port = int(port_s)
            pid = int(cols[4])
        except ValueError:
            continue
        out.append(ListeningSocket(host=host, port=port, pid=pid))
    return out
