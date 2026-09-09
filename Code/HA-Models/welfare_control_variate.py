#!/usr/bin/env python3
"""Control-variate estimator for the welfare-6 UI cells: what does "stratify by income" or "stratify by
marginal utility" buy when done POST HOC, with zero bias, on the seeds already run -- and how much of
the seed-to-seed variance is collector composition AT ALL?

WHY (owner, 2026-09-08).  The income-strata shuffle cuts the UI cells' seed SD ~25 % but moves the
estimand with the number of strata at Baseline's occupancy.  A control variate removes the same
explained variance without touching the estimand.  The households that COLLECT the extension in a
given recession are decided by the transition draws -- the rank of a uniform independent of income and
wealth -- so for any covariate z fixed at t = 0,

        Z = sum_{collectors i} ( z_i - zbar_{cell(i)} ),     cell = (agent type, Markov state at t = 0),

has E[Z] = 0 EXACTLY whatever the collector count, and  w6 - b Z  is unbiased for any fixed b.

WHAT IS EXACT HERE.  Collectors and their outlays are reconstructed from the saved Markov path with the
policy's own pay rule (``ui_extension_rule.extension_pay_mask``; benefit = (IncUnemp - IncUnempNoBenefits)
x pLvl) and CHECKED against the saved aggregate income difference at t = 0 (must match to 1e-9).  The
battery saves the Markov and pLvl panels for EVERY duration only under HAFISCAL_WELFARE6_SAVE_PER_DUR_PANELS=1;
otherwise only duration 0 is on disk, and the exact analysis is of the duration-0 cell (a one-quarter
recession) while the full, published cell gets the duration-0 Z as a legitimate but imperfect variate.
A consumption-response classifier for the other durations was tried and rejected (331 false positives
at 99 % recall on duration 0: the announcement moves consumption for households that never collect).

WHAT IS REPORTED, per cell and covariate set:
  E1  the exact regression estimator: the ratio's per-household influence  y_i = [(X_i - dC_i) - w b_i]/B
      (w = (A - dC)/B) regressed on the collectors' covariates with cell fixed effects; slope from ~10^3
      collectors, so effectively fixed; corrected  w6 - b.Z; the within-collector R^2.
  E2  the across-seed leave-one-out control variate (textbook, honest at small S, noisy).
  BOUND  the stratified-sampling variance of the collectors' influence sum, sum_cells n_c (1 - n_c/N_c) Var_c(y),
      against the observed seed variance: the share of the seed-to-seed variance that is collector
      COMPOSITION at all -- the ceiling for every composition device (strata, control variates, a
      p-weighted measure) at this panel.
Covariates (base world, t = 0; functions of the initial state and the t=0 income draws, independent of
the transition draws): p0 (income level), MU0 = cNrm0^(-rho) (baseline marginal utility, scale-free --
the owner's "c_base^rho"), a0 (normalized liquid assets).  Reproduces every seed's published cell from
its pickles to 1e-8 before anything else and refuses otherwise.  Adopts nothing.

Usage:  welfare_control_variate.py --results-glob "FromPandemicCode/welfare6_scenario_results_<tag>_seed*"
                                   [--policy paper_capped] [--out REPORT.md] [--recompute]
"""
import argparse, glob, json, os, pickle, re, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ui_extension_rule as uer  # noqa: E402

EDUC_SHARES = [0.093, 0.527, 0.38]          # EstimParameters.data_EducShares (dropout, HS, college)
DISCFAC_COUNT = 7                            # Baseline
UBSPELL_NORMAL, UBSPELL_EXTENDED = 2, 5      # EstimParameters
INC_UNEMP, INC_UNEMP_NOBEN = 0.7, 0.5        # EstimParameters (checked against the saved aggregate at t=0)
COVS = ("p0", "MU0", "a0")


def felicity(c, rho):
    c = np.maximum(c, 1e-16)
    return np.log(c) if abs(rho - 1.0) < 1e-12 else c ** (1 - rho) / (1 - rho)


