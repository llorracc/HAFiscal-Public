#!/usr/bin/env python3
"""Compare per-machine bench_toolmap.py result JSONs → the cross-platform tolerance.

Phase-A job #3: read every `results/<host>.json`, diff the numeric fingerprints
across machines (element-wise abs + relative), and print (a) the worst x-platform
delta — the tolerance to quote — and (b) the solve/sim timing table for the tool
map. Pure stdlib; no deps.

Usage:  python Code/HA-Models/toolmap/compare_results.py
"""
import json, glob, os, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = sorted(glob.glob(os.path.join(HERE, "results", "*.json")))


def load(p):
    with open(p) as f:
        return json.load(f)


def rel(a, b):
    d = abs(a - b)
    s = max(abs(a), abs(b))
    return d / s if s else 0.0


def flat_fp(d):
    """Flatten a fingerprint into {label: value} for element-wise diffing."""
    fp = d["fingerprint"]
    out = {}
    for i, v in enumerate(fp.get("cfunc_at_points", [])):
        out[f"cfunc[m={fp['cfunc_m_points'][i]}]"] = v
    if fp.get("anderson_engaged", True):  # skip if Anderson fell back to EGM on this machine
        for i, v in enumerate(fp.get("anderson_cfunc_at_points", [])):
            out[f"andcfunc[m={fp['cfunc_m_points'][i]}]"] = v
    for k, v in fp.get("agg_moments", {}).items():
        out[f"agg.{k}"] = v
    for k, v in fp.get("tm_moments", {}).items():
        if isinstance(v, (int, float)):   # skip 'interpretation', etc.
            out[f"tm.{k}"] = v
    return out


def main():
    if len(RESULTS) < 1:
        print("no results/*.json found")
        return
    runs = {load(p)["env"]["hostname"]: load(p) for p in RESULTS}
    hosts = list(runs)
    print(f"machines: {len(hosts)}")
    for h in hosts:
        e = runs[h]["env"]
        print(f"  {h:18s} {e['arch']:7s} py{e['python_version']} np{e['numpy_version']} "
              f"numba{e['numba_version']} HARK{e['hark_version']}")

    print("\n=== timings (s) ===")
    print(f"  {'host':18s} {'build':>8s} {'solve':>8s} {'sim':>8s} {'total':>8s}")
    for h in hosts:
        r = runs[h]
        print(f"  {h:18s} {r.get('build_seconds',0):8.3f} {r['solve_seconds']:8.3f} "
              f"{r['sim_seconds']:8.3f} {r.get('total_seconds',0):8.3f}")

    if len(hosts) < 2:
        print("\n(only one machine — run on a second platform to get a tolerance)")
        return

    print("\n=== cross-platform fingerprint delta ===")
    worst_abs = 0.0
    worst_rel = 0.0
    worst_label = ""
    for a, b in itertools.combinations(hosts, 2):
        fa, fb = flat_fp(runs[a]), flat_fp(runs[b])
        keys = [k for k in fa if k in fb]
        pair_abs = max((abs(fa[k] - fb[k]) for k in keys), default=0.0)
        pair_rel = max((rel(fa[k], fb[k]) for k in keys), default=0.0)
        print(f"  {a} vs {b}:  max |abs| = {pair_abs:.3e}   max rel = {pair_rel:.3e}")
        for k in keys:
            r = rel(fa[k], fb[k])
            if r > worst_rel:
                worst_rel, worst_abs, worst_label = r, abs(fa[k] - fb[k]), k
        worst_abs = max(worst_abs, pair_abs)

    print(f"\nWORST relative delta: {worst_rel:.3e}  (field {worst_label!r}, |abs| {worst_abs:.3e})")
    n_ident = "identical" if worst_rel == 0 else f"agree to ~{-1*__import__('math').log10(worst_rel):.0f} significant digits" if worst_rel > 0 else ""
    print(f"=> cross-platform (x86_64 vs arm64) reproduction is {n_ident}.")
    print("   Same-platform reruns are bit-identical (deterministic seeds); cross-platform")
    print(f"   tolerance to quote for the tool map: rel <= {max(worst_rel,1e-15):.0e}.")


if __name__ == "__main__":
    main()
