"""F19 · ClassifierService facade (IAPI-010).

Feature design §IC ClassifierService.classify / test_connection:
    * classify(req) — never raises:
        - enabled=False → RuleBackend.decide() (skip LLM entirely).
        - enabled=True → FallbackDecorator(primary=LlmBackend, fallback=RuleBackend)
          → audit warning on LLM failure → RuleBackend fallback.
    * test_connection(req) — returns TestConnectionResult (never raises):
        - SSRF validation first (short-circuit to error_code="ssrf_blocked").
        - 401 / connect-refused / DNS / timeout classified.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from ...auth import KeyringGateway
from .errors import SsrfBlockedError
from .fallback import AuditSink, FallbackDecorator
from .llm_backend import LlmBackend, _KEYRING_SERVICE
from .models import (
    ClassifierConfig,
    ClassifyRequest,
    ProviderPreset,
    TestConnectionRequest,
    TestConnectionResult,
    Verdict,
)
from .prompt_store import PromptStore
from .provider_presets import ProviderPresets
from .rule_backend import RuleBackend


class ClassifierService:
    """Facade — holds config + backends + audit sink; never raises from classify()."""

    def __init__(
        self,
        config: ClassifierConfig,
        *,
        prompt_store_path: Path,
        keyring: KeyringGateway | None = None,
        audit_sink: AuditSink | None = None,
        presets: ProviderPresets | None = None,
    ) -> None:
        self._config = config
        self._keyring = keyring or KeyringGateway()
        self._prompt_store = PromptStore(path=Path(prompt_store_path))
        self._audit_sink = audit_sink
        self._presets = presets or ProviderPresets()
        self._rule = RuleBackend()

    # ------------------------------------------------------------------ helpers
    def _resolve_preset(self, provider: str, base_url: str, model_name: str) -> ProviderPreset:
        """Build a ProviderPreset using the requested provider + effective base_url."""
        if provider == "custom":
            return ProviderPreset(
                name="custom",
                base_url=base_url,
                default_model=model_name,
                api_key_user_slot="custom",
            )
        base = self._presets.resolve(provider)
        # Keep the preset's canonical base_url unless the caller explicitly overrides.
        effective_base = base_url or base.base_url
        effective_model = model_name or base.default_model
        return ProviderPreset(
            name=base.name,
            base_url=effective_base,
            default_model=effective_model,
            api_key_user_slot=base.api_key_user_slot,
        )

    def _audit(self, event: dict[str, Any]) -> None:
        if self._audit_sink is not None:
            try:
                self._audit_sink(event)
            except Exception:  # pragma: no cover
                pass

    # ------------------------------------------------------------------ classify
    async def classify(self, req: ClassifyRequest) -> Verdict:
        """Return a Verdict; NEVER raise (IAPI-010 永不抛 contract)."""
        # Off-switch — skip LLM entirely.
        if not self._config.enabled:
            return self._rule.decide(req)

        # Resolve prompt (fallback to default on any corruption).
        try:
            prompt_body = self._prompt_store.get().current
        except Exception:
            prompt_body = "You are Harness's ticket classifier. Return strict JSON."

        # Build LlmBackend per call (each request may use different preset).
        try:
            preset = self._resolve_preset(
                self._config.provider,
                self._config.base_url,
                self._config.model_name,
            )
        except Exception as exc:
            self._audit(
                {
                    "event": "classifier_fallback",
                    "cause": "preset_resolve_error",
                    "exc_class": type(exc).__name__,
                    "summary": str(exc),
                }
            )
            return self._rule.decide(req)

        primary = LlmBackend(preset=preset, keyring=self._keyring)
        decorator = FallbackDecorator(
            primary=primary,
            fallback=self._rule,
            audit_sink=self._audit_sink,
        )

        try:
            return await decorator.invoke(req, prompt_body)
        except Exception as exc:  # last-resort — classify must never raise
            self._audit(
                {
                    "event": "classifier_fallback",
                    "cause": "unexpected_error",
                    "exc_class": type(exc).__name__,
                    "summary": str(exc),
                }
            )
            return self._rule.decide(req)

    # ------------------------------------------------------------------ test_connection
    async def test_connection(self, req: TestConnectionRequest) -> TestConnectionResult:
        """Probe the configured endpoint; return TestConnectionResult (never raises)."""
        # Step 1 — SSRF short-circuit.
        try:
            self._presets.validate_base_url(req.base_url)
        except SsrfBlockedError as exc:
            return TestConnectionResult(
                ok=False,
                error_code="ssrf_blocked",
                message=str(exc),
            )

        # Step 2 — keyring lookup (best-effort; some providers allow missing key).
        api_key: str | None = None
        try:
            api_key = self._keyring.get_secret(_KEYRING_SERVICE, req.provider)
        except Exception:
            api_key = None

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Probe body: minimal chat completion.
        url = req.base_url.rstrip("/") + "/chat/completions"
        body = {
            "model": req.model_name,
            "messages": [{"role": "user", "content": "ping"}],
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            return TestConnectionResult(
                ok=False,
                error_code="timeout",
                message=str(exc),
            )
        except httpx.ConnectError as exc:
            msg = str(exc).lower()
            if "getaddrinfo" in msg or "name or service not known" in msg or "dns" in msg:
                return TestConnectionResult(
                    ok=False,
                    error_code="dns_failure",
                    message=str(exc),
                )
            return TestConnectionResult(
                ok=False,
                error_code="connection_refused",
                message=str(exc),
            )
        except httpx.HTTPError as exc:
            return TestConnectionResult(
                ok=False,
                error_code="connection_refused",
                message=str(exc),
            )

        latency = int((time.monotonic() - start) * 1000)

        if resp.status_code == 401:
            return TestConnectionResult(
                ok=False,
                error_code="401",
                message="unauthorized",
                latency_ms=latency,
            )
        if resp.status_code >= 400:
            return TestConnectionResult(
                ok=False,
                error_code="connection_refused",
                message=f"HTTP {resp.status_code}",
                latency_ms=latency,
            )

        return TestConnectionResult(
            ok=True,
            latency_ms=latency,
            message="OK",
        )


__all__ = ["ClassifierService"]
