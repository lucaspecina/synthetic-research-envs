# SREG — Como funciona hoy

> Explicacion end-to-end del sistema tal cual esta implementado.
> Para detalles tecnicos de componentes y contratos: `ARCHITECTURE.md`.
> Para la vision y principios: `PROJECT.md`.
>
> Actualizado: 2026-03-29

---

## Que es SREG

SREG genera **investigaciones sinteticas** con **reward exacto**. Es como
OpenAI Gym pero para razonamiento cientifico: genera entornos donde un agente
tiene que investigar un problema, y computa un score exacto de que tan bien
investigo — sin jueces humanos ni LLM-as-judge.

Otros traen su policy + framework de RL y entrenan contra los entornos de SREG.

---

## La idea central: dos capas

Cada caso tiene dos capas que nunca se mezclan:

**Capa oculta (el SCM):** Un modelo causal estructural — un grafo con ecuaciones
que definen como cada variable causa a las demas. Esta es la "verdad" del mundo.
El solver nunca la ve. Es lo que permite computar rewards exactos.

**Capa visible (lo que ve el solver):** Un brief de investigacion ("investiga por
que las internaciones son desiguales entre hospitales"), datasets con ruido y datos
faltantes, contexto narrativo, y herramientas de analisis. Todo se ve como un
problema de investigacion real.

> **Ejemplo:** El SCM dice que "tratamiento -> recuperacion" con efecto +0.4, pero
> hay un confunder "severidad" que crea la ilusion de que el tratamiento empeora
> las cosas (Simpson's paradox). El solver ve datos crudos donde parece que tratar
> es malo. Tiene que descubrir el confunder y estimar el efecto real.

---

## El flujo completo: de un paper a un score

### Paso 1: Semilla

Todo empieza con un **seed** — puede ser un paper real (PDF o markdown), una
descripcion libre ("marine ecology"), o nada (el sistema inventa). El paper
inspira la problematica pero no se replica.

### Paso 2: Orchestrator disena el caso

Un LLM (el orchestrator) lee el seed y disena un **caso de investigacion**:
- Que variables hay y como se relacionan causalmente (el SCM)
- Un brief de investigacion en lenguaje natural
- Sub-preguntas ocultas que son el criterio real de evaluacion
- Que datos estaran disponibles

> **Ejemplo con un paper de contaminacion del agua:** El orchestrator extrae
> que el paper estudia como la industria afecta la calidad del agua via
> contaminantes. Disena un SCM con 8 variables (industria, contaminante,
> tratamiento, pH, etc.), un brief ("investiga que factores afectan la calidad
> del agua en esta cuenca"), y genera 3 datasets con ruido y missingness.

### Paso 3: Se construye el mundo formal

Las herramientas del sistema construyen:
- El **SCMWorld** con ecuaciones y ruido
- **Datasets realistas** (multiples fuentes, ruido de medicion, datos faltantes)
- El **ResearchProblem** visible (brief + datos + contexto + herramientas)

### Paso 4: El solver investiga

El solver recibe el brief y los datasets. Tiene herramientas:
- **python_exec**: ejecutar codigo (pandas, numpy, scipy, statsmodels, sklearn)
- **think**: razonar en voz alta sin que cuente como accion
- **submit_claims**: entregar sus hallazgos como "claim cards"

El solver NO sabe que hay un SCM detras. NO sabe que patrones se van a evaluar.
Solo ve un problema de investigacion y tiene que decidir que investigar, como
analizarlo, y que concluir.

> **Ejemplo:** El solver recibe datos de agua. Corre correlaciones, nota que
> pH y contaminante estan correlacionados. Hace una regresion, descubre que
> controlando por tratamiento el efecto cambia. Hace 2SLS. Concluye:
> "la industria causa contaminacion con efecto moderado, mediado por
> concentracion de quimicos". Entrega 3 claim cards.

### Paso 5: Compilacion y verificacion

Las claim cards del solver pasan por un pipeline de 3 capas:

1. **Extractor (LLM):** traduce el texto libre de cada claim a una o mas
   intenciones estructuradas (`ClaimIntent`) — que tipo de hallazgo es (efecto
   causal, mediacion, confounding...) y que variables involucra. Claims
   compuestos (ej. "A causa B que causa C") se descomponen en N intenciones.

2. **Compiler (deterministico):** convierte cada intencion a un `CompiledUnit`
   con specs ejecutables contra el SCM. Usa una gramatica composable (~24
   piezas atomicas que se combinan en cientos de verificaciones posibles).
   La salida (`CompilerOutput`) tiene una lista de units y un status
   (`compiled` / `partial` / `abstention`).

3. **Verifier (deterministico):** ejecuta las specs de cada unit contra el SCM
   via Monte Carlo. Produce un resultado numerico exacto — true/false con
   magnitud. El scoring se computa per-unit y luego se agrega.

> **Ejemplo:** El solver dice "la industria causa contaminacion". El extractor
> identifica: patron=causal_effect, causa=industria, efecto=contaminacion.
> El compiler genera un CompiledUnit con spec: "simular industria alta vs baja,
> medir contaminacion, comparar medias". El verifier ejecuta 100K samples en el
> SCM y dice: "si, efecto significativo de +2.3 unidades, el claim es correcto".

### Paso 6: Scoring

El score final combina:
- **Correctness:** que tan verdaderos son los claims (verificado contra SCM)
- **Coverage:** cuanto del problema cubrio (basado en sub-preguntas ocultas)
- **Efficiency:** no spamear claims a ver si pega

El resultado es un **reward signal exacto** que puede usarse para RL.

---

## Open Investigation — el unico modo

El solver recibe un brief abierto y tiene libertad total. Entrega claim cards
con sus hallazgos. El sistema compila y verifica contra el SCM.

No hay modo "guided" ni preguntas predefinidas. Todo el codigo legacy (BN
discreta, EpisodeRunner, guided tasks, research actions con budget) fue
eliminado del repo.

---

## La verdad oculta: el SCM

Un SCM (Structural Causal Model) es un grafo causal con ecuaciones. Cada nodo
es una variable, cada flecha dice "A causa B", y la ecuacion dice como.

```
industria -> contaminante: contaminante = 0.6 * industria + normal(0, 1)
contaminante -> pH:        pH = 7.0 - 0.3 * contaminante + normal(0, 0.5)
```

Con esto el sistema puede:
- **Samplear datos** observacionales (con ruido, missingness, outliers)
- **Intervenir**: "que pasa si forzamos industria=0?" (do-calculus)
- **Verificar claims**: "es verdad que industria causa contaminacion?" -> si, efecto +2.3
- **Computar mediacion**: "cuanto del efecto pasa por contaminante vs directo?"
- **Detectar interacciones**: "el efecto cambia segun el nivel de tratamiento?"

Todo esto es **deterministico dado el seed** — no hay LLM judge involucrado.

Las variables son continuas con unidades reales (celsius, mL/kg, USD, etc.).
Los datasets tienen ruido de medicion (~5%), datos faltantes (MAR ~5%), y
multiples fuentes de distinta calidad.

---

## Lo que ve y hace el solver

El solver recibe:
- **Research brief**: encargo de investigacion en lenguaje natural
- **Datasets**: 1-3 tablas con datos (en OI se acceden via el catalogo de artefactos;
  en guided mode se pre-cargan como `df`, `df_1`, `df_2`)
- **Contexto**: narrativa del dominio, descripcion de variables
- **Herramientas**: python_exec (con pandas, numpy, scipy, statsmodels, sklearn),
  think (razonamiento interno), submit_claims (entregar hallazgos, 1-5 claims)

El solver **NO ve**:
- El SCM (la verdad oculta)
- Las sub-preguntas de evaluacion
- Los patrones o categorias de scoring

Principio fundamental: **el solver investiga libre, sin saber como va a ser
evaluado**. Si le decimos que busque "efectos causales" o "mediaciones", lo
estamos sesgando.

---

## Como evaluamos SREG

### Nivel 1: Tests del codigo

`pytest tests/ -v` — verifican que el codigo funciona, no que el sistema
produzca buenas investigaciones.

### Nivel 2: Evaluacion de entornos (lo mas importante)

Generar SRCs reales con LLM y evaluarlos:
- **Cuantitativo**: metricas automaticas (scores, submission rate, baselines)
- **Cualitativo**: leer los casos generados con rubrica + descubrimiento abierto
- **No-data baseline**: darle el brief a un LLM SIN datos. Si responde bien, el
  caso no fuerza investigacion — es un test critico.

### Nivel 3: Transfer benchmark (futuro)

Entrenar una policy con entornos SREG y medir si mejora en benchmarks externos
(CLadder, QRData, DiscoveryBench). No implementado aun — es el test definitivo.

---

## Que falta (limitaciones honestas)

- **El compiler LLM extraction es el bottleneck**: el multi-unit compiler (A22)
  resolvio la abstention rate descomponiendo claims compuestos en N units. Pero
  la calidad de extraccion LLM sigue siendo el cuello de botella — chain claims
  no extraen todas las relaciones pairwise, y conclusiones indirectas se pierden.

- **Submission aversion (mitigada)**: el solver a veces investiga bien pero no
  entrega sus claims a tiempo. Mitigacion S02: force-submit da al solver un turno
  extra con SOLO `submit_claims` disponible si agota iteraciones sin submittear.
  Funciona en la mayoria de los casos pero es solucion temporal.

- **Preguntas no data-indexed**: algunas preguntas se pueden responder sin mirar
  los datos (desde conocimiento general). Esto es un problema del guided mode;
  OI lo mitiga parcialmente pero no del todo.

- **SCM rejection sampling**: escala mal con muchas variables de evidencia (>5).
  Futuro: importance weighting.

---

## Como ejecutar

```bash
conda activate sreg

# Generar un SRC desde un paper
python scripts/generate_src.py --seed-file seeds/paper.pdf -o output/ --inspect

# Generar con OI (investigacion abierta)
python scripts/generate_src.py --seed-file seeds/paper.pdf -o output/ --oi

# Generar desde un goal libre
python scripts/generate_src.py --goal "marine ecology" -o output/ --inspect

# Tests
pytest tests/ -v

# Benchmarks externos
python scripts/run_benchmark.py -b cladder --subset dev
```
