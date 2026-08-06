#!/usr/bin/env python
"""Self-test for the T1c comparison gate (``t1c_compare_decay_forms.py``).

Validates the *FAIL* direction of the gate (the exp-vs-exp self-compare only ever
proved it will not false-PASS). Builds perturbed COPIES of the finished exp leg in
a fresh temp dir (the real ``Figures/Baseline_pfexp`` is NEVER modified) and drives
the harness as a subprocess, asserting exit code + the key output lines for:

  1. Multiplier FAIL       : Check-AD[-1] += 0.01           -> FAIL / exit 1
  2. Boundary (Check)      : +0.0005 -> PASS ; +0.0015 -> FAIL  (gate at 0.001)
     Boundary (TaxCut)     : +0.0005 -> PASS ; +0.0015 -> FAIL
  3. TranMatrix perturb    : move mass in one interior column of ONE type's
                             tm_data.TranMatrix -> that type surfaces with
                             nnz(D)>0 / max|Dp|>0 in the decomposition, others 0
                             (verdict stays PASS: multiplier gate is authoritative,
                             TranMatrix is diagnostic-only -- BY DESIGN)
  4. Non-final quarter     : Check-AD[10] += 0.01 (leave [-1]) -> headline PASS but
                             the whole-array max|Delta| WARNING fires

No heavy compute: only pickle-load / copy / perturb + the (fast, ~4s) harness runs.

Run:
    PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
    cd /home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models
    $PY t1c_compare_gate_selftest.py
Exit 0 = all validations passed; 1 = at least one validation failed.
"""
import os
import pickle
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import scipy.sparse as sp

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "t1c_compare_decay_forms.py")
REF = os.path.join(HERE, "FromPandemicCode", "Figures", "Baseline_pfexp")
MULT_FILE = "C_Multiplier_Baseline_Results.csv"
BASE_FILE = "base_results.csv"

# be a good citizen: single-threaded BLAS so we do not fight a running sim
_ENV = dict(os.environ)
_ENV.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")


# --------------------------------------------------------------------------
# perturbation helpers (operate ONLY on copies)
# --------------------------------------------------------------------------
def _copy_ref(dst):
    shutil.copytree(REF, dst)
    return dst


def perturb_multiplier(dst_dir, key, index, delta):
    """Copy the ref, then add ``delta`` to ``key[index]`` of the multiplier pickle."""
    _copy_ref(dst_dir)
    p = os.path.join(dst_dir, MULT_FILE)
    with open(p, "rb") as f:
        obj = pickle.load(f)
    arr = np.asarray(obj[key], dtype=float).copy()
    arr[index] = arr[index] + delta
    obj[key] = arr
    with open(p, "wb") as f:
        pickle.dump(obj, f)
    return dst_dir


def perturb_tranmatrix(dst_dir, type_idx, eps):
    """Copy the ref, then move ``eps`` mass between two rows of one interior column
    of ``_type_results[type_idx].tm_data.TranMatrix`` (stays column-stochastic)."""
    _copy_ref(dst_dir)
    p = os.path.join(dst_dir, BASE_FILE)
    with open(p, "rb") as f:
        obj = pickle.load(f)
    tm = obj["_type_results"][type_idx]["tm_data"]["TranMatrix"]
    A = tm.toarray()
    n = A.shape[0]
    col = n // 2                       # an interior column
    rows = np.where(A[:, col] > 0)[0]  # its nonzero rows
    assert rows.size >= 2, "need a column with >=2 nonzeros for a mass-preserving move"
    r_lo, r_hi = int(rows[0]), int(rows[-1])
    # move eps from r_lo to r_hi (column sum preserved -> still stochastic)
    A[r_lo, col] -= eps
    A[r_hi, col] += eps
    obj["_type_results"][type_idx]["tm_data"]["TranMatrix"] = sp.csc_matrix(A)
    with open(p, "wb") as f:
        pickle.dump(obj, f)
    return dst_dir, col, (r_lo, r_hi)


