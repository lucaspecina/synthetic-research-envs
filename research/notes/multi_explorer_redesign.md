# Re-diseño multi-agente del Designer (v1.5)

> **Doc canónico** del re-diseño que mata el catálogo cerrado de `query_kinds`
> y reemplaza el flujo lineal Explorer → Question Designer por un flujo
> multi-agente con N Explorers/Designers en paralelo + un Selector advisory.
>
> Validado con Codex en consulta dedicada (2026-05-04).
> **Antes de aplicar a `ARCHITECTURE.md`** se aprueba en este doc.
>
> Estado del repo: `dev`. Contratos #55 mergeados. Environment SCM mergeado
> (15 tests OK). Verifier con dispatch programado pero NO commiteado — se
> borra como parte de este re-diseño.

---

## 1. Por qué cambiamos el diseño

### El problema 1 — Catálogo cerrado de `query_kinds`

El diseño anterior tenía un catálogo de 16 operaciones canónicas (10 SCM + 6 ODE) que el `Verifier` despachaba por dispatch dict. Cada `GoldQuestion` declaraba un `verifier_query` con un `query_kind` del catálogo.

**Riesgos detectados**:

- **Sesgo a "siempre lo mismo"**: si el Question Designer sabe que solo 16 operaciones producen `AnswerKey` numérico, va a inventar preguntas que mapeen a esas 16. Resultado: todos los casos pueden tener una pregunta de ATE, una de mediation, etc. — predictibilidad alta.
- **Eco a `AtomicSpec` v1**: aunque los `query_kinds` no restringen lo que dice el solver (a diferencia del compiler v1), restringen lo que el sistema puede verificar numéricamente. Mismo tipo de trampa, otra puerta.
- **Inconsistencia con el `Explorer`**: el `Explorer` ya escribe scripts Python arbitrarios contra el `Environment` y captura el resultado en `ExecutableEvidence`. El `Question Designer` hacía lo mismo de manera totalmente distinta (dispatch dict). Doble mecanismo para la misma operación.

**Decisión**: matar el catálogo. Los `AnswerKey` se producen con el mismo patrón que `ExecutableEvidence`: el agente escribe un script, el sistema lo ejecuta contra el `Environment`, el resultado queda registrado.

### El problema 2 — Doble trabajo Architect ↔ Explorer

El flujo anterior asumía que el `Explorer` exploraba el mundo a ciegas para encontrar fenómenos interesantes. Pero el `World Architect` ya construye el mundo CON INTENCIÓN — basado en `PaperInsights` (mecanismos esperados, fenómenos típicos del paper). Un mundo aleatorio no se construye así.

Si el Architect ya sabe qué fenómenos quiso poner, hacer que el Explorer redescubra todo desde cero es ineficiente y puede no encontrar lo que el Architect quería destacar.

**Decisión**: que el Architect produzca `intended_phenomena` (lista corta de "qué quise poner") como guía para los Explorers. Los Explorers verifican y profundizan, no exploran a ciegas.

### El problema 3 — Flujo lineal Explorer → Question Designer

El flujo anterior corría 1 Explorer + 1 Question Designer. Eso da un único "punto de vista" sobre el mundo. Sin diversidad real entre casos generados desde el mismo seed paper.

**Decisión**: N Explorer/Designers en paralelo (multi-turn), cada uno con un foco distinto. Diversidad emergente del proceso, no de un catálogo.

---

## 2. Nuevo flujo

