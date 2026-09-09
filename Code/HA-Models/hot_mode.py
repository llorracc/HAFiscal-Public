"""``--hot``: exercise every live path as fast as possible, and keep none of the numbers.

WHAT IT IS FOR.  A hot run answers one question -- *does the whole pipeline still execute?*
-- and no other.  It is the check you want after a refactor, a dependency bump or a machine
change, when a two-hour ``do_all`` is too slow to run and ``make test-fast`` is too shallow
to prove the steps still compose.

WHAT IT IS NOT.  It is not a fast way to get results.  Everything it does to be quick makes
its numbers unquotable: a single education group instead of 21 cohorts, one seed, a reduced
population.  The banner says so, and the outputs are suffixed so they cannot be mistaken
for, or overwrite, the paper's.

WHY IT DOES NOT WARM-START.  The obvious way to make this faster is to feed each solve the
previous run's converged answer.  That is deliberately NOT done, for two reasons.

*It would defeat the purpose.*  Start an iterative solver at its own fixed point and it
takes ~zero iterations, so the iteration loop, the convergence test and the guards that
fire on a bad iterate are exactly what stops being exercised.  A hot run would be fastest
where it tests least -- the opposite of what it is for.

*The unverified form of it is a live bug.*  ``HAFISCAL_NM_IN_PLACE=1`` reuses the economy's
agents in place across objective evaluations -- endpoint as startpoint, exactly.  It trips
the BUG-062 PF-decay guard, which is why every hand-run driver sets it to ``0`` and why
``do_all`` omitting that flag silently killed the fit-table pass in the 2026-09-06 chain of
record (BUG-125).  Reuse in this codebase is safe only where it is VERIFIED: the policy
store re-checks every hit with a backward sweep of the agent's own solver, and the
AD-equilibrium store keys on the world and the flags.  Those caches stay ON in a hot run,
because they are verified.  Nothing new is added on top.

The one sound way to reuse more is at a STAGE boundary -- Step 5b consuming Step 5a's
converged equilibrium, which already exists as ``ad_equilibrium_share`` and is checkable
from provenance.  Reusing a completed stage's output is not the same act as warm-starting
an iteration inside one.

FLAGS.  ``HAFISCAL_HOT=1`` turns it on; ``HAFISCAL_HOT_SCOPE`` picks the parametrization
(default ``HS_Only``).  See ``Code/HA-Models/docs/ENV_FLAGS.md``.
"""

import os
import shutil

SUFFIX = "_hot"
DEFAULT_SCOPE = "HS_Only"


def enabled():
    return os.environ.get("HAFISCAL_HOT", "").strip().lower() in ("1", "on", "true", "yes")


def scope():
    """The parametrization a hot run uses. HS_Only by default: one education group, but a
    real solve and a real simulation -- Smoke_Test (N=100) is a crash check, not a path
    exercise, and several downstream steps have nothing to read from it."""
    return os.environ.get("HAFISCAL_HOT_SCOPE", "").strip() or DEFAULT_SCOPE


# Optimizer tolerances a hot run loosens. THIS is where a hot run's speed comes from, and
# it is the honest lever: a coarse tolerance still runs the iteration loop and still fires
# the convergence test -- it just converges sooner. Warm-starting from a converged endpoint
# would skip both, which is why hot mode does not do it (see the module docstring).
#
# It has to be this lever, because the SCOPE lever alone buys almost nothing. Measured from
# README's own numbers, do_all at Baseline is 136 min: Step 1 = 23, Step 2 = 40, Step 4 =
# 10, Step 5a = 43, Step 5b = 13, fit pass = 7. HAFISCAL_HOT_SCOPE only shrinks Step 5
# (56 min of the 136); Steps 1 and 2 -- 63 min between them -- are full-cost estimations
# that do not know what scope Step 5 is running.
# Step 1's ~23-25 minutes are not tolerance -- they are the CONTINUATION protocol (a cold
# multistart of the restricted problem, then a joint descent). START_SUBSET selects ONE start
# of the dispersed cold grid and, per the registry, implies multistart semantics: a single
# COLD start, the loop and the convergence test fully exercised, no warm start anywhere.
STEP1_ONE_COLD_START = {"HAFISCAL_STEP1_START_SUBSET": "1"}

