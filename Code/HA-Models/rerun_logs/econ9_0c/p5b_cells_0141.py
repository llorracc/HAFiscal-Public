"""P5b (Econ-9 step 0c; HARK 0.14.1, the QE repo's own ConsMarkovModel + the QE HANK script's segments executed
verbatim, COMMITTED QE calibration Results/DiscFacEstim_CRRA_2.0_R_1.01.txt): per (educ, beta) cell, the transfers
Jacobian's top-left SxS block (S=10) exactly as QE compute_type_jacobian would produce it at bigT=300, without
building 300 transition matrices:
  * SS exactly as compute_type_jacobian (compute_steady_state);
  * zeroth column: Zeroth_col_agent solved over the full bigT=300 backward chain (verbatim), then only its first S
    transition matrices built (T_cycle truncated AFTER the solve -- calc_transition_matrix / define_distribution_grid
    index solution[t], IncShkDstn[t], LivPrb[t], ... for t < T_cycle only);
  * rows/cols >= 1: finite-horizon agent over S periods (the last S backward steps from the SS terminal are the same
    for any bigT >= S), its S matrices, and compile_JAC's recursion restricted to the block (J[t,s] references only
    smaller indices).
VALIDATE_CELL: the verbatim compute_type_jacobian is also run at bigT=10 and compared with this construction at
T_zeroth=10 (must agree to machine precision) and at T_zeroth=300 (differs only by the extra backward steps' drift).
Env: CELLS='e:d,e:d,...'; OUT_DIR; S_BLOCK. Read-only w.r.t. both repos; per-cell .npz to OUT_DIR."""
import os, sys, copy, time, resource, numpy as np
QE = "/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode"
OUT = os.environ["OUT_DIR"]; S = int(os.environ.get("S_BLOCK", "10")); BIGT = 300
CELLS = [tuple(int(x) for x in c.split(":")) for c in os.environ["CELLS"].split(",")]
VAL = os.environ.get("VALIDATE_CELL", "")
VAL = tuple(int(x) for x in VAL.split(":")) if VAL else None
os.chdir(QE); sys.path.insert(0, QE); sys.argv = sys.argv[:1]
import matplotlib; matplotlib.use("Agg")
import HARK, numpy, scipy
print(f"HARK {HARK.__version__} numpy {numpy.__version__} scipy {scipy.__version__} python {sys.version.split()[0]}", flush=True)
src = open("HA-Fiscal-HANK-SAM.py").read().split("\n")
ns = {"__file__": os.path.join(QE, "HA-Fiscal-HANK-SAM.py"), "__name__": "hank_probe"}
exec("\n".join(src[:95]), ns)                 # lines 1-95: params (committed calibration), 6-state chain, grids, bigT=300
from ConsMarkovModel import MarkovConsumerType
inits = [ns["init_dropout"], ns["init_highschool"], ns["init_college"]]
agents = []
for init in inits:
    a = MarkovConsumerType(**init); a.cycles = 0; agents.append(a)
ns["BaseTypeList"] = agents; ns["dx"] = 0.0001; ns["MarkovConsumerType"] = MarkovConsumerType
exec("\n".join(src[196:320]), ns)             # lines 197-320: per-type income distributions (verbatim)
exec("\n".join(src[321:615]), ns)             # lines 322-615: compute_type_jacobian + compile_JAC (verbatim)
dx = ns["dx"]; assert ns["bigT"] == 300 and ns["states"] == 6
ALT = os.environ.get("ALT_ESTIM", "")             # 'b,n,GICx;b,n,GICx;b,n,GICx' -> rebuild DiscFacDstns by the QE rule
if ALT:                                            # (Parameters.py:265-272: Uniform(b-n,b+n).discretize(7), cap GICmaxBetas[e]*GICfactor, floor minBeta)
    from HARK.distribution import Uniform
    import EstimParameters as EP
    for e, trip in enumerate(ALT.split(";")):
        b, n, g = (float(x) for x in trip.split(","))
        dfs = Uniform(b - n, b + n).discretize(7); gf = np.exp(g) / (1 + np.exp(g))
        for i in range(7):
            if dfs.atoms[0][i] > EP.GICmaxBetas[e] * gf: dfs.atoms[0][i] = EP.GICmaxBetas[e] * gf
            elif dfs.atoms[0][i] < EP.minBeta: dfs.atoms[0][i] = EP.minBeta
        ns["DiscFacDstns"][e] = dfs
    print("ALT_ESTIM in force (DiscFacDstns rebuilt):", ALT, flush=True)
