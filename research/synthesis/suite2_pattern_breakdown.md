# Suite 2 — Per-pattern bucket breakdown (v2, canonical)

> **Status:** CANON post-fix. Replaces the 2026-04-14 upper-bound triage.
> **Source:** `research/synthesis/compiler_baseline_full_dump_v2.json`
> (55 targets, 5 buckets, round-trip-safe dump).
> **Date:** 2026-04-15.
> **Related:** `suite2_compiler_baseline.md` §9 (addendum documenting v1→v2).

## What changed from the upper-bound triage

The first version of this doc was an **upper-bound triage** — v1 only
persisted the 21 verdict_fail entries, so per-pattern cells reported
`max_possible_effective_pass` rather than an actual rate.

v2 persists all 55 targets with their bucket category. This doc now
reports **actual per-bucket counts** per family, regime, and difficulty.

## Headline (v2)

- `strict_full_pass_rate` = 7/55 = **13%** (all 3 stages correct).
- `effective_pass_rate` = 17/55 = **31%** (strict + adjust_swap).
- `real_error_rate` = 38/55 = **69%**.

Nomenclature frozen per I-027 item 6. **Never write "pass rate" without a
prefix.**

## By primary pattern

The first family tag per fact (`fact.families[0]`) is used as
`primary_pattern`.

| Pattern | N | full_pass | adjust_swap | real_struct_err | verdict_wrong | stage1_fail | eff_pass | strict_pass |
|---|---|---|---|---|---|---|---|---|
| CC-A1 | 9 | 0 | 6 | 0 | 3 | 0 | 67% | 0% |
| CC-A3 | 8 | 0 | 0 | 3 | 5 | 0 | 0% | 0% |
| CC-A2 | 5 | 1 | 0 | 4 | 0 | 0 | 20% | 20% |
| SQ-A1 | 3 | 0 | 0 | 3 | 0 | 0 | 0% | 0% |
| CC-A4 | 3 | 0 | 0 | 0 | 3 | 0 | 0% | 0% |
| CC-A5 | 3 | 0 | 0 | 0 | 3 | 0 | 0% | 0% |
| CC-B5 | 3 | 0 | 0 | 0 | 1 | 2 | 0% | 0% |
| CC-C2 | 3 | 0 | 2 | 1 | 0 | 0 | 67% | 0% |
| CC-E2 | 3 | 2 | 0 | 0 | 1 | 0 | 67% | 67% |
| CC-A8 | 2 | 1 | 0 | 1 | 0 | 0 | 50% | 50% |
| CC-A7 | 2 | 0 | 0 | 0 | 2 | 0 | 0% | 0% |
| CC-D1 | 2 | 0 | 2 | 0 | 0 | 0 | 100% | 0% |
| CC-D2 | 2 | 0 | 0 | 1 | 1 | 0 | 0% | 0% |
| CC-E3 | 2 | 0 | 0 | 0 | 0 | 2 | 0% | 0% |
| SQ-A3 | 2 | 2 | 0 | 0 | 0 | 0 | 100% | 100% |
| SQ-C1 | 2 | 1 | 0 | 0 | 0 | 1 | 50% | 50% |
| CC-E1 | 1 | 0 | 0 | 0 | 0 | 1 | 0% | 0% |

### Interpretation

**Zero strict-pass families with non-trivial N (≥3):** CC-A1, CC-A3,
CC-A4, CC-A5, CC-B5, CC-C2, SQ-A1. These are the compiler's weak spots.
Among them:

- **CC-A1 and CC-C2** are "rescued" by adjust_swap — effective pass 67%
  despite strict 0%. These families systematically trigger the
  adjust↔intervene representation mismatch.
- **CC-A3, CC-A4, CC-A5, CC-B5, SQ-A1** are genuine recipe gaps — effective
  pass 0% on 3+ targets each. These are the best targets for recipe
  exemplar work (I-026).

**Strong families:** SQ-A3 (2/2) and CC-E2 (2/3 strict) are the only
families where the compiler works end-to-end. Worth auditing whether
these are "easy" or if the compiler has genuine competence here.

**CC-D1** is a curiosity: 100% effective pass, but 0% strict pass — every
target trips adjust_swap. Consistent with an identifiability-or-contrast
family where the compiler always picks the "wrong but mathematically
equivalent" arm representation.

## By regime

