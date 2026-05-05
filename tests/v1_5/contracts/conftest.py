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
    EvidenceArtifact,
    GoldQuestion,
    HypothesisEntry,
    IntendedPhenomenon,
    InvestigationLog,
    InvestigatorAction,
    PaperInsights,
    PhenomenaManifest,
    Phenomenon,
    QuestionProposal,
    QuestionsBundle,
    ResearchCase,
    Rubric,
    SelectionReport,
    ToolSpec,
    ValidationReport,
    VariableSpec,
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
def evidence_artifact() -> EvidenceArtifact:
    return EvidenceArtifact(
        script=(
            "df1 = env.intervene(do={'X': 1}, n=1000)\n"
            "df0 = env.intervene(do={'X': 0}, n=1000)\n"
            "ate = df1['Y'].mean() - df0['Y'].mean()"
        ),
        numerical_result={"ate": 0.3, "n_samples": 1000},
        tag="ate_computation",
    )


@pytest.fixture
def gold_question(rubric: Rubric, evidence_artifact: EvidenceArtifact) -> GoldQuestion:
    return GoldQuestion(
        id="GQ1",
        text="¿Cuál es el efecto causal de X sobre Y?",
        weight=0.20,
        role="required",
        answer_key=AnswerKey(
            summary="Efecto positivo, ~+0.3.",
            numeric={"effect_direction": "positive", "magnitude": 0.3},
        ),
        answer_key_provenance=[evidence_artifact],
        identification_hint="El reporte menciona el efecto de X sobre Y con un número.",
        rubric=rubric,
    )


@pytest.fixture
def questions_bundle(gold_question: GoldQuestion) -> QuestionsBundle:
    return QuestionsBundle(questions=[gold_question])


@pytest.fixture
def question_proposal(rubric: Rubric, evidence_artifact: EvidenceArtifact) -> QuestionProposal:
    return QuestionProposal(
        proposal_id="prop_001",
        author_run_id="explorer_run_2_focus_collider",
        focus="ip_collider_smoking_u",
        question_text="¿El efecto estratificado por LBW se invierte?",
        rubric_draft=rubric,
        answer_key=AnswerKey(
            summary="Sí: en LBW=1 el efecto se invierte; señal de collider.",
            numeric={"effect_lbw_0": 0.013, "effect_lbw_1": -0.216},
        ),
        answer_key_provenance=[evidence_artifact],
        status="verified",
    )


@pytest.fixture
def selection_report() -> SelectionReport:
    return SelectionReport(
        selected_proposals=["prop_001", "prop_002"],
        rejected_proposals=["prop_003"],
        diversity_score=0.7,
    )


@pytest.fixture
def intended_phenomenon() -> IntendedPhenomenon:
    return IntendedPhenomenon(
        id="ip_collider_x_u",
        kind="collider",
        description="LBW como collider entre Smoking y un confounder no observado U",
        relevant_variables=["smoking", "low_birth_weight", "hidden_u"],
    )


@pytest.fixture
def world_spec(intended_phenomenon: IntendedPhenomenon) -> WorldSpec:
    return WorldSpec(
        formalism="scm",
        variables=[
            VariableSpec(name="X", kind="binary"),
            VariableSpec(name="Y", kind="continuous"),
        ],
        relationships=[],
        parameters={"alpha": 0.5},
        metadata=WorldMetadata(domain="generic"),
        intended_phenomena=[intended_phenomenon],
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
def phenomena_manifest(evidence_artifact: EvidenceArtifact) -> PhenomenaManifest:
    return PhenomenaManifest(
        world_id="w1",
        phenomena=[
            Phenomenon(
                kind="counterintuitive",
                description="Efecto crudo positivo, ajustado nulo.",
                evidence=evidence_artifact,
                tags=["collider", "simpson_reversal"],
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
