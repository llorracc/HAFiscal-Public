"""
Cache API: cache key, save, load, drop-in cached_eco_solve.

On-disk layout:
    Code/HA-Models/solution_cache/
        __init__.py, cache.py, serialize.py, keys.py   # module files
        <parametrization>/
            <shock_type>/
                <human-tag>__<short-hash>.pkl          # gitignored
                <human-tag>__<short-hash>.meta.json    # gitignored

Atomic writes: pickle -> per-writer-unique .pkl.tmp.<pid>.<uuid> -> atomic
rename (os.replace) to .pkl. Concurrent writers of the same key are safe (each
owns its own tmp, so last-writer-wins with no FileNotFoundError races, and no
partial file is ever visible at the published path — see the invariant comment
above _TMP_NAME_RE). Tmp files orphaned by writers killed mid-write are swept
best-effort by _cleanup_orphan_tmps on each successful publish.
"""
from __future__ import annotations
import json
import os
import pickle
import re
import sys
import time
import uuid

# Support both package import (from solution_cache import ...) and
# script-style execution (python solution_cache/cache.py).
try:
    from .keys import (
        gather_solve_inputs, hash_solve_inputs, parametrization_tag,
        check_provenance_match, gather_sim_inputs, hash_sim_inputs,
    )
    from .serialize import extract_eco_solution, reconstruct_eco_solution
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from keys import (
        gather_solve_inputs, hash_solve_inputs, parametrization_tag,
        check_provenance_match, gather_sim_inputs, hash_sim_inputs,
    )
    from serialize import extract_eco_solution, reconstruct_eco_solution


USE_CACHE_ENV_VAR = "HAFISCAL_USE_SOLUTION_CACHE"

# Cache root = same directory as this file (the solution_cache/ package).
# Parametrization subdirs live alongside the .py files.
_CACHE_ROOT = os.path.dirname(os.path.abspath(__file__))


def record_reuse_event(kind, outcome, byte_effect="none", **fields):
    """Best-effort passthrough to provenance.record_reuse_event (the schema-v2
    reuse ledger; plan 20260803-0900h). One sys.path-robust import point so
    every runner file can hook with `from solution_cache import
    record_reuse_event`. NEVER raises; silently no-ops if provenance is
    unavailable (minimal checkouts)."""
    try:
        _parent = os.path.dirname(_CACHE_ROOT)  # Code/HA-Models
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        from provenance import record_reuse_event as _rre
        _rre(kind, outcome, byte_effect=byte_effect, **fields)
    except Exception:
        pass


def _entry_ref(pkl_path, meta_path=None):
    """Self-contained reference fields for a cache entry (plan §1: hash8,
    saved_at, producer git sha — no chasing). Best-effort."""
    ref = {"entry": os.path.basename(str(pkl_path))}
    try:
        if meta_path and os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            if meta.get("saved_at"):
                ref["entry_saved_at"] = meta["saved_at"]
            prov = ((meta.get("inputs") or {}).get("provenance") or {})
            for k in ("hafiscal_sha", "hark_sha"):
                if prov.get(k):
                    ref[f"entry_{k}"] = prov[k]
    except Exception:
        pass
    return ref


def byte_exact_forces_fresh_solve():
    """Under --byte-identical (VERIFY level 'byte') the ~3e-7 lossy node-rebuild solution
    cache must NOT be reused: force a fresh from-scratch solve so the result is BYTE-EXACT.
    The byte-exact full-object-pickle cache is a deferred speedup; per the thread-2 spec, until
    it exists 'byte' ⟹ re-solve everything. NO-OP at the default / 'complete' levels — the cache
    behaves exactly as before. Best-effort: if verify_level cannot be imported, do NOT force
    (preserves the default behavior). Shared by cache.py + ad_cache.py.
    Spec: plans/20260622_reuse-fidelity-verification-flag-taxonomy.md.
    """
    try:
        from verify_level import verify_at_least, BYTE
    except ImportError:
        _parent = os.path.dirname(_CACHE_ROOT)  # Code/HA-Models (parent of solution_cache/)
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        try:
            from verify_level import verify_at_least, BYTE
        except Exception:
            return False
    try:
        return verify_at_least(BYTE)
    except Exception:
        return False


def _parametrization_name(eco):
    """Best-effort label for the parametrization (used in path).

    Looks at how many cohorts/edu groups exist and tries to match the
    standard HAFiscal labels. Falls back to 'custom'.
    """
    n = len(eco.agents)
    if n == 1:
        return "HS_Only"
    if n == 3:
        return "Reduced_Run"
    if n == 21:
        return "Baseline"
    if n == 7:
        return "College_Beta_Het"
    return f"custom_{n}cohorts"


def cache_path_for_key(parametrization, shock_type, human_tag, key,
                         create_dir=False):
    """Return (pkl_path, meta_path) for the given key."""
    short = key[:8]
    dir_path = os.path.join(_CACHE_ROOT, parametrization, shock_type)
    if create_dir:
        os.makedirs(dir_path, exist_ok=True)
    pkl_path = os.path.join(dir_path, f"{human_tag}__{short}.pkl")
    meta_path = os.path.join(dir_path, f"{human_tag}__{short}.meta.json")
    return pkl_path, meta_path


