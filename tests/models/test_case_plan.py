"""Tests for CasePlan and EvalQuestionPlan models."""

import pytest
from pydantic import ValidationError

from sreg.models.case_plan import CasePlan, EvalQuestionPlan
from sreg.models.task import TaskType


# ---------------------------------------------------------------------------
# EvalQuestionPlan
# ---------------------------------------------------------------------------


class TestEvalQuestionPlan:
    def test_valid_question(self):
        q = EvalQuestionPlan(
            question_text="What is the most likely soil type in this region?",
            eval_type=TaskType.INFER_TARGET,
            target_node="soil_type",
            rationale="Core question of the research case",
        )
        assert q.eval_type == TaskType.INFER_TARGET
        assert q.target_node == "soil_type"

    def test_all_eval_types(self):
        for tt in TaskType:
            q = EvalQuestionPlan(
                question_text=f"Question about {tt.value} with enough length",
                eval_type=tt,
                target_node="node_a",
            )
            assert q.eval_type == tt

    def test_question_text_too_short(self):
        with pytest.raises(ValidationError, match="String should have at least 10"):
            EvalQuestionPlan(
                question_text="Short",
                eval_type=TaskType.INFER_TARGET,
                target_node="x",
            )

    def test_invalid_eval_type(self):
        with pytest.raises(ValidationError):
            EvalQuestionPlan(
                question_text="What is the most likely outcome?",
                eval_type="nonexistent_type",
                target_node="x",
            )

    def test_rationale_defaults_empty(self):
        q = EvalQuestionPlan(
            question_text="What is the dominant factor here?",
            eval_type=TaskType.NEXT_BEST_OBSERVATION,
            target_node="factor",
        )
        assert q.rationale == ""


# ---------------------------------------------------------------------------
# CasePlan
# ---------------------------------------------------------------------------


