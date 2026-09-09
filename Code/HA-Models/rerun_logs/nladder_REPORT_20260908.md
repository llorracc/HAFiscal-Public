# Income-strata shuffle: N-ladder certification report

Paired difference pstratM − plainM (relative, %) per rung; both arms Madow rounding, whole-cell seeds 0–2, CRN-paired. Standard: the difference vanishes with N (inside 2 paired SE at the top rung, or below the 0.05 % reporting-precision floor; and not growing along the ladder). Adopts nothing.

## baseline: Baseline, sharing + weighted-tail panel (the default world's sampler)

| N | cell | plainM per-seed SD | pstratM per-seed SD | paired diff | paired SE | z | S |
|---|---|---|---|---|---|---|---|
| 10000 | check_rec | 0.03 % | 0.13 % | +0.08 % | 0.07 % | 1.2 | 3 |
| 10000 | ui_rec | 3.07 % | 2.76 % | +1.02 % | 0.70 % | 1.5 | 3 |
| 10000 | taxcut_rec | 0.02 % | 0.03 % | -0.04 % | 0.01 % | 3.9 | 3 |
| 10000 | check_rec_AD | 0.37 % | 0.37 % | +0.07 % | 0.05 % | 1.4 | 3 |
| 10000 | ui_rec_AD | 3.87 % | 3.04 % | +0.87 % | 0.99 % | 0.9 | 3 |
| 10000 | taxcut_rec_AD | 0.06 % | 0.07 % | -0.05 % | 0.01 % | 4.3 | 3 |
| 40000 | check_rec | 0.10 % | 0.08 % | -0.03 % | 0.01 % | 3.1 | 3 |
| 40000 | ui_rec | 0.87 % | 0.24 % | +0.83 % | 0.42 % | 2.0 | 3 |
| 40000 | taxcut_rec | 0.01 % | 0.01 % | -0.01 % | 0.01 % | 0.9 | 3 |
| 40000 | check_rec_AD | 0.17 % | 0.17 % | -0.02 % | 0.01 % | 1.8 | 3 |
| 40000 | ui_rec_AD | 0.43 % | 0.07 % | +0.86 % | 0.23 % | 3.7 | 3 |
| 40000 | taxcut_rec_AD | 0.03 % | 0.03 % | -0.01 % | 0.01 % | 0.6 | 3 |
| 100000 | check_rec | 0.06 % | 0.08 % | +0.04 % | 0.01 % | 2.7 | 6 |
| 100000 | ui_rec | 0.95 % | 0.66 % | +0.67 % | 0.17 % | 4.0 | 6 |
| 100000 | taxcut_rec | 0.01 % | 0.01 % | -0.01 % | 0.00 % | 1.5 | 6 |
| 100000 | check_rec_AD | 0.06 % | 0.07 % | +0.04 % | 0.01 % | 3.7 | 6 |
| 100000 | ui_rec_AD | 0.84 % | 0.61 % | +0.63 % | 0.17 % | 3.8 | 6 |
| 100000 | taxcut_rec_AD | 0.02 % | 0.02 % | -0.00 % | 0.01 % | 0.6 | 6 |

### Verdict
- check_rec: top rung N=100000 diff +0.04 % ± 0.01 % (z 2.7); |diff| along the ladder 0.08 % → 0.03 % → 0.04 % — PASS (below the 0.05 % reporting-precision floor at the top)
- ui_rec: top rung N=100000 diff +0.67 % ± 0.17 % (z 4.0); |diff| along the ladder 1.02 % → 0.83 % → 0.67 % — FAIL (OUTSIDE 2 SE and above the 0.05 % floor at the top)
- taxcut_rec: top rung N=100000 diff -0.01 % ± 0.00 % (z 1.5); |diff| along the ladder 0.04 % → 0.01 % → 0.01 % — PASS (within 2 SE at the top)
- check_rec_AD: top rung N=100000 diff +0.04 % ± 0.01 % (z 3.7); |diff| along the ladder 0.07 % → 0.02 % → 0.04 % — PASS (below the 0.05 % reporting-precision floor at the top)
- ui_rec_AD: top rung N=100000 diff +0.63 % ± 0.17 % (z 3.8); |diff| along the ladder 0.87 % → 0.86 % → 0.63 % — FAIL (OUTSIDE 2 SE and above the 0.05 % floor at the top)
- taxcut_rec_AD: top rung N=100000 diff -0.00 % ± 0.01 % (z 0.6); |diff| along the ladder 0.05 % → 0.01 % → 0.00 % — PASS (within 2 SE at the top)

**baseline: NOT certifiable on this ladder — see the failing cells**

## hsonly: HS_Only, own AD loop + equal-weight panel (as-corrected's sampler)

