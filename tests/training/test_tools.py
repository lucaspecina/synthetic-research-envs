"""Tests for async tool functions (research_action, submit)."""

import asyncio

from sreg.models.episode import ActionDef
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool
from sreg.training.tools import research_action, submit


def _make_runner_and_state(seed=42, eval_type="infer_target"):
    """Create an EpisodeRunner and state dict for testing.

    Generates a world + episode, then adds ActionDefs from available_nodes
    so the episode works in rich-action mode (which is what real SRCs use).
    """
    from sreg.env.episode import EpisodeRunner

    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(seed=seed, num_nodes=6, edge_strength=0.7))
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)

    ep_gen = EpisodeGenTool()
    episode = ep_gen.generate(world, EpisodeGenConfig(budget=4, seed=seed))

    # Add ActionDefs from available_nodes (rich-action mode for training)
    for node_name in episode.available_nodes:
        cost = episode.node_costs.get(node_name, 1)
        episode.action_defs.append(
            ActionDef(
                id=f"act_{node_name}",
                action_type="observe",
                nodes=[node_name],
                cost=cost,
            )
        )

    runner = EpisodeRunner(world=world, episode=episode, true_state=true_state)

    # Find target node
    from sreg.models.world import NodeType

    target = next(n for n in world.nodes if n.type == NodeType.TARGET)
    prior = solver.posterior(target.name, {})

    state = {
        "runner": runner,
        "eval_type": eval_type,
        "correct_answer": {s: round(p, 6) for s, p in prior.items()},
        "submitted": False,
        "submission_payload": None,
        "done_reason": None,
        "invalid_action_count": 0,
        "budget_used": 0,
        "tool_trace": [],
    }
    return runner, state, world


class TestResearchAction:
    def test_valid_observe(self):
        runner, state, world = _make_runner_and_state()
        # Get first available node
        node = runner.episode.available_nodes[0]
        result = asyncio.get_event_loop().run_until_complete(
            research_action(action_id=f"act_{node}", runner=runner, state=state)
        )
        assert "Error" not in result
        assert "Budget remaining" in result
        assert len(state["tool_trace"]) == 1
        assert state["tool_trace"][0]["ok"] is True

    def test_invalid_action_id(self):
        runner, state, _ = _make_runner_and_state()
        result = asyncio.get_event_loop().run_until_complete(
            research_action(action_id="nonexistent_action", runner=runner, state=state)
        )
        assert "Error" in result
        assert state["invalid_action_count"] == 1

    def test_no_runner(self):
        result = asyncio.get_event_loop().run_until_complete(
            research_action(action_id="obs_x", runner=None, state=None)
        )
        assert "Error" in result

    def test_budget_tracking(self):
        runner, state, _ = _make_runner_and_state()
        node = runner.episode.available_nodes[0]
        asyncio.get_event_loop().run_until_complete(
            research_action(action_id=f"act_{node}", runner=runner, state=state)
        )
        assert state["budget_used"] > 0


class TestSubmit:
    def test_valid_distribution_submit(self):
        _, state, _ = _make_runner_and_state(eval_type="infer_target")
        result = asyncio.get_event_loop().run_until_complete(
            submit(distribution='{"low": 0.5, "high": 0.5}', state=state)
        )
        assert "submitted" in result.lower() or "complete" in result.lower()
        assert state["submitted"] is True
        assert state["done_reason"] == "submit"
        assert state["submission_payload"] is not None

    def test_valid_choice_submit(self):
        _, state, _ = _make_runner_and_state(eval_type="should_condition")
        asyncio.get_event_loop().run_until_complete(
            submit(choice="yes", state=state)
        )
        assert state["submitted"] is True

    def test_valid_set_submit(self):
        _, state, _ = _make_runner_and_state(eval_type="adjustment_set")
        asyncio.get_event_loop().run_until_complete(
            submit(adjustment_set=["x", "y"], state=state)
        )
        assert state["submitted"] is True

    def test_double_submit_rejected(self):
        _, state, _ = _make_runner_and_state(eval_type="infer_target")
        asyncio.get_event_loop().run_until_complete(
            submit(distribution='{"low": 0.5, "high": 0.5}', state=state)
        )
        result = asyncio.get_event_loop().run_until_complete(
            submit(distribution='{"low": 0.3, "high": 0.7}', state=state)
        )
        assert "Error" in result
        assert state["invalid_action_count"] == 1
        # Double submit should be traced
        trace_errors = [t for t in state["tool_trace"] if not t["ok"]]
        assert len(trace_errors) == 1
        assert trace_errors[0]["error"] == "already submitted"

    def test_wrong_format_rejected(self):
        _, state, _ = _make_runner_and_state(eval_type="infer_target")
        result = asyncio.get_event_loop().run_until_complete(
            submit(choice="A", state=state)
        )
        assert "Error" in result
        assert state["submitted"] is False
        assert state["invalid_action_count"] == 1

    def test_empty_submit_rejected(self):
        _, state, _ = _make_runner_and_state(eval_type="infer_target")
        result = asyncio.get_event_loop().run_until_complete(
            submit(state=state)
        )
        assert "Error" in result
        assert state["submitted"] is False

    def test_no_state(self):
        result = asyncio.get_event_loop().run_until_complete(
            submit(choice="A", state=None)
        )
        assert "Error" in result
