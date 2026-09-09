"""Shared AD-equilibrium store: the spending program publishes each recession scenario's
converged aggregate-demand equilibrium, the welfare battery consumes it and never
re-solves it.

Owner ruling (2026-08-25 ~01:00): "the welfare calculations should NOT SOLVE ANYTHING —
everything has already been solved in the spending engine; the point of the welfare
analysis is to CALCULATE the welfare consequences of the solution already obtained,
which requires MC rather than TM". The AD fixed point — the belief ``CFunc`` (aggregate
consumption ratio per macro-state transition) together with the households' policies
solved at that belief — is part of the SOLUTION, not the measurement. Until this module
Step 5b's four ``_AD`` cells recomputed it with their own MC iteration (``run_recession_AD``:
warm re-solve <-> simulate <-> belief update), a second solve of the equilibrium by a
different method, and the source of the default world's 0.7-0.8 % cross-seed scatter on
AD cells (each seed re-solving its own fixed point).

Objects. Under the TM engine (Step 5a, ``run_experiments_all_recessions_ad_tm``) Phase 1
trains ONE belief over the whole macro chain and Phase 2 only evaluates each recession
duration on it; under the MC engine (``solve_ad_recession``) the loop converges the same
kind of object. Either way the equilibrium is the pair ``store_ADsolution`` snapshots:
``(CFunc, ADelasticity, [agent.solution, ...])``. This store holds that pair per
(scenario, model), keyed exactly like the per-agent policy store — every agent's
solve-determining primitives (for THIS scenario's income process and Markov chain),
the solver environment, the solver-source hash — plus the AD inputs and the TM/AD
environment that define the fixed point. The active ``ADelasticity`` is solve STATE and is
excluded (keys.py's rule); ``demand_ADelasticity`` is the input.

Contract. ``HAFISCAL_AD_EQUILIBRIUM_SHARE=1`` (opt-in for the 2026-08-25 measurement; the
default flip is the owner's): Step 5a saves after its AD-TM block; ``run_recession_AD``
installs on a hit and SKIPS its AD loop, so the ``_AD`` cells become pure MC measurement on
the spending engine's equilibrium — in both worlds, for every seed (seed bands then carry
simulation variance only). Under ``HAFISCAL_POLICY_STORE_REQUIRE=1`` (the welfare entry
points' default) a missing equilibrium is an ERROR, like a missing policy.

Prescribed path (BUG-092, 2026-08-25). Every engine trains its belief as
``CRule(Cratio_t, slope=0)`` — a CONSTANT per macro-state transition — so ``mill_rule``'s
``CratioNext = intercept + slope*(Cratio-1)`` is the intercept whatever the consumer's panel
aggregates. An installed equilibrium therefore IS a prescribed AD path: the welfare panel's
own aggregation is inert for everything its households see (the sown ``Cratio`` and
``AggDemandFac``), which is exactly what makes the ``_AD`` cells pure measurement on the
spending program's equilibrium. ``prescribed_path`` recovers that path (the trained macro
intercepts along the recession chain) and counts nonzero slopes; ``save`` records both in
the entry's meta, ``try_load`` verifies the slopes are zero (a belief with a slope would
silently make the AD path depend on the finite-N panel again — REJECTED, an error under
``HAFISCAL_POLICY_STORE_REQUIRE=1``) and prints/records the path on every HIT.

Layout: ``<policy store dir>/equilibrium/<key[:2]>/<key>.pkl`` + ``.meta.json``.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import time
from copy import deepcopy

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_HA = os.path.dirname(_HERE)
for _p in (_HA, os.path.join(_HA, "FromPandemicCode")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from solution_cache import policy_store as _ps  # noqa: E402
from solution_cache.cache import record_reuse_event  # noqa: E402

FORMAT = 1
ENV_FLAG = "HAFISCAL_AD_EQUILIBRIUM_SHARE"
_TRUTHY = ("1", "on", "true", "yes")

# KEY = the MODEL: what both entry points share by construction — every household's
# policy-store primitives for the scenario (which already carry the solver environment,
# incl. _TM_CFUNC_OFFSET / _DIST_* / _PERM_DURING_UNEMP -- but NOT the engine-selection
# flags, ENGINE_SELECTION_ENV_VARS below), the AD
# inputs, the world axis, and the solver-source hash.
#
# NOT in the key — the PRODUCER's conventions: the AD loop's tolerance / iteration cap
# and the TM engine's discretisation. The consumer never iterates, so it has no such
# knobs of its own to match; it wants THE spending program's equilibrium, whatever that
# program converged to. First cross-entry gate (2026-08-25, m5): the sole differing leaf
# on all 4 misses was HAFISCAL_AD_CONVERGENCE_TOL — AggFiscalMAIN_reduced.py setdefaults
# it to 1e-2 (STANDARD tier), the welfare battery leaves it unset (its own loop uses
# Parameters' 1e-3 at Baseline). Those are recorded in the entry's meta as its
# `conventions`, printed on every HIT, and a re-publish with DIFFERENT conventions
# REPLACES the entry (the spending program is the authority; last producer wins).
# BUG-122 Step 0 (2026-09-06): the onset-spike ordering is a KEY leaf, not a producer convention.
# It does not touch the household problem -- the policy store rightly ignores it -- but it changes
# the period-0 distribution the experiment starts from, hence the aggregate consumption path, hence
# the AD equilibrium. Keyed here, the two arms of the measurement cannot share an entry; unkeyed,
# a welfare battery run under the fix would have silently consumed the equilibrium of a run without
# it (the failure this list exists to prevent, [[feedback_first_use_of_new_axis]]).
EQUILIBRIUM_ENV_VARS = ("HAFISCAL_WORLD", "HAFISCAL_ONSET_SPIKE_T0_EXEMPT")
PRODUCER_ENV_VARS = ("HAFISCAL_AD_CONVERGENCE_TOL", "HAFISCAL_AD_MAX_ITER",
                     "HAFISCAL_TM_AMAX", "HAFISCAL_TM_MCOUNT")
# BUG-119 option 2 (2026-09-02): ENGINE-SELECTION flags are the PRODUCER's convention, not
# the model. They legitimately differ between the two entry points -- the TM multiplier
# program (Step 5a) runs under HAFISCAL_TM_A_INDEXED=1, the MC welfare battery (Step 5b)
# without it -- and the stored equilibrium is "the spending program's" whichever engine
# produced it (a re-publish under another engine REPLACES; the consumer never runs a TM).
# Keyed on them, a bare env difference between the entry points made all four _AD welfare
# cells MISS on both 2026-09-02 cold runs (dell, ccarroll-m5). They are removed from the
# KEY here and recorded in the entry's `conventions` (producer_env) instead. Audit
# 2026-09-02: only HAFISCAL_TM_A_INDEXED is keyed today (policy_store.SOLVER_ENV_VARS);
# the three siblings sit in neither whitelist and are listed as a guard. Existing entries
# are re-keyed by `rekey_equilibria.py --any-with-leaf --drop-env-leaf ... --move`.
ENGINE_SELECTION_ENV_VARS = ("HAFISCAL_TM_A_INDEXED", "HAFISCAL_MULTIPLIER_ENGINE",
                             "HAFISCAL_SIM_METHOD", "HAFISCAL_STEP2_SIM_ENGINE")


def enabled():
    return os.environ.get(ENV_FLAG, "").strip().lower() in _TRUTHY


def _log(msg):
    print(f"[ad-equilibrium] {msg}", flush=True)


class PrescribedPathError(RuntimeError):
    """A stored belief carries a nonzero slope under strict mode: installing it would make
    the consumer panel's own aggregation feed the AD path (see the module docstring)."""


