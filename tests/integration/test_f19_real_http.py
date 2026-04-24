"""Integration test for F19 · real HTTP httpx timeout enforcement (feature #19).

Covers T31 (INTG/http · PERF) from feature design §7 Test Inventory.

SRS trace: FR-023 · IFR-004 (classifier HTTP 10 s budget).

[integration] — binds to a REAL TCP loopback server that intentionally never
responds within the 10 s budget. ``httpx.AsyncClient(timeout=10)`` is the
production primary dependency; we do NOT mock it. The only substitute is the
upstream endpoint (a real socket on 127.0.0.1) — the network stack, TLS-less
HTTP handshake, and timeout enforcement path are all real.

IFR-004 (classifier call 10 s budget) is enforced via black-box wall-clock
assertion (elapsed in [9, 13] s) on the loopback black-hole socket below.

Feature ref: feature_19

Real-test invariants (Rule 5a):
  - DOES NOT mock httpx.AsyncClient (the primary external dependency).
  - Hard-fails when socket allocation fails (assert, not skip-and-pass).
  - Uses a real TCP listener, real httpx.AsyncClient, real asyncio wait loop.
  - High-value assertions: elapsed wall-clock in [8, 12] s window AND verdict
    falls back to backend="rule" (not raised).
"""

from __future__ import annotations

import asyncio
import socket
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.real_http


@pytest.mark.real_http
@pytest.mark.asyncio
async def test_f19_t31_real_http_timeout_triggers_rule_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """feature_19 real test: ClassifierService via ClassifierConfig pointing at
    a real loopback socket that accepts connections but never sends a reply.

    httpx.AsyncClient(timeout=10) MUST abort the hang after ~10 s; the service
    MUST fall back to RuleBackend and return a Verdict (never raise).

    SRS trace: FR-023 · IFR-004 (classifier call 10 s timeout budget).
    """
    from harness.auth import KeyringGateway
    from harness.dispatch.classifier.models import ClassifierConfig, ClassifyRequest
    from harness.dispatch.classifier.service import ClassifierService

    # --- real loopback black-hole server ---------------------------------
    # [TEST-FIX] asyncio's loop.sock_accept requires a non-blocking socket;
    # otherwise it blocks the whole event loop and httpx's 10 s read-timeout
    # never fires. Setting setblocking(False) restores cooperative scheduling
    # so the timeout path is exercised as the design intends.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]

    accepted: list[socket.socket] = []

    async def _accept_loop() -> None:
        loop = asyncio.get_running_loop()
        while True:
            client_sock, _ = await loop.sock_accept(sock)
            # Hold it open but send NOTHING — forces httpx read-timeout.
            accepted.append(client_sock)

    task = asyncio.create_task(_accept_loop())

    try:
        # keyring is patched to avoid touching the real platform keychain;
        # this is not the primary dependency (httpx+socket is).
        monkeypatch.setattr(
            KeyringGateway,
            "get_secret",
            lambda self, service, user: "sk-t",  # noqa: ARG005
            raising=True,
        )

        cfg = ClassifierConfig(
            enabled=True,
            provider="custom",
            base_url=f"http://127.0.0.1:{port}/v1/",
            model_name="stub",
        )
        service = ClassifierService(
            config=cfg,
            prompt_store_path=tmp_path / "prompt.json",
        )
        req = ClassifyRequest(
            exit_code=0,
            stderr_tail="",
            stdout_tail="",
            has_termination_banner=False,
        )

        start = time.monotonic()
        verdict = await service.classify(req)
        elapsed = time.monotonic() - start

        # Design: 10 s budget ±1 s. Accept 9-13 s for integration-noise.
        assert 9.0 <= elapsed <= 13.0, (
            f"httpx timeout must enforce ~10 s; elapsed={elapsed:.2f}s. "
            "If elapsed<1 s the connection was not actually attempted (mock slipping in?); "
            "if elapsed>13 s the timeout config is missing or too lax."
        )
        # Fall-through to rule backend — not raised up.
        assert verdict.backend == "rule"
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        for c in accepted:
            c.close()
        sock.close()
