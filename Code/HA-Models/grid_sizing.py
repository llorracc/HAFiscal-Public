"""grid_sizing.py — endogenous asset-grid maxima for HAFiscal (solve grid vs TM grid).

WHY THIS EXISTS
===============
HAFiscal sizes two asset grids, and historically BOTH were hand-set with no link to the
calibration:
  * the household SOLVE grid `aXtraMax` (was hard-coded 40 in EstimParameters.py, no override);
  * the transition-matrix TM grid `aMax` (hand-set 1300 via HAFISCAL_TM_AMAX).
When the calibration or `theGICfactor` moves, both had to be re-derived by hand. This module
computes both ENDOGENOUSLY from buffer-stock patience factors, so they adapt to how patient the
agents are, and so a future maintainer can trace every number to its origin.

The two grids answer DIFFERENT questions and key off DIFFERENT objects:

  SOLVE grid  — "how far out must the cFunc be solved so its PF-asymptote (decay) extrapolation
                is accurate?"  Governed by the RETURN-patience gap MPCmin = 1 − Þ_Liv/R (the rate
                at which c'(m) → MPCmin).  EXISTS under the Return Impatience Condition (RIC),
                which is much weaker than the growth conditions — so it is robust.
  TM grid     — "how far does the ergodic wealth DISTRIBUTION's upper tail reach?"  This tail is
                a Pareto/Kesten power law (see below), whose (1−p) quantile is too sensitive to
                the tail exponent ζ for a clean closed form.  The PRODUCTION engine therefore
                MEASURES it (`adaptive_grid_tm.production_aMax()`).  This module supplies a
                robust ANALYTIC estimate `ϕ·(1+h)` for cross-checking that measurement and as a
                FALLBACK when the measurement is unavailable (see GIC-Mod-failure note).

THE THREE GAPS (per discount-factor atom; Þ = (Rβ)^{1/ρ}, Þ_Liv = (RβƐ)^{1/ρ}, Ɛ=LivPrb=Ɫ):
  return-patience   MPCmin   = 1 − Þ_Liv/R                       → SOLVE grid (decay reach)
  modified-growth   gap_MOD  = 1 − Ɫ·Þ·E[1/ψ]/Γ                  → individual normalized target
  raw-growth        gap_RAW  = 1 − Ɫ·Þ/Γ                          → aggregate (level) pseudo-target
Mortality enters MPCmin as IMPATIENCE (inside Þ_Liv) and the sustainable locus as wealth
EROSION (the −D in ω = r−g−D).  These are the two distinct mortality channels.

WHAT THE EXPERIMENTS FOUND (2026-06-24, real ESC calibration, GIC-cap atom of each group;
see prompts_local/2026-06-24_grid-sizing-experiments-journal.md, scripts scratchpad/exp{1,2,3}*):
  * gap_RAW (+0.00349), gap_MOD (+0.00050), and the Kesten tail exponent ζ (≈3.0) are IDENTICAL
    across Dropout/HS/College — they are pinned by `theGICfactor` (gap_MOD = 1−theGICfactor;
    gap_RAW = 1−theGICfactor/E[1/ψ]).  So `C/gap` formulas CANNOT size a per-group grid, and
    gap_MOD > 0 means GIC-Mod actually HOLDS (barely) at every cap.
  * Human wealth h is the group-varying income scale: Dropout 151 < HS 181 < College 195.
    Analytic h (mom_bounds.solve_markov_human_wealth, the (I−W)⁻¹W@E[inc] solve) == HARK's
    solved-cFunc asymptote h to 0.1 (cross-check passed).  h needs only FHWC (Γ<R) — robust.
  * The ergodic wealth tail is Pareto with ζ≈3: q(1−p) ≈ x_min·p^{−1/ζ}.  For p=1e-4, ζ=3:
    p^{−1/ζ}=21.5.  MEASURED (1−1e-4) quantiles: Dropout 1149, HS 1217, College 1224 — within 7%,
    College largest, so ONE global grid (College → round-100 → 1300) covers all groups (matches
    production_aMax and adaptive_grid_tm's single-grid design).
  * `ϕ ≡ q/(1+h)` drifts 6.24 (College) → 7.54 (Dropout): the Pareto scale x_min≈57 is pinned, so
    the tail barely moves with h.  Hence `ϕ·(1+h)` is a ±20% analytic ESTIMATE, not exact — fine
    for a cross-check / guard / fallback, NOT a replacement for the measurement.
  * SOLVE-grid decay: error ≈ C1·exp(−MPCmin·m), C1≈0.034.  College needs aXtraMax≈228 for 1% tail
    accuracy (vs the legacy 40 → 2.88%); HS/Dropout need less (larger MPCmin).

GIC-MOD-FAILURE ROBUSTNESS (the owner's hard constraint)
========================================================
For calibrations/atoms where GIC-Liv-Mod FAILS (gap_MOD ≤ 0), the NORMALIZED ergodic wealth
distribution has no stationary point — `production_aMax()` cannot measure a quantile (mass
escapes the grid).  In that regime use the analytic `tm_grid_aMax` (the Pareto/wealth-scale form),
which needs only GIC-Liv-Raw (ζ>0) + FHWC (finite h) — both strictly weaker than GIC-Mod.  The
finite life-cycle keeps wealth bounded even then; the analytic value sizes the reach.  GUARDS here
refuse and name the failing atom when RIC (MPCmin≤0), the wealth scale (h non-finite), or the
Pareto exponent (ζ≤0) break.

RE-DERIVATION (do this if R, ρ, the calibration, or theGICfactor changes)
=========================================================================
  * MPCmin, h, gaps, ζ: rerun scratchpad/exp1_factors.py.
  * ϕ and the per-group tails: rerun scratchpad/exp2_tail.py (or adaptive_grid_tm.production_aMax()).
  * C1/bar: rerun scratchpad/exp3_decay_realG.py.
  * The constants below (SOLVE_C1, TM_PHI, PARETO_THRESHOLD) are those measurements; update them.

BST anchors: pseudo-target / GICRaw `thm-MSSBalExists`, `eq-balgrostable`; individual target /
GICMod `thm-target`; ordering m̌≤m̂ `lemma-orderingPartOne`; mortality / GIC-Liv-Mod `sec-Mortality`,
`eq-GICLivMod`; cFunc′→MPCmin `prop-convgGrowth`.  (BufferStockTheory-Latest/_ai/concepts/.)

This module is PURE and env-free (no os.environ reads — the wiring layer in EstimParameters.py
owns the flags).  It must NOT import hark_fti (it is on the DEFAULT reproduction path).  It reuses
mom_bounds.py (same directory; pure numpy) for the human-wealth solve and MPCmin.
"""
from __future__ import annotations

