# ssj_ladder — the gated ladder for the HANK block

The executable form of `plans/20260901-2010h_ssj-gated-ladder_plan.md`: HARK mechanisms start
OFF and turn on one rung at a time, each behind measured gates, from minimal two-state cells up
to the full production construction and its GE. Status 2026-09-02: **every phase green.**

| phase | what | verdict |
|---|---|---|
| A0 | minimal 2-state household, step4 vs the `sequence_jacobian` reference twin | 199/0 |
| A1 | the real 6-state SAM chain, per-state income, UI instruments, eta by chain-dY | 300/0 |
| A2 | uniform growth: the two aggregation conventions — (W) the production p-weighted survivor-weight measure vs (P) plain per-capita — DISCRIMINATED (cash ratio = Γ at 1e-10) | 170/0 |
| A3 | production ψ/θ (permanent/transitory) risk — S-only, i.e. gated on the step4 engine alone: the `sequence_jacobian` twin has no such feature ("the SSJ wall"); β must respect the cell's own GIC — see the record | 82/0 |
| A4 | mortality ON — past the SSJ wall, so S-only; κ = ℒΓ cash gate exact; finite-difference reference values ("FD oracle") + survivor-weight unit tests | 94/0 |
| A5 | heterogeneity: the budget identity at the cap atom (the highest-β discount-factor mass point) + the weighted-aggregation identity (1e-12) | pass |
| A6 | production semantics: kernels via B9; one education-group Jacobian block spot-checked against the reference build (byte-identical) | pass |
| A7 | G14 measured + RECLASSIFIED: the overlay is the PE-faithful convention (the 1.8% non-shrinking residual belonged to the unfaithful benchmark and VANISHES when the newborn endowment scales with income — 4.8e-3 at n=450, refining); the splurge-independent residual is the HANK newborn-endowment convention (`HAFISCAL_HANK_NEWBORN_M=income` = the PE-faithful candidate) | PASS |
| B0–B10 | from the published configuration up to production, one mechanism per rung; the last rung's output must equal the production goldens to 6 decimals | 13/13 |
| C1–C6 | the GE gates (expansions below) | 16/16 |

Verdict column = checks passed / checks failed ("pass" = a single-verdict rung). "Goldens" =
the pinned reference values the regression tests compare against.

**Gate-name expansions (Phase C and friends):** G11 — the aggregate-demand-off wiring residual
(with AD off, C and A must come solely from the household Jacobians); G-IKC — the
intertemporal-Keynesian-cross reconstruction (a package-free closed form must reproduce the GE
dump); G-UJAC — a spot identity on the unemployment-block Jacobian; G-ETA — the η
(UI-financing payroll-tax instrument) column checked against the chain-implied dY; G-WAL —
Walras'-law residual; G-BB — the balanced-budget (ς = 1, fixed-real) identity; G-KP — the
κ_p = 0 limit (Taylor must collapse onto fixed-real) plus the κ_p dial; G-COND — conditioning:
σ_min of the GE system matrix H_U at the production φ_π; G-PHIB — the φ_b (debt-rule) sweep
with its stability assert; G-TRUNC — truncation-horizon sensitivity from one long build; G14 —
whether the splurge OVERLAY is equivalent to structurally-splurged preferences; D4/G8 — the
7→6 state lumping and the experiment layer's dated paths; G-SPL — splurge-overlay consistency.

## Running

```bash
cd Code/HA-Models
# Phase A rungs (env pinned inside; verdict JSON per run):
python -m ssj_ladder.run_rung A0|A1|A2|A3|A4 [--quick] [--out DIR]
python -m ssj_ladder.rung_a56 --out DIR          # A5 + A6
python -m ssj_ladder.rung_a7 --out DIR [--quick] # G14: overlay vs structural splurge
# Phase B chain (hermetic env per rung, cascade-halt, resume-aware):
python -m ssj_ladder.phase_b --chain --dir rerun_logs/phase_b_<date>
# Phase C gates (all runs to scratch; dump-reuse on rerun):
python -m ssj_ladder.phase_c --dir rerun_logs/phase_c_<date>
# The G8 experiment-layer gate (both halves), on any production MULT_DUMP:
python -m ssj_ladder.gate_g8 --dump <dump.pkl> --ss <ss.pkl>
python -m ssj_ladder.gate_g8_lumpability [--json out.json]  # D4 lumping on the experiment chains
# The A2 twin ℒΓ-bridge (units conversion between the two engines' books; broad columns gated):
python -m ssj_ladder.rung_a2_bridge [--out DIR] [--gamma G --beta B]
# The PE-reproduction gate (the owner's rule — "the baseline HANK with multiplier mechanisms
# turned off should reproduce the partial-equilibrium model" — as a measurement):
python -m ssj_ladder.pe_reproduction ...
```

## Modules

