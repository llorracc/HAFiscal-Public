'''
This is the main script for the paper
'''
#from Parameters import return_parameters

import os

# --- Numeric-thread caps: fork-oversubscription fix (2026-07-07) ---------------
# MUST run before numpy/HARK are imported (below, via `from Simulate import ...`).
# This venv's numpy is linked against OpenBLAS, which spawns a thread pool sized
# to the logical-core count (32 on the dev box) the INSTANT numpy is imported.
# This entry point fans work out with os.fork() at TWO levels -- the outer
# shock-type fork (up to 7 concurrent jobs, Simulate.py ~L1273) and the inner
# duration fork (HAFISCAL_DUR_WORKERS, Simulate.py _fork_dispatch_durations) --
# and each forked PROCESS gets its own full-width BLAS pool. N worker processes x
# 32 BLAS threads oversubscribes 32 cores (observed load ~197, ~32 h wall vs a
# ~9.45 h precedent). The fork dispatchers already budget cores assuming ONE
# thread per worker (ncpu//8), so pin BLAS to 1 and let PROCESS-parallelism do
# the work. setdefault => an explicit env override (e.g. OMP_NUM_THREADS=2) wins.
# Mirrors welfare6_scenario.py (Step-5b), which already pins these. Per-var WHY:
#   OPENBLAS_NUM_THREADS  this venv's actual BLAS backend (the 32-thread pool)
#   OMP_NUM_THREADS       OpenBLAS / numba / scipy OpenMP fallback knob
#   MKL_/VECLIB_/NUMEXPR_ portability: MKL-linked numpy, macOS Accelerate, numexpr
#   NUMBA_NUM_THREADS     HARK interpolation/utilities use numba (its own pool)
for _thr_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_thr_var, "1")
# -------------------------------------------------------------------------------
import sys
from time import time

# Owner rulings R1/R2 (2026-08-07): the Step-5a entry point defaults to
# newton2d + the numba kernel (worlds/explicit env excluded inside the
# helper; FTI-absent runs fall back to plain EGM at solve time).
try:
    _ham_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..'))
    if _ham_dir not in sys.path:
        sys.path.insert(0, _ham_dir)
    from solver_accel import apply_newton2d_defaults as _n2d_defaults
    _n2d_defaults("step5a")
except Exception as _n2d_e:  # pragma: no cover - fail-soft to plain EGM
    print(f"[step5a] newton2d defaults unavailable ({_n2d_e}); plain EGM")

mystr = lambda x : '{:.2f}'.format(x)

# for output
cwd             = os.getcwd()
folders         = cwd.split(os.path.sep)
top_most_folder = folders[-1]
if top_most_folder == 'FromPandemicCode':
    Abs_Path = cwd
else:
    Abs_Path = cwd + '/Code/HA-Models/FromPandemicCode'
    os.chdir(Abs_Path)

sys.path.append(Abs_Path)
from Simulate import Simulate
from Output_Results import Output_Results

#%%



Run_Dict = dict()
Run_Dict['Run_Baseline']            = True
Run_Dict['Run_Recession ']          = True
Run_Dict['Run_Check_Recession']     = True
Run_Dict['Run_UB_Ext_Recession']    = True
Run_Dict['Run_TaxCut_Recession']    = True
Run_Dict['Run_Check']               = True
Run_Dict['Run_UB_Ext']              = True
Run_Dict['Run_TaxCut']              = True
Run_Dict['Run_AD ']                 = True
Run_Dict['Run_1stRoundAD']          = True   # 2026-04-30: re-enabled. Was set to
                                              # False in the original 2023 "reduced
                                              # reproduce" stub (commit 5ab588e5) and
                                              # never flipped back when the rest of
                                              # the flags became production. Flipping
                                              # it back to True restores the 1st-round
                                              # AD multipliers the QE paper reports
                                              # (Multiplier.tex row "1st round AD
                                              # effect only"). Adds ~25% to Step 5
                                              # runtime.
Run_Dict['Run_NonAD']               = True
Run_Dict['sim_method']              = 'TM'   # 'MC', 'TM', or 'both'

