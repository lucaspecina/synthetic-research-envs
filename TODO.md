# SREG — TODO

> Single source of truth for task tracking.
> Statuses: `[ ]` pending | `[~]` in progress | `[x]` done | `[-]` cancelled
> Vision and scope: see PROJECT.md

## Done (v0 progress)
- [x] Pydantic data contracts (World, Episode, Task, Score, etc.)
- [x] World generation + validation (latent_preference template, WorldCheckTool)
- [x] Teacher solver (exact Bayesian inference, optimal actions, >90% accuracy)
- [x] Episodes, tasks, verifier, EpisodeRunner
- [x] LLM Orchestrator (world generation via tool calling)
- [x] Semantic layer (names, narrative, data presentation, ResearchProblem)
- [x] LLM Agent solver (observe/submit loop, comparison with teacher/random)
- [x] End-to-end pipeline: orchestrator -> agent -> score (scripts/test_e2e.py)

## Next — Closes v0
- [x] Teacher trajectory export as JSONL (problem, actions, observations, posteriors)
- [x] Batch evaluation: generate N problems programmatically, run agent + teacher, collect metrics
- [x] Summary report: agent vs teacher vs random across difficulty levels
- [ ] Update demo script and notebook
- [ ] Run batch eval across varying parameters (nodes, edge_strength, budget)

## Known issues (from E2E testing, 2026-03-07)
- [ ] Agent submit format: LLM sends flat keys instead of `{"distribution": {...}}`, wastes 1 turn on retry every time
- [ ] Agent worse than random on 8-node worlds: bad inference when more variables are involved (soil case KL 4.21 vs random 0.30)
- [ ] Orchestrator ignores difficulty in goal: always generates "easy" regardless of "hard difficulty" in prompt
- [ ] `apply_semantics` always fails first call: LLM sends empty `node_renames`, then retries correctly (wastes 1 API call)
- [ ] Agent variable selection suboptimal: doesn't pick most informative variables (different order than teacher)

## v1 — More templates + more tasks
- [x] Causal chain template (with semantic layer from start)
- [x] Fork/collider template (with semantic layer from start)
- [x] `next_best_observation` task type
- [ ] `hypothesis_selection` task type
- [ ] Multiple evaluations per problem: same world generates all 3 task types together

## Backlog
- [ ] Synthetic document artifacts (papers, reports, notes)
- [ ] Seeds from real papers (LLM extracts structure)
- [ ] Automatic paper search for seeds
- [ ] Intervention tasks (do-calculus)
- [ ] Structure recovery tasks
- [ ] Complex agent actions (multi-node, conditional)
- [ ] Agent actions defined freely per world (beyond observe)
- [ ] Approximate inference teacher (larger worlds)
- [ ] Curriculum over world complexity
- [ ] RL training loop with verifier as reward
