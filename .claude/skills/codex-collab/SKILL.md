---
name: codex-collab
description: "Workflow for collaborating with Codex (OpenAI) as a critical second opinion via MCP. Use when reviewing changes or debating architecture. ONLY if Codex MCP is available."
disable-model-invocation: true
---

# Codex Collaboration Protocol (SREG)

**PREREQUISITE:** This workflow ONLY applies when `mcp__codex__codex` is available
as an MCP tool. If Codex MCP is not connected, skip all Codex steps entirely and
work normally.

## Role of Codex

Codex is a **critical collaborator**, not an assistant or yes-man.

- Codex should **challenge assumptions**, **find flaws**, and **propose alternatives**
- If Codex just agrees with everything, it's not doing its job — push for genuine critique
- Codex is a different model (OpenAI) with different strengths and blind spots
- The value is in the DISAGREEMENT and DEBATE, not in validation

## When to consult Codex

### MANDATORY:
- **Code review** — After implementation, before presenting to user. Codex reviews
  the diff and finds bugs, over-engineering, missed edge cases, inconsistencies.

### RECOMMENDED (use judgment — don't overuse, Codex takes time):
- **Strategy/next steps** — When deciding what to work on next, how to prioritize,
  or suggesting next steps to the user. Codex may see priorities differently.
- **Design/architecture** — When there are multiple valid approaches and it's not
  clear which is best. "I'm choosing X over Y because Z. Challenge this."
- **Problem-solving** — When stuck or unsure about an approach, a different
  model's perspective can unblock.

### SKIP:
- Routine planning for clear tasks
- Doc-only changes, typos, formatting
- Trivial fixes with obvious solutions
- When the user explicitly says to skip

## How to call Codex

### Thread management
- Start a new thread per work session with `mcp__codex__codex`
- Continue with `mcp__codex__codex-reply` + `threadId`

### Context briefing (CRITICAL)

Codex can read files but does NOT see our conversation with the user. Every call
must include a **context briefing**:

- **What we're working on** — task, goal, why it matters
- **What was decided** — choices made, user preferences, strategy
- **What happened since last call** — if continuing a thread, summarize what
  was implemented, what the user said, what changed

When Codex gives feedback and we don't follow it, tell Codex WHY in the next call.

### Prompt guidelines
- Share relevant context (diffs, design rationale, user decisions)
- **Always ask Codex to be critical**: "Don't just agree — tell me what's wrong"
- For SREG: remind Codex of two-layer architecture (formal BN + semantic) and
  that SREG generates environments, not trains policies

## Integration with SREG commit workflow

```
1. IMPLEMENT — Write code + tests
2. REVIEW    — Codex reviews diff critically (MANDATORY)
3. PRESENT   — Show user: changes + Codex feedback + resolution
4. COMMIT    — Only after user approval
```

## Handling disagreements

- Present BOTH perspectives to the user with reasoning
- Don't silently ignore Codex's critique
- Don't blindly follow it either — evaluate on merit
- The user is the final arbiter
