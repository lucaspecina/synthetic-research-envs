# Benchmarks para evaluar agentes LLM en razonamiento científico: análisis para SREG

**No existe un benchmark único que cubra las tres habilidades de SREG simultáneamente.** Tras investigar más de 20 benchmarks publicados entre 2023-2026, la conclusión más honesta es que la combinación específica que entrena SREG —razonamiento causal desde datos tabulares, formulación de hipótesis bajo evidencia parcial, y selección de experimentos óptimos— no tiene una evaluación unificada disponible. Sin embargo, un conjunto de **4-5 benchmarks complementarios** puede cubrir las tres dimensiones con scoring automático, datos públicos, y suficiente dificultad para discriminar mejoras pre/post entrenamiento. La buena noticia es que varios benchmarks de 2024-2025 son sorprendentemente cercanos al perfil de SREG, especialmente DiscoveryBench, QRData, SciGym y HypoBench. La mala noticia es que cada uno mide un subconjunto de las habilidades y ninguno replica el formato exacto de "datos tabulares → inferir causas ocultas → decidir qué medir → estimar efectos causales".

---

## Los benchmarks que realmente importan para SREG

Tras analizar todos los candidatos, cinco benchmarks destacan por su alineamiento con las capacidades que SREG entrena. Los presento en orden de relevancia práctica.

### DiscoveryBench: el más alineado para formulación de hipótesis desde datos

**DiscoveryBench** (Allen AI, NeurIPS 2024) es el benchmark más directamente relevante para SREG. El agente recibe **datasets tabulares reales (CSVs)** junto con metadata y un objetivo de descubrimiento en lenguaje natural, y debe producir una **hipótesis en lenguaje natural** sobre relaciones entre variables. La versión DB-REAL contiene **264 tareas** extraídas de 20+ papers publicados en 6 dominios (sociología, biología, economía, humanidades, ingeniería, meta-ciencia), mientras que DB-SYNTH ofrece **903 tareas sintéticas** con dificultad controlada mediante "hypothesis semantic trees".

El scoring es automático mediante **Hypothesis Matching Score (HMS)**, que descompone la hipótesis predicha y la gold en tres facetas: contexto (condiciones de contorno), variables identificadas, y relaciones entre variables. Usa GPT-4 como juez, con faceted evaluation que es más robusta que comparación holística. El mejor agente (Reflexion con GPT-4o) alcanza solo **25% HMS**, lo que deja amplio margen para demostrar mejoras post-SREG.

**Alineamiento con SREG**: ★★★★★ para formulación de hipótesis, ★★★★ para razonamiento causal (las tareas incluyen relaciones causales pero también correlacionales), ★★ para diseño experimental (no lo evalúa). Disponible en GitHub (github.com/allenai/discoverybench) y HuggingFace (allenai/discoverybench), licencia ODC-BY. La evaluación se ejecuta con un CLI sencillo y soporta múltiples modelos.

**Limitaciones honestas**: El scoring por LLM-judge introduce variabilidad entre ejecuciones (no es determinista). Para comparaciones before/after, conviene promediar múltiples runs de evaluación. Además, no toda tarea es genuinamente causal — algunas hipótesis gold son correlacionales o descriptivas. Y el formato requiere que el agente genere código Python para analizar datos, lo cual mide parcialmente capacidad de coding.

### QRData: la prueba directa de razonamiento causal con datos reales

**QRData** (ACL Findings 2024) es el único benchmark que explícitamente mide **razonamiento estadístico y causal con datos tabulares reales** de forma separada. Contiene **411 preguntas** acompañadas de archivos de datos (CSVs) de textbooks, cursos y papers académicos, más 290 preguntas solo texto como control. Las preguntas cubren intervalos de confianza, tests de hipótesis, distribuciones, regresión, y crucialmente, **inferencia causal** (estimación de efectos de tratamiento, identificación de confounders, causal discovery).

El scoring es **automático por accuracy** (comparación exacta contra respuestas gold, tanto multiple-choice como numéricas). GPT-4 alcanza **58%** accuracy general, pero el rendimiento cae dramáticamente en preguntas causales vs. estadísticas — exactamente el tipo de señal que revelaría si SREG mejora el razonamiento causal específicamente.

**Alineamiento con SREG**: ★★★★★ para razonamiento causal con datos, ★★★ para formulación de hipótesis (algunas preguntas lo requieren indirectamente), ★ para diseño experimental. Disponible en GitHub (github.com/xxxiaol/QRData).

**Limitaciones honestas**: Solo 411 preguntas (el subset causal es más pequeño aún). El formato es Q&A estático, no multi-step agentic — el modelo responde una pregunta, no itera. Esto lo hace útil como test rápido pero no captura el comportamiento agentivo que SREG entrena. Las preguntas son estilo textbook, más estructuradas que los problemas abiertos de investigación real.

