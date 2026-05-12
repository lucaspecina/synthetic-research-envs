# Diseño del Designer multi-agente (v1.5)

> **Doc canónico** del Designer v1.5 después de tres rondas de simplificación.
> Estado: **diseño cerrado**, listo para aplicar a contratos y `ARCHITECTURE.md`.
>
> El nombre del archivo (`multi_explorer_redesign.md`) es histórico — viene de
> la primera versión multi-agente que mataba el catálogo cerrado de
> `query_kinds`. El diseño actual ya no tiene "Explorers" como rol separado.
>
> Validado con Codex en 3 consultas dedicadas:
> - Ronda 12 (2026-05-04): muerte del catálogo cerrado, multi-agent inicial.
> - Ronda 13 (2026-05-05) parte 1: Validators con feedback loop, recorte del Selector.
> - Ronda 13 (2026-05-05) parte 2: walkthrough Birth Weight Paradox + recorte final.
>
> Estado del repo (rama `dev`): contratos #55 mergeados; `proposal.py` (con
> `QuestionProposal`/`SelectionReport`) será borrado como parte de este
> diseño; `verifier/` ya fue borrado en ronda 12.

---

## 1. Por qué llegamos a este diseño

El camino hasta acá tuvo tres recortes encadenados.

### 1.1 Recorte 1: muerte del catálogo cerrado de `query_kinds` (ronda 12)

El primer diseño v1.5 tenía un `Verifier` con dispatch a 16 operaciones canónicas (10 SCM + 6 ODE). Cada `GoldQuestion` declaraba un `verifier_query` con un `query_kind` del catálogo.

Detectado por el usuario: mismo tipo de trampa que el `AtomicSpec` v1 — sesga al Question Designer a inventar siempre las mismas preguntas. Eco arquitectónico del compiler que ya tocó techo.

**Decisión**: matar el catálogo. Los `AnswerKey` se producen con scripts Python ejecutables (`EvidenceArtifact`). Sin enum cerrado.

### 1.2 Recorte 2: Validators con feedback loop, sin Explorers (ronda 13.1)

El segundo diseño tenía N Explorer/Designers en paralelo — cada uno con un foco distinto, multi-turn, escribiendo scripts contra el Environment, proponiendo `QuestionProposal`s. Un Selector advisory rankeaba/filtraba/mergeaba.

Detectado por el usuario: los Explorer/Designers no exploraban de verdad. El Architect ya cocina el `WorldSpec` con intención (basado en `PaperInsights`), entonces los Explorers solo verificaban hipótesis pre-cocinadas. Doble agente para una sola función.

**Decisión**: reemplazar Explorer/Designers por **Validators** que verifican `intended_phenomena` específicos del Architect, con feedback loop cerrado al Architect mismo. El Architect itera el `WorldSpec` hasta que los fenómenos se materializan.

### 1.3 Recorte 3: Architect agrega votos, sin Selector, sin wildcard (ronda 13.2)

El tercer recorte vino del walkthrough con el caso Birth Weight Paradox (`research/examples/birth_weight_paradox.md`). El usuario propuso eliminar el Selector y el wildcard challenger.

**Decisión**:
- **Architect agrega votos directamente**: lee `failure_reasons` de los Validators y decide si itera o pasa. Ya no hay Aggregator separado.
- **Sin wildcard MVP**: arrancamos con `N validators = N intended_phenomena`. Si después los casos quedan monótonos, lo agregamos.
- **Sin `QuestionProposal` / `SelectionReport`**: contratos no necesarios. Aparece `ValidatedPhenomenon` como contrato nuevo.
- **Question Designer no consulta el paper**: usa `description + EvidenceArtifact + WorldSpec` + cápsula narrativa saneada (anti-leak).

Codex (consulta dedicada post-recorte) validó la dirección pero advirtió que **el recorte quitó agentes pero no funciones**. Las funciones de `bundle shaping`, `interface answerability` y `robust numeric truth` hay que reubicarlas explícitamente. La sección §3 de este doc lo hace.

---

## 2. Flujo final

