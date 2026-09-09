"""Supervised worker pools: a killed child FAILS the map, never hangs it.

Infrastructure item A6 (plans/20260828-1130h_infrastructure-lessons-implementation_plan.md;
memory feedback_no_corunning_5a_on_dell / feedback_compute_in_own_systemd_unit).

THE DEFECT. ``multiprocessing.Pool`` has no notion of a worker dying. When the cgroup
OOM-killer (the systemd unit's ``MemoryMax``) SIGKILLs a pool child mid-task, that task's
result never arrives, the pool's worker-handler thread quietly forks a replacement, and
the parent blocks in ``pool.map()`` for ever: on 2026-08-28 two appendix multiplier
programs sat 7 h and 4 h with the parent in ``do_wait``, the surviving workers in
``futex_do_wait`` (the killed child had been holding the task pipe's reader lock) and the
pool idle on the pipe. Detecting the death from outside is easy (poll the workers'
``exitcode``); cleaning up is not: ``Pool.terminate()`` -- what ``with pool:`` runs on the
way out -- re-acquires that same reader lock and hangs too (CPython gh-66591, open since
2014; measured here 2026-08-28: the ``terminate()`` thread was still blocked 5 s after
every worker had been SIGKILLed).

THE PRIMITIVE. ``concurrent.futures.ProcessPoolExecutor`` is the stdlib's fail-fast pool:
its manager thread waits on the worker SENTINELS as well as on the result pipe, so any
worker exit while work is pending marks the executor broken, fails every pending future
with ``BrokenProcessPool``, SIGTERMs the survivors and shuts down without touching the
dirty lock (measured 2026-08-28, fork context: ``BrokenProcessPool`` 1.0 s after the
kill, shutdown 0.00 s, clean interpreter exit -- for a busy victim and for idle ones).
It also fails instead of hanging when a RESULT cannot be unpickled in the parent (the
2026-08-24 hark_fti class of deadlock). This module wraps it so that every site gets the
same behaviour and the same failure report: the site's name, the dead worker's pid and
exit signal, the peak RSS of the largest reaped child (``getrusage``), and the kernel's
OOM line for that pid when ``journalctl -k`` has one.

RESULT EQUIVALENCE. ``supervised_map(func, items, ...)`` returns exactly what
``pool.map(func, items)`` returned: ``[func(x) for x in items]``, one call per item in a
worker process, results in input order. Under ``start_method='fork'`` the workers are
forked at the first submit, i.e. inside the call, so module globals set before it are
inherited exactly as they were with ``Pool(...)`` created at the same point. Only the
chunking differs (one task per item versus ``Pool.map``'s ``len/(4*workers)`` chunks),
and which worker computes which item is not part of any result.
``supervised_map_unordered`` is the ``list(pool.imap_unordered(func, items, chunksize=1))``
equivalent for a persistent executor (completion order, as before).

NOT COVERED. A worker that is alive but stuck (a fork-inherited lock, say) is not a death;
nothing here times out a running task.
"""
from __future__ import annotations

import multiprocessing as mp
import resource
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_EXCEPTION, ProcessPoolExecutor, as_completed, wait
from concurrent.futures.process import BrokenProcessPool

__all__ = [
    "PoolWorkerDied",
    "supervised_map",
    "supervised_map_unordered",
    "persistent_executor",
    "executor_unusable",
    "shutdown_executor",
]

# Bound on the post-failure shutdown. Measured 0.00 s; the bound is the promise that a
# second defect in the cleanup can never turn a loud failure back into a silent hang.
_CLEANUP_TIMEOUT_S = 30.0
# How far back to look for the kernel's OOM line about a dead worker.
_JOURNAL_WINDOW = "-30min"


class PoolWorkerDied(RuntimeError):
    """A supervised pool lost a worker process while work was pending.

    ``site``: the caller's name as passed to the helper.
    ``dead_pids``: workers whose exit was not the cleanup's own SIGTERM (the victims).
    ``exit_codes``: pid -> exit code for every worker of the pool at failure time
    (negative = killed by that signal; None = still not reaped at the bound).
    """

    def __init__(self, message, *, site, dead_pids, exit_codes):
        super().__init__(message)
        self.site = site
        self.dead_pids = list(dead_pids)
        self.exit_codes = dict(exit_codes)


