"""
Key extraction: gather all numerical-result-affecting params from an eco/agent
into a stable dict, then SHA256 it.

Includes:
- Per-cohort solve-time numerical params (CRRA, DiscFac, Rfree, ...)
- Grid params (aXtraGrid contents, Cgrid contents)
- IncShkDstn atoms + probabilities
- MrkvArray
- AD-loop params (num_max_iterations_solvingAD, convergence_tol_solvingAD,
  Cfunc_iter_stepsize)
- ADelasticity
- Forward-sim params used during AD: AgentCount, shuffle on/off, seeds,
  init-panel method, MC method (HARK vs JAX)
- The whitelisted HAFISCAL_* env flags in ``_HAFISCAL_NUMERICAL_ENV_VARS``
  (see that tuple for the completeness criterion and the per-flag rationale)
- Provenance: HARK commit SHA, HAFiscal commit SHA, Python major.minor

Explicitly NOT in the key (numerical-equivalent across these):
- T_sim, AgentCount when not used for AD (only for post-AD reporting MC)
- HAFISCAL_JAX_MC_USE_2D_LIFT / VMAP_SEEDS / BATCH_TABLES / LAZY_PANEL /
  VMAP_COHORTS — these are speedup-only optimizations, parity-validated
- HAFISCAL_PARALLEL_SOLVE (just changes cohort scheduling, not output)
- HAFISCAL_USE_JAX_SOLVER (validated to give same converged cFunc)
- JAX backend (CPU vs GPU)
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import numpy as np


# Whitelist of HAFISCAL_* env vars that affect the AD-converged solve output
# (the cFunc) and MUST be in the cache key.
#
# COMPLETENESS CRITERION (what belongs here, and why this list is short):
# An env flag needs to be in THIS tuple only if its numerical effect on the
# solved cFunc is NOT already captured by the gathered agent/eco params
# (DiscFac, PermGroFac, Rfree, aXtraGrid, Cgrid, IncShkDstn, MrkvArray, the
# AD-loop params — see gather_solve_inputs / _agent_params_dict / _ad_params_dict).
# Most numerical flags act THROUGH those params and are therefore captured
# transitively: e.g. HAFISCAL_TM_AMAX / TM_ACOUNT / AXTRA_COUNT / FAST_GRIDS
# only reshape aXtraGrid (hashed); INTERPRETATION / PERM_DURING_UNEMP /
# PLVL_GROWS_DURING_UNEMP change IncShkDstn/PermGroFac (hashed); GICX_MODE /
# the urate/agentcount calibration flags feed the estimation step that PRODUCES
# the DiscFac atoms + grids (hashed). The flags listed below are kept EXPLICITLY
# because they (a) change a captured param but the calibration is estimated
# PAIRED with a specific regime so cross-loading is meaningless even if the
# hash technically differs (PERMGROFAC_FIX, GIC_SHAVE_ON_GPF), or (b) select a
# distinct forward-sim / solve CODE PATH whose output is only ~kernel-parity
# (USE_JAX_2B*), or (c) the shuffle/edu-share/CFunc-offset/encoding switches
# whose effect is not fully reconstructible from the static agent params alone.
# Pure speedup / scheduling / reporting flags are intentionally EXCLUDED (see
# the "Explicitly NOT in the key" list in the module docstring).
#
# This list is COMPLETE for the cFunc-affecting class as of 2026-07-05 (the last
# gap, HAFISCAL_PF_DECAY_EXTRAP, was added then; before that
# HAFISCAL_GIC_SHAVE_ON_GPF on 2026-06-12 — see BUG-059).
_HAFISCAL_NUMERICAL_ENV_VARS = (
    "HAFISCAL_PLVL_GROWS_DURING_UNEMP",
    "HAFISCAL_TM_CFUNC_OFFSET",
    "HAFISCAL_AGGREGATE_BY_EDU_SHARE",
    "HAFISCAL_UI_STATE_ENCODING",
    "HAFISCAL_SHUFFLE_MRKV_TRANSITION",
    "HAFISCAL_AGENTCOUNT_D",
    "HAFISCAL_AGENTCOUNT_H",
    "HAFISCAL_AGENTCOUNT_C",
    "HAFISCAL_INTERPRETATION",
    "HAFISCAL_WRAPPER_EDTYPES",
    "HAFISCAL_GICX_MODE",
    "HAFISCAL_NM_START_FROM_SAVED",
    # BUG-053: the GPF-based beta-cap shave changes which College beta atoms are
    # clipped -> numerically distinct solutions across flag flips. Added
    # 2026-06-12 (was the known gap recorded in docs/ENV_FLAGS.md; same failure
    # class as the PERMGROFAC_FIX omission fixed 2026-06-04).
    "HAFISCAL_GIC_SHAVE_ON_GPF",
    # BUG-047: PERMGROFAC_FIX={0,1} toggles the PermGroFac^(-CRRA) factor in the
    # solver's marginal value -> changes the cFunc by ~6-7%. A FIX=0 (buggy) and a
    # FIX=1 (fixed) solution are NUMERICALLY DISTINCT and MUST NOT be cross-loaded.
    # Critically: the discount-factor calibration (beta) is ESTIMATED PAIRED with a
    # specific FIX regime (beta re-absorbs the fix to hit K/Y). Serving a cached
    # solution from the other regime to a given beta is a meaningless mismatched
    # pairing (a model that hits no targets). So this MUST be in the key.
    "HAFISCAL_PERMGROFAC_FIX",
    # (HAFISCAL_GIC_SHAVE_ON_GPF is listed once, above — the duplicate second entry was
    # de-duplicated 2026-06-22 per the Plan-2 key-completeness audit. It was harmless to
    # the hash, _env_dict being a dict, but a maintenance trap. See BUG-053 above.)
    # 2B JAX-native iter loop replaces HARK's solve_agent. Parity vs HARK is
    # ~1e-3 (kernel-parity range), NOT bit-identical — so a 2B-solved cache
    # entry shouldn't be loaded under HARK mode. Treat as a numerically-
    # distinct path; the conservative thing is to key on it.
    "HAFISCAL_USE_JAX_2B",
    "HAFISCAL_USE_JAX_2B_VMAP",  # vmap variant of 2B; numerically equivalent
                                  # to serial 2B (parity 4e-10) but keep in
                                  # the key for forensics (different code path).
    # F1.1 (2026-07-23): under the power-law default the 2B paths attach the
    # production power-law measured-Q tails post-solve (jax2b_powerlaw_tail);
    # this escape hatch disables the attach, changing the produced cFunc above
    # the grid top at FIXED (USE_JAX_2B, PF_DECAY_EXTRAP) — so it must key the
    # cache (same never-cross-load class as PF_DECAY_EXTRAP itself).
    "HAFISCAL_JAX2B_ALLOW_NO_TAIL",
    # Step-2 multi-state global-Newton (NAMG) base solver (default OFF). Selects a
    # DISTINCT base-solve code path whose cFunc is only ~kernel-parity (~3.6e-3) vs
    # the HARK-EGM default — same class as USE_JAX_2B above. The path is structurally
    # confined to num_macro_states==1 (AD-off), which is exactly where solution_cache
    # (AD-on, Step-5) is NOT used, so a collision is already impossible; these entries
    # are the belt-and-suspenders guard so that a NAMG-solved entry can never
    # cross-load against an EGM-keyed one. Both the current flag and its deprecated
    # alias are keyed: either one enables the path (see _step2_namg_enabled), so both
    # must change the key.
    "HAFISCAL_STEP2_NAMG",
    "HAFISCAL_STEP2_ANDERSON",  # DEPRECATED alias of HAFISCAL_STEP2_NAMG
    # Step-5a ConsumedATI-Markov stationary solver (default OFF; P4b of the
    # power-law-tail meld, 2026-07-23). Selects a DISTINCT solve code path for
    # qualifying AD-off agents whose cFunc is only ~same-fixed-point parity
    # (~1e-9 consumed(a) vs the deep same-form reference; the stock arm's own
    # 1e-6-tolerance stopping distance separates them) — same never-cross-load
    # class as HAFISCAL_STEP2_NAMG / USE_JAX_2B. The MIN_DISCFAC threshold
    # selects WHICH atoms take the ATI engine (patience routing), so two runs
    # with different thresholds have differently-composed solution sets — it
    # must key the cache exactly like the on/off flag itself.
    "HAFISCAL_STEP5_ATI",
    "HAFISCAL_STEP5_ATI_MIN_DISCFAC",
    # BUG-062 (PR-3): opt-in per-Markov-state PF decay extrapolation for the 2D
    # AggShock cFunc + the constrained-PF terminal start. Selects a distinct
    # solve code path whose converged cFunc differs above the top asset
    # gridpoint — same never-cross-load class as PERMGROFAC_FIX. Added
    # 2026-07-05 (closes the known gap recorded in docs/ENV_FLAGS.md; NOTE this
    # rewrites every cache key once — the gitignored dev cache re-solves).
    "HAFISCAL_PF_DECAY_EXTRAP",
    # 2026-07-23 (default-ON flip): the tail-exponent SOURCE also changes the
    # converged cFunc at a given grid (slope-Q vs the measured two-secant Q
    # attach different tails), so it must key the cache. Grid-shape flags
    # (AXTRA_COUNT / SOLVE_AMAX / PF_DECAY_AMAX_MULT) are already covered via
    # the aXtraGrid contents in the key.
    "HAFISCAL_PF_DECAY_Q",
    # 2026-07-26 (dist-grid-top scoping, component B): selects HOW the TM
    # distribution-grid top (dist_aGrid_max) is resolved when no explicit value
    # is passed to build_tm_agg_fiscal_a — 'global' (default: the
    # HAFISCAL_TM_AMAX env else legacy 500) vs 'per_atom' (each agent's own
    # wealth-weighted ergodic quantile via
    # adaptive_grid_tm.per_atom_dist_aGrid_max). HAFISCAL_TM_AMAX itself is
    # captured transitively (see the COMPLETENESS CRITERION above), but the
    # MODE is a resolution-PATH selector whose per-atom tops are computed
    # downstream of the hashed static agent params — the same must-key class
    # as the ATI engine-selection precedent (HAFISCAL_STEP5_ATI above): runs
    # under different modes build different TM dist grids (hence different
    # TM-ergodic init panels / TM-side outputs consumed during AD) at
    # identical hashed params and MUST NOT cross-load. (Like PF_DECAY_EXTRAP's
    # 2026-07-05 addition, this rewrites every cache key once — the gitignored
    # dev cache re-solves; numerical results are unchanged.)
    "HAFISCAL_DIST_TOP_MODE",
    # 2026-07-26 (dist-grid-top scoping, P4' tail state): appends one analytic
    # Pareto TAIL STATE per micro state to the a-indexed baseline-ergodic TM
    # (the TM becomes (A+1)*J with a redirected top-clip inflow and an
    # m^alpha stay / truncated-Pareto re-entry outflow — tm_methods.
    # _build_period_tm_a_tail), and routes the estimation read-out through
    # the Pareto-segment expansion (tail_state_readout). Same must-key class
    # as HAFISCAL_DIST_TOP_MODE directly above: a build-PATH selector whose
    # TM-side outputs (ergodic init panels / estimation moments) differ at
    # identical hashed static params and MUST NOT cross-load. Default off is
    # byte-identical; the flag also hard-disables the separate _tm_a_cache
    # warm-start cache at the build site (its key cannot describe the tail).
    "HAFISCAL_DIST_TAIL_STATE",
    # 2026-07-26 (owner ruling: remove the undocumented QE-era maximum-age
    # cap): overrides T_age (unset=status quo 200/100; 'none'=uncapped;
    # int=that cap). T_age does not enter the SOLVE, but the AD solution
    # cache stores post-AD economy state whose SIMULATED ergodics (effective
    # mortality, pLvl/age chains, tail exponent) all depend on it — entries
    # under different caps MUST NOT cross-load. Same rewrite-once cost note
    # as above.
    "HAFISCAL_T_AGE",
    # 2026-08-04 (gridpoint-reduction T2a, gap closed retroactively): the
    # per-C-slice interpolant selector (linear default | hermite EGM-exact
    # MPC slices). Changes the in-solver interpolant and therefore the
    # CONVERGED cFunc at identical hashed params — the same never-cross-load
    # class as USE_JAX_2B. Every T2a run to date disabled the cache, so no
    # contaminated entry exists; this entry makes that a guarantee.
    "HAFISCAL_SLICE_INTERP",
    # 2026-08-04 (universal-solver-acceleration plan 20260804-0745h): the
    # accelerated fixed-point driver (off | aitken | anderson). Converges to
    # the SAME fixed point but stops at a different iterate (stopping-point
    # class, like STEP5_ATI's ~1e-6 separation) — must-key so an accelerated
    # entry never cross-loads against a plain-EGM one.
    "HAFISCAL_SOLVE_ACCEL",
)


def sim_cache_enabled():
    """Gate for the (design-only, NOT-yet-materialized) forward-sim panel cache —
    Plan-2 STEP 4. The SIM-cache key helpers (``gather_sim_inputs`` / ``verify_sim_panel``)
    exist for design + unit-test, but no run path consults a sim cache yet; this reader is
    the single point that would gate it once materialized. Default OFF."""
    return os.environ.get("HAFISCAL_USE_SIM_CACHE", "0") == "1"


def _git_sha(repo_dir):
    """Return short git SHA of HEAD in repo_dir, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _hafiscal_root():
    """Locate the HAFiscal repo root from this file's location."""
    here = os.path.abspath(os.path.dirname(__file__))
    # Walk up until we find .git
    cur = here
    while cur and cur != "/":
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        cur = os.path.dirname(cur)
    return None


