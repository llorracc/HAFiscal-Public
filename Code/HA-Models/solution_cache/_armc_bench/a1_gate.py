"""A1=R2 gate (plan 20260807-0919h): slimmed pc schema (no stored col_lo;
consumers derive max(col_up-1, 0); col_up kept int64 — int32 storage was
REFUTED by the numpy fancy-index intp cast, 83 vs 55 ms/matvec). Gates: X
BITWISE vs the
dict-era flat.npz, wall ~33 s, truth bank unchanged, matvec timing,
RSS-ratchet flatness, and pairs-bytes accounting (measured new layout vs
computed old layout)."""
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
from HARK.interpolation import LinearInterp
cnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))

N = len(hb)
X0 = np.array([np.maximum(MPCmin * (aG + hb[b]), 1e-10) for b in range(N)])
kw = dict(aNrmNow=aG, edges=edges, hNrm=hb, R_own=rb, MPCmin=MPCmin,
          cFuncCnst=cnst, CRRA=CRRA, DiscFacEff=DFE,
          tail_form="powerlaw", tail_Q=None)
p = residual_parts_generic(X0, **kw)


def _pcs(parts):
    for pcs in parts["pairs"].values():
        for pc in (pcs if isinstance(pcs, list) else [pcs]):
            yield pc


new_b = old_b = 0
for pc in _pcs(p):
    n_el = pc["col_up"].size
    dat = sum(pc[k].nbytes for k in ("data_up", "data_lo", "dec_p", "dec_q"))
    new_b += dat + pc["col_up"].nbytes             # col_up only (int64)
    old_b += dat + n_el * 8 * 2                    # int64 col_up + col_lo
    assert "col_lo" not in pc
print(f"[a1] pairs bytes (132-state iterate): new={new_b/1e6:.1f}MB "
      f"old-layout={old_b/1e6:.1f}MB saved={(1-new_b/old_b)*100:.1f}%",
      flush=True)

U = np.random.default_rng(3).standard_normal(X0.shape)
apply_jacobian_generic(U, p)
t0 = time.time()
for _ in range(20):
    apply_jacobian_generic(U, p)
print(f"[a1] matvec: {(time.time()-t0)/20*1000:.1f} ms (pre-A1 ref ~52)",
      flush=True)
del p, U

walls, rss_after = [], []
for rep in (1, 2):
    t0 = time.time()
    X, conts, info = solve_stationary_consumed_blocks(
        aG, edges, hb, rb, MPCmin, CRRA, DFE, inner="gmres",
        tol_delta=1e-9, tol_EE=1e-9, maxit=120, tail_form="powerlaw")
    walls.append(time.time() - t0)
    rss_after.append(rss_gb())
    print(f"[a1] solve#{rep}: iters={info['iters']} conv={info['converged']} "
          f"wall={walls[-1]:.1f}s rss_after={rss_after[-1]:.2f}G", flush=True)

ref = np.load(BENCH + "/flat.npz")
nbad = int(np.count_nonzero(X != ref["X"]))
maxdiff = float(np.max(np.abs(X - ref["X"])))
print(f"[a1] X vs flat.npz: nbad={nbad} maxdiff={maxdiff:.3e} "
      f"{'BITWISE PASS' if nbad == 0 else 'FAIL'}", flush=True)

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
print(f"[a1] truth-bank: max={E.max():.3e} med={np.median(E):.3e} "
      f"(ref raw a0: 2.937e-04 / 2.688e-06)", flush=True)
print(f"[a1] ratchet: solve1={rss_after[0]:.2f}G solve2={rss_after[1]:.2f}G "
      f"delta={rss_after[1]-rss_after[0]:+.2f}G", flush=True)
print("[a1] DONE", flush=True)
