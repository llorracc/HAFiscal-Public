"""Step-2 TM-a vs MC: per-eval runtime + moment/distance parity + the
level-vs-normalized Lorenz gap, in one process.

Phase-A instrument for the simulation-speedup assessment
(`plans/20260617-1153h_step2-simulation-speedup-assessment.md`). It answers:

  (T2) How fast is one `betas_obj_func_educ_tm_a` (TM ergodic, no 50k panel)
       eval vs one MC `betas_obj_func_educ` eval, warm?
  (T3) The CRUX: on the SAME converged MC cross-section, how big is the gap
       between the LEVEL-wealth Lorenz (what the MC objective targets) and the
       NORMALIZED-wealth Lorenz (what a TM ergodic over `a` can produce)?
       This isolates the methodology gap from grid/income-process differences.
  (T4) MC vs TM-a moment + NM-objective `distance` parity at FIXED (beta, nabla,
       GICx): would the estimated point move beyond NM resolution (xtol=1e-2)?

Default OFF / read-only. Builds BOTH economies (MC via EstimAggFiscalMAIN,
TM-a via estim_phase2_tm_a with HAFISCAL_EDTYPES='' so no NM runs), under a
single explicit interpretation. Writes nothing to tracked result files.

Run (from FromPandemicCode/):
  PYTHONPATH=. HAFISCAL_SKIP_ESTIMATION=1 HAFISCAL_SERIAL=1 \
      HAFISCAL_INTERPRETATION=ESC HAFISCAL_EDTYPES= \
      <python> fti_diagnostics/bench_step2_tm_vs_mc.py
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

# MC import builds economy without running NM; TM-a import must not run NM either.
os.environ.setdefault("HAFISCAL_SKIP_ESTIMATION", "1")
os.environ.setdefault("HAFISCAL_SERIAL", "1")
os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")  # production default
os.environ["HAFISCAL_EDTYPES"] = ""  # TM-a script: build economy + objective, run NO NM

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROMPANDEMIC = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_FROMPANDEMIC, os.path.normpath(os.path.join(_FROMPANDEMIC, ".."))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from HARK.utilities import get_lorenz_shares, get_percentiles  # noqa: E402

LORENZ_PCTS = [0.2, 0.4, 0.6, 0.8]


def _fmt(arr):
    return "[" + ", ".join(f"{x:6.2f}" for x in np.atleast_1d(arr)) + "]"


def main():
    edtype = int(os.environ.get("BENCH_EDTYPE", "1"))
    educ_names = ["Dropout", "Highschool", "College"]

    print("Importing MC economy (EstimAggFiscalMAIN)...", flush=True)
    t0 = time.time()
    import EstimAggFiscalMAIN as E
    print(f"  MC build: {time.time() - t0:.1f}s", flush=True)

    from EstimParameters import DiscFacCount, data_LorenzPts, data_medianLWPI

    print("Importing TM-a economy (estim_phase2_tm_a, EDTYPES='')...", flush=True)
    t0 = time.time()
    import estim_phase2_tm_a as T
    print(f"  TM-a build: {time.time() - t0:.1f}s", flush=True)

    GICx = float(np.log(E.theGICfactor / (1 - E.theGICfactor)))

    # Capture TM-a's internal moment outputs non-invasively (it returns only
    # `distance`). It calls get_percentiles / get_lorenz_shares in its own module
    # namespace; wrap those references to record the last raw result.
    _tm_cap = {}
    _gp, _gl = T.get_percentiles, T.get_lorenz_shares

    def _gp_cap(*a, **k):
        r = _gp(*a, **k)
        _tm_cap["median"] = float(np.atleast_1d(r)[0])
        return r

    def _gl_cap(*a, **k):
        r = _gl(*a, **k)
        _tm_cap["lorenz"] = np.array(r, dtype=float)
        return r

    T.get_percentiles, T.get_lorenz_shares = _gp_cap, _gl_cap

    # Fixed (beta, nabla) probe points around the loaded calibration for this cohort.
    probes = {
        0: [(0.75, 0.30), (0.78, 0.28)],
        1: [(0.93, 0.07), (0.935, 0.065)],
        2: [(0.98, 0.015), (0.982, 0.013)],
    }[edtype]

    print(f"\n{'='*78}\nedType={edtype} ({educ_names[edtype]}); interpretation="
          f"{os.environ['HAFISCAL_INTERPRETATION']}; GICx={GICx:.4f}\n"
          f"data target: median={data_medianLWPI[edtype]:.2f}  "
          f"Lorenz={_fmt(data_LorenzPts[edtype])}\n{'='*78}", flush=True)

    mc_times, tm_times = [], []
    for k, (beta, nabla) in enumerate(probes):
        # ---- MC eval ----
        t0 = time.time()
        dist_mc = float(E.betas_obj_func_educ(beta, nabla, GICx, educ_type=edtype))
        mc_t = time.time() - t0
        # extract moments from the now-simulated panel (no re-sim)
        cohort = E.AggDemandEconomy.agents[edtype * DiscFacCount:(edtype + 1) * DiscFacCount]
        aLvl = np.concatenate([E._aLvl_for(t) for t in cohort])
        aNrm = np.concatenate([E._aNrm_for(t) for t in cohort])
        w_lvl = np.ones(len(aLvl)) / len(aLvl)
        w_nrm = np.ones(len(aNrm)) / len(aNrm)
        median_mc = 100.0 * float(get_percentiles(aNrm, weights=w_nrm, percentiles=[0.5])[0])
        lorenz_lvl_mc = 100.0 * np.array(get_lorenz_shares(aLvl, weights=w_lvl, percentiles=LORENZ_PCTS))
        lorenz_nrm_mc = 100.0 * np.array(get_lorenz_shares(aNrm, weights=w_nrm, percentiles=LORENZ_PCTS))

        # ---- TM-a eval ----
        _tm_cap.clear()
        t0 = time.time()
        dist_tm = float(T.betas_obj_func_educ_tm_a(beta, nabla, GICx, educ_type=edtype))
        tm_t = time.time() - t0
        median_tm = 100.0 * _tm_cap.get("median", float("nan"))
        lorenz_tm = 100.0 * _tm_cap.get("lorenz", np.full(4, np.nan))

        if k > 0:  # skip the first (warm-from-import) eval in the timing means
            mc_times.append(mc_t)
            tm_times.append(tm_t)

        print(f"\n--- probe {k}: beta={beta:.4f} nabla={nabla:.4f} ---", flush=True)
        print(f"  TIME      MC {mc_t:7.2f}s   TM-a {tm_t:7.2f}s   "
              f"(MC/TM-a = {mc_t/tm_t:5.1f}x)", flush=True)
        print(f"  medianLWPI (normalized; method-invariant):", flush=True)
        print(f"            MC {median_mc:7.2f}   TM-a {median_tm:7.2f}   "
              f"diff {median_mc - median_tm:+6.2f} ({100*(median_mc-median_tm)/median_mc:+5.1f}%)",
              flush=True)
        print(f"  Lorenz LEVEL    (MC objective target): MC {_fmt(lorenz_lvl_mc)}", flush=True)
        print(f"  Lorenz NORMALIZED (TM-a producible):", flush=True)
        print(f"            MC-panel {_fmt(lorenz_nrm_mc)}   TM-a {_fmt(lorenz_tm)}", flush=True)
        print(f"  *** LEVEL-vs-NORMALIZED gap on the SAME MC panel "
              f"(p20/40/60/80): {_fmt(lorenz_lvl_mc - lorenz_nrm_mc)}  "
              f"(this is the methodology crux) ***", flush=True)
        print(f"  TM-a-vs-MC NORMALIZED Lorenz gap (grid/income only): "
              f"{_fmt(lorenz_nrm_mc - lorenz_tm)}", flush=True)
        print(f"  NM distance:  MC {dist_mc:.4f}   TM-a {dist_tm:.4f}   "
              f"diff {dist_mc - dist_tm:+.4f}", flush=True)

    if mc_times:
        mc_m, tm_m = float(np.mean(mc_times)), float(np.mean(tm_times))
        print(f"\n{'='*78}", flush=True)
        print(f"WARM eval time mean: MC {mc_m:.2f}s   TM-a {tm_m:.2f}s   "
              f"=> TM-a is {mc_m/tm_m:.1f}x faster per eval", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
