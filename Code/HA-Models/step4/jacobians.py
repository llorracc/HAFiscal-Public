"""Step-4 household fake-news Jacobians (live engine).

The compute core is the frozen monolith's post-rebuild structure (L1
hoist, L1b persistent finite-horizon agent, L3a/L3b compiled fast paths
with certified python fallbacks, diagonal-cumsum fake-news recursion)
with the fixed semantics built in: solves see the intended shocks
(BUG-071, structural via hh_setup's clean construction), the s=0 column
is the direct dated-policy experiment (BUG-072, unconditional here), and
PermGroFac carries the PE education-specific growth (BUG-073, hh_setup)
and the distribution transitions carry it too (BUG-097: bNext divided
by the next state's Gamma in every builder, HAFISCAL_STEP4_TRANMAT_GROWTH).

State count: everything here is sized from the agent's chain
(MrkvArray[0].shape[0]) — 6 employment states, or 2 x 6 under the
earnings phase (hh_setup: [growing 6 | matured 6]; the job_find
perturbation is re-wrapped by hh_setup.perturbed_mrkv). The Jacobians
aggregate over every state, so the GE stage is state-count-agnostic.

THE DATING OF eta (the job_find instrument) — the single statement; every
other site points here.
--------------------------------------------------------------------------
`eta_t` indexes the period a searcher moves INTO: it is the probability of
entering employment AT date t, not of leaving unemployment between t and
t+1. Matches dissolve at the end of a period and form at the beginning of
the next, and households consume AFTER the period's matches are formed —
Ravn & Sterk (2017 JME, 2021 JEEA) and Du (2025), the source the HANK block
follows, state it in one sentence, and `Subfiles/Appendix-HANK.tex` now
states it too (the "Timing" paragraph under Matching). The GE's own
unemployment Jacobian uses the same dating: `ge.py` records the perturbed
push AT row s of column s.

Two consequences, both load-bearing:

  * COLUMN 0 IS PURELY COMPOSITIONAL. The date-0 draw is realized INTO the
    date-0 state, so a change in eta_0 moves no date-0 decision beyond who
    is where: the column is the steady-state distribution pushed once
    through the perturbed transition at UNCHANGED policies. That is what
    the `historical`/`unanticipated` construction below computes. It is not
    a shortcut — the sequence-space toolkit produces exactly this structure
    (`sequence_jacobian/blocks/het_block.py:227, :240, :283` apply the
    exogenous transition BEFORE the period's decision), and a minimal
    HetBlock whose exogenous transition IS a job-finding rate reproduces
    the composition term to 1.9e-10 with the same-date policy term exactly
    zero. Columns s >= 1 DO carry the anticipatory policy response, which
    first enters at row s-1 and which the fake-news recursion then spreads
    over every earlier row.
  * IT HOLDS ONLY BECAUSE eta REACHES THE HOUSEHOLD SOLELY THROUGH THE
    CHAIN. `perturbed_mrkv` touches nothing but MrkvArray, and the
    `job_find` branch below pins IncShkDstn to steady state. If a future
    change gave date-t income a direct dependence on eta_t, column 0 would
    acquire a same-date policy term (measured at 74% of the column in a
    controlled toy) and this comment would be wrong.

HARK is dated the other way — `MrkvArray[t]` is the transition OUT of date
t — so HAFiscal's `MrkvArray[s]` IS the HANK block's eta_{s+1}, the same
object indexed one apart. The bridge is the deliberate one-row shift
`colC[:T-1] = dC[1:]`, giving `_zeroth_direct_column(slot=s)[t] ==
J[t+1, s+1]` — the identity BUG-112 established for income and
`test_g10_fd_oracle.py` now gates for `job_find` too (slots 0/1/2, plus the
cross-column alignment of the flow-budget residual; an eta shock delivers
no cash, so the income flow-budget gate is structurally inapplicable).

Survey that settled this and the sources quoted:
`conclusions_private/2026-09-05_timing-conventions-survey_job-finding-shock-and-column-0.md`.

Output: FromPandemicCode/HA_Fiscal_Jacs.obj — dict with C/A (8
instruments, (300,300) each), C_by_educ/A_by_educ, and the weighted
steady-state aggregates C_ss_weighted/A_ss_weighted. Byte-compatible
with the monolith's default output (L4 birth gate).
"""
import os
import time
from copy import deepcopy

import numpy as np

from . import hh_setup
from .common import FPC_DIR, ensure_paths, fast_backward_mods

ensure_paths()

from ConsMarkovModel import MarkovConsumerType  # noqa: E402

from .hh_setup import bigT, dx, perturbed_mrkv  # noqa: E402

OUTPUT_OBJ = os.path.join(FPC_DIR, "HA_Fiscal_Jacs.obj")

shock_params = ["transfers", "Rfree", "wage", "tax", "job_find", "DiscFac",
                "UI_extend", "UI_rr"]
# Spellings the GE stage consumes (same order):
shock_params_out = ["transfers", "r", "w", "tau", "eta", "DiscFac",
                    "UI_extend", "UI_rr"]

num_educ_types = 3
education_groups = ['dropout', 'highschool', 'college']


def _util_vectors(c_ss, gamma):
    """(u(c_ss), u'(c_ss)) on the distribution grid, CRRA gamma.

    Used by the first-order welfare Jacobians (owner commission
    2026-08-09): J^W is the fake-news machinery with the policy-deviation
    term aggregated against u'(c_ss)-weighted mass and the
    distribution-shift term seeded with u(c_ss) LEVELS (utility
    constants are irrelevant: distribution deviations sum to zero).
    At gamma=0 (u=c, u'=1) J^W collapses to J^C exactly — the built-in
    identity check of the construction."""
    c = np.asarray(c_ss, dtype=float)
    uprime = c ** (-gamma)
    if gamma == 1.0:
        u = np.log(c)
    else:
        u = c ** (1.0 - gamma) / (1.0 - gamma)
    return u, uprime
# Education weights and the beta-atom count are ingested from the
# calibration at run time (dx-units/dead-code audit 2026-08-09: the
# monolith's num_discfacs=7 literal and re-hardcoded weight list were
# silent traps under any non-Baseline parametrization; at Baseline the
# ingested values are bit-identical to the literals).


