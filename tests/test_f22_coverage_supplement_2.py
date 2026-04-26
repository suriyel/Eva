"""Second supplemental unit-test set for F22 — pushes backend coverage from
89.41% to >= 90% by hitting remaining missing branches in the F22-modified
modules.

Targeted lines (via pytest-cov term-missing):
    - harness/api/validate.py            135-140 (ValidatorScriptUnknown
                                            HTTPException 400),
                                          147-148 (temp_path.unlink swallow
                                            OSError),
                                          153 (env restore prev_strict not None)
    - harness/api/general_settings.py    103 (json non-dict load),
                                          119 (PUT plaintext key skipped in
                                            response carry-over),
                                          137 (PUT body not dict → 400),
                                          161, 163 (carry-over prev ref/masked)
    - harness/api/git_routes.py          69 (git-log fallback when registry
                                            empty for real git repo),
                                          91 (split parts != 5 skip),
                                          120-124 (DiffNotFound fallback path
                                            via in-memory loader),
                                          166 (no current diff line skipped)
    - harness/subprocess/validator/runner.py
                                          108-109 (terminate
                                            ProcessLookupError swallow),
                                          113-114 (kill ProcessLookupError
                                            swallow),
                                          134 (parsed dict-issue branch when
                                            issue is dict — covered by file
                                            running) — already covered.

All tests anchor to feature #22 (F22) SRS coverage (FR-032, FR-033, FR-035,
FR-038, FR-041, NFR-008, IFR-004, IFR-005, IFR-006); no new FR-IDs are
introduced.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# harness.api.validate — ValidatorScriptUnknown 400 + temp_path unlink swallow
# Traces To IFR-004 (FR-039 + FR-040 error wrapping)
# ---------------------------------------------------------------------------
def test_f22_validate_returns_400_when_script_unknown(tmp_path: Path) -> None:
    """When ValidatorRunner raises ValidatorScriptUnknown, route wraps it as
    HTTP 400 ``unknown_script`` (validate.py:135-138)."""
    from harness.api.validate import router
    from harness.subprocess.validator.runner import ValidatorScriptUnknown

    app = FastAPI()
    app.include_router(router)
    workdir = tmp_path / "wd"
    workdir.mkdir()
    (workdir / "feature-list.json").write_text("{}", encoding="utf-8")
    app.state.workdir = str(workdir)

    class _Runner:
        async def run(self, _req: Any) -> Any:
            raise ValidatorScriptUnknown("unknown validator script: 'x'")

    app.state.validator_runner = _Runner()
    client = TestClient(app)
    resp = client.post(
        "/api/validate/feature-list.json",
        json={"script": "validate_features", "timeout_s": 10.0},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "unknown_script"


def test_f22_validate_returns_500_when_runner_times_out(tmp_path: Path) -> None:
    """Runner timeout → HTTP 500 with `error_code='timeout'` (validate.py:139-142)."""
    from harness.api.validate import router
    from harness.subprocess.validator.runner import ValidatorTimeout

    app = FastAPI()
    app.include_router(router)
    workdir = tmp_path / "wd"
    workdir.mkdir()
    (workdir / "feature-list.json").write_text("{}", encoding="utf-8")
    app.state.workdir = str(workdir)

    class _Runner:
        async def run(self, _req: Any) -> Any:
            raise ValidatorTimeout("validator timeout")

    app.state.validator_runner = _Runner()
    client = TestClient(app)
    resp = client.post(
        "/api/validate/feature-list.json",
        json={"script": "validate_features", "timeout_s": 0.1},
    )
    assert resp.status_code == 500
    assert resp.json()["detail"]["error_code"] == "timeout"


def test_f22_validate_swallows_temp_unlink_oserror(tmp_path: Path) -> None:
    """When temp_path.unlink() raises OSError, route does NOT propagate
    (validate.py:147-148)."""
    from harness.api import validate as v

    app = FastAPI()
    app.include_router(v.router)
    workdir = tmp_path / "wd"
    workdir.mkdir()
    app.state.workdir = str(workdir)

    class _OkRunner:
        async def run(self, _req: Any) -> Any:
            from harness.subprocess.validator.schemas import ValidationReport

            return ValidationReport(
                ok=True, issues=[], script_exit_code=0, duration_ms=1, http_status_hint=200
            )

    app.state.validator_runner = _OkRunner()

    # Patch Path.unlink globally during the request to force the OSError path.
    real_unlink = Path.unlink

    def _unlink(self: Path, *args: Any, **kwargs: Any) -> None:
        # Trip OSError ONLY on the temp file the route created, not on test cleanup.
        if "f22_validate_" in self.name:
            raise OSError("simulated unlink failure")
        return real_unlink(self, *args, **kwargs)

    with patch.object(Path, "unlink", _unlink):
        client = TestClient(app)
        resp = client.post(
            "/api/validate/feature-list.json",
            json={"content": "{}", "script": "validate_features", "timeout_s": 5.0},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_f22_validate_restores_previous_strict_features_env(tmp_path: Path) -> None:
    """When ``HARNESS_STRICT_FEATURES`` was already set, finally-block restores
    it to the prior value (validate.py:152-153)."""
    from harness.api import validate as v

    app = FastAPI()
    app.include_router(v.router)
    workdir = tmp_path / "wd"
    workdir.mkdir()
    (workdir / "feature-list.json").write_text("{}", encoding="utf-8")
    app.state.workdir = str(workdir)

    class _OkRunner:
        async def run(self, _req: Any) -> Any:
            from harness.subprocess.validator.schemas import ValidationReport

            return ValidationReport(
                ok=True, issues=[], script_exit_code=0, duration_ms=1, http_status_hint=200
            )

    app.state.validator_runner = _OkRunner()
    prev = os.environ.get("HARNESS_STRICT_FEATURES")
    os.environ["HARNESS_STRICT_FEATURES"] = "preset_value"
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/validate/feature-list.json",
            json={"script": "validate_features", "timeout_s": 5.0},
        )
        assert resp.status_code == 200
        # After call, env should be restored to "preset_value", NOT removed.
        assert os.environ.get("HARNESS_STRICT_FEATURES") == "preset_value"
    finally:
        if prev is None:
            os.environ.pop("HARNESS_STRICT_FEATURES", None)
        else:
            os.environ["HARNESS_STRICT_FEATURES"] = prev


# ---------------------------------------------------------------------------
# harness.api.general_settings — load non-dict + PUT branches
# Traces To NFR-008 + IFR-006
# ---------------------------------------------------------------------------
def test_f22_general_settings_load_returns_empty_when_json_is_not_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_load_settings_dict` returns ``{}`` when config.json contains a
    non-dict JSON (e.g. a list) — line 103."""
    from harness.api import general_settings as gs

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path))
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    out = gs._load_settings_dict()
    assert out == {}


