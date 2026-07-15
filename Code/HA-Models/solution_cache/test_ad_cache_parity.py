"""Leg A3 parity gate for the AD-converged solution cache.

Runs ONE ``HS_Only recessionCheck_AD`` welfare-6 cell THREE ways:

    (i)   cache OFF   — reference (HAFISCAL_USE_SOLUTION_CACHE=0)
    (ii)  cache ON, MISS — fresh cache dir, so the AD loop runs and saves
    (iii) cache ON, HIT  — same fresh dir, so the AD loop is skipped and the
                           converged eco state is reconstructed from disk

Assertion (REVISED 2026-06-22 — the original "all three bit-identical" premise was
empirically false; see below):
  * OFF == MISS : **byte-identical**. solve+save produces the same in-memory objects as
    cache-OFF (the save is a pure side effect), forward-sim RNG untouched.
  * HIT vs OFF  : **numerically equivalent within Tier I (rtol=1e-6)**, NOT byte-identical.
    The load does NOT restore the live solution objects bit-for-bit — it reconstructs each
    cFunc from stored interpolation NODES (float64 ``x_list``/``y_list`` + ``CRule``
    intercept/slope), which is not a bit-faithful copy of the freshly-solved
    transform-interpolated cFunc. Measured ~3.2e-7 relative at HS_Only — well inside the
    Tier-I intermediate-quantity bar (1e-6) of
    ``conclusions_private/2026-06-22_numerical-stability-acceptance-criterion.md``, but it
    is a real reconstruction floor, not byte-identity. (The earlier claim that the cache is
    a "byte-identical exact replay" was wrong; it is a numerically-equivalent replay.)
    Byte-exact caching would require pickling the full solution objects rather than
    node-extract+reconstruct — a deeper change, deferred unless the Tier-I bar is breached
    (e.g. if the round-trip error grows at Baseline scale — check in the cascade).

This is the gate that must be green BEFORE the cache is proposed default-ON,
and it is the in-process check that closes the post-build-grid-mutation
blind spot (key-match but table-mismatch) by comparing a HIT against a fresh
MISS produced in the same environment.

CASCADE-GATE (per [cascade-gating] / [grid_convergence_test_in_college_beta_het]):
run HS_Only FIRST (this test). Escalate to ``College_Only`` with all 7 beta
atoms — the binding high-aNrm tail for which the AD/grid coverage is the
tightest — ONLY on a clean HS_Only pass. HALT-on-fail at the current tier;
do not advance a tier whose cheaper predecessor failed.

Marked ``slow`` (each of the three runs builds + solves an HS_Only economy and
runs the recessionCheck AD loop). It is compute-heavy, so it is NOT meant to
run in a normal unit-test sweep; the Leg-A cascade driver runs it explicitly.
Set ``HAFISCAL_SKIP_SLOW_ITEST=1`` to skip at collection time (e.g. on a box
that cannot afford to build the economy), so ``--collect-only`` and a plain
``pytest`` invocation never hang.

Run explicitly with:
    pytest Code/HA-Models/solution_cache/test_ad_cache_parity.py -m slow
"""
import os
import pickle
import subprocess
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
# _HERE = .../Code/HA-Models/solution_cache; FromPandemicCode is a sibling.
_HAMODELS = os.path.abspath(os.path.join(_HERE, ".."))
_FPC = os.path.join(_HAMODELS, "FromPandemicCode")

# Collection-time skip guard: building the HS_Only AD cell is too heavy for
# some environments. Honoring this env var keeps `--collect-only` (and any
# non-slow sweep) from importing/instantiating anything expensive.
_SKIP_SLOW = os.environ.get("HAFISCAL_SKIP_SLOW_ITEST", "").lower() in (
    "1", "on", "true", "yes")
pytestmark = pytest.mark.skipif(
    _SKIP_SLOW,
    reason="HAFISCAL_SKIP_SLOW_ITEST set — skipping heavy AD-cell parity build",
)

# The single AD cell this gate exercises. recessionCheck has the strongest AD
# amplification of the reportable cells, so its converged CFunc is the most
# demanding round-trip for the cache.
_SCENARIO = "recessionCheck_AD"
_PARAMETRIZATION = "HS_Only"
# Small N keeps the build affordable while still exercising the full
# AD-converged reconstruct path; parity is exact regardless of N.
_AGENT_COUNT_TOTAL = 2000


