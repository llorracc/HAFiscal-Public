#!/usr/bin/env python3
"""Probe (2026-08-29, coordinator request): which permanent-income GROWTH factor does the Monte-Carlo simulation apply
to UNEMPLOYED households in the default world (flag HAFISCAL_EARNINGS_PHASE_HAZARD unset, h = 0)?

The solver / TM give every unemployed micro state PermGroFac = G_u = PermGroFac_unemp = 1 (EstimParameters.py:533,
income_process_sst.build_PermGroFac_micro, tile_PermGroFac_composite; the solver reads PermGroFac[j] per state in
solve_agg_cons_markov_alt, the a-indexed kernel PermGroFac_arr[jp] in tm_methods._build_period_tm_a). The MC has TWO
paths for the permanent shock:
  (a) the LIVE path (burn-in / warmup, read_shocks = False): HARK MarkovConsumerType.get_shocks draws, per REALIZED state j,
      PermShk = psi * PermGroFac[t-1][j] (HARK ConsMarkovModel.py get_shocks) -- G_u for the unemployed;
  (b) the EXPERIMENT REPLAY path (run_experiment -> hit_with_recession_shock, read_shocks = True): the shocks come from a
      FIXED history drawn once with every household forced into state 0 (AggFiscalModel.make_idiosyncratic_shock_histories:
      `self.Mrkv_univ = 0` -> get_markov_states overwrites shocks['Mrkv'] with 0 -> HARK draws psi * PermGroFac[0] = psi * G_emp)
      and, under perm_shocks_during_unemployment (the default world, EstimParameters.py:548), hit_with_recession_shock
      assigns that same fixed draw to the unemployed household-quarters:
      `self.shock_history['PermShk'][unemp_*] = <perm_shock_fixed_hist>[unemp_*]`.
  The pLvl update is pLvlNow = pLvlPrev * shocks['PermShk'] (HARK ConsIndShockModel transition), so the growth factor the
  MC applied at t is pLvl_t / (pLvl_{t-1} * psi_t).

Method: build the HS_Only base economy (welfare6_scenario.build_and_solve), run the base experiment (the replay path)
and a short LIVE simulation; for every surviving household-quarter identify psi_t and the applied growth factor by
matching pLvl_t / pLvl_{t-1} against the employed distribution's psi atoms times {G_emp, G_u} (exact float matches;
G_emp = 1.00453 separates the two sets), and tabulate by the household's employment state at t. No model code is touched.
Usage: python Code/HA-Models/probe_unemp_growth_mc.py  (flag unset; writes nothing but stdout)."""
import os, sys, json
sys.argv = [sys.argv[0]]
assert os.environ.get("HAFISCAL_EARNINGS_PHASE_HAZARD", "0").strip() in ("", "0"), "run with the earnings phase OFF"
os.environ.setdefault("HAFISCAL_QUIET_BETADISTR", "1")
os.environ.setdefault("HAFISCAL_POLICY_STORE_REQUIRE", "0")
os.environ.setdefault("HAFISCAL_MC_WEIGHTED_TAIL", "0")          # equal-weight panel (irrelevant to the growth question)
HERE = os.path.dirname(os.path.abspath(__file__)); FPC = os.path.join(HERE, "FromPandemicCode")
os.chdir(FPC); sys.path.insert(0, FPC); sys.path.insert(0, HERE)
import numpy as np
import welfare6_scenario as ws


def classify(applied, atoms, G_emp, G_u, rtol=1e-9):
    """Per household-quarter: which (psi atom, growth) pair produced the applied shock. Returns (psi, G, kind) with kind
    'emp' (psi*G_emp), 'unemp' (psi*G_u) or 'none'."""
    n = applied.size
    psi = np.full(n, np.nan); G = np.full(n, np.nan); kind = np.full(n, "none", dtype=object)
    for k, at in enumerate(atoms):
        m = np.isclose(applied, at * G_emp, rtol=rtol, atol=0.0) & (kind == "none")
        psi[m] = at; G[m] = G_emp; kind[m] = "emp"
    for k, at in enumerate(atoms):
        m = np.isclose(applied, at * G_u, rtol=rtol, atol=0.0) & (kind == "none")
        psi[m] = at; G[m] = G_u; kind[m] = "unemp"
    return psi, G, kind


