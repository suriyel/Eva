"""未 wire orchestrator 时各路由的容错行为。

修复 ``AttributeError: 'State' object has no attribute 'orchestrator'`` 的回归测试。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_no_wire(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """提供 lifespan 完成但 wire_services 未触发的 app（current_workdir=None）。"""
    home = tmp_path / ".harness"
    home.mkdir()
    monkeypatch.setenv("HARNESS_HOME", str(home))
    from harness.api import app

    for slot in (
        "orchestrator",
        "run_control_bus",
        "ticket_repo",
        "files_service",
        "commit_list_service",
        "diff_loader",
        "validator_runner",
        "workdir",
    ):
        if hasattr(app.state, slot):
            try:
                delattr(app.state, slot)
            except AttributeError:
                pass
    yield TestClient(app)


def test_runs_current_returns_null_when_no_orchestrator(app_no_wire) -> None:
    r = app_no_wire.get("/api/runs/current")
    assert r.status_code == 200
    assert r.json() is None


def test_runs_list_returns_empty(app_no_wire) -> None:
    r = app_no_wire.get("/api/runs?limit=10")
    assert r.status_code == 200
    assert r.json() == []


def test_runs_start_returns_400_workdir_not_selected(app_no_wire) -> None:
    r = app_no_wire.post("/api/runs/start", json={"workdir": "/tmp/x"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error_code"] == "workdir_not_selected"


def test_runs_pause_returns_404(app_no_wire) -> None:
    r = app_no_wire.post("/api/runs/some-run/pause")
    assert r.status_code == 404
    assert r.json()["detail"]["error_code"] == "run_not_found"


def test_runs_cancel_returns_404(app_no_wire) -> None:
    r = app_no_wire.post("/api/runs/some-run/cancel")
    assert r.status_code == 404
    assert r.json()["detail"]["error_code"] == "run_not_found"


def test_tickets_list_returns_empty(app_no_wire) -> None:
    r = app_no_wire.get("/api/tickets?run_id=run-1")
    assert r.status_code == 200
    assert r.json() == []


def test_tickets_detail_returns_404(app_no_wire) -> None:
    r = app_no_wire.get("/api/tickets/some-id")
    assert r.status_code == 404


def test_files_tree_returns_empty(app_no_wire) -> None:
    r = app_no_wire.get("/api/files/tree?root=docs")
    assert r.status_code == 200
    body = r.json()
    assert body.get("children") == []


def test_skills_install_returns_400(app_no_wire) -> None:
    r = app_no_wire.post(
        "/api/skills/install",
        json={"kind": "clone", "source": "https://github.com/x/y.git", "target_dir": "plugins/y"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error_code"] == "workdir_not_selected"


def test_git_commits_returns_empty(app_no_wire) -> None:
    r = app_no_wire.get("/api/git/commits?limit=5")
    assert r.status_code == 200
    assert r.json() == []
