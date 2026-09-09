#!/usr/bin/env python
"""Robustness appendix: re-estimated values vs the hand-typed published tables.

`Subfiles/Appendix-Robustness.tex` carries its tables as literal numbers (no generated
inputs). This tool reads the re-estimated calibrations and welfare tables produced by the
2026-08-20/21 robustness batteries and prints them next to the published rows, so the
appendix can be updated (or converted to generated inputs) with the differences in view.

Per configuration it shows
  splurge            Target_AggMPCX_LiquWealth/Result_AllTarget_ESC.txt (R / benefits rows: the
                     main-spec splurge, NOT re-estimated, as published) or
                     Result_CRRA_<g>.0_ESC.txt (gamma rows: re-estimated per gamma)
  (beta, nabla) x 3  Results/DiscFacEstim_CRRA_<g>_R_<R>[_altBenefits]_ESC.txt
  C (bp), no AD / AD delegated to robustness_appendix_tables.config_cells (the SoT for the
                     appendix's C rows) -- seed-mean over FromPandemicCode/Tables/<param>_seed*/
                     welfare4_candidate.tex, so this report and the appendix tables cannot disagree
                     (BUG-082 corrected; HAFISCAL_WELFARE_CE_HORIZON=lifetime)
  W                  seed-mean over FromPandemicCode/Tables/<param>_seed*/welfare6_candidate.tex
                     (main-text measure, for the sign cross-check), the same seed set as C
  The pre-2026-09-04 reads were Tables/<param>_parallel/, the layout the 2026-08-20/21
  batteries wrote; every battery since writes per-seed dirs, so those reads returned nothing.

Usage:
  python robustness_appendix_diff.py                 # main checkout
  python robustness_appendix_diff.py --root ~/coldrun_2026-08/wt2   # a worktree
  python robustness_appendix_diff.py --md out.md     # also write markdown
Missing inputs print as "—" (nothing is invented).
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import robustness_appendix_tables as rat  # noqa: E402  (the SoT for the appendix's C rows)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# (label, parametrization, DiscFacEstim stem, splurge file, published key in the tex)
CONFIGS = [
    ("R = 1.005",            "Rfree_1005", "DiscFacEstim_CRRA_2.0_R_1.005",           "Result_AllTarget_ESC.txt"),
    ("R = 1.01 (baseline)",  "Baseline",   "DiscFacEstim_CRRA_2.0_R_1.01",            "Result_AllTarget_ESC.txt"),
    ("R = 1.015",            "Rfree_1015", "DiscFacEstim_CRRA_2.0_R_1.015",           "Result_AllTarget_ESC.txt"),
    ("gamma = 1",            "CRRA1",      "DiscFacEstim_CRRA_1.0_R_1.01",            "Result_CRRA_1.0_ESC.txt"),
    ("gamma = 3",            "CRRA3",      "DiscFacEstim_CRRA_3.0_R_1.01",            "Result_CRRA_3.0_ESC.txt"),
    ("lower benefits",       "LowerUBnoB", "DiscFacEstim_CRRA_2.0_R_1.01_altBenefits", "Result_AllTarget_ESC.txt"),
    ("Rspell 4q",            "Rspell_4",   None,                                       None),
    ("AD elasticity 0.5",    "ADElas",     None,                                       None),
]

# Published appendix rows (QE 17(3); hand-typed in Subfiles/Appendix-Robustness.tex).
# estimates: splurge, (beta, nabla) dropout / HS / college. welfare: C bp no-AD (check, UI,
# taxcut), AD (check, UI, taxcut). '*' / dagger decorations dropped.
PUBLISHED = {
    "R = 1.005":           {"est": (0.307, 0.740, 0.298, 0.927, 0.193, 0.989, 0.0082),
                            "C":   (0.005, 0.295, 0.001, 0.081, 0.618, 0.030)},
    "R = 1.01 (baseline)": {"est": (0.307, 0.735, 0.298, 0.924, 0.137, 0.984, 0.0096),
                            "C":   (0.011, 0.509, 0.002, 0.151, 1.101, 0.056)},
    "R = 1.015":           {"est": (0.307, 0.724, 0.357, 0.919, 0.138, 0.979, 0.0105),
                            "C":   (0.014, 0.666, 0.003, 0.215, 1.496, 0.081)},
    "gamma = 1":           {"est": (0.312, 0.692, 0.333, 0.966, 0.154, 1.05, 0.015),
                            "C":   None},   # the published gamma table shows only gamma = 2, 3 welfare rows
    "gamma = 3":           {"est": (0.304, 0.593, 0.459, 0.889, 0.110, 0.973, 0.017),
                            "C":   (0.011, 0.558, 0.002, 0.156, 1.207, 0.059)},
    "lower benefits":      {"est": (0.306, 0.609, 0.445, 0.890, 0.116, 0.978, 0.016),
                            "C":   (0.043, 1.845, 0.003, 0.157, 2.514, 0.048)},
    "Rspell 4q":           {"est": None, "C": (0.010, 0.424, 0.002, 0.143, 0.926, 0.045)},
    "AD elasticity 0.5":   {"est": None, "C": (0.011, 0.509, 0.002, 0.297, 1.695, 0.110)},
}

_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _read_discfac(path):
    rows = {}
    if not os.path.exists(path):
        return None
    for line in open(path):
        m = re.search(r"'EducationGroup': (\d).*?'beta': ([0-9.eE+-]+).*?'nabla': ([0-9.eE+-]+)", line)
        if m:
            rows[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
    return rows if len(rows) == 3 else None


def _read_splurge(path):
    if not os.path.exists(path):
        return None
    first = open(path).read().strip().splitlines()[0]
    m = re.search(r"'splurge': ([0-9.eE+-]+)", first)
    return float(m.group(1)) if m else None


def _read_tex_rows(path, n_cells):
    """Numeric cells of the data rows of a battery table: list of tuples (len n_cells),
    blank cells as None."""
    if not os.path.exists(path):
        return None
    out = []
    for line in open(path):
        if "&" not in line or "\\\\" not in line or "mathcal" not in line:
            continue
        cells = line.split("\\\\")[0].split("&")[1:]
        vals = []
        for c in cells:
            m = _NUM.search(c)
            vals.append(float(m.group(0)) if m else None)
        if len(vals) == n_cells:
            out.append(tuple(vals))
    return out or None


def _fmt(v, d=3):
    return "—" if v is None else f"{v:.{d}f}"


def _delta(new, old):
    if new is None or old is None:
        return ""
    if old == 0:
        return ""
    return f" ({100 * (new - old) / abs(old):+.0f}%)"


def _seed_mean_rows(tables_dir, param, fname, ncols):
    """Seed-mean of a battery tabular over Tables/<param>_seed*/<fname> -- the same seed set
    config_cells averages for C, so the two columns of this report describe one sample."""
    import glob as _glob
    tabs = [_read_tex_rows(f, ncols) for f in sorted(_glob.glob(os.path.join(tables_dir, f"{param}_seed*", fname)))]
    tabs = [t for t in tabs if t]
    if not tabs:
        return None
    nrow = min(len(t) for t in tabs)
    out = []
    for r in range(nrow):
        row = []
        for c in range(ncols):
            vals = [t[r][c] for t in tabs if t[r][c] is not None]
            row.append(sum(vals) / len(vals) if vals else None)
        out.append(tuple(row))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=REPO, help="repo root or worktree to read from")
    p.add_argument("--md", default=None, help="also write the markdown here")
    args = p.parse_args(argv)
    root = os.path.abspath(os.path.expanduser(args.root))
    res = os.path.join(root, "Code", "HA-Models", "Results")
    s1 = os.path.join(root, "Code", "HA-Models", "Target_AggMPCX_LiquWealth")
    fpc = os.path.join(root, "Code", "HA-Models", "FromPandemicCode")
    lines = [f"# Robustness appendix — re-estimated vs published (root: {root})", ""]
    lines += ["## Estimates (splurge; beta, nabla by education)", "",
              "| config | splurge new (pub) | D beta | D nabla | HS beta | HS nabla | C beta | C nabla |",
              "|---|---|---|---|---|---|---|---|"]
    for label, param, dstem, sfile in CONFIGS:
        pub = PUBLISHED.get(label, {}).get("est")
        if dstem is None:
            continue
        d = _read_discfac(os.path.join(res, dstem + "_ESC.txt")) or _read_discfac(os.path.join(res, dstem + "_TM_a_ESC.txt"))
        spl = _read_splurge(os.path.join(s1, sfile)) if sfile else None
        cells = [f"{_fmt(spl)} ({_fmt(pub[0]) if pub else '—'})"]
        for g, (pb, pn) in zip((0, 1, 2), ((1, 2), (3, 4), (5, 6))):
            b = d[g][0] if d else None
            n = d[g][1] if d else None
            cells.append(f"{_fmt(b)} ({_fmt(pub[pb]) if pub else '—'}){_delta(b, pub[pb] if pub else None)}")
            cells.append(f"{_fmt(n, 4)} ({_fmt(pub[pn], 4) if pub else '—'}){_delta(n, pub[pn] if pub else None)}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "## Welfare C in basis points (BUG-082 corrected, lifetime horizon) — new (published)", "",
              "| config | no AD: check | UI | tax cut | AD: check | UI | tax cut | W (new, Rec AD=0 / AD=1: check, UI, taxcut) |",
              "|---|---|---|---|---|---|---|---|"]
    for label, param, dstem, sfile in CONFIGS:
        pubC = PUBLISHED.get(label, {}).get("C")
        td = os.path.join(fpc, "Tables")
        cells = rat.config_cells(param, "window", td)          # seed-mean, the appendix tables' own reader
        newC = tuple(cells["noAD"][0]) + tuple(cells["AD"][0]) if cells else (None,) * 6
        w6 = _seed_mean_rows(td, param, "welfare6_candidate.tex", 3)
        cells = [f"{_fmt(v)} ({_fmt(pubC[i]) if pubC else '—'})" for i, v in enumerate(newC)]
        wtxt = "—"
        if w6 and len(w6) >= 3:
            wtxt = " / ".join(", ".join(_fmt(v, 2) for v in row) for row in (w6[1], w6[2]))
        lines.append(f"| {label} | " + " | ".join(cells) + f" | {wtxt} |")
    lines += ["", "Published values are the hand-typed rows of Subfiles/Appendix-Robustness.tex (QE 17(3)); "
              "their C column is the BUG-082-defective measure, so level differences there are expected "
              "(the corrected gain term is ~12x larger at gamma = 2; compare signs with W).", ""]
    text = "\n".join(lines)
    print(text)
    if args.md:
        with open(args.md, "w") as f:
            f.write(text)
        print(f"written: {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
