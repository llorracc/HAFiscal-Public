"""R-d: analytic Pareto tail-bucket read-out correction for the dist grid.

plans/20260726_dist-grid-top-scoping_plan.md (capstone amendment + the
R-c x R-d per-atom recommendation).

WHY. The TM lottery PILES all ergodic mass above the grid top into the top
node -- the mass total is right but its location is wrong, which truncates the
wealth integrals (Lorenz, E[a], top shares). Grid-height cannot fix this for
the cap-atom tail (measured deep decay X^(-b), b~0.3-0.6: halving the error
costs ~5x in top). Instead: REDISTRIBUTE the top-node pile as a discretized
Pareto tail and recompute the moments.

PER-ATOM (the 2026-07-26 v1->v3 lesson). Applied to the POOLED distribution,
every variant fails the two-sided validation: the pooled tail exponent DRIFTS
with window height (mixture artifact -- alpha_local ~2.2 in the 300-1300
window falling toward the cap atom's ~1.5 in 1300-6000), so 'pile'
under-corrects (+0.80% vs raw-6000, consistency FAIL 1.2%) and 'anchored'
over-corrects (-3.18%, consistency FAIL 1.4%). Applied PER ATOM, each ergodic
tail is a clean single-alpha Kesten tail -- alpha solves
L * E[(Thorn_Gamma/psi)^alpha] = 1 (LivPrb inside the condition; no positive
root at L=1 -- mortality is the entire tail stabilizer, see
conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md)
-- so the two variants should nearly AGREE. That agreement is a battery gate,
which is why BOTH variants are kept importable. Exponent policy: the atom's
own MEASURED tail alpha is primary; the Kesten root (per_atom_alpha.py,
component A) is prior/fallback (standing rule
[[feedback_local_measurement_over_asymptotic_anchors]]; cap-atom ledger:
lognormal caricature alpha~1.70, measured deep alpha~1.5).

REFACTOR (2026-07-26, dist-top plan component C): the module top is now
side-effect free and cheap to import -- `apply_tail_bucket` /
`resolve_atom_alpha` are consumed lazily by
FromPandemicCode/estim_phase2_tm_a.py under HAFISCAL_DIST_TAIL_BUCKET
(default off = byte-identical). The heavy CLI machinery (env pins, chdir,
`import estim_phase2_tm_a` -- which SOLVES the economy at import time) moved
into main() under the __main__ guard. CLI usage is unchanged.

VALIDATION (falsifiable, two-sided; battery in the session scratchpad,
peratom/battery.sh + battery_analyze.py):
  1. corrected(top=1300) must move TOWARD raw(top=6000) -- closing most of the
     measured ~2.5% raw College Lorenz gap;
  2. corrected(1300) must agree with corrected(6000) (consistency: if the
     bucket is right, the answer must not depend on where the grid stops);
  3. per-atom 'pile' vs 'anchored' must nearly agree (the pooled-mixture
     drift that split them is gone).

Usage: python disttop_tail_bucket.py <top> <outdir>   # e.g. 1300 /tmp/x
"""
import os
import sys

import numpy as np

ALPHA_CAP = 1.47          # cap-atom Kesten root: the PINNED deep-tail exponent
N_TAIL_NODES = 12         # discretized Pareto segments above the grid top
TAIL_SPAN = 100.0         # bucket reaches TAIL_SPAN * x_top (log-spaced)

# measured-alpha plausibility band: outside it the local fit is treated as
# failed and the caller falls back (Kesten root, else skip). Thin/impatient
# atoms measure near-exponential tails (huge alpha_hat) where the bucket is
# immaterial anyway; alpha <= 1 would mean an infinite-mean tail.
ALPHA_MEASURED_BAND = (1.05, 12.0)

# default local fit window on the atom's own ergodic, as fractions of x_top:
# [x_top/6, x_top/2] -- high enough to be in the tail, capped at x_top/2 so
# the top-node pile never contaminates the fit.
MEASURE_WINDOW = (1.0 / 6.0, 1.0 / 2.0)

_PAA_WARNED = [False]     # warn-once latch for the per_atom_alpha fallback


