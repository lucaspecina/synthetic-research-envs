# SREG — Arquitectura
## Synthetic Research Environment Generator

> Este documento define como deberia estar organizado SREG dentro del
> alcance arquitectonico hoy seleccionado.
>
> `PROJECT.md` define la vision.
> `ARCHITECTURE.md` define el sistema objetivo para este horizonte.
> `CURRENT_STATE.md` describe que parte de eso existe hoy realmente.
> GitHub Issues describe la brecha y el trabajo pendiente.

---

> **Versión: v1.5 (en desarrollo, rama `dev`). 2026-04-23.**
>
> Este doc es **spec vivo**: working canon hasta que el primer MVP
> end-to-end corra. Si algo de esto no sobrevive al contacto con código
> real, se actualiza acá.
>
> `main` queda congelada en v1.x con tag `pre-v1.5` como referencia
> estable. La arquitectura v1 (orchestrator + AtomicSpec compiler +
> Flow A/B) está preservada en `docs/archive/architecture_v1.md` para
> referencia histórica y operativa sobre código legacy en `main`.
>
> **Origen del rediseño:** `research/notes/rethink_sreg_2026-04-23.md`
> (working doc con todo el historial de discusión, consultas a Codex,
> debates). Este doc extrae la especificación limpia; el notes/ queda
> como contexto para quien quiera entender por qué llegamos acá.
> Post-mortem del compiler v1 (por qué lo matamos):
> `research/notes/compiler_v1_postmortem.md`.

---

## 0. Mapa macro del sistema

A alto nivel, SREG v1.5 tiene **3 bloques principales** + 1 motor
transversal:

```
┌─────────────────────────┐      ┌──────────────────┐      ┌────────────────────┐
│ 1. CASE GENERATION      │ →    │ 2. SOLVER        │ →    │ 3. EVALUATION      │
│    (Designer, 5 agentes)│ case │    SCAFFOLD      │ out  │    (LLM judge)     │
│    + Paper Digestion    │      │    (Investigator │      │                    │
│    + Validator loop     │      │     + tools      │      │    + trace scoring │
│    + novelty gate       │      │     + InvLog)    │      │      [futuro]      │
└──────┬──────────────────┘      └──────────────────┘      └────────────────────┘
       │                                                            ▲
       └──► Verifier (transversal) ◄───────── AnswerKeys ───────────┘
            motor matemático determinista
            (oracle SCM/ODE/SDE-grounded, la joya del sistema)
```

### 1. Case Generation (Designer)

**Lo más pesado del diseño, ~70% del esfuerzo de implementación.**
Vive acá toda la complejidad nueva de v1.5. Compuesto por:

- **Paper Digestion** → `PaperInsights` (extrae mecanismo central +
  fenómenos + counterintuitive priors del seed paper).
- **World Architect** → `WorldSpec` (diseña el sistema matemático
  subyacente, anclado en el paper).
- **Explorer** → `PhenomenaManifest` (ejecuta el mundo para encontrar
  fenómenos interesantes, con evidencia ejecutable adjunta).
- **Question Designer** → `QuestionsBundle` (GoldQuestions con
  identification_hint + Rubrics con scoring_hint + AnswerKeys
  computados por el Verifier).
- **Case Writer** → `ResearchCase` (brief + contexto + datos,
  disfrazado realista sin leak).
- **Validator transversal**: feedback focalizado por agente, diversity
  gate corpus-level, max 2 iteraciones por agente / 8-10 total,
  re-semilla si no converge.

Si este bloque produce casos pobres, el resto no salva el proyecto.

### 2. Solver Scaffold (Investigator)

**Relativamente delgado, ~10% del esfuerzo de implementación.** Ya
existe buena parte de v1 reusable.

