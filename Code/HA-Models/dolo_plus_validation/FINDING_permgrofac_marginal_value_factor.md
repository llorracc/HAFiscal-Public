# FINDING: HAFiscal solver omits PermGroFac^(-gamma) in the marginal-value factor

Date: 2026-06-03. Surfaced by the YAML <-> HAFiscal-code consistency check
(`check_vs_hafiscal_code.py`, ESC mode, `_TM-vs-MC` branch).

## What the check did
Built a baseline single-cohort HS `AggFiscalType` (interpretation='ESC'), solved it,
extracted its EXACT calibration (beta=0.9278, rho=2, Rfree=1.01, LivPrb=0.99375,
PermGroFac=[1.00453,1,1,1,1,1], the 6x6 MrkvArray, per-state IncShkDstn), then solved the
SAME problem with an independent textbook EGM (the equations the dolo-plus YAML encodes)
using that exact calibration, and compared the employed-state policy `cFunc[0](m)`.

## Result
| EGM marginal-value factor | max rel diff vs HAFiscal cFunc[0] |
|---|---|
| `(PermGroFac*psi)^(-gamma)`  (spec 7.4, standard HARK, the YAML) | **5.19%** (grows with m) |
| `psi^(-gamma)` only  (matches AggFiscalModel.py:1803) | **0.28%** (grid-level residual) |

Dropping `PermGroFac` from the EGM's marginal-value factor closes the gap to grid
precision -> the discrepancy is fully explained by that one factor.

## Root cause
`AggFiscalModel.py:1803` (and the identical `:1805`):
```python
vPnext_array = Rfree[j]*PermShkValsNext_tiled**(-CRRA)*vPfuncNext(mNrmNext_array)
```
uses `PermShk^(-CRRA)` ONLY. But the transition (`:1800`) correctly divides by
`PermGroFac[j]*PermShk`:
```python
mNrmNext_array = Rfree[j]*aNrmNow_tiled/(PermGroFac[j]*PermShkValsNext_tiled) + TranShkValsNext_tiled
```
Standard HARK (`ConsMarkovModel.solve_one_period_ConsMarkov:401`) uses
`vPfacEff = DiscFacEff*Rfree*PermGroFac**(-CRRA)` — i.e. it INCLUDES `PermGroFac^(-CRRA)`.
The Carroll envelope condition requires the marginal-value factor to be
`Ghat^(-gamma) = (PermGroFac*psi)^(-gamma)` to be consistent with a transition that
divides by `PermGroFac*psi`. HAFiscal uses `PermGroFac*psi` in the transition but only
`psi^(-gamma)` in the value factor — an internal inconsistency.

## Assessment
LIKELY A BUG in HAFiscal's custom `solve_agg_cons_markov_alt`: the `PermGroFac**(-CRRA)`
factor present in standard HARK is missing. Effect is small per period (PermGroFac ~ 1.0045
quarterly for employed, 1.0 for unemployed) but COMPOUNDS over the infinite horizon to
~5% on the employed consumption policy at high m. It is consistent across both code paths
(:1803 and :1805). Because the model was CALIBRATED with this solver, the estimated beta
likely absorbs part of the bias; fixing it cleanly would require re-checking the
calibration.

## Three-way consistency status (the user's original question)
- **spec/paper math (§7.4 `Ghat^(-gamma)`)  ==  standard HARK  ==  the dolo-plus YAML** — consistent.
- **HAFiscal code (`psi^(-gamma)` only)** — DEVIATES from all three.
So: YAML is faithful to the SPEC, NOT to the current CODE; the code appears to carry a bug.

## Decision needed (NOT made here)
(a) Treat as a HAFiscal solver bug -> add `PermGroFac**(-CRRA)` to AggFiscalModel.py:1803/1805
    (and re-verify calibration). The YAML is already correct. OR
(b) Treat the code as the reference -> change the YAML/spec marginal value to `psi^(-gamma)`
    (non-standard; would also require editing spec §7.4). NOT recommended — it's
    mathematically inconsistent with the transition.

Reproduce: `EGM_FACTOR_MODE={standard|hafiscal_code} python check_vs_hafiscal_code.py`
(report: `check_vs_hafiscal_report.txt`).

---

## UPDATE 2026-06-03: diagnostic fix applied + impact measured

Added guarded flag `HAFISCAL_PERMGROFAC_FIX` (default '0' = current behavior) at
AggFiscalModel.py:1803/1805 — when '1', multiplies the marginal value by
`PermGroFac[j]**(-CRRA)` (the standard/missing factor).