def prescribed_path(CFunc, eco):
    """Return ``(path, n_nonzero_slopes)`` for the belief ``CFunc`` — ``path`` is the AD
    path the belief PRESCRIBES along the recession chain (the trained macro intercepts
    0->3, 2j+3->2j+5, 2ne+1->1 and the 1->1 mean, recovered by tm_methods' inverse map;
    ``None`` when the economy lacks the chain geometry, e.g. a synthetic test economy),
    ``n_nonzero_slopes`` the number of belief entries whose slope is not exactly zero
    (zero for every equilibrium either engine trains; see the module docstring)."""
    n_nonzero = 0
    for row in CFunc:
        for c in row:
            slope = c[1] if isinstance(c, tuple) else getattr(c, "slope", 0.0)
            if float(slope) != 0.0:
                n_nonzero += 1
    path = None
    try:
        from tm_methods import _cratio_path_from_seed_CFunc
        import earnings_phase as _ep
        J = _ep.j_full(int(eco.num_base_MrkvStates))   # belief-block stride: 2J micro states per macro block under the phase
        ne = int(eco.num_experiment_periods)
        act_T = int(eco.act_T)
        if len(CFunc) < (2 * ne + 2) * J:
            raise ValueError("belief smaller than the recession chain")
        full = _cratio_path_from_seed_CFunc(CFunc, J, ne, act_T)
        path = [round(float(v), 6) for v in full[: ne + 2]]
    except Exception:
        path = None
    return path, n_nonzero


