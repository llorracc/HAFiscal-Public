"""Unconstrained (theta-space) parameterization of the Step-1 search.

Owner rulings 2026-08-18 (plans_local/20260818-1200h_step1-unconstrained-reparameterization_plan.md,
§7): D1 = full theta for find_Opt AND find_Opt_splurge0; D2 = logit(splurge),
log(cap - a_hi), log(nabla); D3 = opt-in behind HAFISCAL_STEP1_PARAM=native|theta,
default native.

    theta = (theta_s, theta_hi, theta_w) in R^3   <->   (splurge, beta, nabla)

        splurge = expit(theta_s)                        in (0, 1)
        a_hi    = cap_eff - exp(theta_hi)               in (-inf, cap_eff)
        nabla   = exp(theta_w)                          in (0, inf)
        beta    = a_hi - kappa * nabla

    where a_hi = beta + kappa*nabla is the TOP discount-factor atom (kappa = the top-atom
    offset, (TypeCount-1)/TypeCount = 6/7 at TypeCount=7 -- see top_atom_offset() in the
    estimator) and cap_eff = cap - CAP_EPS.

WHY THE TOP ATOM AND NOT THE CENTER. The GIC cap binds on the most patient atom, not on
beta: log(cap - beta) would keep the center below the cap while the three atoms above it
crossed. Constraining a_hi < cap constrains every atom, since all are <= a_hi.

WHY THIS REMOVES THE TAPER. Under theta no atom can reach the cap, so the arctan squash
that used to enforce it has nothing to do and is SKIPPED (the estimator gates it on the
mode). The squash's saturation shelf -- slope (2/pi)/(1+z^2), already 0.64 at the band
edge, <13% at z>2, where run-4's above-cap seeds died -- and its band-width knob tau both
disappear from the search. NOTE what does NOT disappear: any barrier map flattens the
objective as it approaches the barrier (d a_hi/d theta_hi = -(cap_eff - a_hi) -> 0). The
gain is that the flat region sits AT the cap rather than tau below it, is smooth rather
than kinked, and there is no bound for the optimizer to probe -- the run-7 dust
(splurge = -5.29e-23 from scipy's bounded line search) was a property of BOUNDED Powell,
which no longer runs at all: with no bounds scipy switches its line search from
_minimize_scalar_bounded to _minimize_scalar_brent (plan §7a F1).

WHY log(nabla) AND NOT A NESTED LOGIT (D2). log(nabla) is directly the log of the reported
dispersion, so its SE is a relative SE; the price is that a_lo = beta - kappa*nabla > minBeta
is not structural. It is not needed structurally: the estimator's own atom floor
(atoms < minBeta are clipped to minBeta, native and theta alike) makes the objective
well-defined for EVERY theta, and today's native box already implied a_lo >= 0.357. The
census reports floor hits so a search that ever relies on the floor is visible.

CAP_EPS -- the one constant, with its derivation. cap_eff = cap - CAP_EPS keeps the most
patient atom a fixed distance short of the GIC boundary. Not for solvability -- EGM's
contraction is governed by the RIC, which is slack -- but for the WEALTH TARGETS:
step1_tm_init.ergodic_joint_moments runs a power iteration whose convergence degrades as
the top type approaches unit root ("the near-unit-root top type makes 1e-12 power
iteration the wall driver"). Native's bounded search already evaluated at cap - 2.7e-5
routinely (beta's 1.1 upper bound pushed through the arctan at tau=0.002 lands there),
so 1e-5 keeps theta-space within a factor ~3 of a regime native visited on every seed,
and never asks for one it did not. The optimum of record sits 2.9e-3 from the cap, 290x
further out, so CAP_EPS is invisible to the estimate. Env-tunable for probing.

PURE FUNCTIONS. cap and kappa are ARGUMENTS, read by the caller from gic_taper_cap() and
top_atom_offset() at call time (base_params is mutated by the CRRA-sensitivity blocks, so
the cap must be read per solve). This module therefore never imports the estimator --
which has no __main__ guard -- and is unit-testable in milliseconds.
"""
import math
import os

import numpy as np
from scipy.special import expit, logit

MODES = ("native", "theta", "mixed")

CAP_EPS = float(os.environ.get("HAFISCAL_STEP1_CAP_EPS", "1e-5"))


