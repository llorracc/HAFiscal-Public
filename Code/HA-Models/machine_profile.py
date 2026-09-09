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
# Per-child memory envelope: the FULL end-to-end peak of a cold newton2d
# battery child at the certified dw=sw=4 shape. Measured 2026-08-07 (plan
# 20260807-0919h C1): one recessionCheck_AD solo to completion under the
# scope (78.9 min, 189 solves, bitwise-identical output to the pre-A1
# reference) peaked at 9.4 GiB with malloc_trim + R1 (post-step pairs
# release) + A1 (col_lo dropped) in — down from 18.5 pre-trim and 12.1
# post-trim (both 2026-08-06); +margin => 11. The ladder 7 (hybrid
# cache-warm) -> 9 (mid-growth snapshot) -> 18 (pre-trim cold peak) -> 11
# (post trim/R1/A1, measured 9.4 + margin) is phase/cache-state/
# code-version dependence, not remeasurement noise; production cache-HIT
# batteries never see this footprint. 11 -> 12 (owner ruling R4,
# 2026-08-07 evening): the numba kernel is now the default at the
# Step-5a/welfare6 entry points and cold-numba solos peaked 10.8 (the
# flat ping-pong Jacobian buffers) — 12 = 10.8 + margin; jhu-dell still
# plans 3 slots.
_MEM_GB_PER_CHILD = 12
# WARM envelope (owner 2026-09-07, the slot fix): a policy-store HIT child never builds the cold
# numba buffers -- the 2026-09-07 band's children measured 4.5-5.0 GB (6 processes each, N=9,982,
# [mem] census) against the 12 GB cold peak, so the 40 GB cgroup on jhu-dell was planning 3 slots
# (four waves of 12 scenarios, 9.3 min/seed on 2.7 of 30 cores). The warm value is used ONLY when a
# cold solve cannot happen by construction: HAFISCAL_POLICY_STORE_REQUIRE=1 turns a store MISS into
# an error instead of a solve (solution_cache/policy_store.require_hits). Otherwise the cold
# envelope stands -- a fresh machine, a changed solver source or a new calibration must never be
# planned on the warm number. HAFISCAL_WELFARE_CHILD_GB (numeric) overrides either, for measurement.
_MEM_GB_PER_CHILD_WARM = 6
_MAX_CPU_SLOTS_CAP = 8      # packing-bound beyond this at Baseline (12 scenarios)
# System reserve (owner directives 2026-08-02, revised same day): leave 2
# cores untrammeled by default so the machine stays responsive under a full
# battery (was clamp(cores/8,2,4); owner: 2 is enough).
_RESERVE_DEFAULT = 2
# G1, plan 20260806-1211h (OOM record 20260806-0101h): the memory analog of
# the cores reserve — the interactive-machine allowance subtracted from the
# memory term. Added to a LIVE Unevictable probe (a vmtouch mlock pin is
# invisible to MemTotal but structurally unreclaimable). 0 under a
# scheduler, mirroring the cores logic (the cgroup grant is already carved).
_MEM_RESERVE_GB_DEFAULT = 4


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

    unevict_gb, avail_gb = _probe_meminfo_extras()
    gpus, gpu_driver_error = _probe_gpus()
    import sys as _sys
    return {
        "logical_cores": cores,
        "effective_cores": eff_cores,
        "cores_source": cores_source,
        "mem_gb": mem_gb,
        "effective_mem_gb": eff_mem,
        "mem_source": mem_source,
        "unevictable_gb": unevict_gb,
        "mem_available_gb": avail_gb,
        "scheduler": ({"kind": "slurm", "job_id": slurm_job}
                      if slurm_job else None),
        "cpu_topology": (_darwin_perflevels()
                         if _sys.platform == "darwin" else None),
        "gpus": gpus,
        "gpu_stack": probe_gpu_stack(gpus, gpu_driver_error),
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


def _probe_meminfo_extras():
    """(Unevictable GiB, MemAvailable GiB) from /proc/meminfo; (None, None)
    where unreadable (macOS). Unevictable makes an mlock pin (e.g. a vmtouch
    OS-cache pin) visible to the planner — it is invisible to MemTotal by
    construction and the kernel is structurally forbidden to reclaim it."""
    unevict = avail = None
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("Unevictable:"):
                    unevict = round(int(line.split()[1]) / 1024 ** 2, 1)
                elif line.startswith("MemAvailable:"):
                    avail = round(int(line.split()[1]) / 1024 ** 2, 1)
    except OSError:
        pass
    return unevict, avail


def _gpu_mib_to_gb(tok):
    try:
        t = tok.split()
        return round(float(t[0]) / (1024 if t[-1] == "MiB" else 1), 1)
    except (ValueError, IndexError):
        return None


def _parse_gpu_query(text, fields):
    """Parse nvidia-smi CSV output into per-GPU dicts (pure; unit-testable)."""
    gpus = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != len(fields):
            continue
        g = {}
        for key, raw in zip(fields, parts):
            if key in ("memory.total", "memory.free"):
                g[{"memory.total": "vram_gb",
                   "memory.free": "vram_free_gb"}[key]] = _gpu_mib_to_gb(raw)
            elif key == "utilization.gpu":
                try:
                    g["utilization_pct"] = int(raw.split()[0])
                except (ValueError, IndexError):
                    g["utilization_pct"] = None
            elif key == "index":
                try:
                    g["index"] = int(raw)
                except ValueError:
                    g["index"] = None
            elif key == "compute_cap":
                g["compute_cap"] = raw or None
            elif key == "driver_version":
                g["driver_version"] = raw or None
            else:
                g[key] = raw
        gpus.append(g)
    return gpus


_GPU_QUERY_FIELDS = ("index", "name", "memory.total", "memory.free",
                     "compute_cap", "driver_version", "utilization.gpu")


def _probe_gpus():
    """GPU hardware inventory + driver health via nvidia-smi.

    Returns ``(gpus, driver_error)``: per-GPU dicts (index, name, vram_gb,
    vram_free_gb, compute_cap, driver_version, utilization_pct) and a
    driver-health string — None when healthy, else the failure ("nvidia-smi
    absent" on GPU-less/AMD/mac boxes; the stderr tail on an NVML
    driver/library mismatch, the classic broken-driver-pin signature).
    Falls back to a reduced query on old nvidia-smi without compute_cap.
    """
    smi = shutil.which("nvidia-smi")
    if not smi:
        return [], "nvidia-smi absent"
    for fields in (_GPU_QUERY_FIELDS,
                   ("index", "name", "memory.total", "memory.free",
                    "driver_version", "utilization.gpu")):
        try:
            out = subprocess.run(
                [smi, f"--query-gpu={','.join(fields)}",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as e:
            return [], f"nvidia-smi failed: {e}"
        if out.returncode == 0:
            return _parse_gpu_query(out.stdout, fields), None
        err = (out.stderr or out.stdout).strip().splitlines()
        if fields is not _GPU_QUERY_FIELDS or "compute_cap" not in str(err):
            return [], (err[-1] if err else f"nvidia-smi rc={out.returncode}")
    return [], "nvidia-smi query failed"


def nvidia_venv_lib_dirs():
    """Colon-joined venv ``nvidia/*/lib`` dirs (cuBLAS, cuSPARSE, cuDNN, …)
    for LD_LIBRARY_PATH so JAX-CUDA can dlopen them at runtime. Without these
    on the loader path jax fails "Unable to load cuSPARSE" and SILENTLY falls
    back to CPU (diagnosed 2026-06-23: the .so's are present, just not
    found). Pure loader-search-path fix. '' if none. SST home of the logic
    formerly private to run_welfare6_parallel."""
    import sys as _sys
    import glob as _glob
    venv = os.path.dirname(os.path.dirname(_sys.executable))
    for py_dir in ("python3.11", "python3.12", "python3.10"):
        base = os.path.join(venv, "lib", py_dir, "site-packages", "nvidia")
        if os.path.isdir(base):
            dirs = sorted(_glob.glob(os.path.join(base, "*", "lib")))
            if dirs:
                return ":".join(dirs)
    return ""


def nvjitlink_preload_path():
    """venv libnvJitLink.so.12 for LD_PRELOAD (the 2026-06 quirk: jax-cuda
    needs it preloaded on this stack); None when absent."""
    import sys as _sys
    venv = os.path.dirname(os.path.dirname(_sys.executable))
    for py_dir in ("python3.11", "python3.12", "python3.10"):
        cand = os.path.join(venv, "lib", py_dir, "site-packages",
                            "nvidia", "nvjitlink", "lib",
                            "libnvJitLink.so.12")
        if os.path.exists(cand):
            return cand
    return None


def probe_gpu_stack(gpus=None, driver_error=None, _find_spec=None):
    """Everything the code needs to know to USE the GPUs on request.

    Static checks only (no jax import, no CUDA context — safe to run at
    every battery start): hardware inventory + driver health (from
    ``_probe_gpus``), jax + jax CUDA plugin presence/versions, the venv
    nvidia lib dirs LD_LIBRARY_PATH needs, and the nvjitlink preload path.
    Returns a dict with ``usable`` (bool), ``reasons`` (why not, in check
    order), ``warnings`` (usable-but-note), plus the ingredients
    (jax_version, cuda_plugin_version, lib_dirs, nvjitlink, driver_version).
    The DEFINITIVE runtime test (actually initializing a CUDA context) is
    ``gpu_deep_check()`` — subprocess-isolated, run on demand only.
    """
    if _find_spec is None:
        from importlib.util import find_spec as _find_spec
    if gpus is None:  # caller passes both or neither (None error = healthy)
        gpus, driver_error = _probe_gpus()
    reasons, warnings_ = [], []
    if driver_error == "nvidia-smi absent":
        reasons.append("no NVIDIA driver/tools (nvidia-smi absent)")
    elif driver_error:
        reasons.append(f"driver unhealthy: {driver_error}")
    elif not gpus:
        reasons.append("no NVIDIA GPUs present")

    def _ver(dist):
        try:
            from importlib.metadata import version
            return version(dist)
        except Exception:
            return None

    jax_ver = cuda_plugin_ver = None
    try:
        if _find_spec("jax") is None:
            reasons.append("jax not installed")
        else:
            jax_ver = _ver("jax")
        if _find_spec("jax_cuda12_plugin") is None:
            reasons.append("jax CUDA plugin not installed "
                           "(pip: jax[cuda12] / jax-cuda12-plugin)")
        else:
            cuda_plugin_ver = _ver("jax-cuda12-plugin")
    except Exception as e:  # never let stack introspection break a probe
        reasons.append(f"stack introspection failed: {e}")
    lib_dirs = nvidia_venv_lib_dirs()
    if not lib_dirs:
        reasons.append("venv nvidia/*/lib dirs missing (pip nvidia-*-cu12 "
                       "stack) — jax-cuda would silently fall back to CPU")
    nvjit = nvjitlink_preload_path()
    if lib_dirs and nvjit is None:
        warnings_.append("libnvJitLink.so.12 not found for LD_PRELOAD "
                         "(needed on the 2026-06 stack; newer jax may not)")
    return {
        "usable": not reasons,
        "reasons": reasons,
        "warnings": warnings_,
        "driver_version": (gpus[0].get("driver_version")
                           if gpus else None),
        "jax_version": jax_ver,
        "cuda_plugin_version": cuda_plugin_ver,
        "lib_dirs": lib_dirs,
        "nvjitlink": nvjit,
    }


def gpu_deep_check(timeout=90):
    """The definitive on-request test: initialize jax-CUDA in a THROWAWAY
    subprocess (never in the caller — a CUDA context in a battery parent
    would leak into every fork child) with exactly the env the GPU children
    get, and report the devices jax actually sees. ~5-15 s. Returns
    {"ok", "devices", "error"}."""
    import sys as _sys
    stack = probe_gpu_stack()
    if not stack["usable"]:
        return {"ok": False, "devices": [],
                "error": "; ".join(stack["reasons"])}
    env = dict(os.environ)
    env["JAX_PLATFORMS"] = "cuda"
    if stack["lib_dirs"]:
        env["LD_LIBRARY_PATH"] = (stack["lib_dirs"] + ":"
                                  + env.get("LD_LIBRARY_PATH", "")).rstrip(":")
    if stack["nvjitlink"]:
        env["LD_PRELOAD"] = stack["nvjitlink"]
    code = ("import jax; "
            "print('|'.join(str(d) for d in jax.devices()))")
    try:
        out = subprocess.run([_sys.executable, "-c", code],
                             capture_output=True, text=True,
                             timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "devices": [],
                "error": f"jax CUDA init exceeded {timeout}s"}
    except OSError as e:
        return {"ok": False, "devices": [], "error": str(e)}
    if out.returncode != 0:
        tail = (out.stderr or out.stdout).strip().splitlines()
        return {"ok": False, "devices": [],
                "error": tail[-1] if tail else f"rc={out.returncode}"}
    devs = [d for d in out.stdout.strip().split("|") if d]
    cuda = [d for d in devs if "cuda" in d.lower() or "gpu" in d.lower()]
    return {"ok": bool(cuda), "devices": devs,
            "error": None if cuda else "jax initialized but saw no CUDA "
            "device (silent CPU fallback)"}


def effective_cpu_count():
    """Affinity-aware CPU count for budgeters outside the slot planner.

    == os.cpu_count() on an unconfined box; == the allocation size under a
    cgroup cpuset (SLURM on Rockfish, taskset). The single primitive every
    worker-count formula should use instead of raw os.cpu_count()."""
    return _affinity_cores() or os.cpu_count() or 1


def child_envelope_gb(env=None):
    """(gb, label): the per-child memory envelope the planner divides by. 'cold' (12 GB) unless
    the policy store is in require-hit mode ('warm', 6 GB) or HAFISCAL_WELFARE_CHILD_GB is set
    ('explicit'). See _MEM_GB_PER_CHILD_WARM for the reasoning."""
    if env is None:
        env = os.environ
    v = env.get("HAFISCAL_WELFARE_CHILD_GB", "").strip()
    if v:
        try:
            return max(1.0, float(v)), "explicit"
        except ValueError:
            print(f"[machine-profile] ignoring non-numeric HAFISCAL_WELFARE_CHILD_GB={v!r}", flush=True)
    # same truthy set as solution_cache/policy_store.require_hits (_TRUTHY)
    if env.get("HAFISCAL_POLICY_STORE_REQUIRE", "").strip().lower() in ("1", "on", "true"):
        return float(_MEM_GB_PER_CHILD_WARM), "warm"
    return float(_MEM_GB_PER_CHILD), "cold"


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
      cpu_slots = clamp(min(usable // 4, usable_mem_gb // 18), 1, 8)
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
    child_gb, envelope = child_envelope_gb(env)
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
    # G1 (plan 20260806-1211h; incident 20260806-0101h): a memory reserve
    # symmetric with the cores reserve. The old formula divided TOTAL RAM by
    # the per-child envelope — on a workstation with a 9 GiB mlock pin and a
    # desktop it authorized 7×7=49 GB = 100% of what the machine had left,
    # and the global OOM killed the USER'S SESSION (oom_score_adj ordering).
    # Reserve = live Unevictable + a 4 GB interactive allowance (0 under a
    # scheduler); MemAvailable enters ONLY as a min-component — alone it
    # provably still yields the fatal slot count (record §7.1).
    # HAFISCAL_MEM_RESERVE_GB: numeric override; 'off' disables G1 entirely.
    unevict_gb = profile.get("unevictable_gb") or 0.0
    avail_gb = profile.get("mem_available_gb")
    # v2 (contained-OOM 2026-08-06 13:41): when the planning base is already
    # a cgroup cap (the mem-guard scope, itself pin-aware since v2), do NOT
    # re-subtract the pin — that double-count cost a slot; the availability
    # arm (global truth) covers the pin independently. Unconfined physical
    # base keeps the full reserve.
    under_cgroup = profile.get("mem_source") == "cgroup"
    mem_reserve = (0.0 if under_scheduler
                   else _MEM_RESERVE_GB_DEFAULT if under_cgroup
                   else _MEM_RESERVE_GB_DEFAULT + unevict_gb)
    _m_env = env.get("HAFISCAL_MEM_RESERVE_GB", "").strip().lower()
    g1_off = _m_env == "off"
    if _m_env and not g1_off:
        try:
            mem_reserve = max(0.0, float(_m_env))
        except ValueError:
            print(f"[machine-profile] ignoring non-numeric "
                  f"HAFISCAL_MEM_RESERVE_GB={_m_env!r}", flush=True)
    if g1_off:
        usable_mem = float(mem_gb)
        mem_reserve = 0.0
    else:
        usable_mem = float(mem_gb) - mem_reserve
        if avail_gb is not None:
            # The availability arm accounts for what system + other apps
            # ACTUALLY use right now (MemAvailable already nets out the
            # mlock pin and resident apps — do not re-subtract the pin
            # here), minus a growth margin: granting 100% of what is
            # currently free repeats the incident's zero-headroom pattern
            # from a lower base (apps grow; the page cache needs room).
            usable_mem = min(usable_mem,
                             float(avail_gb) - _MEM_RESERVE_GB_DEFAULT)
        usable_mem = max(child_gb, usable_mem)  # >=1 child
    cpu_slots = max(1, min(usable // _CORES_PER_CHILD,
                           int(usable_mem // child_gb),
                           _MAX_CPU_SLOTS_CAP))
    plan = {"max_cpu_slots": cpu_slots, "max_gpu_slots": 0,
            "reserve_cores": reserve, "usable_cores": usable,
            "mem_reserve_gb": round(mem_reserve, 1),
            "usable_mem_gb": round(usable_mem, 1),
            "child_gb": child_gb, "envelope": envelope}
    for var, key in (("HAFISCAL_MAX_CPU_SLOTS", "max_cpu_slots"),
                     ("HAFISCAL_MAX_GPU_SLOTS", "max_gpu_slots")):
        v = env.get(var, "").strip()
        if v:
            try:
                plan[key] = max(0, int(v))
            except ValueError:
                print(f"[machine-profile] ignoring non-integer {var}={v!r}",
                      flush=True)
    # GPU "upon request" gate (owner charge 2026-08-06): an explicit
    # HAFISCAL_MAX_GPU_SLOTS opt-in is honored ONLY when the probed GPU
    # stack is actually usable — requesting CUDA children on a box with a
    # broken driver pin or a CPU-only jax install must fail loudly at plan
    # time, not silently-fall-back (or crash) per child at solve time.
    if plan["max_gpu_slots"] > 0:
        stack = profile.get("gpu_stack") or probe_gpu_stack()
        if not stack.get("usable"):
            print("[machine-profile] HAFISCAL_MAX_GPU_SLOTS="
                  f"{plan['max_gpu_slots']} requested but the GPU stack is "
                  f"unusable ({'; '.join(stack.get('reasons', ['unknown']))})"
                  " -> gpu_slots=0", flush=True)
            plan["max_gpu_slots"] = 0
        elif plan["max_gpu_slots"] > len(profile.get("gpus") or []):
            print(f"[machine-profile] note: {plan['max_gpu_slots']} GPU "
                  f"slots requested on {len(profile.get('gpus') or [])} "
                  "GPU(s) — children will share devices", flush=True)
    if plan["max_cpu_slots"] < 1:
        plan["max_cpu_slots"] = 1
    plan["profile"] = profile
    return plan


def describe(plan):
    p = plan["profile"]
    gpus = (", ".join(
        g["name"] + (f" {g['vram_free_gb']}/{g['vram_gb']}G free"
                     if g.get("vram_gb") is not None else "")
        + (f" cc{g['compute_cap']}" if g.get("compute_cap") else "")
        for g in p["gpus"]) or "none")
    stack = p.get("gpu_stack")
    if stack is not None and p["gpus"]:
        if stack["usable"]:
            gpus += (f" [stack READY: driver {stack['driver_version']}, "
                     f"jax {stack['jax_version']} + cuda plugin "
                     f"{stack['cuda_plugin_version']}"
                     + ("; " + "; ".join(stack["warnings"])
                        if stack["warnings"] else "") + "]")
        else:
            gpus += f" [stack UNUSABLE: {'; '.join(stack['reasons'])}]"
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
    line = (f"[machine-profile] {p['hostname']}: {cores_txt} "
            f"({plan['reserve_cores']} reserved for the system, "
            f"{plan['usable_cores']} usable), {mem_txt}{sched_txt}, "
            f"GPU: {gpus} -> cpu_slots={plan['max_cpu_slots']} "
            f"gpu_slots={plan['max_gpu_slots']} (probe defaults; CLI/env override)")
    # G4 (plan 20260806-1211h): print the MEMORY plan, not just the CPU plan —
    # the overnight OOM's 49-of-60.5 GB authorization was invisible in a log
    # that already recorded every CPU decision.
    if "mem_reserve_gb" in plan:
        claim = plan["max_cpu_slots"] * plan.get("child_gb", _MEM_GB_PER_CHILD)
        un = p.get("unevictable_gb")
        av = p.get("mem_available_gb")
        line += (f"\n[machine-profile] memory plan: {plan['max_cpu_slots']} "
                 f"slots x {plan.get('child_gb', _MEM_GB_PER_CHILD):g} GB ({plan.get('envelope', 'cold')} envelope) = {claim:g} GB of "
                 f"{p['mem_gb']} GB total (reserve {plan['mem_reserve_gb']} GB"
                 f"{f' incl. unevictable {un}' if un else ''}"
                 f"{f'; MemAvailable {av}' if av is not None else ''}; "
                 f"usable {plan['usable_mem_gb']} GB)")
    return line


if __name__ == "__main__":
    # Operator tool: `python machine_profile.py` prints the plan (incl. the
    # memory plan and GPU stack verdict); `--gpu-deep` additionally runs the
    # definitive subprocess jax-CUDA initialization test (~5-15 s).
    import sys as _sys
    print(describe(plan_welfare6_slots()))
    if "--gpu-deep" in _sys.argv:
        r = gpu_deep_check()
        print(f"[machine-profile] gpu deep check: "
              f"{'OK' if r['ok'] else 'FAIL'} devices={r['devices']}"
              + (f" error={r['error']}" if r["error"] else ""))
