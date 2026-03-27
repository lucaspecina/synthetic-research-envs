"""Tests for OI Solver Prompt template."""

from __future__ import annotations

from sreg.tools.oi_prompts import (
    build_oi_briefing,
    build_oi_solver_prompt,
    build_oi_strategy_section,
    build_oi_system_prompt,
    build_oi_tools_section,
)


def _sample_catalog():
    return [
        {
            "artifact_id": "dataset_bg",
            "description": "Background environmental measurements",
            "columns": ["temperature", "humidity", "pollution", "health"],
            "num_rows": 500,
            "source": "Multi-site monitoring network",
        },
        {
            "artifact_id": "dataset_survey",
            "description": "Field survey of local conditions",
            "num_rows": 150,
        },
    ]


class TestSystemPrompt:
    def test_contains_investigation_framing(self):
        prompt = build_oi_system_prompt()
        assert "research scientist" in prompt
        assert "INVESTIGATE" in prompt

    def test_contains_causation_warning(self):
        prompt = build_oi_system_prompt()
        assert "causal language" in prompt.lower()
        assert "observational regression" in prompt.lower()

    def test_no_predetermined_questions(self):
        prompt = build_oi_system_prompt()
        assert "do NOT have predetermined questions" in prompt


class TestToolsSection:
    def test_lists_artifacts(self):
        section = build_oi_tools_section(_sample_catalog())
        assert "dataset_bg" in section
        assert "dataset_survey" in section

    def test_shows_columns(self):
        section = build_oi_tools_section(_sample_catalog())
        assert "temperature" in section
        assert "health" in section

    def test_shows_row_count(self):
        section = build_oi_tools_section(_sample_catalog())
        assert "500 rows" in section

    def test_lists_all_tools(self):
        section = build_oi_tools_section([])
        assert "load_artifact" in section
        assert "python_exec" in section
        assert "submit_claims" in section
        assert "oi.corr" in section
        assert "oi.regress" in section


class TestBriefing:
    def test_includes_research_brief(self):
        brief = build_oi_briefing("Study pollution effects on health", [])
        assert "pollution effects on health" in brief

    def test_lists_datasets(self):
        brief = build_oi_briefing("Brief text", _sample_catalog())
        assert "dataset_bg" in brief
        assert "dataset_survey" in brief


class TestStrategy:
    def test_four_phases(self):
        strategy = build_oi_strategy_section()
        assert "EXPLORE" in strategy
        assert "INVESTIGATE" in strategy
        assert "VALIDATE" in strategy
        assert "REPORT" in strategy

    def test_association_vs_causation(self):
        strategy = build_oi_strategy_section()
        assert "Association vs Causation" in strategy


class TestFullPrompt:
    def test_combines_all_sections(self):
        prompt = build_oi_solver_prompt(
            research_brief="Study the relationship between X and Y",
            artifact_catalog=_sample_catalog(),
            title="Environmental Health Study",
            domain="epidemiology",
        )
        # System
        assert "research scientist" in prompt
        # Title
        assert "Environmental Health Study" in prompt
        assert "epidemiology" in prompt
        # Tools
        assert "load_artifact" in prompt
        assert "dataset_bg" in prompt
        # Briefing
        assert "relationship between X and Y" in prompt
        # Strategy
        assert "EXPLORE" in prompt

    def test_no_scoring_info(self):
        """Solver should NOT know about scoring, warrant, or coverage."""
        prompt = build_oi_solver_prompt(
            "Brief", _sample_catalog(),
        )
        assert "warrant" not in prompt.lower()
        assert "coverage" not in prompt.lower()
        assert "correctness" not in prompt.lower()
        assert "salience" not in prompt.lower()

    def test_without_title(self):
        prompt = build_oi_solver_prompt("Brief", [])
        assert "research scientist" in prompt
        # Should not have investigation title section
        assert "Investigation:" not in prompt
