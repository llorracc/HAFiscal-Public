"""UI-extension delivery rule — single source of truth (Improvements A/B, 2026-08-26).

Which unemployed micro states pay the EXTENDED benefit (``IncUnemp`` instead of
``IncUnempNoBenefits``) in the ``recessionUI`` scenario, as a function of the
encoding, the composite Markov state and the extension-policy window. Every
production consumer (the multiplier entry ``Simulate.py``, the welfare battery
``welfare6_scenario.py``, the MC realized-income override in ``AggFiscalModel.py``)
calls :func:`pays_extension` / :func:`extension_pay_mask`; nothing else may
re-implement the rule. (Correction, dual-path sweep 2026-09-02: the toolmap bench
was listed here as a caller but never was — ``toolmap/bench_toolmap.py`` builds its
own pre-BUG-090/050/091 income set and times a DIFFERENT model than production;
see the sweep table before citing its timings.)

Encodings (``HAFISCAL_UI_STATE_ENCODING``)
------------------------------------------
``legacy``
    The published QE code: 4 micro states {e, u1Q, u2Q, noBen}; the extension is
    the ``transition_ub=False`` FREEZE of the benefit chain on transitions INTO
    experiment blocks 1..ExtraUBperiods (``Parameters.make_cond_mrkv_arrays_recession_ui``).
    There are no extension states, so this module is never consulted.
``calendar``  (Improvement A; default since 2026-08-26)
    ``2 + UBspell_normal + n_extension`` micro states {e, u1Q, u2Q, u3Q, ..., noBen};
    the PLAIN chain in every scenario (identical Markov dynamics across the
    policy/no-policy pair, which is what restores per-agent CRN coupling for the
    stratified-shuffle engine — the speedup A is built for). The extension is
    INCOME at the extension states u_{UBspell_normal + j}, j = 1..n_extension,
    paid at experiment period t (= macro block - 1) iff

        t_enact + (j - 1)·[entry == 'continuation']  <=  t  <=  t_end.

    Under the paper's window (policy ``window``: t_enact = 0, t_end = ExtraUBperiods,
    entry = continuation, n_extension = ExtraUBperiods) this reproduces the legacy
    freeze EXACTLY as a relabeling of states — derivation below.
``bug_fix``
    The 2026-05-16 rule (6 states; u3Q/u4Q paid iff the CURRENT macro variant is
    the recession, ``macro_idx % 2 == 1``). A DIFFERENT policy from the paper's
    (four quarters for anyone unemployed while the recession lasts, cut off when it
    ends); kept only to reproduce the 2026-05-16..08-26 numbers. Not a bug fix —
    BUG-043 was withdrawn (RECONCILED-005).

Why ``continuation`` shifts the start by j - 1, and why n_extension = ExtraUBperiods
----------------------------------------------------------------------------------
Timing: the onset spike sets laid-off agents to u1Q in the PRE-period, and the
simulation then applies one transition per recorded period, INTO period t using
``CondMrkvArrays[macro_t]`` (``AggFiscalModel.hit_with_recession_shock``). With
``EconomyMrkv_init = [3, 5, 7, ...]`` block b = macro//2 and t = b - 1, so the legacy
freeze (blocks 1..E, E = ExtraUBperiods = UBspell_extended - UBspell_normal = 3) holds
the benefit clock on the transitions into t = 0, 1, ..., E-1.

Take a spell whose first u1Q period is k0 (k0 <= -1 for the pre-onset unemployed
and the spike cohort, which is u1Q at the pre-period, k0 = -1). By period t it has
advanced (t - k0) - f steps, f = |{0..E-1} ∩ (k0, t]| frozen transitions; it still
draws benefits iff it has advanced at most UBspell_normal - 1 = 1 step. On the plain
chain the same spell sits at u_{1 + (t - k0)}; the extension quarter index there is
j = t - k0 - 1 (j = 1 for u3Q, ...). Equating "still on benefits under the freeze"
with "paid at extension quarter j" gives, for UBspell_normal = 2 and E = 3:

    paid  <=>  f >= j  <=>  (j - 1 <= t <= E)          [checked case by case in
                                                       test_ui_extension_schedule.py]

i.e. a calendar window with start j - 1: the spell must have been drawing REGULAR
benefits in the quarter before enactment (u1Q or u2Q at t = -1, k0 >= -2) — the
extension CONTINUES benefits, it does not re-open them for exhaustees (k0 <= -3,
already in noBen at onset, get nothing under the freeze). And because the freeze
can hold the spike cohort / pre-onset u1Q for E = 3 transitions, that spell occupies
UBspell_normal + E = 5 CHAIN POSITIONS, so the plain chain needs E = 3 extension
states (7 micro states, not 6) to carry it: a 6-state chain is one position short.

Positions are not payments (clarified 2026-09-06). The spike cohort's pre-period
position is never simulated — no income is drawn there — so it is PAID four quarters,
which is what the paper says. The pre-onset cohorts genuinely drew their pre-onset
quarters, so they are paid five, which is BUG-122. Under the Step-0 timing fix
(``Code/HA-Models/onset_spike_rule.py``) the spike cohort is held at u1Q for the first
recorded period, which is where it belongs and what makes the two cases separable: the
cap of BUG-122 is read off the state label, and until then that label put the spike
cohort where a genuinely pre-onset household sits.

``open`` entry (Improvement B, policy ``history``) drops the j - 1 shift: every
agent who is in an extension state while the program is in force is paid, as
under EUC08 / PEUC (open entry for exhaustees); agents already in noBen at
enactment cannot be reached without duration memory — a documented omission.
"""
from __future__ import annotations

