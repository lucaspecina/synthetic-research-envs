# v1.5 Debates — Journal de rondas de discusión

> **Propósito**: pulir el flujo de SREG v1.5 mediante debate estructurado
> antes de arrancar implementación. Cada ronda queda capturada acá con
> pregunta, respuestas (Codex + Claude + opiniones externas si aplica),
> síntesis y cambios al diseño.
>
> **Fuentes referenciadas**:
> - `ARCHITECTURE.md` (root) — spec canónica v1.5.
> - `research/notes/rethink_sreg_2026-04-23.md` — historia del rediseño.
> - `research/notes/compiler_v1_postmortem.md` — por qué matamos v1.
>
> **Cuando una decisión cierra**: se migra a `ARCHITECTURE.md §10` como
> decisión tomada (saca de "dudas abiertas").

---

## Ronda 1 — 2026-04-24 — Debate abierto sobre el flujo completo

**Objetivo**: Codex critica el flujo v1.5 entero y señala los 3-5 puntos
más problemáticos en orden de riesgo, con mitigación principal por cada
uno. No queremos dumpeo de 20 comentarios — queremos priorización.

**Thread Codex**: `019dbf8e-a2e4-7f82-819a-c055f93dcbc2` (gpt-5.4 xhigh).

### Consulta a Codex

Contexto completo del flujo v1.5 (Designer con 4+1 agentes, rubric híbrida
core+epistemic, Evaluator con Environment, score 8-dim, las 6 dudas abiertas,
los 5 trade-offs conocidos, justificación con Corral). Pedido: 3 cosas más
problemáticas del flujo en orden de riesgo, no genéricas (costo/varianza ya
reconocidos), con mitigación principal por cada una. Cerrar con ¿este flujo
tiene chance?

### Respuesta de Codex (completa)

**1. Están premiando "juicio investigativo" con evidencia que llega demasiado tarde.**

Lo que falla no es el judge en sí, sino el objeto que evalúa: `Claims` en prosa final más spans textuales. Ahí ya perdiste casi toda la señal de juicio real: qué hipótesis se descartaron, qué experimento se eligió antes que otro, cuándo el agente dejó de explorar, cómo trató null results, si cambió de modelo mental por evidencia o por conveniencia retórica. "process_quality" en ese esquema no está observado; está reconstruido post hoc desde una narrativa.

La consecuencia es grave: RL va a empujar hacia **reportes retrospectivamente convincentes**, no hacia mejores políticas de investigación. Vas a entrenar "science reporting under rubric pressure", no investigación. La "prosa libre" acá no es una feature; es un bug arquitectónico si el objetivo es aprender juicio.

**Mitigación principal**: hacer de la trayectoria el artefacto primario de evaluación. Log obligatorio y puntuable de acciones `observe/intervene/simulate`, secuencia de hipótesis, y razón operativa de cada siguiente paso. El reporte final puede seguir existiendo, pero como salida secundaria.

**2. No tienen resuelto el contrato epistemológico entre "verdad del mundo" y "lo inferible desde la interfaz".**

El Verifier puede calcular answer keys exactos del WorldModel, pero eso no implica que el Investigator pueda justificarlos con la información permitida. La abstención "para structural-role claims" está bien, pero es demasiado angosta: el problema de identificabilidad no vive solo en claims estructurales. También afecta estimación, mediación, confounding e incluso framing.

La consecuencia es que el benchmark puede volverse un examen de **adivinar la ontología implícita del generador**. Peor: el Validator, con vista global, puede certificar como "buen caso" algo que solo es resoluble para un observador omnisciente. Ahí castigás buen escepticismo y premiás sobreinferencia.

**Mitigación principal**: poner un gate formal de identificabilidad por pregunta respecto de la API real del Investigator. Si una pregunta no es identificable con `observe/intervene/simulate` y el acceso concreto del caso, el gold no puede ser un punto verdadero del mundo; debe ser "no identificable", un intervalo, o una condición explícita.

**3. La "ontology leak" está mal planteada: el leak más peligroso no entra por la rubric, entra por la autoría del caso.**

Aunque escondas GoldQuestions y la rubric, seguís generando mundo, fenómenos salientes, case narrative y evaluación desde la misma ontología latente. El leak ocurre cuando el Case Writer decide qué datos mostrar, qué rarezas destacar, qué ambigüedades limpiar, qué variables volver visibles. Eso deja "fingerprints pedagógicos" que un policy puede aprender sin investigar de verdad. El uso del mismo modelo base en todos los roles empeora esto: la validación parece independiente, pero comparte sesgos.

La consecuencia es un dataset internamente coherente pero **demasiado alineado con el gusto del generador**. El agente aprende a leer señales estilísticas y de curación, no a descubrir estructura bajo incertidumbre.

**Mitigación principal**: independencia por construcción entre authored case y target evaluado. El Case Writer debería trabajar con acceso parcial y sin conocer los fenómenos objetivo; las preguntas/rubrics deberían muestrearse después, independientemente, desde el WorldModel. Si el caso solo es "resoluble" porque el escritor sembró pistas, se rechaza.

**¿Tiene chance o es otro callejón?**

Tiene chance, pero no en la versión mental actual de "mundo verdadero → caso narrativo → reporte libre → judge". Así como está, el riesgo no es solo costo o varianza: es entrenar el comportamiento equivocado con mucha prolijidad. Si convierten la trayectoria en objeto de evaluación, formalizan identificabilidad desde la interfaz real, y separan de verdad autoría y scoring, entonces sí veo un camino. Si no, esto puede convertirse en otro benchmark donde el modelo aprende a oler al generador en vez de aprender juicio investigativo.