def prepare_type_base(agent, dict, DiscFac, IncDist):
    """L1 hoist: everything here depends only on (educ-type agent,
    DiscFac, IncDist) — never on the shock param — so it is computed ONCE
    per (educ, beta) and shared across all 8 params: the SS solve, the
    finite-horizon params dict, and the baseline-solved zeroth-column
    agent (its SOLVE is param-independent; only its transition matrices
    vary by param and are rebuilt per param)."""
    agent_SS = deepcopy(agent)
    agent_SS.IncShkDstn = deepcopy(IncDist)
    agent_SS.DiscFac = DiscFac
    agent_SS.compute_steady_state()

    params = deepcopy(dict)
    params["T_cycle"] = bigT
    params["LivPrb"] = params["T_cycle"] * [agent_SS.LivPrb[0]]
    params["PermGroFac"] = params["T_cycle"] * [agent_SS.PermGroFac[0]]
    params["PermShkStd"] = params["T_cycle"] * [agent_SS.PermShkStd[0]]
    params["TranShkStd"] = params["T_cycle"] * [agent_SS.TranShkStd[0]]
    params["Rfree"] = params["T_cycle"] * [agent_SS.Rfree[0]]  # [0]: same time-vary idiom as the neighboring lines
    params["MrkvArray"] = params["T_cycle"] * agent_SS.MrkvArray
    params["DiscFac"] = DiscFac
    params["cycles"] = 1

    Zeroth_col_agent = MarkovConsumerType(**deepcopy(params))
    Zeroth_col_agent.solution_terminal = deepcopy(agent_SS.solution[0])
    Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)
    zeroth_policies = None
    _fbm = fast_backward_mods()
    if _fbm is not None:
        Zeroth_col_agent.neutral_measure = True
        Zeroth_col_agent.define_distribution_grid()
        zeroth_policies = _fbm[0].fast_backward(Zeroth_col_agent)
    if zeroth_policies is None:
        Zeroth_col_agent.solve()

    # BUG-075 fix — the GHOST RUN (canonical ABRS/SSJ): the UNSHOCKED
    # dated chain, against which every shocked chain is differenced so
    # that the backward chain's convergence drift cancels. The historical
    # construction differenced against the STATIC steady state; on
    # near-unit-root cells (the GIC-cap atoms, contraction modulus ≈ 1)
    # the infinite-horizon solve's residual keeps converging along the
    # 300-period dated chain, and (chain − SS)/dx turns that drift into
    # O(0.1) spurious Jacobian entries wherever the ergodic mass is
    # dense (first materialized under the PE grids; measured drift
    # ~1.1e-4 in-grid at the College cap cell). The ghost = the zeroth
    # agent's baseline chain, already solved above; here its transition
    # matrices are built once and consumed immediately into the vectors
    # compile_JAC and the direct column need (never stored as (T,N,N)).
    T_ = params["T_cycle"]
    # transition matrices always build under the NEUTRAL (Harmenberg)
    # shock family, mirroring every per-param chain (solve with the raw
    # dstns, tranmat with agent_SS.IncShkDstn).
    _ghost_dstn = T_ * deepcopy(agent_SS.IncShkDstn)
    if zeroth_policies is not None:
        ghost_c = zeroth_policies[0].reshape(T_, -1).copy()
        ghost_a = zeroth_policies[1].reshape(T_, -1).copy()
        ghost_tm = _fbm[1].finite_tranmat_from_policies(
            Zeroth_col_agent, _ghost_dstn,
            zeroth_policies[0], zeroth_policies[1])
    else:
        ghost_tm = None
    if ghost_tm is None:
        # certified python path (also the fallback when the kernel
        # tranmat builder declines the structure)
        if not getattr(Zeroth_col_agent, "solution", None):
            _cur_dstn = Zeroth_col_agent.IncShkDstn
            Zeroth_col_agent.solve()
            Zeroth_col_agent.IncShkDstn = _cur_dstn
        Zeroth_col_agent.IncShkDstn = _ghost_dstn
        Zeroth_col_agent.neutral_measure = True
        Zeroth_col_agent.define_distribution_grid()
        Zeroth_col_agent.calc_transition_matrix()
        ghost_tm = list(np.asarray(Zeroth_col_agent.tran_matrix))
        ghost_c = np.array([np.asarray(Zeroth_col_agent.cPol_Grid[t]).flatten()
                            for t in range(T_)])
        ghost_a = np.array([np.asarray(Zeroth_col_agent.aPol_Grid[t]).flatten()
                            for t in range(T_)])

    c_ss_flat_ = np.asarray(agent_SS.cPol_Grid).flatten()
    a_ss_flat_ = np.asarray(agent_SS.aPol_Grid).flatten()
    D_ss_ = agent_SS.vec_erg_dstn
    tranmat_ss_ = agent_SS.tran_matrix

    # curlyY ghosts, aligned like c_t/a_t (index T = the SS row)
    ghost_c_t = np.empty((T_ + 1, ghost_c.shape[1]))
    ghost_c_t[:T_] = ghost_c
    ghost_c_t[T_] = c_ss_flat_
    ghost_a_t = np.empty((T_ + 1, ghost_a.shape[1]))
    ghost_a_t[:T_] = ghost_a
    ghost_a_t[T_] = a_ss_flat_
    # curlyD ghost pushes: ghost_tm[t]·D_ss, index T = Λ_ss·D_ss
    ghost_push = np.empty((T_ + 1,) + tuple(np.shape(np.dot(tranmat_ss_, D_ss_))))
    for t in range(T_):
        ghost_push[t] = np.dot(ghost_tm[t], D_ss_)
    ghost_push[T_] = np.dot(tranmat_ss_, D_ss_)
    # direct-column ghost aggregates (the unshocked twin of the BUG-072
    # experiment, same forward-iteration convention). The distribution
    # chain is kept so the WELFARE ghost aggregate can be evaluated
    # lazily at call-time CRRA (keeps the gamma=0 identity J_W == J_C
    # exact even under test-harness gamma mutation).
    gC = np.zeros(T_)
    gA = np.zeros(T_)
    ghost_d = np.zeros((T_, ghost_c.shape[1]))
    # UNANTICIPATED-column twin (BUG-112). compile_JAC's zeroth-column block
    # runs a DIFFERENT forward iteration from the one above: it pushes first
    # and measures after, at the STATIC SS policies. Its unshocked twin has to
    # match that convention exactly or the subtraction does not cancel, so it
    # is accumulated here — same loop, same transition matrices, one step out
    # of phase and on c_ss/a_ss instead of the dated policies.
    gC0 = np.zeros(T_)
    gA0 = np.zeros(T_)
    ghost_d0 = np.zeros((T_, ghost_c.shape[1]))
    d_ = D_ss_
    for t in range(T_):
        ghost_d[t] = np.asarray(d_).flatten()
        gC[t] = np.dot(ghost_c[t], d_)[0]
        gA[t] = np.dot(ghost_a[t], d_)[0]
        d_ = np.dot(ghost_tm[t], d_)
        ghost_d0[t] = np.asarray(d_).flatten()
        gC0[t] = np.dot(c_ss_flat_, d_)[0]
        gA0[t] = np.dot(a_ss_flat_, d_)[0]
    del ghost_tm  # (T,N,N) — not kept

    ghost = {"c_t": ghost_c_t, "a_t": ghost_a_t, "push": ghost_push,
             "C_pre": gC, "A_pre": gA, "c": ghost_c, "d": ghost_d,
             "C0": gC0, "A0": gA0, "d0": ghost_d0}

    # L1b: the finite-horizon agent's CONSTRUCTION is also param-independent
    # (the constructor rebuilds 300 income dstns, ~1.6 s) — construct once,
    # snapshot the fields the per-param branches rebind or mutate in place
    # (time_inv/time_vary via del_from_time_inv/add_to_time_vary), and
    # restore per param before applying that param's perturbation.
    FinHorizonAgent = MarkovConsumerType(**deepcopy(params))
    FinHorizonAgent.solution_terminal = deepcopy(agent_SS.solution[0])
    fh_snap = (list(FinHorizonAgent.time_inv), list(FinHorizonAgent.time_vary),
               FinHorizonAgent.MrkvArray, FinHorizonAgent.Rfree,
               FinHorizonAgent.DiscFac)

    return {"agent": agent, "agent_SS": agent_SS, "params": params,
            "Zeroth_col_agent": Zeroth_col_agent,
            "zeroth_policies": zeroth_policies,
            "FinHorizonAgent": FinHorizonAgent, "fh_snap": fh_snap,
            "DiscFac": DiscFac, "ghost": ghost}


