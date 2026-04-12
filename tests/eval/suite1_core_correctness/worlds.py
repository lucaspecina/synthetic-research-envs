"""Suite 1 Core Correctness — Hand-crafted SCM worlds with analytical ground truth.

Each world has:
- Simple, linear-Gaussian equations (closed-form expectations)
- Documented analytical derivations for key quantities
- A unique structural property needed by specific test cases

These worlds are the FOUNDATION of Suite 1. Every expected value in the
registry is derived from the equations below — not from running the code.
"""

from __future__ import annotations

import numpy as np

from sreg.world.scm import SCMWorld


# ---------------------------------------------------------------------------
# World 1: LINEAR CHAIN  (A -> B -> C)
# ---------------------------------------------------------------------------
#
# Equations:
#   A ~ N(0, 1)
#   B = 0.5*A + eps_B,   eps_B ~ N(0, 0.3)
#   C = 0.8*B + eps_C,   eps_C ~ N(0, 0.2)
#
# Analytical ground truth:
#   E[B | do(A=a)]           = 0.5 * a
#   Var[B | do(A=a)]         = 0.09
#   E[C | do(A=a)]           = 0.8 * 0.5 * a = 0.4 * a
#   Var[C | do(A=a)]         = 0.8^2 * 0.09 + 0.04 = 0.0976
#   E[C | do(B=b)]           = 0.8 * b
#   ATE(A->C, a=1 vs a=-1)  = 0.4 - (-0.4) = 0.8
#   ATE(A->B, a=1 vs a=-1)  = 0.5 - (-0.5) = 1.0
#   E[B | do(A=0)]           = 0.0
#   E[C | do(A=0)]           = 0.0
#   Var[C | baseline]        = 0.8^2 * (0.25 + 0.09) + 0.04
#                            = 0.64 * 0.34 + 0.04 = 0.2576 + 0.04 ≈ 0.2576
#     (Var[B|baseline] = 0.25*1 + 0.09 = 0.34)
#
#   Mediation: A->B->C is the ONLY path (no direct A->C edge).
#     Total effect = indirect effect = 0.4*a. Direct effect = 0.
#
#   Identifiability: A is a root, so do(A) = condition on A. Always identifiable.
#   Backdoor adjustment for A->C: no confounders, empty set is valid.


def linear_chain() -> SCMWorld:
    return SCMWorld(
        id="suite1-linear-chain",
        graph={"A": [], "B": ["A"], "C": ["B"]},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "B": lambda p, rng: 0.5 * p["A"] + rng.normal(0, 0.3),
            "C": lambda p, rng: 0.8 * p["B"] + rng.normal(0, 0.2),
        },
    )


# ---------------------------------------------------------------------------
# World 2: CONFOUNDER  (Z -> A, Z -> Y, A -> Y)
# ---------------------------------------------------------------------------
#
# Equations:
#   Z ~ N(0, 1)
#   A = 0.5*Z + eps_A,   eps_A ~ N(0, 0.4)
#   Y = 0.3*A + 0.7*Z + eps_Y,   eps_Y ~ N(0, 0.3)
#
# Analytical ground truth:
#   Causal effect A->Y (true, via do-calculus):
#     E[Y | do(A=a)] = integral over Z of E[Y | A=a, Z=z] * P(Z=z) dz
#                    = 0.3*a + 0.7 * E[Z] = 0.3*a
#     ATE(do(A=1) vs do(A=-1)) = 0.6
#
#   Observational (confounded):
#     E[Y | A=a] = 0.3*a + 0.7 * E[Z|A=a]
#     E[Z|A=a]: from A = 0.5*Z + eps_A, by regression of Z on A:
#       Cov(Z,A) = 0.5*Var(Z) = 0.5
#       Var(A) = 0.25 + 0.16 = 0.41
#       E[Z|A=a] = (0.5/0.41) * a ≈ 1.2195 * a
#     E[Y|A=a] ≈ 0.3*a + 0.7*1.2195*a ≈ 1.154*a
#     Obs ATE(A=1 vs A=-1) ≈ 2.308 (biased!)
#
#   Partial correlation corr(A, Y | Z):
#     Direct effect A->Y = 0.3, so partial corr > 0.
#
#   Identifiability: Z is observable parent of A, valid backdoor set = {Z}.
#
#   Correlation(A, Y | baseline):
#     Both A and Y are driven by Z, plus direct A->Y.
#     corr(A,Y) > 0 (substantial, due to confounding + direct).
#
#   Var[Y | do(A=a)] = 0.7^2 * Var(Z) + Var(eps_Y) = 0.49 + 0.09 = 0.58


