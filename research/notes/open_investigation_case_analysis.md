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
1. **Claim cards vs prosa libre:** RESPONDIDA — claim cards semi-estructuradas.
   El solver llena: texto, variables foco, contexto, tipo de patron, confianza,
   evidencia. Es un formato de reporte cientifico, no un formulario tecnico.
2. **Operadores extensibles:** RESPONDIDA — no hay operadores fijos. Hay una
   GRAMATICA COMPOSABLE de 4 piezas (simulacion + medicion + comparacion +
   asercion). Ver seccion "Gramatica composable de verificacion".
3. **Threshold y no-linealidad:** PARCIAL — regime_change_scan + dose_response
   cubren la mayoria. Tolerancias por definir en implementacion.

### Sobre coverage y relevancia
4. **Cobertura vs precision:** RESPONDIDA — coverage por FAMILIAS (no por items).
   Family key = (brief_target, focus_signature, pattern_class, scope_class).
   Derivadas algoritmicamente del truth map.
5. **Facetas complementarias:** RESPONDIDA — como las familias son ortogonales,
   claims sobre facetas distintas caen en familias distintas.
6. **Relevance contract:** PARCIAL — contrato de TIPOS DE CONTRIBUCION, no de
   respuestas concretas. Necesita "intent metadata" del generador del caso.
   Sin eso, la relevancia no se puede derivar automaticamente.

### Sobre tipos de output
7. **Outputs no-causales:** PARCIAL — politicas, heterogeneidad, measurement
   artifacts SI entran. Taxonomias, reformulaciones, sintesis NO (Alpha).
   Subidentificacion posible pero necesita operador nuevo (identifiability_check).
8. **Outputs mixtos:** RESPONDIDA — cada finding se evalua individualmente.
   Support graph (coherence-lite) da bonus chico por conexion entre claims.

### Sobre proceso
9. **Warrant sin LLM judge:** RESPONDIDA parcialmente — log check basico
   (observo evidencia antes de afirmar) es suficiente para Alpha.
10. **Modelo de observacion:** DEBATIBLE — vale la pena si el SCM ya modela
    latente vs observado (como en P5/manufactura). No agregar capa extra solo
    para esto en Alpha.

---

## Stress test extendido: 30 casos, 10 dominios

> Sesion 2026-03-26 (segunda ronda). Objetivo: evaluar si las claim cards
> funcionan como formato universal. 15 casos generados por Claude, 15 por Codex.

### P1: Epidemiologia — Pico desigual de internaciones
Variables SCM (12): vacunacion, movilidad_barrial, ventilacion_escolar,
hacinamiento, humedad, PM2_5, inmunidad_previa, acceso_clinico,
demora_testeo, edad_promedio, contagios, internaciones

R1.1 (causal simple): "Vacunacion es el factor mas importante. Barrios con
cobertura <40% tienen 3x mas internaciones."
R1.2 (threshold + interaccion): "PM2.5 tiene un efecto no lineal — por debajo
de cierto nivel no pasa nada, por arriba se dispara, especialmente con mala
ventilacion."
R1.3 (politica operativa): "Vacunacion focalizada en barrios de alta movilidad
tiene 2x mas impacto por dosis que distribuir parejo."

### P2: Economia — Programa de transferencias
Variables SCM (12): monto, puntualidad, precios_alimentos, acceso_mercado,
deuda, control_femenino, empleo_informal, shock_lluvia, apoyo_familiar,
costo_transporte, inseguridad_alimentaria, diversidad_dieta

R2.1 (ranking): "La puntualidad importa mas que el monto."
R2.2 (heterogeneidad): "Funciona donde hay mercado accesible; sin acceso, solo
amortigua."
R2.3 (estabilizacion): "No baja mucho la media pero reduce los peores meses."

### P3: Educacion — Recuperacion post-pandemia
Variables SCM (10): horas_pantalla, apoyo_familiar, formacion_docente,
conectividad, ingreso_hogar, desayuno_escolar, ausentismo, motivacion,
ansiedad, score_matematica