def compute_type_jacobian(agent, dict, DiscFac, IncDist, IncDist_dx, param):
    """Legacy single-call API: prepare + one param."""
    base = prepare_type_base(agent, dict, DiscFac, IncDist)
    return compute_type_jacobian_for_param(base, IncDist, IncDist_dx, param)


def _zeroth_direct_column(base, IncDist, IncDist_dx, param, agent_inc_dx, slot=0):
    """BUG-072 fix (unconditional in the live engine): the TRUE direct
    s=0 column — solve WITH the slot-0 perturbation (dated policies),
    dated transitions, and aggregation under the pipeline convention
    J[t,0] = direct_pre[t+1]. The historical baseline-solve column
    (which omitted the date-0 behavioral response) lives only in the
    frozen monolith's QE-fidelity arm. Columns s>=1 are unaffected.

    `slot` (G10, 2026-08-31): which DATE carries the perturbation. The production path always passes
    0, and every expression below reduces to the original when slot == 0 (a 0-length prefix list),
    so the live column is byte-identical. slot > 0 makes this a finite-difference ORACLE for an
    arbitrary Jacobian column: run the dated ±dx experiment with the shock at date s and difference
    it, then compare against the fake-news assembly's J[:, s]. That is the strongest available
    statement that the Jacobians say what the PE machinery says these households do, and it is the
    same arithmetic the s=0 column has always used — only the date moves."""
    agent = base["agent"]
    agent_SS = base["agent_SS"]
    DiscFac = base["DiscFac"]
    params = deepcopy(base["params"])
    T = params["T_cycle"]
    dxv = dx  # single-sourced (dx-units audit R1): all perturbations = hh_setup.dx

    fd = MarkovConsumerType(**params)
    fd.dist_pGrid = T * [np.array([1])]
    fd.solution_terminal = deepcopy(agent_SS.solution[0])
    fd.del_from_time_inv("IncShkDstn")
    fd.IncShkDstn = T * deepcopy(IncDist)
    fd.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")
    if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr"):
        fd.IncShkDstn = (slot * deepcopy(IncDist) + deepcopy(IncDist_dx)
                         + (T - 1 - slot) * deepcopy(IncDist))
    elif param == "Rfree":
        fd.del_from_time_inv("Rfree")
        fd.add_to_time_vary("Rfree")
        fd.Rfree = (slot * [agent.Rfree[0]] + [agent.Rfree[0] + dxv]
                    + (T - 1 - slot) * [agent.Rfree[0]])
    elif param == "job_find":
        # BUG-076: perturb THIS education group's own chain (base None
        # under the legacy shared-chain escape — byte-identical path);
        # re-wrapped by the earnings phase when the agent carries one.
        # Dating: MrkvArray[slot] carries date `slot` INTO date slot+1, so this
        # dated experiment is the eta_{slot+1} column read a row early — see
        # "THE DATING OF eta" in the module docstring.  Gated:
        # test_g10_fd_oracle.py::test_job_find_obeys_the_same_index_identity_as_income.
        fd.MrkvArray = (slot * agent.MrkvArray + [perturbed_mrkv(agent, dxv)]
                        + (T - 1 - slot) * agent.MrkvArray)
    elif param == "DiscFac":
        fd.del_from_time_inv("DiscFac")
        fd.add_to_time_vary("DiscFac")
        fd.DiscFac = (slot * [DiscFac] + [DiscFac + dxv]
                      + (T - 1 - slot) * [DiscFac])
    # Kernel-routed (Z2 of plan 20260809-0936h) with certified python
    # fallback preserved.
    _fbm_z = fast_backward_mods()
    _solve_dstn_z = fd.IncShkDstn
    if _fbm_z is None:
        fd.solve()

    if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr"):
        fd.IncShkDstn = (slot * deepcopy(agent_SS.IncShkDstn)
                         + deepcopy(agent_inc_dx.IncShkDstn)
                         + (T - 1 - slot) * deepcopy(agent_SS.IncShkDstn))
    else:
        fd.IncShkDstn = T * deepcopy(agent_SS.IncShkDstn)
    fd.neutral_measure = True
    fd.define_distribution_grid()
    _done_fast = False
    if _fbm_z is not None:
        _pol_z = _fbm_z[0].fast_backward(fd, shk_dstn=_solve_dstn_z)
        _tm_z = (_fbm_z[1].finite_tranmat_from_policies(
                     fd, fd.IncShkDstn, _pol_z[0], _pol_z[1])
                 if _pol_z is not None else None)
        if _tm_z is not None:
            tran_t = np.array(_tm_z)
            c_t = _pol_z[0].reshape(T, -1)
            a_t = _pol_z[1].reshape(T, -1)
            _done_fast = True
        else:
            print("[fast_backward] zeroth-direct fallback to certified python path")
            _neutral_z = fd.IncShkDstn
            fd.IncShkDstn = _solve_dstn_z
            fd.solve()
            fd.IncShkDstn = _neutral_z
    if not _done_fast:
        fd.calc_transition_matrix()
        tran_t = np.array(fd.tran_matrix)
        c_t = np.array([np.asarray(fd.cPol_Grid[t]).flatten() for t in range(T)])
        a_t = np.array([np.asarray(fd.aPol_Grid[t]).flatten() for t in range(T)])
    # Welfare mirror: exact utility flow along the dated path (u at the
    # DATED policies — agrees with the linearized u'(c_ss)·dc form to
    # O(dx²) and captures the composition shift through the dated dstn).
    gamma = agent_SS.CRRA

    C_pre = np.zeros(T)
    A_pre = np.zeros(T)
    W_pre = np.zeros(T)
    d = agent_SS.vec_erg_dstn
    for t in range(T):
        C_pre[t] = np.dot(c_t[t], d)[0]
        A_pre[t] = np.dot(a_t[t], d)[0]
        W_pre[t] = np.dot(_util_vectors(c_t[t], gamma)[0], d)[0]
        d = np.dot(tran_t[t], d)
    # BUG-075 fix: difference against the GHOST twin (the unshocked
    # dated chain's aggregates, precomputed per cell), not the static
    # SS — the backward chain's convergence drift cancels exactly.
    # The welfare ghost is evaluated at CALL-time CRRA from the stored
    # ghost policies/distribution chain (gamma=0 identity preserved).
    g = base["ghost"]
    gW_pre = np.array([np.dot(_util_vectors(g["c"][t], gamma)[0],
                              g["d"][t]) for t in range(T)])
    dC = (C_pre - g["C_pre"]) / dxv
    dA = (A_pre - g["A_pre"]) / dxv
    dW = (W_pre - gW_pre) / dxv
    colC = np.empty(T); colC[:T - 1] = dC[1:]; colC[T - 1] = 0.0
    colA = np.empty(T); colA[:T - 1] = dA[1:]; colA[T - 1] = 0.0
    colW = np.empty(T); colW[:T - 1] = dW[1:]; colW[T - 1] = 0.0
    return colC, colA, colW