- `rungs.py` — the Phase-A registry: pinned specs, per-rung thresholds (every tier carries its
  measured basis inline), env pins.
- `run_rung.py` — Phase-A runner: owns argv (BUG-114), pins env BEFORE the first step4 import,
  writes verdict JSONs; carries the A2 discrimination flow, the A4 ℒΓ gates, the η-vs-chain-dY
  gate (chain side scaled by κ = ℒΓ), and the probe of whether the twin's transition matrix Π
  can be shocked directly (it cannot, natively).
- `minimal_cell.py` / `reference_ssj.py` — the step4 cell (untouched per-cell API) and the
  external `sequence_jacobian` twin, per rung family.
- `phase_b.py` — the B0–B10 registry + driver. Each rung runs with a fully controlled
  environment: every variable in the managed list is either set to the rung's own value or
  explicitly unset, so nothing is inherited from the shell ("hermetic env"). Scratch-only
  outputs; flow-budget tolerances set at 3× the residual measured on a known-good build, so
  they fire on a structural change rather than numerical noise; the gate that the published
  pickle's rows s ≥ 1 must be reproduced; B4's transitional ceiling for the plain (bst)
  transition kernel; B9's exit requirement that its output equal the production numbers
  exactly.
- `phase_c.py` — the GE gates on the production obj; every run through `run_ge_scratch`.
- `closed_form.py` — the fixed-real GE reconstruction with no `sequence_jacobian` dependency
  (numpy only) + the unemployment-Jacobian spot identity + the η-vs-chain-dY arithmetic.
- `budget_suite.py` — the full-model per-input flow-budget suite + the by-educ identity.
- `build_obj.py` / `run_ge_scratch.py` — children that build Jacobian objs / run the GE against
  arbitrary objs WITHOUT touching the tracked paths (the ladder never writes
  `FromPandemicCode/HA_Fiscal_Jacs.obj` or the Results_HANK pickle).
- `gate_g8_lumpability.py` — the D4 state-lumping (PE 7 micro states onto the HANK's 6) tested
  on EVERY experiment chain: the transition side lumps exactly (0) everywhere; the one place
  the UI experiment's PAY pattern cannot be represented on 6 states is exactly the set of
  quarters the window policy itself pays the deepest extension state — pinned as a prediction
  the gate trips on if that ever changes. Suite wrapper `step4/test_g8_lumpability.py`.
- `rung_a2_bridge.py` — the A2 units-conversion bridge J_W = ℒΓ·D J_P D⁻¹: after converting,
  the broad income columns (transfers/w/tau) agree within A1's Γ=1 discretization band (gated).
  The UI columns cannot agree: the twin's asset response to UI is identically zero (its
  recipients sit at the borrowing constraint, while the production measure keeps
  newborn-reinjected cash there), so the rung only asserts that this zero persists — if it ever
  stops being zero, the recorded diagnosis is stale and the rung fails. Agreement there would
  need birth/death machinery added inside the sequence_jacobian package itself; the measured
  boundary is in the module docstring. Validation-only either way — nothing consumes the twin.
- `rung_a56.py`, `gate_g8.py`, `pe_reproduction.py`, `gates.py`, `test_rung_a0.py`.

## Conventions worth knowing before extending

1. **Env before import**: `hh_setup` reads `HAFISCAL_HANK_BIGT` (and friends) at module load;
   every entry point pins env first and refuses otherwise.
2. **Own argv**: `Parameters.return_parameters` parses `sys.argv` positionally on every call
   (BUG-114) — set `sys.argv = [argv0]` before anything imports it.
3. **Impatience is per-CELL**: a rung's β must satisfy the growth-impatience condition under the
   rung's own Γ and risk (A2 re-pinned β for Γ<1; A3's first spec at A1's β piled wealth on the
   grid top and broke the SS identity by 10% — the machinery was innocent).
4. **The (W) measure convention** (verified in `ConsMarkovModel` ~1824): ρ = R·ℒ Γ-free, delivery
   κ = ℒΓ, newborns keep the destination state. The A2/A4 derived-cash gates pin it.
5. **Thresholds carry their measured basis**: tolerances are 1.5× (Phase A) or 3× (Phase B)
   the residual measured on a known-good build — at 3× a gate is a change-detector
   ("tripwire"), firing on a structural break rather than numerical noise — with the
   measurement cited inline. Columns with tiny cash flows have small maximum Jacobian entries,
   so a given absolute error is a large relative one: hence a separate tolerance per input, not
   one global tolerance.
6. **Bit-for-bit comparisons are valid within a single process only**: the GE's ergodic ARPACK
   eigensolve starts from a random vector (~1.5e-11 multiplier jitter across runs).
7. **Scratch discipline**: tracked artifacts are never written by ladder runs — and diagnostics
   count (BUG-117: `hank_diagnose`'s loader-side materialize needed a restore-on-exit guard).
