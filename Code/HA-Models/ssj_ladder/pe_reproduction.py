"""The owner's rule as a measurement: AD-off HANK must reproduce the PE model.

    python -m ssj_ladder.pe_reproduction pe --seed K [--out DIR]
        runs the PE side: build_and_solve('Baseline', seed_offset=K), the base
        scenario, then the Check-without-recession scenario (the PE model's own
        non-AD check experiment around its ergodic baseline), and saves the
        CRN-paired AggCons / AggIncome paths.

    python -m ssj_ladder.pe_reproduction compare [--out DIR]
        loads every saved PE seed plus the saved production household Jacobians,
        applies the splurge overlay through the SAME module ge.py uses
        (step4.splurge_overlay), and prints the verdict table: cumulative
        spending per delivered dollar, M(h) = NPV(dC,h)/NPV(dY), for the PE
        model against four HANK arms --
          shipped        = bug072 column 0 + legacy overlay   (production today)
          112-only       = unanticipated + legacy
          112+111(est)   = unanticipated + cash, DiscFac-column f_t
          112+111+rho    = unanticipated + cash, rho = R*LivPrb   (the package)
        plus a flat-across-education HANK variant of the package arm, which
        removes the largest declared incidence difference (the PE check is a
        flat $1,200 with a high-income phase-out; the HANK transfers instrument
        is proportional to permanent income, so the across-education allocation
        of the dollars differs).

Everything PE-side runs the canonical default configuration (MC, stratified
engine, policy store); everything HANK-side is read-only on the saved objs.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HA = os.path.join(REPO, "Code", "HA-Models")
FPC = os.path.join(HA, "FromPandemicCode")
DEFAULT_OUT = os.path.join(HA, "rerun_logs", "pe_reproduction_20260901")

JACS_UNANT = os.path.join(HA, "rerun_logs", "zerocol_fix_20260901", "jacs_unanticipated.obj")
JACS_BUG072 = os.path.join(HA, "rerun_logs", "zerocol_20260831", "jacs_bug072.obj")

R = 1.01
# Routed to the installed Step-1 estimate (dual-path sweep 2026-09-02) so the
# gate tracks re-estimations; the assert pins today's vintage loudly instead
# of letting a silent literal drift from the economy it certifies.
def _resolve_splurge():
    import os, sys
    _fpc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "FromPandemicCode")
    if _fpc not in sys.path:
        sys.path.insert(0, _fpc)
    _argv = sys.argv
    sys.argv = [_argv[0]]          # EstimParameters reads argv at import (BUG-114)
    try:
        from EstimParameters import Splurge as _s
    finally:
        sys.argv = _argv
    return float(_s)


SPLURGE = _resolve_splurge()
assert abs(SPLURGE - 0.3010418817919867) < 1e-12, (
    "installed splurge moved (Step-1 re-run?) — re-derive this gate's PE arm and update the pin")
# The education shares come from budget_suite, which resolves them from
# EstimParameters.data_EducShares — one source for every ladder gate instead of a second
# literal copy here (Q9, dual-path sweep 2026-09-02 §4; Phase-2 brief 2026-09-03).
if HA not in sys.path:
    sys.path.insert(0, HA)
from ssj_ladder.budget_suite import EDUC_SHARES  # noqa: E402


def run_pe(seed, out_dir, check_scale=1.0):
    """check_scale: multiply every agent's CheckStimLvl post-solve. The check is
    simulation-side cash (AggFiscalModel initialize_sim: CheckAmount[0] = CheckStimLvl,
    means-tested per agent) -- the solved policies do not embed the amount, so scaling
    it is a pure size probe: as check_scale -> 0 the PE response approaches the
    derivative the HANK Jacobian computes, isolating finite-check nonlinearity."""
    os.makedirs(out_dir, exist_ok=True)
    sys.argv = [sys.argv[0]]              # Parameters reads argv at import
    if FPC not in sys.path:
        sys.path.insert(0, FPC)
    os.chdir(FPC)
    import welfare6_scenario as ws
    t0 = time.time()
    ctx = ws.build_and_solve("Baseline", seed_offset=seed)
    if check_scale != 1.0:
        for agent in ctx["AggEco"].agents:
            agent.CheckStimLvl = agent.CheckStimLvl * check_scale
    t1 = time.time()
    base = ws.run_one_scenario(ctx, "base")
    t2 = time.time()
    chk = ws.run_one_scenario(ctx, "Check")
    t3 = time.time()
    out = {}
    for name, r in (("base", base), ("check", chk)):
        out[f"AggCons_{name}"] = np.asarray(r["AggCons"], dtype=float)
        out[f"AggIncome_{name}"] = np.asarray(r["AggIncome"], dtype=float)
    out["seed"] = seed
    out["check_scale"] = check_scale
    out["wall_solve"] = t1 - t0
    out["wall_base"] = t2 - t1
    out["wall_check"] = t3 - t2
    tag = f"pe_seed{seed}" + (f"_scale{check_scale}" if check_scale != 1.0 else "")
    path = os.path.join(out_dir, f"{tag}.npz")
    np.savez(path, **out)
    dY = out["AggIncome_check"] - out["AggIncome_base"]
    dC = out["AggCons_check"] - out["AggCons_base"]
    print(f"[pe seed {seed}] solve {t1-t0:.0f}s base {t2-t1:.0f}s check {t3-t2:.0f}s | "
          f"dY[0]={dY[0]:.5f} dY[1]={dY[1]:.2e} dC[0]={dC[0]:.5f} -> {path}", flush=True)


def _npv(x, h):
    x = np.asarray(x, dtype=float)
    if len(x) < h:
        raise ValueError(
            f"_npv: series length {len(x)} < requested horizon {h} — refusing to discount "
            "over a silently shorter window (the BUG-109 class; dual-path sweep 2026-09-02)")
    x = x[:h]
    return float(np.sum(x / R ** np.arange(len(x))))


def _m_curve(dC, dY, hs, y_horizon):
    denom = _npv(dY, y_horizon)
    return {h: _npv(dC, h) / denom for h in hs}, denom


def _budget_col0(JC, JA, rho):
    JC, JA = np.asarray(JC), np.asarray(JA)
    r = np.empty(JC.shape[0])
    r[0] = JA[0, 0] + JC[0, 0]
    r[1:] = JA[1:, 0] - rho * JA[:-1, 0] + JC[1:, 0]
    return r


def _hank_arm(jacs, arm, rho_mode, livprb):
    """Overlaid column-0 spending path + the RAW pair's delivered-cash path."""
    from copy import deepcopy
    from step4 import splurge_overlay as sov
    periods = np.asarray(jacs["C"]["transfers"]).shape[0]
    tgt = {"C": deepcopy(dict(jacs["C"])), "A": deepcopy(dict(jacs["A"]))}
    sov.apply_aggregate(tgt, jacs, arm, SPLURGE, R, livprb, periods, rho_mode=rho_mode)
    dC = np.asarray(tgt["C"]["transfers"])[:, 0]
    dY = _budget_col0(jacs["C"]["transfers"], jacs["A"]["transfers"], R * livprb)
    return dC, dY


