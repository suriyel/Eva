"""Integration tests for F23 · real uvicorn subprocess + WebSocket handshake.

Bugfix Feature #23 — IFR-007 / §6.2.3: 5 WebSocket channels on the production
ASGI entry ``harness.api:app`` must complete a real HTTP 101 upgrade against a
**real uvicorn process** (not just an in-process Starlette TestClient). The
current bug surface has two layers:

  1. ``requirements.txt`` pins ``uvicorn==0.44.0`` without ``[standard]`` — so
     ``websockets`` / ``wsproto`` are NOT installed, and uvicorn rejects every
     WS upgrade with HTTP 404 *before* the ASGI app is reached.
  2. The 5 WS endpoints in ``harness/api/__init__.py`` are F12 echo stubs that
     send mock ``_F21_*_BOOTSTRAP`` envelopes instead of real broadcaster data
     from RunControlBus / HilEventBus / SignalFileWatcher / StreamParser /
     AnomalyClassifier.

[integration] — uses REAL ``uvicorn`` subprocess + REAL ``websockets`` library
end-to-end. NO Starlette TestClient (which bypasses uvicorn entirely and would
hide the 404 root cause). Primary dependencies (uvicorn, websockets, FastAPI,
asyncio) are NOT mocked.

Feature ref: feature 23

Traces To
=========
  R22  IFR-007 + §6.2.3 L1175  /ws/hil real handshake                          (INTG/uvicorn-real-handshake)
  R23  IFR-007 + §6.2.3 L1173  /ws/run/{rid} real broadcaster                  (INTG/uvicorn-real-handshake)
  R24  IFR-007 + §6.2.3 L1176 + FR-024  /ws/anomaly real broadcaster           (INTG/uvicorn-real-handshake)
  R25  IFR-007 + §6.2.3 L1177  /ws/signal SignalFileWatcher real bridge        (INTG/uvicorn-real-handshake)
  R26  IFR-007 + §6.2.3 L1174  /ws/stream/{tid} broadcast_stream_event         (INTG/uvicorn-real-handshake)
  R27  IFR-007 ping protocol §6.1.7 L1101  30s server ping                     (INTG/uvicorn-real-handshake)
  R42  §Interface Contract `ws.ws_run` Raises  unknown run_id                  (FUNC/error)

Negative ratio (this file): R42 = 1/7 ≈ 14.3%
Real uvicorn handshake count (this file): 7

NOTE: These tests REQUIRE a uvicorn child process listening on an ephemeral
port. The fixture ``_real_uvicorn_app`` spawns ``python -m uvicorn
harness.api:app --host 127.0.0.1 --port 0 --no-access-log`` and waits for the
``/api/health`` probe. Until feature 23 is shipped, the spawn either (a) fails
because ``websockets`` is missing — surfaces as ``ConnectionRefusedError`` /
``InvalidStatusCode`` from the websockets client; or (b) the server starts but
WS upgrades are 404'd by uvicorn's HTTP handler. Both are RED outcomes.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest


pytestmark = [pytest.mark.real_http, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _free_port() -> int:
    """Allocate an ephemeral TCP port on 127.0.0.1; release before returning."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


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


