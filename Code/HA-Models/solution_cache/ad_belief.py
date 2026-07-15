"""
Cross-phase AD-belief sidecar (Plan 1, LEG B — WARM-START ONLY, default-OFF consume).

Step-5a (TM multipliers) and Step-5b (MC welfare-6) each solve the SAME aggregate-demand
fixed point per recession ``shock_type``, in two processes that never share state. The
AD outer loop is >99% of an AD cell's wall (see ``ad_cache.py:20``). This module lets
Step-5a publish its converged macro AD belief (``economy.CFunc``) as a tiny durable
artifact that Step-5b can load to **seed** ``solve_ad_recession``'s loop, reducing the
iteration count.

IMPORTANT — this is a WARM START, NOT a skip. The published belief is ONLY an initial
guess. Step-5b's ``solve_ad_recession`` runs its real fixed-point loop to its own
``convergence_cutoff`` unchanged, so the converged result is NUMERICALLY EQUIVALENT to
the flat-start solve — NOT byte-identical. A loop-seed warm start changes the AD
trajectory, which crosses the convergence_cutoff step-threshold at a different point than
the flat trajectory, so the two converged beliefs differ by an amount BELOW the cutoff
(MEASURED 2026-06-22 at HS_Only recessionCheck_AD: welfare reldiff 9.8e-8, cLvl panel max
reldiff 2.5e-5; iterations 4 -> 1). For BYTE-identical fast reproduction of frozen tables
use the AD CACHE (``ad_cache.py``, exact replay); this seed is for FRESH / candidate runs
(``HAFISCAL_AD_BELIEF_SEED``, default OFF). The Step-5a TM belief and the Step-5b MC belief are NOT the same object
(TM has a hard Cratio clip + mill_rule; MC has neither) — but because the seed is
never trusted as a result, that cross-engine difference is irrelevant to correctness.
See ``plans/20260622_welfare6-reuse-presolved-AD-equilibria.md`` §"Why Leg B cannot skip".

The sidecar is the macro belief ONLY (``N x N`` ``CRule(intercept, slope)`` pairs,
``N`` = macro state count, <=252 under bug_fix) — NOT the per-cohort ``agent.solution``,
which is a deterministic function of ``(CFunc, calibration)`` reproducible by
``eco.solve()``. It carries a calibration+engine fingerprint
(``keys.hash_solve_inputs(keys.gather_solve_inputs(...))`` with ``mc_method``), an
``engine`` tag (``'tm'`` / ``'hark_mc'``), and the composite ``regime_fingerprint()``
so a wrong-regime / wrong-engine belief is never silently consumed as a useful guess.

Toggles (registered in docs/ENV_FLAGS.md by C1):
    HAFISCAL_AD_BELIEF_PUBLISH  — Step-5a publish (default ON; this module is a no-op
                                  for the caller on any failure).
    HAFISCAL_AD_BELIEF_SEED     — Step-5b consume / warm-start (default OFF).
"""
from __future__ import annotations
import json
import os
import pickle
import sys
import time

# Mirror ad_cache.py's import-fallback dance: prefer the package-relative import,
# fall back to a sys.path insert when this module is imported flat (as Step-5a /
# Step-5b both do — the live run path puts Code/HA-Models AND solution_cache/ on
# sys.path rather than importing the package).
try:
    from .cache import _atomic_pickle_write, _atomic_json_write
    from .keys import gather_solve_inputs, hash_solve_inputs
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cache import _atomic_pickle_write, _atomic_json_write
    from keys import gather_solve_inputs, hash_solve_inputs


# Fixed sidecar filenames (one belief per <parametrization>/<shock_type>; no key in the
# name — Step-5b finds the belief by (parametrization, shock_type) without re-deriving
# the hash to locate the file, then soft-gates on the fingerprint stored INSIDE).
_BELIEF_PKL = "ad_belief.pkl"
_BELIEF_META = "ad_belief.meta.json"


def _belief_dir(parametrization, shock_type, create_dir=False):
    """solution_cache/<parametrization>/<shock_type>/ — same layout as ad_cache.py.

    Anchored on THIS file's directory (solution_cache/) so the path is identical
    whether Step-5a or Step-5b is the writer/reader, regardless of their cwd
    (both chdir into FromPandemicCode/; solution_cache/ is one level up)."""
    dir_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        str(parametrization), str(shock_type),
    )
    if create_dir:
        os.makedirs(dir_path, exist_ok=True)
    return dir_path


def _belief_paths(parametrization, shock_type, create_dir=False):
    d = _belief_dir(parametrization, shock_type, create_dir=create_dir)
    return os.path.join(d, _BELIEF_PKL), os.path.join(d, _BELIEF_META)


