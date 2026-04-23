# Rethink SREG — Sesión 2026-04-19 → 2026-04-23

> **Estado:** Working notes. Captura el hilo de rediseño arquitectónico de SREG
> iniciado 2026-04-19 (sesión compiler-fix) y continuado 2026-04-23 con
> propuesta formal del usuario + findings de Corral (Jablonka et al.).
>
> **No es canon.** Es trabajo en curso. Cuando consolidemos decisiones,
> promoverlas a `research/synthesis/` y actualizar `PROJECT.md` / `ARCHITECTURE.md`.

---

## 0. Resumen ejecutivo

Estamos rediseñando el flujo de SREG desde primeros principios, motivados por:

1. **Compiler frágil**: Suite 2 effective pass 31%. Toda la capa NL↔IR
   (AtomicSpec con ~5600 combos teóricos) es el bottleneck del ceiling,
   no el verifier matemático.
2. **Mundos superficiales**: SCMs producen DAGs con ruido lineal, sin
   feedback / teoría / dinámica. Un científico real no investiga mundos así.
3. **Paper Corral** (arXiv:2604.18805, abril 2026, 25k runs): validación
   empírica externa de LA PREGUNTA de SREG. 41.4% de la varianza es el
   modelo base, 1.5% el scaffold. Incluye metodología completa de anotación
   epistemológica con 95.7% agreement LLM↔humano.

Dirección consensuada hasta ahora (usuario + Claude + Codex):
- **Matar el compiler runtime** (SQ compiler + claim compiler + IR rica).
- **Conservar el verifier matemático** pero relocalizarlo al **diseño de
  caso** (explorar el mundo para generar buenas Q/SQ) y como **sentinel
  anti-hallucination** en runtime para claims cuantitativos explícitos.
- **Scoring por rúbricas graduadas + LLM-judge anclado al mundo**. Judge
  descompuesto en 6-10 criterios auditables (no holístico), agregación
  determinística.
- **Abrir a dominios dinámicos** (ODEs/SDEs) como segundo tipo de mundo,
  con la misma arquitectura de evaluación.
- **MVP sobre 1 dominio SCM + 1 dominio ODE**, 50-100 mundos, 3 modelos
  frontier, publicable en 2-3 meses (a validar factibilidad).

---

## 1. Contexto conversacional (2026-04-19 → 2026-04-23)

### Arranque (2026-04-19)

Usuario planteó: "Creo que estamos llegando a dead ends con el tema del
compiler, mundos sin sentido, mundos superficiales". Pidió repasar el
flujo desde cero, quizás simplificarlo.

Identificamos 3 síntomas separados:
1. Mundos superficiales (SCMs lineales ruidosos sin teoría).
2. Compiler cuello de botella (síntoma de #1: extraer IR rica de prosa
   libre es frágil; si los mundos fueran más ricos, los claims serían
   más significativos).
3. IR forzando forma causal-experimental (no encaja con investigaciones
   descriptivas / system mapping / epistemológicas).

### Debate de arquitectura

Exploramos dos caminos extremos:
- **A (hoy)**: solver libre + compiler LLM adivina estructura. Frágil.
- **B (primera propuesta)**: solver con tools estructuradas
  (`submit_prediction(...)`). Robusto pero overfit al formato nuestro.

Usuario cazó el problema de overfit al formato: agente entrenado sobre
SREG aprendería a llenar nuestros JSONs, no a comunicar como paper real.
Transfer se degrada.

Clave del usuario: **"el problema no es el verifier sino el COMPILER"**.
El verifier matemático funciona bien; lo que falla es traducir NL↔IR en
ambas direcciones (SQ→specs y claim→specs).

Con esta clarificación, evolucionamos a:
- **C (propuesta actual)**: rúbricas + LLM-judge anclado en answer keys
  ricos del SCM. El verifier matemático se mantiene pero se usa:
  (a) durante el diseño del caso, (b) como sentinel en runtime.

### Consulta a Codex (gpt-5.4 xhigh reasoning)

Codex coincidió con la dirección pero introdujo refinamientos clave:

1. **NO hacer judge holístico**. Descomponer cada rúbrica en 6-10
   criterios explícitos y auditables, cada uno con evidencia esperada +
   anchor del SCM. Agregación determinística (el código suma; el LLM no).

2. **Verifier NO sale 100% del runtime**. Mantener rol angosto de
   **guardrail/sentinel** para claims cuantitativos explícitos,
   direccionales fuertes, identifiability/confounding cuando hay patrón
   detectable. No scorer principal — auditor del judge y anti-hallucination.

3. **Calibración externa crítica** (mis mitigaciones eran insuficientes):
   - Dev/test set humano congelado.
   - Versionado estricto prompt + modelo + rúbrica.
   - Evaluación por criterio (no solo score final).
   - Adversarial evals de prose hacking.
   - **Obligar al judge a citar evidencia textual/artifact_id para
     acreditar un criterio.**

4. **Gotchas reales**:
   - **Ontology leak 2.0**: si las preguntas nacen del scorer (rúbrica
     pre-computada), el solver juega la rúbrica, no investiga. Vuelta a
     examen disfrazado. Necesita "novel-but-correct lane".
   - Checklist completion vs discovery.
   - Reward drift entre versiones de rúbrica/judge.

5. **Preservar a toda costa**: el oracle SCM-grounded en diseño.
   "Si perdés eso, SREG deja de ser scientific judgment grounded in a
   world y pasa a ser otro benchmark de LLM-as-judge con mejor narrativa."

**Veredicto Codex**: *"Matá el compiler runtime, conservá el oracle SCM,
y construí scoring rubricado, criterial y auditable."*

### Paper Corral (integrado 2026-04-23)

