"""Step-1 Stage B (`tm`): fully deterministic Fagereng targets — no panel, no seeds.

plans/20260724_step1-tm-a-simulation_plan.md Stage B, owner-ordered 2026-07-27
("I want all MC outside the welfare context gone"), REDESIGNED same day per the
owner's correction: NO 2-D joint state. The within-age (a, pLvl) correlation is
carried by per-cell pLvl MOMENT recursions (g1, g2) through the same
psi-coupled kernel (the Step-2 cohort-array precedent, ~3x the 1-D cost), plus
conditional-lognormal read-out (the phi(pLvl)-class approximation, ~1%
precedent) — see step1_tm_init.ergodic_joint_moments.

Components (matching Estimation_BetaNablaSplurge semantics exactly):
* Lorenz: WealthNow = end-of-period household assets in LEVELS = the ergodic
  joint itself; shares of min-adjusted wealth at population percentiles
  20/40/60/80 (the file's Lorenz_Data_Adj convention; the model minimum is
  the constrained a=0 cell, so the adjustment is a distribution-form no-op).
* K/Y: CapAgg/IncAgg with IncAgg = E[pLvl*TranShk] carrying the same-atom
  (psi, xi) entanglement + the newborn xi=1 convention (the panel's
  death-marker idiom).
* Aggregate MPCX path + smoothed-quartile MPCs: two-arm adjoint propagation
  per (a-node x conditional-p-atom) cell; the random win-quarter is the exact
  average over the four variants; frame anchoring via Lnrm = Llvl/(p*frame).

Gates: full-target f0 vs mc at fixed production parameters; bit-identical
repeat evaluations (determinism).
"""
import math
import os

import numpy as np
from scipy.stats import norm

from step1_tm_init import ergodic_joint_moments, step1_esc_active

__all__ = ["compute_step1_wealth_targets", "compute_step1_experiment",
           "smoothed_quartile_means"]

_MASS_FLOOR = 1e-9        # drop (renormalize) cells below this mass share

def _moments_grid(agent):
    """Extended dist grid for the moment recursion: the solve grid + a geometric
    tail extension (top x HAFISCAL_STEP1_DIST_TOP_MULT, HAFISCAL_STEP1_DIST_EXTRA
    points). The 2026-07-27 drill: the top type's ergodic reaches ~2100 vs the
    604 solve-top; the clip under-counted its E[a] by 5.6% (KY -2%-class);
    extension closes it to -1.35% while bulk metrics are top-invariant."""
    base = np.insert(np.asarray(agent.aXtraGrid, dtype=float), 0, 0.0)
    mult = float(os.environ.get("HAFISCAL_STEP1_DIST_TOP_MULT", "10"))
    extra = int(os.environ.get("HAFISCAL_STEP1_DIST_EXTRA", "80"))
    if mult <= 1 or extra <= 0:
        return base
    # Anchor the geometric extension at the BASIS top, not the knot-extended top.
    # Solve-side tail knots (aXtraExtra; the grid-only S1 stack, 2026-08-21) are
    # SOLVE machinery: without this anchor they silently rescaled the extension
    # to mult x the LAST KNOT (72,540 at REACH=12) at fixed count, leaving the
    # mass-bearing ~604..2100 range to a handful of coarse knot cells — the
    # G-battery valley-scatter mechanism (scatter ~7x the no-knots stack;
    # 2026-08-22). Knots stay IN the grid as bonus nodes; with no knots this is
    # value-identical to the historical rule (ext from the grid top).
    try:
        _ax = getattr(agent, "aXtraExtra", None)
        knots = (np.asarray(_ax, dtype=float).ravel()
                 if _ax is not None and np.size(_ax) else np.array([]))
    except (TypeError, ValueError):
        knots = np.array([])
    if knots.size:
        solved = np.asarray(agent.aXtraGrid, dtype=float)
        basis = np.setdiff1d(solved, knots)
        basis_top = float(np.max(basis)) if basis.size else float(base[-1])
    else:
        basis_top = float(base[-1])
    ext = np.geomspace(basis_top, basis_top * mult, extra + 1)[1:]
    return np.unique(np.concatenate([base, ext]))



