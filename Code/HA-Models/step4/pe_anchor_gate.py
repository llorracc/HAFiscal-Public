#!/usr/bin/env python
"""H0/H1 of the HANK⇄PE anchored debug chain (plans/20260830-1455h_hank-pe-anchored-debug-chain_plan.md).

Rung H0 (input identity): build the PE model's own agents and the HANK household block from the SAME
`Parameters.return_parameters(...)` call, then compare — field by field, per education group — everything the two
sides are supposed to share: the discount-factor atoms (post GIC cap), CRRA, Rfree, LivPrb, PermGroFac, the base
Markov chain, the solve grids, the shock standard deviations, and the employed state's income distribution.

Rung H1 (solver identity, `--solve`): one backward solve of the two agents on the identical inputs; compares the
consumption function state by state on a common grid.

Every row is classified:
  MATCH     max|Δ| ≤ tol — byte-frontier held
  EXPECTED  a difference this file names and explains (the documented residuals of the R-e ruling and the HANK
            block's own construction); the NUMBER is still reported, so an expected difference that changes size
            shows up
  FAIL      a difference nobody declared — the gate's product

The PE side is `AggFiscalType` (what the PE model solves and simulates); the HANK side is `step4.hh_setup.build()`,
whose agents the Jacobian stage deep-copies. The state spaces differ by the documented lumping (the PE base chain
carries 2 + UBspell_normal + n_extension micro states, the HANK block 6); it is applied through
`normalize_to_hank_states`, which asserts lumpability rather than assuming it.

usage (cwd = Code/HA-Models), with the environment of the HANK arm under test:
  python -m step4.pe_anchor_gate [--tol 1e-12] [--solve] [--out h0_report.json]
"""
import argparse
import json
import os
import sys

import numpy as np

EDUC = ("dropout", "highschool", "college")

# Differences this gate DECLARES: field -> the reason a reader can check. Anything else numeric is a FAIL.
EXPECTED = {
    "cFunc/cap_atom": (
        "the GIC-cap atom has no finite wealth target (GPF_in > 1), so its policy approaches the "
        "perfect-foresight limit slowly and the two solvers' upper-region treatments separate: the PE's "
        "`solve_agg_cons_markov_alt` carries the PF-decay tail machinery with the MEASURED tail "
        "exponent (local_q_tail), while the HANK block's vendored `_solve_ConsMarkov` carries the "
        "power-law FORM (BUG-106) but the slope-derived exponent — decay_extrap_Q is not passed at "
        "ConsMarkovModel.py:790/:813 (dual-path sweep 2026-09-02: the declared residual below is "
        "the exponent gap, not a missing tail). Measured 2026-08-30 (rung H1): identical to 1e-15 inside the grid at the "
        "low/middle atoms, and at the cap atom 0.002 % of consumption at m=10 rising to 0.15 % at the solve-grid "
        "top and 0.3-0.4 % beyond it. Aggregate effect measured at rung H2 and immaterial (see below)"),
    "h2/solve_grid_coverage": (
        "the solve grid tops at aXtraMax (356/375/383 by education) while the distribution grid runs to "
        "dist mMax = 1300, so the ergodic distribution is evaluated on an extrapolated policy above the solve top. "
        "Mass there is ~1e-16 at the low/middle atoms; at the CAP atoms it is 0.017 %/0.029 %/0.52 % of households "
        "holding 1.4 %/2.0 %/12.0 % of that atom's wealth. Consequence measured by rebuilding with a covering solve "
        "grid (aXtraMax 1400): A_ss -0.10 %/-0.12 %/-0.07 %, C_ss -0.002 %/-0.002 %/-0.009 % — immaterial, so the "
        "production grids stand; the number is reported here so a change in it shows up"),
    "IncShkDstn/employed/TranShk": (
        "the HANK block scales the employed transitory shock by wage_ss*(1-tau_ss) (net income level; "
        "HAFISCAL_HANK_INCOME_LEVEL=net, the R-e item-2 arm) — the PE's own level is gross"),
    "dist_grid": (
        "documented R-e residual: the fake-news distribution grid lives on market resources m (mCount/mMax), "
        "the PE transition matrix's on end-of-period assets a (dist_aGrid_count/max); exp-mult spacing; mMin=1e-4"),
}


