"""
Regression test: saved Step-2 calibration must be self-consistent with the
current code's wealth-fit measurement.

What it checks: the medianLWPI value reported in saved AllResults at the
saved (β, ∇, GICx) must equal what the CURRENT code produces at the same
(β, ∇, GICx). If they diverge, either the saved cal was just re-anchored
(pin needs update) OR a code change shifted the wealth-fit landscape
(BUG-034-class regression).

Why: BUG-034 (the (1-ς) wealth-aggregator fix landed Apr 26, 2026)
silently invalidated the saved Step-2 calibration. The pre-BUG-034
aggregator deflated wealth by ~26%, and the optimizer compensated by
choosing higher β. After BUG-034, the same β produces ~35% higher
medianLWPI than what saved AllResults reports. Without this test, the
staleness was invisible: the saved files looked plausible, AllResults
reported a near-perfect fit, and the Step-5 pipeline ran without errors.

The test uses TM-a (analytical ergodic) for speed. Under CDC at the
then-production aCount=100 (as of 2026-05-01; the estimation-kernel
default is now aCount=200 — see estim_phase2_tm_a.py), TM-a's medianLWPI
tracks MC's medianLWPI within ~2pp (per the B1 + B2 sweeps documented in
conclusions_private/2026-05-01_saved-step2-cal-stale-due-to-bug-034.md).
So if TM-a's result at saved β diverges from saved AllResults's MC value
by more than ~5%, that's a real signal — either the calibration is
stale or the code's wealth-fit semantics have shifted.

When this test fails:
  (a) If you just re-anchored Step-2 and updated AllResults, the test
      should PASS automatically (both sides moved together). If it
      doesn't, dig in.
  (b) If no re-anchor happened, a code change has shifted the wealth-fit
      landscape — diagnose before proceeding (BUG-034 was exactly this).

Tolerance: 5% on each cohort's medianLWPI (accommodates TM-a-vs-MC
methodological gap of ~2pp + TM-a grid noise at aCount=100 of ~1pp).
"""
import os
import sys
import re
from copy import deepcopy

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

# CLAUDE.md note: EstimParameters reads sys.argv. Patch BEFORE imports.
_SAVED_ARGV = sys.argv
sys.argv = ['test_saved_calibration_self_consistent', '1.01', '2.0', '0.7']

from HARK.distributions import Uniform, DiscreteDistribution
from HARK.utilities import get_percentiles
from EstimParameters import (
    init_dropout, init_highschool, init_college, init_ADEconomy,
    DiscFacCount, UBspell_normal,
    GICmaxBetas, gic_capped_beta, minBeta,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution

sys.argv = _SAVED_ARGV

TOLERANCE_PCT = 5.0

# A DiscFacEstim numeric field may be a bare float (`0.93`) OR a numpy-2.x repr
# wrapper (`np.float64(0.93)`) — the latter leaks in when a numpy>=2 box repr()'d
# a dict of np.float64 values (the Mac venvs wrote per-edType edType1/2 files that
# way). Tolerate both. MUST stay in sync with EstimAggFiscalMAIN.py's BUG-039
# Phase E warm-start regex (the `_FL` there); test_warmstart_files_parse below
# guards that the production parser handles both formats.
_FL = r"(?:np\.float64\()?([\d.eE+-]+)\)?"


def _read_saved_calibration():
    """Parse DiscFacEstim_CRRA_2.0_R_1.01.txt → list of (beta, nabla, GICx)."""
    path = os.path.normpath(os.path.join(_HERE, '..', 'Results', 'DiscFacEstim_CRRA_2.0_R_1.01.txt'))
    if not os.path.isfile(path):
        pytest.skip(f"Saved DiscFacEstim file missing: {path}")
    rows = []
    for line in open(path):
        m = re.search(r"'beta':\s*" + _FL + r".*'nabla':\s*" + _FL + r".*'GICx':\s*" + _FL, line)
        if m:
            rows.append(tuple(float(x) for x in m.groups()))
    assert len(rows) == 3, f"Expected 3 cohorts in DiscFacEstim file, found {len(rows)}"
    return rows


def _read_saved_allresults_medianLWPI():
    """Parse AllResults_*.txt → [D, HS, C] medianLWPI as reported there."""
    path = os.path.normpath(os.path.join(_HERE, '..', 'Results', 'AllResults_CRRA_2.0_R_1.01.txt'))
    if not os.path.isfile(path):
        pytest.skip(f"Saved AllResults file missing: {path}")
    txt = open(path).read()
    m = re.search(r"Median LW/PI-ratios\s*=\s*\[([\d.,\s]+)\]", txt)
    if not m:
        pytest.skip(f"Could not parse Median LW/PI-ratios line in {path}")
    return [float(x.strip()) for x in m.group(1).split(',')]


@pytest.fixture(scope='module')
def setup_economy():
    """Build the 3-base-cohort economy ONCE for all per-cohort tests."""
    agt_d = AggFiscalType(**init_dropout); agt_d.cycles = 0
    agt_h = AggFiscalType(**init_highschool); agt_h.cycles = 0
    agt_c = AggFiscalType(**init_college); agt_c.cycles = 0
    econ = AggregateDemandEconomy(**init_ADEconomy)
    agt_d.get_economy_data(econ); agt_h.get_economy_data(econ); agt_c.get_economy_data(econ)
    BaseTypeList = [agt_d, agt_h, agt_c]
    IncomeDstn_unemp = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([agt_d.IncUnemp])])
    IncomeDstn_unemp_nobenefits = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([agt_d.IncUnempNoBenefits])])
    for ThisType in BaseTypeList:
        ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncomeDstn_unemp]*UBspell_normal + [IncomeDstn_unemp_nobenefits]]
        ThisType.IncShkDstn_base = ThisType.IncShkDstn
    return BaseTypeList, econ