def _conditional_lognormals(grid, pi, g1, g2):
    """Per a-cell conditional-lognormal (mu_c, sig_c) by moment matching."""
    keep = pi > _MASS_FLOOR
    Ep = np.where(keep, g1 / np.maximum(pi, 1e-300), 1.0)
    Ep2 = np.where(keep, g2 / np.maximum(pi, 1e-300), 1.0)
    var = np.maximum(Ep2 - Ep ** 2, 0.0)
    sig2 = np.log1p(var / np.maximum(Ep ** 2, 1e-300))
    mu = np.log(np.maximum(Ep, 1e-300)) - 0.5 * sig2
    return keep, Ep, mu, np.sqrt(sig2)


def _c_household(agent, grid, varsigma, Lnrm):
    """Household consumption row + full transition operator for one quarter
    with a win of Lnrm (0 = base). Consumption weighted pmv (measured on all
    alive this quarter — they die at period END); transitions weighted
    LivPrb*pmv + the newborn column. Consumption is household-total
    ((1-s)*cFunc + s*income) under BOTH interpretations; the asset transition
    dispatches on interpretation (CDC splurge-in-budget vs ESC plain optimizer
    rule — BUG-054 Option A, see step1_tm_init.step1_esc_active)."""
    dstn = agent.IncShkDstn[0]
    psi = np.asarray(dstn.atoms[0], float).ravel()
    xi = np.asarray(dstn.atoms[1], float).ravel()
    pmv = np.asarray(dstn.pmv, float).ravel()
    R = float(np.asarray(getattr(agent, "Rsave", getattr(agent, "Rfree"))).ravel()[0])
    G = float(np.asarray(agent.PermGroFac[0]).ravel()[0])
    L = float(np.asarray(agent.LivPrb[0]).ravel()[0])
    cFunc = agent.solution[0].cFunc
    A = len(grid)
    from step1_tm_init import newborn_aNrm_params
    mu_nb, sd_nb = newborn_aNrm_params(agent)
    if sd_nb > 0:
        probs = (np.arange(7) + 0.5) / 7.0
        nb_vals = np.exp(mu_nb + sd_nb * norm.ppf(probs))
    else:
        nb_vals = np.array([math.exp(mu_nb)])
    nb_vals = np.minimum(nb_vals, grid[-1])
    nb_col = np.zeros(A)
    idx = np.clip(np.searchsorted(grid, nb_vals, side="right") - 1, 0, A - 2)
    w_lo = np.clip((grid[idx + 1] - nb_vals) / (grid[idx + 1] - grid[idx]), 0, 1)
    np.add.at(nb_col, idx, w_lo / len(nb_vals))
    np.add.at(nb_col, idx + 1, (1 - w_lo) / len(nb_vals))

    c_bar = np.zeros(A)
    K = np.zeros((A, A))
    esc = step1_esc_active()

    # BATCHED SHOCK NODES (2026-08-18). This loop used to call cFunc once per income-shock
    # node -- S=30 calls per invocation, 3682 invocations per objective evaluation, so
    # ~110,880 separate HARK interpolator calls each carrying full Python dispatch through
    # LinearInterp.__call__ -> LowerEnvelope._evaluate -> powerlaw_decay._evalOrDer. A
    # cProfile of one production evaluation put 5.9s in HARK.interpolation and 2.8s in
    # powerlaw_decay, against 16.5s for the whole evaluation. The arithmetic per element is
    # trivial; the cost was almost entirely per-call overhead paid 110,880 times.
    #
    # So the whole (S, A) block is now built at once and cFunc is called ONCE on its
    # flattening. Interpolation is an elementwise map, so this is not an approximation --
    # it is the same operation on the same values in a different container.
    #
    # BIT-IDENTITY IS THE BINDING CONSTRAINT, and two details carry it:
    #   * ASSOCIATION ORDER of the argument. `scale[:,None]*grid[None,:] + xi[:,None] + Lnrm`
    #     reproduces `(scale_s*grid + xi_s) + Lnrm` element for element. Folding the scalars
    #     first -- `... + (xi + Lnrm)[:,None]` -- would regroup the additions and can differ
    #     in the last bits. Do not "simplify" it.
    #   * The REDUCTIONS STAY IN THE LOOP. `c_bar += pmv[s]*C[s]` and the two np.add.at
    #     scatters accumulate float in s order; replacing them with a vectorised sum or a
    #     single fused scatter would change summation order and hence the last bits.
    #     Only the elementwise work is batched.
    # Verified bitwise on all 7 discount-factor types x both lottery arms (argument and
    # cFunc output via np.array_equal), on (c_bar, K), and end-to-end on the objective --
    # see test_step1_tm_targets_batching.py.
    scale = R / (G * psi)                                   # (S,)
    M = scale[:, None] * grid[None, :] + xi[:, None] + Lnrm  # (S, A)  == per-s `m`
    C_stage = cFunc(M.ravel()).reshape(M.shape)              # ONE interpolator call
    C = (1.0 - varsigma) * C_stage + varsigma * (xi + Lnrm)[:, None]
    A_next = np.clip(M - (C_stage if esc else C), 0.0, grid[-1])
    IDX = np.clip(np.searchsorted(grid, A_next, side="right") - 1, 0, A - 2)
    W_LO = np.clip((grid[IDX + 1] - A_next) / (grid[IDX + 1] - grid[IDX]), 0, 1)

    cols = np.arange(A)                                      # hoisted; was rebuilt per s
    for s in range(len(pmv)):
        np.add.at(K, (IDX[s], cols), L * pmv[s] * W_LO[s])
        np.add.at(K, (IDX[s] + 1, cols), L * pmv[s] * (1 - W_LO[s]))
        c_bar += pmv[s] * C[s]
    K += (1.0 - L) * nb_col[:, None]
    return c_bar, K


