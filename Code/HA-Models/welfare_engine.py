"""Canonical welfare-6 engine resolution (the 2026-08-02 hybrid default).

One place defines what "the hybrid methodology" means so every entry point
(run_welfare6_parallel children, direct welfare6_scenario singles, do_all
Step 5b via the wrapper) resolves the same certified configuration.

Owner rulings 2026-08-02 (plans/20260802-0030h §2 ledger): replay-fed JAX-AD
(row 2, residual accepted under sig-figs), capture-presolve cache (row 3),
corrected-head CRATIO_PREV (row 3b). Certification + validation:
plans/20260802-0300h_canonical-hybrid-default_plan.md.

Engine values
-------------
hybrid : the accepted configuration (HYBRID_BUNDLE below), applied via
         env.setdefault — any EXPLICIT per-flag env override still wins.
hark   : the pre-arc all-HARK path — the ARC flags are hard-cleared (the
         one-knob rollback, bit-identity proven vs the pre-arc reference).
         Legacy defaults that predate the arc (HAFISCAL_USE_JAX_MC and
         HAFISCAL_USE_SOLUTION_CACHE, both wrapper-era setdefaults) are left
         to their owners: under the uncapped world USE_JAX_MC without
         UNCAPPED auto-routes to HARK-AD, which IS the hark path.

Resolution precedence (resolve_welfare_engine):
1. explicit HAFISCAL_WELFARE_ENGINE (invalid values raise — fail loudly);
2. world guard: HAFISCAL_QE_FIDELITY=1 or HAFISCAL_WORLD=as-corrected force
   'hark' (the hybrid engine is an owner-adopted IMPROVEMENT, not a bug fix;
   the bug-fix-only world and the QE escape hatch must not silently change
   method);
3. default: 'hybrid'.
"""

import os

# The certified bundle (CERT band 2026-08-02, git 1c5b2b76 lineage): the
# PRESOLVE/AD_INIT pairing is required by the loader's co-gate
# (solution_cache/cache.py:346-350 — PRESOLVE_CACHE alone is a silent no-op).
HYBRID_BUNDLE = {
    "HAFISCAL_USE_JAX_MC": "1",
    "HAFISCAL_USE_JAX_MC_UNCAPPED": "1",
    "HAFISCAL_JAX_MC_REPLAY_AD": "1",
    "HAFISCAL_REPLAY_CRATIO_PREV": "1",
    "HAFISCAL_REPLAY_PRESOLVE_CACHE": "1",
    "HAFISCAL_AD_INIT_CACHE": "1",
    "HAFISCAL_USE_SOLUTION_CACHE": "1",
}

# Cleared under engine=hark: exactly the flags this arc introduced/repurposed.
# USE_JAX_MC / USE_SOLUTION_CACHE are NOT arc flags (legacy wrapper defaults)
# and are left untouched so hark reproduces the pre-arc environment.
ARC_KEYS = (
    "HAFISCAL_USE_JAX_MC_UNCAPPED",
    "HAFISCAL_JAX_MC_REPLAY_AD",
    "HAFISCAL_REPLAY_CRATIO_PREV",
    "HAFISCAL_REPLAY_PRESOLVE_CACHE",
    "HAFISCAL_AD_INIT_CACHE",
)

_TRUTHY = ("1", "on", "true")


def resolve_welfare_engine(env=None):
    """Return 'hybrid' or 'hark' per the precedence in the module docstring."""
    if env is None:
        env = os.environ
    explicit = env.get("HAFISCAL_WELFARE_ENGINE", "").strip().lower()
    if explicit:
        if explicit not in ("hybrid", "hark"):
            raise ValueError(
                f"HAFISCAL_WELFARE_ENGINE={explicit!r}: valid values are "
                "'hybrid' (canonical default) or 'hark' (pre-arc rollback)")
        return explicit
    if env.get("HAFISCAL_QE_FIDELITY", "").strip().lower() in _TRUTHY:
        return "hark"
    if env.get("HAFISCAL_WORLD", "").strip().lower() == "as-corrected":
        return "hark"
    return "hybrid"


def apply_welfare_engine_defaults(env=None, verbose=True):
    """Resolve the engine and apply it to ``env`` (default: os.environ).

    hybrid: setdefault the bundle (explicit per-flag overrides win).
    hark:   hard-clear the ARC flags (one-knob rollback).
    Returns the resolved engine string.
    """
    if env is None:
        env = os.environ
    engine = resolve_welfare_engine(env)
    if engine == "hybrid":
        for k, v in HYBRID_BUNDLE.items():
            env.setdefault(k, v)
        if verbose:
            print(f"[welfare-engine] hybrid (canonical default 2026-08-02): "
                  f"bundle applied via setdefault "
                  f"({len(HYBRID_BUNDLE)} keys; explicit env wins)",
                  flush=True)
    else:
        for k in ARC_KEYS:
            env.pop(k, None)
        if verbose:
            print("[welfare-engine] hark (pre-arc rollback): arc flags "
                  "cleared", flush=True)
    # Execution-platform pin (2026-08-02, R3-verification finding): the
    # certified numbers are CPU-kernel numbers, and the parallel runner pins
    # its children accordingly (hw_slot env) — but a BARE welfare6_scenario
    # single carried no pin, so on a GPU box jax auto-initialized CUDA and
    # the replay kernel's GPU reduction topology shifted the AD fixed point
    # at ULP scale (deterministic 1e-15-class panel deltas vs the CPU canon,
    # growing with recession dwell; dur-0 untouched). setdefault so EVERY
    # entry point runs the certified CPU configuration by default; an
    # explicit JAX_PLATFORMS (the GPU opt-in path) still wins. Applied for
    # both engines — it is a platform default, not an engine flag.
    env.setdefault("JAX_PLATFORMS", "cpu")
    return engine
