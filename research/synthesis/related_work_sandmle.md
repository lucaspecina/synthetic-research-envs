# SandMLE — analisis y comparacion con SREG

> **Status:** Related work consolidado. Referencia obligada para paper / tesis.
> **Fecha:** 2026-04-07
> **Paper:** Zhou et al. 2026, "Synthetic Sandbox for Training Machine
> Learning Engineering Agents", arXiv:2604.04872v1 (CC-BY 4.0).
> **Conecta con:** `sreg_training_transfer_protocol.md`,
> `thesis_evaluation_framework.md`, `oi_scoring_fundamentals.md`,
> `PROJECT.md`.

## Por que este paper importa para SREG

SandMLE es el primo mas cercano que SREG tiene en la literatura
contemporanea. Resuelve un problema **estructuralmente paralelo** (entrenar
agentes con RL en dominios donde la verificacion es cara) con una
**arquitectura paralela** (entornos sinteticos con ground truth
programatico, generados por un pipeline multi-agente desde seeds minimos).

Para SREG esto importa por tres razones:

1. **Validacion externa de la vision.** Un equipo independiente llego al
   mismo Translator pattern desde un problema completamente distinto. No
   estamos solos creyendo que esta es la forma de habilitar RL agentico
   en dominios con verificacion costosa.
2. **Referencia obligada en related work.** Cuando se escriba el paper de
   SREG, SandMLE es la cita primaria a la que hay que posicionarse: SREG
   es la contraparte para investigacion cientifica de lo que SandMLE es
   para ML engineering.
3. **Espejo para nuestras decisiones.** Donde ellos resolvieron un
   problema, podemos reusar el approach. Donde ellos simplificaron,
   podemos justificar por que SREG es mas dificil y necesita estructuras
   adicionales.

## Resumen ejecutivo del paper

**Autores:** Zhou, Zhang, Wu, Liu, Fan, Zhao, Yan (2026).

**Problema:** Entrenar agentes para ML engineering con RL trajectory-wise.
A diferencia de SWE (donde un unit test corre en segundos), MLE requiere
entrenar un modelo desde cero en cada intento (~196s por intento en
promedio). Esto hace RL on-policy prohibitivamente lento.

**Insight central:** "MLE latency is overwhelmingly driven by dataset
size". Si se constrina cada tarea a 50-200 muestras, el tiempo por
intento baja a ~14s — un **13x speedup** que habilita trajectory-wise
RL en MLE por primera vez.

**Pipeline de generacion (4 agentes orquestados):**

1. **Data Strategist** — extrae "Task DNA": un schema matematico
   (modalidad, resolucion, cardinalidad de etiquetas) **stripped de
   contexto semantico**. Define la regla oculta `H: l = f(z) + epsilon`
   que conecta features con labels. Aplica "Domain Attribution" para
   reasignar la tarea a un dominio nuevo. Inyecta ruido adversarial.
2. **ML Developer** — escribe Python que sintetiza el dataset siguiendo
   `H` deterministicamente, particiona train/test, entrena baselines, y
   calcula thresholds progresivos `S = {s_1, ..., s_k}` a partir de los
   baselines.
3. **MLOps Engineer** — construye un evaluador con metrica hardcoded
   `M`, direccion de optimizacion, y los thresholds `S`. Loop de
   verificacion ejecutiva: si el script falla, vuelve al agente para
   debugging iterativo.
4. **Technical Writer** — redacta la narrativa del problema en el
   dominio nuevo, sin filtrar la verdad oculta.

**Sanity verification (clave del approach):** una tarea es valida solo
si los thresholds son monotonicamente ordenados:

```
Si I=1 (lower is better): s_1 < s_2 < ... < s_k AND s_1 < s_sample
Si I=0 (higher is better): s_1 > s_2 > ... > s_k AND s_1 > s_sample
```

Tareas que no cumplen son "automatically discarded from the training
curriculum, ensuring RL agent only optimizes against valid, monotonic
reward signals". Tasa de descarte reportada: 1200 → 1119 → 1106 → 912
(76% yield final).

**Diversidad reportada (60 seeds → 848 tareas de training, ~14x):**
- **Dominios:** Healthcare 25%, Retail 18%, Manufacturing 14%, IT 13%,
  Transportation, Finance, Science.
