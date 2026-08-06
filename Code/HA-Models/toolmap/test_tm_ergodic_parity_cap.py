#!/usr/bin/env python
"""OPT-IN parity gate: TM-ergodic vs TM-SEEDED MC at the College GIC-cap atoms.

WHY THIS GATE EXISTS (owner-ordered 2026-07-24)
-----------------------------------------------
The Phase-A parity gate (`test_tm_ergodic_parity.py`) validates TM-vs-MC
aNrm-moment agreement at HS_Only — a single fast-mixing atom (β=0.9356, not at
the cap), cold-ish short burn-in. The speed-defaults deep dive
(`conclusions_private/2026-07-24_speed_deepdive_p0p1.md` §2) showed that the
near-critical GIC-cap atoms are qualitatively different: cold MC needs
τ≈500–2000 quarters to reach the ergodic there, and the cap atom's wealth tail
is heavy (measured local exponent ≈2.17, asymptotic root ≈1.1 — 2026-07-25),
making MC sample MEANS stable-law noisy at practical panel sizes.
Production never runs cold — every production MC is warm-started FROM the TM-a
ergodic (BUG-052 default; `welfare6_scenario.py` / `Simulate.py` via
`tm_methods.initialize_mc_from_tm_ergodic`). THIS gate validates that
warm-start contract at the hardest atoms in the model: seed from the ergodic,
free-run a production-scale window, and require the panel to still agree with
the ergodic.

OPT-IN, NOT DEFAULT (owner ruling 2026-07-24: "as an opt-in not as the default
way to do things"): skipped unless HAFISCAL_PARITY_CAP=1. It solves the full
Baseline economy (21 types incl. the patient atoms) — ~2–4 min wall.

    HAFISCAL_PARITY_CAP=1 VIRTUAL_ENV=.venv-linux-x86_64 uv run --no-sync \
        --active python -m pytest \
        Code/HA-Models/toolmap/test_tm_ergodic_parity_cap.py -v -s

WHAT IS COMPARED (cap-atom pool = the two effective College cap atoms; the
2026-07-24 Step-2 decomposition showed College atom 5's raw β sits 7.7e-8
below the cap, so both top atoms iterate/behave as cap atoms)
----------------------------------------------------------------------------
  TM side : per-type ergodic asset marginal π(a) (P-measure,
            dist_aGrid_count=HAFISCAL_TM_MCOUNT default 200 (the flag keeps its M-era spelling by owner ruling); the distribution-grid top
            `dist_aGrid_max` DERIVED by the default method —
            `adaptive_grid_tm.production_dist_aGrid_max()`, = 2900 under the
            current default numerics; an explicit HAFISCAL_TM_AMAX set BEFORE
            this module is imported wins — owner ruling 2026-07-25: no
            hardwired grid top) → median, p90, mean.
  MC side : the PRODUCTION warm-start path `initialize_mc_from_tm_ergodic`
            (internal warmup, default 24) then a W=HAFISCAL_PARITY_CAP_WINDOW
            (default 40) quarter base-scenario free-run at constant aggregate
            factors → the same statistics from the end-of-window panel.
  Gated   : median(aNrm) and p90(aNrm) of the cap-atom pool — quantiles are
            tail-robust, so they are the honest parity comparands at a
            heavy-tailed atom.
  Reported only (NOT gated): mean(aNrm) — the cap atom's wealth tail is
            heavy (measured local exponent ≈2.17 over the populated range,
            2026-07-25; asymptotic deterministic-growth root ≈1.1), so at
            ~540 agents/atom the sample mean is stable-law-noisy and a mean
            band would gate sampling luck, not parity.

TOLERANCE RATIONALE (dev-measured 2026-07-25 at the DERIVED grid
dist_aGrid_max=2900; run `__main__` to reproduce)
--------------------------------------------------------------------------
One Baseline build+solve, then the MC leg at 4 seed offsets (W=40) plus a
window ladder at seed 0. TM cap-pool: median=24.00, p90=91.59, mean=45.17.
  * W=0 (straight after the production warmup): median −0.25%, p90 +3.04%,
    mean −2.13% — the seeding path itself lands the panel on the ergodic
    within ~±3% even at the cap atoms.
  * W=40 across seeds {0..3}: median Δ ∈ [−4.72%, +2.55%], p90 Δ ∈ [−1.11%,
    +4.35%], mean Δ ∈ [−5.13%, +1.59%] — seed-to-seed sign flips, i.e.
    sampling noise at n=1084, not systematic drift.
Bands = ~2x the worst quantile |Δ| observed at the production window:
  * median : |Δ| < 0.10
  * p90    : |Δ| < 0.10
Documented caveat: at W=80 (beyond production windows) seed 0 showed p90
−6.2% / mean −11.2% — possible onset of slow MC-vs-TM tail relaxation; a
longer-window drift study belongs to the Step-1 TM-a plan's gate set, not
this regression gate, which pins the PRODUCTION window W=40.

DETERMINISM: TM side no-RNG; the pytest gate runs seed offset 0 with fixed
per-type seeds (build_economy), so it is exactly reproducible (measured
gate-point deltas at the derived grid: median +2.55%, p90 +4.35%); the
seed-offset spread above is a dev-mode measurement, not part of the pytest
gate. The TM build also exercises `assert_mortality_inclusive_ergodicity`
(tm_methods) on the real Baseline economy — the mortality-inclusive
ergodicity HALT guard (owner order 2026-07-25) — as a silent integration
check.
"""
import os

