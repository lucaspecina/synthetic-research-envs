"""Fixtures compartidas para los tests de contratos v1.5."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sreg.v1_5.contracts import (
    AnswerKey,
    AnswerKeyAnchor,
    Claim,
    Criterion,
    Dataset,
    ExecutableEvidence,
    GoldQuestion,
    HypothesisEntry,
    InvestigationLog,
    InvestigatorAction,
    PaperInsights,
    PhenomenaManifest,
    Phenomenon,
    QuestionsBundle,
    ResearchCase,
    Rubric,
    ToolSpec,
    ValidationReport,
    VariableSpec,
    VerifierQuery,
    WorldMetadata,
    WorldSpec,
)


@pytest.fixture
def anchor() -> AnswerKeyAnchor:
    return AnswerKeyAnchor(path="effect_direction", match="enum", value=["positive", "negative"])


@pytest.fixture
def criterion(anchor: AnswerKeyAnchor) -> Criterion:
    return Criterion(
        text="Reporta una estimación numérica del efecto.",
        weight=2,
        role="core",
        anchor=anchor,
        scoring_hint="Acreditar si el reporte da un número con incertidumbre.",
    )


@pytest.fixture
def rubric(criterion: Criterion) -> Rubric:
    return Rubric(criteria=[criterion])


@pytest.fixture
def gold_question(rubric: Rubric) -> GoldQuestion:
    return GoldQuestion(
        id="GQ1",
        text="¿Cuál es el efecto causal de X sobre Y?",
        weight=0.20,
        role="required",
        verifier_query=VerifierQuery(query_kind="ate", args={"treatment": "X", "outcome": "Y"}),
        answer_key=AnswerKey(
            summary="Efecto positivo, ~+0.3.",
            numeric={"effect_direction": "positive", "magnitude": 0.3},
        ),
        identification_hint="El reporte menciona el efecto de X sobre Y con un número.",
        rubric=rubric,
    )


@pytest.fixture
def questions_bundle(gold_question: GoldQuestion) -> QuestionsBundle:
    return QuestionsBundle(questions=[gold_question])


@pytest.fixture
def world_spec() -> WorldSpec:
    return WorldSpec(
        formalism="scm",
        variables=[
            VariableSpec(name="X", kind="binary"),
            VariableSpec(name="Y", kind="continuous"),
        ],
        relationships=[],
        parameters={"alpha": 0.5},
        metadata=WorldMetadata(domain="generic"),
    )


@pytest.fixture
def research_case() -> ResearchCase:
    return ResearchCase(
        case_id="case-001",
        brief="Investigá el efecto de X sobre Y.",
        context="Dataset observacional de 1000 unidades.",
        datasets=[
            Dataset(
                id="main",
                description="Datos principales",
                columns=["x", "y"],
                n_rows=1000,
                path="data/main.csv",
            )
        ],
        tools=[
            ToolSpec(
                name="python_exec",
                description="Ejecutar Python sobre los datasets",
                schema_={"type": "object", "properties": {"code": {"type": "string"}}},
            )
        ],
    )


@pytest.fixture
def paper_insights() -> PaperInsights:
    return PaperInsights(
        paper_id="p1",
        objective="Estudia efecto de X sobre Y.",
        entities=["X", "Y", "Z"],
        mechanisms=["X afecta Y", "Z confunde X-Y"],
        phenomena=["paradoja de Simpson cuando se estratifica por Z"],
        complications=["Z parcialmente no observado"],
        counterintuitive_priors=["asumir que X protege a Y en LBW"],
        realism_bounds=["X y Y dentro de rangos plausibles"],
    )


@pytest.fixture
def phenomena_manifest() -> PhenomenaManifest:
    return PhenomenaManifest(
        world_id="w1",
        phenomena=[
            Phenomenon(
                kind="counterintuitive",
                description="Efecto crudo positivo, ajustado nulo.",
                evidence=ExecutableEvidence(
                    script="env.intervene(do={'X': 1}, n=1000)",
                    numerical_result={"ate": 0.3},
                ),
            )
        ],
        interesting_score=0.8,
    )


@pytest.fixture
def investigation_log() -> InvestigationLog:
    return InvestigationLog(
        case_id="case-001",
        actions=[
            InvestigatorAction(
                step=1,
                timestamp=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
                kind="python_exec",
                payload={"code": "df.head()"},
                rationale="Inspección inicial",
                epistemic_tag="E",
            )
        ],
        hypotheses_log=[
            HypothesisEntry(step=2, text="X aumenta Y", rationale="primera mirada")
        ],
        final_claims=[Claim(text="X aumenta Y en ~0.3.", cited_evidence=["main"])],
    )


@pytest.fixture
def validation_report() -> ValidationReport:
    return ValidationReport(passed=True)
