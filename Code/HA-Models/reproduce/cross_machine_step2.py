#!/usr/bin/env python3
"""Distribute Step-2 discount-factor estimation across machines (one education
group per machine), gather the per-group result files back to dell, and report
per-(group, machine) wall time. Optionally merge + finalize for a real run.

Each group is run via the EXISTING single-group machinery:
    HAFISCAL_EDTYPES={N} HAFISCAL_SERIAL=1 python -u EstimAggFiscalMAIN.py
which writes ``DiscFacEstim_..._edType{N}[suffix].txt``. Here that write is
redirected to a per-machine scratch dir via ``HAFISCAL_RESULTS_OUT_DIR`` so the
git-tracked ``Results/`` warm-start files are NEVER clobbered (warm-start READS
still come from ``Results/``; only the OUTPUT is redirected). The orchestrator
gathers the per-group files from each machine's scratch dir.

DURABLE LAUNCH (item a): each group is launched **detached** via
``nohup ... </dev/null >log 2>&1 &`` (portable across Linux + macOS — ``setsid``
is Linux-only) and writes an atomic ``done`` marker (``echo $? > done.tmp; mv``)
on exit. The orchestrator POLLS the markers instead of holding the ssh
connection, so a dropped ssh / a restarted orchestrator can NOT kill a
multi-hour group. Liveness (pgrep) + a max-wait timeout guard against a job that
dies without writing a marker.

PRE-TEST / "Reduced_Run":  --nm-cap N  caps Nelder-Mead to N function calls so
each group finishes in minutes — enough to validate the cross-machine mechanics
(sync, dispatch, durable wait, gather, timing) without the real ~7 h. Use
--nm-cap 0 for a real full run, and --finalize to merge the gathered per-group
files into a candidate-routed canonical + run the calcAllResults pass.

Assignment (edType -> host), by the lightest->weakest-box heuristic:
    0 Dropout    -> ccarroll      (M4 Max, 64 GiB)
    1 Highschool -> ccarroll-m5   (M5 Max, 128 GiB)
    2 College    -> dell (local)  (i9-13900K)
The per-(group, machine) wall times printed at the end are the data to re-balance
the real run.
"""
import argparse
import glob
import os
import subprocess
import time

BRANCH = "0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC"
DELL_REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
MAC_REPO = "/Volumes/Sync/GitHub/llorracc/HAFiscal-Latest"
# ABSOLUTE venv paths — the child cd's into FromPandemicCode (deep in the repo),
# so a relative "./.venv-..." would resolve there and not exist (rc=127). The
# venv lives at the repo root.
MAC_PY = MAC_REPO + "/.venv-darwin-arm64/bin/python"
DELL_PY = DELL_REPO + "/.venv-linux-x86_64/bin/python"

# (label, host|None=local, edType, repo_root, python)
MACHINES = [
    ("ccarroll_M4Max_edType0_Dropout", "ccarroll", 0, MAC_REPO, MAC_PY),
    ("ccarroll-m5_M5Max_edType1_HS", "ccarroll-m5", 1, MAC_REPO, MAC_PY),
    ("dell_i9_edType2_College", None, 2, DELL_REPO, DELL_PY),
]
SSH = ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes"]

# Step-2 engine → (estimator script, HAFISCAL_STEP2_SIM_ENGINE value). 'mc' is the
# MC-panel-moment estimator; 'tm' the TM-ergodic-moment estimator (~10-21× faster
# sim, deterministic). Mirrors run_phase2_parallel.py's dispatch.
_ENGINE = {
    "mc": ("EstimAggFiscalMAIN.py", "mc"),
    "tm": ("estim_phase2_tm_a.py", "tm_ergodic"),
}


def _run(host, inner, timeout=30):
    """Run ``inner`` on ``host`` (or locally if host is None). Never raises:
    on ssh timeout / network blip returns a failed CompletedProcess so the poll
    loop degrades to 'not done yet' and retries next tick."""
    cmd = (SSH + [host, inner]) if host else ["bash", "-lc", inner]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:  # TimeoutExpired, ssh failure, etc.
        return subprocess.CompletedProcess(cmd, 255, "", str(e))


