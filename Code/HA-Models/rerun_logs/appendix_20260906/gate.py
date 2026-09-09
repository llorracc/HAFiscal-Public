#!/usr/bin/env python3
"""Did today's defaults move the ESTIMATION? Compare the re-run calibration to the snapshot.

The appendix queue re-runs Steps 5a and 5b only, on the calibrations of 2026-09-04/05, because
neither of today's corrections should reach the estimation. This measures that rather than
assuming it -- the chain-of-record `do_all` re-ran Steps 1 and 2 under the new defaults and wrote
these same files.

The FIRST version of this gate compared bytes, and went red on differences in the eleventh
significant figure. That was the wrong test and a lesson the repo has already written down
(numerical stability is judged in significant figures; byte-identity is a tripwire, not a
criterion). An optimizer's argmin is not bit-reproducible across a change in array shapes even
when the objective is economically identical -- and the chain did change shape, from seven micro
states to six. So the gate is a TOLERANCE, and it prints what it actually measured.
"""

import argparse
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_DIRS = (REPO / "Code/HA-Models/Results", REPO / "Code/HA-Models/Target_AggMPCX_LiquWealth")


def _numbers(path):
    """Every float in a calibration file, keyed by (line, field) so they line up across versions."""
    out = {}
    for i, line in enumerate(Path(path).read_text().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            d = ast.literal_eval(line)
        except (ValueError, SyntaxError):
            for j, tok in enumerate(line.replace(",", " ").split()):
                try:
                    out[(i, j)] = float(tok)
                except ValueError:
                    pass
            continue
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, (int, float)):
                    out[(i, k)] = float(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=1e-6,
                    help="max relative move allowed in any calibrated number (default 1e-6)")
    a = ap.parse_args()

    worst, worst_where, checked, missing = 0.0, None, 0, []
    for snap in sorted((HERE / "calibration_snapshot").iterdir()):
        live = next((d / snap.name for d in LIVE_DIRS if (d / snap.name).exists()), None)
        if live is None:
            missing.append(snap.name)
            continue
        before, after = _numbers(snap), _numbers(live)
        keys = sorted(set(before) & set(after), key=str)
        if set(before) != set(after):
            print(f"  STRUCTURE CHANGED in {snap.name}: fields differ, not just values")
            return 9
        file_worst = 0.0
        for k in keys:
            b, c = before[k], after[k]
            rel = 0.0 if b == c else abs(c - b) / max(abs(b), 1e-300)
            file_worst = max(file_worst, rel)
            if rel > worst:
                worst, worst_where = rel, f"{snap.name} {k}: {b!r} -> {c!r}"
        checked += len(keys)
        print(f"  {snap.name}: {len(keys)} numbers, worst relative move {file_worst:.2e}")

    if missing:
        print(f"  MISSING live counterpart for: {', '.join(missing)}")
        return 9
    print(f"\n  {checked} calibrated numbers compared; worst relative move {worst:.2e} "
          f"(tolerance {a.tol:.0e})")
    if worst_where:
        print(f"  worst: {worst_where}")
    if worst > a.tol:
        print("\n=== GATE RED: the new defaults MOVED the estimation beyond tolerance.")
        print("===           The 5a+5b-only queue is invalid; every arm needs its Step 2 back.")
        return 9
    print("\n=== GATE GREEN: the estimation is invariant to today's defaults at this tolerance,")
    print("===             so re-running Steps 5a and 5b on the existing calibrations is correct.")
    (HERE / "gate.green").write_text(f"worst relative move {worst:.3e} <= {a.tol:.0e}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
