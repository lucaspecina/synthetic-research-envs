# SubQuestionIntent v2 — Spec de diseno

**Date:** 2026-03-30
**Type:** Spec de diseno / decision consolidada
**Status:** APROBADO PARA IMPLEMENTAR
**Prerequisitos:** S04 (compilacion directa validada), S05 (diagnostico SQ),
A23 (grammar-first), A24 (runtime general como horizonte)
**Evidencia:** S05 audito 10/10 experimentos causualizados. S04 valido
compilacion directa a AtomicSpec (2.3x verificaciones, 0 abstentions).

---

## 1. Problema

`SubQuestionIntent` fuerza todas las SQs a pasar por `PatternClass` — un
enum de 8 patterns fijos (causal_effect, mediation, confounding,
heterogeneity, observational_association, effect_ranking, tail_risk,
variance_effect).

Resultado: 10/10 experimentos generan los mismos SQ patterns sin importar
la seed. Un brief epistemologico, uno descriptivo y uno de VOI producen
SQs identicas (causal_effect + confounding + mediation + effect_ranking).

El solver investiga mejor de lo que las SQs lo evaluan. Claims diversas
(adjustment sensitivity, sign reversal, composicion vs tiempo) no matchean
SQs causales.

## 2. Que es una SubQuestion

**Una necesidad de evidencia verificable.**

No es una pregunta NL (eso es `text_gloss`). No es incertidumbre abstracta.
Es: "para considerar cubierta esta dimension de la investigacion, la
evidencia del solver debe ser consistente con estas verificaciones ocultas."

Las SQ existen para **relevancia**: sin ellas, un solver podria tirar
claims triviales verdaderas y sacar score perfecto. Las SQs definen que
DEBERIA cubrir la investigacion.

## 3. Nuevo contrato de SubQuestionIntent

### Campos

```python
class SubQuestionIntentV2(BaseModel):
    sq_id: str
    text_gloss: str                       # libre, humano-legible
    verification_specs: list[VerificationSpec]  # 1..N specs verificables
    tier: SQTier = SQTier.HIGH            # high / medium / low
    focus_variables: tuple[str, ...] = ()  # para pre-filtro rapido
```

### VerificationSpec

```python
class VerificationSpec(BaseModel):
    spec: AtomicSpec                      # la verificacion concreta
    role: Literal["required", "support"]  # obligatorio vs bonus
    verdict: AtomVerdict | None = None    # se llena al resolver contra SCM
```

### Que desaparece

- **`pattern`**: no hay campo pattern. La semantica se expresa en los specs.
- **`roles` (SQRoles)**: no hay treatment/outcome/mediator como campos
  estructurados. Las variables aparecen en los specs.
- **`ask` (AskOperator)**: no hay existence/sign/magnitude como enum.
  Lo que se pregunta esta en los specs (assertion kind + comparison kind).
- **`acceptance_rule`**: reemplazado por required/support en cada spec.

### Que se mantiene

- **`sq_id`**: identidad.
- **`text_gloss`**: descripcion libre. Sin restriccion de formato.
- **`tier`**: importancia relativa (high=1.0, medium=0.6, low=0.4).
- **`focus_variables`**: variables involucradas, para pre-filtro. NO para
  scoring.

## 4. Compilacion: SQ texto a specs

### Camino B — compile step separado

El orchestrador genera SQs como texto libre. Un compile step separado
las baja a AtomicSpecs. Separacion de concerns: el orc decide QUE
investigar, el compilador decide COMO verificar.

```
Orchestrador genera:
  { sq_id, text_gloss, focus_variables, tier }

Compile step recibe:
  SQ raw + world variables + grammar reference + world summary

Compile step produce:
  { sq_id, text_gloss, verification_specs: [VerificationSpec, ...], tier }

Resolution:
  verify_atom(spec) para cada spec → llenar verdict
```

### Invariantes del compile step

1. Toda SQ produce al menos 1 spec valido.
2. Los specs usan solo variables del mundo.
3. Los specs son ejecutables por el verifier.
4. Al menos 1 spec es `required`.
5. El compile step usa LLM + grammar (mismo approach que S04
   direct-to-atoms). No hay routing por pattern.

### Required vs support

El compile step decide cual spec es `required` (el que realmente
responde la pregunta) y cuales son `support` (evidencia adicional).

Ejemplo:
```
SQ: "Es la asociacion particle-wheeze robusta al ajuste covariable?"

  REQUIRED: partial_correlation(particle, wheeze | confounders)
            vs correlation(particle, wheeze) → contrast_diff → material
  SUPPORT:  correlation(particle, wheeze) → identity → positive
  SUPPORT:  partial_correlation(particle, wheeze | confounders) → identity → ...
```

Un solver que encuentra la correlacion cruda cubre un SUPPORT pero no
el REQUIRED. Credito parcial por la estructura del bundle, no por fuzzy
matching.

## 5. Matching: claim-specs vs SQ-specs

### Principios

1. **Exacto en el estimand**: mismo measurement kind + mismas primary
   variables + mismo tipo de conditioning (con/sin cond_set, mismas
   variables en el set). Si no matchea, score = 0.