import math
import os
import sys
import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np

# Reuse the local, hark_fti-free MoM bounds (same directory). Path-robust so this works whether
# imported as `grid_sizing` from Code/HA-Models or from FromPandemicCode (EstimParameters adds the
# parent to sys.path). mom_bounds.compute_mpc_min == 1−(R·β·Ɫ)^{1/ρ}/R; solve_markov_human_wealth
# == the (I−W)⁻¹W@E[inc] human-wealth fixed point.
try:
    from mom_bounds import compute_mpc_min, solve_markov_human_wealth, FHWC_GAP
except ImportError:  # pragma: no cover - path fallback
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from mom_bounds import compute_mpc_min, solve_markov_human_wealth, FHWC_GAP


# ---------------------------------------------------------------------------
# Calibrated constants (MEASURED 2026-06-24 — re-derive via the scripts named above)
# ---------------------------------------------------------------------------
# Solve grid: error ≈ C1·exp(−MPCmin·m). C1≈0.034 fitted (E3); rounded UP to 0.04 so the grid is
# never undersized. bar = target max relative decay-extrapolation error over [aXtraMax, tm_aMax].
SOLVE_C1 = 0.04
SOLVE_BAR = 0.01            # 1% tail accuracy (Step-2 β is insensitive — moments sit at m≈6 ≪ grid)

