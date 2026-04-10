# External benchmarks — analisis y transferencia esperada

> **Status:** CANON. Analisis estructurado de los 6 benchmarks de la suite
> de tesis: que miden, como se ven los ejemplos concretos, y por que cabe
> esperar (o no) que un agente entrenado con SREG transfiera a cada uno.
> **Fecha:** 2026-04-07
> **Conecta con:** `sreg_training_transfer_protocol.md`,
> `thesis_evaluation_framework.md`, `related_work_sandmle.md`,
> `related_work_scigym.md`.

## Para que existe este documento

La suite externa final de tesis es:

```
held-out SREG + CLadder + QRData + DiscoveryBench + CausalReasoningBenchmark + SciGym
```

Listar los nombres no alcanza. Antes de correr BEFORE/AFTER, hace falta
entender **que mide cada benchmark, como se ve un ejemplo concreto, y
si un agente entrenado con SREG razonablemente deberia mejorar ahi**.
Si no podemos articular eso, no podemos interpretar los deltas.

Este doc responde, para cada benchmark:

1. **Como se ve un ejemplo.** Concreto, en lenguaje natural.
2. **Que mide y como puntua.** Metrica explicita.
3. **Por que SREG deberia transferir (o no).** Argumento estructural.
4. **Prediccion de magnitud.** Tibia, fuerte, nula, negativa.
5. **Riesgo principal.** Que puede arruinar la transferencia.

Y al final, una **lectura cruzada**: ranking por probabilidad de
transferencia limpia y por valor diagnostico para defender la tesis.

---

## Criterios de evaluacion de transferencia

Para juzgar si SREG deberia transferir a un benchmark X, miramos cinco
ejes:

| Eje | Pregunta |
|---|---|
| **Skill set** | Las habilidades que SREG entrena (cargar datos, intervenir, hacer adjustments, formular claims verificables, decidir que medir) son las que X requiere? |
| **Output format** | El output que el solver produce en SREG (claims en prosa via OI) es compatible con lo que X espera? |
| **Action space** | Las acciones disponibles en SREG (`python_exec` libre) coinciden con las que X permite? |
| **Domain proximity** | Los dominios y formatos de datos de SREG cubren los de X, o hay un gap grande? |
| **Scoring proximity** | El reward de SREG (truth + relevance + coverage contra SCM) presiona en la misma direccion que el scoring de X? |

Cuanto mas alineados los cinco, mayor la transferencia esperada.

Importante: SREG entrena via Open Investigation, donde **el solver
produce claims en prosa libre** y un compiler las traduce a especificaciones
verificables. El solver NO ve el compiler ni produce structured output.
Esto significa que SREG no impone format mismatch a benchmarks que
esperan prosa cientifica natural.

---

## 1. held-out SREG — control in-domain

### Como se ve un ejemplo

El mismo formato que cualquier caso SREG de training, pero generado con
seeds que no fueron parte del split de entrenamiento. Brief en lenguaje
natural, datasets tabulares, accion via `python_exec`, output en claims
en prosa.

### Que mide y como puntua

Mismas metricas que el training: `score.total` (truth + relevance +
coverage + no-spam), reward-order accuracy, no_data_gap. Es el unico
benchmark donde podemos medir nuestras metricas internas
(`investigation_gap`, alineamiento del scorer con audits humanos, etc).

### Por que SREG deberia transferir

Por construccion. Es la misma distribucion de tareas, mismo compiler,
mismo verifier. Si SREG-trained no mejora aca, hay un problema serio
con el setup de training.

### Prediccion de magnitud

**Mejora grande esperada.** Es el techo del experimento.

### Riesgo principal

Que mejore SOLO aca y no en los externos. **Eso seria el peor
escenario:** significa que el agente aprendio patterns lexicos del
compiler de SREG y no generalizo a investigacion. La diferencia entre
held-out SREG y los 5 externos es el verdadero diagnostico.

---

## 2. CLadder — razonamiento causal en texto

### Como se ve un ejemplo

