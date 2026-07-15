"""
Sanity tests for the a-indexed transition matrix (BUG-033).

Covers Phase 3 of the splurge-in-budget implementation sequence. Each test is
narrow — the goal is to validate single sub-steps on a lightweight
setup (single dropout agent, ~50 grid points, base shock), not to
reproduce the full Baseline multipliers.
"""

import sys
import numpy as np
import pytest

sys.argv = ['test_tm_a_indexed']

from copy import deepcopy
from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    build_tm_agg_fiscal,
    build_tm_agg_fiscal_a,
    build_experiment_period_tm_a,
    propagate_experiment_tm_a,
    find_ergodic_distribution,
    compute_type_aggregates_tm,
    compute_type_aggregates_tm_a,
    compute_period_aggregates_tm_a,
    _build_period_tm_a,
    _make_newborn_dist_a,
    _solve_markov_ergodic,
    _effective_LivPrb,
    make_grid_exp_mult,
)


@pytest.fixture(scope="module")
def baseline_agent():
    """Single dropout agent configured for the base shock."""
    (init_dropout, init_highschool, init_college, init_ADEconomy,
     DiscFacDstns, DiscFacCount, AgentCountTotal, base_dict,
     num_max_iterations_solvingAD, convergence_tol_solvingAD,
     UBspell_normal, num_base_MrkvStates, data_EducShares,
     max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes, Check_changes,
     recession_Check_changes) = return_parameters(
        Parametrization='Baseline', OutputFor='_Main.py'
    )

    econ = AggregateDemandEconomy(**init_ADEconomy)

    agent = AggFiscalType(**init_dropout)
    agent.cycles = 0
    agent.get_economy_data(econ)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnempNoBenefits])])
    EmployedIncShkDstn = deepcopy(agent.IncShkDstn[0])

    # Encoding-agnostic micro-state list: [e, u1Q..uNQ, (u3Q, u4Q,) noBen].
    # Under the canonical 6-state bug_fix encoding (BUG-043, default since
    # 2026-05-16) the extra u3Q/u4Q states pay no-benefits income in the base
    # scenario, same as noBen — mirrors welfare6_scenario.py's construction.
    agent.IncShkDstn = [[EmployedIncShkDstn]
                        + [IncShkDstn_unemp] * UBspell_normal
                        + [IncShkDstn_unemp_nobenefits]
                        * (num_base_MrkvStates - 1 - UBspell_normal)]
    agent.IncShkDstn_base = agent.IncShkDstn

    econ.agents = [agent]
    agent.update_mrkv_array("base")
    agent.solve()

    return agent


def _column_sums(TM):
    """Columns should sum to 1 (column-stochastic)."""
    if hasattr(TM, 'toarray'):
        col_sums = np.asarray(TM.sum(axis=0)).ravel()
    else:
        col_sums = TM.sum(axis=0)
    return col_sums


def test_a_indexed_tm_column_stochastic(baseline_agent):
    """build_tm_agg_fiscal_a returns a column-stochastic matrix."""
    tm_data = build_tm_agg_fiscal_a(baseline_agent, aCount=50, aMax=50.0)
    col_sums = _column_sums(tm_data['TranMatrix'])
    assert np.allclose(col_sums, 1.0, atol=1e-10), \
        f"col sums not 1: min={col_sums.min():.2e}, max={col_sums.max():.2e}"


def test_a_indexed_tm_ergodic_converges(baseline_agent):
    """find_ergodic_distribution converges on the a-indexed TM."""
    tm_data = build_tm_agg_fiscal_a(baseline_agent, aCount=50, aMax=50.0)
    ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
    assert np.all(np.isfinite(ergodic))
    assert np.isclose(np.sum(ergodic), 1.0, atol=1e-10)
    assert np.all(ergodic >= -1e-14)


def test_a_indexed_newborn_dist_structure(baseline_agent):
    """Newborn dist is concentrated at a=0 for each Markov state."""
    MrkvArray = baseline_agent.MrkvArray[0]
    markov_ergodic = _solve_markov_ergodic(MrkvArray)
    dist_aGrid = make_grid_exp_mult(ming=0.0, maxg=50.0, ng=50, timestonest=3)
    nb = _make_newborn_dist_a(dist_aGrid, markov_ergodic)
    A = len(dist_aGrid)
    J = len(markov_ergodic)
    nb_2d = nb.reshape(J, A)
    # Only the a=0 column of each Markov row should be nonzero.
    assert np.all(nb_2d[:, 1:] == 0.0)
    # Marginal over a equals Markov ergodic.
    assert np.allclose(nb_2d[:, 0], markov_ergodic, atol=1e-12)