# TM grid analytic estimate: aMax ≈ ϕ·(1+h). Measured ϕ = q/(1+h) ∈ [6.24 College, 7.54 Dropout].
# Default 6.5 (≈ College, the binding single-global group; reproduces production 1300 after round).
# Conservative 7.5 (the max) for the GIC-Mod-failure fallback so no group is undersized.
TM_PHI = 6.5
TM_PHI_CONSERVATIVE = 7.5
PARETO_THRESHOLD = 1e-4     # (1−threshold) quantile = the grid's upper-tail coverage target
TM_ROUND_TO = 100.0         # match adaptive_grid_tm.production_aMax rounding


# ---------------------------------------------------------------------------
# Patience factors (full diagnostic bundle)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PatienceFactors:
    """Buffer-stock patience diagnostics for one discount-factor atom.

    All factors use Þ = (Rβ)^{1/ρ} (no mortality) and Þ_Liv = (RβƐ)^{1/ρ} (mortality in the
    discount), with Ɛ = LivPrb = Ɫ. See the module docstring for the derivations.
    """
    R: float
    beta: float
    CRRA: float
    LivPrb: float
    PermGroFac: float
    Ex_inv_PermShk: float
    MPCmin: float          # 1 − Þ_Liv/R  (return patience; sets the SOLVE grid)
    GPFacRaw_Liv: float    # Ɫ·Þ/Γ        (raw growth patience; aggregate level)
    GPFacMod_Liv: float    # Ɫ·Þ·E[1/ψ]/Γ (modified; individual normalized target)
    gap_RAW: float         # 1 − GPFacRaw_Liv
    gap_MOD: float         # 1 − GPFacMod_Liv
    omega: float           # r − g − D  (sustainable-locus slope; <0 ⟹ Pareto tail well-behaved)
    hNrm: Optional[float]  # employed-state human wealth (PDV future income); None if not supplied
    zeta: Optional[float]  # Kesten/Pareto tail exponent; None if not supplied


def patience_factors(R, beta, CRRA, LivPrb, PermGroFac, Ex_inv_PermShk,
                     MrkvArray=None, E_inc=None,
                     perm_shock_vals=None, perm_shock_pmv=None) -> PatienceFactors:
    """Compute the buffer-stock patience factors for one atom.

    Scalar factors (MPCmin, gaps, ω) need only the scalars. Pass `MrkvArray` + `E_inc`
    (per-Markov-state expected income E[ψθ]) to also get human wealth `hNrm`, and the
    permanent-shock marginal (`perm_shock_vals`,`perm_shock_pmv`) to also get the Kesten ζ.
    """
    R = float(R); beta = float(beta); rho = float(CRRA); Liv = float(LivPrb); G = float(PermGroFac)
    Th = (R * beta) ** (1.0 / rho)                       # Þ = (Rβ)^{1/ρ}  (no mortality)
    MPCmin = compute_mpc_min(R, beta, rho, Liv)          # 1 − (RβƐ)^{1/ρ}/R
    GPFacRaw_Liv = Liv * Th / G                          # Ɫ·Þ/Γ
    GPFacMod_Liv = GPFacRaw_Liv * float(Ex_inv_PermShk)  # ·E[1/ψ]
    gap_RAW = 1.0 - GPFacRaw_Liv
    gap_MOD = 1.0 - GPFacMod_Liv
    omega = (R - 1.0) - (G - 1.0) - (1.0 - Liv)          # r − g − D

    hNrm = None
    if MrkvArray is not None and E_inc is not None:
        Pi = np.asarray(MrkvArray, dtype=float)
        S = Pi.shape[0]
        h = solve_markov_human_wealth(Pi, np.full(S, R), np.asarray(E_inc, dtype=float),
                                      PermGroFac_by_state=np.full(S, G))
        hNrm = float(h[0])  # employed-state (index 0) human wealth — the relevant tail scale

    zeta = None
    if perm_shock_vals is not None and perm_shock_pmv is not None:
        zeta = kesten_zeta(GPFacRaw_Liv, perm_shock_vals, perm_shock_pmv, LivPrb=Liv)

    return PatienceFactors(R=R, beta=beta, CRRA=rho, LivPrb=Liv, PermGroFac=G,
                           Ex_inv_PermShk=float(Ex_inv_PermShk), MPCmin=MPCmin,
                           GPFacRaw_Liv=GPFacRaw_Liv, GPFacMod_Liv=GPFacMod_Liv,
                           gap_RAW=gap_RAW, gap_MOD=gap_MOD, omega=omega, hNrm=hNrm, zeta=zeta)


