"""Step-1 Stage A (`tm_init`): TM-ergodic panel seeding for the splurge estimation.

plans/20260724_step1-tm-a-simulation_plan.md, Stage A — the BUG-052 pattern
applied to Step-1: replace the T_sim=800 Monte-Carlo burn-in (~70% of each
objective evaluation, and a TRUNCATION of the stationary estimand — BUG-063)
with an exact ergodic initialization + short MC warmup. The 20-quarter lottery
experiment stays MC (CRN, unchanged).

Model: the Step-1 NOR agent is a single-Markov-state KinkedR consumer
(Rsave = Rfree binding at BoroCnstArt=0, individual PermGroFac=1, LivPrb
constant, UNCAPPED age — the NOR block sets T_age=None and always has). The
aNrm transition under shocks (psi, xi) with survival L and newborn reinjection
is a plain (A x A) column-stochastic matrix; its ergodic is the horizon-free
distribution the burn-in was trying (and failing, per BUG-063) to reach.

Consistency criterion (plan S3, [[feedback_numerical_validation]]): f0 under
`tm_init` must sit at the T->infinity PLATEAU, which the truncated mc-800
value approaches from below — asymptotic convergence, NOT point agreement
with the truncated legacy number.
"""
import math
import os

import numpy as np

from _interpretation import get_interpretation

__all__ = ["build_step1_tm", "ergodic_aNrm", "seed_and_warmup",
           "newborn_aNrm_params", "step1_esc_active"]


def step1_esc_active():
    """True under HAFISCAL_INTERPRETATION=ESC (BUG-054 Option A, 2026-07-27).

    Interpretation changes exactly TWO things in the Step-1 TM machinery:
      1. the asset transition:  CDC  a' = m - [(1-s)*cFunc(m) + s*xi]
                                ESC  a' = m - cFunc(m)  (plain optimizer rule)
      2. the wealth READ-OUT:   CDC  the ergodic state as-is
                                ESC  (1-s)*a  (Edmund Crawley's convention;
                                     scale-invariant for Lorenz shares and
                                     quartile ranks, so only K/Y carries it)
    Household CONSUMPTION is (1-s)*cFunc(m) + s*income under BOTH
    (models_CDC_and_ESC.md; the homotheticity review in the BUG-054 dossier:
    ESC = the SAME standard solve, level-rescaled at the read-out).
    """
    return get_interpretation() == 'ESC'

def newborn_aNrm_params(agent):
    """Newborn aNrm lognormal (mean, std) with the RNGSync sim_birth PRIORITY:
    aNrmInitMean > kLogInitMean > 0.0 (same for std). The 2026-07-27 drill:
    getattr(agent, 'aNrmInitMean', 0.0) silently injected newborns at
    aNrm = e^0 = 1.0 when the Step-1 agent carries only kLogInitMean = -11.51
    (newborns ~1e-5) -- a spurious +1.0 wealth injection per newborn that the
    near-unit-root wealth process amplified into the grid-converged,
    seed-robust +6-8% Ea bias on every ordinary type (mini-MC bisection:
    assumed-law 0.392 vs corrected 0.370 vs panel 0.367)."""
    if hasattr(agent, "aNrmInitMean"):
        return float(agent.aNrmInitMean), float(getattr(agent, "aNrmInitStd", 0.0) or 0.0)
    if hasattr(agent, "kLogInitMean"):
        return float(agent.kLogInitMean), float(getattr(agent, "kLogInitStd", 0.0) or 0.0)
    return 0.0, 0.0



def _lottery(idx_vals, grid):
    """Linear two-point lottery of values onto grid. Returns (lo_idx, w_lo)."""
    idx = np.searchsorted(grid, idx_vals, side="right") - 1
    idx = np.clip(idx, 0, len(grid) - 2)
    lo = grid[idx]
    hi = grid[idx + 1]
    w_lo = np.clip((hi - idx_vals) / (hi - lo), 0.0, 1.0)
    return idx, w_lo


