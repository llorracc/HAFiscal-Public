"""
Asymptotic equality test (revised driver): verify P-MC, Q-MC, and TM-Q converge as
AgentCount grows and TM grid refines.

============================================================================
RULE — NO HYBRID RATIOS
----------------------------------------------------------------------------
Never construct a ratio whose numerator and denominator use different
measures. In particular:

  * NPV(ΔAggCons_Q) / NPV(ΔAggIncome_P)  ← FORBIDDEN (hybrid multiplier)
  * NPV_C_Q / NPV_C_P                    ← FORBIDDEN (hybrid scaling check)
  * E_Q[f(m)] / E_P[g(m)]                ← FORBIDDEN

Why: under Harmenberg, E_P[p·f(m)] = E_P[p] · E_Q[f(m)], so Q-track
aggregates are P-track aggregates rescaled by E_P[p]. Mixing a Q numerator
with a P denominator embeds that scale factor in the ratio and makes it
incomparable to a same-measure quantity (e.g. a TM-Q multiplier). What
*looks* like a 54% "error" is usually just E_P[p] ≠ 1.

A Q-track multiplier requires a Q-track income leg — compute both legs
under the same measure or do not compute the ratio at all.
============================================================================

============================================================================
COMPARISON REGISTRY — every TM↔MC / P↔Q comparison MUST cite the math
derivation that establishes asymptotic equality.
----------------------------------------------------------------------------
Reference files (relative to repo root):
  TMMC = history/20260331-mathematical-derivations-TM-MC-convergence.md
  HARM = history/20260331-mathematical-derivations-harmenberg.md
  APX  = history/20260331-mathematical-derivations-appendix.md

If you add a new comparison, you MUST add a row here. If no derivation
exists, attempt one inline; if that fails, mark the row "UNPROVEN" and
print a prominent warning at the comparison site.

──┬─Comparison────────────────────┬─Limit (N→∞, M→∞)────────┬─Cite─────────
1 │ Phase 0 — per-cohort MC init  │ MC drawn from TM        │ TMMC §4.2,
  │ drift after TM-style setup    │ ergodic remains in      │ §4.3, §6.4
  │ (max|dm|, max|du|, max|dV|)   │ ergodic (drift → 0      │
  │                               │ as warmup → ∞).         │
──┼───────────────────────────────┼─────────────────────────┼──────────────
2 │ Phase 1 — Baseline AggCons    │ Both → E_P[p·c(m,z)].   │ TMMC §3,
  │ per-capita: TM-fine vs MC-P   │                         │ §7, §8, §9,
  │                               │                         │ §10, §14
──┼───────────────────────────────┼─────────────────────────┼──────────────
3 │ Phase 1 — TM ladder (opt-in:  │ TM[mCount] → E_P[p·c]   │ TMMC §10.1,
  │ pass multiple --tm; default   │ at rate O(1/M²) for     │ §10.2,
  │ is single grid TM-default)  │ smooth c.               │ §14.2
──┼───────────────────────────────┼─────────────────────────┼──────────────
4 │ Phase 1 — Per-type baseline   │ ✓ PROVEN. Both → the    │ TMMC §4
  │ moments TM-P vs MC P-cross-   │ same per-type P-ergodic │ (ergodic),
  │ section (E[m], E[c], emp,    │ moments. Same measure   │ §9 (MC LLN),
  │ Var[ln m])                    │ on both sides; standard │ §10 (TM
  │                               │ ergodic + LLN argument. │ grid → erg)
  │                               │ Apples-to-apples        │
  │                               │ replacement for the     │
  │                               │ earlier UNPROVEN TM-Q   │
  │                               │ vs MC test.             │
──┼───────────────────────────────┼─────────────────────────┼──────────────
5 │ [REMOVED] TM-P vs TM-Q        │ Not a convergence test  │ HARM §1
  │ ergodic moments               │ — they're supposed to   │
  │                               │ differ. Comparison      │
  │                               │ eliminated.             │
──┼───────────────────────────────┼─────────────────────────┼──────────────
6a│ Phase 3 (norec-ui) — UI mult: │ ✓ PROVEN. UI extends    │ TMMC §13.5
  │ TM-Q vs MC-P                  │ benefits during          │
  │                               │ unemployment. Per-state  │
  │                               │ income is p-linear: the  │
  │                               │ extra benefit scales p   │
  │                               │ by a fixed factor. So    │
  │                               │ the integrand is         │
  │                               │ p·c(m, j) (no p inside   │
  │                               │ c) and Harmenberg's      │
  │                               │ identity applies         │
  │                               │ pointwise.               │
──┼───────────────────────────────┼─────────────────────────┼──────────────
6b│ Phase 4 (norec-taxcut) —      │ ✓ PROVEN. TaxCut scales │ TMMC §13.5
  │ TaxCut mult: TM-Q vs MC-P     │ employed TranShk by      │
  │                               │ TaxCutIncFactor. Per-    │
  │                               │ agent income is          │
  │                               │ p · TranShk · factor.    │
  │                               │ Integrand is p·c(m, j),  │
  │                               │ p-linear. Harmenberg     │
  │                               │ applies.                 │
──┼───────────────────────────────┼─────────────────────────┼──────────────
6c│ Phase 2 (norec-check) — Check │ ✓ PROVEN (via bucket    │ TMMC §13.5.1
  │ mult: TM-Q vs MC-P            │ scheme).                 │ + BUG-022
  │                               │ Check policy delivers    │
  │                               │ check(p) = $1200 ·       │
  │                               │ phase_out(p), which      │
  │                               │ violates the p-linearity │
  │                               │ hypothesis of §13.5      │
  │                               │ (the integrand is        │
  │                               │ p·c(m + check(p)/p, j),  │
  │                               │ with p inside c).        │
  │                               │ TM handles this via the  │
  │                               │ bucket scheme in         │
  │                               │ tm_methods.py:           │
  │                               │ _compute_check_buckets,  │
  │                               │ which is asymptotically  │
  │                               │ exact as n_buckets→∞.    │
  │                               │ Empirically converges    │
  │                               │ by n_buckets ~= 50       │
  │                               │ (within 0.07% of n=200). │
  │                               │ Default raised from 5    │
  │                               │ to 50 in BUG-022.        │
──┼───────────────────────────────┼─────────────────────────┼──────────────
7 │ Phase 5 — Recession baseline  │ Same as comparison 2    │ TMMC §6.5
  │ AggCons per-capita: TM vs MC  │ but on a non-stationary │ (transition);
  │                               │ Markov path. Limit is   │ TMMC §3, §13
  │                               │ E_P[p_t·c_t(m_t,z_t)]   │
  │                               │ at each t.              │
──┼───────────────────────────────┼─────────────────────────┼──────────────
8 │ Phase 7 — Recession + policy  │ ✓ PROVEN. recUI and     │ TMMC §13.5;
  │ multipliers (recUI, recCheck, │ recTaxCut per items     │ TMMC §6.5;
  │ recTaxCut): TM-Q vs MC-P      │ 6a/6b. recCheck via the │ §13.5.1
  │                               │ same bucket scheme as   │
  │                               │ item 6c, asymptotically │
  │                               │ exact in n_buckets.     │
──┴───────────────────────────────┴─────────────────────────┴──────────────

Status legend: ✓ proven    ⚠ caveats apply   ✗ unproven (DO NOT trust as
asymptotic-equality test until proved or replaced).

All comparisons in this driver are now ✓ PROVEN. Items 4 and 5 (the
unproven and the diagnostic-only ones) have been removed.
============================================================================


Usage (preferred: **named** phases; digits 0–7 remain as legacy aliases):

    python test_asymptotic_equality_revised.py --phase harness
    python test_asymptotic_equality_revised.py --phase baseline
    python test_asymptotic_equality_revised.py --phase norec-check
    python test_asymptotic_equality_revised.py --phase norec-ui
    python test_asymptotic_equality_revised.py --phase norec-taxcut
    python test_asymptotic_equality_revised.py --phase recession-baseline
    python test_asymptotic_equality_revised.py --phase recession-policies
    python test_asymptotic_equality_revised.py --phase ad-loop
    python test_asymptotic_equality_revised.py --phase all

    # Legacy numeric aliases: 0=harness … 7=ad-loop (same order as above)
    python test_asymptotic_equality_revised.py --phase harness --parametrization Smoke_Test

See plans/20260403-1253h_asymptotic-equality-test-plan.md (legacy phase descriptions) and
plans/20260404-1746h_asymptotic-equality-test-plan_revised.md (updated ladder, per-type rules).
"""

import sys
import os
import argparse
import time
import warnings
from contextlib import contextmanager

# Plan 2 v2 Task 1: profile-first instrumentation. Enable with
# HAFISCAL_PROFILE=1 to print one line per timed block. Refactoring
# decisions in Plan 2 must be driven by data from this instrumentation,
# not guesses about where the duplication is.
_PROFILE = os.environ.get("HAFISCAL_PROFILE", "") not in ("", "0", "false", "False")

# Plan 2 v3 Task 2: solve cache (landed; plan DONE). Disable with
# HAFISCAL_NO_SOLVE_CACHE=1 to fall back to the un-cached behavior
# (useful for the regression check that compares per-period series
# with vs without the cache).
#
# Cache key: (Parametrization, shock_type). The cache stores deepcopies
# of each agent's `solution` slot. On hit, the cached solutions are
# restored into the current economy's agents (themselves deepcopied)
# and economy.solve() is skipped entirely.
#
# Why the key omits AgentCount, seed, and mCount: the Bellman is
# determined by (CRRA, beta, R, LivPrb, PermGroFac, IncShkDstn,
# MrkvArray) — none of which depend on those quantities. See the
# headline section of plans/20260408-1028h_asymptotic-equality-driver-baseline-cache-refactor_v3.md.
#
# AD experiments invalidate the cache because solve_ad_recession
# iterates with updated Cratio paths; only the FIRST AD iterate is
# reusable from the non-AD cache. The current driver does not yet
# exercise the AD path (Phase 7 is a stub), so AD-cache integration
# is deferred.
_SOLVE_CACHE_DISABLED = os.environ.get("HAFISCAL_NO_SOLVE_CACHE", "") not in ("", "0", "false", "False")
SOLVE_CACHE = {}  # (parametrization, shock_type) -> list[agent.solution deepcopy]
SOLVE_CACHE_HITS = 0
SOLVE_CACHE_MISSES = 0


def solve_or_cache(economy, shock_type, parametrization=None):
    """
    Solve the economy with caching by (parametrization, shock_type).

    On cache hit: restore each agent's `solution` slot from the cached
    deepcopy and skip economy.solve() entirely. The economy's MrkvArray
    / IncShkDstn / etc. must already be set correctly by the caller
    (typically via switch_shock_type before this call).

    On cache miss: call economy.solve(), then deepcopy each agent's
    solution into the cache for future hits.

    Set HAFISCAL_NO_SOLVE_CACHE=1 to disable caching entirely (fall
    back to plain economy.solve()).
    """
    global SOLVE_CACHE_HITS, SOLVE_CACHE_MISSES
    if _SOLVE_CACHE_DISABLED:
        with profile_block(f"economy.solve({shock_type}) [cache disabled]"):
            economy.solve()
        return
    if parametrization is None:
        parametrization = RUN_PARAMETRIZATION
    key = (parametrization, shock_type)
    cached = SOLVE_CACHE.get(key)
    if cached is not None and len(cached) == len(economy.agents):
        # Hit: restore each agent's solution from a fresh deepcopy.
        with profile_block(f"solve_or_cache HIT ({shock_type})"):
            for agent, sol in zip(economy.agents, cached):
                agent.solution = deepcopy(sol)
                # pre_solve normally sets up MrkvArray and the terminal
                # boundary; switch_shock_type already did the MrkvArray
                # update, and the cached solution already includes the
                # converged interior. We do still need agent.IncShkDstn
                # to be set; the caller is responsible for that
                # (setup_economy and switch_shock_type both handle it).
        SOLVE_CACHE_HITS += 1
        return
    # Miss: do the real solve, then cache.
    with profile_block(f"solve_or_cache MISS ({shock_type}) [solving]"):
        economy.solve()
    SOLVE_CACHE[key] = [deepcopy(agent.solution) for agent in economy.agents]
    SOLVE_CACHE_MISSES += 1


def report_solve_cache_stats():
    """Print cache hit/miss summary at end of run."""
    if _SOLVE_CACHE_DISABLED:
        print("\n[solve-cache] DISABLED via HAFISCAL_NO_SOLVE_CACHE")
        return
    total = SOLVE_CACHE_HITS + SOLVE_CACHE_MISSES
    if total == 0:
        return
    pct = 100.0 * SOLVE_CACHE_HITS / total
    print(f"\n[solve-cache] {SOLVE_CACHE_HITS} hits / {SOLVE_CACHE_MISSES} misses "
          f"= {pct:.1f}% hit rate ({len(SOLVE_CACHE)} unique cache entries)")


@contextmanager
def profile_block(label: str):
    """Time a block of code; print result if HAFISCAL_PROFILE=1."""
    if not _PROFILE:
        yield
        return
    t0 = time.time()
    try:
        yield
    finally:
        dt = time.time() - t0
        print(f"[profile] {label}: {dt:.2f}s")

warnings.filterwarnings("ignore")