def test_f22_general_settings_build_response_drops_plaintext_field() -> None:
    """`_build_response` drops `_PLAINTEXT_FIELD` from carry-over (line 119)."""
    from harness.api import general_settings as gs

    stored = {
        "ui_density": "compact",
        gs._PLAINTEXT_FIELD: "ABCDEF",  # MUST not appear in output
        "extra_field": "kept",
    }
    out = gs._build_response(stored)
    assert gs._PLAINTEXT_FIELD not in out
    assert out["ui_density"] == "compact"
    assert out["extra_field"] == "kept"
    assert "keyring_backend" in out


def test_f22_general_settings_put_rejects_non_object_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PUT with non-dict body returns 400 ``validation`` (line 137)."""
    from harness.api import general_settings as gs

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path))
    app = FastAPI()
    app.include_router(gs.router)
    client = TestClient(app)
    resp = client.put(
        "/api/settings/general",
        json=["not", "a", "dict"],  # JSON array, not object
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "validation"


def test_f22_general_settings_put_carries_over_prev_ref_and_masked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When caller PUTs without supplying plaintext OR ref/masked, route
    carries over the previously-stored ones (lines 159-163)."""
    from harness.api import general_settings as gs

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path))
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "ui_density": "comfortable",
                "api_key_ref": {"service": "svcX", "user": "userX"},
                "api_key_masked": "***xyz",
            }
        ),
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(gs.router)
    client = TestClient(app)
    # Update only ui_density; expect prior api_key_ref / api_key_masked carried.
    resp = client.put("/api/settings/general", json={"ui_density": "compact"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ui_density"] == "compact"
    assert body["api_key_ref"] == {"service": "svcX", "user": "userX"}
    assert body["api_key_masked"] == "***xyz"


# ---------------------------------------------------------------------------
# harness.api.git_routes — _list_git_log skip + DiffNotFound fallback
# Traces To FR-041 + IFR-005
# ---------------------------------------------------------------------------
def test_f22_git_routes_list_git_log_skips_malformed_lines(tmp_path: Path) -> None:
    """`_list_git_log` skips lines whose `\\x1f`-split count != 5 (line 91)."""
    from harness.api import git_routes

    async def _runit() -> list[dict[str, Any]]:
        # Patch asyncio subprocess to emit malformed + valid lines.
        async def _fake_subproc(*_args: Any, **_kwargs: Any) -> Any:
            class _Proc:
                returncode = 0

                async def communicate(self) -> tuple[bytes, bytes]:
                    # 1 malformed (only 3 fields), 1 valid (5 fields).
                    valid = (
                        "deadbeef" + "0" * 32 + "\x1f" + "\x1f" + "Tester <t@e>" + "\x1f"
                        "2024-01-01T00:00:00Z" + "\x1f" + "subject"
                    )
                    bad = "abc\x1fdef\x1fghi"
                    return ((bad + "\n" + valid).encode(), b"")

            return _Proc()

        with patch.object(
            git_routes.asyncio, "create_subprocess_exec", side_effect=_fake_subproc
        ):
            return await git_routes._list_git_log(tmp_path, limit=10)

    rows = asyncio.run(_runit())
    assert len(rows) == 1
    assert rows[0]["subject"] == "subject"


def test_f22_git_routes_diff_falls_back_to_in_memory_loader_when_not_a_repo(
    tmp_path: Path,
) -> None:
    """When workdir is NOT a git repo, /api/git/diff/{sha} delegates to
    `app.state.diff_loader` (lines 119-122)."""
    from harness.api import git_routes

    app = FastAPI()
    app.include_router(git_routes.router)
    app.state.workdir = str(tmp_path)  # tmp_path has no .git, so _is_git_repo=False

    class _Loader:
        async def load_diff(self, sha: str) -> dict[str, Any]:
            return {"sha": sha, "files": [], "stats": {"insertions": 0, "deletions": 0}}

    app.state.diff_loader = _Loader()
    client = TestClient(app)
    resp = client.get("/api/git/diff/deadbeef")
    assert resp.status_code == 200
    assert resp.json()["sha"] == "deadbeef"


def test_f22_git_routes_diff_404_when_in_memory_loader_raises(tmp_path: Path) -> None:
    """Fallback DiffNotFound from in-memory loader → 404 ``diff_not_found``
    (lines 123-124)."""
    from harness.api import git_routes
    from harness.api.git import DiffNotFound

    app = FastAPI()
    app.include_router(git_routes.router)
    app.state.workdir = str(tmp_path)

    class _RaisingLoader:
        async def load_diff(self, sha: str) -> dict[str, Any]:
            raise DiffNotFound(sha)

    app.state.diff_loader = _RaisingLoader()
    client = TestClient(app)
    resp = client.get("/api/git/diff/missing-sha")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "diff_not_found"


def test_f22_git_routes_parse_unified_diff_skips_lines_with_no_diff_header() -> None:
    """`_parse_unified_diff` skips header-less prefix lines (line 166: `if
    current is None: continue`)."""
    from harness.api.git_routes import _parse_unified_diff

    # Garbage prefix BEFORE any `diff --git`.
    text = (
        "stray prelude line 1\n"
        "stray prelude line 2\n"
        "diff --git a/foo.py b/foo.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+hello\n"
    )
    files = _parse_unified_diff(text)
    assert len(files) == 1
    assert files[0]["path"] == "foo.py"


# ---------------------------------------------------------------------------
# harness.subprocess.validator.runner — terminate/kill ProcessLookupError swallow
# Traces To FR-039 + FR-040
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_f22_validator_runner_timeout_swallows_terminate_lookuperror(
    tmp_path: Path,
) -> None:
    """When `proc.terminate()` raises ProcessLookupError, runner still raises
    ValidatorTimeout (lines 108-109 explicit branch)."""
    from harness.subprocess.validator import runner as runner_mod
    from harness.subprocess.validator.runner import (
        ValidatorRunner,
        ValidatorTimeout,
    )
    from harness.subprocess.validator.schemas import ValidateRequest

    plugin_root = tmp_path / "plugin"
    scripts_dir = plugin_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "validate_features.py").write_text(
        "import time\ntime.sleep(60)\n",
        encoding="utf-8",
    )

    class _Proc:
        returncode = None

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.sleep(60)
            return (b"", b"")

        def terminate(self) -> None:
            raise ProcessLookupError("simulated terminate ENOENT")

        def kill(self) -> None:
            # Allow .kill() to succeed so we hit ONLY the terminate branch.
            return None

    async def _fake_create(*_args: Any, **_kwargs: Any) -> _Proc:
        return _Proc()

    runner_inst = ValidatorRunner(plugin_dir=plugin_root)
    req = ValidateRequest(
        path=str(tmp_path / "feature-list.json"),
        script="validate_features",
        workdir=str(tmp_path),
        timeout_s=0.05,
    )
    with patch.object(runner_mod.asyncio, "create_subprocess_exec", side_effect=_fake_create):
        with pytest.raises(ValidatorTimeout):
            await runner_inst.run(req)


@pytest.mark.asyncio
async def test_f22_validator_runner_timeout_swallows_kill_lookuperror(
    tmp_path: Path,
) -> None:
    """When `proc.kill()` raises ProcessLookupError, runner still raises
    ValidatorTimeout (lines 113-114 explicit branch)."""
    from harness.subprocess.validator import runner as runner_mod
    from harness.subprocess.validator.runner import (
        ValidatorRunner,
        ValidatorTimeout,
    )
    from harness.subprocess.validator.schemas import ValidateRequest

    plugin_root = tmp_path / "plugin"
    scripts_dir = plugin_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "validate_features.py").write_text(
        "import time\ntime.sleep(60)\n",
        encoding="utf-8",
    )

    class _Proc:
        returncode = None

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.sleep(60)
            return (b"", b"")

        def terminate(self) -> None:
            return None  # Allow .terminate() to succeed.

        def kill(self) -> None:
            raise ProcessLookupError("simulated kill ENOENT")

    async def _fake_create(*_args: Any, **_kwargs: Any) -> _Proc:
        return _Proc()

    runner_inst = ValidatorRunner(plugin_dir=plugin_root)
    req = ValidateRequest(
        path=str(tmp_path / "feature-list.json"),
        script="validate_features",
        workdir=str(tmp_path),
        timeout_s=0.05,
    )
    with patch.object(runner_mod.asyncio, "create_subprocess_exec", side_effect=_fake_create):
        with pytest.raises(ValidatorTimeout):
            await runner_inst.run(req)


