"""
Progressive validation of DualAggFiscalType in HAFiscal.

Structured as phases, each building on the previous:

  Phase 0 — Smoke test: can we create, solve, simulate?
  Phase 1 — P-track fidelity: dual P == standard AggFiscalType
  Phase 2 — Q-measure properties: pLvl divergence, variance reduction
  Phase 3 — Statistical identities: Harmenberg factorization, cNrm consistency
  Phase 4 — Multi-type economy: 3 education groups, multiple discount factors
  Phase 5 — Aggregate-Q pipeline: aggregate_Q matches P-level aggregates
  Phase 6 — Markov state sharing under employment transitions
  Phase 7 — Splurge-specific validation

Run all:   pytest test_dual_measure_phases.py -v
Run fast:  pytest test_dual_measure_phases.py -v -k "Phase0 or Phase1"
"""

import sys
import numpy as np
import pytest
from copy import deepcopy

sys.argv = ["test", "1.03", "2", "0.3"]

from AggFiscalModel import (
    DualAggFiscalType, AggFiscalType, AggregateDemandEconomy,
)
from Parameters import return_parameters
from HARK.distributions import DiscreteDistribution
from HARK.dual_measure import compute_mean_pLvl, compute_pLvl_factor


# =====================================================================
# Shared fixtures
# =====================================================================

_PARAMS_CACHE = {}

def _get_params():
    if "main" not in _PARAMS_CACHE:
        _PARAMS_CACHE["main"] = return_parameters(OutputFor="_Main.py")
    return _PARAMS_CACHE["main"]


def _make_inc_dstns(agent, UBspell_normal):
    """Build the Markov income distributions for baseline.

    Encoding-agnostic: 4 entries under legacy, 6 under the canonical bug_fix
    encoding (BUG-043) — derived from the agent's base MrkvArray width.
    """
    unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnemp])],
    )
    unemp_no = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnempNoBenefits])],
    )
    n_micro = agent.MrkvArray[0].shape[0]
    return [[agent.IncShkDstn[0]] + [unemp] * UBspell_normal
            + [unemp_no] * (n_micro - 1 - UBspell_normal)]


def _make_single_agent(cls, N=500, seed=0, educ=0):
    """Create one solved agent of the given class (dropout by default)."""
    params = _get_params()
    inits = [params[0], params[1], params[2]]  # dropout, hs, college
    init_ADEconomy = params[3]
    DiscFacDstns = params[4]
    UBspell_normal = params[10]

    agent = cls(**inits[educ])
    agent.cycles = 0
    agent.AgentCount = N
    agent.seed = seed
    agent.DiscFac = DiscFacDstns[educ].atoms[0][3]

    econ = AggregateDemandEconomy(**init_ADEconomy)
    agent.get_economy_data(econ)
    agent.IncShkDstn = _make_inc_dstns(agent, UBspell_normal)

    econ.agents = [agent]
    econ.solve()
    return agent, econ


def _simulate_baseline(agent, T_sim=80, track_extra=None):
    """Run a baseline (no-shock) simulation."""
    tvars = ["cNrm", "pLvl", "aNrm", "cLvl_splurge", "cLvl", "Mrkv"]
    if track_extra:
        tvars = list(set(tvars + track_extra))
    agent.T_sim = T_sim
    agent.track_vars = tvars
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.EconomyMrkvNow = 0
    agent.simulate()
    return agent


