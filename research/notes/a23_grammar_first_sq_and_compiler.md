# A23 — Grammar-first para SQ y compiler: evitar sesgo al catalogo conocido

**Date:** 2026-03-30
**Type:** Autoresearch — diagnostico cualitativo post-S02/S03
**Branch:** autoresearch-open-investigation
**Status:** PROPUESTA. Prioridad alta para la proxima ronda arquitectonica.
**Prerequisitos:** A21 (compatibilidad algebra), A22 (multi-intent compiler), S02/S03 (forensics E2E)

> **LA PREGUNTA filter**: el problema actual es "extraccion LLM floja", o
> estamos forzando tanto las SQ como los claims a pasar por un catalogo
> demasiado estrecho de patterns conocidos? Si la gramatica atomica ya es
> rica, por que seguimos perdiendo credito en casos no causal-simple?

## Tesis

El cuello principal ya no parece ser falta de expresividad del verifier.
La gramatica composable de `open_investigation.py` ya puede representar
mucho mas de lo que hoy usamos en practica.

El problema es anterior:

1. **Las SQ ocultas nacen sesgadas al catalogo conocido** (`pattern + roles + ask`)
   en vez de compilarse desde la necesidad real del brief.
2. **Los claims del solver tambien se comprimen demasiado temprano** a
   `ClaimIntent` + `PatternClass`, incluso cuando la conclusion real es
   compuesta, epistemologica o metodologica.
3. Como resultado, el sistema esta sobre-ajustado a **causal simple**:
   treatment -> outcome, signo, ranking, heterogeneidad textbook,
   confounding textbook.

La direccion correcta no es agregar infinitos patterns fijos.
La direccion correcta es:

- **usar patterns como fast-path**, no como ontologia obligatoria;
- **compilar SQ mas cerca de AtomicSpec bundles**;
- **darle al compiler de claims un fallback directo a gramatica atomica**
  cuando no encaja en recetas conocidas.

## Distincion clave: verifier rico vs IR estrecha

### Lo que YA existe

La gramatica de verificacion en `open_investigation.py` ya soporta:

- multiples `QueryKind` (`intervene`, `observe`, `condition`, `adjust`, `sweep`)
- multiples `MeasurementKind` (`mean`, `correlation`, `partial_correlation`,
  `identifiability_check`, etc.)
- multiples `ComparisonKind` (`difference`, `ranking`, `gap`, `contrast_diff`, etc.)
- multiples `AssertionKind` (`positive`, `negative`, `near_zero`,
  `rank_order`, `not_identifiable`, `not_distinguishable`, etc.)

En otras palabras: el verifier no es "catalogo fijo". Ya tenemos piezas
atomicas suficientemente expresivas.

### Donde se cierra el espacio

Hoy las dos entradas al sistema pasan por IRs estrechas:

```
SQ -> SubQuestionIntent(pattern + roles + ask) -> ClaimIntent candidato -> lower_intent() -> AtomicSpec(s)
Claim -> ClaimIntent(pattern + roles) -> lower_intent() -> AtomicSpec(s)
```

Eso mete un sesgo fuerte antes de llegar al verifier.

La pregunta correcta no deberia ser:

- "que pattern es esto?"

Deberia ser:

- "que atoms hacen falta para verificar esta conclusion?"

## Evidencia cualitativa reciente

### e2e_02_vaca_predictive

La claim C1 del solver combina:

- ranking de importancia (`zone_risk_index` > `coordinate_risk_index`)
- afirmaciones pairwise positivas sobre ambos drivers
- caveat de magnitud / prioridad

El compiler actual la comprime a `effect_ranking` y pierde la afirmacion
pairwise `zone_risk_index -> sanding_risk`. La SQ correspondiente despues
falla por falta de ese atom, no porque el mundo no pueda verificarlo.

**Lectura:** claim compuesta valida, pero el catalogo obliga a elegir una sola
receta canonica.

### e2e_03_epistemic

El brief real pregunta por:

- si la interpretacion causal es defendible
- amenazas de identificacion
- credibilidad del argumento con viento
- que faltaria medir

Pero las SQ ocultas terminan bajando a formas mucho mas estrechas:

- asociacion `proxy -> wheeze`
- confounding industrial emissions
- signo de `wind -> proxy`
- ranking de drivers

El solver, en cambio, produce claims sobre:

