#!/usr/bin/env python
"""Run the FROZEN GE monolith (HA-Fiscal-HANK-SAM-to-python.py) verbatim via runpy under the CURRENT env and dump
its IRFs + multiplier series in the package engine's HAFISCAL_HANK_MULT_DUMP schema (the monolith has no dump
hook). usage: ge_monolith_dump.py <out.pkl>. Deterministic, so a second execution equals the logged run."""
import os, pickle, runpy, sys
import numpy as np
ROOT = "/Users/ccarroll/GitHub/llorracc/HAFiscal-Latest"
FPC = os.path.join(ROOT, "Code/HA-Models/FromPandemicCode")
GE = os.path.join(FPC, "HA-Fiscal-HANK-SAM-to-python.py")
out = sys.argv[1]
os.chdir(FPC)
for p in (FPC, os.path.dirname(FPC)):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.argv = [GE]
g = runpy.run_path(GE, run_name="__main__")

def grab(irf):
    try:
        keys = list(irf.keys())
    except Exception:
        keys = ["C", "Y", "C_dropout", "C_highschool", "C_college", "transfers", "UI_extension_cost", "tax_cost",
                "tau", "w", "eta", "UI_extend", "UI_rr", "r", "r_ante", "B", "G", "N", "i", "pi", "qb", "theta"]
    rec = {}
    for k in keys:
        try:
            rec[k] = np.asarray(irf[k]).copy()
        except Exception:
            pass
    return rec

d = {
    "engine": "monolith",
    "transfers": {"taylor": np.asarray(g["multipliers_transfers"]).copy(),
                  "fixed_nominal": np.asarray(g["multipliers_transfers_fixed_nominal_rate"]).copy(),
                  "fixed_real": np.asarray(g["multipliers_transfers_fixed_real_rate"]).copy()},
    "UI_extensions": {"taylor": np.asarray(g["multipliers_UI_extend"]).copy(),
                      "fixed_nominal": np.asarray(g["multipliers_UI_extensions_fixed_nominal_rate"]).copy(),
                      "fixed_real": np.asarray(g["multipliers_UI_extensions_fixed_real_rate"]).copy()},
    "tax_cut": {"taylor": np.asarray(g["multipliers_tax_cut"]).copy(),
                "fixed_nominal": np.asarray(g["multipliers_tax_cut_fixed_nominal_rate"]).copy(),
                "fixed_real": np.asarray(g["multipliers_tax_cut_fixed_real_rate"]).copy()},
    "irfs": {"transfers": {"taylor": grab(g["irfs_transfer"]),
                           "fixed_nominal": grab(g["irfs_transfer_fixed_nominal_rate"]),
                           "fixed_real": grab(g["irfs_transfer_fixed_real_rate"])},
             "UI_extensions": {"taylor": grab(g["irfs_UI_extend"]),
                               "fixed_nominal": grab(g["irfs_UI_extend_fixed_nominal_rate"]),
                               "fixed_real": grab(g["irfs_UI_extension_fixed_real_rate"])},
             "tax_cut": {"taylor": grab(g["irfs_tau"]),
                         "fixed_nominal": grab(g["irfs_tau_fixed_nominal_rate"]),
                         "fixed_real": grab(g["irfs_tau_fixed_real_rate"])}},
    "ss": {k: float(g[k]) for k in ("C_ss", "A_ss", "B_ss", "G_ss", "Y_ss", "N_ss", "tau_ss", "qb_ss", "U_ss")
           if k in g},
    "Obj": {k: np.asarray(v).copy() for k, v in g["Obj"].items()},
}
with open(out, "wb") as f:
    pickle.dump(d, f)
print("ge_monolith_dump: wrote", out, "ss", d["ss"])