| Regime | N | full_pass | adjust_swap | real_struct_err | verdict_wrong | stage1_fail | eff_pass | strict_pass |
|---|---|---|---|---|---|---|---|---|
| do | 40 | 2 | 10 | 8 | 14 | 6 | 30% | 5% |
| identifiability | 5 | 4 | 0 | 0 | 1 | 0 | 80% | 80% |
| adjusted | 4 | 1 | 0 | 2 | 1 | 0 | 25% | 25% |
| comparative | 3 | 0 | 0 | 0 | 3 | 0 | 0% | 0% |
| observational | 3 | 0 | 0 | 3 | 0 | 0 | 0% | 0% |

### Interpretation

- **`identifiability` dominates strict pass** (4/5 = 80%). The compiler
  correctly produces `IDENTIFIABILITY_CHECK` measurements — possibly
  because that's a relatively rigid recipe with fewer degrees of freedom.
- **`do` is the bulk of the workload** (40/55) and lands at 30% effective.
  The adjust_swap tax (10/40) is large here — this is where the
  intervene↔adjust representation mismatch concentrates.
- **`observational` 100% real_struct_err** (3/3) — the compiler always
  gets verdict right on pure observational claims but structure wrong.
  Classic pass-by-accident territory.
- **`comparative` 100% verdict_wrong** (3/3) — small N, but a clean signal
  that this regime is broken end-to-end.

## By difficulty

| Difficulty | N | full_pass | adjust_swap | real_struct_err | verdict_wrong | stage1_fail | eff_pass | strict_pass |
|---|---|---|---|---|---|---|---|---|
| easy | 14 | 2 | 5 | 3 | 3 | 1 | 50% | 14% |
| medium | 21 | 3 | 5 | 4 | 7 | 2 | 38% | 14% |
| hard | 20 | 2 | 0 | 6 | 9 | 3 | 10% | 10% |

### Interpretation

Monotone decay as expected — but notice that `strict_pass` is flat at
10–14% across difficulties. The easy→hard gradient shows up almost
entirely in `adjust_swap` (which rescues easy/medium but never hard) and
in `verdict_wrong` (which spikes on hard). Strict competence is
difficulty-invariant at current prompt quality.

## By gold status

| Gold status | N | full_pass | adjust_swap | real_struct_err | verdict_wrong | stage1_fail | eff_pass | strict_pass |
|---|---|---|---|---|---|---|---|---|
| compile | 52 | 6 | 10 | 13 | 19 | 4 | 31% | 12% |
| abstain | 3 | 1 | 0 | 0 | 0 | 2 | 33% | 33% |

### Interpretation

Only 3 abstain targets (`W3_F11`, `W3_F12_s{0,1}`, `SQ_F07_s{0,1}` across
surface forms); the compiler correctly abstained only on `SQ_F07_s0`.
`W3_F03_s{0,2}` stage1_fails are **compile targets** on which the
compiler crashed — not abstain mis-decisions (see I-028).

## Zero-strict-pass families (v2)

Families where **no target** crossed all three stages. High-priority for
recipe exemplar design (I-026):

| Family | N | Dominant failure bucket |
|---|---|---|
| CC-A3 | 8 | verdict_wrong (5), real_struct_err (3) |
| CC-A1 | 9 | adjust_swap (6) — but 0 strict |
| CC-A4 | 3 | verdict_wrong (3) |
| CC-A5 | 3 | verdict_wrong (3) |
| SQ-A1 | 3 | real_struct_err (3) |
| CC-B5 | 3 | stage1_fail (2) |
| CC-C2 | 3 | adjust_swap (2) |
| CC-A7 | 2 | verdict_wrong (2) |
| CC-D1 | 2 | adjust_swap (2) |
| CC-D2 | 2 | real_struct_err + verdict_wrong |
| CC-E3 | 2 | stage1_fail (2) |
| CC-E1 | 1 | stage1_fail (1) |

## Next steps implied

1. **Task #11b — audit the now-unblocked IDs** (7 strict + 10
   adjust_swap + 13 real_struct_err). Full IDs enumerated in
   `suite2_compiler_baseline.md` §9.6.
2. **Recipe exemplar priority order** (feeds I-026): SQ-A1 (3), CC-A3
   (8), CC-A5 (3), CC-A4 (3) — families with strict_pass=0% and
   non-trivial N.
3. **Adjust-swap equivalence formalization** — CC-A1 and CC-D1 are
   systematically triggered. Consider encoding adjust↔intervene
   equivalence in `alternative_atoms` instead of treating every instance
   as compiler drift.

## Reproducibility

```bash
conda activate sreg
python scripts/suite2_full_dump_v2.py   # 55 LLM calls, ~6 min
```

Produces `research/synthesis/compiler_baseline_full_dump_v2.json`.
Per-family counts above are regeneratable from that file with
`collections.Counter` over the `category` field joined on
`fact.families[0]`.
