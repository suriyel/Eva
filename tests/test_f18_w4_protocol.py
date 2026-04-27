"""F18 Wave 4 · ToolAdapter Protocol 7-method conformance + dead-code grep.

Test Inventory: T21, T22, T31, T33.
SRS: FR-015 / FR-018 / FR-014 [DEPRECATED] / IAPI-006 [MOD] byte_queue.
NFR-014: Protocol-based design.

Layer marker:
  # [unit] — static introspection + grep.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# T21 — FUNC/happy — FR-015 AC-1 + NFR-014 — 7-method Protocol
# ---------------------------------------------------------------------------
_REQUIRED_METHODS = (
    "build_argv",
    "prepare_workdir",
    "spawn",
    "map_hook_event",
    "parse_result",
    "detect_anomaly",
    "supports",
)


def test_t21_tool_adapter_protocol_exposes_seven_methods():
    """ToolAdapter Protocol must define exactly the 7 Wave-4 methods (no extract_hil)."""
    from harness.adapter.protocol import ToolAdapter

    members = {
        name
        for name, val in inspect.getmembers(ToolAdapter)
        if not name.startswith("_") and (callable(val) or inspect.isfunction(val))
    }
    for required in _REQUIRED_METHODS:
        assert required in members, f"ToolAdapter missing method {required!r}; got {sorted(members)}"
    # Wave 4 removed extract_hil — must NOT exist on Protocol
    assert "extract_hil" not in members, "Wave 4 removed extract_hil; Protocol still exposes it"


def test_t21b_claude_adapter_implements_seven_methods():
    from harness.adapter.claude import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    for required in _REQUIRED_METHODS:
        assert hasattr(adapter, required), f"ClaudeCodeAdapter missing {required}"


def test_t21c_opencode_adapter_implements_seven_methods():
    from harness.adapter.opencode import OpenCodeAdapter

    adapter = OpenCodeAdapter()
    for required in _REQUIRED_METHODS:
        assert hasattr(adapter, required), f"OpenCodeAdapter missing {required}"


def test_t21d_runtime_isinstance_protocol_check_passes_for_concrete_adapters():
    """Concrete adapters must satisfy the WAVE-4 7-method Protocol via runtime
    isinstance + must explicitly NOT expose extract_hil any more (Wave 3 method
    physically removed)."""
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.opencode import OpenCodeAdapter
    from harness.adapter.protocol import ToolAdapter

    claude = ClaudeCodeAdapter()
    opencode = OpenCodeAdapter()
    assert isinstance(claude, ToolAdapter)
    assert isinstance(opencode, ToolAdapter)
    # Wave 4 contract — extract_hil must be physically removed from both adapters.
    assert not hasattr(claude, "extract_hil"), (
        "Wave 4 [REMOVED]: ClaudeCodeAdapter.extract_hil must be deleted; "
        "use map_hook_event instead."
    )
    assert not hasattr(opencode, "extract_hil"), (
        "Wave 4 [REMOVED]: OpenCodeAdapter.extract_hil must be deleted."
    )


# ---------------------------------------------------------------------------
# T22 — FUNC/error — FR-015 AC-2 / FR-018 — incomplete adapter detected
# ---------------------------------------------------------------------------
def test_t22_mock_adapter_missing_prepare_workdir_fails_isinstance_check():
    """A class missing the WAVE-4-specific prepare_workdir / map_hook_event
    methods must NOT pass runtime_checkable Protocol isinstance —
    orchestrator can refuse to register it. This forces ToolAdapter Protocol
    to actually declare the two new methods so runtime_checkable picks them up.
    """
    from harness.adapter.protocol import ToolAdapter

    # A class that satisfies the OLD 6-method Protocol but NOT Wave-4.
    class IncompleteWave4Adapter:
        def build_argv(self, spec):
            return []

        def spawn(self, spec, paths=None):
            return None

        # Wave-3 leftover (which Wave-4 Protocol must NOT expect):
        def extract_hil(self, events):
            return []

        def parse_result(self, events):
            return None

        def detect_anomaly(self, events):
            return None

        def supports(self, flag):
            return False

        # Intentionally missing the Wave-4 newcomers:
        # prepare_workdir, map_hook_event

    adapter = IncompleteWave4Adapter()
    assert not isinstance(adapter, ToolAdapter), (
        "ToolAdapter Protocol still treats Wave-3 (6-method) adapter as valid. "
        "Wave-4 contract requires Protocol to declare prepare_workdir + "
        "map_hook_event so runtime_checkable rejects this stub."
    )


# ---------------------------------------------------------------------------
# T31 — FUNC/happy — FR-014 [DEPRECATED] — dead code grep across project
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "needle",
    ["BannerConflictArbiter", "JsonLinesParser", "HilExtractor"],
)
def test_t31_dead_code_grep_returns_zero_hits_in_production_paths(needle):
    """Wave 4 removed BannerConflictArbiter / JsonLinesParser / HilExtractor.
    Production source trees must contain 0 references."""
    targets = [_REPO_ROOT / "harness", _REPO_ROOT / "scripts"]
    hits: list[str] = []
    for root in targets:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if needle in text:
                hits.append(str(path.relative_to(_REPO_ROOT)))
    assert not hits, (
        f"Wave 4 dead code residue: {needle!r} still referenced in production "
        f"paths: {hits}. Delete before merging."
    )


# ---------------------------------------------------------------------------
# T33 — FUNC/happy — IAPI-006 [MOD] byte_queue not consumed by orchestrator
# ---------------------------------------------------------------------------
def test_t33_byte_queue_not_subscribed_by_orchestrator_or_supervisor():
    """Wave 4 byte_queue is downgraded to stdout-mirror archival.
    No orchestrator / supervisor / parser code may call byte_queue.get(...)."""
    targets = [
        _REPO_ROOT / "harness" / "orchestrator",
        _REPO_ROOT / "harness" / "supervisor",
        _REPO_ROOT / "harness" / "stream",
    ]
    hits: list[str] = []
    for root in targets:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if "byte_queue.get" in text or "byte_queue.qsize" in text:
                hits.append(str(path.relative_to(_REPO_ROOT)))
    assert not hits, (
        f"IAPI-006 [MOD] violation: downstream still consumes byte_queue: {hits}. "
        "Wave 4 routes stream events through HookEventToStreamMapper instead."
    )
