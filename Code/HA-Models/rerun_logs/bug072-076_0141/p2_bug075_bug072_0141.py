"""P2 (HARK 0.14.1, the QE repo's own ConsMarkovModel + the QE HANK script's construction executed verbatim):
BUG-075 -- how much does the UNSHOCKED 300-period backward chain drift away from the 'converged' steady state on the
QE calibration's most patient cell (College top beta), and how big is that drift / dx relative to the TRUE
transfers anticipation response F[0,s]?  BUG-072 -- run the QE script's own compute_type_jacobian (bigT reduced to
30 for memory) for DiscFac and transfers: is J[:,0] for DiscFac identically zero, and does the zeroth-column agent's
date-0 policy equal the SS policy (no behavioural response)?  Read-only: nothing written into either repo."""
import os, sys, copy, time, numpy as np
QE = "/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode"
os.chdir(QE); sys.path.insert(0, QE); sys.argv = sys.argv[:1]
import matplotlib; matplotlib.use("Agg")
import HARK
from HARK.core import AgentType
print("HARK", HARK.__version__, "| AgentType default tolerance:", AgentType().tolerance, flush=True)
src = open("HA-Fiscal-HANK-SAM.py").read().split("\n")
ns = {"__file__": os.path.join(QE, "HA-Fiscal-HANK-SAM.py"), "__name__": "hank_probe"}
exec("\n".join(src[:95]), ns)            # lines 1-95: params, 6-state chain, Gamma=1 overwrite, QE grids
from ConsMarkovModel import MarkovConsumerType
E = int(os.environ.get("PROBE_EDU", "2")); D = int(os.environ.get("PROBE_D", "-1"))
init = [ns["init_dropout"], ns["init_highschool"], ns["init_college"]][E]
betas = ns["DiscFacDstns"][E].atoms[0]; beta = float(betas[D])
print(f"cell: educ={E} beta={beta:.4f} (grid {np.round(betas,4).tolist()}) PermGroFac={init['PermGroFac'][0].tolist()}", flush=True)
agent = MarkovConsumerType(**init); agent.cycles = 0
ns["BaseTypeList"] = [agent]; ns["dx"] = 0.0001; ns["MarkovConsumerType"] = MarkovConsumerType
exec("\n".join(src[196:320]), ns)        # lines 197-320: the deepcopy + positional rescaling construction (verbatim)
IncDist = [ns["IncShkDstn"][0]]; IncDist_tr = [ns["IncShkDstn_transfers_dx"][0]]
dx = ns["dx"]; T = 300
# ---- steady state exactly as compute_type_jacobian does it (QE lines 327-330)
t0 = time.time()
agent_SS = copy.deepcopy(agent); agent_SS.IncShkDstn = copy.deepcopy(IncDist); agent_SS.DiscFac = beta
agent_SS.compute_steady_state()
print(f"SS done in {time.time()-t0:.0f}s: C_ss={agent_SS.C_ss:.6f} A_ss={agent_SS.A_ss:.6f} tol={agent_SS.tolerance}", flush=True)
# one extra backward step from the converged solution: the residual iterate distance at termination
one = copy.deepcopy(agent_SS); one.cycles = 1; one.T_cycle = 1
one.solution_terminal = copy.deepcopy(agent_SS.solution[0])
one.IncShkDstn = copy.deepcopy(IncDist); one.LivPrb = [agent_SS.LivPrb[0]]; one.PermGroFac = [agent_SS.PermGroFac[0]]
one.MrkvArray = agent_SS.MrkvArray; one.Rfree = agent_SS.Rfree
mg = agent_SS.dist_mGrid; D_ss = agent_SS.vec_erg_dstn.flatten()
c_ss = agent_SS.cPol_Grid.flatten(); a_ss = agent_SS.aPol_Grid.flatten()
def pol(sol):
    c = np.array([sol.cFunc[m](mg) for m in range(6)]); return c.flatten(), (np.tile(mg, (6, 1)) - c).flatten()
try:
    one.solve(); c1, a1 = pol(one.solution[0])
    print(f"one more backward step from SS: max|dc|={np.max(np.abs(c1-c_ss)):.3e}  aggregate dC={np.dot(c1-c_ss, D_ss):.3e}", flush=True)
except Exception as ex:
    print("one-step residual probe failed:", type(ex).__name__, str(ex)[:120], flush=True)
# ---- finite-horizon params exactly as QE lines 341-355
def fh_params():
    p = copy.deepcopy(init); p["T_cycle"] = T
    p["LivPrb"] = T * [agent_SS.LivPrb[0]]; p["PermGroFac"] = T * [agent_SS.PermGroFac[0]]
    p["PermShkStd"] = T * [agent_SS.PermShkStd[0]]; p["TranShkStd"] = T * [agent_SS.TranShkStd[0]]
    p["Rfree"] = T * [agent_SS.Rfree]; p["MrkvArray"] = T * agent_SS.MrkvArray
    p["DiscFac"] = beta; p["cycles"] = 1; return p