def kesten_zeta(GPFacRaw_Liv, perm_shock_vals, perm_shock_pmv, LivPrb=1.0):
    """Kesten/Pareto tail exponent ζ of the ergodic normalized-wealth distribution.

    The stationary wealth ratio is approximately autoregressive, a_{t+1} ≈ A·a_t with multiplier
    A = Ɫ·Þ/(Γ·ψ) = GPFacRaw_Liv/ψ (ψ = permanent shock).  Its power-law tail exponent ζ solves
    the Kesten equation E[A^ζ] = 1, i.e. Ɫ·E[(GPFacRaw_Liv/ψ)^ζ] = 1.  ζ governs the (1−p)
    quantile: q(1−p) ≈ x_min·p^{−1/ζ}.  ζ>1 ⟹ finite mean; ζ>2 ⟹ finite variance.  At the HAFiscal
    GIC cap, this function (the DISCRETE 7-point ψ distribution) gives ζ≈3.0; the LOGNORMAL closed
    form L·(Þ_Liv/Γ)^ζ·exp(ζ(ζ+1)σ²/2)=1 — the exact quadratic (σ²/2)ζ²+(ln(Þ_Liv/Γ)+σ²/2)ζ+ln L=0 —
    gives ζ≈2.82 (the discrete dstn truncates ψ's tails, lowering E[ψ^{−ζ}], so it reads a touch higher).
    Both round to "≈3"; the measured ergodic quantile (adaptive_grid_tm.production_aMax) is ground truth.
    See BUGS_private/HAFiscal_BUG-061_*.md §math (a).  Returns NaN if no root in (0, 20].
    """
    from scipy.optimize import brentq
    psi = np.asarray(perm_shock_vals, dtype=float)
    pmv = np.asarray(perm_shock_pmv, dtype=float)
    Liv = float(LivPrb)

    def f(z):
        return Liv * float(np.dot(pmv, (GPFacRaw_Liv / psi) ** z)) - 1.0

    try:
        if f(1e-6) * f(20.0) > 0:
            return float('nan')
        return float(brentq(f, 1e-6, 20.0))
    except Exception:
        return float('nan')


# ---------------------------------------------------------------------------
# FHWC test + large-constant fallback (owner ruling 2026-06-24; BUG-061 §math (c))
# ---------------------------------------------------------------------------
# When the Finite-Human-Wealth Condition FAILS (Γ ≥ R; Markov: ρ(Π·Γ/R) ≥ 1), human wealth h is
# INFINITE: the PF-asymptote intercept κ_min·h diverges, the Kesten additive term B ∝ h diverges
# (so the Pareto scale x_min — and any quantile-derived aMax — is undefined), and the GPF is pushed
# to/over 1 (ζ→0, tail non-integrable). BOTH the wealth scale AND the tail shape blow up, so there is
# NO finite quantile-derived aMax. The defensive choice is a large fixed constant, far beyond any
# economically relevant resource the finite-horizon simulation visits.
FHWC_FALLBACK_AMAX = 10000.0


