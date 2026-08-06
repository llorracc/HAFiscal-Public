"""
AD bottleneck deep-dive profiler (diagnostic; safe to delete).

Tests whether the AD aggregate-demand loop is dominated by re-solving
consumption functions for the slow, most-patient cohorts (esp. College).

Mechanism: monkeypatch solve_agent to time EVERY per-cohort solve. Then run one
recession_AD scenario at small N (sim is N-scaled; solve is N-independent). The
first round of 21 solves = the cold "presolve"; each later round = one warm AD
iteration. Combined with the built-in profiler (AD_presolve / AD_iter_*_solve /
AD_iter_*_experiment) this attributes the whole loop in a single run.

Options via env (argv is reserved for EstimParameters calibration):
  PROF_PARAM (Baseline)  PROF_N (500)  PROF_AD_ITERS (0=keep default)
Run:
  HAFISCAL_WORLD=default PROF_N=500 python _profile_ad_bottleneck.py |& tee /tmp/ad_prof.log
"""
import os, sys, time
from copy import deepcopy
import numpy as np

os.environ.pop("HAFISCAL_USE_SOLUTION_CACHE", None)
os.environ.pop("HAFISCAL_USE_JAX_MC", None)

PARAM    = os.environ.get("PROF_PARAM", "Baseline")
N        = int(os.environ.get("PROF_N", "500"))
AD_ITERS = int(os.environ.get("PROF_AD_ITERS", "0"))
# argv = [name, Rfree, CRRA, IncUnemp, IncUnempNoBenefits, Splurge] (canonical)
sys.argv = [sys.argv[0], "1.01", "2.0", "0.7", "0.5", "0.26718066005582686"]

EDU = {0: "Dropout", 1: "HighSchool", 2: "College"}

def P(*a):
    print(*a, flush=True)

P(f"\n{'='*82}\nAD BOTTLENECK PROFILE  param={PARAM}  N={N}  world={os.environ.get('HAFISCAL_WORLD','?')}\n{'='*82}")

from welfare6_scenario import build_and_solve, run_base, run_recession_AD
from hafiscal_progress import profiler
import HARK.core as _hcore   # solve() does `from HARK.core import solve_agent` each call

# --- monkeypatch solve_agent to record per-cohort timing -------------------
_real_solve_agent = _hcore.solve_agent
REC = []           # list of (call_idx, DiscFac, n_states, dt)
_calls = {"n": 0}
def _timed_solve_agent(agent, *a, **k):
    t = time.time()
    out = _real_solve_agent(agent, *a, **k)
    dt = time.time() - t
    try:
        beta = float(getattr(agent, "DiscFac", float("nan")))
    except Exception:
        beta = float("nan")
    try:
        ns = agent.MrkvArray[0].shape[0]
    except Exception:
        ns = -1
    REC.append((_calls["n"], beta, ns, dt))
    P(f"    [solve#{_calls['n']:>3}] DiscFac={beta:.4f} states={ns:>3} -> {dt:7.2f}s")
    _calls["n"] += 1
    return out
_hcore.solve_agent = _timed_solve_agent

