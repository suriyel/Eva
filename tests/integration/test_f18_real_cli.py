"""F18 · Bk-Adapter — Real CLI integration + HIL PoC tests.

Covers Test Inventory: T29 (single round-trip), T30 (20-round PoC gate).
feature_18 : real_cli marker per feature-list.json real_test.marker_pattern.
feature: 18 (Bk-Adapter — Agent Adapter & HIL Pipeline).

Layer marker:
  # [integration] — uses real `claude` CLI on PATH. Marker `@pytest.mark.real_cli`
  # makes these discoverable by check_real_tests.py without mocking the primary
  # dependency (the CLI itself).

Real-test invariants (Rule 5a):
  - DOES NOT mock claude CLI (the primary external dependency)
  - High-value assertions (pid stability, ≥2 tool_use events, success rate ≥95%)
  - Hard-fails when CLI binary is missing (assert, not skip-and-pass)
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import pytest

# Top-level dependency on existing F02 schema is OK (F02 is passing).
from harness.domain.ticket import DispatchSpec, HilAnswer

# F18 imports deferred per-test (TDD Red — modules absent).


def _isolated_spec(tmp_path):
    base = tmp_path / ".harness-workdir" / "r1"
    plugin_dir = base / ".claude" / "plugins"
    settings_path = base / ".claude" / "settings.json"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{}")
    return DispatchSpec(
        argv=["claude"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(base),
            "TERM": "dumb",
        },
        cwd=str(base),
        model=None,
        mcp_config=None,
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )


# ---------------------------------------------------------------------------
# T29 — INTG/cli — Traces To: IFR-001 · FR-008 · ATS INT-001
# ---------------------------------------------------------------------------
@pytest.mark.real_cli
@pytest.mark.asyncio
async def test_t29_real_claude_hil_round_trip(tmp_path):
    """[feature 18] Spawn real `claude` CLI → wait for AskUserQuestion → write answer → wait next event.

    Asserts (high-value, kills "no-op stub" wrong impl):
      - claude binary exists on PATH (hard-fail if not — Rule 5a forbids silent skip)
      - TicketProcess.pid stays the same across the round-trip (no respawn)
      - At least 2 tool_use events observed in the timeline (initial + post-answer)
    """
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.hil.writeback import HilWriteback
    from harness.stream.parser import JsonLinesParser

    cli = shutil.which("claude")
    assert cli, "Real-CLI test requires `claude` on PATH. Install Claude Code per env-guide §5."

    adapter = ClaudeCodeAdapter()
    spec = _isolated_spec(tmp_path)
    proc = adapter.spawn(spec)
    initial_pid = proc.pid

    # Drive parser + writeback for up to ~30s, collecting at least 2 tool_use events.
    parser = JsonLinesParser()
    tool_use_events = []
    deadline = asyncio.get_event_loop().time() + 30.0
    answered = False

    try:
        while asyncio.get_event_loop().time() < deadline and len(tool_use_events) < 2:
            chunk = await proc.byte_queue.get()
            if chunk is None:
                break
            for evt in parser.feed(chunk):
                if evt.kind == "tool_use":
                    tool_use_events.append(evt)
                    if not answered:
                        # Answer the first AskUserQuestion to trigger a second one.
                        ans = HilAnswer(
                            question_id="poc-q",
                            selected_labels=["yes"],
                            freeform_text=None,
                            answered_at="2026-04-24T00:00:00Z",
                        )
                        wb = HilWriteback(
                            worker=proc.worker,
                            audit=None,
                            ticket_repo=None,
                            ticket_id=proc.ticket_id,
                        )
                        wb.write_answer(ans)
                        answered = True
        # PID stability check (kills accidental respawn implementation)
        assert proc.pid == initial_pid, "ticket pid must NOT change during round-trip"
        assert len(tool_use_events) >= 2, f"expected ≥2 tool_use events, got {len(tool_use_events)}"
    finally:
        proc.worker.close()


# ---------------------------------------------------------------------------
# T30 — INTG/cli — Traces To: FR-013 HIL PoC gate · ATS INT-001
# ---------------------------------------------------------------------------
@pytest.mark.real_cli
@pytest.mark.asyncio
async def test_t30_hil_poc_20_round_success_rate_at_least_95_percent(tmp_path):
    """[feature 18] 20 × HIL round-trip with real `claude`; success rate must be ≥95% (≥19/20)."""
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.hil.writeback import HilWriteback
    from harness.stream.parser import JsonLinesParser

    cli = shutil.which("claude")
    assert cli, "PoC requires real `claude` CLI on PATH (env-guide §5)"

    adapter = ClaudeCodeAdapter()
    successes = 0
    failures = []

    for i in range(20):
        try:
            spec = _isolated_spec(tmp_path / f"round{i}")
            proc = adapter.spawn(spec)
            parser = JsonLinesParser()
            seen_tool_use = 0
            answered = False
            deadline = asyncio.get_event_loop().time() + 20.0
            while asyncio.get_event_loop().time() < deadline and seen_tool_use < 2:
                chunk = await proc.byte_queue.get()
                if chunk is None:
                    break
                for evt in parser.feed(chunk):
                    if evt.kind == "tool_use":
                        seen_tool_use += 1
                        if not answered:
                            ans = HilAnswer(
                                question_id=f"q-{i}",
                                selected_labels=["yes"],
                                freeform_text=None,
                                answered_at="2026-04-24T00:00:00Z",
                            )
                            HilWriteback(
                                worker=proc.worker,
                                audit=None,
                                ticket_repo=None,
                                ticket_id=proc.ticket_id,
                            ).write_answer(ans)
                            answered = True
            if seen_tool_use >= 2:
                successes += 1
            else:
                failures.append(f"round {i}: only {seen_tool_use} tool_use events")
            proc.worker.close()
        except Exception as e:  # noqa: BLE001  (PoC must record all failure modes)
            failures.append(f"round {i}: {type(e).__name__}: {e}")

    rate = successes / 20.0
    # Persist PoC report to docs/poc/ (Implementation Summary spec)
    poc_dir = Path("docs/poc")
    poc_dir.mkdir(parents=True, exist_ok=True)
    (poc_dir / "2026-04-24-hil-poc.md").write_text(
        f"# HIL PoC report\n\n- successes: {successes}/20\n- rate: {rate:.2%}\n"
        + "\n".join(f"- FAIL {f}" for f in failures)
    )
    assert (
        rate >= 0.95
    ), f"FR-013 HIL PoC gate FAIL: {successes}/20 = {rate:.0%} < 95%; failures:\n" + "\n".join(
        failures
    )
