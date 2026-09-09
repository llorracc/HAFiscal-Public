"""H6 probe: is the shipped J[:,0] missing the date-0 behavioral term?

The zeroth-column agent SOLVES AT BASELINE for every instrument and puts
the perturbation only into the slot-0 transition matrices. The TRUE
direct s=0 experiment solves WITH the perturbation at calendar slot 0
(dated policies) and aggregates under the pipeline convention
J[t,0] = direct_pre[t+1]. Instruments: transfers, Rfree, job_find,
DiscFac (cell e=0, beta mid). Kernel default ON is honored throughout.
"""
import os, sys, time
import numpy as np
from copy import deepcopy

FPC = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
OUT = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench"
sys.argv = ["p5_h6"]
os.chdir(FPC)
sys.path.insert(0, FPC)
SRC = os.path.join(FPC, "HA-Fiscal-HANK-SAM.py")
text = open(SRC).read()
ns = {"__name__": "hank_setup_h6", "__file__": SRC}
exec(compile(text[: text.index("for e in range(num_educ_types): #education type")], SRC, "exec"), ns)

MarkovConsumerType = ns["MarkovConsumerType"]
bigT = ns["bigT"]
DX = 0.0001
E, DFI = 0, 3
beta = ns["DiscFacDstns"][E].atoms[0][DFI]
dct = ns["dicts"][E]
IncDist = [ns["IncShkDstn"][E]]
agent = ns["BaseTypeList"][E]
base = ns["prepare_type_base"](agent, dct, beta, IncDist)
agent_SS = base["agent_SS"]
params0 = base["params"]
D_ss = agent_SS.vec_erg_dstn
C_ss, A_ss = agent_SS.C_ss, agent_SS.A_ss


def build_fd_agent():
    params = deepcopy(params0)
    fd = MarkovConsumerType(**params)
    fd.dist_pGrid = params["T_cycle"] * [np.array([1])]
    fd.solution_terminal = deepcopy(agent_SS.solution[0])
    fd.del_from_time_inv("IncShkDstn")
    fd.IncShkDstn = bigT * deepcopy(IncDist)
    fd.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
    return fd, params


def direct_col(perturb):
    """True direct s=0 column: solve WITH the slot-0 perturbation, dated
    transitions, dated-policy pre-convention aggregation."""
    fd, params = build_fd_agent()
    dx_dstn = None
    if perturb == "transfers":
        dx_dstn = [ns["IncShkDstn_transfers_dx"][E]]
        fd.IncShkDstn = deepcopy(dx_dstn) + (bigT - 1) * deepcopy(IncDist)
    elif perturb == "Rfree":
        fd.del_from_time_inv("Rfree")
        fd.add_to_time_vary("Rfree")
        fd.Rfree = [agent.Rfree[0] + DX] + (bigT - 1) * [agent.Rfree[0]]
    elif perturb == "job_find":
        Mrkv_dx = ns["create_matrix_U"](DX).T
        fd.MrkvArray = [Mrkv_dx] + (bigT - 1) * agent.MrkvArray
    elif perturb == "DiscFac":
        fd.del_from_time_inv("DiscFac")
        fd.add_to_time_vary("DiscFac")
        fd.DiscFac = [beta + DX] + (bigT - 1) * [beta]
    fd.solve()
    # neutral-measure dstns for transition building (mirrors the script)
    agent_inc_dx = None
    if perturb == "transfers":
        agent_inc_dx = deepcopy(agent)
        agent_inc_dx.DiscFac = beta
        agent_inc_dx.IncShkDstn = deepcopy(dx_dstn)
        agent_inc_dx.neutral_measure = True
        agent_inc_dx.harmenberg_income_process()
        fd.IncShkDstn = (deepcopy(agent_inc_dx.IncShkDstn)
                         + (bigT - 1) * deepcopy(agent_SS.IncShkDstn))
    else:
        fd.IncShkDstn = bigT * deepcopy(agent_SS.IncShkDstn)
    fd.neutral_measure = True
    fd.define_distribution_grid()
    fd.calc_transition_matrix()
    tran_t = np.array(fd.tran_matrix)
    c_t = np.array([np.asarray(fd.cPol_Grid[t]).flatten() for t in range(bigT)])
    a_t = np.array([np.asarray(fd.aPol_Grid[t]).flatten() for t in range(bigT)])
    C_pre = np.zeros(bigT)
    A_pre = np.zeros(bigT)
    d = D_ss
    for t in range(bigT):
        C_pre[t] = np.dot(c_t[t], d)[0]
        A_pre[t] = np.dot(a_t[t], d)[0]
        d = np.dot(tran_t[t], d)
    dC = (C_pre - C_ss) / DX
    dA = (A_pre - A_ss) / DX
    colC = np.empty(bigT); colC[:bigT-1] = dC[1:]; colC[bigT-1] = 0.0
    colA = np.empty(bigT); colA[:bigT-1] = dA[1:]; colA[bigT-1] = 0.0
    return colC, colA


results = {}
for param in ("transfers", "Rfree", "job_find", "DiscFac"):
    dx_list = ([ns["IncShkDstn_transfers_dx"][E]] if param == "transfers"
               else [ns["IncShkDstn"][E]])
    t0 = time.time()
    CJac, AJac, _, _ = ns["compute_type_jacobian_for_param"](base, IncDist, dx_list, param)
    shippedC, shippedA = CJac[:, 0].copy(), AJac[:, 0].copy()
    trueC, trueA = direct_col(param)
    dmax = float(np.max(np.abs(trueC - shippedC)))
    scale = max(float(np.max(np.abs(CJac))), 1e-12)
    results[param] = (shippedC, trueC, shippedA, trueA)
    print(f"[h6] {param:10s} ({time.time()-t0:.0f}s): shipped J[0:3,0]="
          f"[{shippedC[0]:+.5f} {shippedC[1]:+.5f} {shippedC[2]:+.5f}] "
          f"true=[{trueC[0]:+.5f} {trueC[1]:+.5f} {trueC[2]:+.5f}] "
          f"max|dC|={dmax:.3e} (={dmax/scale:.2%} of J-scale)")

np.savez(os.path.join(OUT, "p5_h6_zeroth.npz"),
         **{f"{k}_{n}": v for k, (sC, tC, sA, tA) in results.items()
            for n, v in (("shippedC", sC), ("trueC", tC), ("shippedA", sA), ("trueA", tA))})
print("[h6] DONE")
