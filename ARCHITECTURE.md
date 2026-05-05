# SREG — Arquitectura
## Synthetic Research Environment Generator

> **Spec viva del sistema target (v1.5).** Sólo decisiones cerradas, componentes y contratos. Sin debates, sin trade-offs largos, sin lessons históricas.
>
> Vision y principios: `PROJECT.md` · Estado actual real: `CURRENT_STATE.md` · Trabajo pendiente: GitHub Issues · Debates históricos: `research/notes/v1_5_debates.md` · Re-diseño multi-agente: `research/notes/multi_explorer_redesign.md`.
>
> **Versión**: v1.5 en desarrollo activo (rama `dev`). Actualizado 2026-05-04. La arquitectura v1.x está preservada en `docs/archive/architecture_v1.md`.

---

## 0. Mapa macro

```
┌─────────────────────────┐  ResearchCase  ┌──────────────────┐  Claims  ┌────────────────────┐
│ 1. CASE GENERATION      │ ───────────────► │ 2. INVESTIGATOR  │ ────────► │ 3. EVALUATION      │
│    Designer multi-agente│                 │    (LLM agente)  │           │    (LLM judge)     │
└──────┬──────────────────┘                 └──────────────────┘           └─────────▲──────────┘
       │                                                                              │
       └──► Environment ────────── AnswerKey + provenance persistido ────────────────┘
            (interfaz ejecutable
             del WorldModel)
```

Tres bloques:

- **Case Generation (Designer multi-agente)**: lo más pesado. Architect + N Explorer/Designers (paralelo, multi-turn) + Selector + Case Writer + Validator transversal. Vive acá toda la complejidad nueva de v1.5.
- **Investigator**: relativamente delgado, ~10% del esfuerzo. Reusa código de v1. Single-turn en v1.5; multi-turno en v2.
- **Evaluator**: LLM judge sin acceso runtime al Environment. Lee AnswerKeys ya computados.

**Environment (transversal)**: interfaz ejecutable del WorldModel (`observe`, `intervene`, `simulate`). Lo usan los Explorer/Designers en design-time para producir AnswerKeys vía scripts Python (`EvidenceArtifact`). El Evaluator NO lo toca en runtime.

**No hay "Verifier" como motor separado.** Los AnswerKeys salen de scripts ejecutables que cada agente del Designer escribe contra el Environment. NO hay catálogo cerrado de operaciones canónicas (ver `multi_explorer_redesign.md` §1).

---

## 1. Tesis

El gap crítico de los agentes AI no es razonamiento puro, es **juicio investigativo**: qué examinar, cuándo pivotar, cómo separar evidencia específica del caso de priors del entrenamiento.

v1 construyó pipeline pero quedó bloqueado en evaluación: el compiler NL↔IR es frágil (techo ~83% en Suite 2). v1.5 **elimina el compiler** y reemplaza con `rubric + LLM judge + answer key grounded en Environment ejecutable`. La verdad numérica se respalda en scripts ejecutables (`EvidenceArtifact`) que cada agente del Designer escribe contra el Environment — sin catálogo cerrado. Se abre la puerta a dominios dinámicos (ODE en v1.5; SDE en v1.6).

Justificación empírica externa: Corral (Ríos-García/Jablonka et al. 2026) — el modelo base explica 41.4% de varianza, el scaffold 1.5%. *"Scaffold doesn't fix reasoning; training does."*

---

## 2. Vocabulario canónico

