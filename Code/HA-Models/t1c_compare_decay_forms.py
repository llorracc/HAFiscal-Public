#!/usr/bin/env python
"""T1c gate/decompose harness: Baseline TM-a multipliers, exp vs powerlaw PF-decay.

Compares the Step-5a Baseline TM-a multiplier outputs produced under the two
perfect-foresight decay-extrapolation forms of ``HAFISCAL_PF_DECAY_EXTRAP``:

    exp       -> Figures/Tables/Baseline_pfexp/   (legacy exponential decay)
    powerlaw  -> Figures/Tables/Baseline_pfpl/    (PowerLawDecayLinearInterp)

This is the Baseline rung of the T0->T3/T1b decay-switch cascade
(``plans/2026-07-05_powerlaw-switch-test-plan.md``); it mirrors the T1 (HS_Only)
and T1b (Reduced_Run) comparison pattern for the Baseline parametrization, whose
College GIC-cap discount-factor atom (the type with the largest ergodic wealth
tail, ``agg.A_nrm`` ~ 22) is the ONLY subpopulation that can non-vacuously feel
the tail form. See RECONCILED-002.

--------------------------------------------------------------------------------
WHAT IT DOES
--------------------------------------------------------------------------------
1. Recursively diffs EVERY numeric leaf across the result files that live in both
   Figures dirs (the ``*.csv`` files are Python PICKLES despite the extension --
   ``Simulate.py``'s ``save_as_pickle``; magic byte 0x80). Handles:
     - scipy sparse matrices (csc_matrix TranMatrix) -> ``.toarray()`` before diff
     - HARK distribution objects (``.pmv`` / ``.atoms`` arrays)
     - nested dict / list / tuple / generic-object ``__dict__``
     - NaN==NaN treated as a zero diff (e.g. the all-NaN UI multiplier column,
       the known NPV_AddInc_UI missing-implementation)
     - non-numeric leaves (str / None / bool / object-dtype arrays) are SKIPPED
   For every numeric leaf it reports both the ABSOLUTE and the RELATIVE max diff
   (relative guards against catastrophic cancellation on tiny quantities).

2. Per-type ``tm_data.TranMatrix`` decomposition (from ``base_results.csv`` ->
   ``_type_results[i]``), for each of the 21 Baseline discount-factor cohorts:
     - nnz(Delta)      : number of transition entries that differ
     - max|Delta p|    : largest single transition-probability difference
     - stat-mass-diff  : stationary mass (of the exp chain) sitting on the columns
                         that differ  -- power iteration, column-stochastic
                         (pi = T @ pi).  THIS is the number that matters: a large
                         max|Delta p| on columns carrying ~zero stationary mass
                         cannot move any aggregate.
     - max|Delta pi|   : max abs difference of the two chains' stationary dists
     - A_nrm           : the type's normalized assets (flags the GIC-cap College
                         atom = the max-A_nrm type)

3. Applies the AUTHORITATIVE owner gate |Delta| > 0.001 to the LAST-ELEMENT AD
   cumulative multiplier (the 10y-horizon headline) in
   ``C_Multiplier_Baseline_Results.csv`` -- keys ``C_Multiplier_Rec_Check_AD`` and
   ``C_Multiplier_Rec_TaxCut_AD`` (exp: 1.224638 / 1.007551). ``C_Multiplier_UI_Rec_AD``
   is all-NaN (missing NPV_AddInc_UI) and is EXCLUDED. This pickle is written at
   Output_Results.py:308, BEFORE the exp/pl legs crash at :346 (missing
   Results_HANK) -- so it exists for both legs even though ``Multiplier.tex`` (line
   482) is NEVER written and ``Tables/Baseline_pf*/`` stay empty. The tex is
   therefore treated as INFORMATIONAL ONLY and never contributes to the verdict.

4. Prints a summary table and a single PASS / FAIL verdict (multiplier gate only).

--------------------------------------------------------------------------------
HOW TO INVOKE (once Baseline_pfpl completes)
--------------------------------------------------------------------------------
    PY=/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python
    cd Code/HA-Models
    $PY t1c_compare_decay_forms.py \
        FromPandemicCode/Figures/Baseline_pfexp \
        FromPandemicCode/Figures/Baseline_pfpl

With no args it defaults to exactly those two Figures dirs. The sibling ``Tables``
dir is auto-derived by replacing ``Figures`` -> ``Tables`` in each path (override
with --tables-a / --tables-b).

SELF-COMPARE VALIDATION (mechanics check while pl is still running):
    $PY t1c_compare_decay_forms.py \
        FromPandemicCode/Figures/Baseline_pfexp \
        FromPandemicCode/Figures/Baseline_pfexp
Because dir_a == dir_b the script switches on a STRICT-ZERO assertion: every
numeric leaf diff must be exactly 0.0 and the verdict must be PASS. This proves
the pickle parser + recursive differ handle the real file formats.

--------------------------------------------------------------------------------
OUTPUT COLUMN MEANINGS
--------------------------------------------------------------------------------
Per-file leaf-diff table:
    file            result pickle basename
    fmt             detected format: 'pickle' (0x80) or 'text-csv'
    leaves          number of numeric leaves compared
    max|abs|        largest absolute diff over all numeric leaves in the file
    max|rel|        largest relative diff (|a-b| / max(|a|,|b|,eps))
    at              dotted path to the leaf attaining max|abs|
TranMatrix table:
    type            cohort index 0..20
    A_nrm           normalized assets of the cohort (max = GIC-cap College atom)
    nnz(D)          count of differing transition entries
    max|Dp|         max single transition-prob difference
    statmass@D      exp-chain stationary mass on the differing columns
    max|Dpi|        max abs diff of the two stationary distributions

--------------------------------------------------------------------------------
EXPECTED A-PRIORI RESULT
--------------------------------------------------------------------------------
PASS. From the cascade (T1b Reduced_Run: College beta=0.98 differed on ~1e4
entries at ~ALL its stationary mass, integrated effect >10 orders below gate),
the Baseline GIC-cap atom's tail mass (<= ~1e-4) times a ~1-2% cFunc delta gives
a multiplier shift on the order of ~1e-6 -- three orders of magnitude under the
0.001 gate. If the gate TRIPS, escalate to owner immediately: the 2026-07-05
flip (commit e5c0b602, RECONCILED-002) would need revisiting.
"""
import argparse
import glob as _glob
import math
import os
import pickle
import re
import sys

