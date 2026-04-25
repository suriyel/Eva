"""Integration tests for F23 · 14 REST routes mounted on production ``harness.api:app``.

Bugfix Feature #23 — F18/F20 IAPI-002 ship miss: 14 REST routes implemented in the
service layer are NOT mounted on the production ASGI entry ``harness.api:app``;
F22 (Fe-Config) cannot enter TDD until this regression is healed.

[integration] — uses REAL FastAPI ASGI dispatch via ``httpx.ASGITransport`` end
to end against the **production** ``harness.api:app`` (NOT the test-only
factory ``harness.app.main.build_app``). Service layer is NOT mocked; tests
seed via real ``app.state.*`` singletons populated through the production
wiring path (or via test fixtures that call the real bootstrap helpers).

Feature ref: feature 23

Traces To
=========
  R1   §6.2.2 L1137  + Interface Contract `runs_router.post_start_run`        (FUNC/happy)
  R2   §Interface Contract `post_start_run` Raises  + FR-001 AC-3              (FUNC/error)
  R3   §Interface Contract `post_start_run` Raises  + workdir shell metachars  (FUNC/error)
  R4   §6.2.2 L1146  + Interface Contract `anomaly_router.post_skip`           (INTG/asgi-rest)
  R5   §6.2.2 L1147  + Interface Contract `anomaly_router.post_force_abort`    (INTG/asgi-rest)
  R6   §Interface Contract `post_skip` Raises  TicketNotFound                   (FUNC/error)
  R7   §Interface Contract `post_force_abort` Raises  InvalidTicketState        (FUNC/error)
  R8   §6.2.2 L1142  + Interface Contract `tickets_router.get_tickets`         (INTG/asgi-rest)
  R9   §Interface Contract `tickets_router.get_ticket` Raises 404               (FUNC/error)
  R10  §6.2.2 L1144  + Interface Contract `tickets_router.get_ticket_stream`   (INTG/asgi-rest)
  R11  §6.2.2 L1162  + Interface Contract `validate_router.post_validate`      (INTG/asgi-rest)
  R12  §Interface Contract `post_validate` non-fatal script errors              (FUNC/error)
  R13  §6.2.2 L1163  + Interface Contract `git_router.get_commits`             (INTG/asgi-rest)
  R14  §6.2.2 L1164  + Interface Contract `git_router.get_diff`                (INTG/asgi-rest)
  R15  §Interface Contract `get_diff` Raises DiffNotFound                       (FUNC/error)
  R16  §6.2.2 L1148  + Interface Contract `general_settings_router.get_general` (INTG/asgi-rest)
  R17  §6.2.2 L1157  + Interface Contract `skills_router.get_tree`             (INTG/asgi-rest)
  R18  §6.2.2 L1138  + Interface Contract `runs_router.get_runs_current`       (INTG/asgi-rest)
  R19  §6.2.2 L1139  + Interface Contract `runs_router.get_runs`               (INTG/asgi-rest)
  R20  §6.2.2 L1160-1161  + Interface Contract `files_router.get_tree`         (INTG/asgi-rest)
  R21  §Interface Contract `files_router.get_tree` Raises PathTraversalError    (FUNC/error)
  R32  §6.2.2 L1145  + Interface Contract `hil_router.post_answer`             (INTG/hil-flow REST half)
  R33  §Interface Contract `validate_router` SEC path traversal                 (SEC/path-traversal)
  R34  §Interface Contract `post_answer` Raises 409                             (FUNC/error)
  R35  §6.2.2 L1149  + Interface Contract `general_settings_router.put_general` (INTG/asgi-rest)
  R37  §6.2.2 L1140  + Interface Contract `runs_router.post_pause`             (INTG/asgi-rest)
  R38  §6.2.2 L1141  + Interface Contract `runs_router.post_cancel`            (INTG/asgi-rest)
  R39  §Boundary Conditions `get_runs.limit` 0                                  (BNDRY/edge)
  R40  §Boundary Conditions `get_runs.limit` 201                                (BNDRY/edge)
  R41  §Boundary Conditions `get_diff.sha` 65 chars                             (BNDRY/edge)
  R43  §Interface Contract `post_answer` SEC freeform passthrough              (SEC/forbid)
  R44  §Boundary Conditions `RunStartRequest.workdir` empty string              (BNDRY/edge)
  R45  §Boundary Conditions `files_router.get_read.path` empty                  (BNDRY/edge)
  R46  §Boundary Conditions `tickets.get_ticket_stream.offset` -1               (BNDRY/edge)

Negative ratio (this file): R2, R3, R6, R7, R9, R12, R15, R21, R33, R34,
                            R39, R40, R41, R43, R44, R45, R46 = 17/33 ≈ 51.5%
(file-local; combined with the rest of the suite is computed in the Red report.)
"""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest


