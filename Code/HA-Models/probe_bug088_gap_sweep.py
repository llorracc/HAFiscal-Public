#!/usr/bin/env python3
"""BUG-088 follow-up (b): map where the spurious ConsumedATI fixed point is reachable.

The June 2026 trip: the College top atom clamped EXACTLY to the GIC cap (beta 1.01141947) solved
cold at S=252 (recessionUI) through the ATI router converged (fnorm 6e-13) on a policy 34.5 %
ABOVE its perfect-foresight line -- a spurious fixed point of the truncated-grid Newton system.
The router gate (2026-08-24) and now the solver's own verdict (2026-09-09, converged=False /
'spurious_above_pf_line') refuse it. This probe asks how close to the cap the spurious branch
is reachable at all: it takes the welfare battery's own College top atom, sets its discount
factor to cap - gap for a ladder of gaps (0 = the June case), switches it to the recessionUI
chain (S=252), and sends it through the production router exactly as Step 5a does, recording
the router's verdict per gap. Diagnostic only; installs nothing; writes REPORT.md + the raw
router lines under the output directory.

Usage: probe_bug088_gap_sweep.py [OUT_DIR] [--gaps 0,1e-4,3e-4,1e-3,3e-3,1e-2]
Env: the production Step-5a environment (HAFISCAL_STEP5_ATI=1, HAFISCAL_TM_A_INDEXED=1) is
set here by default; HAFISCAL_FTI_REPO resolves the sibling checkout as usual.
"""
import argparse, contextlib, copy, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
FPC = os.path.join(HERE, "FromPandemicCode")
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("out_dir", nargs="?", default=os.path.join(HERE, "rerun_logs", "bug088_gap_sweep_20260909"))
ap.add_argument("--gaps", default="0,1e-4,3e-4,1e-3,3e-3,1e-2")
ap.add_argument("--parametrization", default="Baseline")
args = ap.parse_args()
os.makedirs(args.out_dir, exist_ok=True)
for k, v in (("HAFISCAL_STEP5_ATI", "1"), ("HAFISCAL_TM_A_INDEXED", "1"), ("HAFISCAL_QUIET_BETADISTR", "1"),
             ("MPLBACKEND", "Agg"), ("HAFISCAL_SOLVE_WALL_VERBOSE", "1")):
    os.environ.setdefault(k, v)
sys.argv = [sys.argv[0]]            # Parameters.py reads argv
sys.path.insert(0, FPC); sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import welfare6_scenario as ws       # noqa: E402
import EstimParameters as ep         # noqa: E402
from AggFiscalModel import AggregateDemandEconomy, try_solve_ati_markov  # noqa: E402

gaps = [float(g) for g in args.gaps.split(",")]
cap = float(ep.gic_capped_beta(2, ep.theGICfactor))
t0 = time.time()
r = ws.build_and_solve(args.parametrization)
eco = r["AggEco"]
def _beta(a):
    return float(np.asarray(a.DiscFac).reshape(-1)[0])
top = max(eco.agents, key=_beta)
print(f"[sweep] economy built in {time.time()-t0:.0f}s; College top atom beta={_beta(top):.7f}; cap={cap:.8f}; "
      f"base states={np.asarray(top.MrkvArray[0]).shape[0]}", flush=True)

rows, raw = [], []
for gap in gaps:
    ag = copy.deepcopy(top)
    ag.DiscFac = cap - gap
    ag.switch_shock_type("recessionUI")
    ag.update_solution_terminal()
    S = int(np.asarray(ag.MrkvArray[0]).shape[0])
    for attr in ("_step5_ati_info", "_step5_ati_used", "_solved_DiscFac"):
        if hasattr(ag, attr):
            delattr(ag, attr)
    buf = io.StringIO(); t1 = time.time(); err = None
    try:
        with contextlib.redirect_stdout(buf):
            routed = bool(try_solve_ati_markov(ag, None))
    except Exception as e:  # noqa: BLE001 -- the probe records, it does not stop
        routed, err = False, f"{type(e).__name__}: {e}"
    wall = time.time() - t1
    lines = [l for l in buf.getvalue().splitlines() if ("step5-ati" in l or "FALLBACK" in l or "spurious" in l.lower())]
    info = getattr(ag, "_step5_ati_info", None)
    verdict = None
    if routed:
        try:
            sol = ag.solution[0]
            # the router installs the 2-D wrapped policy; re-check the 1-D slices against the line via the router's helper
            verdict = AggregateDemandEconomy._ati_pf_line_violation(
                type("S", (), {"MPCmin": info.get("MPCmin", np.nan), "hNrm": info.get("hNrm", []), "cFunc": sol.cFunc})(), info) \
                if info and "MPCmin" in info else "n/a (router already verified before install)"
        except Exception as e:  # noqa: BLE001
            verdict = f"re-check unavailable ({type(e).__name__})"
    fallback = next((l for l in lines if "FALLBACK" in l), "")
    kind = ("ROUTED (installed; passed the PF-line gate)" if routed else
            "REFUSED: spurious fixed point" if ("spurious" in fallback.lower()) else
            "REFUSED: non-convergence" if "non-convergence" in fallback else
            "REFUSED: unqualified/other" if not err else f"ERROR {err}")
    rows.append(dict(gap=gap, beta=cap - gap, S=S, routed=routed, kind=kind, fallback=fallback[:300],
                     iters=(info or {}).get("iters"), fnorm=(info or {}).get("fnorm"), wall_s=round(wall, 1)))
    raw.append((gap, buf.getvalue()))
    print(f"[sweep] gap={gap:g} beta={cap-gap:.7f} S={S} -> {kind} ({wall:.0f}s) {fallback[:160]}", flush=True)

with open(os.path.join(args.out_dir, "rows.json"), "w") as f:
    json.dump(rows, f, indent=1)
with open(os.path.join(args.out_dir, "router_lines.txt"), "w") as f:
    for gap, txt in raw:
        f.write(f"===== gap={gap:g}\n{txt}\n")
L = ["# BUG-088 gap sweep — where the spurious ATI fixed point is reachable (2026-09-09)", "",
     f"College top atom of the {args.parametrization} welfare battery, discount factor set to cap − gap "
     f"(cap = gic_capped_beta(College, θ) = {cap:.8f}), switched to the recessionUI chain (S = {rows[0]['S']}), "
     "cold-solved through the production ATI router (`try_solve_ati_markov`) exactly as Step 5a does. "
     "With the solver-side verdict of 2026-09-09 a spurious branch shows as `FALLBACK (non-convergence) "
     "reason=spurious_above_pf_line`; the router's own gate would show `FALLBACK (spurious fixed point, BUG-088)`.", "",
     "| gap below cap | β | verdict | iters | fnorm | wall |", "|---|---|---|---|---|---|"]
for r_ in rows:
    fn = "" if r_["fnorm"] is None else "%.1e" % r_["fnorm"]
    L.append("| %g | %.7f | %s | %s | %s | %s s |" % (r_["gap"], r_["beta"], r_["kind"], r_["iters"], fn, r_["wall_s"]))
L += ["", "Raw router lines: `router_lines.txt`; rows: `rows.json`. Diagnostic only — nothing installed, no result of record touched."]
open(os.path.join(args.out_dir, "REPORT.md"), "w").write("\n".join(L) + "\n")
print(f"[sweep] done in {time.time()-t0:.0f}s -> {args.out_dir}/REPORT.md", flush=True)
