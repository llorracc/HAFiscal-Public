"""Analytic Pareto TAIL STATE for the a-indexed baseline-ergodic TM (TS-1).

Implements the math note of record for `HAFISCAL_DIST_TAIL_STATE` (the
2026-07-26 DERIVE-phase note; every formula below was numerically verified
there -- residuals quoted per function).  Design context:
`plans/20260726_dist-grid-top-scoping_plan.md` P4' and
`conclusions_private/2026-07-26_peratom_battery_verdict.md` (owner rulings:
tail mass determined by the simulated dynamics, internal shape Pareto with
the per-atom KESTEN root as input -- deliberate deviation from
measured-alpha-primary, because measurement at low tops is corrupted by the
very truncation being removed; the ladder-flatness gate is the measured
validation).

WHAT THE TAIL STATE IS.  One extra state T_j per micro state j appended to
the a-indexed distribution state space (total (A+1)*J).  INFLOW: the mass
the TM lottery currently clips to the top grid node (a_next >= dist_aGrid[-1])
is redirected to T_{j'}.  Contents of T are frozen at Pareto(alpha) on
[X, inf), X = dist_aGrid[-1].  OUTFLOW per period, per destination state j'
and shock atom s with per-survivor wealth multiplier m = Thorn_{j'}/psi_s:
    m >= 1 : all mass stays in T;
    m <  1 : P(stay) = m^alpha, and the returning mass (1 - m^alpha) lands
             as a truncated Pareto(alpha) on [mX, X), lotteried onto the
             grid nodes (landing_node_weights below).
Death is culled from T at the same effective rate as everywhere else and
re-injected through NewBornDist (which carries ZERO tail mass -- newborns
start at the grid bottom).  READ-OUT: for moments only, T is expanded into
K log-spaced Pareto segments plus a closed-form terminal atom
(tail_readout_nodes below), consumed by the estimation surface.

This module holds the pure-numpy pieces (no HARK / HAFiscal imports, no env
reads at import time) so importing it cannot perturb the default
reproduction path.  `tm_methods` imports it LAZILY under the flag
(precedent: the adaptive_grid_tm lazy import in build_tm_agg_fiscal_a).
New code lives in Code/HA-Models/ (standing rule: no new files in
FromPandemicCode/).
"""

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Prior art (reviewer-verified): the per-atom Kesten root. Pure numpy+scipy,
# no env reads, cheap import.
from per_atom_alpha import kesten_alpha

__all__ = [
    "resolve_tail_alpha",
    "landing_node_weights",
    "tail_readout_nodes",
]

# Kesten-root plausibility band -- the prior-art acceptance band
# (decay_form/disttop_tail_bucket.py ALPHA_MEASURED_BAND upper end is 12; the
# note's V6b shows beta~0.9 atoms give root ~57.5 which must be caught here).
# At alpha >= 20 the widest atom's stay mass m^alpha is ~0.9^20 ~ 0.12-class
# and the tail empties in a few periods -- physically meaningless, numerically
# harmless to skip (per-atom DISABLE, standard A*J build for that atom).
ALPHA_BAND = (1.0, 20.0)

# Read-out defaults (note section 5: every estimand of record wholly contains
# the tail, so it is K-invariant by mean-exactness; K=12 = the prior art's
# N_TAIL_NODES, kept for tail-interior diagnostics; span=1000 makes even the
# no-terminal-atom discard 3e-4-class at alpha~2.17 -- and the terminal atom
# makes the expansion exactly mean-preserving at ANY span).
READOUT_K = 12
READOUT_SPAN = 1000.0


def _first_scalar(x):
    """First scalar of a possibly time-varying HARK parameter (scalar/list/array).

    Same convention as decay_form/disttop_tail_bucket._first_scalar: for
    AggFiscalType, PermGroFac/LivPrb are [array-over-states] lists and index 0
    of the ravel is the EMPLOYED state -- the caricature state the Kesten
    shape input uses (note section 6; the outflow MASS dynamics in the TM
    kernel use each destination state's own (R_jp, Gamma_jp, psi_{jp,s})
    exactly; the ladder gate arbitrates the shape approximation).
    """
    return float(np.asarray(x, dtype=float).ravel()[0])


