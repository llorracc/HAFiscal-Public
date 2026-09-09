#!/usr/bin/env python3
"""Archive a pipeline stage's stdout log under the run_id of the provenance sidecar it produced.

Why (BUG-088 follow-up (f), plans_local/TODO.md, 2026-08-24): the June 2026 Step-5a run whose
spurious ATI fixed point tripped the PF-decay guard left NO stdout log -- only its error text
survived in a chat transcript -- so the diagnosis had to be reconstructed from probes. Every
Step-5a/2/5b launch already writes a per-stage log (the coldrun/spine drivers redirect stdout),
and every run writes a travelling ``RUN_<run_id>.prov.json`` sidecar next to its outputs
(``provenance.py``). This helper joins the two: after a stage finishes it copies the stage log to
``<archive>/RUN_<run_id>.log`` (default archive ``~/coldrun_2026-08/stage_logs``, override with
``HAFISCAL_STAGE_LOG_ARCHIVE``), keyed by the NEWEST sidecar in the outputs directory, and appends
one line to ``<archive>/INDEX.tsv`` (run_id, stage, host, original log path, sidecar). The
provenance reverse-lookup (``provenance.py show <result>``) gives the run_id; this gives the log.

Usage:  archive_step_log.py <stage-log> <outputs-dir> [--stage NAME] [--min-age-s N]
Exit 0 always for a missing sidecar (a stage that produced none has nothing to key on); it
says so on stderr. Never modifies the outputs directory.
"""
import argparse, glob, json, os, shutil, socket, sys, time


def newest_sidecar(outputs_dir, min_age_s=0.0):
    cands = glob.glob(os.path.join(outputs_dir, "RUN_*.prov.json"))
    cands = [c for c in cands if time.time() - os.path.getmtime(c) >= min_age_s]
    return max(cands, key=os.path.getmtime) if cands else None


def archive(log, outputs_dir, stage=None, archive_dir=None, min_age_s=0.0):
    archive_dir = archive_dir or os.environ.get(
        "HAFISCAL_STAGE_LOG_ARCHIVE", os.path.expanduser("~/coldrun_2026-08/stage_logs"))
    side = newest_sidecar(outputs_dir, min_age_s)
    if side is None:
        print(f"[archive_step_log] no RUN_*.prov.json under {outputs_dir}; nothing archived "
              f"for {log}", file=sys.stderr)
        return None
    try:
        run_id = json.load(open(side)).get("run_id") or os.path.basename(side)[4:-10]
    except Exception:
        run_id = os.path.basename(side)[4:-10]
    os.makedirs(archive_dir, exist_ok=True)
    dst = os.path.join(archive_dir, f"RUN_{run_id}.log")
    if os.path.exists(dst) and os.path.getsize(dst) != os.path.getsize(log):
        dst = os.path.join(archive_dir, f"RUN_{run_id}_{int(time.time())}.log")
    shutil.copy2(log, dst)
    shutil.copy2(side, os.path.join(archive_dir, os.path.basename(side)))
    with open(os.path.join(archive_dir, "INDEX.tsv"), "a") as f:
        f.write("\t".join([run_id, stage or "?", socket.gethostname(),
                           time.strftime("%Y-%m-%dT%H:%M:%S"), os.path.abspath(log), side]) + "\n")
    print(f"[archive_step_log] {log} -> {dst} (run_id {run_id}, sidecar {os.path.basename(side)})")
    return dst


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log"); ap.add_argument("outputs_dir")
    ap.add_argument("--stage", default=None)
    ap.add_argument("--archive-dir", default=None)
    ap.add_argument("--min-age-s", type=float, default=0.0,
                    help="ignore sidecars younger than this (a still-writing run)")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.log):
        print(f"[archive_step_log] no such log: {a.log}", file=sys.stderr); return 0
    archive(a.log, a.outputs_dir, a.stage, a.archive_dir, a.min_age_s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
