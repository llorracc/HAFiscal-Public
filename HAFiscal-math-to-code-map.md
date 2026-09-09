# HAFiscal: the mathematical model and its computational instantiation — the map

**Purpose.** One document that (i) states the complete mathematical structure
of the HAFiscal model in a single rigorous pass, and (ii) maps every
mathematical object to the code object that instantiates it — file, function,
line — together with the discretization it uses and the *equivalence class*
of every performance layer sitting between the math and the numbers in the
paper. The intended reader is an inspector who wants to verify that the code
computes the stated model: every symbol below resolves to code, and every
code shortcut resolves to a certification.

**Reading order for a full inspection.**
1. This document (the map).
2. `HAFiscal-bellman-for-matsya.md` — the household stage in full rigor
   (perches, connector, normalization, Euler).
3. `HAFiscal-doloplus-orchestrator.md` — the normative out-of-YAML layer
   (interpretations, splurge accounting, AD loop pseudo-code, macro-state
   machinery, cohort sweep, demographics, measure, outputs) with per-section
   code anchors and a verified-constants index.
4. `MODEL_INTERPRETATIONS.md` — CDC vs ESC: two accounting conventions for
   the same model (read before flagging any splurge "inconsistency").
5. `HAFiscal-doloplus-draft.yaml` — the canonical DDSL encoding of the
   optimizer stage alone.

Line numbers below were verified 2026-08-02 on branch
`0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_powerlaw-decay-extrap`; they
drift with edits, but every anchor also names the function, which is stable.

---

## 1. The model in one pass

### 1.1 The household stage (idiosyncratic layer)

Each of 21 household types — education $e\in\{d,h,c\}$ × 7 discount factors
$\beta_i$ per group — solves, in permanent-income-normalized form with CRRA
$u(c)=c^{1-\gamma}/(1-\gamma)$, $\gamma=2$:

