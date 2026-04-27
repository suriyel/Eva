"""F20 Wave 5 (2026-04-28) hard-flush — Test Inventory T22/T23/T25 + T61..T87
from feature design §7 (Wave 5 NEW rows).

Authoritative tests for F20 Bk-Loop after the Wave 5 hard reset:
  [F] phase_route 内化 (FR-054, API-W5-01..03)
  [G] spawn 内置 skill inject (FR-055, API-W5-04/05)
  [A] retry 真集成 (T22/T23/T25 升集成 — supervisor.run_ticket 接线
      RetryPolicy + RetryCounter + 递归重入 _run_ticket_impl)
  [B] SignalFileWatcher 真集成 (FR-048 双 AC, API-W5-06/10)
  [C] cosmetic — record_call → _record_call private (API-W5-09)

Every test maps 1:1 to a row in
``docs/features/20-f20-bk-loop-run-orchestrator-recovery-su.md`` §Test Inventory
(Wave 5 increment rows). RED phase: every test MUST fail because Wave 5
implementation is not yet in place.

Real test policy: This feature does NOT trigger IFR-004 (OpenAI-compat HTTP).
Real claude-cli markers used by INT-026 (T79) + SKILL.md marker (T80) follow
the project ``real_cli`` marker convention; both are skipped at collection
when claude binary is missing — but they MUST FAIL (not skip) when claude is
present and the implementation is incomplete (current Red state). A real_fs
filesystem-port test (test_w5_real_route_real_fixture_fixture_d) anchors the
``check_real_tests.py`` discovery for feature_20 W5.

Provider tally per design §7: mock=N1=68, claude-cli=3, minimax-http=0.

[unit] coverage scope:
  - phase_route_local (T61..T70): in-proc same-process route() function.
  - feature_list_io (T84/T85): pure ports of plugin scripts.
  - on_signal broadcast (T82): RunControlBus + rt.signal_dirty bookkeeping.
  - cosmetic regression (T83): rg sweep on harness/ + tests/.
  - SkillDispatchError sub-class (T77): isinstance check.

[integration] markers:
  - T71 / T86: cross-impl plugin v1.0.0 vs in-proc port (real subprocess).
  - T79 / T80: real claude-cli + plugin (real_cli marker).
  - T81: cooperative wait (asyncio + signal watcher real fs).
"""

# real_test  --  marker keyword for check_real_tests.py discovery (feature_20)

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.asyncio


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPTS_DIR = REPO_ROOT / "scripts"


# ---------------------------------------------------------------------------
# Helpers — Wave 5 fixture factories (6 priority layers + count_pending shapes)
# ---------------------------------------------------------------------------
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
            "init",
        ],
        cwd=workdir,
        check=True,
    )


def _make_fixture_a_bugfix(root: Path) -> Path:
    """Priority 1 — bugfix-request.json present."""
    (root / "bugfix-request.json").write_text(json.dumps({"reason": "x"}))
    return root


def _make_fixture_b_increment(root: Path) -> Path:
    """Priority 2 — increment-request.json present."""
    (root / "increment-request.json").write_text(json.dumps({"reason": "y"}))
    return root


def _make_minimal_feature_list(features: list, current=None) -> dict:
    return {
        "version": "1.0.0",
        "features": features,
        "current": current,
        "tech_stack": {"language": "python"},
    }


def _make_fixture_c_work_design(root: Path) -> Path:
    """Priority 3a — feature-list.json with current.feature_id+phase=design."""
    fl = _make_minimal_feature_list(
        [
            {
                "id": 1,
                "category": "core",
                "title": "F1",
                "description": "x",
                "priority": "high",
                "status": "failing",
            },
        ],
        current={"feature_id": 1, "phase": "design"},
    )
    (root / "feature-list.json").write_text(json.dumps(fl))
    return root


def _make_fixture_d_all_passing(root: Path) -> Path:
    """Priority 3c — feature-list.json with all features passing → ST."""
    fl = _make_minimal_feature_list(
        [
            {
                "id": 1,
                "category": "core",
                "title": "F1",
                "description": "x",
                "priority": "high",
                "status": "passing",
            },
            {
                "id": 2,
                "category": "core",
                "title": "F2",
                "description": "y",
                "priority": "medium",
                "status": "passing",
            },
        ],
        current=None,
    )
    (root / "feature-list.json").write_text(json.dumps(fl))
    return root


def _make_fixture_e_srs_only(root: Path) -> Path:
    """Priority 4 — only docs/plans/*-srs.md present (no ats/design/ucd)."""
    plans = root / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-x-srs.md").write_text("# SRS\n")
    return root


def _make_fixture_f_empty(root: Path) -> Path:
    """Priority 6 — empty workdir → default long-task-requirements."""
    return root


def _make_corrupt_feature_list(root: Path) -> Path:
    (root / "feature-list.json").write_text('{"current":}')  # invalid JSON
    return root


def _make_count_pending_fixture(root: Path, *, passing: int, failing: int, deprecated: int) -> Path:
    features = []
    fid = 1
    for _ in range(passing):
        features.append(
            {
                "id": fid,
                "category": "core",
                "title": f"F{fid}",
                "description": "x",
                "priority": "low",
                "status": "passing",
            }
        )
        fid += 1
    for _ in range(failing):
        features.append(
            {
                "id": fid,
                "category": "core",
                "title": f"F{fid}",
                "description": "x",
                "priority": "low",
                "status": "failing",
            }
        )
        fid += 1
    for _ in range(deprecated):
        features.append(
            {
                "id": fid,
                "category": "core",
                "title": f"F{fid}",
                "description": "x",
                "priority": "low",
                "status": "passing",
                "deprecated": True,
            }
        )
        fid += 1
    fl = _make_minimal_feature_list(features)
    path = root / "feature-list.json"
    path.write_text(json.dumps(fl))
    return path


# ===========================================================================
# T22 / T23 / T25 — retry 真集成 (Wave 5 升集成)
# ===========================================================================
# These three replace the W4 pure-function variants with INTG/recovery tests
# that drive supervisor.run_ticket through the new retry block: classifier
# returns next_action="retry" → RetryCounter.value → RetryPolicy.next_delay
# → (None: ABORTED+Escalated | float: RetryCounter.inc + sleep + recurse).