def _arr(x):
    return np.asarray(x, dtype=float)


def _dstn(d):
    """(pmv, atoms) of a HARK discrete distribution, atoms as (n_shock_dims, n_points)."""
    return _arr(d.pmv), _arr(d.atoms)


def _pe_states(agent):
    """The PE agent's per-state income list if the live Markov list has been installed, else [employed].
    `AggFiscalType` carries a single `BufferStockIncShkDstn` until a driver installs the list."""
    p0 = agent.IncShkDstn[0]
    return list(p0) if isinstance(p0, (list, tuple)) else [p0]


def install_pe_markov_income(agent, init):
    """Install the PE model's own per-state Markov income list on `agent`, the way the live Step-5 driver does
    (`Simulate.py:245-273`): the employed state's distribution, then `UBspell_normal` with-benefit states and the
    remaining no-benefit states, all built by the income-process SST from the agent's own flags. Without this an
    `AggFiscalType` still carries the constructor's single `BufferStockIncShkDstn` and its solver raises
    `'BufferStockIncShkDstn' object is not subscriptable`."""
    from income_process_sst import build_unemployed_inc_shk_dstn   # noqa: E402
    p0 = agent.IncShkDstn[0]
    emp = p0[0] if isinstance(p0, (list, tuple)) else p0
    p_on = bool(getattr(agent, "perm_shocks_during_unemployment", False))
    t_on = bool(getattr(agent, "tran_shocks_during_unemployment", False))
    ui = build_unemployed_inc_shk_dstn(emp, agent.IncUnemp, p_on, t_on)
    nb = build_unemployed_inc_shk_dstn(emp, agent.IncUnempNoBenefits, p_on, t_on)
    J = int(init["num_base_MrkvStates"]); ub = int(init["UBspell_normal"])
    agent.IncShkDstn = [[emp] + [ui] * ub + [nb] * (J - 1 - ub)]
    agent.IncShkDstn_base = agent.IncShkDstn
    return agent


def pe_side(install_income=False):
    """The PE model's own construction: return_parameters + AggFiscalType per education group.
    `install_income=True` also installs the per-state Markov income list the live driver installs (needed to solve)."""
    sys.argv = sys.argv[:1]                      # Parameters.py parses sys.argv (Rfree, CRRA, IncUnemp)
    from Parameters import return_parameters     # noqa: E402
    from AggFiscalModel import AggFiscalType     # noqa: E402
    r = return_parameters(Parametrization="Baseline", OutputFor="_Main.py")
    inits = [dict(r[0]), dict(r[1]), dict(r[2])]          # snapshot: hh_setup.build() MUTATES these dicts
    DiscFacDstns = r[4]
    agents = []
    for init in inits:
        a = AggFiscalType(**dict(init))
        a.cycles = 0
        if install_income:
            install_pe_markov_income(a, init)
        agents.append(a)
    return {"inits": inits, "DiscFacDstns": DiscFacDstns, "agents": agents}


def hank_side():
    """The HANK household block exactly as the Jacobian stage receives it."""
    from step4 import hh_setup                   # noqa: E402
    ctx = hh_setup.build()
    return {"ctx": ctx, "inits": [ctx.init_dropout, ctx.init_highschool, ctx.init_college],
            "DiscFacDstns": ctx.DiscFacDstns, "agents": ctx.BaseTypeList,
            "IncShkDstn": ctx.IncShkDstn, "n_states": ctx.n_states}


