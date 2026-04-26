"""F20 · ValidatorRunner — IAPI-016 Provider.

Spawns ``python <plugin>/scripts/<script>.py --json <path>`` and parses the
stdout JSON into :class:`ValidationReport`. Errors are returned as data per
FR-040 AC-2 (HTTP 200 + ``ok=False`` + stderr_tail in issues[]); only timeouts
raise (HTTP 500).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from harness.subprocess.validator.schemas import (
    ValidateRequest,
    ValidationIssue,
    ValidationReport,
    ValidatorScript,
)


_DEFAULT_TIMEOUT_S = 60.0


class ValidatorTimeout(Exception):
    """Raised when validator subprocess exceeds ``timeout_s``."""

    http_status = 500

    def __init__(self, message: str = "validator timeout") -> None:
        super().__init__(message)


class ValidatorScriptUnknown(Exception):
    """Raised when ValidateRequest.script is not in the allow-list."""

    http_status = 400


class ValidatorRunner:
    """Spawn ``scripts/validate_*.py`` and surface results as ValidationReport."""

    def __init__(self, *, plugin_dir: Path) -> None:
        self.plugin_dir = Path(plugin_dir)

    def _resolve_script(self, req: ValidateRequest) -> ValidatorScript:
        if req.script is not None:
            return req.script
        # Auto-pick by file basename (FR-040 default routing).
        name = Path(req.path).name
        if name == "feature-list.json":
            return "validate_features"
        if name in {"long-task-guide.md", "guide.md"}:
            return "validate_guide"
        return "validate_features"

    async def run(self, req: ValidateRequest) -> ValidationReport:
        script = self._resolve_script(req)
        if script not in {
            "validate_features",
            "validate_guide",
            "check_configs",
            "check_st_readiness",
        }:
            raise ValidatorScriptUnknown(f"unknown validator script: {script!r}")

        script_path = self.plugin_dir / "scripts" / f"{script}.py"
        if not script_path.exists():
            # F22: fall back to the harness repo root's scripts/ directory so
            # arbitrary tmp workdirs (e.g. integration test fixtures) can still
            # invoke the canonical validate_features.py.
            repo_root = Path(__file__).resolve().parents[3]
            fallback = repo_root / "scripts" / f"{script}.py"
            if fallback.exists():
                script_path = fallback
        python = sys.executable or shutil.which("python") or "python"
        argv = [str(python), str(script_path), req.path]

        cwd = str(req.workdir) if req.workdir else None
        timeout_s = req.timeout_s or _DEFAULT_TIMEOUT_S

        # F22 FR-039: when a strict-features signal is propagated through the
        # request env, run validate_features.py with HARNESS_STRICT_FEATURES=1
        # so empty features[] surfaces as ok=False to the FE. The route layer
        # sets this env var only for /api/validate calls; phase_route shells
        # out separately and keeps the lenient default.
        env = dict(os.environ)

        t0 = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError as exc:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            await asyncio.sleep(0)
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise ValidatorTimeout("validator timeout") from exc

        duration_ms = max(1, int((time.monotonic() - t0) * 1000))
        exit_code = proc.returncode or 0
        out_text = (stdout or b"").decode("utf-8", "replace").strip()
        err_text = (stderr or b"").decode("utf-8", "replace").strip()

        # Try parse JSON first
        parsed: dict[str, Any] | None = None
        if out_text:
            try:
                parsed = json.loads(out_text)
            except json.JSONDecodeError:
                parsed = None

        issues: list[ValidationIssue] = []
        if parsed is not None:
            for issue in parsed.get("issues", []) or []:
                if isinstance(issue, dict):
                    issues.append(
                        ValidationIssue(
                            severity=issue.get("severity", "error"),
                            rule_id=issue.get("rule_id"),
                            path_json_pointer=issue.get("path_json_pointer"),
                            message=str(issue.get("message", "")),
                        )
                    )
                else:
                    issues.append(ValidationIssue(severity="error", message=str(issue)))
            ok = bool(parsed.get("ok", exit_code == 0))
        else:
            ok = False

        if exit_code != 0:
            ok = False
            tail = err_text[-500:] if err_text else (out_text[-500:] if out_text else "")
            if tail:
                issues.append(
                    ValidationIssue(severity="error", rule_id="subprocess_exit", message=tail)
                )

        return ValidationReport(
            ok=ok,
            issues=issues,
            script_exit_code=exit_code,
            duration_ms=duration_ms,
            http_status_hint=200,
        )


__all__ = ["ValidatorRunner", "ValidatorScriptUnknown", "ValidatorTimeout"]