| N | cell | plainM per-seed SD | pstratM per-seed SD | paired diff | paired SE | z | S |
|---|---|---|---|---|---|---|---|
| 1500 | check_rec | 0.62 % | 0.75 % | +0.16 % | 0.11 % | 1.5 | 3 |
| 1500 | ui_rec | 7.91 % | 0.72 % | -7.43 % | 4.11 % | 1.8 | 3 |
| 1500 | taxcut_rec | 0.05 % | 0.11 % | -0.07 % | 0.07 % | 1.0 | 3 |
| 1500 | check_rec_AD | 1.92 % | 2.11 % | -0.05 % | 0.12 % | 0.4 | 3 |
| 1500 | ui_rec_AD | 3.74 % | 1.52 % | -3.76 % | 2.17 % | 1.7 | 3 |
| 1500 | taxcut_rec_AD | 0.35 % | 0.19 % | -0.31 % | 0.20 % | 1.5 | 3 |
| 6000 | check_rec | 0.24 % | 0.25 % | -0.00 % | 0.02 % | 0.2 | 3 |
| 6000 | ui_rec | 2.49 % | 2.02 % | -0.27 % | 0.42 % | 0.7 | 3 |
| 6000 | taxcut_rec | 0.12 % | 0.13 % | -0.02 % | 0.03 % | 0.9 | 3 |
| 6000 | check_rec_AD | 0.46 % | 0.49 % | -0.01 % | 0.01 % | 0.6 | 3 |
| 6000 | ui_rec_AD | 1.57 % | 1.32 % | -0.16 % | 0.18 % | 0.9 | 3 |
| 6000 | taxcut_rec_AD | 0.12 % | 0.11 % | +0.00 % | 0.04 % | 0.1 | 3 |
| 24000 | check_rec | 0.12 % | 0.17 % | -0.04 % | 0.03 % | 1.4 | 3 |
| 24000 | ui_rec | 2.36 % | 2.31 % | +0.05 % | 0.42 % | 0.1 | 3 |
| 24000 | taxcut_rec | 0.03 % | 0.03 % | +0.02 % | 0.02 % | 1.0 | 3 |
| 24000 | check_rec_AD | 0.20 % | 0.16 % | -0.01 % | 0.02 % | 0.5 | 3 |
| 24000 | ui_rec_AD | 1.52 % | 2.19 % | -0.05 % | 0.48 % | 0.1 | 3 |
| 24000 | taxcut_rec_AD | 0.09 % | 0.13 % | +0.02 % | 0.02 % | 1.0 | 3 |
| 96000 | check_rec | 0.08 % | 0.06 % | -0.00 % | 0.01 % | 0.0 | 3 |
| 96000 | ui_rec | 0.39 % | 0.55 % | +0.04 % | 0.15 % | 0.3 | 3 |
| 96000 | taxcut_rec | 0.01 % | 0.02 % | -0.01 % | 0.00 % | 2.7 | 3 |
| 96000 | check_rec_AD | 0.11 % | 0.09 % | -0.00 % | 0.01 % | 0.2 | 3 |
| 96000 | ui_rec_AD | 0.56 % | 0.61 % | +0.10 % | 0.08 % | 1.3 | 3 |
| 96000 | taxcut_rec_AD | 0.01 % | 0.01 % | -0.01 % | 0.01 % | 1.7 | 3 |

### Verdict
- check_rec: top rung N=96000 diff -0.00 % ± 0.01 % (z 0.0); |diff| along the ladder 0.16 % → 0.00 % → 0.04 % → 0.00 % — PASS (within 2 SE at the top)
- ui_rec: top rung N=96000 diff +0.04 % ± 0.15 % (z 0.3); |diff| along the ladder 7.43 % → 0.27 % → 0.05 % → 0.04 % — PASS (within 2 SE at the top)
- taxcut_rec: top rung N=96000 diff -0.01 % ± 0.00 % (z 2.7); |diff| along the ladder 0.07 % → 0.02 % → 0.02 % → 0.01 % — PASS (below the 0.05 % reporting-precision floor at the top)
- check_rec_AD: top rung N=96000 diff -0.00 % ± 0.01 % (z 0.2); |diff| along the ladder 0.05 % → 0.01 % → 0.01 % → 0.00 % — PASS (within 2 SE at the top)
- ui_rec_AD: top rung N=96000 diff +0.10 % ± 0.08 % (z 1.3); |diff| along the ladder 3.76 % → 0.16 % → 0.05 % → 0.10 % — PASS (within 2 SE at the top)
- taxcut_rec_AD: top rung N=96000 diff -0.01 % ± 0.01 % (z 1.7); |diff| along the ladder 0.31 % → 0.00 % → 0.02 % → 0.01 % — PASS (within 2 SE at the top)

