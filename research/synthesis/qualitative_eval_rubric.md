# Rubrica de evaluacion cualitativa para SRCs

> Sintesis de sesion 2026-03-24. Consensuada entre Claude, Codex y usuario.
>
> **Motivacion:** Todas las mejoras fundamentales de SREG se encontraron via
> inspeccion cualitativa ad-hoc (preguntas tipo examen, mecanicas de juego,
> framing artificial). El framework cuantitativo existente
> (`eval_design_notes.md`, `eval_strategy.md`) no captura estos problemas.
> Necesitamos formalizar la evaluacion cualitativa para no depender de
> revisiones casuales.

## Contexto y problema

### Que tenemos hoy

El framework de evaluacion define 3 niveles (tests, diagnostico, transfer)
y 25+ metricas cuantitativas (KL, submit rate, budget efficiency, etc.).
Implementado: DiagnosticRunner con per-type baselines y verdicts.

### Que NO captura

Un SRC puede tener buen KL, buen submit rate, y verdicts "GOOD", pero:
- Las preguntas suenan a parcial de universidad
- La narrativa es decoracion superficial sobre una estructura formal
- El solver responde desde priors de dominio sin mirar los datos
- Las "intervenciones" no tienen sentido cientifico real
- El brief y las preguntas internas cuentan historias diferentes

Estos problemas solo se detectan LEYENDO los casos. Los numeros no los ven.

### La pregunta ordenadora

> "Este SRC funciona como una mini-investigacion cientifica realista,
> verificable, y util para entrenar agentes?"

Si la respuesta es no, el SRC es defectuoso — no importa si los numeros
estan bien.

## Rubrica: 7 dimensiones + 6 critical failures

### Dimensiones (escala 0-1-2)

| # | Dimension | 0 = falla | 1 = mixto | 2 = convincente |
|---|-----------|-----------|-----------|-----------------|
| D1 | **Framing real** | Brief suena a ejercicio academico o benchmark | Brief tiene elementos reales pero tambien lenguaje de benchmark | Brief suena a encargo profesional real que un investigador recibiria |
| D2 | **Necesidad de datos** | Se puede responder sin mirar los datos (priors de dominio o sentido comun bastan) | Algunas preguntas necesitan datos, otras no | Un investigador no podria responder ninguna pregunta sin analizar los datos |
| D3 | **Coherencia entre capas** | Brief, deliverables, preguntas eval, y dataset cuentan historias diferentes | Parcialmente alineados pero con desconexiones | Brief, deliverables, hidden eval, dataset y scoring cuentan la misma historia |
| D4 | **Validez de comparacion** | Las intervenciones/comparaciones no tienen sentido cientifico (ej: "maximize algo negativo") | Parcialmente justificadas | Las comparaciones son las que un equipo de investigacion propondria |
| D5 | **Realismo de datos** | Variables genericas, unidades faltantes, estructura plana | Algunos elementos realistas | Variables con unidades, panel structure, missingness, proxies — se siente como un dataset real |
| D6 | **Riqueza epistemica** | Una sola respuesta correcta obvia, sin ambiguedad | Algo de incertidumbre pero limitada | Hay explicaciones alternativas, sensibilidad a supuestos, posibilidad de estar equivocado |
| D7 | **Workflow investigativo** | El caso se resuelve con una sola operacion | Requiere algunos pasos pero lineales | El caso invita a explorar, contrastar, chequear robustez — un proceso de investigacion |

### Critical failures (binarios)

Cualquier critical failure detectado significa que el SRC tiene un defecto
grave que debe corregirse antes de usarse para entrenamiento.

| ID | Critical failure | Como detectarlo |
|----|-----------------|-----------------|
| CF1 | `answerable_without_data` | Darle a un LLM el brief + preguntas SIN dataset. Si responde bien, falla. |
| CF2 | `exam_like_wording` | Frases como "Answer A or B", "Submit a distribution", "maximize X above Y" |
| CF3 | `brief_eval_mismatch` | El brief habla de un tema y las preguntas eval de otro, o no hay conexion |
| CF4 | `variable_name_leak` | El investigador ve nombres internos (snake_case, node IDs, eval type names) |
| CF5 | `toy_comparison` | Intervenciones o comparaciones sin sentido cientifico (set X to high, maximize negativo) |
| CF6 | `narrative_as_skin` | La narrativa es decoracion — si la quitaras, el caso se resolveria igual |