### SciGym: el más cercano al ciclo completo de SREG para diseño experimental

**SciGym** (julio 2025) es un "dry lab" donde el agente actúa como científico en sistemas biológicos simulados. Recibe sistemas codificados en SBML (Systems Biology Markup Language) y debe **proponer experimentos de perturbación** (knockouts, cambios de parámetros), observar los **resultados simulados como series temporales**, y iterativamente **recuperar la estructura causal** del sistema biológico subyacente. Esto captura el ciclo completo: decidir qué medir → observar → inferir causalidad → refinar.

El scoring usa **graph edit distance** contra el modelo ground-truth (completamente determinista, sin LLM judge). Están disponibles **350 sistemas biológicos** (137 evaluados en el paper, 213 adicionales). Todos descargables de GitHub (github.com/h4duan/SciGym) y HuggingFace (h4duan/scigym-sbml).

**Alineamiento con SREG**: ★★★★★ para diseño experimental / selección de qué medir, ★★★★ para razonamiento causal (inferir estructura causal de datos observacionales + intervencionistas), ★★★★ para formulación de hipótesis (el agente propone hipótesis iterativamente). Es el benchmark más cercano al loop completo de SREG.

**Limitaciones honestas**: Los "datos" son series temporales de simulaciones biológicas, no tablas tabulares con variables discretas como en SREG. El dominio es exclusivamente biología de sistemas. La infraestructura es más compleja de montar que un simple Q&A benchmark. Requiere familiaridad con SBML y simulación.

### HypoBench: evaluación rigurosa de descubrimiento de hipótesis

**HypoBench** (arXiv abril 2025, U. Chicago) evalúa sistemáticamente la generación de hipótesis desde datos. Contiene **194 datasets** en 12 dominios (7 real-world: detección de engaños, contenido AI, persuasión, estrés mental, engagement de noticias, predicción de citas, retweets; 5 sintéticos con dificultad controlable). El agente recibe **datos tabulares/estructurados** y debe generar hipótesis en lenguaje natural sobre patrones explicativos.

El scoring combina **Hypothesis Discovery Rate (HDR)** = Feature Discovery Rate × Relationship Correctness, más métricas de utilidad práctica (accuracy cuando la hipótesis se usa como prompt para clasificación) y generalización (IND vs OOD). Usa LLM-judge validado contra humanos con **κ=0.80-0.86**.

**Alineamiento con SREG**: ★★★★★ para formulación de hipótesis, ★★★★ para razonamiento causal (descubrir features y relaciones causales), ★★ para diseño experimental. Código y datos en GitHub (ChicagoHAI/HypoBench-datasets) y HuggingFace.

**Limitaciones**: Las tareas son más de "pattern discovery" que de inferencia causal formal. Los datasets sintéticos con dificultad controlable son ideales para before/after, pero el LLM judge introduce algo de variabilidad.

### BLADE: la evaluación de decisiones analíticas con datos

**BLADE** (EMNLP 2024 Findings, UW) evalúa las **decisiones analíticas** que un agente toma al enfrentar datos + una pregunta de investigación abierta. El agente recibe un **dataset tabular + pregunta de investigación** y debe: (1) formular variables conceptuales (IV, DV, controles), (2) ejecutar transformaciones de datos, y (3) implementar modelos estadísticos. Las decisiones se comparan contra **500+ decisiones de expertos humanos** en 12 datasets reales.

El scoring es **automático**, comparando las decisiones del agente contra ground-truth multi-experto. Evalúa las decisiones intermedias (no solo la respuesta final), lo que es especialmente relevante para SREG que entrena el proceso de razonamiento.

**Alineamiento con SREG**: ★★★★★ para decidir qué variables medir y cómo analizarlas, ★★★★ para razonamiento causal (las preguntas de investigación frecuentemente implican relaciones causales), ★★★ para formulación de hipótesis. GitHub: github.com/behavioral-data/BLADE.

**Limitaciones**: Solo **12 tareas** — el N es muy bajo para comparaciones estadísticas robustas before/after. El scoring incluye componente de LLM-assisted matching para comparar representaciones de variables.

---

## Benchmarks parcialmente relevantes que merecen consideración

### CLadder: razonamiento causal formal, pero sin datos

CLadder (NeurIPS 2023) contiene **10,112 preguntas** que cubren los tres niveles de Pearl (asociación, intervención, contrafactual). Cada pregunta presenta una descripción textual de un grafo causal + probabilidades numéricas embebidas en texto, y el modelo responde yes/no. El scoring es **exact-match binario**, completamente determinista. Disponible en HuggingFace (causalNLP/cladder) y GitHub.

