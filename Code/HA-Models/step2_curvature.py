"""step2_curvature.py — curvature / identification diagnostic for the Step-2 (β, ∇[, GICx]) estimates.

WHAT THIS IS.  An OPTION, never part of the pipeline (Econ-4; owner 2026-08-28: "make computing this an
option with code comments ... not worth the effort of reporting"; reshaped by the prior-art review of the
same day; re-worked after the first real run of 2026-08-28 13:09 on ccarroll-m5, see THE FIRST REAL RUN).
Around the INSTALLED optimum of each education group it evaluates the REAL Step-2 objective —
`betas_obj_func_educ_tm_a` in FromPandemicCode/estim_phase2_tm_a.py, reached read-only through
step2_attach_probe.exec_estimator_eval_mode (the estimator's HAFISCAL_STEP2_RUN_ESTIMATION=0 eval mode:
machinery built, estimation and every write skipped) — on a finite-difference stencil and reports

  * the RESIDUAL VECTOR r (model − data for the five targets, in percentage points) at every point — captured
    by wrapping the objective's own median and Lorenz calls, and checked against the returned distance
    (|r| must equal f to 1e-10 at every evaluation);
  * the Jacobian J = ∂r/∂x by central differences at a relative step h and at h/2 (Richardson combination;
    per-entry discrepancy = resolved-or-noise verdict; the step is halved up to --max-halvings times while
    the discrepancy exceeds --richardson-tol), and the Gauss-Newton curvature 2·JᵀJ of the SUM OF SQUARES
    S = f² — the smooth least-squares object (f itself is a root-sum-of-squares, V-shaped near a small
    residual, and its second differences are meaningless at any step that is not tiny);
  * the full finite-difference Hessian of S from the same stencil (corner points), whose difference from
    2·JᵀJ is the residual-curvature term 2·Σ r_i ∇²r_i — a second noise/quadratic-regime check;
  * in RELATIVE coordinates u_i = dx_i/x_i: the singular values and right singular vectors of J·diag(x) —
    the identification strengths (pp of residual per unit relative move) and the directions the wealth
    targets pin and do not pin — the condition number σ_max/σ_min, iso-objective half-widths (how far one
    can move along each direction, or one parameter alone, before the fit distance worsens by 1 % of f0),
    and the analytic "top-atom-fixed" direction (see THE MECHANISM) with its own strength;
  * a STATIONARITY check: the gradient of S and the Gauss-Newton step −(JᵀJ)⁻¹Jᵀr with the residual and
    distance it predicts — whether the installed point is the minimum of the objective AS EVALUATED HERE;
  * the objective's profile along ∇ (β fixed) and along the top-atom-fixed direction, with a quadratic fit
    of S — an independent, wide-step estimate of the same curvatures;
  * a path-independence tripwire (the centre re-evaluated after everything else) and an engine-parity
    warm-up (below).

WHAT THE NUMBERS ARE — AND ARE NOT.  The objective is a ROOT-SUM-OF-SQUARES DISTANCE between model and
data moments (the group's median liquid-wealth / permanent-income ratio and four Lorenz points, unweighted,
in percentage points).  No moment covariance Ω exists anywhere in this pipeline — no sampling variance of
the SCF targets, no simulation variance of the model moments — so (JᵀJ)⁻¹ is NOT a covariance matrix and
NOTHING here is a standard error.  The numbers are curvature UNDER THE OBJECTIVE'S OWN METRIC: "moving
1 % along v moves the target moments by σ pp", "the fit is indifferent to this combination".  Calling the
iso-objective half-widths "confidence intervals" would be wrong.  (Prior-art review:
conclusions_private/2026-08-28_prior-art-review_of_proposed_improvements.md, Econ-4 row.)

THE MECHANISM (what the first real run showed).  The group's most-patient atom sits a_hi = β + κ∇ (κ = 6/7
for seven equiprobable atoms) just below the GIC cap — 1.06e-2 for dropouts under the aggregate-cusp cap
of 2026-08-28 — where its ergodic wealth scales like 1/(1 − GPF): the wealth targets respond to a_hi with
|∂f/∂β| ≈ 600–1000 per unit β (f moves by O(1) for a 1e-3 relative move), while the combination that
holds a_hi fixed — ∇ up, β down, dβ = −κ d∇, i.e. relative direction ∝ (−κ∇/β, 1) — is flat to within
the objective's noise.  On ccarroll-m5 the Gauss-Newton curvature of S was rank-one to noise with weak
direction (−0.34, +0.94) in relative coordinates against the analytic (−0.32, +0.95).  So "∇ is weakly
identified" (the record) is, more precisely, "the wealth targets identify the top atom's patience and
little else": ∇ alone is steeply identified through a_hi; the top-atom-fixed combination is not.  The
record's flat ridge in ∇ at matched β (0.581–0.584 over ∇ ∈ [0.31, 0.47], 2026-07-23 §5) lies on the CLIP
SHELF — there the top atoms are pinned at the cap by the estimator's clip, so ∇ no longer moves a_hi (the
mechanism BUG-078 found in Step 1's arctan taper).  Inside the smooth region the objective is a steep V in
∇: on m5, f = 26–28 at ∇ −15 %/−30 % and 3.0–3.5 at +2 %/+4 %.

WHAT THE RECORD SUPPORTS ABOUT CONSEQUENCES.  Weak identification of ∇ is on record for the
WEALTH-DISTRIBUTION fit: the owner's 2026-08-13 ruling makes ∇ report-only in the re-estimation gates
because it "is poorly identified and can move a lot with little consequence for the wealth distribution"
(plans/20260813-1030h_cold-start-full-reestimation_plan.md, the ∇₁ gate, ~L268), and the 2026-07-23
count-convergence study found the dropout ridge above.  That does NOT license "of little consequence for
the paper's results": BUG-047's chain (BUGS_private/HAFiscal_BUG-047_permgrofac_marginal_value_factor.md)
moved the re-estimated atoms substantially (dropout β 0.719 → 0.685, ∇ 0.318 → 0.364; College ∇ +45 %)
while the fit distances barely changed, and its matched multipliers moved ≤ 0.01 only AFTER re-estimation
— the wealth fit does not by itself pin the multipliers across solver regimes.  Whether a move along the
flat direction changes the multipliers is an open question only the two ridge-end Step-5a runs (dropout
∇ ≈ 0.31 vs 0.47 at matched β, deterministic TM) can answer; this module does not run them and does not
claim their answer.

THE FIRST REAL RUN (2026-08-28 13:09, ccarroll-m5, tip a935e51c) and what it taught this tool:
  1. ENGINE PARITY.  The estimator's objective runs `os.environ.setdefault('HAFISCAL_STEP5_ATI','1')` AFTER
     its solve, so the FIRST evaluation in any process solves the near-cap atom by EGM and every later one
     by ATI (visible as the absence of `[step5-ati]` lines before eval 1, a re-keyed policy-store entry for
     the same atom, and a 1.43e-4 gap between the centre and its re-evaluation).  The estimator itself only
     ever uses its first evaluation as a start point; a stencil cannot afford one odd point.  This tool now
     runs one WARM-UP evaluation at the centre before measuring anything and reports the warm-up-to-centre
     gap (the engine-parity gap) separately.
  2. THE STEP.  A relative step of 1e-3 is NOT small for this objective (f moved 0.36 → 0.62 → 1.29 across
     β ∓ 1e-3; the second differences of f at h and h/2 disagreed by 150 %).  The smooth object is S = f²:
     its Gauss-Newton curvature needs only first differences of the residuals, whose h-vs-h/2 discrepancy
     on the same data was 2–20 %, and the step ladder halves h while it is not.
  3. THE MAPPING was right (every stencil point in the JSON is exactly β(1 ± h), ∇(1 ± h) with its label);
     the regression test in test_step2_curvature.py now drives run_group itself with a synthetic objective
     of known asymmetric sensitivities so a swapped argument order would be caught.
  4. STATIONARITY.  The installed point was NOT the minimum of the objective as evaluated on m5 (S fell
     from 0.385 to 0.012 at (β, ∇)·(1 − 5e-4)): a shift of ~5e-4 relative in the parameters — invisible in
     the parameters, an order of magnitude in f because of the steepness — which is what a numerics or
     platform vintage difference between the estimation and the evaluation does.  The tool reports the
     Gauss-Newton step and the distance it predicts, and does not guess the cause.

THE SECOND RUN (2026-08-28 13:38 ccarroll-m5 ecc2b4e8 and 17:27 jhu-dell 68ee1ddb — the same numbers to
1e-12 in f0 and to every printed digit in the Jacobian; dropout; 35 evaluations; every value reproduced
exactly in fresh processes with the policy store on and off).  The residual at the installed point is the
Lorenz-80 miss (−0.62 pp; median +0.017).  Relative Jacobian singular values 839 along (0.947, 0.321) and
11.2 along (−0.321, 0.947), condition 74.7; the weakest direction is the analytic top-atom-fixed direction
to 0.25°; Gauss-Newton and full-FD curvatures of S agree in shape (residual-curvature share 0.27) with
h-vs-h/2 discrepancies ≤ 2 % at relative steps 2.5e-4 / 1.25e-4.  STATIONARITY RESOLVED: the Gauss-Newton
step β −0.060 %, ∇ −0.049 % (predicted f 0.11 vs 0.62) is the BUG-095 vintage — the committed default-world
calibration (2026-08-20) is the perm-OFF point-mass-income estimate, the default objective has been
perm-ON since the 2026-08-26 fix, and BUG-095's own perm-ON re-estimate moved β by −0.066 % (Δa_hi −5.0e-4
vs the step's −5.7e-4; the ∇ difference lies along the unidentified direction).  Under the objective the
point was estimated on (HAFISCAL_STEP2_LEGACY_UNEMP_INCSHK=1) it is stationary: f0 0.1100, gradient norm
0.45, Gauss-Newton step 1.5e-6 / 4.0e-6, singular values 1127 / 11.3 (condition 99.6), same weak direction
(0.24°).  THE RECORD'S RIDGE: at the installed β the objective is FLAT on the clip shelf, f = 3.06–3.81
over ∇ ∈ [0.31, 0.47] (Lorenz-80 residual pinned at −2.8…−3.5 pp by the capped top atom) — the 2026-07-23
ridge reproduced qualitatively; its LEVEL (0.581–0.584 then) belongs to that objective's vintage (cap,
BUG-079 target, BUG-095 income) and is not comparable.  Inside the smooth region the ∇ profile is a steep
asymmetric V under both objectives (f 26–28.5 at −15 / −30 %, 2.9–3.5 at +2 / +4 %); along the
top-atom-fixed direction it is a shallow, near-symmetric bowl (f 2.1–2.2 at ±15 %, 4.0–4.9 at ±30 %).
Quotable from this: the identification structure (σ's, condition number, the weak direction = top atom
fixed), the shelf flatness, the cross-process determinism, and the vintage statement above.  NOT quotable:
any standard-error reading, the shelf's level against the record's, the ∇ component of the Gauss-Newton
step, and — still — "of little consequence for the paper's results".

REFUSALS (clear message, group status "refused", nothing evaluated for that group):
  * a central difference across the GIC cap — an atom sits at the cap or at the floor at the centre (the
    estimator's own clip diagnostic: atoms >= cap − 1e-12, as in its "[newly estimated] betaDistr" print),
    or the stencil's reach h·(β + κ∇) would carry the top atom across the cap (or the bottom atom below
    minBeta).  The College group's most-patient atom is placed at the GIC edge BY DESIGN (memory
    project_gic_cap_mortality_regime_reconfirmed; the BUG-078 taper arc), so a College refusal is the
    expected outcome whenever its top atom rides the cap; under the aggregate-cusp cap of 2026-08-28 it
    sits 5.9e-3 below (dropout 1.06e-2, high school 1.04e-2), so the default relative step 1e-3 passes and
    any step above 5.8e-3 refuses College (the message prints the admissible maximum).  Cap arithmetic is
    the COBYQA barrier's own (step1_param: cap_eff = cap − CAP_EPS is the ceiling the search can never
    cross; the objective's clip sits at cap itself).
  * the pre-BUG-079 gridded-median objective (HAFISCAL_STEP2_MEDIAN=node): the model median is then a step
    function of the parameters (BUGS_private/HAFiscal_BUG-079_step2-median-grid-quantization.md), and a
    step function has no curvature; refused before the economy is built (exit 5).

COST.  Each evaluation re-solves the group's seven types and their ergodic distributions (~8 s for dropout
on an idle m5, 12–20 s on a loaded dell) after the economy setup the eval-mode exec carries (~4 min cold,
~1 min with policy-store hits).  Per group: warm-up + centre + 6 stencil points at h + 6 at h/2 (2-D) +
4 + 4 profile points + the centre again = 22 evaluations (~3 min on m5); each extra halving adds 6.

USAGE (from Code/HA-Models):
    python step2_curvature.py --educ 0                       # dropout, defaults
    python step2_curvature.py --educ all --rel-step 2e-3 --max-halvings 3
    python step2_curvature.py --educ 2 --dry-run             # refusal check + plan, no economy build
    python step2_curvature.py --educ 0 --points 0.748103,0.297466 0.763065,0.291633   # evaluate points only
Outputs: Results/DiscFacEstim_<tag>[_edType<e>]_curvature.json and the one-screen summary (printed and
saved as ..._curvature_summary.txt); --out-dir or HAFISCAL_RESULTS_OUT_DIR redirect both.  No new
environment flag: the plan's proposed opt-in inside the estimator was replaced by this CLI in
Code/HA-Models (no new code in FromPandemicCode).  Exit codes: 0 done, 2 every requested group refused,
3 a Results/*.txt changed (the probe's read-only trap), 4 the estimator's eval mode did not reach the
objective, 5 refused under the node median, 6 --budget-min exceeded.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import socket
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import step1_param as _s1param                          # noqa: E402  cap_eff / CAP_EPS (the barrier's cap arithmetic)
from dist_quantile import median_mode as _median_mode   # noqa: E402  BUG-079 median-estimator selector
import step2_attach_probe as _probe                     # noqa: E402  read-only eval-mode exec + SoR loader

PARAM_NAMES = ("beta", "nabla", "GICx")
MOMENT_NAMES = ("medianLWPI", "Lorenz20", "Lorenz40", "Lorenz60", "Lorenz80")
EDUC_NAMES = ("Dropout", "Highschool", "College")
GICX_MODES = ("legacy", "hardcoded", "twophase")
SCHEMA = "step2_curvature/v2"
EXIT_ALL_REFUSED, EXIT_WRITE_TRAP, EXIT_EXEC_FAIL, EXIT_NODE_MEDIAN, EXIT_BUDGET = 2, 3, 4, 5, 6
OBJECTIVE_DEF = ("f = sqrt(sum of squared misses) over [median LW/PI, Lorenz 20/40/60/80] in percentage "
                 "points (root-sum-of-squares distance, unweighted; estim_phase2_tm_a.betas_obj_func_educ_tm_a); "
                 "curvature is analysed on S = f^2 (the least-squares object)")
RESIDUAL_TOL = 1e-10       # |r| must reproduce the returned distance to this (relative)
PATH_TOL = 1e-12           # centre re-evaluation must match the centre to this (relative)


# ───────────────────────────── finite-difference stencil (pure numpy; unit-tested) ─────────────────────────────

def stencil_offsets(n):
    """The O(h²) stencil in step units: centre, ±e_i, and (+e_i+e_j) / (−e_i−e_j) per pair — 7 points in
    2-D, 13 in 3-D."""
    offs = [tuple([0] * n)]
    for i in range(n):
        for s in (1, -1):
            o = [0] * n
            o[i] = s
            offs.append(tuple(o))
    for i in range(n):
        for j in range(i + 1, n):
            for s in (1, -1):
                o = [0] * n
                o[i] = s
                o[j] = s
                offs.append(tuple(o))
    return offs


def stencil_point(x0, h, offset):
    return np.asarray(x0, dtype=float) + np.asarray(offset, dtype=float) * np.asarray(h, dtype=float)


def _axis(n, i, s):
    o = [0] * n
    o[i] = s
    return tuple(o)


def _corner(n, i, j, s):
    o = [0] * n
    o[i] = s
    o[j] = s
    return tuple(o)


def jacobian_from_stencil(vecs, h):
    """Central-difference Jacobian (m × n) of a vector function from {offset: r} on the ±e_i points."""
    h = np.asarray(h, dtype=float)
    n = h.size
    cols = []
    for i in range(n):
        rp = np.asarray(vecs[_axis(n, i, 1)], dtype=float)
        rm = np.asarray(vecs[_axis(n, i, -1)], dtype=float)
        cols.append((rp - rm) / (2.0 * h[i]))
    return np.column_stack(cols)


def derivatives_from_stencil(vals, h):
    """(gradient, Hessian) of a SCALAR function from {offset: value} on stencil_offsets(n) with steps h.

    Diagonal: (f₊ − 2f₀ + f₋)/h_i².  Mixed: the seven-point formula
        f_ij = [f(+i+j) + f(−i−j) − f(+i) − f(−i) − f(+j) − f(−j) + 2 f₀] / (2 h_i h_j),
    exact for quadratics; its error expansion has even powers only, so the Richardson combination
    (4·H(h/2) − H(h))/3 is valid entry by entry."""
    h = np.asarray(h, dtype=float)
    n = h.size
    f0 = float(vals[tuple([0] * n)])
    g = np.zeros(n)
    H = np.zeros((n, n))
    for i in range(n):
        fp, fm = float(vals[_axis(n, i, 1)]), float(vals[_axis(n, i, -1)])
        g[i] = (fp - fm) / (2.0 * h[i])
        H[i, i] = (fp - 2.0 * f0 + fm) / h[i] ** 2
    for i in range(n):
        for j in range(i + 1, n):
            num = (float(vals[_corner(n, i, j, 1)]) + float(vals[_corner(n, i, j, -1)])
                   - float(vals[_axis(n, i, 1)]) - float(vals[_axis(n, i, -1)])
                   - float(vals[_axis(n, j, 1)]) - float(vals[_axis(n, j, -1)]) + 2.0 * f0)
            H[i, j] = H[j, i] = num / (2.0 * h[i] * h[j])
    return g, H


def richardson(a_h, a_h2):
    """Richardson combination of an O(h²)-accurate estimate at h and at h/2, and the relative
    discrepancy |a(h) − a(h/2)| / max(|a(h)|, |a(h/2)|) (0 where both vanish)."""
    a_h = np.asarray(a_h, dtype=float)
    a_h2 = np.asarray(a_h2, dtype=float)
    r = (4.0 * a_h2 - a_h) / 3.0
    scale = np.maximum(np.maximum(np.abs(a_h), np.abs(a_h2)), 1e-300)
    return r, np.abs(a_h - a_h2) / scale


def jacobian_discrepancy(J_c, J_f, floor=1e-300):
    """|J(h) − J(h/2)| scaled by each COLUMN's largest magnitude over the two estimates — the
    resolved-or-noise measure for the Jacobian.  Per-entry scaling (richardson's) lets a negligible
    entry (a moment that barely responds to a parameter) report an O(1) discrepancy that says nothing
    about the parameter's identification; on the m5 run of 2026-08-28 the Lorenz-40/β entry (2e-3 pp,
    vs 1e3 for Lorenz-80/β) drove two step halvings that way.  Column scaling asks the question that
    matters: is the parameter's column resolved relative to its own largest response."""
    J_c = np.asarray(J_c, dtype=float)
    J_f = np.asarray(J_f, dtype=float)
    scale = np.maximum(np.max(np.abs(np.stack([J_c, J_f])), axis=(0, 1)), floor)
    return np.abs(J_c - J_f) / scale[None, :]


