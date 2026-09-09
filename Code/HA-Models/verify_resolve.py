#!/usr/bin/env python3
"""verify_resolve.py — the ``--complete`` re-solve-and-compare reuse gate.

Thread-2 component 3 of the reuse-fidelity verification taxonomy. The pipeline can REUSE a
solution instead of computing it — the AD solution cache (``HAFISCAL_USE_SOLUTION_CACHE``)
on a HIT skips the whole AD loop; the cross-phase belief seed (``HAFISCAL_AD_BELIEF_SEED``)
warm-starts it. At the default VERIFY level ``numeric`` we TRUST the reuse (the cache key +
fingerprint are the guard). Under ``--complete`` this gate adds the AUTHORITATIVE check:
re-solve the in-scope cells FROM SCRATCH (cache OFF) and compare the reused result to the
fresh solve — a genuine mismatch means the reuse was wrong, and it FAILS LOUD.

Why the full re-solve (not the cheap one-step probe): EGM is a contraction, so a single
backward step from a slightly-wrong seed closes only a fraction of the gap and the residual
falls under tolerance while the seed is the wrong-regime solution (the sibling cache plan's
adversarial finding). A full re-solve cannot be fooled — it IS the ground truth, just
expensive. (Component 4 is the cheaper, subtler de-biased one-step alternative.)

Mechanism (kept decoupled from the production solve / eco state): the run_welfare6_parallel
hook re-runs the in-scope scenarios cache-OFF (via ``launch_scenarios(ad_cache=False)`` —
the existing ``--no-ad-cache`` path) at the SAME ``seed_offset`` as production, then this
module compares each fresh ``<scenario>.pkl`` to the production one. Same seed ⇒ the forward
sim is deterministic, so cache-on vs cache-off differ ONLY by the reuse (and the cache's
~3e-7 reconstruction loss, which Tier-I absorbs). This module owns scope / tolerance /
comparison; the seed re-launch stays in run_welfare6_parallel (reusing launch_scenarios).

Failure semantics: a genuine MISMATCH fails loud (the reused result is suspect). A verify-
MACHINERY error (missing pkl, unreadable file, a re-run crash) DEGRADES with abundant
diagnostics — it does not fail the production result, which already stands.

Env knob: ``HAFISCAL_VERIFY_RESOLVE_SCOPE`` = all (default) | sample | canary | none, or an
explicit comma-separated scenario list. (Owner default 2026-06-22: all.)

Spec:   plans/20260622_reuse-fidelity-verification-flag-taxonomy.md
Build:  plans/20260622_thread2-flag-taxonomy-build-execution-plan.md (component 3)
Reader: verify_level.py (the VERIFY axis)
Gates:  conclusions_private/2026-06-22_reuse-gate-A-vs-B-and-debias-derivation.md
"""
from __future__ import annotations

import os
import pickle
import sys

import numpy as np

import verify_level

SCOPE_ENV = "HAFISCAL_VERIFY_RESOLVE_SCOPE"

# The 12 welfare scenarios (mirror run_welfare6_parallel.ALL_SCENARIOS). The four *_AD
# scenarios are the expensive re-solves (a full AD loop each).
_ALL_SCENARIOS = (
    "base", "Check", "UI", "TaxCut",
    "recession", "recessionUI", "recessionCheck", "recessionTaxCut",
    "recession_AD", "recessionUI_AD", "recessionCheck_AD", "recessionTaxCut_AD",
)
# Representative sample: one plain solve + one AD solve (covers both solve code paths).
_SAMPLE = ("base", "recessionCheck_AD")
_CANARY = ("base",)

_TIER_I = 1e-6   # numerically-equivalent INTERMEDIATE standard (~6 sig figs)
_FLOOR = 1e-12   # relative-diff denominator floor

# Non-result RUN METADATA stamped into each scenario pickle that legitimately varies
# run-to-run and must NOT count as a mismatch. `runtime_s` = wall-clock duration of the
# solve+sim (welfare6_scenario.py:1075). Every actual model-output array is deterministic
# at a fixed seed (verified: two cache-off same-seed base solves agree bit-for-bit), so this
# is the only numeric field to exclude. Add to this set if other timing/provenance numeric
# fields are introduced; keep result arrays IN.
_EXCLUDE_KEYS = frozenset({"runtime_s"})


