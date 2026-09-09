"""DIAGNOSTIC: per-atom policy parity of the Step-2 Anderson base solver vs the production
EGM base solve, via the REAL economy.solve() path (apples-to-apples, no MC noise).

For each cohort atom: solve once with HAFISCAL_STEP2_NAMG unset (EGM solve_agg_cons_markov_alt)
and once with it set (multi-state Anderson), then compare cFunc[j](m, Cratio=1) on the ergodic
region. Isolates whether the Anderson policy matches the production base policy.

Run (from FromPandemicCode/):
  PYTHONPATH=. HAFISCAL_SKIP_ESTIMATION=1 <python> fti_diagnostics/_poc_step2_namg_policy_parity.py
"""
from __future__ import annotations
import os
import sys
import numpy as np

os.environ.setdefault("HAFISCAL_SKIP_ESTIMATION", "1")

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_FROMPANDEMIC, os.path.normpath(os.path.join(_FROMPANDEMIC, ".."))):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _cfuncs_after_solve(eco, anderson):
    if anderson:
        os.environ["HAFISCAL_STEP2_NAMG"] = "1"
    else:
        os.environ.pop("HAFISCAL_STEP2_NAMG", None)
    eco.solve()
    out = []
    for ag in eco.agents:
        S = np.asarray(ag.MrkvArray[0]).shape[0]
        out.append([ag.solution[0].cFunc[j] for j in range(S)])
    return out


def main():
    import EstimAggFiscalMAIN as E
    eco = E.AggDemandEconomy
    agents = eco.agents
    m = np.linspace(0.5, 12.0, 60)
    ones = np.ones_like(m)

    egm = _cfuncs_after_solve(eco, anderson=False)
    if any(getattr(a, "_step2_namg_used", False) for a in agents):
        print("WARNING: Anderson used on the EGM pass!", flush=True)
    for a in agents:
        a._step2_namg_used = False
    nam = _cfuncs_after_solve(eco, anderson=True)
    used = sum(bool(getattr(a, "_step2_namg_used", False)) for a in agents)
    print(f"agents using Anderson on the ON pass: {used}/{len(agents)}\n", flush=True)

    DFC = int(E.DiscFacCount)
    cohorts = {0: "Dropout", 1: "Highschool", 2: "College"}
    print(f"{'atom':>22} {'beta':>8} {'max|dc|':>10} {'rel':>10}")
    worst_overall = 0.0
    for idx, (ce, cn) in enumerate(zip(egm, nam)):
        ed = idx // DFC
        beta = float(agents[idx].DiscFac)
        worst = 0.0
        for j in range(len(ce)):
            c_e = np.asarray(ce[j](m, ones), dtype=float)
            c_n = np.asarray(cn[j](m, ones), dtype=float)
            worst = max(worst, float(np.max(np.abs(c_e - c_n))))
        rel = worst / 1.0
        worst_overall = max(worst_overall, worst)
        flag = "  <<" if worst > 5e-3 else ""
        print(f"{cohorts[ed]+'['+str(idx%DFC)+']':>22} {beta:>8.4f} {worst:>10.2e} {rel:>10.2e}{flag}")
    print(f"\nWORST per-atom policy max|dc| = {worst_overall:.3e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
