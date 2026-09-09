"""BUG-092: derive the weighted-tail panel's UI-cell shortfall, household by household.

The welfare-6 cell for a policy is (run_welfare6_parallel.welfare6_mc)
    w6 = sum_t R^-t sum_i w_i [u(c^pol_it) - u(c^none_it)] / u'(c^base_it) / NPV_AddInc + residual,
with NPV_AddInc the AD=0 pair's discounted outlay, all on LEVEL consumption. The model is exactly
homogeneous of degree one in permanent income p (verified: the equal-weight and weighted runs of the
same seed share byte-identical Markov/aNrm panels and normalized consumption to 5e-16), so writing
W_it = w_i p_it for the household's income weight, both numerator and outlay are income-weighted
sums over ONE shared field:
    Num = sum_d pi_d sum_t R^-t sum_i W_it g_itd,     Cost = sum_d pi_d sum_t R^-t sum_i W_it tau_itd,
    g = [u(c_p)-u(c_n)] c_b^rho / p  (normalized money-metric gain),  tau = 0.2 * 1{u3Q/u4Q at a
recession macro state} (the UI extension, IncUnemp - IncUnempNoBenefits = 0.7 - 0.5).
The two panels differ ONLY in the income weights (equal-weight: stratified draws of the atom's
ergodic p-mixture, randomly permuted; weighted-tail: bulk conditional means + K equal-income tail
strata, randomly permuted). Given the field, each cell is a ratio of income-weighted sums whose
weights are exchangeable within an atom; this script computes, from a re-simulation that saved every
duration's Markov and pLvl panels (HAFISCAL_WELFARE6_SAVE_PER_DUR_PANELS=1):
  * each panel's exact cell (must reproduce the battery's summary value — CRN check),
  * the split of numerator and outlay by education group / atom and by tail-vs-bulk slot,
  * the permutation distribution of each panel's cell (re-assign that panel's (w, p_0) pairs at
    random across slots within each atom, holding the field fixed): its mean is the cell's
    expectation given the field, its SD the sampling error the p-assignment alone induces.
Usage: python bug092_ui_cell_decomposition.py <resim_pickle_dir> <eq_pickle_dir> <wt_pickle_dir> [n_perm]
"""
from __future__ import annotations
import os, sys, json, pickle
import numpy as np

R, RHO = 1.01, 2.0
Ns = [132]*7 + [752]*7 + [542]*7            # Baseline atoms (dropout x7, HS x7, college x7), slot order
GRP = ["D"]*7 + ["H"]*7 + ["C"]*7
EDGES = np.cumsum([0] + Ns)

def u(c): return c ** (1 - RHO) / (1 - RHO)

def load(d, s): return pickle.load(open(os.path.join(d, s + ".pkl"), "rb"))

