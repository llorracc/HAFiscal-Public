#!/usr/bin/env python
"""
Test Step 3: Robustness (Splurge=0) discount factor estimation.

Same as Step 2 but with sys.argv setting Splurge=0.
Uses exec with truncated source to avoid triggering full estimation.
"""

import json
import os
import sys
import time
import io
from contextlib import contextmanager

os.environ["MPLBACKEND"] = "Agg"

sys.argv = [sys.argv[0], "1.01", "2.0", "0.7", "0.5", "0"]


@contextmanager
def suppress_stdout():
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old


workspace = os.environ.get("WORKSPACE", "/workspace")
pandemic_dir = os.path.join(workspace, "Code", "HA-Models", "FromPandemicCode")
ha_models_dir = os.path.join(workspace, "Code", "HA-Models")

os.chdir(pandemic_dir)
if ha_models_dir not in sys.path:
    sys.path.insert(0, ha_models_dir)
if pandemic_dir not in sys.path:
    sys.path.insert(0, pandemic_dir)

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_utils import json_safe

# Pinned Splurge=0 robustness estimates; values verified identical to the live
# Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_Splurge0.txt as of
# 2026-06-11 (i.e., unchanged by the BUG-053 re-estimation of 2026-06-09).
CONVERGED_PARAMS_SPLURGE0 = {
    0: {"beta": 0.7001170241385564, "nabla": 0.33919748446677633, "GICx": 5.827531657297868},
    1: {"beta": 0.8991815015222728, "nabla": 0.10577091081769854, "GICx": 5.519580208328268},
    2: {"beta": 0.9774794313046824, "nabla": 0.018523250050409532, "GICx": 5.8103599196932505},
}

SCRIPT_PATH = os.path.join(pandemic_dir, "EstimAggFiscalMAIN.py")

print("Reading EstimAggFiscalMAIN.py...", file=sys.stderr)
with open(SCRIPT_PATH) as f:
    code = f.read()

CUTOFF_MARKERS = [
    "MC_DETERMINISM_TEST",
    "estimateDiscFacs = True",
    "#%% Estimate discount factor",
]

cut_line = None
lines = code.split("\n")
for i, line in enumerate(lines):
    stripped = line.strip()
    for marker in CUTOFF_MARKERS:
        if stripped.startswith(marker) or marker in stripped:
            if i > 500:
                cut_line = i
                break
    if cut_line is not None:
        break

if cut_line is not None:
    print(f"Truncating at line {cut_line}", file=sys.stderr)
    code = "\n".join(lines[:cut_line])

ns = {"__name__": "__not_main__", "__file__": SCRIPT_PATH}

print("Executing truncated EstimAggFiscalMAIN with Splurge=0...", file=sys.stderr)
t0 = time.time()

with suppress_stdout():
    exec(compile(code, SCRIPT_PATH, "exec"), ns)

print(f"Economy setup complete in {time.time()-t0:.1f}s", file=sys.stderr)
print(f"Splurge = {ns.get('Splurge', 'unknown')}", file=sys.stderr)

obj_func = ns.get("betas_obj_func_educ") or ns.get("betasObjFuncEduc")
func_name = "betas_obj_func_educ" if "betas_obj_func_educ" in ns else "betasObjFuncEduc"
stats_func = ns.get("calc_estim_stats") or ns.get("calcEstimStats")

output = {"step": 3, "func_name": func_name, "splurge": json_safe(ns.get("Splurge", 0))}

for educ_type in [0, 1, 2]:
    educ_names = {0: "Dropout", 1: "HighSchool", 2: "College"}
    params = CONVERGED_PARAMS_SPLURGE0[educ_type]
    test_key = f"educ_{educ_type}_{educ_names[educ_type]}"

    print(f"\nTest 3: educ_type={educ_type} ({educ_names[educ_type]})...", file=sys.stderr)

    t0 = time.time()
    try:
        with suppress_stdout():
            distance = obj_func(
                params["beta"], params["nabla"], params["GICx"],
                educ_type=educ_type,
            )
        elapsed = time.time() - t0

        result = {"distance": json_safe(distance), "time": elapsed}

        if stats_func is not None and "AggDemandEconomy" in ns:
            try:
                stats = stats_func(ns["AggDemandEconomy"].agents)
                result["medianLWPI"] = json_safe(list(stats.medianLWPI))
                result["LorenzPts"] = json_safe(list(stats.LorenzPts))
                result["avgLWPI"] = json_safe(list(stats.avgLWPI))
                result["LWoPI"] = json_safe(list(stats.LWoPI))
            except Exception as stats_err:
                result["stats_error"] = str(stats_err)

        output[test_key] = result
        print(f"  distance = {distance}, {elapsed:.1f}s", file=sys.stderr)

    except Exception as e:
        import traceback
        output[f"{test_key}_error"] = str(e)
        traceback.print_exc(file=sys.stderr)

print(json.dumps(output))
