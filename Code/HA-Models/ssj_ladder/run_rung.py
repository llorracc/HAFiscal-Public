"""Run one ladder rung and stamp its verdict JSON.

    python -m ssj_ladder.run_rung A0 [--out DIR] [--quick]

--quick drops the 450-point tier (R gates then SKIP, not PASS). The env is pinned HERE,
before any step4 import — minimal_cell refuses to load otherwise. Cascade-halt is the
caller's job (a rung's verdict file is its precondition's evidence).
"""
import argparse
import hashlib
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rung", choices=["A0", "A1", "A2", "A3", "A3T", "A4"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    # Parameters/EstimParameters read sys.argv at (lazy) import — our CLI args would be
    # misparsed as calibration overrides. The runner owns argv from here.
    sys.argv = [sys.argv[0]]

    from ssj_ladder.rungs import RUNGS
    rung = RUNGS[args.rung]

    # ---- pin the rung env BEFORE any step4 import ----
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
    # abspath BEFORE the step4 imports below — minimal_cell chdirs to FPC
    os.makedirs(out_dir, exist_ok=True)

    from ssj_ladder import gates
    from ssj_ladder import minimal_cell, reference_ssj  # step4 imports happen here

    ladder = rung["ladder"][:2] if args.quick else rung["ladder"]
    t0 = time.time()
    _b4 = {"a1": minimal_cell.build_cell_a1,
           "a2": minimal_cell.build_cell_a1,
           "a3": minimal_cell.build_cell_a3}.get(
               rung.get("builder"), minimal_cell.build_cell)
    _bj = {"a1": reference_ssj.build_cell_a1,
           "a2": reference_ssj.build_cell_a2}.get(
               rung.get("builder"), reference_ssj.build_cell)
    pairs = {}
    for n in ladder:
        print(f"[{args.rung}] building "
              f"{'step4 only' if rung.get('s_only') else 'both engines'} "
              f"at n={n} ...", flush=True)
        d4 = _b4(rung["model"], n,
                 os.path.join(out_dir, f"scratch_jacs_{n}.obj"))
        dj = None if rung.get("s_only") else _bj(rung["model"], n)
        pairs[n] = (d4, dj)
        if dj is None:
            print(f"  A_ss: step4 {d4['A_ss']:.6f}  (S-only)", flush=True)
            continue
        print(f"  A_ss: step4 {d4['A_ss']:.6f}  ssj {dj['A_ss']:.6f}", flush=True)

    verdict = {"rung": args.rung, "title": rung["title"], "stamp": stamp,
               "quick": bool(args.quick),
               "env_fingerprint": {k: os.environ.get(k) for k in rung["env"]},
               "model": rung["model"], "ladder": list(ladder), "gates": {}}
    if rung.get("builder") == "a2":
        # A2 is the CONVENTION-DISCRIMINATION rung (2026-09-02 note; (W)
        # verified in ConsMarkovModel ~1824). Each engine is gated on its
        # OWN derived budget operator — step4 on (W): rho = R*L, Gamma-free;
        # the twin on (P): rho = R/Gamma — and the cross-engine gate is the
        # derived cash ratio step4/twin = LGamma. Entrywise agreement of
        # the two engines' Jacobian matrices is NOT gated (they keep
        # different books; see rung_a2_bridge for how far a units
        # conversion closes that); relgaps are recorded as diagnostics.
        import numpy as np
        m = rung["model"]
        G = m["gamma"]
        rung_P = dict(rung)
        rung_P["model"] = dict(m, R=m["R"] / G)   # s_gates rho -> R/Gamma
        for n in ladder:
            d4, dj = pairs[n]
            verdict["gates"][f"S_step4_W_n{n}"] = gates.s_gates(d4, rung)
            verdict["gates"][f"S_ssj_P_n{n}"] = gates.s_gates(dj, rung_P)
            xr = {}
            for i in rung["income_inputs"]:
                c4 = verdict["gates"][f"S_step4_W_n{n}"][i]["_cash_median"]
                cj = verdict["gates"][f"S_ssj_P_n{n}"][i]["_cash_median"]
                ratio = c4 / (G * cj)
                xr[f"cash_ratio_{i}"] = {
                    "measured": abs(ratio - 1.0),
                    "threshold": rung["a2_gate"]["cash_ratio_rel"],
                    "PASS": bool(abs(ratio - 1.0)
                                 <= rung["a2_gate"]["cash_ratio_rel"]),
                    "_ratio_over_gamma": ratio}
            for i in rung["inputs"]:
                xr[f"_relgap_diag_{i}"] = float(
                    np.linalg.norm(d4[f"C_{i}"] - dj[f"C_{i}"])
                    / np.linalg.norm(dj[f"C_{i}"]))
            verdict["gates"][f"X_derived_n{n}"] = xr
    elif rung.get("s_only"):
        for n in ladder:
            d4, _ = pairs[n]
            verdict["gates"][f"S_step4_n{n}"] = gates.s_gates(d4, rung)
    else:
        for n in ladder:
            d4, dj = pairs[n]
            s4 = gates.s_gates(d4, rung)
            sj = gates.s_gates(dj, rung)
            verdict["gates"][f"S_step4_n{n}"] = s4
            verdict["gates"][f"S_ssj_n{n}"] = sj
            verdict["gates"][f"X_n{n}"] = gates.x_gates(d4, dj, s4, sj, rung, n)
    if rung.get("builder") == "a2":
        verdict["gates"]["R"] = {"SKIPPED": "A2 is a 2-point discrimination "
                                 "rung; convergence is A1's R tier"}
    elif rung.get("s_only"):
        verdict["gates"]["R"] = {"SKIPPED": "A3 is S-only (no twin); "
                                 "convergence owned by A1's R tier"}
    elif len(ladder) >= 3:
        verdict["gates"]["R"] = gates.r_gates(pairs, rung)
    else:
        verdict["gates"]["R"] = {"SKIPPED": "--quick drops the 450-point tier"}

    if rung.get("sst_gates"):
        import subprocess as _sp
        _ha = os.path.join(repo, "Code", "HA-Models")
        _senv = {k: v for k, v in os.environ.items()
                 if not k.startswith("HAFISCAL_")}
        _senv.update({"PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg"})
        for _sst in rung["sst_gates"]:
            _rc = _sp.call([sys.executable, "-m", "pytest", _sst, "-q",
                            "--no-header"], cwd=_ha, env=_senv,
                           stdout=open(os.path.join(
                               out_dir, f"sst_{os.path.basename(_sst)}.log"),
                               "w"),
                           stderr=_sp.STDOUT)
            verdict["gates"][f"sst:{_sst}"] = {
                "measured": _rc, "threshold": 0, "PASS": _rc == 0}

    if rung.get("a4_gate"):
        import json as _json
        _ref = _json.load(open(os.path.join(
            out_dir, rung["a4_gate"]["ref_verdict"])))
        _LG = rung["model"]["livprb"] * rung["model"]["gamma"]
        _a4 = {}
        for n in ladder:
            for i in rung["income_inputs"]:
                c4 = verdict["gates"][f"S_step4_n{n}"][i]["_cash_median"]
                c3 = _ref["gates"][f"S_step4_n{n}"][i]["_cash_median"]
                dev = abs(c4 / (_LG * c3) - 1.0)
                _a4[f"n{n}_{i}"] = {
                    "measured": dev,
                    "threshold": rung["a4_gate"]["cash_ratio_rel"],
                    "PASS": bool(dev <= rung["a4_gate"]["cash_ratio_rel"]),
                    "_ratio_over_LG": c4 / (_LG * c3)}
        verdict["gates"]["cash_scales_by_LGamma"] = _a4

    if rung.get("builder") in ("a1", "a3"):
        # eta, step4 side: the budget identity against the chain-implied dY
        # (an eta shock delivers income at every t >= s — the delivery-row
        # form is the wrong one, in every phase). Uses the ladder's own
        # closed-form chain machinery; SSJ dPi support is probed + recorded.
        import numpy as np
        from ssj_ladder import closed_form
        m = rung["model"]
        Pi_row = minimal_cell._chain6_row(m["EU"], m["jf"])
        chains = dict(jf=m["jf"], shares=[1.0], chains=[Pi_row.T],
                      seps=[m["EU"] / (1.0 - m["jf"])])
        wnet = m["wage_ss"] * (1.0 - m["tau_ss"])
        y6 = [wnet, m["ue_rr"] * wnet, m["ue_rr"] * wnet,
              m["nb_rr"] * wnet, m["nb_rr"] * wnet, m["nb_rr"] * wnet]
        eta_meas = {}
        for n in ladder:
            d4 = pairs[n][0]
            oC = d4["C_eta"]; oA = d4["A_eta"]
            rho = m["R"] * m["livprb"]
            dY_b = np.zeros_like(oC)
            dY_b[0] = oC[0] + oA[0]
            dY_b[1:] = oC[1:] + oA[1:] - rho * oA[:-1]
            T = m["T"]
            UJ = closed_form.build_ujac([Pi_row.T], [1.0],
                                        [closed_form.ergodic(Pi_row.T)], T)
            # (W)-convention delivery: income reaches SURVIVING p-weighted
            # dollars, so the chain-implied path scales by kappa = L*Gamma
            # (identity at L=Gamma=1; at A4 the unscaled gap measured EXACTLY
            # 1-L = 0.00625 -- the derivation confirmed by its own gate).
            _kappa = m["livprb"] * m["gamma"]
            dY_c = _kappa * np.tensordot(np.asarray(y6), UJ, axes=(0, 0))
            eta_meas[f"n{n}"] = {
                "frob_rel_gap": float(np.linalg.norm(dY_b - dY_c)
                                      / np.linalg.norm(dY_c)),
                "threshold": rung["eta_gate"]["provisional_rel"],
            }
            eta_meas[f"n{n}"]["PASS"] = bool(
                eta_meas[f"n{n}"]["frob_rel_gap"]
                <= rung["eta_gate"]["provisional_rel"])
        verdict["gates"]["eta_chain_dy"] = eta_meas
        # dPi probe on the SSJ twin (recorded, never gated)
        try:
            from ssj_ladder import reference_ssj as _rs
            mm = dict(m); mm["T"] = 8
            ss = None
            probe = "not attempted"
            import sequence_jacobian  # noqa
            cell = _rs.build_cell_a1(mm, 30)  # cheap ss
            probe = "jacobian(inputs=['Pi']) raised"
            _rs.hh6.jacobian(_rs.hh6.steady_state(dict(
                beta=m["beta"], r=m["R"] - 1.0, eis=1.0 / m["crra"],
                w=m["wage_ss"], tau=m["tau_ss"], transfers=0.0,
                UI_extend=0.0, UI_rr=0.0,
                ue_lvl=m["ue_rr"] * wnet, nb_lvl=m["nb_rr"] * wnet,
                ext_coef=wnet, emp6=_rs.EMP6, u12=_rs.U12, u34=_rs.U34,
                u345=_rs.U345, Pi=Pi_row,
                a_grid=__import__("sequence_jacobian").grids.asset_grid(
                    0.0, m["a_max"], 30))), inputs=["Pi"], T=8)
            probe = "SUPPORTED: jacobian wrt Pi returned"
        except Exception as e:  # noqa: BLE001
            probe = f"{probe}: {type(e).__name__}: {e}"
        verdict["dPi_probe"] = probe

    try:
        import sequence_jacobian, HARK, numpy
        verdict["versions"] = {"numpy": numpy.__version__,
                               "HARK": getattr(HARK, "__version__", "?"),
                               "sequence_jacobian": "1.0.0 (no __version__ attr)"}
    except Exception:
        pass
    verdict["wall_s"] = round(time.time() - t0, 1)
    verdict["config_hash"] = hashlib.sha256(
        json.dumps({"model": rung["model"], "thresholds": rung["thresholds"],
                    "ladder": list(ladder)}, sort_keys=True).encode()).hexdigest()[:16]

    n_pass, n_fail, failures = gates.summarize(verdict["gates"])
    verdict["summary"] = {"pass": n_pass, "fail": n_fail, "failures": failures,
                          "VERDICT": "PASS" if n_fail == 0 else "FAIL"}

    path = os.path.join(out_dir, f"verdict_{args.rung}_{stamp}.json")
    with open(path, "w") as f:
        json.dump(verdict, f, indent=1, default=float)
    print(f"\n[{args.rung}] {verdict['summary']['VERDICT']}: "
          f"{n_pass} gates pass, {n_fail} fail "
          f"({verdict['wall_s']}s)  -> {path}")
    for fpath in failures:
        print(f"  FAIL {fpath}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
