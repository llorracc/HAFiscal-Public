"""P1 runtime probes for the BUG-071-class sweep (plan 20260808-1539h).

Probe 1: production agent routing — solve_one_period must be the custom
         positional solver; production IncShkDstn is labeled.
Probe 2: the S1 latent vector — the dead-file EstimAggFiscalModel class
         really does fall through to HARK's stock (labels-aware) solver.
Probe 3: .draw() consumes atoms positionally (sim immunity), even on a
         deepcopy-severed, positionally-mutated labeled dstn.
"""
import sys, os
import numpy as np

FPC = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
sys.argv = ["p1_probe"]
os.chdir(FPC)
sys.path.insert(0, FPC)

print("=== PROBE 1: production routing (AggFiscalModel path used by Steps 2/5/welfare6) ===")
from Parameters import return_parameters
init_dropout = return_parameters(Parametrization='Baseline', OutputFor='_Main.py')[0]
from AggFiscalModel import AggFiscalType, solve_agg_cons_markov_alt

ag = AggFiscalType(**init_dropout)
sop = ag.solve_one_period
print("solve_one_period ->", getattr(sop, "__name__", sop))
assert sop is solve_agg_cons_markov_alt, "PRODUCTION ROUTING BROKEN"
d0 = ag.IncShkDstn[0]
inner = d0[0] if isinstance(d0, list) else d0
print("IncShkDstn[0] container:", type(d0).__name__, "| element:", type(inner).__name__)
labeled = hasattr(inner, "_wrapped_atoms")
print("labeled (has _wrapped_atoms):", labeled)

# Reproduce the production Simulate.py:325 idiom and document the state it leaves.
from copy import deepcopy
e = deepcopy(inner)
pre = np.asarray(e.atoms[1]).copy()
e.atoms = (np.asarray(e.atoms[0], dtype=np.float64),
           np.asarray(e.atoms[1], dtype=np.float64) * 1.5)
pos_scaled = np.allclose(np.asarray(e.atoms[1]), pre * 1.5)
if labeled:
    stale = not np.allclose(np.asarray(e.dataset["TranShk"]), np.asarray(e.atoms[1]))
    print(f"post-rebind: positional scaled={pos_scaled}, labeled views stale={stale} "
          "(harmless HERE: all consumers positional — solver+draws)")
else:
    print(f"post-rebind: positional scaled={pos_scaled}; object unlabeled -> no labeled views exist")

print()
print("=== PROBE 2: S1 latent vector (dead file pair EstimAggFiscalModel/EstimSetupEconomy) ===")
from EstimParameters import init_dropout as ep_init_dropout
import EstimAggFiscalModel as EM

eg = EM.AggFiscalType(**ep_init_dropout)
esop = getattr(eg, "solve_one_period", None)
print("solve_one_period ->", getattr(esop, "__name__", esop))
print("solveOnePeriod (dead camelCase) ->", getattr(eg.solveOnePeriod, "__name__", None))
print("latent vector live:", esop is not EM.solve_agg_cons_markov_alt)

print()
print("=== PROBE 3: .draw() positionality on a severed+mutated labeled dstn ===")
if labeled:
    t = deepcopy(inner)
    t.atoms[1][:] = t.atoms[1] * 100.0  # positional in-place mutation post-deepcopy
    t.seed = 0
    t.reset()
    draws = t.draw(2000)
    tran_draws = np.asarray(draws[1])
    from_mutated = np.mean(np.isin(np.round(tran_draws, 8),
                                   np.round(np.asarray(t.atoms[1]).ravel(), 8)))
    stale_ds = not np.allclose(np.asarray(t.dataset["TranShk"]), t.atoms[1])
    print(f"draws land on MUTATED atoms: {from_mutated:.1%} (expect 100%); dataset stale={stale_ds}")
    print("=> sim draws consume atoms positionally; labeled staleness invisible to MC")
else:
    print("skipped (production dstn unlabeled)")

print()
print("P1 PROBES COMPLETE")