def compute_solve_key(eco, shock_type="recession", mc_method="hark_mc",
                       seeds=(0,), use_shuffle=False,
                       init_panel_method="newborn_pool",
                       agent_count_per_cohort=None):
    """Compute the SHA256 cache key for the given solve configuration."""
    inputs = gather_solve_inputs(
        eco, shock_type=shock_type, mc_method=mc_method,
        seeds=seeds, use_shuffle=use_shuffle,
        init_panel_method=init_panel_method,
        agent_count_per_cohort=agent_count_per_cohort,
    )
    return hash_solve_inputs(inputs), inputs


def _unique_tmp(path):
    # Per-writer unique temp name: a fixed `path + ".tmp"` is shared by every
    # concurrent process writing the same cache key, so the first os.replace
    # consumes the tmp and later writers hit FileNotFoundError on the rename.
    return "%s.tmp.%d.%s" % (path, os.getpid(), uuid.uuid4().hex)


# INVARIANT (why last-writer-wins needs no locking): the cache key is a SHA256
# over gather_solve_inputs(...), i.e. over EVERY input that affects the solve
# (guarded by test_key_completeness.py), and the solve is deterministic given
# those inputs. So all concurrent writers of the same pkl_path serialize the
# SAME solution content by construction; their payloads are interchangeable,
# differing at most in the `saved_at` wall-clock metadata (never consumed
# numerically). Whichever writer's os.replace lands last merely refreshes that
# timestamp. Each writer therefore: owns a private tmp (_unique_tmp), writes +
# fsyncs the COMPLETE payload there, publishes with ONE atomic os.replace
# (rename(2) atomically swaps the directory entry even when the destination
# exists — concurrent replacers serialize in the kernel and cannot fail each
# other), and removes its own tmp in `finally`. Readers only ever open the
# published path, so they see either no file or some writer's complete bytes,
# never a partial write. The .pkl/.meta.json pair is not transactional: a
# reader may pair one writer's pkl with another's meta — benign, since meta is
# informational (provenance warnings) and both describe the same key.
#
# The one leak mode left is a writer killed mid-write (SIGKILL/OOM/power): its
# `finally` never runs and the private tmp is orphaned. _cleanup_orphan_tmps
# below sweeps those.

# Matches "<name>.tmp" (the legacy pre-2026-06-14 shared-tmp scheme) and
# "<name>.tmp.<pid>.<32-hex-uuid>" (the current _unique_tmp scheme).
_TMP_NAME_RE = re.compile(r"\.tmp(?:\.(\d+)\.[0-9a-f]{32})?$")

# Age fallback for the orphan sweep. A legitimate in-flight write holds its tmp
# only for one pickle.dump + fsync (seconds — well under a minute even for
# Baseline-scale payloads), so 6 hours cannot false-positive a live writer. The
# fallback exists to reap (a) orphans whose embedded pid was recycled by an
# unrelated still-running process and (b) legacy no-pid ".tmp" leftovers,
# without manual intervention. The primary rule (embedded pid dead -> remove
# now) reaps ordinary crash orphans immediately.
_ORPHAN_TMP_MAX_AGE_S = 6 * 3600.0


