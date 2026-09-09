"""
HAFISCAL_INTERPRETATION helper module.

Single source of truth for the CDC-vs-ESC interpretation flag and the
filename-suffix convention. Used by:
  - tm_methods.py kernel functions (interpretation parameter dispatch)
  - AggFiscalModel.py AggFiscalType (self.interpretation attribute)
  - EstimAggFiscalMAIN.py (Phase 3 filename-suffix wiring landed 2026-05:
    interp_suffix() on the DiscFacEstim/registry result paths)
  - Estimation_BetaNablaSplurge.py (reads get_interpretation() for the Step-1
    agent-type dispatch, BUG-035 — not the filename suffix)
  - test files (so tests can override the env var via patching)

Per plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md §6
(design decisions resolved 2026-04-27):
  - Configuration mechanism: BOTH env var and CLI flag (precedence:
    explicit kwarg > env var > default 'CDC').
  - Default = 'CDC' preserves byte-identical behavior for unflagged runs.
  - Filename suffix convention: append '_<INTERPRETATION>' before '.txt'.
  - Reader-side fallback: if suffixed file doesn't exist, fall back to
    un-suffixed (legacy compat).

Usage:

  from _interpretation import get_interpretation, suffix_path, resolve_path

  # Read the env var:
  interp = get_interpretation()  # → 'CDC' or 'ESC'

  # Write to a suffixed file:
  out_path = suffix_path('Result_AllTarget.txt')
  # → 'Result_AllTarget_CDC.txt' or 'Result_AllTarget_ESC.txt'

  # Read with fallback:
  in_path = resolve_path('Result_AllTarget.txt')
  # → suffixed if it exists, else un-suffixed

WORLD axis (HAFISCAL_WORLD, owner ruling 2026-06-14): calibration betas are
ALSO world-specific (the as-corrected counterfactual re-estimates them). The
world tag is appended AFTER the interpretation tag, ONLY for the betas:

  from _interpretation import calib_suffix, resolve_calib_path

  # Write the betas (interp + world):
  'DiscFacEstim_CRRA_2.0_R_1.01' + calib_suffix() + '.txt'
  # → '..._ESC_ascorrected.txt' under ESC + HAFISCAL_WORLD=as-corrected

  # Read the betas (interp + world, with a loud wrong-world fallback guard):
  resolve_calib_path('.../DiscFacEstim_CRRA_2.0_R_1.01.txt')

The SHARED Step-1 splurge (Result_AllTarget_*) is perm_during_unemp-independent
and stays on the interp-only suffix_path()/resolve_path()/interp_suffix().
"""

import os


def get_interpretation(require=False):
    """Return current HAFISCAL_INTERPRETATION value, validated.

    Reads `os.environ['HAFISCAL_INTERPRETATION']`; defaults to 'CDC'.
    Raises ValueError on invalid values (fail-fast).

    Parameters
    ----------
    require : bool, default False
        If True and HAFISCAL_INTERPRETATION is None/empty (i.e. NOT
        explicitly set in the environment), raise RuntimeError rather than
        silently assuming the 'CDC' default. Use at guarded entry points
        (BUG-051 matched-pair safety) where assuming an interpretation is
        unsafe. When False, the legacy default-'CDC' behavior is preserved
        for backward compatibility.

    Returns
    -------
    str: 'CDC' or 'ESC' (always uppercase).
    """
    raw = os.environ.get('HAFISCAL_INTERPRETATION')
    if require and (raw is None or raw == ''):
        raise RuntimeError(
            "HAFISCAL_INTERPRETATION must be set explicitly to 'ESC' or "
            "'CDC' — refusing to assume a default in a guarded entry point"
        )
    val = (raw if raw else 'CDC').upper()
    if val not in ('CDC', 'ESC'):
        raise ValueError(
            f"HAFISCAL_INTERPRETATION must be 'CDC' or 'ESC', got: {val!r}"
        )
    return val