@contextmanager
def _spawn_real_uvicorn(
    *, workdir: Path, env_extra: dict[str, str] | None = None
) -> Iterator[tuple[str, int, subprocess.Popen[bytes]]]:
    """Spawn a real ``uvicorn harness.api:app`` subprocess on an ephemeral port.

    Yields ``(host, port, popen)``. On exit, sends SIGTERM and joins. The
    server is verified ready by polling ``GET /api/health`` for up to 8s.

    No mock — uvicorn is the real binary, not stubbed. If ``websockets`` /
    ``wsproto`` are not installed (current bug), uvicorn still binds HTTP/1.1
    successfully but rejects WS upgrades with HTTP 404 in the pre-ASGI layer.
    """
    host = "127.0.0.1"
    port = _free_port()
    env = os.environ.copy()
    env.update(env_extra or {})
    env["HARNESS_WORKDIR"] = str(workdir)
    # Force HARNESS_HOME to a workdir-scoped path so config writes are isolated.
    env.setdefault("HARNESS_HOME", str(workdir / ".harness"))

    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "harness.api:app",
        "--host",
        host,
        "--port",
        str(port),
        "--no-access-log",
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(
        args,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        # Probe /api/health up to 8s.
        deadline = time.monotonic() + 8.0
        ready = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                stdout, _ = proc.communicate(timeout=2)
                raise RuntimeError(
                    f"uvicorn child exited early rc={proc.returncode}; "
                    f"stdout/stderr tail:\n{stdout.decode('utf-8', 'replace')[-2000:]}"
                )
            try:
                with httpx.Client(base_url=f"http://{host}:{port}", timeout=1.0) as c:
                    r = c.get("/api/health")
                    if r.status_code == 200:
                        ready = True
                        break
            except (httpx.HTTPError, OSError):
                pass
            time.sleep(0.1)
        if not ready:
            stdout, _ = proc.communicate(timeout=2)
            raise RuntimeError(
                f"uvicorn never became ready on {host}:{port}; tail:\n"
                f"{stdout.decode('utf-8', 'replace')[-2000:]}"
            )
        yield host, port, proc
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# R22 — Real uvicorn /ws/hil handshake (HTTP 101) + non-echo first frame
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r22_real_uvicorn_ws_hil_completes_handshake(
    tmp_path: Path,
) -> None:
    """feature 23 R22 INTG/uvicorn-real-handshake: a real uvicorn child must
    accept a WebSocket UPGRADE on /ws/hil (HTTP 101). Any frames received
    must NOT be the F12 echo ``subscribe_ack`` envelope nor the F21
    ``hil_question_opened`` *bootstrap* mock (ticket_id='t-bootstrap').
    """
    import websockets  # imported lazily — module unavailable proves R28

    _git_init(tmp_path)
    with _spawn_real_uvicorn(workdir=tmp_path) as (host, port, _proc):
        url = f"ws://{host}:{port}/ws/hil"
        async with websockets.connect(url, open_timeout=5, close_timeout=2) as ws:
            await ws.send(json.dumps({"kind": "subscribe", "channel": "/ws/hil"}))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                envelope: Any = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            except asyncio.TimeoutError:
                envelope = None  # idle until HilEventBus fires — acceptable

    if envelope is not None:
        assert isinstance(
            envelope, dict
        ), f"feature 23 R22 expected JSON dict envelope; got {envelope!r}"
        kind = envelope.get("kind", "")
        assert kind != "subscribe_ack", (
            f"feature 23 R22 received F12 echo subscribe_ack; expected real "
            f"HilEventBus envelope or empty/idle; got {envelope!r}"
        )
        if kind == "hil_question_opened":
            payload = envelope.get("payload") or {}
            assert payload.get("ticket_id") != "t-bootstrap", (
                f"feature 23 R22 received F21 echo bootstrap mock with "
                f"ticket_id='t-bootstrap'; expected real broadcaster envelope; "
                f"got {envelope!r}"
            )


# ---------------------------------------------------------------------------
# R23 — Real uvicorn /ws/run/{rid} broadcasts RunPhaseChanged (running)
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r23_real_uvicorn_ws_run_emits_run_phase_changed(
    tmp_path: Path,
) -> None:
    """feature 23 R23 INTG/uvicorn-real-handshake: starting a run via
    POST /api/runs/start through real uvicorn must cause /ws/run/{rid} to push
    a real RunPhaseChanged{state='running'} envelope (NOT the F21
    ``run_phase_changed`` mock with ``payload.phase='design'``).
    """
    import websockets

    _git_init(tmp_path)
    with _spawn_real_uvicorn(workdir=tmp_path) as (host, port, _proc):
        # Start the run via the real REST route (also exercises R1).
        async with httpx.AsyncClient(base_url=f"http://{host}:{port}", timeout=5.0) as client:
            resp = await client.post("/api/runs/start", json={"workdir": str(tmp_path)})
            assert resp.status_code == 200, (
                f"feature 23 R23 setup: POST /api/runs/start expected 200; got "
                f"{resp.status_code}: {resp.text!r}"
            )
            run_id = resp.json()["run_id"]

        url = f"ws://{host}:{port}/ws/run/{run_id}"
        kinds: list[str] = []
        states: list[str] = []
        async with websockets.connect(url, open_timeout=5, close_timeout=2) as ws:
            try:
                while len(kinds) < 5:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    msg = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                    if isinstance(msg, dict):
                        kinds.append(str(msg.get("kind", "")))
                        payload = msg.get("payload") or {}
                        if isinstance(payload, dict):
                            states.append(str(payload.get("state", "")))
            except asyncio.TimeoutError:
                pass

    assert any(
        k in {"RunPhaseChanged", "run_phase_changed"} for k in kinds
    ), f"feature 23 R23 expected RunPhaseChanged envelope; got kinds={kinds!r}"
    assert "running" in states, (
        f"feature 23 R23 expected payload.state='running' in real broadcaster "
        f"envelope; got states={states!r} (current bug: F12 mock ships "
        f"payload.phase='design' which is not a RunStatus.state literal)"
    )


# ---------------------------------------------------------------------------
# R24 — Real uvicorn /ws/anomaly emits AnomalyDetected after classifier fires
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r24_real_uvicorn_ws_anomaly_pushes_anomaly_detected(
    tmp_path: Path,
) -> None:
    """feature 23 R24 INTG/uvicorn-real-handshake + FR-024: subscribing to
    /ws/anomaly through real uvicorn and triggering a classifier must surface
    an AnomalyDetected envelope (NOT empty echo)."""
    import websockets

    _git_init(tmp_path)
    with _spawn_real_uvicorn(workdir=tmp_path) as (host, port, _proc):
        url = f"ws://{host}:{port}/ws/anomaly"
        async with websockets.connect(url, open_timeout=5, close_timeout=2) as ws:
            # Trigger an anomaly via a debug REST hook the production wiring
            # exposes (POST /api/anomaly/_test/inject — added by feature 23
            # for ws_anomaly fixture). Until shipped → 404 here, masking the
            # WS-side regression as the failure surface.
            async with httpx.AsyncClient(base_url=f"http://{host}:{port}", timeout=5.0) as client:
                inject_resp = await client.post(
                    "/api/anomaly/_test/inject",
                    json={
                        "ticket_id": "t-r24",
                        "cls": "context_overflow",
                        "retry_count": 1,
                    },
                )
                assert inject_resp.status_code == 200, (
                    f"feature 23 R24 setup: anomaly inject hook missing; got "
                    f"{inject_resp.status_code}: {inject_resp.text!r}"
                )

            raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            envelope = json.loads(raw) if isinstance(raw, (str, bytes)) else raw

    assert isinstance(envelope, dict), f"feature 23 R24 expected dict envelope; got {envelope!r}"
    assert envelope.get("kind") in {
        "AnomalyDetected",
        "anomaly_detected",
    }, f"feature 23 R24 expected AnomalyDetected envelope; got {envelope!r}"
    payload = envelope.get("payload") or {}
    assert (
        payload.get("ticket_id") == "t-r24"
    ), f"feature 23 R24 expected payload.ticket_id='t-r24'; got {envelope!r}"
    assert (
        payload.get("cls") == "context_overflow"
    ), f"feature 23 R24 expected payload.cls='context_overflow'; got {envelope!r}"
    assert (
        payload.get("retry_count") == 1
    ), f"feature 23 R24 expected payload.retry_count=1; got {envelope!r}"


# ---------------------------------------------------------------------------
# R25 — Real uvicorn /ws/signal forwards SignalFileWatcher events
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r25_real_uvicorn_ws_signal_forwards_bugfix_request(
    tmp_path: Path,
) -> None:
    """feature 23 R25 INTG/uvicorn-real-handshake: SignalFileWatcher must
    bridge a real ``bugfix-request.json`` write to /ws/signal as
    SignalFileChanged{kind='bugfix_request'}."""
    import websockets

    _git_init(tmp_path)
    with _spawn_real_uvicorn(workdir=tmp_path) as (host, port, _proc):
        url = f"ws://{host}:{port}/ws/signal"
        async with websockets.connect(url, open_timeout=5, close_timeout=2) as ws:
            # Touch the file AFTER subscribing so we can observe the broadcast.
            (tmp_path / "bugfix-request.json").write_text('{"id":"bug-r25"}', encoding="utf-8")

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=4.0)
                envelope = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            except asyncio.TimeoutError:
                pytest.fail(
                    "feature 23 R25 expected SignalFileChanged envelope on "
                    "/ws/signal within 4s of writing bugfix-request.json; "
                    "current bug: F12 echo stub never broadcasts"
                )

    assert isinstance(envelope, dict), f"feature 23 R25 expected dict envelope; got {envelope!r}"
    assert envelope.get("kind") in {
        "SignalFileChanged",
        "signal_file_changed",
    }, f"feature 23 R25 expected SignalFileChanged envelope; got {envelope!r}"
    payload = envelope.get("payload") or {}
    assert (
        payload.get("kind") == "bugfix_request"
    ), f"feature 23 R25 expected payload.kind='bugfix_request'; got {envelope!r}"
    assert "bugfix-request.json" in (payload.get("path") or ""), (
        f"feature 23 R25 expected payload.path containing bugfix-request.json; " f"got {envelope!r}"
    )