R3.1 (mediacion): "El efecto de conectividad pasa por ausentismo."
R3.2 (reformulacion): "La pregunta no es por que cayeron sino por que la
recuperacion es desigual. La clave es apoyo familiar."
R3.3 (subidentificacion): "No puedo distinguir si el efecto es de conectividad
o de ingreso — estan demasiado correlacionados."

### P4: Medio ambiente — Plomo en sangre
Variables SCM (9): antiguedad_vivienda, distancia_industrial, agua_cañeria,
suelo_contaminado, nutricion, lactancia, ingreso, educacion_padres,
plomo_sangre

R4.1 (multi-driver): "Agua, suelo y pintura vieja explican el 80% de la
variacion."
R4.2 (proteccion): "Buena nutricion amortigua el impacto — misma exposicion,
40% menos plomo."
R4.3 (hallazgo sorprendente): "Lactancia extendida se asocia con MAS plomo.
Hipotesis: transferencia via leche."

### P5: Agricultura — Rindes divergentes
Variables SCM (10): tipo_suelo, pH, fertilizante_N, riego, densidad_siembra,
plaga_nivel, variedad_semilla, temperatura, precipitacion, rendimiento

R5.1 (interaccion triple): "Fertilizante funciona solo con riego suficiente y
pH 6-7. Fuera de eso, plata tirada."
R5.2 (delimitacion): "Fertilizante y riego son drivers principales. Sobre
variedad vs suelo, los datos no son concluyentes."
R5.3 (recomendacion practica): "Variedad X con densidad media tiene
consistentemente mejor rendimiento. Recomiendo esa combinacion."

### P6: Manufactura — Defectos en laminado (Codex)
Variables SCM (12): temperatura_horno, variacion_temperatura, humedad_planta,
velocidad_linea, desgaste_rodillos, viscosidad_recubrimiento, lote_insumo,
turno_noche, experiencia_operario, calibracion_sensor, defecto_real,
defecto_reportado

R6.1 (measurement artifact): "Parte del salto en defectos es de medicion: el
sensor recalibrado sobredetecta."
R6.2 (null + ranking): "La temperatura media importa mucho menos que su
variabilidad."
R6.3 (policy bundle): "Lo mejor es bajar velocidad y estabilizar viscosidad al
mismo tiempo."

### P7: Sociologia — Trabajo remoto (Codex)
Variables SCM (12): remoto_dias, autonomia_equipo, claridad_objetivos,
seniority, densidad_reuniones, interrupciones_hogar, espacio_trabajo,
confianza_manager, burnout, productividad_real, evaluacion_manager, rotacion

R7.1 (proxy mismatch): "El remoto no bajo productividad real; bajo la
evaluacion del manager porque perdio visibilidad."
R7.2 (heterogeneidad fuerte): "Ayuda en equipos autonomos, hunde a los de
baja claridad. No hay efecto promedio unico."
R7.3 (taxonomia): "No hay un solo 'equipo remoto'. Hay al menos tres regimenes:
autonomos que mejoran, fragiles que caen, neutros."

### P8: Salud clinica — Mortalidad postoperatoria (Codex)
Variables SCM (12): complejidad_caso, experiencia_cirujano, carga_uci,
ratio_enfermeria, demora_quirofano, adherencia_checklist, transfusion,
infeccion, tiempo_operatorio, fragilidad_paciente, mortalidad_30d, reingreso

R8.1 (selection bias): "La diferencia entre cirujanos se explica casi toda por
case mix."
R8.2 (bottleneck operacional): "El cuello real es la saturacion de UCI."
R8.3 (no concluyente): "No puedo separar ratio de enfermeria de carga UCI."

### P9: Transporte — Seguridad vial (Codex)
Variables SCM (12): carril_bici_protegido, ancho_calzada,
velocidad_percentil85, iluminacion_nocturna, fiscalizacion, flujo_peatonal,
flujo_motos, densidad_comercial, senalizacion, lluvia, accidente_grave,
lesion_peaton

R9.1 (trade-off): "El carril protegido reduce lesiones de ciclistas pero puede
empeorar conflictos peatonales sin cambio de senalizacion."
R9.2 (threshold dominante): "Debajo de velocidad 85p ~35 km/h, los accidentes
graves caen fuerte."
R9.3 (policy con restricciones): "Fiscalizacion + iluminacion nocturna rinde
mas que tocar el ancho de calzada."