def _effective_LivPrb_scalar(L, T_age):
    """Scalar mirror of tm_methods._effective_LivPrb (math-derive-appendix L-eff).

        L_eff = (L - L^T_age) / (1 - L^T_age)

    Kept here so this module stays import-light (importing tm_methods pulls
    HARK); the production caller (build_tm_agg_fiscal_a) passes its OWN
    _effective_LivPrb output in as `L_eff`, so this fallback is only used in
    standalone/diagnostic calls.  test_tail_state.py locks the two
    implementations together.
    """
    if T_age is None:
        return float(L)
    L = float(L)
    LT = L ** T_age
    if abs(1.0 - LT) < 1e-14:
        return 1.0 - 1.0 / T_age
    return (L - LT) / (1.0 - LT)


def resolve_tail_alpha(agent, L_eff=None):
    """Resolve one atom's tail-state parameters from the agent's calibration.

    Returns a dict:
        enabled atom : {'enabled': True, 'alpha', 'alpha_source', 'pat_num',
                        'kappa', 'L_eff', 'L_raw'}
        disabled atom: {'enabled': False, 'reason': <str>}
    A DISABLED atom gets the standard A*J TM (no tail state); the caller's
    post-ergodic materiality check (tm_methods.tail_state_readout) then
    verifies the top-node pile is < 1e-8 -- a material pile on a
    "no-power-tail" atom means the grid top sits inside the atom's BULK
    (mis-sized grid) and raises loudly.

    ALPHA INPUT (owner-recorded; note sections 3 + 6 -- the AMENDED input):
    the T_age-SPLIT Kesten root.  The production TM culls at
    L_eff = _effective_LivPrb(L_raw, T_age) (tm_methods applies it at build
    time) while the solver discounts at DiscFacEff = beta*L_raw (HARK
    convention, no annuities).  The stationary tail sub-process measurably
    equilibrates to the root of

        L_eff * E[ (Thorn_raw/psi)^alpha ] = 1,
        Thorn_raw = (R*beta*L_raw)^(1/CRRA) / PermGroFac

    (note V3: operator solve alpha_hat = 2.1631 vs this root 2.1634 at the
    cap atom, 0.01% -- vs the raw-L root 1.7793, 17.7% off; the split root
    also independently matches the plan's measured moderate-window cap-atom
    wealth-tail alpha ~2.17).  Obtained from per_atom_alpha UNCHANGED via the
    adapter (verified identical to a direct split root-find to 8.2e-14):

        kesten_alpha(beta*L_raw/L_eff, R, CRRA, G, LivPrb=L_eff, psi, pmv)
        # inside:  beta_eff = (beta*L_raw/L_eff)*L_eff = beta*L_raw
        # outside: L_eff (the TM's culling)

    with per_atom_alpha's default mortality_in_discount=True -- the placement
    the note's V1 EGM measurement pins empirically (asymptotic MPC residual
    2.9e-8 for L-inside vs a factor 2.36 for L-outside).

    Parameters
    ----------
    agent : AggFiscalType-like
        Needs DiscFac, Rfree, CRRA, PermGroFac, LivPrb, IncShkDstn[0][0]
        (employed-state joint (psi, xi) discretization: atoms[0] = psi
        values with the joint pmv -- psi values repeat across theta, so the
        joint pmv gives the correct marginal E[(Thorn/psi)^alpha]; same
        extraction as disttop_tail_bucket._kesten_alpha_from_module), and
        optionally T_age.
    L_eff : float or None
        The T_age-adjusted survival THE TM ACTUALLY CULLS AT -- the
        production caller passes float(LivPrb_arr[0]) from its own
        _effective_LivPrb output so the alpha condition and the TM culling
        use the identical number.  None => computed locally from
        (LivPrb, T_age) via _effective_LivPrb_scalar.
    """
    beta = float(agent.DiscFac)
    Rfree = _first_scalar(agent.Rfree)
    CRRA = float(agent.CRRA)
    PermGroFac = _first_scalar(agent.PermGroFac)
    L_raw = _first_scalar(agent.LivPrb)
    if L_eff is None:
        L_eff = _effective_LivPrb_scalar(L_raw, getattr(agent, 'T_age', None))
    L_eff = float(L_eff)

    emp = agent.IncShkDstn[0][0]
    psi_atoms = np.asarray(emp.atoms[0], dtype=float).ravel()
    psi_pmv = np.asarray(emp.pmv, dtype=float).ravel()

    try:
        alpha = kesten_alpha(beta * L_raw / L_eff, Rfree, CRRA, PermGroFac,
                             L_eff, psi_atoms, psi_pmv)
    except ValueError as exc:
        # Subcritical (tail thinner than any power law) or near-degenerate
        # spread (root beyond alpha_max): legit no-power-tail regimes -->
        # per-atom DISABLE (note section 6, guard 1).
        return {'enabled': False, 'reason': f'kesten_alpha: {exc}'}

    lo, hi = ALPHA_BAND
    if not (lo < alpha < hi):
        return {'enabled': False,
                'reason': (f'alpha={alpha:.4f} outside the plausibility band '
                           f'({lo}, {hi}) -- treat as no-power-tail '
                           f'(note section 6; e.g. beta~0.9 atoms give '
                           f'root ~57)')}

    # pat_num = (R*beta*L_raw)^(1/rho) -- the asymptotic-slope numerator:
    # kappa = 1 - pat_num/R is the solved cFunc's asymptotic MPC and
    # m_s(jp, s) = (1 - kappa)*R / (Gamma_jp * psi_s) = pat_num/(Gamma_jp*psi_s)
    # (note section 1; R uniform across micro states, guarded by the caller).
    pat_num = (Rfree * beta * L_raw) ** (1.0 / CRRA)
    kappa = 1.0 - pat_num / Rfree
    return {
        'enabled': True,
        'alpha': float(alpha),
        'alpha_source': 'kesten-split(T_age)',
        'pat_num': float(pat_num),
        'kappa': float(kappa),
        'L_eff': L_eff,
        'L_raw': float(L_raw),
    }


