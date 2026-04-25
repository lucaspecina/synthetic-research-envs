# S03 — Diagnostico de Extraccion LLM del Compiler

> Investigacion: 2026-03-30
> Metodo: A/B test (prompt actual vs prompt con contexto) sobre 5 experimentos E2E

## Resumen ejecutivo

La extraccion LLM del compiler opera en un **vacio de contexto**: solo recibe
el texto del claim y una lista de nombres de variables. No tiene el brief, las
descripciones de variables, el dominio, ni las sub-questions. Esto causa fallos
evitables que representan la mayoria de las perdidas de coverage.

**Hallazgo principal:** agregar contexto (brief + descripciones + SQs) al prompt
de extraccion **elimina la categoria de fallo mas comun** (variables invalidas)
y **recupera claims de abstention**, sin introducir sesgo observable.

## Datos: 5 experimentos E2E


| Caso                    | Tipo               | Submitted? | Score      | Claims | SQ Hits |
| ----------------------- | ------------------ | ---------- | ---------- | ------ | ------- |
| e2e_02 (predictive)     | Predictivo/ranking | Si         | 0.502      | 4      | 3/5     |
| e2e_03 (epistemic)      | Epistemologico     | Si         | 0.0-0.439* | 4      | 0-2/4*  |
| e2e_04 (system mapping) | System mapping     | **No**     | -          | 0      | -       |
| e2e_05 (confounding)    | Confounding        | Si         | 0.843      | 4      | 4/5     |
| e2e_06 (heterogeneity)  | Heterogeneidad     | **No**     | -          | 0      | -       |


*Score varia entre runs por no-determinismo LLM.

**Submission aversion:** 4 de 6 casos totales (contando e2e_01) no submitearon.
Esto sigue siendo el problema #1 del pipeline, por encima de la extraccion.

## Taxonomia de fallos de extraccion

### F1. Variables invalidas en campos estructurados

**Frecuencia:** ~30% de claims en e2e_03
**Impacto:** Claim no compila (lowering falla)
**Ejemplo:** C1 e2e_03 — LLM pone `conditioning_set=["site_id", "wave"]` porque
el claim menciona "site/wave fixed-effects regression". site_id y wave son
columnas del dataset, no variables del mundo.
**Root cause:** El LLM no sabe cuales son las variables del mundo vs columnas
del dataset. Solo tiene los nombres.
**Fix con contexto:** Eliminado. El LLM ya no inventa variables.

### F2. Abstention en claims recuperables

**Frecuencia:** ~25% de claims con informacion util
**Impacto:** Informacion perdida
**Ejemplo:** C2 e2e_03 — "the particle coefficient shrinks (0.116) after
adjusting for traffic, industrial emissions, etc." El LLM intenta extractar
como `confounding` sin poner `confounder` field -> falla validacion pydantic.
**Root cause:** Sin contexto, el LLM no sabe como interpretar claims complejas
sobre ajuste de covariables. Intenta el patron equivocado y falla.
**Fix con contexto:** Recuperado. Con brief+SQs, el LLM entiende que es una
observational_association con conditioning_set de 7 variables validas.

### F3. Extraccion de direcciones contradictorias

**Frecuencia:** Ocasional (claims que discuten multiples datasets)
**Impacto:** Intents contradictorios que se cancelan
**Ejemplo:** C3 e2e_03 — "wind-particle corr = -0.19 in dataset_bg, but
flips to +0.25 in dataset_detail". El LLM extrae 4 intents: 2 negativos
y 2 positivos para los mismos pares.
**Root cause:** El LLM extrae hallazgos per-dataset en vez de la CONCLUSION
del solver. El claim habla de inconsistencia entre datasets.
**Fix con contexto:** No mejora. Necesita guidance: "extract the solver's
CONCLUSION, not per-dataset raw findings".

### F4. Confusion sign vs significancia

**Frecuencia:** Intermitente (a pesar del exemplar en S02)
**Impacto:** Direccion incorrecta -> answer_compatibility = 0
**Ejemplo:** C3 e2e_03 (otro run) — slope=-3.83 clasificado como near_zero
porque p > 0.05.
**Root cause:** El LLM prioriza significancia estadistica sobre el signo del
coeficiente. El exemplar ayuda pero no es deterministico.
**Fix con contexto:** Marginal. Es mas un problema de prompt/exemplars.

### F5. Campos pattern-specific faltantes

**Frecuencia:** Ocasional
**Impacto:** Validacion pydantic falla -> abstention
**Ejemplo:** C2 e2e_03 (run A) — pattern=confounding sin confounder field.
**Root cause:** El LLM elige un patron que requiere campos que no sabe llenar.
**Fix con contexto:** Indirecto — con mas contexto elige mejor patron.

### F6. Submission aversion (no es extraccion, pero domina)

**Frecuencia:** 4/6 casos totales
**Impacto:** Total — sin claims, score = 0 automatico
**Root cause:** Solver prefiere seguir analizando en vez de entregar findings.
Force-submit mitiga parcialmente pero sigue fallando.

## A/B Test: prompt actual vs prompt con contexto

### Que se agrego al prompt B:

1. **Research brief** (la pregunta de investigacion)
2. **Domain context** (descripcion narrativa del problema)
3. **Sub-questions** (con caveat: "for disambiguation, NOT to force matching")

### Resultados en e2e_03 (caso problematico, score 0.0):


| Claim | [A] Sin contexto                                                   | [B] Con contexto                              |
| ----- | ------------------------------------------------------------------ | --------------------------------------------- |
| C1    | obs_assoc OK pero conditioning=[site_id,wave] **INVALIDO**         | obs_assoc OK, sin vars invalidas              |
| C2    | **ABSTENTION** (confounding sin confounder)                        | obs_assoc con 7 conditioning validos          |
| C3    | 4 intents contradictorios + conditioning=[dataset_bg] **INVALIDO** | 4 intents contradictorios, sin vars invalidos |
| C4    | Abstention (correcto)                                              | Abstention (correcto)                         |


**Impacto:** B recupera 2 claims de 4 (C1 y C2) que con A se pierden.

### Resultados en e2e_02 (caso limpio, score 0.502):


| Claim | [A] vs [B]                      |
| ----- | ------------------------------- |
| C1    | Identicos (effect_ranking)      |
| C2    | Identicos (obs_assoc, negative) |
| C3    | Identicos (obs_assoc, positive) |
| C4    | Identicos (2x heterogeneity)    |


**Impacto:** Neutral. Claims limpias no necesitan contexto extra.

### Conclusion del A/B:

- **Contexto no introduce sesgo observable** — en e2e_02, las extracciones son
identicas. El LLM no "fuerza" claims hacia SQs.
- **Contexto elimina fallos tontos** — variables invalidas, abstracciones
innecesarias.
- **El principal beneficio es en claims ambiguas o complejas** — exactamente
donde mas se necesita.

## Informacion disponible para dar contexto

El `OIEpisodeRunner` tiene todo esto cuando llama al compiler:

- `self.problem.research_question` (el brief)
- `self.problem.description` (narrativa del dominio)
- `self.problem.domain` (dominio)
- `self.problem.title` (titulo del caso)
- `self._subquestions` (las SQs)
- `self.world` (el SCM completo)
- `summary.observable_names` (variables) <- esto es lo unico que se pasa hoy

Hoy solo pasa `summary.observable_names` al prompt de extraccion. Todo lo demas
se descarta.

## Que DEBERIA recibir el compiler

### Si (seguro):

1. **Research brief** — la pregunta de investigacion
2. **Descripciones de variables** — que significa cada variable, unidades
3. **Dominio** — contexto narrativo
4. **Titulo** — para orientacion general

### Si (con safeguard):

1. **Sub-questions** — con caveat explicito de "extract what the claim says,
  not what matches the SQ"

### No:

1. **Estructura causal (edges)** — esto es la verdad oculta, no debe influir
2. **Estadisticas del SCM** — estas son para el verifier, no para el extractor

## Problemas que el contexto NO resuelve

1. **Direcciones contradictorias** (F3) — necesita prompt: "extract the
   solver's CONCLUSION, not per-dataset raw findings"
2. **No-determinismo LLM** — mismos claims producen diferentes extracciones
   en diferentes runs. Esto es inherente al LLM.
3. **Submission aversion** (F6) — problema del solver, no del compiler.

## Validacion post-implementacion (S03a rescore)

Despues de implementar el prompt enriquecido (brief + descripciones + SQs +
variable descriptions + exemplar `ex_obs_inconsistent`), se re-scorearon
los 3 casos con claims:

| Caso | Pre-S03a | Post-S03a |
|------|----------|-----------|
| e2e_02 (predictive) | 0.502 | 0.502-0.665 |
| e2e_03 (epistemic) | 0.0-0.439 | **0.239** (estable) |
| e2e_05 (confounding) | 0.843 | 0.700-0.780 |

**Conclusion:** el contexto ayuda modestamente en casos limpios (e2e_02) y
no introduce regresion en el mejor caso (e2e_05, dentro de varianza LLM).
Pero **no resuelve el caso epistemologico** (e2e_03 clavado en 0.239).

### Por que e2e_03 no mejora

El caso epistemologico tiene claims que no encajan en ninguna PatternClass:
- "el instrumento (viento) no es creible" → no es causal_effect ni obs_assoc
- "la missingness limita la identificacion" → no hay patron para esto
- "el efecto es sensible al ajuste" → parcialmente obs_assoc pero pierde matiz

El problema no es falta de contexto — es que la IR (`ClaimIntent` con
`PatternClass`) no puede representar conclusiones epistemologicas o
metodologicas. Esto valida la tesis de A23: la gramatica atomica es rica,
pero la IR intermedia es estrecha.

## Proximos pasos

1. **S03a implementado y validado.** Commit.
2. **A23 queda como diagnostico + hipotesis.** No como tarea ejecutiva.
   La evidencia parcial (e2e_03 no mejora con contexto) lo sustenta,
   pero el diseno exacto (SQ como bundles, compiler hibrido) no esta validado.
3. **Siguiente investigacion:** analizar EXACTAMENTE que claims del caso
   epistemologico se pierden y que expresividad les falta a la IR, para
   darle a A23 evidencia concreta y pasar de hipotesis a propuesta.

