"""Run the step4 GE stage against an ARBITRARY jacs obj, writing to scratch.

The ladder's GE passes never touch the tracked pickle: this child applies the
rung env BEFORE importing step4, then monkeypatches ``ge.JACS_OBJ`` and
``ge.OUTPUT_PICKLE`` (and points figures at a scratch dir) and calls
``ge.run()``.

Usage:
    python -m ssj_ladder.run_ge_scratch --jacs rung.obj --pickle out.obj \
        --figdir /tmp/figs --env KEY=VAL --env KEY2='<unset>'
"""
import argparse
import os
import sys

from .build_obj import apply_env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jacs", required=True)
    ap.add_argument("--pickle", required=True)
    ap.add_argument("--figdir", default="")
    ap.add_argument("--env", action="append", default=[])
    a = ap.parse_args()
    # abspath BEFORE chdir_fpc — relative paths anchor at the caller's cwd
    a.jacs = os.path.abspath(a.jacs)
    a.pickle = os.path.abspath(a.pickle)
    if a.figdir:
        a.figdir = os.path.abspath(a.figdir)
    apply_env(a.env)
    sys.argv = [sys.argv[0]]

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if here not in sys.path:
        sys.path.insert(0, here)

    from step4.common import chdir_fpc, monolith_route_reason
    reason = monolith_route_reason("ge")
    if reason:
        raise SystemExit(
            f"refusing: this env routes the GE stage to the frozen monolith "
            f"({reason}); the ladder runs the package GE only")
    chdir_fpc()
    from step4 import ge, figures
    ge.JACS_OBJ = a.jacs
    out = a.pickle
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ge.OUTPUT_PICKLE = out
    if a.figdir:
        figures.figures_dir = a.figdir
    print(f"[ladder-ge] JACS_OBJ={ge.JACS_OBJ}\n[ladder-ge] OUTPUT_PICKLE={out}",
          flush=True)
    ge.run()


if __name__ == "__main__":
    main()