def _compute_tma_medianLWPI(BaseTypeList, econ, ed, beta, spread, GICx, aCount=200):
    # aCount=200 (was 100) per tm_methods.py:4434: aCount=100 has ~30% K/Y bias
    # from upper-grid tail truncation. The "TM-a vs MC methodology gap" this
    # test was xfail'ing on D was largely a grid-resolution artifact, not a
    # methodology mismatch. With aCount=200 the gap may close enough for D
    # to pass; if so, remove the xfail marker on the [D-0] case below.
    """Build cohort `ed` agents at given (β, ∇, GICx), solve, return TM-a medianLWPI."""
    dfs = Uniform(beta - spread, beta + spread).discretize(DiscFacCount)
    cap = gic_capped_beta(ed, np.exp(GICx) / (1 + np.exp(GICx)))
    for thedf in range(DiscFacCount):
        if dfs.atoms[0][thedf] > cap:
            dfs.atoms[0][thedf] = cap
        elif dfs.atoms[0][thedf] < minBeta:
            dfs.atoms[0][thedf] = minBeta

    TypeList = []
    for ed_loop in range(3):
        for b_idx in range(DiscFacCount):
            T = deepcopy(BaseTypeList[ed_loop])
            T.AgentCount = 1000
            if ed_loop == ed:
                T.DiscFac = dfs.atoms[0][b_idx]
            TypeList.append(T)
    econ.agents = TypeList
    econ.solve()

    cohort_atoms = TypeList[ed * DiscFacCount:(ed + 1) * DiscFacCount]
    a_vals_list, w_vals_list = [], []
    total_w = sum(t.AgentCount for t in cohort_atoms)
    for agent in cohort_atoms:
        agent_w = agent.AgentCount / total_w
        tm_data = build_tm_agg_fiscal_a(agent, aCount=aCount)
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
        dist_aGrid = tm_data['dist_aGrid']
        J = agent.MrkvArray[0].shape[0]; A = len(dist_aGrid)
        erg = np.asarray(ergodic).reshape(J, A)
        for j in range(J):
            mask = erg[j, :] > 1e-15
            if np.any(mask):
                a_vals_list.append(dist_aGrid[mask])
                w_vals_list.append(erg[j, mask] * agent_w)
    a_array = np.concatenate(a_vals_list)
    w_array = np.concatenate(w_vals_list); w_array /= np.sum(w_array)
    return 100 * get_percentiles(a_array, weights=w_array, percentiles=[0.5])[0]