import os
from typing import NamedTuple

import numpy as np

ENCODINGS = ("legacy", "calendar", "bug_fix")
ENTRY_MODES = ("continuation", "open")
# Canonical policy names (renamed 2026-09-06, owner: "use paper and historical"). The former
# names were `window` and `history`, which named different KINDS of thing -- one after its
# mechanism (a calendar interval), the other after its provenance -- and `window` collided in
# conversation with the published code's FREEZE mechanism and with the date interval itself.
# `paper` = the extension policy the paper's UI paragraph describes, as the QE code implements it.
# `historical` = what the federal extensions of 2008/2020 actually did.
# The old spellings remain accepted for one deprecation cycle: prior owner rulings, decision
# records and table rows say "window everywhere", and those must keep resolving.
# `paper_capped` (BUG-122, 2026-09-06): the paper's own policy with its own sentence enforced --
# see resolve_window. Added as a THIRD value rather than a correction of `paper`, because `paper`
# is what the published code does and every record since 2026-08-26 refers to it by that name.
POLICIES = ("paper", "paper_capped", "historical")
POLICY_ALIASES = {"window": "paper", "history": "historical"}


def normalize_policy(policy):
    """Canonical policy name, accepting the pre-2026-09-06 spellings."""
    p = (policy or "paper").strip().lower()
    p = POLICY_ALIASES.get(p, p)
    if p not in POLICIES:
        raise ValueError(
            f"HAFISCAL_UI_EXTENSION_POLICY={policy!r}; expected one of {POLICIES} "
            f"(deprecated aliases: {tuple(POLICY_ALIASES)})")
    return p

# The 2026-05-16 six-state rule's fixed extension-state count (u3Q, u4Q).
BUG_FIX_EXTENSION_STATES = 2


class Window(NamedTuple):
    """The extension policy's parameters (experiment periods; t = macro block - 1)."""
    t_enact: int        # first period the program is in force
    t_end: int          # last period the program is in force (hard stop after it)
    entry: str          # 'continuation' (paper's code) | 'open' (history)
    n_extension: int    # extension states per spell (u3Q.. ), = extra benefit quarters
    policy: str         # 'paper' | 'historical' (canonical; see POLICY_ALIASES)


