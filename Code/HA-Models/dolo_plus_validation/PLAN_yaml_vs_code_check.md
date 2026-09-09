# Plan: YAML ↔ HAFiscal-code consistency check (ESC, _TM-vs-MC branch)

Goal: verify the dolo-plus YAML's OPTIMIZER stage reproduces what HAFiscal's actual
solver (`AggFiscalType`, interpretation='ESC') computes — decoupling equation-faithfulness
from calibration-value choices.

Steps:
1. Build a baseline single-cohort `AggFiscalType` on this branch with `interpretation='ESC'`
   (env `HAFISCAL_INTERPRETATION=ESC` or the attribute). Baseline = no recession (1 macro
   state, J=6 micro). Solve to convergence.
2. Extract the EXACT calibration the agent used: DiscFac (beta), CRRA, Rfree, LivPrb,
   PermGroFac (the per-micro-state vector), the 6x6 MrkvArray, and IncShkDstn[z] per state.
3. Read HAFiscal's solved policy: solution[0].cFunc[E](m=5)  (E = employed micro state).
4. Run the independent EGM (test_euler_at_point.py machinery) with HAFiscal's EXACT
   calibration from step 2.
5. Compare cFunc[E](5): HAFiscal vs EGM. PASS if rel diff < 1e-3 -> YAML equations match
   HAFiscal code. Also spot-check a few m points across the grid.
6. If mismatch: bisect (PermGroFac vector? IncShkDstn? asset rule a=m-c vs splurge?).

Under ESC the optimizer asset rule is HARK default a=m-c (AggFiscalModel.py:1423), so the
optimizer cFunc should be a standard Markov buffer-stock — exactly what the EGM solves.
