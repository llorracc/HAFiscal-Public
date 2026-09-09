"""P10 (BUG-074, owner: financing treatment is paramount): the COMPLETE
financing matrix — 3 policies x {tau-financed, G-financed} x 3 monetary
regimes, in BOTH metrics (spending multiplier + u'-weighted welfare
multiplier from the W-Jacobians).

Design: ONE tau-financed family (tau_t = tau_ss + dtau_x_t + phi_b rule;
the additive-shifter construction, so the tax cut can ride the same rule
as its comparators) and ONE G-financed family (tau exogenous-shiftable,
G rule; generalized to carry the UI_extend/UI_rr cost terms production's
fiscal_G lacks — zero for the tax-cut experiment, so production anchors
are preserved). Built-in anchors: tau-financed {transfers, UI} and
G-financed {tax} must reproduce the production 3x3 table.
"""
import os
import pickle
import sys

import numpy as np
import scipy.sparse as sp

HA = "/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models"
B = os.path.join(HA, "solution_cache", "_armc_bench")
sys.path.insert(0, HA)
sys.path.insert(0, os.path.join(HA, "FromPandemicCode"))

# ---- SAM chain + UJAC + calibration (verbatim ge.py constants) ----
job_find = 2 / 3
EU_prob = 0.0306834
job_sep = EU_prob / (1 - job_find)
markov_array_ss = np.array(
    [[1 - job_sep * (1 - job_find), job_find, job_find, job_find, job_find, job_find],
     [job_sep * (1 - job_find), 0., 0., 0, 0, 0],
     [0., (1 - job_find), 0., 0., 0., 0.],
     [0., 0, (1 - job_find), 0., 0., 0.],
     [0., 0, 0., (1 - job_find), 0., 0.],
     [0., 0., 0, 0, (1 - job_find), (1 - job_find)]])
num_mrkv = 6
eig, ss = sp.linalg.eigs(markov_array_ss, k=1, which='LM')
ss_dstn = (ss[:, 0] / ss[:, 0].sum()).real
N_ss = ss_dstn[0]

def create_matrix_U(dx):
    jf = job_find + dx
    return np.array(
        [[1 - job_sep * (1 - jf), jf, jf, jf, jf, jf],
         [job_sep * (1 - jf), 0., 0., 0, 0, 0],
         [0., (1 - jf), 0., 0., 0., 0.],
         [0., 0, (1 - jf), 0., 0., 0.],
         [0., 0, 0., (1 - jf), 0., 0.],
         [0., 0., 0, 0, (1 - jf), (1 - jf)]])

dx = 0.0001
bigT = 300
dstn = ss_dstn
UJAC = np.zeros((num_mrkv, bigT, bigT))
for s in range(bigT):
    for i in range(bigT):
        if i == s:
            dstn = np.dot(create_matrix_U(dx), dstn)
        else:
            dstn = np.dot(markov_array_ss, dstn)
        UJAC[:, i, s] = (dstn - ss_dstn) / dx

alpha = .65
phi_ss = .71
v_ss = N_ss * job_sep / phi_ss
seachers = (1 - N_ss) + N_ss * job_sep
theta_ss = v_ss / seachers
chi_ss = (phi_ss ** (1 / -alpha) / theta_ss) ** (-alpha)
eta_ss = chi_ss * theta_ss ** (1 - alpha)
R = 1.01
r_ss = R - 1
A_ss_sim = 1.4324029855872642
delta = ((R ** 4) * (1 - (1 / 5))) ** 0.25
qb_ss = 1 / (R - delta)
B_ss = A_ss_sim / qb_ss
wage_ss = 1.0
tau_ss = 0.3
UI = (1 - tau_ss) * .5 * wage_ss

with open(os.path.join(HA, "FromPandemicCode", "HA_Fiscal_Jacs.obj"), 'rb') as f:
    OBJ = pickle.load(f)
C_ss = C_ss_sim = float(OBJ['C_ss_weighted'])
up_pop = float(OBJ['Uprime_ss_weighted'])

