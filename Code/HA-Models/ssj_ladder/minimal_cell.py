"""The A0 minimal household through the UNTOUCHED step4 per-cell API.

Uses `prepare_type_base` + `compute_type_jacobian_for_param` exactly as `jacobians.run()`
does — nothing in step4 is modified, monkeypatched or reimplemented; only the agent, the
init dict, and the income lists are driver-built. The three traps this file exists to
carry (all bitten during independent rebuilds): (1) `PermShkCount = TranShkCount = 1`,
because `calc_transition_matrix` sizes `shk_prbs` as (n_m, TranShkCount*PermShkCount) and
a 1-atom pmv against counts (7,7) silently broadcasts into 49 slots; (2) the +/-dx income
lists MUST use `hh_setup.dx` — `compile_JAC` divides by that module constant, so a
driver-local dx silently rescales every J; (3) the caller must have pinned the rung env
(bigT especially) BEFORE the first step4 import — this module refuses to be imported
otherwise (`run_rung` does the pinning).
"""
import os
import sys
import warnings
from copy import deepcopy

import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_HA = os.path.join(_REPO, "Code", "HA-Models")
if _HA not in sys.path:
    sys.path.insert(0, _HA)

if os.environ.get("HAFISCAL_HANK_BIGT") != "40":
    raise RuntimeError(
        "ssj_ladder.minimal_cell imported without the rung env pinned "
        "(HAFISCAL_HANK_BIGT must be exported BEFORE the first step4 import; "
        "run via `python -m ssj_ladder.run_rung A0`).")

# LivPrb=1 makes HARK's define_distribution_grid compute a 0/0 pGrid intermediate
# that the neutral measure then discards; the finite-grid assert below is the real gate.
warnings.filterwarnings("ignore", category=RuntimeWarning)

from step4 import jacobians as jac  # noqa: E402
from step4 import hh_setup  # noqa: E402
from step4.common import chdir_fpc  # noqa: E402
from ConsMarkovModel import MarkovConsumerType  # noqa: E402
from HARK.distributions import DiscreteDistributionLabeled  # noqa: E402
from Parameters import return_parameters  # noqa: E402

chdir_fpc()

dx = hh_setup.dx  # trap (2): single-sourced


def _labeled(theta):
    """1-atom [PermShk, TranShk] distribution at psi identically 1."""
    return DiscreteDistributionLabeled(
        pmv=np.array([1.0]), atoms=np.array([[1.0], [float(theta)]]),
        var_names=["PermShk", "TranShk"])


def _per_state(emp_theta, u_theta):
    return [_labeled(emp_theta), _labeled(u_theta)]


def build_cell(model, n_pts, scratch_obj):
    """One A0 cell at joint resolution n_pts. Returns dict of J arrays + SS scalars."""
    assert hh_setup.bigT == model["T"], (hh_setup.bigT, model["T"])
    jac.OUTPUT_OBJ = scratch_obj  # tracked-path hygiene: never HA_Fiscal_Jacs.obj

    wage, tau = model["wage_ss"], model["tau_ss"]
    y_emp = wage * (1.0 - tau)                  # 0.7
    b_u = 0.7 * wage * (1.0 - tau)              # 0.49, the with-UI level
    Pi = np.array([[1.0 - model["EU"], model["EU"]],
                   [model["jf"], 1.0 - model["jf"]]])
    n_m = 2

    init = deepcopy(return_parameters(Parametrization="Baseline",
                                      OutputFor="_Main.py")[2])  # college scaffold
    init.update(
        MrkvArray=[Pi],
        Rfree=[np.ones(n_m) * model["R"]],
        LivPrb=[np.ones(n_m) * model["livprb"]],
        PermGroFac=[np.ones(n_m) * model["gamma"]],
        PermShkStd=[0.0], TranShkStd=[0.0],
        PermShkCount=1, TranShkCount=1,          # trap (1)
        UnempPrb=0.0, IncUnemp=0.0,
        CRRA=model["crra"], T_cycle=1,
        mCount=int(n_pts), mMin=model["a_min_step4"],
        mMax=float(model["a_max"]), mFac=model["m_fac"],
        aXtraCount=int(n_pts), aXtraMax=float(model["a_max"]),
    )

    agent = MarkovConsumerType(**init)
    agent.cycles = 0

    IncDist = [_per_state(y_emp, b_u)]
    dx_lists = {
        "transfers": [_per_state(y_emp + dx, b_u + dx)],
        "wage": [_per_state((wage + dx) * (1.0 - tau), b_u)],
        "tax": [_per_state(wage * (1.0 - (tau + dx)), b_u)],
    }

    base = jac.prepare_type_base(agent, init, model["beta"], IncDist)
    ss = base["agent_SS"]
    assert np.isfinite(np.asarray(ss.dist_mGrid, dtype=float)).all(), \
        "non-finite distribution grid at LivPrb=1"

    out = {"A_ss": float(ss.A_ss), "C_ss": float(ss.C_ss),
           "n_pts": int(n_pts), "T": int(model["T"])}
    name_map = {"transfers": "transfers", "wage": "w", "tax": "tau", "Rfree": "r"}
    for param in ("transfers", "wage", "tax", "Rfree"):
        CJ, AJ, _WJ, _C, _A, _U = jac.compute_type_jacobian_for_param(
            base, IncDist, dx_lists.get(param, IncDist), param)
        o = name_map[param]
        out[f"C_{o}"] = np.asarray(CJ)
        out[f"A_{o}"] = np.asarray(AJ)
    return out


