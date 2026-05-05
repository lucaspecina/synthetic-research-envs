"""Contratos Pydantic v1.5.

Schemas tipados para todos los artefactos del pipeline. Cada handoff
entre piezas (Designer → Investigator → Evaluator) requiere artefacto
tipado, no prosa.

**Frontera público/oculto** (invariante operativa):

- **PÚBLICO** (lo ve el Investigator): `ResearchCase`, `Dataset`, `ToolSpec`.
  Opcionalmente `PaperNarrativeCapsule` (saneada, anti-leak) puede
  incluirse en `ResearchCase.context`.
- **OCULTO** (NO se filtra al Investigator): `WorldSpec`, `IntendedPhenomenon`,
  `ValidatorVote`, `ValidatedPhenomenon`, `PhenomenaManifest`,
  `QuestionsBundle`, `GoldQuestion`, `Rubric`, `AnswerKey`,
  `EvidenceArtifact`, `ValidationReport`, `PaperInsights` (resto).

Si alguna vez agregás un campo de la lista oculta a `ResearchCase`,
parás y revisás. Es un bug grave (filtra la respuesta al solver).
"""

from sreg.v1_5.contracts.case import Dataset, ResearchCase, ToolSpec
from sreg.v1_5.contracts.investigation import (
    Claim,
    HypothesisEntry,
    InvestigationLog,
    InvestigatorAction,
)
from sreg.v1_5.contracts.paper import PaperInsights, PaperNarrativeCapsule
from sreg.v1_5.contracts.phenomena import (
    EvidenceArtifact,
    PhenomenaManifest,
    Phenomenon,
)
from sreg.v1_5.contracts.questions import (
    ALLOWED_CRITERION_WEIGHTS,
    ALLOWED_GQ_WEIGHTS,
    AnswerKey,
    AnswerKeyAnchor,
    Criterion,
    GoldQuestion,
    QuestionsBundle,
    Rubric,
)
from sreg.v1_5.contracts.validated_phenomenon import (
    ValidatedPhenomenon,
    ValidatorVote,
)
from sreg.v1_5.contracts.validation import (
    AdversarialAttempt,
    ReiterationTarget,
    ValidationArtifact,
    ValidationIssue,
    ValidationReport,
)
from sreg.v1_5.contracts.world import (
    IntendedPhenomenon,
    RelationshipSpec,
    VariableSpec,
    WorldMetadata,
    WorldSpec,
)

__all__ = [
    # paper
    "PaperInsights",
    "PaperNarrativeCapsule",
    # world
    "VariableSpec",
    "RelationshipSpec",
    "WorldMetadata",
    "IntendedPhenomenon",
    "WorldSpec",
    # phenomena
    "EvidenceArtifact",
    "Phenomenon",
    "PhenomenaManifest",
    # questions
    "ALLOWED_GQ_WEIGHTS",
    "ALLOWED_CRITERION_WEIGHTS",
    "AnswerKey",
    "AnswerKeyAnchor",
    "Criterion",
    "Rubric",
    "GoldQuestion",
    "QuestionsBundle",
    # validated_phenomenon (Architect ↔ Validators flow)
    "ValidatorVote",
    "ValidatedPhenomenon",
    # case
    "Dataset",
    "ToolSpec",
    "ResearchCase",
    # investigation
    "Claim",
    "HypothesisEntry",
    "InvestigatorAction",
    "InvestigationLog",
    # validation
    "ValidationArtifact",
    "ReiterationTarget",
    "ValidationIssue",
    "AdversarialAttempt",
    "ValidationReport",
]