kappa = .07 * (wage_ss * phi_ss)
HC_ss = ((kappa / phi_ss) * (1 - (1 / R) * (1 - job_sep)) + wage_ss)
epsilon_p = 6
MC_ss = (epsilon_p - 1) / epsilon_p
Z_ss = HC_ss / MC_ss
Y_ss = Z_ss * N_ss
G_ss = tau_ss * wage_ss * ss_dstn[0] - (UI * (ss_dstn[1] + ss_dstn[2])
                                        + (1 + delta * qb_ss) * B_ss - qb_ss * B_ss)
pi_ss = 0.0
varphi = 96.9
kappa_p_ss = epsilon_p / varphi

import sequence_jacobian as sj  # noqa: E402
from sequence_jacobian.classes import JacobianDict, SteadyStateDict  # noqa: E402
from sequence_jacobian import create_model  # noqa: E402
from copy import deepcopy  # noqa: E402

SPLURGE = 0.3
SPL_LIST = ['transfers', 'tau', 'UI_extend', 'UI_rr', 'eta', 'w']

def overlay(Jd):
    out = dict(Jd)
    periods = Jd['transfers'].shape[0]
    for ji in SPL_LIST:
        pv = np.sum((Jd[ji] / R ** np.arange(periods)), axis=0)
        comp = np.diag(pv * R ** np.arange(periods))
        out[ji] = SPLURGE * comp + (1 - SPLURGE) * Jd[ji]
    return out

C_spl = overlay(OBJ['C'])
A_spl = dict(OBJ['A'])
for ji in SPL_LIST:
    A_spl[ji] = (1 - SPLURGE) * OBJ['A'][ji]
W_spl = overlay(OBJ['W'])
Jacobian_Dict = JacobianDict({'C': C_spl, 'A': A_spl})
UJAC_dict = JacobianDict({
    'N': {'eta': UJAC[0]}, 'U1': {'eta': UJAC[1]}, 'U2': {'eta': UJAC[2]},
    'U3': {'eta': UJAC[3]}, 'U4': {'eta': UJAC[4]}, 'U5': {'eta': UJAC[5]}})

# ---- common blocks ----
@sj.simple
def unemployment1(U1, U2, U3, U4, U5):
    U = U1 + U2 + U3 + U4 + U5
    return U

@sj.simple
def marginal_cost(HC, Z):
    MC = HC / Z
    return MC

@sj.solved(unknowns={'HC': (-10, 10.0)}, targets=['HC_resid'], solver="brentq")
def hiring_cost(HC, Z, phi, job_sep, r_ante, w):
    HC_resid = HC - ((w + (kappa / (phi)) - (1 / (1 + r_ante)) * (1 - job_sep) * (kappa / (phi(+1)))))
    return HC_resid

@sj.solved(unknowns={'w': (-10, 10.0)}, targets=['wage_resid'], solver="brentq")
def wage_(w, N, phi_w):
    wage_resid = (w / wage_ss).apply(np.log) - (phi_w * (w(-1) / wage_ss).apply(np.log)
                                                + (1 - phi_w) * (N / N_ss).apply(np.log))
    return wage_resid

@sj.solved(unknowns={'pi': (-0.1, 0.1)}, targets=['nkpc_resid'], solver="brentq")
def Phillips_Curve(pi, MC, Y, r_ante, epsilon_p, kappa_p):
    nkpc_resid = (1 + pi).apply(np.log) - (kappa_p * (MC - MC_ss)
                                           + (1 / (1 + r_ante)) * (Y(+1) / Y) * (1 + pi(+1)).apply(np.log))
    return nkpc_resid

@sj.solved(unknowns={'i': (-.5, 0.4)}, targets=['taylor_resid'], solver="brentq")
def taylor(i, pi, Y, ev, rho_r, phi_y, phi_pi):
    taylor_resid = i - rho_r * i(-1) - (1 - rho_r) * (phi_pi * pi + phi_y * Y) - ev
    return taylor_resid