def _pid_alive(pid):
    """True if a process with this pid exists (POSIX probe via signal 0).
    Conservative: permission errors / unknown failures count as alive. Note a
    zombie (dead but unreaped) probes as alive; its orphan waits for the age
    fallback or a later sweep."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # PermissionError (alive, other user) or exotic: keep it
    return True


def _cleanup_orphan_tmps(dir_path, max_age_s=_ORPHAN_TMP_MAX_AGE_S):
    """Best-effort sweep of orphaned atomic-write tmps in one cache directory.

    A writer killed mid-write skips its `finally` cleanup and leaves
    `<name>.tmp.<pid>.<uuid>` behind. Orphans are invisible to readers (readers
    only open published paths) but accumulate disk. Removal rules,
    conservative in both directions:
      - embedded pid no longer alive -> remove now (the ordinary crash case);
      - pid alive (including ourselves) or no pid parseable (legacy ".tmp")
        -> remove only if mtime is older than max_age_s (no legitimate write
        holds a tmp that long).
    Never raises: cleanup must never break a save. Concurrent sweepers may race
    os.remove; the loser's OSError is swallowed per-file.
    """
    try:
        names = os.listdir(dir_path)
    except OSError:
        return
    now = time.time()
    for name in names:
        m = _TMP_NAME_RE.search(name)
        if m is None:
            continue
        fp = os.path.join(dir_path, name)
        try:
            pid = int(m.group(1)) if m.group(1) else None
            if pid is not None and not _pid_alive(pid):
                os.remove(fp)
            elif now - os.stat(fp).st_mtime > max_age_s:
                os.remove(fp)
        except OSError:
            continue  # vanished / raced another sweeper / stat failed: fine


def _atomic_pickle_write(path, obj):
    """Pickle obj to path atomically (write to unique .tmp then rename).

    Safe under concurrent same-key writers — see the last-writer-wins
    INVARIANT comment above _TMP_NAME_RE. Readers never observe partial bytes
    at `path` (the payload is complete + fsync'd before the atomic os.replace).
    """
    tmp = _unique_tmp(path)
    try:
        with open(tmp, "wb") as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(tmp, path)
        except OSError:
            # With per-writer unique tmps a rename cannot lose a race (os.replace
            # atomically replaces an existing destination), so this is NOT the old
            # shared-tmp FileNotFoundError path — only an exotic filesystem failure
            # lands here. Belt-and-suspenders: if some previously published entry
            # exists at `path` it is a valid interchangeable entry (INVARIANT
            # above), so swallow and leave it; otherwise surface the failure.
            if not os.path.exists(path):
                raise
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    _cleanup_orphan_tmps(os.path.dirname(os.path.abspath(path)))


def _atomic_json_write(path, obj):
    """Write JSON to path atomically (write to unique .tmp then rename).

    Same concurrency contract as _atomic_pickle_write (INVARIANT comment
    above _TMP_NAME_RE).
    """
    tmp = _unique_tmp(path)
    try:
        with open(tmp, "w") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(tmp, path)
        except OSError:
            # See _atomic_pickle_write: not a concurrency path; swallow only if a
            # previously published (interchangeable) entry exists at `path`.
            if not os.path.exists(path):
                raise
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    _cleanup_orphan_tmps(os.path.dirname(os.path.abspath(path)))


def save_to_cache(eco, key, inputs, pkl_path, meta_path):
    """Extract solution + write pickle + meta atomically."""
    extracted = extract_eco_solution(eco)
    payload = {
        "version": 1,
        "key": key,
        "extracted": extracted,
        "saved_at": time.time(),
    }
    _atomic_pickle_write(pkl_path, payload)
    meta = {
        "version": 1,
        "key": key,
        "inputs": inputs,
        "saved_at": time.time(),
        "pkl_filename": os.path.basename(pkl_path),
    }
    _atomic_json_write(meta_path, meta)


def _warn_provenance_mismatch(meta_path, label="solution_cache"):
    """If the .meta.json next to the pkl records a different HAFiscal/HARK SHA
    or Python version than the current process, print a one-line warning.
    The cache is still used — this is informational only."""
    if not os.path.exists(meta_path):
        return
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        cached_prov = (meta.get("inputs") or {}).get("provenance") or {}
        diffs = check_provenance_match(cached_prov)
        if diffs:
            parts = ", ".join(f"{k}: {cv}→{nv}" for (k, cv, nv) in diffs)
            print(f"[{label}] provenance mismatch (using cache anyway): {parts}",
                  flush=True)
    except (OSError, ValueError, KeyError):
        pass  # Best-effort; never block loading


def load_from_cache(eco, pkl_path, meta_path=None):
    """Load cached solution and reconstruct into eco in place. Optionally
    pass the .meta.json path to enable provenance-mismatch warnings."""
    if meta_path is not None:
        _warn_provenance_mismatch(meta_path, label="solution_cache")
    with open(pkl_path, "rb") as f:
        payload = pickle.load(f)
    if payload.get("version") != 1:
        raise ValueError(
            f"cache version mismatch: got {payload.get('version')}, want 1")
    reconstruct_eco_solution(eco, payload["extracted"])


# --------------------------------------------------------------------------
# Recession-init solve cache (Lever #1, opt-in: HAFISCAL_AD_INIT_CACHE).
#
# The cold per-cohort recession EGM solve is the SAME work whether done by the
# no-AD recession scenario (welfare6_scenario.run_recession) or by the JAX-AD
# init ref sim (jax_mc_ad_multicohort._build_init_panels_via_hark_quick_sim):
# both switch to the SAME shock_type, solve at a FLAT (no-AD, Cratio=1) belief,
# under the SAME calibration -> bit-identical cFuncs. That cold 21-cohort solve
# is ~89% of the JAX-AD loop wall at Baseline (~945s); the AD iterations
# themselves are ~11%. These helpers let the no-AD recession solve POPULATE a
# per-(parametrization, shock_type) cache that the AD init CONSUMES, so the AD
# loop skips the redundant solve entirely.
#
# Tag "hark_solve_only" (the SOLVE does not depend on MC/forward-sim params),
# matching the base-solve cache convention and distinct from the AD-converged
# cache (ad_*). Gated by BOTH HAFISCAL_USE_SOLUTION_CACHE=1 AND
# HAFISCAL_AD_INIT_CACHE=1 (prototype — default OFF, so the default path is
# byte-unchanged). Both helpers are best-effort: any failure degrades to the
# normal cold solve, never to a wrong result.
_AD_INIT_CACHE_TAG = "hark_solve_only"


def _recession_init_cache_enabled():
    return (os.environ.get(USE_CACHE_ENV_VAR, "0") == "1"
            and os.environ.get("HAFISCAL_AD_INIT_CACHE", "0").lower()
            in ("1", "on", "true")
            and not byte_exact_forces_fresh_solve())


def _recession_init_paths(eco, shock_type):
    """Shared key/path computation so the SAVE site (run_recession) and the LOAD
    site (AD init) resolve to the IDENTICAL cache file. All key inputs are pinned
    to defaults here so the two call sites cannot drift apart."""
    key, inputs = compute_solve_key(
        eco, shock_type=shock_type, mc_method=_AD_INIT_CACHE_TAG,
        seeds=(0,), use_shuffle=False, init_panel_method="newborn_pool",
        agent_count_per_cohort=None)
    pname = _parametrization_name(eco)
    tag = parametrization_tag(
        eco, mc_method=_AD_INIT_CACHE_TAG, use_shuffle=False,
        agent_count_per_cohort=None, seed_offset=0)
    pkl_path, meta_path = cache_path_for_key(
        pname, shock_type, tag, key, create_dir=True)
    return key, inputs, pkl_path, meta_path


def save_recession_init_cache(eco, shock_type, verbose=True):
    """Populate the recession-init solve cache from an already-solved eco (e.g.
    the no-AD recession scenario). Returns True if a cache file exists afterward.
    Best-effort, gated, no-op when disabled."""
    if not _recession_init_cache_enabled():
        return False
    try:
        key, inputs, pkl_path, meta_path = _recession_init_paths(eco, shock_type)
        if os.path.exists(pkl_path):
            return True  # already populated by another scenario / earlier run
        save_to_cache(eco, key, inputs, pkl_path, meta_path)
        record_reuse_event("solve_cache", "saved", "none",
                           tag=_AD_INIT_CACHE_TAG, shock_type=shock_type,
                           entry=os.path.basename(pkl_path))
        if verbose:
            print(f"[recession-init-cache] SAVED {shock_type}: {pkl_path}",
                  flush=True)
        return True
    except Exception as e:  # never let cache-population break a solve
        if verbose:
            print(f"[recession-init-cache] save skipped ({e})", flush=True)
        return False


def load_recession_init_cache(eco, shock_type, verbose=True):
    """Load a cached recession-init solve into eco IN PLACE (skipping the cold
    EGM solve). Returns True on HIT. Best-effort, gated, no-op when disabled."""
    if not _recession_init_cache_enabled():
        return False
    try:
        _, _, pkl_path, meta_path = _recession_init_paths(eco, shock_type)
        if not os.path.exists(pkl_path):
            return False
        load_from_cache(eco, pkl_path, meta_path=meta_path)
        record_reuse_event("solve_cache", "hit", "tolerance",
                           tag=_AD_INIT_CACHE_TAG, shock_type=shock_type,
                           **_entry_ref(pkl_path, meta_path))
        if verbose:
            print(f"[recession-init-cache] HIT {shock_type}: skipped cold solve",
                  flush=True)
        return True
    except Exception as e:  # any load failure -> fall back to the cold solve
        if verbose:
            print(f"[recession-init-cache] load skipped ({e})", flush=True)
        return False


# --- Base-run AggCons share (R3, 2026-08-02) --------------------------------
# Every welfare6 child used to re-simulate the no-policy `base` run only to
# feed AggEco.store_baseline(...): the cross-child consumers are the AggCons
# T-vector (the AD loop's reference path + the recorded Cratio_hist), never
# the panels — those serve only the base child's own pkl. Sharing the vector
# is therefore exact. It is a SIM artifact, so it takes the SIM key
# (gather_sim_inputs: live cohort RNG seeds, shuffle/init-panel env switches,
# panel shape, EconomyMrkv_init), NOT the pinned solve-only key above — and
# because the key hashes the LIVE per-cohort RNG seeds, entries from
# different --seed-offset runs can never cross-load even if a caller plumbs
# the advisory seed_offset wrong. Gated by the master cache gate +
# HAFISCAL_BASE_SHARE (default ON; the master gate is cleared by the `hark`
# rollback engine, preserving pre-arc bytes). Best-effort: any failure falls
# back to computing the base run as before.
_BASE_AGGCONS_TAG = "base_aggcons"


def _base_share_enabled():
    return (os.environ.get(USE_CACHE_ENV_VAR, "0") == "1"
            and os.environ.get("HAFISCAL_BASE_SHARE", "on").lower()
            not in ("off", "0", "false")
            and not byte_exact_forces_fresh_solve())


def _base_aggcons_paths(eco, base_dict=None, seed_offset=0):
    """Shared key/path computation so the SAVE site (run_base) and the LOAD
    site (non-base children) resolve to the IDENTICAL cache file (the
    _recession_init_paths discipline)."""
    use_shuffle = bool(getattr(eco.agents[0], "mc_shuffle", False))
    act_T = getattr(eco, "act_T", None)
    bd = dict(base_dict or {})
    inputs = gather_sim_inputs(
        eco, shock_type="base", mc_method="hark_mc",
        seeds=(int(seed_offset),), use_shuffle=use_shuffle,
        init_panel_method="welfare6_prestate",
        agent_count_per_cohort=None,
        seed_offset=int(seed_offset), T_sim=act_T, act_T=act_T,
        economy_mrkv_init=[int(x) for x in bd.get("EconomyMrkv_init", [0])])
    # The remaining run_experiment scalars (UpdatePrb / Splurge / ...) also
    # determine the realized panel; fold every hashable base_dict entry in.
    inputs["sim"]["base_dict"] = {
        k: (list(v) if isinstance(v, (list, tuple)) else v)
        for k, v in sorted(bd.items())
        if isinstance(v, (bool, int, float, str, list, tuple))
    }
    key = hash_sim_inputs(inputs)
    pname = _parametrization_name(eco)
    pkl_path, meta_path = cache_path_for_key(
        pname, "base", _BASE_AGGCONS_TAG, key, create_dir=True)
    return key, inputs, pkl_path, meta_path


def base_aggcons_paths(eco, base_dict=None, seed_offset=0):
    """Public key/path resolver: call ONCE at a fixed eco state point and pass
    the result to BOTH load_ and save_base_aggcons_cache via ``paths=``.

    The SIM key hashes live agent params, and run_experiment mutates some of
    them (update_mrkv_array rebuilds MrkvArray/IncShkDstn objects), so a key
    computed BEFORE a base run differs from one computed AFTER it — found
    2026-08-02 when the pre-run load silently missed the post-run save.
    Returns (key, inputs, pkl_path, meta_path), or None when the share is
    disabled or path resolution fails (callers then skip load/save)."""
    if not _base_share_enabled():
        return None
    try:
        return _base_aggcons_paths(eco, base_dict=base_dict,
                                   seed_offset=seed_offset)
    except Exception:
        return None


def save_base_aggcons_cache(eco, AggCons, base_dict=None, seed_offset=0,
                            verbose=True, paths=None):
    """Publish the base run's AggCons vector for other children. Best-effort,
    gated, no-op when disabled; returns True if a cache file exists after.
    Pass ``paths`` from base_aggcons_paths (resolved pre-run) so the save and
    load sides share one key state point."""
    if not _base_share_enabled():
        return False
    try:
        key, inputs, pkl_path, meta_path = (
            paths if paths is not None else _base_aggcons_paths(
                eco, base_dict=base_dict, seed_offset=seed_offset))
        if os.path.exists(pkl_path):
            return True  # already published by another child / earlier run
        _atomic_pickle_write(pkl_path, {"key": key, "AggCons": AggCons})
        _atomic_json_write(meta_path, {"key": key, "inputs": inputs,
                                       "saved_at": time.time()})
        record_reuse_event("solve_cache", "saved", "none",
                           tag=_BASE_AGGCONS_TAG, shock_type="base",
                           entry=os.path.basename(pkl_path))
        if verbose:
            print(f"[base-share] SAVED base AggCons: {pkl_path}", flush=True)
        return True
    except Exception as e:  # never let cache publication break the base run
        if verbose:
            print(f"[base-share] save skipped ({e})", flush=True)
        return False


def load_base_aggcons_cache(eco, base_dict=None, seed_offset=0, verbose=True,
                            paths=None):
    """Return the shared base AggCons vector, or None (caller computes the
    base run as before). Best-effort, gated. Pass ``paths`` from
    base_aggcons_paths (resolved pre-run; see its docstring)."""
    if not _base_share_enabled():
        return None
    try:
        key, _, pkl_path, meta_path = (
            paths if paths is not None else _base_aggcons_paths(
                eco, base_dict=base_dict, seed_offset=seed_offset))
        if not os.path.exists(pkl_path):
            return None
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)
        if payload.get("key") != key:
            return None  # defensive: stale/foreign file at this path
        _warn_provenance_mismatch(meta_path, label="base-share")
        record_reuse_event("solve_cache", "hit", "exact",
                           tag=_BASE_AGGCONS_TAG, shock_type="base",
                           **_entry_ref(pkl_path, meta_path))
        if verbose:
            print("[base-share] HIT: base AggCons loaded; base sim skipped",
                  flush=True)
        return payload["AggCons"]
    except Exception as e:  # any load failure -> compute the base run
        if verbose:
            print(f"[base-share] load skipped ({e})", flush=True)
        return None


# --- Lossless policy-solution cache (R4b v2, 2026-08-02) --------------------
# The knot-extraction round-trip above (extract/reconstruct_eco_solution) is
# LOSSY for the production cFuncs: the PF-decay measured-Q tails attached
# above the grid top are not representable in the stored plain-knot form, so
# a reconstructed solution reverts to linear extrapolation there — measured
# 7.2e-3 worst on consumption panels when a runner INSTALLS such a solution
# without re-solving (2026-08-02: a scenario loading its OWN entry, saved
# minutes earlier from a byte-exact solve, reproduced the same 7.2e-3; the
# AD dispatch never noticed because its warm-start RE-SOLVES, rebuilding the
# tails and leaving only the documented ~1e-5 stopping noise). This kind
# therefore stores the solution objects WHOLESALE (pickle) — the persistence
# twin of store_/restore_ADsolution's in-memory copy pattern — keyed exactly
# like the solve_only entries but under a distinct tag. Best-effort + gated
# like every solve-cache consumer.
_POLICY_FULL_TAG = "policy_full"


def _policy_full_enabled():
    return (os.environ.get(USE_CACHE_ENV_VAR, "0") == "1"
            and not byte_exact_forces_fresh_solve())


def _policy_full_paths(eco, shock_type):
    key, inputs = compute_solve_key(
        eco, shock_type=shock_type, mc_method=_AD_INIT_CACHE_TAG,
        seeds=(0,), use_shuffle=False, init_panel_method="newborn_pool",
        agent_count_per_cohort=None)
    pname = _parametrization_name(eco)
    pkl_path, meta_path = cache_path_for_key(
        pname, shock_type, _POLICY_FULL_TAG, key, create_dir=True)
    return key, inputs, pkl_path, meta_path


def save_policy_solution_cache(eco, shock_type, verbose=True):
    """Publish the CURRENT solved agent solutions wholesale (lossless).
    Call right after a fresh solve under `shock_type`'s configuration."""
    if not _policy_full_enabled():
        return False
    try:
        key, inputs, pkl_path, meta_path = _policy_full_paths(eco, shock_type)
        if os.path.exists(pkl_path):
            return True
        payload = {"key": key,
                   "solutions": [a.solution for a in eco.agents]}
        _atomic_pickle_write(pkl_path, payload)
        _atomic_json_write(meta_path, {"key": key, "inputs": inputs,
                                       "saved_at": time.time()})
        record_reuse_event("solve_cache", "saved", "none",
                           tag=_POLICY_FULL_TAG, shock_type=shock_type,
                           entry=os.path.basename(pkl_path))
        if verbose:
            print(f"[policy-full] SAVED {shock_type}: {pkl_path}", flush=True)
        return True
    except Exception as e:  # never let cache publication break a solve
        if verbose:
            print(f"[policy-full] save skipped ({e})", flush=True)
        return False


def load_policy_solution_cache(eco, shock_type, verbose=True):
    """Install a wholesale-pickled policy solution into eco. Returns True on
    HIT (agents carry the exact solved objects, tails included); False lets
    the caller solve fresh. Mirrors restore_ADsolution's install pattern
    (solution assign + get_economy_data); the key covers the regime."""
    if not _policy_full_enabled():
        return False
    try:
        key, _, pkl_path, meta_path = _policy_full_paths(eco, shock_type)
        if not os.path.exists(pkl_path):
            return False
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)
        if payload.get("key") != key:
            return False
        sols = payload["solutions"]
        if len(sols) != len(eco.agents):
            return False
        _warn_provenance_mismatch(meta_path, label="policy-full")
        for agent, sol in zip(eco.agents, sols):
            agent.solution = sol
            agent.get_economy_data(eco)
        record_reuse_event("solve_cache", "hit", "exact",
                           tag=_POLICY_FULL_TAG, shock_type=shock_type,
                           **_entry_ref(pkl_path, meta_path))
        if verbose:
            print(f"[policy-full] HIT {shock_type}: installed wholesale "
                  "solution (solve skipped)", flush=True)
        return True
    except Exception as e:  # any load failure -> fresh solve
        if verbose:
            print(f"[policy-full] load skipped ({e})", flush=True)
        return False


