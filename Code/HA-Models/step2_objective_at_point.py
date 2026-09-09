#!/usr/bin/env python3
"""step2_objective_at_point.py — evaluate the Step-2 (β, ∇) objective at given points, no estimation.

Why (2026-09-03 overnight): both cold multistarts (dell, m5) re-estimate the College spread ∇ ≈ 6.5 %
below the frozen chain-D value while every β centre reproduces to <0.02 %. The engine
(`estim_phase2_tm_a.py`) has no __main__ guard, so it cannot be imported without running the whole
estimation; this tool execs its source PREFIX (everything before the estimation loop — the agents, the
economy, and `betas_obj_func_educ_tm_a`) and evaluates the objective ("distance") at the requested
points under the tree's own calibration context (Splurge from EstimParameters = the frozen 0.29987 in
the main tree). The numbers say how flat the valley is between the chain endpoint and the cold optimum.

usage: python Code/HA-Models/step2_objective_at_point.py [--educ 2] [--force]
           --point LABEL:BETA:NABLA[:GICX] ...   (GICX defaults to the College value 7.60040233450051)
Refuses to run while the timing-bearing cold-run unit is active (dell idle rule) unless --force.
Each evaluation solves the education group's 7 β atoms (≈1–2 min, single process).
"""
import argparse, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
FPC = os.path.join(HERE, "FromPandemicCode")
ENGINE = os.path.join(FPC, "estim_phase2_tm_a.py")
CUT_MARKER = "_edtypes_env = os.environ.get('HAFISCAL_EDTYPES'"   # first line of the estimation loop
GICX_COLLEGE = 7.60040233450051


def unit_active(unit="hafiscal-colddoall-20260902-rerun"):
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() in ("active", "activating")
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--educ", type=int, default=2, help="0 dropout, 1 highschool, 2 college")
    ap.add_argument("--point", action="append", default=[], help="LABEL:BETA:NABLA[:GICX]")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not a.point:
        sys.exit("give at least one --point LABEL:BETA:NABLA[:GICX]")
    if unit_active() and not a.force:
        sys.exit("cold-run unit is ACTIVE — refusing to add compute on dell (idle rule); pass --force to override")
    src = open(ENGINE, encoding="utf-8").read()
    cut = src.find(CUT_MARKER)
    if cut < 0:
        sys.exit(f"cut marker not found in {ENGINE}; the engine changed — update CUT_MARKER")
    prefix = src[:cut]
    os.chdir(FPC)
    sys.path.insert(0, FPC); sys.path.insert(0, HERE)
    sys.argv = ["estim_phase2_tm_a.py"]          # Parameters.py reads argv
    ns = {"__name__": "_step2_engine_prefix", "__file__": ENGINE}
    t0 = time.time()
    exec(compile(prefix, ENGINE, "exec"), ns)     # builds agents + economy, defines the objective
    # the objective calls get_interpretation(), imported AFTER the estimation loop starts (engine
    # lines ~448-453: a sys.path insert + `from _interpretation import ...`); exec that block too.
    i0 = src.find("import sys as _sys_es"); i1 = src.find("from _interpretation import calib_suffix")
    if i0 < 0 or i1 < 0:
        sys.exit("late-import block not found in the engine; update step2_objective_at_point.py")
    i1 = src.find("\n", i1) + 1
    exec(compile(src[i0:i1], ENGINE + " (late imports)", "exec"), ns)
    print(f"[engine prefix loaded in {time.time()-t0:.0f}s; Splurge={ns.get('Splurge')}]", flush=True)
    f = ns["betas_obj_func_educ_tm_a"]
    rows = []
    for spec in a.point:
        parts = spec.split(":")
        label, beta, nabla = parts[0], float(parts[1]), float(parts[2])
        gicx = float(parts[3]) if len(parts) > 3 else GICX_COLLEGE
        t1 = time.time()
        d = float(f(beta, nabla, gicx, educ_type=a.educ, print_mode=False))
        rows.append((label, beta, nabla, gicx, d, time.time() - t1))
        print(f"  {label:12s} beta={beta:.10f} nabla={nabla:.10f} GICx={gicx:.6f} -> distance={d:.6f}  ({time.time()-t1:.0f}s)", flush=True)
    print("\n| point | β | ∇ | distance | Δ vs first |")
    print("|---|---|---|---|---|")
    d0 = rows[0][4]
    for label, beta, nabla, gicx, d, _ in rows:
        print(f"| {label} | {beta:.7f} | {nabla:.7f} | {d:.6f} | {100*(d-d0)/d0:+.4f} % |")


if __name__ == "__main__":
    main()
