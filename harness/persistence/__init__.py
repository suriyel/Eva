"""Harness persistence layer (F02 · feature #2).

Exposes the DAO surface consumed by F03–F11:

- ``Schema`` + ``resolve_db_path``: startup idempotent DDL + path resolution
- ``TicketRepository``: IAPI-011 provider (save/get/list_by_run/list_unfinished/
  mark_interrupted)
- ``RunRepository``: internal helper for runs table
- ``AuditWriter``: IAPI-009 provider (append/close) writing
  ``<workdir>/.harness/audit/<run_id>.jsonl``
- ``RecoveryScanner``: NFR-005 crash-restart scan
- ``DaoError`` / ``IoError``: DAO-layer wrappers for lower-level failures
"""

from __future__ import annotations

from harness.persistence.audit import AuditWriter
from harness.persistence.errors import DaoError, IoError
from harness.persistence.recovery import RecoveryScanner
from harness.persistence.runs import RunRepository
from harness.persistence.schema import Schema, resolve_db_path
from harness.persistence.tickets import TicketRepository

__all__ = [
    "AuditWriter",
    "DaoError",
    "IoError",
    "RecoveryScanner",
    "RunRepository",
    "Schema",
    "TicketRepository",
    "resolve_db_path",
]
