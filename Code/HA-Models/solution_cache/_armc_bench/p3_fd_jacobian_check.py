"""P3: FD-validate a fixed-arm Step-4 Jacobian column (plan 20260808-1539h).

Strategy: exec HA-Fiscal-HANK-SAM.py up to (not including) the main loop to
reuse its exact setup (agents, dstns incl. the SHOCK_FIX relabel, params).
Then for one cell (e=dropout, middle beta, param='transfers'):
  1. compute_type_jacobian -> the fake-news CJac/AJac (what the pipeline ships)
  2. an FD "direct dated path" column builder mirroring the script's own
     Zeroth-column recipe, generalized to shock date s:
       - solve a finite-horizon agent with the dx dstn at calendar slot s
       - rebuild dated transition matrices under the neutral measure
       - forward-iterate D from D_ss, aggregate, difference vs SS, /dx
  3. calibrate at s=0 (must reproduce the script's own direct column ->
     validates the harness), then validate the fake-news COMPOSITION at s=10.
"""
import os, sys, time
import numpy as np
from copy import deepcopy

FPC = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
OUT = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench"
sys.argv = ["p3_fd"]
os.chdir(FPC)
sys.path.insert(0, FPC)

SRC = os.path.join(FPC, "HA-Fiscal-HANK-SAM.py")
text = open(SRC).read()
CUT = "for e in range(num_educ_types): #education type"
assert CUT in text, "cut marker not found"
head = text[: text.index(CUT)]
ns = {"__name__": "hafiscal_hank_setup", "__file__": SRC}
t0 = time.time()
exec(compile(head, SRC, "exec"), ns)
print(f"[p3] setup exec done in {time.time()-t0:.1f}s; SHOCK_FIX arm: "
      f"{os.environ.get('HAFISCAL_STEP4_SHOCK_FIX', '(default=1)')}")

MarkovConsumerType = ns["MarkovConsumerType"]
compute_type_jacobian = ns["compute_type_jacobian"]
bigT = ns["bigT"]
states = ns["states"]
DX = 0.0001  # matches compute_type_jacobian's local dx and the _dx dstn construction

E, DFI, PARAM = 0, 3, "transfers"  # dropout, middle discount atom, headline instrument
betas = ns["DiscFacDstns"][E].atoms[0]
beta = betas[DFI]
dct = ns["dicts"][E]
IncDist = [ns["IncShkDstn"][E]]
IncDist_dx = [ns["IncShkDstn_transfers_dx"][E]]
agent = ns["BaseTypeList"][E]
print(f"[p3] cell: educ={E} beta={beta:.6f} param={PARAM} T={bigT} states={states}")

# ---- 1. the pipeline's fake-news Jacobian for this cell ----
t0 = time.time()
CJac, AJac, C_ss_type, A_ss_type = compute_type_jacobian(agent, dct, beta, IncDist, IncDist_dx, PARAM)
print(f"[p3] fake-news CJac done in {time.time()-t0:.1f}s; C_ss={C_ss_type:.6f}")

# ---- 2. shared SS objects (mirrors compute_type_jacobian lines 360-369) ----
agent_SS = deepcopy(agent)
agent_SS.IncShkDstn = deepcopy(IncDist)
agent_SS.DiscFac = beta
agent_SS.compute_steady_state()
D_ss = agent_SS.vec_erg_dstn
c_ss = agent_SS.cPol_Grid.flatten()
a_ss = agent_SS.aPol_Grid.flatten()
C_ss = agent_SS.C_ss
A_ss = agent_SS.A_ss
tranmat_ss = agent_SS.tran_matrix

agent_inc_dx = deepcopy(agent)
agent_inc_dx.DiscFac = beta
agent_inc_dx.IncShkDstn = deepcopy(IncDist_dx)
agent_inc_dx.neutral_measure = True
agent_inc_dx.harmenberg_income_process()