def experiment_period(macro_idx):
    """t = macro block - 1 (block 0 = the post-horizon / ergodic block -> -1)."""
    return np.asarray(macro_idx) // 2 - 1


def resolve_window(policy: str, UBspell_normal: int, UBspell_extended: int,
                   env=None) -> Window:
    """The policy's parameters, with explicit per-parameter env overrides winning.

    ``paper``  (the paper's UI paragraph, Model.tex 167-170, as the QE code implements it):
        t_enact = 0, t_end = ExtraUBperiods, entry = continuation, n_extension = ExtraUBperiods,
        where ExtraUBperiods = UBspell_extended - UBspell_normal (= 5 - 2 = 3): the number of
        frozen transitions in the published freeze — derived, not chosen (module docstring).
    ``paper_capped`` (BUG-122): the same window and entry rule with the paragraph's own cap
        enforced -- benefits "extended from two quarters to four ... including quarters leading up
        to the recession" means a total of 2 * UBspell_normal, hence n_extension = UBspell_normal
        (the extension doubles the entitlement). Six micro states. Requires the Step-0 onset-spike
        timing fix; see the branch's comment.
    ``historical`` (Improvement B; conclusions_private/2026-08-26_ui-extensions-actual-practice-vs-model-encodings.md):
        t_enact = 1 (enactment lag: 2-3 quarters in 2008, ~1 in 2020), t_end = 8 (a legislated
        end typically ~2 quarters past the trough of a 6-quarter mean recession), entry = open
        (every exhaustee while in force), n_extension = 2 (+2 quarters per spell = the paper's
        extension length, the large episodes' +26 weeks).
    Overrides: HAFISCAL_UI_EXT_ENACT_LAG, HAFISCAL_UI_EXT_END, HAFISCAL_UI_EXT_ENTRY,
    HAFISCAL_UI_EXT_QUARTERS (docs/ENV_FLAGS.md).
    """
    env = os.environ if env is None else env
    policy = normalize_policy(policy)
    extra = int(UBspell_extended) - int(UBspell_normal)
    if extra < 1:
        raise ValueError(f"UBspell_extended ({UBspell_extended}) must exceed UBspell_normal ({UBspell_normal})")
    if policy == "paper":
        t_enact, t_end, entry, n_ext = 0, extra, "continuation", extra
    elif policy == "paper_capped":
        # BUG-122. Same window, same entry rule, same everything -- ONE fewer extension state.
        #
        # The paper's sentence is "unemployment benefits are extended from two quarters to four
        # quarters ... including quarters leading up to the recession", so the cap is
        # 2 * UBspell_normal quarters in total, of which UBspell_normal are the ordinary ones:
        #
        #     n_extension = 2 * UBspell_normal - UBspell_normal = UBspell_normal
        #
        # i.e. the extension DOUBLES the entitlement, which is what the sentence says. At the
        # paper's UBspell_normal = 2 that is 2 extension states and six micro states, against
        # `paper`'s 3 and seven.
        #
        # Nothing else has to change, because under `calendar` the micro state IS the number of
        # benefit quarters the spell has drawn, so dropping the third extension state caps every
        # cohort at four -- INCLUDING the two that draw quarters before the recession, which is
        # the whole of BUG-122. Traced row by row (test_ui_extension_schedule.py): the onset
        # cohort and the t=0 entrant keep four, the t=1 entrant three, later entrants two, and
        # only the two pre-onset rows move, 5 -> 4.
        #
        # STRICTLY DEPENDENT ON THE STEP-0 TIMING FIX (`onset_spike_rule`). Without it the onset
        # spike leaves its cohort one position further along the chain, wearing a pre-onset
        # household's label, and this cap would cut it to three -- breaking a row that is right.
        t_enact, t_end, entry, n_ext = 0, extra, "continuation", int(UBspell_normal)
    else:
        t_enact, t_end, entry, n_ext = 1, 8, "open", 2

    def _int(name, default):
        raw = env.get(name, "").strip()
        return int(raw) if raw else default

    t_enact = _int("HAFISCAL_UI_EXT_ENACT_LAG", t_enact)
    t_end = _int("HAFISCAL_UI_EXT_END", t_end)
    n_ext = _int("HAFISCAL_UI_EXT_QUARTERS", n_ext)
    entry = (env.get("HAFISCAL_UI_EXT_ENTRY", "").strip().lower() or entry)
    if entry not in ENTRY_MODES:
        raise ValueError(f"HAFISCAL_UI_EXT_ENTRY={entry!r}; expected one of {ENTRY_MODES}")
    if t_enact < 0 or t_end < t_enact:
        raise ValueError(f"UI extension window needs 0 <= t_enact <= t_end; got {t_enact}, {t_end}")
    if n_ext < 1:
        raise ValueError(f"HAFISCAL_UI_EXT_QUARTERS must be >= 1; got {n_ext}")
    return Window(t_enact, t_end, entry, n_ext, policy)


