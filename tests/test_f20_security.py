"""F20 · Security tests (T37/T38).

[unit] — path traversal + argv injection threat models for IAPI-002 file APIs +
phase_route subprocess exec.

Feature ref: feature_20

Traces To:
  T37 → §Interface Contract `read_file_tree` / `read_file_content` Raises PathTraversalError
  T38 → IFR-003 + IFR-005 ATS Hint subprocess argv NOT shell-piped
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


# ---- T37 -------------------------------------------------------------------
async def test_t37_path_traversal_blocked(tmp_path: Path) -> None:
    """T37 SEC/path-traversal: read_file_content('../etc/passwd') → PathTraversalError 400."""
    from harness.api.files import FilesService, PathTraversalError

    svc = FilesService(workdir=tmp_path)

    bad_paths = [
        "../etc/passwd",
        "../../etc/passwd",
        "subdir/../../../etc/passwd",
        "/etc/passwd",  # absolute outside workdir
    ]
    for p in bad_paths:
        with pytest.raises(PathTraversalError) as excinfo:
            await svc.read_file_content(p)
        assert excinfo.value.http_status == 400, f"path={p!r} must yield 400; got {excinfo.value}"


# ---- T38 -------------------------------------------------------------------
async def test_t38_subprocess_argv_no_shell_injection(tmp_path: Path) -> None:
    """T38 SEC/argv-injection: malicious workdir string never passed through a shell.

    1. start_run with workdir containing '; rm -rf /' rejects (invalid path).
    2. PhaseRouteInvoker.invoke uses asyncio.create_subprocess_exec (argv list, NOT shell=True),
       so even if a malicious string slipped past validation, no command substitution occurs.
    """
    from harness.orchestrator.errors import RunStartError
    from harness.orchestrator.phase_route import PhaseRouteInvoker
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest

    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    bad_workdir = str(tmp_path) + "; rm -rf /"

    with pytest.raises(RunStartError) as excinfo:
        await orch.start_run(RunStartRequest(workdir=bad_workdir))
    # Must be invalid_workdir / not_a_git_repo, NOT executed as shell
    assert excinfo.value.reason in {
        "invalid_workdir",
        "not_a_git_repo",
    }, f"expected workdir validation rejection; got reason={excinfo.value.reason!r}"

    # Module-level guarantee: invoker uses argv list, not shell
    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    assert (
        invoker.uses_shell is False
    ), "IFR-003 SEC: PhaseRouteInvoker MUST use create_subprocess_exec (no shell=True)"
    # The exec_argv builder must produce a list (not a single shell string)
    argv = invoker.build_argv(workdir=tmp_path)
    assert isinstance(argv, list)
    assert all(isinstance(a, str) for a in argv)
    # No shell metacharacters wrapped — first element is python, second is path
    assert argv[0].endswith("python") or argv[0].endswith("python3") or "python" in argv[0]