def param_mode():
    """The search parameterization. DEFAULT = 'mixed' — the level-splurge COBYQA engine —
    since the owner adoption ruling of 2026-08-19 evening (superseding ruling D3's
    default-native, on the run-13 evidence: 8/8 basin, 7/8 SoR-class polish, 1,380 evals
    for the full battery vs ~10,500 native, corners 163 evals vs ~1,900; decision record
    conclusions_private/2026-08-19_step1-default-cobyqa-adoption.md). 'native' (bounded
    Powell + arctan taper, byte-identical pre-2026-08-18 path) is the ONE-KNOB ROLLBACK
    and remains the engine that produced the S1 estimate of record; 'theta' (fenced
    log-space Powell + fix (c)) stays opt-in. Read from HAFISCAL_STEP1_PARAM at call
    time."""
    m = os.environ.get("HAFISCAL_STEP1_PARAM", "mixed").strip().lower()
    if m not in MODES:
        raise ValueError(f"HAFISCAL_STEP1_PARAM must be one of {MODES}; got {m!r}")
    return m


def cap_eff(cap):
    """The effective ceiling on the top atom: cap - CAP_EPS (see module docstring)."""
    return float(cap) - CAP_EPS


# ---------------------------------------------------------------- 2-D (beta, nabla)

def to_native_bn(theta2, *, cap, kappa):
    """(theta_hi, theta_w) -> (beta, nabla). Used directly by find_Opt_splurge0 (splurge
    pinned to a literal 0 there, never searched) and by the 3-D map below."""
    th_hi, th_w = float(theta2[0]), float(theta2[1])
    a_hi = cap_eff(cap) - math.exp(th_hi)
    nabla = math.exp(th_w)
    beta = a_hi - kappa * nabla
    return beta, nabla


def to_theta_bn(beta, nabla, *, cap, kappa):
    """(beta, nabla) -> (theta_hi, theta_w). Raises on values the map cannot represent as
    FINITE theta -- nabla <= 0, or a top atom at/above cap_eff -- because a search cannot
    start from +-inf. (Values that are merely absurd, e.g. a_lo < minBeta, are representable
    and are NOT rejected here; the estimator's atom floor handles them.)"""
    a_hi = beta + kappa * nabla
    ce = cap_eff(cap)
    if not (nabla > 0.0):
        raise ValueError(f"nabla={nabla!r} must be > 0 to have a finite log-parameter")
    if not (a_hi < ce):
        raise ValueError(f"top atom beta+kappa*nabla={a_hi!r} must be < cap_eff={ce!r} "
                         f"(cap={cap!r}, CAP_EPS={CAP_EPS!r}) to have a finite theta_hi")
    return np.array([math.log(ce - a_hi), math.log(nabla)], dtype=float)


# ---------------------------------------------------------- 3-D (splurge, beta, nabla)

def to_native(theta, *, cap, kappa):
    """theta -> (splurge, beta, nabla). Defined for EVERY finite theta."""
    splurge = float(expit(float(theta[0])))
    beta, nabla = to_native_bn(theta[1:3], cap=cap, kappa=kappa)
    return splurge, beta, nabla


def to_theta(splurge, beta, nabla, *, cap, kappa):
    """(splurge, beta, nabla) -> theta. Raises if splurge is not strictly inside (0, 1)
    (0 and 1 map to -+inf, which a search cannot start from) or if (beta, nabla) is not
    representable -- see to_theta_bn."""
    if not (0.0 < splurge < 1.0):
        raise ValueError(f"splurge={splurge!r} must be strictly inside (0, 1) to have a "
                         f"finite logit; splurge=0 arms pin it as a literal and search "
                         f"(beta, nabla) only (find_Opt_splurge0)")
    bn = to_theta_bn(beta, nabla, cap=cap, kappa=kappa)
    return np.array([float(logit(splurge)), bn[0], bn[1]], dtype=float)


def cap_margin(beta, nabla, *, cap, kappa):
    """cap - a_hi: how far the top atom sits below the (raw) GIC cap. Positive = below."""
    return float(cap) - (beta + kappa * nabla)


def describe(cap, kappa):
    """One-line banner text so every log names the parameterization it ran under."""
    return (f"theta: splurge=expit(t_s), a_hi=cap_eff-exp(t_hi), nabla=exp(t_w), "
            f"beta=a_hi-kappa*nabla; cap={cap:.10f} CAP_EPS={CAP_EPS:g} "
            f"cap_eff={cap_eff(cap):.10f} kappa={kappa:.6f}; taper SKIPPED, "
            f"minBeta atom floor kept")