**hsonly: CERTIFIABLE — the paired difference is inside its SE at the top rung and does not grow**

## baseline_ew: Baseline, sharing + EQUAL-weight panel (the separating rung)

| N | cell | plainM per-seed SD | pstratM per-seed SD | paired diff | paired SE | z | S |
|---|---|---|---|---|---|---|---|
| 100000 | check_rec | 0.07 % | 0.08 % | +0.04 % | 0.02 % | 2.6 | 6 |
| 100000 | ui_rec | 1.01 % | 0.62 % | +0.69 % | 0.20 % | 3.5 | 6 |
| 100000 | taxcut_rec | 0.02 % | 0.01 % | -0.01 % | 0.01 % | 1.3 | 6 |
| 100000 | check_rec_AD | 0.10 % | 0.10 % | +0.03 % | 0.01 % | 2.9 | 6 |
| 100000 | ui_rec_AD | 1.15 % | 0.70 % | +0.71 % | 0.25 % | 2.9 | 6 |
| 100000 | taxcut_rec_AD | 0.02 % | 0.02 % | -0.01 % | 0.01 % | 0.9 | 6 |

### Verdict
- check_rec: top rung N=100000 diff +0.04 % ± 0.02 % (z 2.6); |diff| along the ladder 0.04 % — PASS (below the 0.05 % reporting-precision floor at the top)
- ui_rec: top rung N=100000 diff +0.69 % ± 0.20 % (z 3.5); |diff| along the ladder 0.69 % — FAIL (OUTSIDE 2 SE and above the 0.05 % floor at the top)
- taxcut_rec: top rung N=100000 diff -0.01 % ± 0.01 % (z 1.3); |diff| along the ladder 0.01 % — PASS (within 2 SE at the top)
- check_rec_AD: top rung N=100000 diff +0.03 % ± 0.01 % (z 2.9); |diff| along the ladder 0.03 % — PASS (below the 0.05 % reporting-precision floor at the top)
- ui_rec_AD: top rung N=100000 diff +0.71 % ± 0.25 % (z 2.9); |diff| along the ladder 0.71 % — FAIL (OUTSIDE 2 SE and above the 0.05 % floor at the top)
- taxcut_rec_AD: top rung N=100000 diff -0.01 % ± 0.01 % (z 0.9); |diff| along the ladder 0.01 % — PASS (within 2 SE at the top)

**baseline_ew: NOT certifiable on this ladder — see the failing cells**

## baseline_wo: Baseline, OWN AD loop + weighted-tail panel (the 2x2's fourth cell)

| N | cell | plainM per-seed SD | pstratM per-seed SD | paired diff | paired SE | z | S |
|---|---|---|---|---|---|---|---|
| 40000 | check_rec | 0.10 % | 0.07 % | +0.01 % | 0.02 % | 0.3 | 6 |
| 40000 | ui_rec | 0.85 % | 0.46 % | +1.34 % | 0.34 % | 3.9 | 6 |
| 40000 | taxcut_rec | 0.01 % | 0.01 % | -0.01 % | 0.01 % | 2.2 | 6 |
| 40000 | check_rec_AD | 0.21 % | 0.21 % | +0.02 % | 0.02 % | 0.9 | 6 |
| 40000 | ui_rec_AD | 0.64 % | 0.36 % | +1.30 % | 0.27 % | 4.8 | 6 |
| 40000 | taxcut_rec_AD | 0.03 % | 0.03 % | -0.01 % | 0.01 % | 1.1 | 6 |

### Verdict
- check_rec: top rung N=40000 diff +0.01 % ± 0.02 % (z 0.3); |diff| along the ladder 0.01 % — PASS (within 2 SE at the top)
- ui_rec: top rung N=40000 diff +1.34 % ± 0.34 % (z 3.9); |diff| along the ladder 1.34 % — FAIL (OUTSIDE 2 SE and above the 0.05 % floor at the top)
- taxcut_rec: top rung N=40000 diff -0.01 % ± 0.01 % (z 2.2); |diff| along the ladder 0.01 % — PASS (below the 0.05 % reporting-precision floor at the top)
- check_rec_AD: top rung N=40000 diff +0.02 % ± 0.02 % (z 0.9); |diff| along the ladder 0.02 % — PASS (within 2 SE at the top)
- ui_rec_AD: top rung N=40000 diff +1.30 % ± 0.27 % (z 4.8); |diff| along the ladder 1.30 % — FAIL (OUTSIDE 2 SE and above the 0.05 % floor at the top)
- taxcut_rec_AD: top rung N=40000 diff -0.01 % ± 0.01 % (z 1.1); |diff| along the ladder 0.01 % — PASS (within 2 SE at the top)

**baseline_wo: NOT certifiable on this ladder — see the failing cells**
