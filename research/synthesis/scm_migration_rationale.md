# De BN a SCM — Fundamentos de la migracion

> Decision arquitectonica critica. Este documento explica POR QUE SREG
> debe migrar de Bayesian Networks con CPD tables a Structural Causal
> Models (SCM) con simulacion.
>
> Status: **DECIDIDO** (2026-03-20). Implementacion en branch `feature/scm-engine`.
> Referencia: A8 (historico, resuelto), `notes/gaussian_bn_prototype_findings.md`

---

## El problema

SREG usa redes bayesianas discretas como motor del mundo subyacente. Cada
variable tiene 3 estados (`low/moderate/high`) y las relaciones se definen
con CPD tables (tablas de probabilidad condicional).

Esto causa tres problemas fundamentales:

### 1. Falta de realismo

Un investigador real mide VO2max en mL/kg/min, temperatura en grados,
concentracion en mg/L. No en "low/medium/high". Los datos discretizados
no se parecen a datos reales y el solver hace crosstabs en vez de
regresion, correlacion o scatterplots.

**LA PREGUNTA aplicada:** un cientifico que vea estos datos no los
confundiria con datos reales. Le falta la continuidad, la granularidad
y la forma de los datos del mundo real.

### 2. Escalabilidad

CPD tables crecen exponencialmente: 3 estados x N padres = 3^N entries.
Con 4 padres = 81 entries. Con 6 padres = 729. Esto fuerza `MAX_PARENTS=5`
y el orchestrator gasta iteraciones enteras intentando reducir padres
de nodos que naturalmente tienen 5-6 causas.

**Evidencia:** el seed de football fallo 8/10 iteraciones por
"Nodes exceed max parents" (2026-03-17).

### 3. Expresividad limitada

Las relaciones reales no son tablas de probabilidades. Son ecuaciones
con umbrales, saturacion, interacciones, efectos no lineales. Una BN
discreta no puede representar "la temperatura sube exponencialmente
cuando el ejercicio supera cierto umbral" ni "el riesgo tiene forma
de sigmoid".

**El peligro real (sesgo de formalismo):** si el engine solo puede
representar tablas de probabilidad, terminamos disenando mundos que
se ajustan a lo que el engine puede hacer, en vez de mundos que se
parecen a la realidad.

---

## Que es una BN y por que la usabamos

Una Bayesian Network (Judea Pearl, 1988) es:

- Un **grafo dirigido aciclico** (DAG) que dice que causa que
- Una **CPD por variable** que dice cuanto y como

La ventaja principal: **inferencia exacta**. Dada evidencia, la BN
computa la probabilidad posterior EXACTA (0.37284..., todos los decimales).
Sin simular, sin aproximar. Esto es lo que nos daba el reward exacto.

Las BN se usan en: diagnostico medico, deteccion de fraude, genetica,
filtros de spam. Casos donde el modelo es relativamente chico y necesitas
la probabilidad exacta.

**Lo que la BN nos daba en SREG:**

1. Reward exacto (analitico, cero error)
2. Velocidad (inferencia instantanea para 10-12 nodos)
3. Framework teorico probado (d-separation, do-calculus, backdoor criterion)

---

## Que es un SCM

Un Structural Causal Model (tambien de Pearl) es la forma MAS GENERAL
de modelar causalidad. La BN es un CASO PARTICULAR de un SCM.

Un SCM es:

- Un **grafo dirigido aciclico** (el mismo DAG)
- Una **ecuacion por variable** (en vez de una CPD)
- **Variables de ruido** (exogenas)

```python
# SCM: cada variable es una funcion de sus padres + ruido
carga_semanal = random.uniform(2, 15)
fitness = random.gauss(50, 10)

ejercicio = min(carga_semanal * 0.7 + fitness * 0.1, 10) + noise()

temperatura = 36.5
             + (2.0 * sqrt(ejercicio - 7) if ejercicio > 7 else 0.3 * ejercicio)
             - 0.2 * hidratacion
             + 0.4 * ambiente
             + noise()

riesgo = sigmoid(temperatura - 39, fatiga)
```