# ------------------------------------------------------ the cold-multistart grid (SST)

NABLA0_LEVELS = (0.01, 0.05)     # owner rulings 2026-08-17 (two levels) and 2026-08-18 (reaffirmed:
                                 # "0.01 and 0.05, skip the 0.03"); nabla0=0 excluded -- a degenerate
                                 # zero-dispersion knife edge, and log(0) under theta
K_LEVEL_LOW = 0.90               # the low rung of the top-atom ladder (owner ruling 2026-08-17)


def startpoint_grid(splurge_levels, *, cap, kappa, tau, k_levels=None, nabla_levels=NABLA0_LEVELS):
    """The ONE cold-multistart grid, for every Step-1 arm (owner ruling 2026-08-18: "make
    these defaults universal across all branches").

    Cap-relative: beta0 = k*cap - kappa*nabla0, so every seed's TOP atom sits at exactly
    k*cap -- neither nabla row is privileged and none starts on the taper shelf (the
    defect that killed run 4). k_levels default to (1 - 2*tau/cap, K_LEVEL_LOW): the top
    rung clears the taper band by one band-width (owner ruling 2026-08-17, "the strictly
    dimensional form"); under theta the taper does not run but the rung is still a
    sensible seed, 2*tau below the cap. Returns (startpoints, legend): startpoints are
    [splurge0, beta0, nabla0] lists in COST order (cheap nabla tier first, riskiest k
    next, splurge descending -- the run-6/7 ordering); the legend is the exact line
    s1_gate.py parses ("Multistart grid: N startpoints ..."), generated from the grid it
    describes so it cannot drift.

    Callers: the S1 splurge estimation (splurge_levels=(0.01, 0.50)); the S3 Splurge=0 arm
    (splurge_levels=(0.0,) -- splurge pinned, so this yields the 2-D (beta0, nabla0) grid
    with the same k x nabla design); the CRRA-sensitivity block (called INSIDE its loop,
    because the cap depends on CRRA).
    """
    if k_levels is None:
        k_levels = (1.0 - 2.0 * tau / cap, K_LEVEL_LOW)
    order = sorted([(s, k, n) for s in splurge_levels for k in k_levels for n in nabla_levels],
                   key=lambda t: (0 if t[2] >= max(nabla_levels) else 1,   # cheap nabla tier first
                                  -t[1],                                  # riskiest k first (free)
                                  -t[0]))                                 # weakest signal: splurge desc
    startpoints = [[s, k * cap - kappa * n, n] for (s, k, n) in order]
    ks = sorted({k for _, k, _ in order}, reverse=True)
    ns = sorted({n for _, _, n in order})
    ss = sorted({sp for sp, _, _ in order})
    legend = ("Multistart grid: %d startpoints (cap-relative; GICmaxBeta=%.10f, "
              "top-atom offset=%.6f, tau=%.4f, k=(%s)[top=1-2tau/cap], nabla0=(%s), "
              "splurge0=(%s))"
              % (len(startpoints), cap, kappa, tau,
                 ",".join("%.6f" % k for k in ks),
                 ",".join("%g" % n for n in ns),
                 ",".join("%g" % sp for sp in ss)))
    return startpoints, legend


# ------------------------------------------------- the theta SEARCH BOX (opt-in, V4b)

# Region-of-interest ends in NATIVE units. The three "small" ends are the same number on
# purpose: 1e-4 is where a logit/log map is still comfortably responsive (d splurge/d t_s =
# s(1-s) ~ 1e-4; d nabla/d t_w = 1e-4), i.e. NOT saturated. The other ends are native's own
# search box (splurge <= 0.9, beta >= 0.7 => top-atom margin <= cap-0.7, nabla <= 0.4).
BOX_SMALL = 1e-4          # floor on splurge, on nabla, and on the top atom's margin below cap
BOX_SPLURGE_MAX = 0.9
BOX_BETA_MIN = 0.7
BOX_NABLA_MAX = 0.4

