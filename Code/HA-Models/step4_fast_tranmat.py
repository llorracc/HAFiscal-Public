"""Batched finite-horizon transition-matrix builder for Step-4 (L3a of
plans/20260808-1638h_step4-jacobian-rebuild_plan.md).

The legacy path calls HARK's njit'd gen_tran_matrix_1D once per
(period, markov-pair) — ~3,600 tiny launches per agent per param, each
paying numba boxing plus a parallel=True thread-team spinup on a
~120-point loop. This module runs ONE compiled call per agent covering
all periods and pairs, reproducing the legacy arithmetic exactly:
identical per-element expression trees and identical accumulation order
(the shock loop is sequential per column, prange only over independent
(t, column) work), so the result is bitwise-equal to the legacy loop.

Consumed by FromPandemicCode/ConsMarkovModel.calc_transition_matrix via
a guarded, lazily-imported fast path (HAFISCAL_STEP4_FAST_TRANMAT).

BUG-097 (2026-08-28): this module is also the single source of the
HAFISCAL_STEP4_TRANMAT_GROWTH toggle and of the per-next-state growth
factor every Step-4 transition builder divides by (`tranmat_growth_on`,
`permgrofac_next`); the legacy python loops in ConsMarkovModel import
them lazily, so the kernel and the loops cannot disagree on Gamma.

Earnings phase (2026-08-29; conclusions_private/2026-08-28_earnings-phase-
state_decision.md): the same single-source rule for the NEWBORN RESET
(`newborn_phase_J`). When the household block carries the {growing,
matured} x employment state space (hh_setup.build() under
HAFISCAL_EARNINGS_PHASE_HAZARD; chain [growing J | matured J] =
[[(1-h)M, hM], [0, M]]), matured is absorbing, so a transition builder
that keeps HARK's convention "the newborn mass follows the chain
transition of the household it replaces" would drain every household
into the matured block: the ergodic distribution would be all-matured and
the phase would vanish from the block. Newborns are born growing (the PE
model's rule), so every builder — the kernel here and the three python
loops in ConsMarkovModel.calc_transition_matrix — sends the NEWBORN mass
of a transition into a matured state to the growing image of that state;
the survivors' mass is untouched. The employment state of a newborn keeps
the block's own convention (the chain transition of the deceased).
J = 0 (no phase) leaves the legacy expression in place bitwise.
"""
import os

import numpy as np
import numba

GROWTH_FLAG = "HAFISCAL_STEP4_TRANMAT_GROWTH"
# The agent attribute hh_setup.build() sets when the earnings phase is on: the hazard the household block was
# built with (0 / absent = no phase). Carried on the agent — NOT re-read from the environment at kernel time —
# so a 6-state agent constructed elsewhere while the flag happens to be set is never "reset", and every agent
# derived from the init dict (deepcopy, the finite-horizon MarkovConsumerType(**params)) inherits it.
PHASE_HAZARD_ATTR = "earnings_phase_hazard"


def phase_hazard_of(agent):
    """The earnings-phase hazard the agent was built with (0.0 = no phase)."""
    h = getattr(agent, PHASE_HAZARD_ATTR, 0.0)
    try:
        h = float(np.ravel(h)[0]) if np.size(h) else 0.0
    except (TypeError, ValueError):
        h = 0.0
    return h if h > 0.0 else 0.0


def newborn_phase_J(agent, n_m):
    """The employment-state count J of the agent's wrapped chain, or 0 when the agent carries no earnings phase.

    J > 0 tells every transition builder to send the newborn mass of a transition INTO a matured state
    (index >= J) to that state's growing image (index - J). Structural tripwires (a wrong layout would be
    rerouted silently otherwise): n_m == 2J, and the matured block is absorbing (the lower-left J x J block
    of MrkvArray[0] is zero) — the [[(1-h)M, hM], [0, M]] structure earnings_phase.wrap_chain produces.
    """
    if phase_hazard_of(agent) <= 0.0:
        return 0
    if n_m % 2:
        raise ValueError(f"earnings phase: {n_m} Markov states is not {{growing, matured}} x J")
    J = n_m // 2
    M0 = np.asarray(agent.MrkvArray[0], dtype=float)
    if M0.shape != (n_m, n_m) or np.any(M0[J:, :J] != 0.0):
        raise ValueError("earnings phase: the agent's chain is not the wrapped [[(1-h)M, hM], [0, M]] layout "
                         "(matured block not absorbing); refusing to reroute newborns")
    return J