def compute_type_jacobian_for_param(base, IncDist, IncDist_dx, param):
    # dx is the module-level hh_setup.dx (single-sourced; audit R1) —
    # the same value builds the income dstns and divides compile_JAC.
    agent = base["agent"]
    agent_SS = base["agent_SS"]
    DiscFac = base["DiscFac"]

    C_ss_ThisType = deepcopy(agent_SS.C_ss)
    A_ss_ThisType = deepcopy(agent_SS.A_ss)

    ##################################################################################################
    # Finite Horizon

    params = deepcopy(base["params"])  # per-param isolation

    # L1b: persistent finite-horizon agent — restore the fresh-construction
    # state the branches below perturb, then proceed exactly as before.
    FinHorizonAgent = base["FinHorizonAgent"]
    _ti0, _tv0, _mrkv0, _rfree0, _discfac0 = base["fh_snap"]
    FinHorizonAgent.time_inv = list(_ti0)
    FinHorizonAgent.time_vary = list(_tv0)
    FinHorizonAgent.MrkvArray = _mrkv0
    FinHorizonAgent.Rfree = _rfree0
    FinHorizonAgent.DiscFac = _discfac0
    FinHorizonAgent.neutral_measure = False
    FinHorizonAgent.dist_pGrid = params["T_cycle"] * [np.array([1])]
    FinHorizonAgent.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)

    if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr"):
        agent_inc_dx = deepcopy(agent)
        agent_inc_dx.DiscFac = DiscFac
        agent_inc_dx.IncShkDstn = deepcopy(IncDist_dx)
        agent_inc_dx.neutral_measure = True
        agent_inc_dx.harmenberg_income_process()
        FinHorizonAgent.del_from_time_inv(
            "IncShkDstn",
        )
        FinHorizonAgent.IncShkDstn = (params["T_cycle"] - 1) * deepcopy(IncDist) + deepcopy(IncDist_dx)
        FinHorizonAgent.add_to_time_vary("IncShkDstn", "PermShkDstn", "TranShkDstn")

    elif param == "job_find":
        # BUG-076: per-group perturbation; Mrkv_dx is reused by the
        # Zeroth_col_agent branch below for the SAME agent/educ. On the
        # agent's own state space (phase-wrapped when the agent carries one).
        # The perturbation touches the CHAIN ONLY — IncShkDstn is pinned to
        # steady state below.  That is the precondition under which column 0
        # is purely compositional; see "THE DATING OF eta" in the module
        # docstring.
        Mrkv_dx = perturbed_mrkv(agent, dx)
        FinHorizonAgent.MrkvArray = (params["T_cycle"] - 1) * agent.MrkvArray + [Mrkv_dx]
    elif param == "Rfree":
        FinHorizonAgent.del_from_time_inv(
            "Rfree",
        )  # Rfree varies over time for this perturbation
        FinHorizonAgent.add_to_time_vary("Rfree")
        FinHorizonAgent.Rfree = (params["T_cycle"] - 1) * [agent.Rfree[0]] + [agent.Rfree[0] + dx] + [agent.Rfree[0]]  # [0]: per-state array per period (HARK 0.17 time-vary)
    elif param == "DiscFac":
        FinHorizonAgent.del_from_time_inv(
            "DiscFac",
        )
        FinHorizonAgent.add_to_time_vary("DiscFac")
        FinHorizonAgent.DiscFac = (params["T_cycle"] - 1) * [DiscFac] + [DiscFac + dx]

    _fbm = fast_backward_mods()
    if _fbm is not None:
        _solve_dstn = FinHorizonAgent.IncShkDstn  # raw solve-arm dstns (dx slot placement)
    else:
        FinHorizonAgent.solve()

    if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr"):
        FinHorizonAgent.IncShkDstn = (params["T_cycle"] - 1) * deepcopy(agent_SS.IncShkDstn) + deepcopy(agent_inc_dx.IncShkDstn)
    else:
        FinHorizonAgent.IncShkDstn = params["T_cycle"] * deepcopy(agent_SS.IncShkDstn)

    # Calculate Transition Matrices
    FinHorizonAgent.neutral_measure = True
    FinHorizonAgent.define_distribution_grid()
    if _fbm is not None:
        _pol = _fbm[0].fast_backward(FinHorizonAgent, shk_dstn=_solve_dstn)
        _tm = (_fbm[1].finite_tranmat_from_policies(
                   FinHorizonAgent, FinHorizonAgent.IncShkDstn, _pol[0], _pol[1])
               if _pol is not None else None)
        if _tm is None:
            print("[fast_backward] FH fallback to certified python path")
            _neutral = FinHorizonAgent.IncShkDstn
            FinHorizonAgent.IncShkDstn = _solve_dstn
            FinHorizonAgent.solve()
            FinHorizonAgent.IncShkDstn = _neutral
            FinHorizonAgent.calc_transition_matrix()
        else:
            FinHorizonAgent.cPol_Grid = _pol[0]
            FinHorizonAgent.aPol_Grid = _pol[1]
            FinHorizonAgent.tran_matrix = _tm
    else:
        FinHorizonAgent.calc_transition_matrix()

    ##################################################################################################
    # period zero shock agent — SOLVED once in prepare_type_base (the
    # solve is baseline for every param). Reset the perturbable fields,
    # then rebuild this param's transition matrices.

    Zeroth_col_agent = base["Zeroth_col_agent"]
    Zeroth_col_agent.MrkvArray = params["MrkvArray"]
    Zeroth_col_agent.Rfree = params["Rfree"]
    Zeroth_col_agent.DiscFac = params["DiscFac"]

    if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr"):
        Zeroth_col_agent.IncShkDstn = deepcopy(agent_inc_dx.IncShkDstn) + (params["T_cycle"]) * deepcopy(agent_SS.IncShkDstn)
    elif param == "job_find":
        # Column 0, the eta instrument: the perturbed transition in slot 0 with the
        # agent solved at BASELINE (unanticipating).  Deliberate, not an omission —
        # the date-0 draw is realized into the date-0 state, so nothing at date 0
        # responds to eta_0 beyond composition.  See "THE DATING OF eta" in the
        # module docstring for the literature and the toolkit evidence.
        Zeroth_col_agent.MrkvArray = [Mrkv_dx] + (params["T_cycle"] - 1) * agent.MrkvArray
    elif param == "Rfree":
        Zeroth_col_agent.Rfree = [agent.Rfree[0] + dx] + (params["T_cycle"] - 1) * [agent.Rfree[0]]  # [0]: per-state array per period (HARK 0.17 time-vary)
    elif param == "DiscFac":
        Zeroth_col_agent.DiscFac = [DiscFac + dx] + (params["T_cycle"] - 1) * [DiscFac]

    if param in ("DiscFac", "Rfree", "job_find"):
        Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(agent_SS.IncShkDstn)

    Zeroth_col_agent.neutral_measure = True
    Zeroth_col_agent.define_distribution_grid()
    if fast_backward_mods() is not None and base.get("zeroth_policies") is not None:
        _zc, _za = base["zeroth_policies"]
        _tmz = fast_backward_mods()[1].finite_tranmat_from_policies(
            Zeroth_col_agent, Zeroth_col_agent.IncShkDstn, _zc, _za)
        if _tmz is None:
            print("[fast_backward] zeroth fallback to certified python path")
            if not getattr(Zeroth_col_agent, "solution", None):
                _cur = Zeroth_col_agent.IncShkDstn
                Zeroth_col_agent.IncShkDstn = params["T_cycle"] * deepcopy(IncDist)
                Zeroth_col_agent.solve()
                Zeroth_col_agent.IncShkDstn = _cur
            Zeroth_col_agent.calc_transition_matrix()
        else:
            Zeroth_col_agent.tran_matrix = _tmz
    else:
        Zeroth_col_agent.calc_transition_matrix()

    #################################################################################################
    # calculate Jacobian

    D_ss = agent_SS.vec_erg_dstn

    c_ss = agent_SS.cPol_Grid.flatten()
    a_ss = agent_SS.aPol_Grid.flatten()

    c_t_unflat = FinHorizonAgent.cPol_Grid
    a_t_unflat = FinHorizonAgent.aPol_Grid

    A_ss = agent_SS.A_ss
    C_ss = agent_SS.C_ss

    transition_matrices = FinHorizonAgent.tran_matrix

    # Sized from the agent's chain, never the literal 6: under the earnings
    # phase the block has 2 x 6 states (a fixed 6 here would raise on the
    # flatten — the same silent-truncation family the PE wiring met).
    n_m = len(agent_SS.MrkvArray[0])
    c_t_flat = np.zeros((params["T_cycle"], int(params["mCount"] * n_m)))
    a_t_flat = np.zeros((params["T_cycle"], int(params["mCount"] * n_m)))

    for t in range(params["T_cycle"]):
        c_t_flat[t] = c_t_unflat[t].flatten()
        a_t_flat[t] = a_t_unflat[t].flatten()

    tranmat_ss = agent_SS.tran_matrix

    # L1b: preallocate instead of np.insert — the insert materialized a
    # second (T+1, N, N) copy (~1.2 GB at mCount*states=1200) per param.
    tranmat_t = np.empty((params["T_cycle"] + 1,) + np.shape(tranmat_ss),
                         dtype=np.asarray(tranmat_ss).dtype)
    tranmat_t[:params["T_cycle"]] = transition_matrices
    tranmat_t[params["T_cycle"]] = tranmat_ss

    c_t = np.empty((params["T_cycle"] + 1, c_t_flat.shape[1]), dtype=c_t_flat.dtype)
    c_t[:params["T_cycle"]] = c_t_flat
    c_t[params["T_cycle"]] = c_ss
    a_t = np.empty((params["T_cycle"] + 1, a_t_flat.shape[1]), dtype=a_t_flat.dtype)
    a_t[:params["T_cycle"]] = a_t_flat
    a_t[params["T_cycle"]] = a_ss

    # First-order welfare weights on the distribution grid (owner
    # commission 2026-08-09): CRRA from the calibration; gamma=0 makes
    # J_W collapse to J_C (the construction's identity check).
    gamma = agent_SS.CRRA
    u_ss_vec, uprime_ss = _util_vectors(c_ss, gamma)

    _g = base["ghost"]
    _zcol = _zeroth_column_mode()
    CJAC_perfect, AJAC_perfect, WJAC_perfect = compile_JAC(
        a_ss, c_ss, a_t, c_t, tranmat_ss, tranmat_t, D_ss, C_ss, A_ss,
        Zeroth_col_agent, bigT, u_ss_vec=u_ss_vec, uprime_ss=uprime_ss,
        ghost_c_t=_g["c_t"], ghost_a_t=_g["a_t"], ghost_push=_g["push"],
        ghost_zero=({"C": _g["C0"], "A": _g["A0"], "d": _g["d0"]}
                    if _zcol == "unanticipated" else None))

    # BUG-072 fix: the s=0 column is the direct dated-policy experiment.
    #
    # HAFISCAL_STEP4_ZEROTH_COLUMN (2026-08-31, measurement only, default
    # `bug072` = unchanged) exists because BUG-072's replacement FAILS the
    # household flow-budget identity that compile_JAC's own construction passes.
    # With rho = R*LivPrb, a correct column shows the cash on its delivery row and
    # exactly zero elsewhere. Measured at bigT=80, transfers, college mid-beta:
    #
    #   compile_JAC's historical column 0 : +0.9958 at row 0, 0 elsewhere   <- the
    #                                       same cash every other column delivers
    #   BUG-072's replacement             : +0.9128 at row 0, 0 elsewhere   <- short
    #                                       by 0.083, and it duplicates column 1
    #                                       shifted one row (7.9e-12)
    #
    # Every column must deliver the SAME cash -- the policy is identical, only its
    # date differs -- so this says the override installs a date-1 anticipated
    # experiment where the unanticipated date-0 column belongs. BUG-072 is an
    # adopted, owner-ruled fix, so nothing is changed here: `historical` is a
    # measurement arm for the re-examination, not a proposed default.
    if _zcol == "bug072":
        _inc_dx = agent_inc_dx if param in ("transfers", "wage", "tax", "UI_extend", "UI_rr") else None
        _colC, _colA, _colW = _zeroth_direct_column(base, IncDist, IncDist_dx, param, _inc_dx)
        CJAC_perfect.T[0] = _colC
        AJAC_perfect.T[0] = _colA
        WJAC_perfect.T[0] = _colW
    # `historical` / `unanticipated`: keep compile_JAC's own column, which the
    # ghost_zero argument above has already built in the requested convention.

    Uprime_ss_cell = np.dot(uprime_ss, np.asarray(D_ss).reshape(-1, 1))[0]
    return (CJAC_perfect, AJAC_perfect, WJAC_perfect,
            C_ss_ThisType, A_ss_ThisType, Uprime_ss_cell)


