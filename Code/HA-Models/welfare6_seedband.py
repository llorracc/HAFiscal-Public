#!/usr/bin/env python
"""Aggregate per-seed welfare tables into a seed mean + band (the S=3 ruling, 2026-08-01).

`run_welfare6_parallel.py --seed-offset K` writes one `welfare6_candidate.tex` (and, since
BUG-082, one `welfare4_candidate.tex`) per seed, each a LaTeX tabular whose data rows are
`<label> & v1 & v2 & v3 \\`. This tool reads N such tables (one per seed), aggregates every
numeric cell across the seeds, and writes

  <out_stem>_seedmean.tex   the same tabular with each cell = the seed MEAN, printed at the
                            input's decimals (drop-in for the paper's \input)
  <out_stem>_seedband.json  per cell: the per-seed values, mean, sd (ddof=1), SE, half-range, n
  <out_stem>_seedband.md    a human-readable summary (mean ± half-range, max |Δ| across seeds)

Why a separate step: the per-seed tables are the artefacts of record; the band is a
statistic OVER them, and a battery that overwrote its seeds (the 2026-08-20 spine drivers)
produced a single-seed table dressed as S=3. Counting the inputs here is the check.

Usage:
  python welfare6_seedband.py --out Tables/CRRA2/welfare6 \
      Tables/Baseline_parallel_seed0/welfare6_candidate.tex \
      Tables/Baseline_parallel_seed1/welfare6_candidate.tex \
      Tables/Baseline_parallel_seed2/welfare6_candidate.tex
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

_CELL_NUM = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*$")


def parse_table(text):
    """Split a LaTeX tabular into (preamble_lines, rows, postamble) where rows are
    [(label, [cell_str, ...], line_suffix)] for every line containing '&'."""
    rows = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "&" not in line:
            continue
        body, sep, suffix = line.partition("\\\\")
        cells = body.split("&")
        rows.append((i, cells[0], [c for c in cells[1:]], sep + suffix))
    return lines, rows


def _decimals(s):
    m = _CELL_NUM.match(s)
    if not m:
        return None
    v = m.group(1)
    return len(v.split(".")[1]) if "." in v else 0


def aggregate(texts, labels=None):
    """texts: list of table strings (one per seed). Returns (mean_text, cells) where cells is a
    dict keyed by 'row<i>/col<j>' -> stats, and mean_text is the first table with every numeric
    cell replaced by the seed mean at the input decimals. Raises on structural mismatch."""
    parsed = [parse_table(t) for t in texts]
    lines0, rows0 = parsed[0]
    for k, (_, rows) in enumerate(parsed[1:], start=1):
        if len(rows) != len(rows0) or any(len(r[2]) != len(r0[2]) for r, r0 in zip(rows, rows0)):
            raise ValueError(f"table {k} does not have the structure of table 0")
    cells = {}
    out_lines = list(lines0)
    for ri, (li, label, cells0, suffix) in enumerate(rows0):
        new_cells = []
        for cj, c0 in enumerate(cells0):
            vals = []
            for _, rows in parsed:
                c = rows[ri][2][cj]
                m = _CELL_NUM.match(c)
                if m:
                    vals.append(float(m.group(1)))
            if len(vals) == len(parsed) and vals:
                n = len(vals)
                mean = sum(vals) / n
                sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
                key = f"{label.strip()} | col{cj + 1}"
                cells[key] = {
                    "values": vals, "n": n, "mean": mean, "sd": sd,
                    "se": sd / math.sqrt(n) if n > 1 else 0.0,
                    "half_range": (max(vals) - min(vals)) / 2.0,
                    "min": min(vals), "max": max(vals),
                }
                d = _decimals(c0)
                lead = len(c0) - len(c0.lstrip())
                trail = len(c0) - len(c0.rstrip())
                new_cells.append(" " * lead + f"{mean:.{d}f}" + " " * trail)
            else:
                new_cells.append(c0)  # blank / non-numeric cells pass through unchanged
        out_lines[li] = label + "&" + "&".join(new_cells) + suffix
    return "\n".join(out_lines) + ("\n" if lines0 and texts[0].endswith("\n") else ""), cells


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tables", nargs="+", help="per-seed table files (one per seed, same layout)")
    p.add_argument("--out", required=True, help="output stem, e.g. Tables/CRRA2/welfare6")
    p.add_argument("--min-seeds", type=int, default=2, help="refuse with fewer inputs (default 2)")
    p.add_argument("--label", default="", help="free-text label for the summary")
    args = p.parse_args(argv)
    if len(args.tables) < args.min_seeds:
        print(f"welfare6_seedband: only {len(args.tables)} table(s) given; need >= {args.min_seeds} "
              f"-- a band over fewer seeds is not a band", file=sys.stderr)
        return 2
    texts = [open(f).read() for f in args.tables]
    mean_text, cells = aggregate(texts)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out + "_seedmean.tex", "w") as f:
        f.write(mean_text)
    with open(args.out + "_seedband.json", "w") as f:
        json.dump({"label": args.label, "inputs": args.tables, "n_seeds": len(texts), "cells": cells}, f, indent=2)
    lines = [f"# Seed band{(' — ' + args.label) if args.label else ''}", "",
             f"{len(texts)} seeds: " + ", ".join(args.tables), "",
             "| cell | mean | ± half-range | sd | values |", "|---|---|---|---|---|"]
    worst = 0.0
    for key, st in cells.items():
        rel = st["half_range"] / abs(st["mean"]) if st["mean"] else float("nan")
        worst = max(worst, rel if rel == rel else 0.0)
        lines.append(f"| {key} | {st['mean']:.4f} | {st['half_range']:.4f} | {st['sd']:.4f} | "
                     + " / ".join(f"{v:g}" for v in st["values"]) + " |")
    lines += ["", f"Largest relative half-range across cells: {100 * worst:.2f}%", ""]
    with open(args.out + "_seedband.md", "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"written: {args.out}_seedmean.tex, _seedband.json, _seedband.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
