# 20 Escenarios de Investigacion — Rubrica de Evaluacion

## Para que sirve este documento

Este documento define 20 escenarios de investigacion diversos que sirven como
**checklist de validacion** para cualquier decision de scoring en SREG.
Cada decision de diseno debe testearse mentalmente contra TODOS estos escenarios.

Para cada escenario se define:
- **Pregunta**: que se investiga
- **Variables/datos**: que tiene el investigador
- **Ejemplo de respuesta correcta**: como se ve un buen resultado
- **Espacio de respuestas**: unica, acotado, o abierto
- **Rubrica de scoring**: que dimensiones importan y como medirlas

### Tipos de espacio de respuesta

| Tipo | Descripcion | Ejemplo |
|---|---|---|
| **Unica** | Hay una respuesta correcta objetiva (o un rango estrecho) | Prediccion: MSE = 2.3 |
| **Acotado** | Hay un conjunto finito de respuestas validas, se puede enumerar | "Los confounders son: X, Y, Z" |
| **Abierto** | Multiples investigaciones correctas posibles, no enumerables | "El sistema tiene estas relaciones..." |

### Dimensiones de scoring transversales

| Dimension | Que mide | Aplica a |
|---|---|---|
| **Veracidad** | El claim es factualmente correcto? (verificable contra SCM) | Todos |
| **Completitud** | Cubrio los aspectos importantes del sistema/pregunta? | System mapping, multi-outcome |
| **Especificidad** | Los claims son precisos o vagos? | Todos |
| **Calibracion** | El investigador sabe que NO sabe? | Epistemologico, confounding |
| **Relevancia** | Los claims responden a lo que se pregunto? | Todos |
| **Precision predictiva** | Que tan bien predice datos no vistos? | Predictivo, screening |
| **Optimalidad** | La solucion es buena comparada con el optimo? | Diseño, optimizacion |
| **Robustez** | Las conclusiones sobreviven perturbaciones? | Metodologico, causal |

---

## Los 20 Escenarios

---

### [1] Medicina — Antibioticos tempranos en sepsis

**Tipo**: Causal simple, single-outcome.

**Pregunta**: Un hospital implemento un protocolo de antibioticos en 60 minutos
para pacientes con sospecha de sepsis. El protocolo reduce la mortalidad a 28 dias?

**Variables**: edad, score de severidad (SOFA), comorbilidades, tiempo a
antibiotico, tipo de antibiotico, presion arterial, lactato, mortalidad_28d.

**Ejemplo de respuesta correcta**:
"Administrar antibioticos dentro de 60 minutos reduce la mortalidad a 28 dias
en ~4 puntos porcentuales (de 32% a 28%). El efecto es mayor en pacientes con
SOFA > 8. La severidad basal confunde la relacion — pacientes mas graves
reciben antibioticos mas tarde Y tienen mayor mortalidad."

**Espacio de respuestas**: ACOTADO. El efecto causal tiene un valor verdadero
en el SCM. Pero hay multiples angulos validos (efecto promedio, por subgrupo,
confounders, mecanismo).

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 40% | ATE verificado contra SCM (do-calculus) |
| Completitud | 25% | Identifico confounders? Heterogeneidad? |
| Especificidad | 20% | Cuantifico magnitud o solo dijo "reduce"? |
| Calibracion | 15% | Reconocio limitaciones (observacional, etc.)? |

---

### [2] Oncologia — Inmunoterapia: supervivencia vs toxicidad

**Tipo**: Trade-off multi-outcome.

**Pregunta**: Un nuevo esquema de inmunoterapia mejora la respuesta tumoral
pero reporta eventos adversos graves. Investiga el trade-off entre
supervivencia a 1 anio y toxicidad grado 3+ y cuando conviene usarlo.

**Variables**: edad, estadio tumoral, tipo histologico, esquema (A/B/control),
biomarcadores, supervivencia_1a, toxicidad_grado3, calidad_vida.

**Ejemplo de respuesta correcta**:
"El esquema A mejora supervivencia 1a en 12pp vs control (p<0.01) pero
aumenta toxicidad grado 3+ en 18pp. El esquema B es intermedio: +8pp
supervivencia, +7pp toxicidad. En pacientes con biomarcador alto, A domina
(alta supervivencia, toxicidad manejable). En biomarcador bajo, B es
preferible."

**Espacio de respuestas**: ABIERTO. Multiples conclusiones validas segun
que outcomes priorices y que subgrupos analices.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | Efectos en cada outcome verificados contra SCM |
| Completitud | 35% | Cubrio AMBOS outcomes? Identifico subgrupos? |
| Especificidad | 20% | Cuantifico trade-offs o solo dijo "mejora pero empeora"? |
| Relevancia | 15% | Las conclusiones informan una decision clinica? |

