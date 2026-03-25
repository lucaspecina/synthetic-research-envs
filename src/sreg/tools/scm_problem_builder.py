"""SCMProblemBuilder: package an SCMWorld + data into a ResearchProblem.

Mirrors ProblemBuilder but works with SCMWorld (continuous variables,
structural equations) instead of discrete BN World.

Uses scm_data.realistic_sample() for data generation — no dependency on
pgmpy or discrete DataSampler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sreg.models.research_problem import AvailableAction, DataAsset, ResearchProblem
from sreg.tools.scm_task_gen import SCMTaskGenTool
from sreg.world.scm import SCMWorld
from sreg.world.scm_data import (
    PanelConfig,
    RealisticDataConfig,
    multi_dataset_sample,
    realistic_sample,
)

if TYPE_CHECKING:
    from sreg.models.case_plan import CasePlan
    from sreg.models.task import Task


class SCMProblemBuilder:
    """Build a ResearchProblem from a semantically enriched SCMWorld."""

    def build(
        self,
        world: SCMWorld,
        tasks: list[Task] | None = None,
        target: str | None = None,
        budget: int = 5,
        n_rows: int = 500,
        multi_dataset: bool = False,
        case_plan: CasePlan | None = None,
        seed: int = 0,
        title: str | None = None,
        description: str | None = None,
        domain: str | None = None,
        panel: PanelConfig | None = None,
    ) -> ResearchProblem:
        """Package an SCMWorld into a ResearchProblem the agent can see.

        Args:
            world: An SCMWorld with equations and graph.
            tasks: Generated tasks (used to extract target and bin ranges).
            target: Target variable name. Inferred from tasks or last in topo order.
            budget: Observation budget for the agent.
            n_rows: Number of data rows in the primary dataset.
            multi_dataset: If True, generate multiple datasets with varied quality.
            case_plan: If provided, use the primary question text.
            seed: Random seed for data generation.
            title: Scenario title (from orchestrator semantics).
            description: Scenario description (from orchestrator semantics).
            domain: Scientific domain (from orchestrator semantics).
        """
        # Determine target variable
        if target is None and tasks:
            target = tasks[0].target_node
        if target is None:
            target = world.variables[-1]

        # Generate data
        data_assets = self._build_data(
            world, target, n_rows, multi_dataset, seed, panel
        )

        # Build actions from observable variables
        actions = self._build_actions(world, target)

        # Build target states (bin ranges from the first distribution task, or generic)
        target_states = self._build_target_states(world, tasks, target, seed)

        # Build research question
        question = self._build_question(world, target, target_states, case_plan)

        return ResearchProblem(
            world_id=world.id or "scm_world",
            title=title or f"Research problem: {world.id or 'SCM'}",
            description=description or self._build_description(world, target),
            domain=domain or "continuous_scm",
            data_assets=data_assets,
            available_actions=actions,
            budget=budget,
            research_question=question,
            target_node=target,
            target_states=target_states,
        )

    def _build_data(
        self,
        world: SCMWorld,
        target: str,
        n_rows: int,
        multi_dataset: bool,
        seed: int,
        panel: PanelConfig | None = None,
    ) -> list[DataAsset]:
        """Generate data assets from SCMWorld."""
        obs_vars = world.observable_variables
        # Structural + proxy columns that should be kept alongside obs vars
        _STRUCTURAL = {"sample_id", "site_id", "wave"}

        if multi_dataset:
            config = RealisticDataConfig(seed=seed)
            artifacts = multi_dataset_sample(
                world, config=config, target=target, n=n_rows, panel=panel,
            )
            assets = []
            for art in artifacts:
                # Keep obs variables + structural + proxy columns
                keep = [
                    c for c in art.data.columns
                    if c in obs_vars or c in _STRUCTURAL
                    or c not in world.variables  # proxy columns
                ]
                df_obs = art.data[keep]
                rows = df_obs.to_dict(orient="records")
                cols = [c for c in df_obs.columns if c not in _STRUCTURAL]
                desc = self._describe_dataset(df_obs, cols)
                assets.append(
                    DataAsset(
                        name=art.name,
                        description=art.description,
                        format="tabular",
                        data=rows,
                        source=art.source,
                        columns=cols,
                        num_rows=len(rows),
                    )
                )
            return assets

        # Single dataset mode
        df = realistic_sample(world, n=n_rows, target=target, seed=seed)

        # Filter to observable variables only
        keep_cols = [c for c in df.columns if c in obs_vars]
        df = df[keep_cols]
        df.insert(0, "sample_id", range(1, len(df) + 1))

        rows = df.to_dict(orient="records")
        return [
            DataAsset(
                name="research_data",
                description=f"Dataset with {n_rows} samples. "
                f"Columns: {', '.join(keep_cols)}.",
                format="tabular",
                data=rows,
                source="observational study",
                columns=keep_cols,
                num_rows=n_rows,
            )
        ]

    def _build_actions(
        self, world: SCMWorld, target: str
    ) -> list[AvailableAction]:
        """Create observe actions from observable variables."""
        actions: list[AvailableAction] = []
        for var in world.observable_variables:
            if var == target:
                continue
            label = var.replace("_", " ")
            actions.append(
                AvailableAction(
                    id=f"measure_{var}",
                    node=var,
                    description=f"Measure {label}",
                    cost=1,
                )
            )
        return actions

    def _build_target_states(
        self,
        world: SCMWorld,
        tasks: list[Task] | None,
        target: str,
        seed: int,
    ) -> list[str]:
        """Extract target states (bin ranges) for the agent prompt.

        Uses the first distribution task's correct_answer keys if available,
        otherwise computes bin ranges from scratch.
        """
        if tasks:
            for task in tasks:
                if task.correct_answer and task.target_node == target:
                    keys = list(task.correct_answer.keys())
                    # Check if keys look like bin ranges (not node names or yes/no)
                    if keys and keys[0].startswith("["):
                        return keys

        # Fallback: compute bins
        bin_edges = SCMTaskGenTool._compute_bin_edges(world, target, seed=seed)
        labels = []
        for i in range(len(bin_edges) - 1):
            labels.append(f"[{bin_edges[i]:.2f}, {bin_edges[i + 1]:.2f})")
        return labels

    def _build_question(
        self,
        world: SCMWorld,
        target: str,
        target_states: list[str],
        case_plan: CasePlan | None,
    ) -> str:
        """Build the research question visible to the investigator.

        Priority:
        1. If case_plan has a research_brief, use it (+ deliverables).
        2. Else fall back to questions[0].question_text (legacy).
        3. Else generate a generic question from the world.
        """
        states_str = ", ".join(target_states)

        # Use research brief when available (Fase 5: brief/eval separation)
        if case_plan and case_plan.research_brief:
            parts = [case_plan.research_brief]
            if case_plan.deliverables:
                parts.append("\nDeliverables:")
                for d in case_plan.deliverables:
                    parts.append(f"- {d}")
            return "\n".join(parts)

        # Legacy fallback: use first question's text
        meta = world.variable_meta.get(target)
        target_label = target.replace("_", " ")
        if meta and meta.description:
            desc = meta.description.rstrip(".")
            if len(desc) < 45 and len(desc.split()) <= 6:
                target_label = desc

        if case_plan and case_plan.questions:
            primary = case_plan.questions[0]
            return (
                f"{primary.question_text}\n\n"
                f"Target variable: {target_label} "
                f"(ranges: {states_str}). "
                f"Analyze the data to estimate the distribution."
            )

        unit_str = f" ({meta.unit})" if meta and meta.unit else ""
        return (
            f"Based on the available data, estimate the probability distribution "
            f"over {target_label}{unit_str} across these ranges: {states_str}. "
            f"Analyze the data to refine your estimate."
        )

    @staticmethod
    def _describe_dataset(df, cols: list[str]) -> str:
        """Generate a description from the filtered DataFrame."""
        n_rows = len(df)
        total_cells = n_rows * len(cols)
        missing_cells = df[cols].isna().sum().sum() if cols else 0
        missing_pct = (missing_cells / total_cells * 100) if total_cells > 0 else 0

        desc = f"Dataset with {n_rows} samples. Columns: {', '.join(cols)}."
        if missing_pct > 1:
            desc += f" Missing data: {missing_pct:.0f}%."
        return desc

    def _build_description(self, world: SCMWorld, target: str) -> str:
        """Build a narrative description from variable metadata."""
        obs_vars = world.observable_variables
        target_label = target.replace("_", " ")
        meta_t = world.variable_meta.get(target)
        if meta_t and meta_t.description:
            desc_t = meta_t.description.rstrip(".")
            if len(desc_t) < 45 and len(desc_t.split()) <= 6:
                target_label = desc_t
        parts = [f"Investigate the factors affecting {target_label}."]

        described = []
        for var in obs_vars:
            meta = world.variable_meta.get(var)
            if meta and meta.description:
                label = var.replace("_", " ")
                described.append(f"{label}: {meta.description}")

        if described:
            parts.append("Available measurements include: " + "; ".join(described) + ".")
        else:
            parts.append(f"You have access to {len(obs_vars)} measured variables.")

        return " ".join(parts)


__all__ = ["SCMProblemBuilder"]