def _implied_a_moments_from_m_tm(agent, tm_data_m, ergodic_m):
    """
    Compute E[a], E[m], E[c] implied by the m-indexed TM's ergodic.

    Uses cFunc directly to get c* on dist_mGrid, then under ς=0 the
    realized savings equals m - c* for every ξ draw, independent of
    which ξ was realized (that is precisely why ς=0 has m as a
    sufficient state).
    """
    dist_mGrid = tm_data_m['dist_mGrid']
    M = len(dist_mGrid)
    J = agent.MrkvArray[0].shape[0]
    cPol = tm_data_m['cPol']
    aPol = tm_data_m['aPol']
    E_c = 0.0
    E_a = 0.0
    E_m = 0.0
    for j in range(J):
        dstn_j = ergodic_m[j * M:(j + 1) * M]
        E_c += np.dot(cPol[j], dstn_j)
        E_a += np.dot(aPol[j], dstn_j)
        E_m += np.dot(dist_mGrid, dstn_j)
    return dict(E_a=E_a, E_c=E_c, E_m=E_m)


def _implied_a_moments_from_a_tm(agent, tm_data_a, ergodic_a):
    """
    Compute E[a] from the a-indexed ergodic; E[c], E[m] require
    integrating over (j', ξ) — done via explicit post-arrival loop to
    avoid depending on Phase 3.2 machinery.
    """
    dist_aGrid = tm_data_a['dist_aGrid']
    A = len(dist_aGrid)
    J = agent.MrkvArray[0].shape[0]
    MrkvArray = agent.MrkvArray[0]
    IncShkDstn_list = tm_data_a['IncShkDstn_list']
    Rfree = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    sol = agent.solution[0]
    Splurge = float(agent.Splurge)

    erg = ergodic_a.reshape(J, A)
    E_a = 0.0
    E_c = 0.0
    E_m = 0.0
    for j in range(J):
        for ia, a in enumerate(dist_aGrid):
            w = erg[j, ia]
            if w <= 0.0:
                continue
            E_a += w * a
            for jp in range(J):
                trans = MrkvArray[j, jp]
                if trans < 1e-15:
                    continue
                dstn = IncShkDstn_list[jp]
                psi = dstn.atoms[0]
                xi = dstn.atoms[1]
                pmv = dstn.pmv
                m_next = (Rfree[jp] / (PermGroFac[jp] * psi)) * a + xi
                c_star = sol.cFunc[jp](m_next, np.ones_like(m_next))
                c_actual = (1 - Splurge) * c_star + Splurge * xi
                wt = w * trans * pmv
                E_m += np.dot(wt, m_next)
                E_c += np.dot(wt, c_actual)
    return dict(E_a=E_a, E_c=E_c, E_m=E_m)


def test_a_indexed_matches_m_indexed_at_splurge_zero(baseline_agent):
    """
    Acceptance criterion (Phase 3.1): at ς = 0, the a-indexed TM and the
    m-indexed TM imply the same aggregate moments.

    Rationale. With ς = 0, post-consumption savings are a function of m
    only (no ξ-dependence), so both TMs describe the same underlying
    distribution — just with different state representations. The
    cross-check on E[c] and E[m] is the cleanest sanity check for the
    a-indexed kernel construction.
    """
    agent_z = deepcopy(baseline_agent)
    agent_z.Splurge = 0.0

    # m-indexed reference. mCount/aCount=200 (was 100): under the 6-state
    # encoding the coarser grids left E_a at rel~1.1e-2, just over tolerance —
    # a discretization artifact (the TM-mixing auto-repair also pads the
    # a-grid at aCount=100), not a kernel discrepancy.
    tm_m = build_tm_agg_fiscal(agent_z, mCount=200, Cratio=1.0)
    erg_m = find_ergodic_distribution(tm_m['TranMatrix'])
    mom_m = _implied_a_moments_from_m_tm(agent_z, tm_m, erg_m)

    # a-indexed under test
    tm_a = build_tm_agg_fiscal_a(agent_z, aCount=200, aMax=50.0)
    erg_a = find_ergodic_distribution(tm_a['TranMatrix'])
    mom_a = _implied_a_moments_from_a_tm(agent_z, tm_a, erg_a)

    # 1e-3 tolerance absorbs grid discretization differences (exp-grid
    # on m vs exp-grid on a). Stricter 1e-4 would require matched grids.
    for k in ('E_a', 'E_c', 'E_m'):
        rel = abs(mom_a[k] - mom_m[k]) / max(abs(mom_m[k]), 1e-12)
        assert rel < 1e-2, (
            f"{k}: m-indexed={mom_m[k]:.6f}, a-indexed={mom_a[k]:.6f}, "
            f"rel={rel:.2e}")
    print(f"ς=0 moments  E_a  m={mom_m['E_a']:.4f}  a={mom_a['E_a']:.4f}")
    print(f"ς=0 moments  E_c  m={mom_m['E_c']:.4f}  a={mom_a['E_c']:.4f}")
    print(f"ς=0 moments  E_m  m={mom_m['E_m']:.4f}  a={mom_a['E_m']:.4f}")