@pytest.mark.asyncio
async def test_f22_validator_runner_uses_repo_root_fallback_when_plugin_script_missing(
    tmp_path: Path,
) -> None:
    """When `plugin_dir/scripts/<script>.py` is absent, runner falls back to
    the harness repo root scripts/<script>.py (line 80→82). Drives that fallback
    path with the real `scripts/validate_features.py` from this repo."""
    from harness.subprocess.validator.runner import ValidatorRunner
    from harness.subprocess.validator.schemas import ValidateRequest

    plugin_root = tmp_path / "empty-plugin"
    plugin_root.mkdir()
    # Stage a feature-list.json the real script can read.
    fl = tmp_path / "feature-list.json"
    fl.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0.0",
                "constraints": {},
                "assumptions": [],
                "features": [],
                "required_configs": [],
            }
        ),
        encoding="utf-8",
    )
    runner_inst = ValidatorRunner(plugin_dir=plugin_root)
    req = ValidateRequest(
        path=str(fl),
        script="validate_features",
        workdir=str(tmp_path),
        timeout_s=20.0,
    )
    report = await runner_inst.run(req)
    # Real script ran; we don't care if ok=True/False, just that it executed.
    assert report.script_exit_code in (0, 1)


# ---------------------------------------------------------------------------
# harness.api.git_routes — registry-empty fallback to git log inside real repo
# Traces To IFR-005 + FR-041
# ---------------------------------------------------------------------------
def test_f22_git_commits_falls_back_to_git_log_when_registry_empty(
    tmp_path: Path,
) -> None:
    """When workdir IS a git repo and `commit_list_service.list_commits()`
    returns empty, route augments output with `_list_git_log` (line 69)."""
    from harness.api import git_routes

    # Initialize a fresh git repo with one commit so `git log` returns >= 1 row.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Tester"],
        check=True,
        capture_output=True,
    )
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "a.txt"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "initial: feat"],
        check=True,
        capture_output=True,
    )

    app = FastAPI()
    app.include_router(git_routes.router)
    app.state.workdir = str(tmp_path)

    class _EmptyService:
        async def list_commits(self, *, run_id: Any = None, feature_id: Any = None) -> list[Any]:
            return []  # Empty registry → triggers git-log fallback (line 69).

    app.state.commit_list_service = _EmptyService()
    client = TestClient(app)
    resp = client.get("/api/git/commits")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    assert rows[0]["subject"] == "initial: feat"