def tranmat_growth_on():
    """BUG-097 toggle: do the distribution transitions carry PermGroFac?

    Normalized market resources evolve as m' = R*a/(Gamma*psi) + theta. The
    BUG-073 fix restored Gamma in the household SOLVE only; every
    distribution transition kept bNext = R*a with no Gamma (the policy of
    a growing economy driven by growth-free wealth dynamics). Default ON =
    the repaired, growth-consistent transition. Explicit 0/off/false = the
    growth-free transition (the correction ladder's "before" arm). Under
    HAFISCAL_QE_FIDELITY=1 the default is OFF: the frozen monolith runs
    with Gamma == 1 everywhere (HAFISCAL_HANK_PERMGROFAC defaults to ones
    there), where the two transitions coincide bit-for-bit, and its bytes
    stay untouched by never entering the division. An explicit setting
    always wins.
    """
    default = "0" if os.environ.get("HAFISCAL_QE_FIDELITY", "") == "1" else "1"
    return os.environ.get(GROWTH_FLAG, default).strip().lower() not in ("0", "off", "false")


def permgrofac_next(agent, t, n_m):
    """The period-t transition's growth factor per NEXT Markov state, (n_m,).

    Indexing follows the household solve exactly: ConsMarkovSolver
    conditions on the NEXT state j with `PermGroFac = PermGroFac_list[j]`
    taken from the period-t parameter, and step4_backward_kernel
    .backward_pass computes `m_next = Rf[j] / (Gro[j] * psi) * a + theta`
    with `Gro = PermGroFac_t[t]`. HARK's simulation agrees
    (MarkovConsumerType.get_shocks: PermShk = psi * PermGroFac[t-1][MrkvNow],
    the state just drawn). So the (m -> mp) block of the period-t
    transition divides bNext by PermGroFac[t][mp]. Returns ones when the
    toggle is off, so callers divide unconditionally (x / 1.0 == x exactly
    in IEEE arithmetic: the growth-free build is bitwise the pre-BUG-097
    one).
    """
    if not tranmat_growth_on():
        return np.ones(n_m)
    g = np.asarray(agent.PermGroFac[t], dtype=float).ravel()
    if g.size == n_m:
        return g
    if g.size == 1:
        return np.full(n_m, g[0])
    raise ValueError(
        f"PermGroFac[{t}] has {g.size} entries; expected one per Markov "
        f"state ({n_m}) or a scalar")


@numba.njit(cache=True)
def _jump_1d(m_vals, probs, grid, out):
    """jump_to_grid_1D with a caller-provided output row (zeroed here);
    same digitize/boundary/lerp/accumulation order as HARK's."""
    out[:] = 0.0
    n = grid.shape[0]
    mIndex = np.digitize(m_vals, grid) - 1
    for i in range(m_vals.shape[0]):
        if m_vals[i] <= grid[0]:
            mIndex[i] = -1
        if m_vals[i] >= grid[n - 1]:
            mIndex[i] = n - 1
    for i in range(m_vals.shape[0]):
        if mIndex[i] == -1:
            mlowerIndex = 0
            mupperIndex = 0
            mlowerWeight = 1.0
            mupperWeight = 0.0
        elif mIndex[i] == n - 1:
            mlowerIndex = n - 1
            mupperIndex = n - 1
            mlowerWeight = 1.0
            mupperWeight = 0.0
        else:
            mlowerIndex = mIndex[i]
            mupperIndex = mIndex[i] + 1
            mlowerWeight = (grid[mupperIndex] - m_vals[i]) / (
                grid[mupperIndex] - grid[mlowerIndex])
            mupperWeight = 1.0 - mlowerWeight
        out[mlowerIndex] += probs[i] * mlowerWeight
        out[mupperIndex] += probs[i] * mupperWeight


def newborn_m_values(tran_shks_state):
    """SST for HAFISCAL_HANK_NEWBORN_M — the newborn's market-resources
    vector for one destination state (2026-09-02; owner ruling same day:
    `income` is the DEFAULT-world HANK convention, an IMPROVEMENT).

      unset / "unit"  -> ones: the published convention, newborns at m = 1
                         exactly (byte-identical);
      "income"        -> the state's own transitory-income atoms: newborns
                         hold their first income draw — the PE-faithful
                         convention (PE newborns hold ZERO assets,
                         kLogInitMean = log(1e-5)) and scale-COVARIANT
                         (rung A7: the homotheticity floor vanishes);
      a float literal -> ones * value (the A7 verification dial).

    Consumed by BOTH transition builders — ConsMarkovModel's python loop
    (`_newborn_m_vector` delegates here) and `build_finite_tranmat_1D`
    below — so the loop and the kernel cannot disagree on the newborn.
    The DEFAULT resolution is scoped in step4/hh_setup (income in the
    default world; unit under QE_FIDELITY / as-corrected); PE consumers
    never set the env and get `unit`.
    """
    import os as _os
    v = _os.environ.get("HAFISCAL_HANK_NEWBORN_M", "unit").strip().lower()
    if v in ("", "unit", "1", "1.0"):
        return np.ones_like(tran_shks_state)
    if v == "income":
        return np.asarray(tran_shks_state)
    return np.ones_like(tran_shks_state) * float(v)


