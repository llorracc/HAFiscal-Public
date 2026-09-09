# Bug-fix attribution ladder — the as-corrected engine with ONE fix at its published value per arm

Base: bug-fixed engine (as-corrected) — AD multipliers 1.271 / 1.207 / 1.037 (Check / UI / TaxCut); welfare S=5.
Entries: the arm's value and its change from the base (welfare: mean of the arm's seeds vs the base's S-seed mean; the base's
across-seed SE is the noise scale — an entry inside ±2 SE is not distinguishable from zero).

| fix toggled off | class | AD mult. Check / UI / TaxCut (Δ %) | check_rec (Δ %) | ui_rec (Δ %) | taxcut_rec (Δ %) | check_rec_AD (Δ %) | ui_rec_AD (Δ %) | taxcut_rec_AD (Δ %) |
|---|---|---|---|---|---|---|---|---|
| welfare formula u(E[c]) (BUG-046) | published-path | 1.271 (+0.0 %) / 1.207 (+0.0 %) / 1.037 (+0.0 %) | 1.006 (-0.8 %; 7.9 SE, S=2) | 1.577 (-15.9 %; 27.0 SE, S=2) | 0.998 (+0.6 %; 23.6 SE, S=2) | 1.379 (-0.8 %; 5.0 SE, S=2) | 1.893 (-13.4 %; 28.0 SE, S=2) | 1.154 (+0.2 %; 4.6 SE, S=2) |
| naive-linear cFunc tail (BUG-061/062) | published-path | — | — | — | — | — | — | — |
| m-indexed TM (BUG-033) | new-engine | 1.218 (-4.2 %) / 1.182 (-2.1 %) / 0.998 (-3.8 %) | 1.014 (+0.1 %; 0.6 SE, S=2) | 1.880 (+0.3 %; 0.5 SE, S=2) | 0.992 (+0.0 %; 0.3 SE, S=2) | 1.392 (+0.1 %; 0.8 SE, S=2) | 2.205 (+0.9 %; 1.9 SE, S=2) | 1.151 (-0.0 %; 0.6 SE, S=2) |
| grid top 500 (BUG-084) | new-engine | 1.271 (+0.0 %) / 1.207 (+0.0 %) / 1.037 (+0.0 %) | 1.014 (+0.1 %; 0.6 SE, S=2) | 1.880 (+0.3 %; 0.5 SE, S=2) | 0.992 (+0.0 %; 0.3 SE, S=2) | 1.392 (+0.1 %; 0.8 SE, S=2) | 2.205 (+0.9 %; 1.9 SE, S=2) | 1.151 (-0.0 %; 0.6 SE, S=2) |
| cohort Q-construction (BUG-093) | new-engine | — | — | — | — | — | — | — |
| slope tail exponent (BUG-089) | new-engine | — | — | — | — | — | — | — |

Not toggleable at run time: BUG-053 (GIC-cap factor 0.999 → 0.9995, carried by the re-estimated calibration), BUG-090 and
BUG-091 (the welfare battery's own solve of the unemployed-income process and the tax cut's length — SST fixes; the
battery now consumes the multiplier program's solutions and solves nothing).
