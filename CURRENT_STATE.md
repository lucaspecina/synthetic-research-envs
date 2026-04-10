# SREG — Como funciona hoy

> Referencia del sistema actual, escrita para alguien que quiere entender
> SREG sin tener que reconstruir todo desde el codigo.
>
> Este documento intenta responder dos preguntas:
> 1. Que hace SREG end-to-end?
> 2. Como se traduce una investigacion libre a verificaciones formales y score?
>
> Para detalles tecnicos de bajo nivel: `ARCHITECTURE.md`.
> Para la vision y los principios: `PROJECT.md`.
> Para el marco canonico de evaluacion paper/tesis: `research/synthesis/thesis_evaluation_framework.md`.
> Para la config operativa de training/transfer: `research/synthesis/sreg_training_transfer_protocol.md`.
> Para related work: `research/synthesis/related_work_sandmle.md`.
>
> **Este documento describe SREG v1** (Open Investigation sobre SCM). Para
> el roadmap del producto (v0 → v1 → v2 → v3) ver `PROJECT.md` seccion
> "Roadmap del producto". Para los criterios de cierre de v1 ver `TODO.md`
> seccion "SREG v1 — criterios de done".
>
> Actualizado: 2026-04-09

---

## Config v1 congelada (2026-04-09)

Estos son los parametros que definen "SREG v1". Cualquier cambio a
estos valores es un cambio de version, no un bugfix.

| Parametro | Valor | Donde vive |
|-----------|-------|------------|
| Scoring path | SQ v2 + LLM judge | `oi_runner._score_with_judge` |
| Claim cap | 15 | `open_investigation.MAX_CLAIMS` / `OIEpisodeRunner(claim_cap=)` |
| Solver model | gpt-5.2-codex | env `AZURE_SOLVER_MODEL` |
| Compiler/judge model | gpt-5.4 | env `AZURE_MODEL` |
| Max iterations | 20 | `run_oi_investigation(max_iterations=)` |
| Temperature | 0.0 | `run_oi_investigation(temperature=)` |
| Seed | 42 | `OIEpisodeRunner(seed=)` |
| n_mc (Monte Carlo samples) | 20,000 | `OIEpisodeRunner(n_mc=)` |
| Score formula | `total = correctness x weighted_coverage` | `_aggregate_score` |
| Match formula | `satisfaction = max(truth x relevance)` | `_aggregate_score` |
| Correctness | mean(truth) de TODAS las claims | `_aggregate_score` |

**Baseline canonico:** `results/v1_canonical_batch/` (12 casos, average
total 0.509, `rescore --reaggregate` delta 0.0000). Ver MANIFEST.md.

## Como usar SREG v1 (build -> use -> eval)

Tres pasos, tres scripts. Cada uno es independiente del anterior.

### Paso 1: Build — generar un caso

```bash
# Escribir un seed (archivo .md que describe el problema de investigacion)
# Ver seeds/ para ejemplos

python scripts/generate_src.py \
    --seed-file seeds/mi_caso.md \
    -o results/mi_caso \
    --oi          # incluye --oi para correr el solver en el mismo paso
```

Output: `results/mi_caso/src.json` (mundo, problema, datasets, SQs) +
`results/mi_caso/oi_result.json` (si se uso `--oi`).

Si solo queres generar el caso SIN correr el solver (para correrlo
despues con otro modelo o config):

```bash
python scripts/generate_src.py \
    --seed-file seeds/mi_caso.md \
    -o results/mi_caso
    # sin --oi: solo genera src.json
```

### Paso 2: Use — correr el solver sobre un caso existente

```bash
python scripts/run_oi.py results/mi_caso/
```

Toma `src.json`, reconstruye el mundo, carga las sub-questions, y corre
el solver LLM. Produce `oi_result.json` con claims, scores, y
conversation completa.

Opciones:
- `--claim-cap 15` (default v1)
- `--max-iterations 20` (default v1)
- `--temperature 0.0` (default v1)
- `--solver-model gpt-5.2-codex` (default v1)
- `--out results/otro_dir/` (output a otro directorio)

### Paso 3: Eval — verificar reproducibilidad

```bash
# Reaggregate: verifica que el scoring es determinista
python scripts/rescore.py results/mi_caso/ --reaggregate

# Rejudge: re-evalua relevancia con LLM (frozen truths)
python scripts/rescore.py results/mi_caso/ --rejudge

# Recompile: re-compila claims + re-verifica + re-evalua
python scripts/rescore.py results/mi_caso/ --recompile
```

### Requisitos

- Python 3.11+ con `pip install -e ".[dev]"` (o `conda activate sreg`)
- Azure credentials en `.env`: `AZURE_FOUNDRY_BASE_URL`,
  `AZURE_INFERENCE_CREDENTIAL`, `AZURE_MODEL`, `AZURE_SOLVER_MODEL`

---

## Que es SREG, en una frase

SREG genera **entornos de investigacion sintetica** donde un agente recibe un
brief abierto, datos ruidosos y herramientas de analisis, y el sistema puede
darle un **reward exacto** porque conoce la verdad oculta del mundo.

La idea no es "hacer preguntas de examen". La idea es construir algo mas
parecido a una investigacion real:

- el solver recibe una pregunta abierta;
- explora datos;
- decide que analizar;
- escribe conclusiones;
- y el sistema puntua si esas conclusiones eran verdaderas, relevantes y
  bien alineadas con el problema.

Lo importante es que la **verdad** no viene de un juez humano ni de un LLM.
Viene de una verdad formal oculta: el **SCM**. La **relevancia** (que tan
alineada esta una claim con el objetivo de investigacion) si usa un LLM juez,
pero es separable y reemplazable por feature-matching para RL.