def should_run():
    """True iff the VERIFY axis is at >= complete (so the gate should run)."""
    return verify_level.verify_at_least(verify_level.COMPLETE)


def scope(all_scenarios=None):
    """Tuple of scenarios to re-solve-and-compare.

    From ``HAFISCAL_VERIFY_RESOLVE_SCOPE``: ``all`` (default) | ``sample`` | ``canary`` |
    ``none``, or an explicit comma-separated scenario list. An unrecognized keyword warns
    and falls back to ``all``; an explicit list silently drops unknown names (with a warn)."""
    allsc = tuple(all_scenarios) if all_scenarios is not None else _ALL_SCENARIOS
    raw = os.environ.get(SCOPE_ENV, "").strip()
    if not raw:
        return allsc
    low = raw.lower()
    if low == "all":
        return allsc
    if low == "none":
        return ()
    if low == "sample":
        return tuple(s for s in _SAMPLE if s in allsc)
    if low == "canary":
        return tuple(s for s in _CANARY if s in allsc)
    if "," in raw or raw in allsc:        # explicit scenario list
        sel = [s.strip() for s in raw.split(",") if s.strip()]
        unknown = [s for s in sel if s not in allsc]
        if unknown:
            print(f"[verify_resolve] WARNING: {SCOPE_ENV} names unknown scenario(s) "
                  f"{unknown}; ignoring.", file=sys.stderr)
        return tuple(s for s in sel if s in allsc)
    print(f"[verify_resolve] WARNING: {SCOPE_ENV}={raw!r} unrecognized "
          f"(expected all|sample|canary|none or a scenario list); using 'all'.",
          file=sys.stderr)
    return allsc


def tolerance():
    """Return ``(rtol, label)`` for the result comparison.

    'complete' → Tier-I (1e-6, ~6 sig figs), the numerically-equivalent INTERMEDIATE standard.
    'byte' → 0.0 (BYTE-EXACT): component 5 forces the ~3e-7 lossy reuse OFF under
    ``--byte-identical`` (solution_cache.byte_exact_forces_fresh_solve), so BOTH the production
    run and this re-solve are fresh cache-off same-seed solves — which are bit-identical
    (verified: two such base solves agree 0.0 on every result array) — making an exact
    comparison valid. (The deferred byte-exact full-object cache would re-enable fast reuse
    while keeping this exact.)"""
    if verify_level.get_verify_level() == verify_level.BYTE:
        return 0.0, "byte-exact (rtol=0; --byte-identical forces reuse OFF → fresh re-solve is bit-identical)"
    return _TIER_I, "Tier-I (1e-6)"


