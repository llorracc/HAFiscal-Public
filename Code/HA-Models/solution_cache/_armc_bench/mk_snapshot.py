"""One-time composite-system snapshot for the overnight solver-lab
(2026-08-05 night charge): pickle everything the experiments need so each
probe skips the ~3-min model build. Contents: agent, edges bundle, production
plain solution (1e-6), fine-grid (2x) plain-1e-9 truth solution."""
import faulthandler, os, sys, time, pickle
faulthandler.dump_traceback_later(3600, exit=True)
os.environ["HAFISCAL_USE_SOLUTION_CACHE"] = "0"
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, REPO + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, REPO + "/Code/HA-Models")
os.chdir(REPO + "/Code/HA-Models/FromPandemicCode")
sys.argv = [sys.argv[0]]
import numpy as np
import welfare6_scenario as ws
import solver_accel as sa

BENCH = REPO + "/Code/HA-Models/solution_cache/_armc_bench"
ws._SOLVE_WORKERS = 1
ctx = ws.build_and_solve("HS_Only")
eco = ctx["AggEco"]; eco.switch_shock_type("recession")
ag = eco.agents[0]
ag.update_solution_terminal()
grid_prod = np.asarray(ag.aXtraGrid, float).copy()

edges, hb, rb, MPCmin, meta = sa.build_composite_edges(ag)
with open(BENCH + "/snap_edges.pkl", "wb") as f:
    pickle.dump({"aXtraGrid": grid_prod, "edges": edges, "hb": hb, "rb": rb,
                 "MPCmin": MPCmin, "meta": meta}, f)
print("[snap] edges bundle saved", flush=True)

t0 = time.time()
pl_l, pi = sa.accel_solve_agent(ag, method="plain", tol=None)
print(f"[snap] plain steps={pi['steps']} wall={time.time()-t0:.0f}s", flush=True)
with open(BENCH + "/snap_plain_sol.pkl", "wb") as f:
    pickle.dump(pl_l[0], f)

with open(BENCH + "/snap_agent.pkl", "wb") as f:
    pickle.dump(ag, f)
print("[snap] agent saved", flush=True)

# fine-grid (2x midpoint) 1e-9 truth
mid = 0.5 * (grid_prod[:-1] + grid_prod[1:])
ag.aXtraGrid = np.unique(np.concatenate([grid_prod, mid]))
ag.update_solution_terminal()
t0 = time.time()
tr_l, ti = sa.accel_solve_agent(ag, method="plain", tol=1e-9, max_steps=4000)
print(f"[snap] truth fine({len(ag.aXtraGrid)}pts) steps={ti['steps']} "
      f"wall={time.time()-t0:.0f}s", flush=True)
with open(BENCH + "/snap_truth_sol.pkl", "wb") as f:
    pickle.dump(tr_l[0], f)
print("[snap] DONE", flush=True)