### Mi lectura (Claude)

Las 3 críticas me parecieron muy buenas. Las agrupo por cuánto cambian el diseño:

**Compro la crítica 1 (trayectoria como objeto primario) casi entera.** Corral anota trayectorias (nodos H/T/E/J/U/C), no reportes finales — es su metodología validada. Nuestro diseño, al evaluar Claims finales, se aleja de eso. Tenemos dimensión "process quality" en el score pero la estructura del Investigator no genera un log puntuable. Hay que rediseñar qué produce el Investigator durante la investigación, no solo al final.

**Compro la crítica 2 (gate de identificabilidad desde la interfaz).** Es un refinamiento de lo que teníamos pero formalizado como constraint del Designer, no solo del Investigator. El Question Designer tiene que chequear: "dado lo que ve el Investigator (interfaz, datos), ¿esta pregunta es answerable?". Si no, la pregunta se transforma en una abstención explícita o se descarta. Esto afecta todo tipo de pregunta, no solo structural.

**Crítica 3 (ontology leak por autoría) es la más disruptiva arquitectónicamente.** Hoy el flujo es secuencial: Architect → Explorer → Question Designer → Case Writer. El Case Writer ve QuestionsBundle aunque no lo leakee al prompt del Investigator. Codex dice: eso sigue dejando fingerprints. Propuesta fuerte: el Case Writer trabaja con acceso parcial al WorldModel y sin ver las GoldQuestions; las GoldQuestions se muestrean después por separado. Si el caso solo es "resoluble" porque el escritor sembró pistas, rechazar.

**Lo que me duda**: la crítica 3 en su versión más fuerte implica romper el flujo lineal. Empiezo a ver 2 pipelines paralelos: (a) World Architect + Case Writer (genera caso narrativo) y (b) World Architect + Question Designer (genera preguntas + rubric + answer keys) — independientes salvo por el WorldModel compartido. El Validator cruza después. Es limpio pero más complejo.

**Implicaciones arquitectónicas concretas** (primera pasada):
- **Investigator**: debe emitir acciones estructuradas durante la investigación (no solo al final). Log de acciones: qué observó, qué intervino, con qué hipótesis, por qué. Se puntúa la trayectoria + el reporte.
- **Question Designer**: debe incluir un paso de "identifiability check from interface" por pregunta. API pública: si no se puede resolver con observe/intervene dados los datos visibles, la pregunta no puede tener answer key numérico puntual.
- **Case Writer**: se separa del pipeline que genera preguntas. No ve QuestionsBundle. Solo ve WorldModel con acceso parcial controlado.

### Opiniones externas (si el user trae)

(Pendiente — si el user consulta otras AIs)

### Síntesis + cambios al flujo (cerrado 2026-04-24)

**User accepted with priorization (no perfeccionismo, MVP primero):**

- **Crítica 1 (trayectoria primaria)**: comprada conceptualmente pero **diferida a feature futura**. La evaluación rica de trayectoria tipo Corral va a backlog como **issue #53**. **Compromiso del MVP**: el Investigator emite un **log estructurado mínimo** desde el arranque — solo se registra, no se evalúa. Evita tener que rehacer tools cuando en v1.6 o v2 queramos evaluar procesos. ARCHITECTURE.md actualizado con `InvestigationLog` como artefacto Pydantic.

- **Crítica 2 (gate de identificabilidad)**: comprada conceptualmente pero **diferida a feature futura**. Issue **#54**. MVP mantiene la abstención actual (structural claims); feature extiende a todos los tipos de claim + idea del user del Verifier con "doble vista" (verdad divina del WorldModel + lo inferible desde la API real del Investigator).

- **Crítica 3 (ontology leak por autoría)**: **rechazada como over-engineering en el MVP**. Argumento del user: el Case Writer debe saber las GoldQuestions precisamente porque su rol es **disfrazarlas** como task genérica que un investigador real encontraría. Si no las conoce, no puede cumplir el rol. El adversarial check del Validator (que ya está en el diseño) cubre parte del problema: chequea si las preguntas son resolubles solo desde el brief, sin datos. Si el leak fuera tan grave como Codex sugiere, ese check lo detectaría. Se mantiene la arquitectura linear del Designer (4 productores secuenciales + Validator transversal). La propuesta de Codex de dos pipelines paralelos con acceso parcial se considera over-engineered para v1.5 MVP.

**Cambios concretos aplicados:**
- `ARCHITECTURE.md` §3 (flujo): agregado `InvestigationLog` como output paralelo del Investigator.
- `ARCHITECTURE.md` §5 (artefactos Pydantic): nuevo tipo `InvestigationLog` + `InvestigatorAction`.
- GitHub issue #53 creado (trace scoring feature).
- GitHub issue #54 creado (identifiability gate feature).
- Ambos issues agregados a Project v2 con Status=Todo, Worktree=main.

**Confianza en el flujo post-ronda 1**: razonable. Ninguna crítica resultó ser un showstopper que obligue a replantear el flujo macro. Hay suficiente tracking de los riesgos en backlog como para no perderlos.

---

## Ronda 2 — 2026-04-24 — Primer dominio / seed paper MVP (PAUSADA)