- **Modalidades:** Image 49%, Tabular 25%, Text 10%, Multi-modal 10%,
  Graph 4%, Audio 2%.
- **Task types:** Classification 56%, Regression 15%, Ranking 3%,
  Forecasting+Reconstruction 26%.

**Reward function (dense, multi-componente):**

```
r = 0.1 * r_format + 0.3 * I_execute + 0.1 * I_median
    + 0.2 * I_bronze + 0.2 * I_silver + 0.1 * I_gold
```

- `r_format`: ratio de pasos generados que usan tags de razonamiento
  requeridos (continuo en [0,1]).
- `I_execute`, `I_median`, `I_bronze`, `I_silver`, `I_gold`: indicadores
  binarios sobre milestones progresivos.
- Pesos suman 1.0.

**Resultados principales:**
- **Medal rate relativo:** +20.3% a +66.9% vs SFT baselines, en
  Qwen3-8B / 14B / 30B-A3B.
- **Generalizacion:** hasta +32.4% en HumanRank en MLE-Dojo (benchmark
  externo, fuera de la distribucion de training).

**Limitaciones reportadas:**
- Test-time scaling se traba por context window overflow en horizonte
  largo: el agente cae en loops repetitivos.
- Alta varianza entre scaffolds (AIRA causa degradacion vs AIDE);
  "generalization remains framework-dependent".

## Coincidencias estructurales con SREG

### El Translator pattern, con otro nombre

El hallazgo mas fuerte de la comparacion: SandMLE descubrio
independientemente la misma arquitectura central que SREG.

| SandMLE | SREG | Que comparten |
|---|---|---|
| **Data Strategist** — extrae Task DNA, define `H: l = f(z) + epsilon` | Generador de **SCM** (DAG + ecuaciones) | Verdad matematica pura, sin semantica |
| **ML Developer** — sintetiza dataset deterministico desde `H` | **Compiler** (SCM → datos observados) | Datos derivados de la verdad oculta |
| **MLOps Engineer** — evaluador con metrica hardcoded `M` | **Verifier + scoring** | Scoring programatico, no LLM-judge |
| **Technical Writer** — narrativa del problema en dominio | Generador de **brief** | Envoltorio narrativo separado |

Esto es exactamente el principio operativo de SREG: **la verdad
matematica vive separada del envoltorio narrativo, y se mantiene
escondida del solver**. Que dos equipos hayan llegado al mismo diseno
desde problemas distintos es validacion fuerte del patron.

### Otras coincidencias relevantes

1. **Programmatic ground truth (NO LLM-judge en scoring core).** Coincide
   con nuestro Principio No-Negociable de scoring: "la verificacion es
   matematica contra el SCM". En SandMLE la verdad es la funcion oculta
   `H`; en SREG es un SCM con DAG y ecuaciones. Ambos rechazan jueces
   LLM en el loop de verificacion.
2. **Multi-agent generation con roles especializados.** Ambos usan LLMs
   orquestados con responsabilidades distintas para generar el
   environment.
3. **Sanity verification con descarte explicito.** SandMLE descarta 24%
   de tareas malformadas (1200 → 912). SREG descarta SRCs cuyo verifier
   rechaza claims fundamentales. Mismo patron, distinto check.
4. **Diseno FOR RL, no benchmark estatico.** Ambos papers explicitan
   que el goal es habilitar entrenamiento, no rankear modelos
   existentes.
5. **Seeds → amplificacion.** SandMLE: 60 seeds → 848 tareas (14x).
   SREG: un seed paper → N SRCs distintos via compiler.
6. **Reward denso multi-componente con pesos.** Misma filosofia que
   `truth/relevance/coverage/no-spam` de SREG, aunque con componentes
   distintos.
7. **Verification cost como diseno principal.** Ambos disenan
   explicitamente para que la verificacion sea barata: SandMLE comprime
   datasets; SREG verifica contra SCM sin correr ML.

## Divergencias fundamentales (triple filtro de CLAUDE.md)