Usuario trajo Corral (Jablonka et al., arXiv:2604.18805, abril 2026).
Se leyó synthesis completo y chunks del paper.

**Hallazgos más relevantes para SREG:**

- **Varianza**: model 41.4% / scaffold 1.5% / verbosity 0.1%.
  "Scaffold doesn't fix reasoning; training does." Evidencia empírica
  más fuerte publicada hasta hoy de que el training target es necesario.

- **3 fallos epistemológicos cuantificados en 773 traces anotadas**:
  - 68% evidence non-uptake (recolectan evidencia y no la usan)
  - 53% untested claims (hipótesis sin experimentos)
  - 71% belief never updated
  - Solo 26% refutation-driven belief revision
  - Solo 7% convergent multi-test evidence

- **Metodología de anotación epistemológica** (directamente adoptable):
  - 6 nodos: Hypothesis, Test, Evidence, Judgment, Update, Commitment
  - 6 edges: testing, observing, using, contradicting, competing, updating
  - 7 productive motifs (razonamiento sano)
  - 10 breakdowns (razonamiento roto)
  - Validation: 95.7% human-LLM agreement, 92.6% human-human (PABAK 0.853)
  - Código MIT en `lamalab-org/corral/analysis/`

- **Intervention experiment**: inyectar trayectorias exitosas al contexto
  no mejora hypothesis-driven performance → in-context learning no basta.

**Implicación arquitectónica**: los 6 nodos + 7 motifs + 10 breakdowns de
Corral **pueden ser la espina dorsal de nuestras rúbricas**. Codex proponía
"6-10 criterios auditables"; Corral ofrece exactamente eso, validado con
95.7% agreement humano, y MIT license.

**Diferencial SREG vs Corral**:
- Corral: *te dicen qué investigar* ("identificá este cation"). Mide
  razonamiento sobre problema definido.
- SREG: brief abierto. Agente decide **qué** investigar + cómo. Mide
  razonamiento + **framing**.
- Son jerarquía, no competencia. Corral valida el nivel n; SREG apunta
  al nivel n+1 (definir el problema).

### Propuesta formal del usuario (2026-04-23)

Usuario dropeó propuesta estructurada de 5 etapas (ver sección 3 abajo).
Abierta a debate — no es mandato, es material de discusión.

---

## 2. Estado del código actual (para referencia)

Leído completo en esta conversación:
- `orchestrator/orchestrator.py` + `orchestrator/prompts.py`
- `models/scm_spec.py` + `models/case_plan.py` + `models/open_investigation.py`
- `tools/scm_world_gen.py` + `scm_task_gen.py` + `scm_problem_builder.py`
- `tools/oi_sq_compiler.py`, `oi_extraction.py`, `oi_prompts.py`,
  `oi_verifier.py`, `oi_compiler.py`, `oi_runner.py`, `oi_driver.py`,
  `oi_relevance_judge.py`, `oi_sq_matching.py`

Pendiente de leer (para decisión final):
- `world/scm.py`, `world/scm_data.py`, `world/expression_compiler.py`
- `solver/scm_solver.py`, `agent/engine.py`, `agent/python_exec.py`
- `inference/*`, benchmarks externos

### Flujo actual (simplificado)

```
Orchestrator LLM (loop de hasta 15 iteraciones con function calling)
  ├─ scm_construct(variables, edges, equations)      # LLM imagina
  ├─ world_check (sampling sanity check)              # determinístico
  ├─ apply_semantics (title, domain, theoretical_ctx) # guarda, no usa
  ├─ design_case → produce research_brief + SQs text_gloss
  │     └─ _compile_oi_subquestions:
  │         Phase 1: text_gloss → AtomicSpecs (LLM + grammar_ref)
  │         Phase 2: ground → verify_atom → answer_key_rich (detail)
  └─ build_problem (sample data + datasets)

Solver (python_exec libre)
  └─ submit_claims(list[ClaimCard])  # prosa libre

Compile claims
  └─ compile_claim_direct: LLM con grammar_ref → AtomicSpecs

Score
  ├─ Truth: verify_atom por spec → solver_assertion_holds (booleano)
  │         Claim truth = proporción de specs que holds
  ├─ Relevance: LLM-judge (claim_text vs SQ text_gloss, con answer_key
  │             como contexto pero INSTRUIDO a "no juzgar correctness")
  └─ Total = correctness × weighted_coverage
```

**Dos LLM-judges ya existen**:
- `oi_relevance_judge.py`: pairwise claim × SQ → relevance 0-1 con rúbrica
  explícita (0.9-1.0 directo, 0.7-0.8 major aspect, etc.).
- Answer keys ricos (measurements, comparison_result) ya computados pero
  usados solo como contexto, no como anchor del score.

**El rethink NO empieza de cero**: ~75% de la arquitectura propuesta ya
está esquematizada en el código. Falta: (a) cerrar el ciclo del judge
sobre truth, no solo relevance, y (b) convertir SQs en rúbricas graduadas.

---

## 3. Propuesta del usuario (5 etapas) — versión 2026-04-23

> Captura textual para preservación. Ver sección 4 para análisis técnico.

### Tesis de la propuesta

El gap crítico en capacidad científica de los agentes AI no es
razonamiento puro sino **juicio investigativo**: qué examinar, cuándo
pivotar, cómo separar evidencia del caso específico de priors del training.

### Las 5 etapas

**Etapa 1: Construcción del mundo + exploración iterativa.**
- A partir de un seed paper inspirador, se construye iterativamente
  un mundo sintético mientras se buscan regiones con cosas interesantes.
- "Interesante" = relaciones contraintuitivas, baja identificabilidad
  estructural, regímenes cerca de bifurcaciones, correlaciones espurias
  fuertes que desvíen al agente.
