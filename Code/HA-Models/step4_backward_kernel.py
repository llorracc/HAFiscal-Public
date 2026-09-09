"""Compiled finite-horizon backward pass for Step-4 (L3b of
plans/20260808-1638h_step4-jacobian-rebuild_plan.md).

Replicates the local ConsMarkovModel per-period solve exactly, carrying
the whole functional state as point arrays (the consumer-graph fact: the
dated solutions are consumed only via policy evaluation on dist_mGrid):

per state i the consumption function is
    c(m) = nanmin( unc(m), m - mNrmMin_i )
where unc = LinearInterp(mNrm_pts, cNrm_pts, MPCmin*hNrm, MPCmin):
    - inside: linear interpolation (searchsorted on x[:-1], i>=1)
    - below x[0]: NaN (lower_extrap False) -> envelope takes the
      constrained branch
    - above x[-1]: decay extrapolation
      y = icept + slope*x - A*exp(-B*(x - x_top)) when the decay guard
      holds (|slope_limit - slope_at_top| > 1e-15 + 1e-5*|slope_at_top|,
      i.e. numpy's isclose default rtol with atol=1e-15), else plain
      edge-segment linear extrapolation
and vP(m) = c(m)^(-CRRA).

The per-period step mirrors ConsMarkovSolver.solve(): def_boundary ->
per-next-state conditional EOP (positional shocks; the labeled
expected() is arithmetic-identical here) -> pseudo-inverse LinearInterp
(lower_extrap=True: linear both ends) -> unique-BoroCnst mixing passes
with MrkvArray weighting -> LivPrb scaling -> HumWealth/MPC bounds ->
EGM inversion -> next chain state + policy evaluation on dist_mGrid.

Sequential j-sums replace the (S,S)@(S,n) np.dot of the mixing step and
the small np.dot reductions, so agreement with the python path is
equivalence-class (~1e-15 reduction-order), NOT guaranteed bitwise —
gates and the default-flip governance treat it accordingly.
"""
import numpy as np
import numba


@numba.njit(cache=True)
def _unc_eval(x, xs, ys, n_pts, decay_flag, iceptL, slopeL, decayA, decayB):
    """LinearInterp._evalOrDer level semantics for one x (no lower_extrap)."""
    # searchsorted over xs[:n_pts-1], clamp to >=1
    lo, hi = 0, n_pts - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    i = lo
    if i < 1:
        i = 1
    alpha = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
    y = (1.0 - alpha) * ys[i - 1] + alpha * ys[i]
    if x < xs[0]:
        return np.nan
    if decay_flag and x > xs[n_pts - 1]:
        return iceptL + slopeL * x - decayA * np.exp(-decayB * (x - xs[n_pts - 1]))
    return y


@numba.njit(cache=True)
def _c_next(x, j, xs, ys, n_pts, decay_flag, iceptL, slopeL, decayA, decayB, mMin):
    """LowerEnvelope(unc, cnst) with nanmin semantics for state j."""
    unc = _unc_eval(x, xs[j], ys[j], n_pts, decay_flag[j], iceptL[j],
                    slopeL[j], decayA[j], decayB[j])
    cnst = x - mMin[j]
    if np.isnan(unc):
        return cnst
    return min(unc, cnst)


@numba.njit(cache=True)
def _searchsorted_left(xs, n, x):
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo


@numba.njit(cache=True)
def _nvrs_eval(x, xs, ys, n):
    """LinearInterp with lower_extrap=True and no limits: linear inside,
    edge-segment linear extrapolation both directions."""
    i = _searchsorted_left(xs[: n - 1], n - 1, x)
    if i < 1:
        i = 1
    alpha = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
    return (1.0 - alpha) * ys[i - 1] + alpha * ys[i]


