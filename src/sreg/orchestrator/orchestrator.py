"""LLM Orchestrator: agentic loop for world generation via tool calling."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from sreg.inference.responses_utils import convert_tools_for_responses
from sreg.models.case_plan import CasePlan, EvalQuestionPlan
from sreg.models.dag_spec import DAGNodeSpec, DAGSpec
from sreg.models.research_problem import ResearchProblem
from sreg.models.scm_spec import SCMSpec, SCMVariableSpec
from sreg.models.task import TaskSpec, TaskType
from sreg.models.world import NodeType, World
from sreg.orchestrator.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS
from sreg.tools.data_sampler import DataSamplerConfig
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.scm_problem_builder import SCMProblemBuilder
from sreg.tools.scm_task_gen import SCMTaskGenTool
from sreg.tools.scm_world_gen import SCMWorldGenTool
from sreg.tools.task_gen import TaskGenTool
from sreg.tools.world_check import WorldCheckTool
from sreg.tools.world_gen import CustomWorldGenConfig, WorldGenConfig, WorldGenTool
from sreg.world.dag_generators import (
    generate_erdos_renyi,
    generate_layered,
    generate_preferential_attachment,
    generate_spanning_tree,
)
from sreg.world.expression_compiler import ExpressionError
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)


class OrchestratorResult:
    """Result of an orchestrator run."""

    def __init__(self):
        self.world: World | SCMWorld | None = None
        self.problem: ResearchProblem | None = None
        self.episode: Any = None
        self.task: Any = None
        self.attempts: int = 0
        self.validation_passed: bool = False
        self.messages: list[dict] = []
        self.inspiration_manifest: dict | None = None


class Orchestrator:
    """Orchestrates world generation by driving an LLM through tool calls.

    The LLM proposes world parameters, validates, adjusts if needed,
    then generates episodes and tasks.
    """

    def __init__(
        self,
        model: str | None = None,
        max_iterations: int = 15,
        max_gen_attempts: int = 3,
        client: OpenAI | None = None,
    ):
        self.model = model or os.environ.get("AZURE_MODEL", "gpt-4o")
        self.max_iterations = max_iterations
        self.max_gen_attempts = max_gen_attempts

        if client is not None:
            self._client = client
        else:
            self._client = OpenAI(
                base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
                api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
            )

        self._world_gen = WorldGenTool()
        self._world_check = WorldCheckTool()
        self._episode_gen = EpisodeGenTool()
        self._task_gen = TaskGenTool()
        self._problem_builder = ProblemBuilder()
        self._scm_world_gen = SCMWorldGenTool()
        self._scm_task_gen = SCMTaskGenTool()
        self._scm_problem_builder = SCMProblemBuilder()
        self._worlds: dict[str, World | SCMWorld] = {}
        self._case_plans: dict[str, CasePlan] = {}
        self._world_seeds: dict[str, int] = {}
        self._world_semantics: dict[str, dict] = {}

        # Convert tool definitions to Responses API format
        self._tools = convert_tools_for_responses(TOOL_DEFINITIONS)

    def run(self, goal: str) -> OrchestratorResult:
        """Run the orchestrator with a high-level goal.

        Args:
            goal: Natural language description like
                  "generate a medium-difficulty world about medical diagnosis"
        """
        result = OrchestratorResult()
        messages_log: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": goal},
        ]

        prev_response_id = None

        for iteration in range(self.max_iterations):
            logger.info(f"Orchestrator iteration {iteration + 1}")

            kwargs: dict[str, Any] = {
                "model": self.model,
                "tools": self._tools,
            }

            if prev_response_id is None:
                # First call: include instructions and goal
                kwargs["instructions"] = SYSTEM_PROMPT
                kwargs["input"] = goal
            else:
                # Subsequent calls: chain with previous response
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

            if not tool_calls:
                logger.info("Orchestrator finished (no tool calls)")
                break

            # Process tool calls and build outputs for next round
            self._pending_tool_outputs = []
            for tc in tool_calls:
                fn_name = tc.name
                fn_args = json.loads(tc.arguments)
                logger.info(f"Tool call: {fn_name}({fn_args})")

                tool_result = self._dispatch_tool(fn_name, fn_args, result)

                # Log tool result
                messages_log.append({
                    "role": "tool",
                    "tool_call_id": tc.call_id,
                    "content": json.dumps(tool_result, default=str),
                })

                # Queue for next API call
                self._pending_tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": tc.call_id,
                    "output": json.dumps(tool_result, default=str),
                })

        result.messages = messages_log
        return result

    def _dispatch_tool(self, name: str, args: dict, result: OrchestratorResult) -> dict:
        """Execute a tool call and return the result as a dict."""
        try:
            if name == "world_gen":
                return self._handle_world_gen(args, result)
            elif name == "scm_construct":
                return self._handle_scm_construct(args, result)
            elif name == "dag_generate":
                return self._handle_dag_generate(args, result)
            elif name == "dag_construct":
                return self._handle_dag_construct(args, result)
            elif name == "world_check":
                return self._handle_world_check(args, result)
            elif name == "episode_gen":
                return self._handle_episode_gen(args, result)
            elif name == "task_gen":
                return self._handle_task_gen(args, result)
            elif name == "apply_semantics":
                return self._handle_apply_semantics(args, result)
            elif name == "design_case":
                return self._handle_design_case(args, result)
            elif name == "emit_inspiration_manifest":
                return self._handle_inspiration_manifest(args, result)
            elif name == "build_problem":
                return self._handle_build_problem(args, result)
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {"error": str(e)}

    def _handle_world_gen(self, args: dict, result: OrchestratorResult) -> dict:
        config = WorldGenConfig(
            template_family=args.get("template_family", "latent_preference"),
            num_nodes=args.get("num_nodes", 6),
            num_latent=args.get("num_latent", 1),
            num_states=args.get("num_states", 3),
            edge_strength=args.get("edge_strength", 0.7),
            seed=args.get("seed", 0),
        )

        world = self._world_gen.generate(config)
        self._worlds[world.id] = world
        result.world = world
        result.attempts += 1

        return {
            "world_id": world.id,
            "num_nodes": len(world.nodes),
            "num_edges": len(world.edges),
            "difficulty": world.difficulty.level,
            "nodes": [{"name": n.name, "type": n.type, "states": n.states} for n in world.nodes],
        }

    def _handle_dag_generate(self, args: dict, result: OrchestratorResult) -> dict:
        generator = args.get("generator", "erdos_renyi")
        seed = args.get("seed", 42)
        edge_strength = args.get("edge_strength", 0.7)
        num_latent = args.get("num_latent", 1)
        num_target = args.get("num_target", 1)
        num_states = args.get("num_states", 3)

        generators = {
            "erdos_renyi": lambda: generate_erdos_renyi(
                num_nodes=args.get("num_nodes", 10),
                num_latent=num_latent,
                num_target=num_target,
                num_states=num_states,
                edge_prob=args.get("edge_prob", 0.3),
                seed=seed,
            ),
            "spanning_tree": lambda: generate_spanning_tree(
                num_nodes=args.get("num_nodes", 10),
                num_latent=num_latent,
                num_target=num_target,
                num_states=num_states,
                extra_edge_prob=args.get("extra_edge_prob", 0.1),
                seed=seed,
            ),
            "preferential_attachment": lambda: generate_preferential_attachment(
                num_nodes=args.get("num_nodes", 10),
                num_latent=num_latent,
                num_target=num_target,
                num_states=num_states,
                num_edges_per_node=args.get("num_edges_per_node", 2),
                seed=seed,
            ),
            "layered": lambda: generate_layered(
                num_layers=args.get("num_layers", 4),
                nodes_per_layer=args.get("nodes_per_layer", 3),
                num_latent=num_latent,
                num_target=num_target,
                num_states=num_states,
                inter_layer_prob=args.get("inter_layer_prob", 0.5),
                skip_layer_prob=args.get("skip_layer_prob", 0.1),
                seed=seed,
            ),
        }

        if generator not in generators:
            valid = list(generators.keys())
            return {"error": f"Unknown generator: {generator}. Choose from: {valid}"}

        spec = generators[generator]()
        config = CustomWorldGenConfig(dag_spec=spec, edge_strength=edge_strength, seed=seed)
        world = self._world_gen.generate_custom(config)
        self._worlds[world.id] = world
        result.world = world
        result.attempts += 1

        return {
            "world_id": world.id,
            "generator": generator,
            "num_nodes": len(world.nodes),
            "num_edges": len(world.edges),
            "difficulty": world.difficulty.level,
            "nodes": [
                {"name": n.name, "type": n.type, "states": n.states} for n in world.nodes
            ],
        }

    def _handle_dag_construct(self, args: dict, result: OrchestratorResult) -> dict:
        raw_nodes = args.get("nodes", [])
        raw_edges = args.get("edges", [])
        edge_strength = args.get("edge_strength", 0.7)
        seed = args.get("seed", 42)

        if not raw_nodes:
            return {"error": "nodes list is empty. Provide at least 3 nodes."}
        if not raw_edges:
            return {"error": "edges list is empty. Provide at least one directed edge."}

        try:
            dag_nodes = [
                DAGNodeSpec(
                    name=n["name"],
                    type=NodeType(n["type"]),
                    states=n["states"],
                )
                for n in raw_nodes
            ]
            dag_edges = [(e["from"], e["to"]) for e in raw_edges]
            spec = DAGSpec(nodes=dag_nodes, edges=dag_edges)

            # Extract edge directions (optional)
            edge_directions: dict[tuple[str, str], str] = {}
            for e in raw_edges:
                d = e.get("direction")
                if d in ("positive", "negative"):
                    edge_directions[(e["from"], e["to"])] = d

        except (ValueError, KeyError) as e:
            return {"error": f"Invalid DAG specification: {e}"}

        config = CustomWorldGenConfig(
            dag_spec=spec,
            edge_strength=edge_strength,
            seed=seed,
            edge_directions=edge_directions,
        )
        world = self._world_gen.generate_custom(config)
        self._worlds[world.id] = world
        result.world = world
        result.attempts += 1

        return {
            "world_id": world.id,
            "num_nodes": len(world.nodes),
            "num_edges": len(world.edges),
            "difficulty": world.difficulty.level,
            "nodes": [
                {"name": n.name, "type": n.type, "states": n.states} for n in world.nodes
            ],
        }

    def _handle_scm_construct(self, args: dict, result: OrchestratorResult) -> dict:
        raw_vars = args.get("variables", [])
        raw_edges = args.get("edges", [])
        seed = args.get("seed", 42)

        if not raw_vars:
            return {"error": "variables list is empty. Provide at least 2 variables."}

        try:
            variables = [
                SCMVariableSpec(
                    name=v["name"],
                    role=v["role"],
                    unit=v.get("unit", ""),
                    range=tuple(v["range"]) if v.get("range") else None,
                    description=v.get("description", ""),
                    equation=v["equation"],
                )
                for v in raw_vars
            ]
            edges = [(e["from"], e["to"]) for e in raw_edges]
            spec = SCMSpec(variables=variables, edges=edges)
        except (ValueError, KeyError) as e:
            return {"error": f"Invalid SCM specification: {e}"}

        try:
            world = self._scm_world_gen.generate(spec, seed=seed)
        except (ExpressionError, ValueError) as e:
            return {"error": f"SCM world generation failed: {e}"}

        self._worlds[world.id] = world
        self._world_seeds[world.id] = seed
        result.world = world
        result.attempts += 1

        # Build variable summary for the LLM
        var_info = []
        for v in world.variables:
            meta = world.variable_meta.get(v)
            role = "latent" if v in world.latent_variables else "observable"
            # Find target from the spec
            for sv in raw_vars:
                if sv["name"] == v and sv["role"] == "target":
                    role = "target"
                    break
            info: dict = {"name": v, "role": role}
            if meta and meta.unit:
                info["unit"] = meta.unit
            var_info.append(info)

        return {
            "world_id": world.id,
            "num_variables": len(world.variables),
            "num_edges": len(raw_edges),
            "variables": var_info,
            "validation": "passed (1000 samples: no NaN, no Inf, variance OK)",
            "next_step": (
                "Call apply_semantics to add scenario narrative, "
                "then design_case to define evaluation questions."
            ),
        }

    def _handle_world_check(self, args: dict, result: OrchestratorResult) -> dict:
        world_id = args["world_id"]
        world = self._worlds.get(world_id)
        if world is None:
            return {"error": f"World '{world_id}' not found"}

        # SCMWorld is validated at construction time (NaN, Inf, variance, extremes)
        if isinstance(world, SCMWorld):
            result.validation_passed = True
            return {
                "passed": True,
                "failures": [],
                "metrics": {
                    "num_variables": len(world.variables),
                    "num_edges": sum(len(p) for p in world.graph.values()),
                    "note": "SCM world was validated at construction (sampling check).",
                },
            }

        check = self._world_check.check(world)
        result.validation_passed = check.passed

        return {
            "passed": check.passed,
            "failures": check.failures,
            "metrics": check.metrics,
        }

    def _handle_episode_gen(self, args: dict, result: OrchestratorResult) -> dict:
        world_id = args["world_id"]
        world = self._worlds.get(world_id)
        if world is None:
            return {"error": f"World '{world_id}' not found"}

        budget = args.get("budget", 5)
        config = EpisodeGenConfig(budget=budget, seed=0)
        episode = self._episode_gen.generate(world, config)
        result.episode = episode

        return {
            "episode_id": episode.id,
            "budget": episode.budget,
            "available_nodes": episode.available_nodes,
            "num_initial_evidence": len(episode.initial_evidence),
        }

    def _handle_task_gen(self, args: dict, result: OrchestratorResult) -> dict:
        world_id = args["world_id"]
        world = self._worlds.get(world_id)
        if world is None:
            return {"error": f"World '{world_id}' not found"}

        task_type_str = args.get("task_type", "causal_effect")
        max_budget = args.get("max_budget", 5)

        target_nodes = [n for n in world.nodes if n.type == NodeType.TARGET]
        target = target_nodes[0].name if target_nodes else "target_outcome"

        spec = TaskSpec(
            type=TaskType(task_type_str),
            target_node=target,
            max_budget=max_budget,
        )

        task = self._task_gen.generate(world, spec)
        result.task = task

        return {
            "task_id": task.id,
            "type": task.type,
            "question": task.question,
            "target_node": task.target_node,
            "num_available_evidence": len(task.available_evidence),
        }

    def _handle_apply_semantics(self, args: dict, result: OrchestratorResult) -> dict:
        world_id = args["world_id"]
        world = self._worlds.get(world_id)
        if world is None:
            return {"error": f"World '{world_id}' not found"}

        # SCMWorld: variables already have semantic names from the spec.
        # Just store the narrative metadata for use in build_problem.
        if isinstance(world, SCMWorld):
            semantics = {
                "scenario_title": args.get("scenario_title", ""),
                "scenario_description": args.get("scenario_description", ""),
                "domain": args.get("domain", ""),
                "theoretical_context": args.get("theoretical_context", ""),
            }
            self._world_semantics[world_id] = semantics
            return {
                "world_id": world_id,
                "scenario_title": semantics["scenario_title"],
                "domain": semantics["domain"],
                "variables": [
                    {"name": v, "role": (
                        "latent" if v in world.latent_variables else "observable"
                    )}
                    for v in world.variables
                ],
                "next_step": (
                    "Now call design_case to define evaluation questions, "
                    "then build_problem."
                ),
            }

        # BN World: rename nodes and apply metadata
        node_renames: dict[str, str] = args.get("node_renames", {})
        node_descriptions: dict[str, str] = args.get("node_descriptions", {})
        edge_descriptions: dict[str, str] = args.get("edge_descriptions", {})

        # Auto-complete identity mappings if node_renames is empty or partial.
        world_node_names = {n.name for n in world.nodes}
        if not node_renames:
            node_renames = {n: n for n in world_node_names}

        missing = world_node_names - set(node_renames.keys())
        if missing:
            for m in missing:
                node_renames[m] = m

        world = self._rename_world_nodes(world, node_renames, node_descriptions, edge_descriptions)

        # Apply semantic metadata
        world = world.model_copy(
            update={
                "scenario_title": args.get("scenario_title"),
                "scenario_description": args.get("scenario_description"),
                "domain": args.get("domain"),
                "theoretical_context": args.get("theoretical_context"),
            }
        )

        # Store updated world
        self._worlds[world_id] = world
        result.world = world

        return {
            "world_id": world_id,
            "scenario_title": world.scenario_title,
            "domain": world.domain,
            "nodes_renamed": len(node_renames),
            "nodes": [{"name": n.name, "type": n.type} for n in world.nodes],
            "next_step": "Now call build_problem to sample data and produce the final problem.",
        }

    # Eval types that REQUIRE node hints when used in a CasePlan.
    _HINT_REQUIRED_TYPES: dict[TaskType, list[str]] = {
        TaskType.CAUSAL_EFFECT: ["intervention_node"],
        TaskType.BEST_INTERVENTION: ["desired_state"],
        TaskType.COMPARE_INTERVENTIONS: ["compare_nodes", "desired_state"],
        TaskType.ADJUSTMENT_SET: ["intervention_node"],
        TaskType.SHOULD_CONDITION: ["intervention_node", "condition_variable"],
        TaskType.ATE: ["intervention_node"],
        TaskType.MEDIATION: ["intervention_node", "condition_variable"],
        TaskType.INTERACTION: ["intervention_node", "condition_variable"],
    }

    def _handle_design_case(self, args: dict, result: OrchestratorResult) -> dict:
        world_id = args["world_id"]
        world = self._worlds.get(world_id)
        if world is None:
            return {"error": f"World '{world_id}' not found"}

        is_scm = isinstance(world, SCMWorld)

        # Build lookup maps for validation (polymorphic)
        if is_scm:
            world_node_names = set(world.variables)
            obs_node_names = set(world.observable_variables)
            node_states: dict[str, set[str]] = {}  # SCM has no discrete states
        else:
            world_node_names = {n.name for n in world.nodes}
            obs_node_names = {
                n.name for n in world.nodes if n.type == NodeType.OBSERVABLE
            }
            node_states = {
                n.name: set(n.states) for n in world.nodes
            }

        # Validate research_brief for SCM worlds (required for proper separation)
        research_brief = args.get("research_brief", "")
        if is_scm and not research_brief.strip():
            return {
                "error": (
                    "research_brief is required for SCM worlds. Write a 2-3 paragraph "
                    "research assignment in natural language, WITHOUT naming specific "
                    "model variables or eval types. See 'Brief vs eval separation' in "
                    "the system prompt."
                )
            }

        raw_questions = args.get("questions", [])
        if not raw_questions:
            return {"error": "questions list is empty. Provide at least one question."}

        for i, rq in enumerate(raw_questions):
            target = rq.get("target_node", "")
            if target not in world_node_names:
                return {
                    "error": (
                        f"Question {i}: target_node '{target}' not found in world. "
                        f"Available nodes: {sorted(world_node_names)}"
                    )
                }

            # Validate required hints for node-sensitive eval types
            eval_type_str = rq.get("eval_type", "")
            try:
                eval_type = TaskType(eval_type_str)
            except ValueError:
                continue
            required_hints = self._HINT_REQUIRED_TYPES.get(eval_type, [])
            missing = [h for h in required_hints if not rq.get(h)]
            if missing:
                return {
                    "error": (
                        f"Question {i} ({eval_type_str}): missing required hint(s): "
                        f"{missing}. These are needed so the generated task matches "
                        f"your question text. See tool description for details."
                    )
                }

            # Validate hint node names: must be OBSERVABLE
            for hint_field in ("intervention_node", "condition_variable"):
                hint_val = rq.get(hint_field)
                if hint_val:
                    if hint_val not in world_node_names:
                        return {
                            "error": (
                                f"Question {i}: {hint_field}='{hint_val}' not found "
                                f"in world. Available nodes: {sorted(world_node_names)}"
                            )
                        }
                    if hint_val not in obs_node_names:
                        return {
                            "error": (
                                f"Question {i}: {hint_field}='{hint_val}' must be an "
                                f"observable node (not latent/target). Observable "
                                f"nodes: {sorted(obs_node_names)}"
                            )
                        }
            compare = rq.get("compare_nodes")
            if compare:
                for cn in compare:
                    if cn not in obs_node_names:
                        return {
                            "error": (
                                f"Question {i}: compare_nodes contains '{cn}' which "
                                f"is not an observable node. Available observable "
                                f"nodes: {sorted(obs_node_names)}"
                            )
                        }

            # Validate desired_state against the target node's actual states
            # (skip for SCM — continuous variables have no discrete states)
            desired = rq.get("desired_state")
            if desired and not is_scm:
                valid_states = node_states.get(target, set())
                if desired not in valid_states:
                    return {
                        "error": (
                            f"Question {i}: desired_state='{desired}' is not a valid "
                            f"state of target node '{target}'. Valid states: "
                            f"{sorted(valid_states)}"
                        )
                    }

        # Build the CasePlan (Pydantic validates structure + duplicates)
        try:
            questions = [
                EvalQuestionPlan(
                    question_text=rq["question_text"],
                    eval_type=TaskType(rq["eval_type"]),
                    target_node=rq["target_node"],
                    rationale=rq.get("rationale", ""),
                    intervention_node=rq.get("intervention_node"),
                    desired_state=rq.get("desired_state"),
                    compare_nodes=rq.get("compare_nodes"),
                    condition_variable=rq.get("condition_variable"),
                )
                for rq in raw_questions
            ]
            plan = CasePlan(
                title=args.get("title", ""),
                research_context=args.get("research_context", ""),
                research_brief=args.get("research_brief", ""),
                deliverables=args.get("deliverables", []),
                questions=questions,
                shared_budget=args.get("shared_budget", 5),
                rationale=args.get("rationale", ""),
            )
        except (ValueError, KeyError) as e:
            return {"error": f"Invalid case plan: {e}"}

        # Generate tasks from the plan to validate they are computable
        try:
            if is_scm:
                seed = self._world_seeds.get(world_id, 42)
                tasks = self._scm_task_gen.generate_from_plan(
                    world, plan, seed=seed
                )
            else:
                tasks = self._task_gen.generate_from_plan(
                    world, plan, seed=world.seed
                )
        except Exception as e:
            return {"error": f"Failed to generate tasks from plan: {e}"}

        # Store the plan and tasks
        self._case_plans[world_id] = plan
        result.task = tasks  # list of Task objects

        return {
            "world_id": world_id,
            "title": plan.title,
            "num_questions": len(plan.questions),
            "primary_question": {
                "eval_type": plan.primary_question.eval_type,
                "target_node": plan.primary_question.target_node,
                "question_text": plan.primary_question.question_text,
            },
            "eval_types": sorted(str(t) for t in plan.eval_types),
            "shared_budget": plan.shared_budget,
            "tasks_generated": len(tasks),
            "next_step": "Now call build_problem to sample data and produce the final problem.",
        }

    def _handle_inspiration_manifest(
        self, args: dict, result: OrchestratorResult
    ) -> dict:
        """Store the orchestrator's self-reported inspiration manifest."""
        result.inspiration_manifest = args
        logger.info("Inspiration manifest received")
        return {
            "status": "manifest_recorded",
            "message": "Your inspiration manifest has been recorded. Proceed with build_problem.",
        }

    def _handle_build_problem(self, args: dict, result: OrchestratorResult) -> dict:
        world_id = args["world_id"]
        world = self._worlds.get(world_id)
        if world is None:
            return {"error": f"World '{world_id}' not found"}

        budget = args.get("budget", 5)
        data_format = args.get("data_format", "tabular")
        num_rows = args.get("num_data_rows", 50)
        case_plan = self._case_plans.get(world_id)

        # SCMWorld: use SCMProblemBuilder
        if isinstance(world, SCMWorld):
            semantics = self._world_semantics.get(world_id, {})
            seed = self._world_seeds.get(world_id, 42)

            # Get tasks from result if available
            tasks = result.task if isinstance(result.task, list) else None

            problem = self._scm_problem_builder.build(
                world,
                tasks=tasks,
                budget=budget,
                n_rows=max(num_rows, 200),
                multi_dataset=True,
                case_plan=case_plan,
                seed=seed,
                title=semantics.get("scenario_title"),
                description=semantics.get("scenario_description"),
                domain=semantics.get("domain"),
            )
            result.problem = problem

            return {
                "title": problem.title,
                "domain": problem.domain,
                "budget": problem.budget,
                "research_question": problem.research_question,
                "num_data_assets": len(problem.data_assets),
                "num_actions": len(problem.available_actions),
                "target_node": problem.target_node,
                "target_states": problem.target_states,
            }

        # BN World: use ProblemBuilder
        data_config = DataSamplerConfig(
            num_rows=max(num_rows, 200),  # Minimum 200 rows for realism
            format=data_format,
            seed=world.seed,
            measurement_noise=0.05,  # 5% misclassification on ordinal variables
            missing_rate=0.05,  # 5% MAR missingness
            missing_mechanism="mar",  # Correlated with variable severity
            multi_dataset=True,  # Multiple artifacts with different quality profiles
        )

        problem = self._problem_builder.build(
            world,
            budget=budget,
            data_config=data_config,
            rich_actions=True,
            case_plan=case_plan,
        )
        result.problem = problem

        return {
            "title": problem.title,
            "domain": problem.domain,
            "budget": problem.budget,
            "research_question": problem.research_question,
            "num_data_assets": len(problem.data_assets),
            "num_actions": len(problem.available_actions),
            "target_node": problem.target_node,
            "target_states": problem.target_states,
        }

    @staticmethod
    def _rename_world_nodes(
        world: World,
        renames: dict[str, str],
        descriptions: dict[str, str],
        edge_descs: dict[str, str],
    ) -> World:
        """Create a new World with nodes/edges/CPDs renamed according to the mapping."""
        from sreg.models.world import CPD, Edge, Node

        def r(name: str) -> str:
            return renames.get(name, name)

        new_nodes = [
            Node(
                name=r(n.name),
                type=n.type,
                description=descriptions.get(r(n.name), n.description),
                states=list(n.states),
            )
            for n in world.nodes
        ]

        new_edges = [
            Edge(
                from_node=r(e.from_node),
                to_node=r(e.to_node),
                mechanism=edge_descs.get(f"{r(e.from_node)}->{r(e.to_node)}", e.mechanism),
            )
            for e in world.edges
        ]

        new_cpds = [
            CPD(
                node=r(cpd.node),
                parents=[r(p) for p in cpd.parents],
                table=[list(row) for row in cpd.table],
                state_names={r(k): list(v) for k, v in cpd.state_names.items()},
            )
            for cpd in world.cpds
        ]

        return world.model_copy(
            update={
                "nodes": new_nodes,
                "edges": new_edges,
                "cpds": new_cpds,
            }
        )


__all__ = ["Orchestrator", "OrchestratorResult"]
