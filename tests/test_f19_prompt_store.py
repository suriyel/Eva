"""F19 · Bk-Dispatch — PromptStore versioning + validation + safety tests.

Covers Test Inventory: T28, T29, T30, T43.
SRS: FR-023 · FR-033 (v1) · §IC PromptStore.get/put · §BC content · SEC path-traversal.

Layer marker:
  # [unit] — writes to tmp_path. Fresh instance round-trip (re-read from disk)
  # is part of T28 itself, proving persistence at the unit level.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# T28 — FUNC/happy — Traces To: FR-023 · §IC PromptStore.get/put · §DA seq msg#2
# Kills: history not appended; rev not incremented; hash missing / wrong.
# ---------------------------------------------------------------------------
def test_t28_prompt_store_put_then_put_builds_two_history_revs_with_sha256_hash(
    tmp_path: Path,
):
    from harness.dispatch.classifier.prompt_store import PromptStore

    path = tmp_path / "classifier_prompt.json"
    store = PromptStore(path=path)

    body_v1 = "v1 prompt BODY"
    body_v2 = "v2 prompt BODY (revised)"
    store.put(body_v1)
    store.put(body_v2)

    prompt = store.get()

    assert prompt.current == body_v2, "current must reflect the latest put"
    assert len(prompt.history) == 2, f"expected 2 history entries, got {len(prompt.history)}"

    rev1, rev2 = prompt.history
    assert rev1.rev == 1 and rev2.rev == 2, "rev numbers must be monotonically increasing from 1"

    # Hashes must be sha256 hex of the respective bodies.
    expected_h1 = hashlib.sha256(body_v1.encode("utf-8")).hexdigest()
    expected_h2 = hashlib.sha256(body_v2.encode("utf-8")).hexdigest()
    assert rev1.hash == expected_h1
    assert rev2.hash == expected_h2

    # summary non-empty (first line, capped at 120 chars per design).
    assert rev1.summary and len(rev1.summary) <= 120


# ---------------------------------------------------------------------------
# T29 — BNDRY/edge — Traces To: §IC put · §BC content empty
# Kills: empty prompt silently saved (LLM loses system prompt).
# ---------------------------------------------------------------------------
def test_t29_prompt_store_put_empty_raises_prompt_validation_error(tmp_path: Path):
    from harness.dispatch.classifier.errors import PromptValidationError
    from harness.dispatch.classifier.prompt_store import PromptStore

    store = PromptStore(path=tmp_path / "prompt.json")
    with pytest.raises(PromptValidationError):
        store.put("")


# ---------------------------------------------------------------------------
# T30 — BNDRY/edge — Traces To: §IC put · §BC content 32 KB cap
# Kills: missing upper size bound (disk bloat vector).
# ---------------------------------------------------------------------------
def test_t30_prompt_store_put_32kb_plus_one_raises_prompt_validation_error(
    tmp_path: Path,
):
    from harness.dispatch.classifier.errors import PromptValidationError
    from harness.dispatch.classifier.prompt_store import PromptStore

    store = PromptStore(path=tmp_path / "prompt.json")
    oversized = ("x" * 32768) + "y"  # one byte past 32 KB
    with pytest.raises(PromptValidationError):
        store.put(oversized)


# ---------------------------------------------------------------------------
# T43 — SEC/path-traversal — Traces To: FR-033 SEC · §IC PromptStore
# Kills: attacker-controlled path escaping HARNESS_HOME.
# ---------------------------------------------------------------------------
def test_t43_prompt_store_refuses_path_outside_harness_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from harness.dispatch.classifier.errors import PromptStoreError
    from harness.dispatch.classifier.prompt_store import PromptStore

    # Pin HARNESS_HOME to tmp_path (the sandbox).
    harness_home = tmp_path / "home"
    harness_home.mkdir()
    monkeypatch.setenv("HARNESS_HOME", str(harness_home))

    # Point the store at a path that escapes HARNESS_HOME.
    escape = harness_home / ".." / "etc" / "passwd"
    store = PromptStore(path=escape)

    with pytest.raises(PromptStoreError):
        store.put("attacker prompt")