def _pareto_segments(alpha, x_top, n_nodes, span):
    """Discretized truncated Pareto(alpha) on [x_top, span*x_top].

    Returns (seg_m, seg_mean): segment masses (sum 1) and the conditional mean
    asset level of each segment. Shared by both bucket variants.
    """
    edges = np.geomspace(x_top, span * x_top, n_nodes + 1)
    cc = edges ** (-alpha)
    cc = (cc - cc[-1]) / (cc[0] - cc[-1])           # truncated ccdf 1 -> 0
    seg_m = -np.diff(cc)                            # segment masses, sum = 1
    if abs(alpha - 1.0) < 1e-9:
        seg_mean = np.sqrt(edges[:-1] * edges[1:])
    else:
        k = alpha / (alpha - 1.0)
        num = edges[:-1] ** (1 - alpha) - edges[1:] ** (1 - alpha)
        den = edges[:-1] ** (-alpha) - edges[1:] ** (-alpha)
        seg_mean = k * num / den                    # conditional mean per segment
    return seg_m, seg_mean


def apply_tail_bucket(a, w, alpha, x_top, n_nodes=N_TAIL_NODES, span=TAIL_SPAN,
                      variant='pile'):
    """Replace the top-node pile of (a, w) with an analytic Pareto tail.

    Parameters
    ----------
    a, w : array-like
        Asset nodes and their (not necessarily normalized) masses. Need not be
        sorted; sorted internally. Intended unit of application: ONE atom's
        marginal ergodic distribution (per-atom alpha is the whole point), but
        pooled inputs are accepted (the CLI prototype mode).
    alpha : float
        Tail exponent of the redistribution law -- the atom's own measured
        alpha (primary) or Kesten root (fallback); see resolve_atom_alpha.
    x_top : float
        The dist-grid top (dist_aGrid_max) of THIS distribution -- nodes at
        >= 0.999*x_top are treated as the (possibly piled) top node.
    n_nodes, span : int, float
        Tail discretization: n_nodes log-spaced segments on [x_top, span*x_top].
    variant : 'pile' | 'anchored'
        'pile'     -- redistribute the top node's EXCESS mass (measured pile
                      minus the fitted-law legitimate cell mass) into the tail.
        'anchored' -- size the tail from the INTERIOR ccdf at A0=x_top/2
                      extrapolated with alpha (restores mass the truncated
                      dynamics re-circulated downward), remove it from the
                      interior, zero the pile into the tail.

    Returns
    -------
    (a_new, w_new, diag) with sum(w_new) == sum(w) (MASS-PRESERVING -- callers
    pooling several atoms need no renormalization surprises; conservative
    no-op branches return the inputs unchanged with a diag note).
    """
    a = np.asarray(a, dtype=float)
    w = np.asarray(w, dtype=float)
    if variant == 'pile':
        return _bucket_pile(a, w, float(alpha), float(x_top), int(n_nodes), float(span))
    if variant == 'anchored':
        return _bucket_anchored(a, w, float(alpha), float(x_top), int(n_nodes), float(span))
    raise ValueError(f"unknown tail-bucket variant {variant!r} (use 'pile' or 'anchored')")


