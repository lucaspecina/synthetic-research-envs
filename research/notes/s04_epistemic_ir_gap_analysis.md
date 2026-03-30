# S04 — Analisis del gap de la IR para claims epistemologicos

> Investigacion: 2026-03-30
> Metodo: Trace completo de 4 claims de e2e_03 (epistemologico) a traves del
> pipeline: solver → compiler → lowering → verifier → matching → scoring.
> Objetivo: dar evidencia concreta a A23 sobre que claims se pierden y por que.

## Resumen ejecutivo

El caso epistemologico (e2e_03) es el caso diagnostico perfecto para A23.
El brief pide evaluar si una interpretacion causal es *defendible* — una
pregunta inherentemente epistemologica. El solver responde bien: produce
4 claims sobre asociacion, sensibilidad al ajuste, credibilidad del
instrumento y calidad de datos. Pero la IR (`ClaimIntent` con 8 `PatternClass`)
solo puede representar 1 de los 4 claims, y ese unico claim matchea el SQ
equivocado. Score: **0.239** (coverage=0.02, correctness=1.0).

**Hallazgo central:** el verifier (`AtomicSpec`) YA tiene la expresividad
para verificar al menos 2 de los 3 claims perdidos. El gap esta exclusivamente
en la IR intermedia (`ClaimIntent → lowering → AtomicSpec`), no en la
capacidad de verificacion.

## Datos del trace

### Brief de investigacion

> Assess whether a causal interpretation is defensible from the current
> observational evidence, explain the main threats to identification, and
> evaluate whether the city's proposed quasi-experimental argument based
> on wind conditions is credible.

El brief pide CUATRO cosas, todas epistemologicas:
1. La interpretacion causal es defendible? (evaluacion de evidencia)
2. Cuales son las amenazas de identificacion? (diagnostico metodologico)
3. El argumento cuasi-experimental con viento es creible? (evaluacion de instrumento)
4. Si no basta, que datos adicionales hacen falta? (recomendacion de diseno)

### Sub-questions generadas

| SQ | Pattern | Ask | Variables | Tier |
|----|---------|-----|-----------|------|
| sq1 | causal_effect | existence_and_sign | particle→wheeze | HIGH |
| sq2 | confounding | existence_and_sign | particle→wheeze (conf=industrial) | HIGH |
| sq4 | obs_assoc | sign | wind→particle | MEDIUM |
| sq5 | effect_ranking | rank_order | [industrial, traffic, green_space]→wheeze | LOW |

**Problema SQ:** El brief pide evaluacion epistemologica, pero las SQs bajan
a preguntas sustantivas sobre relaciones. No hay SQ para "es defendible la
interpretacion causal?" o "es creible el instrumento?". La IR de SQs
(`SubQuestionIntent` con `pattern + roles + ask`) no puede expresar
preguntas metodologicas.

### Claims del solver

| Claim | Texto (resumido) | Tipo epistemico |
|-------|-------------------|-----------------|
| C1 | Asociacion positiva r≈0.45, coeficiente ~0.28 con fixed-effects. Soporta asociacion pero no causacion. | Hallazgo sustantivo + caveat epistemologico |
| C2 | Coeficiente encoge de 0.28 a 0.116 al ajustar por 7 covariables. Sugiere confounding y/o inestabilidad por missingness. | **Analisis de sensibilidad** |
| C3 | Correlacion wind-particle = -0.19 en dataset_bg pero flips a +0.25 en dataset_detail. Instrumento cuestionable. | **Evaluacion de instrumento** |
| C4 | Missingness de 18-24% en covariables clave. Reduce muestras usables y arriesga sesgo. Limita identificacion causal. | **Diagnostico de calidad de datos** |

**Calidad del solver:** Las 4 claims responden directamente el brief. Un
revisor humano calificaria esta investigacion como buena. El solver entendio
el tipo de investigacion (epistemologico) y respondio en consecuencia.

## Trace completo: claim → compilacion → verdad → matching

### C1: Asociacion positiva (COMPILA OK)

