# filename: do_all.py

# Import the exec function
from builtins import exec
import sys 
import os
from time import time

# Import progress tracking
try:
    from hafiscal_progress import profiler, start_step, complete_step, substep, progress
    PROFILING_ENABLED = True
except ImportError:
    PROFILING_ENABLED = False
    # Provide no-op functions if profiling module not available
    def start_step(*args, **kwargs): pass
    def complete_step(*args, **kwargs): pass
    def substep(*args, **kwargs): pass
    def progress(*args, **kwargs): pass
    class DummyProfiler:
        def sample_memory(self, *args): pass
    profiler = DummyProfiler()

# Control panel.
# Each step can be opted out via env var HAFISCAL_RUN_STEP_{1,2,3,4,5}=false.
# Defaults preserve the historical behaviour: steps 1, 2, 4, 5 on; step 3 off.
def _env_run(var, default):
    v = os.environ.get(var)
    if v is None:
        return default
    return v.lower() in ('true', '1', 'yes')

run_step_1 = _env_run('HAFISCAL_RUN_STEP_1', True)
run_step_2 = _env_run('HAFISCAL_RUN_STEP_2', True)
# Step 3 produces robustness results in the Online appendix; off by default.
run_step_3 = _env_run('HAFISCAL_RUN_STEP_3', False)
run_step_4 = _env_run('HAFISCAL_RUN_STEP_4', True)
run_step_5 = _env_run('HAFISCAL_RUN_STEP_5', True)
# Step 5b (MC welfare-6) can be skipped independently of Step 5a (TM multipliers).
# Skipping 5b is the qe_fidelity_fast pattern: multipliers only, no welfare.
run_step_5b = _env_run('HAFISCAL_RUN_STEP_5B', True)

# VERIFY axis (reuse-fidelity verification level; thread-2 taxonomy). reproduce.sh sets
# HAFISCAL_VERIFY_LEVEL and it propagates to every step subprocess this orchestrator spawns.
# Announce a non-default level once here (the orchestrator's natural surface); at the default
# 'numeric' stay silent so default-path output is unchanged. The level GATES the opt-in
# double-checks wired incrementally in thread-2 components 2-5 (multi-seed drift+SE,
# re-solve-and-compare on reuse, the de-biased one-step Gate A, byte-exact reuse).
# Reader: Code/HA-Models/verify_level.py.
try:
    from verify_level import get_verify_level as _get_verify_level
    _verify_level = _get_verify_level()
except Exception:
    _verify_level = 'numeric'  # announce-only; safe-degrade if the reader can't import
if _verify_level != 'numeric':
    print(f"[do_all] VERIFY axis: reuse-fidelity verification level = '{_verify_level}' "
          f"(adds opt-in double-checks; default 'numeric' = numerically-equivalent reuse). "
          f"Spec: plans/20260622_reuse-fidelity-verification-flag-taxonomy.md", flush=True)

# Calculate total steps for progress tracking
total_steps = sum([run_step_1, run_step_2, run_step_3, run_step_4, run_step_5])
current_step_num = 0

def next_step():
    global current_step_num
    current_step_num += 1
    return current_step_num

#%%
# Step 1: Estimate the splurge factor (paper section 3.1) — see README.md §Step 1 (this directory).
if run_step_1:
    step_num = next_step()
    start_step(step_num, "Estimating splurge factor (Section 3.1)", total_steps)
    substep("Running Estimation_BetaNablaSplurge.py", expected_duration_min=30)
    profiler.sample_memory("step1_start")
    
    print('Step 1: Estimating the splurge factor\n')
    t0 = time()
    os.chdir('Target_AggMPCX_LiquWealth')
    script_path = "Estimation_BetaNablaSplurge.py"
    os.system("python " + script_path)
    os.chdir('../')
    
    duration = time() - t0
    progress(f"Splurge estimation completed in {duration/60:.1f} minutes")
    profiler.sample_memory("step1_end")
    complete_step(step_num)
    print('Concluded Step 1.\n\n')