def npv(series, R):
    return float(np.sum(np.asarray(series, float) / R ** np.arange(len(series))))


def load(d, s):
    with open(os.path.join(d, s + ".pkl"), "rb") as f:
        return pickle.load(f)


def type_blocks(n_panel, n_total):
    counts = []
    for e in range(3):
        counts += [int(np.floor(n_total * EDUC_SHARES[e] / DISCFAC_COUNT))] * DISCFAC_COUNT
    if sum(counts) != n_panel:
        raise SystemExit(f"type blocks sum to {sum(counts)} but the panel has {n_panel} households")
    return np.repeat(np.arange(len(counts)), counts)


def fe_regress(y, X, groups):
    """Within-group-demeaned OLS of y on the columns of X. Returns (coef, R2_within)."""
    y = np.asarray(y, float); X = np.atleast_2d(np.asarray(X, float)).T if np.ndim(X) == 1 else np.asarray(X, float)
    yd = y.copy(); Xd = X.copy()
    for g in np.unique(groups):
        m = groups == g
        yd[m] -= yd[m].mean(); Xd[m] -= Xd[m].mean(axis=0)
    coef, *_ = np.linalg.lstsq(Xd, yd, rcond=None)
    ss = float(np.sum(yd * yd)); res = yd - Xd @ coef
    return coef, (1.0 - float(np.sum(res * res)) / ss) if ss > 0 else 0.0


def per_household(P, Q, base_mu, probs, disc, rho):
    """X_i, dC_i (duration-weighted over the durations given) for panels P (pol), Q (none) of shape (D, T, N)."""
    N = P.shape[2]; X = np.zeros(N); dC = np.zeros(N)
    for d in range(len(probs)):
        du = (felicity(P[d], rho) - felicity(Q[d], rho)) / base_mu
        X += probs[d] * np.sum(du / disc, axis=0)
        dC += probs[d] * np.sum((P[d] - Q[d]) / disc, axis=0)
    return X, dC