| Concepto | Nombre | Rol |
|---|---|---|
| Sistema matemático subyacente | **WorldModel** | SCM o ODE en v1.5 (SDE intrínseco en v1.6). Ecuaciones, grafos, parámetros. |
| Interfaz ejecutable | **Environment** | Expone `observe`, `intervene`, `simulate`. Cualquier agente del Designer puede escribir scripts Python que la usen. |
| Paper que inspira | **Seed Paper** | Input al Designer. WorldModel se inspira, no replica. |
| LLM meta-agente que diseña | **Designer** | Compuesto por: Architect + N Explorer/Designers (paralelo) + Selector + Case Writer + Validator transversal. |
| Fenómeno declarado por el Architect | **IntendedPhenomenon** | Lo que el Architect quiso poner en el WorldSpec. Guía a los Explorers (no es prescriptivo a nivel de pregunta). |
| Evidencia ejecutable | **EvidenceArtifact** | Script Python + resultado numérico contra el Environment. Patrón canónico para producir AnswerKeys y verificar fenómenos. |
| Pregunta candidata | **QuestionProposal** | Output de un Explorer/Designer. El Selector elige cuáles van al `QuestionsBundle` final. |
| Reporte advisory del Selector | **SelectionReport** | Calidad del pool de propuestas, diversidad, issues. Va al Validator. |
| Pregunta canónica con verdad | **GoldQuestion** | 3-5 por caso. AnswerKey + provenance ejecutable. |
| Estructura de evaluación | **Rubric** | Por GoldQuestion. Criterios concretos generados desde el contenido. |
| Verdad de referencia | **AnswerKey** | Estructurada, computada en design-time vía scripts. NO se recomputa en runtime. |
| Paquete que recibe el agente | **ResearchCase** | Brief + datos + contexto + tools. Sin GoldQuestions ni AnswerKeys. |
| LLM-agente que investiga | **Investigator** | Libre, con `python_exec` sobre datos. Single-turn en v1.5. |
| Afirmación en prosa | **Claim** | Output del Investigator. Sin formato impuesto. |
| LLM que compara y valida | **Evaluator** | Lee Claims y Rubrics. NO toca Environment en runtime. |

Convención externa respetada: `Environment` se alinea con SciGym, BoxingGym, DiscoveryWorld, Corral.

---

## 3. Flujo end-to-end

```
=== FASE A — DESIGN-TIME (Designer multi-agente) ===

  Seed Paper
     │
     ▼
  Paper Digestion ──► PaperInsights (mecanismos, fenómenos, trampas)
     │
     ▼
  World Architect ──► WorldSpec + intended_phenomena
     │                (lista corta a nivel mecanismo: "puse collider en X y U",
     │                 "puse mediation X→M→Y", etc.)
     │
     ▼ [compile]
  Environment (ejecutable)
     ▲                                                          ▲
     │                                                          │ scripts
     │ scripts                                                  │ Python
     │ Python                                                   │
  ┌──┴───────────────────────────────────────────────────────────┴──┐
  │ N Explorer/Designers (paralelo, multi-turn, focos derivados):   │
  │   · 2-3 guiados (uno por intended_phenomenon)                   │
  │   · 1 wildcard (libre, sin foco fijo)                           │
  │   cada uno: verify first, propose later                         │
  │   output: list[QuestionProposal]                                │
  └────────────────────────┬────────────────────────────────────────┘
                           ▼
                    [pool de propuestas]
                           │
                           ▼
                    Selector (advisory) ──► QuestionsBundle + SelectionReport
                                            (rank/filter/merge; NO invalida)
                           │
                           ▼
                    Case Writer ──► ResearchCase (brief + datasets + tools)
                           │
                           ▼
                    Validator transversal (ÚNICO ÁRBITRO)
                    lee TODO incl. SelectionReport
                    decide: passed | invalida con target_to_reiterate
                            ('world' / 'explorers' / 'case'). Max 2 vueltas.

=== FASE B — RUNTIME (Investigator) ===

  ResearchCase
     │
     ▼
  Investigator (LLM, python_exec sobre dataset)
     │   ├─► InvestigationLog (registrado, NO evaluado en MVP)
     ▼
  Claims (prosa libre)

=== FASE C — RUNTIME (Evaluator) — NO toca Environment ===

  Claims + QuestionsBundle (con AnswerKey persistido) ──► Evaluator
                                                              │
                                                              ▼
                                                          score por caso
```