def _short_head(host, repo):
    inner = f"git -C {repo} rev-parse --short HEAD"
    r = _run(host, inner, timeout=30)
    out = (r.stdout or "").strip().splitlines()
    return out[-1] if out else f"?(rc={r.returncode})"


def _launch(host, fpc, scratch, et, envs, py, engine):
    """Detached launch: a nohup'd job writes its rc to an atomic done-marker;
    the launching ssh returns immediately. Returns (ok, log_path)."""
    log = f"{scratch}/run.log"
    script, sim_engine = _ENGINE[engine]
    # The job must DETACH so (1) the launching ssh returns immediately instead of
    # holding the connection for the whole multi-hour run, and (2) a dropped ssh /
    # restarted orchestrator can't kill it. The portable detach (Linux + macOS —
    # macOS has no `setsid`) is a SUBSHELL `( nohup ... & )`: it reparents the job
    # to init/launchd and releases the ssh channel (and the local subprocess pipe)
    # at once. A bare `nohup ... &` does NOT — it leaves the bg job holding the
    # channel so ssh / subprocess.run blocks until the job EXITS (verified on
    # ccarroll-m5: a 20 s job held the launch for 20 s; locally it tripped the
    # 30 s _run timeout → false 'launch failed'). The job's real output goes to
    # {log}; its python exit code to an atomically-written done-marker.
    job = (f"env {envs} HAFISCAL_EDTYPES={et} HAFISCAL_STEP2_SIM_ENGINE={sim_engine} "
           f"HAFISCAL_RESULTS_OUT_DIR={scratch} "
           f"{py} -u {script} > {log} 2>&1; "
           f"echo $? > {scratch}/done.tmp && mv {scratch}/done.tmp {scratch}/done")
    inner = (f"mkdir -p {scratch} && cd {fpc} && "
             f"( nohup bash -c '{job}' </dev/null >/dev/null 2>&1 & ) && echo LAUNCHED")
    r = _run(host, inner, timeout=30)
    return ("LAUNCHED" in (r.stdout or "")), log


def _marker(host, scratch):
    """Return the rc int if the done-marker exists and is a valid int, else None."""
    r = _run(host, f"cat {scratch}/done 2>/dev/null", timeout=20)
    s = (r.stdout or "").strip()
    return int(s) if s and s.lstrip("-").isdigit() else None


def _alive(host, engine):
    """Best-effort: True if the engine's estimator process is running on host.
    (1 group/machine, so this can't be confused with another group's process.)

    The `[E]stim...` bracket trick is load-bearing: a plain `pgrep -f <script>`
    runs inside a shell whose OWN command line contains that literal string, so
    pgrep matches the wrapping shell and ALWAYS reports a (phantom) live process —
    making the vanished-job check useless. The bracketed regex matches the real
    `python … <script>` process but NOT the literal `[…]` in pgrep's own argv."""
    script = _ENGINE[engine][0]
    patt = "[" + script[0] + "]" + script[1:]
    r = _run(host, f"pgrep -f '{patt}' >/dev/null 2>&1 && echo YES || echo NO",
             timeout=20)
    return "YES" in (r.stdout or "")


def _gather_one(host, scratch, et, staging, gather, label):
    """scp the per-edType output file(s) + run.log from a machine's scratch dir."""
    files = []
    pat = f"{scratch}/DiscFacEstim_*_edType{et}*.txt"
    if host:
        ls = _run(host, f"ls -1 {pat} 2>/dev/null", timeout=30)
        for f in (ls.stdout or "").splitlines():
            f = f.strip()
            if f.endswith(".txt"):
                dest = os.path.join(staging, os.path.basename(f))
                subprocess.run(["scp", "-q", f"{host}:{f}", dest], timeout=60)
                files.append(dest)
        subprocess.run(["scp", "-q", f"{host}:{scratch}/run.log",
                        os.path.join(gather, f"{label}.log")], timeout=60)
    else:
        for f in glob.glob(pat):
            dest = os.path.join(staging, os.path.basename(f))
            subprocess.run(["cp", f, dest])
            files.append(dest)
        if os.path.exists(f"{scratch}/run.log"):
            subprocess.run(["cp", f"{scratch}/run.log",
                            os.path.join(gather, f"{label}.log")])
    return files