# --- Guarded wholesale AD-converged cache (2026-08-03 owner ruling) ---------
# Stores the AD loop's converged, belief-consistent pair (belief CFunc,
# per-agent solutions) WHOLESALE — the byte-faithful `policy_full` pickle
# pattern, replacing the knot-extraction serializer whose tail loss measured
# 7.2e-3 on installed solutions (BUG-067 class). Consumers run the owner's
# ONE-ITERATION DOUBLE-CHECK on every HIT (guard at the call site in
# jax_mc_replay_ad): a fresh solve + one map step under the cached belief,
# verified against (a) a calibrated step threshold and (b) the cached
# POLICIES themselves (amendment 1 — the belief-step alone false-passes a
# corrupted payload), then the check's work is DISCARDED and the cached
# state kept — HIT outputs stay a pure function of the cached state
# (byte-identical to the producer). Decision record:
# conclusions_private/2026-08-03_ad-warmstart-dialogue-and-guarded-cache-ruling.md
_AD_FULL_TAG = "ad_full"


def _ad_full_enabled():
    v = os.environ.get("HAFISCAL_AD_FULL_CACHE", "").lower()
    if v in ("off", "0", "false"):
        return False
    if byte_exact_forces_fresh_solve():
        return False
    if os.environ.get(USE_CACHE_ENV_VAR, "0") == "1":
        return True  # default `on` under the master cache gate
    # Explicit affirmative works WITHOUT the master gate (Step-5a's entry
    # point does not set HAFISCAL_USE_SOLUTION_CACHE; arming only ad_full
    # there must not drag the other solve caches along).
    return v in ("1", "on", "true")


