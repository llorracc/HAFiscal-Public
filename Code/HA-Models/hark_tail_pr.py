"""hark_tail_pr.py — load HARK PR #1818's ``tail_interpolation`` against the PINNED HARK.

Owner charge (2026-08-22 ~14:20): "I want to be simultaneously debugging the HARK PR
and the related code on this machine." A venv re-pin onto the PR branch is impossible
(the branch sits on upstream main's >=3.12 epoch; HAFiscal's pinned world is 3.11),
but the PR module is nearly self-contained — it imports only ``LinearInterp`` and
``CubicHermiteInterp`` from ``HARK.interpolation``, which the pinned HARK provides
with identical internals (the retrofit's coeffs-row contract was verified against
both). So this loader imports the PR FILE standalone from the PR worktree; its
internal HARK imports resolve to the venv's pinned HARK.

Resolution order for the file:
  1. ``import HARK.tail_interpolation`` (the future: a re-pin that includes the
     merged PR makes this loader a pass-through);
  2. ``HAFISCAL_HARK_TAIL_PR_PATH`` (explicit file path);
  3. the standard dell worktree
     ``/home/shared/github/econ-ark/HARK-tail-toolkit/HARK/tail_interpolation.py``.

Consumption is OPT-IN via ``HAFISCAL_TAIL_IMPL=pr`` (default ``vendored`` — no
default-path change without its own battery): under ``pr``, ``powerlaw_decay`` and
``mom_chart`` rebind ``retrofit_powerlaw`` / ``chartify_chs`` to the PR
implementations at import (every flown consumer imports those names at CALL time,
so the rebinding reaches them). The parity suite
(``test_step1_tail_attach.py::test_pr_impl_parity``) asserts PR == vendored on the
real S1 solve path — the co-debugging tripwire: edit either side into divergence
and the suite fails loudly.

Editing the PR worktree file is live immediately (same file on disk); its own
13-test suite runs standalone in the worktree against upstream main.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_DEFAULT_WORKTREE = ("/home/shared/github/econ-ark/HARK-tail-toolkit/"
                     "HARK/tail_interpolation.py")

_mod = None
_source = None


def load(strict=False):
    """Return the PR module (cached), or None when unavailable (strict=False)."""
    global _mod, _source
    if _mod is not None:
        return _mod
    try:  # 1. a future pinned HARK that includes the merged PR
        import HARK.tail_interpolation as m  # noqa: PLC0415
        _mod, _source = m, "HARK.tail_interpolation (pinned)"
        return _mod
    except Exception:
        pass
    path = os.environ.get("HAFISCAL_HARK_TAIL_PR_PATH", _DEFAULT_WORKTREE)
    if not os.path.exists(path):
        if strict:
            raise ImportError(f"hark_tail_pr: no PR file at {path!r}")
        return None
    spec = importlib.util.spec_from_file_location("hark_tail_interpolation_pr", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["hark_tail_interpolation_pr"] = m
    spec.loader.exec_module(m)  # its HARK imports resolve to the PINNED venv HARK
    _mod, _source = m, path
    return _mod


def pr_mode_active():
    """True iff HAFISCAL_TAIL_IMPL=pr AND the PR module is loadable."""
    if os.environ.get("HAFISCAL_TAIL_IMPL", "vendored").strip().lower() != "pr":
        return False
    return load(strict=False) is not None


def source():
    return _source