pytestmark = [pytest.mark.real_http, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@contextmanager
def _env_override(**vars_: str) -> Iterator[None]:
    """Save-restore env vars without monkeypatch (real-test scanner clean)."""
    prev: dict[str, str | None] = {k: os.environ.get(k) for k in vars_}
    os.environ.update(vars_)
    try:
        yield
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _git_init(workdir: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=a@b",
            "-c",
            "user.name=A",
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            "initial",
        ],
        cwd=workdir,
        check=True,
    )


def _git_init_with_commit(workdir: Path, message: str = "fix") -> str:
    """Initialise a git repo, write a file, commit, return the commit SHA."""
    _git_init(workdir)
    (workdir / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=workdir, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=a@b",
            "-c",
            "user.name=A",
            "commit",
            "-q",
            "-m",
            message,
        ],
        cwd=workdir,
        check=True,
    )
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _client_for_app(app: Any) -> httpx.AsyncClient:
    """Return an httpx AsyncClient bound to the given ASGI app via real ASGITransport."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _wire_app_for_test(app: Any, *, workdir: Path) -> None:
    """Invoke the production wiring helper for ``harness.api:app``.

    Feature 23 specifies AppBootstrap (or a `_wire_services(app, workdir=...)`
    helper) populates ``app.state.{orchestrator, run_control_bus, ticket_repo,
    hil_event_bus, signal_file_watcher, files_service, commit_list_service,
    diff_loader, validator_runner}``. Tests rely on the helper being importable
    from ``harness.api`` (or ``harness.app``); Red phase: no such helper exists
    → ImportError, which is the expected failure mode for these tests.
    """
    from harness.api import wire_services  # type: ignore[attr-defined]

    wire_services(app, workdir=workdir)


# ---------------------------------------------------------------------------
# R1 — POST /api/runs/start (happy path) on production app
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r1_post_runs_start_returns_200_on_production_app(
    tmp_path: Path,
) -> None:
    """feature 23 R1 INTG/asgi-rest: production ``harness.api:app`` must mount
    POST /api/runs/start and dispatch to RunOrchestrator (currently 405/404)."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.post("/api/runs/start", json={"workdir": str(tmp_path)})

    assert resp.status_code == 200, (
        f"feature 23 R1 expected 200; got {resp.status_code}: {resp.text!r} — "
        f"router /api/runs/start not mounted on harness.api:app (current bug)"
    )
    body = resp.json()
    assert body["state"] in {
        "starting",
        "running",
    }, f"feature 23 R1 expected state ∈ {{starting, running}}; got {body!r}"
    assert body["workdir"] == str(tmp_path)
    assert isinstance(body.get("run_id"), str) and body["run_id"].startswith(
        "run-"
    ), f"feature 23 R1 expected run_id starting with 'run-'; got {body!r}"
    assert (
        isinstance(body.get("started_at"), str) and len(body["started_at"]) >= 19
    ), f"feature 23 R1 expected ISO-8601 started_at; got {body.get('started_at')!r}"


# ---------------------------------------------------------------------------
# R2 — POST /api/runs/start with non-git workdir → 400 not_a_git_repo
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r2_post_runs_start_rejects_non_git_workdir(
    tmp_path: Path,
) -> None:
    """feature 23 R2 FUNC/error: non-git workdir must be 400 not_a_git_repo."""
    from harness.api import app

    _wire_app_for_test(app, workdir=tmp_path)
    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()

    async with _client_for_app(app) as client:
        resp = await client.post("/api/runs/start", json={"workdir": str(plain_dir)})

    assert (
        resp.status_code == 400
    ), f"feature 23 R2 expected 400; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    flat = json.dumps(body)
    assert (
        "not_a_git_repo" in flat or "not a git" in flat.lower()
    ), f"feature 23 R2 expected error_code 'not_a_git_repo'; got {body!r}"


# ---------------------------------------------------------------------------
# R3 — POST /api/runs/start with shell metachar in workdir → 400 invalid_workdir
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r3_post_runs_start_rejects_workdir_shell_metachar(
    tmp_path: Path,
) -> None:
    """feature 23 R3 FUNC/error: workdir containing ';' must be 400 invalid_workdir."""
    from harness.api import app

    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.post(
            "/api/runs/start",
            json={"workdir": f"{tmp_path};rm -rf /"},
        )

    assert resp.status_code == 400, (
        f"feature 23 R3 expected 400; got {resp.status_code}: {resp.text!r} — "
        "router must surface RunStartError(invalid_workdir) as 400, not fall "
        "through to SPA static fallback"
    )
    body = resp.json()
    flat = json.dumps(body)
    assert (
        "invalid_workdir" in flat
    ), f"feature 23 R3 expected error_code 'invalid_workdir'; got {body!r}"