def analyse_seed(d, n_total, policy):
    base = load(d, "base"); pol = load(d, "recessionUI"); none = load(d, "recession")
    R = float(base["Rfree"]); rho = float(base["CRRA"]); T = int(base["act_T"]); disc = (R ** np.arange(T))[:, None]
    summ = json.load(open(os.path.join(os.path.dirname(d), "Tables",
                     os.path.basename(d).replace("welfare6_scenario_results_", ""), "welfare6_parallel_summary.json")))["welfare6"]
    assert np.allclose(pol["agent_weights"], 1.0), "this tool assumes the equal-weight panel"
    N = pol["per_dur_cLvl_all_splurge"].shape[2]
    base_mu = np.maximum(base["cLvl_all_splurge"], 1e-16) ** (-rho)
    out = {"dir": os.path.basename(d), "N": N}

    # ---- the published cells, reproduced (the guard) -------------------------------------------------
    B_full = npv(pol["AggIncome"], R) - npv(none["AggIncome"], R)
    dC_full = npv(pol["AggCons"], R) - npv(none["AggCons"], R)
    X_full, _ = per_household(pol["per_dur_cLvl_all_splurge"], none["per_dur_cLvl_all_splurge"], base_mu, pol["rec_probs"], disc, rho)
    w6_full = X_full.sum() / B_full + (B_full - dC_full) / B_full
    if abs(w6_full - summ["ui_rec"]) > 1e-8 * abs(summ["ui_rec"]):
        raise SystemExit(f"ui_rec reproduced {w6_full:.10f} vs summary {summ['ui_rec']:.10f} -- refusing to continue")
    polAD = load(d, "recessionUI_AD"); noneAD = load(d, "recession_AD")
    XAD, _ = per_household(polAD["per_dur_cLvl_all_splurge"], noneAD["per_dur_cLvl_all_splurge"], base_mu, polAD["rec_probs"], disc, rho)
    w6_AD = XAD.sum() / B_full + (B_full - dC_full) / B_full
    if abs(w6_AD - summ["ui_rec_AD"]) > 1e-8 * abs(summ["ui_rec_AD"]):
        raise SystemExit(f"ui_rec_AD reproduced {w6_AD:.10f} vs summary {summ['ui_rec_AD']:.10f}")
    out["full"] = {"ui_rec": w6_full, "ui_rec_AD": w6_AD, "B": B_full, "dC": dC_full, "A": float(X_full.sum()), "A_AD": float(XAD.sum())}

    # ---- collectors and outlays from the Markov path + the pay rule ------------------------------------
    W = uer.resolve_window(policy, UBSPELL_NORMAL, UBSPELL_EXTENDED)
    J = 2 + UBSPELL_NORMAL + W.n_extension
    exact_all = "per_dur_Mrkv_hist" in pol and "per_dur_pLvl_all" in pol
    if exact_all:
        Mh = pol["per_dur_Mrkv_hist"]; Ph = pol["per_dur_pLvl_all"]; durs = list(range(Mh.shape[0])); probs = pol["rec_probs"]
    else:
        Mh = pol["Mrkv_hist_bs"][None]; Ph = pol["pLvl_all_bs"][None]; durs = [0]; probs = np.array([1.0])
    mac = Mh // J; mic = Mh % J
    if mic.max() != J - 1 or len(np.unique(mac[0][0])) != 1:
        raise SystemExit(f"Markov encoding inconsistent with J={J} (policy {policy}): micro max {mic.max()}, t=0 macro {np.unique(mac[0][0])}")
    mask = uer.extension_pay_mask("calendar", mac, mic, UBSPELL_NORMAL, W.n_extension, W)
    b_dt = (INC_UNEMP - INC_UNEMP_NOBEN) * Ph * mask                        # (D, T, N) outlay per household-quarter
    dI0 = float(pol["AggIncome"][0] - none["AggIncome"][0])
    if abs(b_dt[0, 0].sum() - dI0) > 1e-9 * abs(dI0):
        raise SystemExit(f"pay-rule reconstruction fails at t=0: {b_dt[0,0].sum():.6f} vs saved {dI0:.6f} (policy {policy}?)")
    dI = np.array(pol["AggIncome"]) - np.array(none["AggIncome"])
    if np.any(np.abs(dI[W.t_end + 1:]) > 1e-9) or np.any(dI[:W.t_end + 1] <= 0):
        raise SystemExit("saved outlay is nonzero outside the resolved window: wrong policy?")
    P = pol["per_dur_cLvl_all_splurge"][durs]; Q = none["per_dur_cLvl_all_splurge"][durs]
    X, dC = per_household(P, Q, base_mu, probs, disc, rho)
    b_i = np.einsum("d,dtn->n", probs, b_dt / disc[None])                # duration-weighted NPV outlay per household
    A = float(X.sum()); B = float(b_i.sum()); dCs = float(dC.sum())
    w6 = A / B + (B - dCs) / B
    coll = b_i > 0
    out["scope"] = "all durations (exact)" if exact_all else "duration 0 only (exact); full cell gets the duration-0 Z"
    out["cell"] = {"w6": w6, "A": A, "B": B, "dC": dCs, "n_coll": int(coll.sum()), "A_share_coll": float(X[coll].sum() / A)}

    # ---- covariates (base world, t = 0) and cells (type x recession Markov state at t = 0) -------------
    p0 = base["pLvl_all_bs"][0]; a0 = base["aNrm_all_bs"][0]; j0 = pol["Mrkv_hist_bs"][0]
    MU0 = np.maximum(base["cLvl_all_splurge"][0] / p0, 1e-16) ** (-rho)
    cov = {"p0": p0, "MU0": MU0, "a0": a0}
    cell_id = type_blocks(N, n_total) * 1000 + j0.astype(int)
    dev = {}
    for k, z in cov.items():
        zbar = np.zeros(N)
        for g in np.unique(cell_id):
            m = cell_id == g; zbar[m] = z[m].mean()
        dev[k] = z - zbar
    out["Z"] = {k: float(np.sum(dev[k][coll])) for k in COVS}

    # ---- E1: the ratio's per-household influence, regressed on the collectors' covariates --------------
    wt = (A - dCs) / B
    y = ((X - dC) - wt * b_i) / B
    g = cell_id[coll]
    out["E1"] = {}
    for name, keys in (("p0", ("p0",)), ("MU0", ("MU0",)), ("a0", ("a0",)), ("p0+MU0", ("p0", "MU0")), ("p0+MU0+a0", COVS)):
        Xm = np.column_stack([dev[k][coll] for k in keys])
        coef, r2 = fe_regress(y[coll], Xm, g)
        out["E1"][name] = {"coef": {k: float(c) for k, c in zip(keys, coef)}, "R2": r2,
                           "corrected": float(w6 - sum(c * out["Z"][k] for k, c in zip(keys, coef)))}
    # ---- BOUND: stratified-sampling variance of the collectors' influence sum ----------------------------
    var_comp = 0.0
    for gg in np.unique(cell_id):
        m = cell_id == gg; mc = m & coll; n_c = int(mc.sum()); N_c = int(m.sum())
        if n_c >= 2 and N_c > n_c:
            var_comp += n_c * (1.0 - n_c / N_c) * float(np.var(y[mc], ddof=1))
    out["var_comp_pred"] = var_comp
    # ---- VALIDITY: are the collectors a uniform draw within each cell?  Per-cell t of the collectors' mean
    # covariate against the cell mean (finite-population SE); pooled over cells these should be ~N(0,1).
    out["uniformity"] = {}
    for k in COVS:
        ts = []
        for gg in np.unique(cell_id):
            m = cell_id == gg; mc = m & coll; n_c = int(mc.sum()); N_c = int(m.sum())
            if n_c >= 5 and N_c > n_c + 1:
                sdc = float(np.std(cov[k][m], ddof=1))
                if sdc > 0:
                    ts.append((cov[k][mc].mean() - cov[k][m].mean()) / (sdc / np.sqrt(n_c) * np.sqrt(1 - n_c / N_c)))
        ts = np.asarray(ts)
        out["uniformity"][k] = {"n_cells": int(len(ts)), "mean_t": float(ts.mean()) if len(ts) else float("nan"),
                                "sd_t": float(ts.std(ddof=1)) if len(ts) > 1 else float("nan"),
                                "share_abs_gt2": float(np.mean(np.abs(ts) > 2)) if len(ts) else float("nan")}
    out["n_cells"] = int(len(np.unique(cell_id))); out["J"] = J; out["window"] = str(W)
    return out


