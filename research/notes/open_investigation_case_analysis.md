# Open Investigation — Analisis de casos reales

> Working doc para disenar el contrato de verificacion de Open Investigation.
> Objetivo: encontrar PROBLEMAS en el diseno, no confirmar que funciona.
>
> Linea activa: `synthesis/open_investigation_vision.md`

## Motivacion

El diseno original de OI proponia 4 primitivas fijas (ate, mediation,
interaction, rank_effect). El problema: **si solo tenemos 10 cosas que
podemos verificar, siempre sera un juguete.**

Necesitamos un metodo GENERAL de verificacion. Para encontrarlo, primero
entendemos la diversidad REAL de investigacion.

## Insight fundamental

El SCM es un **simulador completo**. ate() no es una formula — es una
simulacion. Entonces no estamos limitados a "lo que sabemos resolver".
Podemos verificar CUALQUIER cosa que se pueda expresar como simulacion.

La limitacion real no es el SCM sino el **contrato de compilacion** — como
convertir lo que el solver dice en algo ejecutable contra el SCM.

---

## Casos de estudio

### Caso 1: Epidemiologia — Pico desigual de internaciones

**Pregunta de investigacion:**
"La ciudad tuvo un pico desigual de internaciones respiratorias. Que conviene
investigar y donde intervenir?"

**Variables SCM (12):** vacunacion, movilidad_barrial, ventilacion_escolar,
hacinamiento_hogar, humedad, PM2_5, inmunidad_previa, acceso_clinico,
demora_testeo, edad_promedio, contagios, internaciones

**Respuestas validas del solver:**

R1: "Vacunacion y movilidad explican la mayor parte del pico"
- Camino: efecto causal + ranking
- Claim card: {focus: [vacunacion, movilidad, internaciones],
  scenario: do(vacunacion=alta) vs do(vacunacion=baja),
  readout: mean(internaciones), compare: difference, assertion: negative}
- Verificacion: ATE + ranking. FACIL con diserio actual.

R2: "No es la media sino la cola: PM2.5 y humedad empujan brotes extremos"
- Camino: riesgo de cola
- Claim card: {focus: [PM2_5, humedad, internaciones],
  scenario: do(PM2_5=alto) vs baseline,
  readout: P(internaciones > p90), compare: difference, assertion: positive}
- Verificacion: necesita operador de tail risk. NO cae en 4 primitivas.

R3: "La mejor palanca no es subir cobertura total sino focalizar barrios
de alta movilidad"
- Camino: politica optima focalizada
- Claim card: {focus: [vacunacion focalizada vs uniforme, internaciones],
  scenario: policy bundle comparison,
  readout: mean(internaciones), compare: argmin, assertion: focalizada mejor}
- Verificacion: necesita comparacion de politicas (joint interventions).
  NO cae en 4 primitivas.

**Problemas de verificacion:**
- R1 es facil. R2 y R3 no.
- Los tres solvers tienen razon sobre facetas DISTINTAS del mismo fenomeno.
- No compiten entre si — son complementarios.

---

### Caso 2: Economia — Programa de transferencias

**Pregunta:** "El programa de transferencias no redujo igual la inseguridad
alimentaria. Que esta pasando?"

**Variables SCM (12):** monto_transferencia, puntualidad_pago,
precios_alimentos, acceso_mercado, deuda_hogar, control_femenino_ingreso,
empleo_informal, shock_lluvia, apoyo_familiar, costo_transporte,
inseguridad_alimentaria, diversidad_dieta

**Respuestas validas:**

R1: "La puntualidad importa mas que el monto"
- Camino: ranking de efectos
- Verificacion: facil (ATE + rank)

R2: "El programa funciona donde hay mercado accesible; sin acceso solo
amortigua poco"
- Camino: heterogeneidad contextual
- Claim card: efecto de transferencia condicionado a acceso_mercado
- Verificacion: interaccion / efecto por estrato. Manejable.

