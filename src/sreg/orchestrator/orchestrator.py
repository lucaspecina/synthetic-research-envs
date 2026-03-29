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
from sreg.models.open_investigation import (
    AskOperator,
    SQRoles,
    SQTier,
    SubQuestionIntent,
)
from sreg.models.research_problem import ResearchProblem
from sreg.models.scm_spec import SCMSpec, SCMVariableSpec
from sreg.models.task import TaskType
from sreg.models.world import NodeType, World
from sreg.orchestrator.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS
from sreg.tools.scm_problem_builder import SCMProblemBuilder
from sreg.tools.scm_task_gen import SCMTaskGenTool
from sreg.tools.scm_world_gen import SCMWorldGenTool
from sreg.world.expression_compiler import ExpressionError
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)

# OI mode prompt appended to SYSTEM_PROMPT when oi_mode=True
OI_MODE_PROMPT = """

## OPEN INVESTIGATION MODE

You are generating a world for OPEN INVESTIGATION. The solver investigates
freely and submits claims — there are no predefined questions.

### Pipeline

scm_construct -> world_check -> apply_semantics -> design_case -> build_problem

### design_case in OI mode

Call design_case with these fields:
- **research_brief**: A real research assignment a PI would write. Broad,
  natural language. Does NOT name specific variables or analysis methods.
  Example: "Investigate the factors affecting patient recovery after treatment.
  Identify the most important mechanisms and any confounding relationships."
- **deliverables**: 3-5 action items the investigator should deliver.
- **sub_questions**: 4-6 hidden sub-questions that define the scoring agenda.
  The solver NEVER sees these — they are used for evaluation only.
  Use any pattern that fits the research question. The system is general —
  all patterns (causal_effect, observational_association, mediation,
  confounding, heterogeneity, effect_ranking) work for any world.

### Sub-question format

Each sub-question has:
- **sq_id**: Unique ID (e.g., "sq1", "sq2")
- **pattern**: What type of finding this is about:
  - "causal_effect": does X causally affect Y?
  - "mediation": does the effect go through M?
  - "confounding": does Z confound the X-Y relationship?
  - "heterogeneity": does the effect of X on Y depend on Z?
  - "observational_association": are X and Y associated? (observational only)
  - "effect_ranking": which variables matter most for Y?
  - "tail_risk": does X affect extreme values of Y?
- **roles**: Which variables fill which role:
  - treatment: the cause/exposure variable
  - outcome: the effect/response variable
  - mediator: intermediate variable (for mediation)
  - modifier: effect modifier (for heterogeneity)
  - confounder: confounding variable (for confounding)
  - ranking_vars: list of variables to rank (for effect_ranking)
- **ask**: What aspect to evaluate:
  - "existence": does the effect exist?
  - "sign": is it positive or negative?
  - "existence_and_sign": both existence and direction
  - "magnitude": how large is it?
  - "rank_order": which is larger? (for effect_ranking)
- **tier**: How important this sub-question is:
  - "high" (weight 1.0): core question, central to the brief
  - "medium" (weight 0.6): important but secondary
  - "low" (weight 0.4): peripheral, nice to discover

### Portfolio rules

- Use 4-6 sub-questions (4 is fine, 7 is too many)
- At least 2-3 should be HIGH tier
- At least 2 different patterns
- Each HIGH sub-question should be anchored to a deliverable
- The brief should naturally imply the top 2-3 sub-questions

### Do NOT

- Do NOT put specific sub-question details in the brief — keep it vague
- Do NOT create more than 1 near-zero/null-finding sub-question
"""


