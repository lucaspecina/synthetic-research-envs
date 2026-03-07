"""Utilities for converting between SREG World models and pgmpy BayesianNetworks."""

from __future__ import annotations

from pgmpy.factors.discrete import TabularCPD
from pgmpy.models import DiscreteBayesianNetwork

from sreg.models.world import World


def world_to_pgmpy(world: World) -> DiscreteBayesianNetwork:
    """Convert a World to a pgmpy DiscreteBayesianNetwork with CPDs.

    The resulting model passes pgmpy's check_model() validation.
    """
    edges = [(e.from_node, e.to_node) for e in world.edges]
    model = DiscreteBayesianNetwork(edges)

    # Ensure isolated nodes are included
    for node in world.nodes:
        if node.name not in model.nodes():
            model.add_node(node.name)

    for cpd in world.cpds:
        pgmpy_cpd = TabularCPD(
            variable=cpd.node,
            variable_card=len(cpd.state_names[cpd.node]),
            values=cpd.table,
            evidence=cpd.parents if cpd.parents else None,
            evidence_card=([len(cpd.state_names[p]) for p in cpd.parents] if cpd.parents else None),
            state_names=cpd.state_names,
        )
        model.add_cpds(pgmpy_cpd)

    if not model.check_model():
        raise ValueError("pgmpy model validation failed")
    return model


__all__ = ["world_to_pgmpy"]