def tabulate(label, pLvl_hist, Mrkv_hist, who_dies_hist, J, atoms, G_emp, G_u, permshk_hist=None):
    """pLvl_hist: (T, N) post-period pLvl; Mrkv_hist: (T, N) state in period t; who_dies_hist: (T, N) reborn at t."""
    T, N = pLvl_hist.shape
    rows = {}
    ratio = pLvl_hist[1:] / pLvl_hist[:-1]                       # growth applied in period t = 1..T-1 (survivors)
    if who_dies_hist is not None:
        survivor = ~who_dies_hist[1:].astype(bool)               # not reborn at t (the replay's period-aligned fixed history)
    else:
        # live path: HARK's history['who_dies'] is stored with a one-period lag, so identify newborns as the household-
        # quarters whose pLvl ratio matches NO (psi atom x growth) pair (a redrawn lognormal pLvl never does)
        _, _, k0 = classify(ratio.ravel(), atoms, G_emp, G_u)
        survivor = (k0 != "none").reshape(ratio.shape)
        rows["live: household-quarters dropped as newborns (no atom match)"] = float(1.0 - survivor.mean())
    if permshk_hist is not None:
        # alignment check: the applied PermShk of period t must equal the pLvl ratio for survivors
        match_same = np.isclose(ratio, permshk_hist[1:], rtol=1e-12)[survivor].mean()
        rows["alignment_ratio_t_equals_PermShk_t (survivors)"] = float(match_same)
    state_t = Mrkv_hist[1:] % J
    psi, G, kind = classify(ratio[survivor].ravel(), atoms, G_emp, G_u)
    st = state_t[survivor].ravel()
    out = {}
    for name, sel in (("employed (emp==0)", st == 0), ("unemployed (emp>=1)", st >= 1)):
        n = int(sel.sum())
        if n == 0:
            continue
        k = kind[sel]
        applied_G = G[sel]
        out[name] = {
            "household_quarters": n,
            "share_of_survivor_quarters": float(n / len(st)),
            "matched psi*G_emp": float(np.mean(k == "emp")),
            "matched psi*G_u": float(np.mean(k == "unemp")),
            "unmatched": float(np.mean(k == "none")),
            "mean applied growth pLvl_t/(pLvl_{t-1}*psi_t)": float(np.nanmean(applied_G)),
            "min/max applied growth": [float(np.nanmin(applied_G)), float(np.nanmax(applied_G))],
        }
    rows["by_state"] = out
    print(f"\n=== {label} ===")
    print(json.dumps(rows, indent=1))
    return rows


ctx = ws.build_and_solve("HS_Only")
eco = ctx["AggEco"]; a = eco.agents[0]
J = int(a.num_base_MrkvStates)
G_emp = float(a.PermGroFac[0][0]); G_u = float(a.PermGroFac[0][1])
atoms = np.asarray(a.IncShkDstn_base[0][0].atoms[0], dtype=float)      # the employed psi atoms
u_atoms = np.asarray(a.IncShkDstn_base[0][1].atoms[0], dtype=float)    # the unemployed (benefits) psi atoms
print("solver / TM per-state PermGroFac (base):", [float(x) for x in a.PermGroFac[0]])
print("perm_shocks_during_unemployment =", getattr(a, "perm_shocks_during_unemployment", None),
      "; unemp_pLvl_grows_like_employed =", getattr(a, "unemp_pLvl_grows_like_employed", None),
      "; Urate_normal =", float(a.Urate_normal))
