# filename: do_all.py

# Import the exec function
from builtins import exec
import sys 
import os
from time import time

# Run from this file's own directory, whatever the caller's working directory is.
# Every step below chdirs RELATIVELY (os.chdir('Target_AggMPCX_LiquWealth'),
# os.chdir('FromPandemicCode'), os.chdir('../')), so the pipeline used to work only
# when invoked as `python do_all.py` from Code/HA-Models. The form documented
# everywhere else -- `python Code/HA-Models/do_all.py` from the repository root, which
# is what CLAUDE.md, UPDATES.md and the note sent to the co-authors all say -- died on
# its first line with FileNotFoundError: 'Target_AggMPCX_LiquWealth'. Both forms now
# work, and so does any other cwd. Also put this directory on sys.path, since the
# module imports below (hafiscal_progress and the step scripts) assume it.
_HERE = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _HERE:
    os.chdir(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

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

# HOT mode (2026-09-07): exercise every live path as fast as possible and keep none of the
# numbers. Swaps the paper-scale Baseline for a small parametrization and suffixes every
# Step-3/5 output so a hot run cannot be mistaken for --
# or overwrite -- a result of record. Several generators hard-code paper exhibit paths with
# no scope hook, so those are snapshotted before the run and restored (and verified) after.
# The SST, including why a hot run deliberately does NOT warm-start: Code/HA-Models/hot_mode.py
try:
    import hot_mode as _hot_mode
except Exception:
    _hot_mode = None
_HOT = bool(_hot_mode and _hot_mode.enabled())
if _HOT:
    print(_hot_mode.banner(), flush=True)
    # Step 3 deliberately keeps its normal default (OFF). Turning it ON for "more coverage"
    # was the first cut of this mode and it was wrong: Step 3 costs about as much as Step 2
    # (~40 min), so a "fast" mode that enabled it came out SLOWER than an ordinary run --
    # 124 min against 136. Coverage of the Splurge0 arm is a separate request; ask for it
    # with HAFISCAL_RUN_STEP_3=true, which composes with hot mode like any other toggle.
    _HOT_TOL = _hot_mode.apply_tolerances(os.environ)
    if _HOT_TOL:
        print("[hot] coarse optimizer tolerances: "
              + ", ".join(f"{k.replace('HAFISCAL_','')}={v}" for k, v in _HOT_TOL.items()),
              flush=True)
    # Redirect Step 2's calibration writes away from ../Results entirely. Strictly better
    # than restoring afterwards: nothing is written to the real path, so even a hard kill
    # (where the atexit restore never runs) leaves the calibration of record untouched.
    _hot_out = _hot_mode.results_out_dir(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('HAFISCAL_RESULTS_OUT_DIR', _hot_out)
    print(f"[hot] Step-2 calibration writes redirected to {_hot_out}", flush=True)
    # An ISOLATED policy/equilibrium store. The real one is per machine and shared across
    # checkouts; a hot run would otherwise leave every trial beta and every hot equilibrium
    # in it as permanent entries no real run can hit (keys include the Splurge, so they can
    # never collide with a real entry -- but they never go away either).
    _hot_store = _hot_mode.store_dir(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('HAFISCAL_POLICY_STORE_DIR', _hot_store)
    print(f"[hot] policy/equilibrium store isolated at {_hot_store}", flush=True)
    _HOT_SCOPE = _hot_mode.scope()
    _HOT_SUFFIX = _hot_mode.SUFFIX
    _HOT_SAVED, _HOT_ABSENT = _hot_mode.snapshot(
        os.path.dirname(os.path.abspath(__file__)),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.hot_exhibit_snapshot'))
    print(f"[hot] {len(_HOT_SAVED)} protected files snapshotted ({len(_HOT_ABSENT)} protected "
          f"paths absent and will be removed if the run creates them); restored and verified "
          f"when the run ends", flush=True)
    import atexit as _atexit
    import signal as _signal
    from datetime import datetime as _dt
    _HA_DIR = os.path.dirname(os.path.abspath(__file__))
    _HOT_OUT = os.environ.get('HAFISCAL_HOT_OUT', '').strip() or os.path.join(
        _HA_DIR, 'hot_runs',
        # <stamp>_<HEAD8>: name order IS time order (the reverse put a hash's first hex digit
        # ahead of the clock and blessed the wrong run on 2026-09-07)
        f"{_dt.now():%Y%m%d-%H%M%S}_{_hot_mode._git(_HA_DIR, 'rev-parse', '--short', 'HEAD') or 'nohead'}")
    _HOT_REF = os.environ.get('HAFISCAL_HOT_REFERENCE', '').strip() or os.path.join(_HA_DIR, 'hot_reference')
    _HOT_STATE = {'captured': False, 'changed': None}

    def _hot_restore():
        # CAPTURE FIRST: for a protected path the hot result exists only until the restore.
        # This is what turns the run into a regression check -- see hot_mode.capture. Runs from
        # atexit too, so a SIGTERM (converted to SystemExit below) still captures what exists.
        if not _HOT_STATE['captured']:
            _HOT_STATE['captured'] = True
            n = _hot_mode.capture(_HA_DIR, _HOT_SAVED, _HOT_OUT)
            print(f"[hot] captured {n} hot outputs -> {_HOT_OUT}", flush=True)
        print(f"[hot] restored {_hot_mode.restore(_HOT_SAVED, _HOT_ABSENT, _HA_DIR)} "
              f"protected paths (+ removed what the run created at protected patterns)", flush=True)
    _atexit.register(_hot_restore)
    # atexit does not run on SIGTERM (the default action ends the process outright), and
    # SIGTERM is exactly what `systemctl stop` and a job-control kill send. Convert it to
    # SystemExit so the restore above still runs. SIGKILL cannot be caught; that is why
    # Step 2's writes are REDIRECTED rather than restored, and why the calibration of
    # record is safe even then.
    _signal.signal(_signal.SIGTERM, lambda *_: sys.exit(143))

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

# ---------------------------------------------------------------------------
# Step-child launcher: THIS interpreter, loud on failure (2026-08-03).
# The historical `os.system("python " + script)` resolved `python` from PATH,
# which silently picks a foreign interpreter outside an activated venv — on
# ccarroll-m5 the whole pipeline "succeeded" in 10 seconds with every child
# dying on ModuleNotFoundError while os.system discarded the return codes.
# Children now run under sys.executable (the interpreter running do_all) and
# a nonzero rc prints a loud FAILED line and is collected for the end-of-run
# summary + exit code. Keep-going semantics are unchanged (a failed step
# never aborted the later ones).
# ---------------------------------------------------------------------------
_FAILED_STEP_CHILDREN = []


def _py(cmd_tail, env_prefix="", runq_class=None):
    """Run one step child: `<env_prefix> "<sys.executable>" <cmd_tail>`.

    HAFISCAL_RUNQ=1 (opt-in, 2026-08-28; infrastructure plan B4): route the child through the per-machine
    resource queue `Code/HA-Models/runq.py` in its class (5a / battery / step2) so a pipeline run queues behind
    other arms on the box instead of contending with them. Unset or 0 = unchanged behaviour.
    """
    if runq_class and os.environ.get("HAFISCAL_RUNQ", "").strip().lower() in ("1", "on", "true", "yes"):
        _runq = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runq.py")
        cmd_tail = f'"{_runq}" --class {runq_class} -- "{sys.executable}" {cmd_tail}'
    cmd = f'{env_prefix}"{sys.executable}" {cmd_tail}'
    rc = os.system(cmd)
    if rc != 0:
        print(f"[do_all] STEP CHILD FAILED (rc={rc}): {cmd}", flush=True)
        _FAILED_STEP_CHILDREN.append((cmd, rc))
    return rc

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
    substep("Running Estimation_BetaNablaSplurge.py", expected_duration_min=35)  # default = CONTINUATION protocol (owner ruling 2026-08-22: sigma=0 cold 4-start + one joint descent) at the grid-only stack (hermite60 + knots 8@6x): ~25 min sequential
    profiler.sample_memory("step1_start")
    
    print('Step 1: Estimating the splurge factor\n')
    t0 = time()
    os.chdir('Target_AggMPCX_LiquWealth')
    script_path = "Estimation_BetaNablaSplurge.py"
    _py(script_path)
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
    _py(_step2_script, runq_class="step2")
    progress(f"{_step2_script} completed in {(time()-t0)/60:.1f} minutes")
    
    # ---- Fit-table pass (added 2026-09-06) -------------------------------------
    # The estimation above SEARCHES for (beta, nabla) and stops. It does not write the
    # FIT: the search evaluates on a reduced population for speed, and the statistics the
    # paper reports come from a second, non-searching evaluation at the chosen parameters
    # over the full population. That pass is EstimAggFiscalMAIN.py with the Nelder-Mead
    # gate off -- the same "final calcAllResults pass" run_phase2_parallel.py performs --
    # and it writes Results/AllResults_*.txt: median wealth/income ratios, the Lorenz
    # points, and the imposed discount-factor distribution per education group.
    #
    # THE BUG this fixes: do_all never ran it, while all four generators below
    # (CreateLPfig, CreateIMPCfig, estimBetas_tabular_generate,
    # nonTargetedMoments_tabular_generate) READ that file. A reader following the
    # documented pipeline therefore got correct discount factors and whatever fit tables a
    # previous hand-run had left on disk -- three of the paper's exhibits silently stale.
    # It went unnoticed because we always ran the pass by hand.
    #
    # HAFISCAL_NM_IN_PLACE=0 is carried here DELIBERATELY (BUG-125, fixed 2026-09-07). Since
    # the BUG-080 proper fix (2026-09-09, AggFiscalModel.warm_start_seed) it is no longer
    # REQUIRED -- verified the same day: the pass run with the flag unset completes, the gate
    # declining four in-place warm starts ("[warm-start] BUG-080: DiscFac raised in place
    # 0.986129 -> 0.994267; seed declined, cold start") -- but it stays because it pins what
    # this pass does: one deep copy per education group, no warm-start dependence between
    # groups, byte-identical whether or not the gate ever fires. Dropping it would change the
    # pass's solve path (warm where the gate allows), not its numbers; that is an owner call.
    # test_hot_mode.py asserts the flag is still here.
    # History. The comment this replaced (2026-09-06) argued the flag "governs the
    # Nelder-Mead objective's in-place mutation" and that "this pass does not run
    # Nelder-Mead, so inheriting the workaround here would be cargo cult". The name
    # misleads: the flag is not read by any optimizer. It is read inside
    # `betas_obj_func_educ` itself (EstimAggFiscalMAIN.py:1140), and THIS pass calls that
    # function directly at EstimAggFiscalMAIN.py:1820. Without the flag -- before the
    # BUG-080 gate -- the objective mutated the economy's agents in place, and the second
    # education group's solve tripped the PF-decay guard:
    #   ValueError: AggFiscalModel PF-decay: ... top knot c=6.84519 EXCEEDS the AD-aware
    #   PF line 5.2073 ... (HAFISCAL_PF_DECAY_EXTRAP; BUG-062)
    # That is what happened in the 2026-09-06 chain of record (chain.out:3007): the pass
    # died after writing only its 118-byte header, and CreateLPfig, CreateIMPCfig,
    # estimBetas_tabular_generate and nonTargetedMoments_tabular_generate all failed after
    # it -- so the very exhibits this step was added to keep fresh went a revision stale,
    # silently, in the run that was supposed to refresh them.
    # HAFISCAL_EDTYPES is cleared so the pass is full-population even if a caller narrowed
    # the estimation.
    substep("Fit-table pass: full-population statistics at the estimated parameters",
            expected_duration_min=10)
    t0 = time()
    _py("EstimAggFiscalMAIN.py",
        env_prefix="env -u HAFISCAL_EDTYPES HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 "
                   "HAFISCAL_NM_IN_PLACE=0 ")
    progress(f"fit-table pass completed in {(time()-t0)/60:.1f} minutes")

    substep("Creating Lorenz Point figures", expected_duration_min=5)
    t0 = time()
    _py("CreateLPfig.py")
    progress(f"CreateLPfig.py completed in {(time()-t0)/60:.1f} minutes")
    
    substep("Creating IMPC figures", expected_duration_min=5)
    t0 = time()
    _py("CreateIMPCfig.py")
    progress(f"CreateIMPCfig.py completed in {(time()-t0)/60:.1f} minutes")
    
    substep("Generating beta estimation tables", expected_duration_min=2)
    t0 = time()
    _py("estimBetas_tabular_generate.py")
    progress(f"estimBetas_tabular_generate.py completed in {(time()-t0)/60:.1f} minutes")
    
    substep("Generating non-targeted moments tables", expected_duration_min=2)
    t0 = time()
    _py("nonTargetedMoments_tabular_generate.py")
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
    _py(_step2_script + " " + " ".join(args), runq_class="step2")  # same engine as Step 2 (default TM-ergodic)

    # The same fit-table pass as Step 2 (see the comment there), with this arm's
    # arguments: it writes AllResults_*_Splurge0*.txt, which the no-splurge appendix's
    # Lorenz and IMPC figures read. Omitted here for the same reason it was omitted
    # there, and with the same consequence.
    # BUG-125 applies here exactly as in Step 2's pass (the comment it replaces said this
    # omission had "the same consequence" -- it did: the pass died on the second group
    # before the BUG-080 gate; the flag is kept for the same reason as above).
    _py("EstimAggFiscalMAIN.py " + " ".join(args),
        env_prefix="env -u HAFISCAL_EDTYPES HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 "
                   "HAFISCAL_NM_IN_PLACE=0 ")

    # The splurge-zero half of the UI-expiry validation panels (see Step 5c): the MC baseline
    # pickle for this arm, without which EvalConsDropUponUILeave.py cannot draw the comparison.
    # Under hot mode the suffix keeps this out of Tables/Splurge0 and Figures/Splurge0 --
    # the no-splurge appendix's current results -- and in Tables/Splurge0_hot instead.
    _py("AggFiscalMAIN_reduced.py --splurge0",
        env_prefix=(f"HAFISCAL_FIGS_SUFFIX={_HOT_SUFFIX} " if _HOT else "")
                   + "HAFISCAL_BASELINE_ONLY=1 HAFISCAL_SIM_METHOD=MC ")
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

    # compute household Jacobians — the step4 package entry is the single
    # dispatch point (L4, 2026-08-09): it runs the live package engine by
    # default and routes to the frozen monolith pair for QE-fidelity /
    # historical-escape / HAFISCAL_STEP4_ENGINE=monolith requests.
    substep("Computing household Jacobians (step4/run_jacobians.py)", expected_duration_min=15)  # ~13 min kernel-default (2026-08-09; was 12h migration-era)
    t0 = time()
    script_path = os.path.join('..', 'step4', 'run_jacobians.py')
    _py(script_path)
    progress(f"Jacobian computation completed in {(time()-t0)/60:.1f} minutes")

    # run HANK-SAM experiments
    substep("Running HANK-SAM policy experiments", expected_duration_min=1)  # ~13 s measured
    t0 = time()
    script_path = os.path.join('..', 'step4', 'run_ge.py')
    _py(script_path)
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
    if _HOT:
        # --parametrization <scope> instead of --baseline, and HAFISCAL_FIGS_SUFFIX so the
        # run lands in Tables/<scope>_hot/ and Figures/<scope>_hot/ -- never the paper's.
        rc_tm = _py(f"AggFiscalMAIN_reduced.py --parametrization {_HOT_SCOPE}",
                    env_prefix=_tm_idx + f"HAFISCAL_FIGS_SUFFIX={_HOT_SUFFIX} ", runq_class="5a")
    else:
        rc_tm = _py("AggFiscalMAIN_reduced.py --baseline", env_prefix=_tm_idx, runq_class="5a")
    progress(f"Step 5a (TM multipliers) completed in {(time()-t_tm)/60:.1f} minutes (rc={rc_tm})")

    # 5b: MC welfare-6 (parallel driver; Tables/Baseline/welfare6.tex) — see README.md §Step 5.
    if run_step_5b:
        substep("Running run_welfare6_parallel.py --baseline (MC welfare-6, parallel)",
                expected_duration_min=60)  # ~1 h wall parallel (auto)
        t_mc = time()
        # BUG-119 (option 1, 2026-09-02): Step 5b takes the SAME HAFISCAL_TM_A_INDEXED
        # prefix as Step 5a (_tm_idx) so AD-equilibrium sharing's key matches across
        # the two stages. The flag selects the TM multiplier engine; the welfare cells
        # are Monte Carlo and consume Step 5a's SHARED aggregate path, so it is inert
        # for the welfare numbers (the welfare/MC code never reads it) and only fixes
        # the key. Durable follow-up = option 2 (drop engine-selection vars from the
        # sharing key); see BUG-119.
        if _HOT:
            rc_mc = _py(
                f"run_welfare6_parallel.py --parametrization {_HOT_SCOPE} "
                f"--out-dir welfare6_scenario_results_{_HOT_SCOPE}{_HOT_SUFFIX} "
                f"--table-dir Tables/{_HOT_SCOPE}{_HOT_SUFFIX}",
                env_prefix=_tm_idx, runq_class="battery"
            )
        else:
            rc_mc = _py(
                "run_welfare6_parallel.py --baseline "
                "--out-dir welfare6_scenario_results_Baseline_reproduce "
                "--table-dir Tables/Baseline", env_prefix=_tm_idx, runq_class="battery"
            )
        progress(f"Step 5b (MC welfare-6) completed in {(time()-t_mc)/60:.1f} minutes (rc={rc_mc})")
    else:
        progress("Skipping Step 5b welfare-6 (HAFISCAL_RUN_STEP_5B=false) — multiplier-only run")

    # ---- 5c: the validation-exhibit pass (added 2026-09-06) --------------------
    # "Spending upon UI benefit expiry" (the right panel of the nontargeted-moments figure)
    # and its with/without-splurge companion are drawn by EvalConsDropUponUILeave.py from
    # `base_results_full`, a pickle that only the MC arm writes. Production runs the TM
    # engine, so the pickle never appeared and neither panel could be regenerated by the
    # pipeline -- they were hand-made or stale.
    #
    # It costs no solve: the policy store serves the same household problem Step 5a just
    # solved, so this is the baseline SIMULATION only (seconds to ~2 min). It runs as its
    # own process, after 5a, because an MC baseline advances agent state and doing it inside
    # the multiplier run would put that mutation upstream of the TM experiments.
    substep("Validation-exhibit pass: MC baseline for the UI-expiry panels", expected_duration_min=5)
    t_ex = time()
    _ex_scope = f"--parametrization {_HOT_SCOPE}" if _HOT else "--baseline"
    _ex_sfx = f"HAFISCAL_FIGS_SUFFIX={_HOT_SUFFIX} " if _HOT else ""
    rc_ex = _py(f"AggFiscalMAIN_reduced.py {_ex_scope}",
                env_prefix=_tm_idx + _ex_sfx + "HAFISCAL_BASELINE_ONLY=1 HAFISCAL_SIM_METHOD=MC ")
    progress(f"Step 5c (validation-exhibit baseline) completed in {(time()-t_ex)/60:.1f} minutes (rc={rc_ex})")

    # The figure needs BOTH arms. The splurge-zero pickle comes from Step 3 (off by default),
    # so say plainly which one is missing rather than half-drawing the exhibit.
    _figs = os.path.join(os.getcwd(), 'Figures')
    _need = {'estimated splurge': os.path.join(_figs, 'CRRA2', 'base_results_full.pkl'),
             'splurge zero': os.path.join(_figs, 'Splurge0', 'base_results_full.pkl')}
    _missing = [k for k, v in _need.items() if not os.path.exists(v)]
    if _missing:
        progress("Skipping the UI-expiry validation panels: no baseline pickle for "
                 + " and ".join(_missing)
                 + " (the splurge-zero arm is Step 3, HAFISCAL_RUN_STEP_3=true)")
    else:
        substep("Drawing the UI-expiry validation panels", expected_duration_min=1)
        _py("EvalConsDropUponUILeave.py")

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

# ---- HOT regression verdict (2026-09-07): capture now (not at exit), compare to the reference ----
if _HOT:
    _hot_restore()          # capture + restore; the atexit copy becomes a no-op for the capture
    if os.path.isdir(_HOT_REF) and os.path.exists(os.path.join(_HOT_REF, 'MANIFEST.json')):
        _rows, _changed = _hot_mode.compare(_HOT_REF, _HOT_OUT, rel_tol=_hot_mode.tolerance())
        _rep = _hot_mode.write_report(_rows, _changed, _HOT_REF, _HOT_OUT,
                                      os.path.join(_HOT_OUT, 'COMPARE.md'))
        _HOT_STATE['changed'] = _changed
        print(f"\n[hot] REGRESSION CHECK against {_HOT_REF}: "
              + ("NO REGRESSION -- every captured output identical or within tolerance"
                 if _changed == 0 else f"{_changed} FILE(S) CHANGED OR MISSING")
              + f"  (report: {_rep})", flush=True)
        for _rel, _v in _rows:
            if _v.startswith(("CHANGED", "MISSING")):
                print(f"[hot]   {_v:50s} {_rel}", flush=True)
    else:
        print(f"\n[hot] no reference at {_HOT_REF}: nothing to compare against. If this tree is "
              f"the known-good one, bless this run with `make hot-reference`.", flush=True)

# ---- Failure summary + honest exit code (2026-08-03; see _py above) ----
if _HOT and _HOT_STATE.get('changed'):
    print(f"\n[do_all] HOT REGRESSION: {_HOT_STATE['changed']} captured output(s) differ from the "
          f"reference (see COMPARE.md). Exit 2.", flush=True)
    sys.exit(2)
if _FAILED_STEP_CHILDREN:
    print(f"\n[do_all] PIPELINE INCOMPLETE — {len(_FAILED_STEP_CHILDREN)} step "
          f"child(ren) FAILED:", flush=True)
    for _cmd, _rc in _FAILED_STEP_CHILDREN:
        print(f"  rc={_rc}: {_cmd}", flush=True)
    sys.exit(1)
print("\n[do_all] all launched step children exited 0.", flush=True)
