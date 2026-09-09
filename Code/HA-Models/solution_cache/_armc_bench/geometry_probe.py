"""Geometry probe (owner Q, 2026-08-05 night): where is the kink, where is
m1, and what exactly does the below-kink chord look like — measured on the
real HS_Only recession object. Answers: why m1 is NOT ~a_min despite
aXtraMin=0.001 (BoroCnstArt=0 model, kinked; m1 = a_min + X(a_min) with
X(a_min) Euler-pinned at kink-level consumption)."""
import faulthandler, os, sys, time
faulthandler.dump_traceback_later(1800, exit=True)
os.environ["HAFISCAL_USE_SOLUTION_CACHE"] = "0"
REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
sys.path.insert(0, REPO + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, REPO + "/Code/HA-Models")
os.chdir(REPO + "/Code/HA-Models/FromPandemicCode")
sys.argv = [sys.argv[0]]
import numpy as np
import welfare6_scenario as ws
import solver_accel as sa

ws._SOLVE_WORKERS = 1
ctx = ws.build_and_solve("HS_Only")
eco = ctx["AggEco"]; eco.switch_shock_type("recession")
ag = eco.agents[0]
ag.update_solution_terminal()
aG = np.asarray(ag.aXtraGrid, float)
print(f"[geo] aXtraGrid[0] (a_min) = {aG[0]:.6g}   BoroCnstArt = "
      f"{getattr(ag, 'BoroCnstArt', None)}", flush=True)

# --- production plain solve (the reference representation) ---
t0 = time.time()
pl_l, pi = sa.accel_solve_agent(ag, method="plain", tol=None)
print(f"[geo] plain steps={pi['steps']} wall={time.time()-t0:.0f}s", flush=True)
sol = pl_l[0]
Cg = np.asarray(ag.Cgrid, float).reshape(-1)
Cc = len(Cg)
kmid = Cc // 2

# --- pre-confirm newton2d (raw chord representation, no EGM repair) ---
from hark_fti.consumed_ati_markov import solve_stationary_consumed_blocks
from HARK.interpolation import LinearInterpOnInterp1D
edges, hb, rb, MPCmin, meta = sa.build_composite_edges(ag)
t0 = time.time()
X, conts, ninfo = solve_stationary_consumed_blocks(
    aG, edges, hb, rb, MPCmin, meta["CRRA"], meta["DiscFacEff"],
    inner="gmres", tol_delta=1e-9, tol_EE=1e-9, maxit=120,
    tail_form="powerlaw")
print(f"[geo] newton iters={ninfo['iters']} conv={ninfo['converged']} "
      f"wall={time.time()-t0:.0f}s", flush=True)

md = np.linspace(0.005, 3.0, 12000)
print("[geo] per micro-state (macro block 0, mid C-knot): "
      "kink m* | m1=a_min+X(a_min) | prod max|c-m|/m on [0.03,0.95m*] | "
      "raw-newton chord dev (median, min..max) on same band | a_min/m1",
      flush=True)
for j in range(6):
    b = j * Cc + kmid
    m1 = aG[0] + X[b, 0]
    cP = np.asarray(sol.cFunc[j](md, np.full_like(md, Cg[kmid])))
    bind = np.abs(cP - md) <= 1e-9 * np.maximum(1.0, md)
    mkink = md[bind][-1] if bind.any() else np.nan
    if not np.isfinite(mkink):   # production not exactly c=m: find crossing
        below = cP < md
        mkink = md[~below][-1] if (~below).any() else np.nan
    band = (md >= 0.03) & (md <= 0.95 * mkink)
    prod_dev = np.max(np.abs(cP[band] - md[band]) / md[band])
    cN = np.asarray(conts[b][3](md))          # raw consumed(a) 1-D slice
    ndev = (md[band] - cN[band]) / md[band]   # + = chord BELOW the 45-line
    print(f"[geo] j={j}: m*={mkink:.4f}  m1={m1:.4f}  X(a_min)={X[b,0]:.4f}"
          f"  prod_band_dev={prod_dev:.2e}  raw_chord_dev="
          f"{np.median(ndev):.3e} ({ndev.min():.3e}..{ndev.max():.3e})"
          f"  a_min/m1={aG[0]/m1:.3e}", flush=True)
print("[geo] DONE", flush=True)
