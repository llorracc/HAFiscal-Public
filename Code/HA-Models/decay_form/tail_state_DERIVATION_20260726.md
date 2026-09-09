# Tail-state (HAFISCAL_DIST_TAIL_STATE) — derivation note of record

**Status:** DERIVE phase complete, 2026-07-26. Every formula below was numerically
verified (scripts + full outputs in `verif/` next to this note; all runs idle-box,
`ulimit -v 12582912`, `OMP_NUM_THREADS=2`, sequential; total wall < 10 s).
**The builder implements THIS note verbatim.** Where this note deviates from the
orchestrator's sketch, the deviation is derived, verified, and listed in §7.

Design context: `plans/20260726_dist-grid-top-scoping_plan.md` §P4′ and
`conclusions_private/2026-07-26_peratom_battery_verdict.md` (owner rulings).
Prior art reused: `Code/HA-Models/per_atom_alpha.py` (Kesten α),
`Code/HA-Models/decay_form/disttop_tail_bucket.py` (`_pareto_segments`),
`Code/HA-Models/FromPandemicCode/tm_methods.py` (`_build_period_tm_a` :3727,
`build_tm_agg_fiscal_a` :5357, `_make_newborn_dist_a` :3960,
`_effective_LivPrb` :903, `assert_mortality_inclusive_ergodicity` :2844).

---

## 0. Scope, state space, and wiring (TS-1)

* **Flag:** `HAFISCAL_DIST_TAIL_STATE` — off values `{'', '0', 'off'}` = today's
  bytes EXACTLY (the `tail_state=None` code path must be the untouched current
  code); on values `{'1', 'on'}`; any other value **raises** (precedent:
  `HAFISCAL_DIST_TOP_MODE`, tm_methods.py:5472-5475 raises on unknown).
  Register in `Code/HA-Models/docs/ENV_FLAGS.md` (guard:
  `Code/HA-Models/test_env_flag_registry.py`) and append to
  `_HAFISCAL_NUMERICAL_ENV_VARS` in `Code/HA-Models/solution_cache/keys.py`
  (next to `"HAFISCAL_DIST_TOP_MODE"`, keys.py:155, with a precedent-style comment).
* **State space:** one tail state `T_j` per micro state j appended to the
  a-indexed space: total `(A+1)*J`. **Layout** `index = j*(A+1) + i` for grid
  nodes `i = 0..A-1`, `T_j` at `i = A` — preserves the kernel's j-major
  convention (`_make_newborn_dist_a`: `NewBornDist[jp * A + 0]`; ergodic reshape
  `(J, A)` → `(J, A+1)`).
* `X := dist_aGrid[-1]` AFTER the mixing auto-repair (`refine_grid_for_mixing`,
  tm_methods.py:5599-5613, only SUBDIVIDES tail intervals — the top value is
  unchanged; verified by reading `tm_mixing_diagnostic` usage there). The grid
  itself is untouched by this feature.
* **Scope TS-1 guards (all raise `RuntimeError`/`ValueError` naming the flag):**
  * tail build allowed ONLY in `build_tm_agg_fiscal_a` (baseline-ergodic), and
    only with `Cratio == 1.0`, `neutral_measure == False`, and
    `interpretation == 'ESC'` (the interpretation-guard pattern: consumption
    enters the outflow law through the cFunc slope; the CDC blend
    `(1-ς)c*+ςξ` has a DIFFERENT asymptotic slope `(1-(1-ς)κ̲)` — out of scope,
    refuse; kernel guard precedent tm_methods.py:3820-3823, 5412-5418).
  * `build_experiment_period_tm_a` and `propagate_experiment_tm_a` raise at
    entry when the flag is on, AND whenever a handed-in distribution/ergodic
    size is `(A+1)*J ≠ J*len(dist_aGrid)` (Step-5a is measured top-indifferent
    at 3e-5 and stays out).
  * `compute_type_aggregates_tm_a` and `compute_period_aggregates_tm_a`: add an
    explicit size-check raise naming the flag (today they'd fail on reshape
    anyway; make it a designed message). **The 2026-07-26 consumption-block
    `_cons_cache`/`_cons_key` threading (tm_methods.py:5819, 5978-6010, 6263,
    6517, 6604) is NOT touched.**
  * mutually exclusive with `HAFISCAL_DIST_TAIL_BUCKET` (both on = the tail
    counted twice → raise) and with the `HAFISCAL_TM_A_CACHE` warm-start cache
    (its `cache_key` doesn't describe the tail; DISABLE the cache when the tail
    is active — precedent: the custom-`dist_aGrid` disable, tm_methods.py:5509-5510).
  * uniformity guards (the single-κ̲ assumption, §1): raise unless
    `Rfree_arr` is constant across micro states and `LivPrb_arr_raw` is
    constant across micro states.