def relative_jacobian(J, x0):
    """J·diag(|x0|): residual change per unit RELATIVE move u_i = dx_i/|x_i|."""
    return np.asarray(J, dtype=float) @ np.diag(np.abs(np.asarray(x0, dtype=float)))


def relative_coords(x0, g=None, H=None):
    """Gradient/Hessian with respect to u_i = dx_i / |x0_i|: D g and D H D, D = diag(|x0|)."""
    D = np.diag(np.abs(np.asarray(x0, dtype=float)))
    return (None if g is None else D @ np.asarray(g, dtype=float),
            None if H is None else D @ np.asarray(H, dtype=float) @ D)


def identification_svd(J_rel):
    """Singular values (descending) and right singular vectors (columns) of the relative Jacobian —
    the identification strengths and directions — plus the condition number σ_max/σ_min (inf if 0)."""
    U, s, Vt = np.linalg.svd(np.asarray(J_rel, dtype=float), full_matrices=False)
    V = Vt.T
    for k in range(V.shape[1]):                     # orient: largest-|component| positive
        j = int(np.argmax(np.abs(V[:, k])))
        if V[j, k] < 0:
            V[:, k] *= -1.0
    smin = float(np.min(s)) if s.size else 0.0
    cond = math.inf if smin == 0.0 else float(np.max(s)) / smin
    return s, V, cond


