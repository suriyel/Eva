"""Integration test for F19 · real filesystem persistence (feature #19).

Covers T35 (INTG/fs) from feature design §7 Test Inventory.

[integration] — uses the real POSIX filesystem (tmp_path) + a FRESH
``ModelRulesStore`` instance after save to prove the on-disk JSON survives
across instances (catches non-atomic writes / in-memory-only caches / tmp-file
forgotten rename).

Feature ref: feature_19

Real-test invariants (Rule 5a):
  - DOES NOT mock Path / os / json — these are the primary dependencies.
  - Hard-fails if the file is missing or empty (assert, not skip).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.real_fs


@pytest.mark.real_fs
def test_f19_t35_real_fs_model_rules_persist_across_store_instances(
    tmp_path: Path,
) -> None:
    """feature_19 real test: save rules via one ModelRulesStore, re-open
    via a SECOND ``ModelRulesStore`` instance pointed at the same path, and
    require load() to return the equivalent rule list.

    We DO NOT patch filesystem primitives; the assertion is on disk state.
    """
    from harness.dispatch.model.models import ModelRule
    from harness.dispatch.model.rules_store import ModelRulesStore

    target = tmp_path / "model_rules.json"

    writer = ModelRulesStore(path=target)
    rules = [
        ModelRule(skill="requirements", tool="claude", model="opus"),
        ModelRule(skill="work", tool="claude", model="sonnet"),
        ModelRule(skill=None, tool="opencode", model="glm-4-plus"),
    ]
    writer.save(rules)

    # The file must physically exist on disk (no tmp-file forgotten rename).
    assert target.exists(), f"model_rules.json was not persisted at {target}"
    size = target.stat().st_size
    assert size > 0, f"model_rules.json is empty (size={size})"

    # A brand-new store instance — with a fresh path attr — reads the same rules.
    reader = ModelRulesStore(path=target)
    loaded = reader.load()
    assert loaded == rules, f"disk state was lost: disk={loaded!r}, expected={rules!r}"

    # POSIX mode parity (same invariant as T08, but here exercising the real fs).
    if sys.platform != "win32":
        import stat as _stat

        mode = _stat.S_IMODE(os.stat(target).st_mode)
        assert mode == 0o600, f"file permission must be 0o600, got {oct(mode)}"
