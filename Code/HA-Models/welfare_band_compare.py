#!/usr/bin/env python3
"""Seed-paired comparison of two welfare-6 bands, and the blessed per-machine reference band.

Owner charge 2026-09-07 ("put pairing to work"). Every welfare-6 band runs whole-cell seed
offsets 0..S-1, and the offset sets every RNG input (per-type seeds at a stride of 10000, the
income-shock seed, the kernel seeds), so seed k of any two runs starts from the same random
state. Whether the two stay PAIRED depends on whether they consume the streams the same way:

  * a same-engine code change keeps them paired -- the per-seed differences scatter far less
    than two independent draws would (measured 2026-09-07: onset-spike off/on, plain/strata,
    hark/hybrid: UI per-seed diff SD 0-1.9 % against an unpaired expectation of 3.3-6.4 %);
  * a change to the panel SAMPLER or the AD PATH decouples the UI cells (default vs
    as-corrected: 5.3 % vs 5.5 %), because the panel draw itself moves.

This module makes both facts usable. `compare_bands` pairs like-numbered seeds and reports,
per cell, the mean paired difference with its PAIRED standard error next to the unpaired one,
plus an empirical pairing verdict. `pairing_probe` checks the quiet cells (per-seed SD <= 0.1 %)
seed by seed: if they differ, the streams have decoupled and any tolerance calibrated on a
paired SE is void -- the caller must adjudicate the change and re-bless, not widen bars.
`bless` snapshots a band as this machine's reference (untracked `welfare_reference/<world>/`,
the `hot_reference/` pattern) with a manifest naming the commit and the run's resolved flags.

Consumers: full_profile_rerun_gates.py (the seed-paired C4 reference gate), the memo and
briefing SE rows, welfare_bridge_arm.sh (the paired cross-world comparison). Never reads or
writes anything under LOCKED_TABLES; summaries only.

CLI:
  welfare_band_compare.py compare 'Tables/Baseline_seed*' 'Tables/Baseline_ac_20260907_seed*'
  welfare_band_compare.py probe   A B            # pairing verdict only (exit 3 if decoupled)
  welfare_band_compare.py bless   'Tables/Baseline_seed*' --ref-dir welfare_reference/default --world default
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import math
import os
import re
import socket
import subprocess
import sys

SUMMARY = "welfare6_parallel_summary.json"
SKIP = frozenset({"ui_norec"})            # 0/0 cell, never reported (standing rule)
# Pairing probes: cells whose per-seed SD is <= 0.12 % in every band of record (2026-09-07),
# so a per-seed difference above PAIRING_PROBE_TOL cannot be seed noise -- the streams moved.
QUIET_CELLS = ("taxcut_norec", "check_norec", "taxcut_rec")
PAIRING_PROBE_TOL = 2e-3
# Empirical verdict: paired when the per-seed difference SD is under half the unpaired
# expectation sqrt(cv_A^2 + cv_B^2). Measured paired pairs sit at 0.0-0.5 of it, decoupled
# ones at 0.9-1.0; nothing observed near the boundary.
PAIRED_RATIO = 0.5
_SEED_RE = re.compile(r"seed(\d+)$")
_FLAG_KEYS = ("HAFISCAL_WORLD", "HAFISCAL_AD_EQUILIBRIUM_SHARE", "HAFISCAL_MC_WEIGHTED_TAIL",
              "HAFISCAL_UI_EXTENSION_POLICY", "HAFISCAL_ONSET_SPIKE_T0_EXEMPT",
              "HAFISCAL_TM_A_INDEXED", "HAFISCAL_STEP5_ATI", "HAFISCAL_WELFARE_ENGINE",
              "HAFISCAL_PERM_GROWTH_SCALE", "HAFISCAL_SHUFFLE_MRKV_STRATA")


def seed_of(path):
    """Seed index from a per-seed directory or file name ending in seed<k>; None if absent."""
    base = os.path.basename(os.path.normpath(path))
    base = base[:-5] if base.endswith(".json") else base
    m = _SEED_RE.search(base)
    return int(m.group(1)) if m else None


def load_band(spec):
    """{seed: cells}. `spec` is a glob of per-seed dirs ('Tables/Baseline_seed*', each holding
    welfare6_parallel_summary.json), a reference dir holding seed<k>.json, or a list of
    summary-file paths whose parent dirs end in seed<k>."""
    out = {}
    if isinstance(spec, (list, tuple)):
        paths = list(spec)
    elif os.path.isdir(spec) and glob.glob(os.path.join(spec, "seed*.json")):
        paths = sorted(glob.glob(os.path.join(spec, "seed*.json")))
    else:
        paths = [os.path.join(d, SUMMARY) for d in sorted(glob.glob(spec)) if os.path.isdir(d)]
    for p in paths:
        if not os.path.exists(p):
            continue
        k = seed_of(p) if p.endswith(".json") and seed_of(p) is not None else seed_of(os.path.dirname(p))
        if k is None:
            continue
        with open(p) as f:
            j = json.load(f)
        out[k] = dict(j.get("welfare6", j))
    return out


def _mean(v):
    return sum(v) / len(v)


def _sd(v):
    if len(v) < 2:
        return float("nan")
    m = _mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def compare_bands(A, B, cells=None):
    """Per-cell rows for band B relative to band A on their common seeds. Differences are
    RELATIVE (B/A - 1) per seed; `diff` is their mean, `paired_se` its SE, `unpaired_se` the SE
    the same difference of means would carry with independent seeds."""
    keys = sorted(set(A) & set(B))
    if cells is None:
        cells = [c for c in sorted(set().union(*A.values(), *B.values())) if c not in SKIP]
    rows = []
    for c in cells:
        ks = [k for k in keys if c in A[k] and c in B[k] and A[k][c] not in (0, None)]
        if len(ks) < 2:
            rows.append({"cell": c, "n": len(ks), "pairing": "n/a"})
            continue
        a = [float(A[k][c]) for k in ks]
        b = [float(B[k][c]) for k in ks]
        d = [b_i / a_i - 1.0 for a_i, b_i in zip(a, b)]
        n = len(ks)
        cv_a = _sd(a) / abs(_mean(a))
        cv_b = _sd(b) / abs(_mean(b))
        unpaired_per_seed = math.sqrt(cv_a ** 2 + cv_b ** 2)
        sd_d = _sd(d)
        if unpaired_per_seed == 0.0:
            pairing = "paired" if sd_d == 0.0 else "unpaired"
        else:
            pairing = "paired" if sd_d < PAIRED_RATIO * unpaired_per_seed else "unpaired"
        rows.append({
            "cell": c, "n": n, "seeds": ks,
            "mean_a": _mean(a), "mean_b": _mean(b),
            "diff": _mean(d), "sd_diff": sd_d,
            "paired_se": sd_d / math.sqrt(n),
            "unpaired_se": unpaired_per_seed / math.sqrt(n),
            "unpaired_per_seed": unpaired_per_seed,
            "per_seed": d, "pairing": pairing,
        })
    return rows


def pairing_probe(A, B, tol=PAIRING_PROBE_TOL, cells=QUIET_CELLS):
    """(ok, worst) -- ok is False when any quiet cell differs by more than `tol` on any common
    seed, i.e. the two bands' random streams decoupled. `worst` = (cell, seed, rel_diff)."""
    worst = (None, None, 0.0)
    for c in cells:
        for k in sorted(set(A) & set(B)):
            if c not in A[k] or c not in B[k] or not A[k][c]:
                continue
            r = abs(float(B[k][c]) / float(A[k][c]) - 1.0)
            if r > worst[2]:
                worst = (c, k, r)
    return worst[2] <= tol, worst