def _ad_full_paths(eco, shock_type, engine="jax_mc_replay_ad"):
    key, inputs = compute_solve_key(
        eco, shock_type=shock_type, mc_method=engine,
        seeds=(0,), use_shuffle=False, init_panel_method="hark_capture",
        agent_count_per_cohort=None)
    pname = _parametrization_name(eco)
    pkl_path, meta_path = cache_path_for_key(
        pname, shock_type, _AD_FULL_TAG, key, create_dir=True)
    return key, inputs, pkl_path, meta_path


def save_ad_full_cache(eco, shock_type, step_series=None, tol=None,
                       verbose=True, engine="jax_mc_replay_ad"):
    """Publish the CURRENT converged (belief, solutions) pair wholesale.
    Call after the AD loop's convergence rollback (the belief-consistent
    state store_ADsolution snapshots). Amendment 3: the producer's step
    series / final step / modulus estimate ride in the payload + meta."""
    if not _ad_full_enabled():
        return False
    try:
        key, inputs, pkl_path, meta_path = _ad_full_paths(
            eco, shock_type, engine=engine)
        if os.path.exists(pkl_path):
            return True
        ss = [float(x) for x in (step_series or [])]
        modulus = None
        if len(ss) >= 2 and ss[0] > 0:
            try:
                modulus = float((ss[-1] / ss[0]) ** (1.0 / max(1, len(ss) - 1)))
            except Exception:
                modulus = None
        guard_meta = {"iterations": len(ss), "tol": tol,
                      "step_series": ss,
                      "final_step": (ss[-1] if ss else None),
                      "modulus_est": modulus}
        _atomic_pickle_write(pkl_path, {
            "key": key, "CFunc": eco.CFunc,
            "solutions": [a.solution for a in eco.agents],
            "meta": guard_meta})
        _atomic_json_write(meta_path, {"key": key, "inputs": inputs,
                                       "saved_at": time.time(),
                                       "guard_meta": guard_meta})
        record_reuse_event("ad_full", "saved", "none", engine=engine,
                           shock_type=shock_type,
                           iterations=guard_meta.get("iterations"),
                           final_step=guard_meta.get("final_step"),
                           entry=os.path.basename(pkl_path))
        if verbose:
            print(f"[ad-full] SAVED {shock_type}: {pkl_path}", flush=True)
        return True
    except Exception as e:  # never let cache publication break a solve
        if verbose:
            print(f"[ad-full] save skipped ({e})", flush=True)
        return False


