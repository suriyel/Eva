"""Unit tests for F02 · AuditWriter (IAPI-009 Provider).

Covers Test Inventory rows L (disk-full IoError + structlog warning) and
Q (10-way concurrent append maintains line-atomicity).

[unit] — uses tmp_path fixture; the disk-full case monkeypatches `open` to
force ENOSPC. Neither test mocks the AuditWriter itself — only its OS
boundary. The concurrent test drives real filesystem writes.
Feature ref: feature_2
"""

from __future__ import annotations

import asyncio
import builtins
import errno
import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Row L — FUNC/error + ATS Err-E — disk full raises IoError, logs one error
# ---------------------------------------------------------------------------
async def test_append_disk_full_raises_ioerror_and_logs_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monkeypatch builtins.open to raise OSError(ENOSPC) on the audit file.

    Expected: AuditWriter.append raises IoError (DAO-level wrapper, NOT raw
    OSError — so callers can catch a stable exception type). structlog.error
    must be invoked at least once with the failure.
    """
    from harness.domain.ticket import AuditEvent, TicketState
    from harness.persistence.audit import AuditWriter
    from harness.persistence.errors import IoError

    # Capture structlog.error calls by intercepting the module-level logger.
    logged_errors: list[tuple[tuple, dict]] = []

    import structlog

    class _CapLogger:
        def error(self, *args, **kwargs) -> None:
            logged_errors.append((args, kwargs))

        # Allow other methods on the captured logger to no-op (debug/info/etc).
        def __getattr__(self, name):
            return lambda *a, **k: None

    def fake_get_logger(*a, **k):
        return _CapLogger()

    monkeypatch.setattr(structlog, "get_logger", fake_get_logger)

    # Monkeypatch open to ENOSPC ONLY when the file path looks like an audit jsonl.
    real_open = builtins.open

    def enospc_open(file, *args, **kwargs):
        path_str = str(file)
        if path_str.endswith(".jsonl") and "/audit/" in path_str.replace("\\", "/"):
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", enospc_open)

    # Also patch os.open in case AuditWriter uses O_APPEND low-level API.
    import os

    real_os_open = os.open

    def enospc_os_open(path, flags, mode=0o777, *a, **k):
        path_str = str(path)
        if path_str.endswith(".jsonl") and "/audit/" in path_str.replace("\\", "/"):
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_os_open(path, flags, mode, *a, **k)

    monkeypatch.setattr(os, "open", enospc_os_open)

    audit_dir = tmp_path / ".harness" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    writer = AuditWriter(audit_dir)
    event = AuditEvent(
        ts="2026-04-21T10:00:00.000000+00:00",
        ticket_id="t-L-1",
        run_id="run-L-001",
        event_type="state_transition",
        state_from=TicketState.PENDING,
        state_to=TicketState.RUNNING,
    )

    with pytest.raises(IoError):
        await writer.append(event)

    assert (
        len(logged_errors) >= 1
    ), "structlog.error must be called at least once on ENOSPC (ATS Err-E degradation)"


# ---------------------------------------------------------------------------
# Row Q — BNDRY/edge — 10 concurrent appends produce exactly 10 valid JSON lines
# ---------------------------------------------------------------------------
async def test_concurrent_append_produces_ten_valid_json_lines(tmp_path: Path) -> None:
    """asyncio.gather 10 append calls with unique ticket_ids → file has exactly
    10 lines, each line parses to a JSON object with the matching ticket_id.

    A buggy impl without a file-level asyncio.Lock would interleave writes and
    corrupt JSON. This test fails under that bug.
    """
    from harness.domain.ticket import AuditEvent, TicketState
    from harness.persistence.audit import AuditWriter

    run_id = "run-Q-001"
    audit_dir = tmp_path / ".harness" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    writer = AuditWriter(audit_dir)

    events = [
        AuditEvent(
            ts=f"2026-04-21T10:00:{i:02d}.000000+00:00",
            ticket_id=f"t-Q-{i:02d}",
            run_id=run_id,
            event_type="state_transition",
            state_from=TicketState.PENDING,
            state_to=TicketState.RUNNING,
        )
        for i in range(10)
    ]

    await asyncio.gather(*(writer.append(e) for e in events))
    await writer.close()

    jsonl_path = audit_dir / f"{run_id}.jsonl"
    raw = jsonl_path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    assert len(lines) == 10, f"expected 10 lines, got {len(lines)}"

    seen_ids: set[str] = set()
    for ln in lines:
        record = json.loads(ln)  # Must parse cleanly — no truncation / interleave.
        assert record["run_id"] == run_id
        assert record["event_type"] == "state_transition"
        seen_ids.add(record["ticket_id"])
    assert seen_ids == {
        f"t-Q-{i:02d}" for i in range(10)
    }, f"missing ids in concurrent append output: {seen_ids}"


async def test_append_trailing_newline_and_utf8_encoding(tmp_path: Path) -> None:
    """Single append must end with `\\n`; file is utf-8 (no BOM); Chinese payload preserved.

    Rule 4 guard: a buggy impl that uses repr() or drops the newline fails here.
    """
    from harness.domain.ticket import AuditEvent, TicketState
    from harness.persistence.audit import AuditWriter

    audit_dir = tmp_path / ".harness" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    writer = AuditWriter(audit_dir)

    event = AuditEvent(
        ts="2026-04-21T10:00:00.000000+00:00",
        ticket_id="t-utf8",
        run_id="run-utf8",
        event_type="hil_captured",
        state_from=TicketState.RUNNING,
        state_to=TicketState.HIL_WAITING,
        payload={"question": "需要用户确认"},
    )
    await writer.append(event)
    await writer.close()

    jsonl_path = audit_dir / "run-utf8.jsonl"
    raw = jsonl_path.read_bytes()
    # No BOM.
    assert not raw.startswith(b"\xef\xbb\xbf"), "audit file must not have UTF-8 BOM"
    # Ends with a single newline.
    assert raw.endswith(b"\n"), "audit line must terminate with '\\n'"
    # Chinese characters preserved verbatim as UTF-8 (ensure_ascii=False).
    assert "需要用户确认" in raw.decode("utf-8"), "Chinese payload must round-trip"