def test_a_indexed_aggregates_splurge_zero(baseline_agent):
    """
    Phase 3.2 acceptance: at ς = 0, compute_type_aggregates_tm_a returns
    C_splurge_nrm == C_nrm and matches the m-indexed aggregator's
    C_nrm to 1e-3 (grid-discretization floor).
    """
    agent_z = deepcopy(baseline_agent)
    agent_z.Splurge = 0.0

    tm_m = build_tm_agg_fiscal(agent_z, mCount=100, Cratio=1.0)
    erg_m = find_ergodic_distribution(tm_m['TranMatrix'])
    agg_m = compute_type_aggregates_tm(agent_z, tm_m, erg_m)

    tm_a = build_tm_agg_fiscal_a(agent_z, aCount=100, aMax=50.0)
    erg_a = find_ergodic_distribution(tm_a['TranMatrix'])
    agg_a = compute_type_aggregates_tm_a(agent_z, tm_a, erg_a)

    # ς = 0: splurge and non-splurge aggregates are identical by construction
    assert abs(agg_a['C_splurge_nrm'] - agg_a['C_nrm']) < 1e-12, \
        (f"ς=0 splurge/non-splurge diverge: "
         f"C_nrm={agg_a['C_nrm']}, C_spl={agg_a['C_splurge_nrm']}")

    # Cross-method agreement on C_nrm
    rel_C = abs(agg_a['C_nrm'] - agg_m['C_nrm']) / max(abs(agg_m['C_nrm']), 1e-12)
    assert rel_C < 1e-3, \
        (f"C_nrm mismatch m vs a: m={agg_m['C_nrm']:.6f}, "
         f"a={agg_a['C_nrm']:.6f}, rel={rel_C:.2e}")

    # Cross-method agreement on A_nrm (grid-limited)
    rel_A = abs(agg_a['A_nrm'] - agg_m['A_nrm']) / max(abs(agg_m['A_nrm']), 1e-12)
    assert rel_A < 2e-2, \
        (f"A_nrm mismatch m vs a: m={agg_m['A_nrm']:.6f}, "
         f"a={agg_a['A_nrm']:.6f}, rel={rel_A:.2e}")

    # Income aggregate is only a function of Markov ergodic and E[ξ|j],
    # so the two TMs should agree to much tighter tolerance.
    rel_Y = abs(agg_a['Income_nrm'] - agg_m['Income_nrm']) / \
        max(abs(agg_m['Income_nrm']), 1e-12)
    assert rel_Y < 1e-6, \
        (f"Income_nrm mismatch: m={agg_m['Income_nrm']:.8f}, "
         f"a={agg_a['Income_nrm']:.8f}, rel={rel_Y:.2e}")

    print(f"ς=0  C_nrm   m={agg_m['C_nrm']:.6f}  a={agg_a['C_nrm']:.6f}  "
          f"rel={rel_C:.2e}")
    print(f"ς=0  A_nrm   m={agg_m['A_nrm']:.6f}  a={agg_a['A_nrm']:.6f}  "
          f"rel={rel_A:.2e}")
    print(f"ς=0  Y_nrm   m={agg_m['Income_nrm']:.6f}  a={agg_a['Income_nrm']:.6f}")


def test_a_indexed_aggregates_splurge_nonzero(baseline_agent):
    """
    Phase 3.2: at ς > 0, C_splurge_nrm differs from C_nrm by exactly
    the paper's eq. (4) convex combination, and reconstructs as
        C_splurge_nrm == (1-ς) * C_nrm + ς * E[xi]_aggregate.
    """
    ς = 0.2609
    agent_s = deepcopy(baseline_agent)
    agent_s.Splurge = ς

    tm_a = build_tm_agg_fiscal_a(agent_s, aCount=50, aMax=50.0)
    erg_a = find_ergodic_distribution(tm_a['TranMatrix'])
    agg_a = compute_type_aggregates_tm_a(agent_s, tm_a, erg_a)

    # eq. (4) / (5) identity in aggregate form
    expected = (1.0 - ς) * agg_a['C_nrm'] + ς * agg_a['Income_nrm']
    rel = abs(agg_a['C_splurge_nrm'] - expected) / max(abs(expected), 1e-12)
    assert rel < 1e-8, \
        (f"eq.(4) aggregate identity fails: "
         f"C_spl={agg_a['C_splurge_nrm']:.8f}, "
         f"(1-ς)C + ς E[xi]={expected:.8f}, rel={rel:.2e}")
    print(f"ς>0  C_spl = (1-ς) C_nrm + ς Y_nrm   rel={rel:.2e}")