def build_step1_tm(agent, dist_aGrid=None):
    """(A x A) column-stochastic aNrm transition for the solved Step-1 agent.

    Columns = today's a-node; rows = tomorrow's. Includes survival (LivPrb) and
    death->newborn reinjection (newborn aNrm from the agent's own lognormal
    init, discretized 7-point equiprobable). Uses the agent's OWN IncShkDstn
    (which already mixes in unemployment) and its post-solve (possibly
    powerlaw-rewrapped) cFunc — the same objects the MC consumes.
    """
    if dist_aGrid is None:
        dist_aGrid = np.insert(np.asarray(agent.aXtraGrid, dtype=float), 0, 0.0)
    A = len(dist_aGrid)

    dstn = agent.IncShkDstn[0]
    psi = np.asarray(dstn.atoms[0], dtype=float).ravel()
    xi = np.asarray(dstn.atoms[1], dtype=float).ravel()
    pmv = np.asarray(dstn.pmv, dtype=float).ravel()

    # Binding rate: KinkedR with BoroCnstArt=0 never borrows -> Rsave; plain
    # IndShock -> Rfree. (Both scalars in Step-1.)
    R = float(np.asarray(getattr(agent, "Rsave", getattr(agent, "Rfree"))).ravel()[0])
    G = float(np.asarray(agent.PermGroFac[0]).ravel()[0])
    L = float(np.asarray(agent.LivPrb[0]).ravel()[0])
    cFunc = agent.solution[0].cFunc

    # ASSET RULE dispatched on interpretation (BUG-054 Option A, 2026-07-27):
    #   CDC (splurge-in-budget; the falsification catch 2026-07-27): a' =
    #     m - [(1-s)*cFunc(m) + s*xi] (RNGSync get_poststates — v1 of this
    #     module omitted the splurge; the mc-long-vs-tm_init two-limit test
    #     refuted it, f0 0.0057 vs the mc plateau 0.0025; same bug class as
    #     BUG-033/BUG-051).
    #   ESC (splurge-out-of-stage): a' = m - cFunc(m) — the plain optimizer
    #     post-state (Edmund's convention; the (1-s) enters at the WEALTH
    #     read-out, not the transition).
    varsigma = float(getattr(agent, "Splurge", 0.0))
    esc = step1_esc_active()
    T = np.zeros((A, A))
    for s in range(len(pmv)):
        m_next = (R / (G * psi[s])) * dist_aGrid + xi[s]          # (A,)
        c_stage = cFunc(m_next)
        c_household = (1.0 - varsigma) * c_stage + varsigma * xi[s]
        a_next = np.maximum(m_next - (c_stage if esc else c_household), 0.0)
        a_next = np.minimum(a_next, dist_aGrid[-1])               # top clip
        idx, w_lo = _lottery(a_next, dist_aGrid)
        w = L * pmv[s]
        np.add.at(T, (idx, np.arange(A)), w * w_lo)
        np.add.at(T, (idx + 1, np.arange(A)), w * (1.0 - w_lo))

    # Death -> newborn reinjection: aNrm ~ lognormal(aNrmInitMean, aNrmInitStd),
    # 7-pt equiprobable, lotteried onto the grid; every column contributes (1-L).
    mu, sd = newborn_aNrm_params(agent)
    if sd > 0:
        from scipy.stats import norm
        probs = (np.arange(7) + 0.5) / 7.0
        nb_vals = np.exp(mu + sd * norm.ppf(probs))
    else:
        nb_vals = np.array([math.exp(mu)])
    nb_vals = np.minimum(nb_vals, dist_aGrid[-1])
    nb_col = np.zeros(A)
    idx, w_lo = _lottery(nb_vals, dist_aGrid)
    np.add.at(nb_col, idx, w_lo / len(nb_vals))
    np.add.at(nb_col, idx + 1, (1.0 - w_lo) / len(nb_vals))
    T += (1.0 - L) * nb_col[:, None]
    # Survival-only kernel (columns sum to 1): the age-cohort recursion needs
    # the transition CONDITIONAL on surviving, without the death->newborn mix.
    S_surv = (T - (1.0 - L) * nb_col[:, None]) / L
    return T, dist_aGrid, S_surv, nb_col


