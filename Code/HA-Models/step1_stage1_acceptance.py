"""Stage-1 acceptance for the Step-1 continuation protocol (D4, owner-ruled default
2026-08-23: "implement this as default").

The continuation's stage 1 (cold multistart of the restricted splurge=0 problem)
must decide whether its starts located ONE basin. The original criterion —
parameter-space unanimity, relative (max-min)/mean <= 1e-4 on beta AND nabla — is
correct at the fast grid (measured spread there: 1e-8 class) but miscalibrated at
`SOLVE_GRID_PROFILE=full`: the full-grid splurge=0 valley is FLAT at ~1e-5-relative
f, so COBYQA stop-points scatter ~1.5e-3 in nabla while being numerically the same
optimum (measured 2026-08-22/23, both knots settings, reproduced independently on
macOS-ARM to three digits of spread). Parameter unanimity then trips a fallback
battery that spends ~2h re-deriving what stage 1 already knew.

The corrected criterion asks the question that actually matters — "did the starts
find the same OBJECTIVE value?" — because a flat valley makes parameter spread
meaningless while f-spread stays tiny:

    accept  iff  param-unanimity (<= UNANIMITY_RTOL)  OR  f-tie (<= FTIE_RTOL)
    continuation point = the min-f start's (beta, nabla)   [unchanged either way]

FTIE_RTOL = 1e-4 relative, derived from the measured separation of the two classes
it must distinguish (all at the full grid, 2026-08-22/23 record in
plans_local/20260822-1400h_full-profile-rerun-preregistration.md):
  - one-basin stop-scatter (must ACCEPT): widest measured f-range/min = 8.1e-6
    (knots0-full stage 1; knots8-full was 1.6e-7; fast grid 1e-8 class);
  - distinct attractors / straggler stops (must REJECT -> fallback battery):
    smallest measured f-gap = 6.1e-4 relative (the 0.3011 attractor vs the SoR
    basin; straggler stops sit at the same 6e-4-class margin).
1e-4 is the log-midpoint of [8.1e-6, 6.1e-4] rounded to one digit: 12x above the
widest tie, 6x below the smallest genuine split. Validation for free: replayed on
the 2026-08-23 knots0-full record, this criterion accepts (8.1e-6) and selects
start 4 -- whose endpoint IS the installed Splurge-0 SoR bitwise.
"""
from __future__ import annotations

UNANIMITY_RTOL = 1e-4   # the original parameter-space criterion (kept as the OR-arm)
FTIE_RTOL = 1e-4        # relative f-range; derivation in the module docstring


def stage1_accept(results):
    """Decide stage-1 acceptance from [(fval, start_index, {'beta','nabla',...}), ...].

    Returns (accepted: bool, why: str, spread_param: float, spread_f: float).
    Only error-free entries are passed in; fewer than 2 entries never accept
    (no cross-start evidence).
    """
    if len(results) < 2:
        return False, "insufficient starts", float("inf"), float("inf")
    bs = [r[2]["beta"] for r in results]
    ns = [r[2]["nabla"] for r in results]
    fs = [r[0] for r in results]
    spread_param = max(
        (max(bs) - min(bs)) / max(abs(sum(bs) / len(bs)), 1e-12),
        (max(ns) - min(ns)) / max(abs(sum(ns) / len(ns)), 1e-12),
    )
    spread_f = (max(fs) - min(fs)) / max(abs(min(fs)), 1e-300)
    if spread_param <= UNANIMITY_RTOL:
        return True, "parameter unanimity", spread_param, spread_f
    if spread_f <= FTIE_RTOL:
        return True, "f-tie (flat valley)", spread_param, spread_f
    return False, "no unanimity and no f-tie", spread_param, spread_f
