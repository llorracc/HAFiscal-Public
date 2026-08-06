"""K-sweep on the REAL 4-state estimation agent (local2 tee-up, 2026-07-22).

The local2 plan's K=3 caveat: the drift advisory fires on the real 4-state
Markov agent (worst slice ~0.35/e-fold; K3-vs-deep cFunc 4.2e-3 at m~680)
even though the single-state proxy that graded K was silent at K=3. This
harness measures, on the SAME real agent used by the estimation/Step-5 solve
(``AggFiscalType`` + ``AggregateDemandEconomy``, hand-built IncShkDstn — the
``smoke_local2`` construction), where the advisory silences and where the
K-vs-deep cFunc delta plateaus:

    arms (College GIC-cap atom):  t40 | plslope | k3 | k6 | k8 | deep
    subcritical companion (College central beta): sub_k3 | sub_deep
    POST-FLIP NOTE (2026-07-23): a bare env now gives the measured-Q K·h̄
    DEFAULT, so the t40 (legacy) arm requires HAFISCAL_PF_DECAY_EXTRAP=0 and
    the plslope arm requires HAFISCAL_PF_DECAY_Q=slope explicitly.

``solve <label> <beta_mode>`` solves one arm under the CURRENT env (the
launcher sets the HAFISCAL_PF_DECAY_* flags per arm) and writes
``<label>.npz`` (cFunc[0](m, C=1) on m in [0, 1300]) plus ``<label>.json``
(grid actually used, per-slice Q/drift ranges, captured advisory warnings,
wall time) into ``$KSWEEP_OUT``.

``report <dir>`` grades every arm against its deep reference (cap arms vs
``deep``, sub arms vs ``sub_deep``): max relative cFunc delta on the TM range
(0, 1300] and on the extrapolation-dominated band m > 40, plus the advisory
status — the two numbers the K default decision needs.
"""
import json
import os
import sys
import time
import warnings

REPO = "/home/shared/github/llorracc/HAFiscal-Latest"
HAM = os.path.join(REPO, "Code", "HA-Models")
FPC = os.path.join(HAM, "FromPandemicCode")