### P10: Conservacion patrimonial — Degradacion de obras (Codex)
Variables SCM (12): lux_sala, fraccion_azul_led, ciclos_humedad,
temperatura_vitrina, espesor_barniz, limpieza_previa, composicion_pigmento,
microfisuras, flujo_visitantes, polvo_superficie, decoloracion, craquelado

R10.1 (interaccion historica): "La luz azul pega sobre todo en obras con
limpieza previa agresiva y barniz fino."
R10.2 (null + driver replacement): "Los lux no son el problema; la clave son
los ciclos de humedad."
R10.3 (hipotesis prudente): "Dos rutas plausibles: foto-degradacion y
microfisuras por clima. La segunda esta mejor soportada."

---

## Analisis de los 30 casos

### Tabla de resultados

| Caso | Tipo | Card | Compilable | Perdida | Veredicto |
|------|------|------|------------|---------|-----------|
| R1.1 | Causal simple + ranking | SI | PARCIAL | matiz | PARCIAL |
| R1.2 | Threshold + interaccion | SI | SI | matiz | FUNCIONA |
| R1.3 | Politica operativa | SI | SI | matiz | FUNCIONA |
| R2.1 | Ranking de efectos | SI | PARCIAL | matiz | PARCIAL |
| R2.2 | Heterogeneidad | SI | SI | matiz | FUNCIONA |
| R2.3 | Estabilizacion / cola | PARCIAL | PARCIAL | matiz | PARCIAL |
| R3.1 | Mediacion | SI | SI | nada | FUNCIONA |
| R3.2 | Reformulacion | PARCIAL | PARCIAL | esencia | PARCIAL |
| R3.3 | Subidentificacion | PARCIAL | NO | esencia | NO FUNCIONA |
| R4.1 | Multi-driver | SI | PARCIAL | matiz | PARCIAL |
| R4.2 | Proteccion / buffer | SI | SI | matiz | FUNCIONA |
| R4.3 | Hallazgo sorprendente | PARCIAL | PARCIAL | esencia | PARCIAL |
| R5.1 | Interaccion triple | SI | PARCIAL | matiz | PARCIAL |
| R5.2 | Delimitacion honesta | SI | PARCIAL | esencia | PARCIAL |
| R5.3 | Recomendacion practica | SI | SI | nada | FUNCIONA |
| R6.1 | Measurement artifact | SI | SI | matiz | FUNCIONA |
| R6.2 | Null + ranking | SI | PARCIAL | matiz | PARCIAL |
| R6.3 | Policy bundle | SI | SI | nada | FUNCIONA |
| R7.1 | Proxy mismatch | SI | SI | matiz | FUNCIONA |
| R7.2 | Heterogeneidad fuerte | SI | SI | matiz | FUNCIONA |
| R7.3 | Taxonomia / segmentacion | PARCIAL | NO | esencia | NO FUNCIONA |
| R8.1 | Selection bias / ajuste | SI | PARCIAL | matiz | PARCIAL |
| R8.2 | Bottleneck operacional | SI | SI | matiz | FUNCIONA |
| R8.3 | No concluyente | PARCIAL | NO | esencia | NO FUNCIONA |
| R9.1 | Trade-off multi-outcome | PARCIAL | NO | esencia | NO FUNCIONA |
| R9.2 | Threshold dominante | SI | SI | matiz | FUNCIONA |
| R9.3 | Policy con restricciones | SI | PARCIAL | matiz | PARCIAL |
| R10.1 | Interaccion historica | SI | PARCIAL | matiz | PARCIAL |
| R10.2 | Null + driver replace | SI | PARCIAL | matiz | PARCIAL |
| R10.3 | Hipotesis prudente | PARCIAL | NO | esencia | NO FUNCIONA |

### Resumen cuantitativo

- **12/30 FUNCIONA** (40%) — efectos causales directos, mediacion, heterogeneidad
  por estrato, thresholds, policies, proxy mismatch