* **New module** `Code/HA-Models/dist_tail_state.py` (standing rule: no new
  files in `FromPandemicCode/`) holding `resolve_tail_alpha(agent)` (§6),
  `landing_node_weights(alpha, m, dist_aGrid)` (§2), and
  `tail_readout_nodes(alpha, X, K, span)` (§5). `tm_methods` and
  `estim_phase2_tm_a` import it lazily under the flag (precedent: the
  `adaptive_grid_tm` lazy import, tm_methods.py:5453-5459).
* `tm_data` gains a `'tail_state'` key ONLY when the flag is on:
  `{'enabled': True, 'alpha', 'alpha_source', 'X', 'kappa', 'L_eff'}` or
  `{'enabled': False, 'reason'}`. Absent when off (byte-identity of the result
  dict). `find_ergodic_distribution` needs no change (power iteration on any
  column-stochastic matrix).

---

## 1. The outflow multiplier m_s (per_atom_alpha convention)

**Formula.** For destination micro state `jp` and shock atom `s` of
`IncShkDstn_list[jp]` (probability `p_s`, permanent shock `ψ_s = atoms[0][s]`):

```
κ̲    = 1 − (R · β · L_raw)^(1/ρ) / R          (asymptotic MPC of the SOLVED cFunc)
m_s(jp, s) = (1 − κ̲) · R_jp / (Γ_jp · ψ_s)
           = (R · β · L_raw)^(1/ρ) / (Γ_jp · ψ_s)     [R_jp = R uniform, guarded]
           = Thorn_jp / ψ_s        with Thorn_jp = (R β L_raw)^(1/ρ) / Γ_jp
```

with `β = agent.DiscFac`, `ρ = agent.CRRA`, `L_raw` the agent's raw `LivPrb`
(NOT `L_eff`), `Γ_jp = PermGroFac_arr[jp]`, `R = Rfree_arr[jp]` (guarded
uniform). This is EXACTLY `per_atom_alpha`'s effective-growth object
`M = Thorn/ψ` (per_atom_alpha.py:24-37) evaluated with that module's default
`mortality_in_discount=True`.

**Derivation.** In the kernel's own asset update (tm_methods.py:3881-3903,
quoted in §4), `m' = (R_jp/(Γ_jp ψ_s))·a + ξ_eff` and under ESC
`a' = m' − cFunc(m')`. As `m → ∞` the solved cFunc becomes affine,
`c(m) → κ̲·m + const`, so

```
a'/a  =  (1 − κ̲) · R_jp/(Γ_jp ψ_s)  +  O(1/a)  =  m_s(jp,s) + O(1/a).
```

The neglected `O(1/a)` term is `[(1−κ̲)ξ_eff − (c−κ̲m)|_∞]/a` — an O(1)
normalized-units constant against `a ≥ X ≈ 1300`, i.e. a ≲1e-3 relative blur of
the landing boundary; second-order on the read-out moments and absorbed by the
ladder gate.

**Survival-discounting placement, and WHY.** `L` appears in TWO different
roles, and (deviation-relevant, §3) with TWO different VALUES:

* **Inside the CRRA root (discounting):** the solver's Euler discounts at
  `DiscFacEff = β·L_raw` (HARK convention, no annuities), so
  `1−κ̲ = (R β L_raw)^(1/ρ)/R`. This is per_atom_alpha's
  `mortality_in_discount=True` and is the placement the 2026-06-16 ledger check
  pins: only it reproduces the quarterly-ledger row "certainty-equivalent
  patience `(RβL)^{1/2}/Γ = −0.037%`" and the caricature α≈1.70
  (`conclusions_private/2026-06-16_gic-inside-vs-outside-individual-target-vs-tm-ergodic.md`,
  ledger table; per_atom_alpha.py:39-51). The naive outside-only placement
  gives α≈1.099 — a different regime.