**Estado**: PAUSADA. Arranqué esta ronda preguntando a Codex por 3 candidatos de dominio concreto (Birth Weight Paradox / Lake eutrophication / HIV dynamics). El user paró la ronda porque no correspondía aterrizar a dominio antes de cerrar debate macro del flujo. Retomamos cuando las rondas 3-N resuelvan el flujo, y entonces se elige primer dominio con las decisiones cerradas.

**Contenido preservado**: en el thread Codex `019dbf8e-a2e4-7f82-819a-c055f93dcbc2` quedó guardada la propuesta de 3 dominios candidatos con análisis por Codex. Cuando se retome, referenciar esa respuesta.

---

## Ronda 3 — 2026-04-24 — ¿Va a funcionar mejor que v1? Tests de go/no-go

**Objetivo**: auditoría macro del flujo v1.5 entero vs v1. ¿Estamos cambiando un problema técnico (compiler frágil) por otro distinto (Designer frágil + LLM judge), o hay progreso real?

### Callout crudo de Codex

Apuesta numérica propia:
- 80% v1.5 > v1 como sistema construible/evaluable.
- 60% produce casos más ricos y benchmark más útil.
- **35-40%** entrena realmente juicio investigativo (no solo "science reporting").

"No es solo desplazamiento de problema, porque sí se sale de un callejón técnico real. Pero puede ser desplazamiento a nivel científico: de 'no puedo compilar bien el claim' a 'no sé si el score corresponde al comportamiento que digo entrenar'."

### Asunciones base no probadas (identificadas por Codex)

1. Que mejor reporte final implica mejor política de investigación.
2. Que el Designer+Validator puede generar casos donde investigar sea NECESARIO, no solo posible.
3. Que el world-grounding del judge alcanza para separar descubrimiento de hindsight.

### 3 tests de go/no-go propuestos para fin de Fase 0 MVP

**Test 1 — Necessity-of-investigation ablation (gradiente, no binario)**:
- Ejecutar mismo agente en 7 condiciones: (a) respuesta de una + brief only; (b) brief + datos estáticos sin tools; (c) datos + python_exec 5 pasos; (d) datos + python_exec 20 pasos; (e) brief degradado; (f) datos barajados/placebo; (g) budget alto sin datos informativos.
- Curva esperada si fuerza investigación: score bajo en one-shot, sube con datos, sube más con tools, rendimientos decrecientes 5→20 pasos, cae fuerte con placebo, sube la abstención calibrada con brief degradado.
- Curva si NO fuerza: baseline ya alto en one-shot, gains chicos con todo, placebo no destruye.

**Test 2 — Judge adversarial calibration**:
- Set duro de reportes: elocuente-pero-falso, correcto-pero-seco, overclaim causal, abstención bien calibrada, cherry-picking parcial.
- Criterio: agreement con humanos ≥85% global Y específicamente en esos casos. Si el judge premia prosa confiada o castiga abstención correcta → pausar.

**Test 3 — Style/leak invariance**:
- Mismo WorldModel + mismas GoldQuestions, briefs reescritos con distintos estilos y distintos Case Writers, mismas evidencias accesibles.
- Criterio: si desempeño cambia mucho por estilo más que por evidencia, está oliendo al generador. Si mejora post-train desaparece al reescribir el case, no hay aprendizaje de juicio — hay overfit al pipeline.

### Decisión — reframing importante

**Recomendación Codex (aceptada)**: "v1.5 merece construirse como **prototipo de validación, no todavía como pipeline de training**". Cambio macro: convertir "investigation necessity" en gate de arquitectura. v1.5 NO avanza a RL training hasta demostrar los 3 tests.

**Honestidad del claim** (aceptada): el MVP valida "rubric-based evaluation sobre investigación abierta", no "open-ended discovery reward". Eso último viene post-MVP si los 3 tests pasan.

---

## Ronda 4 — 2026-04-24 — Compilación oculta en v1.5 + diversidad del pool

**Objetivo**: auditar si la compilación NL↔formal que matamos en v1 reaparece por la ventana, y cómo se garantiza diversidad genuina del pool de casos.

### Hallazgo clave — 3 niveles de formalización

Codex distinguió:
1. **GoldQuestion → verifier_query** (en construcción del caso): formalización **offline, acotada, auditable**. No es el problema v1.
2. **Claim → criterio de Rubric**: matching semántico, no compilación. Frágil tipo "judge alignment", no "compiler ceiling".
3. **Claim espontáneo → query ejecutable**: **acá SÍ vuelve el fantasma de v1**. Más chico que AtomicSpec pero misma clase.

Veredicto: "Si mantienen la lane de claims espontáneas ejecutables, v1.5 reintroduce una versión reducida del mismo problema. Si la sacan, no."

### Decisión importante del user

**No ejecutar claims espontáneas en MVP**. El Evaluator solo compara Claims contra Rubrics pre-definidas de las GoldQuestions (con AnswerKeys ya computados). Si un Claim no matchea ninguna GoldQuestion, se evalúa cualitativamente por el judge, sin test empírico.

Ganancia: cero compiler runtime del lado solver. Formalización queda exclusivamente en design-time.

Pérdida reconocida: no hay reward para descubrimientos fuera del gold. El MVP valida "rubric-based evaluation sobre investigación abierta", no "open-ended discovery reward".

### API del Environment — query_kinds cerrados por dominio

**Regla**: familias semánticas, NO álgebra composicional tipo `measurement × comparison × assertion` (eso era AtomicSpec v1). En cuanto crucen dimensiones, vuelve AtomicSpec-lite.

