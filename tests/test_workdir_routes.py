"""/api/workdirs REST 路由单测。

GET /api/workdirs        → {workdirs, current}
POST /select             → add + 设 current + wire_services
POST /remove             → 移除；命中 current 同时 unwire
POST /pick-native        → 无 webview window 时 501
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".harness"
    home.mkdir()
    monkeypatch.setenv("HARNESS_HOME", str(home))
    return home


@pytest.fixture
def app_client(isolated_home: Path):
    from harness.api import app

    # 确保 state 干净
    for slot in (
        "orchestrator",
        "run_control_bus",
        "ticket_repo",
        "hil_event_bus",
        "signal_file_watcher",
        "files_service",
        "commit_list_service",
        "diff_loader",
        "validator_runner",
        "workdir",
        "webview_window",
    ):
        if hasattr(app.state, slot):
            try:
                delattr(app.state, slot)
            except AttributeError:
                pass
    yield TestClient(app), app
    for slot in (
        "orchestrator",
        "run_control_bus",
        "ticket_repo",
        "hil_event_bus",
        "signal_file_watcher",
        "files_service",
        "commit_list_service",
        "diff_loader",
        "validator_runner",
        "workdir",
        "webview_window",
    ):
        if hasattr(app.state, slot):
            try:
                delattr(app.state, slot)
            except AttributeError:
                pass


def test_get_workdirs_empty_at_first(app_client) -> None:
    client, _app = app_client
    r = client.get("/api/workdirs")
    assert r.status_code == 200
    assert r.json() == {"workdirs": [], "current": None}


def test_select_validates_path(app_client, tmp_path: Path) -> None:
    client, _app = app_client
    r = client.post("/api/workdirs/select", json={"path": ""})
    assert r.status_code == 400
    assert r.json()["detail"]["error_code"] == "invalid_workdir"

    r = client.post("/api/workdirs/select", json={"path": "/no/such/dir"})
    assert r.status_code == 400
    assert r.json()["detail"]["error_code"] == "invalid_workdir"


def test_select_persists_and_wires(app_client, tmp_path: Path) -> None:
    client, app = app_client
    target = tmp_path / "ws1"
    target.mkdir()

    r = client.post("/api/workdirs/select", json={"path": str(target)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current"] == str(target)
    assert str(target) in body["workdirs"]

    # 9 + 1 = 10 个 slot 都被 wire 上
    for slot in (
        "orchestrator",
        "run_control_bus",
        "ticket_repo",
        "files_service",
        "workdir",
    ):
        assert hasattr(app.state, slot), slot

    # 持久化 → config.json 落盘
    import os

    cfg_path = Path(os.environ["HARNESS_HOME"]) / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["current_workdir"] == str(target)
    assert str(target) in cfg["workdirs"]


def test_select_supports_switching(app_client, tmp_path: Path) -> None:
    client, _app = app_client
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()

    client.post("/api/workdirs/select", json={"path": str(a)})
    r = client.post("/api/workdirs/select", json={"path": str(b)})
    assert r.status_code == 200
    body = r.json()
    assert body["current"] == str(b)
    assert body["workdirs"] == [str(a), str(b)]


def test_remove_clears_current_and_unwires(app_client, tmp_path: Path) -> None:
    client, app = app_client
    target = tmp_path / "ws_to_remove"
    target.mkdir()

    client.post("/api/workdirs/select", json={"path": str(target)})
    assert hasattr(app.state, "orchestrator")

    r = client.post("/api/workdirs/remove", json={"path": str(target)})
    assert r.status_code == 200
    body = r.json()
    assert body["current"] is None
    assert body["workdirs"] == []
    assert not hasattr(app.state, "orchestrator")


def test_remove_keeps_others(app_client, tmp_path: Path) -> None:
    client, _app = app_client
    a = tmp_path / "alpha"
    b = tmp_path / "bravo"
    a.mkdir()
    b.mkdir()
    client.post("/api/workdirs/select", json={"path": str(a)})
    client.post("/api/workdirs/select", json={"path": str(b)})  # b is current

    r = client.post("/api/workdirs/remove", json={"path": str(a)})
    body = r.json()
    assert body["current"] == str(b)
    assert body["workdirs"] == [str(b)]


def test_pick_native_returns_501_when_no_webview(app_client) -> None:
    client, _app = app_client
    r = client.post("/api/workdirs/pick-native")
    assert r.status_code == 501
    assert r.json()["detail"]["error_code"] == "not_supported_in_web_mode"