# Production College central beta — the loader's value (Parameters.py betaDistr
# diagnostic under the production DiscFacEstim_College file; the local2
# re-estimate reproduces it to 4 decimals). A SUBCRITICAL atom, vs the GIC-cap
# atom gic_capped_beta(2) which sits in the concentration strip.
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
        from powerlaw_decay import PowerLawDecayLinearInterp
        import local_q_tail as lqt
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
    with warnings.catch_warnings(record=True) as wrec:
        warnings.simplefilter("always")
        eco.solve()
    wall = time.time() - t0

    # collect power-law slices (generic recursive walk, as in smoke_local2)
    seen, slices = set(), []

    def walk(o, depth=0):
        if id(o) in seen or depth > 8:
            return
        seen.add(id(o))
        if isinstance(o, PowerLawDecayLinearInterp):
            slices.append(o)
            return
        for attr in ("functions", "xInterpolators", "func", "function", "dfunc"):
            v = getattr(o, attr, None)
            if v is None:
                continue
            for it in (v if isinstance(v, (list, tuple)) else [v]):
                walk(it, depth + 1)

    for f in ag.solution[0].cFunc:
        walk(f)
    qs = [s.decay_extrap_Q for s in slices if getattr(s, "decay_extrap", False)]
    diags = [s.local_q_diag for s in slices
             if getattr(s, "local_q_diag", None) is not None]
    drifts = [d[2] for d in diags]

    m_eval = np.linspace(0.0, 1300.0, 261)
    c = np.array([float(ag.solution[0].cFunc[0](m, 1.0)) for m in m_eval])

    out = os.environ["KSWEEP_OUT"]
    np.savez(os.path.join(out, f"{label}.npz"), m=m_eval, c=c)
    meta = {
        "label": label,
        "beta_mode": beta_mode,
        "DiscFac": float(ag.DiscFac),
        "aXtraMax": float(init_college["aXtraMax"]),
        "aXtraCount": int(init_college["aXtraCount"]),
        "env": {k: os.environ.get(k) for k in
                ("HAFISCAL_PF_DECAY_EXTRAP", "HAFISCAL_PF_DECAY_Q",
                 "HAFISCAL_PF_DECAY_AMAX_MULT", "HAFISCAL_SOLVE_AMAX")},
        "n_powerlaw_slices": len(slices),
        "n_decay_active": len(qs),
        "Q_range": [min(qs), max(qs)] if qs else None,
        "drift_range": [min(drifts), max(drifts)] if drifts else None,
        "advisories": [str(w.message) for w in wrec
                       if "drift" in str(w.message).lower()
                       or "local2" in str(w.message).lower()][:10],
        "n_warnings_total": len(wrec),
        "wall_sec": wall,
        "lqt_DIAG": json.loads(json.dumps(getattr(lqt, "DIAG", {}), default=str)),
    }
    with open(os.path.join(out, f"{label}.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(f"[{label}] beta={ag.DiscFac:.6f} grid={meta['aXtraMax']:.0f}/{meta['aXtraCount']}"
          f" slices={len(slices)} Q={meta['Q_range']} drift={meta['drift_range']}"
          f" advisories={len(meta['advisories'])} wall={wall:.1f}s")


def _report(outdir):
    import numpy as np
    arms = sorted(f[:-5] for f in os.listdir(outdir) if f.endswith(".json"))
    metas = {a: json.load(open(os.path.join(outdir, a + ".json"))) for a in arms}
    curves = {a: np.load(os.path.join(outdir, a + ".npz")) for a in arms}

    def delta_vs(a, ref):
        m = curves[a]["m"]
        ca, cr = curves[a]["c"], curves[ref]["c"]
        rel = np.abs(ca - cr) / np.maximum(np.abs(cr), 1e-12)
        band = m > 40.0  # beyond the legacy solve top: extrapolation-dominated
        i_full = int(np.argmax(rel))
        i_band = int(np.argmax(np.where(band, rel, 0.0)))
        return rel[i_full], m[i_full], rel[i_band], m[i_band]

    print(f"{'arm':10s} {'grid':>10s} {'Q range':>18s} {'worst drift':>12s} "
          f"{'adv':>4s} {'max|dc|/c full':>15s} {'@m':>6s} {'m>40':>10s} {'@m':>6s}")
    for a in arms:
        mm = metas[a]
        ref = "deep" if mm["beta_mode"] == "cap" else "sub_deep"
        if a == ref:
            row_delta = ("(reference)", "", "", "")
        else:
            d_full, m_full, d_band, m_band = delta_vs(a, ref)
            row_delta = (f"{d_full:.3e}", f"{m_full:.0f}", f"{d_band:.3e}", f"{m_band:.0f}")
        qr = mm["Q_range"]
        dr = mm["drift_range"]
        print(f"{a:10s} {mm['aXtraMax']:>6.0f}/{mm['aXtraCount']:<3d} "
              f"{('[%.3f, %.3f]' % tuple(qr)) if qr else '-':>18s} "
              f"{('%+.3f' % max(dr, key=abs)) if dr else '-':>12s} "
              f"{len(mm['advisories']):>4d} "
              f"{row_delta[0]:>15s} {row_delta[1]:>6s} {row_delta[2]:>10s} {row_delta[3]:>6s}")
    print("\nadvisory texts (first per arm):")
    for a in arms:
        adv = metas[a]["advisories"]
        if adv:
            print(f"  {a}: {adv[0][:200]}")


if __name__ == "__main__":
    if sys.argv[1] == "solve":
        _solve(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "report":
        _report(sys.argv[2])
    else:
        raise SystemExit("usage: k_sweep_real_agent.py solve <label> <cap|central> | report <dir>")
