# Primera evaluacion cualitativa formal — 2026-03-24

> Rubrica v1.0. Commit: 437b181 (feature/scm-engine)
> Reviewers: claude + codex (second opinion)
> 3 SRCs evaluados: football (post-Fase 9), coral_reef (pre-Fase 9), vaca_muerta (pre-Fase 9)
> **NOTA:** solo football refleja el sistema actual. Coral reef y vaca muerta son
> baseline de comparacion (pre-Fase 9), NO evaluacion del sistema vigente.

## Resumen ejecutivo

| SRC | Score promedio (D1-D7) | Critical failures | Verdict |
|-----|----------------------|-------------------|---------|
| football (actual) | 1.29 (revisado con Codex) | CF4 | NEEDS_WORK |
| coral_reef (viejo) | 1.29 | CF2, CF4, CF5 | DEFECTIVE |
| vaca_muerta (viejo) | 1.00 | CF2, CF3, CF4, CF5 | DEFECTIVE |

Football (sistema actual) elimino los defectos mas graves de Fases anteriores (CF2,
CF5, CF3). Pero CF4 persiste y se identificaron **8 hallazgos nuevos** (4 de Claude,
4 de Codex) que apuntan a un problema raiz mas profundo: las preguntas nacen del
scorer (graph-native, eval-native), no de la investigacion.

**Evaluacion basada en n=1 del sistema actual.** Generar 2-3 SRCs mas antes de
sacar conclusiones definitivas.

---

## SRC 1: Football (post-Fase 9, sistema actual)

**case_id:** football-2026-03-24
**seed:** seeds/football.md
**engine:** SCM

### Dimensiones

| D# | Dimension | Score | Claude original | Ajuste Codex | Evidencia |
|----|-----------|-------|----------------|-------------|-----------|
| D1 | Framing real | **2** | 2 | 2 | Brief suena profesional: "Club Deportivo Auria", departamento de rendimiento, encargo con contexto y motivacion. Deliverables especificos y accionables. |
| D2 | Necesidad de datos | **1** | 2→1 | 1 (provisional) | Q1, Q4, Q5 requieren datos. Pero falta no-data probe formal. Codex: "provisional hasta correr el probe". |
| D3 | Coherencia entre capas | **1** | 2→1 | 1 | Brief promete guidance accionable para staff, pero las preguntas visibles son casi una enumeracion de eval types. Las 5 preguntas mapean 1:1 a causal_effect, compare_interventions, interaction, mediation, infer_latent_cause — la taxonomia se nota. (Codex: "eval_ontology_leak") |
| D4 | Validez de comparacion | **1** | 1 | 1 | Q2 compara recovery_quality vs training_load_7d — sentido cientifico. Pero "setting recovery_quality to low" es artificial. Un investigador diria "players with poor pre-match recovery". |
| D5 | Realismo de datos | **1** | 2→1 | 1 | Panel, missing 28%, proxies, unidades. Pero: columnas casi duplicadas (coach_substitution_pressure + _level), precision inconsistente, faltan player_id/match_id/fecha/rival. `sample_id` no es la llave que un analista esperaria. (Codex: "indexing_realism") |
| D6 | Riqueza epistemica | **1** | 1 | 1 | Q3 (interaccion = no exacto) y Q4 (mediacion = 1.0 exacto). Demasiado limpio. Codex: "un cientifico no puede tolerar 100% de mediacion exacta en un caso observacional". |
| D7 | Workflow investigativo | **1** | 2→1 | 1 | Codex: "faltan decisiones reales de identificacion, robustez y data quality". El caso asume identificacion causal resuelta — salta directo a ATE y mediacion sin justificar. |

**Promedio: 1.14** (revisado) — **era 1.71 antes de la critica de Codex**

### Critical failures

| CF# | Status | Evidencia |
|-----|--------|-----------|
| CF1 | PASS (pendiente probe formal) | Las preguntas cuantitativas requieren datos. Pendiente: no-data baseline probe. |
| CF2 | **PASS** | Templates reescritos en Fase 9. No hay "Answer A or B", "maximize above X", "Submit distribution". |
| CF3 | PASS | Brief y eval alineados. |
| CF4 | **FAIL** | Q2: "'recovery_quality' to 'low'". Q3: "'training_load_7d' on 'second_half_tactical_decline'". Q4: "'training_load_7d' on 'second_half_tactical_decline' is mediated through 'second_half_physical_drop'". Variables internas con snake_case y comillas simples en las preguntas. |
| CF5 | PASS | No hay thresholds arbitrarios ni "maximize algo negativo". |
| CF6 | PASS | La narrativa futbolistica es integral — sin ella no sabrias por que importan estas variables. |

---

## SRC 2: Coral Reef (pre-Fase 9, templates viejos)

