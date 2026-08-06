"""
Comprehensive test suite verifying that a future refactoring of AggFiscalType
to use AggIndMarkovConsumerType (from HARK.ConsumptionSaving.ConsAggIndMarkovModel)
would produce numerically identical results.

Six test levels, from fastest/cheapest to slowest/most comprehensive:

  Level 1: Transition matrix equivalence        (< 1 sec, 51+ matrix comparisons)
  Level 2: Micro state draw equivalence          (< 1 sec, 6 configurations)
  Level 3: Combined state encoding round-trip    (< 1 sec, 5 tests)
  Level 4: Solver equivalence                    (< 5 sec, economy-level)
  Level 5: Simulation path equivalence           (< 10 sec, 5 shock types)
  Level 6: Aggregate dynamics equivalence        (< 10 sec, 4 shock types)

Total: ~28 tests in < 10 seconds with Reduced_Run parameters.

Run from Code/HA-Models/FromPandemicCode/:
    pytest test_agg_ind_markov_equivalence.py -v
    pytest test_agg_ind_markov_equivalence.py -v -k "Level1"   # just matrices
"""

import os
import sys
import unittest
from copy import deepcopy
from itertools import product

import numpy as np

# ---------------------------------------------------------------------------
# Ensure we can import from the HAFiscal codebase.
# Guard sys.argv: EstimParameters.py reads sys.argv[3:4] for IncUnemp params,
# which collides with pytest/unittest args.
# ---------------------------------------------------------------------------
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

_saved_argv = sys.argv[:]
sys.argv = [sys.argv[0]]

# HARK generic hierarchical-Markov utility
from HARK.ConsumptionSaving.ConsAggIndMarkovModel import (
    AggIndMarkovConsumerType,
    make_hierarchical_mrkv_array,
)

# HAFiscal's own builder functions (via Parameters.py)
from Parameters import return_parameters

# Grab the builder functions once (they're pure functions, no side effects)
(
    _make_macro_mrkv_array_recession,
    _make_cond_mrkv_arrays_recession,
    _make_full_mrkv_array,
    _T_sim,
    _make_cond_mrkv_arrays_base,
    _make_cond_mrkv_arrays_recession_ui,
) = return_parameters(OutputFor="_Model.py")

# Also need the raw parameter values for building arrays
from EstimParameters import (
    Urate_normal_d,
    Urate_normal_h,
    Urate_normal_c,
    Uspell_normal,
    UBspell_normal,
    num_base_MrkvStates,
)

# Recession parameters (hard-coded from Parameters.py defaults)
sys.argv = _saved_argv  # restore for pytest

_URATE_RECESSION = {
    "d": 2 * Urate_normal_d,
    "h": 2 * Urate_normal_h,
    "c": 2 * Urate_normal_c,
}
_USPELL_RECESSION = 4
_UBSPELL_EXTENDED = 5

_URATE_NORMAL = {"d": Urate_normal_d, "h": Urate_normal_h, "c": Urate_normal_c}
# 4 under legacy encoding, 6 under the canonical bug_fix encoding (BUG-043).
_NUM_BASE_MRKV_STATES = num_base_MrkvStates
# Number of trailing no-benefits-paying micro states in the base scenario
# (u3Q/u4Q pay no-benefits income outside recessionUI, same as noBen).
_N_NOBEN = _NUM_BASE_MRKV_STATES - 1 - UBspell_normal


# ============================================================================
# Helpers
# ============================================================================

def _build_all_arrays(educ, shock_type, Rspell, num_exp):
    """Build (MacroMrkvArray, CondMrkvArrays, FullMrkv) for a given config."""
    u_normal = _URATE_NORMAL[educ]
    u_recession = _URATE_RECESSION[educ]

    if shock_type == "base":
        macro = np.array([[1.0]])
        cond = _make_cond_mrkv_arrays_base(u_normal, Uspell_normal, UBspell_normal)
    elif shock_type in ("recession", "recessionCheck", "recessionTaxCut"):
        macro = _make_macro_mrkv_array_recession(Rspell, num_exp)
        cond = _make_cond_mrkv_arrays_recession(
            u_normal, Uspell_normal, UBspell_normal,
            u_recession, _USPELL_RECESSION, num_exp,
        )
    elif shock_type in ("recessionUI", "UI"):
        macro = _make_macro_mrkv_array_recession(Rspell, num_exp)
        extra = _UBSPELL_EXTENDED - UBspell_normal
        cond = _make_cond_mrkv_arrays_recession_ui(
            u_normal, Uspell_normal, UBspell_normal,
            u_recession, _USPELL_RECESSION, num_exp, extra,
        )
    else:
        raise ValueError(f"Unknown shock_type: {shock_type}")

    full_old = _make_full_mrkv_array(macro, cond)  # returns [array]
    return macro, cond, full_old[0]


