"""Count-sweep: how solve speed & in-sample accuracy depend on aXtraCount.

Real 4-state College agents (the k_sweep_real_agent construction), two strands
(POST-FLIP vocabulary, 2026-07-23 — the launcher must set env explicitly, since
a bare env now gives the NEW default):
  T = LEGACY (HAFISCAL_PF_DECAY_EXTRAP=0: aMax=40, naive-linear tail),
      counts set via HAFISCAL_AXTRA_COUNT
  L = DEFAULT (measured-Q power-law, K=3 -> aMax=591; pin
      HAFISCAL_PF_DECAY_EXTRAP=1 HAFISCAL_PF_DECAY_Q=measured for determinism),
      same env base counts (scaled by grid_sizing.solve_grid_count, e.g. 48 -> 61)
solve <label> <cap|central>: solve under current env, dump in-sample cFunc + meta.
report <dir>: per (strand, atom), grade each count against the densest arm by
  max relative cFunc delta on bulk [0.05,6] (calibration-moment region),
  mid (6,40], upper (40, aMax] (L strand only), plus solve wall.
"""
import json
import os
import sys
import time

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
HAM = os.path.join(REPO, "Code", "HA-Models")
FPC = os.path.join(HAM, "FromPandemicCode")
CENTRAL_COLLEGE_BETA = 0.9919255740493225


def _solve(label, beta_mode):
    for p in (HAM, FPC):
        sys.path.insert(0, p)
    os.chdir(FPC)
    os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")
    saved = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        import numpy as np
        import EstimParameters as ep
        from EstimParameters import (init_college, init_ADEconomy,
                                     gic_capped_beta, theGICfactor)
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        from HARK.distributions import DiscreteDistribution
    finally:
        sys.argv = saved

    ag = AggFiscalType(**init_college)
    ag.cycles = 0
    eco = AggregateDemandEconomy(**init_ADEconomy)
    ag.get_economy_data(eco)
    Du = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
    Dn = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Du] * ep.UBspell_normal + [Dn]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.DiscFac = (gic_capped_beta(2, theGICfactor) if beta_mode == "cap"
                  else CENTRAL_COLLEGE_BETA)
    ag.AgentCount = 1
    ag.tm_a_indexed = True
    eco.agents = [ag]
    t0 = time.time()
    eco.solve()
    wall = time.time() - t0

    aMax = float(init_college["aXtraMax"])
    segs = [np.geomspace(0.05, 6.0, 60), np.geomspace(6.2, 40.0, 40)]
    if aMax > 41.0:
        segs.append(np.geomspace(41.0, aMax * 0.999, 60))
    m_eval = np.concatenate(segs)
    c = np.array([float(ag.solution[0].cFunc[0](m, 1.0)) for m in m_eval])
    out = os.environ["CSWEEP_OUT"]
    np.savez(os.path.join(out, f"{label}.npz"), m=m_eval, c=c)
    meta = {"label": label, "beta_mode": beta_mode, "DiscFac": float(ag.DiscFac),
            "aXtraMax": aMax, "aXtraCount": int(init_college["aXtraCount"]),
            "wall_sec": wall}
    with open(os.path.join(out, f"{label}.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(f"[{label}] count={meta['aXtraCount']} aMax={aMax:.0f} wall={wall:.1f}s")


def _report(outdir):
    import numpy as np
    metas = {}
    for f in os.listdir(outdir):
        if f.endswith(".json"):
            metas[f[:-5]] = json.load(open(os.path.join(outdir, f)))
    groups = {}
    for lab, m in metas.items():
        strand = lab.split("_")[0][0]  # T or L
        groups.setdefault((strand, m["beta_mode"]), []).append(lab)
    print(f"{'arm':12s} {'count':>5s} {'wall_s':>7s} {'bulk[0.05,6]':>13s} "
          f"{'mid(6,40]':>11s} {'upper(40,aMax]':>15s}")
    for key in sorted(groups):
        labs = sorted(groups[key], key=lambda l: metas[l]["aXtraCount"])
        ref = labs[-1]
        mref = np.load(os.path.join(outdir, ref + ".npz"))
        for lab in labs:
            d = np.load(os.path.join(outdir, lab + ".npz"))
            m, c = d["m"], d["c"]
            cr = np.interp(m, mref["m"], mref["c"])
            rel = np.abs(c - cr) / np.maximum(np.abs(cr), 1e-12)
            def seg(lo, hi):
                mask = (m >= lo) & (m <= hi)
                return f"{np.max(rel[mask]):.2e}" if mask.any() else "-"
            tag = " (ref)" if lab == ref else ""
            print(f"{lab+tag:12s} {metas[lab]['aXtraCount']:>5d} "
                  f"{metas[lab]['wall_sec']:>7.1f} {seg(0.05, 6):>13s} "
                  f"{seg(6.001, 40):>11s} {seg(40.001, 1e9):>15s}")
        print()


if __name__ == "__main__":
    if sys.argv[1] == "solve":
        _solve(sys.argv[2], sys.argv[3])
    else:
        _report(sys.argv[2])