> *"Imagine a self-contained, hypothetical world. Smoking has a direct
> effect on tar deposits. Tar deposits have a direct effect on lung
> cancer. We know that 60% of smokers have tar deposits, and 40% of
> non-smokers have tar deposits. We know that 70% of people with tar
> deposits develop lung cancer, and 20% of people without tar deposits
> develop lung cancer. Suppose we make people stop smoking. Would the
> rate of lung cancer decrease?"*

Respuesta esperada: **yes** o **no**. Sin datos. Solo texto que describe
relaciones causales y probabilidades.

### Que mide y como puntua

Razonamiento causal de Pearl sobre tres rungs:

- **Rung 1**: asociacional (`P(Y|X)`)
- **Rung 2**: intervencional (`P(Y|do(X))`)
- **Rung 3**: contrafactual (`P(Y_{x'}|X=x, Y=y)`)

Scoring determinista (yes/no exact match). 10112 preguntas, varios
splits balanceados.

### Por que SREG deberia transferir

**Argumento positivo:** SREG entrena al agente a pensar en intervenciones,
backdoor adjustment, do-operator. Esa intuicion causal — incluso si
nunca se verbaliza durante training — deberia darle priors mejores que
el modelo base sobre que es una intervencion versus una observacion,
que pasa cuando uno fija una variable, etc.

**Argumento negativo:** CLadder no tiene datos para mirar. SREG entrena
al agente a *cargar un CSV y correr una regresion*. Si su politica
aprendida es "reach for python_exec", aca no hay python_exec — es texto
puro. Riesgo de que el agente intente llamar tools que no existen.

### Prediccion de magnitud

**Mejora moderada.** Probablemente mas en rung 2 y rung 3 que en rung 1,
porque la maquinaria mental de SREG (intervencion, contrafactual) es mas
relevante alli. Menos en rung 1 (asociacional puro).

### Riesgo principal

**Tool dependence.** Si el agente SREG aprende a depender de
`python_exec` para razonar, sin tools degrada. Es una hipotesis a
verificar empiricamente.

---

## 3. QRData — analisis estadistico/causal sobre datos reales

### Como se ve un ejemplo

> *"Dataset: `boston_housing.csv` (506 filas, 13 columnas). Question:
> Calcula la correlacion parcial entre el numero promedio de habitaciones
> (RM) y el precio mediano (MEDV), controlando por la tasa de criminalidad
> (CRIM)."*

Respuesta numerica: `0.7234` (o lo que sea). 411 preguntas en el subset
causal mas comun.

### Que mide y como puntua

Razonamiento estadistico aplicado: calcular correlaciones, regresiones,
ATE, hacer adjustments de confounding sobre datos reales. Scoring
determinista por exact match numerico (con tolerancia).

### Por que SREG deberia transferir

**Es practicamente lo mismo que SREG hace todo el dia.** El solver de
SREG carga datos, corre `pandas`, `statsmodels`, `linearmodels`, hace
adjustments, interpreta coeficientes. QRData es exactamente este flujo
con datasets distintos. La transferencia deberia ser directa.

**Pero ojo: requiere code execution en el harness.** Esta es la
condicion no negociable.

### Prediccion de magnitud

**Mejora grande con code execution** (estimacion: del orden 38% -> 55-65%
en el dev split). El techo lo pone el harness, no el modelo.

### Riesgo principal

**El harness BEFORE corrio text-only (38%).** Si el harness AFTER tiene
code execution y compara contra ese 38%, el delta va a parecer enorme
pero parte del boost es del cambio de harness, no del entrenamiento.
**Esto invalida la comparacion.** O re-corremos BEFORE con code
execution, o sacamos QRData del Tier 1. No hay tercera opcion limpia.

Ver `TODO.md` T4.

---

## 4. DiscoveryBench — generacion de hipotesis

### Como se ve un ejemplo

> *"Dataset: `nls_youth.csv` (longitudinal survey of US youth, 1979-2018).
> Goal: Identify a relationship in this dataset that explains differences
> in adult earnings."*

Output libre (prosa):
> *"Higher childhood reading comprehension scores predict higher adult
> hourly earnings, with the relationship partially mediated by college
> attendance."*

