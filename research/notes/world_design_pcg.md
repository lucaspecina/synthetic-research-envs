# World design — Vertical 1: Procedural Content Generation (PCG) en videojuegos

> Reporte de investigación generado por agente Explore (2026-05-05). Parte del
> survey en `research/synthesis/world_design_techniques_survey.md`.
>
> Foco: técnicas algorítmicas de generación de mundos en videojuegos y game
> research, evaluadas por su transferibilidad estructural a SREG.

---

## 1. Introducción y contexto

La Generación Procedural de Contenido (PCG) es una familia de técnicas algorítmicas que automatiza la creación de artefactos complejos (niveles, mapas, narrativas, reglas) a partir de descripciones compactas, parámetros y restricciones. El campo nació en la industria de videojuegos pero ha convergido con técnicas de IA, optimización y aprendizaje automático. Para SREG, las lecciones de PCG son directamente transferibles: así como un diseñador de juegos genera *mundos solvables con propiedades calibradas*, un Designer multi-agente en SREG debe generar *SCMs/ODEs ejecutables con propiedades científicamente relevantes* y derivar *tareas de investigación bien formadas* sobre ellos.

## 2. Taxonomía de técnicas PCG

Las técnicas PCG pueden clasificarse según **cómo** generan contenido:

- **Basadas en búsqueda**: usan algoritmos estocásticos (genéticos, simulated annealing) para buscar contenido con propiedades deseadas.
- **Basadas en restricciones**: especifican un espacio de diseño mediante restricciones lógicas (Answer Set Programming, SAT solvers).
- **Constructivas**: construyen contenido mediante reglas gramáticas, L-systems, o algoritmos determinísticos.
- **Basadas en ML**: aprenden distribuciones de contenido existente (VAE, GAN, LSTM).
- **Mixtas**: combinan búsqueda, restricciones y creatividad con participación humana (mixed-initiative).

## 3. Técnicas formales y sistemas clave

### 3.1 Wave Function Collapse (WFC) — Maxim Gumin

**Algoritmo**: toma una imagen de ejemplo bitmap → extrae patrones locales (ventanas 3×3) → genera nuevas imágenes donde cada patrón local coincide con uno del ejemplo.

**Propiedades garantizadas**:
- **Coherencia local**: violaciones de restricciones se detectan y se resuelven mediante backtracking (colapso).
- **Síntesis por ejemplo**: no requiere especificación explícita de reglas; aprende del ejemplo.

**Transferencia a SREG**: WFC es esencialmente *constraint propagation* en acción. Aplicado a SCMs: en lugar de colapsar tiles, se colapsan estructuras causales. Por ejemplo: generar un SCM donde cada par de variables tiene *al menos un path causal* se puede formular como un constraint que se propaga localmente — evitar confounders accidentales o grafos desconectados.

