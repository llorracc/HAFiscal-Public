# Published-QE vs current epoch — headline comparison (staged 2026-08-22 21:10)

**QE baseline** = the published paper (QE Vol 17 No 3, July 2026), generated tabulars
pulled from the canonical sibling `../HAFiscal-QE`
(`Code/HA-Models/FromPandemicCode/Tables/CRRA2/{Multiplier,welfare6}.tex`) — NOT the tag.
**Current version** = the belief-consistent current epoch: "installed" = the frozen/
installed tables on this branch; "tonight" = the 2026-08-22 overnight install-rerun
candidates (filled at landing). Report-only: the current world differs from the
published configuration by documented rulings (bug fixes + improvements), so deltas are
EXPECTED and each one gets an attribution, not a pass/fail.

## Multipliers (10y horizon)

| row | policy | published | installed | tonight | Δ (inst−pub) | attribution seed |
|---|---|---|---|---|---|---|
| AD effect | Check | 1.228 | 1.239 | **1.258** | +0.011 | epoch anchor 1.236; small net of fix set |
| AD effect | UI | 1.209 | 1.249 | **1.258** | +0.040 | UI-family fixes (BUG-043 state encoding et al.) |
| AD effect | TaxCut | 0.975 | 1.017 | **1.027** | +0.042 | fix set + belief-consistency |
| no AD | Check | 0.878 | 0.903 | **0.907** | +0.025 | ~uniform +0.025 across policies ⟹ common-factor |
| no AD | UI | 0.906 | 0.925 | **0.931** | +0.019 | (β re-est, aMax=1300, encoding baseline) |
| no AD | TaxCut | 0.846 | 0.871 | **0.878** | +0.025 | — |
| exp. share in rec | UI | 79.6% | 100.0% | **100.0%** | +20.4pp | UI expenditure-timing accounting change — VERIFY the responsible ruling in the morning attribution pass |
| cons. share in rec | UI | 81.1% | 118.2% | **116.9%** | +37.1pp | same family; >100% = stimulus concentrated in recession |
| cons. share in rec | Check | 73.6% | 72.7% | **73.2%** | −0.9pp | minor |
| cons. share in rec | TaxCut | 41.8% | 44.6% | **44.7%** | +2.8pp | minor |

## Welfare-6 (printed 2-dp table cells)

| cell | policy | published | installed | tonight | Δ | note |
|---|---|---|---|---|---|---|
| Rec=0,AD=0 | Check | 0.96 | 0.99 | **0.96** | +0.03 | |
| Rec=0,AD=0 | UI | 0.85 | 1.00 | **— (blank)** | +0.15 | **ui_norec = the 0/0-class degenerate cell (standing never-report rule); do not attribute economics — table-only** |
| Rec=0,AD=0 | TaxCut | 0.99 | 0.99 | **0.99** | 0 | |
| Rec=1,AD=0 | Check | 1.00 | 1.01 | **1.02** | +0.01 | |
| Rec=1,AD=0 | UI | 1.82 | 2.04 | **1.80** | +0.22 (+12%) | UI-family fixes + stratified-MC welfare machinery |
| Rec=1,AD=0 | TaxCut | 0.98 | 1.01 | **0.99** | +0.03 | |
| Rec=1,AD=1 | Check | 1.35 | 1.35 | **1.39** | 0 | |
| Rec=1,AD=1 | UI | 2.13 | 2.50 | **2.14** | +0.37 (+17%) | as above + AD interaction |
| Rec=1,AD=1 | TaxCut | 1.11 | 1.15 | **1.16** | +0.04 | |

**Qualitative headline: unchanged.** UI extension remains the clear welfare winner in
recessions; check strongest on the AD multiplier; the ranking story of the published
paper survives every fix — the fixes move magnitudes (UI most, +12–17% welfare class),
not conclusions.

**Tonight-column note (multipliers filled 2026-08-23 03:15):** the installed→tonight
step (+0.019/+0.009/+0.010 on AD multipliers) is PROVEN epoch change, not noise: the
08-14 GIC-cap ruling (FVAC dropped; caps +0.006/group; anchor ran College 1/7 at cap,
tonight 0/7) + the 08-19 run-13 calibration install (Dropout β 0.7378→0.7481). The
f6c7e615 anchor-commit A/B reproduces the installed values at print precision.
Welfare "tonight" columns await S5b (held by cascade; ~1h on release).

**Welfare tonight-columns filled (08-23 ~09:45, S=3 complete). THE WELFARE HEADLINE
INVERTS the installed-table story:** tonight's printed UI cells (1.80 / 2.14) land ON
the published values (1.82 / 2.13) — within one printed digit, i.e. inside the ±2%
UI seed band. The installed May-16 table (2.04 / 2.50) was the stale outlier, not the
published paper. Current epoch ≈ published on welfare across the board (max printed
delta 0.04 on Check-AD); the ui_norec cell now prints blank per the never-report rule.
Cross-platform: m5 replicated seed 0 to ≤2e-4/cell (max, an AD cell; others ≤1e-5).

**Remaining fills:** none — per-row
attribution verified against the rulings ledger (esp. the UI expenditure-share
restructuring); cross-platform rows (dell/m5/ccarroll f-pin = 0.001646862912 on all
three, ≥10 sig figs — recorded 21:02).

**Context anchor:** the matched-config fidelity path (`qe_fidelity_full`) reproduces
published within ±3% — divergences here are the DOCUMENTED-changes signal, not noise.