@numba.njit(cache=True)
def backward_pass(
    aXtraGrid, dist_mGrid, MrkvArrays, Rfree_t, PermGroFac_t, LivPrb_t,
    pmv_t, perm_t, tran_t, DiscFac_t, CRRA, has_art, BoroCnstArt,
    xs0, ys0, npts0, decay0, icept0, slope0, dA0, dB0, mMin0,
    MPCmin0, MPCmax0, hNrm0,
    cPol_out, aPol_out,
):
    """Run the T-period backward pass and evaluate policies on dist_mGrid.

    Shapes: MrkvArrays (T,S,S); Rfree_t/PermGroFac_t (T,S); LivPrb_t (T,S);
    pmv/perm/tran_t (T,S,K); terminal chain xs0/ys0 (S,P0max) with npts0
    (S,), decay/limit arrays (S,); cPol_out/aPol_out (T,S,n_dist).
    Time direction: t = T-1 ... 0 (solution_next at t = chain from t+1).
    """
    T, S, K = pmv_t.shape
    nA = aXtraGrid.shape[0]
    nD = dist_mGrid.shape[0]
    P = nA + 1  # points per state in constructed periods

    # chain buffers (current "next-period" state)
    Pmax = xs0.shape[1] if xs0.shape[1] > P else P
    xsN = np.zeros((S, Pmax))
    ysN = np.zeros((S, Pmax))
    nptsN = np.zeros(S, dtype=np.int64)
    decN = np.zeros(S, dtype=np.bool_)
    icN = np.zeros(S)
    slN = np.zeros(S)
    dAN = np.zeros(S)
    dBN = np.zeros(S)
    mMinN = np.zeros(S)
    MPCminN = np.zeros(S)
    MPCmaxN = np.zeros(S)
    hNrmN = np.zeros(S)
    for j in range(S):
        nptsN[j] = npts0[j]
        for p in range(npts0[j]):
            xsN[j, p] = xs0[j, p]
            ysN[j, p] = ys0[j, p]
        decN[j] = decay0[j]
        icN[j] = icept0[j]
        slN[j] = slope0[j]
        dAN[j] = dA0[j]
        dBN[j] = dB0[j]
        mMinN[j] = mMin0[j]
        MPCminN[j] = MPCmin0[j]
        MPCmaxN[j] = MPCmax0[j]
        hNrmN[j] = hNrm0[j]

    # scratch
    NatAll = np.zeros(S)
    Nat = np.zeros(S)
    mMinNow = np.zeros(S)
    Dep = np.zeros((S, S))
    ExInc = np.zeros(S)
    WorstP = np.zeros(S)
    aCond = np.zeros((S, nA))
    Nvrs = np.zeros((S, nA))
    EOP = np.zeros((S, nA))
    EOPall = np.zeros((S, nA))
    newx = np.zeros((S, P))
    newy = np.zeros((S, P))

    for tt in range(T):
        t = T - 1 - tt
        Mrkv = MrkvArrays[t]
        Rf = Rfree_t[t]
        Gro = PermGroFac_t[t]
        Liv = LivPrb_t[t]
        DiscFac = DiscFac_t[t]

        # ---- def_boundary ----
        for j in range(S):
            pmin = perm_t[t, j, 0]
            tmin = tran_t[t, j, 0]
            for k in range(1, K):
                if perm_t[t, j, k] < pmin:
                    pmin = perm_t[t, j, k]
                if tran_t[t, j, k] < tmin:
                    tmin = tran_t[t, j, k]
            NatAll[j] = (mMinN[j] - tmin) * (Gro[j] * pmin) / Rf[j]
        for i in range(S):
            mx = -1.0e300
            for j in range(S):
                if Mrkv[i, j] > 0 and NatAll[j] > mx:
                    mx = NatAll[j]
            Nat[i] = mx
            if has_art and BoroCnstArt > Nat[i]:
                mMinNow[i] = BoroCnstArt
            else:
                mMinNow[i] = Nat[i]
            for j in range(S):
                Dep[i, j] = 1.0 if Nat[i] == NatAll[j] else 0.0

        # ---- per-next-state conditional EOP ----
        for j in range(S):
            s_inc = 0.0
            for k in range(K):
                s_inc += pmv_t[t, j, k] * perm_t[t, j, k] * tran_t[t, j, k]
            ExInc[j] = s_inc
            # worst-income probability: exact equality mask on products
            pmin = perm_t[t, j, 0]
            tmin = tran_t[t, j, 0]
            for k in range(1, K):
                if perm_t[t, j, k] < pmin:
                    pmin = perm_t[t, j, k]
                if tran_t[t, j, k] < tmin:
                    tmin = tran_t[t, j, k]
            worst = pmin * tmin
            wsum = 0.0
            for k in range(K):
                if perm_t[t, j, k] * tran_t[t, j, k] == worst:
                    wsum += pmv_t[t, j, k]
            WorstP[j] = wsum
            fac = DiscFac * Rf[j] * Gro[j] ** (-CRRA)
            for a_i in range(nA):
                a = aXtraGrid[a_i] + NatAll[j]
                aCond[j, a_i] = a
                acc = 0.0
                for k in range(K):
                    m_next = Rf[j] / (Gro[j] * perm_t[t, j, k]) * a + tran_t[t, j, k]
                    c = _c_next(m_next, j, xsN, ysN, nptsN[j], decN, icN,
                                slN, dAN, dBN, mMinN)
                    acc += pmv_t[t, j, k] * perm_t[t, j, k] ** (-CRRA) * c ** (-CRRA)
                v = fac * acc
                EOP[j, a_i] = v
                Nvrs[j, a_i] = v ** (-1.0 / CRRA)

        # ---- mixing: unique-BoroCnst passes ----
        # (replicates np.unique pass structure; S small so simple scan)
        EndOfPrdvP = np.zeros((S, nA))
        done = np.zeros(S, dtype=np.bool_)
        for i0 in range(S):
            if done[i0]:
                continue
            aMin = Nat[i0]
            # which_states: all i with Nat[i] == aMin
            for j in range(S):
                for a_i in range(nA):
                    EOPall[j, a_i] = 0.0
            # reachable j from any state in this pass
            for j in range(S):
                reach = False
                for i in range(S):
                    if Nat[i] == aMin and Mrkv[i, j] > 0:
                        reach = True
                        break
                if reach:
                    for a_i in range(nA):
                        ag = aMin + aXtraGrid[a_i]
                        nv = _nvrs_eval(ag, aCond[j], Nvrs[j], nA)
                        EOPall[j, a_i] = nv ** (-CRRA)
            for i in range(S):
                if Nat[i] == aMin and not done[i]:
                    for a_i in range(nA):
                        acc = 0.0
                        for j in range(S):
                            acc += Mrkv[i, j] * EOPall[j, a_i]
                        EndOfPrdvP[i, a_i] = Liv[i] * acc
                    done[i] = True

        # ---- HumWealth and bounding MPCs ----
        MPCminNow = np.zeros(S)
        MPCmaxEff = np.zeros(S)
        hNrmNow = np.zeros(S)
        for i in range(S):
            wp = 0.0
            ex = 0.0
            for j in range(S):
                w = Mrkv[i, j] * Dep[i, j] * WorstP[j]
                wp += w
                ex += w * Rf[j] ** (1.0 - CRRA) * MPCmaxN[j] ** (-CRRA)
            ExMPCmaxNext = (ex / wp) ** (-1.0 / CRRA)
            dfe = DiscFac * Liv[i]
            MPCmax_i = 1.0 / (1.0 + (dfe * wp) ** (1.0 / CRRA) / ExMPCmaxNext)
            if Nat[i] < mMinNow[i]:
                MPCmax_i = 1.0
            MPCmaxEff[i] = MPCmax_i
            h = 0.0
            mn = 0.0
            for j in range(S):
                h += Mrkv[i, j] * (Gro[j] / Rf[j]) * (ExInc[j] + hNrmN[j])
                mn += Mrkv[i, j] * MPCminN[j] ** (-CRRA) * Rf[j] ** (1.0 - CRRA)
            hNrmNow[i] = h
            MPCminNow[i] = 1.0 / (1.0 + (dfe * mn) ** (1.0 / CRRA))

        # ---- EGM points ----
        for i in range(S):
            newx[i, 0] = mMinNow[i]
            newy[i, 0] = 0.0
            for a_i in range(nA):
                c = EndOfPrdvP[i, a_i] ** (-1.0 / CRRA)
                a = aXtraGrid[a_i] + Nat[i]
                newy[i, a_i + 1] = c
                newx[i, a_i + 1] = c + a

        # ---- new chain state + decay parameters ----
        for i in range(S):
            nptsN[i] = P
            for p in range(P):
                xsN[i, p] = newx[i, p]
                ysN[i, p] = newy[i, p]
            icN[i] = MPCminNow[i] * hNrmNow[i]
            slN[i] = MPCminNow[i]
            slope_top = (newy[i, P - 1] - newy[i, P - 2]) / (
                newx[i, P - 1] - newx[i, P - 2])
            level_diff = icN[i] + slN[i] * newx[i, P - 1] - newy[i, P - 1]
            slope_diff = slN[i] - slope_top
            # np.isclose(slope_limit, slope_at_top, atol=1e-15): default rtol
            if abs(slN[i] - slope_top) <= 1e-15 + 1e-5 * abs(slope_top):
                decN[i] = False
                dAN[i] = 0.0
                dBN[i] = 0.0
            else:
                decN[i] = True
                dAN[i] = level_diff
                dBN[i] = -slope_diff / level_diff
            mMinN[i] = mMinNow[i]
            MPCminN[i] = MPCminNow[i]
            MPCmaxN[i] = MPCmaxEff[i]
            hNrmN[i] = hNrmNow[i]

        # ---- policy evaluation on dist_mGrid (this period's cFunc) ----
        for i in range(S):
            for d_i in range(nD):
                m = dist_mGrid[d_i]
                c = _c_next(m, i, xsN, ysN, nptsN[i], decN, icN, slN,
                            dAN, dBN, mMinN)
                cPol_out[t, i, d_i] = c
                aPol_out[t, i, d_i] = m - c
    return 0


