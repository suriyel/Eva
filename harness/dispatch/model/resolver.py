"""F19 · ModelResolver — 4-layer priority chain.

Feature design §IC ModelResolver.resolve:
    Priority order: per-ticket > per-skill > run-default > cli-default.
    Empty string in any layer is normalised to None (§BC rows).
    When all layers empty → ``ResolveResult(model=None, provenance="cli-default")``
    so that F18 ClaudeCodeAdapter omits the ``--model`` argv fragment.
"""

from __future__ import annotations

from .models import ModelOverrideContext, ModelRule, ResolveResult


class ModelResolver:
    """4-layer model-override resolver.

    ``rules`` is an in-memory snapshot of ``ModelRulesStore.load()`` results;
    the resolver is a pure function over (ctx, rules) — no I/O in ``resolve``.
    """

    def __init__(self, rules: list[ModelRule] | None = None) -> None:
        self._rules: list[ModelRule] = list(rules or [])

    @property
    def rules(self) -> list[ModelRule]:
        return list(self._rules)

    def resolve(self, ctx: ModelOverrideContext) -> ResolveResult:
        """Return the resolved model + provenance per the 4-layer priority."""
        # Layer 1 — per-ticket (explicit override wins).
        if ctx.ticket_override:
            return ResolveResult(model=ctx.ticket_override, provenance="per-ticket")

        # Layer 2 — per-skill rule for this (skill, tool) pair.
        if ctx.skill_hint:
            for rule in self._rules:
                if rule.skill == ctx.skill_hint and rule.tool == ctx.tool:
                    return ResolveResult(model=rule.model, provenance="per-skill")

        # Layer 3 — run-level default.
        if ctx.run_default:
            return ResolveResult(model=ctx.run_default, provenance="run-default")

        # Layer 4 — cli-default (model=None; F18 omits --model).
        return ResolveResult(model=None, provenance="cli-default")


__all__ = ["ModelResolver"]
