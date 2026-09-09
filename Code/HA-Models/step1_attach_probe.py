"""step1_attach_probe.py — solve-level diagnostics for the Step-1 above-grid attach.

Part of the grid-only tail comprehensive test battery (owner charge 2026-08-21:
"make then execute a comprehensive set of tests for whether they work in practice
for the problems we are solving here"). This runner exercises the REAL Step-1
path — no replica: it imports ``Estimation_BetaNablaSplurge`` under its own
``HAFISCAL_STEP1_RUN_ESTIMATION=0`` import-safe fixed-point eval mode, calls
``FagerengObjFunc`` ONCE at a given (splurge, beta, nabla) — by default the
installed SoR optimum from ``Result_AllTarget_ESC.txt`` — and dumps per-atom
solution diagnostics to an ``.npz`` consumed by ``test_step1_tail_attach.py``.

The grid/attach configuration under test is selected by the caller's environment
(HAFISCAL_SOLVE_GRID_PROFILE / HAFISCAL_PF_DECAY_Q / HAFISCAL_STEP1_TAIL_KNOTS /
HAFISCAL_STEP1_TAIL_REACH ...), exactly as a real estimation run would be.

READ-ONLY GUARANTEE: eval mode runs no estimation arm, so nothing may touch the
estimation artifacts. The probe snapshots every ``Result_*.txt`` mtime before
import and re-checks after the dump; any change exits 3 (the trap-15 guard —
an accidental in-repo estimation once overwrote the SoR).

Per atom j the npz carries:
  atom{j}_grid   solved aXtraGrid (basis + any tail knots)
  atom{j}_m      evaluation points (dense geomspace + continuity pairs at the top)
  atom{j}_c      cFunc(m)
  atom{j}_dc     cFunc.derivative(m)  (NaN vector if the interp exposes none)
  atom{j}_psi / _theta / _pmv   the type's OWN discretized shock support
and a json ``meta`` with per-atom scalars: DiscFac, LivPrb, Rfree(save), CRRA,
PermGroFac, MPCmin, hNrm, decay_extrap_Q (the installed tail exponent), the
decay form, and the interp class names — everything the tests need to compute
attach metrics and the far-field certification cross-check (farfield_tail_q).
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import sys

import numpy as np


def _find_decay_holder(cF):
    """Walk a composed cFunc for the object carrying the decay-tail attributes."""
    seen = []
    stack = [cF]
    while stack:
        obj = stack.pop(0)
        if obj is None or id(obj) in (id(s) for s in seen):
            continue
        seen.append(obj)
        if getattr(obj, "decay_extrap", None) or hasattr(obj, "decay_extrap_Q"):
            return obj
        for attr in ("functions", "interpolants"):
            sub = getattr(obj, attr, None)
            if isinstance(sub, (list, tuple)):
                stack.extend(sub)
        for attr in ("function", "interpolant", "func"):
            sub = getattr(obj, attr, None)
            if sub is not None and not callable(getattr(sub, "upper", None)):
                stack.append(sub)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="output .npz path")
    ap.add_argument("--splurge", type=float, default=None)
    ap.add_argument("--beta", type=float, default=None)
    ap.add_argument("--nabla", type=float, default=None)
    ap.add_argument("--mmax", type=float, default=3.0e4,
                    help="far edge of the evaluation vector")
    args = ap.parse_args()

    # Eval mode is REQUIRED (hard-set, not setdefault): the probe must never run
    # an estimation arm regardless of the caller's environment.
    os.environ["HAFISCAL_STEP1_RUN_ESTIMATION"] = "0"
    os.environ["HAFISCAL_STEP1_SPLURGE0"] = "0"
    os.environ["HAFISCAL_STEP1_PLOT"] = "0"
    os.environ.pop("HAFISCAL_STEP1_OTHER_CRRA", None)

    here = os.path.dirname(os.path.abspath(__file__))
    tgt = os.path.join(here, "Target_AggMPCX_LiquWealth")
    sys.path.insert(0, tgt)
    sys.path.insert(0, here)
    os.chdir(tgt)

    if args.splurge is None or args.beta is None or args.nabla is None:
        with open(os.path.join(tgt, "Result_AllTarget_ESC.txt")) as fh:
            sor = ast.literal_eval(fh.read().strip())
        splurge = sor["splurge"] if args.splurge is None else args.splurge
        beta = sor["beta"] if args.beta is None else args.beta
        nabla = sor["nabla"] if args.nabla is None else args.nabla
    else:
        splurge, beta, nabla = args.splurge, args.beta, args.nabla

    guard_files = sorted(glob.glob(os.path.join(tgt, "Result_*.txt")))
    mtimes = {f: os.path.getmtime(f) for f in guard_files}

    import Estimation_BetaNablaSplurge as E  # noqa: E402  (import-safe: eval mode)

    fval = E.FagerengObjFunc(splurge, beta, nabla, verbose=False,
                             estimation_mode=True,
                             target="AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC")

    arrays = {}
    meta = {"splurge": float(splurge), "beta_center": float(beta),
            "nabla": float(nabla), "fval": float(fval), "atoms": []}
    for j, T in enumerate(E.EstTypeList):
        sol = T.solution[0]
        cF = sol.cFunc
        grid = np.asarray(T.aXtraGrid, dtype=float)
        top = float(grid.max())
        m_dense = np.geomspace(0.05, args.mmax, 800)
        pairs = np.array([top * (1 - 1e-6), top * (1 - 1e-8),
                          top * (1 + 1e-8), top * (1 + 1e-6)])
        m = np.unique(np.concatenate([m_dense, pairs]))
        c = np.asarray(cF(m), dtype=float)
        try:
            dc = np.asarray(cF.derivative(m), dtype=float)
        except Exception:
            dc = np.full_like(m, np.nan)

        holder = _find_decay_holder(cF)
        shk = T.IncShkDstn[0]
        psi = np.asarray(shk.atoms[0], dtype=float)
        theta = np.asarray(shk.atoms[1], dtype=float)
        pmv = np.asarray(shk.pmv, dtype=float)

        arrays[f"atom{j}_grid"] = grid
        arrays[f"atom{j}_m"] = m
        arrays[f"atom{j}_c"] = c
        arrays[f"atom{j}_dc"] = dc
        arrays[f"atom{j}_psi"] = psi
        arrays[f"atom{j}_theta"] = theta
        arrays[f"atom{j}_pmv"] = pmv
        meta["atoms"].append({
            "j": j,
            "DiscFac": float(T.DiscFac),
            "LivPrb": float(np.ravel(T.LivPrb)[0]),
            "Rfree": float(np.ravel(getattr(T, "Rsave", T.Rfree))[0]),
            "CRRA": float(T.CRRA),
            "PermGroFac": float(np.ravel(T.PermGroFac)[0]),
            "MPCmin": float(getattr(sol, "MPCmin", np.nan)),
            "hNrm": float(getattr(sol, "hNrm", np.nan)),
            "grid_top": top,
            "grid_len": int(grid.size),
            "decay_extrap_Q": (float(getattr(holder, "decay_extrap_Q", np.nan))
                               if holder is not None else float("nan")),
            "decay_form": (str(getattr(holder, "decay_extrap_form", ""))
                           if holder is not None else ""),
            "cfunc_class": type(cF).__name__,
            "holder_class": type(holder).__name__ if holder is not None else "",
        })

    changed = [f for f in guard_files if os.path.getmtime(f) != mtimes[f]]
    if changed:
        print(f"PROBE_WRITE_VIOLATION: {changed}", file=sys.stderr)
        sys.exit(3)

    out = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    np.savez_compressed(out, meta=json.dumps(meta), **arrays)
    print(f"PROBE_OK f={fval:.10g} atoms={len(meta['atoms'])} out={out}")


if __name__ == "__main__":
    main()
