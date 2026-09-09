"""Build the step4 household-Jacobian obj to a SCRATCH path.

The ladder never writes the tracked ``FromPandemicCode/HA_Fiscal_Jacs.obj``
(execution protocol, plan 20260901-2010h §7): this child applies the rung's
env BEFORE any step4 import (hh_setup reads HAFISCAL_HANK_BIGT and friends at
module load), owns sys.argv (Parameters reads argv on every
return_parameters call), refuses monolith-routing envs (the frozen monolith
writes the tracked path unconditionally), and monkeypatches
``jacobians.OUTPUT_OBJ`` to the requested scratch path.

Usage:
    python -m ssj_ladder.build_obj --out /path/rung.obj \
        --env HAFISCAL_HANK_BIGT=300 --env HAFISCAL_QE_FIDELITY='<unset>'

``KEY=<unset>`` removes KEY from the child's env (rungs that hop back to
pure defaults need real unsetting, not empty strings).
"""
import argparse
import os
import sys


def apply_env(pairs):
    for kv in pairs:
        k, _, v = kv.partition("=")
        if not k.startswith("HAFISCAL_") and k not in (
                "PYTHONUNBUFFERED", "MPLBACKEND", "MATPLOTLIB_BACKEND"):
            raise SystemExit(f"refusing non-HAFISCAL env key: {k!r}")
        if v == "<unset>":
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", action="append", default=[],
                    help="KEY=VAL applied before the first step4 import; "
                         "KEY=<unset> removes KEY")
    a = ap.parse_args()
    a.out = os.path.abspath(a.out)  # BEFORE chdir_fpc: relative --out must
    #                                 anchor at the caller's cwd, not FPC
    apply_env(a.env)
    sys.argv = [sys.argv[0]]  # Parameters reads argv at call time

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if here not in sys.path:
        sys.path.insert(0, here)

    from step4.common import chdir_fpc, monolith_route_reason
    reason = monolith_route_reason("jacobians")
    if reason:
        raise SystemExit(
            f"refusing: this env routes the Jacobian stage to the frozen "
            f"monolith ({reason}), which writes the tracked obj; the ladder "
            f"builds package objs only")
    chdir_fpc()
    from step4 import jacobians
    out = a.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    jacobians.OUTPUT_OBJ = out
    print(f"[ladder-build] OUTPUT_OBJ -> {out}", flush=True)
    jacobians.run()
    if not os.path.exists(out):
        raise SystemExit(f"build finished but {out} was not written")
    print(f"[ladder-build] done: {out} ({os.path.getsize(out)} bytes)",
          flush=True)


if __name__ == "__main__":
    main()
