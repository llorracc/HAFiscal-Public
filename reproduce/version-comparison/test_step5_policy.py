#!/usr/bin/env python
"""
Test Step 5: Policy simulations with Reduced_Run parametrization.

Runs Simulate() with Reduced_Run and only the Baseline experiment.
Reads the output pickle and reports key metrics. Outputs JSON to stdout.
"""

import json
import os
import sys
import time
import pickle
import tempfile
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

Run_Dict = {
    "Run_Baseline": True,
    "Run_Recession ": False,
    "Run_Check_Recession": False,
    "Run_UB_Ext_Recession": False,
    "Run_TaxCut_Recession": False,
    "Run_Check": False,
    "Run_UB_Ext": False,
    "Run_TaxCut": False,
    "Run_AD ": False,
    "Run_1stRoundAD": False,
    "Run_NonAD": False,
}

figs_dir = tempfile.mkdtemp(prefix="hafiscal_test5_") + "/"
os.makedirs(figs_dir, exist_ok=True)

print(f"Output directory: {figs_dir}", file=sys.stderr)
print("Importing Simulate...", file=sys.stderr)

with suppress_stdout():
    from Simulate import Simulate

print("Running Simulate(Reduced_Run, Baseline only)...", file=sys.stderr)
t0 = time.time()

try:
    with suppress_stdout():
        Simulate(Run_Dict, figs_dir, Parametrization="Reduced_Run")
    elapsed = time.time() - t0
    print(f"Simulation complete in {elapsed:.1f}s", file=sys.stderr)
except Exception as e:
    import traceback
    traceback.print_exc(file=sys.stderr)
    output = {"step": 5, "error": str(e)}
    print(json.dumps(output))
    sys.exit(0)

output = {"step": 5, "parametrization": "Reduced_Run", "time": elapsed}

pickle_files = [f for f in os.listdir(figs_dir) if f.endswith(".csv")]

print(f"Output files: {os.listdir(figs_dir)}", file=sys.stderr)

for pf in sorted(pickle_files):
    full_path = os.path.join(figs_dir, pf)
    if os.path.isdir(full_path):
        continue
    try:
        with open(full_path, "rb") as f:
            data = pickle.load(f)

        if isinstance(data, dict):
            key = pf.replace(".", "_")
            extracted = {}
            for k, v in data.items():
                if isinstance(v, np.ndarray):
                    if v.size <= 100:
                        extracted[k] = json_safe(v)
                    else:
                        extracted[k + "_shape"] = list(v.shape)
                        extracted[k + "_mean"] = json_safe(float(np.mean(v)))
                        extracted[k + "_std"] = json_safe(float(np.std(v)))
                        extracted[k + "_first5"] = json_safe(v.flat[:5])
                elif isinstance(v, (int, float, np.floating, np.integer)):
                    extracted[k] = json_safe(v)
                elif isinstance(v, (list, tuple)) and len(v) <= 50:
                    extracted[k] = json_safe(v)
            output[f"file_{key}"] = extracted
        elif isinstance(data, np.ndarray):
            key = pf.replace(".", "_")
            output[f"file_{key}_shape"] = list(data.shape)
            output[f"file_{key}_mean"] = json_safe(float(np.mean(data)))
            if data.size <= 100:
                output[f"file_{key}"] = json_safe(data)
    except Exception as e:
        output[f"file_{pf}_error"] = str(e)

import shutil
shutil.rmtree(figs_dir, ignore_errors=True)

print(json.dumps(output))