# ---------------------------------------------------------------------------
# R4 — POST /api/anomaly/{ticket_id}/skip
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r4_post_anomaly_skip_returns_recovery_decision(
    tmp_path: Path,
) -> None:
    """feature 23 R4 INTG/asgi-rest: /api/anomaly/{tid}/skip must dispatch to
    RunOrchestrator.skip_anomaly and return RecoveryDecision(kind='skipped').

    srs_trace: FR-029 (异常可视化 + 手动控制 — Skip)
    """
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator

    # Seed a retrying ticket via orchestrator's internal API.
    ticket_id = await orch.spawn_test_ticket(state="retrying")  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.post(f"/api/anomaly/{ticket_id}/skip")

    assert (
        resp.status_code == 200
    ), f"feature 23 R4 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        body.get("kind") == "skipped"
    ), f"feature 23 R4 expected RecoveryDecision.kind='skipped'; got {body!r}"


# ---------------------------------------------------------------------------
# R5 — POST /api/anomaly/{ticket_id}/force-abort
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r5_post_anomaly_force_abort_returns_abort_decision(
    tmp_path: Path,
) -> None:
    """feature 23 R5 INTG/asgi-rest: /api/anomaly/{tid}/force-abort must
    dispatch to RunOrchestrator.force_abort_anomaly and return kind='abort'."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator

    ticket_id = await orch.spawn_test_ticket(state="running")  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.post(f"/api/anomaly/{ticket_id}/force-abort")

    assert (
        resp.status_code == 200
    ), f"feature 23 R5 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        body.get("kind") == "abort"
    ), f"feature 23 R5 expected RecoveryDecision.kind='abort'; got {body!r}"


# ---------------------------------------------------------------------------
# R6 — POST /api/anomaly/{unknown}/skip → 404 TicketNotFound
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r6_post_anomaly_skip_unknown_ticket_returns_404(
    tmp_path: Path,
) -> None:
    """feature 23 R6 FUNC/error: unknown ticket_id must be 404 (router must
    translate TicketNotFound to HTTPException(404), not 500)."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.post("/api/anomaly/t-does-not-exist/skip")

    assert resp.status_code == 404, (
        f"feature 23 R6 expected 404 TicketNotFound; got {resp.status_code}: "
        f"{resp.text!r} — router must translate TicketNotFound to 404, not 500"
    )


# ---------------------------------------------------------------------------
# R7 — POST /api/anomaly/{completed-tid}/force-abort → 409 InvalidTicketState
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r7_post_anomaly_force_abort_completed_returns_409(
    tmp_path: Path,
) -> None:
    """feature 23 R7 FUNC/error: ticket already COMPLETED → 409 InvalidTicketState."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator

    ticket_id = await orch.spawn_test_ticket(state="completed")  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.post(f"/api/anomaly/{ticket_id}/force-abort")

    assert resp.status_code == 409, (
        f"feature 23 R7 expected 409 InvalidTicketState; got {resp.status_code}: " f"{resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R8 — GET /api/tickets?run_id=<rid>
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r8_get_tickets_by_run_returns_seeded_tickets(
    tmp_path: Path,
) -> None:
    """feature 23 R8 INTG/asgi-rest: /api/tickets?run_id=<rid> must list 3
    seeded tickets sorted by started_at ASC."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    run_id = await orch.spawn_test_run()  # type: ignore[attr-defined]
    seeded_ids: list[str] = []
    for _ in range(3):
        seeded_ids.append(
            await orch.spawn_test_ticket(state="running", run_id=run_id)  # type: ignore[attr-defined]
        )

    async with _client_for_app(app) as client:
        resp = await client.get("/api/tickets", params={"run_id": run_id})

    assert (
        resp.status_code == 200
    ), f"feature 23 R8 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert isinstance(body, list), f"feature 23 R8 expected list; got {type(body)!r}"
    assert (
        len(body) == 3
    ), f"feature 23 R8 expected 3 tickets for run_id={run_id}; got len={len(body)} body={body!r}"
    returned_ids = [t["id"] for t in body]
    assert set(returned_ids) == set(seeded_ids), (
        f"feature 23 R8 expected ticket id set {sorted(seeded_ids)}; " f"got {sorted(returned_ids)}"
    )


