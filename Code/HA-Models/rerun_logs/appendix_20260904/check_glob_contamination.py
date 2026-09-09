#!/usr/bin/env python3
"""Flag stale directories leaking into the appendix readers' seed globs.

The readers select welfare seed batteries by glob ("<tag>_seed*"). Anything else that
matches is silently averaged in. That bit us on 2026-09-04: park() renamed
Tables/Rspell_4_seed0 to Tables/Rspell_4_seed0_pre_lambda_20260904, which still matched,
so config_cells returned S=6 -- three fresh seeds averaged with three pre-lambda ones, and
the AD stimulus-check cell read 2.345 instead of 3.194.

Two independent tests, because either alone misses cases:
  NAME  a matched directory whose name is not exactly <tag>_seed<digits>
  AGE   a matched directory older than --since (default: this run's start). A directory can
        be named perfectly and still be last month's results -- the age test catches the
        contamination the name test cannot, and vice versa.
Also cross-checks each row's S against config_cells, so if the reader's pattern ever
diverges from the one reproduced here, the mismatch is reported rather than hidden.

Usage: check_glob_contamination.py [--since 'YYYY-MM-DD HH:MM'] [--tables DIR]
Exit 1 if anything is flagged.
"""
import argparse, datetime as dt, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import robustness_appendix_tables as rat            # noqa: E402
import waterfall_table as wt                        # noqa: E402


def rows_to_check(td):
    """(label, glob-pattern, config, policy) for every seed glob the appendix report reads."""
    out = []
    for key, (_title, rows) in rat.LABELS.items():
        for cfg, _lab in rows:
            for policy in ("window", "histB"):
                if cfg == "Baseline":
                    if policy == "window":
                        tag = "Baseline" if glob.glob(os.path.join(td, "Baseline_seed*", "welfare4_candidate.tex")) else "Baseline_uiA"
                    else:
                        tag = "Baseline_uiB"
                else:
                    tag = cfg if policy == "window" else f"{cfg}_histB"
                out.append((f"{key}/{cfg}/{policy}", tag, cfg, policy))
    for _lab, d5, wg in wt.ORDERS["ui-policy"]:
        out.append((f"ui-policy/{d5}", wg.replace("_seed*", ""), None, None))
    seen, uniq = set(), []
    for r in out:
        if r[1] not in seen:
            seen.add(r[1]); uniq.append(r)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default=os.path.join(HERE, "..", "..", "FromPandemicCode", "Tables"))
    # Default = the BUG-120/121 calibration install (e35736a3, 2026-09-03). The test is
    # "produced under the CURRENT calibration", not "produced today": the 2026-09-03 Baseline
    # batteries are current (and seed 0 was proven to reproduce byte-for-byte after the OS
    # upgrade), while anything from 2026-08-2x predates the lambda bundle and is stale.
    ap.add_argument("--since", default="2026-09-03 00:00")
    args = ap.parse_args()
    td = os.path.abspath(args.tables)
    cutoff = dt.datetime.strptime(args.since, "%Y-%m-%d %H:%M").timestamp()
    bad = 0
    print(f"tables: {td}\ncutoff: {args.since}\n")
    for label, tag, cfg, policy in rows_to_check(td):
        hits = sorted(glob.glob(os.path.join(td, f"{tag}_seed*", "welfare4_candidate.tex")))
        if not hits:
            print(f"  {label:34s} tag={tag:22s} (pending -- no seed battery)")
            continue
        flags = []
        for h in hits:
            d = os.path.basename(os.path.dirname(h))
            if not re.fullmatch(rf"{re.escape(tag)}_seed\d+", d):
                flags.append(f"NAME {d}"); bad += 1
            elif os.path.getmtime(h) < cutoff:
                age = dt.datetime.fromtimestamp(os.path.getmtime(h)).strftime("%m-%d %H:%M")
                flags.append(f"AGE  {d} ({age})"); bad += 1
        s_reader = None
        if cfg is not None:
            c = rat.config_cells(cfg, policy, td)
            s_reader = c["AD"][2] if c else 0
            if s_reader != len(hits):
                flags.append(f"PATTERN-DRIFT reader S={s_reader} vs {len(hits)} matched here"); bad += 1
        print(f"  {label:34s} tag={tag:22s} S={len(hits)}" + (f" (reader {s_reader})" if s_reader is not None else ""))
        for f in flags:
            print(f"      !! {f}")
    print(f"\n{'CLEAN' if not bad else str(bad) + ' FLAG(S)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
