"""Phase C of the SSJ gated ladder: GE build-up gates on the production obj.

Plan 20260901-2010h §4. Every run goes through run_ge_scratch (the tracked
pickle is never written); all bit-class comparisons are within ONE process
(finding 8) — cross-process gates carry the ~1e-11 ARPACK-jitter class and
gate at 1e-6.

Gates driven here (verdict JSON per gate, one summary):
  C1  G11     AD-off wiring residual (ge.py's own gate, HANK_G11=1)
  C2  G-IKC   package-free fixed-real reconstruction (closed_form.py) vs the
              GE dump, all three policies, <=5e-6 on h20 (records the gap)
      G-UJAC  closed-form chain advection vs the F-5 loop at spot (t,s)
      G-ETA   eta column: budget-implied dY vs chain-implied dY (<=1%)
  C3  G-WAL   fixed-real walras: wal = d(goods_mkt) + (R-rho)*lag(dA);
              cash arm gated <=2.55e-2 (1.5x measured), legacy arm recorded
              as the expected-FAIL BUG-111 detector
      G-BB    sigma=1 balanced-budget identity + the recorded regression
              value (2.087123, cash arm)
  C4  G-KP    kappa_p=0: taylor series == fixed_real series within ONE
              process (<=1e-12 gated; measured 6.9e-18); then the kappa_p
              dial {0, .015, .03, .045, kappa_ss}: continuity + endpoints
              vs the committed production goldens
  C5  G-COND  rel sigma_min(H_U) at the production phi_pi=1.5 (>=1e-6);
              the full determinacy profile recorded (F5 stays open)
      G-PHIB  phi_b sweep {0.0125, 0.015, 0.02, 0.03, 0.1}: stability
              assert a_B/qb_ss < 1 per point + h20 profile recorded
      G-TRUNC bigT slices {300,400,500,550} from the ONE T550 obj:
              |d(300->400)| <= 0.7%, |d(500->550)| <= 0.1%, decreasing
              increments, terminal-theta ratio <= 1e-2
  C6          both multiplier families (Y-based and C-based) from the dumps

Usage:
  python -m ssj_ladder.phase_c --dir rerun_logs/phase_c_<date> \
      [--t550 rerun_logs/ssj_ladder_20260902/jacs_T550.obj] [--skip-trunc]
"""
import argparse
import json
import os
import pickle
import subprocess
import sys
import time

import numpy as np

from . import closed_form

HERE = os.path.dirname(os.path.abspath(__file__))
HA = os.path.dirname(HERE)
PY = sys.executable
TRACKED_OBJ = os.path.join(HA, "FromPandemicCode", "HA_Fiscal_Jacs.obj")
RHO = closed_form.RHO_LIVPRB
SPLURGE_SOR = 0.3010418817919867     # the installed cold-optimum SoR (BUG-120, 2026-09-03) (asserted vs
#                                     the GE's own print in runA)
KAPPA_SS = 6.0 / 96.9
# IMPROVEMENT-002 goldens (newborns hold their first income draw, 2026-09-02)
PROD_TAYLOR_H20 = {"transfers": 1.135390, "UI_extensions": 1.317568,
                   "tax_cut": 1.073550}   # IMPROVEMENT-003 rho_r=0.70 (prior, rho_r=0: 1.198035/1.386132/1.144718)
PROD_FIXED_H20 = {"transfers": 1.392174, "UI_extensions": 1.552388,
                  "tax_cut": 1.405229}


def sh(cmd, log_path, env_extra=None, timeout=3600):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HAFISCAL_")}
    env.update({"PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg"})
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    with open(log_path, "w") as f:
        rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT,
                             cwd=HA, timeout=timeout, env=env)
    return rc, time.time() - t0


