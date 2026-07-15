import numpy as np
import os
import sys
from pathlib import Path
from HARK.distributions import Uniform

# ESC-MOD-PHASE3-read: route the splurge target through the interpretation
# resolver so ESC reads `Result_AllTarget_ESC.txt` (its own Step-1 output)
# instead of CDC's bare `Result_AllTarget.txt`. Falls back to bare file if
# the suffixed variant doesn't exist (legacy compat).
_ha_root = Path(__file__).resolve().parent.parent
if str(_ha_root) not in sys.path:
    sys.path.insert(0, str(_ha_root))
from _interpretation import resolve_path as _resolve_path

# ============================================================================
# CANONICAL SOLUTION-APPROACH DEFAULTS (Plan A, 2026-06-10)
# ----------------------------------------------------------------------------
# Make the *decided* welfare method the DEFAULT, via os.environ.setdefault so
# explicit user/env overrides still win. Validated by the MC-vs-TM-a welfare
# cascade (conclusions_private/2026-06-10_mc_vs_tma_welfare_cascade_HS_Only.md),
# which ran on exactly this config. Decision source:
# conclusions_private/2026-06-10_welfare_method_unified_MC.md.
#
# HAFISCAL_QE_FIDELITY=1 (DEPRECATED — owner ruling 2026-06-13, Q4; scheduled for removal)
# skips these setdefaults so each call site falls back to its own legacy default
# (shuffle OFF, plain 'shuffle' transition, aMax=500, m-indexed TM), approximating the
# published-QE methodology. It is redundant and being retired: use the `as-corrected`
# WORLD for the debugged counterfactual and the old branch / frozen tag
# v2026-01-09-18-17 for EXACT published-QE. It no longer flips HAFISCAL_UI_STATE_ENCODING
# (coupling removed per ruling Q1 — UI encoding is purely the BUG-043 toggle handled by
# the world scheme; reproduce pre-2026-05-16 UI by setting HAFISCAL_UI_STATE_ENCODING=legacy).
# EstimParameters is imported by every entry point before any of these vars are
# read at runtime, so setting them here wins; setdefault lets explicit env win.
# ============================================================================

# ----- INTERPRETATION default-flip (owner ruling Q5, 2026-06-13; WIRED 2026-06-14) -----
# ESC is the adopted HEADLINE interpretation in BOTH worlds (config/catalog.py:
# interpretation canonical=ESC, paper=ESC). Make ESC the PRODUCTION default here via
# setdefault, so every entry point (each imports EstimParameters before any interp read)
# runs ESC unless the env says otherwise. UNCONDITIONAL — applied even under
# HAFISCAL_QE_FIDELITY=1, because the published-QE world is itself ESC (the reproduce.sh
# qe_fidelity profile exports ESC). CDC is now an explicit OPT-IN: the reproduce.sh
# production_*/tm_*/mc_* robustness profiles export HAFISCAL_INTERPRETATION=CDC and (being
# explicit) still win over this setdefault.
#   BUG-049 coupling: an ESC run MUST read ESC betas. The betas loader (Parameters.py ->
#   _interpretation.resolve_calib_path) looks for the _ESC[_ascorrected] DiscFacEstim file
#   and warns LOUDLY + falls back if it is missing. The baseline _ESC betas exist; the
#   robustness parametrizations regenerate theirs on demand.
#   The _interpretation.py library code-literal default stays 'CDC' (conservative for
#   direct importers and its unit tests); ESC is the *production* default, set right here.
# Refs: conclusions_private/20260613_config-worlds-definition-default-legacy.md (Q5);
#       plans/20260614_as-corrected-calibration-run-spec.md.
os.environ.setdefault('HAFISCAL_INTERPRETATION', 'ESC')

if os.environ.get('HAFISCAL_QE_FIDELITY', '') == '1':
    import warnings as _warnings
    _warnings.warn(
        "HAFISCAL_QE_FIDELITY is DEPRECATED and scheduled for removal (owner ruling "
        "2026-06-13, Q4). It is redundant: use the `as-corrected` world for the debugged "
        "counterfactual, or the frozen QE tag v2026-01-09-18-17 for exact published-QE. "
        "As of 2026-06-13 it no longer flips HAFISCAL_UI_STATE_ENCODING (coupling removed).",
        DeprecationWarning, stacklevel=2)
