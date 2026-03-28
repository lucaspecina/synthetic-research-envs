"""Tests for OI sub-question resolution and scoring.

Tests the full pipeline:
    SubQuestionIntent -> resolve -> ResolvedSubQuestion -> score vs claims
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make curated worlds importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_oi_curated_worlds import world_ecosystem, world_education, world_treatment

from sreg.models.open_investigation import (
    AcceptanceRule,
    AskOperator,
    EpisodeSubQuestionScore,
    ResolvedAnswer,
    ResolvedSubQuestion,
    SQRoles,
    SQTier,
    SubQuestionIntent,
    SubQuestionScore,
)
from sreg.tools.oi_compiler import ClaimIntent, Direction, PatternClass
from sreg.tools.oi_subquestions import (
    resolve_all,
    resolve_subquestion,
    score_claim_vs_subquestion,
    score_episode_with_subquestions,
)

N_MC = 20_000
SEED = 42


# ---------------------------------------------------------------------------
# Model construction tests
# ---------------------------------------------------------------------------


class TestSubQuestionModels:
    def test_sq_roles_focus_variables(self):
        roles = SQRoles(treatment="X", outcome="Y", mediator="M")
        assert roles.focus_variables == frozenset({"X", "Y", "M"})

    def test_sq_roles_requires_at_least_one(self):
        with pytest.raises(ValueError, match="at least one"):
            SQRoles()

    def test_subquestion_weight_from_tier(self):
        sq = SubQuestionIntent(
            sq_id="test", pattern="causal_effect",
            roles=SQRoles(treatment="X", outcome="Y"),
            ask=AskOperator.SIGN, tier=SQTier.MEDIUM,
        )
        assert sq.weight == 0.6

    def test_subquestion_high_tier(self):
        sq = SubQuestionIntent(
            sq_id="test", pattern="causal_effect",
            roles=SQRoles(treatment="X", outcome="Y"),
            ask=AskOperator.EXISTENCE_AND_SIGN,
        )
        assert sq.weight == 1.0  # default HIGH


# ---------------------------------------------------------------------------
# Resolution tests — Treatment world
# ---------------------------------------------------------------------------


class TestResolutionTreatment:
    """Resolve sub-questions against the treatment curated world."""

    @pytest.fixture
    def treatment_sqs(self):
        return [
            SubQuestionIntent(
                sq_id="sq1", pattern="causal_effect",
                roles=SQRoles(treatment="Treatment", outcome="Recovery"),
                ask=AskOperator.EXISTENCE_AND_SIGN, tier=SQTier.HIGH,
            ),
            SubQuestionIntent(
                sq_id="sq2", pattern="mediation",
                roles=SQRoles(
                    treatment="Treatment", mediator="Biomarker", outcome="Recovery",
                ),
                ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
            ),
            SubQuestionIntent(
                sq_id="sq3", pattern="confounding",
                roles=SQRoles(
                    treatment="Treatment", outcome="Recovery", confounder="Severity",
                ),
                ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
            ),
            SubQuestionIntent(
                sq_id="sq4", pattern="causal_effect",
                roles=SQRoles(treatment="Severity", outcome="Recovery"),
                ask=AskOperator.SIGN, tier=SQTier.MEDIUM,
            ),
        ]

    @pytest.fixture
    def resolved(self, treatment_sqs):
        world = world_treatment()
        return resolve_all(treatment_sqs, world, target="Recovery", n_mc=N_MC, seed=SEED)

    def test_resolves_all(self, resolved):
        assert len(resolved) == 4

    def test_sq1_treatment_positive(self, resolved):
        r = resolved[0]
        assert r.resolved_answer.exists is True
        assert r.resolved_answer.direction == "positive"
        assert r.resolved_answer.magnitude > 0.5

    def test_sq2_mediation_exists(self, resolved):
        r = resolved[1]
        assert r.resolved_answer.exists is True
        assert r.acceptance_rule == AcceptanceRule.ALL_OF
        assert len(r.components) == 2
        # Indirect effect component
        indirect = r.components[0]
        assert indirect.pattern == "mediation"
        assert indirect.contribution == 0.7
        # Total effect component
        total = r.components[1]
        assert total.pattern == "causal_effect"
        assert total.contribution == 0.3

    def test_sq3_confounding_exists(self, resolved):
        r = resolved[2]
        assert r.resolved_answer.exists is True
        assert r.acceptance_rule == AcceptanceRule.ALL_OF
        assert len(r.components) == 2

    def test_sq4_severity_negative(self, resolved):
        r = resolved[3]
        assert r.resolved_answer.exists is True
        assert r.resolved_answer.direction == "negative"


# ---------------------------------------------------------------------------
# Resolution tests — Ecosystem world
# ---------------------------------------------------------------------------


class TestResolutionEcosystem:
    def test_algae_positive_on_fish(self):
        world = world_ecosystem()
        sq = SubQuestionIntent(
            sq_id="eco1", pattern="causal_effect",
            roles=SQRoles(treatment="Algae", outcome="Fish"),
            ask=AskOperator.EXISTENCE_AND_SIGN,
        )
        resolved = resolve_all([sq], world, target="Fish", n_mc=N_MC, seed=SEED)
        assert resolved[0].resolved_answer.exists is True
        assert resolved[0].resolved_answer.direction == "positive"

    def test_depth_positive_on_fish(self):
        world = world_ecosystem()
        sq = SubQuestionIntent(
            sq_id="eco2", pattern="causal_effect",
            roles=SQRoles(treatment="Depth", outcome="Fish"),
            ask=AskOperator.SIGN,
        )
        resolved = resolve_all([sq], world, target="Fish", n_mc=N_MC, seed=SEED)
        assert resolved[0].resolved_answer.direction == "positive"


# ---------------------------------------------------------------------------
# Resolution tests — Education world
# ---------------------------------------------------------------------------


class TestResolutionEducation:
    def test_education_skill_income_mediation(self):
        world = world_education()
        sq = SubQuestionIntent(
            sq_id="edu1", pattern="mediation",
            roles=SQRoles(
                treatment="Education", mediator="Skill", outcome="Income",
            ),
            ask=AskOperator.EXISTENCE,
        )
        resolved = resolve_all([sq], world, target="Income", n_mc=N_MC, seed=SEED)
        r = resolved[0]
        assert r.resolved_answer.exists is True
        assert len(r.components) == 2


# ---------------------------------------------------------------------------
# Scoring tests
# ---------------------------------------------------------------------------


class TestScoring:
    @pytest.fixture
    def treatment_resolved(self):
        world = world_treatment()
        sqs = [
            SubQuestionIntent(
                sq_id="sq1", pattern="causal_effect",
                roles=SQRoles(treatment="Treatment", outcome="Recovery"),
                ask=AskOperator.EXISTENCE_AND_SIGN,
            ),
            SubQuestionIntent(
                sq_id="sq2", pattern="mediation",
                roles=SQRoles(
                    treatment="Treatment", mediator="Biomarker", outcome="Recovery",
                ),
                ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
            ),
            SubQuestionIntent(
                sq_id="sq3", pattern="confounding",
                roles=SQRoles(
                    treatment="Treatment", outcome="Recovery", confounder="Severity",
                ),
                ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
            ),
        ]
        return resolve_all(sqs, world, target="Recovery", n_mc=N_MC, seed=SEED)

    def test_perfect_claims_high_score(self, treatment_resolved):
        """3 perfect claims matching 3 SQs should score very high."""
        claims = [
            (ClaimIntent(
                claim_id="c1", pattern=PatternClass.CAUSAL_EFFECT,
                treatment="Treatment", outcome="Recovery",
                direction=Direction.POSITIVE,
            ), 1.0),
            (ClaimIntent(
                claim_id="c2", pattern=PatternClass.CONFOUNDING,
                treatment="Treatment", outcome="Recovery",
                confounder="Severity", direction=Direction.POSITIVE,
            ), 1.0),
            (ClaimIntent(
                claim_id="c3", pattern=PatternClass.MEDIATION,
                treatment="Treatment", outcome="Recovery",
                mediator="Biomarker", direction=Direction.POSITIVE,
            ), 1.0),
        ]
        result = score_episode_with_subquestions(claims, treatment_resolved)
        assert result.total > 0.85
        assert result.coverage == 1.0  # All 3 SQs matched
        assert result.correctness == 1.0

    def test_wrong_direction_scores_zero(self, treatment_resolved):
        """Claim with wrong direction should score 0."""
        claims = [
            (ClaimIntent(
                claim_id="wrong", pattern=PatternClass.CAUSAL_EFFECT,
                treatment="Treatment", outcome="Recovery",
                direction=Direction.NEGATIVE,  # WRONG
            ), 0.0),  # Verified as false
        ]
        result = score_episode_with_subquestions(claims, treatment_resolved)
        assert result.total == 0.0

    def test_novel_finding_gets_bonus(self, treatment_resolved):
        """True claim outside all SQs should get novel bonus."""
        claims = [
            # Novel: Biomarker -> Recovery (not in any SQ)
            (ClaimIntent(
                claim_id="novel", pattern=PatternClass.CAUSAL_EFFECT,
                treatment="Biomarker", outcome="Recovery",
                direction=Direction.NEGATIVE,
            ), 1.0),
        ]
        result = score_episode_with_subquestions(claims, treatment_resolved)
        assert result.novel_bonus > 0.0
        assert result.coverage == 0.0  # No SQs matched

    def test_subsumption_mediation_to_causal(self, treatment_resolved):
        """Mediation claim should give partial credit to causal_effect SQ."""
        # Only submit mediation claim, no direct causal_effect claim
        claims = [
            (ClaimIntent(
                claim_id="med", pattern=PatternClass.MEDIATION,
                treatment="Treatment", outcome="Recovery",
                mediator="Biomarker", direction=Direction.POSITIVE,
            ), 1.0),
        ]
        result = score_episode_with_subquestions(claims, treatment_resolved)
        # SQ1 (causal_effect) should get partial credit via subsumption
        sq1_score = next(s for s in result.sq_scores if s.sq_id == "sq1")
        assert sq1_score.satisfaction > 0.0, "Mediation should partially satisfy causal_effect SQ"
        # SQ2 (mediation) should be fully satisfied
        sq2_score = next(s for s in result.sq_scores if s.sq_id == "sq2")
        assert sq2_score.satisfaction > 0.0

    def test_empty_claims_scores_zero(self, treatment_resolved):
        result = score_episode_with_subquestions([], treatment_resolved)
        assert result.total == 0.0
        assert result.coverage == 0.0

    def test_single_claim_partial_satisfaction(self, treatment_resolved):
        """One causal claim: full credit on SQ1, partial on SQ2/SQ3 via subsumption."""
        claims = [
            (ClaimIntent(
                claim_id="c1", pattern=PatternClass.CAUSAL_EFFECT,
                treatment="Treatment", outcome="Recovery",
                direction=Direction.POSITIVE,
            ), 1.0),
        ]
        result = score_episode_with_subquestions(claims, treatment_resolved)
        # SQ1 fully matched, SQ2/SQ3 get partial component credit via subsumption
        sq1 = next(s for s in result.sq_scores if s.sq_id == "sq1")
        sq2 = next(s for s in result.sq_scores if s.sq_id == "sq2")
        sq3 = next(s for s in result.sq_scores if s.sq_id == "sq3")
        assert sq1.satisfaction == 1.0
        assert 0.0 < sq2.satisfaction < 1.0, "Subsumption gives partial credit"
        assert 0.0 < sq3.satisfaction < 1.0, "Subsumption gives partial credit"
        # Weighted coverage should be between 0 and 1
        assert 0.0 < result.weighted_coverage < 1.0


# ---------------------------------------------------------------------------
# Claim vs SQ matching edge cases
# ---------------------------------------------------------------------------


class TestMatchingEdgeCases:
    @pytest.fixture
    def simple_resolved_sq(self):
        """A simple causal_effect SQ for testing matching."""
        from sreg.models.open_investigation import SQComponent
        answer = ResolvedAnswer(exists=True, direction="positive", magnitude=0.5)
        sq = SubQuestionIntent(
            sq_id="test_sq", pattern="causal_effect",
            roles=SQRoles(treatment="X", outcome="Y"),
            ask=AskOperator.EXISTENCE_AND_SIGN,
        )
        return ResolvedSubQuestion(
            intent=sq,
            resolved_answer=answer,
            components=[SQComponent(
                component_id="test_sq:main", pattern="causal_effect",
                roles=SQRoles(treatment="X", outcome="Y"),
                ask=AskOperator.EXISTENCE_AND_SIGN,
                contribution=1.0, resolved_answer=answer,
            )],
        )

    def test_exact_match(self, simple_resolved_sq):
        claim = ClaimIntent(
            claim_id="c", pattern=PatternClass.CAUSAL_EFFECT,
            treatment="X", outcome="Y", direction=Direction.POSITIVE,
        )
        score = score_claim_vs_subquestion(claim, 1.0, simple_resolved_sq)
        assert score == 1.0

    def test_wrong_pattern_no_match(self, simple_resolved_sq):
        claim = ClaimIntent(
            claim_id="c", pattern=PatternClass.TAIL_RISK,
            treatment="X", outcome="Y", direction=Direction.POSITIVE,
        )
        score = score_claim_vs_subquestion(claim, 1.0, simple_resolved_sq)
        assert score == 0.0

    def test_wrong_variables_no_match(self, simple_resolved_sq):
        claim = ClaimIntent(
            claim_id="c", pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A", outcome="B", direction=Direction.POSITIVE,
        )
        score = score_claim_vs_subquestion(claim, 1.0, simple_resolved_sq)
        assert score == 0.0

    def test_near_zero_claim_for_positive_answer(self, simple_resolved_sq):
        """Claiming near_zero when answer is positive = contradiction."""
        claim = ClaimIntent(
            claim_id="c", pattern=PatternClass.CAUSAL_EFFECT,
            treatment="X", outcome="Y", direction=Direction.NEAR_ZERO,
        )
        score = score_claim_vs_subquestion(claim, 1.0, simple_resolved_sq)
        assert score == 0.0

    def test_false_claim_no_credit(self, simple_resolved_sq):
        """Claim with truth=0 should never get credit."""
        claim = ClaimIntent(
            claim_id="c", pattern=PatternClass.CAUSAL_EFFECT,
            treatment="X", outcome="Y", direction=Direction.POSITIVE,
        )
        score = score_claim_vs_subquestion(claim, 0.0, simple_resolved_sq)
        assert score == 0.0


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidateSubQuestions:
    """Tests for validate_sub_questions()."""

    @pytest.fixture
    def tw(self):
        return world_treatment()

    def _make_sq(self, sq_id="sq1", pattern="causal_effect",
                 treatment="Treatment", outcome="Recovery",
                 ask="existence_and_sign", tier="high", **extra_roles):
        roles = SQRoles(treatment=treatment, outcome=outcome, **extra_roles)
        return SubQuestionIntent(
            sq_id=sq_id, pattern=pattern, roles=roles,
            ask=AskOperator(ask), tier=SQTier(tier),
        )

    def test_valid_sqs_pass(self, tw):
        from sreg.tools.oi_subquestions import validate_sub_questions
        sqs = [
            self._make_sq("sq1", "causal_effect", "Treatment", "Recovery"),
            self._make_sq("sq2", "mediation", "Treatment", "Recovery",
                          mediator="Biomarker"),
            self._make_sq("sq3", "confounding", "Treatment", "Recovery",
                          confounder="Severity"),
            self._make_sq("sq4", "causal_effect", "Severity", "Recovery",
                          ask="sign", tier="medium"),
        ]
        accepted, errors = validate_sub_questions(sqs, tw, "experimental")
        hard = [e for e in errors if e["severity"] == "hard"]
        assert len(accepted) == 4
        assert len(hard) == 0

    def test_unknown_pattern_rejected(self, tw):
        from sreg.tools.oi_subquestions import validate_sub_questions
        sqs = [
            self._make_sq("sq1", "bogus_pattern"),
            self._make_sq("sq2", "causal_effect"),
            self._make_sq("sq3", "confounding", confounder="Severity"),
            self._make_sq("sq4", "causal_effect", "Severity", "Recovery",
                          tier="medium"),
        ]
        accepted, errors = validate_sub_questions(sqs, tw, "experimental")
        hard = [e for e in errors if e["severity"] == "hard"]
        assert len(hard) >= 1
        assert any("bogus_pattern" in str(e["reasons"]) for e in hard)

    def test_unknown_variable_rejected(self, tw):
        from sreg.tools.oi_subquestions import validate_sub_questions
        sqs = [
            self._make_sq("sq1", "causal_effect", "Nonexistent", "Recovery"),
            self._make_sq("sq2", "causal_effect"),
            self._make_sq("sq3", "confounding", confounder="Severity"),
            self._make_sq("sq4", "causal_effect", "Severity", "Recovery",
                          tier="medium"),
        ]
        accepted, errors = validate_sub_questions(sqs, tw, "experimental")
        hard = [e for e in errors if e["severity"] == "hard"]
        assert len(hard) >= 1
        assert any("Nonexistent" in str(e["reasons"]) for e in hard)

    def test_epistemological_check_rejects_causal_in_obs(self, tw):
        from sreg.tools.oi_subquestions import validate_sub_questions
        sqs = [
            self._make_sq("sq1", "causal_effect"),
            self._make_sq("sq2", "observational_association"),
            self._make_sq("sq3", "confounding", confounder="Severity"),
            self._make_sq("sq4", "observational_association",
                          "Severity", "Recovery", tier="medium"),
        ]
        accepted, errors = validate_sub_questions(
            sqs, tw, "observational_only"
        )
        hard = [e for e in errors if e["severity"] == "hard"]
        # sq1 uses causal_effect in obs_only -> rejected
        assert any("sq1" == e["sq_id"] for e in hard)
        # sq2/sq3/sq4 should be accepted (obs_assoc + confounding OK)
        assert "sq2" in [sq.sq_id for sq in accepted]

    def test_missing_roles_rejected(self, tw):
        from sreg.tools.oi_subquestions import validate_sub_questions
        # mediation without mediator
        roles = SQRoles(treatment="Treatment", outcome="Recovery")
        sq = SubQuestionIntent(
            sq_id="sq1", pattern="mediation", roles=roles,
            ask=AskOperator.EXISTENCE,
        )
        sqs = [
            sq,
            self._make_sq("sq2", "causal_effect"),
            self._make_sq("sq3", "causal_effect", "Severity", "Recovery",
                          tier="medium"),
        ]
        accepted, errors = validate_sub_questions(sqs, tw, "experimental")
        hard = [e for e in errors if e["severity"] == "hard"]
        assert any("mediator" in str(e["reasons"]) for e in hard)

    def test_duplicate_sqs_flagged(self, tw):
        from sreg.tools.oi_subquestions import validate_sub_questions
        sq = self._make_sq("sq1", "causal_effect")
        sq_dup = self._make_sq("sq2", "causal_effect")  # same pattern+vars
        sqs = [sq, sq_dup, self._make_sq("sq3", "confounding",
                                          confounder="Severity")]
        _, errors = validate_sub_questions(sqs, tw, "experimental")
        hard = [e for e in errors if e["severity"] == "hard"]
        assert any("Duplicate" in str(e["reasons"]) for e in hard)

    def test_reversed_roles_not_duplicate(self, tw):
        """causal_effect(T→R) and causal_effect(R→T) are different SQs."""
        from sreg.tools.oi_subquestions import validate_sub_questions
        sqs = [
            self._make_sq("sq1", "causal_effect", "Treatment", "Recovery"),
            self._make_sq("sq2", "causal_effect", "Recovery", "Treatment"),
            self._make_sq("sq3", "confounding", confounder="Severity"),
        ]
        _, errors = validate_sub_questions(sqs, tw, "experimental")
        hard = [e for e in errors if e["severity"] == "hard"]
        assert not any("Duplicate" in str(e["reasons"]) for e in hard)

    def test_portfolio_too_few_soft_error(self, tw):
        from sreg.tools.oi_subquestions import validate_sub_questions
        sqs = [
            self._make_sq("sq1", "causal_effect"),
            self._make_sq("sq2", "confounding", confounder="Severity"),
        ]
        _, errors = validate_sub_questions(sqs, tw, "experimental")
        soft = [e for e in errors if e["severity"] == "soft"]
        assert any("Too few" in str(e["reasons"]) for e in soft)


class TestCasePlanOIMode:
    """Tests for CasePlan with OI sub-questions."""

    def test_oi_mode_with_sub_questions(self):
        from sreg.models.case_plan import CasePlan
        sq = SubQuestionIntent(
            sq_id="sq1", pattern="causal_effect",
            roles=SQRoles(treatment="X", outcome="Y"),
            ask=AskOperator.EXISTENCE_AND_SIGN,
        )
        plan = CasePlan(
            title="OI Test Case",
            research_context="Testing OI mode with sub-questions",
            research_brief="Investigate X and Y.",
            oi_sub_questions=[sq],
            epistemic_regime="experimental",
            shared_budget=5,
        )
        assert plan.is_oi_mode
        assert len(plan.oi_sub_questions) == 1
        assert plan.primary_question is None
        assert plan.questions == []

    def test_traditional_mode_still_works(self):
        from sreg.models.case_plan import CasePlan, EvalQuestionPlan
        from sreg.models.task import TaskType
        plan = CasePlan(
            title="Traditional Test",
            research_context="Testing traditional mode still works",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the effect?",
                    eval_type=TaskType.CAUSAL_EFFECT,
                    target_node="Y",
                )
            ],
            shared_budget=5,
        )
        assert not plan.is_oi_mode
        assert plan.primary_question is not None

    def test_neither_questions_nor_sqs_fails(self):
        from sreg.models.case_plan import CasePlan
        with pytest.raises(Exception, match="questions or oi_sub_questions"):
            CasePlan(
                title="Empty Test",
                research_context="Testing empty case plan fails",
                shared_budget=5,
            )
