"""F19 · ModelRulesStore — JSON persistence for ``~/.harness/model_rules.json``.

Feature design §IC ModelRulesStore.load/save:
    * load(): returns ``list[ModelRule]``; empty / missing → []; invalid JSON
      or schema mismatch → ``ModelRulesCorruptError``.
    * save(): atomic write (temp + rename); POSIX mode 0o600.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .models import ModelRule


class ModelRulesCorruptError(Exception):
    """Raised by ModelRulesStore.load when JSON is invalid / schema mismatch."""


class ModelRulesStoreError(Exception):
    """Raised by ModelRulesStore.save on irrecoverable disk I/O failure."""


class ModelRulesStore:
    """Persist + retrieve ``ModelRule`` list in a single JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    # --------------------------------------------------------------- load
    def load(self) -> list[ModelRule]:
        if not self._path.exists():
            return []
        try:
            raw = self._path.read_bytes()
        except OSError as exc:  # pragma: no cover
            raise ModelRulesCorruptError(f"cannot read {self._path}: {exc}") from exc

        if not raw.strip():
            return []

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelRulesCorruptError(f"model_rules.json is not valid JSON: {exc}") from exc

        if not isinstance(data, list):
            raise ModelRulesCorruptError(
                f"model_rules.json root must be a list, got {type(data).__name__}"
            )

        try:
            return [ModelRule.model_validate(item) for item in data]
        except ValidationError as exc:
            raise ModelRulesCorruptError(
                f"model_rules.json failed schema validation: {exc}"
            ) from exc

    # --------------------------------------------------------------- save
    def save(self, rules: list[ModelRule]) -> None:
        """Atomic write + POSIX 0o600."""
        payload = json.dumps(
            [rule.model_dump(mode="json") for rule in rules],
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)

        old_umask: int | None = None
        if sys.platform != "win32":
            old_umask = os.umask(0o077)

        tmp_fd: int | None = None
        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix="model_rules.",
                suffix=".json.tmp",
                dir=str(parent),
            )
            tmp_fd = fd
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "wb") as fh:
                tmp_fd = None
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            if sys.platform != "win32":
                os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._path)
            tmp_path = None
        except OSError as exc:  # pragma: no cover
            raise ModelRulesStoreError(f"failed to persist model_rules.json: {exc}") from exc
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


__all__ = [
    "ModelRulesStore",
    "ModelRulesCorruptError",
    "ModelRulesStoreError",
]
