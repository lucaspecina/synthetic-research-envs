"""Tests for OI Solver Driver."""

from __future__ import annotations

import json

import numpy as np
import pytest

from sreg.models.open_investigation import ClaimCard
from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.tools.oi_driver import (
    OI_SOLVER_TOOLS,
    OIInvestigationResult,
    ScriptedAction,
    _parse_claim_cards,
    build_oi_tool_handler,
    run_oi_scripted,
)
from sreg.tools.oi_runner import OIEpisodeRunner

# ---------------------------------------------------------------------------
# Fixtures (reuse from test_oi_runner pattern)
# ---------------------------------------------------------------------------


def _make_data_asset(
    artifact_id: str, name: str, n_rows: int = 50, cols: list[str] | None = None
) -> DataAsset:
    cols = cols or ["A", "B", "Y"]
    rng = np.random.default_rng(42)
    data = [{c: float(rng.normal()) for c in cols} for _ in range(n_rows)]
    return DataAsset(
        artifact_id=artifact_id,
        name=name,
        description=f"Test dataset {name}",
        format="tabular",
        data=data,
        columns=cols,
        num_rows=n_rows,
    )


def _make_problem() -> ResearchProblem:
    return ResearchProblem(
        world_id="test_world",
        title="Test Investigation",
        description="A test research problem",
        domain="test",
        data_assets=[
            _make_data_asset("dataset_bg", "background_records"),
            _make_data_asset("dataset_survey", "field_survey"),
        ],
        available_actions=[],
        budget=10,
        research_question="Investigate the relationship between A and Y",
        target_node="Y",
        target_states=["low", "medium", "high"],
    )


def _make_scm_world():
    from sreg.world.scm import SCMWorld

    return SCMWorld(
        id="test_world",
        graph={
            "A": [],
            "B": ["A"],
            "Y": ["A", "B"],
        },
        equations={
            "A": lambda p, rng: rng.normal(5, 2),
            "B": lambda p, rng: 0.5 * p["A"] + rng.normal(3, 1),
            "Y": lambda p, rng: 0.8 * p["A"] + 0.3 * p["B"] + rng.normal(0, 1),
        },
    )


def _make_runner() -> OIEpisodeRunner:
    return OIEpisodeRunner(_make_problem(), _make_scm_world(), seed=42)


def _claim_dict(
    claim_id: str = "c1",
    text: str = "A has a positive causal effect on Y via direct path",
    focus: list[str] | None = None,
    artifact_id: str = "dataset_bg",
    pattern_tags: list[str] | None = None,
) -> dict:
    """Return a claim as a raw dict (as an LLM tool call would provide)."""
    return {
        "claim_id": claim_id,
        "claim_text": text,
        "focus_variables": focus or ["A", "Y"],
        "confidence": 0.8,
        "evidence_basis": [
            {"artifact_id": artifact_id, "rationale": "regression analysis showed significance"},
        ],
        "pattern_tags": pattern_tags or ["causal_effect"],
    }


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    def test_three_tools(self):
        assert len(OI_SOLVER_TOOLS) == 3

    def test_tool_names(self):
        names = {t["function"]["name"] for t in OI_SOLVER_TOOLS}
        assert names == {"python_exec", "think", "submit_claims"}

    def test_python_exec_requires_code(self):
        tool = next(t for t in OI_SOLVER_TOOLS if t["function"]["name"] == "python_exec")
        assert "code" in tool["function"]["parameters"]["properties"]
        assert "code" in tool["function"]["parameters"]["required"]

    def test_submit_claims_schema(self):
        tool = next(
            t for t in OI_SOLVER_TOOLS if t["function"]["name"] == "submit_claims"
        )
        params = tool["function"]["parameters"]
        assert "claims" in params["properties"]
        items = params["properties"]["claims"]["items"]
        assert "claim_id" in items["properties"]
        assert "claim_text" in items["properties"]
        assert "focus_variables" in items["properties"]
        assert "confidence" in items["properties"]
        assert "evidence_basis" in items["properties"]

    def test_all_tools_have_description(self):
        for tool in OI_SOLVER_TOOLS:
            assert tool["function"]["description"]