else:
    # ----- WORLD axis (R2 wiring 2026-06-13): config/ is the single source of truth -----
    # HAFISCAL_WORLD selects the results-semantics WORLD (orthogonal to the METHOD axis below):
    #   default      -> canonical post-paper config (the paper's headline numbers)
    #   as-corrected -> paper config + ALL-and-ONLY bug fixes (the honest counterfactual)
    # The values come from Code/HA-Models/config/catalog.py (the SoT), so the numbers can no
    # longer drift between this block and the catalog (guarded by config/test_runtime_parity.py).
    # NON-BREAKING for `default`: the catalog default-world values for the settings applied here
    # are byte-identical to the previous hardcoded literals — MC_SHUFFLE=1 (welfare MC shuffle ON),
    # SHUFFLE_MRKV_TRANSITION=stratified (NOT plain 'shuffle', the +8.26%-UI footgun, BUG-044),
    # SHUFFLE_NEWBORN_FIX=transition, TM_AMAX=1300, PERM_DURING_UNEMP=on, WELFARE6_FIX_DUR_AVG=on,
    # UI_STATE_ENCODING=bug_fix. Applied via setdefault (explicit env still wins).
    #   aMax=1300 is NOT a magic number: the TM grid must cover the MOST-PATIENT College
    #   discount-factor atom (the GIC-cap atom, GPF=theGICfactor=0.9995 under BUG-053) — its ergodic
    #   aNrm tail is the binding constraint; 1300 = production_aMax(). The mc engine keeps 1300 (NOT
    #   QE 500) because it seeds the MC cross-section from the TM ergodic dist (Simulate.py
    #   mc_use_tm_init), and a 500-truncated seed grid cannot be rebuilt by the 24-period warmup.
    #   Re-derive via production_aMax() if the calibration/theGICfactor changes. (See catalog tm_amax.)
    #
    # Deliberately NOT forced by the WORLD axis (owned elsewhere; forcing per-world would
    # silently change results):
    #   - HAFISCAL_INTERPRETATION: NOT world-varying (ESC in both worlds). The ESC production
    #     default-flip (owner ruling Q5) is wired ABOVE as an unconditional setdefault, not in
    #     this world loop — keeping it out of _WORLD_APPLY guarantees the worlds don't differ on it.
    #   - HAFISCAL_TM_A_INDEXED: set per-entry-point (do_all Step-5a) — the BUG-033 a-indexed fix.
    #   - estimation-only settings (gicx, nm_warm_start, nm_tol, theGICfactor): inert for a
    #     multiplier/welfare run and need matched re-estimation, so they are excluded.
    from config.catalog import resolve_world as _resolve_world  # pure data; _ha_root on sys.path
    _world = os.environ.get('HAFISCAL_WORLD', 'default').strip().lower()
    if _world not in ('default', 'as-corrected'):
        raise ValueError(
            f"HAFISCAL_WORLD={_world!r} invalid; expected 'default' or 'as-corrected'. "
            "exact published-QE is the frozen tag v2026-01-09-18-17, not a runtime world.")
    # The runtime, world-safe settings this block is authorized to apply (see exclusions above):
    _WORLD_APPLY = (
        'HAFISCAL_MC_SHUFFLE', 'HAFISCAL_SHUFFLE_MRKV_TRANSITION', 'HAFISCAL_SHUFFLE_NEWBORN_FIX',
        'HAFISCAL_TM_AMAX', 'HAFISCAL_PERM_DURING_UNEMP', 'HAFISCAL_WELFARE6_FIX_DUR_AVG',
        'HAFISCAL_UI_STATE_ENCODING',
    )
    _world_env = _resolve_world(_world, include_estimation_only=False)
    for _wk in _WORLD_APPLY:
        if _wk in _world_env:
            os.environ.setdefault(_wk, _world_env[_wk])
    if _world == 'as-corrected':
        import warnings as _warnings
        _warnings.warn(
            "HAFISCAL_WORLD=as-corrected applies the paper's discretionary RUNTIME choices on top of "
            "all bug-fixes (e.g. PERM_DURING_UNEMP=off), but the loaded discount-factor calibration is "
            "the CANONICAL re-estimated set. A fully-matched as-corrected counterfactual requires "
            "RE-ESTIMATING (beta,nabla) under these settings (PERM_DURING_UNEMP affects the estimate), "
            "so until that calibration exists this is a RUNTIME-ONLY counterfactual. See "
            "plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md (R2 / Q4 phase 2).",
            RuntimeWarning, stacklevel=2)

    # METHOD axis (IMPROVEMENT-001) — RENAMED 2026-06-13 (owner ruling Q3). Was HAFISCAL_MODE with
    # values default|legacy, whose 'legacy' value collided with the `as-corrected` WORLD. Now:
    #   HAFISCAL_MULTIPLIER_ENGINE=tm  (default) -> TM a-indexed multipliers
    #   HAFISCAL_MULTIPLIER_ENGINE=mc            -> reliable stratified-MC multipliers (SIM_METHOD=MC)
    # This axis selects ONLY the multiplier engine — both engines share EVERYTHING above (every
    # bug-fix, stratified-MC welfare, aMax=1300, the TM-ergodic MC seed); 'mc' is a clean same-model
    # TM-vs-MC cross-check. It is NOT a "world": reserve legacy/as-corrected for the WORLD axis.
    # exact-QE is NOT a runtime mode (frozen tag v2026-01-09-18-17 with matched buggy calibration).
    # HAFISCAL_MODE is a DEPRECATED alias kept for one cycle: default->tm, legacy->mc.
    # See IMPROVEMENTS_private/HAFiscal_IMPROVEMENT-001_legacy_default_mode_taxonomy.md.
    _engine = os.environ.get('HAFISCAL_MULTIPLIER_ENGINE', '').strip().lower()
    _legacy_mode = os.environ.get('HAFISCAL_MODE', '').strip().lower()
    if not _engine and _legacy_mode:
        if _legacy_mode not in ('default', 'legacy'):
            raise ValueError(
                f"HAFISCAL_MODE={_legacy_mode!r} invalid (deprecated alias; expected 'default' "
                "or 'legacy'). Prefer HAFISCAL_MULTIPLIER_ENGINE=tm|mc.")
        _engine = 'mc' if _legacy_mode == 'legacy' else 'tm'
        import warnings as _warnings
        _warnings.warn(
            "HAFISCAL_MODE is deprecated (owner ruling 2026-06-13, Q3): its 'legacy' value collided "
            "with the as-corrected WORLD. Use HAFISCAL_MULTIPLIER_ENGINE=tm|mc "
            f"(mapped HAFISCAL_MODE={_legacy_mode!r} -> HAFISCAL_MULTIPLIER_ENGINE={_engine!r}).",
            DeprecationWarning, stacklevel=2)
    if not _engine:
        _engine = 'tm'
    if _engine not in ('tm', 'mc'):
        raise ValueError(
            f"HAFISCAL_MULTIPLIER_ENGINE={_engine!r} invalid; expected 'tm' or 'mc'. "
            "exact-QE is the frozen tag v2026-01-09-18-17, not a runtime mode.")
    if _engine == 'mc':
        # mc engine: reliable stratified-MC multipliers (and welfare). Only the multiplier engine
        # changes vs tm; the model, bug-fixes, aMax, and TM-ergodic seed are identical.
        os.environ.setdefault('HAFISCAL_SIM_METHOD', 'MC')

# Splurge target file: resolve from this module so imports work regardless of process cwd (e.g. pytest from repo root).
_SPLURGE_RESULT = _resolve_path(str(_ha_root / "Target_AggMPCX_LiquWealth" / "Result_AllTarget.txt"))

# MC determinism test mode: reduce agent count for fast single-threaded comparison
# Activated by HAFISCAL_MC_DETERMINISM_TEST=1 env var or --mc-test CLI flag
_MC_DETERMINISM_TEST = (os.environ.get('HAFISCAL_MC_DETERMINISM_TEST', '') == '1'
                        or '--mc-test' in sys.argv)

# Targets in the estimation of the discount factor distributions for each 
# education level. 
# From SCF 2004: [20,40,60,80]-percentiles of the Lorenz curve for liquid wealth
data_LorenzPts_d = np.array([0, 0.01, 0.60, 3.58])    # \
data_LorenzPts_h = np.array([0.06, 0.63, 2.98, 11.6]) # -> units: % 
data_LorenzPts_c = np.array([0.15, 0.92, 3.27, 10.3]) # /
data_LorenzPts = [data_LorenzPts_d, data_LorenzPts_h, data_LorenzPts_c]
data_LorenzPtsAll = np.array([0.03, 0.35, 1.84, 7.42])
# From SCF 2004: Average liquid wealth to permanent income ratio 
data_avgLWPI = np.array([15.7, 47.7, 111])*4 # weighted average of fractions in percent
# From SCF 2004: Total LW over total PI by education group
data_LWoPI = np.array([28.1, 59.6, 162])*4 # units: %
# From SCF 2004: Weighted median of liquid wealth to permanent income ratio
data_medianLWPI = np.array([1.16, 7.55, 28.2])*4 # weighted median of fractions in percent

# Population share of each type
data_EducShares = [0.093, 0.527, 0.38] # Proportion of dropouts, HS grads, college types, SCF 2004 
# Wealth share of each type 
data_WealthShares = np.array([0.008, 0.179, 0.812])*100 # Percentage of total wealth of dropouts, HS grads, college types, SCF 2004 

# Parameters concerning the distribution of discount factors
# Initial values for estimation, taken from pandemic paperCondMrkvArrays_base
# Note: only using these values for initialization, they are overwritten by estimation 
num_types = 3
DiscFacMeanD = 0.9647   # Mean intertemporal discount factor for dropout types
DiscFacMeanH = 0.98051  # Mean intertemporal discount factor for high school types
DiscFacMeanC = 0.99160  # Mean intertemporal discount factor for college types

DiscFacInit = [DiscFacMeanD, DiscFacMeanH, DiscFacMeanC]
DiscFacSpreadD = 0.025
DiscFacSpreadH = 0.01676
DiscFacSpreadC = 0.00480  # Half-width of uniform distribution of discount factors

