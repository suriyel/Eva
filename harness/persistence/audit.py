"""AuditWriter (F02 · IAPI-009 · Design §4.2 / §5.6).

Write semantics (per Interface Contract + Impl Summary decision 4):

- one ``AuditEvent`` per call → ``<audit_dir>/<run_id>.jsonl``
- single ``os.open(O_APPEND|O_WRONLY|O_CREAT)`` + ``os.write`` per append
- bytes ``json.dumps(event, ensure_ascii=False).encode('utf-8') + b'\\n'``
- per-file asyncio.Lock to serialise concurrent appends (POSIX O_APPEND is
  atomic for writes < PIPE_BUF; the lock guarantees safety at arbitrary size)
- ``fsync`` after each write (default ``fsync=True``)
- ENOSPC / permission errors are logged via ``structlog.error`` and
  re-raised as :class:`IoError` (ATS Err-E degradation)
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import structlog

from harness.domain.ticket import AuditEvent
from harness.persistence.errors import IoError


class AuditWriter:
    """Append-only JSONL writer for audit events (IAPI-009)."""

    def __init__(self, audit_dir: Path, *, fsync: bool = True) -> None:
        self._audit_dir = Path(audit_dir)
        self._fsync_default = fsync
        # One asyncio.Lock per run_id file path; file handles are short-lived
        # (opened per-append with O_APPEND) — only the lock persists.
        self._locks: dict[str, asyncio.Lock] = {}
        self._logger = structlog.get_logger("harness.persistence.audit")

    def _get_lock(self, run_id: str) -> asyncio.Lock:
        lock = self._locks.get(run_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[run_id] = lock
        return lock

    async def append(self, event: AuditEvent, *, fsync: bool | None = None) -> None:
        """Append a single ``AuditEvent`` line to ``<run_id>.jsonl``.

        Raises :class:`IoError` on OS-level IO failures (disk full, permission,
        etc.); emits a ``structlog.error`` before raising so callers see the
        degradation in logs.
        """

        do_fsync = self._fsync_default if fsync is None else fsync
        target = self._audit_dir / f"{event.run_id}.jsonl"

        # ensure_ascii=False preserves Chinese / CJK payloads verbatim.
        payload_bytes = (
            json.dumps(
                event.model_dump(mode="json", exclude_none=False),
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
        )

        lock = self._get_lock(event.run_id)
        async with lock:
            try:
                # Ensure parent directory exists (no-op if already present).
                self._audit_dir.mkdir(parents=True, exist_ok=True)

                fd = os.open(
                    str(target),
                    os.O_APPEND | os.O_WRONLY | os.O_CREAT,
                    0o644,
                )
                try:
                    remaining = payload_bytes
                    while remaining:
                        n = os.write(fd, remaining)
                        if n <= 0:  # pragma: no cover — defensive.
                            raise OSError("os.write returned 0 bytes")
                        remaining = remaining[n:]
                    if do_fsync:
                        os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError as exc:
                self._logger.error(
                    "audit_append_failed",
                    run_id=event.run_id,
                    ticket_id=event.ticket_id,
                    error=repr(exc),
                )
                raise IoError(f"audit append failed: {exc!r}") from exc

    def append_raw(
        self,
        *,
        run_id: str,
        kind: str,
        payload: dict[str, object] | None = None,
        ts: str | None = None,
    ) -> None:
        """Synchronous append of an arbitrary event (F10 · env.setup /
        env.teardown / skills.install events).

        Bypasses the strict :class:`AuditEvent` model because F10 events do
        not carry a ``ticket_id`` nor a state transition. Writes one JSON
        line with keys ``{ts, kind, run_id, payload}`` to
        ``<audit_dir>/<run_id>.jsonl``.
        """

        if ts is None:
            from datetime import datetime, timezone

            ts = datetime.now(timezone.utc).isoformat()

        record = {
            "ts": ts,
            "kind": kind,
            "run_id": run_id,
            "payload": payload or {},
        }
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")

        target = self._audit_dir / f"{run_id}.jsonl"
        try:
            self._audit_dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(
                str(target),
                os.O_APPEND | os.O_WRONLY | os.O_CREAT,
                0o644,
            )
            try:
                remaining = line
                while remaining:
                    n = os.write(fd, remaining)
                    if n <= 0:  # pragma: no cover
                        raise OSError("os.write returned 0 bytes")
                    remaining = remaining[n:]
                if self._fsync_default:
                    os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as exc:
            self._logger.error(
                "audit_append_raw_failed",
                run_id=run_id,
                kind=kind,
                error=repr(exc),
            )
            raise IoError(f"audit append_raw failed: {exc!r}") from exc

    async def close(self) -> None:
        """Release any retained per-run lock state (handles are per-call)."""

        self._locks.clear()


__all__ = ["AuditWriter"]