# The Step-2 (per-education) nabla end -- BUG-083. Step 1 estimates ONE population-wide
# (beta, nabla) with nabla ~ 0.03, so native's 0.4 never bound there. Step 2 reuses this
# box (owner ruling 2026-08-19: S2 machinery = S1) for each education group separately,
# and for the DROPOUT group under some robustness configurations the data want a wider
# spread: the low-benefits re-estimate (2026-08-20 night) pinned all 4 starts at
# nabla = 0.4000 exactly, with a fit 20x worse than the dropout fit in every other
# configuration (objective 2.20 vs 0.11), and the published appendix reports 0.445 (low
# benefits) and 0.459 (gamma = 3) for that group. The published estimation had no nabla
# bound at all -- it clipped only the top atom at the GIC, which the theta map now does
# structurally -- so a binding search end is a search-procedure artifact, not a model
# choice. 0.55 is the widest end that keeps EVERY discount-factor atom positive when the
# top atom sits at the cap: the N = 7 equiprobable atoms span [a_hi - 2*kappa*nabla, a_hi]
# (kappa = 6/7), so a_lo >= 0 <=> nabla <= a_hi / (2 kappa) = 0.583 a_hi, and the largest
# cap in play is 1.0087 (dropouts; a_lo = 0.066 there at 0.55). The published rows' lowest
# atoms were 0.23 and 0.20, well inside. Owner ruling 2026-08-20 ~22:30 ("follow your
# recommendation"). Step 1's own box is UNCHANGED (BOX_NABLA_MAX above).
BOX_NABLA_MAX_STEP2 = 0.55


def other_crra_values():
    """The Step-1 'other gamma' arm (robustness appendix, gamma rows): the list of CRRA
    values named by HAFISCAL_STEP1_OTHER_CRRA ("1,3" or "1 3"); [] when unset / "0" / "off".
    Each value re-estimates the splurge AND the population (beta, nabla) at that gamma with the
    main arm's machinery (grid, parameterization, GIC cap re-derived at the new gamma), which
    is what the published appendix did (its splurge column moves 0.312 / 0.306 / 0.304 across
    gamma = 1 / 2 / 3). Results: Result_CRRA_<g>.0[_startpoint<i>]_<INTERP>.txt, the names
    Parameters.py resolves for the CRRA1 / CRRA3 parametrizations."""
    raw = os.environ.get("HAFISCAL_STEP1_OTHER_CRRA", "").strip()
    if raw.lower() in ("", "0", "off", "false", "no"):
        return []
    vals = [float(tok) for tok in raw.replace(",", " ").split()]
    for v in vals:
        if not (0.5 <= v <= 10.0):
            raise ValueError(f"HAFISCAL_STEP1_OTHER_CRRA value {v!r} is outside [0.5, 10]")
    return vals


def crra_result_stem(crra):
    """'Result_CRRA_1.0' for gamma = 1 -- the stem Parameters.py reads
    (resolve_path(.../Result_CRRA_{c}.0.txt) for the CRRA1 / CRRA3 parametrizations)."""
    return "Result_CRRA_%.1f" % float(crra)


def step2_nabla_max():
    """The Step-2 nabla search end: HAFISCAL_STEP2_NABLA_MAX, default BOX_NABLA_MAX_STEP2."""
    v = os.environ.get("HAFISCAL_STEP2_NABLA_MAX", "").strip()
    nm = float(v) if v else BOX_NABLA_MAX_STEP2
    if not (BOX_SMALL < nm < 1.0):
        raise ValueError(f"HAFISCAL_STEP2_NABLA_MAX={nm!r} must lie in ({BOX_SMALL}, 1)")
    return nm


