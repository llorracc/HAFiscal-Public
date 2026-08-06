# Canonical results — Baseline (2026-06-11)

Full-scale tier (21 cohorts: 3 education × 7 discount-factor atoms) of the canonical-results
cascade. Canonical solution approach throughout (CLAUDE.md "Canonical solution approach (Plan A, 2026-06-10)").

## Configuration
- **Branch / commit:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` @ `cb7c2883` (+ fork validated Gate-1/Gate-2)
- **Calibration (BUG-053, theGICfactor=0.9995):** D β=0.7384 ∇=0.3037 / HS β=0.9356 ∇=0.0764 / C β=0.9920 ∇=0.0233
- **Env:** `HAFISCAL_INTERPRETATION=ESC`, `HAFISCAL_TM_A_INDEXED=1` (multiplier), canonical defaults
  (stratified-shuffle MC, **TM_AMAX=1300**), `bug_fix` encoding; multiplier `HAFISCAL_DUR_WORKERS=10`

## Multiplier (TM, a-indexed) — `multiplier/` — COMPLETE
Producer: `AggFiscalMAIN_reduced.py --baseline`, 2026-06-11 00:30→10:00, **566.7 min (9.45 h)**
with the forked TM-AD durations loop — vs 22.5 h for the prior (sequential-AD) run = **2.4×**.
Fork bit-validated at Gate-1 (HS_Only) + Gate-2 (Reduced_Run); this run is the first full-scale
production use.

| 10y-horizon | Stimulus check | Tax cut |
|---|---|---|
| Multiplier (no AD) | 0.883 | 0.864 |
| Multiplier (AD) | 1.234 | 1.011 |
| Multiplier (1st-round AD only) | 1.162 | 0.985 |

**aMax matched-pair note (closes the ledger flag):** the prior 22.5 h Baseline ran aMax=500
(truncating the most-patient College atom's wealth tail); this run uses the canonical
**aMax=1300**. Deltas vs the aMax-500 run: Check AD 1.235→1.234, TaxCut AD 1.012→1.011,
first-round 1.163→1.162 / 0.986→0.985 (≤0.001 each, noAD identical) — the multiplier is
**insensitive to the grid extension**; the canonical numbers are confirmed at the correct grid.

- `multiplier/Multiplier.tex`; `multiplier/result_pickles/` (pickles named `*.csv`; figures incl.)
- Log: `/tmp/baseline_canonical_multiplier.log` (transient)

## Welfare-6 (MC + CRN + stratified-shuffle, canonical) — `welfare6_mc_pickles/` — RUNNING
Producer: `welfare6_scenario.py --parametrization Baseline --seed-offset {0..3}` (12 scenarios/seed,
`--duration-workers 1 --solve-workers 8`) + `welfare6_aggregator_stratified.py`. Chain launched
2026-06-11 ~01:00; ~32 min/scenario ⇒ full 4-seed set ~24 h. **Seed-0 cells (complete):**

| cell | MC (seed 0) |
|---|---|
| check_norec | 0.9624 |
| taxcut_norec | 0.9848 |
| check_rec | 1.0096 |
| ui_rec | 1.3812 |
| taxcut_rec | 0.9942 |
| check_rec_AD | 1.3701 |
| ui_rec_AD | 1.7243 |
| taxcut_rec_AD | 1.1726 |
| ui_norec | **excluded** (0/0 by construction) |

4-seed mean ± SE will replace this table when the chain completes (seeds 1-3 in flight).

## Retrieval
- Tables/cells: this manifest + `multiplier/Multiplier.tex`
- Full arrays: pickles under `multiplier/result_pickles/`, `welfare6_mc_pickles/seed{0..3}/`
- Regenerate: commands above at commit `cb7c2883`+ with the stated env