Aplicando los tres filtros que SREG usa para evaluar cualquier diseno,
SandMLE **falla los tres** desde la perspectiva de investigacion
cientifica. Esto no es critica del paper — su objetivo es otro. Es la
delineacion clara del scope que separa los dos proyectos.

### Filtro 1: ¿Se parece a investigacion real?

**SandMLE: NO.** El agente recibe `(X, y)` y debe entrenar un modelo
predictivo. Nunca pregunta "¿que causa que?", "¿que es relevante para
el brief?", "¿hay confounding?", "¿la pregunta esta bien formulada?",
"¿que tendria que medir despues?". Es **ML engineering**, no ciencia.

**SREG: si (intencionalmente).** El brief es libre, el solver decide
que investigar, descompone preguntas vagas, genera hipotesis, decide
cuando parar. Es exactamente lo que un investigador humano hace.

### Filtro 2: ¿Crea presion evolutiva para juicio cientifico?

**SandMLE: NO.** Su scoring presiona hacia **iterar pipelines de ML
hasta superar baselines de Kaggle**. Un agente perfecto en SandMLE sabe
optimizar AUC/F1 — no investigar, no generar hipotesis rivales, no
saber cuando parar.

**SREG: ese es el objetivo central.** PROJECT.md "Presiones evolutivas"
lista 16 propiedades que SREG debe forzar: anti-overexcitement,
hipotesis rivales, no driftear a familiar, refinamiento ante evidencia
parcial, doble vision macro/detalle, separar evidencia de priors, etc.
El test es: "¿un agente sin la propiedad X obtiene en promedio score
mas bajo?" — y para cada propiedad de juicio cientifico, SandMLE no
crea esa presion porque sus tareas son optimizacion sobre metrica
conocida.

### Filtro 3: ¿Funciona para tipos diversos de investigacion?

**SandMLE: NO.** Su "diversidad" es de **dominio** (healthcare, retail,
manufacturing) y de **modalidad** (image, tabular, text). Pero todos
sus **tipos de task** son predictive supervised: classification (56%),
regression (15%), ranking (3%), forecasting+reconstruction (26%).
**Cero cobertura** de los 23 escenarios de
`investigation_scenarios_rubric.md`: system mapping, structure
discovery, descriptivo, epistemologico, multi-outcome, mediacion,
identificabilidad, etc.

**SREG: ese es un requisito de diseno.** El scoring debe funcionar
uniformemente para todos los tipos. Cualquier "scoring profile" por
tipo viola el Principio No-Negociable #1 ("UN solo metodo de scoring
para todo").

### Bonus: violacion del principio "no construir un juego"

El reward de SandMLE es:

```
r = 0.1 * format + 0.3 * execute + 0.1 * median + 0.2 * bronze
    + 0.2 * silver + 0.1 * gold
```