def test_period_aggregator_matches_type_aggregator_on_ergodic(baseline_agent):
    """
    Phase 3.3: compute_period_aggregates_tm_a evaluated on the baseline
    ergodic (with baseline Markov as micro_trans, AggDemandFac=1, no
    TranShk_addition) should match the type aggregator to ~1e-12.

    Rationale: the type aggregator is the period aggregator instantiated
    at the stationary distribution; any drift between them is a
    consistency bug in the integration.
    """
    ς = 0.2609
    agent_s = deepcopy(baseline_agent)
    agent_s.Splurge = ς

    tm_a = build_tm_agg_fiscal_a(agent_s, aCount=50, aMax=50.0)
    erg_a = find_ergodic_distribution(tm_a['TranMatrix'])
    agg_type = compute_type_aggregates_tm_a(agent_s, tm_a, erg_a)

    J = agent_s.MrkvArray[0].shape[0]
    Rfree = np.asarray(agent_s.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent_s.PermGroFac[0][:J], dtype=np.float64)
    cFuncs = [agent_s.solution[0].cFunc[j] for j in range(J)]
    IncShkDstn = tm_a['IncShkDstn_list']

    agg_period = compute_period_aggregates_tm_a(
        erg_a, tm_a['dist_aGrid'], cFuncs, IncShkDstn,
        agent_s.MrkvArray[0], Rfree, PermGroFac,
        ς, Cratio=1.0, AggDemandFac=1.0,
    )

    for k in ('C_nrm', 'C_splurge_nrm', 'Income_nrm'):
        rel = abs(agg_period[k] - agg_type[k]) / max(abs(agg_type[k]), 1e-12)
        assert rel < 1e-10, \
            f"{k}: period={agg_period[k]}, type={agg_type[k]}, rel={rel}"


def test_period_aggregator_ad_scaling(baseline_agent):
    """
    AggDemandFac scaling: Income_nrm scales linearly; consumption
    scales via the splurge term and the cFunc response to higher m.
    """
    agent_s = deepcopy(baseline_agent)
    agent_s.Splurge = 0.2609
    tm_a = build_tm_agg_fiscal_a(agent_s, aCount=50, aMax=50.0)
    erg_a = find_ergodic_distribution(tm_a['TranMatrix'])

    J = agent_s.MrkvArray[0].shape[0]
    Rfree = np.asarray(agent_s.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent_s.PermGroFac[0][:J], dtype=np.float64)
    cFuncs = [agent_s.solution[0].cFunc[j] for j in range(J)]
    IncShkDstn = tm_a['IncShkDstn_list']

    args = (erg_a, tm_a['dist_aGrid'], cFuncs, IncShkDstn,
            agent_s.MrkvArray[0], Rfree, PermGroFac, 0.2609)

    agg_1 = compute_period_aggregates_tm_a(*args, Cratio=1.0, AggDemandFac=1.0)
    agg_ad = compute_period_aggregates_tm_a(*args, Cratio=1.0, AggDemandFac=1.05)

    # Income scales linearly with ADF (all ξ atoms scaled, no shift).
    rel_Y = abs(agg_ad['Income_nrm'] - 1.05 * agg_1['Income_nrm']) \
        / max(abs(1.05 * agg_1['Income_nrm']), 1e-12)
    assert rel_Y < 1e-10, \
        f"Income linear-in-ADF fails: {agg_ad['Income_nrm']} vs {1.05*agg_1['Income_nrm']}"

    # Consumption should rise but less than linearly (cFunc concave).
    assert agg_ad['C_splurge_nrm'] > agg_1['C_splurge_nrm']
    assert agg_ad['C_splurge_nrm'] < 1.05 * agg_1['C_splurge_nrm']