##################################################################################################

def _fakenews_mode():
    """Which fake-news assembly to use (BUG-110).

    `legacy` (default) reproduces the pre-fix assembly byte for byte.
    `fixed` applies the three corrections derived in the bug record.
    """
    mode = os.environ.get("HAFISCAL_STEP4_FAKENEWS_INDEX", "legacy").strip().lower()
    if mode not in ("fixed", "legacy"):
        raise ValueError(
            f"HAFISCAL_STEP4_FAKENEWS_INDEX={mode!r}; expected 'fixed' or 'legacy'")
    return mode


def _zeroth_column_mode():
    """Which construction supplies column 0 of the household Jacobian (BUG-112).

    Column 0 is the response to a transfer that arrives at date 0 with NO prior
    announcement. The three arms differ in what they treat as the unshocked
    baseline, and only one of them delivers, at t = 0, the same cash every other
    column delivers on its own delivery row:

      `bug072`        (reproduction reference; the default until 2026-09-01) the dated
                      slot-0 experiment, packaged with
                      an up-shift. That experiment perturbs IncShkDstn[0], which
                      is the income realised at date 1, so it is the ANTICIPATED
                      date-1 column; the up-shift then deletes its announcement
                      row. Measured: 0.8397 of cash where every other column
                      delivers 0.9956, the deficit being exactly rho times the
                      announcement-date dissaving it dropped.
      `historical`    compile_JAC's own column -- right in concept (unperturbed
                      policies, perturbed date-0 income, measured after the push)
                      but differenced against the STATIC steady state, so any
                      non-stationarity of the unshocked chain on the distribution
                      grid enters divided by dx. Exact at the low-beta atoms and
                      badly wrong at the high-beta ones.
      `unanticipated` the same construction differenced against its own unshocked
                      twin (the BUG-075 correction, which this block never got).
                      Passes the flow budget at every atom.

    DEFAULT FLIPPED to `unanticipated` 2026-09-01 by the owner's rule ("the baseline
    HANK with multiplier mechanisms turned off should reproduce the results from the
    partial equilibrium model"), executed as a measurement: the PE-reproduction gate
    (ssj_ladder/pe_reproduction.py; rerun_logs/pe_reproduction_20260901/) shows the
    corrected arms ~2x closer to the PE non-AD check response in level and shape, and
    per booked dollar the shipped column spends 0.7013 where the PE spends 0.8435
    (the package: 0.8320, the gap attributed to the derived survivor-weight wedge plus
    two measured experiment-design differences). `bug072` stays as the reproduction
    reference arm.
    """
    mode = os.environ.get("HAFISCAL_STEP4_ZEROTH_COLUMN", "unanticipated").strip().lower()
    if mode not in ("bug072", "historical", "unanticipated"):
        raise ValueError(
            f"HAFISCAL_STEP4_ZEROTH_COLUMN={mode!r}; "
            "expected 'bug072', 'historical' or 'unanticipated'")
    return mode


