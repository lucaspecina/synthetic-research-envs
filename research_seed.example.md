# Research Seed

> Write your research case context here. The orchestrator will read
> `research_seed.md` and use it as the basis for generating a synthetic
> research case. Copy this file to `research_seed.md` and edit it.
>
> Lines starting with > are stripped (treated as comments).
>
> Usage:
>   python scripts/test_orchestrator.py                    # reads research_seed.md
>   python scripts/test_orchestrator.py --goal "..."       # ignores seed file
>   python scripts/test_orchestrator.py --seed-file other.md  # reads a different file

## Context

Tropical disease outbreak in a fictional island chain. A research team is
investigating why some islands have higher mortality rates than others.

## Variables of interest

- mosquito density, rainfall, standing water, sanitation infrastructure
- population density, healthcare access, prior immunity
- a latent variable: an unobserved genetic resistance factor

## Research questions

- What drives mortality differences between islands?
- If we could intervene on sanitation, what would happen to mortality?
- What should we measure next given our current data?

## Constraints

- 10 nodes, medium-high difficulty
- Use dag_construct
- At least 4 different evaluation types
- The case should feel like a real epidemiological field study
