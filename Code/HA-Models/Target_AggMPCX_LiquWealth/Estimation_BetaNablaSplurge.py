"""
Estimation_BetaNablaSplurge.py

This script estimates the beta (discount factor) distribution and splurge factor
to match Norwegian lottery winner consumption data from Fagereng et al.

DESIGN CHOICES:
---------------
**Single splurge common to all consumers.** This estimation imposes a single
varsigma applied identically to every consumer, regardless of education group
or within-group discount-factor type. An earlier exploration allowed
heterogeneous splurge (per education cohort, and as a within-cohort
distribution). The lottery-MPC moments from Fagereng et al. and the SCF
wealth-distribution moments did not provide evidence to reject the null of
a single varsigma. Imposing this restriction reduces the parameter
dimensionality of the joint optimization and tightens identification of
(beta-center, beta-spread). Step 2 (`EstimAggFiscalMAIN.py`) takes this
single varsigma as exogenously given and estimates per-cohort
(beta-center, beta-spread) only. See `Subfiles/Parameterization.tex`
section `sec:splurge` (and the footnote on the "all households have the
same propensity to splurge" assumption) for the corresponding paper-side
discussion of this choice.

HISTORICAL NOTE ON CONSUMER TYPE:
---------------------------------
This code uses KinkedRconsumerType (which allows different interest rates for
borrowing vs saving) rather than the simpler IndShockConsumerType.

History:
- March 2020: Original code by Edmund Crawley used IndShockConsumerType
- July 2020: Ivan Frankovic added "kinkyR functionality" as an experimental
  variation to explore how different borrowing vs saving rates affect results.
  The kinkyR version allowed borrowing (BoroCnstArt = -0.8) with a higher
  borrowing rate (Rboro ~20% annual) vs saving rate (Rsave ~2% annual).
- January 2024: BoroCnstArt was changed to 0, disabling borrowing. With
  BoroCnstArt = 0, agents cannot borrow, so Rboro is never used in practice.
  
Current state: KinkedRconsumerType is retained (rather than reverting to
IndShockConsumerType) to allow future robustness checks where researchers
can enable borrowing by setting BoroCnstArt < 0. To enable borrowing:
    base_params['BoroCnstArt'] = -0.8  # Allow borrowing up to 80% of income
    
With the current settings (BoroCnstArt = 0, Rsave = Rfree), the model is
mathematically equivalent to using IndShockConsumerType with a single
interest rate.
"""

# Import python tools
import sys
import os
import math
import numpy as np
import random
from copy import deepcopy
import pandas as pd

# Import needed tools from HARK
from HARK.distributions import Uniform, Lognormal
from HARK.utilities import get_percentiles, get_lorenz_shares

# Candidate-routing (QE-baseline freeze): rendered figures/tables are written
# as `_candidate` siblings unless HAFISCAL_PROMOTE=1. See generated_output.py.
_FROM_PANDEMIC_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'FromPandemicCode')
if _FROM_PANDEMIC_DIR not in sys.path:
    sys.path.insert(0, _FROM_PANDEMIC_DIR)
from generated_output import make_figs_generated as make_figs, open_generated
# Use parallel execution (same as 0.14.1) for performance
# NOTE: This means RNG sequences may differ, but final estimated parameters
# should converge to the same values due to optimization
from HARK.core import multi_thread_commands
from scipy.optimize import minimize

# =============================================================================
# OPTIMIZATION: Loky Worker Pool Warmup (0.17.0-loky-warmup branch)
# =============================================================================
# Import the pool warmup utility. Set HARK_WARM_POOL=1 to enable.
# This pre-compiles Numba functions in worker processes, avoiding ~4s cold-start.
# See parallel_warmup.py and numba_jit_overhead_mwe/ for details.
try:
    from parallel_warmup import maybe_warm_pool, is_warmup_enabled
    WARMUP_AVAILABLE = True
except ImportError:
    WARMUP_AVAILABLE = False
    def maybe_warm_pool(*args, **kwargs): pass
    def is_warmup_enabled(): return False
# Add parent directory to path for imports (rng_synchronized_consumer, matplotlib_config)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# =============================================================================
# RNG-SYNCHRONIZED CONSUMER TYPE (for numerical reproducibility with 0.14.1)
# =============================================================================
# We use RNGSyncKinkedRconsumerType which fully replicates HARK 0.14.1's RNG
# consumption pattern, including:
#   - sim_birth(): Lognormal draws with fresh seeds (not pre-built distributions)
#   - reset_rng(): Synchronizes IncShkDstn seed to match 0.14.1
#   - sim_death(): Matches 0.14.1's RNG consumption during death events
#
# This ensures that simulation results are IDENTICAL to 0.14.1 when using
# the same random seed, which is essential for validation.
#
# NOTE: The solver patch in ConsIndShockModel.py must also be applied for
# the consumption functions to match exactly.
#
# See rng_synchronized_consumer.py for implementation details.
# =============================================================================
from rng_synchronized_consumer import RNGSyncKinkedRconsumerType as KinkedRconsumerType
# --- STEP-1 DEFAULT STACK = GRID-ONLY (owner word 2026-08-21 "this is my word", executed
# on the comprehensive-battery PASS of the same night; supersedes the same-day hermite60+
# farfield H4 stack). The Step-1 estimator family defaults to the hermite60 solve basis
# (60-count K·h̄ grids, HARK cubic-Hermite slices) + J=8 log-spaced SOLVED tail knots
# spanning [1.06, 6]×the basis top (aXtraExtra) + the measured-Q power-law attach serving
# only beyond the last knot (step1_powerlaw_tail CHS in-place retrofit). The coordinates
# fix: with the knots, all three top-secant identifying inputs live on a decades-long log
# lever arm, so the LOCAL measurement is sound and no mini-solve is needed in the flight
# path — farfield_tail_q is DEMOTED to the certification instrument (window-fit knot Q vs
# Anderson q̂ agree 1–3% on the patient atoms; test_step1_tail_attach.py). Acceptance
# (dell battery 2026-08-21, vs the 604/238 measured-Q control/SoR): 8/8 one basin;
# ς +0.27% / β +0.019% / ∇ −0.76% at ~4× control wall. REACH SHRUNK 12→6 (owner R1
# ruling 2026-08-22 on the K8R6 battery: mode ≡ the 12× default to 0.004pp, scatter
# 1.76–1.90× H4, cert depth ≤7.9e-5, farfield 1.4–5.9%; the original REACH=6 rejection
# (G6 ∇ −1.06%) was entirely the moments-grid-bug artifact — post e3df0bae the knots
# no longer rescale the moments window). J=4 measured DEAD (cert 2.95e-4 at 12× AND
# estimation mode ∇ −1.008%; thin 1.39e-4 at 6× with no battery) — J stays 8. Paper-facing method: lit-synthesis §6 (MoM +
# Lentini–Keller anchors). Explicit env always wins (setdefault). Fidelity conventions:
# QE-fidelity and the as-corrected world keep the conservative measured-Q/full-grid path
# (604/238, no knots — pinned by test_fidelity_guard_reproduces_control). Rollback to
# that world: HAFISCAL_SOLVE_GRID_PROFILE=full HAFISCAL_STEP1_TAIL_KNOTS=0. This block
# must precede the SetupParamsCSTW import (whose grid_sizing import resolves the profile
# mapping).
if (os.environ.get("HAFISCAL_QE_FIDELITY", "") != "1"
        and os.environ.get("HAFISCAL_WORLD", "").strip().lower() != "as-corrected"):
    os.environ.setdefault("HAFISCAL_SOLVE_GRID_PROFILE", "hermite60")
    os.environ.setdefault("HAFISCAL_PF_DECAY_Q", "measured")
    os.environ.setdefault("HAFISCAL_STEP1_TAIL_KNOTS", "8")
    os.environ.setdefault("HAFISCAL_STEP1_TAIL_REACH", "6")
from SetupParamsCSTW import init_infinite
# Opt-in FTI (NAM/ATI) Step-1 wiring; inert unless HAFISCAL_STEP1_FTI=1 (default OFF).
# Defensive: an FTI import failure must never break the default (EGM) Step-1 path.
try:
    import fti_step1
except Exception as _fti_import_err:  # noqa: BLE001
    fti_step1 = None
    print(f"[fti_step1] optional FTI wiring unavailable ({_fti_import_err!r}); "
          f"using stock EGM path.")

# ── Step-1 sim engine (plans/20260724_step1-tm-a-simulation_plan.md) ──
# HAFISCAL_STEP1_SIM_ENGINE: 'tm' (DEFAULT — Stage B deterministic engine,
# landed with the BUG-054 arc: distribution-form wealth targets from the
# joint-moment ergodic, NO panel exists) | 'tm_init' (TM-ergodic panel
# seeding + HAFISCAL_STEP1_WARMUP quarters of MC warmup — the panel-capable
# variant; kills the ~70%-of-eval burn-in AND the BUG-063 truncation) |
# 'mc' (byte-identical legacy T_sim=800 burn-in; the cross-check engine).
# History: mc → tm_init (owner ruling 2026-07-27: MC retired as a default
# for everything except welfare; two-limit consistency at noise level,
# f0 0.00264-0.00273 vs mc 0.00257 ± its own ±1.9% horizon band) → tm
# (Stage B). Plot/diagnostic re-evaluations (estimation_mode=False) need a
# PANEL, so under 'tm' the Plot_Output section below runs them via a scoped
# switch to 'tm_init' (2026-08-03 fix — the m5 end-to-end run caught the
# refuse-loudly guard firing on the paper's comparison artifacts).
# Interpretation default = ESC (owner ruling 2026-06-14, config/catalog.py),
# mirrored here entry-point-scoped exactly like EstimParameters.py, so a bare
# `python Estimation_BetaNablaSplurge.py` produces the PRODUCTION (ESC)
# artifact Result_AllTarget_ESC.txt. Explicit HAFISCAL_INTERPRETATION=CDC runs
# the CDC estimation (written to Result_AllTarget_CDC.txt). ESC became
# runnable in this file with the BUG-054 Option A fix (2026-07-27).
os.environ.setdefault('HAFISCAL_INTERPRETATION', 'ESC')
from _interpretation import get_interpretation, suffix_path

_STEP1_ENGINE = os.environ.get('HAFISCAL_STEP1_SIM_ENGINE', 'tm').strip().lower()
if _STEP1_ENGINE not in ('mc', 'tm_init', 'tm'):
    raise ValueError(f"HAFISCAL_STEP1_SIM_ENGINE must be mc|tm_init|tm; got {_STEP1_ENGINE!r}")
# 'tm' (Stage B): deterministic experiment via step1_tm_targets; the burn-in/
# wealth-target panel still uses the tm_init seeding (full distribution-form
# wealth targets ride the 2-D joint upgrade).
_STEP1_WARMUP = int(os.environ.get('HAFISCAL_STEP1_WARMUP', '40'))
# Wealth-target form under engine 'tm': 'panel' (default — tm_init-seeded panel,
# the 3.1% full-target verdict) | 'dist' (distribution form from the joint
# moments; OPT-IN until it passes the full-target gate — see step1_tm_targets).
_STEP1_WEALTH_FORM = os.environ.get('HAFISCAL_STEP1_WEALTH_FORM', 'dist').strip().lower()
if _STEP1_WEALTH_FORM not in ('panel', 'dist'):
    raise ValueError(f"HAFISCAL_STEP1_WEALTH_FORM must be panel|dist; got {_STEP1_WEALTH_FORM!r}")
if _STEP1_ENGINE in ('tm_init', 'tm'):
    import sys as _s1_sys
    _s1_ham = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    if _s1_ham not in _s1_sys.path:
        _s1_sys.path.insert(0, _s1_ham)
    import step1_tm_init as _step1_tm_init
    # The banner must name the engine ACTUALLY selected. It used to hardcode "tm_init"
    # while firing for both 'tm' and 'tm_init', so a default run -- which is 'tm' -- logged
    # itself as 'tm_init'. That line is the only record of the engine in a run's log, so
    # the mislabel propagated straight into the provenance of every battery.
    if _STEP1_ENGINE == 'tm':
        print(f"[step1-engine] tm (Stage B): deterministic TM experiment via "
              f"step1_tm_targets; wealth-target form={_STEP1_WEALTH_FORM!r}; "
              f"NO Monte Carlo panel"
              + ("" if _STEP1_WEALTH_FORM == 'dist'
                 else f" except the legacy mc-800 burn-in panel for wealth targets"))
    else:
        print(f"[step1-engine] tm_init: TM-ergodic seeding + {_STEP1_WARMUP}q warmup "
              f"(mc burn-in replaced; plan Stage A)")

# ── Step-1 SEARCH PARAMETERIZATION (owner rulings 2026-08-18; plan:
# plans_local/20260818-1200h_step1-unconstrained-reparameterization_plan.md) ──
# HAFISCAL_STEP1_PARAM: 'native' (DEFAULT -- bounded Powell over (splurge, beta, nabla)
# with the arctan GIC taper on the atoms; the pre-2026-08-18 path, byte-identical) |
# 'theta' (opt-in -- unconstrained Powell over theta in R^3 with splurge=expit,
# a_hi=cap_eff-exp, nabla=exp; the taper is SKIPPED because no atom can reach the cap).
# The map lives in Code/HA-Models/step1_param.py and is applied in the CALLERS (find_Opt,
# find_Opt_splurge0), so FagerengObjFunc keeps native units and every direct call to it
# is unaffected. Read ONCE at import, like the engine, so a run cannot straddle modes.
import sys as _s1p_sys
_s1p_ham = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
if _s1p_ham not in _s1p_sys.path:
    _s1p_sys.path.insert(0, _s1p_ham)
import step1_param as _s1param
_STEP1_PARAM = _s1param.param_mode()
print(f"[step1-param] {_STEP1_PARAM}"
      + ("" if _STEP1_PARAM == 'native'
         else f" ({'DEFAULT since the 2026-08-19 adoption' if _STEP1_PARAM == 'mixed' else 'opt-in'}; "
              f"full description printed at the first solve; CAP_EPS={_s1param.CAP_EPS:g})"))
_PARAM_ANNOUNCED = False


def _announce_param(cap, kappa):
    """Print the parameterization ONCE, with the cap it will use, at the first solve --
    the cap needs base_params, which does not exist yet at import time."""
    global _PARAM_ANNOUNCED
    if _PARAM_ANNOUNCED:
        return
    _PARAM_ANNOUNCED = True
    if _STEP1_PARAM == 'theta':
        print("PARAM_MODE: " + _s1param.describe(cap, kappa))
    elif _STEP1_PARAM == 'mixed':
        print(f"PARAM_MODE: mixed = level-splurge COBYQA probe (owner spec 2026-08-19): "
              f"splurge in LEVELS, hard bounds [0, 0.9] (zero included); beta/nabla keep "
              f"their theta forms (a_hi=cap_eff-exp(t_hi), nabla=exp(t_w)) so the GIC cap "
              f"is STRUCTURAL (no optimizer constraint); cap={cap:.10f} "
              f"cap_eff={_s1param.cap_eff(cap):.10f} kappa={kappa:.6f}; taper SKIPPED")
    else:
        print(f"PARAM_MODE: native (bounded (splurge,beta,nabla) + arctan taper, "
              f"tau={TAPER_THRESHOLD:g}, cap={cap:.10f})")


def _sim_burnin(type_list):
    """Burn-in dispatcher: legacy 800q MC / TM seed+warmup / NO PANEL (tm)."""
    if _STEP1_ENGINE == 'tm' and _STEP1_WEALTH_FORM == 'dist':
        # Stage B endpoint: no panel at all (wealth targets in distribution
        # form). GATED opt-in — the dist form currently FAILS its full-target
        # gate (Lorenz +11-16%, KY +2.4% vs the mc panel; 2026-07-27 component
        # isolation); default 'panel' keeps the validated hybrid.
        return
    if _STEP1_ENGINE == 'tm':
        # 'tm' + panel wealth-form: the wealth targets come from the LEGACY
        # mc-800 burn-in panel (the configuration whose full-target gate
        # measured 3.1% — the SEEDED panel's wealth targets measured 0.035-class
        # and are NOT used). The deterministic experiment replaces the panel
        # experiment regardless. The burn-in MC is thus the LAST MC remnant on
        # this path; it dies when the dist wealth-form passes its gate.
        multi_thread_commands(type_list, ['initialize_sim()', 'simulate()'])
        return
    if _STEP1_ENGINE == 'tm_init':
        multi_thread_commands(type_list, ['initialize_sim()'])
        for _t in type_list:
            _step1_tm_init.seed_and_warmup(_t, warmup=_STEP1_WARMUP)
    else:
        multi_thread_commands(type_list, ['initialize_sim()', 'simulate()'])
# STEP-1 DEFAULT NUMERICS = POWER-LAW MEASURED-Q TAIL ON THE K·h̄ GRID (F7
# ruling, 2026-07-24, superseding the same-day F1.4 "convention = exp" block).
# History: the F1.4 neutrality gate measured exp@20 f0=0.06766743433639781 vs
# powerlaw@20 f0=0.06628817986658467 — |dObj/Obj| = 2.04e-2, NOT neutral — and
# the port was reverted per the pre-authorization. The owner then ruled the
# ROOT CAUSE is the hardwired shallow grid, not the tail form: "if the problem
# is that aXtraMax was hard-wired to 20 … remove that default of 20 and let
# the new machinery choose aXtraMax = K × h … and rerun the Step 1 exercise
# accordingly." So, under the measured-Q power-law DEFAULT:
#   * the solve grid comes from the SST resolver
#     grid_sizing.resolve_solve_grid (owner SST ruling, same day: ONE
#     precedence implementation shared with EstimParameters + Parameters —
#     SOLVE_AMAX > K·h̄ > legacy), applied to base_params below with STEP-1's
#     OWN primitives (R=Rsave=1.02^0.25, Γ=1 ⟹ h̄≈201.5, top≈604.5; count from
#     the basis-192 rule anchored at Step-1's legacy 20/20);
#   * each solved cFunc's tail is rewrapped to the production power-law
#     measured-Q form (step1_powerlaw_tail; the F1.4 machinery, re-applied).
# The legacy opt-outs (HAFISCAL_PF_DECAY_EXTRAP=exp/0, or
# HAFISCAL_PF_DECAY_Q=slope for the grid) keep exp@20/legacy-count
# BYTE-IDENTICALLY (regression-gated). Numbers, three-eval decomposition and
# the quarantined cold re-estimation:
# conclusions_private/2026-07-24_f7_step1_khbar_rerun.md. CASCADE GATE: any
# re-estimated Step-1 calibration is owner-gated; if splurge moves beyond
# noise the matched Step-2 re-estimation is the NEXT owner decision.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
try:
    import step1_powerlaw_tail
except Exception as _pl_import_err:  # noqa: BLE001
    step1_powerlaw_tail = None
    print(f"[step1_powerlaw_tail] powerlaw tail rewrap unavailable ({_pl_import_err!r}); "
          f"using HARK-native exp tails.")


# CDC-MOD-BUG035: Step-1 agent type with CDC household-bargain asset rule.
# Sibling to AggFiscalModel.AggFiscalType.get_poststates (BUG-031 patch);
# needed for Step-1 estimation simulator state evolution to be CDC-correct
# in the same sense Step-2/5 already are post-BUG-031. See
# BUGS_private/HAFiscal_BUG-035_step1_agent_state_dynamics_not_cdc.md.
class CDCKinkedRConsumerType(KinkedRconsumerType):
    """KinkedR consumer with CDC household-bargain asset rule.

    Identical to KinkedRconsumerType (= RNGSyncKinkedRconsumerType) except
    `get_poststates` applies the CDC household-bargain asset rule

        a_nrm = m_nrm - c_household_nrm
              = m_nrm - [(1 - ς) * cFunc(m) + ς * ξ]

    instead of HARK's default optimizer-only rule a_nrm = m_nrm - cFunc(m).

    Requires `.Splurge` attribute (the current ς guess during the joint
    estimation) to be set on the instance before `simulate()` is called.
    `FagerengObjFunc` sets `BaseType.Splurge = SplurgeEstimate` at the top
    of each evaluation, and `EstTypeList[j].Splurge` inherits via deepcopy.
    """

    def get_poststates(self):
        # CDC household consumption (normalized by pLvl):
        # c_household = (1-ς)·cFunc(m) + ς·ξ
        cNrm_household = ((1.0 - self.Splurge) * self.controls["cNrm"]
                          + self.Splurge * self.shocks["TranShk"])
        # CDC asset rule: a = m - c_household
        self.state_now["aNrm"] = self.state_now["mNrm"] - cNrm_household
        self.state_now["aLvl"] = self.state_now["aNrm"] * self.state_now["pLvl"]
        # Preserve HARK's standard PlvlAgg update if the parent uses it
        if hasattr(self, "PermShkAggNow") and "PlvlAgg" in (self.state_prev or {}):
            self.state_now["PlvlAgg"] = self.state_prev["PlvlAgg"] * self.PermShkAggNow


# for plotting
import matplotlib.pyplot as plt
from matplotlib_config import show_plot     # located in the parent directory

# for output
cwd             = os.getcwd()
folders         = cwd.split(os.path.sep)
top_most_folder = folders[-1]
if top_most_folder == 'Target_AggMPCX_LiquWealth':
    Abs_Path = cwd
else:
    Abs_Path = cwd + '/Code/HA-Models/Target_AggMPCX_LiquWealth'