def _hark_root():
    """Locate the HARK install dir for SHA tracking."""
    try:
        import HARK
        return os.path.dirname(os.path.dirname(HARK.__file__))
    except ImportError:
        return None


def _canonicalize_array(arr):
    """Convert numpy array to a stable JSON-serializable form."""
    a = np.asarray(arr)
    return {
        "_array": True,
        "shape": list(a.shape),
        "dtype": str(a.dtype),
        # Use float64 hash for floats (avoid platform-specific repr issues).
        # For exact reproducibility, hash the bytes.
        "sha256": hashlib.sha256(np.ascontiguousarray(
            a.astype(np.float64) if a.dtype.kind == "f" else a
        ).tobytes()).hexdigest(),
    }


def _canonicalize_dstn(dstn):
    """Canonicalize a HARK distribution (pmv + atoms)."""
    return {
        "_dstn": True,
        "pmv": _canonicalize_array(dstn.pmv),
        "atoms": [_canonicalize_array(a) for a in dstn.atoms],
    }


def _canonicalize_value(v):
    """Convert any param to a stable JSON-serializable form."""
    if isinstance(v, np.ndarray):
        return _canonicalize_array(v)
    if isinstance(v, (list, tuple)):
        return [_canonicalize_value(x) for x in v]
    if isinstance(v, (int, float, str, bool, type(None))):
        return v
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    # HARK distribution-like
    if hasattr(v, "pmv") and hasattr(v, "atoms"):
        return _canonicalize_dstn(v)
    # Indexable container of distributions
    if hasattr(v, "__iter__") and not isinstance(v, dict):
        try:
            return [_canonicalize_value(x) for x in v]
        except Exception:
            pass
    # Fallback: string repr (may break determinism; ideally avoid)
    return f"<unencoded:{type(v).__name__}:{repr(v)[:120]}>"