# The [D-0] case carried a strict xfail ("TM-a vs MC methodology gap ~20%")
# until 2026-06-12: it began XPASSing once the BUG-047 paper-grade re-estimated
# calibration (fitted GICx, commit 2785c1f1) landed — the gap was largely the
# grid-resolution artifact described above plus the pre-fix calibration, so per
# the marker's own instructions the xfail was removed.
@pytest.mark.parametrize("cohort_label,ed", [
    ('D', 0),
    ('HS', 1),
    ('C', 2),
])
def test_saved_cal_medianLWPI_self_consistent(cohort_label, ed, setup_economy):
    """At saved (β, ∇, GICx) for {cohort}, TM-a medianLWPI under current code
    must match what saved AllResults reports within ±{TOLERANCE_PCT}%.
    """
    BaseTypeList, econ = setup_economy
    saved_calibration = _read_saved_calibration()
    saved_medianLWPI = _read_saved_allresults_medianLWPI()
    beta, spread, GICx = saved_calibration[ed]
    expected = saved_medianLWPI[ed]

    actual = _compute_tma_medianLWPI(BaseTypeList, econ, ed, beta, spread, GICx)

    rel_err = abs(actual - expected) / expected * 100
    assert rel_err < TOLERANCE_PCT, (
        f"\n=== Cohort {cohort_label} (ed={ed}) saved-cal self-consistency FAILED ==="
        f"\n  saved (β, ∇, GICx)         = ({beta:.6f}, {spread:.6f}, {GICx:.6f})"
        f"\n  TM-a medianLWPI now        = {actual:.3f}"
        f"\n  Saved AllResults reports   = {expected:.3f}"
        f"\n  Relative error             = {rel_err:.2f}%  (tolerance: {TOLERANCE_PCT}%)"
        f"\n\nDiagnosis:"
        f"\n  (a) If you just re-anchored Step-2 and AllResults reflects the new"
        f"\n      values, this should PASS — if it doesn't, the new AllResults may"
        f"\n      not have been re-generated."
        f"\n  (b) If no re-anchor happened, a code change has shifted the wealth-fit"
        f"\n      landscape; the saved calibration is now stale (BUG-034-class)."
        f"\n      Re-anchor Step-2 before trusting any downstream results."
    )


def _warmstart_row_re(edType):
    """Mirror of EstimAggFiscalMAIN.py BUG-039 Phase E warm-start regex.

    Kept here as a fast guard so a future edit that re-narrows the float
    sub-pattern (and thus silently disables warm-start for np.float64-formatted
    files) is caught without running a full estimation.
    """
    return re.compile(
        r"'EducationGroup':\s*" + str(edType) +
        r".*?'beta':\s*" + _FL + r".*?'nabla':\s*" + _FL +
        r".*?'GICx':\s*" + _FL)


def test_warmstart_regex_handles_both_float_formats():
    """The warm-start parser must read BOTH a bare-float row (numpy<2 / dell)
    AND a numpy-2.x `np.float64(...)` row (the Mac-written per-edType files).
    Regression for the silent cold-start of HS+College discovered 2026-06-23:
    the original `([\\d.eE+-]+)` capture could not match `np.float64(0.93)`, so
    NM_START_FROM_SAVED fell back to legacy starts without warning.
    """
    plain = "{'EducationGroup': 0, 'beta': 0.7237042289931677, 'nabla': 0.3274170583274041, 'GICx': 5.381004901473894}"
    wrapped = "{'EducationGroup': 2, 'beta': np.float64(0.9916907585263794), 'nabla': np.float64(0.025685707717180907), 'GICx': np.float64(12.621123163494428)}"

    m0 = _warmstart_row_re(0).search(plain)
    assert m0 is not None, "bare-float row failed to parse"
    assert abs(float(m0.group(1)) - 0.7237042289931677) < 1e-12
    assert abs(float(m0.group(2)) - 0.3274170583274041) < 1e-12

    m2 = _warmstart_row_re(2).search(wrapped)
    assert m2 is not None, "np.float64(...)-wrapped row failed to parse (the 2026-06-23 bug)"
    assert abs(float(m2.group(1)) - 0.9916907585263794) < 1e-12
    assert abs(float(m2.group(3)) - 12.621123163494428) < 1e-12


@pytest.mark.parametrize("edType", [0, 1, 2])
def test_committed_per_edtype_warmstart_files_parse(edType):
    """Every committed per-edType warm-start file must parse with the production
    regex, regardless of whether it was written with bare floats or np.float64."""
    path = os.path.normpath(os.path.join(
        _HERE, '..', 'Results', f'DiscFacEstim_CRRA_2.0_R_1.01_edType{edType}_ESC.txt'))
    if not os.path.isfile(path):
        pytest.skip(f"per-edType warm-start file missing: {path}")
    text = open(path).read()
    m = _warmstart_row_re(edType).search(text)
    assert m is not None, (
        f"per-edType warm-start file {os.path.basename(path)} did not parse — "
        f"NM_START_FROM_SAVED would silently cold-start edType={edType}. "
        f"First line: {text.splitlines()[0] if text else '(empty)'!r}")
    beta, nabla, GICx = (float(m.group(i)) for i in (1, 2, 3))
    assert 0.0 < beta <= 1.05, f"implausible beta={beta}"
    assert 0.0 <= nabla < 1.0, f"implausible nabla={nabla}"
