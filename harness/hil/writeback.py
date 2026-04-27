"""F18 Wave 4 · HilWriteback (Design §Interface Contract HilWriteback row).

Wave 4 changes:
  - payload is **TUI key-sequence bytes** (no longer JSON)
  - bytes are emitted via ``POST /api/pty/write`` (IAPI-021) — caller injects a
    ``pty_write_client`` adapter so we don't take a hard FastAPI dep here
  - HilEventBus.publish_answered fires on success
  - PtyClosedError → preserve answer in ``pending_answers`` + ticket → failed

Per Design §Interface Contract HilWriteback.write_answer postcondition:
  (1) HilQuestion.kind drives TuiKeyEncoder.encode_*;
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
    ) -> None:
        self._client = pty_write_client
        self._bus = event_bus
        self._repo = ticket_repo
        self._encoder = encoder or TuiKeyEncoder()
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
        # 1. Encode using HilQuestion.kind to pick the right TuiKeyEncoder method.
        try:
            payload_bytes = self._encode(question, answer)
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
    def _encode(self, question: HilQuestion, answer: HilAnswer) -> bytes:
        """Pick TuiKeyEncoder method based on question.kind + answer payload."""
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

    @staticmethod
    def _labels_to_indices(question: HilQuestion, labels: list[str]) -> list[int]:
        order = {opt.label: i + 1 for i, opt in enumerate(question.options)}
        indices: list[int] = []
        for label in labels:
            if label in order:
                indices.append(order[label])
        return indices


__all__ = ["HilWriteback"]
