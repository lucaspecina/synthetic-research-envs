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
  Write each as a NATURAL LANGUAGE research question. The system will
  automatically compile them into formal verification specs.

### Sub-question format

Each sub-question has:
- **sq_id**: Unique ID (e.g., "sq1", "sq2")
- **text_gloss**: A concrete research question in natural language. Must imply
  a verifiable relationship, mechanism, or estimand. NOT a vague topic.
- **tier**: Importance level:
  - "high" (weight 1.0): core question, central to the brief
  - "medium" (weight 0.6): important but secondary
  - "low" (weight 0.4): peripheral, nice to discover
- **focus_variables** (optional): Variables central to this question.

### What makes a GOOD sub-question

A good SQ is concrete enough that a researcher could design a study to answer it.
It implies a specific relationship, comparison, or estimand — even if phrased
in natural language.

GOOD examples (diverse types):
- "Does X causally increase Y, or is the association driven by confounding from Z?"
- "Which variables have the strongest influence on Y? Rank them."
- "Is the effect of X on Y mediated through M, or is there a direct path?"
- "Does the effect of X on Y differ depending on the level of Z?"
- "What is the observational correlation structure among X, Y, and Z?"
- "Can the causal effect of X on Y be identified from observational data,
  given that Z is unobserved?"
- "Does X affect the variance (not just the mean) of Y?"
- "Among all parents of Y, which has the strongest total causal effect?"

BAD examples (too vague, not verifiable):
- "Investigate the role of X" (no estimand)
- "Understand the system" (not a question)
- "What factors matter?" (too broad, no relationship implied)

### Portfolio rules

- Use 4-6 sub-questions (4 is fine, 7 is too many)
- At least 2-3 should be HIGH tier
- Cover DIVERSE aspects: causal, confounding, mediation, ranking, etc.
- Each HIGH sub-question should be anchored to a deliverable
- The brief should naturally imply the top 2-3 sub-questions

### Do NOT

