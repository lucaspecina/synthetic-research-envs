---
name: eval
description: Evaluate world quality across multiple configurations and seeds. Use to measure if generated worlds produce good research problems.
disable-model-invocation: true
---

Evaluate world quality by generating multiple worlds and measuring key metrics.

## What to measure

For each world generated, compute:
- **WorldCheck**: pass/fail (DAG validity, entropy, d-separation, max parents, treewidth)
- **Teacher > prior**: does the teacher's posterior improve over the prior? (KL comparison)
- **Teacher > random**: does the teacher beat random observation strategy?
- **NBO non-trivial**: does the next-best-observation task have at least one node with IG > 0?
- **Hypotheses distinguishable**: is min KL between true posterior and nearest distractor > 0.05?

## How to run

1. Parse arguments: $ARGUMENTS may specify generators, node counts, seeds, or a specific config.
   Defaults: all 4 generators, seeds [1, 7, 42, 99, 123], edge_strength=0.7.

2. Generate worlds using `WorldGenTool().generate_custom()` with each config x seed combo.

3. For each world:
   - Run WorldCheckTool
   - Create ExactBayesSolver, sample state, compute teacher vs prior vs random KL
   - Generate TaskBundle, check NBO and hypothesis quality

4. Print results as a table:
   ```
   Config                 Seed Nodes Edges Check Teacher>Prior Teacher>Rand NBO Hyp
   erdos_renyi              42    10    12  PASS     Y             Y         Y   Y
   ...
   ```

5. Print summary with pass rates and compare against quality targets:
   - Teacher > prior: target >90%
   - Teacher > random: target >80%
   - NBO non-trivial: target >70%
   - Hypotheses distinguishable: target >80%

6. **Analyze**: Flag any surprising patterns (e.g., one generator consistently worse,
   large worlds failing more). Report findings that should go in WORLD_DESIGN.md.

## Key imports

```python
from sreg.world.dag_generators import (
    generate_erdos_renyi, generate_spanning_tree,
    generate_preferential_attachment, generate_layered,
)
from sreg.tools.world_gen import CustomWorldGenConfig, WorldGenTool
from sreg.tools.world_check import WorldCheckTool
from sreg.tools.task_gen import TaskGenTool
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.models.world import NodeType
```