def _agent_inputs(agent):
    d = dict(_ps.key_inputs(agent)["agent"])
    d.pop("ADelasticity", None)          # solve STATE (0 pre-AD, demand value post-AD)
    return d


def _equilibrium_env_value(k):
    """The world axis as a KEY leaf: unset and 'default' are the same world (config
    catalog), so they must produce the same key — the first tripwire smoke (2026-08-25)
    missed all four Baseline entries on exactly this leaf (consumer '' vs stored 'default')."""
    v = os.environ.get(k, "").strip()
    if k == "HAFISCAL_WORLD":
        return v or "default"
    if k == "HAFISCAL_ONSET_SPIKE_T0_EXEMPT":
        # normalise the spellings so "0", "off" and unset are one world, not three keys
        return "1" if v.lower() in ("1", "on", "true", "yes") else "0"
    return v


def key_inputs(eco, shock_type):
    env = _ps._solver_env_dict()
    for k in ENGINE_SELECTION_ENV_VARS:   # BUG-119 option 2: producer's convention, not a key leaf
        env.pop(k, None)
    env.update({k: _equilibrium_env_value(k) for k in EQUILIBRIUM_ENV_VARS})
    return {
        "equilibrium_format": FORMAT,
        "shock_type": str(shock_type),
        "agents": [_agent_inputs(a) for a in eco.agents],
        "ad": {
            "demand_ADelasticity": float(getattr(eco, "demand_ADelasticity", np.nan)),
            "num_experiment_periods": int(getattr(eco, "num_experiment_periods", 0)),
            "num_macro_states": int(getattr(eco, "num_macro_states", 0)),
            "n_macro_cfunc": int(len(getattr(eco, "CFunc", []) or [])),
        },
        "env": env,
        "solver_source": _ps.solver_source_hash(),
    }


def key_for(eco, shock_type):
    inputs = key_inputs(eco, shock_type)
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), inputs


def _paths(key):
    d = os.path.join(_ps.store_dir(), "equilibrium", key[:2])
    return d, os.path.join(d, f"{key}.pkl"), os.path.join(d, f"{key}.meta.json")


def _conventions(producer, extra):
    """The producer's conventions: its AD/TM environment plus the effective values it
    passes in ``extra`` (tolerance, iteration cap, TM discretisation) and its site/engine."""
    return {
        "producer": dict(producer or {}),
        "producer_env": {k: os.environ.get(k, "")
                         for k in PRODUCER_ENV_VARS + ENGINE_SELECTION_ENV_VARS},
        "extra": {k: v for k, v in dict(extra or {}).items()},
    }


def _conventions_summary(conv):
    ex = conv.get("extra") or {}
    pe = conv.get("producer_env") or {}
    tol = ex.get("convergence_tol", pe.get("HAFISCAL_AD_CONVERGENCE_TOL") or "?")
    it = ex.get("num_max_iterations", pe.get("HAFISCAL_AD_MAX_ITER") or "?")
    qm = ex.get("tm_q_method")
    tma = pe.get("HAFISCAL_TM_A_INDEXED")
    return (f"AD tol={tol}, max iters={it}, engine={conv.get('producer', {}).get('engine', '?')}"
            + (f", Q-construction={qm}" if qm else ", Q-construction=pre-BUG-093 (unrecorded)")
            + (f", TM_A_INDEXED={tma}" if tma not in (None, "") else ""))


