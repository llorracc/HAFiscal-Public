"""Replay-fed JAX AD loop — Fix C of the draw-structure plan.

The JAX AD fixed-point iteration forward-simulates every iteration with HARK's
CAPTURED exogenous shock realizations (one capture per shock_type, fixed across
iterations) instead of the kernel's own PRNG draws. This makes the JAX loop
iterate the same deterministic map as HARK-AD, evaluated by the compiled
replay kernel — removing the draw-structure offset by construction.

Why one capture is reusable across candidate policies (verified in code,
plan §0a 2026-08-01): every AD iteration's `run_experiment` rewinds the agent
RNG to its seed, restores the pre-AD state, and builds the whole panel from
pre-materialized fixed histories; income shocks are state-INDEXED (not drawn),
the micro-Markov path is exogenous given the macro path, and policy amounts
are baked into the captured TranShk from AD-invariant state. The captured
`*_init_perperiod` arrays are AD-dependent at ALIVE slots only — the replay
kernel reads them exclusively at dead slots (sim_birth draws, AD-invariant),
and this module NaN-masks the alive slots at t>=1 so any unconditional read
fails loudly rather than silently reintroducing the capture-time AD path.

Entry: solve_ad_recession_jax_replay(eco, base_AggCons, ...). Post-conditions
match the other AD solvers (welfare6 depends only on these): eco.CFunc =
converged belief; eco.ADelasticity set; every agent.solution solved under that
belief (the loop solves at the top of each iteration and rolls the final step
back on convergence — the 2026-07-29 belief-consistency ruling).

v1 deliberately bypasses the AD solution cache (measurement harnesses
quarantine ad_* anyway); enable HAFISCAL_JAX_MC_REPLAY_AD=1 to route
welfare6_scenario.run_recession_AD through this solver.
"""

import os
import sys
import time
from copy import deepcopy

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")
if _FPC not in sys.path:
    sys.path.insert(0, _FPC)


class _MortalityCapture:
    """Picklable get_mortality wrapper (a closure here kills the solve pool:
    fork/spawn workers pickle the agents, and closures don't pickle — measured
    2026-07-31, verify_welfare_replay crash). Captures the post-mortality
    state (survivors' end-of-t-1 state with dead slots freshly sim_birth'd)."""

    def __init__(self, orig):
        self.orig = orig
        self.aNrm = []
        self.pLvl = []

    def __call__(self):
        out = self.orig()
        agent = self.orig.__self__
        self.aNrm.append(np.asarray(agent.state_now['aNrm'], dtype=float).copy())
        self.pLvl.append(np.asarray(agent.state_now['pLvl'], dtype=float).copy())
        return out


_AD_DISPATCH = {
    "recession": "solve_ad_recession",
    "recessionCheck": "solve_ad_check_recession",
    "recessionTaxCut": "solve_ad_recession_taxcut",
    "recessionUI": "solve_ad_ui_extension_recession",
}