# Define the distribution of the discount factor for each eduation level
DiscFacCount = 7
DiscFacDstnD = Uniform(DiscFacMeanD-DiscFacSpreadD, DiscFacMeanD+DiscFacSpreadD)._approx_equiprobable(DiscFacCount)
DiscFacDstnH = Uniform(DiscFacMeanH-DiscFacSpreadH, DiscFacMeanH+DiscFacSpreadH)._approx_equiprobable(DiscFacCount)
DiscFacDstnC = Uniform(DiscFacMeanC-DiscFacSpreadC, DiscFacMeanC+DiscFacSpreadC)._approx_equiprobable(DiscFacCount)
DiscFacDstns = [DiscFacDstnD, DiscFacDstnH, DiscFacDstnC]

# Parameters concerning Markov transition matrix
#https://www.statista.com/statistics/232942/unemployment-rate-by-level-of-education-in-the-us/
# HAFISCAL_URATE_NORMAL_{D,H,C} env-var overrides for shuffle-friendliness
# diagnostics; see plans/20260504-1700h_phase_F_mfmc_tm_a_control_variate.md
# Phase H-0 and memory project_shuffle_friendly_recalibration.
Urate_normal_d = float(os.environ.get('HAFISCAL_URATE_NORMAL_D', 0.085))
Urate_normal_h = float(os.environ.get('HAFISCAL_URATE_NORMAL_H', 0.044))
Urate_normal_c = float(os.environ.get('HAFISCAL_URATE_NORMAL_C', 0.027))
if any(k in os.environ for k in ('HAFISCAL_URATE_NORMAL_D','HAFISCAL_URATE_NORMAL_H','HAFISCAL_URATE_NORMAL_C')):
    print(f'[urate-override] Urate_normal_d={Urate_normal_d}  Urate_normal_h={Urate_normal_h}  Urate_normal_c={Urate_normal_c}')

Uspell_normal = 1.5          # Average duration of unemployment spell in normal times, in quarters
UBspell_normal = 2           # Average duration of unemployment benefits in normal times, in quarters

# Basic model parameters: CRRA, growth factors, unemployment parameters (for normal times)
CRRA = 2.0                 # Coefficient of relative risk aversion (1, 2 or 3)

with open(_SPLURGE_RESULT, "r", encoding="utf-8") as f:
    dictload = eval(f.read())
Splurge = dictload['splurge'] 
if len(sys.argv) >= 6:
    # Number of arguments indicates that Splurge is set manually 
    Splurge = float(sys.argv[5])

# MC determinism test: override Splurge with a fixed value common to both versions
if _MC_DETERMINISM_TEST:
    # Use the 0.14.1 splurge value as canonical so both versions start identically
    _MC_SPLURGE = float(os.environ.get('HAFISCAL_MC_SPLURGE', '0.2461138828477288'))
    print(f'[MC DETERMINISM TEST] Splurge overridden: {Splurge} -> {_MC_SPLURGE}')
    Splurge = _MC_SPLURGE

# elif len(sys.argv) >= 3:
#     # Number of arguments indicates that CRRA is set manually
#     CRRA = float(sys.argv[2])
#     if (CRRA != 1.0 and CRRA != 2.0 and CRRA != 3.0):
#         print('The Splurge was only estimated for CRRA = 1.0, 2.0 and 3.0')
#     # Read in estimated Splurge --> depends on CRRA: 
#     f = open('../Target_AggMPCX_LiquWealth/Result_CRRA_'+str(CRRA)+'.txt', 'r')
#     dictload = eval(f.read())
#     Splurge = dictload['splurge'] 
    
PopGroFac = 1.0         #1.01**0.25  # Population growth factor
# PermGroFacAgg: aggregate productivity / technological growth factor.
# Set to 1.0 (no aggregate growth) per the QE-era model setup.
# This is the BUG-038 restoration of the QE-era spec; BUG-037's setting
# of PermGroFacAgg = G_pop_avg ≈ 1.00455 was reverted (it was an internally
# consistent model-spec change, not a bug fix; the heavy-tail issue it tried
# to address is fixed at the source by the T_age cap restoration — see
# math doc §25 and `plans/20260430-1807h_qtwisted-capped-cohort-age.md`).
PermGroFacAgg = 1.0     # QE-era setup; aggregate productivity stays constant
IncUnemp = 0.7              # Unemployment benefits replacement rate (proportion of permanent income)
IncUnempNoBenefits = 0.5   # Unemployment income when benefits run out (proportion of permanent income)
if len(sys.argv) >= 5:
    IncUnemp = float(sys.argv[3])
    IncUnempNoBenefits = float(sys.argv[4])

# -----------------------------------------------------------------------
# Parameters concerning the initial distribution of permanent income
# -----------------------------------------------------------------------
#
# Newborns of group g are drawn from group-specific Lognormal(pLogInitMean_g,
# pLogInitStd_g), calibrated to SCF 2004 quarterly earnings at age 25 by
# education category. These cross-group differentials are an intentional
# calibration target — they encode the SCF earnings premiums by education
# group, which downstream model behavior is calibrated to match.
#
# BUG-038 (2026-04-30) restored this group-specific spec from the BUG-037
# misdiagnosis, which had replaced per-group `pLogInitMean_g` with a common
# `pLogInitMean_avg`. Per user review, that change was an overreach (it
# imposed a "literature-standard" perpetual-youth convention not appropriate
# to HAFiscal's SCF-calibrated heterogeneity). See
# `plans/20260430-1807h_qtwisted-capped-cohort-age.md` §3 for the revert
# rationale.
# -----------------------------------------------------------------------
pLogInitMean_d = np.log(6.2)   # SCF: avg quarterly permanent income at age 25, HS dropout ($1000)
pLogInitMean_h = np.log(11.1)  # SCF: avg quarterly permanent income at age 25, HS graduate ($1000)
pLogInitMean_c = np.log(14.5)  # SCF: avg quarterly permanent income at age 25, college ($1000)
pLogInitStd_d  = 0.32          # SCF: σ of initial log permanent income, HS dropout
pLogInitStd_h  = 0.42          # SCF: σ of initial log permanent income, HS graduate
pLogInitStd_c  = 0.53          # SCF: σ of initial log permanent income, college

# Parameters concerning grid sizes: assets, permanent income shocks, transitory income shocks
aXtraMin = 0.001        # Lowest non-zero end-of-period assets above minimum gridpoint
aXtraMax = 40           # Highest non-zero end-of-period assets above minimum gridpoint
aXtraCount = int(os.environ.get('HAFISCAL_AXTRA_COUNT', 48))         # Base number of end-of-period assets above minimum gridpoints
if 'HAFISCAL_AXTRA_COUNT' in os.environ:
    print(f'[axtra-override] HAFISCAL_AXTRA_COUNT → aXtraCount={aXtraCount}')
aXtraExtra = [0.002,0.003] # Additional gridpoints to "force" into the grid
aXtraNestFac = 3        # Exponential nesting factor for aXtraGrid (how dense is grid near zero)
PermShkCount = 7        # Number of points in equiprobable discrete approximation to permanent shock distribution
TranShkCount = 7        # Number of points in equiprobable discrete approximation to transitory shock distribution


# Size of simulations
AgentCountTotal = 50000 # Total simulated population
T_sim = 80              # Number of quarters to simulate in counterfactuals

if _MC_DETERMINISM_TEST:
    AgentCountTotal = 500  # Reduced for determinism test (fast, ~1-2 min per evaluation)
    print(f'[MC DETERMINISM TEST] AgentCountTotal reduced to {AgentCountTotal}')

