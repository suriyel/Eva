"""F19 · Bk-Dispatch — ModelRulesStore load/save unit tests.

Covers Test Inventory: T06, T07, T08.
SRS: FR-019, FR-020 · §IC ModelRulesStore.load/save · NFR-008 (file permission).

Layer marker:
  # [unit] — writes to tmp_path; real-fs integration for load/save round-trip
  # by a FRESH store instance lives in tests/integration/test_f19_real_fs.py (T35).
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# T06 — FUNC/error — Traces To: §IC ModelRulesStore.load Raises ModelRulesCorruptError
# Kills: JSON parse errors being swallowed (silent rule drop → security risk).
# ---------------------------------------------------------------------------
def test_t06_load_raises_model_rules_corrupt_error_on_invalid_json(tmp_path: Path):
    from harness.dispatch.model.rules_store import ModelRulesCorruptError, ModelRulesStore

    rules_file = tmp_path / "model_rules.json"
    rules_file.write_text("{ not valid json --- [broken", encoding="utf-8")

    store = ModelRulesStore(path=rules_file)

    with pytest.raises(ModelRulesCorruptError):
        store.load()


# ---------------------------------------------------------------------------
# T07 — FUNC/happy — Traces To: FR-019 · §IC save
# Kills: non-atomic write (half-written file); mode-field persistence bugs.
# ---------------------------------------------------------------------------
def test_t07_save_then_load_round_trip_preserves_single_rule(tmp_path: Path):
    from harness.dispatch.model.models import ModelRule
    from harness.dispatch.model.rules_store import ModelRulesStore

    rules_file = tmp_path / "model_rules.json"
    store = ModelRulesStore(path=rules_file)

    rules_in = [ModelRule(skill="work", tool="claude", model="sonnet")]
    store.save(rules_in)

    # File must exist (atomic replace done).
    assert rules_file.exists(), "save must produce the target file"

    # JSON body is valid; loaded rules are equivalent.
    data = json.loads(rules_file.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 1
    rules_out = store.load()
    assert rules_out == rules_in


# ---------------------------------------------------------------------------
# T08 — SEC/fs-perm — Traces To: §IC save · NFR-008 hygiene
# Kills: world-readable rule file (~/.harness should be user-private).
# POSIX-only (Windows uses ACL; deferred per design parity with F01).
# ---------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only file mode check")
def test_t08_save_sets_posix_mode_0600(tmp_path: Path):
    from harness.dispatch.model.models import ModelRule
    from harness.dispatch.model.rules_store import ModelRulesStore

    rules_file = tmp_path / "model_rules.json"
    store = ModelRulesStore(path=rules_file)
    store.save([ModelRule(skill=None, tool="claude", model="opus")])

    mode = stat.S_IMODE(os.stat(rules_file).st_mode)
    assert mode == 0o600, f"model_rules.json mode must be 0o600, got {oct(mode)}"
