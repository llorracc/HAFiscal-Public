#!/usr/bin/env python
"""a-indexed Step-2 (β/∇) estimation — splurge-in-budget / BUG-033 consistent analogue of estim_phase2_tm.py.

Under splurge-in-budget the budget identity is a_t = m_t - c_actual(m_t, xi_t) with
c_actual = (1-varsigma) * cFunc(m_t) + varsigma * xi_t. The m-indexed TM
collapses the ξ-variance (BUG-033); the a-indexed TM preserves it. For
full consistency with Phase 5 (a-indexed baseline production), Step 2
β/∇ should be re-estimated under the same a-indexed convention.

This script is a minimal edit of estim_phase2_tm.py:
  - build_tm_agg_fiscal → build_tm_agg_fiscal_a
  - no (1-Splurge) * aPol adjustment — the a-grid already holds post-
    consumption assets under splurge-in-budget accounting.
  - output to _TM_a.txt

Usage:
    cd Code/HA-Models/FromPandemicCode
    python estim_phase2_tm_a.py                    # all 3 edTypes
    HAFISCAL_EDTYPES=1,2 python estim_phase2_tm_a.py  # subset
"""

import os, sys, time
import numpy as np
from copy import deepcopy
from HARK.distributions import Uniform
from HARK.utilities import get_percentiles, get_lorenz_shares
from HARK.estimation import minimize_nelder_mead

# Owner ruling 2026-08-19 evening: S2 machinery = S1 machinery. The theta-barrier maps
# and search box are the SAME SST Step-1 uses (Code/HA-Models/step1_param.py) — imported,
# not duplicated, per the SST-for-duplicated-machinery convention.
_ha_models_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
if _ha_models_dir not in sys.path:
    sys.path.insert(0, _ha_models_dir)
import step1_param as _s1param
# BUG-079 (2026-08-20): the model median is the CDF-interpolated quantile of the pooled
# gridded ergodic distribution (Code/HA-Models/dist_quantile.py), not a sample quantile of
# its entries — the latter snapped the median to grid levels (3-11% apart) and made every
# group's optimum a corner solution at a cliff. HAFISCAL_STEP2_MEDIAN=node restores the
# pre-fix call for bisection/anchor reproduction.
from dist_quantile import step2_median as _step2_median, median_mode as _median_mode
print(f"[step2-median] HAFISCAL_STEP2_MEDIAN={_median_mode()} "
      "(interp = CDF-interpolated median of the gridded distribution, BUG-079; node = pre-fix snapping)")


def _fit_start_under_cap(b0, n0, cap_eff_e, kappa_e, margin=1e-3):
    """Nudge a warm start whose TOP ATOM (b0 + kappa*n0) sits at/above cap_eff into
    theta-representable territory: keep beta, shrink nabla so the top atom clears
    cap_eff by `margin` (to_theta_bn needs a FINITE t_hi). Fires only for stale or
    corrupt saved calibrations — every current calibration is strictly below cap."""
    a_hi = float(b0) + kappa_e * float(n0)
    if a_hi < cap_eff_e - 1e-12:
        return float(b0), float(n0)
    n_new = max((cap_eff_e - margin - float(b0)) / kappa_e, 1e-4)
    print(f"  [S2-COBYQA] warm start's top atom {a_hi:.6f} >= cap_eff {cap_eff_e:.6f}; "
          f"nabla nudged {float(n0):.6f} -> {n_new:.6f} to make theta finite")
    return float(b0), n_new

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# R-e item-2 bonded pair: under HAFISCAL_CALIB_TARGET_INCOME=net the paired
# _netinc calibration file may not exist yet — THIS run creates it. Let the
# module imports below seed from the gross-convention file (starting values
# only) without weakening the consumer-side HALT in resolve_calib_path.
os.environ.setdefault('HAFISCAL_CALIB_BOOTSTRAP', '1')

import EstimParameters as ep
from EstimParameters import (
    init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
    DiscFacCount, CRRA, AgentCountTotal, Rfree_base,
    data_LorenzPts, data_medianLWPI, data_EducShares,
    GICmaxBetas, gic_capped_beta, minBeta,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution

# BUG-051 matched-pair guard: this is a guarded TM-a entry point — require the
# interpretation (CDC vs ESC) to be set EXPLICITLY rather than silently
# defaulting to CDC. Runs at module import, after env + sys.path setup and
# before the heavy economy build below. (importing tm_methods above already
# put the HA-Models dir on sys.path, so _interpretation resolves here.)
# Note: mc_tm_dist_eval.py imports this module with HAFISCAL_EDTYPES='' but it
# always sets HAFISCAL_INTERPRETATION first, so the require check passes there.
from _interpretation import get_interpretation as _get_interp_require
_get_interp_require(require=True)

Splurge = ep.Splurge
UBspell_normal = ep.UBspell_normal
num_types = 3

print(f"a-indexed TM Phase 2 estimation (splurge-in-budget consistent)")
print(f"Splurge={Splurge:.6f}  CRRA={CRRA}  Rfree={Rfree_base[0]}  DiscFacCount={DiscFacCount}")
print(f"AgentCountTotal={AgentCountTotal} (used for agent weighting, not simulation)")

# ---- Build economy (same as estim_phase2_tm.py) ----
t0_setup = time.time()
InfHorizonTypeAgg_d = AggFiscalType(**init_dropout)
InfHorizonTypeAgg_d.cycles = 0
InfHorizonTypeAgg_h = AggFiscalType(**init_highschool)
InfHorizonTypeAgg_h.cycles = 0
InfHorizonTypeAgg_c = AggFiscalType(**init_college)
InfHorizonTypeAgg_c.cycles = 0
AggDemandEcon = AggregateDemandEconomy(**init_ADEconomy)
InfHorizonTypeAgg_d.get_economy_data(AggDemandEcon)
InfHorizonTypeAgg_h.get_economy_data(AggDemandEcon)
InfHorizonTypeAgg_c.get_economy_data(AggDemandEcon)
BaseTypeList = [InfHorizonTypeAgg_d, InfHorizonTypeAgg_h, InfHorizonTypeAgg_c]

# BUG-095 (2026-08-26 23:50): the unemployed-state income process was a hard-coded point mass
# (PermShk = 1, TranShk = IncUnemp) here — the published-QE convention — regardless of
# `perm_shocks_during_unemployment` (HAFISCAL_PERM_DURING_UNEMP). BUG-090's fix (895a5cbe)
# routed the MC estimator (EstimAggFiscalMAIN.py) and the welfare drivers through the
# income-process SST but missed THIS file, the production Step-2 engine since 2026-06-23
# (HAFISCAL_STEP2_SIM_ENGINE=tm_ergodic): the default world's committed betas are perm-OFF
# estimates driving a perm-ON world. Found when a perm-OFF "matched" re-estimation returned the
# default betas to 1e-8. Blast radius: with tran_shocks_during_unemployment False the SST returns
# the SAME single-atom distribution when perm is off, so the as-corrected calibration (perm off)
# is byte-identical to the old construction; only the perm-ON (default-world) estimation changes.
# HAFISCAL_STEP2_LEGACY_UNEMP_INCSHK=1 restores the hard-coded point mass (reproduction of the
# pre-fix default-world estimates).
from income_process_sst import build_unemployed_inc_shk_dstn as _build_unemp_inc
_legacy_unemp = os.environ.get('HAFISCAL_STEP2_LEGACY_UNEMP_INCSHK', '').strip().lower() in ('1', 'on', 'true', 'yes')
for ThisType in BaseTypeList:
    _emp0 = ThisType.IncShkDstn[0]
    if _legacy_unemp:
        _p_on, _t_on = False, False
    else:
        _p_on = bool(getattr(ThisType, 'perm_shocks_during_unemployment', False))
        _t_on = bool(getattr(ThisType, 'tran_shocks_during_unemployment', False))
    IncomeDstn_unemp = _build_unemp_inc(_emp0, ThisType.IncUnemp, _p_on, _t_on)
    IncomeDstn_unemp_nobenefits = _build_unemp_inc(_emp0, ThisType.IncUnempNoBenefits, _p_on, _t_on)
    # earnings phase: the employment block wrapped to [growing | matured] (same objects; identity when off)
    ThisType.IncShkDstn = [__import__('earnings_phase').wrap_list([_emp0] + [IncomeDstn_unemp]*UBspell_normal + [IncomeDstn_unemp_nobenefits])]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn
print(f"[step2-unemp-incshk] perm_shocks_during_unemployment={'LEGACY point mass' if _legacy_unemp else _p_on} "
      f"-> unemployed-state atoms: {len(IncomeDstn_unemp.pmv)} (1 = point mass; >1 = employed psi marginal)", flush=True)

TypeList = []
n = 0
for e in range(num_types):
    for b in range(DiscFacCount):
        DiscFac = DiscFacDstns[e].atoms[0][b]
        AgentCount = int(np.floor(AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]))
        ThisType = deepcopy(BaseTypeList[e])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = DiscFac
        ThisType.seed = n
        TypeList.append(ThisType)
        n += 1

