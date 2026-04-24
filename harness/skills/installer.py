"""F10 · SkillsInstaller — git clone / pull / local copy orchestration.

All git invocations go through ``subprocess.run`` with an argv list (never
``shell=True``) — mirrors F01 :class:`ClaudeAuthDetector` pattern.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .errors import (
    GitSubprocessError,
    GitUrlRejectedError,
    SkillsInstallBusyError,
    TargetPathEscapeError,
)
from .models import SkillsInstallRequest, SkillsInstallResult
from .registry import PluginRegistry


_GIT_TIMEOUT_SEC = 120
_MAX_URL_LEN = 2048


def _is_git_url_allowed(source: str) -> bool:
    """Whitelist: https://... OR git@host:path. Reject shell meta / CR / LF / ``..``."""

    if not source or not isinstance(source, str):
        return False
    if len(source) > _MAX_URL_LEN:
        return False

    # Forbid ANY control character (CR, LF, NUL, ...) and shell metacharacters.
    forbidden = set(";&|`$><\r\n\t\x00")
    if any(ch in forbidden for ch in source):
        return False
    # Forbid path traversal anywhere in the URL.
    if ".." in source:
        return False
    # Must be ASCII only.
    try:
        source.encode("ascii")
    except UnicodeEncodeError:
        return False

    # Permitted shapes:
    #   https://<host>/<path>...
    #   git@<host>:<path>
    if source.startswith("https://"):
        try:
            parsed = urlparse(source)
        except ValueError:
            return False
        host = parsed.hostname
        if not host or not parsed.path:
            return False
        return True

    # git@host:path
    if source.startswith("git@"):
        at_split = source.split("@", 1)
        if len(at_split) != 2:
            return False
        rest = at_split[1]
        if ":" not in rest:
            return False
        host, path = rest.split(":", 1)
        if not host or not path:
            return False
        return True

    return False


def _validate_target_dir(target_dir: str, workdir: Path) -> Path:
    """Ensure target_dir resolves under workdir/plugins/<subname>.

    Rejects absolute paths, path traversal, and a bare ``plugins`` root.
    """

    if not isinstance(target_dir, str) or not target_dir:
        raise TargetPathEscapeError("target_dir must be a non-empty relative path")
    # Absolute path disallowed.
    if target_dir.startswith("/") or target_dir.startswith("\\"):
        raise TargetPathEscapeError(f"target_dir must be relative: {target_dir!r}")
    if Path(target_dir).is_absolute():
        raise TargetPathEscapeError(f"target_dir must be relative: {target_dir!r}")
    if ".." in Path(target_dir).parts:
        raise TargetPathEscapeError(f"target_dir contains '..': {target_dir!r}")

    plugins_root = (workdir / "plugins").resolve()
    candidate = (workdir / target_dir).resolve()
    # Must be UNDER plugins/, not equal to it.
    try:
        if not candidate.is_relative_to(plugins_root):
            raise TargetPathEscapeError(f"target_dir escapes {plugins_root}: {candidate}")
    except AttributeError:  # pragma: no cover — Python < 3.9
        if not str(candidate).startswith(str(plugins_root) + "/"):
            raise TargetPathEscapeError(f"target_dir escapes {plugins_root}: {candidate}")
    if candidate == plugins_root:
        raise TargetPathEscapeError(
            "target_dir must include a subdirectory under plugins/, not 'plugins' itself"
        )
    return candidate