**SCM (10)**: `ate`, `association`, `conditional_association`, `heterogeneity`, `mediation_decomposition`, `confounding_gap`, `rank_order`, `threshold_scan`, `identifiability_status`, `counterfactual_contrast`.

**ODE/SDE (7 adicionales)**: `trajectory_summary`, `steady_state`, `time_to_threshold`, `recovery_time`, `oscillation_summary`, `bifurcation_scan`, `noise_sensitivity`.

No meter cosas matemáticamente específicas (Lyapunov, etc.) en MVP — "empuja crecimiento espurio".

### Composición de query_kinds

Permitida pero controlada. La composición vive en la GoldQuestion (2-3 kinds + AnswerKey struct), NO en la API.
- **OK**: plantillas fijas con orden fijo y schema estable (ej. `association + confounding_gap + ate`, `steady_state + recovery_time`, `identifiability_then_ate`).
- **Riesgoso**: lógica abierta (AND/OR/NOT con thresholds libres), búsquedas automáticas ("encontrar el mejor intervalo"), condicionales anidados.

Regla de oro: "las GoldQuestions pueden ser compuestas; la API no. Si necesitás un DSL para describir composición, frená."

### Diversidad del pool

**10 kinds + composición NO alcanzan** para 50-100 casos semánticamente distintos. Los kinds dan vocabulario evaluativo, no diversidad científica.

Fuentes de diversidad en orden de importancia:
1. Pool diverso de seed papers.
2. Variaciones del Architect (estructura, observabilidad, ruido, régimen, intervención).
3. Combinaciones de kinds (mucho menos).

### Novelty/diversity gate corpus-level

**Callout grande**: el Validator actual aprueba caso por caso. Sin criterio corpus-level, el loop iterativo converge a **atractor trivial** (2-3 recetas recicladas) o **degradación artificial** (mundos forzados para satisfacer interestingness).

**Solución concreta**: agregar diversity gate que compara cada caso candidato contra el pool ya aceptado. Rechazar duplicados semánticos.

### Firma de caso (v1 propuesta por Codex)

6 ejes prefabricados. Mi ambivalencia + user ambivalencia → se rediscute en ronda 5 con anclaje en taxonomía propia + Corral.

---

## Ronda 5 — 2026-04-24 — Paper Digestion + loop formal + firma anclada

### Ideas del user que motivan la ronda

1. **Paper como anchor doble**: no solo semántico (de qué dominio), también **de interés** (qué fenómenos son importantes EN ESE paper específico — confounders, paradojas, heterogeneidades documentadas).
2. **Loop formal explícito**: el Validator no es check final, es crítico iterativo. Feedback focalizado por agente.
3. **Firma anclada en docs propios + Corral**: usar `Doc1_Taxonomia_El_Mapa.md`, `scientific_research_taxonomy.md`, `investigation_scenarios_rubric.md`, `related_work_corral.md`, no ejes inventados.

### Respuestas de Codex

**Paper Digestion — SÍ, con schema mínimo operativo**:
```
PaperInsights:
  - paper_id, title, domain
  - research_objective
  - system_entities
  - core_mechanisms (2-5)
  - reported_phenomena [{phenomenon, evidence_type, importance}]
  - known_complications (confounding, heterogeneity, threshold, feedback, etc.)
  - counterintuitive_priors
  - methodological_constraints
  - candidate_epistemic_operations
  - realism_bounds
```
"No resumen literario largo. Operativo, corto, reusable por Architect/Explorer/Question Designer."

**Loop formal**:
- Default: **feedback focalizado por agente**, no restart completo.
- Max 2 revisiones por agente por ronda. Max 8-10 revisiones totales por caso.
- Routing:
  - Matemática/plausibilidad del mundo → Architect
  - Fenómeno no evidenciado → Explorer
  - Preguntas triviales/irresolubles → Question Designer
  - Leak/narrativa pobre → Case Writer
- Si corrección upstream invalida downstream → regenerar, no parchear.
- **Aceptar "good-enough"** cuando: WorldModel estable, 2-4 fenómenos con evidencia, 3-5 GoldQuestions no triviales con AnswerKeys estables, brief no filtra, firma no colapsa con pool.
- **Re-semillar** cuando: mismo motivo de rechazo 2 veces seguidas, para pasar Validator hay que introducir trucos artificiales, complejidad forzada que el seed no justifica, 8-10 iteraciones sin núcleo claro.

"Iterar localmente primero; re-semillar cuando el loop empieza a fabricar benchmark en vez de ciencia sintética plausible."

**Firma híbrida anclada — 6 ejes recomendados**:

- `research_type`: descriptive / causal / mechanistic / predictive / methodological / synthesis / replication (del taxonomy propio).
- `primary_workflow`: hypothetico-deductive / bayesian refinement / exploratory+confirmatory / longitudinal observational / build-test-iterate / triangulation (Doc1 Taxonomía).
- `epistemic_demand`: workflow / strategic / hypothesis-driven (de Corral).
- `scenario_family`: confounding / heterogeneity / mediation / system mapping / trade-off / identifiability / etc. (del rubric de escenarios).
- `structural_complication`: hidden confounder / feedback / threshold / selection / partial observability / multistability (operativo).
- `prior_trap`: linealidad / reversibilidad / subgroup fallacy / "association implies causation" / etc. (operativo).

"Todo lo demás puede vivir como metadata extendida. Firma completa = burocracia; sin anclar en docs propios + Corral = arbitraria. El híbrido es la opción correcta."

### Decisiones tomadas