# ---------------------------------------------------------------------------
# R9 — GET /api/tickets/{unknown} → 404
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r9_get_ticket_unknown_returns_404(
    tmp_path: Path,
) -> None:
    """feature 23 R9 FUNC/error: unknown ticket_id → 404 (router must surface
    a 404, not 500 via uncaught exception)."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/tickets/t-not-here")

    assert resp.status_code == 404, (
        f"feature 23 R9 expected 404 ticket not found; got {resp.status_code}: " f"{resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R10 — GET /api/tickets/{tid}/stream?offset=0
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r10_get_ticket_stream_returns_event_array(
    tmp_path: Path,
) -> None:
    """feature 23 R10 INTG/asgi-rest: /api/tickets/{tid}/stream returns
    StreamEvent[] sorted by seq ASC for the given ticket."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    ticket_id = await orch.spawn_test_ticket(state="running")  # type: ignore[attr-defined]
    # Seed two stream events
    await orch.spawn_test_stream_events(  # type: ignore[attr-defined]
        ticket_id,
        [{"kind": "text", "payload": {"text": "a"}}, {"kind": "text", "payload": {"text": "b"}}],
    )

    async with _client_for_app(app) as client:
        resp = await client.get(f"/api/tickets/{ticket_id}/stream", params={"offset": 0})

    assert (
        resp.status_code == 200
    ), f"feature 23 R10 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        isinstance(body, list) and len(body) == 2
    ), f"feature 23 R10 expected 2 stream events; got {body!r}"
    assert [ev.get("seq") for ev in body] == sorted(
        ev.get("seq") for ev in body
    ), f"feature 23 R10 events must be sorted by seq ASC; got {body!r}"


# ---------------------------------------------------------------------------
# R11 — POST /api/validate/{file} happy path
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r11_post_validate_returns_validation_report(
    tmp_path: Path,
) -> None:
    """feature 23 R11 INTG/asgi-rest: POST /api/validate/feature-list.json
    with a valid feature-list returns ValidationReport(ok=True, issues=[])."""
    from harness.api import app

    _git_init(tmp_path)
    flist = tmp_path / "feature-list.json"
    flist.write_text(
        json.dumps({"version": "1.0", "tech_stack": {}, "features": []}),
        encoding="utf-8",
    )
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.post(
            "/api/validate/feature-list.json",
            json={"script": "validate_features"},
        )

    assert (
        resp.status_code == 200
    ), f"feature 23 R11 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        "ok" in body and "issues" in body
    ), f"feature 23 R11 expected ValidationReport(ok, issues, ...); got {body!r}"
    assert isinstance(body["ok"], bool)
    assert isinstance(body["issues"], list)


# ---------------------------------------------------------------------------
# R12 — POST /api/validate/{file} with invalid feature-list still returns 200
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r12_post_validate_returns_200_for_script_failure(
    tmp_path: Path,
) -> None:
    """feature 23 R12 FUNC/error: script exit≠0 must surface as
    ValidationReport(ok=False, issues=[...]); router must NOT 500 for normal
    validator failures (FR-039 expects user-visible report not server error)."""
    from harness.api import app

    _git_init(tmp_path)
    flist = tmp_path / "feature-list.json"
    flist.write_text("{this is not valid json", encoding="utf-8")
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.post(
            "/api/validate/feature-list.json",
            json={"script": "validate_features"},
        )

    assert resp.status_code == 200, (
        f"feature 23 R12 expected 200 (validator surfaces ok=False); got "
        f"{resp.status_code}: {resp.text!r} — router must NOT translate non-zero "
        "validator exit into 500"
    )
    body = resp.json()
    assert (
        body.get("ok") is False
    ), f"feature 23 R12 expected ok=False for malformed feature-list; got {body!r}"
    assert (
        isinstance(body.get("issues"), list) and len(body["issues"]) > 0
    ), f"feature 23 R12 expected non-empty issues array; got {body!r}"


