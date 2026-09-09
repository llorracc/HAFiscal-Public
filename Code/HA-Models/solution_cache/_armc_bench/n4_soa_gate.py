"""N4 snapshot gates (SoA plan §3): solve twice in one process on the
132-state snapshot — X vs flat.npz, iters, wall, truth-bank score, and the
RSS ratchet probe (VmRSS after each solve; near-flat delta = ratchet dead).
Also times a single matvec dict-vs-soa."""
import faulthandler, os, sys, time, pickle
faulthandler.dump_traceback_later(1800, exit=True)
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, REPO + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, REPO + "/Code/HA-Models")
sys.path.insert(0, "/home/shared/github/llorracc/fast-time-iteration")
import numpy as np

BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"

def rss_gb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024 ** 2
    return float("nan")

with open(BENCH + "/snap_edges.pkl", "rb") as f:
    snap = pickle.load(f)
aG, edges, hb, rb = (snap["aXtraGrid"], snap["edges"], snap["hb"], snap["rb"])
MPCmin, meta = snap["MPCmin"], snap["meta"]
CRRA, DFE = meta["CRRA"], meta["DiscFacEff"]
Cg = np.asarray(meta["Cgrid"], float).reshape(-1)
Cc = len(Cg)

from hark_fti.consumed_ati_markov import solve_stationary_consumed_blocks
from hark_fti.consumed_block_core import (residual_parts_generic,
                                          apply_jacobian_generic)
from hark_fti.consumed_block_core import _state_continuation
from HARK.interpolation import LinearInterp
cnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))

print(f"[n4] rss at import: {rss_gb():.2f}G", flush=True)

# matvec micro: dict vs soa on the same iterate
N = len(hb)
X0 = np.array([np.maximum(MPCmin * (aG + hb[b]), 1e-10) for b in range(N)])
kw = dict(aNrmNow=aG, edges=edges, hNrm=hb, R_own=rb, MPCmin=MPCmin,
          cFuncCnst=cnst, CRRA=CRRA, DiscFacEff=DFE,
          tail_form="powerlaw", tail_Q=None)
pd_ = residual_parts_generic(X0, pairs_layout="dict", **kw)
ps_ = residual_parts_generic(X0, pairs_layout="soa", **kw)
U = np.random.default_rng(3).standard_normal(X0.shape)
yd = apply_jacobian_generic(U, pd_)
ys = apply_jacobian_generic(U, ps_)
dev = np.max(np.abs(ys - yd)) / (np.max(np.abs(yd)) + 1.0)
for tag, p in (("dict", pd_), ("soa", ps_)):
    t0 = time.time()
    for _ in range(20):
        apply_jacobian_generic(U, p)
    print(f"[n4] matvec[{tag}]: {(time.time()-t0)/20*1000:.1f} ms", flush=True)
print(f"[n4] apply dict-vs-soa dev={dev:.2e}  rss now {rss_gb():.2f}G",
      flush=True)
del pd_, ps_

walls, rss_after = [], []
for rep in (1, 2, 3):
    t0 = time.time()
    X, conts, info = solve_stationary_consumed_blocks(
        aG, edges, hb, rb, MPCmin, CRRA, DFE, inner="gmres",
        tol_delta=1e-9, tol_EE=1e-9, maxit=120, tail_form="powerlaw")
    walls.append(time.time() - t0)
    rss_after.append(rss_gb())
    print(f"[n4] solve#{rep}: iters={info['iters']} conv={info['converged']} "
          f"wall={walls[-1]:.1f}s rss_after={rss_after[-1]:.2f}G", flush=True)

ref = np.load(BENCH + "/flat.npz")
dX = float(np.max(np.abs(X - ref["X"]) / (1.0 + np.abs(ref["X"]))))
print(f"[n4] X vs dict-era flat.npz: {dX:.2e} (gate 1e-8)", flush=True)

with open(BENCH + "/snap_truth_sol.pkl", "rb") as f:
    truth = pickle.load(f)
m_probe = np.geomspace(0.05, 30.0, 80)
errs = []
for b in range(N):
    j, k = b // Cc, b % Cc
    tv = np.asarray(truth.cFunc[j](m_probe, np.full_like(m_probe, Cg[k])))
    nv = np.asarray(conts[b][3](m_probe))
    errs.append(np.abs(nv - tv) / np.maximum(np.abs(tv), 1e-8))
E = np.concatenate(errs)
print(f"[n4] truth-bank: max={E.max():.3e} med={np.median(E):.3e} "
      f"(dict-era raw a0: 2.937e-04 / 2.688e-06)", flush=True)
print(f"[n4] ratchet: rss after solve1={rss_after[0]:.2f}G "
      f"solve2={rss_after[1]:.2f}G delta={rss_after[1]-rss_after[0]:+.2f}G",
      flush=True)
print("[n4] DONE", flush=True)