AggDemandEcon.agents = TypeList
# ATI-ESTIMATION DEFAULT (owner ruling 2026-07-27): the ConsumedATI routing is this
# surface's default solver accelerator — measured 3.05× per eval-set and a 7-minute warm
# re-estimation; consistency vs the EGM calibration: β to ~6 digits in every group, worst
# ∇ shift 0.714% ≤ the 2% ∇ budget (ratified 2026-07-27 — ∇ is a weakly-identified spread;
# the 0.1% β standard priced a 3× mode out of default over a 1.3e-4-absolute wobble).
# Entry-point-scoped like the tail state; explicit env always wins; EGM remains one env
# var away (HAFISCAL_STEP5_ATI=0) as the cross-check.
# BUG-101 (2026-08-28, found by the Econ-4 curvature diagnostic): this setdefault used to
# sit INSIDE the objective, after its solve, so the initial solve below and the FIRST
# objective evaluation of every process ran EGM (the router's unset default) and every later
# evaluation ATI -- a 1.4e-4 gap between the centre value and its own re-evaluation. Set it
# here, before any solve, so one engine serves the whole estimation.
os.environ.setdefault('HAFISCAL_STEP5_ATI', '1')
AggDemandEcon.solve()
print(f"Economy setup + initial solve: {time.time()-t0_setup:.1f}s")

# Speedup remedy A (2026-08-20, benchmark-gated): fork-parallel cohort solves inside
# each objective evaluation via the validated bit-identical parallel_solve machinery
# (3.88x at 21 cohorts on the expensive-solve regime). OPT-IN because per-eval WARM
# solves are cheap and fork overhead may eat the gain -- the P3 composed benchmark
# decides whether this default-flips. HAFISCAL_STEP2_PARALLEL_SOLVE=N installs an
# N-worker parallel eco.solve; unset/0 = the serial path, byte-identical.
if int(os.environ.get('HAFISCAL_STEP2_PARALLEL_SOLVE', '0') or '0') > 0:
    if os.environ.get('HAFISCAL_STEP2_DIRTY_SOLVE', '1') == '1':
        # A x C interaction guard: the parallel replacement's signature has no
        # only_agents; composing them would TypeError mid-battery. Dirty-solve wins
        # (the P3 benchmark adjudicates which default-flips); A is skipped LOUDLY.
        print("[remedy A] SKIPPED: HAFISCAL_STEP2_DIRTY_SOLVE=1 is on and the parallel "
              "solve has no only_agents mode -- running dirty-serial instead")
    else:
        os.environ.setdefault('HAFISCAL_PARALLEL_SOLVE', os.environ['HAFISCAL_STEP2_PARALLEL_SOLVE'])
        from parallel_solve import install_parallel_solve_via_env
        install_parallel_solve_via_env(AggDemandEcon)
        print(f"[remedy A] parallel eco.solve installed "
              f"(workers={os.environ['HAFISCAL_PARALLEL_SOLVE']})")


# ---- a-indexed TM objective function ----