# =====================================================================
# Phase 0 — Smoke test
# =====================================================================
class TestPhase0_Smoke:
    """Absolute minimum: create, solve, simulate, get output."""

    def test_create_and_solve(self):
        agent, _ = _make_single_agent(DualAggFiscalType, N=50)
        assert hasattr(agent, "solution")
        assert len(agent.solution) > 0

    def test_setup_q_measure(self):
        agent, _ = _make_single_agent(DualAggFiscalType, N=50)
        agent.setup_Q_measure()
        assert agent.dual_measure is True
        assert hasattr(agent, "IncShkDstn_Q")
        assert len(agent.IncShkDstn_Q) == len(agent.IncShkDstn)

    def test_simulate_10_periods(self):
        agent, _ = _make_single_agent(DualAggFiscalType, N=50)
        agent.setup_Q_measure()
        _simulate_baseline(agent, T_sim=10)
        assert "cNrm" in agent.history
        assert "cNrm" in agent.history_Q
        assert agent.history["cNrm"].shape == (10, 50)
        assert agent.history_Q["cNrm"].shape == (10, 50)

    def test_no_nan_after_burn(self):
        agent, _ = _make_single_agent(DualAggFiscalType, N=100)
        agent.setup_Q_measure()
        _simulate_baseline(agent, T_sim=20)
        for v in ("cNrm", "pLvl", "cLvl_splurge"):
            assert np.isnan(agent.history[v][5:]).sum() == 0, f"P[{v}] NaN"
            assert np.isnan(agent.history_Q[v][5:]).sum() == 0, f"Q[{v}] NaN"


# =====================================================================
# Phase 1 — P-track fidelity
# =====================================================================
class TestPhase1_PTrackFidelity:
    """Dual P-track must be bit-identical to standard AggFiscalType."""

    @pytest.fixture
    def paired_agents(self):
        std, _ = _make_single_agent(AggFiscalType, N=200, seed=42)
        _simulate_baseline(std, T_sim=40)

        dual, _ = _make_single_agent(DualAggFiscalType, N=200, seed=42)
        dual.setup_Q_measure()
        _simulate_baseline(dual, T_sim=40)
        return std, dual

    def test_cnrm_identical(self, paired_agents):
        std, dual = paired_agents
        np.testing.assert_allclose(
            std.history["cNrm"], dual.history["cNrm"], rtol=1e-12,
        )

    def test_plvl_identical(self, paired_agents):
        std, dual = paired_agents
        np.testing.assert_allclose(
            std.history["pLvl"], dual.history["pLvl"], rtol=1e-12,
        )

    def test_anrm_identical(self, paired_agents):
        std, dual = paired_agents
        np.testing.assert_allclose(
            std.history["aNrm"], dual.history["aNrm"], rtol=1e-12,
        )

    def test_splurge_identical(self, paired_agents):
        std, dual = paired_agents
        np.testing.assert_allclose(
            std.history["cLvl_splurge"], dual.history["cLvl_splurge"],
            rtol=1e-12,
        )


# =====================================================================
# Phase 2 — Q-measure properties
# =====================================================================
class TestPhase2_QProperties:
    """Basic properties that must hold for any correct Q-implementation."""

    @pytest.fixture(scope="class")
    def agent(self):
        a, _ = _make_single_agent(DualAggFiscalType, N=2000, seed=7)
        a.setup_Q_measure()
        _simulate_baseline(a, T_sim=150)
        return a

    def test_q_plvl_exceeds_p(self, agent):
        burn = 30
        P = np.nanmean(agent.history["pLvl"][burn:])
        Q = np.nanmean(agent.history_Q["pLvl"][burn:])
        assert Q > P, f"Q-pLvl ({Q:.3f}) should exceed P-pLvl ({P:.3f})"

    def test_q_plvl_ratio_grows(self, agent):
        """Q/P pLvl ratio should increase over time (Harmenberg reweighting)."""
        burn = 10
        ratio = (np.nanmean(agent.history_Q["pLvl"][burn:], axis=1)
                 / np.nanmean(agent.history["pLvl"][burn:], axis=1))
        # Fit a line; slope must be positive
        t = np.arange(len(ratio))
        slope = np.polyfit(t, ratio, 1)[0]
        assert slope > 0, f"Q/P pLvl ratio slope = {slope:.6f}; expected > 0"

    def test_variance_reduction_cnrm(self, agent):
        """Detrended Q-aggregate cNrm has lower CV than P-level aggregate."""
        burn = 30
        from numpy.polynomial.polynomial import polyfit, polyval

        cNrm_P = agent.history["cNrm"][burn:]
        pLvl_P = agent.history["pLvl"][burn:]
        cNrm_Q = agent.history_Q["cNrm"][burn:]

        C_P = np.nanmean(cNrm_P * pLvl_P, axis=1)
        C_Q = np.nanmean(cNrm_Q, axis=1)

        t = np.arange(len(C_P), dtype=float)
        P_cv = np.std(C_P / polyval(t, polyfit(t, C_P, 1)))
        Q_cv = np.std(C_Q / polyval(t, polyfit(t, C_Q, 1)))
        assert Q_cv < P_cv, f"Q CV ({Q_cv:.6f}) should < P CV ({P_cv:.6f})"

    def test_mrkv_shared(self, agent):
        burn = 5
        P = agent.history["Mrkv"][burn:]
        Q = agent.history_Q["Mrkv"][burn:]
        valid = ~(np.isnan(P) | np.isnan(Q))
        np.testing.assert_array_equal(P[valid], Q[valid])