```
Paper Digestion → PaperInsights
    ↓
World Architect → WorldSpec + intended_phenomena (lista corta a nivel
                  fenómeno/mecanismo: "puse collider en X y U",
                  "puse mediation X→M→Y", "puse bifurcación en
                  parámetro α", etc. — NO a nivel pregunta concreta)
    ↓
N Explorer/Designers (paralelo, multi-turn, focos derivados del WorldSpec)
    cada uno tiene un foco específico:
      · "verifica y profundiza el collider entre X y U" (guiado)
      · "verifica y profundiza la mediation X→M→Y" (guiado)
      · "explorá libre, encontrá fenómenos emergentes" (wildcard)
    cada uno multi-turn:
      · turno 1: verifica el intended_phenomenon con script contra Environment
      · si confirma → profundiza, propone preguntas con AnswerKey ejecutable
      · si NO confirma → reporta "intended_phenomenon X NO se materializa
                         en este mundo" y termina sin proponer preguntas
                         (regla dura: verify first, propose later)
    output: list[QuestionProposal]
    ↓
[Pool de propuestas]
    ↓
Selector → rank/filter/merge → QuestionsBundle (3-5 GoldQuestions)
    también produce SelectionReport con calidad de las propuestas
    (puede marcar "calidad insuficiente, razones: ..." pero NO invalida
     directamente al Architect — solo reporta)
    ↓
Case Writer → ResearchCase (brief, datasets, tools)
    ↓
Validator transversal (ÚNICO ÁRBITRO con autoridad de invalidar)
    lee TODO incluido SelectionReport → decide:
      · pasar adelante, o
      · invalidar → re-iterar especificando target:
          · target="world": rehacer World Architect
          · target="explorers": rehacer Explorer/Designer round
          · target="case": rehacer Case Writer
        max 2 vueltas total por caso. Si no converge, descartar y probar
        otro seed paper.
```

---

## 3. Decisiones clave

### 3.1 `intended_phenomena` a nivel mecanismo, no a nivel pregunta

Un `IntendedPhenomenon` describe **qué se quiso poner mecanísticamente**, no **qué pregunta hacer**. Ejemplos válidos:

- "collider entre `smoking` y `hidden_u` con `LBW` como collider"
- "mediation `smoking → BW → mortality`"
- "bifurcación en parámetro `R0` cerca de 1.0"

Ejemplos NO válidos (eso lo decide el Explorer):

- ~~"preguntá el ATE marginal de smoking sobre mortality"~~
- ~~"hacé un análisis de sensibilidad sobre R0"~~

Esto evita que el Architect se vuelva fuente única de qué se pregunta. El espacio de preguntas posibles para un mundo dado es siempre más grande que la lista de mecanismos puestos.

### 3.2 Verificación dura: verify first, propose later

Cada Explorer multi-turn empieza por confirmar el `intended_phenomenon` que le tocó. Si la confirmación falla, **el Explorer NO propone preguntas alternativas creativas**. Reporta el problema y termina.

Razón: si un Architect roto diseñó un mundo donde el collider no se materializa, queremos saberlo. Si el Explorer "compensa" creativamente, ocultamos el bug del Architect bajo preguntas válidas pero no relacionadas con la intención original. El Validator transversal después decide si re-iterar al Architect.

### 3.3 Wildcard explícito (1 de los N)

Uno de los N Explorers no recibe `intended_phenomena` y explora libre. Su rol: descubrir fenómenos emergentes que el Architect no anticipó.

Razón (Codex): el Selector llega demasiado tarde para "mirar emergentes" — para cuando ve las propuestas, los Explorers ya gastaron sus turnos pegados a los `intended_phenomena`. Aceptar el límite (no buscar emergentes) ahorra muy poco comparado con tener 1 Explorer libre.

Distribución MVP:
- **3 Explorers** (default): 2 guiados + 1 wildcard.
- **4 Explorers** (cuando el WorldSpec viene cargado, ej: muchos `intended_phenomena`): 3 guiados + 1 wildcard.
- **NO 5 Explorers** en MVP: el costo en LLM calls no compensa el incremento marginal de diversidad.

### 3.4 Selector advisory, no árbitro

El Selector tiene 4 tareas: `rank, filter, merge, reportar calidad`. NO tiene 5ta tarea de "invalidar al Architect" ni de "pedir más evidencia".

Si las propuestas son flojas, el Selector lo marca en su `SelectionReport.quality_issues`. Eso va al Validator transversal, que es quien decide si re-iterar y a qué etapa.

Razón: gobernanza concentrada. Dos árbitros (Selector + Validator) crean ambigüedad y loops difíciles de razonar.

### 3.5 Validator único árbitro CON target