def betas_obj_func_educ_tm_a(beta, spread, GICx, educ_type=2, print_mode=False):
    """a-indexed TM objective: same targets as m-indexed betas_obj_func_educ_tm
    but preserves ξ-variance in the wealth distribution (BUG-033 fix)."""
    dfs = Uniform(beta - spread, beta + spread).discretize(DiscFacCount)
    for thedf in range(DiscFacCount):
        if dfs.atoms[0][thedf] > gic_capped_beta(educ_type, np.exp(GICx) / (1 + np.exp(GICx))):
            dfs.atoms[0][thedf] = gic_capped_beta(educ_type, np.exp(GICx) / (1 + np.exp(GICx)))
        elif dfs.atoms[0][thedf] < minBeta:
            dfs.atoms[0][thedf] = minBeta

    TypeListNewEduc = []
    for b_idx in range(DiscFacCount):
        AgentCount = int(np.floor(AgentCountTotal * data_EducShares[educ_type] * dfs.pmv[b_idx]))
        ThisType = deepcopy(BaseTypeList[educ_type])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = dfs.atoms[0][b_idx]
        TypeListNewEduc.append(ThisType)

    TypeListAll = AggDemandEcon.agents
    TypeListAll[educ_type * DiscFacCount:(educ_type + 1) * DiscFacCount] = TypeListNewEduc
    AggDemandEcon.agents = TypeListAll
    # Speedup remedy C (owner: "fix this waste", 2026-08-20): only the swapped group's
    # 7 types need solving -- the other 14 keep their converged solutions (economy.solve
    # would re-walk them warm, ~1 sweep each: measured ~10-20% of an eval, not the 2x
    # first claimed -- the warm-start machinery already absorbed most of the redundancy).
    # HAFISCAL_STEP2_DIRTY_SOLVE=0 restores the full-list solve (byte-identical path).
    if os.environ.get('HAFISCAL_STEP2_DIRTY_SOLVE', '1') == '1':
        AggDemandEcon.solve(only_agents=TypeListNewEduc)
    else:
        AggDemandEcon.solve()

    # Build a-indexed TM + ergodic for this edType's 7 agents
    total_weight = sum(t.AgentCount for t in TypeListNewEduc)
    a_vals_list = []
    w_vals_list = []

    # Interpretation single source (CDC vs ESC): drives BOTH the TM kernel asset
    # rule (passed to build_tm_agg_fiscal_a) and the (1-ς) household correction
    # below. Read from get_interpretation() so the TM-a kernel is always matched
    # to the agent/calibration regime, never a stale hardcoded 'CDC'. BUG-051.
    _tm_interp = get_interpretation()

    # HAFISCAL_DIST_TAIL_BUCKET (default 'off' = byte-identical path below):
    # R-d per-atom analytic Pareto tail-bucket
    # (plans/20260726_dist-grid-top-scoping_plan.md, capstone + R-c x R-d).
    # The TM lottery piles all ergodic mass above the dist-grid top
    # (dist_aGrid_max) into the top node; grid height cannot fix the cap
    # atom's fat tail (deep wealth decay ~T^(1-alpha), alpha~1.5). When on,
    # each ATOM's marginal ergodic gets an analytic truncated-Pareto tail
    # above its own grid top, exponent = the atom's OWN measured tail alpha
    # (Kesten root via per_atom_alpha.py as fallback). Per-atom because the
    # POOLED exponent drifts with window height (mixture artifact) -- the
    # v2/v3 pooled-prototype failure mode.
    _tb_env = os.environ.get('HAFISCAL_DIST_TAIL_BUCKET', 'off').strip().lower()
    _tb_variant = {'on': 'pile', 'pile': 'pile', 'anchored': 'anchored'}.get(_tb_env)
    if _tb_variant is None and _tb_env not in ('off', '0', ''):
        print(f"WARNING: HAFISCAL_DIST_TAIL_BUCKET={_tb_env!r} not recognized "
              "(off|on|pile|anchored); tail bucket stays OFF")

    # HAFISCAL_DIST_TAIL_STATE (default 'off' = byte-identical path below):
    # P4' dynamics-level tail state (scope TS-1). When on,
    # build_tm_agg_fiscal_a appends one analytic Pareto tail state per micro
    # state (TM is (A+1)*J; per-atom Kesten alpha; inflow = the clipped-at-top
    # lottery mass; outflow = death + m^alpha stay / truncated-Pareto
    # re-entry), and the ergodic is consumed via tm_methods.tail_state_readout
    # (grid part + K Pareto segments + terminal atom) instead of the (J, A)
    # reshape. Mutually exclusive with HAFISCAL_DIST_TAIL_BUCKET (the builder
    # raises if both are on); unknown values raise inside the builder's own
    # flag parse. See plans/20260726_dist-grid-top-scoping_plan.md P4'.
    # EPOCH 2026-07-27: the tail state is DEFAULT-ON for the ESTIMATION surface
    # in the default world (the installed calibration was estimated with it; the
    # objective must reproduce its own moments). Surface-scoped setdefault — the
    # Step-5a path keeps global default 'off' (it refuses tail TMs by scope and
    # is measured top-indifferent at 3e-5). as-corrected keeps the paper's
    # read-out (no tail state). Explicit env always wins.
    if os.environ.get('HAFISCAL_WORLD', 'default').strip().lower() != 'as-corrected':
        os.environ.setdefault('HAFISCAL_DIST_TAIL_STATE', 'on')
    # ATI-ESTIMATION DEFAULT (owner ruling 2026-07-27): applied at MODULE level, before the
    # initial solve -- see the block above `AggDemandEcon.solve()` (BUG-101: it used to be set
    # HERE, after this objective's first solve, so the first evaluation in every process
    # solved by EGM and the rest by ATI).
    _ts_env = os.environ.get('HAFISCAL_DIST_TAIL_STATE', 'off').strip().lower()
    _ts_on = _ts_env in ('1', 'on')
    _tb_mod = None
    if _tb_variant is not None:
        # Lazy load (decay_form is a plain dir, not a package): by file path,
        # cached in sys.modules so repeated objective evals load once.
        _tb_mod = sys.modules.get('disttop_tail_bucket')
        if _tb_mod is None:
            import importlib.util as _tb_ilu
            _tb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', 'decay_form', 'disttop_tail_bucket.py')
            _tb_spec = _tb_ilu.spec_from_file_location('disttop_tail_bucket', _tb_path)
            _tb_mod = _tb_ilu.module_from_spec(_tb_spec)
            _tb_spec.loader.exec_module(_tb_mod)
            sys.modules['disttop_tail_bucket'] = _tb_mod
            print(f"HAFISCAL_DIST_TAIL_BUCKET={_tb_env}: per-atom analytic "
                  f"Pareto tail-bucket ON (variant={_tb_variant})")

    for agent in TypeListNewEduc:
        agent_w = agent.AgentCount / total_weight if total_weight > 0 else 1.0 / DiscFacCount
        # aCount=200 (was 100) per tm_methods.py:4434 comment: aCount=100 produces
        # ~30% K/Y bias from upper-grid tail truncation when β·Rfree is near GIC
        # (which is exactly the high-β atoms in our distributions). aCount=200
        # drops the bias to <0.1% and is the new default for build_tm_agg_fiscal_a.
        # This was the source of the apparent "TM-a vs MC methodology gap" on
        # HS medianLWPI (-30.8% in the 2026-05-03 ESC TM-a run); not a
        # normalized-vs-level issue but a grid-resolution issue.
        # aCount=200 is the production grid (see comment above). interpretation
        # from the single source (BUG-051) so the TM-a kernel matches the
        # agent/calibration regime.
        # HAFISCAL_TM_ACOUNT (2026-06-10): distribution-grid override. The dist grid is ~1% of
        # the per-eval cost (the 7 solves dominate and are aCount-independent), and the pooled
        # group MEDIAN — a calibration target — carries a ~1.5% quantization bias at aCount=200
        # that converges by ~1600 (jitter 1.49% -> 0.06% vs an N=6400 reference; driven by the
        # two GIC-cap atoms' fat tails). Finer dist grid = nearly-free accuracy on the median
        # target; Lorenz targets are grid-robust either way.
        # BUG-079 (2026-08-20): most of that "quantization" was the sample-quantile call that
        # snapped the median to grid levels; the CDF-interpolated median (dist_quantile.py) is
        # O(h^2) in the level spacing, so aCount=200 no longer carries a first-order median bias.
        _tm_aCount = int(os.environ.get('HAFISCAL_TM_ACOUNT', '200'))
        tm_data = build_tm_agg_fiscal_a(agent, aCount=_tm_aCount, interpretation=_tm_interp)
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])

        dist_aGrid = tm_data['dist_aGrid']
        J = agent.MrkvArray[0].shape[0]
        A = len(dist_aGrid)

        # HAFISCAL_DIST_TAIL_STATE read-out (default off = the unchanged
        # reshape path below): the tail-state ergodic is (A+1)*J, so it MUST
        # be consumed via tail_state_readout — grid part feeds the same
        # per-j appends as today; the pooled tail mass is expanded into K
        # Pareto segments + a terminal atom (exactly mean-preserving). The
        # ESC (1-ς) household correction after the loop then applies to the
        # appended tail nodes automatically (unchanged code order).
        if _ts_on:
            from tm_methods import tail_state_readout as _ts_readout
            _erg_grid, _tail_a, _tail_w = _ts_readout(tm_data, ergodic)
            for j in range(J):
                dstn_j = _erg_grid[j, :]
                mask = dstn_j > 1e-15
                if np.any(mask):
                    a_vals_list.append(dist_aGrid[mask])
                    w_vals_list.append(dstn_j[mask] * agent_w)
            if _tail_w.size and float(np.sum(_tail_w)) > 0.0:
                a_vals_list.append(_tail_a)
                w_vals_list.append(_tail_w * agent_w)
            continue

        # Ergodic layout per build_tm_agg_fiscal_a docstring:
        # [j=0, a=0..A-1, j=1, a=0..A-1, ...] — reshape to (J, A).
        erg = np.asarray(ergodic).reshape(J, A)

        # Per-atom tail bucket (HAFISCAL_DIST_TAIL_BUCKET, default off): replace
        # this atom's top-node pile with an analytic truncated-Pareto tail using
        # the atom's OWN alpha (measured on its ergodic top window; Kesten root
        # via per_atom_alpha.py as fallback; unresolvable alpha => conservative
        # raw append). The atom's MARGINAL over j is pooled -- moment-equivalent
        # to the per-j appends below, since the estimands read only the pooled
        # (a, w) histogram and a-values repeat across j. Mass-preserving, so
        # agent_w weighting survives pooling across atoms.
        if _tb_variant is not None:
            _marg = erg.sum(axis=0)
            _mmask = _marg > 1e-15
            if np.any(_mmask):
                _a_atom = dist_aGrid[_mmask]
                _w_atom = _marg[_mmask] * agent_w
                _x_top = float(dist_aGrid[-1])
                _tb_alpha, _tb_src = _tb_mod.resolve_atom_alpha(
                    _a_atom, _w_atom, _x_top, agent=agent)
                if _tb_alpha is not None:
                    _a_new, _w_new, _tb_diag = _tb_mod.apply_tail_bucket(
                        _a_atom, _w_atom, _tb_alpha, _x_top, variant=_tb_variant)
                    a_vals_list.append(_a_new)
                    w_vals_list.append(_w_new)
                else:
                    a_vals_list.append(_a_atom)
                    w_vals_list.append(_w_atom)
            continue

        for j in range(J):
            dstn_j = erg[j, :]
            mask = dstn_j > 1e-15
            if np.any(mask):
                # dist_aGrid holds the kernel asset state: under CDC this IS the
                # household a_tot; under ESC it is the per-Optimizer a_opt, and the
                # household correction a_tot = (1-ς)·a_opt is applied to a_array
                # after the loop (eq:conv1-ESC; tm_methods.py:4898). BUG-051.
                aNrm_vals = dist_aGrid[mask]
                weights = dstn_j[mask] * agent_w
                a_vals_list.append(aNrm_vals)
                w_vals_list.append(weights)

    a_array = np.concatenate(a_vals_list)
    w_array = np.concatenate(w_vals_list)
    w_array /= np.sum(w_array)

    # ESC household correction (eq:conv1-ESC; tm_methods.py:4898): the kernel grid
    # is the per-Optimizer a_opt; household liquid wealth a_tot = (1-ς)·a_opt. (CDC's
    # grid is already a_tot.) Scales medianLWPI by (1-ς); leaves the scale-invariant
    # Lorenz shares unchanged. Omitting it overstates ESC LW/PI by 1/(1-ς) — the
    # spurious 21-62% "MC-vs-TM gap" diagnosed 2026-06-05 (BUG-051).
    # HAFISCAL_STEP2_WEALTH_LEGACY=1: raw a (no (1-s)) -- diagnostic ONLY. NOT the published Step-2 read-out: the QE
    # Step 2 scaled by (1-Splurge) at every moment (HAFiscal-QE EstimAggFiscalMAIN.py:83,97,105,135,141; verified
    # 2026-08-30), so the default branch below IS the paper's; the switch was dropped from columns A and B that day.
    if _tm_interp == 'ESC' and os.environ.get('HAFISCAL_STEP2_WEALTH_LEGACY', '').strip() != '1':
        a_array = a_array * (1.0 - Splurge)

    medianLWPI = 100.0 * _step2_median(a_array, w_array)   # BUG-079: CDF-interpolated (HAFISCAL_STEP2_MEDIAN)
    LorenzPts = 100.0 * get_lorenz_shares(a_array, weights=w_array,
                                           percentiles=[0.2, 0.4, 0.6, 0.8])

    sumSquares = np.sum((medianLWPI - data_medianLWPI[educ_type]) ** 2)
    sumSquares += np.sum((np.array(LorenzPts) - data_LorenzPts[educ_type]) ** 2)
    distance = np.sqrt(sumSquares)

    if print_mode:
        print(f"  beta={beta:.4f} nabla={spread:.4f} GICx={GICx:.4f}")
        print(f"  medianLWPI: model={medianLWPI[0]:.2f}  data={data_medianLWPI[educ_type]:.2f}")
        print(f"  Lorenz: model=[{', '.join(f'{x:.2f}' for x in LorenzPts)}]  "
              f"data=[{', '.join(f'{x:.2f}' for x in data_LorenzPts[educ_type])}]")
        print(f"  distance={distance:.6f}")

    return distance


