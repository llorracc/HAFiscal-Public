#!/usr/bin/env python3
"""Timing table from the launcher stamps (owner 2026-08-27: "some measure of the difference in timing would be useful").
Parses `=== 5a[tag] start HH:MM:SS` / `=== 5a[tag] end ... HH:MM:SS` and `=== w6[tag] seed K start/end` (also the older
`multiplier[...]` / `welfare[...] seed K` spellings) from every *.out under rerun_logs/ui_ext_20260826 (dell) and its
m5logs/ ccarroll_logs/ xub_logs/ mirrors, and prints per arm: machine, 5a wall (min), battery wall per seed (min; first seed
carries the cold solves), seeds. Usage: python timing_table.py [--out FILE.md]
"""
import argparse, glob, os, re
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "rerun_logs", "ui_ext_20260826")
MACH = {"": "dell", "m5logs": "ccarroll-m5", "ccarroll_logs": "ccarroll", "xub_logs": "xubuntark"}
START = re.compile(r"^=== (?:5a\[(?P<a5>[^\]]+)\]|multiplier\[(?P<a5b>[^\]]+)\]|w6\[(?P<w>[^\]]+)\] seed (?P<k>\d+)|welfare\[(?P<wb>[^\]]+)\] seed (?P<kb>\d+)) start (?P<t>\d\d:\d\d:\d\d)")
END = re.compile(r"^=== (?:5a\[(?P<a5>[^\]]+)\]|multiplier\[(?P<a5b>[^\]]+)\]|w6\[(?P<w>[^\]]+)\] seed (?P<k>\d+)|welfare\[(?P<wb>[^\]]+)\] seed (?P<kb>\d+)) end.*?(?P<t>\d\d:\d\d:\d\d)\s*$")


def mins(t0, t1):
    a = datetime.strptime(t0, "%H:%M:%S"); b = datetime.strptime(t1, "%H:%M:%S")
    if b < a: b += timedelta(days=1)
    return (b - a).total_seconds() / 60


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=None); a = ap.parse_args()
    rows = {}   # (machine, tag) -> {"5a": min, "seeds": {k: min}}
    for sub, mach in MACH.items():
        for f in sorted(glob.glob(os.path.join(LOG, sub, "*.out"))):
            base = os.path.basename(f)   # mirrors copied into the dell dir keep their machine in the name
            mach_f = "ccarroll-m5" if base.endswith("_m5.out") else "xubuntark" if "_xub" in base else "ccarroll" if "_ccarroll" in base else mach
            open_starts = {}
            for line in open(f, errors="replace"):
                m = START.match(line)
                if m:
                    tag = m["a5"] or m["a5b"] or m["w"] or m["wb"]; k = m["k"] or m["kb"]
                    open_starts[(tag, k)] = m["t"]; continue
                m = END.match(line)
                if m:
                    tag = m["a5"] or m["a5b"] or m["w"] or m["wb"]; k = m["k"] or m["kb"]
                    t0 = open_starts.pop((tag, k), None)
                    if t0 is None: continue
                    r = rows.setdefault((mach_f, tag), {"5a": None, "seeds": {}})
                    if k is None: r["5a"] = mins(t0, m["t"])
                    else: r["seeds"][int(k)] = mins(t0, m["t"])
    L = ["| machine | arm | 5a wall (min) | battery per seed (min), first seed cold | seeds |", "|---|---|---|---|---|"]
    for (mach, tag), r in sorted(rows.items()):
        seeds = r["seeds"]; s = ", ".join(f"{seeds[k]:.0f}" for k in sorted(seeds))
        w5 = "—" if r["5a"] is None else f"{r['5a']:.0f}"
        L.append(f"| {mach} | {tag} | {w5} | {s or '—'} | {len(seeds)} |")
    text = "\n".join(L) + "\n"
    if a.out: open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