def eigen_report(H):
    """Ascending eigenvalues, unit eigenvectors (columns), condition number |λ|max/|λ|min (inf if singular)."""
    w, V = np.linalg.eigh(np.asarray(H, dtype=float))
    amin, amax = float(np.min(np.abs(w))), float(np.max(np.abs(w)))
    return w, V, (math.inf if amin == 0.0 else amax / amin)


def iso_halfwidths_ls(r0, J_rel, directions, delta_f):
    """Two-sided half-widths along unit directions v (relative coordinates) at which the distance
    |r0 + t·J_rel·v| first reaches f0 + delta_f, from the exact quadratic
        t²·|Jv|² + 2t·(r0·Jv) + f0² − (f0 + delta_f)² = 0.
    Returns an array (n_dir, 2) of (t_minus <= 0, t_plus >= 0); ±inf where |Jv| = 0."""
    r0 = np.asarray(r0, dtype=float)
    f0 = float(np.linalg.norm(r0))
    out = []
    for v in np.atleast_2d(np.asarray(directions, dtype=float)):
        Jv = np.asarray(J_rel, dtype=float) @ v
        a = float(Jv @ Jv)
        b = 2.0 * float(r0 @ Jv)
        c = f0 ** 2 - (f0 + delta_f) ** 2
        if a <= 0.0:
            out.append((-math.inf, math.inf))
            continue
        disc = b * b - 4.0 * a * c
        s = math.sqrt(max(disc, 0.0))
        out.append(((-b - s) / (2.0 * a), (-b + s) / (2.0 * a)))
    return np.asarray(out)


def gauss_newton(r0, J_rel):
    """(gradient of S in relative coords, GN step Δu, predicted residual, predicted distance);
    step None if JᵀJ is singular."""
    r0 = np.asarray(r0, dtype=float)
    J = np.asarray(J_rel, dtype=float)
    grad = 2.0 * J.T @ r0
    try:
        step = -np.linalg.solve(J.T @ J, J.T @ r0)
    except np.linalg.LinAlgError:
        return grad, None, None, None
    if not np.all(np.isfinite(step)):
        return grad, None, None, None
    r_pred = r0 + J @ step
    return grad, step, r_pred, float(np.linalg.norm(r_pred))


def top_atom_fixed_direction(beta, nabla, kappa):
    """Unit relative direction along which the top atom a_hi = β + κ∇ does not move: dβ = −κ d∇ ⇒
    (u_β, u_∇) ∝ (−κ∇/β, 1) (GICx component 0 when present)."""
    v = np.array([-kappa * nabla / beta, 1.0])
    return v / np.linalg.norm(v)


def quadratic_fit(t, f):
    """Least-squares f ≈ a + b·t + ½·c·t² over profile points; (a, b, c, rms residual) or None if < 3 pts."""
    t = np.asarray(t, dtype=float)
    f = np.asarray(f, dtype=float)
    if t.size < 3:
        return None
    p = np.polyfit(t, f, 2)  # f ≈ p0 t² + p1 t + p2
    resid = f - np.polyval(p, t)
    return float(p[2]), float(p[1]), float(2.0 * p[0]), float(np.sqrt(np.mean(resid ** 2)))


# ───────────────────────────────── cap arithmetic (pure; mirrors the estimator) ─────────────────────────────────

def kappa_of(n_atoms):
    """Top atom = β + κ∇ with κ = (n−1)/n (the estimator's _kappa_e)."""
    return (n_atoms - 1) / n_atoms


def uniform_atoms(beta, nabla, n_atoms):
    """The estimator's discretisation Uniform(β−∇, β+∇) on n equiprobable atoms: β − ∇ + ∇(2k+1)/n."""
    k = np.arange(n_atoms)
    return beta - nabla + nabla * (2 * k + 1) / n_atoms


def gic_factor(gicx):
    """GPF shave from its logit coordinate: σ(GICx)."""
    return float(np.exp(gicx) / (1.0 + np.exp(gicx)))