ReAct-like con tool-calling nativo:
- `load_artifact`, `save_artifact` (datasets).
- `python_exec` (sandbox con pandas/numpy/scipy/statsmodels/sklearn).
- `think` (reasoning explícito opcional).
- `submit_claims` (al cierre).
- **Nuevo en v1.5**: emite `InvestigationLog` estructurado con cada
  acción, hipótesis intermedia, pivoteo, rationale. Solo se registra
  en MVP — habilita trace scoring futuro (issue #53).

**Constraint clave invariante**: el Investigator **NO ve** el
WorldModel, el DAG, las GoldQuestions, las Rubrics ni los
AnswerKeys. Solo datos observacionales + brief + catálogo de tools.
Esa asimetría es lo que preserva la presión evolutiva sobre el
razonamiento del solver.

### 3. Evaluation (Evaluator)

**MVP simple, futuro más rico. ~20% del esfuerzo de implementación.**

**MVP**: LLM-judge con pipeline de 2 pasos por GoldQuestion:
- **Paso 1 — Identificación binary**: ¿el solver aborda este tema?
  Usa `identification_hint`. Si no → score_GQ = 0.
- **Paso 2 — Compleción graduada** (si identificó): para cada
  Criterion de la rubric, usa `scoring_hint` + `anchor` contra el
  reporte del solver. Score graduado core + bonus.

**No ejecuta queries runtime sobre el Environment**. Toda la
formalización vive en design-time (evita reintroducir compiler v1).
Claims espontáneas fuera de GoldQuestions no entran al score
principal en MVP.

**Futuro (post-Fase 0 MVP, gated en los 3 tests de go/no-go)**:
- Trace scoring tipo Corral (nodos H/T/E/J/U/C, productive motifs,
  breakdowns) — issue #53.
- Lane de novel-but-correct para claims espontáneas validadas.
- IRT modeling para separar capacidades por dimensión.
- Distilación del judge a classifier chico para RL training.

### 4. Verifier (transversal, motor matemático)

**Oracle SCM/ODE/SDE-grounded. No es LLM, es código determinista.**
La joya del sistema — lo que preserva la verdad matemática y da
anchors a todo lo demás.

- En **generación del caso**: el Question Designer lo llama para
  computar `AnswerKey` exacto desde el `WorldModel`, dada una
  `verifier_query` compuesta por `query_kinds` (10 SCM + 7 ODE/SDE).
- En **evaluación (MVP)**: no se usa runtime — el Evaluator solo lee
  los `AnswerKeys` precomputados como anchors de los Criterios.

Todos los `query_kinds` son primitivas matemáticas universales del
dominio (`ate`, `association`, `confounding_gap`, `steady_state`,
`recovery_time`, etc.). No se componen como álgebra abierta
(eso era el bug v1) — las GoldQuestions sí pueden combinar 2-3
query_kinds con schema estable.

### Prioridad operativa

- **Diseño**: case generation > evaluation > solver scaffold.
- **Implementación**: case generation (~70%) > evaluation (~20%) >
  solver scaffold (~10%).
- **Riesgo**: el Paper Digestion + el Explorer + el Question Designer
  concentran ~60% del riesgo de que v1.5 no produzca casos
  interesantes y diversos.

---

## 1. Tesis

El gap crítico en la capacidad científica de los agentes AI actuales
no es razonamiento puro sino **juicio investigativo**: qué examinar,
cuándo pivotar, cómo separar evidencia específica del caso de priors
del training.

v1.x construyó el pipeline pero quedó bloqueado en la capa de
evaluación: el compiler que traduce prosa libre del solver a
especificaciones formales verificables es frágil (Suite 2 topped out
en ~83% después de 18 iteraciones empíricas — ver `compiler_v1_postmortem.md`).
La IR `AtomicSpec` con ~5600 combos teóricos fuerza una forma causal-
experimental que no encaja con tipos diversos de investigación.

**v1.5 elimina el compiler.** La evaluación pasa a ser *rubric + LLM
judge con acceso al Environment ejecutable*. El verifier matemático
se mantiene (es el núcleo anti-hallucination del proyecto) pero se
relocaliza al diseño del caso y a rol de sentinel runtime. Se abre la
puerta a dominios dinámicos (ODEs/SDEs) además de SCMs.

**Justificación empírica externa**: Corral (Ríos-García/Jablonka et al.
2026, arXiv:2604.18805) validó con 25k runs y 95.7% human-LLM agreement
sobre 773 traces que el modelo base explica 41.4% de la varianza, el
scaffold 1.5%. "Scaffold doesn't fix reasoning; training does." Ver
`research/synthesis/related_work_corral.md`.

---

## 2. Nomenclatura

| Concepto | Nombre | Rol |
|---|---|---|
| Sistema matemático subyacente | **WorldModel** | SCM / ODE / SDE. Ecuaciones, grafos, parámetros. |
| Interfaz ejecutable del sistema | **Environment** | Expone `observe`, `intervene`, `simulate`. Cualquier consumidor (Designer, Evaluator, Investigator indirecto vía datos) interactúa vía esta interfaz. |
| Paper real que inspira | **Seed Paper** | Input al Designer. El WorldModel se inspira, no replica. |
| LLM meta-agente que diseña casos | **Designer** | Compuesto por 5 roles (ver sección 4). |
| Pregunta canónica con answer key | **GoldQuestion** | Cada caso tiene 3-5. Pre-verificadas ejecutando el Environment. |
| Estructura graduada de evaluación | **Rubric** | Por GoldQuestion. Core analytic + epistemic bonus. |
| Respuesta numérica verdadera | **Answer Key** | Computada por el Verifier ejecutando el Environment. |
| Paquete que recibe el agente | **ResearchCase** | Brief + datos + contexto + tools. Oculta GoldQuestions y Rubrics. |
| LLM-agente que investiga | **Investigator** | Libre, con python_exec sobre los datos. |
| Afirmación en prosa del Investigator | **Claim** | Sin formato impuesto. |
| LLM que compara y valida | **Evaluator** | Tiene acceso al Environment ejecutable. |
| Motor matemático determinista | **Verifier** | Ejecuta queries contra el Environment. NO es LLM. |

Convención externa respetada: `Environment` alinea con SciGym, BoxingGym,
DiscoveryWorld, Corral.

**Nombres muertos**: `orchestrator`, `SQ`/`SubQuestion`, `ClaimCard`,
`AtomicSpec`, `oi_*` prefix, `Suite 1/2/3/4`, `solver` (rebautizado
Investigator), `ResearchProblem` (rebautizado ResearchCase).

---

## 3. Flujo end-to-end

```
Seed Paper
    │
    ▼
┌─────────────────────── DESIGNER ───────────────────────┐
│                                                        │
│  1. World Architect  ──► WorldSpec                     │
│        │                                               │
│  2. Explorer         ──► PhenomenaManifest             │
│        │                  (con evidencia ejecutable)   │
│  3. Question Designer──► QuestionsBundle               │
│        │                  (GoldQuestion + Rubric +     │
│        │                   AnswerKey por pregunta)     │
│  4. Case Writer      ──► ResearchCase                  │
│        │                                               │
│  5. Validator (transversal, puede invalidar upstream)  │
│        └──► ValidationReport                           │
│                                                        │
└────────────────────────────────────────────────────────┘
    │
    ▼
ResearchCase (brief + datos + contexto + tools)
    │
    ▼
Investigator (libre, python_exec)
    │                      ├─► InvestigationLog (log estructurado mínimo
    │                      │    de cada acción — se registra siempre,
    │                      │    no se evalúa en MVP pero habilita
    │                      │    evaluación de trayectoria futura. Ver
    │                      │    issue #53.)
    ▼
Claims (prosa libre, sin formato impuesto)
    │
    ▼
Evaluator (compara Claims vs Rubrics + ejecuta Environment
           para validar claims espontáneas)
    │
    ▼
Score (multi-dimensional: framing, identification, estimation,
       intervention prediction, confounding, mediation,
       epistemic calibration, process quality)
```

El Validator opera en loop iterativo con los productores: puede
invalidar cualquier etapa y gatillar revisión. El caso no sale del
Designer hasta que el Validator aprueba.

---

## 4. Agentes del Designer (4 productores + 1 Validator)

### 4.1 World Architect
- **Input**: Seed Paper + constraints opcionales.
- **Output**: `WorldSpec` (ecuaciones, grafo, parámetros).
- **Responsabilidad**: matemática correcta, fidelidad al paper
  (inspirarse, no replicar), tipo de formalismo (SCM/ODE/SDE según
  el dominio).
- **No responsable de**: identificar qué es interesante. Solo
  construye el mundo.

### 4.2 Explorer
- **Input**: `WorldSpec` + Environment compilado.
- **Output**: `PhenomenaManifest` — lista de fenómenos interesantes
  con **evidencia ejecutable adjunta** (script + resultado numérico),
  no prosa descriptiva.
- **Qué busca**: relaciones contraintuitivas (signo crudo ≠ signo
  ajustado), identifiability gaps, bifurcaciones, spurious correlations
  fuertes, heterogeneidad de efectos, no-linealidades.
- **Por qué la evidencia importa**: sin ejecutable, cualquier
  alucinación del Explorer contamina upstream (error laundering).

### 4.3 Question Designer
- **Input**: `PhenomenaManifest` + Seed Paper + Environment.
- **Output**: `QuestionsBundle` — 3-5 GoldQuestions, cada una con:
  - Texto en lenguaje natural.
  - Rubric graduada (ver sección 6).
  - Answer Key numérico ejecutado contra el Environment.
  - Mapeo explícito `question → verifier_query` (reproducible).
- **Cobertura**: mezcla de operaciones epistémicas (identificación,
  estimación, intervención, confounding, mediación, epistemic
  calibration).
- **Validación implícita**: cada question pasa por el Verifier antes de
  salir.

### 4.4 Case Writer
- **Input**: `QuestionsBundle` (pero **sin leak al solver**) + Seed Paper
  + dominio.
- **Output**: `ResearchCase` — brief + contexto + narrativa + datos
  observacionales + tools disponibles.
- **Estilo**: realista, vago tipo brief de supervisor real. No
  lista las GoldQuestions; las sugiere indirectamente vía contexto.
- **Protege contra**: solver que resuelve mirando el brief, no los datos.

### 4.5 Validator (transversal)
- **Vista global**: lee todos los artefactos (WorldSpec, Manifest,
  QuestionsBundle, ResearchCase).
- **Responsabilidades**:
  - **Trivialidad**: adversarial check. Un LLM sin datos intenta
    responder cada GoldQuestion desde priors. Si acierta, la pregunta
    no mide investigación.
  - **Leakage**: el brief no revela las GoldQuestions.
  - **Internal consistency**: Manifest coincide con WorldSpec,
    Questions coinciden con Manifest, AnswerKeys están dentro de
    tolerancias del Environment.
  - **Rubric / AnswerKey alignment**: cada criterio de la rubric tiene
    soporte en el AnswerKey.
  - **Optimización cruzada perversa**: detecta casos "bonitos" pero
    irresolubles (ej. questions cuyo AnswerKey es inestable bajo ruido
    de sampling).
- **Autoridad**: **puede invalidar outputs upstream y gatillar re-
  iteración**. No solo comenta.
- **Rol adversarial**: intenta hackear el mundo y las preguntas —
  encontrar cómo pasar sin investigar. Si encuentra cómo, la question
  se descarta o se ajusta.

---

## 5. Artefactos tipados (contratos Pydantic)

Cada etapa produce un artefacto con schema estricto. Handoffs requieren
artefacto tipado, no prosa.

```python
class WorldSpec(BaseModel):
    formalism: Literal["scm", "ode", "sde"]
    variables: list[VariableSpec]
    relationships: list[RelationshipSpec]
    parameters: dict[str, float]
    metadata: WorldMetadata  # dominio, inspiración paper, etc.

class PhenomenaManifest(BaseModel):
    world_id: str
    phenomena: list[Phenomenon]  # cada uno con evidencia ejecutable
    interesting_score: float  # agregado de n_counterintuitive, etc.

class Phenomenon(BaseModel):
    kind: Literal["counterintuitive", "identifiability_gap",
                   "bifurcation_proximity", "spurious_correlation",
                   "heterogeneity", "non_linearity"]
    description: str
    evidence: ExecutableEvidence  # script + numerical result

class QuestionsBundle(BaseModel):
    questions: list[GoldQuestion]

class GoldQuestion(BaseModel):
    """Pregunta canónica del caso. Dos niveles de evaluación:
    - Identificación (binary): ¿el solver está hablando de esta GQ?
    - Compleción (graduada): si identifica, rubric criterion por criterion.

    Pesos discretos para evitar ajuste fino arbitrario:
    - weight ∈ {0.08, 0.12, 0.16, 0.20}
    """
    id: str
    text: str                    # pregunta conceptual en prosa
    weight: float                 # peso en score total del caso
    role: Literal["required", "support"]
    verifier_query: VerifierQuery # cómo calcular answer_key
    answer_key: AnswerKey         # struct canónica con campos tipados
    epistemic_operation: str      # "identification", "estimation", etc.
    identification_hint: str      # NL libre: guía al judge para matchear
                                  # la GQ contra el reporte. 2-4 frases
                                  # concretas sobre qué buscar y qué NO
                                  # cuenta como identificación.
    rubric: Rubric

class Rubric(BaseModel):
    criteria: list[Criterion]     # mezcla core + bonus, clasificados por role

class Criterion(BaseModel):
    """Un criterio de la rubric. Pesos discretos (1/2/3) y role
    core vs bonus. Core aporta 70-85% del score de la GQ, bonus 15-30%.
    """
    text: str                     # qué se evalúa
    weight: int                   # 1, 2, o 3
    role: Literal["core", "bonus"]
    anchor: AnswerKeyAnchor       # qué del answer_key lo acredita
    scoring_hint: str             # NL libre: guía al judge para este
                                  # criterion. 2-4 frases concretas.
                                  # Nunca acreditar por terminología sola
                                  # si el span contradice el anchor.
    requires_span: bool = True    # judge debe citar texto del Claim

class AnswerKeyAnchor(BaseModel):
    """Referencia estructurada a un campo del answer_key."""
    path: str                     # ej. "adjusted_ate" o "interpretation.bias_type"
    match: Literal["approx", "equals", "enum", "mentioned"]
    tolerance: float | None = None      # para match="approx"
    value: Any | None = None            # para match="equals" o "enum"

class ResearchCase(BaseModel):
    brief: str
    context: str  # narrativa, background theory opcional
    datasets: list[Dataset]
    tools: list[ToolSpec]
    # NOTA: no incluye QuestionsBundle (hidden del Investigator)

class InvestigationLog(BaseModel):
    """Log estructurado mínimo de lo que hace el Investigator.

    MVP: solo se registra, no se evalúa. Habilita evaluación de
    trayectoria como feature futura (issue #53, inspirado en Corral).
    Capturar desde el arranque evita tener que rehacer tools después.
    """
    case_id: str
    actions: list[InvestigatorAction]  # cada tool call (python_exec,
                                         # submit_claim_draft, pivot, etc.)
    hypotheses_log: list[HypothesisEntry]  # hipótesis formuladas +
                                             # cuándo + por qué
    final_claims: list[Claim]  # el reporte final en prosa

class InvestigatorAction(BaseModel):
    step: int
    timestamp: datetime
    kind: Literal["python_exec", "observe", "intervene",
                   "hypothesis", "pivot", "submit"]
    payload: dict  # schema depende de kind
    rationale: str | None  # por qué esta acción (opcional pero
                             # recomendado — el prompt del Investigator
                             # lo pide)

class ValidationReport(BaseModel):
    passed: bool
    invalidated_artifacts: list[str]  # cuáles etapas fallaron
    issues: list[ValidationIssue]
    adversarial_attempts: list[AdversarialAttempt]  # intentos de hackeo
```

---

## 6. Rubric design

Cada GoldQuestion tiene una Rubric. La evaluación ocurre en **dos niveles
explícitos**:

- **Nivel 1 — Identificación (binary)**: ¿el solver está hablando de
  esta GQ? Se decide mirando el reporte completo con ayuda del
  `identification_hint` de la GQ. Si no identifica → score_GQ = 0 y
  no se evalúa la rubric. Si identifica → pasa al nivel 2.

- **Nivel 2 — Compleción (graduada)**: para cada `Criterion` de la
  rubric, el judge decide si se cumple. Usa el `scoring_hint` + el
  `anchor` para calibrar el juicio.

**Pesos discretos (anti-ajuste-fino)**:
- `weight_GQ` ∈ {0.08, 0.12, 0.16, 0.20} — fuerza elegir entre pocos
  niveles de importancia por GQ.
- `weight_Criterion` ∈ {1, 2, 3} — idem para criterios.

**Split core vs bonus dentro de la rubric**:
- Core: criterios que son obligatorios para responder bien la GQ.
  Aportan 70-85% del score_GQ.
- Bonus: caveats, identifiability awareness, calibración, robustness.
  Aportan 15-30%. **No compensan errores del core.** Si el solver
  afirma causalidad equivocada, no se salva con caveats elegantes.

Fórmula: `score_GQ = alpha × score_core + (1 - alpha) × score_bonus`,
con **`alpha = 0.8` fijo para MVP** (decisión post-ronda 10: alpha
continuo en [0.70, 0.85] era inconsistente con pesos discretos anti-
micro-optimización; se fija en 0.8 por simplicidad). Si evidencia
empírica muestra que conviene variar, discretizar en {0.75, 0.8, 0.85}.

**`identification_hint` (texto libre)**:
Guía al judge sobre qué buscar en el reporte para decidir si aborda
el tema de la GQ. 2-4 frases concretas. Incluye qué términos/conceptos
suelen aparecer Y qué NO cuenta como identificación (ej. mención
tangencial sin análisis de los datos del caso).

**`scoring_hint` por Criterion (texto libre)**:
Guía al judge para calibrar el cumplimiento del criterion. 2-4 frases
concretas. Incluye qué acredita (con comprensión) y qué confusiones
comunes **no** acreditan. Regla editorial: no convertirlo en listas
de keywords — el judge debe entender el criterio, no triggerear por
palabras.

**Regla invariante**: nunca acreditar por terminología sola si el
span contradice el anchor. El judge debe citar span textual del
reporte; sin span = 0 para ese criterion.

**Alternative phrasings** (lesson del compiler v1): cada Criterion
puede listar variantes equivalentes ("el efecto es positivo" ≡ "el
outcome aumenta con el tratamiento"). El Question Designer genera
alternativas al diseñar la rubric.

**Assertion entailment** (tolerance-aware): si el Claim es
cuantitativo ("efecto = 0.42 ± 0.05") y el criterio es cualitativo
("identifica que es positivo"), el judge aplica entailment tolerante:
0.42 > tolerance satisface "positivo" sin match textual exacto.

---

## 7. Evaluator

**Evaluador es un LLM judge sin acceso runtime al Environment** en el
MVP. Toda la formalización vive en design-time (Question Designer) —
el Evaluator solo compara Claims del Investigator contra las Rubrics
pre-definidas. Simplificación deliberada para evitar reintroducir el
compiler frágil por la ventana (ver `research/notes/v1_5_debates.md`
rondas 3 y 4 para el debate completo).

Pipeline del Evaluator, dos pasos por GoldQuestion:

```
Para cada GoldQuestion del caso:

  PASO 1 — IDENTIFICACIÓN (binary)
    Input: reporte del solver + GoldQuestion.identification_hint
    Output: bool "¿el solver aborda este tema?"
    Si no → score_GQ = 0, seguir con la siguiente GQ.

  PASO 2 — COMPLECIÓN (graduada, solo si identificó)
    Para cada Criterion de la Rubric:
      Input: reporte + Criterion.scoring_hint + Criterion.anchor
      Output: {cumplido: bool, span: str, razón: str}
      - Requiere span textual citado del reporte.
      - Evaluar con scoring_hint (qué acredita y qué confusiones NO
        acreditan).
      - Verificar anchor: valor del claim del solver matchea el
        answer_key dentro de tolerancia del anchor.

Score del caso:
    score_total = Σ GQ.weight × score_GQ
    score_GQ = alpha × (Σ core_criterion.weight × cumplido_core) /
                       Σ core_criterion.weight
             + (1-alpha) × (Σ bonus_criterion.weight × cumplido_bonus) /
                           Σ bonus_criterion.weight
```

**Decisiones clave**:

- **El Evaluator NO ejecuta queries arbitrarias sobre el Environment**
  para validar claims espontáneas del solver. Toda la formalización
  vive en design-time. Ventaja: cero compiler NL→query en runtime,
  cero fragilidad tipo v1.
- **Claims espontáneas fuera de las GoldQuestions**: se evalúan
  cualitativamente (no penalizan) o simplemente no puntúan. No entran
  al score principal. (Feature futura: issue #53 — lane de novel-but-
  correct si Fase 0 del MVP muestra que conviene.)
- **Contradicciones explícitas restan**: si el solver tira 20
  afirmaciones contradictorias, no se premia "la que aciertó". Shotgun
  science se penaliza.
- **Regla del span textual**: cada criterion acreditado requiere span
  citado del reporte del solver. Sin span → 0.

---

## 8. Score multi-dimensional

En vez de un score único agregado, reportar un vector por caso:

| Dimensión | Qué mide |
|---|---|
| Framing | ¿Identifica las preguntas relevantes desde el brief abierto? (esto es único de SREG vs Corral) |
| Identification | ¿Reconoce relaciones causales/estructurales? |
| Estimation | ¿Cuantifica efectos correctamente? |
| Intervention prediction | ¿Anticipa efectos de do-operations? |
| Confounding detection | ¿Identifica sesgos? |
| Mediation analysis | ¿Descompone mecanismos? |
| Epistemic calibration | ¿Sabe cuándo no puede concluir? |
| Process quality | ¿El trace muestra productive motifs vs breakdowns? (de Corral) |

Agregado ponderado opcional para comparación simple (modelos, ablations),
pero el reporte principal es el vector — más diagnóstico, mejor para
research, mejor para reward shaping RL.

---

## 9. Cobertura de tipos de investigación

### Cubre bien (todos los formalismos)
- Investigación causal (efectos, confounders, mediación).
- Investigación predictiva (predicciones numéricas contra Environment).
- Descriptiva (distribuciones, patrones, clustering).
- System mapping (estructura del grafo, conexiones).
- Epistemológica (¿qué se puede concluir con estos datos?).
- "Mejor marco conceptual" (componentes verificables contra estructura
  del WorldModel: ¿es cadena o feedback? ¿es lineal o no? etc.).

### Tipos de datasets habilitados por formalismo

**SCM estático (v1.5)**:
- Observaciones puntuales (filas independientes, un snapshot).
- Shape: `n_samples × n_vars`.
- Intervenciones puntuales (do-operator clásico).
- Preguntas naturales: efectos causales, asociaciones, mediaciones,
  heterogeneidades, ranking de importancia, identifiability.

**ODE deterministas (v1.5)**:
- **Trayectorias completas**: cada "fila" es una trayectoria de
  múltiples timesteps × múltiples variables. Shape:
  `n_paths × n_timesteps × n_vars`.
- **Datos con shocks temporales**: before/after designs, treatment
  schedules que varían, intervenciones en tiempos específicos.
- **Observación parcial temporal**: solo algunas variables observables
  en cada timestep, otras latentes (más cerca de ciencia real).
- **Event data**: timestamps de eventos (cruces de umbrales,
  transiciones de régimen).
- **Panel longitudinal**: múltiples unidades × múltiples timesteps.

**SDE estocásticos (v1.5)**:
- Todo lo de ODE, más:
- **Ensembles estocásticos**: múltiples realizaciones del mismo
  sistema bajo distinto ruido. Distribuciones sobre estados en
  tiempos específicos.
- **First-passage times** con variabilidad (distribución, no valor
  único).
- **Análisis señal-ruido**: qué es trend real vs fluctuación aleatoria.

### Tipos de investigación adicionales que habilita la dinámica

Con ODE/SDE aparecen preguntas nativas que SCM estático no puede hacer:

- **Inferencia de escalas temporales**: ¿cuán rápido se estabiliza?
  ¿tiempos característicos del sistema?
- **Detección de oscilaciones**: ¿oscila? ¿con qué frecuencia?
  ¿amortiguado o sostenido (limit cycle)?
- **Régimen stability**: ¿reversible o histérico? ¿hay bistabilidad
  y umbrales?
- **Control óptimo**: ¿cuándo intervenir para efecto máximo? ¿con
  qué protocolo temporal?
- **Identificación de bifurcaciones**: ¿en qué valor de parámetro
  cambia el comportamiento cualitativamente?
- **Filtrado de señales**: ¿qué es señal genuina vs ruido estocástico?
- **Inferencia de parámetros dinámicos**: constantes de tasa,
  coeficientes de difusión.
- **First passage / survival analysis**: ¿cuándo cruza una variable
  un umbral?

### Dominios accesibles con cada formalismo

**SCM estático**: epidemiología observacional, economía causal,
ciencias sociales cuantitativas, política educativa, salud pública
(cross-sectional), estudios de efectos de intervenciones en cohortes.

**ODE adicional**: farmacocinética/farmacodinamia, epidemiología de
enfermedades infecciosas (SIR/SEIR), ecología dinámica (predator-prey,
eutrophication), control de procesos, neurociencia (dinámica neuronal
simplificada), dinámica poblacional, biología del desarrollo.

**SDE adicional**: mercados financieros con jumps, sistemas con ruido
ambiental significativo, procesos de difusión, sistemas de colas,
dinámica estocástica molecular.

### No cubre (out of scope v1.5)
- Investigación hermenéutica / cultural / ética / estética.
- Diseño de experimentos con interacción iterativa (requiere
  Sherlock — v2).
- Teoría fundamentada puramente cualitativa.
- Modelos agent-based complejos (futuro lejano, v3).

---

## 10. Dudas y debates abiertos

> Estas son las preguntas honestas que no tenemos resueltas. La
> especificación de arriba asume choices; acá registramos qué podría
> romperse y qué todavía está para debatir.

### 10.1 Ontology leak 2.0
Si las rubrics salen del mismo pipeline que scorea, el Investigator
entrenado con RL aprende a completar rubrics en vez de investigar.
Vuelta a examen disfrazado.

Mitigaciones en discusión:
- No exponer la rubric completa al Investigator.
- Randomizar descomposiciones (múltiples rubrics isomorfas por caso).
- Reward específico por claims novedosos validados fuera del
  GoldQuestions set (novel-but-correct lane).
- Mundos gemelos / counterfactuales (mismo patrón superficial, pero
  conclusiones distintas según estructura subyacente).

**Pendiente**: cuánta mitigación es suficiente, y si alguna es
implementable en v1.5 MVP o queda para fases siguientes.

### 10.2 Costo del judge para RL training
Millones de episodios con Evaluator LLM completo es caro. Opciones:
- Distilación a classifier chico después de recolectar labels.
- Rubric estable pre-computada por caso (solo el judge varía).
- Uso de Evaluator en subset para validación, proxy barato para
  training dense.

**Pendiente**: cuándo atacar. Probablemente Fase 2.

### 10.3 Cómo generar las rubrics
Tres opciones:
- Question Designer genera rubric libre (más flexible, más variable).
- Templates por tipo de epistemic operation (más consistente, menos
  rico).
- Híbrido: template base + customization por el Question Designer.

**Pendiente**: cuál dar prioridad en MVP.

### 10.4 Cuando el Validator invalida, ¿cuántas iteraciones?
Si el Designer entra en loop de revisión sin convergencia, el caso
nunca se produce. Necesitamos:
- Límite de iteraciones por etapa.
- Criterio de "suficientemente bueno" (Validator como sentinel, no
  perfeccionista).
- Fallback: si no converge, descartar el caso (no forzar).

**Pendiente**: parámetros concretos.

### 10.5 Diversidad vs mundos "forzados a ser interesantes"
Si forzamos mundos con confounders + bifurcaciones + no-linealidades,
el Investigator entrenado sospecha todo en todos lados. Aprende un
estilo específico, no investigación en general.

Mitigación: seed papers diversos (papers con fenómenos variados, no
solo causal complejo).

**Pendiente**: cuál es el pool de seeds v1.5 y cómo lo diversificamos.

### 10.6 Transfer a ciencia real
Agente entrenado sobre SREG con brief abierto, ¿transfiere a
investigación real donde el ground truth no existe? Corral argumenta
que sí para razonamiento sobre problemas dados — hipótesis para
nuestro caso con brief abierto.

**Pendiente**: validar post-training con benchmark externo (Corral
mismo sirve) comparando métricas de proceso antes/después.

### 10.7 Primer seed paper / primer dominio MVP
No está decidido. Criterios:
- Seed con modelo matemático explícito (facilita WorldModel).
- Existe prior fuerte de LLM que podamos romper con diseño.
- Dominio semánticamente rico para narrativa del brief.

Candidatos iniciales:
- Farmacocinética simple (primer ODE): bien matemático, mucho paper,
  LLMs tienen prior pero hay espacio para confounders sorpresa.
- Epidemiología observacional (primer SCM): confounders clásicos,
  transfer a dominio real.
- Política educativa (primer SCM): heterogeneidad natural, múltiples
  outcomes.

**Pendiente**: elegir 1 para Fase 0.

---

## 11. Trade-offs conocidos

- **Error laundering entre agentes**: alucinación temprana entra al
  manifest y agentes downstream la tratan como hecho. Mitigación:
  cada handoff requiere evidencia ejecutable.
- **Optimización cruzada perversa**: Explorer empuja rareza, Validator
  empuja dureza, Case Writer empuja realismo. Sin criterio global, casos
  "bonitos" pero irresolubles. Mitigación: Validator tiene vista global.
- **Prose hacking residual**: Investigator elocuente puede convencer
  al Evaluator. Mitigación: span textual obligatorio + answer key
  numérico como anchor del Evaluator.
- **Dependencia de la calidad del Designer**: el bottleneck se mueve
  del compiler al Designer. Si el Designer genera mundos mal
  calibrados o rubrics débiles, todo falla. Pero el Designer es más
  ingenieriable que el compiler (tools de exploration iterativas,
  validation transversal).
- **Varianza del LLM judge**: `temperature=0` + ensembles + calibración
  humana en pilot.

---

## 12. Fases de implementación

### v1.5 — MVP estático multi-formalismo (Epic #63, ~6-10 semanas)

Paradigma estático (Investigator recibe dataset, responde una vez, fin).
**Los 3 formalismos entran desde el inicio**, no en fases separadas:
porque ODE/SDE no agregan complejidad ortogonal a la mecánica de
evaluación — agregan tipos de Environment y query_kinds adicionales,
pero el flujo Designer → Investigator → Evaluator es el mismo.

Componentes:
- Contratos Pydantic con `formalism: Literal["scm","ode","sde"]`.
- 3 implementaciones de Environment (SCMEnv, ODEEnv, SDEEnv).
- Verifier con 17 query_kinds (10 SCM + 7 dinámicos para ODE/SDE).
- Designer multi-formalismo (Architect elige formalismo según paper).
- Evaluator con `alpha=0.8` fijo.
- Casos canónicos: Birth Weight Paradox (SCM) + 1 ODE (p.ej. SIR).
- Pilot humano (10-20 casos mix, 2 anotadores).

**Gate go/no-go** (3 tests sobre los 2 casos canónicos):
1. Necessity ablation gradient.
2. Judge adversarial calibration.
3. Style/leak invariance.

Si los 3 pasan, v2 arranca. Si alguno falla, diagnose y ajustar.

### v2 — Interactividad Sherlock multi-turno (Epic #64, post-v1.5)

El Investigator deja de ser pasivo. Loop multi-turno con Environment-as-API:
- Primitivas `observe`, `intervene`, `simulate` como acciones del agente.
- Budget visible con cost scaling.
- AccessPolicy con public/internal rationale.
- `InvestigationLog` evaluado (trace scoring) — solo tiene sentido con multi-turno.
- Gate formal de identificabilidad.

**Pre-requisito**: v1.5 cierra con los 3 gates pasados.

**Gate go/no-go v2**:
1. Matched baseline interactivity gain.
2. Budget discrimination.
3. Access policy respect.

---

## 13. Lessons aplicadas del compiler v1

Extracto operativo de `research/notes/rethink_sreg_2026-04-23.md`
sección 11. Para contexto histórico: `research/notes/compiler_v1_postmortem.md`.

| Idea v1 | Aplicación v1.5 |
|---|---|
| Coverage matcher (extras como auxiliares) | Evaluator no penaliza claims extras, los acepta como bonus. |
| Assertion entailment (tolerance-aware) | Evaluator usa entailment cuali↔cuanti con tolerancia. |
| Abstención principled | Investigator sin DAG no debe hacer structural claims; van al Question Designer. |
| Canonicalization en gold | Rubrics tienen alternative phrasings. |
| No metric chasing | No premiar claims vagos; premiar specificidad. |

---

## 14. Lo que v1.5 NO incluye (scope freeze)

- Sherlock interactive investigation (intervención iterativa del
  Investigator sobre el Environment) — v2.
- Investigación hermenéutica / cualitativa pura.
- Generación automática de seed papers (los papers se curan
  manualmente al principio).
- Distilación del Evaluator a classifier chico — fase de post-
  implementación.
- Multi-agent training (agentes cooperando) — v2+.

---

## Referencias

- `research/notes/rethink_sreg_2026-04-23.md` — working doc con
  historia completa, debates, consultas a Codex.
- `research/notes/compiler_v1_postmortem.md` — post-mortem del compiler
  v1, progresión empírica, lessons learned.
- `research/synthesis/related_work_corral.md` — Corral synthesis y cómo
  se integra.
- `PROJECT.md` — LA PREGUNTA y presiones evolutivas (marcos filosóficos
  que v1.5 debe respetar).
