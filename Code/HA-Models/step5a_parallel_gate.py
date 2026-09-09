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

Toggle invariants (infrastructure item A5, plan 20260828-1130h, as reshaped by
the prior-art review of 2026-08-28: this gate's HS_Only 3-shock segment IS the
~2-min smoke class, so the per-toggle invariant check lives here rather than
in a new smoke_gate.py). The failure it guards: a toggle meant to move ONE
policy (the tax-cut mimic) silently moving the check/UI cells too — a check
that used to be done by eye.

  --toggle VAR=VALUE      (repeatable) run the arm with VAR set — applied AFTER
                          the _POP_ENV scrub, so an explicit toggle wins even
                          for a scrubbed flag — into <out-base>/<arm>+VAR=VALUE
                          (override the directory name with --label NAME).
  --expect-unchanged CELL[,CELL..]   with --compare A B: every matched cell
                          must be IDENTICAL (sha256; NUMERIC-ID for the
                          evidence-backed byte-unstable artifacts listed in
                          _BYTE_UNSTABLE_SUFFIXES).
  --expect-changed CELL[,CELL..]     with --compare A B: every matched cell
                          must DIFFER (the toggle must move it).
  --dry-run               print the commands a run would execute; solve nothing.

  A CELL is an artifact key as printed by --compare: figs/<name>.csv for the
  Simulate() result pickles (base_results, Check_results, TaxCut_results,
  recessionCheck_results, recessionCheck_all_results, and their _AD twins)
  and probes/probe_<site>.pkl for the solve probes (initial, norec_Check,
  norec_TaxCut, nonad_recessionCheck, adtm_recessionCheck). A bare word is a
  substring match (TaxCut, Check, initial, base_results); a spec containing
  * ? [ is a glob (fnmatch against the key and its basename). --expect-changed
  specs claim cells FIRST; --expect-unchanged specs then match among the
  remaining cells, so `--expect-changed TaxCut --expect-unchanged '*'` is the
  out-of-scope byte-identity assertion: everything the toggle does not claim
  must be byte-identical. A spec that matches no unclaimed cell FAILS — a
  misspelled cell must not pass silently. Exit 0 = every expectation met,
  1 = a verdict failed, 2 = usage error. The verdict table
  (cell | <A> sha | <B> sha | verdict) fits one screen.

  Paired mode (no --arm, no --compare, with --toggle): runs the flag-off arm
  (reused when <out-base>/off/wall.json exists; --rerun-baseline forces), then
  the toggled arm into a fresh directory, each in a FRESH interpreter, then the
  comparison with the expectations. The plan's canonical check:

    python step5a_parallel_gate.py --toggle HAFISCAL_LEGACY_TAXCUT_ATOM=1 \\
        --expect-changed TaxCut --expect-unchanged '*' --out-base /tmp/g5a

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
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
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


def run_arm(arm, out_base, toggles=(), label=None):
    toggles = [tuple(t) for t in toggles]
    arm_dir = arm_label(arm, toggles, label)
    out_dir = os.path.join(out_base, arm_dir)
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
    # A5 toggles go on AFTER the scrub: an explicit --toggle wins even for a
    # flag in _POP_ENV (that is the point of gating it).
    for var, val in toggles:
        os.environ[var] = val
        print(f"[gate] toggle {var}={val}", flush=True)

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
        json.dump({'arm': arm, 'label': arm_dir, 'toggles': dict(toggles),
                   'wall_sec': wall,
                   'note': 'CONTAMINATED — other agents co-running on this box'},
                  fh, indent=2)
    print(f"[gate] arm={arm_dir} DONE in {wall:.1f}s (CONTAMINATED wall)", flush=True)


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


def compare_cells(out_base, ref, other):
    """Per-cell comparison of two arms (the unit the A5 expectations act on).

    Returns a list of rows, one per artifact key (sorted), each a dict with
    ``key``, ``status`` in IDENTICAL | NUMERIC-ID | DIFFERS | MISSING,
    ``sha_ref`` / ``sha_oth`` (None when the file is absent in that arm),
    ``detail`` (the parenthesised note --compare prints) and ``numeric_diff``
    (the max relative / absolute difference where one was computed).

    NOTE the criterion split (2026-07-25): byte-identity is the gate for
    everything EXCEPT artifacts that pickle LIVE objects, which are byte-
    unstable run-to-run for reasons unrelated to any code change. Established
    by a two-run discriminator (identical code, two flag-off runs): the solver
    probes and 6/7 result CSVs were byte-identical, `base_results.csv` was not,
    and walking both pickles gave a worst numeric relative difference of
    EXACTLY 0.0 across every array and scalar — the only differing members are
    an embedded `csc_matrix` and `IncShkDstn` objects whose pickled state
    carries incidental scipy/RNG bookkeeping. Byte-identity is a tripwire, not
    the standard (the repo's numerical-stability acceptance criterion); for
    these artifacts the honest test is numeric identity.
    """
    ref_files = _collect(out_base, ref)
    oth_files = _collect(out_base, other)
    rows = []
    for k in sorted(set(ref_files) | set(oth_files)):
        row = {'key': k, 'status': None, 'sha_ref': None, 'sha_oth': None,
               'detail': '', 'numeric_diff': None}
        if k not in ref_files or k not in oth_files:
            # probes are dumped only by the edited code — absent in 'pre'
            if k.startswith('probes') and ref == 'pre':
                continue
            row['status'] = 'MISSING'
            if k in ref_files:
                row['sha_ref'] = _sha256(ref_files[k])
            if k in oth_files:
                row['sha_oth'] = _sha256(oth_files[k])
            rows.append(row)
            continue
        row['sha_ref'] = _sha256(ref_files[k])
        row['sha_oth'] = _sha256(oth_files[k])
        same = row['sha_ref'] == row['sha_oth']
        if not same and _is_byte_unstable(k):
            # NUMERIC-IDENTITY criterion for artifacts that embed live
            # objects (see _is_byte_unstable): byte-compare is the wrong
            # test there — it reports incidental scipy/RNG bookkeeping.
            num_diff = _pickle_maxdiff(ref_files[k], oth_files[k])
            row['numeric_diff'] = num_diff
            if num_diff == 0.0:
                row['status'] = 'NUMERIC-ID'
                row['detail'] = ('(bytes differ; max numeric relative diff '
                                 'EXACTLY 0 — embedded-object artifact)')
            else:
                row['status'] = 'DIFFERS'
                row['detail'] = f'(max numeric relative diff={num_diff:.3e})'
        else:
            row['status'] = 'IDENTICAL' if same else 'DIFFERS'
            if not same and k.startswith('probes'):
                try:
                    md = _probe_maxdiff(ref_files[k], oth_files[k])
                except Exception:
                    md = float('inf')   # payloads not comparable: a real difference
                row['numeric_diff'] = md
                row['detail'] = f'(max|diff|={md:.3e})'
        rows.append(row)
    return rows


def _print_compare_block(ref, other, rows):
    """The classic --compare printout for one pair; returns 'PASS' | 'FAIL'."""
    n_same = n_diff = n_missing = 0
    print(f"\n=== {ref} vs {other} ===")
    for r in rows:
        k, status = r['key'], r['status']
        if status == 'MISSING':
            print(f"  MISSING in one arm: {k}")
            n_missing += 1
            continue
        tag = {'IDENTICAL': 'IDENTICAL', 'NUMERIC-ID': 'NUMERIC-ID',
               'DIFFERS': 'DIFFERS  '}[status]
        line = f"  {tag}  {k}"
        if r['detail']:
            line += f"  {r['detail']}"
        print(line)
        if status == 'DIFFERS':
            n_diff += 1
        else:
            n_same += 1
    verdict = 'PASS' if (n_diff == 0 and n_missing == 0) else 'FAIL'
    print(f"  -> {verdict}: {n_same} identical, {n_diff} differ, "
          f"{n_missing} missing")
    return verdict


def compare(out_base, arms):
    ref, rest = arms[0], arms[1:]
    all_ok = True
    for other in rest:
        verdict = _print_compare_block(ref, other, compare_cells(out_base, ref, other))
        all_ok = all_ok and (verdict == 'PASS')
    return 0 if all_ok else 1


# --------------------------------------------------------------------------
# A5: toggles + per-cell expectations (plan 20260828-1130h, reshaped onto this
# gate by the prior-art review of 2026-08-28). Pure functions over the rows of
# compare_cells() so the verdict logic is unit-testable without a solve
# (test_step5a_gate_toggle.py).

_TOGGLE_VAR = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def parse_toggle(spec):
    """'VAR=VALUE' -> (VAR, VALUE); ValueError on a malformed spec."""
    var, sep, val = spec.partition('=')
    if not sep or not _TOGGLE_VAR.match(var):
        raise ValueError(f'--toggle expects VAR=VALUE, got {spec!r}')
    return var, val


def arm_label(arm, toggles=(), label=None):
    """Output-dir name of a run: <arm>, or <arm>+VAR=VALUE[+...] under toggles."""
    if label:
        return label
    if not toggles:
        return arm
    name = '+'.join([arm] + [f'{var}={val}' for var, val in toggles])
    return ''.join('_' if (ch == os.sep or ch.isspace()) else ch for ch in name)


def split_cells(specs):
    """['a,b', 'c'] -> ['a', 'b', 'c']: comma-separated AND repeatable; blanks dropped."""
    out = []
    for spec in specs or ():
        out.extend(s.strip() for s in spec.split(',') if s.strip())
    return out


def cell_matches(spec, key):
    """Bare word = substring of the key; a spec with * ? [ = glob on key or basename."""
    if any(ch in spec for ch in '*?['):
        return (fnmatch.fnmatchcase(key, spec)
                or fnmatch.fnmatchcase(os.path.basename(key), spec))
    return spec in key


_PASSING_STATUS = {'unchanged': ('IDENTICAL', 'NUMERIC-ID'), 'changed': ('DIFFERS',)}


def assert_expectations(rows, expect_unchanged=(), expect_changed=()):
    """Apply --expect-unchanged / --expect-changed specs to compare_cells() rows.

    --expect-changed specs claim cells first; --expect-unchanged specs match
    among the remaining cells (so '*' there means "everything the toggle does
    not claim"). Every claimed cell gets a verdict: an 'unchanged' cell passes
    on IDENTICAL or NUMERIC-ID, a 'changed' cell passes on DIFFERS; MISSING
    fails either way. A spec that claims nothing yields a NO-MATCH row that
    FAILS (a misspelled cell must not pass silently).

    Returns (verdicts, ok): verdicts are dicts with cell, expect, spec, status,
    sha_ref, sha_oth, detail, verdict — in cell order, NO-MATCH rows last;
    ok is True iff every verdict is PASS.
    """
    by_key = {r['key']: r for r in rows}
    claimed = {}
    no_match = []
    for expect, specs in (('changed', expect_changed), ('unchanged', expect_unchanged)):
        for spec in specs:
            hits = [k for k in by_key if k not in claimed and cell_matches(spec, k)]
            if not hits:
                no_match.append({
                    'cell': spec, 'expect': expect, 'spec': spec,
                    'status': 'NO-MATCH', 'sha_ref': None, 'sha_oth': None,
                    'detail': 'spec matches no unclaimed cell', 'verdict': 'FAIL'})
                continue
            for k in hits:
                claimed[k] = (expect, spec)
    verdicts = []
    for k, r in by_key.items():
        if k not in claimed:
            continue
        expect, spec = claimed[k]
        passed = r['status'] in _PASSING_STATUS[expect]
        detail = r['detail']
        if not passed and expect == 'changed' and r['status'] != 'MISSING':
            detail = 'toggle had no effect on a cell it must move'
        verdicts.append({
            'cell': k, 'expect': expect, 'spec': spec, 'status': r['status'],
            'sha_ref': r['sha_ref'], 'sha_oth': r['sha_oth'], 'detail': detail,
            'verdict': 'PASS' if passed else 'FAIL'})
    verdicts.extend(no_match)
    return verdicts, all(v['verdict'] == 'PASS' for v in verdicts)


def format_expectation_table(verdicts, ref, other):
    """One-screen table: cell | <ref> sha | <other> sha | verdict."""
    def sha(s):
        return s[:12] if s else '-'
    head = ('cell', ref, other, 'verdict')
    body = []
    for v in verdicts:
        text = f"{v['verdict']} {v['expect']} {v['status']}"
        if v['detail']:
            text += f" {v['detail']}"
        body.append((v['cell'], sha(v['sha_ref']), sha(v['sha_oth']), text))
    widths = [max(len(r[i]) for r in [head] + body) for i in range(4)]

    def fmt(r):
        return ' | '.join(c.ljust(w) for c, w in zip(r, widths)).rstrip()
    lines = [fmt(head), '-+-'.join('-' * w for w in widths)] + [fmt(r) for r in body]
    return '\n'.join(lines)


def check_expectations(out_base, ref, other, expect_unchanged=(), expect_changed=()):
    """--compare REF OTHER with expectations: classic block, verdict table, 0/1."""
    rows = compare_cells(out_base, ref, other)
    _print_compare_block(ref, other, rows)
    verdicts, ok = assert_expectations(rows, expect_unchanged, expect_changed)
    n_fail = sum(v['verdict'] == 'FAIL' for v in verdicts)
    n_unasserted = len(rows) - sum(v['status'] != 'NO-MATCH' for v in verdicts)
    print(f"\n=== expectations: {ref} -> {other} ===")
    print(format_expectation_table(verdicts, ref, other))
    print(f"  -> {'PASS' if ok else 'FAIL'}: {len(verdicts) - n_fail} passed, "
          f"{n_fail} failed, {n_unasserted} cells unasserted")
    return 0 if ok else 1


def arm_command(arm, out_base, toggles=(), label=None):
    """argv that runs one arm in a fresh interpreter (what --dry-run prints)."""
    cmd = [sys.executable, os.path.abspath(__file__), '--arm', arm]
    for var, val in toggles:
        cmd += ['--toggle', f'{var}={val}']
    if label:
        cmd += ['--label', label]
    return cmd + ['--out-base', out_base]


def pair_commands(arm, toggles, out_base, expect_unchanged=(), expect_changed=()):
    """(baseline_cmd, toggled_cmd, compare_cmd, baseline_name, toggled_name)."""
    out_base = os.path.abspath(out_base)
    base_name = arm_label(arm)
    tog_name = arm_label(arm, toggles)
    cmp_cmd = [sys.executable, os.path.abspath(__file__),
               '--compare', base_name, tog_name, '--out-base', out_base]
    for spec in expect_changed:
        cmp_cmd += ['--expect-changed', spec]
    for spec in expect_unchanged:
        cmp_cmd += ['--expect-unchanged', spec]
    return (arm_command(arm, out_base), arm_command(arm, out_base, toggles),
            cmp_cmd, base_name, tog_name)


def run_pair(arm, toggles, out_base, expect_unchanged=(), expect_changed=(),
             dry_run=False, rerun_baseline=False):
    """Paired toggle run: baseline arm (reused if present), toggled arm, verdicts."""
    out_base = os.path.abspath(out_base)
    base_cmd, tog_cmd, cmp_cmd, base_name, tog_name = pair_commands(
        arm, toggles, out_base, expect_unchanged, expect_changed)
    print("[gate] paired toggle run — each arm in a FRESH interpreter:")
    for cmd in (base_cmd, tog_cmd, cmp_cmd):
        print('  ' + shlex.join(cmd))
    if dry_run:
        print("[gate] DRY-RUN: nothing executed", flush=True)
        return 0
    if os.path.isfile(os.path.join(out_base, base_name, 'wall.json')) and not rerun_baseline:
        print(f"[gate] baseline arm {base_name!r} present under {out_base} — REUSED "
              f"(--rerun-baseline to redo)", flush=True)
    else:
        rc = subprocess.run(base_cmd).returncode
        if rc:
            print(f"[gate] baseline arm FAILED (exit {rc})", flush=True)
            return rc
    tog_dir = os.path.join(out_base, tog_name)
    if os.path.isdir(tog_dir):
        shutil.rmtree(tog_dir)   # no stale artifacts from an earlier toggled run
    rc = subprocess.run(tog_cmd).returncode
    if rc:
        print(f"[gate] toggled arm FAILED (exit {rc})", flush=True)
        return rc
    return check_expectations(out_base, base_name, tog_name,
                              expect_unchanged, expect_changed)


def main():
    ap = argparse.ArgumentParser(
        description='HS_Only Step-5a gate: run an arm, compare arms, or gate a toggle '
                    '(see the module docstring for the cell names and the semantics).')
    ap.add_argument('--arm', choices=['pre', 'off', 'on'])
    ap.add_argument('--compare', nargs='+', metavar='ARM')
    ap.add_argument('--out-base', required=True)
    ap.add_argument('--toggle', action='append', default=[], metavar='VAR=VALUE',
                    help='env var to set for the run (repeatable); applied after the '
                         '_POP_ENV scrub; the output dir is named <arm>+VAR=VALUE')
    ap.add_argument('--label', metavar='NAME',
                    help='output dir name of a single --arm run (default: <arm>[+VAR=VALUE..])')
    ap.add_argument('--expect-unchanged', action='append', default=[],
                    metavar='CELL[,CELL..]',
                    help='with --compare A B: cells that must be byte-identical')
    ap.add_argument('--expect-changed', action='append', default=[],
                    metavar='CELL[,CELL..]',
                    help='with --compare A B: cells the toggle must move (claimed first)')
    ap.add_argument('--dry-run', action='store_true',
                    help='print the command(s) a run would execute; solve nothing')
    ap.add_argument('--rerun-baseline', action='store_true',
                    help='paired mode: re-run the baseline arm even if its outputs exist')
    args = ap.parse_args()
    try:
        toggles = [parse_toggle(t) for t in args.toggle]
    except ValueError as exc:
        ap.error(str(exc))
    unchanged = split_cells(args.expect_unchanged)
    changed = split_cells(args.expect_changed)

    if args.arm and args.compare:
        raise SystemExit('--arm and --compare are mutually exclusive')
    if args.compare:
        if toggles or args.label:
            ap.error('--toggle/--label describe a run; --compare names arms already run')
        if unchanged or changed:
            if len(args.compare) != 2:
                ap.error('--expect-* need exactly two arms: --compare BASELINE TOGGLED')
            if args.dry_run:
                print('[gate] DRY-RUN: ' + shlex.join(sys.argv))
                return
            raise SystemExit(check_expectations(args.out_base, args.compare[0],
                                                args.compare[1], unchanged, changed))
        raise SystemExit(compare(args.out_base, args.compare))
    if args.arm:
        if unchanged or changed:
            ap.error('--expect-* apply to --compare A B or to a paired --toggle run')
        cmd = arm_command(args.arm, os.path.abspath(args.out_base), toggles, args.label)
        if args.dry_run:
            print('[gate] DRY-RUN: ' + shlex.join(cmd))
            return
        run_arm(args.arm, args.out_base, toggles, args.label)
        return
    if toggles:
        if args.label:
            ap.error('--label names a single --arm run; a paired run names its dirs '
                     'after the toggle')
        raise SystemExit(run_pair('off', toggles, args.out_base, unchanged, changed,
                                  dry_run=args.dry_run,
                                  rerun_baseline=args.rerun_baseline))
    raise SystemExit('need --arm, --compare or --toggle')


if __name__ == '__main__':
    main()
