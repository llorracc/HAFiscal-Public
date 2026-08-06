"""Guard tests for the machine probe + welfare-6 slot planning."""

from machine_profile import plan_welfare6_slots, probe_machine


def _prof(cores, mem, gpus=()):
    return {"logical_cores": cores, "mem_gb": mem, "gpus": list(gpus),
            "hostname": "test"}


def test_certification_box_with_reserve():
    # 32 cores / 60 GB: default reserve 2 -> 30 usable -> 7 slots
    # (owner directives 2026-08-02: reserve exactly 2 by default; the
    # 53-54 min certified wall was measured pre-reserve at 8 slots —
    # next battery re-anchors the wall).
    p = plan_welfare6_slots(_prof(32, 60), env={})
    assert (p["max_cpu_slots"], p["max_gpu_slots"]) == (7, 0)
    assert (p["reserve_cores"], p["usable_cores"]) == (2, 30)


def test_sixteen_core_machine_scales_down():
    # the motivating example: 16 cores must NOT get the 32-core plan
    p = plan_welfare6_slots(_prof(16, 64), env={})
    assert (p["reserve_cores"], p["usable_cores"], p["max_cpu_slots"]) == (2, 14, 3)


def test_memory_binds_before_cores():
    assert plan_welfare6_slots(_prof(16, 20), env={})["max_cpu_slots"] == 2


def test_small_machine_floor():
    p = plan_welfare6_slots(_prof(2, 4), env={})
    assert p["max_cpu_slots"] == 1 and p["usable_cores"] >= 1


def test_big_machine_capped_at_packing_bound():
    p = plan_welfare6_slots(_prof(128, 512), env={})
    assert p["max_cpu_slots"] == 8 and p["reserve_cores"] == 2


def test_gpu_defaults_zero_even_when_present():
    p = plan_welfare6_slots(_prof(32, 60, [{"name": "RTX 4080", "vram_gb": 16}]),
                            env={})
    assert p["max_gpu_slots"] == 0


def test_env_overrides_win():
    env = {"HAFISCAL_MAX_CPU_SLOTS": "3", "HAFISCAL_MAX_GPU_SLOTS": "1"}
    p = plan_welfare6_slots(_prof(32, 60), env=env)
    assert (p["max_cpu_slots"], p["max_gpu_slots"]) == (3, 1)


def test_reserve_env_override():
    # explicit zero reserve restores the pre-reserve 8-slot plan on the 32-core box
    p = plan_welfare6_slots(_prof(32, 60), env={"HAFISCAL_CPU_RESERVE_CORES": "0"})
    assert (p["reserve_cores"], p["usable_cores"], p["max_cpu_slots"]) == (0, 32, 8)


def test_bad_env_ignored_and_floor_enforced():
    p = plan_welfare6_slots(_prof(32, 60), env={"HAFISCAL_MAX_CPU_SLOTS": "zero"})
    assert p["max_cpu_slots"] == 7
    p2 = plan_welfare6_slots(_prof(32, 60), env={"HAFISCAL_MAX_CPU_SLOTS": "0"})
    assert p2["max_cpu_slots"] == 1  # floor: at least one CPU child


def test_probe_never_raises():
    prof = probe_machine()
    assert prof["logical_cores"] >= 1 and prof["mem_gb"] > 0
    assert isinstance(prof["gpus"], list)
    # v2 keys present and coherent on a live probe
    assert prof["effective_cores"] >= 1
    assert prof["effective_cores"] <= prof["logical_cores"]
    assert prof["effective_mem_gb"] <= prof["mem_gb"]


# ---- allocation-awareness (2026-08-03 Rockfish/m5 portability pass) --------

def _prof_v2(cores, mem, eff_cores=None, eff_mem=None, scheduler=None):
    p = _prof(cores, mem)
    p["effective_cores"] = eff_cores or cores
    p["cores_source"] = "cpu_count" if eff_cores is None else "slurm:SLURM_CPUS_PER_TASK"
    p["effective_mem_gb"] = eff_mem or mem
    p["mem_source"] = "physical" if eff_mem is None else "slurm"
    p["scheduler"] = scheduler
    return p


def test_legacy_profile_dict_plans_unchanged():
    # Old-shape dicts (no effective_* keys) must plan exactly as before —
    # the compatibility contract with every existing caller and test above.
    p = plan_welfare6_slots(_prof(32, 60), env={})
    assert (p["max_cpu_slots"], p["reserve_cores"]) == (7, 2)


def test_slurm_partial_allocation_plans_from_grant():
    # Rockfish standard node 48c/192G, but the job granted 12 cores / 48 GB:
    # reserve 0 under a scheduler; slots = min(12//4, 48//7=6, 8) = 3.
    prof = _prof_v2(48, 192, eff_cores=12, eff_mem=48,
                    scheduler={"kind": "slurm", "job_id": "123"})
    p = plan_welfare6_slots(prof, env={})
    assert (p["reserve_cores"], p["usable_cores"], p["max_cpu_slots"]) == (0, 12, 3)


def test_slurm_full_node_gets_reserve_zero():
    # A whole Rockfish node under SLURM: no interactive system to protect.
    prof = _prof_v2(48, 192, scheduler={"kind": "slurm", "job_id": "7"})
    p = plan_welfare6_slots(prof, env={})
    assert (p["reserve_cores"], p["max_cpu_slots"]) == (0, 8)


def test_affinity_confinement_without_slurm():
    # taskset-style cpuset restriction on an interactive box: effective
    # cores bind, but the interactive reserve (2) still applies.
    prof = _prof_v2(32, 60, eff_cores=6)
    prof["cores_source"] = "affinity"
    p = plan_welfare6_slots(prof, env={})
    assert (p["reserve_cores"], p["usable_cores"], p["max_cpu_slots"]) == (2, 4, 1)


def test_effective_memory_binds():
    # cgroup memory cap below physical: 20 GB grant -> 20//7 = 2 slots.
    prof = _prof_v2(48, 192, eff_mem=20,
                    scheduler={"kind": "slurm", "job_id": "9"})
    assert plan_welfare6_slots(prof, env={})["max_cpu_slots"] == 2


def test_reserve_env_override_wins_under_scheduler():
    prof = _prof_v2(48, 192, scheduler={"kind": "slurm", "job_id": "5"})
    p = plan_welfare6_slots(prof, env={"HAFISCAL_CPU_RESERVE_CORES": "4"})
    assert (p["reserve_cores"], p["usable_cores"]) == (4, 44)