class SkillsInstaller:
    """Orchestrates git clone / pull / local-copy under workdir/plugins/."""

    def __init__(self, *, registry: PluginRegistry | None = None) -> None:
        self._registry = registry or PluginRegistry()

    # ----------------------------------------------------------------- install
    def install(
        self,
        req: SkillsInstallRequest,
        *,
        workdir: Path,
    ) -> SkillsInstallResult:
        workdir = Path(workdir)

        # Run-lock check up front (applies to all kinds).
        self._check_run_lock(workdir)

        # Kind-specific validation.
        if req.kind == "clone":
            if not _is_git_url_allowed(req.source):
                raise GitUrlRejectedError(f"URL not allowed (whitelist violation): {req.source!r}")
            target_dir = req.target_dir or "plugins/longtaskforagent"
            target_path = _validate_target_dir(target_dir, workdir)
            return self._do_clone(req.source, target_path, workdir)

        if req.kind == "pull":
            target_dir = req.target_dir or "plugins/longtaskforagent"
            target_path = _validate_target_dir(target_dir, workdir)
            return self.pull(str(target_path), workdir=workdir, _skip_lock_check=True)

        if req.kind == "local":
            # source must be absolute existing directory (no shell redirect).
            src_path = Path(req.source)
            if not req.source or not src_path.is_absolute() or not src_path.is_dir():
                raise GitUrlRejectedError(
                    f"local source must be an absolute existing directory: {req.source!r}"
                )
            target_dir = req.target_dir or "plugins/longtaskforagent"
            target_path = _validate_target_dir(target_dir, workdir)
            return self._do_local_copy(src_path, target_path)

        raise GitUrlRejectedError(f"unsupported kind: {req.kind!r}")

    # ------------------------------------------------------------------- pull
    def pull(
        self,
        target_dir: str,
        *,
        workdir: Path,
        _skip_lock_check: bool = False,
    ) -> SkillsInstallResult:
        workdir = Path(workdir)
        if not _skip_lock_check:
            self._check_run_lock(workdir)

        target = Path(target_dir)
        if not target.is_absolute():
            target = (workdir / target_dir).resolve()
        # target must live under workdir/plugins/
        plugins_root = (workdir / "plugins").resolve()
        try:
            if not target.resolve().is_relative_to(plugins_root):
                raise TargetPathEscapeError(f"pull target outside {plugins_root}: {target}")
        except AttributeError:  # pragma: no cover
            pass
        if not (target / ".git").exists():
            raise TargetPathEscapeError(f"pull target is not a git repo (missing .git/): {target}")

        argv = ["git", "-C", str(target), "pull", "--ff-only"]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=_GIT_TIMEOUT_SEC,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitSubprocessError(f"git pull failed: {exc!r}") from exc
        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "").splitlines()[-5:]
            raise GitSubprocessError(f"git pull exit={proc.returncode}: {'; '.join(stderr_tail)}")

        manifest = self._registry.read_manifest(target)
        message = (proc.stdout or "").strip() or "pull 完成"
        return SkillsInstallResult(
            ok=True,
            commit_sha=manifest.commit_sha,
            message=message,
        )

    # ------------------------------------------------------------ private ops
    def _do_clone(self, source: str, target_path: Path, workdir: Path) -> SkillsInstallResult:
        # Ensure parent (e.g. workdir/plugins/) exists.
        target_path.parent.mkdir(parents=True, exist_ok=True)
        # If target exists already, fail fast (409 semantics) — do not let
        # git clone error out late.
        if target_path.exists():
            raise GitSubprocessError(f"target already exists: {target_path}")

        argv = [
            "git",
            "clone",
            "--depth",
            "1",
            "--",
            source,
            str(target_path),
        ]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=_GIT_TIMEOUT_SEC,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitSubprocessError(f"git clone failed: {exc!r}") from exc
        if proc.returncode != 0:
            # Cleanup half-cloned directory so retries work.
            if target_path.exists():
                shutil.rmtree(str(target_path), ignore_errors=True)
            stderr_tail = (proc.stderr or "").splitlines()[-5:]
            raise GitSubprocessError(f"git clone exit={proc.returncode}: {'; '.join(stderr_tail)}")

        manifest = self._registry.read_manifest(target_path)
        return SkillsInstallResult(
            ok=True,
            commit_sha=manifest.commit_sha,
            message=f"clone 完成 ({source})",
        )

    def _do_local_copy(self, src: Path, target_path: Path) -> SkillsInstallResult:
        if target_path.exists():
            raise GitSubprocessError(f"target already exists: {target_path}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(str(src), str(target_path), symlinks=False)
        except OSError as exc:
            raise GitSubprocessError(f"local copy failed {src} -> {target_path}: {exc!r}") from exc

        # If the local dir has a .git, read commit_sha; otherwise None.
        manifest = self._registry.read_manifest(target_path)
        return SkillsInstallResult(
            ok=True,
            commit_sha=manifest.commit_sha,
            message=f"本地复制完成 ({src})",
        )

    # ---------------------------------------------------------------- shared
    @staticmethod
    def _check_run_lock(workdir: Path) -> None:
        lock = workdir / ".harness" / "run.lock"
        if lock.exists():
            raise SkillsInstallBusyError(f"run 进行中，skills 安装被拒绝 (lock: {lock})")


__all__ = ["SkillsInstaller"]
