"""
Phase 1 L3a: cheap-tier MC↔TM convergence sanity for HS cohort.

Per `BUGS_private/HAFiscal_splurge_budget_inconsistency/code_cheatsheet_phase1_convergence.md`
L3a entries (~half day code + ~1-2 hr compute).

L3a is the cheapest gate in the Phase 1 cascade: single cohort (HS), small
N (≤5k), coarse grids (a-grid ≤ 200, ξ-grid = 7). The 6 tests below catch
gross bugs and verify framework basics. Failing here saves all subsequent
tier compute.

Tests (each maps to a row in the L3a table of code_cheatsheet_phase1_convergence.md):
  1. test_l3a_mc_point_estimate_finite_HS
  2. test_l3a_mc_lln_trend_HS                  → (eq:mc-convergence-rate)
  3. test_l3a_tm_ergodic_exists_HS             → (eq:markov-ergodic)
  4. test_l3a_tm_grid_trend_HS                 → (eq:tm-grid-convergence)
  5. test_l3a_cross_method_agreement_HS_loose  → (eq:mc-tm-asymptotic-agreement) ε=5%
  6. test_l3a_interpretation_dispatch_HS       → kernel dispatch verification

HALT criteria per cheat-sheet apply: any failure stops L3a; do NOT escalate
to L3b (per cascade-gating principle, memory feedback_cascade_gating.md).

Run via:
  pytest Code/HA-Models/FromPandemicCode/test_phase1_l3a.py -v
"""

import os
import sys
import numpy as np
import pytest
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

# CLAUDE.md: patch sys.argv before importing EstimParameters.
_SAVED_ARGV = sys.argv
sys.argv = ['test_phase1_l3a']

from EstimParameters import (
    init_highschool, init_ADEconomy, UBspell_normal,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from tm_methods import (
    build_tm_agg_fiscal_a,
    compute_type_aggregates_tm_a,
    find_ergodic_distribution,
)
from HARK.distributions import DiscreteDistribution

sys.argv = _SAVED_ARGV


# ----------------------------------------------------------------------
# Module-scoped fixture: solved HS agent (reused across tests)
# ----------------------------------------------------------------------

@pytest.fixture(scope='module')
def solved_HS():
    """Build + solve a Highschool AggFiscalType."""
    init = deepcopy(init_highschool)
    agent = AggFiscalType(**init)
    agent.cycles = 0
    economy = AggregateDemandEconomy(**init_ADEconomy)
    agent.get_economy_data(economy)

    # Replicate the IncShkDstn setup (mirrors estim_phase2_tm_a.py).
    IncomeDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnemp])]
    )
    IncomeDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnempNoBenefits])]
    )
    agent.IncShkDstn = [
        [agent.IncShkDstn[0]]
        + [IncomeDstn_unemp] * UBspell_normal
        + [IncomeDstn_unemp_nobenefits]
    ]
    agent.IncShkDstn_base = agent.IncShkDstn

    economy.agents = [agent]
    economy.solve()
    return agent


def _assert_cross_method_pass(mc_mean, mc_se, tm_value, eps_gap=0.01, eps_se=0.01,
                              label='cross-method'):
    """Generic Phase 1 cross-method success check.

    Per `(eq:mc-tm-asymptotic-agreement)` of why_convergence_validation.md §2.4:
    success requires BOTH conditions:
        rel_gap = |MC - TM| / |MC| <= eps_gap
        rel_SE  = SE(MC)    / |MC| <= eps_se

    Raises AssertionError with a diagnostic message on failure.

    Generic so all L3a-L3d cross-method tests use the same gate; tolerance
    can be tightened per-test (e.g., L3d may use eps_gap=eps_se=0.005).
    """
    rel_gap = abs(mc_mean - tm_value) / max(abs(mc_mean), 1e-12)
    rel_se  = mc_se / max(abs(mc_mean), 1e-12)
    print(f"  {label}  MC={mc_mean:.5f}  SE={mc_se:.5f}  TM={tm_value:.5f}")
    print(f"  {label}  rel_gap={rel_gap:.4%} (≤{eps_gap:.0%})  rel_SE={rel_se:.4%} (≤{eps_se:.0%})")
    pass_gap = rel_gap <= eps_gap
    pass_se = rel_se <= eps_se
    if not (pass_gap and pass_se):
        msgs = []
        if not pass_gap:
            msgs.append(f"rel_gap={rel_gap:.4%} > {eps_gap:.0%}")
        if not pass_se:
            msgs.append(f"rel_SE={rel_se:.4%} > {eps_se:.0%} (MC has not stabilized)")
        raise AssertionError(
            f"{label} HALT — Phase 1 cross-method gate failed: "
            + "; ".join(msgs)
            + f". MC={mc_mean:.5f}, MC SE={mc_se:.5f}, TM={tm_value:.5f}"
        )