# ---------------------------------------------------------------------------
# R13 — GET /api/git/commits?run_id=<rid>
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r13_get_git_commits_filters_by_run_id(
    tmp_path: Path,
) -> None:
    """feature 23 R13 INTG/asgi-rest: /api/git/commits?run_id=<rid> returns 5
    commits sorted by committed_at DESC for the given run_id.

    srs_trace: FR-042 (Ticket 级 git 记录 — commit 列表按 run_id 过滤)
    """
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    cls = app.state.commit_list_service
    rid = "run-r13"
    seeded = []
    for i in range(5):
        seeded.append(
            {
                "sha": f"{i:040x}",
                "subject": f"commit {i}",
                "committed_at": f"2026-04-25T10:0{i}:00+00:00",
                "run_id": rid,
            }
        )
    await cls.seed_test_commits(seeded)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/git/commits", params={"run_id": rid})

    assert (
        resp.status_code == 200
    ), f"feature 23 R13 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        isinstance(body, list) and len(body) == 5
    ), f"feature 23 R13 expected 5 commits; got {body!r}"
    timestamps = [c["committed_at"] for c in body]
    assert timestamps == sorted(
        timestamps, reverse=True
    ), f"feature 23 R13 commits must be sorted by committed_at DESC; got {timestamps!r}"


# ---------------------------------------------------------------------------
# R14 — GET /api/git/diff/{sha}
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r14_get_git_diff_returns_diff_payload(
    tmp_path: Path,
) -> None:
    """feature 23 R14 INTG/asgi-rest: /api/git/diff/{sha} on a real git commit
    returns DiffPayload{sha, files, stats}."""
    from harness.api import app

    sha = _git_init_with_commit(tmp_path, "feature 23 r14")
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get(f"/api/git/diff/{sha}")

    assert (
        resp.status_code == 200
    ), f"feature 23 R14 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert body.get("sha") == sha, f"feature 23 R14 expected sha={sha!r}; got {body!r}"
    assert (
        "files" in body and "stats" in body
    ), f"feature 23 R14 expected DiffPayload with files+stats; got {body!r}"


# ---------------------------------------------------------------------------
# R15 — GET /api/git/diff/{unknown-sha} → 404 DiffNotFound
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r15_get_git_diff_unknown_sha_returns_404(
    tmp_path: Path,
) -> None:
    """feature 23 R15 FUNC/error: unknown sha must surface as 404 DiffNotFound,
    not 500."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/git/diff/" + ("0" * 40))

    assert resp.status_code == 404, (
        f"feature 23 R15 expected 404 DiffNotFound; got {resp.status_code}: " f"{resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R16 — GET /api/settings/general
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r16_get_settings_general_returns_defaults(
    tmp_path: Path,
) -> None:
    """feature 23 R16 INTG/asgi-rest: /api/settings/general returns
    GeneralSettings defaults from ~/.harness/config.json."""
    from harness.api import app

    _git_init(tmp_path)
    with _env_override(HARNESS_HOME=str(tmp_path / ".harness")):
        _wire_app_for_test(app, workdir=tmp_path)
        async with _client_for_app(app) as client:
            resp = await client.get("/api/settings/general")

    assert (
        resp.status_code == 200
    ), f"feature 23 R16 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        isinstance(body, dict) and len(body) > 0
    ), f"feature 23 R16 expected non-empty GeneralSettings dict; got {body!r}"


# ---------------------------------------------------------------------------
# R17 — GET /api/skills/tree
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r17_get_skills_tree_returns_skill_registry(
    tmp_path: Path,
) -> None:
    """feature 23 R17 INTG/asgi-rest: /api/skills/tree returns SkillTree with
    plugins[] derived from HARNESS_WORKDIR plugin registry."""
    from harness.api import app

    _git_init(tmp_path)
    plugins_dir = tmp_path / "plugins" / "longtaskforagent"
    plugins_dir.mkdir(parents=True)
    with _env_override(HARNESS_WORKDIR=str(tmp_path)):
        _wire_app_for_test(app, workdir=tmp_path)
        async with _client_for_app(app) as client:
            resp = await client.get("/api/skills/tree")

    assert (
        resp.status_code == 200
    ), f"feature 23 R17 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        "root" in body and "plugins" in body
    ), f"feature 23 R17 expected SkillTree {{root, plugins[]}}; got {body!r}"
    assert isinstance(body["plugins"], list)


# ---------------------------------------------------------------------------
# R18 — GET /api/runs/current with no active run → 200 null
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r18_get_runs_current_returns_null_when_idle(
    tmp_path: Path,
) -> None:
    """feature 23 R18 INTG/asgi-rest: no active run → 200 null body."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/runs/current")

    assert (
        resp.status_code == 200
    ), f"feature 23 R18 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert body is None, f"feature 23 R18 expected null body; got {body!r}"