def cap_status(beta, nabla, cap, floor, n_atoms, tol=1e-12):
    """Where the atoms sit relative to the clip: the estimator's own rule (atoms >= cap − 1e-12 count as
    at the cap) plus the margins the stencil must respect."""
    atoms = uniform_atoms(beta, nabla, n_atoms)
    return {"a_hi": float(atoms[-1]), "a_lo": float(atoms[0]),
            "n_at_cap": int(np.sum(atoms >= cap - tol)),
            "n_at_floor": int(np.sum(atoms <= floor + tol)),
            "margin_top": float(cap - atoms[-1]), "margin_floor": float(atoms[0] - floor),
            "cap": float(cap), "cap_eff": float(_s1param.cap_eff(cap)), "cap_eps": float(_s1param.CAP_EPS),
            "floor": float(floor), "kappa": float(kappa_of(n_atoms)), "n_atoms": int(n_atoms)}


def refusal_reason(beta, nabla, cap_center, cap_min, floor, n_atoms, h_beta, h_nabla):
    """None if every stencil point stays strictly inside the smooth (unclipped) region, else the reason.

    cap_min is the smallest cap over the stencil — equal to cap_center unless GICx is a free coordinate
    (legacy mode), in which case the cap itself moves with the GICx steps."""
    st = cap_status(beta, nabla, cap_center, floor, n_atoms)
    kappa = kappa_of(n_atoms)
    reach = abs(h_beta) + kappa * abs(h_nabla)
    if st["n_at_cap"] > 0:
        return (f"atom_at_cap: {st['n_at_cap']} atom(s) sit at the GIC cap {cap_center:.6f} at the centre "
                f"(top atom {st['a_hi']:.6f}); a central difference would straddle the clip kink")
    if st["n_at_floor"] > 0:
        return (f"atom_at_floor: {st['n_at_floor']} atom(s) sit at minBeta {floor:g} at the centre "
                f"(bottom atom {st['a_lo']:.6f}); a central difference would straddle the clip kink")
    if st["a_hi"] + reach >= cap_min:
        max_rel = (cap_min - st["a_hi"]) / (abs(beta) + kappa * abs(nabla))
        return (f"stencil_crosses_cap: top atom {st['a_hi']:.6f} + stencil reach {reach:.2e} >= cap "
                f"{cap_min:.6f} (margin {cap_min - st['a_hi']:.2e}); the largest admissible --rel-step is "
                f"{max_rel:.2e}")
    if st["a_lo"] - reach <= floor:
        return (f"stencil_crosses_floor: bottom atom {st['a_lo']:.6f} − stencil reach {reach:.2e} <= minBeta "
                f"{floor:g} (margin {st['a_lo'] - floor:.2e}); shrink --rel-step")
    return None


def median_refusal():
    """The reason string if the Step-2 median estimator is the pre-BUG-079 node snap, else None."""
    if _median_mode() == "node":
        return ("HAFISCAL_STEP2_MEDIAN=node selects the pre-BUG-079 gridded-median objective: the model median "
                "is then a step function of (beta, nabla) — snapped to grid levels (BUGS_private/"
                "HAFiscal_BUG-079_step2-median-grid-quantization.md) — and a step function has no curvature. "
                "Unset it (interp, the default) to run this diagnostic.")
    return None


def max_feasible_t(x0, direction, cap_fn, floor, n_atoms, t_max=1.0, safety=0.95):
    """Largest t in [0, t_max] (times `safety`) such that x0·(1 + t·direction) keeps every atom strictly
    inside (minBeta, cap(GICx)); 0 if the centre itself is not inside.  Bisection on the exact predicate
    (the cap depends on GICx when that coordinate moves)."""
    x0 = np.asarray(x0, dtype=float)
    direction = np.asarray(direction, dtype=float)

    def feasible(t):
        x = x0 * (1.0 + t * direction)
        if x[1] <= 0.0:
            return False
        cap = cap_fn(x[2] if x.size > 2 else None)
        st = cap_status(x[0], x[1], cap, floor, n_atoms)
        return st["margin_top"] > 0.0 and st["margin_floor"] > 0.0

    if not feasible(0.0):
        return 0.0
    if feasible(t_max):
        return safety * t_max
    lo, hi = 0.0, t_max
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if feasible(mid):
            lo = mid
        else:
            hi = mid
    return safety * lo


def default_profile_offsets(up_max, down_max, span=0.30):
    """Two points each side: ±span/2, ±span, shrunk to the feasible range on either side."""
    u = min(span, up_max)
    d = min(span, down_max)
    offs = []
    if d > 0:
        offs += [-d, -d / 2.0]
    if u > 0:
        offs += [u / 2.0, u]
    return offs


# ───────────────────────────────────────── estimator context ─────────────────────────────────────────

def _gicx_mode():
    m = os.environ.get("HAFISCAL_GICX_MODE", "hardcoded").strip()
    if m not in GICX_MODES:
        raise ValueError(f"HAFISCAL_GICX_MODE must be one of {GICX_MODES}; got {m!r}")
    return m


def _calib_tag_from_ep(ep):
    """The estimator's df_base + calibration suffix (lines ~423–446 of estim_phase2_tm_a.py), for --dry-run."""
    from _interpretation import calib_suffix
    base = f"DiscFacEstim_CRRA_{ep.CRRA}_R_{ep.Rfree_base[0]}"
    if ep.IncUnemp != 0.7 or ep.IncUnempNoBenefits != 0.5:
        base += "_altBenefits"
    if ep.Splurge == 0:
        base += "_Splurge0"
    return base, calib_suffix()


def build_context(argv_tail, dry_run):
    """The objective, its namespace and the estimator's cap machinery.  Full mode execs the real estimator
    in eval mode (economy built and solved at the installed calibration); --dry-run imports
    EstimParameters only."""
    here, fpc, script, res_dir = _probe.estimator_paths()
    if dry_run:
        if fpc not in sys.path:
            sys.path.insert(0, fpc)
        os.chdir(fpc)
        sys.argv = [script] + argv_tail.split()
        os.environ.setdefault("HAFISCAL_CALIB_BOOTSTRAP", "1")   # as the estimator does before its import
        import EstimParameters as ep
        df_base, suffix = _calib_tag_from_ep(ep)
        ns, objective = None, None
    else:
        ns = _probe.exec_estimator_eval_mode(argv_tail)
        ep = ns["ep"]
        df_base, suffix = ns["df_base"], ns["_INTERP_SUFFIX"]
        objective = ns["betas_obj_func_educ_tm_a"]
    return {"ep": ep, "ns": ns, "objective": objective, "df_base": df_base, "suffix": suffix,
            "tag": df_base + suffix, "res_dir": os.path.abspath(res_dir), "argv_tail": argv_tail,
            "gicx_mode": _gicx_mode()}


def resolve_sor_file(ctx, override=None):
    """The installed estimates: the estimator's own suffix-named warm-start file
    (Results/<df_base><calib suffix>.txt — the plan's anchor definition), unless --sor-file says otherwise.
    The estimator's registry lookup (its first warm-start choice) is reported when it points elsewhere."""
    if override:
        return os.path.abspath(os.path.expanduser(override)), None
    path = os.path.join(ctx["res_dir"], ctx["tag"] + ".txt")
    note = None
    try:
        import _registry
        reg = _registry.find_warm_start_cal()
        if reg is not None and os.path.exists(str(reg)) and os.path.abspath(str(reg)) != path:
            note = f"registry warm-start candidate differs: {reg} (ignored; pass --sor-file to use it)"
    except Exception:
        pass
    return path, note


def make_evaluator(ctx, e, gicx_fixed, n, evals, log=print):
    """F(x, label) -> (f, r): the objective at the point x = (β, ∇[, GICx]) — argument order is the
    objective's own (beta, spread, GICx, educ_type=, print_mode=) — with the residual vector r = model −
    data (pp) captured by wrapping the median and Lorenz calls the objective makes in its own namespace.
    Every evaluation is checked: |r| must reproduce the returned distance to RESIDUAL_TOL."""
    ns, obj = ctx["ns"], ctx["objective"]
    targets = np.concatenate([[float(np.asarray(ns["data_medianLWPI"][e]).reshape(-1)[0])],
                              np.asarray(ns["data_LorenzPts"][e], dtype=float).reshape(-1)])
    rec = {}
    orig_median, orig_lorenz = ns["_step2_median"], ns["get_lorenz_shares"]

    def median_wrapped(a, w, *args, **kw):
        out = orig_median(a, w, *args, **kw)
        rec["median"] = 100.0 * float(np.asarray(out, dtype=float).reshape(-1)[0])
        return out

    def lorenz_wrapped(*args, **kw):
        out = orig_lorenz(*args, **kw)
        rec["lorenz"] = 100.0 * np.asarray(out, dtype=float).reshape(-1)
        return out

    ns["_step2_median"], ns["get_lorenz_shares"] = median_wrapped, lorenz_wrapped

    def F(x, label):
        x = np.asarray(x, dtype=float)
        rec.clear()
        t0 = time.time()
        v = obj(float(x[0]), float(x[1]), float(x[2]) if n == 3 else float(gicx_fixed), educ_type=e,
                print_mode=False)
        f = float(np.asarray(v, dtype=float).reshape(-1)[0])
        dt = time.time() - t0
        if "median" not in rec or "lorenz" not in rec:
            raise RuntimeError("residual capture failed: the objective did not call the wrapped median/Lorenz "
                               "functions (estimator changed?)")
        moments = np.concatenate([[rec["median"]], rec["lorenz"]])
        r = moments - targets
        f_check = float(np.linalg.norm(r))
        if abs(f_check - f) > RESIDUAL_TOL * max(1.0, abs(f)):
            raise RuntimeError(f"residual reconstruction mismatch at {label}: |r|={f_check!r} vs f={f!r}")
        evals.append({"label": label, "x": x.tolist(), "f": f, "S": f * f, "residuals": r.tolist(),
                      "moments": moments.tolist(), "wall_s": dt})
        log(f"    eval {len(evals):2d} {label:<16s} x={['%.7f' % t for t in x]} f={f:.8f} "
            f"r={['%+.3f' % t for t in r]} ({dt:.1f}s)")
        return f, r

    F.targets = targets
    return F