---

## La imagen mental correcta: tres capas

Para entender SREG, conviene pensar en **tres capas**.

### 1. La verdad oculta: el mundo causal (`SCMWorld`)

Debajo de todo hay un **Structural Causal Model** o SCM.

Eso significa:

- un grafo causal;
- ecuaciones para cada variable;
- ruido;
- y la capacidad de samplear, intervenir y responder preguntas contra ese mundo.

Esta capa vive sobre todo en:

- `src/sreg/world/scm.py`
- `src/sreg/models/open_investigation.py`

El solver nunca ve esta capa directamente.

### 2. La investigacion visible: el problema que ve el solver (`ResearchProblem`)

Lo que el solver SI ve es un problema de investigacion con pinta real:

- titulo;
- dominio;
- brief;
- descripcion narrativa;
- variables observables;
- 1..N datasets;
- artefactos que puede cargar y analizar.

Esta capa vive sobre todo en:

- `src/sreg/models/research_problem.py`
- `src/sreg/tools/oi_runner.py`

### 3. La agenda de evaluacion: que considera importante el sistema

Ademas del mundo y del brief, SREG tiene una capa de evaluacion que decide
que verdades "importa" descubrir.

Hoy existen dos mecanismos:

- el **path principal actual**: `SubQuestionIntent` -> `ResolvedSubQuestion`
- el **path diagnostico / legado**: `SalienceFamily`

El path principal de los E2E actuales es el de **sub-questions**.

---

## Los nombres mas importantes

Esta es la lista de objetos que mas aparecen cuando uno trata de entender el
sistema actual.

| Nombre | Que es | Donde vive | Por que importa |
|---|---|---|---|
| `SCMWorld` | El mundo causal oculto | `world/scm.py` | Es la verdad del entorno |
| `ResearchProblem` | El problema visible que recibe el solver | `models/research_problem.py` | Define brief, datasets y metadatos |
| `DataAsset` | Un dataset/artefacto visible | `models/research_problem.py` | Es lo que el solver carga con `load_artifact` |
| `OIEpisodeRunner` | El runtime de un episodio OI | `tools/oi_runner.py` | Conecta solver, artefactos, trace y scoring |
| `EpisodeTrace` | Log estructurado de lo que hizo el solver | `models/open_investigation.py` | Registra accesos a artefactos |
| `ClaimCard` | La forma en que el solver entrega hallazgos | `models/open_investigation.py` | Es la entrada humana/semi-estructurada al compiler |
| `ClaimIntent` | IR simbolica intermedia del compiler | `tools/oi_compiler.py` | Traduce una claim libre a pattern + roles |
| `WorldSummary` | Resumen canonico del mundo | `tools/oi_compiler.py` | Convierte palabras vagas como "high" o "low" en valores concretos |
| `CompiledUnit` | Una unidad verificable extraida de una claim | `tools/oi_compiler.py` | Un claim compuesto puede producir varias |
| `AtomicSpec` | La unidad formal minima verificable | `models/open_investigation.py` | Es lo que realmente ejecuta el verifier |
| `SubQuestionIntent` | Item de agenda oculto generado por el orchestrator | `models/open_investigation.py` | Representa que considera importante el sistema |
| `ResolvedSubQuestion` | Una sub-question ya resuelta contra el SCM | `models/open_investigation.py` | Es la "answer key" formal de una SQ |
| `EpisodeSubQuestionScore` | Score principal actual de OI | `models/open_investigation.py` | Resume coverage/correctness sobre SQs |
| `SalienceFamily` | Familia de verdades relevantes | `models/open_investigation.py` | Parte del path diagnostico/legacy |

Si alguien solo pudiera llevarse 5 nombres, deberia recordar estos:

- `SCMWorld`
- `ResearchProblem`
- `ClaimCard`
- `AtomicSpec`
- `SubQuestionIntent`

---

## El flujo completo, de punta a punta

### 1. Seed -> orchestrator -> caso

Todo arranca desde una semilla:

- un paper;
- un PDF;
- un markdown;
- un goal libre;
- o incluso nada.

El orchestrator LLM toma esa semilla y disena un caso:

- que variables hay;
- como se relacionan;
- cual es el brief visible;
- que datos van a estar disponibles;
- y que sub-questions ocultas van a definir la evaluacion.

El punto importante es este:

- el brief visible y la agenda oculta NO son lo mismo;
- el solver ve el brief;
- el sistema usa la agenda oculta para evaluar.

La pieza clave aca es `design_case` en:

- `src/sreg/orchestrator/orchestrator.py`

Salida conceptual:

- un `SCMWorld` oculto;
- un `ResearchProblem` visible;
- una lista de `SubQuestionIntent`.

### 2. Construccion del mundo y los datos

Una vez definido el caso, el sistema construye:

- el grafo causal;
- las ecuaciones estructurales;
- metadatos de variables;
- datasets sampleados del mundo;
- ruido y missingness;
- artefactos visibles para el solver.

En la practica, el solver no interactua con el SCM directamente.
Interactua con `DataAsset`s y con helpers de analisis.

### 3. Inicio del episodio OI

El solver corre dentro de `OIEpisodeRunner`.

Ese runner hace varias cosas a la vez:

- mantiene el catalogo de artefactos (`ArtifactCatalog`);
- expone `load_artifact` y `save_artifact`;
- prepara el namespace de Python;
- registra accesos y analisis en `EpisodeTrace`;
- y al final ejecuta el pipeline de scoring.

