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
    return path[:-4] + f'_{interp}.txt'


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
    cand = _prefer_candidate(suffixed)
    if cand != suffixed:
        return cand
    if os.path.exists(suffixed):
        return suffixed
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


def calib_suffix():
    """Full calibration-file tag: interp_suffix() + world_suffix().

    The combined suffix for files that are BOTH interpretation- and
    world-specific (the discount-factor estimates). Order is interpretation
    first, then world, so an ESC as-corrected run writes '_ESC_ascorrected'.

    Returns
    -------
    str: e.g. '' (CDC/default), '_ESC' (ESC/default),
         '_ascorrected' (CDC/as-corrected), '_ESC_ascorrected' (ESC/as-corrected).
    """
    return interp_suffix() + world_suffix()


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
    world = world_suffix()     # '' or '_ascorrected'

    def _try(p):
        """Return a usable path (candidate sibling or p itself) or None."""
        cand = _prefer_candidate(p)
        if cand != p:
            return cand
        return p if os.path.exists(p) else None

    # 1) the exact interp+world file
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