print("atoms:", {e: np.round(ns["DiscFacDstns"][e].atoms[0], 6).tolist() for e in range(3)}, flush=True)

def fh_params(init, agent_SS, beta, T):      # == compute_type_jacobian's params block
    p = copy.deepcopy(init); p["T_cycle"] = T
    p["LivPrb"] = T * [agent_SS.LivPrb[0]]; p["PermGroFac"] = T * [agent_SS.PermGroFac[0]]
    p["PermShkStd"] = T * [agent_SS.PermShkStd[0]]; p["TranShkStd"] = T * [agent_SS.TranShkStd[0]]
    p["Rfree"] = T * [agent_SS.Rfree]; p["MrkvArray"] = T * agent_SS.MrkvArray
    p["DiscFac"] = beta; p["cycles"] = 1; return p

def block_transfers(e, agent_SS, beta, T_zeroth, S):
    init = inits[e]; agent = agents[e]
    IncDist = [ns["IncShkDstn"][e]]; IncDist_dx = [ns["IncShkDstn_transfers_dx"][e]]
    agent_inc_dx = copy.deepcopy(agent); agent_inc_dx.DiscFac = beta
    agent_inc_dx.IncShkDstn = copy.deepcopy(IncDist_dx); agent_inc_dx.neutral_measure = True
    agent_inc_dx.harmenberg_income_process()
    # finite-horizon agent, S periods (verbatim construction with T_cycle=S)
    p = fh_params(init, agent_SS, beta, S)
    FH = MarkovConsumerType(**p); FH.dist_pGrid = S * [np.array([1])]
    FH.IncShkDstn = S * copy.deepcopy(IncDist); FH.solution_terminal = copy.deepcopy(agent_SS.solution[0])
    FH.del_from_time_inv("IncShkDstn")
    FH.IncShkDstn = (S - 1) * copy.deepcopy(IncDist) + copy.deepcopy(IncDist_dx)
    FH.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
    FH.solve()
    FH.IncShkDstn = (S - 1) * copy.deepcopy(agent_SS.IncShkDstn) + copy.deepcopy(agent_inc_dx.IncShkDstn)
    FH.neutral_measure = True; FH.define_distribution_grid(); FH.calc_transition_matrix()
    assert np.array_equal(FH.dist_mGrid, agent_SS.dist_mGrid)
    # zeroth-column agent over T_zeroth periods (verbatim), matrices for t < S only
    pz = fh_params(init, agent_SS, beta, T_zeroth)
    Z = MarkovConsumerType(**pz); Z.solution_terminal = copy.deepcopy(agent_SS.solution[0])
    Z.IncShkDstn = T_zeroth * copy.deepcopy(IncDist); Z.solve()
    Z.IncShkDstn = copy.deepcopy(agent_inc_dx.IncShkDstn) + T_zeroth * copy.deepcopy(agent_SS.IncShkDstn)
    Z.neutral_measure = True
    Z.T_cycle = S                                  # truncation (see docstring)
    Z.define_distribution_grid(); Z.calc_transition_matrix()
    assert len(Z.tran_matrix) == S and np.array_equal(Z.dist_mGrid, agent_SS.dist_mGrid)
    # compile_JAC restricted to the SxS block, same arithmetic
    D_ss = agent_SS.vec_erg_dstn; c_ss = agent_SS.cPol_Grid.flatten(); a_ss = agent_SS.aPol_Grid.flatten()
    C_ss = agent_SS.C_ss; A_ss = agent_SS.A_ss; tranmat_ss = agent_SS.tran_matrix; N = c_ss.size
    c_t = np.zeros((S + 1, N)); a_t = np.zeros((S + 1, N))
    for t in range(S):
        c_t[t] = FH.cPol_Grid[t].flatten(); a_t[t] = FH.aPol_Grid[t].flatten()
    c_t[S] = c_ss; a_t[S] = a_ss
    tranmat_t = list(FH.tran_matrix) + [tranmat_ss]       # tranmat_t[S] == SS matrix (np.insert(..., T, tranmat_ss))
    exp_c, exp_a = [], []; vc, va = c_ss, a_ss
    for i in range(S):
        exp_c.append(vc); vc = np.dot(tranmat_ss.T, vc); exp_a.append(va); va = np.dot(tranmat_ss.T, va)
    FC = np.zeros((S, S)); FA = np.zeros((S, S))
    for j in range(S):
        FC[0][j] = np.dot(c_t[S - j] - c_ss, D_ss)[0] / dx; FA[0][j] = np.dot(a_t[S - j] - a_ss, D_ss)[0] / dx
        Dcurl = np.dot(tranmat_t[S - j] - tranmat_ss, D_ss) / dx
        for i in range(S - 1):
            FC[i + 1][j] = np.dot(exp_c[i], Dcurl)[0]; FA[i + 1][j] = np.dot(exp_a[i], Dcurl)[0]
    JC = np.zeros((S, S)); JA = np.zeros((S, S))
    for t in range(S):
        for s in range(S):
            if t == 0 or s == 0: JC[t][s] = FC[t][s]; JA[t][s] = FA[t][s]
            else: JC[t][s] = JC[t - 1][s - 1] + FC[t][s]; JA[t][s] = JA[t - 1][s - 1] + FA[t][s]
    dstn = D_ss; Ct = np.zeros(S); At = np.zeros(S)
    for t in range(S):
        dstn = np.dot(Z.tran_matrix[t], dstn); Ct[t] = np.dot(c_ss, dstn)[0]; At[t] = np.dot(a_ss, dstn)[0]
    JC[:, 0] = (Ct - C_ss) / dx; JA[:, 0] = (At - A_ss) / dx
    return JC, JA