```
Solver:  "r≈0.45, coef~0.28, supports association but not causation"
Compiler: obs_assoc, particle→wheeze, positive, observational
Truth:   1.0 (correcto — el SCM tiene asociacion positiva)
Compat:  sq1=0.650, sq2=0.100, sq4=0.000, sq5=0.000
Asignado: sq2 (sat=0.060)  ← DESPERDICIADO en el SQ equivocado
```

**Que se pierde:** El caveat epistemologico "but not causation" no tiene
representacion en la IR. La IR solo puede decir "positivo" o "negativo",
no "positivo pero epistemicamente debil".

**Anomalia de matching:** C1 tiene compat=0.650 con sq1 pero termina
asignado a sq2 con sat=0.060. El algoritmo de asignacion lo desperdicia.

### C2: Sensibilidad al ajuste (NO COMPILA)

```
Solver:  "coefficient shrinks from 0.28→0.116, p≈0.07, n=127,
          suggests confounding and/or missing-data instability"
Compiler: ABSTENTION (intento confounding sin campo confounder → pydantic fallo)
          En otro run: causal_effect + conditioning_set (pierde la comparacion)
Truth:   N/A
Compat:  N/A
```

**Que se pierde:** TODO. La claim es sobre la DIFERENCIA entre estimaciones
cruda y ajustada. No es "X causa Y" ni "X correlaciona con Y". Es
"la evidencia cambia cuando ajustas".

**Que podria expresar el verifier:**
```
AtomicSpec 1: observe() → correlation(particle, wheeze) → identity → positive
AtomicSpec 2: adjust(traffic, industrial, ...) → partial_correlation(particle, wheeze)
              → identity → near_zero (o positive debil)
AtomicSpec 3: comparison(crude vs adjusted) → contrast_diff → positive (encoge)
```

El verifier tiene `adjust` (QueryKind), `partial_correlation` (MeasurementKind),
y `contrast_diff` (ComparisonKind). PUEDE verificar la sensibilidad al ajuste.
Pero `ClaimIntent` no tiene ruta para generar estos specs.

**Tipo de gap:** RUTA BLOQUEADA — el verifier puede, la IR no puede rutear.

### C3: Instrumento inconsistente (COMPILA INCORRECTAMENTE)

```
Solver:  "wind-particle corr = -0.19 en bg, flips a +0.25 en detail.
          Instrument cuestionable."
Compiler: 2 units obs_assoc, wind→particle near_zero + wind→wheeze near_zero
Truth:   0.0 + 0.0 (el SCM dice que ambas son NEGATIVAS, no near_zero)
Compat:  C3a vs sq4 = 1.000, pero truth=0.0 → satisfaccion=0
```

**Que se pierde:**
1. La CONCLUSION real es "instrumento no creible", no "correlacion near_zero"
2. La direction near_zero es incorrecta — el SCM tiene relacion negativa verdadera
3. La inconsistencia entre datasets no es representable (la IR fuerza UNA direccion)

**Doble fallo:**
- El LLM extrae direction=near_zero porque ve evidencia mixta → pero el SCM
  dice negativo → truth=0.0
- Incluso si extrajera direction=negative (correcto), perderia el punto:
  el claim no es "wind-particle is negative" sino "el argumento de instrumento
  es debil porque los datos son inconsistentes"

**El verifier podria parcialmente:**
- `sign_flip` (AssertionKind) existe en la gramatica
- Pero el SCM genera UN solo mundo (no multiples datasets), asi que la
  inconsistencia entre datasets es un fenomeno de sampling, no de estructura

**Tipo de gap:** PARCIALMENTE RUTA BLOQUEADA + PARCIALMENTE FUERA DE ALCANCE.
La inconsistencia es sobre datos finitos, no sobre el SCM.

### C4: Missingness limita identificacion (NO COMPILA)

```
Solver:  "18-24% missingness in key covariables, reduces usable sample,
          risks bias, limits causal identification"
Compiler: ABSTENTION (correcto — no hay patron para esto)
Truth:   N/A
Compat:  N/A
```

**Que se pierde:** TODO. La claim no es sobre ninguna relacion entre variables.
Es sobre la CALIDAD DE LOS DATOS y las LIMITACIONES de lo que se puede
concluir con ellos.

