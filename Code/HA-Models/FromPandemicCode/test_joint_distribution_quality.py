"""
Assess quality of TM-initialized joint (mNrm, pLvl, aNrm) vs burn-in MC.

Plan: debug/20260323-1243h_plan-to-assess-quality-of-initial-joint-distributions_ClaudeOpus4p6.md

TM-init: independent (j,mNrm) from TM ergodic and analytical age-conditional pLvl
(test_tm_init_mc.py style, including BUG-014 lognormal mean correction).

Writes outputs only to paths containing the substring 'composer' (see OUT_* below).
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

# --- Output files: must include "composer" (do not overwrite other AI runs) ---
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_OUT_CSV = os.path.join(
    _REPO_ROOT, "debug", "joint_distribution_quality_table_composer.csv"
)
_OUT_SUMMARY = os.path.join(
    _REPO_ROOT, "debug", "joint_distribution_quality_summary_composer.txt"
)

N = 80000
MCOUNT = 50
BURN_IN_PERIODS = 400
TRACK_PERIODS = 20
RNG_TM = np.random.RandomState(42)


def _moments(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {
            "mean": np.nan,
            "std": np.nan,
            "p25": np.nan,
            "p50": np.nan,
            "p75": np.nan,
        }
    return {
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "p25": float(np.percentile(x, 25)),
        "p50": float(np.percentile(x, 50)),
        "p75": float(np.percentile(x, 75)),
    }


def _corr_safe(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return float("nan")
    ca = a[m] - np.mean(a[m])
    cb = b[m] - np.mean(b[m])
    da = np.std(a[m])
    db = np.std(b[m])
    if da < 1e-15 or db < 1e-15:
        return float("nan")
    return float(np.mean(ca * cb) / (da * db))


def _micro_fracs(mrkv: np.ndarray, J: int) -> list:
    micro = mrkv % J
    return [float(np.mean(micro == j)) for j in range(J)]


def _snapshot_row(
    label: str,
    t: int,
    aNrm: np.ndarray,
    pLvl: np.ndarray,
    mNrm: np.ndarray,
    mrkv: np.ndarray,
    J: int,
) -> dict:
    row = {
        "path": label,
        "t": t,
        "corr_aNrm_pLvl": _corr_safe(aNrm, pLvl),
        "corr_mNrm_pLvl": _corr_safe(mNrm, pLvl),
        "corr_loga_logp": _corr_safe(
            np.log(np.maximum(aNrm, 0.0) + 1.0), np.log(np.maximum(pLvl, 1e-300))
        ),
    }
    for name, arr in [("aNrm", aNrm), ("pLvl", pLvl), ("mNrm", mNrm)]:
        m = _moments(arr)
        for k, v in m.items():
            row[f"{name}_{k}"] = v
    for j, f in enumerate(_micro_fracs(mrkv, J)):
        row[f"frac_{j}"] = f
    return row


def _prepare_agent_base(agent: AggFiscalType) -> None:
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.state_now["PlvlAgg"] = 1.0


def _run_track(
    agent: AggFiscalType,
    J: int,
    n_periods: int,
    mNrm_t0: np.ndarray | None,
    label: str,
) -> list[dict]:
    """
    Record t=0 from current state_now. mNrm_t0: use for t=0 if state mNrm invalid (TM inject).
    Then sim_one_period n_periods-1 more times, recording after each period.
    Total rows = n_periods (t = 0 .. n_periods-1).
    """
    rows = []
    for t in range(n_periods):
        aNrm = np.array(agent.state_now["aNrm"], copy=True)
        pLvl = np.array(agent.state_now["pLvl"], copy=True)
        mNrm = np.array(agent.state_now["mNrm"], copy=True)
        mrkv = np.array(agent.shocks["Mrkv"], copy=True)
        if t == 0 and mNrm_t0 is not None:
            mNrm = np.array(mNrm_t0, copy=True)
        rows.append(_snapshot_row(label, t, aNrm, pLvl, mNrm, mrkv, J))
        if t < n_periods - 1:
            agent.sim_one_period()
    return rows


def main() -> None:
    t_all = time()

    [
        _init_dropout,
        _init_highschool,
        init_college,
        init_ADEconomy,
        DiscFacDstns,
        _DiscFacCount,
        _AgentCountTotal,
        _base_dict,
        _num_max_iter,
        _conv_tol,
        UBspell_normal,
        num_base_MrkvStates,
        _data_EducShares,
        _max_rec_dur,
        num_experiment_periods,
        *_policy_changes,
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

    bl_data = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
    bd = bl_data[0]
    ergodic = bd["ergodic"]
    dist_mGrid = bd["dist_mGrid"]
    M = len(dist_mGrid)
    sol = BaseType.solution[0]
    cFuncs = [sol.cFunc[j] for j in range(J)]

    flat_probs = ergodic / np.sum(ergodic)
    agent_bins = RNG_TM.choice(len(flat_probs), size=N, p=flat_probs)
    agent_j = agent_bins // M
    agent_m_idx = agent_bins % M
    agent_mNrm = dist_mGrid[agent_m_idx].copy()
    for i in range(N):
        idx = agent_m_idx[i]
        if idx < M - 1:
            lo, hi = dist_mGrid[idx], dist_mGrid[idx + 1]
        else:
            lo, hi = dist_mGrid[idx], dist_mGrid[idx] * 1.01
        agent_mNrm[i] = RNG_TM.uniform(lo, hi)

    agent_aNrm = np.zeros(N)
    for j in range(J):
        mask = agent_j == j
        if np.any(mask):
            cNrm_j = cFuncs[j](agent_mNrm[mask], np.ones(np.sum(mask)))
            agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - cNrm_j, 0.0)

    LivPrb = BaseType.LivPrb[0][0]
    T_age = BaseType.T_age
    age_probs = np.array([LivPrb ** (k - 1) for k in range(1, T_age + 1)])
    age_probs /= np.sum(age_probs)
    agent_ages = RNG_TM.choice(T_age, size=N, p=age_probs) + 1

    pLogInitMean = BaseType.pLogInitMean
    pLogInitStd = getattr(
        BaseType, "pLogInitStd", getattr(BaseType, "pLvlInitStd", 0.0)
    )
    log_pLvl_init = RNG_TM.normal(pLogInitMean, pLogInitStd, size=N)
    PermShkDstn = BaseType.IncShkDstn_base[0][0]
    log_PermShk_vals = np.log(PermShkDstn.atoms[0])
    PermShk_var = np.dot(PermShkDstn.pmv, log_PermShk_vals ** 2) - np.dot(
        PermShkDstn.pmv, log_PermShk_vals
    ) ** 2
    g_lvl = effective_pLvl_growth(BaseType, getattr(BaseType, "Urate_normal", 0.0))
    eff_perm = effective_perm_shock_periods_for_t_age(
        agent_ages, BaseType, getattr(BaseType, "Urate_normal", 0.0))
    log_pLvl = log_pLvl_init + agent_ages * np.log(g_lvl)
    log_pLvl += eff_perm * (-PermShk_var / 2.0)
    log_pLvl += RNG_TM.normal(0, np.sqrt(PermShk_var * eff_perm))
    agent_pLvl = np.exp(log_pLvl)

    # --- TM-initialized track ---
    eco_tm = deepcopy(AggEco)
    ag_tm = eco_tm.agents[0]
    ag_tm.AgentCount = N
    ag_tm.seed = 0
    eco_tm.solve()
    eco_tm.reset()
    ag_tm.initialize_sim()
    ag_tm.state_now["aNrm"][:] = agent_aNrm
    ag_tm.state_now["pLvl"][:] = agent_pLvl
    ag_tm.shocks["Mrkv"][:] = agent_j
    if hasattr(ag_tm, "t_age") and ag_tm.t_age is not None:
        ag_tm.t_age[:] = agent_ages
    _prepare_agent_base(ag_tm)
    rows_tm = _run_track(ag_tm, J, TRACK_PERIODS, agent_mNrm, "TM_init")

    # --- Burn-in then same tracking window ---
    eco_bi = deepcopy(AggEco)
    ag_bi = eco_bi.agents[0]
    ag_bi.AgentCount = N
    ag_bi.seed = 0
    ag_bi.get_economy_data(eco_bi)
    eco_bi.solve()
    eco_bi.reset()
    ag_bi.initialize_sim()
    _prepare_agent_base(ag_bi)
    for _ in range(BURN_IN_PERIODS):
        ag_bi.sim_one_period()
    rows_bi = _run_track(ag_bi, J, TRACK_PERIODS, None, "burnin400")

    all_rows = rows_tm + rows_bi

    def _fmt_csv(v):
        if isinstance(v, float) and not np.isfinite(v):
            return ""
        return str(v)

    os.makedirs(os.path.dirname(_OUT_CSV), exist_ok=True)
    fieldnames = sorted({k for r in all_rows for k in r.keys()})
    with open(_OUT_CSV, "w", encoding="utf-8") as f:
        f.write(",".join(fieldnames) + "\n")
        for r in all_rows:
            f.write(",".join(_fmt_csv(r.get(k, "")) for k in fieldnames) + "\n")

    # --- Summary text ---
    lines = [
        "Joint distribution quality (TM-init vs burn-in MC)",
        f"N={N}, mCount={MCOUNT}, burn_in={BURN_IN_PERIODS}, track={TRACK_PERIODS}",
        f"Outputs: {_OUT_CSV}",
        f"         {_OUT_SUMMARY}",
        "",
        "t=0 comparison (corr):",
    ]
    r0_tm = next(r for r in rows_tm if r["t"] == 0)
    r0_bi = next(r for r in rows_bi if r["t"] == 0)
    for key in [
        "corr_aNrm_pLvl",
        "corr_mNrm_pLvl",
        "corr_loga_logp",
        "aNrm_mean",
        "pLvl_mean",
        "mNrm_mean",
    ]:
        lines.append(
            f"  {key:20s}  TM_init={r0_tm.get(key, '')}  burnin={r0_bi.get(key, '')}"
        )

    lines.append("")
    lines.append("Drift TM_init: mean pLvl t=19 vs t=0 (relative):")
    r19_tm = next(r for r in rows_tm if r["t"] == TRACK_PERIODS - 1)
    if r0_tm["pLvl_mean"]:
        lines.append(
            f"  pLvl: {(r19_tm['pLvl_mean'] - r0_tm['pLvl_mean']) / r0_tm['pLvl_mean'] * 100:.3f}%"
        )
    lines.append(
        f"  aNrm: {(r19_tm['aNrm_mean'] - r0_tm['aNrm_mean']) / max(abs(r0_tm['aNrm_mean']), 1e-12) * 100:.3f}%"
    )

    lines.append("")
    lines.append("Drift burn-in window (t=0..19 relative to t=0 in window):")
    r19_bi = next(r for r in rows_bi if r["t"] == TRACK_PERIODS - 1)
    if r0_bi["pLvl_mean"]:
        lines.append(
            f"  pLvl: {(r19_bi['pLvl_mean'] - r0_bi['pLvl_mean']) / r0_bi['pLvl_mean'] * 100:.3f}%"
        )
    lines.append(
        f"  aNrm: {(r19_bi['aNrm_mean'] - r0_bi['aNrm_mean']) / max(abs(r0_bi['aNrm_mean']), 1e-12) * 100:.3f}%"
    )

    lines.append("")
    lines.append(
        "Interpretation (from plan): large |corr| difference at t=0 suggests independence"
        " of (j,m) and pLvl matters; rapid corr stabilization suggests short warmup."
    )
    lines.append(f"Wall time: {time() - t_all:.1f}s")

    with open(_OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
