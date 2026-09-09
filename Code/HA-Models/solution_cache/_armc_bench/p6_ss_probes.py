"""P6 (R-d rationale probes): is A_ss_weighted a robust statistic?

For each of the 21 (education, beta) cells: solve the infinite-horizon
problem ONCE (the solve grid is independent of the distribution grid),
apply the Harmenberg neutral measure once, then recompute the ergodic
distribution and the (C_ss, A_ss) aggregates under several distribution
grids. If the aggregate drifts with the grid top, the household block's
aggregate wealth is tail-dominated (the GIC-cap College atom's
quasi-unit-root wealth process) and is NOT a well-defined calibration
anchor — which decides between the R-d closure rationales.

Also reports: per-education aggregates, the College-top-atom share, and
tail-mass diagnostics (ergodic mass in the top decade of the grid and on
the top gridpoint itself).
"""
import os
import sys
import time
from copy import deepcopy

import numpy as np

HA = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
sys.path.insert(0, HA)
sys.path.insert(0, os.path.join(HA, "FromPandemicCode"))
# cwd=FPC exactly like the production entry (Parameters resolves the
# calibration files cwd-dependently; from repo root it silently falls
# back to the CDC/legacy discount factors — the first run of this probe
# did exactly that and simulated a different block, A_ss=0.351).
os.chdir(os.path.join(HA, "FromPandemicCode"))

from step4 import hh_setup  # noqa: E402

CONFIGS = [  # (label, mMax, mCount); baseline = production (1e5, 200)
    ("1e4/200", 1.0e4, 200),
    ("1e5/200 (prod)", 1.0e5, 200),
    ("1e6/200", 1.0e6, 200),
    ("1e6/400", 1.0e6, 400),
]
WEIGHTS = [0.093, 0.527, 0.38]

ctx = hh_setup.build()
n_betas = len(ctx.DiscFacDstns[0].atoms[0])

# results[cfg][e][d] = (C, A, top_decade_mass, top_point_mass)
results = {lab: np.zeros((3, n_betas, 4)) for lab, _, _ in CONFIGS}

t0 = time.time()
for e in range(3):
    betas = ctx.DiscFacDstns[e].atoms[0]
    for d, beta in enumerate(betas):
        agent = deepcopy(ctx.BaseTypeList[e])
        agent.IncShkDstn = deepcopy([ctx.IncShkDstn[e]])
        agent.DiscFac = float(beta)
        agent.cycles = 0
        agent.solve()
        agent.neutral_measure = True
        agent.harmenberg_income_process()
        for lab, mmax, mcount in CONFIGS:
            agent.mMax = mmax
            agent.mCount = mcount
            agent.define_distribution_grid()
            agent.calc_transition_matrix()
            agent.calc_ergodic_dist()
            a = np.asarray(agent.aPol_Grid).flatten()
            c = np.asarray(agent.cPol_Grid).flatten()
            D = np.asarray(agent.vec_erg_dstn).flatten()
            A_cell = float(np.dot(a, D))
            C_cell = float(np.dot(c, D))
            grid = np.asarray(agent.dist_mGrid)
            nm = len(grid)
            nstates = len(D) // nm
            Dm = D.reshape(nstates, nm) if D.size == nstates * nm else D.reshape(nm, nstates).T
            # mass in the top decade of the m-grid and on the top point
            top_dec = float(Dm[:, grid > mmax / 10.0].sum())
            top_pt = float(Dm[:, -1].sum())
            results[lab][e, d] = (C_cell, A_cell, top_dec, top_pt)
        print(f"[p6] e={e} d={d} beta={beta:.6f} solved+4cfg "
              f"({time.time()-t0:.0f}s)", flush=True)

print("\n===== P6 GRID-SENSITIVITY TABLE =====")
print(f"{'config':>16s} {'C_ss_w':>12s} {'A_ss_w':>12s} "
      f"{'A_drop':>9s} {'A_hs':>9s} {'A_coll':>10s} {'collTopAtom%':>12s} "
      f"{'topDecMass':>11s} {'topPtMass':>10s}")
for lab, mmax, mcount in CONFIGS:
    R = results[lab]
    Cw = sum(WEIGHTS[e] * R[e, :, 0].sum() / n_betas for e in range(3))
    Aw = sum(WEIGHTS[e] * R[e, :, 1].sum() / n_betas for e in range(3))
    A_educ = [R[e, :, 1].mean() for e in range(3)]
    top_atom_contrib = WEIGHTS[2] * R[2, -1, 1] / n_betas
    share = 100.0 * top_atom_contrib / Aw if Aw else float("nan")
    # tail masses shown for the College top atom (the GIC-cap cell)
    print(f"{lab:>16s} {Cw:12.7f} {Aw:12.5f} "
          f"{A_educ[0]:9.4f} {A_educ[1]:9.4f} {A_educ[2]:10.4f} {share:12.2f} "
          f"{R[2, -1, 2]:11.3e} {R[2, -1, 3]:10.3e}")

np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "p6_ss_grid_sensitivity.npz"),
         **{lab.replace("/", "_").replace(" ", ""): results[lab]
            for lab, _, _ in CONFIGS})
print("[p6] saved p6_ss_grid_sensitivity.npz")