# ---- A1: the real 6-state SAM chain --------------------------------------

def _chain6_row(EU, jf):
    """The legacy 6-state employment chain, ROW-stochastic (HARK MrkvArray).

    Transpose of ge.py's column-stochastic construction at dx=0: from-emp
    E->U1 = EU (= sep*(1-jf)); every unemployed state re-finds at jf; U5
    absorbs the exhausted."""
    j = jf
    return np.array([
        [1.0 - EU, EU, 0., 0., 0., 0.],
        [j, 0., 1. - j, 0., 0., 0.],
        [j, 0., 0., 1. - j, 0., 0.],
        [j, 0., 0., 0., 1. - j, 0.],
        [j, 0., 0., 0., 0., 1. - j],
        [j, 0., 0., 0., 0., 1. - j]])


def _states6(y6):
    return [_labeled(t) for t in y6]


def build_cell_a1(model, n_pts, scratch_obj):
    """One A1 cell: 6-state chain, per-state incomes, the five income
    instruments + r + eta (job_find, via the step4 chain perturbation)."""
    assert hh_setup.bigT == model["T"], (hh_setup.bigT, model["T"])
    jac.OUTPUT_OBJ = scratch_obj

    wage, tau = model["wage_ss"], model["tau_ss"]
    y_emp = wage * (1.0 - tau)
    ue = model["ue_rr"] * wage * (1.0 - tau)      # with-UI level (U1, U2)
    nb = model["nb_rr"] * wage * (1.0 - tau)      # exhausted (U3..U5)
    ext = wage * (1.0 - tau)                      # the UI_extend/UI_rr dx coefficient
    Pi = _chain6_row(model["EU"], model["jf"])
    n_m = 6

    init = deepcopy(return_parameters(Parametrization="Baseline",
                                      OutputFor="_Main.py")[2])
    init.update(
        MrkvArray=[Pi],
        Rfree=[np.ones(n_m) * model["R"]],
        LivPrb=[np.ones(n_m) * model["livprb"]],
        PermGroFac=[np.ones(n_m) * model["gamma"]],
        PermShkStd=[0.0], TranShkStd=[0.0],
        PermShkCount=1, TranShkCount=1,
        UnempPrb=0.0, IncUnemp=0.0,
        CRRA=model["crra"], T_cycle=1,
        mCount=int(n_pts), mMin=model["a_min_step4"],
        mMax=float(model["a_max"]), mFac=model["m_fac"],
        aXtraCount=int(n_pts), aXtraMax=float(model["a_max"]),
    )
    agent = MarkovConsumerType(**init)
    agent.cycles = 0

    base_y = [y_emp, ue, ue, nb, nb, nb]
    IncDist = [_states6(base_y)]
    dx_lists = {
        "transfers": [_states6([v + dx for v in base_y])],
        "wage": [_states6([(wage + dx) * (1.0 - tau), ue, ue, nb, nb, nb])],
        "tax": [_states6([wage * (1.0 - (tau + dx)), ue, ue, nb, nb, nb])],
        "UI_extend": [_states6([y_emp, ue, ue, nb + dx * ext, nb + dx * ext, nb])],
        "UI_rr": [_states6([y_emp, ue + dx * ext, ue + dx * ext, nb, nb, nb])],
    }

    base = jac.prepare_type_base(agent, init, model["beta"], IncDist)
    ss = base["agent_SS"]
    assert np.isfinite(np.asarray(ss.dist_mGrid, dtype=float)).all()

    out = {"A_ss": float(ss.A_ss), "C_ss": float(ss.C_ss),
           "n_pts": int(n_pts), "T": int(model["T"])}
    name_map = {"transfers": "transfers", "wage": "w", "tax": "tau",
                "Rfree": "r", "UI_extend": "UI_extend", "UI_rr": "UI_rr",
                "job_find": "eta"}
    for param in ("transfers", "wage", "tax", "Rfree", "UI_extend",
                  "UI_rr", "job_find"):
        CJ, AJ, _WJ, _C, _A, _U = jac.compute_type_jacobian_for_param(
            base, IncDist, dx_lists.get(param, IncDist), param)
        o = name_map[param]
        out[f"C_{o}"] = np.asarray(CJ)
        out[f"A_{o}"] = np.asarray(AJ)
    return out