# Step 2 estimates its three education groups SEQUENTIALLY (`for edType in edtypes_to_run`),
# and the first hot run timed them at 5 / 8 / 8 minutes (dropout / high school / college) --
# the largest single block of the whole 39-minute run. One group exercises the same code as
# three; HS (group 1) is the group HAFISCAL_HOT_SCOPE=HS_Only uses downstream, so the run
# stays self-consistent. The fit-table pass clears HAFISCAL_EDTYPES itself (do_all's
# `env -u`) and reads the real calibration, so it is unaffected. The BUG-121 mirror REFUSES
# to write a consolidated file for a partial run, which is correct and lands in scratch anyway.
STEP2_ONE_GROUP = {"HAFISCAL_EDTYPES": "1"}

COARSE_TOLERANCES = {
    # Step 1 (splurge; COBYQA/Powell over the Fagereng targets)
    "HAFISCAL_STEP1_FTOL": "1e-2",             # default 1e-5
    "HAFISCAL_STEP1_COBYQA_FINAL_TR": "1e-3",  # default 1e-8
    # Step 2, DEFAULT engine (estim_phase2_tm_a.py): its optimizer is COBYQA -- "S2 machinery
    # = S1" (owner 2026-08-19) -- and it reads HAFISCAL_STEP2_COBYQA_FINAL_TR. The first hot
    # run set only the NM_* pair below and Step 2 did not speed up at all: those knobs belong
    # to the `mc` engine (EstimAggFiscalMAIN.py) and never reach COBYQA. Labelled accordingly.
    "HAFISCAL_STEP2_COBYQA_FINAL_TR": "1e-3",  # default matches Step 1's 1e-8
    # Step 2, `mc` engine ONLY (HAFISCAL_STEP2_SIM_ENGINE=mc; Nelder-Mead) -- inert otherwise
    "HAFISCAL_NM_XATOL": "1e-1",               # built-in default 1e-2
    "HAFISCAL_NM_FATOL": "1e-1",               # built-in default 1e-2
}


def apply_tolerances(environ):
    """setdefault the coarse tolerances, so an explicit env still wins. Returns what it set."""
    applied = {}
    for k, v in {**COARSE_TOLERANCES, **STEP1_ONE_COLD_START, **STEP2_ONE_GROUP}.items():
        if not environ.get(k):
            environ[k] = v
            applied[k] = v
    return applied


def banner():
    return (
        "\n" + "=" * 78 + "\n"
        "  HOT RUN -- every live path executes; NO NUMBER IS QUOTABLE.\n"
        f"  scope={scope()}  seeds=1  outputs suffixed '{SUFFIX}'\n"
        "  This exists to prove the pipeline still composes, not to produce results.\n"
        "  Speed comes from COARSE OPTIMIZER TOLERANCES (the loop and the convergence\n"
        "  test still run, they just converge sooner) plus the reduced scope -- not\n"
        "  from warm-starting, which would skip the very code being tested.\n"
        "  Caches: the verified ones stay on (policy store re-checks every hit; the\n"
        "  AD-equilibrium store keys on world+flags). Nothing is warm-started beyond\n"
        "  them -- see hot_mode.__doc__ for why that would defeat the purpose.\n"
        + "=" * 78 + "\n"
    )