import numpy as np
import pytest

OPT_IN = os.environ.get("HAFISCAL_PARITY_CAP", "0") == "1"
pytestmark = pytest.mark.skipif(
    not OPT_IN,
    reason="opt-in cap-atom parity gate: set HAFISCAL_PARITY_CAP=1 "
           "(full Baseline solve, ~2-4 min)")

def _ensure_dist_aGrid_max():
    """Resolve the TM distribution-grid top `dist_aGrid_max` by THE DEFAULT
    METHOD, not a frozen number (owner ruling 2026-07-25: "replace a hard-wired
    choice like aMax=1300 with whatever is now the default method of choosing
    aMax" — quoted verbatim; the object has since been renamed dist_aGrid_max).

    Precedence: an explicit HAFISCAL_TM_AMAX env wins; otherwise DERIVE
    `adaptive_grid_tm.production_dist_aGrid_max()` — the (1−1e-4) cap-atom
    ergodic quantile under the ACTIVE tail numerics (~9 s, opt-in gate only) —
    and publish it to the env for the TM builder.

    Why derive: the frozen canonical 1300 was measured 2026-06-09 under the
    as-shipped NAIVE-LINEAR tail (the derivation reproduces it exactly there:
    q=1224→1300) and went stale through two tail epochs — exp (BUG-062 fix)
    gives q=2207→2300, today's powerlaw measured-Q + K·h̄ default gives
    q=2893→2900. At 1300 under the default numerics the grid truncates
    5.6e-4 of cap-atom mass carrying 2.9% of cap-atom wealth. (The
    production-side HAFISCAL_TM_AMAX=1300 setdefault is a flagged OWNER
    decision — this gate only fixes itself.)
    """
    if _TM_AMAX_USER is not None:
        return float(_TM_AMAX_USER)
    # NOTE: do NOT consult os.environ here — by TM-build time EstimParameters'
    # canonical setdefault ('1300', currently STALE vs the derivation; see the
    # HAFISCAL_TM_AMAX registry entry) has already fired inside the bench
    # import chain. Only the MODULE-IMPORT-TIME snapshot (_TM_AMAX_USER, taken
    # before any heavy import) counts as an explicit user override.
    import sys as _sys
    _ha = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _ha not in _sys.path:
        _sys.path.insert(0, _ha)
    from adaptive_grid_tm import production_dist_aGrid_max
    dist_aGrid_max, _q, _beta_top = production_dist_aGrid_max(verbose=False)
    # Overwrite (not setdefault): the canonical value may already be in the env
    # via EstimParameters and is exactly what we must NOT inherit here.
    os.environ["HAFISCAL_TM_AMAX"] = (str(int(dist_aGrid_max))
                                      if dist_aGrid_max == int(dist_aGrid_max)
                                      else str(dist_aGrid_max))
    return float(dist_aGrid_max)

W_WINDOW = int(os.environ.get("HAFISCAL_PARITY_CAP_WINDOW", "40"))
MEDIAN_REL_TOL = 0.10
P90_REL_TOL = 0.10