def _agent_params_dict(agent):
    """Per-cohort agent params that affect the solve output."""
    params = {}
    # Scalar / list params
    for attr in (
        "CRRA", "DiscFac", "BoroCnstArt", "T_age", "T_cycle", "cycles",
        "Splurge",
    ):
        if hasattr(agent, attr):
            params[attr] = _canonicalize_value(getattr(agent, attr))
    # Array / list params
    for attr in (
        "Rfree", "LivPrb", "PermGroFac", "PermGroFacAgg",
        "aXtraGrid", "Cgrid",
    ):
        if hasattr(agent, attr):
            params[attr] = _canonicalize_value(getattr(agent, attr))
    # IncShkDstn — list of distributions per Markov state per cycle
    if hasattr(agent, "IncShkDstn"):
        try:
            iss = agent.IncShkDstn
            params["IncShkDstn"] = _canonicalize_value(iss)
        except Exception as e:
            params["IncShkDstn_error"] = str(e)
    # MrkvArray and CondMrkvArrays
    if hasattr(agent, "MrkvArray"):
        params["MrkvArray"] = _canonicalize_value(agent.MrkvArray)
    if hasattr(agent, "CondMrkvArrays"):
        params["CondMrkvArrays"] = _canonicalize_value(agent.CondMrkvArrays)
    # Number of base Mrkv states (affects state-space size)
    if hasattr(agent, "num_base_MrkvStates"):
        params["num_base_MrkvStates"] = int(agent.num_base_MrkvStates)
    return params


