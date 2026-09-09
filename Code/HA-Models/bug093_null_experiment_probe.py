"""BUG-093 first probe: the TM engine's NULL experiment, per atom.

Symptom (2026-08-25, `BUGS_private/HAFiscal_BUG-093_*.md`): in the Baseline default (uncapped)
world the TM's no-AD recession experiment never returns to its own base — AggCons/base sits at
+2.6…3.3 % through t=30 while AggIncome returns to 0.9997 — whereas Reduced_Run (either world)
and the Baseline MC own loop return to 1.000. This probe reproduces Step 5a's TM computation
exactly (same builders, same grids: `dist_aGrid_count=100`, `neutral_measure=True`) and asks,
atom by atom:

  base_i      = AgentCount·E_pLvl·C_splurge_nrm  from `compute_type_aggregates_tm_a` on the
                ergodic (what `run_experiment_tm` sums into `base_results`);
  null_i(t)   = `propagate_experiment_tm_a` along EconomyMrkv_init = [0]*act_T (NO recession),
                started from the half-step period-0 distribution — must equal base_i for all t;
  d0_i(t)     = the same along 5a's duration-0 path (one recession quarter) — the aggregate at
                t=0 must reproduce the 5a artifact (Baseline default: 1.0260) so the
                decomposition is trusted.

Usage (one arm per process; the world/cap axis is read by Parameters at import):
    HAFISCAL_WORLD=default          python bug093_null_experiment_probe.py Baseline    out.json
    HAFISCAL_T_AGE=200              python bug093_null_experiment_probe.py Baseline    out.json
    HAFISCAL_WORLD=default          python bug093_null_experiment_probe.py Reduced_Run out.json
Economy build + base solve go through `welfare6_scenario.build_and_solve` (the maintained
builder outside Simulate.py; policy-store HITs), the recession solve through the store-hooked
`AggregateDemandEconomy.solve()`.
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

TM_MCOUNT = int(os.environ.get("HAFISCAL_TM_MCOUNT", "100"))   # 5a's Run_Dict default
NEUTRAL = True                                                  # 5a's tm_neutral_measure
T_REPORT = (0, 1, 2, 5, 10, 20, 30)


def main(parametrization, out_path):
    t0 = time.time()
    import welfare6_scenario as ws
    from tm_methods import (build_tm_agg_fiscal_a, compute_analytical_mean_pLvl,
                            compute_baseline_tm_data, compute_type_aggregates_tm_a,
                            find_ergodic_distribution, propagate_experiment_tm_a,
                            run_experiment_tm)

    ctx = ws.build_and_solve(parametrization)
    eco = ctx["AggEco"]
    act_T = int(ctx["act_T"])
    eco.act_T = act_T
    ne = int(ctx["num_experiment_periods"])
    agents = eco.agents
    print(f"[probe] {parametrization}: {len(agents)} atoms, act_T={act_T}, ne={ne}, "
          f"T_age={getattr(agents[0], 'T_age', None)}, build {time.time()-t0:.0f}s", flush=True)
    for a in agents:
        a.tm_a_indexed = True            # 5a: Run_Dict['tm_a_indexed'] (HAFISCAL_TM_A_INDEXED=1)

    # --- base config: solve (store-hooked), baseline TM data, base per atom (5a order) -------
    eco.switch_shock_type("base")
    eco.solve()
    bd = compute_baseline_tm_data(eco, dist_aGrid_count=TM_MCOUNT, neutral_measure=NEUTRAL)
    base_tm = run_experiment_tm(eco, shock_type="base", dist_aGrid_count=TM_MCOUNT,
                                neutral_measure=NEUTRAL)
    base_agg = float(np.asarray(base_tm["AggCons"], float)[0])
    base_inc_agg = float(np.asarray(base_tm["AggIncome"], float)[0])
    per = []
    for i, agent in enumerate(agents):
        # per-atom base level from the SAME construction the experiments start from (bd carries
        # tm_data + ergodic since the BUG-093 fix; before it this loop rebuilt the plain kernel)
        agent.update_mrkv_array("base")
        agent.solve()
        interp = getattr(agent, "interpretation", "CDC")
        if bd[i].get("tm_data") is not None:
            tm_data, erg = bd[i]["tm_data"], bd[i]["ergodic"]
        else:
            tm_data = build_tm_agg_fiscal_a(agent, aCount=TM_MCOUNT, Cratio=1.0,
                                            neutral_measure=NEUTRAL, interpretation=interp)
            erg = find_ergodic_distribution(tm_data["TranMatrix"])
        agg = compute_type_aggregates_tm_a(agent, tm_data, erg, neutral_measure=NEUTRAL,
                                           interpretation=interp)
        M_i = len(tm_data["dist_aGrid"])
        u_erg = 1.0 - float(np.sum(erg[:M_i]))
        E_p = float(compute_analytical_mean_pLvl(agent, unemployment_rate=u_erg))
        scale = agent.AgentCount * E_p
        per.append({"i": i, "DiscFac": float(agent.DiscFac), "AgentCount": int(agent.AgentCount),
                    "E_pLvl": E_p, "u_erg": u_erg, "base_C": scale * float(agg["C_splurge_nrm"]),
                    "base_Y": scale * float(agg["Income_nrm"]),
                    "bd_E_pLvl": float(bd[i]["E_pLvl"]), "dist_aGrid_top": float(np.max(bd[i]["dist_aGrid"]))})
    sum_base = sum(p["base_C"] for p in per)
    print(f"[probe] base: run_experiment_tm AggCons={base_agg:.1f}; per-atom sum={sum_base:.1f} "
          f"(ratio {sum_base/base_agg:.6f}); AggIncome={base_inc_agg:.1f}", flush=True)

    # --- experiment config, exactly as 5a before run_experiments_all_recessions_tm -----------
    eco.switch_shock_type("recession")
    eco.solve()
    null_path = [0] * act_T
    d0_path = list(np.arange(1, ne + 1) * 2) + [0] * 20
    d0_path[0:1] = (np.array(d0_path[0:1]) + 1).tolist()
    d0_path = (d0_path + [0] * act_T)[:act_T]
    agg_null = np.zeros(act_T); agg_d0 = np.zeros(act_T); inc_null = np.zeros(act_T); inc_d0 = np.zeros(act_T)
    for i, agent in enumerate(agents):
        kw = dict(Cratio=1.0, act_T=act_T, neutral_measure=NEUTRAL, check_info=None,
                  shock_type="recession", interpretation=getattr(agent, "interpretation", "CDC"),
                  # BUG-093 fix: the step matches the start's construction (bd carries it)
                  q_kernel=bd[i].get("q_method"), doob_inj=bd[i].get("doob_inj"))
        rn = propagate_experiment_tm_a(agent, bd[i]["ergodic"], null_path, bd[i]["dist_aGrid"],
                                       bd[i]["E_pLvl"], **kw)
        rd = propagate_experiment_tm_a(agent, bd[i]["ergodic"], d0_path, bd[i]["dist_aGrid"],
                                       bd[i]["E_pLvl"], **kw)
        cn, cd = np.asarray(rn["AggCons"], float), np.asarray(rd["AggCons"], float)
        yn, yd = np.asarray(rn["AggIncome"], float), np.asarray(rd["AggIncome"], float)
        agg_null += cn; agg_d0 += cd; inc_null += yn; inc_d0 += yd
        p = per[i]
        p["null_over_base"] = [float(cn[t] / p["base_C"]) for t in T_REPORT if t < act_T]
        p["d0_over_base"] = [float(cd[t] / p["base_C"]) for t in T_REPORT if t < act_T]
        p["nullY_over_baseY"] = [float(yn[t] / p["base_Y"]) for t in T_REPORT if t < act_T]
        p["base_share"] = p["base_C"] / sum_base
    tr = [t for t in T_REPORT if t < act_T]
    out = {"parametrization": parametrization, "T_age": getattr(agents[0], "T_age", None),
           "world": os.environ.get("HAFISCAL_WORLD", ""), "t_report": tr, "act_T": act_T, "ne": ne,
           "base_AggCons": base_agg, "base_AggIncome": base_inc_agg,
           "agg_null_over_base": [float(agg_null[t] / base_agg) for t in tr],
           "agg_d0_over_base": [float(agg_d0[t] / base_agg) for t in tr],
           "agg_nullY_over_baseY": [float(inc_null[t] / base_inc_agg) for t in tr],
           "agg_d0Y_over_baseY": [float(inc_d0[t] / base_inc_agg) for t in tr],
           "per_atom": per, "wall_s": time.time() - t0}
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    out["q_method"] = [str(b.get("q_method")) for b in bd][:1]
    print(f"\n[probe] {parametrization} world={out['world']!r} T_age={out['T_age']} q_method={out['q_method']}   t = {tr}")
    print(f"  AGG  null/base : " + " ".join(f"{v:.4f}" for v in out["agg_null_over_base"]))
    print(f"  AGG  d0/base   : " + " ".join(f"{v:.4f}" for v in out["agg_d0_over_base"])
          + "   (5a artifact Baseline-default: 1.0260 1.0324 1.0335 1.0333 1.0316 1.0286 1.0260)")
    print(f"  AGG  nullY/baseY: " + " ".join(f"{v:.4f}" for v in out["agg_nullY_over_baseY"]))
    print(f"  per atom (sorted by |null/base - 1| at t=0):  i  DiscFac  N  share  E_pLvl  u_erg | null/base at t | nullY/baseY at t=0,30")
    for p in sorted(per, key=lambda q: -abs(q["null_over_base"][0] - 1)):
        print(f"   {p['i']:2d} {p['DiscFac']:.4f} {p['AgentCount']:5d} {p['base_share']:.3f} {p['E_pLvl']:8.3f} {p['u_erg']:.4f} | "
              + " ".join(f"{v:.4f}" for v in p["null_over_base"]) + " | "
              + f"{p['nullY_over_baseY'][0]:.4f} {p['nullY_over_baseY'][-1]:.4f}")
    print(f"[probe] done in {time.time()-t0:.0f}s -> {out_path}", flush=True)


if __name__ == "__main__":
    _param = sys.argv[1] if len(sys.argv) > 1 else "Baseline"
    _out = sys.argv[2] if len(sys.argv) > 2 else "bug093_probe.json"
    # Parameters.py parses sys.argv positionally (Rfree, CRRA, IncUnemp) at import — scrub it
    # BEFORE importing anything from FromPandemicCode (CLAUDE.md: "patch sys.argv first").
    sys.argv = sys.argv[:1]
    main(_param, _out)