# Module-import-time snapshot of an EXPLICIT user dist_aGrid_max override —
# must be read before any heavy import (EstimParameters setdefaults
# HAFISCAL_TM_AMAX later in the bench import chain, and that canonical value
# must not masquerade as a user choice; see _ensure_dist_aGrid_max).
_TM_AMAX_USER = os.environ.get("HAFISCAL_TM_AMAX")


def _quantile_from_dist(grid, pa, q):
    """Quantile of a discrete distribution (pa over grid) by cum-mass interpolation."""
    c = np.cumsum(pa)
    c = c / c[-1]
    return float(np.interp(q, c, grid))


def _cap_agent_indices(econ):
    """Indices of the cap-atom pool: every agent within 1e-3 of the max DiscFac."""
    dfs = np.array([float(a.DiscFac) for a in econ.agents])
    return [i for i in range(len(dfs)) if dfs.max() - dfs[i] < 1e-3]


def _build_solved_economy():
    """Build + solve the Baseline economy once (seed-independent)."""
    import bench_toolmap as bench  # heavy: performs its module-load env setup

    econ, base_dict = bench.build_economy("Baseline")
    bench.tool_solve({"econ": econ, "base_dict": base_dict})
    cap_idx = _cap_agent_indices(econ)
    assert len(cap_idx) >= 1, "no cap-atom agents found in the Baseline economy"
    return econ, cap_idx


