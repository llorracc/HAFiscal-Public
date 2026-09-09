"""BUG-071 step 0, decisive, through the QE repo's OWN Markov solver under HARK 0.14.1, with the QE HANK script's own
construction executed verbatim (its lines 1-95: parameters + 6-state Markov array; lines 197-307: the deepcopy + positional
rescaling of the per-state income distributions). Compare the dropout type's solve and steady state on
(qe) the script's construction vs (rebuilt) fresh distributions with the same pmv/atoms vs (unscaled) the raw distribution."""
import os, sys, copy, numpy as np
QE = "/home/shared/github/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode"
os.chdir(QE); sys.path.insert(0, QE); sys.argv = sys.argv[:1]
import matplotlib; matplotlib.use("Agg")
import HARK
src = open("HA-Fiscal-HANK-SAM.py").read().split("\n")
ns = {"__file__": os.path.join(QE, "HA-Fiscal-HANK-SAM.py"), "__name__": "hank_probe"}
exec("\n".join(src[:95]), ns)                                   # parameters, returnParameters unpack, 6-state MrkvArray on the init dicts
from ConsMarkovModel import MarkovConsumerType
agent = MarkovConsumerType(**ns["init_dropout"]); agent.cycles = 0
ns["BaseTypeList"] = [agent]; ns["dx"] = 0.0001   # the script sets dx at line 141, outside the exec ranges
exec("\n".join(src[196:307]), ns)                               # the script's per-state construction (deepcopy + atoms[1] *= wage*(1-tau), quasi-HAF states)
qe_list = ns["IncShkDstn"][0]
print("HARK", HARK.__version__, "| states:", len(qe_list), "| type:", type(qe_list[0]).__name__, "| dataset:", hasattr(qe_list[0], "dataset"),
      "| MrkvArray", np.asarray(agent.MrkvArray[0]).shape)
def rebuilt(dk):
    from HARK.distribution import DiscreteDistributionLabeled, DiscreteDistribution
    atoms = np.asarray(dk.atoms).copy(); pmv = np.asarray(dk.pmv).copy()
    return DiscreteDistributionLabeled(pmv=pmv, atoms=atoms, var_names=["PermShk", "TranShk"], seed=0) if hasattr(dk, "dataset") else DiscreteDistribution(pmv=pmv, atoms=atoms, seed=0)
rb_list = [rebuilt(d) for d in qe_list]
d0 = agent.IncShkDstn[0]; un_list = [copy.deepcopy(d0) for _ in qe_list]
k = list(qe_list[0].dataset.data_vars)[1] if hasattr(qe_list[0], "dataset") else None
if k: print("QE construction: dataset stale (TranShk view != atoms row 1)?", not np.allclose(np.asarray(qe_list[0].dataset[k].values), np.asarray(qe_list[0].atoms)[1]),
            "| mean TranShk from atoms", float(np.dot(qe_list[0].pmv, np.asarray(qe_list[0].atoms)[1])), "| from dataset", float(np.dot(qe_list[0].pmv, np.asarray(qe_list[0].dataset[k].values))))
m = np.linspace(0.5, 20, 40)
def solve_with(lst, label):
    a = MarkovConsumerType(**ns["init_dropout"]); a.cycles = 0; a.IncShkDstn = [copy.deepcopy(lst)]; a.solve()
    c = np.array([a.solution[0].cFunc[j](m) for j in range(len(lst))])
    try:
        a.compute_steady_state(); ss = (float(a.C_ss), float(a.A_ss))
    except Exception as ex:
        ss = ("ss failed", type(ex).__name__, str(ex)[:60])
    print(f"  {label:9s} solved; steady state C_ss, A_ss = {ss}")
    return c, ss
c_qe, ss_qe = solve_with(qe_list, "qe"); c_rb, ss_rb = solve_with(rb_list, "rebuilt"); c_un, ss_un = solve_with(un_list, "unscaled")
print("max|c_qe - c_rebuilt| =", float(np.max(np.abs(c_qe - c_rb))), "| max|c_qe - c_unscaled| =", float(np.max(np.abs(c_qe - c_un))))
print("MARKOV PROBE DONE")
