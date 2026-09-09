"""BUG-071 figure-level A/B (R3 evidence): run the HANK-SAM experiments
script against whichever HA_Fiscal_Jacs.obj is in place, then dump every
1-D/2-D float array from its globals to an npz for numeric comparison.

Usage: python hank_experiments_arm.py <tag>
"""
import os
import sys

import numpy as np

TAG = sys.argv[1]
FP = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
SP = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/solution_cache/_armc_bench"
os.chdir(FP)
sys.path.insert(0, FP)
sys.argv = [sys.argv[0]]
os.environ.setdefault("MPLBACKEND", "Agg")

g = {"__name__": "__main__", "__file__": os.path.join(FP, "HA-Fiscal-HANK-SAM-to-python.py")}
src = open(os.path.join(FP, "HA-Fiscal-HANK-SAM-to-python.py")).read()
exec(compile(src, g["__file__"], "exec"), g)

out = {}
for k, v in g.items():
    if isinstance(v, np.ndarray) and v.dtype.kind == "f" and 0 < v.size <= 200000 and v.ndim <= 2:
        out[k] = v
np.savez(os.path.join(SP, f"hank_exp_{TAG}.npz"), **out)
print(f"[hank-exp:{TAG}] dumped {len(out)} arrays", flush=True)
