#!/usr/bin/env python3
"""F18 Wave 4 · claude TUI hook stdin → POST /api/hook/event bridge.

Registered by the workdir-scoped ``.claude/settings.json`` hook entries
(per env-guide §4.5). Each hook fire spawns this short-lived subprocess:

  1. Read stdin JSON (hook event payload)
  2. POST it to ``${HARNESS_BASE_URL}/api/hook/event`` (content-type JSON)
  3. exit 0 on 2xx; exit non-zero + stderr message on connection failure.

Implemented with stdlib only so we never depend on the harness venv resolving
inside the isolated workdir.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base_url = os.environ.get("HARNESS_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        sys.stderr.write("[harness-hook-bridge] HARNESS_BASE_URL not set\n")
        return 2

    try:
        raw = sys.stdin.read()
    except OSError as exc:
        sys.stderr.write(f"[harness-hook-bridge] stdin read failed: {exc}\n")
        return 3

    if not raw.strip():
        sys.stderr.write("[harness-hook-bridge] empty stdin payload\n")
        return 4

    # Minimal stdin JSON validation; harness backend re-validates against
    # HookEventPayload pydantic schema and returns 422 on mismatch.
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[harness-hook-bridge] invalid JSON: {exc}\n")
        return 5

    url = f"{base_url}/api/hook/event"
    body = raw.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Explicitly bypass any HTTP_PROXY in env when posting to a loopback
    # target. urllib.request.urlopen otherwise honours HTTP_PROXY and routes
    # 127.0.0.1 traffic through the proxy, which typically rejects loopback
    # destinations. We build an opener with empty ProxyHandler so the
    # request goes direct.
    parsed_host = ""
    try:
        from urllib.parse import urlparse as _urlparse

        parsed_host = (_urlparse(url).hostname or "").lower()
    except Exception:
        parsed_host = ""
    if parsed_host in ("localhost", "127.0.0.1", "::1"):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    else:
        opener = urllib.request.build_opener()
    try:
        with opener.open(req, timeout=5) as resp:
            status = resp.getcode() or 0
            if 200 <= status < 300:
                return 0
            sys.stderr.write(
                f"[harness-hook-bridge] POST failed: status={status}\n"
            )
            return 6
    except urllib.error.URLError as exc:
        sys.stderr.write(f"[harness-hook-bridge] POST failed: {exc}\n")
        return 7
    except OSError as exc:
        sys.stderr.write(f"[harness-hook-bridge] POST failed: {exc}\n")
        return 8


if __name__ == "__main__":
    raise SystemExit(main())
