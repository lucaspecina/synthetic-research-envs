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

from sreg.agent.prompts import (
    CHOICE_TYPES,
    DISTRIBUTION_TYPES,
    build_agent_system_prompt,
    build_agent_tools,
)
from sreg.env.episode import EpisodeRunner
from sreg.models.episode import Action, ActionType, Observation
from sreg.models.research_problem import ResearchProblem
from sreg.models.score import Score
from sreg.models.task import Task, TaskType
from sreg.models.world import World
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.verifier import VerifierTool

logger = logging.getLogger(__name__)


class AgentResult:
    """Result of an agent solving a research problem."""

    def __init__(self):
        self.submitted_answer: Any = None  # dict, str, list — depends on task type
        self.confidence: float | None = None
        self.reasoning: str | None = None
        self.score: Score | None = None
        self.observations: list[Observation] = []
        self.budget_used: int = 0
        self.budget_total: int = 0
        self.messages: list[dict] = []
        self.task_type: TaskType | None = None


class AgentSolver:
    """LLM agent that plays through a research problem.

    Receives a ResearchProblem (narrative, data, actions, question),
    uses observe/submit tools routed through EpisodeRunner,
    and is scored by VerifierTool.

    When a Task is provided, the submit tool and scoring adapt to the task type:
    - Distribution types (infer_target, causal_effect, infer_latent_cause):
      submit {"distribution": {state: prob}}
    - Choice types (hypothesis_selection, compare_interventions, should_condition):
      submit {"choice": "A"} or {"choice": "yes"}
    - best_intervention: submit {"node": "X", "state": "Y"}
    - adjustment_set: submit {"variables": [...]}
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
        task: Task | None = None,
        on_step: Callable[[str, dict], None] | None = None,
    ) -> AgentResult:
        """Run the agent on a research problem.

        Args:
            world: The underlying World (hidden from the agent).
            problem: The ResearchProblem the agent sees.
            seed: Seed for sampling the true state.
            task: Optional Task for multi-type support. When provided,
                the submit tool and scoring adapt to the task type.
            on_step: Optional callback for real-time output. Called with
                (event_type, data) where event_type is one of:
                "thinking", "observe", "submit", "error".
        """
        result = AgentResult()
        result.budget_total = problem.budget
        result.task_type = task.type if task else TaskType.INFER_TARGET

        # Set up behind-the-scenes infrastructure
        solver = ExactBayesSolver(world)
        true_state = solver.sample_state(seed=seed)

        ep_tool = EpisodeGenTool()
        episode = ep_tool.generate(
            world, EpisodeGenConfig(budget=problem.budget, seed=seed)
        )
        runner = EpisodeRunner(world, episode, true_state)

        # Build the agent's prompt and tools (task-aware)
        system_prompt = build_agent_system_prompt(problem, task=task)
        tools = build_agent_tools(task=task, target_states=problem.target_states)

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please analyze the data and solve this research problem."},
        ]

        for iteration in range(self.max_iterations):
            logger.info(f"Agent iteration {iteration + 1}")

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
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
                    fn_name, fn_args, runner, problem, result, task
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

            # Check if episode is done (distribution types finish via runner,
            # non-distribution types finish via submitted_answer)
            if runner.is_finished or result.submitted_answer is not None:
                break

        result.messages = messages

        # Score the agent
        if result.submitted_answer is not None:
            result.score = self._score_result(result, task, problem, runner)

        return result

    def _dispatch_tool(
        self,
        name: str,
        args: dict,
        runner: EpisodeRunner,
        problem: ResearchProblem,
        result: AgentResult,
        task: Task | None = None,
    ) -> dict:
        """Execute an agent tool call."""
        try:
            if name == "observe":
                return self._handle_observe(args, runner, problem, result)
            elif name == "submit":
                return self._handle_submit(args, runner, problem, result, task)
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
        task: Task | None = None,
    ) -> dict:
        """Handle a submit tool call, routing by task type."""
        task_type = task.type if task else TaskType.INFER_TARGET

        if task_type in DISTRIBUTION_TYPES:
            return self._submit_distribution(args, runner, problem, result, task)
        elif task_type in CHOICE_TYPES or task_type == TaskType.NEXT_BEST_OBSERVATION:
            return self._submit_choice(args, result, task_type)
        elif task_type == TaskType.BEST_INTERVENTION:
            return self._submit_intervention(args, result)
        elif task_type == TaskType.ADJUSTMENT_SET:
            return self._submit_variable_set(args, result)
        else:
            return self._submit_distribution(args, runner, problem, result, task)

    def _submit_distribution(
        self, args: dict, runner: EpisodeRunner,
        problem: ResearchProblem, result: AgentResult,
        task: Task | None = None,
    ) -> dict:
        """Handle distribution submission (infer_target, causal_effect, etc.)."""
        # Use task-specific states when available (e.g. infer_latent_cause
        # has different states than problem.target_states)
        if task and task.correct_answer:
            expected_states = list(task.correct_answer.keys())
        else:
            expected_states = list(problem.target_states)

        distribution = args.get("distribution", {})

        # Fallback: LLM sometimes puts state keys at top level instead of
        # nesting under "distribution". Auto-correct silently to avoid
        # wasting a turn on format retry.
        if not distribution:
            state_set = set(expected_states)
            top_level = {
                k: v for k, v in args.items()
                if k in state_set and isinstance(v, (int, float))
            }
            if top_level:
                distribution = top_level

        if not distribution:
            states_str = ", ".join(sorted(expected_states))
            return {
                "error": (
                    f"You must provide 'distribution' with keys: {states_str}. "
                    f'Example: {{"distribution": '
                    f'{{{", ".join(f"{s!r}: 0.33" for s in expected_states)}}}}}'
                ),
            }

        # Validate states match target
        expected = set(expected_states)
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

        return {"status": "submitted", "distribution": distribution}

    def _submit_choice(
        self, args: dict, result: AgentResult, task_type: TaskType,
    ) -> dict:
        """Handle choice submission (hypothesis, compare, should_condition)."""
        choice = args.get("choice", "")

        if not choice:
            # Fallback: look for common patterns in args
            for key in ("answer", "selection", "hypothesis"):
                if key in args and isinstance(args[key], str):
                    choice = args[key]
                    break

        if not choice:
            if task_type == TaskType.HYPOTHESIS_SELECTION:
                return {"error": "You must provide 'choice' with a hypothesis label (e.g. 'A')."}
            elif task_type == TaskType.COMPARE_INTERVENTIONS:
                return {"error": "You must provide 'choice' with 'A' or 'B'."}
            elif task_type == TaskType.NEXT_BEST_OBSERVATION:
                return {"error": "You must provide 'choice' with a variable name."}
            elif task_type == TaskType.SHOULD_CONDITION:
                return {"error": "You must provide 'choice' with 'yes' or 'no'."}
            else:
                return {"error": "You must provide 'choice' with your answer."}

        result.submitted_answer = choice.strip()
        result.confidence = args.get("confidence")
        result.reasoning = args.get("reasoning")

        return {"status": "submitted", "choice": result.submitted_answer}

    def _submit_intervention(self, args: dict, result: AgentResult) -> dict:
        """Handle intervention submission (best_intervention)."""
        node = args.get("node", "")
        state = args.get("state", "")

        if not node or not state:
            return {
                "error": (
                    "You must provide 'node' (variable name) and 'state' (value). "
                    'Example: {"node": "temperature", "state": "high"}'
                ),
            }

        result.submitted_answer = {"node": node.strip(), "state": state.strip()}
        result.confidence = args.get("confidence")
        result.reasoning = args.get("reasoning")

        return {"status": "submitted", "node": node, "state": state}

    def _submit_variable_set(self, args: dict, result: AgentResult) -> dict:
        """Handle variable set submission (adjustment_set)."""
        not_identifiable = args.get("not_identifiable", False)

        if not_identifiable:
            result.submitted_answer = "_not_identifiable_"
            result.confidence = args.get("confidence")
            result.reasoning = args.get("reasoning")
            return {"status": "submitted", "not_identifiable": True}

        variables = args.get("variables")
        if variables is None:
            return {
                "error": (
                    "You must provide 'variables' (list of variable names to control for). "
                    'Example: {"variables": ["age", "income"]} or {"variables": []}'
                ),
            }

        if not isinstance(variables, list):
            return {"error": "'variables' must be a list of strings."}

        result.submitted_answer = sorted(variables)
        result.confidence = args.get("confidence")
        result.reasoning = args.get("reasoning")

        return {"status": "submitted", "variables": result.submitted_answer}

    def _score_result(
        self,
        result: AgentResult,
        task: Task | None,
        problem: ResearchProblem,
        runner: EpisodeRunner,
    ) -> Score:
        """Score the agent's answer using the appropriate verifier method."""
        verifier = VerifierTool()
        task_type = task.type if task else TaskType.INFER_TARGET

        if task_type in DISTRIBUTION_TYPES:
            # KL divergence scoring
            # Use task.correct_answer when available (e.g. causal_effect has
            # P(target|do(X=x)), infer_latent_cause has P(latent|evidence)).
            # Fall back to runner posterior for infer_target without explicit task.
            if task is not None and task.correct_answer:
                true_posterior = task.correct_answer
            else:
                true_posterior = runner.true_posterior(problem.target_node)
            return verifier.score(
                agent_posterior=result.submitted_answer,
                true_posterior=true_posterior,
                budget_used=result.budget_used,
                budget_total=result.budget_total,
            )

        # For non-distribution types, compute a functional_score and wrap in Score
        score_val = 0.0

        if task_type == TaskType.HYPOTHESIS_SELECTION:
            score_val = verifier.score_hypothesis(
                result.submitted_answer, task.correct_answer
            )
        elif task_type == TaskType.COMPARE_INTERVENTIONS:
            score_val = verifier.score_compare_interventions(
                result.submitted_answer, task.correct_answer
            )
        elif task_type == TaskType.SHOULD_CONDITION:
            score_val = verifier.score_should_condition(
                result.submitted_answer, task.correct_answer
            )
        elif task_type == TaskType.BEST_INTERVENTION:
            score_val = verifier.score_best_intervention(
                result.submitted_answer["node"],
                result.submitted_answer["state"],
                task.correct_answer,
            )
        elif task_type == TaskType.ADJUSTMENT_SET:
            if result.submitted_answer == "_not_identifiable_":
                score_val = 1.0 if "_not_identifiable_" in task.correct_answer else 0.0
            else:
                score_val = verifier.score_adjustment_set(
                    result.submitted_answer, task.correct_answer
                )
        elif task_type == TaskType.NEXT_BEST_OBSERVATION:
            score_val = verifier.score_nbo(
                result.submitted_answer, task.correct_answer
            )

        return Score(
            functional_score=score_val,
            information_efficiency=0.0,
            per_step=[],
            budget_used=result.budget_used,
            budget_total=max(1, result.budget_total),
        )


__all__ = ["AgentResult", "AgentSolver"]