- **13/30 PARCIAL** (43%) — necesitan operadores nuevos o metadata extra
- **5/30 NO FUNCIONA** (17%) — claims epistemicos, taxonomias, trade-offs incompletos

### Los 5 que NO funcionan

1. **R3.3 y R8.3 — Subidentificacion** ("no puedo distinguir X de Y"):
   Necesita `identifiability_check` — verificar si dos variables son
   distinguibles dado el grafo y los observables. Teoricamente computable
   contra el SCM (es un check de d-separation + correlacion condicional),
   pero requiere operador nuevo.

2. **R7.3 — Taxonomia** ("hay 3 regimenes"):
   Necesita `regime_clustering` — detectar subgrupos latentes. Dificil
   porque el SCM no modela mezclas explicitamente. Fuera de Alpha.

3. **R9.1 — Trade-off multi-outcome** ("reduce X pero empeora Y"):
   Si el SCM tiene AMBOS outcomes, es verificable. Falla cuando un outcome
   no esta en el SCM. Solucion: asegurar que el SCM cubra los outcomes
   relevantes al brief.

4. **R10.3 — Comparacion de evidencia** ("ruta A esta mejor soportada que B"):
   Genuinamente subjetivo. Requiere juicio sobre fuerza de evidencia.
   Fuera de alcance SCM.

### Patron critico: el cuello NO son las claim cards

Las claim cards funcionan en 22/30 (73%) de forma limpia y en 8/30 parcial.
El cuello real es la COMPILACION A SPECS EJECUTABLES. Y los que rompen son
claims **epistemicos/metodologicos**, no causales complejos.

De los 5 que no funcionan, 3 (R3.3, R8.3, R9.1) podrian rescatarse con
operadores nuevos o mejor cobertura del SCM. Solo R7.3 (taxonomia) y
R10.3 (comparacion de evidencia) estan genuinamente fuera del espacio
de verdad-local del SCM.

---

## Gramatica composable de verificacion

> Insight clave de la sesion: NO necesitamos un catalogo fijo de operadores.
> Necesitamos una GRAMATICA de 4 piezas composables.

### El problema de los operadores fijos

Si definimos 10 operadores nombrados, seguimos con el mismo problema que
teniamos con 4 primitivas: un claim que necesite un operador que no existe
queda unscorable. Pasamos de un juguete chico a un juguete mas grande.

### La solucion: composicion de 4 piezas

Toda verificacion contra un SCM se descompone en:

```
VERIFICACION = Simulacion + Medicion + Comparacion + Asercion
```

**1. Simulacion** — que "experimento" corremos en el SCM
- `do(X=valor)` — intervencion simple
- `do(X=valor) | Z=estrato` — intervencion condicionada
- `sweep(X, rango)` — barrer un rango de valores
- `do(X=a, Y=b)` — intervencion conjunta (policy bundle)
- `baseline` — sin intervencion (observacional)

**2. Medicion** — que miramos del resultado
- `mean(Y)` — promedio del outcome
- `variance(Y)` — variabilidad
- `quantile(Y, q)` — percentil
- `P(Y > umbral)` — probabilidad de superar umbral (tail risk)
- `correlation(A, B)` — relacion entre variables
- `distribution_shape(Y)` — test de forma (bimodalidad, etc.)

**3. Comparacion** — como relacionamos dos mediciones
- `difference` — cuanto cambia entre scenarios
- `ratio` — cuantas veces cambia
- `ranking` — cual tiene mas efecto
- `piecewise_fit` — buscar puntos de quiebre
- `gap` — diferencia entre observado y latente
- `proportion` — fraccion del efecto total (mediacion)

**4. Asercion** — que deberia ser verdad
- `positive` / `negative` / `near_zero` — signo del efecto
- `A > B` — ordenamiento
- `changepoint_exists` — hay un umbral
- `sign_changes_by_stratum` — heterogeneidad de signo
- `gap_material` — divergencia observable vs latente

### Operadores nombrados = macros de la gramatica

Los operadores no son fijos — son SHORTCUTS para combinaciones frecuentes:

