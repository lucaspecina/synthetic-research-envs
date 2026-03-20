"""Solver: teacher inference engines for BN and SCM worlds."""

from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.solver.scm_solver import SCMSolver

__all__ = ["ExactBayesSolver", "SCMSolver"]