def assert_interpretation(passed, context=''):
    """Assert an explicitly-passed interpretation matches the env single source.

    Matched-pair safety guard (BUG-051): a function that takes an explicit
    `interpretation=` argument must not run a TM kernel / asset rule under an
    interpretation that disagrees with HAFISCAL_INTERPRETATION — that is
    exactly the silent CDC-kernel-under-ESC-run class of bug this guards.

    Parameters
    ----------
    passed : str or None
        The explicit interpretation argument. If None, no check is done
        (caller is expected to resolve None from get_interpretation()).
    context : str
        Caller name / site, surfaced in the error message.

    Raises
    ------
    RuntimeError if `passed` is not None and disagrees (case-insensitively)
    with get_interpretation().
    """
    if passed is None:
        return
    env_interp = get_interpretation()
    if str(passed).upper() != env_interp:
        raise RuntimeError(
            f"matched-pair violation: explicit interpretation "
            f"{str(passed).upper()!r} disagrees with "
            f"HAFISCAL_INTERPRETATION={env_interp!r}"
            + (f" (context: {context})" if context else "")
        )


def suffix_path(path):
    """Append '_<INTERPRETATION>' before '.txt' suffix.

    Parameters
    ----------
    path : str
        File path ending in '.txt'.

    Returns
    -------
    str: '<basename>_<INTERPRETATION>.txt'.

    Raises
    ------
    ValueError if path does not end in '.txt' (defensive — current convention
    only applies to .txt files).
    """
    if not path.endswith('.txt'):
        raise ValueError(
            f"suffix_path expects a .txt path, got: {path!r}"
        )
    interp = get_interpretation()
    # income-convention component (R-e item-2 / BUG-077): '' by default,
    # '_netinc' or '_taustar' under the matched-calibration axes, so the
    # Step-1 splurge family and other interp-scoped files stay paired
    # with the convention they were estimated under.
    return path[:-4] + f'_{interp}' + income_suffix() + '.txt'


def _prefer_candidate(path):
    """QE-baseline freeze: prefer the `_candidate` sibling when it exists.

    Pipeline runs write intermediates as `<base>_candidate.txt`
    (FromPandemicCode/generated_output.py), so readers must pick those up
    for regenerated results to flow downstream. Under HAFISCAL_PROMOTE=1
    the canonical (frozen) file is read instead. The '_candidate' suffix
    constant mirrors generated_output.CANDIDATE_SUFFIX.
    """
    if os.environ.get('HAFISCAL_PROMOTE') == '1':
        return path
    root, ext = os.path.splitext(path)
    cand = root + '_candidate' + ext
    return cand if os.path.exists(cand) else path