# Set key problem-specific parameters
TypeCount = 7       # Number of consumer types with heterogeneous discount factors
LAST_TAPER_CENSUS = None  # BUG-078: refreshed each FagerengObjFunc eval with the atoms-vs-GIC-cap census
# GIC taper band width (the zone is [GICmaxBeta - tau, GICmaxBeta)). Default
# 0.005 by OWNER RULING 2026-08-14 (evening), decided on a same-seed-family A/B
# under the aggregate cap: tau=0.005 halves the objective at the optimum vs the
# inherited 0.01 (f 0.0017545 vs 0.0034196 against the SAME empirical targets),
# with fewer taper-zone atoms (1 vs 2), zero pinned, and the touching atom ~41%
# responsive -- the estimator sheds dispersion (nabla 0.047 -> 0.032) when the
# band stops dragging sub-cap atoms. Known cost: high-beta STARTS are hostile
# (seed [0.3, 1.0, 0.05] starts at f~13.9 and dies far-field; multistart's
# non-killed consensus absorbs those rows). tau=0.01 = the pre-ruling inherited
# 2024-01-09 literal (commit 5648d214, no recorded derivation), reachable via
# env. tau=0.001 was probed and rejected (near-hard-clip, z scales 1/tau).
# SUPERSEDED 2026-08-18 (owner ruling): default is now tau = 0.002, not 0.005.
# At 0.005 the ANSWER OF RECORD sat INSIDE the taper band -- nominal top atom
# 1.006394, 75.5% of the way through the band, only 40.5% responsive -- so the
# taper was not a guardrail the optimum avoided but something SHAPING where the
# optimum landed. At 0.002 the optimum is INTERIOR: the code's own census reports
# n_in_taper=0, n_pinned=0, with the top atom 0.45*tau clear of the band floor.
# Both probe arms agreed (0.29985/0.97951/0.02941 and 0.29985/0.97952/0.02939),
# on two architectures, at f=0.001647 vs 0.0017544 -- a 6.1% better fit to the
# SAME empirical targets.
# The obvious confound was checked: is that 6.1% really the TOLERANCE change
# rather than tau? No. At tau=0.002, loose tolerances gave f=0.001647 (840 evals)
# and tight gave 0.0016470 (1043) -- identical. For a converged seed tolerance
# does not move f, so the gap is tau.
# The f sequence 0.0034196 (tau=.01) -> 0.0017544 (.005) -> 0.001647 (.002)
# decelerates, as expected once the optimum leaves the band: below the escape
# threshold, narrowing tau cannot touch it. tau=0.001 remains rejected
# (near-hard-clip; z scales as 1/tau).
# THE GRID FOLLOWS AUTOMATICALLY: k_top = 1 - 2*tau/cap, so the seeds re-derive
# and stay exactly one band-width clear. Changing tau changes the OBJECTIVE, so
# this opens a new era; runs 1-5 are not comparable to run 6 on f.
# Records: conclusions_private/2026-08-14_gic-cap-min-fvac-aggregate.md (taper
# section) + BUGS_private/HAFiscal_BUG-078_*.
TAPER_THRESHOLD = float(os.environ.get('HAFISCAL_STEP1_TAPER_THRESHOLD', '0.002'))

# Tolerance for float dust at a parameter-domain bound; see the guards in FagerengObjFunc.
# scipy's bounded Powell probed the splurge=0 bound at -5.3e-23 in run 7 (2026-08-18) and
# an exact-zero guard killed two seeds. 1e-9 is ~14 orders above that dust and ~8 orders
# below any value that could move a reported digit.
_DOMAIN_DUST = 1e-9

# Floor on every discount-factor atom (was a local literal in FagerengObjFunc; hoisted so the
# theta path can name the same number). Applies in BOTH parameterizations: under 'theta' it
# is what keeps the objective well-defined at absurd nabla (a_lo far below any sane value),
# since log(nabla) makes nabla>0 structural but not a_lo>MIN_BETA_ATOM -- see step1_param.py.
MIN_BETA_ATOM = 0.01
AdjFactor = 1.0     # Factor by which to scale all of MPCs in Table 9
T_kill    = 400     # Don't let agents live past this age (expressed in quarters)
drop_corner = True  # If True, ignore upper left corner when calculating distance

# Set standard HARK parameter values (from stickyE paper)
base_params = deepcopy(init_infinite)
base_params['LivPrb']       = [0.995]       #from stickyE paper
base_params['Rfree']        = 1.015         #from stickyE paper
base_params['Rsave']        = 1.015         #from stickyE paper
base_params['Rboro']        = 1.025         #from stickyE paper
base_params['PermShkStd']   = [0.001**0.5]  #from stickyE paper
base_params['TranShkStd']   = [0.132**0.5]  #from stickyE paper
base_params['T_age']        = 400           # Kill off agents if they manage to achieve T_kill working years
base_params['AgentCount']   = 5000          # Number of agents per instance of IndShockConsType
base_params['pLogInitMean'] = np.log(23.72) 
base_params['T_sim']        = 800


Parametrization = 'NOR' 
if  Parametrization == 'NOR':    
    base_params['LivPrb']       = [1-1/160]     
    base_params['Rfree']        = 1.02**0.25
    # Interest rate settings for KinkedRconsumerType:
    # - Rsave: Interest rate earned on positive assets (set = Rfree for baseline)
    # - Rboro: Interest rate paid on debt (only matters if BoroCnstArt < 0)
    # With BoroCnstArt = 0, agents cannot borrow so Rboro has no effect.
    base_params['Rsave']        = 1.02**0.25    # Same as Rfree (no kink when saving)
    base_params['Rboro']        = 1.137**0.25   # ~13.7% annual (only used if borrowing enabled)
    base_params['pLogInitMean'] = 0 
    base_params['UnempPrb']     = 0.044
    base_params['IncUnemp']     = 0.60
    base_params['PermShkStd']   = [0.001**0.5] #from Crawley,Moll,Tretvoll
    base_params['TranShkStd']   = [0.132**0.5]
    # Borrowing constraint: 0 = no borrowing allowed (baseline)
    # To check robustness with borrowing, set to negative value, e.g.:
    #   base_params['BoroCnstArt'] = -0.8  # Allow borrowing up to 80% of perm income
    # When BoroCnstArt < 0, agents can borrow and will face Rboro on debt.
    base_params['BoroCnstArt']  = 0  # No borrowing (was -0.8 before Jan 2024)
    base_params['PermGroFacAgg']= 1.01**0.25
    base_params['CRRA']         = 2.0
    base_params['T_age']        = None


# ── Step-1 solve grid via the SST resolver (F7, 2026-07-24) ──────────────────
# grid_sizing.resolve_solve_grid is THE precedence implementation (owner SST
# ruling — no local copy): HAFISCAL_SOLVE_AMAX > K·h̄ under the measured-Q
# default > legacy 20/20 (byte-identical opt-outs). h̄ from STEP-1's OWN
# primitives: the KinkedR saving rate (Rsave; = Rfree here, and the binding
# rate at BoroCnstArt=0 where agents never borrow) and the INDIVIDUAL
# PermGroFac. count_basis_anchor=20 = Step-1's unmodified code default, so the
# count-converged basis-192 promotion mirrors the production sites' anchor-48
# rule. See the F7 ruling block above.
import grid_sizing as _gs_step1
_s1_aMax, _s1_aCount, _s1_why = _gs_step1.resolve_solve_grid(
    Rfree=float(np.asarray(base_params.get('Rsave', base_params['Rfree'])).reshape(-1)[0]),
    PermGroFac=float(np.asarray(base_params['PermGroFac']).reshape(-1)[0]),
    legacy_aMax=base_params['aXtraMax'],
    # HAFISCAL_AXTRA_COUNT's VALUE must enter as the count base here, mirroring the
    # EstimParameters site (which reads the env into ITS aXtraCount before resolving).
    # Without this, setting the env merely SUPPRESSED the basis-192 promotion while the
    # value never arrived: the hermite60 arms ran 25-point grids (60*20/48) against a
    # 238-point control — the invalid-S1-arms bug, 2026-08-21.
    legacy_count=int(os.environ.get('HAFISCAL_AXTRA_COUNT',
                                    base_params['aXtraCount'])),
    aXtraMin=base_params['aXtraMin'], count_basis_anchor=20,
    tag='[grid_sizing:step1]')
if _s1_why is not None:
    print(f"[grid_sizing:step1] {_s1_why} → aXtraMax/aXtraCount: "
          f"{_s1_aMax:.0f}/{_s1_aCount} "
          f"(legacy {base_params['aXtraMax']}/{base_params['aXtraCount']}; "
          f"count scaled to hold near-0 density)")
base_params['aXtraMax'] = _s1_aMax
# --- SOLVED TAIL KNOTS above the top (lit-synthesis shortlist #1, owner-ordered experiment
# 2026-08-21): append J log-spaced knots covering the expectation REACH SET (top-knot
# expectations land at m' up to ~1.15-1.6x the top), so the fixed point consults SOLVED
# values there instead of the extrapolant — closing the measured ~10x feedback channel by
# construction. Default 0 = byte-identical. HARK's make_assets_grid inserts aXtraExtra
# verbatim, so the grid top becomes reach_hi * aXtraMax and every consumer of
# max(aXtraGrid) (farfield window, attach pin) adapts automatically.
_s1_tailJ = int(os.environ.get('HAFISCAL_STEP1_TAIL_KNOTS', '0'))
if _s1_tailJ > 0:
    _s1_reach = float(os.environ.get('HAFISCAL_STEP1_TAIL_REACH', '2.2'))
    _s1_knots = [float(v) for v in
                 np.geomspace(1.06 * _s1_aMax, _s1_reach * _s1_aMax, _s1_tailJ)]
    base_params['aXtraExtra'] = _s1_knots
    print(f"[tail-knots:step1] J={_s1_tailJ} solved knots above the top "
          f"({_s1_knots[0]:.0f}..{_s1_knots[-1]:.0f}); attach serves only beyond")
base_params['aXtraCount'] = _s1_aCount


## TARGETS
# implements (eq:targets) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
# (the calibration targets the spec lists in §3: K/Y ≈ 6.60, four Lorenz percentiles
#  20/40/60/80, and the aggregate Fagereng-Holm-Natvik lottery MPC at horizons 0–4)

# Define the MPC targets from Fagereng et al Table 9; element i,j is lottery quartile i, deposit quartile j
MPC_target_base = np.array([[1.047, 0.745, 0.720, 0.490],
                            [0.762, 0.640, 0.559, 0.437],
                            [0.663, 0.546, 0.390, 0.386],
                            [0.354, 0.325, 0.242, 0.216]])
MPC_target = AdjFactor*MPC_target_base

# Define the agg MPCx targets from Fagereng et al. Figure 2; first element is same-year response, 2nd element, t+1 response etcc
Agg_MPCX_target = np.array([0.5056845, 0.1759051, 0.1035106, 0.0444222, 0.0336616])

# Define the four lottery sizes, in thousands of USD; these are eyeballed centers/averages
# 5th element is used as rep. lottery win to get at aggregate MPC / MPCX
lottery_size_USD = np.array([1.625, 3.3741, 7.129, 40.0, 7.129])
lottery_size_NOK = lottery_size_USD * (10/1.1) #in Fagereng et al it is mentioned that 1000 NOK = 110 USD
lottery_size = lottery_size_NOK / (270/4); # Income after tax according to Table 1 is approx. 24k USD.
RandomLotteryWin = True #if True, then the 5th element will be replaced with a random lottery size win draw from the 1st to 4th element for each agent

# Liquid wealth target from US
lorenz_target = np.array([0.029, 0.354, 1.84, 7.42])/100
KY_target = 6.60

# BUG-077 stage C (the tau*-world cascade): under
# HAFISCAL_CALIB_TARGET_INCOME=taustar the wealth-to-income RATIO
# target is restated in the model's net-income units (x 1/(1-tau*)).
# The lottery sizes are ALREADY disposable-income-denominated (the
# normalization above divides by "Income after tax according to
# Table 1"), and the Lorenz targets are scale-free shares — both stay
# untouched. Outputs carry the '_taustar' suffix via suffix_path.
_cti_s1 = os.environ.get('HAFISCAL_CALIB_TARGET_INCOME', 'gross').strip().lower()
if _cti_s1 == 'taustar':
    import sys as _s1sys
    _ha_models_s1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _ha_models_s1 not in _s1sys.path:
        _s1sys.path.insert(0, _ha_models_s1)
    from fiscal_tau_star import TAU_STAR as _ts_s1
    KY_target = KY_target / (1.0 - _ts_s1)
    print(f"[calib-target-income] TAUSTAR: KY_target restated -> {KY_target:.4f} "
          f"(x 1/(1-{_ts_s1:.6f})); lottery sizes already disposable-denominated; "
          f"Lorenz shares scale-free", flush=True)




#%%  Interpretation-specific helpers (extracted from inline closures during the
# CDC/ESC configurable refactor; see plans/20260426-0706h_pre-refactor-prep.md
# item 2a and plans/20260425-2137h_cdc-esc-configurable-refactor.md — both DONE).
# CURRENT REALITY: the ESC sibling helpers once promised here
# (`_wealth_under_esc`, `_lottery_consumption_under_esc`) were never built. The
# CDC wealth/lottery path below runs UNCONDITIONALLY under both interpretations
# (only the agent TYPE dispatches on HAFISCAL_INTERPRETATION). Owner ruling
# 2026-06-12: this is a BUG in the ESC pathway, not an intended approximation —
# tracked as BUGS_private/HAFiscal_BUG-054_step1_esc_uses_cdc_wealth_correction.md
# (default CDC pipeline unaffected; fix = build the siblings + dispatch).

_GIC_GUARD_WARNED = False


def _verify_gic_satisfied(beta_set, base_params, agents):
    """AGGREGATE-stationarity guard for the Step-1 discount-factor atoms: GPF_Liv < 1.

    Verifies the mortality-adjusted Growth Patience Factor for every tapered atom:

        GPF_Liv(beta) = (R*beta)^(1/rho) * LivPrb / Gamma_individual  <  1

    GPF_Liv < 1 is what determines whether a steady-state distribution of wealth
    exists when mortality is active (OWNER RULING 2026-08-17), and it is therefore
    the existence condition for the simulated cross-section and the MC/TM ergodic
    distribution.

    NO Jensen term. Until 2026-08-17 this guard multiplied by E[1/psi] =
    exp(PermShkStd**2), following the `GPF_out` spelling in
    conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md
    (see that file's 2026-08-17 amendment). E[1/psi] is a Jensen artifact of the
    INDIVIDUAL normalized ratio m = M/P, which divides by the idiosyncratic permanent
    shock; in the AGGREGATE ratio those shocks average out (E[psi] = 1), so the term
    does not belong in a population-stationarity condition. Dropping it moves the
    boundary from beta = 1.0056042 to beta = 1.0076174 -- which is EXACTLY
    GICmaxBeta, the cap the taper enforces (owner ruling 2026-08-14, the
    mortality-adjusted aggregate cusp (Gamma/L)^rho/R). Guard and cap now test the
    same condition, as they should: previously the guard was 0.0020 in beta STRICTER
    than the cap, so it warned about atoms the cap deliberately admitted (it fired
    once on each arm of run 4 for exactly that reason).

    Mortality sits OUTSIDE the 1/rho power. The LivPrb-INSIDE form,
    GPF_in = (R*beta*LivPrb)^(1/rho)/Gamma, is the *individual* condition -- whether
    each agent has a finite buffer-stock target -- and the near-edge top atom is
    allowed to violate it by design (no finite individual target). That inside/outside
    finding is unchanged by this amendment; only the Jensen term was dropped.

    Gamma_individual is the agent's INDIVIDUAL perceived per-period growth
    (PermGroFac = 1.0 in Step 1), NOT the aggregate PermGroFacAgg that the legacy
    GICmaxBeta cap uses.

    Warn-once and never raise: FagerengObjFunc is the optimizer's hot loop, and the
    arctan taper can asymptotically push the top atom toward the (slightly loose) cap
    for extreme (center, spread), so a hard assert would crash the search. The point
    is to surface an aggregate-non-stationarity violation instead of letting it pass
    silently.
    """
    global _GIC_GUARD_WARNED
    if _GIC_GUARD_WARNED:
        return
    try:
        R = float(base_params['Rfree'])
        L = float(base_params['LivPrb'][0])
        rho = float(base_params['CRRA'])
        # individual perceived growth (SetupParamsCSTW.PermGroFac_i == 1.0)
        Gamma = float(np.asarray(agents[0].PermGroFac).reshape(-1)[0])
        # GPF_Liv: mortality OUTSIDE the 1/rho power, no Jensen term (see docstring)
        gpf_liv = (R * np.asarray(beta_set, dtype=float)) ** (1.0 / rho) * L / Gamma
        worst = float(np.max(gpf_liv))
        if worst >= 1.0:
            import warnings
            warnings.warn(
                "BUG-060: Step-1 GIC taper admitted a discount-factor atom that "
                f"VIOLATES the AGGREGATE-stationarity condition GPF_Liv (max GPF_Liv "
                f"= {worst:.6f} >= 1; Gamma_individual = {Gamma:.6f}) -> no steady-state "
                "distribution of wealth exists for that atom, so the simulated "
                "cross-section is non-stationary. (This is NOT the by-design "
                "individual-target GPF_in>1 violation.) Since 2026-08-17 this guard "
                "shares its boundary with GICmaxBeta, so reaching here means the taper "
                "itself let an atom past its own cap -- investigate the taper, not the "
                "threshold. See BUGS_private/HAFiscal_BUG-060_*.md.",
                RuntimeWarning,
                stacklevel=2,
            )
            _GIC_GUARD_WARNED = True
    except Exception:
        # never let a diagnostic guard break the estimation
        pass


# implements (eq:budget-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
def _wealth_under_cdc(agent, splurge):
    """CDC-MOD-BUG032: splurge-in-budget wealth correction under the CDC household-bargain reading.

    Under (eq:budget-CDC) of models_CDC_and_ESC.md §4.2 (alias: (CDC-1)):
        a_actual = m - c_actual = m - (1-ς)·cFunc(m) - ς·y
                                = aLvl_HARK - ς·pLvl·(TranShk - cNrm).

    HARK's state_now["aLvl"] = pLvl·(mNrm - cNrm) = aLvl_HARK. Correction
    applies a ς·(y - cFunc)·pLvl shift: agents who would under-spend
    (cNrm < TranShk) have LESS actual wealth (they forced extra spending
    via splurge); agents who over-spend (cNrm > TranShk) have MORE.

    See plans/20260425-2102h_cdc-implementation-map.md row 32.2.

    FIXED (BUG-054 Option A, owner-ordered 2026-07-27): the ESC sibling
    `_wealth_under_esc` (Edmund Crawley's `(1-ς)·aLvl` line, ported from
    `origin/maintain_bound_pair_fix_splurge`) now exists, and every wealth
    read-out goes through the `_wealth_actual` dispatcher — this CDC helper
    runs only under HAFISCAL_INTERPRETATION=CDC. Output is routed per
    interpretation (suffix_path): ESC runs write `Result_AllTarget_ESC.txt`,
    CDC runs write `Result_AllTarget_CDC.txt`; the bare `Result_AllTarget.txt`
    is a symlink to the production (_ESC) file. See
    BUGS_private/HAFiscal_BUG-054_step1_esc_uses_cdc_wealth_correction.md and
    conclusions_private/2026-06-11_esc_step1_wealth_concept_investigation.md.
    """
    aLvl_hark = agent.state_now["aLvl"]
    # cNrm may live in controls or state_now depending on HARK type
    cNrm = agent.controls.get("cNrm", agent.state_now.get("cNrm"))
    return aLvl_hark - splurge * agent.state_now["pLvl"] * \
        (agent.shocks["TranShk"] - cNrm)


# implements the ESC wealth read-out of models_CDC_and_ESC.md §5.3 (Convention 1)
def _wealth_under_esc(agent, splurge):
    """ESC (splurge-out-of-stage) household wealth: (1 - ς)·aLvl.

    Ported from Edmund Crawley's `origin/maintain_bound_pair_fix_splurge`
    (his exact line: `(1-SplurgeEstimate)*ThisType.state_now["aLvl"]`) —
    BUG-054 Option A, owner-ordered 2026-07-27. Homotheticity (BUG-054 dossier
    review 2026-06-11): under ESC the stage problem is the SAME standard
    solve; the household balance sheet is its level rescale by (1 - ς),
    applied at the read-out. The simulated trajectory is the plain optimizer's
    (a = m - cFunc(m)), which is exactly what the plain (non-CDC) agent type
    the ESC branch constructs already simulates.
    """
    return (1.0 - splurge) * agent.state_now["aLvl"]


def _wealth_actual(agent, splurge):
    """Interpretation dispatch for the household wealth read-out (BUG-054).

    HAFISCAL_STEP1_WEALTH_LEGACY=1 (reproduction arm ONLY, 2026-08-29): the PUBLISHED
    read-out -- the raw HARK `aLvl` with no splurge adjustment (QE
    Estimation_BetaNablaSplurge.py:146), which is what the K/Y and Lorenz targets were
    matched on in the paper. Found by the 0.14.1-vs-0.17.2 bisection at the published
    point: the MPC and Lorenz blocks agree to 4-6 digits, the whole 0.0049 -> 0.066
    objective gap is K/Y 6.58 -> 4.96 = the ESC (1 - s) rescale (plan
    20260829-1935h, D1).
    """
    if os.environ.get('HAFISCAL_STEP1_WEALTH_LEGACY', '').strip() == '1':
        return agent.state_now["aLvl"]
    if get_interpretation() == 'ESC':
        return _wealth_under_esc(agent, splurge)
    return _wealth_under_cdc(agent, splurge)