El solver NO esta "hablando con el SCM". Esta haciendo algo mucho mas parecido
a una investigacion sobre datasets visibles.

### 4. Herramientas visibles del solver

Hoy el solver opera principalmente con:

- `python_exec`
- `load_artifact(...)`
- `save_artifact(...)`
- `submit_claims(...)`

Cada vez que carga un artefacto, el runner lo registra en `EpisodeTrace`.
Esto permite reconstruir que hizo realmente el solver.

### 5. El solver entrega `ClaimCard`s

Al final, el solver no entrega codigo ni un paper entero. Entrega una lista de
`ClaimCard`s.

Una `ClaimCard` tiene principalmente:

- `claim_id`
- `claim_text`
- `focus_variables`
- `confidence`
- `evidence_basis`

Y algunos campos opcionales:

- `outcome_aspect`
- `comparison_text`
- `scope_text`
- `pattern_tags`
- `caveats`

La idea de `ClaimCard` es importante:

- no es texto totalmente libre;
- pero tampoco es una especificacion formal como `AtomicSpec`.

Es un formato de "hallazgo cientifico reportado".

---

## Como una claim termina convertida en una verificacion formal

Esta es probablemente la parte mas importante para entender SREG hoy.

El pipeline actual es:

```text
ClaimCard
  -> extractor LLM
  -> ClaimIntent
  -> lowering deterministico
  -> AtomicSpec(s)
  -> verifier
  -> truth score
```

### Paso A. `ClaimCard` -> `ClaimIntent`

Esto ocurre en:

- `src/sreg/tools/oi_extraction.py`
- `src/sreg/tools/oi_exemplars.py`

El extractor usa un LLM para leer el texto de la claim y producir una
representacion intermedia llamada `ClaimIntent`.

Hoy `ClaimIntent` tiene principalmente:

- `pattern`
- `treatment`
- `outcome`
- `direction`
- y opcionalmente `mediator`, `modifier`, `confounder`, `ranking_vars`,
  `conditioning_set`

Los `pattern`s reconocidos hoy son 8:

- `causal_effect`
- `mediation`
- `heterogeneity`
- `tail_risk`
- `variance_effect`
- `observational_association`
- `effect_ranking`
- `confounding`

Importante:

- esta lista NO es toda la expresividad del sistema;
- es solo la ontologia intermedia que hoy usa el compiler.

Otra idea importante: una claim puede ser compuesta.
Por eso desde A22 una sola `ClaimCard` puede producir varios `CompiledUnit`s.

### Paso B. `WorldSummary`: de palabras vagas a anclas canonicas

El LLM no elige percentiles ni thresholds concretos.
Eso lo hace el codigo via `WorldSummary`.

`WorldSummary` samplea el mundo y guarda cosas como:

- `p25`
- `p50`
- `p75`
- `mean`
- `std`

para cada variable.

Entonces el LLM dice algo como:

- "tratamiento alto vs bajo"

y el codigo lo vuelve algo como:

- `high = p75`
- `low = p25`

Esto es importante porque reduce subjetividad.
El LLM decide la intencion; el codigo fija los valores canonicos.

### Paso C. `ClaimIntent` -> `AtomicSpec(s)`

Esto ocurre en:

- `src/sreg/tools/oi_compiler.py`

La funcion clave es `lower_intent()`.

Toma un `ClaimIntent` ya validado y lo convierte a uno o mas `AtomicSpec`s.

La idea central es:

- `ClaimIntent` todavia es una IR humana/simbolica;
- `AtomicSpec` ya es una unidad formal ejecutable.

### Paso D. Que es un `AtomicSpec`

`AtomicSpec` es la pieza formal mas importante del sistema actual.

Un `AtomicSpec` combina cuatro cosas:

1. `arms` (`QueryArm`)
2. `measurement`
3. `comparison`
4. `assertion`

Eso significa:

1. **Que escenarios corro?**
   Ejemplo: baseline, intervenir, observar condicionado, ajustar, sweep.
2. **Que mido en esos escenarios?**
   Ejemplo: media, correlacion, partial correlation, varianza.
3. **Como comparo esos resultados?**
   Ejemplo: diferencia, ratio, ranking, gap.
4. **Que afirmo sobre esa comparacion?**
   Ejemplo: positivo, negativo, near_zero, rank_order, not_identifiable.

Una manera amigable de pensarlo es:

- `AtomicSpec` = "la pregunta formal exacta que el verifier sabe ejecutar".

### Ejemplo concreto: "X aumenta Y"

Supongamos que el solver entrega:

> "A mayor tratamiento, mayor recuperacion"

El compiler podria bajar eso a algo conceptualmente asi:

- `arms`:
  - intervenir `treatment = low`
  - intervenir `treatment = high`
- `measurement`:
  - media de `recovery`
- `comparison`:
  - diferencia entre ambos brazos
- `assertion`:
  - esa diferencia debe ser positiva

Ese bundle de 4 piezas ya es un `AtomicSpec`.

### Ejemplo concreto: "Z confunde X -> Y"

Una claim de confounding suele necesitar mas de un atom.
Por ejemplo:

- un atom que representa el efecto causal X -> Y;
- otro atom que representa la asociacion ajustada/controlada;
- y el veredicto conjunto sale de ambos.

Por eso una claim no tiene que corresponder 1:1 con un solo `AtomicSpec`.
Puede bajar a varios.

### Paso E. `AtomicSpec` -> verificacion

Esto ocurre en:

- `src/sreg/tools/oi_verifier.py`

La funcion clave es `verify_atom(spec, world, solver, ...)`.

El verifier hace siempre la misma secuencia:

1. corre los `arms`;
2. mide lo que dice `measurement`;
3. compara con `comparison`;
4. chequea si la `assertion` se cumple.

La salida es un `AtomVerdict`:

- cual era el atom;
- cual fue el ground truth numerico;
- si la afirmacion del solver se sostiene o no;
- y score 0/1 para ese atom.

En el path actual de sub-questions, una `CompiledUnit` se considera verdadera
solo si **todos** sus atoms sostienen la afirmacion del solver.

---

## Como funcionan hoy las sub-questions

Las `SubQuestionIntent` son la agenda oculta que define que considera
importante descubrir el sistema.

Hoy cada SQ tiene principalmente:

- `sq_id`
- `pattern`
- `roles`
- `ask`
- `tier`
- `text_gloss`

### Que significa cada campo

- `pattern`: de que tipo de hallazgo estamos hablando
- `roles`: que variables juegan cada rol (`treatment`, `outcome`, etc.)
- `ask`: que se pregunta exactamente (`existence`, `sign`, `magnitude`, `rank_order`)
- `tier`: cuanto pesa (`high`, `medium`, `low`)
- `text_gloss`: explicacion humana corta

### Como se resuelven hoy contra el SCM

Esto ocurre en:

- `src/sreg/tools/oi_subquestions.py`

La funcion clave es `resolve_subquestion()`.

Y este detalle es muy importante:

**Hoy las SQ no van directo a `AtomicSpec`.**

El flujo actual es mas indirecto:

```text
SubQuestionIntent
  -> construir ClaimIntent(s) candidatos
  -> lower_intent()
  -> AtomicSpec(s)
  -> verify
  -> ResolvedSubQuestion
```

En otras palabras:

- primero la SQ se expresa como `pattern + roles + ask`;
- despues el sistema reconstruye intents candidatos;
- recien despues baja a `AtomicSpec`.

El resultado final es una `ResolvedSubQuestion`, que contiene:

- la SQ original (`intent`);
- la respuesta verdadera (`resolved_answer`);
- los componentes que la sustentan (`components`);
- y los specs usados para resolverla.

### Por que esto importa tanto

Porque significa que el sesgo al catalogo de patterns no solo afecta a las
claims del solver. Tambien afecta a la propia agenda oculta.

Ese fue justamente el hallazgo nuevo de A23:

- no solo el compiler de claims esta acotado;
- tambien las SQ actuales pasan por una IR estrecha basada en patterns.

---

## Como se calcula hoy el score principal

El path principal es **v2 con LLM judge** (`_score_with_judge` en oi_runner.py).

Pipeline:

```text
ClaimCards + compiled specs + SQs v2
  -> 1. Truth per claim (conjunctive: all atoms must hold)
  -> 1b. Evidence validation (cited artifacts must be in trace)
  -> 2. Answer keys from pre-grounded SQ verdicts
  -> 3. LLM judge: relevance per (claim, SQ) pair
  -> 4. Per-SQ satisfaction = max(truth x relevance) across claims
  -> EpisodeSubQuestionScore final
```

### Paso 1: Truth (exacta, sin LLM)

Para cada claim compilada, el verifier ejecuta todos sus AtomicSpecs contra
el SCM. Si **todos** los atoms sostienen la afirmacion = truth 1.0, si alguno
falla = truth 0.0 (conjunctiva). Ademas, si el solver cita artifacts que
nunca cargo ni creo, se aplica una **penalidad proporcional** sobre el truth
de esa claim (BUG 8 fix, 2026-04-06): si todas las citas son fabricadas
→ truth × 0.1; si algunas son validas → truth × (validas / total).

**Nota sobre credit-assignment (limitacion conocida, ver TODO A28):** el truth
se calcula a nivel de **claim completa** (promedio de todos sus specs). Esto
puede penalizar claims ambiciosas con muchos specs donde algunos fallan, y
favorecer claims genericas con pocos specs. Es un design issue documentado
que se planea resolver con unit-level scoring (TODO I0d P2).

### Paso 2-3: Relevance (LLM judge)

El juez LLM recibe cada claim y cada SQ (con sus answer keys ricos: verdad
resuelta contra el SCM, variables, direccion esperada) y decide que tan
relevante es esa claim para esa SQ (0 a 1). No evalua verdad — solo
alineacion semantica.

### Paso 4: Scoring

Para cada SQ: satisfaction = max(truth x relevance) entre todas las claims.

Componentes del score:

- `weighted_coverage`: media ponderada de satisfactions (weight por tier)
- `correctness`: media de truth de TODAS las claims (penaliza claims falsas)
- `total = correctness x weighted_coverage` (ambos deben ser altos)

### Resultados E2E validados (2026-04-06)

Batch de 12 seeds diversas (post BUG 8+9 fix). 11/12 exitosos:

| Seed | Type | Total | Correctness | Wt.Coverage |
|------|------|-------|-------------|-------------|
| missing_data | epistemological_method | 0.786 | 1.000 | 0.786 |
| selection_bias | selection_bias | 0.719 | 0.875 | 0.821 |
| identifiability | epistemological | 0.679 | 0.833 | 0.814 |
| heterogeneity | heterogeneity | 0.632 | 0.917 | 0.689 |
| chemical | optimization | 0.551 | 0.875 | 0.629 |
| confounding | confounding | 0.422 | 0.700 | 0.602 |
| coral_bleach | descriptive | 0.380 | 0.688 | 0.552 |
| competing_mech | causal_mechanism | 0.363 | 0.525 | 0.692 |
| microbiome | system_mapping | 0.196 | 0.506 | 0.387 |
| policy_equity | policy_tradeoff | 0.142 | 0.467 | 0.303 |
| poverty | causal_simple | 0.003 | 0.025 | 0.101 |
| vaca_predict | prediction | FAIL | — | — |