def save(eco, shock_type, producer=None, extra=None, verbose=True):
    """Publish ``eco``'s CURRENT equilibrium for ``shock_type``: its belief ``CFunc``, the
    AD-on elasticity, and every agent's solution AS THEY STAND (the caller ensures the
    agents are solved at this belief — Step 5a calls this right after its AD-TM block).
    An existing entry with the SAME conventions is kept (idempotent re-publish); one
    with DIFFERENT conventions is REPLACED — the spending program is the authority."""
    if not enabled():
        return False
    try:
        key, inputs = key_for(eco, shock_type)
        d, pkl_path, meta_path = _paths(key)
        conv = _conventions(producer, extra)
        if os.path.exists(pkl_path):
            old = {}
            try:
                with open(meta_path) as f:
                    old = json.load(f).get("conventions") or {}
            except Exception:
                pass
            if old == conv:
                if verbose:
                    _log(f"KEPT {shock_type}: entry exists with the same conventions "
                         f"({_conventions_summary(conv)}) [{key[:16]}]")
                return True
            if verbose:
                _log(f"REPLACING {shock_type}: stored conventions ({_conventions_summary(old)}) "
                     f"!= this producer's ({_conventions_summary(conv)}) [{key[:16]}]")
        os.makedirs(d, exist_ok=True)
        ad_el = float(getattr(eco, "demand_ADelasticity", getattr(eco, "ADelasticity", 0.0)))
        payload = {
            "format": FORMAT, "key": key, "shock_type": str(shock_type),
            "CFunc": deepcopy(eco.CFunc), "ADelasticity": ad_el,
            "solutions": [deepcopy(a.solution) for a in eco.agents],
            "extra": dict(extra or {}),
        }
        path, n_nonzero = prescribed_path(eco.CFunc, eco)
        _ps._atomic_pickle_write(pkl_path, payload)
        root = _ps._hafiscal_root()
        _ps._atomic_json_write(meta_path, {
            "key": key, "inputs": inputs, "saved_at": time.time(),
            "producer": producer or {}, "conventions": conv,
            "host": socket.gethostname(), "pid": os.getpid(),
            "hafiscal_sha": _ps._git_sha(root) if root else "unknown",
            "n_agents": len(eco.agents), "n_cfunc": len(eco.CFunc),
            "active_ADelasticity_at_save": float(getattr(eco, "ADelasticity", np.nan)),
            "extra": dict(extra or {}),
            # the AD path this belief prescribes + its slope count (BUG-092)
            "prescribed_path": path, "n_nonzero_slopes": int(n_nonzero),
        })
        record_reuse_event("ad_equilibrium", "saved", "none", key=key[:16],
                           shock_type=str(shock_type), entry=os.path.basename(pkl_path),
                           conventions=_conventions_summary(conv),
                           n_nonzero_slopes=int(n_nonzero))
        if verbose:
            _log(f"SAVED {shock_type}: {len(eco.agents)} agents, belief {len(eco.CFunc)}x{len(eco.CFunc)}, "
                 f"ADelasticity={ad_el}, {_conventions_summary(conv)} [{key[:16]}]")
            if n_nonzero:
                _log(f"  WARNING: {n_nonzero} belief entries have a nonzero slope — consumers "
                     f"will REJECT this entry (the AD path would depend on their panel)")
            if path is not None:
                _log(f"  prescribed AD path (macro Cratio along the recession chain): {path}")
        return True
    except Exception as e:
        if verbose:
            _log(f"save skipped ({type(e).__name__}: {str(e)[:120]})")
        return False


def _flatten(x, prefix=""):
    """Flatten key inputs to {leaf-path: scalar}; canonicalized arrays / distributions
    (keys.py's ``{"_array": …}`` / ``{"_dstn": …}`` records) collapse to one leaf each."""
    out = {}
    if isinstance(x, dict):
        if x.get("_array") is True:
            out[prefix] = f"array{x.get('shape')}:{str(x.get('sha256'))[:12]}"
        elif x.get("_dstn") is True:
            pm = x.get("pmv") or {}
            out[prefix] = (f"dstn(pmv {pm.get('shape')}:{str(pm.get('sha256'))[:12]}, "
                           f"atoms {[str(a.get('sha256'))[:8] for a in x.get('atoms', [])]})")
        else:
            for k, v in x.items():
                out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(x, (list, tuple)):
        for i, v in enumerate(x):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = x
    return out