def _ad_params_dict(eco):
    """AD-loop params (eco-level).

    NOTE: the ACTIVE ``ADelasticity`` is deliberately EXCLUDED — it is solve STATE, not
    a solve INPUT. ``solve_ad_recession`` sets ``self.ADelasticity = self.demand_ADelasticity``
    (AggFiscalModel.py:2691), so it reads 0.0 pre-solve and ``demand_ADelasticity`` (e.g.
    0.3) post-solve. Hashing it made the fingerprint LIFECYCLE-dependent, which silently
    broke the AD-belief warm-start: the publisher fingerprints post-solve, the consumer
    pre-solve, so the seed was always rejected on a phantom mismatch (diagnosed 2026-06-22
    — the SOLE differing leaf was ``ad.ADelasticity 0.0 vs 0.3``). The genuine input,
    ``demand_ADelasticity`` (kept below), fully determines the AD elasticity, so excluding
    the redundant active copy loses no key information. Harmless to the AD cache, which
    always keyed pre-solve where ADelasticity==0.0 (a constant), so its keys merely rehash.
    """
    params = {}
    for attr in (
        "num_max_iterations_solvingAD", "convergence_tol_solvingAD",
        "Cfunc_iter_stepsize", "demand_ADelasticity",
        "num_experiment_periods",
    ):
        if hasattr(eco, attr):
            params[attr] = _canonicalize_value(getattr(eco, attr))
    return params