def _bucket_pile(a, w, alpha, x_top, n_nodes, span):
    """Redistribute the top-node pile as a truncated Pareto(alpha) above x_top.

    Pile estimate: the fitted cell mass at the top node, from the ccdf law
    calibrated on the [x_top/6, x_top/2] window, is what the top node WOULD
    carry without pile-up; the excess is the pile. Conservative: if the fit
    fails or the excess is <=0, return inputs unchanged.
    """
    W_in = float(w.sum())
    if W_in <= 0:
        return a, w, {"variant": "pile", "note": "zero total mass"}
    order = np.argsort(a)
    asort = a[order]
    wsort = w[order] / W_in
    top_mask = asort >= x_top * 0.999
    m_top = float(wsort[top_mask].sum())
    if m_top <= 0:
        return a, w, {"variant": "pile", "note": "no top mass"}
    if top_mask.all():
        return a, w, {"variant": "pile", "note": "all mass at top"}
    ccdf = 1.0 - np.cumsum(wsort) + wsort          # P(A >= a_i), sorted
    win = (asort >= x_top / 6.0) & (asort <= x_top / 2.0) & (ccdf > 0)
    if win.sum() < 5:
        return a, w, {"variant": "pile", "note": "fit window too thin"}
    slope, icpt = np.polyfit(np.log(asort[win]), np.log(ccdf[win]), 1)
    alpha_fit = -slope
    # Decomposition of the measured top-node mass m_top under the fitted law:
    #   m_top  ~=  P(a_prev < a <= x_top)  +  P(a > x_top)
    #              [legit cell mass]          [the PILE the lottery clipped in]
    # v1 BUG (2026-07-26, "no excess detected" no-op): excess was computed as
    # m_top - ccdf_fit(a_prev), i.e. m_top minus (legit + pile) ~= 0 by
    # construction. The pile is ccdf_fit(x_top); legit is the DIFFERENCE.
    # v4 refactor note (2026-07-26, component C): a_prev was previously taken
    # as a[order][~unsorted_mask].max() -- an unsorted-aligned mask applied to
    # the SORTED array. On pooled (interleaved) inputs with >=2 top-reaching
    # slices that evaluated to x_top itself, so legit_fit collapsed to 0 and
    # the recorded v2 arms effectively redistributed the FULL top node. Fixed
    # by sorting once at entry (this function); pooled-CLI 'pile' numbers
    # shift slightly (more conservative); single-atom sorted inputs -- the
    # per-atom production use -- were never affected.
    a_prev = float(asort[~top_mask].max())
    ccdf_fit = lambda x: float(np.exp(icpt + slope * np.log(x)))
    legit_fit = max(ccdf_fit(a_prev) - ccdf_fit(x_top), 0.0)
    excess = max(m_top - legit_fit, 0.0)           # pile beyond the top node
    legit = m_top - excess
    if excess <= 0:
        return a, w, {"variant": "pile", "alpha_fit": float(alpha_fit),
                      "note": "no excess detected"}
    seg_m, seg_mean = _pareto_segments(alpha, x_top, n_nodes, span)
    a_new = np.concatenate([asort[~top_mask], [x_top], seg_mean])
    w_new = np.concatenate([wsort[~top_mask], [legit], excess * seg_m]) * W_in
    return a_new, w_new, {"variant": "pile", "alpha_fit": float(alpha_fit),
                          "m_top": m_top, "excess": float(excess),
                          "alpha_used": float(alpha)}


def _bucket_anchored(a, w, alpha, x_top, n_nodes, span):
    """Anchored variant: size the pile from the INTERIOR ccdf, not the top node.

    v2 finding (2026-07-26): the top-node pile under-counts the true tail mass --
    truncated dynamics re-circulate would-be-tail agents DOWNWARD, so trusting
    m_top inherits the loss (65% gap closure, consistency fail at 1.2%). Anchor
    instead at A0 = x_top/2 (inside the trusted region), extrapolate
    P(a > x_top) = P(a > A0) * (A0/x_top)^alpha with the passed alpha, remove the
    difference proportionally from the interior (where re-circulation parked it),
    and lay the tail segments carrying the anchored mass.

    v4 refactor (2026-07-26, component C) -- mass-preservation guards added:
      * if the pinned law implies LESS tail mass than the pile (p_tail < m_top),
        the surplus now STAYS at the top node instead of silently vanishing;
      * if the interior cannot absorb the added mass, conservative no-op.
    The mainline case (add > 0, absorbable) is unchanged from the recorded v3.
    """
    W_in = float(w.sum())
    if W_in <= 0:
        return a, w, {"variant": "anchored", "note": "zero total mass"}
    order = np.argsort(a)
    asort = a[order]
    wsort = w[order] / W_in
    top_mask = asort >= x_top * 0.999
    m_top = float(wsort[top_mask].sum())
    A0 = x_top / 2.0
    p_anchor = float(wsort[asort > A0].sum())      # empirical ccdf at the anchor
    if p_anchor <= 0:
        return a, w, {"variant": "anchored", "note": "empty anchor"}
    p_tail = p_anchor * (A0 / x_top) ** alpha      # power-law extrapolation
    add = max(p_tail - m_top, 0.0)                 # dynamics-lost mass to restore
    interior = (~top_mask) & (asort > A0)
    int_sum = float(wsort[interior].sum())
    if add > 0 and int_sum <= add:
        return a, w, {"variant": "anchored", "note": "interior too thin to absorb",
                      "p_tail": float(p_tail), "m_top": m_top}
    seg_m, seg_mean = _pareto_segments(alpha, x_top, n_nodes, span)
    w_new = wsort.copy()
    if add > 0:
        # remove `add` proportionally from interior nodes in (A0, x_top) -- where
        # the re-circulated mass parked -- then lay the tail carrying p_tail total
        w_new[interior] *= (int_sum - add) / int_sum
    surplus = max(m_top - p_tail, 0.0)             # pile exceeding the pinned law
    w_new[top_mask] = 0.0
    a_new = np.concatenate([asort, [x_top], seg_mean])
    w_new = np.concatenate([w_new, [surplus], p_tail * seg_m]) * W_in
    return a_new, w_new, {"variant": "anchored", "m_top": m_top,
                          "p_anchor": p_anchor, "p_tail": float(p_tail),
                          "added": float(add), "surplus": float(surplus),
                          "alpha_used": float(alpha)}