# implements (eq:total-CDC) and (eq:budget-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
def _lottery_consumption_under_cdc(cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm):
    """CDC-MOD-BUG032: splurge-in-budget lottery-MPC formula under the CDC household-bargain reading.

    Both baseline and lottery trajectories implement (eq:total-CDC) for the
    consumption side and (eq:budget-CDC) for the asset side (per
    models_CDC_and_ESC.md §4.1-4.2; aliases (CDC-1)):
        c = (1 - ς)·cFunc(m) + ς·income       — (eq:total-CDC)
        a = m - c                              — (eq:budget-CDC)

    cFunc is evaluated at the original (pre-splurge) market resources because
    the HARK solver is splurge-unaware. Under splurge-in-budget, the asset
    update subtracts the realized weighted consumption (CDC-1). See
    BUGS_private/HAFiscal_BUG-032_lottery_splurge_formula.md.

    The ESC sibling `_lottery_consumption_under_esc` exists since the BUG-054
    Option A fix (2026-07-27); call sites go through the `_lottery_consumption`
    dispatcher. (An older note here sketched cFunc(m/(1-ς)) per-Optimizer
    normalization for ESC; the 2026-06-11 homotheticity review settled ESC as
    Convention 1 — the SAME standard solve with the plain asset rule, the
    (1-ς) rescale applied at the wealth read-out — which is what Edmund's
    branch and the sibling implement.)

    Returns (c_base_nrm, a_base_nrm, c_actu_nrm, a_actu_nrm) — all normalized
    by pLvl. Caller multiplies by pLvl for level versions.
    """
    c_base_nrm = (1 - splurge) * cFunc(m_base) + splurge * xi_hark
    a_base_nrm = m_base - c_base_nrm
    c_actu_nrm = (1 - splurge) * cFunc(m_lottery) + splurge * TotIncNrm
    a_actu_nrm = m_lottery - c_actu_nrm
    return c_base_nrm, a_base_nrm, c_actu_nrm, a_actu_nrm


# implements the ESC lottery-MPC arithmetic (BUG-054 Option A, Edmund's convention)
def _lottery_consumption_under_esc(cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm):
    """ESC lottery-MPC arithmetic (BUG-054 Option A, 2026-07-27).

    Household CONSUMPTION is the same total under both interpretations
    (c = (1-ς)·cFunc(m) + ς·income, the lottery counted in income); the
    interpretations differ only in the ASSET update: ESC tracks the plain
    optimizer post-state a = m - cFunc(m) (Edmund's `a_adj = m_adj - c_opt`
    on `origin/maintain_bound_pair_fix_splurge`), not the household-blended
    budget. Same return signature as the CDC helper.
    """
    c_stage_base = cFunc(m_base)
    c_stage_lott = cFunc(m_lottery)
    c_base_nrm = (1 - splurge) * c_stage_base + splurge * xi_hark
    a_base_nrm = m_base - c_stage_base
    c_actu_nrm = (1 - splurge) * c_stage_lott + splurge * TotIncNrm
    a_actu_nrm = m_lottery - c_stage_lott
    return c_base_nrm, a_base_nrm, c_actu_nrm, a_actu_nrm


def _lottery_consumption_legacy_bug032(cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm):
    """The PUBLISHED lottery-MPC arithmetic (the pre-BUG-032 code, reproduction arm ONLY).

    HAFISCAL_LOTTERY_SPLURGE_LEGACY=1 restores what the QE code did (dossier
    BUGS_private/HAFiscal_BUG-032_lottery_splurge_formula.md, "Root cause"):
        c_base = cFunc(m)                      (no splurge on the baseline path)
        SplurgeNrm = s * L                     (splurge on the lottery INCREMENT only)
        c_actu = cFunc(m + L - SplurgeNrm) + SplurgeNrm
        a = m (+ L) - c                        (both paths)
    with L = TotIncNrm - xi_hark the normalized lottery increment of THIS quarter
    (zero in every other quarter, so later quarters reduce to c = cFunc(m) on both
    paths -- the pattern the pre-fix code extended). Added 2026-08-29 for the
    ergodic-conversion chain (plans/20260829-1935h_ergodic-conversion-chain_plan.md,
    D1): column A must estimate the splurge exactly the paper's way so that the
    BUG-032 fix is measured in the corrections column, not hidden in "new machinery".
    """
    L = TotIncNrm - xi_hark
    spl = splurge * L
    c_base_nrm = cFunc(m_base)
    a_base_nrm = m_base - c_base_nrm
    c_actu_nrm = cFunc(m_lottery - spl) + spl
    a_actu_nrm = m_lottery - c_actu_nrm
    return c_base_nrm, a_base_nrm, c_actu_nrm, a_actu_nrm


def _lottery_consumption(cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm):
    """Interpretation dispatch for the lottery-MPC arithmetic (BUG-054)."""
    if os.environ.get('HAFISCAL_LOTTERY_SPLURGE_LEGACY', '').strip() == '1':
        return _lottery_consumption_legacy_bug032(
            cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm)
    if get_interpretation() == 'ESC':
        return _lottery_consumption_under_esc(
            cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm)
    return _lottery_consumption_under_cdc(
        cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm)


#%%  Objective function

def gic_taper_cap():
    """The GIC cap the discount-factor taper enforces, plus its two candidate cusps.

    SINGLE SOURCE for the cap. Called by the taper inside FagerengObjFunc *and* by
    the cold-multistart grid builder, so a startpoint can never be constructed
    against a different cap than the one that will taper it -- the defect that
    killed run 4 (see the grid builder's comment, owner ruling 2026-08-17).

    Reads base_params at CALL time rather than closing over module-level constants,
    because the CRRA-sensitivity blocks near the bottom of this file mutate
    base_params['CRRA']; each caller therefore gets the cap that applies to its own
    parametrisation. Returns (GICmaxBeta, beta_FVAC, beta_AGG).

    Which condition, why the aggregate cusp alone, and why FVAC is a diagnostic
    only: see the comment block at the taper site in FagerengObjFunc and
    conclusions_private/2026-08-14_gic-cap-min-fvac-aggregate.md.
    """
    _Gamma_ind = base_params['PermGroFac'][0]                       # individual per-period growth (= 1.0)
    _L_surv = base_params['LivPrb'][0]
    _rho_crra = base_params['CRRA']
    _sig2_psi = base_params['PermShkStd'][0]**2
    _E_psi_1mrho = float(np.exp(_sig2_psi * _rho_crra * (_rho_crra - 1.0) / 2.0))  # E[psi^(1-rho)]
    _beta_FVAC = _Gamma_ind**(_rho_crra - 1.0) / (_L_surv * _E_psi_1mrho)
    _beta_AGG = (_Gamma_ind / _L_surv)**_rho_crra / base_params['Rfree']
    if os.environ.get('HAFISCAL_STEP1_GIC_LEGACY', '0') == '1':
        # pre-BUG-060 behavior: aggregate Gamma + old additive form (GPF_out, but loose)
        GICmaxBeta = (1-base_params['LivPrb'][0]) + (base_params['PermGroFacAgg']**base_params['CRRA'])/base_params['Rfree']
    elif os.environ.get('HAFISCAL_STEP1_GIC_GPFMOD', '0') == '1':
        # 2026-06-16..2026-08-14 interim (BUG-060-corrected GPF-Mod form): the cusp
        # for finiteness of the mean individual ratio E[M/P] (Jensen E[1/psi] term).
        # Escape hatch for byte-exact reproduction of the run-1 / BUG-054-anchor
        # objective; superseded as default by the min(FVAC, aggregate) ruling.
        _E_inv_psi = float(np.exp(base_params['PermShkStd'][0]**2))     # E[1/psi] for mean-one lognormal
        GICmaxBeta = (_Gamma_ind / (base_params['LivPrb'][0]*_E_inv_psi))**base_params['CRRA'] / base_params['Rfree']
    else:
        GICmaxBeta = _beta_AGG
    return GICmaxBeta, _beta_FVAC, _beta_AGG


def top_atom_offset():
    """How far the most-patient atom sits above the distribution centre, per unit
    of spread. Uniform(center-spread, center+spread).discretize(N) places N
    equiprobable atoms at the interval midpoints, so the extreme one lands
    (N-1)/N of the way out, NOT at center+spread. Derivation: atom i sits at
    bot + (top-bot)*(2i+1)/(2N); for i=N-1 that is center + spread*(N-1)/N.
    At TypeCount=7 the factor is 6/7 -- e.g. a nominal (beta,nabla) of
    (0.978601, 0.032420) yields a top atom of 1.006390, not 1.011021.
    """
    return (TypeCount - 1) / TypeCount


def FagerengObjFunc(SplurgeEstimate,center,spread,verbose=False,estimation_mode=True,target='AGG_MPC',investigate=False):
    '''
    Objective function for the quick and dirty structural estimation to fit
    Fagereng, Holm, and Natvik's Table 9 results with a basic infinite horizon
    consumption-saving model (with permanent and transitory income shocks).

    Parameters
    ----------
    center : float
        Center of the uniform distribution of discount factors.
    spread : float
        Width of the uniform distribution of discount factors.
    verbose : bool
        When True, print to screen MPC table for these parameters.  When False,
        print (center, spread, distance).

    Returns
    -------
    distance : float
        Euclidean distance between simulated MPCs and (adjusted) Table 9 MPCs.
    '''
    
    # SPLURGE-RANGE TRIPWIRE (2026-08-18). splurge (varsigma) is a CONVEX-COMBINATION
    # WEIGHT, not a free parameter: consumption is c = (1-s)*cFunc(m) + s*income and the
    # ESC household balance sheet is wealth = (1-s)*aLvl. Outside [0,1] neither expression
    # is a convex combination any more.
    #
    # The two sides fail differently, and NEITHER is the silent mirror that makes the nabla
    # guard below so important -- both expressions are AFFINE in s, so f(-s) != f(+s) and a
    # negative splurge shows up as a bad fit rather than a plausible one (measured: at
    # cFunc=0.8, y=1.0, s=+0.3 gives c=0.86 and s=-0.3 gives c=0.74). This guard therefore
    # buys less than the nabla one; it is here to reject a meaningless parameterisation
    # cheaply and at the point of use, rather than to catch an invisible answer.
    #
    # The s>1 side is the more insidious of the two: (1-s)*aLvl flips the SIGN of every
    # agent's wealth simultaneously (s=1.5 sends aLvl 0.5/2.0/10.0 to -0.25/-1.0/-5.0), so
    # the entire liquid-wealth cross-section inverts while f stays finite.
    #
    # BOTH ENDPOINTS ARE ADMITTED, deliberately. s=0 is not hypothetical -- four call sites
    # pass a literal 0 (find_Opt_splurge0 and its check probe, and the two Run_3D_Plot
    # calls), so a guard written `<= 0` would break the Splurge=0 arm outright. s=1 is the
    # degenerate but well-defined pure-hand-to-mouth limit; it makes wealth identically 0
    # for every agent, which makes the liquid-wealth targets uninformative but is not a
    # sign error, so it is treated as valid-but-degenerate rather than rejected.
    #
    # BOUNDARY DUST -- the tolerance is NOT cosmetic (regression fixed 2026-08-18). scipy's
    # bounded Powell does not keep its evaluations strictly inside the box: the line-search
    # arithmetic can undershoot a bound by float dust. MEASURED in run 7: the splurge=0
    # bound was probed at -5.293955920339377e-23 on x86-64, and the first version of this
    # guard rejected it, killing seeds 4 and 8 outright about 19 evaluations in. A guard
    # that rejects a value which IS zero to 23 significant figures is not protecting the
    # estimate, it is breaking the optimizer.
    #
    # So the trigger is a MATERIALLY out-of-range value. _DOMAIN_DUST sits ~14 orders above
    # the observed dust and ~8 orders below any splurge or nabla that could move a reported
    # digit, so no value is both plausible and ambiguous.
    #
    # The dust is passed through UNCHANGED rather than clamped to the bound: clamping would
    # alter the value the objective sees and break bitwise agreement with the pre-guard
    # code, for a difference of 5e-23 that nothing downstream can resolve.
    if not (-_DOMAIN_DUST <= SplurgeEstimate <= 1.0 + _DOMAIN_DUST):
        raise ValueError(
            "splurge (SplurgeEstimate) = %r is outside [0, 1]. splurge is a convex-"
            "combination weight: c = (1-s)*cFunc(m) + s*income and wealth = (1-s)*aLvl, "
            "so s<0 or s>1 makes neither a convex combination, and s>1 inverts the sign "
            "of the entire wealth cross-section. Bound splurge to [0, 1] at the call "
            "site." % (SplurgeEstimate,))

    # NEGATIVE-SPREAD TRIPWIRE (2026-08-18). nabla is a HALF-WIDTH, so nabla<0 is not just
    # meaningless -- it is SILENTLY meaningless. Uniform(bot=center+|nabla|,
    # top=center-|nabla|).discretize(N) returns the same SET of atoms as +|nabla|, merely in
    # reverse order (measured: sorted atoms allclose, unsorted not). A search permitted into
    # nabla<0 would therefore find a perfect MIRROR of the true minimum at -nabla_hat, with
    # an f indistinguishable from the real one, and report a negative dispersion that
    # nothing downstream would question.
    #
    # All four call sites bound nabla to [0.0,0.4] (find_Opt, its check_maximum probe,
    # find_Opt_splurge0, and that arm's L-BFGS-B diagnostic).
    #
    # RETRACTED 2026-08-18, and the retraction is the useful part. This comment used to cite
    # "ZERO negative evaluations in 6,320 logged evals" as proof that no call site could
    # reach the failure region. That evidence was INVALID: the guard runs at the TOP of this
    # function and the (splurge, beta, nabla, distance) line is printed at the BOTTOM, so a
    # rejected value never reaches the log. Historical logs record only the evaluations that
    # COMPLETED, and therefore could not have contained an out-of-range probe even if one
    # had occurred every time. The supporting scipy experiment was equally weak -- it planted
    # a minimum outside the bound on a smooth quadratic, which is not the ragged objective
    # whose line search actually produces the dust.
    #
    # The correct instrument is to record what the objective is CALLED with, not what it
    # logged: see test_boundary_dust_is_tolerated, which drives a real bounded Powell solve
    # and captures every incoming argument.
    #
    # It exists for when that stops being true -- an unbounded call, a swapped optimizer, a
    # hand-written direct call -- which is exactly when a silent mirror answer would do the
    # most damage. Guarding at the OBJECTIVE rather than inside powell_minimize is
    # deliberate: the L-BFGS-B diagnostic bypasses that SST, but not this line.
    # Same boundary-dust tolerance as the splurge guard above, and for the same reason: the
    # nabla=0 bound is approached by the nabla0=0.01 seeds and Powell will undershoot it by
    # float dust exactly as it did on splurge. This guard had not fired only because those
    # seeds had not reached the bound yet -- it was the same defect, not a different one.
    #
    # Written as `not (spread >= -_DOMAIN_DUST)` rather than `spread < -_DOMAIN_DUST` so the
    # test IS the stated invariant. The two differ only on NaN, where every comparison is
    # False: this form rejects NaN, the other would wave it through to build NaN atoms and
    # hand Powell a NaN distance.
    if not (spread >= -_DOMAIN_DUST):
        raise ValueError(
            "nabla (spread) = %r is not >= 0. nabla is a half-width: a negative value "
            "produces the SAME discount-factor atoms as +|nabla|, so the search would "
            "settle on a mirror minimum with no economic meaning. Bound nabla to a "
            "non-negative interval at the call site." % (spread,))

    # Give our consumer types the requested discount factor distribution
    for j in range(TypeCount):
        EstTypeList[j].reset_rng()
    random.seed(55)
    beta_set = Uniform(bot=center-spread, top=center+spread).discretize(TypeCount).atoms[0]
    _beta_set_nominal = beta_set.copy()  # BUG-078 census: atoms before the GIC taper

    # Taper off toward the growth impatience condition
    #
    # WHICH condition: this cap targets the AGGREGATE-stationarity factor GPF_out
    # (LivPrb OUTSIDE the 1/rho power) = (R*beta)^(1/rho)*L*E[1/psi]/Gamma < 1, which
    # is the existence condition for the simulated cross-section (and the MC/TM ergodic
    # distribution). It is NOT the individual-target factor GPF_in (LivPrb inside) =
    # (R*beta*L)^(1/rho)*E[1/psi]/Gamma < 1; the most-patient atom is allowed to violate
    # GPF_in (no finite individual target) by design — same convention as Step 2's
    # EstimParameters.py shave. See conclusions_private/2026-06-16_gic-inside-vs-outside-
    # individual-target-vs-tm-ergodic.md.
    #
    # BUG-060 (FIXED, default): the cap is now the GPF_out=1 boundary computed with the
    # *individual* PermGroFac (= 1.0 in Step 1, SetupParamsCSTW.PermGroFac_i) and the
    # corrected multiplicative form (Gamma/(L*E[1/psi]))^rho/R — identical convention to
    # BUG-037 Change (c) in EstimParameters.py. E[1/psi] = exp(PermShkStd^2) (lognormal,
    # E[psi]=1). This is the Step-1 sibling fix that BUG-037 should have included.
    #
    # The pre-BUG-060 cap used the *aggregate* PermGroFacAgg (= 1.01**0.25, != 1) as Gamma
    # and the old additive bound (1-L)+Gamma^rho/R, giving ~1.006275 vs the correct
    # ~1.005604 (looser by ~0.00067 — admitted GPF_out>1 atoms asymptotically; realized
    # atoms stayed below only via the arctan margin). Escape hatch for byte-identical
    # pre-fix reproduction: HAFISCAL_STEP1_GIC_LEGACY=1. NOTE: this fix moves the cap, so
    # it re-tapers the top ~2 atoms (<=0.0006 in beta) and slightly changes the estimated
    # splurge -> requires a Step-1 re-estimation + candidate promotion (the published QE
    # numbers live on the frozen tag). See
    # BUGS_private/HAFiscal_BUG-060_step1_gic_taper_aggregate_gamma_and_old_formula.md.
    # Owner ruling 2026-08-14 (REVISED later same day: FVAC dropped): the cap is
    # the mortality-adjusted AGGREGATE cusp alone -- the two things that matter
    # are (1) finiteness of the AGGREGATE wealth-income ratio and (2)
    # nondegeneracy of the consumption function, and (2) is guarded by the FHWC
    # precondition + RIC (slack), NOT by FVAC (see below).
    # (0) PRECONDITION, imposed in practice (owner note 2026-08-14): FHWC
    #     (Gamma < R; with mortality Gamma*L < R). Without finite human wealth
    #     the PF solution is c(w)=infinity for EVERY w (c = kappa*(w+h), h
    #     infinite) -- degenerate before any other condition can bite. Holds
    #     identically here (Gamma=1 < R), beta-independent => no beta cusp.
    # (1) Aggregate (BST eq:GICLivMod; Modigliani estate destruction, which is this
    #     model: estates die, newborns start at a=0). RAW GPF, no psi moment --
    #     idiosyncratic psi's wash out of Sum(M)/Sum(P) by LLN (the E[1/psi] term
    #     belongs to the MEAN INDIVIDUAL RATIO E[M/P], a different object):
    #         L*(R*beta)^(1/rho)/Gamma < 1   =>   beta_AGG = (Gamma/L)^rho / R
    # (2) Nondegeneracy: guarded by (0) FHWC and by RIC (the classic c->0
    #     degeneracy; beta_RIC = R^(rho-1)/L, slack above beta_AGG here; not
    #     coded). FVAC (beta_FVAC = Gamma^(rho-1)/(L*E[psi^(1-rho)]),
    #     E[psi^(1-rho)] = exp(sigma^2*rho*(rho-1)/2)) was briefly part of a
    #     min() criterion on 2026-08-14 and then DROPPED by owner ruling the
    #     same day: FHWC ^ GIC => FVAC without mortality (it could never bind);
    #     mortality's asymmetric relief (1/L^rho to the aggregate GIC vs 1/L to
    #     FVAC) opens a window (beta_FVAC, beta_AGG) where autarky VALUE
    #     diverges -- but that is a value-LEVEL statement invisible to Euler
    #     iteration; the optimal value stays finite there (income floor + RIC:
    #     fund PF-growth consumption from savings), welfare cells compare
    #     finite-episode differences, and an EGM probe at beta {1.0048, 1.0065,
    #     1.0075} is finite/monotone/continuous straight through the FVAC
    #     frontier. beta_FVAC stays in TAPER_CENSUS as a diagnostic only.
    # Derivation, numbers, probe, and scope:
    # conclusions_private/2026-08-14_gic-cap-min-fvac-aggregate.md (REVISED section)
    GICmaxBeta, _beta_FVAC, _beta_AGG = gic_taper_cap()   # single source; see gic_taper_cap()
    minBeta = MIN_BETA_ATOM
    _n_floored = 0
    if _STEP1_PARAM in ('theta', 'mixed'):
        # THETA: the arctan taper is SKIPPED. Under the theta map the top atom is
        # a_hi = cap_eff - exp(t_hi) < cap by construction, so no atom can reach the cap and
        # there is nothing to squash -- the saturation shelf and its tau knob are gone from
        # the search. Only the atom floor remains (see MIN_BETA_ATOM). Nominal == effective.
        # MIXED (owner probe 2026-08-19): same skip -- the cap is enforced by COBYQA's
        # nonlinear constraint beta + kappa*nabla <= cap_eff, plus the raw-cap penalty
        # guard in _find_Opt_mixed, so no above-cap atom ever reaches this point either.
        for thedf in range(TypeCount):
            if beta_set[thedf] < minBeta:
                beta_set[thedf] = minBeta
                _n_floored += 1
    else:
        for thedf in range(TypeCount):
            taper_threshold = TAPER_THRESHOLD
            if beta_set[thedf] > GICmaxBeta-taper_threshold:
                beta_set[thedf] = GICmaxBeta-taper_threshold + (np.arctan((beta_set[thedf] - GICmaxBeta + taper_threshold)/taper_threshold))*taper_threshold/np.pi*2
            elif beta_set[thedf] < minBeta:
                beta_set[thedf] = minBeta

    # BUG-060 aggregate-stationarity guard: verify GPF_out (= (R*beta)^(1/rho) * L *
    # E[1/psi] / Gamma_individual < 1) holds for every tapered atom, using the agent's
    # INDIVIDUAL PermGroFac (= 1.0 here). With the fix above this is satisfied with
    # margin; it still guards the HAFISCAL_STEP1_GIC_LEGACY=1 path (and any future
    # calibration change). Checks ONLY GPF_out (aggregate), not GPF_in (individual
    # target, intentionally allowed to exceed 1). Warn-once (never raise: the optimizer
    # explores extreme (center, spread) whose tapered top atom can approach the
    # aggregate-violating limit, and a hard assert would crash the search).
    _verify_gic_satisfied(beta_set, base_params, EstTypeList)

    # BUG-078 diagnostic: census of the discount-factor atoms against the GIC-taper
    # cap. z = (nominal - (GICmaxBeta - taper_threshold)) / taper_threshold with
    # taper_threshold = TAPER_THRESHOLD (module level, env-tunable, default
    # 0.01); the taper's slope d(effective)/
    # d(nominal) = (2/pi)/(1+z^2) (note the 2/pi: the slope is ~0.64 at the
    # zone edge, a kink), so z>0 means "inside the taper zone" and z>2 means
    # <13% responsiveness ("pinned" against the cap). Refreshed on every objective
    # evaluation; find_Opt re-evaluates at the optimum and prints the census there.
    global LAST_TAPER_CENSUS
    _z_taper = (_beta_set_nominal - (GICmaxBeta - TAPER_THRESHOLD)) / TAPER_THRESHOLD
    LAST_TAPER_CENSUS = {
        'GICmaxBeta': GICmaxBeta,
        'taper_threshold': TAPER_THRESHOLD,
        'beta_FVAC': _beta_FVAC,
        'beta_AGG': _beta_AGG,
        'nominal_atoms': [round(float(b), 6) for b in _beta_set_nominal],
        'effective_atoms': [round(float(b), 6) for b in beta_set],
        'z': [round(float(z), 3) for z in _z_taper],
        'n_in_taper': int((_z_taper > 0).sum()),
        'n_pinned': int((_z_taper > 2).sum()),
    }
    if _STEP1_PARAM in ('theta', 'mixed'):
        # theta/mixed diagnostics (the native census stays byte-identical): how far the top
        # NOMINAL atom sits below the raw cap, and whether the atom floor ever fired.
        LAST_TAPER_CENSUS['param_mode'] = _STEP1_PARAM
        LAST_TAPER_CENSUS['cap_margin_top'] = float(GICmaxBeta - float(np.max(_beta_set_nominal)))
        LAST_TAPER_CENSUS['n_floored'] = int(_n_floored)
    
      
    
    for j in range(TypeCount):
        EstTypeList[j].DiscFac = beta_set[j]
        # CDC-MOD-BUG035: set the current candidate ς on each agent so the
        # CDCKinkedRConsumerType.get_poststates override uses the right value.
        # Each evaluation of FagerengObjFunc tries a different SplurgeEstimate;
        # the agents' simulator dynamics must reflect the current candidate.
        EstTypeList[j].Splurge = SplurgeEstimate

    # Solve and simulate all consumer types, then gather their wealth levels
    # HARK 0.17.0: unpack_cFunc() no longer exists - cFunc is directly accessible from solution
    if os.environ.get('HAFISCAL_STEP1_FTI', '0') == '1' and fti_step1 is None:
        raise RuntimeError(
            "HAFISCAL_STEP1_FTI=1 but the fti_step1/hark_fti wiring failed to "
            "import — refusing to silently run EGM (owner ruling 2026-08-22: "
            "no soft-fallbacks on explicit FTI opt-ins).")
    if fti_step1 is not None and fti_step1.STEP1_FTI_ON:
        # Opt-in (HAFISCAL_STEP1_FTI=1): solve each type, transplant the FTI (NAM/ATI)
        # cFunc onto the KinkedR host, then simulate unchanged. The default path (flag
        # OFF, below) is byte-identical. See fti_step1.py + the external `hark_fti`
        # package (sibling fast-time-iteration repo; resolved via _hark_fti_path).
        # (Host-side powerlaw rewrap under the default happens INSIDE
        # solve_types_fti, keeping the graft comparison form-consistent — F7.)
        fti_step1.solve_types_fti(EstTypeList, base_params)
        _sim_burnin(EstTypeList)
    elif step1_powerlaw_tail is not None and step1_powerlaw_tail.powerlaw_form_active():
        # F7 default path: solve on the K·h̄ grid (applied to base_params at
        # module scope), rewrap each type's cFunc tail to the production
        # power-law measured-Q form, then simulate. Identical solved knots;
        # only above-grid extrapolation changes. See the F7 ruling block.
        multi_thread_commands(EstTypeList,['solve()'])
        step1_powerlaw_tail.maybe_rewrap_types(EstTypeList)
        _sim_burnin(EstTypeList)
    else:
        # Legacy tail (HAFISCAL_PF_DECAY_EXTRAP=exp/0): the pre-F7 path —
        # exp@20/legacy-count, byte-identical (single multi_thread_commands
        # call, no rewrap; the SST resolver left base_params untouched).
        multi_thread_commands(EstTypeList,['solve()'])
        _sim_burnin(EstTypeList)
    # Wealth read-out dispatched on HAFISCAL_INTERPRETATION (BUG-054 Option A,
    # 2026-07-27): CDC = `_wealth_under_cdc` splurge-in-budget shift; ESC =
    # `_wealth_under_esc` (1-ς)·aLvl (Edmund's convention). See
    # plans/20260425-2102h_cdc-implementation-map.md row 32.2.
    if _STEP1_ENGINE == 'tm' and _STEP1_WEALTH_FORM == 'dist':
        # STAGE B: wealth targets in DISTRIBUTION FORM from the joint-moment
        # ergodic (pi, g1, g2) — no panel exists. WealthNow (end-of-period
        # household assets in levels) IS the ergodic state, so Lorenz and K/Y
        # read off it directly; the same-atom (psi,xi) entanglement and the
        # newborn xi=1 convention are reproduced in compute_step1_wealth_targets.
        if not estimation_mode:
            raise RuntimeError(
                'HAFISCAL_STEP1_SIM_ENGINE=tm has no panel; plot/diagnostic '
                'runs (estimation_mode=False) need one — rerun with '
                'HAFISCAL_STEP1_SIM_ENGINE=tm_init or mc.')
        import sys as _s1w_sys
        _s1w_ham = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        if _s1w_ham not in _s1w_sys.path:
            _s1w_sys.path.insert(0, _s1w_ham)
        import step1_tm_targets as _s1w
        lorenz_Model, KY_Model = _s1w.compute_step1_wealth_targets(EstTypeList)
    else:
        WealthNow = np.concatenate([_wealth_actual(ThisType, SplurgeEstimate) for ThisType in EstTypeList])


        # Get wealth quartile cutoffs and distribute them to each consumer type
        quartile_cuts = get_percentiles(WealthNow,percentiles=[0.25,0.50,0.75])
        wealth_list = np.array([])
        for ThisType in EstTypeList:
            a_actual = _wealth_actual(ThisType, SplurgeEstimate)
            WealthQ = np.zeros(ThisType.AgentCount,dtype=int)
            for n in range(3):
                WealthQ[a_actual > quartile_cuts[n]] += 1
            ThisType.WealthQ = WealthQ
            wealth_list = np.concatenate((wealth_list, a_actual))
            

         
        # Get lorenz curve
        order = np.argsort(WealthNow)
        WealthNow_sorted = WealthNow[order]
        Lorenz_Data = get_lorenz_shares(WealthNow_sorted,percentiles=np.arange(0.01,1.00,0.01),presorted=True) 
        Lorenz_Data = np.hstack((np.array(0.0),Lorenz_Data,np.array(1.0))) 
        Wealth_adj = WealthNow_sorted - WealthNow_sorted[0] # add lowest possible value to everyone
        Lorenz_Data_Adj = get_lorenz_shares(Wealth_adj,percentiles=np.arange(0.01,1.00,0.01),presorted=True) 
        Lorenz_Data_Adj = np.hstack((np.array(0.0),Lorenz_Data_Adj,np.array(1.0))) 
        lorenz_Model = np.array([Lorenz_Data_Adj[20], Lorenz_Data_Adj[40], Lorenz_Data_Adj[60], Lorenz_Data_Adj[80]])
    
        # Get K to Y
        # implements (eq:KY-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
        # The K/Y aggregator is the second step of a two-step CDC pattern:
        #   step 1 (line ~244-248):  WealthNow = [_wealth_under_cdc(t, ς) for t in EstTypeList]
        #                            implements (eq:budget-CDC) rearranged for wealth
        #   step 2 (here):            CapAgg = Σ WealthNow ;  K/Y = CapAgg / Σ (pLvl·TranShk)
        #                            implements (eq:KY-CDC) — the K/Y aggregator under CDC
        # The interpretive choice (CDC vs ESC) is encapsulated in step 1; this sum
        # is then interpretation-agnostic (just summing whatever the chosen wealth
        # rule produced). See plans/20260425-2102h_cdc-implementation-map.md row 32.2.
        CapAgg      = np.sum(WealthNow)
        TransNow    = np.concatenate([ThisType.shocks["TranShk"] for ThisType in EstTypeList])
        permNow     = np.concatenate([ThisType.state_now["pLvl"] for ThisType in EstTypeList])
        IncAgg      = np.sum(permNow*TransNow)
        KY_Model    = CapAgg/IncAgg
    
