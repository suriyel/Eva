"""F10 · PluginRegistry — manifest reader + physical bundle copy.

``sync_bundle`` uses ``shutil.copytree(..., dirs_exist_ok=True)`` for
idempotent physical copy (single-path implementation per 2026-04-24
user-approved Design Deviation; NOT symlink / junction).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from .errors import (
    BundleSyncError,
    PluginManifestCorruptError,
    PluginManifestMissingError,
)
from .models import PluginManifest, PluginSyncResult


_MANIFEST_MAX_BYTES = 65536  # §Boundary — plugin.json ≤ 64 KiB


class PluginRegistry:
    """Read plugin manifests and perform idempotent physical bundle copies."""

    def read_manifest(self, plugin_dir: Path) -> PluginManifest:
        plugin_dir = Path(plugin_dir)
        manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
        if not manifest_path.is_file():
            raise PluginManifestMissingError(f"plugin.json not found: {manifest_path}")

        try:
            raw = manifest_path.read_bytes()
        except OSError as exc:
            raise PluginManifestCorruptError(f"cannot read plugin.json: {exc!r}") from exc

        if len(raw) == 0:
            raise PluginManifestCorruptError(f"plugin.json is empty: {manifest_path}")
        if len(raw) > _MANIFEST_MAX_BYTES:
            raise PluginManifestCorruptError(
                f"plugin.json exceeds {_MANIFEST_MAX_BYTES} bytes: "
                f"{len(raw)} bytes at {manifest_path}"
            )

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PluginManifestCorruptError(
                f"plugin.json is not valid UTF-8 JSON: {exc!r}"
            ) from exc

        if not isinstance(data, dict):
            raise PluginManifestCorruptError(
                f"plugin.json top-level must be object, got {type(data).__name__}"
            )

        name = data.get("name")
        version = data.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise PluginManifestCorruptError(
                f"plugin.json missing required name/version strings: {manifest_path}"
            )

        # Optional commit_sha from git rev-parse HEAD when .git/ present.
        commit_sha: str | None = None
        if (plugin_dir / ".git").exists():
            commit_sha = self._rev_parse_head(plugin_dir)

        return PluginManifest(name=name, version=version, commit_sha=commit_sha)

    def sync_bundle(self, src_bundle: Path, dst_plugin_dir: Path) -> PluginSyncResult:
        """Physical copy of src_bundle → dst_plugin_dir (idempotent).

        Implements the 2026-04-24 Design Deviation — single-path
        shutil.copytree with dirs_exist_ok=True (no symlink, no junction).
        """

        src_bundle = Path(src_bundle)
        dst_plugin_dir = Path(dst_plugin_dir)

        if not src_bundle.is_dir():
            raise BundleSyncError(f"src_bundle not a directory: {src_bundle}")
        manifest_src = src_bundle / ".claude-plugin" / "plugin.json"
        if not manifest_src.is_file():
            raise BundleSyncError(f"src_bundle missing .claude-plugin/plugin.json: {src_bundle}")

        # Reject mutually nested paths.
        src_resolved = src_bundle.resolve()
        dst_resolved = (
            dst_plugin_dir.resolve()
            if dst_plugin_dir.exists()
            else (dst_plugin_dir.parent.resolve() / dst_plugin_dir.name)
        )
        try:
            if dst_resolved.is_relative_to(src_resolved):
                raise BundleSyncError(f"dst_plugin_dir nested inside src_bundle: {dst_resolved}")
            if src_resolved.is_relative_to(dst_resolved):
                raise BundleSyncError(f"src_bundle nested inside dst_plugin_dir: {src_resolved}")
        except AttributeError:  # pragma: no cover — Python < 3.9
            pass

        try:
            shutil.copytree(
                str(src_bundle),
                str(dst_plugin_dir),
                dirs_exist_ok=True,
                symlinks=False,
            )
        except OSError as exc:
            raise BundleSyncError(
                f"copytree failed {src_bundle} -> {dst_plugin_dir}: {exc!r}"
            ) from exc

        # Hash the manifest in the destination (must equal source per contract).
        dst_manifest = dst_plugin_dir / ".claude-plugin" / "plugin.json"
        if not dst_manifest.is_file():  # pragma: no cover — sanity
            raise BundleSyncError(f"post-copy manifest missing at {dst_manifest}")
        dst_bytes = dst_manifest.read_bytes()
        manifest_sha = hashlib.sha256(dst_bytes).hexdigest()

        copied_count = sum(1 for p in dst_plugin_dir.rglob("*") if p.is_file())

        return PluginSyncResult(
            dst_plugin_dir=str(dst_plugin_dir),
            manifest_sha256=manifest_sha,
            copied_file_count=copied_count,
        )

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _rev_parse_head(plugin_dir: Path) -> str | None:
        try:
            proc = subprocess.run(
                ["git", "-C", str(plugin_dir), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        sha = (proc.stdout or "").strip()
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            return sha
        return None


__all__ = ["PluginRegistry"]
