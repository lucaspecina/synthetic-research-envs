# Suite 2 Compiler Baseline Delta — v2 vs v3

Targets compared: 55

## Pass rates

| metric | v2 | v3 | Delta (pp) |
|---|---|---|---|
| strict_full_pass_rate | 7/55 (12.7%) | 17/55 (30.9%) | +18.2 |
| effective_pass_rate | 17/55 (30.9%) | 18/55 (32.7%) | +1.8 |

## Bucket distribution

| bucket | v2 | v3 | Delta |
|---|---|---|---|
| full_pass | 7 | 17 | +10 |
| adjust_swap | 10 | 1 | -9 |
| real_struct_err | 13 | 18 | +5 |
| verdict_wrong | 19 | 15 | -4 |
| stage1_fail | 6 | 4 | -2 |

## Transitions: improved=17, regressed=6, same=32

### Improved

| id | v2 | v3 | claim |
|---|---|---|---|
| SQ_F07_s1 | stage1_fail | full_pass | What treatment level maximizes outcome while minimizing side effects? |
| W1_F01_s0 | adjust_swap | full_pass | Treatment has a positive causal effect on outcome. |
| W1_F01_s1 | adjust_swap | full_pass | Intervening to increase treatment dosage improves patient outcomes. |
| W1_F01_s2 | verdict_wrong | real_struct_err | The causal effect of treatment on outcome, accounting for all pathways including |
| W1_F03_s1 | adjust_swap | full_pass | Treatment improves the primary outcome but also increases the risk of side effec |
| W1_F06_s2 | verdict_wrong | real_struct_err | Among patients with biomarker one standard deviation above the mean, the treatme |
| W1_F07_s1 | verdict_wrong | real_struct_err | Without adjusting for severity, the observed association between treatment and o |
| W2_F01_s0 | adjust_swap | full_pass | Exposure reduces the risk of disease. |
| W2_F01_s2 | verdict_wrong | real_struct_err | Intervening to increase exposure by one unit reduces disease risk by approximate |
| W2_F11_s0 | adjust_swap | full_pass | Exposure causes an increase in disease. |
| W2_F11_s1 | adjust_swap | full_pass | Increasing exposure leads to higher disease risk. |
| W3_F03_s1 | verdict_wrong | real_struct_err | The effect of temperature on health changes sharply at a threshold near zero: mi |
| W3_F08_s0 | adjust_swap | full_pass | Wind speed does not affect health. |
| W3_F08_s1 | adjust_swap | full_pass | There is no causal relationship between wind speed and health outcomes. |
| W3_F11_s0 | stage1_fail | full_pass | Temperature changes precede health effects by several days. |
| W3_F12_s0 | stage1_fail | full_pass | A randomized controlled trial would be needed to establish the causal effect of  |
| W3_F12_s1 | stage1_fail | full_pass | The sample size is insufficient to detect a small effect of wind speed on health |

### Regressed

| id | v2 | v3 | claim |
|---|---|---|---|
| W1_F03_s0 | adjust_swap | real_struct_err | Treatment causes side effects. |
| W1_F04_s2 | verdict_wrong | stage1_fail | The direct causal effect of treatment on outcome, controlling for compliance, is |
| W1_F05_s2 | real_struct_err | stage1_fail | The indirect effect of treatment on outcome through compliance is positive but s |
| W1_F09_s0 | full_pass | real_struct_err | Treated patients show more variable outcomes than untreated patients. |
| W2_F07_s0 | real_struct_err | verdict_wrong | Adjusting for the collider variable introduces bias in the exposure-disease esti |
| W2_F09_s1 | full_pass | verdict_wrong | Is the causal effect of exposure on disease identifiable from observational data |

## Abstention honesty (gold_status='abstain')

IDs: SQ_F07_s0, SQ_F07_s1, W3_F11_s0, W3_F12_s0, W3_F12_s1

| metric | v2 | v3 |
|---|---|---|
| stage1_ok (compiler correctly abstained) | 1/5 | 5/5 |
| deliberate (honest abstention) | 0 | 0 |
| fallback (lucky — crash/parse fail) | 1 | 5 |