def ergodic_aNrm(T, tol=1e-12, max_iter=20000):
    """Stationary distribution of the column-stochastic T by power iteration."""
    A = T.shape[0]
    pi = np.full(A, 1.0 / A)
    for _ in range(max_iter):
        nxt = T @ pi
        nxt /= nxt.sum()
        if np.max(np.abs(nxt - pi)) < tol:
            return nxt
        pi = nxt
    return pi


def seed_and_warmup(agent, warmup=40, seed=0):
    """Seed the (already initialize_sim'd) panel at the TM ergodic + warm up.

    aNrm ~ pi(a) (grid atoms); t_age ~ geometric(1-L) truncated where survivor
    mass < 1e-9 (the agent is UNCAPPED — T_age=None in the NOR block); pLvl |
    age = the exact single-state lognormal recursion
        log pLvl(k) ~ N(pLogInitMean + k*(log G - sigma_psi^2/2),
                        pLogInitStd^2 + k*sigma_psi^2).
    Marginal-product seeding per the plan (joint a-age correlation restored by
    the warmup; the drift gates judge). Then agent.simulate(warmup).
    """
    T, grid, S_surv, _nb = build_step1_tm(agent)
    pi = ergodic_aNrm(T)
    rng = np.random.default_rng(seed + int(1e6 * float(agent.DiscFac)))
    N = agent.AgentCount

    L = float(np.asarray(agent.LivPrb[0]).ravel()[0])
    K = max(400, int(math.ceil(math.log(1e-9) / math.log(L))))
    ages = rng.geometric(1.0 - L, size=N)
    ages = np.minimum(ages, K)

    # AGE-CONDITIONAL aNrm (the marginal-vs-joint diagnostic catch, 2026-07-27):
    # marginal seeding (aNrm ~ pi, age independent) destroyed the a-age-pLvl
    # coupling the wealth-quartile targets sort on (measured corr(a,pLvl)
    # -0.026 vs the MC's -0.239). Draw a | age from the cohort recursion
    # pi_k = S_surv @ pi_{k-1}, pi_0 = newborn dist — the exact single-state
    # age-resolved distribution. One forward pass to the panel's max age,
    # sampling each cohort as we reach it (A~110, K~3300: trivial cost).
    a_draw = np.empty(N)
    pi_k = _nb.copy()
    max_age = int(ages.max())
    for k in range(1, max_age + 1):
        pi_k = S_surv @ pi_k
        pi_k = np.maximum(pi_k, 0.0)
        pi_k /= pi_k.sum()
        sel = ages == k
        if np.any(sel):
            a_draw[sel] = rng.choice(grid, size=int(sel.sum()), p=pi_k)

    # pLvl | age: exact single-state lognormal recursion IN DEFLATED UNITS.
    # cstw-style setup: newborns enter at the PermGroFacAgg-growing frontier, so
    # an age-k survivor's RELATIVE pLvl carries a -k*ln(G_agg) gradient on top
    # of the individual drift (the pLvl-mean diagnostic catch: MC deflated mean
    # ~0.72, the gradient-free version gave 1.01). Absolute PlvlAgg scale is
    # target-invariant (verified: mc f0 flat over T_sim 800->4000 while PlvlAgg
    # grows ~20x), so we seed in deflated units and leave PlvlAgg at its
    # initialize_sim value.
    G = float(np.asarray(agent.PermGroFac[0]).ravel()[0])
    G_agg = float(np.asarray(getattr(agent, "PermGroFacAgg", 1.0)).ravel()[0])
    psi = np.asarray(agent.IncShkDstn[0].atoms[0], dtype=float).ravel()
    pmv = np.asarray(agent.IncShkDstn[0].pmv, dtype=float).ravel()
    mlog = float(np.sum(pmv * np.log(psi)))          # E log psi (= -s^2/2-ish)
    vlog = float(np.sum(pmv * np.log(psi) ** 2) - mlog ** 2)
    mu0 = float(getattr(agent, "pLogInitMean", getattr(agent, "pLvlInitMean", 0.0)))
    sd0 = float(getattr(agent, "pLogInitStd", getattr(agent, "pLvlInitStd", 0.0)))

    # FRAME ANCHOR (the third diagnostic catch, 2026-07-27): the estimand is
    # NOT scale-free — the lottery is an ABSOLUTE level (Lnrm = Llvl/pLvl,
    # lottery_size fixed), and sim_birth scales newborn pLvl by the CURRENT
    # PlvlAgg, so the legacy mc-800 procedure measures MPCs at the t=800
    # aggregate frame (measured newborn intercept e^1.984 = G_agg^800). Stage A
    # must reproduce that frame: seed at G_agg^(T_REF - warmup) and seed
    # PlvlAgg itself so warmup newborns enter at the same frame; after the
    # warmup the experiment starts at exactly G_agg^T_REF, matching legacy.
    T_REF = int(os.environ.get("HAFISCAL_STEP1_TM_INIT_TREF", "800"))
    frame = G_agg ** max(T_REF - warmup, 0)
    p_draw = frame * np.exp(mu0 + ages * (math.log(G) + mlog - math.log(G_agg))
                            + rng.standard_normal(N) * np.sqrt(sd0 ** 2 + ages * vlog))

    agent.state_now["aNrm"] = a_draw
    agent.state_now["pLvl"] = p_draw
    if "aLvl" in agent.state_now:
        agent.state_now["aLvl"] = a_draw * p_draw
    if "PlvlAgg" in agent.state_now:
        agent.state_now["PlvlAgg"] = frame
    agent.t_age = ages.astype(int)
    agent.t_cycle = np.zeros(N, dtype=int)
    if warmup > 0:
        agent.simulate(warmup)
    return pi, grid