# ---------------------------------------------------------------------------
# Claim parsing
# ---------------------------------------------------------------------------


class TestParseClaimCards:
    def test_valid_claim(self):
        cards = _parse_claim_cards([_claim_dict()])
        assert len(cards) == 1
        assert isinstance(cards[0], ClaimCard)
        assert cards[0].claim_id == "c1"

    def test_multiple_claims(self):
        cards = _parse_claim_cards([
            _claim_dict("c1"),
            _claim_dict("c2", text="B mediates the effect of A on Y through indirect path"),
        ])
        assert len(cards) == 2

    def test_non_dict_raises(self):
        with pytest.raises(TypeError, match="must be a dict"):
            _parse_claim_cards(["not a dict"])

    def test_missing_required_field(self):
        bad = {"claim_id": "c1", "claim_text": "too short"}
        with pytest.raises(ValueError, match="claims\\[0\\]"):
            _parse_claim_cards([bad])

    def test_claim_text_too_short(self):
        bad = _claim_dict()
        bad["claim_text"] = "short"
        with pytest.raises(ValueError):
            _parse_claim_cards([bad])


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------


class TestToolHandler:
    def test_think_returns_noted(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        result = json.loads(handler("think", {"reasoning": "checking data"}))
        assert result["status"] == "noted"

    def test_python_exec_runs_code(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        result = handler("python_exec", {"code": "x = 2 + 3\nprint(x)"})
        assert "5" in result

    def test_python_exec_no_code(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        result = json.loads(handler("python_exec", {}))
        assert "error" in result

    def test_python_exec_increments_step(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        handler("python_exec", {"code": "x = 1"})
        handler("python_exec", {"code": "y = 2"})
        assert runner._step["current"] == 2

    def test_python_exec_has_load_artifact(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        result = handler(
            "python_exec",
            {"code": "df = load_artifact('dataset_bg')\nprint(len(df))"},
        )
        assert "50" in result

    def test_submit_claims_success(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        # Load data first so warrant is non-trivial
        handler("python_exec", {"code": "df = load_artifact('dataset_bg')"})
        result = json.loads(
            handler("submit_claims", {"claims": [_claim_dict()]})
        )
        assert result["status"] == "submitted"
        assert result["n_claims"] == 1
        assert runner.is_submitted

    def test_submit_claims_empty(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        result = json.loads(handler("submit_claims", {"claims": []}))
        assert "error" in result

    def test_submit_claims_double_submit(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        handler("python_exec", {"code": "df = load_artifact('dataset_bg')"})
        handler("submit_claims", {"claims": [_claim_dict()]})
        result = json.loads(
            handler("submit_claims", {"claims": [_claim_dict("c2")]})
        )
        assert "error" in result
        assert "already submitted" in result["error"].lower()

    def test_submit_claims_bad_format(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        result = json.loads(
            handler("submit_claims", {"claims": [{"bad": "format"}]})
        )
        assert "error" in result

    def test_unknown_tool(self):
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        result = json.loads(handler("unknown_tool", {}))
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_submit_does_not_leak_score(self):
        """Score details should NOT be visible to solver."""
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        handler("python_exec", {"code": "df = load_artifact('dataset_bg')"})
        result_text = handler("submit_claims", {"claims": [_claim_dict()]})
        result = json.loads(result_text)
        # Should not contain scoring details
        assert "correctness" not in result
        assert "coverage" not in result
        assert "total" not in result

    def test_post_submit_guard_blocks_python_exec(self):
        """After submit, python_exec calls must be rejected (Codex #2)."""
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        handler("python_exec", {"code": "df = load_artifact('dataset_bg')"})
        handler("submit_claims", {"claims": [_claim_dict()]})
        assert runner.is_submitted
        # Now try to run code — should be rejected
        result = json.loads(
            handler("python_exec", {"code": "print('should not run')"})
        )
        assert "error" in result
        assert "already submitted" in result["error"].lower()

    def test_post_submit_guard_allows_think(self):
        """Think is always allowed, even after submit."""
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        handler("python_exec", {"code": "df = load_artifact('dataset_bg')"})
        handler("submit_claims", {"claims": [_claim_dict()]})
        result = json.loads(handler("think", {"reasoning": "done"}))
        assert result["status"] == "noted"

    def test_post_submit_guard_no_trace_mutation(self):
        """Post-submit python_exec must NOT modify trace/step count."""
        runner = _make_runner()
        handler = build_oi_tool_handler(runner)
        handler("python_exec", {"code": "df = load_artifact('dataset_bg')"})
        handler("submit_claims", {"claims": [_claim_dict()]})
        steps_before = runner._step["current"]
        handler("python_exec", {"code": "x = 1"})
        assert runner._step["current"] == steps_before  # No step increment


# ---------------------------------------------------------------------------
# Scripted investigation
# ---------------------------------------------------------------------------


class TestScriptedInvestigation:
    def test_simple_investigation(self):
        """Load data, analyze, submit."""
        runner = _make_runner()
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "df = load_artifact('dataset_bg')\nprint(df.shape)"},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": (
                    "r = oi.corr(df, cols=['A', 'Y'])\n"
                    "print(r)"
                )},
            ),
            ScriptedAction(
                tool="think",
                args={"reasoning": "A and Y are correlated. Let me check B."},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": "reg = oi.regress(df, y='Y', x=['A', 'B'])\nprint(reg)"},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [_claim_dict()]},
            ),
        ]
        result = run_oi_scripted(runner, script)
        assert result.submitted
        assert result.score is not None
        assert result.n_steps > 0
        assert len(result.messages) > 0

    def test_stops_after_submit(self):
        """Script continues after submit but runner is done."""
        runner = _make_runner()
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "df = load_artifact('dataset_bg')"},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [_claim_dict()]},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": "print('this should not run')"},
            ),
        ]
        result = run_oi_scripted(runner, script)
        assert result.submitted
        # Third action should not have executed (loop breaks after submit)
        assert result.n_steps == 1  # Only the first python_exec incremented step

    def test_no_action_stops(self):
        """None action means solver stops."""
        runner = _make_runner()
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "x = 1"},
            ),
            ScriptedAction(tool=None),
        ]
        result = run_oi_scripted(runner, script)
        assert not result.submitted
        assert result.score is None
        assert result.n_steps == 1

    def test_empty_script(self):
        runner = _make_runner()
        result = run_oi_scripted(runner, [])
        assert not result.submitted
        assert result.score is None

    def test_messages_have_system_and_user(self):
        runner = _make_runner()
        result = run_oi_scripted(runner, [ScriptedAction(tool=None)])
        roles = [m["role"] for m in result.messages]
        assert "system" in roles
        assert "user" in roles

    def test_messages_have_tool_results(self):
        runner = _make_runner()
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "print('hello')"},
            ),
            ScriptedAction(tool=None),
        ]
        result = run_oi_scripted(runner, script)
        tool_msgs = [m for m in result.messages if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        assert "hello" in tool_msgs[0]["content"]

    def test_trace_records_accesses(self):
        """Trace should record artifact loads."""
        runner = _make_runner()
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "df = load_artifact('dataset_bg')"},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": "df2 = load_artifact('dataset_survey')"},
            ),
            ScriptedAction(tool=None),
        ]
        result = run_oi_scripted(runner, script)
        accessed = {a.artifact_id for a in result.trace.accesses}
        assert "dataset_bg" in accessed
        assert "dataset_survey" in accessed

    def test_trace_records_accesses(self):
        """Trace should record artifact accesses."""
        runner = _make_runner()
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "df = load_artifact('dataset_bg')"},
            ),
            ScriptedAction(tool=None),
        ]
        result = run_oi_scripted(runner, script)
        assert len(result.trace.accesses) > 0

    def test_post_submit_code_blocked_in_script(self):
        """Code after submit should be blocked even in scripted mode."""
        runner = _make_runner()
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "df = load_artifact('dataset_bg')"},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [_claim_dict()]},
            ),
        ]
        result = run_oi_scripted(runner, script)
        steps_at_submit = runner._step["current"]
        assert result.submitted
        # Now manually call handler — should be blocked
        handler = build_oi_tool_handler(runner)
        blocked = json.loads(handler("python_exec", {"code": "x = 1"}))
        assert "error" in blocked
        assert runner._step["current"] == steps_at_submit


