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


def find_fti_repo():
    """Return a fast-time-iteration checkout dir that contains ``hark_fti/``, or None."""
    candidates = []
    env = os.environ.get("HAFISCAL_FTI_REPO")
    if env:
        candidates.append(env)
    here = os.path.dirname(os.path.abspath(__file__))
    # FromPandemicCode -> HA-Models -> Code -> HAFiscal-Latest -> <parent of repo>
    haf_root = os.path.normpath(os.path.join(here, os.pardir, os.pardir, os.pardir))
    candidates.append(os.path.join(os.path.dirname(haf_root), "fast-time-iteration"))
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