# Step-2/3 estimator dispatched by HAFISCAL_STEP2_SIM_ENGINE. DEFAULT = TM-ergodic
# (estim_phase2_tm_a.py) since 2026-06-23: validated to estimate the SAME beta as the MC
# panel (<=0.06% across all three cohorts) at ~10-21x the speed (a full estimation in
# ~15 min vs ~half a day). HAFISCAL_STEP2_SIM_ENGINE=mc restores the MC panel
# (EstimAggFiscalMAIN.py). Rationale + validation table:
# conclusions_private/2026-06-23_step2-default-flip-to-tm-ergodic.md.
_step2_engine = os.environ.get('HAFISCAL_STEP2_SIM_ENGINE', 'tm_ergodic').strip().lower()
_step2_script = 'EstimAggFiscalMAIN.py' if _step2_engine == 'mc' else 'estim_phase2_tm_a.py'


#%%
# Step 2: Estimate discount factor distributions (paper section 3.3.3) — see README.md §Step 2.
if run_step_2:
    step_num = next_step()
    start_step(step_num, "Estimating discount factor distributions (Section 3.3.3)", total_steps)
    profiler.sample_memory("step2_start")
    
    print('Step 2: Estimating discount factor distributions (this takes a while!)\n')
    os.chdir('FromPandemicCode')
    
    substep(f"Running {_step2_script} (main estimation, engine={_step2_engine})", expected_duration_min=2880)
    t0 = time()
    os.system("python " + _step2_script)
    progress(f"{_step2_script} completed in {(time()-t0)/60:.1f} minutes")
    
    substep("Creating Lorenz Point figures", expected_duration_min=5)
    t0 = time()
    os.system("python " + "CreateLPfig.py")
    progress(f"CreateLPfig.py completed in {(time()-t0)/60:.1f} minutes")
    
    substep("Creating IMPC figures", expected_duration_min=5)
    t0 = time()
    os.system("python " + "CreateIMPCfig.py")
    progress(f"CreateIMPCfig.py completed in {(time()-t0)/60:.1f} minutes")
    
    substep("Generating beta estimation tables", expected_duration_min=2)
    t0 = time()
    os.system("python " + "estimBetas_tabular_generate.py")
    progress(f"estimBetas_tabular_generate.py completed in {(time()-t0)/60:.1f} minutes")
    
    substep("Generating non-targeted moments tables", expected_duration_min=2)
    t0 = time()
    os.system("python " + "nonTargetedMoments_tabular_generate.py")
    progress(f"nonTargetedMoments_tabular_generate.py completed in {(time()-t0)/60:.1f} minutes")
    
    os.chdir('../')
    profiler.sample_memory("step2_end")
    complete_step(step_num)
    print('Concluded Step 2.\n\n')

#%%
# Step 3: Robustness estimation with Splurge=0 (Online Appendix; off by default) — see README.md §Step 3.
if run_step_3:
    step_num = next_step()
    start_step(step_num, "Robustness: Splurge=0 estimation (Online Appendix)", total_steps)
    substep("Running EstimAggFiscalMAIN.py with Splurge=0", expected_duration_min=2880)
    profiler.sample_memory("step3_start")
    
    print('Step 3: Robustness results (note: this repeats step 2)\n')  
    os.chdir('FromPandemicCode')
    # Order of input arguments: interest rate, risk aversion, replacement rate w/benefits, replacement rate w/o benefits, Splurge   
    # For robustness, keep basline parameters, but set splurge to 0

    t0 = time()
    args = ['1.01', '2.0', '0.7', '0.5', '0']
    cmd = "python " + _step2_script + " " + " ".join(args)  # same engine as Step 2 (default TM-ergodic)
    os.system(cmd)
    progress(f"Robustness estimation completed in {(time()-t0)/60:.1f} minutes")
    
    os.chdir('../')
    profiler.sample_memory("step3_end")
    complete_step(step_num)
    print('Concluded Step 3.\n\n')


