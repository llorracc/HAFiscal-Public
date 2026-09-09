"""The A2 twin ℒΓ-bridge: does the independent sequence_jacobian twin reproduce
the production Jacobians once income growth is on, after a units conversion?

The deferred half of rung A2. Purpose of the twin, stated plainly: it is an
independent reimplementation of the same household block in the external
sequence_jacobian package, kept purely so that agreement between two
unrelated codebases certifies both (nothing in the paper or pipeline
consumes it). The rung certified each engine on its OWN derived budget
operator — step4 on the production (W) survivor-weight measure (ρ = R·ℒ
Γ-free, delivery κ = ℒΓ), the sj twin on the per-capita (P) measure
(ρ = R/Γ at ℒ=1, unit cash) — and gated only the derived cash RATIO (= ℒΓ).
Entry-for-entry agreement of the Jacobian matrices was deferred because the
two keep different books, and reconciling them looked like it would mean
modifying the sequence_jacobian package's internals.

The candidate closed form: substituting J_W[t,s] = α·Γ^{t−s}·J_P[t,s] into
the (W) flow identity reproduces the (P) identity exactly when α = κ_W/κ_P =
ℒΓ — the diagonal conjugation J_W = ℒΓ · D J_P D^{-1}, D = diag(Γ^t). The
identities constrain one combination per column, so the claim is TESTED
entrywise, and the 2026-09-02 measurement SPLIT it:

  BRIDGED (gated here): the broad income columns transfers/w/tau land inside
      rung A1's Γ=1 cross-engine discretization band (bridged relgaps
      0.8–2.3% at n=150 vs tier 4.5%; also under the Euler-matched
      Γ=0.995/β=0.95962 control). Measure conjugation IS the bridge for
      columns carried by interior households — no sj surgery needed there.

  NOT BRIDGEABLE (recorded, signature-guarded): the UI columns. At A2's
      β=0.95 the twin's u3/u4 recipients sit exactly at the borrowing
      constraint — its A_UI_extend is IDENTICALLY zero (≈1e-17), so the
      relgap is 1.0 at any scale and no diagonal transform can move it. The
      (W) engine keeps a genuinely different corner population (the m = 1
      newborn-complement reinjection, present even at LivPrb = 1). The
      residual is corner-REGIME-borne, not complement-sized: halving the
      complement Euler-matched moved C_UI_extend only 0.48 -> 0.42, and at
      Γ=1 (rung A1, patient β so the corner is unpopulated) the same columns
      agreed at 1.3%. Making the twin agree on the UI columns too would
      therefore require adding birth/death machinery to the package's own
      distribution-update step (the ℒΓ survivor weight plus the newborn
      reinjection) — internals it does not expose. The original deferral
      reason, now with its measured boundary; validation-only either way.

  Bonus knife-edge (recorded in the sawtooth-era verdicts): at β=0.95 the
      cell crosses into a FULLY-constrained steady state between Γ=0.99 and
      Γ=0.999 (twin A_ss 0.040 -> 9e-16) — pair any --gamma probe with
      --beta to hold β·R·Γ^{-σ} or the regime flips underneath you.

The r column is excluded as in A2 itself (the twin's r is d/dr_b holding
r_e — a different instrument, not a measure question).

Usage: python -m ssj_ladder.rung_a2_bridge [--out DIR] [--quick]
"""
import argparse
import json
import os
import sys
import time