R3: "No baja mucho la media anual, pero reduce los peores meses"
- Camino: estabilizacion / reduccion de cola
- Claim card: efecto sobre P(inseguridad > p85) vs efecto sobre mean
- Verificacion: necesita tail risk. NO cae en 4 primitivas.

**Problemas:** R3 es una observacion sofisticada y realista que nuestro
diseno actual no puede capturar. "Estabiliza" no es una primitiva.

---

### Caso 3: Ecologia — Colapso de guarderia de peces

**Pregunta:** "Las guarderias de peces del estuario colapsan algunos anios
y otros no. Cual es la historia causal?"

**Variables SCM (12):** escorrentia_nutrientes, carga_sedimento,
oxigeno_disuelto, temperatura_agua, salinidad, cobertura_manglar,
ruido_botes, supervivencia_larval, densidad_predadores, indice_bloom,
lluvia_extrema, recambio_mareal

**Respuestas validas:**

R1: "Nutrientes -> bloom -> bajo oxigeno -> caida larval"
- Camino: cadena de mediacion
- Verificacion: mediacion. Manejable.

R2: "El sistema tiene regimen umbral: con lluvia extrema, salinidad y
temperatura disparan el colapso"
- Camino: threshold / regimen change
- Claim card: supervivencia cae abruptamente arriba de cierto nivel de
  salinidad
- Verificacion: necesita operador de threshold/change-point.
  NO cae en 4 primitivas.

R3: "Los manglares no causan el shock, pero amortiguan sus consecuencias"
- Camino: buffering / resiliencia
- Claim card: efecto de nutrientes sobre supervivencia es menor cuando
  cobertura_manglar es alta
- Verificacion: interaccion de buffering. Manejable (variante de interaction).

**Problemas:** R1 y R3 son dos respuestas correctas sobre la MISMA pregunta
que describen facetas complementarias: causa proximal vs resiliencia. Un buen
scorer deberia dar credito a ambas.

---

### Caso 4: Educacion — Curriculo de matematica

**Pregunta:** "El nuevo curriculo de matematica mejoro algunas escuelas y
otras no. Que conviene concluir?"

**Variables SCM (12):** fidelidad_implementacion, conocimiento_docente,
asistencia, tutorias, apoyo_directivo, tamanio_clase, internet,
disrupcion_aula, habilidad_inicial, ansiedad_test, alineacion_prueba,
puntaje_math

**Respuestas validas:**

R1: "El curriculo funciona cuando mejora la practica docente; el mediador
real es conocimiento/fidelidad"
- Verificacion: mediacion. Manejable.

R2: "No falla en todos: ayuda sobre todo a alumnos de nivel medio con buena
asistencia"
- Camino: subgrupo beneficiado
- Claim card: efecto de curriculo en estrato habilidad_media + asistencia_alta
- Verificacion: ATE por estrato. Manejable con extension.

R3: "La media cambia poco, pero la cola alta mejora mucho"
- Camino: efecto en cuantiles
- Claim card: q90(puntaje) sube aunque mean casi no cambia
- Verificacion: necesita quantile comparison. NO cae en 4 primitivas.

**Problemas:** Tres lecturas completamente validas de la misma intervencion.
La "respuesta correcta" no es una — son facetas.

---

### Caso 5: Ingenieria industrial — Defectos intermitentes

**Pregunta:** "La linea 3 tiene defectos intermitentes. Que deberia creer
operaciones?"

**Variables SCM (12):** temp_horno_media, temp_horno_var, humedad,
viscosidad_resina, desgaste_maquina, experiencia_turno, velocidad_linea,
tiempo_curado, lote_materia_prima, sensibilidad_inspeccion, defecto_latente,
defecto_observado

**Respuestas validas:**

R1: "El problema es la variabilidad termica, no la temperatura promedio"
- Camino: efecto de varianza de input
- Claim card: efecto de temp_horno_var > efecto de temp_horno_media
- Verificacion: necesita tratar varianza como input. Inusual pero manejable.

