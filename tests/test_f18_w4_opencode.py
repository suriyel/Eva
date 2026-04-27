"""F18 Wave 4 · OpenCode adapter Wave-4 contract tests.

Test Inventory: T37, T38, T39.
SRS: FR-012 / IFR-002 / IFR-002 SEC BNDRY.

Layer marker:
  # [unit] — fakes filesystem + version probe; integration counterpart in
  #          tests/integration/test_f18_real_fs_hooks.py (kept).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.domain.ticket import DispatchSpec
from harness.env.models import IsolatedPaths


def _opencode_spec_paths(tmp_path: Path):
    cwd = tmp_path / ".harness-workdir" / "r1"
    plugin_dir = cwd / ".opencode" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path = cwd / ".opencode" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{}", encoding="utf-8")
    spec = DispatchSpec(
        argv=[],
        env={"HOME": str(cwd)},
        cwd=str(cwd),
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )
    paths = IsolatedPaths(
        cwd=str(cwd), plugin_dir=str(plugin_dir), settings_path=str(settings_path)
    )
    return spec, paths


# ---------------------------------------------------------------------------
# T37 — INTG/api — FR-012 — OpenCode hooks → /api/hook/event → HilQuestion derived
# ---------------------------------------------------------------------------
def test_t37_opencode_map_hook_event_returns_hil_question_same_schema(tmp_path):
    from harness.adapter.opencode import OpenCodeAdapter

    # Wave 4: OpenCode hook payload must mirror Claude schema (PreToolUse + Question)
    payload = {
        "session_id": "oc-abc",
        "transcript_path": "/tmp/oc.jsonl",
        "cwd": str(tmp_path),
        "hook_event_name": "PreToolUse",
        "tool_name": "Question",
        "tool_use_id": "oc-toolu-1",
        "tool_input": {
            "questions": [
                {
                    "header": "Editor",
                    "question": "Which editor?",
                    "options": [{"label": "vim"}, {"label": "emacs"}],
                    "multiSelect": False,
                }
            ]
        },
        "ts": "2026-04-26T23:46:01+00:00",
    }
    adapter = OpenCodeAdapter()
    questions = adapter.map_hook_event(payload)
    assert len(questions) == 1, f"got {len(questions)} questions"
    q = questions[0]
    assert q.header == "Editor"
    assert q.question == "Which editor?"
    assert [o.label for o in q.options] == ["vim", "emacs"]
    assert q.multi_select is False
    assert q.kind == "single_select"


# ---------------------------------------------------------------------------
# T38 — FUNC/error — FR-012 AC-2 — version < 0.3.0 raises HookRegistrationError
# ---------------------------------------------------------------------------
def test_t38_opencode_version_too_old_raises_hook_registration_error(tmp_path, monkeypatch):
    from harness.adapter.errors import HookRegistrationError
    from harness.adapter.opencode import OpenCodeAdapter

    # Force version probe to report < 0.3.0
    import harness.adapter.opencode as oc_mod

    def fake_probe():
        return "0.2.9"

    monkeypatch.setattr(oc_mod, "_probe_opencode_version", fake_probe, raising=False)

    spec, paths = _opencode_spec_paths(tmp_path)
    adapter = OpenCodeAdapter()
    with pytest.raises(HookRegistrationError):
        adapter.prepare_workdir(spec, paths)


# ---------------------------------------------------------------------------
# T39 — UT/SEC — IFR-002 SEC BNDRY — Question name > 256B truncates safely
# ---------------------------------------------------------------------------
def test_t39_long_question_name_truncated_to_256_bytes_no_crash(tmp_path):
    from harness.adapter.opencode import OpenCodeAdapter

    long_name = "A" * 1024  # 1024 bytes >> 256B limit
    payload = {
        "session_id": "oc-abc",
        "transcript_path": "/tmp/oc.jsonl",
        "cwd": str(tmp_path),
        "hook_event_name": "PreToolUse",
        "tool_name": "Question",
        "tool_use_id": "oc-toolu-1",
        "tool_input": {
            "questions": [
                {
                    "header": long_name,
                    "question": "Pick one",
                    "options": [{"label": "x"}],
                    "multiSelect": False,
                }
            ]
        },
        "ts": "2026-04-26T23:46:01+00:00",
    }
    questions = OpenCodeAdapter().map_hook_event(payload)
    assert len(questions) == 1
    encoded = questions[0].header.encode("utf-8")
    assert len(encoded) <= 256, f"header bytes {len(encoded)} > 256 limit"
    # Prefix preserved (truncation not random)
    assert questions[0].header.startswith("AAA")