```
Paper Digestion → PaperInsights
                  ├── mecanismos (input al Architect)
                  └── cápsula narrativa saneada (input al Question Designer
                      y al Case Writer): dominio, población, unidades,
                      convenciones, "estilo de pregunta natural", SIN
                      frases icónicas ni punchlines del paper.
    ↓
Architect (multi-iter, hard cap 3 vueltas)
    1. propone draft WorldSpec + intended_phenomena[N]
       (mecanismos a nivel "puse collider X-U sobre Z", NO preguntas)
    2. lanza N Validators (uno por intended_phenomenon, NO hardcode 3)
       cada uno escribe scripts Python libres contra el Environment
       y devuelve: ValidatorVote {
                     vote: passes | weak_pass | fails,
                     margin: float,
                     fragility: float,
                     delta_from_previous: dict,
                     evidence: list[EvidenceArtifact],
                     failure_reason: str | None
                   }
    3. el Architect lee votos crudos (inmutables)
    4. promoción: solo vote=passes promueve a ValidatedPhenomenon
       weak_pass NO promueve silenciosamente
    5. si quedan fenómenos sin promover y hay vueltas disponibles,
       el Architect ajusta WorldSpec o intended_phenomena (con versionado
       en log para que no achique la tesis sin dejar rastro) y vuelve a 1
    6. si tras 3 vueltas no convergió, descarta seed paper o
       reduce intended_phenomena (con log explícito)
    ↓ list[ValidatedPhenomenon]
Question Designer
    consume el LIST COMPLETO de ValidatedPhenomena, produce QuestionsBundle
    libremente. NO 1:1 — una GQ puede combinar varios fenómenos, un
    fenómeno puede generar varias GQs.
    redacción: usa ValidatedPhenomenon.description + EvidenceArtifact +
               cápsula narrativa saneada. NO el paper crudo (anti-leak).
    AnswerKey: numeric reusado del EvidenceArtifact (NO inventado),
               con tolerance/range basado en la stability medida.
    answer_key_provenance: list[EvidenceArtifact] re-ejecutables.
    ↓
Case Writer → ResearchCase
    brief NL anti-leak (sin variables latentes, sin términos técnicos
    que filtren), dataset visible (sin columnas latentes), tools
    (python_exec + numpy + pandas + statsmodels).
    ↓
Validator transversal (único árbitro con autoridad de invalidar)
    checks (10):
      1. cobertura: cada ValidatedPhenomenon core está cubierto por
         al menos una GQ.
      2. provenance: toda GQ tiene >=1 EvidenceArtifact.
      3. leak en brief: regex + LLM judge buscan filtración de
         answer keys, variables latentes, términos delatadores.
      4. trivialness: lazy investigator simulado scorea < 0.3.
      5. rubric coherence: respuesta canónica scorea > 0.85.
      6. answerability pública: cada GQ es respondible con dataset
         visible + tools, no solo "verdadera en el WorldSpec".
      7. modality match de provenance: si EvidenceArtifact usó
         latentes / intervenciones, no respalda pregunta empírica
         pura — salvo que la GQ pida explícitamente "no identificable".
      8. stability del answer key: numeric viene con tolerance o CI
         medido empíricamente, no número crudo de una corrida.
      9. bundle redundancy: no hay GQs casi idénticas con wording
         distinto (chequeo de overlap semántico).
      10. salience threshold: cada fenómeno detrás de una GQ tiene
          tamaño de efecto suficiente para merecer pregunta.
    output: ValidationReport(
              passed: bool,
              target_to_reiterate: Literal["world", "designer", "case"] | None
            )
    si invalida: re-itera la etapa indicada (max 2 vueltas totales).
```

---

## 3. Decisiones clave

### 3.1 Architect con disciplina formal

El Architect agrega los votos él mismo (sin Aggregator separado), pero con tres reglas duras:

- **Votos crudos inmutables**: el Architect lee, no edita ni reescribe los `ValidatorVote`s.
- **Promoción explícita**: solo `vote="passes"` graduates a `ValidatedPhenomenon`. `weak_pass` NO. Esto evita que el Architect "redondee hacia arriba" ambigüedades.
- **Versionado del `intended_phenomenon`**: si el Architect cambia el `description` o las `relevant_variables` entre iteraciones, queda registrado. Eso impide que achique la tesis silenciosamente para hacerla más fácil de validar.

Hard cap = 3 iteraciones. Si tras 3 vueltas hay fenómenos sin promover, el Architect decide entre:
- bajar la lista de `intended_phenomena` (con log explícito de qué se descarta),
- declarar el seed paper inviable y descartarlo.

### 3.2 Validator output enriquecido

Cada `ValidatorVote` no es solo `pass/fail`. Devuelve:

- `vote`: `passes | weak_pass | fails`.
- `margin`: claridad cuantitativa del resultado. Ej: para una paradoja con `diff_lbw=-0.045 ± 0.01`, margin alto. Para `=-0.005 ± 0.01`, margin nulo.
- `fragility`: cuánto se mueve el fenómeno si se perturba un coef. Esto le da al Architect señal de sensibilidad para iterar inteligentemente, no a ciegas.
- `delta_from_previous`: qué cambió entre esta iteración y la anterior (para detectar oscilación).
- `evidence`: `list[EvidenceArtifact]` (script + numerical_result).
- `failure_reason`: texto explicando el problema si `vote != passes`.

Sin `margin/fragility`, el Architect hace hill-climbing ciego: cambia coef, los validators dicen "ok", pero no sabemos si está sólido o al borde.

### 3.3 N Validators = N intended_phenomena (emergente, no fijo)

El número de Validators es función del WorldSpec, no constante. Si el Architect pone 2 fenómenos, manda 2 Validators. Si pone 5, 5. NO hardcodear "siempre 3" — eso huele a otro catálogo cerrado disimulado.

Para MVP: rango razonable 2-5. Más de 5 fenómenos en un solo caso huele a sobrecarga del Architect; bajamos.

### 3.4 Question Designer consume el bundle completo, no 1:1

El Question Designer recibe `list[ValidatedPhenomenon]` entera y produce `QuestionsBundle` libremente. Mappings posibles:

- **N:1**: una GQ combina varios fenómenos. Ej: en Birth Weight Paradox, GQ4 ("¿qué tipo de variable es LBW?") combina paradoja al estratificar (ip2) + no identifiability del efecto directo (ip3).
- **1:N**: un fenómeno genera varias GQs con ángulos distintos.
- **1:1**: el caso simple.

Hardcodear `1 fenómeno → 1 pregunta` haría el sistema rígido y mataría diversidad real.

### 3.5 Anti-leak: cápsula narrativa saneada

El paper crudo NO se le pasa al Question Designer (riesgo: pregunta calcada del paper, frases icónicas como "the birth weight paradox", el Investigator memoriza la respuesta).

En cambio, Paper Digestion produce **dos artefactos** desde el seed paper:

1. **Mecanismos** (para el Architect): "collider entre `Smoking` y un confounder no observado de mortalidad", "estratificar por `LBW` invierte signo".
2. **Cápsula narrativa saneada** (para el Question Designer y el Case Writer):
   - dominio: epidemiología perinatal
   - población: ~1500 nacimientos en cohorte observacional
   - unidades: peso al nacer en gramos, mortalidad binaria primer mes
   - convenciones de medición: LBW threshold 2500g
   - "estilo de pregunta natural en este dominio": estimaciones de efecto causal con CI, análisis estratificados, discusión de identifiability
   - **PROHIBIDO**: nombres canónicos del paper ("paradoja de X"), frases icónicas, conclusiones del paper, recomendaciones de salud pública.

Esto es anti-leak parcial. El leak fuerte (autoría del caso) no se elimina; solo el wording.

### 3.6 Validator transversal con 10 checks

Ver §2 para lista completa. Los críticos que vinieron de Codex y NO estaban en versiones anteriores:

