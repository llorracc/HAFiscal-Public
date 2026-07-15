"""
Integration tests for DualAggFiscalType — the dual-measure (P/Q) variant
of HAFiscal's AggFiscalType.

Validates that the Harmenberg neutral measure works correctly within the
full HAFiscal simulation pipeline, including:
- AggDemandFac in the budget constraint
- Sticky expectations (MrkvNowPcvd)
- 2-argument cFunc(mNrm, Cratio)
- Splurge consumption (cLvl_splurge)
- Shared Markov states between P and Q tracks
- Variance reduction in Q-aggregate consumption
- P-Q statistical consistency (Harmenberg identity)
"""

import sys
import os
import numpy as np
import pytest
from copy import deepcopy

sys.argv = ["test", "1.03", "2", "0.3"]

from AggFiscalModel import DualAggFiscalType, AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from HARK.distributions import DiscreteDistribution


def _setup_hafiscal_agent(N=500, seed=0):
    """Create a solved DualAggFiscalType agent with HAFiscal parameters.

    Returns (agent, UBspell_normal) tuple ready for simulation.
    """
    [init_dropout, init_highschool, init_college, init_ADEconomy,
     DiscFacDstns, DiscFacCount, AgentCountTotal, base_dict,
     num_max_iterations_solvingAD, convergence_tol_solvingAD,
     UBspell_normal, num_base_MrkvStates, data_EducShares,
     max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        OutputFor="_Main.py"
    )

    agent = DualAggFiscalType(**init_dropout)
    agent.cycles = 0
    agent.AgentCount = N
    agent.seed = seed
    agent.DiscFac = DiscFacDstns[0].atoms[0][3]

    econ = AggregateDemandEconomy(**init_ADEconomy)
    agent.get_economy_data(econ)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnemp])],
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnempNoBenefits])],
    )
    # Encoding-agnostic (4 legacy / 6 bug_fix micro states; BUG-043).
    agent.IncShkDstn = [
        [agent.IncShkDstn[0]]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
        * (num_base_MrkvStates - 1 - UBspell_normal)
    ]

    econ.agents = [agent]
    econ.solve()

    agent.setup_Q_measure()
    return agent, UBspell_normal


def _run_hafiscal_dual(N=500, seed=0, T_sim=100):
    """Run a dual-measure HAFiscal simulation and return the agent."""
    agent, _ = _setup_hafiscal_agent(N=N, seed=seed)
    agent.T_sim = T_sim
    agent.track_vars = [
        "cNrm", "pLvl", "aNrm", "cLvl_splurge", "cLvl", "Mrkv",
    ]
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.EconomyMrkvNow = 0
    agent.simulate()
    return agent


# -----------------------------------------------------------------
# Test 1: Basic plumbing — histories are populated, no NaNs
# -----------------------------------------------------------------
class TestDualAggFiscalPlumbing:
    def test_histories_populated(self):
        agent = _run_hafiscal_dual(N=200, T_sim=30)
        burn = 5
        for v in ["cNrm", "pLvl", "cLvl_splurge"]:
            P = agent.history[v][burn:]
            Q = agent.history_Q[v][burn:]
            assert np.isnan(P).sum() == 0, f"P-history[{v}] has NaNs"
            assert np.isnan(Q).sum() == 0, f"Q-history[{v}] has NaNs"
            assert P.shape == Q.shape

    def test_mrkv_shared(self):
        """Mrkv states are identical between P and Q tracks."""
        agent = _run_hafiscal_dual(N=200, T_sim=30)
        burn = 5
        P_mrkv = agent.history["Mrkv"][burn:]
        Q_mrkv = agent.history_Q["Mrkv"][burn:]
        valid = ~(np.isnan(P_mrkv) | np.isnan(Q_mrkv))
        np.testing.assert_array_equal(
            P_mrkv[valid], Q_mrkv[valid],
            err_msg="Mrkv should be identical in P and Q tracks",
        )


# -----------------------------------------------------------------
# Test 2: Q-pLvl diverges from P (Harmenberg reweighting)
# -----------------------------------------------------------------
class TestQPLvlDiverges:
    def test_q_plvl_larger(self):
        agent = _run_hafiscal_dual(N=1000, T_sim=100)
        burn = 20
        P_mean = np.nanmean(agent.history["pLvl"][burn:])
        Q_mean = np.nanmean(agent.history_Q["pLvl"][burn:])
        assert Q_mean > P_mean, (
            f"Q-pLvl ({Q_mean:.4f}) should exceed P-pLvl ({P_mean:.4f})"
        )


