# SREG — Arquitectura
## Synthetic Research Environment Generator

> **Spec viva del sistema target (v1.5).** Sólo decisiones cerradas, componentes y contratos. Sin debates, sin trade-offs largos, sin lessons históricas.
>
> Vision y principios: `PROJECT.md` · Estado actual real: `CURRENT_STATE.md` · Trabajo pendiente: GitHub Issues · Debates históricos: `research/notes/v1_5_debates.md`.
>
> **Versión**: v1.5 en desarrollo activo (rama `dev`). Actualizado 2026-05-04. La arquitectura v1.x está preservada en `docs/archive/architecture_v1.md`.

---

## 0. Mapa macro

```
┌─────────────────────────┐  ResearchCase  ┌──────────────────┐  Claims  ┌────────────────────┐
│ 1. CASE GENERATION      │ ───────────────► │ 2. INVESTIGATOR  │ ────────► │ 3. EVALUATION      │
│    Designer + Validator │                 │    (LLM agente)  │           │    (LLM judge)     │
└──────┬──────────────────┘                 └──────────────────┘           └─────────▲──────────┘
       │                                                                              │
       └────► Verifier (transversal) ────────── AnswerKey persistido ─────────────────┘
              motor matemático determinista
              (oracle SCM/ODE-grounded; v1.6 agrega SDE)
```

Tres bloques + 1 motor transversal:

- **Case Generation (Designer)**: lo más pesado — 5 roles (Paper Digestion, World Architect, Explorer, Question Designer, Case Writer) + Validator. Vive acá toda la complejidad nueva de v1.5.
- **Investigator**: relativamente delgado, ~10% del esfuerzo. Reusa código de v1. Single-turn en v1.5; multi-turno en v2.
- **Evaluator**: LLM judge sin acceso runtime al Environment. Lee AnswerKeys ya computados.
- **Verifier**: motor matemático determinista (no LLM). Joya del sistema. Ejecuta queries del Environment para producir AnswerKeys en design-time. NO se usa en runtime de evaluación.

---

## 1. Tesis

El gap crítico de los agentes AI no es razonamiento puro, es **juicio investigativo**: qué examinar, cuándo pivotar, cómo separar evidencia específica del caso de priors del entrenamiento.

v1 construyó pipeline pero quedó bloqueado en evaluación: el compiler NL↔IR es frágil (techo ~83% en Suite 2). v1.5 **elimina el compiler** y reemplaza con `rubric + LLM judge + answer key grounded en Environment ejecutable`. El verifier matemático se mantiene como núcleo anti-hallucination, relocalizado a design-time del caso. Se abre la puerta a dominios dinámicos (ODE en v1.5; SDE en v1.6).

Justificación empírica externa: Corral (Ríos-García/Jablonka et al. 2026) — el modelo base explica 41.4% de varianza, el scaffold 1.5%. *"Scaffold doesn't fix reasoning; training does."*

---

## 2. Vocabulario canónico

| Concepto | Nombre | Rol |
|---|---|---|
| Sistema matemático subyacente | **WorldModel** | SCM o ODE en v1.5 (SDE intrínseco en v1.6). Ecuaciones, grafos, parámetros. |
| Interfaz ejecutable | **Environment** | Expone `observe`, `intervene`, `simulate` al Designer. NO al Investigator en v1.5. |
| Paper que inspira | **Seed Paper** | Input al Designer. WorldModel se inspira, no replica. |
| LLM meta-agente que diseña | **Designer** | Compuesto por 5 roles + Validator transversal. |
| Pregunta canónica con verdad | **GoldQuestion** | 3-5 por caso. AnswerKey pre-computado por Verifier. |
| Estructura de evaluación | **Rubric** | Por GoldQuestion. Criterios concretos generados desde el contenido. |
| Verdad de referencia | **AnswerKey** | Estructurada, computada en design-time. NO se recomputa en runtime. |
| Paquete que recibe el agente | **ResearchCase** | Brief + datos + contexto + tools. Sin GoldQuestions ni AnswerKeys. |
| LLM-agente que investiga | **Investigator** | Libre, con `python_exec` sobre datos. Single-turn en v1.5. |
| Afirmación en prosa | **Claim** | Output del Investigator. Sin formato impuesto. |
| LLM que compara y valida | **Evaluator** | Lee Claims y Rubrics. NO toca Environment en runtime. |
| Motor matemático determinista | **Verifier** | Ejecuta queries contra Environment para AnswerKeys. NO es LLM. |

