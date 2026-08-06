#!/usr/bin/env python
"""Regression gate: TM-ergodic vs MC aNrm-moment agreement (HS_Only).

WHY THIS TEST EXISTS
--------------------
This is the **parity gate** for the (owner-approved, currently DEFERRED)
TM-ergodic Step-2 wiring. Phase A of the solve/simulate tool map
(`conclusions_private/2026-06-21_toolchain-ledger.md` §A.2;
`Code/HA-Models/docs/SOLVE_SIMULATE_TOOLMAP.md`) established that the
**TM-ergodic** asset moments — computed via the *production* seeding path
`tm_methods.compute_baseline_tm_data` (the same a-indexed transition-matrix
ergodic that `welfare6_scenario.py` / `Simulate.py` use to warm-start the
Monte-Carlo agents) — agree with the **MC** forward-sim's aggregate normalized
assets to within ~2% (MC sampling noise) and run ~10-21x faster.

Because that agreement is the safety condition under which the deferred
TM-ergodic Step-2 wiring can later be flipped on, this test locks it in as a
regression gate: if a future change breaks TM-vs-MC moment agreement, this
test fails and the flip-on is blocked until the divergence is understood.

THIS TEST CHANGES NO DEFAULT BEHAVIOR. It only *measures* the existing
default EGM solve + MC sim against the existing (deterministic) TM-ergodic
kernel — both already exercised by `bench_toolmap.py`. The TM-ergodic Step-2
wiring is NOT enabled by this test or by the default pipeline.

PHASE-A MEASURED NUMBERS (HS_Only; identical on econ-mw x86_64 and
ccarroll-m5 arm64 — see ledger §A.2, and `results/*.json`):
    aNrm_mean : MC 0.4072121  TM 0.4099529   ->  Δ = +0.6731 %
    aNrm_var  : MC 0.1325750  TM 0.1356842   ->  Δ = +2.3452 %
(speed: TM-ergodic ~10-21x faster per eval than the MC sim.)

The +0.67% / +2.34% gap is a structural TM-vs-MC / sampling difference (TM
ergodic and MC are two *different* estimators of the same ergodic moment), not
a platform artifact or a bug — it is identical to ~1e-16 across both machines.

WHAT IS COMPARED (apples-to-apples)
-----------------------------------
Both sides use the RAW-KERNEL aNrm moments, NOT the per-interpretation
(1-splurge) household rescale:
  * MC  : mean/var of the raw `aNrm_all` panel (`tool_sim` ->
          `agg_moments.aNrm_mean` / `aNrm_var`).
  * TM  : E[a]=Σ π(a)·a and Var[a]=Σ π(a)·a² over the SAME grid the MC is
          seeded from (`tool_tm_ergodic` -> `tm_moments.aNrm_mean` /
          `aNrm_var`). (`tm_moments.A_nrm_household` is the
          interpretation-aware mean and is deliberately NOT the comparand.)

TOLERANCE RATIONALE
-------------------
Bands are documented, regression-catching, and comfortably above the observed
gap + MC noise — they are NOT FP-tight (TM and MC are different estimators, so
an FP band would be wrong):
  * aNrm_mean: |Δ| < 0.03  (observed 0.0067 -> ~4.5x headroom)
  * aNrm_var : |Δ| < 0.05  (observed 0.0235 -> ~2.1x headroom)
The headroom absorbs ordinary MC sampling jitter while still catching any real
structural divergence (a broken kernel, a grid/seeding regression, etc.).

DETERMINISM & SPEED
-------------------
Deterministic: the MC sim uses fixed per-type seeds (set in `build_economy`),
and the TM ergodic is a no-RNG power-iteration fixed point. Fast: a single
HS_Only solve + short MC sim (act_T=100) + one TM ergodic, < ~15 s wall.

REUSE
-----
The economy build, EGM solve, MC sim, and TM-ergodic kernel are imported
straight from `bench_toolmap.py` (the Phase-A harness) — this test does NOT
duplicate any economy-build / solve / sim logic. Importing `bench_toolmap`
also performs its module-load setup (patches `sys.argv`, prepends
`FromPandemicCode/` to `sys.path`, `chdir`s into it, single-threads BLAS,
headless matplotlib) so the imported helpers run in the same environment they
were designed for.

RUN
---
    VIRTUAL_ENV=.venv-linux-x86_64 uv run --no-sync --active \
        python -m pytest Code/HA-Models/toolmap/test_tm_ergodic_parity.py -v
(plain `uv run` creates an empty `.venv` and fails to import numpy.)
Discoverable by `pytest Code/`.
"""

