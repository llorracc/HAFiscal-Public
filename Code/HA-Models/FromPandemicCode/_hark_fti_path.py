"""Resolve the external ``hark_fti`` solver package (homed in fast-time-iteration).

The generic fast-time-iteration solver family (White's NAM / Winant's ATI, the
global-Newton NAMG derivatives, and the licence-clean Anderson-EGM /
consumed(a)-Newton / ConsumedATI Tier-C solvers) was relocated OUT of HAFiscal
into the sibling ``fast-time-iteration`` repo, which is now its canonical home.
HAFiscal consumes it as an external, strictly OPT-IN dependency: nothing on the
default reproduction path imports ``hark_fti``.

Importing this module makes ``import hark_fti`` resolvable by locating a
fast-time-iteration checkout, in this order:

1. ``hark_fti`` is already importable (e.g. ``uv pip install -e ../fast-time-iteration``).
2. ``$HAFISCAL_FTI_REPO`` points at a fast-time-iteration checkout.
3. the sibling ``../fast-time-iteration`` next to the HAFiscal-Latest repo root.

If none resolve, a ``ModuleNotFoundError`` with actionable guidance is raised.
Only opt-in FTI code paths import this module, so the default pipeline is
unaffected when fast-time-iteration is absent.
"""
from __future__ import annotations

import importlib.util
import os
import sys

__all__ = ["ensure_hark_fti", "find_fti_repo"]


# Canonical checkout locations (owner ruling 2026-08-22: the FTI env must ALWAYS
# be available — worktree runs must resolve WITHOUT per-run env plumbing; the
# sibling rule fails under ~/coldrun worktrees, which is how the Step-2 smoke
# silently ran EGM). Env override still wins — and an EXPLICIT env that does not
# resolve is a loud error, never a fall-through (first-use discipline).
_CANONICAL_FTI_LOCATIONS = (
    "/home/shared/github/llorracc/fast-time-iteration",      # dell
    "/Volumes/Sync/GitHub/llorracc/fast-time-iteration",     # m5
    os.path.expanduser("~/GitHub/llorracc/fast-time-iteration"),
)


def find_fti_repo():
    """Return a fast-time-iteration checkout dir that contains ``hark_fti/``, or None.

    Raises ImportError when ``$HAFISCAL_FTI_REPO`` is SET but does not contain
    ``hark_fti/`` (explicit env must never silently fall through)."""
    env = os.environ.get("HAFISCAL_FTI_REPO")
    if env:
        if os.path.isdir(os.path.join(env, "hark_fti")):
            return env
        raise ImportError(
            f"HAFISCAL_FTI_REPO={env!r} is set but contains no hark_fti/ package "
            "— refusing to fall through to other locations (owner ruling "
            "2026-08-22: no silent fallbacks on the FTI path)."
        )
    here = os.path.dirname(os.path.abspath(__file__))
    # FromPandemicCode -> HA-Models -> Code -> HAFiscal-Latest -> <parent of repo>
    haf_root = os.path.normpath(os.path.join(here, os.pardir, os.pardir, os.pardir))
    candidates = [os.path.join(os.path.dirname(haf_root), "fast-time-iteration")]
    candidates.extend(_CANONICAL_FTI_LOCATIONS)
    for d in candidates:
        if d and os.path.isdir(os.path.join(d, "hark_fti")):
            return d
    return None


def ensure_hark_fti():
    """Make ``import hark_fti`` resolvable; raise a helpful error if impossible."""
    if importlib.util.find_spec("hark_fti") is not None:
        return
    repo = find_fti_repo()
    if repo is not None:
        if repo not in sys.path:
            sys.path.insert(0, repo)
        return
    raise ModuleNotFoundError(
        "The opt-in fast-time-iteration solvers (`hark_fti`) are not available. "
        "They now live in the private `fast-time-iteration` repo (canonical home). "
        "Install editable into this environment (`uv pip install -e ../fast-time-iteration`), "
        "set $HAFISCAL_FTI_REPO to a fast-time-iteration checkout, or place that repo "
        "as a sibling of HAFiscal-Latest. The default HAFiscal reproduction does not "
        "require it."
    )


ensure_hark_fti()
