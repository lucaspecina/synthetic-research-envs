"""Async E2E tests for the env bridge in sreg.training.tools.

These exercise the asyncio.wait_for / asyncio.to_thread path that connects
verifiers' async tool protocol to the synchronous OIEpisodeRunner. The
critical invariant (issue #25): if the async timeout fires, the worker
thread must NOT end up committing the runner in a way that blocks a retry.

Tests are plain sync functions that call asyncio.run() on an inner async
helper. This avoids a new dependency on pytest-asyncio.
"""

from __future__ import annotations

import asyncio
import time

import numpy as np
import pytest

from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    AtomVerdict,
    Comparison,
    ComparisonKind,
    EpisodeSubQuestionScore,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
    SubQuestionIntentV2,
    VerificationSpec,
)
from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.tools.oi_runner import OIEpisodeRunner
from sreg.training.tools import _parse_claim, submit_claims


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_data_asset(artifact_id: str = "dataset_bg", n_rows: int = 50) -> DataAsset:
    cols = ["A", "B", "Y"]
    rng = np.random.default_rng(42)
    data = [{c: float(rng.normal()) for c in cols} for _ in range(n_rows)]
    return DataAsset(
        artifact_id=artifact_id,
        name="background_records",
        description="Test dataset",
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
        data_assets=[_make_data_asset()],
        available_actions=[],
        budget=10,
        research_question="Investigate the relationship between A and Y",
        target_node="Y",
        target_states=["low", "medium", "high"],
    )


def _make_scm_world():
    from sreg.world.scm import SCMWorld, VariableMeta

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
        variable_meta={
            "A": VariableMeta(description="Exposure intensity", unit="mg/L"),
            "B": VariableMeta(description="Intermediate burden", unit="index"),
            "Y": VariableMeta(description="Outcome response", unit="points"),
        },
    )


def _make_sq() -> SubQuestionIntentV2:
    atom = AtomicSpec(
        spec_id="s1",
        arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
        measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.POSITIVE),
    )
    verdict = AtomVerdict(
        atom_id="s1", spec=atom, ground_truth=1.0,
        solver_assertion_holds=True, score=1.0,
    )
    spec = VerificationSpec(spec=atom, role="required", verdict=verdict)
    return SubQuestionIntentV2(
        sq_id="sq1",
        text_gloss="Does A increase Y?",
        verification_specs=[spec],
        focus_variables=("A", "Y"),
    )


def _dummy_score(total: float = 0.5) -> EpisodeSubQuestionScore:
    return EpisodeSubQuestionScore(
        sq_scores=[], coverage=total, weighted_coverage=total,
        correctness=total, novel_bonus=0.0, total=total,
    )


def _build_runner() -> OIEpisodeRunner:
    problem = _make_problem()
    world = _make_scm_world()
    runner = OIEpisodeRunner(problem, world, n_mc=1000)
    runner.set_subquestions_v2([_make_sq()])
    # Simulate solver having accessed the artifact (so evidence_basis passes).
    runner._namespace["load_artifact"]("dataset_bg")
    return runner


def _claim_dict(claim_id: str = "c1") -> dict:
    return {
        "claim_id": claim_id,
        "claim_text": "A has a positive effect on Y",
        "focus_variables": ["A", "Y"],
        "confidence": 0.8,
        "evidence_basis": [
            {"artifact_id": "dataset_bg", "rationale": "regression"},
        ],
    }


# ---------------------------------------------------------------------------
# Tests — the issue #25 race invariants
# ---------------------------------------------------------------------------


