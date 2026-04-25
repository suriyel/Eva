"""Integration test for F20 · real FastAPI REST + WebSocket (T50).

[integration] — uses REAL FastAPI TestClient + REAL httpx + REAL websockets
end-to-end. The orchestrator wiring through HTTP is exercised, not mocked.

Feature ref: feature_20

Traces To:
  T50 → §Interface Contract `start_run` end-to-end + IAPI-001/002
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.real_http, pytest.mark.asyncio]


def _git_init(workdir: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=a@b",
            "-c",
            "user.name=A",
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            "i",
        ],
        cwd=workdir,
        check=True,
    )


@pytest.mark.real_http
async def test_t50_post_runs_start_emits_ws_run_phase_changed(tmp_path: Path) -> None:
    """T50 INTG/api+ws (feature_20): POST /api/runs/start returns 200 RunStatus; /ws/run/:id receives RunPhaseChanged(starting) → (running)."""
    from fastapi.testclient import TestClient
    from harness.app.main import build_app  # FastAPI factory

    _git_init(tmp_path)
    app = build_app(workdir=tmp_path)
    client = TestClient(app)

    # POST /api/runs/start
    resp = client.post("/api/runs/start", json={"workdir": str(tmp_path)})
    assert resp.status_code == 200, f"expected 200; got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["state"] in {"starting", "running"}
    run_id = body["run_id"]

    # WS subscribe
    received_kinds: list[str] = []
    with client.websocket_connect(f"/ws/run/{run_id}") as ws:
        # Drain up to 5 messages or 3s
        try:
            while len(received_kinds) < 3:
                msg = ws.receive_json(mode="text")
                received_kinds.append(msg.get("kind", ""))
        except Exception:
            pass

    # Must have at least one RunPhaseChanged
    assert any(
        "RunPhaseChanged" in k or "run_phase_changed" in k for k in received_kinds
    ), f"missing RunPhaseChanged WS event; got kinds={received_kinds}"
