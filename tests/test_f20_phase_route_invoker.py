"""F20 · PhaseRouteInvoker unit tests (T03/T04/T06/T07/T08/T31).

[unit] — subprocess mocked at asyncio.create_subprocess_exec boundary; the invoker
itself is exercised end-to-end (no internal mocks). T05 (real subprocess) is in
tests/integration/test_f20_real_subprocess.py.

Wave 5 [API-W5-02] note: ``PhaseRouteInvoker.invoke`` defaults to the in-proc
``phase_route_local.route`` path; these legacy unit tests opt into the
[DEPRECATED Wave 5] subprocess fallback by setting
``HARNESS_PHASE_ROUTE_FALLBACK=1`` (matches design §7 T07/T08 setup).

Feature ref: feature_20

Traces To:
  T03 → §Interface Contract `PhaseRouteInvoker.invoke` postcondition
  T04 → §Interface Contract `PhaseRouteInvoker.invoke` Raises PhaseRouteError
  T06 → NFR-015 PhaseRouteResult extra='ignore' relaxed parsing
  T07 → IFR-003 stdout-not-JSON failure mode → PhaseRouteParseError
  T08 → FR-003 hotfix signal transparently passed via skill_hint
  T31 → FR-047 AC-2 not hardcoded — unknown skill name still dispatchable
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _enable_subprocess_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wave 5: opt every test in this module into the subprocess fallback path.

    Design §6/§8 make ``await asyncio.to_thread(phase_route_local.route, ...)``
    the default; ``HARNESS_PHASE_ROUTE_FALLBACK=1`` flips back to the
    legacy ``asyncio.create_subprocess_exec`` path that these tests pin.
    """
    monkeypatch.setenv("HARNESS_PHASE_ROUTE_FALLBACK", "1")


def _mock_proc(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0) -> Any:
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.pid = 4242
    proc.wait = AsyncMock(return_value=returncode)
    proc.kill = MagicMock()
    proc.terminate = MagicMock()
    return proc


# ---- T03 -------------------------------------------------------------------
async def test_t03_invoke_happy_path_returns_phase_route_result(tmp_path: Path) -> None:
    """T03 FUNC/happy: stdout JSON → PhaseRouteResult fields preserved verbatim."""
    from harness.orchestrator.phase_route import PhaseRouteInvoker, PhaseRouteResult

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    payload = {
        "ok": True,
        "next_skill": "long-task-design",
        "feature_id": None,
        "counts": {"work": 3},
    }
    proc = _mock_proc(stdout=json.dumps(payload).encode(), returncode=0)

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result: PhaseRouteResult = await invoker.invoke(workdir=tmp_path)

    assert result.ok is True
    assert result.next_skill == "long-task-design"
    assert result.feature_id is None
    assert result.counts == {"work": 3}


# ---- T04 -------------------------------------------------------------------
async def test_t04_invoke_exit_nonzero_raises_phase_route_error(tmp_path: Path) -> None:
    """T04 FUNC/error: subprocess exit=2 stderr non-empty → PhaseRouteError + tail captured."""
    from harness.orchestrator.errors import PhaseRouteError
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    proc = _mock_proc(stdout=b"", stderr=b"feature-list.json missing", returncode=2)

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(PhaseRouteError) as excinfo:
            await invoker.invoke(workdir=tmp_path)

    assert "feature-list.json missing" in str(excinfo.value)


# ---- T06 -------------------------------------------------------------------
async def test_t06_relaxed_parsing_default_fields(tmp_path: Path) -> None:
    """T06 BNDRY/edge: stdout {'ok':true} (missing fields) → defaults; new field 'extras' ignored."""
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)

    # Fixture A — only `ok`
    proc_a = _mock_proc(stdout=b'{"ok":true}', returncode=0)
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc_a)):
        a = await invoker.invoke(workdir=tmp_path)
    assert a.ok is True
    assert a.next_skill is None  # default
    assert a.feature_id is None  # default
    assert a.starting_new is False  # default
    assert a.needs_migration is False  # default
    assert a.counts is None  # default
    assert a.errors == []  # default

    # Fixture B — extras ignored
    payload = {"ok": True, "next_skill": "x", "extras": {"new_field": 1, "future": [1, 2]}}
    proc_b = _mock_proc(stdout=json.dumps(payload).encode(), returncode=0)
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc_b)):
        b = await invoker.invoke(workdir=tmp_path)
    assert b.next_skill == "x"
    # extras must be silently ignored — no ValidationError
    assert not hasattr(b, "extras") or getattr(b, "extras", None) in (None, {})


# ---- T07 -------------------------------------------------------------------
async def test_t07_stdout_not_json_raises_parse_error_and_audits(tmp_path: Path) -> None:
    """T07 BNDRY/edge: stdout='not a json' exit=0 → PhaseRouteParseError + audit phase_route_parse_error."""
    from harness.orchestrator.errors import PhaseRouteParseError
    from harness.orchestrator.phase_route import PhaseRouteInvoker

    audit_calls: list[tuple[str, dict[str, Any]]] = []

    class FakeAudit:
        async def append_raw(self, run_id, kind, payload, ts):  # noqa: D401
            audit_calls.append((kind, payload))

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path, audit_writer=FakeAudit(), run_id="r-1")
    proc = _mock_proc(stdout=b"not a json", returncode=0)

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        with pytest.raises(PhaseRouteParseError):
            await invoker.invoke(workdir=tmp_path)

    kinds = [c[0] for c in audit_calls]
    assert (
        "phase_route_parse_error" in kinds
    ), f"audit must record phase_route_parse_error; got {kinds!r}"


# ---- T08 -------------------------------------------------------------------
async def test_t08_hotfix_signal_passed_through_via_skill_hint(tmp_path: Path) -> None:
    """T08 FUNC/happy: phase_route returns next_skill='long-task-hotfix' → TicketCommand.skill_hint identical."""
    from harness.orchestrator.phase_route import PhaseRouteInvoker
    from harness.orchestrator.supervisor import build_ticket_command

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    payload = {"ok": True, "next_skill": "long-task-hotfix", "feature_id": None}
    proc = _mock_proc(stdout=json.dumps(payload).encode(), returncode=0)

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await invoker.invoke(workdir=tmp_path)

    cmd = build_ticket_command(result, parent=None)
    assert (
        cmd.skill_hint == "long-task-hotfix"
    ), "FR-003 requires hotfix signal transparently passed; orchestrator must NOT rewrite skill_hint"


# ---- T31 -------------------------------------------------------------------
async def test_t31_unknown_skill_name_dispatchable(tmp_path: Path) -> None:
    """T31 BNDRY/edge: phase_route returns next_skill='long-task-future-skill-xyz' (not in 14-set) → TicketCommand built without UnknownSkill."""
    from harness.orchestrator.phase_route import PhaseRouteInvoker
    from harness.orchestrator.supervisor import build_ticket_command

    invoker = PhaseRouteInvoker(plugin_dir=tmp_path)
    payload = {"ok": True, "next_skill": "long-task-future-skill-xyz"}
    proc = _mock_proc(stdout=json.dumps(payload).encode(), returncode=0)

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
        result = await invoker.invoke(workdir=tmp_path)

    # Builder must not raise UnknownSkill etc.
    cmd = build_ticket_command(result, parent=None)
    assert (
        cmd.skill_hint == "long-task-future-skill-xyz"
    ), "FR-047 AC-2: skill names are NOT a hardcoded enum; future skills must dispatch transparently"