R2: "Velocidad alta solo rompe cuando la maquina esta gastada"
- Verificacion: interaccion. Manejable.

R3: "Parte del 'aumento' es medicion: subio defecto observado por
inspeccion mas sensible, no defecto real"
- Camino: artefacto de medicion
- Claim card: defecto_observado sube pero defecto_latente casi no cambia
  cuando sensibilidad_inspeccion sube
- Verificacion: requiere distinguir outcome latente vs observado.
  ROMPE el diseno si no hay modelo de observacion explicito.

**Problemas:** R3 es quizas la respuesta MAS valiosa de un investigador —
identificar un artefacto de medicion. Pero requiere que el SCM modele
el proceso de observacion, no solo el fenomeno.

---

### Caso 6: Sociologia — Confianza vecinal post-renovacion

**Pregunta:** "Despues de la renovacion urbana cayo la confianza vecinal.
Que facetas son reales?"

**Variables SCM (12):** aumento_alquiler, riesgo_desplazamiento,
share_recien_llegados, vacancia_comercial, paradas_policiales,
participacion_reuniones, densidad_red_cuidados, fairness_percibida,
ruido_nocturno, crimen_real, trust_survey, ayuda_mutua_real

**Respuestas validas:**

R1: "La erosion real viene por desplazamiento y ruptura de redes"
- Verificacion: mediacion. Manejable.

R2: "La percepcion de injusticia modera casi todo"
- Verificacion: interaccion/moderacion. Manejable.

R3: "Cae el survey de confianza, pero la ayuda mutua real casi no cambia"
- Camino: desacople entre medida y fenomeno
- Claim card: trust_survey cae pero ayuda_mutua_real se mantiene
- Verificacion: requiere comparar DOS outcomes bajo la misma intervencion.
  Extendible pero no es ninguna primitiva actual.

**Problemas:** R3 es un hallazgo metodologico profundo — la medida no
captura el fenomeno. Similar al caso de manufactura (R3).

---

### Caso 7: Agricultura — Rindes divergentes

**Pregunta:** "Con lluvias parecidas, los rindes de lotes vecinos son muy
distintos. Donde esta el mecanismo?"

**Variables SCM (13):** materia_organica, drenaje, variedad_semilla,
densidad_siembra, timing_riego, nitrogeno, presion_plagas,
profundidad_raiz, dias_calor, asistencia_tecnica, mano_obra, rinde_media,
rinde_var

**Respuestas validas:**

R1: "Materia organica y drenaje explican resiliencia al exceso de agua"
- Camino: buffering
- Verificacion: interaccion. Manejable.

R2: "El riego a tiempo reduce perdidas extremas por calor mas que sube
la media"
- Camino: tail risk
- Verificacion: efecto sobre P(rinde < p15). NO cae en 4 primitivas.

R3: "La mejor variedad depende del suelo; no hay una ganadora global"
- Camino: ranking condicional
- Claim card: argmax(variedad) cambia segun estrato de suelo
- Verificacion: ranking condicional / interaccion compleja.
  Extendible pero inusual.

---

### Caso 8: Conservacion de arte (caso raro)

**Pregunta:** "Tras cambiar a iluminacion LED, algunas pinturas empezaron
a oscurecerse de forma extrana. Que deberia concluir conservacion?"

**Variables SCM (12):** fraccion_azul_LED, lux_totales, ciclos_humedad,
espesor_barniz, limpieza_solvente_prev, composicion_aglutinante, fuga_UV,
horas_exhibicion, microfisuras, oxidacion_pigmento, shift_color_medio,
patchiness

**Respuestas validas:**

R1: "El LED azul importa sobre todo cuando limpiezas previas dejaron
barniz fino"
- Verificacion: interaccion. Manejable.

R2: "La media de oscurecimiento es modesta, pero aparece un patron bimodal
de manchas"
- Camino: propiedad distribucional
- Verificacion: necesita test de bimodalidad. NO cae en 4 primitivas.
  Requiere operador analitico nuevo.

