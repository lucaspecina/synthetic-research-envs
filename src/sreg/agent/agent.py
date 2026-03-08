"""AgentSolver: LLM agent that receives a ResearchProblem and solves it."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from sreg.agent.prompts import AGENT_TOOL_DEFINITIONS, build_agent_system_prompt
from sreg.env.episode import EpisodeRunner
from sreg.models.episode import Action, ActionType, Observation
from sreg.models.research_problem import ResearchProblem
from sreg.models.score import Score
from sreg.models.world import World
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.verifier import VerifierTool

logger = logging.getLogger(__name__)


class AgentResult:
    """Result of an agent solving a research problem."""

    def __init__(self):
        self.submitted_answer: dict[str, float] | None = None
        self.confidence: float | None = None
        self.reasoning: str | None = None
        self.score: Score | None = None
        self.observations: list[Observation] = []
        self.budget_used: int = 0
        self.budget_total: int = 0
        self.messages: list[dict] = []


class AgentSolver:
    """LLM agent that plays through a research problem.

    Receives a ResearchProblem (narrative, data, actions, question),
    uses observe/submit tools routed through EpisodeRunner,
    and is scored by VerifierTool.
    """

    def __init__(
        self,
        model: str | None = None,
        max_iterations: int = 15,
        client: OpenAI | None = None,
    ):
        self.model = model or os.environ.get("AZURE_MODEL", "gpt-4o")
        self.max_iterations = max_iterations

        if client is not None:
            self._client = client
        else:
            self._client = OpenAI(
                base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
                api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
            )

    def solve(
        self,
        world: World,
        problem: ResearchProblem,
        seed: int = 0,
        on_step: Callable[[str, dict], None] | None = None,
    ) -> AgentResult:
        """Run the agent on a research problem.

        Args:
            world: The underlying World (hidden from the agent).
            problem: The ResearchProblem the agent sees.
            seed: Seed for sampling the true state.
            on_step: Optional callback for real-time output. Called with
                (event_type, data) where event_type is one of:
                "thinking", "observe", "submit", "error".
        """
        result = AgentResult()
        result.budget_total = problem.budget

        # Set up behind-the-scenes infrastructure
        solver = ExactBayesSolver(world)
        true_state = solver.sample_state(seed=seed)

        ep_tool = EpisodeGenTool()
        episode = ep_tool.generate(
            world, EpisodeGenConfig(budget=problem.budget, seed=seed)
        )
        runner = EpisodeRunner(world, episode, true_state)

        # Build the agent's prompt
        system_prompt = build_agent_system_prompt(problem)

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please analyze the data and solve this research problem."},
        ]

        for iteration in range(self.max_iterations):
            logger.info(f"Agent iteration {iteration + 1}")

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=AGENT_TOOL_DEFINITIONS,
            )

            choice = response.choices[0]
            message = choice.message

            # Add assistant message to history
            msg_dict: dict[str, Any] = {"role": "assistant"}
            if message.content:
                msg_dict["content"] = message.content
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            messages.append(msg_dict)

            # Notify callback about agent thinking
            if on_step and message.content:
                on_step("thinking", {
                    "content": message.content,
                    "iteration": iteration + 1,
                })

            if choice.finish_reason == "stop" and not message.tool_calls:
                logger.info("Agent finished without submitting")
                break

            if not message.tool_calls:
                break

            # Process tool calls
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                logger.info(f"Agent tool call: {fn_name}({fn_args})")

                tool_result = self._dispatch_tool(
                    fn_name, fn_args, runner, problem, result
                )

                # Notify callback about tool result
                if on_step:
                    if "error" in tool_result:
                        on_step("error", {"tool": fn_name, "error": tool_result["error"]})
                    elif fn_name == "observe":
                        on_step("observe", tool_result)
                    elif fn_name == "submit":
                        on_step("submit", tool_result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str),
                    }
                )

                # If agent submitted, we're done
                if fn_name == "submit" and "error" not in tool_result:
                    break

            # Check if episode is done
            if runner.is_finished:
                break

        result.messages = messages

        # Score the agent if they submitted
        if result.submitted_answer is not None:
            true_posterior = runner.true_posterior(problem.target_node)
            verifier = VerifierTool()
            result.score = verifier.score(
                agent_posterior=result.submitted_answer,
                true_posterior=true_posterior,
                budget_used=result.budget_used,
                budget_total=result.budget_total,
            )

        return result

    def _dispatch_tool(
        self,
        name: str,
        args: dict,
        runner: EpisodeRunner,
        problem: ResearchProblem,
        result: AgentResult,
    ) -> dict:
        """Execute an agent tool call."""
        try:
            if name == "observe":
                return self._handle_observe(args, runner, problem, result)
            elif name == "submit":
                return self._handle_submit(args, runner, problem, result)
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            logger.error(f"Agent tool {name} failed: {e}")
            return {"error": str(e)}

    def _handle_observe(
        self,
        args: dict,
        runner: EpisodeRunner,
        problem: ResearchProblem,
        result: AgentResult,
    ) -> dict:
        """Handle an observe tool call."""
        variable = args.get("variable", "")

        # Check if variable is available
        available_nodes = [a.node for a in problem.available_actions]
        if variable not in available_nodes:
            return {
                "error": (
                    f"Variable '{variable}' is not available. "
                    f"Available: {available_nodes}"
                ),
            }

        # Check budget
        if runner.budget_remaining <= 0:
            return {
                "error": "No budget remaining. You must submit your answer now.",
            }

        action = Action(type=ActionType.OBSERVE, node=variable)
        step_result = runner.step(action)

        obs = step_result.observation
        result.observations.append(obs)
        result.budget_used += 1

        return {
            "variable": obs.node,
            "observed_state": obs.state,
            "remaining_budget": step_result.remaining_budget,
            "message": f"{obs.node} was observed to be '{obs.state}'.",
        }

    def _handle_submit(
        self,
        args: dict,
        runner: EpisodeRunner,
        problem: ResearchProblem,
        result: AgentResult,
    ) -> dict:
        """Handle a submit tool call."""
        distribution = args.get("distribution", {})

        # Fallback: LLM sometimes puts state keys at top level
        if not distribution:
            target_states = set(problem.target_states)
            top_level = {k: v for k, v in args.items() if k in target_states}
            if top_level:
                distribution = top_level

        if not distribution:
            states_str = ", ".join(sorted(problem.target_states))
            return {
                "error": (
                    f"You must provide 'distribution' with keys: {states_str}. "
                    f'Example: {{"distribution": {{{", ".join(f"{s!r}: 0.33" for s in problem.target_states)}}}}}'
                ),
            }

        # Validate states match target
        expected = set(problem.target_states)
        provided = set(distribution.keys())
        if provided != expected:
            return {
                "error": (
                    f"Distribution keys must match target states. "
                    f"Expected: {sorted(expected)}, got: {sorted(provided)}"
                ),
            }

        # Normalize
        total = sum(distribution.values())
        if total <= 0:
            return {"error": "Distribution values must be positive."}
        distribution = {k: v / total for k, v in distribution.items()}

        # Submit through runner
        action = Action(
            type=ActionType.SUBMIT,
            answer=distribution,
            confidence=args.get("confidence"),
        )
        runner.step(action)

        result.submitted_answer = distribution
        result.confidence = args.get("confidence")
        result.reasoning = args.get("reasoning")

        return {
            "status": "submitted",
            "distribution": distribution,
        }


__all__ = ["AgentResult", "AgentSolver"]
