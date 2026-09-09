"""P3b: aligned FD-vs-fake-news stats under the discovered convention
J[t,s] = direct_pre[t+1] (end-of-period aggregation lead), at s=10 (from
the stashed run) and a fresh s=30 column."""
import os, sys, time
import numpy as np
from copy import deepcopy

OUT = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench"
d = np.load(os.path.join(OUT, "p3_fd_jacobian_check.npz"))


def aligned_stats(jac_col, pre_path, label):
    T = len(jac_col)
    fd_aligned = np.empty(T)
    fd_aligned[:T - 1] = pre_path[1:]
    fd_aligned[T - 1] = 0.0
    scale = np.max(np.abs(jac_col))
    absd = np.abs(fd_aligned - jac_col)
    imax = int(np.argmax(absd))
    sig = np.abs(jac_col) > 1e-3 * scale
    relsig = np.max(absd[sig] / np.abs(jac_col[sig]))
    print(f"[p3b] {label}: max|diff|={absd.max():.3e} (rel-to-scale "
          f"{absd.max()/scale:.3e} at t={imax}); max rel on entries >1e-3*scale: "
          f"{relsig:.3e}; corr={np.corrcoef(fd_aligned, jac_col)[0,1]:.8f}")
    return fd_aligned


print("=== s=10 (stashed) aligned under J[t,s]=pre[t+1] ===")
aC10 = aligned_stats(d["CJac_col10"], d["v_pre_C"], "s=10 C")
aA10 = aligned_stats(d["AJac_col10"], d["v_pre_A"], "s=10 A")

print("=== s=30 (fresh solve) ===")
FPC = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
sys.argv = ["p3b"]
os.chdir(FPC)
sys.path.insert(0, FPC)
SRC = os.path.join(FPC, "HA-Fiscal-HANK-SAM.py")
text = open(SRC).read()
head = text[: text.index("for e in range(num_educ_types): #education type")]
ns = {"__name__": "hafiscal_hank_setup", "__file__": SRC}
exec(compile(head, SRC, "exec"), ns)
MarkovConsumerType = ns["MarkovConsumerType"]
compute_type_jacobian = ns["compute_type_jacobian"]
bigT = ns["bigT"]
DX = 0.0001
E, DFI, S2 = 0, 3, 30
beta = ns["DiscFacDstns"][E].atoms[0][DFI]
dct = ns["dicts"][E]
IncDist = [ns["IncShkDstn"][E]]
IncDist_dx = [ns["IncShkDstn_transfers_dx"][E]]
agent = ns["BaseTypeList"][E]

CJac, AJac, _, _ = compute_type_jacobian(agent, dct, beta, IncDist, IncDist_dx, "transfers")

agent_SS = deepcopy(agent)
agent_SS.IncShkDstn = deepcopy(IncDist)
agent_SS.DiscFac = beta
agent_SS.compute_steady_state()
D_ss = agent_SS.vec_erg_dstn
c_ss = agent_SS.cPol_Grid.flatten()
a_ss = agent_SS.aPol_Grid.flatten()
C_ss, A_ss = agent_SS.C_ss, agent_SS.A_ss
agent_inc_dx = deepcopy(agent)
agent_inc_dx.DiscFac = beta
agent_inc_dx.IncShkDstn = deepcopy(IncDist_dx)
agent_inc_dx.neutral_measure = True
agent_inc_dx.harmenberg_income_process()

params = deepcopy(dct)
params["T_cycle"] = bigT
params["LivPrb"] = bigT * [agent_SS.LivPrb[0]]
params["PermGroFac"] = bigT * [agent_SS.PermGroFac[0]]
params["PermShkStd"] = bigT * [agent_SS.PermShkStd[0]]
params["TranShkStd"] = bigT * [agent_SS.TranShkStd[0]]
params["Rfree"] = bigT * [agent_SS.Rfree[0]]
params["MrkvArray"] = bigT * agent_SS.MrkvArray
params["DiscFac"] = beta
params["cycles"] = 1
fd = MarkovConsumerType(**params)
fd.dist_pGrid = bigT * [np.array([1])]
fd.solution_terminal = deepcopy(agent_SS.solution[0])
fd.del_from_time_inv("IncShkDstn")
fd.IncShkDstn = (S2 * deepcopy(IncDist) + deepcopy(IncDist_dx)
                 + (bigT - 1 - S2) * deepcopy(IncDist))
fd.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
fd.solve()
fd.IncShkDstn = (S2 * deepcopy(agent_SS.IncShkDstn)
                 + deepcopy(agent_inc_dx.IncShkDstn)
                 + (bigT - 1 - S2) * deepcopy(agent_SS.IncShkDstn))
fd.neutral_measure = True
fd.define_distribution_grid()
fd.calc_transition_matrix()
tran_t = np.array(fd.tran_matrix)
c_t = np.array([fd.cPol_Grid[t].flatten() for t in range(bigT)])
a_t = np.array([fd.aPol_Grid[t].flatten() for t in range(bigT)])
C_pre, A_pre = np.zeros(bigT), np.zeros(bigT)
dd = D_ss
for t in range(bigT):
    C_pre[t] = np.dot(c_t[t], dd)[0]
    A_pre[t] = np.dot(a_t[t], dd)[0]
    dd = np.dot(tran_t[t], dd)
preC30 = (C_pre - C_ss) / DX
preA30 = (A_pre - A_ss) / DX
aC30 = aligned_stats(CJac[:, S2], preC30, "s=30 C")
aA30 = aligned_stats(AJac[:, S2], preA30, "s=30 A")

np.savez(os.path.join(OUT, "p3b_fd_aligned.npz"),
         CJac_col30=CJac[:, S2], AJac_col30=AJac[:, S2],
         preC30=preC30, preA30=preA30)
print("[p3b] DONE")
