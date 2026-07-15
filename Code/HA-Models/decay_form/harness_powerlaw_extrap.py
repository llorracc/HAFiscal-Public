"""Validation harness for HARK's power-law decay_extrap_form (the PR in the
fast-time-iteration-adjacent worktree `HARK-pr-aggshock-pf-decay`).

Drives the WORKTREE HARK (sys.path injection -- run with the HAFiscal venv) and,
for each calibration of the derivation's SS5 table
(conclusions_private/2026-06-24_buffer-stock-decay-power-law-derivation.md):

  (a) solves a DEEP-grid infinite-horizon IndShock model (the truth), then for a
      ladder of grid depths rebuilds truncated-grid extrapolants and reports the
      implied power-law exponent Q_emp = B*(m_top + h) against the theory
      anchors q* (Kesten root) and min(1, q*) (asymptotic leading exponent) --
      Q_emp should migrate from ~q* below the crossover toward min(1, q*) as
      the grid deepens (the two-channel structure);
  (b) at depth 40 (the HAFiscal production-solve-grid scale), compares
      exponential vs power-law extrapolation error against the deep truth.

Cancellation guard: gap measurements are only trusted where gap/c > 1e-10 (the
float64 catastrophic-cancellation floor established in the decay_form work).

Usage:
    PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
    $PY Code/HA-Models/decay_form/harness_powerlaw_extrap.py
"""

import sys

WORKTREE = '/home/shared/github/econ-ark/HARK-pr-aggshock-pf-decay'
sys.path.insert(0, WORKTREE)

import numpy as np
from scipy.optimize import brentq

from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType
from HARK.interpolation import LinearInterp

GAP_FLOOR = 1e-10  # trust gap measurements only where gap/c exceeds this
DEPTHS = (20.0, 40.0, 100.0, 400.0, 1000.0)


def qstar_discrete(R, Gamma, beta, rho, LivPrb, psi_atoms, psi_pmv):
    """Kesten root of E[psi^(1+q)] = (R/Gamma) * P_Gamma^q, with the survival
    factor entering through the growth patience factor P_Gamma = (R beta L)^(1/rho)/Gamma
    (mortality-as-impatience, matching pf_mpc_min). Discrete-psi version so the
    root is model-consistent with the solved agent's shock discretization."""
    PG = (R * beta * LivPrb) ** (1.0 / rho) / Gamma
    if PG >= 1.0:
        return np.nan  # GIC fails; no decaying gap exponent

    def f(q):
        return (
            np.log(np.dot(psi_pmv, psi_atoms ** (1.0 + q)))
            - np.log(R / Gamma)
            - q * np.log(PG)
        )

    if f(0.0) >= 0.0:  # FHWC fails or degenerate
        return np.nan
    hi = 1.0
    while f(hi) < 0.0 and hi < 512.0:
        hi *= 2.0
    return brentq(f, 0.0, hi, xtol=1e-10)


def solve_case(name, R, Gamma, beta, rho=2.0, LivPrb=1.0, sigma_tran=0.1,
               perm_std=0.0, unemp=0.0, inc_unemp=0.0):
    pars = dict(
        cycles=0, Rfree=[R], PermGroFac=[Gamma], DiscFac=beta, CRRA=rho,
        LivPrb=[LivPrb], PermShkStd=[perm_std], TranShkStd=[sigma_tran],
        UnempPrb=unemp, IncUnemp=inc_unemp, T_cycle=1,
        aXtraMax=1.0e6, aXtraCount=240, aXtraNestFac=3,
        vFuncBool=False, CubicBool=False,
    )
    agent = IndShockConsumerType(**pars)
    agent.solve()
    sol = agent.solution[0]
    dstn = agent.IncShkDstn[0]
    psi = np.asarray(dstn.atoms[0], float)
    pmv = np.asarray(dstn.pmv, float)
    qs = qstar_discrete(R, Gamma, beta, rho, LivPrb, psi, pmv)
    return dict(name=name, sol=sol, qstar=qs, R=R, Gamma=Gamma, beta=beta)