# ---- back-compat wrappers (pre-refactor names; CLI + external notebooks) ----

def _bucket_correct(a, w, alpha, x_top):
    return apply_tail_bucket(a, w, alpha, x_top, variant='pile')


def _bucket_correct_anchored(a, w, alpha, x_top):
    return apply_tail_bucket(a, w, alpha, x_top, variant='anchored')


# ---- per-atom exponent policy: measured primary, Kesten prior/fallback ----

def measured_alpha(a, w, x_top, window=MEASURE_WINDOW, min_points=5):
    """Local tail exponent measured on the atom's own ergodic top window.

    Fits -d log ccdf / d log a on [window[0]*x_top, window[1]*x_top] (the pile
    at the top node is excluded by window[1] <= 1/2). Returns (alpha, diag);
    alpha is None when the window is too thin or the fit falls outside
    ALPHA_MEASURED_BAND. Standing rule: this measured value is PRIMARY, the
    Kesten root is prior/fallback
    ([[feedback_local_measurement_over_asymptotic_anchors]]).
    """
    a = np.asarray(a, dtype=float)
    w = np.asarray(w, dtype=float)
    W_in = float(w.sum())
    if W_in <= 0:
        return None, {"note": "zero total mass"}
    order = np.argsort(a)
    asort = a[order]
    wsort = w[order] / W_in
    ccdf = 1.0 - np.cumsum(wsort) + wsort
    win = (asort >= x_top * window[0]) & (asort <= x_top * window[1]) & (ccdf > 0)
    n_win = int(win.sum())
    if n_win < min_points:
        return None, {"note": "fit window too thin", "n_win": n_win}
    slope, _ = np.polyfit(np.log(asort[win]), np.log(ccdf[win]), 1)
    alpha_hat = float(-slope)
    lo, hi = ALPHA_MEASURED_BAND
    if not np.isfinite(alpha_hat) or not (lo < alpha_hat < hi):
        return None, {"note": "fit outside plausibility band",
                      "alpha_hat": alpha_hat, "n_win": n_win}
    return alpha_hat, {"alpha_hat": alpha_hat, "n_win": n_win}


def _import_per_atom_alpha():
    """Lazy, defensive import of component A's Code/HA-Models/per_atom_alpha.py.

    Tries a plain import (works when HA-Models is on sys.path, as in the
    estim_phase2_tm_a caller), then a path-based load relative to this file.
    Returns the module or None (caller warns once and stays measured-only).
    """
    try:
        import per_atom_alpha as _paa
        return _paa
    except Exception:
        pass
    try:
        import importlib.util as _ilu
        cand = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'per_atom_alpha.py')
        if os.path.isfile(cand):
            spec = _ilu.spec_from_file_location('per_atom_alpha', cand)
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            sys.modules.setdefault('per_atom_alpha', mod)
            return mod
    except Exception:
        pass
    return None


def _first_scalar(x):
    """First scalar of a possibly time-varying HARK parameter (scalar/list/array)."""
    return float(np.asarray(x, dtype=float).ravel()[0])