2. **Fuzzy solo en la assertion**: positive matchea positive,
   near_zero no matchea positive. Tolerancia en threshold/magnitude.
3. **Bipartite 1-a-1**: un claim-spec solo puede cubrir un SQ-spec.
   Matching optimo (max-weight bipartite).
4. **No tablas de compatibilidad**: no recrear PatternClass en tablas
   de compat entre measurement kinds. Match exacto, no parcial.

### Definicion formal

```
spec_match(claim_spec, sq_spec) -> float [0, 1]:
    # Hard gate: estimand
    if claim_spec.measurement.kind != sq_spec.measurement.kind:
        return 0.0
    if primary_vars(claim_spec) != primary_vars(sq_spec):
        return 0.0
    if conditioning_set(claim_spec) != conditioning_set(sq_spec):
        return 0.0

    # Hard gate: ambos verificados TRUE
    if not claim_spec.verdict.solver_assertion_holds:
        return 0.0
    if not sq_spec.verdict.solver_assertion_holds:
        # SQ spec is FALSE in ground truth — skip, don't penalize
        return 0.0

    # Soft score: assertion compatibility
    return assertion_compat(claim_spec.assertion, sq_spec.assertion)

assertion_compat(claim_a, sq_a) -> float:
    # Same kind: 1.0
    # Compatible (positive/negative are directional matches): 0.8
    # Contradictory (positive vs negative): 0.0
    # Near_zero vs directional: 0.0
```

### primary_vars y conditioning_set

```
primary_vars(spec):
    m = spec.measurement
    if m.target: return {m.target}
    if m.lhs and m.rhs: return {m.lhs, m.rhs}
    if m.treatment and m.outcome: return {m.treatment, m.outcome}
    return set()

conditioning_set(spec):
    m = spec.measurement
    return set(m.cond_set) if m.cond_set else set()
```

### SQ satisfaction

```
claim_covers_sq(claim_specs, sq) -> float:
    # Bipartite 1-a-1 matching
    matches = bipartite_match(claim_specs, sq.verification_specs, spec_match)

    # Required coverage
    required_specs = [vs for vs in sq.verification_specs if vs.role == "required"]
    required_covered = sum(1 for rs in required_specs if matches[rs] > 0)
    required_coverage = required_covered / len(required_specs) if required_specs else 0

    # Support bonus
    support_specs = [vs for vs in sq.verification_specs if vs.role == "support"]
    support_covered = sum(1 for ss in support_specs if matches[ss] > 0)
    support_bonus = (support_covered / len(support_specs) * 0.2) if support_specs else 0

    return min(1.0, required_coverage + support_bonus)
```

### Episode-level SQ score

```
for each SQ:
    satisfaction = max(claim_covers_sq(claim.specs, sq) for claim in claims)
    # satisfaction > 0 only if at least one required spec is covered

coverage = count(satisfaction > 0) / n_sqs
weighted_coverage = sum(satisfaction * sq.weight) / sum(sq.weight)
correctness = mean truth rate of claims used in matching
novel_bonus = true claims not matched to any SQ (capped)

total = weighted_coverage * 0.70 + correctness * 0.20 + novel_bonus + coverage * 0.10
```

Misma estructura que el scoring actual. Lo que cambia es COMO se computa
satisfaction (specs vs patterns), no la agregacion.

## 6. Anti-spam (precision gate)

El solver no debe ser recompensado por tirar muchos specs a ver que pega.

- **EPISODE_PRECISION_GATE** (ya existe, ~0.55): si la fraccion de
  claim-specs TRUE es menor que el gate, penalizar.
- **Por claim**: si un claim genera 10 specs y 2 son TRUE, su truth
  rate es 0.20. No sirve como evidencia confiable.
- **Novel bonus capped**: claims fuera de SQs dan bonus limitado. No
  premiar masa bruta.

## 7. Resolution

Hoy `resolve_subquestion()` rutea por pattern, construye specs, verifica
contra SCM, clasifica la respuesta (positive/negative/near_zero).

Con v2, resolution se simplifica:

```
resolve_sq(sq: SubQuestionIntentV2, world, solver):
    for vs in sq.verification_specs:
        vs.verdict = verify_atom(vs.spec, world, solver)
    return sq  # con verdicts llenos
```

No hay clasificacion de respuesta. No hay "resolved direction". Los
verdicts son la resolucion. Un spec que dice "partial_correlation is
positive" tiene verdict.solver_assertion_holds = True o False.

Para diagnostico humano se puede derivar un summary ("robust",
"sensitive", "not identifiable") de los verdicts, pero no participa
en scoring.

## 8. Ejemplos concretos

### Caso epistemologico (e2e_03)

Brief: evaluar si la interpretacion causal particle→wheeze es defendible.

**SQ actual** (v1):
```
pattern=causal_effect, ask=existence_and_sign
roles: treatment=particle, outcome=wheeze
```
→ El solver encuentra C2 (adjustment sensitivity). ABSTENTION.

