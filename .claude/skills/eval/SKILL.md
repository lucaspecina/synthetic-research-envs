---
name: eval
description: Evaluate SRC quality — quantitative metrics AND qualitative rubric + open discovery. Use after changes that affect SRC generation, or periodically as health check. The most important evaluation tool in the project.
---

Evaluate Synthetic Research Cases (SRCs) for quality. This is Level 2 of the
evaluation harness — "are the environments good?"

**This skill has two equally important components:**
1. Quantitative: automated metrics (KL, submit rate, baselines)
2. Qualitative: structured rubric + open-ended discovery of new problems

Both must run. Quantitative alone misses the most important problems.

## Step 1: Generate or select SRCs

Parse $ARGUMENTS:
- If a path to an existing case is given, use that
- If a topic/seed is given, generate with `/run`
- If nothing specified, generate 3 SRCs with diverse seeds

**Minimum for evaluation:** 3 SRCs from different domains.
**Recommended after big changes:** 5-10 SRCs.

```bash
# Generate with inspection
python scripts/generate_src.py --goal "..." -o experiments/eval_TOPIC/ --inspect --seed N

# Or use existing
ls experiments/case_NAME/
```

## Step 2: Quantitative evaluation

For each SRC, if `--solve` was used or DiagnosticRunner is available:

**Metrics to report:**
- Orchestrator completion: did it produce a complete case?
- WorldCheck pass rate
- Agent submit rate
- KL distribution (mean, median, min, max)
- Baseline comparison per eval type (agent vs random)
- Budget efficiency
- Failure modes: no-submit, worse-than-baseline, format errors, ZERO_OBS

**Key imports:**
```python
from sreg.orchestrator.orchestrator import Orchestrator
from sreg.agent.agent import AgentSolver
from sreg.harness.agent_trajectory import extract_agent_trajectory
from sreg.harness.trajectory import generate_teacher_trajectory
from sreg.harness.comparison import compare_trajectories
```

## Step 3: Qualitative evaluation — structured rubric

Read `briefing.md` and `answer_key.md` for each case. Score:

### 7 Dimensions (0 = falla, 1 = mixto, 2 = convincente)

| D# | Dimension | Que evaluar |
|----|-----------|-------------|
| D1 | Framing real | Brief suena a encargo profesional, no a ejercicio academico? |
| D2 | Necesidad de datos | Se puede responder sin mirar los datos? |
| D3 | Coherencia entre capas | Brief, deliverables, eval questions, dataset cuentan la misma historia? |
| D4 | Validez de comparacion | Las intervenciones tienen sentido cientifico? |
| D5 | Realismo de datos | Variables con unidades, estructura de panel, missingness, proxies? |
| D6 | Riqueza epistemica | Hay ambiguedad, alternativas, sensibilidad a supuestos? |
| D7 | Workflow investigativo | El caso invita a explorar, contrastar, chequear robustez? |

### 6 Critical Failures (binarios — cualquiera = defecto grave)

| CF# | Failure | Como detectar |
|-----|---------|---------------|
| CF1 | answerable_without_data | LLM responde bien sin dataset (ver Step 4) |
| CF2 | exam_like_wording | "Answer A or B", "Submit a distribution", "maximize X" |
| CF3 | brief_eval_mismatch | Brief habla de un tema, eval questions de otro |
| CF4 | variable_name_leak | snake_case, node IDs, eval type names visibles al investigador |
| CF5 | toy_comparison | Intervenciones sin sentido cientifico ("set X to high") |
| CF6 | narrative_as_skin | Si quitas la narrativa, el caso se resuelve igual |

**IMPORTANTE**: estas dimensiones y CFs son el PISO, no el techo.
Ver Step 5 (descubrimiento abierto).

## Step 4: No-data baseline probe

El test mas poderoso. Para cada SRC:

1. Tomar el brief + preguntas visibles (de `briefing.md`)
2. Darselo a un LLM SIN dataset, SIN esquema de datos
3. Pedirle que responda lo mejor que pueda
4. Comparar con las respuestas correctas de `answer_key.md`

