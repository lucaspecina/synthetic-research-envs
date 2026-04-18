---
name: prompts
description: Review and improve orchestrator prompts and tool definitions. Use when adding eval types, changing tool behavior, or after analyzing E2E results.
---

Review and improve the orchestrator prompts in `src/sreg/orchestrator/prompts.py`.

## When to use

- After adding a new eval type (must add it to the system prompt guide AND the design_case enum)
- After changing tool behavior (e.g., build_problem now uses CasePlan)
- After E2E analysis reveals the LLM making bad choices (wrong eval type, bad budget, etc.)
- When the user asks to improve prompt quality

## File to edit

`src/sreg/orchestrator/prompts.py` — contains:
- `SYSTEM_PROMPT`: workflow instructions, eval type guide, generation method guide, guidelines
- `TOOL_DEFINITIONS`: JSON schema for each tool (name, description, parameters)

## Best practices for tool descriptions

Following OpenAI and Anthropic best practices:

1. **Description**: 3-4 sentences minimum. Explain what the tool does, what it returns, when to use it, and when NOT to use it. Include preconditions ("call AFTER apply_semantics").

2. **Enum parameters**: Don't just list values — describe what each value means and when to choose it. The LLM reads the description, not just the enum list.

3. **Distinguish similar tools**: If two tools could be confused, explain the difference explicitly. Include "prefer X when..." guidance.

4. **Examples in descriptions**: For complex parameters (node_renames, questions), include concrete examples showing the expected format and good vs bad values.

5. **Error prevention**: If there are known failure modes (apply_semantics with empty node_renames), mention them. "MUST include a mapping for EVERY node."

6. **Connect tools to each other**: Explain the workflow sequence. "Call AFTER world_check and BEFORE build_problem."

## Checklist when adding a new eval type

1. Add to `SYSTEM_PROMPT` "Evaluation types" section:
   - Name and one-line description
   - "Use when..." guidance with a concrete example
   - Scoring method
2. Add to `design_case` tool's `eval_type` enum
3. Add to `design_case` tool's `eval_type` description (the inline guide)
4. Verify the system prompt's eval type count is still correct
5. Run E2E to verify the LLM picks the new type appropriately

## Checklist when changing tool behavior

1. Update the tool's `description` to reflect new behavior
2. Update parameter descriptions if defaults or behavior changed
3. Update `SYSTEM_PROMPT` if the workflow guidance references the changed tool
4. Check that tool preconditions/postconditions still make sense
5. Run E2E to verify the LLM adapts to the new behavior

## After editing

1. Read the full prompts.py and check for consistency
2. Verify all eval types in the enum match the system prompt guide
3. Run `ruff check src/sreg/orchestrator/prompts.py`
4. Report changes to the user in Spanish
