"""F20 · PhaseRouteInvoker (IAPI-003 Consumer).

Wave 5 [API-W5-02]: ``invoke`` defaults to
``await asyncio.to_thread(phase_route_local.route, workdir)`` — same-process,
no subprocess fork. The legacy ``build_argv`` path is kept as a [DEPRECATED
Wave 5] fallback gated by ``HARNESS_PHASE_ROUTE_FALLBACK=1`` so plugin
v1.0.0 wire compatibility tests (T45–T47) and operational diagnostics still
anchor the contract.

Test instance variant supports ``set_responses`` / ``set_failure`` to drive
the orchestrator main loop deterministically — both short-circuit before the
in-proc / subprocess branch.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from harness.orchestrator.errors import PhaseRouteError, PhaseRouteParseError


class PhaseRouteResult(BaseModel):
    """Pydantic mirror of phase_route.py JSON output (Design §6.2.4)."""

    # NFR-015: new fields ignored, missing fields → defaults.
    model_config = ConfigDict(extra="ignore")

    ok: bool = False
    next_skill: str | None = None
    feature_id: str | None = None
    starting_new: bool = False
    needs_migration: bool = False
    # NFR-015 relaxed: ``counts`` may carry ints, None, or arbitrary scalar
    # values; we keep the field loose so future phase_route revisions don't
    # break the orchestrator.
    counts: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


class _AuditAdapter(Protocol):
    async def append_raw(
        self, run_id: str, kind: str, payload: dict[str, Any], ts: str
    ) -> None: ...


class PhaseRouteInvoker:
    """Real subprocess invoker for phase_route.py.

    Test code may pre-program :meth:`set_responses` (a queue of dicts) or
    :meth:`set_failure` to short-circuit the actual subprocess and return
    deterministic fixtures — used by RunOrchestrator unit tests.
    """

    def __init__(
        self,
        *,
        plugin_dir: Path,
        audit_writer: _AuditAdapter | None = None,
        run_id: str | None = None,
    ) -> None:
        self.plugin_dir = Path(plugin_dir)
        self._audit_writer = audit_writer
        self._run_id = run_id or "phase-route"
        self._scripted_responses: list[dict[str, Any]] | None = None
        self._scripted_failure: tuple[int, str] | None = None
        self._default_response: dict[str, Any] = {"ok": True, "next_skill": None}
        self.invocation_count: int = 0

    # ------------------------------------------------------------------
    # Test-injection hooks
    # ------------------------------------------------------------------
    def set_responses(self, responses: list[dict[str, Any]]) -> None:
        self._scripted_responses = list(responses)
        self._scripted_failure = None

    def set_default_response(self, payload: dict[str, Any]) -> None:
        self._default_response = dict(payload)

    def set_failure(self, *, exit_code: int, stderr: str) -> None:
        self._scripted_failure = (exit_code, stderr)

    # ------------------------------------------------------------------
    # SEC: shell-injection guard helpers (T38)
    # ------------------------------------------------------------------
    @property
    def uses_shell(self) -> bool:
        return False

    def build_argv(self, *, workdir: Path) -> list[str]:
        script = self.plugin_dir / "scripts" / "phase_route.py"
        python = sys.executable or shutil.which("python") or "python"
        return [str(python), str(script), "--json"]

    # ------------------------------------------------------------------
    # invoke
    # ------------------------------------------------------------------
    async def invoke(self, *, workdir: Path, timeout_s: float = 30.0) -> PhaseRouteResult:
        if timeout_s <= 0:
            raise ValueError(f"timeout_s must be > 0; got {timeout_s!r}")
        self.invocation_count += 1

        # Test failure fixture — return ok=False with stderr in errors[].
        if self._scripted_failure is not None:
            exit_code, stderr = self._scripted_failure
            raise PhaseRouteError(f"phase_route exited {exit_code}: {stderr}", exit_code=exit_code)

        # Test response queue — pop the next deterministic dict; when the
        # scripted queue is exhausted we fall back to an implicit ST-Go
        # terminator (`next_skill=None`) so loops drain naturally.
        if self._scripted_responses is not None:
            if self._scripted_responses:
                payload = self._scripted_responses.pop(0)
            else:
                payload = self._default_response
            try:
                return PhaseRouteResult.model_validate(payload)
            except Exception as exc:
                raise PhaseRouteParseError(str(exc)) from exc

        # Wave 5 [API-W5-02 / FR-054 AC-1] — same-process path is the default;
        # ``await asyncio.to_thread(phase_route_local.route, workdir)`` keeps
        # the call stack free of subprocess fork. The legacy subprocess path
        # is retained as a [DEPRECATED Wave 5] fallback gated on
        # ``HARNESS_PHASE_ROUTE_FALLBACK=1`` so the W4 baseline tests
        # (T07/T08/T45/T46/T47) and operational diagnostic / plugin v1.0.0
        # cross-impl scenarios still anchor the wire contract. Full retirement
        # is scheduled for v1.2 once the plugin cross-impl tests retire.
        if os.environ.get("HARNESS_PHASE_ROUTE_FALLBACK", "") != "1":
            from harness.orchestrator import phase_route_local

            try:
                payload = await asyncio.to_thread(phase_route_local.route, workdir)
            except Exception as exc:
                raise PhaseRouteParseError(str(exc)) from exc
            try:
                return PhaseRouteResult.model_validate(payload)
            except Exception as exc:
                raise PhaseRouteParseError(str(exc)) from exc

        # Real subprocess invocation [DEPRECATED Wave 5 — fallback / wire
        # compatibility opt-in via HARNESS_PHASE_ROUTE_FALLBACK=1].
        argv = self.build_argv(workdir=workdir)
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
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
            raise PhaseRouteError("phase_route timeout") from exc

        if proc.returncode not in (0, None):
            tail = (stderr_b or b"").decode("utf-8", errors="replace").strip()
            raise PhaseRouteError(
                f"phase_route exit={proc.returncode}: {tail}",
                exit_code=proc.returncode,
            )

        text = (stdout_b or b"").decode("utf-8", errors="replace").strip()
        if not text:
            payload = {"ok": True}
        else:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                if self._audit_writer is not None:
                    try:
                        await self._audit_writer.append_raw(
                            self._run_id,
                            "phase_route_parse_error",
                            {"stdout_tail": text[-512:], "error": str(exc)},
                            datetime.now(timezone.utc).isoformat(),
                        )
                    except Exception:
                        # Audit failure is non-fatal here; the parse error
                        # itself is the headline.
                        pass
                raise PhaseRouteParseError(f"phase_route stdout not JSON: {text[:120]!r}") from exc

        try:
            return PhaseRouteResult.model_validate(payload)
        except Exception as exc:
            raise PhaseRouteParseError(str(exc)) from exc


__all__ = ["PhaseRouteInvoker", "PhaseRouteResult"]