def rows_for_group(e, pe, hk, tol):
    """Compare one education group. Returns a list of (field, status, max_abs_diff, note)."""
    from step4.hh_setup import normalize_to_hank_states, pe_employment_block

    out = []

    def row(field, a, b, note="", expect_key=None):
        a, b = _arr(a), _arr(b)
        if a.shape != b.shape:
            out.append((field, "FAIL", float("nan"), f"shape PE{a.shape} HANK{b.shape} {note}".strip()))
            return
        m = float(np.nanmax(np.abs(a - b))) if a.size else 0.0
        if expect_key is not None:
            out.append((field, "EXPECTED", m, EXPECTED[expect_key]))
        else:
            out.append((field, "MATCH" if m <= tol else "FAIL", m, note))

    pe_init, hk_init = pe["inits"][e], hk["inits"][e]
    pe_agent, hk_agent = pe["agents"][e], hk["agents"][e]
    n = hk["n_states"]

    # --- discount factors (the estimation's own object, post GIC cap) -------------------------------
    p_dfd, h_dfd = pe["DiscFacDstns"][e], hk["DiscFacDstns"][e]
    row("DiscFacDstn/atoms", _arr(p_dfd.atoms).ravel(), _arr(h_dfd.atoms).ravel())
    row("DiscFacDstn/pmv", _arr(p_dfd.pmv).ravel(), _arr(h_dfd.pmv).ravel())

    # --- preferences and returns -------------------------------------------------------------------
    row("CRRA", [pe_agent.CRRA], [hk_agent.CRRA])
    # the HANK block sets Rfree/LivPrb from literals (np.ones(n)*1.01, *0.99375) instead of reading the PE's:
    # this row is what makes that safe — it fails the moment the PE calibration moves off those values.
    row("Rfree", _arr(pe_init["Rfree"]).ravel()[:n], _arr(hk_init["Rfree"][0]).ravel()[:n],
        "HANK sets np.ones(n)*1.01 by literal; PE from the calibration")
    row("LivPrb", _arr(pe_init["LivPrb"][0]).ravel()[:n], _arr(hk_init["LivPrb"][0]).ravel()[:n],
        "HANK sets np.ones(n)*0.99375 by literal; PE from the calibration")

    # --- the base chain and growth, through the documented lumping ---------------------------------
    pe_m, pe_g = pe_employment_block(_arr(pe_init["MrkvArray"][0]), _arr(pe_init["PermGroFac"][0]))
    pe_m6, pe_g6 = normalize_to_hank_states(pe_m, n, pe_g)      # asserts lumpability
    hk_m = _arr(hk_agent.MrkvArray[0])
    hk_g = _arr(hk_agent.PermGroFac[0]).ravel()
    row("MrkvArray(base, lumped to HANK states)", pe_m6, hk_m[:n, :n])
    row("PermGroFac(lumped)", pe_g6, hk_g[:n])

    # --- shocks and solve grids ---------------------------------------------------------------------
    for k in ("PermShkStd", "TranShkStd"):
        row(k, _arr(pe_init[k]).ravel(), _arr(hk_init[k]).ravel())
    for k in ("aXtraMax", "aXtraCount", "aXtraMin", "aXtraNestFac", "PermShkCount", "TranShkCount",
              "UnempPrb", "IncUnemp"):
        if k in pe_init and k in hk_init:
            row("solve_grid/" + k if k.startswith("aXtra") else k, [pe_init[k]], [hk_init[k]])

    # --- the distribution grid: a declared difference, reported with its numbers --------------------
    out.append(("dist_grid/mCount", "EXPECTED", float(hk_init.get("mCount", np.nan)), EXPECTED["dist_grid"]))
    out.append(("dist_grid/mMax", "EXPECTED", float(hk_init.get("mMax", np.nan)), EXPECTED["dist_grid"]))

    # --- the employed state's income distribution ---------------------------------------------------
    pe_states = _pe_states(pe_agent)
    p_pmv, p_at = _dstn(pe_states[0])
    h_pmv, h_at = _dstn(hk["IncShkDstn"][e][0])
    row("IncShkDstn/employed/pmv", p_pmv, h_pmv)
    row("IncShkDstn/employed/PermShk", p_at[0], h_at[0])
    row("IncShkDstn/employed/TranShk", p_at[1], h_at[1], expect_key="IncShkDstn/employed/TranShk")
    # the level wedge stated as a ratio, so a change in the wedge itself is visible
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.nanmedian(h_at[1] / p_at[1]) if p_at[1].size else np.nan
    out.append(("IncShkDstn/employed/TranShk:level_ratio", "EXPECTED", float(ratio),
                "HANK/PE median ratio; = wage_ss*(1-tau_ss) = 0.7 under INCOME_LEVEL=net, 1.0 under gross"))
    # --- the unemployment slots ---------------------------------------------------------------------
    # Since BUG-105 both sides build these through the SAME SST call, so where the PE's own per-state list is
    # installed they are compared as real rows: the permanent-shock ROW must be identical (it carries no level),
    # and the benefit LEVEL differs only by the declared (1-tau_ss) wedge (ratio reported; exactly 1 under
    # HAFISCAL_HANK_INCOME_LEVEL=gross).
    have_pe_list = len(pe_states) > 1
    for j in range(1, min(n, len(hk["IncShkDstn"][e]))):
        hp, ha = _dstn(hk["IncShkDstn"][e][j])
        if have_pe_list and j < len(pe_states):
            pp, pa = _dstn(pe_states[j])
            # the psi row, compared on whichever support each side carries (both come from the same SST decision):
            # E[psi] and E[1/psi] are the moments the solver and the GIC bound use.
            for nm, f in (("E[psi]", lambda x: x), ("E[1/psi]", lambda x: 1.0 / x)):
                mp = float(np.sum(pp * f(pa[0]))); mh = float(np.sum(hp * f(ha[0])))
                row(f"IncShkDstn/unemp{j}/{nm}", [mp], [mh],
                    "both sides now build this through income_process_sst (BUG-105)")
            with np.errstate(divide="ignore", invalid="ignore"):
                lvl_ratio = float(np.nanmedian(ha[1]) / np.nanmedian(pa[1])) if pa[1].size else float("nan")
            out.append((f"IncShkDstn/unemp{j}/TranShk:level_ratio", "EXPECTED", lvl_ratio,
                        "HANK/PE benefit-level ratio; = wage_ss*(1-tau_ss) under INCOME_LEVEL=net, 1.0 under gross"))
        else:
            out.append((f"IncShkDstn/unemp{j}/TranShk:level", "EXPECTED", float(np.nanmedian(ha[1])),
                        "the PE agent carries no per-state list here (run with --solve to install it); "
                        "HANK slots are the replacement rates 0.7 (with UI) / 0.5 (after) at its income level"))
            out.append((f"IncShkDstn/unemp{j}/PermShk:degenerate", "EXPECTED", float(np.nanmax(np.abs(ha[0] - 1.0))),
                        "0 ⇒ psi ≡ 1 in unemployment; >0 ⇒ the employed marginal is kept — since BUG-105 this "
                        "follows the PE model's perm_shocks_during_unemployment, i.e. the world"))
    return out


