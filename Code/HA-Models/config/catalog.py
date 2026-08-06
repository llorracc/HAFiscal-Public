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

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"{self.name}: bad category {self.category!r}")


# ---------------------------------------------------------------------------
# THE CATALOG
# ---------------------------------------------------------------------------
# Values are stored as strings exactly as the env var is read (so the resolver
# can export them verbatim). `theGICfactor` is the one non-env (Python) constant.

CATALOG: tuple[Setting, ...] = (
    # ----- BUG FIXES (canonical in every world) -----------------------------
    Setting(
        name="ui_state_encoding",
        env_var="HAFISCAL_UI_STATE_ENCODING",
        category=BUG_FIX,
        canonical="bug_fix",
        paper="legacy",
        evidence="BUG-043: legacy 4-state encoding under-delivers UI to the "
                 "deepest-unemployment stratum; bug_fix 6-state encoding pays the "
                 "policy the paper describes.",
        refs=("BUGS_private/HAFiscal_BUG-043_*",
              "conclusions_private/2026-05-16_canonical_config_recommendation.md"),
    ),
    Setting(
        name="welfare6_fix_dur_avg",
        env_var="HAFISCAL_WELFARE6_FIX_DUR_AVG",
        category=BUG_FIX,
        canonical="on",
        paper="off",
        evidence="BUG-046: legacy welfare formula computes u(E[c]) != E[u(c)] for "
                 "concave u (Jensen). The fix computes the correct quantity.",
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
        name="t_age_cap",
        env_var="HAFISCAL_T_AGE",
        category=IMPROVEMENT,
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
                 "intended the cap), hence IMPROVEMENT not BUG_FIX.",
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
              "decay_form/tail_state_DERIVATION_20260726.md"),
    ),
    # ----- (improvement riding the fix above) -------------------------------
    Setting(
        name="pf_decay_q_measured",
        env_var="HAFISCAL_PF_DECAY_Q",
        category=IMPROVEMENT,
        canonical="measured",
        paper="slope",
        coupling="Only meaningful with pf_decay_extrap ON in the powerlaw form. "
                 "Selecting 'measured' (alias 'local2') ALSO switches the solve "
                 "grid to the per-group K*hbar top (467/551/591 at K=3) with the "
                 "count basis 192 (density-held); 'slope' restores the legacy "
                 "40/48 grid. The as-corrected combination (owner final ruling "
                 "2026-07-23: bug fixes only, NO improvements; the powerlaw "
                 "restoration = the fix) is {EXTRAP='1' powerlaw, Q='slope', "
                 "top-40, count-48}. The exp-vs-powerlaw form choice is "
                 "results-neutral at <=7e-4 (T1c, RECONCILED-002).",
        evidence="The measured two-secant local exponent replaces theory/slope "
                 "pins (in-range exponents match no closed-form anchor; the "
                 "slope-Q at the legacy grid top is unidentified, T=40 << h~197). "
                 "College objective at count-converged numerics: 4.96 (linear) -> "
                 "4.35 (exp) -> 4.14 (pl-slope@40) -> 3.75 (measured@591). "
                 "Calibration-robust: Tier-2 re-estimation moves beta <=0.3% and "
                 "the configs' optima agree.",
        refs=("plans/20260722_local-two-secant-tail-q_plan.md",
              "conclusions_private/2026-07-23_solve_grid_count_convergence.md"),
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
        category=BUG_FIX,
        canonical="1",
        paper="",  # off
        evidence="BUG-044: reliable UI welfare is a correctness requirement. "
                 "Without stratified shuffle the UI welfare cells swing 27-29% "
                 "between replicates (meaningless). Owner ruling 2026-06-13: "
                 "bug-fix, NOT a discretionary variance-reduction choice.",
        refs=("conclusions_private/2026-06-10_welfare_method_unified_MC.md",
              "conclusions_private/20260613_config-worlds-definition-default-legacy.md"),
    ),
    Setting(
        name="shuffle_mrkv_transition",
        env_var="HAFISCAL_SHUFFLE_MRKV_TRANSITION",
        category=BUG_FIX,
        canonical="stratified",
        paper="shuffle",
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
        category=BUG_FIX,
        canonical="transition",
        paper="off",
        evidence="BUG-044 companion: newborn marginal-distribution correction; "
                 "'transition' matches the non-shuffle marginals.",
        refs=("conclusions_private/2026-06-10_welfare_method_unified_MC.md",),
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
              "history/20260609-1120h_bug053-gpf-shave-and-tm-ergodic-grid-loop.md"),
    ),
    Setting(
        name="the_gic_factor",
        env_var=None,  # Python constant EstimParameters.theGICfactor
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