Convención externa respetada: `Environment` se alinea con SciGym, BoxingGym, DiscoveryWorld, Corral.

---

## 3. Flujo end-to-end

```
=== FASE A — DESIGN-TIME (Designer + Verifier) ===

  Seed Paper
     │
     ▼
  Paper Digestion ──► PaperInsights (mecanismos, fenómenos, trampas)
     │
     ▼
  World Architect ──► WorldSpec ──[compile]──► Environment
     │                                           ▲
     ▼                                           │ exploratory
  Explorer ─────────► PhenomenaManifest ─────────┘ queries
     │                  (con evidencia ejecutable adjunta)
     ▼
  Question Designer ──► QuestionsBundle ─────────┐
     │                  (GoldQuestion + Rubric +  │ verifier_query
     │                   AnswerKey ya ejecutado)  ▼
     │                                       Environment
     ▼
  Case Writer ──► ResearchCase (brief + dataset + tools, sin GQs)
     │
     ▼
  Validator (transversal) ──► passed | invalida y re-itera

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

El Validator opera en loop con los productores: puede invalidar cualquier etapa y gatillar revisión. El caso no sale del Designer hasta que el Validator aprueba.

---

## 4. Designer — 5 roles + Validator

| Rol | Input | Output | Responsabilidad |
|---|---|---|---|
| **Paper Digestion** | Seed Paper | `PaperInsights` | Extrae mecanismos, fenómenos, trampas, counterintuitive priors. |
| **World Architect** | `PaperInsights` | `WorldSpec` | Diseña ecuaciones del WorldModel. SCM o ODE según el dominio. Inspirarse, no replicar. |
| **Explorer** | `WorldSpec` + Environment compilado | `PhenomenaManifest` | Encuentra fenómenos interesantes con **evidencia ejecutable** adjunta (script + número), no prosa. |
| **Question Designer** | `PhenomenaManifest` + Environment | `QuestionsBundle` | 3-5 GoldQuestions con Rubric + AnswerKey pre-computado vía Verifier. |
| **Case Writer** | `QuestionsBundle` + Seed Paper | `ResearchCase` | Brief realista. Disfraza GQs sin filtrar respuestas. |
| **Validator (transversal)** | Todos los artefactos | `ValidationReport` | Trivialidad (adversarial: ¿se responde sin datos?), leakage, internal consistency, alignment Rubric/AnswerKey. **Puede invalidar upstream y forzar re-iteración.** |

Decisión: todos los roles comparten modelo base con prompts específicos. Es más simple que agentes distintos.

---

## 5. Artefactos tipados (contratos clave)

Cada handoff requiere artefacto Pydantic, no prosa. Detalle de los schemas vive en `src/sreg/models/` cuando se implemente. Los contratos clave:

- **`PaperInsights`**: `paper_id`, `objective`, `entities`, `mechanisms`, `phenomena`, `complications`, `counterintuitive_priors`, `realism_bounds`.
- **`WorldSpec`**: `formalism: Literal["scm","ode"]`, `variables`, `relationships`, `parameters`, `metadata`.
- **`PhenomenaManifest`**: lista de `Phenomenon`, cada uno con `kind` (collider, identifiability_gap, bifurcation_proximity, etc.) y `evidence: ExecutableEvidence` (script + resultado numérico).
- **`GoldQuestion`**: `id`, `text`, `weight ∈ {0.08, 0.12, 0.16, 0.20}`, `role: required|support`, `verifier_query`, `answer_key`, `identification_hint`, `rubric`.
- **`Rubric`**: lista de `Criterion`. NO hay tags de "tipo de pregunta" en el schema (ver §6).
- **`Criterion`**: `text`, `weight ∈ {1,2,3}`, `role: core|bonus`, `anchor: AnswerKeyAnchor`, `scoring_hint`, `requires_span: bool`.
- **`AnswerKeyAnchor`**: referencia tipada a un campo del `answer_key` (`path`, `match: approx|equals|enum|mentioned`, `tolerance`).
- **`ResearchCase`**: `brief`, `context`, `datasets`, `tools`. **Sin** `QuestionsBundle` ni `AnswerKey` (frontera público/oculto, ver §10).
- **`InvestigationLog`**: `actions: list[InvestigatorAction]`, `hypotheses_log`, `final_claims`. Registrado siempre; NO evaluado en MVP.
- **`InvestigatorAction`**: `step`, `kind: Literal["python_exec","hypothesis","pivot","submit"]`, `payload`, `rationale`, `epistemic_tag: Literal["H","T","E","J","U","C"] | None`. El tag (vocabulario Corral) es telemetría no-scoring; habilita trace scoring futuro (issue #53). **`observe`, `intervene`, `simulate` NO son `kind` de v1.5** — son acciones de v2 (Sherlock).
- **`ValidationReport`**: `passed`, `invalidated_artifacts`, `issues`, `adversarial_attempts`.

Pesos discretos en GoldQuestion y Criterion son anti-ajuste-fino (evita micro-optimización arbitraria).

---

## 6. Rubric design

Cada GoldQuestion tiene una Rubric. **Los criterios concretos los genera el Question Designer desde el contenido específico de la pregunta.** No hay templates por categoría (rompería el principio "UN método para todo" en `PROJECT.md`).

**4 dimensiones universales** — son **guideline editorial** para el Question Designer al armar criterios, NO un enum del schema:

1. **Fidelidad**: ¿lo que dice corresponde a la verdad del WorldModel?
2. **Justificación**: ¿está respaldada por evidencia o razonamiento, no por tono?
3. **Calibración**: ¿maneja la incertidumbre? Incluye abstención calibrada.
4. **Especificidad**: ¿es concreta y verificable, no vaga?

Los criterios concretos materializan estas dimensiones para esa pregunta. Ejemplo: para "¿cuánto influye X en Y?" la fidelidad puede ser "estimación dentro del intervalo verdadero ± tolerancia"; para "¿qué tipo de variable es Z?" puede ser "identifica el rol estructural correcto". Las dimensiones son siempre las mismas; los criterios cambian.

**Split core vs bonus en cada Rubric**:
- **Core**: criterios obligatorios para responder bien la GQ. Aportan 70-85% del score_GQ.
- **Bonus**: caveats, calibración, robustness. Aportan 15-30%. **No compensan errores del core.**

**Fórmula**: `score_GQ = alpha × score_core + (1 - alpha) × score_bonus`, con `alpha = 0.8` por **default** (configurable). Si la calibración con humanos en pilot muestra que conviene variar, discretizar en {0.75, 0.8, 0.85}.

**Reglas invariantes**:
- **Span textual obligatorio**: cada criterion acreditado requiere span citado del reporte. Sin span → 0.
- **Nunca acreditar por terminología sola** si el span contradice el anchor.
- **Assertion entailment tolerante**: claim cuantitativo ("efecto = 0.42 ± 0.05") satisface criterio cualitativo ("identifica que es positivo") con tolerancia.
- **Alternative phrasings** dentro de cada Criterion (anti-ajuste fino al wording del Investigator).

---

## 7. Evaluator

**Decisión clave: el Evaluator NO toca el Environment en runtime.** Toda la formalización vive en design-time; el Evaluator solo lee `AnswerKey` ya computado por el Question Designer. Razones: reproducibilidad, costo en RL training (millones de episodios), frontera limpia entre quién investiga y quién evalúa.

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
      - Span textual obligatorio.
      - El anchor compara contra AnswerKey con la regla declarada (approx/equals/enum/mentioned).

  score_GQ = identification × (alpha × score_core + (1 - alpha) × score_bonus)

score_total_caso = Σ GQ.weight × score_GQ
```