def confounder() -> SCMWorld:
    return SCMWorld(
        id="suite1-confounder",
        graph={"Z": [], "A": ["Z"], "Y": ["A", "Z"]},
        equations={
            "Z": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: 0.5 * p["Z"] + rng.normal(0, 0.4),
            "Y": lambda p, rng: 0.3 * p["A"] + 0.7 * p["Z"] + rng.normal(0, 0.3),
        },
    )


# ---------------------------------------------------------------------------
# World 3: LATENT CONFOUNDER  (U -> A, U -> Y, A -> Y; U is latent)
# ---------------------------------------------------------------------------
#
# Equations:
#   U ~ N(0, 1)         (LATENT — not observable)
#   A = 1.0*U + eps_A,  eps_A ~ N(0, 0.4)
#   Y = 0.5*A + 0.6*U + eps_Y,  eps_Y ~ N(0, 0.3)
#
# Analytical ground truth:
#   True causal effect A->Y = 0.5
#     E[Y | do(A=a)] = 0.5*a + 0.6*E[U] = 0.5*a
#     ATE(do(A=1) vs do(A=-1)) = 1.0
#
#   BUT: from observables alone, the effect of A on Y is NOT identifiable
#   because U confounds A->Y and U is latent. No valid backdoor set exists
#   (U is the only potential adjustment variable and it's unobservable).
#
#   candidate_adjust_set=("U",) should be rejected: U is latent.
#   candidate_adjust_set=() (empty set) is NOT valid either because
#   there IS a backdoor path A <- U -> Y that needs blocking.


def latent_confounder() -> SCMWorld:
    return SCMWorld(
        id="suite1-latent-confounder",
        graph={"U": [], "A": ["U"], "Y": ["A", "U"]},
        equations={
            "U": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: 1.0 * p["U"] + rng.normal(0, 0.4),
            "Y": lambda p, rng: 0.5 * p["A"] + 0.6 * p["U"] + rng.normal(0, 0.3),
        },
        latent_variables={"U"},
    )


# ---------------------------------------------------------------------------
# World 4: THRESHOLD  (A -> Y with changepoint at A = 0.5)
# ---------------------------------------------------------------------------
#
# Equations:
#   A ~ U(0, 1)
#   Y = { N(0, 0.05)             if A <= 0.5
#       { 2*(A - 0.5) + N(0, 0.05)  if A > 0.5
#
# Analytical ground truth:
#   For A <= 0.5: E[Y | do(A=a)] = 0
#   For A > 0.5: E[Y | do(A=a)] = 2*(a - 0.5)
#   Changepoint at A = 0.5.
#
#   Sweep from 0.1 to 0.9:
#     E[Y|do(A=0.1)] = 0, E[Y|do(A=0.3)] = 0, E[Y|do(A=0.5)] ≈ 0
#     E[Y|do(A=0.6)] = 0.2, E[Y|do(A=0.8)] = 0.6, E[Y|do(A=0.9)] = 0.8
#
#   E[Y | do(A=0.8)] > 0  (POSITIVE assertion)
#   E[Y | do(A=0.2)] ≈ 0  (NEAR_ZERO assertion)


def threshold() -> SCMWorld:
    return SCMWorld(
        id="suite1-threshold",
        graph={"A": [], "Y": ["A"]},
        equations={
            "A": lambda p, rng: rng.uniform(0, 1),
            "Y": lambda p, rng: (
                2.0 * (p["A"] - 0.5) + rng.normal(0, 0.05)
                if p["A"] > 0.5
                else rng.normal(0, 0.05)
            ),
        },
    )


