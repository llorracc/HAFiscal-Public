"""Per-atom ergodic wealth-tail exponents (Component A of the R-c x R-d program).

Context (plans/20260726_dist-grid-top-scoping_plan.md, P3 recommendation):
the POOLED wealth distribution's tail exponent DRIFTS with the measurement
window -- a mixture artifact, not a property of any atom (capstone results,
2026-07-26).  Per (beta, edu) atom, the ergodic tail is a clean single-alpha
Kesten tail, so per-atom dist-grid tops and per-atom analytic tail-buckets
need a per-atom alpha.  This module supplies it three ways:

  kesten_alpha    -- theory root of the atom's Kesten condition (prior/fallback)
  measured_alpha  -- weighted log-log ccdf slope on a wealth window (primary)
  atom_alpha      -- the resolver implementing the standing rule:
                     measured is PRIMARY when a populated window is available;
                     the Kesten root is the prior/fallback
                     (memory: feedback_local_measurement_over_asymptotic_anchors --
                     refuter-hardened asymptotic exponents are not in-range pins)
  atom_dist_top   -- R-b wealth-quantile law X(eps) = (C/eps)**(1/(alpha-1)),
                     the closed-form budgeted dist-grid top (dist_aGrid_max)
                     for one atom

The Kesten condition (conclusions_private/
2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md):

    LivPrb * E[ (Thorn/psi)^alpha ] = 1,      Thorn = (R*beta*LivPrb)**(1/CRRA) / PermGroFac

Derivation of Thorn (why LivPrb sits INSIDE the CRRA root): with no annuities
the Euler equation discounts at DiscFacEff = DiscFac*LivPrb (HARK convention),
so the patient-limit consumption-function slope is 1 - MPCmin =
(R*beta*LivPrb)**(1/CRRA)/R and the per-survivor normalized-wealth multiplier
in the deep tail is

    M = R*(1 - MPCmin) / (PermGroFac*psi) = (R*beta*LivPrb)**(1/CRRA) / (PermGroFac*psi)
      = Thorn/psi.

The OUTER LivPrb in the condition is population culling (survival thins the
tail cohort at rate 1-LivPrb each period); the INNER LivPrb is discounting.
They are different objects and both belong.

Numerical disambiguation on the GIC-cap College atom ledger
(beta=1.00537, R=1.01, CRRA=2, PermGroFac=1.00490, LivPrb=1-1/160,
sigma_psi^2=0.003; 7-point equiprobable mean-one lognormal psi):

    LivPrb inside the root (mortality_in_discount=True,  default): alpha = 1.779
        (exact-lognormal caricature 1.70 -- the conclusions-doc value; the
        201-point discretization gives 1.703)
    LivPrb outside only    (mortality_in_discount=False):          alpha = 1.099

Only the default reproduces the documented caricature ~1.70 and the ledger row
"certainty-equivalent patience (R*beta*L)^(1/2)/Gamma = -0.037%".  The naive
reading is kept as an option purely so the disambiguation stays testable
(test_per_atom_alpha.py pins both numbers).

Regime map for kesten_alpha (which inputs return / raise what):

  max(M) > 1, LivPrb < 1
      -> unique positive root (returned).  f(alpha) = L*E[M^alpha] is convex,
         f(0) = L < 1, f -> inf; the {f<1} set is an interval containing 0.
  max(M) > 1, LivPrb = 1, E[log M] < 0
      -> unique positive root (classic mortality-free Kesten regime).
  LivPrb = 1, E[log M] >= 0
      -> ValueError "positive log-drift".  The cap-atom-without-mortality
         regime: f(0)=1 and f is increasing at 0, so f>1 for all alpha>0.
         Survivors accumulate without bound; mortality is the ENTIRE tail
         stabilizer (impatience -0.037% is a spectator vs Jensen +0.30% and
         mortality -0.625% -- the conclusions-doc quarterly ledger).
  max(M) <= 1  (subcritical: drift strongly down, no growth event at all)
      -> ValueError "subcritical".  M^alpha <= 1 for alpha>=0, so
         f(alpha) <= L <= 1 with no upward crossing: the ergodic tail decays
         FASTER than any power law (alpha effectively +inf).  Callers should
         size such atoms' dist grids by bulk quantiles, not by tail law.
  root would exceed alpha_max
      -> ValueError.  Near-degenerate psi spread; a power-tail description is
         meaningless at such exponents, treat as no-power-tail like the
         subcritical case.

New code lives in Code/HA-Models/ (standing rule: no new files in
FromPandemicCode/).  Pure numpy+scipy; imports no HAFiscal/HARK modules and
reads no environment flags, so importing it cannot perturb the default
reproduction path.
"""

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp

__all__ = [
    "equiprobable_mean_one_lognormal",
    "kesten_alpha",
    "measured_alpha",
    "atom_alpha",
    "atom_dist_top",
]

# Beyond any physically meaningful wealth-tail exponent (this repo's atoms live
# in roughly [0.2, 5]; the empirical US wealth tail is ~1.5).  Reaching it means
# the psi spread is nearly degenerate and a power-tail description is useless.
_ALPHA_MAX_DEFAULT = 256.0

# Same floor as the R-d prototype's fit-window guard
# (decay_form/disttop_tail_bucket.py): fewer knots than this cannot support a
# meaningful two-parameter log-log fit on TM lottery grids.
_MIN_WINDOW_KNOTS = 5


def equiprobable_mean_one_lognormal(sigma_sq, n=7):
    """n-point equiprobable discretization of a mean-one lognormal shock.

    log psi ~ N(-sigma_sq/2, sigma_sq)  (so E[psi] = 1 exactly).

    Atom i is the conditional mean on the i-th probability-1/n quantile
    interval: with s = sqrt(sigma_sq) and z_i the standard-normal quantile
    boundaries,

        psi_i = n * ( Phi(z_{i+1} - s) - Phi(z_i - s) ),

    (the lognormal partial-expectation identity with E[psi]=1); the increments
    telescope, so sum(pmv*atoms) = 1 EXACTLY -- the same construction HARK's
    equiprobable lognormal approximation uses.

    Returns (atoms, pmv) with pmv uniform at 1/n.
    """
    from scipy.stats import norm

    if sigma_sq < 0:
        raise ValueError(f"sigma_sq must be >= 0, got {sigma_sq}")
    n = int(n)
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if sigma_sq == 0 or n == 1:
        return np.ones(n), np.full(n, 1.0 / n)
    s = float(np.sqrt(sigma_sq))
    z = np.concatenate([[-np.inf], norm.ppf(np.arange(1, n) / n), [np.inf]])
    atoms = n * (norm.cdf(z[1:] - s) - norm.cdf(z[:-1] - s))
    pmv = np.full(n, 1.0 / n)
    return atoms, pmv