def landing_node_weights(alpha, m, dist_aGrid):
    """Conditional-on-return landing weights on the grid nodes (sum = 1).

    THE builder formula (note section 2, verified against a 1e7-draw MC
    pushed through the kernel's own searchsorted/clip/linear-weight lottery:
    node masses within <=0.08%, sum exactly 1 to 1e-12).  Conditional on
    returning (a' < X), a' is truncated Pareto(alpha) on [mX, X):

        P(a' > y | return) = ((mX/y)^alpha - m^alpha) / (1 - m^alpha).

    For each grid cell [l, u] intersecting [mX, X) at [l', u']:

        mu_k  = (l'^(-alpha) - u'^(-alpha)) * (mX)^alpha / (1 - m^alpha)
        abar_k = alpha/(alpha-1) * (l'^(1-alpha) - u'^(1-alpha))
                                 / (l'^(-alpha)  - u'^(-alpha))
        node l += mu_k * (u - abar_k)/(u - l)
        node u += mu_k * (abar_k - l)/(u - l)

    sum_k mu_k = 1 exactly (telescoping).  Because the kernel lottery is
    LINEAR in position, lotterying each cell's conditional mean equals the
    exact tent-function integral -- total mass AND the exact first moment of
    the landing distribution are preserved.

    Parameters
    ----------
    alpha : float, > 1 (guaranteed upstream: the ergodicity guard GPF_out < 1
        implies alpha > 1 whenever the root exists -- note section 6 V6a).
    m : float, in (0, 1) strictly (m >= 1 atoms stay entirely in T and must
        not be passed here).
    dist_aGrid : (A,) ascending, dist_aGrid[-1] = X > 0.  X is the tail
        boundary AFTER the mixing auto-repair (which only subdivides -- the
        top value is unchanged).

    Returns
    -------
    (A,) node weights, nonnegative, summing to 1.
    """
    alpha = float(alpha)
    m = float(m)
    grid = np.asarray(dist_aGrid, dtype=float)
    if not alpha > 1.0:
        raise ValueError(f"landing_node_weights needs alpha > 1, got {alpha}")
    if not (0.0 < m < 1.0):
        raise ValueError(
            f"landing_node_weights needs 0 < m < 1, got m={m} "
            f"(m >= 1 atoms stay entirely in T; call sites must not reach here)")
    X = float(grid[-1])
    if X <= 0.0:
        raise ValueError(f"grid top X must be > 0, got {X}")
    # Landing support is [mX, X) with mX > 0 = dist_aGrid[0]: no landing mass
    # can fall off the bottom (note section 2's assert).
    if not m * X > float(grid[0]):
        raise ValueError(
            f"landing support [mX, X) = [{m * X:.6g}, {X:.6g}) does not sit "
            f"above dist_aGrid[0]={float(grid[0]):.6g}")
    stay = m ** alpha
    denom = 1.0 - stay
    if denom <= 0.0:
        # m^alpha rounded to 1: no returning mass to distribute -- callers
        # skip zero return-weight atoms before reaching here.
        raise ValueError(
            f"1 - m^alpha underflowed to {denom} at m={m}, alpha={alpha}: "
            f"no returning mass; treat the atom as stay-all upstream")
    node = np.zeros(len(grid))
    lo_edge = m * X
    for k in range(len(grid) - 1):
        l, u = float(grid[k]), float(grid[k + 1])
        lp, up = max(l, lo_edge), min(u, X)
        if up <= lp or lp <= 0.0:
            continue
        cc_l = lp ** (-alpha)
        cc_u = up ** (-alpha)
        dcc = cc_l - cc_u
        if dcc <= 0.0:
            # Degenerate-width cell at float precision: zero conditional mass.
            continue
        mu = dcc * lo_edge ** alpha / denom
        abar = (alpha / (alpha - 1.0)) \
            * (lp ** (1.0 - alpha) - up ** (1.0 - alpha)) / dcc
        node[k] += mu * (u - abar) / (u - l)
        node[k + 1] += mu * (abar - l) / (u - l)
    return node