class _ConfigurableClassifier:
    """Test-fake classifier whose verdict can flip per call (drives retry)."""

    def __init__(self, sequence: list[dict]) -> None:
        self._seq = list(sequence)
        self._idx = 0
        self.calls = 0

    async def classify_request(self, proc: Any) -> Any:
        from harness.dispatch.classifier.models import Verdict

        self.calls += 1
        idx = min(self._idx, len(self._seq) - 1)
        self._idx += 1
        spec = self._seq[idx]
        return Verdict(
            verdict=spec.get("verdict", "RETRY"),
            reason=spec.get("anomaly") or "ok",
            anomaly=spec.get("anomaly"),
            backend="rule",
        )


# ---- T22 -----------------------------------------------------------------
async def test_t22_w5_supervisor_integrates_retry_for_context_overflow(
    tmp_path: Path,
) -> None:
    """T22 INTG/recovery [Wave 5 升集成]: classifier returns context_overflow 4
    times. Wave 5 supervisor.run_ticket must consume RetryPolicy + RetryCounter
    and recurse — first 3 calls increment counter (1/2/3) then 4th call returns
    next_delay=None → ABORTED + broadcast Escalated.

    Traces To: FR-024 / NFR-003 / §Implementation Summary flow branch RetryDelay.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import TicketCommand

    _git_init(tmp_path)
    classifier = _ConfigurableClassifier([{"verdict": "RETRY", "anomaly": "context_overflow"}] * 5)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.classifier = classifier
    # Track Escalated broadcasts.
    escalated: list[Any] = []
    orig_broadcast = orch.control_bus.broadcast_anomaly

    def _capture_anomaly(event: Any) -> None:
        if getattr(event, "kind", "") == "Escalated":
            escalated.append(event)
        return orig_broadcast(event)

    orch.control_bus.broadcast_anomaly = _capture_anomaly  # type: ignore[assignment]

    cmd = TicketCommand(
        kind="spawn",
        skill_hint="long-task-design",
        run_id="run-w5-t22",
    )
    outcome = await orch.ticket_supervisor.run_ticket(cmd)

    # After exhausting retries (3 retries, 4th call escalates), counter must
    # show exactly 3 inc calls for "long-task-design"; final state ABORTED;
    # exactly 1 Escalated broadcast (NFR-003 第 3 次 escalate).
    assert (
        orch.retry_counter.value("long-task-design") == 3
    ), f"expected 3 inc()s; got {orch.retry_counter.value('long-task-design')}"
    assert (
        outcome.final_state == "aborted"
    ), f"expected ABORTED after 3rd retry exhausted; got {outcome.final_state!r}"
    assert len(escalated) == 1, f"expected exactly 1 Escalated broadcast; got {len(escalated)}"


# ---- T23 -----------------------------------------------------------------
async def test_t23_w5_supervisor_integrates_retry_for_rate_limit_with_scale(
    tmp_path: Path,
) -> None:
    """T23 INTG/recovery [Wave 5 升集成]: rate_limit ×4 + scale_factor=0.001
    compresses 30/120/300s → 0.030/0.120/0.300s. Supervisor must sleep the
    correct delay each time and recurse; 4th call escalates.

    Traces To: FR-025 / NFR-004 ±10% / §Implementation Summary flow.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.recovery.retry import RetryPolicy
    from harness.orchestrator.schemas import TicketCommand

    _git_init(tmp_path)
    classifier = _ConfigurableClassifier([{"verdict": "RETRY", "anomaly": "rate_limit"}] * 5)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.classifier = classifier
    orch.retry_policy = RetryPolicy(scale_factor=0.001)

    sleep_log: list[float] = []
    orig_sleep = asyncio.sleep

    async def _spy_sleep(delay: float, *a: Any, **kw: Any) -> Any:
        if delay >= 0.0001:  # filter epsilon yields
            sleep_log.append(delay)
        return await orig_sleep(0)

    cmd = TicketCommand(
        kind="spawn",
        skill_hint="long-task-tdd",
        run_id="run-w5-t23",
    )
    with patch("asyncio.sleep", new=_spy_sleep):
        outcome = await orch.ticket_supervisor.run_ticket(cmd)

    # Expect 3 sleeps: 0.030s, 0.120s, 0.300s (±10% tolerance).
    assert len(sleep_log) == 3, f"expected 3 retry sleeps; got {sleep_log}"
    expected = [0.030, 0.120, 0.300]
    for got, exp in zip(sleep_log, expected):
        assert exp * 0.9 <= got <= exp * 1.1, f"sleep {got} not within ±10% of {exp}"
    assert outcome.final_state == "aborted"


