# Reward variance audit — 2026-04-17

**Verdict:** `PASS`

> GRPO has signal. Proceed to H100 setup (#38) and first RL run (#24).

## Configuration

- Config: `configs\smoke_rl.yaml`
- Policy temperature: `0.7`
- N prompts: **3**, G rollouts/prompt: **4** (total rollouts: 12)
- Prompts sampled: ['immunotherapy', 'missing_data', 'policy_equity']
- Wall-clock: 12.6 min

## Aggregate metrics

- `mean_reward`: **0.315**
- `mean_intra_group_std`: **0.197** (95% CI: [0.081, 0.290])
- `submitted_only_mean_std`: **0.056** (across 3 qualifying groups)
- `mean_top1_top2_gap`: **0.063**
- `submit_rate`: **66.7%**
- `pct_zero_variance_groups`: **0.0%**
- `pct_single_reward_groups`: **0.0%**
- `step_count_reward_correlation`: **NaN** (negative = more effort → less reward, smell of penalty bug)

## Gate results

| Gate | Threshold | Passed |
|---|---|---|
| all_rewards_mean_std >= 0.05 | 0.197 | YES |
| submitted_only_mean_std >= 0.03 | 0.056 | YES |
| pct_zero_variance_groups <= 40.0% | 0.0% | YES |

## Stop condition distribution

- `no_tools_called`: 12 (100.0%)

## Per-group detail

| problem_id | n | mean | std | n_unique | submitted | submitted_only_std |
|---|---|---|---|---|---|---|
| immunotherapy | 4 | +0.240 | 0.290 | 3 | 2/4 | 0.001 |
| missing_data | 4 | +0.546 | 0.081 | 4 | 4/4 | 0.081 |
| policy_equity | 4 | +0.161 | 0.220 | 3 | 2/4 | 0.087 |

## Reproducibility

- Git SHA: `8a45728e49f0ae6ce54e21cebcd3dd725890f621` (dirty=True)
- verifiers: `0.1.11`
- Python: `3.11.14`

