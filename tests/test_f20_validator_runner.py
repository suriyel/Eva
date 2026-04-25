"""F20 · ValidatorRunner / IAPI-016 unit tests (T23/T25/T26).

[unit] — subprocess mocked at asyncio.create_subprocess_exec boundary. T24 (real
validate_features.py) lives in tests/integration/test_f20_real_subprocess.py.

Feature ref: feature_20

Traces To:
  T23 → FR-039 + Interface Contract `validate_file` postcondition
  T25 → FR-040 AC-2 errors not swallowed (stderr_tail in issues)
  T26 → FR-040 + Boundary `ValidatorRunner.timeout_s`
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.asyncio


def _mock_proc(
    stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0, communicate_delay: float = 0.0
) -> Any:
    proc = MagicMock()
    if communicate_delay:

        async def _delayed() -> tuple[bytes, bytes]:
            await asyncio.sleep(communicate_delay)
            return (stdout, stderr)

        proc.communicate = _delayed
    else:
        proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.pid = 5151
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=returncode)
    return proc


# ---- T23 -------------------------------------------------------------------
async def test_t23_validator_happy_path_returns_ok_report(tmp_path: Path) -> None:
    """T23 FUNC/happy: exit=0 stdout {'ok':true,'issues':[]} → ValidationReport(ok=True, duration_ms>0)."""
    from harness.subprocess.validator.runner import ValidatorRunner
    from harness.subprocess.validator.schemas import ValidateRequest, ValidationReport

    runner = ValidatorRunner(plugin_dir=tmp_path)
    payload = {"ok": True, "issues": []}
    proc = _mock_proc(stdout=json.dumps(payload).encode(), returncode=0)

    fl = tmp_path / "feature-list.json"
    fl.write_text("{}")

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        report: ValidationReport = await runner.run(
            ValidateRequest(path=str(fl), script="validate_features", workdir=tmp_path)
        )

    assert report.ok is True
    assert report.script_exit_code == 0
    assert report.duration_ms >= 0  # may be 0 with mocks but field must exist
    assert report.issues == []


# ---- T25 -------------------------------------------------------------------
async def test_t25_validator_exit_nonzero_does_not_swallow_stderr(tmp_path: Path) -> None:
    """T25 FUNC/error: exit=2 stderr non-empty → ValidationReport(ok=False, issues[0].message contains stderr_tail); HTTP 200."""
    from harness.subprocess.validator.runner import ValidatorRunner
    from harness.subprocess.validator.schemas import ValidateRequest

    runner = ValidatorRunner(plugin_dir=tmp_path)
    proc = _mock_proc(stdout=b"", stderr=b"FileNotFoundError: feature-list.json", returncode=2)

    fl = tmp_path / "feature-list.json"

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        report = await runner.run(
            ValidateRequest(path=str(fl), script="validate_features", workdir=tmp_path)
        )

    assert report.ok is False
    assert report.script_exit_code == 2
    assert len(report.issues) >= 1
    msgs = " ".join(i.message for i in report.issues)
    assert (
        "FileNotFoundError" in msgs
    ), f"FR-040 AC-2: stderr must NOT be swallowed; got issues={report.issues}"
    # HTTP-200 is enforced at REST layer; ensure runner does NOT raise
    assert report.http_status_hint == 200, "errors-as-data, not server error"


# ---- T26 -------------------------------------------------------------------
async def test_t26_validator_timeout_raises_validator_timeout(tmp_path: Path) -> None:
    """T26 BNDRY/edge: subprocess takes >timeout_s → ValidatorTimeout with stderr_tail='validator timeout'."""
    from harness.subprocess.validator.runner import ValidatorRunner, ValidatorTimeout
    from harness.subprocess.validator.schemas import ValidateRequest

    runner = ValidatorRunner(plugin_dir=tmp_path)
    proc = _mock_proc(stdout=b"", returncode=0, communicate_delay=0.5)

    fl = tmp_path / "feature-list.json"

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(ValidatorTimeout) as excinfo:
            await runner.run(
                ValidateRequest(
                    path=str(fl), script="validate_features", workdir=tmp_path, timeout_s=0.1
                )
            )

    assert "timeout" in str(excinfo.value).lower()
    assert excinfo.value.http_status == 500
    # process must have been signalled
    assert proc.terminate.called or proc.kill.called, "timeout must terminate the subprocess"
