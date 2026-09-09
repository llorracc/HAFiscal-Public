#!/usr/bin/env python3
"""eta — expected walls per compute class per host from the launcher stamps (infrastructure plan B4, 2026-08-28).

Reads every rerun_logs/**/*.out (dell) plus the gathered m5logs/ccarroll_logs/xub_logs directories, collects the stamps
    === 5a[tag] end rc=0 wall=NNmin ...        -> class 5a
    === w6[tag] seed K end rc=0 wall=NNmin ... -> class battery (one seed)
    === S2[tag] end wall=NNmin                 -> class step2
and reports the median (and the range) per class per host, then an ETA for a plan.
Usage: eta.py [--host jhu-dell] [--plan 5a:2,battery:6,step2:1] [--since YYYYMMDD]
The ETA assumes the host's runq capacity (runq.CAPACITY) and single-arm walls -- co-running arms are what runq prevents.
"""
import argparse, glob, os, re, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import runq

STAMP = re.compile(r"=== (5a|w6|S2)\[[^\]]*\](?: seed \d+)? end(?: rc=(\d+))? wall=(\d+)min")
CLASS = {"5a": "5a", "w6": "battery", "S2": "step2"}


def host_of(path):
    if "/m5logs/" in path: return "ccarroll-m5"
    if "/ccarroll_logs/" in path: return "ccarroll"
    if "/xub_logs/" in path: return "xubuntark"
    return runq.host_name()


def collect(root, since=None):
    walls = {}
    for f in glob.glob(os.path.join(root, "rerun_logs", "**", "*.out"), recursive=True):
        if since and os.path.basename(os.path.dirname(f)) < since and not os.path.basename(f).startswith("p"):
            continue
        h = host_of(f)
        for line in open(f, errors="replace"):
            m = STAMP.search(line)
            if m and (m.group(2) in (None, "0")):
                walls.setdefault((h, CLASS[m.group(1)]), []).append(int(m.group(3)))
    return walls


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--host", default=None); ap.add_argument("--plan", default=None); ap.add_argument("--since", default=None)
    a = ap.parse_args(); host = runq.host_name(a.host)
    walls = collect(HERE, a.since)
    print(f"{'host':12s} {'class':8s} {'n':>4s} {'median':>7s} {'min':>5s} {'max':>5s}   (minutes, successful runs)")
    for (h, c), xs in sorted(walls.items()):
        print(f"{h:12s} {c:8s} {len(xs):4d} {statistics.median(xs):7.0f} {min(xs):5d} {max(xs):5d}")
    if a.plan:
        cap = runq.CAPACITY.get(host, runq.DEFAULT); total = 0.0; parts = []
        for item in a.plan.split(","):
            c, n = item.split(":"); n = int(n); c2, slots = runq.resolve(host, c)
            xs = walls.get((host, c)) or walls.get((host, c2))
            if not xs: parts.append(f"{c}: no stamps on {host}"); continue
            med = statistics.median(xs); t = med * n / slots; total += t; parts.append(f"{n} x {c} @ {med:.0f} min / {slots} slot(s) = {t:.0f} min")
        print(f"ETA on {host}: {total/60:.1f} h  [" + "; ".join(parts) + "]  (classes assumed sequential; batteries may overlap a 5a)")


if __name__ == "__main__":
    main()
