"""G8 (partial): the experiment layer's dated paths and cost normalizations.

SST plan 20260830-1710h named G8 (the BUG-091 class: the welfare layer once
solved a 10-quarter tax cut while 8 were delivered) as an unbuilt gate; the
ladder plan carried it as F8. This builds the HANK half: from a production
MULT_DUMP, assert each experiment's COST path has exactly the dated shape and
magnitude its definition states —

  transfers: one quarter, t = 0 only, magnitude 0.05 * C_ss;
  UI_extensions: four quarters, t = 0..3, equal steps (0.2 per quarter times
      the wage*(1-tau)*(U3+U4 mass) coefficient — asserted equal, magnitude
      recorded);
  tax_cut: eight quarters, t = 0..7, equal steps (0.02 * wage * N_ss).

Cross-regime: the cost paths must be identical across taylor/fixed_real
(policy definitions do not depend on the monetary rule). Lumpability (the
experiment-chain half of SST-G8) is CLOSED by the companion
``ssj_ladder/gate_g8_lumpability.py`` (2026-09-02; suite wrapper
``step4/test_g8_lumpability.py``): chain lumpability 0 exactly on every
experiment chain, and the recessionUI pay mask non-measurable exactly at the
window's predicted macro states — the policy's own income boundary.

Usage: python -m ssj_ladder.gate_g8 --dump <mult_dump.pkl> [--ss <ss.pkl>]
(--ss supplies full-precision C_ss from the SS dump for the transfers
magnitude check; a truncated CLI float fails the 1e-12 tier on its own)
Returns 0 on pass; prints one line per check.
"""
import argparse
import pickle
import sys

import numpy as np

CHECKS = {
    "transfers": {"cost_key": "transfers", "quarters": 1},
    "UI_extensions": {"cost_key": "UI_extension_cost", "quarters": 4},
    "tax_cut": {"cost_key": "tax_cost", "quarters": 8},
}


def run(dump_path, C_ss=None, tol=1e-12):
    with open(dump_path, "rb") as f:
        d = pickle.load(f)
    ok = True
    results = {}
    for pol, spec in CHECKS.items():
        rows = {}
        paths = {}
        for reg in ("taylor", "fixed_real"):
            irf = d["irfs"][pol][reg]
            c = np.asarray(irf[spec["cost_key"]], float)
            q = spec["quarters"]
            active = c[:q]
            inactive = c[q:]
            rows[f"{reg}_active_equal_steps"] = bool(
                np.max(np.abs(active - active[0])) <= tol * max(1, abs(active[0])))
            rows[f"{reg}_inactive_zero"] = bool(
                np.max(np.abs(inactive)) <= tol)
            rows[f"{reg}_magnitude"] = float(active[0])
            paths[reg] = c
        rows["cross_regime_identical"] = bool(
            np.array_equal(paths["taylor"], paths["fixed_real"]))
        if pol == "transfers" and C_ss is not None:
            rows["magnitude_is_0.05_C_ss"] = bool(
                abs(rows["taylor_magnitude"] - 0.05 * C_ss)
                <= 1e-12 * max(1, 0.05 * C_ss))
        pol_ok = all(v for k, v in rows.items() if isinstance(v, bool))
        rows["PASS"] = pol_ok
        ok = ok and pol_ok
        results[pol] = rows
        print(f"[g8] {pol}: {'PASS' if pol_ok else 'FAIL'} "
              f"({spec['quarters']}q, mag={rows['taylor_magnitude']:.6f})")
    return ok, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--ss", default=None,
                    help="ss.pkl (HANK_SS_DUMP) supplying full-precision "
                         "C_ss for the transfers magnitude check")
    a = ap.parse_args()
    css = None
    if a.ss:
        with open(a.ss, "rb") as f:
            css = float(pickle.load(f)["household"]["C_ss"])
    ok, _ = run(a.dump, css)
    print(f"[g8] OVERALL: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