################## Can return K/Y here
    if target != "Liqu_Wealth_plusKY":

        if _STEP1_ENGINE == 'tm':
            # STAGE B (owner 2026-07-27: all MC outside welfare GONE): fully
            # deterministic experiment -- two-arm TM propagation, exact average
            # over the four win-quarters, per-cell MPCs via cumulative operator
            # products, the panel's smoothed-ramp quartiles in distribution
            # form. See Code/HA-Models/step1_tm_targets.py.
            import sys as _s1b_sys
            _s1b_ham = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
            if _s1b_ham not in _s1b_sys.path:
                _s1b_sys.path.insert(0, _s1b_ham)
            import step1_tm_targets as _s1b
            N_Quarter_Sim = 20
            N_Year_Sim = int(N_Quarter_Sim/4)
            _res_tm = _s1b.compute_step1_experiment(
                EstTypeList, SplurgeEstimate, lottery_size[4],
                n_quarters=N_Quarter_Sim)
            simulated_MPC_mean_add_Lottery_Bin = _res_tm['agg_mpc_by_year']
            simulated_MPC_means_smoothed = _s1b.smoothed_quartile_means(
                _res_tm['cell_mpc_year1'], _res_tm['cell_weight'], _res_tm['cell_wealth'])
        else:
            N_Quarter_Sim = 20; # Needs to be dividable by four
            N_Year_Sim = int(N_Quarter_Sim/4)
            N_Lottery_Win_Sizes = 5 # 4 lottery size bin + 1 representative one for agg MPCX
    
        
            EmptyList = [[],[],[],[],[]]
            MPC_set_list = [deepcopy(EmptyList),deepcopy(EmptyList),deepcopy(EmptyList),deepcopy(EmptyList)]
            MPC_Lists    = [deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list)]    
            # additional list for 5th Lottery bin, just need for elements for four years
            MPC_List_Add_Lottery_Bin = EmptyList
        
            MPC_this_type = np.zeros((TypeCount, ThisType.AgentCount,N_Lottery_Win_Sizes,N_Year_Sim)) #Empty array, MPC for each Lottery size and agent
            
            for type_num, ThisType in zip(range(TypeCount), EstTypeList):
                # HARK 0.17.0: Reset simulation index to allow additional simulate() calls
                # The initial simulate() ran for T_sim periods; reset to allow MPC calculation
                ThisType.t_sim = 0
            
                c_base = np.zeros((ThisType.AgentCount,N_Quarter_Sim))                        #c_base (in case of no lottery win) for each quarter
                c_base_Lvl = np.zeros((ThisType.AgentCount,N_Quarter_Sim))                    #same in levels
                a_base = np.zeros((ThisType.AgentCount,N_Quarter_Sim))                        #a_base: splurge-in-budget-consistent baseline assets (no lottery ever)
                c_actu = np.zeros((ThisType.AgentCount,N_Quarter_Sim,N_Lottery_Win_Sizes))    #c_actu (actual consumption in case of lottery win in one random quarter) for each quarter and lottery size
                c_actu_Lvl = np.zeros((ThisType.AgentCount,N_Quarter_Sim,N_Lottery_Win_Sizes))#same in levels
                a_actu = np.zeros((ThisType.AgentCount,N_Quarter_Sim,N_Lottery_Win_Sizes))    #a_actu captures the actual market resources after potential lottery win (last index) was added and c_actu deducted
                T_hist = np.zeros((ThisType.AgentCount,N_Quarter_Sim))
                P_hist = np.zeros((ThisType.AgentCount,N_Quarter_Sim))
                
                # LotteryWin is an array with AgentCount x 4 periods many entries; there is only one 1 in each row indicating the quarter of the Lottery win for the agent in each row
                # This can be coded more efficiently
                LotteryWin = np.zeros((ThisType.AgentCount,N_Quarter_Sim))   
                for i in range(ThisType.AgentCount):
                    LotteryWin[i,random.randint(0,3)] = 1
                

                for period in range(N_Quarter_Sim): #Simulate for 4 quarters as opposed to 1 year
                
                    # Simulate forward for one quarter (draws shocks; HARK's internal asset
                    # update uses a = m - cFunc(m), which we ignore — splurge-in-budget requires us
                    # to track a_base and a_actu manually with a = m - c_actual.)
                    ThisType.simulate(1)

                    xi_hark = ThisType.shocks["TranShk"]
                    psi_hark = ThisType.shocks["PermShk"]
                    pLvl_now = ThisType.state_now["pLvl"]

                    k = 4; # do not loop to save time
                    Llvl = lottery_size[k]*LotteryWin[:,period]

                    if RandomLotteryWin and k == 5:
                        for i in range(ThisType.AgentCount):
                            Llvl[i] = lottery_size[random.randint(0,3)]*LotteryWin[i,period]
                            if LotteryWin[i,period]==1 and i==0:
                                print(Llvl[i])

                    Lnrm = Llvl/pLvl_now
                    TotIncNrm = xi_hark + Lnrm  # total income this period (splurge applies to all of it)

                    if period == 0:
                        # Period 0: initialize from HARK's post-init m (= a_initial*R/psi_0 + xi_0)
                        m_base = ThisType.state_now["mNrm"]
                        m_lottery = m_base + Lnrm
                    else:
                        T_hist[:,period] = xi_hark
                        P_hist[:,period] = psi_hark
                        # Death: reset both baseline and lottery-path a_prev for dead agents
                        for i_agent in range(ThisType.AgentCount):
                            if xi_hark[i_agent] == 1.0:
                                a_base[i_agent,period-1] = np.exp(base_params['kLogInitMean'])
                                a_actu[i_agent,period-1,k] = np.exp(base_params['kLogInitMean'])
                        R_kink_base = np.where(a_base[:,period-1] < 0, base_params['Rboro'], base_params['Rsave'])
                        R_kink_actu = np.where(a_actu[:,period-1,k] < 0, base_params['Rboro'], base_params['Rsave'])
                        m_base = a_base[:,period-1]*R_kink_base/psi_hark + xi_hark
                        m_lottery = a_actu[:,period-1,k]*R_kink_actu/psi_hark + xi_hark + Lnrm

                    # CDC-MOD-BUG032 [central anchor]. The lottery-MPC arithmetic
                    # dispatches on HAFISCAL_INTERPRETATION (BUG-054 Option A,
                    # 2026-07-27): CDC = household-blended asset budget; ESC =
                    # plain optimizer post-state. Consumption is the same total
                    # under both. See plans/20260425-2102h_cdc-implementation-map.md
                    # row 32.5 and BUGS_private/HAFiscal_BUG-032_lottery_splurge_formula.md.
                    cFunc = ThisType.solution[0].cFunc
                    c_base[:,period], a_base[:,period], c_actu[:,period,k], a_actu[:,period,k] = \
                        _lottery_consumption(cFunc, m_base, m_lottery, SplurgeEstimate, xi_hark, TotIncNrm)
                    c_base_Lvl[:,period] = c_base[:,period] * pLvl_now
                    c_actu_Lvl[:,period,k] = c_actu[:,period,k] * pLvl_now
                    
                    if period%4 + 1 == 4: #if we are in the 4th quarter of a year
                        year = int((period+1)/4)
                        c_actu_Lvl_year = c_actu_Lvl[:,(year-1)*4:year*4,k]
                        c_base_Lvl_year = c_base_Lvl[:,(year-1)*4:year*4]
                        MPC_this_type[type_num,:,k,year-1] = (np.sum(c_actu_Lvl_year,axis=1) - np.sum(c_base_Lvl_year,axis=1))/(lottery_size[k])
                        
            
                # Sort the MPCs into the proper MPC sets
                for q in range(4):
                    these = ThisType.WealthQ == q
                    for k in range(N_Lottery_Win_Sizes):
                        for y in range(N_Year_Sim):
                            MPC_Lists[k][q][y].append(MPC_this_type[type_num,these,k,y])
                        
                # sort MPCs for addtional Lottery bin
                for y in range(N_Year_Sim):
                    MPC_List_Add_Lottery_Bin[y].append(MPC_this_type[type_num,:,4,y])

                
            #Create a list of wealth and MPCs
            MPC_list = np.array([])
            for type_num, ThisType in zip(range(TypeCount), EstTypeList):
                MPC_list = np.concatenate((MPC_list, MPC_this_type[type_num, :, 4, 0] ))
            sorted_wealth_MPC = np.stack((wealth_list, MPC_list))[:,wealth_list.argsort()]
            total_agents = len(MPC_list)
            quartile1_weights = np.zeros(total_agents)
            quartile1_weights[0:int(np.floor(total_agents*9/40))] = 1.0
            quartile1_slope_length = (int(np.floor(total_agents*11/40)-np.floor(total_agents*9/40)))
            quartile1_weights[int(np.floor(total_agents*9/40)):int(np.floor(total_agents*11/40))] = (quartile1_slope_length-np.arange(quartile1_slope_length))/quartile1_slope_length
            quartile2_weights = np.zeros(total_agents)
            quartile2_weights[0:int(np.floor(total_agents*19/40))] = 1- quartile1_weights[0:int(np.floor(total_agents*19/40))]
            quartile2_slope_length = (int(np.floor(total_agents*21/40)-np.floor(total_agents*19/40)))
            quartile2_weights[int(np.floor(total_agents*19/40)):int(np.floor(total_agents*21/40))] = (quartile2_slope_length-np.arange(quartile2_slope_length))/quartile2_slope_length
            quartile3_weights = np.flip(quartile2_weights)
            quartile4_weights = np.flip(quartile1_weights)
            simulated_MPC_means_smoothed = np.zeros(4)
            simulated_MPC_means_smoothed[0] = np.average(sorted_wealth_MPC[1],weights=quartile1_weights)
            simulated_MPC_means_smoothed[1] = np.average(sorted_wealth_MPC[1],weights=quartile2_weights)
            simulated_MPC_means_smoothed[2] = np.average(sorted_wealth_MPC[1],weights=quartile3_weights)
            simulated_MPC_means_smoothed[3] = np.average(sorted_wealth_MPC[1],weights=quartile4_weights)
        
            #if estimation_mode==False or target == 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC':     
            # Calculate average within each MPC set
            simulated_MPC_means = np.zeros((N_Lottery_Win_Sizes,4,N_Year_Sim))
            for k in range(N_Lottery_Win_Sizes):
                for q in range(4):
                    for y in range(N_Year_Sim):
                        MPC_array = np.concatenate(MPC_Lists[k][q][y])
                        simulated_MPC_means[k,q,y] = np.mean(MPC_array)
                    
            # Calculate aggregate MPC and MPCx
            simulated_MPC_mean_add_Lottery_Bin = np.zeros((N_Year_Sim))
            for y in range(N_Year_Sim):
                MPC_array = np.concatenate(MPC_List_Add_Lottery_Bin[y])
                simulated_MPC_mean_add_Lottery_Bin[y] = np.mean(MPC_array)
                
        # Calculate Euclidean distance between simulated MPC averages and Table 9 targets
        
       
        # MPC for representative lottery win (k=4), which corresponds to third row in MPC_target
        diff_MPC = simulated_MPC_means_smoothed - MPC_target[2,:] 
        distance_MPC = 0.1*np.sum((diff_MPC)**2) 
          
        diff_Agg_MPC = simulated_MPC_mean_add_Lottery_Bin - Agg_MPCX_target
        distance_Agg_MPC = np.sum((diff_Agg_MPC)**2)     
        distance_Agg_MPC_24 = np.sum((diff_Agg_MPC[2:4])**2)
        distance_Agg_MPC_01 = np.sum((diff_Agg_MPC[0:1])**2)
    else:
        distance_MPC = 0
        diff_Agg_MPC = 0
        distance_Agg_MPC = 0
        distance_Agg_MPC_24 = 0
        distance_Agg_MPC_01 = 0
        simulated_MPC_means = 0
        simulated_MPC_mean_add_Lottery_Bin = 0
        c_actu_Lvl = 0
        c_base_Lvl = 0
        LotteryWin = 0
        
        
        
    diff_lorenz = lorenz_Model - lorenz_target
    distance_lorenz = np.sum((diff_lorenz)**2)
    
    distance_KY = 1.0*((KY_target - KY_Model)/KY_target)**2 
    

    if target == 'MPC':
        distance = distance_MPC + distance_Agg_MPC
    elif target == 'AGG_MPC':
        distance = distance_Agg_MPC
    elif target == 'AGG_MPC_234':
        distance = distance_Agg_MPC_24
    elif target == 'MPC_plus_AGG_MPC_1':
        distance = distance_MPC + distance_Agg_MPC_01
    elif target == 'AGG_MPC_plus_Liqu_Wealth':
        distance = distance_Agg_MPC + distance_lorenz
    elif target == 'AGG_MPC_plus_Liqu_Wealth_plusKY':
        distance = distance_Agg_MPC + distance_lorenz + distance_KY
    elif target == 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC':
        distance = distance_MPC + distance_Agg_MPC + distance_lorenz + distance_KY
    elif target == "Liqu_Wealth_plusKY":
        distance = distance_lorenz + distance_KY
    elif target == "test":
        distance = distance_MPC
        
    if estimation_mode==False:   
        print(distance_Agg_MPC,distance_lorenz,distance_KY)
        
    if verbose:
        print(simulated_MPC_means)
        print(simulated_MPC_means_smoothed)
    else:
        print (SplurgeEstimate, center, spread, distance)
        
    if investigate:
        print("distance_MPC", distance_MPC) 
        print("distance_Agg_MPC", distance_Agg_MPC)
        print("distance_lorenz", distance_lorenz)
        print("distance_KY", distance_KY)
        print (beta_set)
        
    if investigate:
        # Per-DF-group K/Y for diagnostic printing. Note: this sums HARK's
        # raw aLvl (no splurge-in-budget correction), unlike the production
        # K/Y at line ~303 which sums the CDC-corrected WealthNow. The
        # two will differ by ~ς·(y - cFunc) per agent; for whole-population
        # comparisons use the production CapAgg/IncAgg instead. (Investigate
        # is debug-only; not load-bearing for the published estimation.)
        for j in range(TypeCount):
            CapAggj = np.sum(EstTypeList[j].state_now["aLvl"])
            permNowj = EstTypeList[j].state_now["pLvl"]
            TransNowj = EstTypeList[j].shocks["TranShk"]
            KY_Modelj = CapAggj/np.sum(permNowj*TransNowj)
            print("K/Y for DF group ", str(j), ": ",  KY_Modelj)
        print("K/Y for whole pop : ",  KY_Model)
        print("")
        
    if estimation_mode:
        return distance
    else:
        Output = dict()
        Output['distance'] = distance
        Output['distance_MPC'] = distance_MPC
        Output['distance_Agg_MPC'] = distance_Agg_MPC
        Output['distance_lorenz'] = distance_lorenz
        Output['distance_KY'] = distance_KY
        Output['simulated_MPC_means_smoothed'] = simulated_MPC_means_smoothed
        Output['simulated_MPC_mean_add_Lottery_Bin'] = simulated_MPC_mean_add_Lottery_Bin
        Output['c_actu_Lvl'] = c_actu_Lvl
        Output['c_base_Lvl'] = c_base_Lvl
        Output['LotteryWin'] = LotteryWin
        Output['Lorenz_Data'] = Lorenz_Data
        Output['Lorenz_Data_Adj'] = Lorenz_Data_Adj
        Output['KY_Model'] = KY_Model
        return Output


