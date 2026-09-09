#!/usr/bin/env python3
"""runq — a per-machine resource queue for HAFiscal compute (infrastructure plan B4, 2026-08-28).

Why. On 2026-08-27/28 three Step-5a multiplier programs shared dell and each ran ~3x slower (Rfree_1005 252 min, Rfree_1015
> 4 h, vs 65-80 min alone): the 5a forks 4 shock workers with their own solver pools, so two programs oversubscribe the box
and parallel streams finish LATER than sequential ones. The remedy was a manual SIGSTOP. runq makes launchers queue instead
of contend: a job takes a slot of its resource class (a lock file per slot), waits with a stamp while the class is full,
runs, releases.

Usage
    runq --class 5a|battery|step2|any [--host HOST] -- CMD ARGS...     run CMD holding one slot of the class
    runq status [--host HOST]                                          list slots, holders, waiters
    HAFISCAL_RUNQ=0 runq ...                                           bypass (run immediately; for tests / emergencies)
    HAFISCAL_RUNQ_SLOTS_5A=2                                           override a class's slot count on this host
    runq headroom [--hosts ccarroll,ccarroll-m5]                        load / memory headroom, local or over ssh
    HAFISCAL_RUNQ_HEADROOM=0                                           skip the interactive-host headroom wait
    HAFISCAL_RUNQ_DIR=/path                                            lock directory (default $XDG_RUNTIME_DIR/hafiscal-runq,
                                                                       else ~/.cache/hafiscal/runq -- macOS has no XDG dir)

Classes: `5a` = the TM multiplier program (AggFiscalMAIN_reduced.py); `battery` = a welfare battery (run_welfare6_parallel.py);
`step2` = a Step-2 estimation (its three education groups launched together count as ONE job); `any` = anything else
(takes one slot of the `any` class). Capacity per host (owner-confirmed defaults 2026-08-28): dell 5a x1, battery x2, step2 x1;
ccarroll-m5 x1 each; ccarroll / xubuntark: one job of any class (every class maps to the single `any` slot).
Locks are per user (all our runs are one user per machine). FIFO is by polling order (15 s); there is no preemption --
pause a job by hand with `systemctl --user kill --signal=SIGSTOP <unit>` if you must.
"""
import argparse, fcntl, json, os, socket, subprocess, sys, time

CAPACITY = {
    "jhu-dell":    {"5a": 1, "battery": 2, "step2": 1, "any": 1},   # 2 again since the owner raised the session oomd limit to 80 % (2026-08-28 12:20); 5a's keep HAFISCAL_PARALLEL_SOLVE=10
    "ccarroll-m5": {"5a": 1, "battery": 1, "step2": 1, "any": 1},
    "ccarroll":    {"any": 1},     # a laptop: one job at a time, whatever the class
    "xubuntark":   {"any": 1},
}
# Hosts with INTERACTIVE use (owner 2026-08-28: "there is interactive work on both the macs, so you should assess how much
# headroom there is before deciding what to put where"): before taking a slot, runq waits until the box has headroom --
# 1-min load below HEADROOM_LOAD_FRAC x ncpu and at least HEADROOM_MEM_GB available -- and re-checks every POLL_S.
# `runq headroom [--hosts a,b]` reports the same numbers so the launcher can decide placement. HAFISCAL_RUNQ_HEADROOM=0 bypasses.
INTERACTIVE = {"ccarroll", "ccarroll-m5"}
HEADROOM_LOAD_FRAC = 0.35
HEADROOM_MEM_GB = 8.0
DEFAULT = {"5a": 1, "battery": 1, "step2": 1, "any": 1}
# The per-class slot overrides, spelled out so the env-flag registry guard can see them (they are
# read as HAFISCAL_RUNQ_SLOTS_<CLASS> in resolve()).
SLOT_FLAGS = ("HAFISCAL_RUNQ_SLOTS_5A", "HAFISCAL_RUNQ_SLOTS_BATTERY", "HAFISCAL_RUNQ_SLOTS_STEP2", "HAFISCAL_RUNQ_SLOTS_ANY")
POLL_S = 15
STAMP_EVERY_S = 600