# Harmenberg neutral measure for 1D TM:
#   E_P[p * f(m)] = E_P[p] * E_Q[f(m)]   — math-derive-harm (neutral-identity)
#   BST ApndxHarKmenberg, Theorem 1 / "Harmenberg's Method"
#   Notebook: Harmenberg-Four-Way-Comparison.ipynb §8j (uncorrected 1D pitfall)
# Applies to Type A/B (p-linear) outputs only — see type-map:
#   history/20260402-reduced-run-harmenberg-output-type-map.md
Run_Dict['tm_neutral_measure'] = True
# HAFISCAL_TM_MCOUNT env-var override for D-6-proper test of TM aggregation
# grid refinement. See memory project_mc_tm_newborn_timing_asymmetry.md.
Run_Dict['tm_mCount'] = int(os.environ.get('HAFISCAL_TM_MCOUNT', 100))
if 'HAFISCAL_TM_MCOUNT' in os.environ:
    print(f'[tm-mcount-override-rundict] Run_Dict[tm_mCount] = {Run_Dict["tm_mCount"]}')
# Coarser grid (Phase 2 of plans/20260403-1253h_harmenberg-reduced-reproduce-acceleration-plan.md).
# Currently only tm_mCount is consumed by Simulate.py; the FastReproduce tag is
# a forward-looking key for future code that may adjust additional parameters
# (AD iteration count, grid bounds, etc.).  Validate multipliers before relying.
if '--fast-reproduce' in sys.argv:
    sys.argv.remove('--fast-reproduce')
    Run_Dict['FastReproduce'] = True  # tag only — not yet consumed downstream
    Run_Dict['tm_mCount'] = 40

# SOLO-rec mode (formerly GLP-1): single agent type with recession + policies.
# 1 college type, point beta, fixed 3-quarter recession, all policies, no AD.
# Companion: SOLO-pol (no recession, single policy at a time, HS type) — see
# parity_solo_pol_*.py.
# CLI: python AggFiscalMAIN_reduced.py --solo-rec  (alias: --glp1)
if '--solo-rec' in sys.argv or '--glp1' in sys.argv:
    for _flag in ('--solo-rec', '--glp1'):
        if _flag in sys.argv:
            sys.argv.remove(_flag)
    Run_Dict['GLP1'] = True  # internal flag name kept for backward compatibility
    Run_Dict['GLP1_recession_duration'] = 3  # fixed 3-quarter recession
    Run_Dict['sim_method'] = 'TM'

# Dual-measure MC: runs P-track (standard) and Q-track (Harmenberg neutral)
# simultaneously with shared base draws.  Provides variance reduction and
# Q-aggregate as cross-check on P-aggregate.
# See: plans/20260403-1253h_dual-measure-mc-reduced-reproduce-plan.md
if '--dual-mc' in sys.argv:
    sys.argv.remove('--dual-mc')
    Run_Dict['sim_method'] = 'dual_MC'

# Override sim_method from environment (used by reproduce.sh --tm-only etc.)
_env_sim_method = os.environ.get('HAFISCAL_SIM_METHOD', '').strip()
if _env_sim_method:
    Run_Dict['sim_method'] = _env_sim_method
else:
    # METHOD axis (IMPROVEMENT-001) on a DIRECT invocation: HAFISCAL_MULTIPLIER_ENGINE=mc
    # (or the deprecated alias HAFISCAL_MODE=legacy) selects the reliable-MC multiplier
    # engine. EstimParameters resolves the same flag to a `setdefault` of
    # HAFISCAL_SIM_METHOD=MC, but that import happens AFTER this Run_Dict is built, so
    # a direct `HAFISCAL_MULTIPLIER_ENGINE=mc python AggFiscalMAIN_reduced.py` silently
    # ran the TM engine (found 2026-08-25, BUG-092 Test C: the "mc" table was
    # byte-identical to the TM one). reproduce.sh never hit this because its `mc` path
    # goes through reproduce_computed_mc_only.sh, which exports HAFISCAL_SIM_METHOD=MC.
    _engine_env = os.environ.get('HAFISCAL_MULTIPLIER_ENGINE', '').strip().lower()
    if not _engine_env and os.environ.get('HAFISCAL_MODE', '').strip().lower() == 'legacy':
        _engine_env = 'mc'
    if _engine_env == 'mc':
        Run_Dict['sim_method'] = 'MC'
        os.environ['HAFISCAL_SIM_METHOD'] = 'MC'   # children / EstimParameters see the same choice
        print("[method-axis] HAFISCAL_MULTIPLIER_ENGINE=mc -> sim_method 'MC' (direct invocation)",
              flush=True)

