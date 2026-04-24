"""Unit tests for F10 · PluginRegistry.sync_bundle / read_manifest.

Covers Test Inventory rows:
  T02 FUNC/happy          — sync_bundle physical copy + sha256 parity
  T18 BNDRY/manifest-size — plugin.json 0B / 1B / 64 KiB / 64 KiB+1 handling
  T20 BNDRY/copytree-idempotent — second call with same args is a no-op
  T27 BNDRY/copy-isolation — modifying copy does NOT change source (proves
                             physical copy, not hard/sym link / junction)

Every test imports ``harness.skills`` which does not exist in Red → FAIL.

Feature ref: feature_3
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _write_bundle(root: Path, manifest_bytes: bytes | None = None) -> Path:
    bundle = root / "longtaskforagent"
    (bundle / ".claude-plugin").mkdir(parents=True)
    if manifest_bytes is None:
        manifest_bytes = json.dumps(
            {"name": "longtaskforagent", "version": "1.0.0"}, ensure_ascii=False
        ).encode("utf-8")
    (bundle / ".claude-plugin" / "plugin.json").write_bytes(manifest_bytes)
    (bundle / "skills").mkdir()
    (bundle / "skills" / "a.md").write_text("A\n", encoding="utf-8")
    (bundle / "skills" / "b.md").write_text("B\n", encoding="utf-8")
    return bundle


# ---------------------------------------------------------------------------
# T02 · FUNC/happy — sync_bundle physical copy + manifest sha parity
# ---------------------------------------------------------------------------


def test_t02_sync_bundle_copies_physically_and_sha_matches(tmp_path: Path) -> None:
    """Traces To §Interface Contract sync_bundle postcond + classDiagram."""
    from harness.skills import PluginRegistry, PluginSyncResult

    src = _write_bundle(tmp_path / "src")
    dst = tmp_path / "dst" / "plugins" / "longtaskforagent"
    dst.parent.mkdir(parents=True)

    reg = PluginRegistry()
    result = reg.sync_bundle(src, dst)

    assert isinstance(result, PluginSyncResult)
    # destination manifest exists, physical copy (not symlink)
    dst_manifest = dst / ".claude-plugin" / "plugin.json"
    assert dst_manifest.is_file()
    assert not dst_manifest.is_symlink()
    # all sibling files copied recursively
    assert (dst / "skills" / "a.md").read_text(encoding="utf-8") == "A\n"
    assert (dst / "skills" / "b.md").read_text(encoding="utf-8") == "B\n"

    # manifest_sha256 contract: both src and dst manifests must hash to the
    # same value and equal to the computed digest.
    src_bytes = (src / ".claude-plugin" / "plugin.json").read_bytes()
    dst_bytes = dst_manifest.read_bytes()
    expected = hashlib.sha256(src_bytes).hexdigest()
    assert result.manifest_sha256 == expected
    assert hashlib.sha256(dst_bytes).hexdigest() == expected

    # copied_file_count must be at least 3 (plugin.json + a.md + b.md)
    assert result.copied_file_count >= 3
    # dst_plugin_dir is stringified absolute path
    assert Path(result.dst_plugin_dir) == dst


# ---------------------------------------------------------------------------
# T18 · BNDRY — plugin.json size gating
# Traces To: §Boundary plugin.json 大小
# ---------------------------------------------------------------------------


def test_t18_read_manifest_zero_bytes_raises_corrupt(tmp_path: Path) -> None:
    from harness.skills import PluginManifestCorruptError, PluginRegistry

    bundle = _write_bundle(tmp_path / "src", manifest_bytes=b"")
    reg = PluginRegistry()
    with pytest.raises(PluginManifestCorruptError):
        reg.read_manifest(bundle)


def test_t18b_read_manifest_one_byte_minimal_valid(tmp_path: Path) -> None:
    """1 byte of ``{}`` is invalid JSON schema? Use ``{}`` 2 bytes — smallest
    syntactically valid JSON object. Contract says ≥1 byte legal JSON, so
    we exercise the 2-byte boundary to ensure tiny valid manifests pass."""
    from harness.skills import PluginManifest, PluginRegistry

    bundle = _write_bundle(tmp_path / "src", manifest_bytes=b'{"name":"x","version":"0"}')
    reg = PluginRegistry()
    manifest = reg.read_manifest(bundle)
    assert isinstance(manifest, PluginManifest)
    assert manifest.name == "x"
    assert manifest.version == "0"


def test_t18c_read_manifest_64kib_exact_accepted(tmp_path: Path) -> None:
    from harness.skills import PluginRegistry

    # craft a valid JSON of exactly 64 KiB (65536 bytes)
    padding_len = 65536 - len(b'{"name":"x","version":"0","pad":""}')
    assert padding_len > 0
    payload = b'{"name":"x","version":"0","pad":"' + (b"a" * padding_len) + b'"}'
    assert len(payload) == 65536
    bundle = _write_bundle(tmp_path / "src", manifest_bytes=payload)
    manifest = PluginRegistry().read_manifest(bundle)
    assert manifest.name == "x"


def test_t18d_read_manifest_over_64kib_rejects(tmp_path: Path) -> None:
    from harness.skills import PluginManifestCorruptError, PluginRegistry

    # 64 KiB + 1 → must reject to avoid DoS
    payload = b'{"name":"x","version":"0","pad":"' + (b"a" * (65536 + 1)) + b'"}'
    assert len(payload) > 65536
    bundle = _write_bundle(tmp_path / "src", manifest_bytes=payload)
    with pytest.raises(PluginManifestCorruptError):
        PluginRegistry().read_manifest(bundle)


def test_t18e_read_manifest_missing_raises_missing_error(tmp_path: Path) -> None:
    from harness.skills import PluginManifestMissingError, PluginRegistry

    bundle = tmp_path / "no_manifest_bundle"
    bundle.mkdir()
    with pytest.raises(PluginManifestMissingError):
        PluginRegistry().read_manifest(bundle)


# ---------------------------------------------------------------------------
# T20 · BNDRY — sync_bundle idempotency (second call with same args)
# Traces To: §Interface Contract sync_bundle postcond "幂等"
# ---------------------------------------------------------------------------


def test_t20_sync_bundle_is_idempotent(tmp_path: Path) -> None:
    from harness.skills import PluginRegistry

    src = _write_bundle(tmp_path / "src")
    dst = tmp_path / "dst" / "plugins" / "longtaskforagent"
    dst.parent.mkdir(parents=True)

    reg = PluginRegistry()
    r1 = reg.sync_bundle(src, dst)
    # second call with same args must NOT raise (dirs_exist_ok=True semantics)
    r2 = reg.sync_bundle(src, dst)

    # both results reference the same sha256 (content unchanged)
    assert r1.manifest_sha256 == r2.manifest_sha256
    # destination files still present and identical
    assert (dst / "skills" / "a.md").read_text(encoding="utf-8") == "A\n"
    assert (dst / "skills" / "b.md").read_text(encoding="utf-8") == "B\n"


# ---------------------------------------------------------------------------
# T27 · BNDRY — copy isolation (source untouched when copy is modified)
# Traces To: §Interface Contract sync_bundle src_bundle untouched · ASM-F10-WIN-JUNCTION
# Wrong-impl probe: a hard-link or symlink implementation would fail this
# because the two paths share inode / target.
# ---------------------------------------------------------------------------


def test_t27_copy_isolation_src_untouched_when_dst_modified(tmp_path: Path) -> None:
    from harness.skills import PluginRegistry

    src = _write_bundle(tmp_path / "src")
    dst = tmp_path / "dst" / "plugins" / "longtaskforagent"
    dst.parent.mkdir(parents=True)

    PluginRegistry().sync_bundle(src, dst)
    src_manifest = src / ".claude-plugin" / "plugin.json"
    dst_manifest = dst / ".claude-plugin" / "plugin.json"
    src_sha_before = hashlib.sha256(src_manifest.read_bytes()).hexdigest()

    # Mutate a byte in the destination manifest.
    mutated = dst_manifest.read_bytes() + b" "  # append one byte
    dst_manifest.write_bytes(mutated)

    # Source manifest must be unchanged.
    src_sha_after = hashlib.sha256(src_manifest.read_bytes()).hexdigest()
    assert (
        src_sha_after == src_sha_before
    ), "physical copy contract violated — source mutated when destination was touched"
    # And the two manifests must no longer share content
    assert (
        hashlib.sha256(dst_manifest.read_bytes()).hexdigest() != src_sha_after
    ), "destination manifest did not actually diverge — copy likely a link"


# ---------------------------------------------------------------------------
# Extra: bundle / dst conflict — src and dst mutually prefixed → error
# Traces To: §Boundary "src_bundle 与 dst_plugin_dir 不互为前缀"
# ---------------------------------------------------------------------------


def test_sync_bundle_rejects_nested_dst_inside_src(tmp_path: Path) -> None:
    from harness.skills import BundleSyncError, PluginRegistry

    src = _write_bundle(tmp_path / "src")
    # dst nested inside src → disallowed (would recurse)
    nested = src / "nested_copy"
    with pytest.raises(BundleSyncError):
        PluginRegistry().sync_bundle(src, nested)


__all__: list[str] = []