- Construcción y búsqueda de estructura ocurren **entrelazadas**, no
  secuencialmente. El mundo queda deliberadamente diseñado, no sampleado.

**Etapa 2: Generación de questions_gold.**
- Fijado el mundo, se generan preguntas cuya respuesta se conoce con
  exactitud (tenemos el modelo ejecutable).
- Preguntas validadas ejecutando el mundo: simular, intervenir, observar,
  confirmar que la respuesta gold es correcta y única.
- Cobertura de operaciones epistémicas: identificar relaciones causales,
  estimar parámetros, predecir efectos de intervención, distinguir
  hipótesis competing, detectar confounders, identificar mecanismos.

**Etapa 3: Presentación al solver.**
- Brief con contexto, datos observacionales ruidosos, tools de análisis
  y (opcionalmente) de intervención, consigna abierta tipo "investigá
  este sistema".
- questions_gold permanecen OCULTAS al solver.

**Etapa 4: Producción de claims.**
- Solver genera salidas libres en texto natural: hipótesis, conclusiones,
  estimaciones, inferencias estructurales, caveats.
- **No se pide formato específico de output.**

**Etapa 5: Validación híbrida ejecutable + LLM-as-judge.**
- LLM validador (más capaz que el solver) cumple dos funciones en paralelo:
  1. Identifica qué claims responden a qué questions_gold
     (cobertura/relevancia) y compara respuestas con gold de manera
     **estructurada pero flexible**.
  2. Tiene **acceso al mundo ejecutable**: puede correr simulaciones e
     intervenciones adicionales para testear claims espontáneas del
     solver más allá de las questions predefinidas.
- Score integra: cobertura de questions_gold + corrección de respuestas
  + validación empírica de claims adicionales.

### Rationale del rediseño

1. **Desacopla evaluación de formato**. Agente que razona bien pero
   formatea mal ya no pierde puntos por razones ortogonales.