def save_betanabla_res_txt(filename,res):
    with open(Abs_Path+filename, 'w') as f:
        str1 = repr(res)
        f.write(str1)
        f.close
        
def load_betanabla_res_txt(filename):
    f = open(Abs_Path+filename, 'r')
    if f.mode=='r':
        contents= f.read()
    dictload= eval(contents)
    splurge = dictload['splurge']
    beta    = dictload['beta']
    nabla   = dictload['nabla']
    return [splurge,beta,nabla]


_POWELL_TOL_ANNOUNCED = False


def powell_minimize(fun, x0, bounds, restart_at_best=False):
    """SINGLE SOURCE OF TRUTH for every Step-1 Powell solve.

    bounds: the scipy bounds list on the NATIVE path, None on the unbounded theta path
    (HAFISCAL_STEP1_PARAM=theta, 2026-08-18), or the theta search box
    (HAFISCAL_STEP1_THETA_BOX=1). NOTE scipy uses a
    different scalar line-search routine when bounds is None (_minimize_scalar_brent,
    relative tol) than when it is not (_minimize_scalar_bounded, absolute xatol), so the
    xtol below does not mean the same thing on the two paths; see the reparameterization
    plan §7a F1 and its P4 (tolerance re-derivation).

    restart_at_best (fix (c), owner ruling 2026-08-19): scipy Powell's outer stopping test
    is SIGNED -- `2(fx - fval) <= ftol(|fx|+|fval|) + 1e-20` -- so an iteration that ends
    net-WORSE than it started (negative LHS) passes the test at ANY ftol. Under bounds
    that happens: `_minimize_scalar_bounded` samples its whole segment and may return a
    point worse than the incumbent. Run 10 seed 8 (thetabox, ftol=1e-6) was mid-ESCAPE
    from the splurge=0 basin -- best evaluated f=0.0158, well below that basin's minimum
    0.0807 -- when one regressing line search (-> f=0.1166) ended its iteration net-worse
    and scipy declared "Optimization terminated successfully"; the exact ftol replay shows
    the stop is invariant from 3e-6 to 1e-8 (run-10 gate report, post-hoc section). No
    tolerance reaches this defect, so it is repaired structurally: when the TERMINAL point
    is worse than the best point actually evaluated by more than the stop test's own
    resolution -- `2(f_term - f_best) > ftol(|f_term|+|f_best|) + 1e-20`, i.e. exactly the
    signature that the stop was a spurious regression stop rather than convergence --
    restart Powell FROM the best point with a fresh (identity) direction set, up to
    HAFISCAL_STEP1_RESTART_MAX times (default 2). On a clean stop (terminal ~ best within
    tolerance resolution, true of every modal run-9/10 seed) this is a pure no-op: zero
    extra evaluations, byte-identical results. Callers opt in per call site (the theta
    paths pass restart_at_best=(box is not None), because the box's bounded line searches
    are what create the exposure); HAFISCAL_STEP1_RESTART_AT_BEST=0|1 force-overrides, and
    the LEGACY tolerance path never restarts (its byte-exact reproduction promise wins).
    A restarted trace is NOT one Powell run: s1_ftol_replay.py cannot replay across the
    printed RESTART_AT_BEST marker lines.

    Every bounded-Powell minimisation in this file routes through here, so the convergence
    policy is defined ONCE. Before 2026-08-18 the tolerances lived nowhere -- each call site
    passed none, silently inheriting scipy's defaults -- and when the Step-1 estimator was
    fixed, `find_Opt_splurge0` (the Step-3 Splurge=0 arm) would have been left on the old
    behaviour, so the two arms would have been solved to different standards without
    anything saying so. That is the duplication this function exists to prevent.

    DEFAULTS: xtol=1e-6 (owner ruling 2026-08-18 morning) and ftol=1e-5 (owner ruling
    2026-08-18 evening; 1e-8 from the morning until then), replacing scipy's 1e-4/1e-4.
    THIS CHANGES ESTIMATES vs scipy's defaults. Adopted because scipy's RELATIVE per-cycle
    stopping test was terminating the optimizer far from the optimum on this walled, rugged
    objective, and the resulting endpoints were being recorded as genuine "off-basin"
    answers. Proven by a controlled A/B in which the ONLY difference was these two numbers:

        same seed, scipy defaults :  170 evals -> 0.21051/0.96099/0.05057  f=0.0049430
        same seed, tight          : 1042 evals -> 0.29985/0.97952/0.02939  f=0.0016469
        independent seed, other machine and architecture, for reference:
                                    1043 evals -> 0.29985/0.97951/0.02941  f=0.0016470

    Treatment and control agree to 0.0000% in splurge, 0.0010% in beta, 0.068% in nabla and
    0.0061% in f. The "recurring off-basin attractor" near (0.21, 0.963, 0.05), catalogued
    three times across runs 4, 5 and the tau probe, was never a feature of the objective --
    it was where Powell quit.

    COST is asymmetric, which is what makes it affordable: ~6.1x for a seed that had been
    stopping prematurely, ~1.24x for one that had already converged. The multiplier is
    large only where it buys a correct answer.

    ftol=1e-5 (not 1e-8) -- DERIVED, NOT GUESSED (2026-08-18 evening). ftol enters scipy's
    Powell ONLY in the outer stopping test, so for a fixed xtol the trajectory is identical
    for every ftol up to the stop. Replaying run 7's eight recorded traces through scipy
    (Code/HA-Models/coldrun/s1_ftol_replay.py; every proposed x asserted against the
    recorded x, 0 mismatches) gives the EXACT stop for each candidate:
        ftol 1e-8 -> 10,511 evals total; 1e-5 -> 9,497 (-9.6%), endpoints identical on 5
        of 8 seeds and within 1.4 sd of the inter-seed scatter on the rest;
        1e-4 (scipy's default) -> seed 2 stops at 279 evals on a taper-shelf plateau,
        3041 sd from the answer, and seeds 3/6 drift 3-4 sd.
    So the safe range is ftol <= 3e-5 and 1e-5 carries a 3x margin; the 1e-8 tail was 1-2
    Powell iterations per seed spent below the objective's own noise floor (the terminal
    iteration usually made f slightly WORSE -- the BEST_SO_FAR wrapper below is what
    rescued those). xtol CANNOT be derived by replay (it changes the trajectory) and stays
    at its ruled value pending a real A/B.

    HAFISCAL_STEP1_TOL_LEGACY=1 restores the pre-2026-08-18 behaviour verbatim (no options
    passed) for byte-exact reproduction of runs 1-5 and every anchor of record, all
    computed under scipy's defaults. HAFISCAL_STEP1_FTOL=1e-8 reproduces runs 6-7 and V1.

    Not routed through here: the one L-BFGS-B call in find_Opt_splurge0's check_maximum
    diagnostic -- a different solver with a different option vocabulary. Flagged rather
    than silently folded in.
    """
    global _POWELL_TOL_ANNOUNCED

    # BEST-SO-FAR (owner ruling 2026-08-18). scipy returns the optimizer's TERMINAL point,
    # which on a bounded, clipped objective need not be the best point it evaluated: 7 of
    # 26 run-4 seeds ended ABOVE their own best evaluation -- trivially for healthy seeds
    # (+0.01 to +0.11%) but grossly for failed ones (seed 16 reported f=1.383 having
    # visited 0.224; seeds 9 and 18 reported ~1.22 having visited ~0.232). Recording a
    # straggler as worse than it actually was distorts both the gate's kill decisions and
    # any landscape read taken from endpoints. So wrap the objective, remember the best
    # (x, f) actually seen, and return THAT when it beats the terminal point.
    _best = {'f': float('inf'), 'x': None}

    def _recording(x):
        v = fun(x)
        if v < _best['f']:
            _best['f'] = v
            _best['x'] = np.array(x, dtype=float).copy()
        return v

    if os.environ.get('HAFISCAL_STEP1_TOL_LEGACY', '0') == '1':
        if not _POWELL_TOL_ANNOUNCED:
            print("POWELL_TOL: LEGACY (scipy defaults, pre-2026-08-18)")
            _POWELL_TOL_ANNOUNCED = True
        out = minimize(_recording, x0, method="Powell", bounds=bounds)
    else:
        # Runaway guard. Tight tolerances remove the premature-stop failure but leave no
        # upper bound, so one pathological seed could stall a battery indefinitely. 3000 is
        # ~3x the observed converged cost (1052 and 1177 evals on the two A/B arms), so it
        # cannot truncate a normal solve; hitting it is a loud signal, not a silent cap.
        opts = {'xtol': float(os.environ.get('HAFISCAL_STEP1_XTOL', '1e-6')),
                'ftol': float(os.environ.get('HAFISCAL_STEP1_FTOL', '1e-5')),
                'maxfev': int(os.environ.get('HAFISCAL_STEP1_MAXFEV', '3000'))}
        # fix (c): env force-override ('1'/'0'); 'auto' (default) honors the call site.
        _rab_env = os.environ.get('HAFISCAL_STEP1_RESTART_AT_BEST', 'auto')
        _rab = {'1': True, '0': False}.get(_rab_env, bool(restart_at_best))
        _max_restarts = int(os.environ.get('HAFISCAL_STEP1_RESTART_MAX', '2')) if _rab else 0
        if not _POWELL_TOL_ANNOUNCED:
            print("POWELL_TOL:", opts, " RESTART_AT_BEST=%s (this call: %s, max %d)"
                  % (_rab_env, _rab, _max_restarts))
            _POWELL_TOL_ANNOUNCED = True
        _x0 = x0
        _restarts = 0
        while True:
            out = minimize(_recording, _x0, method="Powell", bounds=bounds, options=opts)
            _nfev_leg = getattr(out, 'nfev', None)
            if _nfev_leg is not None and _nfev_leg >= opts['maxfev']:
                break  # non-converged leg (MAXFEV_HIT prints below); do not chain restarts onto it
            if _restarts >= _max_restarts or _best['x'] is None:
                break
            _f_term = float(out.fun)
            _f_best = _best['f']
            # The trigger IS the stop test's own bound applied to (terminal, best): if the
            # terminal point is worse than an already-evaluated point by more than the
            # resolution ftol claims to certify, the stop was a regression stop, not
            # convergence. Clean stops (terminal ~ best) never trigger.
            if not (2.0 * (_f_term - _f_best) > opts['ftol'] * (abs(_f_term) + abs(_f_best)) + 1e-20):
                break
            _restarts += 1
            print("RESTART_AT_BEST %d/%d: spurious regression stop (terminal f=%.10g vs "
                  "best evaluated f=%.10g, terminal %.4g%% worse); restarting Powell from "
                  "the best point with a fresh direction set"
                  % (_restarts, _max_restarts, _f_term, _f_best,
                     (100.0 * (_f_term / _f_best - 1.0)) if _f_best > 0.0 else float('inf')))
            _x0 = _best['x'].copy()

    _nfev = getattr(out, 'nfev', None)
    _cap = int(os.environ.get('HAFISCAL_STEP1_MAXFEV', '3000'))
    if _nfev is not None and _nfev >= _cap:
        print("MAXFEV_HIT: solve stopped at the %d-evaluation guard rather than by "
              "convergence -- this endpoint is NOT converged and must not be treated as "
              "one. status=%r" % (_cap, getattr(out, 'status', None)))
    if _best['x'] is not None and _best['f'] < out.fun:
        # guard the ratio: f is a distance metric and should never be exactly 0, but a
        # divide-by-zero here would abort a multi-hour battery for a log line
        _pct = (100.0 * (out.fun / _best['f'] - 1.0)) if _best['f'] > 0.0 else float('inf')
        print("BEST_SO_FAR: returning the best point visited, f=%.10g, instead of the "
              "terminal point f=%.10g (terminal was %.4g%% worse)"
              % (_best['f'], out.fun, _pct))
        out.x = _best['x']
        out.fun = _best['f']
    return out


def _find_Opt_theta(target, startpoint, check_maximum):
    """theta-space twin of find_Opt (HAFISCAL_STEP1_PARAM=theta; owner rulings 2026-08-18).

    Same objective, same startpoint (given in NATIVE units and mapped here), same
    powell_minimize SST and tolerances -- the ONLY differences are (i) Powell walks theta
    in R^3 with NO bounds, and (ii) FagerengObjFunc skips the taper (nothing can reach the
    cap). Because bounds=None, scipy also switches its per-direction line search from
    _minimize_scalar_bounded (absolute xatol) to _minimize_scalar_brent (relative tol) --
    plan §7a F1 -- so eval counts are NOT comparable with native as a measure of the map.

    Everything printed stays in native units so the gate / s1_progress.sh parse unchanged;
    the theta coordinates are printed as extra lines.

    check_maximum: kept NATIVE (bounded Powell over (splurge, nabla) at fixed beta), plan
    §7a F3 -- with beta fixed the top atom is not the free coordinate, so the cap is not
    structural in that sub-problem under this map. It is a diagnostic, off by default.
    """
    GICmaxBeta, _fv, _ag = gic_taper_cap()
    kappa = top_atom_offset()
    _announce_param(GICmaxBeta, kappa)
    theta0 = _s1param.to_theta(startpoint[0], startpoint[1], startpoint[2],
                               cap=GICmaxBeta, kappa=kappa)
    print("Theta startpoint: ", [float(t) for t in theta0],
          " (cap=%r kappa=%r cap_eff=%r)" % (GICmaxBeta, kappa, _s1param.cap_eff(GICmaxBeta)))

    def f_theta(th):
        _s, _b, _n = _s1param.to_native(th, cap=GICmaxBeta, kappa=kappa)
        return FagerengObjFunc(_s, _b, _n, target=target)

    # V4 (2026-08-18 night) showed unbounded Brent falling into the splurge=0 saturated
    # asymptote from every k=0.90 seed; HAFISCAL_STEP1_THETA_BOX=1 restores the bounded,
    # globally-sampling line search inside a theta box whose floors are still responsive
    # (see step1_param.theta_box). Default OFF so V4's configuration stays reproducible.
    _box = _s1param.theta_box(cap=GICmaxBeta, kappa=kappa) if _s1param.theta_box_enabled() else None
    print("THETA_BOX: " + ("ON " + repr(_box) if _box is not None else "off (unbounded Brent line searches)"))
    # fix (c) rides with the box: bounded (fminbound) line searches are what create the
    # regression-stop exposure; the unbounded V4 configuration stays byte-reproducible.
    opt_output = powell_minimize(f_theta, theta0, _box, restart_at_best=(_box is not None))
    theta_opt = np.asarray(opt_output.x, dtype=float)
    obs = opt_output.fun
    splurge, beta, nabla = _s1param.to_native(theta_opt, cap=GICmaxBeta, kappa=kappa)
    print('Finished estimating')
    print('Optimal splurge is ' + str(splurge))
    print('Optimal (beta,nabla) is ' + str(beta) + ',' + str(nabla))
    print('Optimal theta is ' + str([float(t) for t in theta_opt])
          + '   cap margin (cap - top atom) = '
          + repr(_s1param.cap_margin(beta, nabla, cap=GICmaxBeta, kappa=kappa)))
    # re-evaluate at the optimum so the census (and the log's last eval line) is AT it,
    # exactly as native does with f_temp(opt)
    FagerengObjFunc(splurge, beta, nabla, target=target)
    if LAST_TAPER_CENSUS is not None:
        print('TAPER_CENSUS at optimum: ' + str(LAST_TAPER_CENSUS))
    if check_maximum:
        print("check_maximum: NATIVE bounded sub-search at fixed beta (plan §7a F3)")
        check_start = [splurge, nabla]
        check_obs = [0.0, 0.0]
        for i, deviation in zip(range(2), [-0.0001, 0.0001]):
            f_chk = lambda y: FagerengObjFunc(y[0], beta + deviation, y[1], target=target)
            check_opt = powell_minimize(f_chk, check_start, [(0.0, 0.9), (0.0, 0.4)])
            check_obs[i] = check_opt.fun
        print("Objective around minimum:")
        print([check_obs[0], obs, check_obs[1]])
        if check_obs[0] < obs or check_obs[1] < obs:
            print("Didn't find minimum - check what is going on")
            return {'splurge': splurge, 'beta': beta, 'nabla': nabla, 'Error': 'Not a maximum'}
        else:
            print("Local minimum check passed")
    return {'splurge': splurge, 'beta': beta, 'nabla': nabla, 'fval': float(obs)}


_COBYQA_ANNOUNCED = False


def cobyqa_minimize(fun, x0, bounds, constraints):
    """SST for the 'mixed' probe's COBYQA solves (owner design 2026-08-19).

    Trust-region SQP on quadratic interpolation models (scipy >= 1.14, method='cobyqa').
    BOUNDS are honored at EVERY evaluation (so splurge=0 is reachable and evaluable --
    the point of the probe); NONLINEAR constraints are enforced to tolerance at the
    solution, with transient trial-point violations absorbed by the CAP_EPS margin and,
    beyond the raw cap, by the mixed_penalty guard in the objective. maxfev shares
    HAFISCAL_STEP1_MAXFEV (3000); other knobs stay at COBYQA defaults for the probe --
    deliberately un-tuned, so the comparison against Powell is defaults-vs-ruled-tols
    and any COBYQA win is an underestimate. BEST_SO_FAR reporting mirrors
    powell_minimize (diagnostic; TR methods should terminate at their best feasible
    point, so a triggered report is itself a finding)."""
    global _COBYQA_ANNOUNCED
    _best = {'f': float('inf'), 'x': None}

    def _recording(x):
        v = fun(x)
        if v < _best['f']:
            _best['f'] = v
            _best['x'] = np.array(x, dtype=float).copy()
        return v

    _maxfev = int(os.environ.get('HAFISCAL_STEP1_MAXFEV', '3000'))
    _opts = {'maxfev': _maxfev}
    # HAFISCAL_STEP1_COBYQA_FINAL_TR: the final trust-region radius -- COBYQA's
    # "accuracy required in the final solution". DEFAULT = 1e-8, the run-13-validated
    # setting adopted with the engine (owner ruling 2026-08-19 evening): on scipy's own
    # default the run-12 probes stopped +0.06-0.09% above f*; at 1e-8 seven of eight
    # battery seeds landed SoR-class for ~+33% evals. The literal value 'scipy' omits
    # the option (scipy's default -- reproduces the run-12 probes).
    _ftr = os.environ.get('HAFISCAL_STEP1_COBYQA_FINAL_TR', '1e-8').strip()
    if _ftr and _ftr.lower() != 'scipy':
        _opts['final_tr_radius'] = float(_ftr)
    if not _COBYQA_ANNOUNCED:
        print("COBYQA_OPTS:", _opts, "(unlisted knobs scipy/COBYQA defaults)")
        _COBYQA_ANNOUNCED = True
    out = minimize(_recording, x0, method="cobyqa", bounds=bounds,
                   constraints=constraints, options=_opts)
    _nfev = getattr(out, 'nfev', None)
    if _nfev is not None and _nfev >= _maxfev:
        print("MAXFEV_HIT: solve stopped at the %d-evaluation guard rather than by "
              "convergence -- this endpoint is NOT converged and must not be treated as "
              "one. status=%r" % (_maxfev, getattr(out, 'status', None)))
    if _best['x'] is not None and _best['f'] < out.fun:
        _pct = (100.0 * (out.fun / _best['f'] - 1.0)) if _best['f'] > 0.0 else float('inf')
        print("BEST_SO_FAR: returning the best point visited, f=%.10g, instead of the "
              "terminal point f=%.10g (terminal was %.4g%% worse)"
              % (_best['f'], out.fun, _pct))
        out.x = _best['x']
        out.fun = _best['f']
    return out