print("employed psi atoms:", np.round(atoms, 6).tolist(), "| unemployed psi atoms:", np.round(u_atoms, 6).tolist())
print(f"G_emp = {G_emp:.6f}, G_u = {G_u:.6f}; psi*G_emp and psi*G_u sets are disjoint:",
      bool(np.min(np.abs(np.subtract.outer(atoms * G_emp, atoms * G_u))) > 1e-9))

# ---- (b) the EXPERIMENT REPLAY path: the base experiment through run_experiment (read_shocks = True)
base = ws.run_base(ctx)
pl = np.asarray(a.history["pLvl"], dtype=float)                   # (T, N), post-period
mh = np.asarray(a.shock_history["Mrkv"], dtype=int)
wd = np.asarray(a.shock_history["who_dies"], dtype=bool)
ps = np.asarray(a.shock_history["PermShk"], dtype=float)
fixed = np.asarray(a.perm_shock_fixed_hist, dtype=float)
print("\nfixed history perm_shock_fixed_hist / G_emp is an employed psi atom for every entry:",
      bool(np.all(np.min(np.abs(np.subtract.outer(fixed.ravel() / G_emp, atoms)), axis=1) < 1e-9)))
unemp_q = (mh % J) >= 1
print("replay path: shock_history['PermShk'] == perm_shock_fixed_hist on unemployed household-quarters:",
      bool(np.allclose(ps[unemp_q], fixed[unemp_q], rtol=1e-14)), f"(n = {int(unemp_q.sum())})")
rep = tabulate("EXPERIMENT REPLAY path (run_experiment / hit_with_recession_shock, read_shocks=True), base scenario, "
               f"T={pl.shape[0]}, N={pl.shape[1]}", pl, mh, wd, J, atoms, G_emp, G_u, permshk_hist=ps)

# ---- (a) the LIVE path: fresh per-state draws (read_shocks = False), 8 quarters
a.read_shocks = False; a.T_sim = 8
a.track_vars = list(dict.fromkeys(list(a.track_vars) + ["PermShk", "Mrkv"]))
a.initialize_sim(); a.simulate(8)
pl2 = np.asarray(a.history["pLvl"], dtype=float)
mh2 = np.asarray(a.history["Mrkv"], dtype=int)
ps2 = np.asarray(a.history["PermShk"], dtype=float)
live = tabulate("LIVE path (read_shocks=False: HARK get_shocks draws psi * PermGroFac[state] per realized state), "
                f"T={pl2.shape[0]}, N={pl2.shape[1]}", pl2, mh2, None, J, atoms, G_emp, G_u, permshk_hist=ps2)

# ---- quantification (closed form) for the replay path
u = float(a.Urate_normal); logG = float(np.log(G_emp)); L = float(a.LivPrb[0][0])
print("\n=== quantification (HS, closed form) ===")
print(f"fraction of household-quarters affected ~ u = {u:.4f} (observed unemployed share of survivor quarters in the replay: "
      f"{rep['by_state'].get('unemployed (emp>=1)', {}).get('share_of_survivor_quarters', float('nan')):.4f})")
print(f"per-quarter drift of log p: solver/TM (1-u)*log G = {(1-u)*logG:.6f}; MC replay log G = {logG:.6f}; "
      f"excess u*log G = {u*logG:.6f} per quarter (+{100*u*logG:.3f} % of E[p] per quarter; +{100*40*u*logG:.2f} % over a 40-quarter experiment)")
Ep_full = (1 - L) / (1 - L * np.exp(logG)); Ep_eff = (1 - L) / (1 - L * np.exp((1 - u) * logG))
print(f"stationary uncapped E[p]/E[p0] if the drift ran for life: log G -> {Ep_full:.3f}, (1-u) log G -> {Ep_eff:.3f}, "
      f"ratio {Ep_full/Ep_eff:.4f} (+{100*(Ep_full/Ep_eff-1):.1f} %) -- an upper bound; the experiments run ~40 quarters from a "
      f"panel seeded at the TM's own ((1-u) log G) ergodic")
