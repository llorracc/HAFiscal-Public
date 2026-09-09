"""ALK G1: does adding a few knots just BELOW aXtraMax recover the deep-truth Q?

plans/20260725_added-local-knots-vs-count_plan.md, gate G1.

H_ALK: the NestFac=3 grid makes the top knots span an enormous range, so the
two-secant Q is a chord across curvature rather than a local estimate. A few
knots placed deliberately below the top should give a genuinely local secant.

DESIGN (owner's constraints):
  * >= 3 added knots, ALL strictly below aXtraMax. Never the top knot itself:
    it carries an endpoint artifact (+0.03..0.07 at every grid top, F5), so a
    window touching it is contaminated by grid-edge effects, not curvature.
  * knots geometric in (x+h) spanning s e-folds below the top pivot, so the
    two secant windows are equal in the estimator's own coordinate.
  * SWEEP the span s: too WIDE re-creates the artifact under test; too NARROW
    puts the gap differences into solver-tolerance noise. The admissible window
    is the deliverable (an EMPTY window refutes H_ALK for that atom).

Injection uses HARK's existing ``aXtraExtra`` (already used in production to
force two bottom knots) — no new grid machinery, and the base grid is untouched
so this is purely additive.

Reuses: the k_sweep_real_agent agent construction (same College GIC-cap atom as
the production estimation solve) and local_q_tail (THE estimator; ALK is a knot
placement, not a second estimator).

Usage:
  python alk_g1_sweep.py solve <label> <K_add> <span>   # one arm -> <label>.json
  python alk_g1_sweep.py report <dir>
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HAM = os.path.normpath(os.path.join(HERE, ".."))
FPC = os.path.join(HAM, "FromPandemicCode")

CENTRAL_COLLEGE_BETA = 0.9919255740493225
#: The highest UNCAPPED College atom ("Ctop", betaDistr index 4). Distinct from
#: the GIC-cap atom (1.005369): subcritical, continued-Kesten root ~0.69 vs the
#: cap's 1.47 (decay_form/kesten_roots.py), so its tail curvature — and hence the
#: local-vs-chord question ALK asks — is a genuinely different test.
CTOP_COLLEGE_BETA = 0.99859
#: HS pole (G2). HS's betaDistr is [0.8702 .. 1.0011] with 0/7 at the cap, so its
#: TOP atom is uncapped and is the direct analogue of College-TOP.
HS_TOP_BETA = 1.0011
HS_CENTRAL_BETA = 0.9356


def _alk_knots(x_top, h, K_add, span):
    """K_add knots geometric in (x+h), spanning `span` e-folds below the top.

    Strictly below x_top: the deepest sits at (x_top+h)*exp(-span), the shallowest
    at exp(-span/K_add) — never AT the top knot (F5 endpoint artifact).
    Returned in ascending x.
    """
    import numpy as np
    piv = x_top + h
    fr = np.exp(-span * np.arange(1, K_add + 1) / K_add)   # (0,1), descending
    return np.sort(piv * fr - h)


def _solve(label, K_add, span, beta_mode="cap"):
    for p in (HAM, FPC):
        sys.path.insert(0, p)
    os.chdir(FPC)
    os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")

    saved = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        import numpy as np
        import EstimParameters as ep
        from EstimParameters import (init_college, init_highschool, init_ADEconomy,
                                     gic_capped_beta, theGICfactor)
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        from HARK.distributions import DiscreteDistribution
        import local_q_tail as lqt
    finally:
        sys.argv = saved

    # G2 second pole: HS is a different education group, so swap the WHOLE
    # parameter block (its own aXtraMax/count come from the same SST rule).
    init = dict(init_highschool if beta_mode.startswith("hs") else init_college)
    # G4: base-count override (ALK_COUNT). The whole point of ALK was the claim
    # that a few top knots could substitute for a large base count, so G4 must be
    # able to REDUCE the base and add ALK on top.
    _c = os.environ.get("ALK_COUNT")
    if _c:
        init["aXtraCount"] = int(_c)
    x_top = float(init["aXtraMax"])
    # h for the cap atom: the PF human wealth used by the attach. Recover it the
    # same way the attach does, from the solved slice below; for knot PLACEMENT a
    # close approximation is enough (knots need only be well-positioned, and the
    # estimator uses the true h afterwards).
    R = float(np.atleast_1d(init["Rfree"]).ravel()[0])
    G = float(np.atleast_1d(init["PermGroFac"]).ravel()[0])
    h_approx = G / max(R - G, 1e-9)

    extra = list(init.get("aXtraExtra") or [])
    alk = []
    if K_add > 0:
        alk = [float(v) for v in _alk_knots(x_top, h_approx, K_add, span) if v > 0]
        extra = extra + alk
    init["aXtraExtra"] = extra or None

    ag = AggFiscalType(**init)
    ag.cycles = 0
    eco = AggregateDemandEconomy(**init_ADEconomy)
    ag.get_economy_data(eco)
    Du = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
    Dn = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Du] * ep.UBspell_normal + [Dn]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.DiscFac = {"cap": gic_capped_beta(2, theGICfactor),
                  "ctop": CTOP_COLLEGE_BETA,
                  "central": CENTRAL_COLLEGE_BETA,
                  "hs_top": HS_TOP_BETA,
                  "hs_central": HS_CENTRAL_BETA}[beta_mode]
    ag.AgentCount = 1
    ag.tm_a_indexed = True
    eco.agents = [ag]

    t0 = time.time()
    eco.solve()
    wall = time.time() - t0

    # The cFunc is a LowerEnvelope2D (the 2-D AD structure), so walk down to the
    # per-(state,C-slice) PowerLawDecayLinearInterp — same extraction as
    # k_sweep_real_agent, which is why that helper exists.
    from powerlaw_decay import PowerLawDecayLinearInterp
    slices, seen = [], set()

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

    sol = ag.solution[0]
    for f in (sol.cFunc if isinstance(sol.cFunc, list) else [sol.cFunc]):
        walk(f)
    if not slices:
        raise RuntimeError("no PowerLawDecayLinearInterp slice found - is the "
                           "power-law attach active? (needs the default env)")
    cf = slices[0]
    # The attach's own pivot/limits, so Q is measured exactly as production does.
    h_true = float(getattr(cf, "decay_extrap_pivot", h_approx + x_top)) - x_top
    mpc = float(getattr(cf, "slope_limit", float("nan")))
    m = np.asarray(cf.x_list, dtype=float)
    c = np.asarray(cf.y_list, dtype=float)
    res_nslices = len(slices)

    res = {"label": label, "K_add": K_add, "span": span, "wall_s": wall,
           "beta_mode": beta_mode, "DiscFac": float(ag.DiscFac),
           "aXtraMax": x_top, "n_knots": int(m.size), "alk_knots": alk, "n_slices": res_nslices,
           "h_used": h_true, "mpc_min": mpc,
           "Q_attach": float(getattr(cf, "decay_extrap_Q", float("nan")))}

    # Production estimator on ALL knots (what ships today)
    res["prod"] = lqt.local_q_from_knots(m, c, h_true, mpc)
    # ALK estimator: restrict to the ADDED interior knots (never the top knot)
    if alk:
        # NB: `alk` are aXtra (asset) coordinates, but x_list is in m
        # (EGM maps each a -> m = a + c(a)), so value-matching finds nothing.
        # The grids correspond by INDEX: x_list = [prepended 0] + sorted(aXtraGrid),
        # so locate each added knot's rank in the reconstructed aXtraGrid.
        from HARK.utilities import make_assets_grid
        full = np.asarray(make_assets_grid(
            init["aXtraMin"], init["aXtraMax"], init["aXtraCount"],
            init["aXtraExtra"], init["aXtraNestFac"]), dtype=float)
        off = int(m.size - full.size)     # 1 when the attach prepends a 0 knot
        sel = np.zeros(m.size, dtype=bool)
        for a in alk:
            k = int(np.argmin(np.abs(full - a))) + off
            if 0 <= k < m.size:
                sel[k] = True
        sel &= m < (m[-1] - 1e-12)        # STRICTLY below the top knot (F5)
        res["alk_index_offset"] = off
        res["alk_m_selected"] = [float(v) for v in m[sel]]
        if sel.sum() >= 3:
            res["alk"] = lqt.local_q_from_knots(m[sel], c[sel], h_true, mpc)
        else:
            res["alk"] = {"ok": False, "reason": f"only {int(sel.sum())} added knots resolved"}
    # G7 (owner challenge 2026-07-25): the metric that MATTERS is the accuracy of
    # the ERGODIC DISTRIBUTION, not of the cFunc. cFunc sup-norm is a solve-side
    # PROXY: errors enter the ergodic through the policy a'(a)=a+y-c(m) and the
    # stationary distribution is a fixed point of that operator, so pointwise
    # error can cancel OR compound. Measure the target directly. The TM-a ergodic
    # is deterministic and ~0.03s, so this is nearly free. Built on a FIXED
    # distribution grid so arms differing only in SOLVE count are comparable.
    try:
        from tm_methods import compute_baseline_tm_data
        for _a in eco.agents:
            _a.tm_a_indexed = True
        _bd = compute_baseline_tm_data(eco, dist_aGrid_count=200, neutral_measure=False,
                                       verbose=False)
        _erg = np.asarray(_bd[0]["ergodic"], dtype=float)
        _grid = np.asarray(_bd[0]["dist_aGrid"], dtype=float)
        _A = _grid.size
        _pa = _erg.reshape(len(_erg)//_A, _A).sum(axis=0)
        _pa = _pa/_pa.sum()
        _cdf = np.cumsum(_pa)
        def _q(u):
            return float(np.interp(u, _cdf/_cdf[-1], _grid))
        _Ea = float(np.sum(_pa*_grid))
        # Lorenz shares: fraction of total wealth held below each population quantile
        _w = _pa*_grid; _wc = np.cumsum(_w)/max(_w.sum(), 1e-300)
        res["ergodic"] = {
            "E_a": _Ea,
            "sd_a": float(np.sqrt(max(np.sum(_pa*_grid**2) - _Ea**2, 0.0))),
            "median": _q(0.5), "q90": _q(0.90), "q99": _q(0.99), "q999": _q(0.999),
            "lorenz_top1": float(1.0 - np.interp(0.99, _cdf/_cdf[-1], _wc)),
            "lorenz_top10": float(1.0 - np.interp(0.90, _cdf/_cdf[-1], _wc)),
            "mass_above_100": float(_pa[_grid > 100].sum()),
        }
    except Exception as _e:
        res["ergodic"] = {"error": repr(_e)}

    # G4 probe: cFunc on a FIXED m-grid so different-count arms are comparable.
    probe = np.concatenate([np.linspace(0.05, 6.0, 240),
                            np.geomspace(6.0, 40.0, 160),
                            np.geomspace(40.0, x_top, 200)])
    res["probe_m"] = [float(v) for v in probe]
    res["probe_c"] = [float(v) for v in np.asarray(cf(probe), dtype=float)]
    res["aXtraCount"] = int(init["aXtraCount"])

    out = os.environ.get("ALK_OUT", "/tmp/alk_g1")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, f"{label}.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    q = res.get("alk", {}).get("Q")
    print(f"[{label}] K_add={K_add} span={span} knots={m.size} "
          f"Q_prod={res['prod'].get('Q')} Q_alk={q} wall={wall:.1f}s", flush=True)


def _report(d):
    import numpy as np
    rows = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            rows.append(json.load(open(os.path.join(d, f))))
    ref = next((r for r in rows if r["label"] == "deep"), None)
    qref = (ref or {}).get("prod", {}).get("Q")
    print(f"{'label':16s} {'K':>3s} {'span':>5s} {'knots':>6s} {'Q_prod':>9s} "
          f"{'Q_alk':>9s} {'drift_alk':>10s} {'|dQ vs deep|':>12s} {'wall':>7s}")
    for r in sorted(rows, key=lambda x: (x["K_add"], x["span"])):
        a = r.get("alk") or {}
        q = a.get("Q")
        dq = (abs(q - qref) if (q is not None and qref is not None) else None)
        print(f"{r['label']:16s} {r['K_add']:>3d} {r['span']:>5.2f} {r['n_knots']:>6d} "
              f"{_f(r['prod'].get('Q')):>9s} {_f(q):>9s} {_f(a.get('drift')):>10s} "
              f"{_f(dq):>12s} {r['wall_s']:>6.1f}s")
    if qref is not None:
        print(f"\ndeep-truth Q (all-knot estimator on the deep arm) = {qref:.4f}")


def _f(v):
    return "—" if v is None else f"{float(v):.4f}"


if __name__ == "__main__":
    if sys.argv[1] == "solve":
        _solve(sys.argv[2], int(sys.argv[3]), float(sys.argv[4]),
               sys.argv[5] if len(sys.argv) > 5 else "cap")
    else:
        _report(sys.argv[2])