def attach_economy(pe, ad_elasticity=0.0):
    """Give the PE agents their economy exactly as the PE model does (welfare6_scenario.py:527-565): the
    aggregate-demand economy supplies Cgrid / CFunc / ADFunc, without which AggFiscalType cannot solve.
    `ad_elasticity=0` switches the AD channel off (ADFunc ≡ 1), so the PE's C-conditional two-loop solver
    should return the same policy as the HANK block's plain MarkovConsumerType solve — the H1 gate."""
    sys.argv = sys.argv[:1]
    from Parameters import return_parameters        # noqa: E402
    from AggFiscalModel import AggregateDemandEconomy   # noqa: E402
    init_eco = dict(return_parameters(Parametrization="Baseline", OutputFor="_Main.py")[3])
    init_eco["ADelasticity"] = ad_elasticity
    eco = AggregateDemandEconomy(**init_eco)
    eco.agents = pe["agents"]
    for a in pe["agents"]:
        a.get_economy_data(eco)
    return eco


def _c_of_m(sol_state, m, c_ratio=1.0):
    """Evaluate a consumption function at market resources m; C-conditional functions take the aggregate
    consumption ratio as a second argument (the PE's two-loop solver), plain ones do not."""
    try:
        return _arr(sol_state(m))
    except TypeError:
        return _arr(sol_state(m, np.full_like(m, c_ratio)))


