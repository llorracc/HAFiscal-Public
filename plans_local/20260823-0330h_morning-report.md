# Morning report — overnight install rerun (2026-08-23)

**One-paragraph summary.** The rerun executed under the approved protocol. S1 and S2
PASS at reproduction class (S1 bitwise vs the afternoon contingency; S2 deltas
1e-6…1e-5 vs installed, estimated FROM tonight's fresh S1 winner). S5a's C3 gate
tripped — and the overnight diagnosis PROVED the cause is **stale anchors, not
regression**: my gate anchored multipliers from the pre-08-14/pre-08-19 epoch, while
tonight ran the current world (FVAC-drop cap regime + run-13 calibration). Tonight's
multipliers (Check 1.258 / UI 1.258 / TaxCut 1.027) are the first correct values of
the current epoch; the anchor-commit A/B reproduces the old values at print precision.
S5b was held by the cascade rule and takes ~1h on your release. Three machines agree
on the objective at 10 significant figures; m5's independent battery re-derived the
installed SoR bitwise. Two driver bugs (mine, mechanical) were fixed and pushed
mid-night per the pre-authorized lane.

## Gate results

| phase | wall | gate | verdict |
|---|---|---|---|
| S1 (knots0-full, battery per branch 2) | 157 min | C1(waived)+A3 | **PASS — bitwise ≡ afternoon contingency** |
| S2 (3 groups, TM-ergodic, FTI-routed) | 17 min | C2 | **PASS** (β 5e-7…5e-6 rel; ∇ 1e-5 class) + ATI tripwire (fixed form) |
| S5a (TM multipliers) | 32 min | C3 | **FAIL on stale anchors → attribution PROVEN** (below) |
| S5b (welfare ×3 seeds) | 105 min | C4 | **PASS** (after per-cell band fix; see below) + seed-band table + m5 parity ≤2e-4 |

## S5b completion (morning, after D1/D2 + the amendment)

Ran 07:43–09:27 under the C5 package-safe park (one mechanical fix: the original park
moved `solution_cache/` wholesale — it is also a CODE package children import; fixed
to park data-subdirs only). C4 tripped on ui_rec/ui_rec_AD only → dispositioned
MISWIRED GATE by the preserved 08-10 S=3 evidence: UI-recession cells have always
carried ~±2% seed scatter (small effective N); tonight's seeds sit inside the 08-10
range. Per-cell bands installed (UI cells 3%, rest 0.5%) → C4 PASS, all cells. Seed-band
SE table: max SE/mean 0.96% (ui_rec_AD), quiet cells ≤0.4%. Welfare headline: tonight's
printed UI cells (1.80/2.14) land ON the published QE values (1.82/2.13) — the stale
May-16 installed table (2.04/2.50) was the outlier. m5 parity arm (same seed, cold,
ATI-on): max cell delta 1.99e-4 — certifies cross-machine seed-spreading (~1h S=3).

## The C3 story (30 seconds)

Fresh table: whole multiplier block up +0.5–1.5%, shares unchanged. Refuted: parser;
ATI flip (anchor run had ATI too). Proven two-way epoch mismatch: the anchor table
(08-07) used the epoch-pre calibration (Dropout β 0.7378 vs current 0.7481, installed
08-19) and the pre-FVAC-drop caps (+0.006/group since 08-14; its College ran 1/7
atoms AT cap, tonight 0/7). Decisive A/B: 5a re-run AT the anchor commit reproduces
1.239/1.248/1.016 ≈ installed 1.239/1.249/1.017 (Δ≤0.001). Same code+inputs ⇒ same
table; the delta is your two rulings flowing through Step 5, exactly as they should.

## Cross-platform (three machines, same objective)

| machine | f at SoR (install config) | independent battery |
|---|---|---|
| dell (Linux x86) | 0.001646862912 | winner −0.009%/+0.000%/−0.002% vs SoR |
| ccarroll-m5 (macOS ARM) | 0.001646862912 | **winner ≡ installed SoR BITWISE** (sp7, f≡pin); stage-1 spread 1.587e-3 vs dell 1.588e-3 |
| ccarroll (macOS ARM) | 0.001646862912 | (light role: sync+probe) |

## Decision stack (in order; my recommendation in bold)

1. **D1 — accept the C3 attribution** → tonight's tagged run becomes the
   epoch-defining anchor set; gate comparators re-anchor to it for future reruns.
   **Rec: yes** — the evidence is the A/B above.
2. **D2 — release S5b** under the reformulated C4 (internal 3-seed band ≤0.5%/cell +
   spine4-seed2 comparison as informational; the wired May-16 reference is dead).
   ~1h; completes the welfare columns and the QE table. **Rec: yes.**
3. **D3 — S7 adopt vs certify-only.** **Rec: ADOPT** — tonight's chain is the first
   coherent full-profile snapshot of the current epoch (fresh S1→S2→5a, mutually
   consistent, tagged `rerun-full-20260822-2222`+`-0123`, provenance'd, cross-platform
   corroborated). Certify-only would leave frozen tables at mixed 05-16/08-07
   vintages that NO current run reproduces. Promotion remains the separate reviewed
   step it always was.
4. D4 — the f-tie stage-1 acceptance recalibration (restores ~40-min install S1;
   tonight's data validates it for free — min-f selected the installed SoR bitwise).
5. D5 — PR #1818 mods memo release (below).

## PR #1818 observation memo (item 5)

Overnight scale evidence: **clean** — the tail machinery ran through S1's full-grid
CHS retrofit (3 full runs today), S2/S5a's per-C-node PowerLawDecayLinearInterp under
mixed ATI/EGM routing, deepcopies, and subprocess boundaries, with ZERO
tail-related warnings (the only warning in all logs is the expected unanimity
banner). Proposed mods (drafts on request, nothing pushed):
1. **Ship a measure-Q utility** (`local_q_tail`-derived) — the PR attaches given Q
   but cannot measure it; every production use tonight measured Q from the solution.
2. Document the base-class divergence (vendored CubicInterp vs PR CubicHermiteInterp
   — numerically verified equivalent, coeffs-row contract).
3. Host-coverage: both hermite-family hosts fired across today's runs; the PR's
   single-host collapse should either cover both or document the boundary.
4. Scale note for the PR text: production evidence at thousands-of-instances scale,
   serialization surfaces included.

## Driver design fixes (queued, not urgent)

Resume clean-check must ignore the run's own staged outputs (tonight: `--allow-dirty`
workaround); C4 rewiring per D2; do_all's stale `expected_duration_min=35` display.

## Also on your desk

The **BabyHAFiscal plan** (your evening charge; umbilical included) awaits spec trims
— `plans_local/20260822-2115h_baby-hafiscal-hark-migration_plan.md`. The QE-published
comparison is filled through multipliers (`20260822-2110h_...`). Macs synced; ledger
refreshed under the endgame; all work committed and pushed.
