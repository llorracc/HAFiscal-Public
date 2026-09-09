"""Shared solved-policy store: solve each household problem ONCE, everywhere.

Plan: plans_local/20260824-1530h_shared-solved-policy-store_plan.md (owner charge
2026-08-24: "the most urgent thing on the agenda"). Background: the multiplier entry
(Step 5a) and the welfare battery (Step 5b) are separate programs that each solved
every household type's cold consumption rule from scratch — 5a on every run, every
seed and in each of its four forked shock workers; 5b in its own per-cell economies
(BUG-089 showed they even used different solvers). The published QE code solved once.

Unit of storage = ONE agent's converged AD-off policy (a HARK ``ConsumerSolution``),
pickled wholesale (the lossless ``policy_full`` pattern; never the knot-extraction
serializer, BUG-067). Key = the agent's solve-determining primitives (the same
``keys._agent_params_dict`` the AD-solution cache uses: DiscFac, CRRA, Rfree, LivPrb,
PermGroFac, grids, Cgrid, IncShkDstn, MrkvArray, ...) + the solver environment (the
existing numerical whitelist PLUS the solver/tail flags it lacked) + a content hash of
the solver source (so a solver edit invalidates entries without pinning commit SHAs).

HIT guard: one backward sweep of the agent's OWN solver applied to the loaded policy
must reproduce it to ``HAFISCAL_POLICY_STORE_VERIFY_TOL`` (relative, default 1e-3 —
coarse on purpose: it catches a wrong calibration vintage, a wrong structure or a
corrupted file; sub-1e-3 drift is excluded by the KEY, because the fast solver's and
EGM's fixed points legitimately differ by ~2e-4 across formulations). The check's
output is discarded; the loaded object is installed as-is (byte purity).

Scope: cold, AD-off solves (``from_solution is None`` and ``ADFunc`` identity) — the
AD-phase warm re-solves depend on the belief CFunc and stay as they are; the
AD-converged pair keeps its own guarded cache (``ad_full``).

Flags: ``HAFISCAL_POLICY_STORE`` (default ON since the 2026-08-24 phase-3 flip;
``0``/``off``/``false``/``no`` opts out), ``HAFISCAL_POLICY_STORE_VERIFY`` (default on),
``HAFISCAL_POLICY_STORE_VERIFY_TOL`` (default 1e-3), ``HAFISCAL_POLICY_STORE_DIR``
(the store keeps a compact ``_index.jsonl`` -- one line per entry: beta, S, primitive/env
digests, solver hash -- appended at every save and rebuilt by ``python -m
solution_cache.policy_store reindex``; a ``REQUIRE=1`` miss reads it to say WHICH cause
applies: solver changed / flags differ / primitives differ / nothing stored — ``diagnose_miss``)
(default ``~/.cache/hafiscal/policy_store`` — per user/machine, shared across checkouts).
The byte-exact certification switch (``cache.byte_exact_forces_fresh_solve``) forces
misses, as it does for every other cache layer. Every HIT / MISS / SAVED / REJECTED is
a ``policy_store`` event in the provenance REUSE ledger.

Primitives FINGERPRINT gate (A2, 2026-08-28; ``solution_cache/fingerprint.py``): the
same ``key_inputs`` doubles as the pre-launch check that a run builds the household
problems it is meant to -- ``python -m solution_cache.policy_store fingerprint
--parametrization Baseline --reference ref.json`` freezes every agent's key inputs in
every scenario (solve-free construction) plus the non-key TM dist-grid top;
``... --check ref.json`` diffs the live build leaf by leaf (``explain_miss`` style) and
exits 1 on any difference. Run it before a reproduction arm (memory rule
``feedback_reproduce_original_model_verify_primitives``).
"""
import hashlib
import inspect
import json
import os
import pickle
import socket
import sys
import time

import numpy as np

_HERE = os.path.abspath(os.path.dirname(__file__))
_HA_MODELS = os.path.dirname(_HERE)
if _HA_MODELS not in sys.path:
    sys.path.insert(0, _HA_MODELS)

from solution_cache.cache import (  # noqa: E402
    _atomic_json_write, _atomic_pickle_write, _cleanup_orphan_tmps,
    byte_exact_forces_fresh_solve, record_reuse_event,
)
from solution_cache.keys import (  # noqa: E402
    _agent_params_dict, _canonicalize_value, _env_dict, _git_sha, _hafiscal_root,
)