def fhwc_holds(R, PermGroFac, MrkvArray=None, fhwc_gap=FHWC_GAP):
    """Finite-Human-Wealth Condition test (WITH a conditioning margin) — depends on Γ,R ONLY (NOT β),
    so it holds/fails for a whole education group at once.

    Scalar:  Γ/R < 1/(1+fhwc_gap).
    Markov:  spectral radius ρ(W) < 1/(1+fhwc_gap), W = Π·Γ/R (the growth/return-discounted income
             operator whose Neumann series gives h = (I−W)⁻¹W·𝟙; reduces to Γ/R<1 in the scalar case).
    The default fhwc_gap=FHWC_GAP (0.005) requires human wealth to be finite AND well-conditioned
    (h ∼ E[y]/ε; see mom_bounds.FHWC_GAP); fhwc_gap=0 recovers the bare FHWC (ρ<1). Returns True iff
    the PF human-wealth bound is trustworthy. When False, size the grid with FHWC_FALLBACK_AMAX.
    """
    R = float(R); G = float(PermGroFac)
    thresh = 1.0 / (1.0 + float(fhwc_gap))
    if MrkvArray is None:
        return (G / R) < thresh
    W = (G / R) * np.asarray(MrkvArray, dtype=float)
    return float(np.max(np.abs(np.linalg.eigvals(W)))) < thresh


# ---------------------------------------------------------------------------
# SOLVE grid — household cFunc solve range (decay-extrapolation reach)
# ---------------------------------------------------------------------------
def solve_grid_aMax(R, beta, CRRA, LivPrb, *, PermGroFac=None, MrkvArray=None,
                    C1=SOLVE_C1, bar=SOLVE_BAR, tm_cap=None):
    """Endogenous household SOLVE-grid maximum `aXtraMax` for one atom.

    The PF-asymptote (decay) extrapolation error of the solved cFunc above the grid falls as
    err(m) ≈ C1·exp(−MPCmin·m)  (E3: rate fitted 0.00529 ≈ MPCmin 0.00542; prefactor C1≈0.034).
    Solving err = bar gives

        aXtraMax = ln(C1 / bar) / MPCmin .

    Keyed off MPCmin (return patience), which exists under the RIC alone — robust to GIC/GIC-Mod
    failure.  Capped at `tm_cap` (the TM grid) since solving past it buys nothing.  At the HAFiscal
    College cap (MPCmin=0.00542) with bar=0.01 this is ≈256 (vs the legacy 40 → 2.88% tail error);
    HS/Dropout get smaller grids (larger MPCmin).

    CAVEAT (hard-wired so a future maintainer can trace a surprise): this assumes the cFunc is
    decay-extrapolated above the grid (HARK's 1D ConsMarkovModel does this correctly).  HAFiscal's
    2D AggShock solve (AggFiscalModel.py:1908) currently extrapolates NAIVE-LINEAR (the parked
    PF-decay-drop fix) — with that path, this aXtraMax under-delivers tail accuracy; either apply
    the decay fix or set aXtraMax = tm_cap to avoid extrapolation entirely.  Step-2 β is unaffected
    regardless (its moments live at m≈6 ≪ aXtraMax).

    If `PermGroFac` is given and the FHWC fails (Γ≥R), there is no finite PF asymptote to decay
    toward, so this returns `FHWC_FALLBACK_AMAX` instead (see `fhwc_holds`, BUG-061 §math (c)).
    """
    R = float(R); beta = float(beta); rho = float(CRRA); Liv = float(LivPrb)
    if PermGroFac is not None and not fhwc_holds(R, PermGroFac, MrkvArray):
        warnings.warn(f"solve_grid_aMax: FHWC fails or is within the conditioning margin "
                      f"(Γ={float(PermGroFac)}, R={R}; ρ(Π·Γ/R) ≥ 1/(1+FHWC_GAP)) — human wealth is "
                      f"infinite or ill-conditioned, no trustworthy PF asymptote to decay toward. "
                      f"Returning FHWC_FALLBACK_AMAX={FHWC_FALLBACK_AMAX} (BUG-061 §math (c)).")
        return float(FHWC_FALLBACK_AMAX)
    MPCmin = compute_mpc_min(R, beta, rho, Liv)
    if not (MPCmin > 0.0):
        raise ValueError(
            f"solve_grid_aMax: MPCmin={MPCmin:.6g} ≤ 0 — Return Impatience Condition (RIC) "
            f"fails for R={R}, beta={beta}, CRRA={rho}, LivPrb={Liv}; the PF asymptote has no "
            f"decay and the grid cannot be sized this way.")
    if not (0.0 < bar < C1):
        raise ValueError(f"solve_grid_aMax: need 0 < bar < C1 (got bar={bar}, C1={C1}); "
                         f"ln(C1/bar) must be positive.")
    aMax = math.log(C1 / bar) / MPCmin
    if tm_cap is not None:
        aMax = min(aMax, float(tm_cap))
    return float(aMax)