* **Outside (population culling):** the chain kills mass at rate
  `1 − L_eff(j)` per period, where `L_eff` is the T_age-adjusted survival the
  TM actually uses (`_effective_LivPrb`, tm_methods.py:903-933, applied at
  :5426-5427: `LivPrb_arr = _effective_LivPrb(LivPrb_arr_raw, T_age)`). The
  estimation agents carry `T_age = 200` (EstimParameters.py:676), so
  `L_eff = (L − L^200)/(1 − L^200) = 0.991254` vs `L_raw = 0.993750`. The
  culling and the discounting are DIFFERENT OBJECTS with different values; §3
  shows using the same value for both (the sketch's implicit reading) is
  measurably wrong for the production chain.

**V1 verification** (`verif/v1_multiplier.py`): (a) module-pin reproduction;
(b) a from-scratch EGM solve of the single-state cap-atom consumption function
(normalized Euler WITH the `(Γψ)^{−ρ}` factor — the BUG-047 lesson) measures
the asymptotic slope and discriminates the placement; (c) the slope-form and
Thorn-form of `m_s` are identical.

```
V1a  kesten_alpha ledger (L inside discount, default) = 1.779332   [module pin 1.779]  residual vs pin = 3.32e-04
V1a  kesten_alpha naive  (L outside only)             = 1.098775   [module pin 1.099]
V1   Thorn = 0.99963021   kappa(L inside) = 0.00541743   kappa(L outside) = 0.00229471   ratio = 2.361
V1b  EGM[DiscFacEff = beta*L (HARK convention)] converged in 4551 iters (rel 1.0e-13); kappa_hat = 0.00541746
V1b    |kappa_hat - kappa(L inside)|  = 2.93e-08  (0.0005% rel)
V1b    |kappa_hat - kappa(L outside)| = 3.12e-03  (136.1% rel)  <- must NOT match
V1b  EGM[DiscFacEff = beta (no survival in discount)] converged in 10386 iters (rel 1.0e-13); kappa_hat = 0.00229472
V1b    counterfactual solver matches kappa(L outside) to 1.13e-08
V1c  m_s from cFunc slope vs per_atom_alpha M = Thorn/psi: max |rel diff| = 2.22e-16
V1c  m_s values (s=0..6): 1.09129 1.04593 1.02152 1.00111 0.98112 0.95819 0.91789
V1c  E[log M] = +0.001032  (supercritical drift)   #atoms with m_s<1: 3/7
```

The EGM measures `κ̂ = 0.00541746` vs theory-with-L-inside `0.00541743`
(3e-8 abs); the counterfactual solver (discount β only) lands on the
L-outside number to 1e-8 — the placement is empirically pinned, not assumed.

---

## 2. P(stay) and the re-entry landing law

Contents of T: `a ~ Pareto(α)` on `[X, ∞)`: `P(a > y) = (X/y)^α`. Apply the
per-survivor multiplier `m ≡ m_s(jp,s)`:

* `m ≥ 1`: `a' = m·a ≥ X` — **all mass stays** in T.
* `m < 1`: `P(stay) = P(a ≥ X/m) = m^α`. Conditional on returning
  (`a' < X`), `a'` is a **truncated Pareto(α) on `[mX, X)`**:

```
P(a' > y | return) = ((mX/y)^α − m^α) / (1 − m^α),   y ∈ [mX, X).
```

(Check: = 1 at `y = mX`, = 0 at `y = X`.)

**Landing onto grid NODES (the builder formula).** For each grid cell
`[l, u] = [g_k, g_{k+1}]` intersecting `[mX, X)` at `[l', u']`
(`l' = max(l, mX)`, `u' = min(u, X)`), with conditional cell mass and
conditional mean (the `_pareto_segments` algebra with clipped edges,
disttop_tail_bucket.py:72-89):

```
μ_k  = (l'^(−α) − u'^(−α)) · (mX)^α / (1 − m^α)
ā_k  = α/(α−1) · (l'^(1−α) − u'^(1−α)) / (l'^(−α) − u'^(−α))
node g_k     += μ_k · (u − ā_k)/(u − l)          # linear lottery of the
node g_{k+1} += μ_k · (ā_k − l)/(u − l)          # conditional mean
```

`Σ_k μ_k = 1` exactly (telescoping). Because the kernel lottery is LINEAR in
position, lotterying each cell's conditional mean equals the exact
tent-function integral `∫ tent_k(y) f(y) dy` — the construction preserves both
total mass and the exact first moment of the landing distribution. Since
`dist_aGrid[0] = 0 < mX` always, no landing mass can fall off the bottom
(assert `m·X > dist_aGrid[0]` anyway).

Reference implementation verified in V2 (this exact function goes into
`dist_tail_state.landing_node_weights`):

```python
def landing_nodes_theory(alpha, m, X, grid):
    node = np.zeros(len(grid))
    for k in range(len(grid) - 1):
        l, u = grid[k], grid[k + 1]
        lp, up = max(l, m * X), min(u, X)
        if up <= lp:
            continue
        mu = (lp ** (-alpha) - up ** (-alpha)) * (m * X) ** alpha / (1.0 - m ** alpha)
        abar = (alpha / (alpha - 1.0)) * (lp ** (1 - alpha) - up ** (1 - alpha)) \
            / (lp ** (-alpha) - up ** (-alpha))
        node[k] += mu * (u - abar) / (u - l)
        node[k + 1] += mu * (abar - l) / (u - l)
    return node
```

**V2 verification** (`verif/v2_stay_landing.py`): 1e7 Pareto(1.779) draws,
multiplied, pushed through the KERNEL'S OWN lottery code (the searchsorted +
clip + linear-weight block, tm_methods.py:3907-3929) and compared to the
closed forms, for `m ∈ {0.90, 0.97, 1.02}` on a 4-cell top grid:

```
V2  m=0.90: P(stay) emp=0.829068 theory=0.829082 |rel err|=0.0016%  (binom SE 1.2e-04)
      node a=0.88: emp=0.056706 th=0.056659 |rel|=0.0820% (SE 1.8e-04)
      node a=0.92: emp=0.376864 th=0.376870 |rel|=0.0017% (SE 3.7e-04)
      node a=0.96: emp=0.387075 th=0.387234 |rel|=0.0412% (SE 3.7e-04)
      node a=1.00: emp=0.179355 th=0.179236 |rel|=0.0665% (SE 2.9e-04)
V2  m=0.97: P(stay) emp=0.947194 theory=0.947255 |rel err|=0.0064%  (binom SE 7.1e-05)
      node a=0.96: emp=0.380308 th=0.380290 |rel|=0.0047%
      node a=1.00: emp=0.619692 th=0.619710 |rel|=0.0029%
V2  m=1.02: P(stay) emp=1.000000 theory=1.000000  — no returns (m >= 1), as required
```

Stay probabilities match to ≤0.006%, node masses to ≤0.08% — all an order
inside the 0.5% target (each within ~2 binomial SE). Landing-ccdf spot checks
≤0.11% except the y=0.995X point (0.63%, = 2σ at that small ccdf value).

---

## 3. Self-consistency of the ONE-state design — PASS, with a production-α finding

**Claim tested:** the TRUE scalar tail sub-process — per-survivor multiplier
`M_s = Thorn/ψ_s`, culling `1−L` per period, entry just above X, exit (absorption)
below X — has a stationary distribution whose conditional shape above X is
`Pareto(α_kesten)`, the shape the tail state freezes.

In `z = log(a/X)` this is a random walk with iid increments `log M_s`,
per-step weight factor `L`, absorption at `z < 0`, constant inflow near 0+.
Its stationary density solves the linear balance `h = L·K h + b`, which
`verif/v3_selfconsistency.py` solves EXACTLY (sparse direct solve of
`(I − L·K) h = b` on a dz=0.002 grid, Z=6, absorbing both ends, entry both
spread-(0,0.05] and point) and independently by a 3500-period weighted-particle
simulation (survival as deterministic weight-thinning; ~293k live particles).

```
V3   L_RAW=0.993750  L_EFF(T_age=200)=0.991254  E[logM]=+0.001032  logM range [-0.08567,+0.08736]
V3   alpha ledger(raw-L root) = 1.779332
V3   alpha split  direct     = 2.163413   adapter(kesten_alpha(beta*Lraw/Leff, Leff)) = 2.163413   |diff| = 8.17e-14
V3op LEDGER (cull L_RAW): alpha_hat=1.7791 (window halves 1.7791/1.7791; point-entry 1.7791)  vs root 1.7793  -> rel err 0.01%
V3op PRODUCTION split (cull L_EFF): alpha_hat=2.1631 (window halves 2.1631/2.1631; point-entry 2.1631)  vs root 2.1634  -> rel err 0.01%
V3mc LEDGER particle sim: live=292650, alpha_hat=1.7810 vs 1.7793 -> rel err 0.09%  (weighted ccdf fit on z in [0.5, 2.2])
```

**Verdict: self-consistency PASSES far inside the 5% tolerance** — 0.01%
(exact operator, entry-insensitive, window-halves identical i.e. purely
exponential) and 0.09% (independent MC). The one-state design STANDS; no
sub-states needed.

**Production-α finding (sketch amendment, verified).** At the brief's ledger
spec (culling = L_raw = 1−1/160) the stationary exponent is 1.7791 ≈ the
per_atom_alpha root 1.779 — the brief's "~1.78" is CONFIRMED for that spec.
But the PRODUCTION chain culls at `L_eff(T_age=200) = 0.991254`
(tm_methods.py:5426-5427) while discounting at `β·L_raw`; re-solving the same
sub-process with production culling gives **α = 2.1631**, matching the
split-condition root `L_eff·E[(Thorn_raw/ψ)^α] = 1` to 0.01%. So the α INPUT
for the build must be the **T_age-split Kesten root**, obtained from
per_atom_alpha UNCHANGED via the adapter (verified identical to a direct
root-find to 8e-14):

