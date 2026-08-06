"""
Proof-of-concept: fixes from debug/20260323-1312h_composer-fixes-for-mortality-discrepancy.md

Not part of main pipeline — compares TM-init drift variants vs baseline jitter.

Fixes tested (combinations):
  - mNrm: baseline jitter | no_jitter | mean_match (scale to TM E[m])
  - pLvl: analytical (default) | scale to MC burn-in mean pLvl
  - optional WARMUP_PERIODS sim steps after inject before 20-period drift window

Outputs: debug/mortality_fix_poc_composer.csv, mortality_fix_poc_composer_assessment.txt
"""

from __future__ import annotations

import os
import sys
from copy import deepcopy
from time import time

import numpy as np

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith("FromPandemicCode"):
    os.chdir(cwd + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, os.getcwd())

os.environ["MPLBACKEND"] = "Agg"

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth, effective_perm_shock_variance_periods
from tm_methods import compute_baseline_tm_data

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_OUT_CSV = os.path.join(_REPO_ROOT, "debug", "mortality_fix_poc_composer.csv")
_OUT_TXT = os.path.join(_REPO_ROOT, "debug", "mortality_fix_poc_composer_assessment.txt")

N = 80000
MCOUNT = 50
BURN_IN_PERIODS = 400
TRACK_PERIODS = 20
WARMUP_OPTIONS = (0, 10)  # compare no warmup vs short warmup on best m-fix
RNG = np.random.RandomState(42)


def _tm_Em_bop(ergodic: np.ndarray, dist_mGrid: np.ndarray, M: int, J: int) -> float:
    em = 0.0
    for j in range(J):
        sl = ergodic[j * M : (j + 1) * M]
        em += float(np.dot(sl, dist_mGrid))
    return em


def _build_college_economy():
    [
        _a,
        _b,
        init_college,
        init_ADEconomy,
        DiscFacDstns,
        _dfc,
        _act,
        _bd,
        _nmi,
        _ct,
        UBspell_normal,
        num_base_MrkvStates,
        _des,
        _mrd,
        num_experiment_periods,
        *_pc,
    ] = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    J = num_base_MrkvStates
    BaseType = AggFiscalType(**init_college)
    BaseType.cycles = 0
    BaseType.AgentCount = N
    BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]
    AggEco = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(AggEco)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])]
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])],
    )
    BaseType.IncShkDstn[0].seed = 763607780
    BaseType.IncShkDstn[0].reset()
    EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    ]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn
    IncShkDstn_recession = [
        BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))
    ]
    BaseType.IncShkDstn_recession = IncShkDstn_recession
    BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
    EmployedIncShkDstn.atoms[0][1] = (
        EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor
    )
    TaxCutStatesIncShkDstn = (
        [EmployedIncShkDstn]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    )
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
        IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
    BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
    BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)
    AggEco.agents = [BaseType]
    AggEco.solve()
    return AggEco, BaseType, J


def _prepare_agent(ag):
    ag.AggDemandFac = 1.0
    ag.RfreeNow = 1.0
    ag.CaggNow = 1.0
    ag.Cratio = 1.0
    ag.state_now["PlvlAgg"] = 1.0


def _pLvl_draws(rng, BaseType, N_loc):
    LivPrb = BaseType.LivPrb[0][0]
    T_age = BaseType.T_age
    age_probs = np.array([LivPrb ** (k - 1) for k in range(1, T_age + 1)])
    age_probs /= np.sum(age_probs)
    agent_ages = rng.choice(T_age, size=N_loc, p=age_probs) + 1
    pLogInitMean = BaseType.pLogInitMean
    pLogInitStd = getattr(
        BaseType, "pLogInitStd", getattr(BaseType, "pLvlInitStd", 0.0)
    )
    log_pLvl_init = rng.normal(pLogInitMean, pLogInitStd, size=N_loc)
    PermShkDstn = BaseType.IncShkDstn_base[0][0]
    log_psi = np.log(PermShkDstn.atoms[0])
    PermShk_var = np.dot(PermShkDstn.pmv, log_psi**2) - np.dot(
        PermShkDstn.pmv, log_psi
    ) ** 2
    g_lvl = effective_pLvl_growth(BaseType, getattr(BaseType, "Urate_normal", 0.0))
    eff_perm = effective_perm_shock_periods_for_t_age(
        agent_ages, BaseType, getattr(BaseType, "Urate_normal", 0.0))
    log_pLvl = log_pLvl_init + agent_ages * np.log(g_lvl)
    log_pLvl += eff_perm * (-PermShk_var / 2.0)
    log_pLvl += rng.normal(0, np.sqrt(PermShk_var * eff_perm))
    return np.exp(log_pLvl), agent_ages