# ── STANDARD tier defaults (owner ratification 2026-07-27, item 4) ──────────
# The S2+ composite became this entry point's default: ConsumedATI solver
# routing and AD tol 1e-2 (ENTRY-POINT-SCOPED setdefaults; explicit env always
# wins). Evidence: Reduced |Δmult| ≤ 5.1e-4 same-commit (tier matrix
# 2026-07-26), Baseline shipped 110.8 min vs S2+ 45.5 min = 2.44× at max
# |Δmult| 7.0e-4 vs the 1e-2 budget (G-B, new world, 2026-07-27).
# REFERENCE/FAST remain env recipes in plans/20260726_tier-scheme_options.md;
# exact-QE on the frozen tag.
#
# The tier's K=1 solve-top / count-basis-96 pins were RETIRED 2026-08-24 (owner
# ruling, BUG-089): the multiplier entry solves on the SAME grid as estimation
# and welfare (the global K=3·h̄ / count-basis-192 defaults). On the K=1 grid
# the ATI's tail-exponent estimate was biased and lifted the most patient
# College atom's whole policy ~1.2% (and the EGM+attach solve itself still
# carried a 0.2-0.6% grid residual); the multiplier tables of BOTH worlds had
# been computed on it. The wall cost of the deeper grid is accepted.
os.environ.setdefault('HAFISCAL_STEP5_ATI', '1')
os.environ.setdefault('HAFISCAL_AD_CONVERGENCE_TOL', '1e-2')
# Cohort-parallel economy solves at Simulate.py's five explicit solve sites
# (step5a_parallel_solve.py; 'auto' = min(cohorts, ncpu) in the pre-fork parent,
# ncpu//8 inside a shock-fork child so the two fans compose). Default since
# 2026-08-24 (P4 of the shared-policy-store plan): the fork worker now runs the
# same cold ladder as the sequential loop — policy store -> ATI router (with its
# BUG-088 gate) -> accel -> EGM — and the m5 Reduced_Run gate showed the pooled
# solve byte-identical to the sequential one (tables + per-agent cFunc probes;
# 16 pooled solves, 0 fallbacks). Before that the wrapper was inert here: it fell
# back to the stock loop whenever HAFISCAL_STEP5_ATI was on. Set '0' to opt out.
os.environ.setdefault('HAFISCAL_STEP5A_PARALLEL_SOLVE', 'auto')

# Enable a-indexed TM (BUG-033 splurge-in-budget fix) from environment.
# Routes baseline + experiments through tm_methods' _a variants, eliminating
# the ξ-variance collapse that biases m-indexed multipliers by 15–25% under
# splurge-in-budget. See BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md.
if os.environ.get('HAFISCAL_TM_A_INDEXED', '').strip() in ('1', 'true', 'yes'):
    Run_Dict['tm_a_indexed'] = True

# Override sim_method via env var (used by run_with_tma_companion.py wrapper
# to switch the script to MC mode without code edits). Valid: MC, TM, both.
_sim_method_env = os.environ.get('HAFISCAL_SIM_METHOD', '').strip()
if _sim_method_env in ('MC', 'TM', 'both'):
    Run_Dict['sim_method'] = _sim_method_env

# Crash / wiring check only: Parametrization Smoke_Test (N=100). Not for moments.
# --baseline: Paper-scale 'Baseline' parametrization (21 types). Used by
# `./reproduce.sh --comp full --tm-only` to get the full TM-valid subset.
if '--smoke-test' in sys.argv:
    sys.argv.remove('--smoke-test')
    _reduced_param = 'Smoke_Test'
elif '--baseline' in sys.argv:
    sys.argv.remove('--baseline')
    _reduced_param = 'Baseline'