def fd_direct_column(s, solve_dx=True, aggregate_dated=True, mirror_zeroth=False):
    """Direct dated-path column: dx dstn at calendar slot s.

    mirror_zeroth=True reproduces the script's Zeroth_col_agent recipe
    EXACTLY (baseline solve; dx only in the slot-0 transition; c_ss
    aggregation) — the harness-calibration mode.
    Otherwise: solve with dx at slot s (anticipatory dated policies),
    dated transitions, and aggregation with the dated policies.
    """
    params = deepcopy(dct)
    params["T_cycle"] = bigT
    params["LivPrb"] = params["T_cycle"] * [agent_SS.LivPrb[0]]
    params["PermGroFac"] = params["T_cycle"] * [agent_SS.PermGroFac[0]]
    params["PermShkStd"] = params["T_cycle"] * [agent_SS.PermShkStd[0]]
    params["TranShkStd"] = params["T_cycle"] * [agent_SS.TranShkStd[0]]
    params["Rfree"] = params["T_cycle"] * [agent_SS.Rfree[0]]
    params["MrkvArray"] = params["T_cycle"] * agent_SS.MrkvArray
    params["DiscFac"] = beta
    params["cycles"] = 1

    fd = MarkovConsumerType(**params)
    fd.dist_pGrid = params["T_cycle"] * [np.array([1])]
    fd.solution_terminal = deepcopy(agent_SS.solution[0])
    if mirror_zeroth:
        fd.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)
    else:
        fd.del_from_time_inv("IncShkDstn")
        if solve_dx:
            fd.IncShkDstn = (s * deepcopy(IncDist) + deepcopy(IncDist_dx)
                             + (bigT - 1 - s) * deepcopy(IncDist))
        else:
            fd.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)
        fd.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
    fd.solve()

    # transition matrices under the neutral measure (script lines 451-462 / 472-493)
    if mirror_zeroth:
        fd.IncShkDstn = (deepcopy(agent_inc_dx.IncShkDstn)
                         + params["T_cycle"] * deepcopy(agent_SS.IncShkDstn))
    else:
        fd.IncShkDstn = (s * deepcopy(agent_SS.IncShkDstn)
                         + deepcopy(agent_inc_dx.IncShkDstn)
                         + (bigT - 1 - s) * deepcopy(agent_SS.IncShkDstn))
    fd.neutral_measure = True
    fd.define_distribution_grid()
    fd.calc_transition_matrix()

    tran_t = np.array(fd.tran_matrix)
    if aggregate_dated and not mirror_zeroth:
        c_t_dated = np.array([fd.cPol_Grid[t].flatten() for t in range(bigT)])
        a_t_dated = np.array([fd.aPol_Grid[t].flatten() for t in range(bigT)])
    else:
        c_t_dated = np.tile(c_ss, (bigT, 1))
        a_t_dated = np.tile(a_ss, (bigT, 1))
    # both aggregation timings from the same solve:
    #   post = script's Zeroth-column ordering (transition, then aggregate)
    #   pre  = fake-news t=0-row ordering (aggregate on start-of-date dstn)
    C_post, A_post = np.zeros(bigT), np.zeros(bigT)
    C_pre, A_pre = np.zeros(bigT), np.zeros(bigT)
    d = D_ss
    for t in range(bigT):
        C_pre[t] = np.dot(c_t_dated[t], d)[0]
        A_pre[t] = np.dot(a_t_dated[t], d)[0]
        d = np.dot(tran_t[t], d)
        C_post[t] = np.dot(c_t_dated[t], d)[0]
        A_post[t] = np.dot(a_t_dated[t], d)[0]
    return {"pre": ((C_pre - C_ss) / DX, (A_pre - A_ss) / DX),
            "post": ((C_post - C_ss) / DX, (A_post - A_ss) / DX)}


def col_stats(fd_col, jac_col, label):
    denom = max(np.max(np.abs(jac_col)), 1e-12)
    absdiff = np.abs(fd_col - jac_col)
    imax = int(np.argmax(absdiff))
    sig = np.abs(jac_col) > 0.05 * denom
    rel_on_sig = (np.max(absdiff[sig] / np.abs(jac_col)[sig]) if sig.any() else np.nan)
    print(f"[p3] {label}: max|diff|={absdiff.max():.3e} at t={imax} "
          f"(scale {denom:.3e}; rel-to-scale {absdiff.max()/denom:.2%}); "
          f"max rel on significant entries={rel_on_sig:.2%}; "
          f"corr={np.corrcoef(fd_col, jac_col)[0,1]:.6f}")
    return absdiff.max() / denom


# ---- 3. calibration at s=0: EXACT mirror of the script's Zeroth recipe ----
t0 = time.time()
z = fd_direct_column(0, mirror_zeroth=True)
print(f"[p3] FD s=0 mirror done in {time.time()-t0:.1f}s")
r0c = col_stats(z["post"][0], CJac[:, 0], "s=0  C mirror-post (calibration)")
r0a = col_stats(z["post"][1], AJac[:, 0], "s=0  A mirror-post (calibration)")

# ---- 4. validation at s=10: dated-path direct column, both timings ----
t0 = time.time()
v = fd_direct_column(10)
print(f"[p3] FD s=10 dated done in {time.time()-t0:.1f}s")
res = {}
for timing in ("pre", "post"):
    res[("C", timing)] = col_stats(v[timing][0], CJac[:, 10], f"s=10 C dated-{timing}")
    res[("A", timing)] = col_stats(v[timing][1], AJac[:, 10], f"s=10 A dated-{timing}")
best = min(("pre", "post"), key=lambda k: max(res[("C", k)], res[("A", k)]))
r10 = max(res[("C", best)], res[("A", best)])
print(f"[p3] best-matching timing: {best} (max rel-to-scale {r10:.2%})")

np.savez(os.path.join(OUT, "p3_fd_jacobian_check.npz"),
         CJac_col0=CJac[:, 0], CJac_col10=CJac[:, 10],
         AJac_col0=AJac[:, 0], AJac_col10=AJac[:, 10],
         z_post_C=z["post"][0], z_post_A=z["post"][1],
         v_pre_C=v["pre"][0], v_pre_A=v["pre"][1],
         v_post_C=v["post"][0], v_post_A=v["post"][1],
         meta=np.array([E, DFI, bigT, DX], dtype=float))
print("[p3] arrays stashed. VERDICT: "
      + ("PASS" if max(r0c, r0a) < 0.01 and r10 < 0.05 else "EXAMINE"))
