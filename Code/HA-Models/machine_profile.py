"""Machine resource probe + welfare-6 slot planning (2026-08-02).

Replaces the machine-specific hardwired slot defaults (max_gpu_slots=1 /
max_cpu_slots=2, tuned to one box in the retired JAX-2B ~17 GB/child era)
with a run-start probe of the actual hardware, so the same code runs
efficiently on a 16-core laptop and a 32-thread workstation without edits.

Precedence for every knob: explicit CLI flag > HAFISCAL_MAX_*_SLOTS env >
this probe's plan. The probe only ever supplies DEFAULTS.

Measured anchors behind the plan formula (certification 2026-08-02,
plans/20260802-0300h_canonical-hybrid-default_plan.md):
- The certified hybrid battery ran 8 CPU children on 32 logical cores /
  ~60 GB (i9-13900K) at a 53-54 min wall, mean utilization 25 cores
  (~3 cores/child) with comfortable memory headroom (~7 GB/child envelope
  post-BUG-064; the 17 GB/child figure was JAX-2B-only, retired).
- More than 8 slots buys nothing at Baseline: the battery is packing-bound
  (12 scenarios, LPT critical chain), so 8 is the cap until re-measured.
- GPU slots default to 0 REGARDLESS of availability: the GPU lane is dead
  at battery scale with proof (device-invariant results at 1e-15, gpu-arm
  wall WORSE 75 vs 71 min, CUDA delivery under the replay engine void) —
  see conclusions_private/2026-08-01_jaxad-graduation.md. Probing still
  records GPU presence so explicit dev arms know what exists — and so a
  bare run on a GPU-less machine no longer hard-fails on the CUDA env.

Allocation-awareness (2026-08-03, Rockfish/ccarroll-m5 portability pass):
the probe now reports EFFECTIVE resources next to the physical ones —
`len(os.sched_getaffinity(0))` (the cgroup-cpuset truth under SLURM or
taskset; absent on macOS), SLURM_CPUS_PER_TASK/ON_NODE, cgroup-v2
memory.max, and SLURM_MEM_PER_NODE/PER_CPU — and the planner budgets from
the effective numbers with reserve 0 under a scheduler (the allocation is
already carved out of a shared node; reserving 2 of a 4-core grant would
waste half of it). Unconfined machines plan exactly as before (verified:
dell-8960 32c/60G -> 7 slots; ccarroll-m5 M5 Max 18c/128G -> 4 slots).
Measured motivation: os.cpu_count() reads 32 under `taskset -c 0-5` while
affinity reads 6; Rockfish standard nodes are 48c/192G SLURM-shared, so a
partial allocation planned from node totals would oversubscribe its cgroup
and be OOM-killed. macOS note: RLIMIT_AS-style memory guards are unusable
on Darwin (a 1 GB cap is rejected — processes map ~100s of GB of shared-
cache address space), so the 7 GB/child planning envelope IS the memory
protection there.
"""

import os
import shutil
import subprocess

# Certified-anchor constants (see module docstring for provenance)
_CORES_PER_CHILD = 4        # ~3 cores/child measured mean + headroom
_MEM_GB_PER_CHILD = 7       # per-child memory envelope, hybrid engine
_MAX_CPU_SLOTS_CAP = 8      # packing-bound beyond this at Baseline (12 scenarios)
# System reserve (owner directives 2026-08-02, revised same day): leave 2
# cores untrammeled by default so the machine stays responsive under a full
# battery (was clamp(cores/8,2,4); owner: 2 is enough).
_RESERVE_DEFAULT = 2


def _affinity_cores():
    """CPUs this process may actually run on, or None.

    On Linux this respects cgroup cpusets — i.e. a SLURM allocation or a
    `taskset` confinement — where os.cpu_count() still reports the whole
    node (measured on Rockfish-class setups: cpu_count=48 vs allocation=12).
    Absent on macOS (no sched_getaffinity there; a whole-machine run is the
    only mode on the Macs anyway)."""
    try:
        return len(os.sched_getaffinity(0)) or None
    except (AttributeError, OSError):
        return None


def _slurm_context(env):
    """(effective_cores, source) from SLURM's own env, plus the job id.

    SLURM_CPUS_PER_TASK is what `-c` granted this task (preferred);
    SLURM_CPUS_ON_NODE is the job's total on this node. Returns
    (None, None, None) outside SLURM."""
    job_id = env.get("SLURM_JOB_ID") or env.get("SLURM_JOBID")
    if not job_id:
        return None, None, None
    for var in ("SLURM_CPUS_PER_TASK", "SLURM_CPUS_ON_NODE"):
        v = (env.get(var) or "").strip()
        if v:
            try:
                return max(1, int(v)), var, job_id
            except ValueError:
                pass
    return None, None, job_id