def kesten_alpha(beta, Rfree, CRRA, PermGroFac, LivPrb, psi_atoms, psi_pmv,
                 *, mortality_in_discount=True, alpha_max=_ALPHA_MAX_DEFAULT):
    """Positive root alpha of the atom's Kesten tail condition.

        LivPrb * sum_i pmv_i * (Thorn/psi_i)^alpha = 1,
        Thorn = (Rfree*beta*LivPrb)**(1/CRRA) / PermGroFac   [default]

    With mortality_in_discount=False, Thorn = (Rfree*beta)**(1/CRRA)/PermGroFac
    (LivPrb outside only).  The default matches the DiscFacEff = beta*LivPrb
    consumption-slope derivation and reproduces the cap-atom caricature
    alpha ~= 1.70; the naive variant gives ~1.10 on the same ledger -- see the
    module docstring for the full disambiguation and regime map.

    The root is found on g(alpha) = log(LivPrb) + logsumexp(log pmv + alpha*log M),
    M = Thorn/psi: log-space evaluation cannot overflow, and g is convex
    (log-sum-exp of affine functions), so the positive root is unique whenever
    it exists.  Bracketing: double hi until g(hi) > 0, then brentq.

    Raises ValueError (with the regime named) when no positive root exists:
    LivPrb=1 with non-negative log-drift (mortality-free supercritical),
    subcritical atoms (max(Thorn/psi) <= 1, tail thinner than any power law),
    or a root beyond alpha_max (near-degenerate psi spread).
    """
    beta = float(beta)
    Rfree = float(Rfree)
    CRRA = float(CRRA)
    PermGroFac = float(PermGroFac)
    LivPrb = float(LivPrb)
    if not (0.0 < LivPrb <= 1.0):
        raise ValueError(f"LivPrb must be in (0, 1], got {LivPrb}")
    if beta <= 0 or Rfree <= 0 or CRRA <= 0 or PermGroFac <= 0:
        raise ValueError(
            "beta, Rfree, CRRA, PermGroFac must all be > 0; got "
            f"beta={beta}, Rfree={Rfree}, CRRA={CRRA}, PermGroFac={PermGroFac}")

    psi = np.asarray(psi_atoms, dtype=float).ravel()
    pmv = np.asarray(psi_pmv, dtype=float).ravel()
    if psi.shape != pmv.shape or psi.size == 0:
        raise ValueError(
            f"psi_atoms and psi_pmv must be same-shape nonempty 1-D arrays, "
            f"got shapes {psi.shape} and {pmv.shape}")
    if np.any(psi <= 0):
        raise ValueError("psi_atoms must be strictly positive")
    if np.any(pmv < 0) or pmv.sum() <= 0:
        raise ValueError("psi_pmv must be nonnegative with positive total mass")
    keep = pmv > 0
    psi, pmv = psi[keep], pmv[keep] / pmv[keep].sum()

    beta_eff = beta * LivPrb if mortality_in_discount else beta
    thorn = (Rfree * beta_eff) ** (1.0 / CRRA) / PermGroFac
    logM = np.log(thorn) - np.log(psi)
    logp = np.log(pmv)

    def g(alpha):
        # log( LivPrb * E[M^alpha] ); root of g = 0 is the tail exponent.
        return float(np.log(LivPrb) + logsumexp(logp + alpha * logM))

    drift0 = float(np.sum(pmv * logM))  # g'(0) = E[log M]

    if np.max(logM) <= 0.0:
        raise ValueError(
            "no positive root: SUBCRITICAL atom -- max(Thorn/psi) = "
            f"{float(np.exp(np.max(logM))):.6f} <= 1 (Thorn={thorn:.6f}, drift "
            f"E[log M]={drift0:+.6f}), so LivPrb*E[M^alpha] <= LivPrb <= 1 for "
            "all alpha >= 0 and the ergodic tail decays faster than any power "
            "law (alpha effectively +inf); size this atom's dist grid by bulk "
            "quantiles, not by a tail law")

    if LivPrb >= 1.0:
        if drift0 >= 0.0:
            raise ValueError(
                "no positive root: LivPrb=1 with POSITIVE LOG-DRIFT "
                f"(E[log(Thorn/psi)]={drift0:+.6f}, Thorn={thorn:.6f}) -- the "
                "mortality-free supercritical regime: survivors accumulate "
                "without bound and no stationary power tail exists; mortality "
                "is the entire tail stabilizer for such atoms (cap-atom "
                "ledger, conclusions_private/2026-06-16_gic-inside-vs-outside-"
                "individual-target-vs-tm-ergodic.md)")
        # classic mortality-free Kesten: g(0)=0, g dips (drift<0), re-crosses.
        lo = 1e-6
        if g(lo) >= 0.0:
            raise ValueError(
                "no usable positive root: LivPrb=1 with near-zero log-drift "
                f"(E[log M]={drift0:+.2e}) -- degenerate Kesten condition")
    else:
        lo = 0.0  # g(0) = log(LivPrb) < 0

    hi = 1.0
    while g(hi) <= 0.0:
        hi *= 2.0
        if hi > alpha_max:
            raise ValueError(
                f"no positive root below alpha_max={alpha_max}: psi spread too "
                f"small relative to the drift (Thorn={thorn:.6f}, E[log M]="
                f"{drift0:+.6f}); a power-tail description is meaningless at "
                "such exponents -- treat as no-power-tail (bulk-quantile "
                "sizing), like the subcritical regime")

    return float(brentq(g, lo, hi, maxiter=200))