def _find_Opt_mixed(target, startpoint, check_maximum):
    """'mixed' = the level-splurge COBYQA probe (owner spec 2026-08-19, refined same
    afternoon): ONLY the splurge coordinate changes -- LEVELS with hard bounds
    [0.0, 0.9], zero included, honored by COBYQA at every evaluation. beta and nabla
    keep their theta forms (a_hi = cap_eff - exp(t_hi), nabla = exp(t_w)), so the
    finite-ergodic-wealth cap stays STRUCTURAL in the map -- no optimizer constraint
    is used (COBYQA's capability to carry the cap as a nonlinear constraint is
    verified in test_step1_mixed_cobyqa.py but deliberately not exercised here).

    PURPOSE: separate "seed 7 finds a TRUE basin at splurge~0" from "the failure is a
    search-procedure artifact". In levels the solver can converge ON the splurge=0 face
    and report it as an active bound (a genuine KKT point of the underlying problem) --
    or lift off it, indicting the procedure. The logit map could never distinguish
    these (splurge=0 sits at t_s = -inf; the theta box could only truncate at 1e-4)."""
    GICmaxBeta, _fv, _ag = gic_taper_cap()
    kappa = top_atom_offset()
    _announce_param(GICmaxBeta, kappa)
    x0 = _s1param.to_mixed(startpoint[0], startpoint[1], startpoint[2],
                           cap=GICmaxBeta, kappa=kappa)
    print("Mixed startpoint (splurge, t_hi, t_w): ", [float(v) for v in x0])

    def f_mixed(x):
        _s, _b, _n = _s1param.from_mixed(x, cap=GICmaxBeta, kappa=kappa)
        return FagerengObjFunc(_s, _b, _n, target=target)

    _bounds = _s1param.mixed_bounds(cap=GICmaxBeta, kappa=kappa)
    print("MIXED_BOUNDS (splurge LEVELS [0,0.9]; t_hi, t_w = theta box):", _bounds)
    opt_output = cobyqa_minimize(f_mixed, x0, _bounds, [])
    splurge, beta, nabla = _s1param.from_mixed(np.asarray(opt_output.x, dtype=float),
                                               cap=GICmaxBeta, kappa=kappa)
    obs = opt_output.fun
    print('Finished estimating')
    print('Optimal splurge is ' + str(splurge)
          + ('   [AT the splurge>=0 bound]' if splurge <= 1e-12 else ''))
    print('Optimal (beta,nabla) is ' + str(beta) + ',' + str(nabla))
    print('Cap slack at optimum (cap_eff - top atom) = '
          + repr(_s1param.cap_eff(GICmaxBeta) - (beta + kappa * nabla))
          + '   raw-cap margin = ' + repr(_s1param.cap_margin(beta, nabla, cap=GICmaxBeta, kappa=kappa)))
    # re-evaluate at the optimum so the census (and the log's last eval line) is AT it
    FagerengObjFunc(splurge, beta, nabla, target=target)
    if LAST_TAPER_CENSUS is not None:
        print('TAPER_CENSUS at optimum: ' + str(LAST_TAPER_CENSUS))
    if check_maximum:
        print("check_maximum: NATIVE bounded sub-search at fixed beta (as in theta mode)")
        check_start = [splurge, nabla]
        check_obs = [0.0, 0.0]
        for i, deviation in zip(range(2), [-0.0001, 0.0001]):
            f_chk = lambda y: FagerengObjFunc(y[0], beta + deviation, y[1], target=target)
            check_opt = powell_minimize(f_chk, check_start, [(0.0, 0.9), (0.0, 0.4)])
            check_obs[i] = check_opt.fun
        print("Objective around minimum:")
        print([check_obs[0], obs, check_obs[1]])
        if check_obs[0] < obs or check_obs[1] < obs:
            print("Didn't find minimum - check what is going on")
            return {'splurge': splurge, 'beta': beta, 'nabla': nabla, 'Error': 'Not a maximum'}
        else:
            print("Local minimum check passed")
    return {'splurge': splurge, 'beta': beta, 'nabla': nabla, 'fval': float(obs)}


def find_Opt(target='', startpoint = [0.27,0.96,0.03], check_maximum = False):
    if _STEP1_PARAM == 'theta':
        return _find_Opt_theta(target, startpoint, check_maximum)
    if _STEP1_PARAM == 'mixed':
        return _find_Opt_mixed(target, startpoint, check_maximum)
    _announce_param(gic_taper_cap()[0], top_atom_offset())
    
    bounds = [(0.0,0.9),(0.7,1.1),(0.0,0.4)]
        
    f_temp = lambda x : FagerengObjFunc(x[0],x[1],x[2],target=target)
    #opt = minimizeNelderMead(f_temp, startpoint2, verbose=1, xtol=0.001, ftol=0.001)
    # Powell tolerances: set by the powell_minimize SST -- xtol=1e-6, ftol=1e-8 since the
    # owner ruling of 2026-08-18, NOT scipy's 1e-4/1e-4 defaults. (This comment asserted the
    # opposite until 2026-08-18. Runs 1-5 and every anchor of record predate the ruling and
    # were computed under scipy's defaults; HAFISCAL_STEP1_TOL_LEGACY=1 restores them.)
    #
    # WHY THIS HOOK EXISTS. Across runs 4-6 the endpoint quality separates by EVAL COUNT
    # with no overlap: seeds that reached the floor used 486-1362 evals (n=15, mean 797),
    # while every "off-basin" endpoint used 268-364 (n=3, mean 308) -- plus run 5's
    # off-basin seed at 364 and the tau=0.002 probe's off-basin arm at 170, against that
    # probe's floor-reaching arm at 840. Powell's stopping test is a RELATIVE per-cycle
    # improvement of ftol=1e-4; on this walled, rugged objective a cycle can fail to beat
    # that while still far from the optimum. SETTLED 2026-08-18 by the controlled A/B in
    # powell_minimize: the recurring "off-basin attractor" near (0.21, 0.963, 0.05) was
    # never an attractor -- it was premature termination. Tightening converts stragglers
    # into good seeds, and the gate's kill rule had been discarding recoverable runs.
    opt_output = powell_minimize(f_temp, startpoint, bounds)
    opt = opt_output.x
    obs = opt_output.fun
    beta = opt[1]
    nabla = opt[2]
    print('Finished estimating')
    print('Optimal splurge is ' + str(opt[0]) )
    print('Optimal (beta,nabla) is ' + str(beta) + ',' + str(nabla))

    # BUG-078: one extra objective evaluation AT the optimum refreshes the
    # module-level census so it reports the atoms of the reported optimum
    # (Powell's last internal eval need not be the returned point).
    f_temp(opt)
    if LAST_TAPER_CENSUS is not None:
        print('TAPER_CENSUS at optimum: ' + str(LAST_TAPER_CENSUS))

    if check_maximum:
        check_start = [opt[0],opt[2]]
        check_obs = [0.0, 0.0]
        for i,deviation in zip(range(2), [-0.0001, 0.0001]):
            f_temp = lambda y : FagerengObjFunc(y[0],opt[1]+deviation,y[1],target=target)
            check_opt = powell_minimize(f_temp, check_start, [(0.0,0.9),(0.0,0.4)])
            check_obs[i] = check_opt.fun
        print("Objective around minimum:")
        print([check_obs[0], obs, check_obs[1]])
        if check_obs[0]<obs or check_obs[1] < obs :
            print("Didn't find minimum - check what is going on")
            return {'splurge' : opt[0], 'beta' : beta, 'nabla': nabla, 'Error': 'Not a maximum'}
        else:
            print("Local minimum check passed")
    
    return {'splurge' : opt[0], 'beta' : beta, 'nabla': nabla, 'fval': float(obs)}

def find_Opt_splurge0(target='', startpoint = [0.96,0.03], check_maximum = False):
    if _STEP1_PARAM == 'mixed':
        # 2-D mixed twin (consistency with _find_Opt_mixed): splurge stays a LITERAL 0;
        # (beta, nabla) keep their theta forms, searched by COBYQA inside the theta box's
        # own (t_hi, t_w) components. Not part of the 2026-08-19 probe's scope but wired
        # so a full 'mixed' estimation cannot silently fall back to native Powell + taper
        # for this arm.
        GICmaxBeta, _fv, _ag = gic_taper_cap()
        kappa = top_atom_offset()
        _announce_param(GICmaxBeta, kappa)
        x0 = _s1param.to_theta_bn(startpoint[0], startpoint[1], cap=GICmaxBeta, kappa=kappa)
        print("Mixed startpoint (t_hi, t_w; splurge literal 0): ", [float(v) for v in x0])
        f_mx2 = lambda x: FagerengObjFunc(0, *_s1param.to_native_bn(x, cap=GICmaxBeta, kappa=kappa),
                                          target=target)
        opt_output = cobyqa_minimize(f_mx2, x0,
                                     _s1param.theta_box_bn(cap=GICmaxBeta, kappa=kappa), [])
        beta, nabla = _s1param.to_native_bn(np.asarray(opt_output.x, dtype=float),
                                            cap=GICmaxBeta, kappa=kappa)
        obs = opt_output.fun
        print('Optimal (beta,nabla) is ' + str(beta) + ',' + str(nabla))
        print('Cap slack at optimum (cap_eff - top atom) = '
              + repr(_s1param.cap_eff(GICmaxBeta) - (beta + kappa * nabla)))
        return {'beta': beta, 'nabla': nabla, 'fval': float(obs)}
    if _STEP1_PARAM == 'theta':
        # 2-D theta twin (owner ruling D1=(c)): splurge stays a LITERAL 0 -- it is not
        # searched here, so making splurge=0 an asymptote of the 3-D map costs nothing --
        # and (beta, nabla) walk (t_hi, t_w) unbounded. Same SST, same tolerances.
        GICmaxBeta, _fv, _ag = gic_taper_cap()
        kappa = top_atom_offset()
        _announce_param(GICmaxBeta, kappa)
        theta0 = _s1param.to_theta_bn(startpoint[0], startpoint[1], cap=GICmaxBeta, kappa=kappa)
        print("Theta startpoint (beta,nabla only): ", [float(t) for t in theta0])
        f_theta = lambda th: FagerengObjFunc(0, *_s1param.to_native_bn(th, cap=GICmaxBeta, kappa=kappa),
                                             target=target)
        _box2 = _s1param.theta_box_bn(cap=GICmaxBeta, kappa=kappa) if _s1param.theta_box_enabled() else None
        print("THETA_BOX: " + ("ON " + repr(_box2) if _box2 is not None else "off (unbounded Brent line searches)"))
        # fix (c) rides with the box (see _find_Opt_theta)
        opt_output = powell_minimize(f_theta, theta0, _box2, restart_at_best=(_box2 is not None))
        beta, nabla = _s1param.to_native_bn(np.asarray(opt_output.x, dtype=float),
                                            cap=GICmaxBeta, kappa=kappa)
        obs = opt_output.fun
        print('Optimal (beta,nabla) is ' + str(beta) + ',' + str(nabla))
        print('Optimal theta is ' + str([float(t) for t in opt_output.x])
              + '   cap margin (cap - top atom) = '
              + repr(_s1param.cap_margin(beta, nabla, cap=GICmaxBeta, kappa=kappa)))
        if check_maximum:
            # NATIVE L-BFGS-B probe on nabla at fixed beta (plan §7a F3), unchanged
            print("check_maximum: NATIVE bounded sub-search at fixed beta (plan §7a F3)")
            check_start = [nabla]
            check_obs = [0.0, 0.0]
            for i, deviation in zip(range(2), [-0.0001, 0.0001]):
                f_chk = lambda y: FagerengObjFunc(0, beta + deviation, y[0], target=target)
                check_opt = minimize(f_chk, check_start, method="L-BFGS-B", bounds=[(0.0, 0.4)])
                check_obs[i] = check_opt.fun
                print([beta + deviation, check_opt.x, check_opt.fun])
            print("Objective around minimum:")
            print([check_obs[0], obs, check_obs[1]])
            if check_obs[0] < obs or check_obs[1] < obs:
                print("Didn't find minimum - check what is going on")
                return {'splurge': 0, 'beta': beta, 'nabla': nabla, 'Error': 'Not a maximum'}
            else:
                print("Local minimum check passed")
        return {'splurge': 0, 'beta': beta, 'nabla': nabla, 'fval': float(obs)}
    _announce_param(gic_taper_cap()[0], top_atom_offset())
        

    f_temp = lambda x : FagerengObjFunc(0,x[0],x[1], target=target)
    # Same convergence policy as find_Opt, via the SST -- previously this arm silently
    # kept scipy's defaults while the splurge estimator was tightened (owner ruling
    # 2026-08-18). NOTE this CHANGES the Step-3 Splurge=0 arm's estimates; it was not part
    # of the tolerance A/B, and is adopted for consistency rather than on its own evidence.
    opt_output = powell_minimize(f_temp, startpoint, [(0.7,1.01),(0.0,0.4)])
    opt = opt_output.x
    obs = opt_output.fun
    beta = opt[0]
    nabla = opt[1]
    print('Optimal (beta,nabla) is ' + str(beta) + ',' + str(nabla)) 
    
    if check_maximum:
        check_start = [opt[1]]
        check_obs = [0.0, 0.0]
        for i,deviation in zip(range(2), [-0.0001, 0.0001]):
            f_temp = lambda y : FagerengObjFunc(0,opt[0]+deviation,y[0],target=target)
            check_opt = minimize(f_temp, check_start,method="L-BFGS-B", bounds = [(0.0,0.4)])
            check_obs[i] = check_opt.fun
            print([opt[0]+deviation,check_opt.x,check_opt.fun])
        print("Objective around minimum:")
        print([check_obs[0], obs, check_obs[1]])
        if check_obs[0]<obs or check_obs[1] < obs :
            print("Didn't find minimum - check what is going on")
            return {'splurge' : 0, 'beta' : beta, 'nabla': nabla, 'Error': 'Not a maximum'}
        else:
            print("Local minimum check passed")
    
    return {'splurge' : 0, 'beta' : beta, 'nabla': nabla, 'fval': float(obs)}


# Make several consumer types to be used during estimation
# CDC-MOD-BUG035 + ESC-MOD-BUG035: Step-1 simulator agent type dispatched by
# HAFISCAL_INTERPRETATION. CDC uses CDCKinkedRConsumerType (subclass with CDC
# household-bargain get_poststates override — sibling fix to AggFiscalType's
# BUG-031 patch on the Step-2/5 side). ESC uses the stock KinkedRconsumerType
# (RNGSyncKinkedRconsumerType) with the optimizer-per-capita asset rule, which
# matches the pre-BUG-035 behavior. The .Splurge attribute is set in
# FagerengObjFunc per-evaluation; deepcopy in EstTypeList propagates it.
from _interpretation import get_interpretation
if get_interpretation() == 'CDC':
    BaseType = CDCKinkedRConsumerType(**base_params)
else:  # ESC
    BaseType = KinkedRconsumerType(**base_params)
# =============================================================================
# OPTIMIZATION: Disable history tracking to reduce memory usage (0.17.0-loky-warmup)
# 0.17.0 defaults to tracking ['aNrm', 'cNrm', 'mNrm', 'pLvl'] which uses ~32MB/agent
# Setting track_vars=[] reduces memory by 60% and prevents Loky worker recycling
# =============================================================================
BaseType.track_vars = []
EstTypeList = []
for j in range(TypeCount):
    EstTypeList.append(deepcopy(BaseType))
    EstTypeList[-1].seed = j