def resolve_path(path):
    """Return suffixed path if it exists; else fall back to un-suffixed.

    Used by reader sites to support backward-compat with legacy un-suffixed
    files while preferring the suffixed variant when it exists.
    Each variant is candidate-aware (see _prefer_candidate): a fresh
    `_candidate` sibling from the current pipeline run wins over the frozen
    canonical file.

    Parameters
    ----------
    path : str
        File path ending in '.txt'.

    Returns
    -------
    str: suffixed path if it exists, else `path` unchanged (each preferring
    its `_candidate` sibling when present).
    """
    suffixed = suffix_path(path)

    # WORLD-AWARENESS for the fit tables (2026-09-06; the item filed 2026-08-24 02:10).
    # `resolve_calib_path` applies the world suffix, so DiscFacEstim_* is matched --
    # but this generic resolver did not, so under HAFISCAL_WORLD=as-corrected the
    # tabular generators and the Lorenz/IMPC figures read the DEFAULT world's
    # `AllResults_..._ESC.txt` while the run's betas came from
    # `DiscFacEstim_..._ESC_ascorrected.txt`. Mixed-world exhibits, silently.
    #
    # Scoped to AllResults on purpose. This resolver also serves the Step-1 splurge
    # family, which is deliberately world-SHARED (see calib_suffix: the splurge file is
    # interp-only), so a blanket world suffix here would break that read instead.
    #
    # The fallback is NOT silent: an as-corrected run reading the default world's fit
    # table is a results error, so it warns, exactly as the ESC hazard below does.
    _world = world_suffix()
    if _world and os.path.basename(path).startswith('AllResults'):
        _w_suffixed = suffixed[:-4] + _world + '.txt'
        _w_cand = _prefer_candidate(_w_suffixed)
        if _w_cand != _w_suffixed or os.path.exists(_w_suffixed):
            return _w_cand
        import warnings
        warnings.warn(
            f"[world MISMATCH] HAFISCAL_WORLD={get_world()!r} but the matched fit table "
            f"'{os.path.basename(_w_suffixed)}' does not exist; falling back to "
            f"'{os.path.basename(suffixed)}', which is the DEFAULT world's. The betas "
            f"for this run come from the as-corrected calibration, so the exhibits built "
            f"from this file would mix two worlds. Run the fit-table pass under "
            f"HAFISCAL_WORLD=as-corrected, or pass the file explicitly.",
            stacklevel=2)

    cand = _prefer_candidate(suffixed)
    if cand != suffixed:
        return cand
    if os.path.exists(suffixed):
        return suffixed
    # The income axis NEVER falls back (matched-triple guard, BUG-077):
    # a tau*-world (or netinc) run consuming the gross-convention
    # splurge/calibration would break the {tau*, sigma, beta} pairing.
    # Step-1 (the writer) never reaches this reader, so no bootstrap
    # escape is needed here — the HALT enforces cascade order.
    _inc = income_suffix()
    if _inc:
        raise FileNotFoundError(
            f"[{_inc[1:]} calibration MISSING] "
            f"HAFISCAL_CALIB_TARGET_INCOME="
            f"{os.environ.get('HAFISCAL_CALIB_TARGET_INCOME')!r} requires "
            f"'{os.path.basename(suffixed)}' (the income-convention-matched "
            f"file; for taustar run Step-1 then Step-2 under the flag "
            f"first). Refusing the gross-convention fallback.")
    # HAZARD GUARD (added 2026-06-04): under ESC, silently falling back to the
    # un-suffixed default loads the CDC/legacy calibration (e.g.
    # DiscFacEstim_CRRA_2.0_R_1.01.txt holds CDC betas). An ESC run reading CDC
    # discount factors is WRONG and silently shifted the recession+AD Check
    # multiplier ~+4% (1.32 -> 1.37) for ESC runs done before the aggregate
    # _ESC.txt was synced. Warn loudly so this cannot recur unnoticed.
    if get_interpretation() == 'ESC':
        import warnings
        warnings.warn(
            f"[ESC calibration HAZARD] expected ESC file "
            f"'{os.path.basename(suffixed)}' not found; falling back to the "
            f"NON-ESC (CDC/legacy) file '{os.path.basename(path)}'. An ESC run "
            f"reading CDC discount factors is WRONG (can shift multipliers ~4%). "
            f"Regenerate the _ESC file or set HAFISCAL_DISCFAC_FILE explicitly.",
            stacklevel=2)
    return _prefer_candidate(path)


def interp_suffix():
    """Return '_<INTERP>' for ESC; empty string for CDC.

    Use this at WRITE sites that want CDC to remain unsuffixed (matching
    the legacy filenames the rest of the codebase already references) while
    tagging ESC outputs with a distinct `_ESC` suffix.

    This is the registry mechanism for cross-interpretation isolation: ESC
    writes a separate file from CDC, so warm-start, comparison, and reads
    get the right artifact for their interpretation.

    Returns
    -------
    str: '_ESC' if HAFISCAL_INTERPRETATION=ESC; '' otherwise.

    Examples
    --------
    >>> # CDC (default):
    >>> 'DiscFacEstim_CRRA_2.0_R_1.01' + interp_suffix() + '.txt'
    'DiscFacEstim_CRRA_2.0_R_1.01.txt'
    >>> # ESC (HAFISCAL_INTERPRETATION=ESC):
    >>> 'DiscFacEstim_CRRA_2.0_R_1.01' + interp_suffix() + '.txt'
    'DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt'
    """
    interp = get_interpretation()
    return '_ESC' if interp == 'ESC' else ''