@sj.simple
def matching(theta, chi):
    eta = chi * theta ** (1 - alpha)
    phi = chi * theta ** (-alpha)
    return eta, phi

@sj.simple
def production(Z, N):
    Y = Z * N
    return Y

@sj.simple
def ex_post_longbonds_rate(qb):
    r = (1 + delta * qb) / qb(-1) - 1
    return r

@sj.solved(unknowns={'qb': (0.1, 30.0)}, targets=['lbp_resid'], solver="brentq")
def longbonds_price(qb, r_ante):
    lbp_resid = qb - (1 + delta * qb(+1)) / (1 + r_ante)
    return lbp_resid

@sj.simple
def vacancies(N, phi, job_sep):
    v = (N - (1 - job_sep(-1)) * N(-1)) / phi
    return v

@sj.simple
def mkt_clearing(C, G, A, qb, B, w, N, U1, U2, U3, U4, U5):
    Y_priv = (1 - tau_ss) * wage_ss * .5 * (U3 + U4 + U5) + (1 - tau_ss) * wage_ss * .2 * (U1 + U2)
    goods_mkt = C + G - w * N - Y_priv
    asset_mkt = A - qb * B
    return goods_mkt, asset_mkt, Y_priv

@sj.simple
def fisher_clearing(r_ante, pi, i):
    fisher_resid = 1 + r_ante - ((1 + i) / (1 + pi(+1)))
    return fisher_resid

@sj.simple
def fisher_clearing_fixed_real_rate(pi):
    i = (1 + pi(+1)) * (1 + r_ss) - 1
    return i

# ---- financing families ----
# tau-financed: ONE rule for everything; the tax cut is the exogenous
# shifter dtau_x riding on the same phi_b rule (BUG-074 fix construction).
@sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
def fiscal_taufin(B, N, qb, G, w, v, pi, phi_b, UI, U1, U2, U3, U4, transfers, UI_extend, deficit_T, UI_rr, dtau_x):
    tau = tau_ss + dtau_x + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss
    fiscal_resid = (1 + delta * qb) * B(-1) + G + transfers + UI * (U1 + U2) \
        + UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2) \
        + UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4) \
        + - qb * B - tau * w * N
    UI_extension_cost = UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
    UI_rr_cost = UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)
    tax_cost = (tau_ss + dtau_x) * 1.0 * N_ss
    tau_rule = tau - tau_ss - dtau_x
    debt = qb * B
    return fiscal_resid, tau, UI_extension_cost, UI_rr_cost, tax_cost, tau_rule, debt

@sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
def fiscal_taufin_fixed_real(B, N, G, w, v, pi, phi_b, UI, U1, U2, U3, U4, transfers, UI_extend, deficit_T, UI_rr, dtau_x):
    tau = tau_ss + dtau_x + phi_b * qb_ss * (B(deficit_T) - B_ss) / Y_ss
    fiscal_resid = (1 + delta * qb_ss) * B(-1) + G + transfers + UI * (U1 + U2) \
        + UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2) \
        + UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4) \
        + - qb_ss * B - tau * w * N
    UI_extension_cost = UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
    UI_rr_cost = UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)
    tax_cost = (tau_ss + dtau_x) * 1.0 * N_ss
    tau_rule = tau - tau_ss - dtau_x
    return fiscal_resid, tau, UI_extension_cost, UI_rr_cost, tax_cost, tau_rule

# G-financed: tau exogenous-shiftable (no rule), G rule stabilizes debt.
# Generalized vs production fiscal_G: carries UI_extend/UI_rr cost terms
# (zero in the tax-cut experiment => production anchor preserved).
@sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
def fiscal_Gfin(B, N, qb, w, v, pi, UI, U1, U2, U3, U4, transfers, UI_extend, UI_rr, phi_G, deficit_T, dtau_x):
    tau = tau_ss + dtau_x
    G = G_ss + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss
    fiscal_resid = (1 + delta * qb) * B(-1) + G + transfers + UI * (U1 + U2) \
        + UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2) \
        + UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4) \
        + - qb * B - tau * w * N
    UI_extension_cost = UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
    UI_rr_cost = UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)
    tax_cost = (tau_ss + dtau_x) * 1.0 * N_ss
    return fiscal_resid, tau, G, UI_extension_cost, UI_rr_cost, tax_cost