def format_table(rows, title=None):
    lines = []
    if title:
        lines.append(f"### {title}")
        lines.append("")
    lines.append("| cell | S | A mean | B mean | B/A−1 | paired SE | unpaired SE | z (paired) | pairing |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r.get("pairing") == "n/a":
            lines.append(f"| {r['cell']} | {r['n']} | | | | | | | n/a |")
            continue
        # Below 1e-6 relative the difference is numerical noise (cross-platform bands differ by
        # ~3e-9, 2026-09-07) and a z built from two ~zero numbers means nothing: print 0.
        z = (0.0 if abs(r["diff"]) < 1e-6 else
             abs(r["diff"]) / r["paired_se"] if r["paired_se"] > 0 else float("inf"))
        lines.append(f"| {r['cell']} | {r['n']} | {r['mean_a']:.4f} | {r['mean_b']:.4f} | "
                     f"{100 * r['diff']:+.2f} % | {100 * r['paired_se']:.2f} % | "
                     f"{100 * r['unpaired_se']:.2f} % | {z:.1f} | {r['pairing']} |")
    return "\n".join(lines)


def _git_head(cwd):
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


def sidecar_flags(dirpath):
    """The run's resolved flags from the newest welfare provenance sidecar in `dirpath`
    (set_flags win over resolved_config.env, both recorded by provenance.py); {} if none."""
    best, best_m = None, -1.0
    for p in glob.glob(os.path.join(dirpath, "RUN_*.prov.json")):
        try:
            with open(p) as f:
                j = json.load(f)
        except Exception:
            continue
        ep = json.dumps(j.get("entry_point", j.get("argv", "")))
        if "welfare" not in ep:
            continue
        m = os.path.getmtime(p)
        if m > best_m:
            best, best_m = j, m
    if best is None:
        return {}
    env = dict(best.get("resolved_config", {}).get("env", {}))
    env.update(best.get("set_flags", {}))
    return {k: env[k] for k in _FLAG_KEYS if k in env}


def bless(band_spec, ref_dir, world, note=""):
    """Snapshot a band's per-seed summaries into `ref_dir` as seed<k>.json + MANIFEST.json.
    Refuses an empty band. Returns the manifest."""
    band = load_band(band_spec)
    if not band:
        raise SystemExit(f"bless: no per-seed summaries match {band_spec!r}")
    os.makedirs(ref_dir, exist_ok=True)
    for old in glob.glob(os.path.join(ref_dir, "seed*.json")):
        os.remove(old)
    sources, flags = {}, {}
    dirs = sorted(d for d in glob.glob(band_spec)) if isinstance(band_spec, str) else []
    for d in dirs:
        k = seed_of(d)
        if k in band:
            sources[str(k)] = os.path.abspath(d)
            if not flags:
                flags = sidecar_flags(d)
    for k, cells in sorted(band.items()):
        with open(os.path.join(ref_dir, f"seed{k}.json"), "w") as f:
            json.dump({"welfare6": cells}, f, indent=1, sort_keys=True)
    manifest = {
        "blessed_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "machine": socket.gethostname(),
        "head": _git_head(os.path.dirname(os.path.abspath(__file__))),
        "world": world,
        "seeds": sorted(band),
        "source_dirs": sources,
        "flags": flags,
        "note": note,
        "format": "welfare-reference-v1",
    }
    with open(os.path.join(ref_dir, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("compare", help="seed-paired comparison of band B against band A")
    pc.add_argument("a")
    pc.add_argument("b")
    pc.add_argument("--cells", nargs="*", default=None)
    pc.add_argument("--json", default=None, help="also write the rows as JSON here")
    pc.add_argument("--title", default=None)
    pp = sub.add_parser("probe", help="pairing verdict on the quiet cells (exit 3 if decoupled)")
    pp.add_argument("a")
    pp.add_argument("b")
    pb = sub.add_parser("bless", help="snapshot a band as this machine's reference")
    pb.add_argument("band")
    pb.add_argument("--ref-dir", required=True)
    pb.add_argument("--world", required=True)
    pb.add_argument("--note", default="")
    args = ap.parse_args(argv)
    if args.cmd == "bless":
        m = bless(args.band, args.ref_dir, args.world, args.note)
        print(f"blessed {len(m['seeds'])} seeds {m['seeds']} -> {args.ref_dir} (head {str(m['head'])[:8]}, "
              f"world {m['world']}, flags {m['flags']})")
        return 0
    A, B = load_band(args.a), load_band(args.b)
    common = sorted(set(A) & set(B))
    if len(common) < 2:
        print(f"only {len(common)} common seeds between {args.a!r} ({sorted(A)}) and {args.b!r} ({sorted(B)})")
        return 2
    ok, worst = pairing_probe(A, B)
    verdict = ("PAIRED streams (quiet cells agree per seed)" if ok else
               f"DECOUPLED streams: {worst[0]} seed {worst[1]} differs {100 * worst[2]:.2f} % "
               f"(> {100 * PAIRING_PROBE_TOL:.1f} %) -- tolerances calibrated on a paired SE do not apply")
    if args.cmd == "probe":
        print(verdict)
        return 0 if ok else 3
    rows = compare_bands(A, B, args.cells)
    print(format_table(rows, args.title or f"{args.b}  vs  {args.a}  (seeds {common})"))
    print()
    print(verdict)
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"a": args.a, "b": args.b, "seeds": common, "pairing_probe_ok": ok,
                       "worst_probe": worst, "rows": rows}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
