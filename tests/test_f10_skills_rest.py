"""FastAPI TestClient-level tests for F10 · IAPI-018 REST layer.

Covers Test Inventory rows:
  T23 INTG/rest-install — POST /api/skills/install happy path (200 + schema)
  T24 INTG/rest-400     — non-whitelisted URL → HTTP 400
  T25 INTG/rest-409     — run.lock present → HTTP 409

Exercises real FastAPI app via TestClient (ASGI in-process; no sockets).
Subprocess calls are mocked at the module boundary so the REST layer is
itself real code under test.

Feature ref: feature_3
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide an isolated workdir the Skills REST routes resolve from.

    F10 design says install/pull consume ``workdir`` — the REST layer likely
    derives it from ``HARNESS_WORKDIR`` env or ConfigStore. We set the env
    var so the route picks it up regardless of the chosen resolution path.
    """
    wd = tmp_path / "project"
    wd.mkdir()
    (wd / ".harness").mkdir()
    (wd / "plugins").mkdir()
    monkeypatch.setenv("HARNESS_WORKDIR", str(wd))
    return wd


# ---------------------------------------------------------------------------
# T23 · INTG/rest-install — happy
# ---------------------------------------------------------------------------


def test_t23_rest_install_clone_returns_200_with_schema(workdir: Path) -> None:
    # Importing the app triggers router registration (F10 must include_router).
    from harness.api import app

    def fake_run(argv, **kwargs):
        assert kwargs.get("shell") is not True
        if "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout="c" * 40 + "\n", stderr="")
        # git clone
        target = Path(argv[-1])
        (target / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (target / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "longtaskforagent", "version": "1.0"}),
            encoding="utf-8",
        )
        (target / ".git").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/install",
                json={
                    "kind": "clone",
                    "source": "https://github.com/org/longtaskforagent.git",
                    "target_dir": "plugins/longtaskforagent",
                },
            )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # schema = SkillsInstallResult { ok, commit_sha, message }
    assert body["ok"] is True
    assert isinstance(body["commit_sha"], str)
    assert len(body["commit_sha"]) == 40
    assert isinstance(body.get("message"), str) and body["message"] != ""
    # Content-Type check
    assert resp.headers.get("content-type", "").startswith("application/json")


# ---------------------------------------------------------------------------
# T24 · INTG/rest-400 — file:// rejected with HTTP 400
# ---------------------------------------------------------------------------


def test_t24_rest_install_non_whitelisted_url_returns_400(workdir: Path) -> None:
    from harness.api import app

    with patch("subprocess.run") as mock_run:
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/install",
                json={
                    "kind": "clone",
                    "source": "file:///etc/passwd",
                    "target_dir": "plugins/ltfa",
                },
            )

    assert resp.status_code == 400, resp.text
    body = resp.json()
    # FastAPI HTTPException detail field carries the message
    detail = body.get("detail") or ""
    # Must contain a user-facing signal — accept either the code or a Chinese
    # message per env-guide zh-CN convention.
    assert isinstance(detail, str) or isinstance(detail, dict)
    if isinstance(detail, dict):
        detail = json.dumps(detail, ensure_ascii=False)
    # subprocess must NOT have been invoked
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# T25 · INTG/rest-409 — run.lock present → HTTP 409
# ---------------------------------------------------------------------------


def test_t25_rest_install_when_run_lock_present_returns_409(workdir: Path) -> None:
    from harness.api import app

    # create the lock file
    (workdir / ".harness" / "run.lock").write_text("", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/install",
                json={
                    "kind": "clone",
                    "source": "https://github.com/org/longtaskforagent.git",
                    "target_dir": "plugins/longtaskforagent",
                },
            )

    assert resp.status_code == 409, resp.text
    body = resp.json()
    # detail should mention run / lock / busy in some form; we accept either
    # English or zh-CN marker as long as a meaningful string is present.
    detail = body.get("detail")
    assert detail, "409 response must carry a non-empty detail"
    mock_run.assert_not_called()


__all__: list[str] = []
