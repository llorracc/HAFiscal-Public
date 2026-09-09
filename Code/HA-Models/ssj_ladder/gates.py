"""The gate suite. Every function returns {measured, threshold, PASS} dicts — the verdict
JSON is built from these verbatim, so a gate can never pass silently.

The flow-budget identity is the ABRS block contract's testable core (certified against
the reference implementation 2026-09-01: its own fake-news Jacobian delivers the cash at
the shock date INCLUDING column 0):

    J_A[t,s] - rho*J_A[t-1,s] + J_C[t,s]  =  cash_s * 1{t==s},    rho = R*LivPrb.
"""
import numpy as np


def _budget(JA, JC, rho):
    lag = np.zeros_like(JA)
    lag[1:] = JA[:-1]
    return JA - rho * lag + JC


def _gate(measured, threshold, larger_is_fail=True):
    ok = (measured <= threshold) if larger_is_fail else (measured >= threshold)
    return {"measured": float(measured), "threshold": float(threshold), "PASS": bool(ok)}


def s_gates(cell, rung):
    """S tier: per-engine structural identities, every input, every column."""
    th = rung["thresholds"]
    rho = rung["model"]["R"] * rung["model"]["livprb"]
    T = cell["T"]
    disc = rho ** (-np.arange(T))
    out = {}
    for i in rung["inputs"]:
        JA, JC = cell[f"A_{i}"], cell[f"C_{i}"]
        r = _budget(JA, JC, rho)
        cash = np.diag(r).copy()
        off = r - np.diag(cash)
        maxJ = max(np.abs(JA).max(), np.abs(JC).max())
        c1 = cash[1:]
        col0_rel = abs(cash[0] - np.median(c1)) / abs(np.median(c1))
        col0_th = (th["s_col0_income_rel"] if i in rung["income_inputs"]
                   else th["s_col0_r_rel"])
        pv_lhs = disc @ JC
        pv_rhs = cash * disc - rho ** (-(T - 1)) * JA[T - 1, :]
        deliv_ok = bool((np.argmax(np.abs(r), axis=0) == np.arange(T)).all())
        out[i] = {
            "off_delivery_rel": _gate(np.abs(off).max() / maxJ, th["s_off_delivery_rel"]),
            "cash_spread_rel": _gate((c1.max() - c1.min()) / abs(np.median(c1)),
                                     th["s_cash_spread_rel"]),
            "announce_row0": _gate(np.abs(r[0, 1:]).max(), th["s_announce"]),
            "pv_identity": _gate(np.abs(pv_lhs - pv_rhs).max(), th["s_pv"]),
            "col0_cash_rel": _gate(col0_rel, col0_th),
            # terminal-populated catches the bug072-class EMPTY terminal row;
            # for tiny-cash inputs at impatient beta the true value sits at or
            # below the engines' arithmetic noise floors (A2: step4 1.8e-10 vs
            # twin ~1e-55 on UI_extend) and the gate is uninformative — a rung
            # may scope it via rung["terminal_inputs"].
            ("terminal_populated"
             if i in rung.get("terminal_inputs", rung["inputs"])
             else "_terminal_diag"):
                _gate(abs(JC[T - 1, 0]), th["s_terminal_min"],
                      larger_is_fail=False),
            "delivery_row_is_s": {"measured": deliv_ok, "threshold": True,
                                  "PASS": deliv_ok},
            "_cash_median": float(np.median(c1)),
        }
    return out


def x_gates(step4_cell, ssj_cell, s4, sj, rung, n_pts):
    """X tier: cross-engine at one pinned resolution."""
    th = rung["thresholds"]
    out = {}
    for i in rung["income_inputs"]:
        c4, cj = s4[i]["_cash_median"], sj[i]["_cash_median"]
        out[f"cash_{i}"] = _gate(abs(c4 - cj) / abs(cj), th["x_cash_rel"])
    # r is grid-limited through its own A_ss: gate PER ENGINE against own A_ss
    for lab, cell, s in (("step4", step4_cell, s4), ("ssj", ssj_cell, sj)):
        out[f"r_own_ss_{lab}"] = _gate(
            abs(s["r"]["_cash_median"] / cell["A_ss"] - 1.0), th["x_r_own_ss_rel"])
    key = {50: "x_relgap_50", 150: "x_relgap_150"}.get(int(n_pts))
    if key:
        for i in rung["inputs"]:
            gap = (np.linalg.norm(step4_cell[f"C_{i}"] - ssj_cell[f"C_{i}"])
                   / np.linalg.norm(ssj_cell[f"C_{i}"]))
            out[f"relgap_{i}"] = _gate(gap, th[key])
    return out


def r_gates(pairs, rung):
    """R tier: the 3-point refinement ladder. pairs = {n_pts: (step4_cell, ssj_cell)}.

    Gate the LAST ratio and the TOTAL shrinkage — the coarse rung alone flips sign with
    a legitimate grid choice (independent-rebuild finding, plan v2 §2).
    """
    th = rung["thresholds"]
    ns = sorted(pairs)
    gaps = {}
    for n in ns:
        d4, dj = pairs[n]
        gaps[n] = {i: float(np.linalg.norm(d4[f"C_{i}"] - dj[f"C_{i}"])
                            / np.linalg.norm(dj[f"C_{i}"])) for i in rung["inputs"]}
    out = {"gaps": gaps}
    for i in rung["inputs"]:
        last = gaps[ns[-1]][i] / gaps[ns[-2]][i]
        total = gaps[ns[0]][i] / gaps[ns[-1]][i]
        out[f"last_ratio_{i}"] = _gate(last, th["r_last_ratio"])
        out[f"total_shrink_{i}"] = _gate(total, th["r_total_shrink"],
                                         larger_is_fail=False)
    return out


def summarize(verdict):
    """Walk the nested gate dicts; return (n_pass, n_fail, failures)."""
    n_pass = n_fail = 0
    failures = []

    def walk(node, path):
        nonlocal n_pass, n_fail
        if isinstance(node, dict):
            if "PASS" in node:
                if node["PASS"]:
                    n_pass += 1
                else:
                    n_fail += 1
                    failures.append(path)
                return
            for k, v in node.items():
                ks = str(k)
                if not ks.startswith("_"):
                    walk(v, f"{path}/{ks}" if path else ks)

    walk(verdict, "")
    return n_pass, n_fail, failures
