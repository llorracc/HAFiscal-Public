"""Time one residual evaluation (full vs lite) on the snapshot system, and
verify the Coleman map T(X) = X*((F+const)/const)**(-1/CRRA) is a contraction
from the PF seed (3 sweeps sanity)."""
import os, sys, time, pickle
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, "/home/shared/github/llorracc/fast-time-iteration")
import numpy as np

BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"
with open(BENCH + "/snap_edges.pkl", "rb") as f:
    snap = pickle.load(f)
aG, edges, hb, rb = (snap["aXtraGrid"], snap["edges"], snap["hb"], snap["rb"])
MPCmin, meta = snap["MPCmin"], snap["meta"]
CRRA, DFE = meta["CRRA"], meta["DiscFacEff"]

from hark_fti.consumed_block_core import residual_parts_generic
from HARK.interpolation import LinearInterp
cnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
N = len(hb)
X0 = np.array([np.minimum(MPCmin * (aG + hb[b]), aG) for b in range(N)])
X0 = np.clip(X0, 1e-10, None)
kw = dict(aNrmNow=aG, edges=edges, hNrm=hb, R_own=rb, MPCmin=MPCmin,
          cFuncCnst=cnst, CRRA=CRRA, DiscFacEff=DFE,
          tail_form="powerlaw", tail_Q=None)

for label, wj in (("full", True), ("lite", False)):
    t0 = time.time()
    for _ in range(3):
        p = residual_parts_generic(X0, **kw, want_jac=wj)
    dt = (time.time() - t0) / 3
    print(f"[tresid] {label}: {dt*1000:.0f} ms/eval  (plain sweep = 242 ms)",
          flush=True)

# Coleman map sanity: 3 sweeps from the PF seed
X = X0.copy()
for k in range(3):
    p = residual_parts_generic(X, **kw, want_jac=False)
    if p is None:
        print(f"[tresid] sweep {k}: INFEASIBLE"); break
    T = X * ((p["F"] + p["const"][:, None]) / p["const"][:, None]) ** (-1.0 / CRRA)
    move = float(np.max(np.abs(T - X) / (1.0 + np.abs(X))))
    print(f"[tresid] sweep {k}: rel-move={move:.3e}  min={T.min():.3e}", flush=True)
    X = np.clip(T, 1e-10, None)
print("[tresid] DONE", flush=True)