elif '--splurge0' in sys.argv:
    # No-splurge appendix arm (2026-08-20): run the 'Splurge0' parametrization (Parameters.py
    # loads DiscFacEstim_..._Splurge0 + Result_AllTarget_Splurge0, splurge = 0) through this
    # same reduced Step-5 driver. Outputs land in Figures/Splurge0/ and Tables/Splurge0/ --
    # the manifest paths of the SplurgeComp artifacts. NOTE: Output_Results' Splurge0
    # comparison branch reads the BASELINE multiplier pickles from top-level Figures/
    # (legacy layout); the baseline run writes them to Figures/Baseline/ -- copy
    # C_/NPV_Multiplier_Baseline_Results.csv across before running this arm.
    sys.argv.remove('--splurge0')
    _reduced_param = 'Splurge0'
elif '--parametrization' in sys.argv:
    # Robustness appendix (2026-08-20): run any parametrization Parameters.py knows
    # (CRRA1, CRRA3, Rfree_1005, Rfree_1015, ADElas, Rspell_4, LowerUBnoB, *_PVSame, ...)
    # through this reduced Step-5 driver; outputs land in Figures/<NAME>/ + Tables/<NAME>/.
    _i = sys.argv.index('--parametrization')
    try:
        _reduced_param = sys.argv[_i + 1]
    except IndexError:
        raise SystemExit("--parametrization needs a name (e.g. --parametrization Rspell_4)")
    del sys.argv[_i:_i + 2]
elif '--hs-only' in sys.argv:
    # Single-cohort (HS, DiscFacCount=1) Step-5 multiplier scope — the cheapest meaningful
    # multiplier run, used as the first cascade tier for fast wiring/sanity gating before
    # escalating to Reduced_Run then Baseline (BUG-053 followup multiplier verification).
    sys.argv.remove('--hs-only')
    _reduced_param = 'HS_Only'
else:
    _reduced_param = 'Reduced_Run'

t0 = time()

# HAFISCAL_FIGS_SUFFIX: append a suffix to the parametrization name in the
# output dir paths (so parallel runs don't collide on Figures/Reduced_Run/).
# Example: HAFISCAL_FIGS_SUFFIX=_h0_treat_seed0 → Figures/Reduced_Run_h0_treat_seed0/
_figs_suffix = os.environ.get('HAFISCAL_FIGS_SUFFIX', '')
if _figs_suffix:
    print(f'[figs-suffix] HAFISCAL_FIGS_SUFFIX={_figs_suffix}')
_fig_base = Abs_Path + '/Figures/' + _reduced_param + _figs_suffix + '/'
_tab_base = Abs_Path + '/Tables/' + _reduced_param + _figs_suffix + '/'
# --- Validation-exhibit pass (HAFISCAL_BASELINE_ONLY, 2026-09-06) ----------------------------
# Two of the paper's model-validation panels -- "Spending upon UI benefit expiry" in the
# nontargeted-moments figure, and its with/without-splurge companion -- are drawn by
# EvalConsDropUponUILeave.py from `base_results_full`, a pickle only the MC arm writes
# (Simulate.py's Run_Baseline block). The production path runs the TM engine, so the pickle
# was never produced and the two panels could not be regenerated by the pipeline at all.
#
# This flag runs the BASELINE ONLY, under whatever sim_method is asked for, so the pickle can be
# produced in a separate short invocation. Separate on purpose: the MC baseline simulation
# advances agent state, and doing it inside the multiplier run would put that mutation upstream of
# the TM experiments. As its own process it cannot perturb them, and it costs no solve -- the
# policy store serves the same household problem the multiplier run just solved.
_baseline_only = os.environ.get('HAFISCAL_BASELINE_ONLY', '').strip().lower() in ('1', 'on', 'true', 'yes')
if _baseline_only:
    for _k in list(Run_Dict):
        if _k.strip().startswith('Run_') and _k.strip() != 'Run_Baseline':
            Run_Dict[_k] = False
    Run_Dict['Run_Baseline'] = True
    print("[baseline-only] every experiment except the baseline is OFF "
          f"(sim_method={Run_Dict['sim_method']}) -- validation-exhibit pass", flush=True)

