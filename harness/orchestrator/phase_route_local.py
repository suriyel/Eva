"""Wave 5 NEW · in-process port of plugin v1.0.0 ``scripts/phase_route.py``.

API-W5-01 / FR-054 / IAPI-022. The :func:`route` function is the single
authoritative same-process replacement for ``subprocess.Popen(scripts/phase_route.py)``;
:class:`PhaseRouteInvoker` delegates to ``await asyncio.to_thread(route, workdir)``.

Behaviour parity with plugin v1.0.0 is enforced by cross-impl tests (T71).
The implementation re-uses the plugin's existing helpers (``count_pending`` /
``validate_features`` / ``phase_route``) by importing them — keeps the wire
contract bit-identical and lets plugin-side fixture changes auto-propagate.

Returned dict shape (canonical, FR-054 AC-2):
    {
        "ok": bool,
        "errors": list[str],
        "needs_migration": bool,
        "counts": dict | None,
        "next_skill": str | None,
        "feature_id": str | int | None,
        "starting_new": bool,
    }

In-proc invariants (FR-054 AC-1 / AC-3):
    * No ``subprocess.Popen`` / ``asyncio.create_subprocess_exec`` along the
      route() call stack (fast path; brownfield heuristic still uses
      ``git rev-list`` via subprocess BUT only when feature-list.json is
      absent — the canonical priority layers 1-3 never spawn).
    * Typical 100KB feature-list.json → ≤ 5ms; hard cap ≤ 50ms.
    * Corrupt feature-list.json → ``ok=False, errors=[...], next_skill=None``;
      does NOT raise.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Mount the plugin's scripts/ directory on sys.path so we can import its
# helpers without spawning a subprocess. The repo root is parents[2] from
# this file (harness/orchestrator/phase_route_local.py → repo root).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_SCRIPTS = _REPO_ROOT / "scripts"
if str(_PLUGIN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_SCRIPTS))

# Late import after sys.path tweak — keeps mypy calm; E402 is intentional.
import phase_route as _plugin_route_mod  # type: ignore[import-not-found]  # noqa: E402


# Canonical key set returned by route() — checked by T62.
_CANONICAL_KEYS: frozenset[str] = frozenset(
    {
        "ok",
        "errors",
        "needs_migration",
        "counts",
        "next_skill",
        "feature_id",
        "starting_new",
    }
)


def route(workdir: Path | str) -> dict[str, Any]:
    """Same-process phase-route decision for *workdir*.

    Returns a dict with the canonical 7-key shape — never raises (corrupt
    inputs surface as ``ok=False, errors=[...]``).
    """
    root = str(workdir) if workdir is not None else "."
    out = _plugin_route_mod.route(root)
    # Defensive: ensure the canonical key set even if plugin upgrade introduces
    # new fields (NFR-015 relaxed parsing — extra keys must NOT leak through).
    cleaned: dict[str, Any] = {k: out.get(k) for k in _CANONICAL_KEYS}
    # Preserve any None defaults the plugin chose (errors=[] etc.).
    if cleaned.get("errors") is None:
        cleaned["errors"] = []
    return cleaned


__all__ = ["route"]