def theta_box(*, cap, kappa, nabla_max=None):
    """Finite bounds in theta for scipy Powell -- a SEARCH region, not a domain constraint.

    WHY THIS EXISTS (V4, 2026-08-18 night). With bounds=None scipy's Powell minimises each
    line with unbounded Brent, a LOCAL descent that brackets outward from the current point
    in whichever direction f falls. From the k=0.90 (impatient) startpoints f falls toward
    splurge=0 at first -- the impatient beta already delivers the MPC, and splurge only
    overshoots -- so the very first splurge line search ran the bracket to theta_s ~ -78,
    where expit is 1e-34 and the objective is EXACTLY flat in theta_s (a change of 1e-34 in
    splurge is invisible to f). Once there nothing can bring it back: every later line
    search along theta_s sees identical f and returns; the seed converges to the splurge=0
    conditional optimum (beta 0.9264, nabla 0.0900, f 0.01650, 10x the true minimum) and
    Powell reports success. Four of eight V4 seeds -- ALL four k=0.90 seeds, both
    splurge0 levels -- died this way, against 8/8 converged in the native run 7.

    Native never had this failure because its line searches are BOUNDED (golden-section
    over the whole feasible segment): global along the line, so a seed parked at the
    splurge=0 bound is re-examined across [0, 0.9] each cycle and escapes once beta has
    risen. That robustness came from the bounded routine, and dropping bounds threw it
    away (plan §7a F1 named the routine change; this is what it cost).

    THE FIX is to give Powell finite bounds in theta so it uses the bounded, globally
    sampling line search again -- while KEEPING the log/logit maps (no taper, structural
    cap) and choosing the box so no saturated region is reachable: the floors sit at
    splurge, nabla and top-atom margin = 1e-4, where the maps are still responsive
    (d splurge/d t_s ~ 1e-4). The other ends are native's box. Every grid startpoint is
    inside (k=0.90 has margin ~0.10; splurge0=0.01 >> 1e-4).

    Returns [(t_s_lo, t_s_hi), (t_hi_lo, t_hi_hi), (t_w_lo, t_w_hi)].

    nabla_max: the nabla end in native units; None = BOX_NABLA_MAX (Step 1's box). Step 2
    passes step2_nabla_max() (BUG-083; see BOX_NABLA_MAX_STEP2).
    """
    ce = cap_eff(cap)
    nm = BOX_NABLA_MAX if nabla_max is None else float(nabla_max)
    m_lo, m_hi = BOX_SMALL, float(cap) - BOX_BETA_MIN         # top-atom margin below the RAW cap
    return [(float(logit(BOX_SMALL)), float(logit(BOX_SPLURGE_MAX))),
            (math.log(m_lo - CAP_EPS), math.log(m_hi - CAP_EPS)),  # a_hi = ce - exp(t_hi)
            (math.log(BOX_SMALL), math.log(nm))]


def theta_box_bn(*, cap, kappa, nabla_max=None):
    """The (t_hi, t_w) box for the 2-D arms (Step 1's splurge=0 arm; Step 2 per education)."""
    return theta_box(cap=cap, kappa=kappa, nabla_max=nabla_max)[1:]


def theta_box_enabled():
    """HAFISCAL_STEP1_THETA_BOX=1 turns the box on (default OFF = V4's unbounded search)."""
    return os.environ.get("HAFISCAL_STEP1_THETA_BOX", "0").strip() == "1"


# -------------------------------------------- 'mixed' = level-splurge COBYQA probe
# (owner spec 2026-08-19, refined the same afternoon): ONLY the splurge coordinate
# changes -- it returns to LEVELS with hard bounds [0.0, 0.9], the ZERO end included,
# honored by COBYQA at every evaluation. beta and nabla KEEP their theta forms
# (a_hi = cap_eff - exp(t_hi), beta = a_hi - kappa*nabla; nabla = exp(t_w)), so the
# finite-ergodic-wealth cap stays STRUCTURAL in the map and no optimizer constraint is
# needed (COBYQA's ability to carry the cap as a nonlinear constraint was verified and
# is documented in test_step1_mixed_cobyqa.py, but this probe deliberately does not use
# it). Optimizer: scipy COBYQA -- trust-region SQP on quadratic interpolation models,
# joint-direction steps, bounds honored pointwise.
#
# PURPOSE: seed 7 (the one start still lost under fenced log-space Powell) converges
# toward splurge=0, which the logit map can never reach (t_s -> -inf) and the theta box
# can only truncate (floor at 1e-4). In LEVELS, splurge=0 is a feasible point: if the
# probe converges ON the face with the objective genuinely rising in +splurge, the
# splurge~0 basin is a TRUE feature of the problem; if it lifts off and reaches the
# global optimum, the corner failures were a search-procedure artifact.

def to_mixed(splurge, beta, nabla, *, cap, kappa):
    """(splurge, beta, nabla) -> x = (splurge, t_hi, t_w); splurge may be 0 here."""
    bn = to_theta_bn(beta, nabla, cap=cap, kappa=kappa)
    return np.array([float(splurge), bn[0], bn[1]], dtype=float)


def from_mixed(x, *, cap, kappa):
    """x = (splurge, t_hi, t_w) -> (splurge, beta, nabla)."""
    beta, nabla = to_native_bn(x[1:3], cap=cap, kappa=kappa)
    return float(x[0]), beta, nabla


def mixed_bounds(*, cap, kappa):
    """Box for (splurge, t_hi, t_w): splurge in [0.0, 0.9] IN LEVELS (zero included --
    the point of the probe); (t_hi, t_w) reuse the theta box's own components."""
    return [(0.0, BOX_SPLURGE_MAX)] + theta_box_bn(cap=cap, kappa=kappa)