# ───────────────────────────────────────────── per-group run ─────────────────────────────────────────────

def _py(o):
    """JSON-safe copy (numpy → python; inf/nan → strings)."""
    if isinstance(o, dict):
        return {str(k): _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(v) for v in o]
    if isinstance(o, np.ndarray):
        return _py(o.tolist())
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else ("inf" if f > 0 else "-inf" if f < 0 else "nan")
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def _fmt_mat(M, fmt="{:+.4e}"):
    M = np.atleast_2d(np.asarray(M, dtype=float))
    return "[" + "; ".join(" ".join(fmt.format(v) for v in row) for row in M) + "]"


def _fmt_vec(v, fmt="{:+.3e}"):
    return "[" + ", ".join(fmt.format(t) for t in np.asarray(v, dtype=float).ravel()) + "]"


def _pct(t):
    return f"{t * 100:+.3g} %" if math.isfinite(t) else ("+inf" if t > 0 else "-inf")


def measure_stencil(F, x0, h, label):
    """Evaluate the ±e_i and corner points at step h (the centre is supplied); returns
    (values {offset: f}, residuals {offset: r})."""
    n = len(x0)
    vals, vecs = {}, {}
    for o in stencil_offsets(n)[1:]:
        f, r = F(stencil_point(x0, h, o), f"{label} {o}")
        vals[o], vecs[o] = f, r
    return vals, vecs


def analyse(x0, r0, levels, opt):
    """The derivative analysis from stencil levels [(h, vals, vecs), ...] (finest last).  Uses the two
    finest levels for the Richardson pair."""
    n = len(x0)
    f0 = float(np.linalg.norm(r0))
    zero = tuple([0] * n)
    (h_c, vals_c, vecs_c), (h_f, vals_f, vecs_f) = levels[-2], levels[-1]
    J_c, J_f = jacobian_from_stencil(vecs_c, h_c), jacobian_from_stencil(vecs_f, h_f)
    J_r, J_disc_entry = richardson(J_c, J_f)
    J_disc = jacobian_discrepancy(J_c, J_f)              # column-scaled: the verdict that matters
    S_c = {o: v * v for o, v in vals_c.items()}          # S = f^2 on the stencil, centre added
    S_c[zero] = f0 * f0
    S_f = {o: v * v for o, v in vals_f.items()}
    S_f[zero] = f0 * f0
    _, HS_c = derivatives_from_stencil(S_c, h_c)
    _, HS_f = derivatives_from_stencil(S_f, h_f)
    HS_r, HS_disc = richardson(HS_c, HS_f)
    J_rel = relative_jacobian(J_r, x0)
    H_gn_rel = 2.0 * J_rel.T @ J_rel                      # Gauss-Newton curvature of S, relative coords
    _, HS_rel = relative_coords(x0, None, HS_r)           # full FD curvature of S, relative coords
    resid_curv = HS_rel - H_gn_rel                         # 2 Σ r_i ∇²r_i (+ noise)
    s, V, cond = identification_svd(J_rel)
    grad_S, step, r_pred, f_pred = gauss_newton(r0, J_rel)
    kappa = kappa_of(int(opt.n_atoms))
    v_fix = top_atom_fixed_direction(x0[0], x0[1], kappa)
    if n == 3:
        v_fix = np.concatenate([v_fix, [0.0]])
    sigma_fix = float(np.linalg.norm(J_rel @ v_fix))
    v_weak = V[:, -1]
    angle = math.degrees(math.acos(min(1.0, abs(float(v_fix @ v_weak)))))
    delta_f = float(opt.delta_f_frac) * f0
    hw_svd = iso_halfwidths_ls(r0, J_rel, V.T, delta_f)
    hw_axis = iso_halfwidths_ls(r0, J_rel, np.eye(n), delta_f)
    hw_fix = iso_halfwidths_ls(r0, J_rel, v_fix[None, :], delta_f)[0]
    noise_J = J_disc > float(opt.richardson_tol)
    improvement = None if f_pred is None else (1.0 - f_pred / f0 if f0 > 0 else 0.0)
    stationary = None if improvement is None else bool(improvement <= float(opt.stationarity_tol))
    return {
        "steps_used": {"coarse_abs": np.asarray(h_c).tolist(), "fine_abs": np.asarray(h_f).tolist(),
                       "coarse_rel": float(h_c[0] / abs(x0[0])), "fine_rel": float(h_f[0] / abs(x0[0])),
                       "levels_evaluated": len(levels)},
        "jacobian": {"coarse": J_c, "fine": J_f, "richardson": J_r, "rel_discrepancy": J_disc,
                     "rel_discrepancy_per_entry": J_disc_entry,
                     "noise_dominated": noise_J, "richardson_tol": float(opt.richardson_tol),
                     "rows": list(MOMENT_NAMES), "units": "pp per unit parameter",
                     "note": "rel_discrepancy is |J(h)-J(h/2)| scaled by each column's largest entry "
                             "(jacobian_discrepancy); per_entry is the entrywise relative version"},
        "jacobian_relative": {"richardson": J_rel, "units": "pp per unit RELATIVE move (u_i = dx_i/|x_i|)"},
        "hessian_S": {"coarse": HS_c, "fine": HS_f, "richardson": HS_r, "rel_discrepancy": HS_disc,
                      "relative_coords": HS_rel, "gauss_newton_relative": H_gn_rel,
                      "residual_curvature_term_relative": resid_curv,
                      "residual_curvature_share": float(np.linalg.norm(resid_curv) /
                                                        max(np.linalg.norm(H_gn_rel), 1e-300)),
                      "note": "S = f^2; full FD Hessian vs 2 J^T J; their difference is 2 sum r_i d2 r_i (+ noise)"},
        "identification": {"singular_values": s, "directions_columns": V, "condition_number": cond,
                           "weak_direction": v_weak, "strong_direction": V[:, 0],
                           "top_atom_fixed_direction": v_fix, "sigma_along_top_atom_fixed": sigma_fix,
                           "angle_deg_weak_vs_top_atom_fixed": angle,
                           "note": "sigma_k = pp of residual per unit relative move along v_k; "
                                   "condition = sigma_max/sigma_min"},
        "iso_objective": {"delta_f_frac": float(opt.delta_f_frac), "delta_f": delta_f,
                          "halfwidths_relative_along_svd_directions": hw_svd,
                          "halfwidths_relative_axis_aligned": hw_axis,
                          "halfwidths_relative_top_atom_fixed": hw_fix,
                          "note": ("(t_minus, t_plus): relative moves at which f first reaches f0 + delta_f; "
                                   "NOT a confidence interval (no moment covariance)")},
        "stationarity": {"gradient_S_relative": grad_S, "gauss_newton_step_relative": step,
                         "predicted_residuals": r_pred, "predicted_f": f_pred,
                         "predicted_improvement_frac": improvement, "tolerance_improvement_frac": float(opt.stationarity_tol),
                         "installed_point_is_minimum_to_tol": stationary,
                         "note": "GN step = -(J^T J)^-1 J^T r in relative coords; None if singular"},
    }