Es útil como **control textual**: si SREG mejora el razonamiento causal general (no solo con datos), CLadder lo detectaría. GPT-4 con CausalCoT alcanza 70.4%, así que hay margen para mejora. **Pero no involucra datos tabulares reales** — todo es verbal. Mide si el modelo "sabe do-calculus", no si puede aplicarlo a datos reales.

### CORR2CAUSE: inferencia correlación→causación, abstracta

CORR2CAUSE (ICLR 2024) presenta **~4,500 instancias test** donde el modelo recibe correlaciones textuales entre variables abstractas (A, B, C) y debe determinar si una hipótesis causal es válida. Scoring binario automático. Disponible en HuggingFace y GitHub. LLMs rinden cerca del azar, lo que lo hace sensible a mejoras.

Relevante porque SREG entrena exactamente esta habilidad — inferir causalidad desde correlaciones. **Pero las correlaciones son declaradas textualmente**, no derivadas de datos. Y las variables son abstractas (sin semántica de dominio).

### CausalBench (Zhou et al., CausalBN-Bench): descubrimiento causal con datos en prompts

Este benchmark (arXiv 2024) usa **15 redes bayesianas reales** de Bnlearn y presenta cuatro formatos de prompt progresivos: solo nombres de variables, + conocimiento de fondo, + datos numéricos reales, o todo combinado. Evalúa identificación de correlaciones, esqueleto causal y dirección causal. Disponible en GitHub (Rainy-ZhouYu/CausalBN-Bench).

**Hallazgo clave y preocupante**: los LLMs entienden causalidad por **asociaciones semánticas con nombres de entidades**, no por distribuciones numéricas. Esto significa que incluir datos numéricos no mejora el rendimiento — el modelo usa los nombres de las variables. Esto es relevante para SREG: si SREG logra que el modelo realmente use los datos numéricos, este benchmark lo detectaría.

### CauSciBench: pipeline causal end-to-end (emergente)

CauSciBench (NeurIPS 2025 Workshop, ETH Zürich) evalúa el **pipeline completo de inferencia causal**: formulación del problema → selección de variables → elección de método (IPW, IV, DID, RDD) → implementación → interpretación. **305-367 tareas** de 52+ datasets en 9 disciplinas. El paper afirma disponibilidad en github.com/causalNLP/CauSciBench, pero la verificación del repositorio no fue concluyente. Si está disponible, sería **el benchmark más directamente alineado** con la parte de estimación causal de SREG. Su principal limitación es que es de un workshop, no está tan establecido como DiscoveryBench o QRData.

### DiscoveryWorld: ciclo científico completo en mundo virtual

DiscoveryWorld (Allen AI, NeurIPS 2024 Spotlight) es un entorno virtual tipo **text adventure** donde el agente completa ciclos de descubrimiento: formulación de hipótesis, diseño de experimentos, ejecución, análisis de resultados. Contiene **120 tareas** en 8 temas × 3 niveles de dificultad. Scoring con 3 métricas automatizadas. Público en GitHub.

Es conceptualmente muy alineado con SREG, pero operacionalmente problemático: el formato es un juego de texto 2D con tiles navegables, no análisis de datos tabulares. Requiere un agente que interactúe con un simulador gráfico, lo que añade complejidad significativa y mide habilidades de navegación además de razonamiento científico.

### HypoSpace: generación de múltiples hipótesis bajo indeterminación

HypoSpace (octubre 2025, NUS/Meta) evalúa si los modelos pueden generar **sets de hipótesis válidas** bajo datos insuficientes. Incluye un dominio de **inferencia de grafos causales** desde perturbaciones. El scoring es completamente **determinista** (sin LLM judge): validez, unicidad, y cobertura del espacio de hipótesis admisibles. Disponible en GitHub.

Relevante porque mide exactamente la capacidad de razonar bajo **evidencia parcial**, una habilidad core de SREG. Los autores advierten explícitamente que es un "diagnostic probe" con settings abstractos, no un benchmark de descubrimiento real.

---

## Benchmarks investigados pero poco relevantes para SREG

**ScienceAgentBench** (ICLR 2025, 102 tareas): Fundamentalmente un benchmark de **generación de código científico**. El agente escribe programas Python para procesar datos de papers publicados. Aunque involucra datos científicos reales, evalúa si el código funciona correctamente, no si el razonamiento causal es correcto. Útil como proxy de capacidad técnica general, no de razonamiento científico per se.

**PaperBench** (OpenAI, ICML 2025, 20 papers): Replicación de papers de ML. Totalmente centrado en **ingeniería ML y coding**. Las 8,316 sub-tareas evalúan implementación de algoritmos, no razonamiento científico. Irrelevante para SREG.