**do-calculus en un SCM:** para computar P(Y | do(X=x)), se reemplaza
la ecuacion de X con `X = x` (se "corta" de sus padres), y se simula
el resto muchas veces. Esto es exactamente lo que Pearl define como
intervencion.

---

## Por que migrar: la comparacion

### Lo que perdemos


| Propiedad               | Con BN            | Con SCM                      | Impacto                                                              |
| ----------------------- | ----------------- | ---------------------------- | -------------------------------------------------------------------- |
| Exactitud analitica     | 0.37284... exacto | 0.3731 +/- 0.002 (MC 100K)   | **Bajo** — para RL el ruido de MC es menor que el ruido del training |
| Velocidad de inferencia | Instantanea       | ~1 seg por query (100K sims) | **Bajo** — aceptable                                                 |
| pgmpy como engine       | Si                | No (networkx para el grafo)  | **Neutral** — pgmpy no tenia inferencia continua de todas formas     |


### Lo que ganamos


| Propiedad       | Con BN                      | Con SCM                                                           | Impacto  |
| --------------- | --------------------------- | ----------------------------------------------------------------- | -------- |
| Variables       | 3 estados discretos         | Cualquier tipo (continuas, discretas, mixtas)                     | **Alto** |
| Relaciones      | Tablas de probabilidad      | Ecuaciones arbitrarias (lineales, no lineales, umbrales, sigmoid) | **Alto** |
| Escalabilidad   | 3^N con N padres            | Lineal (N coeficientes)                                           | **Alto** |
| Datos generados | Artificiales (low/med/high) | Realistas (37.8C, 52.3 mL/kg/min)                                 | **Alto** |
| Solver behavior | Crosstabs, conteo           | Regresion, correlacion, scatterplots                              | **Alto** |
| Riesgo de sesgo | Alto (limitado a CPDs)      | Bajo (ecuaciones libres)                                          | **Alto** |


### Lo que NO cambia


| Propiedad                        | Status                                               |
| -------------------------------- | ---------------------------------------------------- |
| Grafo causal (DAG)               | Se mantiene — es la base de todo                     |
| d-separation                     | Se mantiene — depende del grafo, no de las CPDs      |
| Identifiability                  | Se mantiene — depende del grafo                      |
| do-calculus                      | Se mantiene — "cortar edges y simular"               |
| should_condition, adjustment_set | Se mantienen — usan d-separation del grafo           |
| Reward sin LLM judge             | Se mantiene — MC es suficientemente preciso          |
| Teacher como upper bound         | Se mantiene — el teacher simula con el SCM verdadero |


---

## La pregunta clave: exacto vs preciso

**Para RL, la diferencia entre reward analitico (error=0) y reward
Monte Carlo (error~0.001 con N=100K) importa?**

Probablemente no. El ruido del proceso de entrenamiento (gradientes
estocasticos, sampling de episodios, exploration) es ordenes de magnitud
mayor que el ruido de MC. Nadie nota la diferencia entre un reward de
0.37284 y 0.3731 cuando el gradiente ya tiene varianza 0.1.

Si alguna vez necesitamos mas precision, simplemente subimos N.
Con N=1M el error baja a ~0.0003. Es arbitrariamente preciso.

---

## Como se ve el SCM en la practica

### Definicion del mundo

```python
world = SCMWorld(
    graph={
        "carga": [],                    # raiz
        "fitness": [],                   # raiz
        "ejercicio": ["carga", "fitness"],
        "temperatura": ["ejercicio", "ambiente", "hidratacion"],
        "riesgo": ["temperatura", "fatiga"],
    },
    equations={
        "carga": lambda: random.uniform(2, 15),
        "fitness": lambda: random.gauss(50, 10),
        "ejercicio": lambda p: min(p["carga"]*0.7 + p["fitness"]*0.1, 10) + N(0, 0.5),
        "temperatura": lambda p: (
            36.5 + threshold(p["ejercicio"], 7, slope=2.0)
            - 0.2*p["hidratacion"] + 0.4*p["ambiente"] + N(0, 0.3)
        ),
        "riesgo": lambda p: sigmoid(p["temperatura"] - 39, p["fatiga"]),
    },
    variable_meta={
        "carga": {"unit": "hours/week", "range": [2, 15]},
        "temperatura": {"unit": "celsius", "range": [36, 42]},
        # ...
    }
)
```