def _hank_flat_educ(jacs, arm, rho_mode, livprb):
    """The package arm re-allocated FLAT across education groups (per capita), from the
    by-educ leaves: each education's per-delivered-dollar path, population-weighted."""
    from copy import deepcopy
    from step4 import splurge_overlay as sov
    periods = np.asarray(jacs["C"]["transfers"]).shape[0]
    by, src = {}, {}
    for e in EDUC_SHARES:
        by["C_" + e] = deepcopy(dict(jacs["C_by_educ"][e]))
        by["A_" + e] = deepcopy(dict(jacs["A_by_educ"][e]))
        src["C_" + e] = dict(jacs["C_by_educ"][e])
        src["A_" + e] = dict(jacs["A_by_educ"][e])
    sov.apply_by_educ(by, src, arm, SPLURGE, R, livprb, periods, rho_mode=rho_mode)
    dC = np.zeros(periods)
    for e, w in EDUC_SHARES.items():
        cash_e = _budget_col0(jacs["C_by_educ"][e]["transfers"],
                              jacs["A_by_educ"][e]["transfers"], R * livprb)[0]
        dC += w * np.asarray(by["C_" + e]["transfers"])[:, 0] / cash_e
    return dC, np.concatenate(([1.0], np.zeros(periods - 1)))  # per-dollar by construction


