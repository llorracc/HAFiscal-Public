"""Shared plumbing for the step4 package: paths, flags, kernel loader."""
import os
import sys

HA_MODELS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPC_DIR = os.path.join(HA_MODELS_DIR, "FromPandemicCode")

MONOLITH_JACOBIANS = os.path.join(FPC_DIR, "HA-Fiscal-HANK-SAM.py")
MONOLITH_GE = os.path.join(FPC_DIR, "HA-Fiscal-HANK-SAM-to-python.py")


def ensure_paths():
    """Put Code/HA-Models and FromPandemicCode on sys.path (in that
    priority order, matching the monoliths' runtime context)."""
    for p in (HA_MODELS_DIR, FPC_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)


def chdir_fpc():
    """The monolith pair runs with cwd=FromPandemicCode (do_all Step 4);
    generated_output's candidate routing and a handful of relative reads
    resolve against it. The entries reproduce that context exactly."""
    os.chdir(FPC_DIR)


def flag_on(name, default):
    return os.environ.get(name, default).strip().lower() in ("1", "on", "true")


def flag_off(name, default):
    return os.environ.get(name, default).strip().lower() in ("0", "off", "false")


def resolve_tau_ss():
    """The steady-state tax rate + basket mode (BUG-077 stage B).

    HAFISCAL_TAU_SS (BUG-077 WITHDRAWN, owner 2026-08-10: "the original
    setup was a feature not a bug" — tau=0.3 is the average rate that
    finances G ~ 26% of output, government expenditure the PE model
    deliberately abstracts from, PLUS it supplies the realistic
    marginal automatic-stabilizer leakage that damps the GE demand
    loop; the derived minimal-government tau* gutted the stabilizer
    and inflated every multiplier x1.33 — see
    conclusions_private/2026-08-10_tau-two-roles-lessons_coauthor-note.md):
      'legacy' (DEFAULT) -> 0.3 with the historical 0.5-core UI
        booking — the published construction, now DOCUMENTED as the
        G-financed design.
      'derived' -> the archived tau* exploration arm
        (fiscal_tau_star.TAU_STAR ~ 0.0407: funds only the full-0.7
        eligible UI + debt interest, G==0; PE-first basket rides).
      an explicit float -> that rate with the derived-basket semantics.

    Returns (tau_ss, mode) with mode in {'derived', 'legacy',
    'explicit'}.
    """
    v = os.environ.get("HAFISCAL_TAU_SS", "legacy").strip().lower()
    if v == "legacy":
        from fiscal_tau_star import TAU_LEGACY
        return float(TAU_LEGACY), "legacy"
    if v == "derived":
        ensure_paths()
        from fiscal_tau_star import TAU_STAR
        return float(TAU_STAR), "derived"
    return float(v), "explicit"


def monolith_route_reason(stage):
    """Return a human-readable reason to route this invocation to the
    frozen monolith, or None to run the package (live fixed semantics).

    stage: "jacobians" | "ge". The package implements ONLY the fixed
    construction; every historical-semantics request goes to the frozen
    engine, which honors the full flag surface bit-for-bit."""
    eng = os.environ.get("HAFISCAL_STEP4_ENGINE", "").strip().lower()
    if eng == "monolith":
        return "HAFISCAL_STEP4_ENGINE=monolith (explicit engine override)"
    if eng == "package":
        return None  # explicit package request wins over the checks below
    if os.environ.get("HAFISCAL_QE_FIDELITY", "") == "1":
        return "HAFISCAL_QE_FIDELITY=1 (published construction, bugs included)"
    if stage == "jacobians":
        if flag_off("HAFISCAL_STEP4_SHOCK_FIX", "1"):
            return "HAFISCAL_STEP4_SHOCK_FIX=0 (historical stale-shock arm)"
        if flag_off("HAFISCAL_STEP4_ZEROTH_FIX", "1"):
            return "HAFISCAL_STEP4_ZEROTH_FIX=0 (historical zeroth column)"
    return None


_FASTBACK_MODS = None


def fast_backward_mods():
    """L3b compiled-kernel loader (same semantics as the monolith's
    _fast_backward_mods): (backward_kernel, fast_tranmat) when
    HAFISCAL_STEP4_FAST_BACKWARD is enabled and importable; None for the
    certified python path."""
    global _FASTBACK_MODS
    if flag_off("HAFISCAL_STEP4_FAST_BACKWARD", "1"):
        return None
    if _FASTBACK_MODS is None:
        try:
            ensure_paths()
            import step4_backward_kernel as _bk
            import step4_fast_tranmat as _ft
            _FASTBACK_MODS = (_bk, _ft)
            print("[fast_backward] L3b compiled backward pass ACTIVE")
        except Exception as _e:
            print(f"[fast_backward] unavailable ({type(_e).__name__}: {_e}); python path")
            _FASTBACK_MODS = False
    return _FASTBACK_MODS or None