# =====================================================================
# Phase 3 — Statistical identities
# =====================================================================
class TestPhase3_Statistics:
    """Harmenberg factorization and P-Q consistency."""

    @pytest.fixture(scope="class")
    def agent(self):
        a, _ = _make_single_agent(DualAggFiscalType, N=5000, seed=42)
        a.setup_Q_measure()
        _simulate_baseline(a, T_sim=120)
        return a

    def test_harmenberg_identity(self, agent):
        """E_P[c*p] ≈ E_Q[c] * E_P[p]  (ratio close to 1)."""
        burn = 30
        cNrm_P = agent.history["cNrm"][burn:]
        pLvl_P = agent.history["pLvl"][burn:]
        cNrm_Q = agent.history_Q["cNrm"][burn:]

        LHS = np.nanmean(cNrm_P * pLvl_P, axis=1)
        RHS = np.nanmean(cNrm_Q, axis=1) * np.nanmean(pLvl_P, axis=1)
        ratio = np.mean(LHS / RHS)
        assert 0.95 < ratio < 1.05, f"Harmenberg ratio = {ratio:.4f}"

    def test_cnrm_p_q_within_2se(self, agent):
        """cNrm means agree period-by-period within 2 SE in >= 85% periods."""
        burn = 30
        N = agent.AgentCount
        cNrm_P = agent.history["cNrm"][burn:]
        cNrm_Q = agent.history_Q["cNrm"][burn:]
        T = cNrm_P.shape[0]

        ok = 0
        for t in range(T):
            se = np.nanstd(cNrm_P[t]) / np.sqrt(N)
            if se > 0 and abs(np.nanmean(cNrm_P[t]) - np.nanmean(cNrm_Q[t])) / se < 2:
                ok += 1
        frac = ok / T
        assert frac >= 0.85, f"|cNrm P-Q| < 2 SE in only {frac:.0%} periods"

    def test_se_halves_when_n_quadruples(self):
        """Cross-sectional SE scales as 1/sqrt(N)."""
        Ns, Nl = 1000, 4000
        burn = 20

        a_s, _ = _make_single_agent(DualAggFiscalType, N=Ns, seed=10)
        a_s.setup_Q_measure()
        _simulate_baseline(a_s, T_sim=60)

        a_l, _ = _make_single_agent(DualAggFiscalType, N=Nl, seed=10)
        a_l.setup_Q_measure()
        _simulate_baseline(a_l, T_sim=60)

        for label, hist_key in [("P", "history"), ("Q", "history_Q")]:
            se_s = np.mean(np.nanstd(getattr(a_s, hist_key)["cNrm"][burn:], axis=1)) / np.sqrt(Ns)
            se_l = np.mean(np.nanstd(getattr(a_l, hist_key)["cNrm"][burn:], axis=1)) / np.sqrt(Nl)
            r = se_l / se_s
            assert 0.3 < r < 0.7, f"{label} SE ratio = {r:.3f}; expected ~0.5"


