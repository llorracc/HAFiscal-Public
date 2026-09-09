#!/usr/bin/env python3
"""Compose the no-splurge welfare comparison table from two welfare6 tables.

The paper's `Tables/Splurge0/welfare6-SplurgeComp.tex` shows each welfare cell of the
splurge=0 model with the baseline (splurge>0) value in parentheses, e.g. ``1.27(1.35)``.
Historically it was written by the legacy Step-5 path (``Welfare.py``, Splurge0 branch),
which needs a ``Welfare_Baseline_Results`` pickle that the parallel welfare battery
(``run_welfare6_parallel.py``) never produces. The battery writes an ordinary ``welfare6``
table per parametrization, so this script composes the comparison from the two tables
(Baseline and Splurge0) in the battery's own format -- same header, rows and footer as
``Welfare.py``; a cell that is blank in either table (e.g. the excluded UI no-recession
cell) stays blank.

Usage:
    python welfare6_splurgecomp.py --baseline PATH/welfare6_candidate.tex \
        --splurge0 PATH/welfare6_candidate.tex --out FromPandemicCode/Tables/Splurge0/welfare6-SplurgeComp.tex

The output is routed through generated_output.open_generated, i.e. written as the
`_candidate` sibling of ``--out`` unless HAFISCAL_PROMOTE=1.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROW_LABELS = [
    r"$\mathcal{W}(\text{policy}, Rec=0, AD=0)$",
    r"$\mathcal{W}(\text{policy}, Rec=1, AD=0)$",
    r"$\mathcal{W}(\text{policy}, Rec=1, AD=1)$",
]


def parse_welfare6(path):
    """Return {row_label: [check, ui, taxcut]} with cells as stripped strings ('' if blank)."""
    rows = {}
    for line in open(path, encoding="utf-8"):
        if not line.lstrip().startswith(r"$\mathcal{W}"):
            continue
        body = line.split(r"\\")[0]
        cells = [c.strip() for c in body.split("&")]
        label = cells[0]
        vals = [re.sub(r"\\(mid|bottom)rule", "", c).strip() for c in cells[1:4]]
        rows[label] = vals
    missing = [lab for lab in ROW_LABELS if lab not in rows]
    if missing:
        raise ValueError(f"{path}: welfare6 rows not found: {missing}")
    return rows


def compose(base, s0):
    out = "\\begin{tabular}{@{}lccc@{}} \n"
    out += "\\toprule \n"
    out += "                          & Stimulus check      & UI extension    & Tax cut    \\\\  \\midrule \n"
    for i, label in enumerate(ROW_LABELS):
        cells = []
        for b, s in zip(base[label], s0[label]):
            cells.append(f"{s}({b})" if (b and s) else "")
        tail = " \\\\ \\bottomrule \n" if i == len(ROW_LABELS) - 1 else " \\\\ \n"
        out += f"{label} & " + "  & ".join(f"{c:<11}" for c in cells).rstrip() + "    " + tail
    out += "\\end{tabular}  \n"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--baseline", required=True, help="welfare6 table of the splurge>0 (Baseline) battery")
    ap.add_argument("--splurge0", required=True, help="welfare6 table of the Splurge0 battery")
    ap.add_argument("--out", required=True, help="canonical output path (candidate sibling is written)")
    args = ap.parse_args(argv)
    base = parse_welfare6(args.baseline)
    s0 = parse_welfare6(args.splurge0)
    text = compose(base, s0)
    fpc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FromPandemicCode")
    if fpc not in sys.path:
        sys.path.insert(0, fpc)
    from generated_output import open_generated, output_path
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open_generated(args.out) as fh:
        fh.write(text)
    print(f"wrote {output_path(args.out)}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