**case_id:** coral_reef-2026-03-24
**seed:** (goal directo)
**engine:** SCM

### Dimensiones

| D# | Dimension | Score | Evidencia |
|----|-----------|-------|-----------|
| D1 | Framing real | **2** | Excelente. "Pelagos Crescent", bleaching, resilience, management tradeoffs. Suena a encargo real para ecologos marinos. |
| D2 | Necesidad de datos | **1** | Q1-Q2 necesitan datos. Q3 ("marine_reserve_enforcement vs coastal_runoff_load") podria responderse desde priors de ecologia marina. Q4 (coral morphology modera thermal stress) tambien. |
| D3 | Coherencia entre capas | **1** | Brief pide "heat-stress reduction vs runoff mitigation vs fishery protection". Q3 traduce esto pero con threshold 79.97 y "maximize", desconectando. Q4 es coherente. |
| D4 | Validez de comparacion | **0** | Q3: "maximize 'reef_recovery_index' being above 79.97" — threshold arbitrario (79.97?), framing de optimizacion en vez de investigacion. La comparacion marina reserve vs runoff TIENE sentido cientifico, pero el framing lo arruina. |
| D5 | Realismo de datos | **2** | Panel, missing 20%, proxies (herbivore_fish_biomass_score, reef_recovery_index_measure). Variables con nombres claros del dominio. |
| D6 | Riqueza epistemica | **1** | Multiples pathways (thermal, management, prior damage). Pero Q3-Q4 son binarios (A/B, yes/no) sin matiz. |
| D7 | Workflow investigativo | **2** | 5 preguntas, panel structure, missing data, latente. Invita a explorar. |

**Promedio: 1.29**

### Critical failures

| CF# | Status | Evidencia |
|-----|--------|-----------|
| CF1 | PROBABLE | Q3 (marine reserves vs runoff) y Q4 (coral morphology modera thermal stress) probablemente respondibles desde priors. |
| CF2 | **FAIL** | Q3: "maximize 'reef_recovery_index' being above 79.97... Answer 'A' or 'B'". Q4: "Answer 'yes' if the effect varies... or 'no' if it remains roughly constant." |
| CF3 | PASS | Parcialmente. Q3 desconecta pero Q1-Q2-Q4-Q5 estan alineados. |
| CF4 | **FAIL** | Q3: 'reef_recovery_index', 'marine_reserve_enforcement', 'coastal_runoff_load'. Q4: 'thermal_stress_index', 'bleaching_severity', 'coral_morphology_index'. |
| CF5 | **FAIL** | Threshold 79.97, "maximize". |
| CF6 | PASS | Narrativa es integral. |

---

## SRC 3: Vaca Muerta (pre-Fase 9, templates viejos)

**case_id:** vaca_muerta-2026-03-24
**seed:** seeds/vaca_muerta.md
**engine:** SCM

### Dimensiones

| D# | Dimension | Score | Evidencia |
|----|-----------|-------|-----------|
| D1 | Framing real | **2** | "Kutral shale block", frac-hits, parent wells sanding. Lenguaje profesional de ingenieria de reservorios. |
| D2 | Necesidad de datos | **1** | Q1 (ATE) necesita datos. Q3 (latente) necesita datos. Q4 (adjustment_set) podria responderse desde conocimiento de petroleo. Q2 es problematico (ver abajo). |
| D3 | Coherencia entre capas | **0** | **CRITICO**: Brief dice "reducir sanding risk". Q2 dice "maximize 'parent_sanding_risk' being above 0.04". El brief y la pregunta se CONTRADICEN directamente. |
| D4 | Validez de comparacion | **0** | Q2: "maximize 'parent_sanding_risk' being above 0.04". Maximizar un riesgo que el brief pide MINIMIZAR. Ademas threshold arbitrario 0.04. Cientificamente absurdo. |
| D5 | Realismo de datos | **2** | Panel, 13% missing, proxies (proppant_loading_measure, pressure_pem_ratio_score). Variables petroleras reales. |
| D6 | Riqueza epistemica | **1** | Multiple pathways (pressure, spacing, geomechanics, hidden vulnerability). 4 preguntas es escueto. |
| D7 | Workflow investigativo | **1** | Solo 4 preguntas. Menos invitacion a explorar. Panel + missing ayudan pero la estructura es mas lineal. |

**Promedio: 1.00**

### Critical failures