**SQ propuesta** (v2):
```
text_gloss: "Es la asociacion particle-wheeze robusta al ajuste covariable?"
specs:
  REQUIRED: partial_corr(particle, wheeze | confounders) vs
            corr(particle, wheeze) → contrast_diff → material_change
  SUPPORT:  corr(particle, wheeze) → identity → positive
  SUPPORT:  partial_corr(particle, wheeze | confounders) → identity → ...
```
→ C2 compila a partial_correlation specs → matchea REQUIRED.

### Caso descriptivo (e2e_12)

Brief: perfiles de uso de plataforma y bienestar.

**SQ actual** (v1):
```
pattern=causal_effect, ask=sign
roles: treatment=social_feed_share, outcome=wellbeing_score
```
→ Fuerza marco causal a un brief descriptivo.

**SQ propuesta** (v2):
```
text_gloss: "Que dimensiones de uso se asocian con wellbeing?"
specs:
  REQUIRED: corr(social_feed_share, wellbeing_score) → identity → negative
  REQUIRED: corr(creation_ratio, wellbeing_score) → identity → positive
  SUPPORT:  corr(news_night_share, sleep_quality_score) → identity → negative
  SUPPORT:  corr(daily_platform_time, wellbeing_score) → identity → negative
```
→ No hay treatment/outcome. No es causal. Es verificable.

### Caso VOI (e2e_10)

Brief: asesorar sobre proxima fase de vigilancia de agua subterranea.

**SQ actual** (v1):
```
pattern=causal_effect, ask=sign
roles: treatment=nitrate, outcome=GI_incidence
```
→ Pregunta causal simple para un brief de VOI.

**SQ propuesta** (v2):
```
text_gloss: "Cuan sensible es la estimacion nitrate-GI a confounders?"
specs:
  REQUIRED: corr(nitrate, GI) vs partial_corr(nitrate, GI | pesticide,
            fertilizer, water_table) → contrast_diff → material_change
  SUPPORT:  corr(nitrate, GI) → identity → positive
  SUPPORT:  partial_corr(nitrate, GI | pesticide) → identity → ...
```
→ c3 del solver (adjustment sensitivity) matchea REQUIRED.

**Limitacion documentada**: no podemos verificar "que medicion reduce
mas la incertidumbre" (second-order VOI). Verificamos los building blocks
del razonamiento VOI. Ver PROJECT.md "Scope actual y horizontes futuros".

## 9. Primer experimento

### Setup

- 4 seeds diversas: epistemic (e2e_03), descriptive (e2e_12),
  VOI (e2e_10), selection bias (e2e_07)
- Pipeline A (actual): SQs v1 (pattern+roles) → catalog scoring
- Pipeline B (nuevo): SQs v2 (text+specs) → spec matching

### Que medir

| Metrica | Que captura |
|---------|------------|
| unique_measurement_kinds | Diversidad de verificacion |
| spec_validity | Calidad del compile step (>90%) |
| variable_relevance | Specs tocan variables del brief |
| required_coverage | Claims cubren specs obligatorios |
| clustering_entropy | Anti-monocultura de specs |

### Criterio de exito

1. unique_measurement_kinds > 3 por episodio (vs ~2 con v1)
2. spec_validity > 90%
3. variable_relevance > 0.80
4. Al menos 1 caso donde v2 premia un claim que v1 descarta (ABSTENTION)
5. required_coverage no peor que v1 coverage en casos causales simples

### Que NO medir

- Score final del episodio (no hay scoring v3 todavia)
- Calidad del solver (el experimento es sobre SQs)
- Precision del compiler de claims (no cambia en este paso)

## 10. Secuencia de implementacion

1. **Modelo** — `SubQuestionIntentV2` + `VerificationSpec`. Coexiste con v1.
2. **Compile step** — `compile_sq_to_specs(sq_raw, world, summary)`. LLM-based.
3. **Matching** — `spec_match()` + `claim_covers_sq()` + bipartite matching.
4. **Script de comparacion** — pipeline A vs B en 4 seeds.
5. **Integracion** — si funciona, reemplazar v1 en el pipeline.

## 11. Conexiones

- **S04** — evidencia de compilacion directa a AtomicSpec
- **S05** — diagnostico de diversidad (superseded por este doc)
- **A23** — propuesta original grammar-first (este doc la concreta)
- **A24** — horizonte mediano plazo (validator programs generales)
- **PROJECT.md** — scope actual: ciencia que produce conocimiento
- **CLAUDE.md** — UN solo metodo, brief libre, sistema se adapta

## 12. Decisiones explicitas

| Decision | Alternativa descartada | Razon |
|----------|----------------------|-------|
| Sin pattern | pattern_hint opcional | Crea muleta, alguien lo usa |
| Match exacto en estimand | Credito parcial (0.3) | Blurring, hackeable en RL |
| Required/support | ALL_OF/ANY_OF/SOFT_AND | Mas simple, mismo resultado |
| Bipartite 1-a-1 | Many-to-many | Evita un spec cubriendo N SQs |
| Compile step separado | Orc genera specs | Separacion de concerns |
| Credito parcial via bundle | Fuzzy matching | Limpio, diseñado intencionalmente |
