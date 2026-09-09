#!/usr/bin/env python3
"""Granularity ladder for the income-strata shuffle: does the residual scale with STRATUM SIZE?

Background (2026-09-08).  The N-ladder's split verdict was traced to a confound, not to a carrier:
`strata_nladder_report.py --scope all` shows the same ~+0.7 % UI residual on the equal-weight panel
as on the weighted-tail one, and with the battery's own AD loop as under sharing, so neither the
sampler nor the sharing carries it.  The only uncontrolled axis was PER-TYPE panel size -- HS_Only
puts its whole N in one agent type (96,000 at the top rung) while Baseline splits N over 21 types and
gives each dropout cohort 1.33 % of it (1,329 at N=100,000).

Mechanism under test.  The shuffle assigns transitions per source micro state per agent type
(``AggFiscalModel.py`` ``for jj in range(J)``, J = 7), so a dropout cohort's unemployed households sit
TENS per source state; income quintiles of those are 2-4 households, the regime ``_madow_round``'s own
docstring flags.  If that is the mechanism, the residual must scale with the number of strata at fixed
population, fixed panel and fixed N.

This script reads the arms of one granularity tag and reports each strata arm's CRN-paired difference
against the plain arm, with the per-seed scatter.  It adopts nothing.

Usage: strata_granularity_report.py [--tables DIR] [--tag nladderG] [--param Baseline] [--n 40000]
                                    [--arms plainM,p2M,p5M,p10M] [--out REPORT.md]
"""
import argparse, os, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import welfare_band_compare as wbc  # noqa: E402

CELLS = ["check_rec", "ui_rec", "taxcut_rec", "check_rec_AD", "ui_rec_AD", "taxcut_rec_AD"]
PRECISION_FLOOR = 5e-4          # same reporting-precision floor as the N-ladder report
# number of income strata each arm asks for (p:<n>); the plain arm is the unstratified control
NSTRATA = {"plainM": 1, "p2M": 2, "p5M": 5, "p10M": 10}


def band(tables, param, tag, arm, n):
    return wbc.load_band(os.path.join(tables, f"{param}_{tag}_{arm}_N{n}_seed*"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", default=os.path.join(HERE, "FromPandemicCode", "Tables"))
    ap.add_argument("--tag", default="nladderG")
    ap.add_argument("--param", default="Baseline")
    ap.add_argument("--n", type=int, default=40000)
    ap.add_argument("--arms", default="plainM,p2M,p5M,p10M")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    arms = [s.strip() for s in a.arms.split(",") if s.strip()]
    base_arm, strat_arms = arms[0], arms[1:]
    A = band(a.tables, a.param, a.tag, base_arm, a.n)

    L = ["# Income-strata shuffle: granularity ladder", "",
         f"{a.param}, N = {a.n:,}, tag `{a.tag}`. Each arm's CRN-paired difference against `{base_arm}` "
         "(the unstratified control), all arms Madow rounding, same population, same panel, same N. "
         "Mechanism under test: the residual comes from income strata inside source states that hold only "
         "tens of households, so it must scale with the number of strata. Adopts nothing.", "",
         "**Read p:2 vs p:5 first.** `_mrkv_strata_ids._bins` stops stratifying a source state entirely below "
         "`len < 2n` households, so p:10 carries TWO opposing effects -- finer strata where it applies, and no "
         "stratification at all below 20 households -- and can move toward the plain arm for reasons that are not "
         "granularity. p:2 (guard at 4) vs p:5 (guard at 10) is the clean contrast.", "",
         "| arm | strata | cell | paired diff | paired SE | z | S | per-seed diffs (%) |",
         "|---|---|---|---|---|---|---|---|"]
    table = {}
    for arm in strat_arms:
        B = band(a.tables, a.param, a.tag, arm, a.n)
        common = sorted(set(A) & set(B))
        if len(common) < 2:
            L.append(f"| {arm} | {NSTRATA.get(arm,'?')} | — | (only {len(common)} common seeds) | | | {len(common)} | |")
            continue
        rows = {r["cell"]: r for r in wbc.compare_bands(A, B, CELLS)}
        for c in CELLS:
            r = rows.get(c)
            if not r or r.get("pairing") == "n/a":
                continue
            z = abs(r["diff"]) / r["paired_se"] if r["paired_se"] > 0 else float("inf")
            per = [100 * (B[k][c] - A[k][c]) / abs(A[k][c]) for k in common]
            L.append(f"| {arm} | {NSTRATA.get(arm,'?')} | {c} | {100*r['diff']:+.2f} % | {100*r['paired_se']:.2f} % | "
                     f"{z:.1f} | {r['n']} | " + " ".join(f"{v:+.2f}" for v in per) + " |")
            table.setdefault(c, []).append((NSTRATA.get(arm, 0), arm, r["diff"], r["paired_se"], z))

    L += ["", "### Verdict: is |residual| monotone in the number of strata?", ""]
    for c in ("ui_rec", "ui_rec_AD"):
        seq = sorted(table.get(c, []))
        if len(seq) < 2:
            continue
        d = [abs(x[2]) for x in seq]
        mono = all(d[i] <= d[i + 1] + 1e-12 for i in range(len(d) - 1))
        span = (max(d) - min(d))
        resolved = span > 2.0 * max(x[3] for x in seq)
        L.append(f"- **{c}**: " + " → ".join(f"{a_} {100*x:+.2f} %" for (_, a_, x, _, _) in
                                             [(s[0], s[1], s[2], s[3], s[4]) for s in seq]))
        L.append(f"  - monotone in strata count: **{'YES' if mono else 'NO'}**; spread "
                 f"{100*span:.2f} pp, {'RESOLVED' if resolved else 'NOT resolved'} against the paired SEs "
                 f"(max {100*max(x[3] for x in seq):.2f} %)")
        if mono and resolved:
            L.append("  - ⇒ consistent with the granularity mechanism: coarser strata, smaller residual.")
        elif not resolved:
            L.append("  - ⇒ arms sit on top of each other: granularity is NOT the carrier; next axis is the "
                     "cohort panel itself (`HAFISCAL_AGENTCOUNT_D`).")
        else:
            L.append("  - ⇒ resolved but NOT monotone: the residual depends on strata in some other way; "
                     "report the shape, do not fit a story to it.")
    L.append("")
    for c in ("check_rec", "taxcut_rec", "check_rec_AD", "taxcut_rec_AD"):
        seq = sorted(table.get(c, []))
        if seq and all(abs(x[2]) <= PRECISION_FLOOR for x in seq):
            L.append(f"- {c}: every arm inside the 0.05 % reporting-precision floor.")
    out = "\n".join(L)
    print(out)
    if a.out:
        with open(a.out, "w") as f:
            f.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