def capture_exogenous_panel(eco, shock_type, verbose=True, mask_alive=True,
                            want_result=False, iters=1):
    """One HARK forward pass -> per-cohort exogenous shock panel.

    Runs HARK's own AD dispatch on a deepcopy with num_max_iterations=1 and an
    infinite cutoff: one solve under the identity belief + exactly one
    run_experiment (which populates shock_history through the production
    machinery), with capture hooks installed. Returns (captures, eco_ref) —
    eco_ref's recession-space solution can warm-start the caller's iter 1.
    """
    t0 = time.time()
    eco_ref = deepcopy(eco)
    eco_ref.switch_shock_type(shock_type)

    # Presolve cache (successor-plan row 3): the dispatch's ~550 s identity-
    # belief recession solve is the same solve the no-AD twin performs and the
    # hark_solve_only cache stores. Loading it here CANNOT change the captured
    # exogenous panel (shock histories and sim_birth draws are RNG-only), so
    # the substitution is result-neutral by construction for the capture; the
    # AD loop re-solves under its own belief regardless. Gated + best-effort.
    if os.environ.get("HAFISCAL_REPLAY_PRESOLVE_CACHE", "").lower() in ("1", "on", "true"):
        try:
            from solution_cache import load_recession_init_cache
            if load_recession_init_cache(eco_ref, shock_type, verbose=verbose):
                if verbose:
                    print("  [jax-replay-ad] presolve cache HIT: dispatch "
                          "presolve will warm-start from the twin's solve",
                          flush=True)
        except Exception as _e:
            if verbose:
                print(f"  [jax-replay-ad] presolve cache skipped ({_e})",
                      flush=True)

    hooks = []
    for agent in eco_ref.agents:
        h = _MortalityCapture(agent.get_mortality)
        agent.get_mortality = h
        hooks.append(h)

    result_box = {}
    if want_result:
        _orig_rexp = eco_ref.run_experiment

        def _rexp_capture(*a, **k):
            # diagnostic-only path (unit diff); a closure is fine here because
            # want_result runs are never combined with the parallel solve pool
            for hh in hooks:
                hh.aNrm.clear()
                hh.pLvl.clear()
            # sim-time belief + policies (the dispatch re-solves after its
            # post-sim update, so post-dispatch state is NOT what the sim used)
            result_box['CFunc_at_sim'] = deepcopy(eco_ref.CFunc)
            result_box['solutions_at_sim'] = [deepcopy(ag.solution)
                                              for ag in eco_ref.agents]
            r = _orig_rexp(*a, **k)
            result_box['last'] = r
            for key in ('AggDemandFac', 'Cratio', 'CratioPrev'):
                try:
                    result_box[f'{key}_hist'] = np.asarray(
                        eco_ref.history[key], dtype=float).ravel()
                except Exception:
                    result_box[f'{key}_hist'] = None
            return r
        eco_ref.run_experiment = _rexp_capture

    getattr(eco_ref, _AD_DISPATCH[shock_type])(
        num_max_iterations=iters, convergence_cutoff=np.inf if iters == 1 else 0.0)

    captures = []
    for agent, h in zip(eco_ref.agents, hooks):
        sh = agent.shock_history
        aNrm_pp = np.stack(h.aNrm, axis=0)
        pLvl_pp = np.stack(h.pLvl, axis=0)
        # NaN-mask alive slots at t>=1: those entries carry the capture-time
        # AD path; the kernel must only ever read the dead (sim_birth) slots.
        who_dies = np.asarray(sh['who_dies'], dtype=bool)
        if mask_alive:
            alive = ~who_dies[1:aNrm_pp.shape[0]]
            aNrm_pp[1:][alive] = np.nan
            pLvl_pp[1:][alive] = np.nan
        pcvd = (np.asarray(agent.history['MrkvNowPcvd'], dtype=np.int32)
                if 'MrkvNowPcvd' in getattr(agent, 'history', {}) else None)
        captures.append({
            # Sticky expectations: HARK selects the consumption rule by the
            # PERCEIVED combined state (get_controls, AggFiscalModel:1521);
            # exogenous (the update draw is a fixed history), so capturable.
            'Mrkv_pcvd': pcvd,
            'shock_Mrkv': np.asarray(sh['Mrkv'], dtype=np.int32),
            'shock_TranShk': np.asarray(sh['TranShk'], dtype=np.float64),
            'shock_PermShk': np.asarray(sh['PermShk'], dtype=np.float64),
            'shock_who_dies': who_dies,
            'aNrm_init_perperiod': aNrm_pp,
            'pLvl_init_perperiod': pLvl_pp,
        })
        agent.get_mortality = h.orig  # unhook
    if verbose:
        print(f"  [jax-replay-ad] capture: {len(captures)} cohorts, "
              f"T={captures[0]['shock_Mrkv'].shape[0]}, "
              f"{time.time()-t0:.1f}s", flush=True)
    _dump = os.environ.get("HAFISCAL_REPLAY_CAPTURE_DUMP", "")
    if _dump:
        # Harvest the tracked aggregate histories regardless of want_result
        # (2026-08-02 N2 ran with the harvest want_result-gated -> empty npz).
        # The *_Prev histories ARE the transacted series: mill_rule records
        # sow_state BEFORE overwriting it (AggFiscalModel.py:2383-2384), and
        # run_experiment's income line consumes exactly history['AggDemandFacPrev']
        # (:2505). CAVEAT: at iters=1 the dispatch runs its single experiment
        # at the identity-CFunc reset (AggFiscalModel.py:3362), where mill sows
        # CratioNext = CFunc(C_real) = 1.0 identically — the Cratio dumps are
        # vacuously 1.0 there; a discriminating dump needs iters >= 2.
        for _key in ('AggDemandFac', 'AggDemandFacPrev', 'Cratio', 'CratioPrev'):
            if not isinstance(result_box.get(f'{_key}_hist'), np.ndarray):
                try:
                    result_box[f'{_key}_hist'] = np.asarray(
                        eco_ref.history[_key], dtype=float).ravel()
                except Exception:
                    pass
        try:
            np.savez(_dump, **{k: v for k, v in result_box.items()
                               if isinstance(v, np.ndarray)})
            if verbose:
                print(f"  [jax-replay-ad] capture histories dumped: {_dump} "
                      f"({[k for k, v in result_box.items() if isinstance(v, np.ndarray)]})",
                      flush=True)
        except Exception as _e:
            print(f"  [jax-replay-ad] capture dump FAILED ({_e})", flush=True)
    if want_result:
        return captures, eco_ref, result_box
    return captures, eco_ref


