# Phase 2 agent briefs — the queued consolidations (sweep table §4), 2026-09-03 overnight

You are one agent executing ONE item below, in your own git worktree of HAFiscal-Latest. The owner is
asleep; nothing you do is reviewed before morning, so the gate is the review. Read
`conclusions_private/2026-09-02_dual-path-sweep_table.md` §4 for your row's full context first.

## Contract (every item)
1. **Scope = your row only.** Touch the sites the row names; nothing else. No new code under
   `Code/HA-Models/FromPandemicCode/` (new helpers go in `Code/HA-Models/`). Descriptive names; a
   comment at the point of use saying WHY (link the sweep table + this brief's date).
2. **Never** edit a file listed in `LOCKED_TABLES.manifest`; never re-pin a golden/test pin; never flip
   a default or an env-flag default; never change a number in a record.
3. **Gate before you claim.** Run the gate for your tier (below). PASS = deliver. FAIL = deliver the
   failure (which files/values differ, max numeric delta) — do NOT weaken the gate or "fix" the
   comparison. A failed gate is a valid deliverable.
4. **Deliver three things** into `/tmp/claude-1000/-home-shared-github-llorracc-HAFiscal-Latest/f91dfb72-4520-415e-95d4-8c433281596b/scratchpad/phase2/`:
   `Q<n>.patch` (`git diff` of your worktree vs its base), `Q<n>.gate.log` (the exact gate commands +
   output), `Q<n>.report.md` (≤ 25 lines: what changed, gate verdict, any doubt). Your final message =
   the report's contents.

## Gates by tier
- **SAFE** (docs / gates / latent-path imports): the module's own test file passes
  (`.venv/bin/python -m pytest <tests> -q -p no:cacheprovider -o addopts=""`) and, where you ADD a gate,
  it passes on the untouched tree and would fail if the guarded equality were broken (show that with a
  one-line deliberate break, then revert it).
- **PARITY-GATED** (bitwise-identical refactor): on the UNTOUCHED worktree, run the smallest production
  entry that exercises the touched code and sha256 every output it writes; apply your change; run again;
  every hash identical = PASS. Entries: `tm_methods`/`AggFiscalModel`/`Simulate` →
  `cd Code/HA-Models/FromPandemicCode && HAFISCAL_TM_A_INDEXED=1 HAFISCAL_POLICY_STORE=0 .venv/bin/python
  AggFiscalMAIN_reduced.py --baseline` at the HS_Only parametrization (see `Parameters.py`; pass it the
  way `test_tm_baseline.py` does); welfare kernels → `welfare6_scenario.py --scenario base` HS_Only;
  `step4/` → `pytest Code/HA-Models/step4/ -q` plus the ladder gate the row names (`ssj_ladder/`);
  estimation-side sites → `test_step1*.py` / the Step-2 unit tests only (no re-estimation).
  Also run `pytest Code/HA-Models/solution_cache/ -q` if you touched anything the store hashes
  (`solver_source_hash` covers AggFiscalModel function bodies — a refactor there CHANGES the hash; say so).
- **MEASUREMENT** (Q1 only): produce the before/after numbers; adopt nothing.

## Items
| id | tier | object / sites | action | notes |
|---|---|---|---|---|
| Q7 | SAFE | `HAFISCAL_TM_MCOUNT` has six unset defaults (50 hank/tm, 100 welfare, 200 hybrid/bench) | ENV_FLAGS.md registry row naming each engine's DECIDED default; propose per-engine names in the row, change no code | doc-first; `test_key_completeness.py` must still pass |
| Q9 | SAFE | gate literals `budget_suite.RHO_LIVPRB`, `EDUC_SHARES` copies in `ssj_ladder/` | import from `hh_setup`/`EstimParameters`; `closed_form.py` stays package-free BY DESIGN — add a parity assertion instead | gate-layer: re-run the affected ladder gates |
| Q10 | SAFE | `hark_fti.markov_pf_seed` re-derives PF limits (licence-tier duplicate, permanent) | a PARITY GATE test: `MPCmin` there ≡ `compute_pf_decay_limits`' | `hark_fti` is the external opt-in package (`_hark_fti_path.py`); skip with a note if it does not resolve |
| Q11 | SAFE | dashboards/tutorial NPV denominators hardcode 300 (`dashboard/*`, `HANK_and_SAM_tutorial_utils`) | follow `bigT`; extend the BUG-109 scan beyond `ge.py` | teaching surfaces, not results-bearing |
| Q14 | SAFE | `IncUnempNoBenefits` re-literalized in `Parameters.py:83` | import from `EstimParameters` | latent argv route; `test_*parameters*` |
| Q18 | SAFE | `jax_mc_minimal.py` two splurge spellings (pLvl_prev·G·ψ·ξ vs pLvl_now·ξ) | verify the algebra (write it out), unify if identical, else REPORT the discrepancy | opt-in kernel |
| Q20 | SAFE | JAX-2B tail-attach gating hand-copied from the PE attach (stale line refs) | a parity gate binding the two policies | opt-in kernel |
| Q4 | PARITY | `tm_methods._build_period_tm_a_tail` = copy of `_build_period_tm_a` + redirect | delegate to one body | goldens-bearing a-kernel |
| Q15 | PARITY | `AggFiscalModel` realized-income twin blocks (:1046 vs :1339, ~35 lines) | extract one helper | MC sim path; note the solver-source hash if it moves |
| Q19 | PARITY | `make_assets_grid` triplication; `hh_setup` dist-grid fallback retypes; two dist-top defaults in `tm_methods` (a: 500/AMAX, m: 50) | consolidate onto `grid_sizing`/`adaptive_grid_tm` | frozen grid plumbing |
| Q2 | PARITY | chain builders duplicated `Parameters.py:496-565` vs `EstimParameters.py:451-484` (7 vs 4 states) | route Parameters' four onto EstimParameters with the length parameter | G8-lumpability (`ssj_ladder/gate_g8_lumpability.py`) proves the base chains lump exactly — run it |
| Q5 | PARITY | ergodic-eig idiom in 8+ copies incl. element-wise `np.abs` sign hazard (`tm_methods.py:335/745/1056`) | route onto `find_ergodic_distribution`/`growing_block_ergodic`; fix the abs spelling | many callers — hash every touched engine's outputs |
| Q6 | PARITY | `step4/jacobians.py:847/858/870` divide by n instead of `pmv` | use `pmv` + a non-uniform guard | identical today (equiprobable atoms) — the gate must show it |
| Q8 | PARITY | benefit levels 0.7/0.5 as four literal sets in `step4` (hh_setup, ge fiscal, mkt_clearing, fiscal_tau_star) | one constants import from `EstimParameters` | `pe_anchor_gate` guards the household copy; hash the fiscal outputs |
| Q21 | PARITY | tax_cost writes literal `1.0` for `wage_ss` (ge.py + monolith + dashboards); `gate_g8` asserts magnitude only for transfers | write `wage_ss`; extend `gate_g8` to all three magnitudes | benign at wage_ss=1.0 — prove it |
| Q13 | PARITY | two multiplier families share a name (`NPV_Multiplier_*` vs `C_Multiplier_*`) + the "10y-horizon" label reports `[-1]` of act_T | rename in `Output_Results` + relabel | regenerated tables go to `_candidate` siblings ONLY (the freeze guard); nothing promoted |
| Q17 | PARITY | splurge consumption-rule kernel ~20 inline copies | THIS NIGHT: the `tm_methods` (×6+4) + welfare (×7) copies onto one helper; JAX/estimation copies stay queued (say so) | bulk — hash every touched engine |
| Q1 | MEASUREMENT | vendored HANK solver tail exponent: `ConsMarkovModel.py:790/:813` omit `decay_extrap_Q`; PE passes the measured Q | pass the measured Q; regenerate the HANK candidates (Step 4 only: `HAFISCAL_RUN_STEP_{1,2,5}=false`); REPORT each h20 multiplier before/after and the `pe_anchor` EXPECTED row | expected 0.15–0.4 %; NOT adopted, goldens NOT re-pinned, pins untouched |
| Q3 | DEFER | Step-1 TM kernel written twice | — | belongs to the Step-1 TM-a plan (BUG-063) |
| Q16 | DEFER | GIC-cap double-clip / logit copies / `_regime` fingerprint | comment half only if trivially safe | estimation-side measured pass is the owner's call |
