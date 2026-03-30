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
>
> Actualizado: 2026-03-30

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

Lo importante es que el score no viene de un juez humano ni de un LLM-as-judge.
Viene de una verdad formal oculta: el **SCM**.

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
| `EpisodeTrace` | Log estructurado de lo que hizo el solver | `models/open_investigation.py` | Sirve para provenance y warrant |
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
- `oi.corr(...)`, `oi.regress(...)`, `oi.stratify(...)`, etc.
- `submit_claims(...)`

Cada vez que carga un artefacto o corre analisis, el runner lo registra en
`EpisodeTrace`.

Eso es importante por dos motivos:

- permite reconstruir que hizo realmente el solver;
- y habilita el sistema de `warrant` / evidencia, aunque hoy no sea el score
  principal del path de sub-questions.

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

En los E2E actuales, el score principal es el de sub-questions.

Pipeline:

```text
compiled claim units + resolved sub-questions
  -> score_claim_vs_subquestion(...)
  -> SubQuestionScore por SQ
  -> EpisodeSubQuestionScore final
```

### Matching claim vs SQ

Para cada claim compilada y cada SQ resuelta, el sistema calcula que tan bien
esa claim satisface esa SQ.

Usa principalmente:

- compatibilidad estructural entre roles/patterns;
- compatibilidad de respuesta (`sign`, `existence`, `rank_order`, etc.);
- y la verdad del claim verificada contra el SCM.

### Componentes del score actual

El output principal es `EpisodeSubQuestionScore`, con:

- `coverage`: fraccion de SQs con alguna claim que las satisface
- `weighted_coverage`: lo mismo, pero ponderado por `tier`
- `correctness`: verdad promedio de las claims que matchearon alguna SQ
- `novel_bonus`: bonus por hallazgos verdaderos que no encajaban en ninguna SQ
- `total`: score final del episodio

La formula actual es:

```text
total = weighted_coverage * 0.70
      + correctness * 0.20
      + coverage * 0.10
      + novel_bonus
```

con cap en `1.0`.

### Algo importante: no todo el viejo scoring esta en el path principal

En el repo todavia existen conceptos como:

- `EpisodeScore`
- `ClaimVerdict`
- `SalienceFamily`
- `warrant`
- `efficiency`

pero hoy eso pertenece sobre todo al path v2 / diagnostico con salience map.

En cambio, el **path principal** de los E2E recientes usa:

- `SubQuestionIntent`
- `ResolvedSubQuestion`
- `EpisodeSubQuestionScore`

Esto importa porque si uno lee rapido el repo, puede pensar que `warrant` y
`efficiency` son el score principal actual. Hoy no lo son.

---

## El sistema de warrant: que es y donde entra hoy

`warrant` intenta responder una pregunta distinta de "esto es verdad?".

Pregunta:

- "El solver llego a esta claim investigando de verdad, o la tiro desde priors?"

Para eso usa `EpisodeTrace`:

- que artefactos cargo;
- en que paso;
- que columnas uso;
- que tipo de analisis corrio;
- y si eso paso antes de submittear la claim.

Ese sistema existe, esta bastante trabajado, y vive en:

- `src/sreg/tools/oi_warrant.py`

Pero es importante entender el estado actual:

- existe como mecanismo serio de evidencia/provenance;
- forma parte del path de scoring diagnostico;
- pero no es la pieza central del score de sub-questions usado en la ronda
  E2E mas reciente.

O sea: no esta "muerto", pero tampoco es hoy el centro del reward principal.

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

## Los bottlenecks actuales, sin maquillarlos

### 1. La extraccion LLM sigue siendo fragil

El extractor mejoro, y ahora recibe mas contexto del caso:

- titulo
- dominio
- brief
- descripcion
- descripciones de variables
- sub-questions visibles para el compiler

Pero sigue habiendo fallas tipicas:

- claims compuestas que se comprimen demasiado;
- rankings extraidos sin los atoms pairwise que tambien estaban implicados;
- conclusiones metodologicas o epistemologicas que no entran bien en los 8 patterns.

### 2. El sistema sigue sesgado a causal simple

Este es probablemente el hallazgo mas importante de la ronda actual.

El sesgo a causal simple no aparece solo porque el extractor LLM sea flojo.
Aparece porque dos cosas distintas siguen pasando por una IR estrecha:

- las claims del solver;
- y las sub-questions ocultas.

Hoy la gramatica atomica es mucho mas rica que el catalogo actual de patterns,
pero en la practica seguimos obligando gran parte del sistema a hablar en:

