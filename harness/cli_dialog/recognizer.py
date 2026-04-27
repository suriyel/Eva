"""DialogRecognizer — bytes/text → DialogScreen | None."""

from __future__ import annotations

import re
from typing import Iterable, Protocol, runtime_checkable

from harness.cli_dialog.catalog import KNOWN_DIALOGS, Detector
from harness.cli_dialog.models import DialogScreen


# ANSI escape-sequence stripper. Same pattern used by run_real_hil_round_trip.
_ANSI_STRIP_RE = re.compile(
    rb"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[=>]|[\x07\x0e\x0f]"
)


def normalise(screen_bytes: bytes | str) -> str:
    """ANSI-strip + whitespace-collapse the raw PTY frame.

    claude TUI uses cursor-position control sequences to lay out output, so
    consecutive words concatenate without spaces in the stripped text. Token
    detectors operate on this collapsed form.
    """
    if isinstance(screen_bytes, str):
        raw = screen_bytes.encode("utf-8", errors="replace")
    else:
        raw = screen_bytes
    plain = _ANSI_STRIP_RE.sub(b"", raw).decode("utf-8", errors="replace")
    return re.sub(r"\s+", "", plain)


@runtime_checkable
class DialogRecognizer(Protocol):
    """Strategy interface for parsing PTY screen frames into DialogScreen."""

    def recognize(self, screen_bytes: bytes | str) -> DialogScreen | None: ...


class CatalogRecognizer:
    """Match against the static ``KNOWN_DIALOGS`` token table.

    Fast (no LLM call, no I/O) and deterministic. Returns ``None`` when the
    screen doesn't match any catalog entry — caller can chain into
    ``LLMRecognizer`` for unknown layouts.
    """

    def __init__(self, detectors: Iterable[Detector] = KNOWN_DIALOGS) -> None:
        self._detectors = tuple(detectors)

    def recognize(self, screen_bytes: bytes | str) -> DialogScreen | None:
        collapsed = normalise(screen_bytes)
        for detector in self._detectors:
            if all(tok in collapsed for tok in detector.required_tokens):
                return detector.parse(collapsed)
        return None


class LLMRecognizer:
    """LLM-backed recogniser for unknown dialog layouts (stub).

    Reserved for the next increment (FR-NEW · Boot dialog auto-handler with
    LLM fallback). When the catalog returns ``None``, this recogniser is
    expected to:

      1. Send the (ANSI-stripped, NOT collapsed) screen text to a small
         model via the Anthropic Messages API.
      2. Force structured output via tool_use with a JSON schema mirroring
         ``DialogScreen``.
      3. Return a ``DialogScreen(name=None, ...)`` so downstream policy
         knows the result wasn't catalog-vetted.

    Until the increment lands, calling ``recognize`` raises NotImplementedError.
    """

    def __init__(self, *, llm_client: object | None = None) -> None:
        self._llm_client = llm_client

    def recognize(self, screen_bytes: bytes | str) -> DialogScreen | None:
        raise NotImplementedError(
            "LLMRecognizer is reserved for the boot-dialog-handler increment; "
            "use CatalogRecognizer or wire ChainRecognizer with a real LLM "
            "client once the increment lands."
        )


class ChainRecognizer:
    """Try recognisers in order; first non-None wins."""

    def __init__(self, recognizers: Iterable[DialogRecognizer]) -> None:
        self._recognizers = tuple(recognizers)

    def recognize(self, screen_bytes: bytes | str) -> DialogScreen | None:
        for r in self._recognizers:
            try:
                screen = r.recognize(screen_bytes)
            except NotImplementedError:
                # LLM stub not wired yet — skip.
                continue
            if screen is not None:
                return screen
        return None


__all__ = [
    "DialogRecognizer",
    "CatalogRecognizer",
    "LLMRecognizer",
    "ChainRecognizer",
    "normalise",
]
