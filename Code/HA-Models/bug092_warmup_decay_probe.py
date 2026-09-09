"""Where does the p-mass go during the MC warm-up? Build Baseline with the TM init but NO warm-up,
then step sim_one_period 24 times, recording per quarter: population-weighted E[p]/analytical,
mean log p, the number of deaths, and the survivors' mean log growth. Run with
HAFISCAL_MC_WEIGHTED_TAIL=0 and =200 (HAFISCAL_WELFARE6_MC_WARMUP=0 is set here)."""
import json, os, sys, time
import numpy as np
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "FromPandemicCode")):
    if _p not in sys.path: sys.path.insert(0, _p)
os.environ["HAFISCAL_WELFARE6_MC_WARMUP"] = "0"
def main(out_path, T=24):
    import welfare6_scenario as ws
    from tm_methods import pLvl_steady_state_moments
    K = int(os.environ.get("HAFISCAL_MC_WEIGHTED_TAIL", "0") or 0)
    ctx = ws.build_and_solve("Baseline"); eco = ctx["AggEco"]; agents = eco.agents
    # build_and_solve deletes the base solution after the init (counterfactual mode); the warm-up
    # inside initialize_mc_from_tm_ergodic ran with it present -- re-install it (store HITs)
    eco.switch_shock_type("base"); eco.solve()
    for a in agents:
        a.T_sim = 400; a.t_sim = 0
    Ep_an = [float(pLvl_steady_state_moments(a, pLvl_dist="markov")["E_p"]) for a in agents]
    Ns = [int(a.AgentCount) for a in agents]; tot_an = sum(e * n for e, n in zip(Ep_an, Ns))
    def W(a): w = getattr(a, "agent_weights", None); return np.ones(a.AgentCount) if w is None else np.asarray(w, float)
    def stats():
        Ep = sum(float(np.sum(W(a) * np.asarray(a.state_now["pLvl"], float))) for a in agents) / tot_an
        lp = np.concatenate([np.log(np.asarray(a.state_now["pLvl"], float)) for a in agents])
        top = sum(float(np.sum(W(a)[np.argsort(-np.asarray(a.state_now['pLvl']))[:5]] * np.sort(np.asarray(a.state_now['pLvl'], float))[::-1][:5])) for a in agents) / tot_an
        return Ep, float(lp.mean()), top
    rows = []; prev = [np.asarray(a.state_now["pLvl"], float).copy() for a in agents]
    Ep, mlp, top = stats(); rows.append({"t": 0, "Ep_ratio": Ep, "mean_logp": mlp, "top5_share": top, "deaths": 0, "surv_dlogp": 0.0})
    print(f"t= 0 E[p]/an={Ep:.4f} mean log p={mlp:.4f} top-5-per-atom income share={top:.4f}", flush=True)
    for t in range(1, T + 1):
        for a in agents: a.sim_one_period()
        cur = [np.asarray(a.state_now["pLvl"], float) for a in agents]
        deaths = 0; dl = []
        for a, p0, p1 in zip(agents, prev, cur):
            died = np.asarray(a.shocks.get("who_dies", np.zeros(len(p1), bool))) if hasattr(a, "shocks") and "who_dies" in a.shocks else None
            if died is None or died.shape != p1.shape:
                died = np.log(p1 / p0) < -1.0        # fallback: a reset to p~1 from a large p
            deaths += int(died.sum()); dl.append(np.log(p1[~died] / p0[~died]))
        Ep, mlp, top = stats(); sd = float(np.concatenate(dl).mean()) if dl else float("nan")
        rows.append({"t": t, "Ep_ratio": Ep, "mean_logp": mlp, "top5_share": top, "deaths": deaths, "surv_dlogp": sd})
        print(f"t={t:2d} E[p]/an={Ep:.4f} mean log p={mlp:.4f} top-5 share={top:.4f} deaths={deaths:4d} survivors' mean dlog p={sd:+.5f}", flush=True)
        prev = [c.copy() for c in cur]
    json.dump({"K": K, "rows": rows, "Ep_an": Ep_an, "N": Ns}, open(out_path, "w"), indent=1)
if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "decay.json"; sys.argv = sys.argv[:1]; main(out)