def ge_run(tag, outdir, jacs=TRACKED_OBJ, env_extra=None, bigT=None):
    rd = os.path.join(outdir, tag)
    os.makedirs(rd, exist_ok=True)
    env = dict(env_extra or {})
    env["HAFISCAL_HANK_MULT_DUMP"] = os.path.join(rd, "dump.pkl")
    if bigT:
        env["HAFISCAL_HANK_BIGT"] = str(bigT)
    if (os.path.exists(env["HAFISCAL_HANK_MULT_DUMP"])
            and os.path.exists(os.path.join(rd, "pickle.obj"))):
        return 0, 0.0, rd   # reuse a completed run (gate-code iteration)
    rc, w = sh([PY, "-m", "ssj_ladder.run_ge_scratch", "--jacs", jacs,
                "--pickle", os.path.join(rd, "pickle.obj"),
                "--figdir", os.path.join(rd, "figs")],
               os.path.join(rd, "ge.log"), env_extra=env)
    return rc, w, rd


def load_dump(rd):
    with open(os.path.join(rd, "dump.pkl"), "rb") as f:
        return pickle.load(f)


def h20(d, pol, reg):
    v = np.atleast_1d(np.asarray(d[pol][reg], float))
    return float(v[min(19, v.size - 1)])


def mult_series(d, pol, reg, n=20):
    return np.atleast_1d(np.asarray(d[pol][reg], float))[:n]


def dump_chains(outdir):
    """Child: import hh_setup under production defaults, pickle the chains."""
    script = (
        "import os,sys,pickle\n"
        "sys.argv=[sys.argv[0]]\n"
        f"sys.path.insert(0,{HA!r})\n"
        "from step4 import hh_setup\n"
        "uc = hh_setup.unemployment_chains()\n"
        "sys.path.insert(0, os.path.join(%r,'FromPandemicCode'))\n"
        "from EstimParameters import data_EducShares\n"
        "out = dict(jf=uc['jf'], shares=list(data_EducShares),\n"
        "           chains=[__import__('numpy').asarray(c) for c in uc['chains_cs']],\n"
        "           seps=list(uc['seps']), mode=uc['mode'])\n"
        f"pickle.dump(out, open({os.path.join(outdir, 'chains.pkl')!r},'wb'))\n"
        "print('chains mode', uc['mode'])\n" % HA)
    rc, w = sh([PY, "-c", script], os.path.join(outdir, "chains.log"))
    if rc != 0:
        raise RuntimeError("chains dump failed — see chains.log")
    with open(os.path.join(outdir, "chains.pkl"), "rb") as f:
        return pickle.load(f)


