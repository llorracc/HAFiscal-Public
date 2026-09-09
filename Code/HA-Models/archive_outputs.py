#!/usr/bin/env python3
"""archive_outputs -- route superseded outputs to conclusions_private/artifacts_<date>_<topic>/; never move or rename a
tracked result directory; never leave a superseded directory where a tabulator glob can see it. Infrastructure plan A3
phase 1 (2026-08-28), narrowed by the prior-art review: no new Tables/_archive/ root and no second registry
(Code/HA-Models/_registry.py IS the registry; phase 2 withdrawn).

Why. Two incidents on 2026-08-27, one mistake: a rename inside an output root that other code reads by pattern.
(1) The appendix launcher's `mv Tables/$NAME Tables/${NAME}_pre_reissue_20260827` (rerun_logs/ui_ext_20260826/p29_common.sh)
    displaced Rfree_1005, Rfree_1015 and Rspell_4 -- TRACKED directories holding the published, locked tables; they were
    restored with `git checkout`. The candidate workflow writes `*_candidate.tex` BESIDE the locked files, so there was
    nothing to move in the first place.
(2) Superseded battery directories renamed in place -- Baseline_orig_typo_seed0_pre_mimic_20260827,
    Baseline_orig_pgf_reest_seed0_uncapped_wrong_20260827 -- still matched the tabulators' `Tables/<arm>_seed*` globs, so
    a waterfall column showed S = 5 from the wrong arm until they were moved to Tables/_quarantine_20260827/.

Usage
    archive_outputs.py move SRC... --to artifacts_<YYYYMMDD>_<topic> [--superseded] [--note TEXT] [--dry-run]
        Moves each SRC (a file or directory inside this checkout) to conclusions_private/artifacts_<date>_<topic>/<basename>
        and appends one line per move to that directory's MANIFEST.md (timestamp, HEAD, original path, file count and
        size, sha256 of every *_candidate.tex and *summary*.json inside, why, note). All-or-nothing: if any SRC is
        refused, nothing moves.
        REFUSED: a SRC with any tracked file under it (`git ls-files --error-unmatch`) -- tracked result directories
                 are never moved or renamed; if a published directory must change, that is a git operation;
                 a SRC under Tables/ whose first path component matches the tabulators' glob shape `*_seed[0-9]*`
                 (TABULATOR_GLOBS below) unless --superseded declares it a superseded battery -- moving a live seed
                 directory silently changes a column's S;
                 a SRC already under conclusions_private/, outside the checkout, a symlink, nested in another SRC, or
                 whose destination already exists (never merge two archives silently).
        --dry-run prints the verdicts and moves nothing: the launcher preflight (exit 1 = do not `mv` this).
    archive_outputs.py check [TABLES_DIR]
        Lists directories under Tables/ that look superseded (a SUPERSEDED_MARKERS name part such as _pre_reissue,
        _quarantine, _old, _previous, _wrong, or a suffix after the seed number) but still match a `<arm>_seed*` glob.
        Superseded-looking directories that no glob matches are listed as notes (harmless to the tabulators).
Exit codes: 0 = done / clean; 1 = refused or flagged (nothing moved); 2 = usage or I/O error.
Nothing is staged. Record an archive with `git add -f conclusions_private/artifacts_<date>_<topic>` (`*_candidate.tex` is
gitignored, so a plain `git add` skips exactly the files that matter); leave large pickles out of git.
"""
import argparse
import datetime
import fnmatch
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABLES_REL = os.path.join("Code", "HA-Models", "FromPandemicCode", "Tables")
ARCHIVE_ROOT_REL = "conclusions_private"
ARCHIVE_NAME_RE = re.compile(r"^artifacts_(\d{8})_[A-Za-z0-9][A-Za-z0-9_.-]*$")

