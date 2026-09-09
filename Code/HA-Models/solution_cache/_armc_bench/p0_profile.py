"""P0 profile gate (plan §C16): where do the seconds go in a cold newton2d
solve vs plain EGM. HS_Only recession, single process, no other timing work
co-running."""
import faulthandler, os, sys, time, cProfile, pstats, io
faulthandler.dump_traceback_later(2400, exit=True)
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
aG = np.asarray(ag.aXtraGrid, float)

# --- plain per-sweep cost ---
t0 = time.time()
pl_l, pi = sa.accel_solve_agent(ag, method="plain", tol=None)
wp = time.time() - t0
print(f"[p0] plain steps={pi['steps']} wall={wp:.1f}s "
      f"per-sweep={wp/max(1,pi['steps'])*1000:.0f}ms", flush=True)

# --- edges build cost ---
t0 = time.time()
edges, hb, rb, MPCmin, meta = sa.build_composite_edges(ag)
print(f"[p0] build_composite_edges wall={time.time()-t0:.2f}s "
      f"blocks={len(hb)}", flush=True)

# --- newton2d core under cProfile (no confirm passes) ---
from hark_fti.consumed_ati_markov import solve_stationary_consumed_blocks
pr = cProfile.Profile()
t0 = time.time()
pr.enable()
X, conts, ninfo = solve_stationary_consumed_blocks(
    aG, edges, hb, rb, MPCmin, meta["CRRA"], meta["DiscFacEff"],
    inner="gmres", tol_delta=1e-9, tol_EE=1e-9, maxit=120,
    tail_form="powerlaw")
pr.disable()
wn = time.time() - t0
print(f"[p0] newton core iters={ninfo['iters']} wall={wn:.1f}s "
      f"per-iter={wn/max(1,ninfo['iters']):.2f}s "
      f"(= {wn/max(1,ninfo['iters'])/(wp/max(1,pi['steps'])):.1f} plain sweeps)",
      flush=True)
pr.dump_stats(BENCH + "/p0_newton_core.pstats")
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(35)
print(s.getvalue(), flush=True)

# --- confirm-pass cost (5 passes, timed separately) ---
from HARK.core import solve_one_cycle
from HARK.ConsumptionSaving.ConsIndShockModel import ConsumerSolution
from HARK.interpolation import (LinearInterpOnInterp1D, MargValueFuncCRRA,
                                ConstantFunction)
S, Cc = meta["S"], meta["Ccount"]
Cgrid = meta["Cgrid"]
cFunc, vPfunc, mNrmMin = [], [], []
for j in range(S):
    slices = [conts[j * Cc + k][3] for k in range(Cc)]
    cf2 = LinearInterpOnInterp1D(slices, Cgrid) if Cc > 1 else slices[0]
    cFunc.append(cf2); vPfunc.append(MargValueFuncCRRA(cf2, meta["CRRA"]))
    mNrmMin.append(ConstantFunction(0.0))
sol = ConsumerSolution(cFunc=cFunc, vPfunc=vPfunc, mNrmMin=mNrmMin)
t0 = time.time()
for i in range(5):
    t1 = time.time()
    sol = solve_one_cycle(ag, sol, None)[0]
    print(f"[p0] confirm pass {i+1}: {time.time()-t1:.2f}s", flush=True)
print(f"[p0] confirm total={time.time()-t0:.1f}s", flush=True)
print("[p0] DONE", flush=True)
