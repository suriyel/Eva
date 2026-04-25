"""F21 (feature 21) real WebSocket integration smoke (T28 / T30 wireline).

Traces To 特性 21 design §Test Inventory T28 (INTG/ws · /ws/hil) ·
          T30 (INTG/recon · IFR-007) ·
          §Interface Contract HilInboxPage / TicketStreamPage IAPI-001 consumer ·
          §Design Alignment sequenceDiagram msg `FastApiHilWs-->>HarnessWsClient: HilQuestionOpened`.

F21 是前端特性，但 design §4.6.4 表声明它消费 IAPI-001 WebSocket 频道
``/ws/hil`` / ``/ws/stream/:ticket_id`` / ``/ws/run/<run_id>``。F12 已交付 echo handler
（仅回 ``subscribe_ack``），但 F21 的 sequenceDiagram 要求服务端**主动推送** F21
所需事件 envelope —— 至少 ``HilQuestionOpened`` / ``HilAnswerAccepted`` /
``RunPhaseChanged`` / ``TicketStateChanged`` / ``StreamEvent``。

Red 阶段：F12 echo handler 仅返回 ``{kind: 'subscribe_ack', channel: ..., echo: ...}``，
F21 期望的 hub broadcast 能力尚未接入 → 三个测试都期望 envelope.kind ∈ F21-allowed
集合，**FAIL** 于 F12 echo 的 ``subscribe_ack``。

Real test convention（feature-list.json::real_test）:
  - marker @pytest.mark.real_http
  - feature reference "feature 21" 出现在 docstring + 函数名（check_real_tests.py 扫描）
  - primary dependency（starlette ASGI WebSocket）**不** mock；不引入任何 monkeypatch
  - 高价值断言：envelope.kind 必须属于 F21 design 锁定的 IAPI-001 enum，而非泛 ack
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from harness.api import app

# F21 design §6.2.4 schema-derived envelope kinds expected by HilInboxPage /
# TicketStreamPage / RunOverviewPage. Until the IAPI-001 hub真正广播，echo
# handler 只能给出 'subscribe_ack' —— Red 阶段三测试在此处 FAIL。
F21_HIL_KINDS = {"hil_question_opened", "hil_answer_accepted", "hil_ticket_closed"}
F21_STREAM_KINDS = {"stream_event"}
F21_RUN_KINDS = {
    "run_phase_changed",
    "ticket_spawned",
    "ticket_state_changed",
    "run_completed",
}


@pytest.mark.real_http
def test_f21_feature_21_real_ws_hil_channel_pushes_hil_question_envelope() -> None:
    """feature 21 real WS smoke —— /ws/hil 必须能推 ``hil_question_opened``-类 envelope。"""
    client = TestClient(app)
    with client.websocket_connect("/ws/hil") as ws:
        ws.send_json({"kind": "subscribe", "channel": "/ws/hil"})
        envelope = ws.receive_json()
    assert isinstance(envelope, dict), "WebSocket 必须推送 JSON envelope dict"
    assert (
        envelope.get("channel") == "/ws/hil"
    ), f"envelope.channel 必须为 /ws/hil，实际 {envelope!r}"
    # 高价值断言：F21 design 期望 hub 主动 broadcast HilQuestionOpened（subscribe_ack 不算）
    assert envelope.get("kind") in F21_HIL_KINDS, (
        f"feature 21 期望 envelope.kind ∈ {sorted(F21_HIL_KINDS)}，实际 "
        f"{envelope.get('kind')!r}（envelope={envelope!r}）—— Red 阶段 F12 echo "
        f"handler 仅返回 'subscribe_ack'，需 Green 阶段接入 HIL hub broadcast"
    )


@pytest.mark.real_http
def test_f21_feature_21_real_ws_stream_channel_pushes_stream_event() -> None:
    """feature 21 real WS smoke —— /ws/stream/<ticket_id> 必须推 ``stream_event``。"""
    ticket_id = "t-f21-real-001"
    client = TestClient(app)
    with client.websocket_connect(f"/ws/stream/{ticket_id}") as ws:
        ws.send_json({"kind": "subscribe", "channel": f"/ws/stream/{ticket_id}"})
        envelope = ws.receive_json()
    assert isinstance(envelope, dict)
    assert (
        envelope.get("channel") == f"/ws/stream/{ticket_id}"
    ), f"envelope.channel 必须含 path param，实际 {envelope!r}"
    assert envelope.get("kind") in F21_STREAM_KINDS, (
        f"feature 21 期望 envelope.kind ∈ {sorted(F21_STREAM_KINDS)}，实际 "
        f"{envelope.get('kind')!r}（envelope={envelope!r}）"
    )


@pytest.mark.real_http
def test_f21_feature_21_real_ws_run_channel_pushes_phase_changed() -> None:
    """feature 21 real WS smoke —— /ws/run/<run_id> 必须推 ``run_phase_changed`` 或
    ``ticket_state_changed`` 之一（reducer 累加 cost/turns 的数据来源）。"""
    run_id = "r-f21-real-001"
    client = TestClient(app)
    with client.websocket_connect(f"/ws/run/{run_id}") as ws:
        ws.send_json({"kind": "subscribe", "channel": f"/ws/run/{run_id}"})
        envelope = ws.receive_json()
    assert isinstance(envelope, dict)
    assert envelope.get("channel") == f"/ws/run/{run_id}"
    assert envelope.get("kind") in F21_RUN_KINDS, (
        f"feature 21 期望 envelope.kind ∈ {sorted(F21_RUN_KINDS)}，实际 "
        f"{envelope.get('kind')!r}（envelope={envelope!r}）—— RunOverviewPage "
        f"reducer 依赖这些 kind 累加 cost / 推 phase"
    )