**(a) cFunc match (confirms the factor IS the whole discrepancy).** With the flag ON,
the employed cFunc[0](m) matches the standard EGM to grid precision across the reliable
range (m<=50): rel error drops from {0.69% @m=1, 2.74% @m=5, 5.20% @m=20, 6.72% @m=50}
to {0.16%, 0.12%, 0.28%, 0.20%}. (m>=100 diverges only from extrapolation past both
solvers' asset grids — not meaningful.)

**(b) aggregate/NPV impact (Reduced_Run, legacy 4-state, TM mode).** The bug_fix-encoding
runner is broken by a SEPARATE pre-existing issue (recessionTaxCut IncShkDstn uses
np.mod(i,4), assumes 4 micro states), so this used HAFISCAL_UI_STATE_ENCODING=legacy.
NPV fiscal multipliers and consumption shift (OFF -> ON):
  Check rec+AD     1.37 -> 1.41  (+2.9%)
  Check 1st-round  1.30 -> 1.33  (+2.3%)
  UI rec+AD        1.37 -> 1.39  (+1.5%)
  TaxCut rec+AD    1.14 -> 1.17  (+2.6%)
  NPV Check_Cons   78.06 -> 80.22 (+2.8%)
  NPV UI_Cons      84.90 -> 86.43 (+1.8%)
  NPV *_Inc        unchanged (income = policy injection, behavior-independent)
Direction: fix lowers marginal value of saving -> higher MPC -> larger consumption
response -> higher multiplier. ~100-300x larger than BUG-001's <0.01%.

**CRITICAL caveat — calibration absorption.** beta-bar/nabla were ESTIMATED with the
buggy solver. The numbers above are fix-solver-but-keep-beta, which OVERSTATES the true
impact. The honest "does it change conclusions" number requires re-estimating
(beta-bar, nabla, varsigma) with the fixed solver to re-match targets (K/Y, Lorenz, MPC);
the multiplier shift would then partly (maybe largely) re-absorb. That re-estimation is
the proper next step before judging materiality for the paper.

---

## ADDENDUM 2026-06-12: post-fix reconciliation (re-baseline under today's defaults)

Context: the fix landed as **BUG-047 FIXED, default-ON** (2026-06-04;
`Code/HA-Models/_permgrofac.py` matched-pair flag `HAFISCAL_PERMGROFAC_FIX=1`,
calibration re-estimated under the fixed solver). The 2026-06-03 report above
predated that and was stale. Both checks re-run 2026-06-12 under today's defaults
(`HAFISCAL_PERMGROFAC_FIX=1`, `HAFISCAL_INTERPRETATION=ESC`, re-estimated
calibration); reports regenerated.

### Result: the table from 2026-06-03 has inverted, exactly as the fix predicts

| EGM marginal-value factor | max rel diff vs HAFiscal cFunc[0], on-grid probes m<=40 | verdict |
|---|---|---|
| `(PermGroFac*psi)^(-gamma)` (spec 7.4 / standard HARK / YAML / **post-fix solver**) | **1.17e-4** | **PASS (<1e-3)** |
| `psi^(-gamma)` only (the legacy pre-BUG-047 solver math) | **5.06e-2** | FAIL — expected; now serves as the regression guard that the fix is active |

The production HAFiscal solver now agrees with the spec/YAML/standard-HARK equations
to ~1e-4; the legacy factor disagrees by ~5%. The three-way consistency gap reported
in the original finding is CLOSED: spec == standard HARK == YAML == HAFiscal code.

### Two measurement artifacts diagnosed during the re-baseline (neither is an equation issue)

1. **Grid-density residual at production grids.** At the production asset grid
   (aXtraCount=48, aXtraMax=40) the MODE-standard residual is 4.8e-3, above the 1e-3
   gate. Bisection over HAFiscal aXtraCount x EGM aCount (48/96/192 x 220/440):
   residual falls 4.8e-3 -> 9.0e-4 -> 1.1e-4 as aXtraCount doubles (≈4x per doubling,
   second-order convergence) and is insensitive to the EGM's own grid density. So it
   is HAFiscal asset-grid discretization, not an equation mismatch (this also explains
   the 2.84e-3 "MODE B grid-level residual" noted pre-fix). The check therefore gates
   at equation-check densities (aXtraCount=192, EGM aCount=440); production grids
   remain runnable via `--production-grids` (informational). Full bisection table in
   `check_vs_hafiscal_report.txt`.
2. **Extrapolation beyond grid support.** Probes at m in {50, 100, 300, 1000} exceed
   HAFiscal's aXtraMax=40, where its cFunc is linear extrapolation; the EGM (grid to
   2000) is essentially exact there, so the comparison measures extrapolation policy,
   not equations (2.8e-2 at m=100 rising to 1.4e-1 at m=1000 in MODE standard). These
   probes are printed as FYI rows and excluded from the gate. This is a documented
   gate-domain restriction, NOT a threshold relaxation — the 1e-3 threshold is
   unchanged, applied where both solvers are on-grid. (Whether solver-grid
   extrapolation above m=40 matters in production simulation is a separate question
   outside this harness's scope; noted for completeness.)

### test_euler_at_point.py (YAML-driven, solver-independent)

Re-run 2026-06-12: OVERALL PASS, unchanged from baseline (Euler residual 1.17e-4
normal / 7.96e-5 recession; EGM-vs-HARK c(5,0) cross-check 8.7e-5 / 1.0e-4). Expected:
it never touched the HAFiscal solver, so BUG-047 could not affect it.

Reproduce:
`EGM_FACTOR_MODE={standard|hafiscal_code} python check_vs_hafiscal_code.py [--production-grids]`
(reports: `check_vs_hafiscal_report.txt`, `validation_report.txt`; pytest tier:
`pytest Code/HA-Models/dolo_plus_validation -q`, fast tier with `-m "not slow"`).
