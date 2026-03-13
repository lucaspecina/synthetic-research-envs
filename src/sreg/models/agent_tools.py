"""Agent toolset definition (provider-agnostic).

Defines which tools the agent can use. The conversion to
provider-specific formats (OpenAI function schemas, etc.)
lives in adapter modules, not here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentTool(BaseModel):
    """One tool available to the agent (domain contract)."""

    name: str
    description: str = ""
    input_schema: dict = Field(default_factory=dict)
    is_terminal: bool = False  # True for submit (ends episode)


class AgentToolset(BaseModel):
    """The complete set of tools available to the agent.

    Same toolset for training, diagnostic, and benchmarks.
    """

    tools: list[AgentTool] = Field(default_factory=list)
    max_tool_calls: int = 8
    version: str = "v1"


# ---------------------------------------------------------------------------
# Canonical tool definitions (domain-level, not provider-specific)
# ---------------------------------------------------------------------------

RESEARCH_ACTION = AgentTool(
    name="research_action",
    description=(
        "Execute a research action from the available list. "
        "Each action has a cost in budget units and returns findings."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "action_id": {
                "type": "string",
                "description": "ID of the action to execute",
            },
        },
        "required": ["action_id"],
    },
)

PYTHON_EXEC = AgentTool(
    name="python_exec",
    description=(
        "Execute Python code to analyze data. "
        "The sandbox has numpy, pandas, scipy, statsmodels available. "
        "The dataset is pre-loaded as `df`. No network access."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            },
        },
        "required": ["code"],
    },
)

# submit is task-specific (schema varies by eval type), so we define
# only the base here. The full schema is built by prompts.build_submit_tool().
SUBMIT = AgentTool(
    name="submit",
    description="Submit your final answer to the research question.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    is_terminal=True,
)

DEFAULT_TOOLSET = AgentToolset(
    tools=[RESEARCH_ACTION, PYTHON_EXEC, SUBMIT],
    max_tool_calls=8,
    version="v1",
)
