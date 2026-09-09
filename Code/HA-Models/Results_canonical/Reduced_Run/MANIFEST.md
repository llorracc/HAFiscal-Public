# Canonical results — Reduced_Run (2026-06-11)

Mid-scale tier (3 education cohorts, DiscFacCount=1 each) of the canonical-results
cascade (HS_Only → Reduced_Run → Baseline). Canonical solution approach throughout
(CLAUDE.md "Canonical solution approach (Plan A, 2026-06-10)").

## Configuration
- **Branch / commit:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` @ `cb7c2883`
- **Calibration (BUG-053, theGICfactor=0.9995):** D β=0.7384 ∇=0.3037 / HS β=0.9356
  ∇=0.0764 / C β=0.9920 ∇=0.0233 (single-β per education group at this tier)
- **Env:** `HAFISCAL_INTERPRETATION=ESC`, `HAFISCAL_TM_A_INDEXED=1` (multiplier),
  canonical defaults via EstimParameters (stratified-shuffle MC, TM_AMAX=1300),
  `bug_fix` UI encoding (default); multiplier run used `HAFISCAL_DUR_WORKERS=10`

## Multiplier (TM, a-indexed) — `multiplier/`
Producer: `AggFiscalMAIN_reduced.py` (default Reduced_Run scope) with the forked
TM-AD durations loop, 2026-06-11 00:0x–00:2x, **15.4 min wall** (Gate-2 forked arm,
output dirs `*_g2fork`). Fork transformation bit-validated at Gate-1 (HS_Only) AND at this tier:
**Gate-2 PASS (2026-06-11)** — sequential-reference run content-identical on every
value (all result pickles, `compare_result_pickles.py`) + Multiplier.tex identical.
Speedup at this tier: sequential 56.48 min → forked 15.40 min (**3.67×** at fork-10).

| 10y-horizon | Stimulus check | Tax cut |
|---|---|---|
| Multiplier (no AD) | 0.946 | 0.937 |
| Multiplier (AD) | 1.348 | 1.111 |
| Multiplier (1st-round AD only) | 1.263 | 1.079 |

- `multiplier/Multiplier.tex`; `multiplier/result_pickles/` (pickles named `*.csv`;
  compare via `compare_result_pickles.py`)
- Phase split (instrumentation): recessionCheck-AD Phase-1 training 278.8s,
  block total 437.1s at fork-10; recessionTaxCut-AD 68.6s / 220.5s.
  Phase-1 (solve chain) is the binding share at multi-cohort scale → next lever.
- Log: `/tmp/gate2_fork_reduced.log` (transient)

## Welfare-6 (MC + CRN + stratified-shuffle, canonical) — `welfare6_mc_pickles/`
Producer: `welfare6_scenario.py --parametrization Reduced_Run --seed-offset {0..3}`
(12 scenarios/seed incl. AD; 48/48 runs clean) + `welfare6_aggregator_stratified.py`.
Completed 2026-06-11. Cells (4-seed mean ± SE):

| cell | MC (4-seed) |
|---|---|
| check_norec | 0.9599 ± 0.0002 |
| taxcut_norec | 0.9869 ± 0.0000 |
| check_rec | 1.0074 ± 0.0012 |
| ui_rec | 1.4991 ± 0.0109 |
| taxcut_rec | 0.9965 ± 0.0002 |
| check_rec_AD | 1.4384 ± 0.0023 |
| ui_rec_AD | 1.9768 ± 0.0115 |
| taxcut_rec_AD | 1.1983 ± 0.0004 |
| ui_norec | **excluded** (0/0 by construction — never reported) |

All 8 reportable cells present (complete). Pickles: `welfare6_mc_pickles/seed{0..3}/`.

## Retrieval
- Tables/cells: this manifest + `multiplier/Multiplier.tex`
- Full arrays: pickles under `multiplier/result_pickles/` and `welfare6_mc_pickles/seed{0..3}/`
- Regenerate: commands above at commit `cb7c2883` with the stated env
