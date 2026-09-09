# Step-1 attribution ladder on the ORIGINAL model (2026-08-29/30, dell; `Code/HA-Models/coldrun/step1_ladder.sh`)

Each rung = the paper's Step-1 estimation (N = 5,000, T_sim = 800, no wall, ESC = the published world's interpretation) plus ONE named
change, 8 grid starts + the paper's own start; the winner and the paper's-start result agree to ≤ 2e-4 in every rung (one basin).

| rung | change | ς | β | ∇ | f |
|---|---|---|---|---|---|
| r0w | the paper's procedure complete (published read-out, lottery arithmetic, cap formula, Powell + arctan taper τ 0.01, scipy tolerances, 20/20 grid) — reproduces 0.24611/0.96755/0.05781 (pristine 0.14.1 run: f 0.004889) | 0.24669 | 0.96768 | 0.05762 | 0.004885 |
| r0 | + the BUG-031 wealth read-out (1 − ς)·aLvl in the K/Y target | 0.25889 | 0.97104 | 0.05931 | 0.005875 |
| r1 | + the ESC lottery arithmetic (BUG-054 Option A) | 0.26374 | 0.97062 | 0.06013 | 0.005700 |
| r2 | + the BUG-060 cap formula | 0.27158 | 0.97214 | 0.05118 | 0.004029 |
| r3 | + the solve grid (K·h̄, 604/238) and tail extrapolation (BUG-061/062) | 0.27693 | 0.97405 | 0.04701 | 0.003588 |
| r3b | + the taper threshold 0.002 alone (paper's Powell/arctan kept) | 0.30157 | 0.97963 | 0.02921 | 0.001983 |
| r4 | + the level-splurge COBYQA parametrization at τ 0.002 | 0.30153 | 0.97963 | 0.02921 | 0.001983 |
| r5 | + the deterministic TM engine (= column C's Step 1: 0.29987 on ccarroll) | 0.29984 | 0.97952 | 0.02939 | 0.001647 |

Reading (owner principle §0b of the chain plan): r0w→r0, r0→r2, r2→r3 are corrections of the paper's estimation (BUG-031's read-out,
BUG-060, BUG-061/062); r0→r1 the ESC arithmetic (the interpretation's Step-1 face); r4→r5 the engine (−0.6 %, MC noise: machinery).
r3→r4 (+8.9 %) is ENTIRELY the taper threshold (r3b = r4 to 1e-4 in ς and f): the paper's τ = 0.01 band held the optimum's top atom
(published 0.9676 + 0.0578·6/7 = 1.0171 vs the cap 1.0063: 0.011 into a 0.010 band), so the published estimate was shaped by the
estimator's cap-taper device — an estimation-side defect of the paper's code (BUG-104, the same class as BUG-060/061); the
optimizer/parametrization (r3b→r4) is machinery (+0.0 %).