| CF# | Status | Evidencia |
|-----|--------|-----------|
| CF1 | PROBABLE | Q4 (adjustment set) respondible desde conocimiento petrolero. |
| CF2 | **FAIL** | Q2: "maximize 'parent_sanding_risk' being above 0.04... Answer 'A' or 'B'". |
| CF3 | **FAIL** | Brief pide reducir sanding risk; Q2 pide maximizarlo. |
| CF4 | **FAIL** | Q2: 'parent_sanding_risk', 'max_treatment_pressure', 'child_fluid_intensity'. |
| CF5 | **FAIL** | "Maximize" un outcome negativo + threshold arbitrario 0.04. |
| CF6 | PASS | Narrativa petrolera es integral. |

---

## Hallazgos nuevos (descubrimiento abierto)

Problemas encontrados que NO estan cubiertos por D1-D7 o CF1-CF6.

### H1. Variables referenciadas como codigo, no como prosa (RECURRENTE - 3/3 SRCs)

**Severidad: medium**

Las preguntas citan nombres de variables con comillas simples y snake_case como si
fueran referencias de codigo: "'training_load_7d' on 'second_half_tactical_decline'".
Un investigador real escribiria: "recent training load on second-half tactical decline".

Esto es distinto de CF4 (que es sobre visibilidad de nombres internos). Aqui el problema
es el ESTILO: las preguntas usan sintaxis de programacion para referir variables del
dataset, en vez de usar lenguaje natural.

**Candidato para: sub-criterio de CF4 o nueva dimension "naturalidad del lenguaje".**

### H2. "Setting X to Y" — framing interventional en vez de comparativo (RECURRENTE - 3/3 SRCs)

**Severidad: medium**

Todas las preguntas de compare_interventions usan "setting X to value" como si
estuvieramos escribiendo codigo: `do(recovery_quality = low)`. Un investigador diria:
- "Among players with poor pre-match recovery..." (observacional)
- "If the club were to reduce training load..." (contrafactual natural)
- "What would happen if recovery protocols were improved?" (intervencion real)

El verbo "set" delata el do-calculus subyacente. No es un problema del template
solamente — es como el sistema piensa sobre intervenciones.

**Candidato para: nueva dimension "naturalidad de intervenciones" o sub-criterio de D4.**

### H3. Mediation = 1.0 y interaction = "no" — respuestas artificialmente limpias (FOOTBALL)

**Severidad: medium**

En football, la mediacion por physical_drop es exactamente 1.0 (100% mediada, 0%
directa) y la interaccion training_load x tactical_role es exactamente "no".
En investigacion real, estos valores son ruidosos — mediacion tipica es 0.3-0.7,
y las interacciones rara vez son exactamente cero.

Las ecuaciones del SCM son deterministas (excepto ruido gaussiano), lo que puede
producir relaciones demasiado limpias. Si el efecto de training_load pasa POR
physical_drop, la mediacion sera exactamente 1.0 por construccion.

**Candidato para: sub-criterio de D6 "las respuestas correctas son plausiblemente
imprecisas" o nuevo CF "artificially_clean_answers".**

### H4. Descripcion del dataset revela estructura interna (RECURRENTE - 3/3 SRCs)

**Severidad: low**

Al final de cada briefing hay una linea que dice: "Dataset with 500 observations.
Collected from 4 sites. 3 measurement waves. Columns: [lista completa]".

Esto revela:
- Que hay exactamente 4 sites y 3 waves (un investigador real descubriria esto
  explorando los datos)
- La lista completa de columnas incluyendo las proxy (que podrian confundirse
  con variables causales)
- El % de missing exacto

En un dataset real, recibirias el CSV y un data dictionary separado (o nada).
La metadata al final del briefing es demasiado explicita.

**Candidato para: sub-criterio de D5 "discovery vs disclosure de estructura".**

### Hallazgos de Codex (second opinion, 2026-03-24)

Codex leyo los 4 archivos y concluyo que la evaluacion original era "algo benevola".
Ademas de ajustar scores (reflejados arriba), identifico 4 problemas adicionales:

### H5. causal_warrant — identificacion causal asumida sin justificar (FOOTBALL)

**Severidad: high**

Con datos observacionales de 4 sites, 3 waves y 28% missing, el caso salta
directamente a ATE, mediacion e interaccion como si la identificacion causal
ya estuviera resuelta. Un investigador real primero justificaria su estrategia
de identificacion (instrumentos, diferencias en diferencias, discontinuidad,
etc.) antes de estimar efectos causales.

**Candidato para: nueva dimension "identification credibility".**

### H6. measurement_provenance — variables sin explicar como se midieron (FOOTBALL)

**Severidad: high**

Variables como `cognitive_fatigue`, `second_half_tactical_decline`,
`coach_substitution_pressure` aparecen como columnas limpias en el dataset.
No se explica si son composites, ratings subjetivos, tests estandarizados,
o derivados de otras mediciones. Un investigador real necesita saber esto
para juzgar la calidad de la evidencia.

**Candidato para: sub-criterio de D5 o nueva dimension "measurement_provenance".**

