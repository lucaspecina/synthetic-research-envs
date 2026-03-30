# S01 — Compiler Multi-Unit + Claim Diversity

**Fecha:** 2026-03-29
**Branch:** autoresearch-open-investigation
**Status:** EN CURSO
**Codex thread:** 019d3b67-eb81-7201-9151-9aa26e54ac24

## Pregunta de investigacion

Como hacer que el compiler traduzca claims compuestos Y claims no-pair
(system mapping, predictivo, epistemologico, etc.) a verificaciones
ejecutables contra el SCM?

## Hallazgos del debate (pre-empirico)

### H1: Multi-unit es fix tactico, no solucion general
- Multi-unit (1 claim → N unidades verificables) resuelve ~10/20 escenarios
  (los que tienen claims causales compuestos).
- Los otros ~10 escenarios producen claims que NO son pares treatment→outcome:
  "nodo 4 es critico", "hay 3 clusters", "RMSE=4.2", "efecto no identificable".
- Decision: implementar multi-unit como Fase 1, pero no tratarlo como arquitectura final.

### H2: ClaimIntent no puede ser IR universal
- ClaimIntent (8 patterns, 1 treatment, 1 outcome) solo cubre claims causales/asociativos.
- La arquitectura correcta: ClaimIntent como uno de varios "backends de lowering".
- Futuro: backends para structure, identifiability, predictive, etc.