2. **Captura claims cualitativas** ("el sistema tiene un confounder que
   no puedo observar", "parece no lineal en este rango pero no tengo
   data suficiente") que son típicas del científico real y se pierden en
   specs rígidas.
3. **No colapsa en "LLM opina sobre LLM"** porque el validador está
   anclado en el mundo ejecutable: no juzga si la claim es plausible, corre
   experimentos en el ground truth construido por nosotros.
4. **Libera del formalismo de verificación específico**. Mismo pipeline
   sirve para SCMs, ODEs, SDEs, agent-based, autómatas. Solo cambia el
   motor de simulación y la forma de las questions_gold.

### Extensión a sistemas dinámicos

- SCMs capturan equilibrio pero pierden: inferencia de escalas temporales,
  oscilaciones y ciclos, transitorios vs equilibrio, bifurcaciones,
  control óptimo temporal, análisis de señales ruidosas.
- do-calculus no se extiende limpiamente a dinámica; ODEs/SDEs tienen
  ecosistema fragmentado (identifiability, sensitivity, bifurcation,
  Lyapunov). Flujo ejecutable/judge disuelve esto: todo es "correr el
  integrador y comparar".
- Tareas dinámicas que abriría: farmacocinética, depredador-presa,
  reactores oscilantes (Hopf intrínseca vs forzado), filtrado de señales
  con jumps endógenos vs exógenos.

---

## 4. Análisis técnico de las 8 preguntas abiertas

### Q1 — Construcción iterativa del mundo

**Opción A (propuesta del usuario)**: generador propone mundos → scanner
los evalúa contra "interesting-ness" → selector acepta/rechaza.

**Opción B (propuesta del usuario)**: LLM diseñador directo con propiedades
target.

**Mi lectura**: ninguna pura. Híbrido: **un LLM diseñador con tools
ejecutables de evaluación**. El "scanner" vive dentro del diseñador como
tool calls. Arquitectura:

```
designer_loop:
  propose_scm(seed_paper) → candidate
  run_identifiability_check(candidate, target, obs_vars) → ok/not
  run_intervention_sweep(candidate, var, range) → effect_map
  run_confounding_scan(candidate) → list of spurious correlation strong
  run_bifurcation_scan(candidate, param, range) → bifurcation points
  if interesting criteria met: accept
  else: revise (LLM gets feedback, proposes mutation)
```

Las tools son reutilizables: los mismos primitives que el verifier usa.

**Bottleneck de complejidad**: definir operacionalmente "interesting-ness".
Propuesta concreta:
- `n_counterintuitive_relationships`: N relaciones donde el signo del
  efecto crudo (observational) difiere del signo ajustado (do).
- `identifiability_gaps`: N pares (treatment, outcome) no identificables
  desde observables.
- `bifurcation_proximity` (solo ODEs): distancia entre parámetros y el
  bifurcation manifold más cercano.
- `spurious_correlation_strength`: max correlación observacional entre
  pares no causalmente conectados.

Un mundo "interesante" tiene ≥ N=3 counterintuitives + ≥ 1 identifiability
gap + ≥ 1 spurious strong. Parametrizable.

### Q2 — Questions_gold: cantidad, generación, adversarial check

- **Cantidad**: 3-5 questions_gold core + espacio abierto para claims
  spontaneas del solver. Hoy tenemos 4-6 SQs; más es saturación.
- **Generación**: LLM dado el mundo (depende del dominio semántico). Pero
  cada question **debe validarse ejecutando**: si es "¿X causa Y?",
  correr intervention y verificar ground truth clara (efecto ≠ 0 con
  tolerancia). Descartar questions ambiguas.
- **Adversarial check**: **sí, absolutamente**. LLM sin los datos intenta
  responder desde priors. Si acierta, la question no mide investigación
  — mide prior. Descartar. Esto conecta directo con LA PREGUNTA:
  queremos separar "agente que investigó" de "agente que adivinó".

**Proposal concreta**:
```
generate_questions(world, seed_paper) → candidate_questions
for q in candidates:
  gold_answer = execute_world(q)
  prior_answer = llm_without_data(q, world_narrative)
  if prior_answer == gold_answer: discard (prior-answerable)
  if not gold_answer.is_unique: discard (ambiguous)
  else: accept
```

### Q3 — Validador: modelo, prompt, piloto

- **Modelo**: Corral usa Claude 4.5 Sonnet con 95.7% agreement humano
  en anotación estructural. Para comparación semántica puede ser
  ligeramente peor pero probablemente aún alto. GPT-5.4 y Claude 4.7
  también son candidatos con reasoning alto.
- **Prompt**: seguir approach Corral + dar answer_key rich como contexto
  anchor. Obligar a citar evidencia textual del reporte del solver para
  acreditar criterios. Schema estricto de output (JSON).
- **Piloto**: **sí**. 10-20 casos con 2 anotadores humanos expertos
  (domain + epistemología), comparar contra LLM-judge. Budget: ~2-4
  horas humano total si los casos ya están corridos. MUY barato relativo
  a lo que calibra.

Pipeline de anotación de Corral está MIT. Podemos adaptar sus prompts
directamente: `lamalab-org/corral/analysis/`.

### Q4 — Validación ejecutable de claims espontáneas

Templates limitados vs código arbitrario.

**Mi propuesta**: **empezar con templates**, agregar código arbitrario
después.

Set de templates (8-12 operaciones):
- `check_intervention_effect(var, value, outcome, expected_direction, tol)`
- `check_conditional_correlation(X, Y, Z, expected_sign, tol)`
- `check_non_linearity(var, outcome, range, form)`
- `check_time_scale(var, timescale, tol)` (ODEs)
- `check_identifiability(treatment, outcome, from_obs_set)` (bool)
- `check_mediation_fraction(treatment, mediator, outcome, expected, tol)`
- `check_bifurcation_existence(param, range)` (ODEs)
- `check_tail_behavior(var, tail_percentile, expected_value, tol)`

Si el claim no cae en ningún template: flag "unverifiable", no castigo
al score. El judge textual todavía puede evaluarlo cualitativamente.

Más tarde: código arbitrario en sandbox (validator-as-agent con python_exec
sobre el mundo). Costoso y potencialmente buggy, pero poderoso.

### Q5 — Scoring

**Multi-dimensional IRT-style** > suma ponderada. Razones:
1. Informativo para research (qué dimensión falla).
2. Permite identificar modelo bueno en estimación pero malo en detección
   de confounders.
3. Corral usa IRT con precedente validado.
4. Evita que un único score masque heterogeneidad entre capacidades.

**Dimensiones a separar** (alineadas con Corral y PROJECT.md):
- Framing (solo SREG): ¿identifica las preguntas correctas desde un brief
  abierto? (Para Corral esto no existe porque la tarea ya viene definida.)
- Identification: ¿reconoce relaciones estructurales?
- Estimation: ¿cuantifica efectos correctamente?
- Intervention prediction: ¿anticipa efectos de do-operations?
- Confounding detection: ¿identifica sesgos?
- Mediation analysis: ¿descompone mecanismos?
- Epistemological calibration: ¿sabe cuándo no puede concluir?
- Process quality (de Corral): ¿el trace muestra productive motifs vs
  breakdowns?

Reporte: vector de 8 dimensiones + agregado ponderado opcional para
comparación simple.

### Q6 — Portabilidad entre formalismos

Interfaz propuesta por usuario: `observe`, `intervene`, `simulate`,
`ground_truth_answer`. **Refinamiento necesario**:

```python
class World(Protocol):
    def sample_observational(
        self, n: int, t_eval: list[float] | None = None
    ) -> Data: ...
    def intervene(
        self,
        intervention: Intervention,  # polymorphic
        n: int,
        t_eval: list[float] | None = None,
    ) -> Data: ...
    def ground_truth(self, question: Question) -> Answer: ...
    def identifiability(
        self, target: str, from_obs: list[str]
    ) -> IdentifiabilityReport: ...

class Intervention:  # sum type
    PointIntervention(var, value)
    SustainedIntervention(var, value, t_start, t_end)
    TimeVaryingIntervention(var, trajectory_fn)
    StructuralIntervention(remove_edges, add_edges)
```

Para SCMs: `t_eval=None`, `SustainedIntervention` degenera a `Point`,
`simulate` no se usa.
Para ODEs/SDEs: `t_eval=[0, 1, ..., T]`, todas las interventions aplican.

**Casos que rompe la interfaz cruda del usuario**:
- Agent-based models con estado continuo (necesitás `step()`).
- Mundos con memoria perfecta (saltos en distribución después de observar).
- Mundos con agent-in-the-loop (otros agentes responden a las
  intervenciones).

Para el MVP: **solo SCM + ODE determinísticas + SDE con ruido aditivo**.
Agent-based queda para fase 2.

### Q7 — Literatura relevante

- **Corral** (Jablonka et al. 2026, arXiv:2604.18805):
  - **Reusar**: pipeline de anotación epistemológica
    (`lamalab-org/corral/analysis/`, MIT), taxonomía de 6 nodos + 7
    motifs + 10 breakdowns, IRT modeling approach.
  - **No reusar**: orquestación del agente (ellos tienen tarea definida,
    nosotros brief libre).
- **CLadder** (Jin et al.): benchmark, no framework. Tomar inspiración
  del Pearl ladder (associational / interventional / counterfactual)
  para estratificar questions_gold.
- **HypoBench / BLADE / DiscoveryWorld**: revisar para ver si tienen
  tools de identificabilidad o simulación reusables. Bajo prioridad vs
  Corral.
- **scipy.integrate, torchdiffeq, diffrax**: solvers para ODEs/SDEs.
  diffrax (JAX) si queremos gradientes para RL en el futuro.

### Q8 — MVP: 1 dominio SCM + 1 dominio ODE, 50-100 mundos, 3 modelos, 2-3 meses

**Lectura honesta**: ambicioso pero factible con disciplina de scope.

**Bottlenecks realistas**:
1. **Designer-con-interaction** (nuevo): 3-4 semanas.
   - Tools de interesting-ness + loop iterativo + validación de mundos.
2. **ODE engine** (nuevo): 2-3 semanas.
   - scipy.integrate.solve_ivp wrapper + contratos de mundo + sampling
     con ruido observacional.
3. **LLM-judge rubricado** (reescritura): 2-3 semanas.
   - Rúbricas graduadas + 8-12 templates de claim-validation +
     agregación + adversarial check.
4. **Adaptación de pipeline Corral** (integración): 1-2 semanas.
5. **Pilot humano de 10-20 casos**: 1 semana.
6. **Generación de 50-100 mundos + 3 modelos × E2E**: 2-3 semanas de
   cómputo, 1 semana de análisis.

Total: ~3 meses si trabajamos en paralelo algunas piezas. 4 meses con
margen. 2 meses es optimista — requiere que nada rompa.

**Sugerencia de scope incremental**:
- **Fase 0 (4-6 semanas)**: solo SCM (reusa lo que tenemos) + LLM-judge
  nuevo. Validar el approach de rúbricas antes de tocar ODEs.
- **Fase 1 (4-6 semanas)**: agregar ODE domain.
- **Fase 2 (4-6 semanas)**: SDE + dominio adicional + pulir paper.

Si Fase 0 no funciona (judge no calibra, prose hacking, ontology leak
2.0), no tiene sentido agregar ODE. Matar rápido.

---

## 5. Aclaración importante sobre Corral como validación

El 95.7% agreement humano-LLM de Corral se refiere a **anotación
estructural** del trace ("¿es este mensaje una hipótesis H? ¿este edge
es contradicting?"). Es una tarea de **labeling consistente** sobre
formato de razonamiento.

**NO valida directamente nuestra tarea**, que es más compleja:
- Comparación semántica entre claims en prosa y answer_keys del mundo.
- Graduación contra rúbrica con múltiples criterios.
- Ejecución de experimentos sobre el mundo para testear claims.
- Integración de cobertura + corrección + claims espontáneas.

Corral nos da **evidencia parcial** de que LLMs pueden hacer tareas de
juicio con alta consistencia humana, pero todavía necesitamos **nuestro
propio pilot** para calibrar el judge específicamente para lo que
nosotros queremos que haga. El piloto de 10-20 casos con anotación humana
**no es opcional**: es calibración dedicada.

## 6. Rúbricas: decisión (Codex consultado 2026-04-23, thread 019dbb51)

**Decisión**: **híbrido con core analítico**. No es A ni B puros.

```
score = core_analytic + epistemic_bonus

core_analytic (70-85% del score):
  - Criterios atómicos, acumulativos.
  - Cada criterio ligado a claim EXPLÍCITO del solver (span textual).
  - Verificables contra el mundo ejecutable.

epistemic_bonus (15-30% del score):
  - Caveats, identifiability, reconocimiento de límites, robustness.
  - Incertidumbre bien calibrada.
  - NO compensa errores del core: si el solver afirma causalidad
    equivocada, no se salva con caveats elegantes.

Niveles tipo BARS: solo como ANCLAS DE REDACCIÓN para el judge
(ayuda a encuadrar qué se espera), NO como mecanismo de puntuación.
```

### Gotchas no obvios (de Codex)

1. **Claim packing ("shotgun science")**: solver tira 20 afirmaciones,
   premio las correctas sin penalizar contradicciones → aprende a
   spamear. Mitigación: contradicciones explícitas restan.

2. **Overweight de lo fácilmente ejecutable**: el judge puede premiar
   lo que puede testear rápido y subpremiar insight real pero menos
   trivial de operacionalizar. Hay que reportar qué % del score viene
   de ejecución vs qué % de juicio textual.

3. **No-independencia entre criterios**: "identifica confounder" +
   "ajusta" + "cuantifica" suelen colapsar causalmente. Si sumás mal,
   doble-contás la misma comprensión. Necesitás ortogonalidad o
   descuento por correlación.

4. **Inestabilidad cerca de bifurcaciones** (solo ODEs/SDEs):
   tolerancias numéricas fijas pueden ser injustas. Bandas dependientes
   de sensibilidad local del mundo, no umbrales globales.

### Contra judge que "completa huecos"

Pipeline de 3 pasos:
1. **Extraer claims explícitos** del reporte del solver.
2. **Mapear a criterios** de la rúbrica.
3. **Verificar en el mundo** (ejecutando si es posible).

Cada criterio acreditado requiere **span textual citado** del solver.
Campo obligatorio: `supported_by_text: bool`. Sin span = 0. Instrucción
explícita al judge: "no inferir conocimiento no verbalizado".

### Anti ontology leak 2.0 — estrategias concretas

1. **No exponer la rúbrica completa al solver durante training**.
2. **Randomizar descomposiciones**: mismo fenómeno, múltiples rúbricas
   isomorfas. El solver no puede memorizar estructura del scorer.
3. **Reservar reward para claims novedosos validados** fuera de
   questions_gold. El bonus requiere verificación empírica en el mundo.
4. **Mundos gemelos/counterfactuales**: mismo patrón superficial, pero
   conclusiones distintas según estructura subyacente. El agente tiene
   que investigar para distinguir.
5. **Dimensiones latentes de juicio científico**: parte del score en
   cosas no directamente visibles como checklist.

### Frameworks académicos reusables

- **ECD** (Evidence-Centered Design, Mislevy): match más fuerte
  estructuralmente. Separa *claim model* / *evidence model* / *task
  model*. Calza con mundo ejecutable + judge con tools.
- **BARS** (Behaviorally Anchored Rating Scales): para escribir anclas
  conductuales claras por nivel/dimensión.
- **G-Eval** (arxiv 2303.16634): tomar form-filling y salidas
  estructuradas.
- **FLASK** (arxiv 2307.10928): descomposición por skills.
- Jönsson & Svingby 2007 (analytic vs holistic rubrics — revisión
  sistemática).
- Arieli-Attali et al. 2019 (rubric design empirical).
- HELM: menos directo. Sirve más para cobertura/metadata.

## 7. Puntos pendientes de decisión

1. **¿Arquitectura exacta del designer?** Hybrid con tools parece
   correcta, pero falta especificar iteraciones, criterios de
   terminación, fallbacks.

2. **¿Questions_gold generadas por LLM o por templates?** Default: LLM
   + adversarial check. Templates son más reproducibles pero limitan
   diversidad.

3. **¿Modelo del judge?** Claude 4.7 Sonnet, GPT-5.4, Claude 4.7 Opus.
   Costo y latencia importan para RL futuro. Piloto humano para validar.

4. **¿Cuál es el primer dominio SCM y el primer dominio ODE del MVP?**
   Criterios: (a) seed paper bueno disponible, (b) existe prior de LLM
   que podamos romper, (c) dominio semánticamente rico.

5. **¿Cómo medimos "éxito" del MVP?** Métrica de validación: agreement
   humano-LLM ≥ 90% EN NUESTRA TAREA (no la de Corral), ranking
   consistente de modelos, señal de RL utilizable (correlación
   score-capabilities IRT-style).

6. **¿Cómo implementamos las "múltiples rúbricas isomorfas" contra
   ontology leak?** Requiere diseño. Una opción: generar la rúbrica
   desde N templates equivalentes, elegir uno al azar por episodio.

## 6. Próximos pasos concretos

1. **Este doc es el punto de partida.** Si reinicia la conversación,
   abrir con este archivo.

2. **Actualizar MEMORY.md** ya tiene entrada de Corral (línea 14).
   Agregar pointer a este doc.

3. **Dialogar los puntos pendientes** (sección 5) con el usuario, uno
   por uno, antes de codear nada.

4. **Consultar Codex** sobre la arquitectura del designer y el scoring
   multi-dimensional una vez resuelto (5.1) y (5.5).

5. **NO codear todavía.** El riesgo de implementar antes de cerrar
   arquitectura es altísimo.

---

## 9. Nomenclatura v1.5 + separación de agentes (Codex 2026-04-23, thread 019dbb51)

### Nomenclatura refinada post-Codex

Codex identificó dos nombres que chirrían frente a convenciones externas:

- **World** → considerar alinear con **Environment** (SciGym, BoxingGym,
  DiscoveryWorld, Corral usan "environment"). Propuesta refinada:
  `WorldModel` para el artefacto causal/dinámico subyacente +
  `Environment` para su interfaz ejecutable. Interoperabilidad con
  benchmarks vecinos.
- **Question** es demasiado genérico (se confunde con prompts del brief,
  preguntas del investigator, consultas del evaluator). Usar
  `CanonicalQuestion` o `GoldQuestion` internamente.
- **Case** OK, aunque `ResearchCase` o `Brief` son alternativas más
  precisas si Case suena legal.
- El resto (Designer, Investigator, Claim, Evaluator, Verifier,
  Answer Key, Seed Paper) sigue bien.

Convenciones externas a respetar:
- Science-Gym / BoxingGym / DiscoveryWorld / Corral: `environment`.
- DiscoveryWorld: `environment` / `scenario` / `task`.
- ScienceAgentBench: `task` / `scoring_rubrics`.

**Matar sin duda**: `oi_*` prefix, `ClaimCard`, `AtomicSpec`,
`Suite 1/2/3/4`. Todo deuda semántica.

### Separación de agentes: 4 productores + 1 validador transversal

Codex colapsó 5 roles a **4 productores + 1 validador transversal**
(Adversarial Tester se absorbe en el Validator más amplio).

**Productores (secuenciales)**:
1. **World Architect**: seed paper → ecuaciones / DAG / dinámica.
   Solo matemática correcta + fidelidad al paper.
2. **Explorer**: ejecuta el world → descubre fenómenos interesantes
   (confounders, spurious correlations, non-linearities, bifurcations).
   Output: phenomena_manifest **con evidencia ejecutable** (scripts +
   resultados), no solo prosa.
3. **Question Designer**: manifest + paper + world → CanonicalQuestions
   con Rubrics + Answer Keys. Entrega mapeo `question → verifier_query`,
   no solo texto.
4. **Case Writer**: brief + contexto + narrativa. Vague, realista, no
   leak de las questions.

**Validador transversal**:
5. **Validator / Consistency Auditor**: chequea todo downstream —
   trivialidad (prior-solvability), leakage, internal consistency,
   answer-key/rubric alignment. **Puede invalidar outputs upstream**, no
   solo comentar.

Codex explícitamente descartó separar un "Difficulty Calibrator" todavía
(burocracia salvo que ya haya curriculum RL).

### Decisión de implementación: separación de etapas ya, mismo modelo

Codex rechaza dos extremos:
- Un solo Designer monolítico con prompt gigante (mezcla todo, imposible
  de debuggear).
- Cinco agentes autónomos plenos en v1.5 (overkill).

**Middle ground recomendado**:
- Separación de etapas **desde v1.5** pero con **el mismo modelo/
  orquestador**, distinto prompt por etapa.
- Cada etapa produce un **artefacto tipado** (Pydantic / JSON Schema):
  - `world_spec`
  - `phenomena_manifest` (con evidencia ejecutable)
  - `questions + rubrics + answer_keys`
  - `case`
  - `validation_report`
- Recién en v2 se decide qué etapa merece modelo/agente separado
  (cuando dolor específico lo justifique).

A favor: interfaces fijas temprano, debugging real, evita blob de prompt.
En contra: más plumbing ahora. Vale la pena — separar un monolito después
cuesta más.

### Gotchas críticos de separación de agentes

**Gotcha 1 — Error laundering** (el peor, no costo):
- Alucinación temprana entra al manifest, agentes downstream la tratan
  como hecho. Después todo parece consistente pero es falso.
- Mitigación: **cada handoff debe incluir evidencia ejecutable, no solo
  prosa**. Explorer no entrega "hay confounding interesante"; entrega
  script + resultado. Question Designer no entrega texto; entrega mapeo
  `question → verifier_query`. Validator puede invalidar upstream.

**Gotcha 2 — Optimización cruzada perversa**:
- Explorer empuja rareza. Adversarial Tester empuja dureza. Case Writer
  empuja realismo. Sin criterio global → casos "bonitos" pero
  irresolubles.
- Mitigación: criterios globales + Validator que rechaza casos que
  cruzan un umbral (ej. question válida pero answer_key inestable bajo
  ruido del world, o brief tan vago que ningún investigator razonable
  podría enmarcar el problema).

### Framework de multi-agente

- **AutoGen / CrewAI**: NO para esto. Buenos para demos chat-based,
  malos para pipelines tipados con validación dura.
- **LangGraph**: razonable (DAG / estado / retries).
- **Preferencia Codex (y Claude coincido)**: **sin framework pesado**.
  Python + Pydantic + JSON Schema + ejecutores explícitos + logs
  versionados de artefactos. "Tu problema es compilación de casos, no
  agents chatting."

## 10. Decisiones v1.5 — confirmadas (2026-04-23)

Nomenclatura FINAL:

```
Environment   = interfaz ejecutable del sistema (reemplaza "world" como
                convención externa — SciGym, BoxingGym, DiscoveryWorld,
                Corral usan "environment")
WorldModel    = artefacto matemático formal subyacente (SCM/ODE/SDE).
                Es lo que el Environment expone.
Designer      = LLM que diseña WorldModel + GoldQuestions + ResearchCase
                (antes orchestrator)
ResearchCase  = brief + datos + contexto + tools (antes ResearchProblem)
GoldQuestion  = pregunta canónica con Answer Key (antes SQ)
Rubric        = estructura graduada de evaluación por GoldQuestion
                (core_analytic 70-85% + epistemic_bonus 15-30%)
Answer Key    = respuesta numérica verdadera del WorldModel
Investigator  = LLM-agente que investiga (antes solver)
Claim         = cada afirmación del Investigator (antes ClaimCard)
Evaluator     = LLM que compara Claims con Rubrics + ejecuta Environment
                (antes judge / relevance_judge)
Verifier      = motor matemático que ejecuta queries en el Environment
                (determinista, no LLM)
Seed Paper    = el paper que inspira el caso
```

Muertes anunciadas:
- `oi_*` prefix en todos los archivos.
- `ClaimCard`, `AtomicSpec`, `PatternClass`, `Direction`, etc.
- `Suite 1/2/3/4` como naming.
- El compiler runtime entero (`oi_compiler.py`, `oi_extraction.py`,
  `oi_sq_compiler.py`).

### Separación de agentes — decisión FINAL

**4 productores en secuencia + 1 Validator transversal**:

1. **World Architect** — seed paper → WorldModel (ecuaciones/DAG/dinámica).
   Solo matemática correcta + fidelidad al paper.
2. **Explorer** — ejecuta el Environment → phenomena_manifest con
   **evidencia ejecutable** (scripts + resultados numéricos).
3. **Question Designer** — manifest + paper + world → GoldQuestions +
   Rubrics + Answer Keys. Entrega mapeo `question → verifier_query`.
4. **Case Writer** — ResearchCase con brief + contexto + narrativa.
   Vague, realista, sin leak de GoldQuestions.

**Validator transversal** (el 5to rol, integrando lo que antes era
"Adversarial Tester"):
- **Vista global del pipeline**: ve todos los artefactos juntos, no uno
  a uno. El punto del usuario ("habría que tener uno que sigue todo el
  contexto") — ESE es exactamente el rol. No es un checker local.
- **Responsabilidades**:
  - Trivialidad / prior-solvability (adversarial check — LLM sin datos
    no debe poder responder las GoldQuestions desde priors).
  - Leakage (el brief no revela las GoldQuestions).
  - Internal consistency entre manifest, questions, answer keys y case.
  - Answer-key/rubric alignment.
  - **Hackear el mundo y las preguntas** — explorar modos de falla.
- **Autoridad**: puede invalidar outputs upstream. No solo comentar.
  Gatilla re-iteración.

### Espíritu iterativo adversarial

Punto explícito del usuario: el pipeline **no es lineal one-shot**. El
Validator opera en loop iterativo con los productores upstream:

```
World Architect → Explorer → Question Designer → Case Writer
       ↑              ↑              ↑              ↑
       └──────── Validator ◄─── (puede invalidar cualquier etapa)
                                 (genera feedback concreto para revisar)
```

Cada etapa se re-itera hasta que el Validator approves. Esto encarece
cada caso pero sube la calidad significativamente. Está alineado con el
"diseño deliberado, no muestreado al azar" del rethink original.

### Implementación v1.5

- **Separación de etapas desde v1.5, mismo modelo base** (gpt-5.4 u
  Azure equivalent) con prompts distintos por rol.
- **Cada etapa produce artefacto tipado Pydantic**:
  - `WorldSpec` (ecuaciones, DAG, metadata)
  - `PhenomenaManifest` (con evidencia ejecutable)
  - `QuestionsBundle` (GoldQuestion + Rubric + AnswerKey)
  - `ResearchCase` (brief + contexto + datos)
  - `ValidationReport`
- **Sin framework pesado** (no AutoGen/CrewAI). Python + Pydantic +
  JSON Schema + logs versionados. Posible LangGraph si se necesita
  DAG/retries explícito — decidir al implementar.
- **Fase 0 del MVP**: solo SCM. Validar rúbricas + judge + pipeline
  ANTES de agregar ODE/SDE.
- **Fase 1**: ODE domain (farmacocinética propuesta).
- **Fase 2**: SDE + publicación.

## 11. Crítica macro del flujo + tipos de investigación cubiertos (2026-04-23)

### Dónde el flujo queda bien
Investigaciones con verdad matemática detrás: causalidad, dinámicas,
estimación de parámetros, identificación de mecanismos, confounders.
Encaja con investigación cuantitativa empírica (farmacología,
epidemiología, ecología, economía causal, control de sistemas). Natural
para dominios donde los papers reales tienen modelos matemáticos
explícitos.

### Dónde queda peor / no sirve
- Verdad puramente interpretativa o hermenéutica (significado cultural,
  histórico).
- Investigación cualitativa / teoría fundamentada.
- Estética o ética científica.
- **Diseño de experimentos**: en v1 no sirve porque no hay interacción
  tipo Sherlock con el entorno (solver tiene datos dados, no diseña
  estudios). Queda abierto para v2 con acceso interventivo iterativo.

### Ampliaciones que SÍ soporta el flujo
- **Investigación descriptiva**: "¿cómo se distribuye X?", "¿qué
  categorías hay?", "¿cuál es el patrón típico?" — el mundo da
  medias, varianzas, histogramas, clusters. Rúbrica: "¿identificó
  bimodalidad?", "¿cuantificó dispersión?", "¿reconoció outliers?".
  Perfectamente chequeable.
- **"Mejor marco conceptual para entender el sistema"**: menos
  interpretativo de lo que parece. Marcos tienen componentes
  estructurales verificables contra el DAG/ODE. "¿Es cadena causal o
  feedback loop?" es chequeable. "¿Es lineal o no-lineal?" también.
  Hay "mejor" y "peor" en función de qué estructura tiene el mundo.
  Un poco más subjetivo pero anclable.
- **Investigación predictiva**: trivialmente chequeable contra el mundo.
- **System mapping**: el DAG/ODE es ground truth.
- **Epistemológica** ("¿qué puedo concluir con estos datos?"):
  chequeable contra identifiability del mundo.

### Crítica punto por punto a los 5 riesgos identificados

**(R1) LLM judge sigue siendo LLM**. Usuario: "pero para cosas abiertas
siempre se va a requerir LLM que interprete y compare — sea en compilación
o comparación directa. Pedir exactamente un número va contra nuestra
filosofía abierta". **Aceptado**. El LLM no desaparece; lo anclamos en
ground truth ejecutable. Peor que determinístico puro, mejor que
compiler LLM frágil.

**(R2) Mundos diseñados con trucos**. Usuario: "no necesariamente.
Se inspira en papers reales — el anclaje es el paper, no 'pongamos
confounders a propósito'. Si el paper tiene confounders, está bien.
Si no, no". **Aceptado, yo lo había olvidado**. La inspiración en papers
es justamente la protección contra "mundos diseñados para trucos".

**(R3) Diseñador como nuevo bottleneck**. Usuario: "es la idea. Antes
también era bottleneck (el compiler también). Se mueve de un problema
intratable a uno tratable". **Aceptado**. El diseñador es más
ingenieriable que el compiler (tools de interesting-ness, iteración,
ejecución del mundo para validar).

**(R4) Gaming de rúbricas**. Usuario: "como con todo lo de rúbricas,
pero lo anclamos con el mundo subyacente ejecutable". **Aceptado
parcialmente**. El anclaje ayuda pero no elimina. Sigue siendo un
riesgo real. Estrategias de mitigación en sección 6.

**(R5) Demostrar que funciona**. Usuario: "esto es lo que tenemos que
probar". **Aceptado como tesis experimental del proyecto**. Es la
promesa a demostrar con benchmark before/after (Corral como métrica
externa posible).

### Conclusión macro
El flujo cubre genuinamente la mayoría de los tipos de investigación
que nos importan: causal, descriptiva, predictiva, system mapping,
epistemológica, incluso "mejor marco conceptual" con anclaje
estructural. No cubre diseño de experimentos (v2) ni investigación
puramente interpretativa (out of scope). Los riesgos son reales pero
todos tienen mitigaciones razonables o son parte de la tesis
experimental a validar.

## Referencias

- `research/synthesis/related_work_corral.md` (en worktree qwen-benchmarks):
  synthesis de Corral.
- `research/notes/corral_paper_fulltext.txt` (en worktree qwen-benchmarks):
  paper full text.
- arXiv:2604.18805 — Ríos-García et al., "AI scientists produce results
  without reasoning scientifically".
- `lamalab-org/corral` (MIT) — código del paper.
- PROJECT.md — LA PREGUNTA + presiones evolutivas.
- Esta conversación (Claude Code session, 2026-04-19 → 2026-04-23).