---

### [3] Salud publica — Impuesto a bebidas azucaradas

**Tipo**: Policy multi-outcome + equidad.

**Pregunta**: Una ciudad evalua un impuesto a bebidas azucaradas. Investiga
efectos sobre consumo, obesidad infantil y recaudacion, incluyendo impacto
desigual por nivel socioeconomico.

**Variables**: ingreso_hogar, consumo_azucar, precio, IMC_infantil,
escolaridad_padres, recaudacion, acceso_alternativas, NSE.

**Ejemplo de respuesta correcta**:
"El impuesto reduce consumo promedio en 15% pero el efecto es heterogeneo:
-22% en NSE bajo, -8% en NSE alto. Obesidad infantil cae 2pp en NSE bajo.
Recaudacion es regresiva (NSE bajo paga proporcionalmente mas). El impuesto
es efectivo en salud pero inequitativo fiscalmente."

**Espacio de respuestas**: ABIERTO. Muchos angulos validos. Alguien puede
focalizarse en equidad, otro en efectividad, otro en sustitucion.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | Efectos por outcome verificados |
| Completitud | 35% | Cubrio los 3+ outcomes y la dimension de equidad? |
| Especificidad | 20% | Cuantifico heterogeneidad por NSE? |
| Calibracion | 15% | Reconocio trade-offs en vez de conclusion simplista? |

---

### [4] Conservacion — Cierre pesquero estacional

**Tipo**: Policy multi-outcome eco + socioeconomico.

**Pregunta**: Se propone un cierre estacional de pesca. Investiga impacto
sobre biomasa de la especie objetivo, ingresos de pescadores, y cumplimiento.

**Variables**: biomasa, esfuerzo_pesca, ingreso_pescador, precio_mercado,
estacion, cumplimiento, alternativas_economicas, distancia_a_control.

**Ejemplo de respuesta correcta**:
"El cierre aumenta biomasa en 30% al anio siguiente, pero ingresos caen 40%
durante el cierre. Cumplimiento es solo 60% en zonas sin control cercano.
El efecto neto sobre biomasa depende del cumplimiento — con evasion alta,
el beneficio se reduce a ~12%."

**Espacio de respuestas**: ACOTADO. Los efectos son verificables, pero la
interpretacion integrada (conviene o no?) es abierta.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | Efectos en cada outcome |
| Completitud | 30% | Cubrio eco + socio + cumplimiento? |
| Especificidad | 20% | Cuantifico interaccion cumplimiento-beneficio? |
| Relevancia | 20% | Informa la decision de politica? |

---

### [5] Ingenieria — Gestion termica de baterias

**Tipo**: Multi-outcome + tail risk.

**Pregunta**: Dos disenos de gestion termica compiten: uno maximiza autonomia,
otro reduce riesgo de thermal runaway. Investiga trade-offs entre autonomia,
degradacion y probabilidad de fallo.

**Variables**: diseno (A/B), temperatura_operacion, ciclos, capacidad_residual,
autonomia_km, prob_runaway, carga_rapida, temperatura_ambiente.

**Ejemplo de respuesta correcta**:
"Diseno A: autonomia +15%, degradacion similar, pero prob_runaway 3x mayor
en temperaturas >40C. Diseno B: autonomia base, pero prob_runaway <0.1% en
todas las condiciones. En climas calidos (>35C promedio), B domina porque
el riesgo de A es inaceptable."

**Espacio de respuestas**: ACOTADO. Metricas verificables, pero la
recomendacion depende de tolerancia al riesgo.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | Trade-offs verificados |
| Completitud | 25% | Cubrio los 3 outcomes + condiciones de operacion? |
| Especificidad | 20% | Cuantifico umbrales donde cambia la recomendacion? |
| Robustez | 25% | Analizo sensibilidad a condiciones extremas (tail)? |

---

### [6] Logistica — Por que se atrasan las entregas?

**Tipo**: System mapping / diagnostico sin target unico.

**Pregunta**: Una empresa tiene retrasos en entregas. Datos de proveedores,
inventario, transporte, demanda y clima. Investiga por que se atrasan
y donde intervenir.

**Variables**: lead_time_proveedor, nivel_inventario, distancia_entrega,
capacidad_transporte, demanda, clima, dias_atraso, ruta, almacen.

**Ejemplo de respuesta correcta**:
"El principal driver de atraso es lead_time_proveedor (no transporte como
se creia). Inventario bajo amplifica el efecto. Clima afecta transporte
pero su contribucion al atraso total es <10%. El cuello de botella es la
cadena proveedor → inventario, no la distribucion."