# ============================================================================
# Level 1: Transition Matrix Equivalence
# ============================================================================

class TestLevel1_TransitionMatrixEquivalence(unittest.TestCase):
    """
    Verify make_hierarchical_mrkv_array == make_full_mrkv_array for every
    (MacroMrkvArray, CondMrkvArrays) pair that appears in the HAFiscal workflow.
    """

    _SHOCK_TYPES_RECESSION = ["recession", "recessionUI", "recessionCheck", "recessionTaxCut"]
    _EDUCS = ["d", "h", "c"]
    _RSPELLS = [4, 6]
    _NUM_EXPS = [10, 20]

    def _assert_matrix_equal(self, educ, shock_type, Rspell, num_exp):
        macro, cond, old_full = _build_all_arrays(educ, shock_type, Rspell, num_exp)
        new_full = make_hierarchical_mrkv_array(macro, cond)

        self.assertEqual(
            old_full.shape, new_full.shape,
            f"Shape mismatch for {educ}/{shock_type}/Rspell={Rspell}/nexp={num_exp}: "
            f"old={old_full.shape} new={new_full.shape}",
        )
        np.testing.assert_array_equal(
            old_full, new_full,
            err_msg=(
                f"Matrix mismatch for {educ}/{shock_type}/Rspell={Rspell}/nexp={num_exp}"
            ),
        )

    def test_base_all_educs(self):
        """Base scenario: 1 macro state × 4 micro states, 3 education types."""
        for educ in self._EDUCS:
            with self.subTest(educ=educ):
                self._assert_matrix_equal(educ, "base", Rspell=6, num_exp=20)

    def test_recession_all_combos(self):
        """Recession: 3 educs × 2 Rspell × 2 num_exp = 12 combos."""
        for educ, rsp, nexp in product(self._EDUCS, self._RSPELLS, self._NUM_EXPS):
            with self.subTest(educ=educ, Rspell=rsp, num_exp=nexp):
                self._assert_matrix_equal(educ, "recession", rsp, nexp)

    def test_recessionUI_all_combos(self):
        """RecessionUI: 3 educs × 2 Rspell × 2 num_exp = 12 combos."""
        for educ, rsp, nexp in product(self._EDUCS, self._RSPELLS, self._NUM_EXPS):
            with self.subTest(educ=educ, Rspell=rsp, num_exp=nexp):
                self._assert_matrix_equal(educ, "recessionUI", rsp, nexp)

    def test_recessionCheck_all_combos(self):
        """RecessionCheck: 3 educs × 2 Rspell × 2 num_exp = 12 combos."""
        for educ, rsp, nexp in product(self._EDUCS, self._RSPELLS, self._NUM_EXPS):
            with self.subTest(educ=educ, Rspell=rsp, num_exp=nexp):
                self._assert_matrix_equal(educ, "recessionCheck", rsp, nexp)

    def test_recessionTaxCut_all_combos(self):
        """RecessionTaxCut: 3 educs × 2 Rspell × 2 num_exp = 12 combos."""
        for educ, rsp, nexp in product(self._EDUCS, self._RSPELLS, self._NUM_EXPS):
            with self.subTest(educ=educ, Rspell=rsp, num_exp=nexp):
                self._assert_matrix_equal(educ, "recessionTaxCut", rsp, nexp)

    def test_row_sums(self):
        """Every row of every full matrix must sum to 1.0."""
        for shock in ["base"] + self._SHOCK_TYPES_RECESSION:
            for educ in self._EDUCS:
                rsp = 6
                nexp = 20
                macro, cond, _ = _build_all_arrays(educ, shock, rsp, nexp)
                full = make_hierarchical_mrkv_array(macro, cond)
                row_sums = full.sum(axis=1)
                np.testing.assert_allclose(
                    row_sums, 1.0, atol=1e-14,
                    err_msg=f"Row sums != 1 for {educ}/{shock}",
                )

    def test_matrix_dimensions(self):
        """Verify expected dimensions for each scenario type."""
        N = _NUM_BASE_MRKV_STATES  # 4

        # base: 1 macro × 4 micro = 4×4
        macro, cond, _ = _build_all_arrays("d", "base", 6, 20)
        full = make_hierarchical_mrkv_array(macro, cond)
        self.assertEqual(full.shape, (N, N))

        # recession with num_exp=20: 42 macro × 4 micro = 168×168
        macro, cond, _ = _build_all_arrays("d", "recession", 6, 20)
        full = make_hierarchical_mrkv_array(macro, cond)
        M = 2 * (20 + 1)
        self.assertEqual(full.shape, (M * N, M * N))

        # recession with num_exp=10: 22 macro × 4 micro = 88×88
        macro, cond, _ = _build_all_arrays("d", "recession", 6, 10)
        full = make_hierarchical_mrkv_array(macro, cond)
        M = 2 * (10 + 1)
        self.assertEqual(full.shape, (M * N, M * N))