def supervised_map(func, items, *, n_workers, site, start_method="fork"):
    """``pool.map(func, items)`` on a fresh pool of ``n_workers`` that fails fast.

    Creates the executor, forks/spawns the workers at the first submit (so ``fork``
    inherits the caller's module globals as ``Pool`` did), returns ``[func(x) for x in
    items]`` in input order, and shuts the pool down before returning. A worker death
    raises :class:`PoolWorkerDied` (cause: the executor's ``BrokenProcessPool``) within
    seconds; a worker-side exception propagates as ``pool.map`` propagated it, with the
    other workers terminated as ``with pool:`` terminated them.
    """
    items = list(items)
    if int(n_workers) < 1:
        raise ValueError(f"{site}: n_workers must be >= 1, got {n_workers!r}")
    executor = ProcessPoolExecutor(max_workers=int(n_workers),
                                   mp_context=mp.get_context(start_method))
    return _run(executor, func, items, site=site, ordered=True, own=True)


def persistent_executor(n_workers, *, start_method="spawn"):
    """A long-lived executor for callers that reuse warm workers across calls
    (``welfare6_scenario``'s solve pool). Use with :func:`supervised_map_unordered`;
    retire it with :func:`shutdown_executor`; test :func:`executor_unusable` before
    reusing one that may have failed."""
    if int(n_workers) < 1:
        raise ValueError(f"persistent_executor: n_workers must be >= 1, got {n_workers!r}")
    return ProcessPoolExecutor(max_workers=int(n_workers),
                               mp_context=mp.get_context(start_method))


def supervised_map_unordered(executor, func, items, *, site):
    """``list(pool.imap_unordered(func, items, chunksize=1))`` on a persistent executor:
    results in completion order. A worker death raises :class:`PoolWorkerDied`; the
    executor is then unusable (see :func:`executor_unusable`)."""
    return _run(executor, func, list(items), site=site, ordered=False, own=False)


def executor_unusable(executor):
    """True once an executor is broken or shut down -- a fresh one is needed."""
    return bool(getattr(executor, "_broken", False)
                or getattr(executor, "_shutdown_thread", False))


def shutdown_executor(executor, *, timeout=_CLEANUP_TIMEOUT_S):
    """The ``Pool.terminate(); Pool.join()`` equivalent: cancel pending work, SIGTERM
    live workers, join within ``timeout`` (SIGKILL stragglers). Never raises."""
    try:
        _terminate(executor, _workers(executor), timeout=timeout)
    except Exception:
        pass


# ----------------------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------------------

def _run(executor, func, items, *, site, ordered, own):
    procs = {}
    try:
        futures = [executor.submit(func, item) for item in items]
        procs = _workers(executor)
        if ordered:
            # Fail as early as Pool.map did: the first exception ends the wait, and
            # its future is raised before any still-running one is waited for.
            wait(futures, return_when=FIRST_EXCEPTION)
            failed = next((f for f in futures
                           if f.done() and not f.cancelled() and f.exception() is not None),
                          None)
            if failed is not None:
                failed.result()
            results = [f.result() for f in futures]
        else:
            results = [f.result() for f in as_completed(futures)]
    except BrokenProcessPool as exc:
        exit_codes = _terminate(executor, procs or _workers(executor))
        raise _worker_died(site, exit_codes, exc, n_items=len(items)) from exc
    except BaseException:
        # A worker-side exception, or the caller interrupted: bring the pool down the
        # way ``with pool:`` did on an exception (terminate, do not wait for the rest).
        _terminate(executor, procs or _workers(executor))
        raise
    if own:
        executor.shutdown(wait=True)
    return results


def _workers(executor):
    # The executor keeps its workers in the private ``_processes`` dict (pid -> Process;
    # stable across CPython 3.8-3.13). Used only for the failure REPORT and the bounded
    # cleanup -- the failure DETECTION is the executor's own.
    return dict(getattr(executor, "_processes", None) or {})