def _extract_CFunc(economy):
    """Extract economy.CFunc (list-of-lists of CRule) to two N x N float64 arrays.

    Mirrors ad_cache._save_hark_ad_result:253-261's CFunc extraction exactly so the
    on-disk numerics round-trip identically to the AD-converged cache."""
    import numpy as np
    CFunc = economy.CFunc
    N = len(CFunc)
    intercepts = np.zeros((N, N), dtype=np.float64)
    slopes = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(N):
            intercepts[i, j] = float(CFunc[i][j].intercept)
            slopes[i, j] = float(CFunc[i][j].slope)
    return intercepts, slopes


def save_ad_belief(economy, shock_type, parametrization, *, engine, mc_method):
    """Publish ``economy.CFunc`` as the AD-belief sidecar for (parametrization, shock_type).

    Args:
        economy: the AggregateDemandEconomy whose ``.CFunc`` is the converged macro
            AD belief at the call site (Step-5a, after the ``*_results_AD`` pickle save).
        shock_type: 'recession' / 'recessionCheck' / 'recessionUI' / 'recessionTaxCut'.
        parametrization: 'HS_Only' / 'Baseline' / ... (the run's Parametrization).
        engine: 'tm' (default Step-5a) or 'hark_mc' (Step-5a run with MC). Recorded in the
            meta and returned by ``load_ad_belief`` so a TM belief is never mistaken for an
            MC one; the consumer treats a cross-engine belief as an allowed (but possibly
            poor) starting guess.
        mc_method: the MC method tag for the fingerprint, or None for the TM path
            (``gather_solve_inputs`` records it either way).

    Writes ``solution_cache/<parametrization>/<shock_type>/ad_belief.pkl(+.meta.json)``.
    Returns the pkl path on success.

    NOTE: this is BEST-EFFORT at the call site — Step-5a guards the call in a try/except
    so a sidecar write NEVER aborts the reproduction. This function does its own
    fingerprint gather inside, so a gather failure here is contained to this write.
    """
    import numpy as np  # noqa: F401  (kept symmetric with ad_cache; numpy via _extract_CFunc)
    intercepts, slopes = _extract_CFunc(economy)
    N = intercepts.shape[0]

    # Fingerprint: same machinery the AD cache keys on, WITH mc_method, so a TM-engine
    # belief and an MC-engine belief for the same calibration land on distinct fingerprints
    # (gather_solve_inputs records mc_method) and the consumer's soft gate can tell them
    # apart before spending a warm start.
    inputs = gather_solve_inputs(economy, shock_type=shock_type, mc_method=mc_method)
    fp = hash_solve_inputs(inputs)

    # Composite matched-pair regime tag (PermGroFac / GIC-shave / world / method /
    # interpretation) — same one ad_cache.py stamps. Best-effort: a stripped context
    # without config.* still publishes (the consumer's gate is soft anyway).
    try:
        from _regime import regime_fingerprint
        _rfp = regime_fingerprint()
    except Exception:
        _rfp = None

    pkl_path, meta_path = _belief_paths(parametrization, shock_type, create_dir=True)
    payload = {
        "version": 1,
        "result_type": "ad_belief",
        "engine": engine,
        "fingerprint": fp,
        "regime_fingerprint": _rfp,
        "N": int(N),
        "CFunc_intercepts": intercepts,
        "CFunc_slopes": slopes,
        "saved_at": time.time(),
    }
    _atomic_pickle_write(pkl_path, payload)
    meta = {
        "version": 1,
        "result_type": "ad_belief",
        "engine": engine,
        "fingerprint": fp,
        "regime_fingerprint": _rfp,
        "shock_type": shock_type,
        "parametrization": str(parametrization),
        "mc_method": mc_method,
        "N": int(N),
        # Diagnostics-only: the inputs dict (provenance SHAs etc.) for forensics. Not
        # part of the gate (the gate compares the hash `fingerprint` above).
        "inputs": inputs,
        # Cratio-clip / AD-timing diagnostics requested by the plan (B1) for the
        # TM-vs-MC divergence forensics. Best-effort: present iff the economy exposes them.
        "cratio_clip": [0.8, 1.2] if engine == "tm" else None,
        "ad_last_iters": int(getattr(economy, "_ad_last_iters", 0)) or None,
        "ad_last_converged": getattr(economy, "_ad_last_converged", None),
        "saved_at": time.time(),
        "pkl_filename": _BELIEF_PKL,
    }
    _atomic_json_write(meta_path, meta)
    return pkl_path


