"""LLM Agent solver for research problems."""

from sreg.agent.agent import AgentResult, AgentSolver
from sreg.agent.prompts import AGENT_TOOL_DEFINITIONS, build_agent_system_prompt

__all__ = [
    "AGENT_TOOL_DEFINITIONS",
    "AgentResult",
    "AgentSolver",
    "build_agent_system_prompt",
]
