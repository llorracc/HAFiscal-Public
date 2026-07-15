#!/usr/bin/env python
"""
Test Step 2: Discount factor estimation.

Evaluates the discount factor objective function at converged parameters
for all 3 education types. Outputs JSON to stdout.

Designed to run inside either hafiscal-014 or hafiscal-017 Docker container
with the appropriate codebase mounted at /workspace.

Strategy: read EstimAggFiscalMAIN.py as text, truncate after function
definitions (before the estimation loop), and exec to get the economy setup
and function definitions without triggering the full estimation.
"""

import json
import os
import sys
import time
import io
from contextlib import contextmanager

os.environ["MPLBACKEND"] = "Agg"


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

# Pinned 0.14.1-era converged estimates, kept for cross-version comparison.
# NOT the current calibration (current = post-BUG-053 re-estimation, 2026-06-09,
# with theGICfactor=0.9995 and the GIC shave on GPF — see Code/HA-Models/Results/
# DiscFacEstim_*.txt). Do not update these values without re-running the
# 0.14.1 leg of the comparison.
CONVERGED_PARAMS = {
    0: {"beta": 0.7367769115195405, "nabla": 0.29643835347906666, "GICx": 6.15172479984486},
    1: {"beta": 0.9247767556186197, "nabla": 0.07789834940029464, "GICx": 4.191098588731672},
    2: {"beta": 0.9821148354049904, "nabla": 0.014677315032771067, "GICx": 6.277995962148845},
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
    print(f"Truncating at line {cut_line}: {lines[cut_line][:60]}...", file=sys.stderr)
    code = "\n".join(lines[:cut_line])
else:
    print("WARNING: Could not find cutoff marker, running full script!", file=sys.stderr)

ns = {"__name__": "__not_main__", "__file__": SCRIPT_PATH}

print("Executing truncated EstimAggFiscalMAIN (builds economy)...", file=sys.stderr)
t0 = time.time()

with suppress_stdout():
    exec(compile(code, SCRIPT_PATH, "exec"), ns)

print(f"Economy setup complete in {time.time()-t0:.1f}s", file=sys.stderr)

obj_func = ns.get("betas_obj_func_educ") or ns.get("betasObjFuncEduc")
func_name = "betas_obj_func_educ" if "betas_obj_func_educ" in ns else "betasObjFuncEduc"
stats_func = ns.get("calc_estim_stats") or ns.get("calcEstimStats")

if obj_func is None:
    print("ERROR: Could not find objective function!", file=sys.stderr)
    print(json.dumps({"step": 2, "error": "objective function not found"}))
    sys.exit(0)

print(f"Using: {func_name}", file=sys.stderr)

output = {"step": 2, "func_name": func_name}

for educ_type in [0, 1, 2]:
    educ_names = {0: "Dropout", 1: "HighSchool", 2: "College"}
    params = CONVERGED_PARAMS[educ_type]
    test_key = f"educ_{educ_type}_{educ_names[educ_type]}"

    print(f"\nTest 2: educ_type={educ_type} ({educ_names[educ_type]})...", file=sys.stderr)
    print(f"  params: beta={params['beta']:.6f}, nabla={params['nabla']:.6f}, "
          f"GICx={params['GICx']:.4f}", file=sys.stderr)

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
        print(f"  distance = {distance}", file=sys.stderr)
        print(f"  completed in {elapsed:.1f}s", file=sys.stderr)

    except Exception as e:
        import traceback
        output[f"{test_key}_error"] = str(e)
        print(f"  ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

print(json.dumps(output))