**Average (N=11): 0.443.** Audit profundo revelo 4 failure modes
(ver TODO A28): grammar gap (poverty), credit-assignment (microbiome),
solver miss (policy_equity, coral_bleach), y SQ overlap (secundario).

Datos: `results/e2e_batch_bug8_9_fix/`

### Algo importante: tres scorers existen, solo uno es canonico

Hay **tres rutas de scoring** en el codigo. **Solo la primera es canonica
para SREG v1.** Las otras dos son legacy fallback documentado — sus scores
no son validos como resultados oficiales de v1 y el runner emite un
`logger.warning("LEGACY PATH: ...")` cuando se usan.

| Path | Funcion | Formula | Estado |
|---|---|---|---|
| **CANONICO v1** | `oi_runner._score_with_judge` | `total = correctness x weighted_coverage` (multiplicativo). Match score = `truth x relevance` (LLM judge). Correctness = mean de TODAS las truths. | **Unico path canonico de SREG v1.** Requiere `sub_questions_v2`. |
| legacy: SQ v1 | `oi_subquestions.score_episode_with_subquestions` | `total = wcov*0.70 + corr*0.20 + novel + cov*0.10` (aditivo). Match score = `truth x compat x answer_score` (sin LLM). | Legacy fallback. Warning en logs. No es resultado oficial v1. |
| legacy: salience map | `score_compiled_episode_v2` | `EpisodeScore`, `ClaimVerdict`, `SalienceFamily`, `efficiency`. | Legacy fallback. Warning en logs. No es resultado oficial v1. |

### Claim cap: 15 (congelado para v1, 2026-04-09)

El solver puede submitir entre 1 y **15** claims atomicas. Este valor
(`MAX_CLAIMS = 15`) esta parametrizado como `claim_cap` a lo largo de
todo el chain: `OIEpisodeRunner(claim_cap=...)` -> prompt dinamico
(`"1-{claim_cap} atomic claims"`) -> tool schema (`maxItems`) ->
enforcement en `submit_claims`.

Decision basada en P06 cap decision (24 runs). Cap=5 fuerza bundling
que reduce resolucion del instrumento. Cap=15 permite decomposicion
atomica y amplifica la senal de calidad de juicio (el solver que
especula sin verificar se penaliza mas). Ver
`research/notes/p06_cap_decision_result.md`.

**Para cualquier cambio sobre scoring:** apuntar al canonico
(`_score_with_judge`) y replicar en `scripts/rescore.py::_aggregate_score`
que es el espejo offline. NO modificar los paths legacy salvo que el
cambio sea explicitamente para tests/benchmarks.

**Nota:** el sistema de warrant (que intentaba medir si el solver habia
investigado de verdad antes de submitir) fue eliminado (L1, 2026-04-01).
El solver usa pandas/numpy directamente, sin helpers instrumentadas.

---

## La otra capa de evaluacion: salience families

Antes del path de sub-questions, la idea mas central era la de
`SalienceFamily`:

- el sistema construye familias de verdades relevantes del mundo;
- cada familia tiene uno o varios atoms;
- y el solver gana credito por cubrir familias importantes.

Eso sigue existiendo y es util como diagnostico, pero hoy no es el path mas
usado en la iteracion principal de OI.

Conviene pensarlo asi:

- `SubQuestionIntent` = agenda de evaluacion mas interpretable y pegada al brief
- `SalienceFamily` = mapa de verdades relevantes mas estructural

Hoy coexisten, pero la linea activa va por sub-questions.

---

## Lo que si esta resuelto hoy

Hay varias cosas importantes que ya no son el cuello principal.

### 1. OI como modo principal

El sistema activo es **Open Investigation**.

El solver recibe un brief abierto y decide:

- que mirar;
- que analizar;
- y que concluir.

No hay un cuestionario paso a paso ni un planner rigido en el path central.

### 2. Multi-unit compiler (A22)

Antes, una claim compuesta podia romper el compiler porque `ClaimIntent`
asumia efectivamente una sola relacion central.

Hoy una `ClaimCard` puede producir varias `CompiledUnit`s.

Eso mejoro mucho los casos donde el solver dice cosas como:

- "X afecta Y y tambien afecta Z"
- "A causa B que a su vez afecta C"

### 3. Compatibilidad parcial entre tipos de claim (A21)

No todo mismatch entre claim y SQ vale 0.

Por ejemplo, una claim observacional puede recibir credito parcial frente a
una SQ causal si esta en la direccion correcta y toca la misma estructura.

Eso hace que el sistema sea menos brittle.

### 4. Force-submit

Habia muchos episodios donde el solver investigaba bien pero no llamaba a
`submit_claims` a tiempo.

Hoy existe un mecanismo de force-submit / ultimo turno restringido que mitiga
ese problema.

No es una solucion filosoficamente elegante, pero mejoro bastante el E2E.

---

## Sutileza terminologica: "SQ v1" y "SQ v2" NO son versiones del producto

Este documento describe **SREG v1** (producto). Cuando las secciones
siguientes hablan de "SQ v1 (pattern-based)" y "SQ v2 (specs-based)", se
refieren a **dos sub-pipelines internos** del compiler y del matcher de
sub-questions **dentro de SREG v1**. Son evoluciones internas, no versiones
del producto.

