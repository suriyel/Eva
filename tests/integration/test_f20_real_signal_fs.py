"""Integration test for F20 · real watchdog observer + filesystem (T33).

[integration] — uses REAL watchdog Observer + REAL tmp filesystem.

Feature ref: feature_20

Traces To:
  T33 → FR-048 + IAPI-012 real watchdog observer
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


pytestmark = [pytest.mark.real_fs, pytest.mark.asyncio]


@pytest.mark.real_fs
async def test_t33_real_watcher_yields_5_distinct_signal_kinds(tmp_path: Path) -> None:
    """T33 INTG/fs (feature_20): 5 different signal files created → 5 SignalEvents with distinct `kind` fields."""
    from harness.orchestrator.signal_watcher import SignalEvent, SignalFileWatcher

    class NullBus:
        def broadcast_signal(self, _e: SignalEvent) -> None:  # noqa: D401
            return None

    docs_plans = tmp_path / "docs" / "plans"
    docs_plans.mkdir(parents=True)
    docs_rules = tmp_path / "docs" / "rules"
    docs_rules.mkdir(parents=True)

    watcher = SignalFileWatcher(workdir=tmp_path, control_bus=NullBus())
    watcher.start(workdir=tmp_path)

    received_kinds: list[str] = []

    async def _consumer() -> None:
        async with asyncio.timeout(8.0):
            async for ev in watcher.events():
                received_kinds.append(ev.kind)
                if len(received_kinds) >= 5:
                    return

    async def _writer() -> None:
        await asyncio.sleep(0.1)
        (tmp_path / "bugfix-request.json").write_text("{}")
        await asyncio.sleep(0.4)
        (tmp_path / "increment-request.json").write_text("{}")
        await asyncio.sleep(0.4)
        (tmp_path / "feature-list.json").write_text("{}")
        await asyncio.sleep(0.4)
        (docs_plans / "2026-04-21-srs.md").write_text("# srs")
        await asyncio.sleep(0.4)
        (docs_rules / "rules.md").write_text("# rules")

    try:
        writer = asyncio.create_task(_writer())
        try:
            await asyncio.wait_for(_consumer(), timeout=8.0)
        except asyncio.TimeoutError:
            pass
        await writer
    finally:
        await watcher.stop()

    # Must observe at least 5 distinct kinds
    distinct = set(received_kinds)
    assert (
        len(distinct) >= 5
    ), f"expected ≥5 distinct signal kinds; got {distinct} from received={received_kinds}"
    # Validate kind name set
    assert distinct <= {
        "bugfix_request",
        "increment_request",
        "feature_list_changed",
        "srs_changed",
        "design_changed",
        "ats_changed",
        "ucd_changed",
        "rules_changed",
    }, f"unexpected kind values: {distinct}"