def _compute_tm_moment_HS(agent, a_grid_size, interpretation='CDC'):
    """Run the TM-a chain and return key moments dict.

    Returns dict with: K_Y, A_nrm, Income_nrm, ergodic_sum, n_grid_pts.
    """
    # BUG-051 matched-pair fix: callers in test_phase1_l3a/l3b/l3c compare CDC
    # vs ESC in-process by calling this helper with both interpretations.
    # build_tm_agg_fiscal_a validates its explicit interpretation against
    # HAFISCAL_INTERPRETATION, so set the env to match THIS arm before the
    # kernel calls and restore the prior value in a finally so arms don't leak
    # into each other. The guard is NOT weakened. (This helper is shared across
    # l3a/l3b/l3c and has no monkeypatch fixture in scope, so use os.environ +
    # finally restore.)
    _prev_interp = os.environ.get('HAFISCAL_INTERPRETATION')
    os.environ['HAFISCAL_INTERPRETATION'] = interpretation
    try:
        tm_data = build_tm_agg_fiscal_a(
            agent, aCount=a_grid_size, interpretation=interpretation,
        )
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
        agg = compute_type_aggregates_tm_a(
            agent, tm_data, ergodic, interpretation=interpretation,
        )
    finally:
        if _prev_interp is None:
            os.environ.pop('HAFISCAL_INTERPRETATION', None)
        else:
            os.environ['HAFISCAL_INTERPRETATION'] = _prev_interp
    return {
        'K_Y': agg['A_nrm'] / agg['Income_nrm'] if agg['Income_nrm'] > 0 else float('nan'),
        'A_nrm': agg['A_nrm'],
        'Income_nrm': agg['Income_nrm'],
        'C_nrm': agg['C_nrm'],
        'ergodic_sum': float(ergodic.sum()),
        'n_grid_pts': len(tm_data['dist_aGrid']),
        'tm_data': tm_data,
        'ergodic': ergodic,
    }


def _run_mc_HS_simple(agent_template, N, seed, T_sim=400, T_burnin=200):
    """Run a minimal HS MC simulation and return key moments.

    Uses agent.initialize_sim() + agent.simulate(T_sim). Tracks aNrm and
    TranShk (NORMALIZED — divided by permanent income) to match the TM
    convention. Computing MC K/Y as mean(aLvl)/mean(pLvl·TranShk) would
    introduce a permanent-income covariance term that the TM normalized
    aggregator doesn't have, producing a structural cross-method gap that
    would HALT L3b spuriously. Comparing normalized moments (a-per-pLvl)
    on both sides removes that bias and is the apples-to-apples comparison.

    Returns dict with: K_Y (normalized), mean_aNrm, mean_TranShk, N, seed.
    """
    agent = deepcopy(agent_template)
    agent.AgentCount = N
    agent.seed = seed
    agent.T_sim = T_sim
    agent.track_vars = ['aNrm', 'TranShk', 'pLvl']
    agent.initialize_sim()
    # Baseline AD/macro attrs (needed by AggIndMrkv get_states + get_controls).
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.EconomyMrkvNow_hist = [0] * T_sim
    agent.simulate()

    # After-burnin window for moments
    burnin_idx = T_burnin if T_burnin < T_sim else T_sim // 2
    aNrm_post = agent.history['aNrm'][burnin_idx:]
    tran_post = agent.history['TranShk'][burnin_idx:]
    # K/Y under TM convention: mean(aNrm) / mean(TranShk) — normalized
    # so it directly compares to A_nrm / Income_nrm from TM aggregator.
    mean_aNrm = float(np.mean(aNrm_post))
    mean_TranShk = float(np.mean(tran_post))
    K_Y = mean_aNrm / mean_TranShk if mean_TranShk > 0 else float('nan')

    return {
        'K_Y': K_Y,
        'mean_aNrm': mean_aNrm,
        'mean_TranShk': mean_TranShk,
        'N': N,
        'seed': seed,
    }