# ---------------------------------------------------------------------------
# R26 — Real uvicorn /ws/stream/{tid} forwards broadcast_stream_event
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r26_real_uvicorn_ws_stream_forwards_stream_event(
    tmp_path: Path,
) -> None:
    """feature 23 R26 INTG/uvicorn-real-handshake: RunControlBus.broadcast_stream_event
    must reach /ws/stream/{tid} as a real StreamEvent envelope (current bug:
    bus has no broadcast_stream_event method, ws handler is F12 echo)."""
    import websockets

    _git_init(tmp_path)
    ticket_id = "t-r26"
    with _spawn_real_uvicorn(workdir=tmp_path) as (host, port, _proc):
        url = f"ws://{host}:{port}/ws/stream/{ticket_id}"
        async with websockets.connect(url, open_timeout=5, close_timeout=2) as ws:
            async with httpx.AsyncClient(base_url=f"http://{host}:{port}", timeout=5.0) as client:
                # POST /api/_test/stream-inject is the test-only hook feature 23
                # adds for symmetry with R24's anomaly inject. Missing → 404.
                inject = await client.post(
                    "/api/_test/stream-inject",
                    json={
                        "ticket_id": ticket_id,
                        "seq": 1,
                        "kind": "text",
                        "payload": {"text": "hello-r26"},
                    },
                )
                assert inject.status_code == 200, (
                    f"feature 23 R26 setup: stream inject hook missing; got "
                    f"{inject.status_code}: {inject.text!r}"
                )

            raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            envelope = json.loads(raw) if isinstance(raw, (str, bytes)) else raw

    assert isinstance(envelope, dict), f"feature 23 R26 expected dict envelope; got {envelope!r}"
    assert envelope.get("kind") in {
        "StreamEvent",
        "stream_event",
    }, f"feature 23 R26 expected StreamEvent envelope; got {envelope!r}"
    payload = envelope.get("payload") or {}
    assert (
        payload.get("ticket_id") == ticket_id
    ), f"feature 23 R26 expected payload.ticket_id={ticket_id!r}; got {envelope!r}"
    assert payload.get("seq") == 1, f"feature 23 R26 expected payload.seq=1; got {envelope!r}"
    assert (payload.get("payload") or {}).get(
        "text"
    ) == "hello-r26", f"feature 23 R26 expected nested payload.text='hello-r26'; got {envelope!r}"