@sj.solved(unknowns={'B': (0.0, 10)}, targets=['fiscal_resid'], solver="brentq")
def fiscal_Gfin_fixed_real(B, N, w, v, pi, UI, U1, U2, U3, U4, transfers, UI_extend, UI_rr, phi_G, deficit_T, dtau_x):
    tau = tau_ss + dtau_x
    G = G_ss + phi_G * qb_ss * (B(deficit_T) - B_ss) / Y_ss
    fiscal_resid = (1 + delta * qb_ss) * B(-1) + G + transfers + UI * (U1 + U2) \
        + UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2) \
        + UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4) \
        + - qb_ss * B - tau * w * N
    UI_extension_cost = UI_extend * wage_ss * (1 - tau_ss) * (U3 + U4)
    UI_rr_cost = UI_rr * wage_ss * (1 - tau_ss) * (U1 + U2)
    tax_cost = (tau_ss + dtau_x) * 1.0 * N_ss
    return fiscal_resid, tau, G, UI_extension_cost, UI_rr_cost, tax_cost

SS = SteadyStateDict({
    "asset_mkt": 0.0, "goods_mkt": 0.0, "fiscal_resid": 0.0, "nkpc_resid": 0.0,
    "taylor_resid": 0.0, "lbp_resid": 0.0,
    "epsilon_p": epsilon_p, "U": (1 - N_ss),
    "U1": ss_dstn[1], "U2": ss_dstn[2], "U3": ss_dstn[3], "U4": ss_dstn[4],
    "U5": ss_dstn[5], "HC": MC_ss * Z_ss, "MC": MC_ss, "C": C_ss_sim,
    "r": r_ss, "r_ante": r_ss, "Y": Y_ss, "B": B_ss, "G": G_ss,
    "A": A_ss_sim, "tau": tau_ss, "eta": eta_ss, "phi_b": 0.1, "phi_w": 1.0,
    "N": N_ss, "phi": phi_ss, "v": v_ss, "ev": 0.0, "Z": Z_ss,
    "job_sep": job_sep, "w": wage_ss, "pi": pi_ss, "i": r_ss, "qb": qb_ss,
    "varphi": varphi, "rho_r": 0.0, "kappa_p": kappa_p_ss, "phi_pi": 1.5,
    "phi_y": 0.0, "chi": chi_ss, "theta": theta_ss, "UI": UI,
    "transfers": 0.0, "UI_extend": 0.0, "UI_rr": 0.0, "deficit_T": -1,
    "UI_extension_cost": 0.0, "UI_rr_cost": 0.0, "dtau_x": 0.0,
    "tax_cost": tau_ss * wage_ss * N_ss, "tau_rule": 0.0, "phi_G": -0.015,
    "debt": qb_ss * B_ss, "lag": -1,
})

common_taylor = [Jacobian_Dict, longbonds_price, ex_post_longbonds_rate,
                 production, matching, taylor, Phillips_Curve, marginal_cost,
                 UJAC_dict, hiring_cost, wage_, vacancies, unemployment1,
                 fisher_clearing, mkt_clearing]
common_fr = [Jacobian_Dict, production, matching, Phillips_Curve,
             marginal_cost, UJAC_dict, hiring_cost, wage_, vacancies,
             unemployment1, fisher_clearing_fixed_real_rate, mkt_clearing]

M = {
    ("tau", "taylor"): create_model(common_taylor + [fiscal_taufin], name="tf_t"),
    ("tau", "fixed_real"): create_model(common_fr + [fiscal_taufin_fixed_real], name="tf_fr"),
    ("G", "taylor"): create_model(common_taylor + [fiscal_Gfin], name="gf_t"),
    ("G", "fixed_real"): create_model(common_fr + [fiscal_Gfin_fixed_real], name="gf_fr"),
}