class OrchestratorResult:
    """Result of an orchestrator run."""

    def __init__(self):
        self.world: World | SCMWorld | None = None
        self.problem: ResearchProblem | None = None
        self.episode: Any = None
        self.oi_mode: bool = False
        self.task: Any = None
        self.attempts: int = 0
        self.validation_passed: bool = False
        self.messages: list[dict] = []
        self.inspiration_manifest: dict | None = None
        self.sub_questions: list | None = None  # list[SubQuestionIntent]


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
        oi_mode: bool = False,
    ):
        self.model = model or os.environ.get("AZURE_MODEL", "gpt-4o")
        self.max_iterations = max_iterations
        self.max_gen_attempts = max_gen_attempts
        self.oi_mode = oi_mode

        if client is not None:
            self._client = client
        else:
            self._client = OpenAI(
                base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
                api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
            )

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

        # In OI mode, append instructions to skip task/question generation
        effective_prompt = SYSTEM_PROMPT
        effective_goal = goal
        if self.oi_mode:
            effective_prompt += OI_MODE_PROMPT

        messages_log: list[dict] = [
            {"role": "system", "content": effective_prompt},
            {"role": "user", "content": effective_goal},
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
                kwargs["instructions"] = effective_prompt
                kwargs["input"] = effective_goal
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
        result.oi_mode = self.oi_mode
        return result

    def _dispatch_tool(self, name: str, args: dict, result: OrchestratorResult) -> dict:
        """Execute a tool call and return the result as a dict."""
        try:
            if name == "scm_construct":
                return self._handle_scm_construct(args, result)
            elif name == "world_check":
                return self._handle_world_check(args, result)
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
            # Legacy compat: treat "target" as "observable" (OI uses SQ roles)
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

    def _handle_apply_semantics(self, args: dict, result: OrchestratorResult) -> dict:
        world_id = args["world_id"]
        world = self._worlds.get(world_id)
        if world is None:
            return {"error": f"World '{world_id}' not found"}

        # SCMWorld: variables already have semantic names from the spec.
        # Just store the narrative metadata for use in build_problem.
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

    # Eval types that REQUIRE node hints when used in a CasePlan.
    _HINT_REQUIRED_TYPES: dict[TaskType, list[str]] = {
        TaskType.CAUSAL_EFFECT: ["intervention_node"],
        TaskType.BEST_INTERVENTION: [],
        TaskType.COMPARE_INTERVENTIONS: ["compare_nodes"],
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
        if not raw_questions and not self.oi_mode:
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
            if self.oi_mode:
                return self._build_oi_case_plan(
                    args, world, world_id, is_scm, research_brief,
                    obs_node_names, result,
                )

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

    def _build_oi_case_plan(
        self,
        args: dict,
        world: World | SCMWorld,
        world_id: str,
        is_scm: bool,
        research_brief: str,
        obs_node_names: set[str],
        result: OrchestratorResult,
    ) -> dict:
        """Build CasePlan for OI mode: brief + sub-questions, no eval questions."""
        raw_sqs = args.get("sub_questions", [])
        # epistemic_regime removed — system is general, no type-based filtering

        if not raw_sqs:
            return {
                "error": (
                    "OI mode requires sub_questions (4-6 items). "
                    "Provide sub_questions with pattern, roles, ask, tier "
                    "for each investigation agenda item."
                ),
            }

        # Parse SubQuestionIntents from raw dicts
        parsed_sqs: list[SubQuestionIntent] = []
        parse_errors: list[str] = []
        for i, raw in enumerate(raw_sqs):
            try:
                # Build SQRoles from raw dict
                raw_roles = raw.get("roles", {})
                roles = SQRoles(
                    treatment=raw_roles.get("treatment"),
                    outcome=raw_roles.get("outcome"),
                    mediator=raw_roles.get("mediator"),
                    modifier=raw_roles.get("modifier"),
                    confounder=raw_roles.get("confounder"),
                    ranking_vars=raw_roles.get("ranking_vars", []),
                    conditioning_set=raw_roles.get("conditioning_set", []),
                )
                sq = SubQuestionIntent(
                    sq_id=raw.get("sq_id", f"sq{i+1}"),
                    pattern=raw.get("pattern", ""),
                    roles=roles,
                    ask=AskOperator(raw.get("ask", "existence")),
                    tier=SQTier(raw.get("tier", "high")),
                    materiality_threshold=raw.get("materiality_threshold"),
                    text_gloss=raw.get("text_gloss"),
                )
                parsed_sqs.append(sq)
            except (ValueError, KeyError) as e:
                parse_errors.append(f"sub_question[{i}]: {e}")

        if parse_errors:
            return {"error": f"Invalid sub-questions: {'; '.join(parse_errors)}"}

        # Validate against world
        if parsed_sqs and is_scm:
            from sreg.tools.oi_subquestions import validate_sub_questions

            accepted, val_errors = validate_sub_questions(
                parsed_sqs, world
            )
            hard_errors = [
                e for e in val_errors if e.get("severity") == "hard"
            ]
            if hard_errors:
                return {
                    "error": "Sub-question validation failed",
                    "validation_errors": hard_errors,
                    "accepted_sq_ids": [sq.sq_id for sq in accepted],
                    "hint": (
                        "Fix or remove rejected SQs and retry. "
                        "Accepted SQs can be kept as-is."
                    ),
                }

        # Build CasePlan with sub-questions (no eval questions)
        plan = CasePlan(
            title=args.get("title", "Open Investigation"),
            research_context=args.get("research_context", research_brief),
            research_brief=research_brief,
            deliverables=args.get("deliverables", [
                "Investigate the phenomenon described in the brief",
                "Report your findings as structured claims",
            ]),
            oi_sub_questions=parsed_sqs if parsed_sqs else None,
            # epistemic_regime removed from CasePlan
            shared_budget=args.get("shared_budget", 5),
            rationale=args.get("rationale", "Open Investigation mode"),
        )

        self._case_plans[world_id] = plan
        result.sub_questions = parsed_sqs if parsed_sqs else None

        response: dict = {
            "title": plan.title,
            "research_brief": plan.research_brief,
            "deliverables": plan.deliverables,
            "mode": "open_investigation",
            "mode": "open_investigation",
        }
        if parsed_sqs:
            response["num_sub_questions"] = len(parsed_sqs)
            response["sub_question_patterns"] = sorted(
                {sq.pattern for sq in parsed_sqs}
            )
            response["sub_question_tiers"] = {
                sq.sq_id: sq.tier.value for sq in parsed_sqs
            }
        response["next_step"] = (
            "Now call build_problem to sample data and produce the final problem."
        )
        return response

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
        num_rows = args.get("num_data_rows", 50)
        case_plan = self._case_plans.get(world_id)

        from sreg.world.scm_data import PanelConfig

        semantics = self._world_semantics.get(world_id, {})
        seed = self._world_seeds.get(world_id, 42)

        # Get tasks from result if available (skip in OI mode)
        tasks = None
        if not self.oi_mode:
            tasks = result.task if isinstance(result.task, list) else None

        effective_rows = max(num_rows, 200)
        # Vary panel structure per SRC for realism (A18)
        import numpy as _np  # noqa: E402

        _panel_rng = _np.random.default_rng(seed)
        _n_sites = int(_panel_rng.integers(3, 16))  # 3-15 sites
        _n_waves = int(_panel_rng.choice([2, 3, 3, 4, 5]))  # 2-5, mode=3
        _n_proxy = int(_panel_rng.choice([1, 2, 2, 3]))  # 1-3 proxies
        _dropout = round(float(_panel_rng.uniform(0.05, 0.15)), 2)
        panel_config = PanelConfig(
            n_sites=_n_sites,
            n_waves=_n_waves,
            n_proxy_columns=_n_proxy,
            dropout_rate=_dropout,
            seed=seed,
        )

        problem = self._scm_problem_builder.build(
            world,
            tasks=tasks,
            budget=budget,
            n_rows=effective_rows,
            multi_dataset=True,
            case_plan=case_plan,
            seed=seed,
            title=semantics.get("scenario_title"),
            description=semantics.get("scenario_description"),
            domain=semantics.get("domain"),
            panel=panel_config,
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



__all__ = ["Orchestrator", "OrchestratorResult"]