def _kesten_alpha_from_module(agent):
    """Kesten-root fallback via per_atom_alpha.py (component A), defensively.

    The per-atom exponent solves L * E[(Thorn/psi)^alpha] = 1 (no positive
    root at L=1 -- mortality stabilizes the tail). Component A's API
    (`kesten_alpha(beta, Rfree, CRRA, PermGroFac, LivPrb, psi_atoms,
    psi_pmv)`) takes calibration parameters, extracted here from the agent;
    it RAISES ValueError for atoms with no positive root (e.g. subcritical
    thin atoms -- tail thinner than any power law), which correctly maps to
    "skip the bucket" (return None). If the module is absent or incompatible
    this warns once and the caller stays measured-only, so this file works
    standalone.
    """
    mod = _import_per_atom_alpha()
    if mod is None:
        if not _PAA_WARNED[0]:
            print("WARNING [disttop_tail_bucket]: per_atom_alpha.py (component A) "
                  "not importable -- Kesten fallback unavailable, running "
                  "measured-only alpha policy", flush=True)
            _PAA_WARNED[0] = True
        return None
    fn = getattr(mod, 'kesten_alpha', None)
    if callable(fn) and agent is not None:
        try:
            beta = float(agent.DiscFac)
            Rfree = _first_scalar(agent.Rfree)
            CRRA = float(agent.CRRA)
            PermGroFac = _first_scalar(agent.PermGroFac)
            LivPrb = _first_scalar(agent.LivPrb)
            # employed-state joint (psi, theta) discretization: atoms row 0 is
            # the permanent shock; the joint pmv gives the correct marginal
            # expectation E[(Thorn/psi)^alpha] (psi values repeat across theta).
            emp = agent.IncShkDstn[0][0]
            psi_atoms = np.asarray(emp.atoms[0], dtype=float).ravel()
            psi_pmv = np.asarray(emp.pmv, dtype=float).ravel()
            val = float(fn(beta, Rfree, CRRA, PermGroFac, LivPrb,
                           psi_atoms, psi_pmv))
            if np.isfinite(val) and 1.0 < val < 20.0:
                return val
            return None
        except ValueError:
            return None       # no positive root for this atom: legit, skip
        except Exception:
            pass              # unexpected shape/attr mismatch: try probes below
    # secondary probe: agent-taking convenience APIs a later version may add
    for name in ("kesten_alpha_for_agent", "alpha_for_agent",
                 "atom_alpha_for_agent"):
        fn2 = getattr(mod, name, None)
        if not callable(fn2):
            continue
        try:
            val = float(fn2(agent))
        except Exception:
            continue
        if np.isfinite(val) and 1.0 < val < 20.0:
            return val
    if not _PAA_WARNED[0]:
        print("WARNING [disttop_tail_bucket]: per_atom_alpha.py present but its "
              "kesten-alpha API could not be used for this agent -- "
              "measured-only alpha policy", flush=True)
        _PAA_WARNED[0] = True
    return None


def resolve_atom_alpha(a, w, x_top, agent=None, window=MEASURE_WINDOW):
    """Per-atom exponent policy (plan section R-c x R-d + the standing rule).

    1. MEASURED on the atom's own ergodic top window (primary);
    2. Kesten root from per_atom_alpha.py, component A (prior/fallback) --
       lazy + defensive: absent module => warn once, measured-only;
    3. (None, None) => caller should SKIP the bucket for this atom (the
       conservative no-op; thin atoms carry ~zero top-node mass anyway).

    Returns (alpha_or_None, source) with source in {'measured', 'kesten', None}.
    """
    alpha_hat, _diag = measured_alpha(a, w, x_top, window=window)
    if alpha_hat is not None:
        return alpha_hat, 'measured'
    if agent is not None:
        k = _kesten_alpha_from_module(agent)
        if k is not None:
            return k, 'kesten'
    return None, None


# ---- moments (CLI + battery analysis convenience) ----