def _terminate(executor, procs, timeout=_CLEANUP_TIMEOUT_S):
    """Bring an executor down with a bound: cancel, SIGTERM, join, SIGKILL stragglers.
    Returns pid -> exit code."""
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    for p in procs.values():
        if p.exitcode is None:
            try:
                p.terminate()
            except Exception:
                pass
    joiner = threading.Thread(target=executor.shutdown, kwargs={"wait": True},
                              daemon=True, name="pool-supervision-shutdown")
    joiner.start()
    joiner.join(timeout)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and any(p.exitcode is None for p in procs.values()):
        time.sleep(0.02)
    for p in procs.values():
        if p.exitcode is None:
            try:
                p.kill()
            except Exception:
                pass
    return {pid: p.exitcode for pid, p in procs.items()}


def _worker_died(site, exit_codes, exc, *, n_items):
    cleanup_sig = -int(signal.SIGTERM)
    dead = [pid for pid, code in exit_codes.items()
            if code is not None and code != cleanup_sig]
    others = [pid for pid in exit_codes if pid not in dead]
    lines = [f"[pool-supervision] {site}: a worker process died while {n_items} tasks "
             f"were in flight; failing instead of hanging (multiprocessing.Pool would "
             f"have waited for ever)."]
    if dead:
        lines.append("  dead worker(s): " + "; ".join(
            f"pid {pid} {_explain_code(exit_codes[pid])}" for pid in dead))
    else:
        lines.append("  no worker shows an exit other than the cleanup's SIGTERM; the "
                     "executor reported: " + _cause_text(exc))
    if others:
        lines.append(f"  the other {len(others)} worker(s) were terminated by the cleanup "
                     f"(SIGTERM): pids {', '.join(str(pid) for pid in others)}")
    lines.append("  " + _memory_line())
    oom = _kernel_oom_lines(dead)
    if oom:
        lines.append("  kernel log (journalctl -k): " + " | ".join(oom))
    else:
        lines.append(f"  kernel log: no OOM line naming these pids in journalctl -k "
                     f"(window {_JOURNAL_WINDOW}, or the journal is unavailable here)")
    lines.append("  A SIGKILL with no other explanation is the cgroup OOM-killer (the "
                 "systemd unit's MemoryMax): re-run with fewer workers or more memory.")
    return PoolWorkerDied("\n".join(lines), site=site, dead_pids=dead,
                          exit_codes=exit_codes)


def _explain_code(code):
    if code is None:
        return "not reaped within the cleanup bound"
    if code < 0:
        try:
            name = signal.Signals(-code).name
        except ValueError:
            name = "?"
        return f"killed by signal {-code} ({name})"
    if code == 0:
        return "exited with status 0 mid-task (os._exit / sys.exit inside the worker)"
    return f"exited with status {code}"


def _cause_text(exc):
    cause = getattr(exc, "__cause__", None)
    text = str(cause).strip() if cause is not None else str(exc).strip()
    return text[-600:] if len(text) > 600 else text


def _memory_line():
    try:
        child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        me = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return "peak RSS: unavailable"
    # ru_maxrss is KiB on Linux and bytes on macOS.
    to_gib = 1.0 / 1024 ** 3 if sys.platform == "darwin" else 1.0 / 1024 ** 2
    return (f"peak RSS (getrusage ru_maxrss): largest reaped child {child * to_gib:.2f} GiB, "
            f"this process {me * to_gib:.2f} GiB")


def _kernel_oom_lines(pids, *, since=_JOURNAL_WINDOW, timeout=5.0):
    """Best-effort: the kernel's OOM lines naming these pids ('Killed process <pid> (...)'
    / 'pid=<pid>,'), from ``journalctl -k``. Empty when there are none or the journal
    cannot be read; never raises, bounded by ``timeout``."""
    if not pids:
        return []
    try:
        proc = subprocess.run(
            ["journalctl", "-k", "--since", since, "--no-pager", "-o", "cat"],
            capture_output=True, text=True, timeout=timeout)
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    needles = [f"process {pid} " for pid in pids] + [f"pid={pid}," for pid in pids]
    hits = [ln.strip() for ln in proc.stdout.splitlines()
            if any(n in ln for n in needles)]
    return hits[-3:]