# --------------------------------------------------------------------------
# harness driver + output parsers
# --------------------------------------------------------------------------
def run_harness(dir_a, dir_b):
    """Run the harness; return (returncode, stdout+stderr)."""
    proc = subprocess.run(
        [sys.executable, HARNESS, dir_a, dir_b],
        capture_output=True, text=True, env=_ENV, cwd=HERE)
    return proc.returncode, proc.stdout + proc.stderr


def parse_verdict(out):
    m = re.search(r"^VERDICT:\s+(\w+)", out, re.M)
    return m.group(1) if m else None


def parse_headline_worst(out):
    m = re.search(r"headline worst last-element \|Delta multiplier\| = ([0-9.eE+-]+)", out)
    return float(m.group(1)) if m else None


def parse_key_last_abs(out, key):
    """Return the per-key last-element |Delta| the harness printed for ``key``."""
    m = re.search(re.escape(key) + r"\s+last:.*?\|Delta\|=([0-9.eE+-]+)", out)
    return float(m.group(1)) if m else None


def parse_key_full_max(out, key):
    m = re.search(re.escape(key) + r"\s+last:.*?full-array max\|Delta\|=([0-9.eE+-]+)", out)
    return float(m.group(1)) if m else None


def parse_warning_fullarr(out):
    m = re.search(r"WARNING: full-array max\|Delta\| = ([0-9.eE+-]+)", out)
    return float(m.group(1)) if m else None


def parse_tranmatrix_rows(out):
    """Return {type_idx: (nnz, max_dp)} from the decomposition table."""
    rows = {}
    # columns: type A_nrm nnz(D) max|Dp| statmass@D max|Dpi|
    for m in re.finditer(
            r"^\s*(\d+)\s+([0-9.eE+-]+)\s+(\d+)\s+([0-9.eE+-]+)\s+"
            r"([0-9.eE+-]+)\s+([0-9.eE+-]+)", out, re.M):
        rows[int(m.group(1))] = (int(m.group(3)), float(m.group(4)))
    return rows


# --------------------------------------------------------------------------
# assertion runner
# --------------------------------------------------------------------------
_RESULTS = []


def check(name, cond, detail=""):
    _RESULTS.append((name, bool(cond), detail))
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f"  -- {detail}" if detail else ""))
    return cond


def close(a, b, rtol=1e-6, atol=1e-9):
    return a is not None and abs(a - b) <= atol + rtol * abs(b)