# ---------------------------------------------------------------------------
# WORLD axis (HAFISCAL_WORLD): calibration-file isolation for the as-corrected
# counterfactual. The two worlds differ on exactly one economic axis
# (perm_during_unemp), so the `as-corrected` betas (DiscFacEstim_*) must NOT
# clobber the `default`/headline betas. Convention (owner ruling 2026-06-14;
# plans/20260614_as-corrected-calibration-run-spec.md):
#   default       -> no world tag  (byte-for-byte legacy, non-breaking)
#   as-corrected  -> '_ascorrected' AFTER the interpretation tag
#       e.g.  DiscFacEstim_CRRA_2.0_R_1.01_ESC_ascorrected.txt
# The SHARED Step-1 splurge (Result_AllTarget_*) is perm_during_unemp-INDEPENDENT
# and is NOT world-tagged — it keeps the interp-only resolve_path()/interp_suffix().
# ---------------------------------------------------------------------------

def get_world(require=False):
    """Return current HAFISCAL_WORLD value, validated.

    Reads `os.environ['HAFISCAL_WORLD']`; defaults to 'default'. Raises
    ValueError on invalid values (fail-fast). Mirrors the validation in
    EstimParameters.py's WORLD-axis block.

    Parameters
    ----------
    require : bool, default False
        If True and HAFISCAL_WORLD is unset/empty, raise RuntimeError rather
        than silently assuming 'default'.

    Returns
    -------
    str: 'default' or 'as-corrected' (lowercased).
    """
    raw = os.environ.get('HAFISCAL_WORLD')
    if require and (raw is None or raw == ''):
        raise RuntimeError(
            "HAFISCAL_WORLD must be set explicitly to 'default' or "
            "'as-corrected' — refusing to assume a default in a guarded site"
        )
    val = (raw if raw else 'default').strip().lower()
    if val not in ('default', 'as-corrected'):
        raise ValueError(
            f"HAFISCAL_WORLD must be 'default' or 'as-corrected', got: {val!r}. "
            "exact published-QE is the frozen tag v2026-01-09-18-17, not a runtime world."
        )
    return val


def world_suffix():
    """Return '_ascorrected' for the as-corrected world; '' for default.

    Companion to interp_suffix(). Appended AFTER the interpretation tag at
    calibration WRITE sites that produce world-specific betas (DiscFacEstim_*),
    so default stays byte-for-byte legacy.

    Returns
    -------
    str: '_ascorrected' if HAFISCAL_WORLD=as-corrected; '' otherwise.
    """
    return '_ascorrected' if get_world() == 'as-corrected' else ''


def income_suffix():
    """Return '_netinc' for the net income-convention calibration; '' default.

    R-e item-2 BONDED PAIR (owner "go" 2026-08-09): discount factors
    estimated against wealth/DISPOSABLE-income targets
    (HAFISCAL_CALIB_TARGET_INCOME=net — the convention matching the
    HANK-SAM block's (1-tau)*w*N household income) are a DIFFERENT
    calibration from the gross-convention production betas and must never
    be silently interchanged. Slots between interpretation and world:
    e.g. '_ESC_netinc'.

    Returns
    -------
    str: '_netinc' if HAFISCAL_CALIB_TARGET_INCOME=net; '' otherwise.
    """
    v = os.environ.get('HAFISCAL_CALIB_TARGET_INCOME', 'gross').strip().lower()
    if v == 'net':
        return '_netinc'
    if v == 'taustar':
        # BUG-077 stage C: the shared derived-tau* world (income wedge
        # = fiscal_tau_star.TAU_STAR ~ 0.0407; SCF gross-denominator
        # convention kept — only the wealth/income RATIO targets are
        # restated by 1/(1-tau*)).
        return '_taustar'
    return ''


