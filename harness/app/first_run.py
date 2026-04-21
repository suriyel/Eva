"""FirstRunWizard — FR-050 ``~/.harness/`` bootstrap.

Design §6 · Implementation Summary item 3:
    * ``~/.harness/`` created with POSIX mode ``0o700`` (Windows: no ACL for v1).
    * ``config.json`` written via ``ConfigStore.save`` (atomic rename + leak guard).
    * ``is_first_run()`` → True when config.json missing OR parent dir missing.
    * ``bootstrap()`` returns ``FirstRunResult { home_path, created_files,
      welcome_message }``; welcome_message is simplified-Chinese per NFR-010.
    * When ``~/.harness/`` resolves to a pre-existing NON-directory path (e.g.
      a plain file via attacker-controlled ``HARNESS_HOME``) → raises
      ``HarnessHomeWriteError``; never overwrites the file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..config import ConfigStore, HarnessConfig


class HarnessHomeWriteError(Exception):
    """Raised when ``~/.harness/`` cannot be created (permission / non-dir)."""


class FirstRunResult(BaseModel):
    """Postcondition schema for ``FirstRunWizard.bootstrap()``."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    home_path: Path
    created_files: list[Path]
    welcome_message: str


_WELCOME_MESSAGE_ZH = "Welcome, 已初始化 ~/.harness/"


class FirstRunWizard:
    """Detect first-run and provision ``~/.harness/`` + config.json."""

    def __init__(self, store: ConfigStore) -> None:
        self._store = store

    # ----------------------------------------------------------- is_first_run
    def is_first_run(self) -> bool:
        path = self._store.path
        if not path.parent.is_dir():
            return True
        if not path.exists():
            return True
        return False

    # ----------------------------------------------------------- bootstrap
    def bootstrap(self) -> FirstRunResult:
        home = self._store.path.parent

        # If home is an existing non-directory path → refuse (path-traversal defence).
        if home.exists() and not home.is_dir():
            raise HarnessHomeWriteError(
                f"HARNESS_HOME points at existing non-directory path: {home}"
            )

        # mkdir with owner-only mode on POSIX (ignored on Windows).
        try:
            if sys.platform != "win32":
                home.mkdir(mode=0o700, parents=True, exist_ok=True)
                # ``mode`` is honoured only on creation; if the dir already exists,
                # fix the permission explicitly.
                os.chmod(home, 0o700)
            else:  # pragma: no cover — no Linux CI for Windows
                home.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as exc:
            raise HarnessHomeWriteError(f"cannot create harness home dir {home}: {exc}") from exc

        created: list[Path] = []
        cfg_path = self._store.path
        if not cfg_path.exists():
            try:
                self._store.save(HarnessConfig.default())
            except OSError as exc:
                raise HarnessHomeWriteError(
                    f"cannot write config.json at {cfg_path}: {exc}"
                ) from exc
            created.append(cfg_path)

        return FirstRunResult(
            home_path=home,
            created_files=created,
            welcome_message=_WELCOME_MESSAGE_ZH,
        )