t0 = time.time()
ctx = build_and_solve(PARAM, agent_count_total=N)
P(f"[build_and_solve] {time.time()-t0:.1f}s  (cohorts={len(ctx['AggEco'].agents)})")
NC = len(ctx["AggEco"].agents)
DFC = max(1, NC // 3)

t0 = time.time()
run_base(ctx)
P(f"[run_base] {time.time()-t0:.1f}s")

if AD_ITERS > 0:
    ctx["num_max_iterations_solvingAD"] = AD_ITERS

REC.clear(); _calls["n"] = 0   # only capture the AD scenario's solves
P(f"\n{'-'*82}\nRUN recession_AD  (round 0 = cold presolve; later rounds = warm AD iters)\n{'-'*82}")
t0 = time.time()
run_recession_AD(ctx, "recession", ctx["recession_changes"], duration_workers=1)
ad_wall = time.time() - t0
P(f"[recession_AD] wall {ad_wall:.1f}s, total per-cohort solves recorded = {len(REC)}")

# --- attribute -------------------------------------------------------------
# group recorded solves into rounds of NC (cohort order = edu0 b0..,edu1..,edu2..)
def edu_of(call_idx):
    return (call_idx % NC) // DFC
rounds = {}
for (ci, beta, ns, dt) in REC:
    rnd = ci // NC
    rounds.setdefault(rnd, []).append((edu_of(ci), beta, ns, dt))

if rounds:
    P(f"\n{'-'*82}\nCOLD PRESOLVE (round 0) per-cohort\n{'-'*82}")
    P(f"{'edu':>11} {'DiscFac':>9} {'states':>6} {'cold_s':>9}")
    cold = rounds.get(0, [])
    cold_by_edu = {}
    for (e, beta, ns, dt) in cold:
        P(f"{EDU.get(e,e):>11} {beta:>9.4f} {ns:>6} {dt:>9.2f}")
        cold_by_edu[e] = cold_by_edu.get(e, 0.0) + dt
    tc = sum(d for *_, d in cold) or 1e-9
    P(f"\ncold presolve by edu:")
    for e in sorted(cold_by_edu):
        P(f"  {EDU.get(e,e):>11}: {cold_by_edu[e]:8.1f}s  ({100*cold_by_edu[e]/tc:5.1f}%)")
    P(f"  {'TOTAL':>11}: {tc:8.1f}s")
    if cold:
        sc = max(cold, key=lambda r: r[3])
        P(f"  slowest cold cohort: {EDU.get(sc[0])} DiscFac={sc[1]:.4f} -> {sc[3]:.1f}s ({100*sc[3]/tc:.1f}% of cold)")

    warm_rounds = [r for r in rounds if r >= 1]
    if warm_rounds:
        P(f"\n{'-'*82}\nWARM AD-ITERATION SOLVES (rounds 1..{max(warm_rounds)})\n{'-'*82}")
        warm_by_edu = {}
        warm_tot = 0.0
        for r in sorted(warm_rounds):
            rd = rounds[r]
            warm_tot += sum(d for *_, d in rd)
            for (e, beta, ns, dt) in rd:
                warm_by_edu[e] = warm_by_edu.get(e, 0.0) + dt
        tw = warm_tot or 1e-9
        P(f"warm solve total over {len(warm_rounds)} iters = {warm_tot:.1f}s  (avg/iter {warm_tot/len(warm_rounds):.1f}s)")
        for e in sorted(warm_by_edu):
            P(f"  {EDU.get(e,e):>11}: {warm_by_edu[e]:8.1f}s  ({100*warm_by_edu[e]/tw:5.1f}%)")

# --- built-in profiler AD decomposition ------------------------------------
fp = profiler.function_profiles
def g(name):
    p = fp.get(name);  return (p.total_time, p.call_count) if p else (0.0, 0)
pres_t, _      = g("AD_presolve_recession")
solve_t, sn    = g("AD_iter_recession_solve")
exp_t, en      = g("AD_iter_recession_experiment")
iter_t, itn    = g("AD_iteration_recession")
tot_t, _       = g("AD_solve_total_recession")
P(f"\n{'='*82}\nAD LOOP DECOMPOSITION (from built-in profiler)\n{'='*82}")
P(f"  AD iterations run            : {itn}")
P(f"  presolve (1 cold full solve) : {pres_t:8.1f}s   <- one-time")
P(f"  per-iter SOLVE (warm) total  : {solve_t:8.1f}s   avg/iter {solve_t/max(sn,1):6.2f}s  (n={sn})")
P(f"  per-iter SIMULATE total      : {exp_t:8.1f}s   avg/iter {exp_t/max(en,1):6.2f}s  (n={en})  [at N={N}]")
den = max(solve_t + exp_t, 1e-9)
P(f"  per-iter SOLVE vs SIM        : solve {100*solve_t/den:.1f}%   sim {100*exp_t/den:.1f}%")
P(f"  total AD time                : {tot_t:8.1f}s")
P(f"\n  RESCALING NOTE: SIM scales ~linearly with N (Baseline N=10000 => ~{10000//max(N,1)}x")
P(f"  the SIM time above); SOLVE and presolve are N-independent. Apply that factor")
P(f"  to project the real Baseline split.")
P(f"\n{'='*82}\nDONE\n{'='*82}")