@numba.njit(parallel=True, cache=True)
def batched_tran_1D(grid, bNext_t, gro_t, prbs_t, perm_t, tran_t, SurvWgt_t, mrkv_t, J_phase, nbm_t, out):
    """out[t, mp, :, m, i] = mrkv_t[t,m,mp] * (SurvWgt*jump(bNext_t[t,m,i]
    /gro_t[t,mp]/perm + tran onto grid) + (1-SurvWgt)*newborn(mp)) for
    mrkv>0 pairs, else 0, with SurvWgt = SurvWgt_t[t,mp].

    SurvWgt_t (T, n_m) is the p-weighted SURVIVOR WEIGHT per period and DESTINATION state, from the
    caller from pweighted_survival.survivor_weight -- the single source of truth (BUG-108). The
    kernel never sees LivPrb or PermGroFac's role in the mass split, and performs no arithmetic on
    the weight beyond the one `1.0 - SurvWgt` the python loop's gen_tran_matrix_1D also performs on
    same float. That is what makes the kernel-vs-loop bitwise gate a structural invariant instead of
    a coincidence: neither side can group a product differently, because neither has a product.
    gro_t retains its OTHER role -- normalizing bNext by growing income -- which is why it stays.

    Shapes: grid (n_a,), bNext_t (T,n_m,n_a), gro_t (T,n_m) = the NEXT
    state's PermGroFac per period (BUG-097; ones = growth-free),
    prbs/perm/tran_t (T,n_m,K), liv_t (T,), mrkv_t (T,n_m,n_m),
    out (T,n_m,n_a,n_m,n_a) pre-zeroed. Expression order (b/Gamma)/psi
    + theta is the legacy loop's (bNext[m]/Gamma[mp] pre-divided, then
    gen_tran_matrix_1D's b/psi + theta), so kernel == loop bitwise with
    growth on as well as off.

    J_phase > 0 (the earnings phase; see newborn_phase_J): for a
    destination mp >= J_phase (matured) the survivors' mass stays in mp
    and the NEWBORN mass goes to mp - J_phase (born growing), placed with
    the growing state's own shock probabilities — the same two-step
    (assign the growing block, then add) as the python loops, so kernel
    == loop bitwise under the phase too. J_phase == 0 leaves the legacy
    expression untouched.
    """
    T, n_m, n_a = bNext_t.shape
    K = prbs_t.shape[2]
    for tw in numba.prange(T * n_m):
        t = tw // n_m
        m = tw % n_m
        mvals = np.empty(K)
        jump = np.empty(n_a)
        nb = np.empty(n_a)
        nbg = np.empty(n_a)
        for mp in range(n_m):
            if mrkv_t[t, m, mp] > 0:
                SurvWgt = SurvWgt_t[t, mp]
                _jump_1d(nbm_t[t, mp], prbs_t[t, mp], grid, nb)
                if J_phase > 0 and mp >= J_phase:
                    mg = mp - J_phase
                    _jump_1d(nbm_t[t, mg], prbs_t[t, mg], grid, nbg)
                    for i in range(n_a):
                        bg = bNext_t[t, m, i] / gro_t[t, mp]
                        for k in range(K):
                            mvals[k] = bg / perm_t[t, mp, k] + tran_t[t, mp, k]
                        _jump_1d(mvals, prbs_t[t, mp], grid, jump)
                        for j in range(n_a):
                            out[t, mp, j, m, i] = mrkv_t[t, m, mp] * (SurvWgt * jump[j])
                            out[t, mg, j, m, i] += mrkv_t[t, m, mp] * ((1.0 - SurvWgt) * nbg[j])
                else:
                    for i in range(n_a):
                        bg = bNext_t[t, m, i] / gro_t[t, mp]
                        for k in range(K):
                            mvals[k] = bg / perm_t[t, mp, k] + tran_t[t, mp, k]
                        _jump_1d(mvals, prbs_t[t, mp], grid, jump)
                        for j in range(n_a):
                            out[t, mp, j, m, i] = mrkv_t[t, m, mp] * (
                                SurvWgt * jump[j] + (1.0 - SurvWgt) * nb[j])