def calib_suffix():
    """Full calibration-file tag: interp_suffix() + income_suffix() + world_suffix().

    The combined suffix for files that are interpretation-, income-convention-
    and world-specific (the discount-factor estimates). Order is interpretation
    first, then income convention, then world, so an ESC net-income
    as-corrected run writes '_ESC_netinc_ascorrected'.

    Returns
    -------
    str: e.g. '' (CDC/default), '_ESC' (ESC/default),
         '_ESC_netinc' (ESC/net-income bonded pair),
         '_ascorrected' (CDC/as-corrected), '_ESC_ascorrected' (ESC/as-corrected).
    """
    return interp_suffix() + income_suffix() + world_suffix()


def resolve_calib_path(path):
    """World + interpretation aware reader for calibration betas (DiscFacEstim_*).

    Looks for `<base><interp><world>.txt` (candidate-aware), with a fallback
    chain that NEVER silently loads the WRONG world's betas:

      1. interp+world file (the exact file this run should use);
      2. if as-corrected and (1) is missing -> LOUD warning, then fall back to
         the interp-only (default-world) file — an as-corrected run reading the
         default-world betas is a results error, so it must be visible;
      3. if ESC and still missing -> the existing LOUD ESC hazard warning,
         then the un-suffixed legacy file.

    For the `default` world (world_suffix()=='') this is byte-for-byte identical
    to resolve_path(): it looks for `<base><interp>.txt` then falls back to the
    un-suffixed legacy file, with the same ESC hazard guard. Use resolve_path()
    (interp-only, no world) for the SHARED splurge file.
    """
    if not path.endswith('.txt'):
        raise ValueError(f"resolve_calib_path expects a .txt path, got: {path!r}")
    import warnings
    stem = path[:-4]
    interp = interp_suffix()   # '' or '_ESC'
    income = income_suffix()   # '' or '_netinc'
    world = world_suffix()     # '' or '_ascorrected'

    def _try(p):
        """Return a usable path (candidate sibling or p itself) or None."""
        cand = _prefer_candidate(p)
        if cand != p:
            return cand
        return p if os.path.exists(p) else None

    # 1) the exact interp+income+world file
    hit = _try(stem + interp + income + world + '.txt')
    if hit is not None:
        return hit

    # 1b) the income axis NEVER falls back for CONSUMERS (bonded pair, R-e
    # item 2): a net-income run consuming gross-convention betas is exactly
    # the inconsistency the pair exists to remove — HALT instead. Sole
    # exception: the ESTIMATOR'S OWN BOOTSTRAP (the run that CREATES the
    # paired file; the Step-2 drivers setdefault HAFISCAL_CALIB_BOOTSTRAP=1)
    # may seed module imports from the gross-convention chain — starting
    # values only; the optimizer's starts are its own and the objective
    # overwrites the discount factors every evaluation.
    if income:
        if os.environ.get('HAFISCAL_CALIB_BOOTSTRAP', '0') != '1':
            raise FileNotFoundError(
                f"[netinc calibration MISSING] HAFISCAL_CALIB_TARGET_INCOME=net "
                f"requires the paired calibration file "
                f"'{os.path.basename(stem + interp + income + world + '.txt')}' "
                f"(betas estimated against wealth/DISPOSABLE-income targets). "
                f"Refusing to fall back to the gross-convention betas. Generate it "
                f"with: HAFISCAL_CALIB_TARGET_INCOME=net python estim_phase2_tm_a.py")
        warnings.warn(
            f"[netinc BOOTSTRAP] paired file "
            f"'{os.path.basename(stem + interp + income + world + '.txt')}' not "
            f"found; seeding module imports from the gross-convention chain "
            f"(STARTING VALUES ONLY — estimator bootstrap). If you see this "
            f"outside a Step-2 estimation run, something is wrong.",
            stacklevel=2)
        # Prefer the exact income-less file (e.g. the production _ESC betas)
        # as the seed before the historical warning chain below.
        hit = _try(stem + interp + world + '.txt')
        if hit is not None:
            return hit

    # 2) as-corrected missing -> warn loudly, fall back to default-world (interp) file
    if world:
        warnings.warn(
            f"[as-corrected calibration HAZARD] expected world file "
            f"'{os.path.basename(stem + interp + world + '.txt')}' not found; "
            f"falling back to the DEFAULT-world file "
            f"'{os.path.basename(stem + interp + '.txt')}'. An as-corrected run "
            f"reading the default-world (perm-during-unemp=on) betas is WRONG — "
            f"re-estimate the as-corrected calibration "
            f"(plans/20260614_as-corrected-calibration-run-spec.md) or set "
            f"HAFISCAL_DISCFAC_FILE explicitly.",
            stacklevel=2)
        hit = _try(stem + interp + '.txt')
        if hit is not None:
            return hit

    # 3) interp(+world) missing -> ESC hazard guard, then un-suffixed legacy
    if interp == '_ESC':
        warnings.warn(
            f"[ESC calibration HAZARD] expected ESC file "
            f"'{os.path.basename(stem + interp + '.txt')}' not found; falling "
            f"back to the NON-ESC (CDC/legacy) file '{os.path.basename(path)}'. "
            f"An ESC run reading CDC discount factors is WRONG (can shift "
            f"multipliers ~4%). Regenerate the _ESC file or set "
            f"HAFISCAL_DISCFAC_FILE explicitly.",
            stacklevel=2)
    return _prefer_candidate(path)