def compute_step1_wealth_targets(agent_list):
    """(lorenz_Model 4-vector, KY_Model) in distribution form.

    Deflated pLvl units throughout — both outputs are frame-invariant ratios.
    """
    cells_w, cells_a, cells_mu, cells_sig = [], [], [], []
    cap = 0.0
    inc = 0.0
    ntypes = len(agent_list)
    esc = step1_esc_active()
    for agent in agent_list:
        # tol 1e-9: the wealth targets are quantile-class (need ~1e-6); the
        # near-unit-root top type makes 1e-12 power iteration the wall driver.
        grid, pi, g1, g2, k = ergodic_joint_moments(agent, tol=1e-9, dist_aGrid=_moments_grid(agent))
        keep, Ep, mu, sig = _conditional_lognormals(grid, pi, g1, g2)
        w = pi / ntypes
        cells_w.append(w[keep]); cells_a.append(grid[keep])
        cells_mu.append(mu[keep]); cells_sig.append(sig[keep])
        # BUG-054 Option A: ESC household wealth = (1-s)*a_stage. Lorenz shares
        # and quartile ranks are scale-invariant, so ONLY the K/Y numerator
        # carries the (1-s); the ergodic itself already runs on the ESC (plain)
        # asset rule via the kernels.
        # HAFISCAL_STEP1_WEALTH_LEGACY=1: the PUBLISHED read-out (raw wealth, no (1-s)) -- columns A/B of the
        # ergodic-conversion chain keep BUG-031's Step-1 face in; the correction is column C (plan 20260829-1935h).
        _legacy_readout = os.environ.get('HAFISCAL_STEP1_WEALTH_LEGACY', '').strip() == '1'
        wscale = (1.0 - float(getattr(agent, "Splurge", 0.0))) if (esc and not _legacy_readout) else 1.0
        cap += wscale * float((grid * g1).sum()) / ntypes  # E[a*p] exact via g1
        # IncAgg: E[p_now * xi_now] — survivors carry the SAME atom in the
        # p-multiplier and xi; newborns arrive with xi = 1.0 exactly.
        Ep_prev = float(g1.sum())
        surv = sum(w_s * m_s * x for (_i, _w, w_s, m_s, x) in k["atoms"])
        inc += (Ep_prev * surv + (1.0 - k["L"]) * k["E_p_nb"] * k["xi_nb"]) / ntypes

    w = np.concatenate(cells_w); a = np.concatenate(cells_a)
    mu = np.concatenate(cells_mu); sig = np.concatenate(cells_sig)
    w = w / w.sum()
    pos = a > 0
    ln_a = np.log(np.maximum(a, 1e-300))
    pe_full = np.exp(ln_a[pos] + mu[pos] + 0.5 * sig[pos] ** 2)
    tot_wealth = float((w[pos] * pe_full).sum())

    def cdf(x):
        if x <= 0:
            return float(w[~pos].sum()) if x >= 0 else 0.0
        z = (math.log(x) - ln_a[pos] - mu[pos]) / np.maximum(sig[pos], 1e-12)
        return float(w[~pos].sum() + (w[pos] * norm.cdf(z)).sum())

    def wealth_below(x):
        if x <= 0:
            return 0.0
        z = (math.log(x) - ln_a[pos] - mu[pos]) / np.maximum(sig[pos], 1e-12)
        return float((w[pos] * pe_full * norm.cdf(z - sig[pos])).sum())

    hi = float(np.max(np.exp(ln_a[pos] + mu[pos] + 8 * sig[pos])))
    shares = []
    for q in (0.20, 0.40, 0.60, 0.80):
        lo_x, hi_x = 0.0, hi
        for _ in range(80):
            mid = 0.5 * (lo_x + hi_x)
            if cdf(mid) < q:
                lo_x = mid
            else:
                hi_x = mid
        shares.append(wealth_below(0.5 * (lo_x + hi_x)) / tot_wealth)
    return np.asarray(shares), cap / inc


