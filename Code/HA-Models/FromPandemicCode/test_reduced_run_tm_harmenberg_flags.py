"""
Fast regression: Reduced_Run + TM baseline data with/without Harmenberg neutral measure.

References:
    BST ApndxHarKmenberg, Theorem 1 ("Harmenberg's Method")
    math-derive-harm (neutral-identity): E_P[p*f(m)] = E_P[p] * E_Q[f(m)]
    history/20260402-reduced-run-harmenberg-output-type-map.md (Type A/B/C)
"""

import os
import sys
from copy import deepcopy

import numpy as np
import pytest

sys.argv = [os.path.basename(__file__)]

# Match validate_tm_check.py / AggFiscalMAIN_reduced single-type setup
cwd = os.getcwd()
if not cwd.endswith("FromPandemicCode"):
    os.chdir(os.path.join(cwd, "Code", "HA-Models", "FromPandemicCode"))
sys.path.insert(0, os.getcwd())

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import compute_baseline_tm_data


def _build_single_type_reduced_economy(agent_count=500):
    [
        init_dropout,
        init_highschool,
        init_college,
        init_ADEconomy,
        DiscFacDstns,
        DiscFacCount,
        AgentCountTotal,
        base_dict,
        num_max_iterations_solvingAD,
        convergence_tol_solvingAD,
        UBspell_normal,
        num_base_MrkvStates,
        data_EducShares,
        max_recession_duration,
        num_experiment_periods,
        recession_changes,
        UI_changes,
        recession_UI_changes,
        TaxCut_changes,
        recession_TaxCut_changes,
        Check_changes,
        recession_Check_changes,
    ] = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")

    init_dict = init_highschool
    BaseType = AggFiscalType(**init_dict)
    BaseType.cycles = 0
    BaseType.AgentCount = agent_count
    BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

    AggDemandEconomy = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(AggDemandEconomy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseType.IncUnemp])],
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])],
    )

    BaseType.IncShkDstn[0].seed = 763607780
    BaseType.IncShkDstn[0].reset()

    # Encoding-agnostic micro-state lists (4 legacy / 6 bug_fix; BUG-043):
    # the extra u3Q/u4Q states pay no-benefits income outside recessionUI.
    n_noben = num_base_MrkvStates - 1 - UBspell_normal
    EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits] * n_noben
    ]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn
    IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    BaseType.IncShkDstn_recession = IncShkDstn_recession
    BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
    EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor
    TaxCutStatesIncShkDstn = (
        [EmployedIncShkDstn]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits] * n_noben
    )
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
        IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[
            np.mod(i, num_base_MrkvStates)]
    BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
    BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    AggDemandEconomy.agents = [BaseType]
    return AggDemandEconomy


@pytest.mark.slow
def test_compute_baseline_tm_data_neutral_measure_reduced_run():
    economy = _build_single_type_reduced_economy()
    economy.solve()

    m_count = 25
    results = {}
    for neutral in (False, True):
        out = compute_baseline_tm_data(
            economy,
            mCount=m_count,
            neutral_measure=neutral,
            verbose=False,
        )
        assert len(out) == 1
        erg = out[0]["ergodic"]
        assert np.isfinite(erg).all()
        assert abs(np.sum(erg) - 1.0) < 1e-6
        assert out[0]["E_pLvl"] > 0.0 and np.isfinite(out[0]["E_pLvl"])
        results[neutral] = out[0]

    # Q-ergodic must differ from P-ergodic in the within-state m-distribution
    # (the ψ-reweighting shifts mass toward high-m; see math-derive-harm §1).
    # State fractions should be nearly identical (Q-P-frac-equal).
    erg_P = results[False]["ergodic"]
    erg_Q = results[True]["ergodic"]
    assert not np.allclose(erg_P, erg_Q, atol=1e-8), (
        "P and Q ergodic distributions should differ (neutral_measure flag may be ignored)"
    )
    M = len(results[False]["dist_mGrid"])
    frac_P = np.sum(erg_P[:M])
    frac_Q = np.sum(erg_Q[:M])
    assert abs(frac_P - frac_Q) < 0.01, (
        f"Employed state fractions under P ({frac_P:.6f}) and Q ({frac_Q:.6f}) "
        "should be nearly equal — math-derive-harm (Q-P-frac-equal)"
    )