# =====================================================================
# Phase 4 — Multi-type economy
# =====================================================================
class TestPhase4_MultiType:
    """Multiple education groups with different discount factors."""

    @pytest.fixture(scope="class")
    def agents(self):
        params = _get_params()
        inits = [params[0], params[1], params[2]]
        init_ADEconomy = params[3]
        DiscFacDstns = params[4]
        UBspell_normal = params[10]

        agent_list = []
        econ = AggregateDemandEconomy(**init_ADEconomy)
        for e in range(3):
            a = DualAggFiscalType(**inits[e])
            a.cycles = 0
            a.AgentCount = 500
            a.seed = e
            a.DiscFac = DiscFacDstns[e].atoms[0][3]
            a.get_economy_data(econ)
            a.IncShkDstn = _make_inc_dstns(a, UBspell_normal)
            agent_list.append(a)

        econ.agents = agent_list
        econ.solve()

        for a in agent_list:
            a.setup_Q_measure()
            _simulate_baseline(a, T_sim=80)

        return agent_list

    def test_all_types_have_q_history(self, agents):
        for i, a in enumerate(agents):
            assert "cNrm" in a.history_Q, f"Agent {i} missing Q history"
            burn = 10
            assert np.isnan(a.history_Q["cNrm"][burn:]).sum() == 0

    def test_harmenberg_identity_per_type(self, agents):
        burn = 20
        for i, a in enumerate(agents):
            cNrm_P = a.history["cNrm"][burn:]
            pLvl_P = a.history["pLvl"][burn:]
            cNrm_Q = a.history_Q["cNrm"][burn:]

            LHS = np.nanmean(cNrm_P * pLvl_P, axis=1)
            RHS = np.nanmean(cNrm_Q, axis=1) * np.nanmean(pLvl_P, axis=1)
            ratio = np.mean(LHS / RHS)
            assert 0.90 < ratio < 1.10, (
                f"Agent {i}: Harmenberg ratio = {ratio:.4f}"
            )

    def test_aggregate_consumption_positive(self, agents):
        burn = 20
        total_P = sum(
            np.nanmean(a.history["cLvl_splurge"][burn:], axis=1) * a.AgentCount
            for a in agents
        )
        total_Q = sum(
            np.nanmean(a.history_Q["cLvl_splurge"][burn:], axis=1) * a.AgentCount
            for a in agents
        )
        assert np.all(total_P > 0)
        assert np.all(total_Q > 0)


# =====================================================================
# Phase 5 — aggregate_Q pipeline
# =====================================================================
class TestPhase5_AggregateQ:
    """The aggregate_Q convenience method."""

    @pytest.fixture(scope="class")
    def agent(self):
        a, _ = _make_single_agent(DualAggFiscalType, N=3000, seed=42)
        a.setup_Q_measure()
        _simulate_baseline(a, T_sim=120)
        return a

    def test_aggregate_q_runs(self, agent):
        C_Q = agent.aggregate_Q("cNrm", burn=30)
        assert len(C_Q) == 90
        assert np.all(np.isfinite(C_Q))
        assert np.all(C_Q > 0)

    def test_aggregate_q_close_to_p(self, agent):
        burn = 30
        C_Q = agent.aggregate_Q("cNrm", burn=burn)
        cNrm_P = agent.history["cNrm"][burn:]
        pLvl_P = agent.history["pLvl"][burn:]
        C_P = agent.AgentCount * np.nanmean(cNrm_P * pLvl_P, axis=1)
        ratio = np.mean(C_Q) / np.mean(C_P)
        assert 0.90 < ratio < 1.10, f"C_Q/C_P = {ratio:.4f}"

    def test_aggregate_q_with_analytical_E_p(self, agent):
        burn = 30
        emp_E_p = np.nanmean(agent.history["pLvl"][burn:])
        C_Q_emp = agent.aggregate_Q("cNrm", burn=burn, E_pLvl=emp_E_p)
        C_Q_def = agent.aggregate_Q("cNrm", burn=burn)
        np.testing.assert_allclose(C_Q_emp, C_Q_def, rtol=0.01)