def compile_JAC(a_ss, c_ss, a_t, c_t, tranmat_ss, tranmat_t, D_ss, C_ss, A_ss,
                Zeroth_col_agent, bigT, u_ss_vec=None, uprime_ss=None,
                ghost_c_t=None, ghost_a_t=None, ghost_push=None,
                ghost_zero=None):
    """Fake-news assembly. When (u_ss_vec, uprime_ss) are supplied, a
    first-order welfare Jacobian J_W is assembled ALONGSIDE J_C/J_A by
    the same recursions — the C/A lines below are byte-untouched; every
    W line is an adjacent mirror with the substitutions (c_ss-seed →
    u(c_ss)-seed) on the distribution side and (D_ss → u'(c_ss)⊙D_ss)
    on the policy-deviation side."""
    T = bigT
    do_W = u_ss_vec is not None

    # Expectation vectors
    exp_vecs_a_e = []
    exp_vec_a_e = a_ss

    exp_vecs_c_e = []
    exp_vec_c_e = c_ss

    if do_W:
        exp_vecs_u_e = []
        exp_vec_u_e = u_ss_vec

    for i in range(T):
        exp_vecs_a_e.append(exp_vec_a_e)
        exp_vec_a_e = np.dot(tranmat_ss.T, exp_vec_a_e)

        exp_vecs_c_e.append(exp_vec_c_e)
        exp_vec_c_e = np.dot(tranmat_ss.T, exp_vec_c_e)

        if do_W:
            exp_vecs_u_e.append(exp_vec_u_e)
            exp_vec_u_e = np.dot(tranmat_ss.T, exp_vec_u_e)

    exp_vecs_a_e = np.array(exp_vecs_a_e)
    exp_vecs_c_e = np.array(exp_vecs_c_e)
    if do_W:
        exp_vecs_u_e = np.array(exp_vecs_u_e)
        D_w = uprime_ss.reshape(-1, 1) * np.asarray(D_ss).reshape(-1, 1)

    # BUG-075 fix: deviations are taken against the GHOST (unshocked
    # dated) chain when provided, so the backward chain's convergence
    # drift cancels; the historical SS-differencing survives only for
    # ghost-less callers (none in the package).
    # BUG-110: which chain index carries curlyY_s / curlyD_s.
    #
    # The dated chain is [chain[0] .. chain[T-1], SS] (length T+1) and the
    # perturbation sits at chain index T-1.  curlyY_s is the response to news of
    # a shock s periods AHEAD, so it lives at chain index (T-1) - s:
    #
    #     s = 0  -> index T-1   the shock period itself (impact)
    #     s = 1  -> index T-2   one period of anticipation
    #
    # `T - i` instead reads the appended STEADY-STATE row at s = 0 -- so
    # curlyY_0 = curlyD_0 = 0 identically -- and hands every later s the value
    # belonging to s-1, while chain index 0 is never read at all.  The whole
    # fake-news matrix is then shifted one column, and because the recursion
    # J[t,s] = J[t-1,s-1] + F[t,s] runs down diagonals, every column s >= 1
    # comes out carrying the date-(s-1) experiment.  Column 0 is exempt only
    # because it is overwritten below by the BUG-072 direct construction, which
    # is why this survived: the one column ever checked bypasses the assembly.
    _mode = _fakenews_mode()
    # curlyY keeps the T base in BOTH arms.  Under the pipeline's row convention
    # (J[t,s] = dC_s[t+1], so row 0 is DATE 1) the policy channel in row 0 is the
    # deviation one period BEFORE the shock, i.e. curlyY_{s-1} -- and `a_t[T-i]`
    # is exactly that array, with 0 at s=0 because the shock has already passed.
    # curlyD moves to the T-1 base under `fixed`: it is the one-step distribution
    # response to news s periods ahead, which lives at chain index (T-1)-s.
    _idxD = T - 1 if _mode == "fixed" else T

    da0_s = []
    dc0_s = []

    for i in range(T):
        if ghost_a_t is not None:
            da0_s.append(a_t[T - i] - ghost_a_t[T - i])
            dc0_s.append(c_t[T - i] - ghost_c_t[T - i])
        else:
            da0_s.append(a_t[T - i] - a_ss)
            dc0_s.append(c_t[T - i] - c_ss)

    da0_s = np.array(da0_s)
    dc0_s = np.array(dc0_s)

    dA0_s = []
    dC0_s = []
    dW0_s = []

    for i in range(T):
        dA0_s.append(np.dot(da0_s[i], D_ss))
        dC0_s.append(np.dot(dc0_s[i], D_ss))
        if do_W:
            dW0_s.append(np.dot(dc0_s[i], D_w))  # u'(c_ss)-valued dc

    dA0_s = np.array(dA0_s)
    A_curl_s = dA0_s / dx

    dC0_s = np.array(dC0_s)
    C_curl_s = dC0_s / dx

    if do_W:
        dW0_s = np.array(dW0_s)
        W_curl_s = dW0_s / dx

    # Lane A: identical per-element arithmetic to the historical two-loop
    # form ((tranmat_t - tranmat_ss) then @ D_ss), WITHOUT materializing
    # the (T, N, N) dlambda0_s array it fed.
    dD0_s = []

    for i in range(T):
        if ghost_push is not None:
            dD0_s.append(np.dot(tranmat_t[_idxD - i], D_ss) - ghost_push[_idxD - i])
        else:
            dD0_s.append(np.dot(tranmat_t[_idxD - i] - tranmat_ss, D_ss))

    dD0_s = np.array(dD0_s)
    D_curl_s = dD0_s / dx

    Curl_F_A = np.zeros((T, T))
    Curl_F_C = np.zeros((T, T))

    Curl_F_A[0] = A_curl_s.T[0]
    Curl_F_C[0] = C_curl_s.T[0]
    # (row 0 gains its distribution term below, once D_curl_mat exists)

    # Lane A: the historical (T-1)xT python loop of scalar np.dot calls
    # is ONE matrix product: Curl_F[i+1, j] = exp_vecs[i] . D_curl_s[j].
    D_curl_mat = D_curl_s.reshape(T, -1)              # (T, N)
    # BUG-110.  Row t of F is DATE t+1 under the pipeline's convention.
    #
    #   t >= 1 : by then the recursion already carries the policy history, so the
    #            incremental term is purely distributional -- curlyE_t . curlyD_s.
    #            `legacy` used curlyE_{t-1}, one date too early.
    #   t == 0 : date 1 has BOTH channels -- the policy deviation one period
    #            before the shock (curlyY_{s-1}, already in Curl_F[0]) and the
    #            distribution after one step (curlyE_0 . curlyD_s).  `legacy`
    #            carried only the first, so every column lost its row-0
    #            distribution term.
    _erow = slice(1, T) if _mode == "fixed" else slice(0, T - 1)
    Curl_F_A[1:, :] = exp_vecs_a_e.reshape(T, -1)[_erow] @ D_curl_mat.T
    Curl_F_C[1:, :] = exp_vecs_c_e.reshape(T, -1)[_erow] @ D_curl_mat.T
    if _mode == "fixed":
        Curl_F_A[0] = Curl_F_A[0] + exp_vecs_a_e.reshape(T, -1)[0] @ D_curl_mat.T
        Curl_F_C[0] = Curl_F_C[0] + exp_vecs_c_e.reshape(T, -1)[0] @ D_curl_mat.T

    if do_W:
        Curl_F_W = np.zeros((T, T))
        Curl_F_W[0] = W_curl_s.T[0]
        Curl_F_W[1:, :] = exp_vecs_u_e.reshape(T, -1)[_erow] @ D_curl_mat.T
        if _mode == "fixed":
            Curl_F_W[0] = Curl_F_W[0] + exp_vecs_u_e.reshape(T, -1)[0] @ D_curl_mat.T

    # L1b: the fake-news recursion J[t,s] = J[t-1,s-1] + F[t,s] runs down
    # each diagonal independently — np.cumsum accumulates in the same
    # sequential order as the historical python double loop.
    J_A = np.empty((T, T))
    J_C = np.empty((T, T))
    J_W = np.empty((T, T)) if do_W else None
    for k in range(T):  # diagonals starting at (0, k)
        idx = np.arange(T - k)
        J_A[idx, idx + k] = np.cumsum(Curl_F_A[idx, idx + k])
        J_C[idx, idx + k] = np.cumsum(Curl_F_C[idx, idx + k])
        if do_W:
            J_W[idx, idx + k] = np.cumsum(Curl_F_W[idx, idx + k])
    for k in range(1, T):  # diagonals starting at (k, 0)
        idx = np.arange(T - k)
        J_A[idx + k, idx] = np.cumsum(Curl_F_A[idx + k, idx])
        J_C[idx + k, idx] = np.cumsum(Curl_F_C[idx + k, idx])
        if do_W:
            J_W[idx + k, idx] = np.cumsum(Curl_F_W[idx + k, idx])

    # Zeroth Column of the Jacobian (historical construction; the live
    # engine overwrites it with the BUG-072 direct column afterwards —
    # kept so the fake-news recursion's own column math stays identical).
    Zeroth_col_agent.tran_matrix = np.array(Zeroth_col_agent.tran_matrix)

    C_t = np.zeros(T)
    A_t = np.zeros(T)
    W_t = np.zeros(T) if do_W else None

    dstn_dot = D_ss

    for t in range(T):
        tran_mat_t = Zeroth_col_agent.tran_matrix[t]

        dstn_all = np.dot(tran_mat_t, dstn_dot)

        C = np.dot(c_ss, dstn_all)
        A = np.dot(a_ss, dstn_all)

        C_t[t] = C[0]
        A_t[t] = A[0]
        if do_W:
            W_t[t] = np.dot(u_ss_vec, dstn_all)[0]

        dstn_dot = dstn_all

    if ghost_zero is None:
        # Historical: difference against the STATIC steady state. Exact only
        # where the unshocked chain is exactly stationary on the distribution
        # grid — which fails at the high-beta atoms (BUG-112).
        J_A.T[0] = (A_t - A_ss) / dx
        J_C.T[0] = (C_t - C_ss) / dx
        if do_W:
            U_ss = np.dot(u_ss_vec, np.asarray(D_ss).reshape(-1, 1))[0]
            J_W.T[0] = (W_t - U_ss) / dx
    else:
        # BUG-112 fix: difference against the chain's OWN unshocked twin, the
        # same correction BUG-075 applied to curlyY/curlyD and to the direct
        # column. The twin carries whatever drift the grid induces, so it
        # cancels instead of being divided by dx.
        J_A.T[0] = (A_t - ghost_zero["A"]) / dx
        J_C.T[0] = (C_t - ghost_zero["C"]) / dx
        if do_W:
            gW0 = np.array([np.dot(u_ss_vec,
                                   np.asarray(ghost_zero["d"][t]).reshape(-1, 1))[0]
                            for t in range(T)])
            J_W.T[0] = (W_t - gW0) / dx

    return J_C, J_A, J_W