def _finalize(staging, py, engine):
    """Merge the gathered per-edType files into a candidate-routed canonical +
    run the calcAllResults pass, by invoking run_phase2_parallel.py's
    finalize-only mode (single source of truth for the merge logic)."""
    fpc = f"{DELL_REPO}/Code/HA-Models/FromPandemicCode"
    env = os.environ.copy()
    env["HAFISCAL_PHASE2_FINALIZE_ONLY"] = "1"
    env["HAFISCAL_PHASE2_PER_EDTYPE_DIR"] = staging
    env["HAFISCAL_STEP2_SIM_ENGINE"] = _ENGINE[engine][1]  # merge to the right canonical (_TM_a for tm)
    print(f"[xm] FINALIZE: merging {staging} via run_phase2_parallel.py (candidate-routed)…")
    rc = subprocess.run([py, "-u", "run_phase2_parallel.py"], cwd=fpc, env=env).returncode
    print(f"[xm] FINALIZE rc={rc}")
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nm-cap", type=int, default=3,
                    help="HAFISCAL_NM_VALIDATE_N_ITERS (0 = full real run)")
    ap.add_argument("--engine", choices=["mc", "tm"], default="tm",
                    help="Step-2 sim engine. DEFAULT tm=estim_phase2_tm_a.py (TM-ergodic "
                         "moments, ~10-21× faster; flipped from mc 2026-06-23 — TM≡MC β "
                         "≤0.06%, see conclusions_private/2026-06-23_step2-default-flip-to-"
                         "tm-ergodic.md). mc=EstimAggFiscalMAIN.py (MC-panel) is opt-in")
    ap.add_argument("--gather-dir", default=None)
    ap.add_argument("--poll-secs", type=int, default=15)
    ap.add_argument("--max-hours", type=float, default=None,
                    help="safety timeout (default 0.5 h pre-test / 24 h real run)")
    ap.add_argument("--finalize", action="store_true",
                    help="after gather, merge per-edType files + calcAllResults "
                         "(REAL run only; owner-gated — re-estimation is opt-in)")
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d-%H%M%S")
    gather = args.gather_dir or f"/tmp/xmstep2_{ts}"
    staging = os.path.join(gather, "staging")
    os.makedirs(staging, exist_ok=True)

    env_parts = ["HAFISCAL_SERIAL=1", "HAFISCAL_NUM_STARTS=1"]
    if args.nm_cap > 0:
        env_parts.append(f"HAFISCAL_NM_VALIDATE_N_ITERS={args.nm_cap}")
    envs = " ".join(env_parts)
    max_secs = (args.max_hours if args.max_hours is not None
                else (0.5 if args.nm_cap > 0 else 24.0)) * 3600

    print(f"[xm] gather dir: {gather}")
    print(f"[xm] engine: {args.engine} ({_ENGINE[args.engine][0]})")
    print(f"[xm] mode: {'PRE-TEST nm_cap=%d' % args.nm_cap if args.nm_cap else 'FULL RUN'}"
          f"  finalize={args.finalize}  max_wait={max_secs/3600:.1f}h")
    print("[xm] preflight commits:")
    for label, host, et, repo, py in MACHINES:
        print(f"     {label:34s} {host or 'local':12s} {_short_head(host, repo)}")

    # ---- detached launch of all groups ----
    jobs = []
    for label, host, et, repo, py in MACHINES:
        fpc = f"{repo}/Code/HA-Models/FromPandemicCode"
        scratch = f"/tmp/xmstep2_out_{ts}_edType{et}"
        ok, log = _launch(host, fpc, scratch, et, envs, py, args.engine)
        jobs.append(dict(label=label, host=host, et=et, scratch=scratch,
                         t0=time.time(), launched=ok, rc=None, dur=0.0, strikes=0))
        print(f"[xm] launched {label} (edType={et}) on {host or 'dell(local)'}: "
              f"{'OK (detached)' if ok else 'LAUNCH FAILED'}")

    # ---- durable wait: poll markers; survive dropped ssh ----
    remaining = [j for j in jobs if j["launched"]]
    for j in jobs:
        if not j["launched"]:
            j["rc"] = -3  # never launched
    while remaining:
        time.sleep(args.poll_secs)
        for j in list(remaining):
            rc = _marker(j["host"], j["scratch"])
            if rc is not None:
                j["rc"], j["dur"] = rc, time.time() - j["t0"]
                print(f"[xm] DONE {j['label']}: rc={rc} after {j['dur']/60:.1f} min")
                remaining.remove(j); continue
            if time.time() - j["t0"] > max_secs:
                j["rc"], j["dur"] = -2, time.time() - j["t0"]
                print(f"[xm] TIMEOUT {j['label']} after {j['dur']/60:.1f} min (no marker)")
                remaining.remove(j); continue
            # liveness: a job dead WITHOUT a marker for 2 consecutive polls is
            # 'vanished' (OOM/kill). 2 polls absorbs the exit→marker-write race.
            if _alive(j["host"], args.engine):
                j["strikes"] = 0
            else:
                j["strikes"] += 1
                if j["strikes"] >= 2:
                    j["rc"], j["dur"] = -1, time.time() - j["t0"]
                    print(f"[xm] VANISHED {j['label']} (no process, no marker) "
                          f"after {j['dur']/60:.1f} min")
                    remaining.remove(j)

    # ---- gather per-group output files + logs from each scratch dir ----
    print("\n[xm] gathering per-group DiscFacEstim_..._edType{N} files from scratch:")
    gathered = []
    for label, host, et, repo, py in MACHINES:
        scratch = next(j["scratch"] for j in jobs if j["label"] == label)
        files = _gather_one(host, scratch, et, staging, gather, label)
        for f in files:
            gathered.append((et, host or "local", f))
    for et, where, f in gathered:
        print(f"     edType={et} [{where}] {os.path.basename(f)}")

    # ---- optional finalize (real run) ----
    finalize_rc = None
    if args.finalize:
        if args.nm_cap > 0:
            print("\n[xm] WARNING: --finalize with --nm-cap>0 would merge CAPPED "
                  "(garbage) estimates. Skipping finalize. Use --nm-cap 0 for a real run.")
        elif len(gathered) < 3:
            print(f"\n[xm] WARNING: only {len(gathered)} per-group files gathered; "
                  "skipping finalize (need all 3).")
        else:
            finalize_rc = _finalize(staging, DELL_PY, args.engine)

    # ---- report ----
    print("\n========== CROSS-MACHINE STEP-2 REPORT ==========")
    print(f"{'group/machine':36s} {'rc':>3s} {'wall(min)':>9s}   (rc: 0 ok, -1 vanished, -2 timeout, -3 launch-fail)")
    ok = True
    for label, host, et, repo, py in MACHINES:
        j = next(jj for jj in jobs if jj["label"] == label)
        ok = ok and (j["rc"] == 0)
        print(f"{label:36s} {str(j['rc']):>3s} {j['dur']/60:>9.1f}")
    print(f"\nper-group result files gathered: {len(gathered)} (>=3 expected)")
    if args.finalize and finalize_rc is not None:
        print(f"finalize (merge + calcAllResults): rc={finalize_rc}")
    passed = ok and len(gathered) >= 3 and (finalize_rc in (None, 0))
    print("RESULT:", "PASS" if passed else f"FAIL (see logs in {gather})")
    if not args.finalize:
        print("\nNOTE: merge into the canonical DiscFacEstim is SKIPPED (no --finalize)."
              " Scratch output means NO git-tracked Results file was touched on any"
              " machine. For a real run: --nm-cap 0 --finalize (owner-gated).")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
