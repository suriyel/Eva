"""F21 (feature 21) real WebSocket integration smoke (T28 / T30 wireline).

Traces To 特性 21 design §Test Inventory T28 (INTG/ws · /ws/hil) ·
          T30 (INTG/recon · IFR-007) ·
          §Interface Contract HilInboxPage / TicketStreamPage IAPI-001 consumer ·
          §Design Alignment sequenceDiagram msg `FastApiHilWs-->>HarnessWsClient: HilQuestionOpened`.

F21 是前端特性，但 design §4.6.4 表声明它消费 IAPI-001 WebSocket 频道
``/ws/hil`` / ``/ws/stream/:ticket_id`` / ``/ws/run/<run_id>``。F12 已交付 echo handler
但仅返回 ``subscribe_ack``；feature #23 把 5 条 WS 频道从 echo stub 升级为接驳
``RunControlBus`` / ``HilEventBus`` / F18 stream parser / ``AnomalyClassifier`` /
``SignalFileWatcher`` 真实 broadcaster。本测试组验证升级后契约：

- in-process ``TestClient(app)`` 必须先调 ``wire_services(app, workdir=…)``
  才能让 broadcaster 在 ``app.state`` 上可见。
- ``/ws/run/{run_id}`` / ``/ws/stream/{ticket_id}`` 在 subscribe 时**重放**
  ``bus.captured_*_events()`` 中匹配 id 的事件，所以测试预先 broadcast 一条事件
  让 receive_json 立即拿到。
- ``/ws/hil`` 不重放，只在 ``HilEventBus`` 推送时入队，所以测试用副线程
  在握手后 publish_opened，再 receive_json。

Real test convention（feature-list.json::real_test）:
  - marker @pytest.mark.real_http
  - feature reference "feature 21" 出现在 docstring + 函数名（check_real_tests.py 扫描）
  - primary dependency（starlette ASGI WebSocket）**不** mock；不引入任何 monkeypatch
  - 高价值断言：envelope.kind 与 payload 字段对齐 F23 broadcaster 实际产出
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from harness.api import app, wire_services
from harness.domain.ticket import HilOption, HilQuestion
from harness.orchestrator.bus import RunEvent


@pytest.mark.real_http
def test_f21_feature_21_real_ws_hil_channel_pushes_hil_question_envelope(tmp_path) -> None:
    """feature 21 real WS smoke —— /ws/hil 必须能推 HilQuestionOpened envelope。"""
    wire_services(app, workdir=tmp_path)
    hil_bus = app.state.hil_event_bus

    question = HilQuestion(
        id="q-f21",
        kind="single_select",
        header="Q21",
        question="What?",
        options=[HilOption(label="yes"), HilOption(label="no")],
        multi_select=False,
        allow_freeform=False,
    )

    client = TestClient(app)
    with client.websocket_connect("/ws/hil") as ws:
        hil_bus.publish_opened(ticket_id="t-f21-real-001", run_id="r-f21", question=question)
        envelope = ws.receive_json()
    assert isinstance(envelope, dict), "WebSocket 必须推送 JSON envelope dict"
    # F23 wiring._hil_broadcast emits {kind: 'hil_event', payload: ...}.
    # The HilQuestionOpened discriminator is the presence of payload.question;
    # HilAnswerAccepted carries payload.answer instead.
    assert envelope.get("kind") == "hil_event", (
        f"feature 21 期望 envelope.kind=='hil_event'（F23 broadcaster），实际 {envelope!r}"
    )
    payload = envelope.get("payload") or {}
    assert payload.get("ticket_id") == "t-f21-real-001"
    assert "question" in payload, (
        f"HilQuestionOpened envelope 必须携带 payload.question；实际 {envelope!r}"
    )


@pytest.mark.real_http
def test_f21_feature_21_real_ws_stream_channel_pushes_stream_event(tmp_path) -> None:
    """feature 21 real WS smoke —— /ws/stream/<ticket_id> 必须推 StreamEvent envelope。"""
    wire_services(app, workdir=tmp_path)
    bus = app.state.run_control_bus
    ticket_id = "t-f21-real-001"
    bus.broadcast_stream_event(
        {
            "ticket_id": ticket_id,
            "kind": "tool_use",
            "data": {"tool": "Read"},
            "ts": "2026-04-25T00:00:00Z",
        }
    )

    client = TestClient(app)
    with client.websocket_connect(f"/ws/stream/{ticket_id}") as ws:
        ws.send_json({"kind": "subscribe", "channel": f"/ws/stream/{ticket_id}"})
        envelope = ws.receive_json()
    assert isinstance(envelope, dict)
    # F23 broadcast_stream_event emits {kind: 'StreamEvent', payload: <event-dict>}.
    assert envelope.get("kind") == "StreamEvent", (
        f"feature 21 期望 envelope.kind=='StreamEvent'，实际 {envelope!r}"
    )
    payload = envelope.get("payload") or {}
    assert payload.get("ticket_id") == ticket_id


@pytest.mark.real_http
def test_f21_feature_21_real_ws_run_channel_pushes_phase_changed(tmp_path) -> None:
    """feature 21 real WS smoke —— /ws/run/<run_id> 必须推 run_phase_changed
    或 ticket_state_changed 之一（reducer 累加 cost/turns 的数据来源）。"""
    wire_services(app, workdir=tmp_path)
    bus = app.state.run_control_bus
    run_id = "r-f21-real-001"
    bus.broadcast_run_event(
        RunEvent(
            kind="run_phase_changed",
            payload={"run_id": run_id, "state": "running"},
        )
    )

    client = TestClient(app)
    with client.websocket_connect(f"/ws/run/{run_id}") as ws:
        ws.send_json({"kind": "subscribe", "channel": f"/ws/run/{run_id}"})
        envelope = ws.receive_json()
    assert isinstance(envelope, dict)
    allowed_kinds = {
        "run_phase_changed",
        "ticket_spawned",
        "ticket_state_changed",
        "run_completed",
    }
    assert envelope.get("kind") in allowed_kinds, (
        f"feature 21 期望 envelope.kind ∈ {sorted(allowed_kinds)}，实际 {envelope!r}"
    )
    payload = envelope.get("payload") or {}
    assert payload.get("run_id") == run_id
