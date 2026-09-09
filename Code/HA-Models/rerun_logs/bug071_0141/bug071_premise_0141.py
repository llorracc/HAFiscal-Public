"""BUG-071 step 0 (Econ-9): reproduce the 0.14.1 aliasing premise. Under HARK 0.14.1: (a) is IncShkDstn[0] a labeled
distribution with an xarray dataset? (b) does deepcopy sever .atoms from .dataset (fresh: shared memory)? (c) after the QE
script's positional rescaling `d.atoms[1] = d.atoms[1]*0.7`, does the dataset (what expected()/the solver reads) change?"""
import numpy as np, copy, HARK, sys
from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType, init_idiosyncratic_shocks
print("HARK", HARK.__version__, "python", sys.version.split()[0])
a = IndShockConsumerType(**init_idiosyncratic_shocks); a.update_income_process()
d0 = a.IncShkDstn[0]
print("(a) type:", type(d0).__name__, "| has dataset:", hasattr(d0, "dataset"), "| atoms shape:", np.asarray(d0.atoms).shape)
def dataset_vals(d):
    ds = getattr(d, "dataset", None)
    if ds is None: return None
    names = list(ds.data_vars); return {n: np.asarray(ds[n].values) for n in names}
fresh = dataset_vals(d0)
print("    fresh: dataset vars", None if fresh is None else list(fresh))
if fresh is not None:
    keys = list(fresh); k1 = keys[1] if len(keys) > 1 else keys[0]
    print("    fresh shares memory (atoms row1 vs dataset var2)?", np.shares_memory(np.asarray(d0.atoms)[1], fresh[k1]))
    d = copy.deepcopy(d0); after = dataset_vals(d)
    print("(b) deepcopy shares memory (atoms row1 vs dataset)?", np.shares_memory(np.asarray(d.atoms)[1], after[k1]))
    before_atoms = np.asarray(d.atoms)[1].copy(); before_ds = after[k1].copy()
    d.atoms[1] = d.atoms[1] * 0.7                      # the QE script's construction (positional rescale after deepcopy)
    now = dataset_vals(d)
    print("(c) after atoms[1]*=0.7: atoms row1 changed:", not np.allclose(np.asarray(d.atoms)[1], before_atoms),
          "| dataset changed:", not np.allclose(now[k1], before_ds))
    # what expected() returns (the solver-facing reduction)
    try:
        e_atoms = float(np.dot(d.pmv, np.asarray(d.atoms)[1])); e_ds = float(d.expected(lambda x: x[k1]))
        print("    E[row1] from atoms:", round(e_atoms, 6), "| from expected() (dataset):", round(e_ds, 6), "| ratio", round(e_ds / e_atoms, 4))
    except Exception as ex:
        print("    expected() failed:", type(ex).__name__, str(ex)[:100])
    # the same on a FRESH (non-deepcopied) object
    f = a.IncShkDstn[0]; fb = dataset_vals(f)[k1].copy(); f.atoms[1] = f.atoms[1] * 0.7
    print("    fresh object after atoms[1]*=0.7: dataset changed:", not np.allclose(dataset_vals(f)[k1], fb))
print("PREMISE PROBE DONE")
