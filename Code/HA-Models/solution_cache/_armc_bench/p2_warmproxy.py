"""P2 proxy: warm-start payoff under an AD-iteration-sized perturbation.
Perturb every edge's transitory atoms by f (proxy for the AD loop moving
ADFunc/Cnext), then solve cold vs warm-from-unperturbed-X*. The iteration
count from warm start is the AD-regime speedup driver."""
import faulthandler, os, sys, time, pickle, copy
faulthandler.dump_traceback_later(1800, exit=True)
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, "/home/shared/github/llorracc/fast-time-iteration")
import numpy as np

BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"
with open(BENCH + "/snap_edges.pkl", "rb") as f:
    snap = pickle.load(f)
aG, edges, hb, rb = (snap["aXtraGrid"], snap["edges"], snap["hb"], snap["rb"])
MPCmin, meta = snap["MPCmin"], snap["meta"]
CRRA, DFE = meta["CRRA"], meta["DiscFacEff"]
from hark_fti.consumed_ati_markov import solve_stationary_consumed_blocks

aG0 = np.insert(aG, 0, 0.0)
Xstar = np.load(BENCH + "/newton_a0.npz")["X"]

def perturb(f):
    e2 = copy.deepcopy(edges)
    for ei in e2:
        for e in ei:
            if e.get("combine") == "nvrs":
                for (_, _, at) in e["targets"]:
                    at["Tran"] = np.asarray(at["Tran"], float) * f
            else:
                e["Tran"] = np.asarray(e["Tran"], float) * f
    return e2

for f in (1.002, 1.0002):
    e2 = perturb(f)
    t0 = time.time()
    Xc, _, ic = solve_stationary_consumed_blocks(
        aG0, e2, hb, rb, MPCmin, CRRA, DFE, inner="gmres",
        tol_delta=1e-9, tol_EE=1e-9, maxit=120, tail_form="powerlaw")
    wc = time.time() - t0
    t0 = time.time()
    Xw, _, iw = solve_stationary_consumed_blocks(
        aG0, e2, hb, rb, MPCmin, CRRA, DFE, inner="gmres",
        tol_delta=1e-9, tol_EE=1e-9, maxit=120, tail_form="powerlaw",
        c_init=Xstar)
    ww = time.time() - t0
    d = float(np.max(np.abs(Xw - Xc) / (1.0 + np.abs(Xc))))
    print(f"[p2] f={f}: cold iters={ic['iters']} wall={wc:.1f}s | "
          f"warm iters={iw['iters']} wall={ww:.1f}s | Xw-vs-Xc={d:.2e} "
          f"(conv {ic['converged']}/{iw['converged']})", flush=True)
print("[p2] DONE", flush=True)