# ---------------------------------------------------------------------------
# World 5: INDEPENDENCE  (A and Y are independent)
# ---------------------------------------------------------------------------
#
# Equations:
#   A ~ N(0, 1)
#   Y ~ N(3, 0.5)    (mean=3 so we can test GREATER_THAN on baseline)
#
# Analytical ground truth:
#   E[Y | do(A=a)] = 3.0 for any a (A has no effect on Y)
#   ATE(do(A=1) vs do(A=-1)) = 0.0
#   Corr(A, Y) = 0.0
#   Var(Y) = 0.25
#   E[Y | baseline] = 3.0
#
#   Identifiability: A is root, no confounders. do(A) = trivially identifiable.
#   But the effect IS zero, so "distinguishable" between do(A=1) and do(A=-1)
#   should be FALSE (not distinguishable — same distribution).


def independence() -> SCMWorld:
    return SCMWorld(
        id="suite1-independence",
        graph={"A": [], "Y": []},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "Y": lambda p, rng: rng.normal(3.0, 0.5),
        },
    )


# ---------------------------------------------------------------------------
# World 6: MEDIATION  (X -> M -> Y, X -> Y)
# ---------------------------------------------------------------------------
#
# Equations:
#   X ~ N(0, 1)
#   M = 0.7*X + eps_M,  eps_M ~ N(0, 0.3)
#   Y = 0.3*X + 0.6*M + eps_Y,  eps_Y ~ N(0, 0.3)
#
# Analytical ground truth:
#   Total effect X->Y:
#     E[Y | do(X=x)] = 0.3*x + 0.6*(0.7*x) = 0.3*x + 0.42*x = 0.72*x
#     ATE(do(X=1) vs do(X=-1)) = 1.44
#
#   Direct effect (fixing M at reference value m_ref = E[M|do(X=-1)] = -0.7):
#     E[Y | do(X=x, M=m_ref)] = 0.3*x + 0.6*m_ref
#     Direct ATE = 0.3*1 + 0.6*(-0.7) - (0.3*(-1) + 0.6*(-0.7))
#               = (0.3 - 0.42) - (-0.3 - 0.42) = -0.12 - (-0.72) = 0.6
#
#   Indirect effect (natural indirect = total - direct):
#     Indirect = 1.44 - 0.6 = 0.84
#     (Or: via contrast_diff, the sign_flip/indirect decomposition)
#
#   For CONTRAST_DIFF (4 arms: total_hi, total_lo, direct_hi, direct_lo):
#     contrast_diff = (total_hi - total_lo) - (direct_hi - direct_lo)
#     = ATE_total - ATE_direct = 1.44 - 0.6 = 0.84 > 0  (positive indirect)
#
#   RANKING of effects across arms:
#     E[Y|do(X=1)] = 0.72, E[Y|do(X=0)] = 0, E[Y|do(X=-1)] = -0.72
#     Ranking by mean(Y): X=1 > X=0 > X=-1
#
#   Var[Y | do(X=x)] = 0.6^2 * 0.09 + 0.09 = 0.0324 + 0.09 = 0.1224
#
#   Correlation(X, Y | baseline): positive (X drives Y through two paths).
#   Partial corr(X, Y | M): direct path remains, so still positive = 0.3 effect.


def mediation() -> SCMWorld:
    return SCMWorld(
        id="suite1-mediation",
        graph={"X": [], "M": ["X"], "Y": ["X", "M"]},
        equations={
            "X": lambda p, rng: rng.normal(0, 1),
            "M": lambda p, rng: 0.7 * p["X"] + rng.normal(0, 0.3),
            "Y": lambda p, rng: 0.3 * p["X"] + 0.6 * p["M"] + rng.normal(0, 0.3),
        },
    )


# ---------------------------------------------------------------------------
# World registry — central access point for all worlds
# ---------------------------------------------------------------------------

ALL_WORLDS: dict[str, SCMWorld] = {
    "linear_chain": linear_chain(),
    "confounder": confounder(),
    "latent_confounder": latent_confounder(),
    "threshold": threshold(),
    "independence": independence(),
    "mediation": mediation(),
}