def _precompute_m_variants(
    rng_m: np.random.RandomState,
    agent_bins: np.ndarray,
    dist_mGrid: np.ndarray,
    M: int,
    E_m_tm: float,
) -> dict:
    """Same agent_bins for all; fair pLvl across scenarios (computed outside)."""
    agent_m_idx = agent_bins % M
    m_grid = dist_mGrid[agent_m_idx].astype(float).copy()
    m_jitter = m_grid.copy()
    for i in range(len(m_jitter)):
        idx = agent_m_idx[i]
        if idx < M - 1:
            lo, hi = dist_mGrid[idx], dist_mGrid[idx + 1]
        else:
            lo, hi = dist_mGrid[idx], dist_mGrid[idx] * 1.01
        m_jitter[i] = rng_m.uniform(lo, hi)
    m_jitter_mm = m_jitter * (E_m_tm / max(np.mean(m_jitter), 1e-15))
    m_grid_mm = m_grid * (E_m_tm / max(np.mean(m_grid), 1e-15))
    return {
        "jitter": m_jitter,
        "no_jitter": m_grid,
        "mean_match": m_jitter_mm,
        "no_jitter_mean_match": m_grid_mm,
    }


def _aNrm_from_m(agent_mNrm, agent_j, cFuncs, J):
    agent_aNrm = np.zeros(len(agent_mNrm))
    for j in range(J):
        mask = agent_j == j
        if np.any(mask):
            cj = cFuncs[j](agent_mNrm[mask], np.ones(np.sum(mask)))
            agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - cj, 0.0)
    return agent_aNrm


def _drift_aNrm(ag, J, track, m0, warmup: int) -> dict:
    for _ in range(warmup):
        ag.sim_one_period()
    r0 = float(np.mean(ag.state_now["aNrm"]))
    for _ in range(track - 1):
        ag.sim_one_period()
    r1 = float(np.mean(ag.state_now["aNrm"]))
    return {
        "aNrm_mean_t0": r0,
        "aNrm_mean_tEnd": r1,
        "aNrm_drift_pct": (r1 - r0) / max(abs(r0), 1e-12) * 100.0,
    }


def _run_scenario(
    label: str,
    AggEco,
    BaseType,
    J,
    cFuncs,
    agent_j,
    agent_mNrm: np.ndarray,
    agent_pLvl: np.ndarray,
    agent_ages: np.ndarray,
    E_m_tm: float,
    scale_pLvl: bool,
    mc_mean_pLvl: float | None,
    warmup: int,
) -> dict:
    agent_pLvl = np.array(agent_pLvl, copy=True)
    if scale_pLvl and mc_mean_pLvl is not None and np.mean(agent_pLvl) > 1e-15:
        agent_pLvl = agent_pLvl * (mc_mean_pLvl / np.mean(agent_pLvl))
    agent_aNrm = _aNrm_from_m(agent_mNrm, agent_j, cFuncs, J)

    eco = deepcopy(AggEco)
    ag = eco.agents[0]
    ag.AgentCount = N
    ag.seed = 0
    eco.solve()
    eco.reset()
    ag.initialize_sim()
    ag.state_now["aNrm"][:] = agent_aNrm
    ag.state_now["pLvl"][:] = agent_pLvl
    ag.shocks["Mrkv"][:] = agent_j
    if hasattr(ag, "t_age") and ag.t_age is not None:
        ag.t_age[:] = agent_ages
    _prepare_agent(ag)

    d = _drift_aNrm(ag, J, TRACK_PERIODS, agent_mNrm, warmup)
    return {
        "label": label,
        "scale_pLvl": int(scale_pLvl),
        "warmup": warmup,
        "mean_mNrm_inject": float(np.mean(agent_mNrm)),
        "E_m_tm": E_m_tm,
        "mean_m_err": float(np.mean(agent_mNrm) - E_m_tm),
        "mean_pLvl_inject": float(np.mean(agent_pLvl)),
        **d,
    }