# Basic lifecycle length parameters (don't touch these)
T_cycle = 1

# Define grid of aggregate assets to labor
CgridBase = np.array([0.8, 1.0, 1.2])

# BUG-043 fix: extend the micro state space to encode "quarter of unemployment"
# explicitly so UI extension can be implemented as a payout-based policy
# rather than a freeze-window mechanism.
#
# HAFISCAL_UI_STATE_ENCODING:
#   'legacy':            4 micro states {e, u1Q, u2Q, noBen}.
#                        UI extension implemented via transition_ub=False
#                        freeze over a fixed macro-state window. Under-delivers
#                        by 1Q for Case 1 agents (BUG-043). Bit-identical to
#                        the published code; use only when reproducing
#                        pre-2026-05-16 numbers.
#   'bug_fix' (default): 6 micro states {e, u1Q, u2Q, u3Q, u4Q, noBen}.
#                        UI extension implemented via macro-state-conditional
#                        income at u3Q/u4Q (= 0.7 when recession + recessionUI
#                        scenario; 0.5 otherwise). Fixes BUG-043; matches paper
#                        Model.tex line 167-168 ("up to four quarters").
#                        Side benefit: enables shuffle CRN for UI welfare cells.
#                        Cutover 2026-05-16 (see
#                        conclusions_private/2026-05-16_canonical_config_recommendation.md).
# See plans/20260511_BUG-043_fix_state_expansion_plan.md
HAFISCAL_UI_STATE_ENCODING = os.environ.get('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')
assert HAFISCAL_UI_STATE_ENCODING in ('legacy', 'bug_fix'), \
    f"HAFISCAL_UI_STATE_ENCODING must be 'legacy' or 'bug_fix', got {HAFISCAL_UI_STATE_ENCODING!r}"

# Policy_ExtraBenefitQuarters: how many EXTRA quarters of UI benefits the
# extension policy provides on top of UBspell_normal. Per paper Model.tex
# line 167 ("extended from two quarters to four quarters"): 2 extra.
Policy_ExtraBenefitQuarters = 2

if HAFISCAL_UI_STATE_ENCODING == 'bug_fix':
    # Expanded state space: encode each quarter of unemployment as its own
    # micro state up to UBspell_normal + Policy_ExtraBenefitQuarters.
    # E.g., with UBspell_normal=2 and Policy_ExtraBenefitQuarters=2: 4 benefit-
    # eligible states (u1Q, u2Q, u3Q, u4Q) + employed + noBen = 6 micro states.
    num_base_MrkvStates = 2 + UBspell_normal + Policy_ExtraBenefitQuarters
else:
    # Legacy 4-state encoding: 2 benefit-eligible states + employed + noBen.
    num_base_MrkvStates = 2 + UBspell_normal

# Inform user of encoding choice (cheap, helpful for log reading)
if HAFISCAL_UI_STATE_ENCODING == 'bug_fix':
    print(f'[BUG-043 fix] HAFISCAL_UI_STATE_ENCODING=bug_fix → '
          f'num_base_MrkvStates={num_base_MrkvStates} '
          f'(legacy would be {2 + UBspell_normal})')

num_experiment_periods = 20

def small_MrkvArray(e,u,ub,transition_ub=True):
    small_MrkvArray = np.zeros((ub+2, ub+2))
    small_MrkvArray[0,0] = e
    small_MrkvArray[0,1] = 1-e
    for i in np.array(range(ub))+1:
        if transition_ub:
            small_MrkvArray[i,i+1] = u
        else:
            small_MrkvArray[i,i] = u
        small_MrkvArray[i,0] = 1-u
    small_MrkvArray[ub+1,ub+1] = u
    small_MrkvArray[ub+1,0] = 1-u
    return small_MrkvArray 

def make_cond_mrkv_arrays_base(Urate_normal, Uspell_normal, UBspell_normal):
    U_persist_normal = 1.-1./Uspell_normal
    E_persist_normal = 1.-Urate_normal*(1.-U_persist_normal)/(1.-Urate_normal)
    MrkvArray_normal         = small_MrkvArray(E_persist_normal,    U_persist_normal,    UBspell_normal)
    CondMrkvArrays = [MrkvArray_normal]
    return CondMrkvArrays

def make_full_mrkv_array(MacroMrkvArray, CondMrkvArrays):
    for i in range(MacroMrkvArray.shape[0]):
        this_row = MacroMrkvArray[i,0]*CondMrkvArrays[0]
        for j in range(MacroMrkvArray.shape[0]-1):
            this_row = np.concatenate((this_row, MacroMrkvArray[i,j+1]*CondMrkvArrays[j+1]),axis=1)
        if i==0:
            FullMrkv = this_row
        else:
            FullMrkv = np.concatenate((FullMrkv, this_row), axis=0)
    return [FullMrkv]

MacroMrkvArray_base = np.array([[1.0]])
CondMrkvArrays_base_d = make_cond_mrkv_arrays_base(Urate_normal_d, Uspell_normal, UBspell_normal)
MrkvArray_base_d = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_d)
CondMrkvArrays_base_h = make_cond_mrkv_arrays_base(Urate_normal_h, Uspell_normal, UBspell_normal)
MrkvArray_base_h = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_h)
CondMrkvArrays_base_c = make_cond_mrkv_arrays_base(Urate_normal_c, Uspell_normal, UBspell_normal)
MrkvArray_base_c = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_c)

# Define permanent income growth rates
PermGroFac_base =   [1.0]
PermGroFac_base_d = [1.0 + 0.01421/4]  # From Pandemic paper: avg growth rates during
PermGroFac_base_h = [1.0 + 0.01812/4]  # working life for each education group
PermGroFac_base_c = [1.0 + 0.01958/4]

# BUG-038 (2026-04-30): PermGroFacAgg stays at 1.0 per the QE-era setup
# (assigned at line ~99 above). The BUG-037 override that set it to
# G_pop_avg ≈ 1.00455 was reverted because (a) per user review, the
# heavy-tail issue it tried to address is more cleanly fixed by the
# T_age cap restoration in BUG-038, and (b) PermGroFacAgg = 1 is the
# QE paper's setup — minimum disruption from that baseline.
# See `plans/20260430-1807h_qtwisted-capped-cohort-age.md` §3 and
# `BUGS_private/HAFiscal_BUG-038_T_age_cap_removal.md`.

# SST (income process): see income_process_sst.py and history/20260403-sst-permgrofac-income-process-plan.md
from income_process_sst import build_PermGroFac_micro