# ---------------------------------------------------------------------------
# R19 — GET /api/runs?limit=2&offset=0 → 2 RunSummary
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r19_get_runs_paginates_history(
    tmp_path: Path,
) -> None:
    """feature 23 R19 INTG/asgi-rest: /api/runs?limit=2 returns 2 RunSummary
    rows from a history of 3 seeded runs, sorted started_at DESC."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    seeded_ids = []
    for _ in range(3):
        seeded_ids.append(await orch.spawn_test_run())  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.get("/api/runs", params={"limit": 2, "offset": 0})

    assert (
        resp.status_code == 200
    ), f"feature 23 R19 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        isinstance(body, list) and len(body) == 2
    ), f"feature 23 R19 expected 2 RunSummary entries; got {body!r}"


# ---------------------------------------------------------------------------
# R20 — GET /api/files/tree?root=docs
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r20_get_files_tree_returns_filetree(
    tmp_path: Path,
) -> None:
    """feature 23 R20 INTG/asgi-rest: /api/files/tree?root=docs returns
    FileTree{root, nodes}."""
    from harness.api import app

    _git_init(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("a", encoding="utf-8")
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/files/tree", params={"root": "docs"})

    assert (
        resp.status_code == 200
    ), f"feature 23 R20 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        "root" in body and "nodes" in body
    ), f"feature 23 R20 expected FileTree{{root, nodes}}; got {body!r}"


# ---------------------------------------------------------------------------
# R21 — GET /api/files/tree?root=../etc/passwd → 400 PathTraversalError
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r21_get_files_tree_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    """feature 23 R21 FUNC/error: parent-traversal root → 400 PathTraversalError."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/files/tree", params={"root": "../etc/passwd"})

    assert resp.status_code == 400, (
        f"feature 23 R21 expected 400 PathTraversalError; got {resp.status_code}: "
        f"{resp.text!r} — router must translate FilesService PathTraversalError to 400"
    )


# ---------------------------------------------------------------------------
# R32 — POST /api/hil/{tid}/answer (REST half; WS half is in the WS file)
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r32_post_hil_answer_rest_half_returns_ack(
    tmp_path: Path,
) -> None:
    """feature 23 R32 INTG/hil-flow REST half: POST /api/hil/{tid}/answer
    returns HilAnswerAck(accepted=True, ticket_state)."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    ticket_id = await orch.spawn_test_ticket(state="hil_waiting")  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.post(
            f"/api/hil/{ticket_id}/answer",
            json={
                "question_id": "q-1",
                "selected_labels": ["yes"],
                "freeform_text": "go",
                "answered_at": "2026-04-25T10:00:00+00:00",
            },
        )

    assert (
        resp.status_code == 200
    ), f"feature 23 R32 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        body.get("accepted") is True
    ), f"feature 23 R32 expected HilAnswerAck.accepted=True; got {body!r}"


# ---------------------------------------------------------------------------
# R33 — POST /api/validate/<traversal-path> → 400/422
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r33_post_validate_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    """feature 23 R33 SEC/path-traversal: POST /api/validate/../../etc/passwd
    must be rejected with 400 or 422 (router must guard path before runner)."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.post(
            "/api/validate/..%2F..%2Fetc%2Fpasswd",
            json={"script": "validate_features"},
        )

    assert resp.status_code in {400, 422, 404}, (
        f"feature 23 R33 expected 400/422/404 path rejection; got "
        f"{resp.status_code}: {resp.text!r}"
    )
    body = resp.json()
    flat = json.dumps(body).lower()
    assert (
        "path" in flat or "traversal" in flat or "invalid" in flat
    ), f"feature 23 R33 expected error mentioning path/traversal/invalid; got {body!r}"


