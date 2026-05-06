# SREG — Arquitectura
## Synthetic Research Environment Generator

> **Spec viva del sistema target (v1.5).** Sólo decisiones cerradas, componentes y contratos. Sin debates, sin trade-offs largos, sin lessons históricas.
>
> Vision y principios: `PROJECT.md` · Estado actual real: `CURRENT_STATE.md` · Trabajo pendiente: GitHub Issues · Debates históricos: `research/notes/v1_5_debates.md` · Diseño del Designer multi-agente: `research/notes/multi_explorer_redesign.md`.
>
> **Versión**: v1.5 en desarrollo activo (rama `dev`). Actualizado 2026-05-05. La arquitectura v1.x está preservada en `docs/archive/architecture_v1.md`.

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

- **Case Generation (Designer multi-agente)**: lo más pesado. Architect (multi-iter) + N Validators + Discovery Designer + Case Writer + Validator transversal. Vive acá toda la complejidad nueva de v1.5.
- **Investigator**: relativamente delgado, ~10% del esfuerzo. Reusa código de v1. Single-turn en v1.5; multi-turno en v2.
- **Evaluator**: LLM judge sin acceso runtime al Environment. Lee AnswerKeys ya computados.

**Environment (transversal)**: interfaz ejecutable del WorldModel (`observe`, `intervene`, `simulate`). Lo usan los Validators y el Discovery Designer en design-time para producir AnswerKeys vía scripts Python (`EvidenceArtifact`). El Evaluator NO lo toca en runtime.

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
| LLM meta-agente que diseña | **Designer** | Compuesto por: Architect (multi-iter) + N Validators + Discovery Designer + Case Writer + Validator transversal. |
| Fenómeno declarado por el Architect | **IntendedPhenomenon** | Lo que el Architect quiso poner en el WorldSpec. Cada uno se asigna a un Validator. |
| Voto de un Validator sobre un fenómeno | **ValidatorVote** | `vote` (passes/weak_pass/fails) + margin + fragility + delta_from_previous + evidence + failure_reason. Output crudo inmutable. |
| Fenómeno con materialización verificada | **ValidatedPhenomenon** | `IntendedPhenomenon` cuyos Validators votaron `passes`. Apunta al original vía `source_intended_id`. Input principal del Discovery Designer. |
| Evidencia ejecutable | **EvidenceArtifact** | Script Python + resultado numérico contra el Environment. Patrón canónico para producir anchors y verificar fenómenos. (Hook v1.6: `access_mode` ∈ {public_data, interventional, omniscient_latent} para que el Evaluator distinga qué evidencia es recuperable desde la interfaz pública). |
| Descubrimiento central oculto del caso | **DiscoveryTarget** | 3-5 por caso. Conclusión científica esperada (capa A flexible NL) + AnswerKey + provenance ejecutable (capa B formal). Apunta a sus orígenes vía `source_validated_ids: list[str]` (mapping N:M con ValidatedPhenomena). NO es una pregunta cerrada — es un descubrimiento que una buena investigación libre debería recuperar. Internamente el schema mantiene el nombre histórico `GoldQuestion` durante Fases 1.x; se renombrará al implementar Discovery Designer (Fase 3). Ver `PROJECT.md` §"Investigación abierta vs examen cerrado". |
| Estructura de evaluación | **Rubric** | Por DiscoveryTarget. Criterios concretos generados desde el contenido del descubrimiento. Acredita conclusiones equivalentes (paráfrasis), claims cuantitativas que implican la conclusión cualitativa, y caveats correctos. NO premia wording exacto. |
| Verdad de referencia | **AnswerKey** | Estructurada, computada en design-time vía scripts. NO se recomputa en runtime. |
| Hint para emparejar claim con descubrimiento | **claim_match_hint** (campo de DiscoveryTarget) | Reemplaza el viejo `identification_hint`. Indica al Evaluator cómo decidir si alguna claim del reporte llega a la conclusión esperada (no si "aborda el tema"). |
| Paquete que recibe el agente | **ResearchCase** | Brief + datos + contexto + tools. Sin DiscoveryTargets ni AnswerKeys. |
| LLM-agente que investiga | **Investigator** | Libre, con `python_exec` sobre datos. Single-turn en v1.5. Output: reporte científico con claims/conclusiones, no respuestas a preguntas. |
| Afirmación en prosa | **Claim** | Output del Investigator. Sin formato impuesto. Forma esperada: conclusión + evidencia + interpretación + calibración + especificidad. |
| LLM que compara y valida | **Evaluator** | Lee Claims y Rubrics. NO toca Environment en runtime. Step 1: ¿alguna claim del reporte llega a esta conclusión? Step 2: rubric graduada. |