def measured_alpha(a, w, lo, hi, *, min_knots=_MIN_WINDOW_KNOTS):
    """Weighted log-log ccdf slope on the wealth window [lo, hi].

    The PRIMARY per-atom exponent estimate (standing rule: local measurement
    over asymptotic anchors).  Same construction as the R-d prototype's fit
    window (decay_form/disttop_tail_bucket.py, reimplemented here -- that file
    is a standalone script whose import would trigger a model build):

        ccdf_i = P(A >= a_i) = 1 - cumsum(w)_i + w_i     (a sorted ascending)
        alpha  = -slope of ordinary least squares log(ccdf) on log(a)
                 over knots in [lo, hi]

    a, w: wealth knots and their (unnormalized OK) ergodic weights.
    Raises ValueError when the window holds fewer than min_knots usable knots
    (ties in `a` are kept as-is, matching the prototype) or when the fitted
    slope is non-decaying (alpha <= 0) -- callers (atom_alpha) treat that as
    "window not populated" and fall back to the Kesten prior.
    """
    a = np.asarray(a, dtype=float).ravel()
    w = np.asarray(w, dtype=float).ravel()
    if a.shape != w.shape or a.size == 0:
        raise ValueError(
            f"a and w must be same-shape nonempty 1-D arrays, got {a.shape} "
            f"and {w.shape}")
    lo = float(lo)
    hi = float(hi)
    if not (0.0 < lo < hi):
        raise ValueError(f"need 0 < lo < hi, got lo={lo}, hi={hi}")
    if np.any(w < 0) or w.sum() <= 0:
        raise ValueError("w must be nonnegative with positive total mass")
    wn = w / w.sum()
    order = np.argsort(a)
    asort = a[order]
    wsort = wn[order]
    ccdf = 1.0 - np.cumsum(wsort) + wsort  # P(A >= a_i)
    win = (asort >= lo) & (asort <= hi) & (ccdf > 0.0) & (asort > 0.0)
    n_win = int(win.sum())
    if n_win < min_knots:
        raise ValueError(
            f"fit window [{lo}, {hi}] too thin: {n_win} usable knots < "
            f"min_knots={min_knots}")
    slope, _ = np.polyfit(np.log(asort[win]), np.log(ccdf[win]), 1)
    alpha = -float(slope)
    if alpha <= 0.0:
        raise ValueError(
            f"non-decaying ccdf on window [{lo}, {hi}] (fitted alpha="
            f"{alpha:.4f} <= 0): not a tail measurement")
    return alpha