#%% Estimation
Run_estimation      = os.environ.get('HAFISCAL_STEP1_RUN_ESTIMATION', '1') == '1'  # =0: import-safe fixed-point eval mode
# Env hooks mirror HAFISCAL_STEP1_RUN_ESTIMATION (defaults unchanged; added for
# the cold-rerun chain, which must drive these without editing frozen code):
Run_SplurgeZero     = os.environ.get('HAFISCAL_STEP1_SPLURGE0', '0') == '1'  # S3 arm: splurge=0 re-estimation
RunLoopofStarpoints = os.environ.get('HAFISCAL_STEP1_MULTISTART', '1') == '1'  # DEFAULT ON (owner ruling 2026-08-19 evening: the publication protocol -- the dispersed cold multistart -- IS the default; =0 restores the warm single descent)
# Running the Loop of startpoints shows that that the algorithm converges to the same
# solution independent of startpoint and thus strongly suggests that the global minimum was found

    
if Run_estimation:
    # =========================================================================
    # OPTIMIZATION: Pre-warm Loky pool (0.17.0-loky-warmup branch)
    # =========================================================================
    # Warming the pool pre-compiles Numba in workers, avoiding ~4s cold-start.
    # Enable with: export HARK_WARM_POOL=1
    # Without warmup: first call ~4s, subsequent ~0.3s
    # With warmup: all calls ~0.3s (warmup cost ~4s paid once upfront)
    # IMPORTANT: num_agents must match TypeCount for proper worker pool reuse!
    if WARMUP_AVAILABLE:
        maybe_warm_pool(KinkedRconsumerType, num_agents=TypeCount, verbose=True)
    # =========================================================================
    
    print("RUNNING RUN KY AND INIT MPC ESTIMATION")
    target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
    
    if RunLoopofStarpoints:
        # CAP-RELATIVE 18-pt cold-multistart grid (OWNER RULING 2026-08-17, run 5).
        #
        # The seed's beta is no longer an absolute level. What must be controlled is
        # the TOP ATOM of the initial discount-factor distribution relative to the GIC
        # cap, because that is what the arctan taper acts on:
        #
        #     top atom = beta0 + top_atom_offset()*nabla0            (= beta0 + (6/7)*nabla0 at TypeCount=7)
        #     beta0(k, nabla0) = k*GICmaxBeta - top_atom_offset()*nabla0
        #
        # so every seed's top atom sits at exactly k * cap, for k in (1.00, 0.95, 0.90),
        # whatever nabla0 is. Widening nabla0 now pulls beta0 down to compensate instead
        # of pushing the top atom through the cap.
        #
        # WHY (the run-4 defect): the previous grid crossed beta0 in {0.85, 0.925, 1.0}
        # with nabla0 in {0, 0.025, 0.05}, which puts the top atom ABOVE the cap
        # (1.0076174) for the six seeds with beta0=1.0 and nabla0>0 -- 1.0214 and 1.0429.
        # Those seeds are BORN on the taper's saturation shelf, where the effective beta
        # barely responds to the nominal one (d(eff)/d(nom) = 0.042 and 0.0097
        # respectively), so bounded Powell gets almost no signal in that direction and
        # terminates far-field. Measured over run 4's 25 completed starts per arm: 4 of
        # 4 above-cap seeds became stragglers, versus 2 of 21 below-cap seeds. BUG-078's
        # regrid fixed only the nabla leg -- it respread nabla0 off 0.10 but left the
        # beta leg cap-unaware, so "no seed starts past the GIC cap" was never actually
        # imposed. The tau=0.005 ruling's accepted cost ("high-beta STARTS are hostile
        # ... multistart's non-killed consensus absorbs those rows", see TAPER_THRESHOLD
        # above) is hereby retired in favour of not creating dead seeds at all.
        #
        # TOP RUNG IS DERIVED FROM THE TAPER WIDTH, NEVER HARDWIRED
        # (owner ruling 2026-08-17, superseding the same day's k=1.00):
        #
        #     k_top = 1 - 2*TAPER_THRESHOLD/GICmaxBeta
        #
        # so the most-patient seed's top atom clears the taper band by exactly one band
        # width, and it re-derives itself if tau ever changes.
        #
        # The division by the cap is not pedantry: tau is an ABSOLUTE beta width while k
        # is a dimensionless fraction OF the cap, so dividing is what makes the two
        # commensurable -- and it is what makes the margin EXACT rather than approximate.
        # By construction k_top*cap = cap - 2*tau, so the gap to the band floor (cap - tau)
        # is identically tau, for every tau and every cap:
        #     (cap - tau) - k_top*cap  ==  tau        exactly
        # The undivided form 1 - 2*tau leaves a margin of 1.015*tau at the live
        # calibration -- close, but only because cap happens to be near 1; it drifts with
        # the cap and is exact at no calibration. (The bare band-clearing threshold, with
        # zero margin, is 1 - tau/cap. The doubling is what buys the margin, and the margin
        # is wanted because the optimizer EXPLORES UPWARD: a seed placed exactly at the
        # band floor enters the throttled region on its first step.)
        #
        # WHY, and what this replaces: the first cap-relative grid used k=1.00, putting
        # the top atom exactly AT the cap -- inside the band at z=1, ~1/pi ~ 32%
        # responsive -- on the reasoning that 32% is two orders above the 0.0097 that
        # killed run-4's above-cap seeds. Run 5's own traces falsified that reasoning
        # within an hour. Its k=1.00 seeds with the NARROW nabla0=0.01, whose 7 atoms
        # span only +-(6/7)*0.01 and so put the top two or three INSIDE the band, went
        # the wrong way: dell seed 1 sat at f=0.0441 after 267 evaluations (25x the
        # era-4 floor) with beta climbing toward the cap, nabla collapsing to 0.0082 and
        # splurge ballooning to 0.463 -- while EVERY run-4 seed, including the three that
        # ended off-basin, was already at f=0.002-0.006 by that eval count. The k=1.00
        # seeds with nabla0=0.05 were fine (m5 seed 2: f=0.0044), because the 5x wider
        # spread leaves only the top atom in the band. So the hazard is not the top
        # atom's position alone but HOW MUCH OF THE ATOM SET sits in the band, and
        # clearing the band outright removes it for every nabla0.
        #
        # k = (k_top, 0.90) -- TWO rungs (owner ruling 2026-08-17). 0.95 was the interior
        # rung and is dropped for the same reason 0.03 went from the nabla leg and
        # 0.10/0.30 from the splurge leg: with a bracket, the interior buys little. Every
        # axis is now a 2-level bracket, giving 2x2x2 = 8 seeds. 0.90 stays a literal --
        # it sits far below the band at any plausible tau, so deriving it would add
        # machinery without adding safety.
        # COST OF 8: the 2/3 consensus rule then needs 6 of 8 in the modal basin, i.e. it
        # tolerates only 2 stragglers (12 seeds tolerated 4). Run 4 ran 6 stragglers in 25
        # seeds, but 4 of those were the above-cap class this design removes; the residual
        # rate is ~10%, so <1 straggler is expected. Three surprises would leave the
        # battery inconclusive -- an accepted, owner-ruled risk.
        #
        # The nabla leg is TWO levels, (0.01, 0.05) -- owner ruling 2026-08-17,
        # restoring the published 18-point count (3 splurge x 3 k x 2 nabla). nabla0=0
        # is excluded as a degenerate zero-dispersion knife edge, and the interior
        # 0.03 is dropped: nabla is report-only in the S1 gate and is the least
        # identified of the three parameters ("nabla is not well identified and can
        # move a lot with little consequence for the distribution of wealth", owner
        # 2026-08-13), so spending a third of the battery on an interior nabla level
        # buys less than the ~19 h of wall time it costs. Endpoints still bracket the
        # dispersion axis, and the cap-relative construction holds the top atom at
        # k*cap on BOTH nabla rows, so no row is privileged.
        #
        # Enumeration order is preserved from run 4 -- splurge-major, then the beta
        # level (now indexed by k), nabla innermost -- so grid position i keeps its
        # meaning across runs even though the seed values move.
        # Records: plans/20260813-1030h_cold-start-full-reestimation_plan.md (S1),
        # Results/cold_rerun_2026-08/s1_run4_27pt_tau005_PARTIAL/KILLED.txt.
        _cap = gic_taper_cap()[0]
        _tw = top_atom_offset()
        _k_top = 1.0 - 2.0 * TAPER_THRESHOLD / _cap   # derived, not hardwired -- see above
        #
        # ENUMERATION ORDER = CHEAPEST EXPECTED WALL FIRST (owner ruling 2026-08-17), so a
        # battery killed for a newly-found bug has banked as many finished seeds as
        # possible, and a restart discards the least work.
        #
        # The cost model is measured, not guessed: over run 4's HEALTHY seeds (far-field
        # and off-basin ones excluded, since their cheapness is failure, not speed),
        # nabla0 is the dominant and MONOTONE predictor of evaluation count --
        #     nabla0 = 0.000 -> 1016 evals (n=5, range 702-1362)
        #     nabla0 = 0.025 ->  817 evals (n=5, range 692-1017)
        #     nabla0 = 0.050 ->  560 evals (n=5, range 486- 678)
        # -- a near-2x spread. Mechanism: at nabla=0 all TypeCount atoms coincide, so the
        # objective is flat in nabla and the optimizer is slow to escape a degenerate
        # start; a wide start already has spread to work with. beta0 carried no signal
        # except in the near-cap row (n=1), and splurge0 essentially none (843/788/668
        # evals at 0.10/0.30/0.50, and the 0.50 group is n=2). So nabla0 sets the tier and
        # the other two axes only break ties. Interpolating the two anchors puts
        # nabla0=0.01 at ~936 evals, i.e. ~1.7x the cost of a nabla0=0.05 seed.
        #
        # WITHIN a tier every seed costs the same, so the intra-tier order is FREE and is
        # spent on RISK instead: k descending, most-patient (nearest the GIC cap) first.
        # That is the rung where a taper-side defect would show, and run 5 proved such a
        # defect can hide there -- so it is exercised in the first few seeds rather than
        # after 15 hours, at no cost to the cheapest-first property.
        # splurge0 in (0.01, 0.50) -- TWO rungs, not three (owner ruling 2026-08-17).
        # Run 4 showed splurge0 carries almost no signal: 843/788/668 mean evals at
        # 0.10/0.30/0.50 (the last n=2), and every healthy seed reached the same basin
        # regardless of it. The two survivors bracket the era-4 optimum (0.2955) more
        # widely than 0.10/0.50 did, so dispersion on this axis improves while cost falls.
        #
        # The bottom rung is 0.01, NOT 0.00 (owner ruling 2026-08-17, revised): 0.00 sits
        # EXACTLY on the optimizer's lower bound -- find_Opt uses
        # bounds [(0.0,0.9),(0.7,1.1),(0.0,0.4)] -- so bounded Powell's first line search
        # in that coordinate would be one-sided, able only to step up. That is legitimate
        # in principle, but it is a configuration never previously exercised in a
        # 3-parameter fit: the existing 0.00 startpoints belong to the Splurge=0 arm, where
        # splurge is FIXED at 0 and only (beta,nabla) are optimized. At 8 seeds it would
        # have been HALF the battery riding an untested boundary start, so 0.01 buys the
        # question away at negligible cost to dispersion (the optimum is at 0.2955; 0.01 vs
        # 0.00 is a 0.03% change in the distance to it).
        # THE grid is built by the SST step1_param.startpoint_grid (owner ruling 2026-08-18:
        # universal across the S1, S3 and CRRA arms) -- cost-ordered, cap-relative,
        # nabla0=(0.01,0.05), k=(1-2tau/cap, 0.90); the legend it returns is the exact
        # line s1_gate.py parses and is generated from the grid itself, so it cannot drift.
        startpoints, _legend = _s1param.startpoint_grid((0.01, 0.50), cap=_cap, kappa=_tw,
                                                        tau=TAPER_THRESHOLD)
        print(_legend)
    else:
        # Warm start at the latest estimated optimum for the ACTIVE interpretation
        # (both are 2026-07-27 noise-free TM-engine optima; the ESC one is the
        # first valid ESC estimation after the BUG-054 Option A fix, +1.2% ς off
        # Edmund's pre-staged April value — the same drift class as the CDC
        # re-derivation, so the noise/era correction transports).
        print("WARNING: warm start from the previously estimated optimum (single "
              "descent). Any final production run for publication should use the "
              "cold multi-start: set RunLoopofStarpoints = True.")
        if get_interpretation() == 'ESC':
            startpoints = [ [0.2703537277859902, 0.973125362575203, 0.059370560558206206] ]
        else:
            startpoints = [ [0.2598155088512016, 0.9623248540370246, 0.07165354296044844] ]
    
    # BUG-078 pilot/shard hook: HAFISCAL_STEP1_START_SUBSET="18" (or "1,5,9") runs
    # only those 1-based grid indices; result filenames keep the ORIGINAL grid
    # numbering so a subset run's outputs land in their full-grid slots.
    _subset_env = os.environ.get('HAFISCAL_STEP1_START_SUBSET', '').strip()
    if RunLoopofStarpoints and _subset_env:
        _keep = sorted({int(tok) for tok in _subset_env.replace(',', ' ').split()})
        indexed_startpoints = [(k, startpoints[k-1]) for k in _keep]
    else:
        indexed_startpoints = list(enumerate(startpoints, start=1))
    # Owner probe hook (2026-08-19): HAFISCAL_STEP1_STARTPOINT="s,b,n" replaces the grid
    # with ONE custom startpoint (e.g. the splurge=0 conditional optimum, to test whether
    # joint moves off the splurge=0 face descend -- the "bottom start"). Result slot 'C'
    # (Result_AllTarget_startpointC_*.txt) so no grid slot is shadowed and the gate never
    # ingests it. Overrides START_SUBSET when both are set.
    _custom_env = os.environ.get('HAFISCAL_STEP1_STARTPOINT', '').strip()
    if RunLoopofStarpoints and _custom_env:
        _vals = [float(tok) for tok in _custom_env.replace(',', ' ').split()]
        if len(_vals) != 3:
            raise ValueError("HAFISCAL_STEP1_STARTPOINT needs exactly 3 floats 's,b,n'; "
                             "got %r" % _custom_env)
        indexed_startpoints = [('C', _vals)]
        print("CUSTOM STARTPOINT (HAFISCAL_STEP1_STARTPOINT):", _vals)
    # ── CONTINUATION PROTOCOL (owner ruling 2026-08-22 ~13:05: "make the continuation
    # the canonical Step-1 protocol now" — revises the 08-19 dispersed-cold-multistart
    # default, which is DEMOTED to the certification instrument: opt in with
    # HAFISCAL_STEP1_PROTOCOL=multistart, or implicitly via any explicit
    # START_SUBSET/STARTPOINT hook, and run it per calibration change and at R2
    # installs). Two-stage parameter continuation in the splurge — deterministic and
    # history-free (NOT a saved-artifact warm start: stage 1 is itself a cold
    # multistart of the ς=0 restricted problem; stage 2 is its continuation):
    #   stage 1  COLD multistart over the splurge0 arm's own cap-relative (β,∇) grid.
    #            Basin certification lives HERE (validated 2026-08-22: 4/4 starts to
    #            NINE digits at the main spec — the 2-D restricted problem has no flat
    #            splurge direction). Writes the Splurge0 SoR files as a by-product
    #            (Step 3's S1-level input falls out of the main protocol).
    #   stage 2  ONE joint descent from (0, β̂₀, ∇̂₀) through the startpoint-C
    #            machinery below (slot C per-start file + the canonical winner write).
    #            Validated to land ON the dispersed battery's winner
    #            (−0.020%/−0.0004%/−0.007%; assessment doc §6).
    # Unanimity guard: if the error-free stage-1 starts disagree beyond 1e-4 relative
    # on β or ∇ (the 08-22 measurement: ~2e-9), the protocol's premise fails — warn
    # LOUDLY and fall back to the dispersed multistart for this run (transparent
    # fallback; the γ=1/BUG-086 face-stuck class is exactly what this catches).
    # Fidelity conventions: QE-fidelity and the as-corrected world default to
    # 'multistart' (the pre-continuation behavior). Explicit env always wins.
    _protocol = os.environ.get('HAFISCAL_STEP1_PROTOCOL', '').strip().lower()
    if not _protocol:
        _fid_world = (os.environ.get('HAFISCAL_QE_FIDELITY', '') == '1'
                      or os.environ.get('HAFISCAL_WORLD', '').strip().lower()
                      == 'as-corrected')
        _protocol = 'multistart' if _fid_world else 'continuation'
    if _protocol not in ('continuation', 'multistart'):
        raise ValueError("HAFISCAL_STEP1_PROTOCOL must be 'continuation' or "
                         "'multistart'; got %r" % _protocol)
    if (_protocol == 'continuation' and RunLoopofStarpoints
            and not _subset_env and not _custom_env):
        _cap1, _fv_unused, _ag_unused = gic_taper_cap()
        _cont_starts, _cont_legend = _s1param.startpoint_grid(
            (0.0,), cap=_cap1, kappa=top_atom_offset(), tau=TAPER_THRESHOLD)
        print(_cont_legend.replace("Multistart grid:",
                                   "Continuation stage 1 (splurge=0) grid:"))
        _cont_st1 = []
        for _ci, _csp in enumerate(_cont_starts, start=1):
            print("Continuation stage 1, startpoint no. ", _ci)
            print("Startpoint used: ", _csp)
            _cres = find_Opt_splurge0(target=target, startpoint=_csp[1:3])
            _cfv = _cres.pop('fval', None)
            _cres.setdefault('splurge', 0)
            save_betanabla_res_txt(
                '/Result_AllTarget_Splurge0_startpoint' + str(_ci) + '.txt', _cres)
            if 'Error' not in _cres and _cfv is not None:
                _cont_st1.append((_cfv, _ci, dict(_cres)))
        # Acceptance = parameter unanimity OR f-tie (D4 default, 2026-08-23).
        # The f-tie arm is the flat-valley correction: at PROFILE=full the
        # splurge=0 valley is flat at ~1e-5-relative f, so COBYQA stops scatter
        # ~1.5e-3 in nabla while f-tying at 8e-6 -- one basin, not many.
        # Criterion, tolerances, and the measured derivation live in
        # step1_stage1_acceptance (guard: test_step1_ftie_acceptance.py).
        from step1_stage1_acceptance import stage1_accept as _s1accept
        _cont_ok, _cont_why, _cont_spread, _cont_fspread = _s1accept(_cont_st1)
        if _cont_ok:
            _cont_best = min(_cont_st1)
            save_betanabla_res_txt('/Result_AllTarget_Splurge0.txt', _cont_best[2])
            print('CONTINUATION stage 1 CERTIFIED via %s: %d/%d error-free starts '
                  '(param spread %.2e, f spread %.2e; beta0=%.12f nabla0=%.12f, '
                  'min-f start %d); Splurge0 SoR written as the protocol by-product.'
                  % (_cont_why, len(_cont_st1), len(_cont_starts), _cont_spread,
                     _cont_fspread, _cont_best[2]['beta'], _cont_best[2]['nabla'],
                     _cont_best[1]))
            indexed_startpoints = [('C', [0.0, float(_cont_best[2]['beta']),
                                          float(_cont_best[2]['nabla'])])]
            print('CONTINUATION stage 2: one joint descent from (0, beta0, nabla0)')
        else:
            print('=' * 78)
            print('WARNING: CONTINUATION stage 1 FAILED acceptance (%s: param '
                  'spread %.3e, f spread %.3e across %d error-free starts of %d).'
                  % (_cont_why, _cont_spread, _cont_fspread,
                     len(_cont_st1), len(_cont_starts)))
            print('The continuation premise does not hold for this configuration; '
                  'FALLING BACK to the dispersed cold multistart for this run.')
            print('=' * 78)
    _ms_best = None   # (fval, slot, 3-key result) across the multistart battery
    for i,startpoint in indexed_startpoints:
        print("Startpoint run no. ", i)
        print("Startpoint used: ", startpoint)


        if RunLoopofStarpoints:
            filename = '/' + suffix_path('Result_AllTarget_startpoint'+str(i)+'.txt')
        else:
            # BUG-054 Option A (owner 2026-07-27): each interpretation writes
            # its own file (Result_AllTarget_ESC.txt / _CDC.txt); the bare
            # Result_AllTarget.txt is a symlink to the production (_ESC) file.
            filename = '/' + suffix_path('Result_AllTarget.txt')
        res = find_Opt(target=target, startpoint=startpoint)
        _fv = res.pop('fval', None)   # result FILES keep the classic 3-key shape
        save_betanabla_res_txt(filename,res)
        if RunLoopofStarpoints and _fv is not None and 'Error' not in res:
            if _ms_best is None or _fv < _ms_best[0]:
                _ms_best = (_fv, i, dict(res))
    # Owner ruling 2026-08-19 evening: the canonical result Step 2 consumes MUST be
    # this Step-1 iteration's winner. Under multistart, write the best-of-battery
    # (min f, Error-free) into Result_AllTarget(.suffix).txt -- previously only the
    # per-startpoint files were written and the canonical went silently stale (the
    # chain runners compensated externally at gate time; a plain do_all could not).
    # Custom-startpoint PROBES (HAFISCAL_STEP1_STARTPOINT, slot C) never touch it.
    # NOT under START_SUBSET: a sharded process (one start of a concurrent battery)
    # cannot know the other shards' f values -- writing the canonical from a shard
    # would be last-finisher-wins, not min-f. Shard batteries are merged/installed
    # by the external gate (s1_merge_shards.sh); only a FULL in-process battery may
    # write the canonical here. (Caught in the 2026-08-19 overnight pre-flight.)
    if RunLoopofStarpoints and _ms_best is not None and not _custom_env and not _subset_env:
        print('MULTISTART_WINNER: startpoint %s  f=%.10g  %r' % (_ms_best[1], _ms_best[0], _ms_best[2]))
        print('MULTISTART_WINNER: canonical ' + suffix_path('Result_AllTarget.txt') + ' updated (consumed by Step 2)')
        save_betanabla_res_txt('/' + suffix_path('Result_AllTarget.txt'), _ms_best[2])
        

if Run_SplurgeZero:
    print("RUNNING RUN KY AND INIT MPC ESTIMATION, SPLURGE = 0")
    target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
    
    if RunLoopofStarpoints:
        # Loop over starting points with beta in (0.85, 0.925, 1) and nabla in (0.00, 0.025, 0.05)
        # BUG-078 extension (owner confirm 2026-08-14): the nabla starts were
        # (0.05, 0.10, 0.20) -- the same GIC-taper saturation-shelf disease as the
        # main grid, deeper (z up to ~21 at beta0=1, nabla0=0.20). Same 3x3
        # (beta, nabla) factorial, splurge fixed at 0 by design.
        # SAME grid design as S1 via the SST, with splurge pinned at 0 (owner ruling
        # 2026-08-18: universal defaults across arms). Replaces the paper-era absolute
        # 3x3 (beta0 in {0.85,0.925,1.0} x nabla0 in {0,0.025,0.05}): nabla0=0 was a
        # zero-dispersion knife edge (and log(0) under theta), and beta0=1.0 put the
        # top atom above the cap for every nabla0>0 (dead on arrival without the taper).
        _cap3, _fv3, _ag3 = gic_taper_cap()
        startpoints, _legend3 = _s1param.startpoint_grid((0.0,), cap=_cap3, kappa=top_atom_offset(),
                                                         tau=TAPER_THRESHOLD)
        print(_legend3.replace("Multistart grid:", "Multistart grid (splurge0 arm):"))
    else:
        print("WARNING: warm start from the previously estimated optimum (single "
              "descent). Any final production run for publication should use the "
              "cold multi-start: set RunLoopofStarpoints = True.")
        startpoints = [ [0, 0.9215203827041509, 0.11625829523973752] ]
        
    # Same shard hook as S1: HAFISCAL_STEP1_START_SUBSET="1,3" runs only those 1-based grid
    # indices, filenames keep the ORIGINAL numbering (so concurrent per-seed processes on
    # one machine write disjoint files -- the run-7 concurrency pattern).
    _subset_env3 = os.environ.get('HAFISCAL_STEP1_START_SUBSET', '').strip()
    if RunLoopofStarpoints and _subset_env3:
        _keep3 = sorted({int(tok) for tok in _subset_env3.replace(',', ' ').split()})
        _indexed3 = [(k, startpoints[k-1]) for k in _keep3]
    else:
        _indexed3 = list(enumerate(startpoints, start=1))
    _s0_best = None
    for i,startpoint in _indexed3:
        print("Startpoint run no. ", i)
        print("Startpoint used: ", startpoint)
        if RunLoopofStarpoints:
            filename = '/Result_AllTarget_Splurge0_startpoint'+str(i)+'.txt'
        else:
            filename = '/Result_AllTarget_Splurge0.txt'
        res = find_Opt_splurge0(target=target, startpoint=startpoint[1:3])
        _fv3 = res.pop('fval', None)
        # The arm pins splurge at 0 and find_Opt_splurge0 returns only (beta, nabla); every
        # consumer of the result file (load_betanabla_res_txt, Parameters.py's Splurge0
        # branch) reads the 'splurge' key. Found 2026-08-20 (no-splurge chain, N1).
        res.setdefault('splurge', 0)
        save_betanabla_res_txt(filename,res)
        if RunLoopofStarpoints and _fv3 is not None and 'Error' not in res:
            if _s0_best is None or _fv3 < _s0_best[0]:
                _s0_best = (_fv3, i, dict(res))
    if RunLoopofStarpoints and _s0_best is not None and not _subset_env3:
        print('MULTISTART_WINNER (Splurge0): startpoint %s  f=%.10g  %r' % (_s0_best[1], _s0_best[0], _s0_best[2]))
        save_betanabla_res_txt('/Result_AllTarget_Splurge0.txt', _s0_best[2])

#%% Output results for paper

