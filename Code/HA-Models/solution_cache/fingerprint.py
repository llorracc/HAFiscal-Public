"""Primitives FINGERPRINT gate: compare the household problems a launch WOULD build
against a frozen reference, before any compute is spent.

Plan item A2 (plans/20260828-1130h_infrastructure-lessons-implementation_plan.md), as
reshaped by the prior-art review (conclusions_private/2026-08-28_prior-art-review_of_
proposed_improvements.md): "KEEP the gate, RESHAPE onto ``policy_store.key_inputs`` +
``explain_miss`` (add only ``dist_aGrid_max``)". Rule enforced (memory
``feedback_reproduce_original_model_verify_primitives``, 2026-08-27): before running a
"reproduce the original model" arm, construct the agents under the intended env and
compare the LOADED primitives -- the beta atoms after the solve-time clip, the income
process in every scenario, the solve grid, the solver regime -- not the calibration
file's numbers. Three relaunches (~5.5 h of discarded compute) came from primitives that
differed while the calibration files matched: the atom clip, the solve grid, the age cap.

NO second hashing scheme. One (agent, scenario) fingerprint IS ``policy_store.key_inputs``
-- the per-agent primitives (``keys._agent_params_dict``: DiscFac, CRRA, Rfree, LivPrb,
PermGroFac, grids, Cgrid, IncShkDstn, MrkvArray, T_age, Splurge, ...) plus the solver
environment and the solver-source hash -- computed in the SAME agent state the economy
solve keys on (``switch_shock_type`` for the scenario, then ``pre_solve``). The
comparison is leaf-by-leaf in ``equilibrium_store.explain_miss``'s style (field, leaf,
live vs reference). The ONE addition is the TM distribution-grid top ``dist_aGrid_max``
(``HAFISCAL_TM_AMAX`` / ``HAFISCAL_DIST_TOP_MODE``, resolved as ``tm_methods.
build_tm_agg_fiscal_a`` resolves it), which is NOT a store-key leaf and lives in a
separate ``extra`` block; ``key_inputs`` itself is untouched (changing the store key
would invalidate every stored solution on every machine).

Construction is SOLVE-FREE: ``welfare6_scenario.build_and_solve`` is the one place both
entry points' construction is mirrored (Simulate.py's block is inlined in a 1500-line
function), and its first call after construction is ``solution_cache.cached_eco_solve``
-- intercepted here, as ``fti_diagnostics/_poc_mm5_aggfiscal_parity.py`` does, so the
economy is captured and the solve never starts. A Baseline reference builds in a few
seconds (21 agents x 5 scenarios). The multiplier entry's import-time setdefaults that
are key leaves (``HAFISCAL_STEP5_ATI=1``, ``solver_accel.apply_newton2d_defaults``) are
applied first, so the env block is the one a launch would key on (explicit env wins).

Usage (from ``Code/HA-Models``; also ``python -m solution_cache.policy_store fingerprint ...``)::

    python -m solution_cache.fingerprint --parametrization Baseline --reference ref.json[.gz]
    python -m solution_cache.fingerprint --parametrization Baseline --check ref.json[.gz]
        [--scenarios base,recession,...] [--no-include-dist-top] [--verbose]

``--check`` prints a one-screen summary and exits 1 on ANY difference in the compared
blocks (agents' primitives per scenario, the solver env, the extra block), 0 when
identical, 2 on a build/usage error. The solver-source hash and the per-(agent,
scenario) store keys are reported (how many of the reference's keys this machine's
store already holds), not gated: a solver EDIT changes every key without changing a
primitive, and the gate is about the model, not the cache. A reference stores each
(agent, scenario)'s key plus its inputs in the leaf form the comparison uses (~3 MB
plain / ~0.2 MB as ``.json.gz`` at Baseline); ``--reference`` never touches the store.
The CLI pins the numeric-thread caps (re-exec once; see ``_THREAD_VARS``) so a build on
a loaded box costs one core for ~10 s, not every core for minutes.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import re
import socket
import sys
import time

# Numeric-thread caps (as AggFiscalMAIN_reduced.py and welfare6_scenario.py set them):
# this venv's OpenBLAS spawns a full-width pool the instant numpy loads, and the
# fingerprint's many tiny per-state operations then spin-wait on every core -- measured
# 2026-08-28: a Baseline reference took 237 s wall at 2242 % CPU (53 CPU-min user + 43
# sys) on a loaded box, and 9 s single-threaded. `python -m solution_cache.fingerprint`
# imports the package __init__ (numpy) BEFORE this module runs, so the caps cannot take
# effect in this process: the CLI guards call ``reexec_with_thread_caps_if_needed`` and
# re-exec ONCE with the caps in the environment (library callers never re-exec).
# setdefault: an explicit override wins; ``_PINNED_HERE`` = the vars this module set.
_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS")
_PINNED_HERE = tuple(v for v in _THREAD_VARS if v not in os.environ)
for _thr_var in _THREAD_VARS:
    os.environ.setdefault(_thr_var, "1")
_REEXEC_MARK = "FINGERPRINT_THREADS_PINNED"


def reexec_with_thread_caps_if_needed():
    """CLI entry only (the two ``__main__`` guards): if this module had to set thread caps
    after numpy was already imported, replace the process with one that starts capped.
    Guarded twice (the caps are inherited, so the child sets none; plus a marker)."""
    if not _PINNED_HERE or os.environ.get(_REEXEC_MARK):
        return
    os.environ[_REEXEC_MARK] = "1"
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, [sys.executable, sys.argv[0], *sys.argv[1:]])


import numpy as np  # noqa: E402

_HERE = os.path.abspath(os.path.dirname(__file__))
_HA_MODELS = os.path.dirname(_HERE)
_FPC = os.path.join(_HA_MODELS, "FromPandemicCode")
for _p in (_HA_MODELS, _FPC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from solution_cache import policy_store as _ps  # noqa: E402
from solution_cache.equilibrium_store import _flatten  # noqa: E402

FORMAT = 1
SCENARIOS = ("base", "recession", "recessionUI", "recessionTaxCut", "recessionCheck")
# tm_methods.build_tm_agg_fiscal_a: with HAFISCAL_TM_AMAX unset (global mode) the
# distribution-grid top falls back to the legacy 500.0 (EstimParameters setdefaults
# the flag to the catalog value, 1300, in both worlds -- so 500 means "no world applied").
LEGACY_DIST_TOP = 500.0
# Readable, per-agent projection of the same objects the key hashes (arrays and
# distributions collapse to hashes in the leaf diff; these name the numbers a human
# checks first -- the memory rule's list: betas, income process, grid, age cap).
_SUMMARY_SCALARS = ("CRRA", "T_age", "Splurge", "IncUnemp", "IncUnempNoBenefits",
                    "TaxCutIncFactor", "UnempPrb", "Urate_normal", "Urate_recession",
                    "UBspell_normal", "UBspell_extended", "Uspell_normal", "Uspell_recession")


class _StopAfterConstruction(Exception):
    """Raised inside the intercepted ``cached_eco_solve`` to unwind ``build_and_solve``."""


def _log(msg):
    print(f"[fingerprint] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Construction (solve-free) and resolution of the non-key extra
# ---------------------------------------------------------------------------
def apply_entry_point_defaults(env=None):
    """The multiplier entry's import-time setdefaults that are STORE-KEY leaves
    (AggFiscalMAIN_reduced.py: ``HAFISCAL_STEP5_ATI=1``; ``solver_accel.
    apply_newton2d_defaults('step5a')`` -> SOLVE_ACCEL / NEWTON2D_KERNEL in the default
    world). The welfare entry applies the same at its own import / ``main``; its extra
    WARM_PAYLOAD default is key-inert (``policy_store.STORE_KEY_INERT``). Its AD-tolerance
    and pool-size setdefaults are not key leaves and are not applied. Returns the
    leaves this call SET (i.e. that were unset); explicit env always wins."""
    e = os.environ if env is None else env
    before = dict(e)
    e.setdefault("HAFISCAL_STEP5_ATI", "1")
    try:
        from solver_accel import apply_newton2d_defaults
        apply_newton2d_defaults("step5a", env=e)
    except Exception:  # the accelerator glue is optional: the leaves then stay unset, as they
        pass           # would for an entry point that could not import it either
    return {k: v for k, v in e.items() if k not in before}


def build_economy_no_solve(parametrization, quiet=True):
    """The economy exactly as ``welfare6_scenario.build_and_solve`` constructs it, captured
    at its first ``cached_eco_solve`` call (the base solve never starts). Returns
    ``(eco, build_log)``. ``sys.argv`` is blanked around the build (Parameters.py parses
    it) and the cwd is restored afterwards (welfare6_scenario chdirs at import)."""
    saved_argv, saved_cwd = sys.argv[:], os.getcwd()
    sys.argv = [sys.argv[0]]
    buf = io.StringIO()
    captured = {}
    try:
        with contextlib.redirect_stdout(buf if quiet else sys.stdout):
            import solution_cache
            import welfare6_scenario as ws
            orig = solution_cache.cached_eco_solve

            def _capture_and_abort(ctx, *a, **kw):
                captured["eco"] = ctx["AggEco"]
                raise _StopAfterConstruction()

            solution_cache.cached_eco_solve = _capture_and_abort
            try:
                ws.build_and_solve(parametrization)
            except _StopAfterConstruction:
                pass
            finally:
                solution_cache.cached_eco_solve = orig
    finally:
        sys.argv = saved_argv
        os.chdir(saved_cwd)
    if "eco" not in captured:
        raise RuntimeError(
            f"build_and_solve({parametrization!r}) returned without calling "
            "solution_cache.cached_eco_solve -- the construction path changed; move the "
            "capture point (fingerprint.build_economy_no_solve).")
    return captured["eco"], buf.getvalue()


def resolve_dist_top():
    """The TM distribution-grid top a build would use, resolved as ``tm_methods.
    build_tm_agg_fiscal_a`` resolves it when no explicit ``dist_aGrid_max`` is passed:
    ``HAFISCAL_DIST_TOP_MODE`` 'global' (default) -> ``HAFISCAL_TM_AMAX`` else the legacy
    500; 'per_atom' -> each agent's own wealth-weighted ergodic quantile, which needs a
    SOLVED agent and is therefore recorded as unresolved here."""
    mode = os.environ.get("HAFISCAL_DIST_TOP_MODE", "global").strip() or "global"
    amax = os.environ.get("HAFISCAL_TM_AMAX", "").strip()
    if mode == "per_atom":
        return {"dist_aGrid_max": "per_atom", "dist_top_mode": mode,
                "source": "adaptive_grid_tm.per_atom_dist_aGrid_max (needs a solve; unresolved here)"}
    if mode != "global":
        return {"dist_aGrid_max": None, "dist_top_mode": mode,
                "source": f"invalid HAFISCAL_DIST_TOP_MODE={mode!r} (build_tm_agg_fiscal_a raises)"}
    if amax:
        try:
            return {"dist_aGrid_max": float(amax), "dist_top_mode": mode, "source": "HAFISCAL_TM_AMAX"}
        except ValueError:
            return {"dist_aGrid_max": None, "dist_top_mode": mode,
                    "source": f"invalid HAFISCAL_TM_AMAX={amax!r}"}
    return {"dist_aGrid_max": LEGACY_DIST_TOP, "dist_top_mode": mode,
            "source": "legacy default (HAFISCAL_TM_AMAX unset)"}


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------
def _scalar(v):
    try:
        a = np.asarray(v)
        if a.size == 0:
            return None
        x = a.reshape(-1)[0]
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating, float)):
            return float(x)
        if isinstance(x, (np.bool_, bool)):
            return bool(x)
        return x.item() if hasattr(x, "item") else x
    except Exception:
        return None


def _summary(agent):
    """Human-readable projection of the objects the key hashes (see _SUMMARY_SCALARS)."""
    g = np.asarray(agent.aXtraGrid, dtype=float).reshape(-1)
    out = {
        "educ": _scalar(getattr(agent, "EducType", None)),
        "DiscFac": _scalar(agent.DiscFac),
        "Rfree": _scalar(agent.Rfree),
        "LivPrb": _scalar(agent.LivPrb),
        "PermGroFac_employed": _scalar(agent.PermGroFac),
        "aXtraMin": float(g.min()), "aXtraMax": float(g.max()), "aXtraCount": int(g.size),
    }
    for k in _SUMMARY_SCALARS:
        v = getattr(agent, k, None)
        out[k] = None if v is None else _scalar(v)
    return out


def _agent_record(agent, index):
    return {"index": int(index), "educ": _scalar(getattr(agent, "EducType", None)),
            "beta": _scalar(agent.DiscFac), "summary": _summary(agent)}


def _provenance(parametrization, entry_defaults, argv):
    root = _ps._hafiscal_root()
    try:
        import HARK
        hark = getattr(HARK, "__version__", "?")
    except Exception:
        hark = "?"
    try:
        from config import effective_config
        cfg = json.loads(json.dumps(effective_config(), default=str))
    except Exception as e:
        cfg = {"unavailable": f"{type(e).__name__}: {str(e)[:80]}"}
    return {
        "parametrization": parametrization,
        "host": socket.gethostname(), "pid": os.getpid(),
        "hafiscal_sha": _ps._git_sha(root) if root else "unknown",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}", "hark": str(hark),
        "saved_at": time.time(), "saved_at_iso": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "argv": list(argv or []), "cwd": os.getcwd(),
        "world": (os.environ.get("HAFISCAL_WORLD", "").strip() or "default"),
        "entry_defaults_applied": dict(entry_defaults or {}),
        "resolved_config": cfg,
    }


def fingerprint(parametrization="Baseline", scenarios=SCENARIOS, include_dist_top=True,
                quiet=True, argv=None):
    """Build the economy (no solve) and key every agent in every scenario through
    ``policy_store.key_for`` in the state the economy solve keys on. Returns the
    fingerprint dict (JSON-serializable); the build log is under ``_build_log``."""
    scenarios = tuple(scenarios)
    bad = [s for s in scenarios if s not in SCENARIOS]
    if bad:
        raise ValueError(f"unknown scenario(s) {bad}; choose from {list(SCENARIOS)}")
    entry_defaults = apply_entry_point_defaults()
    eco, log = build_economy_no_solve(parametrization, quiet=quiet)
    agents = [_agent_record(a, i) for i, a in enumerate(eco.agents)]
    env = solver_source = store_format = None
    for s in scenarios:
        # The SAME switch the entry points perform (AggregateDemandEconomy.switch_shock_type:
        # per-agent MrkvArray / IncShkDstn / CondMrkvArrays / per-state LivPrb+PermGroFac,
        # then get_economy_data), then the solve's own pre_solve, then the key.
        eco.switch_shock_type(s)
        for i, a in enumerate(eco.agents):
            a.pre_solve()
            key, inputs = _ps.key_for(a)
            if env is None:
                env, solver_source, store_format = inputs["env"], inputs["solver_source"], inputs["store_format"]
            elif inputs["env"] != env or inputs["solver_source"] != solver_source:
                raise RuntimeError("policy_store.key_inputs env/solver_source differ across agents "
                                   "-- they are process-wide by construction")
            # the key (the exact sha over the full inputs) + the inputs in the leaf form the
            # comparison uses (explain_miss's _flatten: arrays -> "array[shape]:sha12",
            # distributions -> one "dstn(...)" leaf) -- 1/8 the size of the raw records
            agents[i][s] = {"key": key, "leaves": _flatten(inputs["agent"])}
    eco.switch_shock_type("base")
    fp = {
        "fingerprint_format": FORMAT,
        "parametrization": parametrization,
        "scenarios": list(scenarios),
        "store_format": store_format,
        "env": env,
        "solver_source": solver_source,
        "agents": agents,
        "provenance": _provenance(parametrization, entry_defaults, argv),
        "_build_log": log,
    }
    if include_dist_top:
        fp["extra"] = resolve_dist_top()
    # plain JSON types only (the reference file round-trips through json; the live side
    # is compared in the same normalized form so tuple/list and numpy scalars never differ)
    return json.loads(json.dumps(fp, default=str))


# ---------------------------------------------------------------------------
# Comparison (explain_miss style) and report
# ---------------------------------------------------------------------------
_BRACKETS = re.compile(r"\[[^\]]*\]")


def _same(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _comparable(fp, scenarios, include_dist_top):
    """The gated subset: env, extra (optional), and per agent the summary + the key
    inputs of the requested scenarios. Keys / solver_source / provenance are informational."""
    out = {"env": fp.get("env") or {}}
    if include_dist_top and "extra" in fp:
        out["extra"] = fp["extra"]
    agents = []
    for a in fp.get("agents") or []:
        rec = {"summary": a.get("summary") or {}}
        for s in scenarios:
            if s in a:
                rec[s] = {"agent": a[s].get("leaves")}
        agents.append(rec)
    out["agents"] = agents
    return json.loads(json.dumps(out, default=str))


def _parse_path(path):
    """('agents', i, scenario, field) | ('env', name) | ('extra', name) | (top, rest)."""
    parts = path.split(".")
    if parts[0].startswith("agents["):
        i = int(parts[0][7:-1])
        scenario = parts[1] if len(parts) > 1 else "?"
        field = _BRACKETS.sub("", parts[3]) if (len(parts) > 3 and parts[2] == "agent") else (
            _BRACKETS.sub("", parts[2]) if len(parts) > 2 else "?")
        return ("agents", i, scenario, field)
    return (parts[0], ".".join(parts[1:]) if len(parts) > 1 else "")


def _ranges(ints):
    ints = sorted(set(ints))
    out, start, prev = [], None, None
    for i in ints:
        if start is None:
            start = prev = i
        elif i == prev + 1:
            prev = i
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = i
    if start is not None:
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ",".join(out)


def compare(live, ref, scenarios=None, include_dist_top=True):
    """Leaf-by-leaf diff of the gated subset. Returns ``(diffs, notes)``: ``diffs`` =
    list of ``(path, live_value, ref_value)`` over the common scenarios; ``notes`` =
    informational lines (scenario coverage asymmetry, solver-source, store keys)."""
    notes = []
    live_sc, ref_sc = list(live.get("scenarios") or []), list(ref.get("scenarios") or [])
    common = [s for s in (scenarios or live_sc) if s in live_sc and s in ref_sc]
    only_live = [s for s in (scenarios or live_sc) if s in live_sc and s not in ref_sc]
    only_ref = [s for s in ref_sc if s not in live_sc]
    if only_live:
        notes.append(f"scenarios not pinned by the reference (not compared): {only_live}")
    if only_ref:
        notes.append(f"reference scenarios not built here (not compared): {only_ref}")
    if include_dist_top and ("extra" in live) != ("extra" in ref):
        side = "reference" if "extra" in ref else "live"
        notes.append(f"extra block (dist_aGrid_max) present only on the {side} side -- "
                     f"reported as a difference; build both with the same --include-dist-top")
    a = _flatten(_comparable(live, common, include_dist_top))
    b = _flatten(_comparable(ref, common, include_dist_top))
    diffs = []
    for p in sorted(set(a) | set(b)):
        x, y = a.get(p, "<absent>"), b.get(p, "<absent>")
        if not _same(x, y):
            diffs.append((p, x, y))
    if live.get("solver_source") != ref.get("solver_source"):
        notes.append(f"solver_source differs (a solver EDIT; every store key changes, no primitive need "
                     f"differ): live {str(live.get('solver_source'))[:12]} | reference "
                     f"{str(ref.get('solver_source'))[:12]}")
    n_keys = n_eq = 0
    for la, ra in zip(live.get("agents") or [], ref.get("agents") or []):
        for s in common:
            if s in la and s in ra:
                n_keys += 1
                n_eq += int(la[s].get("key") == ra[s].get("key"))
    if n_keys:
        notes.append(f"store keys: {n_eq}/{n_keys} (agent, scenario) keys equal the reference's")
    return diffs, notes


def _store_presence(fp, scenarios):
    n = k = 0
    for a in fp.get("agents") or []:
        for s in scenarios:
            if s in a and a[s].get("key"):
                n += 1
                try:
                    k += int(os.path.exists(_ps._paths(a[s]["key"])[1]))
                except Exception:
                    pass
    return k, n


def format_report(live, ref, diffs, notes, max_lines=12):
    prov = ref.get("provenance") or {}
    lines = [f"reference: {prov.get('parametrization', '?')} built {prov.get('saved_at_iso', '?')} on "
             f"{prov.get('host', '?')} @ {prov.get('hafiscal_sha', '?')} (world {prov.get('world', '?')})",
             f"live:      {live.get('parametrization', '?')} on {socket.gethostname()} @ "
             f"{(live.get('provenance') or {}).get('hafiscal_sha', '?')} (world "
             f"{(live.get('provenance') or {}).get('world', '?')})",
             f"agents: {len(live.get('agents') or [])} live / {len(ref.get('agents') or [])} reference; "
             f"scenarios compared: {[s for s in live.get('scenarios') or [] if s in (ref.get('scenarios') or [])]}"]
    n_live, n_ref = len(live.get("agents") or []), len(ref.get("agents") or [])
    if n_live != n_ref:
        lines.append(f"  STRUCTURE: agent count differs ({n_live} live vs {n_ref} reference) -- "
                     f"live betas {[a.get('beta') for a in live.get('agents') or []]}; "
                     f"reference betas {[a.get('beta') for a in ref.get('agents') or []]}")
    env_d = [(p, x, y) for p, x, y in diffs if p.startswith("env.")]
    extra_d = [(p, x, y) for p, x, y in diffs if p.startswith("extra.")]
    agent_d = [(p, x, y) for p, x, y in diffs if p.startswith("agents[")]
    n_env_leaves = len((live.get("env") or {}))
    lines.append(f"env (solver regime): {len(env_d)} of {n_env_leaves} leaves differ")
    for p, x, y in env_d[:max_lines]:
        lines.append(f"    {p[4:]}: live={x!r} | reference={y!r}")
    if len(env_d) > max_lines:
        lines.append(f"    ... {len(env_d) - max_lines} more env leaves")
    if extra_d:
        for p, x, y in extra_d:
            lines.append(f"extra: {p[6:]}: live={x!r} | reference={y!r}")
    groups = {}   # (field, scenario-or-summary) -> {index: example}
    for p, x, y in agent_d:
        _, i, scenario, field = _parse_path(p)
        g = groups.setdefault((field, scenario), {})
        g.setdefault(i, (p, x, y))
    by_field = {}
    for (field, scenario), members in groups.items():
        by_field.setdefault(field, {})[scenario] = members
    n_agents_diff = len({i for m in groups.values() for i in m})
    lines.append(f"agents: {n_agents_diff} agents differ in {len(by_field)} fields ({len(agent_d)} leaves)")
    for n, (field, per_sc) in enumerate(sorted(by_field.items())):
        if n >= max_lines:
            lines.append(f"    ... {len(by_field) - max_lines} more fields")
            break
        idx = sorted({i for m in per_sc.values() for i in m})
        sc = [s for s in (live.get("scenarios") or []) + ["summary"] if s in per_sc]
        ex_sc = sc[0]
        ex_i = min(per_sc[ex_sc])
        p, x, y = per_sc[ex_sc][ex_i]
        lines.append(f"    {field}: agents [{_ranges(idx)}] in {sc}; e.g. {p}: "
                     f"live={str(x)[:60]} | reference={str(y)[:60]}")
    for nline in notes:
        lines.append(f"note: {nline}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def write_reference(path, fp):
    """Compact JSON (sorted keys), gzip when ``path`` ends with ``.gz`` (a Baseline
    reference is ~3 MB plain / ~0.2 MB gzipped -- use ``.json.gz`` for a committed one);
    written to a temp name and renamed, like the store metas."""
    import gzip
    tmp = f"{path}.tmp.{os.getpid()}"
    opener = gzip.open if path.endswith(".gz") else open
    with opener(tmp, "wt") as f:
        json.dump(fp, f, sort_keys=True, separators=(",", ":"))
    os.replace(tmp, path)


def read_reference(path):
    import gzip
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        return json.load(f)


_ARRAY_LEAF = re.compile(r"array\[(\d+)")


def _state_count(leaves):
    """S from the ``MrkvArray[0]`` leaf (``"array[S, S]:sha12"`` in _flatten's form)."""
    for k, v in (leaves or {}).items():
        if k.startswith("MrkvArray") and isinstance(v, str):
            m = _ARRAY_LEAF.match(v)
            if m:
                return int(m.group(1))
    return "?"


def _reference_summary(fp):
    agents = fp.get("agents") or []
    by_educ = {}
    for a in agents:
        by_educ.setdefault(a.get("educ"), []).append(a)
    lines = [f"{fp.get('parametrization')}: {len(agents)} agents, scenarios {fp.get('scenarios')}, "
             f"solver_source {str(fp.get('solver_source'))[:12]}"]
    for educ, members in sorted(by_educ.items(), key=lambda kv: (kv[0] is None, kv[0])):
        s = members[0].get("summary") or {}
        betas = [m.get("beta") for m in members]
        S = {sc: _state_count((members[0].get(sc) or {}).get("leaves"))
             for sc in fp.get("scenarios") or [] if sc in members[0]}
        lines.append(f"  educ {educ}: {len(members)} atoms, beta [{min(betas):.6f} .. {max(betas):.6f}], "
                     f"grid {s.get('aXtraMin'):.4g}..{s.get('aXtraMax'):.4g} x{s.get('aXtraCount')}, "
                     f"T_age {s.get('T_age')}, Splurge {s.get('Splurge')}, IncUnemp {s.get('IncUnemp')}/"
                     f"{s.get('IncUnempNoBenefits')}, states {S}")
    env_set = {k: v for k, v in (fp.get("env") or {}).items() if v}
    lines.append(f"  env leaves set: {env_set}")
    if "extra" in fp:
        lines.append(f"  extra: {fp['extra']}")
    ed = (fp.get("provenance") or {}).get("entry_defaults_applied") or {}
    if ed:
        lines.append(f"  entry-point defaults applied (were unset): {ed}")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python -m solution_cache.fingerprint",
        description="Primitives fingerprint gate on policy_store.key_inputs: freeze what a "
                    "launch would build (--reference) or diff the live build against a "
                    "reference (--check; exit 1 on any difference).")
    p.add_argument("--parametrization", default="Baseline",
                   help="Parameters.return_parameters name (default Baseline; HS_Only / "
                        "Reduced_Run for tests)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--reference", metavar="OUT.json", help="write the live fingerprint here")
    g.add_argument("--check", metavar="REF.json", help="diff the live fingerprint against this file")
    p.add_argument("--scenarios", default=",".join(SCENARIOS),
                   help=f"comma list from {list(SCENARIOS)} (default all)")
    p.add_argument("--include-dist-top", action=argparse.BooleanOptionalAction, default=True,
                   help="record/compare the TM distribution-grid top (HAFISCAL_TM_AMAX / "
                        "HAFISCAL_DIST_TOP_MODE) as the extra block (default on)")
    p.add_argument("--max-lines", type=int, default=12, help="report lines per section")
    p.add_argument("--verbose", action="store_true", help="show the construction log")
    a = p.parse_args(argv)
    scenarios = tuple(s.strip() for s in a.scenarios.split(",") if s.strip())
    # resolve paths BEFORE the build (welfare6_scenario chdirs at import)
    out_path = os.path.abspath(a.reference) if a.reference else None
    ref_path = os.path.abspath(a.check) if a.check else None
    t0 = time.time()
    try:
        fp = fingerprint(a.parametrization, scenarios=scenarios,
                         include_dist_top=a.include_dist_top, quiet=not a.verbose, argv=sys.argv)
    except Exception as e:
        _log(f"BUILD FAILED for {a.parametrization!r}: {type(e).__name__}: {str(e)[:200]}")
        return 2
    build_s = time.time() - t0
    log = fp.pop("_build_log", "")
    k, n = _store_presence(fp, scenarios)
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        write_reference(out_path, fp)
        _log(f"REFERENCE written: {out_path} ({os.path.getsize(out_path) / 1e6:.2f} MB, "
             f"built in {build_s:.1f} s)")
        print(_reference_summary(fp))
        _log(f"store entries present on this machine: {k}/{n} under {_ps.store_dir()}")
        return 0
    try:
        ref = read_reference(ref_path)
    except Exception as e:
        _log(f"cannot read reference {ref_path}: {type(e).__name__}: {e}")
        return 2
    if ref.get("fingerprint_format") != FORMAT:
        _log(f"reference format {ref.get('fingerprint_format')!r} != {FORMAT}")
        return 2
    diffs, notes = compare(fp, ref, scenarios=scenarios, include_dist_top=a.include_dist_top)
    structural = len(fp.get("agents") or []) != len(ref.get("agents") or [])
    _log(f"CHECK {a.parametrization} vs {ref_path} (built in {build_s:.1f} s)")
    print(format_report(fp, ref, diffs, notes, max_lines=a.max_lines))
    _log(f"store entries present on this machine: {k}/{n} under {_ps.store_dir()}")
    if a.verbose and log:
        print("---- construction log ----")
        print(log)
    if diffs or structural:
        _log(f"RESULT: DIFFERENT ({len(diffs)} leaves) -> exit 1")
        return 1
    _log("RESULT: IDENTICAL -> exit 0")
    return 0


if __name__ == "__main__":
    reexec_with_thread_caps_if_needed()
    sys.exit(main())