def compute_average_aggregates(C_ss_all, A_ss_all, DiscFacDstns, weights):
    n = len(DiscFacDstns[0].atoms[0])
    C_ss_final = 0
    A_ss_final = 0
    for d in range(n):  # discount factor
        for e in range(num_educ_types):  # education type
            C_ss_final += weights[e] * C_ss_all[e, d, 0] / n
            A_ss_final += weights[e] * A_ss_all[e, d, 0] / n
    return C_ss_final, A_ss_final


def compute_average_JAC(CJAC, AJAC, DiscFacDstns, weights):
    n = len(DiscFacDstns[0].atoms[0])
    CJAC_weighted_avg = np.zeros((len(shock_params), bigT, bigT))
    AJAC_weighted_avg = np.zeros((len(shock_params), bigT, bigT))
    for s in range(len(shock_params)):  # shock type
        for d in range(n):  # discount factor
            for e in range(num_educ_types):  # education type
                CJAC_weighted_avg[s] += weights[e] * CJAC[e, d, s] / n
                AJAC_weighted_avg[s] += weights[e] * AJAC[e, d, s] / n
    return CJAC_weighted_avg, AJAC_weighted_avg


def compute_average_JAC_by_educ(CJAC, AJAC, DiscFacDstns):
    n = len(DiscFacDstns[0].atoms[0])
    CJAC_weighted_avg = np.zeros((len(shock_params), num_educ_types, bigT, bigT))
    AJAC_weighted_avg = np.zeros((len(shock_params), num_educ_types, bigT, bigT))
    for s in range(len(shock_params)):  # shock type
        for d in range(n):  # discount factor
            for e in range(num_educ_types):  # education type
                CJAC_weighted_avg[s, e] += CJAC[e, d, s] / n
                AJAC_weighted_avg[s, e] += AJAC[e, d, s] / n
    return CJAC_weighted_avg, AJAC_weighted_avg