El `ValidationReport` ya existe (en contratos #55) pero hay que extenderlo con un campo `target_to_reiterate: Literal["world", "explorers", "case"] | None`.

Razón (Codex): si el Validator solo dice "no pasa, re-itere", el sistema no sabe qué rehacer. El target hace que el loop sea concreto. Si `target="world"`, vuelve al Architect. Si `target="explorers"`, los Explorers corren de nuevo sobre el mismo WorldSpec. Si `target="case"`, solo el Case Writer.

### 3.6 No hay "Selector pide más evidencia" en MVP

Si las propuestas tienen evidencia floja, el Selector lo registra y deja que el Validator decida qué hacer (probablemente `target="explorers"` para re-correr con los mismos `intended_phenomena`). No hay un sub-loop interno entre Selector y Explorers.

Razón: mantener el sistema simple para MVP. Si después vemos que vale la pena un sub-loop, se agrega.

---

## 4. Cambios concretos en contratos Pydantic

### Crear

**`IntendedPhenomenon`** (nuevo):

```python
class IntendedPhenomenon(BaseModel):
    """Lo que el World Architect quiso poner intencionalmente en el WorldSpec."""
    id: str
    kind: str  # tag libre: "collider", "mediation", "bifurcation", "non_linearity", etc.
    description: str  # NL: qué fenómeno y entre qué variables
    relevant_variables: list[str]
```

**`EvidenceArtifact`** (nuevo, reemplaza el rol de `VerifierQuery`):

```python
class EvidenceArtifact(BaseModel):
    """Evidencia ejecutable que respalda un AnswerKey o un Phenomenon.

    Patrón: el agente escribe un script Python que recibe el Environment,
    lo ejecuta, y captura el resultado numérico.
    """
    script: str  # código Python que usa env.observe / env.intervene / env.simulate
    numerical_result: dict[str, Any]  # output del script
    notes: str | None = None
    tag: str | None = None  # opcional: descriptivo para análisis agregado
                            # (NO restrictivo, NO valida contra catálogo)
```

**`QuestionProposal`** (nuevo):

```python
class QuestionProposal(BaseModel):
    """Output de un Explorer/Designer: una pregunta candidata con su evidencia."""
    proposal_id: str
    author_run_id: str  # qué Explorer la generó
    focus: str  # qué intended_phenomenon (o "wildcard") motivó esta propuesta
    question_text: str
    rubric_draft: Rubric
    answer_key: AnswerKey
    answer_key_provenance: list[EvidenceArtifact]  # plural: una pregunta puede
                                                    # necesitar varios scripts
    status: Literal["proposed", "verified", "rejected_unconfirmed"]
    tags: list[str] = Field(default_factory=list)
```

**`SelectionReport`** (nuevo):

```python
class SelectionReport(BaseModel):
    """Output advisory del Selector. NO tiene autoridad de invalidar."""
    selected_proposals: list[str]  # proposal_ids elegidos
    rejected_proposals: list[str]
    merged_proposals: dict[str, list[str]]  # final_id -> [source_proposal_ids]
    quality_issues: list[str]  # problemas detectados en el pool
    diversity_score: float | None  # qué tan diversas son las preguntas finales
```

### Modificar

**`WorldSpec`**: agregar `intended_phenomena: list[IntendedPhenomenon] = Field(default_factory=list)`.

**`Phenomenon.kind`**: cambiar de `Literal[6 valores cerrados]` a `str` libre. Agregar `tags: list[str]` opcional para taxonomía no normativa.

**`GoldQuestion.verifier_query`**: cambiar de un solo `VerifierQuery` a `answer_key_provenance: list[EvidenceArtifact]`. Una pregunta puede necesitar evidencia de varios scripts.

**`ValidationReport`**: agregar `target_to_reiterate: Literal["world", "explorers", "case"] | None = None`.

### Borrar / deprecar

**`VerifierQuery`**: el contrato actual con `query_kind: str + args: dict` deja de tener sentido sin un catálogo cerrado. Se borra.

### Mantener sin cambios

- `PaperInsights`
- `ExecutableEvidence` (ya estaba bien — el patrón se generaliza con `EvidenceArtifact`)
- `Rubric`, `Criterion`, `AnswerKey`, `AnswerKeyAnchor`
- `ResearchCase`, `Dataset`, `ToolSpec`
- `InvestigationLog`, `InvestigatorAction`, `Claim`, `HypothesisEntry`
- `ValidationIssue`, `AdversarialAttempt`

---

## 5. Cambios en código que ya está commiteado o programado

### Borra

- `src/sreg/v1_5/verifier/` completo: dispatch dict, funciones canónicas SCM (`verify_ate`, etc.), `Verifier` fachada.
- Tests de `verifier/` (no se commitearon, pero los tengo localmente).

### Mantiene

- `src/sreg/v1_5/contracts/` (con los cambios listados arriba).
- `src/sreg/v1_5/environment/` (Protocols, SCMEnvironmentAdapter — sirven igual).
- Tests de `contracts/` (con ajustes mínimos por los cambios de schema).
- Tests de `environment/` (sin cambios).

### Eventualmente agrega

- Helpers de bajo nivel SI emergen como necesarios (ej. `bootstrap_ci`). NO de alto nivel (no `compute_ate`, etc.).

---

## 6. Cambios en docs

- **`ARCHITECTURE.md`**: sacar refs a `query_kinds`, `Verifier con dispatch`, "16 operaciones canónicas". Agregar el flujo multi-agente, `intended_phenomena`, Selector advisory, Validator con `target_to_reiterate`.
- **`research/notes/v1_5_query_matrix.md`**: archivar. Era la spec congelada del catálogo cerrado. Con el catálogo muerto, el doc queda como referencia histórica del approach desechado. Mover a `research/archive/pre_v1_5/v1_5_query_matrix.md` o similar.
- **`research/notes/v1_5_debates.md`**: agregar Ronda 12 con este re-diseño y las consultas a Codex que lo validaron.
- **Body de issue #56** (Environment + Verifier): re-titular y re-scopear. Ya no es "Environment + Verifier multi-formalismo (10 SCM + 6 ODE)". Ahora es "Environment infra (SCM + ODE) + helpers mínimos". El "Verifier dispatch" desaparece; cualquier cómputo lo hace cada agente con sus propios scripts.
- **Body de issue #58** (Designer): re-titular y re-scopear. Ahora es "Designer multi-agente: Architect + N Explorer/Designers + Selector + Case Writer". El rol del antiguo "Question Designer" se distribuye entre Explorers y Selector.

---

## 7. Riesgos abiertos (a vigilar durante MVP)

- **Diversidad real entre los N Explorers**: si los focos derivados se construyen mal, los N pueden converger. Hay que diseñar el prompt builder con cuidado.
- **Wildcard puede divagar**: el Explorer wildcard sin foco podría perder turnos en cosas irrelevantes. Si vemos que el wildcard rinde poco en pilot humano, ajustamos (ej. darle restricción tipo "buscá fenómenos emergentes que no estén en `intended_phenomena`").
- **Selector como cuello de botella oculto**: si el Selector elige mal, todo el caso sufre. El `SelectionReport` con `quality_issues` mitiga pero no resuelve. Pilot humano va a calibrar.
- **Validator sobrecargado**: ahora tiene que procesar más artefactos (intended_phenomena + N proposals + SelectionReport + ResearchCase). Hay que ver si rinde con un solo prompt.
- **Costo en LLM calls**: 3-4 Explorers multi-turn aumenta el costo por caso. Ver si rinde para RL training o si hay que paralelizar de manera más agresiva.

---

## 8. Próximos pasos

1. Aplicar cambios a contratos Pydantic v1.5.
2. Borrar `src/sreg/v1_5/verifier/` (dispatch + funciones canónicas).
3. Actualizar `ARCHITECTURE.md`.
4. Actualizar bodies de issues #56 y #58 en GitHub.
5. Codex review final del cambio aplicado.
6. Commit + push.

Después de eso, recién retomamos implementación: probablemente arrancando por #58 (Designer multi-agente) ya que es donde está la mayor complejidad nueva. #56 queda mucho más chico (solo Environment + helpers básicos).