def num_extension_states(encoding: str, window: Window | None) -> int:
    """Extension micro states the encoding carries (0 under legacy)."""
    if encoding == "legacy":
        return 0
    if encoding == "bug_fix":
        return BUG_FIX_EXTENSION_STATES
    if encoding == "calendar":
        if window is None:
            raise ValueError("calendar encoding needs a resolved Window")
        return int(window.n_extension)
    raise ValueError(f"HAFISCAL_UI_STATE_ENCODING={encoding!r}; expected one of {ENCODINGS}")


def extension_pay_mask(encoding: str, macro, micro, UBspell_normal: int, n_extension: int,
                       window: Window | None):
    """Boolean array: which (macro, micro) composite states pay the extension in recessionUI.

    True only at extension states (micro = UBspell_normal + j, 1 <= j <= n_extension) that the
    encoding's rule pays at that macro state. Vectorized over arrays of any shape.
    """
    macro = np.asarray(macro, dtype=np.int64)
    micro = np.asarray(micro, dtype=np.int64)
    j = micro - int(UBspell_normal)
    is_ext = (j >= 1) & (j <= int(n_extension))
    if encoding == "legacy":
        return np.zeros_like(is_ext, dtype=bool)
    if encoding == "bug_fix":
        return is_ext & (macro % 2 == 1)
    if encoding == "calendar":
        if window is None:
            raise ValueError("calendar encoding needs a resolved Window")
        t = experiment_period(macro)
        shift = (j - 1) if window.entry == "continuation" else 0
        return is_ext & (t >= window.t_enact + shift) & (t <= window.t_end)
    raise ValueError(f"HAFISCAL_UI_STATE_ENCODING={encoding!r}; expected one of {ENCODINGS}")


def pays_extension(encoding: str, macro_idx: int, micro_idx: int, UBspell_normal: int,
                   n_extension: int, window: Window | None) -> bool:
    """Scalar form of :func:`extension_pay_mask`."""
    return bool(extension_pay_mask(encoding, macro_idx, micro_idx, UBspell_normal,
                                   n_extension, window))


def describe(encoding: str, window: Window | None, num_base_MrkvStates: int) -> str:
    """One log line for the encoding/policy in force."""
    if encoding == "legacy":
        return (f"[ui-encoding] HAFISCAL_UI_STATE_ENCODING=legacy -> {num_base_MrkvStates} micro states; "
                "extension = the published freeze window (transition_ub=False)")
    if encoding == "bug_fix":
        return (f"[ui-encoding] HAFISCAL_UI_STATE_ENCODING=bug_fix -> {num_base_MrkvStates} micro states; "
                "u3Q/u4Q paid iff the current macro state is the recession (2026-05-16 rule)")
    return (f"[ui-encoding] HAFISCAL_UI_STATE_ENCODING=calendar -> {num_base_MrkvStates} micro states "
            f"({window.n_extension} extension states); policy '{window.policy}': paid at experiment "
            f"periods t_enact={window.t_enact}..t_end={window.t_end}, entry={window.entry}")