#%%
# Step 4: Solve the HANK-SAM model (paper section 5) — see README.md §Step 4.
if run_step_4:
    step_num = next_step()
    start_step(step_num, "HANK/SAM Model - Jacobians and experiments (Section 5)", total_steps)
    profiler.sample_memory("step4_start")
    
    print('Step 4: HANK Robustness Check\n')
    os.chdir('FromPandemicCode')

    # compute household Jacobians
    substep("Computing household Jacobians (HA-Fiscal-HANK-SAM.py)", expected_duration_min=720)  # ~12 hours
    t0 = time()
    script_path = 'HA-Fiscal-HANK-SAM.py'
    os.system("python " + script_path) 
    progress(f"Jacobian computation completed in {(time()-t0)/60:.1f} minutes")

    # run HANK-SAM experiments
    substep("Running HANK-SAM policy experiments", expected_duration_min=60)
    t0 = time()
    script_path = 'HA-Fiscal-HANK-SAM-to-python.py'
    os.system("python " + script_path)  
    progress(f"HANK-SAM experiments completed in {(time()-t0)/60:.1f} minutes")
    
    os.chdir('../')
    profiler.sample_memory("step4_end")
    complete_step(step_num)
    print('Concluded Step 4. \n')


#%%
# Step 5: Compare fiscal stimulus policies (paper section 4) — see README.md §Step 5.
if run_step_5:
    step_num = next_step()
    start_step(step_num, "Comparing fiscal stimulus policies (Section 4)", total_steps)
    profiler.sample_memory("step5_start")

    # Two phases: 5a TM multipliers + 5b MC welfare-6 — see README.md §Step 5.
    print('Step 5: Comparing policies (TM multipliers + MC welfare-6)\n')
    t0 = time()
    os.chdir('FromPandemicCode')

    # 5a: TM multipliers — a-indexed canonical (BUG-033); HAFISCAL_QE_FIDELITY=1 reverts to m-indexed. See README.md §Step 5.
    substep("Running AggFiscalMAIN_reduced.py --baseline (TM multipliers, a-indexed)",
            expected_duration_min=1350)  # ~22.5 h: a-indexed + bug_fix encoding (Plan B aims to cut this)
    t_tm = time()
    _tm_idx = "" if os.environ.get('HAFISCAL_QE_FIDELITY', '') == '1' else "HAFISCAL_TM_A_INDEXED=1 "
    rc_tm = os.system(_tm_idx + "python AggFiscalMAIN_reduced.py --baseline")
    progress(f"Step 5a (TM multipliers) completed in {(time()-t_tm)/60:.1f} minutes (rc={rc_tm})")

    # 5b: MC welfare-6 (parallel driver; Tables/Baseline/welfare6.tex) — see README.md §Step 5.
    if run_step_5b:
        substep("Running run_welfare6_parallel.py --baseline (MC welfare-6, parallel)",
                expected_duration_min=60)  # ~1 h wall parallel (auto)
        t_mc = time()
        rc_mc = os.system(
            "python run_welfare6_parallel.py --baseline "
            "--out-dir welfare6_scenario_results_Baseline_reproduce "
            "--table-dir Tables/Baseline"
        )
        progress(f"Step 5b (MC welfare-6) completed in {(time()-t_mc)/60:.1f} minutes (rc={rc_mc})")
    else:
        progress("Skipping Step 5b welfare-6 (HAFISCAL_RUN_STEP_5B=false) — multiplier-only run")

    progress(f"Step 5 total: {(time()-t0)/60:.1f} minutes")
    os.chdir('../')
    profiler.sample_memory("step5_end")
    complete_step(step_num)
    print('Concluded Step 5. \n')


# ---- Provenance hook (best-effort; never aborts the pipeline) ----
# Emit one run-provenance record for the whole do_all pipeline: a central
# manifest plus travelling RUN_<run_id>.prov.json sidecars next to the headline
# deliverables. Per-script sidecars are also emitted by the sub-entry-points.
try:
    import provenance as _prov  # do_all runs from Code/HA-Models (sidecar importable here)
    _prov.emit(
        ["Results", "FromPandemicCode/Tables/Baseline", "FromPandemicCode/Figures/Baseline"],
        command="python do_all.py",
        argv=sys.argv,
        label="do_all",
        output_roots=["FromPandemicCode/Tables/Baseline",
                      "FromPandemicCode/Figures/Baseline"],
    )
except Exception as _prov_err:
    print(f"[provenance] WARNING: do_all sidecar emit skipped (non-fatal): {_prov_err!r}")