def load_ad_belief(shock_type, parametrization):
    """Load the AD-belief sidecar for (parametrization, shock_type).

    Returns:
        (CFunc_list, fingerprint_hash, engine) where CFunc_list is a list-of-lists of
        reconstructed ``AggFiscalModel.CRule`` (mirrors ad_cache._load_hark_ad_result:449-456),
        fingerprint_hash is the stored calibration+engine hash, and engine is the
        ``'tm'``/``'hark_mc'`` tag.
        Returns ``None`` if no sidecar exists (best-effort: a missing belief is not an
        error — the consumer just proceeds with a flat start).

    NOTE: this does NOT gate. The consumer (welfare6_scenario.run_recession_AD) compares
    the returned ``fingerprint_hash`` to its own run's fingerprint and soft-gates there —
    a mismatch means "don't waste a warm start on this guess", never a correctness hazard.
    """
    pkl_path, _meta_path = _belief_paths(parametrization, shock_type, create_dir=False)
    if not os.path.exists(pkl_path):
        return None
    try:
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)
    except Exception:
        # Corrupt / partially-written sidecar — treat as absent (warm start is optional).
        return None
    if payload.get("version") != 1 or payload.get("result_type") != "ad_belief":
        return None

    # Reconstruct the list-of-lists of CRule (mirror _load_hark_ad_result:449-456).
    try:
        from AggFiscalModel import CRule
    except ImportError:
        # AggFiscalModel must be importable in the consume context (it always is in
        # welfare6_scenario); if not, signal "no usable belief".
        return None
    intercepts = payload["CFunc_intercepts"]
    slopes = payload["CFunc_slopes"]
    N = int(payload.get("N", intercepts.shape[0]))
    CFunc_list = [
        [CRule(float(intercepts[i, j]), float(slopes[i, j])) for j in range(N)]
        for i in range(N)
    ]
    return CFunc_list, payload.get("fingerprint"), payload.get("engine")


def load_ad_belief_meta(shock_type, parametrization):
    """Return the sidecar's ``.meta.json`` dict (forensics / tests), or None if absent."""
    _pkl_path, meta_path = _belief_paths(parametrization, shock_type, create_dir=False)
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path) as f:
            return json.load(f)
    except Exception:
        return None


def _diff_inputs(a, b, path="", out=None, cap=30):
    """Recursively collect leaf paths where two gather_solve_inputs dicts differ.

    Returns a list of human-readable 'path: stored=… vs current=…' strings, capped so a
    wholesale structural change cannot flood the log."""
    if out is None:
        out = []
    if len(out) >= cap:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if len(out) >= cap:
                break
            _diff_inputs(a.get(k, "<MISSING>"), b.get(k, "<MISSING>"),
                         f"{path}.{k}", out, cap)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: list-len {len(a)} vs {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                if len(out) >= cap:
                    break
                _diff_inputs(x, y, f"{path}[{i}]", out, cap)
    elif a != b:
        out.append(f"{path}: stored={repr(a)[:60]} vs current={repr(b)[:60]}")
    return out


def describe_fingerprint_mismatch(economy, shock_type, parametrization, mc_method):
    """Multi-line, debug-oriented description of WHY a published belief's fingerprint did
    NOT match this run's — the SPECIFIC differing solve-inputs, not just 'mismatch'.

    Loads the sidecar's stored inputs dict from ``.meta.json`` and diffs it against this
    run's ``gather_solve_inputs``. Best-effort: returns a short fallback line on ANY error
    (it must never raise into the warm-start path, which is itself best-effort). This is
    the "abundant documentation of what the failure was" the safe-degradation discipline
    requires — enough to debug a rejected warm-start without re-instrumenting by hand."""
    try:
        meta = load_ad_belief_meta(shock_type, parametrization)
        if not meta:
            return ("    [ad_belief] mismatch detail: no .meta.json beside the sidecar; "
                    "cannot localize (delete the stale .pkl and re-publish).")
        stored_inputs = meta.get("inputs") or {}
        cur_inputs = gather_solve_inputs(
            economy, shock_type=shock_type, mc_method=mc_method)
        leaves = _diff_inputs(stored_inputs, cur_inputs)
        lines = [
            f"    [ad_belief] mismatch detail for ({parametrization}, {shock_type}):",
            f"      stored fingerprint = {meta.get('fingerprint')}",
            f"      stored regime      = {meta.get('regime_fingerprint')}",
            f"      stored engine={meta.get('engine')} mc_method={meta.get('mc_method')}"
            f"  |  this-run mc_method={mc_method}",
        ]
        if not leaves:
            lines.append("      (no differing solve-input LEAF found — the gap is in a "
                         "hash-excluded field [provenance SHA] or the engine/mc_method "
                         "tag; compare stored vs this-run mc_method above)")
        else:
            lines.append(f"      differing solve-input leaves "
                         f"({len(leaves)} shown, capped):")
            lines += [f"        - {ln}" for ln in leaves]
        lines.append("      -> belief was computed under different calibration/flags; "
                     "warm-start SKIPPED, flat start used (safe, result unaffected).")
        return "\n".join(lines)
    except Exception as e:
        return (f"    [ad_belief] mismatch detail unavailable "
                f"({type(e).__name__}: {e}) — warm-start skipped, flat start used.")
