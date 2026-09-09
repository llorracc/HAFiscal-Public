#!/usr/bin/env python
"""Dump what step4.hh_setup.build() hands the Jacobian stage (the constructed HANK agents + the six income-distribution
lists) under the CURRENT env, as JSON, so two envs can be diffed with compare_primitives.py. No solve. usage:
probe_hh_setup.py <out.json>"""
import json, os, sys
import numpy as np
out = sys.argv[1]; sys.argv = sys.argv[:1]
HA = "/Users/ccarroll/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models"
os.chdir(os.path.join(HA, "FromPandemicCode"))
for p in (HA, os.path.join(HA, "FromPandemicCode")):
    if p not in sys.path: sys.path.insert(0, p)
from step4 import hh_setup
ctx = hh_setup.build()

def walk(x, depth=0):
    if depth > 10: return {"__deep__": repr(x)[:60]}
    if hasattr(x, "pmv") and hasattr(x, "atoms"):
        return {"pmv": np.asarray(x.pmv, dtype=float).tolist(), "atoms": np.asarray(x.atoms, dtype=float).tolist()}
    if hasattr(x, "dstns"): return [walk(v, depth + 1) for v in x.dstns]
    if isinstance(x, np.ndarray): return x.tolist() if x.dtype.kind in "fiub" else [repr(v)[:60] for v in x.ravel()]
    if isinstance(x, (list, tuple)): return [walk(v, depth + 1) for v in x]
    if isinstance(x, dict): return {str(k): walk(v, depth + 1) for k, v in x.items()}
    if isinstance(x, (np.floating, np.integer, np.bool_)): return x.item()
    if isinstance(x, (bool, int, float, str)) or x is None: return x
    return {"__type__": type(x).__name__}

d = {}
names = [n for n in dir(ctx) if not n.startswith("_")] if not isinstance(ctx, dict) else list(ctx)
get = (lambda n: ctx[n]) if isinstance(ctx, dict) else (lambda n: getattr(ctx, n))
for n in names:
    v = get(n)
    if callable(v) and not hasattr(v, "IncShkDstn"): continue
    if n == "BaseTypeList":
        d[n] = [{k: walk(getattr(a, k)) for k in ("DiscFac", "CRRA", "Rfree", "LivPrb", "PermGroFac", "MrkvArray", "T_cycle",
                 "cycles", "BoroCnstArt", "aXtraMin", "aXtraMax", "aXtraCount", "aXtraNestFac", "mCount", "mMax", "mMin", "mFac",
                 "tolerance", "IncShkDstn") if hasattr(a, k)} for a in v]
    elif n.startswith("IncShkDstn") or n in ("ss_dstn", "markov_array_ss", "job_find", "job_sep", "EU_prob", "states",
                                              "num_mrkv", "bigT", "mCount", "tau_ss", "wage_ss", "DiscFacDstns", "data_EducShares"):
        d[n] = walk(v)
d["__names__"] = names
json.dump(d, open(out, "w"))
print("probe_hh_setup: wrote", out, "| ctx names:", names)
