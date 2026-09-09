"""The A0 twin in the installed `sequence_jacobian` package's OWN het block.

The reference implementation, not a reimplementation of step4: one-asset CRRA EGM
household with the same 2-state chain and the same income semantics as hh_setup
(transfers move every state; w and tau move the employed slot only; date-t r pays on
a_{t-1} via coh = (1+r)a + y). Hetinputs follow the package's named-return discipline —
a bare-expression return breaks its output-name inference.
"""
import numpy as np
from sequence_jacobian import het, interpolate, misc, grids

EMP = np.array([1.0, 0.0])


def hh_init(a_grid, y, r, eis):
    coh = (1 + r) * a_grid[np.newaxis, :] + y[:, np.newaxis]
    Va = (1 + r) * (0.1 * coh) ** (-1 / eis)
    return Va


@het(exogenous="Pi", policy="a", backward="Va", backward_init=hh_init)
def hh(Va_p, a_grid, y, r, beta, eis):
    uc_nextgrid = beta * Va_p
    c_nextgrid = uc_nextgrid ** (-eis)
    coh = (1 + r) * a_grid[np.newaxis, :] + y[:, np.newaxis]
    a = interpolate.interpolate_y(c_nextgrid + a_grid, coh, a_grid)
    misc.setmin(a, a_grid[0])
    c = coh - a
    Va = (1 + r) * c ** (-1 / eis)
    return Va, a, c


def income(w, tau, transfers, b_u, emp):
    y = w * (1.0 - tau) * emp + b_u * (1.0 - emp) + transfers
    return y


hh_ext = hh.add_hetinputs([income])


def build_cell(model, n_pts):
    """The SSJ twin at resolution n_pts. Same output schema as minimal_cell.build_cell."""
    wage, tau = model["wage_ss"], model["tau_ss"]
    b_u = 0.7 * wage * (1.0 - tau)
    Pi = np.array([[1.0 - model["EU"], model["EU"]],
                   [model["jf"], 1.0 - model["jf"]]])
    a_grid = grids.asset_grid(0.0, model["a_max"], int(n_pts))
    calib = dict(beta=model["beta"], r=model["R"] - 1.0, eis=1.0 / model["crra"],
                 w=wage, tau=tau, transfers=0.0, b_u=b_u, emp=EMP,
                 Pi=Pi, a_grid=a_grid)
    ss = hh_ext.steady_state(calib, backward_tol=1e-12, forward_tol=1e-13)
    J = hh_ext.jacobian(ss, inputs=["transfers", "w", "tau", "r"], T=model["T"])
    out = {"A_ss": float(ss["A"]), "C_ss": float(ss["C"]),
           "n_pts": int(n_pts), "T": int(model["T"])}
    for i in ("transfers", "w", "tau", "r"):
        out[f"C_{i}"] = np.asarray(J["C"][i])
        out[f"A_{i}"] = np.asarray(J["A"][i])
    return out


# ---- A1: the 6-state twin -------------------------------------------------

EMP6 = np.array([1., 0., 0., 0., 0., 0.])
U12 = np.array([0., 1., 1., 0., 0., 0.])
U34 = np.array([0., 0., 0., 1., 1., 0.])
U345 = np.array([0., 0., 0., 1., 1., 1.])


def income6(w, tau, transfers, UI_extend, UI_rr, ue_lvl, nb_lvl, ext_coef,
            emp6, u12, u34, u345):
    """Mirrors hh_setup's net-arm instrument semantics: w and tau move the
    employed slot only (benefit LEVELS are constants); UI_extend pays
    ext_coef per unit into U3/U4; UI_rr into U1/U2; transfers everywhere."""
    y = (w * (1.0 - tau) * emp6 + ue_lvl * u12 + nb_lvl * u345
         + transfers + ext_coef * UI_extend * u34 + ext_coef * UI_rr * u12)
    return y


hh6 = hh.add_hetinputs([income6])


def chain6_row(EU, jf):
    j = jf
    return np.array([
        [1.0 - EU, EU, 0., 0., 0., 0.],
        [j, 0., 1. - j, 0., 0., 0.],
        [j, 0., 0., 1. - j, 0., 0.],
        [j, 0., 0., 0., 1. - j, 0.],
        [j, 0., 0., 0., 0., 1. - j],
        [j, 0., 0., 0., 0., 1. - j]])