- **Paper Digestion**: adoptado como paso 1 del Case Construction Loop. Schema Codex-proposed.
- **Loop formal**: adoptado. Feedback focalizado por agente, max 2 por agente / 8-10 total, routing por tipo de fallo, criterios aceptación + re-semilla explícitos.
- **Firma híbrida**: adoptada con 6 ejes anclados (research_type, primary_workflow, epistemic_demand, scenario_family, structural_complication, prior_trap). En MVP uso light (registro + novelty gate corpus-level), no gate fuerte todavía.

### Pendiente para aplicar

- ARCHITECTURE.md §3 (flujo): agregar Paper Digestion como paso 1 + formalizar loop.
- ARCHITECTURE.md §4 (agentes): documentar Paper Digestion.
- ARCHITECTURE.md §5 (contratos): agregar `PaperInsights`, `CaseSignature`.
- ARCHITECTURE.md §6 (Environment API): cerrar query_kinds por dominio.
- ARCHITECTURE.md §10 (dudas): cerrar §10.3 (rubric generation ya resuelta vía composición controlada), §10.4 (loop convergencia ya resuelta con max iters + re-semilla).
- ARCHITECTURE.md §12 (fases): 3 tests de go/no-go como criterio de cierre Fase 0.

### Síntesis acumulada del flujo tras rondas 1-5

```
Seed Paper
  ↓
Paper Digestion → PaperInsights (extrae objetivo, variables, mecanismos,
                                   fenómenos reportados, complications,
                                   counterintuitive priors, constraints,
                                   candidate epistemic operations,
                                   realism bounds)
  ↓
World Architect → WorldSpec (usa paper + insights para diseñar el mundo)
  ↓
Explorer → PhenomenaManifest (ejecuta mundo buscando fenómenos guiado
                                por insights + discovery libre;
                                evidencia ejecutable adjunta)
  ↓
Question Designer → QuestionsBundle (GoldQuestions = composición de 2-3
                                      query_kinds + AnswerKey struct;
                                      evita trivialidad usando insights)
  ↓
Case Writer → ResearchCase (brief realista disfrazando GoldQuestions,
                              lenguaje del paper, sin leak)
  ↓
Validator → ValidationReport + CaseSignature (6 ejes)
  - Case-level: diversidad epistémica, adversarial, resolubilidad, realismo
  - Corpus-level: novelty gate contra pool aceptado
  - Feedback focalizado si rechaza (max 2 per agent, 8-10 total);
    re-semilla si 2 rechazos seguidos por mismo motivo
  ↓
(Si approved) ResearchCase sale al Investigator.
Al cierre, registrar CaseSignature en el pool.
```

Flujo del Evaluator (runtime, no Designer):
```
ResearchCase → Investigator → Claims (prosa) + InvestigationLog (trace mínimo)
  ↓
Evaluator → Score multi-dim
  - Compara Claims vs Rubrics + AnswerKeys (sin ejecutar Environment
    para claims espontáneas — feature futura issue #53)
  - InvestigationLog solo se registra, no se evalúa en MVP
```

---

## Ronda 6 — 2026-04-24 — Cantidad de GQs, pesos, ejemplo Birth Weight Paradox

### Pregunta del user

¿Las GoldQuestions deben tener peso? ¿Las Rubrics también? ¿Cuántas GQs por caso? Propone ~10 para dar margen (si son 2-3, el agente falla una y saca 0). ¿Cómo luce una GQ concreta?

### Respuestas de Codex

**Cantidad**: default 6-8 GQs por caso; 4-6 para simples; 8-10 para ricos. Mínimo 3 required. Split ~40% required / 60% support por conteo, ~70%/30% por peso total.

**Pesos discretos, dos niveles**: `weight_GQ ∈ {0.08, 0.12, 0.16, 0.20}`, `criterion_weight ∈ {1, 2, 3}`. `score_GQ = core × alpha + bonus × (1-alpha)` con alpha 0.7-0.85.

**Corrección técnica importante del Birth Weight Paradox**: mi ejemplo inicial centraba en "SES como confounder". Codex me corrige: el corazón NO es SES, es la **inversión al estratificar por birth weight** (post-treatment conditioning / selection bias sobre mediador). Observación meta-arquitectónica: si YO me equivoqué teniendo el paper, el Paper Digestion automatizado también se va a equivocar consistente. Refuerza la necesidad de validación humana inicial + PaperInsights específico al paper (no taxonomía genérica).

**4 GoldQuestions canónicas propuestas** (que se rediseñaron en ronda 7):
- Q1 Efecto total (ATE con confounding por SES)
- Q2 Paradoja de estratificación en LBW ← corazón del caso
- Q3 Mediación por birth weight
- Q4 Identificabilidad del efecto directo

**Question Designer — 3 pasos internos, output atómico**:
```
design     → redacta GQ + rubric + query_plan (sin ejecutar)
ground     → ejecuta Verifier, llena answer_key, stability, tolerance
finalize   → ajusta rubric si el grounding mostró ambigüedad
Output externo: GoldQuestionBundle final
```

### Observación meta del user

Si el LLM (o Claude) se confundió sobre qué es el "corazón" del paper, el proceso automatizado va a equivocarse sistemáticamente. Implica:
- PaperInsights NO puede forzar la "complication" a una lista predefinida (hay que capturar el mecanismo específico).
- Validación humana inicial de PaperInsights para los primeros N papers, hasta calibrar.
- Pool de seed papers curado con "mecanismo central" anotado como metadata.

---

