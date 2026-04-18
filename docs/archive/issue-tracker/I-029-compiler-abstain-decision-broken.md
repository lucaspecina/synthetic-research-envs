---
id: 29
title: Claim compiler never abstains — always tries to compile, even on non-expressible claims
status: open
type: bug
lane: compiler
priority: soon
created: 2026-04-15
related: [I-007, I-026, I-027, I-028]
origin: Suite 2 diagnostic battery (2026-04-15) — stage1 split + D2 slot elicitation
---

# I-029: Claim compiler never abstains — always tries to compile

## Status
- **Estado:** detectado durante la diagnostic battery D1/D2 + stage1_split
  del compiler v2 (2026-04-15). Ver
  `research/synthesis/suite2_compiler_improvement_strategy.md` §7.2 y §7.4.

## Síntomas

De los 55 targets del baseline v2, **5 tienen gold_status=abstain**
(non_expressible, latent variable, temporal-only, etc.). El compiler
acierta en **0/5**:

- Los 4 stage1_fail con gold=abstain (W2_F12, W3_F05_s0, W3_F11_s0,
  W3_F12_s0, y otros) son todos `decision_fail` tipo "compilé cuando
  debía abstenerme".
- En D2 (slot elicitation independiente del compiler real), el mismo
  modelo gpt-5.4 con el prompt del diagnostic acierta `status=abstain`
  en **51/55** (93%). O sea, **el LLM sabe cuándo abstenerse cuando se
  le pregunta**; pero el compiler real nunca toma esa decisión.

Inferencia: el prompt/policy del compiler no tiene una **puerta de
abstain explícita**. El LLM asume "si me dan una claim, producir
specs".

## Evidencia

1. **stage1_split** (`research/synthesis/suite2_stage1_split.json`):
   - decision_fail: 4 (todos con gold=abstain, compiler emitió specs)
   - crash: 2 (ambos I-028 sweep_values)
2. **D2 slot elicitation**
   (`research/synthesis/suite2_diag_d2_results.json`):
   - status accuracy = 93% (51/55) con el prompt diagnostic que
     menciona abstain explícitamente.
   - Contraste directo: el modelo SÍ sabe cuándo abstenerse. El
     compiler real NO lo usa.

## Hipótesis de causa

1. **Prompt policy missing:** `compile_claim_direct` no instruye al
   LLM a devolver `{"abstain": true}` cuando la claim es
   non-expressible. El output schema asume compile.
2. **Output format coercion:** aunque el LLM quisiera abstenerse, la
   schema obligada le pide specs. Sin un path explícito de abstain
   el modelo se esfuerza por compilar lo que puede.
3. **No classifier-head:** no hay una decisión first-pass "compile
   vs abstain" antes del recipe generation.

## Scope del fix

- **Opción A (prompt clause):** agregar al system prompt del compiler
  una cláusula dedicada "If the claim is non-expressible (no
  intervene-able variable, temporal-only, methodological) → output
  `{status: 'abstain', abstain_reason: '<code>'}`. **NO try to emit
  specs.**"
- **Opción B (two-step compile):** primera LLM call decide
  compile/abstain + reason; solo si compile, segunda call emite specs.
  Más robusto pero 2× cost.
- **Opción C (structured output):** forzar el schema de output a
  incluir `status: "compile" | "abstain"` como top-level discriminator.

Preferencia tentativa: **A + C**. A es barato; C valida
estructuralmente.

## Impacto esperado del fix

Los 4 decision_fail por abstain se reclasifican a `full_pass` (o al
menos `effective_pass`). Eso sube:
- stage1_fail: 6 → 2 (solo crashes de I-028)
- effective_pass_rate: 31% → ~38%
- strict_full_pass_rate: 13% → ~20% (se combina con la formalización
  adjust-swap parcial, §7.1)

## Reproducción

```bash
conda activate sreg
# Via baseline dump (offline)
python -c "
import json
entries = json.load(open('research/synthesis/compiler_baseline_full_dump_v2.json'))
abstain_entries = [e for e in entries if e['gold_status'] == 'abstain']
for e in abstain_entries:
    print(e['id'], e['compiler_compiled'], e.get('compiler_abstain_reason'))
"
```

Debe imprimir 4-5 entries, todos con `compiler_compiled=True` (bug).

## Links
- `research/synthesis/suite2_compiler_improvement_strategy.md` §7.2, §8.1
- `research/synthesis/suite2_stage1_split.json`
- `research/synthesis/suite2_diag_d2_results.json` (slot `status`)
- Suite 2 baseline issue: I-007
- Recipe exemplar work: I-026
- Stage1 bucket hygiene: I-027 item 7
