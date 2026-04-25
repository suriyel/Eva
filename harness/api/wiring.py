"""F23 · Production wiring helper for ``harness.api:app``.

Populates ``app.state.*`` slots with the service singletons that the routers
in this package read at request time:

    orchestrator         RunOrchestrator (test-default profile)
    run_control_bus      RunControlBus  (shared with orchestrator)
    ticket_repo          orchestrator.ticket_repo passthrough
    hil_event_bus        HilEventBus  (broadcasts to /ws/hil subscribers)
    signal_file_watcher  SignalFileWatcher  (started against workdir)
    files_service        FilesService(workdir)
    commit_list_service  CommitListService()
    diff_loader          DiffLoader(workdir)
    validator_runner     ValidatorRunner(plugin_dir=workdir)

Idempotent — calling twice with the same ``workdir`` rebuilds singletons.
Importable as ``from harness.api import wire_services``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.api.files import FilesService
from harness.api.git import CommitListService, DiffLoader
from harness.hil.event_bus import HilEventBus
from harness.orchestrator.run import RunOrchestrator
from harness.orchestrator.signal_watcher import SignalFileWatcher
from harness.subprocess.validator.runner import ValidatorRunner


def wire_services(app: Any, *, workdir: Path) -> None:
    """Populate ``app.state.*`` for the F23 production wiring path."""
    workdir = Path(workdir)

    orch = RunOrchestrator.build_test_default(workdir=workdir)
    bus = orch.control_bus

    # HilEventBus — broadcasts to /ws/hil subscribers via injected callable.
    captured_answers: list[dict[str, Any]] = []

    def _hil_broadcast(payload: dict[str, Any]) -> None:
        envelope = {"kind": "hil_event", "payload": payload}
        if "answer" in payload:
            captured_answers.append(payload["answer"])
        for q in list(getattr(app.state, "_hil_subs", [])):
            try:
                q.put_nowait(envelope)
            except Exception:
                pass

    hil_bus = HilEventBus(ws_broadcast=_hil_broadcast)
    # Expose captured answers for R43 (HTML freeform passthrough).
    hil_bus.captured_answers = lambda: list(captured_answers)  # type: ignore[attr-defined]

    # SignalFileWatcher — start once against workdir; bridges to bus broadcast_signal.
    watcher = SignalFileWatcher(workdir=workdir, control_bus=bus)
    try:
        watcher.start(workdir=workdir)
    except Exception:
        pass

    files_service = FilesService(workdir=workdir)
    commit_list_service = CommitListService()
    diff_loader = DiffLoader(workdir=workdir)
    validator_runner = ValidatorRunner(plugin_dir=workdir)

    app.state.orchestrator = orch
    app.state.run_control_bus = bus
    app.state.ticket_repo = orch.ticket_repo
    app.state.hil_event_bus = hil_bus
    app.state.signal_file_watcher = watcher
    app.state.files_service = files_service
    app.state.commit_list_service = commit_list_service
    app.state.diff_loader = diff_loader
    app.state.validator_runner = validator_runner
    app.state.workdir = str(workdir)
    if not hasattr(app.state, "_hil_subs"):
        app.state._hil_subs = []


__all__ = ["wire_services"]