- Do NOT put specific sub-question details in the brief — keep it vague
- Do NOT create more than 1 near-zero/null-finding sub-question
- Do NOT limit yourself to "does X cause Y" — explore diverse question types
"""


class OrchestratorResult:
    """Result of an orchestrator run."""

    def __init__(self):
        self.world: SCMWorld | None = None
        self.problem: ResearchProblem | None = None
        self.episode: Any = None
        self.oi_mode: bool = False
        self.task: Any = None
        self.attempts: int = 0
        self.validation_passed: bool = False
        self.messages: list[dict] = []
        self.inspiration_manifest: dict | None = None
        self.sub_questions: list | None = None  # list[SubQuestionIntent]
        self.sub_questions_v2: list | None = None  # list[SubQuestionIntentV2]


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
        self._worlds: dict[str, SCMWorld] = {}
        self._case_plans: dict[str, CasePlan] = {}
        self._world_seeds: dict[str, int] = {}
        self._oi_sqs_v2: dict[str, list] = {}  # world_id -> [SubQuestionIntentV2]
        self._world_semantics: dict[str, dict] = {}

        # Convert tool definitions to Responses API format
        self._tools = convert_tools_for_responses(TOOL_DEFINITIONS)

    def _call_text_model(self, system: str, user: str) -> str:
        """Simple text-in/text-out LLM call (no tools).

        Used by the SQ compile step to convert text_gloss -> AtomicSpecs.
        """
        response = self._client.responses.create(
            model=self.model,
            instructions=system,
            input=user,
        )
        # Concatenate all text parts (responses can be multi-part)
        parts: list[str] = []
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        parts.append(part.text)
        return "".join(parts)

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

        # Build lookup maps for validation
        world_node_names = set(world.variables)
        obs_node_names = set(world.observable_variables)

        # Validate research_brief (required for proper separation)
        research_brief = args.get("research_brief", "")
        if not research_brief.strip():
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

        # Build the CasePlan (Pydantic validates structure + duplicates)
        try:
            if self.oi_mode:
                return self._build_oi_case_plan(
                    args, world, world_id, research_brief,
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
            seed = self._world_seeds.get(world_id, 42)
            tasks = self._scm_task_gen.generate_from_plan(
                world, plan, seed=seed
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

    def _compile_oi_subquestions(
        self,
        raw_sqs: list[dict],
        world: SCMWorld,
    ) -> tuple[list, list[str]]:
        """Compile raw SQ dicts (text_gloss) into SubQuestionIntentV2 via LLM.

        Returns (compiled_sqs, errors).
        """
        from sreg.models.open_investigation import SubQuestionIntentV2
        from sreg.tools.oi_compiler import build_world_summary
        from sreg.tools.oi_sq_compiler import compile_sq_to_specs

        # Build world summary for the compiler
        target = world.variables[-1]  # same convention as SCMProblemBuilder
        summary = build_world_summary(world, target)

        compiled: list[SubQuestionIntentV2] = []
        errors: list[str] = []

        for i, raw in enumerate(raw_sqs):
            sq_id = raw.get("sq_id", f"sq{i+1}")
            text_gloss = raw.get("text_gloss", "")
            focus_vars = tuple(raw.get("focus_variables", []))
            tier = SQTier(raw.get("tier", "high"))

            if not text_gloss:
                errors.append(f"{sq_id}: empty text_gloss")
                continue

            logger.info("Compiling SQ %s: %s", sq_id, text_gloss[:80])
            result = compile_sq_to_specs(
                sq_id=sq_id,
                text_gloss=text_gloss,
                focus_variables=focus_vars,
                tier=tier,
                summary=summary,
                llm_call=self._call_text_model,
            )

            if result.success:
                compiled.append(result.sq)
                n_specs = len(result.sq.verification_specs)
                n_req = len(result.sq.required_specs)
                logger.info("  -> OK: %d specs (%d required)", n_specs, n_req)
            else:
                errors.append(f"{sq_id}: {'; '.join(result.errors)}")
                logger.warning("  -> FAIL: %s", result.errors)

        return compiled, errors

    def _build_oi_case_plan(
        self,
        args: dict,
        world: SCMWorld,
        world_id: str,
        research_brief: str,
        obs_node_names: set[str],
        result: OrchestratorResult,
    ) -> dict:
        """Build CasePlan for OI mode: brief + sub-questions v2 (text -> specs)."""
        raw_sqs = args.get("sub_questions", [])

        if not raw_sqs:
            return {
                "error": (
                    "OI mode requires sub_questions (4-6 items). "
                    "Provide sub_questions with sq_id, text_gloss, tier."
                ),
            }

        # Compile text SQs to AtomicSpec bundles via LLM
        compiled_sqs, compile_errors = self._compile_oi_subquestions(
            raw_sqs, world
        )

        min_required = max(2, len(raw_sqs) // 2)
        if len(compiled_sqs) < min_required:
            return {
                "error": (
                    f"Too few sub-questions compiled: {len(compiled_sqs)}/{len(raw_sqs)} "
                    f"(need at least {min_required})"
                ),
                "compile_errors": compile_errors,
                "hint": (
                    "Write more concrete questions that imply a verifiable "
                    "relationship. E.g. 'Does X causally affect Y?' not "
                    "'Investigate the role of X'."
                ),
            }

        # Store v2 SQs in transitional storage
        self._oi_sqs_v2[world_id] = compiled_sqs
        result.sub_questions_v2 = compiled_sqs

        # Build v1 shim SQs ONLY to satisfy CasePlan validator
        # (CasePlan requires questions OR oi_sub_questions non-empty)
        # These are NOT exposed via result.sub_questions to avoid
        # downstream code resolving/scoring against fake variables.
        shim_sqs = []
        for sq_v2 in compiled_sqs:
            shim_sqs.append(SubQuestionIntent(
                sq_id=sq_v2.sq_id,
                pattern="causal_effect",
                roles=SQRoles(treatment="_shim", outcome="_shim"),
                ask=AskOperator.EXISTENCE,
                tier=sq_v2.tier,
                text_gloss=sq_v2.text_gloss,
            ))

        plan = CasePlan(
            title=args.get("title", "Open Investigation"),
            research_context=args.get("research_context", research_brief),
            research_brief=research_brief,
            deliverables=args.get("deliverables", [
                "Investigate the phenomenon described in the brief",
                "Report your findings as structured claims",
            ]),
            oi_sub_questions=shim_sqs,
            shared_budget=args.get("shared_budget", 5),
            rationale=args.get("rationale", "Open Investigation mode"),
        )

        self._case_plans[world_id] = plan

        # Build response
        response: dict = {
            "title": plan.title,
            "research_brief": plan.research_brief,
            "deliverables": plan.deliverables,
            "mode": "open_investigation",
            "num_sub_questions": len(compiled_sqs),
            "sub_question_tiers": {
                sq.sq_id: sq.tier.value for sq in compiled_sqs
            },
            "compiled_specs_per_sq": {
                sq.sq_id: len(sq.verification_specs) for sq in compiled_sqs
            },
        }
        if compile_errors:
            response["compile_warnings"] = compile_errors
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