# ---------------------------------------------------------------------------
# R34 — POST /api/hil/{tid}/answer when ticket not in hil_waiting → 409
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r34_post_hil_answer_wrong_state_returns_409(
    tmp_path: Path,
) -> None:
    """feature 23 R34 FUNC/error: ticket not in hil_waiting must be 409."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    ticket_id = await orch.spawn_test_ticket(state="running")  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.post(
            f"/api/hil/{ticket_id}/answer",
            json={
                "question_id": "q-1",
                "selected_labels": ["yes"],
                "freeform_text": "go",
                "answered_at": "2026-04-25T10:00:00+00:00",
            },
        )

    assert resp.status_code == 409, (
        f"feature 23 R34 expected 409 InvalidTicketState; got {resp.status_code}: " f"{resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R35 — PUT /api/settings/general
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r35_put_settings_general_persists_to_disk(
    tmp_path: Path,
) -> None:
    """feature 23 R35 INTG/asgi-rest: PUT /api/settings/general persists to
    ~/.harness/config.json and round-trips."""
    from harness.api import app

    _git_init(tmp_path)
    home = tmp_path / ".harness"
    home.mkdir()
    with _env_override(HARNESS_HOME=str(home)):
        _wire_app_for_test(app, workdir=tmp_path)
        async with _client_for_app(app) as client:
            resp = await client.put(
                "/api/settings/general",
                json={"ui_density": "comfortable"},
            )

    assert (
        resp.status_code == 200
    ), f"feature 23 R35 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        body.get("ui_density") == "comfortable"
    ), f"feature 23 R35 expected ui_density='comfortable'; got {body!r}"
    cfg_path = home / "config.json"
    assert (
        cfg_path.exists()
    ), f"feature 23 R35 expected ~/.harness/config.json persisted; missing {cfg_path}"
    persisted = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert (
        persisted.get("ui_density") == "comfortable"
    ), f"feature 23 R35 expected persisted ui_density='comfortable'; got {persisted!r}"


# ---------------------------------------------------------------------------
# R37 — POST /api/runs/{rid}/pause
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r37_post_runs_pause_returns_pause_pending(
    tmp_path: Path,
) -> None:
    """feature 23 R37 INTG/asgi-rest: pause an active run → 200 RunStatus with
    state='pause_pending'."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    run_id = await orch.spawn_test_run()  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.post(f"/api/runs/{run_id}/pause")

    assert (
        resp.status_code == 200
    ), f"feature 23 R37 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        body.get("state") == "pause_pending"
    ), f"feature 23 R37 expected state='pause_pending'; got {body!r}"