class TestCasePlan:
    @pytest.fixture
    def basic_plan(self):
        return CasePlan(
            title="Soil Analysis Case",
            research_context="A team of researchers is studying soil composition on planet XR-7.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the most likely soil type?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="soil_type",
                    rationale="Primary research question",
                ),
                EvalQuestionPlan(
                    question_text="What experiment would be most informative next?",
                    eval_type=TaskType.NEXT_BEST_OBSERVATION,
                    target_node="soil_type",
                    rationale="Guide the research strategy",
                ),
            ],
            shared_budget=5,
            rationale="Combines inference and strategy evaluation",
        )

    def test_valid_plan(self, basic_plan):
        assert basic_plan.title == "Soil Analysis Case"
        assert len(basic_plan.questions) == 2
        assert basic_plan.shared_budget == 5

    def test_primary_question(self, basic_plan):
        assert basic_plan.primary_question.eval_type == TaskType.INFER_TARGET

    def test_sub_questions(self, basic_plan):
        subs = basic_plan.sub_questions
        assert len(subs) == 1
        assert subs[0].eval_type == TaskType.NEXT_BEST_OBSERVATION

    def test_eval_types(self, basic_plan):
        assert basic_plan.eval_types == {
            TaskType.INFER_TARGET,
            TaskType.NEXT_BEST_OBSERVATION,
        }

    def test_single_question_plan(self):
        plan = CasePlan(
            title="Minimal Case",
            research_context="A minimal research scenario for testing.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the hidden variable's value?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="hidden",
                ),
            ],
            shared_budget=3,
        )
        assert len(plan.questions) == 1
        assert plan.sub_questions == []
        assert plan.primary_question.target_node == "hidden"

    def test_three_question_plan(self):
        plan = CasePlan(
            title="Full Evaluation Case",
            research_context="Complete evaluation with all three task types.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the most likely soil type?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="soil_type",
                ),
                EvalQuestionPlan(
                    question_text="What experiment would be most informative?",
                    eval_type=TaskType.NEXT_BEST_OBSERVATION,
                    target_node="soil_type",
                ),
                EvalQuestionPlan(
                    question_text="Which hypothesis best matches the evidence?",
                    eval_type=TaskType.HYPOTHESIS_SELECTION,
                    target_node="soil_type",
                ),
            ],
            shared_budget=8,
        )
        assert len(plan.questions) == 3
        assert plan.eval_types == {
            TaskType.INFER_TARGET,
            TaskType.NEXT_BEST_OBSERVATION,
            TaskType.HYPOTHESIS_SELECTION,
        }

    def test_no_questions_and_no_sqs_fails(self):
        with pytest.raises(ValidationError, match="questions or oi_sub_questions"):
            CasePlan(
                title="Empty Case",
                research_context="A case with no questions at all.",
                questions=[],
                shared_budget=5,
            )

    def test_title_too_short(self):
        with pytest.raises(ValidationError, match="at least 5"):
            CasePlan(
                title="Hi",
                research_context="Some research context for the case.",
                questions=[
                    EvalQuestionPlan(
                        question_text="What is the hidden value?",
                        eval_type=TaskType.INFER_TARGET,
                        target_node="x",
                    ),
                ],
                shared_budget=5,
            )

    def test_context_too_short(self):
        with pytest.raises(ValidationError, match="at least 20"):
            CasePlan(
                title="Valid Title",
                research_context="Too short",
                questions=[
                    EvalQuestionPlan(
                        question_text="What is the hidden value?",
                        eval_type=TaskType.INFER_TARGET,
                        target_node="x",
                    ),
                ],
                shared_budget=5,
            )

    def test_budget_must_be_positive(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            CasePlan(
                title="Budget Test",
                research_context="A research context long enough to pass.",
                questions=[
                    EvalQuestionPlan(
                        question_text="What is the hidden value?",
                        eval_type=TaskType.INFER_TARGET,
                        target_node="x",
                    ),
                ],
                shared_budget=0,
            )

    def test_duplicate_question_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate question"):
            CasePlan(
                title="Duplicate Test",
                research_context="A case testing duplicate question detection.",
                questions=[
                    EvalQuestionPlan(
                        question_text="What is the soil type in this region?",
                        eval_type=TaskType.INFER_TARGET,
                        target_node="soil",
                    ),
                    EvalQuestionPlan(
                        question_text="What is the soil composition here?",
                        eval_type=TaskType.INFER_TARGET,
                        target_node="soil",
                    ),
                ],
                shared_budget=5,
            )

    def test_same_eval_type_different_targets_ok(self):
        plan = CasePlan(
            title="Multi-target Case",
            research_context="Two inference questions targeting different nodes.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the soil type in this area?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="soil_type",
                ),
                EvalQuestionPlan(
                    question_text="What is the vegetation pattern?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="vegetation",
                ),
            ],
            shared_budget=6,
        )
        assert len(plan.questions) == 2

    def test_same_target_different_eval_types_ok(self):
        plan = CasePlan(
            title="Multi-eval Case",
            research_context="Different evaluation types for the same target.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the soil type?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="soil",
                ),
                EvalQuestionPlan(
                    question_text="What's the best next experiment for soil?",
                    eval_type=TaskType.NEXT_BEST_OBSERVATION,
                    target_node="soil",
                ),
            ],
            shared_budget=5,
        )
        assert len(plan.questions) == 2

    def test_rationale_defaults_empty(self):
        plan = CasePlan(
            title="No Rationale Case",
            research_context="A minimal case without explicit rationale.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the hidden variable?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="hidden",
                ),
            ],
            shared_budget=3,
        )
        assert plan.rationale == ""

    def test_serialization_roundtrip(self, basic_plan):
        data = basic_plan.model_dump()
        restored = CasePlan.model_validate(data)
        assert restored == basic_plan

    def test_json_roundtrip(self, basic_plan):
        json_str = basic_plan.model_dump_json()
        restored = CasePlan.model_validate_json(json_str)
        assert restored == basic_plan

    def test_research_brief_defaults_empty(self, basic_plan):
        """research_brief defaults to empty string for backward compat."""
        assert basic_plan.research_brief == ""
        assert basic_plan.deliverables == []

    def test_research_brief_and_deliverables(self):
        plan = CasePlan(
            title="Sanding risk investigation",
            research_context="Investigating sanding in the Vaca Muerta formation.",
            research_brief=(
                "Investigate why some fracture interference events result "
                "in sanding while others do not. Identify key operational "
                "and geomechanical factors."
            ),
            deliverables=[
                "Identify the main causal drivers of sanding",
                "Evaluate preventive interventions",
                "Recommend changes for next campaign",
            ],
            questions=[
                EvalQuestionPlan(
                    question_text="What factors affect sanding probability?",
                    eval_type=TaskType.CAUSAL_EFFECT,
                    target_node="sanding_risk",
                    intervention_node="pad_spacing",
                ),
            ],
            shared_budget=5,
        )
        assert "fracture interference" in plan.research_brief
        assert len(plan.deliverables) == 3
        assert "causal drivers" in plan.deliverables[0]

    def test_brief_serialization_roundtrip(self):
        plan = CasePlan(
            title="Test with brief",
            research_context="Testing brief serialization works correctly.",
            research_brief="Investigate the phenomenon.",
            deliverables=["Identify causes", "Recommend solutions"],
            questions=[
                EvalQuestionPlan(
                    question_text="What is the distribution?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="outcome",
                ),
            ],
            shared_budget=3,
        )
        data = plan.model_dump()
        restored = CasePlan.model_validate(data)
        assert restored.research_brief == plan.research_brief
        assert restored.deliverables == plan.deliverables
