"""Integration test for F01 · real filesystem permission enforcement (feature #1).

Covers T18 (INTG/filesystem-permissions) from design §7 Test Inventory.

[integration] — real ``os.chmod`` + ``Path.mkdir`` against a tmp dir; no mocks.
Feature ref: feature_1

The test module is marked ``pytest.mark.skipif`` at collection time for
Windows only because the POSIX permission model is not applicable there;
this is an infrastructure gate, NOT a silent-skip of failures.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

# Module-level markers: real_fs for discovery, POSIX gate for platform.
pytestmark = [
    pytest.mark.real_fs,
    pytest.mark.skipif(
        sys.platform == "win32", reason="POSIX-only (F01 §Impl Summary defers Win ACL to v1.1)"
    ),
]


@pytest.mark.real_fs
def test_real_first_run_refuses_readonly_parent_dir(tmp_path: Path) -> None:
    """feature_1 real test: FirstRunWizard.bootstrap under a non-writable parent.

    No mocks on Path / os.chmod — we really drop permissions and expect the
    bootstrap to raise HarnessHomeWriteError.
    """
    from harness.app import FirstRunWizard
    from harness.app.first_run import HarnessHomeWriteError
    from harness.config import ConfigStore

    parent = tmp_path / "locked_parent"
    parent.mkdir(mode=0o500)  # r-x only — cannot write subdirs.
    harness_home = parent / ".harness"

    try:
        wizard = FirstRunWizard(ConfigStore(harness_home / "config.json"))
        with pytest.raises(HarnessHomeWriteError):
            wizard.bootstrap()

        # Must not partially create anything inside the locked parent.
        assert (
            not harness_home.exists()
        ), "bootstrap under read-only parent must not create ~/.harness/"
    finally:
        # Restore perms so pytest can clean up tmp_path.
        os.chmod(parent, 0o700)


@pytest.mark.real_fs
def test_real_first_run_sets_owner_only_permissions(tmp_path: Path) -> None:
    """feature_1 real test: ~/.harness/ must be chmod 0700 after bootstrap."""
    from harness.app import FirstRunWizard
    from harness.config import ConfigStore

    home = tmp_path / ".harness"
    wizard = FirstRunWizard(ConfigStore(home / "config.json"))
    wizard.bootstrap()

    mode = stat.S_IMODE(home.stat().st_mode)
    assert mode == 0o700, f"~/.harness/ mode must be 0o700 (got {oct(mode)})"

    # config.json itself must not be world/group readable.
    cfg = home / "config.json"
    assert cfg.is_file()
    cfg_mode = stat.S_IMODE(cfg.stat().st_mode)
    assert (
        cfg_mode & 0o077 == 0
    ), f"config.json must not be group/other readable (got {oct(cfg_mode)})"