def solve_ad_recession_jax_replay(eco, base_AggCons, num_max_iterations,
                                  convergence_cutoff, shock_type,
                                  verbose=True):
    """Replay-fed AD fixed point: HARK's update rule, JAX replay forward sim."""
    import jax
    jax.config.update('jax_enable_x64', True)  # HARK parity needs x64
    import jax.numpy as jnp
    from AggFiscalModel import CRule
    from jax_mc_ad import compute_AggDemandFac_path, extract_cfunc_table_per_period
    from jax_mc_hark_integration import extract_recession_kernel_inputs
    from jax_mc_ad_replay_v2 import simulate_jax_replay_v2
    from jax_mc_ad_multicohort import _maybe_get_per_agent_weights

    wall_start = time.time()
    # R6b / Leg-B replay-side consume (2026-08-03): run_recession_AD's sidecar
    # branch may have installed a warm-start belief into eco.CFunc and armed
    # eco._ad_warm_start (HAFISCAL_AD_BELIEF_SEED=1 + fingerprint match).
    # BOTH switch_shock_type below (calc_CFunc rebuilds identity rules) and
    # the explicit identity reset would clobber it — the reason the seed was
    # inert under this engine. Snapshot it here; reinstall after the reset.
    # WARM START ONLY: the loop below still runs to its own convergence
    # cutoff (the bench class: 6→1 iterations, ΔCratio ~1e-5; see
    # docs/ENV_FLAGS.md HAFISCAL_AD_BELIEF_SEED).
    _seed_CFunc = (deepcopy(eco.CFunc)
                   if getattr(eco, "_ad_warm_start", False) else None)
    # Guarded wholesale AD-converged cache (2026-08-03 ruling; plan
    # 20260803-1030h). A HIT supplies BOTH halves of the converged state:
    # the belief rides the seed-honor path below (the loop starts at A, so
    # its FIRST iteration is exactly the owner's double-check — one fresh
    # solve + one map step), and the cached POLICIES are kept aside for the
    # amendment-1 comparison and, on GUARD PASS, reinstalled as the kept
    # state. The guard's fresh work is discarded, so HIT outputs remain a
    # pure function of the cached state (byte-identical to the producer).
    # GUARD FAIL quarantines the entry and lets the loop continue cold.
    _adf_payload = None
    _adf_guard_active = False
    # Iteration-limited calls are a different economic object (the tm_a
    # arm-C1 gate caught 1stRoundAD being hijacked by the cache); a
    # convergence cache consumes only when convergence is requested.
    if num_max_iterations >= 2:
        try:
            from solution_cache import load_ad_full_cache as _adf_load
            _adf_payload = _adf_load(eco, shock_type, verbose=verbose)
        except Exception:
            _adf_payload = None
    if _adf_payload is not None:
        _seed_CFunc = deepcopy(_adf_payload["CFunc"])
        _adf_guard_active = True
        _adf_meta = _adf_payload.get("meta", {}) or {}
        if verbose:
            print(f"  [ad-full] HIT {shock_type}: guard armed "
                  f"(producer iters={_adf_meta.get('iterations')}, "
                  f"final_step={_adf_meta.get('final_step')}, "
                  f"modulus~{_adf_meta.get('modulus_est')})", flush=True)
    eco.switch_shock_type(shock_type)
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates
    n_macro = n_combined // J
    num_exp = eco.num_experiment_periods
    ADelasticity = eco.demand_ADelasticity
    eco.ADelasticity = ADelasticity

    captures, eco_ref = capture_exogenous_panel(eco, shock_type, verbose=verbose)
    # Warm-start iter 1 from the ref's recession-space solution (same shock
    # type, identity belief) — the same write-back the auto-init path does.
    for a_dst, a_src in zip(eco.agents, eco_ref.agents):
        a_dst.solution = a_src.solution
    # Retained for the ad-full guard's FAIL path: a byte-certified cold
    # fallback must restart the inner solver from the SAME state the cold
    # path starts from (references only — no copy).
    _init_solutions = [a.solution for a in eco.agents]
    del eco_ref

    # Reset belief to identity — unless a warm seed was armed (above), in
    # which case start the loop from the sidecar belief. The loop's macro
    # rules are the per-block representatives of the combined belief
    # (Macro_2_Micro images are macro-block-constant by construction; for a
    # cross-engine sidecar the extraction is a projection — still only a
    # starting guess, the loop converges to its own fixed point).
    if _seed_CFunc is not None and len(_seed_CFunc) == n_combined:
        eco.CFunc = _seed_CFunc
        for agent in eco.agents:
            agent.CFunc = eco.CFunc
        if verbose:
            print("  [jax-replay-ad] AD-belief seed honored: loop starts "
                  "from the sidecar belief (identity reset skipped; loop "
                  "runs to its own cutoff unchanged)", flush=True)
    else:
        _seed_CFunc = None  # length mismatch degrades to the flat start
        eco.CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)]
                     for _ in range(n_combined)]
        for agent in eco.agents:
            agent.CFunc = eco.CFunc

    act_T = eco.agents[0].T_sim
    EconomyMrkv_init = list(np.arange(1, num_exp + 1) * 2 + 1) + [1] * 12 + [0] * 20
    EconomyMrkv_path = (EconomyMrkv_init + [0] * act_T)[:act_T]
    macros = np.array(EconomyMrkv_path, dtype=int)
    if _seed_CFunc is not None:
        MacroCFunc = [[CRule(float(eco.CFunc[i * J][j * J].intercept),
                             float(eco.CFunc[i * J][j * J].slope))
                       for j in range(n_macro)] for i in range(n_macro)]
    else:
        MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)]
                      for _ in range(n_macro)]

    cohort_weights = _maybe_get_per_agent_weights(eco.agents)
    base_AggCons = np.asarray(base_AggCons)
    per_cohort_inp = [extract_recession_kernel_inputs(a, scenario=shock_type)
                      for a in eco.agents]

    # Map-evaluation fidelity knob (diagnosis 2026-08-01): the kernel evaluates
    # policies through a per-period cFunc table interpolated on m_grid; HARK
    # evaluates cFuncs exactly. Path-DIFFERENTIAL errors of ~5e-5 from this
    # interpolation move the AD welfare cells by percents (ratio of small
    # differences). k>1 inserts k-1 midpoints per interval (endpoints and
    # geometry preserved) to test/shrink that error.
    _densify = max(1, int(os.environ.get("HAFISCAL_REPLAY_MGRID_DENSIFY", "1")))

    def _densified(m):
        if _densify == 1:
            return m
        segs = [np.linspace(m[i], m[i + 1], _densify + 1)[:-1]
                for i in range(len(m) - 1)]
        return np.concatenate(segs + [m[-1:]])

    # KNOT-ALIGNED TABLES (owner-directed 2026-08-01): linear interpolation of a
    # table sampled from a piecewise-linear function is exact except in cells
    # straddling the function's OWN knots. HARK's cFunc is LowerEnvelope2D over
    # LinearInterp-family components, so aligning the table nodes with the
    # components' m-knots makes the kernel's evaluation HARK's evaluation, up
    # to the per-(t,state) envelope crossings — which cannot all be shared-grid
    # nodes without an ~800 MB table, so a dense low-m patch bounds their error
    # to the ~1e-5 class instead (the crossings live at low m, where the
    # borrowing-constraint arm binds; unit-diff worst agents sat at m≲1).
    # Knot LOCATIONS come from the solve grid and are iteration-invariant, so
    # they are extracted once per cohort from the iter-1 solution.
    _knot_tables = os.environ.get(
        "HAFISCAL_REPLAY_KNOT_TABLES", "").lower() in ("1", "on", "true")

    def _extract_m_knots(cf, out):
        """Best-effort recursive m-knot extraction from HARK interpolants."""
        if cf is None:
            return
        xl = getattr(cf, "x_list", None)
        if xl is not None:
            out.append(np.asarray(xl, dtype=float).ravel())
        for sub in getattr(cf, "xInterpolators", []) or []:
            _extract_m_knots(sub, out)
        for name in ("functions", "func", "f1", "f2"):
            sub = getattr(cf, name, None)
            if isinstance(sub, (list, tuple)):
                for s in sub:
                    _extract_m_knots(s, out)
            elif sub is not None and name != "x_list":
                _extract_m_knots(sub, out)

    def _knot_grid(agent, base_grid, n_states):
        chunks = [np.asarray(base_grid, dtype=float)]
        for j in range(n_states):
            try:
                _extract_m_knots(agent.solution[0].cFunc[j], chunks)
            except Exception:
                pass
        lo = max(float(np.min(base_grid)), 1e-3)
        chunks.append(np.geomspace(lo, 3.0, 300))     # envelope-crossing patch
        g = np.unique(np.concatenate(chunks))
        g = g[(g >= np.min(base_grid)) & (g <= np.max(base_grid))]
        return np.ascontiguousarray(g)

    _knot_grid_cache = {}

    iter_history = []
    converged = False
    _step_series = []   # ad-full amendment 3: producer step series -> entry meta
    per_cohort_cLvl = [None] * len(eco.agents)
    per_cohort_AggInc = [None] * len(eco.agents)
    AggCons_total = np.zeros(act_T)

    # Self-document the compute device once per run: the 2026-08-01 G-GPU-4
    # verdict was mislabeled partly because nothing recorded which backend
    # the kernels actually used (the guard counted env lines, and 1/4 was
    # just slot arithmetic). One line makes every future run adjudicable.
    try:
        import jax as _jax_plat
        from solution_cache import record_reuse_event as _rre_plat
        _rre_plat("platform", "observed", "none",
                  jax_backend=str(_jax_plat.default_backend()),
                  panel_dtype=("float32" if os.environ.get(
                      "HAFISCAL_REPLAY_FP32", "").lower() in ("1", "on", "true")
                      else "float64"))
    except Exception:
        pass
    if verbose:
        try:
            import jax as _jax_dev
            _fp32 = os.environ.get("HAFISCAL_REPLAY_FP32", "").lower() in ("1", "on", "true")
            print(f"  [jax-replay-ad] jax backend: {_jax_dev.default_backend()} "
                  f"devices={_jax_dev.devices()} "
                  f"panel_dtype={'float32' if _fp32 else 'float64'}", flush=True)
        except Exception:
            pass

    # M0 stage decomposition (GPU re-eval plan §1): per-iteration walls for
    # solve / tables / kernel / rest, printed under HAFISCAL_REPLAY_STAGE_TIMES.
    _stage_times = os.environ.get("HAFISCAL_REPLAY_STAGE_TIMES", "").lower() in ("1", "on", "true")

    # R2 state-restricted tables (2026-08-02, default ON; HAFISCAL_TABLE_RESTRICT=off
    # reverts): the deterministic experiment path occupies exactly ONE macro
    # state per period, so per-period tables need only that macro's J micro
    # rows — (T, J, M) instead of (T, n_combined, M), a ~n_macro-fold cut in
    # the dominant AD-iteration stage. The invariant is GUARDED here against
    # every captured panel (protects future perception/timing changes, e.g.
    # StickyE selecting rules by a lagged perceived macro state): any
    # violation falls back to full tables with a loud warning — correctness
    # is unconditional, the restriction is only an optimization.
    _restrict = os.environ.get("HAFISCAL_TABLE_RESTRICT", "").lower() not in ("off", "0")
    if _restrict:
        _macros_col = macros[:, None]
        for _ci, _cap in enumerate(captures):
            if not np.all(_cap['shock_Mrkv'] // J == _macros_col):
                print(f"  [jax-replay-ad] R2 GUARD: cohort {_ci} has agent "
                      "states outside the period's macro block — falling back "
                      "to FULL (unrestricted) tables.", flush=True)
                _restrict = False
                break

    for it in range(num_max_iterations):
        iter_start = time.time()
        eco.solve()
        _t_solve = time.time() - iter_start
        _t_tables = 0.0
        _t_kernel = 0.0

        Cratio_obs = np.zeros(act_T)
        Cratio_obs[0] = MacroCFunc[0][macros[0]].intercept
        for t in range(1, act_T):
            i, j = macros[t - 1], macros[t]
            rule = MacroCFunc[i][j]
            Cratio_obs[t] = rule.intercept + rule.slope * (Cratio_obs[t - 1] - 1.0)
        # C-ARGUMENT timing (adjudicated by code reading, 2026-08-02): HARK's
        # sim evaluates cFunc(m, C) at the PREVIOUSLY-SOWN aggregate Cratio —
        # mill_rule at t sows CratioNext = CFunc[s_{t-1}][s_t](C_realized_t)
        # for t+1 (AggFiscalModel.py:2378/2400), and the loop's slope-0 rules
        # make that the Prev-shifted recursion. The head is 1.0, NOT
        # Cratio_obs[0]: run_experiment's intended intercept-init writes the
        # DEAD key 'CratioNow' (:2447 — rename survivor; that spelling is live
        # only in EstimAggFiscalModel), so the live sow_init['Cratio'] keeps
        # update()'s 1.0 (:2413; HARK core.py:2826 copies sow_vars keys only).
        # ADF is different: its t=0 init writes the LIVE key (:2449), so the
        # shifted ADF_path below keeps its own head — HARK's t=0 is internally
        # inconsistent (income uses ADF(C_obs[0]) while agents see C=1.0;
        # BUG-066) and the replay reproduces it faithfully.
        if os.environ.get("HAFISCAL_REPLAY_CRATIO_PREV", "").lower() in ("1", "on", "true"):
            Cratio_tab = np.concatenate([[1.0], Cratio_obs[:-1]])
        else:
            Cratio_tab = Cratio_obs
        ADF_path = compute_AggDemandFac_path(
            Cratio_obs, EconomyMrkv_path, 1, ADelasticity).astype(np.float64)
        # ADF TIMING (found 2026-08-01, unit-diff phase 2): HARK's sim
        # transacts period t at the PREVIOUSLY SOWN AggDemandFac (millRule
        # computes ADF from period-t aggregates and sows it for t+1; sow-init
        # gives t=0 the ADF of the initial state). Feeding the unshifted path
        # left a 4.3e-4 aggregate deviation; the Prev-shifted REALIZED path
        # closed it to 5.3e-7. At the loop's fixed point the realized path
        # equals the belief path, so the Prev-shifted BELIEF path yields the
        # IDENTICAL fixed-point condition as HARK's endogenous timing — no
        # cross-cohort coupling needed.
        ADF_path = np.concatenate([ADF_path[:1], ADF_path[:-1]])

        AggCons_total = np.zeros(act_T)
        cohort_times = []
        for c_idx, agent in enumerate(eco.agents):
            c_start = time.time()
            inp = per_cohort_inp[c_idx]
            if _knot_tables:
                if c_idx not in _knot_grid_cache:
                    _knot_grid_cache[c_idx] = _knot_grid(
                        agent, np.asarray(inp['m_grid'], dtype=float),
                        n_combined)
                    if verbose and it == 0:
                        print(f"  [jax-replay-ad] knot-aligned grid cohort "
                              f"{c_idx}: {len(_knot_grid_cache[c_idx])} nodes "
                              f"(base {len(inp['m_grid'])})", flush=True)
                m_grid = _knot_grid_cache[c_idx]
            else:
                m_grid = _densified(np.asarray(inp['m_grid']).astype(np.float64))
            _t0 = time.time()
            cfunc_table = extract_cfunc_table_per_period(
                agent, Cratio_tab, m_grid,
                n_combined=n_combined,
                macro_path=(macros if _restrict else None),
                J=(J if _restrict else None)).astype(np.float64)
            _t_tables += time.time() - _t0
            cap = captures[c_idx]
            _t0 = time.time()
            inc, cons, panel = simulate_jax_replay_v2(
                cap['aNrm_init_perperiod'][0], cap['pLvl_init_perperiod'][0],
                ADF_path, cfunc_table, jnp.asarray(m_grid),
                cap['shock_Mrkv'], cap['shock_TranShk'], cap['shock_PermShk'],
                cap['shock_who_dies'],
                cap['aNrm_init_perperiod'], cap['pLvl_init_perperiod'],
                Rfree_macro=jnp.asarray(inp['Rfree_macro'], dtype=jnp.float64),
                PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro'],
                                             dtype=jnp.float64),
                Splurge=inp['Splurge'], act_T=act_T, J=J,
                restricted=_restrict)
            AggCons_total += np.asarray(cons) * cohort_weights[c_idx]
            per_cohort_AggInc[c_idx] = np.asarray(inc)
            per_cohort_cLvl[c_idx] = np.asarray(panel)
            _t_kernel += time.time() - _t0
            cohort_times.append(time.time() - c_start)

        Cratio_hist = AggCons_total / base_AggCons

        new_MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)]
                          for _ in range(n_macro)]
        new_MacroCFunc[0][3] = CRule(float(Cratio_hist[0]), 0.0)
        for j in range(num_exp - 1):
            new_MacroCFunc[2 * j + 3][2 * j + 5] = CRule(float(Cratio_hist[j + 1]), 0.0)
        new_MacroCFunc[2 * num_exp + 1][1] = CRule(float(Cratio_hist[num_exp]), 0.0)
        new_MacroCFunc[1][1] = CRule(
            float(np.mean(Cratio_hist[num_exp + 1:num_exp + 10])), 0.0)

        Old_CFunc = eco.CFunc
        New_CFunc = eco.Macro_2_Micro_CFunc(new_MacroCFunc)
        step = eco.Cfunc_iter_stepsize
        Step_CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)]
                      for _ in range(n_combined)]
        for ii in range(n_combined):
            for jj in range(n_combined):
                Step_CFunc[ii][jj].slope = (
                    Old_CFunc[ii][jj].slope
                    + step * (New_CFunc[ii][jj].slope - Old_CFunc[ii][jj].slope))
                Step_CFunc[ii][jj].intercept = (
                    Old_CFunc[ii][jj].intercept
                    + step * (New_CFunc[ii][jj].intercept
                              - Old_CFunc[ii][jj].intercept))
        eco.CFunc = Step_CFunc
        for agent in eco.agents:
            agent.CFunc = eco.CFunc
        MacroCFunc = new_MacroCFunc

        Total_Diff = eco.Compare_CFunc_Convergence(Old_CFunc, eco.CFunc)
        _step_series.append(float(Total_Diff))
        iter_history.append({'iter': it + 1, 'Cratio_hist': Cratio_hist.copy(),
                             'Total_Diff': Total_Diff,
                             'wall': time.time() - iter_start,
                             'cohort_times': cohort_times})
        if verbose:
            if _stage_times:
                _t_rest = (time.time() - iter_start) - _t_solve - _t_tables - _t_kernel
                print(f"  [jax-replay-ad M0] iter {it+1}: solve={_t_solve:.1f}s "
                      f"tables={_t_tables:.1f}s kernel={_t_kernel:.1f}s rest={_t_rest:.1f}s", flush=True)
            print(f"  [jax-replay-ad iter {it+1}] Total_Diff={Total_Diff:.4g}, "
                  f"Cratio[0]={Cratio_hist[0]:.4f}, "
                  f"wall={time.time()-iter_start:.1f}s", flush=True)
        if _adf_guard_active and it == 0:
            # The owner's double-check (2026-08-03 ruling): iteration 1 was
            # a fresh solve + one map step under the cached belief. Verify
            # (amendment 2) the step against the calibrated threshold and
            # (amendment 1) the fresh policies against the CACHED policies;
            # then DISCARD the fresh work and keep the cached state.
            _pfs = float((_adf_payload.get("meta", {}) or {})
                         .get("final_step") or 0.0)
            _gthr = max(2.0 * convergence_cutoff, 2.0 * _pfs)
            _step_ok = Total_Diff < _gthr
            _pol_dev = None
            if _step_ok:
                try:
                    from solution_cache import compare_policies_max_rel as _adf_cmp
                    _pol_dev = _adf_cmp(eco.agents, _adf_payload["solutions"])
                except Exception as _e_cmp:
                    print(f"  [ad-full] GUARD: policy-compare errored "
                          f"({_e_cmp}); treating as FAIL.", flush=True)
            if _step_ok and _pol_dev is not None and _pol_dev < 1e-3:
                converged = True
                eco.CFunc = Old_CFunc              # keep the cached belief
                for agent in eco.agents:
                    agent.CFunc = eco.CFunc
                for agent, _sol in zip(eco.agents, _adf_payload["solutions"]):
                    agent.solution = _sol           # keep the cached policies
                    agent.get_economy_data(eco)
                try:
                    from solution_cache import record_reuse_event as _rre_gp
                    _rre_gp("ad_full", "guard_pass", "exact",
                            engine="jax_mc_replay_ad", shock_type=shock_type,
                            step=float(Total_Diff), step_threshold=float(_gthr),
                            policy_dev=float(_pol_dev))
                except Exception:
                    pass
                if verbose:
                    print(f"  [ad-full] GUARD PASS: step={Total_Diff:.3g} "
                          f"(thr {_gthr:.3g}), policy_dev={_pol_dev:.3g} "
                          f"(thr 1e-3) — cached state kept; the check's "
                          f"fresh work discarded.", flush=True)
                break
            try:
                from solution_cache import record_reuse_event as _rre_gf
                _rre_gf("ad_full", "guard_fail_quarantined", "exact",
                        engine="jax_mc_replay_ad", shock_type=shock_type,
                        step=float(Total_Diff), step_threshold=float(_gthr),
                        policy_dev=(None if _pol_dev is None else float(_pol_dev)))
            except Exception:
                pass
            print(f"  [ad-full] GUARD FAIL for {shock_type}: "
                  f"step={Total_Diff:.4g} (thr {_gthr:.4g}), "
                  f"policy_dev={_pol_dev} — quarantining the entry; "
                  f"continuing with the COLD solve.", flush=True)
            try:
                from solution_cache import quarantine_ad_full_entry as _adf_q
                _adf_q(eco, shock_type, verbose=verbose)
            except Exception:
                pass
            _adf_guard_active = False
            # FULL RESET to the identity belief (gate G3 finding 2026-08-03):
            # merely continuing the loop inherits the cached (possibly
            # poisoned) belief as its starting point and converges to a
            # DIFFERENT in-ball point than the certified cold path (measured
            # 2.6e-3). Resetting makes the fallback byte-identical to a true
            # cold run.
            eco.CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)]
                         for _ in range(n_combined)]
            for agent in eco.agents:
                agent.CFunc = eco.CFunc
            for agent, _s0 in zip(eco.agents, _init_solutions):
                agent.solution = _s0   # inner-solver start = the cold path's
            MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)]
                          for _ in range(n_macro)]
            _step_series = []
            # no break: the next iterations ARE the certified cold run, and
            # convergence republishes a fresh entry below.
        elif Total_Diff < convergence_cutoff:
            converged = True
            # Belief consistency (2026-07-29 ruling): policies were solved
            # under Old_CFunc; discard the marginal final step.
            eco.CFunc = Old_CFunc
            for agent in eco.agents:
                agent.CFunc = eco.CFunc
            break

    assert 0.8 < float(Cratio_hist[0]) < 1.2, (
        f"replay-AD converged Cratio[0]={Cratio_hist[0]:.4f} outside [0.8,1.2] "
        f"(RECONCILED-001 bound)")

    # ad-full publish (2026-08-03 ruling): the state here is the rolled-back
    # belief-consistent pair. save skips if the entry already exists (the
    # guard-pass path), and after a guard quarantine the path is clear so
    # the cold re-converge republishes a fresh entry. Best-effort.
    if converged:
        try:
            from solution_cache import save_ad_full_cache as _adf_save
            _adf_save(eco, shock_type, step_series=_step_series,
                      tol=convergence_cutoff, verbose=verbose)
        except Exception:
            pass

    if verbose:
        print(f"  [jax-replay-ad] {len(iter_history)} iters, "
              f"converged={converged}, wall={time.time()-wall_start:.1f}s",
              flush=True)
    return {
        'iter_history': iter_history,
        'final_Cratio_hist': Cratio_hist,
        'final_AggCons': AggCons_total,
        'final_AggIncome': (np.sum([w * a for w, a in
                                    zip(cohort_weights, per_cohort_AggInc)],
                                   axis=0)
                            if per_cohort_AggInc[0] is not None else None),
        'final_cLvl_all_splurge': (np.concatenate(per_cohort_cLvl, axis=1)
                                   if per_cohort_cLvl[0] is not None else None),
        'per_cohort_cLvl': per_cohort_cLvl,
        'per_cohort_AggInc': per_cohort_AggInc,
        'cohort_weights': cohort_weights,
        'converged': converged,
        'wall_time': time.time() - wall_start,
    }
