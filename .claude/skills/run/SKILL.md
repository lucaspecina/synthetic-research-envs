---
name: run
description: Run the LLM orchestrator to generate a research case. Use to create and inspect cases, analyze quality, and export results.
---

Run the SREG orchestrator to generate a full research case with the LLM.

## What it does

Executes `scripts/test_orchestrator.py` which:
1. Sends a goal to the LLM
2. The LLM designs a causal structure (DAG), applies semantics, designs research questions, builds the problem
3. Shows the full process step by step
4. Shows the case plan (questions, eval types, rationale)
5. Shows the generated tasks with correct answers
6. Shows the research problem (what the agent would see)
7. Optionally exports everything to JSON

## How to run

Parse $ARGUMENTS for optional parameters:
- A topic/domain/goal description (free text)
- `--seed N` for reproducibility
- `--export path` to save JSON

Build and execute the command:

```bash
# From research_seed.md (reads automatically if file exists)
python scripts/test_orchestrator.py

# With a specific goal (ignores seed file)
python scripts/test_orchestrator.py --goal "research problem about [topic], 8 nodes, medium difficulty. Use dag_construct. Design a research case with at least 3 different evaluation types."

# From a different seed file
python scripts/test_orchestrator.py --seed-file my_case.md

# With seed for reproducibility
python scripts/test_orchestrator.py --seed 42

# With export
python scripts/test_orchestrator.py --seed 42 --export output/case_name.json
```

**Goal priority**: `--goal` > `research_seed.md` (if exists) > default (marine ecology)

If $ARGUMENTS is just a topic (e.g., `/run epidemiology`), build a goal like:
```
"Generate a research problem about [topic] in a fictional setting.
Use dag_construct with 8 nodes. Design a research case with at least
3 different evaluation types. Medium difficulty."
```

Always add `--export output/case_YYYYMMDD_HHMMSS.json` with timestamp if no explicit export path given.

## After running

1. **Read the output carefully** — especially the case plan questions and rationale
2. **Analyze the tasks** — do the correct answers make sense? Are the questions interesting?
3. **Check the narrative** — does it feel like a real research scenario?
4. **Report findings** to the user in Spanish:
   - What domain/scenario the LLM chose
   - How many eval types it used and which ones
   - Whether the questions feel like real science or like DAG exercises
   - Any issues (apply_semantics retry, weird naming, etc.)
   - Whether the case would be interesting for an agent to solve

## Key issues to watch for

- `apply_semantics` failing on first call (known bug: LLM sends empty node_renames)
- Questions that feel too generic or don't match the domain
- All actions cost 1 (build_problem doesn't use rich_actions yet)
- Data asset names auto-generated from title (ugly)
- LLM ignoring the seed hint