def _cgroup_mem_gb():
    """cgroup-v2 memory.max walking up from this process's cgroup, or None.

    This is the limit a SLURM job is actually killed at; /proc/meminfo and
    sysconf report the whole node. 'max' (unlimited) and any read failure
    -> None."""
    try:
        with open("/proc/self/cgroup") as f:
            rel = f.read().strip().split("::", 1)[-1]
        path = os.path.join("/sys/fs/cgroup", rel.lstrip("/"))
        while path.startswith("/sys/fs/cgroup"):
            p = os.path.join(path, "memory.max")
            if os.path.exists(p):
                with open(p) as f:
                    v = f.read().strip()
                if v.isdigit():
                    return round(int(v) / 1024 ** 3, 1)
                return None  # 'max' = unlimited
            parent = os.path.dirname(path)
            if parent == path:
                break
            path = parent
    except OSError:
        pass
    return None


def _slurm_mem_gb(env, effective_cores):
    """The job's memory grant from SLURM env (MB units), or None."""
    v = (env.get("SLURM_MEM_PER_NODE") or "").strip()
    if v.isdigit():
        return round(int(v) / 1024, 1)
    v = (env.get("SLURM_MEM_PER_CPU") or "").strip()
    if v.isdigit() and effective_cores:
        return round(int(v) * effective_cores / 1024, 1)
    return None


