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
    NUMERIC_TYPES,
    build_agent_system_prompt,
    build_agent_tools,
    build_case_system_prompt,
    build_case_tools,
)
from sreg.agent.python_exec import execute_code, make_python_namespace
from sreg.env.episode import EpisodeRunner
from sreg.inference.responses_utils import convert_tools_for_responses
from sreg.models.episode import Action, ActionType, Observation
from sreg.models.research_problem import ResearchProblem
from sreg.models.score import Score
from sreg.models.task import Task, TaskType
from sreg.models.world import World
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.verifier import VerifierTool
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)


class AgentResult:
    """Result of an agent solving a single task."""

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


class CaseResult:
    """Result of an agent solving an entire research case (multiple tasks)."""

    def __init__(self):
        self.task_results: dict[int, AgentResult] = {}  # question_number -> result
        self.observations: list[Observation] = []
        self.budget_used: int = 0
        self.budget_total: int = 0
        self.messages: list[dict] = []


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
        self._python_namespace: dict = {}

    @staticmethod
    def _parse_distribution(raw: Any) -> dict:
        """Parse distribution from args — handles both dict and JSON string."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    @staticmethod
    def _make_solver(world: World | SCMWorld):
        """Create the appropriate solver for the world type."""
        if isinstance(world, SCMWorld):
            from sreg.solver.scm_solver import SCMSolver

            return SCMSolver(world)
        return ExactBayesSolver(world)

    def solve(
        self,
        world: World | SCMWorld,
        problem: ResearchProblem,
        seed: int = 0,
        task: Task | None = None,
        on_step: Callable[[str, dict], None] | None = None,
    ) -> AgentResult:
        """Run the agent on a research problem."""
        result = AgentResult()
        result.budget_total = problem.budget
        result.task_type = task.type if task else TaskType.INFER_TARGET

        # Set up behind-the-scenes infrastructure
        solver = self._make_solver(world)
        true_state = solver.sample_state(seed=seed)

        # EpisodeRunner requires discrete World. For SCMWorld, single-task
        # solve() is not yet supported (needs SCMEpisodeRunner).
        if isinstance(world, SCMWorld):
            raise NotImplementedError(
                "solve() with SCMWorld is not yet supported. "
                "Use solve_case() for multi-task mode instead."
            )

        ep_tool = EpisodeGenTool()
        episode = ep_tool.generate(
            world,
            EpisodeGenConfig(budget=problem.budget, seed=seed),
            available_actions=problem.available_actions,
        )
        runner = EpisodeRunner(world, episode, true_state)

        # Build persistent Python namespace with dataset pre-loaded
        self._python_namespace = make_python_namespace(
            data_assets=problem.data_assets,
            observations={},
        )

        # Build the agent's prompt and tools (task-aware)
        system_prompt = build_agent_system_prompt(problem, task=task)
        tools = convert_tools_for_responses(
            build_agent_tools(task=task, target_states=problem.target_states)
        )

        messages_log: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please analyze the data and solve this research problem."},
        ]

        prev_response_id = None

        for iteration in range(self.max_iterations):
            logger.info(f"Agent iteration {iteration + 1}")

            kwargs: dict[str, Any] = {
                "model": self.model,
                "tools": tools,
            }

            if prev_response_id is None:
                kwargs["instructions"] = system_prompt
                kwargs["input"] = "Please analyze the data and solve this research problem."
            else:
                kwargs["previous_response_id"] = prev_response_id
                kwargs["input"] = self._pending_tool_outputs

            response = self._client.responses.create(**kwargs)
            prev_response_id = response.id

            # Parse output items
            text_content = None
            tool_calls = []
            for item in response.output:
                if item.type == "message":
                    for part in item.content:
                        if hasattr(part, "text"):
                            text_content = (text_content or "") + part.text
                elif item.type == "function_call":
                    tool_calls.append(item)

            # Log assistant message
            msg_dict: dict[str, Any] = {"role": "assistant"}
            if text_content:
                msg_dict["content"] = text_content
            if tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.call_id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in tool_calls
                ]
            messages_log.append(msg_dict)

            # Notify callback about agent thinking
            if on_step and text_content:
                on_step("thinking", {
                    "content": text_content,
                    "iteration": iteration + 1,
                })

            if not tool_calls:
                logger.info("Agent finished without submitting")
                break

            # Process tool calls
            self._pending_tool_outputs = []
            for tc in tool_calls:
                fn_name = tc.name
                fn_args = json.loads(tc.arguments)
                logger.info(f"Agent tool call: {fn_name}({fn_args})")

                tool_result = self._dispatch_tool(
                    fn_name, fn_args, runner, problem, result, task
                )

                # Notify callback about tool result
                if on_step:
                    if "error" in tool_result:
                        on_step("error", {"tool": fn_name, "error": tool_result["error"]})
                    elif fn_name in ("research_action", "observe"):
                        on_step("observe", tool_result)
                    elif fn_name == "python_exec":
                        on_step("python_exec", {"output": tool_result.get("output", "")})
                    elif fn_name == "submit":
                        on_step("submit", tool_result)

                result_str = json.dumps(tool_result, default=str)
                messages_log.append({
                    "role": "tool",
                    "tool_call_id": tc.call_id,
                    "content": result_str,
                })
                self._pending_tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": tc.call_id,
                    "output": result_str,
                })

                # If agent submitted, we're done
                if fn_name == "submit" and "error" not in tool_result:
                    break

            # Check if episode is done
            if runner.is_finished or result.submitted_answer is not None:
                break

        result.messages = messages_log

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
            if name == "think":
                return {"status": "noted", "reasoning": args.get("reasoning", "")}
            elif name == "research_action":
                tool_result = self._handle_research_action(args, runner, problem, result)
                # Sync observations into python namespace
                self._python_namespace["observations"] = dict(runner.evidence)
                return tool_result
            elif name == "observe":
                # Legacy backward compat
                tool_result = self._handle_observe(args, runner, problem, result)
                self._python_namespace["observations"] = dict(runner.evidence)
                return tool_result
            elif name == "python_exec":
                return self._handle_python_exec(args)
            elif name == "submit":
                return self._handle_submit(args, runner, problem, result, task)
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            logger.error(f"Agent tool {name} failed: {e}")
            return {"error": str(e)}

    def _handle_research_action(
        self,
        args: dict,
        runner: EpisodeRunner,
        problem: ResearchProblem,
        result: AgentResult,
    ) -> dict:
        """Handle a research_action tool call (action_id-based dispatch)."""
        action_id = args.get("action_id", "")

        # Validate action_id exists in episode action_defs
        action_map = {ad.id: ad for ad in runner.episode.action_defs}
        if action_id not in action_map:
            available = [ad.id for ad in runner.episode.action_defs]
            return {
                "error": (
                    f"Unknown action '{action_id}'. "
                    f"Available actions: {available}"
                ),
            }

        action_def = action_map[action_id]

        # Check budget
        if action_def.cost > runner.budget_remaining:
            return {
                "error": (
                    f"Insufficient budget: '{action_id}' costs {action_def.cost}, "
                    f"you have {runner.budget_remaining} remaining. "
                    f"You must submit your answer now."
                ),
            }

        # Check not already used
        if action_id in runner._used_action_ids:
            return {"error": f"Action '{action_id}' has already been executed."}

        # Find the matching AvailableAction for its description
        aa_desc = action_id
        for aa in problem.available_actions:
            if aa.id == action_id:
                aa_desc = aa.description
                break

        # Map semantic action type to interaction type
        if action_def.action_type == "intervene":
            action_type = ActionType.INTERVENE
        else:
            action_type = ActionType.OBSERVE

        action = Action(type=action_type, action_id=action_id)
        step_result = runner.step(action)

        # Collect all observations
        all_obs = [step_result.observation]
        if step_result.extra_observations:
            all_obs.extend(step_result.extra_observations)
        result.observations.extend(all_obs)
        result.budget_used = result.budget_total - step_result.remaining_budget

        # Build result with description
        findings = ", ".join(f"{o.node} = {o.state}" for o in all_obs)

        return {
            "action": aa_desc,
            "findings": findings,
            "remaining_budget": step_result.remaining_budget,
            "message": f"Result of '{aa_desc}': {findings}",
        }

    def _handle_python_exec(self, args: dict) -> dict:
        """Handle python_exec tool call — run code in persistent namespace."""
        code = args.get("code", "")
        if not code:
            return {"error": "No code provided."}

        result = execute_code(code, self._python_namespace)
        return {"output": result.output}

    def _handle_observe(
        self,
        args: dict,
        runner: EpisodeRunner,
        problem: ResearchProblem,
        result: AgentResult,
    ) -> dict:
        """Handle an observe tool call (legacy backward compat)."""
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
        result.budget_used = result.budget_total - step_result.remaining_budget

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
        elif task_type in NUMERIC_TYPES:
            return self._submit_numeric(args, result)
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
        if task and task.correct_answer:
            expected_states = list(task.correct_answer.keys())
        else:
            expected_states = list(problem.target_states)

        distribution = self._parse_distribution(args.get("distribution", {}))

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

    def _submit_numeric(self, args: dict, result: AgentResult) -> dict:
        """Handle numeric submission (ATE, mediation)."""
        value = args.get("value")
        if value is None:
            return {
                "error": (
                    "You must provide 'value' (a numeric estimate). "
                    'Example: {"value": 2.35}'
                ),
            }
        if not isinstance(value, (int, float)):
            return {"error": "'value' must be a number."}
        result.submitted_answer = float(value)
        result.confidence = args.get("confidence")
        result.reasoning = args.get("reasoning")
        return {"status": "submitted", "value": result.submitted_answer}

    def _score_result(
        self,
        result: AgentResult,
        task: Task | None,
        problem: ResearchProblem,
        runner: EpisodeRunner | None,
    ) -> Score:
        """Score the agent's answer using the appropriate verifier method."""
        verifier = VerifierTool()
        task_type = task.type if task else TaskType.INFER_TARGET

        if task_type in DISTRIBUTION_TYPES:
            if task is not None and task.correct_answer:
                true_posterior = task.correct_answer
            elif runner is not None:
                true_posterior = runner.true_posterior(problem.target_node)
            else:
                # SCMWorld case mode — tasks always have correct_answer
                true_posterior = {}
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
        elif task_type in NUMERIC_TYPES:
            true_value = task.correct_answer.get("value", 0.0)
            score_val = verifier.score_numeric(result.submitted_answer, true_value)

        return Score(
            functional_score=score_val,
            information_efficiency=0.0,
            per_step=[],
            budget_used=result.budget_used,
            budget_total=max(1, result.budget_total),
        )


    def solve_case(
        self,
        world: World | SCMWorld,
        problem: ResearchProblem,
        tasks: list[Task],
        seed: int = 0,
        on_step: Callable[[str, dict], None] | None = None,
    ) -> CaseResult:
        """Run the agent on a full research case with multiple tasks.

        All tasks share the same episode, budget, and observations.
        The agent receives all questions at once and submits answers
        per question using submit(question=N, ...).
        """
        case_result = CaseResult()
        case_result.budget_total = problem.budget

        # Initialize per-task results
        for i in range(len(tasks)):
            case_result.task_results[i + 1] = AgentResult()
            case_result.task_results[i + 1].budget_total = problem.budget
            case_result.task_results[i + 1].task_type = tasks[i].type

        # Set up environment (one episode for all tasks)
        solver = self._make_solver(world)
        true_state = solver.sample_state(seed=seed)

        # EpisodeRunner requires discrete World — skip it for SCMWorld.
        # In case mode, research_action is disabled anyway (returns error),
        # so the runner only provides budget tracking (unused) and scoring
        # fallback (not needed — SCMTaskGenTool always sets correct_answer).
        runner: EpisodeRunner | None = None
        if not isinstance(world, SCMWorld):
            ep_tool = EpisodeGenTool()
            episode = ep_tool.generate(
                world,
                EpisodeGenConfig(budget=problem.budget, seed=seed),
                available_actions=problem.available_actions,
            )
            runner = EpisodeRunner(world, episode, true_state)

        # Python namespace with dataset
        self._python_namespace = make_python_namespace(
            data_assets=problem.data_assets,
            observations={},
        )

        # Build unified prompt and tools
        system_prompt = build_case_system_prompt(problem, tasks)
        tools = convert_tools_for_responses(build_case_tools())

        messages_log: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please investigate this case and answer all questions."},
        ]

        prev_response_id = None
        n_submitted = 0
        # Nudge threshold: start warning when 25% of iterations remain
        nudge_threshold = max(1, int(self.max_iterations * 0.75))
        deadline_nudged = False
        deadline_msg = None

        for iteration in range(self.max_iterations):
            logger.info(f"Case solver iteration {iteration + 1}")

            kwargs: dict[str, Any] = {
                "model": self.model,
                "tools": tools,
            }

            if prev_response_id is None:
                kwargs["instructions"] = system_prompt
                kwargs["input"] = "Please investigate this case and answer all questions."
            else:
                kwargs["previous_response_id"] = prev_response_id
                kwargs["input"] = self._pending_tool_outputs

            response = self._client.responses.create(**kwargs)
            prev_response_id = response.id

            # Parse output items
            text_content = None
            tool_calls = []
            for item in response.output:
                if item.type == "message":
                    for part in item.content:
                        if hasattr(part, "text"):
                            text_content = (text_content or "") + part.text
                elif item.type == "function_call":
                    tool_calls.append(item)

            # Log assistant message
            msg_dict: dict[str, Any] = {"role": "assistant"}
            if text_content:
                msg_dict["content"] = text_content
            if tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.call_id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in tool_calls
                ]
            messages_log.append(msg_dict)

            if on_step and text_content:
                on_step("thinking", {"content": text_content, "iteration": iteration + 1})

            if not tool_calls:
                # Agent responded with text but no tool calls.
                # If there are unanswered questions, nudge it to use submit tool.
                if n_submitted < len(tasks):
                    unanswered = [
                        i for i in range(1, len(tasks) + 1)
                        if case_result.task_results[i].submitted_answer is None
                    ]
                    nudge = (
                        f"You have {len(unanswered)} unanswered question(s): "
                        f"{unanswered}. You MUST use the `submit` tool (function call) "
                        f"for each one. Do NOT write answers as text -- use the tool."
                    )
                    messages_log.append({"role": "user", "content": nudge})
                    self._pending_tool_outputs = [
                        {"role": "user", "content": nudge}
                    ]
                    continue
                break

            self._pending_tool_outputs = []

            # Proactive deadline nudge: when running low on iterations and
            # there are still unanswered questions, inject a warning AFTER
            # processing tool outputs (below) so the model sees it next turn.
            remaining_iters = self.max_iterations - iteration - 1
            if (
                iteration >= nudge_threshold
                and not deadline_nudged
                and n_submitted < len(tasks)
            ):
                unanswered = [
                    i for i in range(1, len(tasks) + 1)
                    if case_result.task_results[i].submitted_answer is None
                ]
                deadline_msg = (
                    f"DEADLINE WARNING: You have only {remaining_iters} iteration(s) "
                    f"left and {len(unanswered)} unanswered question(s): {unanswered}. "
                    f"Stop analyzing and submit your best answers NOW using the "
                    f"`submit` tool. Use your current analysis -- do not start new "
                    f"computations. Submit one answer per tool call."
                )
                deadline_nudged = True
                # This will be appended to pending_tool_outputs after processing
            for tc in tool_calls:
                fn_name = tc.name
                fn_args = json.loads(tc.arguments)
                logger.info(f"Case solver tool call: {fn_name}({fn_args})")

                tool_result = self._dispatch_case_tool(
                    fn_name, fn_args, runner, problem, tasks, case_result,
                )

                if on_step:
                    if "error" in tool_result:
                        on_step("error", {"tool": fn_name, "error": tool_result["error"]})
                    elif fn_name in ("research_action", "observe"):
                        on_step("observe", tool_result)
                    elif fn_name == "python_exec":
                        on_step("python_exec", {"output": tool_result.get("output", "")})
                    elif fn_name == "submit":
                        on_step("submit", tool_result)

                result_str = json.dumps(tool_result, default=str)
                messages_log.append({
                    "role": "tool",
                    "tool_call_id": tc.call_id,
                    "content": result_str,
                })
                self._pending_tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": tc.call_id,
                    "output": result_str,
                })

                if fn_name == "submit" and "error" not in tool_result:
                    n_submitted += 1

            # Stop when all questions answered
            if n_submitted >= len(tasks):
                break

            # Inject deadline nudge after tool outputs if triggered this iteration
            if deadline_nudged and deadline_msg:
                messages_log.append({"role": "user", "content": deadline_msg})
                self._pending_tool_outputs.append(
                    {"role": "user", "content": deadline_msg}
                )
                deadline_msg = None  # Only inject once

        case_result.messages = messages_log
        if runner is not None:
            case_result.budget_used = problem.budget - runner.budget_remaining
            case_result.observations = list(runner.evidence.items())
        else:
            case_result.budget_used = 0
            case_result.observations = []

        # Score each submitted task
        for q_num, task in enumerate(tasks, 1):
            tr = case_result.task_results[q_num]
            tr.budget_used = case_result.budget_used
            if tr.submitted_answer is not None:
                tr.score = self._score_result(tr, task, problem, runner)

        return case_result

    def _dispatch_case_tool(
        self,
        name: str,
        args: dict,
        runner: EpisodeRunner,
        problem: ResearchProblem,
        tasks: list[Task],
        case_result: CaseResult,
    ) -> dict:
        """Dispatch tool calls in multi-task case mode."""
        try:
            if name == "think":
                return {"status": "noted", "reasoning": args.get("reasoning", "")}
            elif name == "research_action":
                return {
                    "error": (
                        "research_action is not available. "
                        "Use python_exec to analyze the datasets directly."
                    )
                }
            elif name == "python_exec":
                return self._handle_python_exec(args)
            elif name == "submit":
                return self._handle_case_submit(args, tasks, case_result)
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            logger.error(f"Case tool {name} failed: {e}")
            return {"error": str(e)}

    def _handle_case_submit(
        self,
        args: dict,
        tasks: list[Task],
        case_result: CaseResult,
    ) -> dict:
        """Handle submit in multi-task mode -- routes by question number."""
        q_num = args.get("question")
        if q_num is None:
            return {"error": "You must provide 'question' (the question number, e.g. 1)."}

        if not isinstance(q_num, int) or q_num < 1 or q_num > len(tasks):
            return {
                "error": f"Invalid question number {q_num}. Must be 1-{len(tasks)}."
            }

        task = tasks[q_num - 1]
        tr = case_result.task_results[q_num]

        if tr.submitted_answer is not None:
            return {"error": f"Question {q_num} was already answered."}

        task_type = task.type

        # Extract the answer based on task type
        if task_type in DISTRIBUTION_TYPES:
            distribution = self._parse_distribution(args.get("distribution", {}))
            if not distribution:
                if task.correct_answer:
                    state_set = set(task.correct_answer.keys())
                    top_level = {
                        k: v for k, v in args.items()
                        if k in state_set and isinstance(v, (int, float))
                    }
                    if top_level:
                        distribution = top_level
            if not distribution:
                states = list(task.correct_answer.keys()) if task.correct_answer else []
                return {
                    "error": (
                        f"Question {q_num} needs a distribution. "
                        f"Keys: {', '.join(states)}"
                    ),
                }
            # Validate keys match expected states
            if task.correct_answer:
                expected = set(task.correct_answer.keys())
                provided = set(distribution.keys())
                if provided != expected:
                    return {
                        "error": (
                            f"Distribution keys must match target states. "
                            f"Expected: {sorted(expected)}, got: {sorted(provided)}"
                        ),
                    }
            total = sum(distribution.values())
            if total > 0:
                distribution = {k: v / total for k, v in distribution.items()}
            tr.submitted_answer = distribution

        elif task_type in CHOICE_TYPES or task_type == TaskType.NEXT_BEST_OBSERVATION:
            choice = args.get("choice", "")
            if not choice:
                return {"error": f"Question {q_num} needs a 'choice'."}
            tr.submitted_answer = choice.strip()

        elif task_type == TaskType.BEST_INTERVENTION:
            node = args.get("node", "")
            state = args.get("state", "")
            if not node or not state:
                return {"error": f"Question {q_num} needs 'node' and 'state'."}
            tr.submitted_answer = {"node": node.strip(), "state": state.strip()}

        elif task_type == TaskType.ADJUSTMENT_SET:
            variables = args.get("variables")
            if variables is None:
                return {"error": f"Question {q_num} needs 'variables' (list)."}
            tr.submitted_answer = sorted(variables)

        elif task_type in NUMERIC_TYPES:
            value = args.get("value")
            if value is None:
                return {"error": f"Question {q_num} needs a 'value' (numeric)."}
            if not isinstance(value, (int, float)):
                return {"error": f"Question {q_num}: 'value' must be a number."}
            tr.submitted_answer = float(value)

        else:
            # Fallback to distribution
            distribution = self._parse_distribution(args.get("distribution", {}))
            if distribution:
                total = sum(distribution.values())
                if total > 0:
                    distribution = {k: v / total for k, v in distribution.items()}
                tr.submitted_answer = distribution
            else:
                return {"error": f"Could not parse answer for question {q_num}."}

        tr.confidence = args.get("confidence")
        tr.reasoning = args.get("reasoning")

        answered = sum(1 for r in case_result.task_results.values() if r.submitted_answer is not None)
        remaining = len(case_result.task_results) - answered

        return {
            "status": "submitted",
            "question": q_num,
            "message": (
                f"Answer for question {q_num} recorded. "
                f"{remaining} question(s) remaining."
            ),
        }


__all__ = ["AgentResult", "AgentSolver", "CaseResult"]
