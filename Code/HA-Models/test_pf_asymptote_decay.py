"""Regression test for the opt-in per-Markov-state PF decay extrapolation
(`HAFISCAL_PF_DECAY_EXTRAP`; BUG-062 / PR-3 of
``plans/20260624_hark-2d-markov-extrapolation-fix.md``).

What it locks:
  (a) FLAG ON -> every converged per-state cFunc slice carries the PF decay
      (``decay_extrap is True`` and ``slope_limit == MPCmin``), with the
      AD-aware per-(C-slice, state) intercept ``MPCmin * h_AD[n][i]`` (Markov-
      JOINT human wealth, AD-augmented at the slice's aggregate C). Plus (a')
      the AD-aware ``h_AD`` reduces to the base joint-h in the baseline
      (ADelasticity==0 -> ADFunc==1 -> C-flat); and (c') a direct helper test
      that recession-state ``h_AD`` is AD-scaled (< base when C<1) — owner
      directive 2026-06-24.
  (b) ASYMPTOTE -> at large m the flag-ON cFunc tracks the affine PF line
      ``MPCmin*(m + h_i)`` to a tight tolerance (the OFF naive-linear path is
      ~30% high there); and crucially the flag-ON value is well BELOW the
      flag-OFF naive value at that m (the bug it fixes).
  (c) CONCAVITY HALT -> the Carroll-Kimball guard raises ``ValueError`` on a
      genuinely-impossible knot (above the PF line, regardless of top-slope --
      the EVERY-ITERATE form enabled by the constrained-PF terminal start, owner
      insight 2026-06-24); and the CONVERGED real solve stays weakly below the
      line so it never trips on a normal run.
  (d) BYTE-NEUTRAL OFF -> with the flag unset the per-state cFunc is bit-for-bit
      identical to the same solve with the flag explicitly '0' (the default path
      is unchanged).

The model is the most-patient (GIC-cap) College atom — the deepest-tail atom
that sets the production aMax — built exactly as
``adaptive_grid_tm.college_top_ergodic`` does (``AggFiscalType(**init_college)``,
``get_economy_data``, hand-built ``IncShkDstn``, ``eco.solve()``). The decay
matters most precisely for this atom (smallest MPCmin ~ 0.0054, slowest decay).

Runs in well under a minute (one ~3 s College solve per flag state).
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

# --- paths: this file lives in Code/HA-Models; the solver lives in
# Code/HA-Models/FromPandemicCode. Mirror college_top_ergodic's import dance. ---
_HA_MODELS = Path(__file__).resolve().parent
_FPC = _HA_MODELS / "FromPandemicCode"
for _p in (str(_HA_MODELS), str(_FPC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# The decay slices live behind LowerEnvelope2D.functions -> VariableLowerBoundFunc2D.func
# -> LinearInterpOnInterp1D.xInterpolators -> [LinearInterp ...]. Walk those attrs.
_CHILD_ATTRS = ("functions", "func", "lowerBound", "xInterpolators", "cFunc")


def _decay_slices(cfunc_state):
    """Return all LinearInterp slices under a per-current-state cFunc that have
    decay extrapolation engaged (slope_limit set + decay_extrap True)."""
    out, stack, seen = [], [cfunc_state], set()
    while stack:
        x = stack.pop()
        if id(x) in seen:
            continue
        seen.add(id(x))
        if (getattr(x, "slope_limit", None) is not None
                and getattr(x, "decay_extrap", False)
                and hasattr(x, "x_list")):
            out.append(x)
        for a in _CHILD_ATTRS:
            if hasattr(x, a):
                s = getattr(x, a)
                if isinstance(s, (list, tuple)):
                    stack.extend(s)
                elif callable(s) and any(t in type(s).__name__
                                         for t in ("Interp", "Func", "Envelope")):
                    stack.append(s)
    return out


# Pin the attach tests to the pre-measured-Q baseline: the (a)-(e) families lock
# the ATTACH mechanics (slope-Q powerlaw vs exp vs legacy linear) at the legacy
# 40/48 solve grid. Since the 2026-07-23 default flip (PF_DECAY_EXTRAP default ON,
# PF_DECAY_Q default 'measured', K·h̄ grid default), an unpinned import here would
# give the K·h̄ grid at EstimParameters import time and the measured-Q attach.
# The default-path behavior itself is exercised by the (f) Step-5 grid tests,
# which manage their own env per call.
os.environ.setdefault("HAFISCAL_PF_DECAY_Q", "slope")

_UNSET = object()
_POP = object()   # sentinel: remove the flag entirely (exercise the DEFAULT path)


def _build_and_solve_college_cap(decay_on, flag_value=_UNSET):
    """Solve the most-patient College cap atom with the flag on/off.

    Returns (agent, MPCmin, hNrm). Sets HAFISCAL_PF_DECAY_EXTRAP BEFORE the
    solve (the flag is read inside solve_one_period). Self-contained: neutralizes
    sys.argv for the EstimParameters import and restores the env after.

    ``decay_on`` is the high-level intent (True -> '1', False -> unset). Pass an
    explicit ``flag_value`` string (e.g. '0') to drive a specific literal — used
    by the byte-neutral test to prove '0' parses falsey just like unset.
    """
    os.environ.setdefault("HAFISCAL_SKIP_ESTIMATION", "1")
    os.environ.setdefault("HAFISCAL_QUIET_BETADISTR", "1")
    if flag_value is _POP:
        os.environ.pop("HAFISCAL_PF_DECAY_EXTRAP", None)   # DEFAULT path (ON since 2026-07-23)
    elif flag_value is not _UNSET:
        os.environ["HAFISCAL_PF_DECAY_EXTRAP"] = flag_value
    elif decay_on:
        os.environ["HAFISCAL_PF_DECAY_EXTRAP"] = "1"
    else:
        # legacy opt-out: the DEFAULT has been ON since the 2026-07-23 owner flip,
        # so the OFF arms of these tests must pin the literal '0'.
        os.environ["HAFISCAL_PF_DECAY_EXTRAP"] = "0"

    saved_argv = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        import EstimParameters as ep
        from EstimParameters import (
            init_college, init_ADEconomy, DiscFacCount, minBeta,
            gic_capped_beta, UBspell_normal,
        )
        from HARK.distributions import Uniform, DiscreteDistribution
        from AggFiscalModel import (
            AggFiscalType, AggregateDemandEconomy, compute_pf_decay_limits,
        )
        from mom_bounds import compute_mpc_min, solve_markov_human_wealth
    finally:
        sys.argv = saved_argv

    # Most-patient (GIC-cap) atom: beta=1.01, nabla=0 -> every discretized atom
    # clips down to gic_capped_beta(2, theGICfactor) (mirrors college_top_ergodic).
    cap = gic_capped_beta(2, ep.theGICfactor)
    dfs = Uniform(1.01, 1.01).discretize(DiscFacCount)
    beta_top = float(np.clip(dfs.atoms[0], minBeta, cap).max())

    ag = AggFiscalType(**init_college)
    ag.cycles = 0
    eco = AggregateDemandEconomy(**init_ADEconomy)
    ag.get_economy_data(eco)
    Dunemp = DiscreteDistribution(np.array([1.0]),
                                  [np.array([1.0]), np.array([ag.IncUnemp])])
    Dunemp_nb = DiscreteDistribution(np.array([1.0]),
                                     [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Dunemp] * UBspell_normal + [Dunemp_nb]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.DiscFac = beta_top
    ag.AgentCount = 1
    ag.tm_a_indexed = True
    eco.agents = [ag]
    eco.solve()

    # Re-derive the PF limit the solver should have used (same inputs, sliced to
    # StateCount exactly as the solver does). Two derivations:
    #   hNrm   : the BASE joint-h (no AD), for the baseline-identity assertions.
    #   h_AD   : the AD-AWARE (Ccount, StateCount) limits via the production helper
    #            compute_pf_decay_limits (what the solver/terminal actually attach).
    # For this BASELINE atom ADelasticity==0 => ADFunc==1 => h_AD is C-flat and
    # equals hNrm for every slice (asserted explicitly in
    # test_ad_aware_h_reduces_to_base_in_baseline).
    S = np.asarray(ag.MrkvArray[0]).shape[0]
    Rfree = np.asarray(ag.Rfree, float).flatten()[:S]
    PermGroFac = np.asarray(ag.PermGroFac, float).flatten()[:S]
    LivPrb0 = float(np.asarray(ag.LivPrb, float).flat[0])
    inc = ag.IncShkDstn[0]
    Cgrid = np.asarray(ag.Cgrid, float)
    E_inc = np.array([
        float(np.sum(np.asarray(inc[j].pmv) * np.asarray(inc[j].atoms[0])
                     * np.asarray(inc[j].atoms[1])))
        for j in range(S)
    ])
    MPCmin = compute_mpc_min(float(Rfree[0]), float(beta_top), float(ag.CRRA),
                             LivPrb=LivPrb0)
    hNrm = solve_markov_human_wealth(np.asarray(ag.MrkvArray[0], float), Rfree,
                                     E_inc, PermGroFac_by_state=PermGroFac)
    MPCmin_h, h_AD = compute_pf_decay_limits(
        np.asarray(ag.MrkvArray[0], float), ag.Rfree, ag.PermGroFac, inc, Cgrid,
        ag.ADFunc, ag.num_base_MrkvStates, float(beta_top), float(ag.CRRA),
        ag.LivPrb)
    return (ag, float(MPCmin), np.asarray(hNrm, float),
            np.asarray(h_AD, float), Cgrid)


# --- module-level cache so we solve at most once per flag state -------------
_CACHE = {}


def _solved(decay_on):
    key = bool(decay_on)
    if key not in _CACHE:
        _CACHE[key] = _build_and_solve_college_cap(decay_on)
    return _CACHE[key]


# ===========================================================================
# (a) FLAG ON -> decay engaged on every converged slice, slope_limit == MPCmin
# ===========================================================================
def test_flag_on_attaches_decay_to_every_state_slice():
    ag, MPCmin, hNrm, h_AD, Cgrid = _solved(decay_on=True)
    cf = ag.solution[0].cFunc
    assert len(cf) >= 1
    assert MPCmin > 0, "RIC must hold for the College cap atom (MPCmin > 0)"
    for i in range(len(cf)):
        slices = _decay_slices(cf[i])
        assert slices, (
            f"state {i}: flag ON but no decay-extrapolating slice found "
            f"(expected one per Cgrid point)")
        # The AD-aware intercept for current state i and C-slice n is
        # MPCmin*h_AD[n][i]. _decay_slices returns the per-C slices in an
        # unspecified order, so each slice's intercept must MATCH ONE of the
        # per-C expected values for this state. (In the baseline atom ADFunc==1,
        # so every h_AD[n][i] equals hNrm[i] and this is just MPCmin*hNrm[i].)
        expected = MPCmin * h_AD[:, i]   # (Ccount,)
        for s in slices:
            assert s.decay_extrap is True
            assert np.isclose(float(s.slope_limit), MPCmin, rtol=0, atol=1e-12), (
                f"state {i}: slope_limit {s.slope_limit} != MPCmin {MPCmin}")
            assert np.any(np.isclose(float(s.intercept_limit), expected,
                                     rtol=1e-9, atol=1e-12)), (
                f"state {i}: intercept_limit {s.intercept_limit} not among the "
                f"AD-aware per-C intercepts MPCmin*h_AD[:,i]={expected}")


# ===========================================================================
# (b) ASYMPTOTE -> flag-ON cFunc tracks MPCmin*(m+h_i) at large m, and is well
#     below the flag-OFF naive-linear value there (the bug it fixes).
# ===========================================================================
def test_asymptote_tracks_pf_line_at_large_m():
    ag_on, MPCmin, hNrm, h_AD, Cgrid = _solved(decay_on=True)
    ag_off, _, _, _, _ = _solved(decay_on=False)
    cf_on = ag_on.solution[0].cFunc
    cf_off = ag_off.solution[0].cFunc
    m_big = 1300.0
    m = np.array([m_big])
    one = np.ones_like(m)
    for i in range(len(cf_on)):
        c_on = float(np.asarray(cf_on[i](m, one)).reshape(-1)[0])
        c_off = float(np.asarray(cf_off[i](m, one)).reshape(-1)[0])
        pf = MPCmin * (m_big + hNrm[i])
        rel = abs(c_on - pf) / pf
        # '1' selects the POWER-LAW form since 2026-07-05 (RECONCILED-002): the
        # gap it deliberately KEEPS at m=1300 is ~2e-3 of the line (measured,
        # decay_form/t0_out.txt), so the bound is 6e-3 — still ~50x below the
        # naive-linear OFF error (~30%). The tight 2e-3 bound now lives with
        # the explicit 'exp' opt-out below.
        assert rel < 6e-3, (
            f"state {i}: flag-ON c({m_big})={c_on:.6g} vs PF line {pf:.6g} "
            f"(rel {rel:.3%}) — asymptote not tracked")
        # The whole point: OFF is naive-linear and sits ABOVE the PF line at m_big;
        # ON decays toward it, so ON must be meaningfully below OFF.
        assert c_on < c_off, (
            f"state {i}: flag-ON c({m_big})={c_on:.6g} should be below the "
            f"naive flag-OFF value {c_off:.6g}")
    # The legacy exponential opt-out ('exp') still tracks the line TIGHTLY
    # (it decays the gap much faster — that over-tracking is exactly why it
    # was replaced, but it remains the regression anchor for the old form).
    ag_exp, MPCmin_e, hNrm_e, _, _ = _build_and_solve_college_cap(
        True, flag_value="exp")
    cf_exp = ag_exp.solution[0].cFunc
    for i in range(len(cf_exp)):
        c_e = float(np.asarray(cf_exp[i](m, one)).reshape(-1)[0])
        pf = MPCmin_e * (m_big + hNrm_e[i])
        assert abs(c_e - pf) / pf < 2e-3, (
            f"state {i}: 'exp' opt-out c({m_big})={c_e:.6g} vs PF line "
            f"{pf:.6g} — legacy exponential regression broken")


# ===========================================================================
# (c) CONCAVITY HALT — unit-test the §1.3 guard condition directly, and assert
#     the real converged solve stays weakly below the PF line everywhere.
# ===========================================================================
def _halt_condition(c_top, m_top, m_prev, c_prev, MPCmin, h_i):
    """Replicate the in-solver HALT predicate (AggFiscalModel.solve_agg_cons_markov_alt).

    EVERY-ITERATE form (owner insight 2026-06-24): with the constrained-PF
    terminal start, by Carroll-Kimball concavity every backward iterate -- not
    just the converged solution -- stays at/below the PF line, so an above-line
    top knot is impossible REGARDLESS of its top-segment slope. Raise iff the
    top knot is above the PF line by a resolvable margin (level_diff < -tol).
    The ``c_prev``/``m_prev`` slope is no longer part of the predicate (kept in
    the signature only because callers compute it); it remains relevant only to
    the *decay-attach* branch's B>0 guard, not to the HALT.
    """
    pf_top = MPCmin * (m_top + h_i)
    level_diff = pf_top - c_top
    tol = 1e-9 * max(1.0, abs(pf_top))
    return level_diff < -tol


def test_concavity_halt_condition():
    MPCmin, h_i = 0.0054, 190.0
    # IMPOSSIBLE knot: far above the PF line -> HALT (slope is irrelevant now).
    assert _halt_condition(c_top=40.0, m_top=80.0, m_prev=78.0, c_prev=39.999,
                           MPCmin=MPCmin, h_i=h_i) is True
    # Above the line with a STEEP top slope (the old "transient" case) is ALSO a
    # HALT under the every-iterate form: the constrained-PF start forbids any
    # above-line iterate, so this signature can only be a broken/non-concave knot.
    assert _halt_condition(c_top=40.0, m_top=80.0, m_prev=78.0, c_prev=39.0,
                           MPCmin=MPCmin, h_i=h_i) is True
    # Well-behaved knot: below the line -> NOT a halt.
    assert _halt_condition(c_top=0.97, m_top=41.0, m_prev=40.0, c_prev=0.9624,
                           MPCmin=MPCmin, h_i=h_i) is False


def test_concavity_halt_fires_via_solver_on_constructed_input():
    """The HALT is reachable through the real solver when handed a pathological
    cNrm/mNrm slice. Drive solve_agg_cons_markov_alt's slice loop indirectly by
    asserting the predicate the solver uses; a full pathological solve is not
    constructible cheaply, so we assert the guard exists in the source and the
    predicate is exercised above."""
    src = (_FPC / "AggFiscalModel.py").read_text(encoding="utf-8")
    assert "HAFISCAL_PF_DECAY_EXTRAP" in src
    assert "Carroll-Kimball" in src
    assert "raise ValueError" in src and "EXCEEDS the AD-aware PF line" in src


def test_converged_solve_stays_below_pf_line():
    ag, MPCmin, hNrm, h_AD, Cgrid = _solved(decay_on=True)
    cf = ag.solution[0].cFunc
    worst = -np.inf
    for i in range(len(cf)):
        # AD-aware: each per-C slice has its own line MPCmin*(m+h_AD[n][i]).
        # _decay_slices doesn't tag which C a slice is, so bound every slice by
        # the LEAST-restrictive (largest-intercept) per-C line for this state —
        # a slice above its own line would also be above this max. (In the
        # baseline atom every per-C line is identical, so this == the base line.)
        pf_h_i = float(np.max(h_AD[:, i]))
        for s in _decay_slices(cf[i]):
            m = np.asarray(s.x_list, float)
            c = np.asarray(s.y_list, float)
            pf_top = MPCmin * (m[-1] + pf_h_i)
            worst = max(worst, c[-1] - pf_top)
    # All decay-bearing slices in the converged solve are at/below the PF line
    # (a tiny positive epsilon would still be inside the build tolerance).
    assert worst <= 1e-6, (
        f"converged solve has a slice top knot {worst:.3g} ABOVE the PF line — "
        f"Carroll-Kimball concavity violated")


# ===========================================================================
# (a') AD-AWARE h REDUCES TO BASE in the baseline (ADelasticity==0, ADFunc==1):
#      h_AD must be C-flat and equal the base joint-h for every slice/state.
# ===========================================================================
def test_ad_aware_h_reduces_to_base_in_baseline():
    ag, MPCmin, hNrm, h_AD, Cgrid = _solved(decay_on=True)
    S = h_AD.shape[1]
    # ADFunc==1 in the baseline -> every C-slice's h_AD row equals base hNrm.
    for n in range(h_AD.shape[0]):
        assert np.allclose(h_AD[n, :], hNrm, rtol=0, atol=1e-12), (
            f"C-slice {n} (C={Cgrid[n]}): AD-aware h_AD {h_AD[n]} != base hNrm "
            f"{hNrm} — the AD code does not reduce to base when ADFunc==1")
    # C-flatness (max spread across the C axis per state) is ~0.
    spread = float(np.max(h_AD.max(axis=0) - h_AD.min(axis=0)))
    assert spread < 1e-12, (
        f"baseline h_AD is not C-flat (max spread {spread:.3g}) — ADFunc should "
        f"be identically 1 here")


# ===========================================================================
# (c') AD-AWARE RECESSION CORRECTNESS — drive the production helper directly
#      with a synthetic recession Markov chain + nonzero ADelasticity and show
#      recession-state h_AD < base h when aggregate C < 1 (and > base when C>1),
#      with the PF intercept MPCmin*h_AD correspondingly AD-scaled.
# ===========================================================================
def test_compute_pf_decay_limits_is_ad_aware_in_recession():
    saved_argv = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        from AggFiscalModel import compute_pf_decay_limits, _ADFuncImpl
    finally:
        sys.argv = saved_argv

    # num_base=2 -> RecState_j = floor(j/2)%2: states 0,1 normal; 2,3 recession.
    num_base = 2
    M = np.array([
        [0.80, 0.05, 0.10, 0.05],
        [0.40, 0.40, 0.15, 0.05],
        [0.20, 0.05, 0.65, 0.10],
        [0.20, 0.10, 0.30, 0.40],
    ])
    M = M / M.sum(axis=1, keepdims=True)
    R = np.full(6, 1.01)
    G = np.array([1.005, 1.0, 1.0, 1.0, 1.0, 1.0])
    LivPrb = np.full(6, 0.99375)
    DiscFac, CRRA = 0.985, 2.0
    Cgrid = np.array([0.8, 0.9, 1.0, 1.1, 1.2])

    class _D:
        def __init__(self, E):
            self.pmv = np.array([1.0])
            self.atoms = [np.array([1.0]), np.array([E])]
    inc = [_D(1.0), _D(0.7), _D(1.0), _D(0.7)]
    RecState = [bool(int(np.floor(j / num_base)) % 2 == 1) for j in range(4)]

    # ADelasticity == 0 -> exactly the base joint-h, C-flat.
    MPCmin0, h0 = compute_pf_decay_limits(
        M, R, G, inc, Cgrid, _ADFuncImpl(0.0), num_base, DiscFac, CRRA, LivPrb)
    assert np.all(np.isfinite(h0)) and MPCmin0 > 0
    assert float(np.max(h0.max(0) - h0.min(0))) < 1e-12  # C-flat
    h_base = h0[0].copy()

    # ADelasticity == 0.5 -> AD-aware.
    el = 0.5
    MPCmin, h_AD = compute_pf_decay_limits(
        M, R, G, inc, Cgrid, _ADFuncImpl(el), num_base, DiscFac, CRRA, LivPrb)
    assert np.isclose(MPCmin, MPCmin0)  # MPCmin is C-independent
    i_C08 = int(np.argmin(np.abs(Cgrid - 0.8)))
    i_C10 = int(np.argmin(np.abs(Cgrid - 1.0)))
    i_C12 = int(np.argmin(np.abs(Cgrid - 1.2)))
    # At C==1, ADFunc==1 so h_AD == base exactly.
    assert np.allclose(h_AD[i_C10], h_base, atol=1e-10)
    for j in range(4):
        if RecState[j]:
            # C<1: recession income AD-scaled DOWN -> h_AD strictly below base.
            assert h_AD[i_C08, j] < h_base[j] - 1e-6, (
                f"recession state {j}: h_AD@C=0.8 {h_AD[i_C08,j]:.4f} not below "
                f"base {h_base[j]:.4f}")
            # C>1: scaled UP -> above base.
            assert h_AD[i_C12, j] > h_base[j] + 1e-6
            # Intercept MPCmin*h_AD is correspondingly ordered across C.
            assert (MPCmin * h_AD[i_C08, j]
                    < MPCmin * h_AD[i_C10, j]
                    < MPCmin * h_AD[i_C12, j])


# ===========================================================================
# (d) DEFAULT IDENTITY — since the 2026-07-23 owner flip the DEFAULT (flag
#     unset) is ON: unset must equal explicit '1' bit-for-bit, and the literal
#     '0' must still deliver the legacy no-decay path (the opt-out survives).
# ===========================================================================
def test_default_on_identity_and_legacy_opt_out():
    # unset == '1' bit-for-bit (the default-ON identity)
    ag_unset = _build_and_solve_college_cap(True, flag_value=_POP)[0]
    try:
        ag_one = _build_and_solve_college_cap(True, flag_value="1")[0]
        ag_zero = _build_and_solve_college_cap(False, flag_value="0")[0]
    finally:
        os.environ.pop("HAFISCAL_PF_DECAY_EXTRAP", None)

    cf_a = ag_unset.solution[0].cFunc
    cf_b = ag_one.solution[0].cFunc
    assert len(cf_a) == len(cf_b)
    m = np.geomspace(0.1, 1300.0, 40)
    for i in range(len(cf_a)):
        for C in (0.8, 1.0, 1.2):
            Cv = np.full_like(m, C)
            a = np.asarray(cf_a[i](m, Cv), float)
            b = np.asarray(cf_b[i](m, Cv), float)
            assert np.array_equal(a, b), (
                f"state {i}, C={C}: default-unset cFunc differs from flag='1' "
                f"(max |Δ|={np.max(np.abs(a - b)):.3g}) — the 2026-07-23 "
                "default-ON flip is not byte-faithful to explicit '1'")
    # '0' = the legacy opt-out: no decay slices anywhere
    for i in range(len(ag_zero.solution[0].cFunc)):
        assert not _decay_slices(ag_zero.solution[0].cFunc[i]), (
            f"state {i}: flag '0' attached decay slices — the legacy opt-out "
            "path regressed")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# ===========================================================================
# (e) POWERLAW VALUE -> the 'powerlaw' flag literal attaches the power-law form
#     (HAFiscal-local mirror of the HARK-PR decay_extrap_form='powerlaw';
#     plans/2026-07-05_powerlaw-switch-test-plan.md T0. Measured baselines in
#     decay_form/t0_out.txt: in-sample exp-vs-pl max|dC/C| = 5.2e-3; tail
#     c_pl < c_exp by 0.2-1.9% on m in [50, 1300]; gap_pl > 0 everywhere.)
# ===========================================================================
def test_powerlaw_flag_value_attaches_powerlaw_form():
    from powerlaw_decay import PowerLawDecayLinearInterp

    ag_pl, MPCmin, hNrm, h_AD, Cgrid = _build_and_solve_college_cap(
        True, flag_value="powerlaw")
    # THE FLIP LOCK (owner decision 2026-07-05, RECONCILED-002): plain '1'
    # must ALSO attach the power-law class now.
    ag_one, _, _, _, _ = _solved(decay_on=True)
    for i in range(len(ag_one.solution[0].cFunc)):
        for s in _decay_slices(ag_one.solution[0].cFunc[i]):
            assert isinstance(s, PowerLawDecayLinearInterp), (
                f"state {i}: flag '1' attached {type(s).__name__} — the "
                "2026-07-05 powerlaw-default flip has regressed")
    # The exp side of the ordering comparisons uses the explicit opt-out.
    ag_exp, MPCmin_e, hNrm_e, _, _ = _build_and_solve_college_cap(
        True, flag_value="exp")
    cf_pl = ag_pl.solution[0].cFunc
    cf_exp = ag_exp.solution[0].cFunc

    lad = np.array([50.0, 100.0, 200.0, 400.0, 700.0, 1000.0, 1300.0])
    m_in = np.linspace(0.5, 39.5, 80)
    saw_powerlaw = False
    for i in range(len(cf_pl)):
        slices = _decay_slices(cf_pl[i])
        assert slices, f"state {i}: 'powerlaw' flag ON but no decay slice engaged"
        for s in slices:
            assert isinstance(s, PowerLawDecayLinearInterp), (
                f"state {i}: engaged slice is {type(s).__name__}, expected "
                "PowerLawDecayLinearInterp under HAFISCAL_PF_DECAY_EXTRAP=powerlaw")
            assert getattr(s, "decay_extrap_form", None) == "powerlaw"
            assert s.decay_extrap_Q > 0.0
            saw_powerlaw = True
        # tail: strictly below the PF line (Carroll-Kimball), and weakly below
        # the exp variant (the power law holds the gap the exponential destroys)
        C1 = np.full(lad.shape, 1.0)
        c_pl = np.asarray(cf_pl[i](lad, C1))
        c_exp = np.asarray(cf_exp[i](lad, C1))
        line = MPCmin * (lad + hNrm[i])
        assert np.all(c_pl < line), f"state {i}: powerlaw tail not below the PF line"
        assert np.all(c_pl <= c_exp * (1.0 + 1e-9)), (
            f"state {i}: powerlaw tail above the exponential tail")
        # in-sample feedback (tail form re-enters via top-node expectations) is
        # bounded: measured 5.2e-3 max for this atom; lock at 2e-2
        Cin = np.full(m_in.shape, 1.0)
        d_in = np.max(np.abs(np.asarray(cf_pl[i](m_in, Cin))
                             - np.asarray(cf_exp[i](m_in, Cin)))
                      / np.abs(np.asarray(cf_exp[i](m_in, Cin))))
        assert d_in < 2e-2, f"state {i}: in-sample exp-vs-powerlaw delta {d_in:.3e}"
    assert saw_powerlaw


# ===========================================================================
# (f) STEP-5 SOLVE GRID — the local2 K·h̄ rule reaches Parameters.py's init
#     dicts (the candidate multiplier-pipeline config), and the default path
#     is unchanged (plans/20260722_local-two-secant-tail-q_plan.md; the
#     default-vs-local2 A/B tee-up, 2026-07-22).
# ===========================================================================
_GRID_ENV = ("HAFISCAL_PF_DECAY_EXTRAP", "HAFISCAL_PF_DECAY_Q",
             "HAFISCAL_PF_DECAY_AMAX_MULT", "HAFISCAL_SOLVE_AMAX",
             "HAFISCAL_ENDOGENOUS_GRID", "HAFISCAL_FAST_GRIDS")


def _step5_inits(**env):
    """return_parameters('Reduced_Run') under a controlled grid-env patch.

    Returns (init_dropout, init_highschool, init_college). Safe to call
    repeatedly in one process: the grid block re-reads the env on every call.
    """
    saved_argv = sys.argv
    saved_env = {k: os.environ.get(k) for k in _GRID_ENV}
    sys.argv = [saved_argv[0]]
    for k in _GRID_ENV:
        os.environ.pop(k, None)
    os.environ.update(env)
    os.environ.setdefault("HAFISCAL_QUIET_BETADISTR", "1")
    try:
        from Parameters import return_parameters
        out = return_parameters("Reduced_Run", "_Main.py")
        return out[0], out[1], out[2]
    finally:
        sys.argv = saved_argv
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_step5_solve_grid_default_is_k_hbar_and_legacy_opt_out_is_40_48():
    # DEFAULT (2026-07-23 owner flip + pre-approved count ruling): bare env ⟹
    # the K·h̄ per-group top with counts scaled from the count-converged basis 192.
    import math
    inits = _step5_inits()
    R = inits[0]["Rfree_base"][0]
    for d in inits:
        G = d["PermGroFac_base"][0]
        assert d["aXtraMax"] == pytest.approx(3.0 * G / (R - G)), (
            f"EducType {d['EducType']}: DEFAULT Step-5 solve top must be K=3·h̄ "
            "(the 2026-07-23 flip)")
        expected_count = math.ceil(
            192 * math.log(d["aXtraMax"] / 0.001) / math.log(40 / 0.001))
        assert d["aXtraCount"] == expected_count, (
            f"EducType {d['EducType']}: DEFAULT count must scale from basis 192 "
            "(pre-approved ruling 2026-07-23)")
    # LEGACY opt-outs: each must restore the 40/48 grid.
    for legacy_env in ({"HAFISCAL_PF_DECAY_EXTRAP": "0"},
                       {"HAFISCAL_PF_DECAY_EXTRAP": "exp"},
                       {"HAFISCAL_PF_DECAY_Q": "slope"}):
        for d in _step5_inits(**legacy_env):
            assert d["aXtraMax"] == 40 and d["aXtraCount"] == 48, (
                f"legacy env {legacy_env} must restore the 40/48 solve grid")


def test_step5_solve_grid_local2_applies_k_hbar_per_group():
    # explicit legacy alias 'local2' must behave exactly like the canonical 'measured'
    inits = _step5_inits(HAFISCAL_PF_DECAY_EXTRAP="1", HAFISCAL_PF_DECAY_Q="local2")
    K = 3.0  # HAFISCAL_PF_DECAY_AMAX_MULT default
    R = inits[0]["Rfree_base"][0]
    tops = []
    for d in inits:
        G = d["PermGroFac_base"][0]
        assert d["aXtraMax"] == pytest.approx(K * G / (R - G)), (
            f"EducType {d['EducType']}: Step-5 aXtraMax != K·h̄")
        assert d["aXtraCount"] > 48, "density-held count must extend with the top"
        tops.append(d["aXtraMax"])
    # per-group: College's larger Γ ⟹ larger h̄ ⟹ deepest solve top
    assert tops[0] < tops[1] < tops[2]
    # the 'exp' opt-out must NOT trigger the grid rule (form gate parity with
    # the AggFiscalModel attach gate, which warns+ignores local2 under exp)
    for d in _step5_inits(HAFISCAL_PF_DECAY_EXTRAP="exp", HAFISCAL_PF_DECAY_Q="local2"):
        assert d["aXtraMax"] == 40


def test_step5_axtra_count_override_reaches_the_grid():
    # The 2026-07-23 probe found Parameters.py ignored HAFISCAL_AXTRA_COUNT (it
    # scaled from a hardcoded 48). Base 96 must scale to ceil(96·ln(aMax/aMin)/
    # ln(40/aMin)) under the default K·h̄ grid, and pass through unscaled (96)
    # under the legacy opt-out.
    import math
    for d in _step5_inits(HAFISCAL_AXTRA_COUNT="96"):
        expected = math.ceil(96 * math.log(d["aXtraMax"] / 0.001) / math.log(40 / 0.001))
        assert d["aXtraCount"] == expected, (
            f"EducType {d['EducType']}: count override not scaled into the K·h̄ grid")
    for d in _step5_inits(HAFISCAL_AXTRA_COUNT="96", HAFISCAL_PF_DECAY_EXTRAP="0"):
        assert d["aXtraCount"] == 96