**Si el LLM sin datos supera al random baseline, el SRC no fuerza investigacion.**
Esto es CF1 (answerable_without_data) y es el critical failure mas grave.

Implementacion: puede ser manual (copiar el brief, pegar en otro chat) o
con un script dedicado cuando exista.

## Step 5: Descubrimiento abierto — LA FASE MAS IMPORTANTE

**Leer el caso completo con ojos frescos** y buscar CUALQUIER cosa que se
sienta mal, artificial, o que no pasaria en una investigacion real.

Preguntas guia (pero NO limitarse a estas):
- Un cientifico del dominio creeria que este es un caso real?
- Las preguntas son las que un investigador haria?
- Los datos se ven como un dataset real?
- El brief y los datos cuentan la misma historia?
- Hay algo que suene a "juego" en vez de "investigacion"?
- Las variables tienen sentido en el contexto del dominio?
- Las unidades son correctas? Los rangos son plausibles?
- Hay algo que un investigador notaria en 10 segundos como falso?

**Cuando encuentres un problema nuevo (no cubierto por D1-D7 o CF1-CF6):**
1. Documentarlo en el registro de la evaluacion
2. Evaluar si es recurrente (aparece en otros SRCs tambien?)
3. Si es recurrente, agregarlo a `research/synthesis/qualitative_eval_rubric.md`
   como candidato a nueva dimension o critical failure

**La rubrica evoluciona.** Cada evaluacion puede descubrir nuevos problemas
que se promueven a dimensiones o CFs formales.

## Step 6: Registrar resultados

Para cada SRC evaluado, registrar en formato estructurado:

```yaml
case_id: [topic]-[date]
commit: [hash]
reviewer: claude|human|codex
seed: [seed file or goal]

# Quantitative (if available)
kl_scores: [list]
submit_rate: X%
baseline_comparison: {eval_type: beats_random_%}

# Qualitative — structured rubric
dimensions:
  D1_framing_real: 0|1|2
  D2_data_necessity: 0|1|2
  D3_layer_coherence: 0|1|2
  D4_comparison_validity: 0|1|2
  D5_data_realism: 0|1|2
  D6_epistemic_richness: 0|1|2
  D7_investigation_workflow: 0|1|2

critical_failures: [list of CF IDs, empty if none]

# Qualitative — open discovery
new_findings:
  - description: "..."
    severity: low|medium|high
    recurrent: true|false  # seen in other SRCs?
    candidate_for: dimension|critical_failure|none

evidence: "Free text — specific examples, quotes from briefing/answer_key"
overall_verdict: GOOD|NEEDS_WORK|DEFECTIVE
```

Guardar en `experiments/qualitative/` como YAML o en el reporte del caso.

## Step 7: Reportar al usuario

En espanol. Incluir:
1. **Resumen ejecutivo**: cuantos SRCs evaluados, verdict general
2. **Tabla de dimensiones**: scores por SRC y promedios
3. **Critical failures encontrados**: cuales y en que casos
4. **Hallazgos nuevos**: problemas no cubiertos por la rubrica actual
5. **Recomendaciones**: que arreglar primero, que investigar mas
6. **Evolucion de rubrica**: si hay hallazgos nuevos recurrentes,
   proponer promocion a dimension o CF formal

## Step 8: Actualizar rubrica si corresponde

Si se encontraron problemas nuevos recurrentes:
1. Abrir `research/synthesis/qualitative_eval_rubric.md`
2. Agregar al "Registro de hallazgos" con fecha y evidencia
3. Si aparecio en 2+ SRCs, proponer como nueva dimension o CF
4. Discutir con el usuario antes de promover

## Referencia

- Rubrica completa: `research/synthesis/qualitative_eval_rubric.md`
- Framework cuantitativo: `research/synthesis/eval_strategy.md`
- Metricas detalladas: `research/notes/eval_design_notes.md`
- Harness overview: seccion "Harness de evaluacion" en `CLAUDE.md`