def run_group(ctx, e, sor_row, opt, log=print):
    """Evaluate the stencil (or --points) for one education group; returns the group's result dict
    (status ok / refused / planned / points / budget).  `opt` is the parsed CLI namespace."""
    ep = ctx["ep"]
    n_atoms = int(ep.DiscFacCount)
    floor = float(ep.minBeta)
    mode = ctx["gicx_mode"]
    gicx_pin = float(np.log(ep.theGICfactor / (1.0 - ep.theGICfactor)))
    beta0, nabla0, gicx_file = float(sor_row["beta"]), float(sor_row["nabla"]), float(sor_row["GICx"])
    free = ["beta", "nabla"] + (["GICx"] if mode == "legacy" else [])
    if mode == "legacy":
        x0 = np.array([beta0, nabla0, gicx_file])
        gicx_fixed = None
    else:
        x0 = np.array([beta0, nabla0])
        gicx_fixed = gicx_pin
    n = x0.size
    opt.n_atoms = n_atoms
    cap_fn = (lambda gx: float(ep.gic_capped_beta(e, gic_factor(gicx_fixed if gx is None else gx))))
    h = float(opt.rel_step) * np.abs(x0)
    cap_center = cap_fn(x0[2] if n == 3 else None)
    cap_min = min(cap_fn(x0[2] - h[2]), cap_fn(x0[2] + h[2]), cap_center) if n == 3 else cap_center
    st = cap_status(beta0, nabla0, cap_center, floor, n_atoms)
    res = {"group": e, "name": EDUC_NAMES[e], "free_params": free, "gicx_mode": mode,
           "point": {"beta": beta0, "nabla": nabla0, "GICx": (x0[2] if n == 3 else gicx_fixed),
                     "GICx_in_file": gicx_file, "GICx_pinned": gicx_pin},
           "cap": st, "cap_min_over_stencil": cap_min,
           "steps": {"rel": float(opt.rel_step), "abs": h.tolist(), "max_halvings": int(opt.max_halvings)}}
    if mode != "legacy" and abs(gicx_file - gicx_pin) > 1e-9:
        res["note_gicx"] = (f"file GICx {gicx_file:.6f} != pinned logit(theGICfactor) {gicx_pin:.6f}; "
                            f"the {mode} mode pins it, as the estimator does")
    evals = []

    # ---- --points: evaluate explicit points only (warm-up, centre, points, centre again) ----
    if opt.points:
        pts = [np.array([float(t) for t in p.split(",")]) for p in opt.points]
        if opt.dry_run:
            res["status"], res["plan"] = "planned", {"n_evals": len(pts) + 3, "points": [p.tolist() for p in pts]}
            return res
        F = make_evaluator(ctx, e, gicx_fixed, n, evals, log)
        t_start = time.time()
        F(x0, "warm-up")
        f0, r0 = F(x0, "centre")
        for k, p in enumerate(pts):
            xp = np.concatenate([p, x0[len(p):]]) if p.size < n else p[:n]
            F(xp, f"point {k + 1}")
        f_again, _ = F(x0, "centre-again")
        res.update({"status": "points", "objective": OBJECTIVE_DEF, "objective_at_center": f0,
                    "residuals_at_center": r0.tolist(), "targets": F.targets.tolist(),
                    "engine_parity_gap": abs(evals[0]["f"] - f0),
                    "path_independence": {"value_again": f_again, "abs_diff": abs(f_again - f0),
                                          "ok": abs(f_again - f0) <= PATH_TOL * max(1.0, abs(f0))},
                    "evaluations": evals,
                    "timing": {"n_evals": len(evals), "total_s": time.time() - t_start,
                               "per_eval_s": (time.time() - t_start) / max(len(evals), 1)}})
        return res

    reason = refusal_reason(beta0, nabla0, cap_center, cap_min, floor, n_atoms, h[0], h[1])
    if reason is not None:
        res["status"], res["reason"] = "refused", reason
        log(f"[curvature] {EDUC_NAMES[e]} (e={e}): REFUSED — {reason}")
        return res

    # profile directions and feasible ranges (pure arithmetic; needed for the plan too)
    kappa = kappa_of(n_atoms)
    v_fix = top_atom_fixed_direction(beta0, nabla0, kappa)
    if n == 3:
        v_fix = np.concatenate([v_fix, [0.0]])
    e_nabla = np.eye(n)[1]
    ranges = {}
    for name, d in (("nabla", e_nabla), ("top_atom_fixed", v_fix)):
        ranges[name] = {"up": max_feasible_t(x0, d, cap_fn, floor, n_atoms),
                        "down": max_feasible_t(x0, -d, cap_fn, floor, n_atoms)}
    prof_offs = {name: (list(opt.profile_offsets) if opt.profile_offsets
                        else default_profile_offsets(rg["up"], rg["down"], span=float(opt.profile_span)))
                 for name, rg in ranges.items()}
    axes = ("nabla", "top_atom_fixed") if opt.profile_axis == "both" else (opt.profile_axis,)
    n_stencil = len(stencil_offsets(n)) - 1
    n_evals = 3 + 2 * n_stencil + sum(len(prof_offs[a]) for a in axes)
    res["profile_feasible_t"] = ranges
    res["plan"] = {"n_evals_base": n_evals, "n_evals_per_extra_halving": n_stencil,
                   "profile_axes": list(axes), "profile_offsets": {a: prof_offs[a] for a in axes}}
    log(f"[curvature] {EDUC_NAMES[e]} (e={e}): centre beta={beta0:.6f} nabla={nabla0:.6f} "
        f"GICx={'free ' + format(x0[2], '.4f') if n == 3 else 'pinned ' + format(gicx_fixed, '.4f')}; "
        f"cap {cap_center:.6f} (top atom {st['a_hi']:.6f}, margin {st['margin_top']:.2e}); "
        f"h={h.tolist()}; {n_evals} evaluations planned (+{n_stencil} per extra halving); profiles along "
        f"{axes} at t={ {a: ['%+.3f' % t for t in prof_offs[a]] for a in axes} }; top-atom-fixed direction "
        f"{_fmt_vec(v_fix, '{:+.3f}')}")
    if opt.dry_run:
        res["status"] = "planned"
        return res

    F = make_evaluator(ctx, e, gicx_fixed, n, evals, log)
    t_start = time.time()
    # engine parity: the estimator's first evaluation in a process solves under different defaults
    # (its HAFISCAL_STEP5_ATI setdefault runs after the solve) — burn it, then measure
    f_warm, _ = F(x0, "warm-up")
    f0, r0 = F(x0, "centre")
    if opt.budget_min is not None:
        proj = evals[-1]["wall_s"] * n_evals / 60.0
        if proj > float(opt.budget_min):
            log(f"[curvature] projected {proj:.1f} min for {n_evals} evaluations exceeds --budget-min "
                f"{opt.budget_min}; aborting before the stencil")
            res["status"], res["reason"] = "budget", f"projected {proj:.1f} min > budget {opt.budget_min}"
            return res

    # stencil ladder: h, h/2, and further halvings while the Jacobian is not resolved
    levels = []
    h_cur = h.copy()
    for lvl in range(2 + int(opt.max_halvings)):
        vals, vecs = measure_stencil(F, x0, h_cur, f"h/{2 ** lvl}" if lvl else "h")
        levels.append((h_cur.copy(), vals, vecs))
        if len(levels) >= 2:
            disc = jacobian_discrepancy(jacobian_from_stencil(levels[-2][2], levels[-2][0]),
                                        jacobian_from_stencil(levels[-1][2], levels[-1][0]))
            if float(np.max(disc)) <= float(opt.richardson_tol) or lvl == 1 + int(opt.max_halvings):
                break
            log(f"    [ladder] Jacobian h-vs-h/2 column-scaled discrepancy {float(np.max(disc)):.0%} > tol; "
                f"halving the step")
        h_cur = h_cur / 2.0
    an = analyse(x0, r0, levels, opt)

    # profiles: along nabla (beta fixed) and along the top-atom-fixed direction, quadratic fit of S
    profiles = {}
    for name in axes:
        d = e_nabla if name == "nabla" else v_fix
        pts = [{"t": 0.0, "x": x0.tolist(), "f": f0, "S": f0 * f0, "residuals": r0.tolist(),
                "n_at_cap": st["n_at_cap"], "n_at_floor": st["n_at_floor"], "on_shelf": False}]
        for t in sorted(prof_offs[name]):
            if abs(t) < 1e-12:
                continue
            x = x0 * (1.0 + t * d)
            stx = cap_status(x[0], x[1], cap_fn(x[2] if n == 3 else None), floor, n_atoms)
            fx, rx = F(x, f"{name} {t:+.3f}")
            pts.append({"t": float(t), "x": x.tolist(), "f": fx, "S": fx * fx, "residuals": rx.tolist(),
                        "n_at_cap": stx["n_at_cap"], "n_at_floor": stx["n_at_floor"],
                        "on_shelf": bool(stx["n_at_cap"] > 0 or stx["n_at_floor"] > 0)})
        pts.sort(key=lambda p: p["t"])
        smooth = [p for p in pts if not p["on_shelf"]]
        fit = quadratic_fit([p["t"] for p in smooth], [p["S"] for p in smooth])
        J_rel = an["jacobian_relative"]["richardson"]
        prof = {"direction_relative": d.tolist(), "feasible_t": ranges[name], "points": pts,
                "n_shelf_points": len(pts) - len(smooth), "quadratic_fit_S": None,
                "gauss_newton_curvature_S_same_direction": float(2.0 * np.linalg.norm(J_rel @ d) ** 2)}
        if fit is not None:
            a, b, c, rms = fit
            prof["quadratic_fit_S"] = {"S_at_0": a, "slope": b, "curvature": c, "rms_residual": rms,
                                       "n_points": len(smooth)}
        profiles[name] = prof

    f_again, _ = F(x0, "centre-again")
    path_ok = abs(f_again - f0) <= PATH_TOL * max(1.0, abs(f0))
    res.update({
        "status": "ok",
        "objective": OBJECTIVE_DEF,
        "objective_at_center": f0,
        "S_at_center": f0 * f0,
        "residuals_at_center": r0.tolist(),
        "moments_at_center": (r0 + F.targets).tolist(),
        "targets": F.targets.tolist(),
        "moment_names": list(MOMENT_NAMES),
        "engine_parity_gap": {"warm_up_f": f_warm, "centre_f": f0, "abs_diff": abs(f_warm - f0),
                              "note": "first evaluation in the process vs the second at the same point "
                                      "(the estimator's post-solve HAFISCAL_STEP5_ATI setdefault)"},
        "path_independence": {"value_again": f_again, "abs_diff": abs(f_again - f0), "ok": path_ok},
        **an,
        "profiles": profiles,
        "evaluations": evals,
        "timing": {"n_evals": len(evals), "total_s": time.time() - t_start,
                   "per_eval_s": (time.time() - t_start) / max(len(evals), 1)},
    })
    return res


