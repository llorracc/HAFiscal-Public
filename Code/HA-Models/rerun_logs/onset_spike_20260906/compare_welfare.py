#!/usr/bin/env python3
"""Compare the welfare-6 cells of the two BUG-122 Step-0 arms, seed by paired seed.

Usage:  compare_welfare.py <parametrization> [--seeds 3] [--tag-off osoff] [--tag-on oson]

Both arms run the same seed offsets, so the per-seed difference is common-random-number paired
and its across-seed spread is the right yardstick for the change -- far tighter than comparing
two independent means. With S seeds the paired t has S-1 degrees of freedom, so at S = 3 read
the ratio as an order of magnitude, not a p-value.

`ui_norec` is never reported: it is 0/0 by construction.
"""

import argparse
import json
import math
import sys
from pathlib import Path

FPC = Path(__file__).resolve().parents[2] / "FromPandemicCode"

SKIP = {"ui_norec"}
ORDER = ["check_norec", "taxcut_norec", "check_rec", "ui_rec", "taxcut_rec",
         "check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]


def _cells(param, tag, seed):
    p = FPC / "Tables" / f"{param}_{tag}_seed{seed}" / "welfare6_parallel_summary.json"
    if not p.exists():
        return None
    with open(p) as fh:
        return (json.load(fh) or {}).get("welfare6") or {}


def _mean_sd(xs):
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, float("nan")
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(var)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("param")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--tag-off", default="osoff")
    ap.add_argument("--tag-on", default="oson")
    a = ap.parse_args()

    off = [_cells(a.param, a.tag_off, k) for k in range(a.seeds)]
    on = [_cells(a.param, a.tag_on, k) for k in range(a.seeds)]
    have = [k for k in range(a.seeds) if off[k] and on[k]]
    if not have:
        print(f"# no paired seeds found for {a.param} "
              f"({a.tag_off}/{a.tag_on}, seeds 0..{a.seeds - 1})")
        return 1
    missing = [k for k in range(a.seeds) if k not in have]
    print(f"# {a.param}: {len(have)} paired seed(s) {have}"
          + (f"  -- MISSING {missing}" if missing else ""))
    print(f"# arms: OFF = _{a.tag_off}_seed*   ON = _{a.tag_on}_seed*\n")
    print(f"{'cell':<16}{'OFF mean':>12}{'ON mean':>12}{'delta':>12}{'%':>9}"
          f"{'paired SD':>12}{'delta/SE':>10}")
    keys = [k for k in ORDER if k in off[have[0]]] + \
           [k for k in sorted(off[have[0]]) if k not in ORDER and k not in SKIP]
    for key in keys:
        if key in SKIP:
            continue
        a_vals = [off[k][key] for k in have if key in off[k]]
        b_vals = [on[k][key] for k in have if key in on[k]]
        if len(a_vals) != len(b_vals) or not a_vals:
            continue
        diffs = [b - x for x, b in zip(a_vals, b_vals)]
        ma, _ = _mean_sd(a_vals)
        mb, _ = _mean_sd(b_vals)
        md, sd = _mean_sd(diffs)
        se = sd / math.sqrt(len(diffs)) if len(diffs) > 1 else float("nan")
        ratio = md / se if se and se == se and se > 0 else float("nan")
        pct = 100.0 * md / ma if ma else float("nan")
        print(f"{key:<16}{ma:>12.6f}{mb:>12.6f}{md:>12.6f}{pct:>8.2f}%"
              f"{sd:>12.2e}{ratio:>10.1f}")
    print("\n# delta = ON - OFF, paired within seed. 'paired SD' is the across-seed spread of that")
    print("# difference; a |delta/SE| of order 1 is noise, of order 10 is a real move.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
