"""F10 · Environment Isolation exceptions."""

from __future__ import annotations


class EnvError(Exception):
    """Base for all harness.env errors."""


class RunIdInvalidError(EnvError):
    """run_id failed charset / length / traversal validation."""


class WorkdirNotFoundError(EnvError):
    """workdir does not exist, is not absolute, or is not a directory."""


class BundleNotFoundError(EnvError):
    """bundle_root missing .claude-plugin/plugin.json."""


class IsolationSetupError(EnvError):
    """mkdir / write / copytree inside setup_run failed."""


class TeardownError(EnvError):
    """teardown_run called without a matching setup snapshot."""


class HomeSnapshotError(EnvError):
    """HomeMtimeGuard.snapshot IO failure."""


class HomeWriteDetectedError(EnvError):
    """~/.claude/ touched between snapshot and diff."""


class WorkdirScopeError(EnvError):
    """WorkdirScopeGuard IO failure."""


__all__ = [
    "EnvError",
    "RunIdInvalidError",
    "WorkdirNotFoundError",
    "BundleNotFoundError",
    "IsolationSetupError",
    "TeardownError",
    "HomeSnapshotError",
    "HomeWriteDetectedError",
    "WorkdirScopeError",
]