R3: "Reducir humedad ciclica ayuda mas que bajar lux"
- Verificacion: ranking de politicas. Manejable.

---

## Patrones encontrados

### 1. Respuestas multiples validas son la NORMA

En los 8 casos, las 2-3 respuestas no compiten entre si. Describen
**facetas distintas** del mismo fenomeno:
- Mecanismo proximal vs resiliencia (ecologia)
- Media vs cola (educacion, economia, agricultura)
- Causa vs medicion (manufactura, sociologia)
- Efecto global vs politica optima (epidemiologia)

**Implicacion:** el scoring no puede ser "acertaste o no". Tiene que
ser "que facetas descubriste y con que calidad".

### 2. Las 4 primitivas cubren ~40% de las respuestas realistas

De 24 respuestas (8 casos x 3), las 4 primitivas actuales cubren:
- ATE / ranking: ~8 respuestas
- Mediacion: ~4 respuestas
- Interaccion: ~5 respuestas

**No cubiertas (~7 respuestas):**
- Tail risk / quantile effects (4 casos)
- Propiedades distribucionales: bimodalidad (1 caso)
- Artefactos de medicion (2 casos)
- Politicas conjuntas / bundles (2 casos)
- Threshold / regime change (1 caso)

### 3. Los claims mas valiosos son los mas dificiles de verificar

Las respuestas R3 tienden a ser las mas sofisticadas:
- "Estabiliza sin mover la media"
- "El aumento es un artefacto de medicion"
- "El patron es bimodal"
- "El efecto solo aparece arriba de un umbral"

Estas son las que distinguen a un buen investigador. Y son las que
nuestro diseno actual NO puede verificar.

### 4. "No material effect" es un hallazgo valioso

En varios casos, descubrir que algo NO tiene efecto es tan importante
como descubrir que lo tiene:
- "La temperatura media no importa, la variabilidad si" (manufactura)
- "El monto no importa tanto, la puntualidad si" (economia)

El diseno debe dar credito por hallazgos negativos correctos.

### 5. El proceso de observacion importa

Los casos 5 (manufactura) y 6 (sociologia) muestran que la relacion
entre variable latente y variable observada puede ser un hallazgo clave.
Esto requiere que el SCM modele el proceso de medicion, no solo el
fenomeno causal.

---

## Que necesita el diseno general

Basado en los 8 casos, el contrato de verificacion necesita:

### Operadores de readout (que medir)
- mean (ya tenemos via ATE)
- variance
- quantile (q10, q90, etc.)
- probability_above / probability_below (tail risk)
- distribution_test (bimodalidad, normalidad)

### Operadores de comparacion (como comparar)
- difference (ya tenemos)
- ratio
- rank / argmax / argmin
- conditional_rank (ranking que cambia por estrato)
- dose_response (curva, no solo dos puntos)

### Tipos de assertion (que se afirma)
- positive / negative / no_material (ya tenemos)
- nonlinear / threshold_at
- bimodal / multimodal
- stabilizing (reduce varianza sin mover media)
- conditional (vale solo en cierto contexto)
- measurement_artifact (observado vs latente divergen)

### Capacidades del SCM necesarias
- Simulacion con do() — YA TENEMOS
- Simulacion con do() + conditioning (estratos) — YA TENEMOS
- Joint interventions (bundles) — FACIL DE AGREGAR
- Modelo de observacion (latente vs observado) — REQUIERE DISENO
- Multi-arm (>2 niveles) — FACIL DE AGREGAR

---

## Inputs de ChatGPT (sesion paralela del usuario)

El usuario discutio el problema con ChatGPT por separado. Insights clave
que agregan a nuestro analisis:

### Tres planos de evaluacion (formulacion mas clara)

ChatGPT separo la evaluacion en tres planos que estaban mezclados:

1. **Verdad local**: el claim es cierto? → verificable contra SCM
2. **Relevancia global**: responde la investigacion? → parcialmente
   verificable (depende del brief)
3. **Calidad del proceso investigativo**: investigo bien? → dificil sin
   LLM judge

Nuestro analisis de 8 casos se enfoco casi exclusivamente en el plano 1.
Los planos 2 y 3 son igual de importantes.

### Tipos de output mas alla de claims causales

Insight critico: no todo output valioso de investigacion es un claim
causal. Un solver puede producir:

- **Explicacion causal** (lo que venimos modelando)
- **Taxonomia / separacion en subtipos**: "hay dos regimenes distintos"
- **Reformulacion de la pregunta**: "la pregunta correcta no es X sino Y"
- **Conclusion de subidentificacion**: "con estos datos no se puede
  distinguir entre H1 y H2"
- **Propuesta de siguiente experimento**: "el proximo paso seria medir Z"
- **Politica operativa sin mecanismo**: "hacer A funciona, aunque no se
  por que"
- **Delimitacion honesta**: "puedo afirmar X con confianza, pero Y no"

Nuestros 8 casos solo consideraron respuestas tipo "claim causal".
Si Open Investigation solo acepta claims causales, castigamos
investigaciones buenas que van por otro carril.

**Pregunta clave:** cuantos de estos tipos son verificables contra el SCM?

| Tipo de output | Verificable? | Como? |
|---|---|---|
| Explicacion causal | SI | Simulacion + comparacion |
| Taxonomia/subtipos | PARCIAL | Si el SCM tiene estructura de mezcla |
| Reformulacion | NO | Requiere juicio de relevancia |
| Subidentificacion | SI | Verificar que dos hipotesis dan datos iguales |
| Siguiente experimento | PARCIAL | VOI computable contra SCM |
| Politica operativa | SI | Simular politica, medir outcome |
| Delimitacion | PARCIAL | Verificar lo afirmado, verificar incertidumbre de lo no-afirmado |

Sorpresa: mas tipos de los esperados SON verificables. No todos, pero mas
de lo que parece a primera vista.

### "Relevance contract" en vez de agenda fija

En vez de predefinir respuestas (sesgo) o no predefinir nada (vale todo),
predefinir **que familias de output serian valiosas para este brief
especifico**. Por ejemplo, para "investiga por que se arenan los pozos":

- Una explicacion causal plausible y bien sustentada → valioso
- Una separacion en regimenes o subtipos → valioso
- Una politica operativa util → valioso
- Una delimitacion honesta de lo que no se puede inferir → valioso
- Un red herring bien presentado → NO valioso (correcto pero irrelevante)

Esto es mas abstracto que nuestra agenda (que enumera claims especificos)
y mas concreto que "todo vale". Interesante como capa intermedia.

### Preocupacion: proceso vs output

Si evaluamos solo el hallazgo final, un solver que adivina bien saca
buena nota. Si evaluamos el proceso (pivoteo, refutacion activa,
separar caso de priors), es mas justo pero mas dificil sin LLM judge.

Opciones:
- **Process reward via log check**: el solver observo las variables
  relevantes antes de afirmar? (verificable, sin LLM)
- **Process reward via trayectoria**: el solver exploro antes de
  converger? cambio de hipotesis cuando la evidencia cambio? (parcial)
- **Process reward via LLM judge**: el razonamiento fue bueno?
  (no queremos esto)

Para el Alpha, quizas el log check (warrant simple) es suficiente.

### La tension central (bien formulada por ChatGPT)

> "El problema real no es simplemente 'abrir'. El problema real es
> COMO ABRIR SIN PERDER GROUNDING."

Ni gold answers unicas, ni judge libre post hoc. Alguna combinacion de:
- Verdad preanclada en el mundo
- Posibilidad de multiples rutas validas
- Evaluacion separada de verdad, relevancia y proceso
- Capa intermedia que traduzca a algo que el mundo pueda chequear