**MLAgentBench** (ICML 2024, 13 tareas) y **MLE-bench** (OpenAI, ICLR 2025, 75 Kaggle competitions): Benchmarks de **ingeniería ML** — mejorar modelos, optimizar pipelines, formatear submissions. Cero contenido de razonamiento causal, hipótesis, o diseño experimental científico.

**DSBench** (ICLR 2025, 540 tareas): Competencias de data science (ModelOff + Kaggle). Mide habilidad analítica práctica y ML, no razonamiento causal o científico.

**ResearchGym** (febrero 2026, 5 entornos, 39 sub-tareas): Evalúa agentes en **investigación ML end-to-end** (proponer hipótesis, implementar, experimentar). Solo dominio AI/ML, infraestructura compleja, muy reciente. GPT-5 mejora baselines en solo 6.7% de evaluaciones. Poco relevante para las habilidades específicas de SREG.

---

## El gap real: por qué no existe el benchmark perfecto para SREG

El espacio de benchmarks existente tiene un **agujero estructural** exactamente donde SREG opera. La razón es que SREG combina tres capacidades que los benchmarks existentes tratan separadamente:

Los benchmarks de **razonamiento causal** (CLadder, CORR2CAUSE, CausalBench) son predominantemente **textuales** — presentan grafos causales y probabilidades en lenguaje natural, no en datasets. Miden si el modelo "sabe" do-calculus, no si puede descubrir estructura causal desde datos ruidosos.

Los benchmarks de **análisis de datos** (DiscoveryBench, QRData, BLADE, DSBench) dan datos tabulares pero evalúan primariamente **formulación de hipótesis o respuestas estadísticas**, sin un componente explícito de "elige qué medir next" o "diseña el siguiente experimento bajo presupuesto limitado".

Los benchmarks de **diseño experimental** (SciGym, BioDiscoveryAgent, DiscoveryWorld) sí tienen ciclos iterativos de experimentación, pero operan en **dominios especializados** (biología de sistemas, CRISPR, mundos virtuales) con formatos de datos muy diferentes a las tablas tabulares genéricas de SREG.

La **selección de experimentos bajo presupuesto** — una habilidad central de SREG — simplemente no tiene un benchmark dedicado con datos públicos y scoring automático. Este es el gap más significativo.

---

## Recomendación concreta: el suite de evaluación para SREG

La estrategia óptima es un **suite de 4 benchmarks** que cubra las tres habilidades, combinando tests rápidos (Q&A estático) con evaluaciones agentivas (multi-step):

**Para razonamiento causal con datos (Habilidad 1):**
- **QRData** como test rápido y determinista (411 preguntas, accuracy exacta, subset causal separable). Ventaja: scoring completamente determinista, rápido de ejecutar, línea base clara.
- **CLadder** como control de razonamiento causal formal (10,112 preguntas, binary exact-match). Aunque es textual, mide si SREG mejora el razonamiento causal abstracto como efecto secundario.

**Para formulación de hipótesis (Habilidad 2):**
- **DiscoveryBench** como evaluación principal (264 tareas reales con datos tabulares, HMS scoring). Es el benchmark más directamente alineado con lo que hace SREG. Usar DB-SYNTH para las evaluaciones durante el desarrollo (más tareas, dificultad controlable) y DB-REAL para la evaluación final (más realista pero solo 264 tareas).

**Para diseño experimental y ciclo completo (Habilidad 3):**
- **SciGym** como evaluación de capacidad iterativa (350 sistemas, graph edit distance determinista). Captura el loop proponer-observar-refinar que SREG entrena. Es la opción más práctica con scoring determinista.

**Suite complementaria opcional:**
- **HypoBench** si se necesita más granularidad en hipótesis (194 datasets, scoring multidimensional)
- **CORR2CAUSE** como test rápido adicional de correlación→causación (4,500 instancias, binario)
- **CauSciBench** si se confirma disponibilidad pública (pipeline causal end-to-end, el más alineado teóricamente)

Esta combinación de 4 benchmarks principales cubre las tres dimensiones, mezcla scoring determinista (QRData, CLadder, SciGym) con scoring por LLM-judge validado (DiscoveryBench), incluye formatos estáticos (Q&A) y agentivos (multi-step), y todos están públicamente disponibles con suficientes tareas para comparaciones estadísticas significativas. Los modelos frontier rinden entre **25-58%** en estos benchmarks, lo que garantiza headroom para demostrar mejoras post-SREG.

El tradeoff principal es que **ninguno replica exactamente** el formato de SREG (datos tabulares → causas ocultas → presupuesto → selección de mediciones). Para una evaluación verdaderamente alineada, sería necesario construir un benchmark custom — pero este suite de 4 benchmarks externos proporciona la validación externa más creíble actualmente disponible.