def load_ad_full_cache(eco, shock_type, verbose=True,
                       engine="jax_mc_replay_ad"):
    """Return the wholesale payload dict, or None. Does NOT install — the
    guard at the call site owns install / verify / reinstall."""
    if not _ad_full_enabled():
        return None
    try:
        key, _, pkl_path, meta_path = _ad_full_paths(
            eco, shock_type, engine=engine)
        if not os.path.exists(pkl_path):
            return None
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)
        if payload.get("key") != key:
            return None
        if len(payload.get("solutions", [])) != len(eco.agents):
            return None
        if len(payload.get("CFunc", [])) != len(eco.CFunc):
            return None
        _warn_provenance_mismatch(meta_path, label="ad-full")
        _m = payload.get("meta", {}) or {}
        record_reuse_event("ad_full", "hit_loaded", "none", engine=engine,
                           shock_type=shock_type,
                           producer_iterations=_m.get("iterations"),
                           producer_final_step=_m.get("final_step"),
                           **_entry_ref(pkl_path, meta_path))
        return payload
    except Exception as e:  # any load failure -> cold path
        if verbose:
            print(f"[ad-full] load skipped ({e})", flush=True)
        return None


def quarantine_ad_full_entry(eco, shock_type, verbose=True,
                             engine="jax_mc_replay_ad"):
    """Guard-failure disposition: move the entry aside so the cold re-solve
    republishes a fresh one. Corruption degrades to slowness, never to
    wrong numbers."""
    try:
        _, _, pkl_path, meta_path = _ad_full_paths(
            eco, shock_type, engine=engine)
        for p in (pkl_path, meta_path):
            if os.path.exists(p):
                os.replace(p, p + ".quarantined")
        record_reuse_event("ad_full", "quarantined", "none", engine=engine,
                           shock_type=shock_type)
        if verbose:
            print(f"[ad-full] entry QUARANTINED for {shock_type}", flush=True)
    except Exception:
        pass


