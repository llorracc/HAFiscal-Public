"""HS_Only gate harness for the Step-5a cohort-parallel solve scout (R8 item 8).

Runs a SMALL end-to-end HS_Only Step-5a segment through Simulate() and
byte-compares outputs across arms:

  --arm pre   pre-edit Simulate.py (materialized from `git show HEAD:...`,
              shadow-loaded ahead of FromPandemicCode on sys.path):
              neutrality reference — proves the flag-off default is
              byte-identical to the unedited code.
  --arm off   edited Simulate.py, HAFISCAL_STEP5A_PARALLEL_SOLVE unset.
  --arm on    edited Simulate.py, HAFISCAL_STEP5A_PARALLEL_SOLVE=auto +
              HAFISCAL_STEP5A_FORCE_POOL=1 (HS_Only has ONE cohort, so the
              force knob makes the fork+pickle path actually execute).
  --compare A B [C ...]   sha256 + numeric comparison of the arms' outputs.

Gate segment (Run_Dict): Run_Baseline + Run_Check_Recession (NonAD + AD-TM)
+ Run_Check + Run_TaxCut, sim_method='TM', tm_a_indexed=True,
tm_neutral_measure=True, tm_mCount=100 — i.e. the production TM multiplier
configuration, restricted to 3 shock jobs so the outer shock fork is ACTIVE
(pool-inside-forked-child composition is exercised) while staying cheap.
Covers wrapped sites: 'initial' (parent), 'norec_Check' + 'norec_TaxCut'
(children), 'nonad_recessionCheck' + 'adtm_recessionCheck' (child), plus the
inner duration fork running AFTER a pooled solve in the same child.

Each arm must run in a FRESH interpreter (BLAS pins + env are read at import
time): invoke this script once per arm.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))          # Code/HA-Models
FPC = os.path.join(HERE, 'FromPandemicCode')
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# Env overrides that must NOT leak into the gate (fixed config across arms).
_POP_ENV = [
    'HAFISCAL_SIM_METHOD', 'HAFISCAL_TM_MCOUNT', 'HAFISCAL_NO_FORK',
    'HAFISCAL_PARALLEL_SOLVE', 'HAFISCAL_USE_SOLUTION_CACHE',
    'HAFISCAL_USE_JAX_2B', 'HAFISCAL_USE_JAX_2B_VMAP',
    'HAFISCAL_STEP2_NAMG', 'HAFISCAL_STEP2_ANDERSON', 'HAFISCAL_STEP5_ATI',
    'HAFISCAL_SEED_OFFSET', 'HAFISCAL_AGENTCOUNT_D', 'HAFISCAL_AGENTCOUNT_H',
    'HAFISCAL_AGENTCOUNT_C', 'HAFISCAL_FIGS_SUFFIX',
    'HAFISCAL_STEP5A_PARALLEL_SOLVE', 'HAFISCAL_STEP5A_FORCE_POOL',
    'HAFISCAL_STEP5A_SOLVE_PROBE_DIR',
]


def _gate_run_dict():
    return {
        'Run_Baseline': True,
        'Run_Recession ': False,
        'Run_Check_Recession': True,
        'Run_UB_Ext_Recession': False,
        'Run_TaxCut_Recession': False,
        'Run_Check': True,
        'Run_UB_Ext': False,
        'Run_TaxCut': True,
        'Run_AD ': True,
        'Run_1stRoundAD': False,
        'Run_NonAD': True,
        'sim_method': 'TM',
        'tm_neutral_measure': True,
        'tm_mCount': 100,
        'tm_a_indexed': True,
    }


def run_arm(arm, out_base):
    out_dir = os.path.join(out_base, arm)
    figs_dir = os.path.join(out_dir, 'figs') + os.sep
    probe_dir = os.path.join(out_dir, 'probes')
    os.makedirs(figs_dir, exist_ok=True)
    os.makedirs(probe_dir, exist_ok=True)

    # ---- env (before ANY numpy/HARK import) ----
    for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS',
                'NUMBA_NUM_THREADS'):
        os.environ.setdefault(var, '1')
    for var in _POP_ENV:
        os.environ.pop(var, None)
    os.environ['HAFISCAL_DUR_WORKERS'] = '2'      # bound the inner fan, same all arms
    os.environ['HAFISCAL_AD_BELIEF_PUBLISH'] = '0'  # no shared-cache sidecars from a gate
    os.environ['HAFISCAL_STEP5A_SOLVE_PROBE_DIR'] = probe_dir
    if arm == 'on':
        os.environ['HAFISCAL_STEP5A_PARALLEL_SOLVE'] = 'auto'
        os.environ['HAFISCAL_STEP5A_FORCE_POOL'] = '1'
    elif arm not in ('off', 'pre'):
        raise SystemExit(f'unknown arm {arm!r}')

    # ---- sys.path / cwd ----
    if arm == 'pre':
        shadow = os.path.join(out_dir, 'shadow')
        os.makedirs(shadow, exist_ok=True)
        src = subprocess.run(
            ['git', '-C', REPO, 'show',
             'HEAD:Code/HA-Models/FromPandemicCode/Simulate.py'],
            check=True, capture_output=True).stdout
        with open(os.path.join(shadow, 'Simulate.py'), 'wb') as fh:
            fh.write(src)
        sys.path.insert(0, shadow)
    os.chdir(FPC)
    for p in (FPC, HERE):
        if p not in sys.path:
            sys.path.insert(1 if arm == 'pre' else 0, p)
    sys.argv = [sys.argv[0]]   # Parameters/EstimParameters parse argv at import

    from Simulate import Simulate  # noqa: E402  (pre arm: shadow copy wins)
    print(f"[gate] arm={arm}  Simulate from: {sys.modules['Simulate'].__file__}",
          flush=True)

    t0 = time.time()
    Simulate(_gate_run_dict(), figs_dir, Parametrization='HS_Only')
    wall = time.time() - t0
    with open(os.path.join(out_dir, 'wall.json'), 'w') as fh:
        json.dump({'arm': arm, 'wall_sec': wall,
                   'note': 'CONTAMINATED — other agents co-running on this box'},
                  fh, indent=2)
    print(f"[gate] arm={arm} DONE in {wall:.1f}s (CONTAMINATED wall)", flush=True)


# --------------------------------------------------------------------------

def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _collect(out_base, arm):
    """{relpath: abspath} for comparable artifacts of one arm."""
    found = {}
    for sub in ('figs', 'probes'):
        root = os.path.join(out_base, arm, sub)
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fn in sorted(files):
                full = os.path.join(dirpath, fn)
                rel = os.path.join(sub, os.path.relpath(full, root))
                found[rel] = full
    return found


#: Artifacts that pickle LIVE objects (scipy sparse matrices, HARK distribution
#: instances) alongside their numeric payload. Their bytes are not reproducible
#: run-to-run — verified by a two-run identical-code discriminator, 2026-07-25 —
#: so they are gated on NUMERIC identity instead. Keep this list minimal and
#: evidence-backed: every entry is a place where byte-identity was demonstrated
#: to be the wrong criterion, never a place where a real difference was excused.
_BYTE_UNSTABLE_SUFFIXES = ('base_results.csv',)


def _is_byte_unstable(key):
    return key.endswith(_BYTE_UNSTABLE_SUFFIXES)


def _pickle_maxdiff(path_a, path_b):
    """Worst RELATIVE numeric difference between two pickled result objects.

    Walks dicts/lists/arrays/scalars; embedded non-numeric objects (scipy
    matrices, HARK distributions) are skipped by design — they are exactly the
    members whose byte instability motivated this comparison. Returns inf if the
    structures cannot be walked in parallel (a real, reportable difference).
    """
    import pickle
    import numpy as np

    def load(p):
        with open(p, 'rb') as fh:
            return pickle.load(fh)

    worst = 0.0

    def walk(x, y):
        nonlocal worst
        if isinstance(x, dict):
            if not isinstance(y, dict):
                worst = float('inf')
                return
            for k in x:
                if k in y:
                    walk(x[k], y[k])
        elif isinstance(x, (list, tuple)):
            if not isinstance(y, (list, tuple)) or len(x) != len(y):
                worst = float('inf')
                return
            for u, v in zip(x, y):
                walk(u, v)
        elif isinstance(x, np.ndarray):
            try:
                scale = max(float(np.max(np.abs(x))), 1e-300)
                worst = max(worst, float(np.max(np.abs(x - y))) / scale)
            except Exception:
                pass  # non-numeric array member; not a numeric claim
        elif isinstance(x, (int, float, np.floating)) and not isinstance(x, bool):
            worst = max(worst, abs(float(x) - float(y)) / max(abs(float(x)), 1e-300))
        # anything else (scipy/HARK objects, strings) is deliberately skipped

    try:
        walk(load(path_a), load(path_b))
    except Exception:
        return float('inf')
    return worst


def _probe_maxdiff(path_a, path_b):
    import pickle
    import numpy as np
    with open(path_a, 'rb') as fh:
        a = pickle.load(fh)
    with open(path_b, 'rb') as fh:
        b = pickle.load(fh)
    md = 0.0
    for ag_a, ag_b in zip(a['agents'], b['agents']):
        if ag_a['n_states'] != ag_b['n_states']:
            return float('inf')
        md = max(md, float(np.max(np.abs(ag_a['cFunc_evals'] - ag_b['cFunc_evals']))))
    return md


def compare(out_base, arms):
    ref, rest = arms[0], arms[1:]
    ref_files = _collect(out_base, ref)
    # NOTE the criterion split below (2026-07-25): byte-identity is the gate for
    # everything EXCEPT artifacts that pickle LIVE objects, which are byte-
    # unstable run-to-run for reasons unrelated to any code change. Established
    # by a two-run discriminator (identical code, two flag-off runs): the solver
    # probes and 6/7 result CSVs were byte-identical, `base_results.csv` was not,
    # and walking both pickles gave a worst numeric relative difference of
    # EXACTLY 0.0 across every array and scalar — the only differing members are
    # an embedded `csc_matrix` and `IncShkDstn` objects whose pickled state
    # carries incidental scipy/RNG bookkeeping. Byte-identity is a tripwire, not
    # the standard (the repo's numerical-stability acceptance criterion); for
    # these artifacts the honest test is numeric identity.
    all_ok = True
    for other in rest:
        oth_files = _collect(out_base, other)
        keys = sorted(set(ref_files) | set(oth_files))
        n_same = n_diff = n_missing = 0
        print(f"\n=== {ref} vs {other} ===")
        for k in keys:
            if k not in ref_files or k not in oth_files:
                # probes are dumped only by the edited code — absent in 'pre'
                if k.startswith('probes') and ref == 'pre':
                    continue
                print(f"  MISSING in one arm: {k}")
                n_missing += 1
                continue
            same = _sha256(ref_files[k]) == _sha256(oth_files[k])
            if not same and _is_byte_unstable(k):
                # NUMERIC-IDENTITY criterion for artifacts that embed live
                # objects (see _is_byte_unstable): byte-compare is the wrong
                # test there — it reports incidental scipy/RNG bookkeeping.
                num_diff = _pickle_maxdiff(ref_files[k], oth_files[k])
                if num_diff == 0.0:
                    print(f"  NUMERIC-ID  {k}  (bytes differ; max numeric "
                          f"relative diff EXACTLY 0 — embedded-object artifact)")
                    n_same += 1
                    continue
                print(f"  DIFFERS    {k}  (max numeric relative diff="
                      f"{num_diff:.3e})")
                n_diff += 1
                continue
            n_same += int(same)
            n_diff += int(not same)
            line = f"  {'IDENTICAL' if same else 'DIFFERS  '}  {k}"
            if not same and k.startswith('probes'):
                line += f"  (max|diff|={_probe_maxdiff(ref_files[k], oth_files[k]):.3e})"
            print(line)
        verdict = 'PASS' if (n_diff == 0 and n_missing == 0) else 'FAIL'
        print(f"  -> {verdict}: {n_same} identical, {n_diff} differ, "
              f"{n_missing} missing")
        all_ok = all_ok and (verdict == 'PASS')
    return 0 if all_ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['pre', 'off', 'on'])
    ap.add_argument('--compare', nargs='+', metavar='ARM')
    ap.add_argument('--out-base', required=True)
    args = ap.parse_args()
    if args.arm and args.compare:
        raise SystemExit('--arm and --compare are mutually exclusive')
    if args.compare:
        raise SystemExit(compare(args.out_base, args.compare))
    if not args.arm:
        raise SystemExit('need --arm or --compare')
    run_arm(args.arm, args.out_base)


if __name__ == '__main__':
    main()
