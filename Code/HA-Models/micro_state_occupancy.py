#!/usr/bin/env python3
"""How many households does each source micro state actually hold, per cohort and panel size?

WHY THIS EXISTS (2026-09-08).  The income-strata shuffle assigns transitions per SOURCE MICRO STATE per
AGENT TYPE (``AggFiscalModel`` ``for jj in range(J)``), and ``_mrkv_strata_ids._bins`` refuses to stratify
a state holding fewer than ``2n`` households.  So "is the panel big enough for the strata knob to behave?"
is a question about per-state occupancy inside the SMALLEST cohort, not about ``--agent-count-total``.  The
strata certification ladder compared HS_Only against Baseline without controlling this and the two halves
turned out never to have overlapped: HS_Only is ``DiscFacCount = 1`` with shares ``[0, 1, 0]``, so its whole
N sits in one agent type, while Baseline splits N over 21 types as ``N x share_e / DiscFacCount`` and gives
each dropout cohort 1.33 % of it.

No simulation and no solve is needed: the micro chain's stationary distribution is linear algebra on the
model's own parameters.  ``Parameters.small_MrkvArray(e, u, ub)`` with
``U_persist = 1 - 1/Uspell`` and ``E_persist = 1 - u(1-U_persist)/(1-u)`` (the emp-persist identity), and
``ub = UBspell_normal + Policy_ExtraBenefitQuarters`` (5 under the paper's window, so J = 7 micro states).

Usage:  micro_state_occupancy.py [--regime recession|normal] [--strata 5] [--n 40000 100000] [--json]
"""
import argparse, json, sys

import numpy as np

# Model parameters (EstimParameters.py / Parameters.py); overridable on the command line.
USPELL_NORMAL, USPELL_RECESSION = 1.5, 4.0
URATE_NORMAL = {"dropout": 0.085, "HS": 0.044, "college": 0.027}
RECESSION_URATE_MULT = 2.0                      # Parameters.py:321-323
EDUC_SHARES = {"dropout": 0.093, "HS": 0.527, "college": 0.38}
DISCFAC_COUNT = 7                               # Baseline; HS_Only/Reduced_Run use 1
UB_CHAIN = 4                                    # UBspell_normal(2) + n_extension(2) -> J = 6 under the paper_capped
                                                # policy in force since BUG-122 (2026-09-06); `paper` (pre-fix) had 3 -> J = 7


def small_mrkv_array(e, u, ub=UB_CHAIN):
    """The micro chain of Parameters.small_MrkvArray (transition_ub=True)."""
    M = np.zeros((ub + 2, ub + 2))
    M[0, 0], M[0, 1] = e, 1 - e
    for i in range(1, ub + 1):
        M[i, i + 1], M[i, 0] = u, 1 - u
    M[ub + 1, ub + 1], M[ub + 1, 0] = u, 1 - u
    return M


def stationary(M):
    w, v = np.linalg.eig(M.T)
    p = np.real(v[:, int(np.argmin(abs(w - 1)))])
    return p / p.sum()


def micro_shares(urate, uspell, ub=UB_CHAIN):
    u_persist = 1.0 - 1.0 / uspell
    e_persist = 1.0 - urate * (1.0 - u_persist) / (1.0 - urate)
    return stationary(small_mrkv_array(e_persist, u_persist, ub))


def occupancy(parametrization, cohort, n_total, regime="recession", ub=UB_CHAIN):
    """Households per source micro state for one cohort of one parametrization."""
    urate = URATE_NORMAL[cohort] * (RECESSION_URATE_MULT if regime == "recession" else 1.0)
    uspell = USPELL_RECESSION if regime == "recession" else USPELL_NORMAL
    if parametrization == "HS_Only":
        n_i = n_total                                   # DiscFacCount = 1, shares [0, 1, 0]
    else:
        n_i = int(np.floor(n_total * EDUC_SHARES[cohort] / DISCFAC_COUNT))
    return n_i, micro_shares(urate, uspell, ub) * n_i


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regime", default="recession", choices=("recession", "normal"))
    ap.add_argument("--strata", type=int, default=5, help="income strata per source state (p:<n>)")
    ap.add_argument("--n", type=int, nargs="+", default=[40000, 100000])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ub-chain", type=int, default=UB_CHAIN, help="UBspell_normal + extension states (J = ub + 2)")
    a = ap.parse_args(argv)
    guard = 2 * a.strata                               # _bins refuses below this

    rows = []
    for param, cohorts in (("Baseline", ("dropout", "HS", "college")), ("HS_Only", ("HS",))):
        for cohort in cohorts:
            for n_total in a.n:
                n_i, occ = occupancy(param, cohort, n_total, a.regime, a.ub_chain)
                unemp = occ[1:]
                strat = [o for o in occ if o >= guard]
                rows.append({"parametrization": param, "cohort": cohort, "n_total": n_total, "n_i": n_i,
                             "per_state": [round(float(o), 1) for o in occ],
                             "states_stratified": f"{len(strat)}/{len(occ)}",
                             "min_unemployed_stratum": round(float(min(u for u in unemp) / a.strata), 2)})
    if a.json:
        print(json.dumps(rows, indent=2)); return 0
    print(f"{a.regime} chain, p:{a.strata} (a state below {guard} households is NOT stratified)\n")
    print(f"{'param':9s} {'cohort':8s} {'N_total':>8s} {'N_i':>7s}  per source state"
          f"{'':22s} strat  min unemp stratum")
    for r in rows:
        print(f"{r['parametrization']:9s} {r['cohort']:8s} {r['n_total']:>8,} {r['n_i']:>7,}  "
              + " ".join(f"{o:>6.0f}" for o in r["per_state"])
              + f"  {r['states_stratified']:>5s}  {r['min_unemployed_stratum']:>8.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