def summarize_group(r, delta_frac):
    """The one-screen text block for a group."""
    e, name = r["group"], r["name"]
    p = r["point"]
    head = f"-- {name} (e={e}): beta {p['beta']:.6f}  nabla {p['nabla']:.6f}"
    if r["status"] == "refused":
        return head + f"  -> REFUSED: {r['reason']}"
    if r["status"] in ("planned", "budget"):
        return head + (f"  -> {r['status'].upper()} ({r['plan']}" + (f"; {r['reason']}" if r.get("reason") else "") + ")")
    if r["status"] == "points":
        lines = [head + f"   f0 = {r['objective_at_center']:.6f}  r0 = {_fmt_vec(r['residuals_at_center'], '{:+.4f}')}"
                 f"   [engine-parity gap {r['engine_parity_gap']:.2e}; centre re-eval "
                 f"{'identical' if r['path_independence']['ok'] else 'DIFFERS ' + format(r['path_independence']['abs_diff'], '.2e')}]"]
        for ev in r["evaluations"]:
            lines.append(f"   {ev['label']:<13s} x={['%.7f' % t for t in ev['x']]}  f={ev['f']:.8f}  "
                         f"r={_fmt_vec(ev['residuals'], '{:+.4f}')}")
        return "\n".join(lines)
    st, tm, names = r["cap"], r["timing"], r["free_params"]
    lines = [head + (f"  GICx {p['GICx']:.4f} (free)" if len(names) == 3 else f"  GICx pinned {p['GICx']:.4f}")
             + f"   f0 = {r['objective_at_center']:.6f} (S0 = {r['S_at_center']:.6f})   [{tm['n_evals']} evals, "
               f"{tm['total_s'] / 60:.1f} min, {tm['per_eval_s']:.1f} s/eval; engine-parity gap "
               f"{r['engine_parity_gap']['abs_diff']:.2e}; centre re-eval "
               f"{'identical' if r['path_independence']['ok'] else 'DIFFERS ' + format(r['path_independence']['abs_diff'], '.2e')}]"]
    lines.append("   residuals r0 = model − data (pp): "
                 + "  ".join(f"{m} {v:+.3f}" for m, v in zip(r["moment_names"], r["residuals_at_center"])))
    su = r["steps_used"]
    lines.append(f"   cap {st['cap']:.6f}: top atom {st['a_hi']:.6f} (margin {st['margin_top']:.2e}); floor "
                 f"{st['floor']:g}: bottom atom {st['a_lo']:.4f}  -> stencil inside the smooth region; steps "
                 f"used rel {su['coarse_rel']:.2e} and {su['fine_rel']:.2e} ({su['levels_evaluated']} levels)")
    jd = np.asarray(r["jacobian"]["rel_discrepancy"])
    noise = np.asarray(r["jacobian"]["noise_dominated"])
    lines.append(f"   Jacobian h-vs-h/2 discrepancy (column-scaled): max {float(np.max(jd)):.1%}, per parameter "
                 + ", ".join(f"{nm} {float(np.max(jd[:, i])):.1%}" for i, nm in enumerate(names))
                 + ("   ** noise-dominated entries present" if noise.any() else "   (resolved)"))
    Jr = np.asarray(r["jacobian_relative"]["richardson"])
    lines.append("   relative Jacobian (pp per unit relative move), rows = moments, cols = " + ", ".join(names)
                 + ": " + _fmt_mat(Jr, "{:+.3e}"))
    idn = r["identification"]
    s, V = np.asarray(idn["singular_values"]), np.asarray(idn["directions_columns"])
    lines.append("   identification (SVD of the relative Jacobian): "
                 + "   ".join(f"sigma_{k + 1} = {s[k]:.3e} v_{k + 1} = {_fmt_vec(V[:, k], '{:+.3f}')}" for k in range(s.size))
                 + f"   condition {idn['condition_number']:.3g}")
    lines.append(f"   top-atom-fixed direction {_fmt_vec(idn['top_atom_fixed_direction'], '{:+.3f}')}: sigma "
                 f"{idn['sigma_along_top_atom_fixed']:.3e} ({idn['angle_deg_weak_vs_top_atom_fixed']:.1f} deg "
                 f"from the weakest SVD direction)")
    hs = r["hessian_S"]
    lines.append(f"   curvature of S (relative coords): Gauss-Newton 2J'J {_fmt_mat(hs['gauss_newton_relative'], '{:+.3e}')}; "
                 f"full FD {_fmt_mat(hs['relative_coords'], '{:+.3e}')} (h-vs-h/2 max "
                 f"{float(np.max(np.asarray(hs['rel_discrepancy']))):.0%}); residual-curvature share "
                 f"{hs['residual_curvature_share']:.2f}")
    stn = r["stationarity"]
    if stn["gauss_newton_step_relative"] is None:
        lines.append(f"   stationarity: gradient of S (relative) {_fmt_vec(stn['gradient_S_relative'])}; J'J singular -> no GN step")
    else:
        lines.append(f"   stationarity: gradient of S (relative) {_fmt_vec(stn['gradient_S_relative'])}; Gauss-Newton step "
                     + "  ".join(f"{nm} {_pct(v)}" for nm, v in zip(names, stn["gauss_newton_step_relative"]))
                     + f"  -> predicted f {stn['predicted_f']:.4f} vs f0 {r['objective_at_center']:.4f} "
                       f"({stn['predicted_improvement_frac']:+.1%}); installed point is this objective's minimum to "
                       f"{stn['tolerance_improvement_frac']:.0%}: {'yes' if stn['installed_point_is_minimum_to_tol'] else 'NO'}")
    iso = r["iso_objective"]
    hw_svd, hw_ax, hw_fix = (np.asarray(iso["halfwidths_relative_along_svd_directions"]),
                             np.asarray(iso["halfwidths_relative_axis_aligned"]),
                             np.asarray(iso["halfwidths_relative_top_atom_fixed"]))
    lines.append(f"   iso-objective moves (f0 -> f0 + {delta_frac:.0%} f0): along v_k "
                 + "  ".join(f"v_{k + 1} [{_pct(hw_svd[k, 0])}, {_pct(hw_svd[k, 1])}]" for k in range(hw_svd.shape[0]))
                 + "; one parameter at a time "
                 + "  ".join(f"{nm} [{_pct(hw_ax[i, 0])}, {_pct(hw_ax[i, 1])}]" for i, nm in enumerate(names))
                 + f"; top-atom-fixed [{_pct(hw_fix[0])}, {_pct(hw_fix[1])}]   (curvature under the objective's own "
                   "metric — NOT standard errors)")
    for name, pr in r["profiles"].items():
        pts = "  ".join(f"t={q['t']:+.3f} f={q['f']:.4f}{'*' if q['on_shelf'] else ''}" for q in pr["points"])
        txt = f"   profile along {name}: {pts}" + ("   (* = on the clip shelf)" if pr["n_shelf_points"] else "")
        txt += f"   feasible t in [-{pr['feasible_t']['down']:.3f}, +{pr['feasible_t']['up']:.3f}]"
        qf = pr["quadratic_fit_S"]
        if qf:
            txt += (f"; quadratic fit of S: curvature {qf['curvature']:+.3e} vs Gauss-Newton "
                    f"{pr['gauss_newton_curvature_S_same_direction']:+.3e}, rms {qf['rms_residual']:.2e}")
        lines.append(txt)
    return "\n".join(lines)


