### D2 per-family × per-slot accuracy

| family | n | status | n_atoms | arm_kinds | role_vars | meas_kind | comp_kind | assert | top-2 weak | fail rate | bucket mix |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CC-A2 | 5 | 100% | 60% | **0%** | 100% | 0% | 100% | 80% | `arm_kinds` 0%, `measurement_kind` 0% | 80% | real_struct_err=4, full_pass=1 |
| CC-A4 | 3 | 100% | 33% | **0%** | 100% | 100% | 0% | 33% | `arm_kinds` 0%, `comparison_kind` 0% | 100% | verdict_wrong=3 |
| CC-A5 | 3 | 100% | 100% | **0%** | 100% | 0% | 0% | 33% | `arm_kinds` 0%, `measurement_kind` 0% | 100% | verdict_wrong=3 |
| CC-B5 | 3 | 100% | 100% | **0%** | 100% | 100% | 100% | 100% | `arm_kinds` 0%, `n_atoms` 100% | 100% | stage1_fail=2, verdict_wrong=1 |
| CC-E2 | 3 | 66% | 66% | **0%** | 66% | 66% | 66% | 33% | `arm_kinds` 0%, `assertion_polarity` 33% | 33% | full_pass=2, verdict_wrong=1 |
| SQ-A1 | 3 | 100% | 100% | **100%** | 100% | 100% | 100% | 0% | `assertion_polarity` 0%, `n_atoms` 100% | 100% | real_struct_err=3 |
| CC-D2 | 2 | 100% | 100% | **0%** | 100% | 0% | 0% | 0% | `arm_kinds` 0%, `measurement_kind` 0% | 100% | real_struct_err=1, verdict_wrong=1 |
| SQ-A3 | 2 | 100% | 100% | **0%** | 100% | 100% | 100% | 100% | `arm_kinds` 0%, `n_atoms` 100% | 0% | full_pass=2 |
| CC-A7 | 2 | 100% | 100% | **50%** | 100% | 100% | 50% | 0% | `assertion_polarity` 0%, `arm_kinds` 50% | 100% | verdict_wrong=2 |
| CC-A3 | 8 | 100% | 37% | **75%** | 87% | 100% | 37% | 87% | `n_atoms` 37%, `comparison_kind` 37% | 100% | verdict_wrong=5, real_struct_err=3 |
| CC-A8 | 2 | 100% | 50% | **100%** | 100% | 100% | 100% | 100% | `n_atoms` 50%, `arm_kinds` 100% | 50% | full_pass=1, real_struct_err=1 |
| CC-C2 | 3 | 100% | 100% | **66%** | 100% | 66% | 66% | 100% | `arm_kinds` 66%, `measurement_kind` 66% | 100% | adjust_swap=2, real_struct_err=1 |
| CC-A1 | 9 | 100% | 100% | **100%** | 100% | 88% | 100% | 88% | `measurement_kind` 88%, `assertion_polarity` 88% | 100% | adjust_swap=6, verdict_wrong=3 |
| CC-D1 | 2 | 100% | 100% | **100%** | 100% | 100% | 100% | 100% | `n_atoms` 100%, `arm_kinds` 100% | 100% | adjust_swap=2 |
| CC-E3 | 2 | 50% | - | **-** | - | - | - | - | — | 100% | stage1_fail=2 |
| SQ-C1 | 2 | 0% | - | **-** | - | - | - | - | — | 50% | full_pass=1, stage1_fail=1 |
| CC-E1 | 1 | 100% | - | **-** | - | - | - | - | — | 100% | stage1_fail=1 |