# ---- T25 -----------------------------------------------------------------
async def test_t25_w5_supervisor_integrates_retry_for_network(
    tmp_path: Path,
) -> None:
    """T25 INTG/recovery [Wave 5 升集成]: network ×3 + scale_factor=0.001 →
    1st sleep=0.0, 2nd=0.060s, 3rd escalate.

    Traces To: FR-026 / §Implementation Summary flow.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.recovery.retry import RetryPolicy
    from harness.orchestrator.schemas import TicketCommand

    _git_init(tmp_path)
    classifier = _ConfigurableClassifier([{"verdict": "RETRY", "anomaly": "network"}] * 4)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    orch.classifier = classifier
    orch.retry_policy = RetryPolicy(scale_factor=0.001)

    sleep_log: list[float] = []
    orig_sleep = asyncio.sleep

    async def _spy_sleep(delay: float, *a: Any, **kw: Any) -> Any:
        sleep_log.append(delay)
        return await orig_sleep(0)

    cmd = TicketCommand(
        kind="spawn",
        skill_hint="long-task-st",
        run_id="run-w5-t25",
    )
    with patch("asyncio.sleep", new=_spy_sleep):
        outcome = await orch.ticket_supervisor.run_ticket(cmd)

    # Two retries: sleep[0]==0.0, sleep[1]==0.060 ±10%; then escalate.
    assert len(sleep_log) == 2, f"expected 2 retry sleeps; got {sleep_log}"
    assert sleep_log[0] == 0.0, f"first network retry must be immediate; got {sleep_log[0]}"
    assert 0.054 <= sleep_log[1] <= 0.066, f"second sleep {sleep_log[1]} not within ±10% of 0.060"
    assert outcome.final_state == "aborted"


# ===========================================================================
# T61..T71 — phase_route_local 内化 (FR-054 / API-W5-01..03)
# ===========================================================================


# ---- T61 -----------------------------------------------------------------
async def test_t61_phase_route_local_runs_in_process_zero_subprocess(
    tmp_path: Path,
) -> None:
    """T61 FUNC/happy: phase_route_local.route() must run in-proc — no
    subprocess.Popen / asyncio.create_subprocess_exec calls in its stack.

    Traces To: FR-054 AC-1 / API-W5-01.
    """
    from harness.orchestrator import phase_route_local

    _make_fixture_f_empty(tmp_path)

    popen_calls = 0
    exec_calls = 0

    def _track_popen(*a: Any, **kw: Any) -> Any:
        nonlocal popen_calls
        popen_calls += 1
        raise AssertionError("phase_route_local.route must not call subprocess.Popen")

    async def _track_exec(*a: Any, **kw: Any) -> Any:
        nonlocal exec_calls
        exec_calls += 1
        raise AssertionError("phase_route_local.route must not call asyncio.create_subprocess_exec")

    with (
        patch("subprocess.Popen", new=_track_popen),
        patch("asyncio.create_subprocess_exec", new=_track_exec),
    ):
        result = phase_route_local.route(tmp_path)

    assert isinstance(result, dict)
    assert popen_calls == 0
    assert exec_calls == 0


# ---- T62 -----------------------------------------------------------------
def test_t62_phase_route_local_dict_keys_are_canonical(tmp_path: Path) -> None:
    """T62 FUNC/happy: returned dict.keys() across all 6 fixtures must equal
    canonical set EXACTLY (==), not superset.

    Traces To: FR-054 AC-2 / API-W5-01.
    """
    from harness.orchestrator import phase_route_local

    canonical = {
        "ok",
        "errors",
        "needs_migration",
        "counts",
        "next_skill",
        "feature_id",
        "starting_new",
    }

    fixtures = [
        ("a_bugfix", _make_fixture_a_bugfix),
        ("b_increment", _make_fixture_b_increment),
        ("c_work_design", _make_fixture_c_work_design),
        ("d_all_passing", _make_fixture_d_all_passing),
        ("e_srs_only", _make_fixture_e_srs_only),
        ("f_empty", _make_fixture_f_empty),
    ]
    for name, factory in fixtures:
        sub = tmp_path / name
        sub.mkdir()
        factory(sub)
        out = phase_route_local.route(sub)
        assert set(out.keys()) == canonical, (
            f"fixture {name!r} key mismatch: "
            f"extra={set(out.keys()) - canonical}, "
            f"missing={canonical - set(out.keys())}"
        )


# ---- T63 -----------------------------------------------------------------
def test_t63_phase_route_local_perf_under_50ms_for_100kb(tmp_path: Path) -> None:
    """T63 PERF/timing: feature-list.json with 500 features (~100KB) → route()
    typical ≤ 5ms; hard cap ≤ 50ms over 100 invocations.

    Traces To: FR-054 AC-3.
    """
    from harness.orchestrator import phase_route_local

    big = _make_minimal_feature_list(
        [
            {
                "id": i,
                "category": "core",
                "title": f"F{i}",
                "description": "x" * 50,
                "priority": "low",
                "status": "passing" if i % 3 else "failing",
            }
            for i in range(1, 501)
        ],
        current=None,
    )
    path = tmp_path / "feature-list.json"
    path.write_text(json.dumps(big))
    # Confirm fixture is the right size band.
    size_kb = path.stat().st_size / 1024
    assert 50 < size_kb < 200, f"fixture not ~100KB; got {size_kb:.1f}KB"

    samples: list[float] = []
    for _ in range(100):
        t0 = time.perf_counter()
        phase_route_local.route(tmp_path)
        samples.append(time.perf_counter() - t0)

    worst = max(samples)
    assert worst <= 0.050, f"hard cap 50ms exceeded; worst={worst*1000:.1f}ms"


# ---- T64 -----------------------------------------------------------------
def test_t64_phase_route_local_priority1_bugfix(tmp_path: Path) -> None:
    """T64 FUNC/happy: only bugfix-request.json present → next_skill=long-task-hotfix.

    Traces To: FR-054 AC-4 / §State Diagram CheckBugfix→EmitHotfix / INT-027 第 1 层.
    """
    from harness.orchestrator import phase_route_local

    _make_fixture_a_bugfix(tmp_path)
    out = phase_route_local.route(tmp_path)
    assert out["next_skill"] == "long-task-hotfix"
    assert out["ok"] is True


# ---- T65 -----------------------------------------------------------------
def test_t65_phase_route_local_priority2_increment(tmp_path: Path) -> None:
    """T65 FUNC/happy: only increment-request.json → long-task-increment.

    Traces To: FR-054 AC-4 / §State Diagram CheckIncrement→EmitIncrement.
    """
    from harness.orchestrator import phase_route_local

    _make_fixture_b_increment(tmp_path)
    out = phase_route_local.route(tmp_path)
    assert out["next_skill"] == "long-task-increment"
    assert out["ok"] is True


# ---- T66 -----------------------------------------------------------------
def test_t66_phase_route_local_priority3a_current_design(tmp_path: Path) -> None:
    """T66 FUNC/happy: feature-list.json + current={feature_id:1,phase:design}
    → long-task-work-design + feature_id=1.

    Traces To: FR-054 AC-4 / §State Diagram CheckFeatureList→EmitWorkPhase.
    """
    from harness.orchestrator import phase_route_local

    _make_fixture_c_work_design(tmp_path)
    out = phase_route_local.route(tmp_path)
    assert out["next_skill"] == "long-task-work-design"
    assert out["feature_id"] == 1


# ---- T67 -----------------------------------------------------------------
def test_t67_phase_route_local_priority3c_all_passing_st(tmp_path: Path) -> None:
    """T67 FUNC/happy: all features passing + current=null → long-task-st.

    Traces To: FR-054 AC-4 / §State Diagram CheckFeatureList→EmitST.
    """
    from harness.orchestrator import phase_route_local

    _make_fixture_d_all_passing(tmp_path)
    out = phase_route_local.route(tmp_path)
    assert out["next_skill"] == "long-task-st"


# ---- T68 -----------------------------------------------------------------
def test_t68_phase_route_local_priority4_srs_only_returns_ucd(tmp_path: Path) -> None:
    """T68 FUNC/happy: only docs/plans/*-srs.md present → next ladder is
    long-task-ucd (per scripts/phase_route.py reference: srs.md → next is ucd).

    Note: Design §Test Inventory T68 example says "long-task-design" but plugin
    v1.0.0 reference (scripts/phase_route.py:182-184) routes srs.md → ucd. We
    assert the AUTHORITATIVE plugin behaviour to keep API-W5-01/IAPI-022 cross-
    impl parity.

    Traces To: FR-054 AC-4 / §State Diagram CheckPlansLadder→EmitUCD.
    """
    from harness.orchestrator import phase_route_local

    _make_fixture_e_srs_only(tmp_path)
    out = phase_route_local.route(tmp_path)
    assert out["next_skill"] == "long-task-ucd"


# ---- T69 -----------------------------------------------------------------
def test_t69_phase_route_local_priority6_empty_workdir_default(tmp_path: Path) -> None:
    """T69 FUNC/happy: empty workdir → default long-task-requirements.

    Traces To: FR-054 AC-4 / §State Diagram CheckBrownfield→EmitRequirements.
    """
    from harness.orchestrator import phase_route_local

    _make_fixture_f_empty(tmp_path)
    out = phase_route_local.route(tmp_path)
    assert out["next_skill"] == "long-task-requirements"


# ---- T70 -----------------------------------------------------------------
def test_t70_phase_route_local_corrupt_feature_list_returns_errors(
    tmp_path: Path,
) -> None:
    """T70 FUNC/error: corrupt feature-list.json → ok=False, errors non-empty,
    next_skill=None — does NOT raise.

    Traces To: FR-054 / §Boundary Conditions phase_route_local.route corruption.
    """
    from harness.orchestrator import phase_route_local

    _make_corrupt_feature_list(tmp_path)
    # Must not raise.
    out = phase_route_local.route(tmp_path)
    assert out["ok"] is False
    assert (
        isinstance(out["errors"], list) and out["errors"]
    ), f"expected non-empty errors; got {out['errors']!r}"
    assert out["next_skill"] is None


# ---- T71 -----------------------------------------------------------------
def test_t71_phase_route_local_matches_plugin_v1_0_0_for_all_fixtures(
    tmp_path: Path,
) -> None:
    """T71 INTG/cross-impl: run plugin scripts/phase_route.py via real subprocess
    on the same fixture set; compare output dict with phase_route_local.route().

    Traces To: FR-054 / IAPI-022 ASM-001/ASM-011.
    """
    from harness.orchestrator import phase_route_local

    plugin_script = PLUGIN_SCRIPTS_DIR / "phase_route.py"
    assert plugin_script.exists(), (
        f"plugin reference script not found at {plugin_script}; "
        "T71 cannot anchor cross-impl parity"
    )

    fixtures = [
        ("a_bugfix", _make_fixture_a_bugfix),
        ("b_increment", _make_fixture_b_increment),
        ("c_work_design", _make_fixture_c_work_design),
        ("d_all_passing", _make_fixture_d_all_passing),
        ("e_srs_only", _make_fixture_e_srs_only),
        ("f_empty", _make_fixture_f_empty),
    ]
    for name, factory in fixtures:
        sub = tmp_path / name
        sub.mkdir()
        factory(sub)

        # Plugin v1.0.0 reference output via real subprocess.
        proc = subprocess.run(
            [sys.executable, str(plugin_script), "--root", str(sub), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        ref = json.loads(proc.stdout)
        # In-proc port output.
        port = phase_route_local.route(sub)

        assert port == ref, f"fixture {name!r} mismatch:\n" f"  plugin: {ref}\n" f"  port:   {port}"


# ===========================================================================
# T72..T80 — spawn 内置 skill inject (FR-055 / API-W5-04)
# ===========================================================================


def _build_dispatch_spec(plugin_dir: Path, settings_path: Path) -> Any:
    from harness.domain.ticket import DispatchSpec

    return DispatchSpec(
        argv=["claude"],
        env={},
        cwd=str(settings_path.parent),
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )


def _build_isolated_paths(workdir: Path) -> Any:
    from harness.env.models import IsolatedPaths

    cwd = workdir / ".harness-workdir" / "run-1"
    cwd.mkdir(parents=True, exist_ok=True)
    settings = cwd / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    return IsolatedPaths(
        cwd=str(cwd),
        plugin_dir=str(workdir / "plugin"),
        settings_path=str(settings),
    )


class _FakePtyWorker:
    """Minimal PTY worker stand-in supporting boot/inject/marker scenarios."""

    def __init__(
        self,
        *,
        boot_stable_after_s: float = 0.05,
        marker_after_s: float = 0.05,
        skill_hint: str = "long-task-design",
        write_raises: bool = False,
        boot_never_stable: bool = False,
        marker_never_appears: bool = False,
    ) -> None:
        self._boot_after = boot_stable_after_s
        self._marker_after = marker_after_s
        self._skill = skill_hint
        self._write_raises = write_raises
        self._boot_never = boot_never_stable
        self._marker_never = marker_never_appears
        self.writes: list[bytes] = []
        self._t0 = time.monotonic()
        self.pid = 9999
        self.byte_queue: Any = None

    def start(self) -> None:
        self._t0 = time.monotonic()

    def is_boot_stable(self) -> bool:
        if self._boot_never:
            return False
        return (time.monotonic() - self._t0) >= self._boot_after

    def write(self, data: bytes) -> None:
        if self._write_raises:
            raise OSError("pty write failed")
        self.writes.append(data)

    def screen_text(self) -> str:
        if self._marker_never:
            return "(no marker)"
        if (time.monotonic() - self._t0) >= self._marker_after + self._boot_after:
            return f"I'm using {self._skill}\nready"
        return "boot prompt..."


# ---- T72 -----------------------------------------------------------------
async def test_t72_spawn_writes_bracketed_paste_skill_inject_sequence(
    tmp_path: Path,
) -> None:
    """T72 FUNC/happy: spawn writes ESC[200~/<skill>ESC[201~ + sleep(0.5) + CR.

    Traces To: FR-055 AC-1 / API-W5-04 / §Design Alignment seq msg PtyWorker.write.
    """
    from harness.adapter.claude import ClaudeCodeAdapter

    paths = _build_isolated_paths(tmp_path)
    spec = _build_dispatch_spec(
        plugin_dir=Path(paths.plugin_dir), settings_path=Path(paths.settings_path)
    )
    spec_dict = dict(spec)
    spec_dict["skill_hint"] = "long-task-design"
    # Provide fake pty factory that returns a stable boot + quick marker hit.
    fake_worker = _FakePtyWorker(
        boot_stable_after_s=0.05, marker_after_s=0.05, skill_hint="long-task-design"
    )

    def _fake_factory(*a: Any, **kw: Any) -> Any:
        return fake_worker

    adapter = ClaudeCodeAdapter(pty_factory=_fake_factory)

    # The Wave 5 spawn signature is unchanged; skill_hint comes via spec.
    # We pass it through TicketCommand-shaped spec for forward-compat.
    cmd = MagicMock()
    cmd.skill_hint = "long-task-design"
    proc = await adapter.spawn(spec, paths, skill_hint="long-task-design")

    # Concatenate writes and assert the bracketed paste protocol.
    blob = b"".join(fake_worker.writes)
    assert (
        b"\x1b[200~/long-task-design\x1b[201~" in blob
    ), f"bracketed paste sequence missing; writes={fake_worker.writes!r}"
    assert b"\r" in blob, "CR (carriage return) must be written after paste"
    assert proc is not None


# ---- T73 -----------------------------------------------------------------
async def test_t73_spawn_boot_timeout_raises_skill_dispatch_error(
    tmp_path: Path,
) -> None:
    """T73 FUNC/error: boot sentinel never clears within 8s → SkillDispatchError
    reason=BOOT_TIMEOUT, elapsed_ms ≥ 8000.

    Traces To: FR-055 AC-2 / Err-K BOOT_TIMEOUT.
    """
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.errors import SkillDispatchError, SpawnError

    paths = _build_isolated_paths(tmp_path)
    spec = _build_dispatch_spec(
        plugin_dir=Path(paths.plugin_dir), settings_path=Path(paths.settings_path)
    )

    fake_worker = _FakePtyWorker(boot_never_stable=True)

    def _factory(*a: Any, **kw: Any) -> Any:
        return fake_worker

    adapter = ClaudeCodeAdapter(pty_factory=_factory)

    # Use injected short timeout via env or kwarg — production default is 8s
    # but tests must trigger BOOT_TIMEOUT in <1s. The Wave 5 spawn must accept
    # boot_timeout_s kwarg.
    with pytest.raises(SkillDispatchError) as excinfo:
        await adapter.spawn(
            spec,
            paths,
            skill_hint="long-task-design",
            boot_timeout_s=0.2,
        )
    assert excinfo.value.reason == "BOOT_TIMEOUT"
    # SpawnError sub-class invariant — supervisor's existing except SpawnError
    # path must catch it.
    assert isinstance(excinfo.value, SpawnError)


# ---- T74 -----------------------------------------------------------------
async def test_t74_spawn_write_failure_raises_skill_dispatch_error(
    tmp_path: Path,
) -> None:
    """T74 FUNC/error: PTY.write raises OSError → SkillDispatchError
    reason=WRITE_FAILED.

    Traces To: FR-055 / Err-K WRITE_FAILED.
    """
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.errors import SkillDispatchError

    paths = _build_isolated_paths(tmp_path)
    spec = _build_dispatch_spec(
        plugin_dir=Path(paths.plugin_dir), settings_path=Path(paths.settings_path)
    )

    fake_worker = _FakePtyWorker(write_raises=True, boot_stable_after_s=0.0)

    def _factory(*a: Any, **kw: Any) -> Any:
        return fake_worker

    adapter = ClaudeCodeAdapter(pty_factory=_factory)

    with pytest.raises(SkillDispatchError) as excinfo:
        await adapter.spawn(spec, paths, skill_hint="long-task-design")
    assert excinfo.value.reason == "WRITE_FAILED"


# ---- T75 -----------------------------------------------------------------
async def test_t75_spawn_marker_timeout_raises_skill_dispatch_error(
    tmp_path: Path,
) -> None:
    """T75 FUNC/error: SKILL.md marker never appears within 30s →
    SkillDispatchError reason=MARKER_TIMEOUT.

    Traces To: FR-055 AC-3 / Err-K MARKER_TIMEOUT.
    """
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.errors import SkillDispatchError

    paths = _build_isolated_paths(tmp_path)
    spec = _build_dispatch_spec(
        plugin_dir=Path(paths.plugin_dir), settings_path=Path(paths.settings_path)
    )

    fake_worker = _FakePtyWorker(boot_stable_after_s=0.0, marker_never_appears=True)

    def _factory(*a: Any, **kw: Any) -> Any:
        return fake_worker

    adapter = ClaudeCodeAdapter(pty_factory=_factory)

    with pytest.raises(SkillDispatchError) as excinfo:
        await adapter.spawn(
            spec,
            paths,
            skill_hint="long-task-design",
            boot_timeout_s=0.2,
            marker_timeout_s=0.3,
        )
    assert excinfo.value.reason == "MARKER_TIMEOUT"


# ---- T76 -----------------------------------------------------------------
async def test_t76_spawn_uses_short_slash_form_not_namespaced(
    tmp_path: Path,
) -> None:
    """T76 BNDRY/edge: skill_hint='long-task-hotfix' → bytes contain
    b'/long-task-hotfix' NOT b'/long-task:long-task-hotfix'.

    Traces To: FR-055 AC-4 / puncture_wave5 plugin TUI parity.
    """
    from harness.adapter.claude import ClaudeCodeAdapter

    paths = _build_isolated_paths(tmp_path)
    spec = _build_dispatch_spec(
        plugin_dir=Path(paths.plugin_dir), settings_path=Path(paths.settings_path)
    )

    fake_worker = _FakePtyWorker(
        boot_stable_after_s=0.0, marker_after_s=0.0, skill_hint="long-task-hotfix"
    )

    def _factory(*a: Any, **kw: Any) -> Any:
        return fake_worker

    adapter = ClaudeCodeAdapter(pty_factory=_factory)
    await adapter.spawn(spec, paths, skill_hint="long-task-hotfix")

    blob = b"".join(fake_worker.writes)
    assert b"/long-task-hotfix" in blob
    # Must NOT contain the namespaced form
    assert (
        b"/long-task:long-task-hotfix" not in blob
    ), "Wave 5 mandates short slash form; namespaced form rejected by plugin TUI"


# ---- T77 -----------------------------------------------------------------
def test_t77_skill_dispatch_error_inherits_spawn_error() -> None:
    """T77 FUNC/error: SkillDispatchError is a subclass of SpawnError so
    supervisor's existing `except SpawnError` path catches it.

    Traces To: FR-055 / supervisor backward-compat invariant.
    """
    from harness.adapter.errors import SkillDispatchError, SpawnError

    err = SkillDispatchError("BOOT_TIMEOUT", skill_hint="x", elapsed_ms=8000.0)
    assert isinstance(err, SpawnError)
    # The reason / skill_hint / elapsed_ms attributes must round-trip per design.
    assert err.reason == "BOOT_TIMEOUT"
    assert err.skill_hint == "x"
    assert err.elapsed_ms == 8000.0


# ---- T78 -----------------------------------------------------------------
async def test_t78_spawn_rejects_control_chars_in_skill_hint(
    tmp_path: Path,
) -> None:
    """T78 SEC/inject: control char in skill_hint → SkillDispatchError
    WRITE_FAILED; raw \\x03 NOT written to PTY (NFR-009 / FR-053 byte守恒).

    Traces To: FR-055 / NFR-009 control-char rejection.
    """
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.errors import SkillDispatchError

    paths = _build_isolated_paths(tmp_path)
    spec = _build_dispatch_spec(
        plugin_dir=Path(paths.plugin_dir), settings_path=Path(paths.settings_path)
    )

    fake_worker = _FakePtyWorker(boot_stable_after_s=0.0)

    def _factory(*a: Any, **kw: Any) -> Any:
        return fake_worker

    adapter = ClaudeCodeAdapter(pty_factory=_factory)

    with pytest.raises(SkillDispatchError) as excinfo:
        await adapter.spawn(spec, paths, skill_hint="long-task\x03hotfix")
    assert excinfo.value.reason == "WRITE_FAILED"
    # The raw \x03 byte must never reach the PTY.
    blob = b"".join(fake_worker.writes)
    assert b"\x03" not in blob, "control char leaked to PTY (NFR-009 violation)"


# ---- T79 -----------------------------------------------------------------
@pytest.mark.real_cli
async def test_t79_real_cli_spawn_one_pty_per_ticket_invariant(
    tmp_path: Path,
) -> None:
    """T79 INTG/spawn-real: real claude-cli + plugin; spawn N=3 tickets;
    PTY pids set size MUST == 3 (no session reuse).

    Traces To: FR-055 / INT-026 / spawn_model_invariant 1:1.
    """
    import shutil as _shutil

    if _shutil.which("claude") is None:
        pytest.fail("claude CLI not on PATH — required for INT-026 real spawn")

    # The scaffolding for real spawn is provided by the production code path
    # being implemented in Wave 5. We assert structurally that with three
    # distinct skill_hints, three distinct PIDs are created.
    from harness.adapter.claude import ClaudeCodeAdapter

    pids: set[int] = set()
    adapter = ClaudeCodeAdapter()
    for hint in ["long-task-hotfix", "long-task-increment", "long-task-design"]:
        paths = _build_isolated_paths(tmp_path / hint)
        spec = _build_dispatch_spec(
            plugin_dir=Path(paths.plugin_dir),
            settings_path=Path(paths.settings_path),
        )
        proc = await adapter.spawn(spec, paths, skill_hint=hint)
        pids.add(proc.pid)
    assert len(pids) == 3, f"expected 3 distinct PIDs; got {pids}"


# ---- T80 -----------------------------------------------------------------
@pytest.mark.real_cli
async def test_t80_real_cli_skill_md_marker_is_observed_within_30s(
    tmp_path: Path,
) -> None:
    """T80 INTG/spawn-real: real claude-cli + plugin; spawn long-task-hotfix;
    SKILL.md "I'm using long-task-hotfix" marker observed within 30s.

    Traces To: FR-055 AC-3.
    """
    import shutil as _shutil

    if _shutil.which("claude") is None:
        pytest.fail("claude CLI not on PATH — required for marker validation")

    from harness.adapter.claude import ClaudeCodeAdapter

    paths = _build_isolated_paths(tmp_path)
    spec = _build_dispatch_spec(
        plugin_dir=Path(paths.plugin_dir), settings_path=Path(paths.settings_path)
    )
    adapter = ClaudeCodeAdapter()
    proc = await adapter.spawn(spec, paths, skill_hint="long-task-hotfix")
    # Spawn returning successfully implies the marker was hit (Wave 5 contract);
    # also assert worker has a screen_text method indicating marker validation
    # ran in production code path.
    assert proc.pid > 0
    # If proc has a screen attribute capture, assert marker presence.
    screen = getattr(proc, "screen_text", None)
    if callable(screen):
        text = screen()
        assert "long-task-hotfix" in text


# ===========================================================================
# T81 — cooperative wait (FR-048 AC-2 / API-W5-06)
# ===========================================================================
# ---- T81 -----------------------------------------------------------------
async def test_t81_run_loop_cooperative_wait_signal_dirty_set_and_no_cancel(
    tmp_path: Path,
) -> None:
    """T81 INTG/cooperative-wait: while ticket is running, signal_watcher fires
    bugfix_request → rt.signal_dirty.set() called; ticket NOT force-cancelled;
    next loop iteration calls phase_route → next_skill=long-task-hotfix.

    Traces To: FR-048 AC-2 / API-W5-06 / §Design Alignment seq msg signal_dirty.set.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest, SignalEvent

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)

    # Configure phase_route: 1st returns long-task-design (current ticket),
    # 2nd MUST return long-task-hotfix (signal-driven re-route), 3rd ST-Go.
    orch.phase_route_invoker.set_responses(
        [
            {"ok": True, "next_skill": "long-task-design"},
            {"ok": True, "next_skill": "long-task-hotfix", "feature_id": "hotfix-x"},
            {"ok": True, "next_skill": None},
        ]
    )
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    # Schedule signal mid-run.
    await asyncio.sleep(0.05)
    sig = SignalEvent(kind="bugfix_request", path=str(tmp_path / "bugfix-request.json"))
    # on_signal exists in Wave 5 as formal contract.
    await orch.on_signal(sig)

    runtime = orch._runtimes[s.run_id]
    # Wave 5 invariant: rt.signal_dirty was set by on_signal handler.
    assert (
        getattr(runtime, "signal_dirty", None) is not None
    ), "Wave 5 _RunRuntime must expose signal_dirty asyncio.Event"
    assert runtime.signal_dirty.is_set(), "on_signal must set rt.signal_dirty"

    # Allow loop to drain.
    await orch.wait_for_state(s.run_id, "completed", timeout=4.0)

    # The hotfix skill must appear in dispatched skill hints (signal advanced loop).
    spawned = orch.tool_adapter.dispatched_skill_hints()
    assert "long-task-hotfix" in spawned, f"signal-driven hotfix dispatch missing from {spawned}"


# ===========================================================================
# T82 — on_signal broadcast (FR-048 AC-1 / API-W5-10)
# ===========================================================================
# ---- T82 -----------------------------------------------------------------
async def test_t82_on_signal_broadcasts_via_control_bus_and_sets_dirty(
    tmp_path: Path,
) -> None:
    """T82 FUNC/happy: SignalFileWatcher.on_signal → rt.signal_dirty.set +
    control_bus.broadcast_signal called.

    Traces To: FR-048 AC-1 / API-W5-10 / IAPI-012.
    """
    from harness.orchestrator.signal_watcher import SignalFileWatcher
    from harness.orchestrator.schemas import SignalEvent

    bcast: list[SignalEvent] = []

    class _BusStub:
        def broadcast_signal(self, event: SignalEvent) -> None:
            bcast.append(event)

    class _RtStub:
        def __init__(self) -> None:
            self.signal_dirty = asyncio.Event()

    rt = _RtStub()
    watcher = SignalFileWatcher(workdir=tmp_path, control_bus=_BusStub())
    # Wave 5 contract: on_signal accepts (event, *, rt=None).
    watcher.attach_runtime(rt)  # type: ignore[attr-defined]
    evt = SignalEvent(kind="increment_request", path=str(tmp_path / "increment-request.json"))
    await watcher.on_signal(evt)

    assert rt.signal_dirty.is_set(), "on_signal must set rt.signal_dirty"
    assert len(bcast) == 1, f"broadcast_signal must be called once; got {len(bcast)}"
    assert bcast[0].kind == "increment_request"


# ===========================================================================
# T83 — record_call privatisation regression (API-W5-09)
# ===========================================================================
# ---- T83 -----------------------------------------------------------------
def test_t83_record_call_renamed_to_underscore_record_call_globally() -> None:
    """T83 INTG/cosmetic: rg-equivalent sweep across harness/ + tests/ for the
    bare ``.record_call(`` token. Wave 5 mandates the public→private rename.

    Traces To: API-W5-09 / §Wave 5 Inlining Decisions.
    """
    import re

    pattern = re.compile(r"\.record_call\(")
    offenders: list[str] = []
    for root in [REPO_ROOT / "harness", REPO_ROOT / "tests"]:
        for py in root.rglob("*.py"):
            # Skip the cache and the W5 file we are authoring.
            if "__pycache__" in str(py):
                continue
            if py.name == "test_f20_w5_design.py":
                continue
            text = py.read_text(encoding="utf-8", errors="replace")
            if pattern.search(text):
                offenders.append(str(py.relative_to(REPO_ROOT)))
    assert not offenders, (
        "Wave 5 API-W5-09 violation — `.record_call(` still present in:\n  "
        + "\n  ".join(offenders)
        + "\nrename all to `._record_call(` (or migrate to `call_trace()` reads)"
    )


# ===========================================================================
# T84 / T85 — feature_list_io.count_pending (API-W5-07)
# ===========================================================================
# ---- T84 -----------------------------------------------------------------
def test_t84_feature_list_io_count_pending_matches_plugin_v1_0_0(
    tmp_path: Path,
) -> None:
    """T84 FUNC/happy: count_pending on a 5p+3f+2d fixture must match plugin's
    schema and values exactly.

    Traces To: API-W5-07 / ASM-011.
    """
    from harness.utils import feature_list_io

    path = _make_count_pending_fixture(tmp_path, passing=5, failing=3, deprecated=2)
    out = feature_list_io.count_pending(path)
    # Plugin v1.0.0 schema: {total, passing, failing, current, deprecated, legacy_sub_status}
    # Wave 5 design §Interface Contract simplifies to {passing, failing, deprecated, total}
    # Both forms must contain the four core counts; assert canonically.
    assert out["passing"] == 5
    assert out["failing"] == 3
    assert out["deprecated"] == 2
    assert out["total"] == 8


# ---- T85 -----------------------------------------------------------------
def test_t85_feature_list_io_count_pending_errors_on_missing_or_corrupt(
    tmp_path: Path,
) -> None:
    """T85 FUNC/error: missing path → OSError (FileNotFoundError); corrupt JSON
    → ValueError. Behaviour parity with plugin scripts/count_pending.py.

    Traces To: API-W5-07.
    """
    from harness.utils import feature_list_io

    missing = tmp_path / "no-such-file.json"
    with pytest.raises(OSError):
        feature_list_io.count_pending(missing)

    corrupt = tmp_path / "feature-list.json"
    corrupt.write_text("{not json")
    with pytest.raises(ValueError):
        feature_list_io.count_pending(corrupt)


# ===========================================================================
# T86 — feature_list_io vs plugin v1.0.0 cross-impl (ASM-011)
# ===========================================================================
# ---- T86 -----------------------------------------------------------------
def test_t86_feature_list_io_matches_plugin_v1_0_0_across_5_fixtures(
    tmp_path: Path,
) -> None:
    """T86 INTG/cross-impl: 5 fixture shapes — single feature / 100 features /
    contains deprecated / contains invalid status / empty features.

    Traces To: ASM-011.
    """
    from harness.utils import feature_list_io

    plugin_count = PLUGIN_SCRIPTS_DIR / "count_pending.py"
    assert plugin_count.exists(), f"plugin reference {plugin_count} missing"

    fixtures: list[tuple[str, dict]] = [
        (
            "single",
            _make_minimal_feature_list(
                [
                    {
                        "id": 1,
                        "category": "core",
                        "title": "F1",
                        "description": "x",
                        "priority": "low",
                        "status": "passing",
                    },
                ]
            ),
        ),
        (
            "hundred",
            _make_minimal_feature_list(
                [
                    {
                        "id": i,
                        "category": "core",
                        "title": f"F{i}",
                        "description": "x",
                        "priority": "low",
                        "status": "passing" if i % 2 else "failing",
                    }
                    for i in range(1, 101)
                ]
            ),
        ),
        (
            "with_deprecated",
            _make_minimal_feature_list(
                [
                    {
                        "id": 1,
                        "category": "core",
                        "title": "F1",
                        "description": "x",
                        "priority": "low",
                        "status": "passing",
                    },
                    {
                        "id": 2,
                        "category": "core",
                        "title": "F2",
                        "description": "x",
                        "priority": "low",
                        "status": "passing",
                        "deprecated": True,
                    },
                ]
            ),
        ),
        (
            "invalid_status",
            _make_minimal_feature_list(
                [
                    {
                        "id": 1,
                        "category": "core",
                        "title": "F1",
                        "description": "x",
                        "priority": "low",
                        "status": "weird-status",
                    },
                ]
            ),
        ),
        ("empty", _make_minimal_feature_list([])),
    ]

    for name, content in fixtures:
        sub = tmp_path / name
        sub.mkdir()
        path = sub / "feature-list.json"
        path.write_text(json.dumps(content))

        # Plugin reference subprocess.
        proc = subprocess.run(
            [sys.executable, str(plugin_count), str(path), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        ref = json.loads(proc.stdout)
        port = feature_list_io.count_pending(path)

        for k in ("total", "passing", "failing", "deprecated"):
            assert port.get(k) == ref.get(k), (
                f"fixture {name!r} field {k!r} mismatch: " f"port={port.get(k)} plugin={ref.get(k)}"
            )


# ===========================================================================
# T87 — cooperative interrupt boundary (API-W5-06)
# ===========================================================================
# ---- T87 -----------------------------------------------------------------
async def test_t87_cooperative_wait_signal_and_ticket_complete_concurrently(
    tmp_path: Path,
) -> None:
    """T87 BNDRY/cooperative: signal fires at t=50ms; ticket completes at
    t=100ms. FIRST_COMPLETED picks signal_task; ticket_task is awaited (not
    cancelled); next loop iteration re-routes.

    Traces To: API-W5-06 / cooperative interrupt edge.
    """
    from harness.orchestrator.run import RunOrchestrator
    from harness.orchestrator.schemas import RunStartRequest, SignalEvent

    _git_init(tmp_path)
    orch = RunOrchestrator.build_test_default(workdir=tmp_path)
    # 1st: design (current ticket); 2nd: hotfix (signal-driven re-route); 3rd: ST.
    orch.phase_route_invoker.set_responses(
        [
            {"ok": True, "next_skill": "long-task-design"},
            {"ok": True, "next_skill": "long-task-hotfix"},
            {"ok": True, "next_skill": None},
        ]
    )
    s = await orch.start_run(RunStartRequest(workdir=str(tmp_path)))

    # Fire the signal almost immediately to race with ticket completion.
    await asyncio.sleep(0.005)
    sig = SignalEvent(kind="bugfix_request", path=str(tmp_path / "bugfix-request.json"))
    await orch.on_signal(sig)

    # Loop must drain to completed without hanging — proves ticket_task was
    # NOT cancelled (await natural finish).
    await orch.wait_for_state(s.run_id, "completed", timeout=4.0)

    # Both design + hotfix must have been dispatched.
    spawned = orch.tool_adapter.dispatched_skill_hints()
    assert "long-task-design" in spawned
    assert "long-task-hotfix" in spawned


# ===========================================================================
# Real-port anchor for check_real_tests.py — feature_20 W5
# ===========================================================================
@pytest.mark.real_fs
def test_w5_real_route_real_fixture_fixture_d(tmp_path: Path) -> None:
    """Real-fs anchor: phase_route_local.route on a real filesystem fixture
    (no mocks). Drives check_real_tests.py discovery for feature_20 Wave 5.

    Traces To: §Real Test Convention — Wave 5 phase_route_local in-proc port.
    """
    from harness.orchestrator import phase_route_local

    _make_fixture_d_all_passing(tmp_path)
    # Real filesystem read; no mocks. Hard assertion on outcome.
    out = phase_route_local.route(tmp_path)
    assert out["ok"] is True
    assert out["next_skill"] == "long-task-st"
