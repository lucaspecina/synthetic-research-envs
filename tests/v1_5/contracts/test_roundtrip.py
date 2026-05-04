"""Roundtrip JSON tests: serialize → deserialize → equal.

Garantiza que los contratos top-level se persisten y reconstruyen sin
pérdida ni mutación.
"""

from __future__ import annotations

from sreg.v1_5.contracts import (
    InvestigationLog,
    PaperInsights,
    PhenomenaManifest,
    QuestionsBundle,
    ResearchCase,
    ValidationReport,
    WorldSpec,
)


def _roundtrip(model_instance, model_cls):
    """Helper: serialize a JSON, deserialize, comparar igualdad estructural."""
    json_text = model_instance.model_dump_json()
    reconstructed = model_cls.model_validate_json(json_text)
    assert reconstructed == model_instance


def test_world_spec_roundtrip(world_spec: WorldSpec) -> None:
    _roundtrip(world_spec, WorldSpec)


def test_paper_insights_roundtrip(paper_insights: PaperInsights) -> None:
    _roundtrip(paper_insights, PaperInsights)


def test_phenomena_manifest_roundtrip(phenomena_manifest: PhenomenaManifest) -> None:
    _roundtrip(phenomena_manifest, PhenomenaManifest)


def test_questions_bundle_roundtrip(questions_bundle: QuestionsBundle) -> None:
    _roundtrip(questions_bundle, QuestionsBundle)


def test_research_case_roundtrip(research_case: ResearchCase) -> None:
    _roundtrip(research_case, ResearchCase)


def test_investigation_log_roundtrip(investigation_log: InvestigationLog) -> None:
    _roundtrip(investigation_log, InvestigationLog)


def test_validation_report_roundtrip(validation_report: ValidationReport) -> None:
    _roundtrip(validation_report, ValidationReport)
