"""F20 · SignalFileWatcher unit tests (T32/T34).

[unit] — uses watchdog real Observer on tmp_path (lightweight, no network).
T33 (multi-signal-kind real fs) lives in tests/integration/test_f20_real_signal_fs.py.

Feature ref: feature_20

Traces To:
  T32 → FR-048 + Interface Contract `SignalFileWatcher.events`
  T34 → FR-048 debounce + Boundary `SignalFileWatcher.debounce_ms`
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


# ---- T32 -------------------------------------------------------------------
async def test_t32_watcher_yields_bugfix_request_within_2s(tmp_path: Path) -> None:
    """T32 FUNC/happy: external write of bugfix-request.json → events() yields SignalEvent within 2s; broadcast_signal called."""
    from harness.orchestrator.signal_watcher import SignalEvent, SignalFileWatcher

    broadcasted: list[SignalEvent] = []

    class FakeBus:
        def broadcast_signal(self, event: SignalEvent) -> None:
            broadcasted.append(event)

    watcher = SignalFileWatcher(workdir=tmp_path, control_bus=FakeBus())
    watcher.start(workdir=tmp_path)

    try:
        # Write the file from the outside
        target = tmp_path / "bugfix-request.json"

        async def _writer() -> None:
            await asyncio.sleep(0.1)
            target.write_text("{}")

        loop_task = asyncio.create_task(_writer())

        # Drain events until target arrives or 2s budget exhausted
        evt: SignalEvent | None = None
        async with asyncio.timeout(2.0):
            async for e in watcher.events():
                if e.kind == "bugfix_request":
                    evt = e
                    break

        await loop_task
        assert evt is not None, "FR-048: no bugfix_request event yielded within 2s"
        assert Path(evt.path).name == "bugfix-request.json"
        # broadcast also fired
        assert any(
            b.kind == "bugfix_request" for b in broadcasted
        ), "broadcast_signal must be invoked alongside events()"
    finally:
        await watcher.stop()


# ---- T34 -------------------------------------------------------------------
async def test_t34_watcher_debounces_rapid_writes(tmp_path: Path) -> None:
    """T34 BNDRY/edge: 3 writes within debounce window → only 1 event yielded."""
    from harness.orchestrator.signal_watcher import SignalFileWatcher

    class NullBus:
        def broadcast_signal(self, _e: object) -> None:  # noqa: D401
            return None

    watcher = SignalFileWatcher(workdir=tmp_path, control_bus=NullBus(), debounce_ms=200)
    watcher.start(workdir=tmp_path)
    target = tmp_path / "bugfix-request.json"

    received_kinds: list[str] = []

    async def _consumer() -> None:
        async with asyncio.timeout(1.5):
            async for e in watcher.events():
                received_kinds.append(e.kind)
                if len(received_kinds) >= 2:
                    return  # bail early if extra events seen

    async def _flooder() -> None:
        await asyncio.sleep(0.05)
        for _ in range(3):
            target.write_text("{}")
            await asyncio.sleep(0.03)  # all within 200ms debounce window

    try:
        flood = asyncio.create_task(_flooder())
        try:
            await asyncio.wait_for(_consumer(), timeout=1.5)
        except asyncio.TimeoutError:
            pass
        await flood
    finally:
        await watcher.stop()

    bugfix_events = [k for k in received_kinds if k == "bugfix_request"]
    assert (
        len(bugfix_events) == 1
    ), f"FR-048 debounce: expected exactly 1 event for 3 rapid writes; got {len(bugfix_events)}"