- **answerability pública** (#6): que la GQ sea respondible desde la **interfaz pública** (dataset + tools), no solo "verdadera en el WorldSpec". Si el WorldSpec tiene `HiddenU` y la GQ pide "qué es `HiddenU`", el Investigator no puede responder porque no lo ve. Hay que reformular o descartar.
- **modality match de provenance** (#7): si el `EvidenceArtifact` usó `env.intervene(do=...)` o leyó variables latentes, NO puede respaldar una GQ que el Investigator debe responder empíricamente — salvo que la GQ pida explícitamente "no identificable" / "imposible desde estos datos".
- **stability del answer key** (#8): el `numeric` no puede ser número crudo de una corrida del Validator. Tiene que tener `tolerance` o `ci` medido empíricamente (re-correr con seeds distintos, computar variance). Si no, convertimos ruido de una corrida en gold.
- **bundle redundancy** (#9): sin Selector, alguien tiene que chequear que no haya 3 preguntas casi iguales con wording distinto. Va al Validator transversal.
- **salience threshold** (#10): un fenómeno puede pasar (`vote=passes` + `margin alto`) pero ser marginal o periférico al caso. No todo fenómeno verificado merece ser GQ.

### 3.7 Verify first, propose later (mantiene del recorte 1)

Esta regla sobrevive a los recortes: si un Validator no puede confirmar el `intended_phenomenon` que le tocó, NO inventa preguntas alternativas creativas. Reporta el problema y termina. Eso evita ocultar bugs del Architect bajo preguntas válidas pero desconectadas de la intención original.

En el flujo final, esto se materializa en: el Validator devuelve `vote=fails` con `failure_reason`; el Architect itera. No hay "pregunta de consolación".

---

## 4. Cambios concretos en contratos Pydantic

### Crear

**`ValidatedPhenomenon`** (en `contracts/validated_phenomenon.py`):

```python
class ValidatedPhenomenon(BaseModel):
    """Fenómeno cuya materialización en el WorldSpec fue verificada por
    Validators con vote=passes."""
    id: str
    source_intended_id: str  # apunta al IntendedPhenomenon original
    kind: str  # tag libre
    description: str
    relevant_variables: list[str]
    validator_votes: list[ValidatorVote]  # mínimo 1, todos passes
    margin: float  # del vote (si N validators del mismo, agregado)
    fragility: float
    evidence: list[EvidenceArtifact]  # mínimo 1
```

**`ValidatorVote`** (en mismo archivo):

```python
class ValidatorVote(BaseModel):
    """Output de un Validator sobre un IntendedPhenomenon."""
    validator_id: str
    target_intended_id: str
    iteration: int  # qué vuelta del Architect
    vote: Literal["passes", "weak_pass", "fails"]
    margin: float
    fragility: float
    delta_from_previous: dict[str, Any] | None  # null en iter 1
    evidence: list[EvidenceArtifact]  # mínimo 1
    failure_reason: str | None  # obligatorio si vote != passes
```

### Modificar

**`ValidationReport`**: cambiar `target_to_reiterate: Literal["world", "explorers", "case"]` a `Literal["world", "designer", "case"]` (sin "explorers" — ya no existen como rol).

**`InvestigationLog`**: agregar `extra_claims: list[Claim] = Field(default_factory=list)`. Hook reservado para open scoring del Solver. En v1.5 se registra pero NO se puntúa. En v1.6+ entra al score con bonus.

### Borrar

- **`QuestionProposal`** (en `contracts/proposal.py`): no se usa más.
- **`SelectionReport`** (en `contracts/proposal.py`): no se usa más.
- **`contracts/proposal.py`** completo: borrarlo (queda vacío).
- Tests asociados.

### Mantener sin cambios

- `PaperInsights`
- `WorldSpec` con `intended_phenomena: list[IntendedPhenomenon]`
- `IntendedPhenomenon`
- `EvidenceArtifact`
- `Phenomenon`, `PhenomenaManifest`
- `Rubric`, `Criterion`, `AnswerKey`, `AnswerKeyAnchor`, `GoldQuestion`, `QuestionsBundle`
- `ResearchCase`, `Dataset`, `ToolSpec`
- `InvestigatorAction`, `Claim`, `HypothesisEntry` (`InvestigationLog` solo agrega `extra_claims`)
- `ValidationIssue`, `AdversarialAttempt`

---

## 5. Cambios en código

### Borrar

- `src/sreg/v1_5/contracts/proposal.py` (completo).
- Tests asociados a `QuestionProposal` / `SelectionReport` en `tests/v1_5/contracts/`.
- Exports correspondientes en `src/sreg/v1_5/contracts/__init__.py`.

### Crear

- `src/sreg/v1_5/contracts/validated_phenomenon.py` con `ValidatedPhenomenon` + `ValidatorVote`.
- Tests para los validadores cruzados de los nuevos contratos.

### Modificar

- `src/sreg/v1_5/contracts/validation.py`: ajustar `ValidationReport.target_to_reiterate`.
- `src/sreg/v1_5/contracts/investigation.py`: agregar `extra_claims` a `InvestigationLog`.
- `src/sreg/v1_5/contracts/__init__.py`: actualizar exports.

### Mantener sin cambios

- `src/sreg/v1_5/environment/` (Protocols, SCMEnvironmentAdapter — sirven igual).
- Tests de `environment/`.
- Resto de tests de `contracts/`.

---

## 6. Cambios en docs

- **`ARCHITECTURE.md`**: sacar refs a Selector, Explorer/Designer, wildcard, `QuestionProposal`, `SelectionReport`. Reflejar flujo final con Architect multi-iter + Validators + Question Designer + Case Writer + Validator transversal. Actualizar §2 vocabulario, §3 flujo, §4 Designer multi-agente, §5 contratos, §10 frontera, §11 no-goals.
- **`research/notes/v1_5_debates.md`**: agregar Ronda 13 con el camino de los recortes 2 y 3 + consultas a Codex.
- **Body de issue #56** (Environment + helpers): ya estaba bien post-ronda 12 (Environment + helpers mínimos sin dispatch). Ajustes menores si los hay.
- **Body de issue #58** (Designer): re-titular "Designer multi-agente" → reflejar componentes finales (Architect, Validators, Question Designer, Case Writer, Validator transversal — sin Selector, sin Explorer/Designer).

---

## 7. Hooks reservados para v1.6+

Estos NO se implementan en v1.5, pero se dejan los pegamentos para no reescribir contratos después:

- **Open scoring del Solver**: `InvestigationLog.extra_claims` registra claims fuera de las GoldQuestions. En v1.5 NO paga; el Evaluator los ignora para el score. En v1.6 entran con bonus si son verdaderos (verificable contra el `WorldSpec`) y relevantes (LLM judge). Justificación: el proyecto se inspira en Open Investigation (`research/synthesis/open_investigation_vision.md`) — el Solver debería poder reportar más de lo pedido, sin penalización si no lo hace y con crédito si lo hace bien.
- **Wildcard challenger**: si pilot humano muestra que los casos quedan monótonos (los Architects siempre ponen el mismo tipo de fenómeno), agregamos 1 Validator sin foco que explora libre. Hoy 0.
- **Novelty corpus-level**: chequeo entre casos del corpus (no por caso). Detecta convergencia a 2-3 recetas. v1.6.
- **Sherlock multi-turn**: v2 (Epic #64). El Investigator pide observaciones, interviene, simula. En v1.5 es single-turn sobre dataset pre-sampleado.
- **Process quality scoring del trace**: issue #53.
- **Identifiability gate formal universal**: issue #54.

---

## 8. Riesgos abiertos (a vigilar durante MVP)

- **Architect rompe disciplina**: si "redondea hacia arriba" `weak_pass` o reescribe `intended_phenomenon` para que pase más fácil sin loggearlo, oculta bugs reales del WorldSpec. Mitigación: contratos `ValidatorVote.vote` inmutable; versionado del intended con log visible al Validator transversal. Pilot humano calibra.
- **Hill-climbing ciego con fenómenos acoplados**: si 2-3 fenómenos comparten coeficientes, ajustar un coef para `ip2` puede romper `ip1`. `margin` y `fragility` ayudan a guiar la iteración pero no resuelven. Si en pilot vemos oscilación, descartamos seeds difíciles temprano.
- **Cápsula saneada con leak residual**: el anti-leak no es total. Si la cápsula menciona "ten cuidado con confounders no observados" o "considera análisis estratificados", filtra parcialmente la respuesta. Pilot humano + judge entrenado calibran.
- **Validator transversal sobrecargado**: ahora tiene 10 checks. Puede no rendir con un solo prompt LLM. Si falla, dividimos en 2-3 sub-validators (ej. uno semántico, uno cuantitativo, uno estructural) sin cambiar contratos.
- **Costo en LLM calls**: Architect (multi-iter) + N Validators (×3 vueltas) + Question Designer + Case Writer + Validator transversal. Por caso, ~10-20 LLM calls. Para RL training a escala, hay que paralelizar agresivamente o cachear.

---

## 9. Próximos pasos

1. Aplicar cambios a contratos Pydantic v1.5:
   - borrar `proposal.py` + tests
   - crear `validated_phenomenon.py`
   - ajustar `validation.py` y `investigation.py`
   - actualizar `__init__.py`
2. Actualizar `ARCHITECTURE.md`.
3. Agregar Ronda 13 a `v1_5_debates.md`.
4. Actualizar bodies de issues #56 y #58 en GitHub.
5. Codex review final del cambio aplicado.
6. Commit + push.

Después de eso, retomamos implementación. La mayor complejidad nueva está en el Architect + Validators + feedback loop (issue #58 reescrito). Issue #56 queda chico (solo Environment + helpers básicos, sin dispatch).

---

## Ronda 14 — GoldQuestion → DiscoveryTarget (filosofía discovery-first, 2026-05-06)

Después de implementar Fase 1.2.b (Architect agent + lints + diagnósticos honestos), Lucas planteó una reformulación filosófica importante. Validada por Codex en consulta dedicada (thread `019dfe55-fe93`). Doc filosófico en `PROJECT.md` §"Investigación abierta vs examen cerrado".

### Tesis central

Tensión que el diseño anterior no resolvía bien:

- Si las `GoldQuestion`s son demasiado específicas (*"Estimate the ATE of X on Y"*), SREG se vuelve **examen cerrado**: el Investigator no investiga, responde subpreguntas implícitas.
- Si no hay target oculto, no hay forma de evaluar — pregunta vaga = infinitas respuestas válidas.

**Solución**: reinterpretar `GoldQuestion` como **`DiscoveryTarget`** — un descubrimiento central oculto que el mundo fue diseñado para contener, NO una pregunta a responder. Cada DT tiene dos capas: A) conclusión científica flexible en NL (paráfrasis OK); B) anchors formales verificables vía `EvidenceArtifact`.

### Decisiones de Ronda 14

1. **Renombre de schemas** (al implementar Fase 3, no antes — durante Fases 1.x el schema interno sigue llamándose `GoldQuestion` para no romper código ya commiteado):
   - `GoldQuestion` → `DiscoveryTarget`
   - `QuestionsBundle` → `DiscoveryBundle`
   - `QuestionDesigner` → `DiscoveryDesigner`
   - Campo `identification_hint` → `claim_match_hint` (semántica nueva: no es "¿aborda el tema?" sino "¿alguna claim llega a la conclusión?").

2. **Nuevo campo en DiscoveryTarget**: `source_validated_ids: list[str]` — auditoría del mapping N:M entre `ValidatedPhenomenon`s y `DiscoveryTarget`s. El Discovery Designer NO es 1:1; un fenómeno puede contribuir a varios targets y un target puede combinar varios fenómenos.

3. **Coexistencia de taxonomías**:
   - `IntendedPhenomenon.kind` = estructura del mundo (collider, mediation, etc.) — vocabulario operativo del Architect.
   - `DiscoveryTarget.kind` = tipo de descubrimiento (causal_mechanism, misleading_association, epistemic_limit, etc.) — taxonomía **descriptiva**, NO operativa: NO debe disparar templates de rubric ni scoring profiles, eso reintroduciría el catálogo cerrado que matamos en Ronda 12.

4. **Capability vs Knowledge**: en v1.5, capability-as-evidence permitido SOLO con `role="support"` y peso capado, NUNCA `required`. El score primario es knowledge contributions. Hidden test sets, ROC AUC programático, optimización de policies, controllers ejecutables se difieren a v2+.

5. **Frontera Case Writer rota**: en Ronda 13, el Case Writer recibía `QuestionsBundle`. **En Ronda 14 esto se rompe**: el Case Writer queda **CIEGO al DiscoveryBundle**. Solo recibe:
   - `WorldSpec` (público, conoce las variables visibles).
   - `narrative_capsule` saneada.
   - Lista de `DiscoveryTarget.kind` a alto nivel (taxonomía descriptiva, sin textos).
   El brief del caso NO referencia ningún `DiscoveryTarget.text`. Si lo hiciera, el agente parafrasearía y no investigaría.

6. **Las 4 protecciones contra el regreso al examen cerrado** (las 4 deben coexistir):
   - Capa A flexible en NL (target redactable libremente).
   - Capa B formal en anchors (verdad matemática contra Environment).
   - Evaluator que acredita conclusiones equivalentes (paráfrasis, claims cuantitativas que implican cualitativas).
   - Case Writer ciego al target oculto.

### Hooks reservados para v1.6+

- `EvidenceArtifact.access_mode: Literal["public_data", "interventional", "omniscient_latent"]` — para que el Validator transversal verifique que un anchor es **discoverable** desde la interfaz pública. Hoy un anchor numérico puede venir de leer una variable latente; eso lo hace imposible de recuperar para el Investigator. v1.6 agrega este typing y un nuevo lint.
- **Lint `discoverability` en Validator transversal**: separa "verdad" de "recuperabilidad". Un target puede ser verdadero pero no alcanzable desde el dataset visible bajo asunciones razonables.
- **Anchors específicos para ODE**: dirección/magnitud/ranking alcanza para SCM simples; ODE necesita trayectoria, timing, régimen, threshold temporal, equilibrio.
- Open scoring de `extra_claims` (premia descubrimientos no anticipados por el Architect).

### Cambio en taxonomía recomendada de DiscoveryTarget.kind

Vocabulario descriptivo (NO enum operativo) sugerido:

- `causal_mechanism` — el agente debe recuperar una relación causal con su dirección/magnitud.
- `misleading_association` — asociación cruda que es engañosa (collider, Simpson's paradox, selection bias).
- `mediation` — el efecto pasa por una variable intermedia.
- `effect_heterogeneity` — el efecto cambia según contexto/subgroup.
- `system_mapping` — descripción del comportamiento del sistema sin necesariamente claim causal.
- `epistemic_limit` — algún parámetro / efecto NO es identificable con la evidencia disponible.
- `dynamic_regime` (ODE) — equilibrio, threshold temporal, oscilación, transición de fase.
- `intervention_recommendation` — recomendación accionable expresada como conclusión.

Nuevos kinds pueden agregarse — la taxonomía es descriptiva, no normativa.

### Cambios en docs requeridos

| Doc | Cambio |
|---|---|
| `PROJECT.md` | Sección nueva "Investigación abierta vs examen cerrado" + invariante #2 reformulada + sección "Knowledge vs Capability". ✅ Actualizado. |
| `ARCHITECTURE.md` | §2 vocabulario + §3 flujo (Case Writer ciego al bundle) + §4 tabla del Designer + §5 contratos (DiscoveryTarget con source_validated_ids + claim_match_hint + access_mode hook) + §6 Rubric design + §7 Evaluator (Discovery Match) + §10 frontera + §11 no-goals. ✅ Actualizado. |
| `multi_explorer_redesign.md` | Esta ronda (#14). ✅ Actualizado. |
| `CURRENT_STATE.md` | Aclarar que Fase 1.x sigue válida; el cambio pega downstream. ⏳ Pendiente. |
| Issue #63 body | Reescribir Fases 3/4/6/7 con ontología nueva. ⏳ Pendiente. |
| Memoria personal | Nueva entrada con las 4 invariantes. ⏳ Pendiente. |
| Prompts de Paper Digestion / Architect | Cambios menores: Paper Digestion rename `natural_question_style` → `natural_investigation_style`. Architect agrega línea sobre "intended_phenomena alimentan descubrimientos downstream, no preguntas". ⏳ Pendiente, agendado para Fase 3. |

### Cambios en código que se difieren a Fase 3

NO se tocan ahora porque el código de Fases 1.x sigue válido. Se agendan para cuando arranque Fase 3 (Discovery Designer):

- Renombre del schema `GoldQuestion` → `DiscoveryTarget` (+ `QuestionsBundle` → `DiscoveryBundle`).
- Renombre del campo `identification_hint` → `claim_match_hint`.
- Agregar `source_validated_ids` a `DiscoveryTarget`.
- Rename de `narrative_capsule.natural_question_style` → `natural_investigation_style`.
- Agregar `EvidenceArtifact.access_mode` (hook v1.6+, opcional ahora).
- Update prompt de Paper Digestion (rename de field) + prompt de Architect (línea sobre downstream).

---

## Ronda 15 — Rubric como puente verificable + anchor model clarificado (2026-05-12)

Sesión de pinchazo conceptual con Lucas mientras explicaba el flujo Designer end-to-end. Se detectaron tres ambigüedades operativas en cómo el Evaluator conecta el reporte del Investigator con un `DiscoveryTarget`. No es un cambio filosófico (sigue Ronda 14) — es una clarificación del rol de cada artefacto.

### Las tres ambigüedades

1. **¿Qué es la rubric en v1.5?** En Ronda 13/14 se hablaba de "Completion graduada" como segundo paso del Evaluator (alpha=0.8 al Discovery Match + alpha=0.2 a Completion). Eso mezclaba "¿llegó a la conclusión?" con "¿el reporte está completo/calibrado/justificado?". Lo segundo es **proceso/calidad**, no descubrimiento, y debe diferirse a v1.6+.
2. **¿Cómo se usa el anchor formal?** El texto previo daba a entender que el anchor era "función ejecutable durante eval time" o "número de referencia sin contexto". Ninguna era precisa.
3. **¿Cómo evita el judge ser holístico?** Si la rubric tiene items vagos tipo "¿el reporte está bien?", regresamos al anti-pattern LLM-judge holístico que el SOTA review descartó.

### Decisiones (todas dentro del espíritu Ronda 14)

#### Decisión 1: rubric **es** el evaluador del target

Cada `DiscoveryTarget` tiene tres componentes con roles distintos:

- **`text` (Capa A, NL declarativa)**: descripción del descubrimiento para humanos. *"Estratificar por LBW invierte el signo del efecto Smoking → Mortality."* NO scorea — es identidad/contexto del target.
- **`answer_key` (Capa B, anchors numéricos)**: cantidades con rango/CI. Cada anchor está **respaldado por un `EvidenceArtifact` (script Python libre)** que produjo el número **una sola vez offline durante el Designer**. En evaluation time el anchor es **número de referencia**, no se re-ejecuta. El script queda como prueba reejecutable auditable.
- **`rubric` (preguntas verificables)**: lista de items que el judge evalúa contra el reporte. **Cada item es sí/no o match numérico contra un anchor**. NO hay items vagos tipo "¿es claro?" ni "¿está bien estructurado?". Si el item no puede responderse con criterio claro, NO va a la rubric.

La rubric **es el puente target↔reporte**: sin ella, el judge solo tendría (a) parseo numérico ciego del reporte o (b) juicio holístico. La rubric descompone la pregunta *"¿este reporte llega a la conclusión del target?"* en N preguntas verificables específicas.

#### Decisión 2: anchor model — script offline, número en eval

Flujo del anchor:

1. **Offline (Designer / Validator)**: el script Python del anchor corre contra el `Environment` con seeds múltiples, computa número + CI empírico. Número queda **fijado** en `AnswerKeyAnchor.value` + `tolerance` o `range`.
2. **Online (Evaluator)**: el judge ya tiene el número guardado. Para items numéricos de la rubric (*"¿el reporte da un valor en [-0.06, -0.02]?"*), parsea el reporte y compara. **NO re-ejecuta el script.**
3. **Auditoría**: el script vive en `EvidenceArtifact.script`, reejecutable manualmente si hay sospecha de que un anchor está mal.

Esto preserva los principios:

- No hay catálogo cerrado de funciones — el script es Python libre.
- La verdad sale de correr código contra el mundo formal, no de un LLM "estimando".
- Reproducibilidad: el anchor no depende del seed de evaluación.
- Costo: el LLM judge no necesita ejecutar nada, solo lee.

#### Decisión 3: rol del `claim_match_hint` — atacar target primero, resolver bien después

El campo `claim_match_hint` (Ronda 14, reemplaza `identification_hint`) se materializa en **dos checks distintos** del Evaluator por target:

1. **Match filter**: ¿alguna claim del reporte ataca este target específico? Si no → `score_target = 0`, siguiente target. Esto evita que un reporte sobre un tema no relacionado se "promedie" con uno que tocó el descubrimiento.
2. **Rubric scoring**: si match, recorrer los items de la rubric. Cada item devuelve `{pasó: bool, span: str, razón: str}`.

`score_target` = proporción ponderada de items satisfechos (con threshold, ver Decisión 4).

#### Decisión 4: alpha=1.0 en v1.5

```
score_caso = promedio_ponderado(score_target_i para target_i en bundle)

score_target = 0                                    si match_filter == False
score_target = rubric_score                         si match_filter == True

rubric_score = Σ (item.weight × item.satisfecho) / Σ item.weight
             (sobre items de la rubric del target)
```

**Lo que se difiere a v1.6+** (NO entra en score v1.5):

- Cobertura cualitativa entre múltiples targets (ya entra naturalmente en el promedio).
- Calidad de evidencia / Evidence-consulted logging (SOTA práctica #2 — integrity gate separado, NO scoring component).
- Calibración epistémica como dimensión separada.
- Claims espontáneas correctas fuera del bundle (`extra_claims`).
- Justificación textual evaluada por LLM judge holístico.

Estos artefactos del completion graduado de Ronda 13 (4 dimensiones: fidelidad, justificación, calibración, especificidad) **siguen siendo guideline editorial para redactar items de rubric**, no componentes del score directos.

#### Decisión 5: nuevo check del Validator transversal — rubric respondibilidad

El Validator transversal (Fase 5) ya tiene 12 checks (10 originales + shortcut resistance + difficulty band). Se agrega un **check 13**:

- **Rubric respondibilidad pública**: cada item de la rubric debe ser **respondible desde el dataset visible + tools del caso**. Items que requieran ver variables latentes, conocer parámetros del SCM, o ejecutar intervenciones que el Investigator no puede hacer → invalidan el target. Análogo al check #6 (answerability) pero a nivel ítem.

### Ejemplo concreto — Birth Weight Paradox

`DiscoveryTarget`:

```yaml
id: "bwp_dt_2"
kind: "misleading_association"

text: |
  Estratificar por LBW invierte el signo del efecto Smoking sobre Mortality:
  marginalmente fumar aumenta mortalidad, pero dentro de LBW=1 aparece como
  protector — patrón de collider con un confounder no observado de mortalidad.

answer_key:
  anchors:
    - name: effect_marginal
      range: [+0.03, +0.07]
      provenance: ea_001
    - name: effect_stratified_lbw1
      range: [-0.06, -0.02]
      provenance: ea_002

answer_key_provenance:
  - id: ea_001
    script: |
      data = env.sample(n=10_000, seed_array=range(20))
      effects = [sm.OLS.from_formula("Mortality ~ Smoking", d).fit().params["Smoking"]
                 for d in data]
      return {"mean": np.mean(effects), "ci_95": np.percentile(effects, [2.5, 97.5])}
    numerical_result: {mean: 0.052, ci_95: [0.038, 0.066]}
  - id: ea_002
    script: |
      ...stratified version...
    numerical_result: {mean: -0.041, ci_95: [-0.058, -0.024]}

claim_match_hint:
  match_if:
    - El reporte estima o discute el efecto de Smoking sobre Mortality
    - Y considera al menos una forma de análisis condicional/estratificado
      relacionada con peso al nacer

rubric:
  - id: r1
    text: "¿El reporte estima el efecto crudo (no condicional) de Smoking sobre Mortality?"
    weight: 1
    verifier: judge_yes_no
  - id: r2
    text: "¿El reporte estratifica por LBW (o variable equivalente de peso al nacer) o aplica análisis condicional?"
    weight: 2
    verifier: judge_yes_no
  - id: r3
    text: "¿El reporte detecta que dentro de LBW=1 el efecto se vuelve cero o negativo (cambia de signo o magnitud)?"
    weight: 3
    verifier: judge_yes_no
  - id: r4
    text: "¿Algún valor numérico del reporte para el efecto estratificado cae en [-0.06, -0.02]?"
    weight: 2
    verifier: numeric_match
    anchor_ref: effect_stratified_lbw1
  - id: r5
    text: "¿El reporte conecta el cambio de signo con un mecanismo (collider / confounding / selection bias / Simpson)?"
    weight: 2
    verifier: judge_yes_no
```

Evaluator sobre este target:

1. Match filter (`claim_match_hint`): ¿el reporte habla de Smoking, Mortality y análisis condicional por LBW? Si no → `score_target = 0`.
2. Si match, recorrer rubric. Suponé que satisface r1, r2, r3 (pesos 1+2+3=6); falla r4 (no da número); satisface r5 (pesos 2). Items total = 1+2+3+2+2 = 10. Satisfechos = 1+2+3+2 = 8.
3. `score_target = 8/10 = 0.8`.

### Tensión abierta — flagueada, no resuelta acá

El **Case Writer ciego al DiscoveryBundle** sigue siendo correcto (evita leak en el brief). Pero **el rol de pasarle `DiscoveryTarget.kind`** queda como decisión abierta para Fase 4: la justificación oficial es que el brief tenga el "tipo de problema" del dominio, pero ese olor podría salir solo de `WorldSpec + narrative_capsule` sin necesidad de los kinds. Pasarle kinds roza catálogo cerrado disfrazado.

**Decisión diferida a inicio de Fase 4**, opciones:

- **A**: Case Writer recibe solo `WorldSpec + narrative_capsule`. Cero metadato del bundle. Brief 100% abierto.
- **B**: Case Writer recibe `kinds` (status quo doc actual).
- **C**: Case Writer recibe abstracción más vaga ("este caso tiene N descubrimientos", sin tipo).

Instinto actual: opción A. Validar antes de implementar Case Writer.

### Cambios en docs y código requeridos

| Doc | Cambio |
|---|---|
| `multi_explorer_redesign.md` | Esta ronda. ✅ Aplicado. |
| `ARCHITECTURE.md` | §6 Rubric reescrita (items verificables, sin core/bonus complicado); §7 Evaluator un solo paso alpha=1.0; clarificar anchor model en §5. ⏳ |
| `CHANGELOG.md` | Entrada nueva. ⏳ |
| Memoria personal `project_oi_scoring_fundamentals.md` | Actualizar con el modelo final. ⏳ |
| Body de issue #63 | Ajustar texto de Fase 5 (check 13) y Fase 7 (un solo paso). ⏳ |
| Contratos Pydantic | **Sin cambios** — `Rubric`, `Criterion`, `AnswerKeyAnchor`, `AnswerKey` ya existen y soportan el modelo. La semántica de `Criterion.scoring_hint` se interpreta como "verifier instruction" (judge_yes_no / numeric_match). Eventual ajuste cosmético al implementar Evaluator (Fase 7), no antes. |
| Código | **Sin cambios** — Discovery Designer (Fase 3) y Evaluator (Fase 7) no están implementados todavía. |

### Por qué este modelo evita los anti-patterns conocidos

- **No catálogo cerrado**: rubric e ítems generados libremente por el Discovery Designer para cada target. Vocabulario libre, sin templates por `kind`.
- **No LLM-judge primary holístico**: el judge responde preguntas sí/no específicas, no juicio global. Esto coincide con la mitigación "rubric-based decomposition" / "J1-style thinking judges" mencionada en el HF guide.
- **No PRM dense process rewards**: process quality, calibration, justification quality se difieren a v1.6+. v1.5 mide solo conclusión.
- **No fake completeness**: el match filter (`claim_match_hint`) descarta reportes que no tocaron el target. No se "premia parcialmente" a quien pasó por al lado.

### Status post-ronda

- Diseño cerrado conceptualmente.
- Pendiente aplicar a `ARCHITECTURE.md`, `CHANGELOG.md`, memoria, issue #63.
- Pendiente decidir kinds → Case Writer al inicio de Fase 4.
- Pendiente arranque de Fase 2 (Validators deterministas).
