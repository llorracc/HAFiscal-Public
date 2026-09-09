"""BUG-092 weighted-tail sampler — gates 0 and 1 on the real Baseline economy.

Gate 0 (seed): per agent type the weighted E[p] equals the analytical E[p] (the sampler's own
diagnostic line is printed at the seed by initialize_mc_from_tm_ergodic); after the 24-quarter
warm-up the panel's weighted E[p] is still within a few % of it (in expectation it follows the
model's own law; the equal-weight panel sits ~11 % low).
Gate 1 (level): the base simulation's aggregate consumption per household vs the TM's (B, doob)
base level per household — 487 969.8 / 9 982 = 48.885 at Baseline default (from the 14:37 5a run).

Usage (the sampler is switched on by the env, read inside the TM init):
    HAFISCAL_MC_WEIGHTED_TAIL=200 python bug092_weighted_tail_probe.py Baseline out.json
    HAFISCAL_MC_WEIGHTED_TAIL=0   python bug092_weighted_tail_probe.py Baseline out.json   (control)
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "FromPandemicCode")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TM_BASE_PER_HH = float(os.environ.get("BUG092_TM_BASE_PER_HH", "48.885"))   # B (doob) Baseline default, 14:37 run


def main(parametrization, out_path):
    t0 = time.time()
    import welfare6_scenario as ws
    from tm_methods import pLvl_steady_state_moments
    K = int(os.environ.get("HAFISCAL_MC_WEIGHTED_TAIL", "0") or 0)
    ctx = ws.build_and_solve(parametrization)
    eco = ctx["AggEco"]
    agents = eco.agents
    per = []
    for i, a in enumerate(agents):
        w = getattr(a, "agent_weights", None)
        p = np.asarray(a.state_now["pLvl"], float)
        N = int(a.AgentCount)
        wv = np.ones(N) if w is None else np.asarray(w, float)
        Ep_an = float(pLvl_steady_state_moments(a, pLvl_dist="markov")["E_p"])
        Ep_w = float(np.sum(wv * p) / N)
        shares = wv * p / np.sum(wv * p)
        per.append({"i": i, "DiscFac": float(a.DiscFac), "N": N, "E_p_analytical": Ep_an,
                    "E_p_panel_post_warmup": Ep_w, "ratio": Ep_w / Ep_an,
                    "max_household_income_share": float(np.max(shares)),
                    "weighted": w is not None})
    print(f"[probe] {parametrization} K={K}: post-warm-up panel E[p] / analytical, per atom:")
    for q in per:
        print(f"   atom {q['i']:2d} β={q['DiscFac']:.4f} N={q['N']:4d}: {q['ratio']:.4f}  (max hh income share {q['max_household_income_share']:.2%})")
    tot_w = sum(q["E_p_panel_post_warmup"] * q["N"] for q in per); tot_an = sum(q["E_p_analytical"] * q["N"] for q in per)
    print(f"[probe] population-weighted E[p] panel/analytical = {tot_w/tot_an:.4f}")
    # gate 1: the base simulation's level
    base = ws.run_base(ctx)
    agg = np.asarray(base["AggCons"], float)
    n_hh = sum(int(a.AgentCount) for a in agents)
    per_hh = float(agg[:8].mean() / n_hh)
    print(f"[probe] base AggCons per household (first 8 q) = {per_hh:.3f}  vs TM (doob) {TM_BASE_PER_HH:.3f}  -> panel/TM = {per_hh/TM_BASE_PER_HH:.4f}")
    print(f"[probe] base AggCons path (per hh, t=0..39 step 8): " + " ".join(f"{float(agg[t])/n_hh:.3f}" for t in range(0, len(agg), 8)))
    out = {"parametrization": parametrization, "K": K, "per_atom": per, "E_p_ratio_pop": tot_w / tot_an,
           "base_per_hh": per_hh, "tm_base_per_hh": TM_BASE_PER_HH, "base_path_per_hh": (agg / n_hh).tolist(),
           "n_hh": n_hh, "wall_s": time.time() - t0}
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    print(f"[probe] done in {time.time()-t0:.0f}s -> {out_path}", flush=True)


if __name__ == "__main__":
    _param = sys.argv[1] if len(sys.argv) > 1 else "Baseline"
    _out = sys.argv[2] if len(sys.argv) > 2 else "bug092_wt_probe.json"
    sys.argv = sys.argv[:1]      # Parameters.py parses argv positionally
    main(_param, _out)