| Macro | = Sim | + Med | + Comp | + Assert |
|-------|-------|-------|--------|----------|
| mean_contrast | do(X=a) vs do(X=b) | mean(Y) | difference | positive/negative |
| tail_risk_contrast | do(X=a) vs do(X=b) | P(Y>p90) | difference | positive |
| regime_change_scan | sweep(X, rango) | mean(Y)/level | piecewise_fit | changepoint_exists |
| policy_rank | do(A) vs do(B) vs do(C) | mean(Y) | ranking | A > B > C |
| mediation_decomp | do(X) directo vs via M | mean(Y) | proportion | mediacion > 0 |
| interaction_contrast | do(X) | Z=hi vs Z=lo | mean(Y) | difference | sign_changes |
| variance_contrast | do(X=a) vs do(X=b) | variance(Y) | difference | negative |
| measurement_gap | baseline | mean(obs) vs mean(latente) | gap | gap_material |

### Agregar un tipo de verificacion nuevo = combinar piezas

Si un solver dice "la varianza de Y se estabiliza cuando intervenis X":
```
simulate: do(X=alto) vs baseline
measure:  variance(Y)
compare:  difference
assert:   negative (varianza baja)
```

No necesitabamos un operador "variance_stabilization". Se armo de las piezas.

Si dice "el efecto solo aparece arriba de cierto nivel de PM2.5":
```
simulate: sweep(PM2_5, deciles)
measure:  mean(internaciones) por decil
compare:  piecewise_fit (2 segmentos)
assert:   lower_segment near_zero, upper_segment positive
```

### Que es realmente fijo

Lo que es fijo son las PIEZAS ATOMICAS (tipos de simulacion, tipos de medicion,
etc.), no las combinaciones. Agregar una pieza atomica nueva (ej: un nuevo tipo
de medicion como `entropy(Y)`) extiende TODAS las combinaciones posibles.

### Limitaciones honestas

La gramatica NO cubre todo. Quedan fuera:
- Claims que requieren juicio semantico (taxonomias, reformulaciones)
- Claims sobre la fuerza relativa de evidencia (no verdad del mundo)
- Claims sobre el proceso investigativo mismo

Esto no es un bug — es el limite del SCM como verificador. El SCM sabe
verdades del mundo, no verdades epistemologicas.

---

## Conclusiones del debate (actualizadas)

### Consenso fuerte (acuerdo entre 3+ fuentes)

1. **Claim cards semi-estructuradas** como formato de output del solver.
   No prosa libre, no formulario tecnico. Formato de reporte cientifico.
2. **Gramatica composable** en vez de operadores fijos. Simulacion +
   medicion + comparacion + asercion. Extensible por piezas.
3. **Compile-preview loop** obligatorio para eval formal, no para training.
   Es un loop de CLARIFICACION SEMANTICA — el solver corrige claim cards,
   nunca specs formales.
4. **Truth map algoritmico** sin LLM. Enumerar verdades canonicas del SCM.
   Para relevance/salience, necesita intent metadata del generador del caso.
5. **Coverage por familias** con key hibrida: (target, focus_signature,
   pattern_class, scope_class). Derivadas del truth map.
6. **Parse ciego**: compilacion NO ve las referencias. Referencias guian
   el SCORING, no la compilacion.
7. **Novel bucket = auditoria** en Alpha, no reward online.
8. **"Exact reward" redefinido**: exact local verification + compilacion
   auditable + subjetividad encapsulada. No exact end-to-end.
9. **1 claim → N atomos**: un hallazgo complejo se descompone en multiples
   specs atomicos verificables.
10. **Budget y observe no corren hoy**. El solver solo tiene python_exec +
    think + submit.

### PARCIAL (necesita mas trabajo)

- Relevance contract: contrato de tipos de contribucion, pero sin
  implementacion concreta. Necesita intent metadata.
- Identifiability check: teoricamente computable, no implementado.
- Measurement model: valioso cuando el SCM ya lo tiene, pero no agregar
  capa extra en Alpha.
- Compiler benchmark: se necesita >90% precision, >95% harmful-error
  control. Threshold definido, benchmark no construido.

### FUERA de Alpha

