"""OI Compiler: shared types and WorldSummary for the OI compilation pipeline.

This module provides:
1. ClaimIntent — symbolic IR (retained for legacy compatibility)
2. WorldSummary — canonical anchors (percentiles, bounds per variable)
3. CompiledUnit / CompilerOutput — compiler result types

The actual compilation (ClaimCard → AtomicSpecs) lives in oi_extraction.py
via grammar-direct LLM extraction.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator

from sreg.models.open_investigation import (
    AtomicSpec,
    ClaimCard,
)
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WorldSummary — canonical anchors for each variable
# ---------------------------------------------------------------------------


class VariableAnchors(BaseModel):
    """Canonical percentile anchors for one variable."""

    name: str
    p25: float
    p50: float
    p75: float
    p90: float
    p10: float
    mean: float
    std: float
    is_observable: bool = True


class WorldSummary(BaseModel):
    """Pre-computed summary statistics for all variables in a world.

    Used by the compiler to translate vague phrases ("high", "above median")
    into concrete intervention/condition values. Computed ONCE per world,
    shared between salience map generator and compiler.
    """

    world_id: str
    target: str
    variables: dict[str, VariableAnchors]
    observable_names: list[str]

    def anchors(self, var: str) -> VariableAnchors:
        """Get anchors for a variable, raising ValueError if missing."""
        if var not in self.variables:
            raise ValueError(f"Variable '{var}' not in world summary")
        return self.variables[var]

    def hi(self, var: str) -> float:
        """Canonical 'high' value = p75."""
        return self.anchors(var).p75

    def lo(self, var: str) -> float:
        """Canonical 'low' value = p25."""
        return self.anchors(var).p25

    def mid(self, var: str) -> float:
        """Canonical 'median' = p50."""
        return self.anchors(var).p50


def build_world_summary(
    world: SCMWorld, target: str, n_mc: int = 50_000, seed: int = 42
) -> WorldSummary:
    """Build a WorldSummary from an SCMWorld."""
    df = world.sample(n=n_mc, seed=seed)
    obs = set(world.observable_variables)
    variables = {}

    for var in world.variables:
        if var not in df.columns:
            continue
        col = df[var].values
        variables[var] = VariableAnchors(
            name=var,
            p10=float(np.percentile(col, 10)),
            p25=float(np.percentile(col, 25)),
            p50=float(np.percentile(col, 50)),
            p75=float(np.percentile(col, 75)),
            p90=float(np.percentile(col, 90)),
            mean=float(np.mean(col)),
            std=float(max(np.std(col), 1e-6)),
            is_observable=var in obs,
        )

    return WorldSummary(
        world_id=world.id,
        target=target,
        variables=variables,
        observable_names=sorted(obs),
    )


# ---------------------------------------------------------------------------
# ClaimIntent — symbolic intermediate representation
# ---------------------------------------------------------------------------


class PatternClass(StrEnum):
    """Recognized claim patterns the compiler can translate."""

    CAUSAL_EFFECT = "causal_effect"
    MEDIATION = "mediation"
    HETEROGENEITY = "heterogeneity"
    TAIL_RISK = "tail_risk"
    VARIANCE_EFFECT = "variance_effect"
    OBSERVATIONAL_ASSOCIATION = "observational_association"
    EFFECT_RANKING = "effect_ranking"
    CONFOUNDING = "confounding"


class Direction(StrEnum):
    """Asserted direction of an effect."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEAR_ZERO = "near_zero"