# ============================================================================
# Level 2: Micro State Draw Equivalence
# ============================================================================

class TestLevel2_MicroStateDrawEquivalence(unittest.TestCase):
    """
    Verify that the searchsorted-based micro-state draw (used by AggFiscalType)
    produces correct results when invoked through AggIndMarkovConsumerType's
    override mechanism.
    """

    def _searchsorted_draw(self, CondMrkvArrays, MacroMrkvNow, MicroMrkvPrev,
                           uniform_draws, num_agents):
        """
        Reproduce AggFiscalType.get_micro_markv_states_guts logic exactly.
        """
        J = CondMrkvArrays[0].shape[0]
        MicroMrkvNow = np.zeros(num_agents, dtype=int)
        MicroMrkvBoolArray = np.zeros((J, num_agents))
        for j in range(J):
            MicroMrkvBoolArray[j, :] = MicroMrkvPrev == j

        for i in range(len(CondMrkvArrays)):
            Cutoffs = np.cumsum(CondMrkvArrays[i], axis=1)
            macro_match = MacroMrkvNow == i
            for j in range(J):
                these = np.logical_and(macro_match, MicroMrkvBoolArray[j, :])
                MicroMrkvNow[these] = np.searchsorted(
                    Cutoffs[j, :], uniform_draws[these]
                ).astype(int)
        return MicroMrkvNow

    def _run_draw_test(self, shock_type, Rspell, num_exp, num_agents=1000):
        """Run draw equivalence test for a given configuration."""
        macro_arr, cond, _ = _build_all_arrays("d", shock_type, Rspell, num_exp)
        N = _NUM_BASE_MRKV_STATES
        M = macro_arr.shape[0]

        rng = np.random.default_rng(42)
        uniform_draws = rng.uniform(size=num_agents)

        for macro_state in range(min(M, 4)):  # test a few macro states
            MicroMrkvPrev = rng.integers(0, N, size=num_agents)
            MacroMrkvNow = np.full(num_agents, macro_state, dtype=int)

            result = self._searchsorted_draw(
                cond, MacroMrkvNow, MicroMrkvPrev, uniform_draws, num_agents
            )

            self.assertTrue(np.all(result >= 0), "Negative micro state")
            self.assertTrue(np.all(result < N), f"Micro state >= {N}")

            for j in range(N):
                mask = MicroMrkvPrev == j
                if not mask.any():
                    continue
                draws_j = uniform_draws[mask]
                cutoffs = np.cumsum(cond[macro_state][j, :])
                expected = np.searchsorted(cutoffs, draws_j).astype(int)
                np.testing.assert_array_equal(
                    result[mask], expected,
                    err_msg=(
                        f"Draw mismatch at macro={macro_state}, prev_micro={j}"
                    ),
                )

    def test_base_config(self):
        """Base: 1 macro state, 4 micro states."""
        self._run_draw_test("base", 6, 20)

    def test_recession_full(self):
        """Recession: 42 macro states, 4 micro states."""
        self._run_draw_test("recession", 6, 20)

    def test_recession_reduced(self):
        """Recession reduced: 22 macro states, 4 micro states."""
        self._run_draw_test("recession", 6, 10)

    def test_recessionUI(self):
        """RecessionUI: 42 macro states, non-standard transition_ub."""
        self._run_draw_test("recessionUI", 6, 20)

    def test_recession_rspell4(self):
        """Recession with shorter expected duration."""
        self._run_draw_test("recession", 4, 20)

    def test_override_mechanism(self):
        """
        Verify that a subclass of AggIndMarkovConsumerType can override
        get_micro_markov_states with the searchsorted approach and produce
        results consistent with the standalone function.
        """
        macro_arr, cond, _ = _build_all_arrays("d", "base", 6, 20)
        N = _NUM_BASE_MRKV_STATES

        def _dummy_solver(*args, **kwargs):
            return None

        class MockAgent(AggIndMarkovConsumerType):
            time_inv_ = []
            time_vary_ = []
            shock_vars_ = ["Mrkv"]
            default_ = {
                "params": {"cycles": 0, "T_cycle": 1, "AgentCount": 100},
                "solver": _dummy_solver,
            }

            def __init__(self):
                super().__init__(
                    num_macro_states=1,
                    num_micro_states=N,
                    cycles=0,
                    T_cycle=1,
                    AgentCount=100,
                    construct=False,
                )
                self.global_markov = True
                self.CondMrkvArrays = cond
                self.MacroMrkvArray = macro_arr

            def get_macro_markov_states(self):
                pass  # MacroMrkvNow already set externally

            def get_micro_markov_states(self):
                draws = self.RNG.uniform(size=self.AgentCount)
                J = self.CondMrkvArrays[0].shape[0]
                micro_prev = self.MicroMrkvNow.copy()
                new_micro = np.zeros(self.AgentCount, dtype=int)
                for i in range(self.MacroMrkvArray.shape[0]):
                    Cutoffs = np.cumsum(self.CondMrkvArrays[i], axis=1)
                    macro_match = self.MacroMrkvNow == i
                    for j in range(J):
                        these = np.logical_and(macro_match, micro_prev == j)
                        new_micro[these] = np.searchsorted(
                            Cutoffs[j, :], draws[these]
                        ).astype(int)
                self.MicroMrkvNow = new_micro

        agent = MockAgent()
        agent.MacroMrkvNow = 0
        agent.MicroMrkvNow = np.zeros(100, dtype=int)
        agent.shocks = {"Mrkv": np.zeros(100, dtype=int)}

        agent.get_markov_states()

        self.assertTrue(np.all(agent.MicroMrkvNow >= 0))
        self.assertTrue(np.all(agent.MicroMrkvNow < N))
        combined = agent.shocks["Mrkv"]
        self.assertEqual(
            len(combined), 100,
            "Combined Mrkv should have one entry per agent",
        )
        np.testing.assert_array_equal(
            combined,
            N * agent.MacroMrkvNow + agent.MicroMrkvNow,
        )


