"""F20 · IAPI-002 files REST helpers (`/api/files/tree`, `/api/files/read`).

Path-traversal hardening (T37): every input path is resolved relative to
``workdir`` and rejected if the resolved path escapes the workdir or is
absolute and points outside the workdir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class PathTraversalError(Exception):
    http_status = 400

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"path traversal blocked: {path!r}")


class FileNotFound(Exception):
    http_status = 404


class FilesService:
    def __init__(self, *, workdir: Path) -> None:
        self.workdir = Path(workdir).resolve()

    def _resolve(self, path: str) -> Path:
        if path is None or not path:
            raise PathTraversalError(str(path))
        candidate = Path(path)
        if candidate.is_absolute():
            try:
                resolved = candidate.resolve()
            except OSError as exc:
                raise PathTraversalError(path) from exc
            if not _is_relative_to(resolved, self.workdir):
                raise PathTraversalError(path)
            return resolved
        # Relative — check for parent-references after normalization.
        joined = (self.workdir / candidate).resolve()
        if not _is_relative_to(joined, self.workdir):
            raise PathTraversalError(path)
        return joined

    async def read_file_content(self, path: str) -> dict[str, Any]:
        resolved = self._resolve(path)
        if not resolved.exists():
            raise FileNotFound(str(resolved))
        try:
            content = resolved.read_text(encoding="utf-8")
            return {
                "path": str(resolved),
                "mime": "text/plain",
                "encoding": "utf-8",
                "content": content,
            }
        except UnicodeDecodeError:
            data = resolved.read_bytes()
            import base64

            return {
                "path": str(resolved),
                "mime": "application/octet-stream",
                "encoding": "binary",
                "content": base64.b64encode(data).decode("ascii"),
            }

    async def read_file_tree(self, root: str = "docs") -> dict[str, Any]:
        """Recursively scan ``root`` (resolved under workdir) and return entries.

        Response shape (F22 §IC Section C):
            ``{root: <abs path>, entries: [{path, kind, size?}], nodes: [...]}``
        Both ``entries`` and ``nodes`` carry the same payload — ``entries`` is
        F22 design IC; ``nodes`` is preserved for F23 R20 INTG/asgi-rest test
        backwards-compat (test_f23_feature_23_r20_get_files_tree_returns_filetree).
        Hidden dotfiles and ``__pycache__`` / ``node_modules`` directories are
        skipped to keep the payload bounded.
        """
        resolved = self._resolve(root)
        entries: list[dict[str, Any]] = []
        if resolved.exists() and resolved.is_dir():
            base = self.workdir
            skip_dirs = {"__pycache__", "node_modules", ".git", ".venv", "dist", "build"}
            for path in sorted(resolved.rglob("*")):
                name = path.name
                if name.startswith(".") and name not in (".env.example",):
                    continue
                rel = path.relative_to(base).as_posix()
                if any(seg in skip_dirs for seg in rel.split("/")):
                    continue
                if path.is_dir():
                    entries.append({"path": rel, "kind": "dir"})
                elif path.is_file():
                    try:
                        size = path.stat().st_size
                    except OSError:
                        size = 0
                    entries.append({"path": rel, "kind": "file", "size": size})
        return {"root": str(resolved), "entries": entries, "nodes": entries}


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


__all__ = ["FileNotFound", "FilesService", "PathTraversalError"]