# Short citation strings used at compare sites (keep in sync with the
# Comparison Registry in the module docstring above).
#
# Note on per-shock-type splits: TMMC §13.5 (TM-Q ↔ MC-P multiplier
# identity) requires the income/consumption integrand to be of the form
# `p · f(m, j)` so that Harmenberg's pointwise identity
# `E_P[p·f(m,j)] = E[p]·E_Q[f(m,j)]` applies. The Stimulus Check policy
# violates this hypothesis: the per-agent check is
# `check(p) = $1200 · phase_out(p)`, so the integrand becomes
# `p · c(m + check(p)/p, j)` which has p-dependence INSIDE the c(·)
# argument. The TM treats this via the bucket scheme in
# `_compute_check_buckets`, which is an APPROXIMATION (5 quantile
# buckets, with within-bucket m ⊥ p assumed). The TM↔MC gap on
# `norec-check` is therefore not bounded by the §13.5 theorem; it is
# bounded only by the bucket scheme's discretization + independence
# error. UI and TaxCut do NOT have this issue because their policy
# effects are p-linear (see history/20260331-mathematical-derivations-
# TM-MC-convergence.md §13.5 for the per-policy verification).
MATH_REFS = {
    "init_drift":   "TMMC §4.2-4.3, §6.4",
    "agg_pc":       "TMMC §3, §7-10, §14",
    "tm_ladder":    "TMMC §10.1-10.2, §14.2",
    "type_moments_P": "PROVEN - TMMC §4 (ergodic), §9 (MC LLN), §10 (TM grid)",
    # Per-shock-type multiplier citations:
    "mult_baseline": "PROVEN - TMMC §13.5 (TM-Q ↔ MC-P multiplier identity)",
    "mult_ui":      "PROVEN - TMMC §13.5 (UI extension is p-linear)",
    "mult_taxcut":  "PROVEN - TMMC §13.5 (TaxCut is p-linear via TranShk scaling)",
    "mult_check":   ("PROVEN (via bucket scheme) - Check policy violates "
                     "the p-linearity hypothesis of TMMC §13.5 (check(p)/p "
                     "is non-trivial in p), so the Harmenberg pointwise "
                     "identity does not apply directly. TM uses the bucket "
                     "scheme in tm_methods.py:_compute_check_buckets, which "
                     "is asymptotically exact as n_buckets -> infinity. "
                     "Empirically converges by n_buckets ~= 50 (default). "
                     "BUG-022 raised the default from 5 to 50 — at 5 the "
                     "phase-out kink at pLvl=25 fell inside one bucket and "
                     "produced a +3.9% TM-side bias. See TMMC §13.5.1."),
    "rec_agg":      "TMMC §3, §6.5, §13",
    "rec_mult":     ("PROVEN - rec/recUI/recTaxCut by TMMC §13.5 + §6.5 "
                     "(p-linear); recCheck via the same bucket scheme as "
                     "norec-check (asymptotically exact in n_buckets)"),
}


def _math_ref_for_norec_shock(shock_type):
    """Per-shock multiplier citation for the no-recession phases."""
    if shock_type == "Check":
        return MATH_REFS["mult_check"]
    if shock_type == "UI":
        return MATH_REFS["mult_ui"]
    if shock_type == "TaxCut":
        return MATH_REFS["mult_taxcut"]
    # Fallback (shouldn't happen for the four currently-defined no-rec phases).
    return MATH_REFS["mult_baseline"]

# HAFiscal code lives in the same directory
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_HA_MODELS_DIR = os.path.dirname(_THIS_DIR)
if _HA_MODELS_DIR not in sys.path:
    sys.path.insert(0, _HA_MODELS_DIR)

# Patch sys.argv BEFORE importing Parameters (it reads Rfree, CRRA, IncUnemp)
_orig_argv = sys.argv[:]
sys.argv = [sys.argv[0], "1.01", "2.0", "0.7"]

import numpy as np
from copy import deepcopy

from Parameters import return_parameters
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
try:
    from AggFiscalModel import DualAggFiscalType
    HAS_DUAL = True
except ImportError:
    HAS_DUAL = False
from HARK.distributions import DiscreteDistribution
from tm_methods import (
    calculate_NPV,
    compute_baseline_tm_data,
    run_experiment_tm,
    run_experiment_tm_nonbase,
    run_ad_tm,
    unemployment_rate_for_tm_synthetic_pLvl,
)

sys.argv = _orig_argv

# ``main()`` assigns this before running phases so every ``setup_economy()`` call
# uses the same ``Parametrization`` (e.g. Smoke_Test for fast harness checks).
RUN_PARAMETRIZATION = "Reduced_Run"


# ─── Parameter configurations ────────────────────────────────────────

MC_CONFIGS = {
    # Seed counts: tiny=2, small=3, med=4, large=5, xlarge=6 (minimal SE at each tier).
    "MC-tiny":   {"AgentCountTotal": 200,   "seeds": [0, 1]},
    "MC-small":  {"AgentCountTotal": 1000,  "seeds": [0, 1, 2]},
    "MC-med":    {"AgentCountTotal": 2000,  "seeds": [0, 1, 2, 3]},
    "MC-large":  {"AgentCountTotal": 4000,  "seeds": [0, 1, 2, 3, 4]},
    "MC-xlarge": {"AgentCountTotal": 8000,  "seeds": [0, 1, 2, 3, 4, 5]},
}

TM_CONFIGS = {
    "TM-coarse":  {"mCount": 30},
    "TM-default": {"mCount": 50},
    "TM-50":      {"mCount": 50},   # canonical paired-cell coarse grid
    "TM-medium":  {"mCount": 75},
    "TM-fine":    {"mCount": 100},
    "TM-100":     {"mCount": 100},  # canonical paired-cell fine grid
    "TM-xfine":   {"mCount": 150},
}

# Paired-cell ladder presets (Plan v2). Each preset names exactly two
# cells; Cell 1 always uses TM mCount=50, Cell 2 always uses mCount=100.
# Adjacent presets share an MC config so successive runs are directly
# comparable. See plans/20260408-1028h_asymptotic-equality-driver-ladder-presets_v2.md.
LADDER_PRESETS = {
    "smoke":   [("MC-tiny",   "TM-50"), ("MC-small",  "TM-100")],
    "quick":   [("MC-small",  "TM-50"), ("MC-med",    "TM-100")],
    "parity":  [("MC-med",    "TM-50"), ("MC-large",  "TM-100")],
    "careful": [("MC-large",  "TM-50"), ("MC-xlarge", "TM-100")],
}

# Cap on the number of recession-length variations the test driver
# will loop over for recession-baseline and recession-policies phases.
# Smoke_Test / Reduced_Run set max_recession_duration=11; Baseline
# uses 21. The recession-policies phase is the heaviest in the driver
# precisely because of this loop (each shock_type gets one
# TM experiment + one MC experiment per duration). Capping to 2
# reduces that work by ~5x at smoke scale and ~10x at Baseline scale,
# which is the right trade-off for a parity test (the convergence
# claim does not depend on integrating over many durations).
#
# To restore the full duration loop, set this to None.
TEST_DRIVER_MAX_RECESSION_DURATION = 2


def _warn_if_not_convergence_test(phase_id, mc_configs, tm_configs):
    """
    Plan 1 v2 §B Task 5 runtime check. Warn if both axes are length-1
    in a per-phase invocation; that is a single-cell parity check, not
    a convergence test, and the corresponding 'vs ref' columns will be
    tautologically zero.

    Multiple MC sizes against a single TM (or vice-versa) is still a
    valid one-sided convergence test and does NOT warn.
    """
    mc_n = len(mc_configs) if mc_configs else 0
    tm_n = len(tm_configs) if tm_configs else 0
    if mc_n == 1 and tm_n == 1:
        print(f"\n  ⚠  NOT A CONVERGENCE TEST [{phase_id}]: "
              f"--mc={mc_configs[0]} and --tm={tm_configs[0]} are both "
              f"single configs; the 'vs ref' columns will be 0% by "
              f"construction. Pass at least two configs on either axis "
              f"or use --ladder smoke for a real convergence test.")


def default_configs_for_phase(phase_id):
    """
    Return ``(mc_configs, tm_configs)`` for a phase when the user passes
    neither --ladder nor --mc/--tm.

    Plan 1 v2 §B Tasks 2 and 5: every default invocation must satisfy
    the convergence-test invariant — at least two MC tiers AND at least
    two TM grids. The defaults below all satisfy this.

    Phase-specific tuning balances wall-clock against the convergence
    signal. Phases that loop over many sub-experiments (recession-
    policies, with three shock types) get the smallest meaningful MC
    pair to keep wall-clock manageable; lighter phases get a larger
    MC pair.
    """
    if phase_id == "harness":
        # Harness only needs one cohort to verify wiring; configs are
        # ignored downstream but length-≥2 keeps the invariant green.
        return (["MC-tiny", "MC-small"], ["TM-50", "TM-100"])
    if phase_id == "baseline":
        return (["MC-small", "MC-med"], ["TM-50", "TM-100"])
    if phase_id in ("norec-check", "norec-ui", "norec-taxcut"):
        return (["MC-small", "MC-med"], ["TM-50", "TM-100"])
    if phase_id == "recession-baseline":
        return (["MC-small", "MC-med"], ["TM-50", "TM-100"])
    if phase_id == "recession-policies":
        # Heaviest phase (3 shock types × 11 TM duration runs each).
        # Smaller MC pair to keep wall-clock under ~30 min default.
        return (["MC-tiny", "MC-small"], ["TM-50", "TM-100"])
    if phase_id == "ad-loop":
        # Stub; configs ignored.
        return (["MC-small"], ["TM-100"])
    # Unknown phase: safe fallback.
    return (["MC-small", "MC-med"], ["TM-50", "TM-100"])


# ─── Helpers ─────────────────────────────────────────────────────────

def assert_tm_baseline_indexing(economy, baseline_tm_data):
    """
    ``baseline_tm_data[i]`` must correspond to ``economy.agents[i]`` (per-type TM).
    """
    n_ag = len(economy.agents)
    n_bd = len(baseline_tm_data)
    if n_bd != n_ag:
        raise ValueError(
            f"baseline_tm_data length {n_bd} != len(economy.agents) {n_ag}; "
            "each type needs its own TM row — see plans/20260404-1746h_asymptotic-equality-test-plan_revised.md"
        )


def restore_intended_act_T_after_counterfactual_switch(economy, intended_act_T):
    """
    ``switch_to_counterfactual_mode`` sets ``economy.act_T`` from module ``T_sim``
    in AggFiscalModel; restore the intended experiment horizon (e.g. Reduced_Run act_T).
    """
    economy.act_T = int(intended_act_T)
    for a in economy.agents:
        a.get_economy_data(economy)