def field(resim_dir, ref_dir):
    """Per-slot field quantities from the re-simulation (whose own panel is the weighted one)."""
    pol, none, base = load(resim_dir, "recessionUI"), load(resim_dir, "recession"), load(ref_dir, "base")
    ref_pol = load(ref_dir, "recessionUI")
    # CRN check: the re-simulation must reproduce the battery's duration-0 panels exactly
    assert np.array_equal(np.asarray(pol["Mrkv_hist_bs"]), np.asarray(ref_pol["Mrkv_hist_bs"])), "CRN: Mrkv differs"
    assert np.array_equal(np.asarray(pol["per_dur_cLvl_all_splurge"]), np.asarray(ref_pol["per_dur_cLvl_all_splurge"])), "CRN: cLvl differs"
    M = np.asarray(pol["per_dur_Mrkv_hist"]).astype(np.int64)          # (D, T, N)
    P = np.asarray(pol["per_dur_pLvl_all"])                            # (D, T, N)
    pr = np.asarray(pol["rec_probs"]); D, T, N = M.shape
    assert np.allclose(P, P[0][None]), "pLvl path differs across durations"
    p = P[0]                                                           # (T, N), the shared p path
    disc = R ** -np.arange(T)
    ext = np.isin(M % 6, [3, 4]) & ((M // 6) % 2 == 1)                 # (D,T,N) extension paid
    Cp, Cn = np.asarray(pol["per_dur_cLvl_all_splurge"]), np.asarray(none["per_dur_cLvl_all_splurge"])
    Cb = np.maximum(np.asarray(base["cLvl_all_splurge"]), 1e-16)      # base has no durations
    # normalized field: g_itd and tau_itd, then pi/discount-summed per slot, split pre/post first death
    dies = np.asarray(base["who_dies_all_bs"]).astype(bool)           # (T,N); identical across scenarios
    first_death = np.where(dies.any(0), dies.argmax(0), T)             # t of first death (T if none)
    pre = (np.arange(T)[:, None] < first_death[None, :])               # (T,N) before the slot's first death
    Gam = p / p[0][None, :]                                            # growth factor of the slot's p (pre-death only meaningful)
    g = (u(Cp) - u(Cn)) * (Cb ** RHO)[None] / p[None]                  # (D,T,N)
    tau = 0.2 * ext
    def s(x, mask):   # sum_d pi_d sum_t disc_t x_dt * mask_t  -> (N,)
        return np.einsum("d,t,dtn->n", pr, disc, x * mask[None])
    out = dict(N=N, T=T, p=p, pre=pre, first_death=first_death,
               num_pre=s(g * Gam[None], pre), num_post=s(g * p[None], ~pre),
               cost_pre=s(tau * Gam[None], pre), cost_post=s(tau * p[None], ~pre),
               recip=ext.any(axis=(0, 1)), n_recip_q=ext.sum(axis=(0, 1)))
    # AD cell numerator: the panel's AD pickles (same Markov field under CRN; consumption on the
    # prescribed AD path, shared by both panels under equilibrium sharing)
    polA, noneA = load(ref_dir, "recessionUI_AD"), load(ref_dir, "recession_AD")
    assert np.array_equal(np.asarray(polA["Mrkv_hist_bs"]), np.asarray(ref_pol["Mrkv_hist_bs"])), "AD: Mrkv differs"
    gA = (u(np.asarray(polA["per_dur_cLvl_all_splurge"])) - u(np.asarray(noneA["per_dur_cLvl_all_splurge"]))) * (Cb ** RHO)[None] / p[None]
    out["numAD_pre"] = s(gA * Gam[None], pre); out["numAD_post"] = s(gA * p[None], ~pre)
    return out, pol, none

def cell(fd, w, p0, resid, ad=False):
    k = "numAD" if ad else "num"
    num = np.sum(w * (p0 * fd[k + "_pre"] + fd[k + "_post"]))
    cost = np.sum(w * (p0 * fd["cost_pre"] + fd["cost_post"]))
    return num / cost + resid, num, cost

def residual(dirn):
    pol, none = load(dirn, "recessionUI"), load(dirn, "recession")
    def npv(x): x = np.asarray(x, float); return float(np.sum(x / R ** np.arange(len(x))))
    inc = npv(pol["AggIncome"]) - npv(none["AggIncome"]); con = npv(pol["AggCons"]) - npv(none["AggCons"])
    return (inc - con) / inc, inc

def main(resim_dir, eq_dir, wt_dir, n_perm=400):
    fd, pol, none = field(resim_dir, wt_dir)
    N = fd["N"]
    panels = {}
    for name, d in (("eq", eq_dir), ("wt", wt_dir)):
        b = load(d, "base"); w = b.get("agent_weights"); w = np.ones(N) if w is None else np.asarray(w, float)
        p0 = np.asarray(b["pLvl_all_bs"])[0]
        assert np.allclose(np.asarray(b["pLvl_all_bs"])[fd["pre"]] / p0[None, :].repeat(fd["T"], 0)[fd["pre"]],
                           fd["p"][fd["pre"]] / fd["p"][0][None, :].repeat(fd["T"], 0)[fd["pre"]]), f"{name}: growth path differs"
        resid, cost_agg = residual(d)
        c, num, cost = cell(fd, w, p0, resid)
        cA, numA, _ = cell(fd, w, p0, resid, ad=True)
        summ = json.load(open(os.path.join("Tables", os.path.basename(d).replace("welfare6_scenario_results_", ""), "welfare6_parallel_summary.json")))["welfare6"]
        print(f"[{name}] ui_rec exact from field = {c:.4f} (battery {summ['ui_rec']:.4f});  ui_rec_AD = {cA:.4f} (battery {summ['ui_rec_AD']:.4f})   Num {num:.1f} NumAD {numA:.1f} Cost {cost:.1f} resid {resid:.4f}")
        panels[name] = dict(w=w, p0=p0, resid=resid, cell=c, num=num, cost=cost, cellAD=cA)
    # even-weight references: every slot of an atom carries the atom's mean income weight of that
    # panel (no within-atom sampling at all) -> isolates composition (atom income levels) from
    # the estimator's own sampling/bias
    for name in ("eq", "wt"):
        w, p0 = panels[name]["w"], panels[name]["p0"]; we = np.ones(N); pe = np.empty(N)
        for a in range(len(Ns)):
            sl = slice(EDGES[a], EDGES[a+1]); pe[sl] = np.sum(w[sl] * p0[sl]) / (EDGES[a+1] - EDGES[a])
        panels[name]["even"] = cell(fd, we, pe, panels[name]["resid"])[0]
        panels[name]["evenAD"] = cell(fd, we, pe, panels[name]["resid"], ad=True)[0]
    print(f"even-weight (composition-only) references: ui_rec eq {panels['eq']['even']:.4f} wt {panels['wt']['even']:.4f} (gap {panels['wt']['even']/panels['eq']['even']-1:+.2%}); "
          f"ui_rec_AD eq {panels['eq']['evenAD']:.4f} wt {panels['wt']['evenAD']:.4f} (gap {panels['wt']['evenAD']/panels['eq']['evenAD']-1:+.2%})")
    W = {k: v["w"] * v["p0"] for k, v in panels.items()}
    tail = panels["wt"]["w"] < 0.999
    # --- decomposition by group and by slot type ---------------------------------------------
    print("\nshares of numerator / outlay (all durations) and welfare per outlay dollar, by education group:")
    for name in ("eq", "wt"):
        w, p0 = panels[name]["w"], panels[name]["p0"]
        numi = w * (p0 * fd["num_pre"] + fd["num_post"]); costi = w * (p0 * fd["cost_pre"] + fd["cost_post"])
        line = f"  [{name}] "
        for g in "DHC":
            m = np.array([x == g for x in GRP]); sl = np.concatenate([np.arange(EDGES[a], EDGES[a+1]) for a in np.where(m)[0]])
            line += f"{g}: inc {W[name][sl].sum()/W[name].sum():.3f} num {numi[sl].sum()/numi.sum():.3f} cost {costi[sl].sum()/costi.sum():.3f} per$ {numi[sl].sum()/costi[sl].sum():.3f} | "
        if name == "wt":
            line += f"tail slots: inc {W[name][tail].sum()/W[name].sum():.3f} num {numi[tail].sum()/numi.sum():.3f} cost {costi[tail].sum()/costi.sum():.3f} per$ tail {numi[tail].sum()/costi[tail].sum():.3f} bulk {numi[~tail].sum()/costi[~tail].sum():.3f}"
        print(line)
    # field (unweighted-within-atom) reference: each atom's income weight = the panel's atom mean, slots equal
    # --- permutation distributions ---------------------------------------------------------------
    rng = np.random.default_rng(0)
    print(f"\npermutation test ({n_perm} within-atom re-assignments of each panel's (w, p0) pairs; field fixed):")
    res = {}
    for name in ("eq", "wt"):
        w, p0, resid = panels[name]["w"], panels[name]["p0"], panels[name]["resid"]
        vals, valsA = [], []
        for _ in range(n_perm):
            wp, pp = w.copy(), p0.copy()
            for a in range(len(Ns)):
                s, t = EDGES[a], EDGES[a+1]; perm = rng.permutation(t - s)
                wp[s:t] = w[s:t][perm]; pp[s:t] = p0[s:t][perm]
            vals.append(cell(fd, wp, pp, resid)[0]); valsA.append(cell(fd, wp, pp, resid, ad=True)[0])
        vals, valsA = np.asarray(vals), np.asarray(valsA)
        res[name] = dict(mean=float(vals.mean()), sd=float(vals.std()), meanAD=float(valsA.mean()), sdAD=float(valsA.std()),
                         even=panels[name]["even"], evenAD=panels[name]["evenAD"], realized=panels[name]["cell"], realizedAD=panels[name]["cellAD"])
        print(f"  [{name}] ui_rec   : realized {panels[name]['cell']:.4f} | perm mean {vals.mean():.4f} sd {vals.std():.4f} | even-weight {panels[name]['even']:.4f} | z = {(panels[name]['cell']-vals.mean())/vals.std():+.2f}")
        print(f"  [{name}] ui_rec_AD: realized {panels[name]['cellAD']:.4f} | perm mean {valsA.mean():.4f} sd {valsA.std():.4f} | even-weight {panels[name]['evenAD']:.4f} | z = {(panels[name]['cellAD']-valsA.mean())/valsA.std():+.2f}")
    for k, kA in (("mean", "realized"), ("meanAD", "realizedAD")):
        print(f"  {'ui_rec' if k=='mean' else 'ui_rec_AD'}: expected gap wt-eq {res['wt'][k]/res['eq'][k]-1:+.2%} | realized gap {res['wt'][kA]/res['eq'][kA]-1:+.2%}")
    # atom-level composition-only counterfactual: give the eq panel each atom's wt income level but equal slots
    out = dict(perm=res,
               n_recip=int(fd["recip"].sum()), n_recip_tail=int((fd["recip"] & tail).sum()))
    json.dump(out, open(f"bug092_ui_cell_decomposition_{os.path.basename(resim_dir)}.json", "w"), indent=1)
    print(f"\nrecipients (any duration, any quarter): {out['n_recip']} of {N} slots; {out['n_recip_tail']} tail slots")

if __name__ == "__main__":
    a = sys.argv[1:]; sys.argv = sys.argv[:1]
    main(a[0], a[1], a[2], int(a[3]) if len(a) > 3 else 400)
