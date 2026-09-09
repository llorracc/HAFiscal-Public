"""HAFiscal configuration control — single source of truth for the config "worlds".

This package defines the named configuration *worlds* (`default`,
`as-corrected`) and the result-neutral *improvements* axis, derived from one
per-setting catalog (`catalog.py`). It is the durable answer to "what goes in
`--default` vs `--as-corrected`?".

Design + rationale:
- conclusions_private/20260613_config-worlds-definition-default-legacy.md (definitions, taxonomy)
- plans/20260613-1450h_configuration-control-scheme-design.md (architecture, axes)

STATUS: foundational data layer (the catalog + pure derivation helpers). Not yet
wired into EstimParameters / do_all / reproduce.sh — see the design plan's phased
implementation. Importing this package has NO side effects and does NOT read or
mutate os.environ.
"""

from .catalog import (
    BUG_FIX,
    IMPROVEMENT,
    DISCRETIONARY,
    CATEGORIES,
    DEFAULT,
    AS_CORRECTED,
    WORLDS,
    Setting,
    CATALOG,
    by_name,
    world_value,
    resolve_world,
)
from .resolve import (
    METHODS,
    Resolved,
    resolve,
    format_banner,
    apply,
    effective_config,
)

__all__ = [
    "BUG_FIX",
    "IMPROVEMENT",
    "DISCRETIONARY",
    "CATEGORIES",
    "DEFAULT",
    "AS_CORRECTED",
    "WORLDS",
    "Setting",
    "CATALOG",
    "by_name",
    "world_value",
    "resolve_world",
    "METHODS",
    "Resolved",
    "resolve",
    "format_banner",
    "apply",
    "effective_config",
]