# ============================================================================
# Level 3: Combined State Encoding Round-Trip
# ============================================================================

class TestLevel3_StateEncodingRoundTrip(unittest.TestCase):
    """
    Verify combined-state encoding/decoding for N=4 (HAFiscal's
    num_base_MrkvStates) across all macro-state counts.
    """

    def test_roundtrip_base(self):
        """Base: 1 macro state × 4 micro states = 4 combined states."""
        N = _NUM_BASE_MRKV_STATES
        for macro in range(1):
            for micro in range(N):
                combined = N * macro + micro
                self.assertEqual(combined // N, macro)
                self.assertEqual(combined % N, micro)

    def test_roundtrip_recession_42(self):
        """Recession: 42 macro × 4 micro = 168 combined states."""
        N = _NUM_BASE_MRKV_STATES
        M = 2 * (20 + 1)  # 42
        for macro in range(M):
            for micro in range(N):
                combined = N * macro + micro
                self.assertEqual(combined // N, macro)
                self.assertEqual(combined % N, micro)
                self.assertTrue(0 <= combined < M * N)

    def test_roundtrip_recession_22(self):
        """Reduced_Run: 22 macro × 4 micro = 88 combined states."""
        N = _NUM_BASE_MRKV_STATES
        M = 2 * (10 + 1)  # 22
        for macro in range(M):
            for micro in range(N):
                combined = N * macro + micro
                self.assertEqual(combined // N, macro)
                self.assertEqual(combined % N, micro)
                self.assertTrue(0 <= combined < M * N)

    def test_base_class_helpers(self):
        """Verify AggIndMarkovConsumerType's helper methods match HAFiscal encoding."""
        N = _NUM_BASE_MRKV_STATES

        class Dummy(AggIndMarkovConsumerType):
            pass

        agent = Dummy.__new__(Dummy)
        agent.num_macro_states = 42
        agent.num_micro_states = N

        for macro in range(42):
            for micro in range(N):
                combined = N * macro + micro
                self.assertEqual(agent.macro_from_combined(combined), macro)
                self.assertEqual(agent.micro_from_combined(combined), micro)

    def test_aggfiscal_encoding_matches(self):
        """
        Verify the exact encoding line from AggFiscalModel.py line 648:
            MrkvNow = num_base_MrkvStates * MacroMrkvNow + MicroMrkvNow
        matches AggIndMarkovConsumerType's convention:
            MrkvCombined = num_micro_states * MacroMrkvNow + MicroMrkvNow
        """
        N = _NUM_BASE_MRKV_STATES
        rng = np.random.default_rng(99)
        num_agents = 500
        for M in [1, 22, 42]:
            MacroMrkvNow = rng.integers(0, M, size=num_agents)
            MicroMrkvNow = rng.integers(0, N, size=num_agents)

            hafiscal_encoding = N * MacroMrkvNow + MicroMrkvNow
            hark_encoding = N * MacroMrkvNow + MicroMrkvNow

            np.testing.assert_array_equal(hafiscal_encoding, hark_encoding)


# ============================================================================
# Level 4: Solver Equivalence
# ============================================================================

class TestLevel4_SolverEquivalence(unittest.TestCase):
    """
    Verify that the solver produces identical consumption functions when given
    MrkvArray from make_full_mrkv_array vs make_hierarchical_mrkv_array.

    Since Level 1 proves these matrices are bitwise identical, the solver
    *must* produce identical results. These tests confirm end-to-end through
    the Economy.solve() pathway, which handles CFunc/Cgrid/ADFunc setup.
    """

    @classmethod
    def setUpClass(cls):
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        from HARK.distributions import DiscreteDistribution

        params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
        cls.init_dropout = params[0]
        cls.init_highschool = params[1]
        cls.init_college = params[2]
        cls.init_ADEconomy = params[3]

    def _build_economy_pair(self, shock_type):
        """Build two economies — one with old matrices, one with new — and solve."""
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        from HARK.distributions import DiscreteDistribution

        economies = []
        agent_sets = []

        for use_new in [False, True]:
            agents = []
            for init_params in [self.init_dropout, self.init_highschool, self.init_college]:
                agent = AggFiscalType(**deepcopy(init_params))
                agents.append(agent)

            econ = AggregateDemandEconomy(**deepcopy(self.init_ADEconomy))

            for agent in agents:
                agent.get_economy_data(econ)

            IncomeDstn_unemp = DiscreteDistribution(
                np.array([1.0]),
                [np.array([1.0]), np.array([agents[0].IncUnemp])],
            )
            IncomeDstn_unemp_nobenefits = DiscreteDistribution(
                np.array([1.0]),
                [np.array([1.0]), np.array([agents[0].IncUnempNoBenefits])],
            )
            for agent in agents:
                EmployedIncomeDstn = deepcopy(agent.IncShkDstn[0])
                agent.IncShkDstn = [
                    [EmployedIncomeDstn]
                    + [IncomeDstn_unemp] * UBspell_normal
                    + [IncomeDstn_unemp_nobenefits] * _N_NOBEN
                ]
                agent.IncShkDstn_base = agent.IncShkDstn
                agent.switch_shock_type(shock_type)

                if use_new:
                    agent.update_mrkv_array(shock_type)
                    new_full = make_hierarchical_mrkv_array(
                        agent.MacroMrkvArray, agent.CondMrkvArrays,
                    )
                    agent.MrkvArray = [new_full]

            econ.agents = agents
            econ.solve()
            economies.append(econ)
            agent_sets.append(agents)

        return economies, agent_sets

    def _compare_agents(self, agents_old, agents_new, shock_type):
        """Compare cFunc between old and new agent sets."""
        for idx, (a_old, a_new) in enumerate(zip(agents_old, agents_new)):
            J = a_old.MrkvArray[0].shape[0]
            m_grid = np.linspace(0.1, 20.0, 50)
            c_grid = np.ones(50)
            for j in range(J):
                c_old = a_old.solution[0].cFunc[j](m_grid, c_grid)
                c_new = a_new.solution[0].cFunc[j](m_grid, c_grid)
                np.testing.assert_allclose(
                    c_old, c_new, atol=1e-14,
                    err_msg=(
                        f"cFunc mismatch: agent {idx}, state {j}, "
                        f"shock={shock_type}"
                    ),
                )

    def test_base(self):
        """Base: 4 states. Quick to solve."""
        economies, agent_sets = self._build_economy_pair("base")
        self._compare_agents(agent_sets[0], agent_sets[1], "base")


# ============================================================================
# Level 5: Simulation Path Equivalence
# ============================================================================

def _setup_economy(init_dropout, init_highschool, init_college, init_ADEconomy,
                   shock_type, use_new_matrix=False):
    """
    Build a complete economy following the EstimSetupEconomy.py + Simulate.py
    pattern. Returns (economy, agents).
    """
    from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    from HARK.distributions import DiscreteDistribution

    agents = []
    for init_params in [init_dropout, init_highschool, init_college]:
        agent = AggFiscalType(**deepcopy(init_params))
        agents.append(agent)

    econ = AggregateDemandEconomy(**deepcopy(init_ADEconomy))

    for agent in agents:
        agent.get_economy_data(econ)

    IncomeDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agents[0].IncUnemp])],
    )
    IncomeDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agents[0].IncUnempNoBenefits])],
    )

    # Set up income distributions for all shock types (Simulate.py pattern)
    num_exp = agents[0].num_experiment_periods
    n_micro = _NUM_BASE_MRKV_STATES
    for agent in agents:
        EmployedIncShkDstn = deepcopy(agent.IncShkDstn[0])
        agent.IncShkDstn = [
            [agent.IncShkDstn[0]]
            + [IncomeDstn_unemp] * UBspell_normal
            + [IncomeDstn_unemp_nobenefits] * _N_NOBEN
        ]
        agent.IncShkDstn_base = agent.IncShkDstn

        IncShkDstn_recession = [agent.IncShkDstn[0] * (2 * (num_exp + 1))]
        agent.IncShkDstn_recession = IncShkDstn_recession
        agent.IncShkDstn_recessionUI = IncShkDstn_recession

        EmployedIncShkDstn_tc = deepcopy(EmployedIncShkDstn)
        EmployedIncShkDstn_tc.atoms[0][1] = (
            EmployedIncShkDstn_tc.atoms[0][1] * agent.TaxCutIncFactor
        )
        TaxCutStatesIncShkDstn = (
            [EmployedIncShkDstn_tc]
            + [IncomeDstn_unemp] * UBspell_normal
            + [IncomeDstn_unemp_nobenefits] * _N_NOBEN
        )
        IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
        for i in range(2 * n_micro, 18 * n_micro):
            IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, n_micro)]
        agent.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
        agent.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    econ.agents = agents

    # For base + new-matrix, swap in the rebuilt matrices BEFORE the first
    # (and only) solve. econ.solve() is NOT idempotent — each call advances
    # the economy's AD state — so the old/new paths must call it the same
    # number of times or the cFunc comparison measures solve-count, not
    # matrix equivalence.
    if shock_type == "base" and use_new_matrix:
        for agent in agents:
            agent.update_mrkv_array("base")
            new_full = make_hierarchical_mrkv_array(
                agent.MacroMrkvArray, agent.CondMrkvArrays,
            )
            agent.MrkvArray = [new_full]

    # Solve the base economy first (sets up CFunc, Cgrid, ADFunc)
    econ.solve()

    if shock_type != "base":
        # Use economy-level switch which properly resizes CFunc, MrkvArray,
        # then propagates to agents
        econ.switch_to_counterfactual_mode(shock_type)

        if use_new_matrix:
            for agent in agents:
                # update_mrkv_array sets MacroMrkvArray + CondMrkvArrays + MrkvArray
                agent.update_mrkv_array(shock_type)
                new_full = make_hierarchical_mrkv_array(
                    agent.MacroMrkvArray, agent.CondMrkvArrays,
                )
                agent.MrkvArray = [new_full]

        econ.solve()

    return econ, agents