Metrica: **Hypothesis Match Score (HMS)** — un LLM-judge compara la
hipotesis del agente contra una ground-truth y puntua similitud
semantica. 25 ejemplos en el train split que usamos como dev.

### Que mide y como puntua

Generacion de hipotesis cientificas falsificables a partir de datos.
HMS via LLM-judge. **Es el unico benchmark de la suite con scoring
no-deterministico.**

### Por que SREG deberia transferir

**Argumento positivo:** SREG entrena exactamente esto. El solver explora
datos, identifica patrones, formula claims sobre relaciones causales,
mediacion, heterogeneidad. El output final es prosa cientifica — el
mismo formato que DiscoveryBench acepta. No hay format mismatch entre
lo que SREG produce y lo que DiscoveryBench evalua.

**Argumento negativo:** HMS es ruidoso. Dos hipotesis equivalentes
pueden recibir scores muy distintos segun el wording. La calidad real
del razonamiento se traduce mal en el score.

### Prediccion de magnitud

**Mejora media-alta esperada en sustancia, alta-varianza en HMS bruto.**
Probablemente la mejora real es mayor que la mejora medida por el
juez. Conviene reportar ambas: HMS oficial + analisis cualitativo de
si las hipotesis son objectivamente mejores.

### Riesgo principal

**LLM-judge no determinista.** Sin mitigacion (judge model fijo, prompt
fijo, version fija, multiple seeds + voting), los deltas BEFORE/AFTER
no son comparables. Ver `TODO.md` T5.

### Caveat sobre drift estilistico durante RL

Aunque OI no impone format estructurado, durante RL hay riesgo de
**drift estilistico implicito**: el solver aprende a converger hacia el
estilo de prosa que el compiler de SREG interpreta mejor. Si el
compiler tiene un sweet spot estrecho, el output del solver puede
desviarse del estilo cientifico natural y eso castigaria HMS. Es una
pregunta empirica abierta sobre la robustez del compiler.

---

## 5. CausalReasoningBenchmark (CRB) — identification + estimation

### Como se ve un ejemplo

> *"Research question (Angrist & Krueger, 1991): Does an additional year
> of schooling increase earnings? Dataset: 1980 US Census, n=329509.
> Specify (a) the identification strategy, (b) the treatment, outcome,
> and controls, and (c) a point estimate with standard error."*

Output esperado (estructurado pero en lenguaje natural):
- **Strategy**: Instrumental variables (quarter of birth as instrument
  for years of education)
- **Treatment**: years of education
- **Outcome**: log weekly wage
- **Controls**: year of birth dummies, region dummies
- **Estimate**: 0.076 (SE 0.015)

173 queries sobre 138 datasets reales, curados de 85 papers peer-reviewed
y 4 libros de causal inference.

### Que mide y como puntua

Separa **identification** (definir el research design correctamente) de
**estimation** (producir un numero). Scoring determinista por matching
de strategy/treatment/outcome/controls + numerical accuracy del estimate.

Baseline SOTA (state-of-the-art LLM segun el paper):
- Strategy correcta: 84.4%
- Outcome correcto: 95.4%
- Causal quantity correcta: 61.3%
- **Full identification spec correcta: 30.1%**

Es un benchmark **duro**.

### Por que SREG deberia transferir

**Estructuralmente es lo que mas se parece a lo que SREG entrena.** El
agente tiene que (1) identificar que estrategia causal aplica, (2)
nombrar variables especificas, (3) producir un numero con incertidumbre.
Eso es exactamente el output de un episodio OI bien jugado. SREG
entrena precisamente esa secuencia: leer brief -> decidir estrategia ->
ejecutar -> reportar.

### Prediccion de magnitud

**La mejora mas grande esperada de la suite externa.** El espacio
disponible es enorme (SOTA en 30.1%) y el skill match es casi perfecto.
**Si SREG no mejora aca, algo esta muy mal con el approach.** Es la
prueba mas limpia de que el training transfiere.

### Riesgo principal