def assert_calib_vintage_matches(betas_path, splurge_path, rtol=1e-3):
    """As-corrected vintage guard (owner charge 2026-08-23 night: "fix this").

    The trap it closes: a matched-world calibration file (``_ESC_ascorrected``,
    or its ``_candidate`` shadow) can be STALE — estimated under a different
    splurge/epoch — and mtimes cannot reveal it (git checkouts equalize them;
    the 08-12 saved-cal-locks incident and the 08-23 W-FIX chimera arms were
    both tracked-stale-content traps). The content-based check: every
    DiscFacEstim file records the splurge it was estimated under in its
    ``Parameters: ... Splurge = X`` footer; a MATCHED consumption requires that
    footer to equal the splurge actually in use ({calibration, splurge} is one
    atomic triple with the interpretation — the matched-pair rule). Applies
    only in the as-corrected world: default-world candidates legitimately
    differ pre-promotion, and the default lineage is guarded by LOCKED_TABLES
    + the install workflow instead.

    rtol=1e-3 is the S1 flat-valley acceptance class: splurge values inside it
    are indistinguishable to the S1 objective (f-ties) and PROVEN calibration-
    equivalent (2026-08-23: S2 estimated under 0.29984 matched the install
    estimated under 0.29987 to 1e-6 rel on every group). The trap this guard
    exists for is epoch-scale staleness (0.267 vs 0.300 = 11% rel) — caught
    with 100x margin.

    Raises RuntimeError on a vintage mismatch; silently returns when not in
    the as-corrected world, when either file is missing, or when either value
    cannot be parsed (the pre-existing loud missing-file warnings own those).
    """
    if world_suffix() != '_ascorrected':
        return
    import re as _re
    try:
        foot = open(betas_path).read()
        m = _re.search(r"Splurge\s*=\s*([0-9.eE+-]+)", foot)
        sp_file = float(m.group(1)) if m else None
        stxt = open(splurge_path).read()
        m2 = _re.search(r"'splurge'\s*:\s*([0-9.eE+-]+)", stxt)
        sp_use = float(m2.group(1)) if m2 else None
    except OSError:
        return
    if sp_file is None or sp_use is None:
        return
    if abs(sp_file - sp_use) > rtol * max(abs(sp_use), 1e-12):
        raise RuntimeError(
            f"[as-corrected VINTAGE MISMATCH] calibration {betas_path!r} was "
            f"estimated under Splurge={sp_file!r} but the run consumes "
            f"Splurge={sp_use!r} (from {splurge_path!r}). The as-corrected "
            f"calibration is stale for this epoch — re-estimate it (S2 under "
            f"HAFISCAL_WORLD=as-corrected) or refresh the _ascorrected["
            f"_candidate] files. Refusing to run a mismatched counterfactual.")
