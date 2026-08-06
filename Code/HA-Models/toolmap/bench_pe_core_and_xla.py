"""Does CPython+small-numpy work (HARK's make_history shape) run slower
(a) on an E-core than a P-core, and (b) in a process that has already run XLA?

Written for plans/20260730-0900h_hark-vs-jax-duration-residual_diagnosis_plan.md
(section 3), to test the two runtime-interference hypothesis families cheaply
before spending Baseline-scale hours on them.

Workload proxy: HARK's duration loop is act_T=400 periods x 21 agent types x ~10
numpy ops on 10k-element arrays (80 KB, L2-resident) -- i.e.
interpreter-dispatch-bound, with a searchsorted+lerp cFunc evaluation at its core,
NOT big-array bandwidth work.  That is the regime where P-core vs E-core IPC
differs most, and it is NOT the regime the earlier n=50..100k microbenchmark tested.

    python bench_pe_core_and_xla.py plain    # baseline only
    python bench_pe_core_and_xla.py xla      # baseline, then again after an XLA burn
    taskset -c 2  python bench_pe_core_and_xla.py plain   # a P-core (cpu0-15)
    taskset -c 20 python bench_pe_core_and_xla.py plain   # an E-core (cpu16-31)

MEASURED 2026-07-30 on dell-8960-ext (i9-13900K: 8 P-cores @5.9 GHz w/ SMT =
cpu0-15, 16 E-cores @4.3 GHz = cpu16-31, one 36 MB L3), idle box, JAX_PLATFORMS=cpu:

    P-core   3.26 s      E-core  5.06 s   -> P:E = 1.55x on THIS workload
    unpinned 3.26 s      (landed on a P-core every run: cpu 4, 8, 12)
    after `import jax` + 3 x (4000^2 matmul), same pinned P-core:  3.21 s (0.979x)
    after jax.clear_caches():                                     3.24 s (0.987x)
    102 live XLA threads consumed 0.004 s of CPU over 3 idle seconds

Conclusions drawn from that: an XLA-loaded process does NOT slow equivalent numpy
work (refutes the allocator/heap and thread-spin hypotheses at proxy scale), while
core class alone is worth 1.55x -- so placement, not runtime interference, is the
live microarchitectural hypothesis.  Re-run this before re-proposing either.
"""
import os, sys, time, gc, resource

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np


def nthreads():
    with open("/proc/self/status") as f:
        for ln in f:
            if ln.startswith("Threads:"):
                return int(ln.split()[1])
    return -1


def oncpu():
    return int(open("/proc/self/stat").read().rsplit(") ", 1)[1].split()[36])


def cputime():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime, r.ru_minflt


def workload(T=400, ntypes=21, N=9982):
    grid = np.linspace(0.1, 50.0, 400)
    vals = np.sqrt(grid)
    rng = np.random.default_rng(0)
    states = [rng.random(N) * 40 + 0.5 for _ in range(ntypes)]
    tot = 0.0
    for _t in range(T):
        for s in states:
            idx = np.searchsorted(grid, s)
            np.clip(idx, 1, len(grid) - 1, out=idx)
            lo = grid[idx - 1]
            hi = grid[idx]
            w = (s - lo) / (hi - lo)
            c = vals[idx - 1] * (1.0 - w) + vals[idx] * w
            s *= 0.999
            s += 0.01 * c
            tot += c[0]
    return tot


def timed(tag):
    gc.collect()
    c0, f0 = cputime()
    t0 = time.perf_counter()
    workload()
    w = time.perf_counter() - t0
    c1, f1 = cputime()
    print(f"{tag:22s} wall={w:7.2f}s  cpu={c1-c0:7.2f}s  cpu/wall={(c1-c0)/w:5.2f}"
          f"  minflt={f1-f0:8d}  threads={nthreads():3d}  cpu#={oncpu():2d}",
          flush=True)
    return w


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "plain"
    print(f"== mode={mode}  pinned_to={os.sched_getaffinity(0)}", flush=True)
    a = timed("baseline")
    if mode == "xla":
        t0 = time.perf_counter()
        import jax
        import jax.numpy as jnp
        print(f"   import jax {time.perf_counter()-t0:.1f}s  devices={jax.devices()}"
              f"  threads={nthreads()}", flush=True)
        # mimic the AD stage: real XLA compilation + a few GB of arena churn
        f = jax.jit(lambda x: (x @ x.T).sum())
        for _ in range(3):
            x = jnp.asarray(np.random.default_rng(0).random((4000, 4000)))
            f(x).block_until_ready()
        del x, f
        print(f"   after XLA burn: threads={nthreads()}", flush=True)
        # is the XLA pool burning CPU while we do nothing?
        c0, _ = cputime()
        t0 = time.perf_counter()
        time.sleep(3.0)
        c1, _ = cputime()
        print(f"   idle 3s: cpu consumed={c1-c0:.3f}s  (spin => ~>0.1)", flush=True)
        b = timed("after-XLA")
        gc.collect()
        jax.clear_caches()
        c = timed("after-clear_caches")
        print(f"RATIO after-XLA/baseline = {b/a:.3f}   after-clear/baseline = {c/a:.3f}")