class TestEnvBridgeTimeoutRace:
    """Cover the race condition: asyncio.wait_for cancels the await but NOT
    the worker thread. The env bridge must ensure either:
      (a) the thread aborts before committing (via cancel_event), OR
      (b) the retry recovers the score from a runner that committed late.
    """

    def test_slow_scoring_timeouts_without_committing_runner(self, monkeypatch):
        """Core invariant: slow scoring + fast env timeout → runner stays
        pristine because cancel_event stops the worker thread before commit."""
        # Short env timeout; slow scoring (longer than timeout).
        monkeypatch.setattr("sreg.training.tools._SCORING_TIMEOUT_S", 0.1)

        runner = _build_runner()

        def slow_score(claims, compiled):
            time.sleep(0.5)  # 5x the env timeout
            return (_dummy_score(), {}, [], [])

        runner._score_with_judge = slow_score
        state: dict = {}

        async def run():
            result = await submit_claims(
                [_claim_dict()], runner=runner, state=state,
            )
            assert "timed out" in result.lower(), result
            # Give the worker thread time to finish scoring and hit the
            # cancel checkpoint before we inspect runner state.
            await asyncio.sleep(0.8)

        asyncio.run(run())

        # Runner must be pristine: cancel_event fired, commit aborted.
        assert state.get("submit_error") == "scoring_timeout"
        assert not state.get("submitted")
        assert not runner.is_submitted
        assert runner.get_score() is None

    def test_retry_after_timeout_succeeds(self, monkeypatch):
        """After a timeout + cancel, a fresh submit with fast scoring must
        succeed — no ghost 'already submitted' error."""
        monkeypatch.setattr("sreg.training.tools._SCORING_TIMEOUT_S", 0.1)

        runner = _build_runner()

        def slow_score(claims, compiled):
            time.sleep(0.5)
            return (_dummy_score(), {}, [], [])

        runner._score_with_judge = slow_score
        state1: dict = {}

        async def attempt_one():
            result = await submit_claims(
                [_claim_dict()], runner=runner, state=state1,
            )
            assert "timed out" in result.lower()
            await asyncio.sleep(0.8)  # let worker thread abort

        asyncio.run(attempt_one())
        assert not runner.is_submitted

        # Second attempt: fast scoring, fresh state. Should succeed cleanly.
        runner._score_with_judge = lambda c, co: (_dummy_score(0.7), {}, [], [])
        state2: dict = {}

        async def attempt_two():
            result = await submit_claims(
                [_claim_dict()], runner=runner, state=state2,
            )
            return result

        result2 = asyncio.run(attempt_two())
        assert "successfully" in result2.lower(), result2
        assert state2.get("submitted")
        assert runner.is_submitted
        assert runner.get_score() is not None

    def test_race_recovery_when_thread_commits_before_cancel(self, monkeypatch):
        """Tricky case: the worker thread finished its commit BEFORE the
        env could set cancel_event (or before the retry's check). The retry
        must recover the score from the runner rather than returning an
        'already submitted' error to the agent — BUT only if the retry's
        claims match the committed payload (fingerprint check)."""
        runner = _build_runner()

        # Pre-commit with the SAME claim the retry will send. Mirrors the
        # race where the background thread finished scoring the agent's
        # claims; the retry happens to send the same claims.
        claim_card = _parse_claim(_claim_dict())
        bundle = (_dummy_score(0.9), {}, [], [])
        runner._commit_scoring_result(
            compiled=[], claims=[claim_card],
            bundle=bundle, record_claim_steps=False,
        )
        assert runner.is_submitted

        # Now the retry happens. state.submitted is False (env never saw
        # the success). runner raises AlreadySubmittedError. Env should
        # recover the score because payloads match.
        state: dict = {}

        async def run():
            return await submit_claims(
                [_claim_dict()], runner=runner, state=state,
            )

        result = asyncio.run(run())

        assert "recovered from background scoring" in result, result
        assert state.get("submitted") is True
        assert state.get("submit_error") is None
        assert state.get("score") is runner.get_score()

    def test_recovery_refuses_mismatched_claims(self):
        """Safety check: if the retry sends DIFFERENT claims than the ones
        that actually committed in the background, the env must NOT silently
        award the old score. Correctness > convenience."""
        runner = _build_runner()

        # Background thread committed claim c1 with score 0.9.
        original_claim = _parse_claim(_claim_dict("c1"))
        bundle = (_dummy_score(0.9), {}, [], [])
        runner._commit_scoring_result(
            compiled=[], claims=[original_claim],
            bundle=bundle, record_claim_steps=False,
        )

        # Agent retries with a MODIFIED claim (different id + different text).
        modified_claim_dict = {
            "claim_id": "c2",
            "claim_text": "A has no effect on Y",  # opposite finding
            "focus_variables": ["A", "Y"],
            "confidence": 0.3,
            "evidence_basis": [
                {"artifact_id": "dataset_bg", "rationale": "second look"},
            ],
        }
        state: dict = {}

        async def run():
            return await submit_claims(
                [modified_claim_dict], runner=runner, state=state,
            )

        result = asyncio.run(run())

        # Must NOT recover: the score on runner belongs to the ORIGINAL
        # claims, not the retry's modified payload.
        assert "different claims" in result.lower(), result
        assert state.get("submit_error") == "already_submitted_payload_mismatch"
        assert "score" not in state  # no silent attribution
        assert not state.get("submitted")

    def test_submit_claims_increments_step_count(self):
        """Low-severity diagnostics fix: submit_claims must count as a
        tool call in state['step_count'], same as python_exec and think."""
        runner = _build_runner()
        runner._score_with_judge = lambda c, co: (_dummy_score(0.5), {}, [], [])
        state: dict = {"step_count": 3}  # simulate prior tool calls

        async def run():
            return await submit_claims(
                [_claim_dict()], runner=runner, state=state,
            )

        asyncio.run(run())
        assert state["step_count"] == 4, state

    def test_fast_scoring_commits_normally(self, monkeypatch):
        """Sanity: when scoring is faster than the timeout, no race path
        is exercised and the env bridge behaves like before."""
        runner = _build_runner()
        runner._score_with_judge = lambda c, co: (_dummy_score(0.6), {}, [], [])
        state: dict = {}

        async def run():
            return await submit_claims(
                [_claim_dict()], runner=runner, state=state,
            )

        result = asyncio.run(run())

        assert "successfully" in result.lower(), result
        assert state.get("submitted") is True
        assert state.get("submit_error") is None
        assert runner.is_submitted