def compare_policies_max_rel(agents, cached_solutions, m_probe=None):
    """Amendment 1: max relative deviation between the agents' CURRENT
    (fresh-solved) cFuncs and the cached solutions' cFuncs, evaluated per
    Markov state on a probe grid (m-points x the agent's Cgrid). Pure
    evaluation — mutates nothing. Threshold guidance: solver-path noise is
    ~1e-5; the known lossy-payload corruption class is 7.2e-3; 1e-3 sits
    an order away from each."""
    import numpy as _np
    if m_probe is None:
        # The known corruption class (lossy tail serialization) lives ABOVE
        # the solve-grid top (~470-590): a probe capped below it FALSE-PASSES
        # (measured in gate G2, 2026-08-03 — policy_dev 3.4e-6 while the
        # panels carried 7.2e-3). Probe through the TM dist-grid top (1300).
        m_probe = _np.geomspace(0.1, 1500.0, 60)
    worst = 0.0
    for a, sol_cached in zip(agents, cached_solutions):
        cf_fresh = a.solution[0].cFunc
        cf_cache = sol_cached[0].cFunc
        Cg = _np.asarray(getattr(a, "Cgrid", [0.8, 1.0, 1.2]), dtype=float)
        mm = _np.tile(_np.asarray(m_probe, dtype=float), Cg.size)
        cc = _np.repeat(Cg, len(m_probe))
        n = min(len(cf_fresh), len(cf_cache))
        for j in range(n):
            f = _np.asarray(cf_fresh[j](mm, cc), dtype=float)
            c = _np.asarray(cf_cache[j](mm, cc), dtype=float)
            d = float(_np.max(_np.abs(f - c) / _np.maximum(_np.abs(c), 1e-9)))
            if d > worst:
                worst = d
    return worst