**Espacio de respuestas**: ABIERTO. Multiples mapeos parciales del sistema
son validos. No hay UNA respuesta — hay grados de completitud.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 35% | Relaciones causales correctas en el SCM |
| Completitud | 35% | Que fraccion de la estructura relevante mapeo? |
| Especificidad | 15% | Cuantifico contribuciones relativas? |
| Relevancia | 15% | Identifico puntos de intervencion accionables? |

---

### [7] Biologia — Microbioma y 5 marcadores de salud

**Tipo**: System mapping multi-outcome.

**Pregunta**: Datos de composicion bacteriana intestinal y 5 marcadores de
salud (inflamacion, metabolismo, inmunidad, animo, digestion). Investiga
las relaciones.

**Variables**: diversidad_bacteriana, bacteroides_ratio, firmicutes_ratio,
dieta_fibra, inflamacion, metabolismo_glucosa, inmunidad_score,
animo_score, digestion_score, edad, antibioticos_recientes.

**Ejemplo de respuesta correcta**:
"Diversidad bacteriana tiene efecto causal positivo sobre digestion e
inmunidad, pero no sobre animo (la asociacion esta confundida por dieta).
Antibioticos recientes reducen diversidad, lo que indirectamente empeora
inmunidad. Firmicutes/Bacteroides ratio afecta metabolismo pero no los
otros marcadores."

**Espacio de respuestas**: MUY ABIERTO. 10 variables × 5 outcomes = enorme
espacio de relaciones posibles. Multiples investigaciones parciales validas.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 35% | Cada relacion afirmada es correcta en el SCM? |
| Completitud | 30% | Cuantas relaciones importantes descubrio? |
| Calibracion | 20% | Distinguio causal de asociativo? Dijo "no hay efecto" cuando no lo hay? |
| Especificidad | 15% | Cuantifico magnitudes o solo dijo "afecta"? |

---

### [8] Ingenieria electrica — Cascadas de fallo en la red

**Tipo**: Vulnerabilidad de red / estructura. Output = mapa.

**Pregunta**: Que nodos de la red electrica son criticos? Como se propagan
los fallos? Donde poner redundancia?

**Variables**: nodo_id, carga, capacidad, conexiones, centralidad,
redundancia, fallo_cascada, region, tipo_generacion.

**Ejemplo de respuesta correcta**:
"Los nodos 4 y 7 son criticos — su fallo causa cascada que afecta >60%
de la red. El nodo 12 parece importante (alta carga) pero tiene redundancia
natural. La propagacion va: nodo critico → sobrecarga vecinos →
fallo secundario en 2 pasos. Agregar redundancia en nodo 4 reduce el
riesgo de cascada mayor en ~70%."

**Espacio de respuestas**: ACOTADO. Los nodos criticos son verificables
contra el SCM, pero la estrategia de mitigacion es mas abierta.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 35% | Nodos criticos correctamente identificados? |
| Completitud | 30% | Mapeo la estructura de propagacion? |
| Especificidad | 20% | Cuantifico impacto de cada nodo? |
| Relevancia | 15% | La recomendacion de redundancia es accionable? |

---

### [9] Neurociencia — Quien influye a quien entre regiones cerebrales

**Tipo**: Structure discovery. No hay outcome privilegiado.

**Pregunta**: Con registros de actividad de varias regiones cerebrales
durante una tarea, investiga "quien influye a quien" y que conexiones
son directas vs indirectas.

**Variables**: actividad_corteza_prefrontal, actividad_amigdala,
actividad_hipocampo, actividad_corteza_visual, actividad_corteza_motora,
actividad_talamo, tipo_tarea, tiempo.

**Ejemplo de respuesta correcta**:
"Corteza visual → talamo → corteza prefrontal es la cadena principal
durante la tarea. Amigdala modula la conexion talamo → prefrontal (no
tiene efecto directo sobre visual). Hipocampo influye sobre prefrontal
pero solo durante recall, no durante percepcion."

**Espacio de respuestas**: ABIERTO. Multiples subconjuntos de la
estructura causal son descubrimientos validos.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 40% | Cada conexion afirmada existe en el SCM? |
| Completitud | 30% | Que fraccion del grafo descubrio? |
| Calibracion | 20% | Distinguio directa de indirecta? Dijo "no hay conexion" cuando no la hay? |
| Especificidad | 10% | Cuantifico fuerza de conexiones? |

---

### [10] Epidemiologia — Confounding por indicacion (farmaco X)

**Tipo**: Confounding como objetivo central.

