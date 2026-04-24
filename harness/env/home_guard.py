"""F10 · HomeMtimeGuard + WorkdirScopeGuard.

HomeMtimeGuard uses ``st_mtime_ns`` rather than ``st_mtime`` because the
1 s EXT4/APFS/NTFS stat precision would hide intra-second touches — see
Design §Interface Contract rationale "纳秒级 mtime 比对".

WorkdirScopeGuard enforces FR-044: anything outside the allowed
``.harness/`` / ``.harness-workdir/`` subtrees is reported as
``unexpected_new``.
"""

from __future__ import annotations

from pathlib import Path

from .errors import HomeSnapshotError, WorkdirScopeError
from .models import HomeMtimeChange, HomeMtimeDiff, HomeMtimeSnapshot, WorkdirScopeReport


class HomeMtimeGuard:
    """Snapshot + diff ~/.claude mtime_ns (nanosecond granularity)."""

    def snapshot(
        self,
        home: Path,
        *,
        follow_symlinks: bool = False,
    ) -> HomeMtimeSnapshot:
        """Recursively stat regular files under ``home`` and capture
        mtime_ns. Returns an empty snapshot when ``home`` does not exist."""

        home = Path(home)
        entries: dict[str, int] = {}
        if not home.exists():
            return HomeMtimeSnapshot(root=home, entries=entries)
        if not home.is_dir():
            raise HomeSnapshotError(f"home is not a directory: {home}")

        try:
            for p in home.rglob("*"):
                if follow_symlinks:
                    if not p.is_file():
                        continue
                else:
                    if p.is_symlink():
                        continue
                    if not p.is_file():
                        continue
                try:
                    st = p.stat() if follow_symlinks else p.lstat()
                except OSError:
                    continue
                rel = str(p.relative_to(home))
                entries[rel] = st.st_mtime_ns
        except OSError as exc:  # pragma: no cover — platform specific
            raise HomeSnapshotError(f"snapshot failed under {home}: {exc!r}") from exc

        return HomeMtimeSnapshot(root=home, entries=entries)

    def diff_against(
        self,
        before: HomeMtimeSnapshot,
        *,
        now: HomeMtimeSnapshot | None = None,
    ) -> HomeMtimeDiff:
        """Produce a HomeMtimeDiff. When ``now`` is None, re-snapshot
        ``before.root`` on the fly."""

        current = now if now is not None else self.snapshot(Path(before.root))

        before_entries = dict(before.entries)
        after_entries = dict(current.entries)

        changed: list[HomeMtimeChange] = []
        added: list[str] = []
        removed: list[str] = []

        for rel, before_ns in before_entries.items():
            if rel not in after_entries:
                removed.append(rel)
                continue
            after_ns = after_entries[rel]
            if after_ns != before_ns:
                changed.append(HomeMtimeChange(path=rel, before_ns=before_ns, after_ns=after_ns))

        for rel in after_entries:
            if rel not in before_entries:
                added.append(rel)

        ok = not (changed or added or removed)
        untouched = sum(
            1 for rel, before_ns in before_entries.items() if after_entries.get(rel) == before_ns
        )
        return HomeMtimeDiff(
            changed_files=changed,
            added_files=sorted(added),
            removed_files=sorted(removed),
            ok=ok,
            untouched_files_count=untouched,
        )


# Allowed subdirs: anything under .harness/ or .harness-workdir/ is considered
# legitimate harness-owned scope (FR-044).
_DEFAULT_ALLOWED = frozenset({".harness", ".harness-workdir"})


class WorkdirScopeGuard:
    """Asserts FR-044: Harness must only write into ``.harness*`` subdirs."""

    def assert_scope(
        self,
        workdir: Path,
        *,
        before: set[str],
        after: set[str] | None = None,
        allowed_subdirs: frozenset[str] = _DEFAULT_ALLOWED,
    ) -> WorkdirScopeReport:
        workdir = Path(workdir)
        if not workdir.exists() or not workdir.is_dir():
            raise WorkdirScopeError(f"workdir not found: {workdir}")

        if after is None:
            try:
                after = {str(p.relative_to(workdir)) for p in workdir.rglob("*") if p.is_file()}
            except OSError as exc:  # pragma: no cover
                raise WorkdirScopeError(f"scan failed under {workdir}: {exc!r}") from exc

        def _is_allowed(relpath: str) -> bool:
            # normalise slashes so windows-style separators don't slip through
            norm = relpath.replace("\\", "/")
            for allowed in allowed_subdirs:
                if norm == allowed or norm.startswith(allowed + "/"):
                    return True
            return False

        unexpected = sorted(p for p in (after - before) if not _is_allowed(p))
        return WorkdirScopeReport(
            unexpected_new=unexpected,
            ok=(unexpected == []),
        )


__all__ = ["HomeMtimeGuard", "WorkdirScopeGuard"]
