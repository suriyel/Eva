"""F18 Wave 4 · scripts/claude-hook-bridge.py stdin → POST tests.

Test Inventory: T35, T36.
SRS: FR-051 / IAPI-020 + Design Implementation Summary §3 hook bridge.

Layer marker:
  # [unit] — exercises the bridge script as a subprocess against a mock HTTP listener.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRIDGE_SCRIPT = _REPO_ROOT / "scripts" / "claude-hook-bridge.py"


class _CaptureHandler(http.server.BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"_raw": body}
        type(self).received.append(
            {
                "path": self.path,
                "content_type": self.headers.get("content-type"),
                "body": payload,
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"accepted": true}')

    def log_message(self, *args, **kwargs):  # noqa: D401
        return


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def capture_server():
    """Spin up an in-process HTTP server that records POST bodies."""
    _CaptureHandler.received = []
    port = _free_port()
    server = http.server.HTTPServer(("127.0.0.1", port), _CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"port": port, "received": _CaptureHandler.received}
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# T35 — FUNC/happy — claude-hook-bridge.py POSTs to harness/api/hook/event
# ---------------------------------------------------------------------------
def test_t35_bridge_script_posts_stdin_json_to_harness(capture_server):
    """Run scripts/claude-hook-bridge.py with stdin JSON; verify it POSTs to capture server."""
    assert _BRIDGE_SCRIPT.exists(), (
        f"scripts/claude-hook-bridge.py missing — Wave 4 design §4.5 hook bridge artifact "
        f"must exist at {_BRIDGE_SCRIPT}"
    )
    port = capture_server["port"]
    env = {**os.environ, "HARNESS_BASE_URL": f"http://127.0.0.1:{port}"}
    payload = {
        "session_id": "abc",
        "transcript_path": "/tmp/x.jsonl",
        "cwd": "/tmp",
        "hook_event_name": "SessionStart",
        "ts": "2026-04-26T23:46:00+00:00",
    }
    proc = subprocess.run(
        [sys.executable, str(_BRIDGE_SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode == 0, f"bridge exit code {proc.returncode}; stderr={proc.stderr!r}"
    received = capture_server["received"]
    assert len(received) == 1, f"expected 1 POST, got {len(received)}: {received!r}"
    assert received[0]["path"] == "/api/hook/event"
    assert received[0]["body"]["hook_event_name"] == "SessionStart"
    assert received[0]["body"]["session_id"] == "abc"


# ---------------------------------------------------------------------------
# T36 — FUNC/error — bridge script: harness unreachable → non-zero exit + stderr
# ---------------------------------------------------------------------------
def test_t36_bridge_script_unreachable_harness_exits_nonzero_with_stderr():
    """When harness is not listening, bridge must NOT silently swallow the error."""
    assert _BRIDGE_SCRIPT.exists(), f"bridge script missing: {_BRIDGE_SCRIPT}"
    # 127.0.0.1:1 should be unreachable for almost every test environment.
    env = {**os.environ, "HARNESS_BASE_URL": "http://127.0.0.1:1"}
    payload = {
        "session_id": "abc",
        "transcript_path": "/tmp/x.jsonl",
        "cwd": "/tmp",
        "hook_event_name": "SessionStart",
        "ts": "2026-04-26T23:46:00+00:00",
    }
    proc = subprocess.run(
        [sys.executable, str(_BRIDGE_SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode != 0, f"unreachable harness must yield non-zero exit; got {proc.returncode}"
    assert "POST failed" in proc.stderr or "harness-hook-bridge" in proc.stderr, (
        f"stderr should signal POST failure; got {proc.stderr!r}"
    )