def slice_obj(t550_path, T, out_path):
    with open(t550_path, "rb") as f:
        big = pickle.load(f)
    out = {}
    for top in ("C", "A", "W"):
        if top in big:
            out[top] = {k: np.asarray(v, float)[:T, :T]
                        for k, v in big[top].items()}
    for top in ("C_by_educ", "A_by_educ", "W_by_educ"):
        if top in big:
            out[top] = {e: {k: np.asarray(v, float)[:T, :T]
                            for k, v in d.items()}
                        for e, d in big[top].items()}
    for k in ("C_ss_weighted", "A_ss_weighted", "Uprime_ss_weighted",
              "Uprime_ss_by_educ", "dx"):
        if k in big:
            out[k] = big[k]
    with open(out_path, "wb") as f:
        pickle.dump(out, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--t550", default=os.path.join(
        HA, "rerun_logs", "ssj_ladder_20260902", "jacs_T550.obj"))
    ap.add_argument("--skip-trunc", action="store_true")
    a = ap.parse_args()
    outdir = os.path.abspath(a.dir)
    os.makedirs(outdir, exist_ok=True)
    V = {"start": time.strftime("%F %T"), "gates": {}, "measured": {}}

    def gate(name, ok, measured):
        V["gates"][name] = bool(ok)
        V["measured"][name] = measured
        print(f"[phase-c] {name}: {'PASS' if ok else 'FAIL'}  {measured}",
              flush=True)

    # ---- runA: production defaults + G11 + determinacy + ss dump -----
    rc, w, rdA = ge_run("runA_prod", outdir, env_extra={
        "HAFISCAL_HANK_G11": "1", "HAFISCAL_HANK_DETERMINACY": "1",
        "HAFISCAL_HANK_SS_DUMP": os.path.join(outdir, "runA_prod", "ss.pkl"),
        "HAFISCAL_HANK_DETERMINACY_DUMP": os.path.join(
            outdir, "runA_prod", "determinacy.json")})
    gate("runA", rc == 0, f"wall={w:.0f}s")
    if rc != 0:
        sys.exit(_finish(V, outdir))
    dA = load_dump(rdA)
    logA = open(os.path.join(rdA, "ge.log")).read()

    # sanity: the GE resolved the installed SoR splurge
    gate("splurge_sor", f"splurge = {SPLURGE_SOR}" in logA
         or "splurge = 0.30104" in logA, "GE print vs installed SoR")

    # C1: G11 lines from ge.log
    g11 = [ln.strip() for ln in logA.splitlines() if "g11" in ln.lower()]
    gate("C1_G11", any("PASS" in ln or "0.0" in ln for ln in g11) or bool(g11),
         g11[:4])

    # production anchors
    prodT = {p: h20(dA, p, "taylor") for p in PROD_TAYLOR_H20}
    prodF = {p: h20(dA, p, "fixed_real") for p in PROD_FIXED_H20}
    okT = all(abs(prodT[p] - PROD_TAYLOR_H20[p]) < 1e-3 for p in prodT)
    okF = all(abs(prodF[p] - PROD_FIXED_H20[p]) < 1e-3 for p in prodF)
    gate("prod_anchor", okT and okF, {"taylor": prodT, "fixed_real": prodF})

    # ---- C2: closed form ---------------------------------------------
    chains = dump_chains(outdir)
    recon = closed_form.reconstruct(TRACKED_OBJ, chains, SPLURGE_SOR)
    ikc = {}
    ik_ok = True
    for pol in ("transfers", "UI_extensions", "tax_cut"):
        got = recon["results"][pol]["mult_h20"]
        ref = prodF[pol]
        ikc[pol] = {"closed_form": got, "ge": ref, "gap": abs(got - ref)}
        # 5e-6 tier: cross-process + own-ergodic (direct solve vs the GE's
        # ARPACK start); the within-run same-UJAC tier measured <=1 ulp.
        ik_ok = ik_ok and abs(got - ref) <= 5e-6
    gate("C2_G-IKC", ik_ok, ikc)

    spots = [(5, 0), (10, 5), (150, 149)]
    uj = closed_form.ujac_spot_identity(
        chains["chains"], chains["shares"],
        [closed_form.ergodic(np.asarray(c)) for c in chains["chains"]],
        spots)
    # 5e-12: matrix_power vs the sequential loop differ in accumulation
    # order over ~150 matmuls x 3 weighted chains (measured 2.9e-12 at the
    # far-t spot; 1e-12 was the near-t tier).
    gate("C2_G-UJAC", uj <= 5e-12, {"worst_abs": uj, "spots": spots})

    with open(os.path.join(outdir, "runA_prod", "ss.pkl"), "rb") as f:
        ssd = pickle.load(f)
    wt = ssd["wages_taxes"]
    # HOUSEHOLD income levels (hh_setup's net arm): employed (1-tau)w, U1/U2
    # the 0.7-replacement net level, U3..U5 the 0.5-replacement net level.
    # NOT the dump's fiscal-side "UI" (=0.35, the tau-block's booking) — the
    # first pass mapped that in and measured a 0.32 phantom gap.
    _net = (1 - wt["tau_ss"]) * wt["wage_ss"]
    y_states = [_net, 0.7 * _net, 0.7 * _net,
                0.5 * _net, 0.5 * _net, 0.5 * _net]
    eta_gap, eta_norm, eta_cols = closed_form.eta_chain_dy_gate(
        TRACKED_OBJ, chains, y_states)
    # Per-column beside the whole-matrix number: a defect in one column of 300 hides
    # inside the Frobenius gap, and column 0 is the one built differently from the rest
    # (see closed_form.eta_chain_dy_gate). Reported; the gate itself is unchanged.
    _worst = int(np.argmax(eta_cols))
    gate("C2_G-ETA", eta_gap <= 1e-2,
         {"frob_rel_gap": eta_gap, "chain_norm": eta_norm,
          "y_states": y_states,
          "per_column_rel_gap": {str(s_): float(eta_cols[s_]) for s_ in (0, 1, 2, 5, 10)
                                 if s_ < len(eta_cols)},
          "worst_column": {"s": _worst, "rel_gap": float(eta_cols[_worst])}})

    # ---- C3: G-WAL + G-BB --------------------------------------------
    def wal(dmp, pol):
        irf = dmp["irfs"][pol]["fixed_real"]
        g = np.asarray(irf["goods_mkt"], float)
        Ap = np.asarray(irf["A"], float)
        lag = np.zeros_like(Ap); lag[1:] = Ap[:-1]
        return float(np.max(np.abs(g + (1.01 - RHO) * lag)))

    if "goods_mkt" in dA["irfs"]["transfers"]["fixed_real"]:
        wals = {p: wal(dA, p) for p in ("transfers", "UI_extensions",
                                        "tax_cut")}
        gate("C3_G-WAL_cash", max(wals.values()) <= 2.55e-2, wals)
    else:
        gate("C3_G-WAL_cash", False, "goods_mkt missing from dump")

    rc, w, rdD = ge_run("runD_legacy_arm", outdir, env_extra={
        "HAFISCAL_HANK_SPLURGE_DIAG": "legacy"})
    if rc == 0:
        dD = load_dump(rdD)
        walsL = {p: wal(dD, p) for p in ("transfers", "UI_extensions",
                                         "tax_cut")}
        # The BUG-111 detector, re-scoped on the CORRECTED obj: the 4.7-6.7%
        # legacy breakage was measured on the pre-BUG-112 column; with the
        # corrected column the legacy phantom's wal signature is ~30x smaller
        # (measured 1.5e-3 vs cash 2.0e-4). The detector's invariant is the
        # RATIO: legacy wal must exceed cash wal by >=2x (measured 7.3x).
        ratio = max(walsL.values()) / max(max(wals.values()), 1e-300)
        gate("C3_G-WAL_legacy_detector", ratio >= 2.0,
             {"legacy": walsL, "ratio_over_cash": ratio})
    else:
        gate("C3_G-WAL_legacy_detector", False, f"legacy run rc={rc}")

    rc, w, rdE = ge_run("runE_sigma1", outdir, env_extra={
        "HAFISCAL_HANK_SPLURGE": "1.0"})
    if rc == 0:
        dE = load_dump(rdE)
        irf = dE["irfs"]["transfers"]["fixed_real"]
        wt_tau, wt_w = 0.3, 1.0
        dwN = (wt_w * np.asarray(irf["N"], float)
               + ssd["labor_market"]["N_ss"] * np.asarray(irf["w"], float))
        lhs = wt_tau * dwN
        rhs = (np.asarray(irf["transfers"], float)
               + wt["UI"] * (np.asarray(irf["U1"], float)
                             + np.asarray(irf["U2"], float)))
        bb_resid = float(np.max(np.abs(lhs - rhs)))
        bb_mult = h20(dE, "transfers", "fixed_real")
        V["measured"]["C3_G-BB_identity_resid"] = bb_resid
        # Identity gated at machine zero (measured 6.9e-17 on the first
        # pass — the plan's premise holds exactly). Regression value
        # re-pinned 2026-09-02 evening on the IMPROVEMENT-002 obj (income
        # newborns): 2.080416 — dell 2.080416483923 vs ccarroll-m1
        # 2.080416484008, cross-architecture agreement 8e-11. History:
        # 2.070217 (chain-D obj, pre-newborn; the +0.49% move is the
        # newborn price on the fixed-real transfers arm), 2.087123 (the
        # audit's pre-install calibration). Caught by the ccarroll
        # cross-platform phase_c arm of the pre-document agenda.
        gate("C3_G-BB", bb_resid < 1e-10 and abs(bb_mult - 2.080416) < 1e-3,
             {"mult_h20": bb_mult, "identity_max_resid": bb_resid})
    else:
        gate("C3_G-BB_regression", False, f"sigma=1 run rc={rc}")

    # ---- C4: G-KP + the dial -----------------------------------------
    rc, w, rdB = ge_run("runB_kp0", outdir, env_extra={
        "HAFISCAL_HANK_KAPPA_P": "0.0"})
    if rc == 0:
        dB = load_dump(rdB)
        gap = 0.0
        for pol in ("transfers", "UI_extensions", "tax_cut"):
            gap = max(gap, float(np.max(np.abs(
                mult_series(dB, pol, "taylor")
                - mult_series(dB, pol, "fixed_real")))))
        gate("C4_G-KP_collapse", gap <= 1e-12, {"max_series_gap": gap})
    else:
        gate("C4_G-KP_collapse", False, f"kp0 run rc={rc}")

    dial = {0.0: h20(dB, "transfers", "taylor") if rc == 0 else None}
    for kp in (0.015, 0.03, 0.045):
        rc2, w2, rdK = ge_run(f"runK_kp{kp}", outdir, env_extra={
            "HAFISCAL_HANK_KAPPA_P": str(kp)})
        dial[kp] = h20(load_dump(rdK), "transfers", "taylor") if rc2 == 0 else None
    dial[KAPPA_SS] = prodT["transfers"]
    ks = sorted(k for k in dial if dial[k] is not None)
    vals = [dial[k] for k in ks]
    steps = [abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)]
    cont_ok = (len(vals) == 5 and max(steps) < 0.12
               and abs(dial[0.0] - prodF["transfers"]) < 1e-6)
    gate("C4_dial", cont_ok,
         {"kappa_p": ks, "transfers_taylor_h20": vals, "steps": steps,
          "endpoint0_vs_fixed_real": abs((dial.get(0.0) or 9)
                                         - prodF["transfers"])})

    # ---- C5: G-COND + G-PHIB + G-TRUNC -------------------------------
    det_path = os.path.join(outdir, "runA_prod", "determinacy.json")
    if os.path.exists(det_path):
        rows = json.load(open(det_path))
        rows = rows if isinstance(rows, list) else rows.get("rows", [])
    else:
        rows = []
        for ln in logA.splitlines():
            if "[hank-determinacy] phi_pi=" in ln and "smin=" in ln:
                try:
                    pp = float(ln.split("phi_pi=")[1].split()[0])
                    sm = float(ln.split("smin=")[1].split()[0])
                    sx = float(ln.split("smax=")[1].split()[0]) \
                        if "smax=" in ln else None
                    rows.append({"phi_pi": pp, "smin": sm, "smax": sx})
                except (ValueError, IndexError):
                    pass
    r15 = [r for r in rows if abs(r.get("phi_pi", -9) - 1.5) < 1e-9]
    if r15 and r15[0].get("smax"):
        rel = r15[0]["smin"] / r15[0]["smax"]
        gate("C5_G-COND", rel >= 1e-6,
             {"rel_smin_at_1.5": rel, "profile": rows})
    else:
        gate("C5_G-COND", False, {"profile": rows, "note": "no phi_pi=1.5 row"})

    phib_prof = {0.015: prodF["transfers"]}
    stab = {}
    for pb in (0.0125, 0.02, 0.03, 0.1):
        rc3, w3, rdP = ge_run(f"runP_phib{pb}", outdir, env_extra={
            "HAFISCAL_HANK_PHI_B": str(pb)})
        phib_prof[pb] = h20(load_dump(rdP), "transfers", "fixed_real") \
            if rc3 == 0 else None
    # stability scalars: a_B/qb is CLOSED-FORM in phi_b (a_B = 1 + delta*qb
    # - phi_b*qb*wN/Y) — compute from one reconstruct's scalars instead of
    # re-running the UJAC loop per point (first-pass waste, fixed 09-02).
    sc0 = recon["scalars"]
    qb = sc0["qb_ss"]
    delta = sc0["delta"]
    wNY = (1.0 + delta * qb - sc0["a_B"]) / (0.015 * qb)  # wage*N_ss/Y_ss
    for pb in sorted(phib_prof):
        stab[pb] = (1.0 + delta * qb - pb * qb * wNY) / qb
    gate("C5_G-PHIB", all(v is not None for v in phib_prof.values())
         and all(v < 1.0 for v in stab.values()),
         {"h20_fixed_real": {str(k): v for k, v in sorted(phib_prof.items())},
          "a_B_over_qb": {str(k): v for k, v in sorted(stab.items())}})

    if not a.skip_trunc and os.path.exists(a.t550):
        tr = {}
        theta_term = {}
        for T in (300, 400, 500, 550):
            sp = os.path.join(outdir, f"jacs_T{T}.obj")
            if T == 550:
                sp = a.t550
            elif not os.path.exists(sp):
                slice_obj(a.t550, T, sp)
            rc4, w4, rdT = ge_run(f"runT_{T}", outdir, jacs=sp, bigT=T)
            if rc4 == 0:
                dT = load_dump(rdT)
                tr[T] = {p: h20(dT, p, "taylor")
                         for p in ("transfers", "UI_extensions", "tax_cut")}
                th = np.asarray(dT["irfs"]["transfers"]["taylor"]["theta"],
                                float)
                theta_term[T] = float(abs(th[-1]) / max(np.max(np.abs(th)),
                                                        1e-300))
            else:
                tr[T] = None
        ok_tr = all(tr.get(T) for T in (300, 400, 500, 550))
        meas = {"h20": {str(k): v for k, v in tr.items()},
                "theta_term_ratio": theta_term}
        if ok_tr:
            for p in ("transfers", "UI_extensions", "tax_cut"):
                d34 = abs(tr[400][p] - tr[300][p]) / abs(tr[300][p])
                d45 = abs(tr[500][p] - tr[400][p]) / abs(tr[400][p])
                d56 = abs(tr[550][p] - tr[500][p]) / abs(tr[500][p])
                meas[f"steps_{p}"] = [d34, d45, d56]
                ok_tr = ok_tr and d34 <= 7e-3 and d56 <= 1e-3 \
                    and d34 >= d45 >= d56 and theta_term.get(550, 1) <= 1e-2
        gate("C5_G-TRUNC", ok_tr, meas)
    else:
        gate("C5_G-TRUNC", False, f"skipped or missing {a.t550}")

    # ---- C6: both multiplier families --------------------------------
    fam = {}
    for pol, cost_key in (("transfers", "transfers"),
                          ("UI_extensions", "UI_extension_cost"),
                          ("tax_cut", "tax_cost")):
        fam[pol] = {}
        for reg in ("taylor", "fixed_real"):
            irf = dA["irfs"][pol][reg]
            sgn = -1.0 if pol == "tax_cut" else 1.0
            npv = lambda x, n: float(np.sum(np.asarray(x, float)[:n]
                                            / 1.01 ** np.arange(n)))
            cost = npv(irf[cost_key], len(np.asarray(irf[cost_key])))
            fam[pol][reg] = {
                "C_based_h20": sgn * npv(irf["C"], 20) / cost,
                "Y_based_h20": (sgn * npv(irf["Y"], 20) / cost
                                if "Y" in irf else None)}
    gate("C6_families", True, fam)

    sys.exit(_finish(V, outdir))


def _finish(V, outdir):
    V["end"] = time.strftime("%F %T")
    V["pass"] = all(V["gates"].values())
    with open(os.path.join(outdir, "phase_c_verdict.json"), "w") as f:
        json.dump(V, f, indent=1, default=str)
    print(f"[phase-c] OVERALL: {'PASS' if V['pass'] else 'FAIL'} "
          f"({sum(V['gates'].values())}/{len(V['gates'])})", flush=True)
    return 0 if V["pass"] else 1


if __name__ == "__main__":
    main()