### Generacion de datos

```python
# Generar 500 muestras (datos observacionales)
df = world.sample(n=500, seed=42)
# -> DataFrame con columnas continuas realistas
```

### do-calculus

```python
# P(riesgo | do(ejercicio=9))
dist = world.interventional_distribution("riesgo", do={"ejercicio": 9}, n=100_000)
# -> distribucion empirica de riesgo cuando se fija ejercicio=9
```

### Scoring

```python
# KL entre la distribucion del solver y la distribucion simulada
# Para continuas: discretizar en bins, o usar KDE + KL numerico
score = kl_divergence(solver_dist, true_dist, method="histogram")
```

---

## Opciones intermedias evaluadas y descartadas

### Gaussian BN (Linear Gaussian)

Cada variable es `Y = a + b1*X1 + b2*X2 + ruido_gaussiano`. Inferencia
analitica, KL closed-form. Prototipado exitosamente (2026-03-18).

**Descartado como destino final** porque sigue siendo restrictivo:
relaciones TIENEN que ser lineales y ruido TIENE que ser Gaussiano.
Resuelve escalabilidad pero no expresividad. Podria ser un paso
intermedio si se necesita.

Referencia: `research/notes/gaussian_bn_prototype_findings.md`

### Mas estados discretos (10-20 en vez de 3)

No resuelve nada: CPD tables explotan aun mas (10^N con N padres).
Los datos siguen sin ser continuos. Descartado.

### CLG (Conditional Linear Gaussian)

Mixto: nodos discretos condicionan parametros de nodos Gaussianos.
Mas realista que full Gaussian, pero sigue limitado a linealidad
dentro de cada configuracion discreta. Subsumido por SCM general.

---

## Riesgos y mitigaciones


| Riesgo                                                | Mitigacion                                                                       |
| ----------------------------------------------------- | -------------------------------------------------------------------------------- |
| MC lento para muchas queries                          | Paralelizar, cachear, batch                                                      |
| Precision insuficiente para algun eval type           | Subir N. Con N=1M ~0.0003 error                                                  |
| El orchestrator no sabe disenar ecuaciones            | El orchestrator propone la estructura, un generador crea ecuaciones parametricas |
| Scoring para distribuciones continuas es mas complejo | Histograma + KL, o KDE, o Wasserstein. Investigar                                |
| Eval types como should_condition/adjustment_set       | Solo dependen del grafo (d-separation). No cambian                               |
| Tests existentes (1103) se rompen                     | Mantener el engine discreto para tests legacy. SCM es paralelo                   |


---

## Plan de implementacion

Trabajar en branch `feature/scm-engine`. No tocar el engine actual.

**Fase 1: Prototipo minimo**

- `SCMWorld`: grafo + ecuaciones + sample() + interventional_distribution()
- `SCMSolver` (teacher): usa el SCM para computar ground truth via MC
- Scoring continuo: al menos un metodo (histograma + KL)
- Test con un mundo de 5-6 nodos con ecuaciones no lineales

**Fase 2: Integracion con pipeline**

- TaskGen que genere preguntas sobre un SCMWorld
- Solver prompt adaptado para datos continuos
- generate_src.py que soporte SCM worlds

**Fase 3: Orchestrator**

- El orchestrator disenya la estructura del SCM (grafo + tipos de ecuaciones)
- Generador parametrico de ecuaciones a partir de la especificacion

**Criterio de merge a main:** el pipeline E2E funciona con un SCMWorld,
genera datos realistas, el solver puede analizarlos, y el scoring es
preciso (verificar contra Gaussian analitico como baseline).