Esto es **exactamente el "scoring profile" hardcoded** que SREG rechaza
por diseno (Principio No-Negociable #4: "no construir un juego
estructurado"). SandMLE puede hacerlo porque sus tareas son homogeneas:
todas son optimization-against-leaderboard. SREG no puede porque
"system mapping" o "epistemologica" no tienen un Bronze/Silver/Gold
equivalente.

### El hidden rule es un primo pobre del SCM

SandMLE define la verdad oculta como `H: l = f(z) + epsilon`. Esto es
**una funcion de mapping** features-a-label. No tiene:

- DAG ni estructura causal explicita.
- do-operator ni intervenciones.
- Confounding ni mediacion.
- Contrafactuales.
- Identificabilidad en sentido formal.

El SCM de SREG tiene todo eso. La verdad de SandMLE alcanza para
evaluar "¿el modelo predice bien?". La verdad de SREG alcanza para
evaluar "¿el agente entendio el sistema causal?". **La diferencia no es
estilistica — es la diferencia entre ML y ciencia.**

## Lo que rescatamos para SREG

En orden de utilidad concreta:

### 1. Framing explicito del bottleneck de verificacion para RL

SandMLE articula clarisimamente algo que en SREG estaba implicito: **si
queres RL trajectory-wise, la verificacion tiene que costar segundos,
no minutos**. En su caso, comprimen datasets; en el nuestro, la
SCM-based verification es barata por construccion porque el SCM
responde queries sin entrenar modelos.

**Accion concreta:** dejarlo explicito en `PROJECT.md` o
`oi_scoring_fundamentals.md`. "Verificamos contra el SCM, sin correr
ML, **porque eso permite RL trajectory-wise**. Una verificacion que
requiera correr modelos es incompatible con RL barato."

### 2. Reportar yield rate del compiler

SandMLE reporta 1200 → 1119 → 1106 → 912 en su pipeline (24% descarte).
Es una metrica de salud del generador.

**Accion concreta:** trackear en CURRENT_STATE.md o en analisis de
pilotos:

- # SRCs generados por el compiler.
- # SRCs que pasan el verifier.
- # SRCs que sobreviven a oi_subquestions matching.
- Yield rate final.

Si el yield sube mucho, el verifier es demasiado laxo (esta dejando
pasar SRCs malformados). Si baja mucho, el orchestrator esta fallando
y hay que diagnosticar.

### 3. Sanity check de monotonicidad / smoothness del reward landscape

SandMLE valida que `s_1 < s_2 < ... < s_k`: los thresholds tienen un
gradiente util de dificultad. Tareas sin gradiente se descartan.

**Accion concreta para SREG:** un check analogo en el verifier — para
cada SRC generado, verificar que las sub-questions tienen gradiente
util de dificultad (que las claims faciles puntuan distinto que las
dificiles). Es la version sub-question del `investigation_gap` que ya
tenemos en `notes/oi_investigation_gap.md` y deberiamos formalizar
como gate.

### 4. Domain Attribution sistematico

SandMLE toma **un Task DNA** y lo re-narra en healthcare, retail,
manufacturing — 7 dominios desde el mismo schema matematico. Es una
forma barata de amplificar diversidad sin tocar la verdad.

**Accion concreta:** podemos hacer lo mismo con SCMs. Tomar **un SCM**
y generar N briefs distintos en dominios distintos. Diversidad barata
sin tocar la verdad matematica. Util para data augmentation en SFT y
para reducir overfitting al lexico de un dominio.

### 5. Multi-agent roles mas explicitos en el orchestrator (futuro)

Hoy nuestro orchestrator es bastante monolitico. SandMLE muestra que
**separar la generacion en roles claros** (Strategist / Developer /
MLOps / Writer) hace la pipeline mas debuggeable y especializable.

**Accion concreta (no inmediata):** considerar separar el orchestrator
en agentes con responsabilidad especifica si en algun momento la
calidad del compiler se vuelve un bottleneck. NO sumar complejidad por
sumarla — solo si el monolito empieza a doler.

### 6. Test-time context overflow como riesgo conocido

SandMLE reporta que en horizonte largo el agente se traba en loops por
overflow del context window. **SREG va a tener exactamente este
problema** cuando los OI runs sean largos. Su limitacion mas honesta
es nuestra limitacion futura.

**Accion concreta:** medirlo desde el inicio. Tracking de "el agente
sigue progresando en el turno N o esta repitiendo?". Tener una
eviction strategy razonable. Disenar el agente con tolerancia a
contexto comprimido.

## Lo que NO copiamos (y por que)

1. **Reward dense con thresholds Kaggle.** Viola Principio
   No-Negociable #1 (un solo metodo de scoring para todo) y #4 (no
   construir un juego). Funciona para SandMLE porque sus tareas son
   homogeneas.
2. **Metrica anclada a leaderboard externo.** SREG verifica contra el
   SCM, no contra una referencia humana. Mas limpio, mas generalizable,
   mas dificil de hacer bien.
3. **Reducir la tarea a "optimizar metrica conocida".** Esto destruye
   la capacidad del entorno de ensenar formacion de preguntas, decision
   sobre que medir, descomposicion. Es el unico cambio que NO podemos
   hacer sin convertirnos en SandMLE.
4. **Hidden rule como funcion supervised.** Mantenemos SCM con
   causalidad completa porque queremos ensenar epistemologia, no ML.

## Como evaluan ellos (para alinear nuestro transfer protocol)

Esta seccion es la mas relevante para
`sreg_training_transfer_protocol.md` y para el setup BEFORE/AFTER de
nuestra tesis.

### Metricas

Jerarquia progresiva (cada nivel es % de tareas donde el agente
cumple):

