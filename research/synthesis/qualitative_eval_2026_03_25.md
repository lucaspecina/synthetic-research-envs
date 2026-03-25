# Evaluacion cualitativa formal — 2026-03-25

> **Commit base:** 00a830c + mini-fixes (entity check, desired_state cleanup)
> **Evaluadores:** Claude (principal), Codex (review critico)
> **Branch:** feature/scm-engine

## SRCs evaluados

| ID | Dominio | Seed | Nodes | Tasks | Eval types |
|----|---------|------|-------|-------|------------|
| eval_football | Football / sports science | football.md | 12 | 5 | causal_effect, best_intervention, interaction, mediation, infer_latent_cause |
| eval_coral | Marine ecology / reef | coral_reef_bleaching.md | 13 | 5 | causal_effect, ate, compare_interventions, mediation, infer_latent_cause |
| eval_asthma | Public health / epidemiology | pedersen_2024_air_pollution_asthma.pdf | 10 | 4 | causal_effect, compare_interventions, interaction, infer_latent_cause |

## Scoring por dimensiones (0 = falla, 1 = mixto, 2 = convincente)

| Dimension | Football | Coral | Asthma | Notas |
|-----------|----------|-------|--------|-------|
| D1 Framing real | 2 | 2 | 2 | Briefs profesionales, suenan a encargo real |
| D2 Data necessity | 1 | 1 | 1 | Direccion causal obvia desde priors; magnitud necesita datos |
| D3 Coherence | 2 | 2 | 2 | Brief, deliverables, questions alineados |
| D4 Comparison validity | 1 | 2 | 2 | Football: lever downstream invalida comparacion |
| D5 Data realism | 1 | 1 | 1 | Panel/missing/proxies OK, pero metadata clonico y descripcion mecanica |
| D6 Epistemic richness | 1 | 1 | 1 | Interacciones siempre "no", mediacion = 1.0 |
| D7 Investigative workflow | 1 | 1 | 1 | Agenda prearmada, no hay investigacion abierta |

**Score promedio:** 1.3 / 2.0

**Scores ajustados por Codex:** D4 football baja a 1 (lever downstream), D5
baja a 1 (metadata clonico), D7 baja a 1 (agenda prearmada). Claude habia
puesto 2 en D4/D5/D7 inicialmente — Codex tenia razon.

## Critical failures

| CF | Football | Coral | Asthma | Notas |
|----|----------|-------|--------|-------|
| CF1 answerable_without_data | PARCIAL | PARCIAL | PARCIAL | Direccion si, magnitud no. No-data probe pendiente |
| CF2 exam_like_wording | PASSED | PASSED | PASSED | **Gran mejora vs pre-I10** |
| CF3 brief_eval_mismatch | PASSED | PASSED | PASSED | |
| CF4 variable_name_leak | PASSED | PASSED | PASSED | **Gran mejora vs pre-I10** |
| CF5 toy_comparison | FAIL (P4) | PASSED | PASSED | Football: downstream variable como lever |
| CF6 narrative_as_skin | PASSED | PASSED | PASSED | |

## Problemas encontrados

### P1. Interaction siempre "no" (2/2 SRCs con interaction) — BLOCKER

**Evidencia:** Football Q3 = {"no": 1.0}, Asthma Q3 = {"no": 1.0}. Coral
no tiene interaction question.

**Causa raiz (verificada):** Las ecuaciones del SCM a veces SÍ tienen
terminos multiplicativos (coral: `thermal_stress * branching_cover`, asthma:
`obesity * inactivity`). Pero `_find_modifier()` elige el modifier al azar
entre candidatos plausibles — **no verifica si la ecuacion tiene un termino
de interaccion entre treatment y modifier**. Resultado: siempre elige pares
sin interaccion real.

Ademas, el orchestrator (LLM) tiende a generar ecuaciones aditivas. Los
terminos multiplicativos son la excepcion.

**Impacto:** el eval type interaction no discrimina. Un solver que siempre
dice "no" gana sin investigar.

**Solucion propuesta:** quality gate en task gen — si no encuentra par con
interaccion real, no generar la pregunta. Ademas, guiar al orchestrator
para que genere mas interacciones en las ecuaciones.

### P2. Metadata identica en todos los SRCs — ALTA

**Evidencia:** Los 3 SRCs dicen textualmente "500 observations. Collected
from 4 sites. 3 measurement waves." Misma estructura, misma frase.

**Causa raiz:** `PanelConfig` defaults en orchestrator.py hardcodean
`n_waves=3` y `n_sites` se calcula pero el resultado es siempre el mismo
para 500 rows. La descripcion del dataset es un dump tecnico generado en
`_describe()`.

**Impacto:** olor sintetico inmediato. Un solver entrenado detectaria la
estructura clonico. La descripcion mecanica rompe la experiencia investigativa.

**Solucion propuesta:** variar panel config por SRC (3-15 sites, 2-5 waves,
200-2000 obs). Reescribir `_describe()` para generar descripcion narrativa.

### P3. Mediacion = 1.0 exacto (coral) — MEDIA

**Evidencia:** Coral Q4: "To what extent does bleaching severity mediate the
effect of thermal stress on reef recovery?" → value: 1.0000 (100%).

