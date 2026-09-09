#!/usr/bin/env python
"""Entry: Step-4 household Jacobians.

Single dispatch point for the L4 engine split — routes to the FROZEN
monolith (HA-Fiscal-HANK-SAM.py) for any historical-semantics request
(HAFISCAL_QE_FIDELITY=1, an explicit historical escape flag, or
HAFISCAL_STEP4_ENGINE=monolith); otherwise runs the live package engine
(fixed semantics: BUG-071/072/073 structural). do_all.py Step 4 invokes
this script; running the monolith directly also still works.
"""
import os
import subprocess
import sys

_HA_MODELS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HA_MODELS not in sys.path:
    sys.path.insert(0, _HA_MODELS)

from step4.common import (FPC_DIR, MONOLITH_JACOBIANS, chdir_fpc,  # noqa: E402
                          monolith_route_reason)


def main():
    reason = monolith_route_reason("jacobians")
    if reason:
        print(f"[step4-engine] monolith (frozen QE-fidelity engine): {reason}",
              flush=True)
        sys.exit(subprocess.call([sys.executable, MONOLITH_JACOBIANS],
                                 cwd=FPC_DIR))
    print("[step4-engine] package (live fixed-semantics engine)", flush=True)
    chdir_fpc()
    from step4 import jacobians
    jacobians.run()


if __name__ == "__main__":
    main()
