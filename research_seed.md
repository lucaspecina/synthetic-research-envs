# Research Seed

> Write your research case context here. The orchestrator will read this file
> and use it as the basis for generating a synthetic research case.
>
> You can describe: a phenomenon, a domain, variables of interest, hypotheses,
> the kind of questions you want, constraints, difficulty, or even paste an
> abstract from a real paper as inspiration.
>
> Usage:
>   python scripts/test_orchestrator.py                  # reads this file automatically
>   python scripts/test_orchestrator.py --goal "..."     # ignores this file (explicit goal wins)
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