# --- Unemployment income process flags (SST) ---
# Paper default: unemployed agents have no pLvl growth (PermGroFac_unemp=1),
# no stochastic permanent shocks, and no stochastic transitory shocks.
# Income during unemployment is deterministic: pLvl * IncUnemp.
#
# Rationale for turning off shocks: with ~4.4% unemployment, only ~44 out of
# 1000 agents are unemployed.  Stochastic draws for 44 agents produce sampling
# noise that overwhelms the small signal from their income differences.
# Deterministic unemployment income eliminates this noise source.
#
# For debugging: set unemp_pLvl_grows_like_employed=True to give unemployed
# agents the same PermGroFac as employed (but still no stochastic shocks).
# When True, PermGroFac_unemp is set to the employed rate per education group
# in the build_PermGroFac_micro calls below.
# HAFISCAL_PLVL_GROWS_DURING_UNEMP (default 'off') controls whether unemployed
# agents accumulate the productivity-growth factor G during unemployment spells.
#   'off' (default, QE-published convention): unemployed agents have pLvl FROZEN
#         (no G, no ψ shock under perm_shocks_during_unemp=False). MC and TM-a
#         agree at this convention. Matches what the published QE numbers
#         actually compute.
#   'on'  (Harmenberg-factorizable convention): unemployed agents grow at G
#         (still ψ=1 under perm_shocks=False). Required for pLvl ⊥ state, the
#         Harmenberg analytical factorization that allows TM-a to use the
#         analytical p formula. MC and TM-a both apply G uniformly.
#
# Both conventions are internally consistent. The MC-vs-TM-a residual
# diagnosed 2026-05-05 was caused by the two methods silently using
# DIFFERENT conventions: MC was 'off' (PermShk=1.0 for unemp drops G), TM-a
# was 'on' (PermGroFac uniform across states). This env var unifies both.
_pgu_env = os.environ.get('HAFISCAL_PLVL_GROWS_DURING_UNEMP', 'off').strip().lower()
unemp_pLvl_grows_like_employed = _pgu_env in ('on', '1', 'true', 'yes')
PermGroFac_unemp = 1.0  # Used when unemp_pLvl_grows_like_employed is False
if 'HAFISCAL_PLVL_GROWS_DURING_UNEMP' in os.environ:
    print(f'[plvl-grows-during-unemp] HAFISCAL_PLVL_GROWS_DURING_UNEMP={_pgu_env!r} '
          f'→ unemp_pLvl_grows_like_employed = {unemp_pLvl_grows_like_employed}')
# perm_shocks_during_unemployment: profile-dependent. Set explicitly by reproduce.sh
# profiles via HAFISCAL_PERM_DURING_UNEMP={on,off}. Default ON (Harmenberg-style:
# unemployed agents draw the same PermShk as employed, enabling pLvl ⊥ state
# factorization). The qe_fidelity profile sets OFF to match the published
# HAFiscal-QE assumption (PermShk=1 while unemployed).
_psdu_env = os.environ.get('HAFISCAL_PERM_DURING_UNEMP', '').strip().lower()
if _psdu_env in ('on', '1', 'true', 'yes'):
    perm_shocks_during_unemployment = True
elif _psdu_env in ('off', '0', 'false', 'no'):
    perm_shocks_during_unemployment = False
elif _psdu_env == '':
    perm_shocks_during_unemployment = True   # silent default = Harmenberg-style
else:
    raise ValueError(
        f"HAFISCAL_PERM_DURING_UNEMP={_psdu_env!r} is not a recognized value. "
        f"Use 'on'/'off' (or 1/0, true/false, yes/no)."
    )
tran_shocks_during_unemployment = False  # Paper: no stochastic TranShk while unemployed

# # Define the permanent and transitory shocks 
# TranShkStd = [0.1]
# PermShkStd = [0.05]
# Variances from Sticky expectations paper: 
TranShkStd = [np.sqrt(0.12)]
PermShkStd = [np.sqrt(0.003)]

Rfree_base = [1.01]             #Baseline
if len(sys.argv) >= 2:
    Rfree_base = [float(sys.argv[1])]
LivPrb_base = [1.0-1/160.0]     # 40 years (160 quarters) working life 

