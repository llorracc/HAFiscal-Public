"""Consumption-equivalent welfare gains for CRRA utility (the appendix's 𝒞 measure).

BUG-082 (found 2026-08-20). The paper's online-appendix robustness tables report
"consumption-equivalent welfare gains in basis points", 𝒞. ``Welfare.py`` computed them as

    𝒞 = ΔU / W_c − NPV_cost / P_c,      W_c = PDV(1) · N,

i.e. the change in the social planner's lifetime utility (utils, summed over agents and
discounted) divided by the present value of a unit consumption stream for every agent. That
division turns utils into a proportional consumption change ONLY under log utility, where a
uniform proportional change x raises each agent's lifetime utility by x · PDV(1). The code
said so (``#*** This assumes log utility. Need to fix this if we are going to use it``) and
was used at CRRA = 2 anyway. With CRRA = ρ ≠ 1 the utility change produced by a uniform
proportional change x is

    U(c·(1+x)) − U(c) = [(1+x)^{1−ρ} − 1] · U(c),      U(c) = Σ_t R^{−t} Σ_i c_it^{1−ρ}/(1−ρ),

so the consumption equivalent of a utility change ΔU relative to a reference path c is

    x = (1 + ΔU / U(c))^{1/(1−ρ)} − 1      (ρ ≠ 1),
    x = exp(ΔU / (Σ_t R^{−t} N)) − 1       (ρ = 1),

whose first-order expansion is ΔU / Σ_t R^{−t} Σ_i c_it^{1−ρ} — for ρ = 2 the divisor is
the discounted sum of 1/c_it, not PDV(1)·N. Measured on the 2026-08-20 Baseline welfare
panel (consumption in level units, mean 40.9): the legacy divisor is 12.06× the correct one
at ρ = 2 (72.5× at ρ = 3; 1.000 at ρ = 1). Worse than a scale error: ΔU/W_c at ρ = 2 still
carries the units of 1/c, so the published 𝒞 = ΔU/W_c − NPV/P_c subtracts a dimensionless
cost share from a unit-dependent gain. The main-text 𝒲 (welfare6) divides each felicity
difference by that agent-period's marginal utility and is correct for any ρ; it never used W_c.

This module is the single implementation both consumers use (``Welfare.py``'s legacy
MC path and the ``run_welfare6_parallel.py`` battery). ``HAFISCAL_WELFARE_CE_MODE``:
``crra`` (default: the exact formula above) | ``log_legacy`` (the pre-fix W_c division, for
bisection and reproduction of the published appendix numbers).
"""
from __future__ import annotations

import os

import numpy as np

__all__ = [
    "CE_MODES", "ce_mode", "crra_felicity", "lifetime_utility",
    "consumption_equivalent", "cost_share", "ce_net_gain", "format_bp",
]

CE_MODES = ("crra", "log_legacy")
CE_HORIZONS = ("lifetime", "panel")
_ENV = "HAFISCAL_WELFARE_CE_MODE"
_ENV_H = "HAFISCAL_WELFARE_CE_HORIZON"


def ce_mode(mode=None):
    m = (mode if mode is not None else os.environ.get(_ENV, "crra")).strip().lower()
    if m not in CE_MODES:
        raise ValueError(f"{_ENV} must be one of {CE_MODES}; got {m!r}")
    return m


def ce_horizon(horizon=None):
    """Which consumption stream the equivalent scales.

    ``lifetime`` (default): the PERMANENT proportional change of the reference path —
    the appendix's "lifetime consumption units" and the convention the pre-fix divisor
    PDV(1) = 1/(1 − 1/R) embodied (an infinite-horizon normalizer under a T-period utility
    gain, so a gain confined to the simulated window reads as x·(1 − R^{−T}) of a
    same-horizon change). Under CRRA this needs the reference path's lifetime utility, which
    is completed beyond the simulated window with the stationary baseline's per-period
    felicity (the economy returns to its ergodic distribution; policy and recession effects
    die out). ``panel``: the proportional change over the simulated window only — fully
    determined by the data, no continuation assumption.
    """
    h = (horizon if horizon is not None else os.environ.get(_ENV_H, "lifetime")).strip().lower()
    if h not in CE_HORIZONS:
        raise ValueError(f"{_ENV_H} must be one of {CE_HORIZONS}; got {h!r}")
    return h


def continuation_utility(u_cont_per_period, periods, Rfree):
    """R^{-T}/(1 − 1/R) · ū: lifetime utility beyond the simulated window for a stationary
    continuation with per-period (agent-summed) felicity ū."""
    r = 1.0 / float(Rfree)
    return float(u_cont_per_period) * r ** int(periods) / (1.0 - r)