import numpy as np

try:  # scipy is a hard dep of this repo; guard anyway
    import scipy.sparse as _sp

    def _issparse(x):
        return _sp.issparse(x)
except Exception:  # pragma: no cover
    def _issparse(x):
        return False

GATE = 1e-3          # |Delta multiplier| gate
TOL = 0.0            # entries with |Delta| > TOL count as "differing"
_EPS = 1e-300        # relative-diff denominator floor


# ----------------------------------------------------------------------------
# file loading (pickle-despite-.csv detection)
# ----------------------------------------------------------------------------
def detect_format(path):
    """Return 'pickle' if the first byte is a pickle opcode (0x80 / proto>=2),
    else 'text-csv'."""
    with open(path, "rb") as f:
        first = f.read(1)
    return "pickle" if first[:1] == b"\x80" else "text-csv"


def load_result(path):
    """Load a result file, returning (obj, fmt). Pickle if 0x80, else text CSV."""
    fmt = detect_format(path)
    if fmt == "pickle":
        with open(path, "rb") as f:
            return pickle.load(f), fmt
    # text-csv fallback
    try:
        import pandas as pd

        return pd.read_csv(path), fmt
    except Exception:
        return np.genfromtxt(path, delimiter=",", names=True), fmt


# ----------------------------------------------------------------------------
# recursive numeric-leaf differ
# ----------------------------------------------------------------------------
def _to_dense(x):
    """csc/csr/etc sparse -> dense ndarray; pass ndarrays through."""
    if _issparse(x):
        return x.toarray()
    return x


def _num_array_diff(a, b, path, acc, skipped):
    """Diff two numeric ndarrays; append a leaf record to acc."""
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        acc.append({"path": path, "shape_mismatch": (a.shape, b.shape),
                    "n": 0, "max_abs": math.inf, "max_rel": math.inf})
        return
    if a.dtype.kind not in "fiu" or b.dtype.kind not in "fiu":
        skipped.append(path)  # non-numeric dtype
        return
    af = a.astype(float)
    bf = b.astype(float)
    both_nan = np.isnan(af) & np.isnan(bf)
    d = np.abs(af - bf)
    d = np.where(both_nan, 0.0, d)          # NaN==NaN -> 0
    # one-sided NaN stays NaN in d; surface it as inf so it is never masked
    onesided = np.isnan(d)
    d = np.where(onesided, math.inf, d)
    denom = np.maximum.reduce([np.abs(af), np.abs(bf),
                               np.full(af.shape, _EPS)])
    denom = np.where(both_nan, 1.0, denom)
    rel = np.where(onesided, math.inf, d / denom)
    n = int(a.size)
    max_abs = float(np.max(d)) if n else 0.0
    max_rel = float(np.max(rel)) if n else 0.0
    acc.append({"path": path, "n": n, "max_abs": max_abs, "max_rel": max_rel,
                "onesided_nan": int(np.count_nonzero(onesided))})