# Calculate max beta values for each education group where GIC holds with equality.
#
# Imposes the Risk-Modified Growth Impatience Condition with mortality
# (GIC-Mod-with-Liv) from Carroll's BufferStockTheory paper:
#
#     L · Þ · E[1/ψ] / Γ < 1   where Þ = (Rβ)^(1/ρ)
#
# Solving for β:  β_max = (Γ / (L · E[1/ψ]))^ρ / R
#
# Γ is the **agent's per-period perceived deterministic growth of pLvl**,
# which equals the cohort-specific labor-income growth `PermGroFac_base_g`
# (NOT multiplied by `PermGroFacAgg`). PermGroFacAgg is an aggregate-
# bookkeeping factor that affects the LEVEL at which newborns enter
# (`pLvl_init = Lognormal(... + log(PlvlAgg^t), ...)`) but does NOT enter
# survivors' per-period pLvl evolution: `pLvl_{t+1} = G_g · ψ · pLvl_t`.
# Therefore the agent's normalized-asset chain (aNrm = a/p) depends on G_g
# alone, and the GIC formula must use Γ = G_g.
#
# (An earlier version of this formula multiplied G_g by PermGroFacAgg —
# silently a no-op while PermGroFacAgg = 1, but became spuriously
# loosening when PermGroFacAgg was set to G_pop_avg ≈ 1.005 per BUG-037.
# Corrected here to use G_g alone; see BUG-037 §1.7 for the agent-side
# derivation.)
#
# For lognormal ψ with E[ψ]=1 and var(log ψ)=σ²:  E[1/ψ] = exp(σ²).
#
# ---------------------------------------------------------------------------
# WHICH GIC IS THIS, AND WHY `L` IS *OUTSIDE* THE 1/ρ POWER (read before editing)
# ---------------------------------------------------------------------------
# Carroll's BufferStockTheory ("BST"; econ2.jhu.edu/people/ccarroll/papers/
# BufferStockTheory, or llorracc.github.io/BufferStockTheory) defines:
#   - Absolute Patience Factor (APF)        Þ   = (Rβ)^(1/ρ)               (BST eq. 15)
#   - Growth Patience Factor (GPF)          Þ_Γ = Þ/Γ                      (BST eq. 29)
#   - Risk-modified GIC ("Strong GI"/GIC-Mod):  Þ_Γ · E[ψ⁻¹] < 1           (BST Assumption S.2)
#   - Mortality (no-annuity / accidental-bequest) modified GIC:  L · Þ_Γ < 1 (BST eq. 42)
#
# Combining the last two gives the condition we impose here, with `L` (=LivPrb)
# **OUTSIDE** the 1/ρ power:
#
#       GPF_out  =  (Rβ)^(1/ρ) · L · E[ψ⁻¹] / Γ  <  1                       [THIS FILE]
#
# This is NOT the only mortality-modified GPF, and the distinction is load-
# bearing — DO NOT "fix" `L` to sit inside the power without reading the rest of
# this comment (it has been mistaken for a bug). There are two genuinely
# different objects, because `LivPrb` plays two different roles:
#
#   GPF_out  = (Rβ)^(1/ρ)·L·E[ψ⁻¹]/Γ      (L OUTSIDE, exponent L¹)  -- BST eq. 42
#       `L` here is a *population-survival* / cohort-shrinkage factor. GPF_out < 1
#       is the condition for the **cross-sectional** distribution of normalized
#       assets in a population WITH MORTALITY + BIRTH to be stationary. It
#       coincides with the Blanchard-annuity form (where R̄=R/L, β̄=βL cancel the
#       inside-L; BST eq. 41).
#
#   GPF_in   = (R·β·L)^(1/ρ)·E[ψ⁻¹]/Γ      (L INSIDE, exponent L^{1/ρ})
#       `L` here is *discounting*: with no annuity the Euler equation discounts
#       at DiscFacEff = β·L (mortality ≡ extra discounting), so the individual's
#       MPCmin = 1 − (R·β·L)^{1/ρ}/R and the asymptotic slope of the expected-
#       wealth map is GPF_in. A finite **individual buffer-stock target**
#       `mNrmTrg` exists iff GPF_in < 1. This is HARK's
#       `calc_patience_factor(R, β·L, ρ)` convention.
#
# Since L < 1 and ρ > 1, L^{1/ρ} > L¹, hence **GPF_in > GPF_out**. We deliberately
# shave on GPF_out (the looser, population condition), NOT GPF_in, for two reasons:
#
#  (1) GPF_out < 1 is EXACTLY the existence condition for the transition-matrix
#      (TM) ergodic distribution. The TM kernel (see
#      `tm_methods._build_period_tm_a`) is column-stochastic and INCLUDES the
#      death→newborn reset `+ (1 − L_eff(j))·NewBornDist`; that reset regularizes
#      the chain so its stationary eigenvector exists iff the population can't
#      out-accumulate mortality, i.e. iff GPF_out < 1. MC and TM both reset on
#      death and compute the same cross-section. So this shave keeps the TM method
#      well-posed. (If GPF_out ≥ 1 — e.g. shave disabled — no stationary
#      distribution exists, the eigenvector solve piles mass at aMax, and only
#      finite-horizon MC is meaningful.)
#
#  (2) The most-patient (cap) atom is intentionally placed at GPF_out = theGICfactor
#      ≈ 1 to fit the top of the wealth distribution (cstwMPC-style; see
#      theGICfactor note below). At theGICfactor = 0.9995 and L = 1−1/160 the
#      College cap atom therefore has GPF_out = 0.9995 < 1 but
#      GPF_in = 0.9995/√L ≈ 1.0026 > 1: it satisfies the population condition but
#      VIOLATES the individual one — it has NO finite individual target and its
#      agents accumulate until death. This is BY DESIGN, not a bug: the population
#      cross-section (what the moments use) is still stationary, and that near-edge
#      top atom is what matches College wealth concentration. A converged consumption
#      policy with no drift-zero `mNrmTrg` is NOT an iteration artifact — policy
#      convergence needs only RIC/FVAC (return impatience / finite value of autarky),
#      which still hold while the target is infinite.
#
#      Practical consequence: when GPF_in > 1 the (finite) ergodic wealth tail is
#      FAT (cut off only by mortality), which forces a tall `aMax` — the GIC-edge
#      atom is the binding case for the asset grid top (the (1−1e-4) ergodic aNrm
#      quantile ≈ 1224 → aMax = 1300; see `adaptive_grid_tm.production_aMax`).
#
# Full write-up:
#   conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md
# Whether to ever tighten the shave to GPF_in (the individual condition,
# (Γ/E[ψ⁻¹])^ρ/(R·L)) is an OPEN methodology decision recorded there — it would
# lower the College cap-β by ~√L ≈ 0.3% and require a full re-estimate.
# ---------------------------------------------------------------------------
#
# Replaces an earlier ad-hoc formula (1-L) + Γ^ρ/R which combined
# mortality and the regular GICRaw additively without coupling to shock
# variance and ignored aggregate productivity growth.
Ex_inv_PermShk = np.exp(PermShkStd[0]**2)  # E[1/ψ] for lognormal with E[ψ]=1
_GICMod_denom = LivPrb_base[0] * Ex_inv_PermShk
GICmaxBetas = np.array([
    (PermGroFac_base_d[0] / _GICMod_denom)**CRRA / Rfree_base[0],
    (PermGroFac_base_h[0] / _GICMod_denom)**CRRA / Rfree_base[0],
    (PermGroFac_base_c[0] / _GICMod_denom)**CRRA / Rfree_base[0],
])
# GIC margin: the most-patient (cap) atom's Growth Patience Factor ceiling. Imposed on the GPF
# (BUG-053), so gic_capped_beta(e, theGICfactor) = GICmaxBetas[e]*theGICfactor**CRRA puts the cap
# atom at GPF = theGICfactor. Set to 0.9995 (2026-06-09): the BUG-053 fix correctly moved the cap
# from beta-shave to GPF-shave, but at GPF=0.999 the cap is LOAD-BEARING for College (its
# wealth-concentration fit needs a near-GIC-boundary most-patient atom) — College TM-a distance
# ~5.75 at GPF=0.999 vs ~4.3 at GPF=0.9995. GPF=0.9995 (cap beta = GICmax*0.9995**2 = 1.005375 for
# College) restores the good fit AND coincides with the cap the old beta-shave bug effectively
# produced (GICmax*0.999 = 1.005369, GPF 0.99949), so multipliers stay ~unchanged vs the published
# world while the mechanism is now correct. theGICfactor is the GIC margin choice, not a bug knob.
theGICfactor = 0.9995
minBeta = 0.01

def gic_capped_beta(educ_type, shave):
    """Maximum discount factor (beta) for an education group, capped so the most-patient
    atom's GROWTH PATIENCE FACTOR (GPF) does not exceed `shave`.

    WHAT WE IMPOSE, AND WHY (BUG-053)
    ---------------------------------
    The object that must stay below 1 for a stationary wealth-to-permanent-income ratio is
    the GPF (the Growth Impatience Condition: GPF < 1), NOT beta itself. So the calibration
    ceiling belongs on the GPF: we want the most-patient atom to sit at GPF = `shave`
    (e.g. 0.999) -- a hair inside the growth-impatience boundary GPF = 1.

    `GICmaxBetas[educ_type]` is the beta at which GPF = 1 exactly (the GIC-Mod-with-Liv cap,
    (Gamma / (L * E[1/psi]))**CRRA / R). NOTE this `GPF` is the *population* GPF_out (LivPrb
    OUTSIDE the 1/CRRA power; BST eq. 42) — the existence condition for the TM ergodic
    distribution — NOT the *individual* target condition GPF_in (LivPrb inside). The cap atom
    can satisfy GPF_out < 1 while violating GPF_in > 1 (no individual `mNrmTrg`), by design.
    See the big "WHICH GIC IS THIS" comment above `GICmaxBetas` and
    conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md.
    Since GPF is proportional to beta**(1/CRRA), the beta whose GPF equals `shave` is

        beta_cap = GICmaxBetas[educ_type] * shave**CRRA          # GPF(beta_cap) == shave

    THE FIX (default): exponent CRRA -> `shave` is a ceiling on the GPF. With shave=0.999,
    CRRA=2 the cap atom lands at GPF = 0.999, beta ~= GICmax*0.998.

    THE BUG IT REPLACES: the old code multiplied the cap by `shave` directly
    (GICmaxBetas * shave -- a ceiling on BETA), which yields GPF = shave**(1/CRRA) -- e.g.
    0.999 -> 0.9995. That left the most-patient atom *closer* to the GIC boundary than the
    nominal 0.999, with a correspondingly fatter ergodic wealth tail, slower consumption
    solve, and wider asset grid.

    PAPER TRAIL: HAFISCAL_GIC_SHAVE_ON_GPF defaults to '1' (GPF-shave, the fix). Set it to
    '0' to reproduce the old beta-shave behavior (GPF = shave**(1/CRRA)) for the
    QE-divergence ledger / before-after comparison. Changing the cap moves the calibration,
    so the (beta, nabla) atoms should be RE-ESTIMATED under the fix (gated; see BUG-053).
    """
    import os as _os
    # exponent CRRA  -> `shave` is a ceiling on the GPF (the fix);
    # exponent 1.0   -> `shave` is a ceiling on beta (the BUG-053 behavior, reproducible).
    _exp = CRRA if _os.environ.get('HAFISCAL_GIC_SHAVE_ON_GPF', '1') != '0' else 1.0
    return GICmaxBetas[educ_type] * shave ** _exp

