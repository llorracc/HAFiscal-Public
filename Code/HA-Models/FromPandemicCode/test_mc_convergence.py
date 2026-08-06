"""
Test whether MC-P TaxCut actually converges to TM-Q (0.964068) as N grows,
or stays at the N=2000 value (~0.9756).

If MC converges down → TM is correct, MC at N=2000 was noisy/biased.
If MC stays up      → TM has a bug we still need to find.
"""
import sys, os
import numpy as np

_THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS)
sys.path.insert(0, os.path.dirname(_THIS))

from parity_solo_pol_linear import build_solo_pol_economy, mc_multiplier
from AggFiscalModel import DualAggFiscalType
from tm_methods import compute_pLvl_distribution


def main():
    eco_ref, meta = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    u = getattr(eco_ref.agents[0], 'Urate_normal', 0.044)
    g, p = compute_pLvl_distribution(eco_ref.agents[0], n_points=200, unemployment_rate=u)
    tm_Ep = float(np.dot(p, g))

    print("TM-Q (deterministic) reference: 0.964068")
    print()
    print(f"{'N':>7} {'seeds':>6} {'MC mean':>10} {'MC SE':>10} {'gap to TM':>11}")
    print("-" * 50)

    cases = [
        (2000, 10),
        (8000, 10),
        (32000, 5),
    ]
    for N, n_seeds in cases:
        vals = []
        for s in range(n_seeds):
            v = mc_multiplier(eco_ref, "TaxCut", meta, s * 100, N, True, tm_Ep)
            vals.append(v)
        mean = float(np.mean(vals))
        se = float(np.std(vals) / np.sqrt(n_seeds))
        print(f"{N:>7d} {n_seeds:>6d} {mean:10.6f} {se:10.6f} {(mean-0.964068):+11.6f}")


if __name__ == "__main__":
    main()