t_all = time.time()
for (e, d) in CELLS:
    t0 = time.time(); beta = float(ns["DiscFacDstns"][e].atoms[0][d])
    agent_SS = copy.deepcopy(agents[e]); agent_SS.IncShkDstn = copy.deepcopy([ns["IncShkDstn"][e]]); agent_SS.DiscFac = beta
    agent_SS.compute_steady_state(); t_ss = time.time() - t0
    JC, JA = block_transfers(e, agent_SS, beta, BIGT, S)
    out = dict(e=e, d=d, beta=beta, C_ss=agent_SS.C_ss, A_ss=agent_SS.A_ss, JC=JC, JA=JA)
    line = (f"CELL e={e} d={d} beta={beta:.6f} C_ss={agent_SS.C_ss:.7f} A_ss={agent_SS.A_ss:.6f} | transfers J_C[0,0]={JC[0,0]:.7f} "
            f"J_C[1,0]={JC[1,0]:.7f} J_C[0,1]={JC[0,1]:.7f} J_C[1,1]={JC[1,1]:.7f} J_C[9,9]={JC[9,9]:.7f} J_A[0,0]={JA[0,0]:.7f} "
            f"| SS {t_ss:.0f}s, cell {time.time()-t0:.0f}s")
    if VAL == (e, d):
        JC10, JA10 = block_transfers(e, agent_SS, beta, 10, S)
        ns["bigT"] = 10
        CJv, AJv, Cssv, Assv = ns["compute_type_jacobian"](agents[e], inits[e], beta, [ns["IncShkDstn"][e]],
                                                            [ns["IncShkDstn_transfers_dx"][e]], "transfers")
        ns["bigT"] = 300
        out.update(JC_T10=JC10, JA_T10=JA10, JC_verbatim10=CJv[:S, :S], JA_verbatim10=AJv[:S, :S])
        line += (f"\n  VALIDATION bigT=10: verbatim C_ss={Cssv:.9f} vs mine {agent_SS.C_ss:.9f}; max|JC_mine(T10)-JC_verbatim| = "
                 f"{np.max(np.abs(JC10 - CJv[:S,:S])):.3e}, max|JA| = {np.max(np.abs(JA10 - AJv[:S,:S])):.3e}; "
                 f"zeroth-drift: max|JC(T300)-JC(T10)| = {np.max(np.abs(JC - JC10)):.3e} (col0 {np.max(np.abs(JC[:,0]-JC10[:,0])):.3e}, "
                 f"rest {np.max(np.abs(JC[:,1:]-JC10[:,1:])):.3e}); verbatim J_C[0,0]={CJv[0,0]:.9f} mine(T300)={JC[0,0]:.9f}")
    np.savez(os.path.join(OUT, f"p5b_cell_e{e}_d{d}.npz"), **out)
    print(line, flush=True)
ru = resource.getrusage(resource.RUSAGE_SELF)
print(f"P5b DONE: wall {time.time()-t_all:.0f}s, CPU user {ru.ru_utime:.0f}s sys {ru.ru_stime:.0f}s, maxRSS {ru.ru_maxrss/1e6:.2f} GB", flush=True)