# 2 (2026-08-24): entries carry the accelerated solve's Newton-2D interior
# (``agent._newton2d_cInterior``) so a HIT warm-starts the AD phase exactly as the cold
# solve would have — the xubuntark welfare gate showed the four AD cells 6e-14…3e-12 off
# on hits (non-AD cells exact) because that payload was missing. Part of the key.
STORE_FORMAT = 2
# Solve-side agent attributes that downstream code reads and a HIT must reproduce.
# Enumerated from `getattr(agent, "_…")` readers: solver_accel.py:488 (Newton-2D warm
# start) and welfare6_scenario.py:165 (ships it to the AD-phase re-solves).
WARM_PAYLOAD_ATTRS = ("_newton2d_cInterior",)
ENV_FLAG = "HAFISCAL_POLICY_STORE"
VERIFY_FLAG = "HAFISCAL_POLICY_STORE_VERIFY"
VERIFY_TOL_FLAG = "HAFISCAL_POLICY_STORE_VERIFY_TOL"
DIR_FLAG = "HAFISCAL_POLICY_STORE_DIR"

# Solver / tail flags that change the SOLUTION at fixed primitives and were absent
# from keys._HAFISCAL_NUMERICAL_ENV_VARS (the AD-cache whitelist, which covers the
# primitives-affecting flags). Unset = "" so an unset flag keys like its default.
SOLVER_ENV_VARS = (
    "HAFISCAL_STEP5_ATI", "HAFISCAL_STEP5_ATI_MIN_DISCFAC",
    "HAFISCAL_PF_DECAY_EXTRAP", "HAFISCAL_PF_DECAY_Q", "HAFISCAL_PF_DECAY_DRIFT_TOL",
    "HAFISCAL_PF_DECAY_AMAX_MULT", "HAFISCAL_AXTRA_COUNT", "HAFISCAL_SOLVE_AMAX",
    "HAFISCAL_ENDOGENOUS_GRID", "HAFISCAL_SLICE_INTERP", "HAFISCAL_SOLVE_ACCEL",
    "HAFISCAL_USE_JAX_SOLVER", "HAFISCAL_STEP2_NAMG", "HAFISCAL_TM_A_INDEXED",
    "HAFISCAL_PLVL_GROWS_DURING_UNEMP", "HAFISCAL_PERM_DURING_UNEMP",
)

_SOLVER_SOURCE_HASH = {"value": None}
_TRUTHY = ("1", "on", "true")


def enabled():
    """Default ON (phase-3 flip, 2026-08-24, after the multiplier-entry gate on m5 and
    the welfare-battery gate on xubuntark both showed store OFF / ON-cold / ON-warm
    byte-identical). ``HAFISCAL_POLICY_STORE=0|off|false|no`` opts out; the byte-exact
    certification switch forces misses, as for every cache layer."""
    if os.environ.get(ENV_FLAG, "").strip().lower() in ("0", "off", "false", "no"):
        return False
    return not byte_exact_forces_fresh_solve()


def verify_enabled():
    return os.environ.get(VERIFY_FLAG, "1").strip().lower() in _TRUTHY


def ensure_fti_importable():
    """Best-effort: make ``hark_fti`` importable in THIS process. ATI-solved policies
    pickle ``hark_fti`` classes, and a process that never routed ATI itself — a parent
    collecting fork/spawn-pool results, or any process loading a store entry — must
    still be able to unpickle them. Found the hard way (2026-08-24, m5, as-corrected
    world): the multiplier entry's fork pool deadlocked because the parent could not
    unpickle a worker's ATI result (``ModuleNotFoundError: No module named 'hark_fti'``);
    the default world survived only because the accelerator happens to resolve the FTI
    path in the parent. Never raises; returns whether ``hark_fti`` now imports."""
    try:
        import hark_fti  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import _hark_fti_path
        _hark_fti_path.ensure_hark_fti()
        import hark_fti  # noqa: F401
        return True
    except Exception:
        return False


ensure_fti_importable()   # at import: every store user may unpickle ATI entries

REQUIRE_FLAG = "HAFISCAL_POLICY_STORE_REQUIRE"


def require_hits():
    """``HAFISCAL_POLICY_STORE_REQUIRE=1``: a store-eligible cold solve that MISSES is an
    ERROR, not a fallback solve. Set by the welfare entry points (owner ruling
    2026-08-24: "the welfare battery should not be allowed to solve at all") — every
    welfare-side miss so far was a construction discrepancy between the two entry
    points (BUG-090: unemployed income process; BUG-091: tax-cut duration), which a
    silent re-solve hides and a loud miss exposes. The multiplier program (the
    producer) does not set it."""
    return enabled() and os.environ.get(REQUIRE_FLAG, "").strip().lower() in _TRUTHY


MISS_SCAN_MAX_ENTRIES = 20000
MISS_SCAN_BUDGET_S = 30.0
INDEX_NAME = "_index.jsonl"


def _index_path():
    return os.path.join(store_dir(), INDEX_NAME)