# =====================================================================
# Phase 6 — Markov state sharing under transitions
# =====================================================================
class TestPhase6_MarkovTransitions:
    """Verify employment/unemployment transitions are shared."""

    @pytest.fixture(scope="class")
    def agent(self):
        a, _ = _make_single_agent(DualAggFiscalType, N=2000, seed=99)
        a.setup_Q_measure()
        _simulate_baseline(a, T_sim=100)
        return a

    def test_mrkv_always_shared(self, agent):
        """Mrkv identical in every period (not just post-burn)."""
        for t in range(agent.T_sim):
            P = agent.history["Mrkv"][t]
            Q = agent.history_Q["Mrkv"][t]
            valid = ~(np.isnan(P) | np.isnan(Q))
            if valid.sum() > 0:
                np.testing.assert_array_equal(
                    P[valid], Q[valid],
                    err_msg=f"Mrkv mismatch at t={t}",
                )

    def test_unemployment_fraction_reasonable(self, agent):
        """Some agents should transition to unemployment (micro state > 0)."""
        burn = 10
        mrkv = agent.history["Mrkv"][burn:]
        valid = ~np.isnan(mrkv)
        micro = mrkv[valid].astype(int) % 4
        unemp_frac = np.mean(micro > 0)
        assert 0.01 < unemp_frac < 0.50, (
            f"Unemployment fraction = {unemp_frac:.3f}; expected 1-50%"
        )

    def test_q_cnrm_differs_for_employed(self, agent):
        """For employed agents (micro=0), Q-cNrm should differ from P-cNrm
        because the employed distribution has non-degenerate PermShk."""
        t = 50
        mrkv = agent.history["Mrkv"][t]
        employed = (~np.isnan(mrkv)) & (mrkv.astype(int) % 4 == 0)
        if employed.sum() < 10:
            pytest.skip("Too few employed agents")

        P_cnrm = agent.history["cNrm"][t][employed]
        Q_cnrm = agent.history_Q["cNrm"][t][employed]
        assert not np.allclose(P_cnrm, Q_cnrm, rtol=0.001), (
            "Employed Q-cNrm should differ from P-cNrm"
        )


# =====================================================================
# Phase 7 — Splurge-specific validation
# =====================================================================
class TestPhase7_Splurge:
    """Validate the splurge consumption formula in Q-track."""

    @pytest.fixture(scope="class")
    def agent(self):
        a, _ = _make_single_agent(DualAggFiscalType, N=1000, seed=0)
        a.setup_Q_measure()
        _simulate_baseline(a, T_sim=50)
        return a

    def test_splurge_bounded_below(self, agent):
        """cLvl_splurge >= (1-S)*cLvl  (the S term adds, never subtracts)."""
        S = agent.Splurge
        for t in range(10, 30):
            cLvl_Q = agent.history_Q["cNrm"][t] * agent.history_Q["pLvl"][t]
            splurge_Q = agent.history_Q["cLvl_splurge"][t]
            valid = ~np.isnan(splurge_Q)
            lb = (1.0 - S) * cLvl_Q[valid]
            assert np.all(splurge_Q[valid] >= lb - 1e-10), (
                f"t={t}: splurge_Q < (1-S)*cLvl_Q for some agents"
            )

    def test_splurge_exceeds_clvl(self, agent):
        """Due to the splurge term S*p*theta*ADF, cLvl_splurge should generally
        exceed cLvl = cNrm * pLvl."""
        t = 25
        cLvl_Q = agent.history_Q["cNrm"][t] * agent.history_Q["pLvl"][t]
        splurge_Q = agent.history_Q["cLvl_splurge"][t]
        valid = ~np.isnan(splurge_Q)
        assert not np.allclose(splurge_Q[valid], cLvl_Q[valid], rtol=0.01), (
            "cLvl_splurge_Q should differ from cLvl_Q"
        )

    def test_splurge_variance_reduction(self, agent):
        """Detrended Q-aggregate splurge (normalized) has lower CV than P-level."""
        burn = 15
        from numpy.polynomial.polynomial import polyfit, polyval

        # P: level aggregate of cLvl_splurge
        C_P = np.nanmean(agent.history["cLvl_splurge"][burn:], axis=1)
        # Q: normalized splurge = cLvl_splurge_Q / pLvl_Q
        splurge_nrm_Q = (agent.history_Q["cLvl_splurge"][burn:]
                         / agent.history_Q["pLvl"][burn:])
        C_Q = np.nanmean(splurge_nrm_Q, axis=1)

        t = np.arange(len(C_P), dtype=float)
        P_cv = np.std(C_P / polyval(t, polyfit(t, C_P, 1)))
        Q_cv = np.std(C_Q / polyval(t, polyfit(t, C_Q, 1)))
        assert Q_cv < P_cv, f"Q splurge CV ({Q_cv:.6f}) >= P ({P_cv:.6f})"
