#!/usr/bin/env python
"""
Test Step 4: HANK-SAM Jacobians (reduced configuration).

Runs a reduced version of HA-Fiscal-HANK-SAM.py with smaller grids and fewer
time periods. Compares steady-state distribution, UJAC, and consumption policy
from the solver. Outputs JSON to stdout.
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

script_path = os.path.join(pandemic_dir, "HA-Fiscal-HANK-SAM.py")

print("Reading HA-Fiscal-HANK-SAM.py...", file=sys.stderr)
with open(script_path) as f:
    code = f.read()

REDUCED_BIGT = 20
REDUCED_MCOUNT = 50
REDUCED_ACOUNT = 50

code = code.replace("mCount = 200", f"mCount = {REDUCED_MCOUNT}")
code = code.replace("bigT = 300", f"bigT = {REDUCED_BIGT}")
code = code.replace("aCount = 200", f"aCount = {REDUCED_ACOUNT}")

code = code.replace("show_plot()", "pass  # show_plot() suppressed")
code = code.replace("plt.show()", "pass  # plt.show() suppressed")

for pattern in [
    "plt.plot(", "plt.legend(", "plt.xlim(", "plt.ylabel(",
    "plt.xlabel(", "plt.title(", "plt.figure(", "plt.subplot(",
    "plt.savefig(",
]:
    code = code.replace(pattern, f"pass  # {pattern}")

lines = code.split("\n")
filtered = []
skip_multiline_plot = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith("pass  # plt.") or stripped.startswith("pass  # show_plot"):
        filtered.append(line)
        continue
    filtered.append(line)
code = "\n".join(filtered)

if "pickle.dump(" in code:
    code = code.replace("pickle.dump(", "pass  # pickle.dump(")

ns = {"__name__": "__not_main__", "__file__": script_path}

print(f"Executing with bigT={REDUCED_BIGT}, mCount={REDUCED_MCOUNT}, "
      f"aCount={REDUCED_ACOUNT}...", file=sys.stderr)
t0 = time.time()

try:
    with suppress_stdout():
        exec(compile(code, script_path, "exec"), ns)
    elapsed = time.time() - t0
    print(f"Execution complete in {elapsed:.1f}s", file=sys.stderr)
except Exception as e:
    import traceback
    traceback.print_exc(file=sys.stderr)
    output = {"step": 4, "error": str(e)}
    print(json.dumps(output))
    sys.exit(0)

output = {"step": 4, "bigT": REDUCED_BIGT, "mCount": REDUCED_MCOUNT,
          "aCount": REDUCED_ACOUNT, "time": elapsed}

if "ss_dstn" in ns:
    output["ss_dstn"] = json_safe(ns["ss_dstn"])

if "UJAC" in ns:
    ujac = ns["UJAC"]
    output["UJAC_shape"] = list(ujac.shape)
    output["UJAC_col0_state0"] = json_safe(ujac[0, :, 0])
    output["UJAC_norm"] = json_safe(float(np.linalg.norm(ujac)))

if "agent_DO" in ns:
    agent = ns["agent_DO"]
    if hasattr(agent, "solution") and len(agent.solution) > 0:
        sol = agent.solution[0]
        test_m = np.linspace(0.1, 10.0, 20)
        if hasattr(sol, "cFunc"):
            cfuncs = sol.cFunc
            if isinstance(cfuncs, list):
                output["cFunc_state0"] = json_safe([float(cfuncs[0](m)) for m in test_m])
                if len(cfuncs) > 1:
                    output["cFunc_state1"] = json_safe([float(cfuncs[1](m)) for m in test_m])
            else:
                output["cFunc_state0"] = json_safe([float(cfuncs(m)) for m in test_m])

if "N_ss" in ns:
    output["N_ss"] = json_safe(ns["N_ss"])
if "U_ss" in ns:
    output["U_ss"] = json_safe(ns["U_ss"])

print(json.dumps(output))
