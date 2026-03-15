"""DataSampler: sample from a Bayesian network and present as realistic data assets.

Supports single-dataset mode (backwards compatible) and multi-dataset mode
that generates multiple data assets with column splits, missing data, and
narrative observations — closer to what a real researcher would receive.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
from pydantic import BaseModel, Field

from sreg.models.research_problem import DataAsset
from sreg.models.world import NodeType, World
from sreg.solver.exact_bayes import ExactBayesSolver

# Templates for narrative observations
_NARRATIVE_TEMPLATES = [
    "Field observation: {facts}.",
    "According to station data, {facts}.",
    "A recent survey found that {facts}.",
    "Preliminary measurements indicate that {facts}.",
    "Monitoring records show that {facts}.",
]


class DataSamplerConfig(BaseModel):
    """Configuration for data sampling."""

    num_rows: int = Field(default=50, ge=1, le=10000)
    format: str = Field(
        default="tabular",
        description="'tabular', 'observations', or 'both'",
    )
    seed: int = Field(default=0)
    include_latent: bool = Field(
        default=False,
        description="Whether to include latent variables in the output (normally hidden)",
    )
    # Multi-dataset fields (v2)
    multi_dataset: bool = Field(
        default=False,
        description="Generate 2+ datasets with column splits",
    )
    missing_rate: float = Field(
        default=0.0, ge=0.0, le=0.5,
        description="Fraction of cells to blank out with 'not_measured'",
    )
    narrative_observations: int = Field(
        default=0, ge=0, le=10,
        description="Number of narrative text observations to generate",
    )
    secondary_rows: int | None = Field(
        default=None, ge=1,
        description="Rows in secondary dataset (defaults to num_rows // 3)",
    )
    hidden_columns: list[str] = Field(
        default_factory=list,
        description=(
            "Observable columns to HIDE from the initial dataset. "
            "These variables exist in the world but are not included in "
            "the CSV. The agent must use research_action(observe) to reveal them."
        ),
    )
    # Measurement realism (v2)
    measurement_noise: float = Field(
        default=0.0, ge=0.0, le=0.5,
        description=(
            "Probability of misclassifying a discrete state to an adjacent "
            "state. Simulates measurement error. 0.0 = perfect measurement, "
            "0.1 = 10% chance of adjacent-state flip. Applied to ordinal "
            "variables only (not target, not latent, not nominal)."
        ),
    )
    missing_mechanism: str = Field(
        default="mcar",
        description=(
            "'mcar' = missing completely at random (current behavior). "
            "'mar' = missing depends on observed parent variables. "
            "More realistic: sicker patients more likely to have missing follow-up."
        ),
    )


def _is_ordinal(states: list[str]) -> bool:
    """Heuristic: a variable is ordinal if states suggest an order."""
    ordinal_markers = {
        "low", "medium", "high", "very_low", "very_high",
        "none", "mild", "moderate", "severe",
        "weak", "strong",
        "short", "long",
        "small", "large",
        "few", "many",
        "poor", "good", "excellent",
        "preterm", "early_term", "full_term",
        "shallow", "deep",
        "young", "middle", "advanced",
        "close", "far",
        "dry", "wet",
        "thin", "thick",
        "absent", "present",
    }
    return any(s.lower() in ordinal_markers for s in states)


def _apply_measurement_noise(
    rows: list[dict],
    world_nodes: list,
    noise_rate: float,
    rng,
) -> list[dict]:
    """Apply misclassification noise to ordinal variables.

    For ordinal variables, flips the state to an adjacent one with
    probability noise_rate. Does NOT apply to target or latent nodes.
    """
    if noise_rate <= 0:
        return rows

    # Build state info for each ordinal observable
    ordinal_info: dict[str, list[str]] = {}
    for node in world_nodes:
        if node.type.value in ("latent", "target"):
            continue
        if _is_ordinal(node.states):
            ordinal_info[node.name] = list(node.states)

    for row in rows:
        for col, states in ordinal_info.items():
            if col not in row or row[col] == "not_measured":
                continue
            if rng.random() < noise_rate:
                current = row[col]
                if current in states:
                    idx = states.index(current)
                    # Flip to adjacent state
                    if idx == 0:
                        row[col] = states[1]
                    elif idx == len(states) - 1:
                        row[col] = states[-2]
                    else:
                        row[col] = states[idx + 1] if rng.random() < 0.5 else states[idx - 1]

    return rows


def _apply_mar_missingness(
    rows: list[dict],
    world_nodes: list,
    world_edges: list,
    missing_rate: float,
    rng,
) -> list[dict]:
    """Apply MAR missingness: probability of missing depends on parent values.

    Variables with parents that have "extreme" states (first or last state)
    are more likely to be missing. This creates realistic bias: sicker patients
    drop out more, extreme values are harder to measure.
    """
    if missing_rate <= 0:
        return rows

    # Build parent map
    parent_map: dict[str, list[str]] = {}
    for edge in world_edges:
        parent = edge.from_node if hasattr(edge, "from_node") else edge[0]
        child = edge.to_node if hasattr(edge, "to_node") else edge[1]
        parent_map.setdefault(child, []).append(parent)

    # Node state info
    node_states = {n.name: list(n.states) for n in world_nodes}
    target_names = {n.name for n in world_nodes if n.type.value == "target"}

    for row in rows:
        for col in list(row.keys()):
            if col in ("sample_id",) or col in target_names:
                continue
            if row[col] == "not_measured":
                continue

            # Base missing rate, increased if parents have extreme values
            p_missing = missing_rate
            parents = parent_map.get(col, [])
            for parent in parents:
                if parent in row and parent in node_states:
                    p_states = node_states[parent]
                    val = row[parent]
                    if val in p_states:
                        idx = p_states.index(val)
                        # Extreme states (first/last) increase missing probability
                        if idx == 0 or idx == len(p_states) - 1:
                            p_missing *= 2.0

            p_missing = min(p_missing, 0.5)  # Cap at 50%

            if rng.random() < p_missing:
                row[col] = "not_measured"

    return rows


class DataSampler:
    """Sample data from a world's Bayesian network and format as DataAssets."""

    def sample(self, world: World, config: DataSamplerConfig) -> list[DataAsset]:
        """Generate data assets by sampling from the world's joint distribution."""
        solver = ExactBayesSolver(world)
        assets: list[DataAsset] = []

        visible_nodes = [
            n for n in world.nodes
            if n.type != NodeType.LATENT or config.include_latent
        ]
        hidden_set = set(config.hidden_columns)
        visible_names = [n.name for n in visible_nodes if n.name not in hidden_set]

        if config.multi_dataset and len(visible_names) >= 4:
            assets.extend(
                self._multi_dataset(world, solver, visible_names, config)
            )
        else:
            # Original single-dataset behavior
            if config.format in ("tabular", "both"):
                assets.append(self._tabular(world, solver, visible_names, config))
            if config.format in ("observations", "both"):
                assets.append(self._observations(world, solver, visible_names, config))

        # Narrative observations (works in both modes)
        if config.narrative_observations > 0:
            assets.append(
                self._narrative(world, solver, visible_names, config)
            )

        return assets

    # ------------------------------------------------------------------
    # Multi-dataset mode
    # ------------------------------------------------------------------

    def _multi_dataset(
        self,
        world: World,
        solver: ExactBayesSolver,
        visible_names: list[str],
        config: DataSamplerConfig,
    ) -> list[DataAsset]:
        """Generate primary + secondary datasets with column splits."""
        primary_cols, secondary_cols = self._split_columns(world, visible_names)

        # Primary dataset: all rows
        primary = self._tabular_subset(
            world, solver, primary_cols, config.num_rows, config.seed,
            name_suffix="primary", source="main study",
        )

        # Secondary dataset: fewer rows, different seed
        sec_rows = config.secondary_rows or max(5, config.num_rows // 3)
        secondary = self._tabular_subset(
            world, solver, secondary_cols, sec_rows, config.seed + 10000,
            name_suffix="supplementary", source="supplementary source",
        )

        assets = [primary, secondary]

        # Inject missing data
        if config.missing_rate > 0:
            rng = np.random.default_rng(config.seed + 20000)
            self._inject_missing(primary, config.missing_rate, rng)
            # Secondary has slightly higher missing rate
            sec_rate = min(config.missing_rate * 1.5, 0.3)
            self._inject_missing(secondary, sec_rate, rng)

        return assets

    def _split_columns(
        self, world: World, visible_names: list[str],
    ) -> tuple[list[str], list[str]]:
        """Split visible columns into primary and secondary by DAG proximity to target."""
        # Build undirected graph for distance computation
        dag = nx.DiGraph()
        for node in world.nodes:
            dag.add_node(node.name)
        for edge in world.edges:
            dag.add_edge(edge.from_node, edge.to_node)
        undirected = dag.to_undirected()

        target_nodes = [n for n in world.nodes if n.type == NodeType.TARGET]
        target_name = target_nodes[0].name if target_nodes else visible_names[-1]

        # Compute distances from target
        distances: dict[str, int] = {}
        for name in visible_names:
            try:
                d = nx.shortest_path_length(undirected, name, target_name)
            except nx.NetworkXNoPath:
                d = 999
            distances[name] = d

        # Sort by distance to target
        sorted_names = sorted(visible_names, key=lambda n: distances[n])

        # Split: closer half → primary, farther half → secondary
        mid = max(2, len(sorted_names) // 2)
        primary = sorted_names[:mid]
        secondary = sorted_names[mid:]

        # Ensure target is in primary
        if target_name in secondary:
            secondary.remove(target_name)
            if target_name not in primary:
                primary.append(target_name)

        # Ensure secondary has at least 2 columns
        if len(secondary) < 2 and len(primary) > 3:
            secondary.insert(0, primary.pop())

        # Add 1 overlap node: closest secondary node also in primary
        if secondary and secondary[0] not in primary:
            primary.append(secondary[0])

        return primary, secondary

    def _tabular_subset(
        self,
        world: World,
        solver: ExactBayesSolver,
        columns: list[str],
        num_rows: int,
        seed: int,
        name_suffix: str,
        source: str,
    ) -> DataAsset:
        """Sample N rows with a subset of columns."""
        rows: list[dict[str, str | float]] = []
        for i in range(num_rows):
            state = solver.sample_state(seed=seed + i)
            row: dict[str, str | float] = {"sample_id": i + 1}
            for name in columns:
                row[name] = state[name]
            rows.append(row)

        title = world.scenario_title or world.domain or "research"
        slug = title.lower().replace(" ", "_").replace("-", "_")[:40]
        return DataAsset(
            name=f"{slug}_{name_suffix}",
            description=(
                f"Dataset with {num_rows} samples. "
                f"Columns: {', '.join(columns)}."
            ),
            format="tabular",
            data=rows,
            source=source,
            columns=list(columns),
            num_rows=num_rows,
        )

    def _inject_missing(
        self,
        asset: DataAsset,
        rate: float,
        rng: np.random.Generator,
    ) -> None:
        """Replace a fraction of cell values with 'not_measured' in-place."""
        for row in asset.data:
            data_keys = [k for k in row if k != "sample_id"]
            # Save originals before blanking
            originals = {k: row[k] for k in data_keys}
            for key in data_keys:
                if rng.random() < rate:
                    row[key] = "not_measured"
            # Ensure at least 2 real data columns remain per row
            real_keys = [k for k in data_keys if row[k] != "not_measured"]
            if len(real_keys) < 2:
                blanked = [k for k in data_keys if row[k] == "not_measured"]
                rng.shuffle(blanked)
                needed = 2 - len(real_keys)
                for k in blanked[:needed]:
                    row[k] = originals[k]

    # ------------------------------------------------------------------
    # Narrative observations
    # ------------------------------------------------------------------

    def _narrative(
        self,
        world: World,
        solver: ExactBayesSolver,
        visible_names: list[str],
        config: DataSamplerConfig,
    ) -> DataAsset:
        """Generate N narrative observations as natural-language text."""
        rng = np.random.default_rng(config.seed + 30000)
        observations: list[dict[str, str | float]] = []
        non_target = [
            n for n in visible_names
            if not any(nd.name == n and nd.type == NodeType.TARGET for nd in world.nodes)
        ]

        for i in range(config.narrative_observations):
            state = solver.sample_state(seed=config.seed + 50000 + i)

            # Pick 2-3 random visible nodes for this observation
            n_vars = min(rng.integers(2, 4), len(non_target))
            chosen = list(rng.choice(non_target, size=n_vars, replace=False))

            # Include target in ~30% of narratives
            target_nodes = [n for n in world.nodes if n.type == NodeType.TARGET]
            if target_nodes and rng.random() < 0.3:
                chosen.append(target_nodes[0].name)

            # Build facts string
            facts_parts = []
            for name in chosen:
                node = next(n for n in world.nodes if n.name == name)
                label = node.description or name.replace("_", " ")
                facts_parts.append(f"{label} was {state[name]}")
            facts = " and ".join(facts_parts)

            template = _NARRATIVE_TEMPLATES[i % len(_NARRATIVE_TEMPLATES)]
            text = template.format(facts=facts)

            observations.append({
                "observation": text,
                "source": f"field_report_{i + 1}",
            })

        return DataAsset(
            name="field_notes",
            description=f"{len(observations)} narrative observations from field work.",
            format="narrative",
            data=observations,
            source="field reports",
            num_rows=len(observations),
        )

    # ------------------------------------------------------------------
    # Original single-dataset methods (unchanged for backwards compat)
    # ------------------------------------------------------------------

    def _tabular(
        self,
        world: World,
        solver: ExactBayesSolver,
        visible_names: list[str],
        config: DataSamplerConfig,
    ) -> DataAsset:
        """Sample N rows as a tabular dataset."""
        rows: list[dict[str, str | float]] = []

        for i in range(config.num_rows):
            state = solver.sample_state(seed=config.seed + i)
            row: dict[str, str | float] = {"sample_id": i + 1}
            for name in visible_names:
                row[name] = state[name]
            rows.append(row)

        # Apply measurement noise (misclassification)
        if config.measurement_noise > 0:
            import numpy as _np
            noise_rng = _np.random.default_rng(config.seed + 99999)
            rows = _apply_measurement_noise(rows, world.nodes, config.measurement_noise, noise_rng)

        # Apply missingness
        if config.missing_rate > 0:
            import numpy as _np
            miss_rng = _np.random.default_rng(config.seed + 88888)
            if config.missing_mechanism == "mar":
                rows = _apply_mar_missingness(
                    rows, world.nodes, world.edges, config.missing_rate, miss_rng
                )
            else:
                # MCAR fallback (original behavior)
                for row in rows:
                    for col in list(row.keys()):
                        if col == "sample_id":
                            continue
                        if miss_rng.random() < config.missing_rate:
                            row[col] = "not_measured"

        # Build description with data quality notes
        title = world.scenario_title or world.domain or "research"
        slug = title.lower().replace(" ", "_").replace("-", "_")[:40]

        quality_notes = []
        if config.measurement_noise > 0:
            quality_notes.append(
                f"Measurement error: ~{config.measurement_noise:.0%} misclassification rate"
            )
        if config.missing_rate > 0:
            mechanism = "correlated with variable severity" if config.missing_mechanism == "mar" else "random"
            quality_notes.append(
                f"Missing data: ~{config.missing_rate:.0%} ({mechanism})"
            )
        quality_str = ". ".join(quality_notes)

        desc = (
            f"Dataset with {config.num_rows} samples. "
            f"Columns: {', '.join(visible_names)}."
        )
        if quality_str:
            desc += f" Data quality notes: {quality_str}."

        return DataAsset(
            name=f"{slug}_data",
            description=desc,
            format="tabular",
            data=rows,
        )

    def _observations(
        self,
        world: World,
        solver: ExactBayesSolver,
        visible_names: list[str],
        config: DataSamplerConfig,
    ) -> DataAsset:
        """Sample a few observations as isolated datapoints."""
        observations: list[dict[str, str | float]] = []
        num_obs = min(5, config.num_rows)

        for i in range(num_obs):
            state = solver.sample_state(seed=config.seed + i)
            for name in visible_names:
                node = next(n for n in world.nodes if n.name == name)
                if node.type == NodeType.TARGET:
                    continue
                desc = node.description or name
                observations.append({
                    "observation": f"{desc}: {state[name]}",
                    "variable": name,
                    "value": state[name],
                    "sample": i + 1,
                })

        return DataAsset(
            name="field_observations",
            description=f"{len(observations)} individual field observations.",
            format="observations",
            data=observations,
        )


__all__ = ["DataSampler", "DataSamplerConfig"]
