"""Suite 2 Translation — Three research-grade SCM worlds.

Each world is designed for a DIFFERENT evaluation purpose:
  W1 (Comparative Effectiveness): structural complexity — mediation,
      heterogeneity, multi-outcome, confounding.
  W2 (Observational Epidemiology): disambiguation — Simpson's reversal,
      collider bias, causal-vs-observational distinction.
  W3 (Environmental Health): distributional + abstention — threshold
      effects, latent confounding (non-identifiability), null variables.

All equations are linear-Gaussian EXCEPT:
  - W1 has an interaction term (B*T in Y)
  - W3 has a piecewise-linear threshold (f(Temp) in H)

Ground truth is derived analytically from the equations. Monte Carlo
verification (N=100K) should match within +-0.02 for means and +-0.05
for variances.
"""

from __future__ import annotations

import numpy as np

from sreg.world.scm import SCMWorld


# ===================================================================
# W1: COMPARATIVE EFFECTIVENESS STUDY
# ===================================================================
#
# Domain: Clinical medicine. Observational study of treatment
# effectiveness with confounding, mediation, effect modification,
# and a multi-outcome structure (Y + SE).
#
# Variables (7 observable):
#   A  (age)         ~ N(0, 1)                       root
#   S  (severity)    = 0.4*A + eps(0.5)              A -> S
#   T  (treatment)   = -0.5*S + eps(0.6)             S -> T
#   M  (compliance)  = 0.6*T + eps(0.4)              T -> M
#   B  (biomarker)   ~ N(0, 1)                       root (independent)
#   Y  (outcome)     = 0.5*T + 0.3*M + 0.2*B        T,M,B,S,A -> Y
#                      + 0.35*B*T - 0.3*S + 0.15*A
#                      + eps(0.3)
#   SE (side_effect) = 0.7*T + 0.2*A + eps(0.4)     T,A -> SE
#
# DAG: A->S->T->M->Y, A->Y, A->SE, S->Y, T->Y, T->SE, B->Y, B*T->Y
#
# --- Analytical ground truth ---
#
# ATE(T -> Y) per unit of T:
#   Under do(T=t): E[M] = 0.6*t, E[B] = 0, E[S] = 0, E[A] = 0
#   E[Y|do(T=t)] = 0.5*t + 0.3*(0.6*t) + 0 + 0 - 0 + 0
#                = 0.5*t + 0.18*t = 0.68*t
#   ATE per unit = 0.68
#   Decomposition: direct = 0.50, indirect via M = 0.18
#
# Effect heterogeneity by B:
#   E[Y|do(T=t), B=b] = 0.68*t + 0.2*b + 0.35*b*t + const
#   Marginal effect of T given B=b: 0.68 + 0.35*b
#   At B=+1: effect = 1.03; at B=-1: effect = 0.33; at B=0: effect = 0.68
#
# Total effect of A on Y:
#   Under do(A=a): E[S]=0.4*a, E[T]=-0.2*a, E[M]=-0.12*a
#   E[Y|do(A=a)] = 0.5*(-0.2*a) + 0.3*(-0.12*a) + 0 - 0.3*(0.4*a) + 0.15*a
#                = -0.10*a - 0.036*a - 0.12*a + 0.15*a
#                = -0.106*a  (~-0.11)
#   Positive direct effect (+0.15) dominated by negative indirect paths.
#
# Confounding of T->Y by S:
#   S -> T (coef -0.5) and S -> Y (coef -0.3). Crude observational
#   association of T,Y is confounded. Adjusting for S is required.
#
# Multi-outcome: T -> SE
#   ATE(T -> SE) per unit = 0.70 (direct, no mediator for SE)
#   Treatment helps Y but causes SE — multi-outcome trade-off.
#
# Mediation T -> M -> Y:
#   Direct: 0.50, Indirect: 0.18, Total: 0.68
#
# Ranking of causal effects on Y:
#   T (0.68) > M_direct_on_Y (0.30) > B (0.20) > A_direct (0.15)


def comparative_effectiveness() -> SCMWorld:
    """W1: Comparative Effectiveness Study."""
    return SCMWorld(
        id="suite2-w1-comparative-effectiveness",
        graph={
            "A": [],
            "S": ["A"],
            "T": ["S"],
            "M": ["T"],
            "B": [],
            "Y": ["T", "M", "B", "S", "A"],
            "SE": ["T", "A"],
        },
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "S": lambda p, rng: 0.4 * p["A"] + rng.normal(0, 0.5),
            "T": lambda p, rng: -0.5 * p["S"] + rng.normal(0, 0.6),
            "M": lambda p, rng: 0.6 * p["T"] + rng.normal(0, 0.4),
            "B": lambda p, rng: rng.normal(0, 1),
            "Y": lambda p, rng: (
                0.5 * p["T"]
                + 0.3 * p["M"]
                + 0.2 * p["B"]
                + 0.35 * p["B"] * p["T"]
                - 0.3 * p["S"]
                + 0.15 * p["A"]
                + rng.normal(0, 0.3)
            ),
            "SE": lambda p, rng: 0.7 * p["T"] + 0.2 * p["A"] + rng.normal(0, 0.4),
        },
    )


