"""
Integration checks for SST income process + cwd-safe EstimParameters load.

Run from repo root: uv run pytest Code/HA-Models/FromPandemicCode/test_sst_integration.py -v
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from copy import deepcopy
from HARK.distributions import DiscreteDistribution

_FPC = Path(__file__).resolve().parent


def _patch_income_shock_dstn(agent, UBspell_normal: int) -> None:
    """Match production/TM tests: list of DiscreteDistribution per micro state."""
    _p0 = agent.IncShkDstn[0]
    emp_src = _p0[0] if isinstance(_p0, (list, tuple)) else _p0
    EmployedIncShkDstn = deepcopy(emp_src)
    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnemp])],
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnempNoBenefits])],
    )
    # Encoding-agnostic micro-state count from the agent's base MrkvArray
    # (4 under legacy, 6 under the canonical bug_fix encoding; BUG-043).
    n_micro = agent.MrkvArray[0].shape[0]
    agent.IncShkDstn = [
        [EmployedIncShkDstn]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits] * (n_micro - 1 - UBspell_normal)
    ]
    agent.IncShkDstn_base = agent.IncShkDstn


@pytest.fixture(autouse=True)
def _patch_argv():
    """Parameters/EstimParameters expect argv placeholders when imported as tests."""
    saved = sys.argv[:]
    sys.argv = [sys.argv[0], "1.01", "2.0", "0.7"]
    yield
    sys.argv = saved


def test_H1_estimparameters_splurge_loads_with_cwd_not_frompandemic():
    """EstimParameters must open splurge file via __file__, not process cwd."""
    code = (
        "import os, sys\n"
        f"sys.path.insert(0, {str(_FPC)!r})\n"
        "os.chdir('/')  # not Code/HA-Models/FromPandemicCode\n"
        "import EstimParameters as EP\n"
        "assert EP.Splurge > 0 and EP.Splurge < 1.0\n"
        "print('H1_ok')\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(_FPC),
    )
    assert r.returncode == 0, f"stderr={r.stderr!r} stdout={r.stdout!r}"


def test_H2_return_parameters_includes_sst_fields():
    """Init dicts carry SST keys and micro PermGroFac shape."""
    from Parameters import return_parameters

    out = return_parameters(Parametrization="Baseline", OutputFor="_Main.py")
    init_d, init_h, init_c = out[0], out[1], out[2]
    for label, d in ("dropout", init_d), ("hs", init_h), ("college", init_c):
        assert "PermGroFac_unemp" in d, label
        assert "perm_shocks_during_unemployment" in d, label
        assert "tran_shocks_during_unemployment" in d, label
        pgf = d["PermGroFac"][0]
        nb = d["num_base_MrkvStates"]
        assert len(pgf) == nb, (label, len(pgf), nb)
        assert pgf[0] > 1.0, label
        assert all(pgf[j] == d["PermGroFac_unemp"] for j in range(1, nb)), label


def test_H3_effective_pLvl_growth_matches_agent_perm_gro_fac():
    """Closed form vs income_process_sst for a realistic PermGroFac vector."""
    from income_process_sst import effective_pLvl_growth
    from Parameters import return_parameters

    init_h = return_parameters(Parametrization="Baseline", OutputFor="_Main.py")[1]
    u = float(init_h["Urate_normal"])
    agent = SimpleNamespace(
        PermGroFac=[np.asarray(init_h["PermGroFac"][0], dtype=float)],
        Urate_normal=u,
    )
    g = effective_pLvl_growth(agent, u)
    G0 = float(agent.PermGroFac[0][0])
    G1 = float(agent.PermGroFac[0][1])
    expected = (1.0 - u) * G0 + u * G1
    assert abs(g - expected) < 1e-10


def test_H4_compute_analytical_mean_pLvl_finite_after_import_stack():
    """Full import chain (AggFiscalModel) + tm_methods helper stays finite."""
    from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    from Parameters import return_parameters
    from tm_methods import compute_analytical_mean_pLvl

    params = return_parameters(Parametrization="Baseline", OutputFor="_Main.py")
    init_h = params[1]
    init_AD = params[3]
    UBspell_normal = int(params[10])
    econ = AggregateDemandEconomy(**init_AD)
    agent = AggFiscalType(**init_h)
    agent.cycles = 0
    _patch_income_shock_dstn(agent, UBspell_normal)
    agent.get_economy_data(econ)
    econ.agents = [agent]
    econ.solve()
    Ep = compute_analytical_mean_pLvl(agent)
    assert np.isfinite(Ep) and Ep > 0.0


def test_H5_switch_shock_type_tiles_perm_gro_fac():
    """After switch_shock_type, PermGroFac length matches Mrkv states."""
    from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    from Parameters import return_parameters

    params = return_parameters(Parametrization="Baseline", OutputFor="_Main.py")
    init_h = params[1]
    init_AD = params[3]
    UBspell_normal = int(params[10])
    num_experiment_periods = int(params[14])
    econ = AggregateDemandEconomy(**init_AD)
    agent = AggFiscalType(**init_h)
    agent.cycles = 0
    _patch_income_shock_dstn(agent, UBspell_normal)
    # Same pattern as Simulate.py: recession shock paths need expanded IncShkDstn lists.
    agent.IncShkDstn_recession = [
        agent.IncShkDstn[0] * (2 * (num_experiment_periods + 1))
    ]
    agent.IncShkDstn_recessionUI = agent.IncShkDstn_recession
    agent.IncShkDstn_recessionCheck = deepcopy(agent.IncShkDstn_recession)
    agent.IncShkDstn_recessionTaxCut = deepcopy(agent.IncShkDstn_recession)
    agent.get_economy_data(econ)
    econ.agents = [agent]
    econ.solve()
    n_base = int(agent.num_base_MrkvStates)
    assert len(agent.PermGroFac[0]) == n_base
    agent.switch_shock_type("recession")
    n_mrkv = agent.MrkvArray[0].shape[0]
    assert len(agent.PermGroFac[0]) == n_mrkv
    assert all(
        agent.PermGroFac[0][j] == agent.PermGroFac_base[0]
        for j in range(0, n_mrkv, n_base)
    )
