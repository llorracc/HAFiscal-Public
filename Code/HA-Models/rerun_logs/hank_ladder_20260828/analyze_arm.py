#!/usr/bin/env python
"""Summarize one ladder arm: IRF peaks (% of C_ss), cumulative consumption multipliers (h=20 and peak) per policy
x regime, the emitted pickle's series, the printed NPV output multipliers, and the steady state. Writes
summary.json next to the inputs. usage: analyze_arm.py <arm_dir>"""
import json, os, pickle, re, sys
import numpy as np
D = sys.argv[1]
dump = pickle.load(open(os.path.join(D, "mult_dump.pkl"), "rb"))
pk = pickle.load(open(os.path.join(D, "multipliers_pickle.obj"), "rb"))
ss = dict(dump.get("ss", {}))
if not ss and os.path.exists(os.path.join(D, "ss_dump.pkl")):
    s = pickle.load(open(os.path.join(D, "ss_dump.pkl"), "rb"))
    ss = {"C_ss": s["household"]["C_ss"], "A_ss": s["household"]["A_ss"], "B_ss": s["bonds"]["B_ss"],
          "G_ss": s["government"]["G_ss"], "Y_ss": s["firms"]["Y_ss"], "N_ss": s["labor_market"]["N_ss"],
          "tau_ss": s["wages_taxes"]["tau_ss"], "qb_ss": s["bonds"]["qb_ss"], "U_ss": s["labor_market"]["U_ss"]}
C_ss = ss.get("C_ss")
log = open(os.path.join(D, "ge.log")).read() if os.path.exists(os.path.join(D, "ge.log")) else ""
if C_ss is None:
    m = re.search(r"C_ss=([0-9.]+)", log)
    C_ss = float(m.group(1)) if m else float("nan")
npv = {}
for line in log.splitlines():
    m = re.match(r"multiplier out of (.+?)\s+([-0-9.eE+]+)\s*$", line.strip())
    if m:
        npv[m.group(1).strip()] = float(m.group(2))
POLS = (("transfers", "transfers"), ("UI_extensions", "UI_extension_cost"), ("tax_cut", "tax_cost"))
REGS = ("taylor", "fixed_nominal", "fixed_real")
summary = {"C_ss": C_ss, "ss": ss, "engine": dump.get("engine", "package"), "npv_output_multipliers": npv,
           "cells": {}, "pickle": {}}
print(f"arm dir: {D}\nengine: {summary['engine']}\nsteady state used by the GE: " +
      ", ".join(f"{k}={v:.6f}" for k, v in ss.items()))
print(f"{'policy':14s} {'regime':13s} {'IRFpeak%':>9s} {'q':>3s} {'cum(h=20)':>10s} {'cum peak':>9s} {'h*':>3s}")
for pol, cost in POLS:
    for reg in REGS:
        irf = dump["irfs"][pol][reg]
        c = np.asarray(irf["C"]); pct = 100.0 * c / C_ss
        q = int(np.argmax(pct[:12])); peak = float(pct[q])
        mult = np.asarray(dump[pol][reg]); h20 = float(mult[19]); hp = int(np.argmax(mult)); mpk = float(mult[hp])
        summary["cells"][f"{pol}/{reg}"] = {"irf_peak_pct": peak, "irf_peak_q": q + 1, "cum_h20": h20,
                                            "cum_peak": mpk, "cum_peak_h": hp + 1,
                                            "irf_pct_12q": pct[:12].tolist(), "cum_20h": mult.tolist()}
        print(f"{pol:14s} {reg:13s} {peak:9.4f} {q+1:3d} {h20:10.4f} {mpk:9.4f} {hp+1:3d}")
print("emitted pickle (multipliers_across_horizon_w_splurge.obj):")
for k in ("transfers", "UI_extensions", "tax_cut"):
    v = np.asarray(pk[k]); summary["pickle"][k] = {"h20": float(v[19]), "peak": float(v.max()),
                                                   "peak_h": int(np.argmax(v)) + 1, "series": v.tolist()}
    which = [reg for reg in REGS if np.allclose(v, dump[k][reg], atol=1e-13)]
    print(f"  {k:14s} h20={v[19]:.4f} peak={v.max():.4f} (h={np.argmax(v)+1}) == regime {which}")
if npv:
    print("printed NPV output multipliers (NPV(Y)/NPV(cost), bigT):")
    for k, v in npv.items():
        print(f"  {k}: {v:.4f}")
json.dump(summary, open(os.path.join(D, "summary.json"), "w"))
print("wrote summary.json")
