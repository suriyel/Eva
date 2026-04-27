"""Wave 5 NEW · in-process port of plugin v1.0.0 ``count_pending`` /
``validate_features``.

Behaviour parity with ``scripts/count_pending.py`` + ``scripts/validate_features.py``
on the same fixture set (cross-impl tests T84 / T86 lock the schema).

Public API:
    * :func:`count_pending` — return shape:
        ``{"total", "passing", "failing", "current", "deprecated", "legacy_sub_status"}``
        (matches plugin v1.0.0 stdout JSON)
    * :func:`validate_features` — return :class:`ValidationReport` shape;
        only used internally by ValidatorRunner short-circuit.

API-W5-07 / IAPI-022 / ASM-011 — plugin upgrade is treated as an SRS revision
event; cross-impl fixtures (T71 / T86) lock the contract.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from harness.subprocess.validator.schemas import ValidationIssue, ValidationReport


def count_pending(path: Path | str) -> dict[str, Any]:
    """Return plugin v1.0.0 count_pending dict for *path*.

    Raises:
        OSError / FileNotFoundError when *path* cannot be opened.
        ValueError when JSON is malformed or ``features`` key is missing/wrong type.
    """
    p = Path(path)
    # Surface FileNotFoundError as OSError subclass — matches plugin behaviour.
    with open(p, "r", encoding="utf-8") as fh:
        raw = fh.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Plugin's count() raises ValueError via JSONDecodeError; mirror it.
        raise ValueError(f"invalid JSON in {p}: {exc}") from exc

    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError('"features" key missing or not a list')

    result: dict[str, Any] = {
        "total": 0,
        "passing": 0,
        "failing": 0,
        "current": data.get("current"),
        "deprecated": 0,
        "legacy_sub_status": 0,
    }

    for feat in features:
        if not isinstance(feat, dict):
            continue
        if feat.get("deprecated"):
            result["deprecated"] += 1
            continue
        result["total"] += 1
        if feat.get("status") == "passing":
            result["passing"] += 1
        else:
            result["failing"] += 1
        if "sub_status" in feat:
            result["legacy_sub_status"] += 1
    return result


def validate_features(path: Path | str) -> ValidationReport:
    """Lightweight shape check of feature-list.json.

    Returns :class:`ValidationReport` mirroring ``ValidatorRunner.run`` output;
    only schema-level structural failures are reported as issues. The plugin's
    ``validate_features.py`` performs a much richer audit; we cover the subset
    actually consumed by the orchestrator (presence of ``features`` array).
    """
    p = Path(path)
    started = time.perf_counter()
    issues: list[ValidationIssue] = []
    ok = True
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        ok = False
        issues.append(ValidationIssue(rule_id="file_not_found", message=str(exc)))
        return _make_report(ok, issues, started)
    except json.JSONDecodeError as exc:
        ok = False
        issues.append(ValidationIssue(rule_id="invalid_json", message=str(exc)))
        return _make_report(ok, issues, started)

    features = data.get("features")
    if not isinstance(features, list):
        ok = False
        issues.append(
            ValidationIssue(
                rule_id="features_missing",
                message='"features" key missing or not a list',
            )
        )
    return _make_report(ok, issues, started)


def _make_report(ok: bool, issues: list[ValidationIssue], started: float) -> ValidationReport:
    duration_ms = int((time.perf_counter() - started) * 1000)
    return ValidationReport(
        ok=ok,
        issues=issues,
        script_exit_code=0 if ok else 2,
        duration_ms=duration_ms,
        http_status_hint=200 if ok else 400,
    )


__all__ = ["count_pending", "validate_features"]
