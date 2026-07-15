"""Resolver: turn (world, improvements, method, scope, overrides) into a final
config, with provenance + a footgun gate + a self-logging banner.

Orthogonal axes (plans/20260613-1450h_configuration-control-scheme-design.md):
  WORLD        — `default` | `as-corrected`   (catalog-driven results semantics)
  IMPROVEMENTS — result-neutral accelerators layered onto a world (e.g. `gicx`)
  METHOD       — `MC` | `TM` | `both`         (HAFISCAL_SIM_METHOD pass-through)
  SCOPE        — which do_all steps run        (HAFISCAL_RUN_STEP_* pass-through)

Precedence (low -> high): world base  <  improvement opt-ins  <  method/scope
<  explicit overrides.

WIRING STATUS (R2, 2026-06-13): the WORLD axis is now wired into the run path.
`EstimParameters.py` (the canonical block, imported by every entry point) selects a
world via `HAFISCAL_WORLD` (`default` | `as-corrected`) and applies the world-varying
*runtime, world-safe* settings from `catalog.resolve_world(...)` via os.environ.setdefault.
Guarded by `config/test_runtime_parity.py`. STILL DOCS-ONLY / not auto-applied:
  - the full `apply()` here (its method/scope/footgun/override machinery) — entry points
    use `resolve_world` (catalog) directly, not this `resolve()`/`apply()` pair, yet;
  - `HAFISCAL_TM_A_INDEXED` — deliberately excluded from the wired subset (set per-entry-point,
    BUG-033). (`HAFISCAL_INTERPRETATION`'s ESC default-flip, owner ruling Q5, is now WIRED
    2026-06-14 — but as an UNCONDITIONAL global default in EstimParameters, NOT via this world
    machinery, because it does not vary by world; see catalog.py interpretation + EstimParameters.);
  - a *fully runnable* `as-corrected` world — it needs matched re-estimated calibration
    (perm-during-unemp affects the estimate), so the wired path warns it is RUNTIME-ONLY.
See plans/20260613-1830h_config-taxonomy-reconciliation-post-econ-mw-merge.md (R2).

`resolve()`/`format_banner()`/`apply()` remain pure; `apply()` uses os.environ.setdefault,
so a pre-set env var always wins.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .catalog import (
    CATALOG,
    DEFAULT,
    AS_CORRECTED,
    WORLDS,
    IMPROVEMENT,
    by_name,
    world_value,
    resolve_world,
)

# --- METHOD / SCOPE vocabularies -------------------------------------------
METHODS = ("MC", "TM", "both")
# do_all step toggles, in pipeline order; scope = the subset to RUN.
STEP_ENV = {
    1: "HAFISCAL_RUN_STEP_1",
    2: "HAFISCAL_RUN_STEP_2",
    3: "HAFISCAL_RUN_STEP_3",
    4: "HAFISCAL_RUN_STEP_4",
    5: "HAFISCAL_RUN_STEP_5",
}

# --- FOOTGUN GATE -----------------------------------------------------------
# Final resolved values that are known-wrong and must never be selected by a
# world/override (the QE-repro of a footgun world is the old branch's job).
# Each rule: (env_var, predicate(value)->is_footgun, human reason).
_FOOTGUNS = (
    (
        "HAFISCAL_SHUFFLE_MRKV_TRANSITION",
        lambda v: v.strip().lower() == "shuffle",
        "plain 'shuffle' is the +8.26%-UI footgun; use 'stratified' "
        "(BUG-044 / conclusions_private/2026-06-10_welfare_method_unified_MC.md).",
    ),
)

_IMPROVEMENT_NAMES = frozenset(s.name for s in CATALOG if s.category == IMPROVEMENT)


@dataclass(frozen=True)
class Resolved:
    world: str
    improvements: frozenset
    method: Optional[str]
    scope: Optional[tuple]
    env: dict = field(default_factory=dict)        # env_var -> final value
    provenance: dict = field(default_factory=dict)  # env_var -> source label
    confirm: tuple = ()                              # (setting_name, note) needing owner confirm


def resolve(
    world: str = DEFAULT,
    improvements: Iterable[str] = (),
    method: Optional[str] = None,
    scope: Optional[Iterable[int]] = None,
    overrides: Optional[dict] = None,
    *,
    allow_footguns: bool = False,
    include_estimation_only: bool = True,
) -> Resolved:
    """Resolve axes into a final {env_var: value} map with provenance.

    Raises ValueError on an unknown world/method/improvement, or on a footgun
    value unless allow_footguns=True.
    """
    if world not in WORLDS:
        raise ValueError(f"unknown world {world!r}; expected one of {WORLDS}")
    imps = frozenset(improvements)
    bad = imps - _IMPROVEMENT_NAMES
    if bad:
        raise ValueError(f"unknown improvement(s) {sorted(bad)}; "
                         f"available: {sorted(_IMPROVEMENT_NAMES)}")
    if method is not None and method not in METHODS:
        raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")

    env: dict = {}
    prov: dict = {}
    confirm: list = []

    # 1) world base + improvement opt-ins (catalog-driven)
    for s in CATALOG:
        if s.env_var is None:
            continue
        if s.estimation_only and not include_estimation_only:
            continue
        val = world_value(s, world, imps)
        env[s.env_var] = val
        if s.category == IMPROVEMENT and s.name in imps and world != DEFAULT:
            prov[s.env_var] = f"improvement:{s.name}"
        else:
            prov[s.env_var] = f"world:{world}"
        if s.confirm and (world == DEFAULT or s.name in imps):
            confirm.append((s.name, s.confirm))

    # 2) method axis
    if method is not None:
        env["HAFISCAL_SIM_METHOD"] = method
        prov["HAFISCAL_SIM_METHOD"] = "method"

    # 3) scope axis (run exactly the listed steps; others explicitly off)
    scope_t: Optional[tuple] = None
    if scope is not None:
        scope_t = tuple(sorted(set(scope)))
        unknown = [n for n in scope_t if n not in STEP_ENV]
        if unknown:
            raise ValueError(f"unknown step(s) {unknown}; valid: {sorted(STEP_ENV)}")
        for n, var in STEP_ENV.items():
            env[var] = "1" if n in scope_t else "0"
            prov[var] = "scope"

    # 4) explicit overrides (highest precedence)
    for k, v in (overrides or {}).items():
        env[k] = str(v)
        prov[k] = "override"

    # 5) footgun gate (on the FINAL values)
    if not allow_footguns:
        for var, is_footgun, reason in _FOOTGUNS:
            if var in env and is_footgun(env[var]):
                raise ValueError(
                    f"FOOTGUN blocked: {var}={env[var]!r} -> {reason} "
                    f"(pass allow_footguns=True to override deliberately)."
                )

    return Resolved(
        world=world,
        improvements=imps,
        method=method,
        scope=scope_t,
        env=env,
        provenance=prov,
        confirm=tuple(confirm),
    )


def format_banner(r: Resolved) -> str:
    """Human-readable provenance banner for logs (what config ran, and why)."""
    lines = []
    lines.append("=" * 72)
    lines.append("HAFiscal config resolved")
    lines.append(f"  world        : {r.world}")
    lines.append(f"  improvements : {', '.join(sorted(r.improvements)) or '(none)'}")
    lines.append(f"  method       : {r.method or '(unset)'}")
    lines.append(f"  scope        : {','.join(map(str, r.scope)) if r.scope else '(all)'}")
    lines.append("-" * 72)
    width = max((len(k) for k in r.env), default=0)
    for k in sorted(r.env):
        lines.append(f"  {k:<{width}} = {r.env[k]!r:<14} [{r.provenance.get(k, '?')}]")
    if r.confirm:
        lines.append("-" * 72)
        lines.append("  CONFIRM (unverified assumptions in active settings):")
        for name, note in r.confirm:
            lines.append(f"    - {name}: {note}")
    lines.append("=" * 72)
    return "\n".join(lines)


def effective_config(*, include_estimation_only: bool = True) -> dict:
    """Report the configuration ACTUALLY in force, by reading os.environ.

    Unlike `resolve_world` / `resolve` (both pure), this consults os.environ to
    discover the active world (`HAFISCAL_WORLD`, default ``default``) and then,
    for every env-controlled catalog setting, records the value that is really
    in effect (a pre-set env var WINS over the world's value, mirroring the
    `os.environ.setdefault` apply semantics). It also surfaces the most
    load-bearing axes by name (method / interpretation / perm_during_unemp).

    This is the canonical input for provenance capture (`provenance.py`): it is
    the resolved EFFECTIVE config, not a raw env snapshot, so a human reads
    semantics ("default world, ESC, perm=on") rather than env-var presence.

    Never raises: an unknown `HAFISCAL_WORLD` is reported as-is with
    ``world_known=False`` and an empty resolved-env base.
    """
    world = os.environ.get("HAFISCAL_WORLD", DEFAULT)
    world_known = world in WORLDS
    try:
        base = resolve_world(world, include_estimation_only=include_estimation_only)
    except ValueError:
        base = {}

    env_final: dict = {}
    overridden: list = []
    for var, world_val in base.items():
        actual = os.environ.get(var)
        if actual is not None and actual != world_val:
            env_final[var] = actual
            overridden.append(var)
        else:
            env_final[var] = world_val if actual is None else actual

    return {
        "world": world,
        "world_known": world_known,
        "method": (os.environ.get("HAFISCAL_SIM_METHOD")
                   or os.environ.get("HAFISCAL_MULTIPLIER_ENGINE")),
        "interpretation": os.environ.get("HAFISCAL_INTERPRETATION", "ESC"),
        # Prefer the resolved world value (e.g. default -> on) over raw env, so the
        # defining axis is reported even when not explicitly exported.
        "perm_during_unemp": env_final.get(
            "HAFISCAL_PERM_DURING_UNEMP",
            os.environ.get("HAFISCAL_PERM_DURING_UNEMP")),
        "env": dict(sorted(env_final.items())),
        "env_overridden": sorted(overridden),
    }


def apply(r: Resolved, *, log=None) -> dict:
    """Apply resolved env via os.environ.setdefault (pre-set vars still win).

    NOT wired into any entry point yet. Returns the dict of vars actually set
    (i.e. that were not already present). If `log` is given (a callable), the
    banner is emitted through it.
    """
    if log is not None:
        log(format_banner(r))
    actually_set = {}
    for k, v in r.env.items():
        if k not in os.environ:
            os.environ[k] = v
            actually_set[k] = v
    return actually_set