Convención externa respetada: `Environment` se alinea con SciGym, BoxingGym, DiscoveryWorld, Corral.

---

## 3. Flujo end-to-end

```
=== FASE A — DESIGN-TIME (Designer multi-agente) ===

  Seed Paper
     │
     ▼
  Paper Digestion ──► PaperInsights:
                        ├── mecanismos (input al Architect)
                        └── cápsula narrativa saneada (input al Question
                            Designer y al Case Writer): dominio, población,
                            unidades, convenciones — SIN frases icónicas
                            ni punchlines del paper (anti-leak).
     │
     ▼
  World Architect ◄────────┐  (multi-iter, hard cap 3 vueltas)
     │                     │
     │ propone WorldSpec   │ Architect lee votos crudos (inmutables) y
     │ + intended_phenomena│ decide: promover (vote=passes) o iterar.
     ▼ [compile]           │ weak_pass NO promueve. Cambios al intended
  Environment (ejecutable) │ van versionados.
     ▲                     │
     │ scripts             │
     │ Python              │
  ┌──┴─────────────────────┴───────────────────────────────────────┐
  │ N Validators (uno por intended_phenomenon, paralelo):          │
  │   cada uno escribe scripts Python contra el Environment        │
  │   y devuelve ValidatorVote {vote, margin, fragility,           │
  │                              delta_from_previous, evidence,    │
  │                              failure_reason}                   │
  └────────────────────────┬────────────────────────────────────────┘
                           ▼
                    list[ValidatedPhenomenon] (cuando todos pass)
                           │
                           ▼
                    Discovery Designer ──► DiscoveryBundle (oculto)
                       consume list[ValidatedPhenomenon] (mapping N:M, no 1:1).
                       Cada DiscoveryTarget tiene capa A (conclusión NL flexible)
                       + capa B (anchors formales vía EvidenceArtifact) +
                       source_validated_ids para auditar la procedencia.
                       NO consulta el paper crudo (anti-leak).
                           │
                           ▼
                    Case Writer ──► ResearchCase (brief + datasets + tools)
                    **CIEGO al DiscoveryBundle.** Solo recibe:
                    - WorldSpec (público) para conocer las variables visibles.
                    - PaperInsights.narrative_capsule (saneada).
                    - Lista de DiscoveryTarget.kind a alto nivel (taxonomía
                      descriptiva, no los textos).
                    Esto rompe la frontera anterior donde el Case Writer veía
                    el bundle entero — fuente principal de leak.
                           │
                           ▼
                    Validator transversal (ÚNICO ÁRBITRO)
                    10 checks: cobertura, provenance, leak, trivialness,
                    rubric coherence, answerability pública, modality match,
                    stability AK, bundle redundancy, salience threshold.
                    decide: passed | invalida con target_to_reiterate
                            ('world' / 'designer' / 'case'). Max 2 vueltas.

=== FASE B — RUNTIME (Investigator) ===

  ResearchCase
     │
     ▼
  Investigator (LLM, python_exec sobre dataset)
     │   ├─► InvestigationLog (registrado, NO evaluado en MVP)
     │   └─► extra_claims (registrado, NO scoreado en v1.5; hook v1.6+)
     ▼
  Claims (prosa libre)

=== FASE C — RUNTIME (Evaluator) — NO toca Environment ===

  Claims + DiscoveryBundle (con AnswerKey persistido) ──► Evaluator
                                                              │
                                                              ▼
                                                          score por caso
```

---

## 4. Designer multi-agente

