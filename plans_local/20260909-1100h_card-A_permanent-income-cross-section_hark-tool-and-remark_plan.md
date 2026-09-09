# Card A into Econ-ARK: a HARK tool for the cross-sectional distribution of permanent income under growth and mortality, and a MyST REMARK that derives, cites and illustrates it

**Status:** **DEFERRED — LONG-TERM TODO (owner 2026-09-09 ~11:50: "Let's make the execution of this plan a long-term todo item rather than pursuing it immediately").** Not to be executed now; nothing here starts without the owner's word. Written 11:00, revised ~11:30 on the owner's rulings (below). Open when it starts: the choice among the three names in §0 (D1; D2 follows). Every step is gated (per-PR permission; repo creation, tagging and catalog changes are the owner's). Listed under "Long-term" in `plans_local/TODO.md`.

**Owner rulings 2026-09-09 (verbatim where it matters):**
- *"Nobody cares about the history of the 200-quarter wall, etc, the no-cap constraint, the options, etc. This aims to be a
  general-purpose tool anyone can use who wants to have an infinite-horizon model with permanent shocks. The estimation of lambda,
  however, IS relevant as the tool that allows conversion between a 'life-cycle working age income profile' and an
  'infinite-horizon equivalent' that generates the right gini. Target audience: Researchers who may know nothing, and care less,
  about HAFiscal."* → the book's chapter 1 is rewritten (§3.2); HAFiscal appears only as one worked calibration and in the
  acknowledgments.
- Deliverable 3 (HAFiscal consumes the tool): *"Right."*
- D1/D2: three name proposals consistent with HARK's naming; repo and catalog names derived from the tool name (§0).
- D3: author Christopher Carroll; licence Apache 2.0.
- D4: the Markov version ships in the first PR **and is illustrated with an example** (§2.3, §3.2 ch. 6).

**Owner charge (2026-09-09):** *"Make a plan in plans_local/ to: make a high-grade set of HARK tools, well documented with
proper unit testing and an example/ notebook, to implement in HARK what we are doing now for Part A in HAFiscal-Latest/;
[and] a MyST markdown Jupyter book REMARK containing the mathematical derivations, the citations to the literature, and an
illustration of the use of the tool grounded in the history of why we developed it in the context of the HAFiscal-Latest
project (a desire to be able to use TM methods in a model with permanent income shocks where mortality generates a
cross-sectional distribution of permanent income that matches a measured Gini coefficient)."*

**Standing rulings this plan obeys:** maintainability / modularity / usability over speed (2026-09-08); generic tools
that HAFiscal then *imports* (the ENDGAME frame, 2026-08-22); rigorous computational and mathematical descriptions so
other AIs absorb them (2026-09-08); low-hanging fruit first (2026-09-08); one HARK PR per kept card, permission asked per
PR; no email without approval of the exact text. Source card: `Code/HA-Models/docs/tool_cards/CARD-A_permanent-income-distribution-under-growth-and-mortality.md`
("A good", owner 2026-09-08).

**Vocabulary.** *Part A* = the closed-form cross-section of permanent income (Card A). *Tool* = the HARK module. *Book* =
the REMARK. *Pin* = the HARK commit HAFiscal runs on (`llorracc/HARK` branch `hafiscal-pin-2026-08-13`, 0.17.2 @ bfb77471).
*Upstream* = `econ-ark/HARK` main (0.17.3-dev). *Endgame* = HAFiscal's own `perm_income_inequality.py` and the TM's
mixture builder become thin calls into the tool.

---

## 0. Decisions the owner makes before step 1 (defaults proposed so work can start on "go")

| # | decision | proposed default | why it matters |
|---|---|---|---|
| D1 | **Tool name = module name** in `HARK/Calibration/Income/` (the folder whose README reads "tools for calibrating income processes"; its modules are `IncomeTools.py`, `IncomeProcesses.py`; siblings `SCFDistTools.py`, `SSATools.py`, `CPITools.py`, `AssetProcesses.py`) | **three proposals, owner picks** (below) | the module name is also the book's repo and catalog name (D2) |
| D2 | **Book repository and catalog name** | derived from D1: repo `econ-ark/<ToolName>`, catalog entry `REMARKs/<ToolName>.yml` with `name: <ToolName>` (owner ruling) | one name for the tool, the repo and the catalog entry |
| D3 | **Authorship and licence** | **RULED:** author Christopher Carroll; Apache 2.0 for the whole repository (code and text) | goes into `myst.yml`, from which `CITATION.cff` is generated; `LICENSE` = HARK's Apache-2.0 text |
| D4 | **Markov version in the first PR** | **RULED: yes, with an example.** The state-dependent process on any finite ergodic chain (per-state growth factor and permanent-shock variance), the i.i.d. process as the one-state case; see §1 for what it is and §6 for what it costs | it is what HAFiscal's TM integrates over; the endgame needs it |

**D1 — the three proposals** (function names follow HARK's verbs: `calc_` for a computation, `find_` for a solve, as in
`calc_ergodic_dist`, `calc_transition_matrix`, `find_PermGroFacs`; `PermInc`, `Dist`/`Dstn`, `pLvl` are HARK's own abbreviations):

| | tool / module | functions | derived repo and catalog name | for / against |
|---|---|---|---|---|
| **1 (recommended)** | `PermIncDistTools` — `HARK/Calibration/Income/PermIncDistTools.py` | `calc_perm_inc_dist`, `calc_perm_inc_tail_index`, `calc_markov_perm_inc_moments`, `find_growth_scale_for_gini` | `econ-ark/PermIncDistTools`, entry `PermIncDistTools` | exactly the folder's `*Tools.py` family (`IncomeTools`, `SCFDistTools`) and HARK's `PermInc` abbreviation (`LognormPermIncShk`); says what the object is (a distribution of permanent income) |
| 2 | `ErgodicIncomeTools` — `HARK/Calibration/Income/ErgodicIncomeTools.py` | `calc_ergodic_pLvl_dist`, `calc_pLvl_tail_index`, `find_growth_scale_for_gini` | `econ-ark/ErgodicIncomeTools` | HARK's own word for the stationary cross-section (`calc_ergodic_dist`); does not say *permanent* income |
| 3 | `PerpetualYouthIncome` — `HARK/Calibration/Income/PerpetualYouthIncome.py` | `calc_perpetual_youth_pLvl_dist`, `calc_pLvl_tail_index`, `find_growth_scale_for_gini` | `econ-ark/PerpetualYouthIncome` | names the demographic structure that generates the object (Blanchard–Yaari), which is how the literature searches for it; breaks the `*Tools.py` pattern; a *Markov* chain is not implied |

The rest of this plan uses proposal 1's names provisionally; a different choice renames, nothing else changes.

---

## 1. What "Part A" is, precisely (the specification both deliverables implement)

**The process (one group).** Per period, a surviving household's permanent income obeys $p_{t+1} = G_{j_{t+1}}\,\psi_{t+1}\,p_t$ with
$\log\psi \sim N(-\tfrac{s_j^2}{2}, s_j^2)$ (mean one), a state $j$ (employment) following a Markov chain $M$ (the i.i.d. chain
with unemployment rate $u$ is the special case), survival $L$ per period (perpetual youth, Yaari 1965 / Blanchard 1985),
and newborns entering with $\log p_0 \sim N(\mu_0, s_0^2)$. Optionally an age cap $T_{\text{age}}$ (HARK's `T_age`).

**The object.** The stationary cross-sectional law of $p$: the age mixture $\sum_a w_a\,\mathrm{LogNormal}(\mu_a, \sigma_a^2)$,
$w_a \propto L^a$; with one state, $\mu_a = \mu_0 + a(\log G - s^2/2)$, $\sigma_a^2 = s_0^2 + a s^2$ — exact.

**The Markov (state-dependent) version — what it is and what it is not.** *One* finite ergodic chain $M$ (rows $j \to j'$),
whatever its states mean (an employment chain, a macro chain, or HARK's hierarchical macro × micro chain flattened), with a
growth factor $G_j$ and a shock variance $s_j^2$ attached to each state. Examples it covers: growth suspended while unemployed
($G_u = 1$); permanent shocks switched off while unemployed ($s_u = 0$, the older HAFiscal process); both; different drifts by
macro state. Newborns draw their state from a given distribution $\pi_0$ (the chain's stationary law by default). Then, with
$m^j_n = E[\mathbf 1\{j_n = j\} \log p_n]$, $q^j_n = E[\mathbf 1\{j_n = j\}(\log p_n)^2]$, $\pi^j_n = \Pr(j_n = j)$ and
$c_j = \log G_j - s_j^2/2$:
$$\pi_{n+1} = M^\top \pi_n,\qquad m^{j'}_{n+1} = \sum_j M_{jj'}\,(m^j_n + c_{j'}\pi^j_n),\qquad
q^{j'}_{n+1} = \sum_j M_{jj'}\,(q^j_n + 2c_{j'} m^j_n + (c_{j'}^2 + s_{j'}^2)\pi^j_n),$$
two *linear* recursions, $O(T_{\text{age}} J^2)$, exact for the first two moments of $\log p$ in every $(n, j)$ cell; the level's
moments follow the same pattern with $\kappa_j = G_j E[\psi_j] = G_j$ and $\kappa^{(2)}_j = G_j^2 E[\psi_j^2]$ (exact $E[p]$,
$E[p^2]$). The full law in a cell is a mixture over state paths, so the tool represents it by **one Gaussian per $(n, j)$ cell
matched to those moments** (HAFiscal's `_pLvl_markov_mixture_components`): exact mean and variance of $\log p$ and of $p$,
an approximation to the shape within a cell that HAFiscal validated against its own long panel to 0.01 in the Gini. With
$J = 1$ the recursions collapse to the closed form above. The tail index generalizes from a scalar equation to a Perron root:
$\alpha$ solves $\rho\big(L\, M\, \mathrm{diag}(\kappa_j(\alpha))\big) = 1$ with $\kappa_j(\alpha) = G_j^\alpha e^{\alpha(\alpha-1)s_j^2/2}$
(Beare & Toda 2022, *Econometrica*, for Markov-modulated multiplicative processes); bisection on $\alpha$ with a spectral-radius
evaluation at each step. The i.i.d.-with-growth-suspension formula $d = (1-u)\log G$ used in Card A is the $J = 1$ shortcut
that drops the binomial variance of the employed-period count, $a\,u(1-u)(\log G)^2$ — 0.6 % of $a s^2$ at $u = 0.085$ — which the
recursion carries exactly.

**The answers it returns.** Per group and pooled (population shares): mean, median, std of $\log p$, Gini, Lorenz points
(bottom 50 %, top 10 %, top 1 %), the Pareto tail index $\alpha$ (one state: $L\,G^{\alpha}\,E[\psi^\alpha] = 1$,
$E[\psi^\alpha] = e^{\alpha(\alpha-1)s^2/2}$; Markov: the Perron root above), the finiteness verdicts (mean finite iff the
$\alpha = 1$ balance is below one, i.e. $L G < 1$ with one state; variance finite iff $\alpha > 2$), the share of the mean carried
by households older than a given age, and the **conversion tool**: given a *working-life* income-growth profile (what life-cycle
evidence supplies — an average growth rate over a finite working life, by group), the scale $\lambda$ with
$G(\lambda) = 1 + \lambda(G - 1)$ at which the *infinite-horizon* (perpetual-youth) model reproduces a target Gini of permanent
income. Growth for an unbounded life makes the cross-section Pareto and, unscaled, far more dispersed than the data; the pooled
Gini is monotone in $\lambda$, so bisection identifies it from the process alone (no preference parameters enter).

**Reference implementation and numbers to reproduce** (`Code/HA-Models/perm_income_inequality.py`, 259 lines; record
`conclusions_private/2026-08-29_uniform-growth-downscaling_decision.md`): on the HAFiscal calibration ($L = 1 - 1/160$,
$s^2 = 0.003$, $g = 1.421/1.812/1.958$ %/yr, entry levels 6.2/11.1/14.5 with $s_0 = 0.32/0.42/0.53$, $u = 0.085/0.044/0.027$,
shares 0.093/0.527/0.38): pooled Gini **0.709** at $\lambda = 1$, **0.5007** at $\lambda = 0.44$, $\lambda^* = 0.4367$ for 0.50;
tail indices 1.54/1.31/1.23 at $\lambda = 1$ and 2.07/1.91/1.86 at 0.44; $E[p]$ 8.4/17.4/25.0 at 0.44; the capped ($T_{\text{age}}$ = 200)
paper process Gini 0.41. These are the parity targets of §3.

**Not in scope** (Card A "What it is NOT"): life-cycle earnings profiles ($T_{\text{cycle}} > 1$), return heterogeneity, the
transitory component, and the grid/interpolation power-law machinery of HARK #1818 (a separate project by the owner's ruling).

---

## 2. Deliverable 1 — the HARK tool (one PR; ASK before opening it)

Work on a fresh clone of **upstream** `econ-ark/HARK` main (not the pin; Python 3.12 venv), branch `perm-income-cross-section`.

### 2.1 Module `HARK/Calibration/Income/PermIncDistTools.py` (proposal 1's name, provisional)

Public API:

```python
calc_perm_inc_dist(params, *, groups=None, shares=None, t_age=None,
                   n_grid=8000, age_weight_floor=1e-9) -> PermIncDist
```
- `params`: a HARK agent (`IndShockConsumerType` / `MarkovConsumerType`) **or** a plain dict with `PermGroFac`, `PermShkStd`,
  `LivPrb`, `pLvlInitMean`, `pLvlInitStd`, and either `UnempPrb` (i.i.d.) or `MrkvArray` + per-state `PermGroFac`/`PermShkStd`
  (Markov). Duck-typed: read attributes with the same priority chain `sim_birth` uses (memory: getattr chains). Multi-group via
  a list of such objects plus `shares`.
- returns a small dataclass `PermIncDist`: per-group and pooled `stats` (mean, median, std_log, gini, b50, top10, top1),
  `tail_index` per group, `finite_mean` / `finite_variance` flags, `components` = `(w, mu, sigma)` of the mixture (the same
  contract as HAFiscal's `_pLvl_mixture_components`, so the TM can consume it), and `old_share(age)`.
- with `MrkvArray` present (or a `MarkovConsumerType`), the Markov path of §1 is taken automatically; a plain `IndShock`
  parameter set is the one-state case.

```python
calc_perm_inc_tail_index(LivPrb, PermGroFac, PermShkStd, MrkvArray=None) -> float
    # one state: the balance equation by bisection; Markov: the Perron-root equation; inf when no root
calc_markov_perm_inc_moments(MrkvArray, PermGroFac, PermShkStd, LivPrb, pLvlInitMean, pLvlInitStd,
                             MrkvInitDstn=None, t_age=None) -> (age_prbs, pi, m, q)
    # the exact per-(age, state) recursions of §1 (log and level moments)
make_mixture_from_markov_moments(age_prbs, pi, m, q) -> (w, mu, sigma)
find_growth_scale_for_gini(params, target_gini, *, shares, tol=1e-4, **kw) -> float
    # λ by bisection on [0, 1]; raises with both bracket Ginis if the target is outside [Gini(0), Gini(1)]
```
Lorenz points and the Gini come from HARK's existing `get_lorenz_shares(data, weights, percentiles)` applied to the grid
(`data` = $p$ on the grid, `weights` = its probability mass) — adapt the existing wheel; add `calc_gini(data, weights)` next to it
in `HARK/utilities.py` only if the Lorenz helper cannot give the Gini cleanly (one function, tested).

**Docstrings (numpydoc, per HARK's contributing guide) carry the mathematics**: the module docstring states the process,
the mixture, the tail equation and the finiteness conditions exactly as in §1 (this is the "rigorous description other AIs
absorb"); every function states its convention (the newborn's first growth step is deterministic — HARK's `sim_birth`
timing, BUG-003 in HAFiscal — so age $k$ carries $k+1$ growth factors and $k$ shocks). Symbols follow HARK's parameter names
in code and the paper's letters in the Notes; the book checks them against `NOTATION.md` before it introduces any.

### 2.2 Tests `tests/Calibration/test_PermIncCrossSection.py` (pytest; HARK's `tests/` tree)

The pins from Card A, each a separate test:
1. **Degenerate mixture** ($s = 0$, $s_0 > 0$, $G = 1$): Gini equals the lognormal Gini $2\Phi(\sigma/\sqrt2) - 1$ to 1e-6.
2. **Mean** equals $\sum_a w_a e^{\mu_a + \sigma_a^2/2}$ to 1e-10 whenever $L e^{d} < 1$; `finite_mean` False and mean `inf` otherwise.
3. **Tail index** against the closed form for a single-group mixture (and $\alpha \to \infty$ when $G = 1$, $s = 0$).
4. **Markov = one state** when `MrkvArray` is $1 \times 1$ or its rows are identical and the states share $(G, s)$: the recursion's
   mixture reproduces the closed form's mean and variance of $\log p$ to 1e-10; with identical rows but growth suspended in one
   state, the recursion's $E[\log p]$ equals the $(1-u)\log G$ drift formula and its variance exceeds it by exactly the binomial
   term $a\,u(1-u)(\log G)^2$.
4b. **Perron-root tail index** equals the scalar equation's root when all states share $(G, s)$; is finite and larger than the
   naive "growth in every state" root when growth is suspended in unemployment (less growth, thinner tail).
5. **Monotone λ**: pooled Gini increasing in $\lambda$; `solve_growth_scale` hits the target to `tol` and raises outside the range.
6. **HAFiscal parity**: the §1 numbers (0.709, 0.5007, 0.4367, the tail indices, $E[p]$) to 1e-3 from the calibration written
   into the test as a dict — no HAFiscal import.
7. **Simulation agreement** (the integration test with HARK itself): an `IndShockConsumerType` with the HAFiscal-like
   parameters simulated for 400 quarters at 20,000 agents; simulated Gini and mean of `pLvl` within 0.01 / 3 % of the closed form
   (marked `slow`; the tolerance is the MC error, computed in the test from the seed spread).
8. **Age cap**: `t_age=200` reproduces the truncated mixture; Gini drops toward the paper's 0.41 on the HAFiscal calibration.

### 2.3 Example `examples/Calibration/PermIncDistTools.ipynb` (executed by HARK's nbval CI)

Two parts, under a minute together. **One state:** from an `IndShockConsumerType`'s parameters — density and Lorenz curves,
the tail index and Gini as functions of $\lambda$, the finiteness verdicts, the working-life-profile → infinite-horizon
conversion (`find_growth_scale_for_gini`) on a three-group calibration, the age-cap contrast, and the simulation check of
2.2(7) on a small panel. **Markov (the owner's D4 example):** a `MarkovConsumerType` with an employment chain, three
processes side by side — growth in every state, growth suspended while unemployed, shocks also switched off while unemployed —
their cross-sections, tail indices from the Perron root, and how far the one-state $(1-u)\log G$ shortcut is from the exact
recursion. The narrative is the short version of the book's chapters; the book links to it, not the reverse.

### 2.4 Docs and housekeeping

`docs/reference/tools/incomeprocess.rst` gains the automodule line; `HARK/Calibration/Income/README.md` gains a paragraph;
`docs/CHANGELOG.md` (0.17.3 dev) gains one line; ruff clean; `pytest tests/Calibration/test_PermIncCrossSection.py` green;
`pytest --nbval-lax examples/Calibration/PermanentIncome_CrossSection.ipynb` green.

**Gate to ask for the PR:** all of 2.2 green locally, the notebook executed, parity 2.2(6) within 1e-3. Then ASK; the PR text
is Card A plus the test table. Effort: 2 days (Card A's estimate of 1 day did not include the Markov recursion, the simulation
test and the notebook).

---

## 3. Deliverable 2 — the book: a MyST REMARK (mystmd project; ASK before creating the repository)

### 3.1 Skeleton (half a day): copy of `econ-ark/method-of-moderation` `main`, the parts that are template

`myst.yml` (project frontmatter with `doi:` once the concept DOI exists, `github:`, `license: Apache-2.0` for code and content
(ruled), author Christopher Carroll (ruled), `abstract:` file, toc),
`content/paper/` + `content/macros.yml` + `content/references.bib`, `code/` (executable MyST markdown notebooks + tests),
`reproduce.sh` / `reproduce_min.sh` (executable bit set; `set -euo pipefail`; every step exits 0), `binder/environment.yml`
(Python 3.12 + uv adapter), `Dockerfile`, `pyproject.toml` + `uv.lock` (HARK pinned to a git SHA on the tool branch until the
release that carries it, then to the version), `README.md` ≥ 100 non-empty lines from the start, `REMARK.md` with `tier: 3`,
`.github/workflows` (ci, deploy, binder). Lessons from 2026-09-09 baked in: `CITATION.cff` is *generated* by the `cff` export,
so the DOI enters via `myst.yml`; `cli.py lint --tier 3 --include-optional` is run on a full clone (until econ-ark/REMARK#188
merges, the tool lints `main` instead of the tag).

### 3.2 Chapters (MyST markdown; one executable notebook per illustration)

1. **The problem** (for a reader who has never heard of HAFiscal). Infinite-horizon heterogeneous-agent models with permanent
   income shocks — cstwMPC, Krusell–Smith descendants, most HANK calibrations — are perpetual-youth models: households face
   a constant death hazard and are replaced. Life-cycle evidence supplies income *growth* over a finite working life; carried
   into an unbounded life, growth plus replacement makes the cross-section of permanent income Pareto (Champernowne, Wold &
   Whittle, Reed), possibly with an infinite mean or variance, and far more dispersed than measured permanent income (SCF Gini
   ≈ 0.5, `cstwMPC` §3.4). Nobody checks this at calibration time because the closed form is not packaged. The chapter states
   the three questions the tool answers (is the mean finite; is the variance finite; how much of the mean sits in the tail) and
   the conversion it provides: from a working-life growth profile to the infinite-horizon-equivalent growth rate that reproduces
   a target Gini. HAFiscal is mentioned once, as the project the tool was built for, with the pointer to its calibration used as
   the worked example in chapter 6.
2. **The process and its stationary law.** Perpetual youth (`yaari1965uncertain`, `blanchardFinite`); the log random walk
   with drift and Gaussian reset; the geometric age mixture; the exact Markov-employment recursion (from
   `conclusions_private/2026-06-13_pLvl_employed_steady_state_analytical.md`); the newborn timing convention; the truncated
   mixture under an age cap.
3. **The Pareto tail.** Reed's double Pareto-lognormal (Reed 2001; Reed & Jorgensen 2004 — to be added to `references.bib`,
   not in the SST), the reinjection–growth balance and its lineage (Champernowne 1953, Wold & Whittle 1957, Kesten 1973,
   Gabaix 2009 — to be added; `benhabibWealth`, `StachurskiToda2019JET`, `maTodaRich` are in the SST), the moment
   conditions, and what an infinite variance does to aggregation (`harmenberg2021consumption`, HAFiscal's BUG-038/BUG-092 story).
4. **Inequality measures on a mixture.** Lorenz curve and Gini of a lognormal mixture; the numerical algorithm (log grid,
   $\pm 6\sigma$, age sum to the $10^{-9}$ weight, error control) and its cost; the pooled cross-section by superposition.
5. **Converting a working-life profile into an infinite-horizon equivalent.** The life-cycle growth rate as a working-life
   average; what "the same growth for ever" does to dispersion; the scale $\lambda$ and the monotonicity of the pooled Gini in
   it; bisection; why $\lambda$ is identified from the process alone, before any preference parameter; how to report it.
6. **Illustrations (executable).** (a) One state, three education groups on a published calibration (HAFiscal's, cited as
   such and nothing more): densities, Lorenz curves, tail index and Gini as functions of $\lambda$, the age profile of who earns
   the income, the conversion to the infinite-horizon-equivalent growth rates, a small HARK simulation agreeing with the closed
   form. (b) **Markov:** an employment chain with growth suspended, then shocks also off, in unemployment — cross-sections, tail
   indices from the Perron root, and the size of the one-state shortcut's error. Every number in the prose is produced by the
   notebooks (a `verify_prose_numbers.py`-style check, as method-of-moderation does).
7. **Using the tool** (API reference by example) and **limits** (Card A's "What it is NOT").

Citations use the SST keys where they exist (`cstwMPC`, `ccdft-HAFiscal` / `HAFiscalRR`, `harmenberg2021consumption`,
`benhabibWealth`, `StachurskiToda2019JET`, `maTodaRich`, `castaneda03`, `krusellSmith_heterogeneity_JPE98`, `DeNardi2019`,
`Piketty_Saez2003`, `yaari1965uncertain`, `blanchardFinite`); Reed 2001, Reed–Jorgensen 2004, Champernowne 1953, Wold–Whittle
1957, Kesten 1973, Gabaix 2009 and **Beare–Toda 2022** (the Markov-modulated Pareto exponent) are added to the book's
`references.bib` and, on the owner's word, to the SST.

### 3.3 Tier-3 checklist before the owner tags

`reproduce_min.sh` < 5 min (tests + HTML); `reproduce.sh` (tests + PDF + executed notebooks + output verification) exits 0
and leaves the tree clean; README ≥ 100 non-empty lines; `REMARK.md` `tier: 3`; `doi:` in `myst.yml` → `CITATION.cff`;
`cffconvert --validate` (expect only the upstream bare-ORCID complaint); catalog lint Tiers 1–3 on a full clone; CI green.
Then the owner's steps: annotated tag `v1.0.0`, GitHub release → Zenodo (concept DOI known beforehand only if the Zenodo
integration is enabled first; otherwise tag v1.0.0, archive, then a v1.0.1 carrying the DOI), PR to `econ-ark/REMARK` adding
`REMARKs/PermIncCrossSection.yml`. Effort: 1.5–2 days after the tool exists (the mathematics exists in Card A and the 2026-06-13 derivation; the
Markov chapter's Perron-root section is new; the illustrations reuse the HARK example).

---

## 4. Deliverable 3 — HAFiscal consumes the tool (the endgame for Part A; ASK before touching the production path)

After the HARK PR merges: cherry-pick the tool onto the pin branch (`llorracc/HARK` `hafiscal-pin-2026-08-13`, Python ≥ 3.10
compat — the module is pure numpy and needs nothing newer); bump HAFiscal's pin; make `perm_income_inequality.py` a thin wrapper
that builds the parameter dict from `EstimParameters` and calls the tool (its CLI and markdown row unchanged; a test asserts
the §1 numbers still print); switch `tm_methods._pLvl_markov_mixture_components` to `mixture_from_markov_moments` behind a
**byte-identity gate** on the TM outputs (the mixture feeds the TM's income integration and the MC's analytic seed; the
reference bands `make welfare-check` and the Step-5a multiplier goldens must be unchanged). Both switches are separate
commits, each with its gate output in the message. Effort: half a day plus one reference-band run. This is the step that turns
"HAFiscal has a copy" into "HAFiscal uses HARK" for Part A.

---

## 5. Order, gates, effort

| step | deliverable | gate | ASK | effort |
|---|---|---|---|---|
| 0 | rulings D1–D4 | — | owner | — |
| 1 | HARK module + tests + notebook + docs on a branch | 2.2 all green; parity 1e-3; nbval; ruff | before `gh pr create` | 2 days |
| 2 | book skeleton + chapters 1–7 + illustration | 3.3 checklist; `reproduce.sh` rc 0, clean tree | before creating the econ-ark repo | 1.5–2 days |
| 3 | HAFiscal consumes the tool | byte-identity on TM outputs; reference bands unchanged | before editing `tm_methods.py` | 0.5 day + a band run |
| 4 | owner: HARK merge; book tag + release + catalog PR | catalog lint on the tag | owner / Alan | — |

Total ≈ 4–5 working days; the first PR-able deliverable (step 1) after 2. Steps 1 and 2 can overlap once the API is fixed
(the book pins the branch SHA). Nothing here needs compute beyond a laptop; no overnight batteries.

## 6. Hazards known in advance

- **Timing conventions.** HARK's `sim_birth`/`get_shocks` order decides whether age $k$ carries $k$ or $k+1$ growth factors;
  test 2.2(7) against HARK's own simulator is the arbiter, not the HAFiscal code (which carries the BUG-003 convention).
- **`IndShock` vs `Markov` unemployment.** HARK's `IndShockConsumerType` applies growth and permanent shocks in every state
  (one-state case); state-dependent growth or shocks need a `MarkovConsumerType` and the Markov path. The docstring says which
  HARK type gives which.
- **What the Markov version approximates.** Exact first two moments of $\log p$ and of $p$ per (age, state) cell; the shape
  within a cell is one Gaussian (a mixture over state paths in truth). The docstring says so; test 2.2(7) run on a
  `MarkovConsumerType` panel bounds the Gini error (HAFiscal: 0.01). An exact path-count enumeration is possible for
  two-state chains at $O(T^2)$ and is out of scope unless the bound fails.
- **Age cap.** HARK's `T_age` kills at a fixed age; the truncated mixture is the exact object under it (test 2.2(8)); the book's
  chapter 1 explains why HAFiscal removed it.
- **Infinite moments.** `finite_mean`/`finite_variance` are computed from the balance equation, not from the grid (a grid always
  returns a number); the tool reports both so a calibrator sees the difference.
- **Bibliography.** Reed / Reed–Jorgensen / Champernowne / Wold–Whittle / Kesten / Gabaix are not in the SST; the book's own
  `references.bib` carries them; adding them to `texmf-local` is the owner's call.
- **Python versions.** Upstream HARK development on 3.12; the pin is ≥ 3.10; the module must stay pure numpy/scipy so the
  cherry-pick is clean.

## 7. Where this sits in the larger programme

This is chapter 1 of the arc A → C → B → E if the owner keeps the one-book-per-arc structure recommended on 2026-09-09; the
chapter is written self-contained so it can be lifted into that book unchanged. Cards B, C, E remain as written under review
(`Code/HA-Models/docs/tool_cards/`); their plans wait on rulings. Related open items: econ-ark/method-of-moderation#23 (the
template's own Tier-3 finish, with Alan), econ-ark/REMARK#188 (the catalog lint tag fix).
