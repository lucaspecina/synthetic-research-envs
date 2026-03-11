---
name: eval
description: Run the SREG environment diagnostic — generator quality control using the REAL system with LLM. NOT unit tests. Validates that environments are well-formed, solvable, and non-trivial. NOTE: this is NOT the real benchmark (that's the transfer experiment — see docs/EXTERNAL_BENCHMARKS.md).
disable-model-invocation: true
---

Run the SREG environment diagnostic: generator quality control on the REAL system.

**CRITICAL DISTINCTION — three levels:**
- Unit tests (`pytest tests/`) = "does the code work?" (isolated, fabricated inputs, no LLM)
- Diagnostic (`/eval`) = "are the environments good?" (real system, real LLM, real pipeline)
- Transfer benchmark (FUTURE) = "does training on SREG improve policies?" (external benchmarks, BEFORE/AFTER)

**This skill runs Level 2 (diagnostic).** It validates that the generator produces
quality environments, but does NOT prove that training on them improves policies.

**The diagnostic ALWAYS uses the real system in its best current implementation.**
No toy worlds, no template shortcuts. If the system uses orchestrator + CasePlan +
rich data + semantics, the diagnostic uses ALL of that.

## What to measure

Run the full pipeline: orchestrator generates cases -> agent solves -> compare with teacher.

**Aggregate metrics (per run):**
- Orchestrator completion rate (did it produce a complete case?)
- WorldCheck pass rate
- Agent submit rate
- KL distribution: mean, median, min, max
- Baseline comparison per eval type (agent vs random)
- Per-eval-type breakdown (if CasePlan has multiple types)
- Budget efficiency

**Failure mode analysis (same run):**
- Cases where agent didn't submit -> why?
- Cases where agent was worse than baseline -> what went wrong?
- Narrative confusion (agent misunderstood the question)
- Trivial cases (solved without observations — ZERO_OBS)
- Impossible cases (couldn't solve even with full budget)
- Format errors (submit format wrong, tool call errors)
- Leakage/shortcuts (inferred answer without investigating)

## How to run

1. Parse arguments: $ARGUMENTS may specify number of cases, goals, depth level.
   Defaults: 10 cases, varied goals, full depth.

2. For each case:
   a. Run `Orchestrator().run(goal)` with a varied goal and seed
   b. Verify the case is complete (world + problem + CasePlan + tasks)
   c. Compute structural metrics (WorldCheck, entropy, budget ratio)
   d. Run `AgentSolver().solve(world, problem)`
   e. Extract agent trajectory (`extract_agent_trajectory()`)
   f. Generate teacher trajectory (`generate_teacher_trajectory()`)
   g. Compare (`compare_trajectories()`)
   h. Record metrics, failure modes, and baseline comparison

3. Print aggregate metrics table.

4. Print failure mode analysis: counts, proportions, examples.

5. Save results to `experiments/` with timestamp.

6. Compare with previous diagnostic run if available.

## Goals to vary

Use diverse goals to test different aspects of the system:
- Different domains: marine ecology, epidemiology, materials science, agriculture
- Different sizes: 6, 8, 10, 12 nodes
- Different difficulties: "easy", "medium", "hard"
- Different eval type emphasis: "focus on causal questions", "diagnostic problem"

## Key imports

```python
from sreg.orchestrator.orchestrator import Orchestrator
from sreg.agent.agent import AgentSolver
from sreg.harness.agent_trajectory import extract_agent_trajectory
from sreg.harness.trajectory import generate_teacher_trajectory
from sreg.harness.comparison import compare_trajectories
from sreg.tools.world_check import WorldCheckTool
from sreg.solver.exact_bayes import ExactBayesSolver
```