def _env_dict():
    """Numerical-output-affecting env vars (whitelisted).

    NOTE (2026-07-31): adding a var to the tuple changes EVERY key (the dict
    gains an entry even when the var is unset) and silently invalidates the
    whole on-disk cache — an if-set tier was tried and reverted the same day
    because it forced a global MISS whose fresh-solve path exposed a latent
    'no solution stored' bug (see the draw-structure plan's execution record).
    Sim-only knobs like HAFISCAL_JAX_MC_NEWBORN_POOL_N deliberately stay OUT
    of the solve-cache key (they do not touch cFuncs); the AD-result cache is
    protected operationally by the ad_* quarantine discipline in every
    measurement harness.
    """
    return {
        k: os.environ.get(k, "")
        for k in _HAFISCAL_NUMERICAL_ENV_VARS
    }


def _provenance_dict():
    """Versions / SHAs for cross-checking."""
    hafiscal = _hafiscal_root()
    hark = _hark_root()
    return {
        "hafiscal_sha": _git_sha(hafiscal) if hafiscal else "unknown",
        "hark_sha": _git_sha(hark) if hark else "unknown",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
    }


def gather_solve_inputs(eco, shock_type, mc_method="hark_mc",
                         seeds=(0,), use_shuffle=False,
                         init_panel_method="newborn_pool",
                         agent_count_per_cohort=None):
    """Gather everything that determines the AD-converged eco.solve() output.

    Args:
        eco: HAFiscal AggEconomy object (post-build, pre-solve)
        shock_type: 'recession', 'recessionCheck', etc.
        mc_method: 'hark_mc' / 'jax_mc' / 'jax_mc_replay_v2' / etc.
        seeds: tuple of seed offsets used during AD
        use_shuffle: bool
        init_panel_method: 'newborn_pool' / 'hark_ref' / 'explicit' / ...
        agent_count_per_cohort: tuple of per-cohort N, or None for default

    Returns:
        dict suitable for hashing (all values canonicalized).
    """
    return {
        "shock_type": shock_type,
        "mc_method": mc_method,
        "seeds": list(seeds),
        "use_shuffle": bool(use_shuffle),
        "init_panel_method": init_panel_method,
        "agent_count_per_cohort": (
            list(agent_count_per_cohort)
            if agent_count_per_cohort is not None
            else [int(a.AgentCount) for a in eco.agents]
        ),
        "n_cohorts": len(eco.agents),
        "agents": [_agent_params_dict(a) for a in eco.agents],
        "ad": _ad_params_dict(eco),
        "env": _env_dict(),
        "provenance": _provenance_dict(),
    }


