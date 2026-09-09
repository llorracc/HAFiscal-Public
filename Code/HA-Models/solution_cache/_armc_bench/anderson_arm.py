"""L3: composite Anderson arm on the snapshot — wall + honesty + agreement
with the Newton fixed point + truth-bank score."""
import faulthandler, os, sys, time, pickle
faulthandler.dump_traceback_later(1800, exit=True)
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, REPO + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, REPO + "/Code/HA-Models")
sys.path.insert(0, "/home/shared/github/llorracc/fast-time-iteration")
import numpy as np

BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"
with open(BENCH + "/snap_edges.pkl", "rb") as f:
    snap = pickle.load(f)
aG, edges, hb, rb = (snap["aXtraGrid"], snap["edges"], snap["hb"], snap["rb"])
MPCmin, meta = snap["MPCmin"], snap["meta"]
CRRA, DFE = meta["CRRA"], meta["DiscFacEff"]
Cg = np.asarray(meta["Cgrid"], float).reshape(-1)
Cc = len(Cg)

from hark_fti.consumed_ati_markov import solve_stationary_consumed_anderson

aG0 = np.insert(aG, 0, 0.0)
for depth, grid, gtag in ((5, aG, "a48"), (8, aG, "a48"), (12, aG, "a48"),
                          (8, aG0, "a0+48")):
    t0 = time.time()
    X, conts, info = solve_stationary_consumed_anderson(
        grid, edges, hb, rb, MPCmin, CRRA, DFE, depth=depth, tol=1e-9,
        maxit=600, tail_form="powerlaw", verbose=False)
    wall = time.time() - t0
    if grid.size == aG.size:
        nx = np.load(BENCH + "/flat.npz")
        dX = float(np.max(np.abs(X - nx["X"]) / (1.0 + np.abs(nx["X"]))))
        xs = f"  vs-newton-X={dX:.3e}"
    else:
        xs = ""
    line = (f"[and] depth={depth} grid={gtag}: "
            f"sweeps={info['inner_iters_total']} "
            f"conv={info['converged']} ({info['converged_reason']}) "
            f"fnorm={info['fnorm']:.3e} fb={info['n_fallback']} "
            f"wall={wall:.1f}s{xs}")
    if info["converged"]:
        with open(BENCH + "/snap_truth_sol.pkl", "rb") as f:
            truth = pickle.load(f)
        m_probe = np.geomspace(0.05, 30.0, 80)
        errs = []
        for b in range(len(hb)):
            j, k = b // Cc, b % Cc
            tv = np.asarray(truth.cFunc[j](m_probe,
                                           np.full_like(m_probe, Cg[k])))
            nv = np.asarray(conts[b][3](m_probe))
            errs.append(np.abs(nv - tv) / np.maximum(np.abs(tv), 1e-8))
        E = np.concatenate(errs)
        line += f"  vs-truth max={E.max():.3e} med={np.median(E):.3e}"
    print(line, flush=True)
print("[and] DONE", flush=True)