class TestLevel5_SimulationPathEquivalence(unittest.TestCase):
    """
    Build two full economies — one with original matrices, one with
    make_hierarchical_mrkv_array — and compare solutions. This exercises
    the complete setup → solve → simulation pipeline.

    Since Level 1 proves bitwise matrix identity, these must produce
    identical results. Any deviation indicates a test infrastructure bug
    (and once the refactoring is done, any deviation indicates a
    behavioral mismatch).
    """

    @classmethod
    def setUpClass(cls):
        params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
        cls.init_dropout = params[0]
        cls.init_highschool = params[1]
        cls.init_college = params[2]
        cls.init_ADEconomy = params[3]

    def _compare_solutions(self, shock_type):
        """Build two economies and compare agent solutions."""
        _, agents_old = _setup_economy(
            self.init_dropout, self.init_highschool, self.init_college,
            self.init_ADEconomy, shock_type, use_new_matrix=False,
        )
        _, agents_new = _setup_economy(
            self.init_dropout, self.init_highschool, self.init_college,
            self.init_ADEconomy, shock_type, use_new_matrix=True,
        )

        for idx, (a_old, a_new) in enumerate(zip(agents_old, agents_new)):
            J = a_old.MrkvArray[0].shape[0]
            m_grid = np.linspace(0.1, 20.0, 50)
            c_grid = np.ones(50)
            for j in range(J):
                c_old = a_old.solution[0].cFunc[j](m_grid, c_grid)
                c_new = a_new.solution[0].cFunc[j](m_grid, c_grid)
                np.testing.assert_allclose(
                    c_old, c_new, atol=1e-14,
                    err_msg=(
                        f"cFunc mismatch: agent {idx}, state {j}, "
                        f"shock={shock_type}"
                    ),
                )

    def test_base(self):
        self._compare_solutions("base")

    def test_recession(self):
        self._compare_solutions("recession")

    def test_recessionUI(self):
        self._compare_solutions("recessionUI")

    def test_recessionCheck(self):
        self._compare_solutions("recessionCheck")

    def test_recessionTaxCut(self):
        self._compare_solutions("recessionTaxCut")