# Top-level keys in the inputs dict that are metadata-only — they appear
# in the .meta.json sidecar for forensics but are EXCLUDED from the hash
# so e.g. committing to HAFiscal mid-session doesn't invalidate the cache.
# Numerical-output-affecting params (env, agent params, AD-loop, etc.)
# remain in the hash.
_HASH_EXCLUDED_TOP_KEYS = ("provenance",)


def hash_solve_inputs(inputs):
    """SHA256 of canonical JSON of the inputs dict, EXCLUDING metadata-only
    top-level keys (see ``_HASH_EXCLUDED_TOP_KEYS``). Stable across HAFiscal/
    HARK commits — provenance SHAs land in metadata, not the hash key."""
    hashable = {k: v for k, v in inputs.items()
                if k not in _HASH_EXCLUDED_TOP_KEYS}
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_provenance_match(meta_provenance, current_provenance=None):
    """Compare a cached meta's provenance dict to the current env.

    Returns a list of (field, cached_val, current_val) tuples for fields
    that differ. Empty list = full match.
    """
    if current_provenance is None:
        current_provenance = _provenance_dict()
    diffs = []
    for k, cached_v in meta_provenance.items():
        cur_v = current_provenance.get(k)
        if cur_v != cached_v:
            diffs.append((k, cached_v, cur_v))
    return diffs


def parametrization_tag(eco, mc_method="hark_mc", use_shuffle=False,
                          agent_count_per_cohort=None, seed_offset=0):
    """Human-readable filename tag combining the most navigable params."""
    if agent_count_per_cohort is None:
        agent_count_per_cohort = [int(a.AgentCount) for a in eco.agents]
    ac_str = "-".join(str(n) for n in agent_count_per_cohort)
    shuf_str = "shuf" if use_shuffle else "noshuf"
    return f"AC{ac_str}__mc-{mc_method}__{shuf_str}__seed{seed_offset}"


# ==========================================================================
# SIM-cache key + re-derivation check (Plan 2 STEP 4 — DESIGN ONLY).
#
# The existing cache (ad_cache.py) is a SOLUTION cache: it stores the converged
# cFunc + AD belief, NOT the per-duration forward-sim PANELS. A SIM cache would
# store those panels. Per the welfare6 phase map (plan §2.D) the forward-sim
# (COMPUTE-WELFARE) phase is the CHEAP one and panels are large on disk, so the
# SIM cache is LOWER priority — DESIGNED here, materialized later.
#
# Everything below is gated behind HAFISCAL_USE_SIM_CACHE (default OFF). These
# are pure key/verify helpers: they neither materialize a cache nor get wired
# into any run path. The standard reproduction path never calls them.
#
# WHY THE SOLVE KEY IS INSUFFICIENT FOR A PANEL. gather_solve_inputs DELIBERATELY
# excludes T_sim and the per-cohort AgentCount (numerical-equivalent for the
# converged cFunc — see the module docstring "Explicitly NOT in the key"). But a
# forward-sim PANEL is N-shaped and T-long, and its bytes depend on the exact RNG
# streams. So the SIM key must ADD every RNG/shape determinant of a panel:
#   - per-cohort agent RNG seed  t.seed = e*DiscFacCount + d + seed_offset*10000
#       (welfare6_scenario.build_and_solve, ~line 343)
#   - per-cohort income-shock seed  IncShkDstn[0].seed = 763607780 + seed_offset
#       (welfare6_scenario.build_and_solve, ~line 396)
#   - use_shuffle + HAFISCAL_SHUFFLE_MRKV_TRANSITION + HAFISCAL_SHUFFLE_NEWBORN_FIX
#       (stratified-vs-plain is the +8.26%-UI footgun — MUST be keyed)
#   - HAFISCAL_WELFARE6_TM_INIT (+_MEASURE, +HAFISCAL_WELFARE6_MC_WARMUP):
#       the init-panel determinant (welfare6_scenario, ~line 533-547)
#   - T_sim / act_T and per-cohort AgentCount (panel SHAPE)
#   - the EconomyMrkv_init path (norec vs rec macro-state init).
# ==========================================================================