# ---------------------------------------------------------------------------
# R27 — Server ping protocol on /ws/run/{rid}
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r27_real_uvicorn_ws_run_emits_server_ping(
    tmp_path: Path,
) -> None:
    """feature 23 R27 INTG/uvicorn-real-handshake + IFR-007 ping: server must
    emit a ``ping`` envelope at least once within ~30s (we use a shorter test
    interval via ``HARNESS_WS_PING_INTERVAL_SEC=2`` so the test runs in <5s).

    Current bug: no server-ping logic in F12 echo handlers; client reconnect
    timer (60s) would never observe a heartbeat → would force reconnect storm.
    """
    import websockets

    _git_init(tmp_path)
    run_id = "r-r27"
    with _spawn_real_uvicorn(
        workdir=tmp_path,
        env_extra={"HARNESS_WS_PING_INTERVAL_SEC": "2"},
    ) as (host, port, _proc):
        url = f"ws://{host}:{port}/ws/run/{run_id}"
        kinds: list[str] = []
        async with websockets.connect(url, open_timeout=5, close_timeout=2) as ws:
            deadline = time.monotonic() + 5.0
            try:
                while time.monotonic() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    msg = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                    if isinstance(msg, dict):
                        kinds.append(str(msg.get("kind", "")))
                        if "ping" in str(msg.get("kind", "")).lower():
                            break
            except asyncio.TimeoutError:
                pass

    assert any("ping" in k.lower() for k in kinds), (
        f"feature 23 R27 expected at least one ``ping`` envelope within 5s "
        f"(HARNESS_WS_PING_INTERVAL_SEC=2); got kinds={kinds!r}. Current bug: "
        "no server-side ping in F12 echo handler — IFR-007 reconnect timer "
        "would never see a heartbeat."
    )


