#!/usr/bin/env python
"""Entry: Step-4 GE/SAM experiments (Section-5 figures + multiplier pickle).

Routes to the FROZEN GE monolith (HA-Fiscal-HANK-SAM-to-python.py) under
HAFISCAL_QE_FIDELITY=1 or HAFISCAL_STEP4_ENGINE=monolith; otherwise runs
the live package engine. The live probe/ruling flags
(HAFISCAL_HANK_SPLURGE / _SPLURGE_BYEDUC / _SS_SOURCE / _MULT_REGIME)
are honored identically by both engines.
"""
import os
import subprocess
import sys

_HA_MODELS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HA_MODELS not in sys.path:
    sys.path.insert(0, _HA_MODELS)

from step4.common import (FPC_DIR, MONOLITH_GE, chdir_fpc,  # noqa: E402
                          monolith_route_reason)


def main():
    reason = monolith_route_reason("ge")
    if reason:
        print(f"[step4-engine] monolith (frozen QE-fidelity engine): {reason}",
              flush=True)
        sys.exit(subprocess.call([sys.executable, MONOLITH_GE], cwd=FPC_DIR))
    print("[step4-engine] package (live fixed-semantics engine)", flush=True)
    chdir_fpc()
    from step4 import ge
    ge.run()


if __name__ == "__main__":
    main()