def _max_reldiff(a, b):
    """nan/inf-aware max relative difference between two numeric arrays; inf if shapes or
    NaN patterns disagree (a definite mismatch)."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        return float("inf")
    na, nb = np.isnan(a), np.isnan(b)
    if not np.array_equal(na, nb):
        return float("inf")              # NaN pattern differs -> mismatch
    fin = ~na
    if not fin.any():
        return 0.0                       # all-NaN, same pattern -> equal
    av, bv = a[fin], b[fin]
    rel = np.abs(av - bv) / (np.abs(bv) + _FLOOR)
    bad = np.isnan(rel)                  # inf - inf -> nan
    if bad.any():                        # matching (same-sign) infs => 0, else mismatch
        rel = np.where(bad, np.where(av == bv, 0.0, np.inf), rel)
    return float(np.max(rel))


def compare_pickles(path_a, path_b):
    """Compare the numeric (array/scalar) content of two scenario pickles.

    Returns a summary dict ``{worst_key, worst_reldiff, n_compared, per_key}``; the caller
    applies the tolerance. Compares every key present in BOTH whose value is a numeric
    ndarray/scalar; strings / None / object arrays are skipped. Raises only on unreadable
    input (a machinery error the caller treats as degrade-not-mismatch)."""
    with open(path_a, "rb") as f:
        da = pickle.load(f)
    with open(path_b, "rb") as f:
        db = pickle.load(f)
    worst_key, worst, n, per_key = None, 0.0, 0, {}
    for k in sorted(set(da) & set(db)):
        if k in _EXCLUDE_KEYS:           # non-result run metadata (e.g. wall-clock timing)
            continue
        va = da[k]
        if isinstance(va, (str, bytes)) or va is None:
            continue
        try:
            aa = np.asarray(va, dtype=np.float64)
            bb = np.asarray(db[k], dtype=np.float64)
        except (TypeError, ValueError):
            continue
        if aa.dtype.kind not in "fiu" or aa.size == 0:
            continue
        rd = _max_reldiff(aa, bb)
        n += 1
        per_key[k] = rd
        if rd > worst:
            worst, worst_key = rd, k
    return {"worst_key": worst_key, "worst_reldiff": worst,
            "n_compared": n, "per_key": per_key}


def run_compare(prod_dir, fresh_dir, scenarios, rtol):
    """Compare prod vs fresh per scenario. Returns ``(ok, mismatches, missing, details)``.

    ``mismatches`` = [(scenario, worst_key, worst_reldiff)] exceeding ``rtol`` (real
    failures). ``missing`` = scenarios not comparable (absent/unreadable pkl) — machinery
    issues, not mismatches. ``ok`` = no mismatches (missing alone does not fail)."""
    mismatches, missing, details = [], [], {}
    for s in scenarios:
        pa = os.path.join(prod_dir, f"{s}.pkl")
        pb = os.path.join(fresh_dir, f"{s}.pkl")
        if not (os.path.exists(pa) and os.path.exists(pb)):
            missing.append(s)
            continue
        try:
            cmp = compare_pickles(pa, pb)
        except Exception as e:           # noqa: BLE001 — machinery error, degrade
            missing.append(f"{s} (compare error: {type(e).__name__}: {e})")
            continue
        details[s] = cmp
        if cmp["worst_reldiff"] > rtol:
            mismatches.append((s, cmp["worst_key"], cmp["worst_reldiff"]))
    return (not mismatches), mismatches, missing, details


_BANNER = "=" * 78


def report(ok, mismatches, missing, details, rtol, label):
    """Print the re-solve-and-compare headline + (on failure) abundant diagnostics."""
    print(f"\n{_BANNER}")
    print(f"VERIFY (--complete): re-solve-and-compare reuse gate  [tol {label}]")
    print(f"  re-solved {len(details)} scenario(s) cache-OFF (same seed) vs the production "
          f"result.")
    print(_BANNER)
    if missing:
        print(f"[verify_resolve] DEGRADED: {len(missing)} scenario(s) not compared "
              f"(missing/unreadable pkl): {missing}. The welfare result STANDS; these were "
              f"not verified.", file=sys.stderr)
    if ok:
        worst = max((d["worst_reldiff"] for d in details.values()), default=0.0)
        print(f"  PASS: every compared scenario matches a fresh solve within {label} "
              f"(worst relative diff {worst:.2e}).")
        return
    print(f"  FAIL: {len(mismatches)} scenario(s) exceed {label} — the REUSED (cached / "
          f"seeded) solution does NOT match a fresh from-scratch solve. The production "
          f"result is SUSPECT.", file=sys.stderr)
    for s, key, rd in mismatches:
        print(f"    - {s}: worst array '{key}'  reldiff {rd:.3e}  (> {rtol:.1e})",
              file=sys.stderr)
    print("  Likely cause: a STALE cache entry — the config changed without a cache-key "
          "bump (the BUG-047 key-completeness class) — or a non-deterministic solve. "
          "Debug: re-run with HAFISCAL_USE_SOLUTION_CACHE=0 (bypass the cache) and audit "
          "solution_cache/keys.py's _HAFISCAL_NUMERICAL_ENV_VARS whitelist for a missing "
          "numerical-output flag.", file=sys.stderr)


def main(argv=None):
    """Standalone: compare two welfare result-dirs (production vs a cache-off re-run)."""
    import argparse
    p = argparse.ArgumentParser(
        description="Re-solve-and-compare: diff two welfare result-dirs within Tier-I.")
    p.add_argument("prod_dir", help="production (possibly cache-reused) result-dir")
    p.add_argument("fresh_dir", help="fresh (cache-off) re-run result-dir")
    p.add_argument("--scenarios", default=None,
                   help="comma list (default: the HAFISCAL_VERIFY_RESOLVE_SCOPE scope)")
    args = p.parse_args(argv)
    rtol, label = tolerance()
    sc = (tuple(s.strip() for s in args.scenarios.split(",") if s.strip())
          if args.scenarios else scope())
    ok, mism, missing, details = run_compare(args.prod_dir, args.fresh_dir, sc, rtol)
    report(ok, mism, missing, details, rtol, label)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
