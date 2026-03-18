# Debate: Por que SREG todavia no es una investigacion real?

> Debate iniciado 2026-03-18 entre Claude, Codex y el usuario.
> Objetivo: identificar las brechas entre SREG y la investigacion real,
> y priorizar que cerrar primero.

---

## Ronda 1: Codex — diagnostico inicial

### Diagnostico central

> SREG se parece mas a un **simulador de "resolver un problema bien especificado"**
> que a investigacion cientifica. En investigacion lo central no es contestar la
> pregunta correcta, sino **reducir incertidumbre sobre un mundo mal especificado**.

### 6 brechas invisibles identificadas

**1. Misspecification cero (certeza de clase de modelo)**

El solver "sabe" (implicitamente) que el mundo es una BN sobre estas variables,
con estas independencias, sin mecanismos fuera del grafo. En ciencia real, gran
parte del trabajo es detectar que **tu modelo esta mal** (interacciones no
modeladas, confusores no medidos, cambios de regimen). Sin posibilidad real de
estar equivocado de familia, no hay ciencia: hay puzzle-solving.

**2. Medicion no es un problema (construct validity)**

5% noise/missingness no captura lo duro: operacionalizacion, instrumentos, sesgo
sistematico, proxies, limites de deteccion, calibracion, batch effects, cambios
de protocolo. Muchas conclusiones reales dependen mas de esto que del razonamiento
causal.

**3. No hay equifinalidad real (subdeterminacion / modelos competidores)**

En ciencia, varias explicaciones sobreviven a la evidencia. La habilidad clave
es: (a) decir que NO esta identificado, (b) proponer supuestos explicitos,
(c) disenar evidencia que discrimine. Si casi todo tiene respuesta unica
accesible, faltan las condiciones epistemologicas que hacen investigacion.

**4. Sin validez externa (transportability/shift)**

"Funciona en este dataset" no implica "funciona en otro contexto". Si los datasets
comparten el mismo SCM subyacente, falta el nucleo de generalizacion cientifica:
que es estable y que no.

**5. Semantica como skin, no como constraint**

Si el modo realistic/fictional no impone restricciones (plausibilidad fisica,
monotonicidades, conservacion), la semantica no participa del razonamiento. En
ciencia real, el conocimiento del dominio recorta el espacio de hipotesis.

**6. Incentivo equivocado: score numerico, no epistemologia**

Un cientifico es evaluado por robustez, replicacion, prediccion, claridad de
supuestos, sensibilidad a sesgos. Si el score premia solo coincidencia numerica,
el agente aprende atajos que en ciencia real serian invalidados.

### Sobre BN como verdad formal

> No esta mal como motor generativo, pero es peligroso como unica ontologia.
> El pecado capital es la ausencia de incertidumbre estructural: si el mundo
> siempre es BN-correcto, entrenas confianza injustificada.

BN como backend esta bien SI introduces mismatch, modelos competidores, medicion
y shift. Sin eso, BN te empuja a un "universo de juguete perfectamente modelable".

### Cambio de mayor impacto

Convertir SREG de "Q&A con teacher" a un juego de investigacion secuencial donde
el solver: mantiene distribucion sobre modelos competidores, puede comprar evidencia
con costo, y se puntua con log score + prediccion fuera de muestra + penalizacion
por sobreconfianza.

### Repriorizacion propuesta

1. Incertidumbre estructural + misspecification + modelos competidores + scoring
   calibrado
2. Diseno de evidencia con costos + shift/replicacion
3. Despues: continuas, temporalidad, teoria/literatura sintetica

### Contra-punto Claude

Coincido con el diagnostico, pero hay tension con el Invariante 1 (reward exacto).
Propuesta: dos DAGs competidores donde ambos generan datos compatibles pero solo
uno es correcto. El reward sigue siendo exacto pero el camino requiere investigacion
real.

---

## Ronda 2: Codex responde al pushback

### Pushback del usuario sobre misspecification

> "Por que pasa esto? Misspecification cero... igual la idea de SREG es que haya
> un mundo real subyacente... no me parece mal."

### Respuesta de Codex

> **Tiene razon.** Que exista ground truth no es el problema — lo necesitas para
> reward exacto. El problema es cuando el solver tiene **conocimiento privilegiado**:
> sabe que el mundo es una BN, con que variables, que tipo de ruido, que clase de
> intervenciones. Eso empuja a misspecification=0 y a soluciones "de manual".

La distincion sutil: el ground truth puede existir (y debe, para el reward). Lo
que no deberia existir es que el solver SEPA que tipo de modelo es.

### MVP propuesto por Codex: Interventional Predictive Log-Score

- El agente entrega distribuciones predictivas q(y) para queries interventionales
- Reward = log-score contra p*(y|do(x)) del ground truth (exacto!)
- Penalizacion por costo de experimentos
- Tolera equifinalidad: modelos distintos con mismas predicciones puntuan igual

### Que aprender de otros proyectos

- **ResearchGym**: scoring ejecutable (no LLM judges), acciones son cambios reales
- **SciGym**: agente propone perturbaciones y recibe datos simulados
- **DiscoveryWorld**: pipeline completo (hipotesis -> experimento -> analisis)

---

## Ronda 3: Descubrimiento — leak de framework en las preguntas

### Hallazgo clave

Al investigar si el solver "sabe" que es una BN, descubrimos que las
**preguntas mismas** filtran el framework:

| Template | Leak |
|---|---|
| causal_effect | "This is a causal question... do-operation" |
| best_intervention | "This is a causal question about interventions (do-operations), not observations" |
| compare_interventions | "causal effect", "do-operations (interventions), not observations" |
| infer_latent_cause | "hidden variable", "cannot be directly observed" |
| should_condition | "causal effect", "controlling for" |
| adjustment_set | "backdoor paths", "backdoor criterion", "confounding", "spurious associations" |

### Dos niveles del problema

1. **Preguntas del orchestrator** (caso mode) — bastante naturales, no tan graves
2. **Templates hardcodeados en task_gen.py** — aca esta el leak

Un LLM que vio miles de ejercicios de causal inference lee "do-operation" y
automaticamente entra en "modo BN/SCM". No porque se lo dijimos, sino porque
las preguntas estan formuladas en el lenguaje de esa familia de modelos.

### Accion tomada: naturalizar todos los templates

| Antes | Despues |
|---|---|
| "intervention (do-operation)" | "if X were set to Y" |
| "This is a causal question" | (eliminado) |
| "hidden variable" | "this factor is not directly measured" |
| "controlling for" | "accounting for" |
| "backdoor paths" | "unbiased estimate" |
| "confounding variables that create spurious associations" | "misleading associations" |
| "Intervention A/B" | "Option A/B" |
| "causal effect" | "true effect" |

**Tests:** 1103 pasando. Los tests que chequeaban wording tecnico fueron
actualizados para reflejar el nuevo lenguaje natural.

### Punto abierto: suficiente?

Naturalizar las preguntas ayuda pero no resuelve todo. El format table
(`submit(distribution={...})`) todavia revela que la respuesta es una
distribucion de probabilidad. Y las preguntas tipo causal_effect siguen
preguntando por el efecto de "set X to Y" — un investigador real formularia
la pregunta de forma mas abierta ("que pasa si reducimos la carga?").

La solucion completa probablemente requiere que el orchestrator SIEMPRE
escriba la pregunta en lenguaje completamente natural, y que los templates
sean solo fallback para single-task mode / diagnostico.
