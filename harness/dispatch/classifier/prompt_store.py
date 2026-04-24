"""F19 · PromptStore — classifier prompt versioned storage.

Feature design §IC PromptStore.get/put + §BC content:
    * get(): returns ``ClassifierPrompt(current, history[])``; absent file →
      first-read returns built-in default prompt + ``history=[]``.
    * put(content): validate (non-empty, ≤ 32 KB), atomic write, append a
      ``ClassifierPromptRev`` (rev=N+1, saved_at ISO, hash=sha256 hex,
      summary=first 120 chars of first line); return the new prompt.
    * Path-traversal defense: if HARNESS_HOME is set, the store path must
      resolve inside HARNESS_HOME (T43); otherwise PromptStoreError.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from .errors import PromptStoreCorruptError, PromptStoreError, PromptValidationError
from .models import ClassifierPrompt, ClassifierPromptRev


_MAX_PROMPT_BYTES = 32 * 1024  # 32 KB inclusive per §BC row.


_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / "default_prompt.md"


def _read_default_prompt() -> str:
    try:
        return _DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover
        return "You are Harness's ticket classifier. Return strict JSON per the schema."


class PromptStore:
    """Versioned classifier prompt store (append-only history)."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    # -------------------------------------------------------- security
    def _check_path_inside_home(self) -> None:
        """Reject paths that escape HARNESS_HOME via ``..`` / symlink (T43)."""
        env = os.environ.get("HARNESS_HOME", "")
        if not env:
            return
        try:
            home = Path(env).resolve()
            target = self._path.resolve()
        except (OSError, RuntimeError) as exc:  # pragma: no cover
            raise PromptStoreError(f"cannot resolve path: {exc}") from exc

        try:
            target.relative_to(home)
        except ValueError as exc:
            raise PromptStoreError(f"path {target!r} escapes HARNESS_HOME {home!r}") from exc

    # -------------------------------------------------------- get
    def get(self) -> ClassifierPrompt:
        if not self._path.exists():
            return ClassifierPrompt(current=_read_default_prompt(), history=[])
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            raise PromptStoreError(f"cannot read {self._path}: {exc}") from exc
        if not raw.strip():
            return ClassifierPrompt(current=_read_default_prompt(), history=[])
        try:
            data = json.loads(raw)
            return ClassifierPrompt.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise PromptStoreCorruptError(f"prompt store JSON corrupt: {exc}") from exc

    # -------------------------------------------------------- put
    def put(self, content: str) -> ClassifierPrompt:
        if not content:
            raise PromptValidationError("prompt content must be non-empty")
        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_PROMPT_BYTES:
            raise PromptValidationError(f"prompt content exceeds {_MAX_PROMPT_BYTES} bytes")

        # Path traversal defense.
        self._check_path_inside_home()

        # Load current state (missing → default prompt + empty history).
        try:
            existing = self.get()
        except PromptStoreCorruptError:
            existing = ClassifierPrompt(current=_read_default_prompt(), history=[])

        next_rev = (existing.history[-1].rev + 1) if existing.history else 1
        saved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sha256 = hashlib.sha256(encoded).hexdigest()
        first_line = (content.splitlines() or [content])[0][:120]

        new_rev = ClassifierPromptRev(
            rev=next_rev,
            saved_at=saved_at,
            hash=sha256,
            summary=first_line,
        )

        updated = ClassifierPrompt(
            current=content,
            history=[*existing.history, new_rev],
        )

        self._atomic_write(updated)
        return updated

    # -------------------------------------------------------- atomic write
    def _atomic_write(self, prompt: ClassifierPrompt) -> None:
        payload = json.dumps(
            prompt.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        parent = self._path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PromptStoreError(f"cannot create {parent}: {exc}") from exc

        old_umask: int | None = None
        if sys.platform != "win32":
            old_umask = os.umask(0o077)
        tmp_fd: int | None = None
        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(prefix="prompt.", suffix=".json.tmp", dir=str(parent))
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
        except OSError as exc:
            raise PromptStoreError(f"cannot persist prompt: {exc}") from exc
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


__all__ = ["PromptStore"]
