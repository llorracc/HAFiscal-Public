"""P1 gate: does a0=0-in-grid kill the below-kink chord error at the source?
Scores vs the snapshot truth bank: plain / raw-newton a0-off (rebuilt from
flat.npz X) / raw-newton a0-on / full newton2d path at confirm k=1 and k=5."""
import faulthandler, os, sys, time, pickle
faulthandler.dump_traceback_later(2400, exit=True)
os.environ["HAFISCAL_USE_SOLUTION_CACHE"] = "0"
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
NS = len(hb)
with open(BENCH + "/snap_truth_sol.pkl", "rb") as f:
    truth = pickle.load(f)
m_probe = np.geomspace(0.05, 30.0, 80)

def score_blocks(fn_of_b):
    errs = []
    for b in range(NS):
        j, k = b // Cc, b % Cc
        tv = np.asarray(truth.cFunc[j](m_probe, np.full_like(m_probe, Cg[k])))
        nv = np.asarray(fn_of_b(b))
        errs.append(np.abs(nv - tv) / np.maximum(np.abs(tv), 1e-8))
    E = np.concatenate(errs)
    return float(E.max()), float(np.median(E))

def score_2d(sol):
    return score_blocks(lambda b: sol.cFunc[b // Cc](
        m_probe, np.full_like(m_probe, Cg[b % Cc])))

with open(BENCH + "/snap_plain_sol.pkl", "rb") as f:
    plain = pickle.load(f)
mx, md = score_2d(plain)
print(f"[p1] plain(prod 1e-6):            max={mx:.3e} med={md:.3e}", flush=True)

from hark_fti.consumed_block_core import _state_continuation
from hark_fti.consumed_ati_markov import solve_stationary_consumed_blocks
from HARK.interpolation import LinearInterp
cnst = LinearInterp(np.array([0.0, 1.0]), np.array([0.0, 1.0]))

Xoff = np.load(BENCH + "/flat.npz")["X"]
conts_off = [_state_continuation(Xoff[b], aG, hb[b], MPCmin, cnst,
                                 tail_form="powerlaw", tail_Q=None)
             for b in range(NS)]
mx, md = score_blocks(lambda b: conts_off[b][3](m_probe))
print(f"[p1] raw newton a0-OFF (no conf): max={mx:.3e} med={md:.3e}", flush=True)

aG0 = np.insert(aG, 0, 0.0)
t0 = time.time()
X1, conts_on, info = solve_stationary_consumed_blocks(
    aG0, edges, hb, rb, MPCmin, CRRA, DFE, inner="gmres",
    tol_delta=1e-9, tol_EE=1e-9, maxit=120, tail_form="powerlaw")
mx, md = score_blocks(lambda b: conts_on[b][3](m_probe))
print(f"[p1] raw newton a0-ON  (no conf): max={mx:.3e} med={md:.3e} "
      f"iters={info['iters']} conv={info['converged']} "
      f"wall={time.time()-t0:.1f}s", flush=True)
np.savez(BENCH + "/newton_a0.npz", X=X1)

import solver_accel as sa
with open(BENCH + "/snap_agent.pkl", "rb") as f:
    ag = pickle.load(f)
for k in ("1", "5"):
    os.environ["HAFISCAL_NEWTON2D_CONFIRM"] = k
    os.environ["HAFISCAL_NEWTON2D_A0"] = "1"
    if hasattr(ag, "_newton2d_cInterior"):
        del ag._newton2d_cInterior
    t0 = time.time()
    sol_l, ninfo = sa.newton2d_solve_agent(ag)
    mx, md = score_2d(sol_l[0])
    print(f"[p1] full path a0-ON confirm={k}: max={mx:.3e} med={md:.3e} "
          f"iters={ninfo['iters']} wall={time.time()-t0:.1f}s", flush=True)
print("[p1] DONE", flush=True)