$$
v(\check m, z)\;=\;\max_{\check c\,\ge 0}\;
u(\check c)\;+\;\beta_i(1-D)\,
\mathbb{E}\!\left[\hat\Gamma^{\,1-\gamma}\,
v\!\left(\tfrac{R}{\hat\Gamma}\check a+\check y(z',\xi'),\,z'\right)\right],
\qquad
\check a=\check m-\check c_{sp}-\check c \;\ge 0,
$$

with $\hat\Gamma=\psi\Gamma_e$, splurge $\check c_{sp}=\varsigma\,\check y$,
income map $\check y(E,\xi)=\xi$, $\check y(U_k)=\rho_b$,
$\check y(X)=\rho_{nb}$, and the employment/UI Markov chain $z$ over
$\{E,U_1..U_{T_{UI}},X\}$. The full statement — timing, connector
$\mathcal{J}_t$, mortality/rebirth, Euler equation — is
`HAFiscal-bellman-for-matsya.md` §2–§8. The splurge sits in the budget (CDC)
or in a bonded side-ledger (ESC); the two are the same model up to a
$(1-\varsigma)$ homothetic rescaling (`MODEL_INTERPRETATIONS.md`; production
default is ESC).

| math object | code instantiation |
|---|---|
| type family $(\beta_i,e)$, 21 problems | `welfare6_scenario.build_and_solve` / `Simulate.py` construct 21 `AggFiscalType` agents; β grids from `EstimParameters.py` calibration files |
| micro Markov chain $z$, $\Pi^e$ | `AggFiscalModel.AggFiscalType.update_mrkv_array` (:1419) via `make_cond_mrkv_arrays_*` from `Parameters.py`; 6 micro states under the BUG-043 `bug_fix` UI encoding |
| income map $\check y(z,\xi)$ | `IncShkDstn` built manually per Markov state (`construct=False` pattern, `AggFiscalType.__init__`) |
| splurge $\varsigma$ | `Splurge` parameter; ESC ς=0.27035 installed (Step-1 deterministic engine); simulation split in `get_poststates` (ESC branch) / `_cdc_asset_rule` (:163) |
| EGM solution of the stage | `solve_agg_cons_markov_alt` (AggFiscalModel.py:1936) — see §1.2, its distinguishing feature |
| mortality $D$, perpetual youth | `LivPrb`; simulator rebirth in `sim_birth` (:542) replicating the 0.14.1 RNG sequence |

### 1.2 The C-conditional solution family (the key computational object)

The aggregate-demand externality makes idiosyncratic income depend on
aggregate consumption: transitory income is scaled by

$$
\mathrm{ADF}(C, \mathrm{rec}) \;=\; C^{\,\mathrm{rec}\cdot\eta},
\qquad \eta=\texttt{ADelasticity}=0.3,
$$

where $C$ is the ratio of aggregate consumption to its steady-state path and
$\mathrm{rec}\in\{0,1\}$ is the recession bit of the macro state
(`_ADFuncImpl.__call__`, AggFiscalModel.py:2302–2325: `C ** (RecState *
ADelasticity)`). Rather than re-solving the household problem for every
candidate aggregate path, the solver computes policies **conditional on
aggregate C as an argument**:

$$
\check c \;=\; \mathrm{cFunc}_j(\check m,\; C),
$$

one bivariate function per combined Markov state $j$. This is the object
everything downstream evaluates — simulation, transition-matrix methods, the
replay kernel's per-period tables.

**The solver's two-loop construction** (`solve_agg_cons_markov_alt`,
AggFiscalModel.py:2086–2270 — the mathematical heart):

- **Loop 1 (:2089–2123), conditional end-of-period marginal value.** For each
  *next* state $j$: tile the tensor over $(C_{grid} \times a_{grid} \times
  \text{shocks})$; scale next-period transitory income by
  $\mathrm{ADF}(C', \mathrm{rec}(j))$ (:2107–2108, where the recession bit is
  $\lfloor j/J\rfloor \bmod 2$); compute the natural borrowing constraint
  per $C'$ (:2111–2118) and $\check m'$ (:2123); integrate marginal value
  over the shock distribution to get
  $\mathbb{E}[\hat\Gamma^{-\gamma}v'_m \mid a, C', j]$ — a function of
  $(a, C')$ per next-state $j$.
- **Loop 2 (through :2270), composition under beliefs.** For each *current*
  state $i$: mix the conditional objects over $j$ with $\Pi_{ij}$, evaluating
  each at the **believed** next aggregate $C' = \mathrm{CFunc}[i][j](C)$
  (§1.3); invert the Euler equation on the endogenous grid (EGM); build
  $\mathrm{cFunc}_i(\cdot, C)$ as a `LowerEnvelope2D` of the unconstrained
  interpolant and the constraint plane $c = m - \underline{a}$ (:2150 —
  `cFuncCnst`), interpolated across the C-grid.

Discretizations: `Cgrid = CgridBase = [0.8, 1.0, 1.2]`
(`Parameters.py:419`; the certified band for realized C-ratios —
RECONCILED-001 covers the TM clip / MC assert at these bounds,
AggFiscalModel.py:3466); per-group solve grids `aXtraMax`/`aXtraCount` from
the K·h̄ rule (`[grid_sizing]` banner); shock quadrature from the manually
built `IncShkDstn`. Above the solve-grid top, cFuncs carry measured-Q
power-law decay tails (`HAFISCAL_PF_DECAY_*`, local_q_tail machinery at
:2280) — a fact with consequences for any serialization of the solution
(BUG-067).

### 1.3 Beliefs and the aggregate-demand fixed point

Agent beliefs about aggregate dynamics are affine rules per macro transition
$(i \to j)$:

$$
C'_{\text{believed}} \;=\; \mathrm{CFunc}[i][j](C)
\;=\; \alpha_{ij} + s_{ij}\,(C - 1),
$$

(`CRule.__call__`, AggFiscalModel.py:3509–3520 — "Not logs!"). The
**equilibrium concept** is a fixed point in these rules: solve the
C-conditional policies under the current rules, simulate the economy, observe
the realized aggregate path $C_t = \sum_i c_{i,t}\,/\,C^{base}_t$
(`mill_rule`, :2351/2377 — realized ratio against the stored baseline
`base_AggCons`), update the rule intercepts toward the observed path
(damped), and iterate to convergence (`solve_ad_*` methods; tolerance
`convergence_cutoff`, default profile in `welfare6_scenario`). At
convergence, beliefs are consistent with realizations along the experiment
path — a perfect-foresight-in-aggregates MIT equilibrium, per
`HAFiscal-bellman-for-matsya.md` §7.6 (households never integrate over future
aggregate states).

Timing subtlety (deliberately preserved): agents at $t$ evaluate
$\mathrm{cFunc}(\cdot, C)$ at the **previously sown** aggregate — mill_rule
at $t$ sows $\mathrm{CFunc}[s_{t-1}][s_t](C_t)$ for use at $t{+}1$, and the
$t{=}0$ intercept-init writes a dead key, so the live head is $C=1.0$
(BUG-066, materiality <1e-4, OPEN by owner ruling; the replay engine
reproduces this faithfully — `jax_mc_replay_ad.py` C-ARGUMENT comment).

| math object | code instantiation |
|---|---|
| $\mathrm{ADF}(C,\mathrm{rec})$ | `_ADFuncImpl` (:2302); refreshed on `restore_ADsolution` (:2670) |
| $\mathrm{CFunc}[i][j]$ | `CRule` (:3509); assembled by `calc_CFunc` (:2597); identity rules (α=1, s=0) outside AD experiments |
| realized $C_t$ | `mill_rule` (:2351): `Cratio = AggCons/base_AggCons[t]` (:2377) |
| fixed-point iteration | `solve_ad_recession` family (HARK path); replay-fed twin `Code/HA-Models/jax_mc_replay_ad.py` (hybrid default — §3) |
| baseline path $C^{base}_t$ | `store_baseline` (:2645) — the no-policy base run's `AggCons`; shared across children by the R3 `base_aggcons` cache (exact, byte-gated) |

### 1.4 The experiment layer: hierarchical Markov structure

Aggregate scenarios are encoded as a **hierarchical flat Markov state**:

$$
\text{Mrkv} \;=\; J\cdot\text{macro} + \text{micro},\qquad J=6,
$$

macro $\in \{0,\dots,2(T_{exp}{+}1)-1\}$ = (experiment-period clock) ×
(recession bit): the deterministic period-march chain with the recession bit
persisting with probability $1-1/R_{spell}$ ($R_{spell}=6$). Baseline: 1
macro state (6 combined); recession experiments: 42 macro (252 combined).
Policies (UI extension, tax cut, stimulus check) enter as state-dependent
modifications of the income process in the appropriate macro states —
`update_mrkv_array` / `switch_shock_type` swap in per-policy
`MrkvArray`/`IncShkDstn` (`AggFiscalModel.py:1268/2622`); the orchestrator
§5 gives the full clock/policy-delivery math.

A recession scenario's reported outcome integrates over recession **duration**
$d$ with the geometric weights
$\Pr(d) = R_{persist}^{d}(1-R_{persist})$ (truncated, tail mass on the last):
each duration is one deterministic macro path simulated under CRN
(`_prob_weighted_rec`, `welfare6_scenario.py:666+`; per-duration panels kept
for the Jensen-correct welfare aggregation — BUG-046 comment there). The
simulated panels are bit-identical across shared prefixes by the CRN design
(`read_shocks=True`; shock histories pre-materialized per experiment).

### 1.5 Outputs

- **Fiscal multipliers**: NPV of policy-induced consumption relative to NPV
  of fiscal cost, cumulated per horizon (orchestrator §10.3; TM engine
  `tm_methods.py`, MC cross-check engine — the METHOD axis
  `HAFISCAL_MULTIPLIER_ENGINE=tm|mc`).
- **Welfare-6**: the six-cell welfare metric (policy × recession/AD state),
  per-duration CRRA-utility aggregation weighted by $\Pr(d)$ against the
  base panels (orchestrator §10.4 — cell formula and the canonical
  all-MC ruling; `ui_norec` is 0/0 and never reported).
- Published-paper reproduction: the QE-frozen tables (`LOCKED_TABLES`
  workflow); the sibling `HAFiscal-QE` repo is canonical for the published
  version.

---

## 2. The inspector's equivalence-layer register

Between the math above and the numbers in the paper sit performance layers.
Each is EXACT (byte-identical, gate-verified) or carries a documented,
certified residual. An inspector verifying the MODEL may ignore exact
layers; residual layers cite their dossiers.

| layer | class | certification |
|---|---|---|
| Cohort-parallel solve (`parallel_solve.py`, `_SOLVE_WORKERS`) | exact | bit-identical vs sequential (3.88× at Baseline) |
| TM-ergodic Step-2 engine (default since 2026-06-23) | certified | TM≡MC β to ≤0.06% across cohorts; decision doc 2026-06-23 |
| Hybrid welfare engine (`HAFISCAL_WELFARE_ENGINE=hybrid`, default): replay-fed JAX-AD on HARK's captured exogenous panel | certified residual | CRN-paired −0.5…−1.3% on AD cells vs all-HARK, owner-accepted under sig-figs 2026-08-02; one-knob rollback `hark` is bit-identity-proven |
| Replay-kernel budget identities | exact mirror | `jax_mc_ad_replay_v2._mc_step_replay_v2` (:24–80) reimplements §1.1–§1.3 arithmetic; ESC asset law explicit (`esc_assets`); fp64 aggregate reductions |
| R1 batched + R2 state-restricted cFunc tables (per-period (T,J,M)) | exact | byte-identical end-to-end; runtime guard re-checks the one-macro-per-period invariant per capture, loud fallback |
| R3 base-run share (`base_aggcons` cache) + R4b policy-solve cache (`policy_full`, wholesale-pickled solutions) | exact | six byte gates 0-differing incl. the band canon (2026-08-02); the older knot-extraction serialization is LOSSY (drops PF-decay tails, 7.2e-3) — BUG-067, not used by these layers |
| Solution caches (`hark_solve_only` warm starts, AD-init) | documented residual | ~1e-5-class stopping noise, 2026-07-31 dossier; `HAFISCAL_VERIFY` axis forces fresh solves |
| Guarded wholesale AD-converged cache (`ad_full`, both engines) | exact + self-verifying | HIT is byte-identical to the producer run AND re-verified on every use by a one-iteration double-check (calibrated step threshold + tail-covering policy-compare); fail ⟹ quarantine + byte-certified cold fallback. Gates 2026-08-03 (plan 20260803-1030h) |
| Platform pin `JAX_PLATFORMS=cpu` (resolver default) | exact-by-pin | GPU reductions shift the AD fixed point at ULP scale (deterministic 1e-15 panel deltas) — pinned off the certified path |
| Machine probe (slots/reserve) | exact | scheduling only; `machine_profile.py` |

**Worlds and methods (what configuration am I inspecting?).** WORLD axis
`HAFISCAL_WORLD=default|as-corrected` (bug-fix-only counterfactual); METHOD
axis `HAFISCAL_MULTIPLIER_ENGINE=tm|mc`; interpretation default ESC. Exact
QE-published reproduction is the frozen tag / `HAFiscal-QE`, not a runtime
flag. Flags registry: `Code/HA-Models/docs/ENV_FLAGS.md` (guard-tested
complete).

---

## 3. Deliberate divergences and open items (do not re-flag)

- **CDC vs ESC splurge accounting** — same model, two conventions
  (`MODEL_INTERPRETATIONS.md`); matched-triple rule for
  {PermGroFac, calibration, interpretation}.
- **BUG-066** — the $t{=}0$ sown-C dead-key head (§1.3); OPEN, materiality
  <1e-4, owner-held.
- **BUG-067** — knot-extraction cache serialization drops PF-decay tails;
  the certified canon consistently sits on the lossy-loaded branch of the
  base entry; owner decision required before any fidelity fix (it would
  break byte-continuity).
- **RECONCILED-001** — TM clip / MC assert at the `[0.8,1.2]` C-ratio band:
  investigated, immaterial, guarded.
- Sticky expectations: machinery present, OFF (`UpdatePrb=1.0` everywhere).

**Sidecar-stamped reuse (2026-08-04):** every equivalence-layer row above that
engages at runtime (solve-cache HITs, the ad_full guarded reuse and its
verdicts, belief seeds, presolve warm starts, the JAX backend actually used)
is now RECORDED per run in the result sidecar (`RUN_*.prov.json`, schema v2
`reuse` block with a derived `determinism_class`) — an inspector reads which
layers a given result actually exercised from the file itself.
