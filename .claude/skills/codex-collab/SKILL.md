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
- **But Claude leads.** Codex advises, Claude decides. Don't defer blindly.

## When to consult Codex

### MANDATORY:
- **Code review** — After implementation, before presenting to user. Codex reviews
  the diff and finds bugs, over-engineering, missed edge cases, inconsistencies.

### RECOMMENDED (use judgment — don't overuse, Codex takes time):
- **Pre-implementation strategy** — When a task involves significant design decisions,
  consider presenting the approach to Codex before coding. Can catch issues early.
  Use judgment — not every task needs this.
- **Strategy/next steps** — When deciding what to work on next or how to prioritize.
- **Design/architecture** — When there are multiple valid approaches and it's not
  clear which is best.
- **Problem-solving** — When stuck or unsure, a different perspective can unblock.

### SKIP:
- Routine planning for clear, straightforward tasks
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
- **Always ask for SHORT, CONCISE responses**: "Be brief and direct. No repetition,
  no filler. Bullet points over paragraphs." GPT tends verbose — save time.
- Share relevant context (diffs, design rationale, user decisions)
- **Always ask Codex to be critical**: "Don't just agree — tell me what's wrong"
- For SREG: remind Codex of two-layer architecture (formal BN + semantic) and
  that SREG generates environments, not trains policies

## Integration with SREG commit workflow

```
1. ANALYZE   — Understand the problem
2. STRATEGY  — For non-trivial tasks: propose approach, consult Codex (RECOMMENDED)
3. IMPLEMENT — Write code + tests
4. REVIEW    — Codex reviews diff critically (MANDATORY, one round only)
5. PRESENT   — Show user: changes + Codex feedback + resolution
6. COMMIT    — Only after user approval
```

## Claude leads, Codex advises (CRITICAL)

Codex's role is to be critical, so it will ALWAYS find something to flag.
That's by design. Use good judgment to avoid infinite review loops.

**Guidelines:**
- **Fix what matters.** Bugs, correctness issues, security = fix. Style nits,
  theoretical edge cases, "could be slightly better" = note as deuda, move on.
- **Claude decides.** Codex advises, Claude evaluates on merit and decides what
  to act on. Don't defer blindly — if a finding is minor or disproportionate, skip it.
- **Use judgment on review rounds.** Sometimes one round is enough, sometimes a
  follow-up is warranted for a serious finding. But don't chase diminishing returns.
- **Time matters.** Perfection is the enemy of progress. Ship and iterate.
- **Log deuda, don't block.** Valid but non-urgent findings → mention to the user
  as "deuda conocida" and move on.

## Handling disagreements

- Present BOTH perspectives to the user with reasoning
- Don't silently ignore Codex's critique
- Don't blindly follow it either — evaluate on merit
- The user is the final arbiter
