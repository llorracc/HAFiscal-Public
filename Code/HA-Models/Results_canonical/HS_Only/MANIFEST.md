# Canonical results — HS_Only (2026-06-10/11)

Single-cohort (high-school, DiscFacCount=1) tier of the canonical-results cascade
(HS_Only → Reduced_Run → Baseline). All runs on the **canonical solution approach**
(CLAUDE.md "Canonical solution approach (Plan A, 2026-06-10)").

## Configuration (identical for every artifact below)
- **Branch / commit:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` @ `cb7c2883`
  (Plan A canonicalization + BUG-053 calibration + TM-AD durations fork)
- **Calibration (BUG-053, theGICfactor=0.9995):** D β=0.7384 ∇=0.3037 / HS β=0.9356
  ∇=0.0764 / C β=0.9920 ∇=0.0233 (only HS used at this tier); GIC-cap GPF=0.9995
- **Env:** `HAFISCAL_INTERPRETATION=ESC`, `HAFISCAL_TM_A_INDEXED=1` (multiplier),
  canonical defaults via EstimParameters (MC_SHUFFLE=1, SHUFFLE_MRKV_TRANSITION=stratified,
  SHUFFLE_NEWBORN_FIX=transition, TM_AMAX=1300), `HAFISCAL_UI_STATE_ENCODING=bug_fix` (default)
- **Python/HARK:** .venv (3.11), HARK 0.17.x pinned ref

## Multiplier (TM, a-indexed) — `multiplier/`
Producer: `AggFiscalMAIN_reduced.py --hs-only`, 2026-06-10 ~23:39–23:58 (18.7 min,
forked TM-AD durations loop, Gate-1 run). **Bit-validated**: content-identical to the
sequential run on every value (all 28 result pickles + Multiplier.tex;
`compare_result_pickles.py`).

| 10y-horizon | Stimulus check | Tax cut |
|---|---|---|
| Multiplier (no AD) | 0.978 | 0.982 |
| Multiplier (AD) | 1.458 | 1.205 |
| Multiplier (1st-round AD only) | 1.341 | 1.157 |

- `multiplier/Multiplier.tex` — the table above (UI multiplier cells not produced by this table)
- `multiplier/result_pickles/` — full per-scenario + per-duration result pickles
  (`*_results*.csv` files are PICKLES; load with pickle, compare with `compare_result_pickles.py`)
- Log: `/tmp/gate1_forked_hsonly.log` (transient)

## Welfare-6 (MC + CRN + stratified-shuffle, canonical) — `welfare6_mc_pickles/`
Producer: `welfare6_scenario.py --parametrization HS_Only --seed-offset {0,1,2,3}`
+ `welfare6_aggregator_stratified.py`, 2026-06-10 (MC-vs-TM-a cascade session).
N=10,000 agents/seed. Cells (4-seed mean ± SE):

| cell | MC (4-seed) |
|---|---|
| check_norec | 0.9596 ± 0.0001 |
| taxcut_norec | 0.9836 ± 0.0000 |
| check_rec | 1.0120 ± 0.0005 |
| taxcut_rec | 0.9958 ± 0.0002 |
| ui_rec | 1.5457 ± 0.0058 |
| check_rec_AD | 1.5332 ± 0.0016 |
| ui_rec_AD | 2.0991 ± 0.0070 |
| taxcut_rec_AD | 1.2533 ± 0.0005 |
| ui_norec | **excluded** (0/0 by construction — never reported) |

All 8 reportable welfare-6 cells present (complete). AD amplification pattern (check
1.01→1.53, ui 1.55→2.10, taxcut 1.00→1.25) matches the paper's qualitative Baseline
pattern, stronger at the HS-only single-cohort tier as expected.

- `welfare6_mc_pickles/{norec,rec}_seed{0..3}/` — per-scenario MC panel pickles
  (base/Check/UI/TaxCut; recession*/recession*_AD variants in `rec_seed*`)
- Validation context: `conclusions_private/2026-06-10_mc_vs_tma_welfare_cascade_HS_Only.md`
  (MC vs TM-a: taxcut agrees −0.13%; check/UI divergences explained, MC canonical)

## Retrieval
- Tables/cells: this manifest + `multiplier/Multiplier.tex`
- Full arrays: load the pickles (paths above) with `pickle.load`
- To regenerate: commands above at commit `cb7c2883` with the stated env