def solve_rows(e, pe, hk, tol, eco=None, atoms=(0, 3, 6)):
    """H1: solve each side's agent on the identical inputs and compare the consumption functions.

    The PE side runs its own class and solver (`AggFiscalType`, C-conditional with the AD channel off, its Markov
    income list installed the live way); the HANK side the plain `MarkovConsumerType` the Jacobian stage uses. With H0
    green and the levels matched (`HAFISCAL_HANK_INCOME_LEVEL=gross`) the policies should agree to solver tolerance;
    a FAIL is a real divergence between the two solve paths. Compared at the calibration's own discount-factor atoms
    (`atoms`: low / middle / the GIC-cap atom), state by state in the HANK block's order — index 0 employed, 1..n-1
    the unemployment durations after the documented lumping."""
    pe_agent, hk_agent = pe["agents"][e], hk["agents"][e]
    betas = _arr(pe["DiscFacDstns"][e].atoms).ravel()
    m = np.linspace(0.1, 20.0, 200)
    out = []
    for d in atoms:
        if d >= betas.size:
            continue
        beta = float(betas[d])
        is_cap = (d == betas.size - 1)      # the GIC-cap atom: no finite target, the documented residual below
        try:
            # the HANK agents carry HARK's auto-constructed income; the Jacobian stage assigns the per-state
            # list at solve time (`jacobians.prepare_type_base`: agent_SS.IncShkDstn = deepcopy(IncDist)) — do
            # the same here, or the solver meets a BufferStockIncShkDstn where it expects a per-state list.
            hk_agent.IncShkDstn = [hk["IncShkDstn"][e]]
            for a in (pe_agent, hk_agent):
                a.cycles = 0
                a.DiscFac = beta
                if hasattr(a, "update_mrkv_array"):
                    a.update_mrkv_array("base")
                a.update_solution_terminal()
                a.solve()
        except Exception as exc:                                  # noqa: BLE001 — reported, not raised
            out.append((f"solve/beta[{d}]", "FAIL", float("nan"), f"solve raised: {exc!r}")); continue
        n_pe = len(pe_agent.solution[0].cFunc); n_hk = len(hk_agent.solution[0].cFunc)
        worst, worst_s = 0.0, -1
        for s in range(min(n_pe, n_hk, hk["n_states"])):
            try:
                cp = _c_of_m(pe_agent.solution[0].cFunc[s], m)
                ch = _c_of_m(hk_agent.solution[0].cFunc[s], m)
            except Exception as exc:                              # noqa: BLE001
                out.append((f"cFunc/beta[{d}]/state{s}", "FAIL", float("nan"), f"eval raised: {exc!r}")); continue
            dd = float(np.nanmax(np.abs(cp - ch)))
            if dd > worst:
                worst, worst_s = dd, s
            if is_cap:
                out.append((f"cFunc/beta[{d}]/state{s}", "EXPECTED", dd, EXPECTED["cFunc/cap_atom"]))
            else:
                out.append((f"cFunc/beta[{d}]/state{s}", "MATCH" if dd <= tol else "FAIL", dd,
                            f"beta={beta:.6f}; PE {n_pe} states vs HANK {n_hk}; identical inputs => identical policy"))
        out.append((f"cFunc/beta[{d}]/WORST", ("EXPECTED" if is_cap else ("MATCH" if worst <= tol else "FAIL")), worst,
                    (EXPECTED["cFunc/cap_atom"] if is_cap else f"beta={beta:.6f}, worst at state {worst_s}")))
    return out