def host_name(override=None):
    h = override or socket.gethostname()
    return h.split(".")[0]


def lock_dir():
    d = os.environ.get("HAFISCAL_RUNQ_DIR") or (os.path.join(os.environ["XDG_RUNTIME_DIR"], "hafiscal-runq")
                                                if os.environ.get("XDG_RUNTIME_DIR") else os.path.expanduser("~/.cache/hafiscal/runq"))
    os.makedirs(d, exist_ok=True)
    return d


def resolve(host, cls):
    """(effective class, slot count) on this host: hosts with only an `any` slot map every class to it."""
    table = CAPACITY.get(host, DEFAULT)
    if cls not in table and "any" in table and len(table) == 1:
        cls = "any"
    n = table.get(cls, DEFAULT.get(cls, 1))
    env = os.environ.get(f"HAFISCAL_RUNQ_SLOTS_{cls.upper()}")
    if env:
        n = int(env)
    return cls, n


def _ncpu():
    return os.cpu_count() or 1


def _avail_gb():
    """MemAvailable (Linux) or free+inactive+speculative pages (macOS), in GiB."""
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1048576.0
    except OSError:
        pass
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        import re as _re
        m = _re.search(r"page size of (\d+) bytes", out); page = int(m.group(1)) if m else 4096
        pages = 0
        for key in ("Pages free", "Pages inactive", "Pages speculative"):
            m = _re.search(key + r":\s+(\d+)", out)
            if m:
                pages += int(m.group(1))
        return pages * page / 1073741824.0
    except Exception:
        return float("nan")


def headroom(host):
    """(ok, load1, avail_gb, ncpu): ok = the box can take a job without crowding interactive use."""
    load1 = os.getloadavg()[0]; n = _ncpu(); avail = _avail_gb()
    ok = load1 <= HEADROOM_LOAD_FRAC * n and (avail != avail or avail >= HEADROOM_MEM_GB)   # nan avail -> do not block
    return ok, load1, avail, n


def headroom_report(host, hosts=None):
    if hosts:
        for h in hosts.split(","):
            cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", h,
                   "python3 -c 'import os; print(os.getloadavg()[0], os.cpu_count())'; (grep MemAvailable /proc/meminfo 2>/dev/null || vm_stat 2>/dev/null | head -n 5)"]
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=25).stdout.strip().splitlines()
                load, n = out[0].split()[:2]; print(f"{h:12s} load1={float(load):5.1f} ncpu={n:>3s} headroom_load_cap={HEADROOM_LOAD_FRAC*int(n):4.1f}  mem: {' '.join(out[1:3])[:70]}")
            except Exception as e:
                print(f"{h:12s} unreachable ({e})")
        return 0
    ok, load1, avail, n = headroom(host)
    print(f"{host}: load1={load1:.2f} ncpu={n} cap={HEADROOM_LOAD_FRAC*n:.1f} avail={avail:.1f} GiB (min {HEADROOM_MEM_GB}) -> {'OK' if ok else 'BUSY'}"
          + ("" if host in INTERACTIVE else "  [not an interactive host: headroom is advisory]"))
    return 0


def slot_paths(d, cls, n):
    return [os.path.join(d, f"{cls}.{k}.lock") for k in range(n)]


def try_acquire(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except OSError:
        os.close(fd)
        return None


def holder_info(path):
    try:
        return json.load(open(path + ".json"))
    except Exception:
        return None


def status(host):
    d = lock_dir()
    table = CAPACITY.get(host, DEFAULT)
    print(f"runq status on {host} (locks in {d})")
    for cls, n in table.items():
        for p in slot_paths(d, cls, n):
            fd = try_acquire(p)
            if fd is not None:
                fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)
                print(f"  {os.path.basename(p):18s} free")
            else:
                info = holder_info(p) or {}
                print(f"  {os.path.basename(p):18s} HELD  pid={info.get('pid')} since={info.get('start')} cmd={' '.join(info.get('cmd', []))[:90]}")
    waiters = [f for f in os.listdir(d) if f.endswith(".waiting")]
    for w in sorted(waiters):
        try:
            info = json.load(open(os.path.join(d, w)))
            print(f"  waiting: pid={info.get('pid')} class={info.get('class')} since={info.get('start')} cmd={' '.join(info.get('cmd', []))[:80]}")
        except Exception:
            pass
    return 0


