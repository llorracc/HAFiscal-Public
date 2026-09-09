"""L3b parity harness: compiled backward pass vs the python solve, on the
real transfers FH agent (e=0, beta mid). Compares (T,S,nD) policy grids."""
import os, sys, time
import numpy as np
from copy import deepcopy

FPC = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
HM = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
sys.argv = ["p4_l3b"]
os.chdir(FPC)
sys.path.insert(0, FPC)
sys.path.insert(0, HM)

SRC = os.path.join(FPC, "HA-Fiscal-HANK-SAM.py")
text = open(SRC).read()
ns = {"__name__": "hank_setup_l3b", "__file__": SRC}
exec(compile(text[: text.index("for e in range(num_educ_types): #education type")], SRC, "exec"), ns)

MarkovConsumerType = ns["MarkovConsumerType"]
bigT = ns["bigT"]
E, DFI = 0, 3
beta = ns["DiscFacDstns"][E].atoms[0][DFI]
IncDist = [ns["IncShkDstn"][E]]
IncDist_dx = [ns["IncShkDstn_transfers_dx"][E]]

base = ns["prepare_type_base"](ns["BaseTypeList"][E], ns["dicts"][E], beta, IncDist)
agent_SS = base["agent_SS"]
params = deepcopy(base["params"])

# --- build + python-solve the transfers FH agent exactly as the per-param path ---
fh = MarkovConsumerType(**params)
fh.dist_pGrid = params["T_cycle"] * [np.array([1])]
fh.solution_terminal = deepcopy(agent_SS.solution[0])
fh.del_from_time_inv("IncShkDstn")
solve_dstn = (params["T_cycle"] - 1) * deepcopy(IncDist) + deepcopy(IncDist_dx)
fh.IncShkDstn = solve_dstn
fh.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
t0 = time.time()
fh.solve()
t_solve = time.time() - t0
print(f"[l3b] python solve {t_solve:.1f}s")

agent_inc_dx = deepcopy(ns["BaseTypeList"][E])
agent_inc_dx.DiscFac = beta
agent_inc_dx.IncShkDstn = deepcopy(IncDist_dx)
agent_inc_dx.neutral_measure = True
agent_inc_dx.harmenberg_income_process()
fh.IncShkDstn = ((params["T_cycle"] - 1) * deepcopy(agent_SS.IncShkDstn)
                 + deepcopy(agent_inc_dx.IncShkDstn))
fh.neutral_measure = True
fh.define_distribution_grid()
fh.calc_transition_matrix()
ref_c = np.asarray(fh.cPol_Grid)   # (T,S,nD)
ref_a = np.asarray(fh.aPol_Grid)

# --- compiled backward pass on the same inputs ---
import step4_backward_kernel as K
t0 = time.time()
out = K.fast_backward(fh, shk_dstn=solve_dstn)
t_first = time.time() - t0
assert out is not None, "fast_backward returned None (structural guard tripped)"
cPol, aPol = out
t0 = time.time()
out2 = K.fast_backward(fh, shk_dstn=solve_dstn)
t_warm = time.time() - t0
print(f"[l3b] kernel first(+compile) {t_first:.1f}s, warm {t_warm:.2f}s vs python {t_solve:.1f}s")

dc = np.abs(cPol - ref_c)
da = np.abs(aPol - ref_a)
rel = dc / (1.0 + np.abs(ref_c))
imax = np.unravel_index(np.argmax(dc), dc.shape)
print(f"[l3b] cPol max|diff|={dc.max():.3e} at (t,s,d)={imax} "
      f"(ref there {ref_c[imax]:.6f}); max rel={rel.max():.3e}")
print(f"[l3b] aPol max|diff|={da.max():.3e}")
print(f"[l3b] bitwise-equal fraction: {np.mean(cPol == ref_c):.4%}")
np.savez(os.path.join("/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench", "p4_l3b_parity.npz"),
         cPol=cPol, ref_c=ref_c, dcmax=dc.max(), damax=da.max())
print("[l3b] VERDICT: " + ("PASS-equivalence" if dc.max() < 1e-12 and da.max() < 1e-12 else "EXAMINE"))