**Pregunta**: En datos observacionales, quienes reciben el farmaco X suelen
estar mas graves al inicio. La aparente falta de eficacia se explica por
confounding por severidad?

**Variables**: severidad_basal, farmaco_X (si/no), edad, comorbilidades,
outcome_clinico, dosis, hospital, indicacion_clinica.

**Ejemplo de respuesta correcta**:
"Si: severidad basal confunde la relacion farmaco → outcome. El efecto
crudo es nulo (OR=1.02), pero ajustando por severidad el efecto protector
aparece (OR=0.72). El adjustment set minimo es {severidad, comorbilidades}.
El farmaco SI funciona — simplemente se da mas a pacientes graves."

**Espacio de respuestas**: ACOTADO. El confounding es verificable. El
adjustment set es enumerable (puede haber varios validos pero son finitos).

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 35% | Identifico correctamente el confounder? |
| Completitud | 25% | Encontro el adjustment set correcto? |
| Especificidad | 25% | Cuantifico la diferencia crudo vs ajustado? |
| Calibracion | 15% | Explico POR QUE la severidad confunde (mecanismo)? |

---

### [11] Ciencias sociales — Camaras corporales y sesgo de adopcion

**Tipo**: Selection bias como hallazgo principal.

**Pregunta**: Comisarias que adoptan camaras corporales tienen menos quejas
por uso excesivo de fuerza. Pero adoptaron por presion mediatica
(post-incidente). Es efecto real o sesgo de seleccion?

**Variables**: camaras (si/no), quejas_fuerza, incidentes_previos,
presion_mediatica, tamano_comisaria, entrenamiento, zona, anio_adopcion.

**Ejemplo de respuesta correcta**:
"La relacion camaras → menos quejas esta confundida por presion mediatica:
las comisarias que adoptaron camaras ya estaban bajo escrutinio (lo que
per se reduce quejas). El efecto directo de camaras es positivo pero
menor: ~30% de la reduccion observada es causal, ~70% es seleccion."

**Espacio de respuestas**: ACOTADO. La descomposicion causal/seleccion
es verificable contra el SCM.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 35% | Identifico el sesgo de seleccion? |
| Especificidad | 30% | Descompuso efecto causal vs seleccion? |
| Completitud | 20% | Mapeo el mecanismo de seleccion completo? |
| Calibracion | 15% | Reconocio que HAY efecto causal parcial (no solo sesgo)? |

---

### [12] Medicina personalizada — Para QUIEN funciona el tratamiento?

**Tipo**: Heterogeneidad profunda.

**Pregunta**: Un tratamiento funciona en promedio pero con mucha variabilidad.
Con datos geneticos, clinicos y demograficos, investiga que subgrupos
se benefician y cuales no.

**Variables**: tratamiento, edad, sexo, genotipo_A, genotipo_B,
comorbilidad, biomarcador_X, outcome_primario, efecto_adverso.

**Ejemplo de respuesta correcta**:
"El efecto promedio es +5pp. Pero: genotipo_A positivo + biomarcador_X alto
tiene efecto de +18pp. Genotipo_A negativo tiene efecto nulo (-1pp, NS).
En mayores de 70 con comorbilidad, el efecto adverso supera el beneficio.
La recomendacion: tratar solo genotipo_A+ con biomarcador_X > umbral."

**Espacio de respuestas**: ABIERTO. Multiples particiones validas del
espacio de pacientes. Diferentes niveles de granularidad son correctos.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | Los efectos por subgrupo son correctos? |
| Completitud | 30% | Identifico los moderadores principales? |
| Especificidad | 25% | Definio subgrupos con variables concretas y umbrales? |
| Relevancia | 15% | La conclusion es clinicamente accionable? |

---

### [13] Clima/salud — Mortalidad por olas de calor

**Tipo**: Risk assessment + heterogeneidad + subgrupos.

**Pregunta**: Se observa aumento de mortalidad en olas de calor. Que
factores aumentan el riesgo (edad, vivienda, AC, comorbilidades) y
como cambia el tail risk bajo distintas politicas?

**Variables**: temperatura_max, mortalidad, edad, tipo_vivienda,
acceso_AC, comorbilidades, NSE, zona_urbana, alerta_activada.

**Ejemplo de respuesta correcta**:
"El riesgo de mortalidad se duplica por encima de 40C. Los factores de
riesgo principales son: edad >75 (RR 3.2), sin AC (RR 2.5), vivienda
sin aislamiento (RR 1.8). La alerta temprana reduce mortalidad en 25%
en zonas con acceso a refugios, pero solo 5% en zonas sin ellos.
El grupo de maximo riesgo (>75, sin AC, aislados) tiene mortalidad 8x."