- Taxonomias / segmentacion latente
- Comparacion de fuerza de evidencia
- Composicionalidad real (solo coherence-lite)
- Claims negativos formales (subidentificacion)
- Process reward mas alla de log check basico

---

## Preguntas abiertas (consolidadas)

### Sobre el contrato de verificacion
1. **Claim cards vs prosa libre:** RESPONDIDA — claim cards semi-estructuradas.
   El solver llena: texto, variables foco, contexto, tipo de patron, confianza,
   evidencia. Es un formato de reporte cientifico, no un formulario tecnico.
2. **Operadores extensibles:** RESPONDIDA — gramatica composable de 4 piezas.
   Agregar un tipo nuevo = combinar piezas existentes o agregar pieza atomica.
3. **Threshold y no-linealidad:** PARCIAL — piecewise_fit + dose_response cubren
   la mayoria. Tolerancias de asercion por definir en implementacion.

### Sobre coverage y relevancia
4. **Cobertura vs precision:** RESPONDIDA — coverage por familias con precision
   gate. Si precision < umbral, coverage no paga.
5. **Facetas complementarias:** RESPONDIDA — familias ortogonales, claims sobre
   facetas distintas caen en familias distintas.
6. **Relevance contract:** PARCIAL — necesita intent metadata del generador.

### Sobre tipos de output
7. **Outputs no-causales:** PARCIAL — policies SI, heterogeneidad SI,
   measurement SI, taxonomias NO, reformulaciones NO.
8. **Outputs mixtos:** RESPONDIDA — cada finding individual + coherence bonus.

### Sobre proceso
9. **Warrant sin LLM judge:** Suficiente para Alpha con log check basico.
10. **Modelo de observacion:** Solo si el SCM ya lo modela.

### Nuevas preguntas (de esta sesion)
11. **Compiler benchmark:** como construirlo? Propuesta: 200+ claims, 15+
    mundos, doble anotacion humana, >90% precision para usar en scoring.
12. **Costo en RL:** compile-preview loop es caro. Para training, usar
    claim cards explicitas + compilador local, sin preview.
13. **Intent metadata:** que campos necesita el generador para que
    relevance/salience sea derivable algoritmicamente?
14. **Rescue de NO FUNCIONA:** identifiability_check y multi-outcome
    trade-off podrian rescatarse con operadores nuevos. Priorizar?

### Lineas de exploracion para profundizar

- Formalizar la gramatica composable como DSL ejecutable
- Construir prototype del truth map algoritmico (enumerar verdades de un SCM real)
- Disenar claim cards con slots minimos de intencion verificativa
- Benchmark de compilacion con claims disfrazados de multiples formas
- Explorar identifiability_check como operador nuevo (d-separation + correlacion)
- Evaluar si mixture detection es viable como operador para Alpha-2

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
- Consenso provisional documentado

### 2026-03-26 — Sesion de profundizacion (3 rondas de debate)
- Participantes: Claude, Codex (mismo thread)
- 3 rondas de debate ida y vuelta, 8 tensiones atacadas

**Ronda 1 — Riesgos existenciales:**
- Compilador = riesgo #1. Compile-preview loop OBLIGATORIO
- Agenda no es ground truth — es "benchmark policy"
- 4 casos de ruptura analizados (inesperado, vago, negativo, practico)
- Version simple (correctness-only) valida como Alpha-0 pero no como OI

**Ronda 2 — Diseño concreto:**
- Walk-through completo del compile-preview loop con Hallazgo 2 (PM2.5)
- 1 claim → N atomos verificables (diseño de specs para threshold + interaction)
- Family key hibrida: (brief_target, focus_signature, pattern_class, scope_class)
- Coherence-lite via support graph (no composicionalidad completa)
- DoAtlas-1 como precedente mas cercano (~80% executability)
- Compiler benchmark: >90% precision, >95% harmful-error control

**Ronda 3 — Operadores, costo y experiencia del solver:**
- 10-12 operadores para Alpha, todos implementables como Monte Carlo
- Compile-preview loop es caro para RL → claim cards + compilador local
- El solver entrega claim cards, no prosa libre
- "Open" = libre en investigacion, estructurado en reporte