## Probe hibrido: no-data baseline

El probe mas poderoso para D2 y CF1:

1. Tomar el brief + preguntas visibles (sin dataset, sin esquema)
2. Darle a un LLM y pedirle que responda
3. Comparar con el ground truth

Si el LLM sin datos supera al random baseline, el SRC no fuerza investigacion.

**Implementacion minima:** un script que toma un briefing.md, alimenta un LLM,
y compara con answer_key.md. Corre despues de generar el SRC.

## Protocolo de revision cualitativa

### Cuando correrla

- **Obligatorio:** despues de cada cambio que afecte la generacion de SRCs
  (templates, prompts, orchestrator, problem builder, semantics)
- **Recomendado:** periodicamente como health check del generador

### Set de revision

- **Minimo:** 3 SRCs de dominios distintos (uno por paper seed)
- **Recomendado:** 10-20 SRCs para cambios grandes
- **Fijo:** mantener un set canonico de 5 seeds para comparacion temporal

### Proceso

1. Generar SRCs con `--inspect`
2. Leer `briefing.md` y `answer_key.md` de cada caso
3. Evaluar cada dimension (0/1/2) y marcar critical failures
4. Registrar en formato estructurado (ver abajo)
5. Opcionalmente: correr no-data baseline probe

### Formato de registro

```
case_id: football-2026-03-24
commit: abc1234
reviewer: human|claude|codex
dimensions:
  framing_real: 2
  data_necessity: 1
  layer_coherence: 1
  comparison_validity: 1
  data_realism: 2
  epistemic_richness: 1
  investigation_workflow: 1
critical_failures: [exam_like_wording, variable_name_leak]
evidence: "Q2 uses snake_case variable names as fallback. Q3 still has ..."
overall_verdict: NEEDS_WORK
```

### Tracking temporal

- Guardar reviews en `experiments/qualitative/` como CSV/JSONL
- Medir por version: media por dimension, tasa de critical failures
- Comparacion pairwise: "version A vs B, cual se parece mas a investigacion
  real y por que?"

## Relacion con los 3 niveles existentes

| Nivel | Rol de la rubrica |
|-------|-------------------|
| **Tests (L1)** | Promover invariantes obvios a checks automaticos (ej: CF2 puede ser regex, CF4 puede ser pattern match) |
| **Diagnostico (L2)** | **Hogar principal.** Muestreo cualitativo estructurado como parte del diagnostico, no solo metricas numericas |
| **Transfer (L3)** | Estratificar: si entrenar con SRCs de mala rubrica no transfiere, confirma que el scaffold era incorrecto |

## Descubrimiento abierto — mas alla de la rubrica

Las 7 dimensiones y 6 critical failures son el PISO de la evaluacion, no
el techo. Los problemas mas importantes de SREG se descubrieron fuera de
cualquier checklist — leyendo casos con ojos frescos.

### Principio

**Si encontras un problema y no esta en la rubrica, el problema es real y
la rubrica esta incompleta.** Nunca ignorar algo porque "no esta en el
checklist". La rubrica crece a medida que entendemos mejor que hace falta
para que un SRC sea investigacion real.

### Preguntas guia para descubrimiento

Estas no son las unicas preguntas — son puntos de partida. Lo que importa
es leer el caso como si fueras un investigador que lo recibe por primera vez.

- Un cientifico del dominio creeria que este es un caso real?
- Los datos se ven como un dataset real a primera vista?
- Las variables tienen unidades correctas y rangos plausibles?
- Hay algo que un investigador notaria como falso en 10 segundos?
- Las preguntas de investigacion fluyen naturalmente del brief?
- Las intervenciones propuestas son las que un equipo real propondria?
- La narrativa y la estructura formal cuentan la misma historia?
- Hay algo que suene a "juego" o "examen" en vez de "investigacion"?
- El investigador tendria que pensar y explorar, o solo ejecutar?