# ----------------------------------------------------------------------
# L3a Test 1: MC point estimate is finite and deterministic
# ----------------------------------------------------------------------

def test_l3a_mc_point_estimate_finite_HS(solved_HS):
    """Trivial sanity: MC K/Y is finite and deterministic given seed."""
    moments_a = _run_mc_HS_simple(solved_HS, N=500, seed=42, T_sim=200, T_burnin=100)
    moments_b = _run_mc_HS_simple(solved_HS, N=500, seed=42, T_sim=200, T_burnin=100)

    assert np.isfinite(moments_a['K_Y']), f"K/Y not finite: {moments_a['K_Y']}"
    assert moments_a['K_Y'] > 0, f"K/Y not positive: {moments_a['K_Y']}"
    assert abs(moments_a['K_Y'] - moments_b['K_Y']) < 1e-12, (
        f"MC not deterministic given seed: {moments_a['K_Y']} vs {moments_b['K_Y']}"
    )


# ----------------------------------------------------------------------
# L3a Test 2: MC LLN trend — mean(K/Y | N) trends toward stable value
# Validates: (eq:mc-convergence-rate) loose check
# ----------------------------------------------------------------------

def test_l3a_mc_lln_trend_HS(solved_HS):
    """Verify MC mean(K/Y) trends as N grows from 500 → 5000.

    Loose check at L3a (the tight asymptotic-rate test is L3b). Just verify
    that std(K/Y across seeds | N) is smaller at larger N — qualitative
    LLN behavior.
    """
    Ns = [500, 1000, 5000]
    n_seeds = 3  # Cheap at L3a; L3b uses 5+
    results = {}
    for N in Ns:
        ks = [_run_mc_HS_simple(solved_HS, N=N, seed=s, T_sim=200, T_burnin=100)['K_Y']
              for s in range(n_seeds)]
        results[N] = {'mean': float(np.mean(ks)), 'std': float(np.std(ks)), 'all': ks}

    # Print for diagnostic
    print()
    for N in Ns:
        print(f"  L3a MC HS  N={N:>5d}  mean(K/Y)={results[N]['mean']:.4f}  std={results[N]['std']:.4f}")

    # Verify std shrinks (qualitative LLN)
    std_500 = results[500]['std']
    std_5000 = results[5000]['std']
    assert std_5000 < std_500, (
        f"MC std should shrink with N: std(N=500)={std_500:.4f}, "
        f"std(N=5000)={std_5000:.4f}. Suggests MC noise is non-i.i.d. or burn-in insufficient."
    )

    # Verify mean(K/Y) doesn't drift wildly across N
    means = [results[N]['mean'] for N in Ns]
    drift = max(means) - min(means)
    overall_mean = np.mean(means)
    assert drift / overall_mean < 0.10, (
        f"mean(K/Y) drifts too much across N: drift/mean = {drift/overall_mean:.4f} > 0.10"
    )


# ----------------------------------------------------------------------
# L3a Test 3: TM ergodic exists
# Validates: (eq:markov-ergodic)
# ----------------------------------------------------------------------

def test_l3a_tm_ergodic_exists_HS(solved_HS):
    """TM ergodic computation succeeds; sums to 1; finite."""
    for grid_size in [50, 100, 200]:
        m = _compute_tm_moment_HS(solved_HS, a_grid_size=grid_size, interpretation='CDC')
        assert np.isfinite(m['K_Y']), f"K/Y not finite at grid={grid_size}"
        assert abs(m['ergodic_sum'] - 1.0) < 1e-6, (
            f"Ergodic doesn't sum to 1 at grid={grid_size}: {m['ergodic_sum']}"
        )
        assert m['A_nrm'] > 0
        assert m['Income_nrm'] > 0


# ----------------------------------------------------------------------
# L3a Test 4: TM grid trend
# Validates: (eq:tm-grid-convergence) loose check
# ----------------------------------------------------------------------