# -----------------------------------------------------------------
# Test 3: Variance reduction in Q-aggregate consumption (cNrm)
# -----------------------------------------------------------------
class TestCNrmVarianceReduction:
    def test_q_cnrm_less_noisy(self):
        """Detrended Q-aggregate cNrm should have lower CV than P-level agg."""
        agent = _run_hafiscal_dual(N=3000, seed=42, T_sim=200)
        burn = 30

        cNrm_P = agent.history["cNrm"][burn:]
        pLvl_P = agent.history["pLvl"][burn:]
        cNrm_Q = agent.history_Q["cNrm"][burn:]

        # P-aggregate at consumption level: sum(cNrm_P * pLvl_P)
        C_P = np.nanmean(cNrm_P * pLvl_P, axis=1)
        # Q-aggregate: mean(cNrm_Q)  (Harmenberg-normalized)
        C_Q = np.nanmean(cNrm_Q, axis=1)

        from numpy.polynomial.polynomial import polyfit, polyval

        t = np.arange(len(C_P), dtype=float)
        P_trend = polyval(t, polyfit(t, C_P, 1))
        Q_trend = polyval(t, polyfit(t, C_Q, 1))
        P_cv = np.std(C_P / P_trend)
        Q_cv = np.std(C_Q / Q_trend)

        assert Q_cv < P_cv, (
            f"Q detrended CV ({Q_cv:.6f}) should be less than "
            f"P detrended CV ({P_cv:.6f})"
        )


# -----------------------------------------------------------------
# Test 4: Cross-sectional SE halves when N quadruples
# -----------------------------------------------------------------
class TestHAFiscalSEConvergence:
    def test_cross_sectional_se_halves(self):
        N_small = 1000
        N_large = 4 * N_small
        burn = 20

        agent_s = _run_hafiscal_dual(N=N_small, seed=10, T_sim=80)
        agent_l = _run_hafiscal_dual(N=N_large, seed=10, T_sim=80)

        # Use cNrm (normalized) for SE convergence
        P_s = agent_s.history["cNrm"][burn:]
        P_l = agent_l.history["cNrm"][burn:]
        Q_s = agent_s.history_Q["cNrm"][burn:]
        Q_l = agent_l.history_Q["cNrm"][burn:]

        se_P_s = np.mean(np.nanstd(P_s, axis=1)) / np.sqrt(N_small)
        se_P_l = np.mean(np.nanstd(P_l, axis=1)) / np.sqrt(N_large)
        se_Q_s = np.mean(np.nanstd(Q_s, axis=1)) / np.sqrt(N_small)
        se_Q_l = np.mean(np.nanstd(Q_l, axis=1)) / np.sqrt(N_large)

        ratio_P = se_P_l / se_P_s
        ratio_Q = se_Q_l / se_Q_s

        assert 0.3 < ratio_P < 0.7, (
            f"P cross-sectional SE ratio = {ratio_P:.3f}; expected ~0.5"
        )
        assert 0.3 < ratio_Q < 0.7, (
            f"Q cross-sectional SE ratio = {ratio_Q:.3f}; expected ~0.5"
        )


# -----------------------------------------------------------------
# Test 5: P and Q period-by-period agreement (cNrm within 2 SE)
# -----------------------------------------------------------------
class TestPQConsistency:
    def test_cnrm_within_2se(self):
        """cNrm should agree period-by-period between P and Q within
        2 cross-sectional SEs in >= 85% of periods."""
        N = 5000
        agent = _run_hafiscal_dual(N=N, seed=42, T_sim=100)
        burn = 20

        cNrm_P = agent.history["cNrm"][burn:]
        cNrm_Q = agent.history_Q["cNrm"][burn:]
        T = cNrm_P.shape[0]

        within_2se = 0
        for t in range(T):
            mean_P = np.nanmean(cNrm_P[t])
            mean_Q = np.nanmean(cNrm_Q[t])
            se_P = np.nanstd(cNrm_P[t]) / np.sqrt(N)
            if se_P > 0 and abs(mean_P - mean_Q) / se_P < 2.0:
                within_2se += 1

        frac = within_2se / T
        assert frac >= 0.85, (
            f"Only {frac:.1%} of periods have |cNrm_P-cNrm_Q| < 2*SE_P. "
            f"Expected >= 85%."
        )


# -----------------------------------------------------------------
# Test 6: Harmenberg identity: E_P[c*p] ≈ E_Q[c] * E_P[p]
# -----------------------------------------------------------------
class TestHarmenbergIdentity:
    def test_factorization_holds(self):
        """The Harmenberg factorization should hold approximately:
        E_P[cNrm * pLvl] ≈ E_Q[cNrm] * E_P[pLvl]."""
        N = 5000
        agent = _run_hafiscal_dual(N=N, seed=42, T_sim=100)
        burn = 20

        cNrm_P = agent.history["cNrm"][burn:]
        pLvl_P = agent.history["pLvl"][burn:]
        cNrm_Q = agent.history_Q["cNrm"][burn:]

        LHS = np.nanmean(cNrm_P * pLvl_P, axis=1)
        E_Q_c = np.nanmean(cNrm_Q, axis=1)
        E_P_p = np.nanmean(pLvl_P, axis=1)
        RHS = E_Q_c * E_P_p

        ratio = LHS / RHS
        mean_ratio = np.mean(ratio)
        assert 0.95 < mean_ratio < 1.05, (
            f"Harmenberg identity ratio = {mean_ratio:.4f}; "
            f"expected close to 1.0"
        )


