---
name: eval
description: Evaluate SRC quality — quantitative metrics AND qualitative rubric + open discovery. Use after changes that affect SRC generation, or periodically as health check. The most important evaluation tool in the project.
---

Evaluate Synthetic Research Cases (SRCs) for quality. Level 2 evaluation:
"are the environments good for training scientific judgment?"

**Two components, both mandatory:**
1. Qualitative: structured rubric + open-ended discovery
2. Quantitative: OI scores from real solver runs

Qualitative is MORE IMPORTANT. Scores can mislead (compiler bottleneck).

## Azure LLM

**Azure esta SIEMPRE disponible.** Credenciales en `.env` (raiz del repo),
cargadas automaticamente por `python-dotenv`. No verificar env vars manualmente.
Solo ejecutar los scripts.

## Step 1: Generate or select SRCs

Parse $ARGUMENTS:
- If a path to an existing case is given, use that
- If a topic/seed is given, generate with `/run`
- If nothing specified, generate 2-3 SRCs with diverse seeds

```bash
# Generate with inspection
python scripts/generate_src.py --goal "..." -o experiments/eval_TOPIC/ --inspect --seed N

# Generate with OI solver run
python scripts/generate_src.py --goal "..." -o experiments/eval_TOPIC/ --oi --seed N
```

## Validar contra escenarios diversos — NO NEGOCIABLE

Cualquier cambio de scoring, compiler, IR, o contratos debe funcionar para
la MAYORIA de los tipos de investigacion diversos
(`research/synthesis/investigation_scenarios_rubric.md`).

No solo "X causa Y" — tambien: system mapping, structure discovery,
descriptivo, predictivo, epistemologico, optimizacion, multi-outcome, etc.
Si solo funciona para causal simple, es un juguete. Si mejora 3 pero rompe 5, no vale.

## Step 2: Qualitative evaluation — structured rubric

Read `briefing.md` and `answer_key.md` for each case. Score:

### 7 Dimensions (0 = falla, 1 = mixto, 2 = convincente)

| D# | Dimension | Que evaluar |
|----|-----------|-------------|
| D1 | Framing real | Brief suena a encargo profesional, no a ejercicio? |
| D2 | Necesidad de datos | Se puede responder sin mirar los datos? |
| D3 | Coherencia entre capas | Brief, deliverables, datos cuentan la misma historia? |
| D4 | Validez de comparacion | Las intervenciones tienen sentido cientifico? |
| D5 | Realismo de datos | Variables con unidades, panel, missingness, proxies? |
| D6 | Riqueza epistemica | Ambiguedad, alternativas, sensibilidad a supuestos? |
| D7 | Workflow investigativo | El caso invita a explorar, contrastar, chequear robustez? |

### 6 Critical Failures (binarios — cualquiera = defecto grave)

| CF# | Failure | Como detectar |
|-----|---------|---------------|
| CF1 | answerable_without_data | LLM responde bien sin dataset |
| CF2 | exam_like_wording | "Answer A or B", "Submit a distribution" |
| CF3 | brief_eval_mismatch | Brief habla de un tema, sub-preguntas de otro |
| CF4 | variable_name_leak | snake_case, node IDs visibles al investigador |
| CF5 | toy_comparison | Intervenciones sin sentido ("set X to high") |
| CF6 | narrative_as_skin | Sin narrativa, el caso se resuelve igual |

### LA PREGUNTA doble (evaluar para cada SRC)

- **Investigacion real?** Un cientifico del dominio creeria que esto es un caso real?
- **Entrenaria buen juicio?** Un modelo entrenando con RL sobre este caso,
  aprenderia research taste, a descomponer problemas, a formular preguntas
  finas, a saber cuando una conclusion es prematura?

## Step 3: No-data baseline probe

El test mas poderoso. Para cada SRC:
1. Tomar el brief (de `briefing.md`)
2. Darselo a un LLM SIN dataset, SIN esquema
3. Pedirle que responda
4. Si responde bien, CF1 = el SRC no fuerza investigacion

## Step 4: Descubrimiento abierto

Leer el caso con ojos frescos. Buscar CUALQUIER cosa artificial.
- Un cientifico creeria que esto es real?
- Las preguntas son las que un investigador haria?
- Los datos se ven como un dataset real?
- Hay algo que suene a "juego"?
- Las unidades y rangos son plausibles?

Cuando encuentres un problema nuevo: documentarlo, evaluar si es recurrente.

## Step 5: Quantitative (si hay OI run)

Si se corrio `--oi`, revisar los scores:
- **OI total score**: correctness + coverage + efficiency
- **Claim compilation**: cuantos claims se compilaron correctamente?
- **Submission**: entrego claims el solver?
- **Compiler quality**: algun claim correcto fue mal traducido? (el bottleneck)

No confiar solo en scores — leer los claims del solver y las verificaciones.

## Step 6: Reportar al usuario

En espanol:
1. Resumen: cuantos SRCs, verdict general
2. Tabla de dimensiones por SRC
3. Critical failures encontrados
4. Hallazgos nuevos
5. LA PREGUNTA doble: evaluacion honesta

## Referencia

- Rubrica: `research/synthesis/qualitative_eval_rubric.md`
- Escenarios: `research/synthesis/investigation_scenarios_rubric.md`
- OI vision: `research/synthesis/open_investigation_vision.md`