def build_finite_tranmat_1D(grid, bNext_t, prbs_t, perm_t, tran_t, liv_t, mrkv_t,
                            gro_t=None, J_phase=0):
    """Python wrapper: returns the (T, n_m*n_a, n_m*n_a) block.

    gro_t (T, n_m): the next state's PermGroFac per period (BUG-097);
    None = ones, the growth-free transition. J_phase: the earnings-phase
    newborn reset (newborn_phase_J; 0 = none)."""
    T, n_m, n_a = bNext_t.shape
    if gro_t is None:
        gro_t = np.ones((T, n_m))
    # BUG-108: the survivor/newborn split comes from the SST, once, here -- the kernel receives
    # weights and does no arithmetic on them. Gamma == 1 returns LivPrb exactly (x * 1.0 == x), so
    # the growth-free build is byte-identical to the pre-BUG-108 one.
    from pweighted_survival import survivor_weight
    SurvWgt_t = np.empty((T, n_m))
    for _t in range(T):
        SurvWgt_t[_t] = survivor_weight(float(liv_t[_t]), gro_t[_t])
    # the newborn m-values per (t, destination): the SST resolves the mode
    # once per state row; `unit` yields ones -> arithmetic identical to the
    # pre-knob kernel (the jit signature change only forces a recompile).
    nbm_t = np.empty_like(tran_t)
    for _t in range(T):
        for _m in range(tran_t.shape[1]):
            nbm_t[_t, _m] = newborn_m_values(tran_t[_t, _m])
    out = np.zeros((T, n_m, n_a, n_m, n_a))
    batched_tran_1D(np.ascontiguousarray(grid, dtype=np.float64),
                    np.ascontiguousarray(bNext_t, dtype=np.float64),
                    np.ascontiguousarray(gro_t, dtype=np.float64),
                    np.ascontiguousarray(prbs_t, dtype=np.float64),
                    np.ascontiguousarray(perm_t, dtype=np.float64),
                    np.ascontiguousarray(tran_t, dtype=np.float64),
                    np.ascontiguousarray(SurvWgt_t, dtype=np.float64),
                    np.ascontiguousarray(mrkv_t, dtype=np.float64),
                    int(J_phase),
                    np.ascontiguousarray(nbm_t, dtype=np.float64), out)
    return out.reshape(T, n_m * n_a, n_m * n_a)


def finite_tranmat_from_policies(agent, shk_dstn, cPol, aPol):
    """Build the finite-horizon transition matrices from precomputed
    policy grids (the L3b kernel's output), skipping the per-(t,state)
    interp evaluations. Returns (tran_matrix_list, cPol, aPol) or None
    on structural mismatch (caller falls back to the solve+legacy path).
    """
    import numpy as _np
    try:
        bigT = agent.T_cycle
        n_m = len(agent.MrkvArray[0])
        grid = _np.asarray(agent.dist_mGrid, float)
        n_a = grid.size
        if cPol.shape != (bigT, n_m, n_a):
            return None
        K = len(shk_dstn[0][0].pmv)
        bNext_t = _np.zeros((bigT, n_m, n_a))
        gro_t = _np.zeros((bigT, n_m))
        prbs_t = _np.zeros((bigT, n_m, K))
        perm_t = _np.zeros((bigT, n_m, K))
        tran_t = _np.zeros((bigT, n_m, K))
        liv_t = _np.zeros(bigT)
        mrkv_t = _np.zeros((bigT, n_m, n_m))
        # earnings phase: newborns of a matured destination are born growing (0 = no phase)
        J_phase = newborn_phase_J(agent, n_m)
        for t in range(bigT):
            Rfree = agent.Rfree[t]
            # BUG-097: the growth factor of the state transitioned INTO
            gro_t[t] = permgrofac_next(agent, t, n_m)
            for m in range(n_m):
                bNext_t[t][m] = Rfree[m] * aPol[t][m]
                d = shk_dstn[t][m]
                if len(d.pmv) != K:
                    return None
                prbs_t[t][m] = d.pmv
                tran_t[t][m] = d.atoms[1]
                perm_t[t][m] = d.atoms[0]
            liv_t[t] = agent.LivPrb[t][0]
            mrkv_t[t] = agent.MrkvArray[t]
        block = build_finite_tranmat_1D(grid, bNext_t, prbs_t, perm_t,
                                        tran_t, liv_t, mrkv_t, gro_t=gro_t,
                                        J_phase=J_phase)
        return [block[t] for t in range(bigT)]
    except Exception:
        return None
