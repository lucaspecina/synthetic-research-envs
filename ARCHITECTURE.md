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
    │
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
    id: str
    text: str
    rubric: Rubric
    answer_key: AnswerKey
    verifier_query: VerifierQuery  # mapeo reproducible
    epistemic_operation: str  # "identification", "estimation", etc.

class Rubric(BaseModel):
    core_criteria: list[CoreCriterion]  # 70-85% del score
    epistemic_bonuses: list[EpistemicCriterion]  # 15-30%

class CoreCriterion(BaseModel):
    description: str
    weight: float
    anchor: AnswerKeyAnchor  # qué del AnswerKey satisface esto
    requires_span: bool = True  # judge debe citar texto del Claim

class ResearchCase(BaseModel):
    brief: str
    context: str  # narrativa, background theory opcional
    datasets: list[Dataset]
    tools: list[ToolSpec]
    # NOTA: no incluye QuestionsBundle (hidden del Investigator)

class ValidationReport(BaseModel):
    passed: bool
    invalidated_artifacts: list[str]  # cuáles etapas fallaron
    issues: list[ValidationIssue]
    adversarial_attempts: list[AdversarialAttempt]  # intentos de hackeo
```

---

## 6. Rubric design

Híbrido core analytic + epistemic bonus. Decisión tomada post-consulta
Codex (ver notes/rethink sección 6).

```
score_por_GoldQuestion =
    core_analytic     (70-85% del peso total)
  + epistemic_bonus   (15-30% del peso total)
```

**Core analytic**:
- Criterios atómicos y acumulativos.
- Cada criterio ligado a claim **explícito** del Investigator.
- Verificables contra el Environment.
- Requieren **span textual citado** del reporte del Investigator para
  acreditarse. Sin span = 0.

**Epistemic bonus**:
- Caveats, identifiability awareness, reconocimiento de límites,
  robustness checks, incertidumbre bien calibrada.
- **NO compensa errores del core**. Si el Investigator afirma
  causalidad equivocada, no se salva con caveats elegantes.

**Niveles BARS (Behaviorally Anchored Rating Scales)**: solo como anclas
de redacción para el Evaluator (ayudan a calibrar qué espera cada
criterio). NO son mecanismo de puntuación.

**Alternative phrasings por criterio**: lesson rescatada del compiler
v1 (canonicalization). Ejemplo: "el efecto es positivo" ≡ "el outcome
aumenta con el tratamiento" ≡ "X sube cuando T sube". El Question
Designer genera alternativas; el Evaluator las consume como equivalentes.

**Assertion entailment** (tolerance-aware): si el Claim es cuantitativo
("efecto = 0.42 ± 0.05") y el criterio es cualitativo ("identifica que
es positivo"), el Evaluator aplica entailment tolerante: 0.42 > tolerance
satisface "positivo" sin necesidad de match textual exacto.

---

## 7. Evaluator con acceso al Environment

Pipeline en 3 pasos:

```
1. EXTRACT: identificar claims explícitos del reporte del Investigator
            (pares span + afirmación cuantitativa o cualitativa).

2. MAP:     para cada criterio de cada Rubric, buscar el claim que lo
            acredita. Requiere span textual; sin span = 0.

3. VERIFY:  para claims que soportan criterios cuantitativos, ejecutar
            el Environment con la query correspondiente. Comparar
            contra Claim del Investigator vía assertion entailment.

            Para claims ESPONTÁNEAS (no matchean ninguna Rubric pero
            son testeables), el Evaluator puede ejecutar el Environment
            libremente para validarlas. Si validan → auxiliary bonus.
```

**Decisión importante**: el Evaluator tiene **libertad de ejecución**
sobre el Environment (no set limitado de operaciones). Razón: limitar
empobrece al judge. Costos (reproducibilidad, varianza) se manejan
con prompt engineering estricto + temperature=0 + logs versionados.

**Auxiliares** (coverage matcher lesson del compiler v1): claims extras
del Investigator que no matchean Rubric pero son correctos se aceptan
como auxiliares. **Nunca penalizan**. Puede haber bonus por auxiliares
valiosos (decidir durante implementación).

**Contradicciones explícitas restan**: si el Investigator tira 20
afirmaciones contradictorias, no se premia "la que aciertó". Shotgun
science se penaliza.

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

### Cubre bien
- Investigación causal (efectos, confounders, mediación).
- Investigación predictiva (predicciones numéricas contra Environment).
- Descriptiva (distribuciones, patrones, clustering).
- System mapping (estructura del grafo, conexiones).
- Epistemológica (¿qué se puede concluir?).
- "Mejor marco conceptual" (componentes verificables contra estructura
  del WorldModel: ¿es cadena o feedback? ¿es lineal o no? etc.).

### No cubre (out of scope v1.5)
- Investigación hermenéutica / cultural / ética / estética.
- Diseño de experimentos (requiere Sherlock interactivo — v2).
- Teoría fundamentada puramente cualitativa.

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

### Fase 0 — SCM MVP (4-6 semanas)
- Un solo dominio SCM.
- Designer "monolítico" (mismo modelo, prompts distintos por rol) con
  artefactos tipados Pydantic ya separados.
- Rubric + Evaluator con acceso al Environment ejecutable.
- Pilot humano (10-20 casos, 2 anotadores) para calibrar el judge.
- **Gate**: si el Evaluator no alcanza ≥ 85% agreement humano, pausar
  y recalibrar antes de seguir.

### Fase 1 — ODE + separación opcional (4-6 semanas)
- Agregar dominio ODE (farmacocinética o similar).
- Evaluar si separar agentes de Designer en modelos distintos agrega
  valor vs complica.
- Primera integración con Corral behavioral annotation como métrica
  secundaria.

### Fase 2 — SDE + paper (4-6 semanas)
- Agregar dominio SDE.
- Estabilizar pipeline.
- Experimentos before/after con RL training para demostrar tesis.
- Paper submission-ready.

Total: ~3 meses. Cada fase con gate de ir/no-ir.

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