# Env vars that determine a forward-sim PANEL's bytes (beyond the cFunc-affecting
# whitelist). These select RNG streams / shuffle behaviour / init panels and are
# REQUIRED in the SIM key even though several are intentionally absent from the
# SOLVE whitelist (they don't change the converged cFunc, only the realized panel).
_HAFISCAL_SIM_ENV_VARS = (
    "HAFISCAL_SHUFFLE_MRKV_TRANSITION",   # stratified vs plain (+8.26%-UI footgun)
    "HAFISCAL_SHUFFLE_NEWBORN_FIX",       # newborn re-draw policy under shuffle
    "HAFISCAL_WELFARE6_TM_INIT",          # ergodic warm-start on/off (init panel)
    "HAFISCAL_WELFARE6_TM_INIT_MEASURE",  # P vs Q ergodic measure for the init
    "HAFISCAL_WELFARE6_MC_WARMUP",        # MC warm-up periods feeding the init
)


def _sim_env_dict():
    """Forward-sim-panel-affecting env vars (the SIM-cache extension of _env_dict)."""
    return {k: os.environ.get(k, "") for k in _HAFISCAL_SIM_ENV_VARS}


def _agent_seed(e, d, disc_fac_count, seed_offset):
    """Per-cohort agent RNG seed, mirroring welfare6_scenario.build_and_solve
    (~line 343): ``t.seed = e*DiscFacCount + d + seed_offset*10000``."""
    return int(e) * int(disc_fac_count) + int(d) + int(seed_offset) * 10000


def _incshk_seed(seed_offset):
    """Income-shock-distribution seed, mirroring welfare6_scenario
    (~line 396): ``IncShkDstn[0].seed = 763607780 + seed_offset``."""
    return 763607780 + int(seed_offset)


def _cohort_seeds(eco):
    """Read the per-cohort RNG seeds (agent .seed + IncShkDstn[0].seed) directly
    off the live eco's agents. These ARE the panel's RNG streams, so they pin the
    SIM key without having to re-derive (e, d, seed_offset) from the calibration."""
    out = []
    for a in eco.agents:
        rec = {}
        if hasattr(a, "seed"):
            rec["agent_seed"] = int(a.seed)
        # IncShkDstn[0].seed — the income-shock RNG stream for this cohort.
        try:
            iss0 = a.IncShkDstn[0]
            if hasattr(iss0, "seed"):
                rec["incshk_seed"] = int(iss0.seed)
        except Exception:
            pass
        out.append(rec)
    return out


def gather_sim_inputs(eco, shock_type, mc_method="hark_mc",
                      seeds=(0,), use_shuffle=False,
                      init_panel_method="newborn_pool",
                      agent_count_per_cohort=None,
                      seed_offset=0, T_sim=None, act_T=None,
                      economy_mrkv_init=None):
    """DESIGN-ONLY (Plan 2 STEP 4): SIM-cache key inputs.

    Extends ``gather_solve_inputs`` with every RNG/shape determinant a forward-sim
    PANEL depends on but that the SOLVE key intentionally omits (T_sim, per-cohort
    AgentCount, the per-cohort RNG seeds, the shuffle/init-panel env switches, and
    the EconomyMrkv_init path). See the section header above for the determinant
    list and the welfare6_scenario.py line refs.

    Gated behind ``HAFISCAL_USE_SIM_CACHE`` (default OFF): this helper neither
    materializes a sim cache nor is wired into any run path; it exists so the SIM
    key is reviewable now and the cache can be built later behind that flag.

    Args:
        eco: HAFiscal AggEconomy (post-build).
        shock_type, mc_method, seeds, use_shuffle, init_panel_method,
        agent_count_per_cohort: as in ``gather_solve_inputs``.
        seed_offset: the multi-seed batch offset (pins both RNG seed formulas).
        T_sim / act_T: panel length (a panel is T-long; the SOLVE key omits this).
        economy_mrkv_init: the EconomyMrkv_init macro-state init path
            (norec vs rec), if known to the caller.

    Returns:
        dict suitable for hashing with ``hash_solve_inputs`` (super-set of the
        solve inputs — its hash CHANGES on any panel-determining difference).
    """
    base = gather_solve_inputs(
        eco, shock_type=shock_type, mc_method=mc_method, seeds=seeds,
        use_shuffle=use_shuffle, init_panel_method=init_panel_method,
        agent_count_per_cohort=agent_count_per_cohort,
    )
    base["cache_kind"] = "sim_panel"  # disambiguate from the solve/AD key namespace
    base["sim"] = {
        "seed_offset": int(seed_offset),
        # The actual RNG streams off the live agents (authoritative); plus the
        # offset-derived formulas for forensic cross-checking.
        "cohort_seeds": _cohort_seeds(eco),
        "incshk_seed_from_offset": _incshk_seed(seed_offset),
        "T_sim": (int(T_sim) if T_sim is not None else None),
        "act_T": (int(act_T) if act_T is not None else None),
        "agent_count_per_cohort": (
            list(agent_count_per_cohort)
            if agent_count_per_cohort is not None
            else [int(a.AgentCount) for a in eco.agents]
        ),
        "economy_mrkv_init": economy_mrkv_init,
        "sim_env": _sim_env_dict(),
    }
    return base