# Paper exhibit paths a hot run's children would otherwise write. Several generators
# hard-code these with no world or scope hook (estimBetas/nonTargetedMoments write
# Tables/CRRA2/ literally; CreateLPfig/CreateIMPCfig write the FromPandemicCode root), so
# the suffix cannot protect them and they are snapshotted instead.
_PROTECTED_RELATIVE = (
    "FromPandemicCode/Tables/CRRA2/estimBetas_candidate.ltx",
    "FromPandemicCode/Tables/CRRA2/nonTargetedMoments_candidate.ltx",
    "FromPandemicCode/LorenzPoints_CRRA_2.0_R_1.01_candidate.pdf",
    "FromPandemicCode/LorenzPoints_CRRA_2.0_R_1.01_wSplZero_candidate.pdf",
    "FromPandemicCode/IMPCs_both_candidate.pdf",
    "FromPandemicCode/IMPCs_wSplEstimated_candidate.pdf",
    "FromPandemicCode/IMPCs_wSplZero_candidate.pdf",
    "Results/AllResults_CRRA_2.0_R_1.01_ESC_candidate.txt",
    # Step 4's two products. Byte-identical across runs on an unchanged tree (measured
    # 2026-09-07: the Jacobians exactly, the multiplier pickle to 1.7e-11), so "unchanged vs
    # the snapshot" is the normal case and they must still be captured for the comparison.
    "FromPandemicCode/HA_Fiscal_Jacs.obj",
    "Results_HANK/multipliers_across_horizon_w_splurge.obj",
)

# THE CALIBRATION OF RECORD, and the reason this is not optional.
#
# Steps 1 and 2 do not write `_candidate` siblings -- they overwrite the real, GIT-TRACKED
# calibration files, in place. Under a hot run those estimates come from deliberately
# COARSE optimizer tolerances, so a hot run left unguarded would replace the calibration
# every later stage reads with a throwaway. That is the single worst thing this mode could
# do, and it is exactly the contamination it claims to be incapable of. Globs, not a fixed
# list: the file names carry CRRA/Rfree/interpretation/world suffixes, and a list would
# quietly stop covering a name the day one of those changed.
_PROTECTED_GLOBS = (
    "Target_AggMPCX_LiquWealth/Result_AllTarget*.txt",   # Step 1: the splurge (+ per-start files)
    "Results/DiscFacEstim_*.txt",                        # Step 2: the discount factors
    # Step 1 also draws the paper's lottery-MPC / liquid-wealth exhibits and writes two tables,
    # all six of them LOCKED_TABLES rows, under HAFISCAL_STEP1_PLOT=1 (the default) -- with
    # no scope hook, so a hot run would redraw them from a coarse-tolerance estimate.
    "Target_AggMPCX_LiquWealth/Figures/*_candidate.*",
    # Step 4 (HANK) is scope-independent and has no suffix hook at all. It rewrites the
    # household Jacobians -- a GIT-TRACKED 66 MB pickle -- the GE multiplier pickle the
    # briefing's section 5.3 numbers are read from, and six manifest figure exhibits, all
    # computed on whatever splurge Step 1 just left in place. Every one is protected.
    "FromPandemicCode/HA_Fiscal_Jacs*.obj",     # the UI_extend_real variant etc.
    "Results_HANK/*.obj",
    "FromPandemicCode/Figures/HANK_*_candidate.*",
    # Every fit-table output, not just the Baseline one: Step 3 (if a caller turns it on)
    # writes AllResults_*_Splurge0_*_candidate.txt through the same pass.
    "Results/AllResults_*_candidate.txt",
)


def protected_paths(ha_models_dir):
    import glob as _glob
    out = [os.path.join(ha_models_dir, r) for r in _PROTECTED_RELATIVE]
    for pat in _PROTECTED_GLOBS:
        out.extend(sorted(_glob.glob(os.path.join(ha_models_dir, pat))))
    return out


def store_dir(ha_models_dir):
    """A throwaway policy/equilibrium store for the hot run.

    The real store (~/.cache/hafiscal/policy_store) is per MACHINE and shared across every
    checkout. Its keys include the agent's Splurge, so a hot run's coarse-tolerance splurge
    could never COLLIDE with a real entry -- but every trial beta of a hot Step 1/2 and every
    hot equilibrium would still be SAVED there, as entries no real run can ever hit, for
    good. Pointing HAFISCAL_POLICY_STORE_DIR at a scratch directory removes the whole class:
    the store code still runs (SAVE, then HIT within the run -- Step 5b consuming Step 5a's
    equilibrium exercises the sharing path exactly as in production), nothing persists.
    """
    return os.path.join(ha_models_dir, ".hot_policy_store")