**Gap lexico.** Los nombres de variables en CRB son los del paper
original (`lwklywge`, `yrseduc`, `qob1`, `kwwscore`). SREG entrena con
nombres mas limpios y semanticos. Si el agente necesita resolver el
mapeo entre variable name y meaning para elegir bien, el gap puede
penalizar.

---

## 6. SciGym — loop iterativo en biologia de sistemas

### Como se ve un ejemplo

> *"You are studying a biological pathway with 8 species. Initial SBML
> model is provided with species and parameters but all reactions are
> removed. You can perform up to 20 experiments. Each experiment lets
> you set the initial concentration of one specified species, and you
> observe the resulting concentration time series of all 8 species over
> time. After your experiments, submit a complete SBML model that
> includes the inferred reactions. The hidden ground-truth model has N
> reactions."*

Action space cerrado: `set_initial_concentration(species, value)`,
`run_experiment()`, `submit_sbml(model)`.

Output: un archivo SBML completo con reacciones inferidas.

### Que mide y como puntua

Tres metricas complementarias contra el SBML ground-truth:

- **Network Topology Score (NTS)** — F1 sobre interacciones entre especies
- **Reaction Matching Score (RMS)** — par de reacciones "matched" si tienen
  los mismos reactivos y productos
- **Simulation Trajectory Error (STE)** — SMAPE sobre las series temporales
  predichas vs ground truth

Scoring **completamente determinista**. Ground truth: 350 modelos SBML
de BioModels (137 small con < 10 reacciones, 213 large hasta 400
reacciones).

Baselines reportados (paper, 2025):

| Modelo | STE | RMS F1 |
|---|---|---|
| Gemini-2.5-Pro | 0.32 | 0.18 |
| Claude-3.7-Sonnet | 0.36 | 0.17 |
| GPT-4.1 | 0.46 | 0.17 |

**Frontier models obtienen RMS F1 < 0.20.** Es un benchmark muy duro
en su forma actual.

### Por que SREG deberia transferir

**El loop de SciGym es exactamente lo que SREG aspira a entrenar.**
Proponer experimento -> observar -> actualizar creencia -> refinar.
Es el patron Sherlock-type que `PROJECT.md` Horizonte 2 lista como
aspiracion central. Si SREG funciona como queremos, esto **tiene que**
mejorar. Es la prueba mas afilada de la claim del paper.

### Prediccion de magnitud

**Bisagra del paper.** Dos escenarios posibles:

- **Si la meta-skill transfiere** (planear experimentos, descomponer,
  decidir que medir, saber cuando parar): mejora visible aunque
  modesta. Limitada por gaps de dominio pero presente.

- **Si la meta-skill NO transfiere** y el agente solo aprendio
  object-level (cargar CSV, correr regresion): cero mejora o
  degradacion, porque las herramientas de SREG no aplican aca.

**Este es el benchmark que decide si SREG entrena juicio cientifico
real o solo data analysis bien hecho.** Vale el costo operativo de
integrarlo.

### Riesgo principal

**Tres gaps grandes que pueden enmascarar transferencia real:**

1. **Domain gap.** SREG nunca vio biologia, ni SBML, ni redes de
   reacciones. El agente puede no saber siquiera que es un knockout o
   como se interpreta una concentracion molar.
2. **Format gap.** SREG usa `python_exec` libre, SciGym tiene action
   space cerrado (`set_initial_concentration`, `submit_sbml`). El
   harness de scaffold tiene que mediarse cuidadosamente.
3. **Time-series gap.** SREG procesa datos tabulares cross-section.
   SciGym es dinamica (concentracion vs tiempo). El agente no fue
   expuesto a series temporales durante training.

Si la mejora es nula, **no implica que la meta-skill no transfiera** —
puede ser que los gaps de dominio hayan saturado el efecto. Conviene
reportar tambien comportamiento cualitativo: ¿el agente al menos
*intenta* iterar y planear, o se queda paralizado?

---

## Lectura cruzada

### Ranking por transferencia esperada (limpia)

1. **CRB** — alta. Skill estructural casi identico, headroom enorme.
2. **QRData (con code exec)** — alta. Skill set casi identico, pero
   el techo lo pone el harness.