# Importing bench_toolmap runs its module-level environment setup (sys.argv /
# sys.path / chdir into FromPandemicCode / BLAS single-threading / Agg backend),
# and gives us the exact Phase-A helpers — no economy-build duplication here.
import bench_toolmap as bench

# Documented Phase-A bands (see module docstring). Above the observed
# +0.67% / +2.34% gap + MC noise; not FP-tight (different estimators).
MEAN_REL_TOL = 0.03
VAR_REL_TOL = 0.05

# Phase-A measured deltas (HS_Only, both platforms) — recorded for the report.
OBSERVED_MEAN_DELTA = 0.0067
OBSERVED_VAR_DELTA = 0.0235


def _rel_delta(tm_value, mc_value):
    """Relative |Δ| of the TM moment vs the MC moment (MC is the reference)."""
    return abs(tm_value - mc_value) / abs(mc_value)


def test_tm_ergodic_vs_mc_anrm_moments():
    """Build/solve HS_Only once, then assert TM-ergodic aNrm moments match the
    MC sim's raw aNrm moments within the documented Phase-A bands."""
    # --- Build + solve the HS_Only economy ONCE (reused by sim + TM). ---------
    econ, base_dict = bench.build_economy(bench.PARAMETRIZATION)
    state = {"econ": econ, "base_dict": base_dict}

    # tool_solve solves the economy in place (the shared `econ`); tool_sim and
    # tool_tm_ergodic both read that one solution — exactly as the harness does.
    bench.tool_solve(state)

    # --- MC forward sim: raw aNrm_all moments (agg_moments.aNrm_*). -----------
    mc_out = bench.tool_sim(state)
    mc_moments = mc_out["agg_moments"]
    mc_mean = float(mc_moments["aNrm_mean"])
    mc_var = float(mc_moments["aNrm_var"])

    # --- TM-ergodic: raw-kernel aNrm moments (tm_moments.aNrm_*). -------------
    tm_out = bench.tool_tm_ergodic(state)
    tm_moments = tm_out["tm_moments"]
    tm_mean = float(tm_moments["aNrm_mean"])
    tm_var = float(tm_moments["aNrm_var"])

    # --- Compare. -------------------------------------------------------------
    mean_rel = _rel_delta(tm_mean, mc_mean)
    var_rel = _rel_delta(tm_var, mc_var)

    mean_msg = (
        f"TM-ergodic vs MC aNrm_MEAN disagreement {mean_rel:.4%} exceeds band "
        f"{MEAN_REL_TOL:.0%} (Phase-A observed ~{OBSERVED_MEAN_DELTA:.2%}). "
        f"MC={mc_mean:.7f}  TM={tm_mean:.7f}  "
        f"signed Δ={100.0 * (tm_mean - mc_mean) / mc_mean:+.4f}%."
    )
    var_msg = (
        f"TM-ergodic vs MC aNrm_VAR disagreement {var_rel:.4%} exceeds band "
        f"{VAR_REL_TOL:.0%} (Phase-A observed ~{OBSERVED_VAR_DELTA:.2%}). "
        f"MC={mc_var:.7f}  TM={tm_var:.7f}  "
        f"signed Δ={100.0 * (tm_var - mc_var) / mc_var:+.4f}%."
    )

    assert mean_rel < MEAN_REL_TOL, mean_msg
    assert var_rel < VAR_REL_TOL, var_msg

    # Surface the measured agreement even on PASS (visible with `pytest -s`).
    print(
        "\n[parity] HS_Only TM-ergodic vs MC raw aNrm moments:\n"
        f"  aNrm_mean: MC={mc_mean:.7f}  TM={tm_mean:.7f}  "
        f"Δ={100.0 * (tm_mean - mc_mean) / mc_mean:+.4f}%  "
        f"(band {MEAN_REL_TOL:.0%})\n"
        f"  aNrm_var : MC={mc_var:.7f}  TM={tm_var:.7f}  "
        f"Δ={100.0 * (tm_var - mc_var) / mc_var:+.4f}%  "
        f"(band {VAR_REL_TOL:.0%})",
        flush=True,
    )


if __name__ == "__main__":
    # Allow `python test_tm_ergodic_parity.py` for a quick manual check.
    test_tm_ergodic_vs_mc_anrm_moments()
    print("\nPASS: TM-ergodic vs MC aNrm-moment parity within Phase-A bands.")