def fh_agent(inc_list):
    p = fh_params(); A = MarkovConsumerType(**p); A.dist_pGrid = T * [np.array([1])]
    A.IncShkDstn = inc_list; A.solution_terminal = copy.deepcopy(agent_SS.solution[0]); return A
t0 = time.time()
ghost = fh_agent(T * copy.deepcopy(IncDist)); ghost.solve()
print(f"unshocked (ghost) 300-period chain solved in {time.time()-t0:.0f}s", flush=True)
t0 = time.time()
shocked = fh_agent((T - 1) * copy.deepcopy(IncDist) + copy.deepcopy(IncDist_tr)); shocked.solve()
print(f"transfers-shocked 300-period chain solved in {time.time()-t0:.0f}s", flush=True)
print("\nBUG-075 drift on the QE construction (F[0,s] = (c_{T-s} - c_ss).D_ss/dx; ghost = unshocked chain):")
print(f"{'s':>4} {'drift dC/dx (ghost-SS)':>24} {'maxgrid|c_ghost-c_ss|':>22} {'F0s shipped (shock-SS)':>24} {'F0s true (shock-ghost)':>24} {'drift/true':>11}")
rows = []
for s in [1, 2, 3, 5, 10, 20, 50, 100, 150, 200, 250, 290, 299]:
    cg, ag = pol(ghost.solution[T - s]); cs, a_s = pol(shocked.solution[T - s])
    drift = np.dot(cg - c_ss, D_ss) / dx; ship = np.dot(cs - c_ss, D_ss) / dx; true = np.dot(cs - cg, D_ss) / dx
    rows.append((s, drift, ship, true))
    print(f"{s:4d} {drift:24.6e} {np.max(np.abs(cg-c_ss)):22.3e} {ship:24.6e} {true:24.6e} {drift/true if true!=0 else float('nan'):11.3f}", flush=True)
# ---- BUG-072: the QE script's own compute_type_jacobian, verbatim, bigT=30 (memory), DiscFac and transfers
ns["bigT"] = 30; ns["states"] = 6
exec("\n".join(src[321:615]), ns)        # lines 322-615: compute_type_jacobian + compile_JAC (verbatim)
ns["dx"] = dx
for param, Idx in (("DiscFac", IncDist), ("transfers", IncDist_tr)):
    t0 = time.time()
    CJ, AJ, Css, Ass = ns["compute_type_jacobian"](agent, init, beta, IncDist, Idx, param)
    print(f"\n[{param}] QE compute_type_jacobian (bigT=30) in {time.time()-t0:.0f}s: max|J_C[:,0]|={np.max(np.abs(CJ[:,0])):.3e} "
          f"J_C[0,0]={CJ[0,0]:.6f} J_C[1,0]={CJ[1,0]:.6f}  J_C[0,1]={CJ[0,1]:.6f} J_C[1,1]={CJ[1,1]:.6f}", flush=True)
# zeroth agent policy vs SS policy: re-run the zeroth construction by hand (QE lines 434-437) for transfers
p = copy.deepcopy(init); p["T_cycle"] = 30; p["LivPrb"] = 30*[agent_SS.LivPrb[0]]; p["PermGroFac"] = 30*[agent_SS.PermGroFac[0]]
p["PermShkStd"] = 30*[agent_SS.PermShkStd[0]]; p["TranShkStd"] = 30*[agent_SS.TranShkStd[0]]; p["Rfree"] = 30*[agent_SS.Rfree]
p["MrkvArray"] = 30*agent_SS.MrkvArray; p["DiscFac"] = beta; p["cycles"] = 1
Z = MarkovConsumerType(**p); Z.solution_terminal = copy.deepcopy(agent_SS.solution[0]); Z.IncShkDstn = 30*copy.deepcopy(IncDist); Z.solve()
cz, _ = pol(Z.solution[0]); cz_last, _ = pol(Z.solution[29])
Z2 = MarkovConsumerType(**p); Z2.solution_terminal = copy.deepcopy(agent_SS.solution[0]); Z2.IncShkDstn = copy.deepcopy(IncDist_tr) + 29*copy.deepcopy(IncDist); Z2.solve()
cz2, _ = pol(Z2.solution[0])
print(f"\nBUG-072 zeroth agent (QE construction, solved at baseline): max|c_zeroth[t=0] - c_ss| = {np.max(np.abs(cz-c_ss)):.3e} "
      f"(pure convergence drift after 30 steps: t=29 {np.max(np.abs(cz_last-c_ss)):.3e}); "
      f"with the transfers dx actually in slot 0 of the SOLVE: max|c - c_zeroth| = {np.max(np.abs(cz2-cz)):.3e}, "
      f"aggregate dC/dx = {np.dot(cz2-cz, D_ss)/dx:.4f}", flush=True)
print("P2 DONE")