---

## Debate sobre arquitectura de verificacion

### Propuesta: diseno de dos patas

Emerge de la discusion entre las 3 fuentes (Claude, Codex, ChatGPT):

**Pata 1 — Pre-computar referencias (ANTES del solver)**

Antes de que el solver empiece, nosotros (que conocemos el SCM) pre-computamos:
- Que cosas son verdaderas e importantes en este mundo (agenda)
- Que es descubrible dado el budget y la evidencia visible (discoverability)
- Que familias de hallazgos son relevantes para este brief (relevance contract)

Esto NO es un "answer key" — es un mapa de referencia. El solver NO lo ve.

**Pata 2 — Verificacion post-hoc (DESPUES del solver)**

El solver investiga libre y entrega su output. Despues:
1. Compilamos su output a algo verificable (claim cards → specs ejecutables)
2. Verificamos cada spec contra el SCM (exacto)
3. Comparamos contra nuestras referencias para coverage y relevancia

### Revision critica de Codex

Codex evaluo el diseno de dos patas y respondio:

**Veredicto:** la direccion es correcta, pero tiene riesgos reales.

**Riesgo principal — Reference lock-in:**
> "Si dejan que el mapa precomputado contamine la traduccion, convierten
> Open Investigation en retrieval sobre el answer key."

Si las referencias guian al compilador, el compilador va a "encontrar" lo
que nosotros esperamos. Claims validos pero fuera del mapa quedan subpagados.

**Regla propuesta por Codex — parse ciego:**
1. **Compilar CIEGO** — traducir el claim sin mirar las referencias
2. **Verificar exacto** — el SCM responde
3. **Matching contra referencias** — SOLO para scoring (coverage, relevancia)

Las referencias guian el SCORING, no la COMPILACION.
Excepcion unica: alinear aliases de variables (sinonimos).

**Sobre la subjetividad en la compilacion:**
Codex acepta que es inevitable y propone encapsularla:
- Claim cards semi-estructuradas (reducen ambiguedad)
- Abstencion explicita del compilador cuando hay duda
- N-best parses o parses alternativos
- Benchmark offline del compilador
- Compile-preview loop (solver ve la compilacion y corrige)

"Exacto" es verdad solo DESPUES de fijar una interpretacion. Antes de
fijarla, hay subjetividad. Lo importante es medirla, no negarla.

**Sobre outputs no-causales en Alpha:**

| Output | Alpha? | Justificacion |
|---|---|---|
| Efecto causal / patron | SI | Core, ya verificable |
| Politica operativa | SI | Simulable |
| Heterogeneidad / subgrupo | SI | Verificable por estrato |
| "No concluyente" | SI | Si se formaliza como equivalencia observacional |
| Measurement caveat | SI | Si SCM tiene observation model |
| Reformulacion | NO | Requiere juicio semantico blando |
| Taxonomia | NO | Reintroduce judge |
| Sintesis narrativa | NO | Reintroduce judge |

**Sobre relevance contract:**
Buena idea, pero debe ser contrato de TIPOS DE CONTRIBUCION (mecanismo,
politica, heterogeneidad, medicion), no de respuestas concretas.
Si es muy especifico = agenda disfrazada.
Si es muy abstracto = inutil.

### Riesgos identificados por Codex

1. **Reference lock-in**: el benchmark premia solo lo que el generador
   sabe enumerar. Claims fuera del mapa quedan subpagados.

2. **Novelty tax**: un solver que descubre algo verdadero y valioso pero
   no previsto recibe menos credito que uno que encuentra lo "esperado".

3. **Doble frontera semantica**: hay subjetividad en la compilacion
   (claim → spec) Y en el matching (spec → familia). Dos pasos con
   posibilidad de error interpretativo.

4. **Goodhart de sofisticacion**: si intentamos premiar "claims mas
   sofisticados", terminamos premiando wording complejo, no mejor ciencia.

