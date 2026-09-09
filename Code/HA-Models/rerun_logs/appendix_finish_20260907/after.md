# Appendix 𝒞 tables re-issued (CRRA-consistent normalizer, BUG-082) — UI policy: window

𝒞 = consumption-equivalent welfare gain in basis points of lifetime consumption (`welfare_ce.py`, `crra`); candidate = mean over
seeds (± SE) on the chain's final configuration; published = QE 17(3) hand-typed rows. γ = 1 stays dropped (ruling 2026-08-21).

**DO NOT COMPARE THE TWO COLUMNS CELL BY CELL.** They are different measures, not the same measure on two models. The
published 𝒞 divided the utility change by a log-utility normalizer W_c = PDV(1)·N (BUG-082). At γ = 2 that divisor is 12.06×
too large, and — worse than a scale error — it leaves the gain carrying units of 1/c while the cost share it is netted against
is dimensionless. So the error is NOT a common factor: it does not preserve ratios between policies, and it is not even
sign-preserving. Measured on this model (welfare_ce_decomposition.py, seed 0): under the published formula the revised model
reports the UI extension's recession gain as NEGATIVE in 8 of the 10 arms, while the corrected 𝒞 and the main-text 𝒲 (which
never used W_c and is correct for any ρ) both make it strongly positive. The published column's own positivity was a
coincidence of its calibration, not a property of the measure.

The comparisons that DO carry over: the within-table ORDERING of the corrected column, and the main-text 𝒲 and the
multipliers, which are unaffected by BUG-082. Where a `published formula` column appears below, it is THIS model scored by
the published measure — that column, and only that column, is like-for-like against `published`.

## interest rate

| | row | published check / UI / tax cut | THIS model, published formula | candidate check / UI / tax cut (S) |
|---|---|---|---|---|
| no AD effects | $R = 1.005$ | 0.005 / 0.295 / 0.001 | 0.091 / -0.568 / 0.172 | 0.620 ± 0.065 / 0.866 ± 0.031 / 0.115 ± 0.010 (S=3) |
|  | $R = 1.01$ (baseline) | 0.011 / 0.509 / 0.002 | 0.157 / -1.131 / 0.308 | 1.048 ± 0.078 / 1.547 ± 0.038 / -0.005 ± 0.011 (S=5) |
|  | $R = 1.015$ | 0.014 / 0.666 / 0.003 | 0.227 / -1.575 / 0.432 | 1.452 ± 0.201 / 2.352 ± 0.095 / -0.076 ± 0.027 (S=3) |
| AD effects | $R = 1.005$ | 0.081 / 0.618 / 0.030 | 0.228 / -0.527 / 0.328 | 1.764 ± 0.063 / 1.119 ± 0.031 / 1.412 ± 0.012 (S=3) |
|  | $R = 1.01$ (baseline) | 0.151 / 1.101 / 0.056 | 0.424 / -1.052 / 0.609 | 3.300 ± 0.077 / 2.039 ± 0.037 / 2.535 ± 0.015 (S=5) |
|  | $R = 1.015$ | 0.215 / 1.496 / 0.081 | 0.614 / -1.461 / 0.868 | 4.766 ± 0.194 / 3.068 ± 0.095 / 3.647 ± 0.033 (S=3) |

## risk aversion

| | row | published check / UI / tax cut | THIS model, published formula | candidate check / UI / tax cut (S) |
|---|---|---|---|---|
| no AD effects | $\gamma = 2.0$ (baseline) | 0.011 / 0.509 / 0.002 | 0.157 / -1.131 / 0.308 | 1.048 ± 0.078 / 1.547 ± 0.038 / -0.005 ± 0.011 (S=5) |
|  | $\gamma = 3.0$ | 0.011 / 0.558 / 0.002 | 0.174 / -1.377 / 0.332 | 4.228 ± 1.994 / 2.355 ± 0.234 / -0.045 ± 0.078 (S=3) |
| AD effects | $\gamma = 2.0$ (baseline) | 0.151 / 1.101 / 0.056 | 0.424 / -1.052 / 0.609 | 3.300 ± 0.077 / 2.039 ± 0.037 / 2.535 ± 0.015 (S=5) |
|  | $\gamma = 3.0$ | 0.156 / 1.207 / 0.059 | 0.261 / -1.351 / 0.430 | 6.715 ± 1.992 / 2.908 ± 0.229 / 2.756 ± 0.093 (S=3) |

## benefits