def setup_economy(Parametrization=None, AgentCountTotal_override=None,
                  seed_offset=0, use_dual=False):
    """Build the HAFiscal economy (agents + market) like Simulate.py does."""
    if Parametrization is None:
        Parametrization = RUN_PARAMETRIZATION
    params = return_parameters(Parametrization=Parametrization, OutputFor="_Main.py")
    (init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes) = params

    if AgentCountTotal_override is not None:
        AgentCountTotal = AgentCountTotal_override

    AgentCls = DualAggFiscalType if (use_dual and HAS_DUAL) else AggFiscalType

    BaseTypeList = []
    for init in [init_dropout, init_highschool, init_college]:
        agent = AgentCls(**init)
        agent.cycles = 0
        BaseTypeList.append(agent)

    economy = AggregateDemandEconomy(**init_ADEconomy)
    for agent in BaseTypeList:
        agent.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])],
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])],
    )

    for bt in BaseTypeList:
        bt.IncShkDstn[0].seed = 763607780
        bt.IncShkDstn[0].reset()

    for bt in BaseTypeList:
        EmployedIncShkDstn = deepcopy(bt.IncShkDstn[0])
        bt.IncShkDstn = [[bt.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
        bt.IncShkDstn_base = bt.IncShkDstn

        IncShkDstn_recession = [bt.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
        bt.IncShkDstn_recession = IncShkDstn_recession
        bt.IncShkDstn_recessionUI = IncShkDstn_recession

        # BUG-023 fix: was `atoms[0][1] *= TaxCutIncFactor`, which mutated
        # ONE element of the PermShk atom array (atoms[0] = PermShk,
        # atoms[1] = TranShk per HARK convention). The intended behavior
        # is to scale every joint atom's TranShk component by the
        # tax-cut factor, which is what the comment in
        # tm_methods.py:_scaled_employed_joint_inc_dstn already
        # documented as "TranShk (atoms[1]) scaled". Use the whole-array
        # form so we don't accidentally regress to the typo.
        EmployedIncShkDstn.atoms = (
            np.asarray(EmployedIncShkDstn.atoms[0], dtype=np.float64),
            np.asarray(EmployedIncShkDstn.atoms[1], dtype=np.float64) * bt.TaxCutIncFactor,
        )
        TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
        IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
        for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
            IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
        bt.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
        bt.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    if use_dual and HAS_DUAL:
        for bt in BaseTypeList:
            bt.setup_Q_measure()

    TypeList = []
    n = 0
    for e in range(3):
        # Skip cohorts with zero population share (e.g. dropout and college
        # under HS_Only). The 3-cohort BaseTypeList is built unconditionally
        # so the BaseType solves still happen, but masked cohorts contribute
        # no agents to the simulation. This is "Strategy A" from the
        # earlier HS_Only scoping — no breaking changes to data structures,
        # ~30s of wasted solve work for the masked cohorts at smoke scale.
        if data_EducShares[e] == 0.0:
            continue
        for b in range(DiscFacCount):
            DiscFac = DiscFacDstns[e].atoms[0][b]
            AgentCount = int(np.floor(AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]))
            AgentCount = max(AgentCount, 1)
            ThisType = deepcopy(BaseTypeList[e])
            ThisType.AgentCount = AgentCount
            ThisType.DiscFac = DiscFac
            ThisType.seed = n + seed_offset
            TypeList.append(ThisType)
            n += 1

    economy.agents = TypeList
    # Plan 2 v3 cache target. The Bellman is a pure function of
    # (parametrization, shock_type), so all per-seed and per-cell
    # invocations of setup_economy share the same solve.
    solve_or_cache(economy, "base", parametrization=Parametrization)

    meta = {
        "base_dict": base_dict,
        "num_base_MrkvStates": num_base_MrkvStates,
        "UBspell_normal": UBspell_normal,
        "max_recession_duration": max_recession_duration,
        "num_experiment_periods": num_experiment_periods,
        "recession_changes": recession_changes,
        "UI_changes": UI_changes,
        "recession_UI_changes": recession_UI_changes,
        "TaxCut_changes": TaxCut_changes,
        "recession_TaxCut_changes": recession_TaxCut_changes,
        "Check_changes": Check_changes,
        "recession_Check_changes": recession_Check_changes,
        "DiscFacCount": DiscFacCount,
        "AgentCountTotal": AgentCountTotal,
        "data_EducShares": data_EducShares,
        "num_max_iterations_solvingAD": num_max_iterations_solvingAD,
        "convergence_tol_solvingAD": convergence_tol_solvingAD,
    }
    return economy, meta


def mc_burnin(economy, warmup=24, tm_data=None, use_dual=False):
    """Run MC burn-in, optionally initializing from TM ergodic."""
    economy.reset()
    for agent in economy.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    if tm_data is not None:
        assert_tm_baseline_indexing(economy, tm_data)
        for i, agent in enumerate(economy.agents):
            bd_i = tm_data[i]
            erg = bd_i.get("cohort_ergodic", bd_i.get("ergodic"))
            grid = bd_i["dist_mGrid"]
            J_i = agent.num_base_MrkvStates

            rng_i = np.random.RandomState(agent.seed)
            N_i = agent.AgentCount
            flat_probs = erg / np.sum(erg)

            bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
            M_i = len(grid)
            agent_j = bins // M_i
            agent_mNrm = grid[bins % M_i]

            sol_i = agent.solution[0]
            agent_aNrm = np.zeros(N_i)
            for j in range(J_i):
                mask = agent_j == j
                if np.any(mask):
                    c = sol_i.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
                    agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

            L = agent.LivPrb[0][0]
            T_ag = agent.T_age
            age_probs = np.array([L ** (k - 1) for k in range(1, T_ag + 1)])
            age_probs /= np.sum(age_probs)
            agent_ages = rng_i.choice(T_ag, size=N_i, p=age_probs) + 1

            pLogMean = agent.pLogInitMean
            pLogStd = getattr(agent, "pLogInitStd", getattr(agent, "pLvlInitStd", 0.0))
            PermShkDstn_0 = agent.IncShkDstn_base[0][0]
            log_ps = np.log(PermShkDstn_0.atoms[0])
            ps_var = np.dot(PermShkDstn_0.pmv, log_ps ** 2) - np.dot(PermShkDstn_0.pmv, log_ps) ** 2
            u_p = unemployment_rate_for_tm_synthetic_pLvl(bd_i, agent)
            g_lvl = effective_pLvl_growth(agent, u_p)
            effective_emp_periods = effective_perm_shock_periods_for_t_age(
                agent_ages, agent, u_p)
            log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
            log_pLvl += agent_ages * np.log(g_lvl)
            log_pLvl += effective_emp_periods * (-ps_var / 2.0)
            log_pLvl += rng_i.normal(0, np.sqrt(ps_var * effective_emp_periods))
            agent_pLvl = np.exp(log_pLvl)

            agent.state_now["aNrm"][:] = agent_aNrm
            agent.state_now["pLvl"][:] = agent_pLvl
            agent.shocks["Mrkv"][:] = agent_j
            if hasattr(agent, "t_age") and agent.t_age is not None:
                agent.t_age[:] = agent_ages
            agent.Cratio = 1.0
            agent.state_now["PlvlAgg"] = 1.0

            if use_dual and hasattr(agent, "state_now_Q"):
                for k, v in agent.state_now.items():
                    if isinstance(v, np.ndarray):
                        agent.state_now_Q[k] = v.copy()
                    else:
                        agent.state_now_Q[k] = v

        for _t in range(warmup):
            for agent in economy.agents:
                agent.sim_one_period()
    else:
        economy.make_history()


def run_mc_baseline(economy, base_dict, use_dual=False):
    """Run baseline MC experiment, return results dict."""
    intended_act_T = int(economy.act_T)
    economy.save_state()
    economy.switch_to_counterfactual_mode("base")
    restore_intended_act_T_after_counterfactual_switch(economy, intended_act_T)
    economy.make_idiosyncratic_shock_histories()
    base_dict_agg = deepcopy(base_dict)
    results = economy.run_experiment(**base_dict_agg, Full_Output=True)
    return results


def run_mc_norec_experiment(economy, shock_type, changes, base_dict):
    """Run a no-recession MC experiment."""
    eco = deepcopy(economy)
    # Plan 2 v3 cache target: switch_shock_type + solve. Each unique
    # (parametrization, shock_type) is solved at most once thanks to
    # solve_or_cache.
    eco.switch_shock_type(shock_type)
    solve_or_cache(eco, shock_type)
    dictt = deepcopy(base_dict)
    dictt.update(**changes)
    dictt["EconomyMrkv_init"] = list(np.arange(1, eco.num_experiment_periods + 1) * 2) + [0] * 20
    with profile_block(f"run_mc_norec_experiment.run_experiment({shock_type})"):
        results = eco.run_experiment(**dictt, Full_Output=True)
    return results


def run_mc_recession_experiment(economy, shock_type, changes, base_dict,
                                max_recession_duration, num_experiment_periods):
    """Run recession MC experiments averaged over durations."""
    # Cap to TEST_DRIVER_MAX_RECESSION_DURATION for parity tests.
    if TEST_DRIVER_MAX_RECESSION_DURATION is not None:
        max_recession_duration = min(max_recession_duration,
                                     TEST_DRIVER_MAX_RECESSION_DURATION)
    eco = deepcopy(economy)
    # Plan 2 v3 cache target.
    eco.switch_shock_type(shock_type)
    solve_or_cache(eco, shock_type)

    Rspell = eco.agents[0].Rspell
    R_persist = 1.0 - 1.0 / Rspell
    recession_prob_array = np.array([R_persist ** t * (1 - R_persist) for t in range(max_recession_duration)])
    recession_prob_array[-1] = 1.0 - np.sum(recession_prob_array[:-1])

    dictt = deepcopy(base_dict)
    dictt.update(**changes)
    all_results = []
    for t in range(max_recession_duration):
        dictt["EconomyMrkv_init"] = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
        dictt["EconomyMrkv_init"][0:t + 1] = (np.array(dictt["EconomyMrkv_init"][0:t + 1]) + 1).tolist()
        this_result = eco.run_experiment(**dictt, Full_Output=True)
        all_results.append(this_result)

    output_keys = ["NPV_AggIncome", "NPV_AggCons", "AggIncome", "AggCons"]
    if all_results and "AggCons_Q" in all_results[0]:
        output_keys += ["AggCons_Q", "NPV_AggCons_Q"]

    avg_results = {}
    for key in output_keys:
        avg_results[key] = np.sum(
            np.array([all_results[t][key] * recession_prob_array[t] for t in range(max_recession_duration)]),
            axis=0,
        )
    return avg_results


def rel_err(val, ref):
    """Relative error in percent."""
    if abs(ref) < 1e-15:
        return float("nan")
    return 100.0 * abs(val - ref) / abs(ref)


def baseline_tm_ergodic_moments(bd, agent):
    """
    Expectations under the TM baseline ergodic on the (micro × mGrid) tensor.
    Employed = micro state index 0 (same convention as ``verify_four_methods_agreement``).
    """
    erg = bd.get("cohort_ergodic", bd.get("ergodic"))
    erg_flat = np.asarray(erg, dtype=float).flatten()
    grid = np.asarray(bd["dist_mGrid"], dtype=float)
    J = int(agent.num_base_MrkvStates)
    M = len(grid)
    if erg_flat.size != J * M:
        raise ValueError(
            f"ergodic size {erg_flat.size} != J*M ({J}*{M}) for per-type TM moments"
        )
    sol = agent.solution[0]
    m_tiled = np.tile(grid, J)
    E_mNrm = float(np.dot(erg_flat, m_tiled))
    E_cNrm = 0.0
    log_m = np.log(np.maximum(grid, 1e-16))
    E_log_m = 0.0
    E_log_m2 = 0.0
    for j in range(J):
        sl = slice(j * M, (j + 1) * M)
        w = erg_flat[sl]
        c_row = sol.cFunc[j](grid, np.ones_like(grid))
        E_cNrm += float(np.dot(w, c_row))
        E_log_m += float(np.dot(w, log_m))
        E_log_m2 += float(np.dot(w, log_m * log_m))
    var_log_m = max(E_log_m2 - E_log_m * E_log_m, 0.0)
    frac_emp = float(np.sum(erg_flat[0:M]))
    return {
        "E_mNrm": E_mNrm,
        "E_cNrm": E_cNrm,
        "frac_employed": frac_emp,
        "Var_log_mNrm": var_log_m,
    }


def mc_cross_section_moments(agent, t=0):
    """Cross-sectional moments for one homogeneous cohort at simulation date ``t``."""
    m = np.asarray(agent.history["mNrm"][t], dtype=float).ravel()
    c = np.asarray(agent.history["cNrm"][t], dtype=float).ravel()
    p = np.asarray(agent.history["pLvl"][t], dtype=float).ravel()
    mrkv = np.asarray(agent.shock_history["Mrkv"][t], dtype=int).ravel()
    J = int(agent.num_base_MrkvStates)
    employed = (np.mod(mrkv, J) == 0).astype(float)
    frac_emp = float(np.mean(employed)) if employed.size else float("nan")
    E_m = float(np.mean(m)) if m.size else float("nan")
    E_c = float(np.mean(c)) if c.size else float("nan")
    if m.size > 1:
        var_log_m = float(np.var(np.log(np.maximum(m, 1e-16)), ddof=1))
    elif m.size == 1:
        var_log_m = 0.0
    else:
        var_log_m = float("nan")
    if p.size > 1:
        var_log_p = float(np.var(np.log(np.maximum(p, 1e-16)), ddof=1))
    elif p.size == 1:
        var_log_p = 0.0
    else:
        var_log_p = float("nan")
    return {
        "E_mNrm": E_m,
        "E_cNrm": E_c,
        "frac_employed": frac_emp,
        "Var_log_mNrm": var_log_m,
        "Var_log_pLvl": var_log_p,
    }


def _per_type_init_stability_summary(economy, meta, harness_warmup_periods: int = 2):
    """
    Phase B optional (revised plan §2): per-cohort early drift vs t=0, same
    metrics as ``verify_four_methods_agreement.diagnose_tm_init_stability``.
    Uses this phase's short harness burn-in (default 2); Phase A uses 24.
    """
    from verify_four_methods_agreement import diagnose_tm_init_stability

    n_types = len(economy.agents)
    if n_types < 2:
        return None

    economy.make_idiosyncratic_shock_histories()
    economy.run_experiment(**deepcopy(meta["base_dict"]), Full_Output=True)

    J = economy.agents[0].num_base_MrkvStates
    act_T = int(economy.act_T)
    per_type = []
    rows = []
    w_m = w_p = w_u = w_vm = w_vp = 0.0
    w_den = 0

    for i, ag in enumerate(economy.agents):
        mc_res = {
            "mNrm_all": np.asarray(ag.history["mNrm"], dtype=float),
            "pLvl_all": np.asarray(ag.history["pLvl"], dtype=float),
            "Mrkv_hist": np.asarray(ag.shock_history["Mrkv"], dtype=int),
        }
        d = diagnose_tm_init_stability(
            mc_res,
            J,
            act_T,
            use_burnin=True,
            warmup_periods=harness_warmup_periods,
            verbose=False,
        )
        ni = max(int(ag.AgentCount), 1)
        w_den += ni
        for key, acc in (
            ("max_m_drift_early", "m"),
            ("max_p_drift_early", "p"),
            ("max_u_drift_pp_early", "u"),
            ("max_varlog_m_drift_early", "vm"),
            ("max_varlog_p_drift_early", "vp"),
        ):
            val = d[key]
            if np.isfinite(val):
                if acc == "m":
                    w_m += ni * val
                elif acc == "p":
                    w_p += ni * val
                elif acc == "u":
                    w_u += ni * val
                elif acc == "vm":
                    w_vm += ni * val
                elif acc == "vp":
                    w_vp += ni * val

        per_type.append({"type_index": i, "AgentCount": ni, **d})

        def _fmt(x, nd):
            return f"{x:.{nd}f}" if np.isfinite(x) else "nan"

        rows.append(
            (
                i,
                ni,
                _fmt(d["max_m_drift_early"], 4),
                _fmt(d["max_p_drift_early"], 4),
                _fmt(d["max_u_drift_pp_early"], 3),
                _fmt(d["max_varlog_m_drift_early"], 4),
                _fmt(d["max_varlog_p_drift_early"], 4),
                "Y" if d["init_looks_stable"] else "N",
            )
        )

    print(
        f"\n  Per-type init stability (harness burn-in warmup={harness_warmup_periods}; "
        f"Phase A uses 24). Early drift vs t=0, periods 1..min(25,T-1)."
    )
    # math-deriv: init_drift -> TMMC §4.2-4.3 (TM/MC ergodic), §6.4 (within-period
    # independence). Asymptotic claim: as warmup -> infinity and N -> infinity,
    # an MC population drawn from the TM ergodic stays in that ergodic, so all
    # drift quantities -> 0. Stability test, not a convergence test.
    print(f"  [math-deriv] {MATH_REFS['init_drift']}")
    print_table(
        "Phase 0 (continued): Per-cohort MC init drift after TM-style setup",
        rows,
        ["i", "N", "max|dm|/m0", "max|dp|/p0", "max|du|pp", "max|dVm|/V0", "max|dVp|/V0", "ok"],
    )
    if w_den > 0:
        print(
            f"  AgentCount-weighted means: "
            f"max|dm|/m0={w_m/w_den:.4f}, max|dp|/p0={w_p/w_den:.4f}, "
            f"max|du|pp={w_u/w_den:.3f}, max|dVm|/V0={w_vm/w_den:.4f}, "
            f"max|dVp|/V0={w_vp/w_den:.4f}"
        )

    return {
        "per_type": per_type,
        "weighted_mean": {
            "max_m_drift": w_m / w_den if w_den else float("nan"),
            "max_p_drift": w_p / w_den if w_den else float("nan"),
            "max_u_drift_pp": w_u / w_den if w_den else float("nan"),
            "max_varlog_m_drift": w_vm / w_den if w_den else float("nan"),
            "max_varlog_p_drift": w_vp / w_den if w_den else float("nan"),
        },
    }


def phase0_harness_checks(mc_configs=None, tm_configs=None):
    """
    Phase B harness (plans/20260404-1746h_asymptotic-equality-test-plan_revised.md):
    TM baseline row count vs agents; restore act_T after counterfactual switch.
    When there are multiple cohorts, runs per-type init-stability summary (plan §2.4).
    """
    del mc_configs, tm_configs  # harness does not sweep MC/TM configs yet
    print("\n" + "#" * 70)
    print("# PHASE 0: Harness — TM indexing + act_T after switch_to_counterfactual_mode")
    print("#" * 70)

    economy, _meta = setup_economy()
    bl = compute_baseline_tm_data(economy, mCount=40, neutral_measure=True, verbose=False)
    assert_tm_baseline_indexing(economy, bl)

    intended = int(economy.act_T)
    tm_init = compute_baseline_tm_data(economy, mCount=40, neutral_measure=True, verbose=False)
    mc_burnin(economy, warmup=2, tm_data=tm_init, use_dual=HAS_DUAL)

    economy.save_state()
    economy.switch_to_counterfactual_mode("base")
    after_switch = int(economy.act_T)
    restore_intended_act_T_after_counterfactual_switch(economy, intended)
    assert economy.act_T == intended, (
        f"act_T not restored: want {intended}, got {economy.act_T} (was {after_switch} right after switch)"
    )

    print(
        f"  OK: n_types={len(economy.agents)}, baseline_tm rows={len(bl)}, "
        f"act_T preserved={intended} (value immediately after switch was {after_switch})."
    )

    init_summary = _per_type_init_stability_summary(economy, _meta, harness_warmup_periods=2)

    out = {
        "n_agents": len(economy.agents),
        "act_T": intended,
        "act_T_after_switch_before_fix": after_switch,
        "per_type_init_stability": init_summary,
    }
    return out


def print_table(title, rows, headers):
    """Pretty-print a comparison table."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")
    col_widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    header_line = "  ".join(f"{h:>{w}}" for h, w in zip(headers, col_widths))
    print(header_line)
    print("-" * len(header_line))
    for row in rows:
        print("  ".join(f"{str(v):>{w}}" for v, w in zip(row, col_widths)))
    print()


# ─── Phase 1: Baseline Ergodic ──────────────────────────────────────

def phase1_baseline_ergodic(mc_configs=None, tm_configs=None):
    """
    Compare baseline ergodic distributions across methods.

    After the economy-level AggCons table: **TM-P vs TM-Q** per-type ergodic moments;
    then **per-type TM-Q vs MC** at t=0 using the **first** MC config and **first** seed
    (Phase C in ``asymptotic-equality-test-plan_revised.md``).
    """
    if mc_configs is None or tm_configs is None:
        d_mc, d_tm = default_configs_for_phase("baseline")
        if mc_configs is None:
            mc_configs = d_mc
        if tm_configs is None:
            tm_configs = d_tm
    _warn_if_not_convergence_test("baseline", mc_configs, tm_configs)

    print("\n" + "#" * 70)
    print("# PHASE 1: Baseline Ergodic Distribution Comparison")
    print("#" * 70)

    # --- TM reference (finest grid) ---
    tm_ref_label = tm_configs[-1]
    tm_ref_mCount = TM_CONFIGS[tm_ref_label]["mCount"]
    print(f"\nComputing TM reference ({tm_ref_label}, mCount={tm_ref_mCount})...")
    t0 = time.time()
    with profile_block("phase1.setup_economy"):
        economy_tm, meta = setup_economy()
    with profile_block("phase1.compute_baseline_tm_data(Q)"):
        tm_data_ref = compute_baseline_tm_data(
            economy_tm, mCount=tm_ref_mCount, neutral_measure=True, verbose=False,
        )
    t_tm_q_data_elapsed = time.time() - t0
    print(f"  TM-Q baseline TM data ({t_tm_q_data_elapsed:.1f}s)")

    # TM-P baseline data: needed for the per-type cross-section comparison
    # below (TM-P vs MC P, both same measure -- option (a) replacement for
    # the deleted UNPROVEN TM-Q vs MC comparison).
    # PROFILE TARGET (Plan 2 v2 Task 4): TM-P and TM-Q above share most of
    # their work (transition matrix, ergodic solve); they differ only in
    # the shock reweighting. Likely cacheable into a single shared call.
    t0p = time.time()
    with profile_block("phase1.compute_baseline_tm_data(P)"):
        tm_data_P_ref = compute_baseline_tm_data(
            economy_tm, mCount=tm_ref_mCount, neutral_measure=False, verbose=False,
        )
    print(f"  TM-P baseline TM data ({time.time() - t0p:.1f}s)")

    # Use run_experiment_tm for consistent aggregation with Simulate.py
    t0 = time.time()
    ref_base_tm = run_experiment_tm(
        economy_tm,
        shock_type="base",
        mCount=tm_ref_mCount,
        neutral_measure=True,
        verbose=False,
    )
    ref_AggCons_tm = float(np.mean(ref_base_tm["AggCons"]))
    ref_N_tm = sum(a.AgentCount for a in economy_tm.agents)
    ref_AggCons_pc_tm = ref_AggCons_tm / ref_N_tm
    t_tm_ref = time.time() - t0

    print(
        f"  TM-Q ref AggCons = {ref_AggCons_tm:.6f} (per-capita: {ref_AggCons_pc_tm:.6f}, N={ref_N_tm})  "
        f"({t_tm_ref:.1f}s)"
    )

    # --- TM sweep ---
    tm_results = {}
    for tm_label in tm_configs:
        mCount = TM_CONFIGS[tm_label]["mCount"]
        t0 = time.time()
        base_r = run_experiment_tm(economy_tm, shock_type="base",
                                    mCount=mCount, neutral_measure=True)
        elapsed = time.time() - t0

        AggCons = float(np.mean(base_r["AggCons"]))
        AggCons_pc = AggCons / ref_N_tm

        tm_results[tm_label] = {
            "AggCons": AggCons,
            "AggCons_pc": AggCons_pc,
            "time": elapsed,
        }
        print(f"  {tm_label} (mCount={mCount}): AggCons_pc={AggCons_pc:.6f}, err={rel_err(AggCons_pc, ref_AggCons_pc_tm):.4f}%, {elapsed:.1f}s")

    # --- MC sweep ---
    mc_results = {}
    per_type_rows = None
    per_type_mc_label = None
    for mc_label in mc_configs:
        cfg = MC_CONFIGS[mc_label]
        seeds = cfg["seeds"]
        N_total = cfg["AgentCountTotal"]

        seed_AggCons_pc_P = []
        seed_AggCons_pc_Q = []
        t0_all = time.time()

        for seed in seeds:
            use_dual = HAS_DUAL
            economy_mc, meta_mc = setup_economy(
                AgentCountTotal_override=N_total,
                seed_offset=seed * 100,
                use_dual=use_dual,
            )
            N_mc = sum(a.AgentCount for a in economy_mc.agents)
            tm_init_data = compute_baseline_tm_data(economy_mc, mCount=50, neutral_measure=True)
            mc_burnin(economy_mc, warmup=24, tm_data=tm_init_data, use_dual=use_dual)

            intended_T = int(economy_mc.act_T)
            economy_mc.save_state()
            economy_mc.switch_to_counterfactual_mode("base")
            restore_intended_act_T_after_counterfactual_switch(economy_mc, intended_T)
            economy_mc.make_idiosyncratic_shock_histories()
            base_dict_agg = deepcopy(meta_mc["base_dict"])
            res = economy_mc.run_experiment(**base_dict_agg, Full_Output=True)

            AggCons_P = float(np.mean(res["AggCons"]))
            seed_AggCons_pc_P.append(AggCons_P / N_mc)

            if "AggCons_Q" in res:
                AggCons_Q = float(np.mean(res["AggCons_Q"]))
                seed_AggCons_pc_Q.append(AggCons_Q / N_mc)

            # Per-type cross-section: TM-P ergodic vs MC P-cross-section
            # (same measure on both sides). math-deriv: TMMC §4 (ergodic
            # exists), §10 (TM grid -> ergodic), §9 (MC LLN). Both ->
            # the same per-type P-ergodic moments as N -> infinity and
            # M -> infinity. Replaces the deleted UNPROVEN TM-Q vs MC test.
            if (
                per_type_rows is None
                and mc_label == mc_configs[0]
                and seed == seeds[0]
            ):
                per_type_mc_label = mc_label
                per_type_rows = []
                for i, agent_mc in enumerate(economy_mc.agents):
                    agent_tm = economy_tm.agents[i]
                    tm_m = baseline_tm_ergodic_moments(tm_data_P_ref[i], agent_tm)
                    mc_m = mc_cross_section_moments(agent_mc, t=0)
                    per_type_rows.append((i, tm_m, mc_m))

        elapsed = time.time() - t0_all

        mc_results[mc_label] = {
            "AggCons_pc_P_mean": np.mean(seed_AggCons_pc_P),
            "AggCons_pc_P_se": np.std(seed_AggCons_pc_P) / max(np.sqrt(len(seeds)), 1),
            "AggCons_pc_Q_mean": np.mean(seed_AggCons_pc_Q) if seed_AggCons_pc_Q else None,
            "AggCons_pc_Q_se": np.std(seed_AggCons_pc_Q) / max(np.sqrt(len(seeds)), 1) if seed_AggCons_pc_Q else None,
            "N_mc": N_mc if seeds else 0,
            "n_seeds": len(seeds),
            "time": elapsed,
        }

        pmc = mc_results[mc_label]
        p_err = rel_err(pmc["AggCons_pc_P_mean"], ref_AggCons_pc_tm)
        q_str = ""
        if pmc["AggCons_pc_Q_mean"] is not None:
            q_err = rel_err(pmc["AggCons_pc_Q_mean"], ref_AggCons_pc_tm)
            q_str = f", Q-MC_pc={pmc['AggCons_pc_Q_mean']:.6f} err={q_err:.4f}%"
        print(f"  {mc_label} (N={N_total}, agents={pmc['N_mc']}, {len(seeds)} seeds): "
              f"P-MC_pc={pmc['AggCons_pc_P_mean']:.6f} err={p_err:.4f}%{q_str}, {elapsed:.1f}s")

    # --- Summary table ---
    rows = []
    for label, res in tm_results.items():
        rows.append((label, f"{res['AggCons_pc']:.6f}", f"{rel_err(res['AggCons_pc'], ref_AggCons_pc_tm):.4f}%",
                      "-", "-", f"{res['time']:.1f}s"))
    for label, res in mc_results.items():
        q_val = f"{res['AggCons_pc_Q_mean']:.6f}" if res["AggCons_pc_Q_mean"] is not None else "N/A"
        q_err = f"{rel_err(res['AggCons_pc_Q_mean'], ref_AggCons_pc_tm):.4f}%" if res["AggCons_pc_Q_mean"] is not None else "N/A"
        rows.append((label + " (P)",
                      f"{res['AggCons_pc_P_mean']:.6f}",
                      f"{rel_err(res['AggCons_pc_P_mean'], ref_AggCons_pc_tm):.4f}%",
                      q_val, q_err, f"{res['time']:.1f}s"))

    # math-deriv: agg_pc -> TMMC §3 (factorization AggCons = sum p*c), §7 (TM
    # aggregation formula), §8 (MC aggregation formula), §9 (MC LLN at rate
    # O(1/sqrt(N))), §10 (TM grid -> 0 at rate O(1/M^2)), §14 (joint
    # convergence). Both methods -> the same limit E_P[p*c(m,z)].
    # tm_ladder: same as agg_pc plus TMMC §10.1-10.2, §14.2 for grid rate.
    print(f"  [math-deriv] AggCons: {MATH_REFS['agg_pc']}")
    print(f"  [math-deriv] TM ladder vs ref: {MATH_REFS['tm_ladder']}")
    print_table("Phase 1: Baseline AggCons per capita (ref = TM-Q xfine)",
                rows, ["Method", "C_pc", "vs TM-ref", "C_pc_Q", "Q vs ref", "Time"])

    # Per-type baseline moments: TM-P ergodic vs MC P-cross-section.
    # math-deriv: type_moments_P -> TMMC §4 (ergodic existence), §10
    # (TM grid -> ergodic), §9 (MC LLN). Same measure on both sides;
    # both -> the per-type P-ergodic moments as N, M -> infinity.
    # This is the apples-to-apples replacement for the deleted
    # TM-Q vs MC comparison.
    if per_type_rows:
        pt = []
        for i, tm_m, mc_m in per_type_rows:
            d_emp_pp = abs(tm_m["frac_employed"] - mc_m["frac_employed"]) * 100.0
            pt.append(
                (
                    i,
                    f"{tm_m['E_mNrm']:.4f}",
                    f"{mc_m['E_mNrm']:.4f}",
                    f"{rel_err(mc_m['E_mNrm'], tm_m['E_mNrm']):.2f}%",
                    f"{tm_m['E_cNrm']:.4f}",
                    f"{mc_m['E_cNrm']:.4f}",
                    f"{rel_err(mc_m['E_cNrm'], tm_m['E_cNrm']):.2f}%",
                    f"{tm_m['frac_employed']:.4f}",
                    f"{mc_m['frac_employed']:.4f}",
                    f"{d_emp_pp:.2f}",
                    f"{tm_m['Var_log_mNrm']:.5f}",
                    f"{mc_m['Var_log_mNrm']:.5f}",
                    f"{rel_err(mc_m['Var_log_mNrm'], tm_m['Var_log_mNrm']):.2f}%",
                )
            )
        print(
            f"\n  Per-type moments: TM-P ergodic ({tm_ref_label}, mCount={tm_ref_mCount}) vs "
            f"MC t=0 cross-section ({per_type_mc_label}, first seed)."
        )
        print(f"  [math-deriv] {MATH_REFS['type_moments_P']}")
        print_table(
            "Phase 1 (continued): Per-type baseline moments — TM-P vs MC ✓ PROVEN",
            pt,
            [
                "i",
                "E[m]_TMP",
                "E[m]_MC",
                "m err%",
                "E[c]_TMP",
                "E[c]_MC",
                "c err%",
                "emp_TMP",
                "emp_MC",
                "|d_emp|pp",
                "Vlnm_TMP",
                "Vlnm_MC",
                "Vm err%",
            ],
        )
    return {
        "tm": tm_results,
        "mc": mc_results,
        "ref_AggCons_pc_tm": ref_AggCons_pc_tm,
        "per_type_tm_ref_label": tm_ref_label,
        "per_type_tm_mCount": tm_ref_mCount,
    }


# ─── Phase 2: No-Recession Stimulus Check ────────────────────────────

def phase2_norec_check(mc_configs=None, tm_configs=None):
    """Compare no-recession stimulus check across methods."""
    if mc_configs is None or tm_configs is None:
        d_mc, d_tm = default_configs_for_phase("norec-check")
        if mc_configs is None: mc_configs = d_mc
        if tm_configs is None: tm_configs = d_tm
    _warn_if_not_convergence_test("norec-check", mc_configs, tm_configs)

    print("\n" + "#" * 70)
    print("# PHASE 2: No-Recession Stimulus Check")
    print("#" * 70)

    return _run_norec_experiment("Check", mc_configs, tm_configs)


def phase3_norec_ui(mc_configs=None, tm_configs=None):
    """Compare no-recession UI (unemployment benefit) extension across methods."""
    if mc_configs is None or tm_configs is None:
        d_mc, d_tm = default_configs_for_phase("norec-ui")
        if mc_configs is None: mc_configs = d_mc
        if tm_configs is None: tm_configs = d_tm
    _warn_if_not_convergence_test("norec-ui", mc_configs, tm_configs)

    print("\n" + "#" * 70)
    print("# PHASE 3: No-Recession UI Extension")
    print("#" * 70)

    return _run_norec_experiment("UI", mc_configs, tm_configs)


def phase4_norec_taxcut(mc_configs=None, tm_configs=None):
    """Compare no-recession tax cut across methods (separate experiment from UI)."""
    if mc_configs is None or tm_configs is None:
        d_mc, d_tm = default_configs_for_phase("norec-taxcut")
        if mc_configs is None: mc_configs = d_mc
        if tm_configs is None: tm_configs = d_tm
    _warn_if_not_convergence_test("norec-taxcut", mc_configs, tm_configs)

    print("\n" + "#" * 70)
    print("# PHASE 4: No-Recession Tax Cut")
    print("#" * 70)

    return _run_norec_experiment("TaxCut", mc_configs, tm_configs)


def _run_norec_experiment(shock_type, mc_configs, tm_configs):
    """Generic no-recession experiment runner for all three methods."""

    # --- TM reference ---
    tm_ref_label = tm_configs[-1]
    tm_ref_mCount = TM_CONFIGS[tm_ref_label]["mCount"]

    print(f"\nComputing TM reference ({tm_ref_label}, mCount={tm_ref_mCount})...")
    t0 = time.time()
    economy_tm, meta = setup_economy()
    baseline_tm = compute_baseline_tm_data(economy_tm, mCount=tm_ref_mCount, neutral_measure=True)
    base_tm_results = run_experiment_tm(economy_tm, shock_type="base",
                                        mCount=tm_ref_mCount, neutral_measure=True)

    changes_map = {
        "Check": meta["Check_changes"],
        "UI": meta["UI_changes"],
        "TaxCut": meta["TaxCut_changes"],
    }
    changes = changes_map[shock_type]

    eco_tm = deepcopy(economy_tm)
    eco_tm.switch_shock_type(shock_type)
    solve_or_cache(eco_tm, shock_type)

    EconomyMrkv_init = list(np.arange(1, meta["num_experiment_periods"] + 1) * 2) + [0] * 20
    ref_results = run_experiment_tm_nonbase(
        eco_tm, shock_type, EconomyMrkv_init,
        baseline_tm, mCount=tm_ref_mCount, neutral_measure=True,
    )
    t_ref = time.time() - t0

    Rfree = economy_tm.agents[0].Rfree[0]
    act_T = economy_tm.act_T
    ref_npv_c = calculate_NPV(
        np.array(ref_results["AggCons"]) - np.array(base_tm_results["AggCons"]),
        act_T, Rfree,
    )[-1]
    ref_npv_y = calculate_NPV(
        np.array(ref_results["AggIncome"]) - np.array(base_tm_results["AggIncome"]),
        act_T, Rfree,
    )[-1]
    ref_mult = ref_npv_c / ref_npv_y if abs(ref_npv_y) > 1e-10 else float("nan")
    print(f"  TM ref: NPV_C={ref_npv_c:.6f}, NPV_Y={ref_npv_y:.6f}, mult={ref_mult:.4f} ({t_ref:.1f}s)")

    # --- TM sweep ---
    tm_results = {}
    for tm_label in tm_configs[:-1]:
        mCount = TM_CONFIGS[tm_label]["mCount"]
        t0 = time.time()
        bl_tm = compute_baseline_tm_data(economy_tm, mCount=mCount, neutral_measure=True)
        base_r = run_experiment_tm(economy_tm, shock_type="base", mCount=mCount, neutral_measure=True)

        eco = deepcopy(economy_tm)
        eco.switch_shock_type(shock_type)
        solve_or_cache(eco, shock_type)
        r = run_experiment_tm_nonbase(eco, shock_type, EconomyMrkv_init, bl_tm,
                                      mCount=mCount, neutral_measure=True)
        elapsed = time.time() - t0

        npv_c = calculate_NPV(np.array(r["AggCons"]) - np.array(base_r["AggCons"]), act_T, Rfree)[-1]
        npv_y = calculate_NPV(np.array(r["AggIncome"]) - np.array(base_r["AggIncome"]), act_T, Rfree)[-1]
        mult = npv_c / npv_y if abs(npv_y) > 1e-10 else float("nan")

        tm_results[tm_label] = {"npv_c": npv_c, "npv_y": npv_y, "mult": mult, "time": elapsed}
        print(f"  {tm_label}: mult={mult:.4f}, err={rel_err(mult, ref_mult):.4f}%, {elapsed:.1f}s")

    tm_results[tm_ref_label] = {"npv_c": ref_npv_c, "npv_y": ref_npv_y, "mult": ref_mult, "time": t_ref}

    # --- MC sweep ---
    mc_results = {}
    for mc_label in mc_configs:
        cfg = MC_CONFIGS[mc_label]
        seeds = cfg["seeds"]
        N_total = cfg["AgentCountTotal"]

        # RULE: NEVER construct hybrid ratios where the numerator and
        # denominator use different measures (P vs Q). For example,
        # `NPV(ΔAggCons_Q) / NPV(ΔAggIncome_P)` is meaningless — it carries
        # an E_P[p] scale factor and cannot be compared to a same-measure
        # multiplier. Report P-only and Q-only multipliers, never mixed.
        # A Q-track multiplier requires a Q-track income leg; until the Q
        # income leg is wired through the dual-MC shocks we do NOT report
        # any Q-mult at all.
        seed_mult_P = []
        seed_npv_c_P = []
        t0_all = time.time()

        for seed in seeds:
            use_dual = HAS_DUAL
            # Profile target: setup_economy is called once per seed and
            # includes a fresh solve. Plan 2 v3 cache target (most of
            # the work in setup_economy is the underlying solve, which
            # is RNG-independent and reusable across seeds).
            with profile_block(f"_run_norec.setup_economy(seed={seed})"):
                economy_mc, meta_mc = setup_economy(
                    AgentCountTotal_override=N_total,
                    seed_offset=seed * 100,
                    use_dual=use_dual,
                )
            with profile_block(f"_run_norec.compute_baseline_tm_data(mc_init,seed={seed})"):
                tm_init = compute_baseline_tm_data(economy_mc, mCount=50, neutral_measure=True)
            with profile_block(f"_run_norec.mc_burnin(seed={seed})"):
                mc_burnin(economy_mc, warmup=24, tm_data=tm_init, use_dual=use_dual)
            intended_T = int(economy_mc.act_T)
            economy_mc.save_state()
            economy_mc.switch_to_counterfactual_mode("base")
            restore_intended_act_T_after_counterfactual_switch(economy_mc, intended_T)
            economy_mc.make_idiosyncratic_shock_histories()

            with profile_block(f"_run_norec.run_experiment(base,seed={seed})"):
                base_r = economy_mc.run_experiment(**deepcopy(meta_mc["base_dict"]), Full_Output=True)
            economy_mc.store_baseline(base_r["AggCons"])

            eco = deepcopy(economy_mc)
            eco.switch_shock_type(shock_type)
            solve_or_cache(eco, shock_type)
            dictt = deepcopy(meta_mc["base_dict"])
            dictt.update(**changes_map[shock_type])
            dictt["EconomyMrkv_init"] = list(np.arange(1, meta_mc["num_experiment_periods"] + 1) * 2) + [0] * 20
            exp_r = eco.run_experiment(**dictt, Full_Output=True)

            Rfree_mc = economy_mc.agents[0].Rfree[0]
            act_T_mc = economy_mc.act_T

            delta_c = np.array(exp_r["AggCons"]) - np.array(base_r["AggCons"])
            delta_y = np.array(exp_r["AggIncome"]) - np.array(base_r["AggIncome"])
            npv_c = calculate_NPV(delta_c, act_T_mc, Rfree_mc)[-1]
            npv_y = calculate_NPV(delta_y, act_T_mc, Rfree_mc)[-1]
            mult = npv_c / npv_y if abs(npv_y) > 1e-10 else float("nan")
            seed_mult_P.append(mult)
            seed_npv_c_P.append(npv_c)

            # Intentionally NOT computing a Q-track multiplier here.
            # AggCons_Q would need AggIncome_Q for a same-measure ratio; the
            # Q-income leg is not wired through dual-MC shocks yet. Mixing
            # NPV(ΔAggCons_Q) with NPV(ΔAggIncome_P) is a hybrid ratio and
            # is forbidden — see rule comment above.

        elapsed = time.time() - t0_all
        mc_results[mc_label] = {
            "mult_P_mean": np.mean(seed_mult_P),
            "mult_P_se": np.std(seed_mult_P) / max(np.sqrt(len(seeds)), 1),
            "npv_c_P_mean": np.mean(seed_npv_c_P),
            "n_seeds": len(seeds),
            "time": elapsed,
        }
        pmc = mc_results[mc_label]
        p_err = rel_err(pmc["mult_P_mean"], ref_mult)
        print(f"  {mc_label} (N={N_total}, {len(seeds)} seeds): "
              f"P-MC mult={pmc['mult_P_mean']:.4f} err={p_err:.2f}%, {elapsed:.1f}s")

    # --- Summary table ---
    rows = []
    for label, res in tm_results.items():
        rows.append((label, f"{res['mult']:.4f}",
                     f"{rel_err(res['mult'], ref_mult):.2f}%",
                     f"{res['time']:.1f}s"))
    for label, res in mc_results.items():
        rows.append((f"{label} (P)", f"{res['mult_P_mean']:.4f}",
                     f"{rel_err(res['mult_P_mean'], ref_mult):.2f}%",
                     f"{res['time']:.1f}s"))

    # math-deriv: per-shock-type citation. UI and TaxCut are PROVEN
    # under TMMC §13.5 (their policy effects are p-linear). Check is
    # also PROVEN, but via the bucket scheme in
    # _compute_check_buckets, not via §13.5 directly — the Check
    # policy violates the p-linearity hypothesis but the bucket
    # scheme is asymptotically exact in n_buckets, and the default
    # of 50 buckets is well within the converged regime (BUG-022).
    is_check = shock_type == "Check"
    proven_label = "✓ PROVEN (bucket scheme)" if is_check else "✓ PROVEN"
    print(f"  [math-deriv] {_math_ref_for_norec_shock(shock_type)}")
    print_table(
        f"Phase: No-Rec {shock_type} — Multiplier {proven_label} "
        f"(same-measure only; ref = TM {tm_ref_label})",
        rows,
        ["Method", "Mult", "vs TM-ref", "Time"],
    )

    return {"tm": tm_results, "mc": mc_results, "ref_mult": ref_mult, "ref_npv_c": ref_npv_c}


# ─── Phase 5: Recession Baseline ────────────────────────────────────

def phase5_recession_baseline(mc_configs=None, tm_configs=None):
    """Compare recession baseline across methods."""
    if mc_configs is None or tm_configs is None:
        d_mc, d_tm = default_configs_for_phase("recession-baseline")
        if mc_configs is None: mc_configs = d_mc
        if tm_configs is None: tm_configs = d_tm
    _warn_if_not_convergence_test("recession-baseline", mc_configs, tm_configs)

    print("\n" + "#" * 70)
    print("# PHASE 5: Recession Baseline")
    print("#" * 70)

    return _run_recession_experiment("recession", mc_configs, tm_configs)


def phase6_recession_policies(mc_configs=None, tm_configs=None):
    """Compare recession + policy experiments."""
    if mc_configs is None or tm_configs is None:
        d_mc, d_tm = default_configs_for_phase("recession-policies")
        if mc_configs is None: mc_configs = d_mc
        if tm_configs is None: tm_configs = d_tm
    _warn_if_not_convergence_test("recession-policies", mc_configs, tm_configs)

    print("\n" + "#" * 70)
    print("# PHASE 6: Recession + Policy Experiments")
    print("#" * 70)

    results = {}
    for shock_type in ["recessionUI", "recessionTaxCut", "recessionCheck"]:
        print(f"\n--- {shock_type} ---")
        results[shock_type] = _run_recession_experiment(shock_type, mc_configs, tm_configs)
    return results


def _run_recession_experiment(shock_type, mc_configs, tm_configs):
    """Generic recession experiment runner."""

    tm_ref_label = tm_configs[-1]
    tm_ref_mCount = TM_CONFIGS[tm_ref_label]["mCount"]

    print(f"\nComputing TM reference ({tm_ref_label})...")
    t0 = time.time()
    # Profile target: TM-side setup. Includes the heavy base-state solve.
    with profile_block(f"_run_recession.setup_economy_tm({shock_type})"):
        economy_tm, meta = setup_economy()
    with profile_block(f"_run_recession.compute_baseline_tm_data_tm({shock_type})"):
        baseline_tm = compute_baseline_tm_data(economy_tm, mCount=tm_ref_mCount, neutral_measure=True)
    with profile_block(f"_run_recession.run_experiment_tm(base,{shock_type})"):
        base_tm_results = run_experiment_tm(economy_tm, shock_type="base",
                                            mCount=tm_ref_mCount, neutral_measure=True)

    changes_map = {
        "recession": meta["recession_changes"],
        "recessionCheck": meta["recession_Check_changes"],
        "recessionUI": meta["recession_UI_changes"],
        "recessionTaxCut": meta["recession_TaxCut_changes"],
    }
    changes = changes_map[shock_type]
    max_rec = meta["max_recession_duration"]
    if TEST_DRIVER_MAX_RECESSION_DURATION is not None:
        max_rec = min(max_rec, TEST_DRIVER_MAX_RECESSION_DURATION)
    num_exp = meta["num_experiment_periods"]

    eco_tm = deepcopy(economy_tm)
    eco_tm.switch_shock_type(shock_type)
    solve_or_cache(eco_tm, shock_type)

    Rspell = eco_tm.agents[0].Rspell
    R_persist = 1.0 - 1.0 / Rspell
    recession_prob_array = np.array([R_persist ** t * (1 - R_persist) for t in range(max_rec)])
    recession_prob_array[-1] = 1.0 - np.sum(recession_prob_array[:-1])

    output_keys = ["NPV_AggIncome", "NPV_AggCons", "AggIncome", "AggCons"]
    all_results_tm = []
    for t in range(max_rec):
        EconomyMrkv_init = list(np.arange(1, num_exp + 1) * 2) + [0] * 20
        EconomyMrkv_init[0:t + 1] = (np.array(EconomyMrkv_init[0:t + 1]) + 1).tolist()
        r = run_experiment_tm_nonbase(eco_tm, shock_type, EconomyMrkv_init,
                                      baseline_tm, mCount=tm_ref_mCount, neutral_measure=True)
        all_results_tm.append(r)

    ref_avg = {}
    for key in output_keys:
        ref_avg[key] = np.sum(
            np.array([all_results_tm[t][key] * recession_prob_array[t] for t in range(max_rec)]),
            axis=0,
        )
    t_ref = time.time() - t0

    Rfree = economy_tm.agents[0].Rfree[0]
    act_T = economy_tm.act_T

    if shock_type == "recession":
        ref_n_tm = sum(a.AgentCount for a in economy_tm.agents)
        ref_npv_c = calculate_NPV(ref_avg["AggCons"] - np.array(base_tm_results["AggCons"]), act_T, Rfree)[-1]
        ref_C_mean = float(np.mean(ref_avg["AggCons"]))
        ref_C_mean_pc = ref_C_mean / ref_n_tm
        print(
            f"  TM ref: mean AggCons={ref_C_mean:.6f} (per-capita={ref_C_mean_pc:.6f}, N={ref_n_tm}), "
            f"NPV_delta_C={ref_npv_c:.6f} ({t_ref:.1f}s)"
        )
        ref_val = ref_C_mean_pc
    else:
        base_rec_tm = _compute_recession_baseline_tm(economy_tm, baseline_tm,
                                                      meta, tm_ref_mCount)
        delta_c = ref_avg["AggCons"] - base_rec_tm["AggCons"]
        delta_y = ref_avg["AggIncome"] - base_rec_tm["AggIncome"]
        ref_npv_c = calculate_NPV(delta_c, act_T, Rfree)[-1]
        ref_npv_y = calculate_NPV(delta_y, act_T, Rfree)[-1]
        ref_mult = ref_npv_c / ref_npv_y if abs(ref_npv_y) > 1e-10 else float("nan")
        print(f"  TM ref: mult={ref_mult:.4f}, NPV_C={ref_npv_c:.6f} ({t_ref:.1f}s)")
        ref_val = ref_mult

    # --- MC sweep ---
    mc_results = {}
    for mc_label in mc_configs:
        cfg = MC_CONFIGS[mc_label]
        seeds = cfg["seeds"]
        N_total = cfg["AgentCountTotal"]
        seed_vals_P = []
        seed_vals_Q = []
        t0_all = time.time()

        for seed in seeds:
            use_dual = HAS_DUAL
            economy_mc, meta_mc = setup_economy(
                AgentCountTotal_override=N_total,
                seed_offset=seed * 100,
                use_dual=use_dual,
            )
            N_mc = sum(a.AgentCount for a in economy_mc.agents)
            tm_init = compute_baseline_tm_data(economy_mc, mCount=50, neutral_measure=True)
            mc_burnin(economy_mc, warmup=24, tm_data=tm_init, use_dual=use_dual)
            intended_T = int(economy_mc.act_T)
            economy_mc.save_state()
            economy_mc.switch_to_counterfactual_mode("base")
            restore_intended_act_T_after_counterfactual_switch(economy_mc, intended_T)
            economy_mc.make_idiosyncratic_shock_histories()

            base_r = economy_mc.run_experiment(**deepcopy(meta_mc["base_dict"]), Full_Output=True)
            economy_mc.store_baseline(base_r["AggCons"])

            if shock_type == "recession":
                avg_r = run_mc_recession_experiment(
                    economy_mc, shock_type, changes,
                    meta_mc["base_dict"], max_rec, num_exp,
                )
                val_P = float(np.mean(avg_r["AggCons"])) / N_mc
                seed_vals_P.append(val_P)
                if "AggCons_Q" in avg_r:
                    seed_vals_Q.append(float(np.mean(avg_r["AggCons_Q"])) / N_mc)
            else:
                rec_base_r = run_mc_recession_experiment(
                    economy_mc, "recession", meta_mc["recession_changes"],
                    meta_mc["base_dict"], max_rec, num_exp,
                )
                avg_r = run_mc_recession_experiment(
                    economy_mc, shock_type, changes,
                    meta_mc["base_dict"], max_rec, num_exp,
                )
                Rfree_mc = economy_mc.agents[0].Rfree[0]
                act_T_mc = economy_mc.act_T
                delta_c = avg_r["AggCons"] - rec_base_r["AggCons"]
                delta_y = avg_r["AggIncome"] - rec_base_r["AggIncome"]
                npv_c = calculate_NPV(delta_c, act_T_mc, Rfree_mc)[-1]
                npv_y = calculate_NPV(delta_y, act_T_mc, Rfree_mc)[-1]
                mult = npv_c / npv_y if abs(npv_y) > 1e-10 else float("nan")
                seed_vals_P.append(mult)

        elapsed = time.time() - t0_all
        mc_results[mc_label] = {
            "val_P_mean": np.mean(seed_vals_P),
            "val_P_se": np.std(seed_vals_P) / max(np.sqrt(len(seeds)), 1),
            "val_Q_mean": np.mean(seed_vals_Q) if seed_vals_Q else None,
            "n_seeds": len(seeds),
            "time": elapsed,
        }
        pmc = mc_results[mc_label]
        q_rec = ""
        if shock_type == "recession" and pmc.get("val_Q_mean") is not None:
            q_rec = (
                f", Q-MC_pc={pmc['val_Q_mean']:.6f} err={rel_err(pmc['val_Q_mean'], ref_val):.2f}%"
            )
        # math-deriv: recession baseline (shock_type='recession') reports
        # AggCons per-capita -> rec_agg = TMMC §3, §6.5 (transition), §13.
        # Both methods -> E_P[p_t * c_t] under the recession Markov path.
        # Recession+policy (other shock_types) reports a multiplier ->
        # rec_mult = PARTIALLY PROVEN, TMMC §13.4 + §6.5 + HARM §7
        # (same caveat as no-rec multiplier; see registry items 6, 8).
        _rec_cite = MATH_REFS["rec_agg"] if shock_type == "recession" else MATH_REFS["rec_mult"]
        print(f"  [math-deriv] {_rec_cite}")
        print(
            f"  {mc_label}: P-MC={pmc['val_P_mean']:.6f} err={rel_err(pmc['val_P_mean'], ref_val):.2f}%"
            f"{q_rec}, {elapsed:.1f}s"
        )

    return {"mc": mc_results, "ref_val": ref_val}


def phase7_ad_loop(mc_configs=None, tm_configs=None, ad_policies=None):
    """
    Phase 7 — AD feedback loop multiplier comparison (real version).

    Computes the canonical HAFiscal AD multiplier and compares TM-AD vs
    MC-AD. The AD multiplier is

        mult^AD = NPV(<AD policy avg> − <AD rec_baseline avg>) /
                  NPV(<AD policy income avg> − <AD rec_baseline income avg>)

    where <X avg> is averaged over recession durations weighted by the
    recession_prob_array (geometric distribution from Rspell). The
    "AD rec_baseline" is the recession-only experiment (no policy) with
    AD feedback active — same shape as phase 6's _compute_recession_baseline_tm
    but with run_ad_tm / solve_ad_recession in place of the non-AD calls.

    For each shock type (the policy and the recession baseline), the
    AD-converged cFunc is trained ONCE on the worst-case path; then the
    propagation across durations is cheap (TM uses run_ad_tm with
    skip_training=True; MC just calls run_experiment with the converged
    cFunc, no further iteration). This amortizes the AD iteration cost.

    Parameters
    ----------
    mc_configs, tm_configs : list[str] or None
        MC and TM ladder labels. Defaults to recession-policies defaults.
    ad_policies : list[str] or None
        Subset of {"recessionUI", "recessionTaxCut", "recessionCheck"}.
        Defaults to ["recessionUI"] (the canonical AD policy in HAFiscal).
        Each policy roughly doubles the wall clock at HS_Only/MC-med.

    Notes
    -----
    Wall-clock cost is dominated by the MC AD iteration. At HS_Only,
    one solve_ad_recession call is ~5-10 nested HARK solves; with N seeds
    and (1 baseline + len(ad_policies)) shock types, you pay
    ~N × (1 + len(ad_policies)) trainings on the MC side.

    The signal of the AD effect depends on TEST_DRIVER_MAX_RECESSION_DURATION:
    longer recessions push Cratio further from 1 and exercise the AD
    feedback loop more. At the default cap of 2, the AD effect is small.
    """
    if ad_policies is None:
        ad_policies = ["recessionUI"]
    if mc_configs is None or tm_configs is None:
        d_mc, d_tm = default_configs_for_phase("recession-policies")
        if mc_configs is None: mc_configs = d_mc
        if tm_configs is None: tm_configs = d_tm
    _warn_if_not_convergence_test("ad-loop", mc_configs, tm_configs)

    print("\n" + "#" * 70)
    print(f"# PHASE 7: AD loop (TM-AD vs MC-AD, policies={ad_policies})")
    print("#" * 70)

    tm_ref_label = tm_configs[-1]
    tm_ref_mCount = TM_CONFIGS[tm_ref_label]["mCount"]
    changes_key_for = {
        "recession": "recession_changes",
        "recessionUI": "recession_UI_changes",
        "recessionTaxCut": "recession_TaxCut_changes",
        "recessionCheck": "recession_Check_changes",
    }

    # ─── Setup TM (shared across all shock types) ───
    print(f"\nComputing TM AD reference ({tm_ref_label}, mCount={tm_ref_mCount})...")
    t0 = time.time()
    economy_tm, meta = setup_economy()
    Rfree = economy_tm.agents[0].Rfree[0]
    act_T = economy_tm.act_T
    num_exp = meta["num_experiment_periods"]

    # Determine the duration-averaging support: same as phase 6 with the
    # test-driver cap applied.
    max_rec = meta["max_recession_duration"]
    if TEST_DRIVER_MAX_RECESSION_DURATION is not None:
        max_rec = min(max_rec, TEST_DRIVER_MAX_RECESSION_DURATION)

    Rspell = economy_tm.agents[0].Rspell
    R_persist = 1.0 - 1.0 / Rspell
    rec_prob = np.array([R_persist ** t * (1 - R_persist) for t in range(max_rec)])
    rec_prob[-1] = 1.0 - np.sum(rec_prob[:-1])
    print(f"  duration support: {max_rec} (rec_prob = {rec_prob.round(4).tolist()})")

    def _build_rec_path(t):
        path = list(np.arange(1, num_exp + 1) * 2) + [0] * 20
        path[0:t + 1] = (np.array(path[0:t + 1]) + 1).tolist()
        return path

    baseline_tm = compute_baseline_tm_data(economy_tm, mCount=tm_ref_mCount,
                                           neutral_measure=True)
    base_tm_results = run_experiment_tm(economy_tm, shock_type="base",
                                        mCount=tm_ref_mCount, neutral_measure=True)
    AggCons_baseline = np.array(base_tm_results["AggCons"])

    ADelasticity = float(getattr(economy_tm, "demand_ADelasticity", 0.3))
    num_iter_ad = int(meta.get("num_max_iterations_solvingAD", 5))
    conv_tol_ad = float(meta.get("convergence_tol_solvingAD", 0.01))

    # ─── TM AD per shock_type, with duration averaging ───
    def _tm_ad_for_shock(shock_type):
        eco = deepcopy(economy_tm)
        eco.switch_shock_type(shock_type)
        solve_or_cache(eco, shock_type)
        per_duration = []
        cratio_means = []
        for t in range(max_rec):
            path_t = _build_rec_path(t)
            r_t = run_ad_tm(
                eco, shock_type, path_t, baseline_tm, AggCons_baseline,
                ADelasticity=ADelasticity,
                num_max_iterations=num_iter_ad,
                convergence_tol=conv_tol_ad,
                mCount=tm_ref_mCount,
                neutral_measure=True,
                verbose=False,
                skip_training=(t > 0),
            )
            per_duration.append(r_t)
            c_hist = np.array(r_t.get("Cratio_hist", [1.0] * act_T))
            cratio_means.append(float(np.mean(c_hist)))
        keys = ["NPV_AggIncome", "NPV_AggCons", "AggIncome", "AggCons"]
        avg = {}
        for key in keys:
            avg[key] = np.sum(
                np.array([per_duration[t][key] * rec_prob[t]
                          for t in range(max_rec)]),
                axis=0,
            )
        avg["cratio_means"] = cratio_means
        return avg

    # ─── TM no-AD: needed to compute the policy-cost denominator
    # NPV(ΔY_noAD), which is held FIXED across the no-AD and AD multipliers
    # (canonical convention; see Output_Results.py:210 NPV_AddInc_*).
    def _tm_noAD_for_shock(shock_type):
        eco = deepcopy(economy_tm)
        eco.switch_shock_type(shock_type)
        solve_or_cache(eco, shock_type)
        per_duration = []
        for t in range(max_rec):
            r_t = run_experiment_tm_nonbase(
                eco, shock_type, _build_rec_path(t),
                baseline_tm, mCount=tm_ref_mCount,
                neutral_measure=True, verbose=False,
            )
            per_duration.append(r_t)
        keys = ["NPV_AggIncome", "NPV_AggCons", "AggIncome", "AggCons"]
        avg = {}
        for key in keys:
            avg[key] = np.sum(
                np.array([per_duration[t][key] * rec_prob[t]
                          for t in range(max_rec)]),
                axis=0,
            )
        return avg

    tm_noAD_recbase = _tm_noAD_for_shock("recession")
    tm_noAD_pol_results = {pol: _tm_noAD_for_shock(pol) for pol in ad_policies}

    tm_ad_recbase = _tm_ad_for_shock("recession")
    tm_ad_pol_results = {pol: _tm_ad_for_shock(pol) for pol in ad_policies}
    t_tm = time.time() - t0
    print(f"  TM AD trained for {1 + len(ad_policies)} shock types in {t_tm:.1f}s")

    # ─── TM no-AD and AD multipliers, both using fixed no-AD policy-cost denom ───
    tm_noAD_mult = {}
    tm_ad_mult = {}
    for pol in ad_policies:
        # Fixed denominator: policy expenditure from the no-AD comparison
        npv_y_noAD = calculate_NPV(
            tm_noAD_pol_results[pol]["AggIncome"] - tm_noAD_recbase["AggIncome"],
            act_T, Rfree)[-1]
        npv_c_noAD = calculate_NPV(
            tm_noAD_pol_results[pol]["AggCons"] - tm_noAD_recbase["AggCons"],
            act_T, Rfree)[-1]
        tm_noAD_mult[pol] = (npv_c_noAD / npv_y_noAD) if abs(npv_y_noAD) > 1e-10 else float("nan")

        npv_c_AD = calculate_NPV(
            tm_ad_pol_results[pol]["AggCons"] - tm_ad_recbase["AggCons"],
            act_T, Rfree)[-1]
        # NB: denominator is the no-AD policy cost, not the AD-realized ΔY.
        tm_ad_mult[pol] = (npv_c_AD / npv_y_noAD) if abs(npv_y_noAD) > 1e-10 else float("nan")
        print(f"  TM ({pol}): no-AD mult={tm_noAD_mult[pol]:.4f}  "
              f"AD mult={tm_ad_mult[pol]:.4f}  "
              f"(NPV_ΔG_noAD={npv_y_noAD:.2f}; "
              f"Cratio means by dur: {[round(x, 4) for x in tm_ad_pol_results[pol]['cratio_means']]})")

    # ─── MC AD per shock_type, with duration averaging, per seed ───
    mc_results_by_pol = {pol: {} for pol in ad_policies}
    for mc_label in mc_configs:
        cfg = MC_CONFIGS[mc_label]
        seeds = cfg["seeds"]
        N_total = cfg["AgentCountTotal"]

        # seed_results[shock_type] = list (over seeds) of duration-averaged
        # dicts with NPV_AggCons / NPV_AggIncome / AggCons / AggIncome.
        # Tracks BOTH no-AD ('_noAD' suffix) and AD trajectories so we can
        # compute multipliers with the canonical fixed no-AD policy-cost
        # denominator (Output_Results.py:210 NPV_AddInc_*).
        seed_results = {st: [] for st in ["recession"] + list(ad_policies)}
        seed_results_noAD = {st: [] for st in ["recession"] + list(ad_policies)}
        t0_mc = time.time()

        for seed in seeds:
            economy_mc, meta_mc = setup_economy(
                AgentCountTotal_override=N_total, seed_offset=seed * 100)
            # Phase 7 uses the burnin sequence from
            # test_glp2_ad_comparison.py which is known to leave the
            # agents in a state where solve_ad_recession works correctly.
            # The standard mc_burnin path used by phases 2-6 leaves the
            # agents in a state where solve_ad_recession's internal
            # run_experiment iteration produces a cFunc with NaN
            # regions, causing downstream cFunc evaluations to fail
            # with "All-NaN slice encountered".
            economy_mc.reset()
            for a in economy_mc.agents:
                a.initialize_sim()
                a.AggDemandFac = 1.0
                a.RfreeNow = 1.0
                a.CaggNow = 1.0
            economy_mc.make_history()
            economy_mc.save_state()
            economy_mc.switch_to_counterfactual_mode("base")
            economy_mc.act_T = act_T
            for a in economy_mc.agents:
                a.T_sim = act_T
                a.EconomyMrkvNow_hist = [0] * act_T
            economy_mc.make_idiosyncratic_shock_histories()
            base_dict_mc = deepcopy(meta_mc["base_dict"])
            mc_base = economy_mc.run_experiment(**base_dict_mc, Full_Output=True)
            economy_mc.store_baseline(mc_base["AggCons"])

            # For each shock type (recession baseline + each policy), run
            # solve_ad_recession ONCE to converge the cFunc, then propagate
            # via run_experiment for every duration. The per-duration
            # run_experiment calls are made on FRESH deepcopies of the
            # post-AD-converged economy because solve_ad_recession's
            # internal iteration leaves agent state in an intermediate
            # condition that doesn't survive a second run_experiment call
            # without full re-initialization. Deepcopying per duration is
            # the simplest way to isolate them.
            for shock_type in ["recession"] + list(ad_policies):
                changes_key = changes_key_for.get(shock_type)

                # ---- no-AD leg: solve once (no AD iteration), propagate ----
                eco_noAD = deepcopy(economy_mc)
                eco_noAD.switch_shock_type(shock_type)
                eco_noAD.solve()
                duration_results_noAD = []
                for t in range(max_rec):
                    eco_t = deepcopy(eco_noAD)
                    d = deepcopy(meta_mc["base_dict"])
                    if changes_key is not None:
                        d.update(meta_mc[changes_key])
                    d["EconomyMrkv_init"] = _build_rec_path(t)
                    r_t = eco_t.run_experiment(**d, Full_Output=True)
                    duration_results_noAD.append(r_t)
                avg_noAD = {}
                for key in ["AggCons", "AggIncome"]:
                    avg_noAD[key] = np.sum(
                        np.array([np.asarray(duration_results_noAD[t][key]) * rec_prob[t]
                                  for t in range(max_rec)]),
                        axis=0,
                    )
                seed_results_noAD[shock_type].append(avg_noAD)

                # ---- AD leg: solve_ad_recession, propagate per duration ----
                eco_st_master = deepcopy(economy_mc)
                eco_st_master.switch_shock_type(shock_type)
                eco_st_master.solve_ad_recession(
                    num_max_iterations=num_iter_ad,
                    convergence_cutoff=conv_tol_ad,
                    shock_type=shock_type,
                )
                duration_results = []
                for t in range(max_rec):
                    eco_st = deepcopy(eco_st_master)
                    d = deepcopy(meta_mc["base_dict"])
                    if changes_key is not None:
                        d.update(meta_mc[changes_key])
                    d["EconomyMrkv_init"] = _build_rec_path(t)
                    r_t = eco_st.run_experiment(**d, Full_Output=True)
                    duration_results.append(r_t)
                avg = {}
                for key in ["AggCons", "AggIncome"]:
                    avg[key] = np.sum(
                        np.array([np.asarray(duration_results[t][key]) * rec_prob[t]
                                  for t in range(max_rec)]),
                        axis=0,
                    )
                seed_results[shock_type].append(avg)

        elapsed = time.time() - t0_mc

        # Cross-seed average then per-policy multiplier vs the recession baseline.
        def _seed_mean(slist, key):
            arrs = [np.asarray(s[key]) for s in slist]
            return np.mean(np.stack(arrs, axis=0), axis=0)

        rec_AggCons_mc = _seed_mean(seed_results["recession"], "AggCons")
        rec_AggIncome_mc = _seed_mean(seed_results["recession"], "AggIncome")
        rec_AggCons_mc_noAD = _seed_mean(seed_results_noAD["recession"], "AggCons")
        rec_AggIncome_mc_noAD = _seed_mean(seed_results_noAD["recession"], "AggIncome")
        for pol in ad_policies:
            pol_AggCons_mc = _seed_mean(seed_results[pol], "AggCons")
            pol_AggCons_mc_noAD = _seed_mean(seed_results_noAD[pol], "AggCons")
            pol_AggIncome_mc_noAD = _seed_mean(seed_results_noAD[pol], "AggIncome")
            # Fixed denominator: no-AD policy expenditure
            npv_y_noAD = calculate_NPV(
                pol_AggIncome_mc_noAD - rec_AggIncome_mc_noAD, act_T, Rfree)[-1]
            npv_c_noAD = calculate_NPV(
                pol_AggCons_mc_noAD - rec_AggCons_mc_noAD, act_T, Rfree)[-1]
            npv_c_AD = calculate_NPV(
                pol_AggCons_mc - rec_AggCons_mc, act_T, Rfree)[-1]
            m_noAD = (npv_c_noAD / npv_y_noAD) if abs(npv_y_noAD) > 1e-10 else float("nan")
            m_AD = (npv_c_AD / npv_y_noAD) if abs(npv_y_noAD) > 1e-10 else float("nan")
            mc_results_by_pol[pol][mc_label] = {
                "mult_noAD_mean": m_noAD,
                "mult_AD_mean": m_AD,
                "n_seeds": len(seeds),
                "time": elapsed,
            }
        print(f"  {mc_label} (N={N_total}, {len(seeds)} seeds): "
              f"no-AD/AD mults = "
              f"{ {pol: (round(mc_results_by_pol[pol][mc_label]['mult_noAD_mean'], 4), round(mc_results_by_pol[pol][mc_label]['mult_AD_mean'], 4)) for pol in ad_policies} }  "
              f"({elapsed:.1f}s)")

    # ─── Summary table ───
    rows = []
    for pol in ad_policies:
        rows.append((f"{pol} TM",
                     f"{tm_noAD_mult[pol]:.4f}", f"{tm_ad_mult[pol]:.4f}",
                     f"{tm_ad_mult[pol]/tm_noAD_mult[pol]:.3f}x" if tm_noAD_mult[pol] else "—",
                     "—"))
        for mc_label, res in mc_results_by_pol[pol].items():
            ratio = (res["mult_AD_mean"] / res["mult_noAD_mean"]
                     if res["mult_noAD_mean"] else float("nan"))
            rows.append((f"{pol} {mc_label}",
                         f"{res['mult_noAD_mean']:.4f}",
                         f"{res['mult_AD_mean']:.4f}",
                         f"{ratio:.3f}x",
                         f"{res['time']:.1f}s"))

    print(f"  [math-deriv] AD comparison: NPV(ΔC_AD)/NPV(ΔY_noAD) "
          f"(canonical fixed policy-cost denom; Output_Results.py:210)")
    print_table(
        "Phase 7: AD-loop multiplier — no-AD vs AD (duration-averaged)",
        rows,
        ["Method", "no-AD Mult", "AD Mult", "AD/noAD", "Time"],
    )

    return {
        "tm_ad_mult": tm_ad_mult,
        "mc_ad_results": mc_results_by_pol,
        "ad_policies": ad_policies,
    }


def _compute_recession_baseline_tm(economy, baseline_tm, meta, mCount):
    """Compute recession-only TM results for use as baseline in policy comparison."""
    eco = deepcopy(economy)
    eco.switch_shock_type("recession")
    solve_or_cache(eco, "recession")

    max_rec = meta["max_recession_duration"]
    if TEST_DRIVER_MAX_RECESSION_DURATION is not None:
        max_rec = min(max_rec, TEST_DRIVER_MAX_RECESSION_DURATION)
    num_exp = meta["num_experiment_periods"]
    Rspell = eco.agents[0].Rspell
    R_persist = 1.0 - 1.0 / Rspell
    recession_prob_array = np.array([R_persist ** t * (1 - R_persist) for t in range(max_rec)])
    recession_prob_array[-1] = 1.0 - np.sum(recession_prob_array[:-1])

    output_keys = ["NPV_AggIncome", "NPV_AggCons", "AggIncome", "AggCons"]
    all_results = []
    for t in range(max_rec):
        mk = list(np.arange(1, num_exp + 1) * 2) + [0] * 20
        mk[0:t + 1] = (np.array(mk[0:t + 1]) + 1).tolist()
        r = run_experiment_tm_nonbase(eco, "recession", mk,
                                      baseline_tm, mCount=mCount, neutral_measure=True)
        all_results.append(r)
    avg = {}
    for key in output_keys:
        avg[key] = np.sum(
            np.array([all_results[t][key] * recession_prob_array[t] for t in range(max_rec)]),
            axis=0,
        )
    return avg


# ─── Phase registry (canonical names; stable across renumbering) ─────

def _phase_registry():
    """Ordered (canonical_id, runner). Canonical ids are the preferred ``--phase`` values."""
    return [
        ("harness", phase0_harness_checks),
        ("baseline", phase1_baseline_ergodic),
        ("norec-check", phase2_norec_check),
        ("norec-ui", phase3_norec_ui),
        ("norec-taxcut", phase4_norec_taxcut),
        ("recession-baseline", phase5_recession_baseline),
        ("recession-policies", phase6_recession_policies),
        ("ad-loop", phase7_ad_loop),
    ]


def _phase_alias_table():
    """Map normalized CLI tokens → canonical phase id (or 'all')."""
    reg = _phase_registry()
    m = {}
    for i, (cid, _) in enumerate(reg):
        m[cid] = cid
        m[str(i)] = cid
        m[f"phase{i}"] = cid
    m.update(
        {
            "multi-type-baseline": "baseline",
            "check": "norec-check",
            "ui": "norec-ui",
            "taxcut": "norec-taxcut",
            "ad": "ad-loop",
            "all": "all",
        }
    )
    return m


_PHASE_ALIASES = _phase_alias_table()


def normalize_phase_arg(raw: str) -> str:
    """
    Normalize ``--phase`` to a canonical id or ``all``.

    Accepts kebab-case names, legacy digits ``0``–``7``, and ``phase0``…``phase7``.
    """
    t = raw.lower().strip().replace("_", "-")
    if t not in _PHASE_ALIASES:
        names = [c for c, _ in _phase_registry()]
        raise ValueError(
            f"Unknown --phase {raw!r}. Expected one of: all, {', '.join(names)}, "
            "or legacy 0-7."
        )
    return _PHASE_ALIASES[t]


# ─── Main ────────────────────────────────────────────────────────────

def main():
    global RUN_PARAMETRIZATION
    parser = argparse.ArgumentParser(description="Asymptotic equality test suite (revised driver)")
    _names = ", ".join(c for c, _ in _phase_registry())
    parser.add_argument(
        "--phase",
        type=str,
        default="baseline",
        help=(
            f"Named step to run ({_names}), or 'all'. "
            "Legacy aliases: digits 0-7 and phase0…phase7 (same order as above)."
        ),
    )
    # NOTE: default=None (not []) so we can distinguish "user did not pass
    # the flag" from "user passed it explicitly". Required for --ladder
    # precedence logic below.
    parser.add_argument("--mc", type=str, nargs="*", default=None,
                        help="MC configs to test (e.g., MC-small MC-med). "
                             "Cannot be combined with --ladder.")
    parser.add_argument("--tm", type=str, nargs="*", default=None,
                        help="TM configs to test (e.g., TM-default TM-fine). "
                             "Cannot be combined with --ladder.")
    parser.add_argument(
        "--ladder",
        type=str,
        choices=sorted(LADDER_PRESETS.keys()),
        default=None,
        help=("Convergence-aware preset: runs exactly two paired cells "
              "(Cell 1 = smaller MC + TM mCount=50; Cell 2 = larger MC + "
              "TM mCount=100). Cannot be combined with --mc or --tm. "
              "See plans/20260408-1028h_asymptotic-equality-driver-ladder-presets_v2.md."),
    )
    parser.add_argument(
        "--parametrization",
        type=str,
        default="Reduced_Run",
        help="Parameters.return_parameters name: Reduced_Run (default), Smoke_Test, Baseline, …",
    )
    parser.add_argument(
        "--last-phase",
        type=str,
        default=None,
        help=("Run all phases from the start of the registry up to and "
              "including the named phase, then stop. Equivalent to "
              "--phase all but truncated at this phase. Useful to skip "
              "the recession + ad-loop phases while keeping single-process "
              "dispatch (so the solve cache survives across phases). "
              "Example: --last-phase norec-taxcut runs harness, baseline, "
              "norec-check, norec-ui, norec-taxcut and stops."),
    )
    args = parser.parse_args()
    RUN_PARAMETRIZATION = args.parametrization

    # --ladder precedence: hard error if mixed with explicit --mc/--tm.
    if args.ladder is not None and (args.mc is not None or args.tm is not None):
        parser.error("--ladder cannot be combined with --mc or --tm; pick one")

    try:
        canon = normalize_phase_arg(args.phase)
    except ValueError as e:
        parser.error(str(e))

    # --last-phase semantics: when set, run all phases from the start
    # of the registry up to and including the named phase, then stop.
    # Force canon = "all" unconditionally — if the user passed a
    # specific --phase X, --last-phase wins (their intent is clearly
    # "a range up to here", and silently ignoring --last-phase would
    # be more surprising than silently ignoring --phase).
    last_phase_idx = None
    if args.last_phase is not None:
        try:
            last_phase_canon = normalize_phase_arg(args.last_phase)
        except ValueError as e:
            parser.error(f"--last-phase: {e}")
        if last_phase_canon == "all":
            parser.error("--last-phase cannot be 'all'; name a specific phase")
        registry_ids = [cid for cid, _ in _phase_registry()]
        try:
            last_phase_idx = registry_ids.index(last_phase_canon)
        except ValueError:
            parser.error(f"--last-phase {last_phase_canon} not in phase registry")
        canon = "all"

    # Build the list of (mc_configs, tm_configs, label) tuples to dispatch.
    # Without --ladder this is a single tuple (the user's flags or per-phase
    # defaults). With --ladder it is one tuple per cell so each cell runs
    # independently and prints its own summary table.
    if args.ladder is not None:
        cells = LADDER_PRESETS[args.ladder]
        invocations = [
            ([mc_label], [tm_label], f"cell {i+1}/{len(cells)} ({mc_label} + {tm_label})")
            for i, (mc_label, tm_label) in enumerate(cells)
        ]
        print(f"\n[ladder] preset='{args.ladder}': running {len(cells)} paired cell(s)")
        for i, (mc_label, tm_label) in enumerate(cells):
            print(f"[ladder]   cell {i+1}: MC={mc_label}, TM={tm_label}")
        print(f"[ladder] convergence claim: cell 1 -> cell 2 simultaneously "
              f"increases N (MC) and mCount (TM), so any drift in MC<->TM "
              f"agreement between cells is informative.")
    else:
        invocations = [(args.mc, args.tm, None)]
        # Convergence-test invariant warning (Plan 1 v2 §B Task 5, revised).
        # A run is a valid convergence test if EITHER axis has multiple
        # configs:
        #   - multiple TM grids → demonstrates TM grid convergence
        #   - multiple MC sizes → demonstrates MC sample-size (SLLN) convergence
        # Either alone is enough. E.g. --mc MC-tiny MC-small --tm TM-100 is
        # a valid MC-convergence test against a known-converged TM-100
        # reference (TM grid sweep is unnecessary because TM-100 is already
        # converged at this scale; only the MC dimension needs demonstration).
        # The warning fires only when BOTH axes are length-1 (one cell, no
        # convergence dimension at all) — that's a single parity check, not
        # a convergence test.
        mc_n = len(args.mc) if args.mc is not None else 0
        tm_n = len(args.tm) if args.tm is not None else 0
        if mc_n == 1 and tm_n == 1:
            print(f"\n  ⚠  NOT A CONVERGENCE TEST: --mc={args.mc[0]} and "
                  f"--tm={args.tm[0]} are both single configs; this is a "
                  f"single-cell parity check, not a convergence test. "
                  f"To get a real convergence test, pass at least two "
                  f"configs on either axis (e.g. --mc MC-tiny MC-small "
                  f"--tm TM-100) or use --ladder smoke.")

    all_results = {}
    t_start = time.time()
    reg = _phase_registry()
    runner_by_id = dict(reg)

    # Single-process dispatch (canonical). Each phase × cell runs
    # inside the same Python process, so the SOLVE_CACHE survives
    # across phases and ladder cells. This is the default and the
    # *only* recommended invocation pattern.
    #
    # FUTURE WORK — remove the multi-process pattern entirely.
    # Earlier ladder runs used a bash loop that spawned one
    # `uv run python test_asymptotic_equality_revised.py --phase X`
    # per phase. That pattern existed before the SOLVE_CACHE landed
    # and is now strictly worse: the cache is reset between
    # processes, so each phase pays the full Bellman solve cost from
    # scratch (~12 min of waste per smoke run; see
    # plans/20260408-1028h_asymptotic-equality-driver-baseline-cache-refactor_v3.md).
    # The (theoretical) reasons one *might* still want the
    # multi-process pattern are:
    #   1. Crash containment: if phase 4 throws, phases 5-8 still
    #      run. → Already addressed in this loop by the per-phase
    #      try/except below; a phase failure logs and continues to
    #      the next.
    #   2. Memory isolation: a long-running Python process can in
    #      principle leak memory. → Not observed in practice at
    #      smoke or parity scale (HAFiscal stays well under 1 GB
    #      even after all 8 phases × 2 cells).
    #   3. Bisect-friendly debugging: rerun one phase in isolation
    #      by passing --phase X. → Orthogonal: the driver still
    #      accepts a single --phase argument.
    #   4. Per-phase log files. → Marginal; one combined log is
    #      easier to grep.
    # Caveat: the cache is process-local. If you ever need to run
    # two ladder cells in *parallel*, the multi-process pattern lets
    # you use multi-core; the single-process pattern does not.
    # Today the driver runs serially so this doesn't matter.
    for inv_mc, inv_tm, inv_label in invocations:
        if inv_label is not None:
            print(f"\n{'#' * 70}\n# LADDER {inv_label}\n{'#' * 70}")
        if canon == "all":
            phases_to_run = reg if last_phase_idx is None else reg[:last_phase_idx + 1]
            if last_phase_idx is not None:
                print(f"[last-phase] truncating phase list to "
                      f"{[cid for cid, _ in phases_to_run]}")
        else:
            phases_to_run = [(canon, runner_by_id[canon])]
        for cid, fn in phases_to_run:
            key = cid if inv_label is None else f"{cid}::{inv_label}"
            try:
                all_results[key] = fn(inv_mc, inv_tm)
            except Exception as exc:
                # Match the bash-loop's per-phase crash containment:
                # log the failure and continue with subsequent phases
                # and cells. This is the in-process equivalent of
                # `for p in phases; do uv run … --phase $p || true; done`.
                import traceback
                print(f"\n  ✗ PHASE {cid} FAILED ({inv_label or 'no-cell'}): "
                      f"{type(exc).__name__}: {exc}")
                traceback.print_exc()
                all_results[key] = {"_failed": True, "_exception": str(exc)}

    # Plan 1 v2 follow-up #1: combined paired-cell summary table.
    # When --ladder ran with multiple cells, print a single table that
    # shows each phase's headline number for every cell side-by-side,
    # so the convergence story is visible at a glance instead of buried
    # across the per-cell summary tables.
    if args.ladder is not None and len(invocations) > 1:
        _print_ladder_summary(args.ladder, invocations, all_results, canon, reg)

    total_time = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"  Total elapsed: {total_time:.0f}s ({total_time / 60:.1f} min)")
    print(f"{'=' * 70}")
    report_solve_cache_stats()


def _ladder_phase_headline(phase_id, result):
    """
    Extract a (label, value, fmt) tuple from a phase runner's result dict
    for the ladder summary table. Returns None if no headline can be
    extracted (e.g. ad-loop stub returns None; harness returns no scalar).
    """
    if result is None:
        return None
    if phase_id == "harness":
        return None  # harness reports drift, not a scalar headline
    if phase_id == "baseline":
        # ref_AggCons_pc_tm is the headline; MC error is the convergence
        # signal. Return the TM ref + MC P-mean from the first MC config.
        ref = result.get("ref_AggCons_pc_tm")
        mc = result.get("mc", {})
        if not mc or ref is None:
            return None
        first_mc_label = next(iter(mc))
        mc_val = mc[first_mc_label].get("AggCons_pc_P_mean")
        if mc_val is None:
            return None
        return ("AggCons_pc",
                f"TM={ref:.4f}",
                f"MC={mc_val:.4f}",
                f"err={rel_err(mc_val, ref):.2f}%")
    if phase_id in ("norec-check", "norec-ui", "norec-taxcut"):
        ref = result.get("ref_mult")
        mc = result.get("mc", {})
        if not mc or ref is None:
            return None
        first_mc_label = next(iter(mc))
        mc_val = mc[first_mc_label].get("mult_P_mean")
        if mc_val is None:
            return None
        return (f"{phase_id}",
                f"TM={ref:.4f}",
                f"MC={mc_val:.4f}",
                f"err={rel_err(mc_val, ref):.2f}%")
    if phase_id == "recession-baseline":
        ref = result.get("ref_val")
        mc = result.get("mc", {})
        if not mc or ref is None:
            return None
        first_mc_label = next(iter(mc))
        mc_val = mc[first_mc_label].get("val_P_mean")
        if mc_val is None:
            return None
        return ("rec-baseline",
                f"TM={ref:.4f}",
                f"MC={mc_val:.4f}",
                f"err={rel_err(mc_val, ref):.2f}%")
    if phase_id == "recession-policies":
        # Returns dict of shock_type -> per-experiment result; flatten by
        # picking the first sub-experiment's headline (recessionUI typically).
        if not isinstance(result, dict):
            return None
        for sub_id, sub in result.items():
            if isinstance(sub, dict) and "ref_val" in sub:
                ref = sub["ref_val"]
                mc = sub.get("mc", {})
                if mc:
                    first_mc_label = next(iter(mc))
                    mc_val = mc[first_mc_label].get("val_P_mean")
                    if mc_val is not None:
                        return (f"rec-{sub_id}",
                                f"TM={ref:.4f}",
                                f"MC={mc_val:.4f}",
                                f"err={rel_err(mc_val, ref):.2f}%")
        return None
    return None


def _print_ladder_summary(ladder_name, invocations, all_results, canon, reg):
    """
    Combined paired-cell summary table.

    For each phase that ran, prints one row per cell, side-by-side,
    so the user can see the cell-to-cell convergence directly.
    """
    cell_labels = [inv_label for _, _, inv_label in invocations if inv_label]
    if canon == "all":
        phase_ids = [cid for cid, _ in reg]
    else:
        phase_ids = [canon]

    print(f"\n{'#' * 70}")
    print(f"# LADDER SUMMARY — preset='{ladder_name}' "
          f"({len(cell_labels)} cells × {len(phase_ids)} phases)")
    print(f"# Convergence claim: as N (MC) and mCount (TM) both grow")
    print(f"#                    cell-to-cell, MC↔TM gaps should shrink.")
    print(f"{'#' * 70}\n")

    rows = []
    for phase_id in phase_ids:
        for cell_idx, cell_label in enumerate(cell_labels):
            key = f"{phase_id}::{cell_label}"
            result = all_results.get(key)
            head = _ladder_phase_headline(phase_id, result)
            if head is None:
                rows.append((phase_id if cell_idx == 0 else "",
                             f"cell {cell_idx + 1}", "—", "—", "—"))
                continue
            metric, tm_str, mc_str, err_str = head
            rows.append((phase_id if cell_idx == 0 else "",
                         f"cell {cell_idx + 1}", tm_str, mc_str, err_str))
    print_table(
        f"Ladder summary ({ladder_name})",
        rows,
        ["Phase", "Cell", "TM ref", "MC P-mean", "MC err vs TM"],
    )


if __name__ == "__main__":
    main()