def test_l3a_tm_grid_trend_HS(solved_HS):
    """TM K/Y trends as a-grid refines from 50 → 200.

    Loose check at L3a (the tight halving-with-doubling check is L3b).
    Just verify the moment doesn't oscillate wildly.
    """
    grids = [50, 100, 200]
    Ks = []
    for g in grids:
        m = _compute_tm_moment_HS(solved_HS, a_grid_size=g, interpretation='CDC')
        Ks.append(m['K_Y'])

    print()
    for g, k in zip(grids, Ks):
        print(f"  L3a TM HS  a-grid={g:>3d}  K/Y={k:.4f}")

    # Differences should be modest at this coarse range
    drift = max(Ks) - min(Ks)
    overall = np.mean(Ks)
    assert drift / overall < 0.15, (
        f"TM K/Y drifts too much across grids 50→200: drift/mean = {drift/overall:.4f} > 0.15. "
        f"Possible TM grid issue. Values: {dict(zip(grids, Ks))}"
    )


# ----------------------------------------------------------------------
# L3a Test 5: MC↔TM cross-method agreement (loose)
# Validates: (eq:mc-tm-asymptotic-agreement) at ε = 5%
# ----------------------------------------------------------------------

def test_l3a_cross_method_agreement_HS_loose(solved_HS):
    """MC and TM agree at L3a's loose tolerance.

    Uses the generic Phase 1 gate `_assert_cross_method_pass` with L3a's
    looser tolerances (eps_gap = 0.05, eps_se = 0.05) — appropriate for
    small-N + coarse-grid sanity check. L3b/c/d tighten to 1%.
    Per (eq:mc-tm-asymptotic-agreement) of why_convergence_validation.md §2.4.
    """
    n_seeds = 3
    mc_Ks = [_run_mc_HS_simple(solved_HS, N=5000, seed=s, T_sim=200, T_burnin=100)['K_Y']
             for s in range(n_seeds)]
    mc_mean = float(np.mean(mc_Ks))
    mc_se = float(np.std(mc_Ks) / np.sqrt(n_seeds))

    tm = _compute_tm_moment_HS(solved_HS, a_grid_size=200, interpretation='CDC')
    tm_K = tm['K_Y']

    print()
    _assert_cross_method_pass(
        mc_mean=mc_mean, mc_se=mc_se, tm_value=tm_K,
        eps_gap=0.05, eps_se=0.05,
        label=f'L3a cross-method (n_seeds={n_seeds}, N=5k, a-grid=200)',
    )


# ----------------------------------------------------------------------
# L3a Test 6: Interpretation parameter actually flows
# Validates: dispatch verification (not a math equation)
# ----------------------------------------------------------------------

def test_l3a_interpretation_dispatch_HS(solved_HS):
    """Verify the interpretation parameter actually flows from the test
    through to the kernel: TM_CDC ≠ TM_ESC at Splurge>0; TM_CDC == TM_ESC
    at Splurge=0 (analytical-symmetry sanity)."""
    a_grid_size = 100

    # At Splurge>0 (default agent value), CDC and ESC TMs must differ
    m_cdc = _compute_tm_moment_HS(solved_HS, a_grid_size, interpretation='CDC')
    m_esc = _compute_tm_moment_HS(solved_HS, a_grid_size, interpretation='ESC')
    diff = (m_cdc['tm_data']['TranMatrix'] - m_esc['tm_data']['TranMatrix']).toarray()
    max_diff = float(np.max(np.abs(diff)))
    assert max_diff > 1e-6, (
        f"At Splurge={solved_HS.Splurge:.4f}, CDC and ESC TMs must differ. "
        f"max diff = {max_diff}. Interpretation parameter not flowing to kernel."
    )

    # Per cheat-sheet 33.6: A_nrm_ESC < A_nrm_CDC (ESC applies (1-ς) factor)
    assert m_esc['A_nrm'] < m_cdc['A_nrm'], (
        f"ESC A_nrm should be < CDC A_nrm. Got CDC={m_cdc['A_nrm']:.4f}, "
        f"ESC={m_esc['A_nrm']:.4f}."
    )

    # Splurge=0 sanity: at ς=0, CDC and ESC are analytically equivalent
    original = solved_HS.Splurge
    solved_HS.Splurge = 0.0
    try:
        m_cdc0 = _compute_tm_moment_HS(solved_HS, a_grid_size, interpretation='CDC')
        m_esc0 = _compute_tm_moment_HS(solved_HS, a_grid_size, interpretation='ESC')
        assert abs(m_cdc0['A_nrm'] - m_esc0['A_nrm']) < 1e-10, (
            f"At Splurge=0, CDC and ESC A_nrm should match: "
            f"CDC={m_cdc0['A_nrm']}, ESC={m_esc0['A_nrm']}"
        )
    finally:
        solved_HS.Splurge = original


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