```python
L_eff = _effective_LivPrb(np.array([L_raw]), T_age)[0]     # tm_methods.py:903
alpha = kesten_alpha(beta * L_raw / L_eff, R, CRRA, PermGroFac_employed,
                     L_eff, psi_atoms, psi_pmv)            # mortality_in_discount=True
# inside: beta_eff = (beta*L_raw/L_eff)*L_eff = beta*L_raw  (the solver's discount)
# outside: L_eff                                            (the TM's culling)
```

Using the raw-L root (1.78) instead would mis-state the production shape by
17.7%. Independent corroboration: the split root 2.163 matches the plan's
MEASURED moderate-window cap-atom wealth-tail exponent α≈2.17 (P0 §"Why
truncation must bite" and the P2 step-ratio validation) — theory and
measurement now agree without invoking window drift for the cap atom itself.

**Known residual approximation of the frozen shape (quantified, V3b).** The
true stationary sub-process has an inflow-fed boundary layer near X (20.7% of
tail mass at z<0.1 vs the frozen Pareto's 19.5%), so the frozen law slightly
understates one-period returns. Measured on the exact production-culling
solution (`verif/v3b_boundary_layer.py`):

```
V3b  one-period return prob: true=0.047176 frozen-Pareto=0.042550  rel diff -9.81%
V3b  total outflow rate:     true=0.055509 frozen=0.050924  -> stationary pi_T bias of the frozen law ~ -8.26%
V3b  stationary mass at z<0.1 (boundary layer): 0.207;  z<0.3: 0.486
V3b  E[a/X | in T]: true=1.8440 frozen=1.8595 rel diff +0.85%
```

By outflow balance (`π_T = inflow/outflow`) the one-state tail OVERSTATES
stationary tail mass by ≈ +9% (and conditional tail wealth by +0.85%) at the
cap atom. Impact arithmetic: tail wealth above X=1300 carries ~3.3% of College
wealth (2026-06-16 doc measurement), so the frozen-law bias is ≈ **+0.3% of
College wealth at X=1300** (≈+0.7% at X=500 where the tail share is larger,
≈+0.15% at X=2900) — inside FAST/STANDARD everywhere and inside REFERENCE-1%
for X ≥ ~800. **Pre-registered ladder prediction:** ~flat with a small
monotone offset of that profile. If the gate instead shows a >0.5%-class
offset at production tops, the smallest fix is PRE-DERIVED: replace `m^α` and
the landing shape by the killed-walk stationary `h` (the V3 operator solve —
per-atom one-time sparse solve, milliseconds) — a boundary-corrected outflow
TABLE, still one tail state. 2–3 sub-states are NOT needed on this evidence.

---

## 4. Exact TM column entries (against `_build_period_tm_a`)

Code read (tm_methods.py, current bytes). The kernel builds, per source micro
state j: a death→newborn block, then per destination jp a shock-atom loop with
the lottery; the top-clip is the `above` mask:

```python
3853      # Death/rebirth: fraction death_prb of the mass at each source
3855      if n_nb > 0 and death_prb > 1e-18:
3856          src_cols = np.repeat(src_range_A + col_offset, n_nb)
3857          dst_rows = np.tile(nb_nz_idx, A)
3858          vals = np.tile(death_prb * nb_nz_val, A)
...
3907          idx = np.searchsorted(dist_aGrid, a_next_flat, side='right') - 1
3908          below = a_next_flat <= dist_aGrid[0]
3909          above = a_next_flat >= dist_aGrid[-1]
...
3926          lower_idx[above] = A - 1
3927          upper_idx[above] = A - 1
3928          lower_wt[above] = 1.0
3929          upper_wt[above] = 0.0
3930
3931          # (A*S,) weights, a-major / xi-minor — same layout as m_next_flat.
3932          wt = markov_prob * LivPrb_j * np.tile(shk_prbs, A)
3933          src_cols = np.repeat(src_range_A + col_offset, S)
```

With the tail active (all indices below use stride `A+1`; `col_offset = j*(A+1)`;
`row(jp, i) = jp*(A+1) + i`; `T_jp` row `= jp*(A+1) + A`):

**(a) Ordinary source columns `(a_i, j)`, i = 0..A-1** — identical to today
EXCEPT the inflow redirection rule: the mass currently routed by lines
3926-3929 to node `A-1` goes to `T_jp` instead. Precisely: keep the existing
`above` mask (`a_next >= dist_aGrid[-1]`, so the boundary point belongs to
T's support `[X, ∞)`); exclude `above` points from the lo/hi lottery appends
(`mask_lo &= ~above`, `mask_hi &= ~above`) and append instead

```
row T_jp = jp*(A+1) + A,  col = j*(A+1) + i,  value += Σ_{s: above} wt[i,s]
```

with `wt = markov_prob · LivPrb_j · shk_prbs` exactly as line 3932
(`LivPrb_j = L_eff(j)`). Nothing else in the ordinary columns changes.

**(b) Death→newborn, ALL source columns of state j including `T_j`:** the
line-3856 source range becomes `arange(A+1) + j*(A+1)` — i.e.
`T[:, c] += (1 − L_eff(j)) · NewBornDist` for every column c of micro state j.
`NewBornDist` is `_make_newborn_dist_a` (tm_methods.py:3960-3980) at length
`(A+1)*J`: `NewBornDist[jp*(A+1) + 0] = markov_ergodic[jp]`, **zero at every
tail row** (newborns start at the grid bottom).

**(c) Tail column `T_j` (col `j*(A+1) + A`), survivor part:** for each
destination jp with `micro_trans[j, jp] ≥ 1e-15` (same skip as line 3864-3866)
and each shock atom s of `IncShkDstn_list[jp]` (the DESTINATION-state
distribution, same object the kernel uses at 3868-3871), with
`w0 = L_eff(j) · micro_trans[j,jp] · p_s` and `m = m_s(jp, s)` from §1:

```
m ≥ 1:  T[T_jp, T_j] += w0
m < 1:  T[T_jp, T_j] += w0 · m^α
        T[jp*(A+1) + k, T_j] += w0 · (1 − m^α) · node_k   for the landing
                                 node weights node_k of §2 (Σ node_k = 1)
```

**Column-stochasticity (proof + test).** Ordinary columns: the redirect moves
weight between rows of the same column — sums unchanged from today's
column-stochastic kernel (docstring tm_methods.py:3737-3754). Tail column:

```
Σ_rows T[·, T_j] = (1 − L_eff(j))·ΣNewBorn + L_eff(j)·Σ_jp Mrkv[j,jp]·Σ_s p_s·(m^α + (1−m^α)·Σ_k node_k  or  1)
                 = (1 − L_eff(j)) + L_eff(j) = 1.
```

**V4 verification** (`verif/v4_toy_tm.py`): the full `(A+1)*J` matrix built
from these formulas on random parameters (A=6, J=3, S=4, multipliers spanning
0.70–1.15 incl. a forced 2-cell landing span and a stay-all atom, random
row-stochastic Mrkv, random L_j, random newborn micro weights):

```
V4  column-stochasticity: max |colsum - 1| = 2.22e-16  (PASS)
V4  NewBorn mass on tail rows = 0.0e+00 (must be 0)
V4  strong components = 1  (PASS (irreducible))
V4  power iteration: residual 0.00e+00; stationary tail mass pi_T = 0.0243 (> 0, finite)  sum(v) = 1.000000000000
```

Irreducibility is verified, not assumed: T communicates outward via re-entry
(m<1 atoms) and death→newborn, inward via the redirect — a single strong
component (scipy `connected_components(connection='strong')`), and power
iteration (the actual `find_ergodic_distribution` method) converges to a
proper stationary vector with positive finite tail mass. The
`assert_mortality_inclusive_ergodicity` guard (tm_methods.py:2844) is
untouched and remains the existence condition; §6 shows it also guarantees
α > 1.

---

## 5. Read-out expansion (estimation surface only)

Consumer: `estim_phase2_tm_a.betas_obj_func_educ_tm_a`, which currently
reshapes `(J, A)` and appends per-j `(a, w)` pairs (estim_phase2_tm_a.py:
195-237), pools across atoms, applies the ESC `(1−ς)` household correction
(:248-249), and computes median + Lorenz targets (:251-253). Under the flag:
reshape `(J, A+1)`; the first A columns feed the existing appends unchanged;
the pooled tail mass `w_T = erg[:, A].sum() · agent_w` (pooling over j is
moment-equivalent for the pooled-histogram estimands — same argument as the
DIST_TAIL_BUCKET comment at :203-206) is expanded as:

```
seg_m, seg_mean = _pareto_segments(alpha, X, n_nodes=K, span=span)   # EXISTING code
q      = span^(−α)                       # mass beyond span·X
a_term = α/(α−1) · span · X              # its exact conditional mean
append nodes:  seg_mean  with weights  w_T · (1−q) · seg_m
        plus:  a_term    with weight   w_T · q          (the TERMINAL ATOM)
```

The ESC `(1−ς)` scaling then applies to the appended nodes automatically
(unchanged code order). **Defaults: `K = 12`, `span = 1000`.**

Why this is exact where it matters (V5, `verif/v5_readout.py`):
`_pareto_segments` masses sum to 1 and reproduce the truncated conditional
mean to machine precision; with the terminal atom the expanded FIRST MOMENT
equals the exact Pareto mean `α/(α−1)·X` at ANY span (residual ≤2e-16).
Without the terminal atom, truncation at `span·X` discards tail-wealth share
`span^(1−α)` — e.g. 11.5% at (α=1.47, span=100) and still 2.8% at (α=1.779,
span=100): the sketch's plain-truncation read-out is NOT wealth-safe, hence
the terminal atom (deviation §7). At (α=2.17, span=1000) the discard would be
3.1e-4; the atom makes the choice moot. K only matters for estimands that CUT
THROUGH the tail interior: every estimand of record (Lorenz p20-p80,
top-1%/10% shares, medianLWPI) wholly contains the tail, so it is K-invariant
by mean-exactness — measured: top-0.1% share identical for K ∈ {6, 12, 24}
vs a K=20000 reference to <1e-6 rel. K=12 (the existing `N_TAIL_NODES`) is
kept for tail-interior diagnostics (q99.9-class).

```
V5  alpha=1.470 span=   100 K=12: |sum(seg_m)-1|=2.2e-16  |segmean/trunc-1|=1.1e-16  |total/exact-1|=1.1e-16  discard-if-no-terminal=1.148e-01
V5  alpha=2.170 span=  1000 K=12: |sum(seg_m)-1|=0.0e+00  |segmean/trunc-1|=0.0e+00  |total/exact-1|=2.2e-16  discard-if-no-terminal=3.090e-04
V5  K=    6/12/24: top-0.1% share = 0.001868 each, rel err vs K=20000 ref 0.0000%
```

(`_pareto_segments` signature reused as-is; its import is cheap and
side-effect free per the 2026-07-26 refactor header, disttop_tail_bucket.py:30-36.
The α=1 branch of `_pareto_segments` is unreachable here — §6 guarantees α>1.)

---

## 6. α resolution per atom, and the guard for no-root / trivially-thin atoms

**Resolution (owner-recorded input choice):** the per-atom KESTEN root, NOT
measured-α — measurement at low tops is corrupted by the very truncation being
removed; the ladder-flatness gate is the measured validation; cross-checks vs
measured-α at tall proxy tops stay diagnostics. Primitives extracted exactly as
the prior art does (`disttop_tail_bucket._kesten_alpha_from_module`,
:339-354): `beta = agent.DiscFac`, scalar `Rfree`, `CRRA`, EMPLOYED-state
`PermGroFac` (`_first_scalar`), employed-state joint `IncShkDstn[0][0]` ψ atoms
`atoms[0]` with the joint `pmv`; then the §3 T_age adapter
(`kesten_alpha(beta·L_raw/L_eff, ..., LivPrb=L_eff)`). The employed-state
caricature ignores Markov modulation of Γ/ψ across unemployment spells (~5%
occupancy) — a known approximation of the SHAPE input; the outflow MASS
dynamics in §4 use each destination state's own `(R_jp, Γ_jp, ψ_{jp,s})`
exactly. The ladder gate arbitrates.

**Guard (per-atom disable → build the standard `A*J` TM for that atom):**

1. `per_atom_alpha.kesten_alpha` RAISES (per_atom_alpha.py:52-74 regime map:
   subcritical `max(Thorn/ψ) ≤ 1` — tail thinner than any power law; or root
   beyond `alpha_max` — near-degenerate spread), **or** the root falls outside
   the plausibility band **`1 < α < 20`** (the prior-art acceptance band,
   disttop_tail_bucket.py:355; at α≥20 the stay mass `m^α` of the widest atom
   is <1e-1·…·≈0.9^20≈0.12-class and the tail empties in a few periods —
   physically meaningless, numerically harmless to skip).
2. **Post-ergodic materiality check** (free — the estimation surface already
   solves the ergodic): for a DISABLED atom, if the standard build's top-node
   pile `m_top = Σ_j erg[j, A−1] ≥ 1e-8`, RAISE (loud): a "no-power-tail" atom
   with a material pile means the grid top sits inside the atom's BULK — a
   mis-sized grid, not a tail-law question. Threshold why: ignored tail wealth
   is bounded by `m_top · X · α/(α−1) ≈ 1e-8·1300·1.85 = 2.4e-5` absolute —
   at the smallest group E[a] ~ 1 that is 0.0024%, two orders below the
   tightest (REFERENCE 1%) budget (V6c), and the pile itself OVERSTATES a thin
   atom's clipped mass.

α > 1 (finite tail mean, terminal atom well-defined) is GUARANTEED whenever
the root exists, by the existing ergodicity guard: the identity

```
f(1) = L_out·E[M] = GPF_out · (L_out/L_raw) · L_raw^(1/ρ)   (< GPF_out < 1)
```

holds to machine precision (V6a: |diff| ≤ 2.2e-16, f(1) = 0.99617 raw /
0.99367 split), and `f` convex with `f(α_root) = 1` ⟹ root > 1. `GPF_out`
here is exactly the object `assert_mortality_inclusive_ergodicity` polices
(tm_methods.py:2851-2853; measured 0.999298 on the 7-pt reconstruction of the
ledger, consistent with the theGICfactor 0.9995 design point given the
rounded published cap-β literal and discretization).

```
V6a [raw       ] f(1) = 0.99617061  identity = 0.99617061  |diff| = 2.2e-16   f(1)<1 -> root alpha>1: True
V6a [split/T_age] f(1) = 0.99366858  identity = 0.99366858  |diff| = 1.1e-16   f(1)<1 -> root alpha>1: True
V6b beta=0.9: root = 57.477 (no raise)        <- caught by the (1,20) band instead
V6b beta=0.8: raises ValueError [no positive root: SUBCRITICAL atom -- max(Thorn/psi) = 0.973468 <= 1 ...]
V6c disable threshold: pile m_top < 1e-8 => ignored tail wealth <= 2.41e-05 absolute (0.0024% of E[a]~1)
```

Estimation-population picture under this guard: cap-class atoms (the point of
the feature) → α ≈ 2.16 enabled; mid-β atoms (e.g. β≈0.98) → α ≈ 6-12,
enabled, tail mass negligible (harmless, consistent); low-β atoms → subcritical
raise or band-out → disabled, pile ≈ 0 confirmed by the m_top check.

---

## 7. Deviations from the orchestrator's sketch (all derived + verified above)

1. **α input = the T_age-SPLIT Kesten root** (culling `L_eff`, discount
   `β·L_raw`; adapter in §3), ≈2.1634 at the cap atom — not the sketch's
   raw-L root ≈1.7793 (17.7% apart). The production sub-process measurably
   equilibrates to the split root (0.01%); the split root independently
   matches the plan's measured α≈2.17. The brief's "~1.78" is confirmed for
   the no-T_age ledger spec only.
2. **Read-out gains a closed-form terminal atom** beyond `span·X` (§5); plain
   truncation would discard up to ~11% of tail wealth at plausible (α, span).
   With it, the expansion is exactly mean-preserving at any span, and all
   estimands of record are K-invariant.
3. **Frozen-Pareto boundary-layer bias quantified** (V3b): the one-state
   design overstates stationary tail mass ~+9% (College-wealth impact
   ~+0.3% at X=1300, ~+0.7% at X=500) — pre-registered as the expected ladder
   offset profile; boundary-corrected outflow TABLE (killed-walk operator
   solve, one-time per atom) is the pre-derived smallest fix if the gate
   demands it. Sub-states are not needed.
4. **Extra guards not in the sketch:** ESC-only, `Cratio=1`-only,
   `neutral_measure=False`-only, uniform-R/uniform-LivPrb across micro states,
   α ∈ (1, 20) band, mutual exclusion with `HAFISCAL_DIST_TAIL_BUCKET`,
   `HAFISCAL_TM_A_CACHE` disabled when active, `m_top ≥ 1e-8`
   refuse-on-contradiction for disabled atoms.
5. **The redirect reuses the kernel's existing `above` mask** (`>=` top,
   line 3909): the boundary point a=X belongs to T's support; the top grid
   node keeps only lottery mass from the last interval.
6. V2's deepest ccdf spot check (y=0.995X) came in at 0.63% (2σ at that
   ccdf level); all REQUIRED gates (stay, node masses) are <0.1%.

## 8. Verification inventory (scripts in `verif/`, outputs quoted above)

| script | what it verifies | residual |
|---|---|---|
| `v1_multiplier.py` | kesten pin; EGM asymptotic-MPC placement; m_s identity | 3.3e-4 vs pin; 2.9e-8 abs on κ̲; 2.2e-16 |
| `v2_stay_landing.py` | `P(stay)=m^α`; landing node masses via the kernel lottery | ≤0.006%; ≤0.08% |
| `v3_selfconsistency.py` | stationary shape = Pareto(root), ledger + production culling; adapter | 0.01% op / 0.09% MC; 8.2e-14 |
| `v3b_boundary_layer.py` | frozen-law π_T and E[a\|T] bias (the honest residual) | −8.26% outflow / +0.85% mean (measured, not a gate) |
| `v4_toy_tm.py` | exact columns: stochasticity, newborn zeros, strong irreducibility, power-iter | 2.2e-16; 0; 1 component |
| `v5_readout.py` | `_pareto_segments` + terminal-atom exactness; K-invariance of estimands | ≤2.2e-16; <1e-6 rel |
| `v6_guards.py` | f(1) identity (α>1 under the ergodicity guard); raise regimes; threshold arithmetic | ≤2.2e-16 |