**Espacio de respuestas**: ACOTADO. Riesgos relativos verificables.
Las recomendaciones de politica son mas abiertas.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | Riesgos relativos correctos? |
| Completitud | 25% | Identifico los principales factores + interacciones? |
| Robustez | 25% | Analizo tail risk (extremos), no solo promedios? |
| Relevancia | 20% | Las politicas evaluadas son accionables? |

---

### [14] Sociologia — Perfiles de uso de redes sociales

**Tipo**: Descriptivo / exploratorio + segmentacion.

**Pregunta**: 1000 usuarios con datos de: tiempo en pantalla, tipo de
contenido, edad, genero, bienestar, productividad, sueno. Hay patrones
o clusters de uso? Que grupos son mas vulnerables?

**Variables**: tiempo_pantalla, pct_video, pct_social, pct_noticias,
edad, genero, bienestar, productividad, sueno, hora_pico.

**Ejemplo de respuesta correcta**:
"Hay 3 perfiles principales: (1) uso moderado-diverso (40%), bienestar
normal; (2) uso intensivo-social (25%), bienestar bajo, sueno malo;
(3) uso nocturno-noticias (15%), productividad baja. El perfil 2
(jovenes, >4h/dia, >60% social) es el mas vulnerable: bienestar
1.5 SD por debajo del promedio."

**Espacio de respuestas**: MUY ABIERTO. No hay clustering "correcto" —
multiples segmentaciones son validas. Lo que importa es que capture
estructura real de los datos.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | Los patrones descritos existen en los datos? |
| Completitud | 25% | Cubrio las dimensiones principales? |
| Especificidad | 25% | Cuantifico magnitudes y prevalencias? |
| Calibracion | 20% | Distinguio patrones fuertes de debiles? No sobreinterpreto? |

---

### [15] Meteorologia — Predecir precipitacion diaria

**Tipo**: Predictiva pura.

**Pregunta**: Con datos historicos de temperatura, humedad, presion, viento
y cobertura nubosa, construi el mejor modelo para predecir precipitacion.

**Variables**: temperatura, humedad, presion, velocidad_viento,
direccion_viento, cobertura_nubosa, precipitacion (target), mes, altitud.

**Ejemplo de respuesta correcta**:
"Modelo de regresion con humedad, presion y cobertura como features
principales logra RMSE=4.2mm en test set (vs 6.8mm del baseline).
Agregar interaccion humedad*presion mejora a RMSE=3.8mm. Temperatura
no aporta informacion adicional una vez que humedad esta en el modelo."

**Espacio de respuestas**: UNICA (metrica objetiva). RMSE o MAE en test
set. El "mejor modelo" tiene un score puntual medible.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Precision predictiva | 60% | RMSE/MAE en test set vs baseline |
| Especificidad | 20% | Identifico que features importan y cuales no? |
| Robustez | 20% | El modelo es estable o sobreajusta? |

---

### [16] Drug discovery — Screening de compuestos

**Tipo**: Exploracion de espacio / screening.

**Pregunta**: 500 compuestos con propiedades moleculares medidas, solo 20
testeados in-vitro. Identificar los 10 mas prometedores para testear.

**Variables**: peso_molecular, logP, n_donors, n_acceptors, TPSA,
rotatable_bonds, actividad_in_vitro (solo 20 medidos), familia_quimica.

**Ejemplo de respuesta correcta**:
"Los compuestos activos comparten: logP entre 2-4, TPSA < 90, y
peso_molecular < 450. Recomiendo los 10 candidatos con mayor score
en este perfil. Compuestos 234, 89, 412... son los mas prometedores.
Precision estimada: 60% de los recomendados seran activos."

**Espacio de respuestas**: ACOTADO. Se puede medir: de los 10
recomendados, cuantos son realmente activos (conocido en el SCM)?

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Precision predictiva | 50% | De los K recomendados, cuantos son activos? |
| Especificidad | 25% | Definio criterios claros de seleccion? |
| Calibracion | 25% | Su estimacion de precision es realista? |

---

### [17] Estadistica — Que estimador funciona mejor con datos faltantes?

**Tipo**: Metodologica.

**Pregunta**: Tres metodos para estimar efectos causales con datos faltantes
(IPW, AIPW, imputacion multiple). Con datos simulados, investiga cual
es mas robusto y cuando falla cada uno.

**Variables**: tratamiento, outcome, confounder_1, confounder_2,
prob_missing (mecanismo conocido en SCM), metodo_estimacion.

