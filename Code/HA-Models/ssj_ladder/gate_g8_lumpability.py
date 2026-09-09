"""G8, the lumpability half: the D4 lumping tested on the EXPERIMENT chains.

SST plan 20260830-1710h, row D4/G8: `normalize_to_hank_states` asserts the
7 -> 6 lumping of the PE employment chain row-for-row, but only for the BASE
scenario chain; the experiment chains (recession, recessionUI, recessionCheck,
recessionTaxCut — the macro-state CondMrkvArrays) were unchecked. This gate
closes that half with a measurement in two parts, per education group and per
macro state:

  CHAIN lumpability — under the same merge partition the base lumping uses
      (micro states n-1..k-1 into the single HANK tail), the merged rows must
      coincide after the column collapse. Expected to PASS everywhere: under
      the calendar encoding the experiment chains are the PLAIN advancing
      chains (the window policy delivers the extension in INCOME, not in the
      transition structure), and both merged states send their non-exit mass
      inside the merged block.

  PAY measurability — the recessionUI extension-pay mask must be CONSTANT on
      each merged block for a 6-state income instrument to represent it. The
      merged block is {e_last, terminal} (micro {5, 6} under calendar/window),
      and e_last IS paid at experiment periods t in [t_enact + (n_ext - 1),
      t_end] while the terminal never is — so measurability FAILS exactly
      there, BY THE POLICY'S DESIGN. The gate pins that boundary: the
      non-measurable set must equal the predicted window set exactly, else it
      trips (an encoding/window semantics change).

The verdict this documents: the D4 reconciliation's scope is the base chain
plus the experiment DYNAMICS; the experiment INCOME layer is not exactly
lumpable to 6 states during the window's tail quarters, which is why the HANK
books its UI arm on its own U3/U4 instrument rather than consuming a lumped
PE chain (a design difference, not a defect — visible as HANK-UI > PE-UI in
the multipliers comparison).

Usage: python -m ssj_ladder.gate_g8_lumpability [--json out.json]
Exit 0 iff every chain row passes AND the non-measurable set matches the
prediction for the resolved window, in every education group.
"""
import argparse
import json
import os
import sys

import numpy as np

CHAIN_TOL = 1e-9          # merged rows are computed from the same floats; ~exact
SHOCKS = ("base", "recession", "recessionUI", "recessionCheck", "recessionTaxCut")


def collapse_cols(m, n):
    """Column-collapse a k-state row-stochastic matrix onto n states (tail summed)."""
    k = m.shape[0]
    out = np.empty((k, n))
    out[:, : n - 1] = m[:, : n - 1]
    out[:, n - 1] = m[:, n - 1 :].sum(axis=1)
    return out


def chain_lumpability_dev(m, n):
    """Max deviation among the merged rows after column collapse (0 if k <= n)."""
    k = m.shape[0]
    if k <= n:
        return 0.0
    c = collapse_cols(np.asarray(m, float), n)
    tail = c[n - 1]
    return float(max(np.max(np.abs(c[r] - tail)) for r in range(n, k)))


def run(json_out=None):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if here not in sys.path:
        sys.path.insert(0, here)
    from step4.common import chdir_fpc
    chdir_fpc()
    from step4.pe_anchor_gate import pe_side
    from step4.hh_setup import states as HANK_N
    import ui_extension_rule as uer

    encoding = os.environ.get("HAFISCAL_UI_STATE_ENCODING", "calendar").strip().lower()
    pe = pe_side()
    verdict = {"encoding": encoding, "hank_n": int(HANK_N), "groups": [], "ok": True}

    for e, (agent, init) in enumerate(zip(pe["agents"], pe["inits"])):
        ub_n = int(init["UBspell_normal"])
        ub_x = int(getattr(agent, "UBspell_extended", init.get("UBspell_extended", ub_n + 3)))
        window = None
        if encoding == "calendar":
            window = uer.resolve_window(
                os.environ.get("HAFISCAL_UI_EXTENSION_POLICY", "window"), ub_n, ub_x)
        g = {"educ": e, "UBspell_normal": ub_n, "UBspell_extended": ub_x,
             "window": window._asdict() if window else None, "shocks": {}}

        for shock in SHOCKS:
            agent.update_mrkv_array(shock)
            conds = [np.asarray(c, float) for c in agent.CondMrkvArrays]
            k = conds[0].shape[0]
            devs = [chain_lumpability_dev(c, HANK_N) for c in conds]
            chain_ok = max(devs) <= CHAIN_TOL
            row = {"macro_states": len(conds), "k": int(k),
                   "chain_max_dev": float(max(devs)), "chain_ok": bool(chain_ok)}

            if shock == "recessionUI" and k > HANK_N:
                # measurability: the pay mask constant on the merged block {n-1..k-1}
                n_ext = window.n_extension if window else 0
                nonmeas = []
                for m_idx in range(len(conds)):
                    mask = uer.extension_pay_mask(
                        encoding, m_idx, np.arange(k), ub_n, n_ext, window)
                    blk = np.asarray(mask).ravel()[HANK_N - 1 :]
                    if blk.size and not (blk.all() or not blk.any()):
                        nonmeas.append(m_idx)
                # prediction: e_last (j = n_ext, the one extension state inside the
                # merged block) is paid iff t_enact + (n_ext - 1) <= t <= t_end
                pred = []
                if window is not None:
                    j_last = n_ext                      # micro ub_n + n_ext = k - 2... the deepest ext state
                    if ub_n + j_last >= HANK_N - 1:     # it sits inside the merged block
                        shift = (j_last - 1) if window.entry == "continuation" else 0
                        for m_idx in range(len(conds)):
                            t = int(uer.experiment_period(m_idx))
                            if window.t_enact + shift <= t <= window.t_end:
                                pred.append(m_idx)
                row["pay_nonmeasurable_macro"] = nonmeas
                row["pay_predicted_macro"] = pred
                row["pay_boundary_as_predicted"] = bool(nonmeas == pred)
                if not row["pay_boundary_as_predicted"]:
                    verdict["ok"] = False
            if not chain_ok:
                verdict["ok"] = False
            g["shocks"][shock] = row
            extra = ""
            if "pay_nonmeasurable_macro" in row:
                extra = (f"  pay-nonmeasurable macro={row['pay_nonmeasurable_macro']}"
                         f" predicted={row['pay_predicted_macro']}"
                         f" {'MATCH' if row['pay_boundary_as_predicted'] else 'MISMATCH'}")
            print(f"[g8-lump] educ={e} {shock:>15}: {len(conds):>2} macro x {k} states, "
                  f"chain max dev {max(devs):.2e} {'PASS' if chain_ok else 'FAIL'}{extra}",
                  flush=True)
        verdict["groups"].append(g)

    print(f"[g8-lump] VERDICT: {'PASS' if verdict['ok'] else 'FAIL'}", flush=True)
    if json_out:
        with open(json_out, "w") as f:
            json.dump(verdict, f, indent=1)
        print(f"[g8-lump] wrote {json_out}", flush=True)
    return verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    v = run(a.json or None)
    raise SystemExit(0 if v["ok"] else 1)


if __name__ == "__main__":
    main()
