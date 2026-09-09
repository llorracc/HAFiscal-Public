"""A2c snapshot gate: full-parts timing (python vs numba) + the driver
solve on the 132-state snapshot under kernel="numba" — wall vs the 33.4 s
python reference, X vs flat.npz (equiv-class; the kernel is ~1e-15, so
expect ~1e-9..1e-7 at the fixed point), truth bank, iters."""
import sys, time, pickle
import numpy as np

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, REPO + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, REPO + "/Code/HA-Models")
sys.path.insert(0, "/home/shared/github/llorracc/fast-time-iteration")
BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"

with open(BENCH + "/snap_edges.pkl", "rb") as f:
    snap = pickle.load(f)
aG, edges, hb, rb = snap["aXtraGrid"], snap["edges"], snap["hb"], snap["rb"]
MPCmin, meta = snap["MPCmin"], snap["meta"]
CRRA, DFE = meta["CRRA"], meta["DiscFacEff"]
Cg = np.asarray(meta["Cgrid"], float).reshape(-1)
Cc = len(Cg)

from HARK.interpolation import LinearInterp
from hark_fti.consumed_ati_markov import solve_stationary_consumed_blocks
from hark_fti.consumed_block_core import residual_parts_generic
from hark_fti.consumed_numba_full import make_numba_parts_fn

cnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
N = len(hb)
X0 = np.array([np.maximum(MPCmin * (aG + hb[b]), 1e-10) for b in range(N)])
gkw = dict(aNrmNow=aG, edges=edges, hNrm=hb, R_own=rb, MPCmin=MPCmin,
           cFuncCnst=cnst, CRRA=CRRA, DiscFacEff=DFE,
           tail_form="powerlaw", tail_Q=None)

t0 = time.time(); ref = residual_parts_generic(X0, **gkw)
t_py = time.time() - t0
print(f"[a2c] python FULL parts: {t_py:.3f} s/eval", flush=True)
pf = make_numba_parts_fn(edges, rb, DFE, len(aG))
t0 = time.time(); got = pf(X0, **gkw)
print(f"[a2c] numba first call (incl. compile): {time.time()-t0:.1f} s",
      flush=True)
t0 = time.time()
for _ in range(5):
    pf(X0, **gkw)
t_nb = (time.time() - t0) / 5
devF = float(np.max(np.abs(got["F"] - ref["F"]) / (1.0 + np.abs(ref["F"]))))
print(f"[a2c] numba FULL parts: {t_nb:.3f} s/eval  speedup {t_py/t_nb:.1f}x"
      f"  F dev={devF:.2e}", flush=True)

for tag, kern in (("python", "python"), ("numba", "numba")):
    t0 = time.time()
    X, conts, info = solve_stationary_consumed_blocks(
        aG, edges, hb, rb, MPCmin, CRRA, DFE, inner="gmres",
        tol_delta=1e-9, tol_EE=1e-9, maxit=120, tail_form="powerlaw",
        kernel=kern)
    wall = time.time() - t0
    ref_np = np.load(BENCH + "/flat.npz")
    dX = float(np.max(np.abs(X - ref_np["X"]) / (1.0 + np.abs(ref_np["X"]))))
    print(f"[a2c] solve[{tag}]: iters={info['iters']} "
          f"conv={info['converged']} wall={wall:.1f}s "
          f"X-vs-flat.npz={dX:.2e}", flush=True)
    if tag == "numba":
        with open(BENCH + "/snap_truth_sol.pkl", "rb") as f:
            truth = pickle.load(f)
        m_probe = np.geomspace(0.05, 30.0, 80)
        errs = []
        for b in range(N):
            j, k = b // Cc, b % Cc
            tv = np.asarray(truth.cFunc[j](m_probe, np.full_like(m_probe,
                                                                 Cg[k])))
            nv = np.asarray(conts[b][3](m_probe))
            errs.append(np.abs(nv - tv) / np.maximum(np.abs(tv), 1e-8))
        E = np.concatenate(errs)
        print(f"[a2c] truth-bank[numba]: max={E.max():.3e} "
              f"med={np.median(E):.3e} (48-knot-grid artifact scores: "
              f"1.738e-03 / 2.715e-04)", flush=True)
print("[a2c] DONE", flush=True)
