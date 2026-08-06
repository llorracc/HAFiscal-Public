"""G7: ERGODIC-MOMENT convergence vs SOLVE-grid count (the metric that matters).

plans/20260725_added-local-knots-vs-count_plan.md §10.

WHY. The count basis 48->96->192 was chosen on max-relative cFunc error — a
SOLVE-SIDE PROXY. What the estimation and the multipliers actually consume is the
ERGODIC DISTRIBUTION. cFunc error enters it through the policy a'(a)=a+y-c(m),
and the stationary distribution is a FIXED POINT of that operator, so pointwise
error can cancel OR compound. This measures the target directly.

WHAT, precisely. Re-runs the PRODUCTION Step-2 a-indexed objective path at fixed
production (beta, nabla, GICx) — the same `betas_obj_func_educ_tm_a` internals the
count doc's §4 used — but records the MOMENTS rather than the aggregated distance
scalar. Aggregation can mask offsetting moment errors (a grid can look converged
on the scalar while E[a] and the top Lorenz share move in compensating
directions); detecting that is the point of this gate.

Moments recorded, per education group, from the pooled ergodic (a_array, w_array):
  medianLWPI + the four LorenzPts  <- the ACTUAL estimation targets
  E[a], sd[a], q90/q99/q99.9, top-1%/top-10% wealth shares, mass above 100
The DISTRIBUTION grid is held FIXED (HAFISCAL_TM_ACOUNT), so only the SOLVE count
(HAFISCAL_AXTRA_COUNT) varies between arms.

Usage:  HAFISCAL_AXTRA_COUNT=96 python g7_ergodic_moments.py <label> <outdir>
"""
import os
import sys

os.environ["HAFISCAL_EDTYPES"] = ""            # import module, skip its estimation loop
os.environ["HAFISCAL_INTERPRETATION"] = "ESC"
os.environ["HAFISCAL_QUIET_BETADISTR"] = "1"
os.environ.setdefault("HAFISCAL_GICX_MODE", "hardcoded")
os.environ.setdefault("HAFISCAL_TM_ACOUNT", "200")   # FIXED dist grid across arms

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
HAM = os.path.join(REPO, "Code", "HA-Models")
FPC = os.path.join(HAM, "FromPandemicCode")
for p in (HAM, FPC):
    sys.path.insert(0, p)
os.chdir(FPC)

_saved = sys.argv
sys.argv = [sys.argv[0]]
try:
    import numpy as np
    import estim_phase2_tm_a as est
    from HARK.utilities import get_percentiles, get_lorenz_shares
finally:
    sys.argv = _saved

LABEL = _saved[1]
OUTDIR = _saved[2] if len(_saved) > 2 else "/tmp/g7"


def _moments(a, w):
    """Moments of the pooled ergodic wealth distribution (a with weights w)."""
    a = np.asarray(a, dtype=float)
    w = np.asarray(w, dtype=float)
    w = w / w.sum()
    Ea = float(np.sum(w * a))
    out = {
        "E_a": Ea,
        "sd_a": float(np.sqrt(max(np.sum(w * a * a) - Ea * Ea, 0.0))),
        "medianLWPI": float(100.0 * get_percentiles(a, weights=w, percentiles=[0.5])[0]),
        "q90": float(get_percentiles(a, weights=w, percentiles=[0.90])[0]),
        "q99": float(get_percentiles(a, weights=w, percentiles=[0.99])[0]),
        "q999": float(get_percentiles(a, weights=w, percentiles=[0.999])[0]),
        "mass_above_100": float(w[a > 100].sum()),
    }
    lp = 100.0 * np.asarray(get_lorenz_shares(a, weights=w,
                                              percentiles=[0.2, 0.4, 0.6, 0.8]))
    for i, p in enumerate((20, 40, 60, 80)):
        out[f"lorenz_p{p}"] = float(lp[i])
    # top shares: 1 - (share held below the 99th/90th pctile)
    lt = 100.0 * np.asarray(get_lorenz_shares(a, weights=w, percentiles=[0.90, 0.99]))
    out["top10_share"] = float(100.0 - lt[0])
    out["top1_share"] = float(100.0 - lt[1])
    return out


def main():
    import json
    # Patch the objective's moment site: capture (a_array, w_array) as it is built,
    # so we measure EXACTLY the distribution the production objective uses.
    captured = {}
    _orig_pct = est.get_percentiles

    def _spy(a_array, weights=None, percentiles=None):
        if "a" not in captured and weights is not None:
            captured["a"], captured["w"] = np.asarray(a_array), np.asarray(weights)
        return _orig_pct(a_array, weights=weights, percentiles=percentiles)

    est.get_percentiles = _spy

    res = {"label": LABEL,
           "axtra_count": os.environ.get("HAFISCAL_AXTRA_COUNT", "(default)"),
           "tm_acount": os.environ.get("HAFISCAL_TM_ACOUNT"),
           "groups": {}}
    for e, name in ((0, "dropout"), (1, "highschool"), (2, "college")):
        path = os.path.join(
            HAM, "Results",
            f"DiscFacEstim_CRRA_2.0_R_1.01_edType{e}_TM_a_ESC.txt")
        with open(path) as fh:
            rec = None
            for line in fh:
                if line.strip().startswith("{"):
                    rec = eval(line, {"np": __import__("numpy"), "__builtins__": {}})
        beta, nabla = rec["beta"], rec["nabla"]
        gicx = rec.get("GICx", 7.60040233450051)
        captured.clear()
        d = est.betas_obj_func_educ_tm_a(beta, nabla, gicx, educ_type=e,
                                         print_mode=False)
        g = {"distance": float(d), "beta": float(beta), "nabla": float(nabla)}
        if "a" in captured:
            g.update(_moments(captured["a"], captured["w"]))
        res["groups"][name] = g
        print(f"  [{LABEL}] {name}: distance={d:.6f} "
              f"E[a]={g.get('E_a', float('nan')):.4f} "
              f"median={g.get('medianLWPI', float('nan')):.4f} "
              f"top1={g.get('top1_share', float('nan')):.3f}", flush=True)

    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, f"{LABEL}.json"), "w") as fh:
        json.dump(res, fh, indent=1)


if __name__ == "__main__":
    main()