def hash_sim_inputs(inputs):
    """SHA256 of the SIM-cache inputs (alias of ``hash_solve_inputs``; same
    provenance-excluded canonical-JSON hashing). Named separately so call sites
    read clearly as SIM-key hashing."""
    return hash_solve_inputs(inputs)


def _panel_shock_hash(shock_history, sim_birth):
    """Deterministic SHA256 of a panel's GENERATING arrays (shock_history +
    sim_birth). HARK's ``initialize_sim`` pre-computes ``shock_history``
    deterministically from the seed, and the JAX replay kernel already consumes
    these arrays as data — so hashing them pins the panel's RNG realization
    exactly (no tolerance)."""
    h = hashlib.sha256()
    for name, arr in (("shock_history", shock_history), ("sim_birth", sim_birth)):
        h.update(name.encode("utf-8"))
        if arr is None:
            h.update(b"\x00none")
            continue
        a = np.ascontiguousarray(np.asarray(arr))
        h.update(str(a.shape).encode("utf-8"))
        h.update(str(a.dtype).encode("utf-8"))
        # Cast floats to float64 for cross-platform-stable bytes (matches
        # _canonicalize_array's float64 normalization).
        h.update((a.astype(np.float64) if a.dtype.kind == "f" else a).tobytes())
    return h.hexdigest()


def verify_sim_panel(panel, seeds):
    """DESIGN-ONLY (Plan 2 STEP 4): deterministic re-derivation check for a cached
    forward-sim panel — NOT a tolerance.

    A simulation has no fixed-point residual, so the panel is verified by checking
    its GENERATING INPUTS: recompute the shock-hash from the panel's stored
    ``shock_history``/``sim_birth`` and compare it to the hash recorded when the
    panel was cached. A match means the RNG realization is bit-identical; a mismatch
    means the stored panel was produced by different shocks and MUST NOT be reused.

    The ``seeds`` argument is accepted for the eventual materialized path (where the
    recompute would re-run HARK's deterministic ``initialize_sim`` from the seeds
    rather than trust the panel's own arrays); in this DESIGN-ONLY form it is
    recorded for forensics and the check is over the panel's recorded arrays.

    Args:
        panel: a dict-like with keys ``shock_history``, ``sim_birth`` (the
            generating arrays) and ``shock_hash`` (the recorded hash).
        seeds: the seed tuple/offset the panel claims to have been generated with.

    Returns:
        (ok: bool, recomputed_hash: str, recorded_hash: str|None). ``ok`` is True
        only when a recorded hash exists AND equals the recomputed one. Caller is
        responsible for refusing reuse when ``ok`` is False.
    """
    def _get(p, k, default=None):
        if isinstance(p, dict):
            return p.get(k, default)
        return getattr(p, k, default)

    recorded = _get(panel, "shock_hash")
    recomputed = _panel_shock_hash(
        _get(panel, "shock_history"), _get(panel, "sim_birth"))
    # `seeds` recorded for forensics in the materialized path (recompute-from-seed).
    _ = seeds
    ok = (recorded is not None) and (recomputed == recorded)
    return ok, recomputed, recorded