def run():
    """Compute all household Jacobians and write HA_Fiscal_Jacs.obj."""
    import pickle

    ctx = hh_setup.build()
    dicts = [ctx.init_dropout, ctx.init_highschool, ctx.init_college]
    DiscFacDstns = ctx.DiscFacDstns

    n_betas = len(DiscFacDstns[0].atoms[0])
    CJAC_all = np.zeros((num_educ_types, n_betas, len(shock_params), bigT, bigT))
    AJAC_all = np.zeros((num_educ_types, n_betas, len(shock_params), bigT, bigT))
    WJAC_all = np.zeros((num_educ_types, n_betas, len(shock_params), bigT, bigT))
    C_ss_all = np.zeros((num_educ_types, n_betas, len(shock_params)))
    A_ss_all = np.zeros((num_educ_types, n_betas, len(shock_params)))
    Uprime_all = np.zeros((num_educ_types, n_betas))

    dx_lists = {
        "wage": ctx.IncShkDstn_wage_dx,
        "tax": ctx.IncShkDstn_tax_dx,
        "transfers": ctx.IncShkDstn_transfers_dx,
        "UI_extend": ctx.IncShkDstn_ui_extend_dx,
        "UI_rr": ctx.IncShkDstn_ui_rr_dx,
    }

    # Diagnostic speed lever (instrument-consumption audit 2026-08-09:
    # the GE stage consumes no DiscFac column and never shocks UI_rr).
    # Skipped instruments keep their schema keys but stay ZERO — the
    # output is NOT production-valid for those keys. Default: skip none.
    skip = {t.strip() for t in
            os.environ.get("HAFISCAL_STEP4_SKIP_INSTRUMENTS", "").split(",")
            if t.strip()}
    if skip:
        print(f"[step4] DIAGNOSTIC: skipping instruments {sorted(skip)} "
              "(schema keys kept as zeros; not production-valid)", flush=True)

    start = time.time()
    for e in range(num_educ_types):  # education type
        betas = DiscFacDstns[e].atoms[0]
        dict_ = dicts[e]
        IncDist = [ctx.IncShkDstn[e]]
        for d, beta in enumerate(betas):
            print(f"[step4] educ={e} beta[{d}]={beta:.6f}", flush=True)
            base = prepare_type_base(ctx.BaseTypeList[e], dict_, beta, IncDist)  # L1 hoist
            for s, param in enumerate(shock_params):
                if param in skip or shock_params_out[s] in skip:
                    continue
                if param in dx_lists:
                    IncDist_dx = [dx_lists[param][e]]
                else:
                    IncDist_dx = [ctx.IncShkDstn[e]]

                CJac, AJac, WJac, C_ss, A_ss, Uprime_ss = \
                    compute_type_jacobian_for_param(
                        base, IncDist, IncDist_dx, param)

                CJAC_all[e, d, s] = CJac
                AJAC_all[e, d, s] = AJac
                WJAC_all[e, d, s] = WJac
                C_ss_all[e, d, s] = C_ss
                A_ss_all[e, d, s] = A_ss
                Uprime_all[e, d] = Uprime_ss

    print('time taken to compute all jacobians', time.time() - start)

    weights = ctx.data_EducShares  # == [0.093, 0.527, 0.38] at Baseline
    CJACs_weighted, AJACs_weighted = compute_average_JAC(CJAC_all, AJAC_all, DiscFacDstns, weights)
    WJACs_weighted, _ = compute_average_JAC(WJAC_all, WJAC_all, DiscFacDstns, weights)
    C_ss_sim, A_ss_sim = compute_average_aggregates(C_ss_all, A_ss_all, DiscFacDstns, weights)
    CJACs_weighted_by_educ, AJACs_weighted_by_educ = \
        compute_average_JAC_by_educ(CJAC_all, AJAC_all, DiscFacDstns)
    WJACs_weighted_by_educ, _ = compute_average_JAC_by_educ(WJAC_all, WJAC_all, DiscFacDstns)
    Uprime_by_educ = {educ: float(Uprime_all[e].mean())
                      for e, educ in enumerate(education_groups)}
    Uprime_ss_weighted = float(sum(weights[e] * Uprime_all[e].mean()
                                   for e in range(num_educ_types)))
    print(f"[step4] C_ss_weighted={C_ss_sim:.10f} A_ss_weighted={A_ss_sim:.6f}", flush=True)
    print(f"[step4] Uprime_ss_weighted={Uprime_ss_weighted:.6f} "
          f"by_educ={ {k: round(v, 4) for k, v in Uprime_by_educ.items()} }", flush=True)

    CJAC_dict_temp = {}
    AJAC_dict_temp = {}
    WJAC_dict_temp = {}
    for i, shk in enumerate(shock_params_out):
        CJAC_dict_temp[shk] = deepcopy(CJACs_weighted[i])
        AJAC_dict_temp[shk] = deepcopy(AJACs_weighted[i])
        WJAC_dict_temp[shk] = deepcopy(WJACs_weighted[i])

    CJAC_dict_educ_temp = {}
    AJAC_dict_educ_temp = {}
    WJAC_dict_educ_temp = {}
    for e, educ in enumerate(education_groups):
        CJAC_dict_temp_i = {}
        AJAC_dict_temp_i = {}
        WJAC_dict_temp_i = {}
        for i, shk in enumerate(shock_params_out):
            CJAC_dict_temp_i[shk] = deepcopy(CJACs_weighted_by_educ[i, e])
            AJAC_dict_temp_i[shk] = deepcopy(AJACs_weighted_by_educ[i, e])
            WJAC_dict_temp_i[shk] = deepcopy(WJACs_weighted_by_educ[i, e])
        CJAC_dict_educ_temp[educ] = deepcopy(CJAC_dict_temp_i)
        AJAC_dict_educ_temp[educ] = deepcopy(AJAC_dict_temp_i)
        WJAC_dict_educ_temp[educ] = deepcopy(WJAC_dict_temp_i)

    Obj = {'C': CJAC_dict_temp, 'A': AJAC_dict_temp,
           'C_by_educ': CJAC_dict_educ_temp, 'A_by_educ': AJAC_dict_educ_temp,
           # H4: the education-and-beta-weighted steady-state aggregates,
           # for the GE stage to consume instead of hardcoded literals.
           'C_ss_weighted': C_ss_sim, 'A_ss_weighted': A_ss_sim,
           # First-order welfare Jacobians (owner commission 2026-08-09):
           # utility-FLOW responses per unit instrument (policy term
           # valued at u'(c_ss), composition term at u(c_ss) levels;
           # CRRA from the calibration). Schema-ADDITIVE. Normalization
           # for consumption-equivalent metrics:
           'W': WJAC_dict_temp, 'W_by_educ': WJAC_dict_educ_temp,
           'Uprime_ss_weighted': Uprime_ss_weighted,
           'Uprime_ss_by_educ': Uprime_by_educ,
           # Ingestion hardening (ladder plan §5.6): the FD step every J
           # in this obj was divided by. ge.py asserts its own UJAC dx
           # equals this at load (schema-ADDITIVE; absent in older objs).
           'dx': float(dx)}

    with open(OUTPUT_OBJ, 'wb') as fileObj:
        pickle.dump(Obj, fileObj)
    print(f"[step4] wrote {OUTPUT_OBJ}", flush=True)

    # ---- Provenance sidecar (schema v2; best-effort, never aborts) ----
    try:
        import provenance as _prov
        import sys as _prov_sys
        _prov.emit([OUTPUT_OBJ], command=" ".join(_prov_sys.argv),
                   argv=_prov_sys.argv,
                   label="step4-hank-sam-jacobians", register=True)
    except Exception as _prov_e:
        print(f"[provenance] sidecar emit skipped (non-fatal): {_prov_e}")

    return Obj
