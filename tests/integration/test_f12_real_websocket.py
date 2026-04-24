"""T31 INTG/websocket —— feature 12 × IAPI-001 真实 WebSocket。

Traces To 特性设计 §Interface Contract HarnessWsClient · §Test Inventory T31 · IAPI-001（F01 承载）。

Red 阶段：F01 尚未实现 /ws/run/:id 等 WebSocket endpoint；本测试必须 FAIL 于
    "WebSocket endpoint not found" / 连接被拒，作为 Green 阶段接线点。

本测试标 real_http（走真实 ASGI WebSocket 握手），依赖平台 asyncio + starlette 的
TestClient WebSocket 传输；不 mock 服务端 handler，以保证消费端行为对齐 IAPI-001。
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from harness.api import app


@pytest.mark.real_http
def test_f12_t31_real_websocket_run_channel_opens_and_echoes() -> None:
    """feature 12: /ws/run/test-run 必须能握手成功并接受 subscribe 消息。"""
    client = TestClient(app)
    with client.websocket_connect("/ws/run/test-run") as ws:
        ws.send_json({"kind": "subscribe", "channel": "/ws/run/test-run"})
        # 服务端必须回一个 ack 或一个 WsEvent envelope；断言 envelope 含 kind 字段
        received = ws.receive_json()
    assert isinstance(received, dict), "WebSocket 必须推送 JSON envelope"
    assert "kind" in received, "envelope 必须含 kind 字段（IAPI-001）"


@pytest.mark.real_http
def test_f12_t31_real_websocket_hil_channel_push_event() -> None:
    """feature 12: /ws/hil 推送一个 HilQuestionOpened envelope。"""
    client = TestClient(app)
    with client.websocket_connect("/ws/hil") as ws:
        ws.send_json({"kind": "subscribe", "channel": "/ws/hil"})
        received = ws.receive_json()
    assert (
        received.get("channel") == "/ws/hil"
    ), f"envelope.channel 必须为 /ws/hil，实际 {received!r}"