| Metrica | Que mide |
|---|---|
| **Valid Submission** | El output parsea y tiene schema correcto. Floor de competencia. |
| **Above Median** | Score > p50 del leaderboard humano. Threshold suave. |
| **Bronze / Silver / Gold** | Cumple el threshold respectivo del leaderboard de Kaggle. |
| **Any Medal** | Union de Bronze/Silver/Gold. **Metrica primaria.** |

Adicional:

- **HumanRank Score** (en MLE-Dojo): generalizacion fuera de la
  distribucion de training.

### Setup de experimento

- **Modelos base:** Qwen3-8B, Qwen3-14B, Qwen3-30B-A3B.
  *(Nota: nuestro `transfer_protocol.md` ya eligio Qwen3-8B. SandMLE
  valida empiricamente que ese tamano es entrenable y produce mejoras
  significativas.)*

- **Tres variantes entrenadas (importante para nuestro protocolo):**

  | Variante | Que es | Por que importa |
  |---|---|---|
  | **Seed-SFT** | SFT-only sobre trayectorias de Claude-4.5-Sonnet generadas para los 60 seeds | Baseline contra el que se compara la mejora de RL |
  | **SandMLE** | RL directo (GRPO trajectory-wise) **desde el base**, sin SFT previo | La variante principal del paper |
  | **SFT-SandMLE** | GRPO inicializando desde Seed-SFT (SFT + RL) | Variante hibrida; **NO es la que generaliza mejor** |

- **Train environment:** 848 tareas sinteticas SandMLE.
- **Eval environments:** MLE-bench-lite (in-domain proxy) y MLE-Dojo
  (out-of-distribution transfer).

### Hallazgo clave: SFT-only colapsa fuera del scaffold de generacion

Esta es la observacion mas importante del paper para nuestro protocolo:

> *"the SFT models prove brittle when deployed outside the specific
> scaffold used during their data generation, most notably collapsing to
> a 17.7% Valid Submission rate on MLE-Dojo for the 30B model"*

En contraste, **SandMLE (RL desde base) mantiene 83.9% valid submission**
en el mismo benchmark. La diferencia es brutal: SFT-only memoriza el
scaffold, RL aprende algo mas transferible.

**Implicacion directa para nuestro `transfer_protocol.md`:** hoy listamos
`SFT + RL` como training v1. SandMLE sugiere que **deberiamos al menos
tambien evaluar RL-from-base como variante**, porque puede ser la que mas
generalice a los benchmarks externos. Esto NO invalida SFT+RL — pero abre
una pregunta empirica que vale correr: ¿en SREG, SFT ayuda al RL o lo
contamina? Hay que medirlo.

### Resultados que reportan

- **Medal rate relative improvement:** +20.3% a +66.9% across model
  sizes vs SFT-only.
- **HumanRank en MLE-Dojo:** hasta +32.4% — evidencia de generalizacion
  real fuera de la distribucion sintetica.
- **Test-time scaling:** mejora con mas compute hasta cierto punto,
  despues degrada por context overflow.

### Limitaciones que reportan honestamente

1. **Context window overflow** en horizonte largo → loops repetitivos.
   Bottleneck del effective context length del modelo.
2. **Alta varianza entre scaffolds** (AIRA causa degradacion vs AIDE).
   "Generalization remains framework-dependent".

## Implicaciones para el paper de SREG

### Posicionamiento sugerido

SandMLE es la cita central a la que SREG debe diferenciarse en related
work. Borrador de framing:

> "Recent work has shown that synthetic environments with programmatic
> ground truth can enable trajectory-wise RL training of agentic
> capabilities in domains where real-world verification is prohibitive
> (Zhou et al. 2026, SandMLE). SandMLE applies this insight to ML
> engineering, where the bottleneck is dataset training time. SREG
> applies the same insight to scientific investigation, where the
> bottleneck is the verifiability of research conclusions. Both
> projects converge on a 'Translator pattern' — separating mathematical
> truth from narrative presentation — but differ fundamentally in what
> they measure: SandMLE measures predictive performance against a known
> metric; SREG measures research quality against a structural causal
> model."

### Diferenciador clave a defender en el paper

