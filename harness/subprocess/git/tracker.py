"""F20 · GitTracker (IAPI-013 Provider).

Wraps ``git rev-parse HEAD`` + ``git log --oneline`` as asyncio subprocesses.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GitCommit:
    sha: str
    subject: str
    author: str = "unknown"
    committed_at: str = ""
    files_changed: int = 0
    feature_id: str | None = None
    run_id: str | None = None


@dataclass
class GitContext:
    ticket_id: str
    head_before: str | None = None
    head_after: str | None = None
    commits: list[GitCommit] = field(default_factory=list)


class GitError(Exception):
    """Raised when ``git`` returns a non-zero exit (e.g. not_a_repo)."""

    def __init__(self, *, code: str, exit_code: int, stderr: str = "") -> None:
        self.code = code
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"git {code} (exit={exit_code}): {stderr.strip()[:200]}")


async def _run_git(args: list[str], cwd: Path) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (proc.returncode or 0), stdout, stderr


class GitTracker:
    """Begin/end ticket-level git history tracking."""

    def __init__(self) -> None:
        self._snapshots: dict[str, GitContext] = {}

    async def head_sha(self, *, workdir: Path) -> str:
        rc, out, err = await _run_git(["rev-parse", "HEAD"], workdir)
        if rc != 0:
            raise GitError(code="not_a_repo", exit_code=rc, stderr=err.decode("utf-8", "replace"))
        return out.decode("utf-8", "replace").strip()

    async def begin(self, *, ticket_id: str, workdir: Path) -> GitContext:
        sha = await self.head_sha(workdir=workdir)
        ctx = GitContext(ticket_id=ticket_id, head_before=sha)
        self._snapshots[ticket_id] = ctx
        return ctx

    async def end(self, *, ticket_id: str, workdir: Path) -> GitContext:
        ctx = self._snapshots.get(ticket_id) or GitContext(ticket_id=ticket_id)
        head_after = await self.head_sha(workdir=workdir)
        ctx.head_after = head_after
        if ctx.head_before and head_after and head_after != ctx.head_before:
            commits = await self.log_oneline(
                workdir=workdir, since=ctx.head_before, until=head_after
            )
            ctx.commits = commits
        self._snapshots[ticket_id] = ctx
        return ctx

    async def log_oneline(
        self,
        *,
        workdir: Path,
        since: str | None = None,
        until: str | None = None,
    ) -> list[GitCommit]:
        # ``git log --pretty=format:%H<sep>%s<sep>%an<sep>%aI`` for richer fields
        sep = "\x1f"
        fmt = sep.join(["%H", "%s", "%an", "%aI"])
        if since and until:
            rev = f"{since}..{until}"
        elif since:
            rev = f"{since}..HEAD"
        else:
            rev = "HEAD"
        rc, out, err = await _run_git(["log", f"--pretty=format:{fmt}", rev], workdir)
        if rc != 0:
            raise GitError(code="log_failed", exit_code=rc, stderr=err.decode("utf-8", "replace"))
        text = out.decode("utf-8", "replace")
        commits: list[GitCommit] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            parts = line.split(sep)
            if len(parts) < 4:
                continue
            sha, subject, author, committed_at = parts[0], parts[1], parts[2], parts[3]
            commits.append(
                GitCommit(
                    sha=sha,
                    subject=subject,
                    author=author,
                    committed_at=committed_at,
                )
            )
        return commits


__all__ = ["GitCommit", "GitContext", "GitError", "GitTracker"]
