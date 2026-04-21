"""DAO-layer exception types (F02).

Callers (F03-F11) rely on a stable set of exceptions rather than the
lower-level :class:`sqlite3.IntegrityError` / :class:`OSError` / etc.
"""

from __future__ import annotations


class DaoError(Exception):
    """SQLite / aiosqlite DAO failure surface.

    Wraps integrity errors, IO errors and deserialisation failures so
    consumers can ``except DaoError`` without knowing the underlying driver.
    """


class IoError(Exception):
    """JSONL / filesystem write failure surface for :class:`AuditWriter`.

    Distinct from :class:`DaoError` so that callers (F04/F09) can decide
    whether an audit failure should degrade silently vs. propagate.
    """


__all__ = ["DaoError", "IoError"]
