"""F20 · SignalFileWatcher (IAPI-012 Provider).

Watches a workdir for the small set of signal files that drive Harness's main
loop (bugfix-request.json / increment-request.json / feature-list.json /
docs/plans/*-{srs,design,ats,ucd}.md / docs/rules/*.md). Yields
:class:`SignalEvent` instances via :meth:`events` (async iterator) and pushes
the same events to an injected ``RunControlBus`` for WebSocket broadcasting.

Backed by the :mod:`watchdog` PyPI package as prescribed by Design §6 — uses
``Observer + PatternMatchingEventHandler`` with a 200 ms debounce so editor
atomic-write cycles do not produce duplicate events. Cross-platform notify
backends (inotify / FSEvents / ReadDirectoryChangesW) are auto-selected by
watchdog.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import AsyncIterator, Literal, Protocol, cast

from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from harness.orchestrator.schemas import SignalEvent


class _ControlBus(Protocol):
    def broadcast_signal(self, event: SignalEvent) -> None: ...


# docs/plans/*-{srs,design,ats,ucd}.md → SignalEvent.kind
_DOCS_PLANS_PATTERNS: dict[str, str] = {
    "srs": "srs_changed",
    "design": "design_changed",
    "ats": "ats_changed",
    "ucd": "ucd_changed",
}

# Top-level signal file basenames → SignalEvent.kind
_TOP_LEVEL_KINDS: dict[str, str] = {
    "bugfix-request.json": "bugfix_request",
    "increment-request.json": "increment_request",
    "feature-list.json": "feature_list_changed",
}


def _classify_path(workdir: Path, raw_path: str) -> str | None:
    """Map a filesystem event path to a :class:`SignalEvent.kind` value."""
    try:
        path = Path(raw_path)
        if not path.is_absolute():
            path = (workdir / path).resolve()
    except OSError:
        return None

    name = path.name
    if name in _TOP_LEVEL_KINDS and path.parent == workdir:
        return _TOP_LEVEL_KINDS[name]

    plans_dir = workdir / "docs" / "plans"
    rules_dir = workdir / "docs" / "rules"
    try:
        if path.suffix == ".md" and path.parent == plans_dir:
            stem = path.stem
            for marker, kind in _DOCS_PLANS_PATTERNS.items():
                if stem.endswith(f"-{marker}"):
                    return kind
        if path.suffix == ".md" and path.parent == rules_dir:
            return "rules_changed"
    except OSError:
        return None
    return None


class _SignalEventHandler(PatternMatchingEventHandler):
    """watchdog handler that funnels matching FS events into the watcher queue."""

    def __init__(self, watcher: SignalFileWatcher) -> None:
        super().__init__(
            patterns=[
                "*/bugfix-request.json",
                "*/increment-request.json",
                "*/feature-list.json",
                "*/docs/plans/*-srs.md",
                "*/docs/plans/*-design.md",
                "*/docs/plans/*-ats.md",
                "*/docs/plans/*-ucd.md",
                "*/docs/rules/*.md",
            ],
            ignore_directories=True,
            case_sensitive=True,
        )
        self._watcher = watcher

    # watchdog dispatches create / modify / move events; treat all as a
    # logical "this signal file changed" notification.
    def on_created(self, event: FileSystemEvent) -> None:
        self._watcher._enqueue(_decode_path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        self._watcher._enqueue(_decode_path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        # Both source and destination might match patterns.
        dest = getattr(event, "dest_path", None)
        if dest:
            self._watcher._enqueue(_decode_path(dest))
        else:
            self._watcher._enqueue(_decode_path(event.src_path))


def _decode_path(raw: str | bytes) -> str:
    """Coerce watchdog's ``src_path`` (str | bytes) into a plain ``str``."""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return raw


class SignalFileWatcher:
    """Watch the workdir for signal files; emit :class:`SignalEvent`."""

    def __init__(
        self,
        *,
        workdir: Path,
        control_bus: _ControlBus,
        debounce_ms: int = 200,
    ) -> None:
        self._workdir = Path(workdir).resolve()
        self._bus = control_bus
        # Per Boundary table: debounce_ms ∈ [50, 1000]; clamp out-of-range.
        if debounce_ms < 50:
            debounce_ms = 50
        elif debounce_ms > 1000:
            debounce_ms = 1000
        self._debounce_ms = debounce_ms
        self._queue: asyncio.Queue[SignalEvent] = asyncio.Queue()
        self._observer: BaseObserver | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        # Per-kind debounce bookkeeping.
        self._last_emit: dict[str, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def start(self, *, workdir: Path) -> None:
        """Start the watchdog Observer; idempotent."""
        self._workdir = Path(workdir).resolve()
        if self._observer is not None:
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()

        observer = Observer()
        handler = _SignalEventHandler(self)
        observer.schedule(handler, str(self._workdir), recursive=True)
        observer.start()
        self._observer = observer

    async def stop(self) -> None:
        """Stop the Observer; safe to call multiple times."""
        observer = self._observer
        if observer is None:
            return
        self._observer = None
        await asyncio.to_thread(observer.stop)
        await asyncio.to_thread(observer.join, 1.0)

    async def events(self) -> AsyncIterator[SignalEvent]:
        """Yield :class:`SignalEvent` instances as they arrive."""
        while True:
            evt = await self._queue.get()
            yield evt

    # ------------------------------------------------------------------
    # Called from the watchdog Observer thread — must hop back to the loop.
    def _enqueue(self, raw_path: str) -> None:
        kind = _classify_path(self._workdir, raw_path)
        if kind is None:
            return

        # Debounce: collapse rapid changes within the configured window.
        with self._lock:
            now_ms = time.monotonic() * 1000.0
            last_ms = self._last_emit.get(kind, 0.0)
            if now_ms - last_ms < self._debounce_ms:
                return
            self._last_emit[kind] = now_ms

        try:
            mtime = Path(raw_path).stat().st_mtime
        except OSError:
            mtime = 0.0
        # `kind` was produced by ``_classify_path`` which only returns one of
        # the SignalEvent literals, so the cast is safe.
        kind_lit = cast(
            Literal[
                "bugfix_request",
                "increment_request",
                "feature_list_changed",
                "srs_changed",
                "design_changed",
                "ats_changed",
                "ucd_changed",
                "rules_changed",
            ],
            kind,
        )
        evt = SignalEvent(kind=kind_lit, path=str(raw_path), mtime=mtime)

        loop = self._loop
        if loop is None or loop.is_closed():
            return

        def _push() -> None:
            self._queue.put_nowait(evt)
            try:
                self._bus.broadcast_signal(evt)
            except Exception:
                pass

        try:
            loop.call_soon_threadsafe(_push)
        except RuntimeError:
            # Loop already shutting down — ignore.
            pass


__all__ = ["SignalEvent", "SignalFileWatcher"]