for e in range(num_types):
    for thedf in range(DiscFacCount):
        if DiscFacDstns[e].atoms[0][thedf] > gic_capped_beta(e, theGICfactor):
            DiscFacDstns[e].atoms[0][thedf] = gic_capped_beta(e, theGICfactor)
        elif DiscFacDstns[e].atoms[0][thedf] < minBeta:
            DiscFacDstns[e].atoms[0][thedf] = minBeta

# find intial distribution of states for each education type
vals_d, vecs_d = np.linalg.eig(np.transpose(MrkvArray_base_d[0])) 
vals_d = vals_d.real
vecs_d = vecs_d.real
dist_d = np.abs(np.abs(vals_d) - 1.)
idx_d = np.argmin(dist_d)
init_mrkv_dist_d = vecs_d[:,idx_d].astype(float)/np.sum(vecs_d[:,idx_d].astype(float))

vals_h, vecs_h = np.linalg.eig(np.transpose(MrkvArray_base_h[0])) 
dist_h = np.abs(np.abs(vals_h) - 1.)
idx_h = np.argmin(dist_h)
# Use np.real() to extract real part, avoiding ComplexWarning for negligible imaginary components
init_mrkv_dist_h = np.real(vecs_h[:,idx_h])/np.sum(np.real(vecs_h[:,idx_h]))

vals_c, vecs_c = np.linalg.eig(np.transpose(MrkvArray_base_c[0])) 
dist_c = np.abs(np.abs(vals_c) - 1.)
idx_c = np.argmin(dist_c)
# Use np.real() to extract real part, avoiding ComplexWarning for negligible imaginary components
init_mrkv_dist_c = np.real(vecs_c[:,idx_c])/np.sum(np.real(vecs_c[:,idx_c]))

# Define a parameter dictionary for dropout type
init_dropout = {"cycles": 0, # This will be overwritten at type construction
                "T_cycle": T_cycle,
                'T_sim': 400, #Simulate up to age 400
                'T_age': 200,  # BUG-038: QE-era cap restored (50 years). See math doc §25.
                'AgentCount': 10000,
                "PermGroFacAgg": PermGroFacAgg,
                "PopGroFac": PopGroFac,
                "CRRA": CRRA,
                "DiscFac": 0.98, # This will be overwritten at type construction
                "Rfree_base" : Rfree_base,
                "PermGroFac_base": PermGroFac_base_d,
                "LivPrb_base": LivPrb_base,
                "Rfree" : np.array(num_base_MrkvStates*Rfree_base),
                "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_d[0], num_base_MrkvStates, PermGroFac_base_d[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
                "LivPrb": [np.array(LivPrb_base*num_base_MrkvStates)],
                "MrkvArray_base" : MrkvArray_base_d, 
                "MacroMrkvArray_base" : MacroMrkvArray_base,
                "CondMrkvArrays_base" : CondMrkvArrays_base_d,
                "MrkvArray" : MrkvArray_base_d, 
                "MacroMrkvArray" : MacroMrkvArray_base,
                "CondMrkvArrays" : CondMrkvArrays_base_d,
                "BoroCnstArt": 0.0,
                "PermShkStd": PermShkStd,
                "PermShkCount": PermShkCount,
                "TranShkStd": TranShkStd,
                "TranShkCount": TranShkCount,
                "UnempPrb": 0.0, # Unemployment is modeled as a Markov state
                "IncUnemp": IncUnemp,
                "IncUnempNoBenefits": IncUnempNoBenefits,
                "aXtraMin": aXtraMin,
                "aXtraMax": aXtraMax,
                "aXtraCount": aXtraCount,
                "aXtraExtra": aXtraExtra,
                "aXtraNestFac": aXtraNestFac,
                "CubicBool": False,
                "vFuncBool": False,
                'kLogInitMean': np.log(0.00001), # Initial assets are zero
                'kLogInitStd': 0.0,
                'pLogInitMean': pLogInitMean_d,  # SCF: avg quarterly perm income at age 25 (per group)
                'pLogInitStd': pLogInitStd_d,       # σ_g kept group-specific (within-group dispersion)
                "MrkvPrbsInit" : np.array(list(init_mrkv_dist_d)),
                'Urate_normal' : Urate_normal_d,
                'Uspell_normal' : Uspell_normal,
                'UBspell_normal' : UBspell_normal,
                'num_base_MrkvStates' : num_base_MrkvStates,
                'PermGroFac_unemp': PermGroFac_unemp,
                'perm_shocks_during_unemployment': perm_shocks_during_unemployment,
                'tran_shocks_during_unemployment': tran_shocks_during_unemployment,
                'num_experiment_periods' : num_experiment_periods,
                'UpdatePrb' : 1.0,
                'Splurge' : Splurge,
                'track_vars' : [],
                'EducType': 0
                }

adj_highschool = {
    "PermGroFac_base": PermGroFac_base_h,
    "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_h[0], num_base_MrkvStates, PermGroFac_base_h[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
    "MrkvArray_base" : MrkvArray_base_h, 
    "CondMrkvArrays_base" : CondMrkvArrays_base_h,
    "MrkvArray" : MrkvArray_base_h, 
    "CondMrkvArrays" : CondMrkvArrays_base_h,
    'pLogInitMean': pLogInitMean_h,  # SCF: avg quarterly perm income at age 25 (per group)
    'pLogInitStd': pLogInitStd_h,       # σ_g kept group-specific
    "MrkvPrbsInit" : np.array(list(init_mrkv_dist_h)),
    'Urate_normal' : Urate_normal_h,
    'EducType' : 1}
init_highschool = init_dropout.copy()
init_highschool.update(adj_highschool)

adj_college = {
    "PermGroFac_base": PermGroFac_base_c,
    "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_c[0], num_base_MrkvStates, PermGroFac_base_c[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
    "MrkvArray_base" : MrkvArray_base_c, 
    "CondMrkvArrays_base" : CondMrkvArrays_base_c,
    "MrkvArray" : MrkvArray_base_c, 
    "CondMrkvArrays" : CondMrkvArrays_base_c,
    'pLogInitMean': pLogInitMean_c,  # SCF: avg quarterly perm income at age 25 (per group)
    'pLogInitStd': pLogInitStd_c,       # σ_g kept group-specific
    "MrkvPrbsInit" : np.array(list(init_mrkv_dist_c)),
    'Urate_normal' : Urate_normal_c,
    'EducType' : 2}
init_college = init_dropout.copy()
init_college.update(adj_college)