def _group_of(path):
    """'agents[0].MrkvArray' for 'agents[0].MrkvArray.foo[3]'; 'env.HAFISCAL_X' for env."""
    parts = path.split(".")
    return ".".join(parts[:2]) if len(parts) > 1 else path


def explain_miss(inputs, max_groups=12):
    """Name what differs between THIS consumer's key inputs and the stored equilibrium
    entries for the same scenario (the nearest one — fewest differing leaves — since a
    key is all-or-nothing and says only 'no'). Returns a text block for the MISS
    message; also drops ``inputs`` under ``<store>/equilibrium/_misses/`` so the two
    sides can be diffed offline. Found necessary on the first cross-entry gate
    (2026-08-25, m5): 5a published 4 entries, the welfare battery missed all 4, and the
    bare key could not say which of the ~60 leaves per agent disagreed."""
    eq_dir = os.path.join(_ps.store_dir(), "equilibrium")
    shock_type = inputs.get("shock_type")
    try:
        import glob as _glob
        metas = sorted(_glob.glob(os.path.join(eq_dir, "??", "*.meta.json")))
    except Exception:
        metas = []
    mine = _flatten(inputs)
    best = None
    for meta_path in metas:
        try:
            with open(meta_path) as f:
                m = json.load(f)
        except Exception:
            continue
        theirs_inputs = m.get("inputs") or {}
        if theirs_inputs.get("shock_type") != shock_type:
            continue
        theirs = _flatten(theirs_inputs)
        diffs = []
        for p in sorted(set(mine) | set(theirs)):
            a, b = mine.get(p, "<absent>"), theirs.get(p, "<absent>")
            if a != b:
                diffs.append((p, a, b))
        if best is None or len(diffs) < len(best[1]):
            best = (meta_path, diffs, m)
    try:
        miss_dir = os.path.join(eq_dir, "_misses")
        os.makedirs(miss_dir, exist_ok=True)
        _ps._atomic_json_write(
            os.path.join(miss_dir, f"{shock_type}_{socket.gethostname()}_{os.getpid()}.miss.json"),
            {"inputs": inputs, "host": socket.gethostname(), "pid": os.getpid(),
             "at": time.time(), "nearest": best[0] if best else None})
    except Exception:
        pass
    if best is None:
        return (f"no stored equilibrium for scenario {shock_type!r} under {eq_dir} "
                f"({len(metas)} entries for other scenarios)")
    meta_path, diffs, m = best
    groups = {}
    for p, a, b in diffs:
        g = groups.setdefault(_group_of(p), [0, None])
        g[0] += 1
        if g[1] is None:
            g[1] = (p, a, b)
    lines = [f"nearest stored entry {os.path.basename(meta_path)[:16]} "
             f"(producer {m.get('producer')}, saved by {m.get('host')}) differs in "
             f"{len(diffs)} leaves across {len(groups)} fields:"]
    for g, (n, (p, a, b)) in list(groups.items())[:max_groups]:
        lines.append(f"    {g}: {n} leaf{'s' if n != 1 else ''} differ, e.g. {p}: "
                     f"consumer={str(a)[:60]!s} | stored={str(b)[:60]!s}")
    if len(groups) > max_groups:
        lines.append(f"    ... {len(groups) - max_groups} more fields")
    return "\n".join(lines)


