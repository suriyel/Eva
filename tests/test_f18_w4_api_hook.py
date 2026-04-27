"""F18 Wave 4 · POST /api/hook/event router tests (IAPI-020).

Test Inventory: T15, T16, T17.
SRS: IFR-001 AC-w4-2 (415/422 rejection paths) + Design seq msg#8.

Layer marker:
  # [unit] — uses FastAPI TestClient (in-process); does not spawn real CLI.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest


_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "hook_event_askuserquestion_v2_1_119.json"
)


def _load_fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_test_app():
    """Mount the hook router into a minimal FastAPI app with stub state."""
    from fastapi import FastAPI

    from harness.api.hook import router as hook_router

    app = FastAPI()

    # Minimal app.state shims: adapter_registry + ticket broadcaster.
    class _StubAdapter:
        def __init__(self):
            from harness.hil.hook_mapper import HookEventMapper

            self._mapper = HookEventMapper()
            self.calls = []

        def map_hook_event(self, payload):
            self.calls.append(payload)
            return self._mapper.parse(
                payload.model_dump() if hasattr(payload, "model_dump") else payload
            )

    class _StubBus:
        def __init__(self):
            self.opened_events = []
            self.tool_use_id_queue = []

        def publish_opened(self, ticket_id, run_id, question):
            self.opened_events.append((ticket_id, run_id, question))

    class _StubBroadcaster:
        def __init__(self):
            self.events = []

        def publish(self, event):
            self.events.append(event)

    app.state.adapter_registry = {"claude": _StubAdapter()}
    app.state.hil_event_bus = _StubBus()
    app.state.ticket_stream_broadcaster = _StubBroadcaster()
    # Default ticket id binding (router must look up by session_id or similar).
    app.state.ticket_id_for_session = {
        _load_fixture()["session_id"]: "ticket-001",
    }
    app.state.run_id_for_session = {_load_fixture()["session_id"]: "run-001"}

    app.include_router(hook_router)
    return app


# ---------------------------------------------------------------------------
# T15 — FUNC/happy — Traces To: IAPI-020 happy + Design seq msg#8
# ---------------------------------------------------------------------------
def test_t15_post_hook_event_happy_fan_out_returns_200_and_dispatches():
    from fastapi.testclient import TestClient

    app = _build_test_app()
    client = TestClient(app)

    resp = client.post(
        "/api/hook/event",
        content=json.dumps(_load_fixture()),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200, f"got {resp.status_code} body={resp.text}"
    body = resp.json()
    assert body == {"accepted": True}, f"unexpected body: {body}"

    # adapter.map_hook_event must have been called
    adapter = app.state.adapter_registry["claude"]
    assert len(adapter.calls) == 1, "adapter.map_hook_event was not invoked"

    # HilEventBus.publish_opened must have fired exactly once for AskUserQuestion
    bus = app.state.hil_event_bus
    assert len(bus.opened_events) == 1, f"opened_events={bus.opened_events!r}"

    # broadcaster received a TicketStreamEvent kind=tool_use
    bcast = app.state.ticket_stream_broadcaster
    assert len(bcast.events) == 1, f"broadcaster events: {bcast.events!r}"
    ev = bcast.events[0]
    kind = getattr(ev, "kind", None) or (
        ev.get("kind") if isinstance(ev, dict) else None
    )
    assert kind == "tool_use", f"expected tool_use; got {kind!r}"


# ---------------------------------------------------------------------------
# T16 — FUNC/error — IAPI-020 415 (wrong content-type)
# ---------------------------------------------------------------------------
def test_t16_post_hook_event_non_json_content_type_returns_415():
    from fastapi.testclient import TestClient

    app = _build_test_app()
    client = TestClient(app)

    resp = client.post(
        "/api/hook/event",
        content=json.dumps(_load_fixture()),
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 415, f"expected 415, got {resp.status_code}"
    # Adapter must NOT have been called → ticket not stuck on bad request
    adapter = app.state.adapter_registry["claude"]
    assert adapter.calls == [], "adapter must not be invoked on 415"


# ---------------------------------------------------------------------------
# T17 — FUNC/error — IAPI-020 422 (schema mismatch)
# ---------------------------------------------------------------------------
def test_t17_post_hook_event_missing_required_fields_returns_422():
    from fastapi.testclient import TestClient

    app = _build_test_app()
    client = TestClient(app)

    resp = client.post(
        "/api/hook/event",
        content=json.dumps({"foo": "bar"}),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 422, f"expected 422, got {resp.status_code}"
    # The pydantic error should reference at least one of the required fields.
    body = resp.json()
    body_text = json.dumps(body)
    # At least one of the four required top-level fields must show up in the error
    assert any(
        f in body_text
        for f in ("session_id", "hook_event_name", "cwd", "transcript_path")
    ), f"422 body did not list required fields: {body_text}"