def _index_row(key, inputs, saved_at, host, producer):
    """One compact line per entry: what the miss diagnosis needs without opening the meta
    (a meta carries the full primitives -- an S=252 agent's is 11 MB; dell's 32,596 metas
    total 1.6 GB, so a diagnosis that opened them all would take minutes)."""
    agent = inputs.get("agent", {})
    beta, S = _agent_who(agent)
    return {"key": key, "beta": beta, "S": S, "agent_digest": _digest(agent),
            "env_digest": _digest(inputs.get("env", {})),
            "solver_source": str(inputs.get("solver_source", "")), "saved_at": saved_at,
            "host": host, "engine": (producer or {}).get("engine", "?")}


def _index_append(row):
    """Append-only; one short line, O_APPEND-atomic on a local filesystem, so the
    fork/spawn workers that save concurrently never interleave."""
    try:
        line = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        fd = os.open(_index_path(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except Exception as e:  # noqa: BLE001 -- the index is a convenience; the entry is already saved
        _log(f"index append skipped ({type(e).__name__}: {str(e)[:60]})")


def _index_rows():
    """Yield the index's rows (bad lines skipped); nothing if there is no index yet."""
    try:
        with open(_index_path()) as f:
            for line in f:
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except FileNotFoundError:
        return


def reindex(verbose=True):
    """Rebuild ``_index.jsonl`` from every ``.meta.json`` in the store (one-time, after
    upgrading to the indexed store, or after a suspected index/meta drift). Atomic replace."""
    root = store_dir()
    tmp = _index_path() + f".tmp.{os.getpid()}"
    n = 0
    t0 = time.time()
    with open(tmp, "w") as out:
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                if not fn.endswith(".meta.json"):
                    continue
                try:
                    m = json.load(open(os.path.join(dp, fn)))
                    row = _index_row(m.get("key") or fn[:-10], m.get("inputs") or {}, m.get("saved_at", 0),
                                     m.get("host", "?"), m.get("producer") or {})
                except Exception as e:  # noqa: BLE001
                    if verbose:
                        _log(f"reindex: skipped {fn} ({type(e).__name__})")
                    continue
                out.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
                n += 1
                if verbose and n % 5000 == 0:
                    _log(f"reindex: {n} entries, {time.time() - t0:.0f}s")
    os.replace(tmp, _index_path())
    if verbose:
        _log(f"reindex: {n} entries -> {_index_path()} in {time.time() - t0:.0f}s")
    return n



def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _agent_who(agent_dict):
    """(beta, S) of a stored/queried agent dict, for the coarse match; None where unreadable."""
    try:
        beta = float(np.asarray(agent_dict.get("DiscFac")).reshape(-1)[0])
    except Exception:
        beta = None
    S = _mrkv_state_count(agent_dict.get("MrkvArray"))
    return beta, S


def _mrkv_state_count(mk):
    """State count from a canonicalized MrkvArray. The canonical form of an array is the
    digest dict ``{'_array': True, 'shape': [S, S], ...}`` (see ``_canonicalize_value``),
    wrapped in the time-varying list; older/hand-made metas may hold nested lists.
    None where unreadable."""
    try:
        while isinstance(mk, list) and len(mk) == 1:
            mk = mk[0]
        if isinstance(mk, dict) and mk.get("_array"):
            return int(mk["shape"][0])
        if isinstance(mk, list) and mk and isinstance(mk[0], list):
            return len(mk)
        return None
    except Exception:
        return None


def _differing_keys(a, b):
    keys = sorted(set(a) | set(b))
    return [k for k in keys if a.get(k) != b.get(k)]


def diagnose_miss(inputs, max_entries=MISS_SCAN_MAX_ENTRIES, budget_s=MISS_SCAN_BUDGET_S):
    """Near-miss diagnosis for a store MISS (owner 2026-09-09: "shouldn't m5 notice what is
    missing automatically?"). A bare miss under ``REQUIRE=1`` has four different causes with
    four different remedies, and the store's own metadata tells them apart: every entry's
    ``.meta.json`` records the key's three components separately (``agent`` primitives,
    solver ``env``, ``solver_source``). Scans the per-machine store (bounded by
    ``max_entries`` and ``budget_s``; the error path only) and returns ``(code, text)``:

      solver_changed     -- an entry with the SAME primitives and env exists under a different
                            solver-source hash: the solver code changed since it was stored, the
                            entries are stale BY DESIGN (the solver is part of the key so that a
                            solver fix invalidates what the old solver produced -- BUG-088's
                            spurious fixed point would pass the one-sweep re-verification);
                            remedy: re-run Step 5a, which re-warms the store on the new solver.
      env_differs        -- same primitives, different solver ENVIRONMENT (which flags differ is
                            listed): the two entry points run under different flags
                            (BUG-119 class); remedy: align the flags.
      primitives_differ  -- entries for this (beta, S) exist but the household PRIMITIVES differ
                            (which keys is listed): the two entry points build different
                            problems (BUG-090/BUG-091 class); remedy: compare the metas.
      no_entry           -- nothing stored for this (beta, S) on this machine: Step 5a has not
                            solved it here; remedy: run Step 5a first.
      unavailable        -- the scan itself failed (the text says why).

    Never raises. The text is one paragraph meant to be appended to the miss message.
    """
    try:
        agent_now = inputs.get("agent", {})
        env_now = inputs.get("env", {})
        src_now = str(inputs.get("solver_source", ""))
        a_dig, e_dig = _digest(agent_now), _digest(env_now)
        beta_now, S_now = _agent_who(agent_now)
        t0 = time.time()
        n_seen = n_scanned = n_indexed = 0
        truncated = False
        solver_hits, env_hits, prim_hits = [], [], []
        # The index (one line per entry: beta, S, digests, solver hash) answers the solver-
        # changed / env-differs / no-entry questions without opening a meta; primitives-differ
        # needs the meta's key list, so those candidates are opened (few: same beta and S).
        indexed_keys = set()
        prim_candidates = []
        for r in _index_rows():
            n_indexed += 1
            indexed_keys.add(r.get("key"))
            beta_m, S_m = r.get("beta"), r.get("S")
            coarse = (beta_now is not None and beta_m is not None and abs(float(beta_m) - beta_now) <= 1e-12
                      and S_m == S_now)
            same_agent = r.get("agent_digest") == a_dig
            if not (coarse or same_agent):
                continue
            stamp = (f"stored {time.strftime('%Y-%m-%d %H:%M', time.localtime(r.get('saved_at') or 0))} "
                     f"on {r.get('host', '?')} by {r.get('engine', '?')}")
            if same_agent and r.get("env_digest") == e_dig:
                if str(r.get("solver_source", "")) != src_now:
                    solver_hits.append((str(r.get("solver_source", ""))[:12], stamp))
            elif same_agent:
                prim_candidates.append((r.get("key"), stamp, "env"))
            else:
                prim_candidates.append((r.get("key"), stamp, "prim"))
        for key, stamp, kind in prim_candidates[:200]:
            try:
                m = json.load(open(_paths(key)[2]))
            except Exception:
                continue
            ins = m.get("inputs") or {}
            if kind == "env":
                en = ins.get("env", {})
                env_hits.append((_differing_keys(en, env_now), en, stamp))
            else:
                prim_hits.append((_differing_keys(ins.get("agent", {}), agent_now), stamp))
        # entries saved before the index existed (or by an older store): the bounded meta scan
        for dp, _dn, fns in os.walk(store_dir()):
            for fn in fns:
                if not fn.endswith(".meta.json") or fn[:-10] in indexed_keys:
                    continue
                n_seen += 1
                if n_scanned >= max_entries or (time.time() - t0) > budget_s:
                    truncated = True
                    continue
                try:
                    m = json.load(open(os.path.join(dp, fn)))
                except Exception:
                    continue
                n_scanned += 1
                ins = m.get("inputs") or {}
                ag, en = ins.get("agent", {}), ins.get("env", {})
                beta_m, S_m = _agent_who(ag)
                coarse = (beta_now is not None and beta_m is not None and abs(beta_m - beta_now) <= 1e-12
                          and S_m == S_now)
                if not coarse and _digest(ag) != a_dig:
                    continue
                same_agent = _digest(ag) == a_dig
                stamp = (f"stored {time.strftime('%Y-%m-%d %H:%M', time.localtime(m.get('saved_at', 0)))} "
                         f"on {m.get('host', '?')} by {(m.get('producer') or {}).get('engine', '?')}")
                if same_agent and _digest(en) == e_dig:
                    if str(ins.get("solver_source", "")) != src_now:
                        solver_hits.append((str(ins.get("solver_source", ""))[:12], stamp))
                elif same_agent:
                    env_hits.append((_differing_keys(en, env_now), en, stamp))
                else:
                    prim_hits.append((_differing_keys(ag, agent_now), stamp))
        scanned = (f"index {n_indexed} entries; un-indexed metas scanned {n_scanned} of {n_seen}"
                   + (" (scan truncated -- run `python -m solution_cache.policy_store reindex`)" if truncated else ""))
        who = f"beta={beta_now:.6f} S={S_now}" if beta_now is not None else "this household"
        if solver_hits:
            src, stamp = solver_hits[0]
            return ("solver_changed",
                    f"DIAGNOSIS: the SOLVER SOURCE changed since this household's policy was stored "
                    f"({stamp}; solver {src}… then, {src_now[:12]}… now; {len(solver_hits)} such entr"
                    f"{'y' if len(solver_hits) == 1 else 'ies'}). Stale by design -- the solver is part of the key so a "
                    f"solver fix invalidates what the old solver produced. Remedy: re-run Step 5a "
                    f"(AggFiscalMAIN_reduced.py --baseline) on this machine, which re-warms the store on the new "
                    f"solver; then this entry point hits. [{scanned}]")
        if env_hits:
            keys, en, stamp = env_hits[0]
            shown = "; ".join(f"{k}: stored={str(en.get(k, ''))[:24]!r} now={str(env_now.get(k, ''))[:24]!r}"
                              for k in keys[:6]) + (" …" if len(keys) > 6 else "")
            return ("env_differs",
                    f"DIAGNOSIS: a policy for this exact household exists but under a DIFFERENT solver "
                    f"environment ({stamp}): {shown}. The two entry points run under different flags "
                    f"(BUG-119 class). Remedy: align the flags between Step 5a and this entry point "
                    f"(or re-run Step 5a under these). [{scanned}]")
        if prim_hits:
            keys, stamp = prim_hits[0]
            return ("primitives_differ",
                    f"DIAGNOSIS: {len(prim_hits)} entr{'y' if len(prim_hits) == 1 else 'ies'} for {who} exist "
                    f"({stamp}) but the household PRIMITIVES differ: {', '.join(keys[:8])}"
                    f"{' …' if len(keys) > 8 else ''}. The two entry points build DIFFERENT problems "
                    f"(BUG-090/BUG-091 class). Remedy: compare the key inputs in the store metas. [{scanned}]")
        return ("no_entry",
                f"DIAGNOSIS: no entry for {who} on this machine ({socket.gethostname()}): Step 5a has not "
                f"solved it here. Remedy: run Step 5a first (AggFiscalMAIN_reduced.py --baseline). [{scanned}]")
    except Exception as e:  # noqa: BLE001 -- the diagnosis must never mask the miss itself
        return ("unavailable", f"DIAGNOSIS unavailable ({type(e).__name__}: {str(e)[:80]})")


def raise_on_miss(agent, site):
    """Called by a hook after ``try_load`` returned None for a store-eligible agent
    when ``require_hits()`` is on."""
    try:
        key, inputs = key_for(agent)
        who = f"beta={float(np.asarray(agent.DiscFac).reshape(-1)[0]):.6f} S={_state_count(agent)}"
    except Exception:
        key, who, inputs = "?", "?", None
    code, why = diagnose_miss(inputs) if inputs is not None else ("unavailable", "DIAGNOSIS unavailable (no key)")
    _log(f"MISS at {site} for {who} [{key[:16]}] -> {code}: {why}")
    raise RuntimeError(
        f"[policy-store] MISS at {site} for {who} (key {key[:16]}) with "
        f"{REQUIRE_FLAG}=1: this entry point must not solve. {why} "
        f"(Generic causes: the multiplier program has not yet solved this household on this "
        f"machine, or the two entry points build DIFFERENT household problems — BUG-090/BUG-091 "
        f"class.) {REQUIRE_FLAG}=0 re-enables the fallback solve for a deliberate diagnostic run.")


def verify_tol():
    try:
        return float(os.environ.get(VERIFY_TOL_FLAG, "1e-3"))
    except ValueError:
        return 1e-3


def store_dir():
    """``HAFISCAL_POLICY_STORE_DIR`` if set; else the per-USER cache dir
    ``$XDG_CACHE_HOME/hafiscal/policy_store`` (``~/.cache/hafiscal/policy_store``) —
    per machine, shared by every checkout and worktree on it (the key carries the
    solver-source hash, so trees running different solver code never collide), never
    transported between machines (owner default, 2026-08-24)."""
    d = os.environ.get(DIR_FLAG, "").strip()
    if d:
        return d
    base = os.environ.get("XDG_CACHE_HOME", "").strip() or os.path.expanduser("~/.cache")
    return os.path.join(base, "hafiscal", "policy_store")


def _log(msg):
    print(f"[policy-store] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Solver-source hash: WHICH code produced a policy. Function sources for the
# HAFiscal solver entry points, whole files for the tail/grid helpers, the FTI
# solver family and HARK's interpolation/core. Cached per process.
# ---------------------------------------------------------------------------
def _module_file_bytes(modname):
    try:
        mod = __import__(modname, fromlist=["_"])
        path = getattr(mod, "__file__", None)
        if not path:
            return f"{modname}:no-file".encode()
        if path.endswith(".pyc"):
            path = path[:-1]
        with open(path, "rb") as f:
            return f.read()
    except Exception as e:  # unavailable optional component keys as such
        return f"{modname}:unavailable:{type(e).__name__}".encode()


def solver_source_hash():
    if _SOLVER_SOURCE_HASH["value"] is not None:
        return _SOLVER_SOURCE_HASH["value"]
    h = hashlib.sha256()
    h.update(f"store-format={STORE_FORMAT}".encode())
    # HAFiscal solver entry points (function bodies, so unrelated edits to the
    # 3.5k-line module do not invalidate the store).
    try:
        import AggFiscalModel as _afm
        for obj in (_afm.solve_agg_cons_markov_alt, _afm.compute_pf_decay_limits,
                    _afm.AggFiscalType.update_solution_terminal,
                    _afm.AggregateDemandEconomy._try_solve_ati_markov,
                    _afm.AggregateDemandEconomy._ati_pf_line_violation,
                    _afm.AggregateDemandEconomy._try_solve_namg_base,
                    _afm.maybe_accel_solution):
            h.update(inspect.getsource(obj).encode())
    except Exception as e:
        h.update(f"AggFiscalModel:unavailable:{type(e).__name__}".encode())
    for modname in ("local_q_tail", "powerlaw_decay", "grid_sizing", "mom_bounds",
                    "solver_accel", "HARK.interpolation", "HARK.core",
                    "HARK.ConsumptionSaving.ConsIndShockModel"):
        h.update(_module_file_bytes(modname))
    # The FTI solver family (only reachable when routed; key it if importable).
    try:
        import _hark_fti_path  # noqa: F401
    except Exception:
        pass
    for modname in ("hark_fti.consumed_ati_markov", "hark_fti.consumed_block_core",
                    "hark_fti.consumed_a_newton", "hark_fti.powerlaw_tail"):
        h.update(_module_file_bytes(modname))
    _SOLVER_SOURCE_HASH["value"] = h.hexdigest()
    return _SOLVER_SOURCE_HASH["value"]


# ---------------------------------------------------------------------------
# Key
# ---------------------------------------------------------------------------
# Flags in the AD-cache whitelist that do NOT affect a cold AD-off solve: they are
# process-protocol switches, and keying on them splits entries between entry points
# that solve the identical problem (the welfare battery sets NEWTON2D_WARM_PAYLOAD,
# the multiplier entry does not — found by the 2026-08-24 cross-entry measurement).
STORE_KEY_INERT = ("HAFISCAL_NEWTON2D_WARM_PAYLOAD",)


def _solver_env_dict():
    env = _env_dict()
    env.update({k: os.environ.get(k, "") for k in SOLVER_ENV_VARS})
    for k in STORE_KEY_INERT:
        env.pop(k, None)
    return env


def key_inputs(agent):
    """Everything that determines ONE agent's cold AD-off policy."""
    params = _agent_params_dict(agent)
    for attr in ("num_experiment_periods", "num_macro_states", "ADelasticity",
                 "AgentCount"):
        # AgentCount is simulation-side; recorded for forensics, EXCLUDED below.
        if hasattr(agent, attr):
            params[attr] = _canonicalize_value(getattr(agent, attr))
    excluded = {"AgentCount"}
    hashable_params = {k: v for k, v in params.items() if k not in excluded}
    # Earnings phase (2026-08-28): the primitives (MrkvArray, PermGroFac, IncShkDstn) already separate a
    # phase-on agent from its phase-off twin; the hazard leaf is added ONLY when the phase is on, so every
    # existing (phase-off) key -- and the whole per-machine store -- is untouched.
    try:
        import earnings_phase as _ep
        if _ep.enabled():
            hashable_params["earnings_phase_hazard"] = float(_ep.hazard())
    except ImportError:
        pass
    return {
        "store_format": STORE_FORMAT,
        "agent": hashable_params,
        "env": _solver_env_dict(),
        "solver_source": solver_source_hash(),
    }


def key_for(agent):
    inputs = key_inputs(agent)
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), inputs


def _paths(key):
    d = os.path.join(store_dir(), key[:2])
    return d, os.path.join(d, f"{key}.pkl"), os.path.join(d, f"{key}.meta.json")


# ---------------------------------------------------------------------------
# Qualification + guard
# ---------------------------------------------------------------------------
def is_cold_ad_off(agent, from_solution):
    """Cold (no warm-start seed) AND aggregate-demand-off: the base regime, or an
    ADFunc that is the identity on recession states too — the same test the ATI
    router applies (AggFiscalModel._try_solve_ati_markov)."""
    if from_solution is not None:
        return False
    try:
        if int(getattr(agent, "num_macro_states", 0)) == 1:
            return True
        ADFunc = getattr(agent, "ADFunc", None)
        if ADFunc is None:
            return False
        return float(ADFunc(0.9, True)) == 1.0 and float(ADFunc(1.1, True)) == 1.0
    except Exception:
        return False


def _state_count(agent):
    return int(np.asarray(agent.MrkvArray[0]).shape[0])


def _snapshot(agent, sol, n_m=40):
    """Per-state c(m, C) on a fixed m-grid at the middle C node — the comparison
    surface for the fixed-point check (independent of HARK's distance metric)."""
    S = _state_count(agent)
    top = float(np.max(np.asarray(agent.aXtraGrid, dtype=float)))
    m = np.geomspace(0.25, max(top, 1.0), n_m)
    Cg = np.asarray(getattr(agent, "Cgrid", [1.0]), dtype=float).reshape(-1)
    C = np.full_like(m, float(Cg[len(Cg) // 2]))
    return np.array([np.asarray(sol.cFunc[j](m, C), dtype=float) for j in range(S)])


def verify_fixed_point(agent, sol):
    """Apply ONE backward sweep of the agent's own solver to ``sol``; a genuine
    converged policy for THIS agent's problem reproduces itself to tolerance.
    Requires ``agent.pre_solve()`` to have run (time-varying params installed).
    Returns (ok, rel_err, reason)."""
    try:
        from HARK.core import solve_one_cycle
        if len(sol.cFunc) != _state_count(agent):
            return False, np.inf, "state count mismatch"
        swept = solve_one_cycle(agent, sol, None)[0]
        a = _snapshot(agent, sol)
        b = _snapshot(agent, swept)
        rel = float(np.max(np.abs(a - b) / np.maximum(np.abs(a), 1e-3)))
        tol = verify_tol()
        return rel <= tol, rel, ("ok" if rel <= tol else
                                 f"one-sweep relative move {rel:.2e} > {tol:g}")
    except Exception as e:  # the guard itself raising = not a fixed point here
        return False, np.inf, f"sweep raised {type(e).__name__}: {str(e)[:120]}"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def try_load(agent, eco=None, verbose=True):
    """Install a stored policy into ``agent`` (``agent.solution = [sol]``, plus
    ``get_economy_data(eco)`` when an economy is given). Returns the solution on
    HIT, None on MISS/REJECT. Never raises. The caller runs ``post_solve()``."""
    if not enabled():
        return None
    try:
        key, _ = key_for(agent)
        _, pkl_path, meta_path = _paths(key)
        who = f"beta={float(np.asarray(agent.DiscFac).reshape(-1)[0]):.6f} S={_state_count(agent)}"
        if not os.path.exists(pkl_path):
            record_reuse_event("policy_store", "miss", "none", key=key[:16], who=who)
            return None
        ensure_fti_importable()   # ATI entries carry hark_fti classes
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)
        if payload.get("key") != key or payload.get("store_format") != STORE_FORMAT:
            record_reuse_event("policy_store", "rejected", "none", key=key[:16],
                               who=who, reason="key/format mismatch in payload")
            if verbose:
                _log(f"REJECTED {who}: payload key/format mismatch -> solve")
            return None
        sol = payload["solution"]
        if verify_enabled():
            ok, rel, reason = verify_fixed_point(agent, sol)
            if not ok:
                record_reuse_event("policy_store", "rejected", "none", key=key[:16],
                                   who=who, reason=reason, rel_err=float(rel))
                if verbose:
                    _log(f"REJECTED {who}: {reason} -> solve (entry {os.path.basename(pkl_path)})")
                return None
        else:
            rel = None
        agent.solution = [sol]
        # Reproduce the producer's solve-side agent state too (format 2): the
        # accelerated solver's Newton-2D interior is the AD phase's warm start.
        for attr, v in (payload.get("warm_payload") or {}).items():
            setattr(agent, attr, np.array(v, copy=True) if isinstance(v, np.ndarray) else v)
        if eco is not None:
            agent.get_economy_data(eco)
        record_reuse_event("policy_store", "hit", "exact", key=key[:16], who=who,
                           entry=os.path.basename(pkl_path),
                           verified=bool(verify_enabled()),
                           rel_err=(None if rel is None else float(rel)))
        if verbose:
            _log(f"HIT {who}: installed stored policy"
                 + (f" (one-sweep move {rel:.1e})" if rel is not None else "")
                 + f" [{os.path.basename(pkl_path)[:16]}]")
        return sol
    except Exception as e:  # never let the store break a solve
        if verbose:
            _log(f"load skipped ({type(e).__name__}: {str(e)[:100]}) -> solve")
        return None


def save(agent, sol=None, verbose=True, producer=None):
    """Publish ``agent``'s cold AD-off policy (``agent.solution[0]`` unless given).
    First writer wins; a later writer verifies the entry exists and skips."""
    if not enabled():
        return False
    try:
        sol = sol if sol is not None else agent.solution[0]
        key, inputs = key_for(agent)
        d, pkl_path, meta_path = _paths(key)
        who = f"beta={float(np.asarray(agent.DiscFac).reshape(-1)[0]):.6f} S={_state_count(agent)}"
        if os.path.exists(pkl_path):
            return True
        os.makedirs(d, exist_ok=True)
        _cleanup_orphan_tmps(d)
        warm = {}
        for attr in WARM_PAYLOAD_ATTRS:
            v = getattr(agent, attr, None)
            if v is not None:
                warm[attr] = np.array(v, copy=True) if isinstance(v, np.ndarray) else v
        _atomic_pickle_write(pkl_path, {"key": key, "store_format": STORE_FORMAT,
                                        "solution": sol, "warm_payload": warm})
        root = _hafiscal_root()
        _atomic_json_write(meta_path, {
            "key": key, "inputs": inputs, "saved_at": time.time(),
            "producer": producer or {}, "host": socket.gethostname(),
            "pid": os.getpid(), "hafiscal_sha": _git_sha(root) if root else "unknown",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "solution_classes": sorted({type(f).__name__ for f in sol.cFunc}),
        })
        _index_append(_index_row(key, inputs, time.time(), socket.gethostname(), producer))
        record_reuse_event("policy_store", "saved", "none", key=key[:16], who=who,
                           entry=os.path.basename(pkl_path))
        if verbose:
            _log(f"SAVED {who} [{key[:16]}]")
        return True
    except Exception as e:
        if verbose:
            _log(f"save skipped ({type(e).__name__}: {str(e)[:100]})")
        return False


# ---------------------------------------------------------------------------
# Maintenance CLI: python -m solution_cache.policy_store ls | prune --older-than DAYS
#                                                        | fingerprint <fingerprint.py args>
# ---------------------------------------------------------------------------
def _iter_entries():
    root = store_dir()
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            if fn.endswith(".pkl"):
                yield os.path.join(dp, fn)


def main(argv=None):
    import argparse
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "fingerprint":
        # the primitives gate keeps its own argparse (and --help); dispatched before ours
        from solution_cache import fingerprint as _fp
        return _fp.main(argv[1:])
    p = argparse.ArgumentParser(description="shared solved-policy store maintenance")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ls", help="list entries (age, size, producer host, beta/S)")
    sub.add_parser("reindex", help="rebuild _index.jsonl from the metas (one-time after upgrading; feeds the miss diagnosis)")
    pr = sub.add_parser("prune", help="delete entries older than --older-than days")
    pr.add_argument("--older-than", type=float, default=30.0)
    pr.add_argument("--dry-run", action="store_true")
    sub.add_parser("fingerprint", add_help=False,
                   help="primitives fingerprint gate on key_inputs: --parametrization P "
                        "--reference OUT.json | --check REF.json (solution_cache/fingerprint.py)")
    a = p.parse_args(argv)
    if a.cmd == "reindex":
        reindex(verbose=True)
        return 0
    now = time.time()
    n = tot = 0
    for pkl in sorted(_iter_entries()):
        meta = pkl[:-4] + ".meta.json"
        try:
            m = json.load(open(meta))
        except Exception:
            m = {}
        age_d = (now - m.get("saved_at", os.path.getmtime(pkl))) / 86400.0
        size = os.path.getsize(pkl)
        agent = (m.get("inputs") or {}).get("agent") or {}
        S = _mrkv_state_count(agent.get("MrkvArray"))   # was "?" for every entry: the canonical form is a digest dict
        who = f"beta={float(agent.get('DiscFac', float('nan'))):.6f} S={S if S is not None else '?'}"
        n += 1
        tot += size
        if a.cmd == "ls":
            print(f"{os.path.basename(pkl)[:16]}  {age_d:6.1f} d  {size/1e6:6.1f} MB  "
                  f"{m.get('host','?'):12s} {who}")
        elif age_d > a.older_than:
            print(f"{'would delete' if a.dry_run else 'deleting'} {os.path.basename(pkl)[:16]} ({age_d:.1f} d)")
            if not a.dry_run:
                for f in (pkl, meta):
                    try:
                        os.remove(f)
                    except OSError:
                        pass
    print(f"{n} entries, {tot/1e6:.0f} MB under {store_dir()}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["fingerprint"]:
        from solution_cache import fingerprint as _fp
        _fp.reexec_with_thread_caps_if_needed()   # numpy is loaded already; pin BLAS first
    sys.exit(main())