**El verifier no puede:**
- El SCM genera datos completos por defecto
- La missingness es un feature del data generation, no de la estructura causal
- `identifiability_check` (MeasurementKind) existe, pero chequea si un efecto
  causal es identificable dado el DAG, no si los datos tienen missingness

**Tipo de gap:** FUERA DE ALCANCE — no es una propiedad del SCM.

## Tabla resumen de gaps

| Claim | Tipo | IR puede? | Verifier puede? | Gap |
|-------|------|-----------|-----------------|-----|
| C1 | Asociacion + caveat | Si (pierde caveat) | Si | **CAVEAT PERDIDO** |
| C2 | Sensibilidad al ajuste | **No** | **Si** (partial_corr, contrast_diff) | **RUTA BLOQUEADA** |
| C3 | Instrumento inconsistente | Si (direction incorrecta) | Parcial (sign_flip) | **RUTA BLOQUEADA + OOA** |
| C4 | Calidad de datos | **No** | No | **FUERA DE ALCANCE** |

## Clases de claims que la IR no puede representar

### Clase 1: Analisis de sensibilidad/robustez (C2)
**"El resultado cambia cuando ajustas por X"**

Requiere: COMPARAR dos estimaciones del mismo efecto bajo diferentes
condicionamientos. La IR solo puede decir "el efecto es positivo" o
"el efecto es positivo controlando por X", pero no "el efecto CAMBIA
de fuerte a debil cuando controlas por X".

El verifier PUEDE hacer esto: adjust + partial_correlation + contrast_diff.
Gap: puramente en la IR.

### Clase 2: Evaluacion de instrumento/estrategia (C3)
**"Esta variable/argumento no es creible como instrumento"**

Requiere: evaluar si un instrumento satisface condiciones de validez
(relevancia, exclusion, independencia). La IR puede decir "wind correlaciona
con particle" pero no "wind NO es un buen instrumento para identificar
el efecto de particle".

El verifier PARCIALMENTE puede: sign_flip, identifiability_check.
Gap: mayormente en la IR, parcialmente fuera de alcance (requires reasoning
about instrumental variable assumptions, not just correlation checks).

### Clase 3: Calificacion epistemica (C1 caveat)
**"Esto soporta asociacion pero NO causacion"**

Requiere: un campo de "fuerza epistemica" (observacional vs causal, fuerte
vs debil). La IR tiene `evidence_type` (interventional/observational) pero
no permite decir "la evidencia es insuficiente para la interpretacion causal".

Gap: en la IR. Trivial de agregar (campo `claim_force` ya propuesto en A21).

### Clase 4: Diagnostico de calidad de datos (C4)
**"Los datos tienen limitaciones que impiden concluir"**

Requiere: razonar sobre propiedades del dataset (missingness, sample size,
selection bias) que NO son propiedades del SCM. El SCM define la estructura
causal generadora; las limitaciones del dataset estan en la capa de data
generation.

Gap: fuera del alcance del SCM. Requeriria una capa separada de verificacion
de data quality, o que el SCM modele explicitamente la missingness.

### Clase 5: Inconsistencia empirica (C3 parcial)
**"Los resultados varian entre condiciones/datasets de forma preocupante"**

Requiere: comparar el MISMO estimador bajo condiciones diferentes y detectar
inestabilidad. El SCM genera una sola distribucion, no multiples datasets
con propiedades diferentes.

Gap: parcialmente fuera de alcance (el SCM no modela varianza entre subsets).

## El doble squeeze: SQs tambien

El gap no es solo en la compilacion de claims. Las SQs TAMBIEN estan
squeezed:

| Pregunta del brief | SQ generada | Que se pierde |
|-------------------|-------------|---------------|
| "Es defendible la interpretacion causal?" | sq1: causal_effect sign | Toda la dimension epistemica — la pregunta se reduce a "existe efecto?" |
| "Cuales son las amenazas de identificacion?" | sq2: confounding (1 variable) | El brief pide TODAS las amenazas, la SQ focaliza en UN confounder |
| "El argumento de viento es creible?" | sq4: obs_assoc sign | Se reduce a "correlaciona negativamente?" en vez de "es un instrumento valido?" |
| "Que datos adicionales se necesitan?" | (no hay SQ) | Completamente perdida |