# ---- A3 (S-only): psi/theta shocks on the 6-state chain -------------------

def _shock_products(model):
    """Employed slot: the 7x7 [psi, theta*y] product at production stds;
    unemployed slots: the psi MARGINAL re-expressed on the employed 49-point
    support with a constant benefit-level theta row (hh_setup's own
    expansion — calc_transition_matrix allocates ONE rectangular shock array
    for all states, so every state must carry 49 points)."""
    from HARK.distributions import MeanOneLogNormal, combine_indep_dstns
    psi = MeanOneLogNormal(sigma=model["psi_std"]).discretize(model["shk_count"])
    th = MeanOneLogNormal(sigma=model["theta_std"]).discretize(model["shk_count"])
    prod = combine_indep_dstns(psi, th)
    pmv = np.asarray(prod.pmv, float)
    psi_row = np.asarray(prod.atoms[0], float)
    th_row = np.asarray(prod.atoms[1], float)
    return pmv, psi_row, th_row


def _emp_slot(pmv, psi_row, th_row, level):
    return DiscreteDistributionLabeled(
        pmv=pmv.copy(), atoms=np.stack([psi_row, th_row * float(level)]),
        var_names=["PermShk", "TranShk"])


def _unemp_slot(pmv, psi_row, level, psi_on=True):
    prow = psi_row if psi_on else np.ones_like(psi_row)
    return DiscreteDistributionLabeled(
        pmv=pmv.copy(),
        atoms=np.stack([prow, np.full_like(psi_row, float(level))]),
        var_names=["PermShk", "TranShk"])