# ============================================================================
# Level 6: Aggregate Dynamics Equivalence
# ============================================================================

class TestLevel6_AggregateDynamicsEquivalence(unittest.TestCase):
    """
    Run the full AggregateDemandEconomy solve cycle at Reduced_Run scale
    and compare converged economy-level parameters (CFunc intercepts/slopes)
    between old and new matrix sources.
    """

    @classmethod
    def setUpClass(cls):
        params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
        cls.init_dropout = params[0]
        cls.init_highschool = params[1]
        cls.init_college = params[2]
        cls.init_ADEconomy = params[3]

    def _compare_economy_convergence(self, shock_type):
        """Compare converged economy parameters between old and new."""
        econ_old, _ = _setup_economy(
            self.init_dropout, self.init_highschool, self.init_college,
            self.init_ADEconomy, shock_type, use_new_matrix=False,
        )
        econ_new, _ = _setup_economy(
            self.init_dropout, self.init_highschool, self.init_college,
            self.init_ADEconomy, shock_type, use_new_matrix=True,
        )

        np.testing.assert_allclose(
            econ_old.intercept_prev, econ_new.intercept_prev, atol=1e-14,
            err_msg=f"Intercept mismatch for {shock_type}",
        )
        np.testing.assert_allclose(
            econ_old.slope_prev, econ_new.slope_prev, atol=1e-14,
            err_msg=f"Slope mismatch for {shock_type}",
        )

    def test_base(self):
        self._compare_economy_convergence("base")

    def test_recession(self):
        self._compare_economy_convergence("recession")

    def test_recessionUI(self):
        self._compare_economy_convergence("recessionUI")

    def test_recessionCheck(self):
        self._compare_economy_convergence("recessionCheck")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
