"""T31 INTG/websocket —— feature 12 × IAPI-001 真实 WebSocket。

Traces To 特性设计 §Interface Contract HarnessWsClient · §Test Inventory T31 · IAPI-001（F01 承载）。

Post-F23 contract: F12 echo-stub WebSocket handlers were replaced by real
broadcasters wired through ``harness.api.wire_services``. In-process
``TestClient(app)`` fixtures must explicitly call ``wire_services()`` before
connecting; for /ws/run, pre-publish a ``RunEvent`` so the broadcaster has
something to replay on subscribe; for /ws/hil, publish_opened from inside
the ``with websocket_connect`` block (matching F23 R32 pattern).

本测试标 real_http（走真实 ASGI WebSocket 握手），依赖平台 asyncio + starlette 的
TestClient WebSocket 传输；不 mock 服务端 handler，以保证消费端行为对齐 IAPI-001。
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from harness.api import app, wire_services
from harness.domain.ticket import HilOption, HilQuestion
from harness.orchestrator.bus import RunEvent


@pytest.mark.real_http
def test_f12_t31_real_websocket_run_channel_opens_and_echoes(tmp_path) -> None:
    """feature 12: /ws/run/test-run 必须能握手成功并推送 envelope。"""
    wire_services(app, workdir=tmp_path)
    bus = app.state.run_control_bus
    bus.broadcast_run_event(
        RunEvent(
            kind="run_phase_changed",
            payload={"run_id": "test-run", "state": "running"},
        )
    )

    client = TestClient(app)
    with client.websocket_connect("/ws/run/test-run") as ws:
        ws.send_json({"kind": "subscribe", "channel": "/ws/run/test-run"})
        received = ws.receive_json()
    assert isinstance(received, dict), "WebSocket 必须推送 JSON envelope"
    assert "kind" in received, "envelope 必须含 kind 字段（IAPI-001）"


@pytest.mark.real_http
def test_f12_t31_real_websocket_hil_channel_push_event(tmp_path) -> None:
    """feature 12: /ws/hil 推送一个 HilQuestionOpened envelope。"""
    wire_services(app, workdir=tmp_path)
    hil_bus = app.state.hil_event_bus

    question = HilQuestion(
        id="q-f12",
        kind="single_select",
        header="Q",
        question="Pick one?",
        options=[HilOption(label="a"), HilOption(label="b")],
        multi_select=False,
        allow_freeform=False,
    )

    client = TestClient(app)
    with client.websocket_connect("/ws/hil") as ws:
        hil_bus.publish_opened(ticket_id="t-f12", run_id="r-f12", question=question)
        received = ws.receive_json()
    # Post-F23 wiring._hil_broadcast emits ``{kind: 'hil_event', payload: ...}``.
    # The original "channel == /ws/hil" check came from the F12 echo stub which
    # echoed the subscribe frame; F23 broadcasters carry channel implicitly via
    # the connection URL.
    assert isinstance(received, dict), "WebSocket 必须推送 JSON envelope"
    assert received.get("kind") == "hil_event", (
        f"F23 /ws/hil envelope 必须为 'hil_event'，实际 {received!r}"
    )
    payload = received.get("payload") or {}
    assert payload.get("ticket_id") == "t-f12"
