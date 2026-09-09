"""By-education incidence under the CURRENT construction (the 2026-09-03 3x3 dump + HA_Fiscal_Jacs.obj):
consumption incidence = NPV(dC_educ, h=20)/NPV(cost, 300q)  (the 2026-08-09 definition);
welfare incidence     = NPV(sum_inst W_by_educ[e][inst] @ dX_inst / U'_ss,e, h=20)/NPV(cost) with per-instrument legs
(consumption-equivalent per unit of program cost). Discount 1.01/q, as in the stage's multiplier."""
import pickle, numpy as np
m = pickle.load(open("Code/HA-Models/rerun_logs/bug120_calibration_20260903/mult_3x3.pkl", "rb"))
J = pickle.load(open("Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj", "rb"))
W, Up = J["W_by_educ"], J["Uprime_ss_by_educ"]
npv = lambda x, n: float(np.sum(np.asarray(x, float)[:n] / 1.01 ** np.arange(n)))
COST = {"transfers": "transfers", "UI_extensions": "UI_extension_cost", "tax_cut": "tax_cost"}
INSTS = ("transfers", "r", "w", "tau", "eta", "UI_extend", "UI_rr", "DiscFac")
for reg in ("taylor", "fixed_real"):
    print(f"\n=== regime: {reg} ===")
    for pol in ("transfers", "UI_extensions", "tax_cut"):
        irf = m["irfs"][pol][reg]; sgn = -1.0 if pol == "tax_cut" else 1.0
        cost = npv(irf[COST[pol]], 300)
        cons = {e: sgn * npv(irf[f"C_{e}"], 20) / cost for e in ("dropout", "highschool", "college")}
        print(f"{pol:14s} consumption incidence h20 (per unit cost): " + "  ".join(f"{e[:4]} {v:+.2f}" for e, v in cons.items()))
        for e in ("dropout", "highschool", "college"):
            legs = {}
            for inst in INSTS:
                if inst in irf and inst in W[e]:
                    dX = np.asarray(irf[inst], float)[:300]
                    legs[inst] = sgn * npv(W[e][inst] @ dX / Up[e], 20) / cost
            tot = sum(legs.values())
            print(f"   welfare {e:10s} total {tot:+.2f}   legs: " + "  ".join(f"{k} {v:+.2f}" for k, v in legs.items() if abs(v) > 0.005))
