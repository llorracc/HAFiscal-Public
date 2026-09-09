"""step2_mirror.py — BUG-121 (2026-09-03): put Step 2's re-estimate where the pipeline actually reads it.

The a-indexed Step-2 engine (`estim_phase2_tm_a.py`, the default since 2026-06-23) writes its consolidated
discount-factor estimate to `DiscFacEstim_<CRRA>_R_<R>_TM_a<calib_suffix>.txt`. Every downstream consumer —
`Parameters.py` (Steps 5a/5b, all parametrizations) and `step4/hh_setup` (the HANK stage) — resolves the
UN-tagged `DiscFacEstim_<CRRA>_R_<R><calib_suffix>.txt`; only gate/diagnostic tools read the `_TM_a` file.
The canonical wrapper (`run_phase2_parallel.py`) mirrors one into the other; `do_all` calls the engine directly
and never did, so a from-scratch `do_all` wrote a re-estimate and then ran Steps 4/5 on the tracked betas
(both 2026-09-02 cold runs). This helper is the mirror, on the engine's own path.

Rules: mirror only a COMPLETE consolidated file (all three education groups + the footer) — a single-group
run must never overwrite the downstream file with one row; byte-for-byte copy (the downstream reader
`eval`s the dict rows and skips the footer line); opt out with HAFISCAL_STEP2_MIRROR=0.
"""
import os
import shutil

OPT_OUT_FLAG = "HAFISCAL_STEP2_MIRROR"
N_GROUPS = 3


def mirror_enabled():
    return os.environ.get(OPT_OUT_FLAG, "1").strip().lower() not in ("0", "off", "false", "no")


def read_rows(path):
    """The (EducationGroup, beta, nabla, GICx) rows of a DiscFacEstim file (the reader's own convention)."""
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("{") and "EducationGroup" in line:
            d = eval(line)  # the files are repr()'d dicts of floats; matches Parameters.py's reader
            rows.append((int(d["EducationGroup"]), float(d["beta"]), float(d["nabla"]), float(d["GICx"])))
    return rows


def downstream_path(out_dir, df_base, calib_suffix):
    """The un-tagged file the consumers resolve: `<out_dir>/<df_base><calib_suffix>.txt`."""
    return os.path.join(out_dir, df_base + calib_suffix + ".txt")


def mirror_consolidated(tm_a_path, out_dir, df_base, calib_suffix, verbose=True):
    """Copy the consolidated `_TM_a` file to the downstream canonical name. Returns the path written,
    or None (opted out / incomplete file — refused, with the reason printed)."""
    if not mirror_enabled():
        if verbose:
            print(f"  [BUG-121 mirror] skipped: {OPT_OUT_FLAG}=0")
        return None
    rows = read_rows(tm_a_path)
    groups = sorted(r[0] for r in rows)
    if groups != list(range(N_GROUPS)):
        if verbose:
            print(f"  [BUG-121 mirror] REFUSED: {os.path.basename(tm_a_path)} carries groups {groups}, "
                  f"not all {N_GROUPS} — a partial run must not overwrite the downstream file")
        return None
    dst = downstream_path(out_dir, df_base, calib_suffix)
    shutil.copyfile(tm_a_path, dst)
    if verbose:
        print(f"  [BUG-121 mirror] {os.path.basename(tm_a_path)} -> {os.path.basename(dst)} "
              f"(the file Steps 4/5a/5b read)")
    return dst