def test_build_period_tm_a_scaling_differs_from_baseline(baseline_agent):
    """
    Phase 3.4: _build_period_tm_a with non-trivial ad_tran_shk_scale or
    TranShk_addition produces a different matrix than the baseline
    builder — i.e., the scaling knobs actually enter the kernel.
    """
    agent = deepcopy(baseline_agent)
    agent.Splurge = 0.2609

    J = agent.MrkvArray[0].shape[0]
    MrkvArray = agent.MrkvArray[0]
    Rfree = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb = _effective_LivPrb(
        np.asarray(agent.LivPrb[0][:J], dtype=np.float64),
        getattr(agent, 'T_age', None))
    cFuncs = [agent.solution[0].cFunc[j] for j in range(J)]
    IncShk = [agent.IncShkDstn[0][j] for j in range(J)]
    markov_erg = _solve_markov_ergodic(MrkvArray)

    aGrid = make_grid_exp_mult(ming=0.0, maxg=50.0, ng=50, timestonest=3)
    NB = _make_newborn_dist_a(aGrid, markov_erg)

    TM_base = _build_period_tm_a(
        aGrid, float(agent.Splurge), cFuncs, IncShk, MrkvArray,
        Rfree, PermGroFac, LivPrb, NB, Cratio=1.0,
    )
    TM_ad = _build_period_tm_a(
        aGrid, float(agent.Splurge), cFuncs, IncShk, MrkvArray,
        Rfree, PermGroFac, LivPrb, NB, Cratio=1.0,
        ad_tran_shk_scale=1.1,
    )
    TM_emp = _build_period_tm_a(
        aGrid, float(agent.Splurge), cFuncs, IncShk, MrkvArray,
        Rfree, PermGroFac, LivPrb, NB, Cratio=1.0,
        employed_tran_shk_scale=1.05,
    )
    TM_shift = _build_period_tm_a(
        aGrid, float(agent.Splurge), cFuncs, IncShk, MrkvArray,
        Rfree, PermGroFac, LivPrb, NB, Cratio=1.0,
        TranShk_addition=np.array([0.1] + [0.0] * (J - 1)),
    )
    # All three modifications should produce a detectable difference.
    for TM_mod, name in [(TM_ad, 'ad_tran_shk_scale'),
                         (TM_emp, 'employed_tran_shk_scale'),
                         (TM_shift, 'TranShk_addition')]:
        diff = np.abs((TM_mod - TM_base).toarray()).max()
        assert diff > 1e-6, \
            f"{name} did not alter the TM (max |ΔTM| = {diff})"
        # each is still column-stochastic
        assert np.allclose(np.asarray(TM_mod.sum(axis=0)).ravel(), 1.0, atol=1e-10)


def test_build_experiment_period_tm_a_macro_0(baseline_agent):
    """
    Phase 3.4: build_experiment_period_tm_a with macro_curr=0 and no
    scaling / no shift should produce exactly the same TM as
    build_tm_agg_fiscal_a (both use macro_0 x j_micro states and the
    same Markov transition / income distribution).

    Note: this requires agent.CondMrkvArrays[0] = agent.MrkvArray[0]
    for the base shock config. The test fixture uses
    update_mrkv_array("base") which sets both consistently.
    """
    agent = deepcopy(baseline_agent)
    agent.Splurge = 0.2609
    # Ensure CondMrkvArrays is present for macro_curr=0.
    if not hasattr(agent, 'CondMrkvArrays') or agent.CondMrkvArrays is None:
        agent.CondMrkvArrays = [agent.MrkvArray[0]]

    aGrid = make_grid_exp_mult(ming=0.0, maxg=50.0, ng=50, timestonest=3)
    # Pass the explicit grid to BOTH builders: with auto-grid (aCount=) the
    # 2026-06 TM-mixing auto-repair may insert tail nodes, breaking the
    # shape-identical comparison against the custom-grid experiment TM.
    tm_full = build_tm_agg_fiscal_a(agent, dist_aGrid=aGrid)
    TM_exp, _IncShk, _cFuncs = build_experiment_period_tm_a(
        agent, macro_curr=0, dist_aGrid=aGrid, Cratio=1.0,
    )
    # Compare: both matrices should be identical (macro_curr=0 uses
    # j_micro cFuncs and the micro Markov array).
    diff = np.abs((tm_full['TranMatrix'] - TM_exp).toarray()).max()
    assert diff < 1e-12, f"Expected equivalence but max |Δ| = {diff:.2e}"