def main():
    t0 = time()
    AggEco, BaseType, J = _build_college_economy()
    bl_data = compute_baseline_tm_data(AggEco, dist_aGrid_count=MCOUNT, verbose=False)
    bd = bl_data[0]
    ergodic = bd["ergodic"]
    dist_mGrid = bd["dist_mGrid"]
    M = len(dist_mGrid)
    sol = BaseType.solution[0]
    cFuncs = [sol.cFunc[j] for j in range(J)]
    E_m_tm = _tm_Em_bop(ergodic, dist_mGrid, M, J)

    flat_probs = ergodic / np.sum(ergodic)
    agent_bins = RNG.choice(len(flat_probs), size=N, p=flat_probs)
    agent_j = agent_bins // M
    m_variants = _precompute_m_variants(
        np.random.RandomState(42), agent_bins, dist_mGrid, M, E_m_tm
    )
    rng_p = np.random.RandomState(999)
    agent_pLvl_base, agent_ages = _pLvl_draws(rng_p, BaseType, N)

    # Burn-in reference mean pLvl (end state after BURN_IN_PERIODS)
    eco_bi = deepcopy(AggEco)
    ag_bi = eco_bi.agents[0]
    ag_bi.AgentCount = N
    ag_bi.seed = 0
    ag_bi.get_economy_data(eco_bi)
    eco_bi.solve()
    eco_bi.reset()
    ag_bi.initialize_sim()
    _prepare_agent(ag_bi)
    for _ in range(BURN_IN_PERIODS):
        ag_bi.sim_one_period()
    mc_mean_pLvl = float(np.mean(ag_bi.state_now["pLvl"]))

    def _go(lab, m_key, scale_pl, wu):
        return _run_scenario(
            lab,
            AggEco,
            BaseType,
            J,
            cFuncs,
            agent_j,
            m_variants[m_key],
            agent_pLvl_base,
            agent_ages,
            E_m_tm,
            scale_pl,
            mc_mean_pLvl if scale_pl else None,
            wu,
        )

    scenarios = []
    scenarios.append(_go("A_baseline_jitter", "jitter", False, 0))
    scenarios.append(_go("B_no_jitter", "no_jitter", False, 0))
    scenarios.append(_go("C_jitter_mean_match_m", "mean_match", False, 0))
    scenarios.append(_go("D_no_jitter_mean_match_m", "no_jitter_mean_match", False, 0))
    scenarios.append(_go("E_baseline_jitter_scale_pLvl", "jitter", True, 0))
    scenarios.append(
        _go("F_no_jitter_mean_match_scale_pLvl", "no_jitter_mean_match", True, 0)
    )
    for w in WARMUP_OPTIONS:
        if w == 0:
            continue
        scenarios.append(
            _go(f"G_no_jitter_mean_match_warmup{w}", "no_jitter_mean_match", False, w)
        )
        scenarios.append(
            _go(
                f"H_no_jitter_mean_match_scale_pLvl_warmup{w}",
                "no_jitter_mean_match",
                True,
                w,
            )
        )

    # Burn-in drift over same TRACK window (sanity)
    rows_bi = float(np.mean(ag_bi.state_now["aNrm"]))
    for _ in range(TRACK_PERIODS - 1):
        ag_bi.sim_one_period()
    rows_bi_end = float(np.mean(ag_bi.state_now["aNrm"]))
    burn_drift = (rows_bi_end - rows_bi) / max(abs(rows_bi), 1e-12) * 100.0

    os.makedirs(os.path.dirname(_OUT_CSV), exist_ok=True)
    keys = sorted({k for s in scenarios for k in s.keys()})
    with open(_OUT_CSV, "w", encoding="utf-8") as f:
        f.write(",".join(keys) + "\n")
        for s in scenarios:
            f.write(
                ",".join(
                    ""
                    if isinstance(s.get(k), float)
                    and not np.isfinite(s.get(k, np.nan))
                    else str(s.get(k, ""))
                    for k in keys
                )
                + "\n"
            )

    base_drift = scenarios[0]["aNrm_drift_pct"]
    best = min(scenarios, key=lambda s: abs(s["aNrm_drift_pct"] - 0.0))
    best_vs_burn = min(scenarios, key=lambda s: abs(s["aNrm_drift_pct"] - burn_drift))

    lines = [
        "PoC: mortality / TM-init discrepancy fixes (composer)",
        f"N={N}, mCount={MCOUNT}, burn_in reference pLvl from {BURN_IN_PERIODS} periods",
        f"Track window after inject (after warmup): {TRACK_PERIODS} periods",
        f"TM E[m] BOP (ergodic grid) = {E_m_tm:.6f}",
        f"MC mean pLvl after burn-in (for scaling) = {mc_mean_pLvl:.6f}",
        f"Burn-in continuation drift over {TRACK_PERIODS} periods: aNrm {burn_drift:.3f}%",
        "",
        "=== Results (lower |aNrm_drift_pct| is closer to stationary over window) ===",
    ]
    for s in scenarios:
        lines.append(
            f"  {s['label']:<40}  m_err={s['mean_m_err']:+.5f}  "
            f"aNrm_drift={s['aNrm_drift_pct']:+.3f}%"
        )
    lines.extend(
        [
            "",
            "=== Assessment ===",
            f"Baseline (A) aNrm drift: {base_drift:.3f}%",
            f"Smallest |drift| among TM-inits: {best['label']} -> {best['aNrm_drift_pct']:.3f}%",
            f"Closest drift to burn-in continuation ({burn_drift:.3f}%): "
            f"{best_vs_burn['label']} -> {best_vs_burn['aNrm_drift_pct']:.3f}%",
            "",
            "Typical pattern:",
            "  - no_jitter + mean_match_m removes ~0.14 mean(m) bias from jitter (see trace script).",
            "  - pLvl scaling aligns mean pLvl to burn-in; effect on normalized aNrm drift is secondary.",
            "  - warmup burns joint-law error before measuring drift; helps if injection is off fixed point.",
            f"Wall time: {time() - t0:.1f}s",
        ]
    )
    text = "\n".join(lines) + "\n"
    with open(_OUT_TXT, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