def solve_grid_count(aXtraMax, *, aXtraMin, legacy_aMax, legacy_count):
    """aXtraCount that PRESERVES the near-0 grid density when aXtraMax is extended.

    HARK's make_grid_exp_mult spaces `count` points roughly uniformly in LOG over [aXtraMin, aMax],
    so the density per log-unit is count/ln(aMax/aMin). Extending aMax at a fixed count therefore
    THINS the moment-relevant region (m≈6) — which shifts the estimated beta. To hold that density
    (and beta) constant, scale the count by the log-range ratio:

        count = ceil(legacy_count · ln(aXtraMax/aMin) / ln(legacy_aMax/aMin)).

    WHY THIS MATTERS (hard-wired so a future maintainer can trace a beta surprise): with the legacy
    aXtraMax=40, count=48 there are 37 gridpoints ≤ m=6; extending to 240 at the SAME count=48 drops
    that to 33 and shifts the HS Step-2 beta by ~0.31% (E4 moment-neutral check, 2026-06-24). The
    scaled count restores it (240 → 57 → ≥39 points ≤6 ≈ the legacy 37), making the endogenous grid
    beta-neutral. Measured scaled counts: Dropout 205→56, HS 240→57, College 256→57. Re-derive via
    the grid-density diagnostic in prompts_local/2026-06-24_grid-sizing-experiments-journal.md (E5).
    """
    aXtraMin = float(aXtraMin); legacy_aMax = float(legacy_aMax); legacy_count = int(legacy_count)
    if not (aXtraMax > legacy_aMax):
        return legacy_count
    if not (0.0 < aXtraMin < legacy_aMax):
        raise ValueError(f"solve_grid_count: need 0 < aXtraMin < legacy_aMax (got aXtraMin={aXtraMin}, "
                         f"legacy_aMax={legacy_aMax}).")
    ratio = math.log(float(aXtraMax) / aXtraMin) / math.log(legacy_aMax / aXtraMin)
    return int(math.ceil(legacy_count * ratio))