def results_out_dir(ha_models_dir):
    """Where Step 2 should be told to put its output instead of ../Results.

    `HAFISCAL_RESULTS_OUT_DIR` redirects Step 2's writes wholesale, which is strictly better
    than snapshot-and-restore: nothing is ever written to the real path, so even a hard kill
    (where the restore hook never runs) leaves the calibration untouched. Step 1 has no such
    knob, so it stays covered by the snapshot -- belt for one, braces for both.
    """
    return os.path.join(ha_models_dir, ".hot_results_out")


def snapshot(ha_models_dir, store_dir):
    """Copy every protected exhibit aside. Returns (saved, absent): what was copied, and
    which protected paths did NOT exist beforehand -- so that a file the hot run CREATES
    at one of those paths (a fresh clone has no Result_AllTarget_startpoint1_ESC.txt, say)
    is deleted on restore instead of surviving as a throwaway wearing a real name."""
    os.makedirs(store_dir, exist_ok=True)
    saved, absent = [], []
    for p in protected_paths(ha_models_dir):
        if os.path.exists(p):
            dst = os.path.join(store_dir, p.replace(os.sep, "__"))
            shutil.copy2(p, dst)
            saved.append((p, dst))
        else:
            absent.append(p)
    return saved, absent


def created_at_protected_patterns(ha_models_dir, saved):
    """Files that now match a protected pattern but were not there at snapshot time.

    A glob can only enumerate files that EXIST when it runs, so a file the run creates at a
    protected pattern -- `Result_AllTarget_startpoint1_ESC.txt` from a one-start Step 1, say --
    is in neither `saved` nor `absent`. Re-evaluating the patterns after the run finds it. Such
    a file is a hot result (capture it) wearing a real name (then delete it). Found the hard
    way on the first hot run, 2026-09-07: one survived, uncaptured."""
    known = {p for p, _ in saved}
    return [p for p in protected_paths(ha_models_dir) if p not in known and os.path.exists(p)]


def restore(saved, absent=(), ha_models_dir=None):
    """Put them back and PROVE it. A failed restore raises: a hot run that quietly leaves
    its throwaway numbers in the paper's exhibit paths is worse than no hot run at all."""
    import filecmp
    failed = []
    for p, dst in saved:
        shutil.copy2(dst, p)
        if not filecmp.cmp(p, dst, shallow=False):
            failed.append(p)
    removed = 0
    created = created_at_protected_patterns(ha_models_dir, saved) if ha_models_dir else []
    for p in list(absent) + created:
        if os.path.exists(p):
            os.remove(p); removed += 1
    if failed:
        raise RuntimeError(
            "HOT RUN could not restore these paper exhibits after the run: "
            + ", ".join(failed)
            + " -- restore them by hand from " + os.path.dirname(saved[0][1])
        )
    return len(saved) + removed


# ============================================================================ regression check
# WHAT A HOT RUN IS FOR (owner, 2026-09-07): "as fast as possible a method for checking whether
# anything we have done has introduced bugs in the core mainline code that, before we started a
# debugging session, ran successfully."  That is a REGRESSION check, and it needs three things a
# path exercise does not:
#   1. a REFERENCE -- the same hot configuration run on the known-good tree, its outputs kept;
#   2. the hot outputs CAPTURED before the restore erases them (the Step-4 pickles, the Step-1
#      splurge, the fit-pass tables are all protected paths, so without a capture the very
#      results a regression check would diff are thrown away to keep the tree clean);
#   3. a COMPARISON whose tolerance comes from a measured same-tree repeat, not a guess: run hot
#      twice on one tree, and whatever is not byte-identical between the two is the noise floor.
# Inputs are held fixed so that only code varies: Steps 4/5 read the real calibration (Step 2's
# output is redirected), so a difference in their output is a CODE difference.

