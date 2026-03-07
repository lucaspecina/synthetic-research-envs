"""LLM Orchestrator: agentic loop for world generation via tool calling."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from sreg.models.task import TaskSpec, TaskType
from sreg.models.world import NodeType, World
from sreg.orchestrator.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.task_gen import TaskGenTool
from sreg.tools.world_check import WorldCheckTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool

logger = logging.getLogger(__name__)


class OrchestratorResult:
    """Result of an orchestrator run."""

    def __init__(self):
        self.world: World | None = None
        self.episode: Any = None
        self.task: Any = None
        self.attempts: int = 0
        self.validation_passed: bool = False
        self.messages: list[dict] = []


class Orchestrator:
    """Orchestrates world generation by driving an LLM through tool calls.

    The LLM proposes world parameters, validates, adjusts if needed,
    then generates episodes and tasks.
    """

    def __init__(
        self,
        model: str | None = None,
        max_iterations: int = 10,
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
        self._worlds: dict[str, World] = {}

    def run(self, goal: str) -> OrchestratorResult:
        """Run the orchestrator with a high-level goal.

        Args:
            goal: Natural language description like
                  "generate a medium-difficulty world about medical diagnosis"
        """
        result = OrchestratorResult()

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": goal},
        ]

        for iteration in range(self.max_iterations):
            logger.info(f"Orchestrator iteration {iteration + 1}")

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
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

            if choice.finish_reason == "stop":
                logger.info("Orchestrator finished (stop)")
                break

            if not message.tool_calls:
                logger.info("No tool calls, finishing")
                break

            # Process tool calls
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                logger.info(f"Tool call: {fn_name}({fn_args})")

                tool_result = self._dispatch_tool(fn_name, fn_args, result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str),
                    }
                )

        result.messages = messages
        return result

    def _dispatch_tool(self, name: str, args: dict, result: OrchestratorResult) -> dict:
        """Execute a tool call and return the result as a dict."""
        try:
            if name == "world_gen":
                return self._handle_world_gen(args, result)
            elif name == "world_check":
                return self._handle_world_check(args, result)
            elif name == "episode_gen":
                return self._handle_episode_gen(args, result)
            elif name == "task_gen":
                return self._handle_task_gen(args, result)
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

    def _handle_world_check(self, args: dict, result: OrchestratorResult) -> dict:
        world_id = args["world_id"]
        world = self._worlds.get(world_id)
        if world is None:
            return {"error": f"World '{world_id}' not found"}

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

        task_type_str = args.get("task_type", "infer_target")
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


__all__ = ["Orchestrator", "OrchestratorResult"]
