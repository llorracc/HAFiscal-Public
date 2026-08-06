"""Parallel driver for welfare-6 MC computation.

Launches one subprocess per scenario via `welfare6_scenario.py`,
waits for all to finish, then loads the pickled arrays and computes
the welfare-6 table.

Each subprocess runs independently (no shared memory), rebuilds and
re-solves its own economy copy, and runs one of the 12 scenarios.
Empirically — via `validate_mc_crn.py` + `run_mc_crn_validation.py` —
CRN is preserved exactly across subprocesses given identical seeds,
so the parallel aggregate is bit-identical to the serial aggregate
that `run_hybrid_welfare6.py` would produce.

This script does not modify `run_hybrid_welfare6.py` or any other
existing file. It writes its output to a separate directory
(`Tables/{param}_parallel/welfare6.tex`) so the serial results are
left untouched and the two can be compared side-by-side.

Usage:
    python run_welfare6_parallel.py --parametrization Reduced_Run
    python run_welfare6_parallel.py --baseline --max-parallel 6
"""

import argparse
import json
import os
import pickle
import subprocess
import sys
from time import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIO_SCRIPT = os.path.join(HERE, "welfare6_scenario.py")


def _emit_provenance_sidecar(output_dirs, *, label=None, output_roots=None):
    """Best-effort: drop a RUN_<run_id>.prov.json next to this run's outputs.

    Unified run-provenance emitter (Code/HA-Models/provenance.py). Never raises —
    a provenance failure must not abort the simulation."""
    try:
        _ha = os.path.abspath(os.path.join(HERE, ".."))
        if _ha not in sys.path:
            sys.path.insert(0, _ha)
        import provenance as _prov
        _prov.emit(output_dirs, command=" ".join(sys.argv), argv=sys.argv,
                   label=label, output_roots=output_roots, verbose=True)
    except Exception as _e:  # pragma: no cover - best-effort
        print(f"[provenance] sidecar emit skipped (non-fatal): {_e}")

# Order matches run_hybrid_welfare6.py's scenario dispatch.
ALL_SCENARIOS = (
    "base",
    "Check", "UI", "TaxCut",
    "recession", "recessionUI", "recessionCheck", "recessionTaxCut",
    "recession_AD", "recessionUI_AD",
    "recessionCheck_AD", "recessionTaxCut_AD",
)

# AD-loop scenarios benefit most from GPU (per Step 1 measurements,
# the JAX 2B kernel runs ~3× faster on GPU than CPU at recession scale).
# Used by the slot-aware scheduler to route AD scenarios to the GPU slot.
_AD_SCENARIOS = frozenset({
    "recession_AD", "recessionUI_AD",
    "recessionCheck_AD", "recessionTaxCut_AD",
})

# UI scenarios per [NEVER report ui_norec] project memory: ui_norec
# welfare cell is 0/0 by construction (UI extension never activates in
# non-recession). Skip the UI runs entirely when --skip-ui is set.
_UI_SCENARIOS = frozenset({"UI", "recessionUI", "recessionUI_AD"})


def _venv_nvjitlink_path():
    """Locate the venv's libnvJitLink.so.12 needed for JAX-CUDA on this
    box (CUDA 12.6 system / 12.9 venv ABI mismatch — see
    Code/HA-Models/jax_mc_speedup/GPU_SETUP.md). Returns None if not
    present (no GPU available)."""
    import sys
    # sys.executable is .venv-linux-x86_64/bin/python; venv root is two dirs up.
    venv = os.path.dirname(os.path.dirname(sys.executable))
    for py_dir in ("python3.11", "python3.12", "python3.10"):
        candidate = os.path.join(
            venv, "lib", py_dir, "site-packages",
            "nvidia", "nvjitlink", "lib", "libnvJitLink.so.12",
        )
        if os.path.exists(candidate):
            return candidate
    return None


def _venv_nvidia_lib_dirs():
    """Colon-joined venv ``nvidia/*/lib`` dirs (cuBLAS, cuSPARSE, cuDNN, cuSOLVER, …) for
    LD_LIBRARY_PATH so JAX-CUDA can dlopen them at runtime. The nvjitlink LD_PRELOAD alone is
    NOT enough — without these dirs on the loader path jax fails "Unable to load cuSPARSE" and
    silently falls back to CPU (diagnosed 2026-06-23: the .so's are present, just not found).
    This is a pure loader-search-path fix — numpy/jax/venv are untouched. Returns '' if none."""
    import sys
    import glob
    venv = os.path.dirname(os.path.dirname(sys.executable))
    for py_dir in ("python3.11", "python3.12", "python3.10"):
        base = os.path.join(venv, "lib", py_dir, "site-packages", "nvidia")
        if os.path.isdir(base):
            dirs = sorted(glob.glob(os.path.join(base, "*", "lib")))
            if dirs:
                return ":".join(dirs)
    return ""