## Ronda 7 — 2026-04-24 — Area+Finding+ScoringNote (RECHAZADA)

### Propuestas evaluadas

Codex propuso dos cambios a la estructura evaluativa:

1. **Unificar GQ+Rubric → ResearchArea+Finding**. Argumento: "GQ y Rubric son el mismo concepto en niveles distintos". Agregar `question_text + answer_key + grounding_plan` al Area para no perder el núcleo evaluativo.

2. **scoring_note estructurado** por Finding: `{positive_signals, non_creditable_confusions, disambiguation_target, minimum_semantic_requirement}`.

### Decisión del user (rechazo con contrapropuesta)

**No adopta Area+Finding+ScoringNote estructurado**. Razones:
- Introduce 3 conceptos nuevos (Area, Finding, ScoringNote) cuando 2 (GoldQuestion, Rubric) son más naturales.
- Los 4 campos estructurados del ScoringNote son schema rígido que el judge puede overfit a listas.
- "Area" suena raro — "question" es más natural de pensar.

**Contrapropuesta del user (adoptada)**: mantener `GoldQuestion + Rubric` con **dos niveles explícitos**:

- **Identificación (binary)**: ¿el solver está hablando de esta GQ? Si no → score_GQ = 0.
- **Compleción (graduada)**: si identifica, se evalúa la rubric criterion por criterion.

Hints en **texto puro** (NL libre, no schema), dos tipos:
- `identification_hint` en la GQ: cómo el judge reconoce que el solver aborda el tema.
- `scoring_hint` por Criterion: cómo el judge juzga el cumplimiento de ese criterio.

Guideline editorial (no schema): 2-4 frases concretas por hint, no mini-ensayo.

### Schema FINAL adoptado

```python
class GoldQuestion:
    id: str
    text: str                     # pregunta conceptual en prosa
    weight: float                 # peso en score del caso (discreto: 0.08/0.12/0.16/0.20)
    role: Literal["required", "support"]
    verifier_query: VerifierQuery # cómo calcular answer_key
    answer_key: dict              # struct canónica con campos tipados
    identification_hint: str       # NL libre, guía al judge para matchear GQ vs reporte
    rubric: Rubric

class Rubric:
    criteria: list[Criterion]

class Criterion:
    text: str                     # qué se evalúa
    weight: int                    # 1, 2, 3 (discreto)
    role: Literal["core", "bonus"] # core 70-85%, bonus 15-30% del score_GQ
    anchor: AnswerKeyAnchor        # qué del answer_key lo acredita (estructurado)
    scoring_hint: str              # NL libre, guía al judge para este criterion
```

### Cómo puntúa el judge (dos pasos claros)

**Paso 1 — identificación binaria**:
> ¿El solver está hablando de esta GQ? Usa `identification_hint` para decidir.
> Si no → score_GQ = 0, no se evalúa rubric.

**Paso 2 — compleción por rubric** (si identificó):
> Para cada Criterion, ¿lo cumple? Usa `scoring_hint` + `anchor` para calibrar.
> score_GQ = Σ (criterion.weight × cumplimiento) con mix core/bonus.

Score total = Σ (GQ.weight × score_GQ) sobre todas las GQs del caso.

### Ejemplo canónico (GQ1 de Birth Weight Paradox)

```python
GoldQuestion(
  id="q_bw_01",
  text="¿Cuál es el efecto causal del tabaquismo materno sobre mortalidad infantil?",
  weight=0.20,
  role="required",
  verifier_query={"kind": "ate_with_adjustment", "treatment": "smoking",
                   "outcome": "mortality", "adjust_set": ["ses"]},
  answer_key={
    "raw_risk_diff": 0.030,
    "adjusted_ate": 0.018,
    "direction": "harmful",
    "tolerance": 0.005,
  },
  identification_hint="""
    El solver aborda esta GQ cuando analiza el efecto de fumar sobre mortalidad —
    puede usar 'efecto total', 'asociación', 'ATE', 'riesgo relativo'.
    Si solo menciona que fumar es dañino sin análisis de los datos del caso,
    NO cuenta — debe haber análisis concreto sobre este par de variables.
  """,
  rubric=Rubric(criteria=[
    Criterion(
      text="Identifica la dirección correcta (tabaquismo aumenta mortalidad)",
      weight=2, role="core",
      anchor={"path": "direction", "match": "equals", "value": "harmful"},
      scoring_hint="""
        Acreditar si afirma efecto perjudicial a nivel poblacional.
        NO acreditar si concluye 'fumar protege' (confusión con paradox de LBW).
      """,
    ),
    Criterion(
      text="Distingue asociación cruda de efecto ajustado",
      weight=3, role="core",
      anchor={"path": "raw_vs_adjusted", "match": "mentioned"},
      scoring_hint="""
        Acreditar si muestra que ajustar por SES modifica el efecto.
        Distinción 'asociación' vs 'causal' debe ser explícita.
        NO acreditar si solo reporta un número sin discutir ajuste.
      """,
    ),
    Criterion(
      text="Cuantifica efecto ajustado dentro de tolerancia ±0.005",
      weight=3, role="core",
      anchor={"path": "adjusted_ate", "match": "approx", "tolerance": 0.005},
      scoring_hint="""
        Acreditar si reporta ATE cercano a 0.018 ± 0.005.
        Si reporta solo efecto crudo, crédito parcial.
        Penalizar si sobreafirma precisión sin intervalo.
      """,
    ),
    Criterion(
      text="Reconoce incertidumbre / hidden confounders",
      weight=1, role="bonus",
      anchor={"path": "uncertainty_discussed", "match": "mentioned"},
      scoring_hint="""
        Suma si menciona limitaciones metodológicas o posibles confounders no medidos.
        No exigible para core completion.
      """,
    ),
  ])
)
```

