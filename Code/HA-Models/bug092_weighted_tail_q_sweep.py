"""BUG-092 follow-on (2026-08-25 21:10): how much of the weighted panel's remaining UI-cell noise is
the sampler's tail-population share q? On the saved seed field (bug092_ui_cell_decomposition.field),
re-stratify every atom's ergodic p-mixture for several q (K unchanged), draw the within-atom
permutation distribution of ui_rec, and report its SD and the largest single-slot income share.
Usage: python bug092_weighted_tail_q_sweep.py <resim_dir> <wt_pickle_dir> [n_perm]
"""
from __future__ import annotations
import os, sys, json, time
import numpy as np
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "FromPandemicCode")):
    if _p not in sys.path: sys.path.insert(0, _p)

def main(resim_dir, wt_dir, n_perm=200):
    t0 = time.time()
    import bug092_ui_cell_decomposition as D
    import welfare6_scenario as ws
    from tm_methods import _pLvl_components_select
    from weighted_tail_sampler import mixture_tables, weighted_tail_pLvl
    fd, _, _ = D.field(resim_dir, wt_dir)
    resid, _ = D.residual(wt_dir)
    b = D.load(wt_dir, "base"); w_run = np.asarray(b["agent_weights"]); p_run = np.asarray(b["pLvl_all_bs"])[0]
    ctx = ws.build_and_solve("Baseline"); agents = ctx["AggEco"].agents
    assert [int(a.AgentCount) for a in agents] == D.Ns, "atom sizes differ from the field's"
    tabs = []
    for i, a in enumerate(agents):
        w, mu, sig = _pLvl_components_select(a, pLvl_dist="markov"); tabs.append(mixture_tables(w, mu, sig))
        print(f"[q-sweep] tables atom {i} ({time.time()-t0:.0f}s)", flush=True)
    rng = np.random.default_rng(7); out = {}
    qs = [0.01, 0.03, 0.05, 0.10, 0.20]
    for q in qs:
        vals = []; maxshare = 0.0; tail_inc = 0.0
        for _ in range(n_perm):
            wv = np.empty(fd["N"]); pv = np.empty(fd["N"])
            for i, a in enumerate(agents):
                N_i = int(a.AgentCount); K_i = int(min(200, max(2, N_i // 4)))
                pl, wt, dg = weighted_tail_pLvl(None, None, None, N_i, K_i, q, rng, tables=tabs[i])
                s, t = D.EDGES[i], D.EDGES[i + 1]; pv[s:t] = pl; wv[s:t] = wt
                maxshare = max(maxshare, dg["max_income_share"]); 
            vals.append(D.cell(fd, wv, pv, resid)[0])
        vals = np.asarray(vals)
        W = wv * pv; tail_inc = float(W[wv < 0.999].sum() / W.sum())
        out[str(q)] = dict(mean=float(vals.mean()), sd=float(vals.std()), max_income_share_atom=float(maxshare), tail_income_share=tail_inc)
        print(f"[q-sweep] q={q:.2f}: ui_rec permutation mean {vals.mean():.4f} sd {vals.std():.4f} ({vals.std()/vals.mean():.2%}); largest single-slot share of an atom's income {maxshare:.2%}; tail income share {tail_inc:.1%}   ({time.time()-t0:.0f}s)", flush=True)
    # reference: the run's own weights (q=0.01 realized) and the equal-weight panel's SD from the earlier run
    c_run = D.cell(fd, w_run, p_run, resid)[0]
    out["run_realized_q0.01"] = float(c_run)
    json.dump(out, open(os.path.join(_HERE, f"bug092_weighted_tail_q_sweep_{os.path.basename(resim_dir)}.json"), "w"), indent=1)
    print(f"[q-sweep] done {time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    a = sys.argv[1:]; sys.argv = sys.argv[:1]
    main(a[0], a[1], int(a[2]) if len(a) > 2 else 200)
