"""F10 · Skills exceptions (PluginRegistry + SkillsInstaller)."""

from __future__ import annotations


class SkillsError(Exception):
    """Base for harness.skills errors."""


class PluginManifestMissingError(SkillsError):
    """plugin.json missing."""


class PluginManifestCorruptError(SkillsError):
    """plugin.json unreadable / not valid JSON / outside size bounds."""


class BundleSyncError(SkillsError):
    """sync_bundle copytree failed."""


class GitUrlRejectedError(SkillsError):
    """clone source URL failed the whitelist / meta-character check."""


class TargetPathEscapeError(SkillsError):
    """target_dir attempted to escape <workdir>/plugins/."""


class GitSubprocessError(SkillsError):
    """git subprocess returned non-zero; stderr tail is embedded in message."""


class SkillsInstallBusyError(SkillsError):
    """run.lock present — install/pull would race with an active run."""


__all__ = [
    "SkillsError",
    "PluginManifestMissingError",
    "PluginManifestCorruptError",
    "BundleSyncError",
    "GitUrlRejectedError",
    "TargetPathEscapeError",
    "GitSubprocessError",
    "SkillsInstallBusyError",
]