Ellos verifican contra `H: l = f(z) + epsilon` (mapping supervised).
Nosotros verificamos contra un SCM (causalidad, contrafactuales,
confounding, identificabilidad). Esa diferencia no es cosmetica — es lo
que nos permite ensenar **juicio epistemologico** en vez de **iteracion
de pipelines de ML**.

### Validacion empirica que tomamos prestada

SandMLE es **evidencia empirica de que el approach funciona**:
sintetico + programmatic GT + RL trajectory-wise produce +20-67%
relative en medal rate y +32% en transfer a benchmarks externos. Esto
es la primera prueba publica de que la idea es viable.

Para nosotros, esto:

- **Eleva la barra:** vamos a tener que mostrar mejoras de magnitud
  comparable.
- **Baja el riesgo del approach base:** no tenemos que defender que
  "synthetic env + programmatic GT + RL" funciona en abstracto — ya
  esta probado. Solo tenemos que defender que escala a un dominio mas
  dificil (investigacion abierta).

### Lo que tenemos que probar nosotros (que ellos no necesitan probar)

- Que el approach **escala a investigacion abierta** (no solo a tareas
  con metrica conocida).
- Que el reward de SREG **crea presion para juicio cientifico**, no
  solo para ejecucion correcta de pipelines.
- Que la transferencia de SREG-trained a benchmarks de investigacion
  reales (CLadder, QRData, DiscoveryBench, CausalReasoningBenchmark,
  SciGym) **es positiva**, no neutra.

### Reabrir la decision SFT+RL vs RL-only

El protocolo actual lista `SFT + RL` como training v1. SandMLE muestra
empiricamente que en su dominio:

- SFT-only colapsa en transfer (17.7% valid submission).
- RL-only desde base es la variante que mas generaliza (83.9%).
- SFT+RL existe como variante hibrida pero **no es la que reportan como
  primaria**.

Esto no invalida nuestra eleccion, pero **obliga a tratarla como
hipotesis a validar**, no como decision cerrada. Tres opciones abiertas:

1. **Mantener SFT+RL como v1** (asumir que SREG es lo suficientemente
   distinto a SandMLE como para que el patron no se replique).
2. **Cambiar a RL-from-base como v1** y SFT+RL como ablacion.
3. **Correr ambas en paralelo** y dejar que la data decida. Es la mas
   honesta pero la mas cara.

Recomendacion personal: **opcion 3 si el costo lo permite, opcion 2 si
no**. La razon es que el riesgo asimetrico apunta a RL-from-base: si
SREG-via-SFT memoriza nuestro scaffold de generacion (compiler + sub
questions + claim format), va a colapsar en transfer exactamente como
Seed-SFT colapso en MLE-Dojo. Y los benchmarks externos no comparten
nuestro scaffold.

## Open questions para el equipo

1. **Yield rate.** ¿Implementamos tracking explicito en la pipeline?
   ¿Donde lo reportamos?
2. **Domain Attribution.** ¿Vale la pena un experimento corto generando
   N briefs desde un mismo SCM y midiendo si la diversidad ayuda al
   training?
3. **Smoothness check.** ¿El analogo de la monotonicidad de SandMLE
   para nuestras sub-questions vale como gate del compiler?
4. **Context overflow.** ¿En que punto del scale-up de OI vamos a
   chocar con esto? ¿Disenamos contra eso desde el inicio?
5. **Eval transfer alineado.** Nuestro `held-out SREG / CLadder /
   QRData / DiscoveryBench` es estructuralmente analogo al
   `MLE-bench-lite / MLE-Dojo` de ellos. ¿Vale formalizar esa simetria
   en el paper?
6. **Reporte de resultados.** ¿Adoptamos la convencion de reportar
   "relative improvement vs SFT baseline" como hace SandMLE? Es una
   metrica facil de comparar entre papers.

## Referencia

Zhou, Y., Zhang, L., Wu, Y., Liu, J., Fan, X., Zhao, Z., & Yan, H.
(2026). *Synthetic Sandbox for Training Machine Learning Engineering
Agents* (SandMLE). arXiv:2604.04872v1. License: CC-BY 4.0.

URL: https://arxiv.org/abs/2604.04872