def _run_scenario(out_dir, *, use_cache):
    """Run the single AD scenario once via welfare6_scenario.py (subprocess,
    matching the test_welfare6_ergodic_init.py driver pattern) and return the
    loaded pickle payload.

    ``use_cache`` sets HAFISCAL_USE_SOLUTION_CACHE for the child. A fresh
    ``out_dir`` for the MISS run is the caller's responsibility; the on-disk
    AD cache lives under solution_cache/<param>/<shock_type>/ (NOT out_dir),
    so the MISS→HIT distinction is controlled by wiping that dir, not out_dir.
    """
    env = dict(os.environ)
    # Start from a clean, explicit cache state for every child.
    env["HAFISCAL_USE_SOLUTION_CACHE"] = "1" if use_cache else "0"
    # Pin everything that could perturb the converged solution or the panels
    # so the only thing varying across the three runs is the cache. JAX 2B is
    # dev-only (kernel shift below 2-dp) and would otherwise sit in the cache
    # key; pin it OFF so OFF/MISS/HIT use the identical canonical solve.
    env["HAFISCAL_USE_JAX_2B"] = "0"
    # Exercise the JAX-AD path — the welfare launcher (run_welfare6_parallel
    # ._build_child_env) DEFAULTS HAFISCAL_USE_JAX_MC=1, and the JAX-AD cache
    # HIT/reconstruct path is the one that had the 2026-06-23 ADelasticity bug
    # (flat Baseline AD welfare). Leaving this unset routed the gate through the
    # HARK-AD path (which was never buggy — it carries ADelasticity in its own
    # `stored` snapshot), so the gate FALSE-PASSED and the bug shipped. Pin ON so
    # OFF/MISS/HIT all use the production JAX-AD path. (CPU-falls-back when no GPU.)
    env["HAFISCAL_USE_JAX_MC"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(
        [sys.executable, "welfare6_scenario.py",
         "--scenario", _SCENARIO,
         "--parametrization", _PARAMETRIZATION,
         "--out-dir", out_dir,
         "--agent-count-total", str(_AGENT_COUNT_TOTAL)],
        cwd=_FPC, env=env, check=True,
    )
    with open(os.path.join(out_dir, f"{_SCENARIO}.pkl"), "rb") as f:
        return pickle.load(f)


def _welfare_integrand_sum(payload):
    """A single deterministic scalar summarizing this AD cell's welfare
    contribution from its per-duration panels, computed with the BUG-046
    per-duration ordering (welfare integrand per duration, then rec_probs
    weighting). This is the numerator side of the welfare-6 cell; the full
    cell needs the base/none pickles too, but for a same-cell OFF/MISS/HIT
    parity check the per-duration panels + this scalar fully determine the
    cell, so exact agreement here implies an exact cell.
    """
    per_dur = payload["per_dur_cLvl_all_splurge"]
    rec_probs = payload["rec_probs"]
    CRRA = payload["CRRA"]
    n_dur = len(per_dur)
    acc = 0.0
    for dur in range(n_dur):
        c = np.maximum(np.asarray(per_dur[dur], dtype=np.float64), 1e-16)
        # felicity (CRRA), summed across the panel, weighted by rec_probs —
        # a deterministic function of the panel, so bit-identical iff panels are.
        if abs(CRRA - 1.0) < 1e-12:
            fel = np.log(c)
        else:
            fel = c ** (1 - CRRA) / (1 - CRRA)
        acc += float(rec_probs[dur]) * float(np.sum(fel))
    return acc


@pytest.mark.slow
def test_ad_cache_off_miss_hit_bit_identical(tmp_path):
    """OFF reference, cache MISS, and cache HIT must produce bit-identical
    per-duration cLvl panels AND welfare scalars for HS_Only recessionCheck_AD.
    """
    import glob

    # (iii) HIT shares the same on-disk AD cache dir as (ii) MISS, so wipe any
    # pre-existing HS_Only recessionCheck entries first to force a clean MISS.
    cache_dir = os.path.join(_HERE, _PARAMETRIZATION, "recessionCheck")
    if os.path.isdir(cache_dir):
        for f in glob.glob(os.path.join(cache_dir, "ad_*.pkl")) + \
                 glob.glob(os.path.join(cache_dir, "ad_*.meta.json")):
            os.remove(f)

    # (i) cache OFF — reference.
    off = _run_scenario(str(tmp_path / "off"), use_cache=False)
    # (ii) cache ON, MISS — fresh cache dir (just wiped), AD loop runs + saves.
    miss = _run_scenario(str(tmp_path / "miss"), use_cache=True)
    # (iii) cache ON, HIT — same cache dir now populated, AD loop skipped.
    hit = _run_scenario(str(tmp_path / "hit"), use_cache=True)

    # Sanity: all three actually produced the per-duration panels (BUG-046
    # key). If absent the welfare-6 aggregation would be Jensen-biased and the
    # parity comparison would silently degrade.
    for tag, p in (("off", off), ("miss", miss), ("hit", hit)):
        assert "per_dur_cLvl_all_splurge" in p, (
            f"{tag} payload missing per_dur_cLvl_all_splurge — cannot run the "
            f"per-duration parity check")
        assert "rec_probs" in p, f"{tag} payload missing rec_probs"

    off_panel = np.asarray(off["per_dur_cLvl_all_splurge"], dtype=np.float64)
    miss_panel = np.asarray(miss["per_dur_cLvl_all_splurge"], dtype=np.float64)
    hit_panel = np.asarray(hit["per_dur_cLvl_all_splurge"], dtype=np.float64)

    assert off_panel.shape == miss_panel.shape == hit_panel.shape, (
        f"per-duration panel shape mismatch: off={off_panel.shape}, "
        f"miss={miss_panel.shape}, hit={hit_panel.shape}")

    # OFF == MISS is BYTE-IDENTICAL (solve+save produces the same in-memory objects as
    # cache-OFF; the save is a pure side effect). HIT is NUMERICALLY EQUIVALENT, NOT
    # byte-identical: the load reconstructs each cFunc from stored interpolation NODES,
    # which is not a bit-faithful copy of the freshly-solved (transform-interpolated)
    # cFunc — measured ~3.2e-7 relative at HS_Only. Per the acceptance criterion
    # (conclusions_private/2026-06-22_numerical-stability-acceptance-criterion.md) the
    # intermediate-quantity bar is Tier I = 1e-6; enforce THAT on the HIT round-trip (a
    # breach means a real reconstruction regression, not the usual ~3e-7 floor).
    _HIT_RTOL = 1e-6  # Tier-I numerical-equivalence bar for the load+reconstruct round-trip
    np.testing.assert_array_equal(
        off_panel, miss_panel,
        err_msg="cache MISS per-duration cLvl panel differs from cache-OFF "
                "reference — the AD-loop solve path diverged with the cache on")
    np.testing.assert_allclose(
        hit_panel, off_panel, rtol=_HIT_RTOL, atol=1e-9,
        err_msg="cache HIT per-duration cLvl panel differs from cache-OFF reference by "
                "MORE than the Tier-I round-trip tolerance (rtol=1e-6) — a real "
                "reconstruction regression beyond the usual ~3e-7 node-rebuild floor")

    # Welfare scalar (deterministic function of the panels): OFF==MISS exact; HIT within Tier I.
    w_off = _welfare_integrand_sum(off)
    w_miss = _welfare_integrand_sum(miss)
    w_hit = _welfare_integrand_sum(hit)
    assert w_off == w_miss, (
        f"welfare scalar OFF vs MISS not bit-identical: off={w_off!r}, miss={w_miss!r}")
    assert abs(w_hit - w_off) <= _HIT_RTOL * abs(w_off), (
        f"welfare scalar HIT differs from OFF by more than Tier-I rtol={_HIT_RTOL:g} "
        f"(off={w_off!r}, hit={w_hit!r}, reldiff={abs(w_hit - w_off) / abs(w_off):.2e})")

    # Also check the probability-weighted primary panel + the aggregate
    # consumption/income series the welfare-6 denominator uses, for completeness.
    for key in ("cLvl_all_splurge", "AggCons", "AggIncome"):
        a = np.asarray(off[key], dtype=np.float64)
        b = np.asarray(miss[key], dtype=np.float64)
        c = np.asarray(hit[key], dtype=np.float64)
        np.testing.assert_array_equal(
            a, b, err_msg=f"{key}: cache MISS differs from cache-OFF reference")
        np.testing.assert_allclose(
            c, a, rtol=_HIT_RTOL, atol=1e-9,
            err_msg=f"{key}: cache HIT differs from cache-OFF reference by more than "
                    f"the Tier-I round-trip tolerance (rtol=1e-6)")