# The tabulators' input globs (read from the four files on 2026-08-28). Every one is `Tables/<arm>_seed*/<file>`, one
# level under Tables/, so the shape this tool protects is "a direct child of Tables/ whose name contains `_seed<digit>`"
# (SEED_DIR_RE). The 5a directories the same tabulators read by EXACT name (Tables/<arm>/Multiplier_candidate.tex) are not
# glob inputs: moving one fails loudly (missing file) rather than silently, and the tracked ones are refused anyway.
TABULATOR_GLOBS = (
    ("waterfall_table.py", "Tables/<arm>_seed*/welfare6_parallel_summary.json",
     "arms Baseline_ac_legacy_nshuf, Baseline_ac_pkg, Baseline_ac_impr, Baseline_uiA, Baseline_uiA_nshare, Baseline_uiB, "
     "Baseline_uiL_nshuf, Baseline_uiL_permoff_nshuf, Baseline_orig_typo, Baseline_nocap_pkg, plus --arm NAME=5a_dir:welfare_glob"),
    ("corrections_breakdown_table.py", "Tables/Baseline_<tag>_seed*/welfare6_parallel_summary.json",
     "by_seed(): tags orig, orig_typo, orig_pgf_reest, orig_pfx, ac_pkg, ..."),
    ("robustness_appendix_tables.py", "Tables/<config>[_histB]_seed*/welfare4_candidate.tex",
     "plus Tables/Baseline_uiA_seed*/ and Tables/Baseline_uiB_seed*/ as the Baseline reference; the UI-policy block "
     "(Econ-7) reads welfare6_parallel_summary.json from Baseline_uiA/uiB_seed* and LowerUBnoB[_histB]_seed*"),
    ("welfare6_seedband.py, FromPandemicCode/compute_welfare6_se_table.py", "explicit paths",
     "the launchers (rerun_logs/ui_ext_20260826/p29_common.sh) pass Tables/${NAME}_seed{0,1,2}/welfare6_parallel_summary.json"),
)
SEED_DIR_RE = re.compile(r"_seed\d")            # the shape every glob above shares
SEED_SUFFIX_RE = re.compile(r"_seed\d+[^\d]")   # a suffix after the seed number: <arm>_seed0_pre_mimic_20260827
SUPERSEDED_MARKERS = ("_pre_reissue", "_pre_mimic", "_quarantine", "_old", "_previous", "_wrong", "_superseded",
                      "_stale", "_backup", "_bak", "_broken")
HASH_PATTERNS = ("*_candidate.tex", "*summary*.json")


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)


def repo_root_for(path):
    """The toplevel of the checkout containing `path` (a file or directory), or None."""
    d = path if os.path.isdir(path) else os.path.dirname(path)
    r = git(d, "rev-parse", "--show-toplevel")
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def tracked_files(repo, rel):
    """Tracked files under the repo-relative path `rel` (`git ls-files --error-unmatch`; empty when untracked)."""
    r = git(repo, "ls-files", "--error-unmatch", "--", ":(literal)" + rel)
    return [ln for ln in r.stdout.splitlines() if ln] if r.returncode == 0 else []