def _tm_cap_stats(econ, cap_idx):
    """P-measure TM ergodic on the canonical grid + cap-pool statistics.
    Returns (bd, tm_stats); bd is reused to seed the MC leg."""
    from tm_methods import compute_baseline_tm_data

    dist_aGrid_max = _ensure_dist_aGrid_max()
    print(f"[cap-parity] TM dist-grid top (dist_aGrid_max) resolved by the default method: "
          f"{dist_aGrid_max:g}", flush=True)
    for ag in econ.agents:
        ag.tm_a_indexed = True
    dist_aGrid_count = int(os.environ.get("HAFISCAL_TM_MCOUNT", "200"))
    bd = compute_baseline_tm_data(
        econ, dist_aGrid_count=dist_aGrid_count, neutral_measure=False, verbose=False)

    pas = []
    grid0 = None
    for i in cap_idx:
        erg = np.asarray(bd[i]["ergodic"], dtype=np.float64)
        grid = np.asarray(bd[i]["dist_aGrid"], dtype=np.float64)
        A = len(grid)
        pa = erg.reshape(len(erg) // A, A).sum(axis=0)
        pa = pa / pa.sum()
        grid0 = grid if grid0 is None else grid0
        pas.append(pa)
    # The cap atoms share one dist_aGrid; pool by averaging π(a) with equal
    # weights (they are equal-AgentCount atoms of one edu group).
    pa_pool = np.mean(np.vstack(pas), axis=0)
    tm_stats = dict(
        median=_quantile_from_dist(grid0, pa_pool, 0.5),
        p90=_quantile_from_dist(grid0, pa_pool, 0.9),
        mean=float(np.sum(pa_pool * grid0)),
    )
    return bd, tm_stats


def _mc_cap_leg(econ, bd, cap_idx, seed_bump=0, window=W_WINDOW):
    """The MC leg: production warm-start from the TM ergodic (internal warmup),
    then a W-quarter base-scenario free-run; cap-pool panel statistics."""
    from tm_methods import initialize_mc_from_tm_ergodic

    econ.reset()
    for ag in econ.agents:
        if seed_bump:
            ag.seed = ag.seed + 100003 * seed_bump
        ag.T_sim = max(int(getattr(ag, "T_sim", 0) or 0), 24 + window + 2)
        ag.initialize_sim()
        ag.AggDemandFac = 1.0
        ag.RfreeNow = 1.0
        ag.CaggNow = 1.0
        ag.tm_a_indexed = True

    initialize_mc_from_tm_ergodic(econ.agents, bd)
    for ag in econ.agents:
        ag.simulate(window)

    panel = np.concatenate(
        [np.asarray(econ.agents[i].state_now["aNrm"]).ravel() for i in cap_idx])
    return dict(
        median=float(np.median(panel)),
        p90=float(np.percentile(panel, 90)),
        mean=float(np.mean(panel)),
        n=int(panel.size),
    )


def _run_cap_parity(seed_bump=0, window=W_WINDOW):
    """One-shot build+solve, TM stats, MC leg (used by the pytest gate)."""
    econ, cap_idx = _build_solved_economy()
    bd, tm_stats = _tm_cap_stats(econ, cap_idx)
    mc_stats = _mc_cap_leg(econ, bd, cap_idx, seed_bump=seed_bump, window=window)
    return dict(tm=tm_stats, mc=mc_stats, cap_idx=cap_idx,
                cap_betas=[float(econ.agents[i].DiscFac) for i in cap_idx])


def _rel(mc, tm):
    return (mc - tm) / tm


def test_cap_atom_warmstart_parity():
    """Seed MC from the TM ergodic at the College cap atoms, free-run W
    quarters, and require the panel's tail-robust quantiles to stay within the
    documented bands of the ergodic's."""
    r = _run_cap_parity()
    tm, mc = r["tm"], r["mc"]
    med_rel = _rel(mc["median"], tm["median"])
    p90_rel = _rel(mc["p90"], tm["p90"])

    print(
        f"\n[cap-parity] cap atoms {r['cap_idx']} betas={r['cap_betas']} "
        f"n={mc['n']} window={W_WINDOW}\n"
        f"  median: TM={tm['median']:.4f}  MC={mc['median']:.4f}  "
        f"Δ={100*med_rel:+.2f}%  (band {MEDIAN_REL_TOL:.0%})\n"
        f"  p90   : TM={tm['p90']:.4f}  MC={mc['p90']:.4f}  "
        f"Δ={100*p90_rel:+.2f}%  (band {P90_REL_TOL:.0%})\n"
        f"  mean  : TM={tm['mean']:.4f}  MC={mc['mean']:.4f}  "
        f"Δ={100*_rel(mc['mean'], tm['mean']):+.2f}%  "
        f"(REPORTED ONLY — heavy-tailed atom: local tail exponent ~2.17, asymptotic root ~1.1; sample mean stable-law-noisy at this n, not gated)",
        flush=True)

    assert abs(med_rel) < MEDIAN_REL_TOL, (
        f"cap-atom MEDIAN drift {med_rel:+.4%} exceeds band {MEDIAN_REL_TOL:.0%} "
        f"(TM={tm['median']:.5f} MC={mc['median']:.5f})")
    assert abs(p90_rel) < P90_REL_TOL, (
        f"cap-atom P90 drift {p90_rel:+.4%} exceeds band {P90_REL_TOL:.0%} "
        f"(TM={tm['p90']:.5f} MC={mc['p90']:.5f})")


if __name__ == "__main__":
    # Dev mode: one build+solve, then measure the seed-offset spread (and a
    # window ladder at seed 0) that justifies the bands.
    os.environ["HAFISCAL_PARITY_CAP"] = "1"
    econ, cap_idx = _build_solved_economy()
    bd, tm = _tm_cap_stats(econ, cap_idx)
    print(f"TM cap-pool: median={tm['median']:.4f} p90={tm['p90']:.4f} "
          f"mean={tm['mean']:.4f}", flush=True)
    for k in (0, 1, 2, 3):
        mc = _mc_cap_leg(econ, bd, cap_idx, seed_bump=k)
        print(f"seed+{k} W={W_WINDOW}: "
              f"median Δ={100*_rel(mc['median'], tm['median']):+.2f}%  "
              f"p90 Δ={100*_rel(mc['p90'], tm['p90']):+.2f}%  "
              f"mean Δ={100*_rel(mc['mean'], tm['mean']):+.2f}%  (n={mc['n']})",
              flush=True)
    for w in (0, 12, 80):
        mc = _mc_cap_leg(econ, bd, cap_idx, seed_bump=0, window=w)
        print(f"seed+0 W={w}: "
              f"median Δ={100*_rel(mc['median'], tm['median']):+.2f}%  "
              f"p90 Δ={100*_rel(mc['p90'], tm['p90']):+.2f}%  "
              f"mean Δ={100*_rel(mc['mean'], tm['mean']):+.2f}%",
              flush=True)
    print("dev sweep done — set bands ~2x the worst |Δ| observed at the "
          "production window.", flush=True)
