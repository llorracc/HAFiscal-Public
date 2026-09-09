"""Snapshot-runner: load the composite-system snapshot and run the consumed
Newton core; save X + iteration trace + wall to <tag>.npz. Usage:
  run_newton_snap.py <tag> [maxit]
The standard fast harness for the overnight solver-lab."""
import faulthandler, os, sys, time, pickle
faulthandler.dump_traceback_later(1200, exit=True)
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, REPO + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, REPO + "/Code/HA-Models")
sys.path.insert(0, "/home/shared/github/llorracc/fast-time-iteration")
import numpy as np

BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"
tag = sys.argv[1]
maxit = int(sys.argv[2]) if len(sys.argv) > 2 else 120

with open(BENCH + "/snap_edges.pkl", "rb") as f:
    snap = pickle.load(f)
aG, edges, hb, rb = (snap["aXtraGrid"], snap["edges"], snap["hb"], snap["rb"])
MPCmin, meta = snap["MPCmin"], snap["meta"]

from hark_fti.consumed_ati_markov import solve_stationary_consumed_blocks
t0 = time.time()
X, conts, info = solve_stationary_consumed_blocks(
    aG, edges, hb, rb, MPCmin, meta["CRRA"], meta["DiscFacEff"],
    inner="gmres", tol_delta=1e-9, tol_EE=1e-9, maxit=maxit,
    tail_form="powerlaw", verbose=True)
wall = time.time() - t0
print(f"[snaprun:{tag}] iters={info['iters']} conv={info['converged']} "
      f"reason={info.get('converged_reason')} fnorm={info.get('fnorm'):.3e} "
      f"wall={wall:.1f}s", flush=True)
np.savez(BENCH + f"/{tag}.npz", X=X, wall=wall, iters=info["iters"],
         fnorm=float(info.get("fnorm", np.nan)))
print(f"[snaprun:{tag}] saved", flush=True)