**Ejemplo de respuesta correcta**:
"AIPW es el mas robusto: sesgo < 5% incluso con missing 30%. IPW tiene
buen desempeno con missing < 15% pero sesgo crece rapido despues.
Imputacion multiple falla cuando el mecanismo de missing depende del
outcome (MNAR). El verdadero ATE es 3.2 — AIPW estima 3.1, IPW 3.8,
imputacion 2.4."

**Espacio de respuestas**: ACOTADO. El ATE verdadero es conocido (SCM).
El ranking de metodos es verificable. Pero el analisis de "cuando falla"
es mas abierto.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 35% | Las estimaciones reportadas son correctas? |
| Completitud | 30% | Comparo los 3 metodos en multiples condiciones? |
| Especificidad | 20% | Cuantifico sesgo/varianza por condicion? |
| Relevancia | 15% | Las recomendaciones son claras y accionables? |

---

### [18] Ingenieria de procesos — Optimizar rendimiento de reactor

**Tipo**: Diseño / optimizacion closed-loop.

**Pregunta**: Un reactor quimico tiene 6 parametros ajustables. Cada corrida
es costosa. Encontra la configuracion que maximice rendimiento minimizando
uso de catalizador.

**Variables**: temperatura, presion, concentracion, flujo, catalizador,
tiempo_residencia, rendimiento, pureza, costo_catalizador.

**Ejemplo de respuesta correcta**:
"Optimo encontrado: T=180C, P=3.2atm, flujo=1.2L/min, catalizador=0.8g.
Rendimiento: 87% (vs 72% baseline). Encontrado en 12 corridas usando
exploracion sistematica del espacio T*P. La relacion catalizador-rendimiento
tiene retornos decrecientes por encima de 0.6g."

**Espacio de respuestas**: UNICA (cercano). El optimo del SCM es conocido.
El score mide distancia al optimo + eficiencia de exploracion.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Optimalidad | 50% | Rendimiento logrado vs optimo verdadero del SCM |
| Eficiencia | 30% | En cuantas corridas llego? |
| Especificidad | 20% | Entendio la estructura (que parametros importan)? |

---

### [19] Psiquiatria — Depresion: subtipos y validez de medicion

**Tipo**: Taxonomia + validez de constructo.

**Pregunta**: Se sospecha que "depresion" incluye subtipos con mecanismos
distintos, pero los instrumentos mezclan constructos. Investiga una
tipologia util y evalua validez de medicion.

**Variables**: score_PHQ9, score_anhedonia, score_somatico, score_cognitivo,
cortisol, inflamacion, sueno, actividad_fisica, genotipo, edad, sexo.

**Ejemplo de respuesta correcta**:
"Hay al menos 2 subtipos distinguibles: (1) inflamatorio-somatico
(cortisol alto, inflamacion alta, score somatico dominante) y
(2) cognitivo-anhedonico (cortisol normal, score anhedonia y cognitivo
dominantes). El PHQ9 total no distingue subtipos — los items somaticos
y cognitivos miden constructos diferentes con mecanismos diferentes."

**Espacio de respuestas**: ABIERTO. Multiples tipologias son validas.
Lo que importa es que correspondan a estructura real en los datos Y en
los mecanismos (SCM).

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | Los subtipos corresponden a clusters reales en el SCM? |
| Completitud | 25% | Evaluo validez del instrumento, no solo tipologia? |
| Especificidad | 25% | Definio subtipos con variables concretas y diferenciables? |
| Calibracion | 20% | Reconocio limites de la tipologia (cuantos subtipos, incertidumbre)? |

---

### [20] Medio ambiente — Se puede estimar el efecto de contaminacion en asma?

**Tipo**: Epistemologico / identificabilidad.

**Pregunta**: Solo hay proxies y datos agregados sobre contaminacion del
aire y prevalencia de asma. El efecto es identificable bajo supuestos
razonables? Que medicion adicional lo haria posible?

**Variables**: PM25_proxy (medicion indirecta), asma_prevalencia (agregada),
trafico, zona_industrial, viento, temperatura, NSE, acceso_salud.

**Ejemplo de respuesta correcta**:
"El efecto causal de PM2.5 sobre asma NO es identificable con los datos
actuales por dos razones: (1) PM25_proxy tiene error de medicion
correlacionado con zona_industrial (que afecta asma directamente), y
(2) datos agregados no permiten separar efecto individual. Para
identificar: se necesita medicion individual de exposicion O un instrumento
exogeno como variacion de viento."

