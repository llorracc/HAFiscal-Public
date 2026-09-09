#!/usr/bin/env python
"""Equivalence-gate comparator for Step-4 artifacts.

Usage:
    python gate_compare.py jacs A.obj B.obj    # HA_Fiscal_Jacs objs
    python gate_compare.py mult A.obj B.obj    # multiplier pickles

Prints per-leaf max|diff|, the global max, byte-equality of the pickle
files, and (for jacs) the steady-state keys. Exit code 0 always — the
caller judges the printed numbers against the gate's tolerance.
"""
import hashlib
import pickle
import sys

import numpy as np


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def compare_jacs(pa, pb):
    with open(pa, 'rb') as f:
        A = pickle.load(f)
    with open(pb, 'rb') as f:
        B = pickle.load(f)
    gmax = 0.0
    for top in ('C', 'A'):
        for k in sorted(A[top]):
            d = float(np.max(np.abs(np.asarray(A[top][k]) - np.asarray(B[top][k]))))
            gmax = max(gmax, d)
            print(f"  {top}[{k:>10s}]  max|diff| = {d:.3e}")
    for top in ('C_by_educ', 'A_by_educ'):
        for educ in sorted(A[top]):
            for k in sorted(A[top][educ]):
                d = float(np.max(np.abs(np.asarray(A[top][educ][k]) - np.asarray(B[top][educ][k]))))
                gmax = max(gmax, d)
    for kk in ('C_ss_weighted', 'A_ss_weighted'):
        if kk in A and kk in B:
            print(f"  {kk}: A={float(A[kk]):.10f} B={float(B[kk]):.10f} "
                  f"diff={abs(float(A[kk]) - float(B[kk])):.3e}")
        else:
            print(f"  {kk}: present A={kk in A} B={kk in B}")
    print(f"GLOBAL max leaf |diff| = {gmax:.3e}")
    print(f"BYTES equal: {_sha(pa) == _sha(pb)}")


def compare_mult(pa, pb):
    with open(pa, 'rb') as f:
        A = pickle.load(f)
    with open(pb, 'rb') as f:
        B = pickle.load(f)
    gmax = 0.0
    for k in sorted(set(A) | set(B)):
        a, b = np.asarray(A[k]), np.asarray(B[k])
        d = float(np.max(np.abs(a - b)))
        gmax = max(gmax, d)
        print(f"  {k:>15s}  peakA={float(a.max()):.6f} peakB={float(b.max()):.6f} "
              f"h0A={float(a[0]):.6f} h0B={float(b[0]):.6f} max|diff|={d:.3e}")
    print(f"GLOBAL max |diff| = {gmax:.3e}")
    print(f"BYTES equal: {_sha(pa) == _sha(pb)}")


if __name__ == "__main__":
    mode, pa, pb = sys.argv[1], sys.argv[2], sys.argv[3]
    print(f"[gate_compare:{mode}]\n  A = {pa}\n  B = {pb}")
    if mode == "jacs":
        compare_jacs(pa, pb)
    elif mode == "mult":
        compare_mult(pa, pb)
    else:
        raise SystemExit(f"unknown mode {mode!r}")