Simulate(Run_Dict, _fig_base, Parametrization=_reduced_param)

# BUG-126 (2026-09-07): a baseline-only pass has NO experiments to tabulate. Output_Results ->
# Welfare_Results diffs the baseline against the recession pickles in the same directory --
# which, if present at all, are the earlier TM run's 40-period experiments, against this
# pass's 100-period MC baseline: `operands could not be broadcast together with shapes
# (100,) (40,)`. Step 5c had never run to completion since it was added (2026-09-06): the
# chain of record's 5c died earlier, on the drift gate, and once that gate became report-only
# the first hot run reached this. The pass exists only to write base_results_full.pkl.
if not Run_Dict.get('GLP1', False) and not _baseline_only:
    Output_Results(_fig_base, _fig_base, _tab_base, Parametrization=_reduced_param)
elif _baseline_only:
    print("[baseline-only] Output_Results skipped: nothing to tabulate (BUG-126)", flush=True)

t1 = time()
print('Whole script took ' + mystr((t1-t0)/60) + ' min.')

# ---- Registry hook ----
# Register Step-5 outputs (Multiplier.tex, base_results.csv, key figures)
# in the SQLite registry. No-op if registry import fails.
try:
    import sys as _sys_reg
    _ha_root_reg = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if _ha_root_reg not in _sys_reg.path:
        _sys_reg.path.insert(0, _ha_root_reg)
    import _registry as _reg

    # Record step5_scope directly on the config dict (the registry reads it from
    # here, NOT from the environment). The previous write-only
    # os.environ.setdefault('HAFISCAL_STEP5_SCOPE', ...) had no consumer and was
    # removed 2026-06-13 (ENV_FLAGS owner-review resolution).
    _cfg = _reg.get_current_config()
    _cfg['step5_scope'] = _reduced_param
    _cfg['step5_method'] = Run_Dict.get('sim_method', 'TM')

    _run_id = _reg.register_run(config=_cfg, notes=f"AggFiscalMAIN_reduced.py {_reduced_param}")

    # Register key Step-5 outputs that exist
    _outputs_to_register = [
        (f"step5_multiplier_{_reduced_param.lower()}", _tab_base + "Multiplier.tex"),
        (f"step5_multiplier_{_reduced_param.lower()}", _tab_base + "Multiplier.ltx"),
        (f"step5_base_results_{_reduced_param.lower()}", _fig_base + "base_results.csv"),
    ]
    for _output_type, _path in _outputs_to_register:
        if os.path.exists(_path):
            _reg.register_output(_run_id, _output_type, _path)

    # Key figures
    for _fig_name in ('Cumulative_multipliers', 'Cumulative_multipliers_withHank'):
        _fig_pdf = _fig_base + _fig_name + '.pdf'
        if os.path.exists(_fig_pdf):
            _reg.register_output(_run_id, f"step5_figure_{_fig_name.lower()}_{_reduced_param.lower()}", _fig_pdf)

    _reg.mark_run_status(_run_id, "complete", wall_total_sec=(t1 - t0))
    print(f"[registry] Step-5 ({_reduced_param}) registered as run {_run_id}")
except Exception as _reg_err:
    print(f"[registry] WARNING: Step-5 registry hook failed: {_reg_err!r}")

# ---- Provenance sidecar hook (best-effort; never aborts the run) ----
# Drops a travelling RUN_<run_id>.prov.json next to the Step-5 table + figure
# outputs and writes the central manifest. Reuses the registry's _run_id (if the
# registry hook above succeeded) so the sidecar, manifest, and registry agree.
try:
    _ha_prov = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if _ha_prov not in sys.path:
        sys.path.insert(0, _ha_prov)
    import provenance as _prov
    _prov.emit(
        [_tab_base, _fig_base],
        command=' '.join(sys.argv),
        argv=sys.argv,
        label=f"step5_multipliers-{_reduced_param}",
        output_roots=[_tab_base + 'Multiplier.tex', _fig_base + 'base_results.csv'],
        run_id=locals().get('_run_id'),
        register=False,
    )
except Exception as _prov_err:
    print(f"[provenance] WARNING: sidecar emit skipped (non-fatal): {_prov_err!r}")