---

## 4. Designer multi-agente

| Rol | Cantidad | Input | Output | Responsabilidad |
|---|---|---|---|---|
| **Paper Digestion** | 1 | Seed Paper | `PaperInsights` | Extrae mecanismos, fenómenos, trampas, counterintuitive priors. |
| **World Architect** | 1 | `PaperInsights` | `WorldSpec` + `intended_phenomena` | Diseña ecuaciones del WorldModel y declara qué fenómenos quiso poner. SCM o ODE. |
| **Explorer/Designer** | 3-4 paralelo | `WorldSpec` + Environment + foco | `list[QuestionProposal]` | Multi-turn. Cada uno tiene foco derivado (intended_phenomenon o "wildcard"). Verifica primero, propone preguntas después. |
| **Selector** | 1 | Pool de QuestionProposals | `QuestionsBundle` + `SelectionReport` | Rank / filter / merge. NO invalida — solo reporta calidad. |
| **Case Writer** | 1 | `QuestionsBundle` + Seed Paper | `ResearchCase` | Brief realista. Disfraza GQs sin filtrar respuestas. |
| **Validator (transversal)** | 1 | TODO | `ValidationReport` | ÚNICO ÁRBITRO: invalida cualquier etapa con `target_to_reiterate` ('world' / 'explorers' / 'case'). Max 2 vueltas. |

Decisiones operativas:

- **3-4 Explorer/Designers en paralelo**: 3 default, 4 si el WorldSpec viene cargado. NO 5 en MVP. Distribución: 2 guiados + 1 wildcard (caso 3); 3 guiados + 1 wildcard (caso 4).
- **Verify first, propose later**: si un Explorer no puede confirmar el `intended_phenomenon` que le tocó, NO inventa preguntas alternativas — reporta el problema. Eso evita ocultar bugs del Architect.
- **Selector advisory**: el `SelectionReport` puede declarar "calidad insuficiente, razones X/Y/Z" pero NO llama directo al Architect. El Validator lee el reporte y decide.
- **Validator con `target_to_reiterate`**: cuando invalida, declara qué etapa rehacer (no solo "no pasa"). Eso hace que el loop sea concreto.

---

## 5. Artefactos tipados (contratos clave)

Cada handoff requiere artefacto Pydantic, no prosa. Los schemas viven en `src/sreg/v1_5/contracts/`. Los contratos clave:

- **`PaperInsights`**: `paper_id`, `objective`, `entities`, `mechanisms`, `phenomena`, `complications`, `counterintuitive_priors`, `realism_bounds`.
- **`WorldSpec`**: `formalism: Literal["scm","ode"]`, `variables`, `relationships`, `parameters`, `metadata`, `intended_phenomena: list[IntendedPhenomenon]`. Validator cruzado: `observation_noise` solo en ODE y `>= 0`.
- **`IntendedPhenomenon`**: `id`, `kind: str` (libre, ej. "collider", "mediation"), `description`, `relevant_variables`. Vive a nivel mecanismo, NO a nivel pregunta.
- **`EvidenceArtifact`**: `script: str` (Python ejecutable contra Environment), `numerical_result: dict`, `tag: str | None` (descriptivo, no normativo).
- **`Phenomenon`**: `kind: str` (string libre, no enum cerrado), `description`, `evidence: EvidenceArtifact`, `tags: list[str]`.
- **`PhenomenaManifest`**: lista de `Phenomenon`, `world_id`, `interesting_score`.
- **`QuestionProposal`** (multi-agent): `proposal_id`, `author_run_id`, `focus`, `question_text`, `rubric_draft`, `answer_key`, `answer_key_provenance: list[EvidenceArtifact]`, `status: Literal["proposed","verified","rejected_unconfirmed"]`.
- **`SelectionReport`** (advisory): `selected_proposals`, `rejected_proposals`, `merged_proposals`, `quality_issues`, `diversity_score`.
- **`GoldQuestion`** (final): `id`, `text`, `weight ∈ {0.08, 0.12, 0.16, 0.20}`, `role: required|support`, `answer_key`, `answer_key_provenance: list[EvidenceArtifact]` (mínimo 1), `identification_hint`, `rubric`.
- **`Rubric`**: lista de `Criterion` (`min_length=1`). Debe tener al menos uno con `role="core"`.
- **`Criterion`**: `text`, `weight ∈ {1,2,3}`, `role: core|bonus`, `anchor: AnswerKeyAnchor`, `scoring_hint`, `requires_span: bool`.
- **`AnswerKeyAnchor`**: `path`, `match: approx|equals|enum|mentioned`, `tolerance`, `value`. Validator cruzado por modo de match.
- **`ResearchCase`**: `case_id`, `brief`, `context`, `datasets`, `tools`. **Sin** GoldQuestions, AnswerKeys, IntendedPhenomena (frontera público/oculto, ver §10).
- **`InvestigationLog`**: `actions`, `hypotheses_log`, `final_claims`. Registrado siempre; NO evaluado en MVP.
- **`InvestigatorAction`**: `step`, `kind: Literal["python_exec","hypothesis","pivot","submit"]`, `payload`, `rationale`, `epistemic_tag: Literal["H","T","E","J","U","C"] | None`. El tag (Corral) es telemetría no-scoring (#53). `observe`, `intervene`, `simulate` NO son `kind` de v1.5 — son v2.
- **`ValidationReport`**: `passed`, `invalidated_artifacts`, `issues`, `adversarial_attempts`, `target_to_reiterate: Literal["world","explorers","case"] | None`. Validator cruzado: si `passed=True` el target debe ser `None`; si `passed=False` el target es obligatorio.

Pesos discretos en `GoldQuestion` y `Criterion` son anti-ajuste-fino (evita micro-optimización arbitraria).

---

## 6. Rubric design

Cada GoldQuestion tiene una Rubric. **Los criterios concretos los genera el agente que armó la pregunta (Explorer/Designer) desde el contenido específico de la pregunta.** No hay templates por categoría (rompería el principio "UN método para todo" en `PROJECT.md`).

**4 dimensiones universales** — son **guideline editorial** para armar criterios, NO un enum del schema:

1. **Fidelidad**: ¿lo que dice corresponde a la verdad del WorldModel?
2. **Justificación**: ¿está respaldada por evidencia o razonamiento, no por tono?
3. **Calibración**: ¿maneja la incertidumbre? Incluye abstención calibrada.
4. **Especificidad**: ¿es concreta y verificable, no vaga?

Los criterios concretos materializan estas dimensiones para esa pregunta. Las dimensiones son siempre las mismas; los criterios cambian.

**Split core vs bonus en cada Rubric**:
- **Core**: criterios obligatorios para responder bien la GQ. Aportan 70-85% del score_GQ.
- **Bonus**: caveats, calibración, robustness. Aportan 15-30%. **No compensan errores del core.**

**Fórmula**: `score_GQ = alpha × score_core + (1 - alpha) × score_bonus`, con `alpha = 0.8` por **default** (configurable).

**Reglas invariantes**:
- **Span textual obligatorio**: cada criterion acreditado requiere span citado del reporte. Sin span → 0.
- **Nunca acreditar por terminología sola** si el span contradice el anchor.
- **Assertion entailment tolerante**: claim cuantitativo satisface criterio cualitativo con tolerancia.
- **Alternative phrasings** dentro de cada Criterion (anti-ajuste fino al wording del Investigator).

---

## 7. Evaluator

**Decisión clave: el Evaluator NO toca el Environment en runtime.** Toda la formalización vive en design-time; el Evaluator solo lee `AnswerKey` ya computado por el agente que armó la pregunta. Razones: reproducibilidad, costo en RL training, frontera limpia entre quién investiga y quién evalúa.

Pipeline: dos pasos por GoldQuestion.

```
Para cada GoldQuestion del caso:

  PASO 1 — IDENTIFICACIÓN (binary)
    Input: reporte completo + GoldQuestion.identification_hint
    Output: bool "¿el Investigator aborda este tema?"
    Si no → score_GQ = 0, siguiente GQ.

  PASO 2 — COMPLETION (graduada, sólo si identificó)
    Para cada Criterion de la Rubric:
      Input: reporte + Criterion.scoring_hint + Criterion.anchor + AnswerKey (ya escrito)
      Output: {cumplido: bool, span: str, razón: str}

  score_GQ = identification × (alpha × score_core + (1 - alpha) × score_bonus)

score_total_caso = Σ GQ.weight × score_GQ
```

**Reglas del Evaluator**:
- **No ejecuta queries arbitrarias del Environment.** Si necesita verificar contra el SCM, eso lo hizo el Designer en design-time vía `EvidenceArtifact`.
- **Claims espontáneas fuera de las GoldQuestions** no entran al score principal. (Future: novel-but-correct lane si Fase 0 lo justifica.)
- **Contradicciones explícitas restan**: shotgun science (20 claims contradictorias) no se premia "la que aciertó".

---

## 8. Score y reporting

El score primario que computa el Evaluator es **por GoldQuestion**. Eso se agrega ponderado al score del caso.

Para análisis y reporting agregado (no parte del schema canónico ni del scoring), se puede derivar una **vista por dimensión de habilidad investigativa** clasificando cada GoldQuestion (framing, identification, estimation, intervention prediction, confounding detection, mediation analysis, epistemic calibration). Esta vista es **derivada**, no canónica. **Process quality** (calidad del trace, motifs Corral) NO entra en v1.5 (issue #53).

---

## 9. Cobertura de formalismos y tipos de investigación

**Formalismos en v1.5**:
- **SCM** (causal estático): observaciones puntuales, do-operations clásicas, mediación, identifiability.
- **ODE** (dinámica determinista): trayectorias, before/after, intervenciones temporales. Soporta `observation_noise` opcional para datos con error de medición.

**Formalismo en v1.6**:
- **SDE** (dinámica estocástica intrínseca): difusión molecular, mercados, biofísica con ruido térmico.

**No hay catálogo cerrado de operaciones canónicas en el Environment.** Cualquier cómputo numérico que un agente del Designer necesite — ATE marginal, ATE estratificado, equilibrium, sensitivity, identifiability check, etc. — se hace escribiendo un script Python contra el Environment y registrando el resultado en `EvidenceArtifact`. La diversidad de preguntas es emergente del proceso multi-agente, no de un catálogo (ver `multi_explorer_redesign.md`).

**Tipos de investigación cubiertos**: causal, predictiva, descriptiva, system mapping, epistemológica, "best framework". Con ODE además: escalas temporales, oscilaciones, bifurcaciones, control óptimo, identificación de parámetros dinámicos.

---

## 10. Frontera público / oculto

| Artefacto | ¿Lo ve el Investigator? |
|---|---|
| `ResearchCase` (`brief`, `context`, `datasets`, `tools`) | **Sí.** |
| `WorldSpec`, `IntendedPhenomenon`, `PhenomenaManifest`, `QuestionProposal`, `SelectionReport`, `QuestionsBundle`, `GoldQuestion`, `AnswerKey`, `EvidenceArtifact`, `Rubric`, `ValidationReport` | **No.** |
| `AccessPolicy.public_rationale` (v2) | Sí. |
| `AccessPolicy.internal_rationale` (v2) | No. |

Garantía operativa: el constructor de prompts del Investigator **no puede** acceder a campos ocultos. Tests de frontera (CP0a + CP0b + walk recursivo) verifican que `ResearchCase.model_dump()` no expone ningún campo restringido.

---

## 11. Lo que NO incluye v1.5 (no-goals concretos)

- **Multi-turno / interacción Sherlock** — Epic #64 (v2). El Investigator es single-turn en v1.5.
- **`observe`, `intervene`, `simulate` como acciones del Investigator** — son v2. En v1.5 el Investigator usa `python_exec` sobre el dataset que ya recibió.
- **SDE intrínseco** — v1.6.
- **Trace scoring del InvestigationLog** — issue #53.
- **Identifiability gate formal universal** — issue #54.
- **Claims espontáneas fuera de GoldQuestions** — no entran al score principal.
- **Generación automática de seed papers** — los papers se curan a mano al inicio.
- **Distilación del Evaluator a classifier chico** — post-MVP.
- **Catálogo cerrado de operaciones canónicas** — explícitamente rechazado en re-diseño multi-agente (sesgo a "siempre lo mismo"). Cada agente del Designer escribe sus propios scripts.

---

## 12. Roadmap (high-level)

| Versión | Alcance | Estado |
|---|---|---|
| **v1.5** (Epic #63) | MVP estático SCM + ODE. Designer multi-agente, Evaluator con rubric + answer key + provenance ejecutable, casos diversos por formalismo, 3 tests go/no-go. | En desarrollo. |
| **v1.6** | Agrega SDE intrínseco. | Post-v1.5. |
| **v2** (Epic #64) | Interactividad multi-turno tipo Sherlock: budget visible, AccessPolicy, primitivas observe/intervene/simulate como acciones del Investigator. | Post-v1.5. |

Detalle del orden de implementación de v1.5 y del re-diseño multi-agente: ver body de Epic #63, Ronda 11 en `research/notes/v1_5_debates.md`, y `research/notes/multi_explorer_redesign.md`.

---

## 13. Diversidad de casos — invariante operativo

v1.5 NO entrega un caso canónico único — entrega **varios casos diversos por formalismo**, cubriendo distintos dominios, distintos tipos de trampa (collider, paradoja de Simpson, mediación, no-linealidad, identifiability, bifurcaciones), distintas dificultades. Casos famosos (ej. Birth Weight Paradox SCM, SIR ODE) son **smoke tests**, no evidencia principal.

La diversidad emergente del proceso multi-agente (N Explorers con focos distintos + wildcard) es complementaria a la diversidad de casos. Sin diversidad de casos, los Explorers tendrían los mismos `intended_phenomena` siempre.

Anti-memorización integrada al flujo:
- **Corpus abstracto isomorfo**: variables `X`, `M`, `Y`; briefs neutros; AnswerKeys generadas por scripts ejecutables. Asset permanente del repo.
- **Gate duro post-Evaluator**: tests `answer_key_sensitivity` (mismo caso, AnswerKey alterado → score sigue al AnswerKey, no al prior del modelo) e `isomorph_invariance` (mismo caso renombrado → score parecido).
- **Re-ejecución post-Selector y post-Validator**: el Designer puede reintroducir leak por wording de briefs o rubrics demasiado "teaching-to-the-test".

Regla operativa: si el judge acierta en casos famosos pero falla en suite abstracta → rojo. Si pasa la abstracta y los famosos → señal real.

---

## Apéndice — referencias

- Re-diseño multi-agente del Designer (canon): `research/notes/multi_explorer_redesign.md`.
- Ejemplo canónico completo de un caso SCM: `research/examples/birth_weight_paradox.md`.
- Postmortem del compiler v1 (por qué lo matamos): `research/notes/compiler_v1_postmortem.md`.
- 11+ rondas de debate de diseño v1.5: `research/notes/v1_5_debates.md`.
- Related work: `research/synthesis/related_work_corral.md`, `related_work_sandmle.md`, `related_work_scigym.md`, `related_work_sciagentgym.md`.
- Arquitectura v1 (legacy, código en `main`): `docs/archive/architecture_v1.md`.