def per_atom_kernels(agent, dist_aGrid=None):
    """Per-shock-atom lottery kernels + newborn column, for the joint-moment
    recursion (the g1/g2 machinery; owner design correction 2026-07-27:
    per-cell pLvl MOMENTS through the SAME psi-coupled kernel replace any
    2-D joint state — the Step-2 cohort-array precedent, ~3x the 1-D cost).

    Returns dict with: grid, atoms = list of (idx, w_lo, w_s, mult_s, xi_s)
    where w_s = LivPrb*pmv_s (survivor transition weight) and mult_s =
    psi_s*G/G_agg (the DEFLATED pLvl multiplier riding the same atom),
    nb_col, L, E_p_nb, E_p2_nb (deflated newborn pLvl moments), xi_nb=1.0.
    """
    if dist_aGrid is None:
        dist_aGrid = np.insert(np.asarray(agent.aXtraGrid, dtype=float), 0, 0.0)
    grid = dist_aGrid
    A = len(grid)
    dstn = agent.IncShkDstn[0]
    psi = np.asarray(dstn.atoms[0], float).ravel()
    xi = np.asarray(dstn.atoms[1], float).ravel()
    pmv = np.asarray(dstn.pmv, float).ravel()
    R = float(np.asarray(getattr(agent, "Rsave", getattr(agent, "Rfree"))).ravel()[0])
    G = float(np.asarray(agent.PermGroFac[0]).ravel()[0])
    G_agg = float(np.asarray(getattr(agent, "PermGroFacAgg", 1.0)).ravel()[0])
    L = float(np.asarray(agent.LivPrb[0]).ravel()[0])
    varsigma = float(getattr(agent, "Splurge", 0.0))
    cFunc = agent.solution[0].cFunc
    esc = step1_esc_active()  # BUG-054: asset rule dispatch (see build_step1_tm)

    atoms = []
    for s in range(len(pmv)):
        m = (R / (G * psi[s])) * grid + xi[s]
        c_stage = cFunc(m)
        c_household = (1.0 - varsigma) * c_stage + varsigma * xi[s]
        a_next = np.clip(m - (c_stage if esc else c_household), 0.0, grid[-1])
        idx = np.clip(np.searchsorted(grid, a_next, side="right") - 1, 0, A - 2)
        w_lo = np.clip((grid[idx + 1] - a_next) / (grid[idx + 1] - grid[idx]), 0, 1)
        atoms.append((idx, w_lo, L * pmv[s], psi[s] * G / G_agg, xi[s]))

    mu, sd = newborn_aNrm_params(agent)
    if sd > 0:
        from scipy.stats import norm
        probs = (np.arange(7) + 0.5) / 7.0
        nb_vals = np.exp(mu + sd * norm.ppf(probs))
    else:
        nb_vals = np.array([math.exp(mu)])
    nb_vals = np.minimum(nb_vals, grid[-1])
    nb_col = np.zeros(A)
    idx = np.clip(np.searchsorted(grid, nb_vals, side="right") - 1, 0, A - 2)
    w_lo = np.clip((grid[idx + 1] - nb_vals) / (grid[idx + 1] - grid[idx]), 0, 1)
    np.add.at(nb_col, idx, w_lo / len(nb_vals))
    np.add.at(nb_col, idx + 1, (1 - w_lo) / len(nb_vals))

    mu0 = float(getattr(agent, "pLogInitMean", getattr(agent, "pLvlInitMean", 0.0)))
    sd0 = float(getattr(agent, "pLogInitStd", getattr(agent, "pLvlInitStd", 0.0)) or 0.0)
    return {
        "grid": grid, "atoms": atoms, "nb_col": nb_col, "L": L,
        "E_p_nb": math.exp(mu0 + 0.5 * sd0 ** 2),
        "E_p2_nb": math.exp(2 * mu0 + 2 * sd0 ** 2),
        "xi_nb": 1.0,
    }