**Reglas del Evaluator**:
- **No ejecuta queries arbitrarias del Environment.** Cualquier necesidad de "verificar contra el SCM" se resuelve en design-time con el Question Designer.
- **Claims espontáneas fuera de las GoldQuestions** no entran al score principal. (Future: novel-but-correct lane si Fase 0 lo justifica.)
- **Contradicciones explícitas restan**: shotgun science (20 claims contradictorias) no se premia "la que aciertó".

---

## 8. Score y reporting

El score primario que computa el Evaluator es **por GoldQuestion** (la fórmula de §7). Eso se agrega ponderado al score del caso.

Para análisis y reporting agregado (no parte del schema canónico ni del scoring), se puede derivar una **vista por dimensión de habilidad investigativa** clasificando cada GoldQuestion:

| Dimensión | Qué mide |
|---|---|
| Framing | Identificar las preguntas relevantes desde un brief abierto. |
| Identification | Reconocer relaciones causales/estructurales. |
| Estimation | Cuantificar efectos. |
| Intervention prediction | Anticipar do-operations. |
| Confounding detection | Identificar sesgos. |
| Mediation analysis | Descomponer mecanismos. |
| Epistemic calibration | Saber cuándo no concluir. |

Esta vista es **derivada** (no canónica) — útil para comparar modelos o ablations, pero no es lo que computa el Evaluator. **Process quality** (calidad del trace, motifs/breakdowns tipo Corral) NO entra en v1.5: requiere trace scoring (issue #53), feature futura.

---

## 9. Cobertura de formalismos y tipos de investigación

**Formalismos en v1.5**:
- **SCM** (causal estático): `n_samples × n_vars`. Observaciones puntuales, do-operations clásicas, mediación, identifiability.
- **ODE** (dinámica determinista): `n_paths × n_timesteps × n_vars`. Trayectorias, before/after, intervenciones temporales, panel longitudinal. Soporta `observation_noise` opcional (gaussiano, configurable) para datos con error de medición — cubre la mayoría de los casos realistas.

**Formalismo en v1.6** (post-v1.5):
- **SDE** (dinámica estocástica intrínseca): cuando el ruido es parte del sistema (difusión molecular, Ornstein-Uhlenbeck, mercados, biofísica con ruido térmico). Agrega query_kinds nuevos: `noise_response`, `time_to_event` como distribución.

**Verifier — query_kinds en v1.5** (16 total):
- 10 SCM: `ate`, `association`, `conditional_association`, `heterogeneity`, `mediation_decomposition`, `confounding_gap`, `rank_order`, `threshold_scan`, `identifiability_status`, `counterfactual_contrast`.
- 6 ODE: `equilibrium`, `trajectory_summary`, `parameter_sensitivity`, `phase_portrait_topology`, `bifurcation_threshold`, `time_to_event`.

**Tipos de investigación cubiertos**: causal, predictiva, descriptiva, system mapping, epistemológica, "best framework". Con ODE además: escalas temporales, oscilaciones, bifurcaciones, control óptimo, identificación de parámetros dinámicos.

---

## 10. Frontera público / oculto

| Artefacto | ¿Lo ve el Investigator? |
|---|---|
| `ResearchCase` (brief, context, datasets, tools) | **Sí.** |
| `WorldSpec`, `PhenomenaManifest`, `QuestionsBundle`, `AnswerKey`, `Rubric`, `ValidationReport` | **No.** |
| `AccessPolicy.public_rationale` (v2) | Sí. |
| `AccessPolicy.internal_rationale` (v2) | No. |

Garantía operativa: el constructor de prompts del Investigator **no puede** acceder a campos ocultos. Test obligatorio post-#55: `ResearchCase.model_dump()` no expone ningún campo restringido.

---

## 11. Lo que NO incluye v1.5 (no-goals concretos)

- **Multi-turno / interacción Sherlock** — Epic #64 (v2). El Investigator es single-turn en v1.5: recibe ResearchCase, hace análisis, entrega Claims, fin.
- **`observe`, `intervene`, `simulate` como acciones del Investigator** — son v2. En v1.5, el Investigator usa `python_exec` sobre el dataset que ya recibió.
- **SDE intrínseco** — v1.6.
- **Trace scoring del InvestigationLog** — issue #53. El log se registra pero no se evalúa en MVP.
- **Identifiability gate formal universal** — issue #54. Mientras no esté, regla operativa: en v1.5 no entran GoldQuestions cuyo gold correcto sea "no identificable" salvo que esté modelado como outcome válido.
- **Claims espontáneas fuera de GoldQuestions** — no entran al score principal. Future: novel-but-correct lane.
- **Generación automática de seed papers** — los papers se curan a mano al inicio.
- **Distilación del Evaluator a classifier chico** — post-MVP, para abaratar RL training.

---

## 12. Roadmap (high-level)

| Versión | Alcance | Estado |
|---|---|---|
| **v1.5** (Epic #63) | MVP estático SCM + ODE. Designer multi-formalismo, Evaluator con rubric + answer key, casos diversos por formalismo, 3 tests go/no-go. | En desarrollo. |
| **v1.6** | Agrega SDE intrínseco. | Post-v1.5. |
| **v2** (Epic #64) | Interactividad multi-turno tipo Sherlock: budget visible, AccessPolicy, primitivas observe/intervene/simulate como acciones del Investigator. | Post-v1.5. |

Detalle del orden de implementación de v1.5 (8 sub-issues con checkpoints entre piezas, anti-memorización integrada al flujo): ver body de Epic #63 y Ronda 11 en `research/notes/v1_5_debates.md`.

---

## 13. Diversidad de casos — invariante operativo

v1.5 NO entrega un caso canónico único — entrega **varios casos diversos por formalismo**, cubriendo distintos dominios, distintos tipos de trampa (collider, paradoja de Simpson, mediación, no-linealidad, identifiability, bifurcaciones), distintas dificultades. Casos famosos (ej. Birth Weight Paradox SCM, SIR ODE) son **smoke tests**, no evidencia principal.

Anti-memorización integrada al flujo:
- **Corpus abstracto isomorfo** desde post-#56 (variables `X`, `M`, `Y`; briefs neutros; AnswerKeys generadas por el Verifier). Asset permanente del repo.
- **Gate duro post-#61**: tests `answer_key_sensitivity` (mismo caso, AnswerKey alterado → score sigue al AnswerKey, no al prior del modelo) e `isomorph_invariance` (mismo caso renombrado → score parecido).
- **Re-ejecución post-#58 y post-#59**: el Designer puede reintroducir leak por wording de briefs o rubrics demasiado "teaching-to-the-test".

Regla operativa: si el judge acierta en casos famosos pero falla en suite abstracta → rojo. Si pasa la abstracta y los famosos → señal real.

---

## Apéndice — referencias

- Ejemplo canónico completo de un caso SCM: `research/examples/birth_weight_paradox.md`.
- Postmortem del compiler v1 (por qué lo matamos): `research/notes/compiler_v1_postmortem.md`.
- 11 rondas de debate de diseño v1.5: `research/notes/v1_5_debates.md`.
- Related work: `research/synthesis/related_work_corral.md`, `related_work_sandmle.md`, `related_work_scigym.md`, `related_work_sciagentgym.md`.
- Arquitectura v1 (legacy, código en `main`): `docs/archive/architecture_v1.md`.