En terminos del roadmap del producto (`PROJECT.md` seccion "Roadmap del
producto"):
- **SREG v1** = el producto actual. Open Investigation. Todo lo que
  describe este documento.
- **SREG v2** = futuro. Sherlock-type, research actions con budget,
  capas de revelacion, teoria sintetica.
- **SREG v3** = futuro lejano. Sistemas complejos dinamicos.

Los pipelines "SQ v1" y "SQ v2" viven AMBOS dentro de SREG v1, pero
**solo SQ v2 (specs-based) + LLM judge es el path canonico de SREG v1**
(`oi_sq_compiler.py`, `oi_sq_matching.py`). SQ v1 (pattern-based) y
salience map quedan como legacy fallback documentado — el runner emite
warnings cuando se usan y sus scores no cuentan como resultados oficiales
de v1. Analogamente, "Suite v1" refiere a la suite de evaluacion externa
— no es el producto SREG v1.

---

## SQ v2 — Pipeline principal (integrado)

Ademas del path v1 (pattern-based), existe un prototipo v2 que libera las SQs
del catalogo de 8 patterns. El spec canonico esta en
`research/synthesis/sq_v2_matching_spec.md`.

### Que cambia en v2

| Concepto | v1 (actual) | v2 (prototipo) |
|---|---|---|
| SQ se define como | pattern + roles + ask | text_gloss + verification_specs |
| Verificacion | Se construye via ClaimIntent | Bundle de AtomicSpecs directo |
| Roles en la SQ | treatment, outcome, mediator... | required/support por spec |
| Matching claim-SQ | family_compat x operator_compat | Exacto en estimand, fuzzy en assertion |
| Compilacion | Routing por pattern | LLM + grammar composable |

### Modelos nuevos

- `SubQuestionIntentV2` — sq_id, text_gloss, verification_specs, tier, focus_variables
- `VerificationSpec` — AtomicSpec + role (required/support) + verdict

### Modulos nuevos

- `oi_sq_compiler.py` — compile step LLM: text_gloss → AtomicSpec bundle
- `oi_sq_matching.py` — spec_match + bipartite 1-a-1 + episode scoring

### Primer test (2026-03-30)

5 SQs diversas (causal, epistemologico, descriptivo, confounding, mediacion)
compiladas y verificadas contra un SCM de 8 nodos:

- 5/5 compilaron exitosamente
- 18 specs totales (promedio 3.6/SQ)
- 4 measurement kinds distintos (vs ~2 con v1)
- 0 errores de validacion
- 13/18 TRUE contra el SCM (72%)
- Causal y epistemologico: 100% TRUE
- Los FALSE son assertions que no coinciden con el SCM — funcionamiento esperado

### Estado actual: VALIDADO E2E (2026-04-02)

El pipeline v2 es el **path principal de produccion**. Validado con 7 worlds
(5 curated v1 + 2 seeds v2). El scoring combina:

- **Verdad exacta** del SCM (via AtomicSpecs + verifier con do-calculus)
- **Relevancia semantica** evaluada por un LLM juez (oi_relevance_judge.py)
- **Validacion de evidencia** contra artifacts realmente accedidos (trace)

El juez LLM recibe answer keys ricos (verdad pre-resuelta contra el SCM,
variables, direccion esperada) para evaluar relevancia. Esto hace que el
matching claim-SQ sea mucho mas preciso que el v1 estructural.

### Contrato del compiler — 3 estados terminales (2026-04-08)

El SQ compiler (`oi_sq_compiler.py::compile_sq_to_specs`) ahora distingue
**tres estados terminales** en `SQCompileResult`:

| Estado | Que significa | Como reacciona el orchestrator |
|---|---|---|
| `success` | El LLM emitio specs validas | Se compilan y se agregan al plan |
| `abstained` | El LLM emitio `[]` deliberadamente | La SQ se descarta del plan, NO cuenta como error |
| `error` | El LLM no devolvio JSON valido / fallo el parse | Se cuenta como compile error |

La rama `abstained` cubre claims sobre cantidades que la gramatica del
verifier no puede evaluar de forma exacta — por ejemplo coeficientes de
regresion, betas estandarizados, AIC, R-cuadrado, componentes de varianza
de modelos mixed-effects, o cualquier numero que dependa de un modelo
ajustado por el solver y no de una propiedad del SCM. En lugar de inventar
una spec inverificable, el compiler senala abstencion explicita.

Scoring, matching y la politica de required-fallback quedan **sin
cambios**: este es el contrato de superficie unicamente. El runner E2E
no necesita cambios para consumir el nuevo contrato — el compile loop
ya distingue las tres ramas.

### Flow B: adjust_set derivado del SCM (2026-04-09)

El LLM del SQ compiler (`oi_sq_compiler.py`) **ya no elige `adjust_set`**
en arms de tipo `adjust`. El `GRAMMAR_REF` le dice explicitamente "DO NOT
specify" y el loop de `compile_sq_to_specs` strippea cualquier
`adjust_set` que el LLM haya emitido antes de construir el `AtomicSpec`.

El verifier (`oi_verifier.py::_run_adjustment`) auto-computa un backdoor
set valido desde el DAG del SCM via `_find_backdoor_set(world, T, Y)`
cuando `arm.adjust_set` es vacio, o devuelve `adjust_invalid` limpio
si no existe set identificable. Esto ya existia — el cambio es que ahora
`adjust_set` SIEMPRE llega vacio al verifier desde Flow B.

**Flow A** (`oi_compiler.py::lower_intent`) queda intacto: el solver
sigue siendo responsable de su propio razonamiento causal. Ver
`PROJECT.md` invariante 8 (Flow A vs Flow B) para el contrato completo.

### Harness aislado de recompile (2026-04-08)

`scripts/p06_recompile_only.py` reinvoca el compiler sobre los textos de
SQs congeladas de un baseline y diffea las rutas de emision contra el
baseline original. Es **diagnostico**, no un sustituto del runner E2E:

- Mide cuanto del compiler emite rutas semanticamente validas sobre los
  mismos textos sin volver a correr el solver, el matcher, ni el scoring.
- Tres metricas por componente: `C1a` (resolved_rate, fraccion de SQs
  cuyas required specs compilan), `C1b` (bad_replacement_rate, fraccion
  donde la nueva compilacion rompe specs que antes funcionaban), `C1c`
  (per-component reroute quality flags).
- Gate `role=required` estricto en el classifier: las rutas que solo
  aparecen como `support` no pueden inflar C1a.
- Flag opcional `--ground-sanity` corre `verify_atom` sobre las required
  specs reruteadas — los criterios de exito son `no_exception` /
  `detail_nonempty` / `measurement_finite`, NO `solver_assertion_holds`
  (el harness mide rutas de emision, no si el claim es verdadero).

Default: 5 hard-fail cases (`competing_mech`, `coral_bleach`,
`immunotherapy`, `microbiome`, `selection_bias`); `--all-cases` recompila
la baseline completa.

---

## 15 tipos de investigacion — que puede hacer el sistema hoy

Esta tabla muestra tipos diversos de investigacion y si el sistema actual
puede evaluarlos. La columna "v1" es el path de produccion; "v2" es el
prototipo de SQ specs-based.

1. **Causal simple** — v1: SI, v2: SI
   - Formal: "X causa Y? Con que magnitud?"
   - Real: "Los antibioticos tempranos reducen la mortalidad en sepsis? En cuanto?"

2. **Confounding** — v1: SI, v2: SI
   - Formal: "Z confunde X->Y?"
   - Real: "La severidad del paciente explica por que los que tardan mas en recibir antibioticos mueren mas?"

3. **Mediacion** — v1: SI, v2: SI
   - Formal: "El efecto de X pasa por M?"
   - Real: "La contaminacion afecta la expectativa de vida directamente o porque primero causa enfermedades respiratorias?"

4. **Heterogeneidad** — v1: SI, v2: SI
   - Formal: "El efecto de X varia por subgrupo?"
   - Real: "La inmunoterapia funciona igual en pacientes con biomarcador alto vs bajo?"

5. **Epistemologico** — v1: NO, v2: SI (v1 fuerza pattern causal)
   - Formal: "Es robusta la asociacion al ajuste?"
   - Real: "La correlacion entre contaminacion y enfermedad respiratoria sobrevive si controlamos por tabaquismo y acceso a salud?"

6. **Descriptivo** — v1: NO, v2: SI (v1 fuerza treatment/outcome)
   - Formal: "Que variables se asocian con Y?"
   - Real: "De los 5 marcadores de salud, cuales correlacionan mas fuerte con la diversidad del microbioma?"

7. **System mapping** — v1: PARCIAL, v2: SI (v1 solo cubre pares)
   - Formal: "Cual es la estructura causal del sistema?"
   - Real: "Por que se atrasan las entregas? Es el proveedor, el transporte o el inventario? Como interactuan?"

8. **Multi-outcome / trade-off** — v1: PARCIAL, v2: SI (v1 evalua outcomes por separado)
   - Formal: "Trade-off entre supervivencia y toxicidad"
   - Real: "El esquema A de inmunoterapia mejora supervivencia pero aumenta toxicidad severa. Cuando conviene usarlo?"

9. **Tail risk** — v1: SI, v2: SI
   - Formal: "Prob de fallo catastrofico bajo stress?"
   - Real: "El diseno termico A tiene 3x mas probabilidad de thermal runaway arriba de 40C?"

10. **Value of information** — v1: NO, v2: PARCIAL (v2 verifica building blocks, no VOI puro)
    - Formal: "Que medicion reduce mas la incertidumbre?"
    - Real: "Para decidir si la contaminacion causa cancer, conviene mas medir exposicion individual o hacer un estudio de intervencion?"

11. **Selection bias** — v1: NO, v2: SI (v1 no tiene SQ para adjustment sensitivity)
    - Formal: "El efecto es real o artefacto de seleccion?"
    - Real: "Los arrestos policiales parecen sesgados por raza, pero los datos solo incluyen los detenidos. El sesgo es real o refleja quien entra en la muestra?"

12. **Equidad de politica** — v1: PARCIAL, v2: SI (v1 solo capta heterogeneidad por modifier)
    - Formal: "La politica afecta igual a todos los grupos?"
    - Real: "El impuesto a bebidas azucaradas reduce consumo, pero afecta proporcionalmente mas a hogares de bajos ingresos?"

13. **Structure discovery** — v1: NO, v2: PARCIAL (v2 compila specs de estructura parcial)
    - Formal: "Quien influye a quien? Que es directo vs indirecto?"
    - Real: "Con registros de actividad cerebral de 6 regiones, reconstruir que region influye a cual durante la tarea"

14. **Prediccion / optimizacion** — v1: NO, v2: NO (fuera del scope actual, ver PROJECT.md H1)
    - Formal: "Maximizar AUC" o "mejor configuracion"
    - Real: "Encontrar la combinacion de temperatura y presion que maximiza el rendimiento del proceso quimico"

15. **Diseno experimental** — v1: NO, v2: NO (fuera del scope actual, ver PROJECT.md H2)
    - Formal: "Que dato conviene recolectar primero?"
    - Real: "Tengo presupuesto para 100 mediciones. Donde las pongo para aprender mas sobre el sistema?"

**Resumen**: v1 funciona bien para los primeros 4 (causal clasico). v2 extiende
la cobertura a ~12 de 15 tipos. Los 2-3 restantes requieren extensiones
arquitecturales futuras (artefactos evaluables, interaccion con el entorno).

---

## Los bottlenecks actuales

### 1. Grammar gap: claims sofisticadas inexpresables — MITIGADO P1 (2026-04-06)

**P1 — predicados de subpoblacion (smoke-validated).** `QueryArm.condition_on`
ahora acepta 4 predicados: `approx_eq` (default, backward compat),
`range`, `quantile_range`, `in_set`. Discriminated union + auto-promote
de scalars. Verifier dispatch en `_filter_condition`.

Lo que se puede expresar ahora y antes no:
- RDD / bandwidths: `{"eligibility_gap": {"kind": "range", "lo": -1000, "hi": 1000}}`
- Quartiles: `{"income": {"kind": "quantile_range", "q_lo": 0.0, "q_hi": 0.25}}`
- Categorias: `{"region": {"kind": "in_set", "values": ["urban", "suburban"]}}`

Evidencia smoke-validated:
- rescore --reaggregate sobre 12 casos: delta 0.0000 (backward compat).
- recompile poverty: emite 8 `quantile_range` donde antes solo habia
  point values en abstention. NO se atribuye el salto de score
  (0.003 → 0.449) a P1 — variancia LLM en compiler + cambios de
  pipeline lo confunden.
- 6/12 batch adoptan organicamente: 5 quantile_range + 1 range.
- 5/12 sin condition_on: todos legitimamente no necesitan subpoblacion.

**Caveats abiertos** (deuda P1.5, ver TODO):
- `in_set` no probado E2E con LLM — todos los seeds son numericos
  (gap de worldgen: SCM no soporta categorical nodes, no es gap de P1).
- Ventanas temporales generales (wave/site_id, panel data) NO resueltas:
  P1 cubre predicados sobre variables del world, no sobre columnas
  fuera de `world.variables`.
- `_filter_condition` hoy hace silent skip de columnas faltantes
  (footgun: si el LLM alucina `eligible`, el filtro ignora silenciosamente).
- N=12 es chico — no se afirma que P1 mueve scoring promedio del batch.

### 2. Credit-assignment a nivel claim

Truth se calcula promediando todos los specs de una claim. Claims ambiciosas
con muchos specs (donde algunos fallan) pierden contra claims genericas con
pocos specs. Ademas, `matched = best_score > 0` infla coverage.
Caso emblematico: microbiome (claims correctas, score 0.196).
Solucion planificada: unit-level scoring + threshold para matched (TODO I0d P2).

### 3. El orchestrator no maneja JSON truncado

Con mundos grandes (14+ nodos) el LLM a veces devuelve JSON truncado en
`design_case`. El orchestrator tiene crash guard (2026-04-06) pero no retry
inteligente. vaca_predict fallo por esto.

### 4. Experimental-control drift

**Rescore controlado (P0) — IMPLEMENTADO (2026-04-06).**
`scripts/rescore.py` permite re-evaluar casos congelados sin regenerar
mundo ni solver. Tres modos: `--reaggregate` (solo aritmetica, sin LLM),
`--rejudge` (re-corre juez de relevancia), `--recompile` (full pipeline).
Persistencia via `score_inputs_v2` en `oi_result.json` y `sub_questions_v2`
en `src.json`. Skill: `/rescore`. Ver `.claude/skills/rescore/SKILL.md`.

---

## Direccion activa

1. ~~**Rescore controlado** (I0d P0)~~ — **DONE.** Skill `/rescore`.
2. ~~**Grammar gap: predicados de subpoblacion** (I0d P1)~~ — **SMOKE-VALIDATED.**
   4 predicados (approx_eq, range, quantile_range, in_set) en `condition_on`.
   Deuda en P1.5 (silent skip, non-numeric guards, in_set sin E2E).
3. **Credit-assignment: unit-level scoring** (I0d P2) — arreglar truth
   dilution y coverage inflada. En 3 pasos incrementales.
4. **P1.5 — Robustez del verifier** (deuda de P1) — silent skip de
   columnas faltantes + non-numeric guards en approx_eq.

---

## Si alguien quiere leer el sistema en orden

1. `CURRENT_STATE.md` — este documento
2. `PROJECT.md` — vision y principios
3. `ARCHITECTURE.md` — referencia tecnica
4. `research/README.md` — indice de investigacion
5. `research/synthesis/sq_v2_matching_spec.md` — spec de SQ v2
6. `src/sreg/models/open_investigation.py` — modelos (v1 + v2)
7. `src/sreg/tools/oi_sq_compiler.py` — compile step v2
8. `src/sreg/tools/oi_sq_matching.py` — matching v2
9. `src/sreg/tools/oi_verifier.py` — verificador (compartido v1/v2)
10. `src/sreg/tools/oi_runner.py` — runtime de episodios

---

## Resumen corto

SREG construye un mundo causal oculto y un problema visible de investigacion.
El solver investiga libremente sobre datasets. Entrega `ClaimCard`s. El sistema
las traduce a `AtomicSpec`s y las verifica exactamente contra el mundo.

Una agenda oculta de sub-questions define que deberia cubrir la investigacion.
Claims se matchean contra esa agenda para medir coverage.

Hoy el path principal (v2) libera las SQs del catalogo de patterns usando bundles de AtomicSpecs directamente y un LLM juez de relevancia. El pipeline E2E ya esta integrado y validado con multiples seeds diversas.