def main():
    if not os.path.isdir(REF):
        print("REF dir missing:", REF)
        return 2
    tmproot = tempfile.mkdtemp(prefix="t1c_selftest_")
    print("temp root:", tmproot)
    print("reference (read-only):", REF)
    try:
        # ---- Test 1: multiplier FAIL (Check-AD[-1] += 0.01) ----
        print("\n=== Test 1: Multiplier FAIL (Check-AD[-1] += 0.01) ===")
        d = perturb_multiplier(os.path.join(tmproot, "t1"),
                               "C_Multiplier_Rec_Check_AD", -1, 0.01)
        rc, out = run_harness(REF, d)
        check("T1 exit code == 1 (FAIL)", rc == 1, f"rc={rc}")
        check("T1 verdict == FAIL", parse_verdict(out) == "FAIL")
        check("T1 Check |Delta| ~ 0.01",
              close(parse_key_last_abs(out, "C_Multiplier_Rec_Check_AD"), 0.01, rtol=1e-3),
              f"|Delta|={parse_key_last_abs(out, 'C_Multiplier_Rec_Check_AD')}")
        check("T1 TaxCut |Delta| ~ 0 (unchanged)",
              close(parse_key_last_abs(out, "C_Multiplier_Rec_TaxCut_AD"), 0.0, atol=1e-12),
              f"|Delta|={parse_key_last_abs(out, 'C_Multiplier_Rec_TaxCut_AD')}")
        check("T1 headline worst ~ 0.01",
              close(parse_headline_worst(out), 0.01, rtol=1e-3),
              f"headline={parse_headline_worst(out)}")

        # ---- Test 2: boundary (Check & TaxCut, +0.0005 PASS / +0.0015 FAIL) ----
        print("\n=== Test 2: Boundary at gate 0.001 ===")
        for key, short in [("C_Multiplier_Rec_Check_AD", "Check"),
                           ("C_Multiplier_Rec_TaxCut_AD", "TaxCut")]:
            d = perturb_multiplier(os.path.join(tmproot, f"t2_{short}_under"),
                                   key, -1, 0.0005)
            rc, out = run_harness(REF, d)
            check(f"T2 {short} +0.0005 -> PASS (under gate)",
                  rc == 0 and parse_verdict(out) == "PASS",
                  f"rc={rc} headline={parse_headline_worst(out)}")
            d = perturb_multiplier(os.path.join(tmproot, f"t2_{short}_over"),
                                   key, -1, 0.0015)
            rc, out = run_harness(REF, d)
            check(f"T2 {short} +0.0015 -> FAIL (over gate)",
                  rc == 1 and parse_verdict(out) == "FAIL",
                  f"rc={rc} headline={parse_headline_worst(out)}")

        # ---- Test 3: TranMatrix perturbation surfaces the changed type ----
        print("\n=== Test 3: TranMatrix perturbation (type 6, one interior column) ===")
        PT = 6
        d, col, (rlo, rhi) = perturb_tranmatrix(
            os.path.join(tmproot, "t3"), PT, 0.01)
        rc, out = run_harness(REF, d)
        rows = parse_tranmatrix_rows(out)
        pt_nnz, pt_dp = rows.get(PT, (None, None))
        check(f"T3 type {PT} nnz(D) > 0", pt_nnz is not None and pt_nnz > 0,
              f"nnz={pt_nnz} (col {col}, rows {rlo}/{rhi})")
        check(f"T3 type {PT} max|Dp| ~ 0.01", close(pt_dp, 0.01, rtol=1e-3),
              f"max|Dp|={pt_dp}")
        others_zero = all(v[0] == 0 for k, v in rows.items() if k != PT)
        check("T3 all OTHER types nnz(D) == 0 (change localized)", others_zero,
              f"nonzero others={[k for k,v in rows.items() if k!=PT and v[0]!=0]}")
        # multiplier gate untouched -> verdict PASS BY DESIGN (diagnostic-only)
        check("T3 verdict PASS (multiplier gate authoritative; TranMatrix diagnostic)",
              rc == 0 and parse_verdict(out) == "PASS", f"rc={rc}")

        # ---- Test 4: non-final quarter bump -> headline PASS + WARNING ----
        print("\n=== Test 4: Non-final quarter (Check-AD[10] += 0.01) ===")
        d = perturb_multiplier(os.path.join(tmproot, "t4"),
                               "C_Multiplier_Rec_Check_AD", 10, 0.01)
        rc, out = run_harness(REF, d)
        check("T4 exit code == 0 (headline PASS)", rc == 0, f"rc={rc}")
        check("T4 verdict == PASS", parse_verdict(out) == "PASS")
        check("T4 Check last |Delta| ~ 0 (headline keys on [-1])",
              close(parse_key_last_abs(out, "C_Multiplier_Rec_Check_AD"), 0.0, atol=1e-12),
              f"|Delta|={parse_key_last_abs(out, 'C_Multiplier_Rec_Check_AD')}")
        check("T4 Check full-array max|Delta| ~ 0.01",
              close(parse_key_full_max(out, "C_Multiplier_Rec_Check_AD"), 0.01, rtol=1e-3),
              f"full={parse_key_full_max(out, 'C_Multiplier_Rec_Check_AD')}")
        check("T4 WARNING (non-final quarter) fired ~ 0.01",
              close(parse_warning_fullarr(out), 0.01, rtol=1e-3),
              f"warn={parse_warning_fullarr(out)}")

        # ---- summary ----
        npass = sum(1 for _, ok, _ in _RESULTS if ok)
        ntot = len(_RESULTS)
        print("\n" + "=" * 60)
        print(f"SELF-TEST SUMMARY: {npass}/{ntot} validations passed")
        print("=" * 60)
        return 0 if npass == ntot else 1
    finally:
        shutil.rmtree(tmproot, ignore_errors=True)
        print("cleaned temp root")


if __name__ == "__main__":
    sys.exit(main())