# ---------------------------------------------------------------------------
# python-side driver + terminal-chain extraction
# ---------------------------------------------------------------------------

def extract_chain(solution, S):
    """Extract the point-array chain state from a solved ConsumerSolution
    (the SS solution used as solution_terminal). Returns None if the
    structure differs from the expected LowerEnvelope(LinearInterp-with-
    limits, 2-point-cnst) form."""
    try:
        mMin = np.asarray(solution.mNrmMin, dtype=float).ravel()
        MPCmin = np.asarray(solution.MPCmin, dtype=float).ravel()
        MPCmax = np.asarray(solution.MPCmax, dtype=float).ravel()
        hNrm = np.asarray(solution.hNrm, dtype=float).ravel()
        if not (len(solution.cFunc) == S == mMin.size == MPCmin.size
                == MPCmax.size == hNrm.size):
            return None
        pts = []
        for j in range(S):
            env = solution.cFunc[j]
            if not hasattr(env, "functions") or len(env.functions) != 2:
                return None
            unc = env.functions[0]
            if (getattr(unc, "indexer", None) is not None
                    or hasattr(unc, "slopes") or unc.lower_extrap):
                return None
            cn = env.functions[1]
            if cn.x_n != 2 or cn.y_list[0] != 0.0 or cn.y_list[1] != 1.0:
                return None
            dec = bool(getattr(unc, "decay_extrap", False))
            pts.append((np.asarray(unc.x_list, float), np.asarray(unc.y_list, float),
                        dec,
                        float(getattr(unc, "intercept_limit", 0.0) or 0.0) if dec else 0.0,
                        float(getattr(unc, "slope_limit", 0.0) or 0.0) if dec else 0.0,
                        float(getattr(unc, "decay_extrap_A", 0.0)) if dec else 0.0,
                        float(getattr(unc, "decay_extrap_B", 0.0)) if dec else 0.0))
        Pmax = max(p[0].size for p in pts)
        xs0 = np.zeros((S, Pmax)); ys0 = np.zeros((S, Pmax))
        npts0 = np.zeros(S, dtype=np.int64)
        decay0 = np.zeros(S, dtype=bool)
        icept0 = np.zeros(S); slope0 = np.zeros(S)
        dA0 = np.zeros(S); dB0 = np.zeros(S)
        for j, (x, y, dec, ic, sl, dA, dB) in enumerate(pts):
            npts0[j] = x.size
            xs0[j, :x.size] = x; ys0[j, :y.size] = y
            decay0[j] = dec; icept0[j] = ic; slope0[j] = sl
            dA0[j] = dA; dB0[j] = dB
        return dict(xs0=xs0, ys0=ys0, npts0=npts0, decay0=decay0,
                    icept0=icept0, slope0=slope0, dA0=dA0, dB0=dB0,
                    mMin0=mMin, MPCmin0=MPCmin, MPCmax0=MPCmax, hNrm0=hNrm)
    except Exception:
        return None