- asociacion observacional
- sensibilidad al ajuste
- instrumento debil / inconsistente entre datasets
- missingness que limita identificacion

Dos claims importantes (`instrumento no creible`, `faltan datos para
identificar`) terminan en abstention porque no entran comodamente en los
patterns actuales. Pero el problema ya empieza antes: las SQ tampoco
representan fielmente el tipo de investigacion del brief.

**Lectura:** no es solo mala extraccion; hay desalineacion entre brief,
SQ y catalogo de patterns.

### e2e_05_confounding

Este caso se comporta mejor porque SI calza en la ontologia actual:

- crude negative association
- confounding by indication
- adjusted positive effect

Pero incluso aca aparece otro sintoma: el scorer llega a premiar una claim
broad de efecto ajustado por encima de una claim explicita de confounding.

**Lectura:** cuando todo entra en causal-simple el sistema "funciona", pero
todavia depende demasiado de proxies semanticos via pattern.

## Conclusiones

1. **No falta expresividad del verifier.** Falta usarla antes.
2. **El catalogo conocido esta sobrerrepresentado** en ambas entradas:
   SQ y claims.
3. **El sesgo a causal simple nace aguas arriba del scoring.**
4. **Mejorar prompts de extraccion ayuda, pero no resuelve el problema
   estructural** si la IR sigue cerrada.

## Direccion propuesta

### Paso 1: SQ grammar-first

Como las SQ son ocultas al solver, este es el mejor lugar para ser mas
expresivos sin riesgo de sesgo.

Direccion:

- dejar `text_gloss` para legibilidad humana
- permitir que una SQ se exprese como **bundle de atoms verificables**
  o como una receta composicional mas cercana a `AtomicSpec`
- no obligar a toda SQ a ser `pattern + roles + ask`

Objetivo: que briefs epistemologicos, metodologicos o de system-mapping
no se compriman automaticamente a causal simple.

### Paso 2: compiler hibrido para claims

- mantener `PatternClass` como fast-path para casos comunes
- cuando el claim no encaja limpiamente:
  - descomponer en 1..N fragmentos/atoms
  - compilar directo a gramatica atomica
- no abstener solo porque la conclusion no coincide con una receta conocida

Objetivo: pasar de "clasificar claim" a "construir verificaciones".

### Paso 3: matching/scoring menos dependiente de pattern

Si SQ y claims empiezan a bajar a bundles mas ricos, el matching no puede
seguir dependiendo principalmente de `pattern + roles`.

Necesitamos una nocion de compatibilidad mas semantica entre bundles de specs:

- overlap de variables
- tipo epistemologico de la conclusion
- compatibilidad entre assertions/comparisons
- completitud parcial del bundle

## Lo que NO priorizamos por ahora

**Formalizar mas los claims del solver** (por ejemplo pedir JSON mas
estructurado) puede ayudar como mitigacion pragmatica, pero no es la
solucion principal.

Riesgos:

- sesga el estilo de conclusion del solver
- maquilla el problema sin arreglar la ontologia intermedia
- sigue dejando al sistema preso del catalogo si todo termina en pattern

Se puede retomar despues, pero no deberia liderar esta ronda.

## Decision provisional

Para la proxima ronda, la prioridad deberia ser:

1. **SQ directas a bundles atomicos / grammar-first**
2. **Compiler de claims con fallback directo a AtomicSpec**
3. **Matching menos anclado a pattern**
4. **Claim formalization** solo como mitigacion secundaria si hace falta

## Preguntas abiertas

1. Cual es la mejor IR para una SQ grammar-first: `AtomicSpec` directo,
   receta composicional intermedia, o bundle con metadata epistemologica?
2. Como preservar legibilidad humana de las SQ si dejamos de usar
   `pattern + roles + ask` como superficie principal?
3. Que partes del scoring actual se pueden reutilizar y cuales asumen
   demasiado fuerte la existencia de `pattern`?
4. Como evitar specs absurdos en el fallback del compiler sin volver a
   cerrar demasiado la gramatica?

## Conexiones

- **A21** — separo compatibilidad ontologica del hard mismatch 0/1.
- **A22** — ya planteo patterns como fast-path; A23 extiende esa idea
  al lado de las SQ y muestra que el sesgo entra por ambos lados.
- **S02** — mostro coverage como cuello principal.
- **S03** — mostro que mejorar contexto de extraccion ayuda, pero no
  explica por si solo los casos epistemologicos.