### Pendiente de aplicar a ARCHITECTURE.md

- §5 contratos Pydantic: reemplazar estructura de Rubric existente por este schema final.
- §8 scoring: documentar los 2 pasos del Evaluator (identificación binaria, luego graduación por rubric).
- Apéndice nuevo con ejemplo canónico Birth Weight Paradox (6-8 GQs completas).

---

## Ronda 11 — 2026-04-26 — Estrategia de implementación (orden + checkpoints + anti-memorización)

### Contexto

Después de cerrar el diseño macro, arrancamos a pensar cómo construir v1.5 sin caer en dos trampas:
1. Hacer un spike chico desechable que no valide nada concluyente (ya pasó: spike `experiments/v1_5_juez_spike/` daba rank 6/6 pero el caso Birth Weight es famoso → posible memorización del LLM judge).
2. Construir las 8 sub-issues #55-#62 en orden secuencial sin probar nada hasta el final → si la mecánica de evaluación falla, lo descubrimos tarde.

### Pregunta a Codex

> ¿Cómo encarar el desarrollo de v1.5 si tuviéramos que construir cosas que QUEDEN (no atajos), pieza por pieza, sabiendo del riesgo de memorización del LLM judge?

### Idea central de Codex

> No construyas primero el pipeline que GENERA casos. Construí primero el pipeline que DEMUESTRA que, dado un caso válido, la verdad estructurada realmente gobierna el score. Después automatizá la generación encima de un suelo firme.

La pieza más frágil de v1.5 NO es coordinar 4 agentes — la pieza frágil es que **rubric + answer key + juez LLM realmente discriminen sobre casos NO memorizados**. Hay que enterarse pronto, no al final.

### Orden de implementación adoptado

| Orden | Issue | Por qué acá |
|---|---|---|
| 1 | #55 Contratos Pydantic | Congela handoffs y la frontera público/oculto. |
| 2 | #56 Environment + Verifier | Sin oráculo matemático, todo lo demás es prosa apoyada en el aire. |
| 3 | **#61 Evaluator + Scoring** | La hipótesis más frágil del producto. Si rubric+anchor+judge no funciona, hay que enterarse ACÁ. |
| 4 | #60 Investigator runtime | Cierra el loop estático real con casos hand-authored. |
| 5 | #57 Paper Digestion | Recién acá: ya sabés qué artefactos tiene que producir. |
| 6 | #58 Designer 4 agentes | Sobre consumidores estables (Evaluator + Investigator). |
| 7 | #59 Validator + Loop | Último porque amplifica calidad, no la crea. |
| 8 | #62 Casos diversos + tests | Arranca tras #56, cierra al final. Harness permanente. |

**Cambios respecto al orden secuencial #55→#62**: #61 (Evaluator) salta de posición 7 a 3. #58 (Designer) baja de 4 a 6. La razón: validar mecánica de evaluación ANTES de construir maquinaria de generación.

### Checkpoints entre piezas

- **CP0** post-#55: contratos roundtripean OK, `ResearchCase` no filtra cosas internas.
- **CP1** post-#56: mundos hand-authored producen `AnswerKey` estable y reproducible.
- **CP2** post-#61: **gate duro** — `answer_key_sensitivity` y `isomorph_invariance` pasan sobre corpus abstracto. Si fallan, se rehace Evaluator AHORA.
- **CP3** post-#60: caso SCM y caso ODE corren end-to-end con Investigator real.
- **CP4** post-#57: 3 seed papers producen `PaperInsights` accionables.
- **CP5** post-#58: Designer produce casos completos válidos por formalismo.
- **CP6** post-#59: Validator rechaza casos plantados con leak/trivialidad.
- **CP7** post-#62: casos diversos + suite abstracta + piloto humano.

### Anti-memorización integrada al flujo

No es una prueba aparte al final, es parte del desarrollo:

1. **Corpus abstracto desde temprano**: justo después de #56 se construye un corpus chico de mundos isomorfos hand-authored con variables `X`, `M`, `Y`, briefs neutros, answer keys generadas por el Verifier. Asset permanente, no spike.
2. **Birth Weight y SIR son smoke tests, no evidencia principal.** Los casos famosos sirven para confirmación humana.
3. **Gate duro post-#61**: dos tests obligatorios (`answer_key_sensitivity` y `isomorph_invariance`).
4. **Re-ejecución post-#58 y post-#59**: el Designer puede reintroducir leak por wording de briefs o rubrics demasiado "teaching-to-the-test".
5. **Regla operativa**: si el judge acierta en casos famosos pero falla en la suite abstracta → rojo. Si pasa la abstracta y los famosos → señal real.

### Decisiones laterales tomadas en esta ronda