def run(cls, cmd, host):
    if os.environ.get("HAFISCAL_RUNQ", "1").strip().lower() in ("0", "off", "false", "no"):
        return subprocess.call(cmd)
    d = lock_dir()
    cls, n = resolve(host, cls)
    paths = slot_paths(d, cls, n)
    t0 = time.time(); last_stamp = 0.0; fd = None; held = None
    waiting = os.path.join(d, f"wait.{os.getpid()}.waiting")
    while fd is None:
        for p in paths:
            fd = try_acquire(p)
            if fd is not None:
                held = p; break
        if fd is None:
            if time.time() - last_stamp >= STAMP_EVERY_S:
                holders = [(holder_info(p) or {}).get("cmd", ["?"])[:1] for p in paths]
                print(f"[runq] {host}: class {cls} full ({n} slot{'s' if n != 1 else ''}); queued {int((time.time()-t0)/60)} min behind {holders}", flush=True)
                json.dump({"pid": os.getpid(), "class": cls, "start": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)), "cmd": cmd}, open(waiting, "w"))
                last_stamp = time.time()
            time.sleep(POLL_S)
    if host in INTERACTIVE and os.environ.get("HAFISCAL_RUNQ_HEADROOM", "1").strip().lower() not in ("0", "off", "false", "no"):
        last = 0.0
        while True:
            ok, load1, avail, n = headroom(host)
            if ok:
                break
            if time.time() - last >= STAMP_EVERY_S:
                print(f"[runq] {host}: waiting for headroom (load1 {load1:.1f} > {HEADROOM_LOAD_FRAC*n:.1f} or avail {avail:.1f} GiB < {HEADROOM_MEM_GB}); interactive use has priority", flush=True)
                last = time.time()
            time.sleep(POLL_S)
    try:
        os.remove(waiting)
    except OSError:
        pass
    json.dump({"pid": os.getpid(), "start": time.strftime("%Y-%m-%d %H:%M:%S"), "cmd": cmd, "queued_min": round((time.time()-t0)/60, 1)}, open(held + ".json", "w"))
    print(f"[runq] {host}: took {os.path.basename(held)} after {int((time.time()-t0)/60)} min queued; running: {' '.join(cmd)[:120]}", flush=True)
    try:
        proc = subprocess.Popen(cmd)
        try:
            rc = proc.wait()
        except KeyboardInterrupt:
            proc.terminate(); rc = proc.wait()
    finally:
        try:
            os.remove(held + ".json")
        except OSError:
            pass
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)
    print(f"[runq] {host}: released {os.path.basename(held)} rc={rc} wall={int((time.time()-t0)/60)} min", flush=True)
    return rc


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "headroom":
        ap = argparse.ArgumentParser(); ap.add_argument("headroom"); ap.add_argument("--host", default=None); ap.add_argument("--hosts", default=None)
        a = ap.parse_args(argv); return headroom_report(host_name(a.host), a.hosts)
    if argv and argv[0] == "status":
        ap = argparse.ArgumentParser(); ap.add_argument("status"); ap.add_argument("--host", default=None)
        a = ap.parse_args(argv); return status(host_name(a.host))
    if "--" not in argv:
        print(__doc__); return 2
    k = argv.index("--"); opts, cmd = argv[:k], argv[k + 1:]
    ap = argparse.ArgumentParser(); ap.add_argument("--class", dest="cls", required=True, choices=("5a", "battery", "step2", "any"))
    ap.add_argument("--host", default=None); a = ap.parse_args(opts)
    if not cmd:
        print("runq: no command after --"); return 2
    return run(a.cls, cmd, host_name(a.host))


if __name__ == "__main__":
    sys.exit(main())