def crra_felicity(c, CRRA):
    c = np.maximum(np.asarray(c, dtype=float), 1e-16)
    if CRRA == 1:
        return np.log(c)
    return c ** (1.0 - CRRA) / (1.0 - CRRA)


def discount_weights(periods, Rfree):
    """R^{-t}, t = 0..periods-1 — the social planner's discounting (Welfare.py: 1/Rfree)."""
    return (1.0 / float(Rfree)) ** np.arange(int(periods))


def lifetime_utility(felicity_panel, Rfree):
    """U = Σ_t R^{-t} Σ_i u_it for a (periods × agents) felicity panel (SP_welfare)."""
    u = np.asarray(felicity_panel, dtype=float)
    return float(np.sum(np.sum(u, axis=1) * discount_weights(u.shape[0], Rfree)))


def consumption_equivalent(U_pol, U_ref, CRRA, Rfree, periods, n_agents, mode=None,
                           horizon=None, u_cont_per_period=None):
    """Uniform proportional consumption change x of the reference path equivalent to the
    utility change U_pol − U_ref (both summed over the simulated ``periods``).

    ``crra``: exact for CRRA utility — x = (1 + ΔU/U_ref)^{1/(1−ρ)} − 1, from
    U(c(1+x)) = (1+x)^{1−ρ} U(c); x = exp(ΔU/(PDV(1)·N)) − 1 at ρ = 1. Reduces to the
    marginal-utility-weighted first-order formula ΔU / Σ_t R^{−t} Σ_i c_it^{1−ρ}.
    ``log_legacy``: (U_pol − U_ref) / (N / (1 − 1/R)) — the pre-fix W_c division (the
    first-order log formula with the infinite-horizon PDV), reproduced verbatim for
    bisection; NOT a consumption equivalent when ρ ≠ 1.

    ``horizon`` (see ce_horizon): ``lifetime`` scales the reference path for ever — U_ref
    is completed beyond the window with ``u_cont_per_period`` (the stationary baseline's
    agent-summed felicity per period; required for ρ ≠ 1) and PDV(1) is the infinite
    1/(1 − 1/R); ``panel`` scales it over the simulated window only.
    """
    m = ce_mode(mode)
    h = ce_horizon(horizon)
    dU = float(U_pol) - float(U_ref)
    r = 1.0 / float(Rfree)
    if m == "log_legacy":
        return dU / (float(n_agents) / (1.0 - r))
    if CRRA == 1:
        pdv1 = 1.0 / (1.0 - r) if h == "lifetime" else float(np.sum(discount_weights(periods, Rfree)))
        return float(np.exp(dU / (pdv1 * float(n_agents))) - 1.0)
    U_ref = float(U_ref)
    if h == "lifetime":
        if u_cont_per_period is None:
            raise ValueError("horizon='lifetime' with CRRA != 1 needs u_cont_per_period "
                             "(the stationary baseline's per-period felicity sum)")
        U_ref = U_ref + continuation_utility(u_cont_per_period, periods, Rfree)
    if U_ref == 0.0:
        raise ValueError("reference lifetime utility is zero; cannot form a consumption equivalent")
    ratio = 1.0 + dU / U_ref      # = (1+x)^{1-ρ}; U_ref < 0 for ρ > 1 so a gain lowers the ratio
    if ratio <= 0.0:
        return float("nan")
    return float(ratio ** (1.0 / (1.0 - CRRA)) - 1.0)


def cost_share(npv_cost, agg_cons0, Rfree):
    """NPV of the policy's fiscal cost as a share of the present value of baseline
    aggregate consumption held at its period-0 level (Welfare.py's P_c convention)."""
    r = 1.0 / float(Rfree)
    return float(npv_cost) / (float(agg_cons0) / (1.0 - r))


def ce_net_gain(U_pol, U_ref, npv_cost, agg_cons0, CRRA, Rfree, periods, n_agents, mode=None,
                horizon=None, u_cont_per_period=None):
    """x − cost share: the net consumption-equivalent gain of a policy in one cell."""
    return (consumption_equivalent(U_pol, U_ref, CRRA, Rfree, periods, n_agents, mode,
                                   horizon, u_cont_per_period)
            - cost_share(npv_cost, agg_cons0, Rfree))


def format_bp(x):
    """Welfare.py's mystr3bp: basis points with three decimals; blank for nan."""
    if x is None or np.isnan(x):
        return ""
    return "{:.3f}".format(float(x) * 10000.0)