| | row | published check / UI / tax cut | THIS model, published formula | candidate check / UI / tax cut (S) |
|---|---|---|---|---|
| no AD effects | Baseline ($\rho_b = 0.7$, $\rho_{nb} = 0.5$) | 0.011 / 0.509 / 0.002 | 0.157 / -1.131 / 0.308 | 1.048 ± 0.078 / 1.547 ± 0.038 / -0.005 ± 0.011 (S=5) |
|  | Altern. ($\rho_b = 0.3$, $\rho_{nb} = 0.15$) | 0.043 / 1.845 / 0.003 | 1.405 / 1.066 / 0.330 | 8.915 ± 1.252 / 10.727 ± 0.243 / 0.075 ± 0.019 (S=3) |
| AD effects | Baseline ($\rho_b = 0.7$, $\rho_{nb} = 0.5$) | 0.151 / 1.101 / 0.056 | 0.424 / -1.052 / 0.609 | 3.300 ± 0.077 / 2.039 ± 0.037 / 2.535 ± 0.015 (S=5) |
|  | Altern. ($\rho_b = 0.3$, $\rho_{nb} = 0.15$) | 0.157 / 2.514 / 0.048 | 1.768 / 1.186 / 0.722 | 11.735 ± 1.271 / 11.440 ± 0.245 / 3.158 ± 0.021 (S=3) |

## recession properties

| | row | published check / UI / tax cut | THIS model, published formula | candidate check / UI / tax cut (S) |
|---|---|---|---|---|
| no AD effects | Baseline | 0.011 / 0.509 / 0.002 | 0.157 / -1.131 / 0.308 | 1.048 ± 0.078 / 1.547 ± 0.038 / -0.005 ± 0.011 (S=5) |
|  | Shorter average recession, 4q | 0.010 / 0.424 / 0.002 | 0.132 / -0.972 / 0.247 | 0.828 ± 0.147 / 1.416 ± 0.257 / -0.007 ± 0.030 (S=3) |
|  | Stronger AD effects, 0.5 | 0.011 / 0.509 / 0.002 | 0.155 / -1.101 / 0.304 | 1.007 ± 0.134 / 1.560 ± 0.062 / -0.010 ± 0.018 (S=3) |
| AD effects | Baseline | 0.151 / 1.101 / 0.056 | 0.424 / -1.052 / 0.609 | 3.300 ± 0.077 / 2.039 ± 0.037 / 2.535 ± 0.015 (S=5) |
|  | Shorter average recession, 4q | 0.143 / 0.926 / 0.045 | 0.380 / -0.906 / 0.484 | 2.926 ± 0.150 / 1.828 ± 0.258 / 1.998 ± 0.029 (S=3) |
|  | Stronger AD effects, 0.5 | 0.297 / 1.695 / 0.110 | 0.684 / -0.948 / 0.886 | 5.479 ± 0.126 / 2.512 ± 0.062 / 4.907 ± 0.027 (S=3) |

10-year multipliers with AD (the text quotes them; published → candidate):
- Baseline: 1.245 / 1.200 / 0.999 → 1.318 / 1.256 / 1.086
- Shorter average recession, 4q: 1.224 / 1.180 / 0.967 → 1.296 / 1.240 / 1.053
- Stronger AD effects, 0.5: 1.636 / 1.492 / 1.152 → 1.692 / 1.541 / 1.233

## the UI-extension policy

The UI-extension policy is a DISCRETIONARY design choice, not a correction (owner rulings 2026-08-27 17:00 and 2026-08-28 10:33): the main text keeps the paper's window, a one-time extension at the recession's onset (four quarters for the onset cohort, three for the next quarter's entrants, nothing further); the history-consistent policy, enacted one quarter in with open entry and in force through quarter 8 with a hard stop, is this appendix's arm.
Rows: the revised model under each policy, for the Baseline (S = 3/5 seeds, per row; the two-row report of waterfall_table.py --order ui-policy, memo v3 section 5) and for the alternative benefit rates (S = 3 seeds), the one configuration where the policy moves the UI multiplier.
Columns: the 10-year multipliers with AD effects (the exact transition-matrix evolution; no sampling, so no SE); the welfare gain of the UI extension in a recession with and without AD effects, PER DOLLAR of outlay (the welfare-6 cells; mean over the S seeds, SE = std/sqrt(S) in parentheses); the share of the extension's outlay paid during the recession; S = the number of welfare seeds in the row.

| configuration | UI-extension policy | 10y AD multiplier check / UI / tax cut | W(UI, Rec, AD) per $ | W(UI, Rec) per $ | UI outlay in recession | S |
|---|---|---|---|---|---|---|
| Baseline ($\rho_b = 0.7$, $\rho_{nb} = 0.5$) | the paper's window | 1.318 / 1.256 / 1.086 | 2.099 ± 0.022 | 1.792 ± 0.017 | 78.8 % | 5 |
| Baseline ($\rho_b = 0.7$, $\rho_{nb} = 0.5$) | history-consistent | 1.318 / 1.244 / 1.086 | 2.032 ± 0.028 | 1.737 ± 0.020 | 65.4 % | 3 |
| Altern. ($\rho_b = 0.3$, $\rho_{nb} = 0.15$) | the paper's window | 1.342 / 1.392 / 1.091 | 9.784 ± 0.271 | 9.210 ± 0.257 | 78.8 % | 3 |
| Altern. ($\rho_b = 0.3$, $\rho_{nb} = 0.15$) | history-consistent | 1.342 / 1.610 / 1.091 | 8.923 ± 0.207 | 8.126 ± 0.181 | 65.4 % | 3 |