### H3: Solver hints opcionales > solver structured obligatorio
- Obligar al solver a formalizar = form-filling = "juego" (viola principio scoring #4).
- Hints opcionales semanticos (claim_family, assertion_type) = bueno para routing.
- El hint NO debe parecerse a AtomicSpec (no ejecutable, solo semantico).

### H4: CompiledUnit preserva intent→specs
- Bug encontrado por Codex: flattenear specs de N intents pierde mapping.
- Solucion: CompiledUnit(unit_id, intent, specs) dentro de CompilerOutput.
- CompilerOutput sigue 1:1 con ClaimCard (warranty/trace/efficiency keyed por claim_id).

### H5: 3 clases de claims no-pair
1. **Exactificables con nuevos operadores**: identifiability, VOI, structure/paths,
   optimization — el SCM ya tiene la info, solo faltan operadores formales.
2. **Requieren extender formal layer**: predictive protocol, clustering, method comparison
   — necesitan definir train/test, metricas, protocolos.
3. **No core todavia**: demasiado abiertos para reward exacto hoy.

## Experimentos pendientes

### E1: Multi-unit con soil case
- Implementar multi-unit minimo.
- Correr soil case (3/4 ABSTENTION hoy).
- Target: C1 y C3 dejan de ser ABSTENTION, score > 0.

### E2: Coral no-regresion
- Correr coral case con multi-unit.
- Target: score no baja (oversplitting check).

### E3: Probar claim diversity con LLM
- Dar al solver un caso tipo system mapping (#6) o structure discovery (#9).
- Ver que claims produce realmente.
- Evaluar cuantos compila el compiler actual vs cuantos deberia compilar.

## Resultados empiricos

### E3: Logistics system mapping (2026-03-29)

**Caso:** supply chain logistics, 10 nodes, system mapping. Solver=gpt-5.2-codex, Compiler=gpt-5.4.
**Score: total=0.470, correctness=1.000, coverage=0.119**

| Claim | Tipo real | Compiler | Problema |
|-------|----------|----------|----------|
| C1 | Ranking de correlaciones | COMPILED (effect_ranking) | No matchea sq4 (ranking causal vs observacional) |
| C2 | Regression summary: "X pierde significancia controlando M" | **ABSTENTION** | Nuevo tipo: screening_off/bottleneck_mediation |
| C3 | Chain: 4 variables → warehouse_processing_time | **ABSTENTION** | **A22 exacto**: "multiple distinct effects" |
| C4 | Pairwise: carrier ~ port_congestion + weather | COMPILED | OK |
| C5 | Interaction: routing * carrier → compounding delays | COMPILED (heterogeneity) | Matchea sq3 parcial |

**Hallazgos clave:**
1. C3 es A22 puro — multi-unit lo resuelve
2. C2 es un tipo NUEVO (screening_off): "A pierde efecto al controlar M → el pathway real es A→M→Y"
   - Verificable contra SCM: partial_corr(X,Y|M) ≈ 0 AND partial_corr(X,M) ≠ 0 AND corr(M,Y) ≠ 0
   - Codex propone formalizarlo como full_mediation observacional
3. C1 vs sq4: ranking observacional vs causal. Correcto que no matchee full.
4. Solver investiga BIEN (correctness=1.000). Compiler es el bottleneck.

### Orden de fixes propuesto (Codex + Claude coinciden)
1. **A22 multi-unit** — arregla C3 (logistics) + C1/C3 (soil). ROI inmediato.
2. **screening_off pattern** — arregla C2 (logistics). Tipo nuevo para system mapping.
3. **association_ranking vs effect_ranking** — distinguir rankings obs vs causales.

## Resultados empiricos post-A22

### E1: Soil (2026-03-29)

**Caso:** agricultural basin, 8 nodes, contamination + crop health. seed=42.
**Score ANTES (baseline): total=0.200, correctness=0.000, coverage=0.000, 0/5 SQs**
**Score DESPUES (A22): total=0.980, correctness=1.000, coverage=0.686, 4/4 SQs**

| Claim | Tipo | Unidades compiladas | SQ matched |
|-------|------|---------------------|------------|
| C1 | Correlaciones cruzadas | 1 unit (obs_assoc) | sq1, sq2 |
| C2 | Chain: metal→uptake→chlorosis→health | **3 units** (obs_assoc x3) | sq5 (via C2::1) |
| C3 | Co-occurrence: acidity+metal→health | **3 units** (obs_assoc x3) | — |
| C4 | Interaction: metal × rainfall | 1 unit (heterogeneity) | sq3 |
| C5 | Residual site effects | ABSTENTION (site_id not in world) | — |

**Hallazgo clave:** Multi-unit funciona exactamente como se diseño. C2 chain
(3 relaciones) se descompone en 3 unidades verificables independientes.

### E2: Coral (2026-03-29)

**Score: total=0.807, correctness=1.000, coverage=0.475, 3/4 SQs**

| Claim | Tipo | Unidades compiladas | SQ matched |
|-------|------|---------------------|------------|
| C1 | Heat→coral | 1 unit | sq1 |
| C2 | Chain: nutrients→algae→clarity→recruitment→coral | **4 units** | sq2, sq3 (via C2::3 mediation) |
| C3 | Grazing→algae→coral | **3 units** | — |
| C4 | Site residuals | ABSTENTION (site_id) | — |

**No regresion confirmada.** Score alto y multi-unit compilando bien.

### E3v2: Logistics (2026-03-29)

**Score ANTES (baseline E3): total=0.470, correctness=1.000, coverage=0.119, 2/5 SQs**
**Score DESPUES (A22): total=0.551, correctness=1.000, coverage=0.181, 1/4 SQs**

Mejora modesta. El gap aqui es del **solver** (no investiga las variables que los SQs
esperan), no del compiler. C3 y C4 ahora compilan como multi-unit en vez de ABSTENTION.

## Conclusiones post-A22

1. **A22 resuelve el problema de claims compuestos.** soil: 0.200→0.980, coral: 0.807, logistics: +0.08.
2. **El compiler ya no es el bottleneck principal.** Ahora lo es:
   - **Cobertura del solver:** el solver no siempre investiga lo que los SQs esperan.
   - **Patrones faltantes:** screening_off, association_ranking (de E3 original).
   - **site_id claims:** solver genera claims con "site_id" que no existe en el SCM.
3. **ClaimIntent como IR:** funciona bien para claims causales/asociativos compuestos.
   Sigue limitado para claims no-pair (ver H2, H5).
4. **Partial status:** funciona correctamente. No hizo falta en estos 3 E2Es
   (todas las unidades validas compilaron ok).
5. **unit_id convention limpiada:** claim_id::0, claim_id::1, etc. Consistente.

## S02: Coverage forensics post-A22

### Auditoria de misses (12 SQs across 3 cases)

| Caso | SQ | Patron | Tier | Result | Miss category | Notas |
|------|-----|--------|------|--------|--------------|-------|
| soil | sq1 | causal_effect | HIGH | HIT (0.65) | — | C1::0 |
| soil | sq2 | mediation | HIGH | HIT (0.28) | — | C1::0 (low sat, fragil) |
| soil | sq3 | heterogeneity | HIGH | HIT (1.00) | — | C4::0 |
| soil | sq5 | obs_assoc | LOW | HIT (1.00) | — | C2::1 |
| coral | sq1 | causal_effect | HIGH | HIT (0.65) | — | C1::0 |
| coral | sq2 | mediation | HIGH | HIT (0.92) | — | C2::3 |
| coral | sq3 | mediation | MED | HIT (0.22) | — | C2::3 (low sat, fragil) |
| coral | sq4 | causal_effect | HIGH | **MISS** | COMPILER_MISS | C3 dice grazing→coral indirecto. Compiler no extrae |
| logistics | sq1 | causal_effect | HIGH | HIT (0.65) | — | C4::0 |
| logistics | sq2 | mediation | HIGH | **MISS** | COMPILER_MISS | Chain split across C1+C3 |
| logistics | sq3 | obs_assoc | MED | **MISS** | COMPILER_MISS | C2 tiene r=0.61 literal. Compiler fallo |
| logistics | sq4 | effect_ranking | HIGH | **MISS** | UNSUPPORTED_PATTERN | Ranking from prose |

### Hallazgo critico

**El solver NO es el bottleneck.** En los 4 misses, el solver investigo y
reporto los hallazgos correctos. El compiler LLM sigue siendo el cuello.

A22 arreglo claims compuestos. Los nuevos cuellos son:
1. **Phrasing indirecto:** "X helps Z via suppressing Y" no se extrae como X→Z
2. **Cross-claim inference:** el compiler solo ve un claim a la vez, no puede
   ensamblar mediacion split entre C1 y C3
3. **effect_ranking from prose:** dificil de extraer de NL
4. **Low-satisfaction HITs** (soil-sq2=0.28, coral-sq3=0.22) son fragiles

### Distribucion de misses
- COMPILER_MISS: 75% (3/4)
- UNSUPPORTED_PATTERN: 25% (1/4)
- NOT_INVESTIGATED: 0%
- SOLVER_NOT_REPORTED: 0%

### Diagnostico detallado de #3 (logistics-sq3)

sq3 espera: `carrier_route_deviation → end_to_end_delay` (obs_assoc, positive).
C2 dice literalmente: "Carrier route deviation is the strongest correlate of
end-to-end delay (r=0.61)".

**Pero el compiler LLM extrajo las 3 unidades de C2 con `port_berth_congestion`
como treatment:** port_berth_congestion→carrier_route_deviation,
port_berth_congestion→end_to_end_delay, y una mediacion port_berth→delay.

No extrajo `carrier_route_deviation→end_to_end_delay` como unidad separada.
El matching en `role_compat()` es hard gate en treatment: si el claim tiene
`port_berth_congestion` y el SQ pide `carrier_route_deviation`, score=0.

**Diagnostico:** No es bug de matching. Es calidad de extraccion LLM.
El prompt multi-unit dice que "X causes Y, Y causes Z" = 2 units, pero el LLM
interpreto toda la cadena con el primer nodo como treatment.

### Proximos pasos (S03)
Prioridad segun Codex (coincido):
1. Fix #3: mejorar prompt/exemplars para que chain claims extraigan TODOS los pares
2. Fix #1: extraer conclusiones distales explicitas ("indirectly improves")
3. Fix #4: effect_ranking from prose
4. #2 (cross-claim): no tocar aun — riesgo de sobrecrédito