def npv(x, n):
    x = np.asarray(x)
    return float(np.sum(x[:n] / R ** np.arange(n)))

INSTR = ['transfers', 'tau', 'UI_extend', 'UI_rr', 'eta', 'w', 'r']

def dW_of(irf):
    T = 300
    out = np.zeros(T)
    for x in INSTR:
        if x in irf:
            p = np.asarray(irf[x])
            if x == 'tau':
                p = p  # total tau deviation (shifter + rule) — households see it all
            out += W_spl[x] @ p
    return out

shock_paths = {
    "transfers": ("transfers", np.zeros(bigT)),
    "UI_extensions": ("UI_extend", np.zeros(bigT)),
    "tax_cut": ("dtau_x", np.zeros(bigT)),
}
shock_paths["transfers"][1][:1] = C_ss * .05
shock_paths["UI_extensions"][1][:4] = .2
shock_paths["tax_cut"][1][:8] = -.02
COSTK = {"transfers": "transfers", "UI_extensions": "UI_extension_cost",
         "tax_cut": "tax_cost"}

print(f"{'policy':>14s} {'financing':>10s} {'regime':>14s} {'spend(20)':>10s} "
      f"{'W(20)':>8s} {'premium':>8s} {'repaid<=20':>10s}")
results = {}
for pol in ("transfers", "UI_extensions", "tax_cut"):
    var, path = shock_paths[pol]
    for fin in ("tau", "G"):
        for reg in ("taylor", "fixed_nominal", "fixed_real"):
            mkey = (fin, "fixed_real" if reg == "fixed_real" else "taylor")
            ssd = deepcopy(SS)
            ssd['phi_w'] = 0.837
            ssd['deficit_T'] = -1
            ssd['phi_b'] = 0.015
            ssd['phi_G'] = -0.015
            ssd['phi_pi'] = 0.0 if reg == "fixed_nominal" else 1.5
            unk = ['theta'] if reg == "fixed_real" else ['theta', 'r_ante']
            tgt = ['asset_mkt'] if reg == "fixed_real" else ['asset_mkt', 'fisher_resid']
            irf = M[mkey].solve_impulse_linear(ssd, unk, tgt, {var: path})
            sgn = -1.0 if pol == "tax_cut" else 1.0
            cost = abs(npv(irf[COSTK[pol]], 300))
            sp20 = sgn * npv(irf['C'], 20) / cost * (1 if pol != "tax_cut" else -1)
            sp20 = abs(npv(irf['C'], 20)) / cost
            w20 = abs(npv(dW_of(irf), 20)) / (up_pop * cost)
            repaid = ""
            if fin == "tau" and 'tau_rule' in irf:
                repaid = f"{npv(np.asarray(irf['tau_rule']) * wage_ss * N_ss, 20) / cost:10.1%}"
            print(f"{pol:>14s} {fin:>10s} {reg:>14s} {sp20:10.3f} {w20:8.3f} "
                  f"{w20 - sp20:+8.3f} {repaid:>10s}")
            results[(pol, fin, reg)] = (sp20, w20)

print("\nANCHOR CHECKS vs production 3x3 (should match to solver precision):")
prod = {("transfers", "G", None): None}
anchors = {("transfers", "tau", "taylor"): 1.611, ("transfers", "tau", "fixed_real"): 1.207,
           ("UI_extensions", "tau", "taylor"): 1.670, ("UI_extensions", "tau", "fixed_real"): 1.317,
           ("tax_cut", "G", "taylor"): 1.732, ("tax_cut", "G", "fixed_real"): 1.429}
for k, v in anchors.items():
    got = results[k][0]
    print(f"  {k}: got {got:.3f} vs production-h20 {v:.3f}  diff {got - v:+.4f}")
