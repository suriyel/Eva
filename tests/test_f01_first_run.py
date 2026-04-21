"""Unit tests for F01 · FirstRunWizard (feature #1, FR-050).

Covers T01, T17, T27 from design §7 Test Inventory (T18 real-fs moved to
tests/integration/test_f01_real_filesystem.py).

[unit] — ``tmp_path`` + ``HARNESS_HOME`` monkeypatch.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# T01 — FUNC/happy — FR-050 AC1 — first-run creates ~/.harness/config.json
# ---------------------------------------------------------------------------
def test_first_run_bootstrap_creates_harness_home_and_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.app import FirstRunWizard
    from harness.config import ConfigStore, HarnessConfig

    home = tmp_path / ".harness"
    cfg_path = home / "config.json"
    monkeypatch.setenv("HARNESS_HOME", str(home))

    wizard = FirstRunWizard(ConfigStore(cfg_path))
    assert wizard.is_first_run() is True

    result = wizard.bootstrap()

    # Post-conditions from §IC FirstRunWizard.bootstrap.
    assert home.is_dir(), f"{home} must be created as a directory"
    assert cfg_path.is_file(), f"{cfg_path} must be created"
    assert result.home_path == home
    assert cfg_path in result.created_files
    assert result.welcome_message == "Welcome, 已初始化 ~/.harness/"

    # Config equals HarnessConfig.default() once loaded.
    loaded = ConfigStore(cfg_path).load()
    assert loaded == HarnessConfig.default()

    # POSIX permissions: ~/.harness/ must be 0o700 (owner-only).
    if sys.platform != "win32":
        mode = stat.S_IMODE(home.stat().st_mode)
        assert mode == 0o700, f"~/.harness/ mode should be 0o700, got {oct(mode)}"


# ---------------------------------------------------------------------------
# T17 — BNDRY/first-run-rerun — is_first_run() returns False when config exists
# ---------------------------------------------------------------------------
def test_is_first_run_returns_false_when_config_already_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.app import FirstRunWizard
    from harness.config import ConfigStore, HarnessConfig

    home = tmp_path / ".harness"
    home.mkdir(mode=0o700)
    cfg_path = home / "config.json"
    monkeypatch.setenv("HARNESS_HOME", str(home))

    # Pre-existing valid config.
    store = ConfigStore(cfg_path)
    store.save(HarnessConfig.default())

    wizard = FirstRunWizard(store)
    assert wizard.is_first_run() is False


def test_bootstrap_called_twice_does_not_overwrite_existing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running bootstrap on an already-initialised home must not clobber user data."""
    from harness.app import FirstRunWizard
    from harness.config import ConfigStore, HarnessConfig
    from harness.config.schema import ApiKeyRef

    home = tmp_path / ".harness"
    cfg_path = home / "config.json"
    monkeypatch.setenv("HARNESS_HOME", str(home))

    store = ConfigStore(cfg_path)
    wizard = FirstRunWizard(store)
    wizard.bootstrap()

    # User customises the config.
    custom = HarnessConfig(
        provider_refs={"glm": ApiKeyRef(service="harness-classifier-glm", user="alice")},
        retention_run_count=42,
    )
    store.save(custom)

    # Rerun — is_first_run must now be False, and explicit bootstrap (if called)
    # must not overwrite the persisted custom config.
    assert wizard.is_first_run() is False
    loaded = store.load()
    assert loaded.retention_run_count == 42
    assert "glm" in loaded.provider_refs


# ---------------------------------------------------------------------------
# T27 — SEC/path-traversal — HARNESS_HOME pointing at a file path
# ---------------------------------------------------------------------------
def test_bootstrap_refuses_to_write_to_existing_non_directory_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HARNESS_HOME set to a regular file must cause HarnessHomeWriteError."""
    from harness.app import FirstRunWizard
    from harness.config import ConfigStore
    from harness.app.first_run import HarnessHomeWriteError

    evil = tmp_path / "not_a_dir"
    evil.write_text("I am a file, not a directory", encoding="utf-8")
    monkeypatch.setenv("HARNESS_HOME", str(evil))

    wizard = FirstRunWizard(ConfigStore(evil / "config.json"))
    with pytest.raises(HarnessHomeWriteError):
        wizard.bootstrap()

    # Pre-existing file must remain intact.
    assert evil.read_text(encoding="utf-8") == "I am a file, not a directory"