def tail_readout_nodes(alpha, X, K=READOUT_K, span=READOUT_SPAN):
    """Expand the tail state into read-out (a, weight) nodes (weights sum to 1).

    Note section 5: K log-spaced truncated-Pareto segments on [X, span*X]
    via the EXISTING `_pareto_segments` (decay_form/disttop_tail_bucket.py --
    reused, not reimplemented; its import is cheap and side-effect free per
    the 2026-07-26 refactor header), PLUS a closed-form TERMINAL ATOM for the
    mass beyond span*X:

        q      = span^(-alpha)              (mass beyond span*X)
        a_term = alpha/(alpha-1) * span * X (its exact conditional mean)

    With the terminal atom the expanded first moment equals the exact Pareto
    mean alpha/(alpha-1)*X at ANY span (note V5: residual <= 2.2e-16).
    Without it, plain truncation discards tail-wealth share span^(1-alpha)
    (11.5% at alpha=1.47, span=100) -- the note's deviation 2 from the
    original sketch.  Every estimand of record wholly contains the tail, so
    the result is K-invariant by mean-exactness (top-0.1% share identical for
    K in {6, 12, 24} vs a K=20000 reference to <1e-6).

    Returns
    -------
    (nodes, weights) : ((K+1,), (K+1,)) -- asset locations (K segment
    conditional means then the terminal atom) and their masses, summing to 1.
    The caller scales weights by the pooled tail mass w_T.
    """
    alpha = float(alpha)
    X = float(X)
    K = int(K)
    span = float(span)
    if not alpha > 1.0:
        raise ValueError(
            f"tail_readout_nodes needs alpha > 1 (finite tail mean; guaranteed "
            f"upstream by the ergodicity guard), got {alpha}")
    if X <= 0.0 or K < 1 or span <= 1.0:
        raise ValueError(
            f"tail_readout_nodes needs X > 0, K >= 1, span > 1; got "
            f"X={X}, K={K}, span={span}")
    seg_m, seg_mean = _pareto_segments_cached()(alpha, X, K, span)
    q = span ** (-alpha)
    a_term = alpha / (alpha - 1.0) * span * X
    nodes = np.concatenate([np.asarray(seg_mean, dtype=float), [a_term]])
    weights = np.concatenate([(1.0 - q) * np.asarray(seg_m, dtype=float), [q]])
    return nodes, weights


_PARETO_SEGMENTS = [None]


def _pareto_segments_cached():
    """Lazy file-path load of decay_form/disttop_tail_bucket._pareto_segments.

    decay_form/ is a plain directory (not a package), so load by path and
    cache in sys.modules -- the same pattern estim_phase2_tm_a uses for the
    tail-bucket module.  The module top is side-effect free (2026-07-26
    refactor header), so this cannot trigger a model build.
    """
    if _PARETO_SEGMENTS[0] is not None:
        return _PARETO_SEGMENTS[0]
    mod = sys.modules.get('disttop_tail_bucket')
    if mod is None:
        import importlib.util as _ilu
        path = os.path.join(_HERE, 'decay_form', 'disttop_tail_bucket.py')
        spec = _ilu.spec_from_file_location('disttop_tail_bucket', path)
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['disttop_tail_bucket'] = mod
    _PARETO_SEGMENTS[0] = mod._pareto_segments
    return _PARETO_SEGMENTS[0]
