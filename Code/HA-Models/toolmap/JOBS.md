# Phase-A tool-map — two-machine job board

**Driver:** econ-mw (`dell-8960-ext`, x86_64, has GPU). **Runner:** ccarroll-m5 (arm64 Mac, CPU/Metal).
**Coordination:** this branch (`…_toolmap-phase-a`, pushed) + LAN ssh. Each machine runs the *same committed* `bench_toolmap.py` and writes `results/<hostname>.json`. The runner writes ONLY to `results/` + this board.

| # | job | machine | command | result file | status |
|---|---|---|---|---|---|
| 1 | bench v1 (EGM solve + MC sim) | econ-mw | `uv run python Code/HA-Models/toolmap/bench_toolmap.py` | `results/econ-ark-XPS-8960.json` | **DONE** (solve 0.25s / sim 0.63s / total 1.81s; deterministic; HS_Only) |
| 2 | bench v1 (EGM solve + MC sim) | ccarroll-m5 | `git pull` → `.venv-darwin-arm64/bin/python …/bench_toolmap.py` | `results/ccarroll-m5.json` | **DONE** (solve 0.21s / sim 0.50s; arm64) |
| 3 | diff fingerprints → x86↔arm64 tolerance | econ-mw | `python …/compare_results.py` | ledger A.1 | **DONE** (worst rel **3.3e-15** = ~14 sig figs; same-platform bit-identical) |
| 4 | add **TM-ergodic** sim tool, re-bench both | both | `bench_toolmap.py` | both results | **DONE** (21× econ-mw / 10.5× Mac vs MC; matches ~2%; x-plat 1e-16) |
| 5 | add **Anderson-EGM** solve tool, re-bench both | both | `bench_toolmap.py` | both results | **DONE** (econ-mw 5.3× engaged; Mac fell back — sibling-repo gap; matches EGM ~1e-3) |
| 6 | write SOLVE_SIMULATE_TOOLMAP.md + win-list → pick Phase B | econ-mw | — | `docs/SOLVE_SIMULATE_TOOLMAP.md` | **DONE** → Phase-B target = **TM-ergodic** |

**Phase A v1 COMPLETE.** Tools mapped: EGM, Anderson-EGM, MC, TM-ergodic (both machines). Cross-platform tolerance 3.3e-15. Win-list → TM-ergodic. Next: **Phase B** — build TM-ergodic as opt-in/parity-gated/default-OFF (separate plan).

**Protocol:** driver builds/extends the harness + pushes; runner pulls + runs CPU jobs + pushes results; driver collects + diffs. GPU/JAX jobs are econ-mw-only (tag them in the result, never expect them on the Mac).

**Update rule:** flip a row's status as it completes; record the result filename. Keep the cross-platform tolerance here once job 3 lands.