# A1's Γ=1 cross-engine thresholds (rungs.A1 X tier) — the yardstick.
BRIDGE_TIER = {50: 0.63, 150: 0.045}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--gamma", type=float, default=None,
                    help="override the A2 model's Gamma (the newborn-complement "
                         "scaling control: the UI-column residual should shrink "
                         "with 1 - LGamma)")
    ap.add_argument("--beta", type=float, default=None,
                    help="override beta (pair with --gamma to hold the Euler "
                         "factor beta*R*Gamma^-sigma fixed while varying the "
                         "complement; an unpaired Gamma change can cross the "
                         "fully-constrained regime boundary instead — measured "
                         "at Gamma=0.999/beta=0.95: twin A_ss = 9e-16)")
    args = ap.parse_args()
    sys.argv = [sys.argv[0]]          # Parameters reads argv at import (BUG-114)

    from ssj_ladder.rungs import RUNGS
    rung = RUNGS["A2"]
    for k, v in rung["env"].items():
        os.environ[k] = v
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    for k, rel in (("HAFISCAL_DISCFAC_FILE",
                    "Code/HA-Models/rerun_logs/chain_D_20260829/DiscFacEstim_CRRA_2.0_R_1.01_chainD.txt"),
                   ("HAFISCAL_SPLURGE_FILE",
                    "Code/HA-Models/rerun_logs/chain_D_20260829/Result_AllTarget_ESC_chainD.txt")):
        p = os.path.join(repo, rel)
        if os.path.exists(p):
            os.environ.setdefault(k, p)
    for cand in ("/home/shared/github/llorracc/fast-time-iteration",):
        if os.path.isdir(cand):
            os.environ.setdefault("HAFISCAL_FTI_REPO", cand)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.abspath(args.out) if args.out else os.path.join(
        repo, "Code", "HA-Models", "rerun_logs", f"ssj_ladder_{stamp[:8]}")
    os.makedirs(out_dir, exist_ok=True)

    import numpy as np
    from ssj_ladder import minimal_cell, reference_ssj

    m = dict(rung["model"])
    if args.gamma is not None:
        m["gamma"] = float(args.gamma)
    if args.beta is not None:
        m["beta"] = float(args.beta)
    G = float(m["gamma"])
    L = float(m.get("livprb", 1.0))
    alpha = L * G
    ladder = rung["ladder"][:1] if args.quick else rung["ladder"]
    verdict = {"rung": "A2-bridge", "stamp": stamp, "model": m,
               "alpha_LGamma": alpha, "ladder": list(ladder), "gates": {},
               "ok": True}

    for n in ladder:
        print(f"[A2-bridge] building both engines at n={n} ...", flush=True)
        d4 = minimal_cell.build_cell_a1(
            m, n, os.path.join(out_dir, f"bridge_scratch_jacs_{n}.obj"))
        dj = reference_ssj.build_cell_a2(m, n)
        T = np.asarray(d4["C_transfers"]).shape[0]
        conj = alpha * G ** np.subtract.outer(np.arange(T), np.arange(T))
        tier = BRIDGE_TIER.get(n, 0.045)
        g = {"A_ss_step4": d4["A_ss"], "A_ss_twin": dj["A_ss"],
             "A_ss_ratio": d4["A_ss"] / dj["A_ss"], "tier": tier}
        BRIDGED_INPUTS = ("transfers", "w", "tau")     # interior-household columns
        for i in rung["income_inputs"]:
            gated = i in BRIDGED_INPUTS
            for blk in ("C", "A"):
                JW = np.asarray(d4[f"{blk}_{i}"], float)
                JP = np.asarray(dj[f"{blk}_{i}"], float)
                raw = float(np.linalg.norm(JW - JP) / np.linalg.norm(JW))
                bridged = float(np.linalg.norm(JW - conj * JP)
                                / np.linalg.norm(JW))
                ok = (bridged <= tier) if gated else True
                g[f"{blk}_{i}"] = {"raw_relgap": raw,
                                   "bridged_relgap": bridged,
                                   "threshold": tier if gated else None,
                                   "gated": gated, "PASS": bool(ok)}
                if not ok:
                    verdict["ok"] = False
                lab = ("PASS" if bridged <= tier else "FAIL") if gated                     else "diag"
                print(f"  n={n} {blk}_{i:>10}: raw {raw:8.4f} -> bridged "
                      f"{bridged:.4e}  {lab}", flush=True)
        # the corner-regime signature that makes the UI columns unbridgeable:
        # the twin's A_UI_extend is identically zero (its u34 mass is AT the
        # constraint). Guarded so the recorded diagnosis stays true.
        tw_a_ui = float(np.abs(np.asarray(dj["A_UI_extend"], float)).max())
        g["twin_A_UI_extend_absmax"] = tw_a_ui
        g["corner_signature"] = bool(tw_a_ui <= 1e-10)
        if not g["corner_signature"]:
            verdict["ok"] = False
            print(f"  n={n} corner signature BROKEN: twin |A_UI_extend| = "
                  f"{tw_a_ui:.3e} (diagnosis needs re-examination)", flush=True)
        verdict["gates"][f"n{n}"] = g

    print(f"[A2-bridge] VERDICT: {'PASS' if verdict['ok'] else 'FAIL'}",
          flush=True)
    out = os.path.join(out_dir, f"verdict_A2bridge_{stamp}.json")
    with open(out, "w") as f:
        json.dump(verdict, f, indent=1)
    print(f"[A2-bridge] wrote {out}", flush=True)
    raise SystemExit(0 if verdict["ok"] else 1)


if __name__ == "__main__":
    main()