def _darwin_perflevels():
    """{'perflevel0': n, 'perflevel1': n} on Apple Silicon, else None.

    Recorded (not acted on): the cores/child anchor was measured on a
    heterogeneous P/E box already (i9-13900K), so the plan formula absorbs
    asymmetry empirically; this just makes the topology inspectable."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.perflevel0.logicalcpu",
             "hw.perflevel1.logicalcpu"],
            capture_output=True, text=True, timeout=5)
        vals = out.stdout.split()
        if out.returncode == 0 and len(vals) >= 2:
            return {"perflevel0": int(vals[0]), "perflevel1": int(vals[1])}
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def probe_machine(env=None):
    """Best-effort, stdlib-only hardware probe. Never raises.

    Reports BOTH the physical machine (logical_cores, mem_gb) and the
    EFFECTIVE resources this process was actually granted (effective_cores,
    effective_mem_gb) — these differ under a scheduler (SLURM cgroup
    confinement on Rockfish) or taskset, where planning from the physical
    numbers oversubscribes the allocation."""
    if env is None:
        env = os.environ
    cores = os.cpu_count() or 4
    mem_gb = _probe_mem_gb()

    slurm_cores, slurm_src, slurm_job = _slurm_context(env)
    affinity = _affinity_cores()
    eff_cores, cores_source = cores, "cpu_count"
    for cand, src in ((affinity, "affinity"),
                      (slurm_cores, f"slurm:{slurm_src}" if slurm_src else None)):
        if cand and src and cand < eff_cores:
            eff_cores, cores_source = cand, src

    cg_mem = _cgroup_mem_gb()
    sl_mem = _slurm_mem_gb(env, eff_cores)
    eff_mem, mem_source = mem_gb, "physical"
    for cand, src in ((cg_mem, "cgroup"), (sl_mem, "slurm")):
        if cand and cand < eff_mem:
            eff_mem, mem_source = cand, src

    import sys as _sys
    return {
        "logical_cores": cores,
        "effective_cores": eff_cores,
        "cores_source": cores_source,
        "mem_gb": mem_gb,
        "effective_mem_gb": eff_mem,
        "mem_source": mem_source,
        "scheduler": ({"kind": "slurm", "job_id": slurm_job}
                      if slurm_job else None),
        "cpu_topology": (_darwin_perflevels()
                         if _sys.platform == "darwin" else None),
        "gpus": _probe_gpus(),
        "hostname": os.uname().nodename if hasattr(os, "uname") else "?",
    }


def _probe_mem_gb():
    try:  # POSIX (Linux + macOS)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
                     / 1024 ** 3, 1)
    except (ValueError, OSError, AttributeError):
        pass
    try:  # Linux fallback
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024 ** 2, 1)
    except OSError:
        pass
    return 16.0  # conservative default when unprobeable


def _probe_gpus():
    """List of {name, vram_gb} via nvidia-smi; [] when absent/failing."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return []
    try:
        out = subprocess.run(
            [smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return []
        gpus = []
        for line in out.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            vram = None
            if len(parts) > 1 and parts[1].split():
                tok = parts[1].split()
                try:
                    vram = round(float(tok[0]) / (1024 if tok[-1] == "MiB" else 1), 1)
                except ValueError:
                    pass
            gpus.append({"name": parts[0], "vram_gb": vram})
        return gpus
    except (OSError, subprocess.SubprocessError):
        return []


def effective_cpu_count():
    """Affinity-aware CPU count for budgeters outside the slot planner.

    == os.cpu_count() on an unconfined box; == the allocation size under a
    cgroup cpuset (SLURM on Rockfish, taskset). The single primitive every
    worker-count formula should use instead of raw os.cpu_count()."""
    return _affinity_cores() or os.cpu_count() or 1


def plan_welfare6_slots(profile=None, env=None):
    """Resolve {max_cpu_slots, max_gpu_slots} for this machine.

    Formula (anchors in the module docstring):
      cores     = EFFECTIVE cores (allocation-aware; == logical unconfined)
      usable    = cores - reserve   # reserve 2, or 0 under a scheduler:
                                    # a SLURM allocation is already carved
                                    # out of a shared node — there is no
                                    # interactive system to keep responsive,
                                    # and reserving 2 of a 4-core grant
                                    # would waste half of it
      cpu_slots = clamp(min(usable // 4, eff_mem_gb // 7), 1, 8)
      gpu_slots = 0  (dead lane by measurement; explicit opt-in only)
    HAFISCAL_CPU_RESERVE_CORES overrides the reserve.
    HAFISCAL_MAX_CPU_SLOTS / HAFISCAL_MAX_GPU_SLOTS env vars override.

    Accepts legacy profile dicts (no effective_* keys): they plan exactly
    as before (unconfined semantics).
    """
    if profile is None:
        profile = probe_machine()
    if env is None:
        env = os.environ
    cores = profile.get("effective_cores") or profile["logical_cores"]
    mem_gb = profile.get("effective_mem_gb") or profile["mem_gb"]
    under_scheduler = bool(profile.get("scheduler"))
    reserve_default = 0 if under_scheduler else _RESERVE_DEFAULT
    reserve = min(reserve_default, max(0, cores - 1))  # tiny machines: keep >=1 usable
    _r_env = env.get("HAFISCAL_CPU_RESERVE_CORES", "").strip()
    if _r_env:
        try:
            reserve = max(0, min(int(_r_env), cores - 1))
        except ValueError:
            print(f"[machine-profile] ignoring non-integer "
                  f"HAFISCAL_CPU_RESERVE_CORES={_r_env!r}", flush=True)
    usable = max(1, cores - reserve)
    cpu_slots = max(1, min(usable // _CORES_PER_CHILD,
                           int(mem_gb // _MEM_GB_PER_CHILD),
                           _MAX_CPU_SLOTS_CAP))
    plan = {"max_cpu_slots": cpu_slots, "max_gpu_slots": 0,
            "reserve_cores": reserve, "usable_cores": usable}
    for var, key in (("HAFISCAL_MAX_CPU_SLOTS", "max_cpu_slots"),
                     ("HAFISCAL_MAX_GPU_SLOTS", "max_gpu_slots")):
        v = env.get(var, "").strip()
        if v:
            try:
                plan[key] = max(0, int(v))
            except ValueError:
                print(f"[machine-profile] ignoring non-integer {var}={v!r}",
                      flush=True)
    if plan["max_cpu_slots"] < 1:
        plan["max_cpu_slots"] = 1
    plan["profile"] = profile
    return plan


def describe(plan):
    p = plan["profile"]
    gpus = (", ".join(g["name"] for g in p["gpus"]) or "none")
    cores_txt = f"{p['logical_cores']} cores"
    eff_c = p.get("effective_cores")
    if eff_c and eff_c != p["logical_cores"]:
        cores_txt += (f" (EFFECTIVE {eff_c} via {p.get('cores_source')} — "
                      f"planning from the allocation, not the node)")
    mem_txt = f"{p['mem_gb']} GB RAM"
    eff_m = p.get("effective_mem_gb")
    if eff_m and eff_m != p["mem_gb"]:
        mem_txt += f" (EFFECTIVE {eff_m} GB via {p.get('mem_source')})"
    sched = p.get("scheduler")
    sched_txt = (f", scheduler={sched['kind']}:{sched.get('job_id')}"
                 if sched else "")
    return (f"[machine-profile] {p['hostname']}: {cores_txt} "
            f"({plan['reserve_cores']} reserved for the system, "
            f"{plan['usable_cores']} usable), {mem_txt}{sched_txt}, "
            f"GPU: {gpus} -> cpu_slots={plan['max_cpu_slots']} "
            f"gpu_slots={plan['max_gpu_slots']} (probe defaults; CLI/env override)")
