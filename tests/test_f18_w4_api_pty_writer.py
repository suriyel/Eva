"""F18 Wave 4 · POST /api/pty/write router tests (IAPI-021).

Test Inventory: T18, T19, T20.
SRS: FR-052 + Design seq msg#15.

Layer marker:
  # [unit] — uses FastAPI TestClient + fake PtyWorker; no real PTY.
"""

from __future__ import annotations

import base64
import json

import pytest


class _FakePty:
    def __init__(self):
        self.written: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        if self.closed:
            from harness.pty.errors import PtyClosedError

            raise PtyClosedError("pty already closed")
        self.written.append(data)


class _FakeTicket:
    def __init__(self, ticket_id: str, state: str, worker: _FakePty):
        self.ticket_id = ticket_id
        self.state = state
        self.worker = worker


class _FakeTicketRepo:
    def __init__(self):
        self.tickets: dict[str, _FakeTicket] = {}

    def get(self, ticket_id: str):
        return self.tickets.get(ticket_id)


def _build_app(state="hil_waiting"):
    from fastapi import FastAPI

    from harness.api.pty_writer import router as pty_router

    app = FastAPI()
    repo = _FakeTicketRepo()
    pty = _FakePty()
    repo.tickets["t-1"] = _FakeTicket("t-1", state, pty)
    app.state.ticket_repo = repo
    app.include_router(pty_router)
    return app, repo, pty


# ---------------------------------------------------------------------------
# T18 — FUNC/happy — Traces To: IAPI-021 happy + Design seq msg#15
# ---------------------------------------------------------------------------
def test_t18_post_pty_write_happy_writes_decoded_bytes():
    from fastapi.testclient import TestClient

    app, repo, pty = _build_app(state="hil_waiting")
    client = TestClient(app)

    payload_b64 = base64.b64encode(b"1\r").decode("ascii")
    resp = client.post(
        "/api/pty/write",
        json={"ticket_id": "t-1", "payload": payload_b64},
    )
    assert resp.status_code == 200, f"got {resp.status_code} body={resp.text}"
    assert resp.json() == {"written_bytes": 2}
    assert pty.written == [b"1\r"], f"PtyWorker received {pty.written!r}"


# ---------------------------------------------------------------------------
# T19 — FUNC/error — 400 ticket-not-running (state == completed)
# ---------------------------------------------------------------------------
def test_t19_post_pty_write_completed_ticket_returns_400_ticket_not_running():
    from fastapi.testclient import TestClient

    app, repo, pty = _build_app(state="completed")
    client = TestClient(app)

    payload_b64 = base64.b64encode(b"1\r").decode("ascii")
    resp = client.post(
        "/api/pty/write",
        json={"ticket_id": "t-1", "payload": payload_b64},
    )
    assert resp.status_code == 400, f"expected 400; got {resp.status_code}"
    body = resp.json()
    body_text = json.dumps(body)
    assert "ticket-not-running" in body_text, f"expected error_code marker, got {body_text}"
    # Must not have written anything
    assert pty.written == []


# ---------------------------------------------------------------------------
# T20 — FUNC/error — 404 ticket-not-found / 400 b64-decode-error
# ---------------------------------------------------------------------------
def test_t20a_post_pty_write_unknown_ticket_returns_404():
    from fastapi.testclient import TestClient

    app, repo, pty = _build_app()
    client = TestClient(app)

    payload_b64 = base64.b64encode(b"1\r").decode("ascii")
    resp = client.post(
        "/api/pty/write",
        json={"ticket_id": "missing", "payload": payload_b64},
    )
    assert resp.status_code == 404, f"expected 404; got {resp.status_code}"


def test_t20b_post_pty_write_invalid_base64_returns_400_b64_decode_error():
    from fastapi.testclient import TestClient

    app, repo, pty = _build_app(state="hil_waiting")
    client = TestClient(app)

    resp = client.post(
        "/api/pty/write",
        json={"ticket_id": "t-1", "payload": "!!!not-base64!!!"},
    )
    assert resp.status_code == 400, f"expected 400; got {resp.status_code}"
    body_text = json.dumps(resp.json())
    assert "b64-decode-error" in body_text, f"expected error_code marker, got {body_text}"
    assert pty.written == []