def _provenance(ctx):
    sha = None
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True,
                             timeout=10).stdout.strip() or None
    except Exception:
        pass
    return {"created": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(), "git_sha": sha, "python": sys.version.split()[0],
            "argv_tail": ctx["argv_tail"], "cwd_tool": HERE,
            "env_hafiscal": {k: v for k, v in sorted(os.environ.items()) if k.startswith("HAFISCAL_")}}


def parse_groups(text):
    text = text.strip().lower()
    if text == "all":
        return [0, 1, 2]
    groups = sorted({int(t) for t in text.replace(",", " ").split()})
    if any(g not in (0, 1, 2) for g in groups) or not groups:
        raise argparse.ArgumentTypeError(f"--educ must be 0, 1, 2, a comma list, or all; got {text!r}")
    return groups


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 epilog="Curvature under the objective's own metric — NOT standard errors.")
    ap.add_argument("--educ", default="0", type=parse_groups,
                    help="education group(s): 0 (dropout, cheapest), 1, 2, a comma list, or all")
    ap.add_argument("--rel-step", type=float, default=1e-3, help="relative finite-difference step h (default 1e-3)")
    ap.add_argument("--max-halvings", type=int, default=2,
                    help="extra step halvings beyond h/2 while the Jacobian discrepancy exceeds the tolerance")
    ap.add_argument("--richardson-tol", type=float, default=0.25,
                    help="h-vs-h/2 relative discrepancy above which an entry is flagged noise-dominated")
    ap.add_argument("--profile-axis", choices=("nabla", "top_atom_fixed", "both"), default="both",
                    help="profile along nabla (beta fixed), along the top-atom-fixed direction, or both")
    ap.add_argument("--profile-offsets", type=float, nargs="*", default=None,
                    help="explicit relative offsets t for the profiles (points beyond the cap are evaluated "
                         "and flagged as shelf points); default: two points each side within the feasible range")
    ap.add_argument("--profile-span", type=float, default=0.30, help="default profile half-range (relative)")
    ap.add_argument("--delta-f-frac", type=float, default=0.01,
                    help="iso-objective level as a fraction of f0 for the half-widths (default 1%%)")
    ap.add_argument("--stationarity-tol", type=float, default=0.10,
                    help="largest predicted Gauss-Newton improvement of f (fraction of f0) still called stationary")
    ap.add_argument("--points", nargs="*", default=None,
                    help="evaluate only these points 'beta,nabla[,GICx]' (after a warm-up and the centre); "
                         "no derivatives — the fresh-process cross-check mode")
    ap.add_argument("--sor-file", default=None, help="DiscFacEstim_*.txt to read the point from (default: the "
                                                     "estimator's own suffix-named file in Results/)")
    ap.add_argument("--argv", default="", help="argv tail for the estimator (Rfree CRRA IncUnemp NoB Splurge); "
                                             "EMPTY = the production do_all invocation")
    ap.add_argument("--out-dir", default=None, help="where to write the JSON + summary (default: Results/, "
                                                    "or HAFISCAL_RESULTS_OUT_DIR)")
    ap.add_argument("--out-stem", default=None, help="override the output file stem (default from the tag/groups)")
    ap.add_argument("--budget-min", type=float, default=None,
                    help="abort a group before its stencil if the projected wall (from the centre eval) exceeds this")
    ap.add_argument("--dry-run", action="store_true", help="refusal checks + plan only; no economy build")
    return ap


def main(argv=None):
    opt = build_parser().parse_args(argv)

    reason = median_refusal()
    if reason is not None:
        print(f"[curvature] REFUSED: {reason}", file=sys.stderr)
        return EXIT_NODE_MEDIAN

    _, _, _, res_dir = _probe.estimator_paths()
    mtimes = _probe.snapshot_results_mtimes(res_dir)
    try:
        ctx = build_context(opt.argv, opt.dry_run)
    except RuntimeError as err:
        print(f"[curvature] FAIL: {err}", file=sys.stderr)
        return EXIT_EXEC_FAIL
    sor_file, note = resolve_sor_file(ctx, opt.sor_file)
    sor = _probe.load_sor(sor_file)
    print(f"[curvature] tag {ctx['tag']}; installed point from {sor_file}; GICx mode {ctx['gicx_mode']}; "
          f"median {_median_mode()}; objective = {OBJECTIVE_DEF}")
    if note:
        print(f"[curvature] note: {note}")

    results = {}
    for e in opt.educ:
        if e not in sor:
            print(f"[curvature] {EDUC_NAMES[e]} (e={e}): no row in {sor_file}; skipped")
            continue
        results[e] = run_group(ctx, e, sor[e], opt)

    out_dir = (os.path.abspath(opt.out_dir) if opt.out_dir
               else os.environ.get("HAFISCAL_RESULTS_OUT_DIR", "").strip() or ctx["res_dir"])
    os.makedirs(out_dir, exist_ok=True)
    stem = opt.out_stem or (ctx["tag"] + ("" if opt.educ == [0, 1, 2] else "_edType" + "".join(str(e) for e in opt.educ))
                            + ("_points" if opt.points else ""))
    json_path = os.path.join(out_dir, stem + "_curvature.json")
    txt_path = os.path.join(out_dir, stem + "_curvature_summary.txt")

    head = [f"== Step-2 curvature / identification diagnostic — {ctx['tag']} — curvature under the objective's "
            f"own metric, NOT standard errors (no moment covariance exists) ==",
            f"objective: {OBJECTIVE_DEF}",
            f"GICx mode {ctx['gicx_mode']}; median {_median_mode()}; point from {os.path.basename(sor_file)}; "
            f"rel step {opt.rel_step:g} (+ up to {opt.max_halvings} extra halvings); iso level {opt.delta_f_frac:.0%} of f0"]
    body = [summarize_group(results[e], opt.delta_f_frac) for e in sorted(results)]
    summary = "\n".join(head + body)
    print("\n" + summary + "\n")

    payload = {"schema": SCHEMA, "what_this_is": __doc__.split("\n\n")[1].strip(),
               "not_standard_errors": ("No moment covariance exists; (J'J)^-1 is not a covariance matrix. "
                                       "Curvature under the objective's own metric only."),
               "record_supports": ("weak identification of nabla for the WEALTH-DISTRIBUTION fit (owner "
                                   "2026-08-13; 2026-07-23 dropout ridge, which lies on the clip shelf); NOT "
                                   "'little consequence for the paper's results' (BUG-047 chain: the wealth fit "
                                   "does not pin the multipliers across regimes; ridge-end 5a runs not done)"),
               "tag": ctx["tag"], "sor_file": sor_file, "registry_note": note,
               "settings": {k: (v if not isinstance(v, list) else list(v)) for k, v in vars(opt).items()},
               "provenance": _provenance(ctx),
               "groups": {str(e): results[e] for e in sorted(results)},
               "summary_text": summary}
    if not opt.dry_run:
        with open(json_path, "w") as fh:
            json.dump(_py(payload), fh, indent=1)
        with open(txt_path, "w") as fh:
            fh.write(summary + "\n")
        print(f"[curvature] wrote {json_path}\n[curvature] wrote {txt_path}")

    changed = [f for f in _probe.changed_results(mtimes) if os.path.abspath(f) not in (json_path, txt_path)]
    if changed:
        print(f"PROBE_WRITE_VIOLATION: {changed}", file=sys.stderr)
        return EXIT_WRITE_TRAP
    if results and all(r["status"] == "refused" for r in results.values()):
        return EXIT_ALL_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