# ---------------------------------------------------------------------------
# R42 — Real uvicorn /ws/run/{unknown} must NOT echo bogus events
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r42_real_uvicorn_ws_run_unknown_id_emits_no_mock(
    tmp_path: Path,
) -> None:
    """feature 23 R42 FUNC/error: subscribing to /ws/run/{unknown_run_id} on
    real uvicorn must NOT push the F12 ``run_phase_changed`` mock with
    ``payload.phase='design'`` (subscriber may receive nothing or close).
    Current bug: every connection receives the bootstrap mock regardless of
    run_id, deceiving the client into thinking a run exists."""
    import websockets

    _git_init(tmp_path)
    with _spawn_real_uvicorn(workdir=tmp_path) as (host, port, _proc):
        url = f"ws://{host}:{port}/ws/run/run-does-not-exist"
        async with websockets.connect(url, open_timeout=5, close_timeout=2) as ws:
            await ws.send(
                json.dumps({"kind": "subscribe", "channel": "/ws/run/run-does-not-exist"})
            )
            received: list[Any] = []
            try:
                while len(received) < 3:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    msg = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                    received.append(msg)
            except asyncio.TimeoutError:
                pass

    # Must NOT contain the F12 echo run_phase_changed mock with phase='design'.
    for m in received:
        if isinstance(m, dict):
            payload = m.get("payload") or {}
            kind = str(m.get("kind", ""))
            if kind in {"run_phase_changed", "RunPhaseChanged"}:
                # If a real broadcaster fires for our unknown id (it shouldn't),
                # at minimum it must NOT carry the F12 mock 'phase' field.
                assert payload.get("phase") != "design", (
                    f"feature 23 R42 received F12 mock RunPhaseChanged "
                    f"(payload.phase='design') for unknown run_id; got {m!r}"
                )
                # The real broadcaster carries 'state' not 'phase'.
                assert "state" in payload, (
                    f"feature 23 R42 expected real broadcaster envelope to "
                    f"carry payload.state, not the F12 mock 'phase' field; got {m!r}"
                )
