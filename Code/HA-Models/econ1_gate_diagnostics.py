#!/usr/bin/env python3
"""Econ-1 gate diagnostics (2026-08-28): compare per-seed welfare batteries arm against arm.

  compare  PREFIX REF ARM[,ARM..]   the nine welfare cells: across-seed mean, SE, %, difference, SE ratio, CRN-paired t
  decomp   PREFIX ARM[,ARM..]       the UI cell decomposed: realized outlay (denominator), numerator, recipients per quarter,
                                    recipients' income, ever-in-extension share, unemployment share (means, CV %)
  flows    PREFIX ARM[,ARM..] [T]   realized micro-state transition frequencies by source state over the first T quarters
                                    (the job-finding rate is the same in every unemployed state, so the "stay" frequency
                                    must agree across u1Q/u2Q/u3Q -- a rounding bias shows up as a state-size-dependent gap)

Arms are Tables/<PREFIX>_<ARM>_seed<K>/welfare6_parallel_summary.json and the matching
welfare6_scenario_results_<PREFIX>_<ARM>_seed<K>/ pickles (recessionUI_AD, recession_AD). Example:
  python econ1_gate_diagnostics.py compare HS_Only_gate plainM pstratM,pastratM
  python econ1_gate_diagnostics.py compare Baseline_uiA plainH plainM,pstratM
"""
import glob, json, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPC = os.path.join(HERE, "FromPandemicCode")
T = os.path.join(FPC, "Tables")
CELLS = ["check_rec_AD", "ui_rec_AD", "taxcut_rec_AD", "check_rec", "ui_rec", "taxcut_rec", "check_norec", "taxcut_norec"]
EXT = {3, 4, 5}      # calendar encoding, window policy: {e, u1Q, u2Q, u3Q, u4Q, u5Q, noBen} -> extension states 3..5
J = 7


def load(prefix, arm):
    fs = sorted(glob.glob(os.path.join(T, f"{prefix}_{arm}_seed*", "welfare6_parallel_summary.json")))
    return {os.path.basename(os.path.dirname(f)).rsplit("_seed", 1)[1]: json.load(open(f))["welfare6"] for f in fs}


def compare(prefix, ref, arms):
    P = load(prefix, ref)
    for arm in arms:
        Q = load(prefix, arm)
        if not Q:
            print(f"{prefix} {arm}: no results yet"); continue
        com = sorted(set(P) & set(Q))
        print(f"\n{prefix}: {ref} S={len(P)}  {arm} S={len(Q)}  (paired on {len(com)} common seeds)")
        print(f"{'cell':14s} {ref + ' mean':>12s} {'SE':>7s} {'%':>5s} | {arm + ' mean':>12s} {'SE':>7s} {'%':>5s} | "
              f"{'diff':>7s} {'diff/SE':>8s} {'SE ratio':>9s} {'paired t':>9s}")
        for k in CELLS:
            a = np.array([P[s][k] for s in sorted(P)]); b = np.array([Q[s][k] for s in sorted(Q)])
            sa = a.std(ddof=1) / np.sqrt(len(a)); sb = b.std(ddof=1) / np.sqrt(len(b))
            d = b.mean() - a.mean(); sd = np.sqrt(sa ** 2 + sb ** 2)
            pd = np.array([Q[s][k] - P[s][k] for s in com])
            pt = pd.mean() / (pd.std(ddof=1) / np.sqrt(len(pd))) if len(pd) > 2 and pd.std(ddof=1) > 0 else float("nan")
            print(f"{k:14s} {a.mean():12.4f} {sa:7.4f} {100 * sa / a.mean():5.2f} | {b.mean():12.4f} {sb:7.4f} "
                  f"{100 * sb / b.mean():5.2f} | {100 * d / a.mean():+6.2f}% {d / sd:8.2f} {sb / sa:9.2f} {pt:9.2f}")


def _panels(prefix, arm):
    for k in range(20):
        d = os.path.join(FPC, f"welfare6_scenario_results_{prefix}_{arm}_seed{k}")
        s = os.path.join(T, f"{prefix}_{arm}_seed{k}", "welfare6_parallel_summary.json")
        if os.path.exists(os.path.join(d, "recessionUI_AD.pkl")) and os.path.exists(s):
            yield k, d, s