**Espacio de respuestas**: ACOTADO. La identificabilidad es verificable
formalmente contra el SCM (d-separation, adjustment criterion). El
instrumento propuesto es evaluable.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 35% | El diagnostico de (no)identificabilidad es correcto? |
| Completitud | 25% | Explico POR QUE no es identificable (mecanismo)? |
| Especificidad | 25% | Propuso solucion concreta y verificable? |
| Calibracion | 15% | Distinguio "no identificable" de "efecto no existe"? |

---

### [21] Farmacologia — El efecto se mantiene en otra poblacion?

**Tipo**: Transportabilidad / validez externa.

**Pregunta**: Un ensayo clinico mostro que un farmaco reduce mortalidad en
8pp en hospitales europeos. Con datos de hospitales africanos (pacientes
mas jovenes, mas comorbilidades infecciosas, menos acceso a UCI), investiga
si el efecto se mantiene, se atenua, o desaparece — y por que.

**Variables**: edad, comorbilidad_cardiovascular, comorbilidad_infecciosa,
acceso_UCI, farmaco, mortalidad, region, nutricion, adherencia.

**Ejemplo de respuesta correcta**:
"El efecto protector se mantiene en pacientes sin comorbilidad infecciosa
(-7pp, similar a Europa). Pero en pacientes con comorbilidad infecciosa
el efecto desaparece (+1pp, NS). La razon: el farmaco interactua con
tratamiento antiinfeccioso, que es mas frecuente en esta poblacion.
El mecanismo central (via cardiovascular) se transporta; el efecto neto
no, porque la distribucion de comorbilidades es distinta."

**Espacio de respuestas**: ACOTADO. Los efectos por subgrupo son verificables
contra el SCM. La explicacion del "por que no transporta" es mas abierta.

**Limitacion SREG actual**: Requiere dos datasets (o un SCM con dos regimenes
de parametros). No requiere experimentacion — es analisis observacional
de dos poblaciones.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 35% | Efectos por subgrupo/poblacion correctos? |
| Completitud | 25% | Identifico QUE se transporta y que no? |
| Especificidad | 25% | Explico POR QUE no se transporta (mecanismo)? |
| Calibracion | 15% | Distinguio "no se transporta" de "no funciona"? |

---

### [22] Biologia — Dos mecanismos explican lo mismo: cual es real?

**Tipo**: Discriminacion de modelos / equifinalidad.

**Pregunta**: Dos equipos proponen mecanismos distintos para un tratamiento.
Teoria A: actua via reduccion de inflamacion. Teoria B: actua via
estimulacion inmune. Con datos observacionales, ambas predicen lo mismo.
Que evidencia discriminaria entre ellas?

**Variables**: tratamiento, inflamacion, respuesta_inmune, outcome,
biomarcador_inflamatorio, biomarcador_inmune, dosis, tiempo.

**Ejemplo de respuesta correcta**:
"Con datos observacionales, ambas teorias son compatibles (r=0.91 con datos).
Para discriminar: si bloquear inflamacion (controlando biomarcador_inflamatorio)
elimina el efecto del tratamiento, Teoria A es correcta. En los datos,
la correlacion parcial tratamiento→outcome|inflamacion es 0.02 (NS), lo que
favorece Teoria A. Sin embargo, esto no es concluyente — una intervencion
sobre inflamacion seria definitiva."

**Espacio de respuestas**: ABIERTO. Multiples analisis son validos para
acumular evidencia a favor/en contra de cada teoria. Lo valioso es
identificar que PREGUNTA separa las teorias, no solo elegir una.

**Limitacion SREG actual**: Requiere un SCM donde la verdad es UNA de las
teorias, pero ambas generan datos observacionales similares. No requiere
experimentacion — el solver analiza datos y propone que evidencia discriminaria.

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 25% | El analisis observacional es correcto? |
| Especificidad | 30% | Propuso una prueba discriminante concreta? |
| Calibracion | 30% | Reconocio los limites de la evidencia observacional? |
| Completitud | 15% | Considero ambas teorias seriamente? |

---

### [23] Salud publica — Que medicion reduce mas la incertidumbre?

**Tipo**: Value-of-information / diseño de evidencia.

**Pregunta**: Un equipo quiere estimar el efecto de contaminacion en asma
infantil. Tiene presupuesto para 2 mediciones adicionales entre: (a) monitoreo
individual de exposicion, (b) genotipado de susceptibilidad, (c) encuesta
de habitos indoor, (d) medicion de pollen counts. Cuales 2 reducen mas la
incertidumbre sobre el efecto causal?

**Variables**: PM25_zona (proxy), asma, trafico, zona_industrial, NSE,
exposicion_indoor (no medida), genotipo_suscept (no medido),
pollen (no medido), humedad.