def _build_child_env(hw_slot, ad_cache=None):
    """Build per-child env dict. hw_slot in {'cpu', 'gpu'}.

    CPU children: JAX runs on CPU; HAFISCAL_PARALLEL_SOLVE=4 + 8 threads.
    GPU children: JAX_PLATFORMS=cuda + LD_PRELOAD nvjitlink + small
    host-thread budget (GPU is the bottleneck, host needs few threads).

    Universal hardenings: enable solution cache + JAX MC backend; set
    PYTHONUNBUFFERED so child stdout reaches log_fh promptly; pop
    dangerous inherited env vars (HAFISCAL_REFSIM_PARALLEL would create
    a 4×21=84 fork-worker cascade with 4 children).

    ``ad_cache`` (operator override of HAFISCAL_USE_SOLUTION_CACHE; Leg A1):
        None  → default behavior (setdefault ON unless the env already set it);
        True  → force the AD-converged solution cache ON  (HAFISCAL_USE_SOLUTION_CACHE=1);
        False → force it OFF (HAFISCAL_USE_SOLUTION_CACHE=0) regardless of
                the inherited env.
    Forcing is needed because a plain setdefault cannot override an inherited
    "1"; the explicit --no-ad-cache flag must win.

    NOTE (owner ruling 2026-06-12): HAFISCAL_USE_JAX_2B is DEV-ONLY and is no
    longer setdefault'd here — children use the canonical HARK solve_agent
    iter loop. (2B is ~1e-3 kernel parity, 0.045% welfare-cell shift per
    conclusions_private/2026-05-22_morning_summary.md — below the 2-dp
    reporting precision, but the canonical method is HARK.) Export
    HAFISCAL_USE_JAX_2B=1 explicitly for dev/speedup runs; it remains in the
    solution-cache key so cached solves never cross the boundary.
    """
    env = os.environ.copy()
    # Universal
    # Canonical welfare engine (owner-adopted 2026-08-02, plans/20260802-0300h):
    # one resolver setdefaults the certified hybrid bundle (replay-fed JAX-AD +
    # capture-presolve cache + sown-C tables; explicit per-flag env wins);
    # HAFISCAL_WELFARE_ENGINE=hark — or the as-corrected/QE-fidelity worlds —
    # restores the pre-arc path. Replaces the lone USE_JAX_MC setdefault that
    # lived here 2026-07-27..08-02 (hybrid's bundle carries it; hark leaves it
    # to this comment's old semantics: inert under the uncapped world).
    try:
        _ha_we = os.path.abspath(os.path.join(HERE, ".."))
        if _ha_we not in sys.path:
            sys.path.insert(0, _ha_we)
        from welfare_engine import apply_welfare_engine_defaults
        apply_welfare_engine_defaults(env, verbose=False)
    except Exception as _we_e:  # pragma: no cover - never abort the battery
        print(f"[run_welfare6_parallel] welfare_engine unavailable ({_we_e}); "
              "falling back to the legacy USE_JAX_MC default", flush=True)
        env.setdefault("HAFISCAL_USE_JAX_MC", "1")
    # AD-converged solution cache (solution_cache/ad_cache.py). Default-ON via
    # setdefault (Leg A); --ad-cache / --no-ad-cache force it on/off for the
    # operator. force-OFF must clear an inherited "1", so set explicitly.
    if ad_cache is True:
        env["HAFISCAL_USE_SOLUTION_CACHE"] = "1"
    elif ad_cache is False:
        env["HAFISCAL_USE_SOLUTION_CACHE"] = "0"
    else:
        env.setdefault("HAFISCAL_USE_SOLUTION_CACHE", "1")
    env["PYTHONUNBUFFERED"] = "1"
    # Suppress per-scenario provenance sidecars: the parallel driver emits ONE
    # aggregate sidecar next to the welfare6 table; 12 child sidecars in the
    # scratch pickle dir would be redundant (and 12× pip-freeze is wasteful).
    env["HAFISCAL_PROV_CHILD"] = "1"
    # Pop dangerous inherited vars
    for k in ("HAFISCAL_REFSIM_PARALLEL",
              "HAFISCAL_HARK_REFSIM_FULL",
              "HAFISCAL_USE_JAX_2B_VMAP"):
        env.pop(k, None)

    if hw_slot == "cpu":
        env["JAX_PLATFORMS"] = "cpu"
        env.setdefault("HAFISCAL_USE_JAX_2B_THREADS", "8")
        # PARALLEL_SOLVE=1 (NOT 4 as workflow plan suggested): each
        # spawn-pool worker is a full python process at ~17 GB RSS
        # when JAX 2B is active. With 2 CPU children × (1 main + 4
        # workers) × 17 GB = 170 GB → OOM on a 54 GB host (verified
        # by an empirical OOM kill at 2026-06-02T18:10 mid-bench).
        # Inner parallelism comes from JAX_2B_THREADS=8 instead
        # (threads share memory, no per-thread RSS).
        env["HAFISCAL_PARALLEL_SOLVE"] = "1"
        for k in ("LD_PRELOAD",
                  "XLA_PYTHON_CLIENT_PREALLOCATE",
                  "XLA_PYTHON_CLIENT_ALLOCATOR"):
            env.pop(k, None)
    elif hw_slot == "gpu":
        env["JAX_PLATFORMS"] = "cuda"
        nvjl = _venv_nvjitlink_path()
        if nvjl is None:
            raise RuntimeError(
                "GPU slot requested but venv libnvJitLink.so.12 not found. "
                "Run uv sync, or pass --max-gpu-slots=0 to disable GPU.")
        env["LD_PRELOAD"] = nvjl
        # Put the venv's nvidia/*/lib dirs on LD_LIBRARY_PATH so jax can dlopen cuSPARSE/
        # cuBLAS/cuDNN/… at runtime. Without this, GPU children fail "Unable to load cuSPARSE"
        # and fall back to CPU (diagnosed 2026-06-23; LD_PRELOAD of nvjitlink alone is
        # insufficient). Pure loader-path fix — no package/numpy change.
        _nvlib = _venv_nvidia_lib_dirs()
        if _nvlib:
            env["LD_LIBRARY_PATH"] = (
                _nvlib + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""))
        env["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
        env["XLA_PYTHON_CLIENT_ALLOCATOR"] = "platform"
        env.setdefault("HAFISCAL_USE_JAX_2B_THREADS", "2")
        env.setdefault("HAFISCAL_PARALLEL_SOLVE", "1")
    else:
        raise ValueError(f"unknown hw_slot {hw_slot!r}")
    return env


def felicity(c, CRRA):
    c = np.maximum(c, 1e-16)
    if abs(CRRA - 1.0) < 1e-12:
        return np.log(c)
    return c ** (1 - CRRA) / (1 - CRRA)


def calculate_NPV(series, periods, Rfree):
    """Mirrors tm_methods.calculate_NPV for the final index."""
    disc = Rfree ** np.arange(periods)
    cum = np.cumsum(np.array(series) / disc)
    return cum


def welfare6_mc(pol_r, none_r, base_r, periods, Rfree, CRRA,
                cost_pol_r=None, cost_none_r=None):
    """Paper-formula welfare6 (Welfare.py:277/284 convention).

    Numerator (felicity difference) uses pol_r, none_r, base_r for the
    cell's AD setting.  Denominator NPV_AddInc and the budget residual
    use cost_pol_r, cost_none_r — which should always be the AD=0
    scenarios for a given policy, so AD=0 and AD=1 cells share a fixed
    direct-fiscal-cost denominator.

    Defaults to the legacy cell-specific denominator (cost = pol/none)
    when cost_pol_r/cost_none_r are not supplied.

    BUG-046 fix (2026-05-16): The welfare integrand
    `(u(c_p) - u(c_n)) / u'(c_b)` is NONLINEAR in cLvl. Computing it on
    the recession-duration-probability-weighted `cLvl_all_splurge` panel
    is Jensen-biased by approximately −23% on ui_rec (empirically
    measured at HS_Only N=49000 bug_fix). The correct order is to
    compute the welfare integrand PER DURATION, then weight by rec_probs.
    Activated when `pol_r['per_dur_cLvl_all_splurge']` is present
    (= scenario pickle was generated by welfare6_scenario.py with the
    BUG-046 fix). Set HAFISCAL_WELFARE6_FIX_DUR_AVG=off to force
    legacy behavior for diagnostic comparison.
    """
    import os as _os
    if cost_pol_r is None:
        cost_pol_r = pol_r
    if cost_none_r is None:
        cost_none_r = none_r

    NPV_pol_Y = calculate_NPV(
        np.array(cost_pol_r["AggIncome"]), periods, Rfree)[-1]
    NPV_none_Y = calculate_NPV(
        np.array(cost_none_r["AggIncome"]), periods, Rfree)[-1]
    NPV_AddInc = NPV_pol_Y - NPV_none_Y

    NPV_pol_C = calculate_NPV(
        np.array(cost_pol_r["AggCons"]), periods, Rfree)[-1]
    NPV_none_C = calculate_NPV(
        np.array(cost_none_r["AggCons"]), periods, Rfree)[-1]
    NPV_AddCons = NPV_pol_C - NPV_none_C

    if abs(NPV_AddInc) < 1e-10:
        return float("nan")

    _fix_mode = _os.environ.get("HAFISCAL_WELFARE6_FIX_DUR_AVG", "on").lower()
    use_per_dur = (
        _fix_mode in ("on", "1", "true") and
        "per_dur_cLvl_all_splurge" in pol_r and
        "per_dur_cLvl_all_splurge" in none_r
    )

    if use_per_dur:
        # BUG-046 fix: compute welfare integrand per duration, weight by rec_probs.
        per_dur_pol = pol_r["per_dur_cLvl_all_splurge"]
        per_dur_none = none_r["per_dur_cLvl_all_splurge"]
        rec_probs = pol_r["rec_probs"]
        n_dur = len(per_dur_pol)
        # base: use per-dur if available, else broadcast the dur-averaged panel.
        if "per_dur_cLvl_all_splurge" in base_r:
            per_dur_base = base_r["per_dur_cLvl_all_splurge"]
        else:
            base_panel = base_r["cLvl_all_splurge"]
            per_dur_base = [base_panel] * n_dur

        sum_per_t = np.zeros(periods)
        for dur in range(n_dur):
            pol_w_d = felicity(per_dur_pol[dur], CRRA)
            none_w_d = felicity(per_dur_none[dur], CRRA)
            base_MU_d = np.maximum(per_dur_base[dur], 1e-16) ** (-CRRA)
            sum_per_t += rec_probs[dur] * np.sum(
                (pol_w_d - none_w_d) / base_MU_d, 1)
        w6 = (
            np.sum(sum_per_t / NPV_AddInc / Rfree ** np.arange(periods))
            + (NPV_AddInc - NPV_AddCons) / NPV_AddInc
        )
    else:
        # LEGACY (Jensen-biased): u(weighted-avg cLvl).
        pol_w = felicity(pol_r["cLvl_all_splurge"], CRRA)
        none_w = felicity(none_r["cLvl_all_splurge"], CRRA)
        base_MU = np.maximum(base_r["cLvl_all_splurge"], 1e-16) ** (-CRRA)
        w6 = (
            np.sum(
                np.sum((pol_w - none_w) / base_MU, 1)
                / NPV_AddInc
                / Rfree ** np.arange(periods)
            )
            + (NPV_AddInc - NPV_AddCons) / NPV_AddInc
        )
    return float(w6)


def mystr2dp(x):
    if np.isnan(x):
        return ""
    return "{:.2f}".format(x)


def _is_recession_scenario(scenario):
    return scenario.startswith("recession")


# Hard cap on duration-pool workers, RE-DERIVED 2026-07-30 after BUG-064.
#
# The old cap of 2 rested on a curve that turned out to be measuring something
# else: 178.9 s @dw=1, 182.6 @2, 181.6 @4, 308.5 @11 "perfect anti-scaling",
# attributed to fork-COW refcount dirtying and memory bandwidth. That sweep ran on
# a NON-AD scenario, where every fork child re-solved the whole economy (BUG-064),
# so it was reading wall ~ R(dw) + (n/dw)*t with R the per-child re-solve; the
# pool's own term was invisible under it, and dw=11 looked catastrophic only
# because it paid R eleven times.
#
# Re-measured on the fixed code (Baseline recessionCheck, quiet box, one
# build+solve then every width timed in-process, dw=2 bracketed first/last with
# 1.0% drift, AggCons hash identical at every width):
#
#     dw       1       2       4       8      16
#   wall  361.8s  212.6s  107.6s   59.6s   49.3s
#   speedup  1.00x   1.70x   3.36x   6.07x   7.33x
#   effic.    ---     85%     84%     76%     46%
#
# The pool SCALES. 8 is the knee: 6.07x at 76% efficiency, while 16 buys only
# 1.21x more for a 30-point efficiency drop. Peak python RSS across the whole
# sweep was 1.5 GB with 45+ GB free, so the "~16 GB per duration worker" memory
# ceiling is also gone -- that too was the re-solve, which forced each child to
# build its own solution set instead of sharing the parent's copy-on-write.
_MAX_DURATION_WORKERS = 8


def _auto_parallel_plan(cpu_count, max_parallel, scenarios,
                        n_agent_types=21, n_durations=20, slot_cap=None):
    """Budget inner parallelism based on cpu_count and effective outer concurrency.

    Returns a dict with per-scenario-type worker counts:
        {"cpu_count", "max_parallel", "effective_outer", "slot_cap", "budget",
         "norec": {"duration_workers": 1, "solve_workers": S},
         "rec":   {"duration_workers": D, "solve_workers": S}}

    Non-recession scenarios have no duration loop, so all inner budget goes to
    solve-workers.

    Recession scenarios give the FULL budget to BOTH pools, because the two are
    SEQUENTIAL PHASES, not competitors: ``run_recession`` does ``eco.solve()``
    and only then calls ``_prob_weighted_rec``, so the solve pool has finished
    its work before the first duration fork exists. Splitting the budget between
    them (the pre-2026-07-30 ``budget // rec_duration``) therefore starved both
    phases at once -- at 32 cores solo it ran the solve at sw=16 instead of 21
    and the duration loop at dw=2 instead of 8, leaving ~24 cores idle during
    the duration phase for no gain during the solve phase. The persistent solve
    pool does stay alive across the duration loop, but its workers are idle and
    hold ~1.5 GB in total (measured, post-BUG-064).

    ``slot_cap`` (= max_gpu_slots + max_cpu_slots) is the number of children
    that can actually be in flight at once. It must bound ``effective_outer``:
    ``max_parallel`` alone overstates concurrency whenever the hardware slots
    are tighter, and the budget is then divided by children that never co-run.
    Measured 2026-07-29: max_parallel=12 with the default gpu=1/cpu=2 slots gave
    32//12 = 2 cores per scenario while only 3 children ran, leaving 26 of 32
    cores idle for the whole battery.
    """
    caps = [max_parallel, len(scenarios)]
    if slot_cap:
        caps.append(slot_cap)
    effective_outer = max(1, min(caps))
    budget = max(1, cpu_count // effective_outer)

    norec_solve = min(n_agent_types, budget)

    rec_duration = min(_MAX_DURATION_WORKERS, n_durations, budget)
    rec_solve    = min(n_agent_types, budget)   # sequential phases: no split

    return {
        "cpu_count":       cpu_count,
        "max_parallel":    max_parallel,
        "effective_outer": effective_outer,
        "slot_cap":        slot_cap,
        "budget":          budget,
        "norec": {"duration_workers": 1,            "solve_workers": norec_solve},
        "rec":   {"duration_workers": rec_duration, "solve_workers": rec_solve},
    }


def _battery_exit_code(timings, missing, requested, resolve_ok=True):
    """Exit code for a battery run: 0 only if nothing went wrong.

    Fails (1) when any scenario child exited non-zero, when a scenario this run
    was ASKED to produce has no pickle, or when the resolve gate failed. A
    companion pickle that is merely out of scope does NOT fail the run — that is
    the documented "unspecified scenarios are read from existing pickles" mode —
    it only blocks the table.

    Separated out and tested because the inline version silently returned 0 twice
    in one night (all scenarios FAILED; then 5 of 12 killed by an outer timeout),
    and a caller read both as success.
    """
    failed = [s for s, (rc, _) in timings.items() if rc != 0]
    missing_requested = [s for s in missing if s in requested]
    return 0 if (resolve_ok and not failed and not missing_requested) else 1


def _format_parallel_plan(plan):
    return (
        f"Parallel plan:  cpu_count={plan['cpu_count']}  "
        f"max_parallel={plan['max_parallel']}  "
        f"slot_cap={plan['slot_cap']} (effective outer {plan['effective_outer']})\n"
        f"  → cpu_budget_per_scenario={plan['budget']}\n"
        f"  Non-recession: duration_workers={plan['norec']['duration_workers']}, "
        f"solve_workers={plan['norec']['solve_workers']}\n"
        f"  Recession:     duration_workers={plan['rec']['duration_workers']}, "
        f"solve_workers={plan['rec']['solve_workers']}"
    )


def launch_scenarios(parametrization, scenarios, max_parallel, out_dir,
                     log_dir, ad_tolerance=None, solve_workers=None,
                     duration_workers=None, agent_count_total=None,
                     seed_offset=0,
                     max_gpu_slots=None, max_cpu_slots=None, ad_cache=None):
    """Launch scenarios under slot-aware scheduling.

    ``max_gpu_slots`` / ``max_cpu_slots`` left as None are resolved by the
    machine probe (Code/HA-Models/machine_profile.py) so programmatic callers
    get hardware-tailored defaults too (legacy 1/2 only if the probe is
    unavailable).

    ``max_gpu_slots`` (probe default 0 — the GPU lane is dead at battery
    scale by measurement; 0 also spares GPU-less machines the CUDA env):
    max concurrent GPU children. AD scenarios (recession*_AD) are
    preferentially routed to GPU when >0. >1 risks GPU contention (per
    registry lesson L3 — 2 workers on the 16 GB RTX 4080 measured -16%
    wall vs 1 worker).

    ``max_cpu_slots`` (probe default clamp(min(cores//4, mem_gb//7), 1, 8),
    anchored to the certified 8-slot battery): max concurrent CPU
    children. The historical hardwired 2 encoded the retired JAX-2B
    ~17 GB/child era (lesson L3); the hybrid-engine envelope is ~7 GB.

    ``max_parallel`` (legacy): overall cap; if smaller than
    gpu+cpu sum, becomes the binding limit. Set to 0 to use only
    gpu+cpu slot budgets.

    Returns dict scenario -> (rc, wall_clock_s).
    """
    python = sys.executable
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    timings = {}
    if max_gpu_slots is None or max_cpu_slots is None:
        try:
            _ha_mp = os.path.abspath(os.path.join(HERE, ".."))
            if _ha_mp not in sys.path:
                sys.path.insert(0, _ha_mp)
            from machine_profile import plan_welfare6_slots as _mp_plan
            _plan = _mp_plan()
            if max_gpu_slots is None:
                max_gpu_slots = _plan["max_gpu_slots"]
            if max_cpu_slots is None:
                max_cpu_slots = _plan["max_cpu_slots"]
        except Exception:  # pragma: no cover - legacy fallback
            # gpu=0 (not the pre-graduation 1): the GPU lane is explicit
            # opt-in only, and arming it on a probe failure would crash
            # GPU-less machines in _build_child_env (no venv nvjitlink).
            if max_gpu_slots is None:
                max_gpu_slots = 0
            if max_cpu_slots is None:
                max_cpu_slots = 2

    in_flight = {}  # scenario -> (proc, log_fh, t_started, hw_slot)
    gpu_in_flight = 0

    effective_outer_cap = max_parallel if max_parallel > 0 else (
        max_gpu_slots + max_cpu_slots)
    try:
        _ha_mp2 = os.path.abspath(os.path.join(HERE, ".."))
        if _ha_mp2 not in sys.path:
            sys.path.insert(0, _ha_mp2)
        from machine_profile import plan_welfare6_slots as _mp_plan2
        _budget_cores = _mp_plan2()["usable_cores"]   # cores minus system reserve
    except Exception:  # pragma: no cover - legacy fallback
        try:  # still allocation-aware even without machine_profile
            _budget_cores = len(os.sched_getaffinity(0)) or 1
        except (AttributeError, OSError):
            _budget_cores = os.cpu_count() or 1
    plan = _auto_parallel_plan(_budget_cores,
                               effective_outer_cap, scenarios,
                               slot_cap=max_gpu_slots + max_cpu_slots)
    print(_format_parallel_plan(plan))
    print(f"Slots: max_gpu_slots={max_gpu_slots}  max_cpu_slots={max_cpu_slots}  "
          f"effective_outer_cap={effective_outer_cap}")
    print()

    def _launch(scenario, hw_slot):
        slot = "rec" if _is_recession_scenario(scenario) else "norec"
        dw = duration_workers if duration_workers is not None else plan[slot]["duration_workers"]
        sw = solve_workers    if solve_workers    is not None else plan[slot]["solve_workers"]

        # GPU children: keep host-side workers minimal (GPU is the
        # bottleneck; lots of host workers just add scheduling overhead).
        if hw_slot == "gpu":
            sw = min(sw, 4)
            dw = min(dw, 4)

        log_path = os.path.join(log_dir, f"{scenario}.log")
        log_fh = open(log_path, "w")
        cmd = [
            python, SCENARIO_SCRIPT,
            "--scenario", scenario,
            "--parametrization", parametrization,
            "--out-dir", out_dir,
        ]
        if ad_tolerance is not None:
            cmd += ["--ad-tolerance", str(ad_tolerance)]
        if sw and sw > 1:
            cmd += ["--solve-workers", str(sw)]
        if dw and dw > 1:
            cmd += ["--duration-workers", str(dw)]
        if agent_count_total is not None:
            cmd += ["--agent-count-total", str(agent_count_total)]
        if seed_offset:
            cmd += ["--seed-offset", str(seed_offset)]
        child_env = _build_child_env(hw_slot, ad_cache=ad_cache)
        log_fh.write(
            f"[option-d] hw_slot={hw_slot}  JAX_PLATFORMS={child_env.get('JAX_PLATFORMS')}  "
            f"PARALLEL_SOLVE={child_env.get('HAFISCAL_PARALLEL_SOLVE')}  "
            f"JAX_2B_THREADS={child_env.get('HAFISCAL_USE_JAX_2B_THREADS')}\n"
        )
        log_fh.flush()
        proc = subprocess.Popen(cmd, cwd=HERE, stdout=log_fh,
                                stderr=subprocess.STDOUT,
                                env=child_env,
                                start_new_session=True)
        in_flight[scenario] = (proc, log_fh, time(), hw_slot)
        print(f"  → launched {scenario} on {hw_slot} (pid {proc.pid})  "
              f"[dw={dw},sw={sw}]  log: {log_path}")

    # Two queues: AD scenarios preferentially go to GPU; non-AD to CPU.
    ad_queue = [s for s in scenarios if s in _AD_SCENARIOS]
    non_ad_queue = [s for s in scenarios if s not in _AD_SCENARIOS]

    # Lever #1 (HAFISCAL_AD_INIT_CACHE): an AD scenario's init reuses its no-AD
    # twin's recession solve (bit-identical, ~89% of the AD-loop wall). Under
    # concurrency the AD child would start before the twin saved the cache and
    # both would solve. So GATE each AD scenario on its twin finishing first —
    # but ONLY when the recession-init cache is actually active AND the twin is
    # in this run (else the AD scenario would wait forever). When off, the gate
    # is empty and scheduling is byte-unchanged.
    _AD_TWIN = {
        "recession_AD": "recession",
        "recessionUI_AD": "recessionUI",
        "recessionCheck_AD": "recessionCheck",
        "recessionTaxCut_AD": "recessionTaxCut",
    }
    _init_cache_on = (
        os.environ.get("HAFISCAL_AD_INIT_CACHE", "0").lower()
        in ("1", "on", "true")
        and ad_cache is not False)  # --no-ad-cache disables it in children
    def _init_cache_warm(shock):
        """True when a recession-init cache entry for this shock is already on
        disk: the AD child will HIT without waiting for its twin, so gating
        would serialize the schedule for nothing (measured at Baseline:
        gated-cold ~61.5 min vs ungated-warm ~47 min). A stale entry that the
        child MISSes on merely degrades to the ungated-cold (R4b) behaviour —
        twin and AD solve concurrently — never a wrong result."""
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "solution_cache", parametrization, shock)
        try:
            return any(("__mc-hark_solve_only__" in f and f.endswith(".pkl"))
                       for f in os.listdir(d))
        except OSError:
            return False

    _gated_twins = ({ad: tw for ad, tw in _AD_TWIN.items()
                     if ad in scenarios and tw in scenarios
                     and not _init_cache_warm(tw)}
                    if _init_cache_on else {})
    if _gated_twins:
        print(f"  [ad-init-cache] gating AD scenarios on their no-AD twins so "
              f"the recession solve is shared: {sorted(_gated_twins)}")

    def _ad_eligible(s):
        """An AD scenario is launchable now unless it is gated on a twin that
        has not finished yet."""
        tw = _gated_twins.get(s)
        return tw is None or tw in timings

    def _pop_eligible_ad():
        for idx, s in enumerate(ad_queue):
            if _ad_eligible(s):
                return ad_queue.pop(idx)
        return None

    def _try_launch_one():
        """Try to fill an open slot. Returns True if launched, False if
        all slots full or no launchable scenario is available."""
        nonlocal gpu_in_flight
        cpu_in_flight = len(in_flight) - gpu_in_flight
        room_total = (effective_outer_cap - len(in_flight)) > 0
        if not room_total:
            return False
        # Prefer GPU slot for an ELIGIBLE AD scenario
        if gpu_in_flight < max_gpu_slots and max_gpu_slots > 0:
            s = _pop_eligible_ad()
            if s is not None:
                _launch(s, "gpu")
                gpu_in_flight += 1
                return True
        # CPU slot: LONGEST JOB FIRST, i.e. prefer an eligible AD scenario.
        #
        # This inverted on 2026-07-30. The old rule preferred non-AD here, which
        # was right while the non-AD recession scenarios took ~55 min each
        # (BUG-064: every duration child re-solved the economy) and so were
        # comparable in length to the AD ones. With that fixed they collapse to
        # ~12 min while the AD scenarios still cost 33-144 min, so filling the
        # slots with short jobs first strands the long ones at the back of the
        # queue: MEASURED in the 2026-07-29 battery, recessionCheck_AD waited
        # 81.9 min and recessionTaxCut_AD 117.4 min for a slot, and the last
        # 20.6 min of the battery was one AD scenario that could not start
        # earlier. Longest-processing-time-first is the standard makespan
        # heuristic (within 4/3 of optimal) and here it is close to exact,
        # because the four AD jobs alone are longer than everything else
        # combined -- the ideal schedule is simply "start them immediately".
        #
        # The AD_INIT_CACHE gate still wins where it applies: _pop_eligible_ad
        # returns None while an AD scenario is waiting on its twin, so this
        # falls through to the non-AD queue and the twin runs first, exactly as
        # before. The two policies compose without a special case.
        if cpu_in_flight < max_cpu_slots:
            s = _pop_eligible_ad()
            if s is not None:
                _launch(s, "cpu")
                return True
            if non_ad_queue:
                _launch(non_ad_queue.pop(0), "cpu")
                return True
        return False

    # Pre-launch up to the effective cap.
    while _try_launch_one():
        pass

    while in_flight:
        progress = False
        for scenario in list(in_flight.keys()):
            proc, log_fh, t_started, hw_slot = in_flight[scenario]
            rc = proc.poll()
            if rc is not None:
                log_fh.close()
                wall = time() - t_started
                timings[scenario] = (rc, wall)
                status = "OK" if rc == 0 else f"FAIL rc={rc}"
                print(f"  ← {scenario} [{hw_slot}]: {status} ({wall:.0f}s)")
                del in_flight[scenario]
                if hw_slot == "gpu":
                    gpu_in_flight -= 1
                # Try to launch next in any open slot
                while _try_launch_one():
                    pass
                progress = True
        if not progress:
            import time as _t
            _t.sleep(2)

    return timings


def compute_welfare6_table(out_dir):
    """Load the 12 pickles, compute the welfare6 table."""
    loaded = {}
    for s in ALL_SCENARIOS:
        path = os.path.join(out_dir, f"{s}.pkl")
        with open(path, "rb") as f:
            loaded[s] = pickle.load(f)

    act_T = loaded["base"]["act_T"]
    Rfree = loaded["base"]["Rfree"]
    CRRA = loaded["base"]["CRRA"]
    periods = act_T
    base = loaded["base"]

    def w6(pol_key, none_key, cost_pol_key=None, cost_none_key=None):
        cp = loaded[cost_pol_key]  if cost_pol_key  else None
        cn = loaded[cost_none_key] if cost_none_key else None
        return welfare6_mc(
            loaded[pol_key], loaded[none_key], base,
            periods, Rfree, CRRA,
            cost_pol_r=cp, cost_none_r=cn,
        )

    # AD=1 cells use the corresponding AD=0 pair as the fixed NPV_AddInc
    # denominator (paper formula; Welfare.py:277/284).
    results = {
        # (Rec=0, AD=0)
        "check_norec": w6("Check", "base"),
        "ui_norec":    w6("UI",    "base"),
        "taxcut_norec": w6("TaxCut", "base"),
        # (Rec=1, AD=0)
        "check_rec": w6("recessionCheck", "recession"),
        "ui_rec":    w6("recessionUI",    "recession"),
        "taxcut_rec": w6("recessionTaxCut", "recession"),
        # (Rec=1, AD=1) — denominator held fixed at the AD=0 pair
        "check_rec_AD":  w6("recessionCheck_AD",  "recession_AD",
                            "recessionCheck",   "recession"),
        "ui_rec_AD":     w6("recessionUI_AD",     "recession_AD",
                            "recessionUI",      "recession"),
        "taxcut_rec_AD": w6("recessionTaxCut_AD", "recession_AD",
                            "recessionTaxCut",  "recession"),
    }
    return results, loaded


def write_welfare6_tex(results, path):
    # Candidate-routing (QE-baseline freeze): writes `<path>_candidate` sibling
    # unless HAFISCAL_PROMOTE=1. See generated_output.py.
    from generated_output import open_generated
    with open_generated(path) as f:
        f.write("\\begin{tabular}{@{}lccc@{}} \n")
        f.write("\\toprule \n")
        f.write("                          & Stimulus check      & UI extension    & Tax cut    \\\\  \\midrule \n")
        f.write(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=0, AD=0)$ & {mystr2dp(results['check_norec'])}  & {mystr2dp(results['ui_norec'])}  & {mystr2dp(results['taxcut_norec'])}     \\\\ \n")
        f.write(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=1, AD=0)$ & {mystr2dp(results['check_rec'])}  & {mystr2dp(results['ui_rec'])}  & {mystr2dp(results['taxcut_rec'])}     \\\\ \n")
        f.write(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=1, AD=1)$ & {mystr2dp(results['check_rec_AD'])}  & {mystr2dp(results['ui_rec_AD'])}  & {mystr2dp(results['taxcut_rec_AD'])}     \\\\ \\bottomrule \n")
        f.write("\\end{tabular}  \n")


def _maybe_emit_verify_drift(parametrization, out_dir, log_dir, args):
    """Thread-2 component 2: under VERIFY level >= complete, run the cheap 'base'
    (no-recession) cell at a few extra seed-offsets and report the multi-seed
    cross-section drift + SE (the standing rule: never report an MC drift without a
    multi-seed SE).

    Reuses launch_scenarios so each companion base cell is built byte-for-byte the way the
    main run built its base cell (identical calibration / scale / flags), differing ONLY in
    the RNG seed; the main run's out_dir (seed = args.seed_offset) is reused as the first
    sample. Best-effort: this runs AFTER the welfare result is computed and saved, so any
    failure here degrades with abundant diagnostics and never aborts the run.

    Owner: Code/HA-Models/verify_drift.py (the VERIFY axis); the 4-moment SE math is in
    Code/HA-Models/welfare_drift_report.py. The VERIFY level is set by reproduce.sh
    --complete / --byte-identical (HAFISCAL_VERIFY_LEVEL).
    """
    # Code/HA-Models holds verify_level / verify_drift / welfare_drift_report.
    _ha = os.path.abspath(os.path.join(HERE, ".."))
    if _ha not in sys.path:
        sys.path.insert(0, _ha)
    # Gate on the CHEAP reader first (os/sys only) so the default 'numeric' path imports
    # nothing heavier and does zero extra work.
    try:
        import verify_level
    except Exception as e:
        print(f"[verify_drift] verify_level import failed; skipping drift companion: {e}")
        return
    if not verify_level.verify_at_least(verify_level.COMPLETE):
        return  # VERIFY level 'numeric' (default): zero extra cost, no further imports
    try:
        import verify_drift
        n = verify_drift.n_seeds()
        base_seed = args.seed_offset or 0
        comp_root = out_dir.rstrip("/") + "_verify_drift"
        comp_log = os.path.join(log_dir, "_verify_drift")
        print(f"\n[verify_drift] VERIFY level >= complete: running the 'base' cell at "
              f"{n - 1} extra seed-offset(s) (seeds {base_seed + 1}..{base_seed + n - 1}) "
              f"for a multi-seed SE; base seed {base_seed} reuses the main run. This is the "
              f"compute --complete buys (HAFISCAL_VERIFY_DRIFT_SEEDS={n}).")
        dirs = [out_dir]
        for k in range(1, n):
            seed = base_seed + k
            seed_dir = os.path.join(comp_root, f"seed_{seed}")
            launch_scenarios(
                parametrization, ("base",), args.max_parallel, seed_dir, comp_log,
                ad_tolerance=args.ad_tolerance, solve_workers=args.solve_workers,
                duration_workers=args.duration_workers,
                agent_count_total=args.agent_count_total, seed_offset=seed,
                max_gpu_slots=args.max_gpu_slots, max_cpu_slots=args.max_cpu_slots,
                ad_cache=args.ad_cache)
            dirs.append(seed_dir)
        verify_drift.report_multiseed(dirs, label=f"{parametrization} base cell")
    except Exception as e:
        import traceback
        print(f"[verify_drift] WARNING: the drift companion FAILED — the welfare result "
              f"STANDS (additive verification step). {type(e).__name__}: {e}")
        traceback.print_exc()


def _maybe_verify_resolve(parametrization, out_dir, log_dir, args):
    """Thread-2 component 3 (VERIFY axis): under VERIFY level >= complete, re-solve the
    in-scope scenarios FROM SCRATCH (cache OFF, at the SAME seed_offset as production) and
    compare to the production result within Tier-I. A genuine MISMATCH FAILS LOUD (the
    reused/cached solution is suspect); a verify-MACHINERY error degrades with abundant
    diagnostics. Returns True if OK or skipped (numeric / scope=none), False on a real
    mismatch (main() turns that into a non-zero exit).

    SAME seed (unlike the drift companion's varied seeds): fresh-vs-production then differs
    ONLY by whether the cache/belief-seed was reused, isolating the reuse. The re-launch
    reuses launch_scenarios(ad_cache=False) — the existing --no-ad-cache fresh-solve path.
    Owner: Code/HA-Models/verify_resolve.py (scope / tolerance / comparison).
    """
    _ha = os.path.abspath(os.path.join(HERE, ".."))
    if _ha not in sys.path:
        sys.path.insert(0, _ha)
    try:
        import verify_level
    except Exception as e:
        print(f"[verify_resolve] verify_level import failed; skipping re-solve-compare: {e}")
        return True
    if not verify_level.verify_at_least(verify_level.COMPLETE):
        return True  # VERIFY level 'numeric' (default): zero extra cost
    try:
        import verify_resolve
    except Exception as e:
        print(f"[verify_resolve] import failed; DEGRADING (welfare result stands): {e}")
        return True
    scenarios = verify_resolve.scope(ALL_SCENARIOS)
    if not scenarios:
        print("[verify_resolve] HAFISCAL_VERIFY_RESOLVE_SCOPE=none — skipping "
              "re-solve-and-compare.")
        return True
    rtol, label = verify_resolve.tolerance()
    try:
        fresh_dir = out_dir.rstrip("/") + "_verify_resolve"
        fresh_log = os.path.join(log_dir, "_verify_resolve")
        print(f"\n[verify_resolve] VERIFY level >= complete: re-solving {len(scenarios)} of "
              f"{len(ALL_SCENARIOS)} scenario(s) cache-OFF (same seed {args.seed_offset}) to "
              f"compare against the production result within {label}. This is the compute "
              f"--complete buys (HAFISCAL_VERIFY_RESOLVE_SCOPE).")
        launch_scenarios(
            parametrization, tuple(scenarios), args.max_parallel, fresh_dir, fresh_log,
            ad_tolerance=args.ad_tolerance, solve_workers=args.solve_workers,
            duration_workers=args.duration_workers,
            agent_count_total=args.agent_count_total, seed_offset=args.seed_offset,
            max_gpu_slots=args.max_gpu_slots, max_cpu_slots=args.max_cpu_slots,
            ad_cache=False)  # cache OFF -> a fresh from-scratch solve (the ground truth)
        ok, mismatches, missing, details = verify_resolve.run_compare(
            out_dir, fresh_dir, scenarios, rtol)
        verify_resolve.report(ok, mismatches, missing, details, rtol, label)
        return ok
    except Exception as e:  # MACHINERY error (a re-run crash) -> degrade, do not fail
        import traceback
        print(f"[verify_resolve] WARNING: the re-solve-and-compare MACHINERY failed — "
              f"DEGRADING (welfare result STANDS but was NOT verified). "
              f"{type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parametrization", default="Reduced_Run",
                   help="Parametrization name passed to "
                        "welfare6_scenario.py (Baseline, Reduced_Run, "
                        "HS_Only, or any sensitivity name known to "
                        "Parameters.py: CRRA1, CRRA3, ADElas, Rfree_1005, "
                        "Rfree_1015, Rspell_4, LowerUBnoB, Splurge0, "
                        "and *_PVSame variants).")
    p.add_argument("--baseline", action="store_true",
                   help="Alias for --parametrization Baseline.")
    p.add_argument("--max-parallel", type=int, default=12,
                   help="Max concurrent subprocesses (default: 12, one per "
                        "scenario). Lower this if memory is tight.")
    p.add_argument("--scenarios", default=None,
                   help="Comma-separated subset to run (default: all 12). "
                        "Unspecified scenarios are read from existing pickles.")
    p.add_argument("--ad-tolerance", type=float, default=None,
                   help="Override convergence_tol_solvingAD. Forwarded "
                        "to every AD scenario subprocess.")
    p.add_argument("--solve-workers", type=int, default=None,
                   help="Forwarded to each scenario subprocess. Default: "
                        "auto (budgeted via _auto_parallel_plan based on "
                        "cpu_count() and effective outer concurrency). Pass "
                        "an explicit integer to override.")
    p.add_argument("--duration-workers", type=int, default=None,
                   help="Forwarded to each scenario subprocess. Default: "
                        "auto (see --solve-workers). Only applies to "
                        "recession and recession_AD scenarios.")
    p.add_argument("--agent-count-total", type=int, default=None,
                   help="Forwarded to each scenario subprocess. Overrides "
                        "Parameters.py's AgentCountTotal.")
    p.add_argument("--seed-offset", type=int, default=0,
                   help="Forwarded to each scenario subprocess. Non-zero "
                        "values produce independent multi-seed batches "
                        "for variance reduction via panel concatenation. "
                        "Use a different --out-dir per seed_offset.")
    p.add_argument("--out-dir", default=None,
                   help="Directory for per-scenario pickles.")
    p.add_argument("--table-dir", default=None,
                   help="Directory for welfare6.tex (default: "
                        "Tables/{param}_parallel/).")
    p.add_argument("--max-gpu-slots", type=int, default=None,
                   help="Max concurrent GPU children (default: resolved by "
                        "the machine probe -> 0; the GPU lane is dead at "
                        "battery scale by measurement, and 0 also keeps "
                        "GPU-less machines from failing on the CUDA env). "
                        "AD scenarios route here preferentially when >0. "
                        ">1 risks GPU contention (registry lesson L3).")
    p.add_argument("--max-cpu-slots", type=int, default=None,
                   help="Max concurrent CPU children (default: resolved by "
                        "the machine probe: clamp(min(cores//4, mem_gb//7), "
                        "1, 8) -- anchored to the certified 8-slot/32-core/"
                        "60GB hybrid battery; the old hardwired 2 was the "
                        "retired JAX-2B ~17GB/child era). "
                        "HAFISCAL_MAX_{CPU,GPU}_SLOTS env vars also "
                        "override; explicit flag wins over both.")
    p.add_argument("--skip-ui", action="store_true",
                   help="Drop UI / recessionUI / recessionUI_AD from this "
                        "run. NOTE: only ui_norec is excluded from "
                        "reporting by the [NEVER report ui_norec] rule; "
                        "ui_rec / ui_rec_AD ARE reportable (2026-06-10 "
                        "unified-MC decision), so skipping them is a "
                        "speed/scope choice, not a rule. Welfare-6 table "
                        "will have NaN cells for UI; the aggregator "
                        "handles missing pickles gracefully.")
    # Leg A1: operator control over the AD-converged solution cache
    # (HAFISCAL_USE_SOLUTION_CACHE, solution_cache/ad_cache.py). Default
    # (neither flag) preserves the existing setdefault-ON behavior in
    # _build_child_env; --ad-cache forces ON, --no-ad-cache forces OFF
    # (e.g. to defeat an inherited "1" for a from-scratch parity run).
    cache_grp = p.add_mutually_exclusive_group()
    cache_grp.add_argument(
        "--ad-cache", dest="ad_cache", action="store_true", default=None,
        help="Force the AD-converged solution cache ON for every child "
             "(HAFISCAL_USE_SOLUTION_CACHE=1). Default-ON already; this "
             "makes it explicit and overrides an inherited '0'.")
    cache_grp.add_argument(
        "--no-ad-cache", dest="ad_cache", action="store_false", default=None,
        help="Force the AD-converged solution cache OFF for every child "
             "(HAFISCAL_USE_SOLUTION_CACHE=0), overriding the default-ON "
             "and any inherited '1'. Use for a from-scratch (no-HIT) run.")
    args = p.parse_args()

    # Resolve slot counts left unset on the CLI via the machine probe
    # (Code/HA-Models/machine_profile.py): the same code then runs
    # efficiently on a 16-core laptop and a 32-thread workstation without
    # edits. Precedence: explicit CLI flag > HAFISCAL_MAX_*_SLOTS env >
    # probe. Guarded import with the old hardwired values as last resort.
    if args.max_gpu_slots is None or args.max_cpu_slots is None:
        try:
            _ha_mp = os.path.abspath(os.path.join(HERE, ".."))
            if _ha_mp not in sys.path:
                sys.path.insert(0, _ha_mp)
            from machine_profile import describe as _mp_describe
            from machine_profile import plan_welfare6_slots as _mp_plan
            _plan = _mp_plan()
            print(_mp_describe(_plan))
            try:
                from solution_cache import record_reuse_event as _rre_mp
                _prof = _plan.get("profile", {})
                _rre_mp("platform", "plan", "none",
                        cpu_slots=_plan.get("max_cpu_slots"),
                        gpu_slots=_plan.get("max_gpu_slots"),
                        reserve_cores=_plan.get("reserve_cores"),
                        usable_cores=_plan.get("usable_cores"),
                        effective_cores=_prof.get("effective_cores"),
                        cores_source=_prof.get("cores_source"),
                        scheduler=(_prof.get("scheduler") or {}).get("kind")
                        if isinstance(_prof.get("scheduler"), dict) else None)
            except Exception:
                pass
            if args.max_gpu_slots is None:
                args.max_gpu_slots = _plan["max_gpu_slots"]
            if args.max_cpu_slots is None:
                args.max_cpu_slots = _plan["max_cpu_slots"]
        except Exception as _mp_e:  # pragma: no cover - never abort a run
            print(f"[machine-profile] unavailable ({_mp_e}); falling back "
                  "to legacy slot defaults gpu=0, cpu=2", flush=True)
            # gpu=0: arming the GPU lane on probe failure would crash
            # GPU-less machines in _build_child_env (no venv nvjitlink).
            if args.max_gpu_slots is None:
                args.max_gpu_slots = 0
            if args.max_cpu_slots is None:
                args.max_cpu_slots = 2

    parametrization = "Baseline" if args.baseline else args.parametrization
    out_dir = args.out_dir or os.path.join(
        HERE, f"welfare6_scenario_results_{parametrization}")
    table_dir = args.table_dir or os.path.join(
        HERE, "Tables", f"{parametrization}_parallel")
    log_dir = os.path.join(HERE, "welfare6_parallel_logs", parametrization)
    os.makedirs(table_dir, exist_ok=True)

    scenarios = (
        ALL_SCENARIOS if args.scenarios is None
        else tuple(s.strip() for s in args.scenarios.split(",") if s.strip())
    )
    for s in scenarios:
        if s not in ALL_SCENARIOS:
            print(f"unknown scenario {s!r}; valid: {ALL_SCENARIOS}")
            return 1
    if args.skip_ui:
        scenarios = tuple(s for s in scenarios if s not in _UI_SCENARIOS)
        print(f"[--skip-ui] dropped UI scenarios; remaining {len(scenarios)} of 12.")

    print(f"Parametrization : {parametrization}")
    print(f"Scenarios       : {list(scenarios)}")
    print(f"Max parallel    : {args.max_parallel}  "
          f"(slots: gpu={args.max_gpu_slots}, cpu={args.max_cpu_slots})")
    _adc = ("default (setdefault ON)" if args.ad_cache is None
            else ("forced ON" if args.ad_cache else "forced OFF"))
    print(f"AD solution cache: {_adc}  (HAFISCAL_USE_SOLUTION_CACHE)")
    print(f"Pickle dir      : {out_dir}")
    print(f"Log dir         : {log_dir}")
    print(f"Table dir       : {table_dir}")
    print()

    t0 = time()
    timings = launch_scenarios(parametrization, scenarios,
                               args.max_parallel, out_dir, log_dir,
                               ad_tolerance=args.ad_tolerance,
                               solve_workers=args.solve_workers,
                               duration_workers=args.duration_workers,
                               agent_count_total=args.agent_count_total,
                               seed_offset=args.seed_offset,
                               max_gpu_slots=args.max_gpu_slots,
                               max_cpu_slots=args.max_cpu_slots,
                               ad_cache=args.ad_cache)
    wall = time() - t0
    total_cpu = sum(w for (_, w) in timings.values())
    longest = max((w for (_, w) in timings.values()), default=0.0)
    print()
    print(f"Wall clock : {wall:.0f}s ({wall/60:.1f} min)")
    print(f"CPU-sum    : {total_cpu:.0f}s ({total_cpu/60:.1f} min)")
    print(f"Longest    : {longest:.0f}s ({longest/60:.1f} min)")
    if longest > 0:
        print(f"Speedup vs serial lower bound: {total_cpu/wall:.2f}x")

    # A scenario child that died must reach the exit code. Until 2026-07-29 the
    # rc's collected in `timings` were recorded and never inspected, so this
    # wrapper returned 0 with every scenario FAILED, and again with 5 of 12
    # killed mid-queue by an outer timeout — both times a caller read the 0 as
    # success. Report them loudly here and fail at the end.
    failed = {s: rc for s, (rc, _) in timings.items() if rc != 0}
    if failed:
        print("\nFAILED scenarios (rc != 0):")
        for s, rc in sorted(failed.items()):
            print(f"  {s}: rc={rc}   log: {os.path.join(log_dir, s + '.log')}")

    # Check all scenarios have pickles. Distinguish the two cases: a scenario
    # this run was ASKED to produce and didn't is a failure; a companion that was
    # simply not in scope is the documented "read from existing pickles" mode and
    # only blocks the table.
    missing = [s for s in ALL_SCENARIOS
               if not os.path.exists(os.path.join(out_dir, f"{s}.pkl"))]
    if missing:
        missing_requested = [s for s in missing if s in scenarios]
        print(f"\nMissing pickles: {missing}")
        if missing_requested:
            print(f"Requested but not produced: {missing_requested}")
        else:
            print("Run with --scenarios covering these to complete the welfare6 table.")
        return _battery_exit_code(timings, missing, scenarios)

    results, _ = compute_welfare6_table(out_dir)
    tex_path = os.path.join(table_dir, "welfare6.tex")
    write_welfare6_tex(results, tex_path)

    print(f"\nwelfare6 table: {tex_path}")
    print(f"{'':>35} {'Check':>8} {'UI':>8} {'TaxCut':>8}")
    print(f"{'Rec=0, AD=0':>35} {results['check_norec']:8.2f} "
          f"{results['ui_norec']:8.2f} {results['taxcut_norec']:8.2f}")
    print(f"{'Rec=1, AD=0':>35} {results['check_rec']:8.2f} "
          f"{results['ui_rec']:8.2f} {results['taxcut_rec']:8.2f}")
    print(f"{'Rec=1, AD=1':>35} {results['check_rec_AD']:8.2f} "
          f"{results['ui_rec_AD']:8.2f} {results['taxcut_rec_AD']:8.2f}")

    # Also save JSON for programmatic reference
    with open(os.path.join(table_dir, "welfare6_parallel_summary.json"), "w") as f:
        json.dump({
            "parametrization": parametrization,
            "wall_clock_s": wall,
            "cpu_sum_s":   total_cpu,
            "longest_s":   longest,
            "per_scenario": {s: dict(rc=rc, wall_s=w)
                             for s, (rc, w) in timings.items()},
            "welfare6": results,
        }, f, indent=2)

    # Schema v2: fold the sidecar-suppressed children's reuse ledgers into
    # this aggregate sidecar (each event tagged source_child) before emitting.
    try:
        _ha_ing = os.path.abspath(os.path.join(HERE, ".."))
        if _ha_ing not in sys.path:
            sys.path.insert(0, _ha_ing)
        import provenance as _prov_ing
        _n_frag = _prov_ing.ingest_reuse_fragments([out_dir])
        if _n_frag:
            print(f"[provenance] ingested {_n_frag} child reuse fragment(s)",
                  flush=True)
    except Exception:
        pass
    _emit_provenance_sidecar(
        [table_dir],
        label=f"welfare6_parallel-{parametrization}",
        output_roots=[os.path.join(table_dir, "welfare6.tex"),
                      os.path.join(table_dir, "welfare6_parallel_summary.json")],
    )

    # Thread-2 component 2 (VERIFY axis): under --complete, append the multi-seed drift+SE
    # headline. No-op at the default VERIFY level 'numeric'; best-effort otherwise (the
    # welfare result above is already computed and saved).
    _maybe_emit_verify_drift(parametrization, out_dir, log_dir, args)

    # Thread-2 component 3 (VERIFY axis): under --complete, re-solve the in-scope scenarios
    # cache-OFF and compare to the production result (the reuse gate). No-op at 'numeric'.
    # A genuine mismatch fails the run (non-zero exit) — the reused result is suspect; a
    # verify-machinery error degrades (returns True). The welfare result is already saved.
    _resolve_ok = _maybe_verify_resolve(parametrization, out_dir, log_dir, args)
    # A child may have died even though the table built — from stale pickles left
    # by an earlier run — which is exactly why a zero here would be dangerous.
    return _battery_exit_code(timings, missing, scenarios, _resolve_ok)


if __name__ == "__main__":
    sys.exit(main())
