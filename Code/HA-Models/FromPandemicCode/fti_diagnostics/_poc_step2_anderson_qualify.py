"""DIAGNOSTIC: why does the Step-2 Anderson base-solver opt-in fire (or fall back) on a
real cohort agent? Prints each qualification condition + whether the NAMG solve converges
+ whether economy.solve(HAFISCAL_STEP2_NAMG=1) actually flips agent._step2_namg_used.

Run (from FromPandemicCode/):
  PYTHONPATH=. HAFISCAL_SKIP_ESTIMATION=1 <python> fti_diagnostics/_poc_step2_namg_qualify.py
"""
from __future__ import annotations
import os
import sys
import numpy as np

os.environ.setdefault("HAFISCAL_SKIP_ESTIMATION", "1")
os.environ["HAFISCAL_STEP2_NAMG"] = "1"
os.environ["HAFISCAL_STEP2_NAMG_VERBOSE"] = "1"

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_FROMPANDEMIC, os.path.normpath(os.path.join(_FROMPANDEMIC, ".."))):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def main():
    import EstimAggFiscalMAIN as E
    from AggFiscalModel import AggregateDemandEconomy
    eco = E.AggDemandEconomy
    agents = eco.agents
    print(f"\n{len(agents)} agents; enabled={AggregateDemandEconomy._step2_namg_enabled()}")
    a = agents[-1]  # a College-ish slow atom
    S = np.asarray(a.MrkvArray[0]).shape[0]
    print(f"  S(MrkvArray[0])      = {S}")
    print(f"  num_macro_states     = {getattr(a,'num_macro_states','MISSING')}")
    print(f"  num_base_MrkvStates  = {getattr(a,'num_base_MrkvStates','MISSING')}")
    print(f"  BoroCnstArt          = {np.asarray(a.BoroCnstArt).reshape(-1)[:1]}")
    print(f"  permgrofac_fix_on    = {__import__('_permgrofac').permgrofac_fix_on()}")
    print(f"  len(IncShkDstn[0])   = {len(a.IncShkDstn[0])}")
    print(f"  Rfree[:S]      = {AggregateDemandEconomy._per_state_param(a.Rfree, S)}")
    print(f"  PermGroFac[:S] = {AggregateDemandEconomy._per_state_param(a.PermGroFac, S)}")
    print(f"  raw LivPrb   = {np.asarray(a.LivPrb).reshape(-1)[:8]}")

    print("\nCalling economy.solve() with the flag ON...")
    eco.solve()
    used = [bool(getattr(ag, "_step2_namg_used", False)) for ag in agents]
    print(f"  agents that used Anderson: {sum(used)}/{len(agents)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
