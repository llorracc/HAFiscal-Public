#!/usr/bin/env python
"""
Diagnostic: Capture AggFiscalType boundary inputs in both containers.

This script instruments the economy setup and betas_obj_func_educ evaluation
to capture key intermediate values at 5 checkpoints:

  1. IncShkDstn atoms/probabilities (after construction, before Markov replacement)
  2. MrkvArray transition matrices (after economy setup)
  3. Solver cFunc values at test grid points (after solve)
  4. Initial agent states after initialize_sim (aNrm, pLvl, Mrkv)
  5. First-period shocks after get_shocks (PermShk, TranShk, Mrkv)

Outputs JSON to stdout with full-precision arrays for cross-container comparison.
Runs for education type 0 (Dropout) only to keep runtime manageable.

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
# NOT the current calibration (current = post-BUG-053 re-estimation, 2026-06-09;
# see Code/HA-Models/Results/DiscFacEstim_*.txt).
CONVERGED_PARAMS = {
    0: {"beta": 0.7367769115195405, "nabla": 0.29643835347906666, "GICx": 6.15172479984486},
}

EDUC_TYPE = 0

# ---------------------------------------------------------------------------
# Set up the economy exactly as test_step2_discfac.py does
# ---------------------------------------------------------------------------
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
    print("WARNING: Could not find cutoff marker", file=sys.stderr)

ns = {"__name__": "__not_main__", "__file__": SCRIPT_PATH}

print("Executing truncated EstimAggFiscalMAIN (builds economy)...", file=sys.stderr)
t0 = time.time()

with suppress_stdout():
    exec(compile(code, SCRIPT_PATH, "exec"), ns)

print(f"Economy setup complete in {time.time()-t0:.1f}s", file=sys.stderr)

output = {"step": "2b_inputs", "educ_type": EDUC_TYPE}

# ---------------------------------------------------------------------------
# CHECKPOINT 1: IncShkDstn atoms and probabilities for base types
# The employed income distribution is built by HARK's Lognormal discretization.
# In the economy setup, BaseTypeList[e].IncShkDstn has already been replaced
# with the Markov structure: [[employed, unemp, unemp, unemp_noben]].
# The employed distribution is IncShkDstn[0][0].
# ---------------------------------------------------------------------------
print("Checkpoint 1: IncShkDstn...", file=sys.stderr)
try:
    BaseTypeList = ns["BaseTypeList"]
    bt = BaseTypeList[EDUC_TYPE]

    inc_dstn = bt.IncShkDstn
    # Navigate the Markov structure to get the employed income distribution
    # Both versions: IncShkDstn = [[employed_dstn, unemp_dstn, unemp_dstn, unemp_noben_dstn]]
    if isinstance(inc_dstn[0], list):
        employed_dstn = inc_dstn[0][0]
    else:
        employed_dstn = inc_dstn[0]

    # Extract atoms - handle both 0.14.1 and 0.17.0 formats
    if hasattr(employed_dstn, 'atoms'):
        atoms_raw = employed_dstn.atoms
        if isinstance(atoms_raw, list):
            # 0.14.1 format: atoms = [PermShkVals, TranShkVals]
            ckpt1 = {
                "pmv": employed_dstn.pmv.tolist(),
                "PermShkVals": np.array(atoms_raw[0]).tolist(),
                "TranShkVals": np.array(atoms_raw[1]).tolist(),
            }
        elif isinstance(atoms_raw, np.ndarray):
            if atoms_raw.ndim == 2:
                ckpt1 = {
                    "pmv": employed_dstn.pmv.tolist(),
                    "PermShkVals": atoms_raw[0].tolist(),
                    "TranShkVals": atoms_raw[1].tolist(),
                }
            else:
                ckpt1 = {
                    "pmv": employed_dstn.pmv.tolist(),
                    "atoms_flat": atoms_raw.tolist(),
                }
        else:
            ckpt1 = {"error": f"Unknown atoms type: {type(atoms_raw)}"}
    else:
        ckpt1 = {"error": "No atoms attribute on employed_dstn"}

    # Also capture the number of IncShkDstn items per Markov state
    if isinstance(inc_dstn[0], list):
        ckpt1["n_mrkv_dstns"] = len(inc_dstn[0])

    output["checkpoint1_IncShkDstn"] = ckpt1
    print(f"  PermShk shape: {len(ckpt1.get('PermShkVals', []))}", file=sys.stderr)
    print(f"  TranShk shape: {len(ckpt1.get('TranShkVals', []))}", file=sys.stderr)
except Exception as e:
    import traceback
    output["checkpoint1_IncShkDstn"] = {"error": str(e)}
    traceback.print_exc(file=sys.stderr)

# ---------------------------------------------------------------------------
# CHECKPOINT 2: MrkvArray for the first agent
# ---------------------------------------------------------------------------
print("Checkpoint 2: MrkvArray...", file=sys.stderr)
try:
    AggDemandEconomy = ns["AggDemandEconomy"]
    agents = AggDemandEconomy.agents

    agent0 = agents[0]
    mrkv_arrays = agent0.MrkvArray
    ckpt2 = {}
    for idx, arr in enumerate(mrkv_arrays):
        a = np.array(arr)
        ckpt2[f"MrkvArray_{idx}_shape"] = list(a.shape)
        ckpt2[f"MrkvArray_{idx}"] = a.tolist()

    output["checkpoint2_MrkvArray"] = ckpt2
    print(f"  Number of MrkvArray entries: {len(mrkv_arrays)}", file=sys.stderr)
except Exception as e:
    import traceback
    output["checkpoint2_MrkvArray"] = {"error": str(e)}
    traceback.print_exc(file=sys.stderr)

# ---------------------------------------------------------------------------
# Now run betas_obj_func_educ, but with instrumentation.
# We replicate the function logic manually to capture intermediate states.
# ---------------------------------------------------------------------------
print("\nRunning instrumented betas_obj_func_educ...", file=sys.stderr)

params = CONVERGED_PARAMS[EDUC_TYPE]
beta = params["beta"]
nabla = params["nabla"]
GICx = params["GICx"]

try:
    from copy import deepcopy

    # Get key objects from the namespace
    Uniform_cls = ns.get("Uniform")
    if Uniform_cls is None:
        from HARK.distributions import Uniform as Uniform_cls

    DiscFacCount = ns["DiscFacCount"]
    GICmaxBetas = ns["GICmaxBetas"]
    minBeta = ns["minBeta"]
    data_EducShares = ns["data_EducShares"]
    AgentCountTotal = ns["AgentCountTotal"]
    base_dict = ns["base_dict"]

    # Build discount factor distribution (same as in obj func)
    dfs = Uniform_cls(beta - nabla, beta + nabla).discretize(DiscFacCount)
    for thedf in range(DiscFacCount):
        if dfs.atoms[0][thedf] > GICmaxBetas[EDUC_TYPE] * np.exp(GICx) / (1 + np.exp(GICx)):
            dfs.atoms[0][thedf] = GICmaxBetas[EDUC_TYPE] * (np.exp(GICx) / (1 + np.exp(GICx)))
        elif dfs.atoms[0][thedf] < minBeta:
            dfs.atoms[0][thedf] = minBeta

    TypeListNewEduc = []
    n = 0
    for b in range(DiscFacCount):
        AgentCount = int(np.floor(AgentCountTotal * data_EducShares[EDUC_TYPE] * dfs.pmv[b]))
        ThisType = deepcopy(BaseTypeList[EDUC_TYPE])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = dfs.atoms[0][b]
        ThisType.seed = n
        TypeListNewEduc.append(ThisType)
        n += 1

    TypeListAll = AggDemandEconomy.agents
    TypeListAll[EDUC_TYPE * DiscFacCount:(EDUC_TYPE + 1) * DiscFacCount] = TypeListNewEduc

    base_dict['Agents'] = TypeListAll
    AggDemandEconomy.agents = TypeListAll

    # SOLVE
    print("  Solving economy...", file=sys.stderr)
    t0 = time.time()
    with suppress_stdout():
        AggDemandEconomy.solve()
    print(f"  Solve complete in {time.time()-t0:.1f}s", file=sys.stderr)

    # -----------------------------------------------------------------------
    # CHECKPOINT 3: cFunc values at test grid points
    # -----------------------------------------------------------------------
    print("  Checkpoint 3: cFunc...", file=sys.stderr)
    m_grid = np.linspace(0.1, 20.0, 50)
    c_ratio_grid = np.ones(50)

    ckpt3 = {}
    for agent_idx in range(min(3, len(TypeListNewEduc))):
        agent = TypeListNewEduc[agent_idx]
        sol = agent.solution[0]
        n_states = len(sol.cFunc)
        for j in range(n_states):
            try:
                c_vals = sol.cFunc[j](m_grid, c_ratio_grid)
                key = f"agent{agent_idx}_state{j}"
                ckpt3[key] = np.array(c_vals).tolist()
            except Exception as e:
                ckpt3[f"agent{agent_idx}_state{j}_error"] = str(e)
        ckpt3[f"agent{agent_idx}_DiscFac"] = float(agent.DiscFac)
        ckpt3[f"agent{agent_idx}_n_states"] = n_states

    output["checkpoint3_cFunc"] = ckpt3

    # -----------------------------------------------------------------------
    # RESET + INITIALIZE_SIM
    # -----------------------------------------------------------------------
    print("  Resetting and initializing simulation...", file=sys.stderr)
    with suppress_stdout():
        AggDemandEconomy.reset()
        for agent in AggDemandEconomy.agents:
            agent.initialize_sim()
            agent.AggDemandFac = 1.0
            agent.RfreeNow = 1.0
            agent.CaggNow = 1.0

    # -----------------------------------------------------------------------
    # CHECKPOINT 4: Initial agent state after initialize_sim
    # -----------------------------------------------------------------------
    print("  Checkpoint 4: initial agent states...", file=sys.stderr)
    ckpt4 = {}
    for agent_idx in range(min(3, len(TypeListNewEduc))):
        agent = TypeListNewEduc[agent_idx]
        prefix = f"agent{agent_idx}"
        ckpt4[f"{prefix}_aNrm_first20"] = agent.state_now["aNrm"][:20].tolist()
        ckpt4[f"{prefix}_pLvl_first20"] = agent.state_now["pLvl"][:20].tolist()
        ckpt4[f"{prefix}_Mrkv_first20"] = agent.shocks["Mrkv"][:20].tolist()
        ckpt4[f"{prefix}_aNrm_mean"] = float(np.mean(agent.state_now["aNrm"]))
        ckpt4[f"{prefix}_pLvl_mean"] = float(np.mean(agent.state_now["pLvl"]))
        ckpt4[f"{prefix}_Mrkv_mean"] = float(np.mean(agent.shocks["Mrkv"]))
        ckpt4[f"{prefix}_AgentCount"] = int(agent.AgentCount)
        if hasattr(agent, "MacroMrkvNow"):
            macro = agent.MacroMrkvNow
            ckpt4[f"{prefix}_MacroMrkv_first20"] = (
                macro[:20].tolist() if hasattr(macro, "__len__") else [int(macro)] * 20
            )
        if hasattr(agent, "MicroMrkvNow"):
            micro = agent.MicroMrkvNow
            ckpt4[f"{prefix}_MicroMrkv_first20"] = (
                micro[:20].tolist() if hasattr(micro, "__len__") else [int(micro)] * 20
            )

    output["checkpoint4_init_state"] = ckpt4

    # -----------------------------------------------------------------------
    # RUN make_history + save_state (matches betas_obj_func_educ flow)
    # -----------------------------------------------------------------------
    with suppress_stdout():
        AggDemandEconomy.make_history()
        AggDemandEconomy.save_state()

    # -----------------------------------------------------------------------
    # SECOND SOLVE + INITIALIZE (matches the baseline_commands in obj func)
    # -----------------------------------------------------------------------
    print("  Running baseline_commands (solve, initialize_sim, simulate, save_state)...", file=sys.stderr)
    t0 = time.time()

    # Instead of multi_thread_commands_fake, do it manually for one agent
    # to capture checkpoint 5 after the first get_shocks call
    test_agent = TypeListNewEduc[0]

    with suppress_stdout():
        test_agent.solve()
        test_agent.initialize_sim()

    # -----------------------------------------------------------------------
    # CHECKPOINT 5: First-period shocks
    # Manually call one simulation step to get shocks
    # -----------------------------------------------------------------------
    print("  Checkpoint 5: first-period shocks...", file=sys.stderr)
    ckpt5 = {}

    with suppress_stdout():
        test_agent.get_shocks()

    if "PermShk" in test_agent.shocks:
        ckpt5["PermShk_first20"] = np.array(test_agent.shocks["PermShk"][:20]).tolist()
        ckpt5["PermShk_mean"] = float(np.mean(test_agent.shocks["PermShk"]))
    if "TranShk" in test_agent.shocks:
        ckpt5["TranShk_first20"] = np.array(test_agent.shocks["TranShk"][:20]).tolist()
        ckpt5["TranShk_mean"] = float(np.mean(test_agent.shocks["TranShk"]))
    if "Mrkv" in test_agent.shocks:
        ckpt5["Mrkv_first20"] = np.array(test_agent.shocks["Mrkv"][:20]).tolist()
        ckpt5["Mrkv_mean"] = float(np.mean(test_agent.shocks["Mrkv"]))
    if hasattr(test_agent, "MacroMrkvNow"):
        macro = test_agent.MacroMrkvNow
        ckpt5["MacroMrkv_first20"] = (
            macro[:20].tolist() if hasattr(macro, "__len__") else [int(macro)] * 20
        )
    if hasattr(test_agent, "MicroMrkvNow"):
        micro = test_agent.MicroMrkvNow
        ckpt5["MicroMrkv_first20"] = (
            micro[:20].tolist() if hasattr(micro, "__len__") else [int(micro)] * 20
        )
    if "update_draw" in test_agent.shocks:
        ckpt5["update_draw_first20"] = np.array(test_agent.shocks["update_draw"][:20]).tolist()

    output["checkpoint5_first_shocks"] = ckpt5

    # -----------------------------------------------------------------------
    # Also run the full objective to get the final distance for comparison
    # -----------------------------------------------------------------------
    print("  Running full objective function for distance...", file=sys.stderr)
    obj_func = ns.get("betas_obj_func_educ") or ns.get("betasObjFuncEduc")

    # Need to re-setup since we partially ran things above
    # Re-create the type list from scratch
    TypeListNewEduc2 = []
    n = 0
    for b in range(DiscFacCount):
        AgentCount = int(np.floor(AgentCountTotal * data_EducShares[EDUC_TYPE] * dfs.pmv[b]))
        ThisType = deepcopy(BaseTypeList[EDUC_TYPE])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = dfs.atoms[0][b]
        ThisType.seed = n
        TypeListNewEduc2.append(ThisType)
        n += 1

    TypeListAll2 = AggDemandEconomy.agents[:]
    TypeListAll2[EDUC_TYPE * DiscFacCount:(EDUC_TYPE + 1) * DiscFacCount] = TypeListNewEduc2
    base_dict['Agents'] = TypeListAll2
    AggDemandEconomy.agents = TypeListAll2

    t0 = time.time()
    with suppress_stdout():
        distance = obj_func(beta, nabla, GICx, educ_type=EDUC_TYPE)
    elapsed = time.time() - t0

    output["distance"] = json_safe(distance)
    output["distance_time"] = elapsed
    print(f"  distance = {distance}, time = {elapsed:.1f}s", file=sys.stderr)

except Exception as e:
    import traceback
    output["error"] = str(e)
    traceback.print_exc(file=sys.stderr)

print(json.dumps(output))