| Rol | Cantidad | Input | Output | Responsabilidad |
|---|---|---|---|---|
| **Paper Digestion** | 1 | Seed Paper | `PaperInsights` (mecanismos + cápsula narrativa saneada) | Dos artefactos: mecanismos (para Architect) y cápsula narrativa saneada (para Discovery Designer y Case Writer, anti-leak: SIN frases icónicas del paper). |
| **World Architect** | 1 | `PaperInsights` (mecanismos) | `WorldSpec` + `intended_phenomena` + (luego) `list[ValidatedPhenomenon]` | Multi-iter (hard cap 3). Diseña WorldSpec, lanza Validators, lee votos crudos, promueve solo `vote=passes`, itera con cambios versionados. |
| **Validator** | N (= len(intended_phenomena)) paralelo | `WorldSpec` + Environment + 1 `IntendedPhenomenon` | `ValidatorVote` | Escribe scripts libres contra el Environment. Devuelve vote + margin + fragility + delta_from_previous + evidence + failure_reason. Verify first, no inventa preguntas. |
| **Discovery Designer** | 1 | `list[ValidatedPhenomenon]` + cápsula narrativa | `DiscoveryBundle` | Consume el bundle COMPLETO (mapping N:M, no 1:1). Cada DiscoveryTarget es un descubrimiento esperado en capa A (NL flexible) + capa B (anchors formales). Numeric reusado del EvidenceArtifact, provenance re-ejecutable, `source_validated_ids` para auditar. NO consulta el paper crudo. (Internamente el schema todavía se llama `GoldQuestion`/`QuestionsBundle` durante Fases 1.x; renombre va con la implementación de esta etapa.) |
| **Case Writer** | 1 | `WorldSpec` (público) + `narrative_capsule` saneada + lista de `DiscoveryTarget.kind` (taxonomía descriptiva, sin textos) | `ResearchCase` | Brief abierto que **NO referencia los textos de los DiscoveryTargets** — el agente debe descubrir, no parafrasear. Datasets visibles (sin latentes), tools. **El Case Writer es ciego al DiscoveryBundle**: si recibiera los textos, el brief heredaría wording y se rompería la frontera anti-leak. |
| **Validator (transversal)** | 1 | TODO | `ValidationReport` | ÚNICO ÁRBITRO. 10 checks (ver §3). Invalida con `target_to_reiterate` ('world' / 'designer' / 'case'). Max 2 vueltas. |

Decisiones operativas:

- **N Validators emergente, no fijo**: si el Architect pone 2 fenómenos, manda 2 Validators; si pone 5, 5. NO hardcodear "siempre 3" — eso huele a otro catálogo cerrado disimulado. Rango razonable MVP: 2-5.
- **Architect agrega votos él mismo**: NO hay Aggregator separado. Disciplina formal: votos crudos inmutables, `weak_pass` NO promueve a `ValidatedPhenomenon`, cambios al `intended_phenomenon` versionados en log.
- **Validator output enriquecido**: además del vote, cada uno devuelve `margin` (claridad cuantitativa), `fragility` (sensibilidad a coefs), `delta_from_previous` (qué cambió iter-a-iter). Sin esto el Architect hace hill-climbing ciego.
- **Verify first, propose later**: si un Validator no puede confirmar el `intended_phenomenon` que le tocó, devuelve `vote=fails` con `failure_reason`. NO inventa preguntas alternativas. Esto evita ocultar bugs del Architect.
- **Discovery Designer NO 1:1**: consume todo el bundle de `ValidatedPhenomenon` y produce el `DiscoveryBundle` libremente. Un DiscoveryTarget puede combinar fenómenos; un fenómeno puede contribuir a varios DiscoveryTargets. La auditoría se mantiene vía `source_validated_ids: list[str]`.
- **Discovery, no examen**: cada DiscoveryTarget es un descubrimiento esperado (conclusión científica) con anchors formales — NO una pregunta que el agente deba responder. Ver `PROJECT.md` §"Investigación abierta vs examen cerrado" para las 4 protecciones contra el regreso al examen cerrado.
- **Case Writer ciego al DiscoveryBundle**: rompe la frontera del flujo anterior donde el Case Writer veía los textos de los targets. Esto es necesario para que el brief sea abierto y el agente investigue en lugar de parafrasear.
- **Anti-leak con cápsula narrativa**: el paper crudo no llega al Discovery Designer ni al Case Writer. Solo dominio, población, unidades, convenciones, "estilo de investigación natural" — sin nombres canónicos del paper.
- **Validator con `target_to_reiterate`**: cuando invalida, declara qué etapa rehacer (no solo "no pasa"). El loop es concreto.