def truncated_pair(sol, depth, n=250):
    """Rebuild (exp, powerlaw) extrapolants from the truth resampled on
    [mNrmMin + eps, depth], with a refined top segment so the implied top-knot
    secant is a good local derivative."""
    lo = sol.mNrmMin + 0.05
    m = np.unique(np.r_[np.linspace(lo, 0.98 * depth, n),
                        np.linspace(0.98 * depth, depth, 26)])
    c = sol.cFunc(m)
    lims = dict(intercept_limit=sol.MPCmin * sol.hNrm, slope_limit=sol.MPCmin)
    fe = LinearInterp(m, c, **lims)
    fp = LinearInterp(m, c, **lims, decay_extrap_form="powerlaw")
    return fe, fp


def run_case(case, out):
    sol, qs = case['sol'], case['qstar']
    lead = min(1.0, qs) if np.isfinite(qs) else np.nan
    out.append(f"\n=== {case['name']}: R={case['R']} Gamma={case['Gamma']} "
               f"beta={case['beta']} ===")
    out.append(f"    MPCmin={sol.MPCmin:.6f} hNrm={sol.hNrm:.4f}  "
               f"q*={qs:.4f}  min(1,q*)={lead:.4f}")
    # (a) exponent-vs-depth table
    out.append(f"    {'depth':>7} {'Q_emp':>8}   (theory: q* pre-crossover -> min(1,q*) asymptotically)")
    for d in DEPTHS:
        fe, fp = truncated_pair(sol, d)
        q_emp = fp.decay_extrap_Q if fp.decay_extrap else np.nan
        out.append(f"    {d:7.0f} {q_emp:8.4f}")
    # (b) error table at depth 40 vs deep truth
    fe, fp = truncated_pair(sol, 40.0)
    lad = np.geomspace(48.0, 800.0, 22)
    c_true = sol.cFunc(lad)
    gap_true = sol.MPCmin * (lad + sol.hNrm) - c_true
    keep = gap_true / c_true > GAP_FLOOR
    lad, c_true, gap_true = lad[keep], c_true[keep], gap_true[keep]
    err_e = np.abs(fe(lad) - c_true)
    err_p = np.abs(fp(lad) - c_true)
    out.append(f"    depth-40 extrapolation vs truth on m in [{lad[0]:.0f}, {lad[-1]:.0f}] "
               f"({len(lad)} clean pts):")
    out.append(f"      max err/c:      exp {np.max(err_e / c_true):.3e}   "
               f"powerlaw {np.max(err_p / c_true):.3e}")
    out.append(f"      err/gap at top: exp {err_e[-1] / gap_true[-1]:.3f}      "
               f"powerlaw {err_p[-1] / gap_true[-1]:.3f}")
    with np.errstate(divide='ignore'):
        ratio = np.where(err_p > 0, err_e / err_p, np.inf)
    out.append(f"      err_exp/err_pl: median {np.median(ratio):.1f}  min {np.min(ratio):.1f}")


def main():
    out = []
    out.append("POWER-LAW vs EXPONENTIAL decay_extrap: worktree-HARK validation harness")
    out.append(f"worktree: {WORKTREE}")
    import HARK
    out.append(f"HARK resolves to: {HARK.__file__}")
    assert WORKTREE in HARK.__file__, "harness must run against the worktree HARK"

    cases = [
        # the derivation SS5 table (transitory-only, lognormal sigma=0.1)
        solve_case("case A (q*=2.72>1 -> leading m^-1, crossover ~89)",
                   R=1.04, Gamma=1.01, beta=0.96),
        solve_case("impatient (q*=0.21<1 -> leading m^-q*)",
                   R=1.01, Gamma=1.0, beta=0.90),
        solve_case("no-growth patient (q*~49 -> leading m^-1)",
                   R=1.04, Gamma=1.0, beta=0.96),
        # HARK default-ish calibration (perm shocks + unemployment + mortality)
        solve_case("HARK-default-like (perm+unemp+mortality)",
                   R=1.03, Gamma=1.01, beta=0.96, LivPrb=0.98,
                   sigma_tran=0.1, perm_std=0.1, unemp=0.05, inc_unemp=0.3),
    ]
    for c in cases:
        run_case(c, out)

    text = "\n".join(out)
    print(text)
    with open(__file__.replace('.py', '_out.txt'), 'w') as f:
        f.write(text + "\n")


if __name__ == '__main__':
    main()
