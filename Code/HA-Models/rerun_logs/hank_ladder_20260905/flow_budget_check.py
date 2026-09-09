#!/usr/bin/env python
"""Where does the cash land? For each household Jacobian pickle given, print the flow-budget residual
    dA_t - rho*dA_(t-1) + dC_t,   rho = R*LivPrb
row by row for columns 0 and 1 of the transfers and interest-rate Jacobians. A correct column shows the
cash on its delivery row only; an ANTICIPATION row shows a consumption change with zero net cash. This is
the BUG-112 invariant applied to the interest-rate column: the GE feeds the household block the EX-POST
return received at t (ex_post_longbonds_rate), so a column-0 rate shock is a windfall with no earlier date
to anticipate it, and the quarter-0 reaction to a return arriving in quarter 1 belongs to column 1, row 0.
usage: flow_budget_check.py label=path.obj [label=path.obj ...]"""
import pickle, sys
import numpy as np
RHO = 1.01 * (1 - 0.00625)
def budget(JC, JA, s, rows):
    dC, dA = np.asarray(JC)[:, s], np.asarray(JA)[:, s]
    return [dA[t] - RHO * (dA[t - 1] if t else 0.0) + dC[t] for t in range(rows)], dC[:rows]
for arg in sys.argv[1:]:
    label, path = arg.split("=", 1)
    J = pickle.load(open(path, "rb"))
    print(f"== {label}: {path}")
    for inp in ("transfers", "r"):
        if inp not in J["C"]:
            print(f"  {inp}: absent"); continue
        for s in (0, 1):
            res, dC = budget(J["C"][inp], J["A"][inp], s, 4)
            print(f"  {inp:9s} col {s}: cash rows 0..3 = " + " ".join(f"{x:8.4f}" for x in res)
                  + "   dC rows 0..1 = " + " ".join(f"{x:7.4f}" for x in dC[:2]))
