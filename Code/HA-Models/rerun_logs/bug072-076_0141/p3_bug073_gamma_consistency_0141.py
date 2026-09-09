"""P3 (HARK 0.14.1, QE code, College top cell): BUG-073's fix restores the PE growth factor Gamma_e in the household
SOLVE, but the fake-news distribution transition (QE ConsMarkovModel.calc_transition_matrix, HARK's
gen_tran_matrix_1D, HARK 0.17's NK toolkit, and the Latest's step4_fast_tranmat kernel) evolves normalized market
resources as m' = R a / psi + theta -- no Gamma. Quantify on the QE construction: steady state under
 (a) Gamma = 1 everywhere (the PUBLISHED construction);
 (b) Gamma_c in the solve, transition at R          (what the revision's BUG-073 fix computes);
 (c) Gamma_c in the solve, transition at R/Gamma_c  (the internally consistent normalized dynamics; Gamma is
     state-independent so dividing bNext by Gamma == using Rfree/Gamma in calc_transition_matrix).
Read-only; nothing written into either repo."""
import os, sys, copy, time, numpy as np
QE = "/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode"
os.chdir(QE); sys.path.insert(0, QE); sys.argv = sys.argv[:1]
import matplotlib; matplotlib.use("Agg")
src = open("HA-Fiscal-HANK-SAM.py").read().split("\n")
ns = {"__file__": os.path.join(QE, "HA-Fiscal-HANK-SAM.py"), "__name__": "hank_probe"}
exec("\n".join(src[:95]), ns)
from ConsMarkovModel import MarkovConsumerType
from EstimParameters import PermGroFac_base_d, PermGroFac_base_h, PermGroFac_base_c
E = int(os.environ.get("PROBE_EDU", "2")); D = int(os.environ.get("PROBE_D", "-1"))
init = [ns["init_dropout"], ns["init_highschool"], ns["init_college"]][E]
G = [PermGroFac_base_d, PermGroFac_base_h, PermGroFac_base_c][E][0]
beta = float(ns["DiscFacDstns"][E].atoms[0][D])
agent = MarkovConsumerType(**init); agent.cycles = 0
ns["BaseTypeList"] = [agent]; ns["dx"] = 0.0001
exec("\n".join(src[196:320]), ns)
IncDist = [ns["IncShkDstn"][0]]
print(f"cell educ={E} beta={beta:.4f} Gamma_e={G:.6f}", flush=True)
def ss(gamma_solve, R_tran):
    a = copy.deepcopy(agent); a.IncShkDstn = copy.deepcopy(IncDist); a.DiscFac = beta
    a.PermGroFac = [np.ones(6) * gamma_solve]
    a.cycles = 0; a.solve()                                   # policies under gamma_solve
    a.Rfree = np.ones(6) * R_tran                              # transition return (Gamma-less code path)
    a.neutral_measure = True; a.harmenberg_income_process(); a.define_distribution_grid(); a.calc_transition_matrix(); a.calc_ergodic_dist()
    A = np.dot(a.aPol_Grid.flatten(), a.vec_erg_dstn)[0]; C = np.dot(a.cPol_Grid.flatten(), a.vec_erg_dstn)[0]
    D_ = a.vec_erg_dstn.flatten(); mg = a.dist_mGrid; n = mg.size
    mass_m = D_.reshape(6, n).sum(axis=0); mean_m = float(np.dot(mass_m, mg))
    return C, A, mean_m
t0 = time.time()
for label, g, R in (("(a) published: Gamma=1 solve, R transition", 1.0, 1.01),
                    ("(b) BUG-073 fix as built: Gamma_e solve, R transition", G, 1.01),
                    ("(c) consistent: Gamma_e solve, R/Gamma_e transition", G, 1.01 / G)):
    C, A, mm = ss(g, R)
    print(f"{label:60s} C_ss={C:.6f} A_ss={A:.6f} mean m={mm:.4f}  [{time.time()-t0:.0f}s]", flush=True)
print("P3 DONE")