import hashlib
import json
import re
import subprocess

NUMERIC_EXT = (".tex", ".ltx", ".txt", ".csv", ".json")
BINARY_EXT = (".obj", ".pkl")


def _looks_like_pickle(path):
    """A pickle by MAGIC, whatever its extension: Step 5a's MC arm writes its base_results as a
    pickle named `.csv` (found 2026-09-07 when the adoption of the strata shuffle changed it and the
    text path reported 'structure: number count differs or unreadable' instead of a difference)."""
    try:
        with open(path, "rb") as fh:
            return fh.read(1) == b"\x80"
    except OSError:
        return False
FIGURE_EXT = (".pdf", ".png", ".jpg", ".svg")
_FLOAT = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
# Keys of welfare6_parallel_summary.json that are timings, not results.
_SUMMARY_TIMING_KEYS = ("cpu_sum_s", "longest_s", "wall_clock_s", "per_scenario")


def _is_sidecar(name):
    return name.startswith("RUN_") and name.endswith(".prov.json")


def hot_outputs(ha_models_dir, saved):
    """Every file the hot run produced that a regression check should see.

    The protected set has two kinds of member. The explicit list (`_PROTECTED_RELATIVE`) is
    the run's PRODUCTS -- captured always, even when byte-identical to the snapshot, because
    "unchanged" is the normal case and the comparison needs them. The globs are a BACKSTOP
    against overwrites (a hundred-odd calibration variants the run never touches); a backstop
    file is a hot output only if the run changed or created it. The first reference blessed
    without this distinction carried ~110 untouched calibration files and buried the signal."""
    import filecmp
    products = {os.path.join(ha_models_dir, r) for r in _PROTECTED_RELATIVE}
    out = []
    for p, dst in saved:
        if not os.path.exists(p):
            continue
        if p in products or not filecmp.cmp(p, dst, shallow=False):
            out.append(p)
    out += created_at_protected_patterns(ha_models_dir, saved)  # what the run created there
    roots = [results_out_dir(ha_models_dir)]
    fpc = os.path.join(ha_models_dir, "FromPandemicCode")
    for sub in ("Tables", "Figures"):
        base = os.path.join(fpc, sub)
        if os.path.isdir(base):
            roots += [os.path.join(base, d) for d in os.listdir(base) if d.endswith(SUFFIX)]
    for root in roots:
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                if not _is_sidecar(fn):
                    out.append(os.path.join(dp, fn))
    return sorted(set(out))


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(ha_models_dir, *args):
    try:
        return subprocess.run(["git", "-C", ha_models_dir, *args], capture_output=True,
                              text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def capture(ha_models_dir, saved, run_dir):
    """Copy every hot output into run_dir (tree-relative) and write MANIFEST.json. Call this
    BEFORE restore(): for a protected path the hot result exists only until then."""
    os.makedirs(run_dir, exist_ok=True)
    files = {}
    for p in hot_outputs(ha_models_dir, saved):
        rel = os.path.relpath(p, ha_models_dir)
        dst = os.path.join(run_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(p, dst)
        files[rel] = _sha(p)
    manifest = {
        "head": _git(ha_models_dir, "rev-parse", "--short", "HEAD"),
        # TRACKED modifications only: `--porcelain` alone counts untracked files, and this tree
        # always has some (logs, scratch), so the flag read True on a clean tree (2026-09-07).
        "dirty": bool(_git(ha_models_dir, "status", "--porcelain", "--untracked-files=no")),
        "scope": scope(),
        "tolerances": {**COARSE_TOLERANCES, **STEP1_ONE_COLD_START, **STEP2_ONE_GROUP},
        "files": files,
    }
    with open(os.path.join(run_dir, "MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    return len(files)


def _numbers(path):
    """The numbers in a text artifact, in file order -- structure and order both matter."""
    if path.endswith(".json"):
        try:
            d = json.load(open(path))
        except Exception:
            return None
        if isinstance(d, dict) and "welfare6" in d:          # a battery summary: cells only
            d = {k: v for k, v in d.items() if k not in _SUMMARY_TIMING_KEYS}
        return [float(m) for m in _FLOAT.findall(json.dumps(d, sort_keys=True))]
    try:
        text = open(path, errors="replace").read()
    except Exception:
        return None
    return [float(m) for m in _FLOAT.findall(text)]


def _binary_numbers(path):
    """Flatten a pickle of arrays/dicts of arrays into one number list; None if not that shape."""
    try:
        import pickle
        import numpy as np
        obj = pickle.load(open(path, "rb"))
    except Exception:
        return None
    out = []

    def walk(o):
        if isinstance(o, dict):
            for k in sorted(o, key=str):
                walk(o[k])
        elif isinstance(o, (list, tuple)):
            for x in o:
                walk(x)
        else:
            try:
                out.extend(np.asarray(o, dtype=float).ravel().tolist())
            except Exception:
                pass
    walk(obj)
    return out or None


def _max_rel(a, b):
    """Largest relative difference (absolute where the reference is ~0); None on a structure change."""
    if a is None or b is None or len(a) != len(b):
        return None
    worst = 0.0
    for x, y in zip(a, b):
        d = abs(x - y) / abs(y) if abs(y) > 1e-12 else abs(x - y)
        worst = max(worst, d)
    return worst


def tolerance():
    """The comparison tolerance, `HAFISCAL_HOT_TOL` (default 0 = byte identity).

    What was measured 2026-09-07, and a retraction. Two runs of identical code with the same
    warm store agreed byte-for-byte on 181 of 209 captured files, on the welfare summary and the
    multiplier table; the HANK multiplier pickle differed by 1.95e-11 (parallel summation order,
    absorbed by BINARY_TOL below); and the fit-table pass differed by 4e-3 to 1.6e-2 -- on
    exactly four lines, the lottery-win MPC block, whose lottery quarters were drawn from the
    UNSEEDED global RNG (BUG-127, since fixed). An earlier version of this docstring blamed the
    policy store's 1e-3 verify tolerance propagating into wealth statistics; that was a guess
    stated as fact. Lorenz points and median wealth were byte-identical in every comparison.
    With BUG-127 fixed the expected hot-vs-hot floor is 0 (text) and BINARY_TOL (pickles). Set
    HAFISCAL_HOT_TOL only when you have MEASURED a floor above that."""
    v = os.environ.get("HAFISCAL_HOT_TOL", "").strip()
    return float(v) if v else 0.0


# Pickled arrays from parallel stages differ run-to-run at summation-order level: the HANK
# multiplier pickle at 1.95e-11 on identical code (measured 2026-09-07). That is not a change.
BINARY_TOL = 1e-9


def compare(reference_dir, run_dir, rel_tol=0.0):
    """Per-file verdict of run_dir against reference_dir. Returns (rows, n_changed).

    rel_tol is the measured noise floor -- 0.0 until a same-tree repeat says otherwise. Figures
    are reported but never counted: they carry no numbers a check can read; the CSVs and tables
    they were drawn from are compared instead."""
    ref = json.load(open(os.path.join(reference_dir, "MANIFEST.json")))["files"]
    run = json.load(open(os.path.join(run_dir, "MANIFEST.json")))["files"]
    rows, changed = [], 0
    for rel in sorted(set(ref) | set(run)):
        if rel not in ref or rel not in run:
            where = "reference" if rel not in ref else "this run"
            rows.append((rel, f"MISSING in {where}"))
            changed += 1
            continue
        if ref[rel] == run[rel]:
            rows.append((rel, "identical"))
            continue
        pr, pn = os.path.join(reference_dir, rel), os.path.join(run_dir, rel)
        if rel.endswith(FIGURE_EXT):
            rows.append((rel, "bytes differ (figure; not counted -- see its CSV/table)"))
            continue
        is_bin = rel.endswith(BINARY_EXT) or _looks_like_pickle(os.path.join(run_dir, rel))
        nums = (_binary_numbers(pr), _binary_numbers(pn)) if is_bin else (_numbers(pr), _numbers(pn))
        d = _max_rel(nums[1], nums[0])
        tol = max(rel_tol, BINARY_TOL) if is_bin else rel_tol
        if d is None:
            rows.append((rel, "CHANGED (structure: number count differs or unreadable)"))
            changed += 1
        elif d <= tol:
            rows.append((rel, f"within tolerance (max rel diff {d:.2e} <= {tol:.1e})"))
        else:
            rows.append((rel, f"CHANGED (max rel diff {d:.2e})"))
            changed += 1
    return rows, changed


def write_report(rows, changed, reference_dir, run_dir, path):
    with open(path, "w") as fh:
        fh.write(f"# HOT regression check\n\nreference: `{reference_dir}`\nthis run: `{run_dir}`\n\n")
        fh.write(f"**{'NO REGRESSION' if changed == 0 else f'{changed} file(s) CHANGED'}**\n\n")
        figs = [rel for rel, v in rows if v.startswith("bytes differ (figure")]
        if figs:
            fh.write(f"*{len(figs)} figure file(s) differ in bytes and are not compared -- SVG/PDF "
                     f"embed per-run object ids; the CSVs and tables they are drawn from are.*\n\n")
        fh.write("| file | verdict |\n|---|---|\n")
        for rel, v in rows:
            if not v.startswith("bytes differ (figure"):
                fh.write(f"| `{rel}` | {v} |\n")
    return path


def newest_run(ha_models_dir):
    """The most recent hot run -- by its MANIFEST's mtime, never by name.

    The first naming scheme was <HEAD8>_<stamp>, and a lexicographic sort put `b36d4200_...`
    (run 3) after `933ee32f_...` (runs 4 and 5): `make hot-reference` blessed the wrong run
    and `make hot-check` compared against it (2026-09-07). Directories are now named
    <stamp>_<HEAD8> so that name order IS time order, and this function sorts by mtime
    regardless, so an old-style directory cannot win."""
    runs = os.path.join(ha_models_dir, "hot_runs")
    if not os.path.isdir(runs):
        return None
    cands = [os.path.join(runs, d) for d in os.listdir(runs)
             if os.path.exists(os.path.join(runs, d, "MANIFEST.json"))]
    if not cands:
        return None
    return max(cands, key=lambda d: os.path.getmtime(os.path.join(d, "MANIFEST.json")))


def bless(ha_models_dir, run_dir=None):
    """Make a hot run the reference. Run `make hot` on the KNOWN-GOOD tree first; then this."""
    runs = os.path.join(ha_models_dir, "hot_runs")
    if run_dir is None:
        run_dir = newest_run(ha_models_dir)
        if run_dir is None:
            raise SystemExit("no hot run to bless: run `make hot` first")
    ref = os.path.join(ha_models_dir, "hot_reference")
    if os.path.isdir(ref):
        shutil.rmtree(ref)
    shutil.copytree(run_dir, ref)
    return ref


if __name__ == "__main__":
    import sys
    _ha = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) >= 2 and sys.argv[1] == "bless":
        print("reference <-", bless(_ha, sys.argv[2] if len(sys.argv) > 2 else None))
    elif len(sys.argv) == 4 and sys.argv[1] == "compare":
        rows, n = compare(sys.argv[2], sys.argv[3])
        for rel, v in rows:
            print(f"  {v:60s} {rel}")
        print("NO REGRESSION" if n == 0 else f"{n} CHANGED")
        sys.exit(0 if n == 0 else 2)
    else:
        print("usage: hot_mode.py bless [run_dir] | compare <reference_dir> <run_dir>")