3. **DiscoveryBench** — media-alta. Mismo formato de output (prosa),
   riesgo principal es el judge ruidoso, no la transferencia en si.
4. **CLadder** — media. Razonamiento causal si, falta de datos no.
5. **SciGym** — bisagra. En principio alta (es el target conceptual),
   en practica depende de si la meta-skill sobrevive el cambio de
   dominio/formato.

### Ranking por valor diagnostico para la tesis

1. **SciGym** — el mas informativo. Decide la claim grande.
2. **CRB** — el que valida que "SREG transfiere a investigacion real".
3. **QRData** — el que valida que el skill de analisis transfiere.
4. **DiscoveryBench** — el que mide hipotesis libres.
5. **CLadder** — el que mide razonamiento causal puro.

Notar: el ranking de **transferencia esperada** y el de **valor
diagnostico** no coinciden. SciGym es el mas dificil de hacer mejorar
pero el mas importante para defender la claim. Esa asimetria es
central en el plan de tesis.

### El delta in-domain vs out-of-domain como senal central

La metrica mas informativa probablemente NO es ningun score absoluto,
sino el **delta entre held-out SREG y los 5 externos**:

- Si delta es pequeno -> transferencia real, claim defendible.
- Si delta es grande -> overfit a SREG, claim debil.

Esto es estructuralmente el mismo diagnostico que SandMLE hace cuando
mira `MLE-bench-lite` (in-domain proxy) vs `MLE-Dojo`
(out-of-distribution). Vale citarlo asi en el paper.

---

## Lo que NO podemos responder con esta suite

Hay dos cosas que SREG aspira a entrenar y que **ningun benchmark
externo de la suite mide directamente**:

1. **Seleccion de experimentos bajo presupuesto.** Ningun benchmark
   externo tiene un presupuesto cerrado de acciones que el agente debe
   asignar inteligentemente. SciGym tiene un cap de 20 iteraciones pero
   no una "moneda" de presupuesto que el agente vaya gastando.
   Solo `held-out SREG` puede medir esto.

2. **Las propiedades epistemologicas de las "Presiones evolutivas"**
   (anti-overexcitement, hipotesis rivales, saber cuando parar,
   separar evidencia de priors, etc.). Ninguna metrica externa
   captura esto. Solo audits cualitativos sobre `held-out SREG`.

Esto es una limitacion honesta del paper. Hay dos opciones:

- **Aceptar la limitacion** y reportar las metricas externas como
  evidencia de transferencia parcial.
- **Construir un benchmark propio** (estilo SandMLE con MLE-bench-lite)
  que mida exactamente eso. Es la opcion C que discutimos en sesiones
  anteriores: un set congelado de casos SREG-Sherlock con presupuesto
  cerrado y metricas de juicio. Trabajo grande pero convierte el gap
  en una contribucion adicional.

Decision pendiente. Ver `TODO.md` y `thesis_evaluation_framework.md`.

---

## Decisiones que este analisis aclara

1. **CRB y QRData son las pruebas mas limpias.** Si SREG no mejora ahi,
   el approach falla en la pieza facil.
2. **SciGym es la prueba mas dura y la mas importante.** Vale el costo.
3. **DiscoveryBench depende criticamente de la mitigacion del judge.**
   Sin T5 cerrado, los deltas no son interpretables.
4. **CLadder es el control mas barato.** Dejarlo aunque la mejora
   esperada sea modesta — es una validacion barata del razonamiento
   causal puro.
5. **El delta in-domain vs out-of-domain es la metrica central.** Mas
   importante que cualquier accuracy individual.

---

## Que hacer con este doc

- **Antes de cada BEFORE/AFTER:** releer la seccion del benchmark
  correspondiente para alinear expectativas.
- **Cuando salgan los resultados:** comparar deltas observados contra
  predicciones de magnitud aca, y documentar discrepancias. Las
  sorpresas son las cosas que mas ensenan.
- **Cuando se escriba el paper:** este doc alimenta la seccion
  "Benchmark Selection and Expected Transfer".
