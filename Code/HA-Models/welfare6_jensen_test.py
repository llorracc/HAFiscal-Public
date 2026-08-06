#!/usr/bin/env python
"""Decisive test of the MC<->TM non-AD gap diagnosis: it is the within-cell
JENSEN gap (TM evaluates u at the bucket/cohort-MEAN consumption; MC averages the
per-agent u). Reproduce the TM's collapse ON THE MC PANELS and show the gap appears.

For TaxCut the TM uses w_b=1 (cohort-mean collapse, no bucketing) -> cleanest test:
  per-agent  mean_i [u(c^p_i)-u(c^n_i)]/u'(c^b_i)   (== MC)
  cohort     N * [u(c^p_bar)-u(c^n_bar)]/u'(c^b_bar) (== TM)
If (per-agent - cohort) reproduces the TM-MC gap (taxcut_rec -2.34%, check_rec
collapses farther, bucket recovers part), the diagnosis is empirically nailed.
"""
import os
import pickle
import numpy as np

SW = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "Results", "tmp", "shuffle", "shuf_s0")


def load(s):
    with open(os.path.join(SW, f"{s}.pkl"), "rb") as f:
        return pickle.load(f)


def fel(c, rho):
    c = np.maximum(c, 1e-16)
    return np.log(c) if abs(rho - 1.0) < 1e-12 else c ** (1.0 - rho) / (1.0 - rho)


def muinv(c, rho):  # 1/u'(c) = c^rho
    return np.maximum(c, 1e-16) ** rho


def npv(series, R, T):
    series = np.asarray(series, dtype=float)[:T]
    return float(np.sum(series / R ** np.arange(T)))


def per_dur(d):
    pd = d.get("per_dur_cLvl_all_splurge")
    return np.asarray(pd) if pd is not None else None


def cell(pol, none, base, mode="agent", nb=50):
    rho = float(np.asarray(pol["CRRA"]).reshape(-1)[0])
    R = float(np.asarray(pol["Rfree"]).reshape(-1)[0])
    T = int(np.asarray(pol["act_T"]).reshape(-1)[0])
    NPV_AddInc = npv(pol["AggIncome"], R, T) - npv(none["AggIncome"], R, T)
    NPV_AddCons = npv(pol["AggCons"], R, T) - npv(none["AggCons"], R, T)

    pdp, pdn = per_dur(pol), per_dur(none)
    pdb = per_dur(base)
    if pdb is None:
        pdb = np.broadcast_to(np.asarray(base["cLvl_all_splurge"]), pdp.shape)
    rp = np.asarray(pol["rec_probs"]).reshape(-1)
    ndur, Tp, N = pdp.shape
    T = min(T, Tp)

    # pLvl buckets (fixed assignment by each agent's time-mean pLvl)
    if mode in ("bucket", "corrected"):
        pl = np.asarray(pol.get("pLvl_all_bs"))
        key = pl.mean(0) if pl.ndim == 2 else pl
        order = np.argsort(key)
        bucket_of = np.empty(N, dtype=int)
        edges = np.linspace(0, N, nb + 1).astype(int)
        for b in range(nb):
            bucket_of[order[edges[b]:edges[b + 1]]] = b

    sum_per_t = np.zeros(T)
    for dur in range(ndur):
        cp, cn, cb = pdp[dur, :T], pdn[dur, :T], pdb[dur, :T]  # (T,N)
        if mode == "agent":
            # integrand_i = [u(c^p_i)-u(c^n_i)] / u'(c^b_i) = [fel(cp)-fel(cn)] * (1/u') ; 1/u' = c^rho = muinv
            num_t = ((fel(cp, rho) - fel(cn, rho)) * muinv(cb, rho)).sum(1)
        elif mode == "cohort":
            cpm, cnm, cbm = cp.mean(1), cn.mean(1), cb.mean(1)  # (T,)
            num_t = N * (fel(cpm, rho) - fel(cnm, rho)) * muinv(cbm, rho)
        elif mode == "bucket":
            num_t = np.zeros(T)
            for b in range(nb):
                m = bucket_of == b
                nbk = int(m.sum())
                if nbk == 0:
                    continue
                cpm, cnm, cbm = cp[:, m].mean(1), cn[:, m].mean(1), cb[:, m].mean(1)
                num_t += nbk * (fel(cpm, rho) - fel(cnm, rho)) * muinv(cbm, rho)
        elif mode == "corrected":
            # 2nd-order Jensen correction: E[g|b] ~ g(means) + 1/2 sum g_xy Cov(x,y|b)
            # g(p,n,b) = [u(p)-u(n)] * b^rho ; g_pn = 0.
            num_t = np.zeros(T)
            for b in range(nb):
                m = bucket_of == b
                nbk = int(m.sum())
                if nbk == 0:
                    continue
                cpb, cnb, cbb = cp[:, m], cn[:, m], cb[:, m]
                pbar = np.maximum(cpb.mean(1), 1e-12)
                nbar = np.maximum(cnb.mean(1), 1e-12)
                bbar = np.maximum(cbb.mean(1), 1e-12)
                Vp, Vn, Vb = cpb.var(1), cnb.var(1), cbb.var(1)
                Cpb = ((cpb - pbar[:, None]) * (cbb - bbar[:, None])).mean(1)
                Cnb = ((cnb - nbar[:, None]) * (cbb - bbar[:, None])).mean(1)
                upn, brho = fel(pbar, rho) - fel(nbar, rho), bbar ** rho
                g0 = upn * brho
                gpp = -rho * pbar ** (-rho - 1) * brho
                gnn = rho * nbar ** (-rho - 1) * brho
                gbb = upn * rho * (rho - 1) * bbar ** (rho - 2)
                gpb = pbar ** (-rho) * rho * bbar ** (rho - 1)
                gnb = -nbar ** (-rho) * rho * bbar ** (rho - 1)
                corr = 0.5 * (gpp * Vp + gnn * Vn + gbb * Vb + 2 * gpb * Cpb + 2 * gnb * Cnb)
                num_t += nbk * (g0 + corr)
        sum_per_t += rp[dur] * num_t

    disc = R ** np.arange(T)
    return float(np.sum(sum_per_t / NPV_AddInc / disc) + (NPV_AddInc - NPV_AddCons) / NPV_AddInc)


def main():
    base = load("base")
    rec = load("recession")
    print(f"{'cell':<12}{'per-agent(MC)':>14}{'TM-collapse':>13}{'corrected':>11}"
          f"{'  TM-gap':>10}{'corr-resid':>12}")
    for name, polname, nbtm, tmmode in [
            ("taxcut_rec", "recessionTaxCut", 1, "cohort"),
            ("check_rec", "recessionCheck", 50, "bucket")]:
        pol = load(polname)
        a = cell(pol, rec, base, "agent")
        tm = cell(pol, rec, base, tmmode, nb=nbtm)
        cr = cell(pol, rec, base, "corrected", nb=nbtm)
        print(f"{name:<12}{a:>14.4f}{tm:>13.4f}{cr:>11.4f}"
              f"{100*(a-tm)/a:>9.2f}%{100*(a-cr)/a:>11.2f}%")
    print("\nTM-gap = per-agent vs TM-collapse (the Jensen gap, ~ observed MC-TM).")
    print("corr-resid = per-agent vs 2nd-order corrected. If ~0 -> Plan C closes it cheaply.")


if __name__ == "__main__":
    main()
