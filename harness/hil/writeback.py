"""F18 Wave 4 · HilWriteback (Design §Interface Contract HilWriteback row).

Wave 4 changes:
  - payload is **TUI key-sequence bytes** (no longer JSON)
  - bytes are emitted via ``POST /api/pty/write`` (IAPI-021) — caller injects a
    ``pty_write_client`` adapter so we don't take a hard FastAPI dep here
  - HilEventBus.publish_answered fires on success
  - PtyClosedError → preserve answer in ``pending_answers`` + ticket → failed

Wave 4.1 (2026-04-27) — unified Esc-text protocol becomes the **default**:
  - HilWriteback.write_answer constructs a ``merged_text`` from
    ``answer.selected_labels`` + ``answer.freeform_text`` and emits
    ``TuiKeyEncoder.encode_unified_answer(merged_text)`` — a single
    Esc + bracketed-paste(merged_text) + CR keystroke.
  - HIL audit closes via PreToolUse + UserPromptSubmit + Stop hook chain
    (PostToolUse does NOT fire under this path; by design — see ASM-009/010).
  - Baseline ``<N>\\r`` + bracketed-paste-freeform path remains available
    when callers pass ``prefer_baseline=True`` (compatibility regression).

Per Design §Interface Contract HilWriteback.write_answer postcondition:
  (1) default path: merged_text → encode_unified_answer; baseline path:
      HilQuestion.kind drives TuiKeyEncoder.encode_radio/checkbox/freeform;
  (2) base64 encode + POST /api/pty/write;
  (3) success → publish_answered + ticket transition hil_waiting → classifying;
  (4) PtyClosedError → pending_answers[ticket_id] += answer + ticket → failed.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Protocol

from harness.adapter.errors import EscapeError
from harness.domain.ticket import HilAnswer, HilQuestion
from harness.hil.tui_keys import TuiKeyEncoder
from harness.pty.errors import PtyClosedError

_log = logging.getLogger(__name__)


class _PtyWriteClient(Protocol):
    def post(self, ticket_id: str, payload_b64: str) -> int: ...


class _EventBus(Protocol):
    def publish_answered(self, *args: Any, **kwargs: Any) -> Any: ...


class _TicketRepo(Protocol):
    def transition(self, ticket_id: str, new_state: str) -> Any: ...


class HilWriteback:
    """Translate a HilAnswer → TUI key bytes → IAPI-021 POST."""

    def __init__(
        self,
        *,
        pty_write_client: _PtyWriteClient,
        event_bus: _EventBus | None = None,
        ticket_repo: _TicketRepo | None = None,
        encoder: TuiKeyEncoder | None = None,
        prefer_baseline: bool = False,
    ) -> None:
        self._client = pty_write_client
        self._bus = event_bus
        self._repo = ticket_repo
        self._encoder = encoder or TuiKeyEncoder()
        # Wave 4.1: default path is unified Esc-text. Set ``prefer_baseline=True``
        # to fall back to the legacy ``<N>\r`` + bracketed-paste-freeform encoder
        # (kept for backward compatibility — see Wave-4 PoC evidence).
        self._prefer_baseline = prefer_baseline
        # FR-011 AC-4: failed write_answer must preserve the answer here.
        self.pending_answers: dict[str, list[HilAnswer]] = {}

    # ------------------------------------------------------------------
    def write_answer(
        self,
        *,
        ticket_id: str,
        question: HilQuestion,
        answer: HilAnswer,
    ) -> None:
        # 1. Encode using the active path (default = unified Esc-text, Wave 4.1).
        try:
            if self._prefer_baseline:
                payload_bytes = self._encode_baseline(question, answer)
                merged_text: str | None = None
            else:
                merged_text = self._merge_text(question, answer)
                payload_bytes = self._encoder.encode_unified_answer(merged_text)
        except EscapeError:
            # Forbidden control bytes → propagate to caller; do not transition.
            raise

        # 2. base64 encode + POST /api/pty/write (IAPI-021).
        payload_b64 = base64.b64encode(payload_bytes).decode("ascii")
        try:
            self._client.post(ticket_id, payload_b64)
        except PtyClosedError:
            # FR-011 AC-4: preserve answer + ticket → failed; do NOT publish_answered.
            self.pending_answers.setdefault(ticket_id, []).append(answer)
            if self._repo is not None:
                self._repo.transition(ticket_id, "failed")
            _log.warning(
                "HilWriteback: PTY closed before answer could be written; "
                "answer preserved for ticket=%s",
                ticket_id,
            )
            raise

        # 3. Success → publish_answered + ticket → classifying.
        if self._bus is not None:
            if not self._prefer_baseline and merged_text is not None and hasattr(
                self._bus, "publish_answered_via_prompt"
            ):
                # Wave 4.1 default — audit via merged-text channel.
                try:
                    self._bus.publish_answered_via_prompt(
                        ticket_id=ticket_id, run_id="", merged_text=merged_text
                    )
                except TypeError:
                    # Alternate signature without run_id.
                    self._bus.publish_answered_via_prompt(  # type: ignore[call-arg]
                        ticket_id=ticket_id, merged_text=merged_text
                    )
            else:
                try:
                    self._bus.publish_answered(ticket_id=ticket_id, answer=answer)
                except TypeError:
                    # Tolerate alternate signatures; older callers may use run_id keyword.
                    self._bus.publish_answered(
                        ticket_id=ticket_id, run_id="", answer=answer
                    )
        if self._repo is not None:
            self._repo.transition(ticket_id, "classifying")

    # ------------------------------------------------------------------
    @staticmethod
    def _merge_text(question: HilQuestion, answer: HilAnswer) -> str:
        """Wave 4.1 — flatten a HilAnswer into a single merged-text payload.

        Rules (default unified Esc-text protocol):
          - freeform_text non-empty → use as-is (overrides label merge)
          - selected_labels non-empty → ", ".join(labels) (multi-select form)
          - both empty → ""  (TUI accepts an empty paste + CR which submits
            whatever the cursor is currently on — TUI default behaviour)
        """
        if answer.freeform_text:
            return answer.freeform_text
        if answer.selected_labels:
            return ", ".join(answer.selected_labels)
        return ""

    # ------------------------------------------------------------------
    def _encode_baseline(self, question: HilQuestion, answer: HilAnswer) -> bytes:
        """Legacy path (Wave 4 prior to 4.1) kept for compatibility regression.

        Pick TuiKeyEncoder method based on question.kind + answer payload.
        Used when ``prefer_baseline=True``.
        """
        if answer.freeform_text is not None:
            # Freeform text path (single-shot bracketed paste).
            return self._encoder.encode_freeform(answer.freeform_text)

        if question.kind == "multi_select":
            indices = self._labels_to_indices(question, answer.selected_labels)
            return self._encoder.encode_checkbox(indices)

        # single_select / fall-through: pick the first selected label index (1-based).
        if answer.selected_labels:
            indices = self._labels_to_indices(question, answer.selected_labels)
            if indices:
                return self._encoder.encode_radio(indices[0])
        # No selection at all → bare CR confirms whatever the TUI default is.
        return b"\r"

    # Backwards-compat alias used by older tests / call sites.
    def _encode(self, question: HilQuestion, answer: HilAnswer) -> bytes:  # pragma: no cover
        return self._encode_baseline(question, answer)

    @staticmethod
    def _labels_to_indices(question: HilQuestion, labels: list[str]) -> list[int]:
        order = {opt.label: i + 1 for i, opt in enumerate(question.options)}
        indices: list[int] = []
        for label in labels:
            if label in order:
                indices.append(order[label])
        return indices


__all__ = ["HilWriteback"]