class ClaimIntent(BaseModel):
    """Symbolic intent extracted from a ClaimCard by the LLM.

    This is the IR between natural language and formal spec. The LLM fills
    in pattern_class, variable roles, and direction. The code fills in
    concrete values via WorldSummary.
    """

    claim_id: str = Field(min_length=1)
    pattern: PatternClass
    treatment: str = Field(min_length=1, description="Main cause variable")
    outcome: str = Field(min_length=1, description="Main outcome variable")
    direction: Direction = Direction.POSITIVE

    # Optional role-specific fields
    mediator: str | None = Field(default=None, description="For mediation: X→M→Y")
    modifier: str | None = Field(default=None, description="For heterogeneity: effect varies by Z")
    confounder: str | None = Field(
        default=None, description="For confounding: C confounds X→Y"
    )
    ranking_vars: list[str] = Field(
        default_factory=list, description="For ranking: which vars to compare"
    )
    conditioning_set: list[str] = Field(
        default_factory=list, description="For observational: control variables"
    )

    # Scope
    scope: Literal["global", "conditional"] = "global"
    evidence_type: Literal["interventional", "observational"] = "interventional"

    @model_validator(mode="after")
    def validate_roles(self) -> ClaimIntent:
        """Check pattern-specific role requirements."""
        if self.pattern == PatternClass.MEDIATION and not self.mediator:
            raise ValueError("Mediation pattern requires mediator variable")
        if self.pattern == PatternClass.HETEROGENEITY and not self.modifier:
            raise ValueError("Heterogeneity pattern requires modifier variable")
        if self.pattern == PatternClass.EFFECT_RANKING and len(self.ranking_vars) < 2:
            raise ValueError("Effect ranking requires at least 2 variables to compare")
        if self.pattern == PatternClass.OBSERVATIONAL_ASSOCIATION:
            if self.evidence_type != "observational":
                object.__setattr__(self, "evidence_type", "observational")
        if self.pattern == PatternClass.CONFOUNDING and not self.confounder:
            raise ValueError("Confounding pattern requires confounder variable")
        return self


# ---------------------------------------------------------------------------
# CompilerOutput — result of compiling one ClaimCard
# ---------------------------------------------------------------------------


class CompiledUnit(BaseModel):
    """One verifiable unit extracted from a claim.

    Each unit has its own intent (the LLM-extracted symbolic IR) and specs
    (the deterministic lowering to AtomicSpecs). A compound claim produces
    N CompiledUnits; a simple claim produces 1.

    Backends:
    - "claim_intent": v1 — LLM extracts ClaimIntent IR, deterministic lowering
    - "grammar_direct": v2 — LLM produces AtomicSpecs directly from grammar
    """

    unit_id: str = Field(min_length=1)
    intent: ClaimIntent | None = None
    specs: list[AtomicSpec] = Field(default_factory=list)
    backend: Literal["claim_intent", "grammar_direct"] = "claim_intent"


class CompilerOutput(BaseModel):
    """Result of compiling one ClaimCard.

    1:1 with ClaimCard. May contain 0..N CompiledUnits. Multi-unit claims
    (A22) produce N units from compound assertions. Warranty, trace, and
    efficiency are keyed by claim_id (unchanged).

    `deliberate_abstention` is orthogonal to `status`: a status="abstention"
    can come from (a) the LLM explicitly returning [] (deliberate=True,
    model recognized the claim as non-verifiable) or (b) a fallback after
    a crash / parse failure / empty output (deliberate=False). Downstream
    honesty metrics must distinguish these two.
    """

    claim_id: str
    status: Literal["compiled", "partial", "abstention"] = "compiled"
    units: list[CompiledUnit] = Field(default_factory=list)
    abstention_reason: str | None = None
    deliberate_abstention: bool = False
    uncompiled_fragments: list[str] = Field(
        default_factory=list, description="Fragments that could not be compiled"
    )

    @property
    def compiled(self) -> bool:
        return self.status in ("compiled", "partial") and len(self.units) > 0

    @property
    def abstained(self) -> bool:
        return self.status == "abstention"

    @property
    def abstained_deliberately(self) -> bool:
        return self.status == "abstention" and self.deliberate_abstention

    @property
    def abstained_by_fallback(self) -> bool:
        return self.status == "abstention" and not self.deliberate_abstention

    @property
    def specs(self) -> list[AtomicSpec]:
        """Flat list of all specs across units (backward compat)."""
        return [spec for u in self.units for spec in u.specs]

    @property
    def intents(self) -> list[ClaimIntent]:
        """All intents across units."""
        return [u.intent for u in self.units]

    @property
    def intent(self) -> ClaimIntent | None:
        """Single intent for backward compat. Returns first or None."""
        return self.units[0].intent if self.units else None



__all__ = [
    "ClaimIntent",
    "CompiledUnit",
    "CompilerOutput",
    "Direction",
    "PatternClass",
    "VariableAnchors",
    "WorldSummary",
    "build_world_summary",
]