# ---------------------------------------------------------------------------
# harness.api.__init__ — health endpoint cached/uncached branches
# F22 IAPI-002 augmented this app with general_settings + validate routers; the
# /api/health endpoint MUST surface the F22-augmented bind/auth/cli surface
# correctly when the lifespan cache is unpopulated (test path).
# Traces To NFR-008 + IFR-006
# ---------------------------------------------------------------------------
def test_f22_health_endpoint_uses_cached_claude_auth_when_state_missing() -> None:
    """When ``app.state.claude_auth_status`` is None but
    ``app.state._health_cache`` is fresh, /api/health returns the cached value.

    F24 B9 sanctioned drift: cache shape changed from
    ``{cli_versions, claude_auth}`` → ``{_value: {cli_versions, claude_auth},
    _ts: monotonic}`` to support TTL semantics.
    """
    import time
    from harness.api import app
    from harness.auth import ClaudeAuthStatus

    fake_auth = ClaudeAuthStatus(
        cli_present=True,
        authenticated=True,
        hint=None,
        source="claude-cli",
    )
    # Post-B9 cache shape: nest under `_value` + monotonic `_ts` so the TTL
    # check (now - _ts <= TTL_SEC) succeeds and returns cached payload.
    app.state._health_cache = {
        "_value": {
            "cli_versions": {"claude": "claude 1.0", "opencode": None},
            "claude_auth": fake_auth,
        },
        "_ts": time.monotonic(),
    }
    # Ensure no claude_auth_status overrides cache.
    if hasattr(app.state, "claude_auth_status"):
        delattr(app.state, "claude_auth_status")
    client = TestClient(app)
    try:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["claude_auth"]["cli_present"] is True
        assert body["claude_auth"]["authenticated"] is True
        # cli_versions sourced from cache.
        assert body["cli_versions"]["claude"] == "claude 1.0"
    finally:
        if hasattr(app.state, "_health_cache"):
            delattr(app.state, "_health_cache")


def test_f22_health_endpoint_falls_back_to_live_detect_when_no_cache() -> None:
    """When neither ``app.state.claude_auth_status`` nor ``_health_cache`` is
    set, /api/health falls back to a live ``ClaudeAuthDetector().detect()``
    call AND a live `_probe_cli_version()` (lines 144 + 149)."""
    from harness.api import app

    # Remove any prior state so route hits the fallback branches.
    if hasattr(app.state, "claude_auth_status"):
        delattr(app.state, "claude_auth_status")
    if hasattr(app.state, "_health_cache"):
        delattr(app.state, "_health_cache")
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "claude_auth" in body
    assert "cli_versions" in body
    assert isinstance(body["cli_versions"], dict)
