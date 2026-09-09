"""P9: assemble the u'-weighted HANK welfare table (owner commission).

Inputs: the W-extended HA_Fiscal_Jacs.obj (J^W per instrument, aggregate
and by education, + Uprime_ss normalizations) and the GE dump
(equilibrium instrument paths per policy x regime, from
HAFISCAL_HANK_MULT_DUMP).

Object: dW_t = sum_x J^W[x] @ path_x — the first-order utility-flow
deviation (policy term valued at u'(c_ss), composition term at u(c_ss)
levels). Metric:
    W-mult_g(h) = NPV(dW_g, h; R) / (u'_pop_mean * |NPV(cost, 300; R)|)
— "consumption-equivalent at population-average marginal utility per
unit of program cost". At gamma=0 this collapses exactly to the
spending multiplier (identity-checked bitwise at the cell level), so
(W-mult − spending-mult) is a pure u'-targeting/composition premium.
Splurge overlay: headline mirrors the production C-overlay (legacy 0.3,
same instrument list) on J^W; the no-overlay variant is also reported.
"""
import os
import pickle
import sys

import numpy as np

HA = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
B = os.path.join(HA, "solution_cache", "_armc_bench")
R = 1.01
SPLURGE = float(os.environ.get("P9_SPLURGE", "0.3"))
DUMP_FILE = os.environ.get("P9_DUMP", "rb_regime_dump_welfare.obj")
SPL_LIST = ['transfers', 'tau', 'UI_extend', 'UI_rr', 'eta', 'w']
INSTR = ['transfers', 'tau', 'UI_extend', 'UI_rr', 'eta', 'w', 'r']
SHARES = {"dropout": 0.093, "highschool": 0.527, "college": 0.38}
COST_KEY = {"transfers": "transfers", "UI_extensions": "UI_extension_cost",
            "tax_cut": "tax_cost"}

with open(os.path.join(HA, "FromPandemicCode", "HA_Fiscal_Jacs.obj"), 'rb') as f:
    obj = pickle.load(f)
with open(os.path.join(B, DUMP_FILE), 'rb') as f:
    dump = pickle.load(f)
print(f"[p9] dump={DUMP_FILE} splurge={SPLURGE}")

up_pop = float(obj['Uprime_ss_weighted'])
up_educ = obj['Uprime_ss_by_educ']
print(f"u'_pop_mean = {up_pop:.4f};  by educ: " +
      ", ".join(f"{k}={v:.3f} (rel {v/up_pop:.2f})" for k, v in up_educ.items()))


def overlay(Jdict, apply_splurge):
    """Splurge overlay on a W- (or C-) Jacobian dict, mirroring ge.py."""
    if not apply_splurge:
        return Jdict
    out = dict(Jdict)
    periods = Jdict['transfers'].shape[0]
    for ji in SPL_LIST:
        pv = np.sum((Jdict[ji] / R ** np.arange(periods)), axis=0)
        comp = np.diag(pv * R ** np.arange(periods))
        out[ji] = SPLURGE * comp + (1 - SPLURGE) * Jdict[ji]
    return out


def dpath(Jdict, irf):
    """dY_t = sum_x J[x] @ path_x over instruments present in the irf."""
    T = Jdict['transfers'].shape[0]
    out = np.zeros(T)
    for x in INSTR:
        if x in irf:
            p = np.asarray(irf[x])
            out += Jdict[x] @ p
    return out


def npv(x, n):
    x = np.asarray(x)
    return float(np.sum(x[:n] / R ** np.arange(n)))


def tables(apply_splurge, label):
    JW = overlay(obj['W'], apply_splurge)
    JW_educ = {g: overlay(obj['W_by_educ'][g], apply_splurge) for g in SHARES}
    print(f"\n===== W-multipliers ({label}); h in QUARTERS =====")
    print(f"{'policy':>14s} {'regime':>14s} {'W(h=12)':>9s} {'W(h=20)':>9s} "
          f"{'spend(20)':>10s} {'premium':>8s} | {'W_drop':>8s} {'W_hs':>8s} {'W_coll':>8s}")
    for pol in ("transfers", "UI_extensions", "tax_cut"):
        for reg in ("taylor", "fixed_nominal", "fixed_real"):
            irf = dump["irfs"][pol][reg]
            cost = abs(npv(irf[COST_KEY[pol]], 300))
            dW = dpath(JW, irf)
            w12 = npv(dW, 12) / (up_pop * cost)
            w20 = npv(dW, 20) / (up_pop * cost)
            sp20 = abs(npv(irf["C"], 20)) / cost
            educ_vals = []
            for g in ("dropout", "highschool", "college"):
                dWg = dpath(JW_educ[g], irf)
                educ_vals.append(npv(dWg, 20) / (up_pop * cost))
            wtd = sum(SHARES[g] * v for g, v in
                      zip(("dropout", "highschool", "college"), educ_vals))
            flagchk = "" if abs(wtd - w20) < 1e-6 else f"  [DECOMP GAP {wtd - w20:+.2e}]"
            print(f"{pol:>14s} {reg:>14s} {w12:9.3f} {w20:9.3f} {sp20:10.3f} "
                  f"{w20 - sp20:+8.3f} | {educ_vals[0]:8.3f} {educ_vals[1]:8.3f} "
                  f"{educ_vals[2]:8.3f}{flagchk}")


# Path-completeness validation: reconstruct the model's own dC from the
# (splurged) C-Jacobians and the dumped instrument paths — a mismatch
# means a consumed instrument path is missing from the dump.
JC = overlay(obj['C'], True)
print("\n===== C-reconstruction check (validates instrument-path completeness) =====")
for pol in ("transfers", "UI_extensions", "tax_cut"):
    for reg in ("taylor", "fixed_nominal", "fixed_real"):
        irf = dump["irfs"][pol][reg]
        rec = dpath(JC, irf)
        md = float(np.max(np.abs(rec - np.asarray(irf["C"]))))
        rel = md / max(1e-12, float(np.max(np.abs(irf["C"]))))
        print(f"  {pol:>14s} {reg:>14s}  max|dC_rec - dC_model| = {md:.3e} (rel {rel:.1e})")

tables(True, "splurge overlay mirrored, headline")
tables(False, "no splurge overlay, sensitivity")