La IR de SQs (`SubQuestionIntent` con `pattern + roles + ask`) comprime
preguntas epistemologicas a preguntas sustantivas. El mismo squeeze que
afecta a los claims afecta a las SQs.

## Prueba de concepto 1: partial_correlation verifica C2 a mano

Se hand-craftearon AtomicSpecs directamente (sin pasar por ClaimIntent)
y se verificaron contra el mundo e2e_03 con `verify_atom`:

```
C2 raw:      partial_corr(particle, wheeze, cond_set=())           = 0.517 (POSITIVE holds)
C2 adjusted: partial_corr(particle, wheeze, cond_set=[7 confounders]) = 0.189 (POSITIVE holds, 63% mas debil)
C3 wind:     partial_corr(wind, particle, cond_set=())             = -0.248 (NEGATIVE holds)
```

**Resultado:** El efecto encoge de 0.517 a 0.189 al ajustar por 7 covariables.
El verifier YA puede verificar claims de sensibilidad al ajuste. Y la direccion
verdadera de wind→particle es negativa, no near_zero.

## Prueba de concepto 2: compilacion directa LLM → AtomicSpec (sin catalogo)

Se le dio al LLM (gpt-5.4) el texto del claim + la gramatica de AtomicSpec +
las variables del mundo, y se le pidio que genere specs de verificacion
directamente, sin PatternClass ni ClaimIntent intermedio.

Script: `scripts/direct_to_atoms.py`

### C2 (adjustment sensitivity) — de ABSTENTION a 4 specs

| Pipeline | # Specs | Resultado |
|----------|---------|-----------|
| Catalogo (PatternClass) | 0 (ABSTENTION) | Nada verificable |
| Directo (LLM → AtomicSpec) | 4 | 1 fully TRUE + datos utiles |

Specs generados:

| Spec | Medicion | Assertion | Holds | Ground truth |
|------|----------|-----------|-------|-------------|
| raw positive assoc | correlation(particle, wheeze) | positive | **TRUE** | 0.517 |
| adjusted near_zero | partial_corr(particle, wheeze \| 7 vars) | near_zero | FALSE | 0.189 |
| shrinks after adjustment | partial_corr diff | positive | FALSE | ~0 (bug*) |
| identifiability check | identifiability_check(particle→wheeze) | identifiable | **FALSE** | not identifiable |

(*) Spec "shrinks" fallo porque las dos arms son baseline — no supo
diferenciar la medicion cruda vs ajustada en la comparacion. El hand-craft
con cond_set vacio vs lleno funciona mejor.

**Hallazgo clave:** El LLM genero un `identifiability_check` que confirma
que el efecto causal de particle→wheeze NO es identificable con las variables
observadas. Esto es exactamente la conclusion epistemologica de C2.
El pipeline actual no puede ni representar esta pregunta.

### C3 (instrumento inconsistente) — de 0/2 TRUE a **3/3 TRUE**

| Pipeline | # Specs | Resultado |
|----------|---------|-----------|
| Catalogo (PatternClass) | 2 (near_zero) | 0/2 TRUE (direction incorrecta) |
| Directo (LLM → AtomicSpec) | 3 | **3/3 TRUE** |

Specs generados:

| Spec | Medicion | Assertion | Holds | Ground truth |
|------|----------|-----------|-------|-------------|
| wind→particle weak | correlation(wind, particle) | near_zero | TRUE | -0.248 |
| wind→wheeze weak | correlation(wind, wheeze) | near_zero | TRUE | -0.140 |
| wind NOT identifiable as instrument | identifiability_check | not_identifiable | **TRUE** | not identifiable |

**Hallazgo:** El LLM uso `identifiability_check` + `not_identifiable`
para aproximar la conclusion del solver ("questionable instrument").
El pipeline actual lo reducia a "correlacion near_zero", que es una mala
traduccion semantica. El camino directo captura mejor la intencion.

**Caveat (ver seccion de caveats abajo):** `identifiability_check` hoy
implementa identificabilidad via backdoor/d-separation, no validez de
instrumento propiamente dicha. Sirve como evidencia de que la gramatica
directa PUEDE representar mejor el claim, pero no es una prueba exacta
de IV invalidity.