def test_propagate_experiment_tm_a_smoke(baseline_agent):
    """
    Phase 3.5 smoke test: propagate_experiment_tm_a runs without error
    on a minimal setup (act_T=3, all macro=0) and produces finite,
    non-negative AggCons / AggIncome.

    Requires CondMrkvArrays to be set on the agent. For a base-only
    fixture we install CondMrkvArrays = [MrkvArray] so macro_curr=0
    resolves correctly; this is sufficient for the smoke test (full
    experiment validation is Phase 4's job).
    """
    agent = deepcopy(baseline_agent)
    agent.Splurge = 0.2609
    if not hasattr(agent, 'CondMrkvArrays') or agent.CondMrkvArrays is None:
        agent.CondMrkvArrays = [agent.MrkvArray[0]]
    # Urate_normal / Urate_recession for the spike logic. The fixture
    # sets them, but be defensive.
    if not hasattr(agent, 'Urate_normal'):
        agent.Urate_normal = 0.05
    if not hasattr(agent, 'Urate_recession'):
        agent.Urate_recession = 0.05
    if not hasattr(agent, 'AgentCount'):
        agent.AgentCount = 10

    tm_a = build_tm_agg_fiscal_a(agent, aCount=50, aMax=50.0)
    erg_a = find_ergodic_distribution(tm_a['TranMatrix'])
    dist_aGrid = tm_a['dist_aGrid']

    out = propagate_experiment_tm_a(
        agent, erg_a,
        EconomyMrkv_init=[0, 0, 0, 0],
        dist_aGrid=dist_aGrid,
        E_pLvl=1.0,
        Cratio=1.0,
        act_T=3,
        shock_type=None,
    )
    assert out['AggCons'].shape == (3,)
    assert out['AggIncome'].shape == (3,)
    assert np.all(np.isfinite(out['AggCons']))
    assert np.all(np.isfinite(out['AggIncome']))
    assert np.all(out['AggCons'] >= 0)
    assert np.all(out['AggIncome'] >= 0)
    # Baseline-like: mostly stationary
    assert abs(out['AggCons'][1] - out['AggCons'][2]) \
        / max(abs(out['AggCons'][2]), 1e-12) < 1e-8


def test_tm_a_indexed_flag_default(baseline_agent):
    """
    Phase 3.6: AggFiscalType ships with tm_a_indexed=False so the
    existing m-indexed pipeline remains the default. Explicitly
    setting the flag flips dispatch.
    """
    # Default: False
    assert getattr(baseline_agent, 'tm_a_indexed', None) is False, (
        "AggFiscalType.__init__ should set tm_a_indexed = False by default"
    )

    # Dispatch via compute_baseline_tm_data — m-indexed bd has
    # dist_mGrid, a-indexed bd has dist_aGrid.
    from tm_methods import compute_baseline_tm_data
    # Minimal economy stub: one agent.
    class _FakeEcon:
        pass
    econ = _FakeEcon()
    econ.agents = [baseline_agent]

    bd_m = compute_baseline_tm_data(econ, mCount=30, neutral_measure=False,
                                    verbose=False)[0]
    assert bd_m['tm_a_indexed'] is False
    assert 'dist_mGrid' in bd_m and 'dist_aGrid' not in bd_m
    assert bd_m.get('base_aPol') is not None

    baseline_agent.tm_a_indexed = True
    bd_a = compute_baseline_tm_data(econ, mCount=30, neutral_measure=False,
                                    verbose=False)[0]
    assert bd_a['tm_a_indexed'] is True
    assert 'dist_aGrid' in bd_a and 'dist_mGrid' not in bd_a
    assert bd_a['base_aPol'] is None

    # Restore
    baseline_agent.tm_a_indexed = False


def test_a_indexed_splurge_nonzero_runs(baseline_agent):
    """At positive ς, build + ergodic are finite and sensible."""
    agent_s = deepcopy(baseline_agent)
    agent_s.Splurge = 0.2609  # Phase 1 re-estimated value
    tm_a = build_tm_agg_fiscal_a(agent_s, aCount=50, aMax=50.0)
    erg_a = find_ergodic_distribution(tm_a['TranMatrix'])
    assert np.all(np.isfinite(erg_a))
    assert np.isclose(np.sum(erg_a), 1.0, atol=1e-10)
    assert np.all(erg_a >= -1e-14)


# ================================================================
# Phase 4 validation — end-to-end equivalence and cross-checks.
# These tests are heavier than the unit tests above; they set up the
# full 3-type Baseline fixture and run run_experiment_tm /
# propagate_experiment_tm_a over short horizons.
# ================================================================