def sd(v):
    v = np.asarray(v, float); return float(np.std(v, ddof=1)) if len(v) > 1 else float("nan")


def loo(w, Zcols):
    """Leave-one-out across-seed control variate with one or more Z columns."""
    Z = np.column_stack(Zcols); out = []
    for s in range(len(w)):
        keep = np.delete(np.arange(len(w)), s)
        Xd = np.column_stack([np.ones(len(keep)), Z[keep]])
        coef = np.linalg.lstsq(Xd, w[keep], rcond=None)[0]
        out.append(w[s] - float(Z[s] @ coef[1:]))
    return np.array(out)


def report(seeds):
    S = len(seeds); tag = seeds[0]["dir"].rsplit("_seed", 1)[0]
    w = np.array([s["cell"]["w6"] for s in seeds]); A = np.array([s["cell"]["A"] for s in seeds])
    B = np.array([s["cell"]["B"] for s in seeds]); dC = np.array([s["cell"]["dC"] for s in seeds])
    nco = np.array([s["cell"]["n_coll"] for s in seeds])
    wf = np.array([s["full"]["ui_rec"] for s in seeds]); wfAD = np.array([s["full"]["ui_rec_AD"] for s in seeds])
    L = ["# Welfare-6 UI cell: control variates and the composition bound", "",
         f"{S} seeds from `{tag}`, N = {seeds[0]['N']:,}. Scope: **{seeds[0]['scope']}**. J = {seeds[0]['J']} micro states; "
         f"{seeds[0]['window']}. Every seed's published cells reproduced to 1e-8 and the pay rule checked against the saved "
         f"aggregate at t = 0 before anything else. Cells = agent type x recession-world Markov state at t = 0 "
         f"({seeds[0]['n_cells']}); covariates from the base world at t = 0. Adopts nothing.", ""]
    L += ["## The cell analysed, and its pieces", "",
          f"| | mean | seed SD (rel.) |", "|---|---|---|",
          f"| exact-scope cell w6 | {w.mean():.4f} | **{100*sd(w)/w.mean():.2f} %** |",
          f"| numerator A | {A.mean():.1f} | {100*sd(A)/A.mean():.2f} % |",
          f"| outlay B | {B.mean():.1f} | {100*sd(B)/B.mean():.2f} % |",
          f"| added consumption dC | {dC.mean():.1f} | {100*sd(dC)/dC.mean():.2f} % |",
          f"| collectors | {nco.mean():.0f} ({100*nco.mean()/seeds[0]['N']:.2f} %) | {100*sd(nco)/nco.mean():.2f} % |",
          f"| collectors' share of A | {100*np.mean([s['cell']['A_share_coll'] for s in seeds]):.1f} % | |",
          f"| published full cell ui_rec | {wf.mean():.4f} | {100*sd(wf)/wf.mean():.2f} % |",
          f"| published full cell ui_rec_AD | {wfAD.mean():.4f} | {100*sd(wfAD)/wfAD.mean():.2f} % |", "",
          f"corr(A, B) across seeds = {np.corrcoef(A, B)[0,1]:+.2f} — the ratio cancels what the two share.", ""]
    vc = np.array([s["var_comp_pred"] for s in seeds]); var_obs = float(np.var(w, ddof=1))
    L += ["## BOUND: how much of the seed-to-seed variance is collector composition at all?", "",
          f"Stratified-sampling variance of the collectors' influence sum (exact cell counts, per-cell influence variance), "
          f"averaged over seeds: **{100*np.sqrt(vc.mean())/w.mean():.2f} %** of the cell as an SD, against the observed seed SD of "
          f"**{100*np.sqrt(var_obs)/w.mean():.2f} %** — i.e. composition accounts for about **{100*min(vc.mean()/var_obs, 9.99):.0f} %** of the "
          f"variance. Everything above that share is the collectors' subsequent paths, the non-collectors' insurance term and "
          f"the count — untouchable by any composition device (strata, control variates, a p-weighted measure).", ""]
    L += ["## E1 — exact regression estimator (slopes from the collectors' cross-section, cell fixed effects)", "",
          "| covariates | within-collector R² | corrected seed SD | mean shift | across-seed corr(w6, Z) |", "|---|---|---|---|---|"]
    for name in ("p0", "MU0", "a0", "p0+MU0", "p0+MU0+a0"):
        wc = np.array([s["E1"][name]["corrected"] for s in seeds]); r2 = np.mean([s["E1"][name]["R2"] for s in seeds])
        keys = name.split("+"); Zc = np.column_stack([[s["Z"][k] for s in seeds] for k in keys])
        corr = " / ".join(f"{np.corrcoef(w, Zc[:, i])[0,1]:+.2f}" for i in range(Zc.shape[1]))
        L.append(f"| {name} | {r2:.3f} | {100*sd(wc)/w.mean():.2f} % | {100*(wc.mean()-w.mean())/w.mean():+.2f} % | {corr} |")
    L += ["", "## E2 — across-seed leave-one-out control variate (honest at small S, noisy)", "",
          "| covariates | exact-scope cell: corrected SD | mean shift | full published cell (Z from the exact scope): corrected SD | mean shift |", "|---|---|---|---|---|"]
    for name in ("p0", "MU0", "a0", "p0+MU0"):
        keys = name.split("+"); Zc = [np.array([s["Z"][k] for s in seeds]) for k in keys]
        if S - 1 <= len(keys) + 1: continue
        w2 = loo(w, Zc); wf2 = loo(wf, Zc)
        L.append(f"| {name} | {100*sd(w2)/w.mean():.2f} % (raw {100*sd(w)/w.mean():.2f} %) | {100*(w2.mean()-w.mean())/w.mean():+.2f} % | "
                 f"{100*sd(wf2)/wf.mean():.2f} % (raw {100*sd(wf)/wf.mean():.2f} %) | {100*(wf2.mean()-wf.mean())/wf.mean():+.2f} % |")
    L += ["", "## Exogeneity check (E[Z] = 0 by construction; the across-seed mean should sit inside its SE)", ""]
    for k in COVS:
        Z = np.array([s["Z"][k] for s in seeds]); L.append(f"- Z_{k}: mean {Z.mean():+.3g}, SD {sd(Z):.3g}, mean/SE = {Z.mean()/(sd(Z)/np.sqrt(S)):+.2f}")
    L += ["", "## Within-cell uniformity of the collectors (the premise of E[Z] = 0), pooled over cells and seeds", "",
          "| covariate | (seed, cell) pairs | mean t | SD of t | share |t| > 2 | pooled mean t / SE |", "|---|---|---|---|---|---|"]
    for k in COVS:
        n_pairs = sum(s["uniformity"][k]["n_cells"] for s in seeds)
        mt = np.average([s["uniformity"][k]["mean_t"] for s in seeds], weights=[s["uniformity"][k]["n_cells"] for s in seeds])
        sdt = np.sqrt(np.average([s["uniformity"][k]["sd_t"] ** 2 for s in seeds], weights=[s["uniformity"][k]["n_cells"] for s in seeds]))
        sh = np.average([s["uniformity"][k]["share_abs_gt2"] for s in seeds], weights=[s["uniformity"][k]["n_cells"] for s in seeds])
        L.append(f"| {k} | {n_pairs} | {mt:+.3f} | {sdt:.3f} | {100*sh:.1f} % (N(0,1): 4.6 %) | {mt / (sdt / np.sqrt(n_pairs)):+.2f} |")
    L += ["", "Per seed: " + "; ".join(f"s{i}: w6 {s['cell']['w6']:.4f} (full {s['full']['ui_rec']:.4f}), n_coll {s['cell']['n_coll']}, "
                                       f"Z_p0 {s['Z']['p0']:+.1f}, Z_MU0 {s['Z']['MU0']:+.2f}, Z_a0 {s['Z']['a0']:+.1f}" for i, s in enumerate(seeds)), ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-glob", required=True)
    ap.add_argument("--policy", default="paper_capped", help="UI extension policy in force (checked against the saved outlay)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--recompute", action="store_true")
    a = ap.parse_args(argv)
    dirs = sorted(glob.glob(a.results_glob))
    if not dirs:
        raise SystemExit("no results dirs match")
    m = re.search(r"_N(\d+)_seed", dirs[0])
    if not m:
        raise SystemExit("cannot parse N from the directory name")
    n_total = int(m.group(1))
    cache = (a.out + ".seeds.json") if a.out else None
    if cache and os.path.exists(cache) and not a.recompute:
        seeds = json.load(open(cache)); print(f"[cache] {len(seeds)} seeds from {cache}", file=sys.stderr)
    else:
        seeds = []
        for d in dirs:
            print(f"[analyse] {os.path.basename(d)}", file=sys.stderr); seeds.append(analyse_seed(d, n_total, a.policy))
        if cache:
            json.dump(seeds, open(cache, "w"))
    txt = report(seeds); print(txt)
    if a.out:
        open(a.out, "w").write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