def try_load(eco, shock_type, verbose=True):
    """Return the equilibrium payload for ``eco`` in ``shock_type``, or None (miss /
    structural mismatch). Does not install."""
    if not enabled():
        return None
    try:
        key, inputs = key_for(eco, shock_type)
        _, pkl_path, meta_path = _paths(key)
        if not os.path.exists(pkl_path):
            record_reuse_event("ad_equilibrium", "miss", "none", key=key[:16],
                               shock_type=str(shock_type))
            if verbose:
                _log(f"MISS {shock_type} [{key[:16]}]: {explain_miss(inputs)}")
            return None
        _ps.ensure_fti_importable()
        import pickle
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)
        if payload.get("key") != key or payload.get("format") != FORMAT:
            _log(f"REJECTED {shock_type}: key/format mismatch in payload -> not installed")
            return None
        if len(payload.get("solutions", [])) != len(eco.agents):
            _log(f"REJECTED {shock_type}: {len(payload.get('solutions', []))} solutions for "
                 f"{len(eco.agents)} agents -> not installed")
            return None
        if len(payload.get("CFunc", [])) != len(eco.CFunc):
            _log(f"REJECTED {shock_type}: belief {len(payload.get('CFunc', []))} vs eco "
                 f"{len(eco.CFunc)} -> not installed")
            return None
        path, n_nonzero = prescribed_path(payload["CFunc"], eco)
        if n_nonzero:
            why = (f"{shock_type}: the stored belief has {n_nonzero} nonzero slope(s) — installing "
                   f"it would let THIS panel's aggregation feed the AD path (CratioNext = intercept "
                   f"+ slope*(Cratio-1)), so the _AD cells would no longer be pure measurement on "
                   f"the spending program's equilibrium (BUG-092) [{key[:16]}]")
            record_reuse_event("ad_equilibrium", "rejected_nonzero_slope", "none", key=key[:16],
                               shock_type=str(shock_type), n_nonzero_slopes=int(n_nonzero))
            if _ps.require_hits():
                raise PrescribedPathError(f"[ad-equilibrium] REJECTED {why}")
            _log(f"REJECTED {why} -> not installed")
            return None
        producer, conv, saved_by = {}, {}, "?"
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            producer = meta.get("producer") or {}
            conv = meta.get("conventions") or {}
            saved_by = f"{meta.get('host', '?')} @ {meta.get('hafiscal_sha', '?')}"
        except Exception:
            pass
        payload["_meta"] = {"producer": producer, "conventions": conv, "saved_by": saved_by,
                            "summary": _conventions_summary(conv),
                            "prescribed_path": path, "n_nonzero_slopes": 0}
        record_reuse_event("ad_equilibrium", "hit", "exact", key=key[:16],
                           shock_type=str(shock_type), entry=os.path.basename(pkl_path),
                           producer=producer, conventions=_conventions_summary(conv),
                           n_nonzero_slopes=0, prescribed_path=path)
        if verbose:
            _log(f"HIT {shock_type}: installing the spending program's equilibrium "
                 f"(producer {producer}, {_conventions_summary(conv)}, saved by {saved_by}) "
                 f"[{key[:16]}]")
            if path is not None:
                _log(f"  prescribed AD path (every slope 0 — this panel's aggregation is inert): {path}")
        return payload
    except PrescribedPathError:
        raise
    except Exception as e:
        if verbose:
            _log(f"load skipped ({type(e).__name__}: {str(e)[:120]}) -> not installed")
        return None


def install(eco, shock_type, payload):
    """Install the equilibrium into ``eco`` exactly as the AD loop would have left it:
    belief + AD-on elasticity + the agents' solutions, then snapshot it under
    ``shock_type`` so the caller's unchanged ``restore_ADsolution(name)`` works."""
    eco.CFunc = deepcopy(payload["CFunc"])
    eco.ADelasticity = float(payload["ADelasticity"])
    for agent, sol in zip(eco.agents, payload["solutions"]):
        agent.solution = deepcopy(sol)
        agent.CFunc = eco.CFunc
        agent.get_economy_data(eco)
    eco.store_ADsolution(shock_type)
    return True


def raise_on_miss(eco, shock_type, site):
    try:
        key, inputs = key_for(eco, shock_type)
        why = explain_miss(inputs)
    except Exception as e:
        key, why = "?", f"(key inputs unavailable: {type(e).__name__}: {str(e)[:80]})"
    raise RuntimeError(
        f"[ad-equilibrium] MISS at {site} for scenario {shock_type!r} (key {key[:16]}) with "
        f"{_ps.REQUIRE_FLAG}=1 and {ENV_FLAG}=1: this entry point must not solve the AD "
        f"equilibrium. Either the spending program (AggFiscalMAIN_reduced.py --baseline, "
        f"with {ENV_FLAG}=1) has not run for this model/world on this machine, or the two "
        f"entry points build different scenarios. {why}\n"
        f"{ENV_FLAG}=0 re-enables the welfare battery's own AD iteration.")