# ---- Run estimation ----

_edtypes_env = os.environ.get('HAFISCAL_EDTYPES', '0,1,2')
edtypes_to_run = [int(s) for s in _edtypes_env.split(',') if s.strip()]
print(f"\nEdTypes to estimate: {edtypes_to_run}")

res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Results')
# HAFISCAL_RESULTS_OUT_DIR redirects ALL output writes (the truncate-once below, the
# per-edType β rows, and the footer) to a scratch dir, so a validation run still reads
# the committed calibration as warm-start from res_dir but never clobbers the git-tracked
# ../Results files. (Completes the redirect: previously only the per-edType write honored
# the flag; the truncate@~279 and footer@~485 still hit res_dir and would leave the
# canonical file as just a footer with the β rows gone.)
_out_override = os.environ.get('HAFISCAL_RESULTS_OUT_DIR', '').strip()
out_dir = _out_override if _out_override else res_dir
if _out_override:
    os.makedirs(out_dir, exist_ok=True)
df_base = f"DiscFacEstim_CRRA_{CRRA}_R_{Rfree_base[0]}"
if ep.IncUnemp != 0.7 or ep.IncUnempNoBenefits != 0.5:
    df_base += "_altBenefits"
if Splurge == 0:
    df_base += "_Splurge0"