def head_sha(repo):
    r = git(repo, "rev-parse", "--short", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else "no-HEAD"


def glob_protected(rel):
    """The `<arm>_seed*` glob that sees the repo-relative path `rel`, or None (only direct children of Tables/ count)."""
    inside = os.path.relpath(rel, TABLES_REL)
    if inside.startswith(".."):
        return None
    first = inside.split(os.sep)[0]
    return first.split("_seed")[0] + "_seed*" if SEED_DIR_RE.search(first) else None


def walk_files(path):
    if os.path.isfile(path):
        yield path
        return
    for root, _dirs, files in os.walk(path):
        for f in sorted(files):
            yield os.path.join(root, f)


def hashes_for(path):
    """`relname=sha256:<hex>` for every *_candidate.tex / *summary*.json under `path`."""
    out = []
    for f in walk_files(path):
        if any(fnmatch.fnmatch(os.path.basename(f), p) for p in HASH_PATTERNS):
            rel = os.path.basename(f) if os.path.isfile(path) else os.path.relpath(f, path)
            out.append(f"{rel}=sha256:{hashlib.sha256(open(f, 'rb').read()).hexdigest()}")
    return out


def size_of(path):
    n, b = 0, 0
    for f in walk_files(path):
        n += 1
        b += os.path.getsize(f)
    return n, b


def fmt_bytes(b):
    return f"{b / 1e6:.1f} MB" if b >= 1e6 else f"{b / 1e3:.1f} KB"


def archive_dir(repo, to):
    """Validate --to (a bare `artifacts_<date>_<topic>` or that name under conclusions_private/); return its abspath."""
    name = os.path.basename(to.rstrip("/"))
    parent = os.path.dirname(to.rstrip("/"))
    root = os.path.join(repo, ARCHIVE_ROOT_REL)
    if parent and os.path.realpath(parent) != os.path.realpath(root):
        raise SystemExit(f"archive_outputs: --to must be artifacts_<date>_<topic> under {ARCHIVE_ROOT_REL}/ (got {to})")
    m = ARCHIVE_NAME_RE.match(name)
    if not m:
        raise SystemExit(f"archive_outputs: --to must match artifacts_<YYYYMMDD>_<topic> (got {name})")
    try:
        datetime.datetime.strptime(m.group(1), "%Y%m%d")
    except ValueError:
        raise SystemExit(f"archive_outputs: --to carries no valid date: {name}")
    return os.path.join(root, name)


MANIFEST_HEADER = """# MANIFEST -- superseded outputs archived here by `Code/HA-Models/archive_outputs.py`

Convention (Code/HA-Models/docs/FILE_FAMILIES.md, section 10): superseded outputs leave their output roots (Tables/,
welfare6_scenario_results_*, rerun_logs/) for conclusions_private/artifacts_<date>_<topic>/; tracked result directories
are never moved or renamed. One line per move:
`- <timestamp> | HEAD <sha> | <original path> -> <archived as> | <files, size> | <sha256 per *_candidate.tex / *summary*.json> | <why> | <note>`

"""


def cmd_move(args):
    srcs = []
    for s in args.src:
        a = os.path.abspath(s)
        if not os.path.lexists(a):
            raise SystemExit(f"archive_outputs: no such path: {s}")
        if os.path.islink(a):
            raise SystemExit(f"archive_outputs: {s} is a symlink -- archive the target, not the link")
        srcs.append(a)
    roots = {repo_root_for(a) for a in srcs}
    if len(roots) != 1 or None in roots:
        raise SystemExit("archive_outputs: every SRC must live in one git checkout (found: %s)" % ", ".join(map(str, roots)))
    repo = roots.pop()
    for a in srcs:
        for b in srcs:
            if a != b and b.startswith(a + os.sep):
                raise SystemExit(f"archive_outputs: {os.path.relpath(b, repo)} is inside {os.path.relpath(a, repo)} -- pass one of them")
    dest_root = archive_dir(repo, args.to)
    dest_rel = os.path.relpath(dest_root, repo)

    verdicts = []            # (rel, status, detail, dest, why)
    seen = {}
    for a in srcs:
        rel = os.path.relpath(os.path.realpath(a), repo)
        base = os.path.basename(a)
        dest = os.path.join(dest_root, base)
        if rel.startswith(".."):
            verdicts.append((rel, "REFUSED", "outside the checkout", dest, None)); continue
        if rel.split(os.sep)[0] == ARCHIVE_ROOT_REL:
            verdicts.append((rel, "REFUSED", f"already under {ARCHIVE_ROOT_REL}/", dest, None)); continue
        tracked = tracked_files(repo, rel)
        if tracked:
            hint = ("; the candidate workflow writes *_candidate.tex beside the locked files -- leave it in place"
                    if rel.startswith(TABLES_REL) else "")
            verdicts.append((rel, "REFUSED", f"tracked ({len(tracked)} files, e.g. {os.path.basename(tracked[0])}): "
                             f"tracked result directories are never moved or renamed{hint}", dest, None)); continue
        g = glob_protected(rel)
        if g and not args.superseded:
            verdicts.append((rel, "REFUSED", f"matched by the tabulators' glob Tables/{g} (a live column input): "
                             "pass --superseded to declare it a superseded battery", dest, None)); continue
        if os.path.lexists(dest) or base in seen:
            verdicts.append((rel, "REFUSED", f"destination exists: {os.path.join(dest_rel, base)} (never merged silently; "
                             "use another --to topic)", dest, None)); continue
        seen[base] = rel
        verdicts.append((rel, "OK", f"matched by Tables/{g}; declared superseded" if g else "untracked, not a glob input",
                         dest, f"superseded battery (--superseded; Tables/{g})" if g else "archived"))

    refused = [v for v in verdicts if v[1] == "REFUSED"]
    for rel, status, detail, dest, _why in verdicts:
        if status == "REFUSED":
            print(f"REFUSED  {rel}   {detail}")
        else:
            print(f"{'WOULD MOVE' if args.dry_run else 'OK'}  {rel} -> {os.path.join(dest_rel, os.path.basename(dest))}   ({detail})")
    if refused:
        print(f"archive_outputs: {len(refused)} refused, 0 moved -- nothing moved (all-or-nothing).")
        return 1
    if args.dry_run:
        print(f"archive_outputs: dry run -- {len(verdicts)} would move to {dest_rel}/; nothing moved.")
        return 0

    os.makedirs(dest_root, exist_ok=True)
    manifest = os.path.join(dest_root, "MANIFEST.md")
    if not os.path.exists(manifest):
        with open(manifest, "w") as f:
            f.write(MANIFEST_HEADER)
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    head = head_sha(repo)
    big = []
    with open(manifest, "a") as man:
        for rel, _status, _detail, dest, why in verdicts:
            src = os.path.join(repo, rel)
            hashes = hashes_for(src)
            n, b = size_of(src)
            shutil.move(src, dest)
            archived = os.path.join(os.path.basename(dest_root), os.path.basename(dest))
            note = f" | note: {args.note}" if args.note else ""
            man.write(f"- {stamp} | HEAD {head} | {rel} -> {archived} | {n} files, {fmt_bytes(b)} | "
                      f"{' '.join(hashes) if hashes else 'no *_candidate.tex / *summary*.json'} | {why}{note}\n")
            print(f"MOVED    {rel} -> {os.path.join(dest_rel, os.path.basename(dest))}   ({n} files, {fmt_bytes(b)}; {len(hashes)} hashed)")
            if b > 200e6:
                big.append((rel, b))
    print(f"archive_outputs: {len(verdicts)} moved to {dest_rel}/; manifest {os.path.join(dest_rel, 'MANIFEST.md')}")
    print(f"not staged: `git add -f {dest_rel}` records it (*_candidate.tex is gitignored).")
    for rel, b in big:
        print(f"note: {rel} is {fmt_bytes(b)} -- keep pickles of that size out of git")
    return 0


def scan_tables(tables_dir, repo=None):
    """(flagged, notes, tracked): superseded-looking dirs a `<arm>_seed*` glob still matches; superseded-looking dirs no
    glob matches; glob-matched superseded-looking dirs that are TRACKED (left alone: not this tool's business)."""
    flagged, notes, tracked = [], [], []
    for d in sorted(os.listdir(tables_dir)):
        p = os.path.join(tables_dir, d)
        if not os.path.isdir(p) or d.startswith("."):
            continue
        markers = [m for m in SUPERSEDED_MARKERS if m in d.lower()]
        suffix = bool(SEED_SUFFIX_RE.search(d))
        if SEED_DIR_RE.search(d) and (markers or suffix):
            if repo and tracked_files(repo, os.path.relpath(os.path.realpath(p), repo)):
                tracked.append(d); continue
            reason = ("marker " + ", ".join(markers)) if markers else "a suffix after the seed number"
            flagged.append((d, reason, d.split("_seed")[0] + "_seed*"))
        elif markers:
            notes.append((d, ", ".join(markers)))
    return flagged, notes, tracked


def cmd_check(args):
    tables = os.path.abspath(args.tables) if args.tables else os.path.join(repo_root_for(HERE) or os.path.dirname(os.path.dirname(HERE)), TABLES_REL)
    if not os.path.isdir(tables):
        raise SystemExit(f"archive_outputs: not a directory: {tables}")
    repo = repo_root_for(tables)
    flagged, notes, tracked = scan_tables(tables, repo)
    for d, reason, g in flagged:
        print(f"FLAGGED  {d}   {reason}; still matched by Tables/{g} (waterfall / corrections / robustness tabulators)")
    for d, m in notes:
        print(f"note     {d}   superseded-looking (marker {m}); no _seed glob matches it -- archive when convenient")
    for d in tracked:
        print(f"tracked  {d}   glob-shaped name with a marker or seed suffix, but TRACKED -- left alone (a git matter)")
    if flagged:
        print(f"archive_outputs check: {len(flagged)} flagged in {tables} -- archive them with")
        print(f"  python {os.path.relpath(os.path.abspath(__file__))} move {' '.join(os.path.join(TABLES_REL, d) for d, _, _ in flagged[:3])}"
              f"{' ...' if len(flagged) > 3 else ''} --to artifacts_<date>_<topic> --superseded")
        return 1
    print(f"archive_outputs check: clean -- no superseded-looking directory matches a tabulator glob in {tables}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="archive_outputs.py", description=__doc__.split("\n\nWhy.")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    mv = sub.add_parser("move", help="move superseded outputs to conclusions_private/artifacts_<date>_<topic>/")
    mv.add_argument("src", nargs="+", help="files or directories inside this checkout")
    mv.add_argument("--to", required=True, help="artifacts_<YYYYMMDD>_<topic> (created under conclusions_private/)")
    mv.add_argument("--superseded", action="store_true", help="declare *_seed[0-9]* directories superseded (else refused)")
    mv.add_argument("--note", default=None, help="free text appended to each manifest line")
    mv.add_argument("--dry-run", action="store_true", help="print verdicts; move nothing (launcher preflight)")
    mv.set_defaults(fn=cmd_move)
    ck = sub.add_parser("check", help="list superseded-looking Tables/ directories a tabulator glob still matches")
    ck.add_argument("tables", nargs="?", default=None, help=f"Tables directory (default: this checkout's {TABLES_REL})")
    ck.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