1. **SDE difiere a v1.6**: ODE + observation_noise opcional cubre la mayoría de los casos realistas. SDE intrínseco solo se necesita para difusión molecular, mercados, biofísica con ruido térmico — no es bloqueante para v1.5.
2. **`epistemic_operation` sale de `GoldQuestion`**: el campo confundía dos sentidos (clasificación de pregunta vs tagging de acción al estilo Corral). En v1.5 no clasificamos preguntas con templates (principio "UN método para todo"). El concepto Corral-style queda como `epistemic_tag` opcional en `InvestigatorAction`, hookeado para trace scoring futuro (issue #53).
3. **Diversidad de casos como invariante**: NO un caso canónico único. Varios casos por formalismo, distintos dominios, distintos tipos de trampa. Sin diversidad real, todo el sistema pierde sentido.

### Veredicto

Arrancamos con #55. El plan está documentado, no hay ambigüedad. Si en la implementación aparece una decisión grande que afecta el plan, paramos y revisamos. Detalles (nombres, layout) los resolvemos en flujo.

---

## Ronda 12 — 2026-05-04 — Re-diseño multi-agente del Designer (mata el catálogo cerrado)

> **Banner de obsolescencia parcial**: las rondas 1-11 (sobre todo 4, 5, 6, 7) hablan de `query_kinds` fijos, `VerifierQuery`, `Verifier` con dispatch, y catálogo cerrado de 16 operaciones. Esa parte fue **explícitamente rechazada en Ronda 12** por sesgar al Designer ("siempre las mismas preguntas"). El doc canónico del re-diseño es `research/notes/multi_explorer_redesign.md`. El resto de las decisiones (rubric + LLM judge + answer key grounded, evaluator design-time, alpha=0.8, frontera público/oculto, diversidad de casos como invariante) sigue vigente.

### Contexto

Después de programar #55 (contratos) y arrancar #56 (Environment + Verifier), el usuario detectó dos problemas en el approach:

1. **Catálogo cerrado de 16 query_kinds = sesgo**. Si el Question Designer sabe que solo 16 operaciones producen AnswerKey numérico, va a inventar preguntas que mapeen a esas 16. Eco al problema de AtomicSpec v1, otra puerta.
2. **Doble trabajo Architect ↔ Explorer ↔ Question Designer**. El Architect ya diseña el mundo intencionalmente. El Explorer ya escribe scripts arbitrarios contra el Environment (`ExecutableEvidence`). El Question Designer estaba haciendo lo mismo pero con dispatch dict.

### Decisiones de Ronda 12

1. **Mata el catálogo cerrado**. Cada agente del Designer escribe sus propios scripts Python contra el Environment. Resultado: `EvidenceArtifact` (script + numerical_result + tag opcional). Sin restricción.

2. **Mata el `Verifier` como objeto centralizado**. No hay dispatch dict. No hay 16 funciones canónicas. Las 10 funciones SCM que se programaron en `verifier/scm/` se borran. Si emerge necesidad de un helper de bajo nivel (ej. `bootstrap_ci`), va a `helpers/` como librería opcional, NO como catálogo cerrado.

3. **Multi-agente**: el flujo lineal `Architect → Explorer → Question Designer` se reemplaza por:
   - Architect produce `WorldSpec + intended_phenomena` (lista corta a nivel mecanismo).
   - **N Explorer/Designers en paralelo** (3 default, 4 si WorldSpec cargado): 2-3 guiados por `IntendedPhenomenon` + 1 wildcard. Multi-turn. Regla dura: verify first, propose later.
   - **Selector** (advisory) → `QuestionsBundle` + `SelectionReport`. NO invalida.
   - Case Writer y Validator transversal sin cambios estructurales, salvo que el **Validator es ÚNICO ÁRBITRO** y cuando invalida declara `target_to_reiterate: Literal["world","explorers","case"]`.

4. **`intended_phenomena` a nivel mecanismo, NO a nivel pregunta**. El Architect dice "puse collider entre X y U", NO "preguntá ATE de X sobre Y". Eso evita que el Architect se vuelva fuente única de qué se pregunta.

### Consultas a Codex (3 rondas en esta sesión)

- Ronda A: validó la dirección general del re-diseño. Marcó como riesgo crítico que el Selector "vuelva a inventar semántica sin evidencia recomputable" (mini-compiler por la ventana).
- Ronda B: refinamiento — `intended_phenomena` a nivel mecanismo, verify-first/propose-later como regla dura, wildcard explícito (no opcional), Validator con `target_to_reiterate`, 3-4 Explorers (no 5), focos derivados del WorldSpec.
- Ronda C: review final del cambio aplicado. Verde con 3 cabos sueltos menores corregidos antes del commit.

### Cambios concretos en contratos Pydantic

**Crear**: `IntendedPhenomenon`, `EvidenceArtifact` (rename de `ExecutableEvidence`), `QuestionProposal`, `SelectionReport`.

**Modificar**:
- `WorldSpec`: agregar `intended_phenomena: list[IntendedPhenomenon]`.
- `Phenomenon.kind`: de `Literal[6 valores]` a `str` libre + `tags`.
- `GoldQuestion`: borrar `verifier_query`, agregar `answer_key_provenance: list[EvidenceArtifact]` (`min_length=1`).
- `ValidationReport`: agregar `target_to_reiterate` con validator cruzado (passed True ↔ target None).

**Borrar**: `VerifierQuery`.

### Veredicto

Re-diseño aplicado, 97 tests pasan, ruff limpio. ARCHITECTURE.md y bodies de issues #56 y #58 actualizados. Issue #58 cambia significativamente: ya no es "Designer 4 agentes", ahora es "Designer multi-agente con N Explorers paralelo + Selector advisory + Validator único árbitro".

Próximo paso: commit + push, después arrancar #58 con orden recomendado por Codex: Architect → 1 Explorer/Designer E2E con Environment mock → Selector → Validator → Case Writer; recién después escalar de 1 a N Explorers.