# ===================================================================
# W2: OBSERVATIONAL EPIDEMIOLOGY (Simpson's reversal)
# ===================================================================
#
# Domain: Epidemiological study where the crude association has
# OPPOSITE sign from the true causal effect (Simpson's paradox).
#
# Variables (6 observable):
#   C  (confounder)  ~ N(0, 1)                      root
#   I  (upstream)    ~ N(0, 1)                      root
#   E  (exposure)    = 0.5*C + 0.3*I + eps(0.5)    C,I -> E
#   M  (mediator)    = 0.4*E + eps(0.5)             E -> M
#   D  (disease)     = -0.4*E + 0.5*M + 0.6*C      E,M,C -> D
#                      + eps(0.4)
#   L  (collider)    = 0.4*E + 0.5*D + eps(0.5)    E,D -> L (collider!)
#
# DAG: C->E, C->D, I->E, E->M->D, E->D, E->L<-D
#
# --- Analytical ground truth ---
#
# ATE(E -> D) per unit:
#   Under do(E=e): E[M]=0.4*e, E[C]=0
#   E[D|do(E=e)] = -0.4*e + 0.5*(0.4*e) + 0.6*0 = -0.4*e + 0.2*e = -0.2*e
#   ATE per unit = -0.20 (exposure is PROTECTIVE)
#   Decomposition: direct = -0.40, indirect via M = +0.20, total = -0.20
#
# Crude observational Cov(E, D):
#   D as function of primitives (substituting M):
#     D = -0.4*E + 0.5*(0.4*E + eps_M) + 0.6*C + eps_D
#       = -0.2*E + 0.5*eps_M + 0.6*C + eps_D
#   Cov(E, D) = -0.2*Var(E) + 0.6*Cov(E, C)
#   Var(E) = 0.25 + 0.09 + 0.25 = 0.59
#   Cov(E, C) = 0.5*Var(C) = 0.5
#   Cov(E, D) = -0.2*0.59 + 0.6*0.5 = -0.118 + 0.30 = +0.182
#   SIMPSON'S REVERSAL: crude corr > 0, but true ATE = -0.20
#
# Mediation:
#   Direct E->D = -0.40
#   Indirect E->M->D = 0.4*0.5 = +0.20
#   Total = -0.20
#   Signs differ — direct is harmful, indirect is beneficial.
#
# Collider bias:
#   L = 0.4*E + 0.5*D + eps_L  (L is a collider on E->L<-D)
#   Conditioning on L opens a spurious path E->L<-D, biasing estimates.
#   DO NOT adjust for L when estimating E->D.
#
# Instrument:
#   I -> E is the only path from I to D (I has no direct edge to D or
#   via C). I is a valid instrument for E->D (if needed).
#
# Identifiability:
#   ATE(E->D) IS identifiable by adjusting for C (valid backdoor set).
#   Valid adjustment sets: {C}, {C, I}.
#   Invalid: {L} (collider), {L, C} (still opens collider path).


def observational_epidemiology() -> SCMWorld:
    """W2: Observational Epidemiology with Simpson's reversal."""
    return SCMWorld(
        id="suite2-w2-observational-epidemiology",
        graph={
            "C": [],
            "I": [],
            "E": ["C", "I"],
            "M": ["E"],
            "D": ["E", "M", "C"],
            "L": ["E", "D"],
        },
        equations={
            "C": lambda p, rng: rng.normal(0, 1),
            "I": lambda p, rng: rng.normal(0, 1),
            "E": lambda p, rng: 0.5 * p["C"] + 0.3 * p["I"] + rng.normal(0, 0.5),
            "M": lambda p, rng: 0.4 * p["E"] + rng.normal(0, 0.5),
            "D": lambda p, rng: (
                -0.4 * p["E"] + 0.5 * p["M"] + 0.6 * p["C"] + rng.normal(0, 0.4)
            ),
            "L": lambda p, rng: 0.4 * p["E"] + 0.5 * p["D"] + rng.normal(0, 0.5),
        },
    )