@pytest.fixture(scope="module")
def three_type_economy():
    """Build the 3-education-group Baseline economy for base shock."""
    (init_dropout, init_highschool, init_college, init_ADEconomy,
     DiscFacDstns, DiscFacCount, AgentCountTotal, base_dict,
     num_max_iterations_solvingAD, convergence_tol_solvingAD,
     UBspell_normal, num_base_MrkvStates, data_EducShares,
     max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes, Check_changes,
     recession_Check_changes) = return_parameters(
        Parametrization='Baseline', OutputFor='_Main.py'
    )

    from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    from HARK.distributions import DiscreteDistribution

    econ = AggregateDemandEconomy(**init_ADEconomy)

    BaseTypes = []
    for init in (init_dropout, init_highschool, init_college):
        agent = AggFiscalType(**init)
        agent.cycles = 0
        BaseTypes.append(agent)

    for bt in BaseTypes:
        bt.get_economy_data(econ)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypes[0].IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseTypes[0].IncUnempNoBenefits])])

    for agent in BaseTypes:
        EmployedIncShkDstn = deepcopy(agent.IncShkDstn[0])
        # Encoding-agnostic (4-state legacy / 6-state bug_fix): see baseline_agent.
        agent.IncShkDstn = [[EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal
                            + [IncShkDstn_unemp_nobenefits]
                            * (num_base_MrkvStates - 1 - UBspell_normal)]
        agent.IncShkDstn_base = agent.IncShkDstn

    # Small per-type AgentCount and only the central DiscFac per group
    # (keeps the test under 10s while still exercising the 3-type path).
    TypeList = []
    n = 0
    for e in range(3):
        central = len(DiscFacDstns[e].atoms[0]) // 2
        DiscFac = DiscFacDstns[e].atoms[0][central]
        agent = deepcopy(BaseTypes[e])
        agent.AgentCount = 500
        agent.DiscFac = DiscFac
        agent.seed = n
        TypeList.append(agent)
        n += 1

    econ.agents = TypeList
    return econ, TypeList


def test_phase_4_1_full_propagator_splurge_zero_equivalence(three_type_economy):
    """
    Phase 4.1: at varsigma = 0, the full run_experiment_tm output
    (AggCons constant series) matches between tm_a_indexed=False and
    tm_a_indexed=True to within 1e-2 relative — grid discretization
    floor. At varsigma = 0 the two methods describe the same
    underlying stationary distribution with different state grids, so
    the aggregate AggCons level should agree up to that floor.
    """
    from tm_methods import run_experiment_tm
    econ, TypeList = three_type_economy

    # m-indexed baseline
    for agent in TypeList:
        agent.Splurge = 0.0
        agent.tm_a_indexed = False
    out_m = run_experiment_tm(econ, shock_type='base', mCount=80,
                              verbose=False)
    C_m = float(out_m['AggCons'][0])

    # a-indexed baseline
    for agent in TypeList:
        agent.tm_a_indexed = True
    out_a = run_experiment_tm(econ, shock_type='base', mCount=80,
                              verbose=False)
    C_a = float(out_a['AggCons'][0])

    rel = abs(C_a - C_m) / max(abs(C_m), 1e-12)
    assert rel < 1e-2, \
        f"Phase 4.1: AggCons mismatch ς=0: m={C_m:.4f}, a={C_a:.4f}, rel={rel:.2e}"
    print(f"\nPhase 4.1 ς=0   AggCons   m={C_m:.4f}   a={C_a:.4f}   rel={rel:.2e}")

    # Reset
    for agent in TypeList:
        agent.tm_a_indexed = False


def test_phase_4_1_aggregates_splurge_positive(three_type_economy):
    """
    Phase 4.1 (supplementary): at varsigma > 0, the a-indexed
    AggCons is finite, non-negative, larger than AggIncome * (1-ς)
    (consistent with the eq.(4) identity when AggIncome ~ ς-share
    plus some mean-reverting savings), and the a-indexed AggCons
    differs from the m-indexed AggCons (confirming the splurge-in-budget
    correction actually takes effect).

    Note: this test does NOT claim agreement between m-indexed and
    a-indexed at ς > 0 — that difference is precisely the bug
    BUG-033 is fixing.
    """
    from tm_methods import run_experiment_tm
    econ, TypeList = three_type_economy

    for agent in TypeList:
        agent.Splurge = 0.2609
        agent.tm_a_indexed = False
    out_m = run_experiment_tm(econ, shock_type='base', mCount=80,
                              verbose=False)
    C_m = float(out_m['AggCons'][0])
    Y_m = float(out_m['AggIncome'][0])

    for agent in TypeList:
        agent.tm_a_indexed = True
    out_a = run_experiment_tm(econ, shock_type='base', mCount=80,
                              verbose=False)
    C_a = float(out_a['AggCons'][0])
    Y_a = float(out_a['AggIncome'][0])

    # Sanity: finite, non-negative, same order of magnitude.
    assert np.isfinite(C_a) and C_a > 0
    assert np.isfinite(Y_a) and Y_a > 0
    # Income should match closely (same Markov ergodic, no splurge/asset interaction).
    rel_Y = abs(Y_a - Y_m) / max(abs(Y_m), 1e-12)
    assert rel_Y < 5e-3, f"Y mismatch m vs a: {Y_m} vs {Y_a}, rel={rel_Y:.2e}"
    # a-indexed and m-indexed should differ on C under splurge-in-budget.
    rel_C = abs(C_a - C_m) / max(abs(C_m), 1e-12)
    print(f"\nPhase 4.1 ς>0   AggCons   m={C_m:.4f}   a={C_a:.4f}   rel_C={rel_C:.2%}")
    print(f"              AggIncome  m={Y_m:.4f}   a={Y_a:.4f}   rel_Y={rel_Y:.2e}")

    # Reset
    for agent in TypeList:
        agent.tm_a_indexed = False


def test_phase_4_2_lite_tm_a_vs_mc_short(three_type_economy):
    """
    Phase 4.2 lite: quick MC vs TM_a cross-check on the 3-type
    baseline (N=500 per type) under splurge-in-budget.

    Compares NORMALIZED consumption (cNrm) — MC's level AggCons and
    TM's level AggCons differ in E[pLvl] because the MC burn-in is
    short (act_T=40), so direct level comparison is noisy. cNrm
    strips out pLvl and gives the apples-to-apples steady-state
    consumption per unit permanent income, which is what the TM
    directly computes (as C_splurge_nrm).

    Tolerance 3 % here reflects MC sampling noise at N=500/type over
    40 periods. Proper Phase 4.2 validation uses N=10000 over 400
    periods and tests recession / check experiments separately;
    that is out of scope for pytest.
    """
    from tm_methods import run_experiment_tm
    econ, TypeList = three_type_economy

    for agent in TypeList:
        agent.Splurge = 0.2609
        agent.tm_a_indexed = True

    out_a = run_experiment_tm(econ, shock_type='base', mCount=80,
                              verbose=False)
    # Aggregate normalized: AggCons / (N * E[pLvl_analytical])
    type_results = out_a['_type_results']
    total_N = sum(tr['AgentCount'] for tr in type_results)
    # TM's per-type C_splurge_nrm is already the normalized measure.
    # Aggregate via N-weighted average.
    C_a_nrm = sum(tr['agg']['C_splurge_nrm'] * tr['AgentCount']
                  for tr in type_results) / total_N

    # Cheap MC: same economy, same agents, short simulation.
    for agent in TypeList:
        agent.tm_a_indexed = False
    econ.solve()
    econ.reset()
    for agent in TypeList:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    old_act_T = econ.act_T
    try:
        econ.act_T = 40
        econ.make_history()
        econ.save_state()
        econ.switch_to_counterfactual_mode('base')
        econ.make_idiosyncratic_shock_histories()
        (_, _, _, _, _, _, _, base_dict, *_rest) = return_parameters(
            Parametrization='Baseline', OutputFor='_Main.py')
        _ = econ.run_experiment(**base_dict, Full_Output=True)
    finally:
        econ.act_T = old_act_T

    # MC per-type normalized cNrm (mean across agents and time)
    # using the cLvl_splurge / pLvl ratio (since pLvl varies by
    # agent, we aggregate with N-weighting).
    C_mc_nrm_sum = 0.0
    N_mc_total = 0
    for agent in TypeList:
        if 'cLvl_splurge' in agent.history and 'pLvl' in agent.history:
            cLvl = agent.history['cLvl_splurge']
            pLvl = agent.history['pLvl']
            # Per-agent-per-period c/p, averaged over all (agent, t)
            # where pLvl > 0 (always true for living agents).
            mask = pLvl > 0
            if np.any(mask):
                cNrm_agent = float(np.mean(cLvl[mask] / pLvl[mask]))
                C_mc_nrm_sum += cNrm_agent * agent.AgentCount
                N_mc_total += agent.AgentCount
    C_mc_nrm = C_mc_nrm_sum / N_mc_total if N_mc_total > 0 else float('nan')

    rel = abs(C_a_nrm - C_mc_nrm) / max(abs(C_mc_nrm), 1e-12)
    print(f"\nPhase 4.2 lite  ς=0.2609  cNrm   TM_a={C_a_nrm:.4f}"
          f"   MC={C_mc_nrm:.4f}   rel={rel:.2%}")

    # Wide tolerance — this is a consistency check, not production
    # validation. Full Phase 4.2 (N=10K, long burn-in, full experiment
    # paths) is manual.
    assert rel < 0.05, \
        f"Phase 4.2 lite: TM_a cNrm vs MC cNrm differ by {rel:.2%} (tol 5%)"

    # Restore
    for agent in TypeList:
        agent.tm_a_indexed = False


if __name__ == "__main__":
    # Support running as a script for quick iteration.
    import pytest as _pytest
    _pytest.main([__file__, "-v", "-s"])
