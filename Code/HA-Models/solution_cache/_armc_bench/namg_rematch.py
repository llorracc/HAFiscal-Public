"""NAMG-blocks overnight rematch (owner priority): powerlaw tails ENFORCED,
tolil fix in, per-piece cost split, then two arms:
  N1 inner='sparse' (exact LU)            — expected: stalls (exactness)
  N2 inner='gmres' + Eisenstat-Walker     — the load-bearing-inexactness test
Truth-bank scoring for any arm that survives the honesty gate."""
import faulthandler, os, sys, time, pickle
faulthandler.dump_traceback_later(2700, exit=True)
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

from hark_fti.global_newton_markov import (
    solve_stationary_NAMG_blocks, _build_state_cfuncs,
    _markov_residual_and_jac_edges, _solve_block)
from scipy import sparse

mNow = np.insert(aG, 0, 0.0)
NS, J = len(hb), aG.size
cI0 = np.array([np.minimum(MPCmin * (aG + hb[b]), aG) for b in range(NS)])

# --- micro cost split at the PF seed ---
t0 = time.time(); cF, cU = _build_state_cfuncs(mNow, cI0, MPCmin, np.asarray(hb, float),
                                               tail_form="powerlaw", tail_Q_s=None)
t_cf = time.time() - t0
t0 = time.time(); res = _markov_residual_and_jac_edges(mNow, cI0, cF, cU, edges, CRRA, DFE, want_jac=True)
t_pj = time.time() - t0
F, Jac = res
t0 = time.time(); _ = _markov_residual_and_jac_edges(mNow, cI0, cF, cU, edges, CRRA, DFE, want_jac=False)
t_pf = time.time() - t0
t0 = time.time(); x1 = _solve_block(Jac.tocsc(), (-F).ravel(), "sparse")
t_lu = time.time() - t0
t0 = time.time(); x2 = _solve_block(Jac.tocsc(), (-F).ravel(), "gmres", gmres_rtol=1e-2)
t_gm = time.time() - t0
print(f"[namg] micro: cfuncs={t_cf*1000:.0f}ms  parts+J={t_pj:.2f}s  "
      f"parts-F-only={t_pf:.2f}s  LU={t_lu:.2f}s  ILU+GMRES(1e-2)={t_gm:.2f}s  "
      f"nnz={Jac.nnz}", flush=True)

def score(cFuncs):
    with open(BENCH + "/snap_truth_sol.pkl", "rb") as f:
        truth = pickle.load(f)
    m_probe = np.geomspace(0.05, 30.0, 80)
    errs = []
    for b in range(NS):
        j, k = b // Cc, b % Cc
        tv = np.asarray(truth.cFunc[j](m_probe, np.full_like(m_probe, Cg[k])))
        nv = np.asarray(cFuncs[b](m_probe))
        errs.append(np.abs(nv - tv) / np.maximum(np.abs(tv), 1e-8))
    E = np.concatenate(errs)
    return float(E.max()), float(np.median(E))

for tag, kw, cap in (
    ("N1-sparseLU", dict(inner="sparse"), 25),
    ("N2-gmresEW", dict(inner="gmres", ew_inexact=True), 60),
):
    t0 = time.time()
    cI, cFuncs, info = solve_stationary_NAMG_blocks(
        aG, edges, hb, MPCmin, CRRA, DFE, maxit=cap, verbose=True,
        tail_form="powerlaw", tail_Q_s=None, **kw)
    wall = time.time() - t0
    line = (f"[namg] {tag}: iters={info['iters']} conv={info['converged']} "
            f"fnorm={info['fnorm']:.3e} wall={wall:.1f}s")
    if info["converged"]:
        mx, md = score(cFuncs)
        line += f"  vs-truth max={mx:.3e} median={md:.3e}"
    print(line, flush=True)
print("[namg] DONE", flush=True)