def _scatter(vec, idx, w_lo, out):
    np.add.at(out, idx, w_lo * vec)
    np.add.at(out, idx + 1, (1.0 - w_lo) * vec)


def ergodic_joint_moments(agent, tol=1e-12, max_iter=20000, dist_aGrid=None):
    """Stationary (pi, g1, g2): mass, E[p*1(cell)], E[p^2*1(cell)] per a-cell,
    in DEFLATED pLvl units. The same psi atom that moves the a-lottery
    multiplies the p-moments — capturing the within-age (a,pLvl) correlation
    the independence seeding missed (the 11%-aLvl diagnostic catch).
    """
    k = per_atom_kernels(agent, dist_aGrid)
    grid, atoms, nb, L = k["grid"], k["atoms"], k["nb_col"], k["L"]
    A = len(grid)
    # Pre-build the three dense operators once (mass / m-weighted / m^2-weighted)
    # and power-iterate with matvecs: the per-iteration np.add.at scatters were
    # the wall driver (~2800 slow-mode iterations for the near-unit-root type).
    K_pi = np.zeros((A, A)); K_g1 = np.zeros((A, A)); K_g2 = np.zeros((A, A))
    for idx, w_lo, w_s, m_s, _xi in atoms:
        cols = np.arange(A)
        np.add.at(K_pi, (idx, cols), w_s * w_lo)
        np.add.at(K_pi, (idx + 1, cols), w_s * (1 - w_lo))
        np.add.at(K_g1, (idx, cols), w_s * m_s * w_lo)
        np.add.at(K_g1, (idx + 1, cols), w_s * m_s * (1 - w_lo))
        np.add.at(K_g2, (idx, cols), w_s * m_s * m_s * w_lo)
        np.add.at(K_g2, (idx + 1, cols), w_s * m_s * m_s * (1 - w_lo))
    pi = np.full(A, 1.0 / A)
    g1 = pi * 1.0
    g2 = pi * 1.5
    for it in range(max_iter):
        npi = K_pi @ pi + (1.0 - L) * nb
        ng1 = K_g1 @ g1 + (1.0 - L) * k["E_p_nb"] * nb
        ng2 = K_g2 @ g2 + (1.0 - L) * k["E_p2_nb"] * nb
        npi_sum = npi.sum()
        npi /= npi_sum
        ng1 /= npi_sum
        ng2 /= npi_sum
        if (np.max(np.abs(npi - pi)) < tol and np.max(np.abs(ng1 - g1)) < tol * 10
                and np.max(np.abs(ng2 - g2)) < tol * 100):
            return grid, npi, ng1, ng2, k
        pi, g1, g2 = npi, ng1, ng2
    return grid, pi, g1, g2, k