def atom_alpha(beta, Rfree, CRRA, PermGroFac, LivPrb, psi_atoms, psi_pmv,
               a=None, w=None, lo=None, hi=None,
               *, mortality_in_discount=True, min_knots=_MIN_WINDOW_KNOTS):
    """Resolve one atom's tail exponent: MEASURED primary, Kesten prior/fallback.

    Standing rule (feedback_local_measurement_over_asymptotic_anchors): the
    locally measured exponent is primary whenever an ergodic sample (a, w) and
    a populated window [lo, hi] are available; the Kesten root is the
    theory prior (no sample given) or the fallback (window unusable).

    Returns (alpha, source_str) with source_str one of
        "measured"                  -- log-log ccdf slope on [lo, hi]
        "kesten-prior"              -- no (a, w, lo, hi) sample provided
        "kesten-fallback(<reason>)" -- sample provided but the measurement
                                       failed; <reason> is the ValueError text
    Raises ValueError when every applicable route fails (message names both
    failures when a sample was provided).
    """
    have_sample = a is not None and w is not None and lo is not None and hi is not None
    if have_sample:
        try:
            return (measured_alpha(a, w, lo, hi, min_knots=min_knots),
                    "measured")
        except ValueError as e_meas:
            try:
                alpha = kesten_alpha(
                    beta, Rfree, CRRA, PermGroFac, LivPrb, psi_atoms, psi_pmv,
                    mortality_in_discount=mortality_in_discount)
            except ValueError as e_kest:
                raise ValueError(
                    "atom_alpha: both routes failed -- measured: "
                    f"[{e_meas}]; kesten: [{e_kest}]") from e_kest
            return alpha, f"kesten-fallback({e_meas})"
    alpha = kesten_alpha(
        beta, Rfree, CRRA, PermGroFac, LivPrb, psi_atoms, psi_pmv,
        mortality_in_discount=mortality_in_discount)
    return alpha, "kesten-prior"


def atom_dist_top(alpha, C_calib, eps):
    """R-b wealth-quantile law: the budgeted dist-grid top for one atom.

        X(eps) = (C_calib/eps)**(1/(alpha-1))

    Derivation: a Pareto(alpha) ergodic tail carries wealth share
    ~ C * T^(1-alpha) above T (the plan's P1 law; C_calib is the atom's
    calibration constant, e.g. fitted from the measured tail so that the
    known wealth share above a reference top is reproduced).  Requiring the
    truncated share <= eps and inverting gives X(eps).  This sizes the
    dist-grid top (dist_aGrid_max) on the CORRECT integrand -- wealth, which
    the Lorenz/E[a]/top-share metrics integrate -- replacing the population-
    mass quantile proxy (plans/20260726_dist-grid-top-scoping_plan.md, P0/R-b).

    Guard alpha > 1: at alpha <= 1 the tail wealth integral diverges (infinite
    mean), the truncated share never falls below eps, and no finite top
    satisfies the budget -- such atoms need the analytic tail-bucket (R-d),
    not a taller grid.  No cap is applied on the return value: an enormous
    X(eps) for alpha near 1 is the honest answer ("grid-height warfare is
    unwinnable" -- capstone), and the caller decides grid vs bucket.
    """
    alpha = float(alpha)
    C_calib = float(C_calib)
    eps = float(eps)
    if not alpha > 1.0:
        raise ValueError(
            f"atom_dist_top needs alpha > 1, got alpha={alpha}: at alpha <= 1 "
            "the tail wealth integral diverges and no finite dist-grid top "
            "meets any wealth-share budget -- use the analytic tail-bucket "
            "(R-d) for this atom")
    if C_calib <= 0.0:
        raise ValueError(f"C_calib must be > 0, got {C_calib}")
    if eps <= 0.0:
        raise ValueError(f"eps must be > 0, got {eps}")
    return float((C_calib / eps) ** (1.0 / (alpha - 1.0)))


if __name__ == "__main__":
    # Cap-atom ledger demo (the module docstring's disambiguation, executable).
    _atoms, _pmv = equiprobable_mean_one_lognormal(0.003, 7)
    _args = (1.00537, 1.01, 2.0, 1.00490, 1.0 - 1.0 / 160.0, _atoms, _pmv)
    print("cap-atom ledger, 7-pt equiprobable mean-one lognormal psi:")
    print(f"  kesten_alpha (LivPrb in discount, default) = "
          f"{kesten_alpha(*_args):.4f}   [caricature ~1.70]")
    print(f"  kesten_alpha (naive, LivPrb outside only)  = "
          f"{kesten_alpha(*_args, mortality_in_discount=False):.4f}")
    _a21, _ = atom_alpha(*_args)
    print(f"  atom_alpha with no sample -> {_a21:.4f} (kesten-prior)")