Plot_Output = os.environ.get('HAFISCAL_STEP1_PLOT', '1') == '1'  # =0: skip plots (probe/CI mode)
if Plot_Output:
    # The deterministic 'tm' engine has no panel, and everything from here to
    # the end of the script is OUTPUT GENERATION whose estimation_mode=False
    # re-evaluations (here, and the CRRA comparison table further down) build
    # the paper's comparison artifacts from one. Switch to the arc's
    # panel-capable 'tm_init' variant for the REMAINDER of the script — the
    # estimates above are untouched, and an explicit non-'tm'
    # HAFISCAL_STEP1_SIM_ENGINE is honored as-is. Caught 2026-08-03 by the
    # m5 end-to-end run: the refuse-loudly guard in FagerengObjFunc killed
    # Step 1's output section on every machine since the 'tm' default landed.
    if _STEP1_ENGINE == 'tm':
        _STEP1_ENGINE = 'tm_init'
        print("[step1] Plot_Output: engine 'tm' has no panel — output-section "
              "re-evaluations run under 'tm_init' (estimates unaffected).",
              flush=True)
    target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
    # Splurge=0 solution
    [splurge,beta,nabla] = load_betanabla_res_txt('/Result_AllTarget_Splurge0.txt')
    Splurge0_Sol=FagerengObjFunc(splurge,beta,nabla,estimation_mode=False,target=target)

    # Splurge>0 solution (interpretation-routed since BUG-054 Option A)
    [splurge,beta,nabla] = load_betanabla_res_txt('/' + suffix_path('Result_AllTarget.txt'))
    SplurgeNot0_Sol=FagerengObjFunc(splurge,beta,nabla,estimation_mode=False,target=target)
    
    # Plot Lorentz curve
    plt.figure()
    LorenzAxis = np.arange(101,dtype=float)
    plt.plot(LorenzAxis,SplurgeNot0_Sol['Lorenz_Data_Adj'] ,'b-',linewidth=2)
    plt.scatter(np.array([20,40,60,80,100]),np.hstack([lorenz_target,1]),c='black', marker='o')
    plt.xlabel('Liquid wealth percentile',fontsize=12)
    plt.ylabel('Cumulative liquid wealth share',fontsize=12)
    plt.legend(['Model','Data'])
    make_figs('LiquWealth_Distribution_comparison', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot()  
    
    # Plot Lorentz curve
    plt.figure()
    LorenzAxis = np.arange(101,dtype=float)
    plt.plot(LorenzAxis,SplurgeNot0_Sol['Lorenz_Data_Adj'] ,'b-',linewidth=2)
    plt.plot(LorenzAxis,Splurge0_Sol['Lorenz_Data_Adj']    ,'r:',linewidth=2)
    plt.scatter(np.array([20,40,60,80,100]),np.hstack([lorenz_target,1]),c='black', marker='o')
    plt.xlabel('Liquid wealth percentile',fontsize=12)
    plt.ylabel('Cumulative liquid wealth share',fontsize=12)
    plt.legend(['Model, splurge $\geq$ 0','Model, splurge = 0','Data'])
    make_figs('LiquWealth_Distribution_comparison_splurge0', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot() 
    
    # Plot Agg MPCx
    plt.figure()
    xAxis = np.arange(0,5)
    plt.plot(xAxis,SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'] ,'b-',linewidth=2)
    plt.plot(xAxis,Splurge0_Sol['simulated_MPC_mean_add_Lottery_Bin']    ,'r:',linewidth=2)
    plt.scatter(xAxis,Agg_MPCX_target,c='black', marker='o')
    plt.legend(['Model, splurge $\geq$ 0','Model, splurge = 0','Fagereng, Holm and Natvik (2021)'])
    plt.xticks(np.arange(min(xAxis), max(xAxis)+1, 1.0))
    plt.xlabel('year')
    plt.ylabel('% of lottery win spent')
    make_figs('AggMPC_LotteryWin_comparison_splurge0', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot()  
    
    # Plot Agg MPCx
    plt.figure()
    xAxis = np.arange(0,5)
    plt.plot(xAxis,SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'] ,'b-',linewidth=2)
    plt.scatter(xAxis,Agg_MPCX_target,c='black', marker='o')
    plt.legend(['Model','Fagereng, Holm and Natvik (2021)'])
    plt.xticks(np.arange(min(xAxis), max(xAxis)+1, 1.0))
    plt.xlabel('year')
    plt.ylabel('% of lottery win spent')
    make_figs('AggMPC_LotteryWin_comparison', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot() 
    
    # Table initial MPCs along wealth q
    
    def mystr2(number):
        if not np.isnan(number):
            out = "{:.2f}".format(number)
        else:
            out = ''
        return out
    
        
    output  ="\\begin{tabular}{@{}lcccccc@{}} \n"
    output +="\\toprule \n"
    output +="                  & \multicolumn{5}{c}{MPC} &   \\\\   \n"
    output +="                  &  1st WQ  & 2nd WQ  & 3rd WQ & 4th WQ  & Agg  &  K/Y  \\\\  \\midrule \n"
    output +="Splurge $\geq$ 0 &"+mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][3])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][1])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'][0])+ " & "+ mystr2(SplurgeNot0_Sol['KY_Model'])  + " \\\\ \n"
    output +="Splurge = 0 &"+   mystr2(Splurge0_Sol['simulated_MPC_means_smoothed'][3])         + " & "+ mystr2(Splurge0_Sol['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(Splurge0_Sol['simulated_MPC_means_smoothed'][1])         + " & "+ mystr2(Splurge0_Sol['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(Splurge0_Sol['simulated_MPC_mean_add_Lottery_Bin'][0])   + " & "+ mystr2(Splurge0_Sol['KY_Model'])  + " \\\\ \n"
    output +="Data &"+          mystr2(MPC_target[2,3])                                         + " & "+ mystr2(MPC_target[2,2])+ " & "+  \
                                mystr2(MPC_target[2,1])                                         + " & "+ mystr2(MPC_target[2,0]) + " & "+  \
                                mystr2(Agg_MPCX_target[0])                                      + " & "+ mystr2(KY_target)  + " \\\\ \\bottomrule \n"
    output +="\\end{tabular}  \n"
    
    
    # Candidate-routed (2026-08-03): this is a TRACKED paper table; the raw
    # canonical-path write predated the QE freeze and rewrote it in place on
    # every Step-1 run (caught when the m5 end-to-end run dirtied the tree).
    import sys as _go_sys
    _go_ham = os.path.abspath(os.path.join(Abs_Path, '..', 'FromPandemicCode'))
    if _go_ham not in _go_sys.path:
        _go_sys.path.insert(0, _go_ham)
    from generated_output import write_generated as _write_generated
    _write_generated(Abs_Path+'/Figures/Comparison_Splurge_Table.tex', output)
        
    
    output  ="\\begin{tabular}{@{}lcccccc@{}} \n"
    output +="\\toprule \n"
    output +="                  & \multicolumn{5}{c}{MPC} &   \\\\   \n"
    output +="                  &  1st WQ  & 2nd WQ  & 3rd WQ & 4th WQ  & Agg  &  K/Y  \\\\  \\midrule \n"
    output +="Model &"+mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][3])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][1])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'][0])+ " & "+ mystr2(SplurgeNot0_Sol['KY_Model'])  + " \\\\ \n"
    output +="Data &"+          mystr2(MPC_target[2,3])                                         + " & "+ mystr2(MPC_target[2,2])+ " & "+  \
                                mystr2(MPC_target[2,1])                                         + " & "+ mystr2(MPC_target[2,0]) + " & "+  \
                                mystr2(Agg_MPCX_target[0])                                      + " & "+ mystr2(KY_target)  + " \\\\ \\bottomrule \n"
    output +="\\end{tabular}  \n"
    
    
    with open_generated(Abs_Path+'/Figures/MPC_WealthQuartiles_Table.tex') as f:
        f.write(output)
        f.close()   
    
    
    
    Output_to_Excel = False
    if Output_to_Excel:
        x = np.vstack(( xAxis, SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'], Splurge0_Sol['simulated_MPC_mean_add_Lottery_Bin'] , Agg_MPCX_target) )
        df = pd.DataFrame(x.T,columns=['Year','Model, splurge > 0','Model, splurge = 0','Fagereng, Holm and Natvik (2021)'])
        df.to_excel(Abs_Path+'/Data_AggMPC_LotteryWin.xlsx')
        
        x = np.vstack(( LorenzAxis, SplurgeNot0_Sol['Lorenz_Data_Adj'], Splurge0_Sol['Lorenz_Data_Adj'] ) )
        df = pd.DataFrame(x.T,columns=['Percentile','Model, splurge > 0','Model, splurge = 0'])
        df.to_excel(Abs_Path+'/LiquWealth_Distribution_a.xlsx')
        
        x = np.vstack(( np.array([20,40,60,80,100]), np.hstack([lorenz_target,1]) ) )
        df = pd.DataFrame(x.T,columns=['Percentile','Data'])
        df.to_excel(Abs_Path+'/LiquWealth_Distribution_b.xlsx')
        
        
def error_two_arrays(x,y):
    return np.linalg.norm(x-y);

if Plot_Output:
    # These summaries consume Plot_Output's products (SplurgeNot0_Sol/Splurge0_Sol);
    # gated with it (latent coupling exposed by the HAFISCAL_STEP1_PLOT=0 probe mode).
    print('Errors for MPC over time: ')
    print('Splurge > 0:', error_two_arrays(Agg_MPCX_target,SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin']))
    print('Splurge = 0:', error_two_arrays(Agg_MPCX_target, Splurge0_Sol['simulated_MPC_mean_add_Lottery_Bin']))

    print('Errors for MPC across wealth: ')
    print('Splurge > 0:', error_two_arrays(MPC_target[2,:], SplurgeNot0_Sol['simulated_MPC_means_smoothed']))
    print('Splurge = 0:', error_two_arrays(MPC_target[2,:], Splurge0_Sol['simulated_MPC_means_smoothed']))
 
if Plot_Output:
    # Same coupling as above: consumes Plot_Output's products.
    print('Errors for Lorentz curve: ')
    print('Splurge > 0:', error_two_arrays(np.hstack([lorenz_target,1]), SplurgeNot0_Sol['Lorenz_Data_Adj'][[20,40,60,80,100]]))
    print('Splurge = 0:', error_two_arrays(np.hstack([lorenz_target,1]), Splurge0_Sol['Lorenz_Data_Adj'][[20,40,60,80,100]]))

    print('Errors for K/Y: ')
    print('Splurge > 0:', error_two_arrays(KY_target, SplurgeNot0_Sol['KY_Model']))
    print('Splurge = 0:', error_two_arrays(KY_target, Splurge0_Sol['KY_Model']))
     
   


#%% Other risk-aversion values (the robustness appendix's gamma rows)
# Env-gated, sharded, winner-written -- the SAME machinery as the main arm (owner ruling
# 2026-08-20 ~22:30: re-estimate the splurge per gamma, as the published appendix did).
#   HAFISCAL_STEP1_OTHER_CRRA="1,3"      run the arm for these gamma values (default: off)
#   HAFISCAL_STEP1_START_SUBSET="k"      one grid start per process (the shard pattern)
#   HAFISCAL_STEP1_RUN_ESTIMATION=0 HAFISCAL_STEP1_PLOT=0   skip the main arm and the plots
# Per start:  Result_CRRA_<g>.0_startpoint<i>_<INTERP>.txt   (grid numbering preserved)
# Winner:     Result_CRRA_<g>.0_<INTERP>.txt  -- min-f, Error-free, written ONLY by a full
#             in-process battery (a shard cannot know the other shards' f; the external
#             merge installs the canonical from the shard logs, as for the other arms).
# That stem is what Parameters.py resolves for the CRRA1 / CRRA3 parametrizations
# (resolve_path(.../Result_CRRA_1.0.txt)); the pre-2026-08-20 block wrote
# Result_AllTarget_CRRA_<g>_startpoint<i>.txt (0-based, unsuffixed), which nothing read.
# The GIC cap, the cold-multistart grid and the theta/mixed map are all re-derived at the new
# gamma (gic_taper_cap reads base_params at call), and FagerengObjFunc solves the module-level
# EstTypeList, which is rebuilt here from base_params at that gamma.
_other_crra = _s1param.other_crra_values()
Run_other_CRRA_values = bool(_other_crra)
if Run_other_CRRA_values:
    _crra_saved = base_params['CRRA']
    _subset_envC = os.environ.get('HAFISCAL_STEP1_START_SUBSET', '').strip()
    for _crra in _other_crra:
        print('Running CRRA = ', _crra)
        base_params['CRRA'] = _crra
        _PARAM_ANNOUNCED = False          # announce the parameterization with THIS gamma's cap
        # the universal grid (owner ruling 2026-08-18), built AFTER the CRRA change because
        # the cap it is relative to depends on CRRA (gic_taper_cap reads base_params at call)
        _capC, _fvC, _agC = gic_taper_cap()
        startpoints, _legendC = _s1param.startpoint_grid((0.01, 0.50), cap=_capC, kappa=top_atom_offset(),
                                                         tau=TAPER_THRESHOLD)
        print(_legendC.replace("Multistart grid:", "Multistart grid (CRRA=%g):" % _crra))
        print("GIC cap at CRRA=%g: %.10f (beta_FVAC %.6f, beta_AGG %.6f)" % (_crra, _capC, _fvC, _agC))

        # Rebuild the consumer types at this gamma (FagerengObjFunc solves EstTypeList in place)
        BaseTypeCRRA = KinkedRconsumerType(**base_params)
        EstTypeList = []
        for j in range(TypeCount):
            EstTypeList.append(deepcopy(BaseTypeCRRA))
            EstTypeList[-1].seed = j

        target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
        _stemC = _s1param.crra_result_stem(_crra)
        if RunLoopofStarpoints:
            if _subset_envC:
                _keepC = sorted({int(tok) for tok in _subset_envC.replace(',', ' ').split()})
                _indexedC = [(k, startpoints[k-1]) for k in _keepC]
            else:
                _indexedC = list(enumerate(startpoints, start=1))
        else:
            print("WARNING: warm start from the paper-era optimum (single descent). Any "
                  "final production run for publication should use the cold multi-start.")
            _indexedC = [('W', [0.14936532325901916, 0.9768205536148804, 0.09086039551142643]
                          if _crra == 1 else
                          [0.2660514984112632, 0.9549940464615455, 0.06597517675173052])]
        _best_C = None
        for i, startpoint in _indexedC:
            print("Startpoint run no. ", i)
            print("Startpoint used: ", startpoint)
            if RunLoopofStarpoints:
                filename = '/' + suffix_path(_stemC + '_startpoint' + str(i) + '.txt')
            else:
                filename = '/' + suffix_path(_stemC + '.txt')
            res = find_Opt(target=target, startpoint=startpoint)
            _fvC = res.pop('fval', None)      # result FILES keep the classic 3-key shape
            save_betanabla_res_txt(filename, res)
            if RunLoopofStarpoints and _fvC is not None and 'Error' not in res:
                if _best_C is None or _fvC < _best_C[0]:
                    _best_C = (_fvC, i, dict(res))
        if RunLoopofStarpoints and _best_C is not None and not _subset_envC:
            print('MULTISTART_WINNER (CRRA=%g): startpoint %s  f=%.10g  %r'
                  % (_crra, _best_C[1], _best_C[0], _best_C[2]))
            print('MULTISTART_WINNER (CRRA=%g): canonical %s updated (consumed by Step 2 / Parameters.py)'
                  % (_crra, suffix_path(_stemC + '.txt')))
            save_betanabla_res_txt('/' + suffix_path(_stemC + '.txt'), _best_C[2])
    base_params['CRRA'] = _crra_saved


Plot_other_CRRA_values = False
if Plot_other_CRRA_values:
    target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
    # CRRA=1 
    del EstTypeList
    base_params['CRRA'] = 1
    BaseType = KinkedRconsumerType(**base_params)
    EstTypeList = []
    for j in range(TypeCount):
        EstTypeList.append(deepcopy(BaseType))
        EstTypeList[-1].seed = j
    [splurge,beta,nabla] = load_betanabla_res_txt('/Result_AllTarget_CRRA_1.txt')
    CRRA1=FagerengObjFunc(splurge,beta,nabla,estimation_mode=False,target=target)
    
    # CRRA=2
    del EstTypeList
    base_params['CRRA'] = 3
    BaseType = KinkedRconsumerType(**base_params)
    EstTypeList = []
    for j in range(TypeCount):
        EstTypeList.append(deepcopy(BaseType))
        EstTypeList[-1].seed = j
    [splurge,beta,nabla] = load_betanabla_res_txt('/Result_AllTarget_CRRA_3.txt')
    CRRA3=FagerengObjFunc(splurge,beta,nabla,estimation_mode=False,target=target)
    
    # Plot Lorentz curve
    plt.figure()
    LorenzAxis = np.arange(101,dtype=float)
    plt.plot(LorenzAxis,CRRA1['Lorenz_Data_Adj'] ,'b-',linewidth=2)
    plt.plot(LorenzAxis,CRRA3['Lorenz_Data_Adj']    ,'r:',linewidth=2)
    plt.scatter(np.array([20,40,60,80,100]),np.hstack([lorenz_target,1]),c='black', marker='o')
    plt.xlabel('Liquid wealth percentile',fontsize=12)
    plt.ylabel('Cumulative liquid wealth share',fontsize=12)
    plt.legend(['CRRA=1','CRRA = 3','Data'])
    make_figs('LiquWealth_Distribution_comparison_CRRA', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot()  
    
    # Plot Agg MPCx
    plt.figure()
    xAxis = np.arange(0,5)
    plt.plot(xAxis,CRRA1['simulated_MPC_mean_add_Lottery_Bin'] ,'b-',linewidth=2)
    plt.plot(xAxis,CRRA3['simulated_MPC_mean_add_Lottery_Bin']    ,'r:',linewidth=2)
    plt.scatter(xAxis,Agg_MPCX_target,c='black', marker='o')
    plt.legend(['CRRA=1','CRRA = 3','Fagereng, Holm and Natvik (2021)'])
    plt.xticks(np.arange(min(xAxis), max(xAxis)+1, 1.0))
    plt.xlabel('year')
    plt.ylabel('% of lottery win spent')
    make_figs('AggMPC_LotteryWin_comparison_CRRA', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot()  
    
    # Table initial MPCs along wealth q
    
    def mystr2(number):
        if not np.isnan(number):
            out = "{:.2f}".format(number)
        else:
            out = ''
        return out
    
        
    output  ="\\begin{tabular}{@{}lcccccc@{}} \n"
    output +="\\toprule \n"
    output +="                  & \multicolumn{5}{c}{MPC} &   \\\\   \n"
    output +="                  &  1st WQ  & 2nd WQ  & 3rd WQ & 4th WQ  & Agg  &  K/Y  \\\\  \\midrule \n"
    output +="CRRA=1 &"+mystr2(CRRA1['simulated_MPC_means_smoothed'][3])      + " & "+ mystr2(CRRA1['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(CRRA1['simulated_MPC_means_smoothed'][1])      + " & "+ mystr2(CRRA1['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(CRRA1['simulated_MPC_mean_add_Lottery_Bin'][0])+ " & "+ mystr2(CRRA1['KY_Model'])  + " \\\\ \n"
    output +="CRRA=3 &"+   mystr2(CRRA3['simulated_MPC_means_smoothed'][3])         + " & "+ mystr2(CRRA3['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(CRRA3['simulated_MPC_means_smoothed'][1])         + " & "+ mystr2(CRRA3['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(CRRA3['simulated_MPC_mean_add_Lottery_Bin'][0])   + " & "+ mystr2(CRRA3['KY_Model'])  + " \\\\ \n"
    output +="Data &"+          mystr2(MPC_target[2,3])                                         + " & "+ mystr2(MPC_target[2,2])+ " & "+  \
                                mystr2(MPC_target[2,1])                                         + " & "+ mystr2(MPC_target[2,0]) + " & "+  \
                                mystr2(Agg_MPCX_target[0])                                      + " & "+ mystr2(KY_target)  + " \\\\ \n"
    output +="\\end{tabular}  \n"
    
    
    # Candidate-routed (2026-08-03) — see the Comparison_Splurge_Table note.
    from generated_output import write_generated as _write_generated_crra
    _write_generated_crra(Abs_Path+'/Figures/Comparison_CRRA_Table.tex', output)
    


    
 
    
    



    #%% For testing purposes

Run_3D_Plot         = False
Run_Investigation   = False


if Run_Investigation:
    for this_beta in np.linspace(0.925,0.932,10):
        FagerengObjFunc(0,this_beta ,0.086, target='AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC',investigate=True)
        

if Run_3D_Plot:
    # Define the function to be evaluated
    def my_function(x,y):
        return FagerengObjFunc(0,x,y, target='AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC')
      
          
    x_range = np.linspace(0.925, 0.95, 10)
    y_range = np.linspace(0.006, 0.01, 10)
     
    # Create empty arrays to store the results
    z_values = np.zeros((len(x_range), len(y_range)))
     
    # Evaluate the function using loops
    for i, x in enumerate(x_range):
        for j, y in enumerate(y_range):
            if (x + y > 1.05) or  (x + y < 0.98):
                z_values[i, j] = None
            else:
                z_values[i, j] = my_function(x, y)
                
          
                
    # Create a 3D plot
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
     
    # Create meshgrid for plotting
    x_grid, y_grid = np.meshgrid(x_range, y_range)
     
    # Plot the surface
    surf = ax.plot_surface(x_grid, y_grid, z_values.T, cmap='viridis')
     
    # Add labels and title
    ax.set_xlabel('X-axis')
    ax.set_ylabel('Y-axis')
    ax.set_zlabel('Z-axis')
    ax.set_title('Function Evaluation over 2D Grid (using loops)')
     
    # Add color bar
    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10)
     
    # Show the plot
    show_plot()




    




    


# ---- Provenance sidecar (schema v2; best-effort, never aborts) -------------
try:
    import os as _prov_os, sys as _prov_sys
    _prov_ha = _prov_os.path.abspath(_prov_os.path.join(
        _prov_os.path.dirname(_prov_os.path.abspath(__file__)), '..'))
    if _prov_ha not in _prov_sys.path:
        _prov_sys.path.insert(0, _prov_ha)
    import provenance as _prov
    _prov.emit([".", "Figures"], command=" ".join(_prov_sys.argv), argv=_prov_sys.argv,
               label="step1-splurge-estimation", register=False)
except Exception as _prov_e:
    print(f"[provenance] sidecar emit skipped (non-fatal): {_prov_e}")
