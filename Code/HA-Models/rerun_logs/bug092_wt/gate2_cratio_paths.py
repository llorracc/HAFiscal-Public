"""Gate 2: does the weighted panel's REALIZED recession consumption path reproduce the TM's?
Per duration d: panel ratio_t = sum_i w_i cLvl_it(d) / base AggCons_t vs the TM's AggCons_t(d)/base
(no-AD: Figures/Baseline_qdoob/recession_all_results.csv; AD: ..._AD.csv). Reports the max abs gap over
t<12 for the first 3 durations, weighted panel vs equal-weight panel."""
import pickle, sys, numpy as np, os
FPC = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode"
def tm_paths(kind, scen="recession"):
    b = pickle.load(open(f"{FPC}/Figures/Baseline_qdoob/base_results.csv", "rb")); base = np.asarray(b["AggCons"], float)
    r = pickle.load(open(f"{FPC}/Figures/Baseline_qdoob/{scen}_all_results{kind}.csv", "rb"))
    return [np.asarray(x["AggCons"], float) / base[:len(x["AggCons"])] for x in r]
def panel_paths(tag, kind, scen="recession"):
    d = f"{FPC}/welfare6_scenario_results_Baseline_{tag}_seed0"
    base = pickle.load(open(f"{d}/base.pkl", "rb")); rec = pickle.load(open(f"{d}/{scen}{kind}.pkl", "rb"))
    w = rec.get("agent_weights"); w = np.ones(base["cLvl_all_splurge"].shape[1]) if w is None else np.asarray(w, float)
    base_agg = np.asarray(base["cLvl_all_splurge"], float) @ w
    return [np.asarray(p, float) @ w / base_agg[:len(p)] for p in rec["per_dur_cLvl_all_splurge"]], rec.get("agent_weights") is not None
for scen in ("recession", "recessionCheck", "recessionUI", "recessionTaxCut"):
  for kind, label in (("", "no-AD"), ("_AD", "AD")):
    tm = tm_paths(kind, scen)
    for tag in sys.argv[1:]:
        try:
            pp, weighted = panel_paths(tag, kind, scen)
        except Exception as e:
            print(f"{scen} {tag} {label}: {e}"); continue
        gaps = [np.max(np.abs(pp[d][:12] - tm[d][:12])) for d in range(3)]
        # the check's own response: (policy path - recession path) at t=0, panel vs TM
        print(f"{scen:16s} {label:6s} {tag:8s} w={str(weighted)[0]}: max|panel-TM| over t<12, dur 0..2 = " + " ".join(f"{g:.4f}" for g in gaps)
              + f" | dur0 t=0..3 panel " + " ".join(f"{v:.4f}" for v in pp[0][:4]) + " TM " + " ".join(f"{v:.4f}" for v in tm[0][:4]))
