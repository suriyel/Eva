"""F19 · Bk-Dispatch — ModelResolver 4-layer priority tests.

Covers Test Inventory: T01, T02, T03, T04, T05.
SRS: FR-019, FR-020.
UML: classDiagram ModelResolver..>ModelRulesStore; seq msg#1 F20→ModelResolver (via F20→ClassifierService path reuses same resolve pattern).

Layer marker:
  # [unit] — pure function; ModelResolver holds in-memory rule list (no I/O).
  # Real-fs integration for ModelRulesStore persistence is in
  # tests/integration/test_f19_real_fs.py (T35).

Real-test invariants (Rule 5a) satisfied by integration file; this file is
unit-level because ModelResolver is pure (given an injected rule list,
no I/O is performed).
"""

from __future__ import annotations

# F19 imports deferred per-test (TDD Red — modules absent).


# ---------------------------------------------------------------------------
# T01 — FUNC/happy — Traces To: FR-019 AC-1 · §IC ModelResolver.resolve
# Kills: per-skill rule not firing (skill field match skipped).
# ---------------------------------------------------------------------------
def test_t01_resolve_per_skill_rule_returns_opus_with_per_skill_provenance():
    from harness.dispatch import ModelResolver
    from harness.dispatch.model.models import ModelOverrideContext, ModelRule

    rules = [ModelRule(skill="requirements", tool="claude", model="opus")]
    resolver = ModelResolver(rules=rules)
    ctx = ModelOverrideContext(
        ticket_override=None,
        skill_hint="requirements",
        run_default=None,
        tool="claude",
    )

    result = resolver.resolve(ctx)

    # Strong assertions — wrong-impl challenge:
    #  - returning hard-coded "opus" would pass model but fail provenance.
    #  - provenance "run-default" (layer confusion) fails.
    assert result.model == "opus"
    assert result.provenance == "per-skill"


# ---------------------------------------------------------------------------
# T02 — FUNC/happy — Traces To: FR-020 AC-3 · §DA seq msg#1 · §IC resolve
# Kills: per-ticket vs per-skill priority inversion.
# ---------------------------------------------------------------------------
def test_t02_per_ticket_wins_over_per_skill():
    from harness.dispatch import ModelResolver
    from harness.dispatch.model.models import ModelOverrideContext, ModelRule

    # Per-skill says "sonnet" for requirements skill; per-ticket says "opus".
    rules = [ModelRule(skill="requirements", tool="claude", model="sonnet")]
    resolver = ModelResolver(rules=rules)
    ctx = ModelOverrideContext(
        ticket_override="opus",
        skill_hint="requirements",
        run_default=None,
        tool="claude",
    )

    result = resolver.resolve(ctx)

    # If implementation mis-orders layers, result.model would be "sonnet".
    assert result.model == "opus", "per-ticket must win over per-skill"
    assert result.provenance == "per-ticket"


# ---------------------------------------------------------------------------
# T03 — FUNC/happy — Traces To: FR-020 AC-1 · §IC resolve
# Kills: run-default layer skipped.
# ---------------------------------------------------------------------------
def test_t03_run_default_only_returns_haiku_with_run_default_provenance():
    from harness.dispatch import ModelResolver
    from harness.dispatch.model.models import ModelOverrideContext

    resolver = ModelResolver(rules=[])
    ctx = ModelOverrideContext(
        ticket_override=None,
        skill_hint=None,
        run_default="haiku",
        tool="claude",
    )

    result = resolver.resolve(ctx)

    assert result.model == "haiku"
    assert result.provenance == "run-default"


# ---------------------------------------------------------------------------
# T04 — BNDRY/edge — Traces To: FR-020 AC-2 · §BC all-None
# Kills: returning empty string "" (which would surface as --model "" at F18);
#        missing cli-default branch (falling through to error).
# ---------------------------------------------------------------------------
def test_t04_all_layers_none_returns_cli_default_with_model_none():
    from harness.dispatch import ModelResolver
    from harness.dispatch.model.models import ModelOverrideContext

    resolver = ModelResolver(rules=[])
    ctx = ModelOverrideContext(
        ticket_override=None,
        skill_hint=None,
        run_default=None,
        tool="claude",
    )

    result = resolver.resolve(ctx)

    # STRICT: must be None (absence), not empty string.
    assert result.model is None, "four-layer-empty must yield model=None, not empty string"
    assert result.provenance == "cli-default"


# ---------------------------------------------------------------------------
# T05 — BNDRY/edge — Traces To: §BC ticket_override=""
# Kills: empty-string ticket_override accepted as valid (would emit --model "").
# ---------------------------------------------------------------------------
def test_t05_empty_string_ticket_override_skips_to_per_skill_layer():
    from harness.dispatch import ModelResolver
    from harness.dispatch.model.models import ModelOverrideContext, ModelRule

    rules = [ModelRule(skill="requirements", tool="claude", model="opus")]
    resolver = ModelResolver(rules=rules)
    ctx = ModelOverrideContext(
        ticket_override="",  # empty string should be normalized to None
        skill_hint="requirements",
        run_default=None,
        tool="claude",
    )

    result = resolver.resolve(ctx)

    # Empty string must NOT bubble up as model.
    assert result.model == "opus"
    assert result.provenance == "per-skill"