### H7. indexing_realism — faltan llaves que un analista esperaria (FOOTBALL)

**Severidad: medium**

Para un caso player-match faltan `player_id`, `match_id`, fecha, minutos
jugados, rival. Aparece `sample_id` generico. Las llaves naturales del
dominio estan ausentes — un analista real esperaria poder agrupar por
jugador o por partido.

**Candidato para: sub-criterio de D5.**

### H8. eval_ontology_leak — la taxonomia de eval types se nota (FOOTBALL)

**Severidad: high**

Q1-Q5 mapean 1:1 a causal_effect, compare_interventions, interaction,
mediation, infer_latent_cause. Un investigador no plantearia exactamente
una pregunta por tipo de evaluacion. Las preguntas parecen diseñadas para
cubrir la taxonomia interna del sistema, no para investigar el fenomeno.

Codex: "las preguntas nacen del scorer, no de la investigacion". Esto
conecta directamente con I10 Fase 3.

**Candidato para: nueva dimension o nuevo CF "eval_ontology_leak".**

---

## Analisis de causa raiz (sintesis Claude + Codex)

### Codex: los sintomas superficiales vs la raiz profunda

> "CF4 + H1 + H2 no son la raiz — son sintomas. La raiz es que la generacion
> de preguntas sigue siendo **graph-native** y **eval-native**: piensa en node
> IDs, en 'set X to Y', en estimands scoreables, y luego lo viste de narrativa.
> Si mañana reemplazan snake_case por prosa natural, football va a verse mejor;
> igual va a seguir sintiendose benchmark porque las preguntas estan diseñadas
> desde el scorer y no desde una investigacion creible."

### Mapa de sintomas a causa raiz

```
RAIZ: preguntas nacen del scorer (graph/eval-native)
  |
  +-> H8: eval_ontology_leak (1 pregunta por eval type)
  +-> H1/CF4: variable names como codigo (usa node_id)
  +-> H2: "set X to Y" (usa do-calculus directamente)
  +-> H5: causal_warrant asumido (salta a ATE sin justificar)
  +-> H3: respuestas demasiado limpias (ecuaciones deterministas)
```

La solucion de fondo es I10 Fase 3: el orchestrator piensa primero "que
preguntaria un investigador" y DESPUES mapea a eval types. Las correcciones
cosmeticas (usar semantic names, cambiar "set" por prosa natural) son necesarias
pero insuficientes por si solas.

---

## Comparacion antes/despues (Fase 9)

| Aspecto | Pre-Fase 9 (coral, vaca_muerta) | Post-Fase 9 (football) |
|---------|-------------------------------|----------------------|
| CF2 exam_wording | FAIL | **PASS** |
| CF5 toy_comparison | FAIL | **PASS** |
| CF3 mismatch | FAIL (vaca_muerta) | **PASS** |
| CF4 variable_leak | FAIL | **FAIL (persiste)** |
| D4 validez comparacion | 0 | 1 (mejoro pero no resuelto) |
| H1 variables-como-codigo | Presente | **Presente** |
| H2 framing "set X to Y" | Presente | **Presente** |
| H5-H8 (nuevos de Codex) | No evaluados | **Presentes** |

**Conclusion**: Fase 9 elimino los defectos mas obvios (CF2, CF5, CF3). Los
problemas restantes son mas profundos y apuntan a la raiz: las preguntas se
generan desde la ontologia del evaluador, no desde la investigacion.

---

## Prioridades derivadas de esta evaluacion

### Prioridad 1 (raiz): preguntas desde la investigacion, no desde el scorer
- I10 Fase 3: orchestrator piensa que preguntaria un investigador, despues mapea
- Elimina H8 (eval_ontology_leak) y reduce H1, H2, H5
- Es el cambio con mas impacto pero el mas grande

### Prioridad 2 (cosmetic + structural): variable naming + framing
- CF4 + H1: usar semantic names en templates, no node IDs
- H2: reescribir framing "set X to Y" a contrafactuales naturales
- Necesario incluso si se hace Fase 3 (los fallback templates lo necesitan)

### Prioridad 3 (epistemic): respuestas realistas + identification
- H3: ecuaciones SCM que produzcan mediaciones parciales e interacciones no-cero
- H5: el caso deberia plantear el problema de identificacion, no asumirlo
- H6: measurement provenance en el briefing

### Prioridad 4 (data): indexing + metadata
- H7: agregar llaves naturales del dominio (player_id, match_id, etc.)
- H4: reducir metadata explicita en el briefing

### Pendiente: no-data baseline probe (CF1)
- Correr el probe formal con los SRCs actuales
- Generar 2-3 SRCs mas con sistema actual (n=1 insuficiente)
