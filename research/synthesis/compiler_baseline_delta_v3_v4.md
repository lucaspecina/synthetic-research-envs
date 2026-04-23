# Suite 2 Compiler Baseline Delta — v3 vs v4

Targets compared: 55

## Pass rates

| metric | v3 | v4 | Delta (pp) |
|---|---|---|---|
| strict_full_pass_rate | 17/55 (30.9%) | 26/55 (47.3%) | +16.4 |
| effective_pass_rate | 18/55 (32.7%) | 26/55 (47.3%) | +14.5 |

## Bucket distribution

| bucket | v3 | v4 | Delta |
|---|---|---|---|
| full_pass | 17 | 26 | +9 |
| adjust_swap | 1 | 0 | -1 |
| real_struct_err | 18 | 16 | -2 |
| verdict_wrong | 15 | 9 | -6 |
| stage1_fail | 4 | 4 | +0 |

## Transitions: improved=16, regressed=4, same=35

### Improved

| id | v3 | v4 | claim |
|---|---|---|---|
| W1_F03_s0 | real_struct_err | full_pass | Treatment causes side effects. |
| W1_F03_s2 | verdict_wrong | real_struct_err | The treatment faces a trade-off: it improves outcome (effect ~0.7) but causes si |
| W1_F04_s0 | verdict_wrong | real_struct_err | Treatment has a direct effect on outcome beyond its effect through compliance. |
| W1_F04_s1 | real_struct_err | full_pass | Even if compliance were held constant, treatment would still improve outcomes. |
| W1_F05_s0 | real_struct_err | full_pass | Part of treatment's benefit comes through improved compliance. |
| W1_F05_s1 | verdict_wrong | full_pass | Compliance mediates the relationship between treatment and outcome. |
| W1_F05_s2 | stage1_fail | verdict_wrong | The indirect effect of treatment on outcome through compliance is positive but s |
| W1_F06_s0 | verdict_wrong | real_struct_err | The effect of treatment on outcome depends on the patient's biomarker level. |
| W1_F06_s1 | verdict_wrong | full_pass | Patients with high biomarker levels benefit more from treatment than those with  |
| W1_F07_s2 | verdict_wrong | real_struct_err | Severity is a confounder, not a mediator, of the treatment-outcome relationship: |
| W1_F09_s0 | real_struct_err | full_pass | Treated patients show more variable outcomes than untreated patients. |
| W2_F01_s1 | adjust_swap | full_pass | The causal effect of exposure on disease is protective: increasing exposure decr |
| W2_F04_s0 | verdict_wrong | full_pass | Exposure increases disease risk indirectly through the mediator. |
| W2_F04_s1 | verdict_wrong | real_struct_err | The indirect pathway (exposure -> mediator -> disease) works in the opposite dir |
| W2_F09_s1 | verdict_wrong | full_pass | Is the causal effect of exposure on disease identifiable from observational data |
| W3_F04_s0 | verdict_wrong | real_struct_err | Extreme heat creates a significant risk of very poor health outcomes. |

### Regressed

| id | v3 | v4 | claim |
|---|---|---|---|
| W1_F06_s2 | real_struct_err | verdict_wrong | Among patients with biomarker one standard deviation above the mean, the treatme |
| W1_F07_s1 | real_struct_err | verdict_wrong | Without adjusting for severity, the observed association between treatment and o |
| W2_F01_s2 | real_struct_err | verdict_wrong | Intervening to increase exposure by one unit reduces disease risk by approximate |
| W3_F03_s1 | real_struct_err | stage1_fail | The effect of temperature on health changes sharply at a threshold near zero: mi |

## Abstention honesty (gold_status='abstain')

IDs: SQ_F07_s0, SQ_F07_s1, W3_F11_s0, W3_F12_s0, W3_F12_s1

| metric | v3 | v4 |
|---|---|---|
| stage1_ok (compiler correctly abstained) | 5/5 | 5/5 |
| deliberate (honest abstention) | 0 | 0 |
| fallback (lucky — crash/parse fail) | 5 | 5 |
