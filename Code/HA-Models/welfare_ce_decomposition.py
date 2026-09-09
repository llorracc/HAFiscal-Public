#!/usr/bin/env python3
"""Split the appendix's 𝒞 change into the MEASURE fix and the MODEL change.

The published online-appendix 𝒞 tables and the re-issued ones differ enormously -- the
Baseline stimulus-check cell moves 0.011 -> 1.273 basis points -- and the move is not a
common factor: the UI-to-check ratio falls from 46 to 2. Two changes are confounded there:

  MEASURE  BUG-082. The published 𝒞 divided the utility change by a log-utility normalizer
           W_c = PDV(1)·N. At CRRA = 2 that divisor is 12.06x too large, AND it leaves the
           gain carrying units of 1/c while the cost share it is netted against is
           dimensionless -- so the error is not a common scale factor and it does not
           preserve ratios between policies.
  MODEL    the revised model: no age cap, growth rescaled by lambda = 0.44, and the welfare
           bug fixes (BUG-090 unemployed permanent shocks, BUG-091 the tax-cut horizon).

welfare_ce.py implements both formulas (HAFISCAL_WELFARE_CE_MODE = crra | log_legacy), and
compute_welfare_ce_table() reads its inputs from the battery's stored scenario pickles, so
this is post-processing -- no solve, no simulation. Per arm it reports

  legacy   𝒞 on THIS model under the PUBLISHED formula  -> vs published isolates the MODEL
  crra     𝒞 on THIS model under the CORRECTED formula  -> vs legacy   isolates the MEASURE

and re-derives the shipped welfare4_candidate.tex as a self-check: the crra leg must equal
it, otherwise this harness is wrong rather than the economics.

Usage: welfare_ce_decomposition.py --out-root DIR [--arms A,B,...] [--seed K] [--json FILE]
"""
from __future__ import annotations

import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FPC = os.path.join(HERE, "FromPandemicCode")
for p in (HERE, FPC):
    if p not in sys.path:
        sys.path.insert(0, p)

CELLS = ("check_C_rec", "ui_C_rec", "taxcut_C_rec",
         "check_C_rec_AD", "ui_C_rec_AD", "taxcut_C_rec_AD")


def ce_for(out_dir, mode):
    """𝒞 (basis points) for one arm's stored pickles under one measure."""
    os.environ["HAFISCAL_WELFARE_CE_MODE"] = mode
    import importlib
    import welfare_ce
    importlib.reload(welfare_ce)                 # re-read the env at module scope
    import run_welfare6_parallel as rw
    importlib.reload(rw)
    _, loaded = rw.compute_welfare6_table(out_dir)
    base = loaded["base"]
    ce = rw.compute_welfare_ce_table(loaded, base["act_T"], base["Rfree"], base["CRRA"])
    return {k: v * 1e4 for k, v in ce.items()}


def shipped(table_dir):
    """The 𝒞 row actually shipped, parsed back from welfare4_candidate.tex."""
    import re
    p = os.path.join(table_dir, "welfare4_candidate.tex")
    if not os.path.exists(p):
        return None
    txt = open(p).read()
    out = {}
    for rx, keys in ((r"\\mathcal\{C\}\(Rec,\\text\{policy\}\)\$?\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)",
                      ("check_C_rec", "ui_C_rec", "taxcut_C_rec")),
                     (r"\\mathcal\{C\}\(Rec, AD,\\text\{policy\}\)\$?\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)\s*&\s*([-\d.]+)",
                      ("check_C_rec_AD", "ui_C_rec_AD", "taxcut_C_rec_AD"))):
        m = re.search(rx, txt)
        if m:
            out.update(dict(zip(keys, (float(x) for x in m.groups()))))
    return out or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=FPC, help="dir holding welfare6_scenario_results_*")
    ap.add_argument("--tables-root", default=os.path.join(FPC, "Tables"))
    ap.add_argument("--arms", default="Baseline,Rspell_4,ADElas,CRRA3,Splurge0,Baseline_uiB")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    res = {}
    for arm in [x for x in a.arms.split(",") if x]:
        tag = arm if a.seed or arm != "Baseline" else arm      # dirs are <arm>_seed<K>
        od = os.path.join(a.out_root, f"welfare6_scenario_results_{tag}_seed{a.seed}")
        td = os.path.join(a.tables_root, f"{tag}_seed{a.seed}")
        if not os.path.isdir(od):
            print(f"  {arm:16s} SKIP (no {os.path.basename(od)})"); continue
        row = {"legacy": ce_for(od, "log_legacy"), "crra": ce_for(od, "crra"),
               "shipped": shipped(td)}
        res[arm] = row
        sh, cr = row["shipped"], row["crra"]
        chk = "n/a"
        if sh:
            worst = max(abs(cr[k] - sh[k]) for k in CELLS if k in sh)
            chk = f"max|crra-shipped|={worst:.4f}bp" + ("  OK" if worst < 5e-3 else "  MISMATCH")
        print(f"  {arm:16s} {chk}")
        for k in CELLS:
            print(f"      {k:18s} legacy={row['legacy'][k]:10.4f}   crra={row['crra'][k]:10.4f}")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
        print(f"\nwritten: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