# ---------------------------------------------------------------------------
# R38 — POST /api/runs/{rid}/cancel
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r38_post_runs_cancel_returns_cancelled(
    tmp_path: Path,
) -> None:
    """feature 23 R38 INTG/asgi-rest: cancel an active run → 200 RunStatus
    with state='cancelled'."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    run_id = await orch.spawn_test_run()  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.post(f"/api/runs/{run_id}/cancel")

    assert (
        resp.status_code == 200
    ), f"feature 23 R38 expected 200; got {resp.status_code}: {resp.text!r}"
    body = resp.json()
    assert (
        body.get("state") == "cancelled"
    ), f"feature 23 R38 expected state='cancelled'; got {body!r}"


# ---------------------------------------------------------------------------
# R39 — GET /api/runs?limit=0 → 400
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r39_get_runs_limit_zero_returns_400(
    tmp_path: Path,
) -> None:
    """feature 23 R39 BNDRY/edge: limit=0 below the [1,200] range → 400."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/runs", params={"limit": 0})

    assert resp.status_code == 400, (
        f"feature 23 R39 expected 400 invalid_param for limit=0; got "
        f"{resp.status_code}: {resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R40 — GET /api/runs?limit=201 → 400
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r40_get_runs_limit_overflow_returns_400(
    tmp_path: Path,
) -> None:
    """feature 23 R40 BNDRY/edge: limit=201 above the [1,200] range → 400."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/runs", params={"limit": 201})

    assert resp.status_code == 400, (
        f"feature 23 R40 expected 400 invalid_param for limit=201; got "
        f"{resp.status_code}: {resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R41 — GET /api/git/diff/<65-char sha> → 404 DiffNotFound
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r41_get_git_diff_oversized_sha_returns_404(
    tmp_path: Path,
) -> None:
    """feature 23 R41 BNDRY/edge: sha > 64 chars → 404 DiffNotFound (not 500)."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    long_sha = "a" * 65
    async with _client_for_app(app) as client:
        resp = await client.get(f"/api/git/diff/{long_sha}")

    assert resp.status_code == 404, (
        f"feature 23 R41 expected 404 DiffNotFound for 65-char sha; got "
        f"{resp.status_code}: {resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R43 — POST /api/hil/{tid}/answer with HTML in freeform → 200 (no escape)
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r43_post_hil_answer_passes_html_freeform_through(
    tmp_path: Path,
) -> None:
    """feature 23 R43 SEC/forbid: HIL answer with HTML in freeform_text must
    be accepted (200); router MUST NOT HTML-escape — XSS prevention is the
    rendering surface's responsibility, the router must preserve original text."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    ticket_id = await orch.spawn_test_ticket(state="hil_waiting")  # type: ignore[attr-defined]
    payload_text = "<script>alert(1)</script>"

    async with _client_for_app(app) as client:
        resp = await client.post(
            f"/api/hil/{ticket_id}/answer",
            json={
                "question_id": "q-1",
                "selected_labels": ["yes"],
                "freeform_text": payload_text,
                "answered_at": "2026-04-25T10:00:00+00:00",
            },
        )

    assert resp.status_code == 200, (
        f"feature 23 R43 expected 200 (router must accept HTML freeform); got "
        f"{resp.status_code}: {resp.text!r}"
    )
    bus = app.state.hil_event_bus
    received = getattr(bus, "captured_answers", lambda: [])()
    assert any(
        entry.get("freeform_text") == payload_text for entry in received if isinstance(entry, dict)
    ), (
        f"feature 23 R43 expected raw freeform_text preserved on bus; "
        f"got captured_answers={received!r}"
    )


# ---------------------------------------------------------------------------
# R44 — POST /api/runs/start with empty workdir → 400
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r44_post_runs_start_rejects_empty_workdir(
    tmp_path: Path,
) -> None:
    """feature 23 R44 BNDRY/edge: empty workdir → 400 invalid_workdir (router
    must surface RunStartError as 400 rather than 500 RuntimeError)."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.post("/api/runs/start", json={"workdir": ""})

    assert resp.status_code == 400, (
        f"feature 23 R44 expected 400 invalid_workdir for empty workdir; got "
        f"{resp.status_code}: {resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R45 — GET /api/files/read?path= → 400 PathTraversalError
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r45_get_files_read_empty_path_returns_400(
    tmp_path: Path,
) -> None:
    """feature 23 R45 BNDRY/edge: empty path query → 400 PathTraversalError."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/files/read", params={"path": ""})

    assert resp.status_code == 400, (
        f"feature 23 R45 expected 400 for empty path; got {resp.status_code}: " f"{resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R46 — GET /api/tickets/{tid}/stream?offset=-1 → 400
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r46_get_ticket_stream_negative_offset_returns_400(
    tmp_path: Path,
) -> None:
    """feature 23 R46 BNDRY/edge: offset=-1 must be 400 invalid_param."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)
    orch = app.state.orchestrator
    ticket_id = await orch.spawn_test_ticket(state="running")  # type: ignore[attr-defined]

    async with _client_for_app(app) as client:
        resp = await client.get(f"/api/tickets/{ticket_id}/stream", params={"offset": -1})

    assert resp.status_code == 400, (
        f"feature 23 R46 expected 400 invalid_param for offset=-1; got "
        f"{resp.status_code}: {resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R47 — POST /api/validate with non-enum script → 422
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r47_post_validate_non_enum_script_returns_422(
    tmp_path: Path,
) -> None:
    """feature 23 R47 BNDRY/edge (Boundary Conditions `validate.body.script`):
    non-enum script value must be 422 (pydantic validation failure)."""
    from harness.api import app

    _git_init(tmp_path)
    flist = tmp_path / "feature-list.json"
    flist.write_text(
        json.dumps({"version": "1.0", "tech_stack": {}, "features": []}),
        encoding="utf-8",
    )
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.post(
            "/api/validate/feature-list.json",
            json={"script": "DROP TABLE features"},
        )

    assert resp.status_code == 422, (
        f"feature 23 R47 expected 422 (non-enum script); got " f"{resp.status_code}: {resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R48 — GET /api/runs?offset=-1 → 400 invalid_param
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r48_get_runs_negative_offset_returns_400(
    tmp_path: Path,
) -> None:
    """feature 23 R48 BNDRY/edge (Boundary Conditions `get_runs.offset`):
    offset=-1 must be 400 invalid_param (router must validate before service)."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        resp = await client.get("/api/runs", params={"offset": -1})

    assert resp.status_code == 400, (
        f"feature 23 R48 expected 400 invalid_param for offset=-1; got "
        f"{resp.status_code}: {resp.text!r}"
    )


# ---------------------------------------------------------------------------
# R49 — POST /api/anomaly/{empty}/skip — empty path segment → 404 (no match)
# ---------------------------------------------------------------------------
@pytest.mark.real_http
async def test_f23_feature_23_r49_post_anomaly_skip_empty_ticket_returns_404(
    tmp_path: Path,
) -> None:
    """feature 23 R49 BNDRY/edge: empty path segment must be 404 (FastAPI route
    won't match '/api/anomaly//skip'); router must NOT 500 even if a stripped
    request reaches the handler."""
    from harness.api import app

    _git_init(tmp_path)
    _wire_app_for_test(app, workdir=tmp_path)

    async with _client_for_app(app) as client:
        # Use a literal whitespace ticket_id which orchestrator must reject.
        resp = await client.post("/api/anomaly/%20/skip")

    assert resp.status_code in {400, 404}, (
        f"feature 23 R49 expected 400/404 for whitespace ticket_id; got "
        f"{resp.status_code}: {resp.text!r}"
    )