def h2_rows(e, hk, educ_name):
    """H2: the steady state per atom, and the solve-grid coverage residual the H1 cap-atom row points at.

    Reports, for the middle and cap atoms: A_ss, C_ss, the ergodic mass ABOVE the solve-grid top (where the policy
    is extrapolated and the two engines separate) and the share of that atom's wealth held there. These are
    reported numbers, not pass/fail: the consequence was measured once (see EXPECTED['h2/solve_grid_coverage'])
    and is immaterial; the rows exist so a change in the geometry shows up in the report."""
    from copy import deepcopy
    inits = [hk["ctx"].init_dropout, hk["ctx"].init_highschool, hk["ctx"].init_college]
    betas = _arr(hk["DiscFacDstns"][e].atoms).ravel()
    top = float(inits[e]["aXtraMax"])
    out = []
    for d in (3, betas.size - 1):
        a = deepcopy(hk["agents"][e]); a.cycles = 0
        a.IncShkDstn = deepcopy([hk["IncShkDstn"][e]]); a.DiscFac = float(betas[d])
        a.compute_steady_state()
        n_m = len(a.MrkvArray[0]); n_a = len(a.dist_mGrid); n_p = len(a.dist_pGrid)
        D = _arr(a.vec_erg_dstn).reshape(n_m, n_a, n_p); g = _arr(a.dist_mGrid)
        above = g > top
        mass = float(D[:, above, :].sum())
        w = D.sum(axis=(0, 2))
        share = float((w[above] * g[above]).sum() / max((w * g).sum(), 1e-16))
        tag = "cap" if d == betas.size - 1 else f"beta[{d}]"
        out.append((f"h2/{tag}/A_ss", "EXPECTED", float(a.A_ss), "steady-state assets of this atom"))
        out.append((f"h2/{tag}/C_ss", "EXPECTED", float(a.C_ss), "steady-state consumption of this atom"))
        out.append((f"h2/{tag}/mass_above_solve_top", "EXPECTED", mass, EXPECTED["h2/solve_grid_coverage"]))
        out.append((f"h2/{tag}/wealth_share_above_solve_top", "EXPECTED", share, EXPECTED["h2/solve_grid_coverage"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tol", type=float, default=1e-12)
    ap.add_argument("--solve", action="store_true", help="also run rung H1 (one backward solve per side)")
    ap.add_argument("--h2", action="store_true", help="also run rung H2 (steady state per atom + solve-grid coverage)")
    ap.add_argument("--out", help="write the rows as JSON")
    a = ap.parse_args(argv)

    here = os.path.abspath(os.path.dirname(__file__))
    root = os.path.dirname(here)
    for p in (root, os.path.join(root, "FromPandemicCode")):
        if p not in sys.path:
            sys.path.insert(0, p)

    print("[pe-anchor] building the PE side (return_parameters + AggFiscalType)", flush=True)
    pe = pe_side(install_income=a.solve)
    eco = attach_economy(pe) if a.solve else None
    print("[pe-anchor] building the HANK side (step4.hh_setup.build)", flush=True)
    hk = hank_side()

    report, n_fail, n_exp = [], 0, 0
    for e, name in enumerate(EDUC):
        rows = rows_for_group(e, pe, hk, a.tol)
        if a.solve:
            rows += solve_rows(e, pe, hk, a.tol, eco)
        if a.h2:
            rows += h2_rows(e, hk, name)
        for field, status, val, note in rows:
            report.append({"educ": name, "field": field, "status": status, "value": val, "note": note})
            n_fail += status == "FAIL"
            n_exp += status == "EXPECTED"

    print(f"\n[pe-anchor] H0{'+H1' if a.solve else ''} report — tol {a.tol:g}\n")
    print(f"{'educ':11s} {'field':44s} {'status':9s} {'max|Δ| / value':>15s}")
    for r in report:
        flag = "" if r["status"] == "MATCH" else ("  <-- " + r["note"][:88] if r["status"] == "FAIL" else "")
        print(f"{r['educ']:11s} {r['field']:44s} {r['status']:9s} {r['value']:15.6g}{flag}")
    n_match = len(report) - n_fail - n_exp
    print(f"\n[pe-anchor] {n_match} MATCH, {n_exp} EXPECTED (declared), {n_fail} FAIL")
    if a.out:
        with open(a.out, "w") as f:
            json.dump({"tol": a.tol, "rows": report,
                       "summary": {"match": n_match, "expected": n_exp, "fail": n_fail}}, f, indent=1)
        print(f"[pe-anchor] wrote {a.out}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