# ===================================================================
# W3: ENVIRONMENTAL HEALTH (threshold + latent + null)
# ===================================================================
#
# Domain: Climate and pollution effects on health. Includes a latent
# confounder, a piecewise-linear threshold, and a null variable.
#
# Variables (6 observable + 1 latent):
#   R         (region)       ~ N(0, 1)                     root
#   U         (hidden)       ~ N(0, 1)                     root, LATENT
#   Temp      (temperature)  = 0.5*R + eps(0.3)            R -> Temp
#   P         (pollution)    = 0.3*R + 0.4*U + eps(0.3)   R,U -> P
#   W         (water_qual)   = -0.5*Temp - 0.3*P + eps(0.3)  Temp,P -> W
#   H         (health)       = 0.4*W - 0.2*P + 0.3*U      W,P,U,Temp -> H
#                              + f(Temp) + eps(0.3)
#                              where f(Temp) = 0 if Temp<0
#                                            = -0.8*Temp if Temp>=0
#   WindSpeed               ~ N(0, 1)                     root, NULL (no effect)
#
# DAG: R->Temp, R->P, U->P, U->H, Temp->W->H, P->W, P->H,
#      Temp->H (piecewise)
#      WindSpeed is disconnected from all other variables.
#
# --- Analytical ground truth ---
#
# Temp -> H total effect (two paths):
#   Path 1 (indirect): Temp -> W -> H
#     dW/dTemp = -0.5, dH/dW = 0.4 => contribution = -0.20 (always)
#   Path 2 (direct, piecewise): f(Temp)
#     Below threshold (Temp < 0): f = 0, so contribution = 0
#     Above threshold (Temp >= 0): f = -0.8*Temp, so contribution = -0.80
#
#   Total slope of H w.r.t. Temp:
#     Temp < 0:  -0.20 (indirect only)
#     Temp >= 0: -0.20 + (-0.80) = -1.00 (indirect + piecewise)
#   Changepoint at Temp = 0.
#
# P -> H (NOT identifiable):
#   True paths: P -> H direct (-0.2), P -> W -> H (0.4*(-0.3) = -0.12)
#   True total causal effect = -0.20 + (-0.12) = -0.32
#   BUT: U -> P and U -> H, with U latent. No valid backdoor set
#   exists (U is the required adjustment variable and it's unobservable).
#   The causal effect of P on H is NOT identifiable from observational data.
#
# WindSpeed -> H:
#   ZERO effect. WindSpeed is an independent root with no path to H.
#   Null relationship — important for abstention/negative testing.
#
# R -> H:
#   R affects H only indirectly (through Temp and P). No direct edge.
#   Under do(R=r): E[Temp]=0.5*r, E[P]=0.3*r (U marginalized)
#   The total effect depends on the threshold, so it differs by sign of Temp.
#
# Var(H) by region:
#   Heteroscedastic because the piecewise function changes the slope.
#   Regions with higher Temp (higher R) have larger |dH/dTemp|,
#   potentially different variance.


def environmental_health() -> SCMWorld:
    """W3: Environmental Health with threshold, latent, and null."""
    return SCMWorld(
        id="suite2-w3-environmental-health",
        graph={
            "R": [],
            "U": [],
            "Temp": ["R"],
            "P": ["R", "U"],
            "W": ["Temp", "P"],
            "H": ["W", "P", "U", "Temp"],
            "WindSpeed": [],
        },
        equations={
            "R": lambda p, rng: rng.normal(0, 1),
            "U": lambda p, rng: rng.normal(0, 1),
            "Temp": lambda p, rng: 0.5 * p["R"] + rng.normal(0, 0.3),
            "P": lambda p, rng: 0.3 * p["R"] + 0.4 * p["U"] + rng.normal(0, 0.3),
            "W": lambda p, rng: (
                -0.5 * p["Temp"] - 0.3 * p["P"] + rng.normal(0, 0.3)
            ),
            "H": lambda p, rng: (
                0.4 * p["W"]
                - 0.2 * p["P"]
                + 0.3 * p["U"]
                + (-0.8 * p["Temp"] if p["Temp"] >= 0 else 0.0)
                + rng.normal(0, 0.3)
            ),
            "WindSpeed": lambda p, rng: rng.normal(0, 1),
        },
        latent_variables={"U"},
    )


# -------------------------------------------------------------------
# World registry
# -------------------------------------------------------------------

ALL_WORLDS: dict[str, SCMWorld] = {
    "w1_comparative_effectiveness": comparative_effectiveness(),
    "w2_observational_epidemiology": observational_epidemiology(),
    "w3_environmental_health": environmental_health(),
}