def _rows_forward(c_bar, K, n):
    rows = np.zeros((n, len(c_bar)))
    rows[0] = c_bar
    for q in range(1, n):
        rows[q] = rows[q - 1] @ K
    return rows


def compute_step1_experiment(agent_list, splurge, lottery_size_rep,
                             n_quarters=20, win_quarters=(0, 1, 2, 3),
                             n_p_atoms=3):
    """Deterministic MPC targets on (a-node x conditional-p-atom) cells."""
    n_years = n_quarters // 4
    T_REF = int(os.environ.get("HAFISCAL_STEP1_TM_INIT_TREF", "800"))
    agg = np.zeros(n_years)
    tot_w = 0.0
    cells_mpc, cells_w, cells_wealth = [], [], []
    ntypes = len(agent_list)
    qs = norm.ppf((np.arange(n_p_atoms) + 0.5) / n_p_atoms)

    for agent in agent_list:
        # BASE grid for the experiment: MPC components are top-invariant (the
        # 5a 3e-5 precedent held here too: base-grid experiment + mc wealth
        # gated at 0.006%), and the extended grid triples the per-cell cost.
        # The wealth targets use the extended grid separately.
        grid, pi, g1, g2, k = ergodic_joint_moments(agent)
        G_agg = float(np.asarray(getattr(agent, "PermGroFacAgg", 1.0)).ravel()[0])
        frame = G_agg ** T_REF
        keep, Ep, mu, sig = _conditional_lognormals(grid, pi, g1, g2)
        varsigma = float(splurge)
        c_bar0, K0 = _c_household(agent, grid, varsigma, 0.0)
        rows0 = _rows_forward(c_bar0, K0, n_quarters)
        base_at = rows0.T                       # base_at[ci][q]

        for ci in np.nonzero(keep)[0]:
            w_cell = pi[ci] / (n_p_atoms * ntypes)
            if w_cell <= _MASS_FLOOR / 10:
                continue
            for z in qs:
                p_abs = math.exp(mu[ci] + sig[ci] * z) * frame
                Lnrm = lottery_size_rep / p_abs
                c_barW, KW = _c_household(agent, grid, varsigma, Lnrm)
                mpc_y_cell = np.zeros(n_years)
                # OPERATOR-CHAIN CACHING (2026-08-18). The quantity wanted at win-quarter wq and
                # horizon h is  rows0[h] @ KW @ K0^wq. This loop used to rebuild that chain FROM
                # SCRATCH for every wq: at wq it paid 1 matvec for rows0[h] @ KW plus wq more for
                # the K0 powers, so with win_quarters=(0,1,2,3) and n_quarters=20 the four passes
                # cost 19*1 + 18*2 + 17*3 + 16*4 = 170 matvecs, plus 0+1+2+3 = 6 for the c_barW
                # chain -- 176 per (cell, p-atom), and there are 3,675 of those per objective
                # evaluation, each an A x A matvec at A=319.
                #
                # But the wq-th chain is just the (wq-1)-th with one more K0 applied. Carrying each
                # partial product forward instead of recomputing it costs 19 + 18 + 17 + 16 = 70
                # matvecs for the h-chains and 3 for the c_barW chain: 73 instead of 176, a 2.4x
                # reduction in the A x A work.
                #
                # THIS IS BITWISE EXACT, for a specific reason: it re-associates NOTHING. Every
                # partial product is formed by the SAME sequence of matvecs against the SAME
                # operands, left to right, as before. The only change is that a result is kept
                # instead of being thrown away and recomputed identically.
                #
                # Two tempting further optimisations are deliberately NOT taken, both measured:
                #   * batching the h-chains into one (H, A) @ (A, A) GEMM is 2e-15 relative OFF
                #     (BLAS blocks GEMM differently from GEMV) and only 1.17x faster;
                #   * only element [ci] of each product is ever read, so this could collapse to dot
                #     products against a precomputed column of KW @ K0^wq -- ~35x fewer flops, but
                #     a genuine re-association that moves the last bits.
                # Both are available if a non-bitwise change is ever sanctioned; neither is taken.
                #
                # ACCUMULATION ORDER is preserved separately: the operator chains must be walked in
                # ASCENDING wq, but mpc_y_cell is summed in the caller's ORIGINAL win_quarters
                # order, so a non-ascending win_quarters stays bitwise too.
                wqs = sorted(win_quarters)
                n_wq = len(win_quarters)
                Hmax = n_quarters - wqs[0] - 1
                Wchain = [rows0[h] @ KW for h in range(Hmax)]   # h-chains at K0^0
                vb = c_barW                                     # c_barW chain at K0^0
                applied = 0                                     # K0 powers applied so far
                d_by_wq = {}
                for wq in wqs:
                    H = n_quarters - wq - 1
                    for _ in range(wq - applied):
                        vb = vb @ K0
                        for h in range(H):
                            Wchain[h] = Wchain[h] @ K0
                    applied = wq
                    cq = base_at[ci].copy()
                    cq[wq] = vb[ci]
                    for h in range(H):
                        cq[wq + 1 + h] = Wchain[h][ci]
                    d_by_wq[wq] = (cq - base_at[ci]) / Lnrm
                for wq in win_quarters:
                    d = d_by_wq[wq]
                    for y in range(n_years):
                        mpc_y_cell[y] += d[4 * y:4 * y + 4].sum() / n_wq
                agg += w_cell * mpc_y_cell
                tot_w += w_cell
                cells_mpc.append(mpc_y_cell[0])
                cells_w.append(w_cell)
                cells_wealth.append(grid[ci] * p_abs)

    cells_w = np.asarray(cells_w)
    return {
        "agg_mpc_by_year": agg / tot_w,
        "cell_mpc_year1": np.asarray(cells_mpc),
        "cell_weight": cells_w / cells_w.sum(),
        "cell_wealth": np.asarray(cells_wealth),
    }


def smoothed_quartile_means(mpc, weights, wealth):
    """The estimation file's 9/40-11/40 ramp quartile weights, distribution form."""
    order = np.argsort(wealth, kind="stable")
    w = np.asarray(weights)[order]
    m = np.asarray(mpc)[order]
    cdf_hi = np.cumsum(w)
    mid = cdf_hi - 0.5 * w

    def ramp(lo, hi, x):
        r = np.clip((hi - x) / max(hi - lo, 1e-12), 0.0, 1.0)
        r[x <= lo] = 1.0
        return r

    q1 = ramp(9 / 40, 11 / 40, mid)
    q2u = ramp(19 / 40, 21 / 40, mid)
    q3u = ramp(29 / 40, 31 / 40, mid)
    parts = (q1, q2u - q1, q3u - q2u, 1.0 - q3u)
    out = np.zeros(4)
    for i, qq in enumerate(parts):
        ww = w * qq
        out[i] = float((ww * m).sum() / max(ww.sum(), 1e-300))
    return out