def fast_backward(agent, shk_dstn=None):
    """Run the compiled T-period backward pass for a finite-horizon Markov
    agent and return (cPol_Grid, aPol_Grid) evaluated on agent.dist_mGrid.
    Returns None on any structural mismatch (caller falls back)."""
    try:
        T = agent.T_cycle
        S = len(agent.MrkvArray[0])
        if shk_dstn is None:
            shk_dstn = agent.IncShkDstn
        aX = np.asarray(agent.aXtraGrid, float)
        dist_mGrid = np.asarray(agent.dist_mGrid, float)
        K = len(shk_dstn[0][0].pmv)
        Mrkv_t = np.zeros((T, S, S))
        Rf_t = np.zeros((T, S)); Gro_t = np.zeros((T, S)); Liv_t = np.zeros((T, S))
        pmv_t = np.zeros((T, S, K)); perm_t = np.zeros((T, S, K)); tran_t = np.zeros((T, S, K))
        for t in range(T):
            Mrkv_t[t] = agent.MrkvArray[t]
            Rf = agent.Rfree[t]
            Rf_t[t] = np.asarray(Rf, float).ravel() if np.size(Rf) == S else float(np.ravel(Rf)[0])
            g = agent.PermGroFac[t]
            Gro_t[t] = np.asarray(g, float).ravel() if np.size(g) == S else float(np.ravel(g)[0])
            lv = agent.LivPrb[t]
            Liv_t[t] = np.asarray(lv, float).ravel() if np.size(lv) == S else float(np.ravel(lv)[0])
            for j in range(S):
                d = shk_dstn[t][j]
                if len(d.pmv) != K or np.shape(d.atoms) != (2, K):
                    return None
                pmv_t[t, j] = d.pmv
                perm_t[t, j] = d.atoms[0]
                tran_t[t, j] = d.atoms[1]
        chain = extract_chain(agent.solution_terminal, S)
        if chain is None:
            return None
        art = getattr(agent, "BoroCnstArt", None)
        has_art = art is not None
        df = agent.DiscFac
        if isinstance(df, (list, tuple, np.ndarray)) and np.size(df) >= T:
            DiscFac_t = np.asarray([float(np.ravel(df[t])[0]) for t in range(T)])
        else:
            DiscFac_t = np.full(T, float(np.ravel(df)[0]))
        cPol = np.zeros((T, S, dist_mGrid.size))
        aPol = np.zeros((T, S, dist_mGrid.size))
        backward_pass(aX, dist_mGrid, Mrkv_t, Rf_t, Gro_t, Liv_t,
                      pmv_t, perm_t, tran_t, DiscFac_t, float(agent.CRRA),
                      has_art, float(art) if has_art else 0.0,
                      chain["xs0"], chain["ys0"], chain["npts0"], chain["decay0"],
                      chain["icept0"], chain["slope0"], chain["dA0"], chain["dB0"],
                      chain["mMin0"], chain["MPCmin0"], chain["MPCmax0"], chain["hNrm0"],
                      cPol, aPol)
        return cPol, aPol
    except Exception:
        return None
