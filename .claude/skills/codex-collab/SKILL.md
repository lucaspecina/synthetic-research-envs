---
name: codex-collab
description: "Workflow for collaborating with Codex (OpenAI) as a critical second opinion via MCP. Use when reviewing changes or debating architecture. ONLY if Codex MCP is available."
disable-model-invocation: true
---

# Codex Collaboration Protocol (SREG)

**PREREQUISITE:** This workflow ONLY applies when `mcp__codex__codex` is available
as an MCP tool. If Codex MCP is not connected, skip all Codex steps entirely.

## How to call Codex — base-instructions (NON-NEGOTIABLE)

**EVERY call to `mcp__codex__codex` MUST include `base-instructions`.**

Build the base-instructions by concatenating:
1. **User-level** instructions from `~/.claude/skills/codex-collab/codex-base-instructions.md`
   (general: role, doc hierarchy, communication style)
2. **Project-level** instructions from this skill's `codex-base-instructions.md`
   (SREG-specific: architecture, components, QA levels, review checklist)

Read both files, extract the content between the `---` markers, concatenate them,
and pass as the `base-instructions` parameter.

This ensures Codex ALWAYS knows:
- Its role (critical collaborator, not yes-man)
- The document hierarchy (CLAUDE.md -> PROJECT.md -> CURRENT_STATE.md -> ...)
- The project architecture (two-layer: formal SCM + semantic)
- How to review (alignment with PROJECT.md, trigger table, etc.)

### Thread management — PREFER REPLY OVER NEW SESSIONS
- Start ONE thread per topic/session with `mcp__codex__codex` (includes base-instructions)
- **ALWAYS continue with `mcp__codex__codex-reply` + `threadId`** for follow-up
  questions on the same topic. Codex retains full context — no need to re-explain.
- Only start a NEW thread when the topic is genuinely different or unrelated.
- Save the `threadId` from the first call and reuse it for all follow-ups.
- This avoids redundant context-building and produces better, deeper responses.

### The prompt (task-specific context)
The `prompt` parameter contains ONLY the specific task context:
- What we're working on and why
- What was decided, user preferences
- The diff or design to review
- What happened since last call (if continuing thread)

## When to consult Codex

- **MANDATORY:** Code review after implementation, before presenting to user
- **RECOMMENDED:** Pre-implementation strategy, architecture decisions, when stuck
- **SKIP:** Doc-only, trivial fixes, user says to skip

## SREG-specific review checklist

When Codex reviews SREG code, it should check:
- Alignment with PROJECT.md vision (environments for RL, not training)
- Tasks feel like science, not graph theory exercises
- Rewards are exact (from SCM), not heuristic
- Semantic layer is realistic (or fictional for RL training)
- Doc updates needed (trigger table in CLAUDE.md)

## Claude leads, Codex advises

- Fix bugs and correctness issues. Log style nits as deuda.
- One review round by default. Follow-up only for critical findings.
- Present BOTH perspectives to user when Claude and Codex disagree.
- The user is the final arbiter.