# ---------------------------------------------------------------------------
# TM grid — ergodic wealth-distribution tail reach (analytic estimate / fallback)
# ---------------------------------------------------------------------------
def tm_grid_aMax(hNrm, *, phi=TM_PHI, threshold=PARETO_THRESHOLD, round_to=TM_ROUND_TO):
    """Analytic estimate of the TM-grid maximum `aMax` ≈ ϕ·(1+h).

    The ergodic wealth tail is Pareto(ζ≈2.8–3): q(1−p) ≈ x_min·p^{−1/ζ}, x_min ≈ 0.31·(1+h) (measured),
    p^{−1/ζ}=21.5 at p=1e-4 — collapsing to ϕ·(1+h) with ϕ≈6.5 (the binding College value; the
    measured range is 6.24–7.54, drifting up for less-patient groups because x_min is pinned by
    theGICfactor while h shrinks).  Accurate to ≈±20%.

    USE:
      * As a CROSS-CHECK of the measured `production_aMax()` (flag if they disagree by >~25%).
      * As the GIC-Mod-FAILURE FALLBACK: when gap_MOD ≤ 0 the normalized ergodic does not converge
        and production_aMax cannot measure — then this analytic value (needs only finite h via FHWC)
        sizes the grid; pass phi=TM_PHI_CONSERVATIVE (7.5) so no atom is undersized.
    `hNrm` should be the employed-state human wealth of the MOST-PATIENT (GIC-cap) atom of the
    binding (College) group, since the production TM grid is a single global grid sized to it.
    """
    h = float(hNrm)
    if not math.isfinite(h):
        warnings.warn(f"tm_grid_aMax: hNrm={hNrm} is non-finite — FHWC fails (human wealth infinite); "
                      f"returning FHWC_FALLBACK_AMAX={FHWC_FALLBACK_AMAX} (BUG-061 §math (c)).")
        return float(FHWC_FALLBACK_AMAX)
    if h < 0.0:
        raise ValueError(f"tm_grid_aMax: hNrm={hNrm} < 0 — human wealth cannot be negative; the (I−W) "
                         f"solve is broken. Review the income/transition inputs.")
    aMax = float(phi) * (1.0 + h)
    if round_to:
        aMax = math.ceil(aMax / round_to) * round_to
    return float(aMax)


def pareto_tail_aMax(x_min, zeta, *, threshold=PARETO_THRESHOLD, round_to=TM_ROUND_TO):
    """Pareto-quantile TM-grid estimate: aMax ≈ x_min · threshold^{−1/ζ}.

    The structurally-honest form (x_min = the scale at which the power-law tail sets in, ζ = the
    Kesten exponent).  Exponentially ζ-sensitive — why production_aMax MEASURES rather than uses
    this — but it is the right object when GIC-Mod fails and no measured quantile exists.
    """
    x_min = float(x_min); zeta = float(zeta)
    if not (zeta > 0.0):
        raise ValueError(f"pareto_tail_aMax: zeta={zeta} ≤ 0 — no finite Pareto quantile "
                         f"(GIC-Liv-Raw fails); even the life-cycle-bounded reach is undefined here.")
    aMax = x_min * threshold ** (-1.0 / zeta)
    if round_to:
        aMax = math.ceil(aMax / round_to) * round_to
    return float(aMax)


if __name__ == "__main__":
    # Smoke check against the measured College GIC-cap atom (E1/E2/E3, 2026-06-24).
    R, rho, Liv = 1.01, 2.0, 1.0 - 1.0 / 160.0
    beta_cap_college, G_college, EinvPsi = 1.005369, 1.004895, 1.003004
    h_college = 195.1
    pf = patience_factors(R, beta_cap_college, rho, Liv, G_college, EinvPsi)
    print(f"College cap: MPCmin={pf.MPCmin:.5f} (exp 0.00542)  gap_RAW={pf.gap_RAW:+.5f} (exp +0.00349)  "
          f"gap_MOD={pf.gap_MOD:+.5f} (exp +0.00050)  omega={pf.omega:+.6f} (exp -0.00115)")
    sg = solve_grid_aMax(R, beta_cap_college, rho, Liv, tm_cap=1300.0)
    print(f"solve_grid_aMax(bar=0.01) = {sg:.0f}  (E3 fit: ~228-256)")
    tg = tm_grid_aMax(h_college)
    print(f"tm_grid_aMax(h=195.1, phi=6.5) = {tg:.0f}  (production_aMax = 1300)")
    print(f"tm_grid_aMax(h=195.1, phi=7.5 conservative) = {tm_grid_aMax(h_college, phi=TM_PHI_CONSERVATIVE):.0f}")
    print(f"pareto_tail_aMax(x_min=57, zeta=3) = {pareto_tail_aMax(57.0, 3.0):.0f}  (production_aMax = 1300)")