**Stress test de 30 casos:**
- 15 Claude + 15 Codex, 10 dominios distintos
- Resultado: 12 FUNCIONA (40%), 13 PARCIAL (43%), 5 NO FUNCIONA (17%)
- Cuello de botella: compilacion a specs, no las claim cards
- Lo que rompe: claims epistemicos/metodologicos (taxonomia, subidentificacion)

**Insight final — Gramatica composable:**
- NO catalogo fijo de operadores. GRAMATICA de 4 piezas composables:
  Simulacion + Medicion + Comparacion + Asercion
- Operadores nombrados = macros (shortcuts de combinaciones frecuentes)
- Agregar verificacion nueva = combinar piezas existentes
- Esto resuelve la preocupacion del usuario de quedar con "siempre los
  mismos casos disfrazados"

### 2026-03-27 — Autoresearch: 5 preocupaciones criticas + 3 cirugias
- Participantes: Claude (autoresearch), Codex (2 threads: 019d2c96 expirado, 019d2d62 activo)
- Branch: autoresearch-open-investigation

**5 preocupaciones criticas identificadas:**
1. Sesgo interventional — la gramatica solo tiene do(), ciencia es observacional
2. Goodhart de simplicidad — claims crudos y sofisticados pagan parecido
3. Truth map explota — 12 nodos pueden generar miles de verdades
4. Taxonomia/subidentificacion son fundamentales, no edge cases
5. Compiler >90% no tiene evidencia — no hay plan B

**Codex confirmo las 5 y propuso 3 cirugias:**
1. Primitivas observacionales de primera clase (observe, condition, adjust)
2. Scoring anti-simplificacion (specificity bonus + overclaim penalty)
3. Salience map brief-anchored en vez de truth map exhaustivo

**Spec corregida entregada por Codex (thread 019d2d62):**
- QueryContext con 6 ramas: baseline, intervene, observe, condition, adjust, sweep
- 9 mediciones: mean, variance, quantile, tail_prob, prob, correlation,
  partial_correlation, distribution, identifiability_check
- 8 comparaciones: identity, difference, ratio, ranking, gap, proportion,
  piecewise_fit, contrast_diff
- 13 aserciones: positive, negative, near_zero, greater_than, less_than,
  rank_order, changepoint_exists, sign_flip, gap_material, identifiable,
  not_identifiable, distinguishable, not_distinguishable
- regression_coefficient explicitamente PROHIBIDO (depende de spec del modelo)
- 15 macros nombradas (8 originales + 7 nuevas observacionales/estructurales)
- Scoring: SPEC_BASE=0.50, SPEC_BONUS_MAX=0.50, OVERCLAIM_MAX=0.50
- Salience map: 10-24 familias tipico para 12 nodos, hard cap 30
- Lazy expansion: +5 familias por claim sin match

**Proximo paso:** implementar como DSL Python en src/sreg/models/

### 2026-03-27 — Autoresearch: implementacion + review Codex
- 3 modulos implementados: open_investigation.py, oi_verifier.py, oi_salience.py
- 66 tests passing
- **Review de Codex encontro 7 issues:**
  1. CRITICO: ADJUST usa do() en vez de backdoor adjustment real
  2. CRITICO: IDENTIFIABILITY_CHECK no verifica lo que promete
  3. CRITICO: familias heterogeneidad/mediacion generan con un estimando
     y verifican con otro (rompe exactitud local)
  4. IMPORTANTE: familias son mono-atomo → anti-simplificacion no opera
  5. IMPORTANTE: evidence_basis/confidence no se usan en scoring
  6. IMPORTANTE: salience map solo tiene 5 patterns interventionales
  7. MENOR: DISTRIBUTION placeholder, GAP_MATERIAL hardcodeado
- Conclusion de Codex: "esto todavia no pasa LA PREGUNTA — scorea verdad,
  no investigacion. Un solver sin datos pero con priors gana."
- **Plan:** fixear #3 y #4 (esenciales para scoring), luego piloto E2E
  sin compiler (oracle → verify → compare baselines)
