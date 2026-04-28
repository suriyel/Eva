"""ConfigStore — atomic JSON load/save for ``~/.harness/config.json``.

Design §6 · Implementation Summary item 1/3:
    * ``default_path()`` honours ``HARNESS_HOME`` env var (empty string == unset).
    * ``load()`` returns ``HarnessConfig.default()`` when file missing; raises
      ``ConfigCorruptError`` when JSON/pydantic validation fails.
    * ``save(config)`` writes via temp file + atomic rename; payload is scanned
      by ``_detect_secret_leak`` before any disk write.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .schema import ConfigCorruptError, HarnessConfig, SecretLeakError


# ---------------------------------------------------------------------------
# Leak detector patterns (NFR-008 defense-in-depth).
# ---------------------------------------------------------------------------
_KNOWN_KEY_PREFIXES = ("sk-", "sk-ant-", "xai-")
_PEM_BLOCK_RE = re.compile(rb"-----BEGIN [A-Z ]+-----")
# Continuous base64-ish run of length >= 32. Using the base64 alphabet plus
# padding '='. We require a contiguous run to avoid false positives on
# ordinary short identifiers.
_BASE64_RUN_RE = re.compile(rb"[A-Za-z0-9+/]{32,}={0,2}")


def _detect_secret_leak(payload: bytes, *, field_path: str = "<payload>") -> None:
    """Raise ``SecretLeakError`` when payload looks like a plaintext secret.

    Heuristics (conservative but explicit):
      * Any known LLM-key prefix (``sk-``, ``sk-ant-``, ``xai-``).
      * PEM block marker (``-----BEGIN ...-----``).
      * Any contiguous base64 run >= 32 chars.
    """
    for prefix in _KNOWN_KEY_PREFIXES:
        if prefix.encode("ascii") in payload:
            raise SecretLeakError(field_path, f"known key prefix {prefix!r} in payload")
    if _PEM_BLOCK_RE.search(payload):
        raise SecretLeakError(field_path, "PEM block detected in payload")
    if _BASE64_RUN_RE.search(payload):
        raise SecretLeakError(field_path, "base64 run (>=32 chars) detected in payload")


class ConfigStore:
    """Facade over ``~/.harness/config.json``."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    @classmethod
    def default_path(cls) -> Path:
        """Resolve the default config path via ``HARNESS_HOME`` env var.

        Empty-string ``HARNESS_HOME`` is treated as unset (§Boundary row).
        The value is **not** shell-expanded — ``HARNESS_HOME="~"`` is literal.
        """
        env = os.environ.get("HARNESS_HOME", "")
        home = Path(env) if env else (Path.home() / ".harness")
        return home / "config.json"

    # ------------------------------------------------------------------ load
    def load(self) -> HarnessConfig:
        """Read + validate config.json; return default() when absent."""
        if not self._path.exists():
            return HarnessConfig.default()
        try:
            raw = self._path.read_bytes()
        except OSError as exc:  # pragma: no cover — platform-specific
            raise ConfigCorruptError(f"cannot read {self._path}: {exc}") from exc

        if not raw.strip():
            raise ConfigCorruptError(
                f"config.json is empty (0 or whitespace-only bytes): {self._path}"
            )

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigCorruptError(f"config.json is not valid JSON: {exc}") from exc

        try:
            return HarnessConfig.model_validate(data)
        except ValidationError as exc:
            raise ConfigCorruptError(f"config.json failed schema validation: {exc}") from exc

    # ------------------------------------------------------------------ save
    def save(self, config: HarnessConfig) -> None:
        """Write config.json atomically; refuse if payload looks like a secret."""
        # Include extra fields on subclasses that opted into ``extra="allow"``
        # (leak-detector is defense-in-depth against schema bypass).
        payload_dict = config.model_dump(mode="json", by_alias=False)
        try:
            extras = getattr(config, "__pydantic_extra__", None)
        except Exception:  # pragma: no cover
            extras = None
        if extras:
            # Merge extras so leak detector sees the injected plaintext.
            merged = dict(payload_dict)
            for k, v in dict(extras).items():
                merged.setdefault(k, v)
            payload_dict = merged

        payload = json.dumps(payload_dict, ensure_ascii=False, indent=2).encode("utf-8")
        _detect_secret_leak(payload, field_path=str(self._path))

        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)

        # POSIX: tighten umask so the temp file is created 0600.
        old_umask: int | None = None
        if sys.platform != "win32":
            old_umask = os.umask(0o077)
        tmp_fd: int | None = None
        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix="config.",
                suffix=".json.tmp",
                dir=str(parent),
            )
            tmp_fd = fd
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "wb") as fh:
                tmp_fd = None  # fd now owned by file handle
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            if sys.platform != "win32":
                os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._path)
            tmp_path = None
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:  # pragma: no cover
                    pass
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:  # pragma: no cover
                    pass
            if old_umask is not None:
                os.umask(old_umask)

    # ---------------------------------------------------------------- workdirs
    def add_workdir(self, path: str) -> HarnessConfig:
        """Append ``path`` to ``workdirs`` (no-op if already present); persist."""
        try:
            cfg = self.load()
        except ConfigCorruptError:
            cfg = HarnessConfig.default()
        if path not in cfg.workdirs:
            cfg = cfg.model_copy(update={"workdirs": [*cfg.workdirs, path]})
            self.save(cfg)
        return cfg

    def set_current_workdir(self, path: str | None) -> HarnessConfig:
        """Mark ``path`` as the active workdir (must be in ``workdirs``)."""
        try:
            cfg = self.load()
        except ConfigCorruptError:
            cfg = HarnessConfig.default()
        if path is not None and path not in cfg.workdirs:
            raise ValueError(f"workdir not registered: {path!r}")
        cfg = cfg.model_copy(update={"current_workdir": path})
        self.save(cfg)
        return cfg

    def remove_workdir(self, path: str) -> HarnessConfig:
        """Remove ``path`` from ``workdirs``; clear ``current`` if it matched."""
        try:
            cfg = self.load()
        except ConfigCorruptError:
            cfg = HarnessConfig.default()
        new_list = [p for p in cfg.workdirs if p != path]
        new_current = None if cfg.current_workdir == path else cfg.current_workdir
        cfg = cfg.model_copy(
            update={"workdirs": new_list, "current_workdir": new_current}
        )
        self.save(cfg)
        return cfg