def cached_eco_solve(ctx, shock_type="recession",
                      mc_method="hark_mc", seeds=(0,),
                      use_shuffle=False, init_panel_method="newborn_pool",
                      agent_count_per_cohort=None,
                      verbose=True, force_solve=False):
    """Drop-in replacement for the typical
        eco.switch_shock_type(shock_type); eco.solve()
    sequence. Checks the cache first; loads on hit, solves+saves on miss.

    Args:
        ctx: dict from build_and_solve(...) containing 'AggEco'.
        shock_type: 'recession', 'recessionCheck', etc.
        mc_method, seeds, use_shuffle, init_panel_method,
        agent_count_per_cohort: forward-sim params that affect the
            AD-converged result. Pass whatever values your downstream
            forward-sim will use.
        verbose: log cache hits/misses.
        force_solve: skip cache; always solve + save.

    Behavior:
        - Cache off (HAFISCAL_USE_SOLUTION_CACHE != '1'): just calls
          eco.switch_shock_type + eco.solve as before.
        - Cache on + hit: loads from disk, mutates eco in place.
        - Cache on + miss: solves, saves, returns.

    Returns:
        dict with 'cache_hit' (bool), 'wall' (seconds), 'pkl_path' (or None).
    """
    eco = ctx["AggEco"]
    do_switch = shock_type not in (None, "base")

    # Off (or --byte-identical forces a fresh byte-exact solve): just solve
    if os.environ.get(USE_CACHE_ENV_VAR, "0") != "1" or byte_exact_forces_fresh_solve():
        t0 = time.time()
        if do_switch:
            eco.switch_shock_type(shock_type)
        eco.solve()
        return {"cache_hit": False, "wall": time.time() - t0, "pkl_path": None}

    # On: compute key, look up, decide
    if do_switch:
        eco.switch_shock_type(shock_type)
    key, inputs = compute_solve_key(
        eco, shock_type=shock_type, mc_method=mc_method, seeds=seeds,
        use_shuffle=use_shuffle, init_panel_method=init_panel_method,
        agent_count_per_cohort=agent_count_per_cohort,
    )
    pname = _parametrization_name(eco)
    seed_offset = seeds[0] if seeds else 0
    tag = parametrization_tag(
        eco, mc_method=mc_method, use_shuffle=use_shuffle,
        agent_count_per_cohort=agent_count_per_cohort, seed_offset=seed_offset)
    pkl_path, meta_path = cache_path_for_key(
        pname, shock_type, tag, key, create_dir=True)

    if (not force_solve) and os.path.exists(pkl_path):
        if verbose:
            print(f"[solution_cache] HIT: {pkl_path}", flush=True)
        t0 = time.time()
        load_from_cache(eco, pkl_path, meta_path=meta_path)
        record_reuse_event("solve_cache", "hit", "tolerance", tag=tag,
                           shock_type=shock_type,
                           **_entry_ref(pkl_path, meta_path))
        return {"cache_hit": True, "wall": time.time() - t0,
                "pkl_path": pkl_path}

    # Miss: solve + save
    if verbose:
        print(f"[solution_cache] MISS: solving + saving to {pkl_path}",
              flush=True)
    t0 = time.time()
    eco.solve()
    wall_solve = time.time() - t0
    save_to_cache(eco, key, inputs, pkl_path, meta_path)
    record_reuse_event("solve_cache", "miss_solved_saved", "none", tag=tag,
                       shock_type=shock_type,
                       entry=os.path.basename(pkl_path))
    return {"cache_hit": False, "wall": wall_solve, "pkl_path": pkl_path}
