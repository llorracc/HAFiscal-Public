#!/usr/bin/env python3
"""Morning report for the income-strata N-ladder (welfare_strata_nladder.sh): does the CRN-paired
difference pstratM - plainM vanish as the panel grows?

Certification standard (Econ-1 plan, the certified-numerics 'asymptotic' kind): the stratified draw is
an exact re-weighting, so for every welfare cell the paired difference must shrink with N and be
inside its own paired SE at the top rung. This script states, per scope and cell, the paired mean
difference with its SE at each rung, the per-seed scatter of both arms (the knob's payoff), and a
verdict. It reads the per-seed summaries only; it adopts nothing.

Usage: strata_nladder_report.py [--tables DIR] [--scope baseline|hsonly|both] [--out REPORT.md]
"""
import argparse, glob, json, math, os, re, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import welfare_band_compare as wbc  # noqa: E402

CELLS = ["check_rec", "ui_rec", "taxcut_rec", "check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]
# Reporting-precision floor: the welfare tables print two decimals (~1 % of a cell), so a paired
# difference below 0.05 % is zero at twenty times the printed precision whatever its z -- the
# near-deterministic tax-cut cells (per-seed SD 0.01 %) otherwise 'fail' on a 0.01 % difference at
# z 2.7 (HS_Only N=96000, 2026-09-08 00:38). The certification standard is stated in significant
# figures (feedback_numerical_stability_acceptance_criterion), not in z alone.
PRECISION_FLOOR = 5e-4
SCOPES = {"baseline": ("Baseline", [10000, 40000, 100000], "sharing + weighted-tail panel (the default world's sampler)", "nladder"),
          "hsonly": ("HS_Only", [1500, 6000, 24000, 96000], "own AD loop + equal-weight panel (as-corrected's sampler)", "nladder"),
          # 2026-09-08 02:20: the top rung with the EQUAL-weight panel UNDER sharing -- separates the sampler from the
          # sharing as the carrier of the weighted-panel residual (+0.65 % on the UI cells at 100k, z 4).
          "baseline_ew": ("Baseline", [100000], "sharing + EQUAL-weight panel (the separating rung)", "nladderEW"),
          # the 2x2's fourth cell (05:05): weighted panel with the battery's OWN AD loop, at 40k (m5)
          "baseline_wo": ("Baseline", [40000], "OWN AD loop + weighted-tail panel (the 2x2's fourth cell)", "nladderWO")}


def rung(tables, param, arm, n, tag="nladder"):
    return wbc.load_band(os.path.join(tables, f"{param}_{tag}_{arm}_N{n}_seed*"))


def report(tables, scope):
    param, ns, desc, tag = SCOPES[scope]
    L = [f"## {scope}: {param}, {desc}", ""]
    verdict_rows = []
    L.append("| N | cell | plainM per-seed SD | pstratM per-seed SD | paired diff | paired SE | z | S |")
    L.append("|---|---|---|---|---|---|---|---|")
    for n in ns:
        A, B = rung(tables, param, "plainM", n, tag), rung(tables, param, "pstratM", n, tag)
        common = sorted(set(A) & set(B))
        if len(common) < 2:
            L.append(f"| {n} | — | | | (only {len(common)} common seeds: rung incomplete) | | | {len(common)} |")
            continue
        rows = {r["cell"]: r for r in wbc.compare_bands(A, B, CELLS)}
        for c in CELLS:
            r = rows.get(c)
            if not r or r.get("pairing") == "n/a":
                continue
            a = [A[k][c] for k in common]; b = [B[k][c] for k in common]
            sa = st.stdev(a) / abs(st.mean(a)) if len(a) > 1 else float("nan")
            sb = st.stdev(b) / abs(st.mean(b)) if len(b) > 1 else float("nan")
            z = abs(r["diff"]) / r["paired_se"] if r["paired_se"] > 0 else float("inf")
            L.append(f"| {n} | {c} | {100*sa:.2f} % | {100*sb:.2f} % | {100*r['diff']:+.2f} % | {100*r['paired_se']:.2f} % | {z:.1f} | {r['n']} |")
            verdict_rows.append((n, c, r["diff"], r["paired_se"], z))
    L.append("")
    # verdict per cell: |diff| at the top rung within 2 paired SE, and not growing along the ladder
    L.append("### Verdict")
    ok_all = True
    for c in CELLS:
        seq = [(n, d, se, z) for (n, cc, d, se, z) in verdict_rows if cc == c]
        if not seq:
            continue
        top = seq[-1]
        within = top[3] <= 2.0 or abs(top[1]) <= PRECISION_FLOOR
        diffs = [abs(d) for _, d, _, _ in seq]
        shrinking = len(diffs) < 2 or diffs[-1] <= max(diffs[:-1]) + 1e-12
        ok = within and shrinking
        ok_all &= ok
        L.append(f"- {c}: top rung N={top[0]} diff {100*top[1]:+.2f} % ± {100*top[2]:.2f} % (z {top[3]:.1f}); "
                 f"|diff| along the ladder {' → '.join(f'{100*d:.2f} %' for d in diffs)} — "
                 f"{'PASS' if ok else 'FAIL'} ({('within 2 SE at the top' if top[3] <= 2.0 else 'below the 0.05 % reporting-precision floor at the top') if within else 'OUTSIDE 2 SE and above the 0.05 % floor at the top'}"
                 f"{'' if shrinking else '; not shrinking'})")
    L.append("")
    L.append(f"**{scope}: {'CERTIFIABLE — the paired difference is inside its SE at the top rung and does not grow' if ok_all else 'NOT certifiable on this ladder — see the failing cells'}**")
    L.append("")
    return "\n".join(L), ok_all


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", default=os.path.join(HERE, "FromPandemicCode", "Tables"))
    ap.add_argument("--scope", default="both", choices=("baseline", "hsonly", "baseline_ew", "baseline_wo", "both", "all"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    scopes = ["baseline", "hsonly"] if a.scope == "both" else (["baseline", "hsonly", "baseline_ew", "baseline_wo"] if a.scope == "all" else [a.scope])
    parts = ["# Income-strata shuffle: N-ladder certification report", "",
             "Paired difference pstratM − plainM (relative, %) per rung; both arms Madow rounding, whole-cell seeds 0–2, CRN-paired. "
             "Standard: the difference vanishes with N (inside 2 paired SE at the top rung, or below the 0.05 % reporting-precision floor; and not growing along the ladder). Adopts nothing.", ""]
    oks = []
    for s in scopes:
        txt, ok = report(a.tables, s); parts.append(txt); oks.append(ok)
    out = "\n".join(parts)
    print(out)
    if a.out:
        with open(a.out, "w") as f:
            f.write(out)
    return 0 if all(oks) else 3


if __name__ == "__main__":
    sys.exit(main())