def walk(a, b, path, acc, skipped):
    """Recursively walk two objects in parallel, collecting numeric-leaf diffs."""
    # sparse -> dense
    if _issparse(a) or _issparse(b):
        _num_array_diff(_to_dense(a), _to_dense(b), path, acc, skipped)
        return
    if isinstance(a, dict) and isinstance(b, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            acc.append({"path": path, "key_mismatch": ka ^ kb,
                        "n": 0, "max_abs": math.inf, "max_rel": math.inf})
        for k in ka & kb:
            walk(a[k], b[k], f"{path}.{k}", acc, skipped)
        return
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            acc.append({"path": path, "len_mismatch": (len(a), len(b)),
                        "n": 0, "max_abs": math.inf, "max_rel": math.inf})
            return
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", acc, skipped)
        return
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        aa = np.asarray(a)
        if aa.dtype.kind in "fiu":
            _num_array_diff(a, b, path, acc, skipped)
        elif aa.dtype.kind == "O":  # object array -> recurse element-wise
            bb = np.asarray(b)
            if aa.shape != bb.shape:
                acc.append({"path": path, "shape_mismatch": (aa.shape, bb.shape),
                            "n": 0, "max_abs": math.inf, "max_rel": math.inf})
                return
            for idx, (x, y) in enumerate(zip(aa.ravel(), bb.ravel())):
                walk(x, y, f"{path}[{idx}]", acc, skipped)
        else:
            skipped.append(path)
        return
    # HARK distribution
    if hasattr(a, "pmv") and hasattr(a, "atoms") and hasattr(b, "pmv"):
        walk(np.asarray(a.pmv), np.asarray(b.pmv), f"{path}.pmv", acc, skipped)
        walk(np.asarray(a.atoms), np.asarray(b.atoms), f"{path}.atoms",
             acc, skipped)
        return
    # numeric scalar
    if isinstance(a, (int, float, np.integer, np.floating)) and \
            isinstance(b, (int, float, np.integer, np.floating)):
        af, bf = float(a), float(b)
        if math.isnan(af) and math.isnan(bf):
            acc.append({"path": path, "n": 1, "max_abs": 0.0, "max_rel": 0.0})
        else:
            d = abs(af - bf)
            denom = max(abs(af), abs(bf), _EPS)
            acc.append({"path": path, "n": 1, "max_abs": d,
                        "max_rel": d / denom})
        return
    # generic object with __dict__: recurse over comparable members
    da, db = getattr(a, "__dict__", None), getattr(b, "__dict__", None)
    if da is not None and db is not None:
        for k in set(da) & set(db):
            if isinstance(da[k], (np.ndarray, int, float, np.integer,
                                  np.floating, list, tuple, dict)) or \
                    _issparse(da[k]):
                walk(da[k], db[k], f"{path}.{k}", acc, skipped)
        return
    # everything else (str, bool, None, bytes, ...) -> non-numeric, skip
    skipped.append(path)


# ----------------------------------------------------------------------------
# TranMatrix decomposition
# ----------------------------------------------------------------------------
def stationary_col_stochastic(A, max_iter=5000, tol=1e-14):
    """Stationary distribution of a column-stochastic matrix: pi = A @ pi."""
    n = A.shape[0]
    pi = np.full(n, 1.0 / n)
    for _ in range(max_iter):
        nxt = A @ pi
        s = nxt.sum()
        if s > 0:
            nxt = nxt / s
        if np.max(np.abs(nxt - pi)) < tol:
            return nxt
        pi = nxt
    return pi


def decompose_tranmatrix(res_a, res_b):
    """Per-type TranMatrix decomposition. Returns list of row dicts."""
    ta = res_a.get("_type_results")
    tb = res_b.get("_type_results")
    if ta is None or tb is None:
        return None
    rows = []
    for i, (da, db) in enumerate(zip(ta, tb)):
        tm_a = da["tm_data"]["TranMatrix"]
        tm_b = db["tm_data"]["TranMatrix"]
        A = _to_dense(tm_a).astype(float)
        B = _to_dense(tm_b).astype(float)
        D = np.abs(A - B)
        nnz = int(np.count_nonzero(D > TOL))
        max_dp = float(D.max()) if D.size else 0.0
        # columns that differ
        diff_cols = np.where((D > TOL).any(axis=0))[0]
        pi_a = stationary_col_stochastic(A)
        statmass = float(pi_a[diff_cols].sum()) if diff_cols.size else 0.0
        if not np.allclose(A, B):
            pi_b = stationary_col_stochastic(B)
            max_dpi = float(np.max(np.abs(pi_a - pi_b)))
        else:
            max_dpi = 0.0
        rows.append({
            "type": i,
            "A_nrm": float(da["agg"]["A_nrm"]),
            "nnz": nnz,
            "max_dp": max_dp,
            "statmass": statmass,
            "max_dpi": max_dpi,
        })
    return rows


# ----------------------------------------------------------------------------
# multiplier gate
# ----------------------------------------------------------------------------
_MULT_FILE = "C_Multiplier_Baseline_Results.csv"


def _resolve_mult_file(dir_a, dir_b):
    """Resolve the multiplier pickle name present in BOTH dirs.

    Historically hardcoded to the Baseline name; parametrization-suffixed runs
    (e.g. ``C_Multiplier_Reduced_Run_Results.csv`` from the 2026-07-22 local2
    A/B legs) carry the same keys, so match ``C_Multiplier_*_Results.csv`` and
    prefer the Baseline name if several are shared.
    """
    shared = sorted(
        {os.path.basename(f)
         for f in _glob.glob(os.path.join(dir_a, "C_Multiplier_*_Results.csv"))}
        & {os.path.basename(f)
           for f in _glob.glob(os.path.join(dir_b, "C_Multiplier_*_Results.csv"))})
    if _MULT_FILE in shared or not shared:
        return _MULT_FILE
    return shared[0]


_SCENARIO_FILES = ("recession_results.csv", "recession_results_AD.csv",
                   "recessionCheck_results.csv", "recessionCheck_results_AD.csv",
                   "recessionTaxCut_results.csv", "recessionTaxCut_results_AD.csv")


def _mult_from_scenarios(d):
    """Rebuild the headline AD cumulative multipliers from the scenario pickles.

    ``Output_Results.py`` writes the C_Multiplier pickle only under
    ``Parametrization=='Baseline'``; non-Baseline runs (e.g. the Reduced_Run
    local2 A/B legs, 2026-07-22) still carry every input. Mirrors the
    Output_Results computation exactly: ``NPV_AddInc_<pol> = ΔNPV_AggIncome``
    over the no-AD pair; ``C_Multiplier_Rec_<pol>_AD = ΔNPV_AggCons`` over the
    AD pair ``/ NPV_AddInc_<pol>[-1]``. UI is omitted (all-NaN in the pickle —
    the known NPV_AddInc_UI missing-implementation — hence excluded from the
    gate either way).
    """
    objs = {}
    for fn in _SCENARIO_FILES:
        path = os.path.join(d, fn)
        if not os.path.exists(path):
            return None
        objs[fn], _ = load_result(path)
    out = {}
    for pol, stem in (("Check", "recessionCheck"), ("TaxCut", "recessionTaxCut")):
        add_inc = (np.asarray(objs[stem + "_results.csv"]["NPV_AggIncome"], float)
                   - np.asarray(objs["recession_results.csv"]["NPV_AggIncome"], float))
        add_cons_ad = (np.asarray(objs[stem + "_results_AD.csv"]["NPV_AggCons"], float)
                       - np.asarray(objs["recession_results_AD.csv"]["NPV_AggCons"], float))
        out["C_Multiplier_Rec_%s_AD" % pol] = add_cons_ad / add_inc[-1]
    return out


def multiplier_gate(dir_a, dir_b):
    """Apply the owner gate to the multiplier arrays in C_Multiplier_*_Results.csv.

    The HEADLINE gate (per the T1c redirect) is |Delta| > GATE on the LAST-ELEMENT
    AD cumulative multiplier (the 10y-horizon value the paper reports) for the
    reportable policies -- Check-AD and TaxCut-AD. UI-AD is all-NaN by construction
    (missing NPV_AddInc_UI) and is EXCLUDED. This pickle is written at
    Output_Results.py:308, BEFORE the Results_HANK crash at :346, so it exists for
    both legs even though Tables/.../Multiplier.tex never gets written (line 482).

    Per key it also reports the full-array max|Delta| as a diagnostic (a superset
    check); the PASS/FAIL verdict keys on the last-element headline value.
    """
    mult_file = _resolve_mult_file(dir_a, dir_b)
    pa = os.path.join(dir_a, mult_file)
    pb = os.path.join(dir_b, mult_file)
    if os.path.exists(pa) and os.path.exists(pb):
        a, _ = load_result(pa)
        b, _ = load_result(pb)
        source = mult_file
    else:
        a = _mult_from_scenarios(dir_a)
        b = _mult_from_scenarios(dir_b)
        if a is None or b is None:
            return None
        source = "rebuilt from scenario pickles (non-Baseline run; see _mult_from_scenarios)"
    rows = []
    headline_worst = 0.0   # gate quantity: last-element |Delta| over reportable keys
    fullarr_worst = 0.0    # diagnostic: whole-array max |Delta|
    for k in sorted(set(a) & set(b)):
        av = np.asarray(a[k], float).ravel()
        bv = np.asarray(b[k], float).ravel()
        both_nan = np.isnan(av) & np.isnan(bv)
        n_allnan = bool(both_nan.all())
        # full-array (diagnostic)
        d = np.where(both_nan, 0.0, np.abs(av - bv))
        onesided = np.isnan(d)
        d = np.where(onesided, math.inf, d)
        full_max = float(np.max(d)) if d.size else 0.0
        # last-element headline
        la = float(av[-1]) if av.size else float("nan")
        lb = float(bv[-1]) if bv.size else float("nan")
        if math.isnan(la) and math.isnan(lb):
            last_abs = 0.0
        elif math.isnan(la) or math.isnan(lb):
            last_abs = math.inf
        else:
            last_abs = abs(la - lb)
        rows.append({"key": k, "last_a": la, "last_b": lb, "last_abs": last_abs,
                     "full_max": full_max, "all_nan": n_allnan,
                     "onesided_nan": int(np.count_nonzero(onesided))})
        if not n_allnan:
            headline_worst = max(headline_worst, last_abs)
            fullarr_worst = max(fullarr_worst, full_max)
    return {"rows": rows, "headline_worst": headline_worst,
            "fullarr_worst": fullarr_worst,
            "tripped": headline_worst > GATE,
            "fullarr_tripped": fullarr_worst > GATE,
            "source": source}


def _parse_tex_floats(path):
    with open(path) as f:
        txt = f.read()
    return [float(x) for x in re.findall(r"[-+]?\d+\.\d+", txt)]


def tex_gate(tables_a, tables_b, name="Multiplier_candidate.tex"):
    pa = os.path.join(tables_a, name)
    pb = os.path.join(tables_b, name)
    if not (os.path.exists(pa) and os.path.exists(pb)):
        return {"present": False, "a": os.path.exists(pa), "b": os.path.exists(pb)}
    fa, fb = _parse_tex_floats(pa), _parse_tex_floats(pb)
    if len(fa) != len(fb):
        return {"present": True, "count_mismatch": (len(fa), len(fb))}
    diffs = [abs(x - y) for x, y in zip(fa, fb)]
    worst = max(diffs) if diffs else 0.0
    return {"present": True, "worst": worst, "n": len(fa),
            "tripped": worst > GATE}


# ----------------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------------
DEF_A = "FromPandemicCode/Figures/Baseline_pfexp"
DEF_B = "FromPandemicCode/Figures/Baseline_pfpl"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dir_a", nargs="?", default=DEF_A, help="exp Figures dir")
    p.add_argument("dir_b", nargs="?", default=DEF_B, help="powerlaw Figures dir")
    p.add_argument("--tables-a", default=None)
    p.add_argument("--tables-b", default=None)
    p.add_argument("--glob", default="*.csv", help="result-file glob in the Figures dirs")
    p.add_argument("--show-top", type=int, default=8,
                   help="how many worst leaves to list")
    args = p.parse_args(argv)

    dir_a = os.path.abspath(args.dir_a)
    dir_b = os.path.abspath(args.dir_b)
    tables_a = args.tables_a or dir_a.replace("Figures", "Tables")
    tables_b = args.tables_b or dir_b.replace("Figures", "Tables")
    self_cmp = (dir_a == dir_b)

    print("=" * 78)
    print("T1c decay-form comparison  (exp vs powerlaw)")
    print("  dir_a (exp) :", dir_a)
    print("  dir_b (pl)  :", dir_b)
    if self_cmp:
        print("  *** SELF-COMPARE: STRICT-ZERO validation mode ***")
    print("=" * 78)

    # ---- file discovery ----
    files_a = {os.path.basename(f) for f in _glob.glob(os.path.join(dir_a, args.glob))}
    files_b = {os.path.basename(f) for f in _glob.glob(os.path.join(dir_b, args.glob))}
    only_a = sorted(files_a - files_b)
    only_b = sorted(files_b - files_a)
    common = sorted(files_a & files_b)
    if only_a:
        print("  files only in dir_a:", only_a)
    if only_b:
        print("  files only in dir_b:", only_b)
    print(f"  result files to compare: {len(common)}\n")

    global_max_abs = 0.0
    global_max_rel = 0.0
    global_max_abs_path = ""
    any_structural = False
    per_file = []
    base_a = base_b = None

    print(f"{'file':<48}{'fmt':<9}{'leaves':>7}{'max|abs|':>13}{'max|rel|':>13}")
    print("-" * 90)
    for name in common:
        pa = os.path.join(dir_a, name)
        pb = os.path.join(dir_b, name)
        try:
            obj_a, fmt_a = load_result(pa)
            obj_b, fmt_b = load_result(pb)
        except Exception as e:
            print(f"{name:<48}*** UNREADABLE: {e}")
            any_structural = True
            continue
        acc, skipped = [], []
        walk(obj_a, obj_b, name, acc, skipped)
        struct = [r for r in acc if "max_abs" in r and r["max_abs"] == math.inf]
        num = [r for r in acc if r.get("n")]
        fmax_abs = max((r["max_abs"] for r in num), default=0.0)
        fmax_rel = max((r["max_rel"] for r in num), default=0.0)
        leaves = sum(r.get("n", 0) for r in num)
        if struct:
            any_structural = True
        if fmax_abs > global_max_abs:
            global_max_abs = fmax_abs
            hit = max(num, key=lambda r: r["max_abs"])
            global_max_abs_path = hit["path"]
        global_max_rel = max(global_max_rel, fmax_rel)
        per_file.append({"name": name, "fmt": fmt_a, "leaves": leaves,
                         "max_abs": fmax_abs, "max_rel": fmax_rel,
                         "struct": len(struct), "num_records": num})
        flag = "  <-STRUCT" if struct else ""
        print(f"{name:<48}{fmt_a:<9}{leaves:>7}{fmax_abs:>13.3e}"
              f"{fmax_rel:>13.3e}{flag}")
        if name == "base_results.csv":
            base_a, base_b = obj_a, obj_b

    # ---- worst leaves ----
    all_num = [r for pf in per_file for r in pf["num_records"] if r["max_abs"] > 0]
    all_num.sort(key=lambda r: r["max_abs"], reverse=True)
    if all_num:
        print(f"\nTop {args.show_top} numeric leaves by |abs| diff:")
        for r in all_num[:args.show_top]:
            print(f"    {r['max_abs']:.3e}  (rel {r['max_rel']:.3e})  {r['path']}")

    # ---- TranMatrix decomposition ----
    print("\n" + "-" * 90)
    print("Per-type TranMatrix decomposition (from base_results.csv):")
    if base_a is not None and base_b is not None:
        rows = decompose_tranmatrix(base_a, base_b)
        if rows is None:
            print("  (no _type_results in base_results.csv)")
        else:
            print(f"{'type':>4}{'A_nrm':>12}{'nnz(D)':>9}{'max|Dp|':>13}"
                  f"{'statmass@D':>14}{'max|Dpi|':>13}")
            gic = max(rows, key=lambda r: r["A_nrm"])
            for r in rows:
                tag = "  <-GIC-cap College atom" if r is gic else ""
                print(f"{r['type']:>4}{r['A_nrm']:>12.4f}{r['nnz']:>9}"
                      f"{r['max_dp']:>13.3e}{r['statmass']:>14.3e}"
                      f"{r['max_dpi']:>13.3e}{tag}")
            worst_statmass = max(r["statmass"] for r in rows)
            worst_dp = max(r["max_dp"] for r in rows)
            print(f"\n  worst max|Dp| over types = {worst_dp:.3e}; "
                  f"worst stationary-mass-on-differing-cols = {worst_statmass:.3e}")
    else:
        print("  base_results.csv not found in both dirs -- skipped.")

    # ---- multiplier gate (THE gate: last-element AD cumulative multiplier) ----
    print("\n" + "-" * 90)
    print("Multiplier gate (AUTHORITATIVE): |Delta| > %.3g on the LAST-ELEMENT"
          % GATE)
    print("AD cumulative multiplier, from C_Multiplier_Baseline_Results.csv"
          " (pre-crash pickle):")
    mg = multiplier_gate(dir_a, dir_b)
    mult_tripped = False
    if mg is None:
        print("  no C_Multiplier_* pickle in both dirs and the scenario-pickle "
              "rebuild is unavailable -- gate SKIPPED.")
        any_structural = True   # the gate input is mandatory; absence is structural
    else:
        print(f"  source: {mg['source']}")
        for r in mg["rows"]:
            if r["all_nan"]:
                print(f"    {r['key']:<28} all-NaN -> EXCLUDED (missing-impl)")
                continue
            note = ""
            if r["onesided_nan"]:
                note += f"  [{r['onesided_nan']} one-sided-NaN!]"
            print(f"    {r['key']:<28} last: exp={r['last_a']:.6f}"
                  f"  pl={r['last_b']:.6f}  |Delta|={r['last_abs']:.3e}"
                  f"   (full-array max|Delta|={r['full_max']:.3e}){note}")
        mult_tripped = mg["tripped"]
        print(f"  headline worst last-element |Delta multiplier| = "
              f"{mg['headline_worst']:.3e}"
              f"  -> {'TRIPPED' if mult_tripped else 'within gate'}")
        if mg["fullarr_tripped"] and not mult_tripped:
            print(f"  WARNING: full-array max|Delta| = {mg['fullarr_worst']:.3e}"
                  " exceeds gate on a non-final quarter (headline still ok).")

    # ---- tex comparison (INFORMATIONAL ONLY -- never part of the verdict) ----
    # NOTE: the exp/pl legs crash at Output_Results.py:346 (missing Results_HANK)
    # BEFORE Multiplier.tex is written at :482, so this tex is expected ABSENT for
    # both legs. Kept only to surface a diff if a later run ever emits it.
    tg = tex_gate(tables_a, tables_b)
    if not tg.get("present"):
        print(f"  [info] Multiplier_candidate.tex present a={tg.get('a')}"
              f" b={tg.get('b')} -- expected absent (pre-:482 crash); not gated.")
    elif "count_mismatch" in tg:
        print(f"  [info] Multiplier_candidate.tex float-count mismatch"
              f" {tg['count_mismatch']} (informational).")
    else:
        print(f"  [info] Multiplier_candidate.tex: {tg['n']} floats, worst |Delta|"
              f" = {tg['worst']:.3e} (informational, NOT part of gate).")

    # ---- verdict ----
    print("\n" + "=" * 78)
    print("SUMMARY")
    print(f"  global max |abs| leaf diff : {global_max_abs:.3e}"
          f"   at {global_max_abs_path}")
    print(f"  global max |rel| leaf diff : {global_max_rel:.3e}")
    if only_a or only_b:
        print(f"  file-set mismatch          : only_a={len(only_a)} only_b={len(only_b)}")

    gate_pass = (not mult_tripped) and (not any_structural)
    if self_cmp:
        strict_ok = (global_max_abs == 0.0 and global_max_rel == 0.0
                     and not any_structural and not only_a and not only_b)
        print(f"  STRICT-ZERO self-compare   : "
              f"{'PASS (all diffs exactly 0.0)' if strict_ok else 'FAIL'}")
        gate_pass = gate_pass and strict_ok

    verdict = "PASS" if gate_pass else "FAIL"
    print("=" * 78)
    print(f"VERDICT: {verdict}"
          f"   (multiplier gate {'TRIPPED' if mult_tripped else 'ok'}"
          f"{', STRUCTURAL issues' if any_structural else ''})")
    print("=" * 78)
    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())