# -----------------------------------------------------------------
# Test 7: Splurge formula correctness
# -----------------------------------------------------------------
class TestSplurgeFormula:
    """Verify cLvl_splurge_Q uses the correct formula with Q-states."""

    def test_splurge_decomposition(self):
        agent = _run_hafiscal_dual(N=500, seed=0, T_sim=20)
        S = agent.Splurge
        t = 10

        cNrm_Q = agent.history_Q["cNrm"][t]
        pLvl_Q = agent.history_Q["pLvl"][t]
        splurge_Q = agent.history_Q["cLvl_splurge"][t]

        # cLvl_splurge = (1-S)*cNrm*pLvl + S*pLvl*TranShk*ADF
        # Since ADF=1 and TranShk>=0, splurge >= (1-S)*cNrm*pLvl
        cLvl_Q = cNrm_Q * pLvl_Q
        lower_bound = (1.0 - S) * cLvl_Q
        valid = ~np.isnan(splurge_Q)
        assert np.all(splurge_Q[valid] >= lower_bound[valid] - 1e-10), (
            "cLvl_splurge_Q should be >= (1-S)*cLvl_Q"
        )

        assert not np.allclose(
            splurge_Q[valid], cLvl_Q[valid], rtol=0.01
        ), "cLvl_splurge_Q should differ from cLvl_Q due to splurge term"


# -----------------------------------------------------------------
# Test 8: P-history matches standard (non-dual) AggFiscalType
# -----------------------------------------------------------------
class TestPHistoryMatchesStandard:
    """The dual-measure P-track should produce identical results to a
    standard AggFiscalType simulation with the same seed."""

    def test_p_matches_standard(self):
        params = return_parameters(OutputFor="_Main.py")
        init_dropout = params[0]
        DiscFacDstns = params[4]
        init_ADEconomy = params[3]
        UBspell_normal = params[10]
        num_base_MrkvStates = params[11]

        IncShkDstn_unemp = DiscreteDistribution(
            np.array([1.0]),
            [np.array([1.0]), np.array([0.7])],
        )
        IncShkDstn_unemp_nobenefits = DiscreteDistribution(
            np.array([1.0]),
            [np.array([1.0]), np.array([0.5])],
        )

        def _make_agent(cls, seed):
            a = cls(**init_dropout)
            a.cycles = 0
            a.AgentCount = 300
            a.seed = seed
            a.DiscFac = DiscFacDstns[0].atoms[0][3]
            e = AggregateDemandEconomy(**init_ADEconomy)
            a.get_economy_data(e)
            a.IncShkDstn = [
                [a.IncShkDstn[0]]
                + [IncShkDstn_unemp] * UBspell_normal
                + [IncShkDstn_unemp_nobenefits]
                * (num_base_MrkvStates - 1 - UBspell_normal)
            ]
            e.agents = [a]
            e.solve()
            return a

        std_agent = _make_agent(AggFiscalType, seed=77)
        std_agent.T_sim = 40
        std_agent.track_vars = ["cNrm", "pLvl", "aNrm", "cLvl_splurge"]
        std_agent.initialize_sim()
        std_agent.AggDemandFac = 1.0
        std_agent.RfreeNow = 1.0
        std_agent.CaggNow = 1.0
        std_agent.Cratio = 1.0
        std_agent.EconomyMrkvNow = 0
        std_agent.simulate()

        dual_agent = _make_agent(DualAggFiscalType, seed=77)
        dual_agent.setup_Q_measure()
        dual_agent.T_sim = 40
        dual_agent.track_vars = ["cNrm", "pLvl", "aNrm", "cLvl_splurge"]
        dual_agent.initialize_sim()
        dual_agent.AggDemandFac = 1.0
        dual_agent.RfreeNow = 1.0
        dual_agent.CaggNow = 1.0
        dual_agent.Cratio = 1.0
        dual_agent.EconomyMrkvNow = 0
        dual_agent.simulate()

        for v in ["cNrm", "pLvl", "aNrm", "cLvl_splurge"]:
            np.testing.assert_allclose(
                std_agent.history[v],
                dual_agent.history[v],
                rtol=1e-12,
                err_msg=f"P-history[{v}] differs from standard AggFiscalType",
            )