**Causa raiz:** `cumulative_thermal_stress` afecta `reef_recovery_score`
SOLO a traves de `bleaching_severity` (cadena lineal). La mediacion total
es trivial — si hay un solo camino, todo pasa por ahi.

**Impacto:** respuesta obvia sin datos. No discrimina.

**Solucion propuesta:** quality gate que rechace mediacion ~0 o ~1 (buscar
pares con mediacion parcial interesante, ej 0.2-0.8).

### P4. best_intervention incluye variables downstream — BLOCKER

**Evidencia:** Football Q2 lista `second_half_physical_drop` como lever
posible. Es un outcome intermedio, no algo intervenible.

**Causa raiz:** el sistema no distingue "observable" de "intervenible". Para
el, todo lo observable es un lever valido.

**Impacto:** rompe validez cientifica. Un investigador cuestionaria la
premisa.

**Solucion propuesta:** clasificacion de variables: exogenas (intervenibles),
endogenas (consecuencias), target. Solo ofrecer exogenas como levers.
Requiere metadata en VariableMeta o inferencia desde el DAG (roots y nodos
sin padres causales = exogenos).

### P5. Direccion causal obvia desde priors — CRITICO (LA PREGUNTA)

**Evidencia:** Los 3 Q1 piden efectos cuya direccion es sentido comun:
- Football: "mas carga → mas decline" (obvio)
- Coral: "mas estres termico → menos recuperacion" (obvio)
- Asthma: "mas screening → menos mortalidad" (obvio)

**Causa raiz:** los SCMs usan relaciones que siguen la intuicion del dominio
(porque el orchestrator las diseña basandose en conocimiento real). No hay
confounders que inviertan la direccion, ni relaciones contraintuitivas.

**Impacto:** el mas importante para LA PREGUNTA. Si un solver puede acertar
la direccion sin datos, no estamos forzando investigacion.

**Solucion propuesta (no mutuamente excluyentes):**
- Mundos ficcionales donde las relaciones no siguen la intuicion (A3/I2)
- Confounders que invierten la direccion observada (Simpson's paradox)
- Efectos no monotonicos (dosis-respuesta con umbral)
- Preguntas donde la direccion es genuinamente incierta
- No-data probe formal para medir la magnitud del problema

### P6. Dataset description mecanica — ALTA

**Evidencia:** "Columns: county_healthcare_capacity, physical_inactivity_rate_index..."
y "Missing data: 14%." — dump tecnico, no descripcion de investigador.

**Causa raiz:** `_describe()` en `scm_data.py` genera un resumen tecnico
de las columnas, no una narrativa sobre provenance, limitaciones, o contexto
de la recoleccion.

**Impacto:** rompe la experiencia investigativa. Un investigador real
recibiria "el dataset integra registros administrativos con encuestas de
comportamiento..." no una lista de columnas.

**Solucion propuesta:** que el orchestrator o un paso post-generacion
escriba una descripcion narrativa del dataset, similar a como un paper
describe sus datos en la seccion Methods.

## Problemas profundos (estructurales, no fixes rapidos)

### S1. Identificacion causal regalada

Las preguntas piden ATE/mediacion sobre datos observacionales como si la
identificabilidad fuera gratis. Un investigador real primero tiene que
justificar POR QUE puede estimar el efecto causal (confounders, instrumentos,
discontinuidad). SREG no evalua esta justificacion.

**Conecta con:** vision Open Investigation (A15), dimension "warrant".

### S2. Agenda prearmada

El solver recibe 4-5 preguntas formuladas. No descubre que preguntar.
La calidad de investigacion incluye la calidad de las preguntas que el
investigador se plantea.

**Conecta con:** vision Open Investigation (A15), modos Scaffolded y Open.

### S3. SCMs tienden a ser aditivos

El orchestrator (LLM) genera ecuaciones mayormente lineales aditivas.
Interacciones, umbrales, saturaciones y no-linealidades son la excepcion.
Esto limita la complejidad investigativa.

**Conecta con:** mejorar prompts de scm_construct, o post-procesamiento
que inyecte complejidad.

## Comparacion con evaluacion anterior (2026-03-24)

| Aspecto | Pre-I10 (2026-03-24) | Post-I10 (2026-03-25) |
|---------|---------------------|----------------------|
| Wording de preguntas | Tipo examen ("Answer A or B") | Natural ("Which would yield...") |
| Snake_case leaks | Frecuentes (H1, 3/3 SRCs) | Eliminados |
| Brief-eval coherence | Desconectados | Alineados |
| Monocultura eval types | 5/5 SRCs mismo patron | 7 tipos distintos en 3 SRCs |
| Variable name leaks | CF4 triggered 3/3 | CF4 passed 3/3 |
| Interacciones | No evaluado | Siempre "no" (P1 nuevo) |
| Downstream levers | No evaluado | Detectado (P4 nuevo) |
| Direccion desde priors | Sospechado | Confirmado (P5) |

**Veredicto:** mejora significativa en capa visible. Los problemas actuales
son mas profundos y fundamentales — ya no es "olor a examen" sino "esto
todavia no obliga a investigar como cientifico".

## Siguiente paso: no-data baseline probe

Pendiente: darle los 3 briefings (sin datasets) a un LLM y medir si puede
responder correctamente las preguntas. Esto cuantificaria P5.