**Ejemplo de respuesta correcta**:
"La medicion mas valiosa es (a) monitoreo individual: elimina el error de
medicion del proxy PM25_zona y permite separar efecto de contaminacion de
efecto de zona industrial. Segundo: (b) genotipado, porque permite
identificar subgrupos de susceptibilidad y reduce varianza residual. (c)
habitos indoor tiene valor moderado (confounder parcial). (d) pollen no
aporta — no esta en el pathway causal relevante."

**Espacio de respuestas**: ACOTADO. El SCM conoce que informacion da cada
medicion. Se puede calcular la reduccion de incertidumbre de cada opcion.
Pero el razonamiento del "por que" es mas abierto.

**Limitacion SREG actual**: No hay experimentacion interactiva (el solver
no "mide" realmente). Pero se puede plantear como analisis de datos
parciales: el solver ve los datos sin las variables ocultas y debe razonar
sobre cual revelaria mas informacion. La verificacion es contra el SCM
completo (que SI tiene las variables ocultas).

**Rubrica**:
| Dimension | Peso | Como se mide |
|---|---|---|
| Veracidad | 30% | El ranking de mediciones es correcto vs el VOI real? |
| Especificidad | 30% | Explico POR QUE cada medicion aporta (o no)? |
| Calibracion | 25% | Cuantifico valor de informacion o solo dijo "esta es mejor"? |
| Relevancia | 15% | Las mediciones recomendadas son realistas? |

---

## Nota sobre limitaciones actuales de SREG

Los escenarios 18 (optimizacion), 21 (dos poblaciones), 22 (discriminacion),
y 23 (value-of-information) asumen capacidades que SREG no tiene hoy:

- **No hay experimentacion interactiva**: el solver no puede "correr un
  experimento" y recibir nuevos datos. Trabaja con datasets estaticos.
- **No hay interaccion con el entorno**: no hay loop cerrado de
  proponer-medir-actualizar.
- **No hay multiples datasets/regimenes**: un episodio tiene un mundo con
  un set de datos.

Estos escenarios estan incluidos porque representan tipos de investigacion
REALES que SREG deberia cubrir eventualmente. Para cada uno, la columna
"Limitacion SREG actual" explica que se puede hacer HOY (analisis
observacional de datos estaticos) y que requiere desarrollo futuro
(interaccion, multiples regimenes, closed-loop).

**El scoring y el diseno general NO deben excluir estos tipos.** Deben
estar preparados para incorporarlos sin rediseno fundamental.

---

## Resumen de cobertura

| Tipo de investigacion | Escenarios | Espacio de respuesta tipico |
|---|---|---|
| Causal simple | 1 | Acotado |
| Multi-outcome / trade-off | 2, 3, 4, 5 | Abierto |
| System mapping | 6, 7, 8, 9 | Abierto |
| Confounding como objetivo | 10, 11 | Acotado |
| Heterogeneidad | 12, 13 | Abierto |
| Descriptivo / exploratorio | 14 | Muy abierto |
| Predictivo | 15 | Unica (metrica) |
| Exploracion de espacio | 16 | Acotado |
| Metodologico | 17 | Acotado |
| Diseño / optimizacion | 18 | Unica (metrica) |
| Taxonomia / epistemico | 19, 20 | Abierto / Acotado |
| Transportabilidad | 21 | Acotado |
| Discriminacion de modelos | 22 | Abierto |
| Value-of-information | 23 | Acotado |

### Patron clave para scoring

- **Respuesta UNICA** (15, 18): scoring por metrica puntual (RMSE, optimo)
- **Respuesta ACOTADA** (1, 4, 8, 10, 11, 16, 17, 20, 21, 23): claims verificables contra SCM, conjunto finito de respuestas validas
- **Respuesta ABIERTA** (2, 3, 5, 6, 7, 9, 12, 13, 14, 19, 22): multiples investigaciones correctas posibles, scoring por dimensiones

El scoring de SREG debe funcionar para los 3 tipos de espacio de respuesta.

### Que puede SREG hoy vs que requiere desarrollo futuro

| Capacidad | Escenarios que la usan | Status |
|---|---|---|
| Analisis observacional de datos estaticos | 1-14, 19-22 | HOY funciona |
| Prediccion con train/test split | 15, 16 | Requiere framework de eval predictiva |
| Optimizacion interactiva (closed-loop) | 18 | FUTURO: requiere interaccion con entorno |
| Multiples datasets/regimenes | 21 | FUTURO: requiere multi-world support |
| Variables ocultas revelables | 23 | FUTURO: requiere interaccion con entorno |
| Datasets con missing data estructural | 17, 20 | Parcial: missing no implementado en SCM |
