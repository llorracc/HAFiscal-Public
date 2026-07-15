#!/usr/bin/env python
"""
Test Step 1: Splurge factor estimation.

Evaluates FagerengObjFunc at converged parameters and runs 2 Powell iterations
from the default starting point. Outputs JSON to stdout.

Designed to run inside either hafiscal-014 or hafiscal-017 Docker container
with the appropriate codebase mounted at /workspace.
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
    """Redirect stdout to devnull during HAFiscal function calls."""
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old

workspace = os.environ.get("WORKSPACE", "/workspace")
splurge_dir = os.path.join(workspace, "Code", "HA-Models",
                           "Target_AggMPCX_LiquWealth")
ha_models_dir = os.path.join(workspace, "Code", "HA-Models")

os.chdir(splurge_dir)
if ha_models_dir not in sys.path:
    sys.path.insert(0, ha_models_dir)
if splurge_dir not in sys.path:
    sys.path.insert(0, splurge_dir)

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_utils import json_safe

print("Importing Estimation_BetaNablaSplurge (builds agents)...", file=sys.stderr)
t0 = time.time()
with suppress_stdout():
    import Estimation_BetaNablaSplurge as splurge_mod
print(f"Import complete in {time.time()-t0:.1f}s", file=sys.stderr)

FagerengObjFunc = splurge_mod.FagerengObjFunc

CONVERGED_SPLURGE = 0.24611389063967778
CONVERGED_CENTER  = 0.9675511604783018
CONVERGED_SPREAD  = 0.05780500492624704

DEFAULT_START = [0.24906992981618237, 0.9675474591463475, 0.05782806961924406]

output = {"step": 1}

# --- Test 1a: evaluate objective at converged params (detailed mode) ---
print("Test 1a: evaluating at converged params...", file=sys.stderr)
t0 = time.time()
try:
    with suppress_stdout():
        result_detailed = FagerengObjFunc(
            CONVERGED_SPLURGE, CONVERGED_CENTER, CONVERGED_SPREAD,
            estimation_mode=False,
            target="AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC",
        )
    output["test_1a"] = json_safe(result_detailed)
    output["test_1a_time"] = time.time() - t0
    print(f"  distance = {result_detailed['distance']}", file=sys.stderr)
except Exception as e:
    output["test_1a_error"] = str(e)
    print(f"  ERROR: {e}", file=sys.stderr)

# --- Test 1b: evaluate objective at converged params (scalar mode) ---
print("Test 1b: scalar distance at converged params...", file=sys.stderr)
t0 = time.time()
try:
    with suppress_stdout():
        distance_scalar = FagerengObjFunc(
            CONVERGED_SPLURGE, CONVERGED_CENTER, CONVERGED_SPREAD,
            estimation_mode=True,
            target="AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC",
        )
    output["test_1b"] = {"distance": json_safe(distance_scalar)}
    output["test_1b_time"] = time.time() - t0
    print(f"  distance = {distance_scalar}", file=sys.stderr)
except Exception as e:
    output["test_1b_error"] = str(e)
    print(f"  ERROR: {e}", file=sys.stderr)

# --- Test 1c: evaluate at default starting point ---
print("Test 1c: distance at default start point...", file=sys.stderr)
t0 = time.time()
try:
    with suppress_stdout():
        distance_default = FagerengObjFunc(
            DEFAULT_START[0], DEFAULT_START[1], DEFAULT_START[2],
            estimation_mode=True,
            target="AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC",
        )
    output["test_1c"] = {"distance": json_safe(distance_default)}
    output["test_1c_time"] = time.time() - t0
    print(f"  distance = {distance_default}", file=sys.stderr)
except Exception as e:
    output["test_1c_error"] = str(e)
    print(f"  ERROR: {e}", file=sys.stderr)

# --- Test 1d: 2 Powell iterations from default start ---
print("Test 1d: 2 Powell iterations...", file=sys.stderr)
t0 = time.time()
try:
    from scipy.optimize import minimize as _original_minimize

    eval_log = []

    def logging_obj(x):
        with suppress_stdout():
            val = FagerengObjFunc(
                x[0], x[1], x[2],
                estimation_mode=True,
                target="AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC",
            )
        eval_log.append({"params": json_safe(list(x)), "distance": json_safe(val)})
        return val

    bounds = [(0.0, 0.9), (0.7, 1.1), (0.0, 0.4)]
    with suppress_stdout():
        opt_result = _original_minimize(
            logging_obj, DEFAULT_START, method="Powell",
            bounds=bounds, options={"maxiter": 2},
        )
    output["test_1d"] = {
        "final_params": json_safe(list(opt_result.x)),
        "final_distance": json_safe(opt_result.fun),
        "nfev": int(opt_result.nfev),
        "eval_log": eval_log[:10],
    }
    output["test_1d_time"] = time.time() - t0
    print(f"  final distance = {opt_result.fun}, nfev = {opt_result.nfev}", file=sys.stderr)
except Exception as e:
    output["test_1d_error"] = str(e)
    import traceback
    traceback.print_exc(file=sys.stderr)

print(json.dumps(output))