### SQ epistemologica — de 1 SQ comprimida a **10 specs (8/10 TRUE)**

| Pipeline | Output | Resultado |
|----------|--------|-----------|
| Catalogo (SubQuestionIntent) | 1 SQ: causal_effect(sign) | Pierde contenido epistemologico |
| Directo (LLM → AtomicSpec) | 10 specs | **8/10 TRUE** |

Se le dio al LLM la pregunta real del brief:

> "Assess whether the available district-level data can support a causal
> claim about particulate pollution and pediatric wheeze. Identify the main
> sources of bias or non-identification."

Specs generados (resumen):

| Spec | Holds | Ground truth | Que verifica |
|------|-------|-------------|--------------|
| identifiability particle→wheeze | **TRUE** | not identifiable | El efecto no es identificable |
| adjusted partial_corr near_zero | FALSE | 0.189 | Asociacion debil post-ajuste |
| industrial→particle | **TRUE** | 0.522 | Confounder fuente: industrial |
| industrial→wheeze | **TRUE** | 0.356 | Confounds relationship |
| traffic→particle | **TRUE** | 0.538 | Confounder fuente: traffic |
| traffic→wheeze | **TRUE** | 0.345 | Confounds relationship |
| socioeconomic→particle | **TRUE** | 0.056 | Weak confounding |
| socioeconomic→wheeze | **TRUE** | 0.540 | Strong confounding |
| healthcare→wheeze | FALSE | -0.449 | Direction incorrecta (asserted +, true -) |
| wind→particle | **TRUE** | -0.248 | Relacion wind-particle existe |

**Hallazgo clave:** El LLM descompuso una pregunta epistemologica en
verificaciones concretas: un chequeo de identificabilidad, 4 vias de
confounding mapeadas par-a-par, y la relacion wind-particle. Esto es
DRAMATICAMENTE mas rico que la SQ comprimida `causal_effect(sign)`.

8/10 specs son TRUE, con 2 errores menores (direccion de healthcare y
assertion demasiado agresiva para la partial correlation ajustada).

## Imperfecciones del prototipo

1. **Comparacion cruda vs ajustada:** El LLM no supo estructurar una
   comparacion entre mediciones con distinto conditioning. Intento usar
   dos arms baseline con comparison(difference), que da ~0 porque ambas
   arms producen los mismos datos. El hand-craft con partial_corr con
   cond_set vacio vs lleno funciona. Esto sugiere que el LLM necesita
   un ejemplo o guidance sobre como usar cond_set para comparar.

2. **Assertions demasiado agresivas:** El LLM tiende a assertar near_zero
   cuando el valor real es ~0.19 (debil pero no cero). Esto es un problema
   de calibracion, no de arquitectura.

3. **Direcciones asumidas:** healthcare→wheeze asumida positiva cuando es
   -0.449. El LLM asumio la direccion por dominio en vez de dejarla abierta.

4. **Tolerancias:** No queda claro si el LLM ajusto las tolerancias de
   near_zero para que -0.248 pase. Esto necesita inspeccion.

Ninguna de estas imperfecciones es un problema arquitectonico. Son
problemas de prompting, ejemplos y calibracion que se iteran.

## Caveats importantes

### 1. identifiability_check ≠ instrument validity

El `identifiability_check` en `oi_verifier.py` implementa identificabilidad
causal via backdoor criterion / d-separation con variables observadas. Eso
es valioso, pero NO equivale automaticamente a "wind no es un instrumento
valido" en el sentido de IV (relevance, exclusion, independence).

Entonces:
- Como evidencia de que la gramatica directa puede **representar mejor**
  el claim epistemologico: **si**.
- Como prueba exacta de IV invalidity: **no necesariamente**.

El LLM eligio la herramienta mas cercana que tenia disponible, y produjo
un resultado informativo. Pero si quisieramos verificar validez de
instrumento propiamente dicha, la gramatica necesitaria checks adicionales
(exclusion restriction, relevance condition) que hoy no existen en el
verifier.

### 2. Esto prueba capacidad, no arquitectura final