### Como registrar hallazgos nuevos

Cuando encuentres un problema no cubierto por D1-D7 o CF1-CF6:

1. **Documentar** en el registro de la evaluacion (ver formato en `/eval`)
2. **Clasificar severidad**: low (cosmetic), medium (degrada realismo),
   high (rompe la experiencia investigativa)
3. **Evaluar recurrencia**: aparece en otros SRCs? Es sistematico o puntual?
4. **Decidir accion**:
   - Puntual → fix especifico + nota en el registro
   - Recurrente → candidato a nueva dimension o critical failure

## Evolucion de la rubrica

### Protocolo de promocion

```
Problema nuevo encontrado
    → Registro con fecha + evidencia + caso
        → Aparece en 1 SRC? → Nota, no promover aun
        → Aparece en 2+ SRCs? → Candidato a promocion
            → Es una dimension nueva? (espectro 0-1-2)
            → Es un critical failure? (binario, defecto grave)
            → Es sub-criterio de dimension existente?
        → Discutir con el equipo → Promover o descartar
```

### Criterios para promover

**Nueva dimension (D8, D9...):** el problema tiene un espectro natural de
gravedad (no es binario), es ortogonal a las dimensiones existentes, y
aparece de forma independiente en multiples SRCs.

**Nuevo critical failure (CF7, CF8...):** el problema es binario (existe o no),
su presencia invalida el SRC para entrenamiento, y no es un sub-caso de un
CF existente.

**Sub-criterio de dimension existente:** el problema detalla un aspecto de
una dimension ya definida. No agrega una nueva fila — refina la descripcion
de una existente.

### Versionado

Cuando se agrega una dimension o CF:
- Incrementar version de la rubrica (v1 → v1.1 para sub-criterios, v2 para
  dimensiones/CFs nuevos)
- Las evaluaciones anteriores NO se re-califican (snapshot en el tiempo)
- Documentar el cambio en la seccion de historial

### Historial de cambios

| Version | Fecha | Cambio |
|---------|-------|--------|
| v1.0 | 2026-03-24 | Rubrica inicial: 7 dimensiones + 6 critical failures |

## Registro de hallazgos

> Aqui se documentan problemas nuevos encontrados durante evaluaciones
> cualitativas que no estan cubiertos por las dimensiones o CFs formales.
> Los hallazgos recurrentes se promueven a la rubrica.

_Aun no hay hallazgos registrados. Se poblara durante la primera evaluacion
formal._

## MVP y anti-over-engineering

**Hacer ahora:**
- Definir las 7 dimensiones + 6 critical failures (HECHO en este doc)
- Protocolo de revision manual (HECHO)
- Protocolo de evolucion de rubrica (HECHO en este doc)
- No-data baseline probe (script minimo)
- Revisar 3-5 SRCs manualmente por cambio importante
- Registrar como artifact del diagnostico

**NO hacer ahora:**
- LLM-judge automatizado (necesita 50-100 reviews humanas primero para calibrar)
- Sistema de scoring ponderado sofisticado
- Dashboard o pipeline automatizado
- 25 metricas cualitativas — empezar con las 7+6, crecer organicamente

**Riesgo de over-engineering:** Alto. El valor esta en LEER LOS CASOS y
registrar que se encuentra. No en construir un sistema complicado para
evitar leerlos.

## Fuentes

- Sesion 2026-03-24: diagnostico de 3 SRCs (football, Vaca Muerta, coral reef)
- Review de Codex 2026-03-24: propuesta de rubrica
- `research/synthesis/eval_strategy.md`: framework cuantitativo existente
- `research/notes/eval_design_notes.md`: metricas y disenos experimentales
- `research/notes/real_investigations_analysis.md`: como se ve investigacion real