# ESC-MOD-PHASE3-write: cross-interpretation registry isolation. CDC keeps
# legacy unsuffixed names; ESC tags every output with _ESC.
# Used in two ways below:
#   (a) `_INTERP_SUFFIX` appended to all `_TM_a.txt` writes (so ESC writes
#       to `..._TM_a_ESC.txt` instead of overwriting CDC's `..._TM_a.txt`)
#   (b) Warm-start source path tagged the same way (so ESC warm-starts from
#       its own prior ESC saved cal, not CDC's; missing file → cold start)
import sys as _sys_es
_ha_root_es = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _ha_root_es not in _sys_es.path:
    _sys_es.path.insert(0, _ha_root_es)
from _interpretation import interp_suffix as _interp_suffix, get_interpretation
from _interpretation import calib_suffix as _calib_suffix
# WORLD axis (2026-06-14): the TM-a betas are world-specific too, so isolate by
# interpretation AND world (e.g. '_ESC_ascorrected'). default world -> world
# suffix '' -> byte-for-byte legacy. The warm-start source (line ~318) reads the
# same world-tagged file; missing -> cold start (the spec uses cold anyway).
_INTERP_SUFFIX = _calib_suffix()  # '' (CDC/default) .. '_ESC_ascorrected'

educ_names = ['Dropout', 'Highschool', 'College']

# Default starting points (always position 0 in init_vals_grid below; this
# preserves backward compatibility — HAFISCAL_NUM_STARTS=1 reproduces the
# pre-BUG-036 single-start estimation exactly).
init_vals_default = {0: [0.75, 0.3, 6], 1: [0.93, 0.07, 5], 2: [0.98, 0.015, 6]}

# Multi-start grids per BUG-036: the dropout cohort's Nelder-Mead surface is
# multimodal; single-start lands in a 47×-worse local basin. Multi-start
# reliably finds the global minimum. HS and college have narrower distributions
# and are less basin-trap-prone but get a couple of extra starts as cheap
# insurance.
init_vals_grid = {
    0: [  # Dropout — high-∇, multimodal (BUG-036)
        [0.75, 0.30, 6.0],   # script default
        [0.70, 0.34, 6.0],   # near-ESC anchor
        [0.65, 0.40, 5.0],   # low-β / wide-∇ probe (best basin in BUG-036 diag)
        [0.80, 0.20, 6.5],   # high-β / narrow-∇ probe
    ],
    1: [  # Highschool — narrow ∇
        [0.93, 0.07, 5.0],   # script default
        [0.90, 0.11, 4.5],   # post-fix-CDC-like
        [0.95, 0.05, 5.5],   # tighter
    ],
    2: [  # College — very narrow ∇
        [0.98, 0.015, 6.0],  # script default
        [0.97, 0.030, 7.0],  # mild perturbation
    ],
}

NUM_STARTS = int(os.environ.get('HAFISCAL_NUM_STARTS', '1'))
print(f"\nMulti-start: HAFISCAL_NUM_STARTS={NUM_STARTS}  "
      f"(1 = backward-compat single-start; >1 = run multiple starts and pick best)")

# =0: import-safe fixed-point eval mode (mirrors HAFISCAL_STEP1_RUN_ESTIMATION;
# added 2026-08-22 for the S2 solve-path certification probe — Phase 1 of
# plans_local/20260822-1030h_s2-production-solve-path_plan.md). Everything above
# (BaseTypeList, AggDemandEcon, the objective) is built; the estimation loop and
# every file write below are skipped. The probe execs this file and catches the
# SystemExit, keeping the machinery namespace.
if os.environ.get('HAFISCAL_STEP2_RUN_ESTIMATION', '1') != '1':
    print("[step2-eval-mode] HAFISCAL_STEP2_RUN_ESTIMATION=0: machinery built, "
          "estimation skipped")
    raise SystemExit(0)

# Multi-cohort runs share a single consolidated _TM_a[_ESC].txt; truncate
# once so per-cohort writes can append in order (then footer appends too).
if len(edtypes_to_run) > 1:
    open(os.path.join(out_dir, df_base + "_TM_a" + _INTERP_SUFFIX + ".txt"), 'w').close()

