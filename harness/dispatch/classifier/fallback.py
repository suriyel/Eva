"""F19 · FallbackDecorator — LLM first, rule fallback on any failure.

Feature design §IC FallbackDecorator.invoke:
    * primary.invoke() success → pass-through.
    * Any exception from primary → audit log (event="classifier_fallback",
      cause=<exception class + summary>) + fallback.decide() returned.
"""

from __future__ import annotations

from typing import Any, Callable

from .errors import ClassifierHttpError, ClassifierProtocolError
from .llm_backend import LlmBackend
from .models import ClassifyRequest, Verdict
from .rule_backend import RuleBackend


AuditSink = Callable[[dict[str, Any]], None]


class FallbackDecorator:
    """Try LLM primary; on any failure → rule fallback + audit warning."""

    def __init__(
        self,
        primary: LlmBackend,
        fallback: RuleBackend,
        *,
        audit_sink: AuditSink | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._audit_sink = audit_sink

    def _audit(self, event: dict[str, Any]) -> None:
        if self._audit_sink is not None:
            try:
                self._audit_sink(event)
            except Exception:  # pragma: no cover — audit sink must never break
                pass

    async def invoke(self, req: ClassifyRequest, prompt: str) -> Verdict:
        try:
            return await self._primary.invoke(req, prompt)
        except ClassifierHttpError as exc:
            cause = getattr(exc, "cause", "") or "http_error"
            self._audit(
                {
                    "event": "classifier_fallback",
                    "cause": cause,
                    "exc_class": type(exc).__name__,
                    "summary": str(exc),
                }
            )
        except ClassifierProtocolError as exc:
            cause = getattr(exc, "cause", "") or "protocol_error"
            self._audit(
                {
                    "event": "classifier_fallback",
                    "cause": cause,
                    "exc_class": type(exc).__name__,
                    "summary": str(exc),
                }
            )
        except Exception as exc:  # catch-all — must not escape
            self._audit(
                {
                    "event": "classifier_fallback",
                    "cause": "unexpected_error",
                    "exc_class": type(exc).__name__,
                    "summary": str(exc),
                }
            )

        return self._fallback.decide(req)


__all__ = ["FallbackDecorator", "AuditSink"]
