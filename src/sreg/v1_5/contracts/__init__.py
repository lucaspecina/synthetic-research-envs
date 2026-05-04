"""Contratos Pydantic v1.5.

Schemas tipados para todos los artefactos del pipeline. Cada handoff
entre piezas (Designer → Investigator → Evaluator) requiere artefacto
tipado, no prosa.

**Frontera público/oculto** (invariante operativa):

- **PÚBLICO** (lo ve el Investigator): `ResearchCase`, `Dataset`, `ToolSpec`.
- **OCULTO** (NO se filtra al Investigator): `WorldSpec`, `QuestionsBundle`,
  `GoldQuestion`, `Rubric`, `AnswerKey`, `ValidationReport`.

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
from sreg.v1_5.contracts.paper import PaperInsights
from sreg.v1_5.contracts.phenomena import (
    ExecutableEvidence,
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
    VerifierQuery,
)
from sreg.v1_5.contracts.validation import (
    AdversarialAttempt,
    ValidationArtifact,
    ValidationIssue,
    ValidationReport,
)
from sreg.v1_5.contracts.world import (
    RelationshipSpec,
    VariableSpec,
    WorldMetadata,
    WorldSpec,
)

__all__ = [
    # paper
    "PaperInsights",
    # world
    "VariableSpec",
    "RelationshipSpec",
    "WorldMetadata",
    "WorldSpec",
    # phenomena
    "ExecutableEvidence",
    "Phenomenon",
    "PhenomenaManifest",
    # questions
    "ALLOWED_GQ_WEIGHTS",
    "ALLOWED_CRITERION_WEIGHTS",
    "VerifierQuery",
    "AnswerKey",
    "AnswerKeyAnchor",
    "Criterion",
    "Rubric",
    "GoldQuestion",
    "QuestionsBundle",
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
    "ValidationIssue",
    "AdversarialAttempt",
    "ValidationReport",
]