def compare(out_dir):
    import pickle
    if HA not in sys.path:
        sys.path.insert(0, HA)
    from step4.hh_setup import LIVPRB_SS  # noqa: triggers step4 import; env pinned below

    hs = (1, 4, 8, 12, 20)
    y_h = 8   # the check is one-quarter; income diffs beyond a few quarters are noise

    # ---- PE side: seeds ----
    seeds = sorted(int(f.split("seed")[1].split(".")[0])
                   for f in os.listdir(out_dir)
                   if f.startswith("pe_seed") and "scale" not in f)
    pe_curves, pe_denoms, pe_impacts = [], [], []
    for k in seeds:
        d = np.load(os.path.join(out_dir, f"pe_seed{k}.npz"))
        dC = d["AggCons_check"] - d["AggCons_base"]
        dY = d["AggIncome_check"] - d["AggIncome_base"]
        m, den = _m_curve(dC, dY, hs, y_h)
        pe_curves.append(m); pe_denoms.append(den)
        pe_impacts.append(dC[0] / dY[0])
    pe_mean = {h: float(np.mean([c[h] for c in pe_curves])) for h in hs}
    pe_se = {h: float(np.std([c[h] for c in pe_curves], ddof=1) / np.sqrt(len(seeds)))
             if len(seeds) > 1 else float("nan") for h in hs}

    # ---- HANK side: arms ----
    with open(JACS_UNANT, "rb") as f:
        unant = pickle.load(f)
    with open(JACS_BUG072, "rb") as f:
        bug = pickle.load(f)
    arms = {
        "shipped (bug072+legacy)": _hank_arm(bug, "legacy", "livprb", LIVPRB_SS),
        "112-only (unant+legacy)": _hank_arm(unant, "legacy", "livprb", LIVPRB_SS),
        "112+111 (cash, f_t est)": _hank_arm(unant, "cash", "estimate", LIVPRB_SS),
        "112+111+rho (the package)": _hank_arm(unant, "cash", "livprb", LIVPRB_SS),
        "package, flat across educ": _hank_flat_educ(unant, "cash", "livprb", LIVPRB_SS),
    }

    rows = {}
    print("\n" + "=" * 100)
    print("PE-REPRODUCTION GATE -- cumulative spending per delivered dollar, M(h) = NPV(dC,h)/NPV(dY)")
    print(f"PE side: Baseline, Check without recession, {len(seeds)} seed(s); "
          f"HANK side: transfers column 0, overlay via step4.splurge_overlay")
    print("=" * 100)
    hdr = f"{'side / arm':34s}" + "".join(f"  M({h:>2d})" for h in hs) + "   impact dC0/dY0"
    print(hdr); print("-" * len(hdr))
    pe_row = "".join(f"  {pe_mean[h]:.4f}" for h in hs)
    print(f"{'PE model (mean of seeds)':34s}{pe_row}   {np.mean(pe_impacts):.4f}")
    if len(seeds) > 1:
        print(f"{'  (seed SE)':34s}" + "".join(f"  {pe_se[h]:.4f}" for h in hs))
    for name, (dC, dY) in arms.items():
        m, den = _m_curve(dC, dY, hs, y_h)
        rows[name] = m
        print(f"{name:34s}" + "".join(f"  {m[h]:.4f}" for h in hs)
              + f"   {dC[0]/dY[0]:.4f}" + f"   [delivered/unit shock: {den:.4f}]")
    print("-" * len(hdr))
    print("shape (M(h)/M(20)):")
    pe_shape = {h: pe_mean[h] / pe_mean[20] for h in hs}
    print(f"{'PE model':34s}" + "".join(f"  {pe_shape[h]:.4f}" for h in hs))
    for name, m in rows.items():
        print(f"{name:34s}" + "".join(f"  {m[h]/m[20]:.4f}" for h in hs))

    # ---- the multiplier-relevant basis: per unit BOOKED (the policy's cost) ----
    # PE books what it delivers (no wedge); HANK books 1.0/unit shock and delivers
    # kappa = the survivor weight (0.9955, derived) -- or 0.8396 under the bug072
    # defect. M_booked(20) = M(20) * delivered/booked.
    print("\nper unit BOOKED (the multiplier's denominator): NPV(dC,20)/booked")
    print(f"{'PE model':34s}  {pe_mean[20]:.4f}   (delivered == booked)")
    for name, (dC, dY) in arms.items():
        booked = 1.0 if "flat" not in name else 1.0
        m20b = rows[name][20] * ( _npv(dY, y_h) / booked )
        print(f"{name:34s}  {m20b:.4f}")

    # ---- linearity probes (scaled-check PE runs), if present ----
    probes = sorted(f for f in os.listdir(out_dir) if "scale" in f and f.endswith(".npz"))
    if probes:
        print("\ncheck-size linearity probe (PE impact dC0/dY0 vs the package's derivative "
              f"{arms['112+111+rho (the package)'][0][0]/arms['112+111+rho (the package)'][1][0]:.4f}):")
        for f in probes:
            d = np.load(os.path.join(out_dir, f))
            dC = d["AggCons_check"] - d["AggCons_base"]
            dY = d["AggIncome_check"] - d["AggIncome_base"]
            print(f"  {f:32s} scale={float(d['check_scale']):<5} impact={dC[0]/dY[0]:.4f}")

    # verdict: closest arm to the PE at every horizon, level and shape
    verdict = {"seeds": seeds, "pe_mean": {str(h): pe_mean[h] for h in hs},
               "pe_se": {str(h): pe_se[h] for h in hs},
               "arms": {n: {str(h): rows[n][h] for h in hs} for n in rows}}
    lvl_dev = {n: float(np.mean([abs(rows[n][h] - pe_mean[h]) / pe_mean[h] for h in hs]))
               for n in rows}
    shp_dev = {n: float(np.mean([abs(rows[n][h]/rows[n][20] - pe_shape[h]) / pe_shape[h]
                                 for h in hs])) for n in rows}
    verdict["mean_level_dev"] = lvl_dev
    verdict["mean_shape_dev"] = shp_dev
    print("\nmean |level dev| vs PE: " + "  ".join(f"{n.split(' ')[0]}={v:.3%}" for n, v in lvl_dev.items()))
    print("mean |shape dev| vs PE: " + "  ".join(f"{n.split(' ')[0]}={v:.3%}" for n, v in shp_dev.items()))
    with open(os.path.join(out_dir, "gate_verdict.json"), "w") as f:
        json.dump(verdict, f, indent=1)
    print(f"\n-> {os.path.join(out_dir, 'gate_verdict.json')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["pe", "compare"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--check-scale", type=float, default=1.0)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    if args.mode == "pe":
        run_pe(args.seed, args.out, check_scale=args.check_scale)
    else:
        compare(args.out)


if __name__ == "__main__":
    main()
