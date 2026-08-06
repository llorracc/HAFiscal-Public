# MODEL_INTERPRETATIONS.md — the splurge / bonded-pair consumer, CDC vs ESC

**Status:** normative reference (repo root, deliberately conspicuous). Created 2026-06-11.
**Authoritative math/spec:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md`.
This file is the 1.5-page executive statement; that file is the formal one.

---

> # ⛔ STOP — THE #1 RECURRING CONFUSION (read before flagging any "splurge" inconsistency)
> ## ⛔ Splurge-IN-budget and splurge-OUT-of-stage are the SAME model. NOT a contradiction.
>
> If you are about to flag, "bug-report," or "reconcile" a divergence because **one document
> subtracts the splurge inside the budget** (`a = m − c_sp − c_opt`) **and another keeps the splurge
> out of the optimizer stage** (`a = m − c_opt`): **STOP. That is not a divergence. It is the two
> intended interpretations of one model**, and they are reconciled by a proven homotheticity result
> (§3). Specifically:
>
> | document / artifact | which form | which interpretation |
> |---|---|---|
> | `HAFiscal-bellman-for-matsya.md` ("Version A"), paper `eq:budget` | splurge **IN** the household budget | **CDC** (single-household reduced form) |
> | `HAFiscal-doloplus-draft.yaml` (the canonical DDSL stage) | splurge **OUT** of the optimizer stage | **ESC** (Campbell–Mankiw bonded-pair optimizer sub-household) |
>
> Both are **correct, deliberate, and equivalent up to a `(1−ς)` level rescaling** (CRRA
> homotheticity, §3): the optimizer's *normalized* policy IS the standard buffer-stock policy
> `c^std`; the only place the two interpretations genuinely branch is the **asset-update / wealth
> level** (§2 table), which is why the fitted `ς` differs (ESC 0.26718 vs CDC 0.25710 — REAL, not an
> artifact, §4). The YAML being the **ESC optimizer stage** while the bellman doc is the
> **CDC-style household budget** is **BY DESIGN**, documented here, and is **NOT** an open ledger row,
> a bug, or a TODO. Do not re-litigate it. If a spec-gap audit "discovers" this again, the correct
> action is to cite THIS file and move on.
>
> (The single legitimately-open question in this area is the *value* of `ς` per interpretation —
> ledger row D-06 — and the matched-triple `{PermGroFac regime, calibration file, interpretation}`
> consistency rule, §5. Neither is a structural contradiction.)

---

---

## 1. The splurge / bonded-pair setup (what the paper writes)

A consumer `i` faces a stochastic income stream `y` and, **each period, mechanically spends a
fraction `ς` of current income** — the "splurge" — then optimizes over what is left. Paper
`Subfiles/Model.tex` (lines 28–124), labels `eq:model`, `eq:splurge`, `eq:budget`, `eq:income`:

```
c        = c_sp + c_opt              (eq:model)
c_sp     = ς · y                     (eq:splurge)        ς ≈ 0.25–0.27 (estimated, CRRA γ=2)
max  Σ βᵗ(1−D)ᵗ E₀ u(c_opt)          (eq:utility)        utility flows from c_opt ONLY
a        = m − c ,  m' = R·a + y'    (eq:budget)         a ≥ 0 (no borrowing)
```

The paper motivates this with two footnotes that are the *entire* textual basis for the
interpretation question (`Subfiles/Model.tex:28`):

> "With what is left over, the consumer chooses to optimize consumption **without regard to the
> fraction that was already spent**." … "This is **equivalent to households that consist of a pair
> that act independently of each other but share parts of the same income flow** … applying a
> version of \citet{campbell1989consumption}'s model … at the household level."

That footnote is the bonded-pair (Campbell–Mankiw) reading. The body equation `eq:budget`, however,
subtracts **total** `c` from a **single** household budget. The two are not literally the same
object — hence the two interpretations below.

---

## 2. The two interpretations and the ONE equation they differ in

Both readings share: utility `u`, the standard CRRA buffer-stock policy `c^std(m)`, the income
process, the welfare aggregator `u(C_tot)` ("inclusive of the splurge", `Comparing-policies.tex:144`),
and the calibration targets (K/Y≈6.60, four Lorenz points, Fagereng MPCˣ). **They differ in exactly
one equation: the asset-update rule.** (`models_CDC_and_ESC.md` §§4–6.)

| | **CDC** — single-household bargain | **ESC** — Campbell–Mankiw bonded pair |
|---|---|---|
| `opt`/`spl` are… | two *preference-voice proposals* (counterfactual) inside ONE decision unit | two *actually-distinct sub-households* sharing `p_tot`, deciding independently |
| Asset-update rule | **(eq:budget-CDC)**  `A_tot = M_tot − (1−ς)·c^std(m_tot)·p − ς·Y_tot` | **(eq:budget-ESC)**  `A_opt = M_opt − c_opt`; `A_tot = A_opt` (splurger holds 0 assets) |
| What `c^std(·)` argument is | household `m_tot = R·A + Y` | optimizer `m_opt = R·A/(1−ς) + Y_opt` (per-capita; richer asset/income ratio) |
| Optimizer is… | **naive** (perceives full proposal implemented; realized differs) | **rational at its own sub-household scale** (perceived = realized) |
| `state_now["aLvl"]` in code | household asset (override installed) | optimizer per-capita asset (plain HARK) |

Everything else — `c = (1−ς)·c^std + ς·y` for total consumption, the welfare formula, the targets —
is **identical**. Only where assets accumulate (CDC books the household's blended spending; ESC books
the optimizer's own spending on its own income share) does the model branch.

---

## 3. The HOMOTHETICITY result (the load-bearing fact — owner's 2026-06-11 claim, CONFIRMED)

**Claim.** Under ESC, the optimizer sub-household receives income `(1−ς)·Y` and behaves optimally
over it as if the splurger did not exist. Because the buffer-stock problem is **homothetic** (CRRA),
this is *just the standard problem scaled by `(1−ς)`*: the optimizer's permanent-income-**normalized**
policy is **identical** to the standard problem's normalized policy; only the **level** scales by
`(1−ς)`. Hence ESC household wealth `= (1−ς)·aLvl`, where `aLvl` is the **same** standard buffer-stock
solution — **not a fundamentally different solve.**

**This is correct.** The derivation (`equations_paper_and_CDC.md` §"Where does the (1−ς) factor come
from?") substitutes the splurge out of the paper's own budget. Define post-splurge resources
`m̃ ≡ m − ς·y`. Then `eq:model`+`eq:budget` collapse to a standard CRRA buffer-stock in `m̃` whose
income process is scaled by `(1−ς)`:

```
a = m̃ − c_opt ,    m̃' = R·a + (1−ς)·y'.          ← standard problem, income × (1−ς)
```

CRRA homotheticity then gives, with `m̃ = (1−ς)·m*` and `m* = b* + y` the optimizer's own state:

```
c_opt(m̃) = (1−ς) · c^std( m̃/(1−ς) ) = (1−ς) · c^std(m*) .
```

Equivalently (`models_CDC_and_ESC.md` §5.3, Convention 1): normalizing the optimizer's problem by its
own permanent income `p_opt = (1−ς)·p_tot`, the optimizer's **normalized** transitory shock equals the
household's (`ξ_tot`), its **normalized** policy is the standard `c^std`, and `a_opt = a_tot/(1−ς)`
⟺ `a_tot = (1−ς)·a_opt`. Edmund Crawley's branch implements exactly this: the wealth line is
`WealthNow = (1−ς)·state_now["aLvl"]` (`origin/maintain_bound_pair_fix_splurge`, line 219), with
**no** `get_poststates` override — the agent runs the plain standard solve and `(1−ς)` is applied
only as a wealth-level rescaling.

> **Scope of what is proved (be precise).** Homotheticity proves *optimizer-per-capita ≡ paper's
> reduced-form single-state problem, up to (1−ς)*. It does **NOT** prove ESC ≡ CDC: CDC evaluates
> `c^std` at the household state `m_tot = R·A + y`, ESC at the per-capita state `m* = R·A/(1−ς) + y`.
> Since `c^std` is concave and `m* > m_tot`, the two evaluate the *same function at different points*
> ⇒ genuinely different household dynamics (`_archive/notes_on_bound_pair_equivalence.md`). The
> homotheticity equivalence is **internal to ESC** (optimizer ↔ paper-reduced), not a bridge to CDC.

---

## 4. SAME vs DIFFERENT across the two interpretations

| Object | ESC vs CDC |
|---|---|
| Functional form of total consumption `(1−ς)·c^std(·) + ς·y` | **SAME** |
| The standard buffer-stock `c^std` as a *function* / its Euler equation | **SAME** (one solve serves both) |
| Optimizer's **normalized** policy (ESC) vs standard normalized policy | **SAME** (homotheticity; §3) |
| Welfare aggregator `u(C_tot)`, calibration target *set* | **SAME** |
| Wealth **level** entering the targets | **DIFFERENT** — ESC `(1−ς)·aLvl`; CDC `aLvl − ς·p·(ξ−c)` |
| Argument `m` fed to `c^std` (household vs per-capita) | **DIFFERENT** |
| Fitted `(β̄, ∇, ς)` triple | **DIFFERENT** (see §5) |

**Why ς differs even though the normalized policy is the same — this is REAL, not an artifact.**
The two wealth concepts are not algebraically equal: setting `(1−ς)·aLvl_HARK = aLvl_HARK − ς·p·(ξ−c)`
requires `ξ = m` (zero beginning-of-period bank balances for every agent), false across the ergodic
distribution (`...investigation.md` §3). The calibration matches **absolute, level** moments — K/Y and
the SCF Lorenz **levels** — so two different wealth-level maps `(β,∇,ς) → targets` pin **different** ς.
Empirically (current files):

| `Result_AllTarget*.txt` | ς | β̄ | ∇ | source |
|---|---:|---:|---:|---|
| `_CDC` | **0.25982** | 0.96232 | 0.07165 | noise-free TM re-derivation 2026-07-27 (owner D3: replaced the April-era 0.25710/0.96081/0.07129, kept in git history) |
| `_ESC` | **0.27035** | 0.97313 | 0.05937 | noise-free TM re-derivation 2026-07-27 (first valid ESC run after the BUG-054 fix; Edmund's April pre-staged values were 0.26718/0.97148/0.05892, `db48d328`) |

(Since the BUG-054 Option A fix, 2026-07-27, the bare `Result_AllTarget.txt` is a **symlink**
to `_ESC` — each interpretation's estimation writes its own suffixed file. Matched-era
comparisons of the concept gap: April `_CDC`→`_ESC` ς +3.9%; noise-free 0.25974→0.27035
ς +4.1% — stable across eras. The noise-free CDC candidate is NOT installed in `_CDC`;
its adoption, like the Step-2 cascade at the new ESC ς, is a pending owner decision.)

ς differs +0.0101 (≈ **+3.9%**); β +0.0107; ∇ −0.0124. A more patient optimizer (higher β) on the
richer per-capita resource scale is exactly what ESC's homothetic rescaling predicts
(`why_results_match_at_target.md` §5). Note: the homotheticity (§3) makes the *normalized policy* the
same **function**, but the calibration does not target the normalized policy — it targets level wealth,
and the level map differs by interpretation, so the fitted ς differs. **Both are internally consistent;
the difference is a genuine consequence of which wealth concept enters the level targets.**

---

## 5. Which interpretation is canonical? (a muddle worth flagging)

- **Library code-literal = CDC; every entry point defaults ESC.** `_interpretation.get_interpretation()`
  keeps `'CDC'` as the conservative code-literal, but `EstimParameters.py` (since 2026-06-14) and
  `Estimation_BetaNablaSplurge.py` (since the BUG-054 Option A fix, 2026-07-27) both
  `setdefault(HAFISCAL_INTERPRETATION, 'ESC')`, so unflagged pipeline AND Step-1 runs are ESC.
  Step-1 output routes per interpretation (`Result_AllTarget_ESC.txt` / `_CDC.txt`); the bare
  `Result_AllTarget.txt` is a symlink to `_ESC`.
- **Shipped / recent production = ESC.** The pre-staged `_ESC` calibration files (ς=0.26718, and the
  downstream `DiscFacEstim_*_ESC.txt` discount-factor files) are what the recent production and
  validation drivers consume — several set `HAFISCAL_INTERPRETATION=ESC` explicitly
  (`measure_gicfactor_tradeoff.py:15`, `validate_mixing_ergodic.py`, `run_step5a_only.py:34`,
  `harmenberg_doob_tier1_esc.py`, `adaptive_grid_tm.py`). The CLAUDE.md "canonical solution"
  block and the GIC-cap re-estimation work on the ESC calibration.
- **Paper text is ambiguous** between the two (`models_CDC_and_ESC.md` §9, revised 2026-06-03): the
  prose footnote leans bonded-pair (ESC); the written `eq:budget` subtracts total `c` from one
  household budget (CDC). Neither is uniquely required by the current wording.

**Net (muddle resolved 2026-07-27):** default runs and shipped artifacts now agree on ESC end-to-end;
CDC is an explicit opt-in. Any run
must keep the matched **triple `{PermGroFac-fix, calibration files, interpretation}`** consistent
(see MEMORY: "Calibration+solver are an atomic matched pair"). A `[ESC calibration HAZARD]` guard in
`resolve_path` warns if an ESC run silently falls back to CDC discount-factor files.

---

## 6. Pointer table — authoritative sources

| Topic | File |
|---|---|
| Formal CDC vs ESC, the one differing equation, code map | `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` |
| The (1−ς) homotheticity algebra (splurge-out-of-budget) | `BUGS_private/HAFiscal_splurge_budget_inconsistency/equations_paper_and_CDC.md` |
| Scope of homotheticity (ESC-internal, NOT ESC≡CDC) | `BUGS_private/HAFiscal_splurge_budget_inconsistency/_archive/notes_on_bound_pair_equivalence.md` |
| Why targeted/non-welfare aggregates match at each target | `BUGS_private/HAFiscal_splurge_budget_inconsistency/why_results_match_at_target.md` |
| Recursive household Bellman (normalized; "Version A" = CDC-style) | `HAFiscal-bellman-for-matsya.md` |
| Paper equations `eq:model/splurge/utility/budget/income` | `Subfiles/Model.tex` (lines 28–127) |
| Welfare aggregator "inclusive of the splurge" | `Subfiles/Comparing-policies.tex:144` |
| Step-1 wealth concept under ESC (BUG-054 — **FIXED, Option A, 2026-07-27**) | `BUGS_private/HAFiscal_BUG-054_step1_esc_uses_cdc_wealth_correction.md` + `conclusions_private/2026-06-11_esc_step1_wealth_concept_investigation.md` |
| The fitted triples | `Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget{,_CDC,_ESC}.txt` |