**Referencias**: [Gumin 2016](https://github.com/mxgmn/WaveFunctionCollapse); [Oswald et al. FDG 2019, WFC como constraint solving](https://dl.acm.org/doi/10.1145/3102071.3110566).

### 3.2 Answer Set Programming (ASP) para PCG — Adam Smith & Michael Mateas

**Algoritmo**: modela el espacio de diseño como un programa lógico en ASP. Cada solución es un modelo estable del programa.

**Propiedades garantizadas**:
- **Especificación declarativa**: el diseñador especifica *qué* cumplir (e.g., "toda sala tiene puerta"), no *cómo*.
- **Completitud**: encuentra *todas* las soluciones o declara infeasible.

**Aplicaciones**: niveles RTS, mecánicas arcade, composiciones musicales, narrativas simples. Smith demostró generación de contenido para Proofdoku.

**Transferencia a SREG**: especificar propiedades deseadas de SCMs como restricciones lógicas (e.g., "todo par de variables tiene d-separación de profundidad ≤ 3" o "la ODE tiene al menos dos estados estacionarios"). ASP genera configuraciones garantizadas. La limitación: escalabilidad en grafos grandes (NP-completo).

**Referencias**: [Smith & Mateas 2011, "Answer Set Programming for PCG"](https://adamsmith.as/papers/tciaig-asp4pcg.pdf).

### 3.3 Búsqueda basada en evolución — Julian Togelius & Georgios Yannakakis

**Algoritmo**: representar contenido como genoma, usar algoritmos evolutivos (GA, CMA-ES) + función fitness para buscar soluciones.

**Propiedades garantizadas**:
- **Optimización multiobjetivo**: puede balancear solvability, dificultad, diversidad, novelty.
- **Escalabilidad**: aplicable a espacios muy grandes.

**Función fitness clave**: típicamente combina (a) solvability (¿se puede completar?), (b) dificultad estimada, (c) novelty (distancia a contenido previo).

**Transferencia a SREG**: tuning de hiperparámetros de SCMs/ODEs. Un AG puede ajustar coeficientes para alcanzar rangos deseados de dificultad de investigación sin muestreo ciego.

**Referencias**: [Togelius et al. 2011, "Search-based PCG: Taxonomy and Survey"](http://julian.togelius.com/Togelius2011Searchbased.pdf); [Shaker, Togelius & Nelson 2016, "PCG in Games" textbook](https://www.pcgbook.com/).

### 3.4 L-systems y gramáticas generativas — Lindenmayer

**Algoritmo**: un axioma inicial + reglas de reescritura que se aplican en paralelo. Ejemplo: `"F" → "F+F-F-F+F"` genera fractales.

**Propiedades garantizadas**:
- **Determinismo**: generación completamente predecible (dado seed).
- **Autosimilaridad**: estructura fractal natural, alta compresión.

**Aplicaciones**: terrenos y vegetación en *No Man's Sky* (1400 líneas de código para terreno planeta).

**Transferencia a SREG**: estructuras jerárquicas. Un SCM multinivel podría describirse gramáticamente: nivel 0 = variables root; nivel 1 = mediadores; nivel 2 = confounders. Las reglas garantizan que la expansión respeta causalidad. Especialmente potente para ODEs estructuradas (cadenas de reacciones químicas, redes de regulación génica).

### 3.5 Quality-Diversity: MAP-Elites

**Algoritmo**: mantener un mapa de celdas (archive) donde cada celda representa una "región de comportamiento". Almacenar el mejor candidato por celda. Evolutivos generan nuevos candidatos y los añaden si mejoran su celda o tienen comportamiento novel.

**Propiedades garantizadas**:
- **Diversidad explícita**: genera un *rango* de soluciones, no solo la óptima.
- **Exploración equilibrada**: gasta presupuesto de evaluación en descubrir múltiples regiones.

**Transferencia a SREG**: si SREG necesita no solo *un* SCM sino un *portafolio* de SCMs con propiedades distintas (redes causales sparse vs. dense, ODEs stiff vs. smooth), MAP-Elites es ideal. Las "dimensiones de comportamiento" pueden ser: topología (árbol vs. red), complejidad dinámica, rango de parámetros de dificultad.

**Referencias**: [Cully et al. 2015 MAP-Elites](https://arxiv.org/abs/1504.04909); [Liapis et al. 2019 "Empowering Quality Diversity"](https://arxiv.org/abs/1906.05175).

## 4. Estudios de caso: videojuegos y derivación de tareas

### 4.1 Spelunky 1 — Derek Yu

**Generación**: rooms prefabricados (templates) organizados mediante un grafo de conectividad. Restricción hard: *existe path del spawn al exit*. Algoritmo: coloca rooms, conecta con corredores, valida solvability mediante flood-fill.

**Lección para SREG**: Spelunky demuestra que *solvability es verificable y enforced durante gen*, no post-hoc. En SREG: tras generar SCM, verificar que es identificable (tiene d-separation properties requeridas) antes de derivar GoldQuestions.

**Referencias**: [Derek Yu, "Spelunky" book, Boss Fight Books 2016](https://bossfightbooks.com/products/spelunky-by-derek-yu).

### 4.2 Dwarf Fortress — Tarn Adams

**Generación**: 6+ capas: (1) topografía (heightmap + erosión), (2) geology, (3) biomas, (4) civs (civilizaciones procedurales), (5) historia (eventos, guerras, migraciones), (6) leyendas (artefactos nombrados). Cada capa es input de la siguiente.

**Propiedades garantizadas**:
- **Causalidad histórica**: civilizaciones existen porque el terreno permite asentamientos; guerras porque civs contiguas tienen intereses conflictivos.
- **Coherencia narrativa**: el archivo de leyendas está causalmente entrelazado.

**Lección para SREG**: Dwarf Fortress es el referente de *generación causal multi-capa*. SREG podría adoptar este patrón: (1) genera SCM base, (2) instancia parámetros según características del SCM, (3) ejecuta ODE, (4) analiza trayectorias para derivar "historia" (bifurcaciones críticas, puntos de equilibrio, regiones caóticas), (5) genera GoldQuestions basadas en esos hitos.

### 4.3 Caves of Qud — Freehold Games

**Generación**: (1) genera 5 sultanes antiguos, (2) usa *grammar replacement* para generar eventos de sus vidas, (3) sincroniza eventos mediante constraints, (4) genera leyendas narrativas que racionalizan los eventos.

**Insight clave**: NO usa simulación completa de historia; usa *retroactive coherence*. Los eventos se generan primero, luego se textualizan para ser coherentes.

**Lección para SREG**: *retroactive coherence* es crucial cuando la generación es compleja. SREG puede generar SCM + trayectorias, luego *post-hoc* identificar qué hace interesante cada trayectoria (bifurcación, caos, resonancia), y formular GoldQuestion que "racionaliza" esa propiedad.

**Referencias**: [Caves of Qud GDC 2017 talk "Procedurally Generating History"](https://gdcvault.com/play/1024990/Procedurally-Generating-History-in-Caves).

### 4.4 Minecraft — Biomes, Perlin noise, structures

**Generación**: heightmap (Perlin noise), 3D noise para material, biomas (5 dimensiones), structures (templates colocados según reglas).

**Lección para SREG**: aplicación a ODEs: usar noise multidimensional para generar landscapes de parámetros donde el comportamiento dinámico varía suavemente. Regiones del espacio de parámetros corresponden a "biomas dinámicos" (atractores, ciclos, caos). Structures = puntos singulares (equilibrios, bifurcaciones) donde formular GoldQuestions.

### 4.5 No Man's Sky — Procgen a escala galaxia

**Generación**: Perlin noise 3D + L-systems + seed determinístico. 18 quintillones de planetas, cada uno generado on-demand.

**Lección para SREG**: *determinismo + seed* es crucial para reproducibilidad. SREG debería permitir generar SCM/ODE desde un seed reproducible. *Eficiencia* (1400 líneas para un planeta) sugiere que gramáticas generativas pueden ser muy compactas.

## 5. Mixed-Initiative PCG: Sentient Sketchbook y Tanagra

**Sentient Sketchbook** (Liapis, Yannakakis, Togelius): Designer dibuja sketch grueso, IA completa el nivel garantizando solvability y diversidad.

**Tanagra** (Smith): nivel parcial dibujado + constraint solver completa y recoloca elementos manteniendo accesibilidad.

**Lección para SREG**: si el investigador (usuario) quiere participar en diseño de SCM, un sistema mixed-initiative puede:
1. Aceptar sketch: "quiero confounders en X y Z; mediador en M".
2. Generar completaciones consistentes (mediante SAT/constraint solving).
3. Validar que la GoldQuestion es solvable dada la estructura.

## 6. Top 5 técnicas más transferibles a SREG

### 1. Wave Function Collapse + Constraint Propagation
*Por qué*: WFC garantiza coherencia local sin especificar reglas globales. En SCMs: "asegura que cada subgrafo local respeta d-separation y confounding". Backtracking automático cuando hay conflicto.

### 2. Answer Set Programming (ASP)
*Por qué*: especificación declarativa de espacio de diseño. SREG puede formalizar propiedades deseadas ("no ciclos", "al menos 2 paths entre X e Y") como programa ASP. Búsqueda automática exhaustiva.

### 3. Búsqueda evolutiva + multiobjetivo (NSGA-II, MAP-Elites)
*Por qué*: SREG necesita balancear (a) solvabilidad de GoldQuestion, (b) dificultad calibrada, (c) novedad respecto a preguntas previas, (d) rango de parámetros. Evolución multiobjetivo es natural.

### 4. Gramáticas generativas (L-Systems, shape grammars)
*Por qué*: compresión masiva. Un SCM de 100 variables puede describirse recursivamente en 10 líneas de gramática. Estructuras jerárquicas naturales (supuestos SCMs, submodelos).

### 5. Multi-Layer Procedural Synthesis (Dwarf Fortress pattern)
*Por qué*: separar generación en capas (topología → parámetros → simulación → análisis de trayectorias → derivación de tareas) reduce acoplamiento y permite iteración en cada capa.

## 7. Anti-Patterns y fracasos documentados

1. **Falta de validación early**: generar sin verificar solvability hasta el final es costoso. Spelunky verifica connectivity en tiempo real. Lección: validar restricciones críticas durante generación, no post-hoc.

2. **Exceso de aleatoriedad sin restricciones**: "el mundo es impredecible" ≠ "el mundo es bueno". Lección: *constraints encodean intent del diseño*.

3. **Stability & Physics**: GAN-generados niveles de Angry Birds a menudo tienen estructuras inestables. Lección: identificar propiedades que rompen validez (en SREG: ODEs que divergen, SCMs con ciclos no identificables) y enforcedas durante gen.

4. **Falta de métricas de calidad**: si no especificas función fitness, el algoritmo optimiza ruido. Yannakakis: *quality metrics deben ser data-driven*.

5. **Overfitting a ejemplos**: ML-based PCG (VAE, GAN) puede memorizar ejemplos. Lección: validar en holdout; usar regularización; combinar con búsqueda.

## 8. Síntesis: arquitectura sugerida para SREG Designer

```
1. GRAMMAR SYNTHESIS (L-Systems / Shape Grammars)
   Input: spec alto nivel (ej. "causal net, 50 vars")
   Output: SCM template (topología)
       ↓
2. CONSTRAINT-BASED COMPLETION (ASP / WFC)
   Input: template + restricciones (d-sep, no cycles)
   Output: SCM completo validado
       ↓
3. PARAMETER TUNING (Evolutionary Search)
   Input: SCM + objectives (dificultad, novedad)
   Output: parámetros ODE calibrados
       ↓
4. SIMULATION & ANALYSIS
   Input: ODE + parámetros
   Output: trayectorias, bifurcaciones, propiedades
       ↓
5. TASK DERIVATION (Retroactive Coherence)
   Input: análisis dinámico
   Output: GoldQuestions bien formadas, solvables
```

Cada capa aplica una técnica PCG distinta. Validación y constraint enforcement en cada paso.

## 9. Referencias clave

**Surveys & libros**:
- [Togelius, Yannakakis et al. 2011, "Search-Based PCG"](http://julian.togelius.com/Togelius2011Searchbased.pdf)
- [Shaker, Togelius & Nelson 2016, "PCG in Games"](https://www.pcgbook.com/)
- [Summerville et al. 2018, "PCG via Machine Learning"](https://arxiv.org/abs/1702.00539)
- [PCG Survey 2024 with LLM Integration](https://arxiv.org/html/2410.15644v1)

**Técnicas formales**:
- [Smith & Mateas 2011, "ASP for PCG"](https://adamsmith.as/papers/tciaig-asp4pcg.pdf)
- [Gumin, WFC GitHub](https://github.com/mxgmn/WaveFunctionCollapse)

**Estudios de caso**:
- [Derek Yu, "Spelunky" Boss Fight Books 2016](https://bossfightbooks.com/products/spelunky-by-derek-yu)
- [Caves of Qud GDC 2017](https://gdcvault.com/play/1024990/Procedurally-Generating-History-in-Caves)
- [No Man's Sky GDC](https://www.gdcvault.com/play/1024265/Continuous-World-Generation-in-No)
- [Diablo 1 Dungeon Generation](https://www.boristhebrave.com/2019/07/14/dungeon-generation-in-diablo-1/)

**Mixed-initiative & quality**:
- [Liapis et al. 2019 MAP-Elites](https://arxiv.org/abs/1906.05175)
- [Yannakakis Experience-Driven PCG](https://yannakakis.net/wp-content/uploads/2015/11/PID3821875.pdf)
- [Tracery (Kate Compton)](https://github.com/galaxykate/tracery)

**GDC**:
- [PCG Shotgun: 6 Techniques](https://gdcvault.com/play/1024146/PCG-Shotgun-6-Techniques-for)
- [Practical Procedural Generation](https://www.gdcvault.com/play/1024213/Practical-Procedural-Generation-for)