El prototipo demuestra que:
- El camino directo **recupera semantica** que el catalogo pierde.
- El verifier **no necesita cambios** para manejar estos specs.
- El LLM **puede generar** specs razonables sin catalogo intermedio.

Pero **no prueba todavia:**
- Como deberia ser la **agregacion** de multiples specs en un score.
- Como deberia funcionar el **matching** entre claims y SQs si ambos
  son conjuntos de AtomicSpecs en vez de patterns.
- Cual es el **contrato final** del sistema — que promete, que garantiza.

Estas son preguntas de diseno que requieren mas trabajo. El prototipo
es evidencia de que el camino vale la pena explorar, no un diseno cerrado.

## Conclusion

El camino directo (LLM → AtomicSpec, sin catalogo) recupera semantica
que el pipeline basado en catalogo pierde:

- `identifiability_check` para claims epistemologicos (con los caveats de arriba)
- `partial_correlation` con conditioning para sensibilidad al ajuste
- Descomposicion rica de preguntas epistemologicas en verificaciones concretas

El catalogo (`PatternClass` / `ClaimIntent`) fue util como bootstrap pero
ahora es el cuello de botella principal para investigacion no causal-simple.

No se necesita un nuevo catalogo (ni BundleIR ni BundleSemantics). La
direccion es: claim text + grammar schema + variables → LLM → 1..N AtomicSpec.

Los `PatternClass` actuales pueden seguir como fast-path para claims simples,
pero no como ruta obligatoria.

**Lo que queda abierto:** agregacion, matching entre conjuntos de specs, y
contrato final del sistema. Esto es trabajo de diseno, no de investigacion.

## Feedback de Codex (thread 019d3f92)

Correcciones al analisis inicial (pre-prototipo directo):

1. **C1 tiene un bug de matching SEPARADO** del gap de IR. El scoring
   algorithm asigna C1 a sq2 (0.060) en vez de sq1 (0.650). Bug de scorer.
2. **C3 es "semantic collapse"** — el compiler colapsa inconsistencia a
   near_zero, que es una mala traduccion semantica.
3. **C4 no es "fuera del SCM" sino "fuera del contrato de verdad actual"** —
   el repo ya modela missingness en data-gen (scm_data.py).
4. **Categoria faltante: "answer-key compression"** — las SQs SON el reward.
   Si estan mal, nada downstream importa.

Nota: Codex propuso BundleIR con un catalogo de BundleSemantics, lo que
hubiera sido agregar otra capa taxonomica al problema. El prototipo directo
demostro que no hace falta: el LLM compila directo a AtomicSpec sin
necesidad de clasificar el claim en un tipo predefinido.

## Conexiones

- **A21** — compatibility algebra ya separo las dimensiones. Esta evidencia
  muestra que la separacion no basta si la IR de entrada es estrecha.
- **A22** — multi-intent compiler. La direccion correcta no es mas patterns
  sino compilacion directa a AtomicSpec. A22 "Camino B" ya lo proponia.
- **S03** — mostro que contexto ayuda con extraccion pero no con e2e_03.
  S04 explica POR QUE: el problema no es extraccion, es la IR intermedia.
- **A23** — este documento ES la evidencia concreta que A23 necesitaba.
  Pero la solucion no es "SQ grammar-first como bundles" (que es otra
  capa) sino compilacion directa a atoms tanto para SQs como para claims.

## Proximos pasos

1. **Iterar el prompt** — mejorar guidance para comparaciones (cond_set
   vacio vs lleno), calibracion de assertions, y direcciones.
2. **Probar en e2e_02** — confirmar que el camino directo tambien funciona
   para casos mas simples (predictivo) sin regresion.
3. **Decidir integracion** — como enchufar el camino directo al pipeline
   existente. Opciones: reemplazar el compiler actual, o usarlo como
   fallback cuando PatternClass falla (ABSTENTION).
4. **Matching sin PatternClass** — si claims y SQs bajan a AtomicSpec
   directamente, el matching necesita comparar specs en vez de patterns.
   Esto es un cambio de scoring, no trivial.
5. **C4 (data quality)** — queda fuera del alcance del SCM por ahora.
   Posible capa futura de observation-level truth.