def _moments(a, w):
    from HARK.utilities import get_percentiles, get_lorenz_shares
    a = np.asarray(a, float); w = np.asarray(w, float); w = w / w.sum()
    Ea = float(np.sum(w * a))
    out = {"E_a": Ea,
           "medianLWPI": float(100.0 * get_percentiles(a, weights=w, percentiles=[0.5])[0])}
    lp = 100.0 * np.asarray(get_lorenz_shares(a, weights=w, percentiles=[0.2, 0.4, 0.6, 0.8]))
    for i, p in enumerate((20, 40, 60, 80)):
        out[f"lorenz_p{p}"] = float(lp[i])
    lt = 100.0 * np.asarray(get_lorenz_shares(a, weights=w, percentiles=[0.90, 0.99]))
    out["top10_share"] = float(100.0 - lt[0]); out["top1_share"] = float(100.0 - lt[1])
    return out


# ---- CLI (pooled prototype mode; heavy -- everything stays inside main) ----

def main():
    """CLI: pooled-distribution prototype run at one dist top.

    All env pins, sys.path edits, chdir, and the estim_phase2_tm_a import
    (which builds AND SOLVES the economy at import time) live HERE so that
    importing this module stays cheap and side-effect free.
    """
    import json

    TOP = sys.argv[1]
    OUTDIR = sys.argv[2] if len(sys.argv) > 2 else "/tmp/bucket"

    os.environ["HAFISCAL_EDTYPES"] = ""
    os.environ["HAFISCAL_INTERPRETATION"] = "ESC"
    os.environ["HAFISCAL_QUIET_BETADISTR"] = "1"
    os.environ.setdefault("HAFISCAL_GICX_MODE", "hardcoded")
    os.environ.setdefault("HAFISCAL_TM_ACOUNT", "200")
    os.environ["HAFISCAL_TM_AMAX"] = TOP

    REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
    HAM = os.path.join(REPO, "Code", "HA-Models")
    FPC = os.path.join(HAM, "FromPandemicCode")
    for p in (HAM, FPC):
        sys.path.insert(0, p)
    os.chdir(FPC)

    _saved = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        import estim_phase2_tm_a as est
    finally:
        sys.argv = _saved

    captured = {}
    _orig = est.get_percentiles

    def _spy(a_array, weights=None, percentiles=None):
        if "a" not in captured and weights is not None:
            captured["a"], captured["w"] = np.asarray(a_array), np.asarray(weights)
        return _orig(a_array, weights=weights, percentiles=percentiles)

    est.get_percentiles = _spy
    res = {"top": TOP, "groups": {}}
    for e, name in ((0, "dropout"), (1, "highschool"), (2, "college")):
        path = os.path.join(HAM, "Results",
                            f"DiscFacEstim_CRRA_2.0_R_1.01_edType{e}_TM_a_ESC.txt")
        with open(path) as fh:
            rec = None
            for line in fh:
                if line.strip().startswith("{"):
                    rec = eval(line, {"np": np, "__builtins__": {}})
        captured.clear()
        est.betas_obj_func_educ_tm_a(rec["beta"], rec["nabla"],
                                     rec.get("GICx", 7.60040233450051),
                                     educ_type=e, print_mode=False)
        a, w = captured["a"], captured["w"]
        x_top = float(a.max())
        g = {"raw": _moments(a, w)}
        aB, wB, diagB = apply_tail_bucket(a, w, ALPHA_CAP, x_top, variant='pile')
        g["bucket_pinned147"] = _moments(aB, wB); g["diagB"] = diagB
        aA, wA, diagA = apply_tail_bucket(a, w, diagB.get("alpha_fit", ALPHA_CAP),
                                          x_top, variant='pile')
        g["bucket_fitted"] = _moments(aA, wA); g["diagA"] = diagA
        aC, wC, diagC = apply_tail_bucket(a, w, ALPHA_CAP, x_top, variant='anchored')
        g["bucket_anchored"] = _moments(aC, wC); g["diagC"] = diagC
        res["groups"][name] = g
        print(f"  [{TOP}] {name}: raw top1={g['raw']['top1_share']:.3f} "
              f"pin147 top1={g['bucket_pinned147']['top1_share']:.3f} "
              f"fitted(a={diagB.get('alpha_fit', float('nan')):.2f}) "
              f"top1={g['bucket_fitted']['top1_share']:.3f} "
              f"excess={diagB.get('excess', 0):.2e}", flush=True)

    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, f"bucket_top{TOP}.json"), "w") as fh:
        json.dump(res, fh, indent=1)


if __name__ == "__main__":
    main()