def build_cell_a1(model, n_pts):
    wage, tau = model["wage_ss"], model["tau_ss"]
    Pi = chain6_row(model["EU"], model["jf"])
    a_grid = grids.asset_grid(0.0, model["a_max"], int(n_pts))
    calib = dict(beta=model["beta"], r=model["R"] - 1.0,
                 eis=1.0 / model["crra"], w=wage, tau=tau, transfers=0.0,
                 UI_extend=0.0, UI_rr=0.0,
                 ue_lvl=model["ue_rr"] * wage * (1.0 - tau),
                 nb_lvl=model["nb_rr"] * wage * (1.0 - tau),
                 ext_coef=wage * (1.0 - tau),
                 emp6=EMP6, u12=U12, u34=U34, u345=U345,
                 Pi=Pi, a_grid=a_grid)
    ss = hh6.steady_state(calib, backward_tol=1e-12, forward_tol=1e-13)
    J = hh6.jacobian(ss, inputs=["transfers", "w", "tau", "r",
                                 "UI_extend", "UI_rr"], T=model["T"])
    out = {"A_ss": float(ss["A"]), "C_ss": float(ss["C"]),
           "n_pts": int(n_pts), "T": int(model["T"])}
    for i in ("transfers", "w", "tau", "r", "UI_extend", "UI_rr"):
        out[f"C_{i}"] = np.asarray(J["C"][i])
        out[f"A_{i}"] = np.asarray(J["A"][i])
    return out


# ---- A2: growth-normalized twin (convention P — see the 2026-09-02 note) --

def hh_init_g(a_grid, y, r_b, r_e, eis):
    coh = (1 + r_b) * a_grid[np.newaxis, :] + y[:, np.newaxis]
    Va = (1 + r_e) * (0.1 * coh) ** (-1 / eis)
    return Va


@het(exogenous="Pi", policy="a", backward="Va", backward_init=hh_init_g)
def hh_g(Va_p, a_grid, y, r_b, r_e, beta, eis):
    """Uniform-growth normalization, plain measure (P): budget factor
    1 + r_b = R/Gamma; Euler factor 1 + r_e = R * Gamma^(-sigma)."""
    uc_nextgrid = beta * Va_p
    c_nextgrid = uc_nextgrid ** (-eis)
    coh = (1 + r_b) * a_grid[np.newaxis, :] + y[:, np.newaxis]
    a = interpolate.interpolate_y(c_nextgrid + a_grid, coh, a_grid)
    misc.setmin(a, a_grid[0])
    c = coh - a
    Va = (1 + r_e) * c ** (-1 / eis)
    return Va, a, c


hh_g6 = hh_g.add_hetinputs([income6])


def build_cell_a2(model, n_pts):
    """The (P)-convention growth twin: same chain/incomes as A1, Gamma<1
    through the two normalized rates. Its own flow budget holds at
    rho_P = R/Gamma with unit cash; it is NOT a parity target for the
    step4 (W) cell — the cross-engine gate is the derived cash ratio."""
    wage, tau = model["wage_ss"], model["tau_ss"]
    G = model["gamma"]
    sigma = model["crra"]
    Pi = chain6_row(model["EU"], model["jf"])
    a_grid = grids.asset_grid(0.0, model["a_max"], int(n_pts))
    calib = dict(beta=model["beta"],
                 r_b=model["R"] / G - 1.0,
                 r_e=model["R"] * G ** (-sigma) - 1.0,
                 eis=1.0 / sigma, w=wage, tau=tau, transfers=0.0,
                 UI_extend=0.0, UI_rr=0.0,
                 ue_lvl=model["ue_rr"] * wage * (1.0 - tau),
                 nb_lvl=model["nb_rr"] * wage * (1.0 - tau),
                 ext_coef=wage * (1.0 - tau),
                 emp6=EMP6, u12=U12, u34=U34, u345=U345,
                 Pi=Pi, a_grid=a_grid)
    ss = hh_g6.steady_state(calib, backward_tol=1e-12, forward_tol=1e-13)
    J = hh_g6.jacobian(ss, inputs=["transfers", "w", "tau", "r_b",
                                   "UI_extend", "UI_rr"], T=model["T"])
    out = {"A_ss": float(ss["A"]), "C_ss": float(ss["C"]),
           "n_pts": int(n_pts), "T": int(model["T"])}
    name = {"transfers": "transfers", "w": "w", "tau": "tau", "r_b": "r",
            "UI_extend": "UI_extend", "UI_rr": "UI_rr"}
    for i in name:
        out[f"C_{name[i]}"] = np.asarray(J["C"][i])
        out[f"A_{name[i]}"] = np.asarray(J["A"][i])
    return out