---

## 5. Artefactos tipados (contratos clave)

Cada handoff requiere artefacto Pydantic, no prosa. Los schemas viven en `src/sreg/v1_5/contracts/`. Los contratos clave:

- **`PaperInsights`**: `paper_id`, `objective`, `entities`, `mechanisms`, `phenomena`, `complications`, `counterintuitive_priors`, `realism_bounds`, `narrative_capsule` (cápsula saneada para Discovery Designer y Case Writer: dominio, población, unidades, convenciones, "estilo de investigación natural" — SIN frases icónicas del paper). El campo del estilo se renombrará de `natural_question_style` a `natural_investigation_style` cuando se implemente Fase 3, alineado con el cambio filosófico GoldQuestion → DiscoveryTarget.
- **`WorldSpec`**: `formalism: Literal["scm","ode"]`, `variables`, `relationships`, `parameters`, `metadata`, `intended_phenomena: list[IntendedPhenomenon]`. Validator cruzado: `observation_noise` solo en ODE y `>= 0`.
- **`IntendedPhenomenon`**: `id`, `kind: str` (libre, ej. "collider", "mediation"), `description`, `relevant_variables`. Vive a nivel mecanismo, NO a nivel pregunta.
- **`EvidenceArtifact`**: `script: str` (Python ejecutable contra Environment), `numerical_result: dict`, `tag: str | None` (descriptivo, no normativo). **Hook v1.6**: campo `access_mode: Literal["public_data", "interventional", "omniscient_latent"]` para que el Validator transversal verifique que un anchor usado por un `DiscoveryTarget` es **discoverable** desde la interfaz pública del caso (el Investigator no debería tener que recuperar valores de variables latentes ni resultados de intervenciones que él no puede ejecutar).
- **`Phenomenon`**: `kind: str` (string libre, no enum cerrado), `description`, `evidence: EvidenceArtifact`, `tags: list[str]`.
- **`PhenomenaManifest`**: lista de `Phenomenon`, `world_id`, `interesting_score`.
- **`ValidatorVote`**: `validator_id`, `target_intended_id`, `iteration`, `vote: Literal["passes","weak_pass","fails"]`, `margin: float`, `fragility: float`, `delta_from_previous: dict | None`, `evidence: list[EvidenceArtifact]` (mínimo 1), `failure_reason: str | None`. Validator cruzado: `failure_reason` obligatorio si `vote != passes`.
- **`ValidatedPhenomenon`**: `id`, `source_intended_id`, `kind`, `description`, `relevant_variables`, `validator_votes: list[ValidatorVote]` (todos `vote=passes`), `margin`, `fragility`, `evidence: list[EvidenceArtifact]` (mínimo 1).
- **`DiscoveryTarget`** (final, internamente todavía `GoldQuestion` durante Fases 1.x): `id`, `text` (capa A: conclusión científica esperada en NL flexible — NO una pregunta), `weight ∈ {0.08, 0.12, 0.16, 0.20}`, `role: required|support`, `kind: str` (taxonomía descriptiva del descubrimiento, no operativa: `causal_mechanism`, `misleading_association`, `mediation`, `effect_heterogeneity`, `system_mapping`, `epistemic_limit`, `dynamic_regime`, `intervention_recommendation`, etc.), `answer_key` (capa B: anchors formales), `answer_key_provenance: list[EvidenceArtifact]` (mínimo 1), `claim_match_hint` (reemplaza `identification_hint`: cómo decidir si alguna claim del reporte llega a la conclusión), `source_validated_ids: list[str]` (qué `ValidatedPhenomenon` respaldan este descubrimiento, mapping N:M auditeable), `rubric`. **Capability-as-evidence**: si el descubrimiento involucra un modelo predictivo o una optimización, el target solo se admite con `role="support"` y peso capado, no como `required`. v1.5 score primario es knowledge, no capability. |
- **`Rubric`**: lista de `Criterion` (`min_length=1`). Debe tener al menos uno con `role="core"`.
- **`Criterion`**: `text`, `weight ∈ {1,2,3}`, `role: core|bonus`, `anchor: AnswerKeyAnchor`, `scoring_hint`, `requires_span: bool`.
- **`AnswerKeyAnchor`**: `path`, `match: approx|equals|enum|mentioned`, `tolerance`, `value`. Validator cruzado por modo de match.
- **`ResearchCase`**: `case_id`, `brief`, `context`, `datasets`, `tools`. **Sin** DiscoveryTargets, AnswerKeys, IntendedPhenomena, ni textos del DiscoveryBundle (frontera público/oculto, ver §10). El brief se redacta sin referenciar ningún DiscoveryTarget.text.
- **`InvestigationLog`**: `actions`, `hypotheses_log`, `final_claims`, `extra_claims: list[Claim]` (claims fuera de los DiscoveryTargets; registrado en v1.5, NO scoreado; hook reservado para v1.6+ open scoring — claims correctos no anticipados podrían sumar bonus). Registrado siempre.
- **`InvestigatorAction`**: `step`, `kind: Literal["python_exec","hypothesis","pivot","submit"]`, `payload`, `rationale`, `epistemic_tag: Literal["H","T","E","J","U","C"] | None`. El tag (Corral) es telemetría no-scoring (#53). `observe`, `intervene`, `simulate` NO son `kind` de v1.5 — son v2.
- **`ValidationReport`**: `passed`, `invalidated_artifacts`, `issues`, `adversarial_attempts`, `target_to_reiterate: Literal["world","designer","case"] | None`. Validator cruzado: si `passed=True` el target debe ser `None`; si `passed=False` el target es obligatorio.

Pesos discretos en `DiscoveryTarget` y `Criterion` son anti-ajuste-fino (evita micro-optimización arbitraria).

---

## 6. Rubric design

Cada DiscoveryTarget tiene una Rubric. **Los criterios concretos los genera el Discovery Designer desde el contenido específico del descubrimiento esperado** (no desde un template categorizado por kind). El `kind` del DiscoveryTarget es taxonomía descriptiva — NO debe disparar templates de rubric ni "scoring profiles" por tipo, porque eso reintroduciría el catálogo cerrado que ya rechazamos.

La Rubric evalúa si la **claim del agente coincide con la conclusión esperada del descubrimiento**, no si responde una pregunta. Acredita:

- Conclusiones equivalentes (paráfrasis con mismo contenido).
- Claims cuantitativas que implican correctamente la conclusión cualitativa esperada (ej. "ATE = +0.3 (+/- 0.05)" satisface "el efecto es positivo y de magnitud moderada").
- Caveats correctos (calibración de incertidumbre, mención de limitaciones epistémicas).

NO premia: terminología técnica sin conclusión, wording exacto.

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

Pipeline: dos pasos por DiscoveryTarget.

```
Para cada DiscoveryTarget del caso:

  PASO 1 — DISCOVERY MATCH (binary)
    Input: reporte completo + claims explícitas + DiscoveryTarget.claim_match_hint
    Output: bool "¿alguna claim del reporte llega a la conclusión esperada?"
    Cambio respecto a v1: ya NO es "¿aborda este tema?" — ahora exige
    que el reporte HAYA LLEGADO al descubrimiento. Una claim vaga del
    tipo "el efecto fue analizado" NO satisface el match.
    Si no → score_DT = 0, siguiente DiscoveryTarget.

  PASO 2 — COMPLETION (graduada, sólo si match)
    Para cada Criterion de la Rubric:
      Input: reporte + Criterion.scoring_hint + Criterion.anchor + AnswerKey (ya escrito)
      Output: {cumplido: bool, span: str, razón: str}

  score_GQ = identification × (alpha × score_core + (1 - alpha) × score_bonus)

score_total_caso = Σ GQ.weight × score_GQ
```

**Reglas del Evaluator**:
- **No ejecuta queries arbitrarias del Environment.** Si necesita verificar contra el SCM, eso lo hizo el Designer en design-time vía `EvidenceArtifact`.
- **Claims espontáneas fuera de los DiscoveryTargets**: en v1.5 se registran en `InvestigationLog.extra_claims` pero NO entran al score principal. Hook reservado para v1.6+ (open scoring): bonus si son verdaderos contra el `WorldSpec` y relevantes al brief — útil para premiar descubrimientos no anticipados por el Architect.
- **Contradicciones explícitas restan**: shotgun science (20 claims contradictorias) no se premia "la que aciertó".

---

## 8. Score y reporting

El score primario que computa el Evaluator es **por DiscoveryTarget**. Eso se agrega ponderado al score del caso.

Para análisis y reporting agregado (no parte del schema canónico ni del scoring), se puede derivar una **vista por dimensión de habilidad investigativa** clasificando cada DiscoveryTarget (framing, identification, estimation, intervention prediction, confounding detection, mediation analysis, epistemic calibration). Esta vista es **derivada**, no canónica. **Process quality** (calidad del trace, motifs Corral) NO entra en v1.5 (issue #53).

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
| `PaperInsights.narrative_capsule` (cápsula saneada, opcional incluir en `context`) | **Sí.** |
| `WorldSpec`, `IntendedPhenomenon`, `ValidatorVote`, `ValidatedPhenomenon`, `PhenomenaManifest`, `DiscoveryBundle`, `DiscoveryTarget` (especialmente `text`), `AnswerKey`, `EvidenceArtifact`, `Rubric`, `ValidationReport`, `PaperInsights` (resto) | **No.** |
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
- **Open scoring de claims fuera de DiscoveryTargets** — registrados en `InvestigationLog.extra_claims` pero NO scoreados en v1.5. Hook reservado para v1.6+.
- **Capability scoring** (predictors con métrica programática, optimización de policies, controllers) — **explícitamente fuera de v1.5**. v1.5 evalúa knowledge contributions (claims/conclusiones científicas). Capability-as-evidence sí permitido como `role="support"` con peso capado, no como `required`. Ver `PROJECT.md` §"Knowledge vs Capability".
- **Wildcard challenger en el Designer** — diferido a v1.6 si pilot humano detecta convergencia a 2-3 recetas. Hoy el Designer corre con N Validators = N intended_phenomena, sin Validator libre.
- **Novelty corpus-level** — chequeo entre casos del corpus (no por caso). v1.6.
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

La diversidad principal viene de la **variedad de seed papers** y de los `intended_phenomena` que cada Architect propone. La forma del bundle (cuántos DiscoveryTargets, cómo se combinan los fenómenos) la decide el Discovery Designer caso por caso. NO hay diversidad emergente "barata" del Designer — un Architect con poca imaginación va a producir casos parecidos. Mitigación: pilot humano con dietas variadas de papers.

Anti-memorización integrada al flujo:
- **Corpus abstracto isomorfo**: variables `X`, `M`, `Y`; briefs neutros; AnswerKeys generadas por scripts ejecutables. Asset permanente del repo.
- **Gate duro post-Evaluator**: tests `answer_key_sensitivity` (mismo caso, AnswerKey alterado → score sigue al AnswerKey, no al prior del modelo) e `isomorph_invariance` (mismo caso renombrado → score parecido).
- **Cápsula narrativa saneada**: el paper crudo no llega al Discovery Designer ni al Case Writer. Solo el dominio + convenciones; sin frases icónicas que faciliten memorización.
- **Re-ejecución post-Validator transversal**: el Designer puede reintroducir leak por wording de briefs o rubrics demasiado "teaching-to-the-test". El Validator transversal corre los 10 checks (incluyendo `leak`, `bundle redundancy`, `salience threshold`).

Regla operativa: si el judge acierta en casos famosos pero falla en suite abstracta → rojo. Si pasa la abstracta y los famosos → señal real.

---

## Apéndice — referencias

- Re-diseño multi-agente del Designer (canon): `research/notes/multi_explorer_redesign.md`.
- Ejemplo canónico completo de un caso SCM: `research/examples/birth_weight_paradox.md`.
- Postmortem del compiler v1 (por qué lo matamos): `research/notes/compiler_v1_postmortem.md`.
- 11+ rondas de debate de diseño v1.5: `research/notes/v1_5_debates.md`.
- Related work: `research/synthesis/related_work_corral.md`, `related_work_sandmle.md`, `related_work_scigym.md`, `related_work_sciagentgym.md`.
- Arquitectura v1 (legacy, código en `main`): `docs/archive/architecture_v1.md`.
