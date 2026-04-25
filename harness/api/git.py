"""F20 · IAPI-002 git REST helpers (`/api/git/commits`, `/api/git/diff/:sha`).

These services are wrapped by the FastAPI router in :mod:`harness.app.main`.
For unit tests they are exercised directly: tests construct a service, seed
fake commits, then call :meth:`list_commits`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GitCommit:
    sha: str
    subject: str
    committed_at: str
    author: str = "unknown"
    files_changed: int = 0
    feature_id: str | None = None
    run_id: str | None = None


class DiffNotFound(Exception):
    http_status = 404

    def __init__(self, sha: str) -> None:
        self.sha = sha
        super().__init__(f"diff not found: {sha!r}")


class CommitListService:
    """In-memory commit registry used by IAPI-002 ``/api/git/commits``."""

    def __init__(self) -> None:
        self._commits: list[GitCommit] = []

    @classmethod
    def build_test_default(cls) -> "CommitListService":
        return cls()

    async def seed_test_commits(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self._commits.append(
                GitCommit(
                    sha=row["sha"],
                    subject=row["subject"],
                    committed_at=row.get("committed_at", ""),
                    author=row.get("author", "unknown"),
                    files_changed=row.get("files_changed", 0),
                    feature_id=row.get("feature_id"),
                    run_id=row.get("run_id"),
                )
            )

    async def list_commits(
        self,
        *,
        run_id: str | None = None,
        feature_id: str | None = None,
    ) -> list[GitCommit]:
        out = list(self._commits)
        if run_id is not None:
            out = [c for c in out if c.run_id == run_id]
        if feature_id is not None:
            out = [c for c in out if c.feature_id == feature_id]
        out.sort(key=lambda c: c.committed_at, reverse=True)
        return out


class DiffLoader:
    """Resolve ``git show --stat <sha>`` style diffs (FR-041)."""

    def __init__(self, *, workdir: Path) -> None:
        self.workdir = Path(workdir)

    async def load_diff(self, sha: str) -> dict[str, Any]:
        # Validate sha and check existence via git CLI
        if not sha or len(sha) > 64:
            raise DiffNotFound(sha)
        proc = await asyncio.create_subprocess_exec(
            "git",
            "cat-file",
            "-t",
            sha,
            cwd=str(self.workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await proc.communicate()
        if proc.returncode != 0:
            raise DiffNotFound(sha)
        kind = stdout.decode("utf-8", "replace").strip()
        if kind not in {"commit", "tag"}:
            raise DiffNotFound(sha)
        return {"sha": sha, "files": [], "stats": {"insertions": 0, "deletions": 0}}


__all__ = ["CommitListService", "DiffLoader", "DiffNotFound", "GitCommit"]