def decomp(prefix, arms):
    keys = ["cell", "outlay", "num", "recip", "Ep", "Ep0", "ever", "unemp"]
    rows = {}
    for arm in arms:
        rec = []
        for k, d, s in _panels(prefix, arm):
            u = pickle.load(open(os.path.join(d, "recessionUI_AD.pkl"), "rb")); r = pickle.load(open(os.path.join(d, "recession_AD.pkl"), "rb"))
            cell = json.load(open(s))["welfare6"]["ui_rec_AD"]
            outlay = float(np.sum(np.asarray(u["AggIncome"]) - np.asarray(r["AggIncome"])))
            M = np.asarray(u["Mrkv_hist_bs"]); P = np.asarray(u["pLvl_all_bs"]); w = np.asarray(u["agent_weights"]); micro = M % J
            ext = np.isin(micro, list(EXT)); Tq = min(12, M.shape[0])
            recip_q = np.array([(w * ext[t]).sum() / w.sum() for t in range(Tq)])
            Ep = np.array([(w * ext[t] * P[t]).sum() / max((w * ext[t]).sum(), 1e-12) for t in range(Tq) if ext[t].any()])
            ever = ext[:Tq].any(axis=0); Ep0 = (w * ever * P[0]).sum() / (w * ever).sum()
            unemp_q = np.array([(w * (micro[t] >= 1)).sum() / w.sum() for t in range(Tq)])
            rec.append(dict(cell=cell, outlay=outlay, num=cell * outlay, recip=recip_q.sum(), Ep=Ep.mean(), Ep0=Ep0,
                            ever=(w * ever).sum() / w.sum(), unemp=unemp_q.mean()))
        rows[arm] = np.array([[x[k] for k in keys] for x in rec])
    print(f"{'arm':9s} S  " + "  ".join(f"{k:>16s}" for k in keys) + "\n" + " " * 12 + "  ".join(f"{'mean (CV %)':>16s}" for _ in keys))
    for arm in arms:
        a = rows[arm]
        if len(a) == 0:
            print(f"{arm:9s}  0"); continue
        print(f"{arm:9s} {len(a):2d} " + "  ".join(f"{a[:, i].mean():9.4f} ({100 * a[:, i].std(ddof=1) / abs(a[:, i].mean()):4.2f})" for i in range(len(keys))))
    b = rows[arms[0]]
    for arm in arms[1:]:
        a = rows[arm]
        if len(a) == 0 or len(b) == 0:
            continue
        print(f"{arm} vs {arms[0]}: " + "  ".join(
            f"{k} {100 * (a[:, i].mean() / b[:, i].mean() - 1):+.2f}% (t={(a[:, i].mean() - b[:, i].mean()) / np.sqrt(a[:, i].var(ddof=1) / len(a) + b[:, i].var(ddof=1) / len(b)):+.2f})"
            for i, k in enumerate(keys)))


def flows(prefix, arms, tmax=12):
    res = {}
    for arm in arms:
        out = []
        for k, d, s in _panels(prefix, arm):
            M = np.asarray(pickle.load(open(os.path.join(d, "recessionUI_AD.pkl"), "rb"))["Mrkv_hist_bs"]) % J
            C = np.zeros((J, J))
            for t in range(1, tmax + 1):
                np.add.at(C, (M[t - 1], M[t]), 1)
            out.append(C)
        res[arm] = np.array(out)
    for j in range(4):
        print(f"\nfrom micro state {j}:")
        for arm in arms:
            C = res[arm]
            if len(C) == 0:
                continue
            rows = C[:, j, :] / C[:, j, :].sum(axis=1, keepdims=True); n = C[:, j, :].sum(axis=1).mean()
            m = rows.mean(axis=0); se = rows.std(axis=0, ddof=1) / np.sqrt(len(rows))
            print(f"  {arm:9s} S={len(rows)} n/seed={n:7.0f}  " + "  ".join(f"->{k}: {m[k]:.4f}±{se[k]:.4f}" for k in range(J) if m[k] > 0.0005))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "compare":
        compare(sys.argv[2], sys.argv[3], sys.argv[4].split(","))
    elif cmd == "decomp":
        decomp(sys.argv[2], sys.argv[3].split(","))
    elif cmd == "flows":
        flows(sys.argv[2], sys.argv[3].split(","), int(sys.argv[4]) if len(sys.argv) > 4 else 12)
    else:
        print(__doc__); sys.exit(2)