def build_cell_a3(model, n_pts, scratch_obj, income_scale=1.0):
    """A3, S-only: the A1 chain and instruments with real psi/theta risk
    (production stds; psi kept through unemployment, the p_on=main arm).

    income_scale (rung A7 / G14): multiplies EVERY income flow — base levels
    AND every instrument's income increment — by the given factor, leaving
    the r perturbation (a rate, not a flow) and compile_JAC's divisor
    (hh_setup.dx) untouched, so the returned J's are per unit of the GROSS
    instrument. At 1.0 every expression reduces bit-for-bit to the A3/A4
    cell (float multiplication by 1.0 is exact). This is the structural-
    splurge optimizer: under c_sp = sigma*y the optimizer receives
    (1-sigma) of every flow, and G14's question reduces to whether
    J(scale=1-sigma) == (1-sigma) * J(scale=1)."""
    assert hh_setup.bigT == model["T"], (hh_setup.bigT, model["T"])
    jac.OUTPUT_OBJ = scratch_obj

    s_inc = float(income_scale)
    wage, tau = model["wage_ss"], model["tau_ss"]
    y_emp = s_inc * wage * (1.0 - tau)
    ue = s_inc * model["ue_rr"] * wage * (1.0 - tau)
    nb = s_inc * model["nb_rr"] * wage * (1.0 - tau)
    ext = s_inc * wage * (1.0 - tau)
    Pi = _chain6_row(model["EU"], model["jf"])
    n_m = 6
    pmv, psi_row, th_row = _shock_products(model)
    # the E[psi]/E[1/psi] tripwire (hh_setup's own assert class)
    assert abs(float(np.sum(pmv * psi_row)) - 1.0) <= 1e-9

    init = deepcopy(return_parameters(Parametrization="Baseline",
                                      OutputFor="_Main.py")[2])
    init.update(
        MrkvArray=[Pi],
        Rfree=[np.ones(n_m) * model["R"]],
        LivPrb=[np.ones(n_m) * model["livprb"]],
        PermGroFac=[np.ones(n_m) * model["gamma"]],
        PermShkStd=[model["psi_std"]], TranShkStd=[model["theta_std"]],
        PermShkCount=model["shk_count"], TranShkCount=model["shk_count"],
        UnempPrb=0.0, IncUnemp=0.0,
        CRRA=model["crra"], T_cycle=1,
        mCount=int(n_pts), mMin=model["a_min_step4"],
        mMax=float(model["a_max"]), mFac=model["m_fac"],
        aXtraCount=int(n_pts), aXtraMax=float(model["a_max"]),
    )
    agent = MarkovConsumerType(**init)
    agent.cycles = 0

    def states(emp_level, u12_level, u345_level):
        return [_emp_slot(pmv, psi_row, th_row, emp_level),
                _unemp_slot(pmv, psi_row, u12_level),
                _unemp_slot(pmv, psi_row, u12_level),
                _unemp_slot(pmv, psi_row, u345_level),
                _unemp_slot(pmv, psi_row, u345_level),
                _unemp_slot(pmv, psi_row, u345_level)]

    IncDist = [states(y_emp, ue, nb)]

    # transfers moves EVERY slot by +dx (a level ADD, not a scale) — the
    # employed slot's theta row becomes th*y_emp + dx, hh_setup's own
    # emp1_transfers_dx arithmetic.
    def emp_add(level_add):
        d = _emp_slot(pmv, psi_row, th_row, y_emp)
        d.atoms[1] = d.atoms[1] + level_add
        return d
    dx_i = s_inc * dx   # the income increment per unit gross instrument
    dx_lists = {
        "transfers": [[emp_add(dx_i),
                       _unemp_slot(pmv, psi_row, ue + dx_i),
                       _unemp_slot(pmv, psi_row, ue + dx_i),
                       _unemp_slot(pmv, psi_row, nb + dx_i),
                       _unemp_slot(pmv, psi_row, nb + dx_i),
                       _unemp_slot(pmv, psi_row, nb + dx_i)]],
        "wage": [states(s_inc * (wage + dx) * (1.0 - tau), ue, nb)],
        "tax": [states(s_inc * wage * (1.0 - (tau + dx)), ue, nb)],
        "UI_extend": [[_emp_slot(pmv, psi_row, th_row, y_emp),
                       _unemp_slot(pmv, psi_row, ue),
                       _unemp_slot(pmv, psi_row, ue),
                       _unemp_slot(pmv, psi_row, nb + dx * ext),
                       _unemp_slot(pmv, psi_row, nb + dx * ext),
                       _unemp_slot(pmv, psi_row, nb)]],
        "UI_rr": [[_emp_slot(pmv, psi_row, th_row, y_emp),
                   _unemp_slot(pmv, psi_row, ue + dx * ext),
                   _unemp_slot(pmv, psi_row, ue + dx * ext),
                   _unemp_slot(pmv, psi_row, nb),
                   _unemp_slot(pmv, psi_row, nb),
                   _unemp_slot(pmv, psi_row, nb)]],
    }

    base = jac.prepare_type_base(agent, init, model["beta"], IncDist)
    ss = base["agent_SS"]
    assert np.isfinite(np.asarray(ss.dist_mGrid, dtype=float)).all()

    out = {"A_ss": float(ss.A_ss), "C_ss": float(ss.C_ss),
           "n_pts": int(n_pts), "T": int(model["T"])}
    name_map = {"transfers": "transfers", "wage": "w", "tax": "tau",
                "Rfree": "r", "UI_extend": "UI_extend", "UI_rr": "UI_rr",
                "job_find": "eta"}
    for param in ("transfers", "wage", "tax", "Rfree", "UI_extend",
                  "UI_rr", "job_find"):
        CJ, AJ, _WJ, _C, _A, _U = jac.compute_type_jacobian_for_param(
            base, IncDist, dx_lists.get(param, IncDist), param)
        o = name_map[param]
        out[f"C_{o}"] = np.asarray(CJ)
        out[f"A_{o}"] = np.asarray(AJ)
    return out
