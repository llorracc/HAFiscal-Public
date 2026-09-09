#!/usr/bin/env python3
"""Econ-5 (reporting half; owner 2026-08-28 10:33 "reporting only"): who receives the stimulus check.

The check is $1,200 below $100k of annual permanent income, phased out linearly to zero at $150k
(Subfiles/Model.tex; Parameters.py CheckStimLvl_PLvl_Cutoff_start/end = 25 / 37.5 in $1000 per quarter).
The share of households below the phase-out (full check), inside it (partial) and above it (none) is a closed-form
statistic of the ergodic permanent-income distribution -- the same lognormal mixture the TM's 50-bucket delivery
integrates over (tm_methods.compute_pLvl_distribution; BUG-092 probe) -- so it needs no simulation. It depends on the
income process and the age cap (uncapped: College E[p] ~ 4.7 p0), not on the discount factors, so one row per chain
column's ENVIRONMENT is enough. Usage (one process per column; the env selects the world):
  HAFISCAL_WORLD=default python check_coverage_shares.py --label "default (uncapped, perm shocks on)"
  HAFISCAL_WORLD=as-corrected python check_coverage_shares.py --label "corrected (uncapped, perm off)"
  HAFISCAL_WORLD=as-corrected HAFISCAL_T_AGE=200 ... python check_coverage_shares.py --label "original (capped)"
Prints a markdown row: label | dropout full/partial/none | HS ... | college ... | population-weighted (SCF 2004 shares).
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); FPC = os.path.join(HERE, "FromPandemicCode")
sys.path.insert(0, FPC); sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--label", default=os.environ.get("HAFISCAL_WORLD", "default"))
    ap.add_argument("--parametrization", default="Baseline"); ap.add_argument("--n-points", type=int, default=20000)
    ap.add_argument("--header", action="store_true"); a = ap.parse_args()
    sys.argv = sys.argv[:1]
    os.environ.setdefault("HAFISCAL_POLICY_STORE_REQUIRE", "0"); os.environ.setdefault("HAFISCAL_QUIET_BETADISTR", "1")
    import numpy as np
    from Parameters import return_parameters
    import tm_methods as tm
    import welfare6_scenario as ws
    data_EducShares = return_parameters(Parametrization=a.parametrization, OutputFor="_Main.py")[12]
    ctx = ws.build_and_solve(a.parametrization)          # the economy's own agents (policy-store hits; the income process is what matters)
    agents = ctx["AggEco"].agents
    rows = []
    for e in range(3):
        agent = next(ag for ag in agents if int(getattr(ag, "EducType", -1)) == e)
        grid, w = tm.compute_pLvl_distribution(agent, n_points=a.n_points, unemployment_rate=None)
        lo, hi = agent.CheckStimLvl_PLvl_Cutoff_start, agent.CheckStimLvl_PLvl_Cutoff_end
        band = (grid >= lo) & (grid <= hi); above = grid > hi
        rows.append((float(w[~band & ~above].sum()), float(w[band].sum()), float(w[above].sum()), float(w @ grid),
                     getattr(agent, "T_age", None)))
    sh = np.asarray(data_EducShares, float); pop = [float(sum(sh[e] * rows[e][k] for e in range(3))) for k in range(3)]
    if a.header:
        print("| column | dropout full / partial / none | high school | college | population (SCF shares) | E[p] D / HS / C ($k per quarter) |")
        print("|---|---|---|---|---|---|")
    fmt = lambda r: f"{100*r[0]:.1f} / {100*r[1]:.1f} / {100*r[2]:.1f} %"
    print(f"| {a.label} (T_age={rows[0][4]}) | {fmt(rows[0])} | {fmt(rows[1])} | {fmt(rows[2])} | {fmt(pop)} | "
          f"{rows[0][3]:.1f} / {rows[1][3]:.1f} / {rows[2][3]:.1f} |")


if __name__ == "__main__":
    main()