- `causal_effect`
- `mediation`
- `heterogeneity`
- `confounding`
- etc.

Eso funciona bien en casos textbook.
Funciona peor en casos:

- epistemologicos;
- metodologicos;
- de identificabilidad;
- de estabilidad entre datasets;
- o de system mapping menos causal-simple.

### 3. Las SQ hoy no son grammar-first

Este es el punto central de A23.

Aunque ya tengamos `AtomicSpec`, las SQ todavia se representan como:

- `pattern + roles + ask`

y solo despues se convierten a specs.

Eso significa que la propia answer key del sistema ya viene recortada por el
catalogo conocido.

### 4. Matching y scoring todavia dependen demasiado de pattern

Incluso cuando el solver dice algo razonable, el matching puede premiar una
claim mas broad en vez de una claim mas semantica y especifica.

Esto aparecio con claridad en los casos de confounding y en los casos donde
una claim de ranking se comia relaciones pairwise mas precisas.

### 5. Warrant aun no esta plenamente integrado al path principal

La capa de evidencia/provenance existe y es util.
Pero el reward principal actual no la explota al maximo.

Todavia hay trabajo para unificar:

- verdad;
- cobertura;
- relevancia;
- y evidencia real del proceso de investigacion.

---

## Entonces, cual es la arquitectura conceptual correcta hoy?

La forma mas sana de pensar el sistema actual es esta:

### Lo que ya esta bien encaminado

- mundo oculto formal (`SCMWorld`)
- problema visible realista (`ResearchProblem`)
- solver libre (`Open Investigation`)
- verificacion exacta (`AtomicSpec` + verifier)

### Lo que hoy esta demasiado angosto

- la IR intermedia de claims (`ClaimIntent`)
- la IR intermedia de sub-questions (`SubQuestionIntent`)

### La tension central actual

No falta un mejor verificador.
No falta mas Monte Carlo.
No falta inventar 50 patterns nuevos.

Lo que falta es dejar de preguntar:

- "que pattern es esto?"

y empezar a preguntar mas seguido:

- "que atoms hacen falta para verificar esta conclusion?"

Ese cambio vale tanto para:

- claims del solver;
- como para sub-questions.

---

## Direccion activa hoy

La direccion de trabajo abierta despues de A23 es:

1. **SQ grammar-first**
   Las SQ deberian acercarse mas a bundles de `AtomicSpec` o a una receta
   composicional equivalente, en vez de depender tanto de `pattern + roles + ask`.

2. **Compiler hibrido para claims**
   Mantener los `patterns` como fast-path cuando calzan bien, pero agregar
   fallback directo a gramatica atomica cuando no calzan.

3. **Matching mas semantico**
   Menos dependencia de pattern fijo, mas compatibilidad entre bundles de
   verificacion, variables, assertions y tipo de conclusion.

4. **Formalizacion extra de claims**
   Puede servir como mitigacion, pero por ahora NO es la prioridad principal.

---

## Si alguien quiere leer el sistema en orden

Este es un orden recomendable para navegar el repo sin perderse:

1. `CURRENT_STATE.md`
2. `PROJECT.md`
3. `ARCHITECTURE.md`
4. `research/README.md`
5. `src/sreg/models/open_investigation.py`
6. `src/sreg/tools/oi_runner.py`
7. `src/sreg/tools/oi_extraction.py`
8. `src/sreg/tools/oi_compiler.py`
9. `src/sreg/tools/oi_subquestions.py`
10. `src/sreg/tools/oi_verifier.py`

Y para entender la discusion activa:

11. `research/notes/a22_compiler_direct_to_atomicspec.md`
12. `research/notes/a23_grammar_first_sq_and_compiler.md`

---

## Resumen corto

Si hubiera que resumir todo el sistema actual en pocas lineas:

- SREG construye un mundo causal oculto y un problema visible de investigacion.
- El solver investiga libremente sobre datasets, no sobre el SCM.
- Al final entrega `ClaimCard`s.
- El sistema traduce esas claims a `ClaimIntent`, luego a `AtomicSpec`, y las
  verifica exactamente contra el mundo.
- Ademas resuelve una agenda oculta de `SubQuestionIntent`s para medir coverage.
- El score principal actual sale de ese matching claim-vs-subquestion.
- El verifier formal (`AtomicSpec`) ya es bastante rico.
- El cuello actual esta antes: claims y SQs siguen demasiado atadas a un
  catalogo estrecho de patterns conocidos.

Ese es el estado real del sistema hoy.
