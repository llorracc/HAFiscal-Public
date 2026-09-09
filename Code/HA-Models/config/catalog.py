"""Per-setting catalog: the single source of truth for HAFiscal config worlds.

Each results-affecting or improvement setting is classified ONCE here, with the
value it takes in the canonical `default` world and the value the published paper
("QE") used. The worlds are then *derived* (see `resolve_world`), so they cannot
drift apart the way the hand-maintained `reproduce.sh` profiles did.

Taxonomy (owner ruling 2026-06-13;
conclusions_private/20260613_config-worlds-definition-default-legacy.md):

- BUG_FIX        — corrects something unambiguously wrong; MANDATORY in EVERY
                   world. `default` value == `as-corrected` value == canonical.
- IMPROVEMENT    — NOT a bug fix and result-neutral, just better (faster/cleaner).
                   ON in `default`; OFF (== paper value) by default in
                   `as-corrected`, but individually OPT-IN (e.g. as-corrected+gicx).
- DISCRETIONARY  — a legitimate choice that DOES change results; `default` uses
                   the canonical (post-paper) choice, `as-corrected` reverts to
                   the paper's choice.

The deciding question between IMPROVEMENT and DISCRETIONARY is: *does it
materially change the substantive results?* No -> IMPROVEMENT. Yes -> DISCRETIONARY.

CERTIFIED NUMERICS (owner ruling 2026-08-26): an IMPROVEMENT that has been rigorously
tested to leave the estimates unchanged for asymptotically large samples (a
`certification` record on the row) is ALWAYS applied in `as-corrected` as well
(`as_corrected` == canonical). The `as-corrected` world is therefore the paper's
ECONOMICS + all bug fixes + the certified numerics; the paper's own numerical method
remains reproducible by explicit env (e.g. HAFISCAL_UI_STATE_ENCODING=legacy,
HAFISCAL_MC_SHUFFLE=0) and is kept as a reference arm in the archives.

This module is pure data + pure functions. It does NOT touch os.environ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --- categories -------------------------------------------------------------
BUG_FIX = "bug-fix"
IMPROVEMENT = "improvement"
DISCRETIONARY = "discretionary"
CATEGORIES = (BUG_FIX, IMPROVEMENT, DISCRETIONARY)
CERTIFICATION_KINDS = ("exact-relabeling", "asymptotic", "tolerance")   # C9, 2026-08-28
BOTH_WORLDS_KINDS = ("exact-relabeling", "asymptotic")

# Worlds
DEFAULT = "default"
AS_CORRECTED = "as-corrected"
WORLDS = (DEFAULT, AS_CORRECTED)


@dataclass(frozen=True)
class Setting:
    """One results-affecting or improvement configuration setting.

    Attributes
    ----------
    name : short human key (also used as the improvement toggle name).
    env_var : the HAFISCAL_* env var, or None if not env-controlled (e.g. a
        Python-level calibration constant).
    category : one of CATEGORIES.
    canonical : value in the `default` world (and the fixed value for BUG_FIX).
    paper : value the published paper / QE methodology used. For BUG_FIX this is
        the buggy pre-fix value (recorded for provenance; NOT used by any world).
    estimation_only : True if it only affects Step-1/2 estimation outputs, i.e.
        inert for a multiplier/welfare run that loads saved calibration.
    coupling : free-text note on cross-setting constraints (e.g. matched-triple
        BUG-049: interpretation/GICx imply a matched DiscFacEstim file).
    confirm : non-empty if the paper value still needs owner/file confirmation.
    evidence : why this category + values.
    refs : provenance citations.
    """

    name: str
    env_var: Optional[str]
    category: str
    canonical: str
    paper: str
    estimation_only: bool = False
    coupling: str = ""
    confirm: str = ""
    evidence: str = ""
    refs: tuple = ()
    # Optional explicit as-corrected value, for env vars that carry TWO axes in
    # one value (a fix on/off axis plus a form/variant axis). None (the default)
    # preserves the plain category semantics. Currently UNUSED: added 2026-07-23
    # during the pf_decay form deliberation, whose FINAL ruling (the published
    # naive-linear was the bug, so powerlaw restoration IS the fix) needs no
    # override — kept because the schema capability and its guard-test branch
    # are correct and cheap.
    as_corrected: Optional[str] = None
    # Certification (owner ruling 2026-08-26; KINDS added 2026-08-28, infra plan C9): path of the
    # record certifying the IMPROVEMENT, and what the certificate says --
    #   "exact-relabeling": the same computation under another encoding (row-for-row identical
    #                       inputs, e.g. the extension-state UI encoding carrying the paper's policy);
    #   "asymptotic":       leaves the estimates unchanged for asymptotically large samples
    #                       (e.g. the stratified shuffle);
    #   "tolerance":        reproduces the reference within STATED bounds (`tolerance`: cell -> bound),
    #                       a documented residual, NOT numerics-equivalence.
    # World rule: exact-relabeling / asymptotic rows are applied in BOTH worlds (as_corrected ==
    # canonical, guard below); a tolerance row is WORLD-SCOPED (on where the catalog says, off
    # elsewhere: as_corrected stays the paper value).
    certification: str = ""
    certification_kind: Optional[str] = None
    tolerance: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"{self.name}: bad category {self.category!r}")
        if self.certification_kind is not None and self.certification_kind not in CERTIFICATION_KINDS:
            raise ValueError(f"{self.name}: bad certification_kind {self.certification_kind!r}")
        if bool(self.certification) != (self.certification_kind is not None):
            raise ValueError(f"{self.name}: certification path and certification_kind go together")
        if self.certification and self.category != IMPROVEMENT:
            raise ValueError(f"{self.name}: only an IMPROVEMENT row can carry a certification")
        if self.certification_kind in BOTH_WORLDS_KINDS and self.as_corrected != self.canonical:
            raise ValueError(f"{self.name}: a certified-numerics row ({self.certification_kind}) must be "
                             f"applied in both worlds (as_corrected == canonical)")
        if self.certification_kind == "tolerance":
            if not self.tolerance:
                raise ValueError(f"{self.name}: a tolerance certification must state its bounds")
            if self.as_corrected is not None and self.as_corrected == self.canonical:
                raise ValueError(f"{self.name}: a tolerance-certified row is world-scoped, not both-worlds")

    @property
    def certified_numerics(self) -> bool:
        """True for the both-worlds kinds (exact-relabeling / asymptotic); False for tolerance."""
        return self.certification_kind in BOTH_WORLDS_KINDS


# ---------------------------------------------------------------------------
# THE CATALOG
# ---------------------------------------------------------------------------
# Values are stored as strings exactly as the env var is read (so the resolver
# can export them verbatim). `theGICfactor` is the one non-env (Python) constant.

CATALOG: tuple[Setting, ...] = (
    # ----- BUG FIXES (canonical in every world) -----------------------------
    # (ui_state_encoding was the first row here until 2026-08-26; reclassified
    #  IMPROVEMENT -- see the IMPROVEMENTS section. BUG-043 withdrawn, RECONCILED-005.)
    Setting(
        name="welfare6_fix_dur_avg",
        env_var="HAFISCAL_WELFARE6_FIX_DUR_AVG",
        category=BUG_FIX,
        canonical="on",
        # PROVENANCE CORRECTED 2026-08-27 01:50 (attribution ladder): the PUBLISHED computation
        # (HAFiscal-QE Welfare.py:71-78) applies felicity to each recession-duration panel and THEN
        # weights by the duration probabilities -- E[u(c)], the correct order. The u(E[c]) formula
        # existed only in the revision's own run_hybrid_welfare6.py:welfare6_mc() (the 'legacy'
        # of the welfare6 battery, not of the paper), so paper='on' -- a defect of the revision's
        # pipeline, caught and fixed; never in the published numbers (which is why the published
        # UI cells sit beside the bug-fixed ones while toggling the fix off moves them -16 %).
        paper="on",
        evidence="BUG-046: the welfare6 battery's welfare6_mc() computed u(E[c]) != E[u(c)] for "
                 "concave u (Jensen) -- a defect of the revision's welfare machinery; the fix "
                 "restores the published order (per-duration u, then weights). Ladder 2026-08-27: "
                 "toggling it off moves ui_rec -16 %, ui_rec_AD -13 %, check/taxcut <1 %.",
        refs=("BUGS_private/HAFiscal_BUG-046_welfare6_jensen_duration_average.md",
              "conclusions_private/2026-05-16_canonical_config_recommendation.md"),
    ),
    Setting(
        name="pf_decay_extrap",
        env_var="HAFISCAL_PF_DECAY_EXTRAP",
        category=BUG_FIX,
        canonical="1",
        paper="0",
        evidence="BUG-061/062: with the flag off, the 2D AggShock cFunc follows the "
                 "top segment's slope forever above the solve grid (naive-linear "
                 "extrapolation, measured ~34% too high at m=1300), and the TM "
                 "kernel evaluates that region up to dist_aGrid_max=1300. FINAL owner ruling "
                 "2026-07-23 (after a same-day deliberation that briefly routed "
                 "as-corrected through 'exp'): the published naive-linear WAS the "
                 "bug, so the POWERLAW restoration is itself the fix -- canonical "
                 "'1' in BOTH worlds. 'exp' survives only as a diagnostic opt-out "
                 "(the PR-3-era form, kept for T-cascade/RECONCILED-002 "
                 "reproduction); '0' = the as-shipped naive-linear path, reserved "
                 "for QE reproduction only. Default-ON since 2026-07-23.",
        refs=("BUGS_private/HAFiscal_BUG-062_2D_aggshock_pf_decay_extrapolation.md",
              "conclusions_private/2026-07-23_solve_grid_count_convergence.md",
              "RECONCILED_private/RECONCILED-002_pf-decay-exp-vs-powerlaw-form.md"),
    ),
    Setting(
        name="ui_state_encoding",
        env_var="HAFISCAL_UI_STATE_ENCODING",
        category=IMPROVEMENT,
        # RECLASSIFIED 2026-08-26 (owner ruling; was BUG_FIX canonical 'bug_fix' since
        # 2026-05-16). Improvement A: the UI extension delivered in INCOME on a chain with
        # explicit extension states (2 + UBspell_extended = 7 micro states under the paper's
        # window), the PLAIN chain in every scenario. The paper's window reproduces the
        # published freeze EXACTLY as a state relabeling (derivation: ui_extension_rule.py;
        # schedule test: test_ui_extension_schedule.py; HS_Only equivalence gate G1), so it is
        # result-neutral. The case AS PLANNED was the speedup: identical Markov dynamics across
        # the policy/no-policy pair keep the stratified-shuffle engine's per-agent CRN coupling
        # exact for the UI welfare cells (under 'legacy' the freeze merges origin states, so
        # the quota-exact rank assignment differs between recessionUI and recession). MEASURED
        # at gate G1 (HS_Only, 6 seeds x 2 arms, stratified shuffle, own AD loops, 2026-08-26):
        # UI-cell across-seed variance ratio legacy/calendar = 1.3 (ui_rec) and 2.0 (ui_rec_AD),
        # not significant at 6 seeds; the May 'x15' was against the PLAIN-shuffle engine,
        # which the stratified fix (BUG-044, June) already retired. So the precision gain is
        # small-to-nil in the canonical engine; what A delivers is one chain in every scenario
        # (the extension as income, not as a scenario-specific transition matrix) and the
        # substrate for ui_extension_policy (Improvement B), at 7 vs 4 micro states in the TM.
        canonical="calendar",
        paper="legacy",
        # CERTIFIED NUMERICS (owner 2026-08-26): applied in as-corrected too -- the paper's
        # UI policy one-for-one on the extension-state chain, with the stratified shuffle
        # (mc_shuffle) as the other half of the same package. The paper's 4-state freeze stays
        # reproducible by explicit HAFISCAL_UI_STATE_ENCODING=legacy (reference arm).
        as_corrected="calendar",
        certification="conclusions_private/2026-08-26_ui-numerics-package_certification.md",
        certification_kind="exact-relabeling",
        coupling="Under 'legacy' the recessionUI scenario changes the TRANSITION matrices (the "
                 "freeze), and the stratified engine's rank-quota pairing is then only "
                 "approximate: catastrophic on ui_norec (Baseline 2.28 / 5.90 vs 0.85), ~8% high "
                 "on the Baseline recession UI cells -- record section 7. That is why the package "
                 "is applied as ONE unit in both worlds; 'legacy' must be run non-shuffled. "
                 "ui_extension_policy is inert under "
                 "'legacy' (the freeze IS the paper's window) and under 'bug_fix' (the 2026-05-16 "
                 "six-state recession-conditional rule -- a DIFFERENT policy, kept only to "
                 "reproduce the 05-16..08-26 numbers). Chain size follows the policy under "
                 "'calendar' (7 window / 6 history); solution-cache keys carry both axes.",
        evidence="BUG-043 ('legacy under-delivers by 1Q') read only the first two sentences of "
                 "the paper's UI paragraph; traced with the simulation's own timing, the freeze "
                 "implements every clause (onset cohort 4 quarters, one-quarter-in 3, no further "
                 "extensions, unaffected by the recession ending) -- WITHDRAWN, RECONCILED-005. "
                 "The 05-16 'fix' was the only policy change in the chain and is now opt-in. "
                 "Not a bug fix, so it does not enter the as-corrected workflow (owner 2026-08-26).",
        refs=("plans/20260826-0800h_ui-extension-calendar-window-encoding_plan.md",
              "RECONCILED_private/RECONCILED-005_ui-extension-freeze-vs-six-state-rule.md",
              "conclusions_private/2026-08-26_figure-changes_check-irf-and-ui-cumulative-multiplier.md",
              "conclusions_private/2026-05-11_shuffle_ui_welfare_crn_breakdown.md",
              "Code/HA-Models/ui_extension_rule.py"),
    ),
    Setting(
        name="t_age_cap",
        env_var="HAFISCAL_T_AGE",
        # OWNER RULING 2026-08-27 16:40: a CORRECTION (BUG_FIX). The published code was inconsistent with itself
        # -- its Step 2 estimated WITHOUT a maximum age (HaFiscal-QE EstimParameters.py:210, T_age None) while its
        # Step 5 simulated WITH one (Parameters.py:238, T_age=200), executing 28.5 % of each cohort at a wall the
        # paper never states, under decision rules solved for a constant hazard. Mandatory in EVERY world: the
        # as-corrected world is uncapped from this ruling on; its matched calibration is the uncapped perm-off
        # estimate (= the committed default-world ESC file, BUG-095; installed as _ESC_ascorrected 2026-08-27).
        # History: IMPROVEMENT at the 07-27 epoch, DISCRETIONARY ("modification") 08-26, BUG_FIX 08-27.
        category=BUG_FIX,
        canonical="none",
        paper="200",
        coupling="Calibration-matched: the default-world DiscFacEstim_*_ESC files are "
                 "estimated UNCAPPED (epoch 2026-07-27); as-corrected loads its own "
                 "_ascorrected calibration estimated under the paper config.",
        evidence="Owner epoch 2026-07-27 (belief consistency): the QE-era 200-quarter "
                 "maximum-age cap (die at 75; Crawley 2022 commit 770d4d04, "
                 "BUG-038-restored, documented NOWHERE in the paper) executes 28.5% of "
                 "each cohort at the wall under memoryless LivPrb=1-1/160, raising "
                 "effective mortality 40% while agents' decision rules assume constant "
                 "hazard -- beliefs != process. Uncapped, beliefs are exact, the "
                 "measured wealth-tail exponent matches the perpetual-youth Kesten "
                 "root, and re-estimation moved beta by ~4e-4 while fits improved up "
                 "to 5x (College 0.716 vs 3.75): the paper's parameters were right, "
                 "the wall was the distortion. Deliberate model change (the QE code "
                 "intended the cap) that CHANGES RESULTS -- aggregate permanent income is "
                 "2.43x higher uncapped (base AggIncome 472,933 vs 194,569), so every '% of "
                 "aggregate income' statistic shrinks mechanically -- hence a MODIFICATION: "
                 "DISCRETIONARY (owner ruling 2026-08-26; filed IMPROVEMENT at the 07-27 epoch "
                 "although the catalog's own rule assigns result-changing choices to "
                 "DISCRETIONARY). default = uncapped; as-corrected = the paper's cap. The revised "
                 "paper presents policy responses per dollar of outlay for this reason (plans/"
                 "20260826-2100h_presenting-the-revision_plan.md).",
        refs=("conclusions_private/2026-07-27_belief-consistent-world_epoch_evidence.md",
              "plans/20260726_belief-consistency_plan.md",
              "conclusions_private/2026-07-26_peratom_battery_verdict.md"),
    ),
    Setting(
        name="dist_tail_state",
        env_var="HAFISCAL_DIST_TAIL_STATE",
        category=IMPROVEMENT,
        canonical="off",
        paper="off",
        estimation_only=True,
        coupling="GLOBAL env default stays 'off' in BOTH worlds -- the Step-5a path "
                 "refuses tail-state TMs by scope (and is measured top-indifferent at "
                 "3e-5). The DEFAULT world's ESTIMATION surface gets 'on' via a "
                 "world-aware os.environ.setdefault at the estim_phase2_tm_a entry "
                 "point (the installed calibration was estimated with it); "
                 "as-corrected estimation keeps it off. NOT applied via "
                 "resolve_world -- entry-point-scoped by design.",
        evidence="Dynamics-level Pareto tail state (plan P4'): the TM lottery piles "
                 "above-top mass at the top node and distorts the near-top dynamics; "
                 "the tail state carries the tail analytically (per-atom Kesten "
                 "alpha), making ergodic moments ~flat in the dist-grid top "
                 "(ladder: 13-21x flattening; every top 500-2900 inside every "
                 "epsilon tier).",
        refs=("conclusions_private/2026-07-26_peratom_battery_verdict.md",
              "Code/HA-Models/decay_form/tail_state_DERIVATION_20260726.md"),
    ),
    # ----- (part of the fix above since 2026-08-24; was an improvement) ------
    Setting(
        name="pf_decay_q_measured",
        env_var="HAFISCAL_PF_DECAY_Q",
        category=BUG_FIX,
        canonical="measured",
        paper="slope",
        coupling="Only meaningful with pf_decay_extrap ON in the powerlaw form. "
                 "Selecting 'measured' (alias 'local2') ALSO switches the solve "
                 "grid to the per-group K*hbar top (467/551/591 at K=3) with the "
                 "count basis 192 (density-held); 'slope' restores the legacy "
                 "40/48 grid. RECLASSIFIED BUG_FIX 2026-08-24 (owner ruling, "
                 "BUG-089): the slope-derived exponent is biased on short grids "
                 "and, through the near-unit contraction of the most patient "
                 "atoms, biases their WHOLE policy (~1.2% at the certified "
                 "College top atom on the K=1 grid); the measured two-secant Q "
                 "on the K*hbar grid is the correct estimate, so it is canonical "
                 "in BOTH worlds — as-corrected included. (Supersedes the "
                 "2026-07-23 as-corrected combination {powerlaw, Q='slope', "
                 "top-40, count-48}, which in fact never ran: the runtime "
                 "already applied 'measured' there.) The exp-vs-powerlaw form "
                 "choice is results-neutral at <=7e-4 (T1c, RECONCILED-002).",
        evidence="The measured two-secant local exponent replaces theory/slope "
                 "pins (in-range exponents match no closed-form anchor; the "
                 "slope-Q at the legacy grid top is unidentified, T=40 << h~197). "
                 "College objective at count-converged numerics: 4.96 (linear) -> "
                 "4.35 (exp) -> 4.14 (pl-slope@40) -> 3.75 (measured@591). "
                 "Calibration-robust: Tier-2 re-estimation moves beta <=0.3% and "
                 "the configs' optima agree.",
        refs=("plans/20260722_local-two-secant-tail-q_plan.md",
              "conclusions_private/2026-07-23_solve_grid_count_convergence.md",
              # the Step-1 grid-only default flip pins `measured` in its default stack
              "conclusions_private/2026-08-21_step1-grid-only-default-flip.md"),
    ),
    Setting(
        name="tm_a_indexed",
        env_var="HAFISCAL_TM_A_INDEXED",
        category=BUG_FIX,
        canonical="1",
        paper="0",
        evidence="BUG-033: m-indexed TM is structurally biased under "
                 "splurge-in-budget (budget-identity violation); a-indexed is correct.",
        refs=("BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md",),
    ),
    Setting(
        name="mc_shuffle",
        env_var="HAFISCAL_MC_SHUFFLE",
        category=IMPROVEMENT,   # RECLASSIFIED 2026-08-26 (owner): certified numerics, on in BOTH worlds
        canonical="1",
        paper="",  # off -- the paper's MC was non-shuffled (but already paired policy/no-policy runs by
                   # replaying the same *_fixed_hist shock histories; the pairing is not new)
        as_corrected="1",
        certification="conclusions_private/2026-08-26_ui-numerics-package_certification.md",
        certification_kind="asymptotic",
        coupling="MEASURED 2026-08-26 (gate record 2026-08-26_ui-extension_gate-G1_HS_Only.md "
                 "section 7): on the paper's 4-state FREEZE (HAFISCAL_UI_STATE_ENCODING=legacy, the "
                 "as-corrected world since 2026-08-26) the stratified engine's rank-quota coupling "
                 "breaks for the UI scenarios (the freeze merges origin-state groups): Baseline "
                 "ui_norec 2.28 / 5.90 vs the published 0.85, HS_Only 6-seed SD 0.41 vs 0.02. The "
                 "paper's NON-shuffled engine is sane there (HS_Only ui_norec 0.780 +- 0.011; "
                 "Baseline seed 0: 0.82 / 1.92 / 2.23 vs published 0.85 / 1.82 / 2.13). The "
                 "as-corrected battery therefore runs HAFISCAL_MC_SHUFFLE=0 by EXPLICIT env "
                 "(p3b_ac_nshuf_m5.sh) pending the owner's ruling: an as_corrected='' override on "
                 "this row (the fix corrected an IMPROVEMENT the as-corrected world does not "
                 "otherwise adopt), or opting Improvement A (calendar) into as-corrected so the "
                 "shuffle has a chain it can couple. The '27-29% swings' below were not "
                 "reproduced at HS_Only (non-shuffled UI-cell SE 2.8% at 6 seeds).",
        evidence="Owner ruling 2026-08-26 (supersedes the 2026-06-13 'bug-fix' classification): the "
                 "stratified shuffle + policy/no-policy pairing on the extension-state chain is the "
                 "second half of the certified numerics package -- rigorously tested to leave the "
                 "estimates unchanged for large samples, and ALWAYS used in as-corrected. Measured "
                 "gain vs the paper's engine (HS_Only, 6 seeds): variance ratio 1.8 (ui_rec, "
                 "ui_rec_AD), 1.3 (ui_norec), ~2.6 (check cells), 1-2 (tax cut); the May 'x15' was "
                 "against the plain-shuffle-on-freeze arm, 4-6x noisier than the paper's engine. "
                 "The 2026-06-13 evidence ('27-29% swings between replicates without the shuffle') "
                 "was not reproduced at HS_Only (non-shuffled UI-cell SE 2.8% at 6 seeds).",
        refs=("conclusions_private/2026-06-10_welfare_method_unified_MC.md",
              "conclusions_private/20260613_config-worlds-definition-default-legacy.md"),
    ),
    Setting(
        name="shuffle_mrkv_transition",
        env_var="HAFISCAL_SHUFFLE_MRKV_TRANSITION",
        category=IMPROVEMENT,   # part of the certified numerics package (2026-08-26); was BUG_FIX
        canonical="stratified",
        paper="shuffle",
        as_corrected="stratified",
        certification="conclusions_private/2026-08-26_ui-numerics-package_certification.md",
        certification_kind="asymptotic",
        coupling="The plain 'shuffle' value is the +8.26%-UI footgun and must "
                 "NEVER be selected by a world; only 'stratified' is used. "
                 "(QE-repro of the footgun world is the old branch's job.)",
        evidence="BUG-044 / HARK PR #1776: stratified = quota-exact counts AND "
                 "CRN-preserving; agrees with non-shuffle at ui_rec +0.05%.",
        refs=("conclusions_private/2026-06-10_welfare_method_unified_MC.md",),
    ),
    Setting(
        name="shuffle_newborn_fix",
        env_var="HAFISCAL_SHUFFLE_NEWBORN_FIX",
        category=IMPROVEMENT,   # part of the certified numerics package (2026-08-26); was BUG_FIX
        canonical="transition",
        paper="off",
        as_corrected="transition",
        certification="conclusions_private/2026-08-26_ui-numerics-package_certification.md",
        certification_kind="asymptotic",
        evidence="BUG-044 companion: newborn marginal-distribution correction; "
                 "'transition' matches the non-shuffle marginals.",
        refs=("conclusions_private/2026-06-10_welfare_method_unified_MC.md",),
    ),
    Setting(
        name="shuffle_mrkv_strata",
        env_var="HAFISCAL_SHUFFLE_MRKV_STRATA",
        category=IMPROVEMENT,   # OPT-IN. Adopted 2026-09-07 ("OK, I accept this analysis. Implement"); REVERTED 2026-09-08
                                # (owner: "Revert to plain Hamilton -- restore from history and re-bless").
        canonical="",           # REVERTED 2026-09-08 to the paper's plain engine (was "p:5" from 2026-09-07 21:48). At Baseline's
                                # occupancy the ESTIMAND depends on the strata count -- p:2 minus p:5 = -0.89 % +/- 0.20 % on the UI
                                # cell (z 4.6, same machine, 6/6 seeds) -- because the dropout cohorts' unemployed source states hold
                                # 2-71 households (quintiles of 1-14); the Econ-1 N-ladder null FAILED at Baseline (z 4 at 100k,
                                # decay ~N^-0.77). Decision record: conclusions_private/2026-09-08_strata-shuffle-revert-to-plain-hamilton_decision.md
        paper="",               # unset: the certified engine's state-only quotas (the paper had no shuffle at all)
        # as_corrected=None -> the paper value: OFF in both worlds. The asymptotic certification the Econ-1 plan
        # requires was run 2026-09-07/08 and FAILED at Baseline; HS_Only passed only because its whole panel sits in one
        # agent type (quintiles of hundreds). Re-adoption needs an occupancy-aware strata count AND a passing ladder.
        coupling="FORCES Madow rounding of the within-stratum quotas (small strata cannot use Hamilton), so "
                 "adopting it is two changes: see shuffle_mrkv_rounding. Strata = quintiles of the CURRENT "
                 "period's pLvl within each source state (both that and initial-income strata are unbiased; "
                 "the code comment said 'initial' until 2026-09-07). Explicit env always wins. Since the 2026-09-08 "
                 "revert UNSET means the plain engine again; drivers still PIN both flags in every arm (guard "
                 "test_mrkv_strata_arm_pinning.py) so a future flip cannot silently change an arm's meaning.",
        evidence="A/B 2026-09-07 (dell, S=5 CRN-paired, the current default world; three arms: record / Madow "
                 "control / strata): UI per-seed SD 3.49/3.93 % -> 2.11/2.37 % (variance x0.37/0.36 vs the record "
                 "incl. the rounding; x0.57/0.66 for the strata alone); means within 0.4 % everywhere, the knob "
                 "alone check_rec_AD +0.00 % +- 0.05 %, UI +0.39/+0.07 % +- 1.0/1.2 %; the 08-28 measurement on "
                 "the Gini-0.70 panel gave x0.37-0.44. Unbiased by construction: quotas exact within strata, each "
                 "household's marginal probability unchanged (test_mrkv_strata.py). Owner's reading of the "
                 "mechanism accepted 2026-09-07 19:40. REVERT 2026-09-08: the granularity ladder (Baseline 40k, equal-weight "
                 "panel, six CRN seeds, arms plain/p:2/p:5/p:10) showed the estimand moving with the strata count -- p:2 vs "
                 "plain +0.50 % +/- 0.38 % (z 1.3), p:5 +1.41 % +/- 0.33 % (z 4.3), p:2 - p:5 = -0.89 % +/- 0.20 % (z 4.6); "
                 "at 100k the p:5 shift is +0.69 % +/- 0.20 %. The shift moves the PUBLISHED point estimate to reduce an "
                 "UNPUBLISHED seed SE (SEs are excluded from the paper's tables, owner 2026-08-28), and exceeds the S=5 SE.",
        refs=("Code/HA-Models/rerun_logs/strata_ab_20260907/REPORT.md",
              "Code/HA-Models/rerun_logs/nladder_gran_20260908/GRANULARITY_REPORT.md",
              "plans/20260828-1200h_econ-1_ui-welfare-precision_plan.md",
              "conclusions_private/2026-09-07_session-record_putting-pairing-to-work.md",
              "conclusions_private/2026-09-08_strata-shuffle-revert-to-plain-hamilton_decision.md"),
    ),
    Setting(
        name="shuffle_mrkv_rounding",
        env_var="HAFISCAL_SHUFFLE_MRKV_ROUNDING",
        category=IMPROVEMENT,   # OPT-IN. Adopted with shuffle_mrkv_strata 2026-09-07; REVERTED with it 2026-09-08 (owner:
                                # plain Hamilton, the certified engine byte-for-byte, restored from history).
        canonical="hamilton",   # REVERTED 2026-09-08 (was "madow" from 2026-09-07 21:48). Madow itself measured harmless at Baseline
                                # S=5 (check cells +0.12/+0.16 % +- 0.07/0.09 %, UI within noise) and is exact in expectation, but it
                                # is an uncertified change to the certified engine adopted for a diagnostic-SE gain; the owner's
                                # 2026-09-08 ruling keeps the world of record on the engine every certification was done on.
        paper="hamilton",       # floor + largest residual, the certified engine byte-for-byte
        coupling="The strata path uses Madow regardless of this knob; on the plain path Madow removes the "
                 "Hamilton rule's deterministic per-(N,p) rounding, which over-draws rare transitions in the "
                 "smallest unemployed states (u3Q 'stay' 0.362 vs 0.339 for u1Q/u2Q at HS_Only, gate 2026-08-28). "
                 "hamilton in BOTH worlds since the 2026-09-08 revert; madow stays opt-in (a driver that means it pins it).",
        evidence="A/B 2026-09-07, plainM (Madow, no strata) vs the record (Hamilton): UI per-seed SD 3.49/3.93 % "
                 "-> 2.79/2.92 %; means: check cells +0.12/+0.16 % +- 0.07/0.09 % (z 1.8), UI -0.29/+0.36 % +- "
                 "0.5 %, tax-cut cells within 0.02 %. Exact in expectation: test_mrkv_strata.py "
                 "(test_madow_rounding_exact_in_expectation_in_small_strata, test_plain_path_madow_rounding_unbiased).",
        refs=("Code/HA-Models/rerun_logs/strata_ab_20260907/REPORT.md",
              "plans/20260828-1200h_econ-1_ui-welfare-precision_plan.md"),
    ),
    Setting(
        name="tm_amax",
        env_var="HAFISCAL_TM_AMAX",
        category=BUG_FIX,
        canonical="1300",
        paper="500",
        evidence="A distribution-grid top (dist_aGrid_max) of 500 truncates the "
                 "ergodic wealth tail of the most-patient College GIC-cap atom, "
                 "biasing TM results. 1300 = production_dist_aGrid_max() covers "
                 "the (1-1e-4) ergodic-aNrm quantile.",
        refs=("Code/HA-Models/FromPandemicCode/EstimParameters.py (canonical block)",
              "history/20260609-1120h_bug053-gpf-shave-and-tm-ergodic-grid-loop.md",
              # 2026-08-21 ruling: the quantile rule is retired; the onset-and-support rule
              # (python Code/HA-Models/onset_dist_top.py --rho <rho>) ratifies 1300 at rho=2
              "conclusions_private/2026-08-21_dist-top-onset-rule-ruling.md",
              "Code/HA-Models/onset_dist_top.py"),
    ),
    Setting(
        name="the_gic_factor",
        env_var="HAFISCAL_GIC_FACTOR",  # Python constant EstimParameters.theGICfactor
        category=BUG_FIX,
        canonical="0.9995",
        paper="0.999",
        estimation_only=True,
        coupling="Re-estimation input; the canonical DiscFacEstim_* files were "
                 "estimated under 0.9995 (BUG-053).",
        evidence="BUG-053 (owner-requested re-estimation 2026-06-09).",
        refs=("history/20260609-1650h_bug053-reestimation-gicfactor-0p9995.md",),
    ),

    # ----- IMPROVEMENTS (default ON; as-corrected OFF unless opted-in) -------
    Setting(
        name="gicx",
        env_var="HAFISCAL_GICX_MODE",
        category=IMPROVEMENT,
        # OWNER RULING 2026-06-14: the 2-D 'hardcoded' GICx is used in BOTH worlds (default AND
        # as-corrected). It is result-neutral (BUG-039 Phase-F: GICx is non-identified, ~zero
        # (beta,nabla) impact) and much faster, so it is NOT a world-defining revert — both the
        # default and the as-corrected re-estimation run with GICx='hardcoded'. paper='hardcoded'
        # therefore makes world_value() resolve to 'hardcoded' for both worlds. PROVENANCE: the
        # published paper actually used the 3-D 'legacy' GICx NM; that is recorded here in evidence,
        # not in the `paper` field, because reproducing the 3-D NM is the old branch's job, not an
        # as-corrected runtime axis.
        canonical="hardcoded",  # improvement ON (default world)
        paper="hardcoded",      # owner ruling 2026-06-14: also used in as-corrected (result-neutral)
        estimation_only=True,
        coupling="'hardcoded' uses theGICfactor=0.9995 + re-estimated "
                 "DiscFacEstim_* files; the paper-era 3-D 'legacy' NM implies the paper-era "
                 "estimates. Resolver must keep {GICX_MODE, DiscFacEstim file} matched (BUG-049).",
        evidence="BUG-039 Phase-F: GICx 10x spread, negligible (beta,nabla) impact "
                 "(non-identified) => hardcoded 2-D NM is ~result-neutral but much "
                 "faster. Owner ruling 2026-06-13: improvement, not bug-fix. Owner ruling "
                 "2026-06-14: used in BOTH worlds (the published paper used 3-D 'legacy' NM, "
                 "preserved on the old branch / frozen tag only).",
        refs=("conclusions_private/20260613_config-worlds-definition-default-legacy.md",
              "Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (BUG-039 dispatch)"),
    ),
    Setting(
        name="nm_warm_start",
        env_var="HAFISCAL_NM_START_FROM_SAVED",
        category=IMPROVEMENT,
        canonical="1",  # improvement ON
        paper="0",      # improvement OFF (paper's cold starts)
        estimation_only=True,
        confirm="Code comment claims round-trip preservation validated "
                "(warm-start -> identical re-convergence); confirm result-neutral "
                "before exposing as a layerable improvement.",
        evidence="BUG-039 Phase E: warm-start from saved (beta,nabla,GICx) "
                 "re-converges identically; pure speed.",
        refs=("Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py (Phase E)",),
    ),
    Setting(
        name="ad_equilibrium_share",
        env_var="HAFISCAL_AD_EQUILIBRIUM_SHARE",
        category=IMPROVEMENT,
        # OWNER RULING 2026-08-25 (22:30): the welfare battery (Step 5b) consumes the AD
        # equilibrium the spending program (Step 5a, TM) converged and solves nothing; one
        # equilibrium behind both the multiplier and the welfare tables. Classified an
        # IMPROVEMENT by the owner ("the improvement's upside is a big plus"): on in the
        # default world, off in as-corrected (the paper's welfare battery iterated its own
        # MC fixed point) unless opted in with an explicit HAFISCAL_AD_EQUILIBRIUM_SHARE=1.
        # Under sharing the battery also defaults to the weighted-tail panel
        # (HAFISCAL_MC_WEIGHTED_TAIL=200) so the measurement population carries the
        # equilibrium's income level (BUG-092). Measured effect on the default world's
        # Baseline S=3: check_rec_AD -0.96 %, taxcut_rec_AD -0.4 %, UI cells within their
        # p-assignment noise; multipliers unchanged; battery ~3x faster (no AD loops).
        canonical="1",  # improvement ON: Step 5b installs Step 5a's equilibrium and skips its AD loop
        paper="0",      # improvement OFF: the battery iterates its own MC AD fixed point (paper method)
        estimation_only=False,
        coupling="Step 5b requires Step 5a to have published equilibria for the SAME model "
                 "(world, parametrization, conventions) into the policy store; a MISS is an "
                 "error under HAFISCAL_POLICY_STORE_REQUIRE=1 (welfare6_scenario's default).",
        evidence="BUG-092/093 (2026-08-25): the TM's and the battery's own equilibria disagreed by "
                 "up to 5 % on check_rec_AD; with the TM's Q-construction fixed (BUG-093) and the "
                 "weighted-tail panel, the shared equilibrium reproduces the own-loop MC check cell "
                 "to -0.96 % at S=3 without solving. Owner ruling 2026-08-25 22:30: IMPROVEMENT, "
                 "default on. CERTIFIED 2026-08-27 20:30 within the owner's WIDENED tolerance "
                 "(1.5 % on the check/tax-cut AD cells, one seed-band SE on the UI cell, 0.3 % non-AD): "
                 "the -1.0..-1.3 % (check) / -1.04..-1.14 % (tax cut) gap to the own-loop battery is "
                 "invariant to panel size (1x/4x/10x, both sides) and to the sampler's K -- the TM "
                 "equilibrium vs the panel's own MC fixed point, not noise.",
        # C9 (2026-08-28): the 2026-08-27 certification is of the TOLERANCE kind -- the shared
        # equilibrium reproduces the own-loop battery within stated bounds, a documented residual
        # (the TM-vs-MC equilibrium gap; the 08-28 same-seed triple showed it invariant to the
        # panel sampler: weighted vs equal-weight own loops -0.28 % on check_rec_AD, the gap to
        # the shared cell +1.24 % check / +0.82 % tax cut / +1.29 % UI = one seed-band SE, with
        # every non-AD cell identical). World-scoped: on in default, off in as-corrected.
        certification="conclusions_private/2026-08-27_ad-equilibrium-sharing_certification.md",
        certification_kind="tolerance",
        tolerance={"check_rec_AD": "1.5 %", "taxcut_rec_AD": "1.5 %",
                   "ui_rec_AD": "one across-seed SE of the cell", "non-AD cells": "0.3 %"},
        refs=("Code/HA-Models/docs/ENV_FLAGS.md (HAFISCAL_AD_EQUILIBRIUM_SHARE)",
              "BUGS_private/HAFiscal_BUG-092_*.md",
              "conclusions_private/2026-08-25_session-record_bug092-bug093_tm-q-construction-and-weighted-tail-sampler.md",
              "plans/20260828-1200h_econ-2_weighted-own-loop_plan.md (the 08-28 triple)"),
    ),

    # ----- ADDED 2026-08-26 (owner ruling: every adopted method change gets a row so
    # UPDATES.md's "What changed" inventory sees it). NONE of these is applied by the
    # world axis (EstimParameters._WORLD_APPLY is unchanged): each already has its own
    # resolution rule in code, so these rows classify and document — they do not change
    # any run. `test_runtime_parity.py` guards the applied subset. ----------------------
    Setting(
        name="welfare_engine",
        env_var="HAFISCAL_WELFARE_ENGINE",
        category=IMPROVEMENT,
        # OWNER RULING 2026-08-27: canonical FLIPPED to "hark". The hybrid bundle (replay-fed JAX-AD +
        # capture-presolve cache + CRATIO_PREV feed, adopted 2026-08-02 under a sig-figs ruling) was never
        # CERTIFIED to reproduce the all-HARK battery: a CRN-paired -0.5..-1.3 % residual on the AD welfare
        # cells, unattributed after nine refutation attempts; measured again 2026-08-26/27 at S=5 together
        # with sharing + the weighted panel (-1.0..-1.3 % on the AD check/tax-cut cells). Not certified ->
        # not in the world of record; the speed case (72 -> 54 min) predates the policy store. Opt-in by
        # explicit HAFISCAL_WELFARE_ENGINE=hybrid. TODO (plans_local/TODO.md): attribute the residual.
        canonical="hark",
        paper="hark",        # the all-HARK MC welfare battery the paper used
        estimation_only=False,
        coupling="Resolved by Code/HA-Models/welfare_engine.py, NOT by the world block: an explicit "
                 "value wins over everything (including HAFISCAL_QE_FIDELITY=1), and the module "
                 "itself maps HAFISCAL_WORLD=as-corrected and QE_FIDELITY to 'hark'. Must stay out "
                 "of _WORLD_APPLY — a world setdefault would defeat the QE_FIDELITY guard.",
        evidence="Owner adoption 2026-08-02: the hybrid bundle reproduces the all-HARK battery to "
                 "the accepted CRN-paired residual (-0.5..-1.3 % on the AD cells, unattributed after "
                 "nine refutations; sig-figs ruling) at 54 vs 72 min for the Baseline battery; "
                 "'hark' is the bit-identity-proven one-knob rollback. IMPROVEMENT: off in "
                 "as-corrected (the module's own world guard).",
        refs=("plans/20260802-0300h_canonical-hybrid-default_plan.md",
              "conclusions_private/2026-08-01_jaxad-graduation.md",
              "Code/HA-Models/welfare_engine.py",
              "Code/HA-Models/docs/ENV_FLAGS.md (HAFISCAL_WELFARE_ENGINE)"),
    ),
    Setting(
        name="step2_sim_engine",
        env_var="HAFISCAL_STEP2_SIM_ENGINE",
        category=IMPROVEMENT,
        canonical="tm_ergodic",  # a-indexed TM ergodic objective (default since 2026-06-23)
        paper="mc",              # the Monte-Carlo forward-panel objective the paper estimated on
        estimation_only=True,
        coupling="Read by run_phase2_parallel._resolve_step2_engine; estimation-only, so the "
                 "runtime world apply never exports it. The (beta,nabla) estimates are engine-"
                 "neutral to <=0.06 % (the flip's matched re-validation), so the BUGFIXED "
                 "calibration does not depend on this choice.",
        evidence="Owner-gated matched re-validation 2026-06-23: TM-ergodic == MC beta to <=0.06 % "
                 "across cohorts at ~28x the speed; default flipped mc -> tm_ergodic, mc kept opt-in.",
        refs=("conclusions_private/2026-06-23_step2-default-flip-to-tm-ergodic.md",
              "conclusions_private/2026-06-21_toolchain-ledger.md",
              "Code/HA-Models/docs/SOLVE_SIMULATE_TOOLMAP.md"),
    ),
    Setting(
        name="step5_ati",
        env_var="HAFISCAL_STEP5_ATI",
        category=IMPROVEMENT,
        canonical="1",  # FTI/ATI block-Newton solver on every qualifying cold AD-off solve
        paper="0",      # the paper: HARK's iterate-to-tolerance EGM everywhere
        estimation_only=False,
        coupling="Setdefault'ed by the entry points themselves (AggFiscalMAIN_reduced.py, "
                 "estim_phase2_tm_a.py), not by the world block; qualification-gated per agent "
                 "(patience threshold, AD-off, cold) with an EGM route on a qualification miss; "
                 "since the 2026-08-22 owner ruling an exception during an attempted route "
                 "(incl. FTI unavailability) is FATAL — deliberate EGM = explicit "
                 "HAFISCAL_STEP5_ATI=0.",
        evidence="Reduced A/B multiplier gate PASSED 2026-07-24 (worst |dmult| 4.1e-5 vs the 1e-3 "
                 "gate); BUG-089 (2026-08-24) moved the solver's tail exponent onto the attach "
                 "layer's measured Q, after which both worlds' multiplier tables were re-run. "
                 "Owner ruling 2026-08-22: FTI is the engine on the routed Step-2/5 paths in BOTH "
                 "worlds (a solver choice, certified result-neutral), so as_corrected='1' records "
                 "what the BUGFIXED tables were actually solved with; `paper` keeps the provenance.",
        as_corrected="1",
        refs=("conclusions_private/2026-07-23_meld_p4b_step5_ati_wiring.md",
              "BUGS_private/HAFiscal_BUG-089_*.md",
              "Code/HA-Models/test_step5_ati_wiring.py",
              "Code/HA-Models/docs/ENV_FLAGS.md (HAFISCAL_STEP5_ATI)"),
    ),
    Setting(
        name="tm_q_method",
        env_var="HAFISCAL_TM_Q_METHOD",
        category=BUG_FIX,
        canonical="doob",   # ONE construction (Fix 4 p-weighted pi_Q + the matching survival step) for base, start and kernel
        paper="cohort",     # pre-fix: the caller's `cohort` start with the plain kernel elsewhere (the published paper's m-indexed TM has no Q construction at all)
        estimation_only=False,
        coupling="Resolution order everywhere: explicit q_method argument > this env var > the "
                 "module default (tm_methods._resolve_q_method) — the fix is the module default, "
                 "so the world block does not export it.",
        evidence="BUG-093 (2026-08-25): with the start Doob and the kernel plain, a null experiment "
                 "started 3.7 % above base at Baseline-uncapped and the default world's recession "
                 "Cratio sat above 1; one construction for base level, experiment start and "
                 "propagation kernel makes the null experiment 1.0000 under either construction.",
        refs=("BUGS_private/HAFiscal_BUG-093_uncapped_baseline_tm_experiment_consumption_level_offset.md",
              "BUGS_private/HAFiscal_BUG-092_uncapped_tm_ad_equilibrium_disagrees_with_mc_on_check.md",
              "conclusions_private/2026-08-25_session-record_bug092-bug093_tm-q-construction-and-weighted-tail-sampler.md"),
    ),
    Setting(
        name="mc_weighted_tail",
        env_var="HAFISCAL_MC_WEIGHTED_TAIL",
        category=IMPROVEMENT,
        canonical="200",  # K=200 equal-income tail strata per atom (q=0.01 of the population; owner ruling: q stays 0.01)
        paper="0",        # the equal-weight stratified panel
        estimation_only=False,
        coupling="Its effective default FOLLOWS ad_equilibrium_share: welfare6_scenario.py sets 200 "
                 "only when sharing is on (and HAFISCAL_MC_PLVL_INIT=analytic_markov) and the var is "
                 "unset; an own-loop battery (sharing off, incl. as-corrected) keeps the equal-weight "
                 "panel. Not world-applied for that reason — a world export of '0' would override "
                 "the sharing-conditional rule for an as-corrected+sharing opt-in run.",
        evidence="BUG-092 (2026-08-25): on the shared equilibrium the equal-weight panel's "
                 "check_rec_AD sat -5 % from the own-loop MC because the panel's E[p] misses the "
                 "income carried by the uncapped world's tail; the weighted-tail panel brings it "
                 "within 1 % (S=3); the UI cells' -3 % is p-assignment sampling noise (equal-weight "
                 "UI +-4 %/seed, weighted +-1.6 %), not bias.",
        refs=("BUGS_private/HAFiscal_BUG-092_uncapped_tm_ad_equilibrium_disagrees_with_mc_on_check.md",
              "Code/HA-Models/weighted_tail_sampler.py",
              "conclusions_private/2026-08-25_session-record_bug092-bug093_tm-q-construction-and-weighted-tail-sampler.md"),
    ),
    Setting(
        name="welfare_seed_count",
        env_var=None,      # a driver argument (--seed-offset 0,1,2), not an env var
        category=IMPROVEMENT,
        canonical="5",     # whole-cell seeds 0..4 (owner 2026-08-28: "S = 5 is plenty"; SEs are a diagnostic, not for the paper): point tables from seed 0, seeds 1-4 for the across-seed SE table + the C4 band gate
        paper="1",         # the paper reported single-seed welfare cells
        estimation_only=False,
        coupling="Point tables are the seed-0 whole-cell battery; the across-seed SE table and the "
                 "band gate (full_profile_rerun_gates.py s5b; AD cells 1 % since the 2026-08-26 "
                 "ruling) use all three. Reporting precision only; no cell's estimator changes.",
        evidence="Owner ruling 2026-08-28: S=5 (the tables of record since 2026-08-26; the across-seed SEs are a diagnostic, not for the paper), superseding the 2026-08-01 S=3 ruling, which superseded "
                 "the S=4 plan-ruling; every reported bias must carry a multi-seed SE.",
        refs=("conclusions_private/2026-08-28_prior-art-review_of_proposed_improvements.md",
              "conclusions_private/2026-08-01_seed-count-S3-ruling.md",
              "Code/HA-Models/full_profile_rerun_gates.py",
              "Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py"),
    ),

    # ----- DISCRETIONARY (default=canonical; as-corrected=paper) -------------
    Setting(
        name="interpretation",
        env_var="HAFISCAL_INTERPRETATION",
        category=DISCRETIONARY,
        # OWNER RULING 2026-06-13 (Q5, flip_esc): the `default` world's adopted interpretation
        # is ESC, matching production/validation drivers, MODEL_INTERPRETATIONS.md, the
        # reproduce.sh qe_fidelity profile, and dolo-plus D-06. WIRED 2026-06-14: ESC is now the
        # PRODUCTION default — EstimParameters.py sets `os.environ.setdefault(HAFISCAL_INTERPRETATION,
        # 'ESC')` UNCONDITIONALLY in the canonical block (applies even under QE_FIDELITY, since the
        # published-QE world is itself ESC). It is NOT in the WORLD-apply subset because it does NOT
        # vary by world (ESC in both); keeping it global guarantees the worlds never differ on it.
        # The _interpretation.py library code-literal default stays 'CDC' (conservative for direct
        # importers + its unit tests); ESC is the production default. CDC is now an explicit opt-in
        # (reproduce.sh production_*/tm_*/mc_* profiles export CDC). Since the paper also used ESC,
        # interpretation is ESC in BOTH default and as-corrected; CDC is the documented alternative,
        # not a world-defining revert. CRITICAL coupling preserved below.
        canonical="ESC",
        paper="ESC",
        coupling="ESC requires a matched ESC DiscFacEstim_* file (BUG-049: an ESC run silently "
                 "reading CDC betas shifts the Check multiplier ~+4%) — HAFISCAL_DISCFAC_FILE "
                 "must point at the ESC calibration. Selecting CDC (the alternative) needs the "
                 "matched CDC file. The {PermGroFac, calibration, interpretation} triple is atomic.",
        confirm="Confirm the ESC calibration (DiscFacEstim_*_ESC) files exist on this branch.",
        evidence="CDC vs ESC is the splurge-interpretation modeling choice "
                 "(legitimate, results-affecting) settled in the CDC/ESC doc set; ESC adopted "
                 "as the production/default interpretation (owner ruling 2026-06-13).",
        refs=("BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md",
              "BUGS_private/HAFiscal_BUG-049_esc_calibration_silent_fallback.md"),
    ),
    Setting(
        name="perm_during_unemp",
        env_var="HAFISCAL_PERM_DURING_UNEMP",
        category=DISCRETIONARY,
        # OWNER RULING 2026-06-14 (exhaustive_final): this is the SOLE economic difference
        # between the two worlds. default='on', as-corrected='off'. Everything else (CRRA=2.0,
        # Rfree=1.01, urates, IncUnemp replacement rates, LivPrb, life-cycle/T_age, CRRA
        # heterogeneity) is held at the paper's values in BOTH worlds.
        canonical="on",
        paper="off",
        evidence="Whether unemployed agents draw permanent shocks. 'on' is the "
                 "Harmenberg-factorizable convention; 'off' (PermShk=1) is the "
                 "published-QE assumption. Owner ruling 2026-06-14: the ONLY economic "
                 "axis between default and as-corrected.",
        refs=("plans/20260503-1655h_perm_shocks_during_unemp_config_split.md",
              "conclusions_private/2026-05-04_qe_fidelity_full_vs_QE_published.md"),
    ),
    Setting(
        name="ui_extension_policy",
        env_var="HAFISCAL_UI_EXTENSION_POLICY",
        category=BUG_FIX,
        # Improvement B (owner 2026-08-26; the case is REALISM). canonical FLIPPED to 'history'
        # at P4 (2026-08-26) after the Improvement-A gates (G0/G1) and the Baseline runs -- and
        # FLIPPED BACK to 'window' by the owner 2026-08-28 10:33 ("window everywhere"): the paper's
        # policy is the main text's and the chain's; 'history' is the robustness-appendix arm
        # (Econ-7). Every table of record since 08-27 pinned window explicitly; the staged
        # IMPROVED candidates had been copied from the history run (restaged 2026-08-28).
        # RENAMED 2026-09-06 (owner): the values were `window` and `history`, which named the
        # machinery rather than the thing. `paper` is the policy the paper describes; `historical`
        # is the one US extensions actually followed. Both old spellings still resolve
        # (`ui_extension_rule.POLICY_ALIASES`), and "window" survives as the name of the calendar
        # window a policy is in force over, which is what it always meant.
        canonical="paper_capped",
        paper="paper",
        coupling="Only read under HAFISCAL_UI_STATE_ENCODING=calendar (inert under 'legacy', "
                 "whose freeze is the paper's window, and under 'bug_fix'). The policy sets "
                 "t_enact, t_end, entry and the extension-state count "
                 "(ui_extension_rule.resolve_window); HAFISCAL_UI_EXT_{ENACT_LAG,END,ENTRY,"
                 "QUARTERS} override its parameters one at a time. The chain size follows the "
                 "policy (7 micro states under 'paper', 6 under 'paper_capped' and under "
                 "'historical'), so solution-cache "
                 "keys separate the two; a Step-2 estimate is invariant to it (the base chain's "
                 "extension states are lumpable no-benefit states).",
        evidence="'window' = the paper's UI paragraph as the QE code implements it: in force at "
                 "experiment periods t=0..3, CONTINUATION entry (only spells still drawing "
                 "regular benefits in the quarter before enactment are extended; exhaustees are "
                 "not re-opened), three extension states (the freeze's three held transitions). "
                 "'history' = what federal extensions actually did (fact-checked report): enacted "
                 "a quarter late (t_enact=1), OPEN entry for every exhaustee while in force, a "
                 "legislated end with a hard stop (t_end=8, ~2 quarters past the trough of the "
                 "6-quarter mean recession), +2 quarters per spell; renewals (B') deferred. "
                 "Results change by design between 'paper' and 'historical', which is why this row "
                 "was DISCRETIONARY until 2026-09-06. "
                 "RECLASSIFIED TO BUG_FIX, canonical 'paper_capped', OWNER RULING 2026-09-06 "
                 "('wire it into both worlds'), on the ruling of the same day that "
                 "[BUG-122] is a bug: 'if the paper as implemented gave anyone 5 quarters of UI "
                 "benefits, that was a BUG ... the --as-corrected and default new machinery should "
                 "properly give at most four quarters of benefits to anyone.' 'paper_capped' is "
                 "'paper' with the paragraph's own cap enforced -- 'extended from two quarters to "
                 "four quarters ... including quarters leading up to the recession' is a total of "
                 "2*UBspell_normal, so n_extension = UBspell_normal and the extension doubles the "
                 "entitlement; six micro states. Every cohort's schedule is then the paragraph's: "
                 "onset cohort and t=0 entrant four, one quarter in three, later entrants two, "
                 "exhaustees not re-opened, and the two pre-onset rows down from five to four. "
                 "This SUPERSEDES the 'window everywhere' ruling of 2026-08-28 in one narrow "
                 "respect only: that ruling took 'paper' to BE the paper's paragraph, and for the "
                 "two cohorts that draw benefits before the recession it is not. "
                 "Measured (Baseline, on top of the onset-spike timing fix, dell and ccarroll "
                 "independently and identical to the digit): the UI extension's incremental outlay "
                 "3071.1094 -> 2766.3300 (-9.92 %), UI multiplier 1.255 -> 1.256, and the stimulus "
                 "check and tax cut UNCHANGED with their outlays identical to 1e-13 -- a UI-only "
                 "change, as it must be. Requires the onset-spike timing fix "
                 "(onset_spike_t0_exempt): without it the spike leaves its cohort wearing a "
                 "pre-onset household's label and this cap would cut it to three.",
        refs=("plans/20260826-0800h_ui-extension-calendar-window-encoding_plan.md",
              "plans_local/20260906-0600h_ui-extension-four-quarter-cap_plan.md",
              "BUGS_private/HAFiscal_BUG-122_ui_extension_overpays_the_pre_onset_unemployed.md",
              "conclusions_private/2026-08-26_ui-extensions-actual-practice-vs-model-encodings.md",
              "conclusions_private/2026-09-06_onset-spike-timing-fix_measurement-and-ruling.md",
              "Code/HA-Models/ui_extension_rule.py"),
    ),
    Setting(
        name="onset_spike_t0_exempt",
        env_var="HAFISCAL_ONSET_SPIKE_T0_EXEMPT",
        category=BUG_FIX,
        # OWNER RULING 2026-09-06 ("when you have vetted and cleared it, this change will want to become the
        # default"), on the measurement of that day. The recession begins unannounced, so the model lays off, by
        # fiat, enough employed households to take unemployment to its recession value -- the "onset spike". The
        # published code applies that layoff BEFORE the period-0 transition, which immediately advances the
        # laid-off out of their first benefit state. Two things follow, and only the second is substantive: their
        # micro state at the first recorded quarter says they have drawn a benefit quarter they never received
        # (under `calendar` the state label IS the count of quarters drawn, so BUG-122's four-quarter cap cannot be
        # read off it); and they draw ONE recorded quarter of ordinary benefits where every other unemployed
        # household draws two, because one of their two is spent in the pre-period, which is never simulated.
        # The fix holds them in place for that one period AND resizes the spike -- f_exempt = f (T[0,0] - T[1,0]) /
        # T[0,0] -- so the unemployment path is unchanged to machine precision. Without the resizing the first
        # recession quarter comes out 12.5 % above the doubled-unemployment target in every education group.
        # BUG_FIX, hence both worlds: the paper's own policy gives two quarters of ordinary benefits and the
        # published code gave this cohort one. The reproduction arm (the original-model column, and
        # HAFISCAL_UI_STATE_ENCODING=legacy) must pin "0" EXPLICITLY -- unsetting no longer means off.
        canonical="1",
        paper="0",
        estimation_only=False,
        coupling="Step-5 only: the estimation economy never runs a recession, and Step 4 does not touch the "
                 "spike, so no re-estimation is implied. Precondition for BUG-122's four-quarter cap: the cap "
                 "is read off the state label, which lies until this lands.",
        evidence="HS_Only TM, all four recession scenarios: unemployment path identical to 1e-16; plain-recession "
                 "income +0.46 % at q=1 and identical elsewhere; UI extension's incremental outlay -19.2 % (its "
                 "counterfactual became correctly more generous); UI multiplier (AD) 1.437 -> 1.443; check 1.501 "
                 "-> 1.500; tax cut 1.222 -> 1.222 with its outlay identical to 3e-14. Welfare at S=8, CRN-paired: "
                 "check cells -0.5 % (|t| 4.5, 6.6), UI cells -1 to -2 % (|t| 2.1, 3.1), tax-cut cells noise, "
                 "no-recession cells exactly zero. Same in as-corrected. Flag OFF reproduces the pre-refactor "
                 "code at 0.000e+00; xubuntark reproduces dell to 4e-16.",
        refs=("BUGS_private/HAFiscal_BUG-122_ui_extension_overpays_the_pre_onset_unemployed.md",
              "conclusions_private/2026-09-06_onset-spike-timing-fix_measurement-and-ruling.md",
              "Code/HA-Models/onset_spike_rule.py",
              "plans_local/20260906-0600h_ui-extension-four-quarter-cap_plan.md"),
    ),
    Setting(
        name="perm_growth_scale",
        env_var="HAFISCAL_PERM_GROWTH_SCALE",
        category=BUG_FIX,
        # OWNER RULING 2026-08-29 08:35 (plan 20260829-0845h): the uniform downscaling lambda of the three
        # education-specific permanent-income growth rates, PermGroFac_e = 1 + lambda * g_e/4 (the paper's annual
        # g_e = 1.421 / 1.812 / 1.958 % unchanged in the code), BUNDLED with the cap removal (t_age_cap) as ONE
        # correction: the published code's undocumented 200-quarter wall had held the cross-section of permanent
        # income near the SCF's Gini by truncation; without the wall the paper's growth-for-life process is Pareto
        # (Gini 0.71, tail index 1.2-1.6). lambda is identified by the Gini alone (the process is exogenous; no
        # dependence on the discount factors): lambda* = 0.4367 solves pooled Gini = 0.50 (cstwMPC section 3.4,
        # "roughly 0.5" in the SCF) on the closed form (perm_income_inequality.py --solve-lambda); the install value
        # is the 2-decimal 0.44 (Gini 0.5007, within the owner's +-0.005). Both worlds carry it (the bundle IS the
        # fix); the paper's 1 survives only on the original-model reference arm (capped). Applied in
        # EstimParameters at the single upstream definition of PermGroFac_base_{d,h,c}; every consumer (the GIC cap,
        # the micro chain, Step 5, the TM p-mixture, the welfare battery, Step 4 through the PE calibration) inherits.
        # canonical "0.44" since the P4 install of 2026-08-29 (the matched re-estimation S1 -> S2 at lambda = 0.44, one
        # Step-2 estimate for both worlds, the chain columns and HANK landed with it -- one commit, the matched-triple
        # discipline); explicit env wins.
        canonical="0.44",
        paper="1",
        estimation_only=False,
        coupling="Calibration-matched with t_age_cap: the two are one correction ('no maximum age, with the growth "
                 "rates rescaled so the ergodic cross-section of permanent income keeps the SCF Gini, re-estimated'); "
                 "a matched re-estimation (Steps 1-2) is required when the value changes; the earnings-phase hazard "
                 "is 0 alongside it (the phase was the superseded alternative).",
        evidence="conclusions_private/2026-08-28_permanent-income-inequality_capped-vs-uncapped.md (Addenda 3-4: the "
                 "lambda sweep, both criteria); Code/HA-Models/perm_income_inequality.py --solve-lambda (2026-08-29: "
                 "lambda* = 0.4367; 0.44 -> Gini 0.5007).",
        refs=("plans/20260829-0845h_uniform-growth-downscaling-to-scf-gini_plan.md",
              "Code/HA-Models/perm_income_inequality.py"),
    ),
    Setting(
        name="earnings_phase_hazard",
        env_var="HAFISCAL_EARNINGS_PHASE_HAZARD",
        category=DISCRETIONARY,
        # OWNER RULING 2026-08-28 (~20:25): the age-free end of the earnings-growth phase -- a
        # household's education-specific permanent-income growth stops with a constant hazard h
        # per quarter (the "matured-earner" Markov phase; absorbing until death; newborns born
        # growing; everything else identical -- NOT a retirement). Why: with growth for an
        # unbounded life the cross-section of permanent income is Pareto with tail index 1.2-1.6
        # (Gini 0.71 vs the SCF's ~0.5; infinite variance, BUG-038); an age cap is unavailable
        # (the ergodic TM machinery is age-free). At h = 1/120 the closed form gives Gini 0.49,
        # E[p] by education 8.4/17.2/24.6 (the original capped model's) and tail index 2.2-2.7.
        # Record: conclusions_private/2026-08-28_earnings-phase-state_decision.md. The value is
        # applied by the earnings_phase SST (layout Mrkv = 2J*macro + J*phase + emp: the phase in
        # the middle, so `emp = Mrkv % J` stays valid and every macro block stays contiguous).
        # canonical "1/120" since the INSTALL of 2026-08-29 (P3 gates passed 2026-08-28/29: h = 0
        # byte-identity 12/12 cells; realized pooled Gini 0.48, E[p] 8.4/17.2/24.6 = the closed form;
        # the matched re-estimation S1 -> S2 under the Gamma = 1 cap and the chain column 5a + 5b
        # landed with it -- one commit, the matched-triple discipline). paper = "0": the published
        # process has no matured phase.
        # DEMOTED 2026-08-29 08:35 (owner: "a very substantial change in the model which would have to be explained at
        # length"): canonical back to "0" in both worlds from the P4 install of the uniform growth downscaling
        # (perm_growth_scale); the machinery stays as an opt-in and the phase Baseline column stays in the record.
        canonical="0",
        paper="0",
        estimation_only=False,
        coupling="Model change: the micro chain becomes {growing, matured} x the employment/UI "
                 "states (14 micro states under calendar+window); the Step-2 GIC cap uses the "
                 "matured phase's growth (Gamma = 1); a matched re-estimation (Steps 1-2) and a new "
                 "chain column are required when it is turned on; solution-cache keys separate the "
                 "two through the agent primitives (MrkvArray, PermGroFac).",
        evidence="conclusions_private/2026-08-28_permanent-income-inequality_capped-vs-uncapped.md "
                 "(the finding and the two criteria: finite variance, Gini ~ 0.5); "
                 "Code/HA-Models/perm_income_alternatives.py (the h grid).",
        refs=("conclusions_private/2026-08-28_earnings-phase-state_decision.md",
              "plans/20260828-2030h_earnings-phase-state_plan.md",
              "Code/HA-Models/earnings_phase.py"),
    ),
    Setting(
        name="nm_tol",
        env_var="HAFISCAL_NM_XATOL",  # FATOL travels with it
        category=DISCRETIONARY,
        # OWNER RULING 2026-06-14 (nm_tol_axis=same_both, which_tol=1e-3): both worlds use the
        # SAME tolerance 1e-3 (a middle ground: tighter than the old 1e-2 default, cheaper than
        # the paper's 1e-4), so nm_tol is NO LONGER a world-distinguishing setting — it is held
        # equal across worlds to keep perm_during_unemp the only axis. Because this changes the
        # default world's tolerance (was 1e-2), the default-world betas are ALSO re-estimated at
        # 1e-3 (owner ruling default_reestim=reestimate_both; headline refresh via candidate->promote).
        canonical="1e-3",
        paper="1e-3",
        estimation_only=True,
        coupling="HAFISCAL_NM_FATOL takes the same value.",
        evidence="Nelder-Mead estimation tolerance. The published paper used the tighter "
                 "1e-4; the post-paper default was 1e-2. Owner ruling 2026-06-14: both worlds "
                 "re-estimated at 1e-3 (same in both). Results-affecting only through the "
                 "estimate, so inert unless re-estimating.",
        refs=("reproduce.sh (qe_fidelity profile)",
              "plans/20260614_as-corrected-calibration-run-spec.md"),
    ),
)


# ---------------------------------------------------------------------------
# Derivation helpers (pure)
# ---------------------------------------------------------------------------
_BY_NAME = {s.name: s for s in CATALOG}


def by_name(name: str) -> Setting:
    return _BY_NAME[name]


# Settings the WORLD WIRING must not apply, because an ENTRY POINT owns them (do_all sets
# HAFISCAL_TM_A_INDEXED=1 for Step 5a and passes the same value to Step 5b, BUG-119 option 1).
# The catalog still carries a row for them -- it is the record of what the value SHOULD be -- but
# `EstimParameters._WORLD_APPLY` deliberately excludes them, so an unset environment leaves them
# OFF at runtime whatever the catalog says.
#
# This tuple exists because that gap silently corrupted a provenance record (BUG-124, 2026-09-06):
# `effective_config()` built its report from `resolve_world`, so it wrote "TM_A_INDEXED = 1" into
# the sidecar of runs that had actually used the m-indexed engine. Anything that REPORTS what a run
# used must consult os.environ for these, never the catalog.
ENTRY_POINT_OWNED = ("HAFISCAL_TM_A_INDEXED",)


def world_value(setting: Setting, world: str, improvements: frozenset = frozenset()) -> str:
    """Resolve the value a setting takes in `world`, given opted-in improvements.

    Rules:
      BUG_FIX        -> canonical (both worlds).
      DISCRETIONARY  -> default: canonical; as-corrected: paper.
      IMPROVEMENT    -> default: canonical (ON);
                        as-corrected: paper (OFF) unless its name is opted in.
    """
    if world not in WORLDS:
        raise ValueError(f"unknown world {world!r}; expected one of {WORLDS}")
    if world != DEFAULT and setting.as_corrected is not None:
        # Two-axis env vars (see Setting.as_corrected): an opted-in IMPROVEMENT
        # still takes canonical; otherwise the explicit as-corrected value wins.
        if setting.category == IMPROVEMENT and setting.name in improvements:
            return setting.canonical
        return setting.as_corrected
    if setting.category == BUG_FIX:
        return setting.canonical
    if setting.category == DISCRETIONARY:
        return setting.canonical if world == DEFAULT else setting.paper
    # IMPROVEMENT
    if world == DEFAULT:
        return setting.canonical
    return setting.canonical if setting.name in improvements else setting.paper


def resolve_world(world: str, improvements: frozenset = frozenset(),
                  include_estimation_only: bool = True) -> dict:
    """Return {env_var: value} for all env-controlled settings in `world`.

    Non-env settings (env_var is None) and, optionally, estimation-only settings
    are skipped. This is the data the future resolver will apply via
    os.environ.setdefault; it performs NO os.environ access itself.
    """
    out: dict[str, str] = {}
    for s in CATALOG:
        if s.env_var is None:
            continue
        if s.estimation_only and not include_estimation_only:
            continue
        out[s.env_var] = world_value(s, world, improvements)
    return out