5. **Discoverability como pseudo-verdad**: la estimacion de que es
   descubrible es una hipotesis del evaluador. Si esta mal, penalizamos
   al solver por un error del benchmark.

6. **Composicionality**: una investigacion buena no es suma de claims
   sueltos. Hay sintesis, priorizacion, secuencia, narrativa. El scoring
   por claim individual puede no capturar eso.

### Consenso emergente (provisional)

Puntos donde hay acuerdo entre las 3 fuentes:

- **SI** al diseno de dos patas (pre-computar + verificar post-hoc)
- **SI** a aceptar subjetividad en la compilacion, pero encapsulada
- **SI** a un relevance contract como contrato de tipos de contribucion
- **SI** a parse ciego (compilacion no ve las referencias)
- **SI** a empezar con lo verificable y agregar despues
- **NO** a usar referencias para dirigir la compilacion
- **NO** a calibration en Alpha (muy pocos claims por episodio)
- **DEBATIBLE**: que outputs no-causales incluir en Alpha
- **DEBATIBLE**: como puntuar composicion vs claims individuales
- **DEBATIBLE**: cuanto peso dar a proceso vs output

---

## Preguntas abiertas (consolidadas)

### Sobre el contrato de verificacion
1. **Claim cards vs prosa libre:** que tanta estructura pedirle al solver
   para que la compilacion sea confiable sin sesgar la investigacion?
2. **Operadores extensibles:** el registro de operadores (mean, quantile,
   bimodality_test...) debe ser finito y conocido, o puede crecer?
3. **Threshold y no-linealidad:** como definir "hay un umbral en 0.7"
   de forma verificable? Que tolerancia? Que test?

### Sobre coverage y relevancia
4. **Cobertura vs precision:** como medir que "descubriste cosas
   importantes" sin requerir un catalogo exhaustivo?
5. **Facetas complementarias:** como dar credito cuando dos respuestas
   diferentes son ambas correctas sobre facetas distintas?
6. **Relevance contract:** como definir que familias de output son
   valiosas para un brief especifico, sin sesgar hacia una respuesta?

### Sobre tipos de output
7. **Outputs no-causales:** como verificar taxonomias, reformulaciones,
   conclusiones de subidentificacion, propuestas de experimento?
8. **Outputs mixtos:** un reporte puede tener claims causales + politica
   + delimitacion. Como scorear un mix?

### Sobre proceso
9. **Warrant sin LLM judge:** puede el log check (observo evidencia
   antes de afirmar?) capturar suficiente calidad de proceso?
10. **Modelo de observacion:** vale la pena modelar medicion en el SCM
    para capturar artefactos, o es overengineering para el Alpha?

---

## Registro de sesion

### 2026-03-26 — Sesion inicial
- Participantes: usuario, Claude, Codex, ChatGPT (sesion paralela)
- Thread Codex: 019d2ae2-9652-7d20-8da0-3b6d2f8b6418
- Fases del debate:
  1. Codex propuso contrato con 4 primitivas fijas (Claim, CompiledQuery, etc.)
  2. Usuario cuestiono: "por que no simular directamente?" → insight del SCM
     como simulador general, no limitado a primitivas nombradas
  3. Codex propuso SimulationSpec (IR) + Macros (catalogo) + ClaimFamily
  4. Analisis de 8 casos reales (24 respuestas) → 4 primitivas cubren ~40%
  5. ChatGPT aporto: 3 planos (verdad/relevancia/proceso), outputs no-causales,
     relevance contract, "abrir sin perder grounding"
  6. Usuario propuso diseno de dos patas: pre-computar referencias +
     verificacion post-hoc con subjetividad encapsulada
  7. Codex reviso: SI a la direccion, alerta sobre reference lock-in,
     parse ciego obligatorio, 6 riesgos identificados
- Consenso provisional documentado (ver seccion "Consenso emergente")
- Proximo paso: doc de conclusiones pulidas en synthesis/ cuando el debate
  madure lo suficiente