for edType in edtypes_to_run:
    print(f"\n{'='*60}")
    print(f"Estimating {educ_names[edType]} (edType={edType}) via a-indexed TM")
    print(f"{'='*60}")

    # BUG-039 dispatch: HAFISCAL_GICX_MODE = legacy | hardcoded | twophase.
    # See BUGS_private/HAFiscal_BUG-039_GICx_unconditionally_optimized.md
    # and plans/20260502-1145h_fix-BUG-039-GICx-NM-options.md.
    #   hardcoded: 2-D NM (β, ∇); cap pinned at module-load theGICfactor (=0.9995 as of BUG-053,
    #              2026-06-09 — see EstimParameters.py; was 0.999 when this block was written). (DEFAULT post-Phase G)
    #   legacy:    3-D NM (β, ∇, GICx); GICx is a free fit knob. Pre-Phase G default; opt-in for verification.
    #   twophase:  2-D first; if cap binds at converged (β, ∇), refine with 3-D NM.
    # Default flipped 2026-05-03 per Phase G: Phase F evidence (GICx 10× spread with
    # negligible (β,∇) impact) confirms cap is non-load-bearing for all 3 cohorts.
    from EstimParameters import theGICfactor as _theGICfactor
    _GICX_MODE = os.environ.get('HAFISCAL_GICX_MODE', 'hardcoded')
    _GICx_for_factor_0999 = float(np.log(_theGICfactor / (1 - _theGICfactor)))
    if _GICX_MODE not in ('legacy', 'hardcoded', 'twophase'):
        raise ValueError(f"HAFISCAL_GICX_MODE must be 'legacy', 'hardcoded', or 'twophase'; got {_GICX_MODE!r}")
    print(f"[BUG-039] HAFISCAL_GICX_MODE = {_GICX_MODE}")
    if _GICX_MODE == 'hardcoded':
        print(f"[BUG-039 hardcoded] GICx pinned at logit(theGICfactor={_theGICfactor}) = {_GICx_for_factor_0999:.4f}; NM is 2-D (β, ∇)")
        f_temp = lambda x, et=edType: betas_obj_func_educ_tm_a(x[0], x[1], _GICx_for_factor_0999, educ_type=et)
    elif _GICX_MODE == 'twophase':
        print(f"[BUG-039 twophase] phase 1 = 2-D with GICx pinned; phase 2 fires per-start if cap binds")
        f_temp = lambda x, et=edType: betas_obj_func_educ_tm_a(x[0], x[1], _GICx_for_factor_0999, educ_type=et)
    else:  # 'legacy'
        f_temp = lambda x, et=edType: betas_obj_func_educ_tm_a(x[0], x[1], x[2], educ_type=et)

    starts = (init_vals_grid[edType][:NUM_STARTS] if NUM_STARTS > 1
              else [init_vals_default[edType]])

    # BUG-039 Phase E: HAFISCAL_NM_START_FROM_SAVED=1 prepends saved values
    # from DiscFacEstim_*.txt as an additional starting point.
    # Default flipped 2026-05-03 per Phase G: Phase E validated round-trip
    # preservation, so warm-start is on by default. Set =0 to opt out.
    if os.environ.get('HAFISCAL_NM_START_FROM_SAVED', '1') == '1':
        # Read warm-start from the canonical MC saved cal of THIS interpretation.
        # ESC reads `..._ESC.txt`; CDC reads `....txt`. Missing file → cold start.
        # Registry-aware (Phase 3 of registry plan): prefer the registry's
        # saved step2_cal for the matching configuration; fall back to the
        # suffix-named file if no registry entry exists.
        _saved_path = os.path.join(res_dir, df_base + _INTERP_SUFFIX + '.txt')
        try:
            import sys as _sys_reg_ws
            _ha_root_reg_ws = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            if _ha_root_reg_ws not in _sys_reg_ws.path:
                _sys_reg_ws.path.insert(0, _ha_root_reg_ws)
            import _registry as _reg_ws
            _reg_path = _reg_ws.find_warm_start_cal()
            if _reg_path is not None and _reg_path.exists():
                _saved_path = str(_reg_path)
                print(f"[BUG-039 Phase E + registry] warm-start source: {_reg_path}")
        except Exception as _ws_err:
            print(f"[BUG-039 Phase E] registry lookup failed ({_ws_err!r}); using suffix-named file")
        try:
            _saved_text = open(_saved_path).read()
            import re as _re
            _row_pattern = _re.compile(
                r"'EducationGroup':\s*" + str(edType) +
                r".*?'beta':\s*([\d.eE+-]+).*?'nabla':\s*([\d.eE+-]+).*?'GICx':\s*([\d.eE+-]+)"
            )
            _m = _row_pattern.search(_saved_text)
            if _m:
                _saved_start = [float(_m.group(1)), float(_m.group(2)), float(_m.group(3))]
                if NUM_STARTS == 1:
                    # Single-start mode + warm-start: REPLACE default with saved
                    starts = [_saved_start]
                    print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1: replaced single-start "
                          f"default with saved start β={_saved_start[0]:.4f}, ∇={_saved_start[1]:.4f}, "
                          f"GICx={_saved_start[2]:.4f} (from {os.path.basename(_saved_path)})")
                else:
                    # Multi-start: prepend saved + cap at NUM_STARTS
                    starts.insert(0, _saved_start)
                    starts = starts[:NUM_STARTS]
                    print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1: prepended saved start "
                          f"β={_saved_start[0]:.4f}, ∇={_saved_start[1]:.4f}, GICx={_saved_start[2]:.4f} "
                          f"(from {os.path.basename(_saved_path)}; capped to {NUM_STARTS} starts)")
            else:
                print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1 set but no edType={edType} row in {_saved_path}; using legacy starts only")
        except (FileNotFoundError, IOError):
            print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1 set but {_saved_path} not readable; using legacy starts only")

    # BUG-039: for 2-D modes, drop GICx from each starting point.
    if _GICX_MODE in ('hardcoded', 'twophase'):
        starts = [list(s)[:2] for s in starts]
    best_params, best_dist, best_idx = None, np.inf, None
    all_results = []

    # [2026-06-09] live NM progress. HARK's verbose only triggers scipy's final
    # disp summary (no per-iter trace) and exposes no callback, so wrap the
    # objective to log every Nth eval. NM has no fixed total — gauge progress
    # from the objective plateauing + the eval rate. Default on;
    # HAFISCAL_NM_LOG_EVERY=0 disables, any int sets the stride.
    _nm_log_every = int(os.environ.get('HAFISCAL_NM_LOG_EVERY', '5'))

    def _nm_progress(f, tag=''):
        if _nm_log_every <= 0:
            return f
        st = {'n': 0, 'best': float('inf'), 't0': time.time()}

        def g(x):
            v = float(f(x))
            st['n'] += 1
            st['best'] = min(st['best'], v)
            if st['n'] == 1 or st['n'] % _nm_log_every == 0:
                dt = max(time.time() - st['t0'], 1e-9)
                xs = ', '.join(f"{xi:.5f}" for xi in x)
                print(f"  [NM{tag} eval {st['n']}] obj={v:.5g} best={st['best']:.5g} "
                      f"x=[{xs}] ({dt:.0f}s, {st['n']/dt:.2f}/s)", flush=True)
            return v
        return g

    # HAFISCAL_NM_VALIDATE_N_ITERS=N: cap Nelder-Mead at N function calls / iters
    # (mirrors EstimAggFiscalMAIN.py) so the cross-machine orchestrator can run a
    # fast TM smoke (--nm-cap N) before a full convergent run.
    _nm_kwargs = {}
    _nm_cap = os.environ.get('HAFISCAL_NM_VALIDATE_N_ITERS', '').strip()
    if _nm_cap:
        try:
            _nm_kwargs = {'maxfun': int(_nm_cap), 'maxiter': int(_nm_cap)}
            print(f'[NM cap] limiting to {_nm_cap} function calls / iterations')
        except ValueError:
            pass

    # ---- Optimizer dispatch (owner ruling 2026-08-19 evening: S2 machinery = S1) ----
    # DEFAULT 'cobyqa': the SAME engine bundle Step 1 adopted the same evening — scipy
    # COBYQA over the theta-barrier coordinates (t_hi, t_w) with the per-education GIC
    # cap STRUCTURAL in the map (a_hi = cap_eff_e - exp(t_hi)), so the hard clip in
    # betas_obj_func_educ_tm_a can never fire on-path (it is retained as a tripwire).
    # 'nm' = the verbatim legacy machinery (hard clip + Nelder-Mead), the one-knob
    # rollback and the engine that produced the installed calibration and the chain's
    # S2 candidate. The legacy GICx verification modes (legacy/twophase) always run NM.
    _S2_OPTIMIZER = os.environ.get('HAFISCAL_STEP2_OPTIMIZER', 'cobyqa').strip().lower()
    if _S2_OPTIMIZER not in ('cobyqa', 'nm'):
        raise ValueError(f"HAFISCAL_STEP2_OPTIMIZER must be 'cobyqa' or 'nm'; got {_S2_OPTIMIZER!r}")
    if _S2_OPTIMIZER == 'cobyqa' and _GICX_MODE != 'hardcoded':
        print(f"[step2-optimizer] GICx mode {_GICX_MODE!r} is a legacy verification mode "
              f"-> running the legacy NM machinery for it")
        _S2_OPTIMIZER = 'nm'
    if _S2_OPTIMIZER == 'cobyqa':
        from scipy.optimize import minimize as _scipy_minimize
        _gicfac_pin = float(np.exp(_GICx_for_factor_0999) / (1 + np.exp(_GICx_for_factor_0999)))
        _cap_e = float(gic_capped_beta(edType, _gicfac_pin))
        _kappa_e = (DiscFacCount - 1) / DiscFacCount
        _cap_eff_e = _s1param.cap_eff(_cap_e)
        # BUG-083: Step 2's nabla search end is its own (0.55 default, HAFISCAL_STEP2_NABLA_MAX),
        # not Step 1's 0.4 -- which pinned the low-benefits dropout estimate at 0.4000.
        _nabla_max_e = _s1param.step2_nabla_max()
        _bounds_bn = _s1param.theta_box_bn(cap=_cap_e, kappa=_kappa_e, nabla_max=_nabla_max_e)
        _f_theta = (lambda th, et=edType: betas_obj_func_educ_tm_a(
            *_s1param.to_native_bn(th, cap=_cap_e, kappa=_kappa_e),
            _GICx_for_factor_0999, educ_type=et))
        _cobyqa_opts = {'maxfev': int(os.environ.get('HAFISCAL_STEP2_MAXFEV', '1000'))}
        _ftr2 = os.environ.get('HAFISCAL_STEP2_COBYQA_FINAL_TR', '1e-8').strip()
        if _ftr2 and _ftr2.lower() != 'scipy':
            _cobyqa_opts['final_tr_radius'] = float(_ftr2)
        if _nm_cap:
            try:
                _cobyqa_opts['maxfev'] = min(_cobyqa_opts['maxfev'], int(_nm_cap))
            except ValueError:
                pass
        print(f"[step2-optimizer] cobyqa (DEFAULT; owner ruling 2026-08-19: S2 machinery = S1) — "
              f"theta-barrier (t_hi, t_w), cap_e={_cap_e:.6f} STRUCTURAL (clip retired to tripwire), "
              f"kappa={_kappa_e:.6f}, nabla<={_nabla_max_e:g} (HAFISCAL_STEP2_NABLA_MAX; BUG-083), "
              f"opts={_cobyqa_opts}; rollback: HAFISCAL_STEP2_OPTIMIZER=nm")
    else:
        print("[step2-optimizer] nm (legacy machinery: hard clip + Nelder-Mead)")

    for k, x0 in enumerate(starts):
        if NUM_STARTS > 1:
            print(f"\n  --- Start {k+1}/{len(starts)}: x0={x0} ---")
        t0 = time.time()
        if _S2_OPTIMIZER == 'cobyqa':
            _b0, _n0 = _fit_start_under_cap(float(x0[0]), float(x0[1]), _cap_eff_e, _kappa_e)
            _th0 = _s1param.to_theta_bn(_b0, _n0, cap=_cap_e, kappa=_kappa_e)
            _res = _scipy_minimize(_nm_progress(_f_theta, f" e{edType}"), _th0,
                                   method='cobyqa', bounds=_bounds_bn,
                                   options=dict(_cobyqa_opts))
            if getattr(_res, 'nfev', 0) >= _cobyqa_opts['maxfev']:
                print(f"  [S2-COBYQA] MAXFEV_HIT at {_cobyqa_opts['maxfev']} — this endpoint "
                      f"is NOT converged and must not be treated as one")
            _b_opt, _n_opt = _s1param.to_native_bn(np.asarray(_res.x, dtype=float),
                                                   cap=_cap_e, kappa=_kappa_e)
            if _n_opt >= _nabla_max_e * (1 - 1e-6):
                # BUG-083 tripwire: the search end, not the data, chose this nabla.
                print(f"  [S2-COBYQA] NABLA_AT_BOX: nabla={_n_opt:.6f} sits at the search end "
                      f"{_nabla_max_e:g} — this endpoint is bound-constrained, not an interior "
                      f"optimum (raise HAFISCAL_STEP2_NABLA_MAX only if every atom stays positive: "
                      f"nabla < cap/(2 kappa) = {_cap_e / (2 * _kappa_e):.4f})")
            opt = np.array([_b_opt, _n_opt, _GICx_for_factor_0999])
        else:
            opt = minimize_nelder_mead(_nm_progress(f_temp, f" e{edType}"), x0, verbose=(NUM_STARTS == 1), **_nm_kwargs)
        # BUG-039: assemble full (β, ∇, GICx) from the (possibly 2-D) NM result
        if _S2_OPTIMIZER == 'cobyqa':
            pass  # opt already assembled in native units above
        elif _GICX_MODE == 'hardcoded':
            opt = np.array([opt[0], opt[1], _GICx_for_factor_0999])
        elif _GICX_MODE == 'twophase':
            beta_p, spread_p = float(opt[0]), float(opt[1])
            dfs_p = Uniform(beta_p - spread_p, beta_p + spread_p).discretize(DiscFacCount)
            cap_p = gic_capped_beta(edType, _theGICfactor)
            if max(dfs_p.atoms[0]) > cap_p:
                print(f"  [BUG-039 twophase] cap binding at converged (β={beta_p:.4f}, ∇={spread_p:.4f}); running phase 2 (3-D)")
                f_3d = lambda x, et=edType: betas_obj_func_educ_tm_a(x[0], x[1], x[2], educ_type=et)
                opt = minimize_nelder_mead(f_3d, [beta_p, spread_p, _GICx_for_factor_0999], verbose=(NUM_STARTS == 1), **_nm_kwargs)
            else:
                print(f"  [BUG-039 twophase] cap non-binding at converged (β={beta_p:.4f}, ∇={spread_p:.4f}); skipping phase 2")
                opt = np.array([beta_p, spread_p, _GICx_for_factor_0999])
        elapsed = time.time() - t0
        dist = betas_obj_func_educ_tm_a(opt[0], opt[1], opt[2], educ_type=edType)
        all_results.append((k, x0, opt.tolist(), dist, elapsed))
        if NUM_STARTS > 1:
            print(f"    β={opt[0]:.4f} ∇={opt[1]:.4f} GICx={opt[2]:.3f} "
                  f"| distance={dist:.4f} | {elapsed/60:.1f} min")
        if dist < best_dist:
            best_dist = dist
            best_params = opt
            best_idx = k

    if NUM_STARTS > 1:
        print(f"\n  Best basin: start #{best_idx+1} (distance {best_dist:.4f})")
        dist_range = max(r[3] for r in all_results) - min(r[3] for r in all_results)
        print(f"  Distance range across {NUM_STARTS} starts: {dist_range:.4f}")
        if dist_range > 0.1:
            print(f"  ⚠ STRONG basin variation (range > 0.1) — confirms BUG-036 risk for this cohort")

    GICfactor = np.exp(best_params[2]) / (1 + np.exp(best_params[2]))
    print(f"\nFinished {educ_names[edType]}")
    print(f"  Beta={best_params[0]:.4f}  Nabla={best_params[1]:.4f}  GIC factor={GICfactor:.4f}")

    # Print the NEWLY-ESTIMATED discretized + GIC-clipped betaDistr (the distribution just
    # constructed at this optimum), labelled so it is unambiguously the new one — the load-time
    # betaDistr print in Parameters.py shows the STALE on-disk calibration during re-estimation
    # and is suppressed via HAFISCAL_QUIET_BETADISTR (BUG-053 followup, 2026-06-09).
    _gicfac_new = float(np.exp(best_params[2]) / (1 + np.exp(best_params[2])))
    _cap_new = gic_capped_beta(edType, _gicfac_new)
    _atoms_new = np.clip(
        Uniform(best_params[0] - best_params[1], best_params[0] + best_params[1]).discretize(DiscFacCount).atoms[0],
        minBeta, _cap_new)
    _n_at_cap_new = int(np.sum(_atoms_new >= _cap_new - 1e-12))
    print(f"  [newly estimated: EducationGroup {edType}] betaDistr : {np.round(_atoms_new, 4).tolist()}"
          f"  [GIC cap={_cap_new:.5f} (GPF={_gicfac_new:.5f}); {_n_at_cap_new}/{DiscFacCount} at cap]")

    betas_obj_func_educ_tm_a(best_params[0], best_params[1], best_params[2],
                             educ_type=edType, print_mode=True)

    suffix = f"_edType{edType}" if len(edtypes_to_run) == 1 else ""
    out_path = os.path.join(res_dir, df_base + suffix + "_TM_a" + _INTERP_SUFFIX + ".txt")
    # HAFISCAL_RESULTS_OUT_DIR: redirect the per-edType OUTPUT write to a scratch
    # dir (basename preserved) so a cross-machine / parallel run reads the committed
    # calibration as warm-start but never clobbers the git-tracked ../Results files
    # (the orchestrator gathers from the scratch dir). Mirrors EstimAggFiscalMAIN.py.
    _out_dir_override = os.environ.get('HAFISCAL_RESULTS_OUT_DIR', '').strip()
    if _out_dir_override:
        os.makedirs(_out_dir_override, exist_ok=True)
        out_path = os.path.join(_out_dir_override, os.path.basename(out_path))
    mode = 'w' if suffix else 'a'
    with open(out_path, mode) as f:
        # float() the np.array entries: under numpy>=2 (numpy.float64) repr() would emit
        # "np.float64(...)" which ast.literal_eval (run_phase2_parallel.py merge,
        # adaptive_grid_tm._read_estim_record) cannot parse. Bare floats are numpy-version
        # independent and match the existing/QE-lineage calibration files. (BUG-053 audit.)
        f.write(repr({'EducationGroup': edType, 'beta': float(best_params[0]),
                       'nabla': float(best_params[1]), 'GICx': float(best_params[2])}) + '\n')
    print(f"  Wrote {out_path}")

# Footer
if len(edtypes_to_run) == 3:
    out_path = os.path.join(out_dir, df_base + "_TM_a" + _INTERP_SUFFIX + ".txt")
    with open(out_path, 'a') as f:
        f.write(f"\nParameters: R = {round(Rfree_base[0],2)}, CRRA = {round(CRRA,2)}, "
                f"IncUnemp = {round(ep.IncUnemp,2)}, IncUnempNoBenefits = {round(ep.IncUnempNoBenefits,2)}, "
                f"Splurge = {Splurge}\n")
    # BUG-121 (2026-09-03): the consumers (Parameters.py -> Steps 5a/5b; step4/hh_setup -> the HANK
    # stage) read the UN-tagged `df_base + calib_suffix + .txt`, not this `_TM_a` file — without the
    # mirror a `do_all` re-estimate is written and never used (both 2026-09-02 cold runs ran Steps 4/5
    # on the tracked betas). The canonical wrapper mirrors; the engine now does too, on its own path.
    from step2_mirror import mirror_consolidated as _mirror_consolidated
    _mirror_consolidated(out_path, out_dir, df_base, _INTERP_SUFFIX)

print(f"\nDone.")