# ---------------------------------------------------------------------------
# Full E2E scripted investigation
# ---------------------------------------------------------------------------


class TestE2EScriptedFlow:
    def test_investigation_with_multiple_claims(self):
        """Solver loads data, analyzes, submits 2 claims."""
        runner = _make_runner()
        claims = [
            _claim_dict("c1", "A has a positive causal effect on Y via direct path"),
            _claim_dict(
                "c2",
                "B mediates the effect of A on Y through an indirect path",
                focus=["A", "B", "Y"],
                pattern_tags=["mediation"],
            ),
        ]
        script = [
            ScriptedAction(
                tool="python_exec",
                args={"code": "df = load_artifact('dataset_bg')\nprint(df.columns.tolist())"},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": (
                    "r = oi.regress(df, y='Y', x=['A', 'B'])\n"
                    "print(r)"
                )},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": (
                    "# Check mediation: does controlling for B reduce A's effect?\n"
                    "r_total = oi.regress(df, y='Y', x=['A'])\n"
                    "r_controlled = oi.regress(df, y='Y', x=['A', 'B'])\n"
                    "print('Total A effect:', r_total)\n"
                    "print('Direct A effect:', r_controlled)"
                )},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": claims},
            ),
        ]
        result = run_oi_scripted(runner, script)
        assert result.submitted
        assert result.score is not None
        assert result.score.total >= 0.0
        assert result.n_steps == 3  # 3 python_exec calls

    def test_score_reflects_evidence(self):
        """Claims with evidence should score higher than claims without load."""
        runner_with = _make_runner()
        runner_without = _make_runner()

        # With evidence: load data first
        result_with = run_oi_scripted(runner_with, [
            ScriptedAction(
                tool="python_exec",
                args={"code": "df = load_artifact('dataset_bg')"},
            ),
            ScriptedAction(
                tool="python_exec",
                args={"code": "oi.regress(df, y='Y', x=['A'])"},
            ),
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [_claim_dict()]},
            ),
        ])

        # Without evidence: submit without loading data
        result_without = run_oi_scripted(runner_without, [
            ScriptedAction(
                tool="submit_claims",
                args={"claims": [_claim_dict()]},
            ),
        ])

        # Both should produce scores (deterministic fallback)
        assert result_with.score is not None
        assert result_without.score is not None
        # Score with evidence should be >= score without
        # (warrant multiplier should make the difference)
        assert result_with.score.total >= result_without.score.total


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class TestOIInvestigationResult:
    def test_default_values(self):
        result = OIInvestigationResult()
        assert result.score is None
        assert result.messages == []
        assert result.n_steps == 0
        assert not result.submitted

    def test_with_score(self):
        from sreg.models.open_investigation import EpisodeScore

        score = EpisodeScore(
            correctness=0.7, coverage=0.5, efficiency=0.1, total=0.55,
            families_hit=3, families_total=5,
        )
        result = OIInvestigationResult(score=score, submitted=True)
        assert result.score.total == 0.55
        assert result.submitted
