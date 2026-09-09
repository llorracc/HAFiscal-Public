"""P4 (HARK 0.14.1, QE code): steady state of every (educ, beta) cell of the QE HANK household block under
 (a) the published construction (Gamma=1 solve, R transition), (b) Gamma_e solve + R transition (the BUG-073 fix as
 built), (c) Gamma_e solve + R/Gamma_e transition (consistent). One process per beta index D (env PROBE_D).
Prints 'ROW e d variant C_ss A_ss' lines; the aggregator weights them like QE compute_average_aggregates
(weights 0.093/0.527/0.38, /7) and compares with the GE script's hard-coded C_ss_sim / A_ss_sim."""
import os, sys, copy, time, numpy as np
QE = "/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode"
os.chdir(QE); sys.path.insert(0, QE); sys.argv = sys.argv[:1]
import matplotlib; matplotlib.use("Agg")
src = open("HA-Fiscal-HANK-SAM.py").read().split("\n")
ns = {"__file__": os.path.join(QE, "HA-Fiscal-HANK-SAM.py"), "__name__": "hank_probe"}
exec("\n".join(src[:95]), ns)
from ConsMarkovModel import MarkovConsumerType
from EstimParameters import PermGroFac_base_d, PermGroFac_base_h, PermGroFac_base_c
D = int(os.environ.get("PROBE_D", "0"))
inits = [ns["init_dropout"], ns["init_highschool"], ns["init_college"]]
Gs = [PermGroFac_base_d[0], PermGroFac_base_h[0], PermGroFac_base_c[0]]
agents = []
for init in inits:
    a = MarkovConsumerType(**init); a.cycles = 0; agents.append(a)
ns["BaseTypeList"] = agents; ns["dx"] = 0.0001
exec("\n".join(src[196:320]), ns)                    # the QE per-type income distributions, verbatim
def ss(agent, IncDist, beta, gamma_solve, R_tran):
    a = copy.deepcopy(agent); a.IncShkDstn = copy.deepcopy(IncDist); a.DiscFac = beta
    a.PermGroFac = [np.ones(6) * gamma_solve]; a.cycles = 0; a.solve()
    a.Rfree = np.ones(6) * R_tran
    a.neutral_measure = True; a.harmenberg_income_process(); a.define_distribution_grid(); a.calc_transition_matrix(); a.calc_ergodic_dist()
    return (np.dot(a.cPol_Grid.flatten(), a.vec_erg_dstn)[0], np.dot(a.aPol_Grid.flatten(), a.vec_erg_dstn)[0])
t0 = time.time()
for e in range(3):
    beta = float(ns["DiscFacDstns"][e].atoms[0][D]); IncDist = [ns["IncShkDstn"][e]]; G = Gs[e]
    for tag, g, R in (("a", 1.0, 1.01), ("b", G, 1.01), ("c", G, 1.01 / G)):
        C, A = ss(agents[e], IncDist, beta, g, R)
        print(f"ROW {e} {D} {tag} {beta:.6f} {C:.9f} {A:.9f} [{time.time()-t0:.0f}s]", flush=True)
print("P4 DONE")