# ── Endogenous SOLVE-grid sizing (opt-in: HAFISCAL_ENDOGENOUS_GRID, default OFF) ──────────────
# The legacy solve grid is a single hand-set aXtraMax=40 / aXtraCount=48 (lines 284-285) shared by
# all three education groups (HS/College inherit them via init_dropout.copy()). Ample for the Step-2
# (beta) moments — median LW/PI + Lorenz sit at m≈6 ≪ 40 — but the cFunc's PF-asymptote (decay)
# extrapolation is then ~3% off in the wealth TAIL (matters only for tail-weighted quantities like
# K/Y, NOT for beta). The opt-in endogenous path sizes the solve grid PER GROUP to the decay reach of
# that group's most-patient (GIC-cap) atom, AND scales aXtraCount to hold the near-0 density constant:
#     aXtraMax_e   = ln(C1/bar) / MPCmin(gic_capped_beta(e))         # grid_sizing.solve_grid_aMax
#     aXtraCount_e = ceil(count · ln(aXtraMax_e/aMin)/ln(40/aMin))   # grid_sizing.solve_grid_count
# MPCmin keys off RETURN patience (the RIC), defined even when the growth/GIC-Mod conditions fail, so
# it is robust. Measured 2026-06-24 (C1≈0.04, bar=1%): Dropout 205/56, HS 240/57, College 256/57 (vs
# the legacy 40/48). The COUNT scaling is ESSENTIAL: extending aMax at a fixed count thins the moment
# region (37→33 gridpoints ≤ m=6) and shifts HS beta ~0.31% — the scaled count restores beta-neutrality
# (E4/E5 in the journal). Derivations validated in grid_sizing.py and
# prompts_local/2026-06-24_grid-sizing-experiments-journal.md. (The TM grid is sized separately by
# adaptive_grid_tm.production_aMax()=1300, the measured Pareto-tail quantile; grid_sizing.tm_grid_aMax
# is its analytic cross-check / GIC-Mod-failure fallback.)
# Precedence: explicit HAFISCAL_SOLVE_AMAX > endogenous (flag on) > legacy (default).
# DEFAULT (both env vars unset): the if-block is skipped, the per-group vars stay at the legacy
# aXtraMax/aXtraCount, the writes below are no-ops, and grid_sizing is never imported — byte-for-byte.
aXtraMax_d = aXtraMax_h = aXtraMax_c = aXtraMax
aXtraCount_d = aXtraCount_h = aXtraCount_c = aXtraCount
_solve_amax_override = os.environ.get('HAFISCAL_SOLVE_AMAX')
_endogenous_grid_on = os.environ.get('HAFISCAL_ENDOGENOUS_GRID', '0') not in ('0', '', 'false', 'False')
if (_solve_amax_override not in (None, '')) or _endogenous_grid_on:
    import sys as _sys_grid
    _HA_MODELS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Code/HA-Models
    if _HA_MODELS not in _sys_grid.path:
        _sys_grid.path.insert(0, _HA_MODELS)
    import grid_sizing as _gs
    _tm_cap = float(os.environ.get('HAFISCAL_TM_AMAX', '1300'))
    if _solve_amax_override not in (None, ''):
        aXtraMax_d = aXtraMax_h = aXtraMax_c = float(_solve_amax_override)
        _grid_why = f"HAFISCAL_SOLVE_AMAX={aXtraMax_d:g} (all groups)"
    else:
        _c1 = float(os.environ.get('HAFISCAL_GRID_C1', _gs.SOLVE_C1))
        _bar = float(os.environ.get('HAFISCAL_GRID_BAR', _gs.SOLVE_BAR))
        aXtraMax_d = _gs.solve_grid_aMax(Rfree_base[0], gic_capped_beta(0, theGICfactor), CRRA, LivPrb_base[0], PermGroFac=PermGroFac_base_d[0], C1=_c1, bar=_bar, tm_cap=_tm_cap)
        aXtraMax_h = _gs.solve_grid_aMax(Rfree_base[0], gic_capped_beta(1, theGICfactor), CRRA, LivPrb_base[0], PermGroFac=PermGroFac_base_h[0], C1=_c1, bar=_bar, tm_cap=_tm_cap)
        aXtraMax_c = _gs.solve_grid_aMax(Rfree_base[0], gic_capped_beta(2, theGICfactor), CRRA, LivPrb_base[0], PermGroFac=PermGroFac_base_c[0], C1=_c1, bar=_bar, tm_cap=_tm_cap)
        _grid_why = f"HAFISCAL_ENDOGENOUS_GRID=1 (C1={_c1:g} bar={_bar:g} tm_cap={_tm_cap:g})"
    # Hold near-0 grid density constant when aMax is extended (else beta shifts ~0.31%, E4/E5).
    # The existing HAFISCAL_AXTRA_COUNT (already folded into aXtraCount) is the legacy base scaled.
    aXtraCount_d = _gs.solve_grid_count(aXtraMax_d, aXtraMin=aXtraMin, legacy_aMax=aXtraMax, legacy_count=aXtraCount)
    aXtraCount_h = _gs.solve_grid_count(aXtraMax_h, aXtraMin=aXtraMin, legacy_aMax=aXtraMax, legacy_count=aXtraCount)
    aXtraCount_c = _gs.solve_grid_count(aXtraMax_c, aXtraMin=aXtraMin, legacy_aMax=aXtraMax, legacy_count=aXtraCount)
    print(f"[grid_sizing] {_grid_why} → per-group solve grids aXtraMax/aXtraCount: "
          f"Dropout={aXtraMax_d:.0f}/{aXtraCount_d} HS={aXtraMax_h:.0f}/{aXtraCount_h} College={aXtraMax_c:.0f}/{aXtraCount_c} "
          f"(legacy {aXtraMax}/{aXtraCount}; count scaled to hold near-0 density)")
init_dropout["aXtraMax"] = aXtraMax_d;   init_dropout["aXtraCount"] = aXtraCount_d
init_highschool["aXtraMax"] = aXtraMax_h; init_highschool["aXtraCount"] = aXtraCount_h
init_college["aXtraMax"] = aXtraMax_c;   init_college["aXtraCount"] = aXtraCount_c

# Define a dictionary to represent the baseline scenario
base_dict = {'shock_type' : "base",
             'UpdatePrb' : 1.0,
             'Splurge' : Splurge
             }

frictionless_changes = {
             'UpdatePrb' : 1.0
             }

# Parameters for AggregateDemandEconomy economy
intercept_prev = np.ones((num_base_MrkvStates,num_base_MrkvStates ))    # Intercept of aggregate savings function
slope_prev = np.zeros((num_base_MrkvStates,num_base_MrkvStates ))       # Slope of aggregate savings function
ADelasticity = 0.30   # Elasticity of productivity to consumption. SINGLE SOURCE OF TRUTH for the demand
# elasticity: Parameters.py's return_parameters imports THIS value (then applies the ADElas→0.5 override).
# Defined once here; do not re-literalize it elsewhere.

num_max_iterations_solvingAD = 30
convergence_tol_solvingAD = 1E-6
Cfunc_iter_stepsize       = 1

# Make a dictionary to specify a Cobb-Douglas economy
init_ADEconomy = {'intercept_prev': intercept_prev,
                     'slope_prev': slope_prev,
                     'ADelasticity' : 0.0,
                     'demand_ADelasticity' : ADelasticity,
                     'Cfunc_iter_stepsize' : Cfunc_iter_stepsize,
                     'MrkvArray' : MrkvArray_base_h,
                     'num_base_MrkvStates' : num_base_MrkvStates,
                'PermGroFac_unemp': PermGroFac_unemp,
                'perm_shocks_during_unemployment': perm_shocks_during_unemployment,
                'tran_shocks_during_unemployment': tran_shocks_during_unemployment,
                     "MrkvArray_base" : MrkvArray_base_h, 
                     'CgridBase' : CgridBase,
                     'EconomyMrkvNow_init': 0,
                     'act_T' : 400
                     }