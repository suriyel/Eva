"""Integration tests for F23 · dependency, route registration, lifespan wiring,
in-process WS broadcasts, and F20 ST anti-regression anchor.

Bugfix Feature #23 — these tests cover the *non*-handshake regressions:

  R28  Dependency import — ``websockets`` + ``wsproto`` from ``uvicorn[standard]``
  R29  Single ``/ws/run/{run_id}`` route on production ``harness.api:app``
  R30  F20 build_app factory test (test_f20_real_rest_ws.py) still passes
  R31  In-process WS sniff — anomaly broadcaster reaches /ws/anomaly subscribers
  R32  In-process WS sniff — HilEventBus.publish_answered reaches /ws/hil
  R36  AppBootstrap (or wire_services) populates ALL 9 ``app.state.*`` slots

Plus a Bus-API existence guard for ``RunControlBus.broadcast_stream_event``
(new public method introduced by feature 23, see Interface Contract row).

[integration] — uses REAL FastAPI ASGI dispatch via Starlette TestClient
(in-process) for R31/R32 WS sniffing — no mock on the bus, watcher, or hub.

Feature ref: feature 23

Traces To
=========
  R28  Design §3.4 L240 / §8.4 L1539  uvicorn[standard] transitive deps        (INTG/dependency-import)
  R29  §Design Alignment §6.2.3       single /ws/run route on production app   (INTG/single-definition)
  R30  F20 ST anchor                  test_f20_real_rest_ws still green        (INTG/regression-f20-st)
  R31  FR-024 + §6.2.3 L1176          in-process anomaly broadcaster           (INTG/asgi-rest)
  R32  §6.2.2 L1145 + §6.2.3 L1175    HIL flow REST ↔ WS round-trip            (INTG/hil-flow)
  R36  AppBootstrap wiring            9 app.state slots populated              (INTG/lifespan)
  +    bus.broadcast_stream_event API New bus method exists + captured replay  (INTG/bus-api)

Negative ratio (this file): 0/8 (these are wiring / regression / discovery
tests; their RED outcome is ImportError / AttributeError / 404 — not 4xx).
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.real_http]


# ---------------------------------------------------------------------------
# R28 — websockets + wsproto importable (uvicorn[standard] transitive deps)
# ---------------------------------------------------------------------------
@pytest.mark.real_http
def test_f23_feature_23_r28_websockets_and_wsproto_importable() -> None:
    """feature 23 R28 INTG/dependency-import: ``websockets`` and ``wsproto``
    must both be importable. Current bug: ``requirements.txt`` pins
    ``uvicorn==0.44.0`` (no ``[standard]`` extra) so neither transitive dep
    is installed and uvicorn rejects every WS upgrade with HTTP 404 in the
    pre-ASGI layer."""
    websockets_spec = importlib.util.find_spec("websockets")
    wsproto_spec = importlib.util.find_spec("wsproto")

    assert websockets_spec is not None, (
        "feature 23 R28: ``websockets`` is not importable in the current venv. "
        "Fix: change requirements.txt from ``uvicorn==0.44.0`` to "
        "``uvicorn[standard]==0.44.0`` (transitive: websockets, wsproto, "
        "httptools, uvloop)."
    )
    assert wsproto_spec is not None, (
        "feature 23 R28: ``wsproto`` is not importable in the current venv. "
        "Same root cause as the websockets miss; ``uvicorn[standard]`` extra "
        "pulls both."
    )

    # High-value: actually exercise the modules so silent partial installs are caught.
    import websockets as _ws  # noqa: F401  — proves real import works
    import wsproto as _wsp  # noqa: F401

    assert hasattr(_ws, "connect"), (
        "feature 23 R28: ``websockets`` imported but exposes no ``connect`` API; "
        "partial install? expected websockets >= 10.4 from uvicorn[standard]."
    )
    assert hasattr(_wsp, "WSConnection") or hasattr(_wsp, "ConnectionType"), (
        "feature 23 R28: ``wsproto`` imported but exposes no expected API; " "partial install?"
    )


# ---------------------------------------------------------------------------
# R29 — Single /ws/run/{run_id} route on production app
# ---------------------------------------------------------------------------
@pytest.mark.real_http
def test_f23_feature_23_r29_single_ws_run_route_on_production_app_with_real_broadcaster() -> None:
    """feature 23 R29 INTG/single-definition: production ``harness.api:app``
    must declare exactly one ``/ws/run/{run_id}`` WebSocket route, AND that
    route's handler must NOT be the F12 ``_ws_echo_channel`` stub. Build_app
    factory must remain importable (for R30 anti-regression anchor)."""
    import inspect

    from harness.api import app

    matches = [r for r in app.routes if "ws/run" in getattr(r, "path", "")]
    assert len(matches) == 1, (
        f"feature 23 R29 expected exactly 1 /ws/run route on production app; "
        f"got {len(matches)}: {[getattr(r, 'path', '?') for r in matches]!r}"
    )
    paths = {getattr(r, "path", "") for r in matches}
    assert paths == {
        "/ws/run/{run_id}"
    }, f"feature 23 R29 expected /ws/run/{{run_id}}; got {paths!r}"

    # Inspect the handler — it must NOT be the F12 echo stub.
    route = matches[0]
    endpoint = getattr(route, "endpoint", None)
    assert (
        endpoint is not None
    ), f"feature 23 R29 expected ws_run route to expose .endpoint; got {route!r}"
    src = inspect.getsource(endpoint)
    assert "_ws_echo_channel" not in src, (
        f"feature 23 R29 production /ws/run handler must NOT delegate to "
        f"_ws_echo_channel (F12 stub); got source:\n{src[:600]}"
    )
    assert "_F21_RUN_BOOTSTRAP" not in src, (
        f"feature 23 R29 production /ws/run handler must NOT use the "
        f"F21 mock _F21_RUN_BOOTSTRAP envelope; got source:\n{src[:600]}"
    )
    # Real broadcaster must subscribe to RunControlBus.
    assert "run_control_bus" in src or "RunControlBus" in src or "subscribe" in src, (
        f"feature 23 R29 production /ws/run handler must subscribe to "
        f"app.state.run_control_bus (real broadcaster); got source:\n{src[:600]}"
    )

    # build_app must STILL exist (for R30) — feature 23 must not delete it.
    from harness.app.main import build_app  # noqa: F401

    assert callable(build_app), (
        "feature 23 R29: build_app factory must remain callable so the F20 ST "
        "regression anchor (test_f20_real_rest_ws.py) keeps working — feature "
        "23 forbids deleting it; only the production wiring is normalised."
    )


# ---------------------------------------------------------------------------
# R30 — F20 ST regression: test_f20_real_rest_ws.py must remain green
# ---------------------------------------------------------------------------
@pytest.mark.real_http
def test_f23_feature_23_r30_f20_real_rest_ws_anti_regression(
    tmp_path: Path,
) -> None:
    """feature 23 R30 INTG/regression-f20-st: the F20 build_app factory test
    must remain importable AND its single test must succeed when invoked
    via subprocess pytest (full isolation from the wiring changes)."""
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "tests" / "integration" / "test_f20_real_rest_ws.py"
    assert target.exists(), (
        f"feature 23 R30 expected anchor file at {target}; missing — feature 23 "
        "must NOT delete the F20 anti-regression test."
    )

    # Run only the F20 anchor in a child pytest so the wiring work in feature 23
    # is fully isolated from the assertion.
    proc = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(target),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode == 0, (
        f"feature 23 R30 anti-regression FAILED: F20 build_app factory test "
        f"must remain green. Pytest exit={proc.returncode}; tail=\n"
        f"{combined[-2000:]}"
    )


# ---------------------------------------------------------------------------
# R31 — In-process /ws/anomaly receives RunControlBus.broadcast_anomaly events
# ---------------------------------------------------------------------------
@pytest.mark.real_http
def test_f23_feature_23_r31_inproc_ws_anomaly_receives_broadcaster_events(
    tmp_path: Path,
) -> None:
    """feature 23 R31 INTG/asgi-rest: subscribing to /ws/anomaly via the
    Starlette in-process TestClient must surface a real
    ``RunControlBus.broadcast_anomaly`` AnomalyDetected envelope (NOT echo).
    """
    from starlette.testclient import TestClient

    from harness.api import app, wire_services  # type: ignore[attr-defined]
    from harness.orchestrator.bus import AnomalyEvent

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
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
        cwd=tmp_path,
        check=True,
    )
    wire_services(app, workdir=tmp_path)
    bus = app.state.run_control_bus

    client = TestClient(app)
    with client.websocket_connect("/ws/anomaly") as ws:
        # Push one AnomalyEvent through the real bus.
        bus.broadcast_anomaly(
            AnomalyEvent(
                kind="AnomalyDetected",
                cls="context_overflow",
                ticket_id="t-r31",
                retry_count=2,
            )
        )
        envelope = ws.receive_json()

    assert isinstance(envelope, dict), f"feature 23 R31 expected dict envelope; got {envelope!r}"
    assert envelope.get("kind") in {
        "AnomalyDetected",
        "anomaly_detected",
    }, f"feature 23 R31 expected AnomalyDetected envelope; got {envelope!r}"
    payload = envelope.get("payload") or {}
    assert (
        payload.get("ticket_id") == "t-r31"
    ), f"feature 23 R31 expected payload.ticket_id='t-r31'; got {envelope!r}"
    assert (
        payload.get("retry_count") == 2
    ), f"feature 23 R31 expected payload.retry_count=2; got {envelope!r}"


# ---------------------------------------------------------------------------
# R32 — In-process /ws/hil receives HilEventBus.publish_answered events
# ---------------------------------------------------------------------------
@pytest.mark.real_http
def test_f23_feature_23_r32_inproc_ws_hil_receives_publish_answered(
    tmp_path: Path,
) -> None:
    """feature 23 R32 INTG/hil-flow WS half: HilEventBus.publish_answered must
    flow through to /ws/hil subscribers as a real envelope (not F12 echo)."""
    from starlette.testclient import TestClient

    from harness.api import app, wire_services  # type: ignore[attr-defined]
    from harness.domain.ticket import HilAnswer

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
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
        cwd=tmp_path,
        check=True,
    )
    wire_services(app, workdir=tmp_path)
    bus = app.state.hil_event_bus

    client = TestClient(app)
    with client.websocket_connect("/ws/hil") as ws:
        bus.publish_answered(
            ticket_id="t-r32",
            run_id="run-r32",
            answer=HilAnswer(
                question_id="q-1",
                selected_labels=["yes"],
                freeform_text="ok",
                answered_at="2026-04-25T10:00:00+00:00",
            ),
        )
        envelope = ws.receive_json()

    assert isinstance(envelope, dict), f"feature 23 R32 expected dict envelope; got {envelope!r}"
    payload = envelope.get("payload") or envelope
    assert (
        payload.get("ticket_id") == "t-r32"
    ), f"feature 23 R32 expected payload.ticket_id='t-r32'; got {envelope!r}"
    answer = payload.get("answer") or {}
    if isinstance(answer, dict) and answer:
        assert answer.get("freeform_text") == "ok", (
            f"feature 23 R32 expected nested answer.freeform_text='ok'; got " f"{envelope!r}"
        )


# ---------------------------------------------------------------------------
# R36 — AppBootstrap wiring populates 9 ``app.state.*`` slots
# ---------------------------------------------------------------------------
@pytest.mark.real_http
def test_f23_feature_23_r36_appbootstrap_populates_all_state_slots(
    tmp_path: Path,
) -> None:
    """feature 23 R36 INTG/lifespan: after AppBootstrap.start() (or
    wire_services), production ``harness.api:app`` must expose ALL 9
    service singletons on ``app.state``. Current bug: AppBootstrap only
    sets bind_host/bind_port/claude_auth_status; service layer never wired."""
    from harness.api import app, wire_services  # type: ignore[attr-defined]

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
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
        cwd=tmp_path,
        check=True,
    )
    wire_services(app, workdir=tmp_path)

    required_slots = (
        "orchestrator",
        "run_control_bus",
        "ticket_repo",
        "hil_event_bus",
        "signal_file_watcher",
        "files_service",
        "commit_list_service",
        "diff_loader",
        "validator_runner",
    )
    missing = []
    for name in required_slots:
        if not hasattr(app.state, name) or getattr(app.state, name) is None:
            missing.append(name)
    assert not missing, (
        f"feature 23 R36 expected all 9 app.state slots populated; missing: "
        f"{missing!r}. Required: {required_slots!r}."
    )


# ---------------------------------------------------------------------------
# R-bus — RunControlBus.broadcast_stream_event must exist + capture
# ---------------------------------------------------------------------------
@pytest.mark.real_http
def test_f23_feature_23_rbus_run_control_bus_has_broadcast_stream_event() -> None:
    """feature 23 §Interface Contract: ``RunControlBus.broadcast_stream_event``
    is a NEW public method introduced by this bugfix to bridge F18 StreamParser
    async iterator events into the /ws/stream/{tid} broadcaster.

    Current bug: bus has broadcast_run_event/anomaly/signal but NO stream
    counterpart → /ws/stream WS handler cannot replay or push.

    Asserts: method exists, is callable, captures via ``captured_stream_events``.
    """
    from harness.orchestrator.bus import RunControlBus

    bus = RunControlBus.build_test_default()

    assert hasattr(bus, "broadcast_stream_event"), (
        "feature 23 §Interface Contract: RunControlBus.broadcast_stream_event "
        "method missing. Required by /ws/stream/{ticket_id} bridge for F18 "
        "StreamParser → WS clients."
    )
    assert hasattr(bus, "captured_stream_events"), (
        "feature 23 §Interface Contract: RunControlBus.captured_stream_events "
        "introspection missing — needed for replay on subscribe."
    )

    sample_event = {
        "ticket_id": "t-bus-1",
        "seq": 1,
        "ts": "2026-04-25T10:00:00+00:00",
        "kind": "text",
        "payload": {"text": "hi"},
    }
    bus.broadcast_stream_event(sample_event)  # type: ignore[attr-defined]
    captured = bus.captured_stream_events()  # type: ignore[attr-defined]
    assert isinstance(captured, list) and len(captured) == 1, (
        f"feature 23: captured_stream_events() expected list[len=1]; got " f"{captured!r}"
    )
    entry = captured[0]
    if isinstance(entry, dict):
        assert (
            entry.get("ticket_id") == "t-bus-1"
        ), f"feature 23: captured stream event lost ticket_id; got {entry!r}"
        assert entry.get("seq") == 1, f"feature 23: captured stream event lost seq; got {entry!r}"
    else:
        assert (
            getattr(entry, "ticket_id", None) == "t-bus-1"
        ), f"feature 23: captured stream event lost ticket_id; got {entry!r}"
